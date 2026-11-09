"""One bounded alternative segmentation of observed OCR lines.

No replacement dictionary or expected answer is used. Both literal readings,
their real boxes, raster derivations and disagreements remain in extraction
evidence. The selected text is always the original reading.
"""

from __future__ import annotations

import hashlib
import math
import statistics
import subprocess

from .regional_row_context import ROW_CONTEXT_MAX_CALLS
from .source_quality import (
    MAX_READINGS,
    MAX_TOKENS,
    READING_POLICY,
    SIGN_POLICY,
    UNSCALED_RECHECK_POLICY,
    assess_reading,
    can_recheck_unscaled,
    valid_box,
)

MAX_CROP_WIDTH = 4096
MAX_CROP_HEIGHT = 256
CROP_BORDER = 10


def _tokens(frame, *, factor=1., offset=(0., 0.)):
    result = []
    for item in frame.itertuples(index=False):
        try:
            box = [float(item.left) / factor + offset[0], float(item.top) / factor + offset[1],
                   (float(item.left) + float(item.width)) / factor + offset[0],
                   (float(item.top) + float(item.height)) / factor + offset[1]]
            confidence = float(item.conf) / 100
            if not valid_box(box) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                continue
            result.append({"text": str(item.text), "bbox": box, "confidence": confidence})
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
        if len(result) >= MAX_TOKENS:
            break
    return result


def _lines(tokens):
    """Use actual vertical overlap; TSV cell calls can reuse line numbers."""
    lines: list[list[dict]] = []
    for token in sorted(tokens, key=lambda item: ((item["bbox"][1] + item["bbox"][3]) / 2, item["bbox"][0])):
        center = (token["bbox"][1] + token["bbox"][3]) / 2
        height = token["bbox"][3] - token["bbox"][1]
        choices = []
        recent_start = max(0, len(lines) - 16)
        for index in range(recent_start, len(lines)):
            line = lines[index]
            middle = statistics.median((item["bbox"][1] + item["bbox"][3]) / 2 for item in line)
            typical = statistics.median(item["bbox"][3] - item["bbox"][1] for item in line)
            if abs(middle - center) <= min(height, typical) * .45:
                choices.append((abs(middle - center), index))
        if choices:
            lines[min(choices)[1]].append(token)
        else:
            lines.append([token])
    # Numeric lines are checked first; all omitted words remain explicitly
    # unavailable. This is a verification budget, not a ranking of source facts.
    return sorted((sorted(line, key=lambda item: item["bbox"][0]) for line in lines),
                  key=lambda line: (not any(any(char.isdigit() for char in token["text"]) for token in line),
                                    min(token["bbox"][1] for token in line)))


def _sign_bounds(image, token):
    box = token["bbox"]
    height = box[3] - box[1]
    return (max(0, math.floor(box[0]) - 2), max(0, math.floor(box[1]) - 2),
            min(image.width, math.ceil(box[0] + min(box[2] - box[0] + 2, height * 1.3))),
            min(image.height, math.ceil(box[3] + height * .8)))


def plus_shape(image, token):
    """Conservative raster check for a leading + versus an extra lower bar.

    This never emits ± or changes a word. An inconclusive/extra component makes
    a numeric leading plus unavailable even if two OCR calls both read +.
    """
    import numpy as np
    from scipy.ndimage import find_objects, label

    text = token["text"]
    if not text.startswith("+"):
        return None
    box = token["bbox"]
    height = box[3] - box[1]
    left, top, right, bottom = _sign_bounds(image, token)
    if right <= left or bottom <= top or (right - left) * (bottom - top) > 65536:
        return "inconclusive_sign_shape"
    mask = np.asarray(image.crop((left, top, right, bottom)).convert("L")) < 160
    labels, _ = label(mask)
    objects = [(index + 1, item) for index, item in enumerate(find_objects(labels)) if item is not None
               and int((labels[item] == index + 1).sum()) >= 3]
    crosses = []
    for identity, (vertical, horizontal) in objects:
        width, high = horizontal.stop - horizontal.start, vertical.stop - vertical.start
        if width < 3 or high < 3 or horizontal.start > height * .45:
            continue
        component = labels[vertical, horizontal] == identity
        rows, columns = component.sum(axis=1), component.sum(axis=0)
        if rows.max() >= .65 * width and columns.max() >= .65 * high and .15 * high <= rows.argmax() <= .85 * high:
            crosses.append((identity, vertical, horizontal))
    if len(crosses) != 1:
        return "inconclusive_sign_shape"
    identity, vertical, horizontal = crosses[0]
    width, high = horizontal.stop - horizontal.start, vertical.stop - vertical.start
    # A lower bar can touch the stem after rasterisation, so it need not be a
    # separate connected component. Count distinct horizontal bands in the
    # cross's own columns, including pixels below it. Never infer a plain +
    # from a crop that ends before the area where a lower bar could appear.
    if mask.shape[0] < vertical.stop + max(3, math.ceil(high * .5)):
        return "inconclusive_sign_shape"
    broad_rows = mask[:, horizontal.start:horizontal.stop].sum(axis=1) >= width * .55
    bands: list[list[int]] = []
    for row, broad in enumerate(broad_rows):
        if broad and (not bands or row > bands[-1][1] + 1):
            bands.append([row, row])
        elif broad:
            bands[-1][1] = row
    crossing = [band for band in bands if vertical.start < band[0] < vertical.stop]
    if len(crossing) != 1:
        return "additional_lower_bar" if len(crossing) > 1 else "inconclusive_sign_shape"
    if any(band[0] > crossing[0][1] for band in bands):
        return "additional_lower_bar"
    for other_id, (other_y, other_x) in objects:
        if other_id == identity:
            continue
        other_width, other_height = other_x.stop - other_x.start, other_y.stop - other_y.start
        center = (horizontal.start + horizontal.stop) / 2
        if (vertical.stop <= other_y.start <= vertical.stop + high
                and abs((other_x.start + other_x.stop) / 2 - center) < width * .5
                and other_width >= width * .55 and other_height <= max(3, high * .45)):
            return "additional_lower_bar"
    return "cross_only"


def verify_ocr_lines(image, baseline, recognize, minimum_confidence, max_region_pixels, *, used_calls=0, used_pixels=0):
    """Keep OCR text unchanged and share the existing row retry/pixel budget."""
    from PIL import Image, ImageOps

    words = _tokens(baseline)
    source_sha = hashlib.sha256(image.tobytes()).hexdigest()
    records = []
    calls, pixels = used_calls, used_pixels
    recheck_calls = 0
    lines = _lines(words)
    for index, line in enumerate(lines[:MAX_READINGS]):
        record = {"policy": READING_POLICY, "reading_id": f"line-{index}", "baseline_tokens": line,
                  "candidate_tokens": None, "coordinate_frame": "oriented_ocr_region_pixels",
                  "minimum_confidence": max(.8, float(minimum_confidence or .8)), "state": "unavailable",
                  "source_raster_sha256": source_sha, "source_raster_size": list(image.size),
                  "parameters": {"psm": 6, "factor": 2, "border": CROP_BORDER, "resampling": "LANCZOS"}}
        records.append(record)
        if calls >= ROW_CONTEXT_MAX_CALLS:
            record["reason"] = "shared_retry_call_limit"
            continue
        bounds = [max(0, math.floor(min(token["bbox"][0] for token in line)) - 3),
                  max(0, math.floor(min(token["bbox"][1] for token in line)) - 3),
                  min(image.width, math.ceil(max(token["bbox"][2] for token in line)) + 3),
                  min(image.height, math.ceil(max(token["bbox"][3] for token in line)) + 3)]
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        factor = 2 if statistics.median(token["bbox"][3] - token["bbox"][1] for token in line) <= 24 else 1
        size = ((width + 2 * CROP_BORDER) * factor, (height + 2 * CROP_BORDER) * factor)
        record.update(source_crop_bbox=bounds, candidate_raster_size=list(size))
        record["parameters"]["factor"] = factor
        allocation = width * height + (width + 2 * CROP_BORDER) * (height + 2 * CROP_BORDER) + size[0] * size[1]
        sign_pixels = 0
        for token in line:
            if token["text"].startswith("+"):
                left, top, right, bottom = _sign_bounds(image, token)
                sign_pixels += max(0, right - left) * max(0, bottom - top)
        allocation += sign_pixels
        if width <= 0 or height <= 0 or size[0] > MAX_CROP_WIDTH or size[1] > MAX_CROP_HEIGHT:
            record["reason"] = "verification_crop_dimensions_limit"
            continue
        if allocation > max_region_pixels or pixels + allocation > max_region_pixels:
            record["reason"] = "shared_retry_pixel_limit"
            continue
        pixels += allocation
        record["visual_sign_crop_pixels"] = sign_pixels
        for token in line:
            if token["text"].startswith("+"):
                check = plus_shape(image, token)
                token["visual_sign_check"] = check
                token["visual_sign_policy"] = SIGN_POLICY
                if check != "cross_only":
                    token["visual_ambiguities"] = [str(check)]
        patch = ImageOps.expand(image.crop(tuple(bounds)), border=CROP_BORDER, fill="white")
        if factor != 1:
            patch = patch.resize(size, Image.Resampling.LANCZOS)
        record["candidate_raster_sha256"] = hashlib.sha256(patch.tobytes()).hexdigest()
        calls += 1
        try:
            candidate = recognize(patch)
            record["candidate_tokens"] = _tokens(candidate, factor=factor,
                                                  offset=(bounds[0] - CROP_BORDER, bounds[1] - CROP_BORDER))
            assessment = assess_reading(record)
            if can_recheck_unscaled(record, assessment):
                # Enlarging an already legible glyph can lower its OCR score.
                # One unscaled reading may confirm it, but all literal/geometry
                # agreement from the first reading is retained and rechecked.
                # This never retries a disagreement or lowers the threshold.
                retry_pixels = width * height + (width + 2 * CROP_BORDER) * (height + 2 * CROP_BORDER)
                retry = {"policy": UNSCALED_RECHECK_POLICY, "status": "skipped"}
                record["unscaled_recheck"] = retry
                if calls >= ROW_CONTEXT_MAX_CALLS:
                    retry["reason"] = "shared_retry_call_limit"
                elif pixels + retry_pixels > max_region_pixels:
                    retry["reason"] = "shared_retry_pixel_limit"
                else:
                    pixels += retry_pixels
                    calls += 1
                    recheck_calls += 1
                    unscaled = ImageOps.expand(image.crop(tuple(bounds)), border=CROP_BORDER, fill="white")
                    retry["status"] = "failed"
                    try:
                        repeated = recognize(unscaled)
                        prior = {name: record[name] for name in ("candidate_tokens", "candidate_raster_sha256", "candidate_raster_size", "parameters")}
                        record["prior_candidate"] = prior
                        record["candidate_tokens"] = _tokens(repeated, offset=(bounds[0] - CROP_BORDER, bounds[1] - CROP_BORDER))
                        record["candidate_raster_sha256"] = hashlib.sha256(unscaled.tobytes()).hexdigest()
                        record["candidate_raster_size"] = list(unscaled.size)
                        record["parameters"] = {**record["parameters"], "factor": 1}
                        retry["status"] = "completed"
                        assessment = assess_reading(record)
                    finally:
                        unscaled.close()
            record.update(state=assessment["state"], reasons=assessment["reasons"],
                          reason="agreement" if assessment["state"] == "corroborated" else "reading_disagrees_or_uncertain")
        except (subprocess.SubprocessError, OSError, TimeoutError, ValueError):
            record["reason"] = "verification_recognition_failed"
        finally:
            patch.close()
    budget = {"additional_ocr_calls": calls, "additional_ocr_call_limit": ROW_CONTEXT_MAX_CALLS,
              "cumulative_crop_pixels": pixels, "pixel_limit": max_region_pixels,
              "verification_calls": calls - used_calls, "verification_pixels": pixels - used_pixels,
              "verification_recheck_calls": recheck_calls,
              "omitted_reading_lines": max(0, len(lines) - MAX_READINGS)}
    return records, budget
