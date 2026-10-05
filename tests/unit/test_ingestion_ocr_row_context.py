"""Deterministic row-policy and real hook tests with named OCR/model doubles."""

import hashlib
import json
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest
from PIL import Image, ImageDraw, ImageOps

from services.ingestion import regional_grid
from services.ingestion.regional_aspect import inverse_resized_box
from services.ingestion.regional_row_context import recognize_grid_rows
from services.ingestion.regional_tables import rotate_point


def _frame(text="DA-PO3-LEAK", confidence=70.787102, box=(30, 65, 195, 23)):
    return pd.DataFrame([dict(zip(("text", "conf", "left", "top", "width", "height"),
                                 (text, confidence, *box), strict=True))])


def _rows(count=1):
    image = Image.new("RGB", (800, 80 * count + 60), "white")
    draw = ImageDraw.Draw(image)
    cells, baselines, evidence = [], [], []
    for row in range(count):
        dy = row * 80
        cells.extend([[20, 40 + dy, 260, 100 + dy], [264, 40 + dy, 520, 100 + dy],
                      [524, 40 + dy, 760, 100 + dy]])
        for text, confidence, box in (("DA-PO3-LEAK", 70.787102, (30, 65 + dy, 195, 23)),
                                      ("0.3", 95.565926, (400, 65 + dy, 44, 23)),
                                      ("L/min", 94.170029, (620, 65 + dy, 78, 25))):
            left, top, width, height = box
            draw.rectangle((left, top, left + width - 1, top + height - 1), fill="black")
            baselines.append(_frame(text, confidence, box))
            evidence.append({"printed": True, "crop": {"policy": "ink_border_10",
                                                       "density_retry": {"attempted": False}}})
    return image, cells, baselines, evidence


def _candidate():
    # A named OCR double, not a claim that black rectangles were recognized.
    return pd.concat([_frame("DA-P03-LEAK", 80.023476, (10, 10, 195, 23)),
                      _frame("0.3", 95.565926, (380, 10, 44, 23)),
                      _frame("L/min", 94.170029, (600, 10, 78, 25))], ignore_index=True)


def _run(source, recognize, threshold=.8, budget=13_000_000):
    return recognize_grid_rows(*source, recognize, threshold, budget)


def test_row_context_recovers_only_low_cell_at_native_density_with_exact_offsets():
    source = _rows()
    image, _, baseline, _ = source
    originals = [frame.copy(deep=True) for frame in baseline]
    before, candidate, calls = image.tobytes(), _candidate(), []
    candidate_before = candidate.copy(deep=True)

    def RowOcrDouble(patch):
        calls.append(patch.size)
        return candidate

    selected, traces, budget = _run(source, RowOcrDouble)
    assert calls == [(688, 45)]
    assert selected[0]["text"].tolist() == ["DA-P03-LEAK"]
    assert selected[0].iloc[0][["left", "top", "width", "height"]].tolist() == [30, 65, 195, 23]
    assert selected[1] is baseline[1] and selected[2] is baseline[2]
    for actual, original in zip(baseline, originals, strict=True):
        pd.testing.assert_frame_equal(actual, original)
    pd.testing.assert_frame_equal(candidate, candidate_before)
    assert image.tobytes() == before
    trace = traces[0]
    assert trace["selected"] == "row_context" and trace["adopted_cell_indices"] == [0]
    assert trace["raster_offset"] == [20, 55] and trace["factor"] == trace["coordinate_inverse_factor"] == 1
    assert trace["candidate_minimum_word_confidence"] == pytest.approx(.80023476)
    assert trace["source_crop_size"] == [740, 60] and trace["context_raster_size"] == [688, 45]
    assert trace["source_crop_sha256"] == hashlib.sha256(image.crop((20, 40, 760, 100)).tobytes()).hexdigest()
    assert budget == {"pixel_limit": 13_000_000, "cumulative_crop_pixels": 740 * 60 + 688 * 45,
                      "additional_ocr_calls": 1, "additional_ocr_call_limit": 32}
    assert all(text not in json.dumps(traces) for text in ("DA-P03-LEAK", "DA-PO3-LEAK", "0.3", "L/min"))


def test_row_context_accepts_integral_float_cell_coordinates_without_changing_source():
    image, cells, baseline, evidence = _rows()
    floating = [[float(value) for value in bounds] for bounds in cells]
    selected, traces, _ = _run((image, floating, baseline, evidence), lambda patch: _candidate())
    assert selected[0]["text"].tolist() == ["DA-P03-LEAK"]
    assert traces[0]["raster_bbox"] == [20, 40, 760, 100]
    assert floating == [[float(value) for value in bounds] for bounds in cells]


def test_row_context_uses_exact_word_confidence_threshold():
    candidate = _candidate()
    candidate.loc[0, "conf"] = 80
    selected, traces, _ = _run(_rows(), lambda patch: candidate)
    assert selected[0]["conf"].tolist() == [80]
    assert traces[0]["selected"] == "row_context"


@pytest.mark.parametrize("confidence", [79.999999, float("nan"), float("inf"), float("-inf")])
def test_row_context_rejects_any_low_or_nonfinite_candidate_word(confidence):
    source, candidate = _rows(), _candidate()
    candidate.loc[1, "conf"] = confidence
    selected, traces, budget = _run(source, lambda patch: candidate)
    assert all(frame is baseline for frame, baseline in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == "candidate_not_admissible"
    assert traces[0]["attempted"] and budget["additional_ocr_calls"] == 1


@pytest.mark.parametrize("field,value", [("left", float("nan")), ("top", float("inf")),
                                         ("width", 0), ("height", -1), ("left", -1), ("width", 900)])
def test_row_context_rejects_invalid_candidate_geometry(field, value):
    source, candidate = _rows(), _candidate()
    candidate[field] = candidate[field].astype(float)
    candidate.loc[0, field] = value
    selected, traces, _ = _run(source, lambda patch: candidate)
    assert all(frame is baseline for frame, baseline in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == "candidate_invalid_geometry"


@pytest.mark.parametrize("box", [(235, 10, 10, 23), (240, 10, 4, 23), (10, 0, 195, 23)])
def test_row_context_rejects_gutter_or_word_outside_cell_even_with_a_contained_center(box):
    source, candidate = _rows(), _candidate()
    # First box has its center in the first cell but crosses the gutter.
    candidate.loc[0, ["left", "top", "width", "height"]] = box
    if box[1] == 0:
        # Restore the word at row y39, just outside its top40, while staying in the patch.
        source[0].paste("white", (0, 40, 800, 140))
        ImageDraw.Draw(source[0]).rectangle((30, 49, 224, 71), fill="black")
        ImageDraw.Draw(source[0]).rectangle((400, 49, 443, 71), fill="black")
        ImageDraw.Draw(source[0]).rectangle((620, 49, 697, 73), fill="black")
    selected, traces, _ = _run(source, lambda patch: candidate)
    assert all(frame is baseline for frame, baseline in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == "candidate_word_not_in_unique_cell"


def test_row_context_accepts_exact_cell_edges_with_positive_word_size():
    image, cells, baselines, evidence = _rows()
    cells[0][0], cells[0][2], cells[0][1], cells[0][3] = 30, 225, 65, 90
    cells[1][1], cells[1][3] = 65, 90
    cells[2][1], cells[2][3] = 65, 90
    selected, traces, _ = _run((image, cells, baselines, evidence), lambda patch: _candidate())
    assert selected[0]["text"].tolist() == ["DA-P03-LEAK"]
    assert traces[0]["reason"] == "candidate_admissible"


@pytest.mark.parametrize("kind", ["overlapping_cells", "overlapping_rows", "fractional", "nonfinite", "single_cell", "outside"])
def test_row_context_requires_an_established_valid_grid_before_allocating(kind, monkeypatch):
    image, cells, baseline, evidence = _rows(2)
    if kind == "overlapping_cells":
        cells[1][0] = 250
    elif kind == "overlapping_rows":
        for box in cells[3:]:
            box[1], box[3] = 90, 150
    elif kind == "fractional":
        cells[0][0] = 20.5
    elif kind == "nonfinite":
        cells[0][0] = float("nan")
    elif kind == "single_cell":
        cells, baseline, evidence = cells[:1], baseline[:1], evidence[:1]
    else:
        cells[0][0] = -1

    def NoCropDouble(*args, **kwargs):
        pytest.fail("Invalid grid must be rejected before allocation")

    monkeypatch.setattr(Image.Image, "crop", NoCropDouble)
    selected, traces, budget = _run((image, cells, baseline, evidence), NoCropDouble)
    assert all(frame is original for frame, original in zip(selected, baseline, strict=True))
    assert traces[0]["reason"] == "invalid_grid_geometry"
    assert budget["cumulative_crop_pixels"] == budget["additional_ocr_calls"] == 0


@pytest.mark.parametrize("omitted", [0, 1, 2])
def test_row_context_requires_each_printed_cell_in_the_candidate(omitted):
    source, candidate = _rows(), _candidate().drop(index=omitted)
    selected, traces, _ = _run(source, lambda patch: candidate)
    assert all(frame is original for frame, original in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == "candidate_printed_cells_mismatch"


@pytest.mark.parametrize("baseline_text,candidate_text", [("0024", "24"), ("NA", "nan"), ("N·m", "N-m"),
                                                         ("±", "+"), ("0/O", "O/0"), ("e\u0301", "é")])
def test_row_context_rejects_changed_literal_in_an_admissible_neighbor(baseline_text, candidate_text):
    source, candidate = _rows(), _candidate()
    source[2][1].loc[0, "text"] = baseline_text
    candidate.loc[1, "text"] = candidate_text
    selected, traces, _ = _run(source, lambda patch: candidate)
    assert all(frame is original for frame, original in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == "candidate_changed_admissible_cell"


def test_row_context_preserves_nominal_multitoken_order_and_literal_unicode():
    source, candidate = _rows(), _candidate()
    source[2][1] = pd.concat([_frame("NA", 94, (400, 65, 10, 23)),
                             _frame("é😀e\u0301", 95, (420, 65, 24, 23))], ignore_index=True)
    candidate = pd.concat([candidate.iloc[:1], _frame("NA", 99, (380, 10, 10, 23)),
                           _frame("é😀e\u0301", 99, (400, 10, 24, 23)), candidate.iloc[2:]], ignore_index=True)
    selected, traces, _ = _run(source, lambda patch: candidate)
    assert selected[1] is source[2][1]
    assert selected[1]["text"].tolist() == ["NA", "é😀e\u0301"]
    assert selected[1]["conf"].tolist() == [94, 95]
    assert traces[0]["selected"] == "row_context"
    reversed_candidate = pd.concat([candidate.iloc[:1], candidate.iloc[1:3].iloc[::-1], candidate.iloc[3:]], ignore_index=True)
    selected, traces, _ = _run(source, lambda patch: reversed_candidate)
    assert selected[0] is source[2][0] and traces[0]["reason"] == "candidate_changed_admissible_cell"


def test_row_context_can_recover_a_truly_empty_printed_baseline():
    source = _rows()
    source[2][0] = source[2][0].iloc[:0]
    selected, traces, _ = _run(source, lambda patch: _candidate())
    assert selected[0]["text"].tolist() == ["DA-P03-LEAK"]
    assert traces[0]["adopted_cell_indices"] == [0]


def test_row_context_never_adds_words_to_a_nonprinted_cell():
    source = _rows()
    source[3][2]["printed"] = False
    source[2][2] = source[2][2].iloc[:0]
    selected, traces, _ = _run(source, lambda patch: _candidate())
    assert selected[0] is source[2][0] and selected[2].empty
    assert traces[0]["reason"] == "candidate_printed_cells_mismatch"


def test_row_context_preserves_an_empty_nonprinted_cell_when_candidate_agrees():
    source = _rows()
    source[3][2]["printed"] = False
    source[2][2] = source[2][2].iloc[:0]
    selected, traces, _ = _run(source, lambda patch: _candidate().iloc[:2])
    assert selected[0]["text"].tolist() == ["DA-P03-LEAK"]
    assert selected[2] is source[2][2] and selected[2].empty
    assert traces[0]["selected"] == "row_context"


@pytest.mark.parametrize("kind", ["admissible", "nonfinite", "mixed_nonfinite", "geometry_nonfinite",
                                 "mono_low", "mono_nominal", "border_disabled", "threshold_none"])
def test_row_context_exclusions_never_allocate_or_invoke_ocr(kind, monkeypatch):
    source, threshold = _rows(), .8
    reasons = {"admissible": "baseline_admissible", "nonfinite": "invalid_baseline_confidence",
               "mixed_nonfinite": "invalid_baseline_confidence", "geometry_nonfinite": "invalid_baseline_geometry",
               "mono_low": "mono_glyph_retry_already_attempted", "mono_nominal": "mono_glyph_retry_already_attempted",
               "border_disabled": "cell_border_not_configured", "threshold_none": "threshold_not_configured"}
    if kind == "admissible":
        source[2][0].loc[0, "conf"] = 80
    elif kind in ("nonfinite", "mixed_nonfinite"):
        source[2][0].loc[0, "conf"] = float("nan")
        if kind == "mixed_nonfinite":
            source[2][0] = pd.concat([_frame("finite", 95), source[2][0]], ignore_index=True)
    elif kind == "geometry_nonfinite":
        source[2][0]["left"] = source[2][0]["left"].astype(float)
        source[2][0].loc[0, "left"] = float("inf")
    elif kind.startswith("mono_"):
        source[3][0 if kind == "mono_low" else 1]["crop"]["density_retry"]["attempted"] = True
    elif kind == "border_disabled":
        source[3][0]["crop"]["policy"] = "full_grid_cell"
    else:
        threshold = None

    def NoAllocationDouble(*args, **kwargs):
        pytest.fail("Excluded row must not allocate or recognize")

    monkeypatch.setattr(Image.Image, "crop", NoAllocationDouble)
    selected, traces, budget = _run(source, NoAllocationDouble, threshold)
    assert all(frame is original for frame, original in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == reasons[kind] and not traces[0]["attempted"]
    assert budget["additional_ocr_calls"] == budget["cumulative_crop_pixels"] == 0


@pytest.mark.parametrize("width,height", [(2049, 128), (2048, 129)])
def test_row_context_dimension_guard_precedes_source_crop(width, height):
    class UnallocatedRasterDouble:
        def __init__(self):
            self.width, self.height = width, height
            self.size = (width, height)

        def crop(self, bounds):
            pytest.fail("Oversized row must be rejected before source crop")

    cells = [[0, 0, width // 2 - 2, height], [width // 2 + 2, 0, width, height]]
    baseline = [_frame(box=(10, 10, 20, 20)), _frame("NA", 95, (width // 2 + 10, 10, 20, 20))]
    evidence = _rows()[3][:2]
    selected, traces, budget = _run((UnallocatedRasterDouble(), cells, baseline, evidence), lambda patch: pytest.fail("No OCR"))
    assert selected[0] is baseline[0] and traces[0]["reason"] == "source_crop_dimensions_limit"
    assert budget["cumulative_crop_pixels"] == 0


def test_row_context_accepts_the_source_dimension_boundary():
    image = Image.new("RGB", (2048, 128), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 40, 39, 59), fill="black")
    draw.rectangle((1100, 40, 1119, 59), fill="black")
    cells = [[0, 0, 1022, 128], [1026, 0, 2048, 128]]
    baseline = [_frame(box=(20, 40, 20, 20)), _frame("NA", 95, (1100, 40, 20, 20))]
    candidate = pd.concat([_frame("recovered", 95, (10, 10, 20, 20)),
                           _frame("NA", 95, (1090, 10, 20, 20))], ignore_index=True)
    selected, traces, _ = _run((image, cells, baseline, _rows()[3][:2]), lambda patch: candidate)
    assert selected[0]["text"].tolist() == ["recovered"]
    assert traces[0]["source_crop_size"] == [2048, 128]


def test_row_context_final_crop_guard_precedes_border_allocation(monkeypatch):
    image = Image.new("RGB", (2048, 70), "white")
    ImageDraw.Draw(image).rectangle((0, 20, 2047, 42), fill="black")
    cells = [[0, 0, 1022, 70], [1026, 0, 2048, 70]]
    baseline = [_frame(box=(20, 20, 20, 23)), _frame("NA", 95, (1100, 20, 20, 23))]

    def NoExpandDouble(*args, **kwargs):
        pytest.fail("Final width2068 must be refused before border allocation")

    monkeypatch.setattr(ImageOps, "expand", NoExpandDouble)
    selected, traces, budget = _run((image, cells, baseline, _rows()[3][:2]), NoExpandDouble)
    assert selected[0] is baseline[0] and traces[0]["reason"] == "context_crop_dimensions_limit"
    assert traces[0]["context_raster_size"] == [2068, 43]
    assert budget["cumulative_crop_pixels"] == 2048 * 70 and budget["additional_ocr_calls"] == 0


@pytest.mark.parametrize("ink_height,attempted", [(48, True), (49, False)])
def test_row_context_ink_height_bound_precedes_final_crop(ink_height, attempted, monkeypatch):
    source = _rows()
    source[0].paste("white", (0, 0, 800, 140))
    ImageDraw.Draw(source[0]).rectangle((30, 45, 224, 44 + ink_height), fill="black")
    calls = []
    original_expand = ImageOps.expand

    def ExpandSpy(*args, **kwargs):
        calls.append("expand")
        return original_expand(*args, **kwargs)

    monkeypatch.setattr(ImageOps, "expand", ExpandSpy)
    _, traces, budget = _run(source, lambda patch: source[2][0].iloc[:0])
    assert traces[0]["ink_height"] == ink_height
    assert calls == (["expand"] if attempted else [])
    assert budget["additional_ocr_calls"] == int(attempted)
    assert traces[0]["reason"] == ("candidate_not_admissible" if attempted else "ink_height_limit")


def test_row_context_source_pixel_budget_precedes_any_crop(monkeypatch):
    def NoCropDouble(*args, **kwargs):
        pytest.fail("Source pixel budget must be checked first")

    monkeypatch.setattr(Image.Image, "crop", NoCropDouble)
    _, traces, budget = _run(_rows(), NoCropDouble, budget=740 * 60 - 1)
    assert traces[0]["reason"] == "crop_pixel_limit"
    assert budget["cumulative_crop_pixels"] == 0


@pytest.mark.parametrize("remaining,attempted", [(-1, False), (0, True)])
def test_row_context_exact_cumulative_pixel_budget_precedes_final_crop(remaining, attempted, monkeypatch):
    source, crops = _rows(), []
    original_crop = Image.Image.crop

    def CropSpy(image, bounds):
        crops.append(bounds)
        return original_crop(image, bounds)

    monkeypatch.setattr(Image.Image, "crop", CropSpy)
    _, traces, budget = _run(source, lambda patch: _candidate(), budget=740 * 60 + 688 * 45 + remaining)
    assert len(crops) == (2 if attempted else 1)
    assert traces[0]["attempted"] == attempted
    assert traces[0]["reason"] == ("candidate_admissible" if attempted else "cumulative_pixel_limit")
    assert budget["cumulative_crop_pixels"] == 740 * 60 + (688 * 45 if attempted else 0)


@pytest.mark.parametrize("error", [None, "returncode", "timeout", "io"])
def test_row_context_rejected_or_failed_attempt_consumes_cumulative_budget(error):
    source, calls = _rows(2), []

    def RejectedRowOcrDouble(patch):
        calls.append(patch.size)
        if error == "returncode":
            raise subprocess.CalledProcessError(2, ["tesseract"], output=b"private OCR text", stderr=b"private error")
        if error == "timeout":
            raise subprocess.TimeoutExpired(["tesseract"], 30, output=b"private OCR text")
        if error == "io":
            raise OSError("private raster path")
        candidate = _candidate()
        candidate.loc[0, "conf"] = 79
        return candidate

    selected, traces, budget = _run(source, RejectedRowOcrDouble, budget=740 * 60 + 688 * 45 + 740 * 60 - 1)
    assert calls == [(688, 45)]
    assert all(frame is original for frame, original in zip(selected, source[2], strict=True))
    assert traces[0]["reason"] == ("context_recognition_failed" if error else "candidate_not_admissible")
    assert traces[1]["reason"] == "cumulative_pixel_limit" and not traces[1]["attempted"]
    assert budget["cumulative_crop_pixels"] == 740 * 60 + 688 * 45 and budget["additional_ocr_calls"] == 1
    assert "private" not in json.dumps(traces)


def test_row_context_additional_call_limit_is_shared_by_all_rows_and_resets_next_region():
    source, calls = _rows(33), []

    def EmptyRowOcrDouble(patch):
        calls.append(patch.size)
        return _candidate().iloc[:0]

    _, traces, budget = _run(source, EmptyRowOcrDouble)
    assert len(calls) == budget["additional_ocr_calls"] == 32
    assert traces[31]["attempted"] and not traces[32]["attempted"]
    assert traces[32]["reason"] == "additional_call_limit"
    assert budget["cumulative_crop_pixels"] == 32 * (740 * 60 + 688 * 45)
    _, traces, budget = _run(_rows(), EmptyRowOcrDouble)
    assert traces[0]["attempted"] and budget["additional_ocr_calls"] == 1


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_row_context_offset_and_native_density_compose_with_existing_inverse_geometry(angle):
    selected, _, _ = _run(_rows(), lambda patch: _candidate())
    word = selected[0].iloc[0]
    restored = inverse_resized_box([word.left, word.top, word.left + word.width, word.top + word.height],
                                  (1600, 210), (800, 140))
    assert restored == [60, 97.5, 450, 132]
    corners = [rotate_point(x, y, 1600, 210, angle, inverse=True)
               for x in (restored[0], restored[2]) for y in (restored[1], restored[3])]
    for point, rotated in zip(((60, 97.5), (60, 132), (450, 97.5), (450, 132)), corners, strict=True):
        assert rotate_point(*rotated, 1600, 210, angle) == point
    # Source patch coordinates are not divided by the mono-glyph factor2.
    assert word.left == 30 and word.top == 65


def _hook_model(monkeypatch, image, cells, *, cell_border=True):
    class TesseractCliModelDouble:
        def __init__(self, *, options, **kwargs):
            self.options = options
            self.scale = 3
            self._safe_tesseract_cmd = "/private/tesseract-5.4.0"
            self._native_codes = ["fra", "eng"]
            self._safe_tessdata_path = "/private/tessdata"
            self._auto_script = False

        @staticmethod
        def _sanitize_filename(filename):
            return filename

    class StandardPdfPipelineDouble:
        pass

    tesseract_module = ModuleType("docling.models.stages.ocr.tesseract_ocr_cli_model")
    tesseract_module.TesseractOcrCliModel = TesseractCliModelDouble
    pipeline_module = ModuleType("docling.pipeline.standard_pdf_pipeline")
    pipeline_module.StandardPdfPipeline = StandardPdfPipelineDouble
    monkeypatch.setitem(sys.modules, tesseract_module.__name__, tesseract_module)
    monkeypatch.setitem(sys.modules, pipeline_module.__name__, pipeline_module)

    class BoundingBoxDouble:
        def __init__(self, **values):
            self.__dict__.update(values)

        def model_dump(self, **kwargs):
            return vars(self).copy()

    geometry_calls = []

    def TesseractGeometryDouble(box, **kwargs):
        geometry_calls.append({"bounds": [box.l, box.t, box.r, box.b], **kwargs})
        return SimpleNamespace(to_bounding_box=lambda: box)

    utils_module = ModuleType("docling.models.stages.ocr.tesseract_utils")
    utils_module.tesseract_box_to_bounding_rectangle = TesseractGeometryDouble
    core_module = ModuleType("docling_core.types.doc")
    core_module.BoundingBox = BoundingBoxDouble
    core_module.CoordOrigin = SimpleNamespace(TOPLEFT="TOPLEFT")
    monkeypatch.setitem(sys.modules, utils_module.__name__, utils_module)
    monkeypatch.setitem(sys.modules, core_module.__name__, core_module)

    def EstablishedGridDouble(raster):
        return image, {"algorithm": "horizontal-rules-columns-v1", "grid_cells": cells,
                       "rectangular_grid": False, "width": image.width, "height": image.height}

    monkeypatch.setattr(regional_grid, "remove_ruled_grid", EstablishedGridDouble)
    pipeline = regional_grid.regional_pipeline_class(max_region_pixels=13_000_000, cell_border=cell_border,
                                                     minimum_confidence=.8)()
    pipeline.pipeline_options = SimpleNamespace(do_ocr=True, ocr_options=SimpleNamespace(psm=3),
                                               accelerator_options=None)
    model = pipeline._make_ocr_model(None)
    model._current_rects = [BoundingBoxDouble(l=0, t=0, r=image.width / 3, b=image.height / 3,
                                            coord_origin="TOPLEFT")]
    model._current_orientations = [{"resolved": True, "orientation_degrees": 0,
                                   "source_raster_size": list(image.size), "derivative_raster_size": list(image.size)}]
    return model, geometry_calls


@pytest.mark.parametrize("kind", ["recovered", "candidate_low", "candidate_empty", "candidate_gutter", "baseline_empty", "baseline_empty_rejected",
                                 "baseline_nonfinite", "retry_error", "nominal", "border_disabled"])
def test_real_grid_hook_preserves_neighbors_and_publishes_only_final_uncertainty(kind, monkeypatch, tmp_path):
    source = _rows()
    image, cells, baseline, _ = source
    if kind in ("baseline_empty", "baseline_empty_rejected"):
        baseline[0] = baseline[0].iloc[:0]
    elif kind == "baseline_nonfinite":
        baseline[0].loc[0, "conf"] = float("nan")
    elif kind == "nominal":
        baseline[0].loc[0, "conf"] = 90
    row_candidate = _candidate()
    if kind == "candidate_low":
        row_candidate.loc[0, "conf"] = 79
    elif kind in ("candidate_empty", "baseline_empty_rejected"):
        row_candidate = row_candidate.iloc[:0]
    elif kind == "candidate_gutter":
        row_candidate.loc[0, ["left", "width"]] = [235, 10]
    border = kind != "border_disabled"
    model, geometry_calls = _hook_model(monkeypatch, image, cells, cell_border=border)
    global_frame = _frame("HEADER", 99, (30, 10, 120, 20))
    cell_returns = []
    for bounds, frame in zip(cells, baseline, strict=True):
        _, offset = regional_grid.bounded_cell_crop(image, bounds) if border else (None, bounds[:2])
        local = frame.copy()
        local["left"] -= offset[0]
        local["top"] -= offset[1]
        cell_returns.append(local)
    responses, commands, raster_sizes = [global_frame, *cell_returns, row_candidate], [], []

    def TsvEngineDouble(command, **kwargs):
        commands.append(command)
        assert kwargs == {"capture_output": True, "check": True, "shell": False,
                          "stdin": subprocess.DEVNULL, "timeout": 30}
        assert command[0] == "/private/tesseract-5.4.0" and command[1:3] == ["-l", "fra+eng"]
        assert command[3:5] == ["--tessdata-dir", "/private/tessdata"] and command[-2:] == ["stdout", "tsv"]
        with Image.open(command[-3]) as raster:
            raster_sizes.append(raster.size)
        if len(commands) == 5 and kind == "retry_error":
            raise subprocess.CalledProcessError(2, command, output=b"private OCR text", stderr=b"private error")
        return subprocess.CompletedProcess(command, 0, responses[len(commands) - 1].to_csv(sep="\t", index=False, na_rep="nan").encode(), b"")

    monkeypatch.setattr(subprocess, "run", TsvEngineDouble)
    filename = tmp_path / "isolated-row.png"
    image.save(filename)
    selected = model._run_tesseract(str(filename), None)
    metadata = model._current_preprocessing[0]
    attempted = kind not in ("baseline_nonfinite", "nominal", "border_disabled")
    adopted = kind in ("recovered", "baseline_empty")
    assert len(commands) == 4 + attempted
    assert all(command[command.index("--psm") + 1] == "6" for command in commands[1:])
    if attempted:
        assert raster_sizes[-1] == (688, 45)
    assert selected.iloc[0]["text"] == "HEADER"
    assert selected["text"].tolist() == ["HEADER", *(("DA-P03-LEAK",) if adopted else baseline[0]["text"]), "0.3", "L/min"]
    for index in (1, 2):
        pd.testing.assert_frame_equal(selected.iloc[-3 + index:].iloc[:1].reset_index(drop=True), baseline[index], check_dtype=False)
    evidence = metadata["cell_ocr"][0]
    assert evidence["recognized_words"] == (1 if adopted else len(baseline[0]))
    assert evidence["minimum_word_confidence"] == (pytest.approx(.80023476) if adopted else regional_grid._minimum_cell_confidence(baseline[0]))
    unresolved = baseline[0].empty and not adopted
    uncertain = not adopted and kind != "nominal" and not baseline[0].empty
    assert ("unresolved_parser_bbox" in evidence) == unresolved
    assert ("uncertain_parser_bbox" in evidence) == uncertain
    assert len(geometry_calls) == int(unresolved or uncertain)
    if adopted:
        assert evidence["row_context_retry"] == {"row_index": 0, "selected": "row_context"}
    assert metadata["row_context_budget"]["additional_ocr_calls"] == int(attempted)
    assert all("row_context_retry" not in metadata["cell_ocr"][index] for index in (1, 2))
    assert all(token not in json.dumps(metadata) for token in ("DA-P03-LEAK", "DA-PO3-LEAK", "private OCR text", "private error"))


def test_real_cell_hook_baseline_engine_failure_is_not_contained(monkeypatch):
    image, cells, _, _ = _rows()
    model, _ = _hook_model(monkeypatch, image, cells)

    def BaselineEngineFailureDouble(command, **kwargs):
        raise subprocess.CalledProcessError(2, command, stderr=b"private first-call error")

    monkeypatch.setattr(subprocess, "run", BaselineEngineFailureDouble)
    with pytest.raises(subprocess.CalledProcessError):
        model._cell_ocr(image, cells[0])
