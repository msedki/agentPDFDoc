"""I5 corpus integrity tests; explicit PDF byte doubles, no native engine/model."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.qualification import prepare_trust_i5 as harness


def write_json(path: Path, value: object) -> bytes:
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return raw


def frozen_fixture(tmp_path, monkeypatch):
    base = tmp_path / "reserved-double"
    (base / "originals").mkdir(parents=True)
    (base / "scans").mkdir()
    documents = []
    for index in range(3):
        path = f"originals/source-{index}.pdf"
        raw = f"%PDF-1.7 explicit non-rendered harness double {index}".encode()
        (base / path).write_bytes(raw)
        documents.append({"id": f"D{index}", "file": path, "original_sha256": hashlib.sha256(raw).hexdigest(),
                          "bytes": len(raw), "pages": 4, "url": "https://example.invalid/explicit-double.pdf",
                          "revision": "explicit-double", "revision_date_month": None})
    cases = [{"id": f"Q{index}", "document_id": f"D{index % 3}", "question": f"Explicit question double {index}",
              "answerable": index < 8, "scope": {"kind": "pages", "page_start": 2, "page_end": 2},
              "required_evidence_units": [{"id": f"E{index}", "property": "frozen double"}]}
             for index in range(10)]
    scans = []
    for index, mode in enumerate(("image_only", "image_body_native_footer")):
        raw = f"%PDF-1.7 explicit derived double {index}".encode()
        path = f"scans/scan-{index}.pdf"
        (base / path).write_bytes(raw)
        transform = {"render_dpi": 200, "scale": 200 / 72, "rotation_degrees": 0, "color": "8-bit grayscale",
                     "resizing_after_render": False, "augmentation": None, "reportlab_invariant": True,
                     "embedded_text": bool(index), "native_footer": ["explicit footer", "double only"] if index else None,
                     "native_footer_font": "Helvetica" if index else None,
                     "native_footer_size_points": 7.5 if index else None,
                     "native_footer_positions": [[79, 30], [79, 20]] if index else None,
                     "white_footer_rectangle": [0, 0, 612, 44] if index else None}
        scans.append({"id": f"S{index}", "file": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                      "case_id": f"Q{index}", "original_document_id": f"D{index}", "original_page_index": 2,
                      "original_sha256": documents[index]["original_sha256"], "product_physical_page": 1,
                      "kind": mode, "raster_dimensions": [1700, 2200], "transform": transform})
    values = {"sources.json": {"schema_version": "i5-heldout-sources-v1", "documents": documents},
              "questions-oracles.json": {"schema_version": "i5-heldout-questions-v1", "cases": cases},
              "scan-transformations.json": {"schema_version": "i5-heldout-derived-pairs-v1", "scans": scans}}
    reseal(base, values, monkeypatch)
    return base, values


def reseal(base, values, monkeypatch):
    entries = []
    for name, value in values.items():
        raw = write_json(base / name, value)
        entries.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    receipt = {"schema_version": "i5-heldout-freeze-v1", "counts": dict(harness.COUNTS),
               "frozen_at_utc": "2026-11-08T00:00:00+00:00", "private_files": entries}
    raw = write_json(base / "freeze-receipt.json", receipt)
    # Tests explicitly create a different synthetic frozen corpus, never change
    # the actual heldout receipt or its oracle after observing a product output.
    monkeypatch.setattr(harness, "HELDOUT_RECEIPT_SHA256", hashlib.sha256(raw).hexdigest())


def test_rejects_changed_receipt_before_reading_any_oracle(tmp_path):
    (tmp_path / "freeze-receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="freeze receipt"):
        harness.frozen_inputs(tmp_path)
    assert not (tmp_path / "questions-oracles.json").exists()


@pytest.mark.parametrize("entry", ["sources.json", "questions-oracles.json", "scan-transformations.json"])
def test_manifest_changes_are_not_reinterpreted_as_the_frozen_corpus(tmp_path, monkeypatch, entry):
    base, _ = frozen_fixture(tmp_path, monkeypatch)
    with (base / entry).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="manifest changed"):
        harness.frozen_inputs(base)


@pytest.mark.parametrize("entry", ["originals/source-0.pdf", "scans/scan-0.pdf"])
def test_source_and_derived_pdf_bytes_are_verified_before_worker(tmp_path, monkeypatch, entry):
    base, _ = frozen_fixture(tmp_path, monkeypatch)
    (base / entry).write_bytes(b"%PDF-1.7 different source")
    with pytest.raises(ValueError, match="PDF bytes changed"):
        harness.frozen_inputs(base)


def test_same_bytes_through_a_symlink_are_not_accepted_as_confined_input(tmp_path, monkeypatch):
    base, _ = frozen_fixture(tmp_path, monkeypatch)
    target = tmp_path / "outside.pdf"
    source = base / "originals/source-0.pdf"
    target.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(target)
    with pytest.raises(ValueError, match="symbolique"):
        harness.frozen_inputs(base)


@pytest.mark.parametrize("mutation", ["duplicate-question", "unknown-document", "bool-page", "outside-page",
                                     "empty-evidence", "changed-denominator", "wrong-derived-document",
                                     "negative-derived", "wrong-derived-page", "invented-physical-page",
                                     "native-answer-in-scan", "two-scans", "large-raster", "unknown-mode"])
def test_frozen_metadata_links_and_denominators_must_remain_valid(tmp_path, monkeypatch, mutation):
    base, values = frozen_fixture(tmp_path, monkeypatch)
    cases = values["questions-oracles.json"]["cases"]
    scans = values["scan-transformations.json"]["scans"]
    if mutation == "duplicate-question":
        cases[1]["id"] = cases[0]["id"]
    elif mutation == "unknown-document":
        cases[0]["document_id"] = "unknown"
    elif mutation == "bool-page":
        cases[0]["scope"]["page_start"] = True
    elif mutation == "outside-page":
        cases[0]["scope"]["page_end"] = 4
    elif mutation == "empty-evidence":
        cases[0]["required_evidence_units"] = []
    elif mutation == "changed-denominator":
        cases[0]["answerable"] = False
    elif mutation == "wrong-derived-document":
        scans[0]["original_document_id"] = "D1"
    elif mutation == "negative-derived":
        scans[0]["case_id"] = "Q9"
    elif mutation == "wrong-derived-page":
        scans[0]["original_page_index"] = 1
    elif mutation == "invented-physical-page":
        scans[0]["product_physical_page"] = 3
    elif mutation == "native-answer-in-scan":
        scans[0]["transform"]["embedded_text"] = True
    elif mutation == "two-scans":
        scans[1]["kind"] = "image_only"
        scans[1]["transform"]["embedded_text"] = False
        scans[1]["transform"]["native_footer"] = None
    elif mutation == "large-raster":
        scans[0]["raster_dimensions"] = [100_000, 100_000]
    else:
        scans[0]["kind"] = "arbitrary"
    reseal(base, values, monkeypatch)
    with pytest.raises(ValueError):
        harness.frozen_inputs(base)


def test_transfer_and_derived_preserve_oracles_and_physical_page_scopes(tmp_path, monkeypatch):
    base, values = frozen_fixture(tmp_path, monkeypatch)
    before = {name: (base / name).read_bytes() for name in harness.MANIFEST_NAMES}
    transfer = harness.transfer_dataset(base, "transfer")
    derived = harness.transfer_dataset(base, "ocr")
    assert len(transfer["documents"]) == 3 and len(transfer["cases"]) == 10
    assert len(derived["documents"]) == len(derived["cases"]) == 2
    assert [case["oracle"] for case in transfer["cases"]] == values["questions-oracles.json"]["cases"]
    assert all(case["scope"]["page_start"] == case["scope"]["page_end"] == 0 for case in derived["cases"])
    assert all(case["oracle"]["scope"]["page_start"] == 2 for case in derived["cases"])
    assert all(case["repeats"] == 1 for case in transfer["cases"] + derived["cases"])
    assert before == {name: (base / name).read_bytes() for name in harness.MANIFEST_NAMES}
    with pytest.raises(ValueError, match="Unknown I5 split"):
        harness.transfer_dataset(base, "arbitrary")


def test_previously_consumed_dataset_keeps_questions_but_drops_extraction(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7 explicit development double")
    original = {"documents": [{"key": "D", "format": "pdf", "path": "source.pdf", "sha256": harness.prior.digest(source),
                              "extraction_path": "old.json", "extraction_sha256": "obsolete",
                              "extraction_provenance": "candidate-record", "extraction_status": "ready"}],
                "cases": [{"id": "Q", "document_key": "D", "question": "Fixed development question",
                           "oracle": {"fixed": True}, "scope": {"kind": "pages", "page_start": 2, "page_end": 2}}]}
    path = tmp_path / "inputs.json"
    before = write_json(path, original)
    fresh = harness.fresh_development_dataset(path)
    assert path.read_bytes() == before and fresh["cases"] == original["cases"]
    assert not any(key.startswith("extraction_") for key in fresh["documents"][0])
    assert fresh["documents"][0]["path"] == str(source)
    assert fresh["source_manifest_sha256"] == hashlib.sha256(before).hexdigest()
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Development original changed"):
        harness.fresh_development_dataset(path)


def test_duplicate_development_documents_are_rejected(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7 explicit development double")
    document = {"key": "D", "format": "pdf", "path": str(source), "sha256": harness.prior.digest(source)}
    path = tmp_path / "inputs.json"
    write_json(path, {"documents": [document, copy.deepcopy(document)], "cases": [{"id": "Q"}]})
    with pytest.raises(ValueError, match="unique"):
        harness.fresh_development_dataset(path)


def development_window_fixture(tmp_path):
    documents = []
    for key in ("D1", "D2", "D3"):
        path = tmp_path / (key + ".pdf")
        path.write_bytes(("%PDF-1.7 explicit non-rendered window double " + key).encode())
        documents.append({"key": key, "path": str(path), "sha256": harness.prior.digest(path), "format": "pdf",
                          "extraction_path": "obsolete.json", "extraction_sha256": "obsolete"})
    cases = [{"id": key, "document_key": document, "question": "Explicit diagnostic fixture",
              "scope": {"kind": "pages", "document_key": document, "page_start": page, "page_end": page},
              "oracle": {"frozen": True}}
             for key, document, page in (("A", "D1", 0), ("B", "D1", 1), ("C", "D2", 0),
                                         ("D", "D3", 0), ("E", "D3", 2))]
    path = tmp_path / "consumed-inputs.json"
    write_json(path, {"documents": documents, "cases": cases})
    return path


def test_diagnostic_windows_are_bounded_unions_of_original_scopes_not_rewritten_queries(tmp_path):
    path = development_window_fixture(tmp_path)
    before = path.read_bytes()
    frozen = json.loads(before)
    result = harness.development_window_dataset(path)
    assert result["diagnostic_only"] and result["cases"] == frozen["cases"]
    assert {spec["key"]: spec["diagnostic_window"] for spec in result["documents"]} == {
        "D1": {"page_start": 0, "page_end": 1}, "D2": {"page_start": 0, "page_end": 0},
        "D3": {"page_start": 0, "page_end": 2}}
    assert all(spec["sha256"] == original["sha256"] and spec["path"] == original["path"]
               for spec, original in zip(result["documents"], frozen["documents"], strict=True))
    assert all("extraction_path" not in spec for spec in result["documents"])
    assert path.read_bytes() == before


def test_diagnostic_case_selection_is_explicit_and_does_not_renumber_original_page(tmp_path):
    path = development_window_fixture(tmp_path)
    result = harness.development_window_dataset(path, ["E"])
    assert result["selected_case_ids"] == ["E"] and result["omitted_case_ids"] == ["A", "B", "C", "D"]
    assert result["documents"][0]["diagnostic_window"] == {"page_start": 2, "page_end": 2}
    assert result["cases"][0]["scope"]["page_start"] == result["cases"][0]["scope"]["page_end"] == 2
    assert len(result["documents"]) == 1 and result["documents"][0]["key"] == "D3"
    for selection in (["absent"], ["E", "E"]):
        with pytest.raises(ValueError, match="duplicate or absent"):
            harness.development_window_dataset(path, selection)


@pytest.mark.parametrize("mutation", ["reserved-transfer", "non-page", "mismatched-document", "bool-page", "too-wide"])
def test_diagnostic_scope_cannot_silently_expand_or_consume_reserved_i5(tmp_path, mutation):
    path = development_window_fixture(tmp_path)
    data = json.loads(path.read_text())
    if mutation == "reserved-transfer":
        data["heldout_receipt_sha256"] = harness.HELDOUT_RECEIPT_SHA256
    elif mutation == "non-page":
        data["cases"][0]["scope"] = {"kind": "documents"}
    elif mutation == "mismatched-document":
        data["cases"][0]["scope"]["document_key"] = "D2"
    elif mutation == "bool-page":
        data["cases"][0]["scope"]["page_start"] = False
    else:
        data["cases"][0]["scope"]["page_end"] = 9
    write_json(path, data)
    with pytest.raises(ValueError):
        harness.development_window_dataset(path)


def run_window_adapter_double(tmp_path, *, emitted_index=2, emitted_sha="a" * 64):
    """Run only the qualification envelope with an explicitly fake worker package."""
    checkout = tmp_path / "explicit-selected-checkout-double"
    package = checkout / "services/ingestion"
    package.mkdir(parents=True)
    for path in (checkout / "services/__init__.py", package / "__init__.py"):
        path.write_text("")
    (package / "checkpoint.py").write_text(
        "import json\nfrom pathlib import Path\ndef atomic_json(path, data):\n"
        "    Path(path).write_text(json.dumps(data))\n")
    (package / "pipeline.py").write_text(
        "def stitch_structure(pages):\n"
        "    return ([{'selected_revision_stitch': True, 'first_physical_index': pages[0]['page_index']}], [])\n")
    raw_result = {"ok": True, "result": {"sha256": emitted_sha, "page_count": 7, "page_start": 2, "page_end": 2,
                                         "pages": [{"page_index": emitted_index, "ocr_used": False,
                                                    "extraction_state": "ready", "unresolved_regions": [], "blocks": []}],
                                         "sections": [], "tables": [], "warnings": [], "complete": True}}
    (package / "worker.py").write_text(
        "import json\nimport sys\nfrom pathlib import Path\ndef main():\n"
        "    output=Path(sys.argv[sys.argv.index('--result')+1])\n"
        f"    output.write_text(json.dumps({raw_result!r}))\n"
        "    return 0\n")
    request, result = tmp_path / "request.json", tmp_path / "result.json"
    write_json(request, {"page_start": 2, "page_end": 2, "expected_source_sha256": "a" * 64})
    env = {**os.environ, "PYTHONPATH": str(checkout)}
    process = subprocess.run([sys.executable, "-c", harness.WINDOW_WORKER_ADAPTER, str(request), str(result)],
                             cwd=checkout, env=env, capture_output=True, text=True, timeout=10, check=False)
    return process, result, raw_result


def test_window_envelope_retains_raw_worker_and_selected_revision_stitch_without_full_claim(tmp_path):
    process, result_path, expected_raw = run_window_adapter_double(tmp_path)
    assert process.returncode == 0, process.stderr
    raw_path = result_path.with_suffix(".raw-window.json")
    assert json.loads(raw_path.read_text()) == expected_raw
    extraction = json.loads(result_path.read_text())["result"]
    assert extraction["status"] == "ready_partial" and extraction["diagnostic_only"]
    assert extraction["pages"][0]["page_index"] == 2 and extraction["page_count"] == 7
    assert extraction["coverage"]["processed"] == 1 and extraction["coverage"]["omitted_by_diagnostic_scope"] == 6
    assert extraction["sections"] == [{"selected_revision_stitch": True, "first_physical_index": 2}]
    assert extraction["diagnostic_raw_worker_sha256"] == harness.prior.digest(raw_path)
    assert any(item["code"] == "qualification_targeted_diagnostic" for item in extraction["warnings"])


@pytest.mark.parametrize("kwargs", [{"emitted_index": 0}, {"emitted_sha": "b" * 64}])
def test_window_envelope_refuses_renumbered_page_or_wrong_original_but_keeps_raw_failure(tmp_path, kwargs):
    process, result_path, expected_raw = run_window_adapter_double(tmp_path, **kwargs)
    assert process.returncode != 0 and "source binding" in process.stderr
    assert not result_path.exists()
    assert json.loads(result_path.with_suffix(".raw-window.json").read_text()) == expected_raw
