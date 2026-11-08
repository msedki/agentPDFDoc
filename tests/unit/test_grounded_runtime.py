"""4B identity before any document transmission; transport is an explicit double."""

import asyncio
import json

import httpx
import pytest

from services.api.errors import ApiError
from services.api.ollama import OllamaGateway
from services.api.settings import Settings


def identity_settings(tmp_path, size="4.0B", family="qwen3"):
    record = {"name": "locked-4b:q4km", "digest": "a" * 64,
              "details": {"quantization_level": "Q4_K_M", "parameter_size": size, "family": family}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"model": record}))
    return Settings(tmp_path, {"llm": {"model": record["name"], "model_manifest": str(path),
                                      "required_parameter_size": "4.0B", "required_family": "qwen3"}}), record


@pytest.mark.parametrize("size,family", [("8.2B", "qwen3"), ("2.0B", "qwen3"), ("4.0B", "other"), (None, "qwen3")])
def test_incompatible_manifest_refused_even_under_4b_alias(tmp_path, size, family):
    settings, _ = identity_settings(tmp_path, size, family)

    async def scenario():
        gateway = OllamaGateway(settings)
        try:
            with pytest.raises(ApiError, match="Manifest") as failure:
                gateway.expected_identity()
            assert failure.value.code == "llm_identity_unverified"
        finally:
            await gateway.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("resident", [False, True])
def test_runtime_size_mismatch_refuses_before_chat(tmp_path, resident):
    settings, record = identity_settings(tmp_path)
    actual = {**record, "details": {**record["details"], "parameter_size": "8.2B"}}
    calls = []

    def transport(request):
        calls.append(request.url.path)
        assert request.url.path != "/api/chat", "No documentary prompt may reach a mismatching model"
        return httpx.Response(200, json={"models": [actual] if resident or request.url.path == "/api/tags" else []})

    async def scenario():
        gateway = OllamaGateway(settings)
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ApiError) as failure:
                _ = [event async for event in gateway.stream([{"role": "user", "content": "source privée"}], asyncio.Event())]
            assert failure.value.code == "llm_identity_mismatch"
        finally:
            await gateway.close()

    asyncio.run(scenario())
    assert "/api/chat" not in calls


def test_native_read_timeout_is_distinct_from_unavailability(tmp_path):
    settings, record = identity_settings(tmp_path)

    def transport(request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [record]})
        raise httpx.ReadTimeout("controlled idle timeout", request=request)

    async def scenario():
        gateway = OllamaGateway(settings)
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ApiError) as failure:
                _ = [event async for event in gateway.stream([{"role": "user", "content": "preuve"}], asyncio.Event())]
            assert failure.value.code == "ollama_timeout"
            assert isinstance(failure.value.__cause__, httpx.ReadTimeout)
        finally:
            await gateway.close()

    asyncio.run(scenario())
