"""Contrats d'instrumentation et de résidence ; HTTP/mémoire simulés explicitement."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from services.api.errors import ApiError
from services.api.execution_trace import CURRENT_TRACE, ExecutionTrace, read_verified_trace
from services.api.ollama import OllamaGateway
from services.api.settings import Settings
from services.runtime.profile_schema import ProfileValidationError, validate_profile
from services.runtime.supervisor import environment

ROOT = Path(__file__).resolve().parents[2]


def profile():
    return yaml.safe_load((ROOT / "config/local16-4b.yaml").read_text())


def trace_settings(tmp_path, mode="full", **options):
    return Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {"mode": mode, **options}})


@pytest.mark.parametrize("seed", [0, 42, 4_294_967_295])
def test_seed_reaches_native_options_including_zero(tmp_path, seed):
    p = profile()
    p["llm"]["seed"] = seed
    validate_profile(p, consumer="api")
    gateway = OllamaGateway(Settings(tmp_path, p))
    try:
        assert gateway.chat_options()["seed"] == seed
    finally:
        asyncio.run(gateway.close())


@pytest.mark.parametrize("seed", [-1, 4_294_967_296, True, 1.5, "42"])
def test_invalid_seed_refused(seed):
    p = profile()
    p["llm"]["seed"] = seed
    with pytest.raises(ProfileValidationError):
        validate_profile(p, consumer="api")


def test_kv_options_are_server_options_and_require_flash_attention(tmp_path):
    p = profile()
    p["llm"].update(kv_cache_type="q8_0", flash_attention=False)
    with pytest.raises(ProfileValidationError):
        validate_profile(p, consumer="api")
    p["llm"]["flash_attention"] = True
    validate_profile(p, consumer="api")
    env = environment(p, tmp_path, ROOT / "config/local16-4b.yaml")
    assert env["OLLAMA_KV_CACHE_TYPE"] == "q8_0"
    assert env["OLLAMA_FLASH_ATTENTION"] == "1"
    gateway = OllamaGateway(Settings(tmp_path, p))
    try:
        assert "kv_cache_type" not in gateway.chat_options()
    finally:
        asyncio.run(gateway.close())


def test_trace_retains_exact_payload_and_verifies_chain(tmp_path):
    trace = ExecutionTrace(trace_settings(tmp_path), "query-1")
    payload = {"messages": [{"role": "user", "content": "zéro = 0 V ; borne = 36 V"}], "seed": 0}
    trace.record("llm.request", payload)
    trace.record("query.done", {"status": "done"})
    trace.close()
    rows = read_verified_trace(trace.path)
    assert rows[0]["data"] == payload
    assert [r["phase"] for r in rows] == ["llm.request", "query.done"]
    if os.name == "posix":
        assert trace.path.stat().st_mode & 0o777 == 0o600
        assert trace.path.parent.stat().st_mode & 0o777 == 0o700
    broken = trace.path.read_text().replace("36 V", "99 V")
    trace.path.write_text(broken)
    with pytest.raises(ValueError, match="modifié"):
        read_verified_trace(trace.path)


def test_hash_trace_has_no_document_content_and_off_creates_nothing(tmp_path):
    trace = ExecutionTrace(trace_settings(tmp_path, "hashes"), "q-hashes")
    trace.record("context", {"text": "NE PAS JOURNALISER CE TEXTE"})
    trace.close()
    assert "NE PAS JOURNALISER" not in trace.path.read_text()
    assert "data" not in read_verified_trace(trace.path)[0]
    off = ExecutionTrace(trace_settings(tmp_path, "off"), "q-off")
    off.record("context", {"text": "x"})
    assert off.path is None


def test_trace_refuses_overwrite_truncation_and_quota(tmp_path):
    settings = trace_settings(tmp_path, max_bytes_per_query=4096, max_total_bytes=8192, max_files=1)
    trace = ExecutionTrace(settings, "q")
    trace.record("start", {"x": 1})
    with pytest.raises(ApiError) as failure:
        trace.record("llm.request", {"text": "x" * 4096})
    assert failure.value.code == "trace_budget_exceeded"
    trace.close()
    assert len(read_verified_trace(trace.path)) == 1
    with pytest.raises(ApiError):
        ExecutionTrace(settings, "other")
    trace.path.write_bytes(trace.path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="interrompu"):
        read_verified_trace(trace.path)


def test_trace_refuses_symlink_directory_and_path_escape(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "traces").symlink_to(target, target_is_directory=True)
    with pytest.raises(ApiError):
        ExecutionTrace(trace_settings(tmp_path), "q")
    p = profile()
    p["trace"] = {"directory": "../outside"}
    with pytest.raises(ProfileValidationError):
        validate_profile(p, consumer="api")


def test_gateway_captures_body_actually_received_by_http_transport(tmp_path):
    received = []
    model = {"name": "qwen3:4b", "digest": "a" * 64, "details": {"quantization_level": "Q4_K_M"}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"model": model}))
    settings = trace_settings(tmp_path)
    settings.profile["llm"] = {"model": "qwen3:4b", "model_manifest": str(path), "seed": 0}
    trace = ExecutionTrace(settings, "wire")
    def handler(request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [model]})
        received.append(request.content)
        return httpx.Response(200, content=json.dumps({"message": {"content": "0 V [S001]"}, "done": True,
                                                      "done_reason": "stop"}) + "\n")
    async def run():
        gateway = OllamaGateway(settings)
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        token = CURRENT_TRACE.set(trace)
        try:
            return [e async for e in gateway.stream([{"role": "user", "content": "Quelle valeur à zéro ?"}], asyncio.Event())]
        finally:
            CURRENT_TRACE.reset(token)
            await gateway.close()
            trace.close()
    assert asyncio.run(run())[-1]["type"] == "done"
    request = next(r["data"] for r in read_verified_trace(trace.path) if r["phase"] == "llm.request")
    assert request["body"] == json.loads(received[0])
    assert request["wire_sha256"] == hashlib.sha256(received[0]).hexdigest()
    assert request["body"]["options"]["seed"] == 0


@pytest.mark.parametrize("policy,available,unload", [("keep", 1, False), ("unload", 9000, True),
                                                     ("adaptive", 1800, True), ("adaptive", 9000, False)])
def test_residency_policy_releases_only_when_decided(tmp_path, monkeypatch, policy, available, unload):
    import psutil

    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=available * 1048576))
    gateway = OllamaGateway(Settings(tmp_path, {"llm": {"residency_policy": policy}}))
    calls = []
    async def release():
        calls.append("released")
    gateway.unload = release
    async def run():
        try:
            return await gateway.finish_residency()
        finally:
            await gateway.close()
    result = asyncio.run(run())
    assert bool(calls) is unload
    assert result["action"] == ("unloaded_verified" if unload else "kept")


def test_residency_failure_is_not_reported_as_success(tmp_path):
    gateway = OllamaGateway(Settings(tmp_path, {"llm": {"residency_policy": "unload"}}))
    async def release():
        raise ApiError("ollama_unavailable", "échec", 503)
    gateway.unload = release
    async def run():
        try:
            return await gateway.finish_residency()
        finally:
            await gateway.close()
    assert asyncio.run(run())["action"] == "unload_unverified"
