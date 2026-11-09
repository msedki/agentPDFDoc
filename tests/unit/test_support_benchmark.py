"""The evaluation harness rejects corrupted labels and misleading summaries.

These tests exercise the measurement code, not another native RAG campaign.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

from tools.qualification.support_benchmark import (
    apply_ablation,
    classify,
    ensure_disjoint,
    finish_trials,
    load_fixture,
    summarize,
)


def example(expected=True):
    text = "The nominal voltage is 4 V."
    return {"id": "E01", "split": "development", "rationale": "Explicit equality.",
            "expected": {"exact_support": expected, "comparison": None},
            "sources": [{"id": "R001", "text": text, "document_family": "family-a",
                         "annotation_span": {"start": 0, "end": len(text), "text": text}}]}


def fixture(tmp_path, case=None):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"schema_version": 1, "split": "development", "cases": [case or example()]}))
    return path


def assessment(status="covered", facts=True, covered=True, agreement=None):
    return {"status": status, "matched_relations": [{"reference_id": "R001"}] if facts else [],
            "obligations": [{"covered": covered}],
            "comparisons": [{"numeric_agreement": agreement}] if agreement else []}


def test_fixture_requires_exact_codepoint_span(tmp_path):
    case = example()
    case["sources"][0]["annotation_span"]["end"] -= 1
    with pytest.raises(ValueError, match="offsets"):
        load_fixture(fixture(tmp_path, case))


@pytest.mark.parametrize("invalid", ["true", 1, None])
def test_nonboolean_or_missing_annotation_is_not_coerced(tmp_path, invalid):
    case = example(invalid)
    with pytest.raises(ValueError, match="annotation"):
        load_fixture(fixture(tmp_path, case))


def test_duplicate_cases_do_not_inflate_denominator(tmp_path):
    path = fixture(tmp_path)
    data = json.loads(path.read_text())
    data["cases"] *= 2
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicate case"):
        load_fixture(path)


def test_split_leakage_is_rejected_by_family_or_identical_text(tmp_path):
    first = load_fixture(fixture(tmp_path))
    second = copy.deepcopy(first)
    with pytest.raises(ValueError, match="family"):
        ensure_disjoint(first, second)
    second["document_families"] = ["different-family"]
    with pytest.raises(ValueError, match="Identical source"):
        ensure_disjoint(first, second)
    second["cases"][0]["sources"][0]["text"] = "A wholly different statement."
    ensure_disjoint(first, second)


@pytest.mark.parametrize("state", [assessment(facts=False), assessment(covered=False), assessment("partial")])
def test_covered_label_without_complete_actual_support_is_not_accepted(state):
    observed = classify(example(), state, "The nominal voltage is 4 V.")
    assert observed["exact_support_accepted"] is False
    assert observed["exact_support_correct"] is False


def test_literal_quote_fidelity_is_not_exact_semantic_support():
    case = example(False)
    result = classify(case, assessment(), case["sources"][0]["text"])
    assert result["all_source_literals_retained"] is True
    assert result["exact_support_accepted"] is True
    assert result["exact_support_correct"] is False


def test_unsupported_scalar_equality_rejected_even_with_partial_status():
    case = example(False)
    case["expected"]["comparison"] = "forbidden"
    result = classify(case, assessment("partial", agreement="equal"), "")
    assert result["exact_support_correct"] is True
    assert result["comparison_correct"] is False
    assert result["passed"] is False


def test_bound_label_does_not_forbid_valid_difference_reasoning():
    case = example(False)
    case["expected"]["comparison"] = "forbidden"
    assert classify(case, assessment("partial", agreement="different"), "")["comparison_correct"] is True


@pytest.mark.parametrize("agreement", [None, "different"])
def test_positive_equality_requires_actual_comparison(agreement):
    case = example()
    case["expected"]["comparison"] = "equal"
    assert classify(case, assessment(agreement=agreement), "")["comparison_correct"] is False


def test_missing_and_error_results_remain_in_denominators():
    records = [
        {"id": "positive", "expected": {"exact_support": True}, "error": {"type": "ValueError"}},
        {"id": "negative", "expected": {"exact_support": False},
         "observed": {"exact_support_accepted": True, "status": "covered", "passed": False}},
    ]
    result = summarize(records)
    assert result["cases"] == 2 and result["errors"] == 1
    assert result["false_acceptance_rate"] == 1
    assert result["false_rejection_rate"] == 1
    assert result["positive_exact_coverage"] == 0


def test_extractive_reference_has_no_invented_verifier_score():
    record = {"id": "quote", "expected": {"exact_support": False},
              "observed": {"exact_support_accepted": None, "status": "unassessed_quotes",
                           "literal_evidence_retained": 1, "literal_evidence_total": 1,
                           "all_source_literals_retained": True}, "latency_ms": [1, 2, 3]}
    result = summarize([record])
    assert result["false_acceptance_rate"] is None and result["false_rejection_rate"] is None
    assert result["literal_evidence_coverage"] == 1 and result["cases"] == 1


def test_first_failure_cannot_be_replaced_by_favorable_repeat():
    entry = {"expected": {"exact_support": True, "comparison": None}}
    trials = [
        {"repeat_index": 0, "observed": {"status": "error", "exact_support_accepted": False, "passed": False},
         "error": {"type": "TimeoutError", "message": "primary failed"}},
        {"repeat_index": 1, "observed": {"status": "covered", "exact_support_accepted": True, "passed": True}},
    ]
    finish_trials(entry, trials)
    assert entry["observed"]["status"] == "error" and entry["error"]["type"] == "TimeoutError"
    assert len(entry["trials"]) == 2 and len(entry["trial_errors"]) == 1
    assert entry["outcome_varies"] and not entry["all_trials_passed"]


def test_false_acceptance_in_later_repeat_fails_repeat_gate():
    entry = {"expected": {"exact_support": False, "comparison": "forbidden"}}
    trials = [
        {"repeat_index": 0, "observed": {"status": "partial", "exact_support_accepted": False, "passed": True}},
        {"repeat_index": 1, "observed": {"status": "covered", "exact_support_accepted": True, "passed": False,
                                         "numeric_agreements": ["equal"]}},
    ]
    finish_trials(entry, trials)
    assert entry["observed"]["status"] == "partial"
    assert entry["any_false_acceptance"] and entry["any_unsupported_equality"]
    assert not entry["all_trials_passed"]


def test_decision_success_does_not_hide_lost_annotated_evidence():
    result = classify(example(), assessment(), "Source omitted.")
    assert result["decision_passed"] is True and result["passed"] is False


def product_assessment(question, text):
    from services.api.answer_contract import AnswerContract
    from services.api.structured_answer import Catalogue

    reference = {"id": "R001", "kind": "excerpt", "document_id": "synthetic", "document_name": "synthetic",
                 "source_ids": ["S001"], "text": text, "locators": [{"section": "Synthetic clause"}],
                 "extraction_method": "native"}
    return Catalogue("question", [reference], AnswerContract(question, "question", {})).assess()


def test_nonexact_ablation_really_restores_the_previous_false_acceptance(monkeypatch):
    from services.api import answer_contract

    question, text = "What is the nominal voltage?", "The nominal voltage is less than 3.3 V."
    assert product_assessment(question, text)["status"] != "covered"
    monkeypatch.setattr(answer_contract, "has_nonexact_numeric_modifier", answer_contract.has_nonexact_numeric_modifier)
    apply_ablation("nonexact_guard")
    assert product_assessment(question, text)["status"] == "covered"


def test_exception_ablation_really_restores_the_excluded_point_acceptance(monkeypatch):
    from services.api import point_conditions

    question = "What is the output current at TA = 25 °C?"
    text = "Output current is 8 mA unless TA = 25 °C."
    assert product_assessment(question, text)["status"] != "covered"
    monkeypatch.setattr(point_conditions, "point_is_excluded", point_conditions.point_is_excluded)
    apply_ablation("exception_guard")
    assert product_assessment(question, text)["status"] == "covered"


def test_source_drift_report_is_preserved_before_nonzero_exit(tmp_path, monkeypatch):
    from tools.qualification import support_benchmark

    target = tmp_path / "invalid-attempt.json"
    result = {"measurement_valid": False, "summary": {"not_scored": True, "status": "INVALID_SOURCE_IDENTITY"},
              "cases": [{"id": "attempted", "trials": [{"result": "preserved"}]}]}
    monkeypatch.setattr(support_benchmark, "run", lambda *args: result)
    monkeypatch.setattr(sys, "argv", ["support_benchmark.py", "--application-root", str(tmp_path),
                                     "--fixtures", str(tmp_path / "not-read-by-double.json"),
                                     "--label", "explicit-test-double", "--output", str(target)])
    with pytest.raises(SystemExit) as stopped:
        support_benchmark.main()
    assert stopped.value.code == 2
    assert json.loads(target.read_text()) == result


def test_development_annotations_remain_the_frozen_twenty_four():
    root = Path(__file__).resolve().parents[2]
    data = load_fixture(root / "tests/fixtures/support_i5_pj_dev.json")
    assert len(data["cases"]) == 24
    assert sum(case["expected"]["exact_support"] for case in data["cases"]) == 12
    assert {case["language"] for case in data["cases"]} == {"fr", "en"}
