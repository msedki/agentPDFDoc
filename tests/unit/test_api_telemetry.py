"""Process counters against isolated SQLite and explicitly substituted engines."""
import asyncio
import json
from types import SimpleNamespace

import numpy as np
import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage

from services.api.db import now, uid
from services.api.embedding import EmbeddingService
from services.api.jobs import JobSupervisor
from services.api.settings import Settings


def test_api_inference_counts_actual_session_runs_not_tokenizer_counts(tmp_path):
    embedding = EmbeddingService(Settings(tmp_path, {"embedding": {"batch_size": 2}}))
    embedding._tokenizer = SimpleNamespace(encode_batch=lambda texts: [SimpleNamespace(ids=[1, 2]) for _ in texts], token_to_id=lambda name: 0)
    class Session:
        fail = False
        def get_inputs(self):
            return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]
        def run(self, names, feeds):
            if self.fail:
                raise RuntimeError("Controlled engine failure")
            output = np.zeros((len(feeds["input_ids"]), 384), dtype=np.float32)
            output[:, 0] = 1
            return [output]
    session = Session()
    embedding._session = session
    assert embedding.embed([]) == []
    assert embedding.lifecycle()["inference"]["run_calls"] == 0
    assert len(embedding.embed(["one", "two", "three"])) == 3
    observed = embedding.lifecycle()["inference"]
    assert observed["run_calls"] == observed["run_completed"] == 2
    assert observed["inputs_submitted"] == observed["inputs_completed"] == observed["passage_inputs_completed"] == 3
    session.fail = True
    with pytest.raises(RuntimeError):
        embedding.embed(["query"], passage=False)
    observed = embedding.lifecycle()["inference"]
    assert observed["run_calls"] == 3 and observed["run_completed"] == 2 and observed["run_failed"] == 1
    assert observed["inputs_submitted"] == 4 and observed["inputs_completed"] == 3 and observed["query_inputs_completed"] == 0


def test_api_cache_telemetry_counts_only_valid_vectors_used(storage):
    _, _ = import_fixture(storage)
    _, db, _, indexer = storage
    chunk = db.one("SELECT text,text_hash AS hash FROM chunks")
    initial = indexer.diagnostics()
    assert initial["cache_misses"] == initial["embedding_texts_submitted"] == 1
    indexer.cached_embeddings([chunk])
    cached = indexer.diagnostics()
    assert cached["cache_hits"] == 1 and cached["embedding_requests"] == initial["embedding_requests"]
    db.execute("UPDATE embedding_cache SET vector=?", (b"invalid",))
    indexer.cached_embeddings([chunk])
    corrected = indexer.diagnostics()
    assert corrected["cache_hits"] == 1 and corrected["cache_misses"] == 2
    assert corrected["embedding_requests"] == corrected["embedding_requests_completed"] == 2
    assert corrected["last_request"]["misses"] == 1


def test_api_verified_extraction_reuse_has_no_worker_launch(storage, monkeypatch):
    imported, extraction = import_fixture(storage)
    settings, db, _, indexer = storage
    revision = db.one("SELECT * FROM extraction_revisions")
    extraction = {**extraction, "pipeline_fingerprint": "fixture-native-v1", "extraction_revision_id": revision["id"]}
    path = settings.data_dir / "extractions" / imported["version_id"] / "extraction.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
    db.execute("UPDATE extraction_revisions SET path=? WHERE id=?", (str(path), revision["id"]))
    monkeypatch.setattr("services.ingestion.extraction_fingerprint", lambda config: "fixture-native-v1")
    async def forbidden(*args, **kwargs):
        raise AssertionError("A verified extraction must not launch an ingestion worker")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    supervisor = JobSupervisor(db, indexer, settings)
    before = indexer.diagnostics()
    asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (job_id,))))
    observed = supervisor.diagnostics()
    assert observed["cache_checks"] == observed["cache_hits"] == observed["extraction_reuses"] == 1
    assert observed["cache_misses"] == observed["native_worker_launches"] == observed["injected_runner_calls"] == 0
    assert observed["last_extraction"]["extraction_revision_id"] == revision["id"]
    assert indexer.diagnostics()["embedding_requests"] == before["embedding_requests"]
    assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "ready"


@pytest.mark.parametrize("launch_succeeds", [False, True])
def test_api_worker_telemetry_counts_successful_launch_even_if_worker_fails(storage, monkeypatch, launch_succeeds):
    imported, _ = import_fixture(storage)
    settings, db, _, indexer = storage
    monkeypatch.setattr("services.ingestion.extraction_fingerprint", lambda config: "new-pipeline-without-cache")
    async def launch(*args, **kwargs):
        if not launch_succeeds:
            raise OSError("Controlled launch failure")
        from pathlib import Path
        result_path = Path(args[args.index("--result") + 1])
        result_path.write_text(json.dumps({"ok": False, "error": {"code": "controlled_worker_failure", "message": "Controlled worker failure"}}), encoding="utf-8")
        return SimpleNamespace(pid=123, returncode=2)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    supervisor = JobSupervisor(db, indexer, settings)
    from services.api.errors import ApiError
    with pytest.raises(ApiError if launch_succeeds else OSError):
        asyncio.run(supervisor.run(db.one("SELECT * FROM jobs WHERE id=?", (imported["job_id"],))))
    observed = supervisor.diagnostics()
    assert observed["cache_checks"] == observed["cache_misses"] == 1
    assert observed["native_worker_launches"] == int(launch_succeeds)
    assert observed["extraction_reuses"] == observed["injected_runner_calls"] == 0


def test_api_blank_pdf_publishes_original_with_warning_and_without_chunks(storage):
    imported, extraction = import_fixture(storage, text="", pages=[{"page_index": 0, "width": 595, "height": 842, "extraction_state": "blank", "blocks": []}])
    settings, db, vectors, indexer = storage
    generation = db.one("SELECT * FROM index_generations")
    assert generation["state"] == "ready" and generation["actual_chunks"] == generation["expected_chunks"] == 0
    assert json.loads(generation["warnings_json"])[0]["code"] == "no_exploitable_text"
    assert "warnings" not in extraction
    assert db.one("SELECT count(*) AS n FROM chunks")["n"] == 0 and vectors.points == {}
    assert indexer.diagnostics()["embedding_requests"] == 0
    version = db.version(imported["version_id"])
    from pathlib import Path
    assert Path(version["blob_path"]).is_relative_to(settings.data_dir) and Path(version["blob_path"]).is_file()
