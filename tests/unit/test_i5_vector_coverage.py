"""Pure preflight signal tests; no native parser, image or OCR runs here."""

from services.ingestion.config import IngestionConfig
from services.ingestion.preflight import classify_page


def vector_lines():
    return [[20 + x * 25, 220 - y * 15, 40 + x * 25, 228 - y * 15]
            for y in range(5) for x in range(4)]


def test_footer_text_does_not_hide_a_vector_body_without_native_coverage():
    result = classify_page("A complete and lengthy native footer", [], 20, IngestionConfig(),
                           native_text_regions=[[20, 10, 180, 20]], vector_regions=vector_lines(),
                           effective_box=[0, 0, 300, 300])
    assert result == ("mixed", True)


def test_native_text_covering_the_same_vector_regions_is_not_reocrized():
    result = classify_page("Native body with all its words", [], 20, IngestionConfig(),
                           native_text_regions=[[15, 145, 125, 230]], vector_regions=vector_lines(),
                           effective_box=[0, 0, 300, 300])
    assert result == ("native", False)


def test_grid_rules_and_a_large_graphic_do_not_establish_text_regions():
    result = classify_page("Native heading", [], 4, IngestionConfig(),
                           native_text_regions=[[20, 260, 120, 270]],
                           vector_regions=[[10, 20, 290, 20.5], [10, 50, 290, 50.5], [50, 80, 220, 240]],
                           effective_box=[0, 0, 300, 300])
    assert result == ("native", False)


def test_vector_body_without_any_native_text_requires_regional_ocr():
    assert classify_page("", [], 20, IngestionConfig(), native_text_regions=[], vector_regions=vector_lines(),
                         effective_box=[0, 0, 300, 300]) == ("degraded", True)


def test_existing_mixed_bitmap_route_remains_available():
    assert classify_page("Native title", [{"area_ratio": .3}], 0, IngestionConfig(),
                         native_text_regions=[[20, 260, 120, 270]], vector_regions=[],
                         effective_box=[0, 0, 300, 300]) == ("mixed", True)


def test_vector_route_keeps_existing_pixel_budget():
    import pytest

    from services.ingestion.errors import IngestionError
    from services.ingestion.preflight import check_render_budget

    page = {"page_index": 0, "display_width": 300, "display_height": 300}
    with pytest.raises(IngestionError) as failure:
        check_render_budget(page, "regional_ocr", IngestionConfig(max_page_render_pixels=1))
    assert failure.value.code == "PDF_RENDER_LIMIT"


def test_vector_reason_is_distinct_from_bitmap_or_degraded_unicode_text():
    from services.ingestion.pipeline import routing_reason

    page = {"uncovered_vector_regions": [{"bbox": [10, 10, 40, 40]}], "image_regions": []}
    assert routing_reason(page, "regional_ocr", IngestionConfig()) == "uncovered_vector_body"


def test_overlap_ratio_is_measured_on_union_not_assumed_zero_or_double_counted():
    from services.ingestion.preflight import uncovered_vector_regions

    native = [[18, 158, 21, 230], [18, 158, 21, 230]]
    regions = uncovered_vector_regions(vector_lines(), native, [0, 0, 300, 300])
    assert len(regions) == 1
    box = regions[0]["bbox"]
    expected = 3 * 72 / ((box[2] - box[0]) * (box[3] - box[1]))
    assert regions[0]["text_layer_overlap"] == expected > 0
    assert regions[0]["text_layer_overlap_measure"].endswith("observed_native_rectangles")


def test_observation_cap_is_explicit_even_when_native_text_survives():
    from services.ingestion.docling_adapter import document_to_pages

    document = {"pages": {"1": {"size": {"width": 300, "height": 300}}},
                "texts": [{"self_ref": "#/texts/0", "label": "text", "text": "Native footer",
                           "prov": [{"page_no": 1, "bbox": {"l": 20, "t": 280, "r": 120, "b": 290, "coord_origin": "TOPLEFT"}}]}]}
    page = {"page_index": 0, "crop_box": [0, 0, 300, 300], "rotation": 0, "classification": "native",
            "preflight_geometry_warnings": ["PREFLIGHT_VECTOR_SCAN_LIMIT"],
            "uncovered_vector_regions": [{"bbox": [10, 50, 120, 200]}]}
    pages, warnings = document_to_pages(document, [page], "version", "revision", "native")
    assert pages[0]["blocks"][0]["text"] == "Native footer"
    assert {item["reason"] for item in pages[0]["unresolved_regions"]} == {"PREFLIGHT_VECTOR_SCAN_LIMIT", "VECTOR_BODY_NOT_OCR_PROCESSED"}
    assert {item["code"] for item in warnings} >= {"PREFLIGHT_VECTOR_SCAN_LIMIT", "VECTOR_BODY_NOT_OCR_PROCESSED"}
