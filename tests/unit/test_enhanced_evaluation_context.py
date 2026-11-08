"""Real isolated SQLite/OOXML and ASGI; every model/transport is an explicit double."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from test_api_storage import import_fixture
from test_enhanced_retrieval import enable, range_fixture
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.comparison import evaluate_context, selector_identity
from services.api.context import ContextBuilder
from services.api.main import create_app
from services.api.retrieval import SearchService


class NoGeneration:
    async def stream(self, *args, **kwargs):
        pytest.fail("An independent context diagnostic cannot call the model")
        yield

    async def close(self):
        pass


class DiagnosticGovernor:
    def begin_interactive(self):
        pass

    def finish_interactive(self):
        pass


@pytest.mark.parametrize("document_format", ["pdf", "xlsx"])
@pytest.mark.parametrize("contract", [False, True])
def test_context_diagnostics_share_format_contract_selection_and_mark_no_generation(rag, monkeypatch, document_format, contract):
    settings, db, embedding, indexer, resolver, search = rag
    enable(settings, answer_contract=contract, complementary_retrieval=True)
    if document_format == "xlsx":
        scope = range_fixture(rag).scope
        question = "Quelles sont les valeurs de B5 et B6 ?"
    else:
        imported, _ = import_fixture((settings, db, search.vectors, indexer), text="Supply operating voltage: minimum 0 V; maximum 36 V.")
        scope = {"kind": "documents", "documentIds": [imported["document_id"]]}
        question = "Quelle est la plage de tension de fonctionnement ?"

    async def forbidden_refinement(*args, **kwargs):
        pytest.fail("Independent context evaluation must not perform adaptive retrieval")

    monkeypatch.setattr(SearchService, "refine_once", forbidden_refinement)
    builds = []
    original = ContextBuilder.build

    def captured(self, *args, **kwargs):
        builds.append(kwargs.get("structured"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ContextBuilder, "build", captured)
    comparison = asyncio.run(evaluate_context({"question": question, "scope_resolved": scope},
        db, resolver, search, CharTokenizer(), settings))
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "isolated-context-test")
    app = create_app(settings=settings, embedding=embedding, vectors=search.vectors,
        tokenizer=CharTokenizer(), ollama=NoGeneration(), governor=DiagnosticGovernor(), start_jobs=False)
    with TestClient(app, base_url="http://127.0.0.1:8785") as client:
        response = client.post("/api/v1/admin/evaluation/context",
            headers={"X-RAG-Control-Token": "isolated-context-test"}, json={"question": question, "scope": scope})
        assert response.status_code == 200, response.text
        api = response.json()

    assert len(builds) == 2
    for builder in builds:
        if contract or document_format == "xlsx":
            assert builder is not None and builder.enforce_contract is contract
            assert builder.question == (question if contract else None)
        else:
            assert builder is None
    assert api["messages_sha256"] == comparison["messages_sha256"]
    assert api["context_sources"] == comparison["context_sources"]
    assert api["selector_sha256"] == selector_identity()
    for result in (api, comparison):
        assert result["model_called"] is False
        assert result["evaluation_kind"] == "independent_context_build"
        assert result["generation_request_captured"] is False
        assert result["metrics"]["complementary_retrieval"] == {
            "configured": True, "attempted": False, "performed": False, "reason": "context_only_evaluation"}
        assert ("context_assessment" in result["metrics"]) is contract
        if contract or document_format == "xlsx":
            assert result["metrics"]["structured_answer"]["status"] == "context_only"
            assert result["metrics"]["structured_answer"] == api["metrics"]["structured_answer"]
        else:
            assert "structured_answer" not in result["metrics"]
        if document_format == "xlsx":
            assert result["metrics"]["evidence_bundles"]["range_cell_coverage"] == 1
            text = result["context_sources"][0]["text"]
            assert "B5 (value) : 0" in text and "B6 (value) : 36" in text
            assert "OUTSIDE-SECRET" not in str(result)
    assert db.one("SELECT count(*) AS n FROM query_runs")["n"] == 0
