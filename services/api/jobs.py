import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

from .db import json_dump, now
from .errors import ApiError
from .indexing import extraction_content_hash
from .query import empty_lease


class JobSupervisor:
    def __init__(self, db, indexer, settings, governor=None, ingestion_runner=None):
        self.db, self.indexer, self.settings = db, indexer, settings
        self.governor, self.ingestion_runner = governor, ingestion_runner
        self._task = None
        self._closing = False
        self._active = None
        self._process = None
        self._suspended = False
        self._telemetry_lock = threading.Lock()
        self._telemetry = {"cache_checks": 0, "cache_hits": 0, "cache_misses": 0,
                           "extraction_reuses": 0, "native_worker_launches": 0,
                           "injected_runner_calls": 0, "last_extraction": None}

    def diagnostics(self):
        with self._telemetry_lock:
            return {**self._telemetry, "scope": "current_process",
                    "reuse_definition": "Verified ready extraction revision, or ready_partial one when the index identity changed, used without launching a worker; partial state and warnings are kept",
                    "worker_definition": "Successful create_subprocess_exec of the native ingestion worker; OCR work is reported by extraction provenance"}

    def record_extraction(self, job, method, result=None):
        with self._telemetry_lock:
            field = {"verified_cache": "extraction_reuses", "native_worker": "native_worker_launches", "injected_runner": "injected_runner_calls"}[method]
            self._telemetry[field] += 1
            self._telemetry["last_extraction"] = {"job_id": job["id"], "version_id": job["version_id"], "method": method,
                "extraction_revision_id": result.get("extraction_revision_id") if result else None,
                "pipeline_fingerprint": result.get("pipeline_fingerprint", result.get("fingerprint")) if result else None}

    def start(self):
        self._task = asyncio.create_task(self.loop())

    def cancelled(self, job_id):
        row = self.db.one("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,))
        return self._closing or not row or bool(row["cancel_requested"])

    def checkpoint_requested(self):
        manual = self.db.one("SELECT pause_requested FROM jobs WHERE id=?", (self._active,)) if self._active else None
        return self._closing or self._suspended or bool(manual and manual["pause_requested"]) or bool(self.governor and self.governor.should_checkpoint())

    async def loop(self):
        while not self._closing:
            job = self.db.one("SELECT * FROM jobs WHERE state='queued' AND cancel_requested=0 ORDER BY created_at LIMIT 1")
            if self._suspended or job is None or (self.governor and not self.governor.allow_ingestion()):
                await asyncio.sleep(0.5)
                continue
            try:
                lease = self.governor.ingestion() if self.governor else empty_lease()
                async with lease:
                    self._active = job["id"]
                    await self.run(job)
            except asyncio.CancelledError:
                break
            except Exception as error:
                admission_failure = error.__class__.__name__ == "ResourceAdmissionError"
                code = error.code if isinstance(error, ApiError) else ("resource_admission_denied" if admission_failure else "ingestion_failed")
                message = error.message if isinstance(error, ApiError) else (str(error) if admission_failure else "Traitement interrompu ; consulter les diagnostics locaux.")
                paused = code in {"checkpointed", "interrupted", "insufficient_memory", "resource_admission_denied"}
                state = "paused" if paused else ("cancelled" if self.cancelled(job["id"]) else "error")
                self.db.execute("UPDATE jobs SET state=?,stage=?,error_code=?,error_message=?,lease_pid=NULL,updated_at=? WHERE id=?", (state, state, code, message, now(), job["id"]))
                self.db.execute("UPDATE documents SET state=?,updated_at=? WHERE id=? AND active_generation_id IS NULL", ("paused" if paused else state, now(), job["document_id"]))
                if paused:
                    await asyncio.sleep(1)
            finally:
                self._active = None

    async def run(self, job):
        version = self.db.version(job["version_id"])
        directory = self.settings.data_dir / "extractions" / job["version_id"] / job["id"]
        directory.mkdir(parents=True, exist_ok=True)
        request_path = directory / "worker-request.json"
        result_path = directory / "worker-result.json"
        cancel_path = directory / "checkpoint-request"
        if cancel_path.exists():
            cancel_path.unlink()
        request = {"path": version["blob_path"], "output_dir": str(directory), "config": self.settings.profile,
                   "version_id": version["id"], "cancel_path": str(cancel_path)}
        self.db.execute("UPDATE jobs SET state='extracting',stage='extracting',attempts=attempts+1,progress=0.05,heartbeat_at=?,updated_at=? WHERE id=?", (now(), now(), job["id"]))
        cached = await asyncio.to_thread(self.cached_extraction, version) if not self.ingestion_runner else None
        if cached:
            result, extraction_path = cached
            self.record_extraction(job, "verified_cache", result)
        elif self.ingestion_runner:
            self.record_extraction(job, "injected_runner")
            result = await self.ingestion_runner(request)
        else:
            request_path.write_text(json_dump(request), encoding="utf-8")
            environment = os.environ.copy()
            environment.update({"HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
            kwargs = {"cwd": str(self.settings.root), "env": environment, "stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL}
            if os.name == "nt":
                import subprocess
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "services.ingestion.worker", "--request", str(request_path), "--result", str(result_path), **kwargs)
            self.record_extraction(job, "native_worker")
            self._process = process
            self.db.execute("UPDATE jobs SET lease_pid=? WHERE id=?", (process.pid, job["id"]))
            last_progress = time.monotonic()
            durable_signature = None
            watchdog_error = None
            while process.returncode is None:
                if self.cancelled(job["id"]) or self.checkpoint_requested():
                    cancel_path.touch(exist_ok=True)
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.5)
                except TimeoutError:
                    self.db.execute("UPDATE jobs SET heartbeat_at=?,updated_at=? WHERE id=?", (now(), now(), job["id"]))
                    files = [(path.name, path.stat().st_mtime_ns) for path in directory.glob("window-*.json")]
                    signature = tuple(sorted(files))
                    if signature != durable_signature:
                        durable_signature, last_progress = signature, time.monotonic()
                    scheduling = self.settings.value("resources", "scheduling", {})
                    no_progress = scheduling.get("watchdog_no_progress_seconds_initial", 300)
                    window_limit = scheduling.get("watchdog_window_seconds_initial", 900)
                    if time.monotonic() - last_progress > min(no_progress, window_limit):
                        cancel_path.touch(exist_ok=True)
                        # A proven stalled owned subprocess is distinct from normal interactive checkpointing.
                        await asyncio.to_thread(self.terminate_worker_children, process.pid)
                        process.terminate()
                        await process.wait()
                        watchdog_error = {"output_dir": str(directory), "reason": "watchdog_no_progress" if no_progress <= window_limit else "watchdog_window_deadline", "durable_windows": [item[0] for item in signature], "no_progress_seconds": no_progress, "window_limit_seconds": window_limit}
                        self.db.execute("UPDATE jobs SET checkpoint_json=? WHERE id=?", (json_dump(watchdog_error), job["id"]))
            self._process = None
            if watchdog_error:
                raise ApiError("interrupted", "Worker arrêté par watchdog sans progrès ; reprise manuelle depuis les fenêtres durables.", 503)
            if not result_path.is_file():
                raise ApiError("worker_failed", "Le worker n'a pas produit son résultat.", 503)
            envelope = json.loads(result_path.read_text(encoding="utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise ApiError(error.get("code", "worker_failed"), error.get("message", "Le worker a échoué."), 503)
            result = envelope["result"]
        if not cached:
            extraction_path = directory / "extraction.json"
        if self.cancelled(job["id"]):
            raise ApiError("cancelled", "Travail annulé.", 409)
        if result.get("status") in {"interrupted", "paused", "checkpointed"} or self.checkpoint_requested():
            self.db.execute("UPDATE jobs SET checkpoint_json=? WHERE id=?", (json_dump({"output_dir": str(directory)}), job["id"]))
            raise ApiError("checkpointed", "Indexation mise en pause au checkpoint ; reprise manuelle.", 409)
        try:
            await self.indexer.index(job["id"], result, extraction_path, lambda: self.cancelled(job["id"]) or self.checkpoint_requested())
        except ApiError as error:
            if error.code == "cancelled" and not self.cancelled(job["id"]) and self.checkpoint_requested():
                raise ApiError("checkpointed", "Indexation mise en pause au checkpoint ; reprise manuelle.", 409) from error
            raise

    def cached_extraction(self, version):
        with self._telemetry_lock:
            self._telemetry["cache_checks"] += 1
        from services.ingestion import extraction_fingerprint
        fingerprint = extraction_fingerprint(self.settings.profile)
        root = (self.settings.data_dir / "extractions").resolve()
        for revision in self.db.rows("SELECT * FROM extraction_revisions WHERE version_id=? AND fingerprint=? AND path IS NOT NULL ORDER BY created_at DESC", (version["id"], fingerprint)):
            path = Path(revision["path"]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                continue
            try:
                extraction = json.loads(path.read_text(encoding="utf-8"))
                if (extraction.get("sha256") == version["sha256"] and extraction.get("pipeline_fingerprint") == fingerprint
                        and (extraction.get("status") == "ready" or (extraction.get("status") == "ready_partial" and self.dense_identity_changed(revision["id"], fingerprint)))
                        and extraction.get("extraction_revision_id") == revision["id"]
                        and extraction_content_hash(extraction) == revision["source_hash"]):
                    with self._telemetry_lock:
                        self._telemetry["cache_hits"] += 1
                    return extraction, path
            except (ValueError, KeyError, OSError):
                continue
        with self._telemetry_lock:
            self._telemetry["cache_misses"] += 1
        return None

    def dense_identity_changed(self, revision_id, extraction_fingerprint):
        # Une extraction partielle n'est reprise que si l'identité d'index (embedding, découpage) diffère de la
        # dernière génération de cette révision ; à identité égale, le réindex relance le worker pour retenter
        # les pages en échec (erreurs page-locales éventuellement transitoires).
        latest = self.db.one("SELECT fingerprint FROM index_generations WHERE extraction_revision_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (revision_id,))
        current = self.indexer.generation_fingerprint(extraction_fingerprint) if hasattr(self.indexer, "generation_fingerprint") else None
        return bool(latest and current) and latest["fingerprint"] != current

    @staticmethod
    def terminate_worker_children(pid):
        import psutil
        try:
            children = psutil.Process(pid).children(recursive=True)
        except psutil.NoSuchProcess:
            return
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=1)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass

    def cancel(self, job_id):
        row = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        state = row["state"] if row["state"] in {"ready", "ready_partial", "cancelled", "error"} else ("cancelling" if job_id == self._active else "cancelled")
        self.db.execute("UPDATE jobs SET cancel_requested=1,state=?,updated_at=? WHERE id=?", (state, now(), job_id))
        return {"job_id": job_id, "state": state}

    def resume(self, job_id):
        row = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        if row["state"] not in {"paused", "error", "cancelled"}:
            raise ApiError("job_not_resumable", "Ce travail ne peut pas être repris dans son état actuel.", 409)
        if row["attempts"] >= 3 and row["state"] == "error":
            raise ApiError("retry_limit", "Limite de reprises atteinte ; corriger la cause puis réindexer.", 409)
        self.db.version(row["version_id"])
        if self.governor:
            try:
                self.governor.resume_ingestion()
            except RuntimeError as error:
                raise ApiError("interaction_active", "Attendre la fin de la question avant de reprendre l'indexation.", 409) from error
        self._suspended = False
        self.db.execute("UPDATE jobs SET state='queued',stage='resume',cancel_requested=0,pause_requested=0,error_code=NULL,error_message=NULL,updated_at=? WHERE id=?", (now(), job_id))
        return {"job_id": job_id, "state": "queued"}

    def pause(self, job_id):
        row = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        if row["state"] in {"ready", "ready_partial", "error", "cancelled"}:
            raise ApiError("job_not_pauseable", "Ce travail est déjà terminal.", 409)
        state = "pausing" if self._active == job_id else "paused"
        self.db.execute("UPDATE jobs SET pause_requested=1,state=?,stage=?,updated_at=? WHERE id=?", (state, state, now(), job_id))
        return {"job_id": job_id, "state": state, "pause_policy": "cooperative_checkpoint"}

    def request_pause_all(self):
        self._suspended = True
        if self._active:
            self.pause(self._active)
        return {"state": "pausing" if self._active else "interactive", "active_job": self._active}

    async def close(self):
        self._closing = True
        if self._active:
            row = self.db.one("SELECT version_id FROM jobs WHERE id=?", (self._active,))
            if row:
                path = self.settings.data_dir / "extractions" / row["version_id"] / self._active / "checkpoint-request"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
        if self._task:
            # Let the isolated worker reach a safe checkpoint; no nominal forced kill.
            await self._task

    async def quiesce(self):
        self._suspended = True
        if self._active:
            row = self.db.one("SELECT version_id FROM jobs WHERE id=?", (self._active,))
            if row:
                (self.settings.data_dir / "extractions" / row["version_id"] / self._active / "checkpoint-request").touch(exist_ok=True)
        while self._active or self._process:
            await asyncio.sleep(0.1)
        return {"active_job": None, "mutations_paused": True}

    def resume_after_backup(self):
        self._suspended = False
