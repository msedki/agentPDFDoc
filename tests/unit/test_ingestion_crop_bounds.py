"""Découpes OCR et tableaux ramenées dans la page (Docling/PDFium : « Crop exceeds page dimensions »)."""
import importlib.util

import pytest

from services.ingestion.regional_grid import PAGE_EDGE_MARGIN, clamp_box_values, clamp_to_page


def test_a_box_overflowing_the_page_is_brought_back_inside_with_a_rounding_margin():
    # Image placée en partie hors page, comme relevé sur le corpus réel (x négatif).
    assert clamp_box_values(-14.16, 30.0, 52.34, 80.0, 841.92, 595.32) == (0.0, 30.0, 52.34, 80.0)
    left, top, right, bottom = clamp_box_values(800.0, 500.0, 900.0, 700.0, 841.92, 595.32)
    assert (left, top) == (800.0, 500.0) and right == pytest.approx(841.92 - PAGE_EDGE_MARGIN) and bottom == pytest.approx(595.32 - PAGE_EDGE_MARGIN)


def test_a_box_outside_the_page_or_thinner_than_a_point_is_dropped():
    assert clamp_box_values(900.0, 10.0, 950.0, 20.0, 841.92, 595.32) is None
    assert clamp_box_values(-20.0, 10.0, 0.5, 20.0, 841.92, 595.32) is None


def test_a_box_inside_the_page_is_unchanged():
    assert clamp_box_values(10.0, 20.0, 300.0, 400.0, 841.92, 595.32) == (10.0, 20.0, 300.0, 400.0)


@pytest.mark.skipif(importlib.util.find_spec("docling_core") is None, reason="docling_core non provisionné")
def test_clamped_bounding_box_keeps_its_coordinate_origin():
    from docling_core.types.doc import BoundingBox, CoordOrigin

    box = BoundingBox(l=-5, t=-5, r=100, b=50, coord_origin=CoordOrigin.TOPLEFT)
    clamped = clamp_to_page(box, 600, 800)
    assert (clamped.l, clamped.t, clamped.r, clamped.b, clamped.coord_origin) == (0.0, 0.0, 100.0, 50.0, CoordOrigin.TOPLEFT)
    assert clamp_to_page(BoundingBox(l=700, t=10, r=800, b=20, coord_origin=CoordOrigin.TOPLEFT), 600, 800) is None
