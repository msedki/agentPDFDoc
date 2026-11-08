"""Inline written bullets emitted by the real structured parser, generic fixtures.

Parser output/embeddings are doubles; adapter, SQLite, index, scope and
catalogue verification are real. No text or bounding box is synthesized by
the product to split a bullet from its original block.
"""

import copy

import pytest
import test_i4_pdf_structure as fixtures
from test_api_storage import storage as storage

from services.api.structured_answer import StructuredAnswerBuilder


def inline_input(case="inline"):
    document, page, _ = fixtures.adapter_input()
    rows = [
        ("P", "· Supply range:", [44, 700, 170, 712]),
        ("V1", "– 2.4 V to 3.6 V at 25 °C", [58, 680, 285, 690]),
        ("V2", "– 2.7 V to 3.3 V at 70 °C", [58, 660, 285, 670]),
        ("C", "· Supply current:", [44, 640, 180, 652]),
    ]
    document["texts"] = [{"self_ref": f"#/texts/{name}", "parent": {"$ref": "#/body"}, "children": [],
                          "label": "list_item", "orig": text, "text": text,
                          "prov": [{"page_no": 1, "charspan": [0, len(text)], "bbox": fixtures.parser_box(box)}]}
                         for name, text, box in rows]
    document["body"]["children"] = [{"$ref": value["self_ref"]} for value in document["texts"]]
    return document, page, None


def indexed(storage, monkeypatch, mutate=None):
    payload = inline_input()
    if mutate:
        mutate(*payload)
    monkeypatch.setattr(fixtures, "adapter_input", lambda _case="S01": copy.deepcopy(payload))
    return fixtures.index_dev(storage)


def test_inline_closed_list_retains_original_blocks_once_and_proves_both_conditions(storage, monkeypatch):
    result = indexed(storage, monkeypatch)
    found = fixtures.contexts(result)
    assert len(found) == 2
    source = next(source for source in result["sources"] if any(block.get("list_context") for block in source["blocks"]))
    assert len(source["blocks"]) == len({block["id"] for block in source["blocks"]}) == 4
    for context in found.values():
        assert context["heading"]["text"] == "· Supply range:"
        assert context["item_count"] == 2 and context["complete"]
        fixtures.assert_exact_dependencies(result, context)
    cat = StructuredAnswerBuilder(storage[1], result["snapshot"], "What are the two supply voltage ranges?",
                                  enforce_contract=True).catalogue([{**source, "source_id": "S001"}], "question")
    assessment = cat.assess()
    assert assessment["status"] == "covered"
    assert {tuple(fact["values"]) for fact in assessment["matched_relations"] if fact["property"] == "supply"} == {
        ("2.4", "3.6"), ("2.7", "3.3")}
    assert all(fact["condition"] for fact in assessment["matched_relations"] if fact["property"] == "supply")


@pytest.mark.parametrize("damage", ["no_list_label", "no_boundary", "no_marker", "minus_without_separator", "ambiguous_heading"])
def test_inline_relation_requires_unambiguous_written_list(storage, monkeypatch, damage):
    def mutate(document, page, observed):
        if damage == "no_list_label":
            for block in document["texts"]:
                block["label"] = "text"
        elif damage == "no_boundary":
            document["texts"].pop()
        elif damage == "ambiguous_heading":
            duplicate = copy.deepcopy(document["texts"][0])
            duplicate.update(self_ref="#/texts/AMB", text="· Input range:", orig="· Input range:")
            document["texts"].append(duplicate)
        else:
            block = document["texts"][0 if damage == "no_marker" else 1]
            block["orig"] = block["text"] = "Supply range:" if damage == "no_marker" else "−2.4 V to 3.6 V at 25 °C"
        document["body"]["children"] = [{"$ref": value["self_ref"]} for value in document["texts"]]
    result = indexed(storage, monkeypatch, mutate)
    assert not fixtures.contexts(result)


def test_inline_scope_cannot_import_parent_from_an_unselected_block(storage, monkeypatch):
    result = indexed(storage, monkeypatch)
    assert len(fixtures.contexts(result)) == 2
    narrowed = copy.copy(result["snapshot"])
    narrowed.block_ids = [result["names"]["V1"]["id"]]
    for chunk in result["chunks"]:
        source = result["resolver"].source_for_chunk(chunk, narrowed)
        if source:
            assert source["text"] == result["names"]["V1"]["text"]
            assert not source["blocks"][0].get("list_context")


def test_inline_unresolved_gap_never_becomes_a_complete_list():
    from services.ingestion.pdf_structure import explicit_list_groups

    document, preflight, _ = inline_input()
    pages, _ = fixtures.document_to_pages(document, [preflight], "version", "revision", "structured")
    page = pages[0]
    # Unresolved regions belong to the canonical extraction, not preflight
    # geometry (which the adapter correctly resets before real OCR evidence).
    page["unresolved_regions"] = [{"bbox": [50, 671, 280, 679], "reason": "OCR_NUMERIC_AMBIGUITY"}]
    groups = explicit_list_groups(page)
    assert len(groups) == 1 and len(groups[0]["items"]) == 2
    assert not groups[0]["complete"] and all(item["verified"] for item in groups[0]["items"])
