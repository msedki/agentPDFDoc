"""Pure geometric counterexamples for fragmented pre-table bands.

All text and rectangles are synthetic. No OCR, native PDF or engine accuracy is
claimed by these tests; OCR reading quality remains a separate publication gate.
"""

import copy
import hashlib

import pytest
from test_i5_table_conditions import SOURCE_HASH, block, condition_page

from services.ingestion.table_geometry import (
    build_table_general_conditions,
    table_general_condition_fragments,
    validate_table_general_conditions,
)


def fragmented_band():
    table, _, page = condition_page()
    heading = block("heading", "Performance characteristics", [20, 310, 170, 322], "heading")
    words = "Marker identifies values specified throughout the entire rated normal operating region".split()
    fragments = []
    left = 180
    for index, text in enumerate(words):
        width = len(text) * 2.5
        fragments.append(block(f"fragment-{index}", text, [left, 312, left + width, 320]))
        left += width + 3
    condition = block("conditions", "TA = 18°C, supply = 4V unless otherwise noted.", [20, 290, 470, 302])
    blocks = [heading, *fragments, condition, table]
    table["metadata"]["table_general_conditions"] = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    return table, blocks, page


def test_thirteen_fragments_form_two_pieces_without_inventing_a_source_parent():
    table, blocks, page = fragmented_band()
    annotation = validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "supported" and annotation["schema_version"] == "table-general-conditions-v2"
    assert len(annotation["pieces"]) == 2
    line, condition = annotation["pieces"]
    assert line["kind"] == "line_fragments" and len(line["fragments"]) == 12
    assert not {"block_id", "text", "source_text_hash", "start_offset", "end_offset"} & line.keys()
    assert condition["block_id"] == "conditions"
    assert line["bbox"] == [20, 310, blocks[-3]["bbox"][2], 322]
    assert line["display_bbox"] == [20, 78, blocks[-3]["bbox"][2], 90]
    fragments = table_general_condition_fragments(annotation)
    assert len(fragments) == 13
    for fragment, original in zip(fragments, blocks[:-1], strict=True):
        assert fragment["block_id"] == original["id"]
        assert fragment["text"] == original["raw_text"]
        assert fragment["source_text_hash"] == hashlib.sha256(original["raw_text"].encode()).hexdigest()
        assert (fragment["start_offset"], fragment["end_offset"]) == (0, len(original["raw_text"]))
        assert fragment["bbox"] == original["bbox"]
        assert fragment["page_index"] == 0
        assert fragment["version_id"] == original["version_id"]
        assert fragment["extraction_revision_id"] == original["extraction_revision_id"]


def test_fragment_order_is_reconstructed_from_positions_not_input_order():
    table, blocks, page = fragmented_band()
    expected = table["metadata"]["table_general_conditions"]
    assert build_table_general_conditions(table, list(reversed(blocks)), page, source_sha256=SOURCE_HASH) == expected


def test_existing_unfragmented_annotation_remains_byte_identical():
    table, blocks, page = condition_page()
    annotation = validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["schema_version"] == "table-general-conditions-v1"
    assert annotation["policy"] == "explicit-pretable-condition-band-v1"
    assert table_general_condition_fragments(annotation) == annotation["pieces"]
    assert not any("fragments" in piece for piece in annotation["pieces"])


@pytest.mark.parametrize("changed", ["missing", "text", "hash", "revision", "version", "page", "bbox", "order", "offset", "group_bbox"])
def test_every_original_identity_offset_and_rectangle_remains_revalidated(changed):
    table, blocks, page = fragmented_band()
    if changed == "missing":
        blocks.pop(4)
    elif changed in {"order", "offset", "group_bbox"}:
        line = table["metadata"]["table_general_conditions"]["pieces"][0]
        if changed == "order":
            line["fragments"][3:5] = reversed(line["fragments"][3:5])
        elif changed == "offset":
            line["fragments"][4]["start_offset"] = 1
        else:
            line["bbox"][0] += 1
    elif changed == "bbox":
        blocks[4]["bbox"] = [v + 1 for v in blocks[4]["bbox"]]
    elif changed == "text":
        blocks[4].update(raw_text="altered", text="altered", source_text_hash=hashlib.sha256(b"altered").hexdigest())
    else:
        key = {"hash": "source_text_hash", "revision": "extraction_revision_id", "version": "version_id", "page": "page_index"}[changed]
        blocks[4][key] = 1 if changed == "page" else "other"
    assert validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)["state"] == "unavailable"


def test_interfragment_column_gap_is_preserved_as_a_separate_piece():
    table, blocks, page = fragmented_band()
    # Shorten only the heading rectangle; the remaining words still share their
    # own strip and spacing. The 30-point gap cannot enter one line piece.
    blocks[0]["bbox"][2] = 150
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "supported" and len(annotation["pieces"]) == 3
    assert annotation["pieces"][0]["block_id"] == "heading"
    assert annotation["pieces"][1]["fragments"][0]["block_id"] == "fragment-0"


def test_eight_piece_cap_is_not_raised_for_spaced_columns():
    table, blocks, page = fragmented_band()
    # Eleven independent narrow columns at one baseline must not be joined.
    for index, item in enumerate(blocks[1:-2]):
        left = 40 + index * 38
        item["bbox"] = [left, 294, left + 4, 300]
    blocks[-2]["bbox"] = [20, 282, 470, 288]
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable" and annotation["reasons"] == ["general_condition_band_limit"]


def test_eight_piece_cap_is_not_raised_for_nine_actual_lines():
    table, _, page = condition_page()
    heading = block("heading", "Performance characteristics", [20, 308, 250, 310], "heading")
    words = [block(f"word-{index}", "scope", [20, 305 - index * 3, 45, 307 - index * 3]) for index in range(7)]
    condition = block("condition", "TA = 18°C unless otherwise noted.", [20, 284, 470, 286])
    annotation = build_table_general_conditions(table, [heading, *words, condition, table], page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable" and annotation["reasons"] == ["general_condition_band_limit"]


def test_overlapping_rectangles_do_not_create_an_arbitrary_word_order():
    table, blocks, page = fragmented_band()
    blocks[3]["bbox"][0] = blocks[2]["bbox"][2] - 1
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable"


def test_tall_fragment_cannot_bridge_separate_lines():
    table, blocks, page = fragmented_band()
    blocks[3]["bbox"][1] = 296
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable"


@pytest.mark.parametrize("dimension", [0, 1])
def test_zero_area_fragment_does_not_attest_a_line(dimension):
    table, blocks, page = fragmented_band()
    blocks[3]["bbox"][dimension + 2] = blocks[3]["bbox"][dimension]
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable"


@pytest.mark.parametrize("limit", ["MAX_GENERAL_BLOCKS", "MAX_GENERAL_CHARS", "MAX_GENERAL_PIECES"])
def test_all_existing_budgets_still_fail_closed(monkeypatch, limit):
    table, blocks, page = fragmented_band()
    value = {"MAX_GENERAL_BLOCKS": len(blocks) - 1, "MAX_GENERAL_CHARS": 20, "MAX_GENERAL_PIECES": 1}[limit]
    monkeypatch.setattr("services.ingestion.table_geometry." + limit, value)
    assert build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)["state"] == "unavailable"


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_grouping_uses_the_verified_display_frame(rotation):
    from services.ingestion.geometry import display_point_to_pdf

    table, blocks, page = fragmented_band()
    before = table_general_condition_fragments(table["metadata"]["table_general_conditions"])
    frame = [12, 19, 412, 519] if rotation in (90, 270) else [12, 19, 512, 419]
    for item in blocks:
        box = item["bbox"]
        # This inverse accepts displayed bottom-left coordinates. Our initial
        # zero-rotation PDF rectangle already uses that convention.
        corners = [display_point_to_pdf(x, y, frame, rotation) for x in (box[0], box[2]) for y in (box[1], box[3])]
        item["bbox"] = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
    page.update(rotation=rotation, crop_box=frame, effective_box=frame)
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "supported" and len(annotation["pieces"]) == 2
    assert [fragment["block_id"] for fragment in table_general_condition_fragments(annotation)] == [fragment["block_id"] for fragment in before]


def test_utility_helper_rejects_unreconstructed_nested_or_over_budget_shapes():
    table, _, _ = fragmented_band()
    annotation = table["metadata"]["table_general_conditions"]
    malformed = copy.deepcopy(annotation)
    malformed["state"] = "unavailable"
    assert table_general_condition_fragments(malformed) == []
    malformed = copy.deepcopy(annotation)
    malformed["pieces"][0]["fragments"][0] = {"kind": "line_fragments", "fragments": []}
    assert table_general_condition_fragments(malformed) == []
    malformed = copy.deepcopy(annotation)
    malformed["pieces"] *= 5
    assert table_general_condition_fragments(malformed) == []
