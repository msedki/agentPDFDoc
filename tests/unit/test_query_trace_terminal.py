"""Real QueryService/SQLite/OOXML; named embedding/vector/tokenizer doubles.

Thread barriers force cancellation interleavings without changing the original
transaction methods. The gateway forbids native inference or network access.
"""

import asyncio
import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from test_enhanced_retrieval import range_fixture
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.execution_trace import ExecutionTrace, read_verified_trace
from services.api.query import QueryService
from services.api.schemas import QueryRequest, Scope

TERMINALS = {"query.done", "query.error", "query.cancelled"}


class ForbiddenGateway:
    calls = 0

    async def stream(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("This exact cell-reading route must not call a generator")
        yield  # pragma: no cover -- async-generator interface only


@pytest.fixture
def traced_query(rag):
    snapshot = range_fixture(rag)
    settings, db, _, _, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True}
    settings.profile["trace"] = {"mode": "full"}
    gateway = ForbiddenGateway()
    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()), gateway, settings)
    request = QueryRequest(question="Quelles valeurs contiennent exactement les cellules B5 et B6 ?",
                           scope=Scope(**snapshot.scope))
    return SimpleNamespace(service=service, request=request, db=db, settings=settings, gateway=gateway)


def block(event, label):
    assert event.wait(10), f"Scheduling barrier timed out: {label}"


async def reached(event, label):
    await asyncio.to_thread(block, event, label)


def observed(fixture, query_id):
    run = fixture.service.run_detail(query_id)
    events = fixture.db.rows("SELECT * FROM events WHERE query_id=? ORDER BY id", (query_id,))
    trace = read_verified_trace(fixture.settings.data_dir / "traces" / (query_id + ".jsonl"))
    return run, [event for event in events if event["type"] in {"done", "error", "cancelled"}], trace


def assert_confirmed(fixture, query_id, state):
    run, events, trace = observed(fixture, query_id)
    terminals = [row for row in trace if row["phase"] in TERMINALS]
    assert run["state"] == state
    assert len(events) == len(terminals) == 1
    event, terminal = events[0], terminals[0]
    payload = json.loads(event["data_json"])
    assert terminal["phase"] == "query." + event["type"]
    assert terminal["data"] == {**payload, "state": state, "event_id": event["id"], "persistence_confirmed": True}
    # Existing consumers read native/runtime metrics at this unchanged location.
    assert terminal["data"]["metrics"] == run["metrics"]
    assert run["metrics"]["execution_trace"]["snapshot_stage"] == "before_terminal_persistence"
    assert run["metrics"]["execution_trace"]["terminal_captured"] is False
    assert fixture.gateway.calls == 0 and run["metrics"]["model_called"] is False
    assert "Valeur littérale « 0 »" in run["answer"] and "Valeur littérale « 36 »" in run["answer"]
    return trace


@pytest.mark.parametrize("timing,expected", [
    ("control", "done"),
    ("before_commit_late_signal", "cancelled"),
    ("before_commit_immediate_signal", "cancelled"),
    ("after_commit_before_return", "done"),
    ("during_final_observation", "done"),
])
def test_trace_terminal_follows_actual_committed_state_under_late_cancellation(traced_query, monkeypatch, timing, expected):
    fixture, service = traced_query, traced_query.service
    original_finish = service.finish
    original_cancel = service.request_cancellation
    original_observe = service.capture_persisted_terminal
    entered, persisted = threading.Event(), threading.Event()
    release_finish, release_signal = threading.Event(), threading.Event()

    if timing in {"before_commit_late_signal", "before_commit_immediate_signal"}:
        def finish(*args):
            entered.set()
            block(release_finish, "finish before commit")
            return original_finish(*args)
        monkeypatch.setattr(service, "finish", finish)
    elif timing == "after_commit_before_return":
        def finish(*args):
            result = original_finish(*args)
            entered.set()
            block(release_finish, "finish after commit")
            return result
        monkeypatch.setattr(service, "finish", finish)
    elif timing == "during_final_observation":
        def observe(*args):
            entered.set()
            block(release_finish, "final observer before its read and capture")
            return original_observe(*args)
        monkeypatch.setattr(service, "capture_persisted_terminal", observe)

    if timing == "before_commit_late_signal":
        def persist_cancel(query_id):
            state = original_cancel(query_id)
            persisted.set()
            block(release_signal, "late cancellation signal")
            return state
        monkeypatch.setattr(service, "request_cancellation", persist_cancel)

    async def scenario():
        response = await service.create_async(fixture.request)
        query_id = response["query_id"]
        task = service.tasks[query_id]
        try:
            if timing == "before_commit_late_signal":
                await reached(entered, "finish entered")
                cancellation = asyncio.create_task(service.cancel_async(query_id))
                await reached(persisted, "cancel flag committed")
                release_finish.set()
                await asyncio.wait_for(asyncio.shield(task), 10)
                release_signal.set()
                await asyncio.wait_for(cancellation, 10)
            elif timing != "control":
                await reached(entered, timing)
                await service.cancel_async(query_id)
                release_finish.set()
                await asyncio.wait_for(asyncio.shield(task), 10)
            else:
                await asyncio.wait_for(asyncio.shield(task), 10)
        finally:
            release_finish.set()
            release_signal.set()
        return query_id

    query_id = asyncio.run(scenario())
    trace = assert_confirmed(fixture, query_id, expected)
    assert trace[-1]["phase"] == ("query.cancelled" if expected == "cancelled" else "query.done")
    assert "query.done_intent" in {row["phase"] for row in trace}
    intents = [row for row in trace if row["phase"].endswith("_intent")]
    assert all(row["payload_bytes"] < 256 for row in intents)


@pytest.mark.parametrize("state", ["done", "length_limited", "error", "cancelled"])
def test_final_observer_preserves_committed_payload_and_does_not_write_sql(traced_query, state):
    fixture, service = traced_query, traced_query.service
    query_id = service.prepare_query(fixture.request)[0]["query_id"]
    metrics = {"model_called": False, "eval_count": 7}
    event = {"status": state, "text": "unchanged", "metrics": metrics}
    if state in {"done", "length_limited"}:
        service.finish(query_id, state, "unchanged", [], metrics, event)
    elif state == "error":
        service.fail(query_id, "unchanged", metrics, event)
    else:
        service.mark_cancelled(query_id, "unchanged", metrics)
    before = (fixture.db.rows("SELECT * FROM query_runs"), fixture.db.rows("SELECT * FROM events"),
              fixture.db.rows("SELECT * FROM messages"))
    trace = ExecutionTrace(fixture.settings, query_id)
    service.capture_persisted_terminal(query_id, trace)
    trace.close()
    after = (fixture.db.rows("SELECT * FROM query_runs"), fixture.db.rows("SELECT * FROM events"),
             fixture.db.rows("SELECT * FROM messages"))
    assert before == after
    run, events, rows = observed(fixture, query_id)
    assert len(rows) == len(events) == 1
    assert rows[0]["phase"] == "query." + events[0]["type"]
    assert rows[0]["data"] == {**json.loads(events[0]["data_json"]), "state": state,
                                "event_id": run["last_event_id"], "persistence_confirmed": True}
    assert rows[0]["data"]["metrics"]["eval_count"] == 7


def test_finish_failure_confirms_only_the_error_that_was_persisted(traced_query, monkeypatch):
    fixture, service = traced_query, traced_query.service

    def fail_finish(*args):
        raise sqlite3.OperationalError("Named persistence fault before finish commits")

    monkeypatch.setattr(service, "finish", fail_finish)

    async def scenario():
        query_id = (await service.create_async(fixture.request))["query_id"]
        await service.tasks[query_id]
        return query_id

    query_id = asyncio.run(scenario())
    trace = assert_confirmed(fixture, query_id, "error")
    assert [row["phase"] for row in trace if row["phase"] in TERMINALS] == ["query.error"]
    assert trace[-1]["data"]["code"] == "query_failed"
    assert {"query.done_intent", "query.error_intent"} <= {row["phase"] for row in trace}


def fail_observer_read(fixture, monkeypatch):
    original = fixture.db.one

    def one(sql, *args):
        if "e.type AS event_type" in sql:
            raise sqlite3.OperationalError("Named final-observer read fault")
        return original(sql, *args)

    monkeypatch.setattr(fixture.db, "one", one)


@pytest.mark.parametrize("observer_read_fails", [False, True])
def test_failed_error_persistence_has_no_false_terminal_and_keeps_primary_error(traced_query, monkeypatch, observer_read_fails):
    fixture, service = traced_query, traced_query.service
    primary = sqlite3.OperationalError("Named terminal persistence failure")

    def fail_finish(*args):
        raise sqlite3.OperationalError("Named finish failure")

    def fail_error(*args):
        raise primary

    monkeypatch.setattr(service, "finish", fail_finish)
    monkeypatch.setattr(service, "fail", fail_error)
    if observer_read_fails:
        fail_observer_read(fixture, monkeypatch)

    async def scenario():
        query_id = (await service.create_async(fixture.request))["query_id"]
        with pytest.raises(sqlite3.OperationalError) as caught:
            await service.tasks[query_id]
        assert caught.value is primary
        return query_id

    run, events, trace = observed(fixture, asyncio.run(scenario()))
    assert run["state"] == "running" and not events
    assert not any(row["phase"] in TERMINALS for row in trace)
    assert trace[-1]["phase"] == "query.persistence_unconfirmed"
    assert trace[-1]["data"]["persistence_confirmed"] is False
    assert trace[-1]["data"]["reason"] == ("terminal_read_failed" if observer_read_fails else "terminal_state_event_mismatch")


def test_observation_read_failure_leaves_the_committed_success_unchanged(traced_query, monkeypatch):
    fixture, service = traced_query, traced_query.service
    fail_observer_read(fixture, monkeypatch)

    async def scenario():
        query_id = (await service.create_async(fixture.request))["query_id"]
        await service.tasks[query_id]
        return query_id

    run, events, trace = observed(fixture, asyncio.run(scenario()))
    assert run["state"] == "done" and [event["type"] for event in events] == ["done"]
    assert not any(row["phase"] in TERMINALS for row in trace)
    assert trace[-1]["phase"] == "query.persistence_unconfirmed"
    assert trace[-1]["data"]["reason"] == "terminal_read_failed"


@pytest.mark.parametrize("defect", ["missing_event", "wrong_event_type", "wrong_payload_state"])
def test_inconsistent_terminal_records_do_not_claim_confirmation(traced_query, defect):
    fixture, service = traced_query, traced_query.service
    query_id = service.prepare_query(fixture.request)[0]["query_id"]
    service.finish(query_id, "done", "unchanged", [], {}, {"status": "done", "text": "unchanged"})
    if defect == "missing_event":
        fixture.db.execute("DELETE FROM events WHERE query_id=?", (query_id,))
    elif defect == "wrong_event_type":
        fixture.db.execute("UPDATE events SET type='cancelled' WHERE query_id=?", (query_id,))
    else:
        fixture.db.execute("UPDATE events SET data_json=? WHERE query_id=?", ('{"status":"cancelled"}', query_id))
    trace = ExecutionTrace(fixture.settings, query_id)
    service.capture_persisted_terminal(query_id, trace)
    trace.close()
    rows = read_verified_trace(fixture.settings.data_dir / "traces" / (query_id + ".jsonl"))
    assert len(rows) == 1 and rows[0]["phase"] == "query.persistence_unconfirmed"
    assert rows[0]["data"]["persistence_confirmed"] is False


def test_terminal_trace_quota_failure_does_not_change_committed_state(traced_query, monkeypatch):
    fixture, service = traced_query, traced_query.service
    original = service.capture_persisted_terminal
    captured = []

    def exhaust_quota(query_id, trace):
        trace.limit = trace.bytes_written
        captured.append(trace)
        return original(query_id, trace)

    monkeypatch.setattr(service, "capture_persisted_terminal", exhaust_quota)

    async def scenario():
        query_id = (await service.create_async(fixture.request))["query_id"]
        await service.tasks[query_id]
        return query_id

    run, events, trace = observed(fixture, asyncio.run(scenario()))
    assert run["state"] == "done" and [event["type"] for event in events] == ["done"]
    assert captured[0].failed == "trace_budget_exceeded"
    assert not any(row["phase"] in TERMINALS for row in trace)
    assert run["metrics"]["execution_trace"]["terminal_captured"] is False


def test_disabled_tracing_does_not_add_a_terminal_database_read(traced_query, monkeypatch):
    fixture, service = traced_query, traced_query.service
    fixture.settings.profile["trace"]["mode"] = "off"

    def forbidden_observer(*args):
        pytest.fail("Trace-off queries must not call the final observer")

    monkeypatch.setattr(service, "capture_persisted_terminal", forbidden_observer)

    async def scenario():
        query_id = (await service.create_async(fixture.request))["query_id"]
        await service.tasks[query_id]
        return query_id

    run = service.run_detail(asyncio.run(scenario()))
    assert run["state"] == "done" and "execution_trace" not in run["metrics"]
