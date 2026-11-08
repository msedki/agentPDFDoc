"""Numeric OCR ambiguity evidence; never synthesize a replacement reading.

Only an earlier, geometrically aligned min/max/typical header establishes a
numeric role. Ambiguous letters/signs can request the existing bounded row OCR.
Raw/candidate tokens and the actual OCR crop stay in private extraction data,
separate from operational traces, which contain no document text.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUMERIC_POLICY = "numeric_header_ambiguity_row_v3"
NUMERIC_DENSITY_FACTOR = 2
NUMERIC_DENSITY_MAX_INK_HEIGHT = 24
SNAPSHOT_MAX_BYTES = 256 * 1024
SNAPSHOTS_MAX_BYTES = 2 * 1024 * 1024
NUMERIC_HEADERS = {
    "min": "minimum", "minimum": "minimum", "max": "maximum", "maximum": "maximum",
    "typ": "typical", "typical": "typical", "typique": "typical", "nom": "nominal", "nominal": "nominal",
}
# Deliberately narrow: no component codes, addresses, ranges or invented unit.
_UNIT = r"(?:[pnumkMGTµμ]?(?:V|A|Ω|Ohm|W|Hz|s|m|g|F|H|Pa|J|N)|°C|K|%|bar)?"
_LITERAL = re.compile(r"(?P<sign>[+\-−±–—]?)\s*(?P<number>[0-9Oo]+(?:[.,][0-9Oo]+)?(?:[eE][+\-]?[0-9]+)?)\s*(?P<unit>" + _UNIT + r")")


def literal(frame) -> str:
    return " ".join(str(value) for value in frame["text"])


def numeric_ambiguities(text: str) -> tuple[str, ...]:
    """Recognize ambiguous syntax only; a probable 0 is not returned as text."""
    match = _LITERAL.fullmatch(text.strip())
    if match is None:
        return ()
    issues = []
    if "o" in match["number"].lower():
        issues.append("letter_o_in_numeric_field")
    if match["sign"] in {"–", "—"}:
        issues.append("ambiguous_dash_sign")
    return tuple(issues)


def numeric_candidate_admissible(raw: str, candidate: str) -> bool:
    """Require actual OCR plus agreement of unaffected digits, sign and unit.

    Canonicalization is used only to reject inconsistent candidates. The caller
    publishes the OCR tokens themselves and keeps the original reading.
    """
    first, second = _LITERAL.fullmatch(raw.strip()), _LITERAL.fullmatch(candidate.strip())
    if first is None or second is None or not numeric_ambiguities(raw) or numeric_ambiguities(candidate):
        return False
    if first["unit"] != second["unit"]:
        return False
    signs = {"−": "-", "–": "-", "—": "-", "+": ""}
    if signs.get(first["sign"], first["sign"]) != signs.get(second["sign"], second["sign"]):
        return False
    try:
        before = Decimal(first["number"].replace("O", "0").replace("o", "0").replace(",", "."))
        after = Decimal(second["number"].replace(",", "."))
    except InvalidOperation:
        return False
    return before == after


def numeric_cell_contexts(cells, baselines, rows, threshold) -> dict[int, dict[str, Any]]:
    """Discover explicit numeric column headers inside one established grid."""
    from .regional_grid import _minimum_cell_confidence

    headers: dict[tuple[int, int], dict[str, Any]] = {}
    result: dict[int, dict[str, Any]] = {}
    if threshold is None or not math.isfinite(threshold):
        return result
    for indices in rows:
        readings = [(index, literal(baselines[index]), _minimum_cell_confidence(baselines[index])) for index in indices]
        corroborating = [index for index, text, confidence in readings
                         if NUMERIC_HEADERS.get(text.strip().rstrip(".").casefold()) in {"minimum", "maximum", "typical"}
                         and confidence is not None and confidence >= threshold]
        for index, text, confidence in readings:
            label = text.strip().rstrip(".").casefold()
            role = NUMERIC_HEADERS.get(label)
            span = (cells[index][0], cells[index][2])
            if role:
                # A newly observed but unqualified header invalidates the old
                # binding. Never carry MIN from an earlier section through a
                # low-confidence MAX/NOM reading into subsequent numeric cells.
                headers.pop(span, None)
                # "Nom" can mean a French name, so the abbreviation alone is
                # insufficient. Require another qualified numeric header in
                # this same established grid row, independent of cell values.
                if confidence is not None and confidence >= threshold and (label != "nom" or corroborating):
                    headers[span] = {"role": role, "header_cell_index": index,
                                     "header_text": text, "header_raster_bbox": list(cells[index])}
                    if label == "nom":
                        headers[span]["corroborating_header_cell_indices"] = list(corroborating)
            elif span in headers and numeric_ambiguities(text):
                result[index] = {**headers[span], "ambiguities": list(numeric_ambiguities(text))}
    return result


def token_records(frame) -> list[dict[str, Any]]:
    records = []
    for word in frame.itertuples(index=False):
        record: dict[str, Any] = {"text": str(word.text)}
        for field in ("conf", "left", "top", "width", "height"):
            value = float(getattr(word, field))
            record[field] = value if math.isfinite(value) else None
        records.append(record)
    return records


def private_row_record(indices, contexts, cells, baselines, trace) -> dict[str, Any]:
    """Raw/candidate text is private evidence, never an operational log field."""
    return {
        "policy": NUMERIC_POLICY, "coordinate_frame": "oriented_ocr_region_pixels",
        "cells": [{"cell_index": index, "raster_bbox": list(cells[index]), **contexts[index],
                   "raw_tokens": token_records(baselines[index]), "raw_text": literal(baselines[index])}
                  for index in indices if index in contexts],
        "candidate_tokens": None, "candidate_coordinate_frame": "row_context_crop_pixels",
        "ocr_parameters": {"psm": 6, "density_factor": 1, "same_engine_and_languages": True},
        "decision": trace,
    }


def numeric_density_patch(patch, trace, budget, max_width: int, max_height: int, *, factor: int = 1):
    """One alternative for small numeric glyphs; no second recognition call."""
    from PIL import Image

    trace["numeric_policy"] = NUMERIC_POLICY
    if factor == 1:
        trace["numeric_density_state"] = "native_density_selected"
        return patch
    if trace["ink_height"] > NUMERIC_DENSITY_MAX_INK_HEIGHT:
        trace["numeric_density_state"] = "native_density_large_glyphs"
        return patch
    size = (patch.width * NUMERIC_DENSITY_FACTOR, patch.height * NUMERIC_DENSITY_FACTOR)
    trace.update(numeric_density_size=list(size), numeric_density_ink_height_limit=NUMERIC_DENSITY_MAX_INK_HEIGHT)
    if size[0] > max_width or size[1] > max_height:
        trace["reason"] = "numeric_density_dimensions_limit"
        return None
    if not budget.reserve(size[0] * size[1], trace):
        return None
    derived = patch.resize(size, Image.Resampling.LANCZOS)
    trace.update(factor=NUMERIC_DENSITY_FACTOR, numeric_density_state="derived",
                 numeric_density_sha256=hashlib.sha256(derived.tobytes()).hexdigest(), resampling="LANCZOS",
                 cumulative_crop_pixels=budget.pixels)
    return derived


def capture_private_raster(record: dict[str, Any], image, used_bytes: int) -> int:
    """Retain the actual bounded OCR input, with explicit omitted-state at cap."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    record["raster_size"] = list(image.size)
    record["raster_png_sha256"] = hashlib.sha256(png).hexdigest()
    if len(png) > SNAPSHOT_MAX_BYTES or used_bytes + len(png) > SNAPSHOTS_MAX_BYTES:
        record["raster_capture_state"] = "snapshot_byte_limit"
        return used_bytes
    record["raster_png_base64"] = base64.b64encode(png).decode("ascii")
    record["raster_capture_state"] = "captured"
    return used_bytes + len(png)
