"""An unanalysed question keeps its diagnostic through the public route.

SQLite/OOXML and publication are real; vectors, embeddings and token counts use
existing doubles. The gateway must never run for these general questions.
"""

import asyncio
import hashlib
import json

import pytest
from docx import Document
from test_enhanced_answers import catalogue, excerpt, render
from test_grounded_query import run, service_for
from test_office_rag import rag as rag

from services.api.schemas import QueryRequest, Scope
from services.ingestion.office.pipeline import extract_office

QUESTION = "Quelle propriété du carter est décrite ?"
TEXT = "Le carter reste verrouillé pendant le rinçage."
LIMIT = {"code": "evidence_coverage_incomplete", "missing_relation_variants": 1}


@pytest.mark.parametrize("limited", [False, True])
def test_general_question_keeps_analysis_limit_after_its_projection_is_empty(limited):
    cat = catalogue(QUESTION, [excerpt("R001", TEXT)])
    cat.required_documents = ("document-1",)
    if limited:
        cat.retrieval_limitations = [LIMIT]
    assert cat.assess()["kind"] == "general"
    assert cat.assess()["status"] == "unassessed"
    assert cat.model_view()["reference_ids"] == []
    assert cat.deterministic_plan().references == []
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "unassessed" and not assessment["missing"]
    assert assessment.get("retrieval_limitations", []) == ([LIMIT] if limited else [])
    assert not assessment["matched_relations"] and not assessment["obligations"]
    assert not result["citation_spans"] and result["effective_plan"]["references"] == []
    assert "analyse littérale" in result["text"] and "Restitution partielle" not in result["text"]
    assert "réponse reste partielle" not in result["text"]
    assert ("Le budget de recherche" in result["text"]) == limited
    assert TEXT not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("limited", [False, True])
def test_recognized_question_still_reports_an_actually_missing_document(limited):
    cat = catalogue("Quelle est la tension nominale du DEV728 ?", [
        excerpt("R001", "DEV728 nominal voltage: 2.2 V.")])
    cat.required_documents = ("document-1", "document-2")
    if limited:
        cat.retrieval_limitations = [LIMIT]
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert any(item["requirement"] == "requested_document" and item["document_id"] == "document-2"
               for item in assessment["missing"])
    assert any(item["requirement"] == "retrieval_coverage_incomplete" for item in assessment["missing"]) == limited
    assert "2.2 V" in result["text"] and result["citation_spans"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("limited", [False, True])
def test_public_query_keeps_unassessed_done_without_calling_a_generator(rag, monkeypatch, limited):
    settings, db, _, indexer, _, _ = rag
    path = settings.data_dir / "originals" / "public-general-diagnostic.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(TEXT)
    document.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extraction", {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))

    class NeverGateway:
        calls = 0

        async def stream(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("An unassessed general question must not invoke generation")
            yield

    gateway = NeverGateway()
    service = service_for(rag, gateway)
    if limited:
        original_search = service.search.search

        async def limited_search(*args, **kwargs):
            result = await original_search(*args, **kwargs)
            result["evidence_selection"] = {"missing_relation_variants": 1}
            return result

        monkeypatch.setattr(service.search, "search", limited_search)
    query_id, result = run(service, QueryRequest(question=QUESTION,
        scope=Scope(kind="documents", documentIds=[imported["document_id"]])))
    assert result["state"] == "done" and gateway.calls == 0
    assert result["metrics"]["model_called"] is False
    assert result["metrics"]["response_route"] == "deterministic_evidence_contract"
    assert result["metrics"]["context_assessment"]["status"] == "unassessed"
    events = [(row["type"], json.loads(row["data_json"]))
              for row in db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))]
    final = next(data["answer_contract"] for kind, data in reversed(events)
                 if kind == "structured_answer" and "answer_contract" in data)
    assert final["status"] == "unassessed" and not final["missing"]
    assert final.get("retrieval_limitations", []) == ([LIMIT] if limited else [])
    terminals = [(kind, data) for kind, data in events if kind in {"done", "error", "cancelled"}]
    assert len(terminals) == 1 and terminals[0][0] == "done"
    assert terminals[0][1]["citations"] == []
    assert "".join(data["text"] for kind, data in events if kind == "delta") == result["answer"]
    assert "analyse littérale" in result["answer"] and TEXT not in result["answer"]
    assert "réponse reste partielle" not in result["answer"]
    assert ("Le budget de recherche" in result["answer"]) == limited
