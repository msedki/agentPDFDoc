"""Preallocation bounds fixed in the I5 resource addendum before this change.

Literal synthetic questions/IDs test cardinality independently of native RAG.
The API case uses real SQLite/Office with named vector/tokenizer/gateway doubles.
"""

import asyncio
import hashlib
import json

import pytest
from docx import Document
from test_enhanced_answers import catalogue
from test_grounded_query import ForbiddenGateway, run, service_for
from test_office_rag import rag as rag

from services.api.answer_contract import AnswerContract
from services.api.errors import ApiError
from services.api.schemas import QueryRequest, Scope
from services.ingestion.office.pipeline import extract_office


def documents(count):
    return [f"document-{index:04d}" for index in range(count)]


def failure(call):
    with pytest.raises(ApiError) as caught:
        call()
    error = caught.value
    assert error.code == "question_scope_too_complex"
    assert len(error.message) < 250
    assert "DEV" not in error.message and "document-" not in error.message
    return error


def test_exact_cardinality_boundary_is_not_truncated():
    question = "Supply voltage for " + " ".join(f"DEV{index:03d}" for index in range(16))
    contract = AnswerContract(question, "question")
    obligations = contract._obligations([], documents(16))
    assert len(obligations) == 256
    assert len({item["obligation_id"] for item in obligations}) == 256
    assert all(not item["covered"] for item in obligations)
    failure(lambda: contract._obligations([], documents(17)))


def test_exact_clause_character_boundary_and_next_character():
    prefix = "What is the supply voltage? "
    question = prefix + "x" * (256 - len(prefix))
    exact = AnswerContract(question, "question")._obligations([], documents(256))
    assert len(exact) == 256 and sum(len(item["request_clause"]) for item in exact) == 65536
    failure(lambda: AnswerContract(question + "x", "question")._obligations([], documents(256)))


def test_cartesian_dimensions_are_counted_together():
    question = ("Give nominal and operating bus and supply voltage ranges, single and dual, "
                "for DEV011 and DEV012 for drives of 7 mV and 14 mV?")
    contract = AnswerContract(question, "question")
    obligations = contract._obligations([], documents(4))
    assert len(obligations) == 128
    assert {item["property"] for item in obligations} == {"bus", "supply"}
    assert {item["role"] for item in obligations} == {"nominal", "operating"}
    assert {item["supply_configuration"] for item in obligations} == {"single", "dual"}
    failure(lambda: contract._obligations([], documents(9)))


def test_composite_limit_is_global_and_precedes_fact_or_child_allocation(monkeypatch):
    contract = AnswerContract("What is DEV011 supply voltage range and what is the purpose of debounce?", "question")
    assert len(contract.assess([], required_documents=documents(128))["obligations"]) == 256

    def forbidden_facts(*args, **kwargs):
        raise AssertionError("A rejected Cartesian scope must fail before fact work or child obligations")

    monkeypatch.setattr(AnswerContract, "_facts", forbidden_facts)
    failure(lambda: contract.assess([], required_documents=documents(129)))


def test_qualitative_limit_precedes_candidate_work(monkeypatch):
    question = "What is the purpose of debounce for " + " ".join(f"DEV{index:03d}" for index in range(16))
    contract = AnswerContract(question, "question")
    assert len(contract.assess([], required_documents=documents(16))["obligations"]) == 256

    def forbidden_candidates(*args, **kwargs):
        raise AssertionError("Candidate work must follow the complexity guard")

    monkeypatch.setattr(AnswerContract, "_qualitative_candidates", forbidden_candidates)
    failure(lambda: contract.assess([], required_documents=documents(17)))


def test_many_pinned_documents_cannot_reach_model_projection():
    cat = catalogue("What is the supply voltage?", [])
    cat.required_documents = tuple(documents(1000))
    failure(cat.model_view)
    failure(cat.evidence)


def test_ordinary_request_keeps_all_requested_obligations():
    contract = AnswerContract("Give the bus and supply voltage ranges for DEV011 and DEV012.", "question")
    obligations = contract._obligations([], ["a", "b", "a"])
    assert len(obligations) == 8
    assert {item["document_id"] for item in obligations} == {"a", "b"}
    assert all(item["request_clause"] == contract.question for item in obligations)


def test_complex_question_reports_operational_limit_without_model_or_public_answer(rag):
    settings, db, _, indexer, _, _ = rag
    path = settings.data_dir / "originals" / "generic-limit.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("DEV000 supply voltage: 4 V.")
    document.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extraction", {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))
    service = service_for(rag, ForbiddenGateway())
    # Exercise the Cartesian bound inside the existing question token budget.
    # A long list of 257 IDs instead reaches question_too_long first.
    question = ("Give nominal and operating bus and supply voltage ranges, single and dual, for "
                + " ".join(f"DEV{index:03d}" for index in range(9))
                + " for drives of 7 mV, 14 mV, 21 mV and 28 mV?")
    query_id, result = run(service, QueryRequest(question=question,
        scope=Scope(kind="documents", documentIds=[imported["document_id"]])))
    assert result["state"] == "error" and not result["answer"]
    assert not result["metrics"].get("model_call_attempted", False)
    errors = [json.loads(row["data_json"]) for row in db.rows(
        "SELECT data_json FROM events WHERE query_id=? AND type='error'", (query_id,))]
    assert len(errors) == 1 and errors[0]["code"] == "question_scope_too_complex"
    assert db.rows("SELECT type FROM events WHERE query_id=? AND type IN ('delta','done')", (query_id,)) == []
