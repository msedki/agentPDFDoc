"""Evaluation mathematics and immutable gold checks; no HTTP engine calls."""
from copy import deepcopy

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
