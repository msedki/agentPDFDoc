"""Office schema upgrade over a real v3 SQLite PDF/FTS/citation database."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from services.api import db as database_module
from services.api.db import MIGRATIONS, Database, now, relative_document_path, relative_pdf_path
from services.api.errors import ApiError

PDF_TEXT = "CCU-21 : tension 72 V. A😀é e\u0301"
PRESERVED_TABLES = ("pages", "blocks", "chunks", "chunk_sources", "identifiers", "extraction_revisions",
                    "index_generations", "citations")


def legacy_database(tmp_path):
    database = Database(tmp_path / "sqlite" / "rag.sqlite3")
    database.path.parent.mkdir(parents=True)
    with database.connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        for script in sorted(MIGRATIONS.glob("00[123]_*.sql")):
            database.migrate(connection, script.read_text())
        timestamp = now()
        blob = tmp_path / "originals" / "manual.pdf"
        blob.parent.mkdir()
        blob.write_bytes(b"%PDF-1.7\n" + PDF_TEXT.encode())
        digest = hashlib.sha256(blob.read_bytes()).hexdigest()
        connection.execute("INSERT INTO documents(id,name,relative_path,state,active_generation_id,created_at,updated_at) VALUES('document','manual.pdf','manual.pdf','ready','generation',?,?)", (timestamp, timestamp))
        connection.execute("INSERT INTO document_versions(id,document_id,sha256,blob_path,page_count,created_at) VALUES('version','document',?,?,1,?)", (digest, str(blob), timestamp))
        connection.execute("INSERT INTO extraction_revisions(id,version_id,fingerprint,source_hash,created_at) VALUES('revision','version','pdf-parser-v1','source-hash',?)", (timestamp,))
        connection.execute("INSERT INTO index_generations(id,version_id,fingerprint,state,expected_chunks,actual_chunks,created_at,published_at,extraction_revision_id) VALUES('generation','version','pdf-index-v1','ready',1,1,?,?,'revision')", (timestamp, timestamp))
        connection.execute("INSERT INTO pages VALUES('generation',0,?,'ready')", (json.dumps({"width": 595, "height": 842}),))
        connection.execute("INSERT INTO blocks VALUES('generation','block',0,'text',?,'[1,2,3,4]','block',NULL,'{}','revision',?)", (PDF_TEXT, hashlib.sha256(PDF_TEXT.encode()).hexdigest()))
        connection.execute("INSERT INTO chunks(id,chunk_uuid,generation_id,version_id,section_title,text,e5_tokens,llm_tokens,text_hash,extraction_revision_id) VALUES(42,'chunk','generation','version','Énergie',?,20,18,?,'revision')", (PDF_TEXT, hashlib.sha256(PDF_TEXT.encode()).hexdigest()))
        connection.execute("INSERT INTO chunk_sources VALUES('chunk','block',0,0,?,0)", (len(PDF_TEXT),))
        connection.execute("INSERT INTO identifiers VALUES('chunk','CCU-21','CCU21')")
        connection.execute("INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES('query','Tension ?','{}','{}','done',?,?)", (timestamp, timestamp))
        source = {"version_id": "version", "extraction_revision_id": "revision", "page_index": 0,
                  "block_ids": ["block"], "text": PDF_TEXT}
        connection.execute("INSERT INTO citations VALUES('query','S1','version','document',?)", (json.dumps(source, ensure_ascii=False),))
    return database, blob


def snapshot(database):
    with database.connect() as connection:
        return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1,2")]
                for table in PRESERVED_TABLES}


def assert_valid(database, version):
    with database.connect() as connection:
        assert Database.schema_version(connection) == version
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
        assert [row[0] for row in connection.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'tension'")] == [42]


def test_v3_upgrade_preserves_pdf_identity_fts_citations_and_original(tmp_path):
    database, original = legacy_database(tmp_path)
    before, original_bytes = snapshot(database), original.read_bytes()
    database.initialize()
    assert_valid(database, 4)
    assert snapshot(database) == before
    assert database.one("SELECT format,mime_type FROM document_versions WHERE id='version'") == {"format": "pdf", "mime_type": "application/pdf"}
    assert original.read_bytes() == original_bytes
    backups = list((database.path.parent / "schema-backups").glob("*.sqlite3"))
    assert len(backups) == 1
    restored = Database(backups[0])
    assert_valid(restored, 3)
    assert snapshot(restored) == before
    assert not list((database.path.parent / "schema-backups").glob("*.partial"))
    database.initialize()
    assert snapshot(database) == before
    assert len(list((database.path.parent / "schema-backups").glob("*.sqlite3"))) == 1


def test_upgrade_online_backup_includes_committed_wal_content(tmp_path):
    database, _ = legacy_database(tmp_path)
    with database.connect() as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE blocks SET text=? WHERE id='block'", (PDF_TEXT + " WAL",))
        assert Path(str(database.path) + "-wal").stat().st_size > 0
        before = snapshot(database)
        database.initialize()
        backup = Database(next((database.path.parent / "schema-backups").glob("*.sqlite3")))
        assert snapshot(backup) == before
        assert_valid(backup, 3)
    assert snapshot(database) == before


def test_failed_migration_rolls_back_schema_and_pdf_data(tmp_path, monkeypatch):
    database, original = legacy_database(tmp_path)
    before = snapshot(database)
    scripts = tmp_path / "migration_failure"
    scripts.mkdir()
    source = (MIGRATIONS / "004_office_documents.sql").read_text()
    (scripts / "004_failure.sql").write_text(source + "\nINSERT INTO deliberately_absent_table VALUES(1);\n")
    monkeypatch.setattr(database_module, "MIGRATIONS", scripts)
    with pytest.raises(sqlite3.OperationalError, match="deliberately_absent_table"):
        database.initialize()
    assert_valid(database, 3)
    assert snapshot(database) == before
    with database.connect() as connection:
        assert "format" not in {row["name"] for row in connection.execute("PRAGMA table_info(document_versions)")}
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='office_cells'").fetchone() is None
    assert original.is_file()
    assert_valid(Database(next((database.path.parent / "schema-backups").glob("*.sqlite3"))), 3)


def test_migration_refuses_before_mutation_when_backup_has_no_space(tmp_path, monkeypatch):
    from types import SimpleNamespace

    database, _ = legacy_database(tmp_path)
    before = snapshot(database)
    monkeypatch.setattr(database_module.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(ApiError) as error:
        database.initialize()
    assert error.value.code == "migration_backup_no_space"
    assert_valid(database, 3)
    assert snapshot(database) == before


def test_fresh_database_and_repeated_initialization_have_office_tables(tmp_path):
    database = Database(tmp_path / "fresh.sqlite3")
    database.initialize()
    database.initialize()
    with database.connect() as connection:
        assert Database.schema_version(connection) == 4
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"office_documents", "office_units", "office_unit_blocks", "office_cells", "office_cell_bindings"} <= names
    assert not (tmp_path / "schema-backups").exists()


@pytest.mark.parametrize("document_format,mime", [("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                                                 ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
def test_office_import_deduplicates_without_rewriting_an_original(tmp_path, document_format, mime):
    database = Database(tmp_path / "rag.sqlite3")
    database.initialize()
    # Storage registration is not package validation: the API/worker tests
    # exercise actual containers. Here a source blob models immutable bytes.
    original = tmp_path / ("original." + document_format)
    original.write_bytes(b"immutable source bytes")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    first = database.import_original("folder/document." + document_format, digest, original)
    repeated = database.import_original("folder/document." + document_format, digest, original)
    assert repeated["reused"] is True
    assert repeated["job_id"] == first["job_id"]
    assert repeated["version_id"] == first["version_id"]
    assert database.one("SELECT count(*) n FROM document_versions")["n"] == 1
    row = database.version(first["version_id"])
    assert (row["format"], row["mime_type"]) == (document_format, mime)
    assert original.read_bytes() == b"immutable source bytes"
    with pytest.raises(ApiError):
        database.move_document(first["document_id"], "folder/renamed.pdf")
    database.move_document(first["document_id"], "folder/renamed." + document_format)
    assert database.version(first["version_id"])["blob_path"] == str(original)


@pytest.mark.parametrize("path", ["../a.docx", "folder//a.xlsx", "NUL.docx", "folder/a.xlsx:stream", "C:/a.docx", "%252e%252e/a.xlsx"])
def test_office_paths_keep_cross_platform_safety(path):
    with pytest.raises(ApiError):
        relative_document_path(path)


def test_legacy_pdf_path_validator_keeps_its_pdf_only_boundary():
    assert relative_document_path("folder/budget.XLSX") == "folder/budget.XLSX"
    assert relative_pdf_path("folder/manual.pdf") == "folder/manual.pdf"
    with pytest.raises(ApiError):
        relative_pdf_path("folder/budget.xlsx")
