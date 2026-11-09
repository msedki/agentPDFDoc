"""Harnais I4 seulement : aucune extraction native, modèle ni connexion réseau."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from tools.qualification import prepare_production_i4 as preparer
from tools.qualification import production_i4_http as transport
from tools.qualification import run_grounded_native as launcher


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return preparer.digest(path)


def development_double(tmp_path, monkeypatch):
    documents, expected = [], {}
    for key in ("ina226", "tmp117"):
        source = tmp_path / (key + ".pdf")
        source.write_bytes(("%PDF-1.7 explicit fixture, never extracted " + key).encode())
        expected[key] = preparer.digest(source)
        documents.append({"key": key, "format": "pdf", "path": str(source), "sha256": expected[key],
                          "extraction_path": "must-not-be-reused.json", "extraction_sha256": "old-hash",
                          "allow_partial": True})
    monkeypatch.setattr(preparer, "DEVELOPMENT_PDF_SHA256", expected)
    cases = [{"id": "N_" + key, "document_key": key, "question": "frozen explicit question double",
              "scope": {"kind": "pages", "document_key": key, "page_start": 0, "page_end": 0},
              "oracle": {"fixed": True}} for key in expected]
    path = tmp_path / "inputs.json"
    write_json(path, {"documents": documents, "cases": cases})
    return path, cases


def test_development_pdf_discards_obsolete_extraction_without_changing_page_zero_or_oracles(tmp_path, monkeypatch):
    path, cases = development_double(tmp_path, monkeypatch)
    before = path.read_bytes()
    result = preparer.development_pdf_dataset(path)
    assert result["cases"] == cases and path.read_bytes() == before
    assert all("extraction_path" not in spec and "extraction_sha256" not in spec for spec in result["documents"])
    assert all(not spec["reused"] for spec in result["superseded_extractions"])
    assert result["source_manifest_sha256"] == preparer.digest(path)


def test_development_pdf_refuses_changed_original_and_wrong_page_before_worker(tmp_path, monkeypatch):
    path, _ = development_double(tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    data["cases"][0]["scope"]["page_start"] = 1
    write_json(path, data)
    with pytest.raises(ValueError, match="index zéro"):
        preparer.development_pdf_dataset(path)
    data["cases"][0]["scope"]["page_start"] = 0
    write_json(path, data)
    (tmp_path / "ina226.pdf").write_bytes(b"changed PDF")
    with pytest.raises(ValueError, match="différent du verrou"):
        preparer.development_pdf_dataset(path)


def test_heldout_changed_receipt_is_rejected_without_reading_oracles(tmp_path):
    (tmp_path / "freeze-receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="reçu de gel"):
        preparer.frozen_inputs(tmp_path)
    assert not (tmp_path / "questions-oracles.json").exists()


def test_output_and_input_paths_are_not_silently_overwritten_or_escaped(tmp_path):
    path = tmp_path / "result.json"
    preparer.save_new(path, {"first": True})
    with pytest.raises(FileExistsError):
        preparer.save_new(path, {"second": True})
    child = tmp_path / "child"
    child.mkdir()
    with pytest.raises(ValueError, match="sort du dossier"):
        preparer.inside(child, "../result.json")
    assert json.loads(path.read_text()) == {"first": True}


def test_transport_dispatch_accepts_only_fixed_harnesses():
    assert launcher.measurement_script("http").name == "production_i4_http.py"
    assert launcher.measurement_script("direct").name == "revision_campaign.py"
    with pytest.raises(ValueError, match="inconnu"):
        launcher.measurement_script("../untrusted.py")


def test_sse_parser_preserves_private_event_names_and_multiline_data():
    row = transport.parse_sse_frame([": heartbeat", "id: 7", "event: structured_delta", 'data: {"text":',
                                     'data: "private"}'])
    assert row == {"id": 7, "type": "structured_delta", "data": {"text": "private"}}
    assert transport.parse_sse_frame([": heartbeat"]) is None


def publication_fixture():
    identity = {"name": "qwen3-4b-enhanced:q4km", "digest": "a" * 64, "manifest_sha256": "b" * 64}
    answer = "A literal source quotation."
    run = {"state": "done", "answer": answer, "metrics": {"model_called": True}}
    public = [{"id": 2, "type": "delta", "data": {"text": answer}, "arrived_utc": "2026-11-08T17:00:02+00:00"},
              {"id": 3, "type": "done", "data": {}}]
    stored = [{"id": 2, "created_at": "2026-11-08T17:00:01+00:00", "data_json": json.dumps({"text": answer})}]
    trace = [{"phase": "answer.support_validation", "utc": "2026-11-08T17:00:00+00:00", "data": {
        "status": "passed", "unsupported_characters": 0, "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()}},
        {"phase": "llm.request", "data": {"body": {"model": identity["name"]},
            "verified_model_identity": {"digest": identity["digest"], "manifest_sha256": identity["manifest_sha256"]}}},
        {"phase": "llm.response", "data": {"received_done": True}}]
    return run, public, stored, trace, identity


def test_publication_requires_guard_before_observed_bytes_and_exact_answer_hash():
    original = publication_fixture()
    assert transport.publication_checks(*original)["passed"]
    for mutation in ("late-guard", "private-event", "different-answer", "wrong-4b-digest", "no-provider-done"):
        run, public, stored, trace, identity = copy.deepcopy(original)
        if mutation == "late-guard":
            trace[0]["utc"] = "2026-11-08T17:00:03+00:00"
        elif mutation == "private-event":
            public.insert(0, {"id": 1, "type": "structured_delta", "data": {"text": "private"}})
        elif mutation == "different-answer":
            trace[0]["data"]["answer_sha256"] = "c" * 64
        elif mutation == "wrong-4b-digest":
            trace[1]["data"]["verified_model_identity"]["digest"] = "d" * 64
        else:
            trace.pop()
        assert not transport.publication_checks(run, public, stored, trace, identity)["passed"], mutation


def test_http_fixture_versions_are_distinct_and_initial_original_is_preserved(tmp_path):
    output = tmp_path / "frozen-http"
    preparer.prepare_http(output)
    dataset = json.loads((output / "inputs.json").read_text())
    initial = dataset["documents"][0]
    replacement = dataset["replacement"]
    assert initial["relative_path"] == replacement["relative_path"]
    assert initial["sha256"] != replacement["sha256"]
    assert preparer.digest(output / "A.docx") == initial["sha256"]
    assert len(dataset["cases"]) == 1 and dataset["acceptance"]["actual_model_call_required"]
