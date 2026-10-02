"""Lecture des blocs par extraction_check (D02.5, D02.7, D02.10) sur des réponses réelles de l'API.

Les captures `evals/qualification-v2.1/runtime/2026-10-01-DA-P0x-published.json` (capture_bindings.py, 01/10/2026)
gardent, page par page, la réponse de GET /api/v1/versions/{id}/pages/{i}/blocks. La méthode d'extraction, l'OCR, le
tableau et la continuation y sont sous `block.metadata` (services/api/main.py, page_blocks) ; l'outil les lisait au
premier niveau du bloc, d'où des faux négatifs sur D02.5, D02.7 et D02.10 (J8, L6, 02/10/2026).
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import extraction_check  # noqa: E402
from corpus_data import records  # noqa: E402

CAPTURES = ROOT / "evals/qualification-v2.1/runtime"
DEV = {record.index: record for record in records("development")}


class Captured:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return copy.deepcopy(self.payload)


class CapturedApi:
    """Rejoue les réponses capturées de la route des blocs, sans instance."""

    def __init__(self, pages):
        self.pages, self.requested = pages, []

    def get(self, route):
        self.requested.append(route)
        return Captured(self.pages[int(route.split("/")[-2])])


def captured(index):
    snapshot = json.loads((CAPTURES / f"2026-10-01-DA-P{index:02d}-published.json").read_text(encoding="utf-8"))
    binding = snapshot["documents"][f"development-DA-P{index:02d}"]
    return binding["version_id"], binding["pages"]


def facts(index, pages=None):
    version_id, captured_pages = captured(index)
    api = CapturedApi(pages or captured_pages)
    result = extraction_check.page_facts(api, version_id, len(api.pages))
    assert api.requested == [f"/api/v1/versions/{version_id}/pages/{page}/blocks" for page in range(len(api.pages))]
    return result


@pytest.mark.parametrize("index", sorted(extraction_check.NATIVE_DEV))
def test_native_documents_read_method_and_table_rows_under_block_metadata(index):
    pages = facts(index)
    # D02.5 (voie native) et D02.10 (tableau natif exact) : les deux conditions de evaluate() sur la réponse réelle.
    assert all(block["method"] == "native" and not block["ocr_used"] for page in pages for block in page["blocks"])
    rows = {row for block in pages[1]["blocks"] for row in block["rows"]}
    assert sum(row in rows for row in DEV[index].rows) == 3
    assert set(extraction_check.summary(pages)[1]["methods"]) == {"native"}


def test_mixed_page_keeps_the_native_line_once_and_reports_the_scanned_table_as_ocr():
    pages = facts(3)
    mixed, native_line = pages[1], "Les valeurs de ce tableau concernent uniquement DA-P03."
    carriers = [block for block in mixed["blocks"] if native_line in block["text"]]
    # Condition D02.5_mixed_page_without_double_text de evaluate().
    assert extraction_check.page_text(mixed).count(native_line) == 1 and len(carriers) == 1
    assert carriers[0]["method"] == "native" and not carriers[0]["ocr_used"] and mixed["ocr_used"] and not pages[0]["ocr_used"]
    table = next(block for block in mixed["blocks"] if block["type"] == "table")
    assert table["method"] == "ocr" and table["ocr_used"] and table["rows"][0] == ("Référence", "Valeur", "Unité")


def test_scanned_document_blocks_are_reported_as_ocr():
    pages = facts(2)
    assert all(block["method"] == "ocr" and block["ocr_used"] for page in pages for block in page["blocks"])
    table = next(block for block in pages[1]["blocks"] if block["type"] == "table")
    assert ("DA-P02-IN", "14", "mm") in table["rows"]


def test_table_continuation_is_read_under_block_metadata():
    _, pages = captured(1)
    pages = copy.deepcopy(pages)
    table = next(block for block in pages[1]["blocks"] if block["type"] == "table")
    # Forme écrite par l'ingestion (block["metadata"]["continuation_of"]) et rendue telle quelle par l'API.
    table["metadata"]["continuation_of"] = "table-de-la-page-precedente"
    result = facts(1, pages)
    assert next(block for block in result[1]["blocks"] if block["type"] == "table")["continuation_of"] == "table-de-la-page-precedente"
    assert all(block["continuation_of"] is None for block in result[0]["blocks"])


@pytest.mark.parametrize("reason,bbox,accepted", [
    ("GRAPHIC_INTERPRETATION_UNAVAILABLE", [10, 10, 90, 90], False),
    ("OCR_WORD_LOW_CONFIDENCE", [110, 10, 150, 90], False),
    ("OCR_WORD_LOW_CONFIDENCE", None, False),
    ("OCR_WORD_LOW_CONFIDENCE", [20, 20, 40, 40], True),
    ("TABLE_CONTENT_COVERAGE_UNCERTAIN", [10, 10, 90, 90], True),
])
def test_scanned_table_missing_units_need_a_related_localized_warning(reason, bbox, accepted):
    page = {"blocks": [{"id": "table", "type": "table", "bbox": [10, 10, 90, 90],
                        "rows": [("IN", "15", ""), ("OUT", "11", "mm")]}],
            "unresolved_regions": [{"reason": reason, "bbox": bbox, "has_bbox": bbox is not None}]}
    result = extraction_check.scanned_table_evidence(page, (("IN", "15", "mm"), ("OUT", "11", "mm")))
    assert result["exact_rows"] == 1 and result["expected_rows"] == 2
    assert result["exact"] is False
    assert result["accepted"] is accepted


def test_scanned_table_exact_cells_do_not_require_an_unresolved_region():
    expected = (("IN", "15", "mm"), ("OUT", "11", "mm"))
    page = {"blocks": [{"id": "table", "type": "table", "bbox": [10, 10, 90, 90], "rows": list(expected)}],
            "unresolved_regions": []}
    result = extraction_check.scanned_table_evidence(page, expected)
    assert result["accepted"] and result["exact"] and result["exact_rows"] == 2
