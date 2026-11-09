"""Offline trace and explicitly mocked HTTP transport; no native model inference."""

import base64
import copy
import hashlib
import json
import os

import httpx
import pytest

from services.api.execution_trace import ExecutionTrace, fingerprint, read_verified_trace
from services.api.settings import Settings
from tools.qualification import replay_trace as replay

MODEL = {"name": "qwen3:4b", "digest": "a" * 64, "details": {"parameter_size": "4.0B", "quantization_level": "Q4_K_M"}}


def source_trace(tmp_path, *, mode="full", mutate=None, requests=1, terminal=True):
    settings = Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {"mode": mode}})
    trace = ExecutionTrace(settings, "captured")
    body = {"model": MODEL["name"], "messages": [{"role": "system", "content": "Preuves exactes seulement."},
        {"role": "user", "content": "SECRET-CONTEXT zéro 0 V → 36 V 😀"}],
        "stream": True, "think": False, "keep_alive": "10m",
        "options": {"num_ctx": 8192, "temperature": 0.2, "seed": 0, "num_predict": 100, "num_gpu": 0},
        "format": {"type": "object", "required": ["references", "comparisons"], "additionalProperties": False,
            "properties": {"references": {"type": "array", "items": {"enum": ["R001", "R002"]}},
                           "comparisons": {"type": "array"}}}}
    trace.record("context", {"messages": body["messages"], "retained": [{"text": "0 V ; 36 V"}]})
    wire = httpx.Request("POST", "http://127.0.0.1:11434/api/chat", json=body).content
    data = {"body": body, "wire_body_utf8": wire.decode("utf-8"), "wire_sha256": hashlib.sha256(wire).hexdigest(),
        "wire_bytes": len(wire), "verified_model_identity": {"digest": MODEL["digest"], "source": "/api/tags"},
        "server_options_requested": {"kv_cache_type": "f16", "flash_attention": False}, "server_options_verified": False}
    if mutate:
        mutate(data)
    for attempt in range(requests):
        trace.record("llm.request", {**data, "attempt": attempt + 1})
    if terminal:
        trace.record("query.done", {"status": "done"})
    trace.close()
    return trace.path, wire, body


@pytest.fixture
def output(tmp_path, monkeypatch):
    root = tmp_path / "private-qa"
    monkeypatch.setattr(replay, "LOCAL_QA", root)
    return root / "replay.json"


def forbidden(request):
    pytest.fail("No HTTP request may occur in a refused/offline case")


def test_inspection_is_offline_and_hashes_actual_captured_messages(tmp_path, monkeypatch):
    path, wire, body = source_trace(tmp_path)
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: pytest.fail("Inspection is offline"))
    result = replay.inspect_trace(path)
    assert result["network_called"] is False and result["replayable"] is True
    assert result["provenance"]["trace_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["provenance"]["messages_sha256"] == fingerprint(body["messages"])
    assert result["provenance"]["context_matches_request"] is True
    assert result["provenance"]["wire_sha256"] == hashlib.sha256(wire).hexdigest()
    assert "SECRET-CONTEXT" not in json.dumps(result)
    # Trace canonicalization sorts nested objects; this was the actual wire replay trap.
    recorded = next(row["data"]["body"] for row in read_verified_trace(path) if row["phase"] == "llm.request")
    assert httpx.Request("POST", "http://127.0.0.1:1/api/chat", json=recorded).content != wire


class ChunkedNativeStream(httpx.SyncByteStream):
    def __init__(self, raw):
        self.raw = raw

    def __iter__(self):
        for start in range(0, len(self.raw), 13):
            yield self.raw[start:start + 13]


@pytest.mark.parametrize("final_newline", [True, False])
def test_replay_sends_identical_wire_seed_zero_schema_and_preserves_native_output(tmp_path, output, final_newline):
    path, wire, body = source_trace(tmp_path)
    original_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    events = [{"message": {"content": '{"references": ["R001"], '}, "done": False},
              {"message": {"content": '"comparisons": []}'}, "done": False},
              {"message": {"content": ""}, "done": True, "done_reason": "stop", "eval_count": 12,
               "prompt_eval_count": 90, "total_duration": 123000000}]
    raw = "\r\n".join(json.dumps(event) for event in events).encode() + (b"\n" if final_newline else b"")
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [MODEL]})
        assert request.content == wire and request.url.path == "/api/chat"
        assert json.loads(request.content)["options"]["seed"] == 0
        assert json.loads(request.content)["format"] == body["format"]
        return httpx.Response(200, stream=ChunkedNativeStream(raw))

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert seen == [("GET", "/api/tags"), ("POST", "/api/chat")]
    assert result["status"] == "completed" and result["kind"] == "fixed_context_replay"
    assert result["transport_kind"] == "explicit_test_substitute"
    assert result["generation_request_attempted"] and result["generation_response_received"]
    assert result["retrieval_performed"] is False and result["answer_rendering_performed"] is False
    assert result["request"] == body and result["received_done"]
    assert result["response"] == '{"references": ["R001"], "comparisons": []}'
    assert [record["event"] for record in result["native_events"]] == events
    assert result["native_final_event"] == events[-1]
    assert base64.b64decode(result["native_raw"]["base64"]) == raw
    assert result["native_raw"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert json.loads(output.read_text()) == result
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_sha
    if os.name == "posix":
        assert output.stat().st_mode & 0o777 == 0o600


def corrupt(data, kind):
    if kind == "body_missing":
        data.pop("body")
    elif kind == "wire_missing":
        data.pop("wire_body_utf8")
    elif kind == "wire_hash":
        data["wire_sha256"] = "0" * 64
    elif kind == "wire_bytes":
        data["wire_bytes"] += 1
    elif kind == "body_mismatch":
        data["body"] = copy.deepcopy(data["body"])
        data["body"]["options"]["seed"] = False  # Must not equate False with numeric zero.
    elif kind == "missing_digest":
        data["verified_model_identity"] = {}
    else:
        body = json.loads(data["wire_body_utf8"])
        if kind == "model_2b":
            body["model"] = "qwen3.5:2b"
        data["body"] = body
        wire = httpx.Request("POST", "http://127.0.0.1:1/api/chat", json=body).content
        if kind == "encoder_drift":
            wire = b" " + wire
        if kind == "duplicate_key":
            wire = wire[:-1] + b',"model":"qwen3:4b"}'
        data.update(wire_body_utf8=wire.decode(), wire_bytes=len(wire), wire_sha256=hashlib.sha256(wire).hexdigest())


@pytest.mark.parametrize("kind", ["body_missing", "wire_missing", "wire_hash", "wire_bytes", "body_mismatch",
                                  "missing_digest", "encoder_drift", "duplicate_key", "model_2b"])
def test_invalid_captured_request_is_refused_before_network_or_output(tmp_path, output, kind):
    path, _, _ = source_trace(tmp_path, mutate=lambda data: corrupt(data, kind))
    assert replay.inspect_trace(path)["replayable"] is False
    with pytest.raises(ValueError):
        replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(forbidden))
    assert not output.exists()


@pytest.mark.parametrize("options", [{"mode": "hashes"}, {"requests": 0}, {"requests": 0, "terminal": False}])
def test_hashes_or_partial_trace_without_request_cannot_be_replayed(tmp_path, output, options):
    path, _, _ = source_trace(tmp_path, **options)
    assert replay.inspect_trace(path)["replayable"] is False
    with pytest.raises(ValueError):
        replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(forbidden))


def test_partial_terminal_is_named_and_multiple_requests_require_explicit_selection(tmp_path):
    path, _, _ = source_trace(tmp_path, requests=2, terminal=False)
    assert replay.inspect_trace(path)["replayable"] is False
    selected = replay.inspect_trace(path, request_sequence=3)
    assert selected["replayable"] is True
    assert selected["provenance"]["request_sequence"] == 3
    assert selected["provenance"]["trace_terminal_captured"] is False
    assert selected["provenance"]["trace_terminal_phase"] is None
    assert replay.inspect_trace(path, request_sequence=99)["replayable"] is False


def test_trace_tampering_and_interrupted_last_event_are_rejected(tmp_path):
    path, _, _ = source_trace(tmp_path)
    original = path.read_bytes()
    path.write_bytes(original.replace(b"36 V", b"99 V"))
    with pytest.raises(ValueError):
        replay.inspect_trace(path)
    path.write_bytes(original[:-1])
    with pytest.raises(ValueError):
        replay.inspect_trace(path)


@pytest.mark.parametrize("origin", ["https://127.0.0.1:11434", "http://192.0.2.1:11434", "http://127.0.0.1",
    "http://user:password@127.0.0.1:11434", "http://127.0.0.1:11434/prefix", "http://127.0.0.1:11434?extra=1"])
def test_non_loopback_or_non_origin_endpoints_are_refused_before_http(tmp_path, output, origin):
    path, _, _ = source_trace(tmp_path)
    with pytest.raises(ValueError):
        replay.replay_trace(path, output, origin, transport=httpx.MockTransport(forbidden))
    assert not output.exists()


@pytest.mark.parametrize("inventory", [[], [{**MODEL, "digest": "b" * 64}], [MODEL, MODEL]])
def test_exact_model_digest_is_required_before_context_transmission(tmp_path, output, inventory):
    path, _, _ = source_trace(tmp_path)
    seen = []

    def handler(request):
        seen.append(request.url.path)
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": inventory})

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert seen == ["/api/tags"] and result["status"] == "error"
    assert result["generation_request_attempted"] is False and result["generation_response_received"] is False
    assert result["native_raw"]["bytes"] == 0 and output.exists()


def test_redirect_is_not_followed_or_given_documentary_context(tmp_path, output):
    path, _, _ = source_trace(tmp_path)
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(307, headers={"Location": "http://example.invalid/exfil"})

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert seen == ["http://127.0.0.1:11434/api/tags"]
    assert result["status"] == "error" and not result["generation_request_attempted"]


def test_output_never_overwrites_existing_evidence_or_follows_symlink(tmp_path, output):
    path, _, _ = source_trace(tmp_path)
    output.parent.mkdir()
    output.write_text("KEEP ORIGINAL")
    with pytest.raises(ValueError, match="existante"):
        replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(forbidden))
    assert output.read_text() == "KEEP ORIGINAL"
    link = output.parent / "link.json"
    link.symlink_to(output)
    with pytest.raises(ValueError):
        replay.replay_trace(path, link, "http://127.0.0.1:11434", transport=httpx.MockTransport(forbidden))
    assert output.read_text() == "KEEP ORIGINAL"


@pytest.mark.parametrize("raw", [b'{"message":{"content":"partial"},"done":false}\n', b'{"error":"runtime failed"}\n',
    b'{not valid JSON}\n', b'{"message":{"thinking":"forbidden"},"done":true}\n',
    b'{"message":{"tool_calls":[{}]},"done":true}\n'])
def test_native_errors_preserve_raw_evidence_without_claiming_complete_response(tmp_path, output, raw):
    path, _, _ = source_trace(tmp_path)

    def handler(request):
        return httpx.Response(200, json={"models": [MODEL]}) if request.url.path == "/api/tags" else httpx.Response(200, content=raw)

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert result["status"] == "error" and result["received_done"] is False
    assert base64.b64decode(result["native_raw"]["base64"]) == raw
    assert json.loads(output.read_text())["status"] == "error"


def test_capture_size_limit_is_explicit_and_raw_prefix_is_retained(tmp_path, output):
    path, _, _ = source_trace(tmp_path)
    raw = json.dumps({"message": {"content": "x" * 1000}, "done": True}).encode()

    def handler(request):
        return httpx.Response(200, json={"models": [MODEL]}) if request.url.path == "/api/tags" else httpx.Response(200, content=raw)

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler), maximum_response_bytes=64)
    assert result["status"] == "error" and result["response_capture_limit_reached"]
    assert result["native_raw"]["bytes"] == 64
    assert base64.b64decode(result["native_raw"]["base64"]) == raw[:64]


def test_http_error_preserves_native_response_body(tmp_path, output):
    path, _, _ = source_trace(tmp_path)
    raw = b'{"error":"test-only native failure details"}'

    def handler(request):
        return httpx.Response(200, json={"models": [MODEL]}) if request.url.path == "/api/tags" else httpx.Response(500, content=raw)

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert result["status"] == "error" and result["http_status"] == 500
    assert base64.b64decode(result["native_raw"]["base64"]) == raw
    assert result["client_generation_elapsed_ms"] is not None


@pytest.mark.parametrize("size", ["4.0B", "8.0B"])
def test_enhanced_alias_is_read_from_four_b_lock_without_option_overrides(tmp_path, output, monkeypatch, size):
    lock = json.loads(replay.ENHANCED_LOCK.read_bytes())
    assert lock["model"] == "qwen3-4b-enhanced:q4km"
    lock["parameter_size"] = size
    lock_path = tmp_path / "enhanced.lock.json"
    lock_path.write_text(json.dumps(lock))
    monkeypatch.setattr(replay, "ENHANCED_LOCK", lock_path)

    def enhanced(data):
        body = copy.deepcopy(data["body"])
        body["model"] = lock["model"]
        wire = httpx.Request("POST", "http://127.0.0.1:11434/api/chat", json=body).content
        data.update(body=body, wire_body_utf8=wire.decode(), wire_sha256=hashlib.sha256(wire).hexdigest(), wire_bytes=len(wire))

    path, _, _ = source_trace(tmp_path, mutate=enhanced)
    if size != "4.0B":
        with pytest.raises(ValueError):
            replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(forbidden))
        return

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{**MODEL, "name": lock["model"]}]})
        body = json.loads(request.content)
        assert body["model"] == lock["model"] and body["options"]["seed"] == 0
        return httpx.Response(200, json={"message": {"content": ""}, "done": True, "done_reason": "stop"})

    result = replay.replay_trace(path, output, "http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    assert result["status"] == "completed"
    assert result["provenance"]["model_lock"]["sha256"] == hashlib.sha256(lock_path.read_bytes()).hexdigest()
