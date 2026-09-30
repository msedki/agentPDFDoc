import copy

import pytest

from services.ingestion import IngestionError
from services.ingestion.config import IngestionConfig
from services.ingestion.geometry import docling_box_to_pdf
from services.ingestion.regional_aspect import (
    complete_bitmap_pixel_size,
    inverse_resized_box,
    oriented_resize,
    pdf_box_to_display_top_left,
    reduced_aspect_size,
)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_bitmap_display_frame_roundtrips_absolute_crop_offset(rotation):
    page = {"rotation": rotation, "effective_box": [24, 30, 565, 570], "crop_box": [24, 30, 565, 570]}
    source = [50, 80, 500, 400]
    left, top, right, bottom = pdf_box_to_display_top_left(source, page)
    size = (540, 541) if rotation in (90, 270) else (541, 540)
    assert docling_box_to_pdf({"l": left, "t": top, "r": right, "b": bottom, "coord_origin": "TOPLEFT"}, size, page) == source


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_anisotropic_derivative_restores_exact_full_frame_and_interior(angle):
    size = reduced_aspect_size((1501, 961), (600, 1000))
    assert size == (577, 961)
    original, derived = oriented_resize((1501, 961), size, angle)
    assert inverse_resized_box([0, 0, *derived], original, derived) == [0, 0, *original]
    middle = inverse_resized_box([derived[0] / 4, derived[1] / 3, derived[0] / 2, derived[1] * 2 / 3], original, derived)
    assert middle == pytest.approx([original[0] / 4, original[1] / 3, original[0] / 2, original[1] * 2 / 3])
    assert derived[0] * derived[1] <= original[0] * original[1]


def bitmap_page():
    return {"rotation": 0, "effective_box": [24, 30, 565, 570], "image_regions": [
        {"bbox": [50, 80, 550, 400], "pixel_size": [600, 1000], "matrix": [500, 0, 0, 320, 50, 80], "object_level": 0}]}


def test_only_complete_unambiguous_bitmap_is_rectified():
    page = bitmap_page()
    region = {"l": 26, "t": 170, "r": 526, "b": 490}
    assert complete_bitmap_pixel_size(region, page) == (600, 1000)
    cropped = dict(region, r=525)
    assert complete_bitmap_pixel_size(cropped, page) is None
    for field, value in (("object_level", 1), ("matrix", [500, 5, 0, 320, 50, 80]), ("matrix", [-500, 0, 0, 320, 550, 80])):
        invalid = copy.deepcopy(page)
        invalid["image_regions"][0][field] = value
        assert complete_bitmap_pixel_size(region, invalid) is None
    overlap = copy.deepcopy(page)
    overlap["image_regions"].append({"bbox": [200, 100, 300, 200]})
    assert complete_bitmap_pixel_size(region, overlap) is None
    clipped = copy.deepcopy(page)
    clipped["effective_box"] = [24, 30, 500, 570]
    assert complete_bitmap_pixel_size(region, clipped) is None


@pytest.mark.parametrize("field,value", [("pixel_size", [float("nan"), 1000]), ("pixel_size", [True, 1000]),
                                         ("pixel_size", [600.5, 1000]), ("matrix", [500, 0, 0, 320, float("inf"), 80]),
                                         ("matrix", [500, 0, 0, 320, 50])])
def test_invalid_serialized_intrinsic_geometry_is_refused(field, value):
    page = bitmap_page()
    page["image_regions"][0][field] = value
    assert complete_bitmap_pixel_size({"l": 26, "t": 170, "r": 526, "b": 490}, page) is None


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_image_matrix_and_page_rotation_compose_without_losing_pixel_axes(rotation):
    page = bitmap_page()
    page["rotation"] = rotation
    page["image_regions"][0].update(matrix=[0, 320, -500, 0, 550, 80])
    box = pdf_box_to_display_top_left([50, 80, 550, 400], page)
    region = dict(zip(("l", "t", "r", "b"), box, strict=True))
    expected = (600, 1000) if rotation in (90, 270) else (1000, 600)
    assert complete_bitmap_pixel_size(region, page) == expected


def test_normal_aspect_and_unknown_intrinsic_geometry_keep_original_size():
    assert reduced_aspect_size((1500, 960), (1000, 600)) == (1500, 960)
    assert reduced_aspect_size((1500, 960), None) == (1500, 960)


def test_experimental_derivatives_are_explicit_boolean_config_and_fingerprinted():
    normal = IngestionConfig.from_mapping({})
    experimental = IngestionConfig.from_mapping({"ocr_intrinsic_aspect": True, "ocr_cell_border": True})
    assert normal.ocr_intrinsic_aspect is normal.ocr_cell_border is False
    assert normal.fingerprint() != experimental.fingerprint()
    with pytest.raises(IngestionError):
        IngestionConfig.from_mapping({"ocr_intrinsic_aspect": "false"})
