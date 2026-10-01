"""Lecture d'une base sauvegardée par l'outil de qualification de migration (R11), en lecture seule."""

import sqlite3

from tools.qualification.migration_check import database


def test_database_reads_schema_counts_citations_and_active_generations_without_writing(tmp_path):
    path = tmp_path / "app.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE schema_version(version INTEGER); INSERT INTO schema_version VALUES (1), (2);
            CREATE TABLE documents(id TEXT, active_generation_id TEXT, deleted_at TEXT);
            INSERT INTO documents VALUES ('d1', 'g1', NULL), ('d2', 'g9', '2026-09-30');
            CREATE TABLE document_versions(id TEXT); INSERT INTO document_versions VALUES ('v1');
            CREATE TABLE index_generations(id TEXT); INSERT INTO index_generations VALUES ('g1');
            CREATE TABLE citations(query_id TEXT, source_id TEXT, document_id TEXT);
            INSERT INTO citations VALUES ('q1', 'S002', 'd1'), ('q1', 'S001', 'd1');
        """)
    before = path.read_bytes()
    result = database(path)
    assert result["schema_version"] == 2
    assert result["counts"] == {"documents": 2, "document_versions": 1, "index_generations": 1, "citations": 2}
    assert [row["source_id"] for row in result["citations"]] == ["S001", "S002"]
    assert result["active_generations"] == {"d1": "g1"}
    assert path.read_bytes() == before
