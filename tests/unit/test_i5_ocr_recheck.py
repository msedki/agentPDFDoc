"""Named OCR doubles test a bounded recheck, not recognition accuracy."""

import copy

import pandas as pd
import pytest
from PIL import Image

from services.ingestion.ocr_verification import verify_ocr_lines
from services.ingestion.source_quality import (
    UNSCALED_RECHECK_POLICY,
    assess_reading,
    canonical_quality_readings,
)


def frame(text, confidence, box):
    left, top, width, height = box
    return pd.DataFrame([{"text": text, "conf": confidence, "left": left, "top": top,
                          "width": width, "height": height}])


def observed_recheck(*, first_text="24", first_confidence=60, second_text="24",
                     baseline_confidence=95, used_calls=0, pixel_limit=13_000_000,
                     second_error=False):
    calls = []

    def recognize(image):
        calls.append(image.size)
        if len(calls) == 1:
            return frame(first_text, first_confidence, (26, 26, 90, 28))
        if second_error:
            raise TimeoutError("named OCR recheck double")
        return frame(second_text, 95, (13, 13, 45, 14))

    with Image.new("RGB", (120, 60), "white") as image:
        records, budget = verify_ocr_lines(image, frame("24", baseline_confidence, (10, 10, 45, 14)),
                                          recognize, .8, pixel_limit, used_calls=used_calls)
    return records[0], budget, calls


def test_only_the_score_is_rechecked_and_both_literal_observations_remain_available():
    record, budget, calls = observed_recheck()
    assert calls == [(142, 80), (71, 40)]
    assert budget["verification_calls"] == 2 and budget["verification_recheck_calls"] == 1
    assert budget["additional_ocr_call_limit"] == 32 and budget["pixel_limit"] == 13_000_000
    assert budget["verification_pixels"] == 19_080
    assert record["state"] == assess_reading(record)["state"] == "corroborated"
    assert record["minimum_confidence"] == .8
    assert record["parameters"]["factor"] == 1 and record["candidate_raster_size"] == [71, 40]
    prior = record["prior_candidate"]
    assert prior["parameters"]["factor"] == 2 and prior["candidate_raster_size"] == [142, 80]
    assert prior["candidate_tokens"][0]["confidence"] == .6
    assert record["candidate_tokens"][0]["confidence"] == .95
    assert record["candidate_tokens"][0]["text"] == prior["candidate_tokens"][0]["text"] == "24"
    assert record["unscaled_recheck"] == {"policy": UNSCALED_RECHECK_POLICY, "status": "completed"}


@pytest.mark.parametrize("kwargs", [
    {"first_text": "28"}, {"first_text": "24 only"}, {"baseline_confidence": 60},
    {"first_confidence": float("nan")}, {"first_confidence": 150}, {"first_confidence": 95},
])
def test_a_disagreement_invalid_score_or_already_good_reading_is_not_retried(kwargs):
    record, budget, calls = observed_recheck(**kwargs)
    assert len(calls) == 1 and budget["verification_recheck_calls"] == 0
    assert "prior_candidate" not in record and "unscaled_recheck" not in record
    expected = {"corroborated"} if kwargs == {"first_confidence": 95} else {"uncertain", "unavailable"}
    assert assess_reading(record)["state"] in expected


@pytest.mark.parametrize("kwargs,reason", [({"used_calls": 31}, "shared_retry_call_limit"),
                                         ({"pixel_limit": 19_079}, "shared_retry_pixel_limit")])
def test_recheck_cannot_exceed_the_existing_shared_budget(kwargs, reason):
    record, budget, calls = observed_recheck(**kwargs)
    assert len(calls) == 1 and budget["verification_recheck_calls"] == 0
    assert record["unscaled_recheck"]["status"] == "skipped" and record["unscaled_recheck"]["reason"] == reason
    assert assess_reading(record)["state"] == "uncertain"
    assert budget["additional_ocr_calls"] <= 32 and budget["cumulative_crop_pixels"] <= budget["pixel_limit"]


def test_new_disagreement_is_kept_and_never_substitutes_the_original():
    record, _, calls = observed_recheck(second_text="28")
    assert len(calls) == 2 and record["baseline_tokens"][0]["text"] == "24"
    assert record["prior_candidate"]["candidate_tokens"][0]["text"] == "24"
    assert record["candidate_tokens"][0]["text"] == "28"
    assert assess_reading(record)["state"] == "uncertain"


def test_a_failed_recheck_keeps_the_original_low_score_and_cannot_qualify_it():
    record, budget, calls = observed_recheck(second_error=True)
    assert len(calls) == 2 and budget["verification_recheck_calls"] == 1
    assert record["unscaled_recheck"]["status"] == "failed"
    assert "prior_candidate" not in record and record["candidate_tokens"][0]["confidence"] == .6
    assert assess_reading(record)["state"] == "uncertain"


@pytest.mark.parametrize("tamper", ["disagreement", "score", "parameters", "policy", "missing-prior", "raster-size", "same-raster"])
def test_the_first_reading_cannot_be_removed_or_misrepresented_to_approve_the_second(tamper):
    record, _, _ = observed_recheck()
    if tamper == "disagreement":
        record["prior_candidate"]["candidate_tokens"][0]["text"] = "28"
    elif tamper == "score":
        record["prior_candidate"]["candidate_tokens"][0]["confidence"] = float("nan")
    elif tamper == "parameters":
        record["prior_candidate"]["parameters"] = ["invalid"]
    elif tamper == "policy":
        record["unscaled_recheck"]["policy"] = "uncontrolled-retry"
    elif tamper == "missing-prior":
        del record["prior_candidate"]
    elif tamper == "raster-size":
        record["candidate_raster_size"][0] += 1
    else:
        record["candidate_raster_sha256"] = record["prior_candidate"]["candidate_raster_sha256"]
    assert assess_reading(record)["state"] == "unavailable"


def test_all_three_token_sets_are_converted_to_the_same_physical_page_frame():
    record, _, _ = observed_recheck()
    record = copy.deepcopy(record)
    record.update(reading_id="line-0", coordinate_frame="parser_top_left")
    collections = (record["baseline_tokens"], record["candidate_tokens"], record["prior_candidate"]["candidate_tokens"])
    for tokens in collections:
        for token in tokens:
            left, top, right, bottom = token["bbox"]
            token["bbox"] = {"l": left, "t": top, "r": right, "b": bottom, "coord_origin": "TOPLEFT"}
    page = {"effective_box": [0, 0, 120, 60], "crop_box": [0, 0, 120, 60], "rotation": 0}
    result = canonical_quality_readings([record], (120, 60), page)
    assert len(result) == 1 and assess_reading(result[0])["state"] == "corroborated"
    assert result[0]["baseline_tokens"][0]["bbox"] == result[0]["candidate_tokens"][0]["bbox"] == [10., 36., 55., 50.]
    assert result[0]["prior_candidate"]["candidate_tokens"][0]["bbox"] == [10., 36., 55., 50.]
