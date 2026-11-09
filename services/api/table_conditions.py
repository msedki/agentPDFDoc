"""Recover a bounded table-condition bundle from immutable, scoped DB records.

The extraction annotation is a hint. Geometry, exact text, identities and the
annotation are reconstructed before any piece can enter the counted context.
"""

from __future__ import annotations

import hashlib
import json

from services.ingestion.table_geometry import (
    table_general_condition_fragments,
    validate_table_general_conditions,
)

from .scope import block_extraction_method
from .source_geometry import source_page_geometry

MAX_PAGE_BLOCKS = 256
MAX_PAGE_CHARS = 200_000
MAX_PAGE_METADATA_CHARS = 2_000_000


def _limited(block, reason):
    annotation = {"schema_version": "table-general-conditions-v1", "state": "unavailable",
                  "table_block_id": block["id"], "pieces": [], "reasons": [reason]}
    warning = {"code": "table_general_conditions_unavailable", "block_id": block["id"],
               "reason": reason,
               "message": "Les conditions générales liées au tableau ne sont pas entièrement vérifiables dans le périmètre autorisé."}
    return [], annotation, [warning]


def table_conditions_bundle(db, snapshot, source, block, parent):
    """Return (exact source blocks, reconstructed annotation, warnings).

    No nearby heading is invented. Missing old annotations return None, which
    means no association is established, not that the document has no conditions.
    A declared but unreconstructible association stays explicitly unavailable.
    """
    try:
        metadata = json.loads(parent["metadata_json"])
        declared = metadata.get("metadata", {}).get("table_general_conditions")
        if declared is None:
            return [], None, []
        if not isinstance(declared, dict):
            return _limited(block, "invalid_condition_witness")
        generation_id, page_index = source["generation_id"], block.get("page_index")
        if (generation_id not in snapshot.generations
                or source["version_id"] != snapshot.versions.get(generation_id)
                or source["document_id"] != snapshot.documents.get(generation_id)
                or type(page_index) is not int
                or snapshot.page_indices is not None and page_index not in snapshot.page_indices
                or snapshot.block_ids is not None and block["id"] not in snapshot.block_ids):
            return _limited(block, "condition_scope_unavailable")
        generation = db.one(
            "SELECT g.version_id,g.extraction_revision_id,g.state,v.document_id,v.sha256 "
            "FROM index_generations g JOIN document_versions v ON v.id=g.version_id WHERE g.id=?",
            (generation_id,))
        if (not generation or generation["state"] not in {"ready", "ready_partial"}
                or generation["version_id"] != source["version_id"]
                or generation["document_id"] != source["document_id"]
                or generation["extraction_revision_id"] != parent["extraction_revision_id"]
                or generation["extraction_revision_id"] != source.get("extraction_revision_id")
                or generation["extraction_revision_id"] != block.get("extraction_revision_id")):
            return _limited(block, "condition_revision_unavailable")
        clause, parameters = "generation_id=? AND page_index=?", [generation_id, page_index]
        allowed = set(snapshot.block_ids) if snapshot.block_ids is not None else None
        if snapshot.spans:
            selected = {span["blockId"] for span in snapshot.spans}
            allowed = selected if allowed is None else allowed & selected
        if allowed is not None:
            if not allowed or len(allowed) > MAX_PAGE_BLOCKS:
                return _limited(block, "condition_scope_limit")
            clause += " AND id IN (" + ",".join("?" for _ in allowed) + ")"
            parameters.extend(sorted(allowed))
        sizes = db.rows("SELECT length(text) text_size,length(metadata_json) metadata_size FROM blocks WHERE "
                        + clause + " LIMIT ?", (*parameters, MAX_PAGE_BLOCKS + 1))
        if (not sizes or len(sizes) > MAX_PAGE_BLOCKS
                or sum(row["text_size"] for row in sizes) > MAX_PAGE_CHARS
                or sum(row["metadata_size"] for row in sizes) > MAX_PAGE_METADATA_CHARS):
            return _limited(block, "condition_inspection_limit")
        page_row = db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=?",
                          (generation_id, page_index))
        if not page_row:
            return _limited(block, "condition_page_unavailable")
        page = json.loads(page_row["geometry_json"])
        if (not isinstance(page, dict) or page.get("page_index") != page_index
                or page.get("source_sha256", generation["sha256"]) != generation["sha256"]):
            return _limited(block, "condition_geometry_unavailable")
        blocks, by_id = [], {}
        for row in db.rows("SELECT * FROM blocks WHERE " + clause + " LIMIT ?", (*parameters, MAX_PAGE_BLOCKS + 1)):
            if (row["extraction_revision_id"] != generation["extraction_revision_id"]
                    or hashlib.sha256(row["text"].encode()).hexdigest() != row["source_text_hash"]):
                return _limited(block, "condition_text_integrity_failure")
            stored = json.loads(row["metadata_json"])
            if not isinstance(stored, dict):
                return _limited(block, "invalid_condition_metadata")
            item = {**stored, "id": row["id"], "page_index": row["page_index"], "type": row["kind"],
                    "text": row["text"], "raw_text": row["text"], "bbox": json.loads(row["bbox_json"] or "null"),
                    # The extraction witness retains its original version ID.
                    # Importing those frozen bytes creates a new DB version;
                    # that public identity is separately pinned above and by
                    # the source catalogue, never copied from this witness.
                    "source_text_hash": row["source_text_hash"], "version_id": stored.get("version_id"),
                    "extraction_revision_id": row["extraction_revision_id"]}
            blocks.append(item)
            by_id[row["id"]] = (item, row)
        if block["id"] not in by_id:
            return _limited(block, "condition_table_unavailable")
        table = by_id[block["id"]][0]
        annotation = validate_table_general_conditions(table, blocks, page, source_sha256=generation["sha256"])
        if annotation.get("state") == "absent":
            return [], None, []
        if annotation.get("state") != "supported":
            return _limited(block, "condition_witness_reconstruction_failed")
        fragments = []
        source_page = source_page_geometry(page_row["geometry_json"])
        for piece in table_general_condition_fragments(annotation):
            located = by_id.get(piece["block_id"])
            if located is None:
                return _limited(block, "condition_scope_incomplete")
            item, row = located
            low, high = piece["start_offset"], piece["end_offset"]
            if (type(low) is not int or type(high) is not int or not 0 <= low < high <= len(item["text"])
                    or item["text"][low:high] != piece["text"]):
                return _limited(block, "condition_text_integrity_failure")
            if snapshot.spans and not any(
                    span["blockId"] == item["id"] and span["startOffset"] <= low < high <= span["endOffset"]
                    and span["extractionRevisionId"] == item["extraction_revision_id"]
                    and span["blockTextSha256"] == item["source_text_hash"] for span in snapshot.spans):
                return _limited(block, "condition_scope_incomplete")
            fragments.append({"id": item["id"], "block_id": item["id"], "page_index": page_index,
                              "type": item["type"], "text": piece["text"], "start_offset": low, "end_offset": high,
                              "source_text_hash": item["source_text_hash"],
                              "extraction_revision_id": item["extraction_revision_id"],
                              "bbox": item["bbox"], "precision": row["precision"], "page": source_page,
                              "extraction_method": block_extraction_method(row["metadata_json"])})
        if not fragments:
            return _limited(block, "condition_witness_empty")
        return fragments, annotation, []
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _limited(block, "invalid_condition_witness")
