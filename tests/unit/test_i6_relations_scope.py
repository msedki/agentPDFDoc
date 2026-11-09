"""I6 relation-scope regressions, independent of the new final fixture.

The catalogue, condition parser and renderer are real. The character token
counter and explicit reference plan are doubles; no extraction, retrieval or
native generation is exercised. Published I5 failures are development inputs.
"""

import pytest
from test_enhanced_answers import catalogue, excerpt, render

from services.api.point_conditions import condition_measures


def assess_source(question, text):
    cat = catalogue(question, [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["support_validation"]["status"] == "passed"
    return cat, result


@pytest.mark.parametrize("prefix", [
    "à l'exception de",
    "à l’exception de",
    "à l'exclusion de",
    "à l’exclusion de",
    "with the exception of",
    "with exception of",
])
def test_nominal_exclusion_is_a_point_operator_not_an_included_condition(prefix):
    text = "Output current is 17 mA " + prefix + " TA = 32 °C."
    assert condition_measures(text) == []
    point, = condition_measures(text, excluded=True)
    assert point["symbol"] == "TA" and point["value"] == "305.15"
    assert text[point["start"]:point["end"]] == point["text"] == "TA = 32 °C"
    _, result = assess_source("What output current at TA = 32 °C?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"] and result["citation_spans"]


@pytest.mark.parametrize("text", [
    "À l’exception de TA = 32 °C, le courant de sortie est de 17 mA.",
    "Le courant de sortie est de 17 mA. À l’exception de TA = 32 °C.",
    "Output current is 17 mA. With the exception of TA = 32 °C.",
    "Output current is 17 mA with the exception of (TA = 32 °C).",
    "Output current is 17 mA at TA = 32 °C, with the exception of TA = 32 °C.",
])
def test_exclusion_position_cannot_remove_the_literal_restriction(text):
    _, result = assess_source("What output current at TA = 32 °C?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"] and result["citation_spans"]


def test_nominal_exclusion_propagates_only_across_explicit_point_coordination():
    text = "Output current is 17 mA à l’exception de (TA = 32 °C) ou TA = 43 °C."
    assert condition_measures(text) == []
    assert [point["value"] for point in condition_measures(text, excluded=True)] == ["305.15", "316.15"]
    _, result = assess_source("What output current at TA = 43 °C?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert text in result["text"]


@pytest.mark.parametrize("text", [
    "Output current is 17 mA at TA = 32 °C.",
    "Output current is 17 mA at TA = 32 °C, with the exception of TA = 43 °C.",
    "Output current is 17 mA at TA = 32 °C. With the exception of TA = 43 °C.",
    "Output current is 17 mA at TA = 32 °C unless otherwise noted.",
    "Output current is 17 mA without exception at TA = 32 °C.",
])
def test_asserted_point_and_distinct_exception_preserve_useful_coverage(text):
    _, result = assess_source("What output current at TA = 32 °C?", text)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"]
    assert result["citation_spans"]


def test_predicate_negation_keeps_its_location_without_becoming_a_point_exclusion():
    text = "Output current is not established at TA = 32 °C."
    assert len(condition_measures(text)) == 1
    assert condition_measures(text, excluded=True) == []


@pytest.mark.parametrize("question", [
    "Quel courant de sortie à l’exception de TA = 32 °C ?",
    "What output current with the exception of TA = 32 °C?",
])
def test_question_exclusion_cannot_disappear_into_an_unrestricted_lookup(question):
    cat, result = assess_source(question, "Output current is 17 mA at TA = 32 °C.")
    assert "excluded_point_condition_not_supported" in cat.contract.parse_failures
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]


@pytest.mark.parametrize(("question", "text", "value"), [
    ("Quelle est la tension nominale du KZ705 ?",
     "La tension nominale du KZ705 est de 5,7 V ; le courant de sortie ne dépasse pas 26 mA.", "5.7"),
    ("What is the nominal voltage?",
     "The nominal voltage is 4.8 V; the output current is not 19 mA.", "4.8"),
    ("What is the nominal voltage?",
     "The nominal voltage is 4.8 V; the output current is approximately 19 mA.", "4.8"),
])
def test_separate_quantity_clause_does_not_poison_exact_value_or_shorten_the_quote(question, text, value):
    _, result = assess_source(question, text)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    relation, = assessment["matched_relations"]
    assert relation["quantity"] == "voltage" and relation["values"] == [value]
    assert relation["assertion_status"] == "asserted"
    assert text in result["text"] and result["citation_spans"]
    assert not any(item["requirement"].startswith("source_assertion_")
                   for item in assessment["missing"] + assessment["ambiguous"])


def test_independent_positive_quantity_after_negated_quantity_remains_supported():
    text = "The output current is not 19 mA; the nominal voltage is 4.8 V."
    _, result = assess_source("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["values"] == ["4.8"]


@pytest.mark.parametrize("text", [
    "The nominal voltage is not 4.8 V; the output current is 19 mA.",
    "It is not true that the nominal voltage is 4.8 V; the output current is 19 mA.",
    "The nominal voltage is 4.8 V; the nominal voltage is not established.",
    "The nominal voltage is 4.8 V; provided that the output current does not exceed 19 mA.",
    "The nominal voltage is 4.8 V; this value is not guaranteed.",
    "The nominal voltage is 4.8 V; the output current is not 19 mA. The nominal voltage is not established.",
    "La tension nominale est de 4,8 V ; sous réserve que le courant ne dépasse pas 19 mA.",
])
def test_dominant_same_subject_conditional_and_anaphoric_limits_are_not_discarded(text):
    _, result = assess_source("What is the nominal voltage?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


def test_dominant_negation_cannot_be_dropped_before_a_second_quantity():
    text = "It is not true that the nominal voltage is 4.8 V; the output current is 19 mA."
    _, result = assess_source("What output current?", text)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]
