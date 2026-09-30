"""Runner headless de génération : une question d'un split résolu = une génération réelle (POST /api/v1/queries + SSE).

Journal JSONL en ajout seul sous evals/qualification-v2.1/runtime/. La reprise saute les questions terminées et
relit le SSE d'une question déjà créée sans la soumettre une seconde fois. Aucun jugement de qualité ici.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
from api_client import (
    api_client,
    diagnostics_identity,
    fetch_diagnostics,
    follow_query,
    http_error,
    submit_query,
)
from evidence_io import EVALS, ROOT, append_jsonl, checked_output, file_sha256, read_jsonl

sys.path.insert(0, str(ROOT))
from services.api.qualification import canonical_sha, verify_annotations  # noqa: E402

CITATION = re.compile(r"\[(S\d+)\]")
RESUME_KEYS = ("split", "base_url", "dataset_sha256", "source_dataset_sha256", "final_freeze_sha256", "question_ids", "api_identity")
STATUS = {"done": "ANSWERED", "error": "API_ERROR", "cancelled": "CANCELLED", "needs_clarification": "NEEDS_CLARIFICATION"}
SOURCE_KEYS = ("source_id", "chunk_id", "document_id", "version_id", "generation_id", "extraction_revision_id", "page_index", "page_number",
               "label", "block_ids", "precision", "document_name", "citation_url")
METRIC_TOKENS = ("local_prompt_tokens", "prompt_eval_count", "prompt_eval_cached_count", "eval_count", "output_tokens", "evidence_tokens")
METRIC_DURATIONS = {"api_elapsed": "elapsed_ms", "api_ttft": "ttft_ms", "api_queue_wait": "queue_wait_ms", "api_retrieval": "retrieval_ms",
                    "api_context": "context_ms", "api_generation_admission_wait": "generation_admission_wait_ms"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_split(dataset_path: Path, source_path: Path, split: str, freeze_path: Path | None = None) -> tuple[dict, dict, str | None]:
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    source = json.loads(Path(source_path).read_text(encoding="utf-8"))
    verify_annotations(source, dataset)
    if not dataset.get("questions") or any(question.get("split") != split for question in dataset["questions"]):
        raise ValueError("Jeu résolu vide ou mélangeant les splits")
    frozen = None
    if split == "final":
        if not freeze_path:
            raise ValueError("Le split final exige --final-freeze")
        freeze = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
        frozen = freeze.get("canonical_sha256")
        if not frozen or canonical_sha(source) != frozen or len(source["questions"]) != freeze.get("questions"):
            raise ValueError("Le jeu final source ne correspond pas au gel fourni")
        if any(question.get("annotation_state") != "RESOLVED" for question in dataset["questions"]):
            raise ValueError("Toutes les annotations finales doivent être résolues avant génération")
    return dataset, source, frozen


def compact(source: dict) -> dict:
    return {key: source[key] for key in SOURCE_KEYS if key in source}


def journal_state(records: list[dict]) -> tuple[dict, dict]:
    submitted, results = {}, {}
    for record in records:
        if record.get("record") == "submitted":
            submitted[record["question_id"]] = record
        elif record.get("record") == "result":
            if record.get("status") == "API_ERROR" and record.get("model_called") is False:
                # Refus avant tout appel au modèle (admission mémoire…) : aucune génération n'a eu lieu,
                # la question est reposée à la reprise ; la tentative reste dans le journal.
                results.pop(record["question_id"], None)
                submitted.pop(record["question_id"], None)
            else:
                results[record["question_id"]] = record
    return submitted, results


def request_body(question: dict, results: dict) -> tuple[dict | None, str | None]:
    body = {"question": question["question"], "scope": question["scope_resolved"], "mode": question.get("mode") or "question"}
    prior_id = question.get("followup_of_question_id")
    if prior_id:
        # Relance réelle : même conversation et référence explicite à la question utilisateur antérieure.
        prior = results.get(prior_id)
        if prior is None:
            return None, "PRIOR_NOT_ANSWERED_YET"
        if prior.get("status") != "ANSWERED":
            return None, "NOT_RUN_PRIOR_FAILED"
        body.update(conversation_id=prior["conversation_id"], followup_of=prior["query_id"])
    return body, None


def base_record(question: dict, kind: str, **values) -> dict:
    return {"record": kind, "question_id": question["id"], "category": question.get("category"), "language": question.get("language"),
            "answerable": question.get("answerable"), **values, "at_utc": now()}


def result_record(question: dict, submitted: dict, outcome: dict, replayed: bool) -> dict:
    terminal = outcome["terminal"]
    data = terminal["data"] or {}
    events = outcome["events"]
    metrics = data.get("metrics") or {}
    text = data.get("text") if terminal["event"] in {"done", "cancelled"} else None
    sources = next((event["data"].get("sources", []) for event in events if event["event"] == "sources"), [])
    durations = {name: metrics.get(key) for name, key in METRIC_DURATIONS.items()}
    # Une relecture après reprise ne mesure pas la latence : les durées client sont alors nulles.
    durations.update(client_post=None if replayed else submitted.get("post_ms"), client_first_delta=None if replayed else outcome["client_first_delta_ms"],
                     client_terminal=None if replayed else outcome["client_terminal_ms"])
    return base_record(question, "result", status=STATUS[terminal["event"]], query_id=submitted["query_id"], conversation_id=submitted.get("conversation_id"),
                       request=submitted.get("request"), terminal_event=terminal["event"], answer_status=data.get("status"), finish_reason=data.get("finish_reason"),
                       answer_text=text, streamed_text="".join(event["data"].get("text", "") for event in events if event["event"] == "delta"),
                       cited_source_ids=list(dict.fromkeys(CITATION.findall(text or ""))), citations=[compact(item) for item in data.get("citations", [])],
                       sources=[compact(item) for item in sources], warnings=data.get("warnings", []),
                       warning_events=[event["data"] for event in events if event["event"] == "warning"],
                       error={"code": data.get("code"), "message": data.get("message")} if terminal["event"] == "error" else None,
                       choices=data.get("choices") if terminal["event"] == "needs_clarification" else None,
                       model_called=metrics.get("model_called"), tokens={key: metrics.get(key) for key in METRIC_TOKENS}, durations_ms=durations,
                       timings_replayed=replayed, metrics=metrics, sse=outcome["sse"])


def run(dataset_path: Path, source_path: Path, output: Path, base_url: str, split: str, *, freeze_path: Path | None = None, resume: bool = False,
        limit: int | None = None, question_timeout: float = 900.0, transport: httpx.BaseTransport | None = None, runtime_root: Path | None = None) -> dict:
    if split == "final" and limit is not None:
        raise ValueError("Le split final ne se limite pas : reprendre le même journal jusqu'au bout")
    dataset, source, frozen = load_split(dataset_path, source_path, split, freeze_path)
    output = checked_output(output, [runtime_root or EVALS / "runtime"], sources=(dataset_path, source_path), must_exist=resume)
    with api_client(base_url, transport=transport) as client:
        header = {"record": "header", "schema_version": 1, "tool": "tools/qualification/answers.py", "split": split, "base_url": base_url,
                  "dataset_sha256": canonical_sha(dataset), "source_dataset_sha256": canonical_sha(source), "final_freeze_sha256": frozen,
                  "question_ids": [question["id"] for question in dataset["questions"]], "api_identity": diagnostics_identity(fetch_diagnostics(client)),
                  "runner_sha256": {name: file_sha256(Path(__file__).parent / name) for name in ("answers.py", "api_client.py")}, "started_at_utc": now(),
                  "policy": "One POST per question; resume re-reads the SSE of an already created query; model answers are never evidence."}
        if resume:
            records = read_jsonl(output)
            if not records or records[0].get("record") != "header" or any(records[0].get(key) != header[key] for key in RESUME_KEYS):
                raise ValueError("Journal d'une autre exécution (jeu, gel, cible ou identité API différents) : reprise refusée")
            append_jsonl(output, {"record": "resumed", "runner_sha256": header["runner_sha256"], "api_identity": header["api_identity"], "at_utc": now()})
        else:
            records = [header]
            append_jsonl(output, header, create=True)
        submitted, results = journal_state(records)
        submissions = 0
        for question in dataset["questions"]:
            if question["id"] in results:
                continue
            if question["id"] not in submitted:
                if not question.get("scope_resolved"):
                    results[question["id"]] = base_record(question, "result", status="NOT_RUN_UNRESOLVED_SCOPE")
                    append_jsonl(output, results[question["id"]])
                    continue
                body, blocker = request_body(question, results)
                if blocker == "NOT_RUN_PRIOR_FAILED":
                    results[question["id"]] = base_record(question, "result", status=blocker, followup_of_question_id=question["followup_of_question_id"])
                    append_jsonl(output, results[question["id"]])
                    continue
                if blocker:
                    append_jsonl(output, base_record(question, "incident", status=blocker, followup_of_question_id=question["followup_of_question_id"]))
                    continue
                if limit is not None and submissions >= limit:
                    break
                try:
                    created, started, post_ms = submit_query(client, body)
                except (httpx.HTTPError, ValueError, KeyError) as error:
                    append_jsonl(output, base_record(question, "incident", status="POST_FAILED", **http_error(error)))
                    continue
                submissions += 1
                submitted[question["id"]] = base_record(question, "submitted", query_id=created["query_id"], conversation_id=created.get("conversation_id"),
                                                        events_url=created["events_url"], creation_state=created.get("state"), request=body, post_ms=post_ms)
                append_jsonl(output, submitted[question["id"]])
                replayed = False
            else:
                started, replayed = time.perf_counter(), True
            try:
                outcome = follow_query(client, submitted[question["id"]], started=started, deadline_s=question_timeout)
            except (httpx.HTTPError, TimeoutError, ValueError) as error:
                append_jsonl(output, base_record(question, "incident", status="STREAM_FAILED", query_id=submitted[question["id"]]["query_id"], **http_error(error)))
                continue
            if outcome["terminal"] is None:
                append_jsonl(output, base_record(question, "incident", status="STREAM_INCOMPLETE", query_id=submitted[question["id"]]["query_id"], sse=outcome["sse"]))
                continue
            results[question["id"]] = result_record(question, submitted[question["id"]], outcome, replayed)
            append_jsonl(output, results[question["id"]])
    pending = [question["id"] for question in dataset["questions"] if question["id"] not in results]
    return {"output": str(output), "split": split, "results": dict(Counter(record["status"] for record in results.values())), "pending_questions": pending,
            "submissions_this_run": submissions, "complete": not pending}


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True, help="Jeu résolu (runtime/…) du split")
    parser.add_argument("--source-dataset", type=Path, required=True, help="Jeu source gelé correspondant (development.json ou final.json)")
    parser.add_argument("--split", choices=["development", "final"], required=True)
    parser.add_argument("--output", type=Path, required=True, help="Journal JSONL sous evals/qualification-v2.1/runtime/")
    parser.add_argument("--base-url", default="http://127.0.0.1:8785", help="Origine loopback de l'instance cible (port explicite)")
    parser.add_argument("--final-freeze", type=Path, help="final.freeze.json : obligatoire pour le split final")
    parser.add_argument("--resume", action="store_true", help="Reprendre un journal existant de la même exécution")
    parser.add_argument("--limit", type=int, help="Nombre maximal de nouvelles soumissions (développement seulement)")
    parser.add_argument("--question-timeout", type=float, default=900.0)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit doit être positif")
    try:
        result = run(args.dataset, args.source_dataset, args.output, args.base_url, args.split, freeze_path=args.final_freeze, resume=args.resume,
                     limit=args.limit, question_timeout=args.question_timeout)
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.error(str(error) or type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
