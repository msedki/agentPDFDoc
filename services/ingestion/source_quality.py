"""Reconstruct bounded OCR agreement from literal observations, never a score flag.

Agreement of two segmentations is evidence about a reading, not a guarantee of
semantic correctness. Disagreements remain local and raw text is never repaired
here. The API rechecks this witness against its pinned block before using it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any

SCHEMA = "ocr-source-quality-v1"
READING_POLICY = "ocr-geometric-agreement-v1"
SIGN_POLICY = "leading-plus-raster-v2"
UNSCALED_RECHECK_POLICY = "literal-agreement-unscaled-recheck-v1"
MAX_TEXT = 200_000
MAX_TOKENS = 4096
MAX_READINGS = 256
MAX_READING_TOKENS = 256


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def valid_box(box: Any) -> bool:
    return (isinstance(box, list | tuple) and len(box) == 4
            and all(type(value) in (int, float) and math.isfinite(value) for value in box)
            and box[0] < box[2] and box[1] < box[3])


def overlap(first: Any, second: Any) -> float:
    if not valid_box(first) or not valid_box(second):
        return 0.0
    area = (first[2] - first[0]) * (first[3] - first[1])
    intersection = max(0., min(first[2], second[2]) - max(first[0], second[0])) * max(
        0., min(first[3], second[3]) - max(first[1], second[1]))
    return intersection / area


def _confidence(token: dict, minimum: float) -> bool:
    value = token.get("confidence")
    return (isinstance(value, int | float) and not isinstance(value, bool)
            and math.isfinite(value) and minimum <= value <= 1)


def can_recheck_unscaled(record: dict, assessment: dict) -> bool:
    """Only a low score may trigger a recheck, never a competing reading."""
    candidates = record.get("candidate_tokens")
    parameters = record.get("parameters")
    return (isinstance(parameters, dict) and parameters.get("factor") == 2
            and assessment.get("reasons") == ["candidate_low_or_invalid_confidence"]
            and isinstance(candidates, list) and bool(candidates)
            and all(isinstance(token, dict) and _confidence(token, 0.) for token in candidates))


def assess_reading(record: dict) -> dict:
    """Recompute each token's agreement; an asserted state is not authority."""
    baseline, candidate = record.get("baseline_tokens"), record.get("candidate_tokens")
    threshold = record.get("minimum_confidence", .8)
    if (record.get("policy") != READING_POLICY or not isinstance(baseline, list)
            or not 0 < len(baseline) <= MAX_READING_TOKENS or type(threshold) not in (int, float)
            or not math.isfinite(threshold) or not .8 <= threshold <= 1
            or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("source_raster_sha256", "")))
            or candidate is not None and not re.fullmatch(r"[a-f0-9]{64}", str(record.get("candidate_raster_sha256", "")))
            or not isinstance(record.get("parameters"), dict)
            or record["parameters"].get("psm") != 6 or record["parameters"].get("factor") not in (1, 2)):
        return {"state": "unavailable", "reasons": ["invalid_reading_witness"], "tokens": []}
    candidates = candidate if isinstance(candidate, list) and len(candidate) <= MAX_READING_TOKENS else []
    prior = record.get("prior_candidate")
    recheck = record.get("unscaled_recheck")
    if prior is None and isinstance(recheck, dict) and recheck.get("status") == "completed":
        return {"state": "unavailable", "reasons": ["invalid_unscaled_recheck_witness"], "tokens": []}
    if prior is not None:
        if (not isinstance(prior, dict) or set(prior) != {"candidate_tokens", "candidate_raster_sha256", "candidate_raster_size", "parameters"}
                or not isinstance(recheck, dict) or recheck.get("policy") != UNSCALED_RECHECK_POLICY
                or recheck.get("status") != "completed" or record["parameters"].get("factor") != 1
                or prior.get("candidate_raster_sha256") == record.get("candidate_raster_sha256")):
            return {"state": "unavailable", "reasons": ["invalid_unscaled_recheck_witness"], "tokens": []}
        selected_size = record.get("candidate_raster_size")
        prior_size = prior.get("candidate_raster_size")
        if (not isinstance(selected_size, list) or not isinstance(prior_size, list)
                or any(len(size) != 2 or any(type(side) is not int or side <= 0 for side in size)
                       for size in (selected_size, prior_size))
                or prior_size != [side * 2 for side in selected_size]):
            return {"state": "unavailable", "reasons": ["invalid_unscaled_recheck_witness"], "tokens": []}
        first = {key: value for key, value in record.items() if key not in {"prior_candidate", "unscaled_recheck"}}
        first.update(prior)
        first_assessment = assess_reading(first)
        if not can_recheck_unscaled(first, first_assessment):
            return {"state": "unavailable", "reasons": ["invalid_unscaled_recheck_witness"], "tokens": []}
    tokens: list[dict[str, Any]] = []
    paired_candidates: list[int] = []
    for token in baseline:
        if not isinstance(token, dict):
            return {"state": "unavailable", "reasons": ["invalid_reading_witness"], "tokens": []}
        text, box = token.get("text"), token.get("bbox")
        reasons = []
        if not isinstance(text, str) or not text.strip() or not valid_box(box):
            reasons.append("invalid_token_geometry_or_literal")
        if not _confidence(token, threshold):
            reasons.append("baseline_low_or_invalid_confidence")
        matches = [index for index, item in enumerate(candidates)
                   if isinstance(item, dict) and item.get("text") == text
                   and overlap(box, item.get("bbox")) >= .5 and overlap(item.get("bbox"), box) >= .5]
        if len(matches) != 1:
            reasons.append("reading_missing_or_disagrees" if not matches else "ambiguous_reading_alignment")
        else:
            paired_candidates.append(matches[0])
            if not _confidence(candidates[matches[0]], threshold):
                reasons.append("candidate_low_or_invalid_confidence")
        if token.get("visual_ambiguities"):
            reasons.extend(str(reason) for reason in token["visual_ambiguities"])
        if (isinstance(text, str) and text.startswith("+")
                and (token.get("visual_sign_check") != "cross_only"
                     or token.get("visual_sign_policy") != SIGN_POLICY)):
            reasons.append("leading_plus_shape_unverified")
        tokens.append({"text": text, "bbox": box, "confidence": token.get("confidence"),
                       "state": "uncertain" if reasons else "corroborated", "reasons": sorted(set(reasons))})
    # The second reading must not add a negation, sign or qualification that the
    # first one omitted. Agreement is a bijection, not a baseline-only subset.
    # An unmatched extra token can change the meaning of the whole line.
    pair_reasons = []
    if len(set(paired_candidates)) != len(paired_candidates):
        pair_reasons.append("nonunique_reading_pairing")
    if set(paired_candidates) != set(range(len(candidates))):
        pair_reasons.append("candidate_has_unmatched_tokens")
    if pair_reasons:
        for token in tokens:
            token["state"] = "uncertain"
            token["reasons"] = sorted(set(token["reasons"] + pair_reasons))
    state = "corroborated" if all(token["state"] == "corroborated" for token in tokens) else "uncertain"
    if not candidates:
        state = "unavailable"
    return {"state": state, "reasons": sorted({reason for token in tokens for reason in token["reasons"]}),
            "tokens": tokens}


def canonical_quality_readings(raw_readings, parser_size, page):
    """Map actual parser rectangles, rejecting unknown coordinate conventions."""
    from .errors import IngestionError
    from .geometry import docling_box_to_pdf

    if not isinstance(raw_readings, list) or len(raw_readings) > MAX_READINGS:
        return []
    output = []
    for raw in raw_readings:
        if not isinstance(raw, dict) or raw.get("coordinate_frame") != "parser_top_left":
            continue
        record = copy.deepcopy(raw)
        try:
            token_sets = [(record, "baseline_tokens"), (record, "candidate_tokens")]
            if isinstance(record.get("prior_candidate"), dict):
                token_sets.append((record["prior_candidate"], "candidate_tokens"))
            for owner, name in token_sets:
                tokens = owner.get(name)
                if tokens is None and name == "candidate_tokens":
                    continue
                if not isinstance(tokens, list) or len(tokens) > MAX_TOKENS:
                    raise ValueError("Invalid OCR token collection")
                for token in tokens:
                    token["bbox"] = docling_box_to_pdf(token["bbox"], parser_size, page)
                    if not valid_box(token["bbox"]):
                        raise ValueError("Invalid OCR token bounds")
                    confidence = token.get("confidence")
                    if type(confidence) not in (int, float) or not math.isfinite(confidence):
                        token["confidence"] = None
            record["coordinate_frame"] = "pdf_user_space_unrotated"
            result = assess_reading(record)
            record.update(state=result["state"], reasons=result["reasons"])
            output.append(record)
        except (IngestionError, KeyError, TypeError, ValueError):
            continue
    return output


def annotate_ocr_cells(cells, canonical_readings):
    """Join observed OCR words by literal and geometry, never nearby text alone."""
    observations: list[dict[str, Any]] = []
    for record in canonical_readings:
        if not isinstance(record, dict) or not isinstance(record.get("reading_id"), str):
            continue
        observations.extend({**token, "reading_id": record["reading_id"]}
                            for token in assess_reading(record)["tokens"])
    result = []
    for original in cells:
        cell = copy.deepcopy(original)
        if not cell.get("from_ocr"):
            result.append(cell)
            continue
        aligned = [item for item in observations if overlap(item["bbox"], cell.get("bbox")) >= .5
                   and overlap(cell.get("bbox"), item["bbox"]) >= .5]
        matched = [item for item in aligned if item["text"] == cell.get("text")]
        conflicting = any(item["text"] != cell.get("text") for item in aligned)
        # Two overlapping observations from two different regions must not vote
        # away a disagreement. Every matching occurrence must agree.
        state = ("corroborated" if matched and not conflicting and all(item["state"] == "corroborated" for item in aligned)
                 else "uncertain" if aligned else "unavailable")
        reasons = sorted({reason for item in aligned for reason in item["reasons"]})
        if conflicting:
            reasons.append("overlapping_readings_disagree")
        if not matched:
            reasons.append("no_aligned_reading")
        cell["ocr_quality"] = {"state": state, "reading_ids": sorted({item["reading_id"] for item in aligned}),
                               "reasons": reasons}
        result.append(cell)
    return result


def _ordered_intervals(text, cells, page):
    """Bind repeated words only when a complete geometric reading matches.

    Matching a bag of words cannot locate which repeated occurrence is uncertain.
    Here all observed words in a horizontal prose block must reproduce the whole
    registered text, in an unambiguous row/column order, before pairing offsets.
    Unknown layouts fall back to the conservative occurrence-counting route.
    """
    from .errors import IngestionError
    from .geometry import normalize_box, pdf_box_to_docling

    if not isinstance(page, dict) or not cells:
        return None
    try:
        frame = normalize_box(page.get("effective_box") or page["crop_box"])
        width, height = frame[2] - frame[0], frame[3] - frame[1]
        size = (height, width) if int(page["rotation"]) % 360 in {90, 270} else (width, height)
        positioned = []
        for cell in cells:
            if not isinstance(cell.get("text"), str) or not cell["text"].strip() or not valid_box(cell.get("bbox")):
                return None
            box = pdf_box_to_docling(cell["bbox"], size, page)
            positioned.append((cell, [box["l"], box["t"], box["r"], box["b"]]))
        rows: list[list[tuple[dict, list[float]]]] = []
        for cell, box in sorted(positioned, key=lambda item: ((item[1][1] + item[1][3]) / 2, item[1][0])):
            middle, height = (box[1] + box[3]) / 2, box[3] - box[1]
            candidates = [index for index in range(max(0, len(rows) - 16), len(rows))
                          if all(abs((other[1] + other[3]) / 2 - middle) <= min(height, other[3] - other[1]) * .4
                                 for _, other in rows[index])]
            if len(candidates) > 1:
                return None
            if candidates:
                rows[candidates[0]].append((cell, box))
            else:
                rows.append([(cell, box)])
        ordered: list[dict] = []
        previous_bottom = None
        for row in rows:
            row.sort(key=lambda item: item[1][0])
            top, bottom = min(box[1] for _, box in row), max(box[3] for _, box in row)
            if previous_bottom is not None and top < previous_bottom - .5:
                return None
            previous_bottom = bottom
            for left, right in zip(row, row[1:], strict=False):
                a, b = left[1], right[1]
                tolerance = min(a[2] - a[0], b[2] - b[0]) * .01
                # A possible column gutter cannot establish prose order, even
                # if repeated words make both orders spell the same sentence.
                gap_limit = max(8., 2 * min(a[3] - a[1], b[3] - b[1]))
                if a[2] > b[0] + tolerance or b[0] - a[2] > gap_limit:
                    return None
            ordered.extend(cell for cell, _ in row)
        observed = [(word, cell) for cell in ordered for word in cell["text"].split()]
        actual = list(re.finditer(r"\S+", text))
        if [word for word, _ in observed] != [match[0] for match in actual]:
            return None
        intervals = []
        for match, (_, cell) in zip(actual, observed, strict=True):
            quality = cell.get("ocr_quality", {}) if cell.get("from_ocr") else {"state": "corroborated"}
            intervals.append({"start_offset": match.start(), "end_offset": match.end(),
                              "state": quality.get("state", "unavailable"),
                              "reading_ids": quality.get("reading_ids", []), "reasons": quality.get("reasons", [])})
        return intervals
    except (KeyError, TypeError, ValueError, IngestionError):
        return None


def _intervals(text, cells, *, table=False, page=None):
    """Recover exact text intervals; repeated unmatched occurrences stay unknown."""
    if not table:
        ordered = _ordered_intervals(text, cells, page)
        if ordered is not None:
            return ordered
    grouped: dict[str, list[dict]] = defaultdict(list)
    for cell in cells:
        if isinstance(cell.get("text"), str) and cell["text"].strip() and valid_box(cell.get("bbox")):
            grouped[cell["text"]].append(cell)
    intervals: list[dict[str, Any]] = []
    covered = bytearray(len(text))
    # An observed "V," owns its punctuation-bearing occurrence before the
    # shorter observed "V" is counted. This is literal tokenisation, not an
    # OCR spelling repair; counts must still match every observed occurrence.
    for literal, occurrences in sorted(grouped.items(), key=lambda item: (-len(item[0]), item[0])):
        # A TSV word such as "or" must not count the substring inside "for".
        # Likewise, a proved digit may not qualify a part of a different number.
        # Punctuation remains literal; only observed lexical edges are bounded.
        pattern = ((r"(?<!\w)" if re.match(r"\w", literal[0]) else "")
                   + re.escape(literal)
                   + (r"(?!\w)" if re.match(r"\w", literal[-1]) else ""))
        all_starts = [match.start() for match in re.finditer(pattern, text)]
        starts = [start for start in all_starts if not any(covered[start:start + len(literal)])]
        if not starts or len(starts) != len(occurrences):
            if any(any(covered[start:start + len(literal)]) for start in all_starts):
                intervals.extend({"start_offset": start, "end_offset": start + len(literal), "state": "uncertain",
                                  "reading_ids": [], "reasons": ["ambiguous_observed_tokenization"]}
                                 for start in all_starts)
            continue
        states = [cell.get("ocr_quality", {}).get("state", "unavailable") if cell.get("from_ocr") else "native"
                  for cell in occurrences]
        # Repeated words may share a proof only if every observed occurrence is
        # qualified; an uncertain one cannot be assigned a convenient offset.
        state = ("corroborated" if all(value in {"native", "corroborated"} for value in states)
                 else "uncertain" if any(value == "uncertain" for value in states) else "unavailable")
        reasons = sorted({reason for cell in occurrences for reason in cell.get("ocr_quality", {}).get("reasons", [])})
        ids = sorted({identity for cell in occurrences for identity in cell.get("ocr_quality", {}).get("reading_ids", [])})
        for start in starts:
            end = start + len(literal)
            # Different overlapping tokenisations are unresolved, not first-win.
            if any(covered[start:end]):
                intervals.append({"start_offset": start, "end_offset": end, "state": "uncertain",
                                  "reading_ids": ids, "reasons": ["overlapping_text_mapping"]})
            else:
                intervals.append({"start_offset": start, "end_offset": end, "state": state,
                                  "reading_ids": ids, "reasons": reasons})
            covered[start:end] = b"\1" * len(literal)
    missing_start: int | None = None
    for index in range(len(text) + 1):
        absent = index < len(text) and not covered[index] and not text[index].isspace() and not (table and text[index] == "|")
        if absent and missing_start is None:
            missing_start = index
        if not absent and missing_start is not None:
            intervals.append({"start_offset": missing_start, "end_offset": index, "state": "unavailable",
                              "reading_ids": [], "reasons": ["unmapped_source_text"]})
            missing_start = None
    return sorted(intervals, key=lambda item: (item["start_offset"], item["end_offset"]))


def block_quality(text, cells, canonical_readings, source_sha256, page_index, *, kind=None, table=False, page=None):
    """Keep a bounded immutable witness; its intervals can be reconstructed."""
    if (not isinstance(text, str) or len(text) > MAX_TEXT or len(cells) > MAX_TOKENS
            or len(canonical_readings) > MAX_READINGS):
        return {"schema_version": SCHEMA, "state": "unavailable", "reasons": ["quality_witness_limit"]}
    selected_ids = {identity for cell in cells for identity in cell.get("ocr_quality", {}).get("reading_ids", [])}
    readings = [copy.deepcopy(record) for record in canonical_readings if record.get("reading_id") in selected_ids]
    observations = [{key: copy.deepcopy(cell.get(key)) for key in ("text", "bbox", "confidence", "from_ocr")}
                    for cell in cells]
    for cell in observations:
        confidence = cell.get("confidence")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool) or not math.isfinite(confidence):
            cell["confidence"] = None
    checked = annotate_ocr_cells(observations, readings)
    intervals = _intervals(text, checked, table=table or kind == "table", page=page)
    state = ("corroborated" if intervals and all(item["state"] == "corroborated" for item in intervals)
             else "uncertain" if any(item["state"] == "uncertain" for item in intervals) else "unavailable")
    witness = {"schema_version": SCHEMA, "policy": READING_POLICY, "source_sha256": source_sha256,
               "page_index": page_index, "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "text_length": len(text), "table_serialization": bool(table or kind == "table"),
               "observations": observations, "readings": readings, "intervals": intervals, "state": state,
               "reading_ids": sorted(selected_ids), "reasons": sorted({reason for item in intervals for reason in item["reasons"]})}
    if page is not None:
        witness["page_frame"] = {key: page[key] for key in ("page_index", "crop_box", "effective_box", "rotation") if key in page}
    try:
        witness["sha256"] = digest(witness)
    except (TypeError, ValueError, OverflowError):
        return {"schema_version": SCHEMA, "state": "unavailable", "reasons": ["invalid_quality_witness"]}
    return witness


def _unavailable(reason, text):
    return {"policy": READING_POLICY, "state": "unavailable", "reasons": [reason], "text_length": len(text),
            "intervals": [{"start_offset": 0, "end_offset": len(text), "state": "unavailable",
                           "reading_ids": [], "reasons": [reason]}], "reading_ids": [], "sha256": None}


def verified_source_quality(text, metadata, source_sha256, page_index, *, page=None):
    """Validate the DB-loaded witness, source identity and recomputed intervals."""
    if not isinstance(metadata, dict) or not isinstance(text, str) or len(text) > MAX_TEXT:
        return _unavailable("invalid_quality_witness", text if isinstance(text, str) else "")
    method = metadata.get("extraction_method", "unknown")
    if method == "native" and not metadata.get("ocr_used"):
        if "native_condition_projection" in metadata:
            from .table_geometry import validate_native_condition_projection

            projection = validate_native_condition_projection(
                text, metadata, source_sha256=source_sha256, page_index=page_index)
            if projection.get("state") != "supported":
                return _unavailable("native_condition_projection_unverified", text)
        return {"policy": READING_POLICY, "state": "native", "intervals": [], "reading_ids": [],
                "text_length": len(text), "reasons": [], "sha256": None}
    if method not in {"ocr", "mixed"} and not metadata.get("ocr_used"):
        return _unavailable("extraction_method_unknown", text)
    witness = metadata.get("ocr_quality")
    if not isinstance(witness, dict) or witness.get("schema_version") != SCHEMA:
        return _unavailable("ocr_revalidation_required", text)
    try:
        if (not isinstance(witness.get("observations"), list) or len(witness["observations"]) > MAX_TOKENS
                or not all(isinstance(cell, dict) for cell in witness["observations"])
                or not isinstance(witness.get("readings"), list) or len(witness["readings"]) > MAX_READINGS
                or not all(isinstance(record, dict) for record in witness["readings"])):
            return _unavailable("quality_witness_limit", text)
        token_count = 0
        for record in witness["readings"]:
            for name in ("baseline_tokens", "candidate_tokens"):
                tokens = record.get(name) or []
                if not isinstance(tokens, list) or not all(isinstance(token, dict) for token in tokens):
                    return _unavailable("invalid_quality_witness", text)
                token_count += len(tokens)
        if token_count > MAX_TOKENS * 2:
            return _unavailable("quality_witness_limit", text)
        content = {key: value for key, value in witness.items() if key != "sha256"}
        if (witness.get("source_sha256") != source_sha256 or not isinstance(source_sha256, str)
                or not re.fullmatch(r"[a-f0-9]{64}", source_sha256) or witness.get("page_index") != page_index
                or type(page_index) is not int or page_index < 0 or witness.get("sha256") != digest(content)
                or witness.get("source_text_sha256") != hashlib.sha256(text.encode()).hexdigest()):
            return _unavailable("quality_witness_identity_mismatch", text)
        cells = annotate_ocr_cells(witness["observations"], witness["readings"])
        frame = witness.get("page_frame")
        if frame is not None:
            if not isinstance(frame, dict) or not isinstance(page, dict):
                return _unavailable("quality_witness_geometry_unavailable", text)
            expected_frame = {key: page[key] for key in ("page_index", "crop_box", "effective_box", "rotation") if key in page}
            if frame.get("page_index") != page_index or frame != expected_frame:
                return _unavailable("quality_witness_geometry_mismatch", text)
        expected = block_quality(text, cells, witness["readings"], source_sha256, page_index,
                                 table=witness.get("table_serialization") is True, page=frame)
        if canonical_witness(expected) != canonical_witness(witness):
            return _unavailable("quality_witness_reconstruction_failed", text)
        return {key: expected[key] for key in ("policy", "state", "intervals", "reading_ids", "reasons", "sha256", "text_length")}
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError, RecursionError):
        return _unavailable("invalid_quality_witness", text)


def canonical_witness(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def span_quality(quality, start, end):
    """Assess a requested exact source interval without rejecting its neighbours."""
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= quality.get("text_length", 0)):
        return {"state": "unavailable", "reading_ids": [], "reasons": ["invalid_quality_interval"]}
    if quality.get("state") == "native":
        return {"state": "native", "reading_ids": [], "reasons": []}
    selected = [item for item in quality.get("intervals", [])
                if item["start_offset"] < end and start < item["end_offset"]]
    state = ("corroborated" if selected and all(item["state"] == "corroborated" for item in selected)
             else "uncertain" if any(item["state"] == "uncertain" for item in selected) else "unavailable")
    return {"state": state, "reading_ids": sorted({identity for item in selected for identity in item["reading_ids"]}),
            "reasons": sorted({reason for item in selected for reason in item["reasons"]}) or ([] if selected else ["unmapped_source_text"])}
