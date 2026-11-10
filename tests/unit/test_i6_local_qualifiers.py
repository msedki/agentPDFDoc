"""Lexical descriptors stay local while dominant evidence scopes stay whole.

The application catalogue/rendering are real; only the existing character
tokenizer is doubled. These tests do not exercise retrieval or a native LLM.
"""

import json
from pathlib import Path

import pytest
from test_enhanced_answers import catalogue, excerpt, render


def assess(question, text):
    return render(catalogue(question, [excerpt("R001", text)]), ["R001"])


@pytest.mark.parametrize(("case_id", "quantity", "prop", "role"), [
    ("I6D28", "voltage", None, "nominal"),
    ("I6D32", "current", "output", None),
])
def test_published_rejected_relations_keep_their_actual_local_qualifiers(case_id, quantity, prop, role):
    fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures/support_i6_dev.json").read_text())
    case = next(case for case in fixture["cases"] if case["id"] == case_id)
    text = case["sources"][0]["text"]
    result = assess(case["question"], text)
    contract = result["answer_contract"]
    assert contract["status"] == "partial" and not contract["matched_relations"]
    fact, = contract["rejected_relations"]
    assert (fact["quantity"], fact["property"], fact["role"]) == (quantity, prop, role)
    assert fact["assertion_status"] == "negated"
    assert "source_assertion_negated" in fact["reasons"]
    assert fact["quote"] == text == text[fact["source_start"]:fact["source_end"]]
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("connector", [" and ", "; ", ", but "])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("dominant", [True, False])
@pytest.mark.parametrize("french", [True, False])
def test_coordination_never_lends_role_or_property(connector, reverse, dominant, french):
    clauses = (["la tension nominale de ZK580 est de 8.4 V", "le courant de sortie de ZK580 est de 23 mA"]
               if french else ["the nominal voltage of ZK580 is 8.4 V", "the output current of ZK580 is 23 mA"])
    if french:
        connector = {" and ": " et ", "; ": "; ", ", but ": ", mais "}[connector]
    if reverse:
        clauses.reverse()
    prefix = ("Il n'est pas établi que " if french else "It is not established that ") if dominant else ""
    text = prefix + connector.join(clauses) + "."
    questions = [("Quelle est la tension nominale de ZK580 ?" if french else "What is the nominal voltage of ZK580?",
                  "voltage", None, "nominal", "8.4"),
                 ("Quel est le courant de sortie de ZK580 ?" if french else "What is the output current of ZK580?",
                  "current", "output", None, "23")]
    for question, quantity, prop, role, value in questions:
        result = assess(question, text)
        contract = result["answer_contract"]
        assert (contract["status"] == "covered") is (not dominant)
        relations = contract["rejected_relations"] if dominant else contract["matched_relations"]
        fact, = relations
        assert (fact["quantity"], fact["property"], fact["role"]) == (quantity, prop, role)
        assert fact["values"] == [value] and fact["quote"] == text
        assert fact["assertion_status"] == ("negated" if dominant else "asserted")
        assert text[fact["source_start"]:fact["source_end"]] == text
        assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("prefix", [
    "No part of the following statement is established: ",
    "It is not true that ",
])
@pytest.mark.parametrize("tail", ["", " when TA = 37 °C", " unless TA = 37 °C"])
def test_lexical_scope_never_removes_the_dominant_denial_or_condition(prefix, tail):
    text = prefix + "the nominal voltage of ZK580 is 8.4 V and the output current of ZK580 is 23 mA" + tail + "."
    result = assess("What is the output current of ZK580 at TA = 37 °C?", text)
    contract = result["answer_contract"]
    assert contract["status"] != "covered" and not contract["matched_relations"]
    fact, = contract["rejected_relations"]
    assert fact["property"] == "output" and fact["role"] is None
    assert fact["assertion_status"] == "negated" and fact["quote"] == text
    assert text in result["text"] and result["support_validation"]["status"] == "passed"


def test_a_bounded_value_keeps_its_modifier_within_the_local_label():
    text = "It is not established that the maximum voltage is less than 8.4 V and the input current is 23 mA."
    result = assess("What is the maximum voltage?", text)
    fact, = result["answer_contract"]["rejected_relations"]
    assert fact["bound_role"] == "maximum" and fact["property"] is None
    assert "less than" in fact["label"]
    assert "numeric_relation_not_exact" in fact["note_issues"]
    assert fact["assertion_status"] == "negated" and fact["quote"] == text


@pytest.mark.parametrize("condition", ["TA = 37 °C", "ambient temperature 37 °C"])
@pytest.mark.parametrize("where", ["first", "second"])
@pytest.mark.parametrize("french", [False, True])
def test_a_leading_point_condition_does_not_hide_the_local_quantity_descriptor(where, french, condition):
    clauses = (["la tension nominale de ZK580 est de 8.4 V", "le courant de sortie de ZK580 est de 23 mA"]
               if french else ["the nominal voltage of ZK580 is 8.4 V", "the output current of ZK580 is 23 mA"])
    index = 0 if where == "first" else 1
    if french:
        condition = condition.replace("ambient temperature", "température ambiante")
    clauses[index] = ("à " if french else "at ") + condition + " " + clauses[index]
    text = ("Il n'est pas établi que " if french else "It is not established that ")
    text += (" et " if french else " and ").join(clauses) + "."
    question = "Quel est le courant de sortie de ZK580 ?" if french else "What is the output current of ZK580?"
    result = assess(question, text)
    contract = result["answer_contract"]
    assert not contract["matched_relations"] and contract["status"] == "partial"
    fact, = contract["rejected_relations"]
    assert fact["property"] == "output" and fact["role"] is None
    assert fact["assertion_status"] == "negated" and fact["quote"] == text
    assert condition in result["text"]
    assert result["support_validation"]["status"] == "passed"
