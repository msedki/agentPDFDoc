"""Pré-contrôle déterministe valeur/unité, grille manuelle D05 et métriques avec dénominateurs.

`grid` construit la grille à relire depuis le jeu résolu et le journal d'answers.py. `metrics` vérifie qu'une
grille remplie ne modifie que les champs manuels puis calcule les métriques D05 : Wilson par question, bootstrap
par question à graine fixe pour les assertions. Aucun appel modèle ni auto-jugement : le pré-contrôle n'est pas
un verdict.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from answers import journal_state
from evidence_io import EVALS, ROOT, checked_output, file_sha256, read_jsonl, write_json_exclusive

sys.path.insert(0, str(ROOT))
from services.api.qualification import canonical_sha, wilson  # noqa: E402

SEED, ITERATIONS = 20260930, 2000
VERDICTS = {True: ("correct", "partial", "value_unit_error", "unjustified_abstention", "incorrect"), False: ("justified_abstention", "incorrect")}
SUPPORT = ("supported", "partially_supported", "unsupported")
ABSTENTIONS = {"justified_abstention", "unjustified_abstention"}
API_ABSTENTION = "Les preuves disponibles dans ce périmètre ne suffisent pas pour répondre à cette question."
# Un nombre peut être suivi directement de son unité (« 230V ») ; pas d'un autre chiffre.
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![.,]?\d)")
THOUSANDS = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))")
TARGET_KEYS = {"answer_correctness": "answer_correctness_on_answerable_min", "supported_claim_ratio": "supported_claim_ratio_min",
               "correct_abstention": "no_answer_correct_ratio_min", "citation_id_integrity": "citation_integrity_ratio",
               "citation_version_page": "citation_integrity_ratio"}
INSTRUCTIONS = [
    "Remplir uniquement les objets `manual` (ligne et citations) ; toute autre modification est refusée par `metrics`.",
    "Verdict répondable : correct, partial, value_unit_error, unjustified_abstention ou incorrect. Sans réponse : justified_abstention ou incorrect.",
    "Chaque assertion documentaire : texte, citations [Sx] affichées, support supported/partially_supported/unsupported ; un soutien exige une citation.",
    "page_ok : la citation désigne la bonne page physique de la bonne version ; location_ok seulement si la précision n'est pas `page`.",
    "Le pré-contrôle numérique aide la relecture ; il ne remplace ni le verdict ni la vérification des preuves citées.",
]


def value_check(text: str, value: str, unit: str) -> dict:
    """Compare numériquement (virgule ou point décimal) chaque nombre du texte ; l'unité exacte doit suivre."""
    expected = Decimal(value.replace(",", "."))
    unit_after = re.compile(r"\s*" + re.escape(unit) + r"(?!\w)")
    found, with_unit, others = False, False, []
    text = THOUSANDS.sub("", text)  # « 1 020 h » : séparateur de milliers typographique
    for match in NUMBER.finditer(text):
        followed = bool(unit_after.match(text, match.end()))
        if Decimal(match.group().replace(",", ".")) == expected:
            found, with_unit = True, with_unit or followed
        elif followed:
            others.append(match.group())
    status = "VALUE_AND_UNIT" if with_unit else "VALUE_WITHOUT_EXPECTED_UNIT" if found else "VALUE_ABSENT"
    return {"value": value, "unit": unit, "status": status, "other_values_with_unit": others}


def identifier_in(text: str, identifier: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(identifier) + r"(?![\w-])", text) is not None


def precheck(question: dict, answer_text: str | None) -> dict:
    text, expected = answer_text or "", question.get("expected_answer") or ""
    values = [{"key": item["key"], **value_check(text, item["value"], item["unit"])} for item in question.get("important_values", [])]
    annotation = [value_check(expected, item["value"], item["unit"])["status"] == "VALUE_AND_UNIT" for item in question.get("important_values", [])]
    return {"method": "Deterministic numeric match with '.' or ',' decimal separator followed by the exact annotated unit; not a verdict",
            "values": values, "all_values_with_unit": all(item["status"] == "VALUE_AND_UNIT" for item in values) if values else None,
            "required_identifiers_missing": [code for code in question.get("required_identifiers") or [] if not identifier_in(text, code)],
            "forbidden_identifiers_present": [code for code in question.get("forbidden_identifiers") or [] if identifier_in(text, code)],
            "annotation_values_in_expected_answer": all(annotation) if annotation else None, "api_fixed_abstention": text.strip() == API_ABSTENTION}


def build_rows(dataset: dict, records: list[dict]) -> list[dict]:
    _, results = journal_state(records)
    rows = []
    for question in dataset["questions"]:
        result = results.get(question["id"], {})
        answered = result.get("status") == "ANSWERED"
        versions = {item["version_id"] for item in question.get("versions_snapshot") or []}
        registered = {source.get("source_id"): source for source in result.get("sources", [])}
        citations = []
        for source_id in result.get("cited_source_ids", []):
            source = registered.get(source_id, {})
            citations.append({"source_id": source_id, "registered": source_id in registered, **{key: source.get(key) for key in ("document_id", "version_id", "page_index", "page_number", "label", "block_ids", "precision")},
                              "version_in_frozen_snapshot": source.get("version_id") in versions if versions and source else None, "manual": {"page_ok": None, "location_ok": None}})
        expected = [{"document_key": unit["document_key"], "page_index": unit["page_index"], "version_id": unit.get("version_id"), "required_texts": unit.get("required_texts"),
                     "resolution_status": unit.get("resolution_status")} for unit in question.get("expected_units", [])]
        rows.append({"question_id": question["id"], **{key: question.get(key) for key in ("category", "language", "answerable", "question", "prior_user_question", "expected_answer", "absence_reason",
                                                           "important_values", "required_identifiers", "forbidden_identifiers")},
                     "expected_evidence": expected,
                     "generation": {"status": result.get("status", "NOT_IN_JOURNAL"), "query_id": result.get("query_id"), "model_called": result.get("model_called"),
                                    "answer_text": result.get("answer_text"), "cited_source_ids": result.get("cited_source_ids", []),
                                    "warning_codes": [warning.get("code") for warning in result.get("warnings") or []]},
                     "citations": citations, "precheck": precheck(question, result.get("answer_text")) if answered else None,
                     "manual": {"verdict": None if answered else "not_generated", "assertions": [], "reviewer": None, "reviewed_at_utc": None, "notes": ""}})
    return rows


def build_grid(dataset: dict, answers_path: Path) -> dict:
    records = read_jsonl(answers_path)
    header = records[0] if records and records[0].get("record") == "header" else None
    if header is None or header.get("dataset_sha256") != canonical_sha(dataset):
        raise ValueError("Le journal de réponses ne correspond pas à ce jeu résolu")
    return {"schema_version": 1, "kind": "D05_manual_grid", "split": header["split"], "dataset_sha256": header["dataset_sha256"], "answers_sha256": file_sha256(answers_path),
            "generated_at_utc": datetime.now(UTC).isoformat(), "instructions": INSTRUCTIONS, "verdict_options": {"answerable": VERDICTS[True], "unanswerable": VERDICTS[False]},
            "assertion_support_options": SUPPORT, "assertion_template": {"text": "", "citations": [], "support": None}, "rows": build_rows(dataset, records)}


def automatic(row: dict) -> dict:
    stripped = copy.deepcopy(row)
    stripped.pop("manual", None)
    for citation in stripped.get("citations", []):
        citation.pop("manual", None)
    return stripped


def validate(grid: dict, dataset: dict, answers_path: Path) -> tuple[list[str], list[str]]:
    """Refuse toute modification hors `manual` ; renvoie erreurs de saisie et questions non relues."""
    if grid.get("dataset_sha256") != canonical_sha(dataset) or grid.get("answers_sha256") != file_sha256(answers_path):
        raise ValueError("Grille issue d'un autre jeu ou d'un autre journal de réponses")
    header = read_jsonl(answers_path)[0]
    if grid.get("split") != header.get("split"):
        raise ValueError("Le split de la grille diffère de celui du journal de réponses")
    if grid["split"] == "final" and not header.get("final_freeze_sha256"):
        raise ValueError("Journal final sans empreinte de gel : statut de recette impossible")
    reference = build_rows(dataset, read_jsonl(answers_path))
    rows = grid.get("rows", [])
    if len(rows) != len(reference) or any(automatic(row) != automatic(expected) for row, expected in zip(rows, reference, strict=True)):
        raise ValueError("La grille modifie une donnée automatique (question, réponse, citation ou pré-contrôle)")
    errors, ungraded = [], []
    for row in rows:
        manual, answered = row["manual"], row["generation"]["status"] == "ANSWERED"
        verdict = manual.get("verdict")
        if verdict is None:
            ungraded.append(row["question_id"])
            continue
        allowed = VERDICTS[bool(row["answerable"])] if answered else ("not_generated",)
        if verdict not in allowed:
            errors.append(f"{row['question_id']} : verdict {verdict!r} hors de {allowed}")
        if not answered:
            continue
        if not isinstance(manual.get("reviewer"), str) or not manual["reviewer"].strip():
            errors.append(f"{row['question_id']} : relecteur requis")
        cited = set(row["generation"]["cited_source_ids"])
        for assertion in manual.get("assertions", []):
            if not isinstance(assertion.get("text"), str) or not assertion["text"].strip() or assertion.get("support") not in SUPPORT:
                errors.append(f"{row['question_id']} : assertion sans texte ou support invalide")
            elif not set(assertion.get("citations", [])) <= cited:
                errors.append(f"{row['question_id']} : assertion citant un ID non affiché")
            elif assertion["support"] != "unsupported" and not assertion.get("citations"):
                errors.append(f"{row['question_id']} : soutien déclaré sans citation")
        if verdict not in ABSTENTIONS and not manual.get("assertions"):
            errors.append(f"{row['question_id']} : assertions documentaires requises hors abstention")
        for citation in row["citations"]:
            if not isinstance(citation["manual"].get("page_ok"), bool) or citation["manual"].get("location_ok") not in (True, False, None):
                errors.append(f"{row['question_id']} : page_ok booléen requis pour {citation['source_id']}")
    return errors, ungraded


def quantile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)


def bootstrap_ratio(pairs: list[tuple[int, int]], seed: int = SEED, iterations: int = ITERATIONS) -> dict:
    """Ratio d'agrégats avec intervalle bootstrap : les assertions d'une question restent groupées."""
    pairs = [pair for pair in pairs if pair[1]]
    result: dict[str, Any] = {"successes": sum(pair[0] for pair in pairs), "denominator": sum(pair[1] for pair in pairs), "questions": len(pairs), "seed": seed, "iterations": iterations,
                              "method": "bootstrap by question; percentile interval with linear interpolation"}
    if not pairs:
        return {**result, "rate": None, "interval_95": None}
    rng = random.Random(seed)
    estimates = sorted(sum(item[0] for item in sample) / sum(item[1] for item in sample) for sample in (rng.choices(pairs, k=len(pairs)) for _ in range(iterations)))
    return {**result, "rate": result["successes"] / result["denominator"], "interval_95": [quantile(estimates, .025), quantile(estimates, .975)]}


def ratio(successes: int, denominator: int) -> dict:
    return {"successes": successes, "denominator": denominator, "rate": successes / denominator if denominator else None}


def outcome_metrics(rows: list[dict]) -> dict:
    answerable, unanswerable = [row for row in rows if row["answerable"]], [row for row in rows if not row["answerable"]]
    verdict = lambda row: row["manual"].get("verdict") or "ungraded"  # noqa: E731
    return {"answer_correctness": {**wilson(sum(verdict(row) == "correct" for row in answerable), len(answerable)), "breakdown": dict(Counter(map(verdict, answerable)))},
            "correct_abstention": {**wilson(sum(verdict(row) == "justified_abstention" for row in unanswerable), len(unanswerable)), "breakdown": dict(Counter(map(verdict, unanswerable)))},
            "false_refusals_on_answerable": wilson(sum(verdict(row) == "unjustified_abstention" for row in answerable), len(answerable))}


def metrics(grid: dict, dataset: dict, answers_path: Path, targets: dict) -> dict:
    errors, ungraded = validate(grid, dataset, answers_path)
    if errors:
        raise ValueError("Grille invalide : " + " ; ".join(errors[:10]))
    rows = grid["rows"]
    answered = [row for row in rows if row["generation"]["status"] == "ANSWERED"]
    citations = [citation for row in answered for citation in row["citations"]]
    located = [citation for citation in citations if citation.get("precision") not in (None, "page") and citation["manual"].get("location_ok") is not None]
    result = {**outcome_metrics(rows),
              "supported_claim_ratio": bootstrap_ratio([(sum(item["support"] == "supported" for item in row["manual"]["assertions"]), len(row["manual"]["assertions"])) for row in answered]),
              "partially_supported_assertions": sum(item["support"] == "partially_supported" for row in answered for item in row["manual"]["assertions"]),
              "citation_id_integrity": ratio(sum(citation["registered"] for citation in citations), len(citations)),
              "citation_version_page": ratio(sum(bool(citation["registered"] and citation["version_in_frozen_snapshot"] and citation["manual"].get("page_ok")) for citation in citations), len(citations)),
              "citation_location": {**ratio(sum(citation["manual"]["location_ok"] is True for citation in located), len(located)), "excluded_page_precision": len(citations) - len(located)},
              "unknown_citations_removed_by_api": sum(code == "unknown_citations" for row in answered for code in row["generation"]["warning_codes"]),
              "not_generated_questions": sum(row["generation"]["status"] != "ANSWERED" for row in rows), "ungraded_questions": ungraded,
              "by_category": {key: outcome_metrics([row for row in rows if row["category"] == key]) for key in sorted({row["category"] for row in rows})},
              "by_language": {key: outcome_metrics([row for row in rows if row["language"] == key]) for key in sorted({row["language"] for row in rows if row["language"]})}}
    met = {name: result[name]["rate"] is not None and result[name]["rate"] >= targets[key] for name, key in TARGET_KEYS.items()}
    status = "INCOMPLETE" if ungraded else ("PASS" if all(met.values()) else "FAIL") if grid["split"] == "final" else "DEVELOPMENT_DIAGNOSTIC"
    return {"status": status, "split": grid["split"], "dataset_sha256": grid["dataset_sha256"], "answers_sha256": grid["answers_sha256"], "grid_sha256": canonical_sha(grid),
            "targets": {name: targets[key] for name, key in TARGET_KEYS.items()}, "targets_met": met, "metrics": result,
            "limits": ["Manual grid by the named reviewer; no model self-judgement.", "Not generated or ungraded questions stay in denominators as non-successes.",
                       "Question bootstrap does not model dependence between questions of one documentary family."]}


def load_targets(profile: Path) -> dict:
    targets = yaml.safe_load(profile.read_text(encoding="utf-8"))["evaluation_targets"]
    return {key: float(targets[key]) for key in set(TARGET_KEYS.values())}


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("grid", "metrics"):
        command = commands.add_parser(name)
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--answers", type=Path, required=True, help="Journal JSONL d'answers.py")
        command.add_argument("--output", type=Path, required=True, help="Nouveau fichier sous evals/qualification-v2.1/runtime/")
    commands.choices["metrics"].add_argument("--grid", type=Path, required=True, help="Grille relue et remplie")
    commands.choices["metrics"].add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    args = parser.parse_args(argv)
    try:
        output = checked_output(args.output, [EVALS / "runtime"], sources=(args.dataset, args.answers, getattr(args, "grid", args.answers)))
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if args.command == "grid":
            result = build_grid(dataset, args.answers)
        else:
            result = metrics(json.loads(args.grid.read_text(encoding="utf-8")), dataset, args.answers, load_targets(args.profile))
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    write_json_exclusive(output, result)
    summary = {"output": str(output), "status": result.get("status", "GRID_TO_REVIEW"), "rows": len(result.get("rows", [])) or None}
    print(json.dumps(summary, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
