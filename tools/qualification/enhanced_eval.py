"""Analyse EV4B sans appel réseau ni jugement sémantique implicite.

Les annotations et exécutions sont des JSONL distincts. Un jugement absent reste
inconnu ; refus, erreurs et répétitions gardent leurs propres dénominateurs.
Le protocole est dans RAG_Local_Agents/reports/enhanced-4b-protocol-2026-11-07.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qualification.evidence_io import (  # noqa: E402
    LOCAL_QA,
    checked_output,
    file_sha256,
    write_json_exclusive,
)

STATUSES = frozenset({"completed", "refused", "error", "cancelled", "not_run"})
SPLITS = frozenset({"development", "regression", "diagnostic", "holdout"})
METHODS = frozenset({"human", "agent", "rule", "unreviewed"})
FACT_FIELDS = ("correct", "citation_supported", "in_context")
MAX_LINE_BYTES = 2 * 1024 * 1024


def canonical_sha256(value: Any) -> str:
    """Empreinte du JSON canonique, pas des octets HTTP ni des tokens internes."""
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON dupliquée : {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nombre JSON non fini : {value}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Lecture bornée, sans réparation d'un journal partiel ou ambigu."""
    records = []
    with Path(path).open("rb") as stream:
        number = 0
        while raw := stream.readline(MAX_LINE_BYTES + 1):
            number += 1
            if len(raw) > MAX_LINE_BYTES:
                raise ValueError(f"{path}:{number}: ligne supérieure à {MAX_LINE_BYTES} octets")
            if not raw.strip():
                raise ValueError(f"{path}:{number}: ligne vide")
            try:
                record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                    parse_constant=_reject_constant)
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"{path}:{number}: JSON invalide ({error})") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{number}: objet JSON attendu")
            records.append(record)
    return records


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: chaîne non vide attendue")
    return value


def _boolean(value: Any, where: str, *, optional: bool = True) -> None:
    if (optional and value is None) or type(value) is bool:
        return
    raise ValueError(f"{where}: booléen{' ou null' if optional else ''} attendu")


def _number(value: Any, where: str, *, nonnegative: bool = True) -> None:
    if value is None:
        return
    if type(value) not in (int, float) or not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError(f"{where}: nombre fini{' positif ou nul' if nonnegative else ''} attendu")


def _hash(value: Any, where: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{where}: SHA-256 hexadécimal minuscule attendu")


def validate_annotations(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    clusters: dict[str, set[str]] = defaultdict(set)
    for source in records:
        item = dict(source)
        question = _text(item.get("question_id"), "question_id")
        if question in annotations:
            raise ValueError(f"Question dupliquée : {question}")
        document = _text(item.get("document_id"), f"{question}.document_id")
        family = _text(item.get("family_id", document), f"{question}.family_id")
        _text(item.get("question"), f"{question}.question")
        _boolean(item.get("answerable"), f"{question}.answerable", optional=False)
        split = item.get("split")
        if not isinstance(split, str) or split not in SPLITS:
            raise ValueError(f"{question}.split: valeur parmi {sorted(SPLITS)} attendue")
        facts = item.get("required_facts")
        if not isinstance(facts, list):
            raise ValueError(f"{question}.required_facts: liste attendue")
        if bool(facts) != item["answerable"]:
            raise ValueError(f"{question}: faits requis non vides seulement pour une question renseignable")
        ids: set[str] = set()
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError(f"{question}: objet de fait attendu")
            fact_id = _text(fact.get("id"), f"{question}.fact.id")
            _text(fact.get("description"), f"{question}.{fact_id}.description")
            if fact_id in ids:
                raise ValueError(f"{question}: fait dupliqué {fact_id}")
            ids.add(fact_id)
            references = fact.get("references", [])
            if not isinstance(references, list) or any(not isinstance(ref, str) or not ref for ref in references):
                raise ValueError(f"{question}.{fact_id}.references: liste de chaînes attendue")
        _hash(item.get("source_sha256"), f"{question}.source_sha256")
        item["family_id"] = family
        annotations[question] = item
        clusters[f"document:{document}"].add(split)
        clusters[f"family:{family}"].add(split)
    if not annotations:
        raise ValueError("Aucune annotation")
    for cluster, splits in clusters.items():
        if "holdout" in splits and len(splits) > 1:
            raise ValueError(f"Fuite de séparation holdout : {cluster} dans {sorted(splits)}")
    return annotations


def validate_runs(records: Iterable[Mapping[str, Any]], annotations: Mapping[str, Any]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for source in records:
        item = dict(source)
        question = _text(item.get("question_id"), "run.question_id")
        variant = _text(item.get("variant"), f"{question}.variant")
        repeat = item.get("repeat")
        if type(repeat) is not int or repeat < 0:
            raise ValueError(f"{question}.repeat: entier positif ou nul attendu")
        key = (variant, question, repeat)
        if key in seen:
            raise ValueError(f"Exécution dupliquée : {key}")
        seen.add(key)
        if question not in annotations:
            raise ValueError(f"Question sans annotation : {question}")
        if not isinstance(item.get("status"), str) or item["status"] not in STATUSES:
            raise ValueError(f"{key}.status: valeur parmi {sorted(STATUSES)} attendue")
        if item["status"] == "completed":
            if not isinstance(item.get("answer"), str):
                raise ValueError(f"{key}.answer: réponse observée attendue")
            _boolean(item.get("abstained"), f"{key}.abstained", optional=False)
        else:
            _boolean(item.get("abstained"), f"{key}.abstained")
        for field in ("has_false_claims", "has_unsupported_claims"):
            _boolean(item.get(field), f"{key}.{field}")
        for field in ("latency_s", "memory_peak_mib"):
            _number(item.get(field), f"{key}.{field}")
        _number(item.get("selection_score"), f"{key}.selection_score", nonnegative=False)
        facts = item.get("fact_verdicts", {})
        if not isinstance(facts, dict):
            raise ValueError(f"{key}.fact_verdicts: objet attendu")
        allowed = {fact["id"] for fact in annotations[question]["required_facts"]}
        if set(facts) - allowed:
            raise ValueError(f"{key}: faits non annotés {sorted(set(facts) - allowed)}")
        judged = any(item.get(field) is not None for field in ("has_false_claims", "has_unsupported_claims"))
        for fact_id, verdict in facts.items():
            if not isinstance(verdict, dict) or set(verdict) - set(FACT_FIELDS):
                raise ValueError(f"{key}.{fact_id}: champs permis {FACT_FIELDS}")
            for field in FACT_FIELDS:
                _boolean(verdict.get(field), f"{key}.{fact_id}.{field}")
                judged |= verdict.get(field) is not None
            if item["status"] != "completed" and any(verdict.get(f) is not None for f in FACT_FIELDS[:2]):
                raise ValueError(f"{key}: jugement de réponse sans génération terminée")
        judgment = item.get("judgment", {"method": "unreviewed"})
        if not isinstance(judgment, dict) or judgment.get("method") not in METHODS:
            raise ValueError(f"{key}.judgment.method: valeur parmi {sorted(METHODS)} attendue")
        if judged and judgment["method"] == "unreviewed":
            raise ValueError(f"{key}: méthode de jugement requise pour des verdicts renseignés")
        for payload in ("request", "prompt", "context"):
            digest_key = f"{payload}_sha256"
            _hash(item.get(digest_key), f"{key}.{digest_key}")
            if payload in item:
                digest = canonical_sha256(item[payload])
                if item.get(digest_key) not in (None, digest):
                    raise ValueError(f"{key}: empreinte incompatible pour {payload}")
                item[digest_key] = digest
        _hash(item.get("source_sha256"), f"{key}.source_sha256")
        expected = annotations[question].get("source_sha256")
        if expected and item.get("source_sha256") and expected != item["source_sha256"]:
            raise ValueError(f"{key}: source différente de l'annotation")
        item["fact_verdicts"] = facts
        item["judgment"] = judgment
        runs.append(item)
    return runs


def _facts(run: Mapping[str, Any], annotation: Mapping[str, Any], field: str) -> list[bool | None]:
    return [run["fact_verdicts"].get(fact["id"], {}).get(field) for fact in annotation["required_facts"]]


def outcome(run: Mapping[str, Any], annotation: Mapping[str, Any]) -> str:
    if run["status"] != "completed":
        return str(run["status"])
    if run["abstained"]:
        if run.get("has_false_claims") is True:
            return "abstention_with_false_claims"
        return "abstention" if annotation["answerable"] else "correct_abstention"
    if not annotation["answerable"]:
        return "answer_to_unanswerable"
    correct = _facts(run, annotation, "correct")
    if run.get("has_false_claims") is True:
        return "incorrect"
    if any(value is False for value in correct):
        return "partial" if any(value is True for value in correct) else "incomplete"
    if all(value is True for value in correct) and run.get("has_false_claims") is False:
        return "complete"
    return "unreviewed"


def _complete(run: Mapping[str, Any], annotation: Mapping[str, Any]) -> bool | None:
    state = outcome(run, annotation)
    return None if state in {"unreviewed", "not_run"} else state == "complete"


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _distribution(values: list[float]) -> dict[str, Any]:
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "p95": _percentile(values, .95) if values else None, "max": max(values) if values else None}


def risk_coverage_curve(scored: Sequence[tuple[float, bool]], *, denominator: int) -> list[dict[str, Any]]:
    """Risque d'inexactitude/omission ; les groupes ex aequo restent indivisibles."""
    if denominator < len(scored) or denominator < 0:
        raise ValueError("Dénominateur de couverture inférieur au nombre de réponses scorées")
    groups: dict[float, list[bool]] = defaultdict(list)
    for score, correct in scored:
        _number(score, "selection_score", nonnegative=False)
        _boolean(correct, "correct", optional=False)
        groups[score].append(correct)
    points = []
    selected = errors = 0
    for threshold in sorted(groups, reverse=True):
        selected += len(groups[threshold])
        errors += sum(not correct for correct in groups[threshold])
        points.append({"threshold": threshold, "selected": selected, "errors": errors,
                       "coverage": selected / denominator, "risk": errors / selected})
    return points


def summarize_variant(runs: Sequence[Mapping[str, Any]], annotations: Mapping[str, Any]) -> dict[str, Any]:
    submitted = [run for run in runs if run["status"] != "not_run"]
    completed = [run for run in submitted if run["status"] == "completed"]
    answerable = [run for run in submitted if annotations[run["question_id"]]["answerable"]]
    published = [run for run in answerable if run["status"] == "completed" and not run["abstained"]]
    states = Counter(outcome(run, annotations[run["question_id"]]) for run in runs)
    reviewed = [run for run in published if _complete(run, annotations[run["question_id"]]) is not None]
    complete = sum(outcome(run, annotations[run["question_id"]]) == "complete" for run in answerable)
    supported = sum(
        outcome(run, annotations[run["question_id"]]) == "complete"
        and all(v is True for v in _facts(run, annotations[run["question_id"]], "citation_supported"))
        and run.get("has_unsupported_claims") is False
        for run in answerable
    )
    false_reviewed = [run for run in published if run.get("has_false_claims") is not None]
    completed_false_reviewed = [run for run in completed if run.get("has_false_claims") is not None]
    published_false_claim_risk = _ratio(
        sum(run["has_false_claims"] is True for run in false_reviewed), len(false_reviewed)
    )
    context = [v for run in answerable for v in _facts(run, annotations[run["question_id"]], "in_context")]
    context_known = [v for v in context if v is not None]
    scored = [(run["selection_score"], bool(_complete(run, annotations[run["question_id"]])))
              for run in reviewed if run.get("selection_score") is not None]
    memory: dict[str, list[float]] = defaultdict(list)
    for run in submitted:
        if run.get("memory_peak_mib") is not None:
            memory[str(run.get("memory_scope", "unspecified"))].append(run["memory_peak_mib"])
    return {
        "positions": len(runs), "submitted": len(submitted),
        "unique_questions": len({run["question_id"] for run in submitted}),
        "documents": len({annotations[run["question_id"]]["document_id"] for run in submitted}),
        "families": len({annotations[run["question_id"]]["family_id"] for run in submitted}),
        "status_counts": dict(sorted(Counter(run["status"] for run in runs).items())),
        "outcome_counts": dict(sorted(states.items())),
        "judgment_methods": dict(sorted(Counter(run["judgment"]["method"] for run in submitted).items())),
        "answerable_submitted": len(answerable),
        "unanswerable_submitted": len(submitted) - len(answerable),
        "confirmed_complete_per_answerable_submission": _ratio(complete, len(answerable)),
        "complete_accuracy_reviewed_published": _ratio(complete, len(reviewed)),
        "confirmed_complete_and_supported_per_submission": _ratio(supported, len(answerable)),
        "answer_coverage": _ratio(len(published), len(answerable)),
        "incomplete_or_incorrect_risk_reviewed": _ratio(len(reviewed) - complete, len(reviewed)),
        # Preserve the historical metric without silently changing its denominator.
        "false_claim_risk_reviewed": published_false_claim_risk,
        "false_claim_risk_reviewed_published": dict(published_false_claim_risk),
        "false_claim_risk_reviewed_scope": "Completed, non-abstained responses to answerable questions with an explicit has_false_claims verdict only.",
        "false_claim_risk_reviewed_completed": _ratio(
            sum(run["has_false_claims"] is True for run in completed_false_reviewed), len(completed_false_reviewed)
        ),
        "false_claim_risk_reviewed_completed_scope": "All completed responses with an explicit has_false_claims verdict, including abstentions and unanswerable questions; unknown verdicts and non-completed statuses excluded.",
        "completed_responses": len(completed),
        "false_claims_unreviewed_completed": len(completed) - len(completed_false_reviewed),
        "abstentions_with_false_claims": sum(
            run["abstained"] and run.get("has_false_claims") is True for run in completed
        ),
        "unreviewed_published": len(published) - len(reviewed),
        "context_fact_recall_reviewed": _ratio(sum(v is True for v in context_known), len(context_known)),
        "confirmed_context_facts_per_required": _ratio(sum(v is True for v in context), len(context)),
        "context_facts_unreviewed": len(context) - len(context_known),
        "latency_s_by_status": {status: _distribution([run["latency_s"] for run in submitted
                                    if run["status"] == status and run.get("latency_s") is not None])
                                for status in sorted(STATUSES - {"not_run"})},
        "memory_peak_mib_by_scope": {scope: _distribution(values) for scope, values in sorted(memory.items())},
        "risk_coverage": {"score_is_calibrated_probability": False, "scored_reviewed": len(scored),
                          "published_excluded": len(published) - len(scored),
                          "denominator": len(answerable), "points": risk_coverage_curve(scored, denominator=len(answerable))},
        "provenance_missing": {field: sum(not run.get(field) for run in submitted)
                               for field in ("request_sha256", "context_sha256", "source_sha256")},
    }


def repetition_summary(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        if run["status"] != "not_run":
            groups[(run["variant"], run["question_id"])].append(run)
    results = []
    for (variant, question), repeats in sorted(groups.items()):
        if len(repeats) < 2:
            continue
        completed = [run for run in repeats if run["status"] == "completed"]
        hashes = [run.get("request_sha256") for run in repeats]
        results.append({
            "variant": variant, "question_id": question, "repetitions": len(repeats),
            "completed": len(completed), "same_status": len({run["status"] for run in repeats}) == 1,
            "same_request": len(set(hashes)) == 1 if all(hashes) else None,
            "same_answer": len({run["answer"] for run in completed}) == 1 if len(completed) == len(repeats) else None,
        })
    return {"repeated_questions": len(results), "questions": results}


def cluster_interval(question_effects: Mapping[str, float], annotations: Mapping[str, Any], *,
                     seed: int = 42, resamples: int = 2000) -> dict[str, Any]:
    """Moyenne par question, paires conservées, familles rééchantillonnées ensemble."""
    if type(resamples) is not int or not 1 <= resamples <= 100_000:
        raise ValueError("resamples doit être un entier entre 1 et 100000")
    groups: dict[str, list[float]] = defaultdict(list)
    for question, effect in question_effects.items():
        groups[annotations[question]["family_id"]].append(effect)
    result: dict[str, Any] = {
        "estimate": statistics.mean(question_effects.values()) if question_effects else None,
        "questions": len(question_effects), "families": len(groups), "seed": seed,
        "resamples": resamples, "method": "paired_family_percentile_bootstrap",
        "confidence_level": .95, "interval": None,
        "limitation": "exploratory_few_families" if len(groups) < 10 else "sampling_and_annotation_assumptions_required",
    }
    if len(groups) < 2:
        result["limitation"] = "not_estimable_with_fewer_than_two_families"
        return result
    totals = [(sum(values), len(values)) for _, values in sorted(groups.items())]
    generator = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        sample = [generator.choice(totals) for _ in totals]
        estimates.append(sum(total for total, _ in sample) / sum(count for _, count in sample))
    result["interval"] = [_percentile(estimates, .025), _percentile(estimates, .975)]
    return result


def paired_comparison(runs: Sequence[Mapping[str, Any]], annotations: Mapping[str, Any], baseline: str,
                      variant: str, *, seed: int = 42, resamples: int = 2000,
                      require_same_context: bool = False, require_same_prompt: bool = False) -> dict[str, Any]:
    by_variant = {
        name: {(run["question_id"], run["repeat"]): run for run in runs
               if run["variant"] == name and run["status"] != "not_run"}
        for name in (baseline, variant)
    }
    reference, candidate = by_variant[baseline], by_variant[variant]
    shared = sorted(reference.keys() & candidate.keys())
    effects: dict[str, list[float]] = defaultdict(list)
    unreviewed = 0
    for key in shared:
        left, right = reference[key], candidate[key]
        for field, required in (("context_sha256", require_same_context), ("prompt_sha256", require_same_prompt)):
            if required and (not left.get(field) or not right.get(field) or left[field] != right[field]):
                raise ValueError(f"Ablation non comparable {key}: {field} absent ou différent")
        question = key[0]
        if not annotations[question]["answerable"]:
            continue
        first, second = _complete(left, annotations[question]), _complete(right, annotations[question])
        if first is None or second is None:
            unreviewed += 1
            continue
        effects[question].append(float(second) - float(first))
    means = {question: statistics.mean(values) for question, values in effects.items()}
    return {
        "baseline": baseline, "variant": variant, "paired_positions": len(shared),
        "paired_unique_questions": len({key[0] for key in shared}),
        "unpaired_baseline_positions": len(reference.keys() - candidate.keys()),
        "unpaired_variant_positions": len(candidate.keys() - reference.keys()),
        "unreviewed_answerable_pairs": unreviewed,
        "analysed_answerable_pairs": sum(len(values) for values in effects.values()),
        "complete_response_delta": cluster_interval(means, annotations, seed=seed, resamples=resamples),
        "interpretation": "Repeated positions are averaged per question; unreviewed pairs are excluded and counted. Refusals/errors count as no complete response.",
    }


def evaluate(annotations: Iterable[Mapping[str, Any]], runs: Iterable[Mapping[str, Any]], *,
             baseline: str | None = None, seed: int = 42, resamples: int = 2000,
             require_same_context: bool = False, require_same_prompt: bool = False) -> dict[str, Any]:
    gold = validate_annotations(annotations)
    observations = validate_runs(runs, gold)
    variants = sorted({run["variant"] for run in observations})
    if baseline is not None and baseline not in variants:
        raise ValueError(f"Variante de référence absente : {baseline}")
    return {
        "schema_version": 1, "scope": "EV4B explicit judgments; no model call or automatic semantic grader",
        "annotations": {"questions": len(gold), "splits": dict(sorted(Counter(q["split"] for q in gold.values()).items())),
                        "sha256": canonical_sha256([gold[key] for key in sorted(gold)])},
        "runs_sha256": canonical_sha256(observations),
        "variants": {variant: summarize_variant([run for run in observations if run["variant"] == variant], gold)
                     for variant in variants},
        "repetitions": repetition_summary(observations),
        "comparisons": [paired_comparison(observations, gold, baseline, variant, seed=seed, resamples=resamples,
                                          require_same_context=require_same_context, require_same_prompt=require_same_prompt)
                        for variant in variants if baseline is not None and variant != baseline],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--baseline")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--require-same-context", action="store_true")
    parser.add_argument("--require-same-prompt", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = checked_output(args.output, [LOCAL_QA, ROOT / "RAG_Local_Agents" / "reports"],
                                sources=(args.annotations, args.runs))
        report = evaluate(read_jsonl(args.annotations), read_jsonl(args.runs), baseline=args.baseline,
                          seed=args.seed, resamples=args.resamples,
                          require_same_context=args.require_same_context, require_same_prompt=args.require_same_prompt)
        report["input_files"] = {"annotations_sha256": file_sha256(args.annotations), "runs_sha256": file_sha256(args.runs)}
        write_json_exclusive(output, report)
    except (ValueError, OSError) as error:
        print(f"Évaluation refusée : {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), "variants": list(report["variants"]),
                      "paired_comparisons": len(report["comparisons"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
