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
