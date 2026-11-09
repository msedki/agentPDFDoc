"""Synthetic geometry contracts; these doubles do not qualify a PDF engine."""

import copy
import hashlib

import pytest

from services.ingestion.docling_adapter import document_to_pages, table_text

SOURCE_HASH = hashlib.sha256(b"generic synthetic source").hexdigest()


def glyphs_at(lines, *, height=400):
    glyphs = []
    for x, y, text in lines:
        for character in text:
            index = len(glyphs)
            glyphs.append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                           "bbox": [x, height - y - 8, x + 4, height - y], "generated": 0, "unicode_map_error": 0})
            x += 4
    return {"schema_version": "pdfium-glyphs-v1", "source_sha256": SOURCE_HASH, "page_index": 0,
            "coordinate_frame": "pdf_user_space_unrotated", "glyphs": glyphs, "complete": True, "limit_reason": None}


def cell(text, row, column, box, *, header=False, row_header=False, row_span=1):
    return {"text": text, "start_row_offset_idx": row, "end_row_offset_idx": row + row_span,
            "start_col_offset_idx": column, "end_col_offset_idx": column + 1,
            "row_span": row_span, "col_span": 1, "column_header": header, "row_header": row_header,
            "row_section": False, "bbox": {"l": box[0], "t": box[1], "r": box[2], "b": box[3], "coord_origin": "TOPLEFT"}}


def extract_fixture(*, merged=True, missing_min=False, header_names=None, observations=True, transform=None):
    names = header_names or ["Parameter", "Min", "Typ", "Max", "Units"]
    xs = [20, 200, 300, 400, 450]
    lines = [(x, 30, text) for x, text in zip(xs, names, strict=True)]
    cells = [cell(text, 0, i, [x, 30, x + len(text) * 4, 38], header=True)
             for i, (x, text) in enumerate(zip(xs, names, strict=True))]
    if missing_min:
        lines.extend([(20, 60, "Nominal voltage at 10°C"), (300, 60, "1.25"), (450, 60, "V")])
        cells.extend([cell("Nominal voltage at 10°", 1, 0, [20, 60, 104, 68], row_header=True),
                      cell("C 1.25 V", 1, 1, [104, 60, 454, 68])])
    else:
        values = ["Pressure", "1.8", "2.2", "2.9", "bar"]
        lines.extend((x, 60, text) for x, text in zip(xs, values, strict=True))
        if merged:
            cells.append(cell("Pressure 1.8 2.2 2.9 bar", 1, 0, [20, 60, 462, 68], row_header=True))
        else:
            cells.extend(cell(text, 1, i, [x, 60, x + len(text) * 4, 68], row_header=i == 0)
                         for i, (x, text) in enumerate(zip(xs, values, strict=True)))
    data = {"num_rows": 2, "num_cols": 5, "table_cells": cells}
    item = {"self_ref": "#/tables/0", "label": "table", "data": copy.deepcopy(data),
            "prov": [{"page_no": 1, "bbox": {"l": 15, "t": 20, "r": 480, "b": 90, "coord_origin": "TOPLEFT"}}]}
    document = {"tables": [item], "pages": {"1": {"size": {"width": 500, "height": 400}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 500, 400], "effective_box": [0, 0, 500, 400],
            "rotation": 0, "classification": "native", "source_sha256": SOURCE_HASH}
    observed = {0: {"source_sha256": SOURCE_HASH, "native_glyphs": glyphs_at(lines)}} if observations else None
    if transform:
        transform(observed, page, document)
    pages, warnings = document_to_pages(document, [page], "version", "revision", "structured", observed)
    return pages[0]["blocks"][0], data, warnings


def data_cells(block):
    return {(item["start_row_offset_idx"], item["start_col_offset_idx"]): item
            for item in block["metadata"]["table_data"]["table_cells"]}


def test_merged_row_is_rebuilt_from_literal_glyphs_under_explicit_headers():
    block, original, _ = extract_fixture()
    cells = data_cells(block)
    assert [cells[(1, column)]["text"] for column in range(5)] == ["Pressure", "1.8", "2.2", "2.9", "bar"]
    assert block["metadata"]["parser_table_data"] == original
    assert block["text"] == table_text(block["metadata"]["table_data"])
    assert block["source_text_hash"] == hashlib.sha256(block["text"].encode()).hexdigest()


def test_blank_minimum_does_not_receive_a_typical_value_from_wrong_parser_index():
    block, _, _ = extract_fixture(missing_min=True)
    cells = data_cells(block)
    assert not cells.get((1, 1), {}).get("text")
    assert cells[(1, 2)]["text"] == "1.25"
    assert cells[(1, 4)]["text"] == "V"
    assert "10°C" in cells[(1, 0)]["text"]


def test_geometry_proof_is_bound_to_source_page_and_observations():
    block, _, _ = extract_fixture(merged=False)
    quality = block["metadata"].get("table_quality", {})
    assert quality.get("source_sha256") == SOURCE_HASH
    assert quality.get("page_index") == 0
    assert quality.get("observations") and quality.get("bindings")
    assert all(item.get("glyph_ids") for item in quality["observations"])


@pytest.mark.parametrize("names", [["Parameter", "Max", "Typ", "Min", "Units"],
                                    ["Parameter", "Min", "Typ", "Max", "Units"]])
def test_header_permutation_changes_role_not_observed_value_location(names):
    block, _, _ = extract_fixture(header_names=names)
    quality = block["metadata"].get("table_quality", {})
    bindings = {(entry["row"], entry["column"]): entry for entry in quality.get("bindings", [])}
    assert bindings[(1, 1)]["header_text"] == names[1]
    assert data_cells(block)[(1, 1)]["text"] == "1.8"


def test_absent_observations_do_not_certify_parser_column_indices():
    block, original, _ = extract_fixture(observations=False)
    assert block["metadata"]["table_data"] == original
    assert block["metadata"].get("table_quality", {}).get("state") == "unavailable"


def test_unknown_headers_leave_the_parser_table_literal_and_unqualified():
    block, original, _ = extract_fixture(header_names=["Property", "Lower", "Middle", "Upper", "Measure"])
    assert block["metadata"]["table_data"] == original
    assert block["metadata"]["table_quality"]["state"] == "unavailable"


def supplementary_header_literal(observed, document, text, x, column, *, uncertain=False):
    native = observed[0]["native_glyphs"]
    for character in text:
        index = len(native["glyphs"])
        native["glyphs"].append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                                 "bbox": [x, 362, x + 4, 370], "generated": 0, "unicode_map_error": int(uncertain)})
        x += 4
    if column is not None:
        header = document["tables"][0]["data"]["table_cells"][column]
        header["bbox"]["l"] = min(header["bbox"]["l"], x - len(text) * 4)
        header["text"] = text + " " + header["text"]


def test_supplementary_header_literal_is_kept_with_its_unique_geometric_cell():
    def supplement(observed, page, document):
        supplementary_header_literal(observed, document, "approx", 270, 2)
    block, _, _ = extract_fixture(transform=supplement)
    assert data_cells(block)[(0, 2)]["text"] == "approx Typ"
    binding = next(item for item in block["metadata"]["table_quality"]["bindings"] if (item["row"], item["column"]) == (1, 2))
    assert binding["header_text"] == "approx Typ"
    assert len(binding["header_observation_ids"]) == 2 and binding["state"] == "supported"


def test_uncertain_header_mark_is_preserved_and_blocks_only_its_bound_relations():
    def supplement(observed, page, document):
        supplementary_header_literal(observed, document, "*", 290, 2, uncertain=True)
    block, _, _ = extract_fixture(transform=supplement)
    assert data_cells(block)[(0, 2)]["text"] == "* Typ"
    bindings = {(item["row"], item["column"]): item for item in block["metadata"]["table_quality"]["bindings"]}
    assert bindings[(1, 2)]["state"] == "ambiguous"
    assert "native_glyph_mapping_unverified" in bindings[(1, 2)]["reasons"]
    assert bindings[(1, 1)]["state"] == "supported"


def test_extra_header_without_unique_cell_geometry_does_not_disappear():
    def supplement(observed, page, document):
        supplementary_header_literal(observed, document, "*", 100, None)
    block, original, _ = extract_fixture(transform=supplement)
    assert block["metadata"]["table_data"] == original
    assert block["metadata"]["table_quality"]["state"] == "unavailable"
    assert block["metadata"]["table_quality"]["reasons"] == ["header_extra_text_ambiguous"]


def test_narrow_digit_boxes_do_not_invent_spaces_inside_a_number():
    def narrow(observed, page, document):
        for glyph in observed[0]["native_glyphs"]["glyphs"]:
            if glyph["text"] == "1":
                glyph["bbox"][2] = glyph["bbox"][0] + .2
    block, _, _ = extract_fixture(transform=narrow)
    assert data_cells(block)[(1, 1)]["text"] == "1.8"


def test_compact_formula_spanning_numeric_columns_does_not_gain_one_role_by_its_centre():
    def formula(observed, page, document):
        lines = [(20, 30, "Parameter"), (200, 30, "Min"), (300, 30, "Typ"), (400, 30, "Max"), (450, 30, "Units"),
                 (20, 60, "Pressure"), (450, 60, "bar")]
        native = glyphs_at(lines)
        for offset, character in enumerate("U=(T/2)*(3+7*T)+4"):
            index = len(native["glyphs"])
            native["glyphs"].append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                                      "bbox": [200 + offset * 10, 332, 210 + offset * 10, 340], "generated": 0, "unicode_map_error": 0})
        observed[0]["native_glyphs"] = native
    block, _, _ = extract_fixture(transform=formula)
    expression = next(item for item in block["metadata"]["table_data"]["table_cells"] if "U=" in item["text"])
    assert expression["col_span"] >= 3
    binding = next(item for item in block["metadata"]["table_quality"]["bindings"]
                   if (item["row"], item["column"]) == (expression["start_row_offset_idx"], expression["start_col_offset_idx"]))
    assert binding["header_text"] is None and binding["header_observation_ids"] == []


def test_mapping_error_is_local_and_does_not_gain_a_supported_binding():
    def uncertain(observed, page, document):
        for glyph in observed[0]["native_glyphs"]["glyphs"]:
            if glyph["bbox"][0] == 300 and glyph["text"] == "2":
                glyph["unicode_map_error"] = 1
    block, _, _ = extract_fixture(transform=uncertain)
    bindings = {(item["row"], item["column"]): item for item in block["metadata"]["table_quality"]["bindings"]}
    assert bindings[(1, 1)]["state"] == "supported"
    assert bindings[(1, 2)]["state"] == "ambiguous"


def test_crop_origin_and_page_rotation_keep_the_same_literal_column_relations():
    from services.ingestion.geometry import display_point_to_pdf

    def rotate(observed, page, document):
        frame = [17, 23, 417, 523]
        page.update(rotation=90, crop_box=frame, effective_box=frame)
        for glyph in observed[0]["native_glyphs"]["glyphs"]:
            box = glyph["bbox"]
            corners = [display_point_to_pdf(x, y, frame, 90) for x in (box[0], box[2]) for y in (box[1], box[3])]
            glyph["bbox"] = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
    block, _, _ = extract_fixture(transform=rotate)
    assert [data_cells(block)[(1, column)]["text"] for column in range(5)] == ["Pressure", "1.8", "2.2", "2.9", "bar"]


def test_glyph_budget_failure_is_explicit_and_preserves_original_table(monkeypatch):
    monkeypatch.setattr("services.ingestion.table_geometry.MAX_TABLE_GLYPHS", 1)
    block, original, _ = extract_fixture()
    assert block["metadata"]["table_data"] == original
    assert block["metadata"]["table_quality"]["reasons"] == ["table_glyph_limit"]


def test_catalogue_replay_rejects_source_page_text_geometry_and_binding_tampering():
    from services.ingestion.table_geometry import validate_table_quality

    block, _, _ = extract_fixture()
    assert validate_table_quality(block["text"], block["metadata"], source_sha256=SOURCE_HASH, page_index=0)["state"] == "supported"
    assert validate_table_quality(block["text"], block["metadata"], source_sha256="0" * 64, page_index=0)["state"] == "unavailable"
    assert validate_table_quality(block["text"], block["metadata"], source_sha256=SOURCE_HASH, page_index=1)["state"] == "unavailable"
    assert validate_table_quality(block["text"] + " altered", block["metadata"], source_sha256=SOURCE_HASH, page_index=0)["state"] == "unavailable"
    for field in ("bbox", "text"):
        changed = copy.deepcopy(block["metadata"])
        changed["table_quality"]["observations"][0][field] = [1, 2, 3, 4] if field == "bbox" else "fabricated"
        assert validate_table_quality(block["text"], changed, source_sha256=SOURCE_HASH, page_index=0)["state"] == "unavailable"
    changed = copy.deepcopy(block["metadata"])
    changed["table_quality"]["bindings"][-1]["header_text"] = "Minimum"
    assert validate_table_quality(block["text"], changed, source_sha256=SOURCE_HASH, page_index=0)["state"] == "unavailable"


def subline_fixture(*, missing_second_unit=False, displaced_condition=False, condition_header="Conditions"):
    from services.ingestion.table_geometry import build_table_quality

    positions = [(20, "Parameter"), (160, condition_header), (300, "Min"), (360, "Typ"), (420, "Max"), (470, "Units")]
    lines = [(x, 30, name) for x, name in positions]
    lines.extend([(20, 60, "Delay"), (160, 60, "Load = 20pF"), (230, 60, "Drive=7mV"),
                  (230, 73 if displaced_condition else 80, "Drive=14mV"), (360, 60, "75"), (360, 80, "55"), (470, 60, "ns")])
    if not missing_second_unit:
        lines.append((470, 80, "ns"))
    cells = [cell(name, 0, column, [x, 30, x + len(name) * 4, 38], header=True) for column, (x, name) in enumerate(positions)]
    cells.extend([cell("Delay", 1, 0, [20, 60, 40, 68]),
                  cell("Load = 20pF Drive=7mV Drive=14mV", 1, 1, [160, 60, 270, 88]),
                  cell("75 55", 1, 3, [360, 60, 368, 88]),
                  cell("ns ns", 1, 5, [470, 60, 478, 88])])
    original = {"num_rows": 2, "num_cols": 6, "table_cells": cells}
    page = {"page_index": 0, "crop_box": [0, 0, 550, 400], "effective_box": [0, 0, 550, 400], "rotation": 0}
    projected, quality = build_table_quality(original, [10, 300, 500, 380], (550, 400), page,
                                            native=glyphs_at(lines), source_sha256=SOURCE_HASH)
    return projected, quality, original


def test_sublines_pair_values_with_their_own_condition_and_unit():
    data, quality, _ = subline_fixture()
    cells = {(item["start_row_offset_idx"], item["start_col_offset_idx"]): item for item in data["table_cells"]}
    assert cells[(1, 3)]["text"] == "75" and cells[(2, 3)]["text"] == "55"
    assert cells[(1, 1)]["text"] == "Load = 20pF Drive=7mV"
    assert cells[(2, 1)]["text"] == "Drive=14mV"
    assert cells[(1, 5)]["text"] == cells[(2, 5)]["text"] == "ns"
    assert cells[(1, 0)]["row_span"] == 2
    dependency = quality["dependencies"][0]
    assert dependency["row_index"] == 2 and dependency["source_row"] == 1 and dependency["source_column"] == 1
    assert cells[(1, 1)]["text"][dependency["start_offset"]:dependency["end_offset"]] == dependency["text"] == "Load = 20pF"


def test_multiword_header_uses_its_full_literal_geometry_for_column_boundary():
    data, quality, _ = subline_fixture(condition_header="TEST CONDITIONS")
    cells = {(item["start_row_offset_idx"], item["start_col_offset_idx"]): item for item in data["table_cells"]}
    assert cells[(0, 1)]["text"] == "TEST CONDITIONS"
    assert cells[(1, 1)]["text"] == "Load = 20pF Drive=7mV"
    assert quality["state"] == "supported"


def test_missing_subline_unit_is_not_filled_from_the_previous_line():
    data, quality, _ = subline_fixture(missing_second_unit=True)
    assert not any(cell["start_row_offset_idx"] == 2 and cell["start_col_offset_idx"] == 5 for cell in data["table_cells"])
    binding = next(item for item in quality["bindings"] if (item["row"], item["column"]) == (2, 3))
    assert binding["state"] == "ambiguous" and "subline_unit_alignment_missing" in binding["reasons"]


def test_displaced_subline_condition_cannot_be_zipped_to_the_next_value():
    data, quality, _ = subline_fixture(displaced_condition=True)
    value = next(cell for cell in data["table_cells"] if cell["text"] == "55")
    row = value["start_row_offset_idx"]
    assert not any(cell["start_row_offset_idx"] == row and "Drive=14mV" in cell["text"] for cell in data["table_cells"])
    binding = next(item for item in quality["bindings"] if (item["row"], item["column"]) == (row, 3))
    assert binding["state"] == "ambiguous" and "subline_condition_alignment_missing" in binding["reasons"]


def code_duration_fixture(*, names=None, header_flags=True, corrupt_column_ordinals=False):
    from services.ingestion.table_geometry import build_table_quality

    names = names or ["MODE2 D8", "MODE0 D6", "MODE1 D7", "CONVERSION TIME"]
    positions = [20, 140, 260, 380]
    lines = [(x, 30, name) for x, name in zip(positions, names, strict=True)]
    values = ["1", "0", "1", "230µs"]
    lines.extend((x, 60, value) for x, value in zip(positions, values, strict=True))
    cells = [cell(name, 0, column, [x, 30, x + len(name) * 4, 38], header=header_flags)
             for column, (x, name) in enumerate(zip(positions, names, strict=True))]
    cells.append(cell("1 0 1 230µs", 1, 0, [20, 60, 400, 68]))
    if corrupt_column_ordinals:
        for source_cell in cells:
            source_cell.update(start_col_offset_idx=0, end_col_offset_idx=1)
    original = {"num_rows": 2, "num_cols": 4, "table_cells": cells}
    page = {"page_index": 0, "crop_box": [0, 0, 550, 400], "effective_box": [0, 0, 550, 400], "rotation": 0}
    return build_table_quality(original, [10, 310, 500, 380], (550, 400), page,
                               native=glyphs_at(lines), source_sha256=SOURCE_HASH)


@pytest.mark.parametrize("corrupt_column_ordinals", [False, True])
def test_indexed_code_duration_table_keeps_literal_headers_and_physical_bit_order(corrupt_column_ordinals):
    data, quality = code_duration_fixture(corrupt_column_ordinals=corrupt_column_ordinals)
    assert quality["state"] == "supported"
    headers = [item["text"] for item in data["table_cells"] if item["column_header"]]
    assert headers == ["MODE2 D8", "MODE0 D6", "MODE1 D7", "CONVERSION TIME"]
    bindings = {(item["row"], item["column"]): item for item in quality["bindings"]}
    assert [(bindings[(1, column)]["header_text"], next(item["text"] for item in data["table_cells"]
            if (item["start_row_offset_idx"], item["start_col_offset_idx"]) == (1, column))) for column in range(4)] == [
        ("MODE2 D8", "1"), ("MODE0 D6", "0"), ("MODE1 D7", "1"), ("CONVERSION TIME", "230µs")]
    assert len(bindings[(1, 3)]["header_observation_ids"]) == 2


@pytest.mark.parametrize("names", [
    ["MODE3 D8", "MODE2 D6", "MODE1 D7", "CONVERSION TIME"],
    ["MODE2 D8", "MODE0 D6", "MODE0 D7", "CONVERSION TIME"],
    ["MODE2 D8", "MODE0 D6", "OTHER1 D7", "CONVERSION TIME"],
])
def test_incomplete_or_duplicate_code_significance_does_not_gain_a_mapping(names):
    _, quality = code_duration_fixture(names=names)
    assert quality["state"] == "unavailable"


def test_indexed_words_in_data_do_not_become_headers_without_explicit_header_cells():
    _, quality = code_duration_fixture(header_flags=False)
    assert quality["state"] == "unavailable"


@pytest.mark.parametrize("wide", [False, True])
def test_parent_condition_scope_uses_rectangle_instead_of_parser_colspan(wide):
    from services.ingestion.table_geometry import build_table_quality

    positions = [(20, "Parameter"), (200, "Min"), (300, "Max"), (400, "Units")]
    lines = [(20, 15, "TA = 21°C"), *[(x, 40, text) for x, text in positions],
             (20, 65, "Voltage"), (200, 65, "1.4"), (300, 65, "3.2"), (400, 65, "V")]
    parent = cell("TA = 21°C", 0, 0, [20, 14, 430 if wide else 58, 24], header=True)
    parent.update(end_col_offset_idx=4, col_span=4)
    cells = [parent, *[cell(text, 1, column, [x, 40, x + len(text) * 4, 48], header=True)
                       for column, (x, text) in enumerate(positions)],
             cell("Voltage 1.4 3.2 V", 2, 0, [20, 65, 404, 73])]
    original = {"num_rows": 3, "num_cols": 4, "table_cells": cells}
    page = {"page_index": 0, "crop_box": [0, 0, 500, 400], "effective_box": [0, 0, 500, 400], "rotation": 0}
    data, quality = build_table_quality(original, [10, 310, 460, 395], (500, 400), page,
                                        native=glyphs_at(lines), source_sha256=SOURCE_HASH)
    assert quality["state"] == "supported"
    annotation = data["table_cells"][0]
    assert annotation["column_header"] and annotation["text"] == "TA = 21°C"
    assert annotation["end_col_offset_idx"] == (4 if wide else 1)
    assert quality["bindings"][0]["scope_bbox"] == parent["bbox"]
