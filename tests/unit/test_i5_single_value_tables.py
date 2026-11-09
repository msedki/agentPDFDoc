"""Literal three-column value tables; synthetic glyphs do not qualify OCR."""

import copy
from itertools import permutations

import pytest

from services.ingestion.docling_adapter import table_text
from services.ingestion.table_geometry import build_table_quality, validate_table_quality
from tests.unit.test_i5_table_geometry import SOURCE_HASH, cell, glyphs_at


def single_value_fixture(columns, *, corrupt_columns=False, overlapping_headers=False,
                         displaced_unit_header=False, uncertain_value_header=False,
                         omit_unit_value=False, observations=True):
    positions = [20, 200, 330, 440]
    lines, cells = [], []
    for column, ((header, value), x) in enumerate(zip(columns, positions, strict=False)):
        header_x = 45 if overlapping_headers and column == 1 else x
        header_y = 45 if displaced_unit_header and header == "Unit" else 30
        lines.append((header_x, header_y, header))
        cells.append(cell(header, 0, column, [header_x, header_y, header_x + len(header) * 4, header_y + 8], header=True))
        if omit_unit_value and header in {"Unit", "Unité"}:
            continue
        lines.append((x, 60, value))
        cells.append(cell(value, 1, column, [x, 60, x + len(value) * 4, 68]))
    if corrupt_columns:
        for source_cell in cells:
            source_cell.update(start_col_offset_idx=0, end_col_offset_idx=1)
    original = {"num_rows": 2, "num_cols": len(columns), "table_cells": cells}
    page = {"page_index": 0, "crop_box": [0, 0, 550, 400], "effective_box": [0, 0, 550, 400], "rotation": 0}
    native = glyphs_at(lines) if observations else None
    if uncertain_value_header:
        for glyph in native["glyphs"]:
            if glyph["bbox"][0] == 200 and glyph["bbox"][1] == 362:
                glyph["unicode_map_error"] = 1
    projected, quality = build_table_quality(original, [10, 310, 520, 380], (550, 400), page,
                                            native=native, source_sha256=SOURCE_HASH)
    metadata = {"table_data": projected, "parser_table_data": original, "table_quality": quality}
    return projected, quality, metadata


def cells_by_position(data):
    return {(item["start_row_offset_idx"], item["start_col_offset_idx"]): item for item in data["table_cells"]}


@pytest.mark.parametrize("headers", [
    ("Équipement", "Valeur", "Unité"), ("Equipment", "Value", "Unit"),
    ("Libellé", "Valeur", "Unités"), ("Label", "Value", "Units"),
    ("Paramètre", "Valeur", "Unité"), ("Parameter", "Value", "Unit"),
    ("Référence", "Valeur", "Unité"), ("Reference", "Value", "Unit"),
])
def test_single_value_headers_keep_their_literal_meaning_and_observed_cells(headers):
    values = ("Pressure", "7.4", "kPa")
    data, quality, metadata = single_value_fixture(tuple(zip(headers, values, strict=True)))
    cells = cells_by_position(data)
    assert quality["state"] == "supported"
    assert [cells[(0, column)]["text"] for column in range(3)] == list(headers)
    assert [cells[(1, column)]["text"] for column in range(3)] == list(values)
    value_binding = next(binding for binding in quality["bindings"] if (binding["row"], binding["column"]) == (1, 1))
    assert value_binding["header_text"] == headers[1]
    assert value_binding["header_observation_ids"] and value_binding["value_observation_ids"]
    assert validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0)["state"] == "supported"


@pytest.mark.parametrize("columns", list(permutations((("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")))))
def test_permuted_headers_follow_geometry_even_when_parser_column_indices_are_wrong(columns):
    data, quality, _ = single_value_fixture(columns, corrupt_columns=True)
    cells = cells_by_position(data)
    assert quality["state"] == "supported"
    assert [cells[(0, column)]["text"] for column in range(3)] == [header for header, _ in columns]
    assert [cells[(1, column)]["text"] for column in range(3)] == [value for _, value in columns]
    for column, (header, _) in enumerate(columns):
        binding = next(item for item in quality["bindings"] if (item["row"], item["column"]) == (1, column))
        assert binding["header_text"] == header


@pytest.mark.parametrize("columns", [
    (("Equipment", "Pressure"), ("Value", "7.4")),
    (("Equipment", "Pressure"), ("Value", "7.4"), ("Measure", "kPa")),
    (("Unknown", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")),
    (("Equipment", "Pressure"), ("Value", "7.4"), ("Value", "9.2"), ("Unit", "kPa")),
    (("Equipment", "Pressure"), ("Value", "7.4"), ("Valeur", "9.2"), ("Unit", "kPa")),
    (("Equipment", "Pressure"), ("Value", "7.4"), ("Typ", "9.2"), ("Unit", "kPa")),
])
def test_missing_or_ambiguous_roles_preserve_the_unqualified_original_table(columns):
    data, quality, metadata = single_value_fixture(columns)
    assert quality["state"] == "unavailable"
    assert data == metadata["parser_table_data"]
    assert quality["bindings"] == []


def test_overlapping_generic_headers_do_not_establish_column_roles():
    data, quality, metadata = single_value_fixture(
        (("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")), overlapping_headers=True)
    assert quality["state"] == "unavailable"
    assert data == metadata["parser_table_data"]


def test_a_displaced_unit_does_not_complete_the_required_physical_header_band():
    data, quality, metadata = single_value_fixture(
        (("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")), displaced_unit_header=True)
    assert quality["state"] == "unavailable"
    assert data == metadata["parser_table_data"]


def test_uncertain_value_heading_does_not_qualify_its_values():
    _, quality, _ = single_value_fixture(
        (("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")), uncertain_value_header=True)
    bindings = {(item["row"], item["column"]): item for item in quality["bindings"]}
    assert quality["state"] == "partial"
    assert bindings[(1, 1)]["header_text"] == "Value"
    assert bindings[(1, 1)]["state"] == "ambiguous"
    assert "native_glyph_mapping_unverified" in bindings[(1, 1)]["reasons"]
    assert bindings[(1, 0)]["state"] == bindings[(1, 2)]["state"] == "supported"


def test_missing_row_unit_is_left_empty_without_borrowing_or_invention():
    data, _, _ = single_value_fixture(
        (("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")), omit_unit_value=True)
    cells = cells_by_position(data)
    assert cells[(1, 1)]["text"] == "7.4"
    assert (1, 2) not in cells
    assert "kPa" not in table_text(data)


def test_a_literal_value_binding_cannot_be_changed_to_typical_by_catalogue_metadata():
    data, quality, metadata = single_value_fixture((("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")))
    assert quality["state"] == "supported"
    changed = copy.deepcopy(metadata)
    value_binding = next(item for item in changed["table_quality"]["bindings"] if (item["row"], item["column"]) == (1, 1))
    value_binding["header_text"] = "Typ"
    replay = validate_table_quality(table_text(data), changed, source_sha256=SOURCE_HASH, page_index=0)
    assert replay["state"] == "unavailable" and replay["reasons"] == ["table_quality_replay_mismatch"]


def test_parser_headers_without_source_observations_never_certify_a_generic_value():
    data, quality, metadata = single_value_fixture(
        (("Equipment", "Pressure"), ("Value", "7.4"), ("Unit", "kPa")), observations=False)
    assert quality["state"] == "unavailable"
    assert data == metadata["parser_table_data"]
