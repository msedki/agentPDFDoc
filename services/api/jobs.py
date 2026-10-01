import asyncio
import contextlib
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from services.runtime.platforms import native_executable

from .background import FailureLog, finish, log_unexpected_end
from .db import json_dump, now
from .errors import ApiError
from .indexing import extraction_content_hash
from .query import empty_lease

logger = logging.getLogger("rag.jobs")

# Secrets de l'instance absents de l'environnement du worker, qui analyse des PDF non fiables (moindre privilège) :
# jeton de contrôle de l'API, clé Qdrant transmise à l'API et, si elle était présente, celle destinée à Qdrant.
# Défense en profondeur seulement : le worker tourne sous le compte de l'API et peut lire les mêmes secrets dans
# `<data_dir>/control/admin-token` et `<data_dir>/control/qdrant-api-key` (écrits par le superviseur) ; aucune
# isolation par compte ou par ACL n'est en place.
WORKER_WITHHELD_ENVIRONMENT = frozenset({"RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "QDRANT__SERVICE__API_KEY"})
WORKER_FIXED_ENVIRONMENT = {"HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false",
                            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}

WATCHDOG_MESSAGES = {
    "watchdog_no_progress": "Worker arrêté par watchdog sans progrès ; reprise manuelle depuis les fenêtres durables.",
    "watchdog_window_deadline": "Worker arrêté par watchdog : fenêtre de pages au-delà de sa durée maximale ; reprise manuelle depuis les fenêtres durables.",
}


def worker_environment(source=None):
    """Environnement du worker d'extraction : celui de l'API sans ses secrets, plus les réglages hors ligne et de threads."""
    source = os.environ if source is None else source
    # Noms comparés en majuscules : sous Windows, os.environ ignore la casse.
    environment = {name: value for name, value in source.items() if name.upper() not in WORKER_WITHHELD_ENVIRONMENT}
    environment.update(WORKER_FIXED_ENVIRONMENT)
    return environment


def worker_profile(profile):
    """Profil transmis au worker et haché par l'empreinte d'extraction.

    La commande Tesseract du profil livré nomme l'exécutable Windows ; hors Windows, le même chemin sans `.exe`
    est employé (W018). Sous Windows, le profil est rendu tel quel : requête et empreinte restent inchangées.
    """
    pdf = profile.get("pdf")
    if not isinstance(pdf, dict) or not isinstance(pdf.get("tesseract_cmd"), str):
        return profile
    command = native_executable(pdf["tesseract_cmd"])
    if command == pdf["tesseract_cmd"]:
        return profile
    return {**profile, "pdf": {**pdf, "tesseract_cmd": command}}


# Comptabilité des enfants attendus : sous Linux, le temps CPU d'un processus terminé puis attendu (wait) est ajouté par
# le noyau aux champs cutime et cstime de son parent (proc(5)), lus par psutil comme children_user et children_system ;
# psutil les laisse à 0 sous Windows et macOS (docstring de psutil.Process.cpu_times).
WAITED_CHILDREN_ACCOUNTED = sys.platform not in ("win32", "darwin")


def process_tree_cpu_seconds(pid, observed, waited_children_accounted=WAITED_CHILDREN_ACCOUNTED):
    """Temps CPU cumulé du worker et de ses descendants (Tesseract), chaque seconde comptée une fois.

    Chaque processus de l'arbre compte `user + system + children_user + children_system`, lus ensemble.
    - Enfants attendus reportés sur leur parent (Linux) : seule la lecture courante est sommée. Un enfant attendu
      quitte l'arbre et son temps est déjà dans les champs children_* de son parent ; garder sa dernière valeur le
      compterait deux fois. Un descendant orphelin qui quitte l'arbre fait baisser la somme : l'intervalle est alors
      lu comme inactif.
    - Enfants non reportés (Windows) : `observed` garde la dernière valeur lue de chaque processus (pid, date de
      création), pour qu'un enfant terminé conserve sa contribution.
    Rend None si le worker n'existe plus.
    """
    import psutil
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return None
    try:
        processes = [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = [root]
    current: dict[tuple[int, float], float] = {}
    # Racine lue en premier : un enfant attendu entre deux lectures manque une fois au lieu d'être compté deux fois.
    for process in processes:
        try:
            with process.oneshot():
                times = process.cpu_times()
                key = (process.pid, process.create_time())
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            if process is root:
                return None
            continue
        current[key] = times.user + times.system + getattr(times, "children_user", 0.0) + getattr(times, "children_system", 0.0)
    if waited_children_accounted:
        observed.clear()
        observed.update(current)
        return sum(current.values())
    for key, total in current.items():
        observed[key] = max(total, observed.get(key, 0.0))
    return sum(observed.values())


class WorkerWatchdog:
    """Watchdog du worker d'extraction, distinct de la pause coopérative (IMPLEMENTATION.md, CONFIGURATION.md).

    Deux limites indépendantes du profil (`resources.scheduling`) :
    - absence de progrès (`watchdog_no_progress_seconds_initial`, 300 s) : ni fichier nouveau ou modifié dans le
      dossier du travail (fenêtre durable, conversion intermédiaire `docling-*.json`, préflight, trace de cycle
      de vie), ni temps CPU du worker et de ses enfants au-delà d'une fraction d'un cœur ;
    - durée maximale d'une fenêtre (`watchdog_window_seconds_initial`, 900 s) : temps écoulé depuis la dernière
      fenêtre durable `window-*.json`, ou depuis le lancement, même si le worker reste actif.
    Un worker qui progresse n'est arrêté qu'au-delà de la durée maximale d'une fenêtre.
    """

    cpu_probe_interval_seconds = 5.0
    # Part d'un cœur, sur l'intervalle de mesure, au-dessous de laquelle le worker est tenu pour inactif.
    cpu_active_ratio = 0.1
    activity_patterns = ("docling-*.json", "preflight.json", "worker-lifecycle.jsonl", "extraction.json")

    def __init__(self, directory, pid, no_progress_seconds, window_seconds, clock=time.monotonic, cpu_seconds=None):
        self.directory, self.no_progress_seconds, self.window_seconds = Path(directory), no_progress_seconds, window_seconds
        self.clock = clock
        self._observed_cpu: dict[tuple[int, float], float] = {}
        self.cpu_seconds = cpu_seconds or (lambda: process_tree_cpu_seconds(pid, self._observed_cpu))
        started = clock()
        self.last_progress = self.last_window = started
        self.window_signature: tuple[Any, ...] | None = None
        self.activity_signature: tuple[Any, ...] | None = None
        self._cpu_probe: tuple[float, float] | None = None

    def _signature(self, patterns):
        files = []
        for pattern in patterns:
            for path in self.directory.glob(pattern):
                try:
                    status = path.stat()
                except OSError:
                    continue
                files.append((path.name, status.st_size, status.st_mtime_ns))
        return tuple(sorted(files))

    def durable_windows(self):
        return [item[0] for item in self.window_signature or ()]

    def observe(self):
        """Relève l'activité du worker ; rend le motif d'arrêt (`watchdog_window_deadline`, `watchdog_no_progress`) ou None."""
        now = self.clock()
        windows = self._signature(("window-*.json",))
        if windows != self.window_signature:
            self.window_signature, self.last_window, self.last_progress = windows, now, now
        activity = self._signature(self.activity_patterns)
        if activity != self.activity_signature:
            self.activity_signature, self.last_progress = activity, now
        if self._cpu_probe is None or now - self._cpu_probe[0] >= self.cpu_probe_interval_seconds:
            cpu = self.cpu_seconds()
            if cpu is not None:
                if self._cpu_probe is not None and cpu - self._cpu_probe[1] >= self.cpu_active_ratio * (now - self._cpu_probe[0]):
                    self.last_progress = now
                self._cpu_probe = (now, cpu)
        if now - self.last_window > self.window_seconds:
            return "watchdog_window_deadline"
        if now - self.last_progress > self.no_progress_seconds:
            return "watchdog_no_progress"
        return None

    def report(self, reason):
        now = self.clock()
        return {"output_dir": str(self.directory), "reason": reason, "durable_windows": self.durable_windows(),
                "no_progress_seconds": self.no_progress_seconds, "window_limit_seconds": self.window_seconds,
                "seconds_since_progress": round(now - self.last_progress, 1), "seconds_since_durable_window": round(now - self.last_window, 1)}


class JobSupervisor:
    # Reprise de la boucle après une erreur de lecture de la file (SQLite verrouillé, gouverneur indisponible).
    retry_base_seconds = 0.5
    retry_max_seconds = 30.0

    def __init__(self, db, indexer, settings, governor=None, ingestion_runner=None):
        self.db, self.indexer, self.settings = db, indexer, settings
        self.governor, self.ingestion_runner = governor, ingestion_runner
        self._task = None
        self._closing = False
        self._active = None
        self._process = None
        self._suspended = False
        self._telemetry_lock = threading.Lock()
        self._telemetry: dict[str, Any] = {"cache_checks": 0, "cache_hits": 0, "cache_misses": 0,
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
        log_unexpected_end(self._task, "d'ingestion", lambda: self._closing, logger)

    def cancelled(self, job_id):
        # Seule une demande explicite (ou un job disparu) annule ; la fermeture de l'API passe par
        # checkpoint_requested() et laisse le job en pause, reprenable depuis ses fenêtres durables.
        row = self.db.one("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,))
        return not row or bool(row["cancel_requested"])

    def checkpoint_requested(self):
        manual = self.db.one("SELECT pause_requested FROM jobs WHERE id=?", (self._active,)) if self._active else None
        return self._closing or self._suspended or bool(manual and manual["pause_requested"]) or bool(self.governor and self.governor.should_checkpoint())

    async def loop(self):
        """Traite la file dans l'ordre d'import ; une erreur ne l'arrête jamais (reprise bornée, journalisée)."""
        failures = FailureLog(logger, self.retry_base_seconds, self.retry_max_seconds)
        while not self._closing:
            try:
                job = self.db.one("SELECT * FROM jobs WHERE state='queued' AND cancel_requested=0 ORDER BY created_at LIMIT 1")
                idle = self._suspended or job is None or bool(self.governor and not self.governor.allow_ingestion())
            except Exception as error:
                await asyncio.sleep(failures.failure("Sélection du prochain traitement impossible (file SQLite ou gouverneur de ressources)", error))
                continue
            failures.success()
            if idle:
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
                try:
                    paused = self.record_failure(job, error)
                except Exception as recording_error:
                    # Le travail garde son état précédent jusqu'au prochain démarrage, qui le met en pause (db.initialize).
                    await asyncio.sleep(failures.failure(f"État du traitement {job['id']} non enregistré après son échec", recording_error))
                    continue
                if paused:
                    await asyncio.sleep(1)
            finally:
                self._active = None

    def record_failure(self, job, error):
        """Enregistre l'issue d'un traitement interrompu ; rend vrai si le travail est mis en pause."""
        if not isinstance(error, ApiError):
            # Cause technique conservée dans le journal de l'API : type, message et pile de l'exception.
            logger.error("Traitement %s interrompu par une erreur inattendue (%s)", job["id"], type(error).__name__, exc_info=error)
        admission_failure = error.__class__.__name__ == "ResourceAdmissionError"
        code = error.code if isinstance(error, ApiError) else ("resource_admission_denied" if admission_failure else "ingestion_failed")
        message = error.message if isinstance(error, ApiError) else (str(error) if admission_failure else "Traitement interrompu ; consulter les diagnostics locaux.")
        paused = code in {"checkpointed", "interrupted", "insufficient_memory", "resource_admission_denied"}
        state = "paused" if paused else ("cancelled" if self.cancelled(job["id"]) else "error")
        with self.db.transaction() as connection:
            connection.execute("UPDATE jobs SET state=?,stage=?,error_code=?,error_message=?,lease_pid=NULL,updated_at=? WHERE id=?", (state, state, code, message, now(), job["id"]))
            # Le document non publié affiche son dernier travail : celui-ci, ou un travail plus récent déjà en file
            # (réindexation demandée pendant l'annulation), jamais l'issue d'un travail remplacé.
            self.db.align_document_states(connection, [job["document_id"]])
        return paused

    async def run(self, job):
        version = self.db.version(job["version_id"])
        directory = self.settings.data_dir / "extractions" / job["version_id"] / job["id"]
        directory.mkdir(parents=True, exist_ok=True)
        request_path = directory / "worker-request.json"
        result_path = directory / "worker-result.json"
        cancel_path = directory / "checkpoint-request"
        if cancel_path.exists():
            cancel_path.unlink()
        # Le résultat d'une exécution précédente (reprise après pause) ne doit jamais être relu comme le nouveau.
        result_path.unlink(missing_ok=True)
        request = {"path": version["blob_path"], "output_dir": str(directory), "config": worker_profile(self.settings.profile),
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
            kwargs: dict[str, Any] = {"cwd": str(self.settings.root), "env": worker_environment(), "stdout": asyncio.subprocess.DEVNULL, "stderr": asyncio.subprocess.DEVNULL}
            if sys.platform == "win32":
                import subprocess
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "services.ingestion.worker", "--request", str(request_path), "--result", str(result_path), **kwargs)
            self.record_extraction(job, "native_worker")
            self._process = process
            self.db.execute("UPDATE jobs SET lease_pid=? WHERE id=?", (process.pid, job["id"]))
            scheduling = self.settings.value("resources", "scheduling", {}) or {}
            watchdog = WorkerWatchdog(directory, process.pid, scheduling.get("watchdog_no_progress_seconds_initial", 300),
                                      scheduling.get("watchdog_window_seconds_initial", 900))
            watchdog_error = None
            while process.returncode is None:
                if self.cancelled(job["id"]) or self.checkpoint_requested():
                    cancel_path.touch(exist_ok=True)
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.5)
                except TimeoutError:
                    self.db.execute("UPDATE jobs SET heartbeat_at=?,updated_at=? WHERE id=?", (now(), now(), job["id"]))
                    reason = await asyncio.to_thread(watchdog.observe)
                    if reason:
                        cancel_path.touch(exist_ok=True)
                        # A proven stalled owned subprocess is distinct from normal interactive checkpointing.
                        await asyncio.to_thread(self.terminate_worker_children, process.pid)
                        # Le worker peut s'être terminé entre la dernière mesure et l'arrêt : son code de sortie est relu.
                        with contextlib.suppress(ProcessLookupError):
                            process.terminate()
                        await process.wait()
                        watchdog_error = watchdog.report(reason)
                        self.db.execute("UPDATE jobs SET checkpoint_json=? WHERE id=?", (json_dump(watchdog_error), job["id"]))
            self._process = None
            if watchdog_error:
                raise ApiError("interrupted", WATCHDOG_MESSAGES[watchdog_error["reason"]], 503)
            if not result_path.is_file():
                raise ApiError("worker_failed", f"Le worker d'extraction s'est arrêté sans résultat (code {process.returncode}) ; reprendre le traitement ou consulter les diagnostics.", 503,
                               {"worker_exit_code": process.returncode})
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
        fingerprint = extraction_fingerprint(worker_profile(self.settings.profile))
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
        self.db.align_document(row["document_id"])
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
        self.db.align_document(row["document_id"])
        return {"job_id": job_id, "state": "queued"}

    def resume_paused(self):
        """Relance en une fois tous les traitements en pause (checkpoint, interruption, pause demandée), dans leur ordre d'import."""
        rows = self.db.rows("SELECT id FROM jobs WHERE state='paused' ORDER BY created_at")
        # Tout ou rien : une question active refuse la reprise avant qu'un seul traitement ne soit relancé.
        if rows and self.governor:
            try:
                self.governor.resume_ingestion()
            except RuntimeError as error:
                raise ApiError("interaction_active", "Attendre la fin de la question avant de reprendre l'indexation.", 409) from error
        for row in rows:
            self.resume(row["id"])
        return {"resumed": len(rows)}

    def pause(self, job_id):
        row = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        if row["state"] in {"ready", "ready_partial", "error", "cancelled"}:
            raise ApiError("job_not_pauseable", "Ce travail est déjà terminal.", 409)
        state = "pausing" if self._active == job_id else "paused"
        self.db.execute("UPDATE jobs SET pause_requested=1,state=?,stage=?,updated_at=? WHERE id=?", (state, state, now(), job_id))
        self.db.align_document(row["document_id"])
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
        # Let the isolated worker reach a safe checkpoint; no nominal forced kill.
        await finish(self._task)

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
