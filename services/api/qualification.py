"""Evaluate retrieval and final evidence through the real protected local API.

This runner never imports model engines or calls Ollama. It consumes separately
resolved immutable source annotations; unresolved evidence is not a success.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
from urllib.parse import urlparse

import httpx


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def wilson(successes, total):
    if not 0 <= successes <= total:
        raise ValueError("Invalid binary denominator")
    if not total:
        return {"successes": successes, "denominator": total, "rate": None, "interval_95": None, "method": "Wilson per question"}
    z = 1.959963984540054
    p, denominator = successes / total, 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return {"successes": successes, "denominator": total, "rate": p, "interval_95": [max(0, center - radius), min(1, center + radius)], "method": "Wilson per question"}


def bootstrap_units(rows, key, iterations=2000, seed=20260930):
    eligible = [row for row in rows if row.get("expected_unit_count", 0) and row.get("status") == "EVALUATED"]
    total = sum(row["expected_unit_count"] for row in eligible)
    covered = sum(row[key] for row in eligible)
    if not eligible:
        return {"covered_units": 0, "expected_units": 0, "rate": None, "interval_95": None, "method": "bootstrap by question", "seed": seed, "iterations": iterations}
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sample = rng.choices(eligible, k=len(eligible))
        estimates.append(sum(row[key] for row in sample) / sum(row["expected_unit_count"] for row in sample))
    estimates.sort()
    def quantile(p):
        index = (len(estimates) - 1) * p
        low = math.floor(index)
        return estimates[low] + (estimates[min(low + 1, len(estimates) - 1)] - estimates[low]) * (index - low)
    return {"covered_units": covered, "expected_units": total, "rate": covered / total, "interval_95": [quantile(.025), quantile(.975)],
            "method": "bootstrap by question; units of one question stay grouped", "seed": seed, "iterations": iterations,
            "limit": "Question bootstrap does not model additional dependence between questions of one documentary family."}


def interval_covers(intervals, start, end):
    cursor = start
    for first, last in sorted(intervals):
        if first > cursor:
            return False
        cursor = max(cursor, last)
        if cursor >= end:
            return True
    return cursor >= end


def span_covered(span, sources):
    intervals = []
    for source in sources:
        if source.get("version_id") != span["version_id"] or source.get("extraction_revision_id") != span["extraction_revision_id"]:
            continue
        if span.get("generation_id") and source.get("generation_id") != span["generation_id"]:
            continue
        for block in source.get("blocks", []):
            if (block.get("id", block.get("block_id")) != span["block_id"] or block.get("source_text_hash") != span["source_text_hash"]
                    or block.get("page_index") != span["page_index"] or block.get("extraction_revision_id") != span["extraction_revision_id"]):
                continue
            start, end = block["start_offset"], block["end_offset"]
            first, last = max(start, span["start_offset"]), min(end, span["end_offset"])
            if first < last and block["text"][first - start:last - start] == span["text"][first - span["start_offset"]:last - span["start_offset"]]:
                intervals.append((first, last))
    return interval_covers(intervals, span["start_offset"], span["end_offset"])


def unit_covered(unit, sources):
    alternatives = [unit] + [alternative for alternative in unit.get("alternatives", []) if isinstance(alternative, dict)]
    return any(alternative.get("resolved_spans") and all(span_covered(span, sources) for span in alternative["resolved_spans"]) for alternative in alternatives)


def scope_leaks(sources, snapshot):
    leaks = []
    for source in sources:
        generation = source.get("generation_id")
        reason = None
        if (generation not in snapshot.get("generations", []) or source.get("version_id") != snapshot.get("versions", {}).get(generation)
                or source.get("document_id") != snapshot.get("documents", {}).get(generation)):
            reason = "unauthorized_generation_version_document"
        for block in source.get("blocks", []):
            if snapshot.get("page_indices") is not None and block.get("page_index") not in snapshot["page_indices"]:
                reason = "unauthorized_page"
            if snapshot.get("block_ids") is not None and block.get("id") not in snapshot["block_ids"]:
                reason = "unauthorized_block"
            if snapshot.get("spans"):
                intervals = [(span["startOffset"], span["endOffset"]) for span in snapshot["spans"] if span["blockId"] == block.get("id")]
                if not interval_covers(intervals, block["start_offset"], block["end_offset"]):
                    reason = "unauthorized_selection_offsets"
        if source.get("text") != "\n".join(block["text"] for block in source.get("blocks", [])):
            reason = "source_text_not_derived_from_authorized_blocks"
        if reason:
            leaks.append({"chunk_id": source.get("chunk_id"), "document_id": source.get("document_id"), "reason": reason})
    return leaks


QUESTION_DYNAMIC = {"scope_resolved", "versions_snapshot", "annotation_state"}
UNIT_DYNAMIC = {"version_id", "extraction_revision_id", "generation_id", "resolved_spans", "resolution_status", "resolution_warnings", "resolution_errors"}


def immutable_question(question):
    result = {key: value for key, value in question.items() if key not in QUESTION_DYNAMIC}
    result["expected_units"] = [{key: value for key, value in unit.items() if key not in UNIT_DYNAMIC} for unit in question.get("expected_units", [])]
    return result


def verify_annotations(source, resolved):
    originals, annotated = source.get("questions", []), resolved.get("questions", [])
    if len(originals) != len(annotated) or any(immutable_question(original) != immutable_question(question) for original, question in zip(originals, annotated, strict=True)):
        raise ValueError("Resolution changed a frozen question, expected fact, source hash or evidence requirement")


def evaluate_question(question, response):
    expected = question.get("expected_units", [])
    top10 = response.get("retrieval_top10", [])
    context = response.get("context_sources", [])
    covered_top5 = [index for index, unit in enumerate(expected) if unit_covered(unit, top10[:5])]
    covered_top10 = [index for index, unit in enumerate(expected) if unit_covered(unit, top10)]
    covered_context = [index for index, unit in enumerate(expected) if unit_covered(unit, context)]
    first_evidence_rank = next((rank for rank, candidate in enumerate(top10, 1) if any(unit_covered(unit, [candidate]) for unit in expected)), None)
    leaks = scope_leaks(top10 + context, response.get("scope_snapshot", {}))
    allowed_documents = set(question.get("scope_resolved", {}).get("documentIds", []))
    frozen_versions = {version["document_id"]: version for version in question.get("versions_snapshot", [])}
    for source in top10 + context:
        expected_version = frozen_versions.get(source.get("document_id"))
        if allowed_documents and source.get("document_id") not in allowed_documents:
            leaks.append({"chunk_id": source.get("chunk_id"), "reason": "outside_requested_document_scope"})
        elif expected_version and any(expected_version.get(key) and source.get(key) != expected_version[key] for key in ("version_id", "generation_id", "extraction_revision_id")):
            leaks.append({"chunk_id": source.get("chunk_id"), "reason": "outside_frozen_version_revision_generation"})
    return {"question_id": question["id"], "status": "EVALUATED", "answerable": question["answerable"], "category": question["category"],
            "language": question.get("language"), "expected_unit_count": len(expected), "top5_covered_units": len(covered_top5), "top10_covered_units": len(covered_top10), "context_covered_units": len(covered_context),
            "top5_covered_unit_indices": covered_top5, "top10_covered_unit_indices": covered_top10, "context_covered_unit_indices": covered_context,
            "first_evidence_rank": first_evidence_rank, "reciprocal_rank": 1 / first_evidence_rank if first_evidence_rank else 0,
            "scope_leakage_count": len(leaks), "scope_leaks": leaks, "state": response["state"],
            "response": response, "quality_limit": "Retrieval/context only: no answer accuracy, citation-use or correct-abstention claim without generation."}


def summary(rows, include_categories=True):
    evaluated = [row for row in rows if row["status"] == "EVALUATED"]
    answerable = [row for row in evaluated if row["answerable"] and row["expected_unit_count"]]
    recall5 = bootstrap_units(answerable, "top5_covered_units")
    recall = bootstrap_units(answerable, "top10_covered_units")
    coverage = bootstrap_units(answerable, "context_covered_units")
    macro = {name: {"denominator_questions": len(answerable),
                    "mean": sum(row[key] / row["expected_unit_count"] for row in answerable) / len(answerable) if answerable else None,
                    "method": "Mean of per-question evidence-unit coverage; micro aggregate controls the acceptance threshold"}
             for name, key in (("recall_at_5", "top5_covered_units"), ("recall_at_10", "top10_covered_units"), ("evidence_coverage_at_context", "context_covered_units"))}
    result = {"requested_questions": len(rows), "evaluated_questions": len(evaluated), "unresolved_questions": sum(row["status"] == "UNRESOLVED" for row in rows),
            "error_questions": sum(row["status"] == "ERROR" for row in rows), "answerable_evaluated_questions": len(answerable),
            "recall_at_5": recall5, "recall_at_10": recall, "evidence_coverage_at_context": coverage, "per_question_means": macro,
            "mrr_at_10": {"denominator_questions": len(answerable), "mean": sum(row["reciprocal_rank"] for row in answerable) / len(answerable) if answerable else None,
                          "method": "Reciprocal rank of the first individual top10 candidate covering every span of any required evidence unit or admitted alternative; zero if none"},
            "all_units_recalled_at_5_questions": wilson(sum(row["top5_covered_units"] == row["expected_unit_count"] for row in answerable), len(answerable)),
            "all_units_recalled_questions": wilson(sum(row["top10_covered_units"] == row["expected_unit_count"] for row in answerable), len(answerable)),
            "all_units_in_context_questions": wilson(sum(row["context_covered_units"] == row["expected_unit_count"] for row in answerable), len(answerable)),
            "scope_safe_questions": wilson(sum(row["scope_leakage_count"] == 0 for row in evaluated), len(evaluated)),
            "scope_leakage_count": sum(row["scope_leakage_count"] for row in evaluated),
            "generation_metrics": {"answer_correctness": "NOT_RUN", "supported_claim_ratio": "NOT_RUN", "correct_abstention": "NOT_RUN", "model_called": False}}
    if include_categories:
        result["by_category"] = {category: summary([row for row in rows if row.get("category") == category], False)
                                 for category in sorted({row["category"] for row in rows if row.get("category")})}
        result["by_language"] = {language: summary([row for row in rows if row.get("language") == language], False)
                                 for language in sorted({row["language"] for row in rows if row.get("language")})}
    return result


def run(dataset_path, source_path, output_path, base_url, split, freeze_path=None, limit=None):
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError("Only a credential-free local loopback API is authorized")
    token = os.environ.get("RAG_CONTROL_TOKEN")
    if not token:
        raise ValueError("RAG_CONTROL_TOKEN is required in the environment; never pass it in URL or command arguments")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    verify_annotations(source, dataset)
    if any(question.get("split") != split for question in dataset["questions"]):
        raise ValueError("Dataset mixes development and final questions")
    if split == "final":
        if limit is not None or not freeze_path:
            raise ValueError("Final requires its immutable freeze and all questions")
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        if canonical_sha(source) != freeze["canonical_sha256"] or len(dataset["questions"]) != freeze["questions"]:
            raise ValueError("Protected final source no longer matches its freeze")
        if any(question.get("annotation_state") != "RESOLVED" for question in dataset["questions"]):
            raise ValueError("Final annotations must all resolve before exposing held-out results")
    questions = dataset["questions"][:limit] if limit else dataset["questions"]
    if output_path.exists() or output_path.resolve() in {dataset_path.resolve(), source_path.resolve()}:
        raise ValueError("Choose a new evidence output path; existing results and source datasets are immutable")
    rows = []
    headers = {"X-RAG-Control-Token": token}
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, trust_env=False, timeout=60) as client:
        diagnostics_response = client.get("/api/v1/diagnostics")
        diagnostics_response.raise_for_status()
        diagnostics = diagnostics_response.json()
        identity = {key: diagnostics.get(key) for key in ("profile_sha256", "selector_sha256", "dense_identity", "llm_tokenizer_identity", "qdrant_collection")}
        identity_sha = canonical_sha(identity)
        receipt_path = output_path.parent / "final-retrieval-identity-receipt.json"
        if split == "final" and receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt["identity_sha256"] != identity_sha or receipt["source_sha256"] != canonical_sha(source):
                raise ValueError("Final identity already sealed; tuning against held-out results is forbidden")
        if split == "final" and not receipt_path.exists():
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            with receipt_path.open("x", encoding="utf-8") as receipt_file:
                json.dump({"identity_sha256": identity_sha, "source_sha256": canonical_sha(source), "identity": identity}, receipt_file, ensure_ascii=False, indent=2)
        for question in questions:
            if question.get("annotation_state") != "RESOLVED" or not question.get("scope_resolved") or any(not unit.get("resolved_spans") for unit in question.get("expected_units", [])):
                rows.append({"question_id": question["id"], "category": question["category"], "language": question.get("language"), "status": "UNRESOLVED", "reason": "Independent real extraction annotations are not resolved"})
                continue
            body = {"question": question["question"], "scope": question["scope_resolved"], "mode": question.get("mode", "question")}
            if question.get("prior_user_question"):
                body["prior_user_question"] = question["prior_user_question"]
            try:
                response = client.post("/api/v1/admin/evaluation/context", json=body)
                response.raise_for_status()
                payload = response.json()
                if (payload.get("model_called") is not False or payload.get("profile_sha256") != identity["profile_sha256"]
                        or (payload.get("state") == "context_ready" and any(payload.get(key) != identity[key] for key in ("selector_sha256", "dense_identity", "llm_tokenizer_identity")))):
                    raise ValueError("Evaluation runtime drift or unexpected generation")
                rows.append(evaluate_question(question, payload))
            except (httpx.HTTPError, ValueError, KeyError) as error:
                rows.append({"question_id": question["id"], "category": question["category"], "language": question.get("language"), "status": "ERROR", "error_class": type(error).__name__})
    metrics = summary(rows)
    complete = len(rows) == 100 and metrics["evaluated_questions"] == 100
    target = metrics["recall_at_10"]["rate"] is not None and metrics["recall_at_10"]["rate"] >= .9 and metrics["evidence_coverage_at_context"]["rate"] >= .9 and metrics["scope_leakage_count"] == 0
    report = {"date_utc": datetime.now(timezone.utc).isoformat(), "split": split, "phase": "retrieval_and_final_context_no_generation", "status": "PASS" if complete and target else ("FAIL" if complete else "INCOMPLETE"),
              "source_dataset_sha256": canonical_sha(source), "resolved_annotations_sha256": canonical_sha(dataset), "identity": identity, "diagnostics": diagnostics, "metrics": metrics, "questions": rows,
              "limits": ["This result does not qualify answers, correct abstention, real LLM token counts or performance on 25000 chunks.", "Unresolved annotations and runtime errors remain explicit; percentages exclude unavailable gold units and cannot produce PASS."]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8785")
    parser.add_argument("--split", choices=["development", "final"], required=True)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    evidence_root = root / "RAG_Local_Agents/reports/backend"
    if not args.output.resolve().is_relative_to(evidence_root) or (args.limit is not None and args.limit < 1):
        parser.error("Output must be a new backend report; positive limit applies only to development")
    try:
        result = run(args.dataset, args.source_dataset, args.output, args.base_url, args.split, args.freeze, args.limit)
    except (ValueError, OSError, httpx.HTTPError, KeyError) as error:
        parser.error(str(error) if isinstance(error, ValueError) else type(error).__name__)
    print(json.dumps({"status": result["status"], "split": result["split"], "metrics": result["metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
