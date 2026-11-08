"""Échecs fermés : fichier réel, écriture courte et transport HTTP simulés.

Les artefacts de provisionnement sont de petits doubles locaux ; aucun GGUF
réel, serveur Ollama, import natif ou téléchargement n'est utilisé.
"""

import asyncio
import copy
import json

import httpx
import pytest

from services.api.errors import ApiError
from services.api.execution_trace import CURRENT_TRACE, ExecutionTrace, read_verified_trace
from services.api.ollama import OllamaGateway
from services.api.settings import Settings
from tools.qualification import provision_enhanced_4b as provisioning


class ShortWriteToRealFile:
    """Double qui écrit effectivement sept octets sur le fichier temporaire."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        return self.stream.write(data[:7])

    def close(self):
        self.stream.close()


@pytest.mark.parametrize("required", [True, False])
def test_short_write_to_real_trace_file_never_advances_chain(tmp_path, required):
    settings = Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {"mode": "full"}})
    trace = ExecutionTrace(settings, "short-write")
    trace.record("query.start", {"question": "zéro"})
    before = trace.summary()
    original_bytes = trace.path.read_bytes()
    trace.stream = ShortWriteToRealFile(trace.stream)
    try:
        if required:
            with pytest.raises(ApiError) as failure:
                trace.record("llm.request", {"body": {"seed": 0}})
            assert failure.value.code == "trace_write_failed"
        else:
            assert trace.record("llm.request", {"body": {"seed": 0}}, required=False) is False
        after = trace.summary()
        assert after["events"] == before["events"]
        assert after["bytes"] == before["bytes"]
        assert after["last_event_sha256"] == before["last_event_sha256"]
        assert after["failure"] == "trace_write_failed"
        assert after["replayable_content"] is False
        assert "llm.request" not in trace.phases
    finally:
        trace.close()
    assert trace.path.read_bytes().startswith(original_bytes)
    assert trace.path.stat().st_size == len(original_bytes) + 7
    with pytest.raises(ValueError, match="interrompu"):
        read_verified_trace(trace.path)


def test_short_trace_write_blocks_chat_with_mock_http_transport(tmp_path):
    model = {"name": "qwen3:4b", "digest": "a" * 64,
             "details": {"quantization_level": "Q4_K_M"}}
    manifest = tmp_path / "model.json"
    manifest.write_text(json.dumps({"model": model}), encoding="utf-8")
    settings = Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {"mode": "full"},
                                  "llm": {"model": model["name"], "model_manifest": str(manifest), "seed": 0}})
    trace = ExecutionTrace(settings, "blocked-request")
    trace.stream = ShortWriteToRealFile(trace.stream)
    requests = []

    def mock_http_handler(request):
        requests.append(request.url.path)
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [model]})
        pytest.fail("La capture interrompue a autorisé un appel de génération")

    async def run_with_mock_transport():
        gateway = OllamaGateway(settings)
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, trust_env=False,
                                          transport=httpx.MockTransport(mock_http_handler))
        token = CURRENT_TRACE.set(trace)
        try:
            return [event async for event in gateway.stream(
                [{"role": "user", "content": "Quelle valeur ?"}], asyncio.Event())]
        finally:
            CURRENT_TRACE.reset(token)
            await gateway.close()
            trace.close()

    with pytest.raises(ApiError) as failure:
        asyncio.run(run_with_mock_transport())
    assert failure.value.code == "trace_write_failed"
    assert requests == ["/api/ps", "/api/tags"]
    assert trace.sequence == 0
    assert trace.summary()["replayable_content"] is False


@pytest.fixture
def existing_installation_with_mock_http(tmp_path, monkeypatch):
    """Un import déjà déclaré, avec fichiers minuscules et API native simulée."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    tokenizer = root / "tokenizer"
    tokenizer.mkdir()
    (tokenizer / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tokenizer / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "test-double-template"}), encoding="utf-8")
    gguf = root / "not-a-real-model.gguf"
    gguf.write_bytes(b"small artifact double, never imported")
    lock = {"model": "qwen3-4b-enhanced:q4km", "ollama_version": "0.35.0",
            "gguf": {"size": gguf.stat().st_size, "sha256": provisioning.file_sha256(gguf)},
            "tokenizer": {"files": {name: provisioning.file_sha256(tokenizer / name)
                                    for name in ("tokenizer.json", "tokenizer_config.json")}},
            "parameters": {"num_ctx": 8192}}
    lock_path = root / "config/enhanced-4b.lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    model = {"name": lock["model"], "digest": "a" * 64}
    manifest_path = root / "manifest.json"
    manifest = {"model": model, "source_sha256": lock["gguf"]["sha256"],
                "lock_sha256": provisioning.file_sha256(lock_path),
                "verified_inputs": provisioning.validate_inputs(lock, gguf, tokenizer)}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(root, {"llm": {"model": lock["model"], "base_url": "http://127.0.0.1:11434",
                                       "model_manifest": str(manifest_path), "tokenizer_dir": str(tokenizer)}})
    monkeypatch.setattr(provisioning, "ROOT", root)
    monkeypatch.setattr(provisioning.Settings, "load", lambda _path: settings)
    requests = []

    def mock_http_handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/api/version":
            return httpx.Response(200, json={"version": lock["ollama_version"]})
        if request.method == "GET" and request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [model]})
        pytest.fail("La vérification existante a tenté une mutation HTTP")

    original_client = httpx.Client
    monkeypatch.setattr(provisioning.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(mock_http_handler), **kwargs))

    def reject_native_import(*args, **kwargs):
        pytest.fail("La vérification existante a tenté un import natif")

    monkeypatch.setattr(provisioning.subprocess, "run", reject_native_import)
    return {"root": root, "gguf": gguf, "lock": lock, "lock_path": lock_path,
            "manifest": manifest, "manifest_path": manifest_path, "requests": requests}


def verify_existing(fixture):
    return provisioning.provision(fixture["root"] / "profile.yaml",
                                  fixture["root"] / "no-executable", fixture["gguf"])


def test_matching_existing_manifest_is_read_only_with_mock_http(existing_installation_with_mock_http):
    fixture = existing_installation_with_mock_http
    before = fixture["manifest_path"].read_bytes()
    result = verify_existing(fixture)
    assert result["status"] == "verified_existing"
    assert result["digest"] == fixture["manifest"]["model"]["digest"]
    assert fixture["manifest_path"].read_bytes() == before
    assert fixture["requests"] == [("GET", "/api/version"), ("GET", "/api/tags")]


@pytest.mark.parametrize("change", ["missing_lock", "different_lock", "changed_lock_parameters",
                                    "missing_inputs", "different_gguf_input", "different_tokenizer_input",
                                    "different_template_input"])
def test_existing_manifest_proof_mismatch_refused_without_reimport(
        existing_installation_with_mock_http, change):
    fixture = existing_installation_with_mock_http
    manifest = copy.deepcopy(fixture["manifest"])
    if change == "missing_lock":
        manifest.pop("lock_sha256")
    elif change == "different_lock":
        manifest["lock_sha256"] = "0" * 64
    elif change == "changed_lock_parameters":
        fixture["lock"]["parameters"]["num_ctx"] = 16384
        fixture["lock_path"].write_text(json.dumps(fixture["lock"]), encoding="utf-8")
    elif change == "missing_inputs":
        manifest.pop("verified_inputs")
    elif change == "different_gguf_input":
        manifest["verified_inputs"]["gguf_sha256"] = "0" * 64
    elif change == "different_tokenizer_input":
        manifest["verified_inputs"]["tokenizer_sha256"]["tokenizer.json"] = "0" * 64
    elif change == "different_template_input":
        manifest["verified_inputs"]["tokenizer_template_sha256"] = "0" * 64
    fixture["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
    before = fixture["manifest_path"].read_bytes()
    with pytest.raises(ValueError, match="différente ou incomplète"):
        verify_existing(fixture)
    assert fixture["manifest_path"].read_bytes() == before
    assert fixture["requests"] == [("GET", "/api/version"), ("GET", "/api/tags")]
