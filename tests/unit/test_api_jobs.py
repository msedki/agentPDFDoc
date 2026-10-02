import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage

from services.api.db import now, uid
from services.api.errors import ApiError
from services.api.jobs import JobSupervisor


def test_api_job_pause_is_cooperative_and_resume_is_manual(storage):
    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    class Governor:
        pause = False
        def should_checkpoint(self):
            return self.pause
        def allow_ingestion(self):
            return not self.pause
        def resume_ingestion(self):
            self.pause = False
        @asynccontextmanager
        async def ingestion(self):
            yield
    governor = Governor()
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        async def runner(request):
            started.set()
            await release.wait()
            return {**extraction, "status": "interrupted"}
        supervisor = JobSupervisor(db, indexer, settings, governor, runner)
        supervisor.start()
        await asyncio.wait_for(started.wait(), 3)
        governor.pause = True
        assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "extracting"
        release.set()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "paused":
                break
            await asyncio.sleep(0.02)
        paused = db.one("SELECT state,error_code,checkpoint_json FROM jobs WHERE id=?", (job_id,))
        assert paused["state"] == "paused" and paused["error_code"] == "checkpointed"
        assert supervisor.diagnostics()["injected_runner_calls"] == 1
        assert supervisor.diagnostics()["native_worker_launches"] == supervisor.diagnostics()["extraction_reuses"] == 0
        assert json.loads(paused["checkpoint_json"])["output_dir"]
        await supervisor.close()
        assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "paused"
        assert supervisor.resume(job_id)["state"] == "queued"
    asyncio.run(scenario())



def test_api_closing_checkpoints_the_active_job_instead_of_cancelling_it(storage):
    """Arrêt propre de l'API pendant une extraction : pause au checkpoint, reprise possible, pas d'annulation."""
    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    class Governor:
        def should_checkpoint(self):
            return False
        def allow_ingestion(self):
            return True
        def resume_ingestion(self):
            pass
        @asynccontextmanager
        async def ingestion(self):
            yield
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        async def runner(request):
            started.set()
            await release.wait()
            return {**extraction, "status": "interrupted"}
        supervisor = JobSupervisor(db, indexer, settings, Governor(), runner)
        supervisor.start()
        await asyncio.wait_for(started.wait(), 3)
        closing = asyncio.create_task(supervisor.close())
        await asyncio.sleep(0.05)
        release.set()
        await asyncio.wait_for(closing, 5)
        row = db.one("SELECT state,error_code,cancel_requested FROM jobs WHERE id=?", (job_id,))
        assert (row["state"], row["error_code"], row["cancel_requested"]) == ("paused", "checkpointed", 0)
        assert supervisor.resume(job_id)["state"] == "queued"
    asyncio.run(scenario())


def document_state(db, document_id):
    return db.one("SELECT state FROM documents WHERE id=?", (document_id,))["state"]


def test_api_document_state_follows_pause_resume_cancel_of_an_unpublished_document(storage):
    settings, db, _, indexer = storage
    pending = db.import_original("folder/pending.pdf", "1" * 64, "pending.pdf")
    supervisor = JobSupervisor(db, indexer, settings)
    assert document_state(db, pending["document_id"]) == "queued"
    supervisor.pause(pending["job_id"])
    assert document_state(db, pending["document_id"]) == "paused"
    supervisor.resume(pending["job_id"])
    assert document_state(db, pending["document_id"]) == "queued"
    supervisor.cancel(pending["job_id"])
    assert document_state(db, pending["document_id"]) == "cancelled"


def test_api_published_document_keeps_its_generation_state_when_a_new_job_pauses(storage):
    imported, _ = import_fixture(storage)
    settings, db, _, indexer = storage
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    JobSupervisor(db, indexer, settings).pause(job_id)
    assert document_state(db, imported["document_id"]) == "ready"


def test_api_startup_realigns_documents_left_behind_their_last_job(storage):
    settings, db, _, _ = storage
    paused = db.import_original("folder/paused.pdf", "2" * 64, "paused.pdf")
    partial = db.import_original("folder/partial.pdf", "3" * 64, "partial.pdf")
    db.execute("UPDATE jobs SET state='paused' WHERE id=?", (paused["job_id"],))
    db.execute("UPDATE jobs SET state='ready_partial' WHERE id=?", (partial["job_id"],))
    db.execute("UPDATE documents SET state='indexing' WHERE id=?", (partial["document_id"],))
    db.initialize()
    assert document_state(db, paused["document_id"]) == "paused"
    assert document_state(db, partial["document_id"]) == "ready_partial"


def test_api_unpublished_partial_extraction_marks_the_document_partial_not_indexing(storage):
    settings, db, _, indexer = storage
    imported = db.import_original("folder/partial.pdf", "4" * 64, "partial.pdf")
    extraction = {"sha256": "4" * 64, "fingerprint": "fixture-native-v1", "page_count": 2, "status": "ready_partial",
                  "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "type": "text", "text": "CCU-21 72 V", "raw_text": "CCU-21 72 V", "bbox": [10, 10, 100, 30], "precision": "block"}]}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    row = db.one("SELECT state,active_generation_id FROM documents WHERE id=?", (imported["document_id"],))
    assert (row["state"], row["active_generation_id"]) == ("ready_partial", None)


def test_api_resume_paused_relaunches_every_paused_job_and_realigns_documents(storage):
    settings, db, _, indexer = storage
    supervisor = JobSupervisor(db, indexer, settings)
    first = db.import_original("folder/first.pdf", "5" * 64, "first.pdf")
    second = db.import_original("folder/second.pdf", "6" * 64, "second.pdf")
    kept = db.import_original("folder/kept.pdf", "7" * 64, "kept.pdf")
    for item in (first, second):
        supervisor.pause(item["job_id"])
    supervisor.cancel(kept["job_id"])
    assert supervisor.resume_paused() == {"resumed": 2}
    assert [document_state(db, item["document_id"]) for item in (first, second, kept)] == ["queued", "queued", "cancelled"]
    assert supervisor.resume_paused() == {"resumed": 0}


def test_api_graphic_only_partial_extraction_is_published_automatically(storage):
    settings, db, _, indexer = storage
    imported = db.import_original("folder/figures.pdf", "8" * 64, "figures.pdf")
    block = {"id": "b0", "type": "text", "text": "CCU-21 72 V", "raw_text": "CCU-21 72 V", "bbox": [10, 10, 100, 30], "precision": "block"}
    extraction = {"sha256": "8" * 64, "fingerprint": "fixture-native-v1", "page_count": 2, "status": "ready_partial", "parser_complete": True,
                  "pages": [{"page_index": 0, "width": 595, "height": 842, "extraction_state": "native", "classification": "native", "blocks": [block],
                             "unresolved_regions": [{"reason": "GRAPHIC_INTERPRETATION_UNAVAILABLE", "precision": "block"}]},
                            {"page_index": 1, "width": 595, "height": 842, "extraction_state": "error", "classification": "graphic_uncertain",
                             "alphanumeric_count": 0, "blocks": [], "unresolved_regions": []}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    row = db.one("SELECT state,active_generation_id FROM documents WHERE id=?", (imported["document_id"],))
    assert row["state"] == "ready" and row["active_generation_id"] is not None
    assert db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"] == "ready"


def test_api_resume_paused_is_refused_as_a_whole_while_a_question_is_active(storage):
    settings, db, _, indexer = storage
    class BusyGovernor:
        def resume_ingestion(self):
            raise RuntimeError("Une interaction est encore active ; reprise différée.")
    first = db.import_original("folder/busy-1.pdf", "9" * 64, "busy-1.pdf")
    second = db.import_original("folder/busy-2.pdf", "a" * 64, "busy-2.pdf")
    idle = JobSupervisor(db, indexer, settings)
    idle.pause(first["job_id"])
    idle.pause(second["job_id"])
    with pytest.raises(ApiError) as refused:
        JobSupervisor(db, indexer, settings, BusyGovernor()).resume_paused()
    assert refused.value.code == "interaction_active"
    assert [db.one("SELECT state FROM jobs WHERE id=?", (item["job_id"],))["state"] for item in (first, second)] == ["paused", "paused"]

def test_api_extraction_cache_reuses_only_verified_revision(storage, monkeypatch):
    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    revision = db.one("SELECT * FROM extraction_revisions")
    extraction = {**extraction, "pipeline_fingerprint": "fixture-native-v1", "extraction_revision_id": revision["id"]}
    path = settings.data_dir / "extractions" / imported["version_id"] / "extraction.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
    db.execute("UPDATE extraction_revisions SET path=? WHERE id=?", (str(path), revision["id"]))
    monkeypatch.setattr("services.ingestion.extraction_fingerprint", lambda config: "fixture-native-v1")
    supervisor = JobSupervisor(db, indexer, settings)
    assert supervisor.cached_extraction(db.version(imported["version_id"]))[1] == path.resolve()
    extraction["pages"][0]["blocks"][0]["text"] = "corruption"
    path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
    assert supervisor.cached_extraction(db.version(imported["version_id"])) is None


@pytest.mark.parametrize("state", ["paused", "error", "cancelled"])
def test_api_job_resume_rejects_removed_document_before_global_resume(storage, state):
    imported, _ = import_fixture(storage)
    settings, db, _, indexer = storage
    db.execute("UPDATE jobs SET state=? WHERE id=?", (state, imported["job_id"]))
    db.execute("UPDATE documents SET deleted_at=? WHERE id=?", (now(), imported["document_id"]))
    class Governor:
        called = False
        def resume_ingestion(self):
            self.called = True
    governor = Governor()
    supervisor = JobSupervisor(db, indexer, settings, governor)
    with pytest.raises(ApiError) as caught:
        supervisor.resume(imported["job_id"])
    assert caught.value.code == "source_removed" and governor.called is False
    assert db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"] == state


def test_api_staging_rejects_removed_document_before_writing(storage):
    imported, extraction = import_fixture(storage)
    _, db, _, indexer = storage
    db.execute("UPDATE documents SET deleted_at=? WHERE id=?", (now(), imported["document_id"]))
    before = db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"]
    with pytest.raises(ApiError) as caught:
        indexer.stage(imported["job_id"], extraction)
    assert caught.value.code == "source_removed"
    assert db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"] == before


def new_job(db, imported):
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    return job_id


def cache_partial_extraction(context, monkeypatch):
    """Indexe une extraction ready_partial (page 2 en échec Docling) avec l'embedding courant, puis l'expose au cache vérifié."""
    from services.api.indexing import extraction_content_hash
    imported, extraction = import_fixture(context)
    settings, db, _, indexer = context
    block = {**extraction["pages"][0]["blocks"][0], "text": "CCU-21 : 72 V (page 1 seule).", "raw_text": "CCU-21 : 72 V (page 1 seule)."}
    partial = {**extraction, "status": "ready_partial", "page_count": 2, "coverage": {"total": 2, "processed": 1, "ocr": 1},
               "warnings": [{"code": "DOCLING_CONVERSION_FAILED", "page_index": 1, "route": "structured"}],
               "pages": [{**extraction["pages"][0], "blocks": [block]}]}
    asyncio.run(indexer.index(new_job(db, imported), partial))
    revision = db.one("SELECT * FROM extraction_revisions WHERE source_hash=?", (extraction_content_hash(partial),))
    cached = {**partial, "pipeline_fingerprint": "fixture-native-v1", "extraction_revision_id": revision["id"]}
    path = settings.data_dir / "extractions" / imported["version_id"] / "partial-run" / "extraction.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    db.execute("UPDATE extraction_revisions SET path=? WHERE id=?", (str(path), revision["id"]))
    monkeypatch.setattr("services.ingestion.extraction_fingerprint", lambda config: "fixture-native-v1")
    return imported, extraction, partial, revision, cached, path


def test_api_embedding_change_reuses_verified_partial_extraction(storage, monkeypatch):
    from test_api_storage import FakeEmbedding

    imported, extraction, partial, revision, cached, path = cache_partial_extraction(storage, monkeypatch)
    settings, db, _, indexer = storage
    active = db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"]
    async def forbidden(*args, **kwargs):
        raise AssertionError("Changer l'embedding ne doit pas relancer l'extraction/OCR")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    class OtherEmbedding(FakeEmbedding):
        calls = 0
        def identity(self):
            return {"fingerprint": "controlled-embedding-b"}
        def embed(self, texts, passage=True):
            self.calls += 1
            return super().embed(texts, passage)
    indexer.embedding = OtherEmbedding()
    job_id = new_job(db, imported)
    supervisor = JobSupervisor(db, indexer, settings)
    asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    observed = supervisor.diagnostics()
    assert observed["extraction_reuses"] == observed["cache_hits"] == 1 and observed["native_worker_launches"] == 0
    assert observed["last_extraction"]["extraction_revision_id"] == revision["id"] and indexer.embedding.calls == 1
    job = db.one("SELECT state,generation_id FROM jobs WHERE id=?", (job_id,))
    generation = db.one("SELECT * FROM index_generations WHERE id=?", (job["generation_id"],))
    assert job["state"] == generation["state"] == "ready_partial" and generation["published_at"] is None
    assert generation["extraction_revision_id"] == revision["id"]
    assert json.loads(generation["warnings_json"]) == partial["warnings"] and json.loads(generation["coverage_json"]) == partial["coverage"]
    assert db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"] == active
    # L'identité dense est désormais celle de la dernière génération : un nouveau réindex retente l'extraction.
    assert supervisor.cached_extraction(db.version(imported["version_id"])) is None
    indexer.embedding = FakeEmbedding()
    assert supervisor.cached_extraction(db.version(imported["version_id"]))[1] == path.resolve()
    path.write_text(json.dumps({**cached, "status": "interrupted"}, ensure_ascii=False), encoding="utf-8")
    assert supervisor.cached_extraction(db.version(imported["version_id"])) is None


def test_api_same_embedding_reindex_retries_partial_extraction(storage, monkeypatch):
    from pathlib import Path

    imported, extraction, partial, revision, cached, path = cache_partial_extraction(storage, monkeypatch)
    settings, db, _, indexer = storage
    launches = []
    class FinishedWorker:
        # Double explicite du worker natif : aucun processus n'est lancé, le résultat simule une reprise réussie.
        returncode, pid = 0, 4242
        async def wait(self):
            return 0
    async def fake_worker(*args, **kwargs):
        launches.append(args)
        Path(args[args.index("--result") + 1]).write_text(json.dumps({"ok": True, "result": {**extraction, "pipeline_fingerprint": "fixture-native-v1"}}), encoding="utf-8")
        return FinishedWorker()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_worker)
    job_id = new_job(db, imported)
    supervisor = JobSupervisor(db, indexer, settings)
    asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    observed = supervisor.diagnostics()
    assert observed["cache_hits"] == observed["extraction_reuses"] == 0 and observed["cache_misses"] == 1
    assert observed["native_worker_launches"] == 1 and len(launches) == 1 and "services.ingestion.worker" in launches[0]
    job = db.one("SELECT state,generation_id FROM jobs WHERE id=?", (job_id,))
    generation = db.one("SELECT * FROM index_generations WHERE id=?", (job["generation_id"],))
    assert job["state"] == generation["state"] == "ready" and generation["extraction_revision_id"] != revision["id"]
    assert db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"] == job["generation_id"]


def test_api_a_worker_that_leaves_no_result_is_not_mistaken_for_a_previous_run(storage, monkeypatch):
    """Reprise d'un job : le résultat de l'exécution précédente ne doit jamais être relu comme le nouveau."""
    from pathlib import Path

    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    job_id = new_job(db, imported)
    stale = settings.data_dir / "extractions" / imported["version_id"] / job_id / "worker-result.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(json.dumps({"ok": True, "result": {**extraction, "pipeline_fingerprint": "exécution précédente"}}), encoding="utf-8")
    class SilentWorker:
        # Double explicite : le worker se termine en erreur sans écrire de résultat.
        returncode, pid = 3, 4343
        async def wait(self):
            return 3
    async def fake_worker(*args, **kwargs):
        assert not Path(args[args.index("--result") + 1]).exists(), "le résultat précédent doit être retiré avant le lancement"
        return SilentWorker()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_worker)
    monkeypatch.setattr(JobSupervisor, "cached_extraction", lambda self, version: None)
    supervisor = JobSupervisor(db, indexer, settings)
    with pytest.raises(ApiError) as failed:
        asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    assert failed.value.code == "worker_failed" and "code 3" in failed.value.message



def launch_capturing_worker(monkeypatch, extraction):
    """Double explicite du lancement du worker : aucun processus, requête et environnement capturés, résultat écrit."""
    from pathlib import Path

    captured = {}
    class FinishedWorker:
        returncode, pid = 0, 4545
        async def wait(self):
            return 0
    async def fake_worker(*args, **kwargs):
        captured["args"], captured["env"] = args, kwargs["env"]
        captured["request"] = json.loads(Path(args[args.index("--request") + 1]).read_text(encoding="utf-8"))
        Path(args[args.index("--result") + 1]).write_text(json.dumps({"ok": True, "result": extraction}), encoding="utf-8")
        return FinishedWorker()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_worker)
    monkeypatch.setattr(JobSupervisor, "cached_extraction", lambda self, version: None)
    return captured


def test_api_worker_environment_withholds_instance_secrets(storage, monkeypatch):
    """C3 : le worker qui analyse des PDF non fiables ne reçoit ni le jeton de contrôle ni les clés Qdrant."""
    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    for name in ("RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "QDRANT__SERVICE__API_KEY"):
        monkeypatch.setenv(name, "secret-de-test-" + name.lower())
    monkeypatch.setenv("RAG_TEST_INHERITED", "conservée")
    captured = launch_capturing_worker(monkeypatch, extraction)
    job_id = new_job(db, imported)
    asyncio.run(JobSupervisor(db, indexer, settings).run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    environment = captured["env"]
    assert not {"RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "QDRANT__SERVICE__API_KEY"} & {name.upper() for name in environment}
    assert not any(value.startswith("secret-de-test-") for value in environment.values())
    assert environment["RAG_TEST_INHERITED"] == "conservée" and environment["HF_HUB_OFFLINE"] == "1" and environment["OMP_NUM_THREADS"] == "2"
    assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "ready"


def test_api_worker_environment_disables_onnxruntime_telemetry():
    """D08.2 (J8, L10) : le worker reçoit ORT_DISABLE_TELEMETRY=1 dès son lancement, même si l'API hérite d'une autre
    valeur ; une dépendance d'extraction qui chargerait ONNX Runtime ne démarre donc pas son client de télémétrie."""
    from services.api.jobs import worker_environment
    assert worker_environment({})["ORT_DISABLE_TELEMETRY"] == "1"
    assert worker_environment({"ORT_DISABLE_TELEMETRY": "0", "PATH": "/usr/bin"}) == {**worker_environment({}), "PATH": "/usr/bin"}


def test_api_worker_receives_the_native_tesseract_command_of_this_platform(storage, monkeypatch):
    """W018 : `.exe` retiré hors Windows dans la requête du worker et dans l'empreinte du cache ; profil Windows inchangé."""
    import sys

    from services.runtime.platforms import native_executable

    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    configured = ".runtime/bin/tesseract-5.4.0/tesseract.exe"
    settings.profile["pdf"] = {"tesseract_cmd": configured, "tessdata_dir": ".runtime/models/tessdata"}
    captured = launch_capturing_worker(monkeypatch, extraction)
    job_id = new_job(db, imported)
    asyncio.run(JobSupervisor(db, indexer, settings).run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    sent = captured["request"]["config"]["pdf"]
    expected = configured if sys.platform == "win32" else ".runtime/bin/tesseract-5.4.0/tesseract"
    assert sent["tesseract_cmd"] == expected == native_executable(configured)
    assert sent["tessdata_dir"] == ".runtime/models/tessdata" and settings.profile["pdf"]["tesseract_cmd"] == configured
    # L'empreinte du cache d'extraction hache le même profil que celui du worker (doubles du lancement retirés).
    monkeypatch.undo()
    hashed = []
    monkeypatch.setattr("services.ingestion.extraction_fingerprint", lambda config: hashed.append(config) or "fixture")
    JobSupervisor(db, indexer, settings).cached_extraction(db.version(imported["version_id"]))
    assert hashed and hashed[-1]["pdf"]["tesseract_cmd"] == expected


def queued_import(storage, name="queued.pdf", text="CCU-21 : tension nominale 72 V."):
    """Original importé et son travail en file, sans indexation ; extraction de fixture correspondante."""
    import hashlib

    settings, db, _, _ = storage
    payload = b"%PDF-1.7\n" + text.encode()
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original("folder/" + name, digest, blob)
    extraction = {"sha256": digest, "fingerprint": "fixture-native-v1", "page_count": 1, "status": "ready",
                  "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "type": "text", "text": text, "raw_text": text, "bbox": [10, 10, 100, 30], "precision": "block"}]}]}
    return imported, extraction


class FlakyGovernor:
    """Double explicite du gouverneur : la première admission lève une erreur (ex. verrou d'hôte illisible), puis admet."""
    def __init__(self):
        self.calls = 0
    def should_checkpoint(self):
        return False
    def allow_ingestion(self):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("verrou d'hôte illisible (simulé)")
        return True
    def resume_ingestion(self):
        pass
    @asynccontextmanager
    async def ingestion(self):
        yield


@pytest.mark.parametrize("failure", ["queue", "governor"])
def test_api_ingestion_loop_survives_queue_and_governor_errors(storage, monkeypatch, caplog, failure):
    """C4 : une erreur de lecture de la file ou du gouverneur est journalisée et la boucle reprend après une attente bornée."""
    import sqlite3

    settings, db, _, indexer = storage
    imported, extraction = queued_import(storage)
    monkeypatch.setattr(JobSupervisor, "retry_base_seconds", 0.01, raising=False)
    governor = FlakyGovernor() if failure == "governor" else None
    if failure == "queue":
        original_one, failures = db.one, [2]
        def flaky_one(sql, parameters=()):
            if sql.startswith("SELECT * FROM jobs WHERE state='queued'") and failures[0]:
                failures[0] -= 1
                raise sqlite3.OperationalError("database is locked")
            return original_one(sql, parameters)
        monkeypatch.setattr(db, "one", flaky_one)
    async def runner(request):
        return extraction
    async def scenario():
        supervisor = JobSupervisor(db, indexer, settings, governor, runner)
        supervisor.start()
        # Échéance large : sous charge (suite complète, extraction réelle en cours), 4 s ne suffisaient pas toujours.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"] == "ready":
                break
            await asyncio.sleep(0.02)
        alive = not supervisor._task.done()
        await supervisor.close()
        return alive
    with caplog.at_level("ERROR", logger="rag.jobs"):
        alive = asyncio.run(scenario())
    assert alive, "la boucle d'ingestion s'est arrêtée"
    assert db.one("SELECT state FROM jobs WHERE id=?", (imported["job_id"],))["state"] == "ready"
    assert "Sélection du prochain traitement impossible" in caplog.text and "nouvel essai" in caplog.text


def test_api_ingestion_retry_delay_is_bounded_and_never_a_tight_loop():
    from services.api.background import retry_delay

    delays = [retry_delay(failures, JobSupervisor.retry_base_seconds, JobSupervisor.retry_max_seconds) for failures in range(1, 12)]
    assert delays[0] == 0.5 and delays == sorted(delays) and max(delays) == 30.0


def test_api_repeated_loop_failure_logs_its_traceback_once_until_the_error_changes(caplog):
    import logging

    from services.api.background import FailureLog

    failures = FailureLog(logging.getLogger("rag.test"), 0.5, 30.0)
    with caplog.at_level("ERROR", logger="rag.test"):
        delays = [failures.failure("Lecture impossible", error) for error in
                  (OSError("disque plein"), OSError("disque plein"), RuntimeError("autre cause"))]
        failures.success()
        delays.append(failures.failure("Lecture impossible", OSError("disque plein")))
    assert delays == [0.5, 1.0, 2.0, 0.5]
    assert [record.exc_info is not None for record in caplog.records] == [True, False, True, True]
    assert "échec consécutif n° 2" in caplog.records[1].getMessage()


def test_api_reconciler_loop_survives_a_failed_pass(storage, monkeypatch, caplog):
    """C4 : une passe de nettoyage en erreur (SQLite verrouillé) n'arrête pas le nettoyage vectoriel."""
    import sqlite3

    from services.api.reconcile import Reconciler

    imported, _ = import_fixture(storage)
    settings, db, vectors, _ = storage
    generation = db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"]
    db.execute("INSERT INTO vector_cleanup VALUES(?,?,?,?,?,?)", (generation, "superseded", "pending", None, now(), now()))
    monkeypatch.setattr(Reconciler, "interval_seconds", 0.01, raising=False)
    reconciler = Reconciler(db, vectors)
    original, failures = reconciler.pinned, [1]
    def flaky_pinned():
        if failures[0]:
            failures[0] -= 1
            raise sqlite3.OperationalError("database is locked")
        return original()
    reconciler.pinned = flaky_pinned
    async def scenario():
        reconciler.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if db.one("SELECT state FROM vector_cleanup WHERE generation_id=?", (generation,))["state"] != "pending":
                break
            await asyncio.sleep(0.02)
        alive = not reconciler._task.done()
        await reconciler.close()
        return alive
    with caplog.at_level("ERROR", logger="rag.reconcile"):
        alive = asyncio.run(scenario())
    assert alive, "la boucle de nettoyage s'est arrêtée"
    # Génération encore active : conservée, et non supprimée, une fois la passe reprise.
    assert db.one("SELECT state FROM vector_cleanup WHERE generation_id=?", (generation,))["state"] == "retained"
    assert "Passe de nettoyage vectoriel en erreur" in caplog.text


@pytest.mark.parametrize("owner", ["jobs", "reconciler"])
def test_api_unexpected_end_of_a_background_loop_is_logged_and_does_not_break_shutdown(storage, caplog, owner):
    """C4 : une boucle de fond qui s'arrête sans demande laisse une trace, et la fermeture de l'API se poursuit."""
    from services.api.reconcile import Reconciler

    settings, db, vectors, indexer = storage
    loop_owner = JobSupervisor(db, indexer, settings) if owner == "jobs" else Reconciler(db, vectors)
    async def broken_loop():
        raise RuntimeError("défaut simulé hors de la reprise de la boucle")
    loop_owner.loop = broken_loop
    async def scenario():
        loop_owner.start()
        await asyncio.sleep(0.05)
        await loop_owner.close()
    with caplog.at_level("ERROR"):
        asyncio.run(scenario())
    assert "arrêtée par une erreur inattendue" in caplog.text and "défaut simulé" in caplog.text


WORKER_DOUBLE = r'''
import json, sys, time
from pathlib import Path
directory, result, payload, mode, seconds = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], float(sys.argv[5])
deadline = time.monotonic() + seconds
while time.monotonic() < deadline:
    if mode == "trace":
        with (directory / "worker-lifecycle.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": "page_load"}) + "\n")
    time.sleep(0.2)
result.write_text(json.dumps({"ok": True, "result": json.loads(payload)}), encoding="utf-8")
'''


def run_with_worker_double(storage, monkeypatch, mode, seconds, no_progress, window):
    """Lance un vrai sous-processus, double explicite du worker : il écrit (ou non) sa trace de cycle de vie, sans fenêtre durable."""
    import sys

    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    settings.profile["resources"] = {"scheduling": {"watchdog_no_progress_seconds_initial": no_progress, "watchdog_window_seconds_initial": window}}
    real_exec = asyncio.create_subprocess_exec
    async def launch(*args, **kwargs):
        from pathlib import Path
        result = Path(args[args.index("--result") + 1])
        return await real_exec(sys.executable, "-c", WORKER_DOUBLE, str(result.parent), str(result), json.dumps(extraction), mode, str(seconds), **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(JobSupervisor, "cached_extraction", lambda self, version: None)
    job_id = new_job(db, imported)
    supervisor = JobSupervisor(db, indexer, settings)
    asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    return db, job_id


def test_api_watchdog_does_not_kill_a_worker_that_progresses_within_its_window(storage, monkeypatch):
    """C5 : une fenêtre plus longue que le délai sans progrès n'est pas coupée tant que le worker progresse."""
    db, job_id = run_with_worker_double(storage, monkeypatch, "trace", 2.5, no_progress=1, window=10)
    assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "ready"


def test_api_watchdog_enforces_the_window_deadline_even_while_the_worker_progresses(storage, monkeypatch):
    """C5 : la durée maximale d'une fenêtre s'applique à un worker actif, avec son propre motif."""
    with pytest.raises(ApiError) as stopped:
        run_with_worker_double(storage, monkeypatch, "trace", 8, no_progress=1, window=2)
    assert stopped.value.code == "interrupted" and "durée maximale" in stopped.value.message
    db = storage[1]
    checkpoint = json.loads(db.one("SELECT checkpoint_json FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 1")["checkpoint_json"])
    assert checkpoint["reason"] == "watchdog_window_deadline" and checkpoint["window_limit_seconds"] == 2


def test_api_watchdog_stops_an_idle_worker_after_the_no_progress_delay(storage, monkeypatch):
    with pytest.raises(ApiError) as stopped:
        run_with_worker_double(storage, monkeypatch, "idle", 8, no_progress=1, window=10)
    assert stopped.value.code == "interrupted" and "sans progrès" in stopped.value.message
    checkpoint = json.loads(storage[1].one("SELECT checkpoint_json FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 1")["checkpoint_json"])
    assert checkpoint["reason"] == "watchdog_no_progress" and checkpoint["seconds_since_progress"] > 1


def test_api_watchdog_counts_cpu_work_and_durable_windows_as_progress(tmp_path):
    """Horloge et temps CPU contrôlés : calcul du worker ou de Tesseract = progrès ; activité résiduelle = inactivité."""
    from services.api.jobs import WorkerWatchdog

    clock, cpu = [0.0], [0.0]
    watchdog = WorkerWatchdog(tmp_path, 0, no_progress_seconds=300, window_seconds=900, clock=lambda: clock[0], cpu_seconds=lambda: cpu[0])
    assert watchdog.observe() is None
    # Calcul continu sur un cœur pendant 600 s, sans fichier : pas d'arrêt avant la durée maximale de fenêtre.
    for _ in range(120):
        clock[0] += 5
        cpu[0] += 5
        assert watchdog.observe() is None
    # Fenêtre durable écrite : la durée de fenêtre repart.
    (tmp_path / "window-000000-000003.json").write_text("{}", encoding="utf-8")
    clock[0] += 5
    assert watchdog.observe() is None and watchdog.durable_windows() == ["window-000000-000003.json"]
    # Activité résiduelle (moins de 10 % d'un cœur) : inactivité au-delà de 300 s.
    for _ in range(61):
        clock[0] += 5
        cpu[0] += 0.1
        reason = watchdog.observe()
    assert reason == "watchdog_no_progress"
    # Calcul soutenu mais aucune fenêtre durable depuis plus de 900 s : durée maximale dépassée.
    for _ in range(130):
        clock[0] += 5
        cpu[0] += 5
        reason = watchdog.observe()
    assert reason == "watchdog_window_deadline"


def test_api_extraction_progress_counts_the_pages_covered_by_durable_windows(tmp_path):
    """Ronde 4 : progression de l'extraction = pages couvertes par les fenêtres durables / pages du préflight, dans la plage de l'étape."""
    from services.api.indexing import INDEXING_PROGRESS_START
    from services.api.jobs import EXTRACTION_PROGRESS_START, ExtractionProgress, extraction_progress

    assert (EXTRACTION_PROGRESS_START, INDEXING_PROGRESS_START) == (0.05, 0.65)
    assert extraction_progress([], 10) == 0.05
    assert extraction_progress(["window-000000-000003.json"], 10) == 0.29
    # Pages comptées une fois (fenêtres qui se recouvrent), bornées au document ; noms étrangers ignorés.
    assert extraction_progress(["window-000000-000003.json", "window-000002-000005.json", "window-000008-000099.json",
                                ".window-000006-000007.json.tmp", "window-x-y.json"], 10) == 0.53
    assert extraction_progress(["window-000000-000003.json", "window-000004-000007.json", "window-000008-000009.json"], 10) == 0.65
    tracker = ExtractionProgress(tmp_path)
    # Préflight absent ou illisible : aucune progression calculée, les fenêtres seront relues au passage suivant.
    assert tracker.update(("window-000000-000003.json",)) is None
    (tmp_path / "preflight.json").write_text("{\"page_count\": 0}", encoding="utf-8")
    assert tracker.update(("window-000000-000003.json",)) is None
    (tmp_path / "preflight.json").write_text(json.dumps({"page_count": 10, "pages": [{}] * 10}), encoding="utf-8")
    assert tracker.update(("window-000000-000003.json",)) == 0.29
    # Mêmes fenêtres : rien à écrire.
    assert tracker.update(("window-000000-000003.json",)) is None
    assert tracker.update(("window-000000-000003.json", "window-000004-000007.json")) == 0.53
    # Reprise : le préflight de l'essai précédent, présent avant le lancement, n'est pas ouvert ; le worker le réécrit
    # (remplacement atomique) au début de chaque extraction, et sous Windows ce remplacement échoue sur un fichier ouvert
    # par un autre processus. Il n'est lu qu'une fois réécrit par ce worker.
    resumed = ExtractionProgress(tmp_path)
    assert resumed.update(("window-000000-000003.json", "window-000004-000007.json")) is None
    rewritten = tmp_path / ".preflight.json.tmp"
    rewritten.write_text(json.dumps({"page_count": 10, "pages": [{}] * 10}), encoding="utf-8")
    import os
    os.replace(rewritten, tmp_path / "preflight.json")
    assert resumed.update(("window-000000-000003.json", "window-000004-000007.json")) == 0.53


PROGRESS_WORKER_DOUBLE = r'''
import json, os, sys, time
from pathlib import Path
directory, result, payload, page_count, size = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5])

def atomic(path, data):
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temporary, path)

atomic(directory / "preflight.json", {"page_count": page_count, "pages": [{"page_index": index} for index in range(page_count)]})
for number, first in enumerate(range(0, page_count, size), 1):
    last = min(page_count - 1, first + size - 1)
    atomic(directory / f"window-{first:06d}-{last:06d}.json", {"payload": {"page_start": first, "page_end": last}})
    # Attend que l'API ait publié la progression de cette fenêtre (accusé écrit par le test), puis laisse passer
    # plusieurs relevés de la boucle de surveillance (0,5 s) sans fenêtre nouvelle.
    deadline = time.monotonic() + 30
    while not (directory / f"progress-ack-{number}").exists():
        if time.monotonic() > deadline:
            sys.exit(7)
        time.sleep(0.05)
    time.sleep(1.2)
result.write_text(json.dumps({"ok": True, "result": json.loads(payload)}), encoding="utf-8")
'''


def test_api_job_progress_follows_durable_windows_during_extraction_without_a_write_per_poll(storage, monkeypatch):
    """Ronde 4 (J10) : `progress` restait à 0,05 pendant toute l'extraction.

    Vrai sous-processus, double explicite du worker : préflight de 10 pages, puis trois fenêtres durables de 4 pages.
    La boucle qui surveille le worker publie la progression à chaque fenêtre nouvelle (0,29 ; 0,53 ; 0,65), dans la
    plage de l'étape d'extraction, et ne l'écrit pas aux relevés sans fenêtre nouvelle.
    """
    from pathlib import Path

    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    job_id = new_job(db, imported)
    directory = settings.data_dir / "extractions" / imported["version_id"] / job_id
    real_exec = asyncio.create_subprocess_exec
    async def launch(*args, **kwargs):
        result = Path(args[args.index("--result") + 1])
        return await real_exec(sys.executable, "-c", PROGRESS_WORKER_DOUBLE, str(result.parent), str(result), json.dumps(extraction), "10", "4", **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(JobSupervisor, "cached_extraction", lambda self, version: None)
    published, progress_writes = [], []
    real_execute = db.execute
    def observed_execute(sql, parameters=()):
        real_execute(sql, parameters)
        row = db.one("SELECT progress,stage FROM jobs WHERE id=?", (job_id,))
        if row["stage"] != "extracting":
            return
        if "progress" in sql:
            progress_writes.append(row["progress"])
        if not published or row["progress"] != published[-1]:
            published.append(row["progress"])
            if len(published) > 1:
                (directory / f"progress-ack-{len(published) - 1}").touch()
    monkeypatch.setattr(db, "execute", observed_execute)
    supervisor = JobSupervisor(db, indexer, settings)
    asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    assert published == [0.05, 0.29, 0.53, 0.65]
    # Une écriture au lancement, puis une par fenêtre nouvelle : aucune aux relevés de 0,5 s sans fenêtre nouvelle.
    assert progress_writes == published
    assert db.one("SELECT state,progress FROM jobs WHERE id=?", (job_id,)) == {"state": "ready", "progress": 1}


class FakeCpuTree:
    """Double explicite de psutil.Process : arbre de processus et temps CPU scriptés (pid -> création, temps, enfants)."""

    def __init__(self):
        self.table = {}

    def process_class(self):
        import contextlib

        import psutil
        table = self.table

        class Process:
            def __init__(self, pid):
                if pid not in table:
                    raise psutil.NoSuchProcess(pid)
                self.pid = pid

            def children(self, recursive=False):
                return [Process(child) for child in table[self.pid]["children"] if child in table]

            def oneshot(self):
                return contextlib.nullcontext()

            def cpu_times(self):
                if self.pid not in table:
                    raise psutil.NoSuchProcess(self.pid)
                return table[self.pid]["times"]

            def create_time(self):
                return table[self.pid]["created"]

        return Process


def cpu_times(user, system=0.0, children_user=0.0, children_system=0.0):
    from types import SimpleNamespace
    return SimpleNamespace(user=user, system=system, children_user=children_user, children_system=children_system)


def test_api_worker_cpu_counts_a_waited_child_once_when_the_kernel_reports_it_to_the_parent(monkeypatch):
    """Revue A1 (C5), Linux : un Tesseract terminé et attendu passe dans children_* du worker ; il n'est plus compté deux fois."""
    import psutil

    from services.api.jobs import process_tree_cpu_seconds

    tree = FakeCpuTree()
    monkeypatch.setattr(psutil, "Process", tree.process_class())
    observed = {}
    tree.table.update({10: {"created": 1.0, "times": cpu_times(1.0), "children": [20]},
                       20: {"created": 2.0, "times": cpu_times(2.0, 0.5), "children": []}})
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=True) == pytest.approx(3.5)
    # Tesseract terminé puis attendu : 3,0 s de CPU au total, désormais dans children_* du worker.
    del tree.table[20]
    tree.table[10] = {"created": 1.0, "times": cpu_times(1.0, children_user=2.4, children_system=0.6), "children": []}
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=True) == pytest.approx(4.0)


def test_api_worker_cpu_keeps_a_finished_child_where_the_kernel_does_not_report_it(monkeypatch):
    """Windows (children_* toujours nuls) : la dernière valeur lue d'un enfant terminé reste comptée, sans changement."""
    import psutil

    from services.api.jobs import process_tree_cpu_seconds

    tree = FakeCpuTree()
    monkeypatch.setattr(psutil, "Process", tree.process_class())
    observed = {}
    tree.table.update({10: {"created": 1.0, "times": cpu_times(1.0), "children": [20]},
                       20: {"created": 2.0, "times": cpu_times(2.0, 0.5), "children": []}})
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=False) == pytest.approx(3.5)
    del tree.table[20]
    tree.table[10]["children"] = []
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=False) == pytest.approx(3.5)
    # Nouvel enfant réutilisant le même pid : clé distincte par date de création, contribution ajoutée.
    tree.table[20] = {"created": 9.0, "times": cpu_times(0.25), "children": []}
    tree.table[10]["children"] = [20]
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=False) == pytest.approx(3.75)
    del tree.table[10]
    assert process_tree_cpu_seconds(10, observed, waited_children_accounted=False) is None


PARENT_DOUBLE = r'''
import subprocess, sys, time
from pathlib import Path
directory = Path(sys.argv[1])
child = subprocess.Popen([sys.executable, "-c", (
    "import sys, time\nfrom pathlib import Path\nd = Path(sys.argv[1])\nend = time.process_time() + 0.6\n"
    "while time.process_time() < end:\n    pass\n(d / 'burned').write_text('1')\n"
    "while not (d / 'exit').exists():\n    time.sleep(0.02)\n"), str(directory)])
child.wait()
(directory / "waited").write_text("1")
time.sleep(60)
'''


@pytest.mark.skipif(sys.platform == "win32", reason="comptabilité noyau des enfants attendus (children_*) propre à POSIX")
def test_api_worker_cpu_of_a_real_waited_child_is_not_counted_twice(tmp_path):
    """Revue A1 (C5) sur le noyau réel : après l'attente d'un enfant qui a calculé 0,6 s, la mesure reste celle du noyau."""
    import subprocess
    import time

    import psutil

    from services.api.jobs import process_tree_cpu_seconds

    def wait_for(name):
        deadline = time.monotonic() + 30
        while not (tmp_path / name).exists():
            assert time.monotonic() < deadline, f"{name} absent"
            time.sleep(0.02)

    parent = subprocess.Popen([sys.executable, "-c", PARENT_DOUBLE, str(tmp_path)])
    try:
        observed = {}
        wait_for("burned")
        while_running = process_tree_cpu_seconds(parent.pid, observed)
        assert while_running >= 0.5
        (tmp_path / "exit").write_text("1")
        wait_for("waited")
        after_wait = process_tree_cpu_seconds(parent.pid, observed)
        times = psutil.Process(parent.pid).cpu_times()
        kernel = times.user + times.system + times.children_user + times.children_system
        assert times.children_user + times.children_system >= 0.5
        assert after_wait == pytest.approx(kernel, abs=0.05) and after_wait >= while_running - 0.05
    finally:
        parent.kill()
        parent.wait()
