"""Qualité du harnais contrôlé, sans modèle, service natif ni corpus utilisateur."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("grounded_campaign_under_test", ROOT / "tools/qualification/grounded_campaign.py")
assert SPEC and SPEC.loader
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def positive_case():
    return {"id": "positive", "answerable": True, "facts": [
        {"id": "value", "document": "a", "source_patterns": [r"72 V"], "answer_patterns": [r"72 V"]},
    ]}


def record(answer="Tension nominale : 72 V. [S001]", document="doc-a"):
    return {"state": "done", "answer": answer, "public_deltas": [answer], "selector_calls": 1,
            "documents": {"a": {"document_id": "doc-a", "version_id": "v-a"}},
            "citations": [{"source_id": "S001", "document_id": document, "text": "Tension nominale : 72 V."}],
            "citation_checks": [{"source_id": "S001", "valid": True, "reasons": []}]}


def test_a_plausible_answer_with_the_wrong_cited_document_does_not_pass():
    result = harness.grade_case(positive_case(), record(document="wrong-document"))
    assert not result["passed"]
    assert result["facts"][0]["rendered"]
    assert not result["facts"][0]["literal_source_support"]


def test_abstaining_on_an_answerable_case_is_a_failure_even_when_it_quotes_all_facts():
    answer = "Les preuves ne suffisent pas pour répondre.\n\nTension nominale : 72 V. [S001]"
    result = harness.grade_case(positive_case(), record(answer))
    assert not result["passed"]
    assert result["limitation_notice"]
    assert result["facts"][0]["rendered_and_supported"]


def test_private_invalid_plan_may_be_retained_but_never_published():
    case = {"id": "attack", "answerable": False, "expected": "invalid_plan",
            "allowed_errors": ["structured_answer_invalid"], "forbidden_answer_patterns": ["UNSOURCED_GENERATOR_999"]}
    safe = record("")
    safe.update(state="error", error_code="structured_answer_invalid", events=[
        {"type": "structured_delta", "data": {"text": '{"answer":"UNSOURCED_GENERATOR_999"}'}},
    ])
    assert harness.grade_case(case, safe)["passed"]
    unsafe = copy.deepcopy(safe)
    unsafe["public_deltas"] = ["UNSOURCED_GENERATOR_999"]
    assert not harness.grade_case(case, unsafe)["passed"]


def test_malformed_plan_not_exercised_is_not_credited_as_a_rejection():
    case = {"id": "attack", "answerable": False, "expected": "invalid_plan",
            "allowed_errors": ["structured_answer_invalid"]}
    candidate = record("")
    candidate.update(state="error", error_code="structured_answer_invalid", selector_calls=0)
    assert not harness.grade_case(case, candidate)["passed"]


def test_even_a_literal_fact_with_invalid_provenance_fails():
    candidate = record()
    candidate["citation_checks"][0].update(valid=False, reasons=["source_hash_mismatch"])
    assert not harness.grade_case(positive_case(), candidate)["passed"]


def test_same_number_in_another_document_does_not_fill_a_fact():
    facts = [{"id": "value", "document": "a", "source_patterns": ["72 V"]}]
    sources = [{"document_id": "doc-a", "text": "Tension inconnue."},
               {"document_id": "doc-b", "text": "Tension : 72 V."}]
    assert harness.facts_in_sources(facts, sources, {"a": {"document_id": "doc-a"}}) == {"value": False}


def test_numeric_oracle_accepts_sentence_punctuation_but_not_another_decimal():
    pattern = r"(?<![\d.])4(?![\d.])"
    assert harness.all_patterns([pattern], "résultat = 4. [S001]")
    assert not harness.all_patterns([pattern], "résultat = 4.25 [S001]")
    assert not harness.all_patterns([pattern], "résultat = 0.4 [S001]")


def test_explicit_scope_refusal_is_recognized_without_using_product_status():
    case = {"id": "scope", "answerable": False, "expected": "limitation", "must_limit": True}
    answer = "La question demande la feuille 2, mais le périmètre sélectionné autorise seulement la feuille 1."
    result = harness.grade_case(case, record(answer))
    assert result["passed"] and result["limitation_notice"]


@pytest.mark.parametrize("notice", [
    "Les preuves retenues n'établissent pas la valeur dans les conditions demandées.",
    "Le passage n’établit pas la valeur dans les conditions demandées.",
    "Son nombre n'est pas retenu comme valeur affirmée ; l'extrait conserve la formulation source.",
])
def test_explicit_nonassertion_counts_for_limits_and_against_answerable_cases(notice):
    output = record(notice + "\n\nTension nominale : 72 V. [S001]")
    limit = {"id": "limit", "answerable": False, "expected": "limitation", "must_limit": True}
    limited = harness.grade_case(limit, output)
    assert limited["passed"] and limited["limitation_notice"]
    positive = harness.grade_case(positive_case(), output)
    assert not positive["passed"] and positive["limitation_notice"]


def test_a_negative_quotation_or_the_word_negation_does_not_replace_a_limitation_notice():
    case = {"id": "limit", "answerable": False, "expected": "limitation", "must_limit": True}
    output = record("Les passages abordent une négation.\n\n"
                    "Extrait : « Le passage n'établit pas une tension nominale. » [S001]")
    result = harness.grade_case(case, output)
    assert not result["passed"] and not result["limitation_notice"]


def conflict_case_and_record():
    assertions = ["Recommended supply voltage: 3.0 V at TA = 25 °C.",
                  "Recommended supply voltage: 4.0 V at TA = 25 °C."]
    case = {"id": "conflict", "answerable": False, "expected": "conflict",
            "required_answer_patterns": ["différentes"],
            "documents": [{"key": "a", "format": "docx", "paragraphs": assertions}],
            "facts": [{"id": "a", "document": "a", "source_patterns": [r"3\.0", r"4\.0", "25"],
                       "answer_patterns": [r"3\.0", r"4\.0", "25"]}]}
    output = record("Les extraits donnent des valeurs différentes ; aucune valeur n'est arbitrée.\n\n"
                    f"Extrait : « {assertions[0]} » [S001]\n\nExtrait : « {assertions[1]} » [S002]")
    output["citations"] = [{"source_id": f"S{index:03}", "document_id": "doc-a", "version_id": "v-a", "text": text}
                           for index, text in enumerate(assertions, 1)]
    output["citation_checks"] = [{"source_id": source["source_id"], "valid": True, "reasons": []}
                                 for source in output["citations"]]
    return case, output


def test_declared_conflict_can_quote_two_complete_assertions_of_one_document():
    case, output = conflict_case_and_record()
    assert harness.grade_case(case, output)["passed"]
    # Independent assertions are a conflict-specific route, not a relaxation
    # of the single-source relation check or an inferred new oracle.
    assert harness.facts_in_sources(case["facts"], output["citations"], output["documents"]) == {"a": False}
    case["expected"] = "limitation"
    assert not harness.grade_case(case, output)["passed"]


@pytest.mark.parametrize("fault", ["wrong_document", "wrong_version", "missing_source_condition", "missing_rendered_condition"])
def test_conflict_cannot_borrow_a_value_or_lose_its_individual_condition(fault):
    case, output = conflict_case_and_record()
    if fault == "wrong_document":
        output["citations"][1]["document_id"] = "doc-other"
    elif fault == "wrong_version":
        output["citations"][1]["version_id"] = "v-other"
    elif fault == "missing_source_condition":
        output["citations"][1]["text"] = "Recommended supply voltage: 4.0 V."
    else:
        output["answer"] = output["answer"].replace("4.0 V at TA = 25 °C", "4.0 V")
    result = harness.grade_case(case, output)
    assert not result["passed"] and not result["facts"][0]["literal_source_support"]


def test_different_bundles_cannot_silently_supply_opposite_range_ends():
    facts = [{"id": "range", "document": "a", "source_patterns": ["MIN = 0", "MAX = 36"]}]
    sources = [{"document_id": "doc-a", "text": "MIN = 0 for mode A"},
               {"document_id": "doc-a", "text": "MAX = 36 for mode B"}]
    assert harness.facts_in_sources(facts, sources, {"a": {"document_id": "doc-a"}}) == {"range": False}


@pytest.mark.parametrize("spec", [
    {"format": "docx", "paragraphs": ["Condition exacte : seulement à 25 °C."]},
    {"format": "xlsx", "sheets": [{"name": "Valeurs", "cells": {"A1": 0, "B1": -40}}]},
])
def test_same_fixture_produces_identical_original_bytes(tmp_path, spec):
    one, two = tmp_path / ("one." + spec["format"]), tmp_path / ("two." + spec["format"])
    assert harness.generate_document(spec, one) == harness.generate_document(spec, two)
    assert one.read_bytes() == two.read_bytes()
    with pytest.raises(FileExistsError):
        harness.generate_document(spec, one)


def test_synthetic_formula_cache_is_explicit_and_not_recalculated(tmp_path):
    path = tmp_path / "cache.xlsx"
    spec = {"format": "xlsx", "sheets": [{"name": "Valeurs", "cells": {"A1": "=1+2"}}],
            "formula_cache": {"A1": "99"}}
    harness.generate_document(spec, path)
    cached = load_workbook(path, data_only=True)
    formulas = load_workbook(path, data_only=False)
    try:
        assert cached.active["A1"].value == 99
        assert formulas.active["A1"].value == "=1+2"
    finally:
        cached.close()
        formulas.close()


def test_fixture_validation_rejects_an_oracle_with_unknown_document(tmp_path):
    path = tmp_path / "cases.json"
    value = {"schema_version": 1, "cases": [{**positive_case(), "documents": [{"key": "b"}]}]}
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="document de référence"):
        harness.load_fixture(path)


def test_errors_and_limitations_do_not_disappear_from_answerable_denominator():
    one = {**record(), "metrics": {"elapsed_ms": 3}}
    one["judgment"] = harness.grade_case(positive_case(), one)
    two = {**record(""), "state": "error", "metrics": {"elapsed_ms": 10}}
    two["judgment"] = harness.grade_case(positive_case(), two)
    result = harness.summarize([one, two])
    assert result["answerable_total"] == 2 and result["answerable_pass"] == 1
    assert result["required_literal_facts"] == 2 and result["literal_facts_rendered_and_supported"] == 1
    assert result["answerable_errors"] == 1
    assert result["query_latency_ms"]["n"] == 2


def test_frozen_matrix_has_explicit_positive_and_adversarial_denominators():
    fixture = harness.load_fixture(ROOT / "tests/fixtures/grounded_cases.json")
    assert sum(case["answerable"] for case in fixture["cases"]) == fixture["acceptance"]["answerable_total"] == 12
    assert sum(not case["answerable"] for case in fixture["cases"]) == fixture["acceptance"]["limit_controls_total"] == 18
    assert {case["expected"] for case in fixture["cases"] if not case["answerable"]} == {
        "limitation", "conflict", "provenance", "invalid_plan",
    }
