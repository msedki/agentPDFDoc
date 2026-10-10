"""Real Office extraction, source identity and durable unit checkpoints.

Fixtures are generated OOXML archives. Only cooperative cancellation is
instrumented; the package verification and DOCX/XLSX parsers run unchanged.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from test_office_docx import package_file, paragraph

from services.ingestion.errors import IngestionError
from services.ingestion.office import pipeline
from services.ingestion.office.opc import OfficePackage
from tests.fixtures.office.xlsx_cases import write_workbook


def document(tmp_path, document_format):
    if document_format == "xlsx":
        return write_workbook(tmp_path / "budget.xlsx")
    return package_file(tmp_path, paragraph("Titre", '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>')
                        + paragraph("A😀é e\u0301 : tension 72 V."),
                        parts={"word/header1.xml": '<w:hdr xmlns:w="{W}">' + paragraph("En-tête") + "</w:hdr>"})


@pytest.mark.parametrize("document_format", ["docx", "xlsx"])
def test_real_extraction_revision_and_unicode_hash_are_stable(tmp_path, document_format):
    path = document(tmp_path, document_format)
    original = path.read_bytes()
    version_id = str(uuid4())
    first = pipeline.extract_office(path, tmp_path / "first", {}, version_id, document_format)
    second = pipeline.extract_office(path, tmp_path / "second", {}, version_id, document_format)
    cached = pipeline.extract_office(path, tmp_path / "first", {}, version_id, document_format)
    assert first == second == cached
    assert first["sha256"] == hashlib.sha256(original).hexdigest()
    assert pipeline.office_content_hash(first) == first["source_hash"]
    blocks = [block for unit in first["units"] for block in unit["blocks"]]
    assert blocks and len({block["id"] for block in blocks}) == len(blocks)
    for block in blocks:
        assert block["source_text_hash"] == hashlib.sha256(block.get("raw_text", block["text"]).encode()).hexdigest()
        assert block["extraction_revision_id"] == first["extraction_revision_id"]
        assert block["locator"]["kind"] == ("docx_element" if document_format == "docx" else "xlsx_cells")
        assert block.get("page_index") is None
    assert path.read_bytes() == original
    assert json.loads((tmp_path / "first" / "extraction.json").read_text()) == first
    another_version = pipeline.extract_office(path, tmp_path / "third", {}, str(uuid4()), document_format)
    assert another_version["source_hash"] == first["source_hash"]
    assert another_version["extraction_revision_id"] != first["extraction_revision_id"]


@pytest.mark.parametrize("document_format", ["docx", "xlsx"])
def test_pause_after_complete_unit_resumes_exactly_and_skips_source_unit(tmp_path, monkeypatch, document_format):
    path = document(tmp_path, document_format)
    version_id = str(uuid4())
    expected = pipeline.extract_office(path, tmp_path / "reference", {}, version_id, document_format)
    output = tmp_path / "resume"
    cancel = tmp_path / "cancel"
    atomic_json = pipeline.atomic_json

    def pause_on_durable_unit(target, value):
        atomic_json(target, value)
        if target.parent.name == "office-units":
            cancel.touch()

    monkeypatch.setattr(pipeline, "atomic_json", pause_on_durable_unit)
    paused = pipeline.extract_office(path, output, {}, version_id, document_format, cancel)
    assert paused["status"] == "checkpointed"
    assert not (output / "extraction.json").exists()
    caches = list((output / "office-units").glob("*.json"))
    assert len(caches) == 1
    completed = json.loads(caches[0].read_text())["unit"]
    assert completed["blocks"]
    cancel.unlink()
    monkeypatch.setattr(pipeline, "atomic_json", atomic_json)

    # Preflight still verifies all original bytes. The adapter must not perform
    # its expensive second parsing of an already completed source sheet/part.
    source_part = completed["part"]
    if document_format == "xlsx":
        sheet_parser = OfficePackage.iter_xml

        def reject_sheet_parse(package, part, *args, **kwargs):
            if part == source_part:
                pytest.fail("A completed worksheet was parsed again instead of resumed")
            return sheet_parser(package, part, *args, **kwargs)

        monkeypatch.setattr(OfficePackage, "iter_xml", reject_sheet_parse)
    else:
        from services.ingestion.office.docx import _DocxReader

        block_parser = _DocxReader.source_items

        def reject_block_extraction(reader, root, part, *args, **kwargs):
            if part == source_part:
                pytest.fail("A completed DOCX part was extracted again instead of resumed")
            return block_parser(reader, root, part, *args, **kwargs)

        monkeypatch.setattr(_DocxReader, "source_items", reject_block_extraction)
    resumed = pipeline.extract_office(path, output, {}, version_id, document_format)
    assert resumed == expected
    assert all("_resume" not in unit for unit in resumed["units"])


@pytest.mark.parametrize("tamper", ["payload", "source", "fingerprint", "truncated"])
def test_checkpoint_tampering_is_refused_before_publication(tmp_path, tamper):
    path = document(tmp_path, "xlsx")
    output = tmp_path / "extracted"
    version_id = str(uuid4())
    pipeline.extract_office(path, output, {}, version_id, "xlsx")
    (output / "extraction.json").unlink()
    cache = next((output / "office-units").glob("*.json"))
    envelope = json.loads(cache.read_text())
    if tamper == "payload":
        envelope["unit"]["blocks"][0]["text"] += " altered"
    elif tamper == "source":
        envelope["sha256"] = "0" * 64
    elif tamper == "fingerprint":
        envelope["fingerprint"] = "0" * 64
    if tamper == "truncated":
        cache.write_text('{"unit":')
    else:
        cache.write_text(json.dumps(envelope))
    with pytest.raises(IngestionError) as error:
        pipeline.extract_office(path, output, {}, version_id, "xlsx")
    assert error.value.code == "OFFICE_CHECKPOINT_INVALID"
    assert not (output / "extraction.json").exists()


def test_preexisting_cancel_has_no_completed_or_published_extraction(tmp_path):
    path = document(tmp_path, "xlsx")
    cancel = tmp_path / "cancel"
    cancel.touch()
    output = tmp_path / "paused"
    result = pipeline.extract_office(path, output, {}, str(uuid4()), "xlsx", cancel)
    assert result["status"] == "checkpointed"
    assert not (output / "extraction.json").exists()
    assert not list((output / "office-units").glob("*.json"))


def test_corrupt_original_and_resource_limit_cannot_publish(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"PK\x03\x04truncated")
    with pytest.raises(IngestionError):
        pipeline.extract_office(path, tmp_path / "broken", {}, str(uuid4()), "xlsx")
    assert not (tmp_path / "broken" / "extraction.json").exists()
    path = document(tmp_path, "xlsx")
    with pytest.raises(IngestionError) as error:
        pipeline.extract_office(path, tmp_path / "limited", {"office": {"max_cells": 1}}, str(uuid4()), "xlsx")
    assert error.value.code == "OFFICE_LIMIT_EXCEEDED"
    assert not (tmp_path / "limited" / "extraction.json").exists()


@pytest.mark.parametrize("document_format", ["docx", "xlsx"])
def test_native_office_worker_keeps_models_absent_and_document_text_private(tmp_path, document_format):
    path = document(tmp_path, document_format)
    output = tmp_path / "worker-output"
    request, result = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(json.dumps({"path": str(path), "output_dir": str(output), "config": {},
                                   "version_id": str(uuid4()), "format": document_format}))
    # A real isolated Office entrypoint is executed. The code only inspects
    # module presence after extraction; no parser/model boundary is replaced.
    script = "from services.ingestion.office.worker import main; import sys; code = main(); assert not any(name.split('.')[0] in {'torch', 'docling', 'onnxruntime'} for name in sys.modules); raise SystemExit(code)"
    completed = subprocess.run([sys.executable, "-B", "-c", script, "--request", str(request), "--result", str(result)],
                               cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
                               timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == completed.stderr == ""
    envelope = json.loads(result.read_text())
    assert envelope["ok"] is True and envelope["result"]["format"] == document_format
    assert envelope["result"]["units"]
    assert (output / "worker-native-fault.log").stat().st_size == 0


def test_office_worker_corruption_has_safe_error_and_no_native_model_load(tmp_path):
    path = tmp_path / "private-secret-title.docx"
    path.write_bytes(b"PK\x03\x04private-document-body")
    request, result = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(json.dumps({"path": str(path), "output_dir": str(tmp_path / "worker"),
                                   "version_id": str(uuid4()), "format": "docx"}))
    completed = subprocess.run([sys.executable, "-B", "-m", "services.ingestion.office.worker", "--request", str(request),
                                "--result", str(result)], cwd=Path(__file__).resolve().parents[2],
                               capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 2
    assert completed.stdout == completed.stderr == ""
    envelope = json.loads(result.read_text())
    assert envelope["ok"] is False and envelope["error"]["code"] == "OFFICE_INVALID_PACKAGE"
    assert "private-secret-title" not in result.read_text() and "private-document-body" not in result.read_text()
    assert not (tmp_path / "worker" / "extraction.json").exists()
