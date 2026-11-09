"""Bounded native path observations for explicit, enclosed table header groups.

This records PDF objects, not raster visibility. Only simple opaque, undashed
paths with an absent clipping reference can establish a structural enclosure.
Unsupported paint/geometry in the enclosure prevents scope expansion. Borrowed
PDFium page objects and clipping handles are never destroyed by this module.
"""

from __future__ import annotations

import copy
import ctypes
import math
from collections.abc import Callable
from typing import Any

from .errors import IngestionError
from .geometry import normalize_box

RULE_SCHEMA = "pdfium-page-rules-v1"
HEADER_GROUP_SCHEMA = "native-ruled-header-group-v1"
MAX_RULE_OBJECTS = 4096
MAX_PATH_SEGMENTS = 64
MAX_RULE_SEGMENTS = 4096
MAX_RULE_LINES = 256
MAX_RULE_OBSTRUCTIONS = 256
AXIS_TOLERANCE = .05
JOIN_TOLERANCE = 1.0
MAX_RULE_WIDTH = 2.0
MIN_RULE_LENGTH = 4.0


def _box(raw, obj):
    values = [ctypes.c_float() for _ in range(4)]
    if not raw.FPDFPageObj_GetBounds(obj, *(ctypes.byref(value) for value in values)):
        return None
    return normalize_box([value.value for value in values])


def _rgba(raw, obj, method):
    values = [ctypes.c_uint() for _ in range(4)]
    if not getattr(raw, method)(obj, *(ctypes.byref(value) for value in values)):
        return None
    return [value.value for value in values]


def native_rule_observations(page, raw, *, source_sha256, page_index):
    """Capture at most the declared caps in the caller's existing PDFium lock.

    The non-null clip handle is borrowed from a known page object. PDFium's
    implementation returns CountPaths=-1 when that handle has no reference;
    CountPaths=0 may still have text clipping and is deliberately unsupported.
    Missing APIs or unreadable records do not certify an empty set of rules.
    """
    result: dict[str, Any] = {
        "schema_version": RULE_SCHEMA, "source_sha256": source_sha256, "page_index": page_index,
        "coordinate_frame": "pdf_user_space_unrotated", "complete": False,
        "limit_reason": None, "object_count": None, "segment_count": 0, "objects": [],
    }
    try:
        count = int(raw.FPDFPage_CountObjects(page))
        result["object_count"] = count
        if count < 0 or count > MAX_RULE_OBJECTS:
            result["limit_reason"] = "native_rule_object_limit"
            return result
        for index in range(count):
            obj = raw.FPDFPage_GetObject(page, index)
            if not obj:
                result["limit_reason"] = "native_rule_object_unreadable"
                return result
            kind = int(raw.FPDFPageObj_GetType(obj))
            active = ctypes.c_int()
            known_active = bool(raw.FPDFPageObj_GetIsActive(obj, ctypes.byref(active)))
            record: dict[str, Any] = {
                "id": f"o{index}", "object_index": index, "type": kind, "bbox": _box(raw, obj),
                "active": bool(active.value) if known_active else None,
            }
            if kind == 1:
                # Ordinary text is checked separately by the glyph projection.
                # An explicit clipping text object remains an obstruction.
                mode = int(raw.FPDFTextObj_GetTextRenderMode(obj))
                if mode in {0, 1, 2, 3} and known_active:
                    continue
                record["text_render_mode"] = mode
            elif kind == 2:
                segments = int(raw.FPDFPath_CountSegments(obj))
                if segments < 0 or segments > MAX_PATH_SEGMENTS or result["segment_count"] + segments > MAX_RULE_SEGMENTS:
                    result["limit_reason"] = "native_rule_segment_limit"
                    return result
                result["segment_count"] += segments
                matrix = raw.FS_MATRIX()
                matrix_known = bool(raw.FPDFPageObj_GetMatrix(obj, ctypes.byref(matrix)))
                fill_mode, stroke, width = ctypes.c_int(), ctypes.c_int(), ctypes.c_float()
                draw_known = bool(raw.FPDFPath_GetDrawMode(obj, ctypes.byref(fill_mode), ctypes.byref(stroke)))
                width_known = bool(raw.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(width)))
                clip = raw.FPDFPageObj_GetClipPath(obj)
                record.update(
                    matrix=[float(getattr(matrix, field)) for field in ("a", "b", "c", "d", "e", "f")] if matrix_known else None,
                    fill_mode=fill_mode.value if draw_known else None, stroke=bool(stroke.value) if draw_known else None,
                    stroke_width=width.value if width_known else None,
                    stroke_rgba=_rgba(raw, obj, "FPDFPageObj_GetStrokeColor"),
                    fill_rgba=_rgba(raw, obj, "FPDFPageObj_GetFillColor"),
                    has_transparency=bool(raw.FPDFPageObj_HasTransparency(obj)),
                    dash_count=int(raw.FPDFPageObj_GetDashCount(obj)),
                    clip={"handle_present": bool(clip), "path_count": int(raw.FPDFClipPath_CountPaths(clip)) if clip else None},
                    segments=[],
                )
                for position in range(segments):
                    segment = raw.FPDFPath_GetPathSegment(obj, position)
                    x, y = ctypes.c_float(), ctypes.c_float()
                    if not segment or not raw.FPDFPathSegment_GetPoint(segment, ctypes.byref(x), ctypes.byref(y)):
                        result["limit_reason"] = "native_rule_segment_unreadable"
                        return result
                    record["segments"].append({
                        "index": position, "type": int(raw.FPDFPathSegment_GetType(segment)),
                        "point": [x.value, y.value], "close": bool(raw.FPDFPathSegment_GetClose(segment)),
                    })
            result["objects"].append(record)
        result["complete"] = True
        return result
    except (AttributeError, TypeError, ValueError, OverflowError, ctypes.ArgumentError, IngestionError):
        result["limit_reason"] = "native_rule_api_or_geometry_unavailable"
        return result


def _intersects(first, second, tolerance=0.0):
    return (first[0] <= second[2] + tolerance and first[2] >= second[0] - tolerance
            and first[1] <= second[3] + tolerance and first[3] >= second[1] - tolerance)


def _inside(box, frame, tolerance=AXIS_TOLERANCE):
    return (box[0] >= frame[0] - tolerance and box[1] >= frame[1] - tolerance
            and box[2] <= frame[2] + tolerance and box[3] <= frame[3] + tolerance)


def scoped_rule_observations(record, *, source_sha256, page_index, table_bbox):
    """Keep pertinent source objects once; never synthesise a missing witness."""
    if not isinstance(record, dict):
        return None
    frame = normalize_box(table_bbox)

    def unavailable(reason):
        return {"schema_version": RULE_SCHEMA, "source_sha256": source_sha256, "page_index": page_index,
                "coordinate_frame": "pdf_user_space_unrotated", "complete": False, "limit_reason": reason,
                "object_count": 0, "segment_count": 0, "objects": [], "scope_bbox": frame}

    if (record.get("schema_version") != RULE_SCHEMA or record.get("source_sha256") != source_sha256
            or record.get("page_index") != page_index or record.get("coordinate_frame") != "pdf_user_space_unrotated"):
        return unavailable("native_rule_identity_mismatch")
    if record.get("complete") is not True:
        return unavailable(record.get("limit_reason") if isinstance(record.get("limit_reason"), str) else "native_rule_incomplete")
    objects = record.get("objects")
    if (not isinstance(objects, list) or len(objects) > MAX_RULE_OBJECTS
            or type(record.get("object_count")) is not int or not 0 <= record["object_count"] <= MAX_RULE_OBJECTS
            or type(record.get("segment_count")) is not int or not 0 <= record["segment_count"] <= MAX_RULE_SEGMENTS):
        return unavailable("native_rule_schema_or_limit")
    if record.get("scope_bbox") is not None and normalize_box(record["scope_bbox"]) != frame:
        return unavailable("native_rule_scope_mismatch")
    retained, seen = [], set()
    segment_count = 0
    for item in objects:
        if (not isinstance(item, dict) or type(item.get("object_index")) is not int
                or not 0 <= item["object_index"] < record["object_count"]
                or item.get("id") != f"o{item['object_index']}" or item["id"] in seen):
            return unavailable("native_rule_object_identity_invalid")
        seen.add(item["id"])
        if item.get("type") == 2:
            segments = item.get("segments")
            if not isinstance(segments, list) or len(segments) > MAX_PATH_SEGMENTS:
                return unavailable("native_rule_segment_limit")
            segment_count += len(segments)
            if segment_count > MAX_RULE_SEGMENTS or segment_count > record["segment_count"]:
                return unavailable("native_rule_segment_limit")
        if item.get("bbox") is None or _intersects(normalize_box(item["bbox"]), frame, MAX_RULE_WIDTH):
            retained.append(copy.deepcopy(item))
    return {**record, "objects": retained, "scope_bbox": frame}


def _numbers(value, length):
    return (isinstance(value, list) and len(value) == length
            and all(type(item) in {int, float} and math.isfinite(item) for item in value))


def _dark_opaque(value):
    return (isinstance(value, list) and len(value) == 4
            and all(type(channel) is int and 0 <= channel <= 255 for channel in value)
            and value[3] == 255 and max(value[:3]) <= 128)


def _path_lines(item):
    """Rebuild straight painted edges from local points and the actual matrix."""
    matrix, segments = item.get("matrix"), item.get("segments")
    if (item.get("active") is not True or item.get("has_transparency") is not False
            or item.get("dash_count") != 0 or item.get("clip") != {"handle_present": True, "path_count": -1}
            or not _numbers(matrix, 6) or not isinstance(segments, list) or not 2 <= len(segments) <= MAX_PATH_SEGMENTS):
        return None
    a, b, c, d, e, f = matrix
    # Axis-aligned scale/translation/quarter-turn only. Skew is not inferred.
    if (abs(a * c + b * d) > AXIS_TOLERANCE or abs(a * d - b * c) < 1e-9
            or not ((abs(a) <= AXIS_TOLERANCE and abs(d) <= AXIS_TOLERANCE)
                    or (abs(b) <= AXIS_TOLERANCE and abs(c) <= AXIS_TOLERANCE))):
        return None
    edges: list[tuple[int | str, tuple[float, float], tuple[float, float]]] = []
    first, previous = None, None
    for index, segment in enumerate(segments):
        if (not isinstance(segment, dict) or segment.get("index") != index
                or segment.get("type") not in {0, 2} or not _numbers(segment.get("point"), 2)
                or type(segment.get("close")) is not bool):
            return None
        x, y = segment["point"]
        point = (a * x + c * y + e, b * x + d * y + f)
        if segment["type"] == 2:
            if segment["close"]:
                return None
            first = previous = point
            continue
        if previous is None or first is None:
            return None
        edges.append((index, previous, point))
        previous = point
        if segment["close"]:
            if point != first:
                edges.append((f"{index}c", point, first))
            previous = first
    if not edges:
        return None
    if item.get("fill_mode") not in {0, 1, 2} or type(item.get("stroke")) is not bool:
        return None
    output = []
    if item["fill_mode"]:
        # A filled area is an obstruction unless its complete shape is a thin
        # rectangle. Its centreline describes the actual filled rule only.
        corners = {point for _, start, end in edges for point in (start, end)}
        if len(edges) != 4 or len(corners) != 4 or not segments[-1]["close"] or not _dark_opaque(item.get("fill_rgba")):
            return None
        xs, ys = {point[0] for point in corners}, {point[1] for point in corners}
        if len(xs) != 2 or len(ys) != 2 or any(start[0] != end[0] and start[1] != end[1] for _, start, end in edges):
            return None
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        width, length = min(x1 - x0, y1 - y0), max(x1 - x0, y1 - y0)
        if not 0 < width <= MAX_RULE_WIDTH or length < MIN_RULE_LENGTH:
            return None
        if item["stroke"]:
            return None
        box = [x0, (y0 + y1) / 2, x1, (y0 + y1) / 2] if x1 - x0 > y1 - y0 else [(x0 + x1) / 2, y0, (x0 + x1) / 2, y1]
        output.append({"id": item["id"] + ":fill", "bbox": box, "width": width})
    elif item["stroke"]:
        width = item.get("stroke_width")
        if not _dark_opaque(item.get("stroke_rgba")) or type(width) not in {int, float} or not math.isfinite(width) or width <= 0:
            return None
        for edge_index, start, end in edges:
            dx, dy = abs(end[0] - start[0]), abs(end[1] - start[1])
            if min(dx, dy) > AXIS_TOLERANCE:
                return None
            if max(dx, dy) < MIN_RULE_LENGTH:
                continue
            # For the admitted orthogonal matrices this is a conservative
            # bound on the transformed stroke's perpendicular thickness.
            transformed_width = width * max(math.hypot(a, b), math.hypot(c, d))
            if transformed_width > MAX_RULE_WIDTH:
                return None
            box = [min(start[0], end[0]), (start[1] + end[1]) / 2, max(start[0], end[0]), (start[1] + end[1]) / 2] if dx > dy else [
                (start[0] + end[0]) / 2, min(start[1], end[1]), (start[0] + end[0]) / 2, max(start[1], end[1])]
            output.append({"id": f"{item['id']}:s{edge_index}", "bbox": box, "width": transformed_width})
    elif item["fill_mode"] == 0:
        return []
    if item.get("bbox") is None or any(not _inside(line["bbox"], normalize_box(item["bbox"]), JOIN_TOLERANCE) for line in output):
        return None
    return output


def _compiled(record, to_display):
    if not isinstance(record, dict) or record.get("complete") is not True or record.get("limit_reason") is not None:
        return None
    lines: list[dict] = []
    obstructions: list[list[float] | None] = []
    for item in record["objects"]:
        if item.get("active") is False:
            continue
        extracted = _path_lines(item) if item.get("type") == 2 else None
        if extracted is None:
            box = normalize_box(item["bbox"]) if item.get("bbox") is not None else None
            if box is None or box[0] < box[2] and box[1] < box[3]:
                obstructions.append(to_display(box) if box else None)
        else:
            for line in extracted:
                box = to_display(line["bbox"])
                horizontal = box[2] - box[0] > box[3] - box[1]
                lines.append({"ids": [line["id"]], "axis": "h" if horizontal else "v",
                              "position": (box[1] + box[3]) / 2 if horizontal else (box[0] + box[2]) / 2,
                              "start": box[0] if horizontal else box[1], "end": box[2] if horizontal else box[3]})
                if len(lines) > MAX_RULE_LINES:
                    return None
        if len(obstructions) > MAX_RULE_OBSTRUCTIONS:
            return None
    # Collinear contiguous source edges can join; their individual IDs remain.
    merged: list[dict] = []
    for line in sorted(lines, key=lambda row: (row["axis"], row["position"], row["start"], row["end"])):
        if (merged and line["axis"] == merged[-1]["axis"]
                and abs(line["position"] - merged[-1]["position"]) <= AXIS_TOLERANCE
                and line["start"] <= merged[-1]["end"] + JOIN_TOLERANCE):
            merged[-1]["end"] = max(merged[-1]["end"], line["end"])
            merged[-1]["ids"].extend(line["ids"])
        else:
            merged.append(copy.deepcopy(line))
    return merged, obstructions


def prove_header_group(record, candidate, headers, observations, *, table_bbox,
                       to_display: Callable[[list[float]], list[float]]):
    """Return a literal parent's unique enclosed child range, or no extension.

    Inputs are actual spatial observations and source paths. Parser colspan,
    component names and data values do not participate in the decision.
    This proves structural scope across explicit headers, including a unit;
    it assigns no statistical role or relation between their data values.
    """
    if (not candidate or any(item.get("origin") != "native" or item.get("state") != "supported" for item in candidate)
            or len(headers) < 2 or not isinstance(record, dict)):
        return None
    try:
        compiled = _compiled(record, to_display)
        if compiled is None:
            return None
        lines, obstructions = compiled
        parent = [min(item["display_bbox"][0] for item in candidate), min(item["display_bbox"][1] for item in candidate),
                  max(item["display_bbox"][2] for item in candidate), max(item["display_bbox"][3] for item in candidate)]
        header_top = min(item["display_bbox"][1] for item in headers)
        header_bottom = max(item["display_bbox"][3] for item in headers)
        if parent[3] >= header_top - AXIS_TOLERANCE:
            return None
        vertical = [line for line in lines if line["axis"] == "v"
                    and line["start"] <= parent[1] + JOIN_TOLERANCE and line["end"] >= header_bottom - JOIN_TOLERANCE]
        left = max((line for line in vertical if line["position"] < parent[0]), key=lambda line: line["position"], default=None)
        right = min((line for line in vertical if line["position"] > parent[2]), key=lambda line: line["position"], default=None)
        if left is None or right is None:
            return None
        horizontal = [line for line in lines if line["axis"] == "h"
                      and line["start"] <= left["position"] + JOIN_TOLERANCE and line["end"] >= right["position"] - JOIN_TOLERANCE]
        top = max((line for line in horizontal if line["position"] < parent[1]), key=lambda line: line["position"], default=None)
        bottom = min((line for line in horizontal if line["position"] > header_bottom), key=lambda line: line["position"], default=None)
        if top is None or bottom is None:
            return None
        frame = [left["position"], top["position"], right["position"], bottom["position"]]
        if (not _inside(frame, to_display(table_bbox), JOIN_TOLERANCE)
                or any(line["start"] > frame[1] + JOIN_TOLERANCE or line["end"] < frame[3] - JOIN_TOLERANCE for line in (left, right))
                or any(box is None or _intersects(box, frame, AXIS_TOLERANCE) for box in obstructions)):
            return None
        columns = [index for index, item in enumerate(headers) if _inside(item.get("_column_bbox", item["display_bbox"]), frame)]
        if len(columns) < 2 or columns != list(range(columns[0], columns[-1] + 1)):
            return None
        if any(headers[index].get("origin") != "native" or headers[index].get("state") != "supported" for index in columns):
            return None
        if any(index not in columns and _intersects(item["display_bbox"], frame, -AXIS_TOLERANCE) for index, item in enumerate(headers)):
            return None
        parent_ids = [item["id"] for item in candidate]
        child_ids = [identifier for index in columns for identifier in headers[index].get("part_ids", [headers[index]["id"]])]
        allowed = set(parent_ids + child_ids)
        observed = {item["id"]: item for item in observations}
        if any(identifier not in observed or observed[identifier].get("origin") != "native"
               or observed[identifier].get("state") != "supported" for identifier in child_ids):
            return None
        if any(item["id"] not in allowed and _intersects(item["display_bbox"], frame, -AXIS_TOLERANCE) for item in observations):
            return None
        for line in lines:
            if line["axis"] == "v":
                if (frame[0] + JOIN_TOLERANCE < line["position"] < frame[2] - JOIN_TOLERANCE
                        and min(line["end"], frame[3]) - max(line["start"], frame[1]) > JOIN_TOLERANCE):
                    return None
            elif (frame[1] + JOIN_TOLERANCE < line["position"] < frame[3] - JOIN_TOLERANCE
                  and min(line["end"], frame[2]) - max(line["start"], frame[0]) > JOIN_TOLERANCE):
                return None
        return {"schema_version": HEADER_GROUP_SCHEMA, "columns": columns, "display_bbox": frame,
                "parent_observation_ids": parent_ids, "child_header_observation_ids": child_ids,
                "sides": {name: sorted(line["ids"]) for name, line in (("left", left), ("top", top), ("right", right), ("bottom", bottom))}}
    except (KeyError, TypeError, ValueError, IndexError, IngestionError):
        return None
