"""Oracle tests use explicit fabricated observations, never model self-grading."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from tools.qualification import relations_benchmark as bench


def case():
    text = "The nominal voltage of UQ12 is 42.7 mV."
    span = {"start": 0, "end": len(text), "text": text}
    fact = {"id": "G01", "reference_id": "R001", "document_id": "A", "subject": "UQ12",
            "quantity": "voltage", "values": ["42.7"], "unit": "mV", "role": "nominal", "property": None,
            "point_conditions": [], "annotation_span": span, "rationale": "Exact nominal source value."}
    return {"id": "synthetic-oracle-test", "split": "development", "group": "oracle", "category": "explicit-test-double",
            "language": "en", "question": "What is the nominal voltage of UQ12?", "mode": "question",
            "rationale": "Explicit test oracle, not a product benchmark.", "scope": {"kind": "documents", "document_ids": ["A"]},
            "sources": [{"id": "R001", "kind": "excerpt", "document_id": "A", "document_family": "test-family",
                         "source_ids": ["S001"], "text": text, "annotation_span": span}],
            "expected": {"exact_support": True, "allowed_relations": [fact], "forbidden_relations": [],
                         "required_relation_groups": [["G01"]], "comparisons": [], "forbidden_comparison_conclusions": [],
                         "required_literals": [{"reference_id": "R001", **span}], "status_classes": ["covered"]}}


def observed_fact(gold):
    return {"reference_id": gold["reference_id"], "document_id": gold["document_id"], "subjects": [gold["subject"]],
            "quantity": gold["quantity"], "values": gold["values"], "unit": gold["unit"], "role": gold["role"],
            "property": gold["property"], "condition": "".join(f"at {p['symbol']} = {p['value']} {p['unit']}" for p in gold["point_conditions"])}


def result(c, *, facts=None, status="covered", comparisons=None):
    output = bench.extractive_result(c)
    output["answer_contract"] = {"status": status, "matched_relations": [observed_fact(g) for g in c["expected"]["allowed_relations"]] if facts is None else facts,
                                 "obligations": [{"covered": status == "covered"}], "comparisons": comparisons or []}
    return output


def test_true_exact_relation_and_linked_literal_pass():
    c = case()
    assert bench.classify(c, result(c))["passed"]


@pytest.mark.parametrize("field,value", [("values", ["42.8"]), ("unit", "V"), ("subjects", ["OTHER"]),
                                          ("subjects", ["UQ12", "INVENTED"]), ("properties", ["output"]),
                                          ("document_id", "B"), ("role", "max"), ("bound_role", "min"), ("reference_id", "R999")])
def test_status_and_quote_cannot_hide_wrong_atomic_fact(field, value):
    c = case()
    output = result(c)
    output["answer_contract"]["matched_relations"][0][field] = value
    verdict = bench.classify(c, output)
    assert not verdict["passed"] and verdict["any_unexpected_relation"]


def test_exact_unit_conversion_is_independent_of_product():
    c = case()
    output = result(c)
    output["answer_contract"]["matched_relations"][0].update(values=["0.0427"], unit="V")
    assert bench.classify(c, output)["passed"]


def test_unqualified_source_does_not_prove_invented_nominal_role():
    c = case()
    c["expected"]["allowed_relations"][0]["role"] = None
    output = result(c)
    output["answer_contract"]["matched_relations"][0]["role"] = "nominal"
    assert not bench.classify(c, output)["passed"]


def test_unannotated_extra_relation_fails_even_if_required_fact_is_present():
    c = case()
    output = result(c)
    invented = copy.deepcopy(output["answer_contract"]["matched_relations"][0])
    invented["values"] = ["999"]
    output["answer_contract"]["matched_relations"].append(invented)
    assert bench.classify(c, output)["unexpected_matched_relation_indexes"] == [1]


def test_partial_status_does_not_hide_forbidden_operand():
    c = case()
    c["expected"].update(exact_support=False, status_classes=["partial", "ambiguous"], required_relation_groups=[])
    gold = c["expected"]["allowed_relations"].pop()
    c["expected"]["forbidden_relations"].append(gold)
    output = result(c, facts=[observed_fact(gold)], status="partial")
    verdict = bench.classify(c, output)
    assert verdict["exact_support_decision_correct"]
    assert verdict["any_forbidden_operand"] and not verdict["passed"]


def test_missing_subject_or_lost_qualifier_cannot_hide_forbidden_value():
    c = case()
    gold = c["expected"]["allowed_relations"][0]
    gold["point_conditions"] = [{"symbol": "TA", "value": "99", "unit": "°C"}]
    observed = observed_fact(gold)
    observed.update(subjects=[], role=None, condition="")
    assert bench.relation_matches(gold, observed, forbidden=True)
    assert not bench.relation_matches(gold, observed)


def test_requested_point_is_part_of_positive_fact_oracle():
    c = case()
    gold = c["expected"]["allowed_relations"][0]
    gold["point_conditions"] = [{"symbol": "TA", "value": "99", "unit": "°C"}]
    text = c["sources"][0]["text"][:-1] + " at TA = 99 °C."
    span = {"start": 0, "end": len(text), "text": text}
    c["sources"][0].update(text=text, annotation_span=span)
    gold["annotation_span"] = span
    c["expected"]["required_literals"] = [{"reference_id": "R001", **span}]
    output = result(c)
    assert bench.classify(c, output)["passed"]
    output["answer_contract"]["matched_relations"][0]["condition"] = "at TA = 100 °C"
    assert not bench.classify(c, output)["passed"]


@pytest.mark.parametrize("invented", ["at TA = 999 °C", "under vacuum"])
def test_unconditional_gold_cannot_acquire_invented_condition(invented):
    c = case()
    output = result(c)
    output["answer_contract"]["matched_relations"][0]["condition"] = invented
    assert not bench.classify(c, output)["passed"]


def test_condition_fragments_preserve_excluded_points_but_reject_extra_point():
    source = "Except at TA = 81 °C, the output current is 17 mA at TA = 82 °C."
    assert bench.literal_condition_supported("Except at TA = 81 °C, at TA = 82 °C.", source)
    assert not bench.literal_condition_supported("at TA = 82 °C and TA = 999 °C", source)


def test_true_nonnumeric_context_is_not_an_invented_condition():
    c = case()
    gold = c["expected"]["allowed_relations"][0]
    gold["annotation_span"]["text"] += " The circuit operates without an external resistor."
    gold["annotation_span"]["end"] = len(gold["annotation_span"]["text"])
    observed = observed_fact(gold)
    observed["condition"] = "without an external resistor"
    assert bench.relation_matches(gold, observed, evidence_text=c["expected"]["required_literals"][0]["text"])


def test_point_from_another_quantity_is_not_the_target_condition():
    c = case()
    gold = c["expected"]["allowed_relations"][0]
    independent_voltage = gold["annotation_span"]["text"]
    gold["annotation_span"]["text"] += " The output current is 17 mA at TA = 81 °C."
    gold["annotation_span"]["end"] = len(gold["annotation_span"]["text"])
    observed = observed_fact(gold)
    observed["condition"] = "at TA = 81 °C"
    assert not bench.relation_matches(gold, observed, evidence_text=independent_voltage)


def test_invented_conflict_is_not_a_correct_abstention():
    c = case()
    c["expected"].update(exact_support=False, required_relation_groups=[], status_classes=["partial", "ambiguous"])
    verdict = bench.classify(c, result(c, status="conflict"))
    assert not verdict["status_allowed"] and not verdict["passed"]


def test_quote_without_provenance_or_marker_does_not_pass():
    c = case()
    output = result(c)
    output["citation_spans"][0]["source_id"] = "S999"
    verdict = bench.classify(c, output)
    assert verdict["literal_texts_retained"] == 1 and verdict["literal_citations_retained"] == 0
    assert not verdict["passed"]


def test_real_ledger_shape_keeps_citation_tail_with_its_reference():
    c = case()
    output = result(c)
    assert [segment["kind"] for segment in output["support_ledger"]["segments"]] == ["reference", "citation"]
    assert bench.literal_checks(c, output)[0]["linked_citation_retained"]
    output["support_ledger"]["segments"][1]["reference_ids"] = ["R999"]
    assert not bench.literal_checks(c, output)[0]["linked_citation_retained"]


def test_alternative_literal_requires_its_actual_source_identity():
    c = case()
    alternative = copy.deepcopy(c["sources"][0])
    alternative.update(id="R003", source_ids=["S003"], document_id="C")
    c["sources"].append(alternative)
    c["expected"]["required_literals"][0]["alternative_reference_ids"] = ["R001", "R003"]
    only_alternative = copy.deepcopy(c)
    only_alternative["sources"] = [alternative]
    output = bench.extractive_result(only_alternative)
    check = bench.literal_checks(c, output)[0]
    assert check["linked_citation_retained"] and check["valid_reference_ids"] == ["R003"]
    output["support_ledger"]["segments"][0]["reference_ids"] = ["R001"]
    assert not bench.literal_checks(c, output)[0]["linked_citation_retained"]


def test_swapped_citation_markers_are_not_local_provenance():
    c = two_operand_case()
    c["expected"]["required_literals"].append({"reference_id": "R002", **c["sources"][1]["annotation_span"]})
    output = bench.extractive_result(c)
    output["text"] = output["text"].replace("[S001]", "[TEMP]").replace("[S002]", "[S001]").replace("[TEMP]", "[S002]")
    for marker in output["citation_spans"]:
        marker["source_id"] = "S002" if marker["source_id"] == "S001" else "S001"
    assert all(not check["linked_citation_retained"] for check in bench.literal_checks(c, output))


def two_operand_case():
    c = case()
    b = copy.deepcopy(c["sources"][0])
    b.update(id="R002", source_ids=["S002"], document_id="B", text=b["text"].replace("UQ12", "UQ13"))
    b["annotation_span"] = {"start": 0, "end": len(b["text"]), "text": b["text"]}
    c["sources"].append(b)
    second = copy.deepcopy(c["expected"]["allowed_relations"][0])
    second.update(id="G02", reference_id="R002", document_id="B", subject="UQ13")
    c["expected"]["allowed_relations"].append(second)
    c["expected"]["required_relation_groups"].append(["G02"])
    c["expected"]["comparisons"] = [{"id": "C01", "operand_groups": [["G01"], ["G02"]], "conclusion": "equal", "required": True}]
    return c


def test_comparison_requires_both_actual_operand_sources():
    c = two_operand_case()
    comparison = {"status": "equal", "numeric_agreement": "equal", "reference_ids": ["R001", "R002"]}
    assert bench.classify(c, result(c, comparisons=[comparison]))["passed"]
    comparison["reference_ids"] = ["R001"]
    verdict = bench.classify(c, result(c, comparisons=[comparison]))
    assert not verdict["comparisons_correct"] and verdict["any_forbidden_conclusion"]


def test_correct_numbers_with_wrong_comparison_axis_fail():
    c = two_operand_case()
    gold = c["expected"]["comparisons"][0]
    # An extra source can assert the same number, but cannot replace the other operand.
    third = copy.deepcopy(c["expected"]["allowed_relations"][0])
    third.update(id="G03", reference_id="R003", document_id="C")
    c["expected"]["allowed_relations"].append(third)
    comparison = {"status": "equal", "numeric_agreement": "equal", "reference_ids": ["R001", "R003"]}
    assert gold["operand_groups"] == [["G01"], ["G02"]]
    assert not bench.classify(c, result(c, comparisons=[comparison]))["passed"]


@pytest.mark.parametrize("field,value", [("subject", "INVENTED"), ("subjects", ["UQ12", "INVENTED"]),
                                          ("quantity", "time"), ("property", "input"), ("document_ids", ["UNRELATED"])])
def test_comparison_correct_refs_do_not_prove_invented_labels(field, value):
    c = two_operand_case()
    comparison = {"status": "equal", "numeric_agreement": "equal", "reference_ids": ["R001", "R002"], field: value}
    assert not bench.classify(c, result(c, comparisons=[comparison]))["passed"]


def test_declared_operand_groups_cannot_swap_subject_reference_bindings():
    c = two_operand_case()
    comparison = {"status": "equal", "numeric_agreement": "equal", "reference_ids": ["R001", "R002"],
                  "comparison_axis": "subjects", "operand_groups": [{"subject": "UQ12", "reference_ids": ["R001"]},
                                                                     {"subject": "UQ13", "reference_ids": ["R002"]}]}
    assert bench.classify(c, result(c, comparisons=[comparison]))["passed"]
    comparison["operand_groups"][0]["reference_ids"] = ["R002"]
    comparison["operand_groups"][1]["reference_ids"] = ["R001"]
    assert not bench.classify(c, result(c, comparisons=[comparison]))["passed"]


def test_context_mismatch_does_not_claim_the_numeric_agreement():
    c = two_operand_case()
    c["expected"].update(exact_support=False, comparisons=[], required_relation_groups=[], status_classes=["partial"],
                         forbidden_comparison_conclusions=["equal", "different"])
    observed = {"status": "context_differs", "numeric_agreement": "equal", "reference_ids": ["R001", "R002"]}
    verdict = bench.classify(c, result(c, status="partial", comparisons=[observed]))
    assert verdict["passed"] and not verdict["any_forbidden_conclusion"]


def test_inconsistent_covered_obligation_is_visible():
    c = case()
    output = result(c)
    output["answer_contract"]["obligations"][0]["covered"] = False
    verdict = bench.classify(c, output)
    assert not verdict["claimed_coverage_consistent_with_obligations"] and not verdict["passed"]


def test_repeats_keep_first_and_flag_later_unsafe_outcome():
    entry = {"expected": {"exact_support": False}}
    trials = [{"observed": {"complete_support_claimed": False, "passed": True}},
              {"observed": {"complete_support_claimed": True, "passed": False, "any_forbidden_operand": True}}]
    bench.finish_trials(entry, trials)
    assert entry["observed"]["passed"] and entry["any_repeat_false_acceptance"]
    assert entry["any_repeat_forbidden_operand"] and not entry["all_trials_passed"]
    assert entry["outcome_varies"]


def test_extract_only_preserves_citations_without_a_sufficiency_score():
    c = case()
    output = bench.extractive_result(c)
    checks = bench.literal_checks(c, output)
    assert output["answer_contract"] is None and all(x["linked_citation_retained"] for x in checks)
    entry = {"expected": {"exact_support": True}}
    bench.finish_trials(entry, [{"observed": {"status": "unassessed_quotes", "complete_support_claimed": None, "passed": None}, "latency_ms": 1}])
    summary = bench.summarize([entry])
    assert summary["false_complete_acceptances"] is None and summary["positive_fully_correct"] is None


def test_development_frozen_identity_and_complete_annotation():
    path = Path(__file__).resolve().parents[2] / "tests/fixtures/support_i6_dev.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "fbe09846d7fb138ec71b7400e4eba42e2d8fefbcd17e04172a0d28b04b712315"
    fixture = bench.load_fixture(path)
    assert len(fixture["cases"]) == 48
    assert sum(c["expected"]["exact_support"] for c in fixture["cases"]) == 24


def test_bad_gold_source_span_is_rejected(tmp_path):
    c = case()
    c["sources"][0]["annotation_span"]["end"] -= 1
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 2, "split": "development", "cases": [c]}))
    with pytest.raises(ValueError, match="span"):
        bench.load_fixture(path)


def test_source_drift_is_saved_and_not_scored(tmp_path, monkeypatch):
    output = tmp_path / "invalid.json"
    fake = {"measurement_valid": False, "summary": {"status": "INVALID_SOURCE_IDENTITY", "not_scored": True}}
    monkeypatch.setattr(bench, "run", lambda *args: fake)
    monkeypatch.setattr(sys, "argv", ["relations_benchmark", "--application-root", str(tmp_path), "--fixtures", str(tmp_path / "unused"),
                                     "--output", str(output), "--label", "explicit-oracle-test"])
    with pytest.raises(SystemExit) as raised:
        bench.main()
    assert raised.value.code == 2 and json.loads(output.read_text()) == fake
