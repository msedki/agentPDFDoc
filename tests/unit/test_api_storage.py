"""Real SQLite/FTS5 invariants with explicitly fake embedding/vector boundaries."""
import asyncio
import hashlib
import re
import sqlite3
from contextlib import closing

import pytest

from services.api.db import MIGRATIONS, Database, now, relative_pdf_path
from services.api.errors import ApiError
from services.api.indexing import Indexer
from services.api.schemas import Scope
from services.api.scope import ScopeResolver
from services.api.settings import Settings


class FakeEmbedding:
    def count(self, text, passage=True):
        return len(text) // 4 + 3

    def embed(self, texts, passage=True):
        return [[1.0] + [0.0] * 383 for text in texts]


class FakeLlmTokenizer:
    def count(self, text):
        return len(text) // 4 + 1


class FakeVectors:
    def __init__(self, fail=False):
        self.points = {}
        self.fail = fail

    async def ensure_collection(self):
        pass

    async def upsert(self, points):
        if self.fail:
            raise ApiError("qdrant_unavailable", "Test : indisponibilité Qdrant.", 503)
        self.points.update({point["id"]: point for point in points})

    async def verify(self, expected):
        assert {key: self.points[key]["payload"]["text_hash"] for key in expected} == expected

    async def query(self, vector, snapshot, limit=24):
        return [key for key, point in self.points.items() if point["payload"]["generation_id"] in snapshot.generations][:limit]

    async def close(self):
        pass


@pytest.fixture
def storage(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "chunking": {"overlap_max_tokens": 0}})
    db = Database(settings.db_path)
    db.initialize()
    vectors = FakeVectors()
    indexer = Indexer(db, FakeEmbedding(), vectors, settings, FakeLlmTokenizer())
    return settings, db, vectors, indexer


def import_fixture(storage, path="folder/manual.pdf", text="CCU-21 : tension nominale 72 V.", pages=None, sections=None):
    settings, db, vectors, indexer = storage
    payload = b"%PDF-1.7\n" + text.encode()
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original(path, digest, blob)
    extraction = {"sha256": digest, "fingerprint": "fixture-native-v1", "page_count": len(pages or [0]), "status": "ready", "pages": pages or [{"page_index": 0, "width": 595, "height": 842, "media_box": [0, 0, 595, 842], "crop_box": [0, 0, 595, 842], "rotation": 0, "blocks": [{"id": "b0", "type": "text", "text": text, "raw_text": text, "bbox": [10, 10, 100, 30], "precision": "block"}]}]}
    if sections:
        extraction["sections"] = sections
    asyncio.run(indexer.index(imported["job_id"], extraction))
    return imported, extraction


@pytest.mark.parametrize("path", ["../a.pdf", "C:/a.pdf", "/a.pdf", "%252e%252e/a.pdf", "a\\..\\b.pdf", "NUL.pdf", "folder/a.pdf:stream", "a.txt", "folder//a.pdf", "folder./a.pdf"])
def test_api_paths_reject_unsafe_input(path):
    with pytest.raises(ApiError):
        relative_pdf_path(path)


def test_api_failed_vectors_keep_previous_active_generation(storage):
    imported, _ = import_fixture(storage)
    _, db, vectors, indexer = storage
    before = db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"]
    new_payload = b"%PDF-1.7\nCCU-21 110 V"
    digest = hashlib.sha256(new_payload).hexdigest()
    blob = storage[0].data_dir / "originals" / (digest + ".pdf")
    blob.write_bytes(new_payload)
    changed = db.import_original("folder/manual.pdf", digest, blob)
    vectors.fail = True
    extraction = {"sha256": digest, "fingerprint": "fixture-native-v1", "page_count": 1, "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "text": "CCU-21 110 V"}]}]}
    with pytest.raises(ApiError):
        asyncio.run(indexer.index(changed["job_id"], extraction))
    assert db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"] == before
    assert ScopeResolver(db).resolve(Scope(kind="library")).generations == [before]
    assert db.one("SELECT state FROM index_generations WHERE version_id=?", (changed["version_id"],))["state"] == "staging"


def test_api_reimport_reuses_job_and_version(storage):
    imported, _ = import_fixture(storage)
    version = storage[1].version(imported["version_id"])
    duplicate = storage[1].import_original("folder/manual.pdf", version["sha256"], version["blob_path"])
    assert duplicate["reused"] is True
    assert duplicate["job_id"] == imported["job_id"]
    assert duplicate["version_id"] == imported["version_id"]


def test_api_unicode_selection_hash_and_revision(storage):
    text = "A😀é ﬁ e\u0301 fin"
    imported, _ = import_fixture(storage, text=text)
    _, db, _, _ = storage
    block = db.one("SELECT * FROM blocks")
    span = {"extractionRevisionId": block["extraction_revision_id"], "blockId": "b0", "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point", "startOffset": 1, "endOffset": 3}
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="selection", versionId=imported["version_id"], spans=[span]))
    assert resolver.selected_sources(snapshot)[0]["text"] == "😀é"
    with pytest.raises(ApiError):
        resolver.resolve(Scope(kind="selection", versionId=imported["version_id"], spans=[{**span, "blockTextSha256": "0" * 64}]))
    with pytest.raises(ApiError):
        resolver.resolve(Scope(kind="selection", versionId=imported["version_id"], spans=[{**span, "extractionRevisionId": "other"}]))


def test_api_partial_never_replaces_complete_without_explicit_publication(storage):
    imported, extraction = import_fixture(storage)
    settings, db, vectors, indexer = storage
    before = db.one("SELECT active_generation_id FROM documents")["active_generation_id"]
    from services.api.db import now, uid
    job_id = uid()
    db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
    extraction["status"] = "ready_partial"
    asyncio.run(indexer.index(job_id, extraction))
    assert db.one("SELECT active_generation_id FROM documents")["active_generation_id"] == before
    assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "ready_partial"
    partial = db.one("SELECT * FROM index_generations WHERE id=(SELECT generation_id FROM jobs WHERE id=?)", (job_id,))
    assert partial["published_at"] is None
    assert ScopeResolver(db).resolve(Scope(kind="pages", versionId=imported["version_id"], pageStart=0, pageEnd=0)).generations == [before]
    indexer.publish(job_id, partial["id"], partial["actual_chunks"], partial=True, allow_partial=True)
    assert db.one("SELECT active_generation_id FROM documents")["active_generation_id"] == partial["id"]


def test_api_embedding_cache_separates_full_model_identity(storage):
    imported, extraction = import_fixture(storage)
    _, db, _, indexer = storage
    class CountedEmbedding(FakeEmbedding):
        def __init__(self, identity):
            self.calls, self.model_identity = 0, identity
        def identity(self):
            return {"fingerprint": self.model_identity}
        def embed(self, texts, passage=True):
            self.calls += 1
            return super().embed(texts, passage)
    from services.api.db import now, uid
    def reindex():
        job_id = uid()
        db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, imported["document_id"], imported["version_id"], now(), now()))
        return asyncio.run(indexer.index(job_id, extraction))
    model_a = CountedEmbedding("graph-a-tokenizer-a-prefix-pooling")
    indexer.embedding = model_a
    generation_a = reindex()
    reindex()
    assert model_a.calls == 1
    model_b = CountedEmbedding("graph-b-tokenizer-a-prefix-pooling")
    indexer.embedding = model_b
    generation_b = reindex()
    assert model_b.calls == 1
    assert db.one("SELECT fingerprint FROM index_generations WHERE id=?", (generation_a,)) != db.one("SELECT fingerprint FROM index_generations WHERE id=?", (generation_b,))
    assert db.one("SELECT count(*) AS n FROM embedding_cache")["n"] == 3


def test_api_reconciler_preserves_query_leases_and_originals(storage):
    imported, _ = import_fixture(storage)
    _, db, vectors, _ = storage
    from services.api.db import json_dump, now, uid
    from services.api.reconcile import Reconciler
    snapshot = ScopeResolver(db).resolve(Scope(kind="library"))
    generation = snapshot.generations[0]
    query_id = uid()
    db.execute("INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,'running',?,?)", (query_id, "fixture", "{}", json_dump(snapshot.as_dict()), now(), now()))
    db.execute("UPDATE documents SET deleted_at=? WHERE id=?", (now(), imported["document_id"]))
    db.execute("INSERT INTO vector_cleanup VALUES(?,?,'pending',NULL,?,?)", (generation, "deleted", now(), now()))
    async def remove_points(generation_id):
        vectors.points = {key: point for key, point in vectors.points.items() if point["payload"]["generation_id"] != generation_id}
    vectors.delete_generation = remove_points
    reconciler = Reconciler(db, vectors)
    assert asyncio.run(reconciler.run_once())["completed"] == []
    assert vectors.points
    db.execute("UPDATE query_runs SET state='done' WHERE id=?", (query_id,))
    assert asyncio.run(reconciler.run_once())["completed"] == [generation]
    assert not vectors.points and db.one("SELECT count(*) AS n FROM chunks")["n"] == 0
    assert db.one("SELECT count(*) AS n FROM blocks")["n"] == 1
    assert db.one("SELECT count(*) AS n FROM extraction_revisions")["n"] == 1
    original = db.one("SELECT blob_path FROM document_versions")["blob_path"]
    from pathlib import Path
    assert Path(original).is_file()


def test_api_restart_requires_manual_job_resume(storage):
    imported, _ = import_fixture(storage)
    db = storage[1]
    db.execute("UPDATE jobs SET state='extracting',lease_pid=9999 WHERE id=?", (imported["job_id"],))
    db.initialize()
    job = db.one("SELECT state,error_code,lease_pid FROM jobs WHERE id=?", (imported["job_id"],))
    assert job == {"state": "paused", "error_code": "interrupted", "lease_pid": None}


def test_api_chunks_record_actual_injected_llm_token_count(storage):
    text = "CCU-21 : tension 72 V. A😀é ﬁ e\u0301"
    import_fixture(storage, text=text)
    chunk = storage[1].one("SELECT text,e5_tokens,llm_tokens FROM chunks")
    assert chunk["text"] == text
    assert chunk["llm_tokens"] == FakeLlmTokenizer().count(text) > 0
    assert chunk["e5_tokens"] == FakeEmbedding().count(text)
    assert chunk["llm_tokens"] != chunk["e5_tokens"]


def test_api_gc_waits_for_active_indexing_writer(storage):
    from services.api.db import now
    from services.api.reconcile import Reconciler
    imported, _ = import_fixture(storage)
    _, db, vectors, _ = storage
    generation = db.one("SELECT generation_id FROM jobs WHERE id=?", (imported["job_id"],))["generation_id"]
    db.execute("UPDATE jobs SET state='cancelling' WHERE id=?", (imported["job_id"],))
    db.execute("UPDATE documents SET deleted_at=? WHERE id=?", (now(), imported["document_id"]))
    db.execute("INSERT INTO vector_cleanup VALUES(?,?,'pending',NULL,?,?)", (generation, "deleted", now(), now()))
    calls = []
    async def delete_generation(generation_id):
        calls.append(generation_id)
    vectors.delete_generation = delete_generation
    reconciler = Reconciler(db, vectors)
    assert asyncio.run(reconciler.run_once())["pinned"] == [generation] and not calls
    db.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (imported["job_id"],))
    assert asyncio.run(reconciler.run_once())["completed"] == [generation] and calls == [generation]


def suspended_fixture(storage):
    settings, db, _, _ = storage
    payload = b"%PDF-1.7\ncontrolled suspended fixture"
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    return db, digest, blob, db.import_original("folder/suspended.pdf", digest, blob)


@pytest.mark.parametrize("state", ["paused", "pausing"])
def test_api_reimport_during_suspended_job_returns_existing_job(storage, state):
    """`resume_required` seulement pour `paused`, que POST /jobs/{id}/resume accepte ; `pausing` est renvoyé avec son état."""
    db, digest, blob, first = suspended_fixture(storage)
    db.execute("UPDATE jobs SET state=?,pause_requested=1 WHERE id=?", (state, first["job_id"]))
    again = db.import_original("folder/suspended.pdf", digest, blob)
    expected = {**first, "reused": True, "job_state": state}
    assert again == ({**expected, "resume_required": True} if state == "paused" else expected)
    assert db.one("SELECT count(*) AS n FROM jobs WHERE version_id=?", (first["version_id"],))["n"] == 1
    assert db.one("SELECT count(*) AS n FROM document_versions")["n"] == 1
    db.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (first["job_id"],))
    retried = db.import_original("folder/suspended.pdf", digest, blob)
    assert retried["reused"] is False and retried["version_id"] == first["version_id"] and retried["job_id"] != first["job_id"]


def test_api_reimport_during_cancelling_queues_a_new_job_like_reindex(storage):
    """Ronde 4 : l'annulation reste définitive ; le réimport crée un travail neuf, exécuté après elle par la file séquentielle."""
    db, digest, blob, first = suspended_fixture(storage)
    db.execute("UPDATE jobs SET state='cancelling',cancel_requested=1 WHERE id=?", (first["job_id"],))
    again = db.import_original("folder/suspended.pdf", digest, blob)
    assert again["reused"] is False and set(again) == {"document_id", "version_id", "job_id", "reused"}
    assert (again["document_id"], again["version_id"]) == (first["document_id"], first["version_id"]) and again["job_id"] != first["job_id"]
    jobs = db.rows("SELECT id,state,cancel_requested FROM jobs WHERE version_id=? ORDER BY created_at,rowid", (first["version_id"],))
    assert jobs == [{"id": first["job_id"], "state": "cancelling", "cancel_requested": 1}, {"id": again["job_id"], "state": "queued", "cancel_requested": 0}]
    # Fin de l'annulation : le document non publié affiche le travail neuf en file, pas l'annulation.
    with db.transaction() as connection:
        connection.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (first["job_id"],))
        db.align_document_states(connection, [first["document_id"]])
    assert db.one("SELECT state FROM documents WHERE id=?", (first["document_id"],))["state"] == "queued"


def legacy_v2_database(path, patched=False):
    """Base v2 réelle : sans les deux colonnes, ou déjà patchée à chaud par l'ancien initialize()."""
    script = (MIGRATIONS / "001_initial.sql").read_text(encoding="utf-8")
    if not patched:
        script = re.sub(r" (?:pause_requested|resolution_json) [^\n]*\n", "", script)
        assert "pause_requested" not in script and "resolution_json" not in script
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(script + (MIGRATIONS / "002_cache_and_gc.sql").read_text(encoding="utf-8"))
        connection.execute("INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES('legacy','fixture','{}','{}','done','t','t')")
        connection.execute("INSERT INTO documents(id,name,relative_path,created_at,updated_at) VALUES('d','a.pdf','a.pdf','t','t')")
        connection.execute("INSERT INTO document_versions(id,document_id,sha256,blob_path,created_at) VALUES('v','d','0','a','t')")
        connection.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES('j','d','v','ready','complete','t','t')")
        connection.commit()
        assert [row[0] for row in connection.execute("SELECT version FROM schema_version ORDER BY version")] == [1, 2]


@pytest.mark.parametrize("patched", [False, True])
def test_api_migration_003_upgrades_existing_v2_idempotently(tmp_path, patched):
    path = tmp_path / "legacy.sqlite"
    legacy_v2_database(path, patched)
    db = Database(path)
    db.initialize()
    db.initialize()
    assert [row["version"] for row in db.rows("SELECT version FROM schema_version ORDER BY version")] == [1, 2, 3, 4]
    assert db.one("SELECT resolution_json FROM query_runs WHERE id='legacy'")["resolution_json"] == "{}"
    assert db.one("SELECT pause_requested FROM jobs WHERE id='j'")["pause_requested"] == 0
    assert [row["name"] for row in db.rows("PRAGMA table_info(jobs)")].count("pause_requested") == 1


def test_api_migration_fresh_database_reaches_v4(tmp_path):
    db = Database(tmp_path / "fresh.sqlite")
    db.initialize()
    assert [row["version"] for row in db.rows("SELECT version FROM schema_version ORDER BY version")] == [1, 2, 3, 4]
    assert {"resolution_json"} <= {row["name"] for row in db.rows("PRAGMA table_info(query_runs)")}
    assert {"chunks_ai", "chunks_ad", "chunks_au"} == {row["name"] for row in db.rows("SELECT name FROM sqlite_master WHERE type='trigger'")}


def test_api_refuses_database_newer_than_code_without_touching_it(tmp_path):
    from services.api.db import uid
    db = Database(tmp_path / "newer.sqlite")
    db.initialize()
    query_id = uid()
    db.execute("INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,'running',?,?)", (query_id, "fixture", "{}", "{}", now(), now()))
    db.execute("INSERT INTO schema_version VALUES(5)")
    with pytest.raises(ApiError) as caught:
        db.initialize()
    assert caught.value.code == "database_schema_too_new" and caught.value.details == {"database_version": 5, "supported_version": 4}
    assert db.one("SELECT state FROM query_runs WHERE id=?", (query_id,))["state"] == "running"


def test_api_documents_scope_reports_ignored_documents(storage):
    indexed, _ = import_fixture(storage)
    removed, _ = import_fixture(storage, path="folder/removed.pdf", text="CCU-22 : tension nominale 110 V.")
    _, db, _, _ = storage
    pending = db.import_original("folder/pending.pdf", "0" * 64, "pending.pdf")
    db.execute("UPDATE documents SET deleted_at=? WHERE id=?", (now(), removed["document_id"]))
    resolver = ScopeResolver(db)
    requested = [indexed["document_id"], pending["document_id"], removed["document_id"], "unknown-document"]
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=requested), "comparison")
    assert set(snapshot.documents.values()) == {indexed["document_id"]}
    ignored = {warning["document_id"]: warning["reason"] for warning in snapshot.warnings if warning["code"] == "document_not_in_scope"}
    assert ignored == {pending["document_id"]: "not_indexed", removed["document_id"]: "deleted", "unknown-document": "unknown"}
    reduced = [warning for warning in snapshot.warnings if warning["code"] == "comparison_incomplete"]
    assert reduced and reduced[0]["requested_documents"] == 4 and reduced[0]["compared_documents"] == 1
    assert "warnings" not in snapshot.as_dict()
    assert not [warning for warning in resolver.resolve(Scope(kind="documents", documentIds=requested)).warnings if warning["code"] == "comparison_incomplete"]
    assert resolver.resolve(Scope(kind="documents", documentIds=[indexed["document_id"]])).warnings == []
    with pytest.raises(ApiError) as caught:
        resolver.resolve(Scope(kind="documents", documentIds=[pending["document_id"], removed["document_id"], "unknown-document"]))
    assert caught.value.code == "no_document_in_scope" and caught.value.status == 409
    assert {item["reason"] for item in caught.value.details["documents"]} == {"not_indexed", "deleted", "unknown"}
