"""Accélération GPU de la génération côté application (W024, W025) : repli sous le gouverneur réel, diagnostics,
indicateur de l'atelier (P7), relevé de SwapFree (M1) et poste Windows sans GPU utilisable.

Ollama est un double explicite (MockTransport) ; le gouverneur est le vrai ResourceGovernor, avec une mémoire hôte
simulée et un verrou lourd dans tmp_path. Aucun GPU, aucun service ni port réel n'est employé.
"""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import psutil
import pytest
from fastapi.testclient import TestClient
from test_api_gateways import (
    ANSWER,
    GPU_RESIDENT,
    LOAD_FAILURE,
    REFERENCE_CPU_BODY,
    REFERENCE_MESSAGES,
    ScriptedOllama,
    locked_running_model,
    ndjson,
    run_stream,
)
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors

from services.api.errors import ApiError
from services.api.main import PUBLIC_PATHS, create_app
from services.api.ollama import OllamaGateway
from services.api.settings import Settings
from services.runtime import resources
from services.runtime.accelerator import profile_accelerator, read_discovery, resolve_mode
from services.runtime.resources import ResourceAdmissionError, ResourceGovernor

ROOT = Path(__file__).resolve().parents[2]
CONTROL = "test-only-nonce"
ORIGIN = "http://127.0.0.1:8785"
# Valeurs du profil livré (config/local16.yaml) : pic de chargement à froid, pic à chaud, réserve hôte.
RESOURCES = {"initial_llm_load_peak_estimate_mib": 3456, "warm_llm_additional_peak_estimate_mib": 512,
             "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072, "generation_admission_wait_seconds": 0}


@pytest.fixture(autouse=True)
def locked_model_manifest(tmp_path):
    directory = tmp_path / ".runtime/manifests"
    directory.mkdir(parents=True)
    (directory / "ollama-model.json").write_text(json.dumps({"model": locked_running_model()}), encoding="utf-8")


def decide(monkeypatch, mode, reason):
    """Décision du superviseur transmise à l'API seule (variables restaurées par monkeypatch)."""
    monkeypatch.setenv("RAG_LLM_ACCELERATOR", mode)
    monkeypatch.setenv("RAG_LLM_ACCELERATOR_REASON", reason)


class ReleasingEmbedding(FakeEmbedding):
    """Double E5 qui compte les libérations demandées avant un chargement à froid du modèle de réponse."""
    released = 0

    def release_session(self):
        self.released += 1
        return {"state": "released", "next_reload_measurement": "pending"}


def governed_gateway(tmp_path, monkeypatch, available_mib):
    """Passerelle GPU et vrai gouverneur reliés par create_app ; mémoire disponible de l'hôte fixée à `available_mib`."""
    decide(monkeypatch, "gpu", "gpu_discovered")
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    monkeypatch.setattr(resources, "host_sample", lambda disk_root, process=None: {"available_mib": available_mib})
    requirements = []
    original = resources.admission_requirement
    def recorded(settings, owner, loaded=None):
        requirement = original(settings, owner, loaded)
        requirements.append((owner, requirement["resident_model"], requirement["required_available_mib"]))
        return requirement
    monkeypatch.setattr(resources, "admission_requirement", recorded)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "llm": {"accelerator": "auto"}, "resources": RESOURCES})
    governor = ResourceGovernor({"app": {"data_dir": str(tmp_path / "runtime")}, "resources": RESOURCES},
                                host_lock_path=tmp_path / "host-heavy.lock")
    gateway, embedding = OllamaGateway(settings), ReleasingEmbedding()
    create_app(settings=settings, embedding=embedding, vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(), ollama=gateway,
               governor=governor, start_jobs=False)
    return governor, gateway, embedding, requirements


def generate_under_lease(governor, gateway, scripted):
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
        events = []
        try:
            async with governor.generation():
                async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384):
                    events.append(event)
        except ResourceAdmissionError as refused:
            events.append(refused)
        finally:
            await gateway.close()
        return events
    return asyncio.run(scenario())


def test_fallback_after_a_warm_gpu_admission_is_not_relaunched_without_a_cold_admission(tmp_path, monkeypatch):
    # H1 : 3000 Mio suffisent au bail chaud (512 + 1536) mais pas au chargement CPU à froid (3456 + 1536).
    governor, gateway, embedding, requirements = governed_gateway(tmp_path, monkeypatch, 3000)
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER)], resident=GPU_RESIDENT)
    events = generate_under_lease(governor, gateway, scripted)
    assert isinstance(events[-1], ResourceAdmissionError) and events[-1].snapshot["admission"]["resident_model"] is False
    assert requirements == [("generation", True, 2048), ("generation", False, 4992)]
    assert len(scripted.chat_bodies) == 1 and "/api/generate" in scripted.calls
    # Les caches E5 sont libérés comme avant tout chargement à froid ; le repli reste acquis pour l'instance.
    assert embedding.released == 1
    assert gateway.describe()["mode"] == "cpu" and gateway.describe()["fallback"]["http_status"] == 500
    assert governor.snapshot()["heavy_owner"] is None and governor._generation_on_wait is None


def test_fallback_relaunches_on_cpu_once_the_cold_admission_is_granted(tmp_path, monkeypatch):
    governor, gateway, embedding, requirements = governed_gateway(tmp_path, monkeypatch, 6000)
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER)], resident=GPU_RESIDENT)
    events = generate_under_lease(governor, gateway, scripted)
    # L'événement du repli suit la nouvelle admission et précède la relance sur CPU.
    assert [event["type"] for event in events] == ["cpu_fallback", "delta", "done"]
    assert events[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": True}
    assert requirements == [("generation", True, 2048), ("generation", False, 4992)]
    assert scripted.chat_bodies[-1] == REFERENCE_CPU_BODY and embedding.released == 0


class MessageTokenizer(FakeLlmTokenizer):
    """Double du tokenizer Qwen qui compte aussi les messages, comme le constructeur de contexte l'exige."""

    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)


def question_events(tmp_path, monkeypatch, short_after_failure):
    """Question complète par l'API (vrai QueryService, vrai gouverneur, câblage de create_app) sur une instance GPU dont
    Ollama répond 500 au premier /api/chat. Si `short_after_failure`, la mémoire de l'hôte reste à 3000 Mio pendant 1 s
    après l'échec : la nouvelle admission à froid du repli (4992 Mio requis) attend une fois, puis passe."""
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    decide(monkeypatch, "gpu", "gpu_discovered")
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    failed_at = []
    def chat_500(request):
        failed_at.append(time.monotonic())
        return httpx.Response(500, json={"error": LOAD_FAILURE})
    def sample(disk_root, process=None):
        recent = short_after_failure and failed_at and time.monotonic() - failed_at[0] < 1.0
        return {"available_mib": 3000 if recent else 6000}
    monkeypatch.setattr(resources, "host_sample", sample)
    waiting = {**RESOURCES, "generation_admission_wait_seconds": 10}
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "llm": {"accelerator": "auto"}, "resources": waiting})
    scripted = ScriptedOllama([chat_500, ndjson(*ANSWER)])
    gateway = OllamaGateway(settings)
    gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
    governor = ResourceGovernor({"app": {"data_dir": str(tmp_path / "runtime")}, "resources": waiting}, host_lock_path=tmp_path / "host-heavy.lock")
    app = create_app(settings=settings, embedding=ReleasingEmbedding(), vectors=FakeVectors(), tokenizer=MessageTokenizer(), ollama=gateway,
                     governor=governor, start_jobs=False)
    control = {"X-RAG-Control-Token": CONTROL, "Origin": ORIGIN}
    with TestClient(app, base_url=ORIGIN) as client:
        payload = b"%PDF-1.7\nCCU-21 tension 72 V"
        imported = client.post("/api/v1/documents/import", headers=control, files={"files": ("one.pdf", payload, "application/pdf")}).json()
        extraction = {"fingerprint": "fixture", "sha256": hashlib.sha256(payload).hexdigest(), "page_count": 1, "status": "ready",
                      "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "text": "CCU-21 tension 72 V"}]}]}
        client.portal.call(app.state.indexer.index, imported["job_id"], extraction)
        query = client.post("/api/v1/queries", headers=control, json={"question": "Quelle tension CCU-21 ?", "scope": {"kind": "library"}}).json()
        client.get(query["events_url"], headers=control)
        rows = app.state.db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query["query_id"],))
    assert [json.loads(body)["options"].get("num_gpu") for body in scripted.chat_bodies] == [None, 0]
    return [row["type"] if row["type"] != "status" else json.loads(row["data_json"])["state"] for row in rows]


def test_status_returns_to_generating_once_a_fallback_readmission_that_waited_is_granted(tmp_path, monkeypatch):
    # Sans ce retour, l'atelier afficherait « En attente de mémoire disponible » pendant le chargement et le
    # préremplissage sur CPU, jusqu'au premier fragment de la réponse.
    events = question_events(tmp_path, monkeypatch, short_after_failure=True)
    assert events == ["queued", "searching", "sources", "generating", "waiting_for_resources", "generating", "delta", "done"]


def test_fallback_without_waiting_keeps_a_single_generating_status(tmp_path, monkeypatch):
    events = question_events(tmp_path, monkeypatch, short_after_failure=False)
    assert events == ["queued", "searching", "sources", "generating", "delta", "done"]


def test_readmission_reuses_the_lease_announcement_and_is_refused_outside_a_generation_lease(tmp_path):
    governor = ResourceGovernor({"app": {"data_dir": str(tmp_path)}}, host_lock_path=tmp_path / "host-heavy.lock")
    with pytest.raises(RuntimeError, match="hors d'un bail de génération"):
        asyncio.run(governor.readmit_generation(None))
    seen = []
    async def recorded(loaded, on_wait):
        seen.append((loaded, on_wait))
    governor._admit_generation = recorded
    def announce(sample):
        pass
    async def scenario():
        async with governor.generation(on_wait=announce):
            await governor.readmit_generation({"loaded": False})
    asyncio.run(scenario())
    assert seen == [(None, announce), ({"loaded": False}, announce)]


class UnprovisionedEmbedding(FakeEmbedding):
    """Double E5 sans modèle sur disque : /readiness le signale comme aujourd'hui sur un poste non provisionné."""

    def model_path(self):
        raise ApiError("embedding_model_missing", "Modèle E5 absent (double de test).", 503)


class SnapshotGovernor:
    """Double du gouverneur : mesures fixes ; la nouvelle admission du repli est consignée."""

    def __init__(self):
        self.readmitted = []

    def snapshot(self):
        return {"available_mib": 8000, "heavy_owner": None, "pause_requested": False}

    async def readmit_generation(self, loaded=None):
        self.readmitted.append(loaded)
        return self.snapshot()


def workspace(tmp_path, monkeypatch, scripted, decided=("gpu", "gpu_discovered"), llm=None):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    decide(monkeypatch, *decided)
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "llm": llm or {"accelerator": "auto"}})
    gateway, governor = OllamaGateway(settings), SnapshotGovernor()
    # Client de test posé avant tout appel : aucune connexion au port Ollama du profil.
    gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(scripted))
    app = create_app(settings=settings, embedding=UnprovisionedEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=gateway, governor=governor, start_jobs=False)
    return app, gateway, governor


def test_diagnostics_and_jobs_report_the_generation_device_and_its_fallback(tmp_path, monkeypatch):
    scripted = ScriptedOllama([httpx.Response(500, json={"error": LOAD_FAILURE}), ndjson(*ANSWER)], resident=GPU_RESIDENT)
    app, gateway, governor = workspace(tmp_path, monkeypatch, scripted)
    control = {"X-RAG-Control-Token": CONTROL}
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/v1/diagnostics", headers=control).json()["llm_accelerator"] == {
            "requested": "auto", "requested_source": "profile", "mode": "gpu", "reason": "gpu_discovered", "fallback": None}
        assert client.get("/api/v1/jobs", headers=control).json()["generation"] == {"device": "gpu", "fallback": False, "processor": None, "model": "qwen3.5:4b"}

        async def answer():
            return [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        events = client.portal.call(answer)
        assert events[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": True}
        assert governor.readmitted and governor.readmitted[0]["loaded"] is False
        accelerator = client.get("/api/v1/diagnostics", headers=control).json()["llm_accelerator"]
        jobs = client.get("/api/v1/jobs", headers={**control, "X-RAG-Background": "1"}).json()
    assert {key: accelerator[key] for key in ("requested", "mode", "reason")} == {"requested": "auto", "mode": "cpu", "reason": "gpu_discovered"}
    assert set(accelerator["fallback"]) == {"utc", "http_status", "error"} and accelerator["fallback"]["error"] == LOAD_FAILURE
    # Le repli décharge le modèle : son occupation n'est plus connue avant la question suivante.
    assert jobs["generation"] == {"device": "cpu", "fallback": True, "processor": None, "model": "qwen3.5:4b"}


def test_cpu_instance_reports_cpu_without_fallback(tmp_path, monkeypatch):
    app, _, _ = workspace(tmp_path, monkeypatch, ScriptedOllama([]), ("cpu", "no_gpu_discovered"))
    control = {"X-RAG-Control-Token": CONTROL}
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/v1/diagnostics", headers=control).json()["llm_accelerator"] == {
            "requested": "auto", "requested_source": "profile", "mode": "cpu", "reason": "no_gpu_discovered", "fallback": None}
        assert client.get("/api/v1/jobs", headers=control).json()["generation"] == {"device": "cpu", "fallback": False, "processor": None, "model": "qwen3.5:4b"}


GPU_SIZE = GPU_RESIDENT["size"]


@pytest.mark.parametrize("size_vram,processor", [(GPU_SIZE, "100% GPU"), (GPU_SIZE * 3 // 4, "25%/75% CPU/GPU"), (0, "100% CPU")],
                         ids=["gpu", "partiel", "processeur"])
def test_jobs_publish_the_model_placement_observed_after_a_gpu_answer(tmp_path, monkeypatch, size_vram, processor):
    """Occupation du modèle pour l'atelier : relue dans /api/ps avant chaque question et, en mode GPU, après chaque réponse ;
    /jobs, relu toutes les 3 s, ne fait aucun appel à Ollama."""
    scripted = ScriptedOllama([ndjson(*ANSWER), ndjson(*ANSWER)])
    def placing(request):
        response = scripted(request)
        if request.url.path == "/api/chat":
            scripted.resident = {**GPU_RESIDENT, "size_vram": size_vram}
        return response
    app, gateway, _ = workspace(tmp_path, monkeypatch, placing)
    control = {"X-RAG-Control-Token": CONTROL, "X-RAG-Background": "1"}

    async def answer():
        events = [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        # La relecture d'après réponse tourne hors du flux : on l'attend ici pour observer son effet.
        await asyncio.gather(*gateway.placement_reads)
        return events
    with TestClient(app, base_url=ORIGIN) as client:
        # Modèle absent avant la première question : aucune occupation observée.
        assert client.get("/api/v1/jobs", headers=control).json()["generation"] == {"device": "gpu", "fallback": False, "processor": None, "model": "qwen3.5:4b"}
        assert client.portal.call(answer)[-1]["metrics"]["llm_execution"] == {"mode": "gpu", "fallback": False}
        calls = list(scripted.calls)
        assert client.get("/api/v1/jobs", headers=control).json()["generation"] == {"device": "gpu", "fallback": False, "processor": processor, "model": "qwen3.5:4b"}
        assert client.get("/api/v1/jobs", headers=control).json()["generation"]["processor"] == processor
        assert scripted.calls == calls, "/jobs ne contacte pas Ollama"
        client.portal.call(answer)
    assert calls == ["/api/ps", "/api/tags", "/api/chat", "/api/ps"]
    # Question suivante : occupation relue avant la génération (modèle résident), puis après la réponse.
    assert scripted.calls[len(calls):] == ["/api/ps", "/api/chat", "/api/ps"]


def test_the_end_of_a_gpu_answer_does_not_wait_for_the_placement_reading(tmp_path, monkeypatch):
    """Revue J11 : un /api/ps lent après la réponse ne retarde ni l'événement done ni la fin du flux."""
    scripted = ScriptedOllama([ndjson(*ANSWER)], resident=GPU_RESIDENT)
    slow = asyncio.Event()
    async def slow_after_the_answer(request):
        if request.url.path == "/api/ps" and scripted.chat_bodies:
            await slow.wait()
        return scripted(request)
    app, gateway, _ = workspace(tmp_path, monkeypatch, slow_after_the_answer)

    async def answer():
        started = time.monotonic()
        events = [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        elapsed = time.monotonic() - started
        pending = len(gateway.placement_reads)
        slow.set()
        await asyncio.gather(*gateway.placement_reads)
        return events, elapsed, pending
    with TestClient(app, base_url=ORIGIN) as client:
        events, elapsed, pending = client.portal.call(answer)
    assert events[-1]["type"] == "done" and pending == 1 and elapsed < 1


def test_a_failed_placement_reading_after_the_answer_keeps_the_answer_and_the_last_observation(tmp_path, monkeypatch):
    scripted = ScriptedOllama([ndjson(*ANSWER)], resident=GPU_RESIDENT)
    reads = []
    def failing_after_the_answer(request):
        if request.url.path == "/api/ps" and scripted.chat_bodies:
            reads.append(request.url.path)
            return httpx.Response(500, json={"error": "indisponible"})
        return scripted(request)
    app, gateway, _ = workspace(tmp_path, monkeypatch, failing_after_the_answer)

    async def answer():
        return [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
    with TestClient(app, base_url=ORIGIN) as client:
        events = client.portal.call(answer)
        generation = client.get("/api/v1/jobs", headers={"X-RAG-Control-Token": CONTROL}).json()["generation"]
    assert [event["type"] for event in events] == ["delta", "done"] and reads == ["/api/ps"]
    assert generation == {"device": "gpu", "fallback": False, "processor": "100% GPU", "model": "qwen3.5:4b"}


def test_public_routes_never_disclose_the_generation_hardware(tmp_path, monkeypatch):
    app, _, _ = workspace(tmp_path, monkeypatch, ScriptedOllama([], resident=GPU_RESIDENT))
    with TestClient(app, base_url=ORIGIN) as client:
        public = [client.get("/api/v1/health"), client.get("/api/v1/readiness"),
                  client.get("/api/v1/session/open", follow_redirects=False), client.post("/api/v1/session/logout")]
        refused = [client.get("/api/v1/diagnostics"), client.get("/api/v1/jobs")]
    assert {response.request.url.path for response in public} == set(PUBLIC_PATHS)
    for response in public:
        text = response.text
        assert "gpu" not in text.lower() and "llm_accelerator" not in text and '"device"' not in text and '"generation"' not in text, response.request.url
    assert [response.status_code for response in refused] == [401, 401]
    assert all("gpu" not in response.text.lower() for response in refused)


@pytest.mark.parametrize("llm", [{"accelerator": "auto"}, {"accelerator": "gpu"}, {"num_gpu": 0}, {}])
def test_windows_host_without_usable_gpu_keeps_the_reference_cpu_body(tmp_path, monkeypatch, llm):
    """Chaîne du poste Windows de référence : journal réel d'Ollama (Iris Xe écarté, `id=cpu`), décision du superviseur,
    puis corps /api/chat identique octet pour octet à celui d'avant W024."""
    discovery = read_discovery(ROOT / "RAG_Local_Agents/reports/cpu-pilot-first.service.log")
    decision = resolve_mode(profile_accelerator({"llm": llm}), discovery, {"variants": {}}, platform="windows-x86_64")
    expected = "legacy_profile_cpu" if "num_gpu" in llm else "no_gpu_discovered"
    assert (decision["mode"], decision["reason"], decision["device"]) == ("cpu", expected, None)
    decide(monkeypatch, decision["mode"], decision["reason"])
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=False: 3)
    gateway = OllamaGateway(Settings(tmp_path, {"llm": llm}))
    scripted = ScriptedOllama([ndjson(*ANSWER)], resident=locked_running_model())
    events = run_stream(gateway, scripted)
    assert scripted.chat_bodies == [REFERENCE_CPU_BODY]
    # Aucun appel de plus à Ollama : l'occupation n'est relue après la réponse qu'en mode GPU.
    assert scripted.calls == ["/api/ps", "/api/chat"]
    assert events[-1]["metrics"]["llm_execution"] == {"mode": "cpu", "fallback": False}
    assert gateway.describe() == {**profile_accelerator({"llm": llm}), "mode": "cpu", "reason": expected, "fallback": None}


def test_resource_samples_record_swap_free_beside_mem_available(tmp_path, monkeypatch):
    # M1 : mémoire unifiée des Jetson ; sous Windows, la trace ne change pas.
    monkeypatch.setattr(psutil, "swap_memory", lambda: SimpleNamespace(free=2048 * 1048576 + 4000))
    sample = resources.host_sample(tmp_path)
    if sys.platform == "win32":
        assert "swap_free_mib" not in sample
    else:
        assert sample["swap_free_mib"] == 2048.0 and "available_mib" in sample


@pytest.mark.skipif(sys.platform == "win32", reason="plateforme Windows simulée depuis Linux")
def test_simulated_windows_resource_samples_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(psutil, "swap_memory", lambda: pytest.fail("aucun relevé de swap sous Windows"))
    monkeypatch.setattr(resources.sys, "platform", "win32")
    sample = resources.host_sample(tmp_path)
    assert "swap_free_mib" not in sample and sample["memory_method"].startswith("Windows working set")
