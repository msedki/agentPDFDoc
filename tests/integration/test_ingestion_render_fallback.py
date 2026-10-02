"""Préservation native réelle d'une page mixte A3, sans modèle ni rendu de page."""

import hashlib
import zlib

import pytest

from services.ingestion import extract_pdf, preflight_pdf
from services.ingestion.docling_adapter import DoclingSession

pytestmark = pytest.mark.integration
NATIVE_LINE = "Couche native préservée : équipement CCU-21, tension nominale 24 V."


def mixed_a3_pdf():
    """PDF synthétique : une ligne native fiable et une image, sur le format qui déclenche le plafond livré."""
    content = (f"BT /F1 14 Tf 50 1100 Td <{NATIVE_LINE.encode('cp1252').hex()}> Tj ET\n"
               "q 600 0 0 800 50 100 cm /Im0 Do Q").encode()
    image = zlib.compress(bytes(range(64)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 841.89 1190.55] /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 6 0 R >> >> /Contents 5 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length "
        + str(len(image)).encode() + b" >>\nstream\n" + image + b"\nendstream",
    ]
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
    return bytes(output)


def test_real_mixed_a3_keeps_native_text_and_render_limit_on_resume(tmp_path, monkeypatch):
    original = tmp_path / "Page mixte A3.pdf"
    original.write_bytes(mixed_a3_pdf())
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    config = {"pdf": {"pdf_backend": "pypdfium2"}}
    preview = preflight_pdf(original, config)
    assert preview["pages"][0]["classification"] == "mixed" and preview["pages"][0]["needs_ocr"]
    original_converter = DoclingSession.converter
    routes = []

    def native_only(self, route):
        # La garde échoue avant la création de modèles si le pipeline tente malgré tout structured/OCR.
        assert route == "native"
        routes.append(route)
        return original_converter(self, route)

    monkeypatch.setattr(DoclingSession, "converter", native_only)
    result = extract_pdf(original, tmp_path / "extraction", config, "mixed-a3-version")
    assert result["status"] == "ready_partial" and routes == ["native"]
    page = result["pages"][0]
    assert page["extraction_route"] == "native" and page["routing_reason"] == "render_limit_native_fallback"
    text_blocks = [block for block in page["blocks"] if block["raw_text"].strip()]
    assert "\n".join(block["raw_text"] for block in text_blocks).count(NATIVE_LINE) == 1
    assert all(block["bbox"] is not None and block["metadata"]["extraction_method"] == "native" for block in text_blocks)
    assert all(block["source_text_hash"] == hashlib.sha256(block["raw_text"].encode()).hexdigest() for block in text_blocks)
    assert page["native_quality"]["alphanumeric_coverage_ratio"] >= .95 and not page["ocr_used"]
    assert "PDF_RENDER_LIMIT" in {region["reason"] for region in page["unresolved_regions"]}
    warning = next(warning for warning in result["warnings"] if warning["code"] == "PDF_RENDER_LIMIT")
    assert warning["route"] == "regional_ocr" and warning["render_pixels"] > warning["pixel_limit"] == 8_000_000
    assert not any(warning["code"] == "DOCUMENT_WITHOUT_TEXT" for warning in result["warnings"])
    resumed = extract_pdf(original, tmp_path / "extraction", config, "mixed-a3-version")
    assert routes == ["native"] and all(window["reused"] for window in resumed["windows"])
    assert resumed["status"] == "ready_partial" and resumed["pages"] == result["pages"]
    assert resumed["warnings"] == result["warnings"]
    assert result["sha256"] == digest == hashlib.sha256(original.read_bytes()).hexdigest()
