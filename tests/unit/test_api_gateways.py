"""HTTP payload/stream contracts with explicit MockTransport, not real server proof."""
import asyncio
import json

import httpx
import pytest

from services.api.ollama import OllamaGateway
from services.api.retrieval import QdrantStore
from services.api.scope import ScopeSnapshot
from services.api.settings import Settings


LOCKED_DIGEST = "a" * 64


def locked_running_model():
    return {"name": "qwen3.5:4b", "digest": LOCKED_DIGEST, "context_length": 8192, "size_vram": 0,
            "details": {"quantization_level": "Q4_K_M"}}


@pytest.fixture(autouse=True)
def locked_model_manifest(tmp_path):
    directory = tmp_path / ".runtime/manifests"
    directory.mkdir(parents=True)
    (directory / "ollama-model.json").write_text(json.dumps({"model": locked_running_model()}), encoding="utf-8")


def test_api_qdrant_server_filter_identity_and_verified_upsert(tmp_path):
    config = {"vectors": {"dense": {"size": 384, "distance": "Cosine", "on_disk": True}}, "replication_factor": 1, "on_disk_payload": True,
              "hnsw_config": {"on_disk": False}, "optimizers_config": {"max_optimization_threads": 1}}
    (tmp_path / "config").mkdir()
    (tmp_path / "config/qdrant.collection.json").write_text(json.dumps(config))
    store = QdrantStore(Settings(tmp_path))
    store._identity = {"fingerprint": "abcdef0123456789" * 4}
    snapshot = ScopeSnapshot({"kind": "pages"}, ["generation"], {"generation": "version"}, {"generation": "doc"}, [2], ["block"])
    requests, points = [], {}
    exists = False
    def handler(request):
        nonlocal exists
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, dict(request.url.params), body))
        if request.url.path.endswith("/points/query"):
            assert body["filter"] == snapshot.vector_filter() and body["limit"] == 24 and body["params"]["hnsw_ef"] == 64
            return httpx.Response(200, json={"status": "ok", "result": {"points": [{"id": "point"}]}})
        if request.method == "PUT" and request.url.path.endswith("/points"):
            assert request.url.params["wait"] == "true"
            points.update({point["id"]: point for point in body["points"]})
        elif request.method == "POST" and request.url.path.endswith("/points"):
            return httpx.Response(200, json={"status": "ok", "result": [points[key] for key in body["ids"]]})
        elif request.method == "GET":
            if not exists:
                return httpx.Response(404)
            return httpx.Response(200, json={"status": "ok", "result": {"config": {"params": {key: value for key, value in config.items() if key not in {"hnsw_config", "optimizers_config"}}, "hnsw_config": config["hnsw_config"], "optimizer_config": config["optimizers_config"]}}})
        elif request.method == "PUT" and not request.url.path.endswith("/index"):
            exists = True
        return httpx.Response(200, json={"status": "ok", "result": True})
    async def scenario():
        await store.client.aclose()
        store.client = httpx.AsyncClient(base_url=store.base_url, transport=httpx.MockTransport(handler))
        await store.ensure_collection()
        assert store.collection.endswith("_abcdef0123456789")
        assert await store.query([1.0] * 384, snapshot) == ["point"]
        await store.upsert([{"id": "point", "payload": {"text_hash": "hash"}, "vector": {"dense": [1.0] * 384}}])
        await store.verify({"point": "hash"})
        await store.close()
    asyncio.run(scenario())
    assert any(method == "PUT" and path.endswith("/index") for method, path, _, _ in requests)


def test_api_ollama_real_ndjson_contract_cpu_and_length_limit(tmp_path):
    gateway = OllamaGateway(Settings(tmp_path))
    requests = []
    def handler(request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [locked_running_model()]})
        body = json.loads(request.content)
        requests.append(body)
        assert body["think"] is False and body["options"]["num_gpu"] == 0 and body["options"]["num_predict"] == 384
        assert 1 <= body["options"]["num_thread"] <= 4
        content = '\n'.join(json.dumps(event) for event in [{"message": {"content": "72 V [S001]"}, "done": False}, {"message": {"content": ""}, "done": True, "done_reason": "length", "eval_count": 384}])
        return httpx.Response(200, content=content, headers={"content-type": "application/x-ndjson"})
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        events = [event async for event in gateway.stream([{"role": "user", "content": "fixture"}], asyncio.Event(), 384)]
        await gateway.close()
        return events
    events = asyncio.run(scenario())
    assert events[0] == {"type": "delta", "text": "72 V [S001]"}
    assert events[1]["finish_reason"] == "length" and events[1]["metrics"]["prompt_eval_cached_count"] == "unknown"


def test_api_ollama_cancel_closes_pending_stream(tmp_path):
    gateway = OllamaGateway(Settings(tmp_path))
    class SlowStream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield b'{"message":{"content":"partial"},"done":false}\n'
            await asyncio.sleep(3600)
        async def aclose(self):
            self.closed = True
    stream = SlowStream()
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": [locked_running_model()]}) if request.url.path == "/api/ps" else httpx.Response(200, stream=stream)))
        cancelled = asyncio.Event()
        generator = gateway.stream([{"role": "user", "content": "fixture"}], cancelled)
        assert (await anext(generator))["text"] == "partial"
        cancelled.set()
        with pytest.raises(asyncio.CancelledError):
            await anext(generator)
        assert stream.closed
        await gateway.close()
    asyncio.run(scenario())


def test_api_ollama_unload_is_confirmed_control_call(tmp_path):
    gateway = OllamaGateway(Settings(tmp_path))
    unloaded = False
    def handler(request):
        nonlocal unloaded
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [] if unloaded else [{"name": "qwen3.5:4b"}]})
        body = json.loads(request.content)
        assert request.url.path == "/api/generate" and body["keep_alive"] == 0 and body["prompt"] == ""
        unloaded = True
        return httpx.Response(200, json={"done": True, "done_reason": "unload"})
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        result = await gateway.unload()
        await gateway.close()
        return result
    assert asyncio.run(scenario())["state"] == "unloaded"


@pytest.mark.parametrize("changes,loaded", [({}, True), ({"context_length": 4096}, False), ({"context_length": None}, False), ({"size_vram": 1}, False), ({"details": {"quantization_level": "Q8_0"}}, False)])
def test_api_ollama_loaded_state_requires_cpu_context_and_quantization(tmp_path, changes, loaded):
    gateway = OllamaGateway(Settings(tmp_path))
    record = {"name": "qwen3.5:4b", "context_length": 8192, "size_vram": 0, "size": 4096 * 1048576,
              "digest": LOCKED_DIGEST, "details": {"quantization_level": "Q4_K_M"}, **changes}
    requests = []
    def handler(request):
        requests.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"models": [record]})
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        result = await gateway.loaded_state()
        await gateway.close()
        return result
    result = asyncio.run(scenario())
    assert result["loaded"] is loaded and result["resident"] is True
    assert result["resident_size_mib"] == 4096 and result["additional_peak_mib"] == 512
    assert bool(result["cold_reasons"]) is not loaded
    assert requests == [("GET", "/api/ps", b"")]


def test_api_ollama_loaded_state_absent_model_stays_cold(tmp_path):
    gateway = OllamaGateway(Settings(tmp_path))
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": [{"name": "other-model"}]})))
        result = await gateway.loaded_state()
        await gateway.close()
        return result
    assert asyncio.run(scenario()) == {"loaded": False, "resident": False, "model": "qwen3.5:4b", "additional_peak_mib": 0}


def test_api_ollama_threads_follow_profile_and_physical_limit(tmp_path, monkeypatch):
    import psutil
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    gateway = OllamaGateway(Settings(tmp_path, {"llm": {"threads_max": 8}}))
    def handler(request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [locked_running_model()]})
        assert json.loads(request.content)["options"]["num_thread"] == 2
        return httpx.Response(200, content=json.dumps({"done": True, "done_reason": "stop", "message": {"content": ""}}))
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        assert [event async for event in gateway.stream([], asyncio.Event())][0]["type"] == "done"
        await gateway.close()
    asyncio.run(scenario())


def test_api_embedding_release_preserves_tokenizer_and_measures_next_reload(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    import psutil
    from services.api.embedding import EmbeddingService
    embedding = EmbeddingService(Settings(tmp_path))
    embedding._session = object()
    tokenizer = object()
    embedding._tokenizer = tokenizer
    embedding._identity = {"fingerprint": "controlled-identity"}
    samples = iter([{"available_mib": 5000, "process_rss_mib": 500}, {"available_mib": 5400, "process_rss_mib": 100},
                    {"available_mib": 5400, "process_rss_mib": 100}, {"available_mib": 5000, "process_rss_mib": 500}])
    monkeypatch.setattr(embedding, "memory_sample", lambda: next(samples))
    released = embedding.release_session()
    assert released["rss_decrease_mib"] == 400 and released["available_increase_mib"] == 400
    assert embedding._tokenizer is tokenizer and embedding._identity["fingerprint"] == "controlled-identity"
    assert embedding.lifecycle()["session_loaded"] is False and released["next_reload_measurement"] == "pending"
    class Options:
        def add_session_config_entry(self, *args):
            pass
    class Session:
        def __init__(self, *args, **kwargs):
            assert kwargs["providers"] == ["CPUExecutionProvider"]
        def get_providers(self):
            return ["CPUExecutionProvider"]
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(SessionOptions=Options, InferenceSession=Session))
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=8000 * 1048576))
    monkeypatch.setattr(embedding, "model_path", lambda: tmp_path / "controlled-model.onnx")
    embedding.session()
    state = embedding.lifecycle()
    assert state["session_loaded"] and state["load_count"] == 1 and state["last_load"]["reload_after_release"]
    assert state["last_release"]["next_reload_measurement"] == "observed" and state["last_load"]["elapsed_ms"] >= 0


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("digest", [None, "b" * 64, LOCKED_DIGEST])
def test_api_ollama_checks_provisioned_digest_before_cold_or_warm_stream(tmp_path, warm, digest):
    from services.api.errors import ApiError
    gateway = OllamaGateway(Settings(tmp_path))
    requests = []
    def handler(request):
        requests.append(request.url.path)
        record = {**locked_running_model(), "digest": digest}
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [record] if warm else []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [record]})
        assert request.url.path == "/api/chat"
        return httpx.Response(200, content=json.dumps({"message": {"content": ""}, "done": True}))
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        try:
            if digest != LOCKED_DIGEST:
                with pytest.raises(ApiError) as failure:
                    _ = [event async for event in gateway.stream([{"role": "user", "content": "private-documentary-context"}], asyncio.Event())]
                assert failure.value.code == "llm_identity_mismatch"
                assert "private-documentary-context" not in failure.value.message
            else:
                result = [event async for event in gateway.stream([], asyncio.Event())]
                assert result[-1]["metrics"]["verified_model_identity"]["digest"] == LOCKED_DIGEST
                assert result[-1]["metrics"]["verified_model_identity"]["source"] == ("/api/ps" if warm else "/api/tags")
        finally:
            await gateway.close()
    asyncio.run(scenario())
    assert ("/api/chat" in requests) is (digest == LOCKED_DIGEST)
    assert ("/api/tags" in requests) is not warm


def test_api_ollama_missing_manifest_refuses_before_network_or_context(tmp_path):
    from services.api.errors import ApiError
    (tmp_path / ".runtime/manifests/ollama-model.json").unlink()
    gateway = OllamaGateway(Settings(tmp_path))
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(lambda request: pytest.fail("No network call with unknown provisioned identity")))
        with pytest.raises(ApiError) as failure:
            _ = [event async for event in gateway.stream([], asyncio.Event())]
        assert failure.value.code == "llm_identity_unverified"
        await gateway.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("profile,available_mib,estimate,admitted", [
    ({"resources": {"embedding_load_peak_estimate_mib": 512}}, 1536 + 600, 512, True),
    ({}, 1536 + 600, 768, False),
    ({"resources": {"embedding_load_peak_estimate_mib": 512}}, 1536 + 400, 512, False)])
def test_api_embedding_admission_reads_profile_load_estimate(tmp_path, monkeypatch, profile, available_mib, estimate, admitted):
    import sys
    from types import SimpleNamespace

    import psutil

    from services.api.embedding import EmbeddingService
    from services.api.errors import ApiError
    embedding = EmbeddingService(Settings(tmp_path, profile))
    embedding._identity = {"fingerprint": "controlled-identity"}
    loads = []
    class Options:
        def add_session_config_entry(self, *args):
            pass
    class Session:
        def __init__(self, *args, **kwargs):
            loads.append(kwargs["providers"])
        def get_providers(self):
            return ["CPUExecutionProvider"]
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(SessionOptions=Options, InferenceSession=Session))
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=available_mib * 1048576))
    monkeypatch.setattr(embedding, "model_path", lambda: tmp_path / "controlled-model.onnx")
    if admitted:
        embedding.session()
        assert loads == [["CPUExecutionProvider"]]
    else:
        with pytest.raises(ApiError) as caught:
            embedding.session()
        assert caught.value.code == "embedding_admission_denied" and caught.value.details["load_estimate_mib"] == estimate and not loads
