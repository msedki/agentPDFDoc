"""Scope needs actual enclosed paths; synthetic witnesses do not qualify PDFium."""

import copy
import ctypes

import pytest
from i5_rule_fixtures import adjacent_grouped_header_fixture, grouped_header_fixture, rule_record

from services.ingestion.docling_adapter import table_text
from services.ingestion.geometry import docling_box_to_pdf
from services.ingestion.table_geometry import build_table_quality, validate_table_quality
from services.ingestion.table_rules import (
    MAX_PATH_SEGMENTS,
    MAX_RULE_OBJECTS,
    native_rule_observations,
    prove_header_group,
    scoped_rule_observations,
)


def build(fixture):
    projected, quality = build_table_quality(fixture["data"], fixture["bbox"], fixture["parser_size"], fixture["page"],
                                            native=fixture["native"], source_sha256=fixture["page"]["source_sha256"])
    return projected, quality


def parent_cell(data):
    return next(cell for cell in data["table_cells"] if cell["text"] == "MODEL-Z7")


def parent_binding(quality):
    return next(binding for binding in quality["bindings"] if binding["row"] == 0)


def replay(fixture, data, quality):
    return validate_table_quality(table_text(data), {"table_data": data, "parser_table_data": fixture["data"], "table_quality": quality},
                                  source_sha256=fixture["page"]["source_sha256"], page_index=0,
                                  page=fixture["page"], table_bbox=fixture["bbox"])


def test_closed_native_rectangle_proves_group_scope_without_any_typical_value():
    fixture = grouped_header_fixture()
    data, quality = build(fixture)
    parent = parent_cell(data)
    assert parent["start_col_offset_idx"] == 1 and parent["end_col_offset_idx"] == 4
    assert parent["bbox"] == {"l": 278.0, "t": 24.0, "r": 310.0, "b": 32.0, "coord_origin": "TOPLEFT"}
    assert parent["row_span"] == 1
    assert not any(cell["start_row_offset_idx"] == 2 and cell["start_col_offset_idx"] == 2 for cell in data["table_cells"])
    binding = parent_binding(quality)
    assert binding["scope_bbox"] == {"l": 150.0, "t": 18.0, "r": 425.0, "b": 60.0, "coord_origin": "TOPLEFT"}
    assert binding["header_group"]["columns"] == [1, 2, 3]
    assert set(binding["header_group"]["sides"]) == {"left", "top", "right", "bottom"}
    assert len(binding["header_group"]["child_header_observation_ids"]) == 3
    assert quality["native_glyphs"]["rules"]["scope_bbox"] == fixture["bbox"]
    assert replay(fixture, data, quality)["state"] == "supported"


@pytest.mark.parametrize("side", range(4))
def test_missing_enclosure_side_never_expands_a_title_by_its_centre(side):
    fixture = grouped_header_fixture()
    fixture["native"]["rules"]["objects"].pop(side)
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)
    assert replay(fixture, data, quality)["state"] == "supported"


def test_old_glyph_only_witness_does_not_receive_new_rule_evidence():
    fixture = grouped_header_fixture()
    del fixture["native"]["rules"]
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "rules" not in quality["native_glyphs"]
    assert replay(fixture, data, quality)["state"] == "supported"


def test_separate_adjacent_enclosure_cannot_lend_its_scope():
    fixture = grouped_header_fixture()
    fixture["native"]["rules"] = rule_record([[15, 382, 250, 382], [15, 340, 250, 340],
                                              [15, 340, 15, 382], [250, 340, 250, 382]],
                                             source_sha256=fixture["page"]["source_sha256"])
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)


@pytest.mark.parametrize("line", [[250, 340, 250, 360], [150, 363, 425, 363]])
def test_interior_separator_prevents_enclosure_from_claiming_all_children(line):
    fixture = grouped_header_fixture()
    extra = rule_record([line], source_sha256=fixture["page"]["source_sha256"])["objects"][0]
    extra.update(id="o4", object_index=4)
    fixture["native"]["rules"]["objects"].append(extra)
    fixture["native"]["rules"].update(object_count=5, segment_count=10)
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)


def test_a_frame_enclosing_data_rows_does_not_create_a_header_row_span():
    fixture = grouped_header_fixture()
    bottom = fixture["native"]["rules"]["objects"][1]
    bottom["segments"][0]["point"][1] = bottom["segments"][1]["point"][1] = 305
    bottom["bbox"] = [14.75, 304.75, 480.25, 305.25]
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1 and parent_cell(data)["row_span"] == 1
    assert "header_group" not in parent_binding(quality)


def test_parser_row_span_does_not_extend_the_proven_header_frame():
    fixture = grouped_header_fixture()
    fixture["data"]["table_cells"][2].update(row_span=2, end_row_offset_idx=2)
    data, quality = build(fixture)
    assert parent_cell(data)["row_span"] == 1
    assert parent_binding(quality)["header_group"]["columns"] == [1, 2, 3]


def test_competing_titles_in_one_frame_do_not_gain_each_others_columns():
    fixture = grouped_header_fixture()
    fixture["data"]["table_cells"][1]["bbox"]["t"] = 24
    fixture["data"]["table_cells"][1]["bbox"]["r"] = 204
    fixture["data"]["table_cells"][1]["text"] = "ALT-Q8 Min"
    glyphs = fixture["native"]["glyphs"]
    for offset, character in enumerate("ALT-Q8"):
        index = len(glyphs)
        glyphs.append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                       "bbox": [180 + offset * 4, 368, 184 + offset * 4, 376], "generated": 0, "unicode_map_error": 0})
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert not any("header_group" in binding for binding in quality["bindings"])


def test_two_closed_groups_have_separate_children_without_subject_inheritance():
    headers = [{"id": f"h{index}", "text": text, "display_bbox": [x, 45, x + 15, 53], "origin": "native", "state": "supported"}
               for index, (x, text) in enumerate(((60, "Min"), (160, "Typ"), (290, "Max"), (390, "Units")))]
    first = {"id": "p1", "text": "MODEL-Z7", "display_bbox": [100, 24, 132, 32], "origin": "native", "state": "supported"}
    second = {"id": "p2", "text": "ALT-Q8", "display_bbox": [330, 24, 354, 32], "origin": "native", "state": "supported"}
    lines = [[20, 18, 450, 18], [20, 60, 450, 60], [20, 18, 20, 60], [230, 18, 230, 60], [450, 18, 450, 60]]
    record = rule_record(lines, source_sha256="a" * 64)
    one = prove_header_group(record, [first], headers, headers + [first, second], table_bbox=[15, 10, 480, 100], to_display=lambda box: box)
    two = prove_header_group(record, [second], headers, headers + [first, second], table_bbox=[15, 10, 480, 100], to_display=lambda box: box)
    assert one["columns"] == [0, 1] and two["columns"] == [2, 3]
    assert one["parent_observation_ids"] == ["p1"] and two["parent_observation_ids"] == ["p2"]
    assert not set(one["child_header_observation_ids"]) & set(two["child_header_observation_ids"])


def test_two_group_projection_keeps_the_adjacent_subject_outside_the_first_scope():
    fixture = adjacent_grouped_header_fixture()
    data, quality = build(fixture)
    first = parent_cell(data)
    second = next(cell for cell in data["table_cells"] if cell["text"] == "ALT-Q8")
    assert (first["start_col_offset_idx"], first["end_col_offset_idx"]) == (1, 3)
    assert (second["start_col_offset_idx"], second["end_col_offset_idx"]) == (3, 5)
    assert replay(fixture, data, quality)["state"] == "supported"


def test_uncertain_native_child_cannot_establish_an_extended_parent_scope():
    fixture = grouped_header_fixture()
    for glyph in fixture["native"]["glyphs"]:
        if 180 <= glyph["bbox"][0] < 192 and glyph["bbox"][1] == 347:
            glyph["unicode_map_error"] = 1
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert not any("header_group" in binding for binding in quality["bindings"])


def test_thin_filled_closed_rectangles_are_rules_but_a_filled_panel_is_not():
    fixture = grouped_header_fixture()
    path = fixture["native"]["rules"]["objects"][0]
    path.update(fill_mode=1, stroke=False, bbox=[15, 381.5, 480, 382.5], segments=[
        {"index": index, "type": 2 if index == 0 else 0, "point": point, "close": index == 3}
        for index, point in enumerate(([15, 381.5], [480, 381.5], [480, 382.5], [15, 382.5]))])
    fixture["native"]["rules"]["segment_count"] = 10
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 3
    assert parent_binding(quality)["header_group"]["sides"]["top"] == ["o0:fill"]
    path["segments"][0]["point"][1] = path["segments"][1]["point"][1] = 350
    path["bbox"][1] = 350
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)


@pytest.mark.parametrize("change", [
    {"active": False}, {"active": None}, {"has_transparency": True}, {"stroke_rgba": [0, 0, 0, 128]},
    {"stroke_rgba": [255, 255, 255, 255]}, {"dash_count": 1}, {"stroke_width": 4},
    {"clip": {"handle_present": False, "path_count": None}},
    {"clip": {"handle_present": True, "path_count": 0}}, {"clip": {"handle_present": True, "path_count": 1}},
    {"matrix": None}, {"matrix": [1, .1, 0, 1, 0, 0]},
])
def test_unknown_or_noncontinuous_paint_never_certifies_an_enclosure(change):
    fixture = grouped_header_fixture()
    fixture["native"]["rules"]["objects"][0].update(change)
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)


def test_unresolved_form_covering_header_is_an_obstruction():
    fixture = grouped_header_fixture()
    fixture["native"]["rules"]["objects"].append({"id": "o4", "object_index": 4, "type": 5,
                                                    "bbox": [200, 355, 350, 380], "active": True})
    fixture["native"]["rules"]["object_count"] = 5
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert "header_group" not in parent_binding(quality)


def test_paths_outside_table_are_not_duplicated_into_its_bindings():
    fixture = grouped_header_fixture()
    outside = rule_record([[20, 200, 120, 200]], source_sha256=fixture["page"]["source_sha256"])["objects"][0]
    outside.update(id="o4", object_index=4)
    fixture["native"]["rules"]["objects"].append(outside)
    fixture["native"]["rules"].update(object_count=5, segment_count=10)
    data, quality = build(fixture)
    assert len(quality["native_glyphs"]["rules"]["objects"]) == 4
    assert all("segments" not in binding for binding in quality["bindings"])
    assert replay(fixture, data, quality)["state"] == "supported"


@pytest.mark.parametrize("alteration", ["scope", "side", "matrix", "paint", "source", "page"])
def test_catalogue_replay_rejects_tampered_rule_or_binding(alteration):
    fixture = grouped_header_fixture()
    data, quality = build(fixture)
    if alteration == "scope":
        parent_binding(quality)["header_group"]["columns"] = [0, 1, 2, 3]
    elif alteration == "side":
        parent_binding(quality)["header_group"]["sides"]["left"] = ["o999:s1"]
    elif alteration == "matrix":
        quality["native_glyphs"]["rules"]["objects"][0]["matrix"][5] += 20
    elif alteration == "paint":
        quality["native_glyphs"]["rules"]["objects"][0]["stroke_rgba"][3] = 0
    elif alteration == "source":
        quality["native_glyphs"]["rules"]["source_sha256"] = "a" * 64
    else:
        quality["native_glyphs"]["rules"]["page_index"] = 1
    assert replay(fixture, data, quality)["state"] == "unavailable"


def test_path_matrix_is_applied_before_frame_selection():
    fixture = grouped_header_fixture()
    for path in fixture["native"]["rules"]["objects"]:
        path["matrix"] = [1, 0, 0, 1, 50, 100]
        for segment in path["segments"]:
            segment["point"][0] -= 50
            segment["point"][1] -= 100
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 3
    assert replay(fixture, data, quality)["state"] == "supported"


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_page_rotation_preserves_physical_rule_and_literal_provenance(rotation):
    fixture = grouped_header_fixture()
    original_page = copy.deepcopy(fixture["page"])
    fixture["page"]["rotation"] = rotation
    fixture["page"]["crop_box"] = fixture["page"]["effective_box"] = ([0, 0, 400, 500] if rotation in {90, 270} else [0, 0, 500, 400])
    def mapped(box):
        return docling_box_to_pdf({"l": box[0], "t": 400 - box[3], "r": box[2], "b": 400 - box[1], "coord_origin": "TOPLEFT"},
                                  fixture["parser_size"], fixture["page"])
    for glyph in fixture["native"]["glyphs"]:
        glyph["bbox"] = mapped(glyph["bbox"])
    for path in fixture["native"]["rules"]["objects"]:
        path["bbox"] = mapped(path["bbox"])
        for segment in path["segments"]:
            x, y = segment["point"]
            point = mapped([x, y, x, y])
            segment["point"] = point[:2]
    fixture["bbox"] = mapped(fixture["bbox"])
    data, quality = build(fixture)
    assert original_page["rotation"] == 0
    assert parent_cell(data)["col_span"] == 3
    assert parent_cell(data)["bbox"]["t"] == 24
    assert replay(fixture, data, quality)["state"] == "supported"


def test_incomplete_native_capture_stays_explicit_and_replayable_without_scope_gain():
    fixture = grouped_header_fixture()
    fixture["native"]["rules"].update(complete=False, limit_reason="native_rule_segment_limit")
    data, quality = build(fixture)
    assert parent_cell(data)["col_span"] == 1
    assert quality["native_glyphs"]["rules"]["limit_reason"] == "native_rule_segment_limit"
    assert replay(fixture, data, quality)["state"] == "supported"


class OversizedRaw:
    def FPDFPage_CountObjects(self, page):
        return MAX_RULE_OBJECTS + 1

    def FPDFPage_GetObject(self, page, index):
        pytest.fail("an excessive count must be refused before accessing objects")


def test_native_object_cap_precedes_any_object_allocation():
    record = native_rule_observations(object(), OversizedRaw(), source_sha256="a" * 64, page_index=0)
    assert not record["complete"] and record["objects"] == []
    assert record["limit_reason"] == "native_rule_object_limit"


class OversizedSegmentsRaw:
    def FPDFPage_CountObjects(self, page):
        return 1

    def FPDFPage_GetObject(self, page, index):
        return object()

    def FPDFPageObj_GetType(self, obj):
        return 2

    def FPDFPageObj_GetIsActive(self, obj, pointer):
        pointer._obj.value = 1
        return 1

    def FPDFPageObj_GetBounds(self, obj, *values):
        for pointer, value in zip(values, [0, 0, 100, 100], strict=True):
            pointer._obj.value = value
        return 1

    def FPDFPath_CountSegments(self, obj):
        return MAX_PATH_SEGMENTS + 1

    def FPDFPath_GetPathSegment(self, obj, index):
        pytest.fail("an excessive segment count must be refused before allocating segments")


def test_native_segment_cap_precedes_any_segment_allocation():
    record = native_rule_observations(object(), OversizedSegmentsRaw(), source_sha256="a" * 64, page_index=0)
    assert not record["complete"] and record["objects"] == []
    assert record["limit_reason"] == "native_rule_segment_limit"


def test_missing_native_api_remains_unavailable_instead_of_claiming_no_obstruction():
    record = native_rule_observations(object(), object(), source_sha256="a" * 64, page_index=0)
    assert not record["complete"] and record["limit_reason"] == "native_rule_api_or_geometry_unavailable"
    scoped = scoped_rule_observations(record, source_sha256="a" * 64, page_index=0, table_bbox=[0, 0, 100, 100])
    assert scoped_rule_observations(scoped, source_sha256="a" * 64, page_index=0, table_bbox=[0, 0, 100, 100]) == scoped


class Matrix(ctypes.Structure):
    _fields_ = [(name, ctypes.c_float) for name in ("a", "b", "c", "d", "e", "f")]


class NativeRawDouble(OversizedSegmentsRaw):
    FS_MATRIX = Matrix

    def FPDFPath_CountSegments(self, obj):
        return 2

    def FPDFPageObj_GetMatrix(self, obj, pointer):
        for field, value in zip(("a", "b", "c", "d", "e", "f"), (1, 0, 0, 1, 5, 7), strict=True):
            setattr(pointer._obj, field, value)
        return 1

    def FPDFPath_GetDrawMode(self, obj, fill, stroke):
        fill._obj.value, stroke._obj.value = 0, 1
        return 1

    def FPDFPageObj_GetStrokeWidth(self, obj, width):
        width._obj.value = .5
        return 1

    def FPDFPageObj_GetClipPath(self, obj):
        return object()

    def FPDFClipPath_CountPaths(self, clip):
        return -1

    def FPDFPageObj_GetStrokeColor(self, obj, *channels):
        for pointer, value in zip(channels, (0, 0, 0, 255), strict=True):
            pointer._obj.value = value
        return 1

    FPDFPageObj_GetFillColor = FPDFPageObj_GetStrokeColor

    def FPDFPageObj_HasTransparency(self, obj):
        return 0

    def FPDFPageObj_GetDashCount(self, obj):
        return 0

    def FPDFPath_GetPathSegment(self, obj, index):
        return index + 1

    def FPDFPathSegment_GetPoint(self, segment, x, y):
        x._obj.value, y._obj.value = ((10, 20) if segment == 1 else (90, 20))
        return 1

    def FPDFPathSegment_GetType(self, segment):
        return 2 if segment == 1 else 0

    def FPDFPathSegment_GetClose(self, segment):
        return 0


def test_native_capture_retains_real_api_fields_without_rendering_or_freeing_borrowed_objects():
    result = native_rule_observations(object(), NativeRawDouble(), source_sha256="a" * 64, page_index=2)
    assert result["complete"] and result["segment_count"] == 2
    path = result["objects"][0]
    assert path["matrix"] == [1, 0, 0, 1, 5, 7]
    assert path["segments"][1]["point"] == [90, 20]
    assert path["clip"] == {"handle_present": True, "path_count": -1}
    assert path["stroke_rgba"] == [0, 0, 0, 255] and path["active"] is True
