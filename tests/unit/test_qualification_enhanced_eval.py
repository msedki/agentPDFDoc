"""Invariants de mesure EV4B sur données synthétiques, sans génération ni réseau."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.qualification import enhanced_eval as ev


def annotation(question="q1", document="d1", *, split="regression", answerable=True, family=None):
    result = {"question_id": question, "document_id": document, "split": split,
              "question": "Quelle plage ?", "answerable": answerable,
              "required_facts": [{"id": "min", "description": "borne inférieure"},
                                 {"id": "max", "description": "borne supérieure"}] if answerable else []}
    if family:
        result["family_id"] = family
    return result


def execution(question="q1", variant="enhanced", repeat=0, *, correct=True):
    return {"question_id": question, "variant": variant, "repeat": repeat, "status": "completed",
            "answer": "0 à 36 V", "abstained": False,
            "fact_verdicts": {fact: {"correct": correct, "citation_supported": True, "in_context": True}
                              for fact in ("min", "max")},
            "has_false_claims": False, "has_unsupported_claims": False,
            "judgment": {"method": "rule"}, "latency_s": 0.0, "memory_peak_mib": 0.0,
            "memory_scope": "synthetic", "request": {"messages": [{"role": "user", "content": "Quelle plage ?"}],
                                                       "options": {"seed": 0}}}


def unreviewed(question="q1", variant="enhanced"):
    result = execution(question, variant)
    result.update(fact_verdicts={}, has_false_claims=None, has_unsupported_claims=None,
                  judgment={"method": "unreviewed"})
    return result


def test_denominators_preserve_unknown_abstentions_refusals_and_not_run():
    gold = [annotation(f"q{i}", f"d{i}") for i in range(1, 7)]
    gold.append(annotation("q7", "d7", answerable=False))
    partial = execution("q2")
    partial["fact_verdicts"]["max"] = {"correct": False, "citation_supported": None, "in_context": False}
    abstained = unreviewed("q5")
    abstained.update(answer="Non établi.", abstained=True)
    negative = {**unreviewed("q7"), "answer": "Non établi.", "abstained": True}
    runs = [execution("q1"), partial, unreviewed("q3"),
            {"question_id": "q4", "variant": "enhanced", "repeat": 0, "status": "refused"},
            abstained, {"question_id": "q6", "variant": "enhanced", "repeat": 0, "status": "not_run"}, negative]
    result = ev.evaluate(gold, runs)["variants"]["enhanced"]
    assert result["positions"] == 7 and result["submitted"] == 6
    assert result["answerable_submitted"] == 5 and result["unanswerable_submitted"] == 1
    assert result["confirmed_complete_per_answerable_submission"] == {"numerator": 1, "denominator": 5, "value": .2}
    assert result["complete_accuracy_reviewed_published"]["value"] == .5
    assert result["answer_coverage"]["value"] == .6
    assert result["unreviewed_published"] == 1
    assert result["context_fact_recall_reviewed"]["value"] == .75
    assert result["context_facts_unreviewed"] == 6
    assert result["outcome_counts"]["correct_abstention"] == 1
    assert result["memory_peak_mib_by_scope"]["synthetic"]["max"] == 0
    assert result["latency_s_by_status"]["completed"]["median"] == 0


def test_extra_false_claim_prevents_exact_answer_despite_all_required_facts():
    run = execution()
    run["has_false_claims"] = True
    result = ev.evaluate([annotation()], [run])["variants"]["enhanced"]
    assert result["outcome_counts"] == {"incorrect": 1}
    assert result["confirmed_complete_per_answerable_submission"]["numerator"] == 0


@pytest.mark.parametrize("answerable", [True, False])
def test_false_claim_in_abstention_is_counted_without_known_required_fact_correctness(answerable):
    run = unreviewed()
    run.update(answer="Le document ne contient pas cette donnée ; je ne peux pas répondre.",
               abstained=True, has_false_claims=True, judgment={"method": "agent"})
    if answerable:
        run["fact_verdicts"] = {fact: {"correct": None, "citation_supported": None, "in_context": True}
                                for fact in ("min", "max")}
    result = ev.evaluate([annotation(answerable=answerable)], [run])["variants"]["enhanced"]
    assert result["outcome_counts"] == {"abstention_with_false_claims": 1}
    assert result["confirmed_complete_per_answerable_submission"]["numerator"] == 0
    assert result["false_claim_risk_reviewed"] == {"numerator": 0, "denominator": 0, "value": None}
    assert result["false_claim_risk_reviewed_completed"] == {"numerator": 1, "denominator": 1, "value": 1}
    assert result["abstentions_with_false_claims"] == 1
    assert result["false_claims_unreviewed_completed"] == 0


def test_completed_false_claim_risk_preserves_old_published_metric_and_counts_unknown_verdicts():
    gold = [annotation(f"q{i}", f"d{i}", answerable=i != 3) for i in range(1, 6)]
    false_abstention = {**unreviewed("q2"), "abstained": True, "has_false_claims": True,
                        "judgment": {"method": "agent"}}
    false_unanswerable_answer = {**unreviewed("q3"), "has_false_claims": True,
                                 "judgment": {"method": "agent"}}
    unknown_abstention = {**unreviewed("q5"), "abstained": True}
    result = ev.evaluate(gold, [execution("q1"), false_abstention, false_unanswerable_answer,
                                unreviewed("q4"), unknown_abstention])["variants"]["enhanced"]
    assert result["false_claim_risk_reviewed"] == {"numerator": 0, "denominator": 1, "value": 0}
    assert result["false_claim_risk_reviewed_published"] == result["false_claim_risk_reviewed"]
    assert "non-abstained" in result["false_claim_risk_reviewed_scope"]
    assert result["false_claim_risk_reviewed_completed"] == {"numerator": 2, "denominator": 3, "value": 2 / 3}
    assert result["completed_responses"] == 5
    assert result["false_claims_unreviewed_completed"] == 2
    assert result["abstentions_with_false_claims"] == 1
    assert result["outcome_counts"]["answer_to_unanswerable"] == 1


@pytest.mark.parametrize("status", ["refused", "error", "cancelled", "not_run"])
def test_noncompleted_status_cannot_enter_completed_false_claim_denominator(status):
    run = {"question_id": "q1", "variant": "enhanced", "repeat": 0, "status": status,
           "has_false_claims": True, "judgment": {"method": "agent"}}
    result = ev.evaluate([annotation()], [run])["variants"]["enhanced"]
    assert result["false_claim_risk_reviewed_completed"] == {"numerator": 0, "denominator": 0, "value": None}
    assert result["completed_responses"] == result["false_claims_unreviewed_completed"] == 0
    assert result["abstentions_with_false_claims"] == 0
    assert result["outcome_counts"] == {status: 1}


@pytest.mark.parametrize("false_claims", [False, None])
def test_unanswerable_abstention_keeps_existing_outcome_but_unknown_false_claim_verdict_is_not_reviewed(false_claims):
    run = {**unreviewed(), "abstained": True, "has_false_claims": false_claims,
           "judgment": {"method": "agent" if false_claims is not None else "unreviewed"}}
    result = ev.evaluate([annotation(answerable=False)], [run])["variants"]["enhanced"]
    assert result["outcome_counts"] == {"correct_abstention": 1}
    assert result["abstentions_with_false_claims"] == 0
    assert result["false_claim_risk_reviewed_completed"]["numerator"] == 0
    assert result["false_claim_risk_reviewed_completed"]["denominator"] == (1 if false_claims is False else 0)
    assert result["false_claims_unreviewed_completed"] == (0 if false_claims is False else 1)


def test_valid_required_citations_do_not_prove_entire_answer_supported():
    run = execution()
    run["has_unsupported_claims"] = None
    result = ev.evaluate([annotation()], [run])["variants"]["enhanced"]
    assert result["confirmed_complete_per_answerable_submission"]["numerator"] == 1
    assert result["confirmed_complete_and_supported_per_submission"]["numerator"] == 0


def test_unreviewed_response_does_not_become_correct_or_wrong_by_string_match():
    result = ev.evaluate([annotation()], [unreviewed()])["variants"]["enhanced"]
    assert result["outcome_counts"] == {"unreviewed": 1}
    assert result["complete_accuracy_reviewed_published"]["denominator"] == 0
    assert result["false_claim_risk_reviewed"]["value"] is None


def test_false_numeric_and_null_values_are_not_interchangeable():
    run = execution()
    run["fact_verdicts"]["min"]["correct"] = 0
    with pytest.raises(ValueError, match="booléen"):
        ev.evaluate([annotation()], [run])


@pytest.mark.parametrize("change", [{"repeat": True}, {"repeat": -1}, {"latency_s": float("nan")},
                                    {"memory_peak_mib": -1}, {"abstained": None}, {"answer": None}])
def test_invalid_measurements_and_missing_completed_response_rejected(change):
    with pytest.raises(ValueError):
        ev.evaluate([annotation()], [{**execution(), **change}])


def test_duplicate_question_or_repetition_cannot_inflate_sample_size():
    with pytest.raises(ValueError, match="Question dupliquée"):
        ev.evaluate([annotation(), annotation()], [])
    with pytest.raises(ValueError, match="Exécution dupliquée"):
        ev.evaluate([annotation()], [execution(), execution()])


def test_unknown_fact_and_unattributed_judgment_rejected():
    run = execution()
    run["fact_verdicts"]["invented"] = {"correct": True}
    with pytest.raises(ValueError, match="non annotés"):
        ev.evaluate([annotation()], [run])
    run = execution()
    run.pop("judgment")
    with pytest.raises(ValueError, match="méthode de jugement"):
        ev.evaluate([annotation()], [run])


def test_holdout_is_split_by_family_and_document_not_only_by_question():
    with pytest.raises(ValueError, match="Fuite"):
        ev.evaluate([annotation("q1", "rev1", family="same"),
                     annotation("q2", "rev2", family="same", split="holdout")], [])
    with pytest.raises(ValueError, match="Fuite"):
        ev.evaluate([annotation("q1", "same", family="a"),
                     annotation("q2", "same", family="b", split="holdout")], [])


def test_request_hash_preserves_zero_order_and_exact_unicode_content():
    payload = {"options": {"seed": 0}, "messages": ["0 V", "36 V"]}
    assert ev.canonical_sha256(payload) == ev.canonical_sha256(dict(reversed(list(payload.items()))))
    assert ev.canonical_sha256(payload) != ev.canonical_sha256({**payload, "messages": ["36 V", "0 V"]})
    assert ev.canonical_sha256("é") != ev.canonical_sha256("e\u0301")
    assert ev.canonical_sha256("0 V") != ev.canonical_sha256("0  V")


def test_wrong_prompt_or_source_digest_stops_analysis():
    run = {**execution(), "prompt": ["test"], "prompt_sha256": "0" * 64}
    with pytest.raises(ValueError, match="empreinte incompatible"):
        ev.evaluate([annotation()], [run])
    with pytest.raises(ValueError, match="source différente"):
        ev.evaluate([{**annotation(), "source_sha256": "a" * 64}],
                    [{**execution(), "source_sha256": "b" * 64}])


def test_evaluation_never_mutates_input_records():
    gold, runs = [annotation()], [execution()]
    originals = copy.deepcopy((gold, runs))
    ev.evaluate(gold, runs)
    assert (gold, runs) == originals


def test_repetitions_have_equal_question_weight_in_paired_effect():
    gold = [annotation("q1", "doc-a"), annotation("q2", "doc-b")]
    runs = []
    for repeat in range(4):
        runs += [execution("q1", "baseline", repeat, correct=False), execution("q1", "enhanced", repeat)]
    runs += [execution("q2", "baseline"), execution("q2", "enhanced", correct=False)]
    result = ev.evaluate(gold, runs, baseline="baseline", resamples=100)["comparisons"][0]
    effect = result["complete_response_delta"]
    assert result["paired_positions"] == 5
    assert effect["questions"] == 2 and effect["families"] == 2
    assert effect["estimate"] == 0  # Equal question weights; not +0.6 from treating repeats as new questions.
    assert effect["interval"] == [-1, 1]


def test_document_cluster_is_not_inflated_by_two_questions_or_many_repeats():
    gold = ev.validate_annotations([annotation("q1", "rev-a", family="manual"),
                                    annotation("q2", "rev-b", family="manual")])
    effect = ev.cluster_interval({"q1": 1, "q2": 0}, gold)
    assert effect["families"] == 1 and effect["interval"] is None
    assert effect["estimate"] == .5


def test_unreviewed_pairs_and_unmatched_positions_remain_visible():
    gold = [annotation("q1"), annotation("q2", "d2")]
    runs = [execution("q1", "baseline"), unreviewed("q1"), execution("q2", "baseline")]
    result = ev.evaluate(gold, runs, baseline="baseline")["comparisons"][0]
    assert result["paired_positions"] == 1
    assert result["unreviewed_answerable_pairs"] == 1
    assert result["unpaired_baseline_positions"] == 1
    assert result["complete_response_delta"]["estimate"] is None


def test_fixed_context_ablation_requires_exact_observed_fingerprints():
    runs = [{**execution(variant=variant), "context": ["0", "36"]} for variant in ("baseline", "enhanced")]
    result = ev.evaluate([annotation()], runs, baseline="baseline", require_same_context=True)
    assert result["comparisons"][0]["paired_positions"] == 1
    runs[1]["context"].reverse()
    with pytest.raises(ValueError, match="Ablation non comparable"):
        ev.evaluate([annotation()], runs, baseline="baseline", require_same_context=True)
    with pytest.raises(ValueError, match="Ablation non comparable"):
        ev.evaluate([annotation()], runs, baseline="baseline", require_same_prompt=True)


def test_risk_coverage_ties_cannot_be_ordered_to_create_artificial_gain():
    curve = ev.risk_coverage_curve([(.9, True), (.9, False), (.2, True)], denominator=4)
    assert len(curve) == 2
    assert curve[0] == {"threshold": .9, "selected": 2, "errors": 1, "coverage": .5, "risk": .5}
    assert curve[1]["coverage"] == .75
    with pytest.raises(ValueError, match="Dénominateur"):
        ev.risk_coverage_curve([(.9, True)], denominator=0)


def test_repetition_does_not_drop_failed_attempt_and_claim_stability():
    runs = [execution(), {"question_id": "q1", "variant": "enhanced", "repeat": 1, "status": "error"}]
    repeat = ev.evaluate([annotation()], runs)["repetitions"]["questions"][0]
    assert repeat["repetitions"] == 2 and repeat["completed"] == 1
    assert repeat["same_answer"] is None and repeat["same_request"] is None
    assert repeat["same_status"] is False


@pytest.mark.parametrize("text", ['{"x":1,"x":2}\n', '{"x":NaN}\n', '\n', '[1]\n', '{"x":'])
def test_jsonl_rejects_ambiguous_or_incomplete_records(tmp_path: Path, text):
    path = tmp_path / "cases.jsonl"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        ev.read_jsonl(path)


def test_jsonl_line_size_bound_is_enforced(tmp_path: Path, monkeypatch):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"value":"' + "a" * 100 + '"}\n', encoding="utf-8")
    monkeypatch.setattr(ev, "MAX_LINE_BYTES", 30)
    with pytest.raises(ValueError, match="supérieure"):
        ev.read_jsonl(path)


def test_cli_records_input_hashes_and_cannot_overwrite_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ev, "LOCAL_QA", tmp_path)
    gold, runs, output = (tmp_path / name for name in ("gold.jsonl", "runs.jsonl", "summary.json"))
    gold.write_text(json.dumps(annotation()) + "\n", encoding="utf-8")
    runs.write_text(json.dumps(execution()) + "\n", encoding="utf-8")
    args = ["--annotations", str(gold), "--runs", str(runs), "--output", str(output)]
    assert ev.main(args) == 0
    saved = output.read_bytes()
    report = json.loads(saved)
    assert report["input_files"]["annotations_sha256"] == ev.file_sha256(gold)
    assert ev.main(args) == 2
    assert output.read_bytes() == saved


def test_empty_run_set_preserves_not_run_instead_of_fake_success():
    result = ev.evaluate([annotation()], [])
    assert result["variants"] == {} and result["comparisons"] == []
    assert result["annotations"]["questions"] == 1
