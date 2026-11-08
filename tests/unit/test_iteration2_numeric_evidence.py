"""Numeric column role guards; OCR is an explicit named recognition double."""

import pandas as pd
import pytest
from test_ingestion_numeric_evidence import candidate, table

from services.ingestion.numeric_evidence import numeric_cell_contexts
from services.ingestion.regional_row_context import recognize_grid_rows


def test_explicit_nom_header_can_request_real_candidate_validation():
    source, readings, calls = table(headers=("NOM", "MAX")), [], []

    def RecognitionDouble(patch):
        calls.append(patch.size)
        return candidate()

    selected, _, budget = recognize_grid_rows(*source, RecognitionDouble, .8, 13_000_000,
                                            private_numeric_readings=readings)
    assert len(calls) == budget["additional_ocr_calls"] == 1
    assert readings[0]["cells"][0]["role"] == "nominal"
    assert readings[0]["cells"][0]["header_text"] == "NOM"
    assert readings[0]["cells"][0]["corroborating_header_cell_indices"] == [1]
    assert readings[0]["cells"][0]["raw_text"] == "OV"
    assert selected[2]["text"].tolist() == ["0V"]
    assert readings[0]["candidate_tokens"][0]["text"] == "0V"
    assert source[2][2]["text"].tolist() == ["OV"]


@pytest.mark.parametrize("confidence", [79.999, float("nan"), float("inf"), float("-inf")])
def test_unqualified_repeated_header_clears_the_previous_numeric_role(confidence):
    cells = [[0, row * 40, 100, row * 40 + 30] for row in range(3)]
    baselines = [pd.DataFrame([{"text": text, "conf": score}])
                 for text, score in [("MIN", 95), ("MAX", confidence), ("OV", 95)]]
    assert numeric_cell_contexts(cells, baselines, [[0], [1], [2]], .8) == {}


def test_a_qualified_repeated_header_updates_the_role_and_its_source_location():
    cells = [[0, row * 40, 100, row * 40 + 30] for row in range(3)]
    baselines = [pd.DataFrame([{"text": text, "conf": 95}]) for text in ["MIN", "Nominal", "OV"]]
    contexts = numeric_cell_contexts(cells, baselines, [[0], [1], [2]], .8)
    assert contexts[2]["role"] == "nominal"
    assert contexts[2]["header_cell_index"] == 1
    assert contexts[2]["header_raster_bbox"] == cells[1]


@pytest.mark.parametrize("label", ["Nom", "NOM"])
def test_nom_without_a_numeric_neighbor_does_not_reinterpret_a_name_column(label):
    source = table(headers=(label, "Code"))
    selected, _, budget = recognize_grid_rows(*source, lambda patch: pytest.fail("No numeric role is established"), .8, 13_000_000)
    assert budget["additional_ocr_calls"] == 0
    assert selected[2] is source[2][2] and selected[2]["text"].tolist() == ["OV"]
