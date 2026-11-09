"""Recipe/provenance checks; the extraction objects below are explicit doubles."""

import hashlib
import json
from pathlib import Path

import pytest

from services.api.answer_contract import AnswerContract
from services.api.schemas import QueryRequest
from services.api.structured_answer import Catalogue
from tools.qualification import prepare_relations_native as native
from tools.qualification.relations_benchmark import classify
from tools.qualification.support_benchmark import CharacterCounterDouble

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/support_i6_dev.json"


def extraction_double(text, sha, *, version_id="version", revision_id="revision"):
    box = [40.0, 500.0, 500.0, 520.0]
    return {"sha256": sha, "version_id": version_id, "extraction_revision_id": revision_id,
            "status": "ready", "parser_complete": True,
            "pages": [{"page_index": 0, "width": 840.0, "height": 595.0, "source_sha256": sha,
                       "ocr_used": False, "blocks": [{"id": "block", "raw_text": text, "page_index": 0,
                       "version_id": version_id, "extraction_revision_id": revision_id,
                       "source_text_hash": hashlib.sha256(text.encode()).hexdigest(), "bbox": box,
                       "precision": "block", "spans": [{"start_offset": 0, "end_offset": len(text), "bbox": box}],
                       "metadata": {"extraction_method": "native", "ocr_used": False}}]}]}


def test_recipe_preserves_document_grouping_scope_and_unchanged_gold():
    recipe = native.build_recipe(FIXTURE)
    original_cases = {case["id"]: case for case in json.loads(FIXTURE.read_text())["cases"]}
    documents = {document["key"]: document for document in recipe["documents"]}
    cases = {case["id"]: case for case in recipe["cases"]}
    assert len(documents) == 23
    assert len(cases) == 18
    assert sum(document["format"] == "pdf" for document in documents.values()) == 6
    assert [len(documents[key]["paragraphs"]) for key in cases["N_I6D35"]["scope"]["document_keys"]] == [2]
    assert [len(documents[key]["paragraphs"]) for key in cases["N_I6D38"]["scope"]["document_keys"]] == [2, 2]
    assert [len(documents[key]["paragraphs"]) for key in cases["N_I6D45"]["scope"]["document_keys"]] == [2, 1]
    for case in cases.values():
        assert case["document_key"] in case["scope"]["document_keys"]
        if case["id"] in {"N17", "N18"}:
            assert case["annotation"]["requires_actual_4b_call"] is True
            continue
        original = original_cases[case["annotation"]["source_fixture_case"]]
        assert case["question"] == original["question"]
        assert case["annotation"]["expected"] == original["expected"]
        for binding in case["annotation"]["source_bindings"]:
            doc = documents[binding["document_key"]]
            assert doc["fixture_document_id"] == binding["fixture_document_id"]
            assert doc["paragraphs"][binding["paragraph_index"]] == binding["text"]


def test_every_native_case_is_a_valid_api_request_without_changing_subject_comparison():
    recipe = native.build_recipe(FIXTURE)
    original = {case["id"]: case for case in json.loads(FIXTURE.read_text())["cases"]}
    changed_modes = []
    for case in recipe["cases"]:
        request = QueryRequest.model_validate({"question": case["question"], "mode": case["mode"],
            "scope": {"kind": "documents", "documentIds": case["scope"]["document_keys"]}})
        fixture_case = case["annotation"].get("source_fixture_case")
        if fixture_case and request.mode != original[fixture_case]["mode"]:
            changed_modes.append(case["id"])
            contract = AnswerContract(request.question, request.mode)
            assert contract.comparison_requested and contract.comparison_axis == "subjects"
            assert contract.subjects == ("SV6135", "SV6135B")
            assert case["annotation"]["expected"] == original[fixture_case]["expected"]
            reference_case = original[fixture_case]
            references = [{**source, "document_name": source["document_id"]} for source in reference_case["sources"]]
            required = tuple(reference_case["scope"]["document_ids"])
            cat = Catalogue(request.mode, references, contract, required_documents=required)
            plan = cat.validate(json.dumps({"references": [source["id"] for source in references], "comparisons": []}))
            result = cat.render(plan, CharacterCounterDouble(), 5000, required)
            assert classify(reference_case, result)["passed"]
    assert changed_modes == ["N_I6D35"]


def test_single_document_comparison_cannot_silently_become_an_unrelated_question():
    with pytest.raises(ValueError, match="explicitly compare source subjects"):
        native.api_mode("What is the supply voltage of SV6135?", "comparison", ["one"])


def test_comparison_document_limit_is_not_relaxed_by_the_preparer():
    with pytest.raises(ValueError, match="deux à quatre documents"):
        native.api_mode("Compare SV6135 and SV6135B.", "comparison", ["a", "b", "c", "d", "e"])


def test_changed_fixture_is_rejected_before_any_materialization(tmp_path):
    altered = tmp_path / "altered.json"
    altered.write_bytes(FIXTURE.read_bytes() + b"\n")
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError, match="frozen I6"):
        native.prepare(altered, destination)
    assert not destination.exists()


def test_existing_output_is_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        native.prepare(FIXTURE, tmp_path)


def test_unicode_offsets_and_block_precision_are_preserved(tmp_path):
    original = tmp_path / "source.pdf"
    original.write_bytes(b"explicit-original-double")
    text = "Le courant est de 19 mA à l’exception de TA = 46 °C."
    sha = native.digest(original)
    check = native.extraction_check({"key": "x", "paragraphs": [text]}, original, sha, extraction_double(text, sha))
    assert check["passed"]
    assert check["witnesses"][0]["end_offset"] == len(text)
    assert check["witnesses"][0]["precision"] == "block"


@pytest.mark.parametrize("fault", ["literal", "source_hash", "text_hash", "offset", "bbox", "version", "ocr", "partial"])
def test_corrupt_pdf_provenance_never_qualifies(fault, tmp_path):
    original = tmp_path / "source.pdf"
    original.write_bytes(b"explicit-original-double")
    text, sha = "Current: 19 mA.", native.digest(original)
    extracted = extraction_double(text, sha)
    page, block = extracted["pages"][0], extracted["pages"][0]["blocks"][0]
    if fault == "literal":
        block["raw_text"] = "Current: 18 mA."
    elif fault == "source_hash":
        extracted["sha256"] = "wrong"
    elif fault == "text_hash":
        block["source_text_hash"] = "wrong"
    elif fault == "offset":
        block["spans"][0]["end_offset"] -= 1
    elif fault == "bbox":
        block["bbox"][2] = page["width"] + 1
    elif fault == "version":
        block["version_id"] = "another-version"
    elif fault == "ocr":
        page["ocr_used"] = True
    elif fault == "partial":
        extracted["status"] = "ready_partial"
    check = native.extraction_check({"key": "x", "paragraphs": [text]}, original, sha, extracted)
    assert not check["passed"]


def test_failed_extraction_keeps_recipe_and_diagnostic_without_ready_inputs(monkeypatch, tmp_path):
    def failed_extraction(*args):
        raise ValueError("explicit extraction failure double")

    monkeypatch.setattr(native, "extract_pdf", failed_extraction)
    destination = tmp_path / "failed"
    with pytest.raises(ValueError, match="explicit extraction failure double"):
        native.prepare(FIXTURE, destination)
    assert (destination / "recipe.json").exists()
    assert not (destination / "inputs.json").exists()
    failure = json.loads((destination / "preparation-failure.json").read_text())
    assert failure["inputs_ready"] is False
    assert failure["model_inference"] == "NOT_RUN"
