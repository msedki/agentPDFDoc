import pytest
from PIL import Image, ImageDraw

from services.ingestion.regional_grid import (
    bounded_cell_crop,
    read_tesseract_tsv,
    recognize_cell_patch,
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


def test_horizontal_ruled_scan_segments_printed_units_without_a_vertical_grid():
    # DA-P03, inchangé : l'OCR global omet les deux unités « mm ». Ses séparateurs sont gris et seulement horizontaux.
    from pathlib import Path

    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(Path(__file__).resolve().parents[2] / "fixtures/qualification-v2.1/development/Procédures/Atelier 3 - Banc pneumatique DA-P03.pdf")
    page = document[1]
    bitmap = None
    try:
        bitmap = next(iter(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]))).get_bitmap(render=False)
        source = bitmap.to_pil().convert("RGB")
    finally:
        if bitmap is not None:
            bitmap.close()
        page.close()
        document.close()
    before = source.tobytes()
    derived, metadata = remove_ruled_grid(source)
    assert metadata is not None
    assert metadata["algorithm"] == "horizontal-rules-columns-v1"
    assert metadata["vertical_rules"] == 0
    assert len(metadata["grid_cells"]) == 9
    # Les colonnes sont déduites de la séparation de l'encre, jamais du texte attendu.
    for index, token_box in ((2, (1015, 313, 1060, 327)), (5, (1015, 396, 1060, 410)), (8, (1015, 473, 1080, 494))):
        left, top, right, bottom = metadata["grid_cells"][index]
        assert left <= token_box[0] < token_box[2] <= right
        assert top <= token_box[1] < token_box[3] <= bottom
        assert derived.crop(token_box).tobytes() == source.crop(token_box).tobytes()
    assert derived.size == source.size and source.tobytes() == before


@pytest.mark.parametrize("kind", ["no_columns", "filled_band", "unaligned"])
def test_horizontal_rule_candidate_without_table_structure_is_unchanged(kind):
    source = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(source)
    for index, y in enumerate((80, 180, 280)):
        left, right = (20, 580) if kind != "unaligned" else ((20, 340) if index == 0 else (260, 580))
        draw.line((left, y, right, y), fill=(168, 176, 181), width=3)
    for y in (110, 210):
        draw.rectangle((40, y, 70, y + 30), fill="black")
        if kind != "no_columns":
            draw.rectangle((380, y, 410, y + 30), fill="black")
    if kind == "filled_band":
        draw.rectangle((20, 20, 580, 50), fill=(100, 100, 100))
    derived, metadata = remove_ruled_grid(source)
    assert metadata is None
    assert derived.tobytes() == source.tobytes()


def _horizontal_rules_with_columns(extents):
    source = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(source)
    for y, (left, right) in zip((80, 180, 280), extents, strict=True):
        draw.line((left, y, right, y), fill=(168, 176, 181), width=3)
    for y in (110, 210):
        for x in (150, 400):
            draw.rectangle((x, y, x + 30, y + 30), fill="black")
    return source


def test_horizontal_separators_with_large_overlap_but_different_extents_are_refused():
    # Les trois lignes partagent une longue intersection, mais leurs extrémités décrivent des bandes différentes.
    source = _horizontal_rules_with_columns([(20, 580), (20, 500), (80, 580)])
    before = source.tobytes()
    derived, metadata = remove_ruled_grid(source)
    assert metadata is None
    assert derived.tobytes() == before == source.tobytes()


def test_horizontal_separator_alignment_allows_only_raster_rounding():
    source = _horizontal_rules_with_columns([(20, 580), (21, 579), (22, 580)])
    before = source.tobytes()
    derived, metadata = remove_ruled_grid(source)
    assert metadata is not None and metadata["algorithm"] == "horizontal-rules-columns-v1"
    assert len(metadata["grid_cells"]) == 4
    assert derived.size == source.size and source.tobytes() == before


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


def test_cell_crop_ignores_rule_residue_at_the_cell_frame():
    # Reproduit E1 : quelques pixels de règle retirée au bord ramenaient le crop à la cellule entière.
    source = Image.new("RGB", (402, 140), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((21, 48, 58, 90), fill="black")
    for x, y in ((401, 60), (401, 61), (401, 62), (200, 1), (300, 139)):
        source.putpixel((x, y), (89, 89, 89))
    patch, offset = bounded_cell_crop(source, [0, 0, 402, 140])
    assert offset == (11, 38)
    assert patch.size == (58, 63)
    assert bounded_cell_crop(source, [0, 0, 402, 140], edge=0)[0].size == (401, 159)
    residue_only = Image.new("RGB", (402, 140), "white")
    residue_only.putpixel((401, 60), (0, 0, 0))
    assert bounded_cell_crop(residue_only, [0, 0, 402, 140]) == (None, None)


def test_cell_crop_keeps_a_glyph_touching_the_frame_whole():
    source = Image.new("RGB", (300, 120), "white")
    ImageDraw.Draw(source).rectangle((0, 30, 25, 80), fill="black")
    patch, offset = bounded_cell_crop(source, [0, 0, 300, 120])
    assert offset == (-10, 20)
    assert patch.size == (46, 71)
    assert patch.getpixel((10, 10)) == (0, 0, 0)


def _small_glyph_patch(size=(38, 39), ink=(10, 10, 27, 28)):
    patch = Image.new("RGB", size, "white")
    ImageDraw.Draw(patch).rectangle(ink, fill="black")
    return patch


def _cell_frame(text="Vv", confidence=74.086845, box=(10, 10, 18, 19)):
    import pandas as pd

    return pd.DataFrame([dict(zip(("text", "conf", "left", "top", "width", "height"),
                                 (text, confidence, *box), strict=True))])


@pytest.mark.parametrize("confidence", [80, 80.977661])
def test_cell_density_retry_does_not_revisit_an_admissible_baseline(confidence):
    patch, baseline, calls = _small_glyph_patch(), _cell_frame("DA-P03-IN", confidence), []

    def recognize(image):
        calls.append(image.size)
        return baseline

    selected, trace = recognize_cell_patch(patch, recognize, .8, 8_000_000)
    assert selected is baseline and calls == [(38, 39)]
    assert trace["selected"] == "baseline" and not trace["attempted"]
    assert trace["reason"] == "baseline_admissible"


def test_cell_density_retry_accepts_only_admissible_result_and_inverts_all_coordinates():
    import hashlib

    from services.ingestion.regional_aspect import inverse_resized_box

    patch, baseline, calls = _small_glyph_patch(), _cell_frame(), []
    before = patch.tobytes()
    candidate = _cell_frame("V", 89.386497, (20, 20, 35, 38))

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else candidate

    selected, trace = recognize_cell_patch(patch, recognize, .8, 8_000_000)
    assert selected["text"].tolist() == ["V"] and calls == [(38, 39), (76, 78)]
    assert selected.iloc[0][["left", "top", "width", "height"]].tolist() == [10, 10, 17.5, 19]
    assert candidate.iloc[0][["left", "top", "width", "height"]].tolist() == [20, 20, 35, 38]
    assert patch.tobytes() == before
    assert trace["source_raster_sha256"] == hashlib.sha256(before).hexdigest()
    assert trace["derived_raster_sha256"] != trace["source_raster_sha256"]
    assert trace["source_raster_size"] == [38, 39] and trace["derived_raster_size"] == [76, 78]
    assert trace["factor"] == 2 and trace["selected"] == "derived"
    assert trace["baseline_minimum_word_confidence"] == pytest.approx(.74086845)
    assert trace["retry_minimum_word_confidence"] == pytest.approx(.89386497)
    # Repère réel 90° : /2 puis offset de crop, restauration anisotrope, rotation inverse et points PDF originaux.
    local = selected.iloc[0]
    oriented = [local["left"] + 677, local["top"] + 194,
                local["left"] + local["width"] + 677, local["top"] + local["height"] + 194]
    restored = inverse_resized_box(oriented, (960, 1500), (960, 576))
    corners = [rotate_point(x, y, 1500, 960, 90, inverse=True)
               for x in (restored[0], restored[2]) for y in (restored[1], restored[3])]
    physical = [(50 + x / 3, 400 - y / 3) for x, y in corners]
    assert [min(x for x, _ in physical), min(y for _, y in physical),
            max(x for x, _ in physical), max(y for _, y in physical)] == pytest.approx(
                [227.0833333333, 309, 243.5763888889, 314.8333333333])


@pytest.mark.parametrize("candidate_confidence", [79, float("nan"), float("inf"), float("-inf")])
def test_cell_density_retry_rejected_confidence_retains_baseline(candidate_confidence):
    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else _cell_frame("wrong", candidate_confidence, (20, 20, 35, 38))

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected is baseline and len(calls) == 2
    assert trace["selected"] == "baseline" and trace["reason"] == "retry_not_admissible"
    assert trace["retry_minimum_word_confidence"] == (.79 if candidate_confidence == 79 else None)


def test_cell_density_retry_does_not_skip_a_nonfinite_word_inside_a_candidate():
    import pandas as pd

    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else pd.concat(
            [_cell_frame("finite", 95, (20, 20, 10, 20)), _cell_frame("unknown", float("nan"), (40, 20, 10, 20))])

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected is baseline and trace["retry_minimum_word_confidence"] is None
    assert trace["reason"] == "retry_not_admissible"


def test_cell_density_retry_empty_baseline_can_be_recovered():
    baseline, calls = _cell_frame().iloc[0:0], []

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else _cell_frame("V", 90, (20, 20, 35, 38))

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected["text"].tolist() == ["V"] and len(calls) == 2
    assert trace["baseline_minimum_word_confidence"] is None and trace["selected"] == "derived"


@pytest.mark.parametrize("kind", ["nan", "inf", "negative_inf", "mixed_nan"])
def test_cell_density_retry_nonfinite_baseline_remains_visible_without_retry(kind):
    import pandas as pd

    from services.ingestion.regional_grid import _minimum_cell_confidence

    confidence = {"nan": float("nan"), "inf": float("inf"), "negative_inf": float("-inf"), "mixed_nan": float("nan")}[kind]
    baseline, calls = _cell_frame(confidence=confidence), []
    if kind == "mixed_nan":
        baseline = pd.concat([_cell_frame("finite", 95), baseline])

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else _cell_frame("V", 90, (20, 20, 35, 38))

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected is baseline and calls == [(38, 39)]
    assert not trace["attempted"] and trace["selected"] == "baseline"
    assert trace["reason"] == "invalid_baseline_confidence"
    assert trace["baseline_minimum_word_confidence"] is None
    # Le même résultat invalide arrive au contrôle de cellule existant : confiance inconnue, région incertaine.
    assert _minimum_cell_confidence(selected) is None


@pytest.mark.parametrize("kind,reason", [("tall", "ink_height_limit"), ("wide", "crop_dimensions_limit"),
                                         ("multiple", "multiple_ink_components"), ("empty", "no_ink")])
def test_cell_density_retry_refuses_large_or_ambiguous_rasters(kind, reason):
    patch = _small_glyph_patch((64, 70), (10, 10, 30, 40)) if kind == "tall" else _small_glyph_patch()
    if kind == "wide":
        patch = _small_glyph_patch((200, 39), (10, 10, 180, 28))
    elif kind == "multiple":
        ImageDraw.Draw(patch).rectangle((30, 10, 31, 28), fill="black")
    elif kind == "empty":
        patch = Image.new("RGB", (38, 39), "white")
    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline

    selected, trace = recognize_cell_patch(patch, recognize, .8, 8_000_000)
    assert selected is baseline and len(calls) == 1
    assert trace["reason"] == reason and not trace["attempted"]


@pytest.mark.parametrize("budget,attempted", [(76 * 78 - 1, False), (76 * 78, True)])
def test_cell_density_retry_checks_exact_derivative_pixel_budget(budget, attempted):
    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, budget)
    assert selected is baseline and len(calls) == 1 + attempted
    assert trace["attempted"] == attempted
    assert trace["derived_render_pixels"] == 76 * 78 and trace["pixel_limit"] == budget
    assert trace["reason"] == ("retry_not_admissible" if attempted else "derivative_pixel_limit")


def test_cell_density_retry_never_invents_an_admission_threshold():
    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, None, 8_000_000)
    assert selected is baseline and len(calls) == 1
    assert trace["reason"] == "threshold_not_configured"


def test_cell_density_retry_rejects_invalid_derived_geometry():
    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        return baseline if len(calls) == 1 else _cell_frame("V", 90, (20, 20, 1000, 38))

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected is baseline and len(calls) == 2
    assert trace["reason"] == "retry_invalid_geometry"


@pytest.mark.parametrize("kind", ["return_code", "timeout", "io"])
def test_cell_density_retry_failure_keeps_baseline_without_parser_output(kind):
    import subprocess

    baseline, calls = _cell_frame(), []

    def recognize(image):
        calls.append(image.size)
        if len(calls) == 1:
            return baseline
        if kind == "return_code":
            raise subprocess.CalledProcessError(1, ["tesseract"], stderr=b"private parser output")
        if kind == "timeout":
            raise subprocess.TimeoutExpired(["tesseract"], 30, stderr=b"private parser output")
        raise OSError("private raster path")

    selected, trace = recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)
    assert selected is baseline and len(calls) == 2
    assert trace["reason"] == "retry_failed" and trace["selected"] == "baseline"
    assert "private" not in str(trace)


def test_cell_density_retry_never_masks_a_baseline_engine_failure():
    import subprocess

    def recognize(image):
        raise subprocess.CalledProcessError(1, ["tesseract"], stderr=b"private parser output")

    with pytest.raises(subprocess.CalledProcessError):
        recognize_cell_patch(_small_glyph_patch(), recognize, .8, 8_000_000)


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
