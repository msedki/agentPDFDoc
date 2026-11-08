"""Inspect a captured execution offline, or replay its exact 4B request locally.

This is a fixed-context replay: no database, retrieval, tokenizer or answer
renderer is rerun. Native output is preserved separately from answer quality.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.execution_trace import canonical_bytes, fingerprint, read_verified_trace  # noqa: E402
from tools.qualification.api_client import loopback_origin  # noqa: E402
from tools.qualification.evidence_io import LOCAL_QA, checked_output  # noqa: E402

FOUR_B_MODELS = frozenset({"qwen3:4b", "qwen3.5:4b", "qwen3.5:4b-text"})
ENHANCED_LOCK = ROOT / "config" / "enhanced-4b.lock.json"
TERMINALS = frozenset({"query.done", "query.error", "query.cancelled"})
MAX_RESPONSE_BYTES = 4_194_304


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("Nonfinite JSON number")


def _json(text):
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _model_lock(model):
    if model in FOUR_B_MODELS:
        return None
    try:
        raw = ENHANCED_LOCK.read_bytes()
        lock = _json(raw)
        if (lock.get("schema_version") != 1 or lock.get("model") != model
                or lock.get("family") != "qwen3" or lock.get("parameter_size") != "4.0B"
                or lock.get("quantization") != "Q4_K_M"
                or lock.get("gguf", {}).get("filename") != "Qwen3-4B-Q4_K_M.gguf"
                or not re.fullmatch(r"[0-9a-f]{64}", str(lock.get("gguf", {}).get("sha256", "")))):
            raise ValueError("Incompatible 4B lock")
        return {"file": ENHANCED_LOCK.name, "sha256": hashlib.sha256(raw).hexdigest(),
                "model": model, "gguf_sha256": lock["gguf"]["sha256"]}
    except (OSError, ValueError, AttributeError, TypeError) as error:
        raise ValueError("Only historical Qwen 4B models or the exact enhanced 4B lock alias are eligible") from error


def _verified(path: Path):
    # Compare before/after to avoid describing a trace that changed during read.
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 16_777_216:
        raise ValueError("Trace is not regular or exceeds the read byte budget")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        rows = read_verified_trace(path)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed trace event") from error
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != after or not rows or any(row.get("schema_version") != 1 for row in rows):
        raise ValueError("Empty, changed or nonregular trace")
    return rows, after


def _request(rows, sequence=None):
    if any(row.get("capture_mode") != "full" or "data" not in row for row in rows):
        raise ValueError("Full capture is required; hashes-only traces cannot be replayed")
    requests = [row for row in rows if row["phase"] == "llm.request"]
    if sequence is not None:
        requests = [row for row in requests if row["sequence"] == sequence]
    if len(requests) != 1:
        raise ValueError("One captured llm.request is required; select --request-sequence when several exist")
    selected = requests[0]
    data = selected["data"]
    if not isinstance(data, dict) or not isinstance(data.get("body"), dict):
        raise ValueError("Captured request has no complete body")
    wire_text = data.get("wire_body_utf8")
    if not isinstance(wire_text, str):
        raise ValueError("Captured wire_body_utf8 is missing; never reconstruct wire order from sorted trace JSON")
    wire = wire_text.encode("utf-8")
    if (hashlib.sha256(wire).hexdigest() != data.get("wire_sha256")
            or len(wire) != data.get("wire_bytes")):
        raise ValueError("Captured wire hash or length mismatch")
    body = _json(wire_text)  # Original HTTP key order, preserved in the captured string.
    if not isinstance(body, dict) or canonical_bytes(body) != canonical_bytes(data["body"]):
        raise ValueError("Captured body and wire JSON differ")
    _model_lock(body.get("model"))
    if body.get("stream") is not True or body.get("think") is not False:
        raise ValueError("Only the captured non-thinking streaming chat contract is supported")
    if not isinstance(body.get("messages"), list) or not body["messages"]:
        raise ValueError("Captured messages are missing")
    if not isinstance(body.get("options"), dict):
        raise ValueError("Captured native options are missing")
    identity = data.get("verified_model_identity")
    if not isinstance(identity, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(identity.get("digest", ""))):
        raise ValueError("Captured exact model digest is missing")
    # Detect HTTPX encoder/version drift before even reading the local runtime.
    encoded = httpx.Request("POST", "http://127.0.0.1:11434/api/chat", json=body).content
    if encoded != wire:
        raise ValueError("Current HTTPX serialization differs from the captured request bytes")
    return selected, body, wire


def _provenance(rows, source_sha, selected, body):
    previous_context = next((row for row in reversed(rows[:selected["sequence"] - 1])
        if row["phase"] == "context"), None)
    messages_sha = fingerprint(body["messages"])
    context_matches = (isinstance(previous_context, dict)
        and isinstance(previous_context.get("data"), dict)
        and fingerprint(previous_context["data"].get("messages")) == messages_sha)
    terminal = next((row["phase"] for row in reversed(rows) if row["phase"] in TERMINALS), None)
    return {"trace_sha256": source_sha, "trace_last_event_sha256": rows[-1]["event_sha256"],
        "trace_terminal_phase": terminal, "trace_terminal_captured": terminal is not None,
        "request_sequence": selected["sequence"], "request_event_sha256": selected["event_sha256"],
        "request_payload_sha256": selected["payload_sha256"], "body_sha256": fingerprint(body),
        "messages_sha256": messages_sha, "messages_hash_encoding": "canonical_json_utf8",
        "model_lock": _model_lock(body["model"]),
        "context_event_sha256": previous_context["event_sha256"] if context_matches and previous_context is not None else None,
        "context_payload_sha256": previous_context["payload_sha256"] if context_matches and previous_context is not None else None,
        "context_matches_request": bool(context_matches),
        "context_proof": "captured_llm_request.messages; no retrieval reconstruction",
        "response_format_sha256": fingerprint(body["format"]) if "format" in body else None,
        "wire_sha256": selected["data"]["wire_sha256"], "wire_bytes": len(selected["data"]["wire_body_utf8"].encode("utf-8"))}


def inspect_trace(path: Path, request_sequence: int | None = None) -> dict:
    """Offline metadata only; never emits source text or performs HTTP calls."""
    rows, source_sha = _verified(Path(path))
    result: dict[str, Any] = {"kind": "offline_trace_inspection", "trace_sha256": source_sha,
        "events": len(rows), "phases": [row["phase"] for row in rows],
        "requests": [{"sequence": row["sequence"], "event_sha256": row["event_sha256"]}
                     for row in rows if row["phase"] == "llm.request"],
        "network_called": False, "replayable": False}
    try:
        selected, body, _ = _request(rows, request_sequence)
        result.update(replayable=True, provenance=_provenance(rows, source_sha, selected, body))
    except ValueError as error:
        result["reason"] = str(error)
    return result


def _verify_runtime(client, body, captured_identity):
    response = client.get("/api/tags")
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ValueError("Local model inventory is not verifiable")
    matches = [row for row in models if isinstance(row, dict) and row.get("name", row.get("model")) == body["model"]]
    if len(matches) != 1 or matches[0].get("digest") != captured_identity["digest"]:
        raise ValueError("Local model digest differs from the captured exact model identity")
    return {"source": "/api/tags", "model": body["model"], "digest": matches[0]["digest"],
            "model_record": matches[0], "captured_identity": captured_identity}


def _consume(response, report, raw, *, started, maximum_bytes):
    if not response.is_success:
        for chunk in response.iter_bytes():
            raw.extend(chunk[:maximum_bytes - len(raw)])
            if len(raw) >= maximum_bytes:
                report["response_capture_limit_reached"] = True
                break
    response.raise_for_status()
    buffer = b""
    parts = []

    def consume_line(line):
        if not line.strip():
            return False
        event = _json(line.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("Native event is not a JSON object")
        report["native_events"].append({"event": event, "client_ms": round((time.monotonic() - started) * 1000, 3)})
        if event.get("error"):
            raise ValueError("Native runtime returned an error event")
        message = event.get("message", {})
        if not isinstance(message, dict) or message.get("tool_calls") or message.get("thinking"):
            raise ValueError("Native event violates the non-thinking chat contract")
        content = message.get("content", "")
        if not isinstance(content, str):
            raise ValueError("Native content is not text")
        if content:
            if report["client_first_content_ms"] is None:
                report["client_first_content_ms"] = round((time.monotonic() - started) * 1000, 3)
            parts.append(content)
            report["response"] = "".join(parts)
        if event.get("done") is True:
            report["native_final_event"] = event
            report["finish_reason"] = event.get("done_reason", "unknown")
            report["received_done"] = True
            return True
        return False

    for chunk in response.iter_bytes():
        if len(raw) + len(chunk) > maximum_bytes:
            raw.extend(chunk[:maximum_bytes - len(raw)])
            report["response_capture_limit_reached"] = True
            raise ValueError("Native response exceeded the explicit capture byte budget")
        raw.extend(chunk)
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if consume_line(line):
                return
    # aiter_lines in the application also accepts a complete last JSON event
    # terminated by EOF. Its exact absence of newline remains in native_raw.
    if buffer and consume_line(buffer):
        return
    raise ValueError("Native stream ended without a complete done event")


def replay_trace(path: Path, output: Path, base_url: str, *, request_sequence: int | None = None,
                 transport: httpx.BaseTransport | None = None, read_timeout: float = 300.0,
                 maximum_response_bytes: int = MAX_RESPONSE_BYTES) -> dict:
    """One native call, exact captured wire, exclusive private report; no retries."""
    if not 0 < read_timeout <= 3600 or not 0 < maximum_response_bytes <= 16_777_216:
        raise ValueError("Replay timeout or capture budget is out of bounds")
    origin = loopback_origin(base_url)
    path = Path(path)
    rows, source_sha = _verified(path)
    selected, body, wire = _request(rows, request_sequence)
    output = checked_output(Path(output), [LOCAL_QA], sources=(path,))
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    report: dict[str, Any] = {"kind": "fixed_context_replay", "status": "started", "started_utc": datetime.now(UTC).isoformat(),
        "base_url": origin, "provenance": _provenance(rows, source_sha, selected, body),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "httpx_version": httpx.__version__,
        "transport_kind": "explicit_test_substitute" if transport is not None else "native_http",
        "request": body, "generation_request_attempted": False, "generation_response_received": False,
        "retrieval_performed": False, "answer_rendering_performed": False,
        "response": "", "received_done": False, "native_final_event": None, "native_events": [],
        "client_first_content_ms": None, "response_byte_budget": maximum_response_bytes, "response_capture_limit_reached": False,
        "server_options_captured": selected["data"].get("server_options_requested"), "server_options_verified": False,
        "measurement_limit": "Same captured request bytes and model digest; runtime/cache state, server options and output determinism are not established. No full-chain quality or rendered answer is inferred."}
    raw = bytearray()
    started = time.monotonic()
    generation_started = None
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        try:
            with httpx.Client(base_url=origin, trust_env=False, follow_redirects=False, transport=transport,
                              timeout=httpx.Timeout(read_timeout, connect=min(read_timeout, 5))) as client:
                report["verified_model_identity"] = _verify_runtime(client, body, selected["data"]["verified_model_identity"])
                request = client.build_request("POST", "/api/chat", json=body)
                if request.content != wire:
                    raise ValueError("Final HTTPX request bytes differ from captured wire")
                report["generation_request_attempted"] = True
                generation_started = time.monotonic()
                response = client.send(request, stream=True)
                try:
                    report["generation_response_received"] = True
                    report["http_status"] = response.status_code
                    _consume(response, report, raw, started=generation_started, maximum_bytes=maximum_response_bytes)
                finally:
                    response.close()
                report["status"] = "completed"
        except (httpx.HTTPError, ValueError, OSError) as error:
            report["status"] = "error"
            report["error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            report["client_elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            report["client_generation_elapsed_ms"] = (round((time.monotonic() - generation_started) * 1000, 3)
                                                      if generation_started is not None else None)
            report["finished_utc"] = datetime.now(UTC).isoformat()
            report["native_raw"] = {"base64": base64.b64encode(raw).decode("ascii"), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(), "encoding": "http_decoded_body_bytes",
                "capture_until": "first_done_or_error"}
            report["response_sha256"] = hashlib.sha256(report["response"].encode("utf-8")).hexdigest()
            handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--trace", type=Path, required=True)
        command.add_argument("--request-sequence", type=int)
        if name == "replay":
            command.add_argument("--base-url", required=True, help="Existing authorized Ollama loopback origin")
            command.add_argument("--output", type=Path, required=True, help="New private report under .runtime/qa/")
            command.add_argument("--read-timeout", type=float, default=300.0, help="Maximum idle HTTP read in seconds")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(inspect_trace(args.trace, args.request_sequence), ensure_ascii=False, indent=2))
            return 0
        report = replay_trace(args.trace, args.output, args.base_url,
            request_sequence=args.request_sequence, read_timeout=args.read_timeout)
        print(json.dumps({"kind": report["kind"], "status": report["status"], "output": str(args.output),
            "generation_request_attempted": report["generation_request_attempted"], "response_sha256": report["response_sha256"]}))
        return 0 if report["status"] == "completed" else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "refused", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
