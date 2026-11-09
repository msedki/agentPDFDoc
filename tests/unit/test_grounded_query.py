"""Publication boundary with real SQLite/OOXML and named model/retrieval doubles."""

import asyncio
import hashlib
import json

import pytest
from docx import Document
from test_enhanced_retrieval import range_fixture
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.execution_trace import read_verified_trace
from services.api.query import QueryService
from services.api.schemas import QueryRequest, Scope
from services.api.structured_answer import Catalogue
from services.ingestion.office.pipeline import extract_office


class ForbiddenGateway:
    async def stream(self, *args, **kwargs):
        raise AssertionError("Verified exact cell reading does not need generation")
        yield


def service_for(rag, gateway):
    settings, db, _, _, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True}
    settings.profile["trace"] = {"mode": "full"}
    return QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()), gateway, settings)


def run(service, request):
    async def scenario():
        response = await service.create_async(request)
        await service.tasks[response["query_id"]]
        return response["query_id"], service.run_detail(response["query_id"])

    return asyncio.run(scenario())


def test_post_render_corruption_is_blocked_before_public_delta(rag, monkeypatch):
    snapshot = range_fixture(rag)
    service = service_for(rag, ForbiddenGateway())
    original = Catalogue.render

    def corrupt(self, *args, **kwargs):
        rendered = original(self, *args, **kwargs)
        rendered["text"] += "\nConclusion ajoutée : tension admissible 999 V."
        return rendered

    monkeypatch.setattr(Catalogue, "render", corrupt)
    query_id, result = run(service, QueryRequest(
        question="Quelles valeurs contiennent exactement les cellules B5 et B6 ?", scope=Scope(**snapshot.scope)))
    assert result["state"] == "error"
    assert not result["answer"]
    public_text = rag[1].rows("SELECT * FROM events WHERE query_id=? AND type IN ('delta','done')", (query_id,))
    assert public_text == []


def test_ledger_is_captured_before_selection_and_verified_before_terminal(rag):
    snapshot = range_fixture(rag)
    service = service_for(rag, ForbiddenGateway())
    query_id, result = run(service, QueryRequest(
        question="Quelles valeurs contiennent exactement les cellules B5 et B6 ?", scope=Scope(**snapshot.scope)))
    assert result["state"] == "done"
    trace = read_verified_trace(rag[0].data_dir / "traces" / (query_id + ".jsonl"))
    phases = [event["phase"] for event in trace]
    assert phases.index("evidence.ledger") < phases.index("answer.deterministic_plan")
    assert phases.index("answer.support_validation") < phases.index("query.done")
    assert result["metrics"]["answer_support_validation"]
    assert result["metrics"]["structured_answer"]["support_ledger_sha256"]


@pytest.mark.parametrize("finish_reason", ["length", "cancelled"])
@pytest.mark.parametrize("complete_plan", [False, True])
def test_unfinished_reference_plan_publishes_no_text(rag, monkeypatch, finish_reason, complete_plan):
    settings, db, _, indexer, _, _ = rag
    path = settings.data_dir / "originals" / "case.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("Le boîtier est étanche uniquement lorsque le couvercle est fermé.")
    document.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extraction", {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))

    def force_reference_selector(self, required_documents=()):
        # I5 normally skips generation for this complete literal relation.
        # This named route double isolates the unfinished-model boundary;
        # source validation and every publication assertion remain active.
        assert self.assess(required_documents=required_documents)["status"] == "covered"
        assert self.model_view()["reference_ids"]
        return None

    monkeypatch.setattr(Catalogue, "deterministic_plan", force_reference_selector)

    class TruncatedGateway:
        async def stream(self, *args, **kwargs):
            assert kwargs["response_format"]["additionalProperties"] is False
            text = (json.dumps({"references": kwargs["response_format"]["properties"]["references"]["items"]["enum"][:1],
                                "comparisons": []}) if complete_plan else '{"references":["R001"]')
            yield {"type": "delta", "text": text}
            yield {"type": "done", "finish_reason": finish_reason, "metrics": {"eval_count": 12}}

    service = service_for(rag, TruncatedGateway())
    query_id, result = run(service, QueryRequest(
        question="Dans quelle condition le boîtier est-il étanche ?",
        scope=Scope(kind="documents", documentIds=[imported["document_id"]])))
    assert result["state"] == "error"
    assert result["metrics"]["model_call_attempted"] is True
    assert not result["answer"]
    events = db.rows("SELECT type,data_json FROM events WHERE query_id=?", (query_id,))
    assert not any(event["type"] in {"delta", "done"} for event in events)
    errors = [json.loads(event["data_json"]) for event in events if event["type"] == "error"]
    assert len(errors) == 1
    assert errors[0]["code"] == ("structured_answer_incomplete" if finish_reason == "length" else "structured_answer_invalid")
