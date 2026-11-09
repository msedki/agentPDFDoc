"""Development counterexamples found by independent review of R1.

Real catalogue/rendering; the existing token counter is a test double. These
cases verify written identity and nonlocal restrictions, not native retrieval.
"""

import pytest
from test_enhanced_answers import catalogue, excerpt, render


def test_short_written_subject_survives_an_independent_quantity_decision():
    text = "Component AX71. The nominal voltage is 4.8 V; the output current is 19 mA."
    result = render(catalogue("What is the nominal voltage of AX71?", [excerpt("R001", text)]), ["R001"])
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["subjects"] == ["AX71"]
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("text", [
    "The nominal voltage is 4.8 V; the output current is 19 mA; the nominal voltage is not established.",
    "The nominal voltage is 4.8 V; the output current is 19 mA; this value is not guaranteed.",
    "It is not true that (the nominal voltage is 4.8 V; the output current is 19 mA).",
])
def test_later_correction_or_crossing_group_cannot_be_discarded(text):
    result = render(catalogue("What is the nominal voltage?", [excerpt("R001", text)]), ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"


def test_following_restriction_attaches_to_the_selected_second_quantity():
    text = ("The nominal voltage is 4.8 V; the output current is 19 mA. "
            "The output current is not established.")
    result = render(catalogue("What output current?", [excerpt("R001", text)]), ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"
