"""Fragmented condition bands through actual SQLite, scope and publication.

The fixture intercepts only the fabrication of synthetic extraction input. It
uses real indexing, geometric reconstruction and API checks, with the existing
embedding/vector/token doubles; no native PDF/OCR or model fidelity is claimed.
"""

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_i5_general_condition_publication import CONDITIONS, ROWS

from services.api.evidence_selection import table_bundle
from services.api.schemas import Scope
from services.api.structured_answer import StructuredAnswerBuilder
from services.api.table_conditions import table_conditions_bundle
from services.ingestion.table_geometry import (
    build_table_general_conditions,
    table_general_condition_fragments,
)

DECLARATION_WORDS = ("(", "FS", "=", "full", "scale", "of", "the", "sensor", "output", "span", ")")
QUESTION = "What is the pressure range at TA = 18 °C with its general conditions?"


def fragmented_workspace(storage, monkeypatch, *, split_point=False):
    indexer = storage[3]
    actual_index = indexer.index
    captured = {}

    async def index_fragmented_input(job_id, extraction):
        page = extraction["pages"][0]
        table = next(item for item in page["blocks"] if item["type"] == "table")
        heading = next(item for item in page["blocks"] if item["id"] == "general-heading")
        original = next(item for item in page["blocks"] if item["id"] == "general-conditions")
        fragments = []

        def fragment(identity, text, left, top):
            width = max(4, len(text) * 3)
            item = {**copy.deepcopy(original), "id": identity, "text": text, "raw_text": text,
                    "bbox": [left, page["height"] - top - 8, left + width, page["height"] - top],
                    "source_text_hash": hashlib.sha256(text.encode()).hexdigest()}
            fragments.append(item)
            return left + width + 2

        left = heading["bbox"][2] + 2
        for index, token in enumerate(DECLARATION_WORDS):
            left = fragment(f"definition-{index:02d}", token, left, 8)
        if split_point:
            left = 20
            for index, token in enumerate(CONDITIONS.split()):
                left = fragment(f"condition-{index:02d}", token, left, 22)
        else:
            fragment("condition-point", CONDITIONS, 20, 22)
        page["blocks"] = [table, heading, *fragments]
        table["metadata"]["table_general_conditions"] = build_table_general_conditions(
            table, page["blocks"], page, source_sha256=extraction["sha256"])
        captured.update(originals={item["id"]: copy.deepcopy(item) for item in [heading, *fragments]},
                        annotation=copy.deepcopy(table["metadata"]["table_general_conditions"]))
        return await actual_index(job_id, extraction)

    monkeypatch.setattr(indexer, "index", index_fragmented_input)
    search, snapshot, source, _ = witnessed_sparse_table(
        storage, ROWS, general_conditions=" ".join(DECLARATION_WORDS) + " " + CONDITIONS)
    source["source_id"] = "S001"
    return SimpleNamespace(db=search.db, resolver=search.resolver, snapshot=snapshot, source=source, **captured)


def bundle(workspace, snapshot=None):
    parent = workspace.db.one("SELECT * FROM blocks WHERE generation_id=? AND id='sparse-table'",
                              (workspace.source["generation_id"],))
    return table_conditions_bundle(workspace.db, snapshot or workspace.snapshot, workspace.source,
                                   workspace.source["blocks"][0], parent)


def catalogue(workspace, snapshot=None):
    snapshot = snapshot or workspace.snapshot
    source, warnings = table_bundle(workspace.db, snapshot, workspace.source, question=QUESTION)
    result = StructuredAnswerBuilder(workspace.db, snapshot, QUESTION, enforce_contract=True).catalogue([source], "question")
    return result, warnings


def selected_scope(workspace, *, omit=None, clip=None):
    rows = workspace.db.rows("SELECT * FROM blocks WHERE generation_id=?", (workspace.source["generation_id"],))
    spans = [{"extractionRevisionId": row["extraction_revision_id"], "blockId": row["id"],
              "blockTextSha256": row["source_text_hash"], "offsetUnit": "unicode_code_point",
              "startOffset": 1 if row["id"] == clip else 0, "endOffset": len(row["text"])}
             for row in rows if row["id"] != omit]
    return workspace.resolver.resolve(Scope(kind="selection", versionId=workspace.source["version_id"], spans=spans))


def test_fragmented_band_keeps_thirteen_original_parents_and_complete_public_proof(storage, monkeypatch):
    workspace = fragmented_workspace(storage, monkeypatch)
    fragments, annotation, warnings = bundle(workspace)
    assert not warnings and annotation["state"] == "supported"
    assert annotation["schema_version"] == "table-general-conditions-v2" and len(annotation["pieces"]) == 2
    assert len(fragments) == 13 and len(table_general_condition_fragments(annotation)) == 13
    assert {item["id"] for item in fragments} == set(workspace.originals)
    for item in fragments:
        original = workspace.originals[item["id"]]
        assert item["text"] == original["text"][item["start_offset"]:item["end_offset"]]
        assert item["source_text_hash"] == original["source_text_hash"]
        assert item["extraction_revision_id"] == original["extraction_revision_id"]

    cat, warnings = catalogue(workspace)
    result = render(cat)
    assert not warnings and result["answer_contract"]["status"] == "covered"
    assert CONDITIONS in result["text"] and result["citation_spans"]
    displayed = set(result["answer_contract"]["rendered_reference_ids"])
    for identity, original in workspace.originals.items():
        matches = [ref for ref in cat.references if ref["id"] in displayed and any(
            segment["block_id"] == identity and segment["source_text_hash"] == original["source_text_hash"]
            and segment["start_offset"] == 0 and segment["end_offset"] == len(original["text"])
            for segment in ref.get("segments", []))]
        assert matches, identity
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("gate", ["missing", "clipped"])
def test_one_missing_or_clipped_fragment_cannot_expand_the_authorized_scope(storage, monkeypatch, gate):
    workspace = fragmented_workspace(storage, monkeypatch)
    snapshot = selected_scope(workspace, **{"omit" if gate == "missing" else "clip": "definition-04"})
    fragments, annotation, warnings = bundle(workspace, snapshot)
    assert fragments == [] and annotation["state"] == "unavailable" and warnings
    cat, _ = catalogue(workspace, snapshot)
    result = render(cat)
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "1.8" not in result["text"]


@pytest.mark.parametrize("alteration", ["hash", "order"])
def test_a_forged_fragment_witness_is_reconstructed_before_flattening(storage, monkeypatch, alteration):
    workspace = fragmented_workspace(storage, monkeypatch)
    row = workspace.db.one("SELECT metadata_json FROM blocks WHERE generation_id=? AND id='sparse-table'",
                           (workspace.source["generation_id"],))
    metadata = json.loads(row["metadata_json"])
    line = metadata["metadata"]["table_general_conditions"]["pieces"][0]
    if alteration == "hash":
        line["fragments"][1]["source_text_hash"] = "0" * 64
    else:
        line["fragments"][1:3] = reversed(line["fragments"][1:3])
    workspace.db.execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id='sparse-table'",
                         (json.dumps(metadata), workspace.source["generation_id"]))
    fragments, annotation, warnings = bundle(workspace)
    assert fragments == [] and annotation["state"] == "unavailable" and warnings
    cat, _ = catalogue(workspace)
    assert not render(cat)["answer_contract"]["matched_relations"]


def test_one_uncorroborated_fragment_still_blocks_the_table_value(storage, monkeypatch):
    workspace = fragmented_workspace(storage, monkeypatch)
    row = workspace.db.one("SELECT metadata_json FROM blocks WHERE generation_id=? AND id='definition-04'",
                           (workspace.source["generation_id"],))
    metadata = json.loads(row["metadata_json"])
    metadata["metadata"]["extraction_method"] = "unknown"
    workspace.db.execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id='definition-04'",
                         (json.dumps(metadata), workspace.source["generation_id"]))
    fragments, annotation, _ = bundle(workspace)
    assert len(fragments) == 13 and annotation["state"] == "supported"
    cat, _ = catalogue(workspace)
    result = render(cat)
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "1.8" not in result["text"]


def test_geometric_grouping_does_not_reconstruct_a_point_split_between_blocks(storage, monkeypatch):
    workspace = fragmented_workspace(storage, monkeypatch, split_point=True)
    assert bundle(workspace)[1]["state"] == "supported"
    cat, _ = catalogue(workspace)
    result = render(cat)
    assert result["answer_contract"]["status"] == "partial"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
