"""Real QueryService, OOXML, SQLite and trace files; no native inference.

Embedding, vector transport and token counting use the named doubles from the
Office fixture. The selector double below emits only allowed reference IDs.
"""

import asyncio
import hashlib
import json

import pytest
from test_office_rag import rag as rag
from test_query_trace_terminal import traced_query as traced_query

from services.api.execution_trace import ExecutionTrace, fingerprint, read_verified_trace
from services.api.structured_answer import Catalogue, digest

PHASE = "answer.rendered_support_ledger"


def run_query(fixture):
    async def scenario():
        query_id = (await fixture.service.create_async(fixture.request))["query_id"]
        await fixture.service.tasks[query_id]
        return query_id

    query_id = asyncio.run(scenario())
    run = fixture.service.run_detail(query_id)
    events = fixture.db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))
    path = fixture.settings.data_dir / "traces" / (query_id + ".jsonl")
    return run, events, path


class AllowedReferenceSelectorDouble:
    calls = 0

    async def stream(self, messages, cancelled, output_tokens, *, response_format):
        self.calls += 1
        ids = response_format["properties"]["references"]["items"]["enum"]
        yield {"type": "delta", "text": json.dumps({"references": ids, "comparisons": []})}
        yield {"type": "done", "finish_reason": "stop", "metrics": {"eval_count": 1}}


@pytest.mark.parametrize("selector", [False, True])
def test_rendered_ledger_is_captured_after_verification_with_final_text(traced_query, monkeypatch, selector):
    fixture = traced_query
    if selector:
        monkeypatch.setattr(Catalogue, "deterministic_plan", lambda self, required_documents=(): None)
        fixture.gateway = AllowedReferenceSelectorDouble()
        fixture.service.ollama = fixture.gateway
    run, events, path = run_query(fixture)
    assert run["state"] == "done"
    assert fixture.gateway.calls == int(selector)
    rows = read_verified_trace(path)
    captures = [row for row in rows if row["phase"] == PHASE]
    assert len(captures) == 1
    captured = captures[0]["data"]
    initial = next(row["data"] for row in rows if row["phase"] == "evidence.ledger")
    validation = next(row for row in rows if row["phase"] == "answer.support_validation")
    terminal = next(row for row in rows if row["phase"] == "query.done")
    assert validation["sequence"] < captures[0]["sequence"] < terminal["sequence"]
    assert captured["validation"] == validation["data"]
    assert captured["validation"]["status"] == "passed"
    assert captured["validation"]["general_semantic_entailment_verified"] is False
    assert captured["text"] == run["answer"] == terminal["data"]["text"]
    assert captured["answer_sha256"] == hashlib.sha256(run["answer"].encode()).hexdigest()
    assert captured["ledger"]["answer_sha256"] == captured["answer_sha256"]
    assert captured["catalogue_sha256"] == run["metrics"]["structured_answer"]["catalogue_sha256"]
    assert captured["ledger"]["catalogue_sha256"] == captured["catalogue_sha256"]
    assert captured["sha256"] == digest(captured["ledger"])
    assert captured["sha256"] == terminal["data"]["structured_answer"]["rendered_support_ledger_sha256"]
    assert initial["sha256"] == terminal["data"]["structured_answer"]["support_ledger_sha256"]
    assert initial["sha256"] != captured["sha256"]
    segments = captured["ledger"]["segments"]
    assert segments and captured["validation"]["segments_checked"] == len(segments)
    assert all(captured["text"][segment["start_offset"]:segment["end_offset"]] for segment in segments)
    assert "OUTSIDE-SECRET" not in json.dumps(captured)
    # The new payload is private trace data; no new public/event-store payload.
    assert not any(event["type"] == PHASE for event in events)
    assert "ledger" not in terminal["data"]["structured_answer"]
    assert "ledger" not in run["metrics"]


@pytest.mark.parametrize("mode", ["hashes", "off"])
def test_trace_modes_keep_documentary_payload_private(traced_query, monkeypatch, mode):
    fixture = traced_query
    fixture.settings.profile["trace"]["mode"] = mode
    original = ExecutionTrace.record
    observed = []

    def capture(self, phase, data, *, required=True):
        if phase == PHASE:
            observed.append({"sha256": fingerprint(data), "text": data["text"]})
        return original(self, phase, data, required=required)

    monkeypatch.setattr(ExecutionTrace, "record", capture)
    run, _, path = run_query(fixture)
    assert run["state"] == "done"
    if mode == "off":
        assert not path.exists()
        return
    rows = read_verified_trace(path)
    ledger_event = next(row for row in rows if row["phase"] == PHASE)
    assert len(observed) == 1
    assert ledger_event["payload_sha256"] == observed[0]["sha256"]
    assert all("data" not in row for row in rows)
    assert run["answer"] not in path.read_text()
    assert "start_offset" not in path.read_text()


@pytest.mark.parametrize("tamper", ["answer", "offset", "catalogue", "ledger_hash"])
def test_invalid_rendering_cannot_leave_a_certified_rendered_ledger(traced_query, monkeypatch, tamper):
    original = Catalogue.render

    def damaged(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if tamper == "answer":
            result["text"] += " Unsupported addition."
        elif tamper == "offset":
            result["support_ledger"]["segments"][0]["start_offset"] += 1
            result["support_ledger_sha256"] = digest(result["support_ledger"])
        elif tamper == "catalogue":
            result["support_ledger"]["catalogue_sha256"] = "0" * 64
            result["support_ledger_sha256"] = digest(result["support_ledger"])
        else:
            result["support_ledger_sha256"] = "0" * 64
        return result

    monkeypatch.setattr(Catalogue, "render", damaged)
    run, events, path = run_query(traced_query)
    assert run["state"] == "error" and not run["answer"]
    assert not any(event["type"] == "delta" for event in events)
    rows = read_verified_trace(path)
    assert not any(row["phase"] == PHASE for row in rows)
    assert rows[-1]["phase"] == "query.error"
    assert rows[-1]["data"]["code"] == "structured_answer_support_invalid"


def test_a_missing_source_answer_has_no_rendered_ledger(traced_query):
    fixture = traced_query
    fixture.request = fixture.request.model_copy(update={
        "scope": fixture.request.scope.model_copy(update={"rowStart": 100, "rowEnd": 101}),
    })
    run, _, path = run_query(fixture)
    assert run["state"] == "done" and fixture.gateway.calls == 0
    assert run["metrics"]["model_called"] is False
    assert "ne suffisent pas" in run["answer"]
    assert not any(row["phase"] == PHASE for row in read_verified_trace(path))


def test_disabled_support_check_cannot_be_recorded_as_a_verified_rendering(traced_query, monkeypatch):
    original = Catalogue.verify_rendered

    def disabled(self, rendered):
        return {**original(self, rendered), "status": "disabled"}

    monkeypatch.setattr(Catalogue, "verify_rendered", disabled)
    run, events, path = run_query(traced_query)
    assert run["state"] == "error" and not run["answer"]
    assert not any(event["type"] == "delta" for event in events)
    rows = read_verified_trace(path)
    assert next(row["data"] for row in rows if row["phase"] == "answer.support_validation")["status"] == "disabled"
    assert not any(row["phase"] == PHASE for row in rows)
    assert rows[-1]["data"]["code"] == "structured_answer_support_invalid"


def test_rendered_ledger_capture_keeps_the_trace_budget_fail_closed(traced_query, monkeypatch):
    original = ExecutionTrace.record

    def exhaust_after_validation(self, phase, data, *, required=True):
        result = original(self, phase, data, required=required)
        if phase == "answer.support_validation":
            self.limit = self.bytes_written
        return result

    monkeypatch.setattr(ExecutionTrace, "record", exhaust_after_validation)
    run, events, path = run_query(traced_query)
    assert run["state"] == "error" and not run["answer"]
    assert run["metrics"]["execution_trace"]["failure"] == "trace_budget_exceeded"
    assert not any(event["type"] == "delta" for event in events)
    assert json.loads(next(event["data_json"] for event in events if event["type"] == "error"))["code"] == "trace_budget_exceeded"
    assert not any(row["phase"] == PHASE for row in read_verified_trace(path))
