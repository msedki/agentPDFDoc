"""Actual Docling/PDFium boundaries on synthetic originals in pytest tmp paths."""

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from services.ingestion import IngestionError, extract_pdf, extract_window, preflight_pdf

pytestmark = pytest.mark.integration


def native_config():
    return {"pipeline_route": "native", "pdf_backend": os.environ.get("RAG_TEST_PDF_BACKEND", "docling_parse")}


def write_native_pdf(path, page_count=1, rotation=0, crop=None, inherited_media=False):
    """Write controlled PDF bytes without introducing a second PDF parser."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for index in range(page_count):
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        crop_entry = f" /CropBox [{' '.join(str(x) for x in crop)}]" if crop else ""
        media_entry = "" if inherited_media else " /MediaBox [0 0 600 800]"
        page = f"<< /Type /Page /Parent 2 0 R{media_entry} /Rotate {rotation}{crop_entry} /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>"
        text = f"Procédure installation page {index + 1}: CCU-21 tension nominale 24 V."
        # Hex WinAnsi string preserves the controlled accent in the original.
        content = f"BT /F1 14 Tf 50 650 Td <{text.encode('cp1252').hex()}> Tj ET".encode()
        objects += [page.encode(), b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    inherited_entry = " /MediaBox [0 0 600 800]" if inherited_media else ""
    objects[1] = f"<< /Type /Pages /Count {page_count} /Kids [{' '.join(kids)}]{inherited_entry} >>".encode()
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, content in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + content + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    Path(path).write_bytes(output)
    return path


@pytest.fixture(autouse=True)
def require_actual_parsers():
    if importlib.util.find_spec("docling") is None or importlib.util.find_spec("pypdfium2") is None:
        pytest.skip("Runtimes Docling/pypdfium2 non provisionnés ; aucune preuve d'intégration produite.")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_real_native_provenance_with_rotation_and_crop(tmp_path, rotation):
    original = write_native_pdf(tmp_path / "Procédure française.pdf", rotation=rotation, crop=[20, 30, 580, 770])
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    result = extract_pdf(original, tmp_path / "extraction", native_config(), "native-version")
    assert result["status"] == "ready"
    assert result["sha256"] == before == hashlib.sha256(original.read_bytes()).hexdigest()
    page = result["pages"][0]
    assert page["rotation"] == rotation
    assert page["crop_box"] == [20, 30, 580, 770]
    matching = [block for block in page["blocks"] if "CCU-21" in block["raw_text"]]
    assert matching
    block = matching[0]
    assert block["bbox"] is not None, result["warnings"]
    # All physical rotations refer to the same original line near (50,650).
    assert 40 <= block["bbox"][0] <= 60
    assert 630 <= block["bbox"][1] <= 665
    assert block["source_text_hash"] == hashlib.sha256(block["raw_text"].encode()).hexdigest()
    assert not page["ocr_used"]


def test_real_absolute_page_range_and_checkpoint_reuse(tmp_path):
    original = write_native_pdf(tmp_path / "version.pdf", page_count=5)
    window = extract_window(original, "window-version", 3, 4, native_config(), tmp_path / "one-window")
    assert [page["page_index"] for page in window["pages"]] == [3, 4]
    assert any("page 5" in block["text"] for block in window["pages"][1]["blocks"])
    first = extract_pdf(original, tmp_path / "all", native_config(), "window-version")
    checkpoint = tmp_path / "all" / "window-000000-000003.json"
    timestamp = checkpoint.stat().st_mtime_ns
    second = extract_pdf(original, tmp_path / "all", native_config(), "window-version")
    assert second["status"] == "ready"
    assert second["pages"] == first["pages"]
    assert all(window["reused"] for window in second["windows"])
    assert checkpoint.stat().st_mtime_ns == timestamp


def test_real_inherited_boxes_never_fabricate_ansi_page(tmp_path):
    original = write_native_pdf(tmp_path / "inherited.pdf", inherited_media=True)
    result = extract_pdf(original, tmp_path / "extraction", native_config(), "inherited-version")
    assert result["status"] == "ready"
    page = result["pages"][0]
    assert page["effective_box"] == [0, 0, 600, 800]
    assert page["media_box"] in (None, [0, 0, 600, 800])
    assert page["crop_box"] in (None, [0, 0, 600, 800])
    assert 40 <= page["blocks"][0]["bbox"][0] <= 60


def test_real_preflight_refusal_and_pause_resume(tmp_path):
    invalid = tmp_path / "malformed.pdf"
    invalid.write_bytes(b"%PDF-1.7\nmalformed original")
    with pytest.raises(IngestionError) as caught:
        preflight_pdf(invalid)
    assert caught.value.code == "PDF_INVALID"
    original = write_native_pdf(tmp_path / "valid.pdf")
    with pytest.raises(IngestionError) as caught:
        preflight_pdf(original, {"max_file_mib": 1, "max_document_pages": 0})
    assert caught.value.code == "INVALID_CONFIG"
    signal = tmp_path / "pause"
    signal.touch()
    paused = extract_pdf(original, tmp_path / "extraction", native_config(), "pause-version", signal)
    assert paused["status"] == "interrupted"
    assert paused["coverage"]["processed"] == 0
    signal.unlink()
    resumed = extract_pdf(original, tmp_path / "extraction", native_config(), "pause-version", signal)
    assert resumed["status"] == "ready"


def test_fresh_worker_reports_safe_failure(tmp_path):
    import json
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"private text deliberately not a PDF")
    request = tmp_path / "request.json"
    output = tmp_path / "result.json"
    request.write_text(json.dumps({"path": str(invalid), "output_dir": str(tmp_path / "extraction"), "version_id": "invalid-version"}), encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "services.ingestion.worker", "--request", str(request), "--result", str(output)], capture_output=True, text=True, timeout=60, check=False)
    response = json.loads(output.read_text(encoding="utf-8"))
    assert process.returncode == 2
    assert response["error"]["code"] == "INVALID_PDF_SIGNATURE"
    assert "private text" not in process.stdout + process.stderr + output.read_text()
