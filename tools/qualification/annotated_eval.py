"""Évaluation de la recherche sur le jeu de référence établi par lecture intégrale des documents (W014).

`resolve` lit les fichiers du jeu (`.runtime/evals/annotated-v1/*.json`, un par document), rattache chaque
extrait exact d'une preuve aux blocs de la génération active de l'instance, puis écrit un jeu exécutable sous
`.runtime/` : périmètre du document (« reference ») et toute la bibliothèque (« portee_bibliotheque »).
Un extrait introuvable sur sa page est cherché dans tout le document (page corrigée) ; une question dont une
preuve n'est pas rattachée n'est mesurée qu'au niveau de la page.

`run` interroge `POST /api/v1/admin/evaluation/context` (sans modèle) et mesure, par bloc et par page,
la présence de la preuve au top 10, dans la liste finale et dans le contexte transmis au modèle. Les questions
sans réponse ne se mesurent qu'avec la génération (aucune abstention de recherche hors identifiants).
Le rapport ne contient que des identifiants, des états de rattachement et des agrégats.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.retrieval import DASHES  # noqa: E402
from tools.qualification.corpus_eval import block_ids, instance, rate_table, score  # noqa: E402

# Seuil de rattachement approché : part des mots de l'extrait retrouvés dans le bloc (OCR, coupures de ligne).
FUZZY_COVERAGE = 0.7


def normalize(text: str) -> str:
    folded = "".join(char for char in unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text).casefold()) if not unicodedata.combining(char))
    folded = folded.replace("’", "'").replace("‘", "'").translate(DASHES)
    return re.sub(r"\s+", " ", folded).strip()


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", normalize(text))


def locate(excerpt: str, blocks: list[dict[str, Any]]) -> tuple[list[str], str, float]:
    """Blocs qui portent l'extrait : exact, à cheval sur deux blocs consécutifs, ou approché (part des mots)."""
    wanted = normalize(excerpt)
    if not wanted:
        return [], "EMPTY", 0.0
    for block in blocks:
        if wanted in normalize(block["text"]):
            return [block["id"]], "EXACT", 1.0
    for first, second in zip(blocks, blocks[1:], strict=False):
        if wanted in normalize(first["text"] + " " + second["text"]):
            return [first["id"], second["id"]], "EXACT_SPAN", 1.0
    asked = words(excerpt)
    if len(asked) < 3:
        return [], "NOT_RESOLVED", 0.0
    best, coverage = None, 0.0
    for block in blocks:
        present = set(words(block["text"]))
        share = sum(1 for word in asked if word in present) / len(asked)
        if share > coverage:
            best, coverage = block, share
    if best is not None and coverage >= FUZZY_COVERAGE:
        return [best["id"]], "FUZZY", round(coverage, 3)
    return [], "NOT_RESOLVED", round(coverage, 3)


def resolve_unit(unit: dict[str, Any], document_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    page_index = unit.get("page_index")
    if page_index is None and unit.get("page_number"):
        page_index = int(unit["page_number"]) - 1
    on_page = [block for block in document_blocks if block["page_index"] == page_index]
    found: list[str] = []
    statuses = []
    corrected_pages: set[int] = set()
    for excerpt in unit.get("required_texts") or []:
        ids, status, coverage = locate(excerpt, on_page)
        if not ids:
            # Page annoncée erronée : seule une correspondance exacte ailleurs est retenue. Une correspondance approchée
            # sur une autre page tombe sur des textes répétés (cartouches, en-têtes) et désignerait un faux bloc.
            elsewhere, found_status, _ = locate(excerpt, document_blocks)
            if elsewhere and found_status in {"EXACT", "EXACT_SPAN"}:
                ids, status, coverage = elsewhere, "PAGE_CORRECTED_" + found_status, 1.0
                corrected_pages |= {block["page_index"] for block in document_blocks if block["id"] in ids}
        statuses.append({"status": status, "coverage": coverage})
        found += [identifier for identifier in ids if identifier not in found]
    pages = sorted({page_index} | corrected_pages) if page_index is not None else sorted(corrected_pages)
    return {"page_indices": pages, "block_ids": found, "excerpts": statuses, "resolved": bool(found)}


def resolve_dataset(annotated: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    questions = []
    for document_file in annotated:
        document = document_file["document"]
        document_blocks = [block for block in blocks if block["document_id"] == document["document_id"]]
        for item in document_file["questions"]:
            units = [resolve_unit(unit, document_blocks) for unit in item.get("expected_units") or [] if unit.get("role", "answer") == "answer"]
            base = {"source_id": item["id"], "category": item["category"], "question": item["question"],
                    "prior_user_question": item.get("prior_user_question"), "answerable": bool(item.get("answerable")),
                    "difficulty": item.get("difficulty"), "document_id": document["document_id"], "split": "annotated",
                    "expected_block_ids": sorted({identifier for unit in units for identifier in unit["block_ids"]}),
                    "expected_pages": sorted({page for unit in units for page in unit["page_indices"]}),
                    "block_resolved": bool(units) and all(unit["resolved"] for unit in units),
                    "resolution": [{"excerpts": unit["excerpts"], "page_indices": unit["page_indices"]} for unit in units],
                    "annotation_state": "ASSISTANT_READ_NOT_EXPERT_VALIDATED"}
            questions.append({**base, "variant": "reference", "scope": {"kind": "documents", "documentIds": [document["document_id"]]}})
            questions.append({**base, "variant": "portee_bibliotheque", "scope": {"kind": "library"}})
    for index, item in enumerate(questions):
        item["id"] = f"a{index + 1:03d}"
    statuses = Counter(excerpt["status"] for item in questions if item["variant"] == "reference" for unit in item["resolution"] for excerpt in unit["excerpts"])
    return {"format": "annotated-eval-v1", "questions": questions, "documents": [item["document"]["document_id"] for item in annotated],
            "resolution_summary": {"excerpts": dict(statuses),
                                   "answerable_questions": sum(1 for item in questions if item["variant"] == "reference" and item["answerable"]),
                                   "block_resolved": sum(1 for item in questions if item["variant"] == "reference" and item["answerable"] and item["block_resolved"])}}


def page_hits(sources: list[dict[str, Any]], document_id: str, pages: set[int]) -> list[bool]:
    hits = []
    for source in sources:
        indices = set(source.get("page_indices") or []) | {block.get("page_index") for block in source.get("blocks", [])}
        hits.append(source.get("document_id") == document_id and bool(indices & pages))
    return hits


def score_annotated(question: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"id": question["id"], "source_id": question["source_id"], "category": question["category"], "variant": question["variant"],
                           "difficulty": question.get("difficulty"), "block_resolved": question["block_resolved"], "state": result.get("state")}
    pages = set(question["expected_pages"])
    top10 = page_hits(result.get("retrieval_top10", []), question["document_id"], pages)
    rank = next((position for position, hit in enumerate(top10, 1) if hit), None)
    row.update({"page_at_10": rank is not None, "page_reciprocal_rank": round(1 / rank, 4) if rank else 0.0,
                "page_in_final": any(page_hits(result.get("retrieval_final", []), question["document_id"], pages)),
                "page_in_context": any(page_hits(result.get("context_sources", []), question["document_id"], pages))})
    if question["block_resolved"]:
        blocks = score({**question, "alternative_block_ids": []}, result)
        row.update({key: blocks[key] for key in ("success_at_10", "reciprocal_rank", "in_final", "in_context")})
    row["context_blocks"] = sum(len(block_ids(source)) for source in result.get("context_sources", []))
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for variant in sorted({row["variant"] for row in rows}):
        subset = [row for row in rows if row["variant"] == variant]
        report[variant] = {"page": rate_table(subset, ("page_at_10", "page_in_final", "page_in_context")),
                           "page_mrr_at_10": round(sum(row["page_reciprocal_rank"] for row in subset) / len(subset), 4) if subset else None,
                           "block": rate_table([row for row in subset if row["block_resolved"]], ("success_at_10", "in_final", "in_context")),
                           "by_category": {category: rate_table([row for row in subset if row["category"] == category], ("page_at_10", "page_in_context"))
                                           for category in sorted({row["category"] for row in subset})},
                           "by_difficulty": {str(difficulty): rate_table([row for row in subset if row.get("difficulty") == difficulty], ("page_at_10", "page_in_context"))
                                             for difficulty in sorted({str(row.get("difficulty")) for row in subset})}}
    return report


CITATION = re.compile(r"\[(S\d+)\]")
# Tournures par lesquelles le modèle dit que les preuves ne contiennent pas l'information (indice, pas un jugement).
ABSTENTION = re.compile(r"(?i)(ne (?:précis|mentionn|contien|donn|fourni|indiqu|permet|comport|trait|figur)\w*\b[^.]{0,80}?\bpas"
                        r"|n'(?:est|sont|apparaît|apparaissent) pas (?:mentionn|indiqu|précis|donn|fourni|présent)\w*"
                        r"|aucune (?:information|mention|donnée|indication|précision)|pas d'information|insuffisan|n'apparaît pas|introuvable)")


def generation_sample(dataset: dict[str, Any], answerable: int, unanswerable: int) -> list[dict[str, Any]]:
    """Échantillon déterministe pour la génération : périmètre du document, tour à tour par document, questions de suivi exclues."""
    pools: dict[tuple[bool, str], list[dict[str, Any]]] = {}
    for item in dataset["questions"]:
        if item["variant"] == "reference" and item["category"] != "conversation_followup":
            pools.setdefault((item["answerable"], item["document_id"]), []).append(item)
    chosen = []
    for kind, wanted in ((True, answerable), (False, unanswerable)):
        queues = [sorted(pool, key=lambda item: item["source_id"]) for (flag, _), pool in sorted(pools.items(), key=lambda entry: entry[0][1]) if flag is kind]
        taken: list[dict[str, Any]] = []
        while len(taken) < wanted and any(queues):
            for queue in queues:
                if queue and len(taken) < wanted:
                    # Pas fixe dans chaque document : couvre début, milieu et fin plutôt que les premières questions.
                    taken.append(queue.pop(len(queue) // 2))
        chosen += taken
    return chosen


def answer_record(question: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    terminal = outcome["terminal"] or {"event": "timeout", "data": {}}
    data = terminal.get("data") or {}
    text = data.get("text") or ""
    sources: list[dict[str, Any]] = next((event["data"].get("sources", []) for event in outcome["events"] if event["event"] == "sources"), [])
    metrics = data.get("metrics") or {}
    return {"id": question["id"], "source_id": question["source_id"], "document_id": question["document_id"], "answerable": question["answerable"],
            "status": terminal["event"], "answer_status": data.get("status"), "finish_reason": data.get("finish_reason"),
            "error_code": data.get("code") if terminal["event"] == "error" else None,
            "answer_text": text, "cited": list(dict.fromkeys(CITATION.findall(text))),
            "sources": [{"source_id": source.get("source_id"), "document_id": source.get("document_id"), "page_index": source.get("page_index")} for source in sources],
            "metrics": {key: metrics.get(key) for key in ("ttft_ms", "elapsed_ms", "prompt_eval_count", "eval_count", "evidence_tokens", "generation_admission_wait_ms")},
            "at_utc": dt.datetime.now(dt.UTC).isoformat()}


def grade_answer(record: dict[str, Any], question: dict[str, Any], annotated: dict[str, Any]) -> dict[str, Any]:
    """Contrôles automatiques d'une réponse : valeurs, citations, page citée, tournure d'abstention (aucun texte conservé)."""
    # Les scripts de qualification s'importent entre eux par leur nom (grade -> answers -> evidence_io).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from grade import value_check

    text = record["answer_text"] or ""
    registry = {source["source_id"] for source in record["sources"]}
    cited = [source for source in record["sources"] if source["source_id"] in set(record["cited"])]
    row: dict[str, Any] = {"id": record["id"], "source_id": record["source_id"], "answerable": record["answerable"], "status": record["status"],
                           "answered": record["status"] == "done" and bool(text.strip()), "truncated": record.get("answer_status") == "length_limited",
                           "error_code": record.get("error_code"), "citations_valid": set(record["cited"]) <= registry,
                           "cites_expected_page": any(source["document_id"] == question["document_id"] and source["page_index"] in set(question["expected_pages"])
                                                      for source in cited),
                           "abstention_phrase": bool(ABSTENTION.search(text)), "metrics": record["metrics"]}
    values = [item for item in annotated.get("important_values") or [] if str(item.get("value") or "").strip()]
    checks = []
    for item in values:
        if item.get("unit") and re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", str(item["value"]).strip()):
            checks.append(value_check(text, str(item["value"]).strip(), str(item["unit"]).strip())["status"] == "VALUE_AND_UNIT")
        else:
            checks.append(normalize(str(item["value"])) in normalize(text))
    row["values_expected"], row["values_found"] = len(checks), sum(checks)
    return row


def grade_answers_command(args: argparse.Namespace) -> int:
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    questions = {item["id"]: item for item in dataset["questions"]}
    annotated = {item["id"]: item for path in sorted(args.input.glob("*.json")) if not path.name.startswith("resolved")
                 for item in json.loads(path.read_text(encoding="utf-8")).get("questions", [])}
    # Dernière tentative de chaque question ; une erreur reprise ensuite est remplacée par la réponse obtenue.
    records = {record["id"]: record for record in map(json.loads, args.answers.read_text(encoding="utf-8").splitlines()) if record}
    rows = [grade_answer(record, questions[record["id"]], annotated[record["source_id"]]) for record in records.values()]
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    with_values = [{"ok": row["values_found"] == row["values_expected"]} for row in answerable if row["values_expected"]]
    summary: dict[str, Any] = {
        "answerable": {**rate_table(answerable, ("answered", "truncated", "citations_valid", "cites_expected_page", "abstention_phrase")),
                       "all_values_found": rate_table(with_values, ("ok",))["ok"]},
        "unanswerable": rate_table(unanswerable, ("answered", "citations_valid", "abstention_phrase")),
        "ttft_ms": sorted(row["metrics"].get("ttft_ms") or 0 for row in rows), "elapsed_ms": sorted(row["metrics"].get("elapsed_ms") or 0 for row in rows)}
    report = {"format": "annotated-answers-report-v1", "utc": dt.datetime.now(dt.UTC).isoformat(), "annotation_state": "ASSISTANT_READ_NOT_EXPERT_VALIDATED",
              "answers_sha256": hashlib.sha256(args.answers.read_bytes()).hexdigest(), "summary": summary, "rows": rows,
              "note": "Contrôles automatiques seulement ; le jugement de justesse de chaque réponse est consigné à part."}
    target = args.report.resolve()
    if target.exists():
        raise SystemExit("Rapport existant : choisir un nouveau fichier")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def answer_command(client: httpx.Client, args: argparse.Namespace, runtime: Path) -> int:
    from tools.qualification.api_client import follow_query, submit_query

    output = args.output.resolve()
    if not output.is_relative_to(runtime):
        raise SystemExit("Les réponses contiennent du texte du corpus : journal sous .runtime/ exigé")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    # Une question en erreur (réserve mémoire menacée, coupure) est relancée ; seule la dernière ligne d'une question compte.
    latest = {record["id"]: record for record in map(json.loads, output.read_text(encoding="utf-8").splitlines()) if record} if output.exists() else {}
    done = {identifier for identifier, record in latest.items() if record["status"] != "error"}
    output.parent.mkdir(parents=True, exist_ok=True)
    for question in generation_sample(dataset, args.answerable, args.unanswerable):
        if question["id"] in done:
            continue
        body = {"question": question["question"], "scope": question["scope"], "mode": "question"}
        try:
            created, started, _ = submit_query(client, body)
            outcome = follow_query(client, created, started=started, deadline_s=args.deadline)
            record = answer_record(question, outcome)
        except httpx.HTTPError as error:
            # Refus d'admission ou coupure : rien n'est écrit, la question sera reprise au prochain lancement.
            print(json.dumps({"id": question["id"], "error": type(error).__name__}), flush=True)
            continue
        with output.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps({"id": question["id"], "status": record["status"], "answer_status": record["answer_status"], "error_code": record["error_code"],
                          "ttft_ms": record["metrics"]["ttft_ms"],
                          "elapsed_ms": record["metrics"]["elapsed_ms"]}), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    answer = sub.add_parser("answer", help="Génération réelle sur un échantillon (réponses sous .runtime/, reprise possible)")
    answer.add_argument("--dataset", type=Path, required=True)
    answer.add_argument("--output", type=Path, required=True, help="Journal JSONL des réponses sous .runtime/ (texte des réponses)")
    answer.add_argument("--answerable", type=int, default=16)
    answer.add_argument("--unanswerable", type=int, default=6)
    answer.add_argument("--deadline", type=float, default=900.0, help="Délai maximal par question, en secondes")
    graded = sub.add_parser("grade-answers", help="Contrôles automatiques des réponses ; rapport sans texte")
    graded.add_argument("--dataset", type=Path, required=True)
    graded.add_argument("--answers", type=Path, required=True)
    graded.add_argument("--input", type=Path, default=ROOT / ".runtime/evals/annotated-v1")
    graded.add_argument("--report", type=Path, required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--input", type=Path, default=ROOT / ".runtime/evals/annotated-v1")
    resolve.add_argument("--output", type=Path, required=True, help="Jeu exécutable sous .runtime/ (contient le texte des questions)")
    run = sub.add_parser("run")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--report", type=Path, required=True, help="Rapport agrégé, sans texte du corpus ni des questions")
    for command in (resolve, run, answer):
        command.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    args = parser.parse_args()
    runtime = (ROOT / ".runtime").resolve()
    if args.command == "grade-answers":
        return grade_answers_command(args)
    origin, verify, headers = instance(args.profile)
    with httpx.Client(base_url=origin, headers={"Origin": origin, **headers}, verify=verify, trust_env=False, timeout=httpx.Timeout(300, connect=10)) as client:
        if args.command == "answer":
            return answer_command(client, args, runtime)
        if args.command == "resolve":
            output = args.output.resolve()
            if not output.is_relative_to(runtime) or output.exists():
                raise SystemExit("Le jeu contient le texte des questions : nouveau fichier sous .runtime/ exigé")
            sources = sorted(path for path in args.input.glob("*.json") if not path.name.startswith("resolved"))
            annotated = [item for item in (json.loads(path.read_text(encoding="utf-8")) for path in sources)
                         if isinstance(item, dict) and "document" in item and "questions" in item]
            tree = client.get("/api/v1/library/tree", params={"limit": 200}).json()
            wanted = {item["document"]["document_id"] for item in annotated}
            blocks = []
            for document in tree["documents"]:
                if document["id"] not in wanted or not document.get("active_generation_id"):
                    continue
                version = document.get("active_version_id") or document.get("version_id")
                for page_index in range(int(document.get("page_count") or 0)):
                    response = client.get(f"/api/v1/versions/{version}/pages/{page_index}/blocks")
                    if response.status_code == 200:
                        blocks += [{"id": block["id"], "document_id": document["id"], "page_index": page_index, "text": block.get("text") or ""}
                                   for block in response.json()["blocks"] if (block.get("text") or "").strip()]
            dataset = resolve_dataset(annotated, blocks)
            dataset["created_utc"] = dt.datetime.now(dt.UTC).isoformat()
            dataset["sources_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(json.dumps({"sha256": hashlib.sha256(output.read_bytes()).hexdigest(), **dataset["resolution_summary"]}, ensure_ascii=False))
            return 0
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = []
        failures: Counter[str] = Counter()
        for question in dataset["questions"]:
            if not question["answerable"]:
                continue
            body = {"question": question["question"], "scope": question["scope"], "mode": "question"}
            if question.get("prior_user_question"):
                body["prior_user_question"] = question["prior_user_question"]
            response = client.post("/api/v1/admin/evaluation/context", json=body)
            if response.status_code != 200:
                failures[str(response.json().get("code", response.status_code))] += 1
                continue
            rows.append(score_annotated(question, response.json()))
        report = {"format": "annotated-eval-report-v1", "utc": dt.datetime.now(dt.UTC).isoformat(),
                  "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(), "annotation_state": "ASSISTANT_READ_NOT_EXPERT_VALIDATED",
                  "resolution_summary": dataset.get("resolution_summary"), "request_failures": dict(failures),
                  "unanswerable_not_measured_here": sum(1 for item in dataset["questions"] if not item["answerable"]),
                  "method": "POST /api/v1/admin/evaluation/context (aucun appel au modèle)", "metrics": summarize(rows), "rows": rows}
        target = args.report.resolve()
        if target.exists():
            raise SystemExit("Rapport existant : choisir un nouveau fichier")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({variant: {"page": values["page"], "block": values["block"]} for variant, values in report["metrics"].items()}, ensure_ascii=False))
        return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
