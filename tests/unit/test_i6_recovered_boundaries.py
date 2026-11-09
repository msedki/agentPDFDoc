"""New reproductions from the I6 recovery notes, not recovered historical tests.

The real contract and renderer are exercised with literal public fixtures and
the existing character-tokenizer double. No FINAL, model or native RAG is used.
"""

import pytest
from test_enhanced_answers import catalogue, excerpt, render

from services.api.answer_contract import AnswerContract
from services.api.errors import ApiError
from services.api.predicate_conditions import predicate_conditions


@pytest.mark.parametrize(("written", "requested"), [("mA", "MA"), ("x²", "x₂"), ("α²", "α2")])
def test_opaque_predicate_symbols_are_not_equated(written, requested):
    text = f"The nominal voltage is 5.3 V when selector is {written}."
    cat = catalogue(f"What is the nominal voltage when selector is {requested}?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert any("requested_predicate_condition_not_established" in fact["reasons"]
               for fact in result["answer_contract"]["rejected_relations"])
    assert text in result["text"] and result["citation_spans"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("written", ["mA", "MA", "x²", "x₂", "α²", "α2"])
def test_opaque_predicate_literal_identity_and_whitespace_remain_supported(written):
    text = f"The nominal voltage is 5.3 V when selector   is {written}."
    cat = catalogue(f"What is the nominal voltage when selector is {written}?", [excerpt("R001", text)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "covered"
    assert len(result["answer_contract"]["matched_relations"]) == 1
    assert text in result["text"] and result["support_validation"]["status"] == "passed"


def test_predicate_key_preserves_original_unicode_and_case():
    request, = predicate_conditions("when I² equals I₂ and selector is mA")
    assert request["key"] == "I² equals I₂ and selector is mA"


@pytest.mark.parametrize("mode", ["question", "comparison"])
def test_qualitative_document_subject_budget_precedes_candidate_allocation(mode, monkeypatch):
    question = "What is the function of the clock of AX1 and AX2?"
    contract = AnswerContract(question, mode)
    documents = [f"document-{index:03d}" for index in range(128)]
    assessment = contract.assess([], required_documents=documents)
    assert contract._obligation_work(len(documents))[0] == 256
    assert len(assessment["obligations"]) == 256
    assert len({obligation["obligation_id"] for obligation in assessment["obligations"]}) == 256

    def forbidden_candidates(*args, **kwargs):
        raise AssertionError("The complete Cartesian budget must be checked before candidate work")

    monkeypatch.setattr(AnswerContract, "_qualitative_candidates", forbidden_candidates)
    with pytest.raises(ApiError) as failure:
        contract.assess([], required_documents=[*documents, "document-128"])
    assert failure.value.code == "question_scope_too_complex"
    assert failure.value.details["max_obligations"] == 256


@pytest.mark.parametrize(("question", "voltage", "current"), [
    ("When mode is SAFE, what is the nominal voltage and output current?",
     "The nominal voltage is 5.3 V when mode is SAFE.", "The output current is 17 mA when mode is {mode}."),
    ("Lorsque le mode est SAFE, quelles sont la tension nominale et le courant de sortie ?",
     "La tension nominale est de 5,3 V lorsque le mode est SAFE.", "Le courant de sortie est de 17 mA lorsque le mode est {mode}."),
])
@pytest.mark.parametrize("current_mode", ["SAFE", "OTHER"])
def test_leading_predicate_is_required_for_each_quantity(question, voltage, current, current_mode):
    current = current.format(mode=current_mode)
    cat = catalogue(question, [excerpt("R001", voltage), excerpt("R002", current)])
    assert cat.contract.kind == "composite"
    assert all(part.requested_predicate_conditions for part in cat.contract.components)
    result = render(cat, ["R001", "R002"])
    assessment = result["answer_contract"]
    assert (assessment["status"] == "covered") is (current_mode == "SAFE")
    assert {fact["quantity"] for fact in assessment["matched_relations"]} == (
        {"voltage", "current"} if current_mode == "SAFE" else {"voltage"})
    assert voltage in result["text"] and current in result["text"]
    assert len(result["citation_spans"]) >= 2
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("question", [
    "When mode is SAFE what is the nominal voltage and output current?",
    "When mode is SAFE what is the nominal voltage, and output current?",
    "When , what is the nominal voltage and output current?",
    "Lorsque le mode est SAFE quelles sont la tension nominale et le courant de sortie ?",
])
def test_truncated_shared_predicate_cannot_admit_any_operand(question):
    texts = ["The nominal voltage is 5.3 V when mode is SAFE.",
             "The output current is 17 mA when mode is OTHER."]
    cat = catalogue(question, [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"]
    assert not any(item["covered"] for item in assessment["obligations"])
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"


def test_separately_requested_predicates_remain_local_to_their_quantity():
    texts = ["The nominal voltage is 5.3 V when mode is SAFE.",
             "The output current is 17 mA when mode is OTHER."]
    cat = catalogue("Give the nominal voltage when mode is SAFE, and output current when mode is OTHER.",
                    [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    assessment = render(cat, ["R001", "R002"])["answer_contract"]
    assert assessment["status"] == "covered"
    assert {fact["quantity"] for fact in assessment["matched_relations"]} == {"voltage", "current"}


@pytest.mark.parametrize(("current_point", "covered"), [
    ("TA = 31 °C", True), ("TA = 304.15 K", True), ("TA = 80 °C", False), ("TJ = 31 °C", False),
])
@pytest.mark.parametrize("connector", ["When", "At", "À", "For"])
def test_shared_numeric_point_preserves_symbol_and_exact_unit_conversion(current_point, covered, connector):
    texts = ["The nominal voltage is 5.3 V at TA = 31 °C.",
             f"The output current is 17 mA at {current_point}."]
    cat = catalogue(f"{connector} TA = 31 °C, what is the nominal voltage and output current?",
                    [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assessment = result["answer_contract"]
    assert (assessment["status"] == "covered") is covered
    assert {fact["quantity"] for fact in assessment["matched_relations"]} == (
        {"voltage", "current"} if covered else {"voltage"})
    assert all(part.requested_point_conditions for part in cat.contract.components)
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize(("current_mode", "current_point", "covered"), [
    ("SAFE", "TA = 31 °C", True), ("OTHER", "TA = 31 °C", False),
    ("SAFE", "TA = 80 °C", False), ("SAFE", "TJ = 31 °C", False),
])
def test_shared_verbal_and_numeric_conditions_are_both_preserved(current_mode, current_point, covered):
    texts = ["The nominal voltage is 5.3 V when mode is SAFE; at TA = 31 °C.",
             f"The output current is 17 mA when mode is {current_mode}; at {current_point}."]
    cat = catalogue("When mode is SAFE, at TA = 31 °C, what is the nominal voltage and output current?",
                    [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assessment = result["answer_contract"]
    assert (assessment["status"] == "covered") is covered
    assert {fact["quantity"] for fact in assessment["matched_relations"]} == (
        {"voltage", "current"} if covered else {"voltage"})
    assert all(part.requested_predicate_conditions and part.requested_point_conditions
               for part in cat.contract.components)
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("connector", ["Unless", "Except when", "Sauf si", "Except at", "Sauf à"])
def test_shared_excluded_point_cannot_become_a_positive_condition(connector):
    texts = ["The nominal voltage is 5.3 V at TA = 31 °C.", "The output current is 17 mA at TA = 31 °C."]
    cat = catalogue(f"{connector} TA = 31 °C, what is the nominal voltage and output current?",
                    [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert all("excluded_point_condition_not_supported" in part.parse_failures for part in cat.contract.components)
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("question", [
    "When TA = 31 °C what is the nominal voltage and output current?",
    "When mode is SAFE, at TA = 31 °C what is the nominal voltage and output current?",
])
def test_incomplete_shared_numeric_scope_preserves_diagnostics_without_operands(question):
    texts = ["The nominal voltage is 5.3 V when mode is SAFE; at TA = 31 °C.",
             "The output current is 17 mA when mode is SAFE; at TA = 80 °C."]
    cat = catalogue(question, [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("alternative", ["or", "ou"])
def test_shared_point_alternatives_are_not_rewritten_as_a_conjunction(alternative):
    texts = ["The nominal voltage is 5.3 V at TA = 31 °C and TA = 80 °C.",
             "The output current is 17 mA at TA = 31 °C and TA = 80 °C."]
    cat = catalogue(f"When TA = 31 °C {alternative} TA = 80 °C, what is the nominal voltage and output current?",
                    [excerpt("R001", texts[0]), excerpt("R002", texts[1])])
    result = render(cat, ["R001", "R002"])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert all(text in result["text"] for text in texts)
    assert result["citation_spans"] and result["support_validation"]["status"] == "passed"
