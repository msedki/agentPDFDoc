"""Evaluation mathematics, immutable gold checks and report locations; no engine call (the local API is an explicit httpx.MockTransport double)."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from services.api.qualification import evaluate_question, span_covered, summary, verify_annotations, wilson


def evidence():
    span = {"version_id": "v1", "extraction_revision_id": "r1", "generation_id": "g1", "block_id": "b1", "source_text_hash": "hash1",
            "page_index": 0, "start_offset": 1, "end_offset": 4, "text": "😀éV"}
    block = {"id": "b1", "extraction_revision_id": "r1", "source_text_hash": "hash1", "page_index": 0,
             "start_offset": 0, "end_offset": 5, "text": "A😀éVZ"}
    source = {"document_id": "d1", "version_id": "v1", "extraction_revision_id": "r1", "generation_id": "g1", "chunk_id": "c1", "text": block["text"], "blocks": [block]}
    return span, source


def test_api_qualification_codepoint_coverage_requires_revision_hash_and_exact_substring():
    span, source = evidence()
    assert span_covered(span, [source])
    for key, wrong in [("version_id", "v2"), ("extraction_revision_id", "r2"), ("generation_id", "g2")]:
        assert not span_covered(span, [{**source, key: wrong}])
    corrupted = deepcopy(source)
    corrupted["blocks"][0]["source_text_hash"] = "other"
    assert not span_covered(span, [corrupted])
    corrupted["blocks"][0]["source_text_hash"] = "hash1"
    corrupted["blocks"][0]["text"] = "A😀X V"
    assert not span_covered(span, [corrupted])
    left, right = deepcopy(source), deepcopy(source)
    left["blocks"][0].update(end_offset=3, text="A😀é")
    right["blocks"][0].update(start_offset=3, text="VZ")
    assert span_covered(span, [left, right])
    right["blocks"][0].update(start_offset=4, text="Z")
    assert not span_covered(span, [left, right])


def test_api_qualification_annotation_binding_cannot_change_frozen_fact():
    source = {"questions": [{"id": "dev-1", "question": "Tension ?", "expected_answer": "72 V", "expected_units": [{"document_key": "fixture", "file_sha256": "source", "required_texts": ["72 V"], "version_id": None}]}]}
    resolved = deepcopy(source)
    resolved["questions"][0].update(annotation_state="RESOLVED", scope_resolved={"kind": "documents", "documentIds": ["d1"]})
    resolved["questions"][0]["expected_units"][0].update(version_id="v1", resolved_spans=[{"text": "72 V"}], resolution_status="RESOLVED")
    verify_annotations(source, resolved)
    resolved["questions"][0]["expected_units"][0]["required_texts"] = ["110 V"]
    with pytest.raises(ValueError, match="frozen question"):
        verify_annotations(source, resolved)


def test_api_qualification_checks_requested_scope_even_if_runtime_snapshot_is_broad():
    span, source = evidence()
    question = {"id": "dev-1", "answerable": True, "category": "technical", "scope_resolved": {"kind": "documents", "documentIds": ["d1"]},
                "versions_snapshot": [{"document_id": "d1", "version_id": "v1", "generation_id": "g1", "extraction_revision_id": "r1"}], "expected_units": [{"resolved_spans": [span]}]}
    snapshot = {"generations": ["g1", "g2"], "versions": {"g1": "v1", "g2": "v2"}, "documents": {"g1": "d1", "g2": "d2"}}
    extra = {**deepcopy(source), "document_id": "d2", "version_id": "v2", "generation_id": "g2"}
    row = evaluate_question(question, {"state": "context_ready", "scope_snapshot": snapshot, "retrieval_top10": [source, extra], "context_sources": [source]})
    assert row["top10_covered_units"] == row["context_covered_units"] == 1
    assert row["scope_leakage_count"] == 1 and row["scope_leaks"][0]["reason"] == "outside_requested_document_scope"


def test_api_qualification_denominators_and_wilson_preserve_incomplete_evidence():
    metrics = summary([{"status": "UNRESOLVED", "category": "tables"}, {"status": "ERROR", "category": "tables"}, {"status": "EVALUATED", "answerable": True, "category": "technical",
                       "expected_unit_count": 2, "top5_covered_units": 1, "top10_covered_units": 1, "context_covered_units": 0, "scope_leakage_count": 0, "reciprocal_rank": 1}])
    assert metrics["requested_questions"] == 3 and metrics["evaluated_questions"] == 1
    assert metrics["recall_at_10"]["rate"] == .5 and metrics["evidence_coverage_at_context"]["rate"] == 0
    assert metrics["generation_metrics"]["correct_abstention"] == "NOT_RUN"
    assert wilson(100, 100)["interval_95"][0] == pytest.approx(.9630065018)
    assert wilson(0, 0)["rate"] is None


def test_api_qualification_mrr_requires_a_complete_evidence_unit_and_preserves_multiunit_failure():
    span, source = evidence()
    irrelevant = deepcopy(source)
    irrelevant["blocks"][0]["source_text_hash"] = "wrong"
    second_span = {**span, "block_id": "b2", "source_text_hash": "hash2", "text": "110"}
    question = {"id": "dev-table", "answerable": True, "category": "tables", "scope_resolved": {"kind": "documents", "documentIds": ["d1"]},
                "expected_units": [{"resolved_spans": [span]}, {"resolved_spans": [second_span]}]}
    response = {"state": "context_ready", "scope_snapshot": {"generations": ["g1"], "versions": {"g1": "v1"}, "documents": {"g1": "d1"}},
                "retrieval_top10": [irrelevant] * 5 + [source], "context_sources": [source]}
    row = evaluate_question(question, response)
    assert row["first_evidence_rank"] == 6 and row["reciprocal_rank"] == pytest.approx(1 / 6)
    assert row["top5_covered_units"] == 0 and row["top10_covered_units"] == row["context_covered_units"] == 1
    metrics = summary([row, {"status": "UNRESOLVED", "category": "technical"}])
    assert metrics["recall_at_5"]["rate"] == 0 and metrics["recall_at_10"]["rate"] == .5
    assert metrics["all_units_in_context_questions"]["successes"] == 0
    assert metrics["mrr_at_10"]["mean"] == pytest.approx(1 / 6)
    assert metrics["by_category"]["tables"]["evaluated_questions"] == 1
    assert metrics["by_category"]["technical"]["unresolved_questions"] == 1
    assert metrics["by_category"]["technical"]["recall_at_10"]["rate"] is None
    question["expected_units"] = [{"resolved_spans": [span, second_span]}]
    partial_unit = evaluate_question(question, response)
    assert partial_unit["reciprocal_rank"] == 0 and partial_unit["first_evidence_rank"] is None


def test_api_qualification_micro_aggregate_and_per_question_mean_have_distinct_denominators():
    rows = [{"status": "EVALUATED", "category": "comparison", "answerable": True, "expected_unit_count": 4, "top5_covered_units": 2, "top10_covered_units": 3,
             "context_covered_units": 2, "scope_leakage_count": 0, "reciprocal_rank": .5},
            {"status": "EVALUATED", "category": "factual", "answerable": True, "expected_unit_count": 1, "top5_covered_units": 1, "top10_covered_units": 1,
             "context_covered_units": 1, "scope_leakage_count": 0, "reciprocal_rank": 1}]
    metrics = summary(rows)
    assert metrics["recall_at_10"]["expected_units"] == 5 and metrics["recall_at_10"]["rate"] == .8
    assert metrics["per_question_means"]["recall_at_10"]["mean"] == .875
    assert metrics["per_question_means"]["evidence_coverage_at_context"]["mean"] == .75
    assert metrics["mrr_at_10"]["mean"] == .75 and metrics["mrr_at_10"]["denominator_questions"] == 2


def test_api_qualification_summary_reports_by_language_with_own_denominators():
    span, source = evidence()
    question = {"id": "dev-en", "answerable": True, "category": "factual_fr_en", "language": "en", "scope_resolved": {"kind": "documents", "documentIds": ["d1"]},
                "expected_units": [{"resolved_spans": [span]}]}
    row = evaluate_question(question, {"state": "context_ready", "scope_snapshot": {"generations": ["g1"], "versions": {"g1": "v1"}, "documents": {"g1": "d1"}},
                                       "retrieval_top10": [source], "context_sources": [source]})
    assert row["language"] == "en"
    rows = [row, {"status": "UNRESOLVED", "category": "factual_fr_en", "language": "fr"}, {"status": "ERROR", "category": "tables", "language": "fr"}]
    metrics = summary(rows)
    assert sorted(metrics["by_language"]) == ["en", "fr"]
    assert metrics["by_language"]["en"]["recall_at_10"]["rate"] == 1 and metrics["by_language"]["en"]["evaluated_questions"] == 1
    assert metrics["by_language"]["fr"]["requested_questions"] == 2 and metrics["by_language"]["fr"]["evaluated_questions"] == 0
    assert metrics["by_language"]["fr"]["recall_at_10"]["rate"] is None and "by_language" not in metrics["by_language"]["fr"]
    assert "by_language" in summary([row]) and summary([{"status": "UNRESOLVED", "category": "x"}])["by_language"] == {}


# --- Emplacement des rapports : rapport complet hors Git, résumé versionné, sceau du final ---------------------------
# API locale simulée par httpx.MockTransport (double explicite) ; racine du dépôt temporaire, `.runtime` en lien.
REPOSITORY = Path(__file__).resolve().parents[2]
BACKEND = "RAG_Local_Agents/reports/backend"

def evaluation_repository(tmp_path, monkeypatch, split="development"):
    import services.api.qualification as qualification

    root, outside = tmp_path / "depot", tmp_path / "volume" / "runtime"
    (root / "RAG_Local_Agents/reports/backend").mkdir(parents=True)
    (outside / "qa").mkdir(parents=True)
    try:
        (root / ".runtime").symlink_to(outside, target_is_directory=True)
    except OSError:  # Windows sans droit de créer un lien : dossier réel, même règle
        (root / ".runtime").mkdir()
        (root / ".runtime" / "qa").mkdir()
    monkeypatch.setattr(qualification, "ROOT", root, raising=False)
    monkeypatch.setenv("RAG_CONTROL_TOKEN", "jeton-de-test")
    span, source = evidence()
    frozen = {"id": f"{split}-1", "split": split, "question": "Tension ?", "category": "factual_fr_en", "language": "fr", "answerable": True,
              "expected_units": [{"document_key": "fixture", "required_texts": ["😀éV"]}]}
    resolved = deepcopy(frozen)
    resolved.update(annotation_state="RESOLVED", scope_resolved={"kind": "documents", "documentIds": ["d1"]})
    resolved["expected_units"][0].update(version_id="v1", resolved_spans=[span], resolution_status="RESOLVED")
    files = {name: tmp_path / f"{name}.json" for name in ("source", "resolved", "freeze")}
    files["source"].write_text(json.dumps({"questions": [frozen]}, ensure_ascii=False), encoding="utf-8")
    files["resolved"].write_text(json.dumps({"questions": [resolved]}, ensure_ascii=False), encoding="utf-8")
    files["freeze"].write_text(json.dumps({"canonical_sha256": qualification.canonical_sha({"questions": [frozen]}), "questions": 1}), encoding="utf-8")
    identity = {"profile_sha256": "p" * 64, "selector_sha256": "s" * 64, "dense_identity": {"model": "e5"}, "llm_tokenizer_identity": {"model": "qwen"}, "qdrant_collection": "c"}
    calls = []

    def api(request):
        calls.append(request.url.path)
        if request.url.path == "/api/v1/diagnostics":
            return httpx.Response(200, json={**identity, "resources": {"data_dir": "/home/poste/donnees"}})
        return httpx.Response(200, json={**identity, "model_called": False, "state": "context_ready", "retrieval_top10": [source], "context_sources": [source],
                                         "scope_snapshot": {"generations": ["g1"], "versions": {"g1": "v1"}, "documents": {"g1": "d1"}}})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **options: real_client(transport=httpx.MockTransport(api), **options))
    return qualification, root, files, identity, calls


def run_cli(monkeypatch, qualification, files, *arguments, split="development"):
    argv = ["qualification", "--dataset", str(files["resolved"]), "--source-dataset", str(files["source"]), "--split", split,
            "--base-url", "http://127.0.0.1:9", *arguments]
    if split == "final":
        argv += ["--freeze", str(files["freeze"])]
    monkeypatch.setattr(sys, "argv", argv)
    qualification.main()


def test_full_report_kept_outside_git_with_a_versioned_summary(tmp_path, monkeypatch):
    qualification, root, files, identity, calls = evaluation_repository(tmp_path, monkeypatch)
    full = root / ".runtime/qa/j8-linux/development-retrieval-full.json"
    summary_path = root / "RAG_Local_Agents/reports/backend/development-retrieval-summary.json"
    run_cli(monkeypatch, qualification, files, "--output", str(full), "--summary", str(summary_path))
    assert calls == ["/api/v1/diagnostics", "/api/v1/admin/evaluation/context"]
    report = json.loads(full.read_text(encoding="utf-8"))
    assert full.resolve().is_relative_to((tmp_path / "volume").resolve()) or not (root / ".runtime").is_symlink()
    assert "response" in report["questions"][0] and "diagnostics" in report
    written = json.loads(summary_path.read_text(encoding="utf-8"))
    # Même forme que le résumé versionné du 1er octobre : référence du rapport complet, puis le rapport allégé.
    assert list(written)[:2] == ["full_report", "date_utc"]
    assert written["full_report"]["path"] == ".runtime/qa/j8-linux/development-retrieval-full.json"
    assert written["full_report"]["bytes"] == full.stat().st_size
    assert written["full_report"]["sha256"] == hashlib.sha256(full.read_bytes()).hexdigest()
    assert "hors Git" in written["full_report"]["note"]
    assert "diagnostics" not in written and "/home/poste" not in summary_path.read_text(encoding="utf-8")
    assert written["metrics"] == report["metrics"] and written["identity"] == identity and written["status"] == report["status"]
    assert [row["question_id"] for row in written["questions"]] == ["development-1"]
    assert written["questions"][0] == {key: value for key, value in report["questions"][0].items() if key != "response"}
    assert "😀éV" not in summary_path.read_text(encoding="utf-8")  # texte du document absent du résumé
    delivered = json.loads((REPOSITORY / BACKEND / "2026-10-01-development-retrieval-summary.json").read_text(encoding="utf-8"))
    assert set(written) == set(delivered) and set(written["full_report"]) == set(delivered["full_report"])
    # Le résumé garde en plus les indices d'unités couvertes et le détail des fuites : quelques octets par question.
    assert set(delivered["questions"][0]) <= set(written["questions"][0])
    assert set(written["questions"][0]) - set(delivered["questions"][0]) == {"top5_covered_unit_indices", "top10_covered_unit_indices", "context_covered_unit_indices", "scope_leaks"}


def test_backend_output_unchanged_and_misplaced_outputs_refused_before_any_call(tmp_path, monkeypatch):
    qualification, root, files, identity, calls = evaluation_repository(tmp_path, monkeypatch)
    backend = root / "RAG_Local_Agents/reports/backend"
    run_cli(monkeypatch, qualification, files, "--output", str(backend / "development-retrieval.json"))
    assert "response" in json.loads((backend / "development-retrieval.json").read_text(encoding="utf-8"))["questions"][0]
    calls.clear()
    (backend / "existant.json").write_text("{}", encoding="utf-8")
    for arguments in (["--output", str(root / "autre/rapport.json")],
                      ["--output", str(root / ".runtime/data/rapport.json")],
                      ["--output", str(root / ".runtime/qa/rapport.json"), "--summary", str(root / ".runtime/qa/resume.json")],
                      ["--output", str(root / ".runtime/qa/rapport.json"), "--summary", str(backend / "existant.json")],
                      ["--output", str(backend / "complet.json"), "--summary", str(backend / "resume.json")],
                      ["--output", str(root / ".runtime/qa/rapport.json"), "--limit", "0"]):
        with pytest.raises(SystemExit) as refused:
            run_cli(monkeypatch, qualification, files, *arguments)
        assert refused.value.code == 2, arguments
    assert calls == [] and not (root / ".runtime/qa/rapport.json").exists() and not (backend / "complet.json").exists()


def test_final_seal_stays_in_the_versioned_folder_when_the_full_report_is_outside_git(tmp_path, monkeypatch, capsys):
    qualification, root, files, identity, calls = evaluation_repository(tmp_path, monkeypatch, split="final")
    backend = root / "RAG_Local_Agents/reports/backend"
    run_cli(monkeypatch, qualification, files, "--output", str(root / ".runtime/qa/final-1.json"), split="final")
    receipt = backend / "final-retrieval-identity-receipt.json"
    assert json.loads(receipt.read_text(encoding="utf-8"))["identity"] == identity
    assert not (root / ".runtime/qa/final-retrieval-identity-receipt.json").exists()
    # Une autre identité ne contourne pas le sceau en changeant de dossier de sortie.
    sealed = json.loads(receipt.read_text(encoding="utf-8"))
    receipt.write_text(json.dumps({**sealed, "identity_sha256": "0" * 64}), encoding="utf-8")
    (root / ".runtime/qa/autre").mkdir()
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, qualification, files, "--output", str(root / ".runtime/qa/autre/final-2.json"), split="final")
    assert not (root / ".runtime/qa/autre/final-2.json").exists()
    assert "Final identity already sealed; tuning against held-out results is forbidden" in capsys.readouterr().err
    # Revue J8 : un sous-dossier du dossier versionné ne contourne pas non plus le sceau.
    (backend / "autre").mkdir()
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, qualification, files, "--output", str(backend / "autre/final-3.json"), split="final")
    assert not (backend / "autre/final-3.json").exists() and not (backend / "autre/final-retrieval-identity-receipt.json").exists()
