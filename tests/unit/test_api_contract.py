"""Non-dérive du contrat partagé packages/contracts/contracts.json face à l'API réelle (constat C1 du 01/10/2026).

Routes montées, types d'événements SSE émis et écoutés par l'interface, états, modes et champs des corps,
frontières du gouverneur, de l'ingestion et du lancement : le contrat doit décrire ce que le code fait.
"""
import ast
import hashlib
import importlib.util
import inspect
import json
import re
import types
import typing
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors

from services.api.db import Database
from services.api.main import create_app
from services.api.schemas import QueryRequest, Scope, SelectedSpan
from services.api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
API_SOURCES = sorted((ROOT / "services/api").glob("*.py"))
CONTRACT = json.loads((ROOT / "packages/contracts/contracts.json").read_text(encoding="utf-8"))


def alternatives(value):
    return set(value.split("|"))


class SilentOllama:
    """Double explicite : aucune passerelle Ollama n'est contactée pour énumérer les routes."""
    async def close(self):
        pass


@pytest.fixture
def app(tmp_path):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    return create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                      ollama=SilentOllama(), governor=types.SimpleNamespace(), start_jobs=False)


def test_contract_lists_exactly_the_mounted_api_routes(app):
    prefix = CONTRACT["api_prefix"]
    mounted = {f"{method} {route.path.removeprefix(prefix)}" for route in app.routes
               if isinstance(route, APIRoute) and route.path.startswith(prefix + "/") for method in route.methods}
    assert len(CONTRACT["routes"]) == len(set(CONTRACT["routes"])), "route en double dans le contrat"
    assert set(CONTRACT["routes"]) == mounted


def test_contract_public_paths_match_the_session_boundary():
    from services.api.main import PUBLIC_PATHS

    prefix = CONTRACT["api_prefix"]
    assert {prefix + path for path in CONTRACT["access"]["public"]} == set(PUBLIC_PATHS)
    assert all(route.split(" ", 1)[1].startswith(CONTRACT["access"]["control_token_only_prefix"]) for route in CONTRACT["routes"] if "/admin/" in route)


def emitted_event_types():
    """Types littéraux passés à Database.add_event (directement ou via database_call) ou insérés dans events.

    Seule l'implémentation de Database.add_event insère un type variable (son paramètre `kind`) ; tout autre
    type non littéral ferait échouer le test, car il échapperait à la comparaison avec le contrat.
    """
    found = set()
    for source in API_SOURCES:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        generic = {id(node) for function in ast.walk(tree) if isinstance(function, ast.FunctionDef) and function.name == "add_event"
                   for node in ast.walk(function)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            direct = isinstance(node.func, ast.Attribute) and node.func.attr == "add_event" and len(node.args) >= 2
            offloaded = (isinstance(node.func, ast.Name) and node.func.id == "database_call" and len(node.args) >= 3
                         and isinstance(node.args[0], ast.Attribute) and node.args[0].attr == "add_event")
            if direct or offloaded:
                kind = node.args[2 if offloaded else 1]
                assert isinstance(kind, ast.Constant) and isinstance(kind.value, str), f"type d'événement non littéral dans {source.name}:{node.lineno}"
                found.add(kind.value)
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.startswith("INSERT INTO events") and id(node) not in generic:
                values = node.args[1]
                assert isinstance(values, ast.Tuple) and isinstance(values.elts[2], ast.Constant), f"insertion d'événement non littérale dans {source.name}:{node.lineno}"
                found.add(values.elts[2].value)
    return found


def test_contract_event_types_are_those_emitted_by_the_api_and_listened_by_the_interface():
    contract = set(CONTRACT["query_events"]["types"])
    assert contract == emitted_event_types()
    # L'interface écoute la liste QUERY_EVENT_TYPES de types.ts (également comparée au contrat par contracts.test.ts).
    stream = (ROOT / "apps/web/src/lib/stream.ts").read_text(encoding="utf-8")
    assert re.search(r"for \(const type of QUERY_EVENT_TYPES\) stream\.addEventListener\(type,", stream), \
        "stream.ts n'écoute plus la liste QUERY_EVENT_TYPES"
    types = (ROOT / "apps/web/src/lib/types.ts").read_text(encoding="utf-8")
    listened = re.search(r"export const QUERY_EVENT_TYPES = \[([^\]]*)\]", types)
    assert listened, "liste QUERY_EVENT_TYPES introuvable dans apps/web/src/lib/types.ts"
    assert set(re.findall(r'"([a-z_]+)"', listened.group(1))) == contract


@pytest.mark.parametrize("expression", ["db.add_event('q', 'status', {})", "database_call(db.add_event, 'q', 'status', {})"])
def test_event_oracle_recognizes_direct_and_offloaded_literal_types(tmp_path, monkeypatch, expression):
    source = tmp_path / "literal.py"
    source.write_text(expression, encoding="utf-8")
    monkeypatch.setitem(globals(), "API_SOURCES", [source])
    assert emitted_event_types() == {"status"}


@pytest.mark.parametrize("expression", ["db.add_event('q', dynamic, {})", "database_call(db.add_event, 'q', dynamic, {})"])
def test_event_oracle_keeps_refusing_dynamic_types_in_direct_and_offloaded_calls(tmp_path, monkeypatch, expression):
    source = tmp_path / "dynamic.py"
    source.write_text(expression, encoding="utf-8")
    monkeypatch.setitem(globals(), "API_SOURCES", [source])
    with pytest.raises(AssertionError, match="type d'événement non littéral"):
        emitted_event_types()


def literal_states(table):
    """États littéraux écrits par le SQL de services/api pour une table : `state='x'` dans un UPDATE, valeurs d'un INSERT."""
    states = set()
    for source in API_SOURCES:
        text = source.read_text(encoding="utf-8")
        for statement in re.findall(rf"UPDATE {table} SET [^\"]*", text):
            states |= set(re.findall(r"\bstate='([a-z_]+)'", statement))
        for statement in re.findall(rf"INSERT INTO {table}\([^\"]*", text):
            states |= set(re.findall(r"'([a-z_]+)'", statement))
    return states


def test_contract_document_states_are_the_states_the_api_produces():
    assert alternatives(CONTRACT["document"]["state"]) == Database.DOCUMENT_STATES
    assert set(Database.JOB_TO_DOCUMENT_STATE.values()) <= Database.DOCUMENT_STATES
    assert literal_states("documents") <= Database.DOCUMENT_STATES
    assert {"paused", "cancelled"} <= Database.DOCUMENT_STATES


def test_contract_job_states_are_the_states_the_api_produces():
    assert alternatives(CONTRACT["job"]["state"]) == Database.JOB_STATES
    assert set(Database.JOB_TO_DOCUMENT_STATE) <= Database.JOB_STATES
    assert Database.SUSPENDED_JOB_STATES <= Database.JOB_STATES
    assert literal_states("jobs") <= Database.JOB_STATES


def test_contract_query_request_matches_the_validated_body():
    request = CONTRACT["query_request"]
    assert set(request) == set(QueryRequest.model_fields)
    assert alternatives(request["mode"]) == set(typing.get_args(QueryRequest.model_fields["mode"].annotation))
    base = {"question": "q", "scope": {"kind": "library"}}
    for key in request["focus"]:
        assert QueryRequest(**base, focus={key: "valeur"}).focus == {key: "valeur"}
    with pytest.raises(ValidationError):
        QueryRequest(**base, focus={"inconnu": "valeur"})
    assert set(CONTRACT["scope"]) == set(Scope.model_fields)
    assert set(CONTRACT["scope"]["spans"][0]) == set(SelectedSpan.model_fields)


def test_contract_health_response_matches_the_public_probe(app):
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        health = client.get("/api/v1/health").json()
    assert set(health) == set(CONTRACT["health_response"])
    assert set(health["commands"]) == set(CONTRACT["health_response"]["commands"])
    # Chaque description du contrat cite les deux formes livrées, dont celle que ce poste annonce réellement.
    for action, described in CONTRACT["health_response"]["commands"].items():
        assert f".\\rag.ps1 {action}" in described and f"./rag.sh {action}" in described, action
        assert health["commands"][action] in described, action
    # Installation par le kit Linux (R26-KIT-04) : lanceur atelier de la destination, champ launcher décrit par le contrat.
    from services.runtime.platforms import INSTALLED_ACTIONS, MODEL_ACTIONS

    for action, described in CONTRACT["health_response"]["commands"].items():
        assert f"<destination>/atelier {INSTALLED_ACTIONS[action]}" in described, action
        # --modele : seulement pour les actions qui choisissent le profil (ouvrir, diagnostic).
        assert ("--modele <tag>" in described) is (action in MODEL_ACTIONS), action
    launcher = CONTRACT["health_response"]["launcher"]
    assert set(health["launcher"]) == set(launcher) == {"kind", "menu"}
    assert launcher["kind"].split(":", 1)[0].split("|") == ["installation", "projet"]
    assert launcher["menu"].startswith("string|null:") and "Atelier documentaire" in launcher["menu"]
    assert health["launcher"] == {"kind": "projet", "menu": None}


def test_contract_reindex_outcomes_are_those_of_the_api_for_each_last_job_state(tmp_path, monkeypatch):
    """Revues W1 et J5 : la réponse de POST /documents/{id}/reindex selon l'état du dernier travail de la version.

    `resume_required` n'accompagne qu'un travail `paused` ; `pausing` est refusé (409 `job_pausing`, aucun travail
    créé) ; `cancelling` n'empêche pas un travail neuf. Chaque état de travail est exercé sur l'API réelle.
    """
    from fastapi.testclient import TestClient

    nonce = "test-only-contract-nonce"
    monkeypatch.setenv("RAG_CONTROL_TOKEN", nonce)
    outcomes, fields = CONTRACT["reindex_outcomes"], CONTRACT["reindex_response"]
    covered = [state for key in outcomes for state in alternatives(key)]
    assert len(covered) == len(set(covered)), "état de travail décrit deux fois"
    assert set(covered) == Database.JOB_STATES
    # `job_state` et `resume_required` ne sont annoncés que pour les états dont l'issue les renvoie.
    resumable = {state for key, outcome in outcomes.items() if "resume_required" in alternatives(outcome.get("fields", "")) for state in alternatives(key)}
    assert alternatives(fields["job_state"].split(",", 1)[0]) == resumable == {"paused"}
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=SilentOllama(), governor=types.SimpleNamespace(), start_jobs=False)
    with TestClient(app, base_url="http://127.0.0.1:8785", headers={"X-RAG-Control-Token": nonce}) as client:
        db = app.state.db
        for key, outcome in outcomes.items():
            for state in sorted(alternatives(key)):
                imported = db.import_original(f"contract/{state}.pdf", hashlib.sha256(state.encode()).hexdigest(), f"{state}.pdf")
                db.execute("UPDATE jobs SET state=?,stage=? WHERE id=?", (state, state, imported["job_id"]))
                answer = client.post(f"/api/v1/documents/{imported['document_id']}/reindex")
                body = answer.json()
                jobs = [row["id"] for row in db.rows("SELECT id FROM jobs WHERE document_id=? ORDER BY created_at,rowid", (imported["document_id"],))]
                assert answer.status_code == outcome["status"], (state, body)
                if outcome["status"] == 409:
                    error = outcome["error"]
                    assert set(body) == set(error) == set(CONTRACT["error"]), state
                    assert body["code"] == error["code"] == "job_pausing" and body["message"], state
                    assert set(body["details"]) == set(error["details"]) and error["details"]["job_state"] == state
                    assert body["details"] == {"job_id": imported["job_id"], "version_id": imported["version_id"], "job_state": state}
                    assert jobs == [imported["job_id"]], f"{state} : aucun travail ne doit être créé"
                    continue
                assert set(body) == alternatives(outcome["fields"]) and set(body) <= set(fields), state
                assert body["reused"] is outcome["reused"], state
                if outcome["reused"]:
                    assert body["job_id"] == imported["job_id"] and jobs == [imported["job_id"]], state
                else:
                    assert body["job_id"] != imported["job_id"] and jobs == [imported["job_id"], body["job_id"]], state
                    assert body["version_id"] == imported["version_id"], state
                if "resume_required" in body:
                    assert (body["job_state"], body["resume_required"], body["version_id"]) == (state, True, imported["version_id"])


def test_contract_import_outcomes_are_those_of_the_api_for_each_last_job_state(tmp_path, monkeypatch):
    """Ronde 4 : réimport d'un contenu identique au même chemin selon l'état du dernier travail de sa version.

    Même règle que la réindexation : `resume_required` n'accompagne qu'un travail `paused`, le seul que
    POST /jobs/{job_id}/resume accepte ; `pausing` est renvoyé avec son état, sans travail créé ni reprise annoncée ;
    `cancelling` n'empêche pas un travail neuf. Chaque état est exercé par la vraie route d'import.
    """
    from fastapi.testclient import TestClient

    nonce = "test-only-contract-nonce"
    monkeypatch.setenv("RAG_CONTROL_TOKEN", nonce)
    outcomes, response = CONTRACT["import_outcomes"], CONTRACT["import_response"]
    entry = response["imports"][0]
    covered = [state for key in outcomes for state in alternatives(key)]
    assert len(covered) == len(set(covered)), "état de travail décrit deux fois"
    assert set(covered) == Database.JOB_STATES
    returned_with_state = {state for key, outcome in outcomes.items() if "job_state" in alternatives(outcome["fields"]) for state in alternatives(key)}
    resumable = {state for key, outcome in outcomes.items() if "resume_required" in alternatives(outcome["fields"]) for state in alternatives(key)}
    assert alternatives(entry["job_state"].split(",", 1)[0]) == returned_with_state == Database.SUSPENDED_JOB_STATES == {"paused", "pausing"}
    assert resumable == {"paused"} and entry["resume_required"].startswith("true with job_state paused only")
    # Avec un seul fichier, les champs de imports[0] sont repris à la racine de la réponse.
    repeated = [key for key in response if key != "imports"]
    assert len(repeated) == 1 and alternatives(repeated[0]) == set(entry)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=SilentOllama(), governor=types.SimpleNamespace(), start_jobs=False)

    def upload(client, *named):
        files = [("files", (Path(path).name, payload, "application/pdf")) for path, payload in named]
        return client.post("/api/v1/documents/import", files=files, data={"relative_paths": json.dumps([path for path, _ in named])})

    with TestClient(app, base_url="http://127.0.0.1:8785", headers={"X-RAG-Control-Token": nonce}) as client:
        db = app.state.db
        for key, outcome in outcomes.items():
            for state in sorted(alternatives(key)):
                named = (f"contract/{state}.pdf", b"%PDF-1.7\ncontract " + state.encode())
                imported = upload(client, named).json()["imports"][0]
                db.execute("UPDATE jobs SET state=?,stage=? WHERE id=?", (state, state, imported["job_id"]))
                answer = upload(client, named)
                body = answer.json()
                jobs = [row["id"] for row in db.rows("SELECT id FROM jobs WHERE document_id=? ORDER BY created_at,rowid", (imported["document_id"],))]
                assert answer.status_code == outcome["status"] == 202, (state, body)
                assert len(body["imports"]) == 1 and set(body) == {"imports", *body["imports"][0]}, state
                again = body["imports"][0]
                assert {name: body[name] for name in again} == again, state
                assert set(again) == alternatives(outcome["fields"]) and set(again) <= set(entry), state
                assert again["reused"] is outcome["reused"], state
                assert (again["document_id"], again["version_id"]) == (imported["document_id"], imported["version_id"]), state
                if outcome["reused"]:
                    assert again["job_id"] == imported["job_id"] and jobs == [imported["job_id"]], state
                else:
                    assert again["job_id"] != imported["job_id"] and jobs == [imported["job_id"], again["job_id"]], state
                    assert db.one("SELECT state FROM jobs WHERE id=?", (again["job_id"],))["state"] == "queued", state
                if "job_state" in again:
                    assert again["job_state"] == state, state
                    assert again.get("resume_required", False) is (state == "paused"), state
        # Plusieurs fichiers : un travail en cours de mise en pause n'empêche pas l'import des autres.
        pausing = ("contract/pausing.pdf", b"%PDF-1.7\ncontract pausing")
        batch = upload(client, pausing, ("contract/fresh.pdf", b"%PDF-1.7\ncontract fresh"))
        assert batch.status_code == 202 and "document_id" not in batch.json()
        first, second = batch.json()["imports"]
        assert (first["job_state"], first["reused"], "resume_required" in first) == ("pausing", True, False)
        assert second["reused"] is False and set(second) == {"document_id", "version_id", "job_id", "reused"}


def test_contract_governor_boundary_matches_the_resource_governor():
    from services.runtime.resources import ResourceGovernor

    interface = CONTRACT["governor_interface"]
    assert list(inspect.signature(ResourceGovernor.__init__).parameters)[1:] == interface["constructor"]
    for name in interface["methods"]:
        assert callable(getattr(ResourceGovernor, name, None)), name
    for name in interface["async_context_managers"]:
        assert callable(getattr(ResourceGovernor, name, None)), name
    for name in interface["methods"] + interface["async_context_managers"] + interface["hooks_set_by_api"]:
        assert name in CONTRACT["governor_boundary"], name
    main = (ROOT / "services/api/main.py").read_text(encoding="utf-8")
    for hook in interface["hooks_set_by_api"]:
        assert f"governor.{hook} =" in main, hook


def test_contract_ingestion_boundary_matches_the_ingestion_package():
    import services.ingestion as ingestion

    interface = CONTRACT["ingestion_interface"]
    for name in ("preflight_pdf", "extraction_fingerprint", "extract_window", "extract_pdf"):
        assert list(inspect.signature(getattr(ingestion, name)).parameters) == interface[name], name
    assert importlib.util.find_spec(interface["worker_module"]) is not None
    jobs = (ROOT / "services/api/jobs.py").read_text(encoding="utf-8")
    assert f'"-m", "{interface["worker_module"]}"' in jobs


def test_contract_integration_entry_matches_create_app_and_the_real_launcher():
    interface = CONTRACT["integration_interface"]
    assert list(inspect.signature(create_app).parameters) == interface["create_app_parameters"]
    module = importlib.util.find_spec(interface["launch_module"])
    assert module is not None and module.origin
    assert f'"{interface["asgi_application"]}"' in Path(module.origin).read_text(encoding="utf-8")
    assert "python -m uvicorn" not in CONTRACT["integration_entry"]
    assert interface["launch_module"] in CONTRACT["integration_entry"]


def test_contract_generation_accelerator_fields_match_the_api(tmp_path, monkeypatch):
    """W025 : `llm_accelerator` des diagnostics, champ `generation` de GET /jobs (P7) et `metrics.llm_execution`."""
    import asyncio

    import httpx
    from fastapi.testclient import TestClient
    from test_api_gateways import (
        ANSWER,
        GPU_RESIDENT,
        REFERENCE_MESSAGES,
        ScriptedOllama,
        locked_running_model,
        ndjson,
    )

    from services.api.ollama import OllamaGateway
    from services.runtime.accelerator import ACCELERATOR_VALUES, REASON_TEXTS

    (tmp_path / ".runtime/manifests").mkdir(parents=True)
    (tmp_path / ".runtime/manifests/ollama-model.json").write_text(json.dumps({"model": locked_running_model()}), encoding="utf-8")
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    monkeypatch.setenv("RAG_LLM_ACCELERATOR", "gpu")
    monkeypatch.setenv("RAG_LLM_ACCELERATOR_REASON", "gpu_discovered")
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "llm": {"accelerator": "auto"}})
    gateway = OllamaGateway(settings)
    gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(ScriptedOllama([ndjson(*ANSWER)], resident=GPU_RESIDENT)))
    governor = types.SimpleNamespace(snapshot=lambda: {"available_mib": 8000, "pause_requested": False})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=gateway, governor=governor, start_jobs=False)
    control = {"X-RAG-Control-Token": "test-only-nonce"}
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        accelerator = client.get("/api/v1/diagnostics", headers=control).json()["llm_accelerator"]
        jobs = client.get("/api/v1/jobs", headers=control).json()

        async def answer():
            return [event async for event in gateway.stream(REFERENCE_MESSAGES, asyncio.Event(), 384)]
        done = client.portal.call(answer)[-1]
    described = CONTRACT["diagnostics_llm_accelerator"]
    assert set(accelerator) == set(described) - {"rule"}
    assert alternatives(described["requested"]) == set(ACCELERATOR_VALUES)
    assert alternatives(described["reason"]) == set(REASON_TEXTS) | {"null"}
    assert set(described["fallback"]) - {"null"} == {"utc", "http_status", "error"}
    assert set(jobs) == set(CONTRACT["jobs_response"])
    assert set(jobs["generation"]) == set(CONTRACT["jobs_response"]["generation"]) - {"null"}
    assert alternatives(CONTRACT["jobs_response"]["generation"]["device"]) == {"gpu", "cpu"} == alternatives(described["mode"])
    # Occupation observée du modèle : colonne PROCESSOR d'`ollama ps`, dont le contrat cite chaque forme.
    processor = CONTRACT["jobs_response"]["generation"]["processor"]
    assert processor.startswith("string|null:") and jobs["generation"]["processor"] in (None, "100% GPU")
    for label in ("100% GPU", "100% CPU", "<cpu>%/<gpu>% CPU/GPU", "Unknown"):
        assert label in processor, label
    execution = CONTRACT["query_events"]["done_data"]["metrics"]["llm_execution"]
    assert set(done["metrics"]["llm_execution"]) == set(execution) - {"rule"} and alternatives(execution["mode"]) == {"gpu", "cpu"}
    # `mode` est le mode demandé à Ollama pour la réponse, pas l'occupation observée, publiée à part.
    assert "requested from Ollama" in execution["rule"] and "jobs_response.generation.processor" in execution["rule"]


def test_contract_llm_execution_is_absent_from_an_abstention_that_calls_no_model(tmp_path, monkeypatch):
    """Question sans preuve dans le périmètre : `done` sans appel au modèle, donc sans `metrics.llm_execution`."""
    import httpx
    from fastapi.testclient import TestClient
    from test_api_gateways import locked_running_model

    from services.api.ollama import OllamaGateway

    (tmp_path / ".runtime/manifests").mkdir(parents=True)
    (tmp_path / ".runtime/manifests/ollama-model.json").write_text(json.dumps({"model": locked_running_model()}), encoding="utf-8")
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "test-only-nonce")
    monkeypatch.setenv("RAG_LLM_ACCELERATOR", "gpu")
    monkeypatch.setenv("RAG_LLM_ACCELERATOR_REASON", "gpu_discovered")
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, "llm": {"accelerator": "auto"}})
    gateway = OllamaGateway(settings)
    gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(lambda request: pytest.fail("aucun appel au modèle")))
    governor = types.SimpleNamespace(begin_interactive=lambda: None, finish_interactive=lambda: None,
                                     snapshot=lambda: {"available_mib": 8000, "heavy_owner": None, "pause_requested": False})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=gateway, governor=governor, start_jobs=False)
    control = {"X-RAG-Control-Token": "test-only-nonce", "Origin": "http://127.0.0.1:8785"}
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        query = client.post("/api/v1/queries", headers=control, json={"question": "Quelle tension ?", "scope": {"kind": "library"}}).json()
        client.get(query["events_url"], headers=control)
        done = app.state.db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query["query_id"],))
    metrics = json.loads(done["data_json"])["metrics"]
    assert metrics["model_called"] is False and "llm_execution" not in metrics
    rule = CONTRACT["query_events"]["done_data"]["metrics"]["llm_execution"]["rule"]
    assert "only when the model was called (model_called true)" in rule


def test_contract_identifier_coverage_states_are_those_the_context_builder_assigns():
    """États de `metrics.identifier_coverage_states` : valeurs littérales affectées par ContextBuilder.build (D04.7)."""
    described = CONTRACT["query_events"]["done_data"]["metrics"]["identifier_coverage_states"]
    tree = ast.parse((ROOT / "services/api/context.py").read_text(encoding="utf-8"))

    def outcomes(value):
        """Valeurs possibles d'une affectation : littéral, ou branches d'une expression conditionnelle."""
        if isinstance(value, ast.IfExp):
            return outcomes(value.body) | outcomes(value.orelse)
        assert isinstance(value, ast.Constant) and isinstance(value.value, str), f"état non littéral à la ligne {value.lineno} de context.py"
        return {value.value}
    assigned = set().union(*(outcomes(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "states" for target in node.targets)))
    assert alternatives(described["<identifier>"]) == assigned
    assert {"covered", "identifier_present_no_answer_evidence", "identifier_present_languages_differ"} <= assigned
    # L'état des langues différentes n'affirme ni réponse ni absence : aucun avertissement ne l'accompagne.
    assert "neither an answer nor its absence" in described["rule"] and "no warning" in described["rule"]


def test_contract_accelerator_reason_without_the_supervisor_decision_matches_the_api(tmp_path, monkeypatch):
    """Sans décision du superviseur, un profil en CPU imposé garde la raison tirée du profil ; auto et gpu donnent null."""
    monkeypatch.delenv("RAG_LLM_ACCELERATOR", raising=False)
    monkeypatch.delenv("RAG_LLM_ACCELERATOR_REASON", raising=False)
    observed = {json.dumps(llm, sort_keys=True): Settings(tmp_path, {"llm": llm}).llm_accelerator["reason"]
                for llm in ({"accelerator": "cpu"}, {"num_gpu": 0}, {"accelerator": "auto"}, {"accelerator": "gpu"}, {})}
    assert observed == {'{"accelerator": "cpu"}': "imposed_by_profile", '{"num_gpu": 0}': "legacy_profile_cpu",
                        '{"accelerator": "auto"}': None, '{"accelerator": "gpu"}': None, "{}": None}
    rule = CONTRACT["diagnostics_llm_accelerator"]["rule"]
    assert "reason is imposed_by_profile or legacy_profile_cpu" in rule and "null for an auto or gpu profile started without" in rule


def test_contract_source_extraction_methods_are_the_ingestion_vocabulary():
    """R26-OCR-01 : valeurs de `extraction_methods` = valeurs que rend `source_method` de l'ingestion, plus `unknown` d'office."""
    from services.api.scope import UNKNOWN_METHOD
    tree = ast.parse((ROOT / "services/ingestion/docling_adapter.py").read_text(encoding="utf-8"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "source_method")

    def returned(value):
        if isinstance(value, ast.IfExp):
            return returned(value.body) | returned(value.orelse)
        assert isinstance(value, ast.Constant) and isinstance(value.value, str), f"méthode non littérale à la ligne {value.lineno}"
        return {value.value}
    produced = set().union(*(returned(node.value) for node in ast.walk(function) if isinstance(node, ast.Return) and node.value is not None))
    described = CONTRACT["source"]
    assert alternatives(described["extraction_methods"][0]) == alternatives(described["block_extraction_method"]) == produced | {UNKNOWN_METHOD}
    assert "never native" in described["extraction_provenance_rule"] and 'read it as extraction_methods ["unknown"]' in described["extraction_provenance_rule"]


def test_contract_r26_warning_fields_match_the_warnings_built_by_the_api():
    """Champs des avertissements R26 : ceux que construisent réellement retrieval.py et claims.py."""
    from services.api.claims import answer_warnings
    from services.api.retrieval import (
        PARTIAL_EXTRACTION_MESSAGE,
        dense_identity_warning,
        ocr_evidence_warnings,
    )
    described = CONTRACT["query_events"]["warning_data"]
    built = ocr_evidence_warnings([{"source_id": "S001", "document_id": "A", "document_name": "a.pdf", "extraction_methods": ["mixed"]}])
    built.append(dense_identity_warning([{"document_id": "A", "document_name": "a.pdf", "generation_id": "g"}]))
    built += answer_warnings("Selon S001, la pression est de 9 bar.", [{"source_id": "S001", "text": "Pression 3 bar"}])
    built += answer_warnings("Pression 2.7 bar [S001].", [{"source_id": "S001", "text": "QV-01"}, {"source_id": "S002", "text": "2.7 bar"}])
    built.append({"code": "partial_extraction", "document_id": "A", "message": PARTIAL_EXTRACTION_MESSAGE})
    by_code = {warning["code"]: warning for warning in built}
    assert set(by_code) == set(described) - {"code", "message", "rule"}
    for code, warning in by_code.items():
        assert set(warning) == alternatives(described[code]["fields"]), code
        for item in warning.get("values", []):
            assert set(item) == set(described[code]["values"][0]), code
    claims = (ROOT / "services/api/claims.py").read_text(encoding="utf-8")
    assert set(re.findall(r'"code": "([a-z_]+)"', claims)) <= set(described)


def test_contract_readiness_dense_index_fields_are_those_of_the_api(tmp_path):
    """R26-IDX-02 : `dense_index` et `documents_to_reindex` de GET /readiness, valeurs possibles comprises."""
    from fastapi.testclient import TestClient

    from services.api.embedding import EmbeddingService
    from services.api.retrieval import DenseCoverage
    described = CONTRACT["readiness_dense_index"]
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    # Vrai EmbeddingService jamais chargé (artefacts absents) ; vecteurs, tokenizer, génération et gouverneur en doubles.
    app = create_app(settings=settings, embedding=EmbeddingService(settings), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=SilentOllama(), governor=types.SimpleNamespace(), start_jobs=False)
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        body = client.get("/api/v1/readiness").json()
    assert {"dense_index", "documents_to_reindex"} <= set(body) and isinstance(body["documents_to_reindex"], list)
    assert body["dense_index"] in alternatives(described["dense_index"])
    source = inspect.getsource(DenseCoverage.status) + (ROOT / "services/api/main.py").read_text(encoding="utf-8")
    produced = set(re.findall(r'"(complete|dense_migration_incomplete|unverifiable|not_applicable)"', source))
    assert produced == alternatives(described["dense_index"])
    assert "non blocking" in described["rule"] and "behind the session" in described["rule"]
