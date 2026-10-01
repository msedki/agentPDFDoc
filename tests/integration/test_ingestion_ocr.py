"""Real CPU Docling/Tesseract coverage on controlled printed images."""

import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from services.ingestion import preflight_pdf
from services.runtime.platforms import native_executable

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Police de la fixture : Arial sous Windows, comme jusqu'ici ; ailleurs Liberation Sans Regular seule, police libre
# aux métriques d'Arial (mêmes chasses, donc même mise en page des cellules). Aucune autre police n'est substituée :
# DejaVu Sans, par exemple, a d'autres chasses. Texte, corps et positions sont inchangés.
FONT_SEARCH_ROOTS = (Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                     Path.home() / ".local/share/fonts", Path.home() / ".fonts")
LIBERATION_SANS_MISSING = ("Police de fixture Liberation Sans Regular (métriques d'Arial) introuvable sous /usr/share/fonts, "
                           "/usr/local/share/fonts, ~/.local/share/fonts ou ~/.fonts : l'installer (paquet fonts-liberation2 "
                           "sous Ubuntu 20.04) pour exécuter cet essai OCR ; aucune autre police n'est substituée.")


def _font_revision(path):
    """Révision déclarée par la table `head` du fichier TrueType (2.1 pour Liberation 2.1.0)."""
    data = path.read_bytes()
    for index in range(struct.unpack(">H", data[4:6])[0]):
        tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * index:28 + 16 * index])
        if tag == b"head":
            return round(struct.unpack(">i", data[offset + 4:offset + 8])[0] / 65536, 4)
    return 0.0


def fixture_font():
    """Arial sous Windows ; ailleurs le Liberation Sans Regular de plus haute révision, sinon essai ignoré."""
    if sys.platform == "win32":
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"
        if not font_path.is_file():
            pytest.skip("Police de fixture Windows Arial indisponible.")
        return font_path
    from PIL import ImageFont

    candidates = sorted({path.resolve() for root in FONT_SEARCH_ROOTS if root.is_dir()
                         for path in root.rglob("LiberationSans-Regular.ttf") if path.is_file()})
    candidates = [path for path in candidates if ImageFont.truetype(str(path), 29).getname() == ("Liberation Sans", "Regular")]
    if not candidates:
        pytest.skip(LIBERATION_SANS_MISSING)
    return max(candidates, key=lambda path: (_font_revision(path), str(path)))


def fixture_font_evidence(font_path):
    return {"font_path": str(font_path), "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
            "font_revision": _font_revision(font_path), "platform": sys.platform}


@pytest.fixture(autouse=True)
def recorded_fixture_font(record_property):
    """Police de la fixture consignée dans le rapport JUnit de chaque essai de ce module."""
    for key, value in fixture_font_evidence(fixture_font()).items():
        record_property(key, value)


@pytest.mark.skipif(sys.platform == "win32", reason="Sous Windows, la fixture utilise Arial, comme avant W018.")
def test_fixture_font_is_liberation_sans_only_outside_windows(tmp_path, monkeypatch):
    """Sans Liberation Sans, l'essai est ignoré avec son motif ; aucune autre police, même renommée, n'est prise."""
    fonts = tmp_path / "fonts"
    dejavu = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if dejavu.is_file():
        # Autre famille sous le nom attendu : refusée sur le nom interne de la police.
        (fonts / "faux").mkdir(parents=True)
        (fonts / "faux/LiberationSans-Regular.ttf").write_bytes(dejavu.read_bytes())
        (fonts / "faux/DejaVuSans.ttf").write_bytes(dejavu.read_bytes())
    monkeypatch.setattr(sys.modules[__name__], "FONT_SEARCH_ROOTS", (fonts,))
    with pytest.raises(pytest.skip.Exception, match="Liberation Sans Regular"):
        fixture_font()
    installed = {_font_revision(path): path for path in Path("/usr/share/fonts").rglob("LiberationSans-Regular.ttf")} \
        if Path("/usr/share/fonts").is_dir() else {}
    if not installed:
        return
    for index, path in enumerate(installed.values()):
        copy = fonts / f"v{index}/LiberationSans-Regular.ttf"
        copy.parent.mkdir(parents=True)
        copy.write_bytes(path.read_bytes())
    chosen = fixture_font()
    assert _font_revision(chosen) == max(installed)
    assert fixture_font_evidence(chosen)["font_sha256"] == hashlib.sha256(installed[max(installed)].read_bytes()).hexdigest()


def extract_in_fresh_worker(source, output_dir, config, version_id):
    request = Path(output_dir).parent / "worker-request.json"
    output = Path(output_dir).parent / "worker-result.json"
    request.write_text(json.dumps({"path": str(Path(source).resolve()), "output_dir": str(Path(output_dir).resolve()),
                                  "config": config, "version_id": version_id, "cancel_path": os.environ.get("RAG_TEST_CANCEL_PATH")}), encoding="utf-8")
    process = subprocess.run([sys.executable, "-X", "utf8", "-m", "services.ingestion.worker", "--request", str(request), "--result", str(output)],
                             capture_output=True, stdin=subprocess.DEVNULL, close_fds=True, timeout=900, check=False)
    response = json.loads(output.read_text(encoding="utf-8"))
    assert process.returncode == 0 and response["ok"], response
    assert process.stdout == process.stderr == b""
    assert (Path(output_dir) / "worker-native-fault.log").stat().st_size == 0
    return response["result"]


def write_printed_pdf(path, native=True, image_rotation=0):
    from PIL import Image, ImageDraw, ImageFont

    font_path = fixture_font()
    # Preuve à côté du PDF : chemin, SHA-256 et révision de la police qui a dessiné la fixture.
    Path(path).with_name(Path(path).stem + "-font.json").write_text(json.dumps(fixture_font_evidence(font_path)), encoding="utf-8")
    image = Image.new("RGB", (1000, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 29)
    draw.text((35, 20), "Tableau technique : valeurs nominales", fill="black", font=font)
    columns = (30, 480, 700, 970)
    rows = (90, 180, 270, 360, 450)
    for x in columns:
        draw.line((x, rows[0], x, rows[-1]), fill="black", width=3)
    for y in rows:
        draw.line((columns[0], y, columns[-1], y), fill="black", width=3)
    values = (("Équipement", "Valeur", "Unité"), ("CCU-21", "24", "V"),
              ("Température capteur", "45", "°C"), ("Courant nominal", "2", "A"))
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            draw.text((columns[column_index] + 15, rows[row_index] + 25), value, fill="black", font=font)
    draw.text((35, 510), "Vérifier la tension avant le raccordement.", fill="black", font=font)
    if image_rotation:
        image = image.rotate(image_rotation, expand=True)
    image_bytes = zlib.compress(image.tobytes())
    commands = []
    if native:
        for y, value in ((720, "Installation de l'équipement CCU-21."), (680, "Le paragraphe natif décrit le raccordement sécurisé.")):
            commands.append(f"BT /F1 14 Tf 50 {y} Td <{value.encode('cp1252').hex()}> Tj ET")
    commands.append("q 500 0 0 320 50 80 cm /Im0 Do Q")
    stream = "\n".join(commands).encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 6 0 R >> >> /Contents 5 0 R >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
               f"<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(image_bytes)} >>\nstream\n".encode() + image_bytes + b"\nendstream"]
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
    return Path(path)


@pytest.fixture
def actual_profile():
    import yaml

    profile = yaml.safe_load(Path("config/local16.yaml").read_text(encoding="utf-8-sig"))
    # Même commande que celle que l'API transmet au worker : sans `.exe` hors Windows (W018), inchangée sous Windows.
    profile["pdf"]["tesseract_cmd"] = native_executable(profile["pdf"]["tesseract_cmd"])
    if os.environ.get("RAG_TEST_PDF_BACKEND"):
        profile["pdf"]["pdf_backend"] = os.environ["RAG_TEST_PDF_BACKEND"]
    if os.environ.get("RAG_TEST_OCR_DERIVATIVES") == "intrinsic_and_border":
        profile["pdf"].update(ocr_intrinsic_aspect=True, ocr_cell_border=True, ocr_min_word_confidence=.8)
    artifact_dir = Path(profile["pdf"]["artifacts_path"])
    required = [artifact_dir / "docling-project--docling-layout-heron/model.safetensors",
                artifact_dir / "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors"]
    if not all(path.is_file() for path in required):
        pytest.skip("Poids Docling réels non provisionnés ; aucune preuve OCR produite.")
    return profile


def assert_nominal_table(page, image_rotation=0):
    tables = [block for block in page["blocks"] if block["type"] == "table"]
    assert len(tables) == 1
    data = tables[0]["metadata"]["table_data"]
    assert (data["num_rows"], data["num_cols"]) == (4, 3)
    actual = {(cell["start_row_offset_idx"], cell["start_col_offset_idx"]): cell["text"] for cell in data["table_cells"]}
    expected = (("Équipement", "Valeur", "Unité"), ("CCU-21", "24", "V"),
                ("Température capteur", "45", "°C"), ("Courant nominal", "2", "A"))
    assert actual == {(row, column): value for row, cells in enumerate(expected) for column, value in enumerate(cells)}
    columns, rows = (30, 480, 700, 970), (90, 180, 270, 360, 450)
    for cell in tables[0]["metadata"]["table_cell_regions"]:
        row, column, region = cell["row"], cell["column"], cell["bbox"]
        assert region is not None
        points = [(x, y) for x in (columns[column], columns[column + 1]) for y in (rows[row], rows[row + 1])]
        if image_rotation == 90:
            points = [(y, 1000 - x) for x, y in points]
        width, height = (600, 1000) if image_rotation == 90 else (1000, 600)
        physical = [(50 + x * 500 / width, 400 - y * 320 / height) for x, y in points]
        limit = [min(x for x, _ in physical), min(y for _, y in physical), max(x for x, _ in physical), max(y for _, y in physical)]
        assert limit[0] - 3 <= region[0] <= region[2] <= limit[2] + 3
        assert limit[1] - 3 <= region[1] <= region[3] <= limit[3] + 3


def test_real_mixed_native_and_scanned_table_without_duplicate(tmp_path, actual_profile):
    original = write_printed_pdf(tmp_path / "mixed.pdf")
    source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    preview = preflight_pdf(original, actual_profile)
    assert preview["pages"][0]["classification"] == "mixed"
    result = extract_in_fresh_worker(original, tmp_path / "extraction", actual_profile, "mixed-version")
    assert result["status"] == "ready", result["warnings"]
    assert result["sha256"] == source_hash == hashlib.sha256(original.read_bytes()).hexdigest()
    page = result["pages"][0]
    assert page["ocr_used"] and page["ocr_cell_count"] > 0
    text = "\n".join(block["raw_text"] for block in page["blocks"])
    assert text.count("Le paragraphe natif") == 1
    assert "CCU-21" in text and "24" in text and "45" in text
    assert any(block["type"] == "table" for block in page["blocks"])
    assert_nominal_table(page)
    native = [block for block in page["blocks"] if "Le paragraphe natif" in block["raw_text"]]
    assert native[0]["metadata"]["extraction_method"] == "native"
    assert not native[0]["metadata"]["ocr_used"]
    assert page["ocr_regions"]
    assert page["ocr_preprocessing"][0]["algorithm"] == "crossing-rules-v2"
    assert all(40 <= box[0] <= box[2] <= 560 and 70 <= box[1] <= box[3] <= 410 for box in page["ocr_regions"])
    Path(tmp_path / "fixture-proof.json").write_text(json.dumps({"source_sha256": source_hash, "coverage": result["coverage"], "warnings": result["warnings"], "ocr_cell_count": page["ocr_cell_count"]}), encoding="utf-8")


@pytest.mark.parametrize("rotation", [0, 90])
def test_real_french_scan_and_region_orientation(tmp_path, actual_profile, rotation):
    original = write_printed_pdf(tmp_path / "scan.pdf", native=False, image_rotation=rotation)
    result = extract_in_fresh_worker(original, tmp_path / "extraction", actual_profile, f"scan-{rotation}-version")
    assert result["status"] == "ready", result["warnings"]
    page = result["pages"][0]
    assert page["classification"] == "scan_candidate"
    assert page["orientation_correction"] == rotation
    assert page["ocr_used"] and page["ocr_regions"]
    text = "\n".join(block["raw_text"] for block in page["blocks"])
    assert "CCU-21" in text and "24" in text and "45" in text
    assert_nominal_table(page, rotation)
    assert all(block["source_text_hash"] == hashlib.sha256(block["raw_text"].encode()).hexdigest() for block in page["blocks"])


def test_real_five_page_scan_reuses_pipeline_across_windows(tmp_path, actual_profile):
    import pypdfium2 as pdfium

    single = write_printed_pdf(tmp_path / "one-page.pdf", native=False)
    original = tmp_path / "five-pages.pdf"
    with pdfium.PdfDocument(str(single)) as source, pdfium.PdfDocument.new() as destination:
        destination.import_pages(source, [0] * 5)
        destination.save(str(original))
    source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    result = extract_in_fresh_worker(original, tmp_path / "extraction", actual_profile, "five-scan-version")
    assert result["status"] == "ready", result["warnings"]
    assert result["sha256"] == source_hash == hashlib.sha256(original.read_bytes()).hexdigest()
    assert [(window["page_start"], window["page_end"]) for window in result["windows"]] == [(0, 3), (4, 4)]
    assert result["coverage"] == {"total": 5, "processed": 5, "ocr": 5, "unresolved": 0, "unresolved_regions": 0}
    for page in result["pages"]:
        assert_nominal_table(page)
    lifecycles = []
    for path in sorted((tmp_path / "extraction").glob("window-*.json")):
        window = json.loads(path.read_text(encoding="utf-8"))["payload"]
        lifecycles.extend(metric["lifecycle"] for metric in window["route_metrics"])
    assert len(lifecycles) == 2
    assert len({record["converter_instance"] for record in lifecycles}) == 1
    assert len({record["pipeline_instance"] for record in lifecycles}) == 1
    assert len({record["backend"]["backend_sequence"] for record in lifecycles}) == 2
    for record, expected_range in zip(lifecycles, [[1, 4], [5, 5]], strict=True):
        backend = record["backend"]
        assert record["remaining_stage_threads"] == []
        assert backend["page_range"] == expected_range
        if backend["iteration_mode"] == "threaded":
            assert backend["iterator_exhausted"] is True
        else:
            assert backend["requested_pages_complete"] is True
            assert backend["loaded_outside_page_range"] == []
        assert backend["unload_completed"] is True
        assert backend["drained_outside_page_range"] == []
        assert sorted(backend["yielded_page_numbers"] + backend["drained_page_numbers"]) == list(range(expected_range[0], expected_range[1] + 1))
