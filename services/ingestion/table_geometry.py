"""Rebuild PDF table relations from bounded, literal spatial observations.

Parser row/column indices alone never establish a MIN/TYP/MAX binding. Native
observations retain PDFium character indices; OCR observations retain the real
reading witnesses. The original parser table remains available for audit. This
module does not infer missing numbers, units, headings or scientific meaning.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import statistics
import unicodedata
from bisect import bisect_right
from pathlib import Path
from typing import Any

from .errors import IngestionError
from .geometry import docling_box_to_pdf, normalize_box, pdf_box_to_docling
from .table_rules import native_rule_observations, prove_header_group, scoped_rule_observations

TABLE_QUALITY_SCHEMA = "geometry-table-v1"
TABLE_GEOMETRY_POLICY = "literal-glyph-projection-v1"
TABLE_ORIENTATION_SCHEMA = "table-reading-orientation-v1"
MAX_PAGE_GLYPHS = 20_000
MAX_TABLE_GLYPHS = 6_000
MAX_TABLE_OBSERVATIONS = 4_096
MAX_PARSER_TABLE_CELLS = 4_096
MAX_QUALITY_BYTES = 1_500_000
GENERAL_CONDITIONS_SCHEMA = "table-general-conditions-v1"
GENERAL_CONDITIONS_POLICY = "explicit-pretable-condition-band-v1"
GENERAL_CONDITION_LINES_SCHEMA = "table-general-conditions-v2"
GENERAL_CONDITION_LINES_POLICY = "explicit-pretable-condition-band-lines-v2"
MAX_GENERAL_BLOCKS = 256
MAX_GENERAL_PIECES = 8
MAX_GENERAL_CHARS = 4096
_GENERAL_HEADER = re.compile(r"\b(?:specifications?|characteristics|caracteristiques?|conditions?)\b", re.I)
_GENERAL_QUALIFIER = re.compile(r"\b(?:unless\s+otherwise\s+(?:noted|specified|stated)|sauf\s+(?:mention|indication)\s+contraire|except\s+(?:as|where)\s+(?:noted|specified))\b", re.I)
_ROLES = {
    "min": "minimum", "minimum": "minimum", "minimale": "minimum",
    "max": "maximum", "maximum": "maximum", "maximale": "maximum",
    "typ": "typical", "typical": "typical", "typique": "typical",
    "nom": "nominal", "nominal": "nominal", "nominale": "nominal",
    "unit": "unit", "units": "unit", "unite": "unit", "unites": "unit",
    "condition": "condition", "conditions": "condition",
    "parameter": "parameter", "parameters": "parameter", "parametre": "parameter", "parametres": "parameter",
    "symbol": "symbol", "symbole": "symbol",
}
_NUMERIC_ROLES = {"minimum", "maximum", "typical", "nominal"}
_VALUE_ROLES = _NUMERIC_ROLES | {"quantity"}
_SINGLE_VALUE_HEADER_ROLES = {
    **{word: role for word, role in _ROLES.items() if role in {"parameter", "unit"}},
    "equipment": "parameter", "equipement": "parameter", "label": "parameter", "libelle": "parameter",
    "reference": "parameter", "value": "quantity", "valeur": "quantity",
}
_DURATION_HEADER_WORDS = {"time", "duration", "delay", "latency", "temps", "duree", "delai", "latence"}
_INDEXED_HEADER = re.compile(r"([A-Za-z][A-Za-z_]{0,31})([0-9]{1,2})")
_UNSUPPLIED_FRAME = object()


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _fold(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char)).strip().rstrip(".")


def _union(boxes):
    return [min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes)]


def _inside(box, frame, tolerance=1.0):
    return (box[0] >= frame[0] - tolerance and box[1] >= frame[1] - tolerance
            and box[2] <= frame[2] + tolerance and box[3] <= frame[3] + tolerance)


def _display_box(box, page, reading_rotation=0):
    """Use the same verified inverse as the regional OCR adapter."""
    frame = page.get("effective_box") or page.get("crop_box")
    left, bottom, right, top = normalize_box(frame)
    width, height = right - left, top - bottom
    rotation = (int(page["rotation"]) + reading_rotation) % 360
    size = (height, width) if rotation in {90, 270} else (width, height)
    mapped = pdf_box_to_docling(box, size, {**page, "rotation": rotation})
    return [mapped["l"], mapped["t"], mapped["r"], mapped["b"]]


def native_glyph_observations(path, page_indices, source_sha256):
    """Read glyph identities without rendering, under the existing PDFium lock.

    GetUnicode indices are not Python string offsets. Experimental map/generated
    flags are version-pinned by the adapter tests; unknown states remain unknown.
    Every native handle is closed before returning the bounded observations.
    """
    import pypdfium2 as pdfium
    from docling.backend.pypdfium2_backend import pypdfium2_lock

    result = {}
    with pypdfium2_lock:
        document = pdfium.PdfDocument(str(Path(path)))
        try:
            for index in sorted(set(page_indices)):
                record: dict[str, Any] = {"schema_version": "pdfium-glyphs-v1", "source_sha256": source_sha256,
                          "page_index": index, "coordinate_frame": "pdf_user_space_unrotated", "glyphs": [],
                          "complete": False, "limit_reason": None}
                page = document[index]
                text_page = page.get_textpage()
                try:
                    count = text_page.count_chars()
                    if count > MAX_PAGE_GLYPHS:
                        record["limit_reason"] = "native_glyph_page_limit"
                        result[index] = record
                        continue
                    for glyph_index in range(count):
                        codepoint = int(pdfium.raw.FPDFText_GetUnicode(text_page, glyph_index))
                        value = chr(codepoint) if 0 < codepoint <= 0x10FFFF and not 0xD800 <= codepoint <= 0xDFFF else None
                        try:
                            box = normalize_box(text_page.get_charbox(glyph_index))
                        except (pdfium.PdfiumError, IngestionError):
                            box = None
                        text_object = pdfium.raw.FPDFText_GetTextObject(text_page, glyph_index)
                        render_mode = int(pdfium.raw.FPDFTextObj_GetTextRenderMode(text_object)) if text_object else None
                        record["glyphs"].append({"id": f"g{glyph_index}", "glyph_index": glyph_index,
                                                 "codepoint": codepoint, "text": value, "bbox": box,
                                                 "generated": int(pdfium.raw.FPDFText_IsGenerated(text_page, glyph_index)),
                                                 "unicode_map_error": int(pdfium.raw.FPDFText_HasUnicodeMapError(text_page, glyph_index)),
                                                 "render_mode": render_mode})
                    record["complete"] = True
                    if count:
                        record["rules"] = native_rule_observations(page, pdfium.raw, source_sha256=source_sha256, page_index=index)
                    result[index] = record
                finally:
                    text_page.close()
                    page.close()
        finally:
            document.close()
    return result


def _line_groups(items):
    """Group by actual vertical overlap, attaching small punctuation to its line."""
    if not items:
        return []
    median_height = statistics.median(item["display_bbox"][3] - item["display_bbox"][1] for item in items)
    anchors = [item for item in items if item["display_bbox"][3] - item["display_bbox"][1] >= median_height * .6]
    small = [item for item in items if item not in anchors]
    lines: list[list[dict]] = []
    for item in sorted(anchors, key=lambda v: ((v["display_bbox"][1] + v["display_bbox"][3]) / 2, v["display_bbox"][0])):
        box = item["display_bbox"]
        cy = (box[1] + box[3]) / 2
        candidates = []
        for line in lines:
            centres = [(word["display_bbox"][1] + word["display_bbox"][3]) / 2 for word in line]
            centre = statistics.median(centres)
            if abs(cy - centre) <= median_height * .45:
                candidates.append((abs(cy - centre), line))
        if candidates:
            min(candidates, key=lambda entry: entry[0])[1].append(item)
        else:
            lines.append([item])
    for item in small:
        cy = (item["display_bbox"][1] + item["display_bbox"][3]) / 2
        distances = [(abs(cy - statistics.median((w["display_bbox"][1] + w["display_bbox"][3]) / 2 for w in line)), line)
                     for line in lines]
        if distances and min(distances, key=lambda entry: entry[0])[0] <= median_height:
            min(distances, key=lambda entry: entry[0])[1].append(item)
        else:
            lines.append([item])
    return [sorted(line, key=lambda item: (item["display_bbox"][0], item["display_bbox"][1], item["id"]))
            for line in sorted(lines, key=lambda line: statistics.median(item["display_bbox"][1] for item in line))]


def _native_words(glyphs, page, reading_rotation=0):
    by_index = {glyph["glyph_index"]: glyph for glyph in glyphs}
    positioned = []
    for glyph in glyphs:
        if not glyph.get("text") or not glyph["text"].strip() or glyph.get("bbox") is None:
            continue
        box = normalize_box(glyph["bbox"])
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        positioned.append({**glyph, "display_bbox": _display_box(box, page, reading_rotation)})
    words = []
    for line in _line_groups(positioned):
        height = statistics.median(item["display_bbox"][3] - item["display_bbox"][1] for item in line)
        groups: list[list[dict]] = []
        for glyph in line:
            previous = groups[-1][-1] if groups else None
            gap = glyph["display_bbox"][0] - previous["display_bbox"][2] if previous else 0
            consecutive = previous is not None and glyph["glyph_index"] == previous["glyph_index"] + 1
            lower, upper = sorted((previous["glyph_index"], glyph["glyph_index"])) if previous else (0, 0)
            written_space = previous is not None and upper - lower <= 8 and any(
                (by_index.get(index, {}).get("text") or "").isspace() for index in range(lower + 1, upper))
            # Tight glyph boxes do not measure advance width: a narrow '1' can
            # leave a larger gap inside 100 than the gap between words. Actual
            # character adjacency prevents fabricating an internal space.
            split = written_space or gap > max(1.2, height * .3) and not (consecutive and gap <= height * 1.5)
            if not groups or split:
                groups.append([glyph])
            else:
                groups[-1].append(glyph)
        for group in groups:
            ids = [glyph["id"] for glyph in group]
            valid = all(type(glyph.get("unicode_map_error")) is int and glyph["unicode_map_error"] == 0
                        and type(glyph.get("generated")) is int and glyph["generated"] == 0
                        and type(glyph.get("render_mode", 0)) is int and glyph.get("render_mode", 0) in {0, 1, 2, 4, 5, 6} for glyph in group)
            words.append({"id": "n:" + ",".join(ids), "text": "".join(glyph["text"] for glyph in group),
                          "bbox": _union([glyph["bbox"] for glyph in group]), "origin": "native", "glyph_ids": ids,
                          "state": "supported" if valid else "ambiguous",
                          "reasons": [] if valid else ["native_glyph_mapping_unverified"]})
    return words


def _spatial_observations(bbox, page, native, cells, reading_rotation=0):
    glyphs = []
    if isinstance(native, dict) and native.get("complete") is True:
        seen = set()
        for glyph in native.get("glyphs", []):
            index = glyph.get("glyph_index")
            if (type(index) is not int or index < 0 or index in seen or glyph.get("id") != f"g{index}"
                    or glyph.get("text") is not None and (not isinstance(glyph["text"], str) or len(glyph["text"]) != 1
                                                         or ord(glyph["text"]) != glyph.get("codepoint"))):
                return [], [], "native_glyph_identity_invalid"
            seen.add(index)
            if glyph.get("bbox") and _inside(normalize_box(glyph["bbox"]), bbox):
                box = normalize_box(glyph["bbox"])
                value = glyph.get("text")
                if box[2] > box[0] and box[3] > box[1] and (value is None or not value.isspace() and unicodedata.category(value).startswith("C")):
                    return [], [], "native_glyph_unmapped"
                glyphs.append(copy.deepcopy(glyph))
    if len(glyphs) > MAX_TABLE_GLYPHS:
        return [], [], "table_glyph_limit"
    observations = _native_words(glyphs, page, reading_rotation)
    ocr_cells = []
    for index, cell in enumerate(cells):
        if not cell.get("from_ocr") or not cell.get("text", "").strip() or not cell.get("bbox") or not _inside(cell["bbox"], bbox):
            continue
        quality = cell.get("ocr_quality", {})
        observation = {"id": f"o:{index}", "text": cell["text"], "bbox": list(cell["bbox"]), "origin": "ocr", "glyph_ids": [],
                       "reading_ids": list(quality.get("reading_ids", [])),
                       "state": "supported" if quality.get("state") == "corroborated" else "ambiguous",
                       "reasons": list(quality.get("reasons", [])) or ([] if quality.get("state") == "corroborated" else ["ocr_reading_unverified"])}
        observations.append(observation)
        ocr_cells.append(copy.deepcopy(cell))
    if len(observations) > MAX_TABLE_OBSERVATIONS:
        return [], [], "table_observation_limit"
    if not observations:
        return [], [], "table_observations_missing"
    native_subset = {**native, "glyphs": glyphs} if isinstance(native, dict) else None
    if native_subset is not None and "rules" in native_subset:
        native_subset["rules"] = scoped_rule_observations(native_subset["rules"], source_sha256=native_subset["source_sha256"],
                                                        page_index=page["page_index"], table_bbox=bbox)
    return observations, [native_subset, ocr_cells], None


def _header_role(header):
    return header.get("_role") or _ROLES.get(_fold(header["text"]))


def _single_value_headers(source_groups):
    """Admit an explicit label/value/unit band without inventing a statistic.

    Only the first observed row group may establish this narrow three-column
    grammar. Anchors must be unique, horizontally distinct and on one physical
    line. Other literal header parts still pass through _header_literals; they
    are never discarded. Data values and parser column ordinals do not choose
    the grammar, and Value/Valeur never means typical, nominal or a bound.
    """
    if not source_groups:
        return None
    items = source_groups[0]["observations"]
    known = [item for item in items if _fold(item["text"]) in _SINGLE_VALUE_HEADER_ROLES]
    roles = [_SINGLE_VALUE_HEADER_ROLES[_fold(item["text"])] for item in known]
    if len(known) != 3 or set(roles) != {"parameter", "quantity", "unit"}:
        return None
    if any(_ROLES.get(_fold(item["text"])) in _NUMERIC_ROLES | {"condition", "symbol"} for item in items):
        return None
    identities = {item["id"] for item in known}
    if not any(identities <= {item["id"] for item in line} for line in _line_groups(items)):
        return None
    ordered = sorted(known, key=lambda item: item["display_bbox"][0])
    if any(left["display_bbox"][2] >= right["display_bbox"][0] for left, right in zip(ordered, ordered[1:], strict=False)):
        return None
    return [{**item, "_role": _SINGLE_VALUE_HEADER_ROLES[_fold(item["text"])]} for item in ordered]


def _headers(observations, source_groups):
    candidates = []
    for line in _line_groups(observations):
        known = [item for item in line if _fold(item["text"]) in _ROLES]
        roles = [_ROLES[_fold(item["text"])] for item in known]
        if len(set(roles) & _NUMERIC_ROLES) >= 2 and "unit" in roles and "parameter" in roles and len(roles) == len(set(roles)):
            candidates.append(known)
    if candidates:
        return sorted(candidates, key=lambda group: (min(item["display_bbox"][1] for item in group), -len(group)))[0]
    single_value = _single_value_headers(source_groups)
    if single_value is not None:
        return single_value
    # An indexed code family plus an explicit duration heading establishes a
    # different table grammar. Neither data values nor parser column ordinals
    # select the family or define a bit's significance. Keep suffix labels such
    # as pin/register positions as literal header parts, not a second bit order.
    for group in source_groups:
        if not group["cells"] or not all(cell.get("column_header") is True for cell in group["cells"]):
            continue
        families: dict[str, list[tuple[int, dict]]] = {}
        durations = []
        for item in group["observations"]:
            match = _INDEXED_HEADER.fullmatch(item["text"])
            if match:
                families.setdefault(match[1], []).append((int(match[2]), item))
            if _fold(item["text"]) in _DURATION_HEADER_WORDS:
                durations.append(item)
        complete = [family for family in families.values() if 2 <= len(family) <= 16
                    and sorted(index for index, _ in family) == list(range(len(family)))]
        if len(complete) == 1 and len(durations) == 1:
            anchors = [{**item, "_role": "code"} for _, item in complete[0]]
            anchors.append({**durations[0], "_role": "quantity"})
            return anchors
    return None


def _boundaries(headers, table_box):
    boxes = [header.get("_column_bbox", header["display_bbox"]) for header in headers]
    centres = [(box[0] + box[2]) / 2 for box in boxes]
    result = [table_box[0]]
    for index in range(1, len(headers)):
        left, right = headers[index - 1], headers[index]
        left_box, right_box = boxes[index - 1], boxes[index]
        role = _header_role(right)
        prior = _header_role(left)
        if role in _VALUE_ROLES and prior not in _VALUE_ROLES:
            next_numeric = next((j for j in range(index + 1, len(headers)) if _header_role(headers[j]) in _VALUE_ROLES), None)
            distance = centres[next_numeric] - centres[index] if next_numeric is not None else centres[index] - centres[index - 1]
            boundary = max(left_box[2] + 1, centres[index] - distance / 2)
        elif role in {"parameter", "condition", "symbol"}:
            boundary = right_box[0] - max(1, (right_box[3] - right_box[1]) / 2)
        else:
            boundary = (centres[index - 1] + centres[index]) / 2
        result.append(boundary)
    result.append(table_box[2])
    return result if all(a < b for a, b in zip(result, result[1:], strict=False)) else None


def _column(observation, boundaries):
    box = observation["display_bbox"]
    return min(len(boundaries) - 2, max(0, bisect_right(boundaries, (box[0] + box[2]) / 2) - 1))


def _column_range(observation, boundaries):
    box = observation["display_bbox"]
    margin = min(1.0, (box[2] - box[0]) / 4)
    low = min(len(boundaries) - 2, max(0, bisect_right(boundaries, box[0] + margin) - 1))
    high = min(len(boundaries) - 2, max(0, bisect_right(boundaries, box[2] - margin) - 1))
    return low, high + 1


def _text(items):
    return " ".join(item["text"] for line in _line_groups(items) for item in line)


def _condition_key(items):
    match = re.match(r"^(.+?)([=<>:])", _text(items))
    return (_fold(match[1]), match[2]) if match else None


def _cell(items, row, column, *, end_column=None, row_span=1, header=False, row_header=False, section=False):
    box = _union([item["display_bbox"] for item in items])
    return {"text": _text(items), "start_row_offset_idx": row, "end_row_offset_idx": row + row_span,
            "start_col_offset_idx": column, "end_col_offset_idx": end_column or column + 1,
            "row_span": row_span, "col_span": (end_column or column + 1) - column,
            "column_header": header, "row_header": row_header, "row_section": section,
            "bbox": {"l": box[0], "t": box[1], "r": box[2], "b": box[3], "coord_origin": "TOPLEFT"},
            "_observation_ids": [item["id"] for line in _line_groups(items) for item in line]}


def _source_groups(data, observations, parser_size, page, reading_rotation=0):
    grouped: dict[int, dict[str, Any]] = {}
    for cell in data.get("table_cells", []):
        row = cell.get("start_row_offset_idx")
        if type(row) is not int or not cell.get("bbox"):
            continue
        box = _display_box(docling_box_to_pdf(cell["bbox"], parser_size, page), page, reading_rotation)
        group = grouped.setdefault(row, {"source_row": row, "boxes": [], "cells": [], "observations": []})
        group["boxes"].append(box)
        group["cells"].append(cell)
    groups = sorted(grouped.values(), key=lambda group: min(box[1] for box in group["boxes"]))
    for group in groups:
        group["bbox"] = _union(group["boxes"])
    unassigned = []
    for observation in observations:
        box = observation["display_bbox"]
        height = box[3] - box[1]
        candidates = [(max(0, min(box[3], group["bbox"][3] + 1) - max(box[1], group["bbox"][1] - 1)) / height, group)
                      for group in groups]
        candidates = sorted((entry for entry in candidates if entry[0] >= .5), key=lambda entry: -entry[0])
        if not candidates or len(candidates) > 1 and math.isclose(candidates[0][0], candidates[1][0], abs_tol=.01):
            unassigned.append(observation["id"])
        else:
            candidates[0][1]["observations"].append(observation)
    return [group for group in groups if group["observations"]], unassigned


def _horizontal_segments(items):
    result = []
    for line in _line_groups(items):
        height = statistics.median(item["display_bbox"][3] - item["display_bbox"][1] for item in line)
        groups: list[list[dict]] = []
        for item in line:
            if not groups or item["display_bbox"][0] - groups[-1][-1]["display_bbox"][2] > max(8, height * 2.5):
                groups.append([item])
            else:
                groups[-1].append(item)
        result.extend(groups)
    return result


def _header_literals(headers, extras, source_cells, parser_size, page, reading_rotation=0):
    """Keep a supplementary literal only with its unique observed header cell.

    The explicit role word remains the column anchor. A bar, footnote or
    qualifier is not discarded or called a grid line: its literal and reading
    observations become part of the public header. Parser column indices do not
    participate in this attachment; a cell must spatially contain exactly one
    anchor and the whole extra observation. Ambiguous attachments fail closed.
    """
    parts = {header["id"]: [header] for header in headers}
    regions = []
    for cell in source_cells:
        if not cell.get("bbox"):
            continue
        box = _display_box(docling_box_to_pdf(cell["bbox"], parser_size, page), page, reading_rotation)
        anchors = [header for header in headers if _inside(header["display_bbox"], box)]
        if len(anchors) == 1:
            regions.append((box, anchors[0]["id"]))
    for item in extras:
        matches = {identity for box, identity in regions if _inside(item["display_bbox"], box)}
        if len(matches) != 1:
            return None
        parts[next(iter(matches))].append(item)
    return parts


def _condition_header_cells(group, headers, row, parser_size, page, reading_rotation=0):
    """Project an explicit condition band using its actual cell rectangle.

    A parser colspan is never proof of scope. Only the header anchors enclosed
    horizontally by the observed source cell can inherit its exact condition.
    The source glyphs still certify the literal independently of that geometry.
    """
    records: list[dict] = []
    assigned: set[str] = set()
    for source_cell in group["cells"]:
        if not source_cell.get("bbox"):
            return None
        box = _display_box(docling_box_to_pdf(source_cell["bbox"], parser_size, page), page, reading_rotation)
        contents = [item for item in group["observations"] if _inside(item["display_bbox"], box)]
        if not contents:
            continue
        if any(item["id"] in assigned for item in contents):
            return None
        assigned.update(item["id"] for item in contents)
        columns = [column for column, header in enumerate(headers)
                   if box[0] - 1 <= header.get("_column_bbox", header["display_bbox"])[0]
                   and header.get("_column_bbox", header["display_bbox"])[2] <= box[2] + 1]
        if not columns or columns != list(range(min(columns), max(columns) + 1)):
            return None
        record = _cell(contents, row, min(columns), end_column=max(columns) + 1, header=True)
        record["_scope_bbox"] = source_cell["bbox"]
        records.append(record)
    return records if assigned == {item["id"] for item in group["observations"]} else None


def _project(data, observations, bbox, parser_size, page, reading_rotation=0, native_rules=None):
    positioned = [{**item, "display_bbox": _display_box(item["bbox"], page, reading_rotation)} for item in observations]
    groups, unassigned = _source_groups(data, positioned, parser_size, page, reading_rotation)
    if unassigned:
        return None, [], [], ["table_observations_outside_row_geometry"]
    headers = _headers(positioned, groups)
    if headers is None:
        return None, [], [], ["explicit_numeric_headers_missing"]
    headers.sort(key=lambda item: item["display_bbox"][0])
    header_ids = {item["id"] for item in headers}
    header_groups = [group for group in groups if header_ids <= {item["id"] for item in group["observations"]}]
    if len(header_groups) != 1:
        return None, [], [], ["header_row_geometry_ambiguous"]
    header_group = header_groups[0]
    same_band = [item for line in _line_groups([item for item in header_group["observations"] if item["id"] not in header_ids])
                 if min(item["display_bbox"][1] for item in line) >= min(item["display_bbox"][1] for item in headers) - 1 for item in line]
    header_parts = _header_literals(headers, same_band, header_group["cells"], parser_size, page, reading_rotation)
    if header_parts is None:
        return None, [], [], ["header_extra_text_ambiguous"]
    headers = [{**header, "_column_bbox": _union([item["display_bbox"] for item in header_parts[header["id"]]])} for header in headers]
    boundaries = _boundaries(headers, _display_box(bbox, page, reading_rotation))
    if boundaries is None:
        return None, [], [], ["header_geometry_ambiguous"]
    numeric_columns = {index for index, item in enumerate(headers) if _header_role(item) in _VALUE_ROLES}
    cells, dependencies = [], []
    next_row = 0
    for group in groups:
        items = group["observations"]
        if header_ids <= {item["id"] for item in items}:
            extra = [item for item in items if item["id"] not in header_ids]
            same_band = []
            for line in _line_groups(extra):
                if min(item["display_bbox"][1] for item in line) >= min(item["display_bbox"][1] for item in headers) - 1:
                    same_band.extend(line)
                    continue
                for segment in _horizontal_segments(line):
                    start, end = min(_column(item, boundaries) for item in segment), max(_column(item, boundaries) for item in segment) + 1
                    ruled_group = prove_header_group(
                        native_rules, segment,
                        [{**header, "part_ids": [item["id"] for item in header_parts[header["id"]]]} for header in headers],
                        positioned, table_bbox=bbox, to_display=lambda value: _display_box(value, page, reading_rotation))
                    if ruled_group is not None:
                        start, end = ruled_group["columns"][0], ruled_group["columns"][-1] + 1
                    record = _cell(segment, next_row, start, end_column=end, header=True)
                    if ruled_group is not None:
                        display = ruled_group.pop("display_bbox")
                        reading_page = {**page, "rotation": (int(page["rotation"]) + reading_rotation) % 360}
                        frame = normalize_box(page.get("effective_box") or page.get("crop_box"))
                        width, height = frame[2] - frame[0], frame[3] - frame[1]
                        reading_size = (height, width) if reading_page["rotation"] in {90, 270} else (width, height)
                        physical = docling_box_to_pdf({"l": display[0], "t": display[1], "r": display[2], "b": display[3],
                                                       "coord_origin": "TOPLEFT"}, reading_size, reading_page)
                        record["_scope_bbox"] = pdf_box_to_docling(physical, parser_size, page)
                        record["_header_group"] = {**ruled_group, "frame_bbox": physical}
                    cells.append(record)
                next_row += 1
            attached = _header_literals(headers, same_band, group["cells"], parser_size, page, reading_rotation)
            if attached is None:
                return None, [], [], ["header_extra_text_ambiguous"]
            header_parts = attached
            cells.extend(_cell(header_parts[header["id"]], next_row, column, header=True) for column, header in enumerate(headers))
            next_row += 1
            continue
        if (group["cells"] and all(cell.get("column_header") is True for cell in group["cells"])
                and max(item["display_bbox"][3] for item in items) < min(item["display_bbox"][1] for item in headers)
                and re.search(r"[=<>≤≥]", _text(items))):
            parent_headers = _condition_header_cells(group, headers, next_row, parser_size, page, reading_rotation)
            if parent_headers is None:
                return None, [], [], ["condition_header_scope_ambiguous"]
            cells.extend(parent_headers)
            next_row += 1
            continue
        lines = _line_groups(items)
        if any(cell.get("row_section") is True for cell in group["cells"]):
            cells.append(_cell(items, next_row, 0, end_column=len(headers), section=True))
            next_row += 1
            continue
        value_lines = [line for line in lines if any(_column(item, boundaries) in numeric_columns and re.search(r"\d", item["text"]) for item in line)]
        sublines = value_lines if len(value_lines) > 1 else [items]
        row_start = next_row
        if len(sublines) > 1:
            # A label outside a value band can be a common prefix only when it
            # belongs to this same observed parser row group.
            used = {item["id"] for line in sublines for item in line}
            extras = [item for item in items if item["id"] not in used]
            if any(_column(item, boundaries) in numeric_columns for item in extras):
                return None, [], [], ["numeric_subline_alignment_ambiguous"]
            if any(_header_role(headers[_column(item, boundaries)]) not in {"parameter", "symbol"} for item in extras):
                # An unaligned condition/unit gets its own physical row. It is
                # never zipped onto an adjacent value merely by list order.
                sublines = lines
            else:
                sublines[0] = extras + sublines[0]
        emitted = []
        for offset, line in enumerate(sublines):
            by_span: dict[tuple[int, int], list] = {}
            for segment in _horizontal_segments(line):
                start = min(_column_range(item, boundaries)[0] for item in segment)
                end = max(_column_range(item, boundaries)[1] for item in segment)
                # A continuous formula across numeric columns stays merged.
                # Distinct explicit text columns (symbol/parameter/condition)
                # retain their observed boundary even when the words are close.
                if end > start + 1 and not all(column in numeric_columns for column in range(start, end)):
                    for item in segment:
                        first_column, last_column = _column_range(item, boundaries)
                        by_span.setdefault((first_column, last_column), []).append(item)
                else:
                    by_span.setdefault((start, end), []).extend(segment)
            merged_spans: list[tuple[tuple[int, int], list]] = []
            for (start, end), contents in sorted(by_span.items()):
                if merged_spans and start < merged_spans[-1][0][1]:
                    previous_span, previous_contents = merged_spans.pop()
                    merged_spans.append(((previous_span[0], max(previous_span[1], end)), previous_contents + contents))
                else:
                    merged_spans.append(((start, end), contents))
            for (start, end), contents in merged_spans:
                spanning = end > start + 1
                role = _header_role(headers[start]) if not spanning else None
                shared_label = offset == 0 and len(sublines) > 1 and role in {"parameter", "symbol"} and not any(
                    any(_column(item, boundaries) == start for item in other) for other in sublines[1:])
                record = _cell(contents, next_row, start, end_column=end, row_span=len(sublines) if shared_label else 1,
                               row_header=role == "parameter", section=any(c.get("row_section") is True for c in group["cells"]))
                record["_quality_reasons"] = []
                if len(sublines) > 1 and role in _VALUE_ROLES:
                    for required_role in ("unit", "condition"):
                        required_columns = {i for i, candidate in enumerate(headers) if _header_role(candidate) == required_role}
                        if any(_column(item, boundaries) in required_columns for item in items) and not any(
                                _column(item, boundaries) in required_columns for item in line):
                            record["_quality_reasons"].append(f"subline_{required_role}_alignment_missing")
                cells.append(record)
                emitted.append(record)
            next_row += 1
        if len(sublines) > 1:
            for column, header in enumerate(headers):
                if _header_role(header) != "condition":
                    continue
                condition_lines = [[item for item in line if _column(item, boundaries) == column] for line in sublines]
                if any(not line for line in condition_lines):
                    continue
                local_left = min(item["display_bbox"][0] for item in condition_lines[1])
                local = [[item for item in line if item["display_bbox"][0] >= local_left - 2] for line in condition_lines]
                keys = [_condition_key(line) for line in local]
                if any(not line for line in local) or None in keys or len(set(keys)) != 1:
                    continue
                prefix = [item for item in condition_lines[0] if item["display_bbox"][2] < local_left - 2]
                prefix_text = _text(prefix) if prefix else ""
                if not re.fullmatch(r"[^=;]+\s*=\s*[^;]+", prefix_text) or re.search(r"\b(if|when|unless|only|si|sauf)\b", prefix_text, re.I):
                    continue
                origin = next((cell for cell in emitted if cell["start_row_offset_idx"] == row_start and cell["start_col_offset_idx"] == column), None)
                if origin is None or not origin["text"].startswith(prefix_text):
                    continue
                for offset in range(1, len(sublines)):
                    dependencies.append({"row_index": row_start + offset, "kind": "shared_condition", "source_row": row_start,
                                         "source_column": column, "start_offset": 0, "end_offset": len(prefix_text),
                                         "text": prefix_text, "observation_ids": [item["id"] for item in prefix],
                                         "source_parser_row": group["source_row"]})
    if not cells or len(cells) > MAX_TABLE_OBSERVATIONS:
        return None, [], [], ["table_projection_cell_limit"]
    observations_by_id = {item["id"]: item for item in positioned}
    bindings = []
    for cell in cells:
        ids = cell.pop("_observation_ids")
        structural_reasons = cell.pop("_quality_reasons", [])
        scope_bbox = cell.pop("_scope_bbox", None)
        ruled_group = cell.pop("_header_group", None)
        column = cell["start_col_offset_idx"]
        header = headers[column] if cell["col_span"] == 1 else None
        header_observations = header_parts[header["id"]] if header else []
        bound_observations = [observations_by_id[identifier] for identifier in ids]
        checked_observations = bound_observations + header_observations
        valid = not structural_reasons and all(item["state"] == "supported" for item in checked_observations)
        bindings.append({"row": cell["start_row_offset_idx"], "column": column,
                         "row_end": cell["end_row_offset_idx"], "column_end": cell["end_col_offset_idx"],
                         "header_text": _text(header_observations) if header and not cell["column_header"] else None,
                         "header_observation_ids": [item["id"] for item in header_observations] if header and not cell["column_header"] else [],
                         "value_observation_ids": ids, "state": "supported" if valid else "ambiguous",
                         "reasons": sorted({*structural_reasons, *(reason for item in checked_observations for reason in item["reasons"])}) if not valid else []})
        if scope_bbox is not None:
            bindings[-1]["scope_bbox"] = scope_bbox
        if ruled_group is not None:
            bindings[-1]["header_group"] = ruled_group
    if reading_rotation:
        # The extra rotation is only a reading frame. Public parser rectangles
        # and citations remain in the original page frame, never this view.
        reading_page = {**page, "rotation": (int(page["rotation"]) + reading_rotation) % 360}
        frame = normalize_box(page.get("effective_box") or page.get("crop_box"))
        width, height = frame[2] - frame[0], frame[3] - frame[1]
        reading_size = (height, width) if reading_page["rotation"] in {90, 270} else (width, height)
        for cell in cells:
            physical = docling_box_to_pdf(cell["bbox"], reading_size, reading_page)
            cell["bbox"] = pdf_box_to_docling(physical, parser_size, page)
    return {"num_rows": next_row, "num_cols": len(headers), "table_cells": cells}, bindings, dependencies, []


def _pixel_size(value):
    if not isinstance(value, list | tuple) or len(value) != 2 or any(type(size) is not int or size <= 0 for size in value):
        return None
    return tuple(value)


def _same_box(first, second):
    return all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(normalize_box(first), normalize_box(second), strict=True))


def _table_reading_orientation(data, bbox, parser_size, page, cells, quality_readings,
                               orientation_records, preprocessing, table_corrections, source_sha256):
    """Reconstruct a local frame from one real OCR/table correction chain.

    An orientation number alone is not evidence. Require a unique OSD region,
    its preprocessing raster dimensions/hashes, the same-tableformer correction
    and every retained reading's region/raster identity. Recognition uncertainty
    remains independent: a valid frame never promotes a token's text quality.
    """
    unavailable = "table_orientation_witness_incomplete"
    collections = (orientation_records, preprocessing, table_corrections)
    if any(not isinstance(records, list | tuple) or len(records) > 64
           or any(not isinstance(record, dict) for record in records) for records in collections):
        return 0, None, "table_orientation_observation_limit_or_schema"

    def region(record):
        return docling_box_to_pdf(record["parser_bbox"], parser_size, page) if isinstance(record.get("parser_bbox"), dict) else None

    def covers(record):
        box = region(record)
        return box is not None and _inside(bbox, box, tolerance=2)

    orientations = [record for record in orientation_records if covers(record)]
    rasters = [record for record in preprocessing if covers(record)]
    corrections = [record for record in table_corrections if region(record) is not None and _same_box(region(record), bbox)]
    table_cells = [cell for cell in cells if cell.get("from_ocr") and cell.get("text", "").strip()
                   and cell.get("bbox") and _inside(normalize_box(cell["bbox"]), bbox)]
    reading_ids = {identity for cell in table_cells for identity in cell.get("ocr_quality", {}).get("reading_ids", [])}
    readings = [record for record in quality_readings if record.get("reading_id") in reading_ids]
    if not corrections and not any(record.get("orientation_degrees", 0) != 0 for record in [*orientations, *rasters, *readings]):
        return 0, None, None
    if len(corrections) != 1 or len(orientations) != 1 or len(rasters) != 1:
        return 0, None, "table_orientation_region_ambiguous" if any(len(records) > 1 for records in (corrections, orientations, rasters)) else unavailable
    correction, orientation, raster = corrections[0], orientations[0], rasters[0]
    angle = correction.get("orientation_degrees")
    if (type(angle) is not int or angle not in {0, 90, 180, 270}
            or orientation.get("orientation_degrees") != angle or raster.get("orientation_degrees") != angle
            or orientation.get("resolved") is not True or raster.get("orientation_resolved") is not True
            or orientation.get("orientation_convention") != "counterclockwise_from_upright"
            or orientation.get("correction_degrees_pil") != -angle
            or raster.get("coordinate_frame") != "oriented_ocr_region_pixels"
            or correction.get("model") != "same-tableformer-accurate"
            or type(correction.get("cells")) is not int or correction["cells"] != len(data["table_cells"])):
        return 0, None, "table_orientation_correction_mismatch"
    orientation_box, raster_box = region(orientation), region(raster)
    if not _same_box(orientation_box, raster_box):
        return 0, None, "table_orientation_region_mismatch"
    source_size = _pixel_size(orientation.get("source_raster_size"))
    derivative_size = _pixel_size(orientation.get("derivative_raster_size"))
    oriented_size = _pixel_size(raster.get("source_oriented_raster_size"))
    derived_size = _pixel_size(raster.get("derived_oriented_raster_size"))
    if None in (source_size, derivative_size, oriented_size, derived_size):
        return 0, None, unavailable
    if (oriented_size != (source_size[::-1] if angle in {90, 270} else source_size)
            or derived_size != (derivative_size[::-1] if angle in {90, 270} else derivative_size)):
        return 0, None, "table_orientation_raster_dimensions_mismatch"
    scale = raster.get("scale")
    inverse = raster.get("resize_inverse_factors")
    region_index = raster.get("ocr_region_index")
    if (type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0
            or type(region_index) is not int or region_index < 0
            or not isinstance(inverse, list | tuple) or len(inverse) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in inverse)):
        return 0, None, unavailable
    parser_box = raster["parser_bbox"]
    expected_size = (abs(parser_box["r"] - parser_box["l"]) * scale, abs(parser_box["b"] - parser_box["t"]) * scale)
    if (not all(math.isclose(a, b, abs_tol=2) for a, b in zip(source_size, expected_size, strict=True))
            or not all(math.isclose(value, original / resized, abs_tol=1e-9)
                       for value, original, resized in zip(inverse, oriented_size, derived_size, strict=True))):
        return 0, None, "table_orientation_raster_dimensions_mismatch"
    hashes = [orientation.get("osd_raster_sha256"), raster.get("source_raster_sha256"), raster.get("derived_raster_sha256")]
    if any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes):
        return 0, None, unavailable
    if raster.get("osd_raster_sha256") != orientation["osd_raster_sha256"]:
        return 0, None, "table_orientation_osd_raster_mismatch"
    if (not table_cells or not reading_ids or len(readings) != len(reading_ids)
            or any(not cell.get("ocr_quality", {}).get("reading_ids") for cell in table_cells)):
        return 0, None, unavailable
    for reading in readings:
        if (reading.get("coordinate_frame") != "pdf_user_space_unrotated" or reading.get("orientation_degrees") != angle
                or reading.get("ocr_region_index") != region_index or reading.get("scale") != scale
                or reading.get("resize_inverse_factors") != list(inverse)
                or reading.get("source_raster_sha256") != raster["derived_raster_sha256"]
                or _pixel_size(reading.get("source_raster_size")) != derived_size
                or region(reading) is None or not _same_box(region(reading), raster_box)):
            return 0, None, "table_orientation_reading_raster_mismatch"
    orientation_keys = ("orientation_degrees", "resolved", "orientation_convention", "correction_degrees_pil", "parser_bbox",
                        "source_raster_size", "derivative_raster_size", "intrinsic_pixel_size", "osd_raster_sha256")
    raster_keys = ("algorithm", "coordinate_frame", "ocr_region_index", "orientation_degrees", "orientation_resolved", "parser_bbox",
                   "source_oriented_raster_size", "derived_oriented_raster_size", "source_raster_sha256", "derived_raster_sha256",
                   "osd_raster_sha256", "scale", "resize_inverse_factors")
    witness = {"schema_version": TABLE_ORIENTATION_SCHEMA, "source_sha256": source_sha256, "page_index": page["page_index"],
               "table_bbox": bbox, "orientation_degrees": angle, "reading_ids": sorted(reading_ids),
               "region_orientation": {key: copy.deepcopy(orientation[key]) for key in orientation_keys if key in orientation},
               "region_preprocessing": {key: copy.deepcopy(raster[key]) for key in raster_keys if key in raster},
               "table_correction": {key: copy.deepcopy(correction[key]) for key in ("orientation_degrees", "parser_bbox", "model", "cells")}}
    return angle, witness, None


def build_table_quality(data, bbox, parser_size, page, *, native=None, cells=(), quality_readings=(), source_sha256=None,
                        orientation_records=(), preprocessing=(), table_corrections=()):
    """Return canonical data plus a replayable geometry witness, or the raw table."""
    base = {"schema_version": TABLE_QUALITY_SCHEMA, "policy": TABLE_GEOMETRY_POLICY, "state": "unavailable",
            "source_sha256": source_sha256, "page_index": page["page_index"], "observations": [], "bindings": [], "dependencies": []}
    if not bbox or not isinstance(source_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha256):
        return data, {**base, "reasons": ["table_source_identity_or_geometry_missing"]}
    if native is not None and (not isinstance(native, dict) or native.get("schema_version") != "pdfium-glyphs-v1"
                               or native.get("coordinate_frame") != "pdf_user_space_unrotated"
                               or native.get("source_sha256") != source_sha256 or native.get("page_index") != page["page_index"]):
        return data, {**base, "reasons": ["native_observation_identity_mismatch"]}
    try:
        from .source_quality import annotate_ocr_cells

        if (not isinstance(data, dict) or not isinstance(data.get("table_cells"), list)
                or len(data["table_cells"]) > MAX_PARSER_TABLE_CELLS or any(not isinstance(cell, dict) for cell in data["table_cells"])
                or not isinstance(cells, list | tuple) or any(not isinstance(cell, dict) for cell in cells)
                or native is not None and (not isinstance(native.get("glyphs"), list) or len(native["glyphs"]) > MAX_PAGE_GLYPHS
                                          or any(not isinstance(glyph, dict) for glyph in native["glyphs"]))):
            return data, {**base, "reasons": ["table_observation_schema_invalid"]}
        cells = annotate_ocr_cells(cells, quality_readings) if any(cell.get("from_ocr") for cell in cells) else cells
        reading_rotation, orientation_witness, reason = _table_reading_orientation(
            data, bbox, parser_size, page, cells, quality_readings, orientation_records, preprocessing, table_corrections, source_sha256)
        if reason:
            return data, {**base, "reasons": [reason]}
        observations, retained, reason = _spatial_observations(bbox, page, native, cells, reading_rotation)
        if reason:
            return data, {**base, "reasons": [reason]}
        native_subset, ocr_cells = retained
        projected, bindings, dependencies, reasons = _project(data, observations, bbox, parser_size, page, reading_rotation,
                                                            native_subset.get("rules") if native_subset else None)
        if projected is None:
            return data, {**base, "reasons": reasons}
        reading_ids = {identifier for cell in ocr_cells for identifier in cell.get("ocr_quality", {}).get("reading_ids", [])}
        quality = {**base, "state": "supported" if all(binding["state"] == "supported" for binding in bindings) else "partial",
                   "reasons": reasons, "observations": observations, "bindings": bindings, "dependencies": dependencies,
                   "observations_sha256": _digest(observations), "table_data_sha256": _digest(projected),
                   "native_glyphs": native_subset, "ocr_cells": ocr_cells,
                   "ocr_readings": [copy.deepcopy(reading) for reading in quality_readings if reading.get("reading_id") in reading_ids],
                   "table_bbox": bbox,
                   "parser_size": list(parser_size),
                   "page_frame": {key: page[key] for key in ("page_index", "crop_box", "effective_box", "rotation") if key in page}}
        if orientation_witness is not None:
            quality["table_orientation"] = orientation_witness
        if len(json.dumps(quality, ensure_ascii=False).encode()) > MAX_QUALITY_BYTES:
            return data, {**base, "reasons": ["table_quality_byte_limit"]}
        return projected, quality
    except (KeyError, TypeError, ValueError, IndexError, IngestionError):
        return data, {**base, "reasons": ["table_observation_geometry_invalid"]}


def _page_frame_identity(page):
    if (not isinstance(page, dict) or type(page.get("page_index")) is not int
            or type(page.get("rotation")) is not int or page["rotation"] not in {0, 90, 180, 270}):
        return None
    return {"page_index": page["page_index"], "rotation": page["rotation"],
            "crop_box": normalize_box(page["crop_box"]) if page.get("crop_box") is not None else None,
            "effective_box": normalize_box(page.get("effective_box") or page["crop_box"])}


def validate_table_quality(text, metadata, *, source_sha256, page_index,
                           page=_UNSUPPLIED_FRAME, table_bbox=_UNSUPPLIED_FRAME):
    """Replay a witness from catalogue metadata, never from a retrieval boolean.

    Runtime callers supply source identity, page frame and block rectangle from
    their authorized DB join. Explicitly missing geometry fails closed. Isolated
    witness tests may omit the external geometry, but this grants no runtime
    scope; offsets and visible dependencies remain answer-catalogue checks.
    """
    unavailable = {"state": "unavailable", "bindings": [], "cells": {}, "dependencies": [], "reasons": ["table_quality_unavailable"]}
    nested = metadata.get("metadata", metadata) if isinstance(metadata, dict) else {}
    quality = nested.get("table_quality")
    if not isinstance(quality, dict) or quality.get("schema_version") != TABLE_QUALITY_SCHEMA or quality.get("policy") != TABLE_GEOMETRY_POLICY:
        return unavailable
    if quality.get("source_sha256") != source_sha256 or type(page_index) is not int or quality.get("page_index") != page_index:
        return {**unavailable, "reasons": ["table_quality_identity_mismatch"]}
    if quality.get("state") == "unavailable":
        return {**unavailable, "reasons": quality.get("reasons", unavailable["reasons"])}
    try:
        if len(json.dumps(quality, ensure_ascii=False).encode()) > MAX_QUALITY_BYTES:
            return {**unavailable, "reasons": ["table_quality_byte_limit"]}
        if page is not _UNSUPPLIED_FRAME:
            registered_frame = _page_frame_identity(page)
            if (registered_frame is None or registered_frame != _page_frame_identity(quality.get("page_frame"))
                    or page.get("source_sha256") is not None and page["source_sha256"] != source_sha256):
                return {**unavailable, "reasons": ["table_quality_page_frame_mismatch"]}
        if table_bbox is not _UNSUPPLIED_FRAME and (table_bbox is None or not _same_box(table_bbox, quality.get("table_bbox"))):
            return {**unavailable, "reasons": ["table_quality_bbox_mismatch"]}
        orientation = quality.get("table_orientation")
        if orientation is not None and (not isinstance(orientation, dict) or orientation.get("schema_version") != TABLE_ORIENTATION_SCHEMA
                                        or orientation.get("source_sha256") != source_sha256 or orientation.get("page_index") != page_index):
            return {**unavailable, "reasons": ["table_orientation_identity_mismatch"]}
        data, rebuilt = build_table_quality(nested["parser_table_data"], quality["table_bbox"], quality["parser_size"], quality["page_frame"],
                                           native=quality.get("native_glyphs"), cells=quality.get("ocr_cells", []),
                                           quality_readings=quality.get("ocr_readings", []), source_sha256=source_sha256,
                                           orientation_records=[orientation["region_orientation"]] if orientation else (),
                                           preprocessing=[orientation["region_preprocessing"]] if orientation else (),
                                           table_corrections=[orientation["table_correction"]] if orientation else ())
        if rebuilt != quality or data != nested.get("table_data"):
            return {**unavailable, "reasons": ["table_quality_replay_mismatch"]}
        rows: dict[int, list] = {}
        for cell in data["table_cells"]:
            rows.setdefault(cell["start_row_offset_idx"], []).append((cell["start_col_offset_idx"], cell["text"]))
        rebuilt_text = "\n".join(" | ".join(value for _, value in sorted(rows[row])) for row in sorted(rows))
        if rebuilt_text != text:
            return {**unavailable, "reasons": ["table_quality_text_mismatch"]}
        return {"state": quality["state"], "bindings": quality["bindings"],
                "cells": {(binding["row"], binding["column"]): binding for binding in quality["bindings"]},
                "dependencies": quality["dependencies"], "reasons": quality["reasons"]}
    except (KeyError, TypeError, ValueError, IndexError, IngestionError):
        return {**unavailable, "reasons": ["table_quality_invalid"]}


def native_condition_projection(text, bbox, page, native, source_sha256):
    """Reassemble an explicit condition band from its real native glyphs only.

    This corrects parser duplication, not a guessed mathematical symbol. An
    unmapped glyph or incomplete observation leaves the parser reading visible
    with an unavailable witness, so the publication boundary can refuse it.
    """
    if not native or not bbox or not _GENERAL_QUALIFIER.search(_fold(text)) or "=" not in text:
        return text, None
    base = {"schema_version": "native-condition-projection-v1", "state": "unavailable", "source_sha256": source_sha256,
            "page_index": page["page_index"], "source_bbox": bbox, "input_text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    if not isinstance(native, dict) or native.get("source_sha256") != source_sha256 or native.get("page_index") != page["page_index"]:
        return text, {**base, "reasons": ["native_condition_identity_mismatch"]}
    try:
        observations, retained, reason = _spatial_observations(bbox, page, native, [])
        if reason or any(item["state"] != "supported" for item in observations):
            return text, {**base, "reasons": [reason or "native_condition_glyph_uncertain"]}
        positioned = [{**item, "display_bbox": _display_box(item["bbox"], page)} for item in observations]
        projected = _text(positioned)
        if (not _GENERAL_QUALIFIER.search(_fold(projected)) or "=" not in projected
                or len(projected) > MAX_GENERAL_CHARS):
            return text, {**base, "reasons": ["native_condition_projection_incomplete"]}
        witness = {**base, "state": "supported", "reasons": [], "native_glyphs": retained[0], "observations": observations,
                   "page_frame": {key: page[key] for key in ("page_index", "crop_box", "effective_box", "rotation") if key in page},
                   "output_text_sha256": hashlib.sha256(projected.encode()).hexdigest()}
        witness["sha256"] = _digest(witness)
        return projected, witness
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, IngestionError):
        return text, {**base, "reasons": ["native_condition_projection_invalid"]}


def validate_native_condition_projection(text, metadata, *, source_sha256, page_index):
    witness = metadata.get("native_condition_projection") if isinstance(metadata, dict) else None
    failure = {"state": "unavailable", "reasons": ["native_condition_witness_invalid"]}
    if not isinstance(witness, dict) or witness.get("schema_version") != "native-condition-projection-v1":
        return failure
    if witness.get("source_sha256") != source_sha256 or witness.get("page_index") != page_index:
        return failure
    if witness.get("state") == "unavailable":
        return {**failure, "reasons": witness.get("reasons", failure["reasons"])}
    try:
        if len(json.dumps(witness, ensure_ascii=False).encode()) > MAX_QUALITY_BYTES:
            return failure
        projected, rebuilt = native_condition_projection(metadata["parser_original_text"], witness["source_bbox"], witness["page_frame"],
                                                        witness["native_glyphs"], source_sha256)
        if projected != text or rebuilt != witness:
            return failure
        return {"state": "supported", "reasons": []}
    except (KeyError, TypeError, ValueError, IndexError):
        return failure


def _block_text(block):
    return block.get("raw_text", block.get("text", ""))


def _seal_general(annotation):
    try:
        return {**annotation, "sha256": _digest(annotation)}
    except (TypeError, ValueError):
        safe = {"schema_version": GENERAL_CONDITIONS_SCHEMA, "policy": GENERAL_CONDITIONS_POLICY,
                "state": "unavailable", "pieces": [], "reasons": ["general_condition_nonfinite_or_invalid_metadata"]}
        return {**safe, "sha256": _digest(safe)}


def _general_line_pieces(candidates, pieces):
    """Group only disjoint, closely spaced fragments sharing a vertical band.

    Each source fragment stays independently addressable. A tall fragment that
    could belong to two lines, overlapping horizontal boxes, or more than eight
    resulting pieces cannot be repaired by concatenating the source text.
    """
    if any(not box[0] < box[2] or not box[1] < box[3] for box, _ in candidates):
        return None
    lines: list[dict[str, Any]] = []
    for box, block in sorted(candidates, key=lambda pair: ((pair[0][1] + pair[0][3]) / 2, pair[0][0])):
        height = box[3] - box[1]
        matches = [line for line in lines
                   if min(line["bottom"], box[3]) - max(line["top"], box[1]) >= .5 * min(line["height"], height)]
        if len(matches) > 1:
            return None
        if matches:
            line = matches[0]
            line.update(top=max(line["top"], box[1]), bottom=min(line["bottom"], box[3]),
                        height=min(line["height"], height))
            line["members"].append((box, block))
        else:
            lines.append({"top": box[1], "bottom": box[3], "height": height, "members": [(box, block)]})
    lines.sort(key=lambda line: (line["top"], line["bottom"]))
    if any(first["bottom"] > second["top"] for first, second in zip(lines, lines[1:], strict=False)):
        return None
    # Recheck after all rows exist: an early tall box must not bridge two rows.
    for box, _ in candidates:
        if sum(min(line["bottom"], box[3]) - max(line["top"], box[1]) >= .5 * min(line["height"], box[3] - box[1])
               for line in lines) != 1:
            return None
    by_id = {piece["block_id"]: piece for piece in pieces}
    grouped = []
    for line in lines:
        runs: list[list[tuple[list[float], dict[str, Any]]]] = []
        for box, block in sorted(line["members"], key=lambda pair: pair[0][0]):
            if runs:
                previous = runs[-1][-1][0]
                gap = box[0] - previous[2]
                if gap < 0:
                    return None
                # Local glyph height bounds a word gap; separate columns stay
                # separate pieces even when their baselines happen to coincide.
                maximum_gap = min(16., max(2., 1.5 * min(box[3] - box[1], previous[3] - previous[1])))
                if gap <= maximum_gap:
                    runs[-1].append((box, block))
                    continue
            runs.append([(box, block)])
        for run in runs:
            fragments = [by_id[block["id"]] for _, block in run]
            if len(fragments) == 1:
                grouped.append(fragments[0])
            else:
                grouped.append({"kind": "line_fragments", "page_index": fragments[0]["page_index"],
                                "bbox": _union([fragment["bbox"] for fragment in fragments]),
                                "display_bbox": _union([box for box, _ in run]), "fragments": fragments})
    return grouped if len(grouped) <= MAX_GENERAL_PIECES else None


def table_general_condition_fragments(annotation):
    """Flatten only an already reconstructed condition annotation for callers.

    This helper is not an authority check. Call validate_table_general_conditions
    first, then keep each returned original's scope, hash and reading gates.
    """
    if (not isinstance(annotation, dict) or annotation.get("state") != "supported"
            or annotation.get("schema_version") not in {GENERAL_CONDITIONS_SCHEMA, GENERAL_CONDITION_LINES_SCHEMA}
            or not isinstance(annotation.get("pieces"), list) or not 0 < len(annotation["pieces"]) <= MAX_GENERAL_PIECES):
        return []
    fragments = []
    for piece in annotation["pieces"]:
        if not isinstance(piece, dict):
            return []
        if piece.get("kind") == "line_fragments":
            if (annotation["schema_version"] != GENERAL_CONDITION_LINES_SCHEMA
                    or not isinstance(piece.get("fragments"), list) or not 2 <= len(piece["fragments"]) <= MAX_GENERAL_BLOCKS):
                return []
            originals = piece["fragments"]
        else:
            if "fragments" in piece:
                return []
            originals = [piece]
        if any(not isinstance(fragment, dict) or "fragments" in fragment
               or not {"block_id", "text", "start_offset", "end_offset", "source_text_hash", "bbox",
                       "version_id", "extraction_revision_id", "page_index", "type"} <= fragment.keys()
               for fragment in originals):
            return []
        fragments.extend(originals)
        if len(fragments) > MAX_GENERAL_BLOCKS:
            return []
    return fragments


def build_table_general_conditions(table, blocks, page, *, source_sha256):
    """Describe only an explicit pre-table condition band on this same page.

    Supported means that the spatial association is justified. Each fragment's
    reading quality and the caller's version/span scope remain separate gates.
    Absent means no explicit band was established, never absence in the PDF.
    """
    base = {"schema_version": GENERAL_CONDITIONS_SCHEMA, "policy": GENERAL_CONDITIONS_POLICY,
            "state": "unavailable", "support_scope": "geometric_binding_only", "source_sha256": source_sha256,
            "page_index": page.get("page_index"), "table_block_id": table.get("id"),
            "table_source_text_hash": table.get("source_text_hash"), "table_bbox": table.get("bbox"), "pieces": []}
    if (not isinstance(blocks, list | tuple) or len(blocks) > MAX_GENERAL_BLOCKS or not table.get("bbox")
            or not isinstance(source_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha256)
            or table.get("page_index") != page.get("page_index")):
        return _seal_general({**base, "reasons": ["general_condition_identity_or_limit"]})
    try:
        table_text_value = _block_text(table)
        if hashlib.sha256(table_text_value.encode()).hexdigest() != table.get("source_text_hash"):
            return _seal_general({**base, "reasons": ["general_condition_table_hash_mismatch"]})
        table_box = _display_box(table["bbox"], page)
        metadata = table.get("metadata", {})
        headers = [observation for observation in metadata.get("table_quality", {}).get("observations", [])
                   if _fold(observation.get("text", "")) in _ROLES]
        heights = [(_display_box(item["bbox"], page)[3] - _display_box(item["bbox"], page)[1]) for item in headers if item.get("bbox")]
        maximum_gap = min(48.0, max(16.0, 4 * statistics.median(heights))) if heights else 32.0
        candidates = []
        for block in blocks:
            if (block.get("id") == table.get("id") or block.get("type", block.get("kind")) not in {"heading", "text", "caption"}
                    or block.get("page_index") != page.get("page_index") or not block.get("bbox") or not _block_text(block).strip()):
                continue
            box = _display_box(block["bbox"], page)
            gap = table_box[1] - box[3]
            if not (-1 <= gap <= maximum_gap and box[0] >= table_box[0] - 2 and box[2] <= table_box[2] + 2):
                continue
            obstructed = False
            for other in blocks:
                if other.get("id") == table.get("id") or other.get("type", other.get("kind")) != "table" or not other.get("bbox"):
                    continue
                obstacle = _display_box(other["bbox"], page)
                if (box[3] <= obstacle[1] <= obstacle[3] <= table_box[1]
                        and min(obstacle[2], box[2]) > max(obstacle[0], box[0])):
                    obstructed = True
                    break
            if not obstructed:
                candidates.append((box, block))
        combined = " ".join(_block_text(block) for _, block in sorted(candidates, key=lambda pair: (pair[0][1], pair[0][0])))
        named_header = any(block.get("type", block.get("kind")) == "heading" and _GENERAL_HEADER.search(_fold(_block_text(block)))
                           for _, block in candidates)
        if not named_header or not _GENERAL_QUALIFIER.search(_fold(combined)) or "=" not in combined:
            return _seal_general({**base, "state": "absent", "reasons": ["explicit_general_condition_band_not_established"]})
        if len(combined) > MAX_GENERAL_CHARS:
            return _seal_general({**base, "reasons": ["general_condition_band_limit"]})
        pieces = []
        identities = set()
        for _, block in sorted(candidates, key=lambda pair: (pair[0][1], pair[0][0])):
            text_value = _block_text(block)
            if (not isinstance(block.get("id"), str) or block["id"] in identities
                    or not isinstance(table.get("version_id"), str) or not isinstance(table.get("extraction_revision_id"), str)
                    or block.get("version_id") != table.get("version_id")
                    or block.get("extraction_revision_id") != table.get("extraction_revision_id")
                    or block.get("source_text_hash") != hashlib.sha256(text_value.encode()).hexdigest()):
                return _seal_general({**base, "reasons": ["general_condition_fragment_integrity"]})
            identities.add(block["id"])
            pieces.append({"block_id": block["id"], "page_index": block["page_index"], "text": text_value,
                           "start_offset": 0, "end_offset": len(text_value), "source_text_hash": block["source_text_hash"],
                           "bbox": block["bbox"], "type": block.get("type", block.get("kind")),
                           "version_id": block.get("version_id"), "extraction_revision_id": block.get("extraction_revision_id")})
        if len(pieces) > MAX_GENERAL_PIECES:
            grouped = _general_line_pieces(candidates, pieces)
            if grouped is None:
                return _seal_general({**base, "reasons": ["general_condition_band_limit"]})
            return _seal_general({**base, "schema_version": GENERAL_CONDITION_LINES_SCHEMA,
                                  "policy": GENERAL_CONDITION_LINES_POLICY, "state": "supported",
                                  "pieces": grouped, "reasons": []})
        return _seal_general({**base, "state": "supported", "pieces": pieces, "reasons": []})
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, IngestionError):
        return _seal_general({**base, "reasons": ["general_condition_geometry_invalid"]})


def validate_table_general_conditions(table, blocks, page, *, source_sha256):
    """Reconstruct the stored annotation from the caller's authorized DB rows."""
    metadata = table.get("metadata", {})
    supplied = metadata.get("table_general_conditions") if isinstance(metadata, dict) else None
    failure = {"schema_version": GENERAL_CONDITIONS_SCHEMA, "state": "unavailable", "pieces": [],
               "reasons": ["general_condition_witness_missing_or_changed"], "table_block_id": table.get("id")}
    if not isinstance(supplied, dict):
        return failure
    expected = build_table_general_conditions(table, blocks, page, source_sha256=source_sha256)
    if supplied != expected:
        return failure
    return expected
