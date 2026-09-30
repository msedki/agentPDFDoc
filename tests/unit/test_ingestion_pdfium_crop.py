"""Repère des cellules PDFium (Docling 2.131) sur une CropBox décalée : vrai PDFium, sans modèle."""

import importlib.util
from pathlib import Path

import pytest

from services.ingestion.geometry import docling_box_to_pdf
from services.ingestion.lifecycle import crop_consistent_pdfium_page_class, crop_translation

pytestmark = pytest.mark.skipif(importlib.util.find_spec("docling") is None or importlib.util.find_spec("pypdfium2") is None,
                                reason="Docling/pypdfium2 non provisionnés")
CROP = [20, 30, 580, 770]


def write_pdf(path: Path, rotation: int) -> Path:
    content = b"BT /F1 14 Tf 50 650 Td (CCU-21 tension nominale 24 V) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /CropBox [{' '.join(map(str, CROP))}] "
               f"/Rotate {rotation} /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>".encode(),
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    output = bytearray(b"%PDF-1.7\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    output += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(output))
    return path


def test_translation_table_matches_docling_rotation_formulas():
    assert crop_translation(20, 30, 0) == (-20, 30)
    assert crop_translation(20, 30, 90) == (-30, -20)
    assert crop_translation(20, 30, 180) == (20, -30)
    assert crop_translation(20, 30, 270) == (30, 20)
    assert crop_translation(0, 0, 90) == (0, 0)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_pdfium_cells_land_on_the_original_line_with_offset_cropbox(tmp_path, rotation):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(write_pdf(tmp_path / f"crop-{rotation}.pdf", rotation)))
    page = crop_consistent_pdfium_page_class()(document, "test-hash", 0)
    try:
        size = page.get_size()
        cells = [cell for cell in page.get_text_cells() if "CCU-21" in cell.text]
        assert cells
        box = cells[0].rect.to_bounding_box()
        pdf_box = docling_box_to_pdf({"l": box.l, "t": box.t, "r": box.r, "b": box.b, "coord_origin": box.coord_origin.value},
                                     (size.width, size.height), {"crop_box": CROP, "rotation": rotation})
        # Même ligne d'origine (50, 650) pour toutes les rotations, sans double décalage de CropBox.
        assert 40 <= pdf_box[0] <= 60 and 630 <= pdf_box[1] <= 665
        # Aller-retour : la requête texte dans le cadre traduit retrouve la même ligne.
        assert "CCU-21" in page.get_text_in_rect(box)
    finally:
        page.unload()
        document.close()
