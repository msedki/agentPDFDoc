"""OCR provenance and bounded agreement; recognition callbacks are explicit doubles."""

import copy
import hashlib

import pandas as pd
import pytest
from PIL import Image


def token(text, box=(10, 10, 55, 24), confidence=.95):
    return {"text": text, "bbox": list(box), "confidence": confidence}


def reading(*, text="3.8", candidate="3.8", candidate_box=None, confidence=.95):
    return {"policy": "ocr-geometric-agreement-v1", "reading_id": "ocr-0",
            "baseline_tokens": [token(text, confidence=confidence)],
            "candidate_tokens": [token(candidate, candidate_box or (10, 10, 55, 24))],
            "state": "corroborated", "reason": "agreement", "minimum_confidence": .8,
            "source_raster_sha256": "a" * 64, "candidate_raster_sha256": "b" * 64,
            "parameters": {"psm": 6, "factor": 2}, "coordinate_frame": "pdf_user_space_unrotated"}


def annotated(text="3.8", candidate="3.8"):
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality

    records = [reading(text=text, candidate=candidate)]
    cells = annotate_ocr_cells([{**token(text), "from_ocr": True}], records)
    return block_quality(text, cells, records, "c" * 64, 2)


def test_old_adapter_does_not_treat_a_high_confidence_disagreement_as_supported():
    from services.ingestion.docling_adapter import document_to_pages

    page = {"page_index": 0, "classification": "scan_candidate", "width": 100, "height": 100,
            "crop_box": [0, 0, 100, 100], "effective_box": [0, 0, 100, 100], "rotation": 0,
            "source_sha256": "c" * 64}
    box = {"l": 10, "t": 10, "r": 55, "b": 24, "coord_origin": "TOPLEFT"}
    doc = {"pages": {"1": {"size": {"width": 100, "height": 100}}},
           "texts": [{"self_ref": "#/texts/0", "label": "text", "text": "3.8",
                      "prov": [{"page_no": 1, "bbox": box}]}]}
    evidence = reading(candidate="8.8")
    evidence["coordinate_frame"] = "parser_top_left"
    for item in evidence["baseline_tokens"] + evidence["candidate_tokens"]:
        item["bbox"] = box
    pages, _ = document_to_pages(doc, [page], "version", "revision", "regional_ocr", {
        0: {"cell_count": 1, "cells": [{"text": "3.8", "bbox": box, "from_ocr": True, "confidence": .95}],
            "quality_readings": [evidence]}}, .8)
    quality = pages[0]["blocks"][0]["metadata"].get("ocr_quality")
    assert quality is not None, "OCR words currently carry no checked second-reading evidence"
    assert quality["state"] != "corroborated"


def test_agreement_requires_same_literal_same_geometry_and_real_confidences():
    from services.ingestion.source_quality import assess_reading

    assert assess_reading(reading())["state"] == "corroborated"
    assert assess_reading(reading(candidate="8.8"))["state"] == "uncertain"
    assert assess_reading(reading(candidate_box=(75, 10, 99, 24)))["state"] == "uncertain"
    assert assess_reading(reading(confidence=.4))["state"] == "uncertain"
    invalid = reading()
    invalid["candidate_tokens"][0]["confidence"] = float("nan")
    assert assess_reading(invalid)["state"] == "uncertain"


def test_declared_state_never_overrides_the_two_actual_readings():
    from services.ingestion.source_quality import assess_reading

    false_certificate = reading(candidate="8.8")
    false_certificate["state"] = "corroborated"
    false_certificate["verified"] = True
    assert assess_reading(false_certificate)["state"] == "uncertain"


@pytest.mark.parametrize("raw,other", [("+4", "±4"), ("14µW", "14HW"), ("7mV", "7V"),
                                      ("0.8", "O.8"), ("V+", "V*"), ("COUT", "Cour")])
def test_sign_unit_signal_and_digit_disagreements_remain_literal(raw, other):
    from services.ingestion.source_quality import assess_reading

    result = assess_reading(reading(text=raw, candidate=other))
    assert result["state"] == "uncertain"
    assert result["tokens"][0]["text"] == raw


def test_source_identity_and_payload_are_rechecked_before_publication():
    from services.ingestion.source_quality import verified_source_quality

    quality = annotated()
    metadata = {"extraction_method": "ocr", "ocr_quality": quality}
    assert verified_source_quality("3.8", metadata, "c" * 64, 2)["state"] == "corroborated"
    assert verified_source_quality("3.8", metadata, "d" * 64, 2)["state"] == "unavailable"
    assert verified_source_quality("3.8", metadata, "c" * 64, 3)["state"] == "unavailable"
    changed = copy.deepcopy(metadata)
    changed["ocr_quality"]["readings"][0]["candidate_tokens"][0]["text"] = "8.8"
    assert verified_source_quality("3.8", changed, "c" * 64, 2)["state"] == "unavailable"


def test_legacy_ocr_requires_revalidation_but_native_stays_available():
    from services.ingestion.source_quality import verified_source_quality

    assert verified_source_quality("3.8", {"extraction_method": "ocr"}, "c" * 64, 2)["state"] == "unavailable"
    assert verified_source_quality("3.8", {"extraction_method": "native"}, "c" * 64, 2)["state"] == "native"


def test_uncertainty_is_local_to_the_affected_interval():
    from services.ingestion.source_quality import (
        annotate_ocr_cells,
        block_quality,
        span_quality,
        verified_source_quality,
    )

    records = [reading()]
    bad = reading(text="9.1", candidate="8.1")
    bad["reading_id"] = "ocr-1"
    for item in bad["baseline_tokens"] + bad["candidate_tokens"]:
        item["bbox"] = [65, 10, 95, 24]
    records.append(bad)
    cells = [{**token("3.8"), "from_ocr": True}, {**token("9.1", (65, 10, 95, 24)), "from_ocr": True}]
    quality = block_quality("3.8 9.1", annotate_ocr_cells(cells, records), records, "c" * 64, 2)
    verified = verified_source_quality("3.8 9.1", {"extraction_method": "ocr", "ocr_quality": quality}, "c" * 64, 2)
    assert span_quality(verified, 0, 3)["state"] == "corroborated"
    assert span_quality(verified, 4, 7)["state"] == "uncertain"
    assert span_quality(verified, 0, 7)["state"] == "uncertain"


def test_missing_or_repeated_word_mapping_is_never_guessed():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality, span_quality

    records = [reading()]
    cells = annotate_ocr_cells([{**token("3.8"), "from_ocr": True}], records)
    quality = block_quality("3.8 3.8", cells, records, "c" * 64, 2)
    assert span_quality(quality, 0, 7)["state"] != "corroborated"


def test_parser_geometry_uses_actual_rotation_and_cropbox():
    from services.ingestion.source_quality import canonical_quality_readings

    record = reading()
    record["coordinate_frame"] = "parser_top_left"
    for item in record["baseline_tokens"] + record["candidate_tokens"]:
        item["bbox"] = {"l": 10, "t": 10, "r": 55, "b": 24, "coord_origin": "TOPLEFT"}
    page = {"effective_box": [20, 30, 120, 230], "crop_box": [20, 30, 120, 230], "rotation": 90}
    converted = canonical_quality_readings([record], (200, 100), page)
    assert converted[0]["baseline_tokens"][0]["bbox"] == [30.0, 40.0, 44.0, 85.0]
    assert record["baseline_tokens"][0]["bbox"]["coord_origin"] == "TOPLEFT"


def frame(text="3.8", x=20, y=20):
    return pd.DataFrame([{"text": text, "left": x, "top": y, "width": 30, "height": 12, "conf": 95}])


def test_retry_budget_is_checked_before_any_recognition_and_keeps_original():
    from services.ingestion.ocr_verification import verify_ocr_lines

    raster = Image.new("RGB", (200, 80), "white")
    before = hashlib.sha256(raster.tobytes()).hexdigest()
    baseline = frame()
    records, budget = verify_ocr_lines(raster, baseline, lambda _: pytest.fail("No allocation/recognition at exhausted cap"),
                                     .8, 100, used_calls=32, used_pixels=100)
    assert records and all(record["state"] != "corroborated" for record in records)
    assert budget["additional_ocr_calls"] == 32
    assert baseline["text"].tolist() == ["3.8"]
    assert hashlib.sha256(raster.tobytes()).hexdigest() == before


def test_retry_failure_is_evidence_not_a_changed_reading():
    from services.ingestion.ocr_verification import verify_ocr_lines

    def RecognitionDouble(_):
        raise TimeoutError("deliberate recognition double")

    records, budget = verify_ocr_lines(Image.new("RGB", (200, 80), "white"), frame(), RecognitionDouble, .8, 13000000)
    assert budget["additional_ocr_calls"] == 1
    assert records[0]["state"] == "unavailable"
    assert records[0]["baseline_tokens"][0]["text"] == "3.8"
    assert "deliberate" not in str(records)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_inverse_parser_geometry_roundtrips_without_inventing_a_frame(rotation):
    from services.ingestion.geometry import docling_box_to_pdf, pdf_box_to_docling

    page = {"effective_box": [20, 30, 120, 230], "crop_box": None, "rotation": rotation}
    size = (200, 100) if rotation in {90, 270} else (100, 200)
    original = [30, 45, 60, 85]
    converted = pdf_box_to_docling(original, size, page)
    assert docling_box_to_pdf(converted, size, page) == original


def test_leading_plus_requires_an_observed_cross_and_no_extra_lower_bar():
    from PIL import ImageDraw

    from services.ingestion.ocr_verification import plus_shape
    from services.ingestion.source_quality import SIGN_POLICY, assess_reading

    raster = Image.new("RGB", (80, 60), "white")
    draw = ImageDraw.Draw(raster)
    draw.rectangle((10, 16, 22, 18), fill="black")
    draw.rectangle((15, 10, 17, 24), fill="black")
    plus = token("+4", (10, 10, 45, 25))
    assert plus_shape(raster, plus) == "cross_only"
    check = reading(text="+4", candidate="+4")
    assert assess_reading(check)["state"] == "uncertain"
    check["baseline_tokens"][0]["visual_sign_check"] = "cross_only"
    assert assess_reading(check)["state"] == "uncertain"  # old shape policy is not promoted
    check["baseline_tokens"][0]["visual_sign_policy"] = SIGN_POLICY
    assert assess_reading(check)["state"] == "corroborated"
    draw.rectangle((10, 28, 22, 30), fill="black")
    assert plus_shape(raster, plus) == "additional_lower_bar"
    check["baseline_tokens"][0]["visual_sign_check"] = "additional_lower_bar"
    assert assess_reading(check)["state"] == "uncertain"


@pytest.mark.parametrize("joined", [False, True])
@pytest.mark.parametrize("bar_height", [2, 4, 6])
def test_lower_sign_bar_is_detected_even_when_thick_or_joined_to_the_cross(joined, bar_height):
    from PIL import ImageDraw

    from services.ingestion.ocr_verification import plus_shape

    raster = Image.new("RGB", (100, 80), "white")
    draw = ImageDraw.Draw(raster)
    draw.rectangle((10, 16, 24, 19), fill="black")
    draw.rectangle((16, 10, 18, 26 if joined else 23), fill="black")
    draw.rectangle((10, 26, 24, 25 + bar_height), fill="black")
    assert plus_shape(raster, token("+8", (10, 10, 52, 32))) == "additional_lower_bar"


def test_a_cross_without_space_to_observe_a_lower_bar_is_inconclusive():
    from PIL import ImageDraw

    from services.ingestion.ocr_verification import plus_shape

    raster = Image.new("RGB", (80, 26), "white")
    draw = ImageDraw.Draw(raster)
    draw.rectangle((10, 16, 22, 18), fill="black")
    draw.rectangle((15, 10, 17, 24), fill="black")
    assert plus_shape(raster, token("+4", (10, 10, 45, 25))) == "inconclusive_sign_shape"


def test_whole_word_mapping_does_not_confuse_a_word_and_a_substring():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality

    words = ['for', 'or', 'a', 'data']
    records, cells = [], []
    for index, word in enumerate(words):
        record = reading(text=word, candidate=word)
        record['reading_id'] = f'ocr-{index}'
        box = [index * 60 + 10, 10, index * 60 + 55, 24]
        for item in record['baseline_tokens'] + record['candidate_tokens']:
            item['bbox'] = box
        records.append(record)
        cells.append({**token(word, box), 'from_ocr': True})
    result = block_quality('for or a data', annotate_ocr_cells(cells, records), records, 'c' * 64, 2)
    assert result['state'] == 'corroborated'


def test_an_observed_digit_cannot_qualify_part_of_a_different_number():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality, span_quality

    records = [reading(text='5', candidate='5')]
    cells = annotate_ocr_cells([{**token('5'), 'from_ocr': True}], records)
    result = block_quality('15', cells, records, 'c' * 64, 2)
    assert span_quality(result, 1, 2)['state'] == 'unavailable'


@pytest.mark.parametrize('extra', ['not', '±', 'only'])
def test_extra_candidate_qualification_prevents_one_sided_agreement(extra):
    from services.ingestion.source_quality import assess_reading

    record = reading(text='permitted', candidate='permitted')
    record['candidate_tokens'].append(token(extra, (1, 10, 8, 24)))
    result = assess_reading(record)
    assert result['state'] == 'uncertain'
    assert 'candidate_has_unmatched_tokens' in result['tokens'][0]['reasons']


def test_a_candidate_word_cannot_verify_two_overlapping_baseline_words():
    from services.ingestion.source_quality import assess_reading

    record = reading()
    record['baseline_tokens'].append(copy.deepcopy(record['baseline_tokens'][0]))
    result = assess_reading(record)
    assert result['state'] == 'uncertain'
    assert all('nonunique_reading_pairing' in word['reasons'] for word in result['tokens'])


def test_overlapping_regions_with_different_readings_remain_a_local_conflict():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality, verified_source_quality

    first = reading(text='4.8', candidate='4.8')
    other = reading(text='8.8', candidate='8.8')
    other['reading_id'] = 'ocr-1'
    cells = annotate_ocr_cells([{**token('4.8'), 'from_ocr': True}], [first, other])
    assert cells[0]['ocr_quality']['state'] == 'uncertain'
    assert cells[0]['ocr_quality']['reading_ids'] == ['ocr-0', 'ocr-1']
    witness = block_quality('4.8', cells, [first, other], 'c' * 64, 2)
    result = verified_source_quality('4.8', {'extraction_method': 'ocr', 'ocr_quality': witness}, 'c' * 64, 2)
    assert result['state'] == 'uncertain'
    assert 'overlapping_readings_disagree' in result['reasons']


def test_punctuation_bearing_observations_do_not_hide_the_unpunctuated_word():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality

    first = reading(text='V', candidate='V')
    second = reading(text='V,', candidate='V,')
    second['reading_id'] = 'ocr-1'
    for item in second['baseline_tokens'] + second['candidate_tokens']:
        item['bbox'] = [65, 10, 95, 24]
    cells = [{**token('V'), 'from_ocr': True}, {**token('V,', (65, 10, 95, 24)), 'from_ocr': True}]
    witness = block_quality('V V,', annotate_ocr_cells(cells, [first, second]), [first, second], 'c' * 64, 2)
    assert witness['state'] == 'corroborated'


def test_overlapping_inconsistent_token_counts_cannot_be_silently_discarded():
    from services.ingestion.source_quality import block_quality

    cells = [{**token('V,'), 'from_ocr': False}, {**token('V'), 'from_ocr': False}]
    witness = block_quality('V,', cells, [], 'c' * 64, 2)
    assert witness['state'] == 'uncertain'
    assert 'ambiguous_observed_tokenization' in witness['reasons']


def test_exact_geometric_sequence_localizes_repeated_word_uncertainty():
    from services.ingestion.source_quality import (
        annotate_ocr_cells,
        block_quality,
        span_quality,
        verified_source_quality,
    )

    records = [reading(text='power', candidate='power'), reading(text='power', candidate='tower')]
    records[1]['reading_id'] = 'ocr-1'
    for item in records[1]['baseline_tokens'] + records[1]['candidate_tokens']:
        item['bbox'] = [65, 10, 95, 24]
    cells = [{**token('power'), 'from_ocr': True}, {**token('power', (65, 10, 95, 24)), 'from_ocr': True}]
    page = {'page_index': 2, 'crop_box': [0, 0, 100, 100], 'effective_box': [0, 0, 100, 100], 'rotation': 0}
    witness = block_quality('power power', annotate_ocr_cells(cells, records), records, 'c' * 64, 2, page=page)
    quality = verified_source_quality('power power', {'extraction_method': 'ocr', 'ocr_quality': witness}, 'c' * 64, 2, page=page)
    assert span_quality(quality, 0, 5)['state'] == 'corroborated'
    assert span_quality(quality, 6, 11)['state'] == 'uncertain'
    assert verified_source_quality('power power', {'extraction_method': 'ocr', 'ocr_quality': witness}, 'c' * 64, 2)['state'] == 'unavailable'
    altered_page = {**page, 'rotation': 180}
    assert verified_source_quality('power power', {'extraction_method': 'ocr', 'ocr_quality': witness}, 'c' * 64, 2, page=altered_page)['state'] == 'unavailable'


def test_unproved_geometric_order_does_not_borrow_a_repeated_word_proof():
    from services.ingestion.source_quality import annotate_ocr_cells, block_quality, span_quality

    first, second = reading(text='power', candidate='power'), reading(text='power', candidate='tower')
    second['reading_id'] = 'ocr-1'
    for item in second['baseline_tokens'] + second['candidate_tokens']:
        item['bbox'] = [60, 10, 95, 24]
    cells = [{**token('power'), 'from_ocr': True}, {**token('power', (60, 10, 95, 24)), 'from_ocr': True}]
    # An unobserved intervening word prevents complete sequence equality.
    page = {'page_index': 2, 'crop_box': [0, 0, 100, 100], 'rotation': 0}
    witness = block_quality('power missing power', annotate_ocr_cells(cells, [first, second]), [first, second], 'c' * 64, 2, page=page)
    assert span_quality(witness, 0, 5)['state'] != 'corroborated'


def test_two_column_ambiguity_cannot_locate_a_repeated_word():
    from services.ingestion.source_quality import _ordered_intervals

    cells = [token('voltage', (5, 70, 35, 80)), token('power', (150, 70, 180, 80)),
             token('power', (5, 50, 35, 60)), token('current', (150, 50, 180, 60))]
    page = {'page_index': 0, 'crop_box': [0, 0, 200, 100], 'rotation': 0}
    assert _ordered_intervals('voltage power power current', cells, page) is None


def test_tiny_duplicate_boxes_cannot_prove_two_distinct_occurrences():
    from services.ingestion.source_quality import _ordered_intervals

    cells = [token('x', (5, 5, 5.3, 6)), token('x', (5, 5, 5.3, 6))]
    page = {'page_index': 0, 'crop_box': [0, 0, 20, 20], 'rotation': 0}
    assert _ordered_intervals('x x', cells, page) is None
