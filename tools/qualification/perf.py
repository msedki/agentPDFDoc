"""Runner D07 : N recherches POST /api/v1/search puis M questions POST /api/v1/queries, séquentielles, sur l'API réelle.

Rapporte latences client et API, p50/p95 (interpolation linéaire), TTFT, durée totale, longueurs réelles
prompt_eval_count/eval_count et durées de chargement rapportées par l'API. Aucune extrapolation : un scénario
non observé reste NOT_OBSERVED. Le split final est refusé (jeu tenu à l'écart).
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Sequence
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
from evidence_io import EVALS, checked_output, file_sha256, write_json_exclusive

NS_PER_MS = 1_000_000


def distribution(values: Sequence[float | None]) -> dict:
    values = sorted(value for value in values if isinstance(value, int | float))
    def quantile(fraction):
        position = (len(values) - 1) * fraction
        lower = math.floor(position)
        return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)
    return {"count": len(values), "min": values[0] if values else None, "p50": quantile(.5) if values else None, "p95": quantile(.95) if values else None,
            "max": values[-1] if values else None, "method": "linear interpolation between order statistics"}


def eligible(dataset: dict) -> list[dict]:
    if any(question.get("split") == "final" for question in dataset["questions"]):
        raise ValueError("Le split final est tenu à l'écart : aucune mesure de performance sur ce jeu")
    # Les relances dépendent d'une conversation antérieure : exclues pour des mesures indépendantes.
    return [question for question in dataset["questions"] if question.get("scope_resolved") and not question.get("followup_of_question_id")]


def ns_to_ms(value) -> float | None:
    return round(value / NS_PER_MS, 2) if isinstance(value, int | float) and not isinstance(value, bool) else None


def search_row(client: httpx.Client, question: dict) -> dict:
    body = {"question": question["question"], "scope": question["scope_resolved"], "mode": question.get("mode") or "question"}
    started = time.perf_counter()
    try:
        response = client.post("/api/v1/search", json=body)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return {"question_id": question["id"], "status": "ERROR", **http_error(error)}
    return {"question_id": question["id"], "status": "OK", "client_ms": round((time.perf_counter() - started) * 1000, 2), "api_elapsed_ms": payload.get("elapsed_ms"),
            "results": len(payload.get("results", [])), "warning_codes": [warning.get("code") for warning in payload.get("warnings", [])]}


def query_row(client: httpx.Client, question: dict, deadline_s: float, cold_load_ms: float) -> dict:
    body = {"question": question["question"], "scope": question["scope_resolved"], "mode": question.get("mode") or "question"}
    try:
        created, started, post_ms = submit_query(client, body)
        outcome = follow_query(client, created, started=started, deadline_s=deadline_s)
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError) as error:
        return {"question_id": question["id"], "status": "CLIENT_ERROR", **http_error(error)}
    terminal = outcome["terminal"]
    if terminal is None:
        return {"question_id": question["id"], "status": "STREAM_INCOMPLETE", "query_id": created["query_id"], "sse": outcome["sse"]}
    metrics = terminal["data"].get("metrics") or {}
    load_ms = ns_to_ms(metrics.get("load_duration"))
    # Froid/chaud selon la durée de chargement rapportée par l'API (Ollama load_duration) et un seuil déclaré.
    residency = "unreported" if load_ms is None else "cold" if load_ms >= cold_load_ms else "warm"
    eval_ms, prompt_ms = ns_to_ms(metrics.get("eval_duration")), ns_to_ms(metrics.get("prompt_eval_duration"))
    eval_count, prompt_count = metrics.get("eval_count"), metrics.get("prompt_eval_count")
    return {"question_id": question["id"], "status": terminal["event"].upper(), "query_id": created["query_id"], "model_called": metrics.get("model_called"),
            "finish_reason": terminal["data"].get("finish_reason"), "error_code": terminal["data"].get("code"), "residency": residency, "client_post_ms": post_ms,
            "client_first_delta_ms": outcome["client_first_delta_ms"], "client_terminal_ms": outcome["client_terminal_ms"],
            "api_ttft_ms": metrics.get("ttft_ms"), "api_elapsed_ms": metrics.get("elapsed_ms"), "api_retrieval_ms": metrics.get("retrieval_ms"),
            "api_queue_wait_ms": metrics.get("queue_wait_ms"), "api_generation_admission_wait_ms": metrics.get("generation_admission_wait_ms"),
            "load_ms": load_ms, "prompt_eval_ms": prompt_ms, "eval_ms": eval_ms, "prompt_eval_count": prompt_count,
            "prompt_eval_cached_count": metrics.get("prompt_eval_cached_count"), "eval_count": eval_count, "local_prompt_tokens": metrics.get("local_prompt_tokens"),
            "prefill_tokens_per_s": round(prompt_count / prompt_ms * 1000, 3) if isinstance(prompt_count, int) and prompt_ms else None,
            "decode_tokens_per_s": round(eval_count / eval_ms * 1000, 3) if isinstance(eval_count, int) and eval_ms else None,
            "sse": {key: outcome["sse"][key] for key in ("bytes", "sha256", "event_counts")}}


def summarize(searches: list[dict], queries: list[dict], cold_load_ms: float) -> dict:
    ok_searches = [row for row in searches if row["status"] == "OK"]
    generated = [row for row in queries if row["status"] == "DONE" and row.get("model_called") is True]
    long_answers = [row for row in generated if isinstance(row.get("eval_count"), int) and row["eval_count"] >= 400]
    groups = {name: [row for row in generated if row["residency"] == name] for name in ("warm", "cold", "unreported")}
    phase = lambda rows: {key: distribution([row.get(key) for row in rows]) for key in ("api_ttft_ms", "client_first_delta_ms", "api_elapsed_ms", "client_terminal_ms", "load_ms", "prompt_eval_ms", "eval_ms")}  # noqa: E731
    return {"search": {"requested": len(searches), "succeeded": len(ok_searches), "client_ms": distribution([row["client_ms"] for row in ok_searches]),
                       "api_elapsed_ms": distribution([row["api_elapsed_ms"] for row in ok_searches])},
            "queries": {"requested": len(queries), "status_counts": {status: sum(row["status"] == status for row in queries) for status in sorted({row["status"] for row in queries})},
                        "model_generations": len(generated), "residency_rule": f"cold when API-reported load_duration >= {cold_load_ms} ms; unreported when absent",
                        "by_residency": {name: {"count": len(rows), **phase(rows)} for name, rows in groups.items()},
                        "prompt_eval_count": distribution([row.get("prompt_eval_count") for row in generated]),
                        "eval_count": distribution([row.get("eval_count") for row in generated]),
                        "answers_reaching_400_tokens": {"count": len(long_answers), "status": "OBSERVED" if long_answers else "NOT_OBSERVED",
                                                         "client_terminal_ms": distribution([row["client_terminal_ms"] for row in long_answers]),
                                                         "shorter_answer_lengths": sorted(row["eval_count"] for row in generated if isinstance(row.get("eval_count"), int) and row["eval_count"] < 400)},
                        "decode_tokens_per_s": distribution([row.get("decode_tokens_per_s") for row in generated]),
                        "prefill_tokens_per_s": distribution([row.get("prefill_tokens_per_s") for row in generated])}}


def run(dataset_path: Path, output: Path, base_url: str, searches: int, queries: int, *, cold_load_ms: float = 1000.0, question_timeout: float = 900.0,
        transport: httpx.BaseTransport | None = None, runtime_root: Path | None = None) -> dict:
    output = checked_output(output, [runtime_root or EVALS / "runtime"], sources=(dataset_path,))
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    candidates = eligible(dataset)
    if searches < 0 or queries < 0 or searches + queries > len(candidates) or not searches + queries:
        raise ValueError(f"{searches}+{queries} questions distinctes demandées ; {len(candidates)} disponibles (scope résolu, hors relance)")
    started_at = datetime.now(UTC).isoformat()
    with api_client(base_url, transport=transport) as client:
        first = fetch_diagnostics(client)
        search_rows = [search_row(client, question) for question in candidates[:searches]]
        query_rows = [query_row(client, question, question_timeout, cold_load_ms) for question in candidates[searches:searches + queries]]
        last = fetch_diagnostics(client)
    identity, before, after = diagnostics_identity(first), first.get("resources"), last.get("resources")
    # Une dérive d'identité pendant la mesure est conservée comme échec, jamais masquée.
    status = "MEASURED_NOT_QUALIFIED" if diagnostics_identity(last) == identity else "INVALID_API_IDENTITY_DRIFT"
    report = {"status": status, "tool": "tools/qualification/perf.py", "api_identity_after": diagnostics_identity(last), "runner_sha256": {name: file_sha256(Path(__file__).parent / name) for name in ("perf.py", "api_client.py")},
              "base_url": base_url, "dataset_sha256": file_sha256(dataset_path), "started_at_utc": started_at, "finished_at_utc": datetime.now(UTC).isoformat(),
              "api_identity": identity, "resources_before": before, "resources_after": after, "sequential": True, "distinct_questions": True,
              "summary": summarize(search_rows, query_rows, cold_load_ms), "searches": search_rows, "queries": query_rows,
              "limits": ["No extrapolation: unobserved scenarios stay NOT_OBSERVED; a shorter natural answer is not scaled to 400 tokens.",
                         "D07 thresholds require >=25000 chunks and a declared warm model; corpus size is not verified by this tool.",
                         "Client durations include loopback HTTP and SSE polling (100 ms server cadence); API durations come from the done event."]}
    write_json_exclusive(output, report)
    return report


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True, help="Jeu résolu de développement ou de performance (split final refusé)")
    parser.add_argument("--searches", type=int, required=True)
    parser.add_argument("--queries", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Nouveau rapport sous evals/qualification-v2.1/runtime/")
    parser.add_argument("--base-url", default="http://127.0.0.1:8785", help="Origine loopback de l'instance cible (port explicite)")
    parser.add_argument("--cold-load-ms", type=float, default=1000.0, help="Seuil déclaré sur load_duration rapporté pour classer froid/chaud")
    parser.add_argument("--question-timeout", type=float, default=900.0)
    args = parser.parse_args(argv)
    try:
        report = run(args.dataset, args.output, args.base_url, args.searches, args.queries, cold_load_ms=args.cold_load_ms, question_timeout=args.question_timeout)
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.error(str(error) or type(error).__name__)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    main()
