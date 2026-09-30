import pytest

from services.ingestion.errors import IngestionError
from services.ingestion.geometry import docling_box_to_pdf


@pytest.mark.parametrize("rotation,size,box", [
    (0, (100, 200), {"l": 10, "b": 20, "r": 30, "t": 50, "coord_origin": "BOTTOMLEFT"}),
    (90, (200, 100), {"l": 20, "b": 70, "r": 50, "t": 90, "coord_origin": "BOTTOMLEFT"}),
    (180, (100, 200), {"l": 70, "b": 150, "r": 90, "t": 180, "coord_origin": "BOTTOMLEFT"}),
    (270, (200, 100), {"l": 150, "b": 10, "r": 180, "t": 30, "coord_origin": "BOTTOMLEFT"}),
    (90, (200, 100), {"l": 20, "t": 10, "r": 50, "b": 30, "coord_origin": "TOPLEFT"}),
])
def test_rotation_and_nonzero_crop_recover_known_pdf_region(rotation, size, box):
    page = {"crop_box": [10, 20, 110, 220], "rotation": rotation}
    assert docling_box_to_pdf(box, size, page) == [20, 40, 40, 70]


def test_unknown_frame_does_not_fabricate_region():
    with pytest.raises(IngestionError, match="repère") as caught:
        docling_box_to_pdf({"l": 1, "b": 1, "r": 2, "t": 2, "coord_origin": "BOTTOMLEFT"}, (300, 300), {"crop_box": [0, 0, 100, 200], "rotation": 0})
    assert caught.value.code == "GEOMETRY_FRAME_MISMATCH"


def test_unknown_origin_is_rejected():
    with pytest.raises(IngestionError) as caught:
        docling_box_to_pdf({"l": 1, "b": 1, "r": 2, "t": 2}, (100, 200), {"crop_box": [0, 0, 100, 200], "rotation": 0})
    assert caught.value.code == "UNKNOWN_COORDINATE_ORIGIN"
