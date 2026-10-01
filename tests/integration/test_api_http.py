"""HTTP contracts against real isolated SQLite, fake models explicitly injected."""
import asyncio
import hashlib
import json
from contextlib import asynccontextmanager, contextmanager

import pytest
from fastapi.testclient import TestClient

from services.api.db import now, uid
from services.api.main import create_app
from services.api.settings import Settings


class FakeEmbedding:
    def count(self, text, passage=True):
        return len(text) // 4 + 3
    def embed(self, texts, passage=True):
        return [[1.0] + [0.0] * 383 for text in texts]

class FakeVectors:
    def __init__(self):
        self.points = {}
    async def ensure_collection(self):
        pass
    async def upsert(self, points):
        self.points.update({point["id"]: point for point in points})
    async def verify(self, expected):
        assert len(expected) <= len(self.points)
    async def query(self, vector, snapshot, limit=24):
        return [key for key, point in self.points.items() if point["payload"]["generation_id"] in snapshot.generations][:limit]
    async def count_generation(self, generation_id):
        return sum(point["payload"]["generation_id"] == generation_id for point in self.points.values())
    async def close(self):
        pass

class FakeTokenizer:
    def count(self, text):
        return len(text) // 4 + 1
    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)

class FakeOllama:
    calls = 0
    async def stream(self, messages, cancelled, output_tokens=None):
        self.calls += 1
        yield {"type": "delta", "text": "La tension est 72 V [S001]."}
        yield {"type": "done", "finish_reason": "stop", "metrics": {"eval_count": 12}}
    async def close(self):
        pass

class FakeGovernor:
    def begin_interactive(self):
        pass
    def finish_interactive(self):
        pass
    def snapshot(self):
        return {"heavy_owner": None}
    @asynccontextmanager
    async def generation(self, on_wait=None):
        yield


CONTROL = "test-only-nonce"


@pytest.fixture(autouse=True)
def control_token(monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)


@contextmanager
def browser_client(app):
    """Client muni d'une session ouverte comme par le navigateur : lien à usage unique, cookie, jeton CSRF."""
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        link = client.post("/api/v1/admin/session-links", headers={"X-RAG-Control-Token": CONTROL}).json()["path"]
        opened = client.get(link, follow_redirects=False)
        assert opened.status_code == 303 and opened.headers["location"] == "/workspace/"
        client.headers["X-CSRF-Token"] = client.cookies["rag_csrf"]
        yield client

def test_api_blank_pdf_exposes_warning_and_preserves_original_http(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        payload = b"%PDF-1.7\ncontrolled blank fixture"
        imported = client.post("/api/v1/documents/import", files={"files": ("blank.pdf", payload, "application/pdf")}).json()
        extraction = {"fingerprint": "blank-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready", "pages": [
            {"page_index": 0, "width": 595, "height": 842, "extraction_state": "blank", "blocks": []}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        page = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()
        assert page["blocks"] == [] and page["page"]["extraction_state"] == "blank"
        assert page["warnings"][0]["code"] == "no_exploitable_text"
        job = next(row for row in client.get("/api/v1/jobs").json()["jobs"] if row["id"] == imported["job_id"])
        assert job["state"] == "ready" and job["published"] is True and job["warnings"] == page["warnings"]
        original = client.get(f"/api/v1/versions/{imported['version_id']}/file")
        assert original.status_code == 200 and original.content == payload
        assert original.headers["etag"] == '"' + hashlib.sha256(payload).hexdigest() + '"'
        diagnostic = client.get("/api/v1/diagnostics").json()
        assert diagnostic["indexing_cache"]["embedding_requests"] == 0
        assert diagnostic["ingestion_cache"]["native_worker_launches"] == 0
        assert diagnostic["embedding_session"]["status"] == "explicit_test_substitute"


def publish_two_extraction_revisions(client, app):
    payload = b"%PDF-1.7\nsame immutable original, distinct controlled parser revisions"
    imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", payload, "application/pdf")}).json()
    extraction = {"fingerprint": "parser-old", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready", "pages": [
        {"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": "Ancien relevé 72 V 😀", "bbox": [10, 10, 100, 30], "section_id": "s0"}]}],
        "sections": [{"id": "s0", "title": "Ancien sommaire", "page_index": 0, "block_ids": ["b0"]}]}
    client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
    old = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()
    job_id = uid()
    app.state.db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    second = {**extraction, "fingerprint": "parser-new", "pages": [{"page_index": 0, "width": 595, "height": 842,
        "blocks": [{"id": "b0", "raw_text": "Nouvelle extraction 110 V", "bbox": [30, 40, 200, 60], "section_id": "s0"}]}],
        "sections": [{"id": "s0", "title": "Nouveau sommaire", "page_index": 0, "block_ids": ["b0"]}]}
    client.portal.call(app.state.indexer.index, job_id, second)
    latest = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()
    assert old["generation_id"] != latest["generation_id"] and old["extraction_revision_id"] != latest["extraction_revision_id"]
    assert old["blocks"][0]["source_text_hash"] != latest["blocks"][0]["source_text_hash"]
    return imported, old, latest


def test_api_diagnostics_compares_active_generation_points_with_sqlite_chunks(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        assert client.get("/api/v1/diagnostics").json()["index_consistency"] == {"status": "consistent", "active_generations": 0, "sqlite_chunks": 0, "mismatches": []}
        _, _, latest = publish_two_extraction_revisions(client, app)
        consistency = client.get("/api/v1/diagnostics").json()["index_consistency"]
        assert consistency["status"] == "consistent" and consistency["active_generations"] == 1 and consistency["sqlite_chunks"] > 0
        # Un point perdu de la génération active est signalé, avec les deux comptes.
        lost = next(key for key, point in app.state.vectors.points.items() if point["payload"]["generation_id"] == latest["generation_id"])
        del app.state.vectors.points[lost]
        consistency = client.get("/api/v1/diagnostics").json()["index_consistency"]
        assert consistency["status"] == "inconsistent"
        [mismatch] = consistency["mismatches"]
        assert mismatch["generation_id"] == latest["generation_id"] and mismatch["qdrant_points"] == mismatch["sqlite_chunks"] - 1


@pytest.mark.parametrize("route", ["blocks", "outline", "selection"])
def test_api_historical_extraction_revision_survives_same_version_reindex(tmp_path, route):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        imported, old, latest = publish_two_extraction_revisions(client, app)
        from services.api.reconcile import Reconciler
        async def delete_generation(generation_id):
            app.state.vectors.points = {key: point for key, point in app.state.vectors.points.items() if point["payload"]["generation_id"] != generation_id}
        app.state.vectors.delete_generation = delete_generation
        cleaned = client.portal.call(Reconciler(app.state.db, app.state.vectors).run_once)
        assert cleaned["completed"] == [old["generation_id"]]
        assert app.state.db.one("SELECT published_at FROM index_generations WHERE id=?", (old["generation_id"],))["published_at"] is not None
        assert app.state.db.one("SELECT source_text_hash FROM blocks WHERE generation_id=?", (old["generation_id"],))["source_text_hash"] == old["blocks"][0]["source_text_hash"]
        revision = old["extraction_revision_id"]
        if route == "blocks":
            response = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks", params={"extraction_revision_id": revision})
            assert response.status_code == 200, response.text
            assert response.json() == old
        elif route == "outline":
            response = client.get(f"/api/v1/versions/{imported['version_id']}/outline", params={"extraction_revision_id": revision})
            assert response.status_code == 200, response.text
            assert response.json()["sections"][0]["title"] == "Ancien sommaire"
            assert response.json()["extraction_revision_id"] == revision and response.json()["generation_id"] == old["generation_id"]
        else:
            block = old["blocks"][0]
            span = {"extractionRevisionId": revision, "blockId": block["id"], "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": len(block["raw_text"])}
            response = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": {"kind": "selection", "versionId": imported["version_id"], "spans": [span]}})
            assert response.status_code == 200, response.text
            result = response.json()["results"][0]
            assert result["text"] == block["raw_text"] and result["generation_id"] == old["generation_id"]
            assert result["extraction_revision_id"] == revision and result["blocks"][0]["bbox"] == block["bbox"]
        ordinary = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()
        assert ordinary == latest


def test_api_pinned_revision_never_falls_back_when_invalid_or_unpublished(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        imported, old, latest = publish_two_extraction_revisions(client, app)
        version = app.state.db.version(imported["version_id"])
        other = app.state.db.import_original("other.pdf", version["sha256"], version["blob_path"])
        staged_job = uid()
        app.state.db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (staged_job, imported["document_id"], imported["version_id"], now(), now()))
        staged_generation, _ = app.state.indexer.stage(staged_job, {"fingerprint": "unpublished-parser", "sha256": version["sha256"], "status": "ready", "page_count": 1,
            "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": "Unpublished text"}]}]})
        staged_revision = app.state.db.one("SELECT extraction_revision_id FROM index_generations WHERE id=?", (staged_generation,))["extraction_revision_id"]
        for version_id, revision in [(imported["version_id"], "unknown"), (other["version_id"], old["extraction_revision_id"]), (imported["version_id"], staged_revision)]:
            for endpoint in ["outline", "pages/0/blocks"]:
                response = client.get(f"/api/v1/versions/{version_id}/{endpoint}", params={"extraction_revision_id": revision})
                assert response.status_code == 404 and response.json()["code"] == "extraction_revision_not_found"
            block = old["blocks"][0]
            span = {"extractionRevisionId": revision, "blockId": block["id"], "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": len(block["raw_text"])}
            response = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": {"kind": "selection", "versionId": version_id, "spans": [span]}})
            assert response.status_code == 404 and response.json()["code"] == "extraction_revision_not_found"
        old_block, new_block = old["blocks"][0], latest["blocks"][0]
        spans = [{"extractionRevisionId": source["extraction_revision_id"], "blockId": source["id"], "blockTextSha256": source["source_text_hash"], "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": len(source["raw_text"])} for source in [old_block, new_block]]
        response = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": {"kind": "selection", "versionId": imported["version_id"], "spans": spans}})
        assert response.status_code == 400 and response.json()["code"] == "invalid_selection"


@pytest.mark.parametrize("scope_kind", ["documents", "pages", "selection"])
def test_api_search_returns_actual_document_and_page_metadata_without_citations(tmp_path, scope_kind):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        payload = b"%PDF-1.7\ncontrolled metadata fixture"
        imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", payload, "application/pdf")}, data={"relative_paths": '["engineering/manual.pdf"]'}).json()
        text = "CCU-21 tension 72 V"
        extraction = {"fingerprint": "metadata-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 2, "status": "ready", "pages": [
            {"page_index": 0, "label": "i", "width": 595, "height": 842, "blocks": [{"id": "cover", "raw_text": "Cover page"}]},
            {"page_index": 1, "label": "A-2", "width": 595, "height": 842, "blocks": [{"id": "b1", "raw_text": text, "bbox": [10, 20, 200, 40], "precision": "block"}]},
        ]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        page = client.get(f"/api/v1/versions/{imported['version_id']}/pages/1/blocks").json()
        block = page["blocks"][0]
        scope = {"kind": "documents", "documentIds": [imported["document_id"]]}
        if scope_kind == "pages":
            scope = {"kind": "pages", "versionId": imported["version_id"], "pageStart": 1, "pageEnd": 1}
        elif scope_kind == "selection":
            scope = {"kind": "selection", "versionId": imported["version_id"], "spans": [{"extractionRevisionId": block["extraction_revision_id"], "blockId": block["id"], "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": len(text)}]}
        response = client.post("/api/v1/search", json={"question": "Quelle tension CCU-21 ?", "scope": scope})
        assert response.status_code == 200, response.text
        result = response.json()
        for hit in [result["results"][0], result["top10"][0]]:
            assert hit["name"] == hit["document_name"] == "manual.pdf"
            assert hit["relative_path"] == "engineering/manual.pdf"
            assert hit["page_index"] == 1 and hit["page_number"] == 2 and hit["label"] == "A-2"
            assert hit["version_id"] == imported["version_id"] and hit["generation_id"] == page["generation_id"]
            assert hit["extraction_revision_id"] == block["extraction_revision_id"]
            assert not {"source_id", "query_id", "citation_url"}.intersection(hit)
            source_block = hit["blocks"][0]
            assert source_block["id"] == block["id"] and source_block["source_text_hash"] == block["source_text_hash"]
            assert source_block["bbox"] == block["bbox"] and source_block["precision"] == block["precision"]
            assert source_block["text"] == text and source_block["start_offset"] == 0 and source_block["end_offset"] == len(text)
        assert app.state.db.one("SELECT count(*) AS n FROM query_runs")["n"] == 0
        assert app.state.db.one("SELECT count(*) AS n FROM citations")["n"] == 0


@pytest.mark.parametrize("loaded,resident,available,expected_release", [(False, False, 5000, True), (False, False, 5888, False), (True, True, 2300, False), (False, True, 5000, False)])
def test_api_releases_e5_only_for_cold_insufficient_memory(tmp_path, loaded, resident, available, expected_release):
    class ControlledEmbedding(FakeEmbedding):
        released = 0
        tokenizers_released = 0
        def release_session(self):
            self.released += 1
            return {"state": "released", "next_reload_measurement": "pending"}
        def release_tokenizer(self):
            self.tokenizers_released += 1
            return {"state": "released", "next_reload_measurement": "pending"}
    class ControlledTokenizer(FakeTokenizer):
        released = 0
        def release_tokenizer(self):
            self.released += 1
            return {"state": "released", "next_reload_measurement": "pending"}
    class ControlledRuntime(FakeOllama):
        async def loaded_state(self):
            return {"loaded": loaded, "resident": resident, "additional_peak_mib": 512}
        async def unload(self):
            return {"state": "unloaded"}
    class ControlledGovernor(FakeGovernor):
        def snapshot(self):
            return {"available_mib": available, "heavy_owner": None}
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "resources": {"initial_llm_load_peak_estimate_mib": 4352, "host_available_min_mib": 1536}})
    embedding, governor, tokenizer = ControlledEmbedding(), ControlledGovernor(), ControlledTokenizer()
    app = create_app(settings=settings, embedding=embedding, vectors=FakeVectors(), tokenizer=tokenizer, ollama=ControlledRuntime(), governor=governor, start_jobs=False)
    with browser_client(app) as client:
        state = client.portal.call(governor.before_generation)
        assert state["loaded"] is loaded and bool(embedding.released) is expected_release
        assert ("embedding_release" in state) is expected_release
        assert bool(embedding.tokenizers_released) is expected_release and bool(tokenizer.released) is expected_release
        assert ("llm_tokenizer_release" in state) is expected_release
        assert governor.after_resource_violation == governor.before_ingestion


def test_api_admin_evaluation_runs_real_scope_and_context_without_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    class NoGeneration(FakeGovernor):
        @asynccontextmanager
        async def generation(self, on_wait=None):
            raise AssertionError("Diagnostic context must never acquire generation admission")
            yield
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    runtime = FakeOllama()
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=NoGeneration(), start_jobs=False)
    with browser_client(app) as client:
        pdf = b"%PDF-1.7\ncontrolled diagnostic fixture\n"
        imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", pdf, "application/pdf")}).json()
        extraction = {"fingerprint": "fixture-v1", "sha256": hashlib.sha256(pdf).hexdigest(), "page_count": 1, "status": "ready", "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": "CCU-21 72 V. CCU-22 110 V.", "bbox": [10,10,200,30], "precision": "block"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        body = {"question": "Quelle est sa tension ?", "prior_user_question": "Parle de CCU-21", "scope": {"kind": "documents", "documentIds": [imported["document_id"]]}}
        url = "/api/v1/admin/evaluation/context"
        assert client.post(url, json=body).status_code == 403
        headers = {"X-RAG-Control-Token": "test-only-nonce"}
        assert client.post(url, headers={**headers, "Origin": "https://evil.example"}, json=body).status_code == 403
        response = client.post(url, headers=headers, json=body)
        assert response.status_code == 200, response.text
        evaluated = response.json()
        assert evaluated["state"] == "context_ready" and evaluated["model_called"] is False and runtime.calls == 0
        assert evaluated["resolution"]["method"] == "unique_user_referent" and "CCU-21" in evaluated["effective_question"]
        assert evaluated["context_sources"][0]["version_id"] == imported["version_id"]
        assert evaluated["retrieval_top10"][0]["blocks"][0]["source_text_hash"]
        assert app.state.db.one("SELECT count(*) AS n FROM query_runs")["n"] == 0
        ambiguous = client.post(url, headers=headers, json={**body, "prior_user_question": "Compare CCU-21 et CCU-22"})
        assert ambiguous.json()["state"] == "needs_clarification" and runtime.calls == 0
        app.state.jobs._active = "controlled-active-job"
        assert client.post(url, headers=headers, json=body).status_code == 409
        app.state.jobs._active = None
        app.state.mutations_paused = True
        assert client.post(url, headers=headers, json=body).status_code == 503


def test_api_import_range_scope_sse_reconnect_and_citation(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    runtime = FakeOllama()
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        pdf = b"%PDF-1.7\ncontrolled fixture only\n"
        response = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", pdf, "application/pdf")}, data={"relative_paths": '["engineering/manual.pdf"]'})
        assert response.status_code == 202, response.text
        imported = response.json()
        extraction = {"fingerprint": "fixture-v1", "sha256": hashlib.sha256(pdf).hexdigest(), "page_count": 1, "status": "ready", "pages": [{"page_index": 0, "width": 595, "height": 842, "crop_box": [0,0,595,842], "media_box": [0,0,595,842], "rotation": 0, "blocks": [{"id": "b0", "text": "CCU-21 tension 72 V", "bbox": [10,10,200,30], "precision": "block"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        document = client.get("/api/v1/documents/" + imported["document_id"]).json()
        assert document["active_version_id"] == imported["version_id"]
        assert client.get("/api/v1/library/tree").json()["total_documents"] == 1
        file_url = f"/api/v1/versions/{imported['version_id']}/file"
        ranged = client.get(file_url, headers={"Range": "bytes=0-7"})
        assert ranged.status_code == 206 and ranged.content == pdf[:8]
        assert ranged.headers["etag"] == '"' + hashlib.sha256(pdf).hexdigest() + '"'
        cached = client.get(file_url, headers={"If-None-Match": ranged.headers["etag"]})
        assert cached.status_code == 304 and cached.content == b"" and cached.headers["etag"] == ranged.headers["etag"]
        block = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()["blocks"][0]
        assert block["raw_text"] == "CCU-21 tension 72 V" and block["source_text_hash"]
        query = client.post("/api/v1/queries", json={"question": "Quelle tension CCU-21 ?", "scope": {"kind": "documents", "documentIds": [imported["document_id"]]}}).json()
        events = client.get(query["events_url"]).text
        assert events.index("event: sources") < events.index("event: delta")
        assert "event: done" in events
        source = client.get(f"/api/v1/citations/{query['query_id']}/S001").json()
        assert source["version_id"] == imported["version_id"] and source["extraction_revision_id"]
        assert source["blocks"][0]["bbox"] == [10,10,200,30]
        last_id = app.state.db.one("SELECT last_event_id FROM query_runs WHERE id=?", (query["query_id"],))["last_event_id"]
        replay = client.get(query["events_url"] + f"?after={last_id-1}").text
        assert "event: done" in replay and runtime.calls == 1
        client.delete("/api/v1/documents/" + imported["document_id"])
        assert client.get(f"/api/v1/citations/{query['query_id']}/S001").status_code == 404
        assert client.get("/api/v1/library/tree").json()["total_documents"] == 0


def test_api_partial_job_metadata_and_explicit_publication(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        payload = b"%PDF-1.7\ncontrolled partial fixture"
        imported = client.post("/api/v1/documents/import", files={"files": ("partial.pdf", payload, "application/pdf")}).json()
        extraction = {"fingerprint": "partial-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 2, "status": "ready_partial", "coverage": {"total": 2, "processed": 1, "ocr": 0}, "warnings": [{"code": "fixture_missing_page"}], "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "text": "CCU-21 tension 72 V"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        pending = client.get("/api/v1/jobs").json()["jobs"][0]
        assert pending["state"] == "ready_partial" and pending["published"] is False and pending["active"] is False and pending["published_at"] is None
        assert pending["coverage"] == {"total": 2, "processed": 1, "ocr": 0} and pending["warnings"][0]["code"] == "fixture_missing_page"
        assert client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").status_code == 409
        published = client.post(f"/api/v1/jobs/{imported['job_id']}/publish-partial")
        assert published.status_code == 200 and published.json()["coverage"] == pending["coverage"]
        active = client.get("/api/v1/jobs").json()["jobs"][0]
        assert active["published"] is True and active["active"] is True and active["published_at"]
        document_job = client.get(f"/api/v1/documents/{imported['document_id']}").json()["jobs"][0]
        assert document_job["published"] is True and document_job["coverage"] == pending["coverage"]
        # La réponse porte l'avertissement d'extraction partielle avant toute génération, puis dans son état final.
        query = client.post("/api/v1/queries", json={"question": "Quelle tension CCU-21 ?", "scope": {"kind": "documents", "documentIds": [imported["document_id"]]}}).json()
        events = client.get(query["events_url"]).text
        assert events.index("partial_extraction") < events.index("event: done") and "event: error" not in events
        done = json.loads(app.state.db.one("SELECT warnings_json FROM query_runs WHERE id=?", (query["query_id"],))["warnings_json"])
        assert any(warning["code"] == "partial_extraction" and warning["document_id"] == imported["document_id"] for warning in done)


def test_api_rejects_host_origin_traversal_and_private_error_inputs(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 400
        assert client.post("/api/v1/queries", headers={"Origin": "https://evil.example"}, json={}).status_code == 403
        rejected = client.post("/api/v1/documents/import", files={"files": ("../private.pdf", b"%PDF-1.7\n", "application/pdf")})
        assert rejected.status_code == 400
        body = client.post("/api/v1/queries", json={"question": "private marker", "scope": {"kind": "unknown"}})
        assert body.status_code == 422 and "private marker" not in body.text


def test_api_backend_restart_marks_query_interrupted(tmp_path):
    from services.api.db import Database
    db = Database(tmp_path / "state.sqlite")
    db.initialize()
    query_id = uid()
    db.execute("INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,'running',?,?)", (query_id, "fixture", "{}", "{}", now(), now()))
    db.initialize()
    assert db.one("SELECT state FROM query_runs WHERE id=?", (query_id,))["state"] == "interrupted"
    assert db.one("SELECT type,data_json FROM events WHERE query_id=?", (query_id,))["type"] == "error"


def test_api_quiesce_nonce_blocks_mutations_and_preserves_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        assert client.post("/api/v1/admin/quiesce").status_code == 403
        header = {"X-RAG-Control-Token": "test-only-nonce"}
        quiesced = client.post("/api/v1/admin/quiesce", headers=header)
        assert quiesced.status_code == 200 and quiesced.json()["state"] == "quiesced"
        assert quiesced.json()["sqlite_checkpoint"][0] == 0
        assert client.get("/api/v1/library/tree").status_code == 200
        assert client.post("/api/v1/queries", json={"question": "fixture", "scope": {"kind": "library"}}).status_code == 503
        assert client.get("/api/v1/admin/status", headers=header).json()["mutations_paused"]
        resumed = client.post("/api/v1/admin/resume", headers=header)
        assert resumed.status_code == 200 and resumed.json()["ingestion_auto_resume"] is False
        assert client.get("/api/v1/admin/status", headers=header).json()["mutations_paused"] is False


def test_api_no_evidence_abstains_without_generation_admission(tmp_path):
    class DeniedGovernor(FakeGovernor):
        @asynccontextmanager
        async def generation(self, on_wait=None):
            raise AssertionError("Language-model admission must not be requested without evidence")
            yield
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    runtime = FakeOllama()
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=DeniedGovernor(), start_jobs=False)
    with browser_client(app) as client:
        query = client.post("/api/v1/queries", json={"question": "Quelle tension ?", "scope": {"kind": "library"}}).json()
        events = client.get(query["events_url"]).text
        assert "event: done" in events and "event: error" not in events and runtime.calls == 0
        result = app.state.db.one("SELECT metrics_json FROM query_runs WHERE id=?", (query["query_id"],))
        assert json.loads(result["metrics_json"])["model_called"] is False


def test_api_manual_pause_resume_and_runtime_mode(tmp_path):
    class ModeGovernor(FakeGovernor):
        mode = "interactive"
        def request_ingestion_pause(self):
            self.mode = "interactive"
        def resume_ingestion(self):
            self.mode = "ingestion"
        def snapshot(self):
            return {"heavy_owner": None, "mode": self.mode}
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=ModeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        imported = client.post("/api/v1/documents/import", files={"files": ("fixture.pdf", b"%PDF-1.7\nfixture", "application/pdf")}).json()
        job = imported["job_id"]
        paused = client.post(f"/api/v1/jobs/{job}/pause")
        assert paused.status_code == 200 and paused.json()["state"] == "paused"
        assert client.post("/api/v1/runtime/mode", json={"mode": "interactive"}).json()["state"] == "interactive"
        assert client.post(f"/api/v1/jobs/{job}/resume").json()["state"] == "queued"
        assert app.state.db.one("SELECT pause_requested FROM jobs WHERE id=?", (job,))["pause_requested"] == 0
        assert client.post("/api/v1/runtime/mode", json={"mode": "ingestion"}).json()["state"] == "ingestion"


def test_api_direct_client_scope_change_excludes_previous_answer_history(tmp_path):
    class RecordingOllama(FakeOllama):
        requests = []
        async def stream(self, messages, cancelled, output_tokens=None):
            self.requests.append(messages)
            yield {"type": "delta", "text": "L'information autorisée est 72 V [S001]."}
            yield {"type": "done", "finish_reason": "stop", "metrics": {"eval_count": 12}}
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    runtime = RecordingOllama()
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        imports = []
        for name, text in [("one.pdf", "CCU-21 private_old_scope_marker 999 V"), ("two.pdf", "CCU-22 authorized_new_scope 72 V")]:
            payload = b"%PDF-1.7\n" + text.encode()
            imported = client.post("/api/v1/documents/import", files={"files": (name, payload, "application/pdf")}).json()
            extraction = {"fingerprint": "fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready", "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "text": text}]}]}
            client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
            imports.append(imported)
        first = client.post("/api/v1/queries", json={"question": "Quelle tension CCU-21 ?", "scope": {"kind": "documents", "documentIds": [imports[0]["document_id"]]}}).json()
        assert "event: done" in client.get(first["events_url"]).text
        second = client.post("/api/v1/queries", json={"question": "Quelle tension CCU-22 ?", "conversation_id": first["conversation_id"], "scope": {"kind": "documents", "documentIds": [imports[1]["document_id"]]}}).json()
        assert second["conversation_id"] == first["conversation_id"]
        assert "event: done" in client.get(second["events_url"]).text
        serialized = json.dumps(runtime.requests[-1])
        assert "authorized_new_scope" in serialized and "private_old_scope_marker" not in serialized and "CCU-21" not in serialized
        assert len(runtime.requests[-1]) == 2


def test_api_readiness_is_blocked_without_artifacts_and_never_loads_models(tmp_path):
    from services.api.embedding import EmbeddingService
    class AvailableVectors(FakeVectors):
        collection = "explicit-test-collection"
        async def request(self, method, path):
            return {"status": "ok"}
    class TagsResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"models": [{"name": "qwen3.5:4b"}]}
    class TagsClient:
        async def get(self, path):
            assert path == "/api/tags"
            return TagsResponse()
    runtime = FakeOllama()
    runtime.client = TagsClient()
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    embedding = EmbeddingService(settings)
    app = create_app(settings=settings, embedding=embedding, vectors=AvailableVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        response = client.get("/api/v1/readiness")
        assert response.status_code == 503
        assert response.json()["checks"]["qdrant"] and response.json()["checks"]["ollama"]
        assert {"embedding_not_ready", "llm_tokenizer_not_ready"} <= set(response.json()["blockers"])
        assert embedding._session is None and embedding._tokenizer is None and runtime.calls == 0
        assert not settings.embedding_dir.exists() and not settings.llm_tokenizer_dir.exists()


def test_api_default_port_is_project_port(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime"}})
    assert settings.origin == "http://127.0.0.1:8785"
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health", headers={"Host": "127.0.0.1:8765"}).status_code == 400


def test_api_controls_do_not_wait_for_long_mutation_but_quiesce_does(tmp_path, monkeypatch):
    import threading

    from starlette.datastructures import UploadFile
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    entered, release = threading.Event(), threading.Event()
    original_read = UploadFile.read
    async def slow_upload_read(self, size=-1):
        # Simule un upload de 200 Mio encore en cours : la mutation reste admise sans bloquer la boucle.
        if not entered.is_set():
            entered.set()
            await asyncio.to_thread(release.wait, 10)
        return await original_read(self, size)
    monkeypatch.setattr(UploadFile, "read", slow_upload_read)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        query = client.post("/api/v1/queries", json={"question": "Quelle tension ?", "scope": {"kind": "library"}}).json()
        assert "event: done" in client.get(query["events_url"]).text
        results = {}
        def call(name, url, **kwargs):
            results[name] = client.post(url, **kwargs)
        upload = threading.Thread(target=call, args=("import", "/api/v1/documents/import"), kwargs={"files": {"files": ("slow.pdf", b"%PDF-1.7\nslow upload", "application/pdf")}})
        upload.start()
        try:
            assert entered.wait(5)
            for name, url, body in [("cancel", f"/api/v1/queries/{query['query_id']}/cancel", None), ("mode", "/api/v1/runtime/mode", {"mode": "interactive"}),
                                    ("search", "/api/v1/search", {"question": "Quelle tension ?", "scope": {"kind": "library"}})]:
                worker = threading.Thread(target=call, args=(name, url), kwargs={"json": body} if body else {})
                worker.start()
                worker.join(5)
                assert not worker.is_alive() and results[name].status_code == 200, name
            assert "import" not in results and app.state.mutations_in_flight == 1
            quiesce = threading.Thread(target=call, args=("quiesce", "/api/v1/admin/quiesce"), kwargs={"headers": {"X-RAG-Control-Token": "test-only-nonce"}})
            quiesce.start()
            quiesce.join(0.5)
            assert quiesce.is_alive() and "import" not in results
        finally:
            release.set()
            upload.join(10)
        quiesce.join(10)
        assert results["import"].status_code == 202 and results["quiesce"].json()["state"] == "quiesced"
        assert app.state.mutations_in_flight == 0
        assert client.post("/api/v1/documents/import", files={"files": ("late.pdf", b"%PDF-1.7\nlate", "application/pdf")}).status_code == 503


def test_api_resume_waits_for_running_quiesce_and_leaves_consistent_state(tmp_path, monkeypatch):
    import threading

    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    jobs, entered, release = app.state.jobs, threading.Event(), threading.Event()
    original_quiesce = jobs.quiesce
    async def slow_quiesce():
        # Simule un checkpoint d'ingestion long : `rag backup` peut abandonner sur timeout et appeler resume.
        entered.set()
        await asyncio.to_thread(release.wait, 10)
        return await original_quiesce()
    jobs.quiesce = slow_quiesce
    header, results = {"X-RAG-Control-Token": "test-only-nonce"}, {}
    with browser_client(app) as client:
        def call(name, url):
            results[name] = client.post(url, headers=header)
        quiesce = threading.Thread(target=call, args=("quiesce", "/api/v1/admin/quiesce"))
        quiesce.start()
        try:
            assert entered.wait(5)
            resume = threading.Thread(target=call, args=("resume", "/api/v1/admin/resume"))
            resume.start()
            resume.join(0.5)
            assert resume.is_alive() and "resume" not in results
        finally:
            release.set()
            quiesce.join(10)
        resume.join(10)
        assert results["quiesce"].json()["state"] == "quiesced" and results["resume"].json()["state"] == "running"
        assert app.state.mutations_paused is False and jobs._suspended is False and app.state.reconciler.suspended is False
        assert client.get("/api/v1/admin/status", headers=header).json()["mutations_paused"] is False


def test_api_move_changes_tree_without_job_version_or_embedding(tmp_path):
    class CountingEmbedding(FakeEmbedding):
        calls = 0
        def embed(self, texts, passage=True):
            self.calls += 1
            return super().embed(texts, passage)
    embedding, vectors = CountingEmbedding(), FakeVectors()
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=embedding, vectors=vectors, tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        payload = b"%PDF-1.7\ncontrolled move fixture"
        imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", payload, "application/pdf")}, data={"relative_paths": '["archive/2025/manual.pdf"]'}).json()
        extraction = {"fingerprint": "move-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready", "pages": [
            {"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": "CCU-21 tension 72 V"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        other = client.post("/api/v1/documents/import", files={"files": ("other.pdf", b"%PDF-1.7\nother", "application/pdf")}, data={"relative_paths": '["engineering/other.pdf"]'}).json()
        document_url = "/api/v1/documents/" + imported["document_id"]
        before = client.get(document_url).json()
        jobs_before = app.state.db.rows("SELECT id,state,generation_id FROM jobs ORDER BY id")
        points_before, calls_before, indexing_before = dict(vectors.points), embedding.calls, app.state.indexer.diagnostics()
        moved = client.post(document_url + "/move", json={"relative_path": "engineering/current/manual.pdf"})
        assert moved.status_code == 200, moved.text
        assert moved.json()["moved"] is True and moved.json()["previous_relative_path"] == "archive/2025/manual.pdf"
        after = client.get(document_url).json()
        assert after["relative_path"] == "engineering/current/manual.pdf" and after["name"] == "manual.pdf"
        assert after["version_id"] == before["version_id"] and after["active_generation_id"] == before["active_generation_id"]
        assert after["versions"] == before["versions"] and after["extraction_revision_id"] == before["extraction_revision_id"]
        assert app.state.db.rows("SELECT id,state,generation_id FROM jobs ORDER BY id") == jobs_before
        assert vectors.points == points_before and embedding.calls == calls_before and app.state.indexer.diagnostics() == indexing_before
        assert app.state.db.one("SELECT count(*) AS n FROM index_generations")["n"] == 1
        folders = {folder["path"]: folder["id"] for folder in client.get("/api/v1/library/tree").json()["folders"]}
        def folder_scope(path):
            response = client.post("/api/v1/search", json={"question": "Quelle tension CCU-21 ?", "scope": {"kind": "folder", "folderId": folders[path], "recursive": True}})
            assert response.status_code == 200, response.text
            return response.json()
        engineering = folder_scope("engineering")
        assert engineering["scope_snapshot"]["generations"] == [before["active_generation_id"]]
        assert engineering["results"][0]["relative_path"] == "engineering/current/manual.pdf"
        archive = folder_scope("archive")
        assert archive["scope_snapshot"]["generations"] == [] and archive["results"] == []
        for unsafe in ["../escape.pdf", "C:/escape.pdf", "%2e%2e/escape.pdf", "/abs.pdf", "engineering/escape.txt", "a\\..\\b.pdf"]:
            rejected = client.post(document_url + "/move", json={"relative_path": unsafe})
            assert rejected.status_code == 400 and rejected.json()["code"] == "invalid_path", unsafe
        conflict = client.post(document_url + "/move", json={"relative_path": "engineering/other.pdf"})
        assert conflict.status_code == 409 and conflict.json()["code"] == "path_conflict"
        assert client.post("/api/v1/documents/unknown/move", json={"relative_path": "x.pdf"}).status_code == 404
        assert client.post(document_url + "/move", json={"relative_path": "x.pdf", "folder": "y"}).status_code == 422
        assert client.post(document_url + "/move", json={"relative_path": "engineering/current/manual.pdf"}).json()["moved"] is False
        client.delete("/api/v1/documents/" + other["document_id"])
        assert client.post(document_url + "/move", json={"relative_path": "engineering/other.pdf"}).status_code == 409
        assert client.get(document_url).json()["relative_path"] == "engineering/current/manual.pdf"


def test_api_historical_revision_and_document_scope_warnings(tmp_path):
    from services.api.reconcile import Reconciler
    runtime = FakeOllama()
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(), ollama=runtime, governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        versions = []
        for text in ["CCU-21 tension 72 V", "CCU-21 tension 110 V"]:
            payload = b"%PDF-1.7\n" + text.encode()
            imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", payload, "application/pdf")}).json()
            extraction = {"fingerprint": "history-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready",
                          "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": text, "section_id": "s0"}]}],
                          "sections": [{"id": "s0", "title": "Tension", "page_index": 0, "block_ids": ["b0"]}]}
            client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
            versions.append(imported)
        old, current = versions
        assert old["document_id"] == current["document_id"] and old["version_id"] != current["version_id"]
        old_generation = app.state.db.one("SELECT id FROM index_generations WHERE version_id=?", (old["version_id"],))["id"]
        def warned(scope):
            response = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": scope})
            assert response.status_code == 200, response.text
            return response.json(), [warning for warning in response.json()["warnings"] if warning["code"] == "dense_unavailable_for_historical_revision"]
        pages = {"kind": "pages", "versionId": old["version_id"], "pageStart": 0, "pageEnd": 0}
        assert warned(pages)[1] == []
        async def delete_generation(generation_id):
            app.state.vectors.points = {key: point for key, point in app.state.vectors.points.items() if point["payload"]["generation_id"] != generation_id}
        app.state.vectors.delete_generation = delete_generation
        assert client.portal.call(Reconciler(app.state.db, app.state.vectors).run_once)["completed"] == [old_generation]
        for scope in [pages, {"kind": "section", "versionId": old["version_id"], "sectionId": "s0"}]:
            result, warnings = warned(scope)
            assert len(warnings) == 1 and warnings[0]["generation_id"] == old_generation and warnings[0]["version_id"] == old["version_id"], scope["kind"]
            assert result["results"][0]["generation_id"] == old_generation and "72 V" in result["results"][0]["text"]
        assert warned({**pages, "versionId": current["version_id"]})[1] == []
        query = client.post("/api/v1/queries", json={"question": "Quelle tension ?", "scope": pages}).json()
        events = client.get(query["events_url"]).text
        assert "event: warning" in events and "dense_unavailable_for_historical_revision" in events and "event: done" in events
        documents = {"kind": "documents", "documentIds": [current["document_id"], "unknown-document"]}
        compared = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": documents, "mode": "comparison"})
        assert compared.status_code == 200, compared.text
        codes = [warning["code"] for warning in compared.json()["warnings"]]
        assert "document_not_in_scope" in codes and "comparison_incomplete" in codes
        empty = client.post("/api/v1/queries", json={"question": "Quelle tension ?", "scope": {"kind": "documents", "documentIds": ["unknown-document"]}})
        assert empty.status_code == 409 and empty.json()["code"] == "no_document_in_scope"


def test_api_short_selection_never_triggers_dense_or_global_lexical_search(tmp_path):
    calls = []
    class SpyEmbedding(FakeEmbedding):
        armed = strict = False
        def embed(self, texts, passage=True):
            if self.armed:
                calls.append("embedding.embed")
                if self.strict:
                    raise AssertionError("Une sélection courte ne doit pas calculer d'embedding")
            return super().embed(texts, passage)
    class SpyVectors(FakeVectors):
        armed = strict = False
        async def query(self, vector, snapshot, limit=24):
            if self.armed:
                calls.append("vectors.query")
                if self.strict:
                    raise AssertionError("Une sélection courte ne doit pas interroger Qdrant")
            return await super().query(vector, snapshot, limit)
    embedding, vectors, runtime = SpyEmbedding(), SpyVectors(), FakeOllama()
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=embedding, vectors=vectors, tokenizer=FakeTokenizer(), ollama=runtime, governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        payload = b"%PDF-1.7\ncontrolled selection fixture"
        imported = client.post("/api/v1/documents/import", files={"files": ("manual.pdf", payload, "application/pdf")}).json()
        text = "CCU-21 tension 72 V ; CCU-22 tension 110 V"
        extraction = {"fingerprint": "selection-fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready",
                      "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "raw_text": text, "bbox": [10, 10, 200, 30], "precision": "block"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        block = client.get(f"/api/v1/versions/{imported['version_id']}/pages/0/blocks").json()["blocks"][0]
        lexical = app.state.search.lexical
        def lexical_spy(question, snapshot):
            calls.append("search.lexical")
            if embedding.strict:
                raise AssertionError("Une sélection courte ne doit pas lancer de recherche FTS5")
            return lexical(question, snapshot)
        app.state.search.lexical = lexical_spy
        embedding.armed = vectors.armed = embedding.strict = vectors.strict = True
        span = {"extractionRevisionId": block["extraction_revision_id"], "blockId": "b0", "blockTextSha256": block["source_text_hash"],
                "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": 19}
        scope = {"kind": "selection", "versionId": imported["version_id"], "spans": [span]}
        searched = client.post("/api/v1/search", json={"question": "Que dit ce passage sur CCU-21 ?", "scope": scope})
        assert searched.status_code == 200, searched.text
        assert [result["text"] for result in searched.json()["results"]] == ["CCU-21 tension 72 V"]
        query = client.post("/api/v1/queries", json={"question": "Que dit ce passage ?", "scope": scope, "mode": "selection"}).json()
        events = client.get(query["events_url"]).text
        assert "event: done" in events and "event: error" not in events and runtime.calls == 1
        assert "CCU-22" not in app.state.db.one("SELECT source_json FROM citations WHERE query_id=?", (query["query_id"],))["source_json"]
        assert calls == []
        embedding.strict = vectors.strict = False
        control = client.post("/api/v1/search", json={"question": "Quelle tension ?", "scope": {"kind": "documents", "documentIds": [imported["document_id"]]}})
        assert control.status_code == 200 and {"embedding.embed", "vectors.query", "search.lexical"} <= set(calls)


def test_api_readiness_accepts_a_missing_collection_only_while_the_library_is_empty(tmp_path):
    from services.api.embedding import EmbeddingService
    from services.api.errors import ApiError

    class EmptyServer(FakeVectors):
        collection = "explicit-test-collection"

        async def request(self, method, path):
            if path == "/collections":
                return {"collections": []}
            raise ApiError("qdrant_unavailable", "Collection absente (404 simulé).", 503)

    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=EmbeddingService(settings), vectors=EmptyServer(), tokenizer=FakeTokenizer(), ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    with browser_client(app) as client:
        body = client.get("/api/v1/readiness").json()
        assert body["checks"]["qdrant"] is True and body["qdrant_collection"] == "absent_empty_library"
        blob = tmp_path / "original.pdf"
        blob.write_bytes(b"%PDF-1.7\n")
        version = app.state.db.import_original("manuel.pdf", "0" * 64, blob)["version_id"]
        app.state.db.execute("INSERT INTO index_generations(id,version_id,fingerprint,expected_chunks,created_at,published_at) VALUES('g',?,'f',0,'t','t')", (version,))
        body = client.get("/api/v1/readiness").json()
        assert body["checks"]["qdrant"] is False and body["qdrant_collection"] == "absent_with_published_generations"
