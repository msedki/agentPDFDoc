"""Public development controls for verbal conditions and diagnostic evidence.

Uses the real catalogue/rendering and the existing character-token double.
No heldout fixture, retrieval or native inference is exercised here.
"""

import pytest
from test_enhanced_answers import catalogue, excerpt, render


@pytest.mark.parametrize(("suffix", "covered"), [
    ("when the output is short-circuited", True),
    ("unless the output is short-circuited", False),
    ("unless when the output is short-circuited", False),
    ("unless at TA = 32.5 °C when the output is short-circuited", False),
    ("when the output is enabled", False),
    ("when the output is short-circuited unless the input is enabled", False),
])
def test_requested_verbal_condition_requires_literal_positive_support(suffix, covered):
    text = "The output current of CX810 is 17 mA at TA = 32 °C " + suffix + "."
    cat = catalogue("What is the output current of CX810 at TA = 32 °C when the output is short-circuited?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert (result["answer_contract"]["status"] == "covered") is covered
    assert bool(result["answer_contract"]["matched_relations"]) is covered
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize(("source_connector", "expected"), [("lorsque", "covered"), ("sauf lorsque", "partial")])
def test_french_verbal_conditions_preserve_their_polarity(source_connector, expected):
    text = f"Le courant de sortie du CX810 est de 17 mA à TA = 32 °C {source_connector} la sortie est court-circuitée."
    cat = catalogue("Quel courant de sortie du CX810 à TA = 32 °C lorsque la sortie est court-circuitée ?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == expected
    assert text in result["text"] and result["support_validation"]["status"] == "passed"


def test_numeric_point_conditions_keep_their_existing_grammar():
    text = "Output current is 17 mA when TA = 32 °C."
    cat = catalogue("What output current when TA = 32 °C?", [excerpt("R001", text)])
    assert not cat.contract.requested_predicate_conditions
    assert render(cat, ["R001"])["answer_contract"]["status"] == "covered"


def test_wrong_role_is_cited_as_a_limit_without_becoming_the_requested_operand():
    texts = ["The nominal voltage of CX810 is 4.8 V.", "The maximum voltage of CX811 is 4.8 V."]
    cat = catalogue("Compare the nominal voltages of CX810 and CX811.", [
        excerpt("R001", texts[0], document="first"), excerpt("R002", texts[1], document="second"),
    ], mode="comparison")
    result = render(cat, ["R001", "R002"], required_documents=["first", "second"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial" and not assessment["comparisons"]
    assert {fact["reference_id"] for fact in assessment["matched_relations"]} == {"R001"}
    assert any("requested_role_not_established" in fact["reasons"] for fact in assessment["rejected_relations"])
    assert all(text in result["text"] for text in texts)
    assert result["support_validation"]["status"] == "passed"


def test_unresolved_named_alternative_preserves_its_diagnostic_without_assigning_the_value():
    text = ("The nominal voltage of either CX810 or CX811 is 4.8 V; "
            "the source does not identify which device.")
    cat = catalogue("Compare the nominal voltages of CX810 and CX811.", [excerpt("R001", text)], mode="comparison")
    result = render(cat, ["R001"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"] and not assessment["comparisons"]
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"
