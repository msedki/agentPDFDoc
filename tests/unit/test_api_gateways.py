"""HTTP payload/stream contracts with explicit MockTransport, not real server proof."""
import asyncio
import json

import httpx
import pytest

from services.api.errors import ApiError
from services.api.ollama import OllamaGateway
from services.api.retrieval import QdrantStore, placement_matches
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


# Configurations effectives relues le 01/10 sur Qdrant 1.19.1 : collection de l'instance principale créée avant W017
# (ancienne forme) et collection de sondage créée avec `memory` (W017).
LEGACY_EFFECTIVE = {"params": {"vectors": {"dense": {"size": 384, "distance": "Cosine", "on_disk": True}}, "replication_factor": 1, "on_disk_payload": True},
                    "hnsw_config": {"m": 16, "ef_construct": 100, "on_disk": False}, "optimizer_config": {"max_optimization_threads": 1}}
MEMORY_EFFECTIVE = {"params": {"vectors": {"dense": {"size": 384, "distance": "Cosine", "memory": "cold"}}, "replication_factor": 1, "on_disk_payload": True,
                               "payload": {"memory": "cold"}},
                    "hnsw_config": {"m": 16, "ef_construct": 100, "on_disk": False, "memory": "cached"}, "optimizer_config": {"max_optimization_threads": 1}}


def test_api_qdrant_memory_placement_accepts_both_forms_and_rejects_other_tiers():
    import copy
    assert placement_matches(LEGACY_EFFECTIVE) and placement_matches(MEMORY_EFFECTIVE)
    wrong = []
    for path, value in ((("params", "vectors", "dense", "memory"), "cached"), (("params", "payload", "memory"), "cached"), (("hnsw_config", "memory"), "cold"),
                        (("params", "vectors", "dense", "memory"), "pinned"), (("hnsw_config", "memory"), "pinned")):
        effective = copy.deepcopy(MEMORY_EFFECTIVE)
        target = effective
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        wrong.append(placement_matches(effective))
    legacy_ram_vectors = copy.deepcopy(LEGACY_EFFECTIVE)
    legacy_ram_vectors["params"]["vectors"]["dense"]["on_disk"] = False
    legacy_disk_graph = copy.deepcopy(LEGACY_EFFECTIVE)
    legacy_disk_graph["hnsw_config"]["on_disk"] = True
    assert wrong == [False] * 5 and not placement_matches(legacy_ram_vectors) and not placement_matches(legacy_disk_graph)
    # `memory` prévaut sur l'ancien drapeau quand les deux sont présents.
    conflicting = copy.deepcopy(MEMORY_EFFECTIVE)
    conflicting["hnsw_config"]["memory"] = "cold"
    assert not placement_matches(conflicting)


def test_api_qdrant_store_sends_instance_api_key_from_supervisor_or_control_file(tmp_path, monkeypatch):
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    monkeypatch.delenv("RAG_QDRANT_API_KEY", raising=False)
    settings = Settings(tmp_path)
    assert settings.qdrant_headers == {}
    control = tmp_path / ".runtime/control"
    control.mkdir(parents=True)
    (control / "qdrant-api-key").write_text("cle-du-fichier", encoding="ascii")
    assert settings.qdrant_headers == {"api-key": "cle-du-fichier"}
    monkeypatch.setenv("RAG_QDRANT_API_KEY", "cle-du-superviseur")
    seen = []
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **options: real_client(
        transport=httpx.MockTransport(lambda request: seen.append((request.url.path, request.headers.get("api-key")))
                                      or httpx.Response(200, json={"status": "ok", "result": {"collections": []}})), **options))
    store = QdrantStore(settings)
    async def scenario():
        await store.request("GET", "/collections")
        await store.client.get("/collections/absente")
        await store.close()
    asyncio.run(scenario())
    assert seen == [("/collections", "cle-du-superviseur"), ("/collections/absente", "cle-du-superviseur")]

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


# --- Accélération GPU de la génération (W024, W025) ----------------------------------------------------------------
# Doubles explicites d'Ollama 0.35.0 (MockTransport) : aucune preuve d'un GPU réel, qui relève de l'essai J11.8.

# Corps /api/chat produits par ollama.py avant W024 (fichier inchangé de ba945af à 0dbae7b), relevés octet pour octet
# avec psutil.cpu_count(logical=False) == 3 : référence du mode CPU, qui ne doit pas changer (poste sans GPU utilisable).
REFERENCE_MESSAGES = [{"role": "user", "content": "Question ? « é »"}]
REFERENCE_CPU_BODY = (b'{"model":"qwen3.5:4b","messages":[{"role":"user","content":"Question ? \xc2\xab \xc3\xa9 \xc2\xbb"}],'
                      b'"stream":true,"think":false,"keep_alive":"10m","options":{"num_ctx":8192,"num_predict":384,'
                      b'"temperature":0.2,"top_p":0.9,"num_gpu":0,"num_thread":2}}')
REFERENCE_DEFAULT_MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
REFERENCE_DEFAULT_CPU_BODY = (b'{"model":"qwen3.5:4b","messages":[{"role":"system","content":"s"},{"role":"user","content":"q"}],'
                              b'"stream":true,"think":false,"keep_alive":"10m","options":{"num_ctx":8192,"num_predict":768,'
                              b'"temperature":0.2,"top_p":0.9,"num_gpu":0,"num_thread":2}}')
GPU_RESIDENT = {**locked_running_model(), "size": 3_670_016_000, "size_vram": 3_670_016_000}
ANSWER = ({"message": {"content": "72 V [S001]"}, "done": False},
          {"message": {"content": ""}, "done": True, "done_reason": "stop", "eval_count": 3})
LOAD_FAILURE = "llama runner process has terminated: CUDA error: out of memory"


def ndjson(*events):
    return httpx.Response(200, content="\n".join(json.dumps(event) for event in events), headers={"content-type": "application/x-ndjson"})


class ScriptedOllama:
    """Double d'Ollama : `/api/ps` rend le modèle résident, `/api/generate` (keep_alive 0) le décharge, `/api/chat`
    rejoue ses réponses dans l'ordre et, sur un succès, laisse le modèle résident sur GPU ou CPU selon `num_gpu`.
    Chaque requête est consignée avec son corps."""

    def __init__(self, chats, *, resident=None, unload_reply=None, on_unload=None):
        self.chats, self.resident, self.unload_reply, self.on_unload = list(chats), resident, unload_reply, on_unload
        self.calls, self.chat_bodies = [], []

    def __call__(self, request):
        self.calls.append(request.url.path)
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [self.resident] if self.resident else []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [locked_running_model()]})
        if request.url.path == "/api/generate":
            assert json.loads(request.content)["keep_alive"] == 0
            if self.on_unload:
                self.on_unload()
            if self.unload_reply is not None:
                return self.unload_reply
            self.resident = None
            return httpx.Response(200, json={"done": True, "done_reason": "unload"})
        assert request.url.path == "/api/chat"
        self.chat_bodies.append(request.content)
        reply = self.chats.pop(0)
        response = reply(request) if callable(reply) else reply
        if response.status_code == 200:
            cpu = "num_gpu" in json.loads(request.content)["options"]
            self.resident = {**GPU_RESIDENT, "size_vram": 0} if cpu else GPU_RESIDENT
        return response

    def chats_sent(self):
        return [json.loads(body)["options"] for body in self.chat_bodies]


def accelerated_gateway(tmp_path, monkeypatch, decided=("gpu", "gpu_discovered"), llm=None):
    """Passerelle d'une instance dont le superviseur a décidé `decided` (RAG_LLM_ACCELERATOR et sa raison)."""
    import psutil
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    for name, value in zip(("RAG_LLM_ACCELERATOR", "RAG_LLM_ACCELERATOR_REASON"), decided or (None, None), strict=True):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return OllamaGateway(Settings(tmp_path, {"llm": llm if llm is not None else {"accelerator": "auto"}}))


def run_stream(gateway, scripted, messages=REFERENCE_MESSAGES, output_tokens=384, cancelled=None, before=None):
    """Événements d'une génération ; l'exception levée est rendue comme dernier élément."""
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
        events = []
        try:
            if before:
                await before()
            async for event in gateway.stream(messages, cancelled or asyncio.Event(), output_tokens):
                events.append(event)
        except (Exception, asyncio.CancelledError) as error:
            events.append(error)
        finally:
            await gateway.close()
        return events
    return asyncio.run(scenario())


@pytest.mark.parametrize("llm,decided", [
    ({}, None),
    ({"accelerator": "cpu"}, None),
    ({"accelerator": "cpu"}, ("gpu", "gpu_discovered")),
    ({"num_gpu": 0}, ("gpu", "gpu_discovered")),
    ({"accelerator": "auto"}, ("cpu", "no_gpu_discovered")),
    ({"accelerator": "auto"}, ("cpu", "gpu_path_not_qualified")),
    ({"accelerator": "gpu"}, ("cpu", "discovery_unreadable")),
    ({"accelerator": "auto"}, ("GPU", "gpu_discovered")),
], ids=["sans-cle-sans-decision", "cpu", "cpu-impose-malgre-decision-gpu", "forme-anterieure", "auto-sans-gpu",
        "auto-voie-non-qualifiee", "essai-gpu-decouverte-illisible", "decision-invalide"])
def test_api_ollama_cpu_mode_sends_the_reference_body_byte_for_byte(tmp_path, monkeypatch, llm, decided):
    gateway = accelerated_gateway(tmp_path, monkeypatch, decided, llm)
    assert gateway.execution["mode"] == "cpu"
    scripted = ScriptedOllama([ndjson(*ANSWER), ndjson(*ANSWER)], resident=locked_running_model())
    first = run_stream(gateway, scripted)
    gateway = accelerated_gateway(tmp_path, monkeypatch, decided, llm)
    second = run_stream(gateway, ScriptedOllama([ndjson(*ANSWER)], resident=locked_running_model()), REFERENCE_DEFAULT_MESSAGES, None)
    assert scripted.chat_bodies == [REFERENCE_CPU_BODY]
    assert first[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": False}
    assert second[-1]["type"] == "done"


def test_api_ollama_cpu_mode_default_body_matches_its_reference(tmp_path, monkeypatch):
    scripted = ScriptedOllama([ndjson(*ANSWER)], resident=locked_running_model())
    run_stream(accelerated_gateway(tmp_path, monkeypatch, None, {}), scripted, REFERENCE_DEFAULT_MESSAGES, None)
    assert scripted.chat_bodies == [REFERENCE_DEFAULT_CPU_BODY]


@pytest.mark.parametrize("llm,reason", [({"accelerator": "auto"}, "gpu_discovered"), ({"accelerator": "gpu"}, "gpu_trial"), ({}, "gpu_discovered")])
def test_api_ollama_gpu_mode_only_omits_num_gpu(tmp_path, monkeypatch, llm, reason):
    gateway = accelerated_gateway(tmp_path, monkeypatch, ("gpu", reason), llm)
    scripted = ScriptedOllama([ndjson(*ANSWER)], resident=GPU_RESIDENT)
    events = run_stream(gateway, scripted)
    assert scripted.chat_bodies == [REFERENCE_CPU_BODY.replace(b'"num_gpu":0,', b"")]
    assert list(json.loads(scripted.chat_bodies[0])["options"]) == ["num_ctx", "num_predict", "temperature", "top_p", "num_thread"]
    assert events[-1]["metrics"]["llm_execution"] == {"mode": "gpu", "fallback": False}
    assert gateway.describe() == {"requested": llm.get("accelerator", "auto"), "requested_source": "profile" if llm else "default",
                                  "mode": "gpu", "reason": reason, "fallback": None}


def loaded_state_for(tmp_path, monkeypatch, decided, record):
    gateway = accelerated_gateway(tmp_path, monkeypatch, decided)
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"models": [record]})))
        try:
            return await gateway.loaded_state()
        finally:
            await gateway.close()
    return asyncio.run(scenario())


@pytest.mark.parametrize("decided,size_vram,loaded,processor", [
    (("cpu", "no_gpu_discovered"), 0, True, "100% CPU"),
    (("cpu", "no_gpu_discovered"), 1, False, "100%/0% CPU/GPU"),
    (("cpu", "imposed_by_profile"), 4096 * 1048576, False, "100% GPU"),
    (("gpu", "gpu_discovered"), 4096 * 1048576, True, "100% GPU"),
    (("gpu", "gpu_discovered"), 3072 * 1048576, True, "25%/75% CPU/GPU"),
    # M5 : en GPU, un runner chargé sur CPU sert aussi (la requête sans num_gpu ne recharge pas, `needsReload`).
    (("gpu", "gpu_discovered"), 0, True, "100% CPU"),
])
def test_api_ollama_loaded_state_follows_the_execution_mode(tmp_path, monkeypatch, decided, size_vram, loaded, processor):
    record = {**locked_running_model(), "size": 4096 * 1048576, "size_vram": size_vram}
    state = loaded_state_for(tmp_path, monkeypatch, decided, record)
    assert state["resident"] is True and state["loaded"] is loaded
    assert ("cpu_residency_not_verified" in state["cold_reasons"]) is (not loaded)
    assert state["processor"] == processor and state["execution_mode"] == decided[0]
    assert state["additional_peak_mib"] == 512


def test_api_ollama_gpu_load_failure_falls_back_to_cpu_once_for_the_instance(tmp_path, monkeypatch):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    readmissions = []
    async def cold_readmission():
        # L'admission à froid suit le déchargement et précède la relance (H1).
        readmissions.append(list(scripted.calls))
    gateway.before_cpu_fallback = cold_readmission
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER), ndjson(*ANSWER)], resident=GPU_RESIDENT)
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
        first = [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        calls_after_first = list(scripted.calls)
        second = [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        await gateway.close()
        return first, calls_after_first, second
    first, calls_after_first, second = asyncio.run(scenario())
    assert calls_after_first == ["/api/ps", "/api/chat", "/api/ps", "/api/generate", "/api/ps", "/api/chat"]
    assert readmissions == [calls_after_first[:5]]
    # Question suivante : résidence relue (modèle désormais sur CPU), puis directement le corps CPU, sans repli.
    assert scripted.calls[len(calls_after_first):] == ["/api/ps", "/api/chat"]
    gpu_body = REFERENCE_CPU_BODY.replace(b'"num_gpu":0,', b"")
    assert scripted.chat_bodies == [gpu_body, REFERENCE_CPU_BODY, REFERENCE_CPU_BODY]
    assert [event["type"] for event in first] == ["cpu_fallback", "delta", "done"]
    assert first[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": True}
    assert second[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": False}
    fallback = gateway.describe()["fallback"]
    assert gateway.describe()["mode"] == "cpu" and gateway.describe()["reason"] == "gpu_discovered"
    assert set(fallback) == {"utc", "http_status", "error"} and fallback["http_status"] == 500 and fallback["error"] == LOAD_FAILURE
    assert "Question" not in json.dumps(gateway.describe())


@pytest.mark.parametrize("reply,code", [
    (httpx.Response(503, json={"error": "server busy, please try again.  maximum pending requests exceeded"}), "ollama_unavailable"),
    (httpx.Response(499, json={"error": "request canceled"}), "ollama_unavailable"),
    (httpx.Response(400, json={"error": "registry.ollama.ai/library/qwen3.5:4b does not support tools"}), "ollama_unavailable"),
    (httpx.Response(404, json={"error": 'model "qwen3.5:4b" not found, try pulling it first'}), "ollama_unavailable"),
    (httpx.Response(502), "ollama_unavailable"),
    (ndjson({"error": "llama runner process has terminated"}), "ollama_failure"),
    (lambda request: (_ for _ in ()).throw(httpx.ConnectError("connexion refusée", request=request)), "ollama_unavailable"),
], ids=["503", "499", "400", "404", "502", "evenement-error", "transport"])
def test_api_ollama_gpu_errors_other_than_a_500_before_the_stream_never_fall_back(tmp_path, monkeypatch, reply, code):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    gateway.before_cpu_fallback = lambda: pytest.fail("aucune admission de repli attendue")
    scripted = ScriptedOllama([reply], resident=GPU_RESIDENT)
    events = run_stream(gateway, scripted)
    assert isinstance(events[-1], ApiError) and events[-1].code == code
    assert scripted.calls == ["/api/ps", "/api/chat"] and len(scripted.chat_bodies) == 1
    assert gateway.describe()["mode"] == "gpu" and gateway.describe()["fallback"] is None


def test_api_ollama_gpu_error_after_a_delta_is_reported_without_fallback(tmp_path, monkeypatch):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    scripted = ScriptedOllama([ndjson({"message": {"content": "72 V"}, "done": False}, {"error": "CUDA error: an illegal memory access"})],
                              resident=GPU_RESIDENT)
    events = run_stream(gateway, scripted)
    assert events[0] == {"type": "delta", "text": "72 V"}
    assert isinstance(events[-1], ApiError) and events[-1].code == "ollama_failure"
    assert len(scripted.chat_bodies) == 1 and "/api/generate" not in scripted.calls
    assert gateway.describe()["mode"] == "gpu" and gateway.describe()["fallback"] is None


def test_api_ollama_cpu_mode_never_falls_back(tmp_path, monkeypatch):
    gateway = accelerated_gateway(tmp_path, monkeypatch, ("cpu", "no_gpu_discovered"))
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER)], resident=locked_running_model())
    events = run_stream(gateway, scripted)
    assert isinstance(events[-1], ApiError) and events[-1].code == "ollama_unavailable"
    assert scripted.chat_bodies == [REFERENCE_CPU_BODY] and "/api/generate" not in scripted.calls
    assert gateway.describe()["fallback"] is None


@pytest.mark.parametrize("unload_reply", [httpx.Response(500, json={"error": "unload failed"}),
                                          httpx.Response(200, json={"done": False})], ids=["http-500", "non-confirme"])
def test_api_ollama_unconfirmed_unload_does_not_prevent_the_fallback(tmp_path, monkeypatch, caplog, unload_reply):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    readmitted = []
    async def cold_readmission():
        readmitted.append(True)
    gateway.before_cpu_fallback = cold_readmission
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER)], resident=GPU_RESIDENT, unload_reply=unload_reply)
    with caplog.at_level("WARNING", logger="rag.llm"):
        events = run_stream(gateway, scripted)
    assert events[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": True}
    assert readmitted == [True] and scripted.chat_bodies[-1] == REFERENCE_CPU_BODY
    assert any("déchargement du modèle non confirmé" in record.getMessage() for record in caplog.records)


def test_api_ollama_cancellation_during_the_unload_of_a_fallback_stops_before_the_relaunch(tmp_path, monkeypatch):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    gateway.before_cpu_fallback = lambda: pytest.fail("annulée : aucune admission de repli")
    cancelled = asyncio.Event()
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE})], resident=GPU_RESIDENT, on_unload=cancelled.set)
    events = run_stream(gateway, scripted, cancelled=cancelled)
    assert isinstance(events[-1], asyncio.CancelledError) and len(scripted.chat_bodies) == 1
    # Le repli reste acquis pour l'instance : la question suivante partira directement sur CPU.
    assert gateway.describe()["mode"] == "cpu" and gateway.describe()["fallback"]["http_status"] == 500


def test_api_ollama_task_cancelled_during_the_cold_readmission_never_relaunches(tmp_path, monkeypatch):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE})], resident=GPU_RESIDENT)
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
        entered = asyncio.Event()
        async def blocked_readmission():
            entered.set()
            await asyncio.Event().wait()
        gateway.before_cpu_fallback = blocked_readmission
        async def consume():
            return [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        task = asyncio.create_task(consume())
        waiter = asyncio.create_task(entered.wait())
        # Attente bornée : une génération qui se termine sans atteindre l'admission de repli fait échouer le test.
        await asyncio.wait({task, waiter}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
        reached = entered.is_set()
        waiter.cancel()
        task.cancel()
        outcome = (await asyncio.gather(task, return_exceptions=True))[0]
        await gateway.close()
        return reached, outcome
    reached, outcome = asyncio.run(scenario())
    assert reached and isinstance(outcome, asyncio.CancelledError)
    assert len(scripted.chat_bodies) == 1 and gateway.describe()["mode"] == "cpu"


@pytest.mark.parametrize("body,expected", [
    ({"error": "x" * 1000}, "x" * 300),
    ("<html>\n  erreur   du runner\n</html>", "<html> erreur du runner </html>"),
    (b"", ""),
], ids=["tronque", "corps-non-json", "corps-vide"])
def test_api_ollama_fallback_records_a_bounded_error_text(tmp_path, monkeypatch, body, expected):
    gateway = accelerated_gateway(tmp_path, monkeypatch)
    reply = httpx.Response(500, json=body) if isinstance(body, dict) else httpx.Response(500, content=body if isinstance(body, bytes) else body.encode())
    scripted = ScriptedOllama([reply, ndjson(*ANSWER)], resident=GPU_RESIDENT)
    run_stream(gateway, scripted)
    assert gateway.describe()["fallback"]["error"] == expected
