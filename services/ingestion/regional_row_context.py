"""Bounded native-density OCR context for rows of an established grid."""

import hashlib
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass

ROW_CONTEXT_MAX_WIDTH = 2048
ROW_CONTEXT_MAX_HEIGHT = 128
ROW_CONTEXT_MAX_INK_HEIGHT = 48
ROW_CONTEXT_MAX_CALLS = 32
ROW_CONTEXT_BORDER = 10
ROW_CONTEXT_EDGE = 4
ROW_CONTEXT_POLICY = "grid_row_native_density_retry_v1"


@dataclass
class _RowBudget:
    limit: int
    pixels: int = 0
    calls: int = 0

    def reserve(self, pixels, trace):
        if pixels > self.limit:
            trace["reason"] = "crop_pixel_limit"
            return False
        if self.pixels + pixels > self.limit:
            trace["reason"] = "cumulative_pixel_limit"
            return False
        self.pixels += pixels
        return True

    def metadata(self):
        return {"pixel_limit": self.limit, "cumulative_crop_pixels": self.pixels,
                "additional_ocr_calls": self.calls, "additional_ocr_call_limit": ROW_CONTEXT_MAX_CALLS}


def _grid_rows(image, cells):
    """Require finite, in-frame disjoint cells sharing complete row bands."""
    groups = defaultdict(list)
    for index, bounds in enumerate(cells):
        if len(bounds) != 4 or not all(math.isfinite(value) and value == int(value) for value in bounds):
            return None
        left, top, right, bottom = bounds
        if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            return None
        groups[(top, bottom)].append(index)
    rows = sorted(groups.items())
    if not rows or any(band[0] < prior[1] for (prior, _), (band, _) in zip(rows, rows[1:], strict=False)):
        return None
    result = []
    for _, indices in rows:
        indices.sort(key=lambda index: cells[index][0])
        if len(indices) < 2 or any(cells[a][2] > cells[b][0] for a, b in zip(indices, indices[1:], strict=False)):
            return None
        result.append(indices)
    return result


def _bounded_row_crop(image, bounds, budget, trace):
    """Check each allocation before copying the row or adding its ink border."""
    import numpy as np
    from PIL import ImageOps
    from scipy.ndimage import label

    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    trace.update(source_crop_size=[width, height], source_crop_pixels=width * height)
    if width > ROW_CONTEXT_MAX_WIDTH or height > ROW_CONTEXT_MAX_HEIGHT:
        trace["reason"] = "source_crop_dimensions_limit"
        return None, None
    if not budget.reserve(width * height, trace):
        return None, None
    crop = image.crop(tuple(bounds)).convert("RGB")
    trace["source_crop_sha256"] = hashlib.sha256(crop.tobytes()).hexdigest()
    dark = np.asarray(crop.convert("L")) < 128
    edge = max(0, min(ROW_CONTEXT_EDGE, (min(height, width) - 1) // 2))
    labels, count = label(dark, structure=np.ones((3, 3), dtype=bool))
    interior = np.zeros_like(dark)
    interior[edge:height - edge, edge:width - edge] = True
    content = np.flatnonzero(np.bincount(labels[interior], minlength=count + 1)[1:]) + 1
    kept = np.isin(labels, content)
    rows, columns = np.flatnonzero(kept.any(axis=1)), np.flatnonzero(kept.any(axis=0))
    if not rows.size:
        trace["reason"] = "no_interior_ink"
        return None, None
    ink = (int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1)
    trace["ink_height"] = ink[3] - ink[1]
    if trace["ink_height"] > ROW_CONTEXT_MAX_INK_HEIGHT:
        trace["reason"] = "ink_height_limit"
        return None, None
    size = (ink[2] - ink[0] + 2 * ROW_CONTEXT_BORDER, ink[3] - ink[1] + 2 * ROW_CONTEXT_BORDER)
    trace.update(context_raster_size=list(size), context_raster_pixels=size[0] * size[1])
    if size[0] > ROW_CONTEXT_MAX_WIDTH or size[1] > ROW_CONTEXT_MAX_HEIGHT:
        trace["reason"] = "context_crop_dimensions_limit"
        return None, None
    if not budget.reserve(size[0] * size[1], trace):
        return None, None
    patch = ImageOps.expand(crop.crop(ink), border=ROW_CONTEXT_BORDER, fill="white")
    offset = (bounds[0] + ink[0] - ROW_CONTEXT_BORDER, bounds[1] + ink[1] - ROW_CONTEXT_BORDER)
    trace.update(raster_offset=list(offset), context_raster_sha256=hashlib.sha256(patch.tobytes()).hexdigest())
    return patch, offset


def _valid_boxes(frame, width, height):
    import numpy as np

    boxes = frame[["left", "top", "width", "height"]].to_numpy(dtype=float)
    return bool(np.isfinite(boxes).all() and (boxes[:, :2] >= 0).all() and (boxes[:, 2:] > 0).all()
                and (boxes[:, 0] + boxes[:, 2] <= width).all()
                and (boxes[:, 1] + boxes[:, 3] <= height).all())


def _validated_cells(candidate, patch, offset, cells, indices, baselines, evidence, threshold, trace):
    from .regional_grid import _minimum_cell_confidence

    confidence = _minimum_cell_confidence(candidate)
    trace["candidate_minimum_word_confidence"] = confidence
    if confidence is None or confidence < threshold:
        trace["reason"] = "candidate_not_admissible"
        return None
    if not _valid_boxes(candidate, *patch.size):
        trace["reason"] = "candidate_invalid_geometry"
        return None
    restored = candidate.copy()
    restored["left"] += offset[0]
    restored["top"] += offset[1]
    assignments = defaultdict(list)
    for position, word in enumerate(restored.itertuples(index=False)):
        owners = [index for index in indices if cells[index][0] <= word.left
                  and cells[index][1] <= word.top and word.left + word.width <= cells[index][2]
                  and word.top + word.height <= cells[index][3]]
        if len(owners) != 1:
            trace["reason"] = "candidate_word_not_in_unique_cell"
            return None
        assignments[owners[0]].append(position)
    per_cell = {}
    for index in indices:
        if evidence[index]["printed"] != bool(assignments[index]):
            trace["reason"] = "candidate_printed_cells_mismatch"
            return None
        per_cell[index] = restored.iloc[assignments[index]].copy()
        before = _minimum_cell_confidence(baselines[index])
        if before is not None and before >= threshold:
            if tuple(per_cell[index]["text"]) != tuple(baselines[index]["text"]):
                trace["reason"] = "candidate_changed_admissible_cell"
                return None
    return per_cell


def recognize_grid_rows(image, cells, baselines, evidence, recognize, minimum_confidence, max_region_pixels):
    """Keep actual cell baselines unless an entire native-density row is valid.

    The callback uses the same cell engine, languages and PSM 6. Printed cells
    with a nonfinite baseline or an already attempted mono-glyph retry exclude
    their row. No expected text, OCR text or subprocess output enters traces.
    Source-row and bordered-context pixels consume one cumulative regional
    budget, even when recognition fails or the candidate is rejected.
    """
    from .regional_grid import _minimum_cell_confidence

    budget = _RowBudget(max_region_pixels)
    selected, traces = list(baselines), []
    rows = _grid_rows(image, cells)
    if rows is None or len(cells) != len(baselines) or len(cells) != len(evidence):
        return selected, [{"policy": ROW_CONTEXT_POLICY, "attempted": False,
                           "selected": "baseline", "reason": "invalid_grid_geometry"}], budget.metadata()
    for row_index, indices in enumerate(rows):
        bounds = [int(min(cells[index][0] for index in indices)), int(cells[indices[0]][1]),
                  int(max(cells[index][2] for index in indices)), int(cells[indices[0]][3])]
        trace = {"policy": ROW_CONTEXT_POLICY, "row_index": row_index, "cell_indices": indices,
                 "raster_bbox": bounds, "factor": 1, "attempted": False, "selected": "baseline",
                 "source_crop_dimensions_limit": [ROW_CONTEXT_MAX_WIDTH, ROW_CONTEXT_MAX_HEIGHT],
                 "context_crop_dimensions_limit": [ROW_CONTEXT_MAX_WIDTH, ROW_CONTEXT_MAX_HEIGHT],
                 "ink_height_limit": ROW_CONTEXT_MAX_INK_HEIGHT, "border": ROW_CONTEXT_BORDER,
                 "minimum_confidence_required": minimum_confidence}
        traces.append(trace)
        if minimum_confidence is None or not math.isfinite(minimum_confidence):
            trace["reason"] = "threshold_not_configured"
            continue
        printed = [index for index in indices if evidence[index]["printed"]]
        if any(not baselines[index].empty and _minimum_cell_confidence(baselines[index]) is None for index in printed):
            trace["reason"] = "invalid_baseline_confidence"
            continue
        if any(not baselines[index].empty and not _valid_boxes(baselines[index], *image.size) for index in printed):
            trace["reason"] = "invalid_baseline_geometry"
            continue
        low = [index for index in printed if baselines[index].empty
               or _minimum_cell_confidence(baselines[index]) < minimum_confidence]
        trace["eligible_cell_indices"] = low
        if not low:
            trace["reason"] = "baseline_admissible"
            continue
        if any(evidence[index].get("crop", {}).get("policy") != "ink_border_10" for index in printed):
            trace["reason"] = "cell_border_not_configured"
            continue
        if any(evidence[index].get("crop", {}).get("density_retry", {}).get("attempted", False) for index in indices):
            trace["reason"] = "mono_glyph_retry_already_attempted"
            continue
        if budget.calls >= ROW_CONTEXT_MAX_CALLS:
            trace["reason"] = "additional_call_limit"
            continue
        patch, offset = _bounded_row_crop(image, bounds, budget, trace)
        trace.update(cumulative_crop_pixels=budget.pixels, additional_ocr_calls=budget.calls)
        if patch is None:
            continue
        budget.calls += 1
        trace.update(attempted=True, additional_ocr_calls=budget.calls,
                     trigger="printed_cell_low_or_missing_confidence", candidate_minimum_word_confidence=None)
        try:
            candidate = recognize(patch)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
            trace.update(reason="context_recognition_failed", retry_error=type(error).__name__)
            if isinstance(error, subprocess.CalledProcessError):
                trace["retry_returncode"] = error.returncode
            continue
        validated = _validated_cells(candidate, patch, offset, cells, indices, baselines, evidence,
                                     minimum_confidence, trace)
        if validated is None:
            continue
        for index in low:
            selected[index] = validated[index]
        trace.update(selected="row_context", reason="candidate_admissible", adopted_cell_indices=low,
                     coordinate_inverse_factor=1)
    return selected, traces, budget.metadata()
