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
    """Types littéraux passés à Database.add_event ou insérés directement dans la table events, dans tout services/api.

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
            if isinstance(node.func, ast.Attribute) and node.func.attr == "add_event" and len(node.args) >= 2:
                kind = node.args[1]
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
