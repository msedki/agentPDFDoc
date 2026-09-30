import asyncio
from contextlib import asynccontextmanager
import json
import pytest

from services.api.db import now, uid
from services.api.jobs import JobSupervisor
from services.api.errors import ApiError

from test_api_storage import import_fixture, storage


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
