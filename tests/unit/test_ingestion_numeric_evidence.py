"""Numeric-role OCR policy with named recognition doubles, not native OCR scores."""

import base64
import hashlib
import json

import pandas as pd
import pytest
from PIL import Image, ImageDraw

from services.ingestion import numeric_evidence
from services.ingestion.docling_adapter import document_to_pages
from services.ingestion.regional_row_context import recognize_grid_rows


def frame(text, left, top, confidence=95):
    return pd.DataFrame([{"text": text, "left": left, "top": top, "width": 80, "height": 24,
                          "conf": confidence}])


def table(raw="OV", headers=("Min", "Max")):
    image = Image.new("RGB", (800, 180), "white")
    draw = ImageDraw.Draw(image)
    cells = [[20, 20, 370, 70], [380, 20, 760, 70], [20, 80, 370, 140], [380, 80, 760, 140]]
    baselines = [frame(headers[0], 30, 30), frame(headers[1], 390, 30), frame(raw, 30, 90), frame("36V", 390, 90)]
    for baseline in baselines:
        word = baseline.iloc[0]
        draw.rectangle((word.left, word.top, word.left + word.width - 1, word.top + word.height - 1), fill="black")
    evidence = [{"printed": True, "crop": {"policy": "ink_border_10", "density_retry": {"attempted": False}}}
                for _ in cells]
    return image, cells, baselines, evidence


def candidate(text="0V", factor=1):
    # Named recognition double on black rectangles; original offset (20,80).
    result = pd.concat([frame(text, 10, 10), frame("36V", 370, 10)], ignore_index=True)
    for field in ("left", "top", "width", "height"):
        result[field] *= factor
    return result


@pytest.mark.parametrize("raw,issues", [("OV", ("letter_o_in_numeric_field",)),
                                       ("O V", ("letter_o_in_numeric_field",)),
                                       ("-O,5 mV", ("letter_o_in_numeric_field",)),
                                       ("–3 V", ("ambiguous_dash_sign",)),
                                       ("0 V", ()), ("OPA036", ()), ("OVP", ()),
                                       ("NOMINAL", ()), ("0x0F", ()), ("—", ()), ("±3 V", ())])
def test_ambiguity_detection_is_narrow_and_keeps_component_codes(raw, issues):
    assert numeric_evidence.numeric_ambiguities(raw) == issues


@pytest.mark.parametrize("raw,recovered,accepted", [("OV", "0 V", True), ("-O,5 V", "−0.5 V", True),
                                                     ("3O", "30", True), ("–3 V", "-3 V", True),
                                                     ("OV", "OV", False), ("OV", "0 A", False),
                                                     ("3O", "80", False), ("-OV", "0 V", False),
                                                     ("0 V", "0 V", False)])
def test_candidate_must_be_actual_clear_reading_with_same_unaffected_value_and_unit(raw, recovered, accepted):
    assert numeric_evidence.numeric_candidate_admissible(raw, recovered) is accepted


def test_high_confidence_ambiguity_triggers_one_row_call_and_preserves_private_raw_reading():
    source, readings, calls = table(), [], []
    image_before = source[0].tobytes()

    def RecognitionDouble(patch):
        calls.append(patch.size)
        return candidate()

    selected, traces, budget = recognize_grid_rows(*source, RecognitionDouble, .8, 13_000_000,
                                                   private_numeric_readings=readings)
    assert budget["additional_ocr_calls"] == len(calls) == 1
    assert selected[2]["text"].tolist() == ["0V"]
    assert selected[3] is source[2][3]
    assert source[2][2]["text"].tolist() == ["OV"] and source[0].tobytes() == image_before
    assert traces[1]["trigger"] == "numeric_field_ambiguity"
    assert source[3][2]["numeric_ambiguity_unresolved"] is False
    assert traces[1]["factor"] == 1 and traces[1]["coordinate_inverse_factor"] == 1
    assert selected[2]["left"].tolist() == [30]
    assert readings[0]["cells"][0]["raw_text"] == "OV"
    assert readings[0]["candidate_tokens"][0]["text"] == "0V"
    assert readings[0]["decision"]["selected"] == "row_context"
    assert readings[0]["cells"][0]["header_cell_index"] == 0
    png = base64.b64decode(readings[0]["raster_png_base64"])
    assert hashlib.sha256(png).hexdigest() == readings[0]["raster_png_sha256"]
    assert all(value not in json.dumps(traces) for value in ("OV", "0V", "36V"))


@pytest.mark.parametrize("headers,raw", [(('Component', 'Code'), 'OV'), (('Min', 'Max'), 'OPA036'),
                                         (('Min', 'Max'), '0V'), (('Value', 'Code'), 'O')])
def test_no_numeric_role_or_no_ambiguity_performs_no_additional_ocr(headers, raw):
    source = table(raw, headers)
    selected, _, budget = recognize_grid_rows(*source, lambda patch: pytest.fail("No numeric retry"), .8, 13_000_000)
    assert all(a is b for a, b in zip(selected, source[2], strict=True))
    assert budget["additional_ocr_calls"] == 0


@pytest.mark.parametrize("raw_candidate", ["OV", "0A", "3V"])
def test_unresolved_or_inconsistent_candidate_keeps_baseline_and_ambiguity(raw_candidate):
    source, readings = table(), []
    selected, traces, budget = recognize_grid_rows(*source, lambda patch: candidate(raw_candidate), .8, 13_000_000,
                                                   private_numeric_readings=readings)
    assert selected[2] is source[2][2]
    assert budget["additional_ocr_calls"] == 1
    assert traces[1]["reason"] == "candidate_numeric_ambiguity_unresolved"
    assert source[3][2]["numeric_ambiguity_unresolved"] is True
    assert readings[0]["candidate_tokens"][0]["text"] == raw_candidate


def test_existing_density_retry_blocks_accumulation_of_another_attempt():
    source, readings = table(), []
    source[3][2]["crop"]["density_retry"]["attempted"] = True
    _, traces, budget = recognize_grid_rows(*source, lambda patch: pytest.fail("Second retry"), .8, 13_000_000,
                                            private_numeric_readings=readings)
    assert budget["additional_ocr_calls"] == 0
    assert traces[1]["reason"] == "mono_glyph_retry_already_attempted"
    assert source[3][2]["numeric_ambiguity_unresolved"] is True
    assert readings[0]["candidate_tokens"] is None


def test_exhausted_region_budget_preserves_ambiguity_without_allocating_ocr_input():
    source, readings = table(), []
    _, traces, budget = recognize_grid_rows(*source, lambda patch: pytest.fail("Budget exceeded"), .8, 100,
                                            private_numeric_readings=readings)
    assert budget["additional_ocr_calls"] == 0
    assert traces[1]["reason"] == "crop_pixel_limit"
    assert readings[0]["decision"]["attempted"] is False


def test_private_snapshot_cap_is_visible_without_claiming_image_was_retained(monkeypatch):
    monkeypatch.setattr(numeric_evidence, "SNAPSHOT_MAX_BYTES", 1)
    source, readings = table(), []
    selected, _, _ = recognize_grid_rows(*source, lambda patch: candidate(), .8, 13_000_000,
                                         private_numeric_readings=readings)
    assert selected[2]["text"].tolist() == ["0V"]
    assert readings[0]["raster_capture_state"] == "snapshot_byte_limit"
    assert "raster_png_base64" not in readings[0]


def test_density_experiment_is_explicit_bounded_and_has_inverse_geometry():
    source, readings = table(), []
    selected, traces, budget = recognize_grid_rows(*source, lambda patch: candidate(factor=2), .8, 13_000_000,
                                                   private_numeric_readings=readings, numeric_density_factor=2)
    assert selected[2]["text"].tolist() == ["0V"]
    assert selected[2]["left"].tolist() == [30]
    assert traces[1]["coordinate_inverse_factor"] == .5
    assert readings[0]["ocr_parameters"]["density_factor"] == 2
    assert budget["additional_ocr_calls"] == 1
    width, height = readings[0]["raster_size"]
    assert width <= 2048 and height <= 128


def test_density_derivative_budget_checked_before_resize(monkeypatch):
    source = table()

    def NoResizeDouble(*args, **kwargs):
        pytest.fail("Derivative must be refused before allocation")

    monkeypatch.setattr(Image.Image, "resize", NoResizeDouble)
    _, traces, budget = recognize_grid_rows(*source, lambda patch: pytest.fail("No OCR"), .8, 100_000,
                                            numeric_density_factor=2)
    assert budget["additional_ocr_calls"] == 0
    assert traces[1]["reason"] == "cumulative_pixel_limit"


@pytest.mark.parametrize("factor", [0, 3, True, 2.0])
def test_numeric_density_does_not_accept_unbounded_or_coerced_factors(factor):
    with pytest.raises(ValueError, match="facteur"):
        recognize_grid_rows(*table(), lambda patch: pytest.fail("No OCR"), .8, 13_000_000,
                            numeric_density_factor=factor)


def test_adapter_keeps_private_readings_and_publishes_ambiguity_location_without_text():
    region = {"l": 10, "t": 20, "r": 30, "b": 50, "coord_origin": "TOPLEFT"}
    document = {"pages": {"1": {"size": {"width": 100, "height": 200}}}}
    page = {"page_index": 0, "crop_box": [0, 0, 100, 200], "rotation": 0, "classification": "scan_candidate"}
    private = [{"cells": [{"raw_text": "OV"}], "candidate_tokens": None}]
    observed = {0: {"cell_count": 1, "numeric_readings": private,
                    "preprocessing": [{"cell_ocr": [{"numeric_unresolved_parser_bbox": region}]}]}}
    pages, warnings = document_to_pages(document, [page], "v", "r", "regional_ocr", observed)
    assert {"code": "OCR_NUMERIC_AMBIGUITY", "page_index": 0} in warnings
    assert pages[0]["ocr_numeric_readings"] == private
    assert pages[0]["unresolved_regions"][0] == {"bbox": [10, 150, 30, 180], "reason": "OCR_NUMERIC_AMBIGUITY", "precision": "block"}
    assert "OV" not in json.dumps(warnings)


def test_extraction_fingerprint_covers_the_new_numeric_policy(monkeypatch):
    from services.ingestion import config

    marker = ["a" * 64]
    seen = []

    def SourceDigestDouble(path):
        seen.append(path.name)
        return marker[0] if path.name == "numeric_evidence.py" else "0" * 64

    monkeypatch.setattr(config, "sha256_file", SourceDigestDouble)
    settings = config.IngestionConfig(artifacts_lock_path=None)
    first = settings.fingerprint()
    marker[0] = "b" * 64
    assert settings.fingerprint() != first
    assert "numeric_evidence.py" in seen
