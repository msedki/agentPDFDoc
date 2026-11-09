"""Real PDFium path capture on tiny synthetic PDFs, without raster/OCR/Docling."""

import hashlib

import pytest

from services.ingestion.table_rules import native_rule_observations, prove_header_group

pytestmark = pytest.mark.integration


def synthetic_pdf(path, content):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << >> /Contents 4 0 R >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    payload = bytearray(b"%PDF-1.7\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    startxref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def captured(path, source_sha):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    try:
        page = document[0]
        try:
            return native_rule_observations(page, pdfium.raw, source_sha256=source_sha, page_index=0)
        finally:
            page.close()
    finally:
        document.close()


def observations():
    parent = {"id": "p", "text": "PART-Q8", "origin": "native", "state": "supported", "display_bbox": [90, 40, 120, 48]}
    headers = [{"id": f"h{index}", "text": text, "display_bbox": [x, 60, x + 15, 68], "origin": "native", "state": "supported"}
               for index, (x, text) in enumerate(((60, "Min"), (140, "Max")))]
    return parent, headers


def test_pdfium_matrix_paint_and_real_segments_prove_the_expected_physical_rectangle(tmp_path):
    path = tmp_path / "translated-rules.pdf"
    # The content matrix is deliberately nonidentity; the capture must not
    # treat local segment coordinates as physical coordinates.
    sha = synthetic_pdf(path, b"q 1 0 0 1 10 20 cm 0 G 0.5 w 30 100 m 170 100 l 170 160 l 30 160 l h S Q")
    record = captured(path, sha)
    assert record["complete"] and record["limit_reason"] is None
    assert record["source_sha256"] == sha and record["page_index"] == 0
    path_record = next(item for item in record["objects"] if item["type"] == 2)
    a, b, c, d, e, f = path_record["matrix"]
    positions = [(a * point[0] + c * point[1] + e, b * point[0] + d * point[1] + f)
                 for point in (item["point"] for item in path_record["segments"])]
    assert min(x for x, _ in positions) == pytest.approx(40)
    assert max(x for x, _ in positions) == pytest.approx(180)
    assert min(y for _, y in positions) == pytest.approx(120)
    assert max(y for _, y in positions) == pytest.approx(180)
    assert path_record["active"] is True and path_record["stroke_rgba"] == [0, 0, 0, 255]
    assert path_record["dash_count"] == 0 and path_record["stroke_width"] == pytest.approx(.5)
    parent, headers = observations()
    proof = prove_header_group(record, [parent], headers, [parent, *headers], table_bbox=[20, 100, 200, 190],
                               to_display=lambda box: [box[0], 200 - box[3], box[2], 200 - box[1]])
    assert proof is not None and proof["columns"] == [0, 1]
    assert proof["display_bbox"] == pytest.approx([40, 20, 180, 80])


@pytest.mark.parametrize("prefix", [b"0 0 100 200 re W n ", b"[3 3] 0 d "])
def test_real_clip_or_dash_cannot_be_replayed_as_an_unbroken_enclosure(tmp_path, prefix):
    path = tmp_path / "unsupported-paint.pdf"
    sha = synthetic_pdf(path, b"q " + prefix + b"0 G 0.5 w 40 120 m 180 120 l 180 180 l 40 180 l h S Q")
    record = captured(path, sha)
    assert record["complete"]
    parent, headers = observations()
    assert prove_header_group(record, [parent], headers, [parent, *headers], table_bbox=[20, 100, 200, 190],
                               to_display=lambda box: [box[0], 200 - box[3], box[2], 200 - box[1]]) is None
