"""Cell-range evidence projected before lexical statistics and dense ranking."""

import hashlib
import json
import sqlite3

from .errors import ApiError
from .office import cell_semantics

MAX_RANGE_CELLS = 1_000
MAX_RANGE_TEXT = 200_000
MAX_RANGE_FRAGMENTS = 2_048


def focused_ranges(snapshot, alias):
    if snapshot.cell_ranges is None:
        return "", []
    if not snapshot.cell_ranges or len(snapshot.cell_ranges) > 128:
        raise ApiError("invalid_cell_focus", "Focus cellule invalide.")
    clauses: list[str] = []
    parameters: list[int] = []
    for bounds in snapshot.cell_ranges:
        clauses.append(f"({alias}.row_index BETWEEN ? AND ? AND {alias}.column_index BETWEEN ? AND ?)")
        parameters.extend(bounds[key] for key in ("row_start", "row_end", "column_start", "column_end"))
    return " AND (" + " OR ".join(clauses) + ")", parameters


def projected_cells(db, snapshot):
    if not snapshot.generations:
        return []
    scope = snapshot.scope
    generation_id = snapshot.generations[0]
    parameters = (generation_id, scope["sheetId"], scope["rowStart"], scope["rowEnd"], scope["columnStart"], scope["columnEnd"])
    clause, focus = focused_ranges(snapshot, "c")
    count = db.one("SELECT count(*) n FROM office_cells c WHERE generation_id=? AND unit_id=? AND row_index BETWEEN ? AND ? AND column_index BETWEEN ? AND ?" + clause, (*parameters, *focus))["n"]
    if count > MAX_RANGE_CELLS:
        raise ApiError("office_scope_too_large", "La recherche d'une plage est limitée à 1 000 cellules présentes ; réduisez le périmètre.", 413)
    clause, focus = focused_ranges(snapshot, "x")
    rows = db.rows("SELECT x.*,b.text,b.metadata_json,b.extraction_revision_id,b.source_text_hash,c.address,c.data_json FROM office_cell_bindings x JOIN blocks b ON b.generation_id=x.generation_id AND b.id=x.block_id JOIN office_cells c ON c.generation_id=x.generation_id AND c.unit_id=x.unit_id AND c.row_index=x.row_index AND c.column_index=x.column_index WHERE x.generation_id=? AND x.unit_id=? AND x.row_index BETWEEN ? AND ? AND x.column_index BETWEEN ? AND ?" + clause + " ORDER BY x.row_index,x.column_index,x.field,x.start_offset", (*parameters, *focus))
    cells: dict[tuple[int, int], dict] = {}
    total = 0
    for row in rows:
        if snapshot.block_ids is not None and row["block_id"] not in snapshot.block_ids:
            continue
        metadata = json.loads(row["metadata_json"])
        original_binding = next((binding for binding in metadata.get("bindings", [])
                                 if binding["start"] == row["start_offset"] and binding["end"] == row["end_offset"]
                                 and binding["address"] == row["address"] and binding["field"] == row["field"]), None)
        if original_binding is None:
            raise ApiError("source_text_integrity_failure", "La projection ne correspond pas aux cellules sources.", 409)
        total += row["end_offset"] - row["start_offset"]
        if total > MAX_RANGE_TEXT:
            raise ApiError("office_scope_too_large", "Le texte de la plage dépasse le budget local ; réduisez le périmètre.", 413)
        cell = cells.setdefault((row["row_index"], row["column_index"]), {"address": row["address"], "row": row["row_index"], "column": row["column_index"], "fields": {}, "facts": cell_semantics(json.loads(row["data_json"]))})
        cell["fields"].setdefault(row["field"], []).append((original_binding.get("source_start", 0), row, metadata["locator"]))
    generation = db.one("SELECT extraction_revision_id,state,coverage_json,warnings_json FROM index_generations WHERE id=?", (generation_id,))
    results = []
    for cell in cells.values():
        text = ""
        spans = []
        for field, records in sorted(cell["fields"].items()):
            records.sort(key=lambda item: item[0])
            if text:
                text += "\n"
            prefix = f"{cell['address']} ({field}) : "
            for position, (_, row, locator) in enumerate(records):
                start = row["start_offset"] - len(prefix) if position == 0 else row["start_offset"]
                if position == 0 and row["text"][start:row["start_offset"]] != prefix:
                    raise ApiError("source_text_integrity_failure", "La localisation du champ source est invalide.", 409)
                piece = row["text"][start:row["end_offset"]]
                exact_locator = {**locator, "cell_range": cell["address"], "row_start": cell["row"], "row_end": cell["row"],
                                 "column_start": cell["column"], "column_end": cell["column"]}
                spans.append({"id": row["block_id"], "block_id": row["block_id"], "text": piece,
                              "start_offset": start, "end_offset": row["end_offset"], "projection_start": len(text),
                              "projection_end": len(text) + len(piece), "page_index": None, "page": {}, "bbox": None,
                              "precision": "cell", "type": "table_cell", "locator": exact_locator,
                              "field": field, "extraction_revision_id": row["extraction_revision_id"],
                              "source_text_hash": row["source_text_hash"], "extraction_method": "office_native"})
                text += piece
        if not text:
            continue
        results.append({"text": text, "blocks": spans, "format": "xlsx", "precision": "cell", "locator": spans[0]["locator"],
                        "generation_id": generation_id, "extraction_revision_id": generation["extraction_revision_id"],
                        "version_id": snapshot.versions[generation_id], "document_id": snapshot.documents[generation_id],
                        "coverage": json.loads(generation["coverage_json"]), "extraction_state": generation["state"],
                        "extraction_warnings": json.loads(generation["warnings_json"]), "page_indices": [],
                        "extraction_methods": ["office_native"], "parent_id": "cell:" + scope["sheetId"] + ":" + cell["address"],
                        "scope_projected": True, "cell_facts": [cell["facts"]]})
    return results


def projection_fragments(db, snapshot, embedding):
    from .indexing import split_text
    result = []
    for cell in projected_cells(db, snapshot):
        for start, end in split_text(cell["text"], embedding, 320, 48):
            blocks = []
            for block in cell["blocks"]:
                lo, hi = max(start, block["projection_start"]), min(end, block["projection_end"])
                if lo < hi:
                    offset = lo - block["projection_start"]
                    blocks.append({**block, "text": block["text"][offset:offset + hi - lo],
                                   "start_offset": block["start_offset"] + offset, "end_offset": block["start_offset"] + offset + hi - lo})
            text = cell["text"][start:end]
            digest = hashlib.sha256(text.encode()).hexdigest()
            result.append({**cell, "text": text, "blocks": blocks, "chunk_id": "office-range:" + digest,
                           "hash": digest})
            if len(result) > MAX_RANGE_FRAGMENTS:
                raise ApiError("office_scope_too_large", "La plage produit trop de fragments ; réduisez le périmètre.", 413)
    return result


def lexical_projection(question, sources, limit):
    from .retrieval import contains_identifier, identifiers, match_expression, normalized_identifier
    expression = match_expression(question)
    exact = []
    codes = sorted({normalized_identifier(value) for value in identifiers(question)})
    # Independent FTS5 corpus: excluded cells cannot alter document frequency/BM25.
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE VIRTUAL TABLE evidence USING fts5(text)")
        connection.executemany("INSERT INTO evidence(rowid,text) VALUES(?,?)", [(i + 1, source["text"]) for i, source in enumerate(sources)])
        ranked = [row[0] - 1 for row in connection.execute("SELECT rowid FROM evidence WHERE evidence MATCH ? ORDER BY bm25(evidence),rowid LIMIT ?", (expression, limit))] if expression else []
        order = ranked + [i for i in range(len(sources)) if i not in ranked]
        for code in codes:
            exact.extend([i for i in order if contains_identifier(sources[i]["text"], code)][:limit])
    exact = list(dict.fromkeys(exact))[:limit]
    return list(dict.fromkeys(exact + ranked))[:limit], exact
