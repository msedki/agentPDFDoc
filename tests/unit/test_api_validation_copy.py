"""Vraie validation ASGI, SQLite temporaire et services explicitement doublés, sans réseau."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.api.errors import ApiError, request_validation_message
from services.api.main import create_app
from services.api.schemas import Scope
from services.api.settings import Settings

LIMIT_MESSAGE = "Le périmètre est limité à 1 000 documents sélectionnés. Réduisez la sélection, puis réessayez."
FALLBACK_MESSAGE = "Certains paramètres de la demande sont manquants ou incorrects. Vérifiez les champs renseignés, puis réessayez."
SYNTHETIC_TOKEN = "synthetic-validation-copy-token"


class UnusedGateway:
    async def close(self):
        pass


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    for key in ("RAG_DATA_DIR", "RAG_DB_PATH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAG_CONTROL_TOKEN", SYNTHETIC_TOKEN)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("unexpected business or network call")
        pytest.fail("La validation doit refuser avant tout appel métier ou réseau.")

    async def forbidden_async(*args, **kwargs):
        forbidden()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_async)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}})
    assert settings.data_dir == tmp_path / "runtime"
    assert settings.db_path == tmp_path / "runtime" / "app.sqlite3"
    vectors = UnusedGateway()
    vectors.query = forbidden_async
    vectors.upsert = forbidden_async
    application = create_app(settings=settings, embedding=SimpleNamespace(count=forbidden, embed=forbidden),
                             vectors=vectors, tokenizer=SimpleNamespace(count=forbidden),
                             ollama=UnusedGateway(), governor=SimpleNamespace(), start_jobs=False)
    monkeypatch.setattr(application.state.search.resolver, "resolve", forbidden)
    monkeypatch.setattr(application.state.search, "search", forbidden_async)
    monkeypatch.setattr(application.state.queries, "create", forbidden)
    assert application.state.jobs._task is None and application.state.reconciler._task is None
    return application, calls


def test_scope_list_boundary_remains_1000_entries_not_unique_documents():
    assert Scope.model_json_schema()["properties"]["documentIds"]["maxItems"] == 1000
    identifiers = ["synthetic-repeated-document"] * 1000
    assert Scope(kind="documents", documentIds=identifiers).documentIds == identifiers
    with pytest.raises(ValidationError) as refused:
        Scope(kind="documents", documentIds=[*identifiers, "synthetic-extra-document"])
    assert [(error["loc"], error["type"]) for error in refused.value.errors()] == [(("documentIds",), "too_long")]


@pytest.mark.parametrize("path", ["/api/v1/search", "/api/v1/queries"])
def test_oversized_selection_has_actionable_copy_without_business_calls(isolated_app, path):
    application, calls = isolated_app
    tables = ("documents", "document_versions", "index_generations", "jobs", "query_runs", "events")
    with TestClient(application, base_url="http://127.0.0.1:8785",
                    headers={"X-RAG-Control-Token": SYNTHETIC_TOKEN}) as client:
        before = {table: application.state.db.rows(f"SELECT * FROM {table}") for table in tables}
        response = client.post(path, json={"question": "PRIVATE_QUESTION_SENTINEL", "scope": {
            "kind": "documents", "documentIds": ["PRIVATE_DOCUMENT_SENTINEL"] * 1001}})
        assert response.status_code == 422
        body = response.json()
        assert set(body) == {"code", "message", "details", "request_id"}
        assert body["code"] == "validation_error"
        assert body["details"] == {"fields": [{"loc": ["body", "scope", "documentIds"], "type": "too_long"}]}
        assert body["request_id"] and response.headers["x-request-id"] == body["request_id"]
        assert response.headers["cache-control"] == "no-store"
        assert body["message"] == LIMIT_MESSAGE
        assert "PRIVATE_" not in response.text
        assert {table: application.state.db.rows(f"SELECT * FROM {table}") for table in tables} == before
        assert calls == []
        assert application.state.jobs._task is None and application.state.reconciler._task is None


@pytest.mark.parametrize("fields", [
    [], [{}],
    [{"loc": ["scope", "documentIds"], "type": "too_long"}],
    [{"loc": ["body", "scope", "spans"], "type": "too_long"}],
    [{"loc": ["body", "scope", "documentIds", 0], "type": "too_long"}],
    [{"loc": ["body", "scope", "documentIds"], "type": "value_error"}],
    [{"loc": ["body", "unknown"], "type": "unknown"}],
    [{"loc": ["body", "scope", "documentIds"], "type": "too_long"},
     {"loc": ["body", "question"], "type": "missing"}],
])
def test_unknown_or_multiple_errors_keep_a_fixed_fallback(fields):
    assert request_validation_message(fields) == FALLBACK_MESSAGE


def test_validation_message_ignores_received_values_and_keeps_projection_unchanged():
    field = {"loc": ["body", "scope", "documentIds"], "type": "too_long",
             "input": "PRIVATE_INPUT_SENTINEL", "msg": "PRIVATE_MESSAGE_SENTINEL",
             "ctx": {"error": ValueError("PRIVATE_CONTEXT_SENTINEL")}}
    fields = [field]
    before = repr(fields)
    assert request_validation_message(fields) == LIMIT_MESSAGE
    assert repr(fields) == before


@pytest.mark.parametrize("payload, expected_fields", [
    ({"question": {"value": "PRIVATE_VALUE_SENTINEL"}, "scope": {"kind": "library"}},
     [{"loc": ["body", "question"], "type": "string_type"}]),
    ({"question": "PRIVATE_QUESTION_SENTINEL", "scope": {"kind": "library"}, "unknown": "PRIVATE_EXTRA_SENTINEL"},
     [{"loc": ["body", "unknown"], "type": "extra_forbidden"}]),
    ({"scope": {"kind": "documents", "documentIds": ["PRIVATE_DOCUMENT_SENTINEL"] * 1001}},
     [{"loc": ["body", "question"], "type": "missing"},
      {"loc": ["body", "scope", "documentIds"], "type": "too_long"}]),
])
def test_real_validation_fallback_does_not_expose_payload(isolated_app, payload, expected_fields):
    application, calls = isolated_app
    with TestClient(application, base_url="http://127.0.0.1:8785",
                    headers={"X-RAG-Control-Token": SYNTHETIC_TOKEN}) as client:
        response = client.post("/api/v1/search", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "validation_error" and body["message"] == FALLBACK_MESSAGE
        assert body["details"] == {"fields": expected_fields}
        assert body["request_id"] == response.headers["x-request-id"]
        assert "PRIVATE_" not in response.text and calls == []


def test_controlled_application_errors_keep_their_original_message(isolated_app):
    application, calls = isolated_app

    @application.get("/api/v1/synthetic-validation-application-error")
    async def controlled_failure():
        raise ApiError("synthetic_refusal", "Refus métier synthétique conservé.", 409, {"reason": "synthetic"})

    with TestClient(application, base_url="http://127.0.0.1:8785",
                    headers={"X-RAG-Control-Token": SYNTHETIC_TOKEN}) as client:
        response = client.get("/api/v1/synthetic-validation-application-error")
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "synthetic_refusal" and body["message"] == "Refus métier synthétique conservé."
        assert body["details"] == {"reason": "synthetic"}
        assert body["request_id"] == response.headers["x-request-id"] and calls == []
