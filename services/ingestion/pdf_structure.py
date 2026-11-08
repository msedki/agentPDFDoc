"""Conservative bindings for written PDF list hierarchies.

The rule needs a parent bullet, a colon-terminated label, indented child markers
and a closing parent bullet. Geometry disambiguates these written signs; it
never supplies an absent title, condition or value. All source strings stay
separate and byte-for-byte unchanged.
"""

import hashlib
import json
import math

LIST_STRUCTURE_REVISION = "explicit-pdf-list-v1"
MAX_LIST_PAGE_BLOCKS = 1024
MAX_LIST_PAGE_CHARS = 200_000
MAX_LIST_ITEMS = 64
MAX_LIST_GROUP_CHARS = 12_000
PARENT_MARKERS = frozenset({"•", "●", "◦", "▪", "·"})
CHILD_MARKERS = frozenset({"–", "—", "-", "•", "◦", "▪"})


def _text(block):
    return block.get("raw_text", block.get("text", ""))


def _marker(block):
    text = _text(block)
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    markers = PARENT_MARKERS | CHILD_MARKERS
    if stripped in markers:
        return stripped
    # Structured Docling may keep the written glyph inside a list-item block.
    # Keep that whole source block: splitting it would invent a glyph bbox.
    if (block.get("metadata", {}).get("label") == "list_item" and len(stripped) > 2
            and stripped[0] in markers and stripped[1].isspace()):
        return stripped[0]
    return None


def _inline_marker(block):
    marker = _marker(block)
    return marker is not None and _text(block).strip() != marker


def _box(block):
    box = block.get("bbox")
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) for value in box)
            or box[0] >= box[2] or box[1] >= box[3]):
        return None
    return box


def _intersects(first, second):
    return min(first[2], second[2]) > max(first[0], second[0]) and min(first[3], second[3]) > max(first[1], second[1])


def _method(block):
    metadata = block.get("metadata")
    return metadata.get("extraction_method", "unknown") if isinstance(metadata, dict) else "unknown"


def _eligible(block, page):
    text, box = _text(block), _box(block)
    if (not isinstance(text, str) or not text.strip() or len(text) > 4096 or "\n" in text.strip()
            or not box or block.get("type", block.get("kind")) not in {"text", "heading"}
            or block.get("page_index") != page.get("page_index")
            or _method(block) not in {"native", "ocr", "mixed"}
            or hashlib.sha256(text.encode()).hexdigest() != block.get("source_text_hash")):
        return False
    bounds = page.get("crop_box", page.get("media_box"))
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4
            or box[0] < bounds[0] or box[1] < bounds[1] or box[2] > bounds[2] or box[3] > bounds[3]):
        return False
    for region in page.get("unresolved_regions", []):
        if region.get("reason") == "GRAPHIC_INTERPRETATION_UNAVAILABLE":
            continue
        region_box = _box(region)
        if region_box is None or _intersects(box, region_box):
            return False
    return True


def _paired_text(marker, blocks):
    """A glyph must have exactly one text partner on its visual baseline."""
    if _inline_marker(marker):
        return marker
    box = _box(marker)
    if box is None:
        return None
    midpoint = (box[1] + box[3]) / 2
    candidates = []
    for block in blocks:
        other = _box(block)
        text = _text(block)
        if (block is marker or not other or not isinstance(text, str) or not text.strip()
                or text.strip() in PARENT_MARKERS | CHILD_MARKERS
                or block.get("type", block.get("kind")) not in {"text", "heading"}):
            continue
        height = other[3] - other[1]
        if other[1] - height * .15 <= midpoint <= other[3] + height * .15 and 0 <= other[0] - box[2] <= height * 2.5:
            candidates.append(block)
    return candidates[0] if len(candidates) == 1 else None


def _group_identity(group):
    blocks = [group["parent_marker"], group["heading"],
              *(block for item in group["items"] for block in (item["marker"], item["block"])),
              group["boundary_marker"], group["boundary"]]
    value = [[block["id"], block["source_text_hash"], block["extraction_revision_id"], block["bbox"]] for block in blocks]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def explicit_list_groups(page):
    """Return only closed, unambiguous written lists in one canonical page.

    An uncertain child remains counted but cannot receive a verified binding.
    The rule is bounded and independent of the question, tokenizer and model.
    """
    blocks = page.get("blocks", [])
    if (not isinstance(blocks, list) or len(blocks) > MAX_LIST_PAGE_BLOCKS or page.get("rotation", 0) != 0
            or page.get("source_provenance_incomplete")
            or sum(len(_text(block)) for block in blocks if isinstance(_text(block), str)) > MAX_LIST_PAGE_CHARS):
        return []
    ids = [block.get("id") for block in blocks]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        return []
    markers = [block for block in blocks if _marker(block) is not None]
    pairs = {marker["id"]: _paired_text(marker, blocks) for marker in markers}
    groups = []
    for parent in markers:
        heading = pairs[parent["id"]]
        if (_marker(parent) not in PARENT_MARKERS or not heading or not _text(heading).rstrip().endswith(":")
                or len(_text(heading)) > 180 or not _eligible(parent, page) or not _eligible(heading, page)):
            continue
        head_box, parent_box = heading["bbox"], parent["bbox"]
        height = head_box[3] - head_box[1]
        tolerance = max(2.0, height * .5)
        closing = [marker for marker in markers if _marker(marker) in PARENT_MARKERS
                   and marker is not parent and _box(marker) and marker["bbox"][3] < head_box[1]
                   and abs(marker["bbox"][0] - parent_box[0]) <= tolerance]
        closing.sort(key=lambda block: -block["bbox"][3])
        if not closing:
            continue
        boundary_marker = closing[0]
        boundary = pairs[boundary_marker["id"]]
        if (not boundary or not _eligible(boundary_marker, page) or not _eligible(boundary, page)
                or abs(boundary["bbox"][0] - head_box[0]) > tolerance
                or len(closing) > 1 and abs(closing[1]["bbox"][3] - boundary_marker["bbox"][3]) <= tolerance):
            continue
        lower = boundary["bbox"][3]
        nested = [marker for marker in markers if marker is not parent and _box(marker)
                  and _marker(marker) in CHILD_MARKERS
                  and lower < (marker["bbox"][1] + marker["bbox"][3]) / 2 < head_box[1]
                  and (height * .3 <= marker["bbox"][0] - head_box[0] <= height * 3
                       if _inline_marker(parent) else abs(marker["bbox"][0] - head_box[0]) <= tolerance)]
        nested.sort(key=lambda block: -block["bbox"][3])
        if not nested or len(nested) > MAX_LIST_ITEMS:
            continue
        items = []
        previous_bottom = head_box[1]
        invalid = False
        for marker in nested:
            block = pairs[marker["id"]]
            # A tightly attached dash can be a numeric sign, not a list marker.
            if (not block or not _box(block) or not height * .3 <= block["bbox"][0] - head_box[0] <= height * 3
                    or not _inline_marker(marker) and _marker(marker) in {"–", "—", "-"}
                    and block["bbox"][0] - marker["bbox"][2] < (block["bbox"][3] - block["bbox"][1]) * .75
                    or block["bbox"][3] >= previous_bottom + height * .25
                    or previous_bottom - block["bbox"][3] > height * 4
                    or block["bbox"][1] <= lower):
                invalid = True
                break
            items.append({"marker": marker, "block": block, "verified": _eligible(marker, page) and _eligible(block, page)})
            previous_bottom = block["bbox"][1]
        if invalid or previous_bottom - lower > height * 4:
            continue
        # A wrapped qualifier, competing title or merged cross-column text is
        # not silently skipped. A neighbouring column may interleave in parser
        # order, but cannot overlap this list's text region.
        right = max(item["block"]["bbox"][2] for item in items)
        occupied = {parent["id"], heading["id"], boundary_marker["id"], boundary["id"],
                    *(block["id"] for item in items for block in (item["marker"], item["block"]))}
        corridor = [parent_box[0], lower, right, head_box[3]]
        if any(block["id"] not in occupied and _box(block) and isinstance(_text(block), str) and _text(block).strip()
               and _intersects(corridor, block["bbox"]) for block in blocks):
            continue
        # Missing OCR material may occupy a gap without overlapping any known
        # item. Keep the verified local facts, but never certify this list as
        # complete or guess how many entries were lost in that region.
        unresolved_gap = any(region.get("reason") != "GRAPHIC_INTERPRETATION_UNAVAILABLE"
                             and (_box(region) is None or _intersects(corridor, region["bbox"]))
                             for region in page.get("unresolved_regions", []))
        used = [parent, heading, boundary_marker, boundary, *(block for item in items for block in (item["marker"], item["block"]))]
        revisions = {block.get("extraction_revision_id") for block in used}
        if (len(revisions) != 1 or None in revisions or any(block.get("page_index") != page.get("page_index") for block in used)
                or any(not isinstance(_text(block), str) or hashlib.sha256(_text(block).encode()).hexdigest() != block.get("source_text_hash")
                       for block in used)
                or sum(len(_text(block)) for block in used) > MAX_LIST_GROUP_CHARS):
            continue
        group = {"heading": heading, "parent_marker": parent, "boundary_marker": boundary_marker,
                 "boundary": boundary, "items": items,
                 "complete": not unresolved_gap and all(item["verified"] for item in items)}
        group["id"] = _group_identity(group)
        groups.append(group)
    return groups


def list_annotation(group, item):
    return {"revision": LIST_STRUCTURE_REVISION, "group_id": group["id"],
            "heading_block_id": group["heading"]["id"], "parent_marker_block_id": group["parent_marker"]["id"],
            "item_block_id": item["block"]["id"], "item_marker_block_id": item["marker"]["id"],
            "boundary_block_ids": [group["boundary_marker"]["id"], group["boundary"]["id"]],
            "item_index": group["items"].index(item), "item_count": len(group["items"]),
            "verified_item_count": sum(child["verified"] for child in group["items"]), "complete": group["complete"]}


def annotate_explicit_lists(page):
    """Add only structural metadata; never rewrite a source string or section."""
    for block in page.get("blocks", []):
        block.pop("list_structure", None)
    groups = explicit_list_groups(page)
    owners: dict[str, list[tuple[dict, dict]]] = {}
    for group in groups:
        for item in group["items"]:
            if item["verified"]:
                owners.setdefault(item["block"]["id"], []).append((group, item))
    for owners_for_block in owners.values():
        if len(owners_for_block) == 1:
            group, item = owners_for_block[0]
            item["block"]["list_structure"] = list_annotation(group, item)


def list_piece(block, kind=None):
    text = _text(block)
    piece = {"block_id": block["id"], "page_index": block["page_index"], "start_offset": 0, "end_offset": len(text),
             "text": text, "source_text_hash": block["source_text_hash"], "extraction_revision_id": block["extraction_revision_id"],
             "bbox": block["bbox"], "extraction_method": _method(block)}
    if kind:
        piece["kind"] = kind
    return piece


def list_context(group, item):
    annotation = list_annotation(group, item)
    return {key: annotation[key] for key in ("revision", "group_id", "item_index", "item_count", "verified_item_count", "complete")} | {
        "page_index": item["block"]["page_index"], "extraction_revision_id": item["block"]["extraction_revision_id"],
        "heading": list_piece(group["heading"]), "item": list_piece(item["block"]),
        "dependencies": [list_piece(group["parent_marker"], "parent_marker"), list_piece(item["marker"], "item_marker"),
                         list_piece(group["boundary_marker"], "list_boundary_marker"), list_piece(group["boundary"], "list_boundary")]}
