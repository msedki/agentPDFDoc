import asyncio
import json
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
        for _ in range(100):
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
