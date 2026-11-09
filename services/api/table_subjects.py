"""A bounded, explicit page-header subject authority for verified PDF evidence.

The complete page must already be authorized and its unique printed header
already retained. No subject is read from a filename, a question, or an inferred
section. Table rows and complete prose keep separate admission gates.
"""

from __future__ import annotations

import hashlib
import json

from services.ingestion.errors import IngestionError
from services.ingestion.geometry import normalize_box, pdf_box_to_docling

from .answer_contract import SUBJECT, _source_identifiers, reference_span_quality
from .source_geometry import source_page_geometry
from .table_conditions import MAX_PAGE_BLOCKS, MAX_PAGE_CHARS, MAX_PAGE_METADATA_CHARS


def _display_rectangle(raw, page):
    """Use the inverse checked PDF/display transform, including rotation/crop."""
    box = normalize_box(raw)
    frame = normalize_box(page.get("effective_box") or page["crop_box"])
    if (box[0] >= box[2] or box[1] >= box[3] or frame[0] >= frame[2] or frame[1] >= frame[3]
            or box[0] < frame[0] or box[1] < frame[1] or box[2] > frame[2] or box[3] > frame[3]):
        return None
    width, height = frame[2] - frame[0], frame[3] - frame[1]
    size = (height, width) if page["rotation"] in {90, 270} else (width, height)
    mapped = pdf_box_to_docling(box, size, page)
    return [mapped["l"], mapped["t"], mapped["r"], mapped["b"]]


def _page_subject(db, snapshot, source, target_id, parent, references, *, prose=False):
    """Reconstruct a page-header witness solely from pinned DB rows.

    A narrow block/character scope cannot establish page-wide uniqueness. The
    same bounded page inspection as table conditions is used; unavailable or
    malformed evidence supplies no subject. References here are the builder's
    already revalidated catalogue, not retrieval hints.
    """
    try:
        generation_id, page_index = source["generation_id"], parent["page_index"]
        if (source.get("source_format") != "pdf" or generation_id not in snapshot.generations
                or source["version_id"] != snapshot.versions.get(generation_id)
                or source["document_id"] != snapshot.documents.get(generation_id)
                or snapshot.block_ids is not None or snapshot.spans or snapshot.cell_ranges is not None
                or type(page_index) is not int
                or snapshot.page_indices is not None and page_index not in snapshot.page_indices):
            return None
        generation = db.one(
            "SELECT g.version_id,g.extraction_revision_id,g.state,v.document_id,v.sha256,v.format "
            "FROM index_generations g JOIN document_versions v ON v.id=g.version_id WHERE g.id=?",
            (generation_id,))
        if (not generation or generation["state"] not in {"ready", "ready_partial"} or generation["format"] != "pdf"
                or generation["version_id"] != source["version_id"]
                or generation["document_id"] != source["document_id"]
                or generation["sha256"] != source.get("source_file_sha256")
                or generation["extraction_revision_id"] != parent["extraction_revision_id"]
                or generation["extraction_revision_id"] != source["extraction_revision_id"]):
            return None
        sizes = db.rows("SELECT length(text) text_size,length(metadata_json) metadata_size FROM blocks "
                        "WHERE generation_id=? AND page_index=? LIMIT ?", (generation_id, page_index, MAX_PAGE_BLOCKS + 1))
        if (not sizes or len(sizes) > MAX_PAGE_BLOCKS
                or sum(item["text_size"] for item in sizes) > MAX_PAGE_CHARS
                or sum(item["metadata_size"] for item in sizes) > MAX_PAGE_METADATA_CHARS):
            return None
        page_row = db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=?",
                          (generation_id, page_index))
        if not page_row:
            return None
        page = json.loads(page_row["geometry_json"])
        if (not isinstance(page, dict) or page.get("page_index") != page_index
                or page.get("source_sha256") != generation["sha256"]
                or type(page.get("rotation")) is not int or page["rotation"] not in {0, 90, 180, 270}):
            return None
        stored_table = json.loads(parent["metadata_json"])
        extraction_version = stored_table.get("version_id")
        if not isinstance(extraction_version, str) or not extraction_version:
            return None
        blocks = []
        for row in db.rows("SELECT * FROM blocks WHERE generation_id=? AND page_index=? LIMIT ?",
                           (generation_id, page_index, MAX_PAGE_BLOCKS + 1)):
            metadata = json.loads(row["metadata_json"])
            if (not isinstance(metadata, dict) or not isinstance(metadata.get("metadata", {}), dict)
                    or row["extraction_revision_id"] != generation["extraction_revision_id"]
                    or metadata.get("extraction_revision_id") != row["extraction_revision_id"]
                    or metadata.get("version_id") != extraction_version
                    or metadata.get("page_index") != page_index
                    or hashlib.sha256(row["text"].encode()).hexdigest() != row["source_text_hash"]):
                return None
            blocks.append({**dict(row), "label": metadata.get("metadata", {}).get("label"),
                           "has_table_data": "table_data" in metadata.get("metadata", {}),
                           "bbox": json.loads(row["bbox_json"] or "null")})
        target = next((item for item in blocks if item["id"] == target_id), None)
        headers = [item for item in blocks if item["label"] == "page_header"]
        if target is None or target["source_text_hash"] != parent["source_text_hash"]:
            return None
        if prose:
            if (target["kind"] not in {"text", "list_item"} or target["label"] not in {"text", "list_item"}
                    or target["has_table_data"] or source.get("table_context") or source.get("table_quality")
                    or not source.get("source_span_complete") or source.get("source_parent_start") != 0
                    or source.get("text") != target["text"]
                    or source.get("locators") != [{"page_index": page_index}]
                    or not any(segment["block_id"] == target_id and segment["source_text_hash"] == target["source_text_hash"]
                               and segment["start_offset"] == 0 and segment["end_offset"] == len(target["text"])
                               for segment in source.get("segments", []))):
                return None
            quality = reference_span_quality(source, 0, len(source["text"]))
            if quality is None or quality["state"] not in {"native", "corroborated"}:
                return None
            # Written local/list subjects keep their existing authority. The
            # page header cannot override or supplement a competing identity.
            if (_source_identifiers(target["text"])
                    or _source_identifiers((source.get("list_context") or {}).get("heading", {}).get("text", ""))):
                return None
        elif target["kind"] != "table":
            return None
        if prose:
            authority = _prose_authority(blocks, headers)
            if authority is None:
                return None
            header, subject, identity_start, identity_end, authority_kind = authority
        else:
            if len(headers) != 1:
                return None
            header = headers[0]
            subject = header["text"].strip()
            if (header["kind"] not in {"text", "heading", "page_header"} or not SUBJECT.fullmatch(subject)
                    or _source_identifiers(subject) != {subject.casefold()}):
                return None
            identity_start, identity_end, authority_kind = 0, len(header["text"]), "page_header"
        header_box, target_box = _display_rectangle(header["bbox"], page), _display_rectangle(target["bbox"], page)
        if header_box is None or target_box is None or header_box[3] >= target_box[1]:
            return None
        if prose and _prose_identity_conflict(target["text"], subject):
            return None
        for block in blocks:
            if block["id"] == header["id"] or block["label"] in {"page_header", "page_footer"} or not block["text"].strip():
                continue
            if block["kind"] not in {"text", "heading", "section_header", "caption", "table", "list_item"}:
                continue
            box = _display_rectangle(block["bbox"], page)
            if box is None or header_box[3] >= box[1]:
                return None
            if (block["kind"] in {"heading", "section_header"} or block["label"] == "section_header") and box[3] <= target_box[1]:
                identifiers = _source_identifiers(block["text"])
                if (identifiers and identifiers != {subject.casefold()}
                        or prose and _prose_identity_conflict(block["text"], subject)):
                    return None
            if prose and block["id"] != target_id:
                horizontal_overlap = max(box[0], target_box[0]) < min(box[2], target_box[2])
                if horizontal_overlap and box[1] < target_box[3]:
                    # This is only a conflict guard. A preceding paragraph,
                    # its proximity or its section_id never supplies a subject.
                    if _prose_identity_conflict(block["text"], subject):
                        return None
                    if (block["kind"] == "table" or block["has_table_data"]) and target_box[1] < box[3]:
                        return None  # no unverified table line through prose
        candidates = [item for item in references if item["kind"] == "excerpt"
                      and item.get("source_format") == "pdf" and item.get("source_span_complete")
                      and item["generation_id"] == generation_id and item["version_id"] == source["version_id"]
                      and item["document_id"] == source["document_id"]
                      and item.get("source_file_sha256") == generation["sha256"]
                      and item["extraction_revision_id"] == generation["extraction_revision_id"]
                      and item.get("source_parent_start") == 0 and item["text"] == header["text"]
                      and item.get("locators") == [{"page_index": page_index}]
                      and any(segment["block_id"] == header["id"] and segment["source_text_hash"] == header["source_text_hash"]
                              and segment["start_offset"] == 0 and segment["end_offset"] == len(header["text"])
                              for segment in item.get("segments", []))]
        candidates.sort(key=lambda item: item["id"])
        if not candidates:
            return None
        retained = candidates[0]
        quality = reference_span_quality(retained, 0, len(retained["text"]))
        if quality is None or quality["state"] not in {"native", "corroborated"}:
            return None
        return {"schema_version": "prose-page-subject-v1" if prose else "table-page-subject-v1", "state": "supported",
                "support_scope": "unique_printed_title_above_body" if authority_kind == "printed_title" else "unique_page_header_above_body",
                **({"authority_kind": authority_kind} if prose else {}), "subject": subject,
                "document_id": source["document_id"], "version_id": source["version_id"],
                "generation_id": generation_id, "extraction_version_id": extraction_version,
                "extraction_revision_id": generation["extraction_revision_id"], "source_sha256": generation["sha256"],
                "page_index": page_index, "page": source_page_geometry(page_row["geometry_json"]),
                "inspected_page_blocks": len(blocks),
                "prose" if prose else "table": {"block_id": target_id, "source_text_hash": target["source_text_hash"],
                                                "bbox": target["bbox"], "display_bbox": target_box},
                "header": {"block_id": header["id"], "reference_id": retained["id"], "text": header["text"],
                           "source_text_hash": header["source_text_hash"], "start_offset": identity_start, "end_offset": identity_end,
                           "bbox": header["bbox"], "display_bbox": header_box, "label": header["label"],
                           "source_quality": quality}}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, IngestionError):
        return None


def _prose_identity_conflict(text, subject):
    """Detect a potential rival without creating an identifier or an alias.

    Removing a registered mark here can only reject a page inheritance. The
    exact separately retained header remains its sole positive authority, and
    source text/offsets and the general identifier grammar remain unchanged.
    """
    identifiers = _source_identifiers(text) | _source_identifiers(text.replace("®", ""))
    return bool(identifiers - {subject.casefold()})


def _leading_identifier(text):
    start = len(text) - len(text.lstrip())
    match = SUBJECT.match(text, start)
    if match is None or _source_identifiers(match[0]) != {match[0].casefold()}:
        return None
    return match[0], match.start(), match.end()


def _prose_authority(blocks, headers):
    """A title can attest its printed prefix, never a composite running header.

    Geometry, complete retained text and source quality are checked by the
    caller. A composite header participates only as a potential conflict.
    """
    if len(headers) > 1:
        return None
    if headers:
        header = headers[0]
        subject = header["text"].strip()
        if (header["kind"] in {"text", "heading", "page_header"} and SUBJECT.fullmatch(subject)
                and _source_identifiers(subject) == {subject.casefold()}):
            return header, subject, 0, len(header["text"]), "page_header"
    titles = []
    for block in blocks:
        if block["kind"] not in {"heading", "section_header"} or block["label"] != "section_header":
            continue
        prefix = _leading_identifier(block["text"])
        if prefix is not None and _source_identifiers(block["text"]) == {prefix[0].casefold()}:
            titles.append((block, *prefix, "printed_title"))
    if len(titles) != 1:
        return None
    title = titles[0]
    for header in headers:
        prefix = _leading_identifier(header["text"])
        if (prefix is not None and prefix[0].casefold() != title[1].casefold()
                or prefix is None and _source_identifiers(header["text"].replace("®", ""))):
            return None
    return title


def table_page_subject(db, snapshot, source, table_id, parent, references):
    return _page_subject(db, snapshot, source, table_id, parent, references)


def prose_page_subject(db, snapshot, reference, block_id, parent, references):
    return _page_subject(db, snapshot, reference, block_id, parent, references, prose=True)


def page_subject_applies(binding, reference, context):
    """Local/ancestor subjects win; other rows never define this row's subject."""
    if binding is None or context.get("row_role") != "data":
        return False
    if _source_identifiers(reference["text"]) or any(_source_identifiers(header["text"])
            for cell in context["cells"] for header in cell["headers"]):
        return False
    parent_texts = [item["text"] for item in context["dependencies"]]
    parent_texts.append(context.get("section_heading", {}).get("text", ""))
    return all(not (identifiers := _source_identifiers(text)) or identifiers == {binding["subject"].casefold()}
               for text in parent_texts)
