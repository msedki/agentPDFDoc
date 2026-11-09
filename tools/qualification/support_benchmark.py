"""Mesurer les contrôles de relations exactes sur des extraits annotés FR/EN.

Le catalogue et le rendu applicatifs sont réels. L'extraction, la recherche et
le modèle 4B ne sont pas exécutés ; le compteur de caractères est un double.
Les labels portent sur une relation numérique exacte applicable à la question,
pas sur l'absence de toute information utile ni sur une sémantique générale.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): digest(path) for path in sorted((root / "services").rglob("*.py"))}


def load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("split") not in {"development", "heldout"}:
        raise ValueError("Unknown fixture schema or split")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Empty fixture")
    identifiers: set[str] = set()
    families: set[str] = set()
    for case in cases:
        if not isinstance(case.get("id"), str) or case["id"] in identifiers:
            raise ValueError("Invalid or duplicate case ID")
        identifiers.add(case["id"])
        if case.get("split") != data["split"] or not case.get("rationale"):
            raise ValueError("Split mismatch or missing annotation rationale")
        if type(case.get("expected", {}).get("exact_support")) is not bool:
            raise ValueError("Missing binary exact-support annotation")
        if case["expected"].get("comparison") not in {None, "equal", "different", "forbidden"}:
            raise ValueError("Unknown comparison label")
        references = case.get("sources")
        if not isinstance(references, list) or not references:
            raise ValueError("Missing source evidence")
        refs: set[str] = set()
        for source in references:
            if source.get("id") in refs:
                raise ValueError("Duplicate source reference")
            refs.add(source["id"])
            family = source.get("document_family")
            if not isinstance(family, str) or not family:
                raise ValueError("Missing document family")
            families.add(family)
            span = source.get("annotation_span", {})
            text = source.get("text")
            start, end = span.get("start"), span.get("end")
            if (not isinstance(text, str) or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(text) or text[start:end] != span.get("text")):
                raise ValueError("Annotation does not match its source codepoint offsets")
    data["document_families"] = sorted(families)
    return data


def ensure_disjoint(first: dict[str, Any], second: dict[str, Any]) -> None:
    if set(first["document_families"]) & set(second["document_families"]):
        raise ValueError("Document-family leakage between splits")
    hashes = [{hashlib.sha256(source["text"].encode()).hexdigest()
               for case in fixture["cases"] for source in case["sources"]}
              for fixture in (first, second)]
    if hashes[0] & hashes[1]:
        raise ValueError("Identical source text across splits")


class CharacterCounterDouble:
    def count(self, text: str) -> int:
        return len(text) // 4 + 1


def classify(case: dict[str, Any], assessment: dict[str, Any], text: str) -> dict[str, Any]:
    """Read the product's relation/coverage decisions, not answer-word regexes."""
    facts = assessment.get("matched_relations", [])
    obligations = assessment.get("obligations", [])
    covered = bool(facts) and assessment.get("status") == "covered"
    # A status alone cannot replace the actual matched evidence and obligations.
    if obligations and not all(item.get("covered") is True for item in obligations):
        covered = False
    comparisons = assessment.get("comparisons", [])
    agreements = [item.get("numeric_agreement") for item in comparisons]
    expected = case["expected"]
    requested_comparison = expected["comparison"]
    if requested_comparison in {"equal", "different"}:
        comparison_correct = bool(agreements) and all(value == requested_comparison for value in agreements)
    elif requested_comparison == "forbidden":
        # Frozen negatives prohibit a manufactured scalar equality. An exact
        # inequality could establish a difference; this benchmark does not
        # forbid that valid deduction or label every bounded question absent.
        comparison_correct = "equal" not in agreements
    else:
        comparison_correct = True
    retained = [source["annotation_span"]["text"] in text for source in case["sources"]]
    exact_correct = covered is expected["exact_support"]
    return {
        "exact_support_accepted": covered,
        "exact_support_correct": exact_correct,
        "comparison_correct": comparison_correct,
        "decision_passed": exact_correct and comparison_correct,
        "passed": exact_correct and comparison_correct and all(retained),
        "matched_relation_count": len(facts),
        "numeric_agreements": agreements,
        "literal_evidence_retained": sum(retained),
        "literal_evidence_total": len(retained),
        "all_source_literals_retained": all(retained),
        "status": assessment.get("status", "missing"),
        "nonexact_does_not_mean_unanswerable": True,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [item for item in records if item["expected"]["exact_support"]]
    negative = [item for item in records if not item["expected"]["exact_support"]]
    assessed = any(item.get("observed", {}).get("exact_support_accepted") is not None for item in records)
    false_accepts = sum(item.get("observed", {}).get("exact_support_accepted") is True for item in negative)
    false_rejects = sum(item.get("observed", {}).get("exact_support_accepted") is not True for item in positive)
    retained = sum(item.get("observed", {}).get("literal_evidence_retained", 0) for item in records)
    total = sum(item.get("observed", {}).get("literal_evidence_total", 0) for item in records)
    negative_retained = sum(item.get("observed", {}).get("all_source_literals_retained", False) for item in negative)
    latencies = [value for item in records for value in item.get("latency_ms", [])]
    return {
        "cases": len(records), "positive_exact_support": len(positive), "negative_exact_support": len(negative),
        "false_acceptance_count": false_accepts if assessed else None,
        "false_acceptance_rate": false_accepts / len(negative) if assessed and negative else None,
        "false_rejection_count": false_rejects if assessed else None,
        "false_rejection_rate": false_rejects / len(positive) if assessed and positive else None,
        "positive_exact_coverage": (len(positive) - false_rejects) / len(positive) if assessed and positive else None,
        "case_passed": sum(item.get("observed", {}).get("passed") is True for item in records) if assessed else None,
        "all_repeats_case_passed": sum(item.get("all_trials_passed") is True for item in records) if assessed else None,
        "any_repeat_false_acceptance_cases": sum(item.get("any_false_acceptance", False) for item in negative) if assessed else None,
        "any_repeat_unsupported_equality_cases": sum(item.get("any_unsupported_equality", False) for item in negative) if assessed else None,
        "errors": sum("error" in item for item in records),
        "cases_with_any_trial_error": sum(bool(item.get("trial_errors")) for item in records),
        "statuses": dict(Counter(item.get("observed", {}).get("status", "error") for item in records)),
        "literal_evidence_retained": retained, "literal_evidence_total": total,
        "literal_evidence_coverage": retained / total if total else None,
        "negative_cases_all_literals_retained": negative_retained,
        "negative_cases_total": len(negative),
        "latency_ms_median": statistics.median(latencies) if latencies else None,
        "latency_ms_p95": sorted(latencies)[max(0, math.ceil(0.95 * len(latencies)) - 1)] if latencies else None,
        "measurement_repeats_not_independent_cases": True,
        "variable_outcomes": sum(item.get("outcome_varies", False) for item in records),
    }


def finish_trials(entry: dict[str, Any], trials: list[dict[str, Any]]) -> None:
    """Keep the predeclared first trial primary, including a first-trial error."""
    first = trials[0]
    entry["trials"] = trials
    entry["observed"] = first["observed"]
    for name in ("result", "error"):
        if name in first:
            entry[name] = first[name]
    entry["trial_errors"] = [{"repeat_index": trial["repeat_index"], **trial["error"]}
                             for trial in trials if "error" in trial]
    entry["outcome_varies"] = any(trial["observed"] != first["observed"] for trial in trials[1:])
    entry["all_trials_passed"] = all(trial["observed"].get("passed") is True and "error" not in trial for trial in trials)
    negative = not entry["expected"]["exact_support"]
    entry["any_false_acceptance"] = negative and any(trial["observed"].get("exact_support_accepted") is True for trial in trials)
    entry["any_unsupported_equality"] = entry["expected"].get("comparison") == "forbidden" and any(
        "equal" in trial["observed"].get("numeric_agreements", []) for trial in trials)


def apply_ablation(ablation: str) -> None:
    if ablation in {"nonexact_guard", "both_guards"}:
        module: Any = importlib.import_module("services.api.answer_contract")
        if not hasattr(module, "has_nonexact_numeric_modifier"):
            raise ValueError("This revision does not contain the nonexact guard")
        module.has_nonexact_numeric_modifier = lambda prefix, suffix: False
    if ablation in {"exception_guard", "both_guards"}:
        module = importlib.import_module("services.api.point_conditions")
        if not hasattr(module, "point_is_excluded"):
            raise ValueError("This revision does not contain the exception guard")
        module.point_is_excluded = lambda text, start: False


def run(root: Path, fixture_path: Path, label: str, mode: str, ablation: str, repeats: int) -> dict[str, Any]:
    root = root.resolve(strict=True)
    fixture = load_fixture(fixture_path)
    if not 1 <= repeats <= 20 or mode not in {"contract", "extractive_all"}:
        raise ValueError("Unsupported measurement configuration")
    if mode == "extractive_all" and ablation != "none":
        raise ValueError("The extractive reference has no contract to ablate")
    if any(name == "services" or name.startswith("services.") for name in sys.modules):
        raise ValueError("Run each application revision in a fresh process")
    before = source_manifest(root)
    harness_before = digest(Path(__file__))
    fixture_before = digest(fixture_path)
    sys.path.insert(0, str(root))
    contract_module = importlib.import_module("services.api.answer_contract")
    structured = importlib.import_module("services.api.structured_answer")
    for name, module in sys.modules.copy().items():
        filename = getattr(module, "__file__", None)
        if name.startswith("services.") and filename and not Path(filename).resolve().is_relative_to(root):
            raise ValueError("Application import from another checkout: " + name)
    apply_ablation(ablation)
    records = []
    process = psutil.Process()
    rss_before = process.memory_info().rss
    rss_sampled_peak = rss_before
    tracemalloc.start()
    try:
        for case in fixture["cases"]:
            entry: dict[str, Any] = {"id": case["id"], "category": case["category"], "language": case["language"],
                                     "question": case["question"], "expected": case["expected"],
                                     "rationale": case["rationale"], "latency_ms": [], "python_allocation_peak_bytes": []}
            trials = []
            for repeat_index in range(repeats):
                trial: dict[str, Any] = {"repeat_index": repeat_index}
                current, _ = tracemalloc.get_traced_memory()
                tracemalloc.reset_peak()
                started = time.perf_counter_ns()
                try:
                    references = copy.deepcopy(case["sources"])
                    for source in references:
                        source["document_name"] = source["document_id"]
                    if mode == "extractive_all":
                        text = "\n\n".join(source["text"] + " [" + source["source_ids"][0] + "]" for source in references)
                        observed = {"exact_support_accepted": None, "status": "unassessed_quotes", "passed": None,
                                    "literal_evidence_retained": len(references), "literal_evidence_total": len(references),
                                    "all_source_literals_retained": True}
                        result = {"text": text, "answer_contract": None, "support_validation": None}
                    else:
                        required = tuple(source["document_id"] for source in references) if len(references) > 1 else ()
                        contract = contract_module.AnswerContract(case["question"], case["mode"], {})
                        cat = structured.Catalogue(case["mode"], references, contract, required_documents=required)
                        raw = json.dumps({"references": [source["id"] for source in references], "comparisons": []})
                        result = cat.render(cat.validate(raw), CharacterCounterDouble(), 5000, required)
                        observed = classify(case, result["answer_contract"], result["text"])
                    trial["result"] = result
                    trial["observed"] = observed
                except Exception as error:
                    trial["error"] = {"type": type(error).__name__, "message": str(error)}
                    trial["observed"] = {"exact_support_accepted": False if mode == "contract" else None,
                                         "status": "error", "passed": False, "literal_evidence_total": len(case["sources"])}
                finally:
                    trial["latency_ms"] = (time.perf_counter_ns() - started) / 1_000_000
                    trial["python_allocation_peak_bytes"] = max(0, tracemalloc.get_traced_memory()[1] - current)
                    entry["latency_ms"].append(trial["latency_ms"])
                    entry["python_allocation_peak_bytes"].append(trial["python_allocation_peak_bytes"])
                    rss_sampled_peak = max(rss_sampled_peak, process.memory_info().rss)
                    trials.append(trial)
            finish_trials(entry, trials)
            records.append(entry)
    finally:
        tracemalloc.stop()
    after = source_manifest(root)
    changes = [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
    identity_valid = not changes and harness_before == digest(Path(__file__)) and fixture_before == digest(fixture_path)
    return {
        "schema_version": 1, "protocol_id": fixture["protocol_id"], "split": fixture["split"],
        "created_utc": datetime.now(UTC).isoformat(), "label": label, "mode": mode, "ablation": ablation,
        "fixtures_sha256": fixture_before, "harness_sha256": harness_before,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "application_root": str(root), "source_manifest": before, "sources_unchanged": not changes,
        "source_manifest_after": after, "source_changes": changes, "measurement_valid": identity_valid,
        "harness_unchanged": harness_before == digest(Path(__file__)),
        "fixtures_unchanged": fixture_before == digest(fixture_path),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "doubles": ["CharacterCounterDouble", "all-authorized-reference selector"],
        "not_executed": ["PDF/Office extraction", "retrieval", "embeddings", "Qdrant", "4B inference", "HTTP"],
        "annotation": fixture["annotation"], "scope": fixture["task"],
        "label_interpretation": "exact_support is exact relation/applicability, not answerability; forbidden comparison forbids manufactured equality",
        "quality_primary": "first trial fixed before execution; every repeat retained; any false acceptance or error fails the repeat safety gate",
        "repeats": repeats, "memory": {"rss_before_bytes": rss_before, "rss_sampled_peak_bytes": rss_sampled_peak,
                                         "measurement": "whole benchmark process sampled after each trial; not native pipeline RAM"},
        "latency_scope": "in-process catalogue/render with tracemalloc enabled; no native pipeline latency",
        "summary": (summarize(records) if identity_valid else
                    {"status": "INVALID_SOURCE_IDENTITY", "not_scored": True, "cases_recorded": len(records)}),
        "cases": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=("contract", "extractive_all"), default="contract")
    parser.add_argument("--ablation", choices=("none", "nonexact_guard", "exception_guard", "both_guards"), default="none")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = run(args.application_root, args.fixtures, args.label, args.mode, args.ablation, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False))
    if not result["measurement_valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
