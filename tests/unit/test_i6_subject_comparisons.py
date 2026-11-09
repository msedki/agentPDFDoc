"""Comparative scope regressions; literal source-bound renderer, no live LLM.

The token counter is the existing unit double. These cases are development
counterexamples, not the sealed I6 final fixture.
"""

import copy

import pytest
from test_enhanced_answers import catalogue, excerpt, render

from services.api.errors import ApiError


def compare(question, texts, documents=None, *, keep_all=True, names=None):
    documents = documents or [f"document-{index}" for index in range(len(texts))]
    names = names or [f"Record {index}" for index in range(len(texts))]
    references = [
        excerpt(f"R{index:03d}", text, document=document, name=name)
        for index, (text, document, name) in enumerate(zip(texts, documents, names, strict=True), 1)
    ]
    cat = catalogue(question, references, mode="comparison")
    result = render(cat, [ref["id"] for ref in references], required_documents=list(dict.fromkeys(documents)))
    assert result["support_validation"]["status"] == "passed"
    assert all(text in result["text"] for text in (texts if keep_all else texts[:1]))
    return cat, result


@pytest.mark.parametrize(("language", "second", "expected"), [
    ("en", "4.6", "equal"), ("en", "6.2", "different"),
    ("fr", "4.6", "equal"), ("fr", "6.2", "different"),
])
def test_subject_comparison_uses_each_subjects_own_explicit_evidence(language, second, expected):
    question = ("Compare the nominal voltages of ZR410 and ZR411." if language == "en"
                else "Compare les tensions nominales du ZR410 et du ZR411.")
    texts = (["The nominal voltage of ZR410 is 4.6 V.", f"The nominal voltage of ZR411 is {second} V."]
             if language == "en" else
             ["La tension nominale du ZR410 est de 4.6 V.", f"La tension nominale du ZR411 est de {second} V."])
    _, result = compare(question, texts)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert len(assessment["obligations"]) == 2
    assert all(item["covered"] for item in assessment["obligations"])
    assert len(assessment["comparisons"]) == 1
    comparison = assessment["comparisons"][0]
    assert comparison["status"] == comparison["numeric_agreement"] == expected
    assert set(comparison["reference_ids"]) == {"R001", "R002"}
    assert "ZR410" in result["text"] and "ZR411" in result["text"]


def test_subjects_may_be_compared_inside_one_document():
    _, result = compare(
        "Compare the nominal voltages of ZR410 and ZR411.",
        ["The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V."],
        ["shared", "shared"],
    )
    assert result["answer_contract"]["status"] == "covered"
    assert [item["status"] for item in result["answer_contract"]["comparisons"]] == ["different"]


@pytest.mark.parametrize("question", [
    "Compare the nominal voltages of ZR410 and ZR411 in each document.",
    "Compare les tensions nominales du ZR410 et du ZR411 dans chaque document.",
])
def test_explicit_each_document_keeps_every_subject_document_obligation(question):
    _, result = compare(question, [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
    ])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert len(assessment["obligations"]) == 4
    assert sum(item["covered"] for item in assessment["obligations"]) == 2
    assert not assessment["comparisons"]


def test_each_document_compares_subjects_separately_when_all_evidence_exists():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411 in each document.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
        "The nominal voltage of ZR410 is 7.8 V.", "The nominal voltage of ZR411 is 7.8 V.",
    ], ["first", "first", "second", "second"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert len(assessment["obligations"]) == 4
    assert sorted(item["status"] for item in assessment["comparisons"]) == ["different", "equal"]
    assert {tuple(item["document_ids"]) for item in assessment["comparisons"]} == {("first",), ("second",)}


def test_missing_subject_is_not_inferred_from_document_name_or_equal_value():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR412 is 4.6 V.",
    ], keep_all=False, names=["ZR410", "ZR411"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["comparisons"]
    assert any(item.get("subject") == "ZR411" and not item["covered"] for item in assessment["obligations"])


@pytest.mark.parametrize("second", [
    pytest.param("The maximum voltage of ZR411 is 4.6 V.", id="role"),
    pytest.param("The nominal input voltage of ZR411 is 4.6 V.", id="property"),
    pytest.param("The nominal output voltage of ZR411 is 4.6 V at TA = 95 °C.", id="condition"),
    pytest.param("The nominal output voltage of ZR411 is less than 4.6 V at TA = 35 °C.", id="nonexact"),
])
def test_compared_subject_does_not_erase_other_relation_qualifications(second):
    _, result = compare("Compare the nominal output voltages of ZR410 and ZR411 at TA = 35 °C.", [
        "The nominal output voltage of ZR410 is 4.6 V at TA = 35 °C.", second,
    ], keep_all=False)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["status"] == "equal" for item in result["answer_contract"]["comparisons"])
    assert "les valeurs citées concordent" not in result["text"]


def test_conflicting_values_for_a_subject_across_documents_block_subject_comparison():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.",
        "The nominal voltage of ZR410 is 6.2 V.",
        "The nominal voltage of ZR411 is 4.6 V.",
    ])
    assessment = result["answer_contract"]
    assert assessment["status"] == "conflict"
    assert not any(item["status"] in {"equal", "different"} for item in assessment["comparisons"])
    assert {"R001", "R002"} <= set(assessment["required_reference_ids"])


def test_equal_sets_of_contradictory_values_do_not_establish_scalar_equality():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR410 is 6.2 V.",
        "The nominal voltage of ZR411 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
    ])
    assert result["answer_contract"]["status"] == "conflict"
    assert not any(item["status"] == "equal" for item in result["answer_contract"]["comparisons"])
    assert "les valeurs citées concordent" not in result["text"]


def test_single_subject_document_comparison_keeps_document_disagreement():
    _, result = compare("Compare the nominal voltage of ZR410 between the two documents.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR410 is 6.2 V.",
    ])
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert not assessment["conflicts"]
    assert [item["status"] for item in assessment["comparisons"]] == ["different"]


def test_filename_alone_cannot_supply_a_compared_subject():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage is 4.6 V.",
    ], names=["ZR410 datasheet", "ZR411 datasheet"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["comparisons"]
    assert not any("ZR411" in fact["subjects"] for fact in assessment["matched_relations"])
    assert any("comparison_subject_not_explicit" in fact["reasons"] for fact in assessment["rejected_relations"])


def test_common_values_requested_from_documents_do_not_turn_into_subject_agreement():
    _, result = compare("Which common nominal voltages do documents A and B establish for both ZR410 and ZR411?", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
        "The nominal voltage of ZR410 is 6.2 V.", "The nominal voltage of ZR411 is 4.6 V.",
    ], ["first", "first", "second", "second"])
    assessment = result["answer_contract"]
    assert assessment["comparison_axis"] == "documents"
    assert assessment["status"] == "conflict"
    assert len(assessment["obligations"]) == 4
    assert all(item["status"] == "different" for item in assessment["comparisons"])


def test_subject_comparison_does_not_require_a_value_in_an_unrelated_extra_document():
    cat, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
        "The output current of ZR412 is 19 mA.",
    ], keep_all=False)
    assert result["answer_contract"]["status"] == "covered"
    assert len(result["answer_contract"]["obligations"]) == 2
    assert cat.contract._obligation_work(3)[0] == 2


def test_comparison_keeps_subjects_bound_to_their_cited_operands():
    _, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
    ])
    comparison, = result["answer_contract"]["comparisons"]
    assert comparison["operand_groups"] == [
        {"subject": "ZR410", "reference_ids": ["R001"]},
        {"subject": "ZR411", "reference_ids": ["R002"]},
    ]
    assert "ZR410 / ZR411" in result["text"]


def test_collective_subject_ranges_keep_cross_document_conflicts():
    _, result = compare("Comparer les plages de tension d'alimentation DEV123 et DEV456", [
        "DEV123 operating supply voltage: 1 to 3 V. DEV456 operating supply voltage: 2 to 4 V.",
        "DEV123 operating supply voltage: 2 to 4 V. DEV456 operating supply voltage: 1 to 3 V.",
    ])
    assessment = result["answer_contract"]
    assert assessment["status"] == "conflict"
    assert not any(item["status"] == "equal" for item in assessment["comparisons"])


@pytest.mark.parametrize(("field", "value"), [("comparison_axis", "documents"), ("comparison_per_document", True)])
def test_published_comparison_axis_is_reverified(field, value):
    cat, result = compare("Compare the nominal voltages of ZR410 and ZR411.", [
        "The nominal voltage of ZR410 is 4.6 V.", "The nominal voltage of ZR411 is 6.2 V.",
    ])
    tampered = copy.deepcopy(result)
    tampered["answer_contract"][field] = value
    with pytest.raises(ApiError, match="restitution"):
        cat.verify_rendered(tampered)
