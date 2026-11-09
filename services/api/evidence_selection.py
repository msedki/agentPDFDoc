"""Bounded evidence bundles assembled from authorized, revision-pinned text.

The functions in this module do not infer missing values, correct OCR or recalculate
formulas. A bundle is a selection unit: its source spans survive or leave the
context together. The original extraction and its hashes remain unchanged.
"""

import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from typing import Any

from services.ingestion.pdf_structure import (
    LIST_STRUCTURE_REVISION,
    MAX_LIST_PAGE_BLOCKS,
    MAX_LIST_PAGE_CHARS,
    explicit_list_groups,
    list_annotation,
    list_context,
)

from .errors import ApiError
from .source_geometry import source_page_geometry

REVISION = "evidence-bundles-v4"
TABLE_RELATIONS_REVISION = "verified-table-relations-v1"
MAX_TABLE_INSPECT_CHARS = 200_000
MAX_TABLE_METADATA_CHARS = 2_000_000
MAX_TABLE_CELLS = 4_096
MAX_TABLE_HEADER_DEPTH = 8
MAX_TABLE_RECOVERY_HASHES = 20_000
MAX_TABLE_RECOVERY_BYTES = 8_388_608
MAX_TABLE_RECOVERY_SECONDS = .05
MAX_TABLE_NOTE_LINKS = 64


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def deduplicate_expanded_sources(sources):
    """Drop identical expanded evidence before assigning public source IDs.

    Only retrieval bookkeeping may differ. All source text, block spans,
    version/provenance, table relations and identifier obligations participate
    in the key. Incomplete records remain separate for later validation.
    """
    bookkeeping = {"chunk_id", "parent_id", "score", "rerank_features", "rerank_revision", "parent_expanded"}
    required = {"document_id", "version_id", "generation_id", "extraction_revision_id", "text", "blocks"}
    block_fields = {"id", "start_offset", "end_offset", "source_text_hash", "extraction_revision_id", "text"}
    results, seen = [], set()
    for source in sources:
        if (not required <= source.keys() or not source["blocks"]
                or any(not block_fields <= block.keys() for block in source["blocks"])):
            results.append(source)
            continue
        key = _digest({field: value for field, value in source.items() if field not in bookkeeping})
        if key not in seen:
            seen.add(key)
            results.append(source)
    return results


def _registered_list_contexts(db, snapshot, generation_id, page_index):
    """Rebuild layout solely from bounded, authorized immutable DB records."""
    generation = db.one("SELECT g.version_id,g.extraction_revision_id,g.state,v.document_id FROM index_generations g "
                        "JOIN document_versions v ON v.id=g.version_id WHERE g.id=?", (generation_id,))
    if (not generation or generation["state"] not in {"ready", "ready_partial"}
            or generation["version_id"] != snapshot.versions.get(generation_id)
            or generation["document_id"] != snapshot.documents.get(generation_id)
            or snapshot.page_indices is not None and page_index not in snapshot.page_indices):
        return {}
    clause, parameters = "generation_id=? AND page_index=?", [generation_id, page_index]
    allowed_ids = set(snapshot.block_ids) if snapshot.block_ids is not None else None
    if snapshot.spans:
        selected_ids = {span["blockId"] for span in snapshot.spans}
        allowed_ids = selected_ids if allowed_ids is None else allowed_ids & selected_ids
    if allowed_ids is not None:
        if not allowed_ids or len(allowed_ids) > MAX_LIST_PAGE_BLOCKS:
            return {}
        clause += " AND id IN (" + ",".join("?" for _ in allowed_ids) + ")"
        parameters.extend(sorted(allowed_ids))
    sizes = db.rows("SELECT id,length(text) text_size,length(metadata_json) metadata_size FROM blocks WHERE " + clause + " LIMIT ?",
                    (*parameters, MAX_LIST_PAGE_BLOCKS + 1))
    if (not sizes or len(sizes) > MAX_LIST_PAGE_BLOCKS or sum(row["text_size"] for row in sizes) > MAX_LIST_PAGE_CHARS
            or sum(row["metadata_size"] for row in sizes) > MAX_TABLE_METADATA_CHARS):
        return {}
    page_row = db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=?", (generation_id, page_index))
    if not page_row:
        return {}
    try:
        page = json.loads(page_row["geometry_json"])
        if not isinstance(page, dict) or page.get("page_index") != page_index:
            return {}
        blocks = []
        for row in db.rows("SELECT * FROM blocks WHERE " + clause + " LIMIT ?", (*parameters, MAX_LIST_PAGE_BLOCKS + 1)):
            if (row["extraction_revision_id"] != generation["extraction_revision_id"]
                    or hashlib.sha256(row["text"].encode()).hexdigest() != row["source_text_hash"]):
                return {}
            if snapshot.spans and not any(span["blockId"] == row["id"] and span["startOffset"] == 0
                    and span["endOffset"] == len(row["text"]) and span["extractionRevisionId"] == row["extraction_revision_id"]
                    and span["blockTextSha256"] == row["source_text_hash"] for span in snapshot.spans):
                continue
            metadata = json.loads(row["metadata_json"])
            if not isinstance(metadata, dict):
                return {}
            blocks.append({**metadata, "id": row["id"], "page_index": row["page_index"], "type": row["kind"],
                           "text": row["text"], "raw_text": row["text"], "bbox": json.loads(row["bbox_json"] or "null"),
                           "source_text_hash": row["source_text_hash"], "extraction_revision_id": row["extraction_revision_id"]})
        page["blocks"] = blocks
        contexts: dict[str, dict] = {}
        owners: dict[str, list[dict]] = {}
        for group in explicit_list_groups(page):
            for item in group["items"]:
                if item["verified"] and item["block"].get("list_structure") == list_annotation(group, item):
                    owners.setdefault(item["block"]["id"], []).append(list_context(group, item))
        for block_id, candidates in owners.items():
            if len(candidates) == 1:
                contexts[block_id] = candidates[0]
        return contexts
    except (ValueError, TypeError, KeyError, AttributeError):
        return {}


def verified_list_context(db, snapshot, generation_id, item_block_id, *, _cache=None):
    """Return a reconstructed written-list relation, never a metadata assertion.

    Callers must additionally bind every returned piece to visible, exact source
    spans in their current context/catalogue. No extra source is fetched for the
    response and no relation from another revision or scope can be certified.
    """
    if generation_id not in snapshot.generations or snapshot.block_ids is not None and item_block_id not in snapshot.block_ids:
        return None
    if snapshot.spans and item_block_id not in {span["blockId"] for span in snapshot.spans}:
        return None
    row = db.one("SELECT page_index,metadata_json FROM blocks WHERE generation_id=? AND id=? AND length(metadata_json)<=?",
                 (generation_id, item_block_id, MAX_TABLE_METADATA_CHARS))
    if not row or row["page_index"] is None:
        return None
    try:
        annotation = json.loads(row["metadata_json"]).get("list_structure")
        if not isinstance(annotation, dict) or annotation.get("revision") != LIST_STRUCTURE_REVISION:
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    cache: dict = {} if _cache is None else _cache
    key = (generation_id, row["page_index"], _digest(snapshot.as_dict()))
    if key not in cache:
        cache[key] = _registered_list_contexts(db, snapshot, generation_id, row["page_index"])
    return cache[key].get(item_block_id)


def attach_list_contexts(db, snapshot, source, candidate_ids):
    """Attach only relations whose complete proof is already in this source."""
    cache: dict = {}
    for block in source["blocks"]:
        if block["id"] not in candidate_ids:
            continue
        block.pop("list_context", None)
        context = verified_list_context(db, snapshot, source["generation_id"], block["id"], _cache=cache)
        if context is None:
            continue
        pieces = [context["heading"], context["item"], *context["dependencies"]]
        if all(any(visible["id"] == piece["block_id"] and visible["source_text_hash"] == piece["source_text_hash"]
                   and visible["extraction_revision_id"] == piece["extraction_revision_id"]
                   and visible["start_offset"] <= piece["start_offset"] < piece["end_offset"] <= visible["end_offset"]
                   and visible["text"][piece["start_offset"] - visible["start_offset"]:piece["end_offset"] - visible["start_offset"]] == piece["text"]
                   for visible in source["blocks"]) for piece in pieces):
            block["list_context"] = context
    return source


def _column(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _warning(code, message, source=None):
    result = {"code": code, "message": message}
    if source is not None:
        result.update(document_id=source["document_id"], chunk_id=source.get("chunk_id"))
    return result


def small_range_bundle(db, snapshot, *, maximum_cells=64, maximum_chars=12_000):
    """Return all registered textual cells of a small range, without ranking.

    ``None`` means that the bounded exhaustive route is inapplicable. Empty cells
    with no source field are not invented. Focus narrowing is applied by the same
    projection used by lexical/dense search, before any evidence is assembled.
    """
    from .office_search import projected_cells

    scope = snapshot.scope
    if scope["kind"] != "cell_range" or not snapshot.generations:
        return None, []
    positions = (scope["rowEnd"] - scope["rowStart"] + 1) * (scope["columnEnd"] - scope["columnStart"] + 1)
    if positions > maximum_cells:
        return None, []
    cells = projected_cells(db, snapshot)
    if not cells:
        return [], []
    text = "\n".join(cell["text"] for cell in cells)
    if len(text) > maximum_chars:
        return None, [_warning("cell_range_exhaustive_budget_exceeded",
            "Le texte de la plage dépasse la limite de récupération exhaustive ; seuls des fragments classés pourront être retenus.")]
    blocks = []
    offset = 0
    for cell in cells:
        for block in cell["blocks"]:
            blocks.append({**block, "projection_start": offset + block["projection_start"],
                           "projection_end": offset + block["projection_end"]})
        offset += len(cell["text"]) + 1
    first = cells[0]
    addresses = [cell["cell_facts"][0]["address"] for cell in cells]
    rows = [block["locator"]["row_start"] for block in blocks]
    columns = [block["locator"]["column_start"] for block in blocks]
    first_address = _column(min(columns)) + str(min(rows))
    last_address = _column(max(columns)) + str(max(rows))
    locator = {**first["locator"], "row_start": min(rows), "row_end": max(rows),
               "column_start": min(columns), "column_end": max(columns),
               "cell_range": first_address if first_address == last_address else f"{first_address}:{last_address}"}
    identity = _digest([first["generation_id"], first["extraction_revision_id"], snapshot.as_dict(),
                        [(block["id"], block["start_offset"], block["end_offset"], block["source_text_hash"]) for block in blocks]])
    bundle = {**first, "text": text, "blocks": blocks, "chunk_id": "evidence-range:" + identity,
              "parent_id": "evidence-range:" + identity, "hash": hashlib.sha256(text.encode()).hexdigest(),
              "cell_facts": [fact for cell in cells for fact in cell["cell_facts"]],
              "locator": locator, "precision": "cell" if len(cells) == 1 else "range",
              "score": None, "exact_identifier": False,
              "evidence_bundle": {"id": identity, "revision": REVISION, "kind": "cell_range",
                                  "atomic": True, "cell_addresses": addresses,
                                  "available_cells_complete": True, "blank_positions_inferred": False}}
    # The range does not authorize table headers elsewhere in the sheet. Report
    # this boundary without serializing their text, names or formulas.
    warnings = [_warning("cell_range_interpretation_boundary",
        "Toutes les cellules textuelles de la plage sont récupérées. Les en-têtes, unités ou conditions extérieurs à cette plage ne sont pas ajoutés.")]
    return [bundle], warnings


def _recover_cell_texts(metadata, text):
    """Recover omitted cell text only from matching authorized UTF-8 hashes.

    Metadata supplies lengths, hashes and coordinates, never new text. The
    caller must additionally reproduce the complete table serialization exactly
    before using its row/header roles. Cost is bounded independently of text.
    """
    nested = metadata.get("metadata") if isinstance(metadata, dict) else None
    table = nested.get("table_data") if isinstance(nested, dict) else None
    cells = table.get("table_cells") if isinstance(table, dict) else None
    if not isinstance(cells, list) or not cells or len(cells) > MAX_TABLE_CELLS:
        return None, "unavailable"
    assert isinstance(metadata, dict) and isinstance(nested, dict) and isinstance(table, dict)
    wanted = defaultdict(set)
    for cell in cells:
        if not isinstance(cell, dict):
            return None, "unavailable"
        if "text" in cell:
            continue
        proof = cell.get("text_provenance")
        if not isinstance(proof, dict) or proof.get("text_export") != "publisher_text_omitted":
            return None, "unavailable"
        length, digest = proof.get("text_characters"), proof.get("text_sha256")
        if (type(length) is not int or not 0 <= length <= len(text)
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            return None, "unverified"
        wanted[length].add(digest)
    if not wanted:
        return None, "unavailable"
    # These are possible cell starts in the registered pipe/newline serializer;
    # embedded separators merely add candidates, never proof of cell boundaries.
    starts = [0, *(match.end() for match in re.finditer(r" \| |\n", text))]
    if len(starts) > MAX_TABLE_CELLS * 2:
        return None, "budget_exceeded"
    found = {}
    attempts = hashed_bytes = 0
    deadline = time.perf_counter() + MAX_TABLE_RECOVERY_SECONDS
    for length, digests in wanted.items():
        missing = set(digests)
        for start in starts:
            if start + length > len(text):
                continue
            if attempts >= MAX_TABLE_RECOVERY_HASHES or time.perf_counter() >= deadline:
                return None, "budget_exceeded"
            candidate = text[start:start + length]
            encoded = candidate.encode("utf-8")
            if hashed_bytes + len(encoded) > MAX_TABLE_RECOVERY_BYTES:
                return None, "budget_exceeded"
            attempts += 1
            hashed_bytes += len(encoded)
            digest = hashlib.sha256(encoded).hexdigest()
            if digest in missing:
                found[length, digest] = candidate
                missing.remove(digest)
            if not missing:
                break
        if missing:
            return None, "unverified"
    recovered = []
    for cell in cells:
        if "text" in cell:
            recovered.append(cell)
        else:
            proof = cell["text_provenance"]
            recovered.append({**cell, "text": found[proof["text_characters"], proof["text_sha256"]]})
    return {**metadata, "metadata": {**nested, "table_data": {**table, "table_cells": recovered}}}, "hash_verified"


def _row_records(metadata):
    """Reconstruct only the two serializers implemented by the extractors."""
    if not isinstance(metadata, dict):
        return None
    nested = metadata.get("metadata")
    table = nested.get("table_data") if isinstance(nested, dict) else None
    records = []
    if isinstance(table, dict):
        cells = table.get("table_cells")
        if not isinstance(cells, list) or not cells or len(cells) > MAX_TABLE_CELLS:
            return None
        by_row = defaultdict(list)
        for cell in cells:
            if not isinstance(cell, dict):
                return None
            row, column = cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx")
            if (type(row) is not int or type(column) is not int or min(row, column) < 0
                    or not isinstance(cell.get("text"), str)):
                return None
            by_row[row].append(cell)
        for row, row_cells in sorted(by_row.items()):
            row_cells = sorted(row_cells, key=lambda cell: (cell["start_col_offset_idx"], str(cell.get("text", ""))))
            records.append({"index": row, "text": " | ".join(str(cell.get("text", "")) for cell in row_cells),
                            "header": any(cell.get("column_header") is True for cell in row_cells),
                            "section": any(cell.get("row_section") is True for cell in row_cells),
                            "spans_to": max([row + 1] + [cell.get("end_row_offset_idx", row + 1)
                                for cell in row_cells if type(cell.get("end_row_offset_idx", row + 1)) is int]),
                            "merge_origins": [], "raw_cells": row_cells, "separator": " | ", "format": "pdf"})
    else:
        structure = metadata.get("structure", {})
        if not isinstance(structure, dict) or structure.get("serialization") != "tab_newline_v1":
            return None
        rows = structure.get("rows", [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get("row")) is not int
                or not isinstance(row.get("cells"), list) for row in rows):
            return None
        if sum(len(row["cells"]) for row in rows) > MAX_TABLE_CELLS:
            return None
        if any(not isinstance(cell, dict) or not isinstance(cell.get("text"), str)
               or cell.get("merge_origin_id") is not None and not isinstance(cell["merge_origin_id"], str)
               for row in rows for cell in row["cells"]):
            return None
        origins = {cell["id"]: row["row"] for row in rows for cell in row["cells"] if isinstance(cell.get("id"), str)}
        for row in rows:
            row_cells = row["cells"]
            records.append({"index": row["row"], "text": "\t".join(cell["text"] for cell in row_cells),
                            "header": row.get("is_header") is True, "section": False, "spans_to": row["row"] + 1,
                            "merge_origins": [origins[cell["merge_origin_id"]] for cell in row_cells
                                if cell.get("merge_origin_id") in origins],
                            "raw_cells": row_cells, "separator": "\t", "format": "docx"})
    offset = 0
    for record in records:
        record.update(start=offset, end=offset + len(record["text"]))
        cell_offset, cells = offset, []
        for cell in record.pop("raw_cells"):
            if record["format"] == "pdf":
                row_start, row_end = cell.get("start_row_offset_idx"), cell.get("end_row_offset_idx")
                column_start, column_end = cell.get("start_col_offset_idx"), cell.get("end_col_offset_idx")
            else:
                row_start, column_start = cell.get("row"), cell.get("column")
                row_span, column_span = cell.get("row_span"), cell.get("column_span")
                row_end = row_start + row_span if type(row_start) is type(row_span) is int else None
                column_end = column_start + column_span if type(column_start) is type(column_span) is int else None
            cells.append({"text": cell["text"], "start_offset": cell_offset,
                          "end_offset": cell_offset + len(cell["text"]),
                          "row_start": row_start, "row_end": row_end,
                          "column_start": column_start, "column_end": column_end,
                          "column_header": cell.get("column_header") is True if record["format"] == "pdf" else record["header"],
                          "row_header": cell.get("row_header") is True,
                          "row_section": cell.get("row_section") is True,
                          "merge_origin_id": cell.get("merge_origin_id")})
            cell_offset += len(cell["text"]) + len(record["separator"])
        record["cells"] = cells
        offset = record["end"] + 1
    _bind_columns(records)
    if _explicit_docx_header(records):
        _bind_columns(records)
    _bind_notes(records)
    return records or None


_HEADER_ROLES = {
    "min": "minimum", "minimum": "minimum", "minimale": "minimum",
    "max": "maximum", "maximum": "maximum", "maximale": "maximum",
    "typ": "typical", "typical": "typical", "typique": "typical",
    "nom": "nominal", "nominal": "nominal", "nominale": "nominal",
    "unit": "unit", "units": "unit", "unite": "unit", "unites": "unit",
    "condition": "condition", "conditions": "condition", "test conditions": "condition",
    "conditions d'essai": "condition", "conditions de test": "condition",
    "note": "note", "notes": "note", "remark": "note", "remarks": "note",
    "remarque": "note", "remarques": "note",
    "parameter": "parameter", "parameters": "parameter", "parametre": "parameter",
    "parametres": "parameter", "grandeur": "parameter",
}

# This separate family is considered only for a complete three-column PDF
# header. A literal Value column supplies a quantity, never MIN/TYP/NOM/MAX.
_SINGLE_VALUE_HEADER_ROLES = {
    "parameter": "parameter", "parameters": "parameter", "parametre": "parameter", "parametres": "parameter",
    "equipment": "parameter", "equipement": "parameter", "label": "parameter", "libelle": "parameter",
    "reference": "parameter",
    "value": "quantity", "valeur": "quantity",
    "unit": "unit", "units": "unit", "unite": "unit", "unites": "unit",
}


def _header_role(text, *, single_value=False):
    # Only explicit labels are interpreted. Numeric values and positions never
    # establish a role, particularly after sparse PDF columns are serialized.
    label = " ".join(_fold(text).replace("’", "'").strip().rstrip(".").split())
    return (_SINGLE_VALUE_HEADER_ROLES if single_value else _HEADER_ROLES).get(label)


def _explicit_docx_header(records):
    """Recognize a complete literal OOXML header without guessing a PDF grid.

    An unmarked first Word row can explicitly name its columns. Accept only a
    complete, single-row grid with unique known labels, a parameter and unit,
    and at least two numeric roles. No value from subsequent rows is consulted.
    """
    if (len(records) < 2 or records[0]["format"] != "docx" or records[0]["index"] != 0
            or any(record["header"] for record in records)
            or not all(record["column_bindings_verified"] for record in records)):
        return False
    first = records[0]
    cells = first["cells"]
    if not 4 <= len(cells) <= 16 or any(not cell["text"].strip() or cell["merge_origin_id"]
            or (cell["row_start"], cell["row_end"], cell["column_start"], cell["column_end"]) != (0, 1, index, index + 1)
            for index, cell in enumerate(cells)):
        return False
    roles = [_header_role(cell["text"]) for cell in cells]
    if (None in roles or len(roles) != len(set(roles)) or not {"parameter", "unit"} <= set(roles)
            or len(set(roles) & {"minimum", "maximum", "typical", "nominal"}) < 2
            or any(cell["column_end"] > len(cells) for record in records[1:] for cell in record["cells"])):
        return False
    first.update(header=True, header_detection="explicit_labels")
    for cell in cells:
        cell["column_header"] = True
    return True


def _bind_columns(records):
    """Attach geometric header links, pending the caller's text verification.

    Missing/overlapping coordinates disable relations for the table, while its
    literal rows remain usable. This never interprets compacted pipe ordinals.
    """
    cells = [cell for record in records for cell in record["cells"]]
    indices = [record["index"] for record in records]
    valid = (indices == sorted(set(indices)) and all(type(value) is int and 0 <= value <= MAX_TABLE_CELLS
             for cell in cells for value in (cell["row_start"], cell["row_end"], cell["column_start"], cell["column_end"]))
             and all(cell["row_start"] < cell["row_end"] and cell["column_start"] < cell["column_end"] for cell in cells)
             and all(cell["row_start"] == record["index"] for record in records for cell in record["cells"]))
    depth = 0
    for record in records:
        depth = depth + 1 if record["header"] else 0
        if depth > MAX_TABLE_HEADER_DEPTH:
            # Otherwise a legal-sized 4096-cell metadata block could generate
            # millions of ancestor dictionaries before the text budget applies.
            valid = False
            break
    if valid:
        for record in records:
            # Explicit empty OOXML merge placeholders may overlap their origin;
            # a nonempty continuation cannot silently replace that origin.
            active = sorted(_active_cells(cells, record["index"]), key=lambda cell: cell["column_start"])
            if any(left["column_end"] > right["column_start"] for left, right in zip(active, active[1:], strict=False)):
                valid = False
                break
    headers: list[dict[str, Any]] = []
    single_value_headers: set[int] = set()
    previous_header = ambiguous_roles = False
    for record in records:
        record["column_bindings_verified"] = valid
        if record["header"] and not previous_header:
            # A repeated header group replaces the preceding group's context.
            # Within one consecutive group, all geometrically enclosing
            # ancestors remain relevant (for example TA=25°C above MIN/MAX).
            headers = []
            single_value_headers.clear()
        for cell in record["cells"]:
            matches = [header for header in headers if header["row_end"] <= cell["row_start"]
                       and header["column_start"] <= cell["column_start"] < cell["column_end"] <= header["column_end"]]
            cell["headers"] = [{key: header[key] for key in ("text", "start_offset", "end_offset", "row_start", "row_end",
                                                            "column_start", "column_end")} | {
                                   "role": _header_role(header["text"], single_value=id(header) in single_value_headers)}
                               for header in matches]
            if len({header["role"] for header in cell["headers"] if header["role"] is not None}) > 1:
                ambiguous_roles = True
        if valid and record["header"]:
            current = [cell for cell in record["cells"] if cell["column_header"]]
            value_roles = [_header_role(cell["text"], single_value=True) for cell in current]
            if (record["format"] == "pdf" and len(current) == len(record["cells"]) == 3
                    and set(value_roles) == {"parameter", "quantity", "unit"}):
                single_value_headers.update(id(cell) for cell in current)
            headers.extend(current)
        previous_header = record["header"]
    if ambiguous_roles:
        for record in records:
            record["column_bindings_verified"] = False
            for cell in record["cells"]:
                cell["headers"] = []


def _active_cells(cells, row_index):
    active = [cell for cell in cells if cell["row_start"] <= row_index < cell["row_end"]]
    # Some PDF serializers retain an empty continuation in the rectangle of an
    # explicitly spanning origin. It supplies no text; the actual origin does.
    return [cell for cell in active if cell["text"] or not any(
        origin["row_start"] < cell["row_start"] and origin["column_start"] <= cell["column_start"]
        and cell["column_end"] <= origin["column_end"] for origin in active)]


_NOTE_MARKER = re.compile(
    r"\((\d{1,3})\)|\[(\d{1,3})\]|(?<!\*)(\*{1,3}|[†‡])(?![\w*])|\bnote\s+(\d{1,3})\b", re.IGNORECASE)
_NOTE_DEFINITION = re.compile(
    r"^\s*(?:(?:note|remarque)\s+(?:\((\d{1,3})\)|\[(\d{1,3})\]|(\d{1,3}))\s*[:.)-]?\s*"
    r"|(?:\((\d{1,3})\)|\[(\d{1,3})\]|(\*{1,3}|[†‡]))\s+)(?=\S)", re.IGNORECASE)


def _bind_notes(records):
    """Link explicit table-local note markers, never a guessed nearby footnote.

    A definition starts the first nonempty cell and has a textual body. Repeated
    definitions remain ambiguous: all their exact rows are retained, but none is
    chosen as authoritative. Bounds apply before constructing row dependencies.
    """
    definitions: dict[str, list[int]] = defaultdict(list)
    for record in records:
        first = next((cell["text"] for cell in record["cells"] if cell["text"].strip()), "")
        match = _NOTE_DEFINITION.match(first) if not record["header"] and not record["section"] else None
        marker = next((value for value in match.groups() if value is not None), None) if match else None
        if match and not any(char.isalpha() for char in first[match.end():]):
            marker = None
        record["note_marker"] = marker
        if marker is not None:
            definitions[marker].append(record["index"])
        record.update(note_rows=[], note_markers=[], unresolved_note_markers=[], ambiguous_note_markers=[],
                      note_scan_complete=True)
    links = 0
    for record in records:
        markers = set()
        for cell in record["cells"]:
            # Parenthesized numbers in a numeric column are not a note by
            # themselves. Their raw interpretation remains the extractor's.
            if (re.fullmatch(r"\s*\(\d{1,3}\)\s*", cell["text"])
                    and any(header["role"] in {"minimum", "maximum", "typical", "nominal"} for header in cell["headers"])):
                continue
            for match in _NOTE_MARKER.finditer(cell["text"]):
                marker = next(value for value in match.groups() if value is not None)
                if marker != record["note_marker"]:
                    markers.add(marker)
                if len(markers) > MAX_TABLE_NOTE_LINKS:
                    break
            if len(markers) > MAX_TABLE_NOTE_LINKS:
                break
        links += sum(max(1, len(definitions.get(marker, []))) for marker in markers)
        if links > MAX_TABLE_NOTE_LINKS:
            # No partial list may acquire the appearance of complete note proof.
            for item in records:
                item.update(note_rows=[], note_markers=[], unresolved_note_markers=[],
                            ambiguous_note_markers=[], note_scan_complete=False)
            return
        record["note_markers"] = sorted(markers)
        record["note_rows"] = sorted({index for marker in markers for index in definitions.get(marker, [])})
        record["unresolved_note_markers"] = sorted(marker for marker in markers if marker not in definitions)
        record["ambiguous_note_markers"] = sorted(marker for marker in markers if len(definitions.get(marker, [])) > 1)


def _table_context(records, record, block, chosen):
    """Publish relations only between exact cells and selected source rows."""
    if not record["column_bindings_verified"]:
        return None
    index = record["index"]
    cells = _active_cells([cell for row in records for cell in row["cells"]], index)
    dependencies = {header["row_start"]: "header" for cell in cells for header in cell["headers"]}
    dependencies.update({cell["row_start"]: "row_span" for cell in cells if cell["row_start"] != index})
    shared = record.get("shared_conditions", [])
    for condition in shared:
        dependencies.setdefault(condition["row_index"], "shared_condition_origin")
    # A section row starts a sibling group; the preceding section is not its
    # parent. Data rows still require their own nearest explicit section.
    section = (None if record["section"] else
               next((row["index"] for row in reversed(records) if row["section"] and row["index"] < index), None))
    if section is not None:
        dependencies[section] = "row_section"
    # Notes on a relied-upon header, merged origin or note are also required.
    # Each row is visited once, including cycles such as (1) -> (2) -> (1).
    by_index = {row["index"]: row for row in records}
    relevant = {index, *dependencies}
    pending = list(relevant)
    while pending:
        current = pending.pop()
        for note in by_index[current].get("note_rows", []):
            if note != index:
                dependencies[note] = "note"
            if note not in relevant:
                relevant.add(note)
                pending.append(note)
    note_context = [by_index[row] for row in relevant]
    if not set(dependencies) <= {row["index"] for row in chosen}:
        return None
    return {"revision": TABLE_RELATIONS_REVISION, "table_block_id": block["id"],
            "source_text_hash": block["source_text_hash"], "extraction_revision_id": block["extraction_revision_id"],
            "serialization_verified": True, "row_index": index,
            "header_detection": "explicit_labels" if any(row.get("header_detection") == "explicit_labels" for row in records)
                                else "structural_metadata" if any(row["header"] for row in records) else "unverified",
            "row_role": "header" if record["header"] else "section" if record["section"] else "note" if record.get("note_marker") else "data",
            "note_markers": sorted({marker for row in note_context for marker in row.get("note_markers", [])}),
            "unresolved_note_markers": sorted({marker for row in note_context for marker in row.get("unresolved_note_markers", [])}),
            "ambiguous_note_markers": sorted({marker for row in note_context for marker in row.get("ambiguous_note_markers", [])}),
            "note_scan_complete": all(row.get("note_scan_complete", True) for row in note_context),
            "cells": [{key: value for key, value in cell.items() if key != "merge_origin_id"} for cell in cells],
            "dependencies": [{"kind": dependencies[row["index"]], "row_index": row["index"], "text": row["text"],
                              "start_offset": row["start"], "end_offset": row["end"]}
                             for row in chosen if row["index"] in dependencies] + shared}


def _verified_table_records(parent_text, metadata):
    records, recovery = None, "unavailable"
    if not isinstance(parent_text, str) or len(parent_text) > MAX_TABLE_INSPECT_CHARS:
        return None, recovery
    try:
        records = _row_records(metadata)
        if records is None or "\n".join(record["text"] for record in records) != parent_text:
            recovered, recovery = _recover_cell_texts(metadata, parent_text)
            records = _row_records(recovered) if recovered is not None else None
    except (ValueError, TypeError):
        records = None
    if records is not None and "\n".join(record["text"] for record in records) != parent_text:
        records = None
    if records is not None:
        _shared_table_conditions(records, metadata, parent_text)
    return records, recovery


def _shared_table_conditions(records, metadata, parent_text):
    """Carry exact candidate dependency spans; the builder replays their proof.

    These metadata hints grant neither trust nor scope. A malformed or omitted
    hint cannot create a certified table relation at the publication boundary.
    """
    nested = metadata.get("metadata", {})
    quality = nested.get("table_quality", {}) if isinstance(nested, dict) else {}
    dependencies = quality.get("dependencies", []) if isinstance(quality, dict) else []
    if not isinstance(dependencies, list) or len(dependencies) > MAX_TABLE_CELLS:
        return
    rows = {item["index"]: item for item in records}
    for dependency in dependencies:
        if not isinstance(dependency, dict) or dependency.get("kind") != "shared_condition":
            continue
        target, origin = rows.get(dependency.get("row_index")), rows.get(dependency.get("source_row"))
        if target is None or origin is None:
            continue
        cells = [cell for cell in origin["cells"] if cell["column_start"] == dependency.get("source_column")]
        if len(cells) != 1:
            continue
        cell = cells[0]
        low, high = dependency.get("start_offset"), dependency.get("end_offset")
        if type(low) is not int or type(high) is not int or not 0 <= low < high <= len(cell["text"]):
            continue
        start, end = cell["start_offset"] + low, cell["start_offset"] + high
        if parent_text[start:end] != dependency.get("text"):
            continue
        target.setdefault("shared_conditions", []).append({"kind": "shared_condition", "row_index": origin["index"],
                                                           "text": dependency["text"], "start_offset": start, "end_offset": end,
                                                           "observation_ids": dependency.get("observation_ids", [])})


def verified_table_rows(parent_text, metadata):
    """Rebuild exact rows/cells from registered parent text and its metadata.

    Used by the answer catalogue to independently check supplied relations. The
    caller must still verify revision/hash and authorize every published span;
    this helper grants no access and invents no missing source text.
    """
    return _verified_table_records(parent_text, metadata)[0]


def _parent(db, snapshot, source, block):
    generation = source["generation_id"]
    if (generation not in snapshot.generations or source["version_id"] != snapshot.versions[generation]
            or source["document_id"] != snapshot.documents[generation]
            or snapshot.page_indices is not None and block.get("page_index") not in snapshot.page_indices
            or snapshot.block_ids is not None and block["id"] not in snapshot.block_ids):
        raise ApiError("scope_leakage", "Une preuve structurée sort du périmètre autorisé.", 409)
    size = db.one("SELECT length(text) text_size,length(metadata_json) metadata_size FROM blocks WHERE generation_id=? AND id=?",
                  (generation, block["id"]))
    if not size:
        raise ApiError("source_text_integrity_failure", "Le bloc de tableau n'existe plus dans cette révision.", 409)
    if size["text_size"] > MAX_TABLE_INSPECT_CHARS or size["metadata_size"] > MAX_TABLE_METADATA_CHARS:
        return None
    row = db.one("SELECT text,source_text_hash,extraction_revision_id,metadata_json,section_id FROM blocks WHERE generation_id=? AND id=?",
                 (generation, block["id"]))
    start, end = block["start_offset"], block["end_offset"]
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(row["text"])
            or row["source_text_hash"] != block["source_text_hash"]
            or hashlib.sha256(row["text"].encode()).hexdigest() != row["source_text_hash"]
            or row["extraction_revision_id"] != block["extraction_revision_id"]
            or source["extraction_revision_id"] != row["extraction_revision_id"]
            or row["text"][start:end] != block["text"]):
        raise ApiError("source_text_integrity_failure", "Le tableau ne correspond plus au texte et à la révision de la preuve.", 409)
    return row


def _section_heading(db, snapshot, source, block, parent):
    """Recover a unique explicit section heading, never a nearby guessed title."""
    section_id = parent.get("section_id")
    if not section_id:
        return None
    rows = db.rows("""SELECT b.id,b.page_index,b.kind,b.text,b.bbox_json,b.precision,b.section_id,
                     b.source_text_hash,b.extraction_revision_id,b.metadata_json,s.title,s.block_ids_json,p.geometry_json
                     FROM sections s JOIN blocks b ON b.generation_id=s.generation_id AND b.section_id=s.id
                     LEFT JOIN pages p ON p.generation_id=b.generation_id AND p.page_index=b.page_index
                     WHERE s.generation_id=? AND s.id=? AND length(s.block_ids_json)<=?
                     AND b.kind IN ('heading','section_header') AND b.text=s.title
                     AND length(b.text)<=? AND length(b.metadata_json)<=? LIMIT 2""",
                 (source["generation_id"], section_id, MAX_TABLE_METADATA_CHARS, 2_000, MAX_TABLE_METADATA_CHARS))
    if len(rows) != 1:
        return None
    row = rows[0]
    if (row["kind"] not in {"heading", "section_header"} or row["section_id"] != section_id
            or row["text"] != row["title"] or not row["text"]
            or row["extraction_revision_id"] != parent["extraction_revision_id"]
            or hashlib.sha256(row["text"].encode()).hexdigest() != row["source_text_hash"]
            or snapshot.page_indices is not None and row["page_index"] not in snapshot.page_indices
            or snapshot.block_ids is not None and row["id"] not in snapshot.block_ids):
        return None
    try:
        ids = json.loads(row["block_ids_json"])
        if not isinstance(ids, list) or len(ids) > MAX_TABLE_CELLS or block["id"] not in ids or row["id"] not in ids:
            return None
        from .scope import block_extraction_method

        heading = {"id": row["id"], "block_id": row["id"], "page_index": row["page_index"],
                "type": row["kind"], "text": row["text"], "start_offset": 0, "end_offset": len(row["text"]),
                "source_text_hash": row["source_text_hash"], "extraction_revision_id": row["extraction_revision_id"],
                "bbox": json.loads(row["bbox_json"]) if row["bbox_json"] else None,
                "precision": row["precision"], "page": source_page_geometry(row["geometry_json"]),
                "extraction_method": block_extraction_method(row["metadata_json"])}
        if row["page_index"] is None:
            metadata = json.loads(row["metadata_json"])
            locator = metadata.get("locator")
            if not isinstance(locator, dict) or locator.get("kind") != "docx_element":
                return None
            heading.update({key: metadata[key] for key in ("locator", "structure", "bindings") if key in metadata})
        return heading
    except (ValueError, TypeError):
        return None


def table_bundle(db, snapshot, source, *, maximum_chars=12_000, question=None, required_identifiers=(), _table_cache=None):
    """Recover complete table rows with verified headers and merge origins.

    A text selection remains literal: reconstruction never widens its authorized
    spans. A table with unknown header roles is kept whole when bounded, rather
    than guessing that its first row contains column headers.
    """
    if source.get("evidence_bundle") or source.get("format") == "xlsx":
        return source, []
    if not any(block.get("type") == "table" for block in source.get("blocks", [])):
        return source, []
    if snapshot.spans or snapshot.scope["kind"] == "cell_range":
        return source, [_warning("table_context_limited_by_selection",
            "La sélection textuelle reste stricte ; les autres cellules et en-têtes du tableau ne sont pas ajoutés.", source)]
    blocks, structure, warnings = [], [], []
    table_cache = _table_cache if _table_cache is not None else {}
    for block in source["blocks"]:
        if block.get("type") != "table":
            blocks.append(block)
            continue
        parent = _parent(db, snapshot, source, block)
        if parent is None:
            return source, [_warning("table_evidence_inspection_limit",
                "La structure de ce tableau dépasse la limite de lecture locale ; le fragment original est conservé.", source)]
        key = (source["generation_id"], block["id"], parent["source_text_hash"], parent["extraction_revision_id"])
        if key not in table_cache:
            try:
                metadata = json.loads(parent["metadata_json"])
                table_cache[key] = _verified_table_records(parent["text"], metadata)
            except (ValueError, TypeError):
                table_cache[key] = None, "unavailable"
        records, recovery = table_cache[key]
        if recovery == "budget_exceeded":
            warnings.append(_warning("table_cell_recovery_budget_exceeded",
                "Le contrôle des cellules archivées atteint sa limite de calcul ; aucune attribution de ligne ou colonne n'est déduite.", source))
        if records is None or "\n".join(record["text"] for record in records) != parent["text"]:
            if len(parent["text"]) > maximum_chars:
                return source, [*warnings, _warning("table_evidence_bundle_too_large",
                    "La structure n'est pas vérifiable et le tableau entier dépasse la limite ; le fragment original reste partiel.", source)]
            # The exact registered table text remains usable when a recovered
            # export omitted cell metadata. Keep the bounded whole block without
            # manufacturing header roles, rows, values or repaired whitespace.
            blocks.append({**block, "text": parent["text"], "start_offset": 0, "end_offset": len(parent["text"])})
            structure.append({"block_id": block["id"], "source_rows": [], "header_rows": [],
                "headers_verified": False, "whole_table": True, "complete_rows": False, "serialization_verified": False})
            warnings.append(_warning("table_structure_unverified",
                "Le texte source intégral de ce tableau est conservé ; les rôles de lignes et de colonnes ne sont pas vérifiés.", source))
            continue
        hit_rows = {record["index"] for record in records
                    if max(record["start"], block["start_offset"]) < min(record["end"], block["end_offset"])}
        headers = {record["index"] for record in records if record["header"]}
        focused = _focused_rows(records, question, required_identifiers) if headers and question else None
        if focused is not None:
            hit_rows = focused
        selected = hit_rows | headers if headers else {record["index"] for record in records}
        # Each row enters the queue once; no unbounded fixed-point rescans.
        by_index = {record["index"]: record for record in records}
        pending = list(selected) if selected != set(by_index) else []
        while pending:
            selected_row = pending.pop()
            dependencies = set(by_index[selected_row]["merge_origins"])
            dependencies.update(by_index[selected_row].get("note_rows", []))
            dependencies.update(item["row_index"] for item in by_index[selected_row].get("shared_conditions", []))
            section = next((record["index"] for record in reversed(records)
                            if record["section"] and record["index"] <= selected_row), None)
            if section is not None:
                dependencies.add(section)
            dependencies.update(record["index"] for record in records
                                if record["index"] <= selected_row < record["spans_to"])
            for dependency in dependencies - selected:
                if dependency in by_index:
                    selected.add(dependency)
                    pending.append(dependency)
        chosen = [record for record in records if record["index"] in selected and record["text"]]
        unresolved_notes = sorted({marker for record in chosen for marker in record.get("unresolved_note_markers", [])})
        ambiguous_notes = sorted({marker for record in chosen for marker in record.get("ambiguous_note_markers", [])})
        if unresolved_notes:
            warnings.append({**_warning("table_note_unresolved",
                "Un renvoi de note du tableau n'est pas résolu dans les preuves autorisées ; ses conditions d'application restent inconnues.", source),
                "markers": unresolved_notes})
        if ambiguous_notes:
            warnings.append({**_warning("table_note_ambiguous",
                "Plusieurs notes portent le même renvoi dans ce tableau ; leurs textes sont conservés sans en choisir une.", source),
                "markers": ambiguous_notes})
        if not all(record.get("note_scan_complete", True) for record in chosen):
            warnings.append(_warning("table_note_verification_limit",
                "Les renvois de notes dépassent la limite de vérification ; leur couverture n'est pas établie.", source))
        if len("\n".join(record["text"] for record in chosen)) > maximum_chars:
            return source, [*warnings, _warning("table_evidence_bundle_too_large",
                "Les lignes et en-têtes liés dépassent la limite du paquet de preuves ; le fragment original reste signalé comme partiel.", source)]
        heading_key = ("section_heading", *key)
        if heading_key not in table_cache:
            table_cache[heading_key] = _section_heading(db, snapshot, source, block, parent)
        heading = table_cache[heading_key]
        if heading is not None and not any(item["id"] == heading["id"] and item["start_offset"] == 0
                                          and item["end_offset"] == heading["end_offset"]
                                          for item in [*source["blocks"], *blocks]):
            blocks.append(heading)
        from .table_conditions import table_conditions_bundle

        condition_key = ("table_general_conditions", *key)
        if condition_key not in table_cache:
            table_cache[condition_key] = table_conditions_bundle(db, snapshot, source, block, parent)
        condition_fragments, condition_annotation, condition_warnings = table_cache[condition_key]
        warnings.extend(condition_warnings)
        added_conditions = [piece for piece in condition_fragments if not any(
            item["id"] == piece["id"] and item["start_offset"] == piece["start_offset"]
            and item["end_offset"] == piece["end_offset"] for item in [*source["blocks"], *blocks])]
        condition_size = sum(len(piece["text"]) + 1 for piece in added_conditions)
        if condition_size + len("\n".join(record["text"] for record in chosen)) > maximum_chars:
            condition_annotation = {"schema_version": "table-general-conditions-v1", "state": "unavailable",
                                    "table_block_id": block["id"], "pieces": [], "reasons": ["condition_bundle_budget"]}
            warnings.append(_warning("table_general_conditions_unavailable",
                                     "Les conditions générales et les lignes nécessaires dépassent le budget du paquet de preuves.", source))
        else:
            blocks.extend(added_conditions)
        for record in chosen:
            selected_block = {**block, "text": parent["text"][record["start"]:record["end"]],
                              "start_offset": record["start"], "end_offset": record["end"]}
            relation = _table_context(records, record, block, chosen)
            if relation is not None:
                if heading is not None:
                    relation["section_heading"] = {"block_id": heading["id"], "section_id": parent["section_id"],
                        **{key: heading[key] for key in ("text", "start_offset", "end_offset", "source_text_hash",
                                                        "extraction_revision_id", "page_index")}}
                if condition_annotation is not None:
                    relation["general_conditions"] = condition_annotation
                selected_block["table_context"] = relation
            blocks.append(selected_block)
        if not all(record["column_bindings_verified"] for record in chosen):
            warnings.append(_warning("table_column_bindings_unverified",
                "Les lignes exactes sont conservées ; les liens de colonnes ou d'en-têtes sont ambigus ou dépassent les limites de vérification.", source))
        structure.append({"block_id": block["id"], "source_rows": [record["index"] for record in chosen],
                          "header_rows": sorted(headers), "headers_verified": bool(headers),
                          "header_detection": "explicit_labels" if any(record.get("header_detection") == "explicit_labels" for record in records)
                                              else "structural_metadata" if headers else "unverified",
                          "whole_table": len(chosen) == len([record for record in records if record["text"]]),
                          "complete_rows": True, "serialization_verified": True,
                          "column_bindings_verified": all(record["column_bindings_verified"] for record in chosen),
                          "cell_text_verification": recovery if recovery == "hash_verified" else "stored_text",
                          "row_selection": "question_terms" if focused is not None else "retrieved_span"})
    text = "\n".join(block["text"] for block in blocks)
    if not structure:
        return source, []
    if len(text) > maximum_chars:
        return source, [*warnings, _warning("table_evidence_bundle_too_large",
            "L'ensemble des blocs liés dépasse la limite du paquet ; le fragment original reste partiel.", source)]
    identity = _digest([source["generation_id"], [(block["id"], block["start_offset"], block["end_offset"],
                                                 block["source_text_hash"]) for block in blocks]])
    from .scope import extraction_methods

    return {**source, "text": text, "blocks": blocks, "extraction_methods": extraction_methods(blocks),
        "page_indices": sorted({block["page_index"] for block in blocks if block.get("page_index") is not None}), "evidence_bundle": {
        "id": identity, "revision": REVISION, "kind": "table_rows" if all(item["serialization_verified"] for item in structure)
        else "table_blocks", "atomic": True, "tables": structure}}, warnings


def prepare_tables(db, snapshot, sources, *, maximum_chars=12_000, maximum_candidates=48, question=None, required_identifiers=()):
    results, warnings = [], []
    table_cache: dict = {}
    for index, source in enumerate(sources):
        if index < maximum_candidates:
            source, notices = table_bundle(db, snapshot, source, maximum_chars=maximum_chars, question=question,
                                          required_identifiers=required_identifiers, _table_cache=table_cache)
            warnings.extend(notices)
        results.append(source)
    # Several chunks can lead to the same complete row/header packet.
    unique, seen = [], set()
    for source in results:
        identity = source.get("evidence_bundle", {}).get("id")
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        unique.append(source)
    return unique, warnings


def _fold(text):
    return "".join(char for char in unicodedata.normalize("NFKD", text).casefold() if not unicodedata.combining(char))


TERM_GROUPS = (
    frozenset({"voltage", "tension"}), frozenset({"current", "courant"}),
    frozenset({"supply", "alimentation"}), frozenset({"input", "entree", "entrees"}),
    frozenset({"output", "sortie", "sorties"}), frozenset({"temperature", "temperatures"}),
    frozenset({"range", "plage", "intervalle", "interval", "bornes"}),
    frozenset({"min", "minimum", "minimale", "minimal"}),
    frozenset({"max", "maximum", "maximale", "maximal"}),
    frozenset({"condition", "conditions", "essai", "essais", "test"}),
)
ROLE_GROUPS = {
    "operating": frozenset({"operating", "operation", "fonctionnement", "admissible", "admissibles", "recommended"}),
    "absolute": frozenset({"absolute", "absolue", "absolues", "absolu", "absolus"}),
    "typical": frozenset({"typical", "typique", "typiques"}),
    "test": frozenset({"test", "essai", "essais", "characterization", "caracterisation"}),
}


def _expanded_terms(question):
    from .retrieval import answer_terms

    terms = set(answer_terms(question))
    expanded = set(terms)
    for group in TERM_GROUPS:
        keys = {word[:5] for word in group}
        if terms & keys:
            expanded.update(keys)
    return expanded


def _focused_rows(records, question, required_identifiers):
    """Cover distinct requested terms and explicit roles with complete rows.

    Winner-only overlap discarded a requested range when another row mentioned
    both the range's subject and a test condition. Preserve maximum-score ties,
    then cover remaining terms without dropping tied rows arbitrarily. A role
    contributes only when a nonempty cell binds to its explicit column header.
    The bounded fallback retains the original retrieved spans.
    """
    from .retrieval import contains_identifier

    terms = _expanded_terms(question)
    role_terms = {"condition": {"condi", "essai", "test"}, "minimum": {"min", "minim"},
                  "maximum": {"max", "maxim"}, "typical": {"typ", "typic", "typiq"},
                  "nominal": {"nom", "nomin"}, "unit": {"unit", "units", "unite"}}
    requested_roles = {role for role, aliases in role_terms.items() if aliases & terms}
    ranked = []
    spanning = [cell for record in records if record.get("column_bindings_verified")
                for cell in record.get("cells", []) if cell["row_end"] > cell["row_start"] + 1]
    if sum(cell["row_end"] - cell["row_start"] - 1 for cell in spanning) > MAX_TABLE_CELLS:
        return None  # Retain original spans when inherited ranking work is too large.
    inherited_by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for cell in spanning:
        for row_index in range(cell["row_start"] + 1, cell["row_end"]):
            inherited_by_row[row_index].append(cell)
    for record in records:
        if record["header"] or record["section"] or record.get("note_marker") or not record["text"]:
            continue
        inherited = [cell["text"] for cell in _active_cells([*inherited_by_row[record["index"]], *record.get("cells", [])], record["index"])
                     if cell["row_start"] != record["index"]]
        # Ranking sees literal rowspan context; the row's stored/public text
        # is never rewritten or independently attached to an unproved header.
        words = set(re.findall(r"\w+", _fold(" ".join([record["text"], *inherited]))))
        matches = terms & {word[:5] for word in words if len(word) >= 3}
        roles = {header["role"] for cell in record.get("cells", []) if cell["text"].strip()
                 for header in cell.get("headers", [])} & requested_roles
        # Synonyms form one obligation rather than awarding three points for a
        # single TEST CONDITIONS label.
        matches.update("role:" + role for role in roles)
        ranked.append((matches, record["index"]))
    best = max((len(matches) for matches, _ in ranked), default=0)
    if not best:
        return None
    selected = {index for matches, index in ranked if len(matches) == best}
    # A generic one-word query is not an authorization to discard an arbitrary
    # tail of equally relevant rows. Keep original span selection in that case.
    if len(selected) > 12:
        return None
    covered = set().union(*(matches for matches, index in ranked if index in selected))
    while True:
        remaining = [(len(matches - covered), len(matches), index, matches) for matches, index in ranked
                     if index not in selected and matches - covered]
        if not remaining:
            break
        gain, score = max((gain, score) for gain, score, _, _ in remaining)
        tied = [(index, matches) for new, total, index, matches in remaining if (new, total) == (gain, score)]
        if len(selected) + len(tied) > 12:
            return None
        selected.update(index for index, _ in tied)
        covered.update(*(matches for _, matches in tied))
    selected.update(record["index"] for record in records
                    if any(contains_identifier(record["text"], code) for code in required_identifiers))
    return selected if len(selected) <= 12 else None


def structural_rerank(question, sources, *, maximum_candidates=48):
    """Stable, transparent lexical/structural refinement of the existing pool.

    Feature counts are ranking signals, never calibrated confidence or an answer
    validator. No new document is searched and no additional model is loaded.
    """
    expanded = _expanded_terms(question)
    question_words = set(re.findall(r"\w+", _fold(question)))
    roles = {role for role, words in ROLE_GROUPS.items() if question_words & words}
    ranked = []
    for position, source in enumerate(sources[:maximum_candidates]):
        words = set(re.findall(r"\w+", _fold(source["text"])))
        matched = sorted(expanded & {word[:5] for word in words if len(word) >= 3})
        source_roles = {role for role, vocabulary in ROLE_GROUPS.items() if words & vocabulary}
        matched_roles = roles & source_roles
        # Test/typical conditions alone must not outrank an operating/absolute
        # limit solely because they contain the same component and units.
        role_conflict = bool(roles & {"operating", "absolute"} and source_roles & {"test", "typical"}
                             and not matched_roles)
        bundle = bool(source.get("evidence_bundle"))
        features = {"matched_terms": matched, "matched_roles": sorted(matched_roles),
                    "role_mismatch": role_conflict, "structured_bundle": bundle, "original_rank": position + 1}
        item = {**source, "rerank_features": features, "rerank_revision": "lexical-structure-v2"}
        # SearchService reserves one actual occurrence for each identifier. A
        # repeated product mention must not monopolize all slots at the expense
        # of the requested facts, which often omit that name inside a table.
        key = (role_conflict, -len(matched_roles), -len(matched), not bundle,
               not source.get("exact_identifier", False), position)
        ranked.append((key, item))
    return [item for _, item in sorted(ranked, key=lambda entry: entry[0])] + list(sources[maximum_candidates:])


def bundle_context_metrics(sources, retained):
    available = {source["evidence_bundle"]["id"]: source["evidence_bundle"]
                 for source in sources if source.get("evidence_bundle")}
    if not available:
        return None
    kept = {source["evidence_bundle"]["id"] for source in retained if source.get("evidence_bundle")}
    excluded = [identity for identity in available if identity not in kept]
    cells = sum(len(bundle.get("cell_addresses", [])) for bundle in available.values())
    retained_cells = sum(len(bundle.get("cell_addresses", [])) for identity, bundle in available.items() if identity in kept)
    return {"revision": REVISION, "available_bundles": len(available), "retained_bundles": len(kept),
            "excluded_bundle_ids": excluded, "retrieved_range_cells": cells, "context_range_cells": retained_cells,
            "range_cell_coverage": retained_cells / cells if cells else None,
            "interpretation": "Coverage of retrieved source cells and atomic bundles, not factual correctness or document completeness."}
