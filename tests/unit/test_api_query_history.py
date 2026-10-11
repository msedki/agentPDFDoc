"""History reads over real isolated SQLite/ASGI; injected model doubles never generate."""
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.db import Database, json_dump
from services.api.errors import ApiError
from services.api.main import create_app
from services.api.query import QueryService
from services.api.settings import Settings
from tests.integration.test_api_http import (
    FakeEmbedding,
    FakeGovernor,
    FakeOllama,
    FakeTokenizer,
    FakeVectors,
    browser_client,
)

ORIGIN = "http://127.0.0.1:8785"
CONTROL = "test-only-nonce"
SCOPE = {"kind": "cell_range", "versionId": "archived-version", "extractionRevisionId": "old-revision",
         "sheetId": "xl/worksheets/sheet1.xml", "rowStart": 2, "rowEnd": 2, "columnStart": 2, "columnEnd": 2}


def seed(db, query_id, *, conversation="conv-a", timestamp="2026-10-09T12:00:00+00:00", state="done"):
    with db.transaction() as connection:
        connection.execute("INSERT OR IGNORE INTO conversations VALUES(?,?)", (conversation, timestamp))
        connection.execute("INSERT INTO query_runs(id,conversation_id,question,scope_json,snapshot_json,state,answer,"
                           "warnings_json,metrics_json,resolution_json,last_event_id,created_at,updated_at) "
                           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (query_id, conversation, "Tension nominale ? 🧪", json_dump(SCOPE),
                           '{"server_only_snapshot":"historical generations, never resolved as latest"}', state,
                           "La tension est 72 V [S004].", '[{"code":"saved-warning"}]', '{"mode":"analysis"}',
                           '{"method":"explicit_focus"}', 2, timestamp, timestamp))
        connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, 1, "sources", '{"sources":[]}', timestamp))
        terminal = "error" if state == "interrupted" else "done"
        data = {"code": "interrupted"} if state == "interrupted" else {"answer": "La tension est 72 V [S004]."}
        connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, 2, terminal, json_dump(data), timestamp))


@pytest.fixture
def history(tmp_path):
    settings = Settings(tmp_path)
    db = Database(settings.db_path)
    db.initialize()
    return QueryService(db, None, None, None, None, settings), db


def test_query_history_total_order_cursor_and_newer_insert_do_not_duplicate(history):
    service, db = history
    for identifier in ["q-a", "q-c", "q-b"]:
        seed(db, identifier)
    seed(db, "older", timestamp="2026-10-08T12:00:00+00:00")
    first = service.list_runs(limit=2)
    assert [item["query_id"] for item in first["queries"]] == ["q-c", "q-b"]
    assert first["next_cursor"] == "q-b"
    assert all(item["mode"] is None for item in first["queries"])
    assert all(not {"answer", "scope", "snapshot", "metrics"}.intersection(item) for item in first["queries"])
    seed(db, "newer", timestamp="2026-10-10T12:00:00+00:00")
    second = service.list_runs(limit=2, cursor=first["next_cursor"])
    assert [item["query_id"] for item in second["queries"]] == ["q-a", "older"]
    assert second["next_cursor"] is None
    assert service.list_runs(limit=2) == service.list_runs(limit=2)


def test_query_history_conversation_filter_and_cursor_membership(history):
    service, db = history
    seed(db, "a-new")
    seed(db, "a-old", timestamp="2026-10-08T12:00:00+00:00")
    seed(db, "b", conversation="conv-b")
    first = service.list_runs(limit=1, conversation_id="conv-a")
    assert [item["query_id"] for item in first["queries"]] == ["a-new"]
    assert [item["query_id"] for item in service.list_runs(cursor=first["next_cursor"], conversation_id="conv-a")["queries"]] == ["a-old"]
    assert service.list_runs(conversation_id="absent")["queries"] == []
    for cursor in ["missing", "b", "' OR 1=1 --"]:
        with pytest.raises(ApiError) as error:
            service.list_runs(cursor=cursor, conversation_id="conv-a")
        assert error.value.code == "invalid_query_cursor" and error.value.status == 400


def test_query_history_limit_bounds_are_real_and_empty_list_has_no_cursor(history):
    service, db = history
    assert service.list_runs() == {"queries": [], "next_cursor": None}
    for index in range(103):
        seed(db, f"query-{index:03}")
    page = service.list_runs(limit=100)
    assert len(page["queries"]) == 100 and page["next_cursor"] is not None
    assert len(service.list_runs(cursor=page["next_cursor"], limit=100)["queries"]) == 3


@pytest.mark.parametrize("state", ["done", "cancelled", "interrupted", "error", "needs_clarification", "running"])
def test_query_history_detail_preserves_original_scope_state_and_unknown_mode(history, state):
    service, db = history
    seed(db, "saved", state=state)
    result = service.run_detail("saved")
    assert result["query_id"] == "saved" and result["conversation_id"] == "conv-a"
    assert result["question"] == "Tension nominale ? 🧪" and result["scope"] == SCOPE
    assert result["state"] == state and result["last_event_id"] == 2
    assert result["mode"] is None and result["metrics"] == {"mode": "analysis"}
    assert result["answer"] == "La tension est 72 V [S004]."
    assert result["warnings"] == [{"code": "saved-warning"}] and result["resolution"] == {"method": "explicit_focus"}
    assert result["events_url"] == "/api/v1/queries/saved/events"
    assert "snapshot" not in result and "snapshot_json" not in result


def test_query_history_missing_detail_is_explicit(history):
    service, _ = history
    with pytest.raises(ApiError) as error:
        service.run_detail("unknown")
    assert error.value.code == "query_not_found" and error.value.status == 404


def test_query_history_http_session_pagination_validation_replay_and_read_only(tmp_path, monkeypatch):
    """Actual routes/auth/SSE in ASGI; no network listener, no model call or new query."""
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(),
                     ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    db = app.state.db
    queries = app.state.queries

    def forbidden(*args, **kwargs):
        pytest.fail("History read must not authorize against latest, search, generate or mutate.")

    monkeypatch.setattr(queries.resolver, "resolve", forbidden)
    monkeypatch.setattr(queries, "prepare_query", forbidden)
    monkeypatch.setattr(queries, "start_query", forbidden)
    original_connect = db.connect

    @contextmanager
    def read_only_connection():
        with original_connect() as connection:
            connection.execute("PRAGMA query_only=ON")
            yield connection

    with browser_client(app) as client:
        # Lifespan initializes the real schema before inserting the saved fixture.
        seed(db, "saved", state="interrupted")
        monkeypatch.setattr(db, "connect", read_only_connection)
        before = {table: db.rows(f"SELECT * FROM {table}") for table in ("query_runs", "events", "messages", "citations", "jobs", "index_generations")}
        # A second client without another lifespan has no authenticated cookie.
        anonymous = TestClient(app, base_url=ORIGIN)
        try:
            for path in ["/api/v1/queries", "/api/v1/queries/saved"]:
                assert anonymous.get(path).status_code == 401
        finally:
            anonymous.close()
        response = client.get("/api/v1/queries", params={"limit": 1})
        assert response.status_code == 200 and response.json()["queries"][0]["query_id"] == "saved"
        detail = client.get("/api/v1/queries/saved")
        assert detail.status_code == 200 and detail.json()["state"] == "interrupted"
        replay = client.get(detail.json()["events_url"], params={"after": 0})
        assert replay.status_code == 200 and "event: sources" in replay.text and '"code":"interrupted"' in replay.text
        assert client.get("/api/v1/queries/missing").status_code == 404
        assert client.get("/api/v1/queries", params={"cursor": "missing"}).status_code == 400
        for limit in [0, 101, -1, "not-an-integer"]:
            assert client.get("/api/v1/queries", params={"limit": limit}).status_code == 422
        assert client.get("/api/v1/queries", params={"cursor": "x" * 129}).status_code == 422
        assert client.get("/api/v1/queries", headers={"X-RAG-Control-Token": CONTROL}).status_code == 200
        assert before == {table: db.rows(f"SELECT * FROM {table}") for table in before}
    assert queries.tasks == {} and queries.cancel_events == {}


def test_query_history_contract_matches_actual_summary_and_detail(history):
    service, db = history
    seed(db, "saved")
    contract = json.loads((Path(__file__).resolve().parents[2] / "packages/contracts/contracts.json").read_text(encoding="utf-8"))["query_history"]
    page = service.list_runs()
    detail = service.run_detail("saved")
    assert set(page) == set(contract["response"])
    assert set(page["queries"][0]) == set(contract["response"]["queries"][0])
    assert set(detail) == set(contract["response"]["queries"][0]) | set(contract["detail"])
    assert page["queries"][0]["mode"] is contract["response"]["queries"][0]["mode"] is None


def test_query_history_query_timestamp_is_not_nullable_by_schema(history):
    _, db = history
    with db.connect() as connection:
        column = next(row for row in connection.execute("PRAGMA table_info(query_runs)") if row["name"] == "created_at")
    assert column["notnull"] == 1
