import hashlib

from services.ingestion.config import IngestionConfig
from services.ingestion.docling_adapter import document_to_pages, table_coverage
from services.ingestion.pipeline import native_quality, page_route, stitch_structure
from services.ingestion.preflight import classify_page


def test_mixed_page_is_not_silently_classified_as_all_native():
    result = classify_page("Un paragraphe natif suffisamment long qui décrit la procédure.", [{"area_ratio": .4}], 0, IngestionConfig())
    assert result == ("mixed", True)
    assert classify_page("", [], 0, IngestionConfig()) == ("blank", False)
    assert classify_page("", [], 4, IngestionConfig()) == ("graphic_uncertain", False)
    assert classify_page("CCU-21", [], 0, IngestionConfig()) == ("native", False)
    assert classify_page("\ufffd\ufffd", [], 0, IngestionConfig()) == ("degraded", True)


def test_low_confidence_cell_remains_visible_and_explicitly_unresolved():
    region = {"l": 10, "t": 20, "r": 30, "b": 50, "coord_origin": "TOPLEFT"}
    document = {"pages": {"1": {"size": {"width": 100, "height": 200}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "scan_candidate"}
    observations = {0: {"cell_count": 1, "preprocessing": [{"cell_ocr": [{"uncertain_parser_bbox": region, "minimum_word_confidence": .6}]}]}}
    pages, warnings = document_to_pages(document, [page], "version", "revision", "regional_ocr", observations)
    assert {"code": "OCR_CELL_LOW_CONFIDENCE", "page_index": 0} in warnings
    assert pages[0]["unresolved_regions"][0] == {"bbox": [10, 150, 30, 180], "reason": "OCR_CELL_LOW_CONFIDENCE", "precision": "block"}
    assert pages[0]["ocr_preprocessing"][0]["cell_ocr"][0]["minimum_word_confidence"] == .6


def test_immutable_unicode_text_and_actual_ocr_counter():
    text = "A😀é ﬁ e\u0301"
    item = {"self_ref": "#/texts/0", "label": "text", "text": text,
            "prov": [{"page_no": 1, "charspan": [0, len(text)], "bbox": {"l": 10, "b": 20, "r": 30, "t": 50, "coord_origin": "BOTTOMLEFT"}}]}
    document = {"texts": [item], "body": {"self_ref": "#/body", "children": [{"$ref": "#/texts/0"}]}, "pages": {"1": {"size": {"width": 100, "height": 200}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "mixed"}
    pages, warnings = document_to_pages(document, [page], "version", "revision", "regional_ocr", {0: {"cell_count": 0}})
    block = pages[0]["blocks"][0]
    assert block["raw_text"] == text
    assert block["source_text_hash"] == hashlib.sha256(text.encode()).hexdigest()
    assert block["spans"][0]["end_offset"] == len(text)
    assert block["bbox"] == [10, 20, 30, 50]
    assert not pages[0]["ocr_used"]
    assert pages[0]["extraction_state"] == "native"
    assert warnings == []
    pages_again, _ = document_to_pages(document, [page], "version", "revision", "regional_ocr")
    assert pages_again[0]["blocks"][0]["id"] == block["id"]


def test_mixed_page_marks_only_observed_ocr_regions_and_exact_spans():
    native = "La procédure native est conservée."
    scanned = "Tension 24 V"
    boxes = [{"l": 10, "b": 100, "r": 90, "t": 150, "coord_origin": "BOTTOMLEFT"},
             {"l": 10, "b": 20, "r": 90, "t": 60, "coord_origin": "BOTTOMLEFT"}]
    items = [{"self_ref": f"#/texts/{index}", "label": "text", "text": text, "orig": text,
              "prov": [{"page_no": 1, "charspan": [0, len(text)], "bbox": boxes[index]}]}
             for index, text in enumerate((native, scanned))]
    document = {"texts": items, "pages": {"1": {"size": {"width": 100, "height": 200}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "mixed"}
    cells = [{"text": native, "bbox": boxes[0], "from_ocr": False},
             {"text": scanned, "bbox": boxes[1], "from_ocr": True}]
    pages, _ = document_to_pages(document, [page], "version", "revision", "regional_ocr", {0: {"cell_count": 1, "cells": cells}})
    blocks = pages[0]["blocks"]
    assert blocks[0]["metadata"]["extraction_method"] == "native"
    assert not blocks[0]["metadata"]["ocr_used"]
    assert blocks[1]["metadata"]["extraction_method"] == "ocr"
    assert blocks[1]["metadata"]["ocr_spans"] == [{"start_offset": 0, "end_offset": len(scanned), "bbox": [10, 20, 90, 60], "precision": "span"}]
    assert pages[0]["ocr_regions"] == [[10, 20, 90, 60]]


def test_orig_stays_immutable_and_invalid_charspan_cannot_cite_another_page():
    original = "é e\u0301"
    document = {"texts": [{"self_ref": "#/texts/0", "label": "text", "text": "normalized", "orig": original,
                          "prov": [{"page_no": 1, "charspan": [0, len(original)], "bbox": {"l": 10, "b": 20, "r": 90, "t": 60, "coord_origin": "BOTTOMLEFT"}}]}],
                "pages": {"1": {"size": {"width": 100, "height": 200}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "native"}
    pages, _ = document_to_pages(document, [page], "version", "revision", "native")
    assert pages[0]["blocks"][0]["raw_text"] == original
    document["texts"][0]["prov"][0]["charspan"] = [5, 20]
    pages, warnings = document_to_pages(document, [page], "version", "revision", "native")
    assert pages[0]["blocks"] == []
    assert pages[0]["extraction_state"] == "error"
    assert any(warning["code"] == "INVALID_SOURCE_CHARSPAN" for warning in warnings)


def test_native_quality_catches_missing_value_and_reading_order():
    full = "Tension CCU-21 : 24 V."
    expected = sum(character.isalnum() for character in full)
    page = {"alphanumeric_count": expected, "blocks": [{"type": "text", "raw_text": "Tension CCU-21", "bbox": [10, 100, 90, 130]}]}
    assert not native_quality(page)["passed"]
    page["blocks"][0]["raw_text"] = full
    assert native_quality(page)["passed"]
    page["blocks"].append({"type": "text", "raw_text": "Préparation", "bbox": [10, 170, 90, 190]})
    assert not native_quality(page)["passed"]


def test_native_route_does_not_discard_heading_or_column_structure():
    page = {"classification": "native", "needs_ocr": False, "effective_box": [0, 0, 600, 800],
            "vector_path_count": 0, "native_text_regions": [], "text_font_sizes": [12, 22]}
    assert page_route(page, IngestionConfig()) == "structured"
    page["text_font_sizes"] = [12]
    page["native_text_regions"] = [[10, y, 200, y + 10] for y in (50, 100, 150)] + [[400, y, 580, y + 10] for y in (50, 100, 150)]
    assert page_route(page, IngestionConfig()) == "structured"


def test_wide_table_collapsed_to_row_labels_is_explicitly_incomplete():
    data = {"num_rows": 3, "num_cols": 1, "table_cells": [{"text": "CCU-21", "row_header": True, "bbox": {"l": 70, "r": 170, "t": 280, "b": 300, "coord_origin": "TOPLEFT"}}]}
    page = {"crop_box": [0, 0, 600, 800], "rotation": 0}
    cells, warnings = table_coverage(data, [60, 200, 540, 600], (600, 800), page)
    assert cells[0]["bbox"] == [70, 500, 170, 520]
    assert warnings == ["TABLE_CONTENT_COVERAGE_UNCERTAIN"]


def test_unresolved_orientation_and_printed_cell_keep_exact_unresolved_regions():
    bounds = {"l": 10, "t": 20, "r": 90, "b": 60, "coord_origin": "TOPLEFT"}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "scan_candidate"}
    document = {"pages": {"1": {"size": {"width": 100, "height": 200}}}}
    observed = {0: {"orientations": [{"parser_bbox": bounds, "resolved": False}],
                    "preprocessing": [{"cell_ocr": [{"unresolved_parser_bbox": bounds}]}]}}
    pages, warnings = document_to_pages(document, [page], "version", "revision", "regional_ocr", observed)
    reasons = {region["reason"] for region in pages[0]["unresolved_regions"]}
    assert reasons == {"OCR_ORIENTATION_UNRESOLVED", "OCR_PRINTED_CELL_UNRESOLVED"}
    assert all(region["bbox"] == [10, 140, 90, 180] for region in pages[0]["unresolved_regions"])
    assert reasons <= {warning["code"] for warning in warnings}


def test_section_survives_four_five_checkpoint_boundary():
    heading = {"id": "heading", "type": "heading", "text": "Installation", "bbox": [10, 600, 200, 700], "metadata": {}}
    text = {"id": "continued", "type": "text", "text": "La tension nominale est 24 V.", "bbox": [10, 300, 200, 400], "metadata": {}}
    pages = [{"page_index": 3, "blocks": [heading], "effective_box": [0, 0, 600, 800]}, {"page_index": 4, "blocks": [text], "effective_box": [0, 0, 600, 800]}]
    sections, _ = stitch_structure(pages)
    assert text["section_id"] == "heading"
    assert sections[0]["block_ids"] == ["heading", "continued"]
    assert sections[0]["page_end"] == 4


def test_table_continuation_needs_headers_positions_and_same_section():
    data = {"num_cols": 2, "table_cells": [{"text": "Valeur", "column_header": True}]}
    first = {"id": "table-4", "type": "table", "text": "Valeur | 24 V", "bbox": [10, 30, 500, 200], "metadata": {"table_data": data}}
    second = {"id": "table-5", "type": "table", "text": "Valeur | 36 V", "bbox": [10, 600, 500, 780], "metadata": {"table_data": data}}
    pages = [{"page_index": 3, "blocks": [first], "effective_box": [0, 0, 600, 800]}, {"page_index": 4, "blocks": [second], "effective_box": [0, 0, 600, 800]}]
    _, tables = stitch_structure(pages)
    assert tables[1]["continuation_of"] == "table-4"
    second["bbox"] = [10, 300, 500, 400]
    _, tables = stitch_structure(pages)
    assert tables[1]["continuation_of"] is None
