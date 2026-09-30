import pytest
from PIL import Image, ImageDraw

from services.ingestion.regional_grid import (
    bounded_cell_crop,
    read_tesseract_tsv,
    remove_ruled_grid,
    subtract_native_regions,
    temporary_raster,
)
from services.ingestion.regional_tables import rotate_point


def test_ruled_grid_derivative_preserves_frame_and_intercell_marks():
    source = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(source)
    for x in (20, 200, 380, 580):
        draw.line((x, 20, x, 380), fill="black", width=3)
    for y in (20, 140, 260, 380):
        draw.line((20, y, 580, y), fill="black", width=3)
    draw.rectangle((230, 160, 240, 170), fill="black")
    before = source.tobytes()
    derived, metadata = remove_ruled_grid(source)
    assert source.tobytes() == before
    assert derived.size == source.size
    assert derived.getpixel((235, 165)) == (0, 0, 0)
    assert derived.getpixel((200, 90)) == (255, 255, 255)
    assert metadata["horizontal_rules"] == metadata["vertical_rules"] == 4
    assert metadata["source_raster_sha256"] != metadata["derived_raster_sha256"]


def test_isolated_underline_is_unchanged():
    source = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(source).line((20, 120, 580, 120), fill="black", width=3)
    derived, metadata = remove_ruled_grid(source)
    assert metadata is None
    assert derived.tobytes() == source.tobytes()


def test_ocr_tsv_preserves_numeric_source_token_without_float_conversion():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    rows = "1\t1\t0\t0\t0\t0\t0\t0\t200\t80\t-1\t\n5\t1\t1\t1\t1\t1\t20\t15\t35\t30\t96.996071\t24\n"
    frame = read_tesseract_tsv(header + rows)
    assert frame["text"].tolist() == ["24"]
    assert int(frame.iloc[0]["left"]) == 20
    assert float(frame.iloc[0]["conf"]) == 96.996071


def test_ocr_tsv_preserves_na_labels_units_and_unicode_codepoints():
    source = "left\ttop\twidth\theight\tconf\ttext\n" + "".join(
        f"0\t0\t20\t30\t95\t{value}\n" for value in ("NA", "N/A", "nan", "0024", "24.0", "°C", "é😀e\u0301"))
    assert read_tesseract_tsv(source)["text"].tolist() == ["NA", "N/A", "nan", "0024", "24.0", "°C", "é😀e\u0301"]


def test_cell_border_has_exact_inverse_offset_and_preserves_original_pixels():
    source = Image.new("RGB", (500, 250), "white")
    ImageDraw.Draw(source).rectangle((100, 80, 110, 100), fill="black")
    before = source.tobytes()
    patch, offset = bounded_cell_crop(source, [40, 50, 450, 220])
    assert patch.size == (31, 41)
    assert offset == (90, 70)
    assert patch.getpixel((10, 10)) == source.getpixel((100, 80))
    assert source.tobytes() == before
    assert bounded_cell_crop(source, [200, 0, 400, 80]) == (None, None)


def test_private_raster_is_removed_when_png_encoder_fails(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    class BrokenEncoder:
        def save(self, stream, **kwargs):
            stream.write(b"partial private raster")
            raise OSError("isolated encoder error")

    with pytest.raises(OSError, match="isolated encoder error"), temporary_raster(BrokenEncoder()):
        pytest.fail("Encoding failed before a path can be used")
    assert list(tmp_path.iterdir()) == []


def test_rotated_table_coordinate_roundtrip_all_quarter_turns():
    for angle in (0, 90, 180, 270):
        for point in ((0, 0), (500, 0), (500, 320), (0, 320), (35, 150)):
            rotated = rotate_point(*point, 500, 320, angle)
            assert rotate_point(*rotated, 500, 320, angle, inverse=True) == point


def test_ocr_partition_excludes_native_ink_and_preserves_other_area():
    fragments, failed = subtract_native_regions([0, 0, 100, 200], [[20, 50, 80, 100]])
    assert not failed
    assert sum((right - left) * (bottom - top) for left, top, right, bottom in fragments) == 100 * 200 - 60 * 50
    assert all(min(right, 80) <= max(left, 20) or min(bottom, 100) <= max(top, 50) for left, top, right, bottom in fragments)
    assert subtract_native_regions([0, 0, 100, 200], [[20, 50, 80, 100]], limit=2) == ([], True)
