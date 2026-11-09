"""Closed numeric limits use the real renderer without a selector call.

Catalogue controls use literal synthetic excerpts. The QueryService test adds
real DOCX extraction, SQLite, FTS and event persistence; embeddings, vector
transport and token counting remain the explicitly named test doubles.
"""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from docx import Document
from test_api_storage import storage as storage
from test_enhanced_answers import catalogue, excerpt, render
from test_office_rag import rag as rag
from test_production_evidence_contract import list_catalogue
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.execution_trace import read_verified_trace
from services.api.query import QueryService
from services.api.schemas import QueryRequest, Scope
from services.ingestion.office.pipeline import extract_office
from services.ingestion.source_quality import verified_source_quality


def complete(reference, text, *, document="document-1"):
    return {**excerpt(reference, text, document=document),
            "source_span_complete": True, "index_generation_state": "ready"}


@pytest.mark.parametrize(("question", "text"), [
    ("What is the nominal supply voltage?", "Nominal supply voltage is less than 4.7 V."),
    ("What output current at TA = 31 °C?", "Output current is 19 mA except at TA = 31 °C."),
    ("Quel courant de sortie à TA = 31 °C ?", "Le courant de sortie est de 19 mA, exception faite de TA = 31 °C."),
    ("What is the nominal supply voltage?", "Nominal supply voltage is not 4.7 V."),
])
def test_complete_numeric_limit_keeps_all_diagnostic_support(question, text):
    cat = catalogue(question, [complete("R001", text)])
    selected = render(cat, ["R001"])
    assert selected["answer_contract"]["status"] == "partial"
    assert selected["answer_contract"]["rejected_relations"]
    plan = cat.deterministic_plan()
    assert plan is not None and plan.references == ["R001"] and plan.comparisons == []
    bounded = render(cat, plan.references)
    for key in ("text", "answer_contract", "support_ledger", "citation_spans"):
        assert bounded[key] == selected[key]
    assert text in bounded["text"]
    assert not bounded["answer_contract"]["matched_relations"]
    assert bounded["support_validation"]["status"] == "passed"


def test_comparison_keeps_both_subjects_and_the_wrong_role_diagnostic():
    sources = [complete("R001", "The nominal voltage of ZQ810 is 4.7 V.", document="first"),
               complete("R002", "The maximum voltage of ZQ811 is 4.7 V.", document="second")]
    cat = catalogue("Compare the nominal voltages of ZQ810 and ZQ811.", sources, mode="comparison")
    required = ["first", "second"]
    selected = render(cat, ["R001", "R002"], required_documents=required)
    assert selected["answer_contract"]["status"] == "partial"
    plan = cat.deterministic_plan(required)
    assert plan is not None and plan.references == ["R001", "R002"]
    bounded = render(cat, plan.references, required_documents=required)
    assert bounded["answer_contract"] == selected["answer_contract"]
    assert bounded["text"] == selected["text"]
    assert not bounded["answer_contract"]["comparisons"]
    assert bounded["source_ids"] == ["S001", "S002"]


def test_conflict_is_preserved_instead_of_selecting_one_value():
    cat = catalogue("What is the nominal supply voltage?", [
        complete("R001", "Nominal supply voltage is 4.7 V."),
        complete("R002", "Nominal supply voltage is 5.2 V."),
    ])
    expected = render(cat, ["R001", "R002"])
    assert expected["answer_contract"]["status"] == "conflict"
    plan = cat.deterministic_plan()
    assert plan is not None and plan.references == ["R001", "R002"]
    observed = render(cat, plan.references)
    assert observed["answer_contract"] == expected["answer_contract"]
    assert observed["text"] == expected["text"]
    assert "4.7 V" in observed["text"] and "5.2 V" in observed["text"]


@pytest.mark.parametrize("boundary", ["truncated", "unknown_span", "partial_generation", "retrieval_gap"])
def test_incomplete_evidence_keeps_reference_selection(boundary):
    reference = complete("R001", "Output current is 19 mA except at TA = 31 °C.")
    if boundary == "truncated":
        reference["source_span_complete"] = False
    elif boundary == "unknown_span":
        del reference["source_span_complete"]
    elif boundary == "partial_generation":
        reference["index_generation_state"] = "ready_partial"
    cat = catalogue("What output current at TA = 31 °C?", [reference])
    if boundary == "retrieval_gap":
        cat.retrieval_limitations = [{"code": "evidence_coverage_incomplete", "missing_relation_variants": 1}]
    assert cat.model_view()["reference_ids"] == ["R001"]
    assert cat.deterministic_plan() is None


def test_unresolved_source_uncertainty_keeps_reference_selection():
    cat = catalogue("What is the nominal supply voltage?", [
        complete("R001", "Nominal supply voltage may be 4.7 V."),
    ])
    assert cat.assess()["status"] == "ambiguous"
    assert cat.deterministic_plan() is None


def test_conflict_status_does_not_hide_an_additional_source_uncertainty():
    cat = catalogue("What is the nominal supply voltage?", [
        complete("R001", "Nominal supply voltage is 4.7 V."),
        complete("R002", "Nominal supply voltage is 5.2 V."),
        complete("R003", "Nominal supply voltage may be 4.9 V."),
    ])
    assessment = cat.assess()
    assert assessment["status"] == "conflict" and assessment["ambiguous"]
    assert cat.deterministic_plan() is None


def test_unresolved_prose_subject_binding_keeps_reference_selection():
    cat = catalogue("What is the nominal supply voltage of ZQ810?", [
        complete("R001", "ZQ810 and ZQ811: nominal supply voltage is 4.7 V."),
    ])
    assessment = cat.assess()
    assert assessment["status"] == "partial" and not assessment["matched_relations"]
    assert any("requested_subject_binding_not_established" in item["reasons"]
               for item in assessment["rejected_relations"])
    assert cat.deterministic_plan() is None


def test_rejected_list_relations_do_not_hide_an_incomplete_group(storage):
    existing, _ = list_catalogue(storage, "S08", first_only=True)
    cat = catalogue("What are the nominal supply voltage ranges?", existing.references)
    assessment = cat.assess()
    assert assessment["status"] == "partial" and not assessment["matched_relations"]
    rejected = assessment["rejected_relations"]
    assert rejected and all("requested_role_not_established" in item["reasons"] for item in rejected)
    assert all(not item["list_binding"]["catalogue_group_complete"] for item in rejected)
    assert cat.deterministic_plan() is None


def test_unanalysed_question_component_keeps_reference_selection():
    cat = catalogue("What output current except at TA = 31 °C?", [
        complete("R001", "Output current is 19 mA at TA = 31 °C."),
    ])
    assert cat.contract.parse_failures
    assert cat.model_view()["reference_ids"]
    assert cat.deterministic_plan() is None


def test_missing_relation_without_a_diagnostic_does_not_close_the_selection():
    cat = catalogue("What are the bus and supply voltage ranges?", [
        complete("R001", "Bus voltage: 0 V to 24 V."),
    ])
    assert cat.assess()["status"] == "partial"
    assert not cat.assess()["rejected_relations"]
    assert cat.deterministic_plan() is None


def test_missing_document_keeps_reference_selection():
    cat = catalogue("Compare the nominal supply voltages.", [
        complete("R001", "Nominal supply voltage is 4.7 V.", document="first"),
    ], mode="comparison")
    assert cat.deterministic_plan(["first", "missing"]) is None


def test_an_unreadable_variant_cannot_be_discarded_to_close_the_selection():
    uncertain = complete("R002", "Nominal supply voltage is 5.2 V.")
    uncertain["extraction_method"] = "ocr"
    uncertain["source_quality"] = verified_source_quality(
        uncertain["text"], {"extraction_method": "ocr"}, "c" * 64, 0)
    assert uncertain["source_quality"]["state"] == "unavailable"
    cat = catalogue("What is the nominal supply voltage?", [
        complete("R001", "Nominal supply voltage is 4.7 V."), uncertain,
    ])
    assert cat.model_view()["reference_ids"] == ["R001"]
    assert cat.assess()["status"] != "covered"
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("closed", [True, False])
def test_real_query_preserves_the_boundary_between_limit_and_selection(rag, closed):
    settings, db, _, indexer, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True,
                                    "complementary_retrieval": True}
    settings.profile["trace"] = {"mode": "full"}
    text = ("The output current of ZQ810 is 19 mA except at TA = 31 °C." if closed
            else "The bus voltage of ZQ810 is 0 V to 24 V.")
    question = ("What output current of ZQ810 at TA = 31 °C?" if closed
                else "What are the bus and supply voltage ranges of ZQ810?")
    path = settings.data_dir / "originals" / "closed-limit.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(text)
    document.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extractions" / imported["version_id"],
                                {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))

    class ControlledGatewayDouble:
        calls = 0

        async def stream(self, messages, cancelled, output_tokens, *, response_format):
            self.calls += 1
            assert not closed, "A closed numeric limit must not call a model"
            ids = response_format["properties"]["references"]["items"]["enum"]
            yield {"type": "delta", "text": json.dumps({"references": ids, "comparisons": []})}
            yield {"type": "done", "finish_reason": "stop", "metrics": {"eval_count": 1}}

    gateway = ControlledGatewayDouble()
    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()),
                           gateway, settings)

    async def scenario():
        response = await service.create_async(QueryRequest(
            question=question,
            scope=Scope(kind="documents", documentIds=[imported["document_id"]])))
        query_id = response["query_id"]
        await service.tasks[query_id]
        run = service.run_detail(query_id)
        assert run["state"] == "done"
        assert run["metrics"]["model_called"] is (not closed)
        assert gateway.calls == int(not closed)
        assert run["metrics"]["response_route"] == ("deterministic_evidence_limit" if closed else "local_4b_generation")
        assert text in run["answer"]
        terminal = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'",
                                     (query_id,))["data_json"])
        result = terminal["structured_answer"]
        assert result["plan_origin"] == ("deterministic_contract" if closed else "model")
        assert result["answer_contract"]["status"] == "partial"
        assert bool(result["answer_contract"]["rejected_relations"]) is closed
        assert bool(result["answer_contract"]["matched_relations"]) is (not closed)
        assert run["metrics"]["answer_support_validation"]["status"] == "passed"
        assert terminal["text"] == run["answer"] and terminal["citations"]
        assert all(citation["version_id"] == imported["version_id"] for citation in terminal["citations"])
        trace = read_verified_trace(Path(settings.data_dir) / "traces" / (query_id + ".jsonl"))
        phases = {row["phase"] for row in trace}
        assert ("answer.deterministic_plan" in phases) is closed
        if closed:
            assert "llm.request" not in phases

    asyncio.run(scenario())
