"""Synthetic OCR frame witnesses; no rendering or recognition is performed."""

import copy
import hashlib

import pytest

from services.ingestion.docling_adapter import document_to_pages, table_text
from services.ingestion.geometry import docling_box_to_pdf, pdf_box_to_docling
from services.ingestion.source_quality import READING_POLICY
from services.ingestion.table_geometry import build_table_quality, validate_table_quality
from tests.unit.test_i5_table_geometry import cell

SOURCE_HASH = hashlib.sha256(b"explicit synthetic local table orientation source").hexdigest()
RASTER_HASH = hashlib.sha256(b"explicit synthetic local orientation raster").hexdigest()
CANDIDATE_HASH = hashlib.sha256(b"explicit synthetic verification crop").hexdigest()


def orientation_fixture(local_rotation, page_rotation=0):
    frame = [13, 23, 613, 823]
    page = {"page_index": 0, "crop_box": frame, "effective_box": frame, "rotation": page_rotation,
            "classification": "scan_candidate", "source_sha256": SOURCE_HASH}
    parser_size = (800, 600) if page_rotation in {90, 270} else (600, 800)
    reading_page = {**page, "rotation": (page_rotation + local_rotation) % 360}
    reading_size = (800, 600) if reading_page["rotation"] in {90, 270} else (600, 800)
    columns = [(20, "Equipment", "Pressure"), (220, "Value", "7.4"), (400, "Unit", "kPa")]
    parser_cells, observations, rows, expected_boxes = [], [], [], {}
    for row, top in [(0, 30), (1, 60)]:
        tokens = []
        for column, (left, heading, value) in enumerate(columns):
            text = heading if row == 0 else value
            upright = {"l": left, "t": top, "r": left + len(text) * 4, "b": top + 8, "coord_origin": "TOPLEFT"}
            physical = docling_box_to_pdf(upright, reading_size, reading_page)
            parser_box = pdf_box_to_docling(physical, parser_size, page)
            source_cell = cell(text, row, column, [parser_box[k] for k in ("l", "t", "r", "b")], header=row == 0)
            parser_cells.append(source_cell)
            expected_boxes[(row, column)] = physical
            observations.append({"text": text, "bbox": physical, "from_ocr": True, "confidence": .95})
            tokens.append({"text": text, "bbox": physical, "confidence": .95})
        rows.append(tokens)
    table_box = docling_box_to_pdf({"l": 10, "t": 20, "r": 520, "b": 90, "coord_origin": "TOPLEFT"}, reading_size, reading_page)
    region = {"l": 0, "t": 0, "r": parser_size[0], "b": parser_size[1], "coord_origin": "TOPLEFT"}
    source_size = [value * 3 for value in parser_size]
    oriented_size = source_size[::-1] if local_rotation in {90, 270} else source_size
    orientation = {"orientation_degrees": local_rotation, "resolved": True, "orientation_convention": "counterclockwise_from_upright",
                   "correction_degrees_pil": -local_rotation, "parser_bbox": region, "source_raster_size": source_size,
                   "derivative_raster_size": source_size, "intrinsic_pixel_size": source_size, "osd_raster_sha256": RASTER_HASH}
    preprocessing = {"algorithm": "unchanged-raster", "coordinate_frame": "oriented_ocr_region_pixels", "ocr_region_index": 0,
                     "orientation_degrees": local_rotation, "orientation_resolved": True, "parser_bbox": region,
                     "source_oriented_raster_size": oriented_size, "derived_oriented_raster_size": oriented_size,
                     "source_raster_sha256": RASTER_HASH, "derived_raster_sha256": RASTER_HASH,
                     "osd_raster_sha256": RASTER_HASH, "scale": 3.0, "resize_inverse_factors": [1.0, 1.0]}
    readings = [{"policy": READING_POLICY, "reading_id": f"region-0-line-{row}", "coordinate_frame": "pdf_user_space_unrotated",
                 "baseline_tokens": tokens, "candidate_tokens": copy.deepcopy(tokens), "minimum_confidence": .8,
                 "source_raster_sha256": RASTER_HASH, "candidate_raster_sha256": CANDIDATE_HASH,
                 "source_raster_size": oriented_size, "parser_bbox": region, "orientation_degrees": local_rotation,
                 "ocr_region_index": 0, "scale": 3.0, "resize_inverse_factors": [1.0, 1.0], "parameters": {"psm": 6, "factor": 1}}
                for row, tokens in enumerate(rows)]
    correction = {"orientation_degrees": local_rotation, "parser_bbox": pdf_box_to_docling(table_box, parser_size, page),
                  "model": "same-tableformer-accurate", "cells": len(parser_cells)}
    arguments = {"cells": observations, "quality_readings": readings, "source_sha256": SOURCE_HASH,
                 "orientation_records": [orientation], "preprocessing": [preprocessing],
                 "table_corrections": [correction] if local_rotation else []}
    original = {"num_rows": 2, "num_cols": 3, "table_cells": parser_cells}
    return original, table_box, parser_size, page, arguments, expected_boxes


def project_fixture(fixture):
    original, box, size, page, arguments, _ = fixture
    data, quality = build_table_quality(original, box, size, page, **arguments)
    return data, quality, {"table_data": data, "parser_table_data": original, "table_quality": quality}


@pytest.mark.parametrize("local_rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("page_rotation", [0, 90, 180, 270])
def test_local_reading_rotation_preserves_physical_cells_with_page_rotation_and_crop(local_rotation, page_rotation):
    fixture = orientation_fixture(local_rotation, page_rotation)
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "supported"
    assert table_text(data) == "Equipment | Value | Unit\nPressure | 7.4 | kPa"
    assert quality["page_frame"]["rotation"] == page_rotation
    for source_cell in data["table_cells"]:
        position = source_cell["start_row_offset_idx"], source_cell["start_col_offset_idx"]
        physical = docling_box_to_pdf(source_cell["bbox"], fixture[2], fixture[3])
        assert physical == pytest.approx(fixture[-1][position], abs=1e-6)
    if local_rotation:
        witness = quality["table_orientation"]
        assert witness["source_sha256"] == SOURCE_HASH and witness["page_index"] == 0
        assert witness["orientation_degrees"] == local_rotation
        assert witness["reading_ids"] == ["region-0-line-0", "region-0-line-1"]
        assert witness["region_preprocessing"]["derived_raster_sha256"] == RASTER_HASH
    assert validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0)["state"] == "supported"


@pytest.mark.parametrize("missing", ["orientation_records", "preprocessing", "table_corrections", "quality_readings"])
def test_a_rotated_frame_requires_the_complete_real_observation_chain(missing):
    fixture = orientation_fixture(90)
    fixture[4][missing] = []
    data, quality, _ = project_fixture(fixture)
    assert quality["state"] == "unavailable"
    assert data == fixture[0]
    assert quality["bindings"] == []


@pytest.mark.parametrize("mutation", ["duplicate_region", "contradictory_angle", "other_raster", "other_region",
                                      "raster_size", "unresolved", "only_flag", "missing_osd_link", "other_osd_raster"])
def test_local_orientation_is_not_inferred_from_ambiguous_or_unbound_metadata(mutation):
    fixture = orientation_fixture(90)
    arguments = fixture[4]
    if mutation == "duplicate_region":
        arguments["orientation_records"].append(copy.deepcopy(arguments["orientation_records"][0]))
    elif mutation == "contradictory_angle":
        arguments["preprocessing"][0]["orientation_degrees"] = 270
    elif mutation == "other_raster":
        arguments["quality_readings"][0]["source_raster_sha256"] = "f" * 64
    elif mutation == "other_region":
        arguments["quality_readings"][0]["ocr_region_index"] = 1
    elif mutation == "raster_size":
        arguments["preprocessing"][0]["derived_oriented_raster_size"] = [10, 20]
    elif mutation == "unresolved":
        arguments["orientation_records"][0]["resolved"] = False
    elif mutation == "missing_osd_link":
        arguments["preprocessing"][0].pop("osd_raster_sha256")
    elif mutation == "other_osd_raster":
        arguments["preprocessing"][0]["osd_raster_sha256"] = "f" * 64
    else:
        arguments["orientation_records"] = [{"orientation_degrees": 90, "resolved": True}]
    data, quality, _ = project_fixture(fixture)
    assert quality["state"] == "unavailable"
    assert data == fixture[0]


def test_a_proven_reading_frame_does_not_promote_an_uncertain_unit():
    fixture = orientation_fixture(90)
    fixture[4]["quality_readings"][1]["candidate_tokens"][2]["confidence"] = .7
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "partial"
    assert table_text(data) == "Equipment | Value | Unit\nPressure | 7.4 | kPa"
    unit = next(binding for binding in quality["bindings"] if (binding["row"], binding["column"]) == (1, 2))
    assert unit["state"] == "ambiguous" and "candidate_low_or_invalid_confidence" in unit["reasons"]
    assert validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0)["state"] == "partial"


@pytest.mark.parametrize("mutation", ["angle", "source", "page", "raster", "osd", "missing_witness", "physical_cell"])
def test_catalogue_replay_rejects_orientation_and_physical_provenance_tampering(mutation):
    data, quality, metadata = project_fixture(orientation_fixture(90))
    assert quality["state"] == "supported"
    changed = copy.deepcopy(metadata)
    witness = changed["table_quality"]["table_orientation"]
    if mutation == "angle":
        witness["orientation_degrees"] = 270
    elif mutation == "source":
        witness["source_sha256"] = "f" * 64
    elif mutation == "page":
        witness["page_index"] = 1
    elif mutation == "raster":
        witness["region_preprocessing"]["derived_raster_sha256"] = "f" * 64
    elif mutation == "osd":
        witness["region_orientation"]["osd_raster_sha256"] = "f" * 64
    elif mutation == "missing_witness":
        changed["table_quality"].pop("table_orientation")
    else:
        changed["table_data"]["table_cells"][0]["bbox"]["l"] += 1
    assert validate_table_quality(table_text(data), changed, source_sha256=SOURCE_HASH, page_index=0)["state"] == "unavailable"


def test_adapter_keeps_the_observed_local_correction_and_physical_cell_regions():
    original, box, size, page, arguments, expected = orientation_fixture(90)
    raw_readings = copy.deepcopy(arguments["quality_readings"])
    for reading in raw_readings:
        reading["coordinate_frame"] = "parser_top_left"
        for name in ("baseline_tokens", "candidate_tokens"):
            for token in reading[name]:
                token["bbox"] = pdf_box_to_docling(token["bbox"], size, page)
    raw_cells = [{**source_cell, "bbox": pdf_box_to_docling(source_cell["bbox"], size, page)} for source_cell in arguments["cells"]]
    observed = {0: {"cells": raw_cells, "source_sha256": SOURCE_HASH, "quality_readings": raw_readings,
                    "orientations": arguments["orientation_records"], "preprocessing": arguments["preprocessing"],
                    "table_orientation_corrections": arguments["table_corrections"]}}
    document = {"pages": {"1": {"size": {"width": size[0], "height": size[1]}}}, "tables": [
        {"self_ref": "#/tables/0", "label": "table", "data": original,
         "prov": [{"page_no": 1, "bbox": pdf_box_to_docling(box, size, page)}]}]}
    pages, warnings = document_to_pages(document, [page], "version", "revision", "regional_ocr", observed)
    block = pages[0]["blocks"][0]
    assert block["metadata"]["table_quality"]["state"] == "supported"
    assert not any(warning.get("code") == "TABLE_RELATION_QUALITY_UNCERTAIN" for warning in warnings)
    for region in block["metadata"]["table_cell_regions"]:
        assert region["bbox"] == pytest.approx(expected[(region["row"], region["column"])], abs=1e-6)


def test_catalogue_replay_binds_to_the_registered_page_frame_and_table_rectangle():
    fixture = orientation_fixture(90, 270)
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "supported"
    result = validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0,
                                    page=fixture[3], table_bbox=fixture[1])
    assert result["state"] == "supported"


def test_an_absent_explicit_cropbox_keeps_the_real_effective_frame():
    fixture = orientation_fixture(90)
    fixture[3]["crop_box"] = None
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "supported"
    assert quality["page_frame"]["crop_box"] is None
    result = validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0,
                                    page=fixture[3], table_bbox=fixture[1])
    assert result["state"] == "supported"


@pytest.mark.parametrize("mutation", ["missing", "page_index", "rotation", "crop_box", "effective_box", "source_sha256"])
def test_an_external_page_frame_mismatch_blocks_an_internally_consistent_witness(mutation):
    fixture = orientation_fixture(90)
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "supported"
    registered_page = copy.deepcopy(fixture[3])
    if mutation == "missing":
        registered_page = None
    elif mutation == "page_index":
        registered_page["page_index"] = 1
    elif mutation == "rotation":
        registered_page["rotation"] = 180
    elif mutation == "source_sha256":
        registered_page["source_sha256"] = "f" * 64
    else:
        registered_page[mutation][0] += 1
    result = validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0,
                                    page=registered_page, table_bbox=fixture[1])
    assert result["state"] == "unavailable"
    assert result["reasons"] == ["table_quality_page_frame_mismatch"]


@pytest.mark.parametrize("mutation", ["missing", "shifted", "invalid"])
def test_an_external_table_rectangle_mismatch_blocks_the_witness(mutation):
    fixture = orientation_fixture(90)
    data, quality, metadata = project_fixture(fixture)
    assert quality["state"] == "supported"
    registered_box = list(fixture[1])
    if mutation == "missing":
        registered_box = None
    elif mutation == "shifted":
        registered_box[0] += 1
    else:
        registered_box = [0, 0, 1]
    result = validate_table_quality(table_text(data), metadata, source_sha256=SOURCE_HASH, page_index=0,
                                    page=fixture[3], table_bbox=registered_box)
    assert result["state"] == "unavailable"
