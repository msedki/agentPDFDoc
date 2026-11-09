"""I4 O01–O08 : frontières réelles, mémoire/fournisseur explicitement doublés.

SQLite, FTS, extraction DOCX, catalogue, rendu, publication et gouverneur sont
réels. Embedding, vecteurs et tokenizer viennent de la fixture `rag`. Aucun
modèle, serveur natif, OCR ou épuisement réel de mémoire n'est lancé ici.
Le délai contrôlé figé vaut 1 s, avec au plus 2 s de coût de transition.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.ollama import OllamaGateway
from services.api.query import QueryService
from services.api.schemas import QueryRequest, Scope
from services.api.structured_answer import Catalogue
from services.ingestion.office.pipeline import extract_office
from services.runtime.resources import ResourceGovernor, acquire_host_heavy_lock
from tools.qualification.grounded_campaign import generate_document

DEADLINE = 1.0
OVERHEAD = 2.0
BOUND = DEADLINE + OVERHEAD
SOURCE = "Le boîtier est étanche uniquement lorsque le couvercle est fermé."
QUESTION = "Dans quelle condition le boîtier est-il étanche ?"


class ReferenceProviderDouble:
    """Sélection d'IDs seuls ; pause et terminaison contrôlées, aucune prose générée."""

    def __init__(self, behavior="complete", *, complete_json=True):
        self.behavior, self.complete_json = behavior, complete_json
        self.calls = 0
        self.paused = asyncio.Event()
        self.closed = asyncio.Event()

    async def stream(self, messages, cancel_event, output_tokens=None, *, response_format=None):
        self.calls += 1
        assert response_format is not None
        identifiers = response_format["properties"]["references"]["items"]["enum"]
        plan = json.dumps({"references": identifiers[:1], "comparisons": []})
        try:
            if self.behavior == "pause":
                yield {"type": "delta", "text": plan[:max(1, len(plan) // 2)]}
                self.paused.set()
                await asyncio.Event().wait()
            else:
                yield {"type": "delta", "text": plan if self.complete_json else plan[:-3]}
                yield {"type": "done", "finish_reason": "length" if self.behavior == "length" else "stop",
                       "metrics": {"eval_count": 12}}
        finally:
            self.closed.set()

    async def close(self):
        pass


@pytest.fixture
async def operation(rag, tmp_path, monkeypatch):
    settings, db, _, indexer, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True,
                                    "structural_reranking": True, "complementary_retrieval": True}
    settings.profile["trace"] = {"mode": "full"}
    settings.profile.setdefault("resources", {}).update(host_available_min_mib=1536,
                                        initial_llm_load_peak_estimate_mib=4352,
                                        generation_admission_wait_seconds=DEADLINE)
    path = settings.data_dir / "originals" / "operations.docx"
    checksum = generate_document({"format": "docx", "paragraphs": [SOURCE]}, path)
    imported = db.import_original(path.name, checksum, path, "docx")
    extracted = extract_office(path, tmp_path / "extraction", settings.profile, imported["version_id"], "docx")
    await indexer.index(imported["job_id"], extracted)
    governor = ResourceGovernor(settings.profile, host_lock_path=tmp_path / "only-this-test.lock")
    memory = {"available_mib": 7000}

    def controlled_sample():
        return {"available_mib": memory["available_mib"], "heavy_owner": governor._owner,
                "host_reserve_mib": governor.reserve_mib,
                "sample_provenance": "explicit test double, not observed machine memory"}

    monkeypatch.setattr(governor, "snapshot", controlled_sample)

    def force_reference_selector(self, required_documents=()):
        # I5 can render this complete, checked relation without a model. This
        # named routing double forces the provider boundary under test; it
        # preserves real source validation, admission, rendering and release.
        assert self.assess(required_documents=required_documents)["status"] == "covered"
        assert self.model_view()["reference_ids"]
        return None

    monkeypatch.setattr(Catalogue, "deterministic_plan", force_reference_selector)
    provider = ReferenceProviderDouble()
    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()), provider, settings,
                           governor=governor)
    result = SimpleNamespace(settings=settings, db=db, search=search, governor=governor, memory=memory,
                             provider=provider, service=service, imported=imported,
                             request=QueryRequest(question=QUESTION, scope=Scope(
                                 kind="documents", documentIds=[imported["document_id"]])))
    try:
        yield result
    finally:
        await service.close()
        await service.ollama.close()


async def start(workspace):
    created = await workspace.service.create_async(workspace.request)
    query_id = created["query_id"]
    return query_id, workspace.service.tasks[query_id]


async def settle(workspace, query_id, task, started):
    try:
        await asyncio.wait_for(asyncio.shield(task), BOUND)
    except TimeoutError:
        await workspace.service.cancel_async(query_id)
        await asyncio.gather(task, return_exceptions=True)
        pytest.fail("Le terminal n'est pas arrivé dans le délai contrôlé + 2 s.")
    await asyncio.sleep(0)  # Callback de retrait de la tâche, sans attente arbitraire.
    assert time.monotonic() - started <= BOUND
    assert_released(workspace)
    return workspace.service.run_detail(query_id)


def assert_released(workspace):
    service, governor = workspace.service, workspace.governor
    assert service.tasks == {} and service.cancel_events == {}
    assert not service.generation_lock.locked()
    assert not governor._heavy.locked() and governor._owner is None and governor._host_lock is None
    assert governor._generation_requests == governor._interactive_requests == 0
    assert governor.reserve_mib == 1536
    assert governor.settings["initial_llm_load_peak_estimate_mib"] == 4352
    # Vérifie le vrai verrou fichier, au-delà des attributs Python du gouverneur.
    with acquire_host_heavy_lock("qualification-released", governor.host_lock_path):
        pass


def assert_no_public_answer(workspace, query_id, terminal, code=None):
    rows = workspace.db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))
    assert not any(row["type"] in {"delta", "done"} for row in rows)
    endings = [row for row in rows if row["type"] in {"error", "cancelled", "done"}]
    assert len(endings) == 1 and endings[0]["type"] == terminal
    if code is not None:
        assert json.loads(endings[0]["data_json"])["code"] == code
    assert workspace.service.run_detail(query_id)["answer"] == ""
    assert not workspace.db.rows("SELECT * FROM messages WHERE query_id=? AND role='assistant' AND content<>''",
                                 (query_id,))


def assert_supported_success(workspace, query_id, run):
    assert run["state"] == "done" and SOURCE in run["answer"]
    assert run["metrics"]["answer_support_validation"]
    citations = workspace.db.rows("SELECT version_id,source_json FROM citations WHERE query_id=?", (query_id,))
    assert citations and all(row["version_id"] == workspace.imported["version_id"] for row in citations)
    assert any(SOURCE in json.loads(row["source_json"])["text"] for row in citations)


async def test_O01_memory_denied_before_model_without_public_answer(operation):
    operation.memory["available_mib"] = 5000  # < 4352 + 1536 ; pas d'épuisement réel.
    started = time.monotonic()
    query_id, task = await start(operation)
    run = await settle(operation, query_id, task, started)
    assert run["state"] == "error" and operation.provider.calls == 0
    assert_no_public_answer(operation, query_id, "error", "resource_admission_denied")


async def test_O02_memory_release_admits_without_lowering_reserve(operation):
    operation.memory["available_mib"] = 5000
    started = time.monotonic()
    query_id, task = await start(operation)
    while True:
        rows = operation.db.rows("SELECT data_json FROM events WHERE query_id=? AND type='status'", (query_id,))
        if any(json.loads(row["data_json"]).get("state") == "waiting_for_resources" for row in rows):
            break
        assert time.monotonic() - started < DEADLINE, "L'annonce doit précéder l'événement de libération."
        await asyncio.sleep(0.005)
    assert operation.provider.calls == 0
    operation.memory["available_mib"] = 7000  # Événement synchronisé avant la borne de 1 s.
    assert time.monotonic() - started < DEADLINE
    run = await settle(operation, query_id, task, started)
    assert operation.provider.calls == 1
    assert_supported_success(operation, query_id, run)


async def test_O03_cancel_during_retrieval_releases_before_model(operation, monkeypatch):
    reached, released = asyncio.Event(), asyncio.Event()

    async def gated_search(*args, **kwargs):
        try:
            reached.set()
            await asyncio.Event().wait()
        finally:
            released.set()

    monkeypatch.setattr(operation.search, "search", gated_search)
    query_id, task = await start(operation)
    await asyncio.wait_for(reached.wait(), DEADLINE)
    started = time.monotonic()
    await operation.service.cancel_async(query_id)
    await settle(operation, query_id, task, started)
    assert released.is_set() and operation.provider.calls == 0
    assert_no_public_answer(operation, query_id, "cancelled")


async def test_O04_cancel_private_partial_plan_releases_generation(operation):
    operation.provider.behavior = "pause"
    query_id, task = await start(operation)
    await asyncio.wait_for(operation.provider.paused.wait(), DEADLINE)
    assert operation.db.rows("SELECT * FROM events WHERE query_id=? AND type='structured_delta'", (query_id,))
    assert not operation.db.rows("SELECT * FROM events WHERE query_id=? AND type='delta'", (query_id,))
    started = time.monotonic()
    await operation.service.cancel_async(query_id)
    await settle(operation, query_id, task, started)
    assert operation.provider.closed.is_set() and operation.provider.calls == 1
    assert_no_public_answer(operation, query_id, "cancelled")


class TimeoutTransportDouble:
    """HTTPX transport factice ; vraie passerelle, identité 4B et ReadTimeout réels."""

    def __init__(self, identity):
        self.identity, self.mode, self.chat_calls = identity, "timeout", 0
        self.stream_closed = False

    def __call__(self, request):
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [self.identity]})
        assert request.url.path == "/api/chat"
        self.chat_calls += 1
        body = json.loads(request.content)
        identifiers = body["format"]["properties"]["references"]["items"]["enum"]
        plan = json.dumps({"references": identifiers[:1], "comparisons": []})
        owner = self

        class ControlledBytes(httpx.AsyncByteStream):
            async def __aiter__(self):
                content = plan if owner.mode == "complete" else plan[:-3]
                yield (json.dumps({"message": {"content": content}, "done": False}) + "\n").encode()
                if owner.mode == "timeout":
                    # Déclenchement injecté à la frontière HTTP ; aucune latence réseau réelle revendiquée.
                    await asyncio.sleep(0)
                    raise httpx.ReadTimeout("controlled transport timeout", request=request)
                yield (json.dumps({"done": True, "done_reason": "stop", "eval_count": 12}) + "\n").encode()

            async def aclose(self):
                owner.stream_closed = True

        return httpx.Response(200, stream=ControlledBytes())


async def use_timeout_gateway(workspace, tmp_path):
    identity = {"name": "qwen3-4b-enhanced:q4km", "digest": "a" * 64,
                "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M"}}
    manifest = tmp_path / "explicit-transport-double-manifest.json"
    manifest.write_text(json.dumps({"model": identity}))
    workspace.settings.profile.setdefault("llm", {}).update(model=identity["name"], model_manifest=str(manifest),
        required_parameter_size="4.0B", required_family="qwen3", required_quantization="Q4_K_M",
        idle_read_timeout_seconds=DEADLINE, residency_policy="keep")
    transport = TimeoutTransportDouble(identity)
    gateway = OllamaGateway(workspace.settings)
    await gateway.client.aclose()
    gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(transport))
    workspace.service.ollama = gateway
    return transport


async def test_O05_real_gateway_timeout_after_private_plan_has_no_public_answer(operation, tmp_path):
    transport = await use_timeout_gateway(operation, tmp_path)
    started = time.monotonic()
    query_id, task = await start(operation)
    await settle(operation, query_id, task, started)
    assert_no_public_answer(operation, query_id, "error", "ollama_timeout")
    assert transport.stream_closed and transport.chat_calls == 1, "Aucune reprise ni prose de secours."
    assert operation.db.rows("SELECT * FROM events WHERE query_id=? AND type='structured_delta'", (query_id,))


@pytest.mark.parametrize("complete_json", [False, True], ids=["partial-json", "valid-json"])
async def test_O06_finish_length_is_never_published(operation, complete_json):
    operation.provider.behavior, operation.provider.complete_json = "length", complete_json
    started = time.monotonic()
    query_id, task = await start(operation)
    await settle(operation, query_id, task, started)
    assert operation.provider.calls == 1 and operation.provider.closed.is_set()
    assert_no_public_answer(operation, query_id, "error", "structured_answer_incomplete")


async def test_O07_post_render_guard_precedes_all_public_text(operation, monkeypatch):
    render = Catalogue.render

    def corrupted(self, *args, **kwargs):
        result = render(self, *args, **kwargs)
        result["text"] += "\nAffirmation extérieure : tension garantie 999 V."
        return result

    monkeypatch.setattr(Catalogue, "render", corrupted)
    started = time.monotonic()
    query_id, task = await start(operation)
    await settle(operation, query_id, task, started)
    assert_no_public_answer(operation, query_id, "error")
    assert operation.provider.calls == 1


async def test_O08_query_after_timeout_reuses_released_application_and_governor(operation, tmp_path):
    transport = await use_timeout_gateway(operation, tmp_path)
    started = time.monotonic()
    failed_id, failed_task = await start(operation)
    await settle(operation, failed_id, failed_task, started)
    assert_no_public_answer(operation, failed_id, "error", "ollama_timeout")
    transport.mode, transport.stream_closed = "complete", False
    started = time.monotonic()
    query_id, task = await start(operation)
    run = await settle(operation, query_id, task, started)
    assert query_id != failed_id and transport.chat_calls == 2 and transport.stream_closed
    assert_supported_success(operation, query_id, run)
