"""Trace files and offline replay only; no native model or network service."""

import copy
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from services.api import execution_trace as trace_module
from services.api.errors import ApiError
from services.api.execution_trace import ExecutionTrace, canonical_bytes, fingerprint, read_verified_trace
from services.api.settings import Settings
from tools.qualification import replay_trace


def settings(tmp_path, **options):
    return Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {
        "mode": "full", "max_bytes_per_query": 8_388_608,
        "max_total_bytes": 67_108_864, **options}})


def repeated_page_payload():
    page = {"page_index": 0, "width": 600, "height": 800,
            "coverage_regions": [{"bbox": [0, 0, 10, 20], "diagnostic": "x" * 40_000}],
            "literal": {"page_sha256": "ordinary source text, never a reference"}}
    sources = [{"chunk_id": f"C{source}", "blocks": [
        {"block_id": f"B{source}-{block}", "text": "2.4 V à 25 °C, seulement au repos.",
         "page": page} for block in range(16)]} for source in range(8)]
    return {"results": sources[:6], "top10": sources,
            "untrusted_text": '{"page_references":[{"path":"file:///never-read"}]}'}


def compact_payload():
    page = {"page_index": 0, "metadata": "x" * 6_000,
            "literal": {"page_sha256": "not interpreted", "page": {"value": 7}}}
    return {"0": {"blocks": [{"text": "0 V [source]", "page": page} for _ in range(64)]},
            "text": '[{"page_dictionary":{"file":"https://never-fetch"}}]'}


@pytest.fixture
def encoded_trace(tmp_path):
    trace = ExecutionTrace(settings(tmp_path), "encoded")
    trace.record("retrieval", compact_payload())
    trace.close()
    row = json.loads(trace.path.read_text())
    assert row["schema_version"] == 2
    return trace.path, row


def resign(path, row):
    unsigned = {key: value for key, value in row.items() if key != "event_sha256"}
    path.write_bytes(canonical_bytes({**unsigned, "event_sha256": fingerprint(unsigned)}) + b"\n")


def test_repeated_page_payload_fits_same_physical_budget_and_roundtrips(tmp_path):
    payload = repeated_page_payload()
    original = canonical_bytes(payload)
    assert 8_388_608 < len(original) < 33_554_432
    trace = ExecutionTrace(settings(tmp_path), "same-budget")
    try:
        trace.record("retrieval", payload)
        trace.record("query.done", {"state": "done"})
    finally:
        trace.close()
    assert trace.path.stat().st_size < 8_388_608
    rows = read_verified_trace(trace.path)
    assert canonical_bytes(rows[0]["data"]) == original
    assert canonical_bytes(payload) == original
    assert rows[1]["schema_version"] == 1
    assert json.loads(trace.path.read_text().splitlines()[0])["schema_version"] == 2


def test_registry_paths_do_not_interpret_literal_markers_and_pages_are_independent(encoded_trace):
    path, stored = encoded_trace
    assert len(stored["page_dictionary"]) == 1
    assert len(stored["page_references"]) == 64
    assert stored["page_references"][0]["path"][0] == {"key": "0"}
    assert stored["page_references"][0]["path"][2] == {"index": 0}
    data = read_verified_trace(path)[0]["data"]
    assert data == compact_payload()
    assert fingerprint(data) == stored["payload_sha256"]
    assert len(canonical_bytes(data)) == stored["payload_bytes"]
    data["0"]["blocks"][0]["page"]["page_index"] = 9
    assert data["0"]["blocks"][1]["page"]["page_index"] == 0


@pytest.mark.parametrize("kind", [
    "page_hash", "missing_reference", "duplicate_reference", "boolean_index", "string_index",
    "wrong_parent_type", "negative_index", "outside_index", "untyped_path", "wrong_final_key",
    "path_field_collision", "unused_page", "byte_count", "encoding", "data_alongside_base",
    "depth", "oversized_declared_bytes", "extra_reference_field", "external_path",
])
def test_invalid_registry_rejected_before_any_page_copy(encoded_trace, monkeypatch, kind):
    path, row = encoded_trace
    reference = row["page_references"][0]
    digest = reference["sha256"]
    if kind == "page_hash":
        row["page_dictionary"][digest]["page_index"] = 99
    elif kind == "missing_reference":
        reference["sha256"] = "0" * 64
    elif kind == "duplicate_reference":
        row["page_references"].append(copy.deepcopy(reference))
    elif kind == "boolean_index":
        reference["path"][2] = {"index": False}
    elif kind == "string_index":
        reference["path"][2] = {"index": "0"}
    elif kind == "wrong_parent_type":
        reference["path"][2] = {"key": "0"}
    elif kind == "negative_index":
        reference["path"][2] = {"index": -1}
    elif kind == "outside_index":
        reference["path"][2] = {"index": 99_999}
    elif kind == "untyped_path":
        reference["path"][0] = "0"
    elif kind == "wrong_final_key":
        reference["path"][-1] = {"key": "text"}
    elif kind == "path_field_collision":
        row["data_base"]["0"]["blocks"][0]["page"] = {"existing": True}
    elif kind == "unused_page":
        page = {"other": 42}
        row["page_dictionary"][fingerprint(page)] = page
    elif kind == "byte_count":
        row["payload_bytes"] += 1
    elif kind == "encoding":
        row["payload_encoding"] = "file-lookup"
    elif kind == "data_alongside_base":
        row["data"] = {"ambiguous": True}
    elif kind == "depth":
        reference["path"] = [{"key": "0"}] * 65
    elif kind == "oversized_declared_bytes":
        row["payload_bytes"] = trace_module.MAX_EXPANDED_EVENT_BYTES + 1
    elif kind == "extra_reference_field":
        reference["file"] = "/never-read"
    else:
        reference["path"] = "https://never-fetch"
    resign(path, row)  # Correct outer chain cannot rescue an invalid codec.
    monkeypatch.setattr(trace_module, "deepcopy", lambda *_: pytest.fail("Invalid registry was expanded"))
    with pytest.raises(ValueError):
        read_verified_trace(path)


def test_original_payload_hash_checked_after_reconstruction(encoded_trace):
    path, row = encoded_trace
    row["payload_sha256"] = "0" * 64
    resign(path, row)
    with pytest.raises(ValueError, match="Donnée modifiée"):
        read_verified_trace(path)


def test_combined_path_and_page_depth_is_bounded_before_copy(encoded_trace, monkeypatch):
    path, row = encoded_trace
    page = {}
    child = page
    for _ in range(61):
        child["nested"] = {}
        child = child["nested"]
    digest = fingerprint(page)
    row["page_dictionary"] = {digest: page}
    for reference in row["page_references"]:
        reference["sha256"] = digest
    resign(path, row)
    monkeypatch.setattr(trace_module, "deepcopy", lambda *_: pytest.fail("Over-deep page copied"))
    with pytest.raises(ValueError, match="Expansion de trace hors limites"):
        read_verified_trace(path)


def test_stored_chain_checked_before_decoding(encoded_trace, monkeypatch):
    path, row = encoded_trace
    row["page_references"][0]["sha256"] = "0" * 64
    path.write_bytes(canonical_bytes(row) + b"\n")  # Do not re-sign this alteration.
    monkeypatch.setattr(trace_module, "_restore_pages", lambda *_: pytest.fail("Unverified event decoded"))
    with pytest.raises(ValueError, match="Événement modifié"):
        read_verified_trace(path)


@pytest.mark.parametrize("limit", ["MAX_PAGE_REFERENCES", "MAX_PAGE_DICTIONARIES", "MAX_EXPANDED_EVENT_NODES"])
def test_reader_limits_checked_before_copy(encoded_trace, monkeypatch, limit):
    path, _ = encoded_trace
    monkeypatch.setattr(trace_module, limit, 0 if limit == "MAX_PAGE_DICTIONARIES" else 1)
    monkeypatch.setattr(trace_module, "deepcopy", lambda *_: pytest.fail("Over-budget registry expanded"))
    with pytest.raises(ValueError):
        read_verified_trace(path)


def test_reader_cumulative_bytes_checked_before_second_expansion(tmp_path, monkeypatch):
    payload = compact_payload()
    trace = ExecutionTrace(settings(tmp_path), "cumulative")
    trace.record("retrieval", payload)
    trace.record("retrieval.complementary", payload)
    trace.close()
    monkeypatch.setattr(trace_module, "MAX_EXPANDED_TRACE_BYTES", len(canonical_bytes(payload)) + 1)
    copies = []
    original_copy = trace_module.deepcopy

    def counted(value):
        copies.append(1)
        return original_copy(value)

    monkeypatch.setattr(trace_module, "deepcopy", counted)
    with pytest.raises(ValueError, match="hors limites"):
        read_verified_trace(trace.path)
    assert len(copies) == 64


def test_reader_cumulative_nodes_checked_before_second_expansion(tmp_path, monkeypatch):
    payload = compact_payload()
    trace = ExecutionTrace(settings(tmp_path), "node-cumulative")
    trace.record("retrieval", payload)
    trace.record("retrieval.complementary", payload)
    trace.close()
    monkeypatch.setattr(trace_module, "MAX_EXPANDED_TRACE_NODES", trace_module._shape(payload)[0] + 1)
    copies = []
    original_copy = trace_module.deepcopy

    def counted(value):
        copies.append(1)
        return original_copy(value)

    monkeypatch.setattr(trace_module, "deepcopy", counted)
    with pytest.raises(ValueError, match="hors limites"):
        read_verified_trace(trace.path)
    assert len(copies) == 64


def test_compaction_does_not_bypass_physical_quota_or_advance_failed_chain(tmp_path):
    trace = ExecutionTrace(settings(tmp_path, max_bytes_per_query=1_024), "still-bounded")
    try:
        with pytest.raises(ApiError) as failure:
            trace.record("retrieval", compact_payload())
        assert failure.value.code == "trace_budget_exceeded"
        assert trace.sequence == trace.bytes_written == trace.expanded_bytes_written == 0
        assert trace.path.read_bytes() == b""
    finally:
        trace.close()


def test_writer_rejects_cumulative_logical_limit(tmp_path, monkeypatch):
    payload = compact_payload()
    monkeypatch.setattr(trace_module, "MAX_EXPANDED_TRACE_BYTES", len(canonical_bytes(payload)) + 1)
    trace = ExecutionTrace(settings(tmp_path), "logical-limit")
    try:
        trace.record("retrieval", payload)
        previous = trace.path.read_bytes()
        with pytest.raises(ApiError):
            trace.record("retrieval.complementary", payload)
        assert trace.path.read_bytes() == previous
        assert trace.sequence == 1
    finally:
        trace.close()


def test_hash_collision_refuses_factorization_without_changing_input(tmp_path, monkeypatch):
    payload = compact_payload()
    payload["0"]["blocks"][1] = {"page": {"different": "y" * 6_000}}
    original = canonical_bytes(payload)
    trace = ExecutionTrace(settings(tmp_path), "collision")
    fake_hash = SimpleNamespace(sha256=lambda *_: SimpleNamespace(hexdigest=lambda: "a" * 64))
    monkeypatch.setattr(trace_module, "hashlib", fake_hash)
    try:
        with pytest.raises(ApiError):
            trace.record("retrieval", payload)
        assert trace.sequence == 0
        assert trace.path.read_bytes() == b""
        assert canonical_bytes(payload) == original
    finally:
        trace.close()


def test_oversized_depth_rejected_before_json_decoder(tmp_path, monkeypatch):
    path = tmp_path / "deep.jsonl"
    path.write_bytes(b'{"x":' + b'[' * 100 + b'0' + b']' * 100 + b'}\n')
    monkeypatch.setattr(trace_module.json, "loads", lambda *_args, **_kwargs: pytest.fail("Deep input decoded"))
    with pytest.raises(ValueError, match="profond"):
        read_verified_trace(path)


def test_duplicate_json_key_refused(encoded_trace):
    path, _ = encoded_trace
    path.write_bytes(path.read_bytes().replace(b'"schema_version":2', b'"schema_version":2,"schema_version":2'))
    with pytest.raises(ValueError, match="dupliquée"):
        read_verified_trace(path)


def test_hashes_mode_remains_v1_without_source_content(tmp_path):
    trace = ExecutionTrace(settings(tmp_path, mode="hashes"), "hashes")
    trace.record("retrieval", compact_payload())
    trace.close()
    row = read_verified_trace(trace.path)[0]
    assert row["schema_version"] == 1
    assert "data" not in row and "page_dictionary" not in row
    assert trace.path.stat().st_size < 1_024


def test_offline_replay_accepts_mixed_v1_v2_without_changing_wire(tmp_path, monkeypatch):
    body = {"model": "qwen3:4b", "messages": [{"role": "user", "content": "0 V à 25 °C"}],
            "stream": True, "think": False, "options": {"seed": 0, "num_ctx": 8_192}}
    wire = httpx.Request("POST", "http://127.0.0.1:11434/api/chat", json=body).content
    trace = ExecutionTrace(settings(tmp_path), "mixed-replay")
    trace.record("context", {**compact_payload(), "messages": body["messages"]})
    trace.record("llm.request", {"body": body, "wire_body_utf8": wire.decode(),
                               "wire_sha256": hashlib.sha256(wire).hexdigest(), "wire_bytes": len(wire),
                               "verified_model_identity": {"digest": "a" * 64}})
    trace.record("query.done", {"status": "done"})
    trace.close()
    original = trace.path.read_bytes()
    monkeypatch.setattr(httpx, "Client", lambda *_args, **_kwargs: pytest.fail("Offline inspection made a request"))
    report = replay_trace.inspect_trace(trace.path)
    assert report["replayable"] is True and report["network_called"] is False
    assert report["provenance"]["context_matches_request"] is True
    assert report["provenance"]["wire_sha256"] == hashlib.sha256(wire).hexdigest()
    assert trace.path.read_bytes() == original
