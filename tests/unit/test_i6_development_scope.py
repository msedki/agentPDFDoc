"""Public I6 DEV boundaries; real catalogue/renderer, explicit selector double.

No FINAL fixture, extraction, retrieval or model is exercised by this module.
The new cases below test the declared grammar beyond the frozen DEV examples.
"""

import json
from pathlib import Path

import pytest
from test_enhanced_answers import catalogue, excerpt, render


def assess(question, text):
    cat = catalogue(question, [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["support_validation"]["status"] == "passed"
    return result


@pytest.mark.parametrize("case_id", ["I6D11", "I6D18", "I6D19", "I6D21", "I6D22", "I6D23", "I6D32"])
def test_public_development_relation_scope(case_id):
    fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures/support_i6_dev.json").read_text())
    case = next(case for case in fixture["cases"] if case["id"] == case_id)
    text = case["sources"][0]["text"]
    result = assess(case["question"], text)
    contract = result["answer_contract"]
    assert contract["status"] in case["expected"]["status_classes"]
    assert (contract["status"] == "covered") is case["expected"]["exact_support"]
    if case["expected"]["exact_support"]:
        assert [fact["values"] for fact in contract["matched_relations"]] == [
            fact["values"] for fact in case["expected"]["allowed_relations"]]
    else:
        assert not contract["matched_relations"]
    assert text in result["text"] and result["citation_spans"]


@pytest.mark.parametrize("connector", ["; ", ", but ", " and "])
def test_independent_predicates_keep_identity_value_and_complete_quote(connector):
    text = "The output current of ZR810 is not 17 mA" + connector + "the nominal voltage of ZR811 is 5.3 V."
    result = assess("What is the nominal voltage of ZR811?", text)
    assert result["answer_contract"]["status"] == "covered"
    fact, = result["answer_contract"]["matched_relations"]
    assert fact["subjects"] == ["ZR811"]
    assert fact["entity_context_identifiers"] == ["zr811"]
    assert fact["values"] == ["5.3"]
    assert fact["quote"] == text
    assert text[fact["source_start"]:fact["source_end"]] == fact["quote"]
    assert text in result["text"] and result["citation_spans"]


@pytest.mark.parametrize("connector", ["; ", ", but ", " and "])
def test_same_dimension_different_properties_are_not_merged(connector):
    text = "The input current is not 17 mA" + connector + "the output current is 17 mA at TA = 31 °C."
    result = assess("What output current at TA = 31 °C?", text)
    assert result["answer_contract"]["status"] == "covered"
    fact, = result["answer_contract"]["matched_relations"]
    assert fact["property"] == "output" and fact["values"] == ["17"]
    assert text in result["text"]


@pytest.mark.parametrize("reverse", [False, True])
def test_explicit_denial_of_one_value_does_not_select_by_position(reverse):
    clauses = ["The nominal voltage is not 6.7 V", "The nominal voltage is 5.3 V"]
    text = "; ".join(reversed(clauses) if reverse else clauses) + "."
    result = assess("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] == "covered"
    assert [fact["values"] for fact in result["answer_contract"]["matched_relations"]] == [["5.3"]]
    assert text in result["text"]


def test_two_affirmative_repeated_predicates_remain_conflicting():
    text = "The nominal voltage is 6.7 V; The nominal voltage is 5.3 V."
    result = assess("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] == "conflict"
    assert {tuple(fact["values"]) for fact in result["answer_contract"]["matched_relations"]} == {("6.7",), ("5.3",)}
    assert text in result["text"]


@pytest.mark.parametrize("text", [
    "The nominal voltage is 5.3 V; The nominal voltage is not 5.3 V.",
    "The nominal voltage is not 5300 mV; The nominal voltage is 5.3 V.",
    "The nominal voltage is 5.3 V; The nominal voltage is not established.",
    "It is not true that the nominal voltage is 5.3 V and the output current is 17 mA.",
    "No part of the following statement is established: the nominal voltage is 5.3 V; the output current is 17 mA.",
    "The nominal voltage is 5.3 V provided that the output current is not 17 mA.",
    "The nominal voltage is 5.3 V and this value is not established.",
    "The nominal voltage is 5.3 V (and the output current is not 17 mA).",
])
def test_dominance_dependency_and_opposite_assertion_cannot_disappear(text):
    result = assess("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


def test_independent_second_predicate_keeps_its_following_restriction():
    text = "The nominal voltage is 5.3 V and the output current is 17 mA. The output current is not established."
    result = assess("What is the output current?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


def test_other_clause_cannot_erase_the_local_numeric_bound():
    text = "The output current is not 17 mA and the nominal voltage is less than 5.3 V."
    result = assess("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


@pytest.mark.parametrize("text", [
    "Le courant de sortie est de 17 mA, exception faite de TA = 31 °C.",
    "Exception faite de TA = 31 °C, le courant de sortie est de 17 mA.",
    "Le courant de sortie est de 17 mA. Exception faite de TA = 31 °C.",
])
def test_participial_exception_preserves_the_excluded_point_and_literal(text):
    result = assess("Quel courant de sortie à TA = 31 °C ?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


def test_participial_exception_does_not_erase_a_distinct_asserted_point():
    text = "Le courant de sortie est de 17 mA à TA = 31 °C, exception faite de TA = 47 °C."
    result = assess("Quel courant de sortie à TA = 31 °C ?", text)
    assert result["answer_contract"]["status"] == "covered"
    assert text in result["text"]


@pytest.mark.parametrize(("question", "text"), [
    ("What is the supply voltage?",
     "The output current is 17 mA when the nominal voltage is 5.3 V and the supply voltage is 6.1 V."),
    ("Quelle est la tension d’alimentation ?",
     "Le courant de sortie est de 17 mA lorsque la tension nominale est de 5,3 V et la tension d’alimentation est de 6,1 V."),
])
def test_coordinated_condition_is_not_promoted_to_an_independent_assertion(question, text):
    cat = catalogue(question, [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert cat.references[0]["text"] == text
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("text", [
    "The output current is not 17 mA when TA = 31 °C; the nominal voltage is 5.3 V.",
    "The output current is not 17 mA at TA = 31 °C and the nominal voltage is 5.3 V.",
])
def test_an_independent_predicate_is_not_poisoned_by_the_other_numeric_test_point(text):
    result = assess("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] == "covered"
    assert [fact["values"] for fact in result["answer_contract"]["matched_relations"]] == [["5.3"]]
    assert text in result["text"]


def test_primary_value_keeps_its_complete_coordinated_condition():
    text = "The output current is 17 mA when the nominal voltage is 5.3 V and the supply voltage is 6.1 V."
    result = assess("What is the output current?", text)
    assert result["answer_contract"]["status"] == "covered"
    fact, = result["answer_contract"]["matched_relations"]
    assert fact["values"] == ["17"]
    assert "when the nominal voltage is 5.3 V and the supply voltage is 6.1 V" in fact["condition"]
    assert text in result["text"]
