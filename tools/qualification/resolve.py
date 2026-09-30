"""Resolve evidence annotations from real API extraction snapshots, without retrieval."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def whitespace_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace only; positions remain Unicode code-point offsets."""
    chars: list[str] = []
    mapping: list[int] = []
    for index, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                mapping.append(index)
        else:
            chars.append(char)
            mapping.append(index)
    while chars and chars[-1] == " ":
        chars.pop(); mapping.pop()
    return "".join(chars), mapping


def metadata(block: dict) -> dict:
    current = block.get("metadata") or {}
    # API stores ingestion metadata inside its own metadata envelope.
    merged = dict(current) if isinstance(current, dict) else {}
    for _ in range(3):
        nested = current.get("metadata") if isinstance(current, dict) else None
        if not isinstance(nested, dict):
            break
        merged.update(nested)
        current = nested
    return merged


def checked_blocks(binding: dict, page_index: int) -> tuple[list[dict], list[str]]:
    errors = []
    pages = [page for page in binding.get("pages", []) if page.get("page", {}).get("page_index", page.get("page_index")) == page_index]
    if len(pages) != 1:
        return [], ["Exactly one real page snapshot required"]
    page = pages[0]
    blocks = []
    for original in page.get("blocks", []):
        block = dict(original)
        raw = block.get("raw_text")
        revision = block.get("extraction_revision_id")
        if not isinstance(raw, str) or not block.get("id") or not revision or not block.get("source_text_hash"):
            errors.append("Block missing exact raw_text, ID, extraction revision or source hash")
            continue
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != block["source_text_hash"]:
            errors.append("Source text hash does not match exact block text")
            continue
        if block.get("version_id", binding.get("version_id")) != binding.get("version_id"):
            errors.append("Block belongs to another version")
            continue
        if binding.get("extraction_revision_id") and revision != binding["extraction_revision_id"]:
            errors.append("Block belongs to another extraction revision")
            continue
        if binding.get("generation_id") and block.get("generation_id", binding["generation_id"]) != binding["generation_id"]:
            errors.append("Block belongs to another generation")
            continue
        block["page_index"] = page_index
        blocks.append(block)
    return blocks, errors


def span(block: dict, start: int, end: int, binding: dict) -> dict:
    return {"block_id": block["id"], "version_id": binding["version_id"], "generation_id": block.get("generation_id", binding.get("generation_id")), "extraction_revision_id": block["extraction_revision_id"], "source_text_hash": block["source_text_hash"], "page_index": block["page_index"], "offset_unit": "unicode_code_point", "start_offset": start, "end_offset": end, "text": block["raw_text"][start:end], "precision": block.get("precision", "block"), "bbox": block.get("bbox")}


def text_spans(blocks: list[dict], needle: str, binding: dict) -> tuple[list[dict] | None, str | None]:
    # Join in the extraction's original order. Whitespace can span native lines
    # and blocks; no ligature expansion, dehyphenation or OCR correction here.
    joined: list[str] = []
    positions: list[tuple[int, int] | None] = []
    for block_index, block in enumerate(blocks):
        if joined:
            joined.append(" "); positions.append(None)
        for index, char in enumerate(block["raw_text"]):
            joined.append(char); positions.append((block_index, index))
    normalized, mapping = whitespace_map("".join(joined))
    target, _ = whitespace_map(needle)
    if not target:
        return None, "Empty required evidence"
    hits = [match.start() for match in re.finditer(re.escape(target), normalized)]
    if len(hits) != 1:
        return None, "Required text absent or ambiguous in exact source"
    hit = hits[0]
    first, last = mapping[hit], mapping[hit + len(target) - 1]
    ranges: dict[int, list[int]] = {}
    for position in positions[first:last + 1]:
        if position is not None:
            block_index, offset = position
            if block_index not in ranges:
                ranges[block_index] = [offset, offset + 1]
            else:
                ranges[block_index][1] = offset + 1
    return [span(blocks[index], start, end, binding) for index, (start, end) in ranges.items()], None


def row_is_structured(block: dict, required: dict) -> bool:
    data = metadata(block).get("table_data")
    if not isinstance(data, dict):
        return False
    rows: dict[int, list[str]] = {}
    for cell in data.get("table_cells", []):
        if not isinstance(cell, dict) or not isinstance(cell.get("text"), str):
            continue
        index = cell.get("start_row_offset")
        if not isinstance(index, int):
            continue
        rows.setdefault(index, []).append(whitespace_map(cell["text"])[0])
    wanted = [str(required[key]) for key in ("identifier", "value", "unit")]
    return any(all(value in cells for value in wanted) for cells in rows.values())


def row_spans(blocks: list[dict], required: dict, binding: dict) -> tuple[list[dict] | None, str | None]:
    matches = []
    wanted = [str(required[key]) for key in ("identifier", "value", "unit")]
    for block in blocks:
        offset = 0
        for row in block["raw_text"].splitlines(keepends=True):
            # A row must contain each exact token, in order, on the same line.
            # Independent arbitrary matches from different rows are refused.
            pattern = r"(?<![\w.-])" + re.escape(wanted[0]) + r"(?![\w.-]).*?(?<![\w.])" + re.escape(wanted[1]) + r"(?![\w.]).*?(?<![\w/])" + re.escape(wanted[2]) + r"(?![\w/])"
            found = re.search(pattern, row)
            if found:
                matches.append([span(block, offset + found.start(), offset + found.end(), binding)])
            offset += len(row)
        if not any(item[0]["block_id"] == block["id"] for item in matches) and row_is_structured(block, required):
            matches.append([span(block, 0, len(block["raw_text"]), binding)])
    if len(matches) != 1:
        return None, "Required table row absent, ambiguous or its cell association not established"
    return matches[0], None


def resolve_unit(original: dict, bindings: dict) -> dict:
    result = copy.deepcopy(original)
    binding = bindings.get(original["document_key"])
    if not binding:
        result.update(resolution_status="UNRESOLVED", resolution_errors=["No real extraction binding for this document"])
        return result
    required_fields = ("document_id", "version_id", "extraction_revision_id", "file_sha256")
    if any(not binding.get(key) for key in required_fields):
        result.update(resolution_status="UNRESOLVED", resolution_errors=["Real document/version/revision/file SHA required"])
        return result
    if binding["file_sha256"] != original["file_sha256"]:
        result.update(resolution_status="UNRESOLVED", resolution_errors=["Original PDF SHA does not match frozen source"])
        return result
    blocks, block_errors = checked_blocks(binding, original["page_index"])
    resolved = []
    errors = []
    if original.get("required_row"):
        found, error = row_spans(blocks, original["required_row"], binding)
        if error:
            errors.append(error)
        else:
            resolved.extend(found or [])
    else:
        for required in original["required_texts"]:
            found, error = text_spans(blocks, required, binding)
            if error:
                errors.append(error)
            else:
                resolved.extend(found or [])
    if errors or not resolved:
        result.update(resolution_status="UNRESOLVED", resolution_errors=errors + block_errors)
    else:
        result.update(version_id=binding["version_id"], extraction_revision_id=binding["extraction_revision_id"], generation_id=binding.get("generation_id"), resolved_spans=resolved, resolution_status="RESOLVED", resolution_warnings=block_errors)
    return result


def resolve_dataset(original: dict, snapshot: dict) -> dict:
    result = copy.deepcopy(original)
    bindings = snapshot.get("documents", {})
    for question in result["questions"]:
        documents = [bindings.get(key) for key in question["scope_template"]["document_keys"]]
        source_hashes = {source["document_key"]: source.get("file_sha256") for source in question.get("document_sources", [])}
        scope_ok = all(document and document.get("document_id") and document.get("version_id") and document.get("extraction_revision_id") and source_hashes.get(key) and document.get("file_sha256") == source_hashes[key] for key, document in zip(question["scope_template"]["document_keys"], documents, strict=True))
        if scope_ok:
            question["scope_resolved"] = {"kind": "documents", "documentIds": [document["document_id"] for document in documents]}
            question["versions_snapshot"] = [{"document_id": document["document_id"], "version_id": document["version_id"], "extraction_revision_id": document.get("extraction_revision_id"), "generation_id": document.get("generation_id"), "file_sha256": document.get("file_sha256")} for document in documents]
        question["expected_units"] = [resolve_unit(unit, bindings) for unit in question["expected_units"]]
        question["annotation_state"] = "RESOLVED" if scope_ok and all(unit["resolution_status"] == "RESOLVED" for unit in question["expected_units"]) else "UNRESOLVED"
    states = [question["annotation_state"] for question in result["questions"]]
    result["status"] = "ANNOTATIONS_RESOLVED_NOT_RAG_QUALIFIED" if all(state == "RESOLVED" for state in states) else "ANNOTATIONS_PARTIALLY_RESOLVED_NOT_RAG_QUALIFIED"
    result["resolution_summary"] = {"resolved_questions": states.count("RESOLVED"), "unresolved_questions": states.count("UNRESOLVED"), "source_snapshot_sha256": hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "evals") or output in (args.dataset.resolve(), args.bindings.resolve()):
        parser.error("Output must be a separate file inside the authorized evals directory")
    result = resolve_dataset(json.loads(args.dataset.read_text(encoding="utf-8")), json.loads(args.bindings.read_text(encoding="utf-8")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["resolution_summary"]))
