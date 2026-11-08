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

from .errors import ApiError

REVISION = "evidence-bundles-v2"
MAX_TABLE_INSPECT_CHARS = 200_000
MAX_TABLE_METADATA_CHARS = 2_000_000
MAX_TABLE_CELLS = 4_096
MAX_TABLE_RECOVERY_HASHES = 20_000
MAX_TABLE_RECOVERY_BYTES = 8_388_608
MAX_TABLE_RECOVERY_SECONDS = .05


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
            if type(row) is not int or type(column) is not int or min(row, column) < 0:
                return None
            by_row[row].append(cell)
        for row, row_cells in sorted(by_row.items()):
            row_cells = sorted(row_cells, key=lambda cell: (cell["start_col_offset_idx"], str(cell.get("text", ""))))
            records.append({"index": row, "text": " | ".join(str(cell.get("text", "")) for cell in row_cells),
                            "header": any(cell.get("column_header") is True for cell in row_cells),
                            "section": any(cell.get("row_section") is True for cell in row_cells),
                            "spans_to": max([row + 1] + [cell.get("end_row_offset_idx", row + 1)
                                for cell in row_cells if type(cell.get("end_row_offset_idx", row + 1)) is int]),
                            "merge_origins": []})
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
                                if cell.get("merge_origin_id") in origins]})
    offset = 0
    for record in records:
        record.update(start=offset, end=offset + len(record["text"]))
        offset = record["end"] + 1
    return records or None


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
    row = db.one("SELECT text,source_text_hash,extraction_revision_id,metadata_json FROM blocks WHERE generation_id=? AND id=?",
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
            records, recovery = None, "unavailable"
            try:
                metadata = json.loads(parent["metadata_json"])
                records = _row_records(metadata)
                if records is None or "\n".join(record["text"] for record in records) != parent["text"]:
                    recovered, recovery = _recover_cell_texts(metadata, parent["text"])
                    records = _row_records(recovered) if recovered is not None else None
            except (ValueError, TypeError):
                records = None
            table_cache[key] = records, recovery
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
        if len("\n".join(record["text"] for record in chosen)) > maximum_chars:
            return source, [_warning("table_evidence_bundle_too_large",
                "Les lignes et en-têtes liés dépassent la limite du paquet de preuves ; le fragment original reste signalé comme partiel.", source)]
        for record in chosen:
            blocks.append({**block, "text": parent["text"][record["start"]:record["end"]],
                           "start_offset": record["start"], "end_offset": record["end"]})
        structure.append({"block_id": block["id"], "source_rows": [record["index"] for record in chosen],
                          "header_rows": sorted(headers), "headers_verified": bool(headers),
                          "whole_table": len(chosen) == len([record for record in records if record["text"]]),
                          "complete_rows": True, "serialization_verified": True,
                          "cell_text_verification": recovery if recovery == "hash_verified" else "stored_text",
                          "row_selection": "question_terms" if focused is not None else "retrieved_span"})
    text = "\n".join(block["text"] for block in blocks)
    if not structure:
        return source, []
    if len(text) > maximum_chars:
        return source, [_warning("table_evidence_bundle_too_large",
            "L'ensemble des blocs liés dépasse la limite du paquet ; le fragment original reste partiel.", source)]
    identity = _digest([source["generation_id"], [(block["id"], block["start_offset"], block["end_offset"],
                                                 block["source_text_hash"]) for block in blocks]])
    return {**source, "text": text, "blocks": blocks, "evidence_bundle": {
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
    """Select complete proven rows; ties too broad retain the retrieved span.

    No quantity, numeric result or column role is inferred by this lexical
    filter. Verified headers, row sections and merged origins are added later.
    """
    from .retrieval import contains_identifier

    terms = _expanded_terms(question)
    ranked = [(len(terms & {word[:5] for word in re.findall(r"\w+", _fold(record["text"])) if len(word) >= 3}), record["index"])
              for record in records if not record["header"] and not record["section"] and record["text"]]
    best = max((score for score, _ in ranked), default=0)
    if not best:
        return None
    selected = {index for score, index in ranked if score == best}
    # A generic one-word query is not an authorization to discard an arbitrary
    # tail of equally relevant rows. Keep original span selection in that case.
    if len(selected) > 12:
        return None
    selected.update(record["index"] for record in records
                    if any(contains_identifier(record["text"], code) for code in required_identifiers))
    return selected


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
