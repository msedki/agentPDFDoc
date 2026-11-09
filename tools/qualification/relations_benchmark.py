"""Independent I6 relation oracle over the real catalogue and renderer.

This measures bounded source support, not retrieval, extraction or 4B inference.
Gold facts and comparison operands are frozen independently of product outputs.
The I5 harness remains unchanged; only its pure identity/counter helpers are reused.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import math
import platform
import re
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psutil

EVALUATOR_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVALUATOR_ROOT))
from tools.qualification import support_benchmark as legacy  # noqa: E402

UNIT_SCALES = {"V": ("voltage", Decimal(1)), "mV": ("voltage", Decimal(".001")),
               "A": ("current", Decimal(1)), "mA": ("current", Decimal(".001"))}
CONCLUSIONS = {"equal", "different"}


def load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2 or data.get("split") not in {"development", "heldout"}:
        raise ValueError("Unknown I6 fixture schema/split")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Empty I6 fixture")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case.get("id"), str) or case["id"] in case_ids:
            raise ValueError("Invalid/duplicate case ID")
        case_ids.add(case["id"])
        if case.get("split") != data["split"] or not case.get("rationale") or not case.get("question"):
            raise ValueError("Missing question/rationale or inconsistent split")
        expected = case.get("expected", {})
        if type(expected.get("exact_support")) is not bool:
            raise ValueError("Exact-support labels must be boolean")
        references: dict[str, dict] = {}
        for source in case.get("sources", []):
            if source.get("id") in references or not source.get("document_family"):
                raise ValueError("Invalid source identity/family")
            references[source["id"]] = source
            check_span(source["text"], source["annotation_span"])
        if not references or set(case["scope"]["document_ids"]) != {s["document_id"] for s in references.values()}:
            raise ValueError("Missing evidence or inconsistent explicit scope")
        facts: dict[str, dict] = {}
        allowed_ids = set()
        for field in ("allowed_relations", "forbidden_relations"):
            for fact in expected[field]:
                if fact["id"] in facts or fact["reference_id"] not in references:
                    raise ValueError("Duplicate gold fact or unknown gold source")
                source = references[fact["reference_id"]]
                if fact["document_id"] != source["document_id"]:
                    raise ValueError("Gold fact belongs to another document")
                check_span(source["text"], fact["annotation_span"])
                if not fact.get("subject") or not fact.get("values") or base_values(fact) is None:
                    raise ValueError("Incomplete gold relation")
                facts[fact["id"]] = fact
                if field == "allowed_relations":
                    allowed_ids.add(fact["id"])
        groups = [*expected["required_relation_groups"]]
        for comparison in expected["comparisons"]:
            if comparison["conclusion"] not in CONCLUSIONS or type(comparison["required"]) is not bool:
                raise ValueError("Unknown gold comparison conclusion")
            if len(comparison["operand_groups"]) < 2:
                raise ValueError("Comparison needs at least two independently bound operands")
            groups.extend(comparison["operand_groups"])
        if any(not group or not set(group) <= allowed_ids for group in groups):
            raise ValueError("Required/compared gold groups must refer only to admissible facts")
        for literal in expected["required_literals"]:
            source = references[literal["reference_id"]]
            check_span(source["text"], literal)
            alternatives = literal.get("alternative_reference_ids", [literal["reference_id"]])
            if not alternatives or not set(alternatives) <= set(references):
                raise ValueError("Unknown alternative literal reference")
            if any(literal["text"] not in references[ref]["text"] for ref in alternatives):
                raise ValueError("Alternative citation does not contain the annotated literal")
        if not set(expected["forbidden_comparison_conclusions"]) <= CONCLUSIONS:
            raise ValueError("Unknown forbidden conclusion")
    return data


def check_span(text: str, span: dict) -> None:
    start, end = span.get("start"), span.get("end")
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
            or text[start:end] != span.get("text")):
        raise ValueError("Gold codepoint span does not match source")


def decimal(value: Any) -> Decimal:
    return Decimal(str(value).replace("−", "-").replace(",", "."))


def base_values(fact: dict) -> tuple[str, tuple[Decimal, ...]] | None:
    """Small independent exact unit registry; no product parser is the oracle."""
    unit = fact.get("unit")
    if unit not in UNIT_SCALES or not isinstance(fact.get("values"), list):
        return None
    dimension, scale = UNIT_SCALES[unit]
    try:
        values = tuple(decimal(v) * scale for v in fact["values"])
        if not values or not all(v.is_finite() for v in values):
            return None
        return dimension, values
    except (InvalidOperation, ValueError):
        return None


def reference_ids(fact: dict) -> set[str]:
    values = fact.get("reference_ids") or [fact.get("reference_id")]
    return {value for value in values if isinstance(value, str)}


def literal_condition_supported(condition: str, evidence: str) -> bool:
    """Reject invented point/qualifier text, allowing literal fragment assembly.

    The product stores condition text as source fragments. Order-preserving token
    reconstruction permits a leading condition and a later point without adding
    a point or word absent from the annotated relation's required evidence span.
    Excluded points remain permitted text when they actually occur in that span.
    """
    token = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+|[=<>°+−-]", re.UNICODE)
    wanted = token.findall(condition.casefold())
    available = iter(token.findall(evidence.casefold()))
    return all(any(candidate == item for candidate in available) for item in wanted)


def condition_points(text: str) -> set[tuple[str | None, Decimal, str]]:
    number = r"[+\-−]?\d+(?:[.,]\d+)?"
    unit = r"°C|K|mV|V|mA|A"
    patterns = [re.compile(r"(?<!\w)(?P<symbol>[A-Za-z][A-Za-z0-9_+\-]{0,15})\s*=\s*"
                           + rf"(?P<value>{number})\s*(?P<unit>{unit})(?!\w)"),
                re.compile(r"(?<!\w)(?i:at|à|a|for|pour)\s+" + rf"(?P<value>{number})\s*(?P<unit>{unit})(?!\w)")]
    result = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            symbol = match.groupdict().get("symbol")
            value, name = decimal(match["value"]), match["unit"]
            if name in {"°C", "K"}:
                value += Decimal("273.15") if name == "°C" else 0
                name = "temperature"
            elif name in UNIT_SCALES:
                name, scale = UNIT_SCALES[name]
                value *= scale
            result.add((symbol, value, name))
    return result


def relation_matches(gold: dict, observed: dict, *, forbidden: bool = False, evidence_text: str | None = None) -> bool:
    """An erased qualifier cannot hide a forbidden numeric operand.

    Positive matching requires its annotated subject, role, property and point.
    Forbidden matching identifies the source number even if a defective parser
    loses or rewrites the condition/role/subject that made it inapplicable.
    """
    if (gold["reference_id"] not in reference_ids(observed)
            or observed.get("document_id") != gold["document_id"]
            or observed.get("quantity") != gold["quantity"]
            or base_values(observed) != base_values(gold)):
        return False
    subjects = {str(s).casefold() for s in observed.get("subjects", [])}
    if subjects and gold["subject"].casefold() not in subjects:
        return False
    if forbidden:
        return True
    if subjects != {gold["subject"].casefold()}:
        return False
    if observed.get("role") != gold.get("role") or observed.get("bound_role") is not None:
        return False
    permitted_properties = {gold["property"]} if gold.get("property") is not None else set()
    if (observed.get("property") != gold.get("property")
            or not set(observed.get("properties", [])) <= permitted_properties):
        return False
    condition = observed.get("condition", "")
    if (not isinstance(condition, str) or not literal_condition_supported(condition, gold["annotation_span"]["text"])
            or not condition_points(condition) <= condition_points(evidence_text or gold["annotation_span"]["text"])):
        return False
    for point in gold.get("point_conditions", []):
        pattern = re.compile(r"(?<!\w)" + re.escape(point["symbol"]) + r"\s*=\s*([+\-−]?\d+(?:[.,]\d+)?)\s*(°C|K)(?!\w)")
        target = decimal(point["value"]) + (Decimal("273.15") if point["unit"] == "°C" else 0)
        matches = [decimal(m[1]) + (Decimal("273.15") if m[2] == "°C" else 0) for m in pattern.finditer(condition)]
        if target not in matches:
            return False
    return True


def literal_checks(case: dict, result: dict) -> list[dict]:
    text = result.get("text", "")
    references = {source["id"]: source for source in case["sources"]}
    segments = result.get("support_ledger", {}).get("segments", [])
    markers = result.get("citation_spans", [])
    checks = []
    for literal in case["expected"]["required_literals"]:
        alternatives = literal.get("alternative_reference_ids", [literal["reference_id"]])
        valid_references = []
        for reference in alternatives:
            source_ids = set(references[reference]["source_ids"])
            linked_segments = [segment for segment in segments
                               if reference in segment.get("reference_ids", [])
                               and bool(source_ids & set(segment.get("source_ids", [])))
                               and type(segment.get("start_offset")) is int and type(segment.get("end_offset")) is int
                               and 0 <= segment["start_offset"] <= segment["end_offset"] <= len(text)
                               and literal["text"] in text[segment["start_offset"]:segment["end_offset"]]]
            locally_cited = False
            for segment in linked_segments:
                following_start = min((s["start_offset"] for s in segments
                                       if type(s.get("start_offset")) is int and s["start_offset"] >= segment["end_offset"]
                                       and s is not segment and s.get("kind") != "citation"), default=len(text))
                for marker in markers:
                    start, end = marker.get("start_offset"), marker.get("end_offset")
                    if (marker.get("source_id") not in source_ids or type(start) is not int or type(end) is not int
                            or not segment["end_offset"] <= start < end <= following_start
                            or text[start:end] != "[" + marker["source_id"] + "]"):
                        continue
                    # Other citation markers may precede this one in the same
                    # segment's citation tail, but unrelated prose may not.
                    between = re.sub(r"\[[^\]\n]+\]", "", text[segment["end_offset"]:start]).strip()
                    citation_segments = [s for s in segments if s.get("kind") == "citation"
                                         and s.get("start_offset") == start and s.get("end_offset") == end]
                    citation_identity_ok = (not citation_segments or any(reference in s.get("reference_ids", [])
                                            and marker["source_id"] in s.get("source_ids", []) for s in citation_segments))
                    if not between and citation_identity_ok:
                        locally_cited = True
            if locally_cited:
                valid_references.append(reference)
        checks.append({"literal": literal, "text_retained": literal["text"] in text,
                       "linked_citation_retained": bool(valid_references), "valid_reference_ids": valid_references})
    return checks


def classify(case: dict, result: dict) -> dict[str, Any]:
    expected = case["expected"]
    assessment = result.get("answer_contract") or {}
    facts = assessment.get("matched_relations", [])
    gold_by_id = {g["id"]: g for g in expected["allowed_relations"]}
    def evidence_for(gold):
        spans = [literal["text"] for literal in expected["required_literals"]
                 if gold["reference_id"] in literal.get("alternative_reference_ids", [literal["reference_id"]])]
        return "\n".join(spans) or gold["annotation_span"]["text"]
    matched_gold = {gid: [index for index, f in enumerate(facts) if relation_matches(g, f, evidence_text=evidence_for(g))]
                    for gid, g in gold_by_id.items()}
    forbidden = [{"gold_id": g["id"], "matched_relation_indexes": indexes}
                 for g in expected["forbidden_relations"]
                 if (indexes := [i for i, f in enumerate(facts) if relation_matches(g, f, forbidden=True)])]
    annotated_indexes = {index for indexes in matched_gold.values() for index in indexes}
    unexpected = [i for i in range(len(facts)) if i not in annotated_indexes]
    required_groups = [{"gold_ids": group, "covered": any(matched_gold.get(gid) for gid in group)}
                       for group in expected["required_relation_groups"]]
    comparisons = assessment.get("comparisons", [])
    conclusion_rows = []
    required_comparisons = {g["id"]: False for g in expected["comparisons"] if g["required"]}
    for index, observed in enumerate(comparisons):
        status = observed.get("status")
        conclusion = status if status in CONCLUSIONS else None
        refs = reference_ids(observed)
        allowed = []
        if conclusion:
            for gold in expected["comparisons"]:
                gold_refs = {gold_by_id[gid]["reference_id"] for group in gold["operand_groups"] for gid in group}
                groups_bound = all(any(matched_gold.get(gid) and gold_by_id[gid]["reference_id"] in refs for gid in group)
                                   for group in gold["operand_groups"])
                operands = [gold_by_id[gid] for group in gold["operand_groups"] for gid in group if gold_by_id[gid]["reference_id"] in refs]
                labels_ok = comparison_labels_match(observed, operands) and comparison_groups_match(observed, gold, gold_by_id)
                if (gold["conclusion"] == conclusion and observed.get("numeric_agreement") == conclusion
                        and groups_bound and refs <= gold_refs and labels_ok):
                    allowed.append(gold["id"])
                    if gold["required"]:
                        required_comparisons[gold["id"]] = True
        conclusion_rows.append({"index": index, "status": status, "numeric_agreement": observed.get("numeric_agreement"),
                                "reference_ids": sorted(refs), "conclusion": conclusion, "matched_gold_comparisons": allowed,
                                "forbidden": bool(conclusion and (conclusion in expected["forbidden_comparison_conclusions"] or not allowed))})
    literal = literal_checks(case, result)
    status = assessment.get("status", "missing")
    complete_claimed = status == "covered"
    obligation_consistency = not complete_claimed or all(o.get("covered") is True for o in assessment.get("obligations", []))
    status_allowed = status in expected["status_classes"]
    all_groups = all(g["covered"] for g in required_groups)
    comparisons_ok = all(required_comparisons.values()) and not any(c["forbidden"] for c in conclusion_rows)
    support_correct = complete_claimed == expected["exact_support"] and status_allowed
    semantic = support_correct and obligation_consistency and not forbidden and not unexpected and all_groups and comparisons_ok
    literal_ok = all(c["text_retained"] and c["linked_citation_retained"] for c in literal)
    return {
        "status": status, "complete_support_claimed": complete_claimed, "exact_support_decision_correct": support_correct,
        "status_allowed": status_allowed, "unassessed": status in {"unassessed", "missing"},
        "claimed_coverage_consistent_with_obligations": obligation_consistency,
        "matched_gold_relations": matched_gold, "forbidden_operands": forbidden, "unexpected_matched_relation_indexes": unexpected,
        "required_relation_groups": required_groups, "all_required_relation_groups_covered": all_groups,
        "comparison_observations": conclusion_rows, "required_comparisons_satisfied": required_comparisons,
        "comparisons_correct": comparisons_ok, "literal_checks": literal,
        "literal_texts_retained": sum(c["text_retained"] for c in literal),
        "literal_citations_retained": sum(c["linked_citation_retained"] for c in literal), "literal_total": len(literal),
        "semantic_passed": semantic, "passed": semantic and literal_ok,
        "any_forbidden_operand": bool(forbidden), "any_unexpected_relation": bool(unexpected),
        "any_forbidden_conclusion": any(c["forbidden"] for c in conclusion_rows),
    }


def comparison_labels_match(comparison: dict, operands: list[dict]) -> bool:
    """Declared labels cannot invent a subject, quantity, property or document.

    Missing optional labels are inferred only from independently bound operands;
    this does not impose a new product schema or a particular axis field.
    """
    if not operands:
        return False
    for field, gold_field in (("quantity", "quantity"), ("property", "property")):
        if field in comparison and comparison[field] not in {g.get(gold_field) for g in operands}:
            return False
    if "document_ids" in comparison and set(comparison["document_ids"]) != {g["document_id"] for g in operands}:
        return False
    declared = {str(s).casefold() for s in comparison.get("subjects", [])}
    if comparison.get("subject") is not None:
        declared.add(str(comparison["subject"]).casefold())
    return not declared or declared == {g["subject"].casefold() for g in operands}


def comparison_groups_match(observed: dict, gold: dict, facts: dict) -> bool:
    groups = [{"subjects": {facts[gid]["subject"].casefold() for gid in group},
               "refs": {facts[gid]["reference_id"] for gid in group}} for group in gold["operand_groups"]]
    axis = "subjects" if len({tuple(sorted(g["subjects"])) for g in groups}) > 1 else "documents"
    if "comparison_axis" in observed and observed["comparison_axis"] != axis:
        return False
    if "operand_groups" not in observed:
        return True
    actual = observed["operand_groups"]
    if not isinstance(actual, list) or not actual or not all(isinstance(g, dict) for g in actual):
        return False
    represented = set()
    all_refs = set()
    for operand in actual:
        subjects = {str(s).casefold() for s in operand.get("subjects", [])}
        if operand.get("subject") is not None:
            subjects.add(str(operand["subject"]).casefold())
        refs = reference_ids(operand)
        matches = [i for i, g in enumerate(groups) if refs and refs <= g["refs"] and subjects == g["subjects"]]
        if not matches:
            return False
        represented.update(matches)
        all_refs.update(refs)
    return len(represented) == len(groups) and all_refs == reference_ids(observed)


def summarize(records: list[dict]) -> dict:
    positive = [r for r in records if r["expected"]["exact_support"]]
    negative = [r for r in records if not r["expected"]["exact_support"]]
    assessed = any(r["observed"].get("complete_support_claimed") is not None for r in records)
    false_accepts = sum(r["observed"].get("complete_support_claimed") is True for r in negative)
    false_rejects = sum(r["observed"].get("complete_support_claimed") is not True for r in positive)
    times = [t["latency_ms"] for r in records for t in r["trials"]]
    total_literals = sum(r["observed"].get("literal_total", 0) for r in records)
    return {
        "cases": len(records), "positive_cases": len(positive), "negative_cases": len(negative),
        "false_complete_acceptances": false_accepts if assessed else None,
        "false_complete_acceptance_rate": false_accepts / len(negative) if assessed and negative else None,
        "positive_status_rejections": false_rejects if assessed else None,
        "positive_status_rejection_rate": false_rejects / len(positive) if assessed and positive else None,
        "positive_fully_correct": sum(r["observed"].get("passed") is True for r in positive) if assessed else None,
        "positive_fully_correct_rate": sum(r["observed"].get("passed") is True for r in positive) / len(positive) if assessed and positive else None,
        "cases_passed": sum(r["observed"].get("passed") is True for r in records) if assessed else None,
        "cases_with_forbidden_operands": sum(r["observed"].get("any_forbidden_operand", False) for r in records) if assessed else None,
        "cases_with_unexpected_relations": sum(r["observed"].get("any_unexpected_relation", False) for r in records) if assessed else None,
        "cases_with_forbidden_conclusions": sum(r["observed"].get("any_forbidden_conclusion", False) for r in records) if assessed else None,
        "unassessed_cases": sum(r["observed"].get("unassessed", False) for r in records),
        "primary_errors": sum("error" in r["trials"][0] for r in records),
        "cases_with_any_error": sum(any("error" in t for t in r["trials"]) for r in records),
        "any_repeat_false_acceptance_cases": sum(r["any_repeat_false_acceptance"] for r in negative) if assessed else None,
        "any_repeat_forbidden_operand_cases": sum(r["any_repeat_forbidden_operand"] for r in records) if assessed else None,
        "any_repeat_unexpected_relation_cases": sum(r["any_repeat_unexpected_relation"] for r in records) if assessed else None,
        "any_repeat_forbidden_conclusion_cases": sum(r["any_repeat_forbidden_conclusion"] for r in records) if assessed else None,
        "variable_outcomes": sum(r["outcome_varies"] for r in records),
        "all_repeats_passed_cases": sum(r["all_trials_passed"] for r in records) if assessed else None,
        "statuses": dict(Counter(r["observed"].get("status", "error") for r in records)),
        "required_literal_total": total_literals,
        "required_literal_texts_retained": sum(r["observed"].get("literal_texts_retained", 0) for r in records),
        "required_literal_citations_retained": sum(r["observed"].get("literal_citations_retained", 0) for r in records),
        "latency_ms_median": statistics.median(times) if times else None,
        "latency_ms_p95_nearest_rank": sorted(times)[math.ceil(.95 * len(times)) - 1] if times else None,
        "latency_ms_max": max(times) if times else None,
        "repeats_are_not_independent_cases": True,
    }


def finish_trials(entry: dict, trials: list[dict]) -> None:
    first = trials[0]
    entry["trials"] = trials
    entry["observed"] = first["observed"]
    for name in ("result", "error"):
        if name in first:
            entry[name] = first[name]
    entry["outcome_varies"] = any(t["observed"] != first["observed"] for t in trials[1:])
    entry["all_trials_passed"] = all(t["observed"].get("passed") is True and "error" not in t for t in trials)
    entry["any_repeat_false_acceptance"] = not entry["expected"]["exact_support"] and any(t["observed"].get("complete_support_claimed") is True for t in trials)
    for field in ("forbidden_operand", "unexpected_relation", "forbidden_conclusion"):
        entry["any_repeat_" + field] = any(t["observed"].get("any_" + field, False) for t in trials)


def extractive_result(case: dict) -> dict:
    parts: list[str] = []
    segments = []
    citations = []
    cursor = 0
    for source in case["sources"]:
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(source["text"])
        cursor += len(source["text"])
        segments.append({"kind": "reference", "reference_ids": [source["id"]], "source_ids": source["source_ids"],
                         "start_offset": start, "end_offset": cursor})
        for source_id in source["source_ids"]:
            parts.append(" ")
            cursor += 1
            marker = "[" + source_id + "]"
            citations.append({"source_id": source_id, "start_offset": cursor, "end_offset": cursor + len(marker)})
            segments.append({"kind": "citation", "reference_ids": [source["id"]], "source_ids": [source_id],
                             "start_offset": cursor, "end_offset": cursor + len(marker)})
            parts.append(marker)
            cursor += len(marker)
    return {"text": "".join(parts), "answer_contract": None, "support_validation": None,
            "support_ledger": {"segments": segments}, "citation_spans": citations}


def run(root: Path, fixture_path: Path, label: str, mode: str, repeats: int) -> dict:
    root = root.resolve(strict=True)
    fixture = load_fixture(fixture_path)
    if mode not in {"contract", "extractive_all"} or not 1 <= repeats <= 20:
        raise ValueError("Unsupported mode/repeats")
    if any(n == "services" or n.startswith("services.") for n in sys.modules):
        raise ValueError("A fresh subprocess is required per application revision")
    sources_before = legacy.source_manifest(root)
    dependencies = [Path(__file__), Path(legacy.__file__)]
    harness_before = {str(p.relative_to(EVALUATOR_ROOT)): legacy.digest(p) for p in dependencies}
    fixture_sha = legacy.digest(fixture_path)
    sys.path.insert(0, str(root))
    contract_module = importlib.import_module("services.api.answer_contract")
    structured = importlib.import_module("services.api.structured_answer")
    for name, module in sys.modules.copy().items():
        filename = getattr(module, "__file__", None)
        if name.startswith("services.") and filename and not Path(filename).resolve().is_relative_to(root):
            raise ValueError("Product import escaped requested revision: " + name)
    records = []
    process = psutil.Process()
    rss_start = rss_peak = process.memory_info().rss
    tracemalloc.start()
    try:
        for case in fixture["cases"]:
            entry = {"id": case["id"], "group": case["group"], "category": case["category"], "language": case["language"],
                     "question": case["question"], "expected": case["expected"], "sources": case["sources"], "rationale": case["rationale"]}
            trials = []
            for index in range(repeats):
                trial: dict[str, Any] = {"repeat_index": index}
                current, _ = tracemalloc.get_traced_memory()
                tracemalloc.reset_peak()
                start = time.perf_counter_ns()
                try:
                    if mode == "extractive_all":
                        result = extractive_result(case)
                        checks = literal_checks(case, result)
                        observed = {"status": "unassessed_quotes", "complete_support_claimed": None, "passed": None,
                                    "literal_total": len(checks), "literal_texts_retained": sum(c["text_retained"] for c in checks),
                                    "literal_citations_retained": sum(c["linked_citation_retained"] for c in checks), "literal_checks": checks}
                    else:
                        references = copy.deepcopy(case["sources"])
                        for source in references:
                            source["document_name"] = source["document_id"]
                        required = tuple(case["scope"]["document_ids"])
                        contract = contract_module.AnswerContract(case["question"], case["mode"], {})
                        cat = structured.Catalogue(case["mode"], references, contract, required_documents=required)
                        plan = json.dumps({"references": [r["id"] for r in references], "comparisons": []})
                        result = cat.render(cat.validate(plan), legacy.CharacterCounterDouble(), 5000, required)
                        observed = classify(case, result)
                    trial.update(result=result, observed=observed)
                except Exception as error:
                    trial["error"] = {"type": type(error).__name__, "message": str(error)}
                    trial["observed"] = {"status": "error", "complete_support_claimed": False if mode == "contract" else None,
                                         "passed": False, "literal_total": len(case["expected"]["required_literals"])}
                finally:
                    trial["latency_ms"] = (time.perf_counter_ns() - start) / 1_000_000
                    trial["python_allocation_peak_bytes"] = max(0, tracemalloc.get_traced_memory()[1] - current)
                    rss_peak = max(rss_peak, process.memory_info().rss)
                    trials.append(trial)
            finish_trials(entry, trials)
            records.append(entry)
    finally:
        tracemalloc.stop()
    after = legacy.source_manifest(root)
    changed = [name for name in sorted(set(sources_before) | set(after)) if sources_before.get(name) != after.get(name)]
    harness_after = {str(p.relative_to(EVALUATOR_ROOT)): legacy.digest(p) for p in dependencies}
    valid = not changed and harness_before == harness_after and fixture_sha == legacy.digest(fixture_path)
    return {"schema_version": 1, "protocol_id": fixture["protocol_id"], "split": fixture["split"],
            "created_utc": datetime.now(UTC).isoformat(), "label": label, "mode": mode, "repeats": repeats,
            "fixture_sha256": fixture_sha, "harness_dependencies": harness_before,
            "application_root": str(root), "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_manifest": sources_before, "source_manifest_after": after, "source_changes": changed,
            "sources_unchanged": not changed, "harness_unchanged": harness_before == harness_after,
            "fixture_unchanged": fixture_sha == legacy.digest(fixture_path), "measurement_valid": valid,
            "environment": {"python": sys.version, "platform": platform.platform()}, "annotation": fixture["annotation"],
            "doubles": ["CharacterCounterDouble", "all-authorized-reference selector"],
            "not_executed": ["extraction", "retrieval", "embeddings", "Qdrant", "4B inference", "HTTP", "route decision R3"],
            "quality_primary": "first trial fixed in advance; all trials and errors retained; any later unsafe outcome fails repeat gate",
            "metrics_scope": "Whole-question support decisions, independently annotated operands/comparison axes, required literal/citation fidelity; no general entailment claim.",
            "latency_scope": "Catalogue/render and oracle with tracemalloc enabled, not native latency; nearest-rank p95 across repeats.",
            "memory": {"rss_start_bytes": rss_start, "rss_sampled_peak_bytes": rss_peak,
                       "scope": "whole evaluator process sampled after each trial, not native service RAM"},
            "summary": summarize(records) if valid else {"status": "INVALID_SOURCE_IDENTITY", "not_scored": True, "cases_recorded": len(records)},
            "groups": {group: summarize([r for r in records if r["group"] == group]) for group in sorted({r["group"] for r in records})} if valid else {},
            "cases": records}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=["contract", "extractive_all"], default="contract")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refuse to overwrite an earlier measurement")
    result = run(args.application_root, args.fixtures, args.label, args.mode, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "measurement_valid": result["measurement_valid"], "summary": result["summary"]}, ensure_ascii=False))
    if not result["measurement_valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
