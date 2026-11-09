"""Numeric verification regressions from I5/PJ; invented bilingual excerpts.

The contract and source-bound renderer are real. Only token counting is doubled;
these tests do not measure extraction, retrieval or a live 4B model.
"""

import pytest
from test_enhanced_answers import catalogue, excerpt, render

from services.api.answer_contract import AnswerContract
from services.api.point_conditions import condition_measures


@pytest.mark.parametrize("text", [
    "Nominal supply voltage < 3.3 V.",
    "Nominal supply voltage ≤ 3.3 V.",
    "Nominal supply voltage > 3.3 V.",
    "Nominal supply voltage >= 3.3 V.",
    "Nominal supply voltage ≠ 3.3 V.",
    "Nominal supply voltage != 3.3 V.",
    "Nominal supply voltage <> 3.3 V.",
    "Nominal supply voltage is less than 3.3 V.",
    "Nominal supply voltage is at most 3.3 V.",
    "Nominal supply voltage is at least 3.3 V.",
    "Nominal supply voltage is different from 3.3 V.",
    "Nominal supply voltage is 3.3 V or less.",
    "La tension nominale d’alimentation est inférieure à 3,3 V.",
    "La tension nominale d’alimentation est différente de 3,3 V.",
    "La tension nominale d’alimentation n’excède pas 3,3 V.",
    "La tension nominale d’alimentation est au plus de 3,3 V.",
])
def test_non_exact_operand_never_establishes_an_exact_numeric_fact(text):
    cat = catalogue("What is the nominal supply voltage?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]
    assert result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("qualified", [
    "Nominal supply voltage is less than 3.3 V.",
    "Nominal supply voltage ≠ 3.3 V.",
    "Nominal supply voltage is at most 3.3 V.",
])
def test_comparison_cannot_equate_a_bound_or_excluded_value_with_an_exact_value(qualified):
    refs = [excerpt("R001", qualified, document="bounded"),
            excerpt("R002", "Nominal supply voltage is 3.3 V.", document="exact")]
    cat = catalogue("Compare les tensions nominales d’alimentation.", refs, mode="comparison")
    result = render(cat, ["R001", "R002"], required_documents=["bounded", "exact"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["comparisons"]
    assert "concordent" not in result["text"]
    assert qualified in result["text"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("modifier", ["unless", "except at", "except when", "without", "sauf à", "sauf si", "sans"])
def test_excluded_test_point_cannot_satisfy_the_requested_positive_point(modifier):
    text = f"Output current is 8 mA {modifier} TA = 25 °C."
    cat = catalogue("What output current at TA = 25 °C?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]
    assert result["support_validation"]["status"] == "passed"
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("text", [
    "Nominal supply voltage is 3.3 V.",
    "Nominal supply voltage = 3.3 V.",
    "Nominal supply voltage is exactly 3.3 V.",
    "La tension nominale d’alimentation est de 3,3 V.",
    "Nominal supply voltage is 3.3 V when TA < 85 °C.",
])
def test_exact_values_remain_usable_and_other_quantity_bounds_are_not_transferred(text):
    cat = catalogue("What is the nominal supply voltage?", [excerpt("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["values"] == ["3.3"]
    assert text in result["text"]
    assert cat.deterministic_plan() is not None


@pytest.mark.parametrize("text", [
    "Output current is 8 mA at TA = 25 °C.",
    "Output current is 8 mA when TA = 25 °C.",
    "Output current is 8 mA at TA = 25 °C, except at VDD = 0 V.",
])
def test_positive_point_condition_remains_available(text):
    assessment = AnswerContract("What output current at TA = 25 °C?", "question").assess([excerpt("R001", text)])
    assert assessment["status"] == "covered"
    assert assessment["matched_relations"][0]["values"] == ["8"]


def test_point_metadata_for_a_negative_predicate_is_retained_for_literal_scope_checks():
    points = condition_measures("The output current is not established at TA = 25 °C.")
    assert len(points) == 1
    assert points[0]["symbol"] == "TA" and points[0]["value"] == "298.15"


def test_strict_upper_bound_is_not_a_maximum_value():
    text = "Supply voltage is less than 3.3 V."
    assessment = AnswerContract("What is the maximum supply voltage?", "question").assess([excerpt("R001", text)])
    assert assessment["status"] != "covered"
    assert not assessment["matched_relations"]


@pytest.mark.parametrize("question", [
    "What output current except at TA = 25 °C?",
    "What output current unless TA = 25 °C?",
    "Quel courant de sortie sauf à TA = 25 °C ?",
])
def test_excluded_point_in_a_question_is_not_erased_into_an_unrestricted_request(question):
    cat = catalogue(question, [excerpt("R001", "Output current is 8 mA at TA = 25 °C.")])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert "excluded_point_condition_not_supported" in {
        item["requirement"] for item in result["answer_contract"]["missing"]}
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize(("text", "value"), [
    ("Output current is 8 mA unless (TA = 25 °C).", "25"),
    ("Output current is 8 mA except at TA = 25 °C or TA = 85 °C.", "85"),
    ("Output current is 8 mA except (TA = 25 °C) or (TA = 85 °C).", "85"),
])
def test_parentheses_and_directly_coordinated_exclusions_do_not_invert_the_point(text, value):
    cat = catalogue(f"What output current at TA = {value} °C?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("excepted", ["25 °C", "298.15 K"])
def test_excluded_point_vetoes_an_identical_positive_point(excepted):
    text = f"Output current is 8 mA at TA = 25 °C except at TA = {excepted}."
    cat = catalogue("What output current at TA = 25 °C?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


@pytest.mark.parametrize("excepted", ["TA = 85 °C", "TJ = 25 °C"])
def test_distinct_explicit_exception_does_not_replace_the_positive_point(excepted):
    text = f"Output current is 8 mA at TA = 25 °C except at {excepted}."
    cat = catalogue("What output current at TA = 25 °C?", [excerpt("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert text in result["text"]


@pytest.mark.parametrize("question", ["What output current?", "What output current at TA = 25 °C?"])
def test_leading_excluded_condition_remains_in_literal_and_relation(question):
    text = "Unless TA = 25 °C, output current is 8 mA."
    cat = catalogue(question, [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert text in result["text"]
    assessment = result["answer_contract"]
    facts = [*assessment["matched_relations"], *assessment["rejected_relations"]]
    assert facts and all("Unless TA = 25 °C" in fact["condition"] for fact in facts)
    if "25" in question:
        assert assessment["status"] != "covered"
        assert not assessment["matched_relations"]


@pytest.mark.parametrize("text", [
    "Nominal supply voltage < (3.3 V).",
    "Nominal supply voltage ≤ [3.3 V].",
    "Nominal supply voltage is less than (3.3 V).",
    "Nominal supply voltage is (3.3 V) or less.",
])
def test_parentheses_cannot_hide_a_numeric_operator(text):
    cat = catalogue("What is the nominal supply voltage?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]


def test_unless_otherwise_noted_is_a_default_condition_not_an_excluded_point():
    text = "Output current is 8 mA at TA = 25 °C unless otherwise noted."
    cat = catalogue("What output current at TA = 25 °C?", [excerpt("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert text in result["text"]


@pytest.mark.parametrize("connector", ["at", "except at"])
def test_explicit_test_variables_do_not_become_extra_requested_quantities(connector):
    question = "What output current at TA = 25 °C and VDD = 3.3 V?"
    text = f"Output current is 8 mA {connector} TA = 25 °C and VDD = 3.3 V."
    contract = AnswerContract(question, "question")
    assert contract.kind == "value" and contract.quantity == "current"
    assessment = contract.assess([excerpt("R001", text)])
    if connector == "at":
        assert assessment["status"] == "covered"
        assert {fact["quantity"] for fact in assessment["matched_relations"]} == {"current"}
        assert len(assessment["obligations"]) == 1
    else:
        assert assessment["status"] != "covered"
        assert not assessment["matched_relations"]


@pytest.mark.parametrize("temperature", ["25", "85"])
def test_genuine_composite_requests_preserve_each_original_point_and_unit(temperature):
    question = "What supply voltage at TA = 25 °C and output current at TA = 85 °C?"
    refs = [excerpt("R001", "Supply voltage is 3.3 V at TA = 25 °C."),
            excerpt("R002", f"Output current is 8 mA at TA = {temperature} °C.")]
    contract = AnswerContract(question, "question")
    assert contract.kind == "composite"
    assert all(part.request_clause in question for part in contract.components)
    assert [part.requested_point_conditions[0]["value"] for part in contract.components] == ["298.15", "358.15"]
    assessment = contract.assess(refs)
    assert (assessment["status"] == "covered") is (temperature == "85")


def test_composite_query_keeps_a_component_exclusion_as_an_analysis_limit():
    question = "What supply voltage except at TA = 25 °C and output current at TA = 85 °C?"
    contract = AnswerContract(question, "question")
    assert contract.kind == "composite"
    assert "excluded_point_condition_not_supported" in contract.components[0].parse_failures
    refs = [excerpt("R001", "Supply voltage is 3.3 V at TA = 25 °C."),
            excerpt("R002", "Output current is 8 mA at TA = 85 °C.")]
    assessment = contract.assess(refs)
    assert assessment["status"] != "covered"
    assert not any(fact["quantity"] == "voltage" for fact in assessment["matched_relations"])


@pytest.mark.parametrize("suffix", ["maximum", "minimum", "max.", "min."])
def test_postposed_bound_is_not_an_exact_nominal_value(suffix):
    text = f"Nominal supply voltage is 3.3 V {suffix}"
    cat = catalogue("What is the nominal supply voltage?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("bound", ["Maximum", "Minimum"])
def test_prefix_bound_value_remains_available_when_that_bound_is_requested(bound):
    text = f"{bound} supply voltage is 3.3 V."
    cat = catalogue(f"What is the {bound.lower()} supply voltage?", [excerpt("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["bound_role"] == bound.lower()
    assert text in result["text"]
