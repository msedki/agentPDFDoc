"""Isolation par page, document sans texte et seuil OCR, avec doubles de session Docling.

Aucun Docling, OCR ni modèle n'est chargé : ces tests ne prouvent pas le parseur réel.
"""

import hashlib
import json
from pathlib import Path

import pytest

from services.ingestion import pipeline
from services.ingestion.config import IngestionConfig, sha256_file
from services.ingestion.errors import IngestionError
from services.ingestion.pipeline import _extract_window, extract_pdf

ROOT = Path(__file__).resolve().parents[2]
TEXT_BOX = {"l": 10, "b": 100, "r": 290, "t": 150, "coord_origin": "BOTTOMLEFT"}


def preflight_page(index, route="structured", width=600, height=800):
    page = {"page_index": index, "page_number": index + 1, "label": None, "effective_box": [0, 0, width, height],
            "crop_box": [0, 0, width, height], "rotation": 0, "display_width": width, "display_height": height,
            "native_text_regions": [], "text_font_sizes": [10], "image_regions": [], "text_mapping_warnings": [],
            "alphanumeric_count": 20, "native_text_sparse": False}
    if route == "structured":
        page.update(classification="native", needs_ocr=False, vector_path_count=8)
    elif route == "regional_ocr":
        page.update(classification="scan_candidate", needs_ocr=True, vector_path_count=0, native_text_sparse=True,
                    image_regions=[{"bbox": [0, 0, width, height], "area_ratio": 1.0}])
    else:
        page.update(classification="blank", needs_ocr=False, vector_path_count=0, alphanumeric_count=0)
    return page


class SessionDouble:
    """Double of DoclingSession: any page range containing a failing page raises."""

    def __init__(self, failing=(), code="DOCLING_CONVERSION_FAILED", ocr_cells=None, details=None):
        self.failing, self.code, self.ocr_cells = set(failing), code, ocr_cells or {}
        # Statut Docling FAILURE par défaut ; exception_type = exception levée hors du statut Docling.
        self.details = details or {"parser_status": "failure"}
        self.calls, self.page_metadata, self.last_lifecycle = [], {}, {}

    def convert(self, path, first, last, route):
        self.calls.append((first, last, route))
        if self.failing & set(range(first, last + 1)):
            raise IngestionError(self.code, "Échec simulé du parseur.", {"page_start": first, "page_end": last, **self.details})
        texts = []
        for index in range(first, last + 1):
            text = f"Page {index} : tension 24 V"
            texts.append({"self_ref": f"#/texts/{index}", "label": "text", "text": text, "orig": text,
                          "prov": [{"page_no": index + 1, "charspan": [0, len(text)], "bbox": TEXT_BOX}]})
        document = {"texts": texts, "pages": {str(index + 1): {"size": {"width": 600, "height": 800}} for index in range(first, last + 1)}}
        observed = {index: {"cell_count": len(cells), "cells": cells} for index, cells in self.ocr_cells.items() if first <= index <= last}
        return document, True, observed


def window(tmp_path, pages, session, settings=None):
    preflight = {"sha256": "0" * 64, "page_count": len(pages), "pages": pages}
    return _extract_window(tmp_path / "source.pdf", "version", 0, len(pages) - 1, settings or IngestionConfig(),
                           tmp_path / "out", preflight, session, None, fingerprint="fingerprint", revision_id="revision")


def test_render_limit_isolates_one_page_and_never_spans_it(tmp_path):
    pages = [preflight_page(0), preflight_page(1, width=4000, height=4000), preflight_page(2)]
    session = SessionDouble()
    result = window(tmp_path, pages, session)
    assert session.calls == [(0, 0, "structured"), (2, 2, "structured")]
    states = [page["extraction_state"] for page in result["pages"]]
    assert states == ["native", "error", "native"]
    assert [page["blocks"][0]["raw_text"] for page in (result["pages"][0], result["pages"][2])] == ["Page 0 : tension 24 V", "Page 2 : tension 24 V"]
    failed = result["pages"][1]
    assert failed["unresolved_regions"] == [{"bbox": None, "reason": "PDF_RENDER_LIMIT", "precision": "page"}]
    assert failed["blocks"] == [] and failed["extraction_route"] == "structured"
    warning = next(item for item in result["warnings"] if item["code"] == "PDF_RENDER_LIMIT")
    assert warning["page_index"] == 1 and warning["render_pixels"] > warning["pixel_limit"]
    assert result["complete"] is False


def test_conversion_failure_is_retried_by_page_and_isolated(tmp_path):
    pages = [preflight_page(index) for index in range(3)]
    session = SessionDouble(failing={1})
    result = window(tmp_path, pages, session)
    assert session.calls == [(0, 2, "structured"), (0, 0, "structured"), (1, 1, "structured"), (2, 2, "structured")]
    assert [page["page_index"] for page in result["pages"]] == [0, 1, 2]
    assert [page["extraction_state"] for page in result["pages"]] == ["native", "error", "native"]
    assert result["pages"][1]["unresolved_regions"][0]["reason"] == "DOCLING_CONVERSION_FAILED"
    codes = [(item["code"], item.get("page_index")) for item in result["warnings"]]
    assert ("PAGE_GROUP_RETRIED_BY_PAGE", None) in codes and ("DOCLING_CONVERSION_FAILED", 1) in codes
    assert not result["complete"]


@pytest.mark.parametrize("code", ["INGESTION_NATIVE_FAULT", "DOCLING_THREADS_STILL_ACTIVE", "DOCLING_ARTIFACTS_MISSING"])
def test_environment_and_native_faults_still_fail_the_extraction(tmp_path, code):
    with pytest.raises(IngestionError) as caught:
        window(tmp_path, [preflight_page(0), preflight_page(1)], SessionDouble(failing={1}, code=code))
    assert caught.value.code == code


def test_parser_exception_outside_docling_status_is_not_page_local(tmp_path):
    # Initialisation du pipeline (poids absents ou corrompus, Torch) : aucune page n'en est la cause.
    session = SessionDouble(failing={1}, details={"exception_type": "RuntimeError"})
    with pytest.raises(IngestionError) as caught:
        window(tmp_path, [preflight_page(index) for index in range(3)], session)
    assert caught.value.code == "DOCLING_CONVERSION_FAILED" and caught.value.details["exception_type"] == "RuntimeError"
    assert session.calls == [(0, 2, "structured")]


def isolated_extract(tmp_path, monkeypatch, pages, session, config=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\n% double de test, jamais ouvert par un parseur\n")
    monkeypatch.setattr(pipeline, "preflight_pdf", lambda path, settings: {"sha256": sha256_file(path), "page_count": len(pages), "size_bytes": 0, "pages": pages})
    monkeypatch.setattr(pipeline, "DoclingSession", lambda settings: session)
    return extract_pdf(source, tmp_path / "out", config or {}, "version")


def test_page_local_failure_publishes_other_pages_as_ready_partial(tmp_path, monkeypatch):
    pages = [preflight_page(0), preflight_page(1, width=4000, height=4000), preflight_page(2)]
    result = isolated_extract(tmp_path, monkeypatch, pages, SessionDouble())
    assert result["status"] == "ready_partial"
    assert result["coverage"]["processed"] == 3 and result["coverage"]["unresolved"] == 1
    assert sum(bool(page["blocks"]) for page in result["pages"]) == 2
    assert not any(item["code"] == "DOCUMENT_WITHOUT_TEXT" for item in result["warnings"])
    # Plafond de rendu : déterministe pour une même empreinte, la fenêtre reste réutilisable.
    assert (tmp_path / "out" / "window-000000-000002.json").is_file()


def test_all_pages_failing_conversion_are_not_published_and_a_retry_reconverts(tmp_path, monkeypatch):
    pages = [preflight_page(index) for index in range(3)]
    with pytest.raises(IngestionError) as caught:
        isolated_extract(tmp_path, monkeypatch, pages, SessionDouble(failing={0, 1, 2}))
    assert caught.value.code == "DOCLING_CONVERSION_FAILED"
    assert caught.value.details["failed_pages"] == [0, 1, 2] and caught.value.details["parser_status"] == "failure"
    output = tmp_path / "out"
    assert not (output / "extraction.json").exists()
    healthy = SessionDouble()
    result = isolated_extract(tmp_path, monkeypatch, pages, healthy)
    assert healthy.calls == [(0, 2, "structured")]
    assert result["status"] == "ready" and result["windows"][0]["reused"] is False


def test_conversion_failure_window_is_written_but_reconverted_on_resume(tmp_path, monkeypatch):
    pages = [preflight_page(index) for index in range(3)]
    first = isolated_extract(tmp_path, monkeypatch, pages, SessionDouble(failing={1}))
    assert first["status"] == "ready_partial" and [page["extraction_state"] for page in first["pages"]] == ["native", "error", "native"]
    # Écrite pour signaler la progression au watchdog de l'API, jamais réutilisée.
    assert (tmp_path / "out" / "window-000000-000002.json").is_file()
    healthy = SessionDouble()
    second = isolated_extract(tmp_path, monkeypatch, pages, healthy)
    assert healthy.calls == [(0, 2, "structured")]
    assert second["status"] == "ready" and second["windows"][0]["reused"] is False
    third = SessionDouble()
    assert isolated_extract(tmp_path, monkeypatch, pages, third)["windows"][0]["reused"] is True and third.calls == []


def test_public_window_without_any_conversion_is_not_published(tmp_path, monkeypatch):
    pages = [preflight_page(0), preflight_page(1)]
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\n% double de test, jamais ouvert par un parseur\n")
    monkeypatch.setattr(pipeline, "preflight_pdf", lambda path, settings: {"sha256": sha256_file(path), "page_count": 2, "size_bytes": 0, "pages": pages})
    monkeypatch.setattr(pipeline, "DoclingSession", lambda settings: SessionDouble(failing={0, 1}))
    with pytest.raises(IngestionError) as caught:
        pipeline.extract_window(source, "version", 0, 1, {}, tmp_path / "out")
    assert caught.value.code == "DOCLING_CONVERSION_FAILED" and caught.value.details["failed_pages"] == [0, 1]


def test_blank_document_is_not_a_silent_success(tmp_path, monkeypatch):
    result = isolated_extract(tmp_path, monkeypatch, [preflight_page(0, "blank"), preflight_page(1, "blank")], SessionDouble())
    assert {"code": "DOCUMENT_WITHOUT_TEXT", "page_count": 2, "blank_pages": 2, "error_pages": 0} in result["warnings"]
    assert result["status"] == "ready"


def test_document_without_text_distinguishes_error_pages_from_blank_pages(tmp_path, monkeypatch):
    session = SessionDouble()
    result = isolated_extract(tmp_path, monkeypatch, [preflight_page(0, width=4000, height=4000), preflight_page(1, "blank")], session)
    assert session.calls == []
    assert {"code": "DOCUMENT_WITHOUT_TEXT", "page_count": 2, "blank_pages": 1, "error_pages": 1} in result["warnings"]
    assert result["status"] == "ready_partial" and result["coverage"]["unresolved"] == 1


def test_real_blank_fixture_reports_document_without_text(tmp_path):
    manifest = json.loads((ROOT / "evals/qualification-v2.1/manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["entries"] if item["key"] == "blank")
    source = ROOT / "fixtures" / entry["path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
    result = extract_pdf(source, tmp_path / "out", {}, "blank-version")
    assert [page["extraction_state"] for page in result["pages"]] == ["blank"]
    assert any(item["code"] == "DOCUMENT_WITHOUT_TEXT" for item in result["warnings"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]


def ocr_cells():
    # Sorties réelles observées (diagnostic E1) : « 24 » 97 %, « v » 60 %, « d » 0 %.
    return {0: [{"text": "24", "from_ocr": True, "confidence": .97, "bbox": {"l": 10, "b": 100, "r": 60, "t": 150, "coord_origin": "BOTTOMLEFT"}},
                {"text": "v", "from_ocr": True, "confidence": .605, "bbox": {"l": 70, "b": 100, "r": 90, "t": 150, "coord_origin": "BOTTOMLEFT"}},
                {"text": "d", "from_ocr": True, "confidence": 0.0, "bbox": {"l": 200, "b": 100, "r": 220, "t": 150, "coord_origin": "BOTTOMLEFT"}}]}


def test_low_confidence_ocr_words_make_the_document_partial_by_default(tmp_path, monkeypatch):
    result = isolated_extract(tmp_path, monkeypatch, [preflight_page(0, "regional_ocr")], SessionDouble(ocr_cells=ocr_cells()))
    page = result["pages"][0]
    assert page["ocr_used"]
    reasons = [(region["reason"], region["confidence"]) for region in page["unresolved_regions"]]
    assert reasons == [("OCR_WORD_LOW_CONFIDENCE", .605), ("OCR_WORD_LOW_CONFIDENCE", 0.0)]
    assert {"code": "OCR_WORD_LOW_CONFIDENCE", "page_index": 0, "count": 2, "minimum_confidence_required": .8} in result["warnings"]
    assert result["status"] == "ready_partial"
    assert result["coverage"]["unresolved_regions"] == 2


def test_profile_threshold_is_applied_and_zero_disables_it_explicitly(tmp_path, monkeypatch):
    result = isolated_extract(tmp_path, monkeypatch, [preflight_page(0, "regional_ocr")], SessionDouble(ocr_cells=ocr_cells()),
                              {"pdf": {"ocr_min_word_confidence": 0.5}})
    assert [region["confidence"] for region in result["pages"][0]["unresolved_regions"]] == [0.0]
    disabled = isolated_extract(tmp_path / "zero", monkeypatch, [preflight_page(0, "regional_ocr")], SessionDouble(ocr_cells=ocr_cells()),
                                {"pdf": {"ocr_min_word_confidence": 0}})
    assert disabled["status"] == "ready" and disabled["pages"][0]["unresolved_regions"] == []
