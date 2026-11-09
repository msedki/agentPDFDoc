"""A replayable table witness must agree with independently loaded DB geometry.

Synthetic glyph observations and actual SQLite/index/catalogue code isolate
the authority boundary. No native engine or language model is exercised.
"""

import copy
import json

import pytest
from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import render

from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.table_geometry import validate_table_quality

QUESTION = "What is the current range?"


def table_case(storage):
    rows = [[(0, "Parameter"), (1, "Min"), (2, "Max"), (3, "Unit")],
            [(0, "Current"), (1, "1.5"), (2, "3.5"), (3, "A")]]
    search, snapshot, source, _ = witnessed_sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question=QUESTION)
    assert not warnings
    bundle["source_id"] = "S001"
    parent = search.db.one("SELECT * FROM blocks WHERE generation_id=? AND id='sparse-table'", (source["generation_id"],))
    return search.db, snapshot, bundle, parent


def build_catalogue(db, snapshot, source):
    return StructuredAnswerBuilder(db, snapshot, QUESTION, enforce_contract=True).catalogue([source], "question")


def test_registered_geometry_supports_the_original_table_and_exact_answer(storage):
    db, snapshot, source, _ = table_case(storage)
    cat = build_catalogue(db, snapshot, source)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["values"] == ["1.5", "3.5"]
    assert result["source_ids"] == ["S001"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("mutation", [
    "rotation", "crop", "effective", "page_index", "page_source", "page_missing", "page_null", "page_invalid",
    "bbox_shift", "bbox_null", "bbox_invalid",
])
def test_consistent_witness_cannot_override_missing_or_different_registered_geometry(storage, mutation):
    db, snapshot, source, parent = table_case(storage)
    generation = source["generation_id"]
    metadata = json.loads(parent["metadata_json"])
    witness = metadata["metadata"]["table_quality"]
    # The witness remains internally replayable. Only the external authority
    # changes, and the already-built retrieval hint still contains the old one.
    assert validate_table_quality(parent["text"], metadata, source_sha256=witness["source_sha256"], page_index=0)["state"] == "supported"
    if mutation.startswith("bbox"):
        box = json.loads(parent["bbox_json"])
        if mutation == "bbox_shift":
            box[0] += 1
        elif mutation == "bbox_null":
            box = None
        else:
            box = {"l": 1, "t": 2}
        db.execute("UPDATE blocks SET bbox_json=? WHERE generation_id=? AND id='sparse-table'", (json.dumps(box), generation))
        reason = "table_quality_invalid" if mutation == "bbox_invalid" else "table_quality_bbox_mismatch"
    else:
        row = db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=0", (generation,))
        page = json.loads(row["geometry_json"])
        if mutation == "rotation":
            page["rotation"] = 180
        elif mutation in {"crop", "effective"}:
            page["crop_box" if mutation == "crop" else "effective_box"][0] += 1
        elif mutation == "page_index":
            page["page_index"] = 1
        elif mutation == "page_source":
            page["source_sha256"] = "f" * 64
        elif mutation == "page_missing":
            page = {}
        elif mutation == "page_null":
            page = None
        value = "invalid-json" if mutation == "page_invalid" else json.dumps(page)
        db.execute("UPDATE pages SET geometry_json=? WHERE generation_id=? AND page_index=0", (value, generation))
        reason = "table_quality_page_frame_mismatch"
    cat = build_catalogue(db, snapshot, source)
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert any(reason in reference.get("table_quality", {}).get("reasons", []) for reference in cat.references)
    assert "1.5" not in result["text"] and "3.5" not in result["text"]
    assert cat.model_view()["reference_ids"] == []
    assert cat.references  # no loss of the internal literal evidence


def test_retrieval_geometry_cannot_replace_registered_page_or_block_geometry(storage):
    db, snapshot, source, parent = table_case(storage)
    forged = copy.deepcopy(source)
    for block in forged["blocks"]:
        block["page"] = {"page_index": 99, "crop_box": [0, 0, 1, 1], "effective_box": [0, 0, 1, 1], "rotation": 270}
        block["bbox"] = [0, 0, 1, 1]
    cat = build_catalogue(db, snapshot, forged)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["values"] == ["1.5", "3.5"]
    assert all(reference["locators"] == [{"page_index": parent["page_index"]}] for reference in cat.references)
    assert result["support_validation"]["status"] == "passed"
