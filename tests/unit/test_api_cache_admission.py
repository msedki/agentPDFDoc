"""Real admission governor with explicit cache/memory/model substitutes; no native inference."""

import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors

from services.api.main import create_app
from services.api.settings import Settings
from services.runtime import resources
from services.runtime.resources import ResourceAdmissionError, ResourceGovernor

RESOURCES = {"initial_llm_load_peak_estimate_mib": 4352, "warm_llm_additional_peak_estimate_mib": 640,
             "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
             "generation_admission_wait_seconds": 0}
WARM = {"loaded": True, "resident": True, "additional_peak_mib": 640}
COLD = {"loaded": False, "resident": False, "additional_peak_mib": 0}


def wired_admission(tmp_path, monkeypatch, available, loaded, *, gain_per_cache=50, governing=None):
    memory = {"available_mib": available}
    calls = []
    monkeypatch.setattr(resources, "host_sample", lambda disk_root, process=None: dict(memory))
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "cache-admission-test-only")
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785},
                                  "llm": {"accelerator": "cpu"}, "resources": copy.deepcopy(RESOURCES)})

    def release(name):
        calls.append(name)
        memory["available_mib"] += gain_per_cache
        return {"state": "released", "measurement_kind": "explicit_test_substitute"}

    class CachedEmbedding(FakeEmbedding):
        def release_session(self):
            return release("embedding_session")

        def release_tokenizer(self):
            return release("embedding_tokenizer")

    class CachedTokenizer(FakeLlmTokenizer):
        def release_tokenizer(self):
            return release("llm_tokenizer")

    class Model:
        state = copy.deepcopy(loaded)
        last_state = None
        messages = None

        async def loaded_state(self):
            self.last_state = copy.deepcopy(self.state)
            return self.last_state

        async def close(self):
            pass

        async def stream(self, messages):
            calls.append("generation")
            self.messages = copy.deepcopy(messages)
            yield {"type": "delta", "text": "explicit model substitute"}

    governor = ResourceGovernor({"app": {"data_dir": str(tmp_path / "runtime")},
                                 "resources": copy.deepcopy(governing or RESOURCES)},
                                host_lock_path=tmp_path / "host-heavy.lock")
    model = Model()
    app = create_app(settings=settings, embedding=CachedEmbedding(), tokenizer=CachedTokenizer(), vectors=FakeVectors(),
                     ollama=model, governor=governor, start_jobs=False)
    return app, governor, model, memory, calls


def generate(governor, model, messages):
    async def run():
        async with governor.generation():
            return [event async for event in model.stream(messages)]
    return asyncio.run(run())


def test_warm_shortfall_releases_idle_caches_before_real_admission_and_preserves_frozen_messages(tmp_path, monkeypatch):
    _, governor, model, memory, calls = wired_admission(tmp_path, monkeypatch, 2100, WARM)
    messages = [{"role": "system", "content": "Preuves figées seulement."},
                {"role": "user", "content": "Document A : 0 V ; maximum 36 V 😀."}]
    before = json.dumps(messages, ensure_ascii=False)
    assert generate(governor, model, messages)[0]["type"] == "delta"
    assert calls == ["embedding_session", "embedding_tokenizer", "llm_tokenizer", "generation"]
    assert memory["available_mib"] == 2250
    decision = model.last_state["generation_cache_release"]
    assert decision["reason"] == "warm_admission_shortfall" and decision["resident_model"] is True
    assert decision["required_available_mib"] == 2176 and decision["additional_peak_estimate_mib"] == 640
    assert decision["host_reserve_mib"] == 1536
    assert decision["before"]["available_mib"] == 2100 and decision["after"]["available_mib"] == 2250
    assert "cold_cache_release_before" not in model.last_state and "cold_required_mib" not in decision
    assert json.dumps(messages, ensure_ascii=False) == before and model.messages == messages
    assert governor.settings == RESOURCES and governor.snapshot()["heavy_owner"] is None


@pytest.mark.parametrize("available", [2176, 2500, 5888])
def test_warm_admissible_memory_keeps_caches_even_below_the_cold_admission_floor(tmp_path, monkeypatch, available):
    _, governor, model, memory, calls = wired_admission(tmp_path, monkeypatch, available, WARM)
    assert generate(governor, model, [])
    assert calls == ["generation"] and memory["available_mib"] == available
    assert model.last_state == WARM


def test_releasing_caches_cannot_authorize_generation_if_the_real_reserve_still_fails(tmp_path, monkeypatch):
    _, governor, model, memory, calls = wired_admission(tmp_path, monkeypatch, 2100, WARM, gain_per_cache=0)
    with pytest.raises(ResourceAdmissionError) as refusal:
        generate(governor, model, [])
    assert calls == ["embedding_session", "embedding_tokenizer", "llm_tokenizer"]
    assert refusal.value.snapshot["admission"]["required_available_mib"] == 2176
    assert refusal.value.snapshot["admission"]["additional_peak_estimate_mib"] == 640
    assert memory["available_mib"] == 2100 and governor.settings == RESOURCES


@pytest.mark.parametrize("unknown", [None, {}, {"resident": True, "additional_peak_mib": 640},
                                     {"loaded": False, "resident": True, "additional_peak_mib": 640}])
def test_unknown_or_incompatible_loaded_state_keeps_the_full_cold_requirement(tmp_path, monkeypatch, unknown):
    _, governor, model, _, calls = wired_admission(tmp_path, monkeypatch, 2500, unknown)
    with pytest.raises(ResourceAdmissionError) as refusal:
        generate(governor, model, [])
    admission = refusal.value.snapshot["admission"]
    assert admission["resident_model"] is False and admission["required_available_mib"] == 5888
    assert admission["additional_peak_estimate_mib"] == 4352
    assert calls == ["embedding_session", "embedding_tokenizer", "llm_tokenizer"]
    if unknown is not None:
        assert all(model.last_state[key] == value for key, value in unknown.items())
        assert model.last_state["generation_cache_release"]["reason"] == "cold_admission_shortfall"


def test_warm_requirement_uses_loaded_increment_instead_of_a_recomputed_profile_default(tmp_path, monkeypatch):
    _, governor, model, _, calls = wired_admission(tmp_path, monkeypatch, 2300, {**WARM, "additional_peak_mib": 900})
    assert generate(governor, model, [])
    assert calls[:3] == ["embedding_session", "embedding_tokenizer", "llm_tokenizer"]
    assert model.last_state["generation_cache_release"]["required_available_mib"] == 2436


def test_cold_release_keeps_legacy_fields_and_uses_the_governors_actual_floor(tmp_path, monkeypatch):
    governing = {**RESOURCES, "admit_heavy_min_available_mib": 7000}
    _, governor, model, _, calls = wired_admission(tmp_path, monkeypatch, 6900, COLD, governing=governing)
    assert generate(governor, model, [])
    assert calls[:3] == ["embedding_session", "embedding_tokenizer", "llm_tokenizer"]
    decision = model.last_state["generation_cache_release"]
    assert decision["cold_required_mib"] == decision["required_available_mib"] == 7000
    assert decision["before"] == model.last_state["cold_cache_release_before"]
    assert decision["after"] == model.last_state["cold_cache_release_after"]
    assert decision["embedding_session"] == model.last_state["embedding_release"]
    assert decision["reason"] == "cold_admission_shortfall" and not decision["resident_model"]


def test_diagnostics_preserve_last_cold_release_when_a_later_warm_release_occurs(tmp_path, monkeypatch):
    app, governor, model, memory, _ = wired_admission(tmp_path, monkeypatch, 5800, COLD)
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        client.portal.call(governor.before_generation)
        cold = client.get("/api/v1/diagnostics", headers={"X-RAG-Control-Token": "cache-admission-test-only"}).json()
        assert cold["cold_cache_release"]["cold_required_mib"] == 5888
        model.state, memory["available_mib"] = WARM, 2100
        client.portal.call(governor.before_generation)
        warm = client.get("/api/v1/diagnostics", headers={"X-RAG-Control-Token": "cache-admission-test-only"}).json()
        assert warm["cold_cache_release"] == cold["cold_cache_release"]
        assert warm["generation_cache_release"]["reason"] == "warm_admission_shortfall"
        assert warm["generation_cache_release"]["required_available_mib"] == 2176
