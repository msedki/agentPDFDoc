import pytest

from services.ingestion.config import IngestionConfig
from services.ingestion.errors import IngestionError
from services.ingestion.preflight import check_render_budget, rendered_pixels


def test_current_a4_scans_remain_inside_actual_216dpi_budget():
    page = {"page_index": 4, "display_width": 595.28, "display_height": 841.89}
    assert rendered_pixels(page["display_width"], page["display_height"], 3) < 5_000_000
    check_render_budget(page, "regional_ocr", IngestionConfig())
    check_render_budget(page, "structured", IngestionConfig())


@pytest.mark.parametrize("size", [(595.28, 841.89), (612, 792), (612, 1008)], ids=["A4", "Letter", "Legal"])
def test_full_page_scans_of_common_formats_reach_ocr_with_the_delivered_profile(size):
    # Essai du 01/10 : la fixture DA-P02 (scan A4 pleine page) était refusée en OCR_RENDER_LIMIT avec le plafond de 8 M
    # pixels, la région étant rendue à 3 × 1,5 (PDFium suréchantillonne puis réduit) : 10,1 M pixels.
    width, height = size
    settings = IngestionConfig(pdf_backend="pypdfium2")
    scan = {"page_index": 0, "display_width": width, "display_height": height, "effective_box": [0, 0, width, height],
            "image_regions": [{"bbox": [0, 0, width, height]}]}
    check_render_budget(scan, "regional_ocr", settings)
    a3 = {"page_index": 0, "display_width": 841.89, "display_height": 1190.55, "effective_box": [0, 0, 841.89, 1190.55],
          "image_regions": [{"bbox": [0, 0, 841.89, 1190.55]}]}
    # Un A3 reste refusé et déclaré : le plafond de la page, contrôlé avant celui de la région OCR, s'applique d'abord.
    with pytest.raises(IngestionError) as caught:
        check_render_budget(a3, "regional_ocr", settings)
    assert caught.value.code == "PDF_RENDER_LIMIT"


def test_large_declared_page_is_rejected_before_any_model_import():
    page = {"page_index": 3, "display_width": 4000, "display_height": 4000}
    for route in ("structured", "regional_ocr"):
        with pytest.raises(IngestionError) as caught:
            check_render_budget(page, route, IngestionConfig())
        assert caught.value.code == "PDF_RENDER_LIMIT"
        assert caught.value.details["page_index"] == 3
    check_render_budget(page, "native", IngestionConfig())
    check_render_budget(page, "blank", IngestionConfig())


def test_render_limits_use_allocation_rounding_and_reject_invalid_frames():
    assert rendered_pixels(600.1, 800.1, 3) == 1801 * 2401
    for width, height in ((float("inf"), 800), (600, float("nan")), (0, 800), (600, -1)):
        with pytest.raises(IngestionError):
            rendered_pixels(width, height, 3)


def test_official_pdfium_oversampling_is_counted_before_models():
    settings = IngestionConfig(pdf_backend="pypdfium2")
    large = {"page_index": 0, "display_width": 1000, "display_height": 1000}
    with pytest.raises(IngestionError) as caught:
        check_render_budget(large, "structured", settings)
    assert caught.value.code == "PDF_RENDER_LIMIT"
    assert caught.value.details["render_pixels"] == 9_000_000
    mixed = {"page_index": 0, "display_width": 600, "display_height": 800,
             "effective_box": [0, 0, 600, 800], "image_regions": [{"bbox": [50, 80, 550, 400]}]}
    check_render_budget(mixed, "regional_ocr", settings)
    oversized_bitmap = {"page_index": 0, "display_width": 900, "display_height": 900,
                        "effective_box": [0, 0, 900, 900], "image_regions": [{"bbox": [0, 0, 900, 900]}]}
    with pytest.raises(IngestionError) as caught:
        check_render_budget(oversized_bitmap, "regional_ocr", settings)
    assert caught.value.code == "OCR_RENDER_LIMIT"
    assert caught.value.details["component"] == "preflight_bitmap"
