"""Verified list subjects outrank a filename without inventing entity bindings.

Synthetic parser/embedding boundaries are explicit. Adapter, SQLite, indexing,
scope and catalogue provenance checks are real; no OCR or generator is run.
"""

import copy
import json

import pytest
import test_i4_pdf_structure as fixtures
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_i4_inline_pdf_lists import inline_input

from services.api.structured_answer import StructuredAnswerBuilder


def subject_list(storage, monkeypatch, *, style, heading_subject, item_subject="", requested_subject="DEV123"):
    document, page, observed = inline_input() if style == "inline" else fixtures.adapter_input()
    for block in document["texts"]:
        name = block["self_ref"].rsplit("/", 1)[-1]
        if name == "P":
            prefix = "· " if style == "inline" else ""
            block["text"] = prefix + (heading_subject + " " if heading_subject else "") + "Supply range:"
        elif name in {"V1", "V2"} and item_subject:
            prefix = "– " if style == "inline" else ""
            remainder = block["text"][len(prefix):]
            block["text"] = prefix + item_subject + " " + remainder
        block["orig"] = block["text"]
        block["prov"][0]["charspan"] = [0, len(block["text"])]
    payload = document, page, observed
    monkeypatch.setattr(fixtures, "adapter_input", lambda _case="S01": copy.deepcopy(payload))
    result = fixtures.index_dev(storage, "DEV123")
    contexts = fixtures.contexts(result)
    assert len(contexts) == 2
    for context in contexts.values():
        fixtures.assert_exact_dependencies(result, context)
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(result["sources"], 1)]
    question = "What are the two supply voltage ranges" + (" for " + requested_subject if requested_subject else "") + "?"
    cat = StructuredAnswerBuilder(storage[1], result["snapshot"], question,
                                  enforce_contract=True).catalogue(sources, "question")
    assert all(reference["document_name"] == "DEV123.pdf" for reference in cat.references)
    return cat, result


@pytest.mark.parametrize("style", ["inline", "separate"])
def test_verified_heading_subject_cannot_be_overridden_by_document_filename(storage, monkeypatch, tmp_path, style):
    cat, result = subject_list(storage, monkeypatch, style=style, heading_subject="DEV456")
    assessment = cat.assess()
    (tmp_path / "heading-subject-diagnostic.json").write_text(json.dumps({
        "question": cat.contract.question, "heading": result["names"]["P"]["text"],
        "filename": "DEV123.pdf", "assessment": assessment,
    }, ensure_ascii=False, indent=2) + "\n")
    assert assessment["status"] == "partial", assessment
    assert all("DEV123" not in fact["subjects"] for fact in assessment["matched_relations"])
    assert any(item["requirement"] == "requested_subject_quantity" for item in assessment["missing"])
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("style", ["inline", "separate"])
@pytest.mark.parametrize(("heading_subject", "item_subject", "requested_subject"), [
    ("DEV456", "", "DEV456"),
    ("DEV456", "DEV456", "DEV456"),
    ("DEV123", "", "DEV123"),
    ("", "DEV456", "DEV456"),
])
def test_explicit_compatible_subjects_and_subjectless_headings_keep_supported_answers(storage, monkeypatch, style,
                                                                                     heading_subject, item_subject,
                                                                                     requested_subject):
    cat, result = subject_list(storage, monkeypatch, style=style, heading_subject=heading_subject,
                              item_subject=item_subject, requested_subject=requested_subject)
    assessment = cat.assess()
    assert assessment["status"] == "covered", assessment
    assert len(assessment["matched_relations"]) == 2
    assert all(fact["subjects"] == [requested_subject] for fact in assessment["matched_relations"])
    plan = cat.deterministic_plan()
    assert plan is not None
    answer = render(cat, plan.references)
    assert answer["answer_contract"]["status"] == "covered"
    assert answer["support_validation"]["unsupported_characters"] == 0
    assert result["names"]["P"]["text"] in answer["text"]
    for fact in assessment["matched_relations"]:
        assert fact["quote"] in {result["names"][name]["text"] for name in ("V1", "V2")}
        assert fact["condition"] in {"at 25 °C", "at 70 °C"}
        assert set(fact["reference_ids"]) <= set(answer["answer_contract"]["rendered_reference_ids"])


@pytest.mark.parametrize("style", [
    pytest.param("inline", id="inline_filename_and_question_only"),
    pytest.param("separate", id="separate_filename_and_question_only"),
])
def test_subjectless_pdf_list_cannot_inherit_subject_from_filename_or_question(storage, monkeypatch, style):
    cat, result = subject_list(storage, monkeypatch, style=style, heading_subject="", item_subject="",
                              requested_subject="DEV123")
    assert "DEV123" in cat.contract.question
    assert all("DEV123" not in block["text"] for block in result["names"].values())
    assessment = cat.assess()
    assert assessment["status"] == "partial", assessment
    assert all("DEV123" not in fact["subjects"] for fact in assessment["matched_relations"])
    assert any(item["requirement"] == "requested_subject_quantity" for item in assessment["missing"])
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("style", ["inline", "separate"])
@pytest.mark.parametrize("requested_subject", ["DEV123", "DEV456", ""])
def test_conflicting_heading_and_item_subjects_never_establish_a_numeric_binding(storage, monkeypatch, style,
                                                                               requested_subject):
    cat, _ = subject_list(storage, monkeypatch, style=style, heading_subject="DEV456", item_subject="DEV123",
                          requested_subject=requested_subject)
    assessment = cat.assess()
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"]
    assert len(assessment["rejected_relations"]) == 2
    assert all("list_heading_subject_conflict" in fact["reasons"]
               for fact in assessment["rejected_relations"])
    assert all(not obligation["covered"] for obligation in assessment["obligations"])
    assert cat.deterministic_plan() is None
    answer = render(cat, [reference["id"] for reference in cat.references])
    assert answer["answer_contract"]["status"] == "partial"
    assert "DEV456 Supply range:" in answer["text"]
    assert "DEV123 2.4 V to 3.6 V" in answer["text"]
    assert answer["support_validation"]["unsupported_characters"] == 0


@pytest.mark.parametrize("style", ["inline", "separate"])
def test_unrelated_subject_conflict_is_not_a_diagnostic_for_a_third_subject(storage, monkeypatch, style):
    cat, _ = subject_list(storage, monkeypatch, style=style, heading_subject="DEV456", item_subject="DEV123",
                          requested_subject="DEV789")
    assessment = cat.assess()
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"] and not assessment["rejected_relations"]
    assert all(not obligation["covered"] for obligation in assessment["obligations"])


@pytest.mark.parametrize("style", ["inline", "separate"])
def test_multiple_heading_identifiers_do_not_fall_back_to_a_different_filename_subject(storage, monkeypatch, style):
    cat, _ = subject_list(storage, monkeypatch, style=style, heading_subject="DEV456 DEV789")
    assessment = cat.assess()
    assert assessment["status"] == "partial"
    assert all("DEV123" not in fact["subjects"] for fact in assessment["matched_relations"])
    assert cat.deterministic_plan() is None
