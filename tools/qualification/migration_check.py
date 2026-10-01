"""Qualification d'une migration sur une sauvegarde (R11, critère D09.4), sans toucher à l'instance principale.

Restaure une sauvegarde d'un schéma antérieur dans une racine neuve, démarre l'instance restaurée (le code courant applique
alors ses migrations), vérifie le schéma, les comptes et chaque citation enregistrée avant la sauvegarde, puis réindexe
chaque document avec la chaîne courante : la nouvelle génération doit être active et les anciennes citations doivent
toujours désigner leur révision d'extraction d'origine. L'instance est arrêtée à la fin ; la cible et son stockage Qdrant
court restent pour diagnostic, sauf avec --cleanup.

    .venv\\Scripts\\python.exe tools/qualification/migration_check.py --backup <sauvegarde> --target <racine neuve> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from services.runtime.backup import restore_backup  # noqa: E402
from services.runtime.selftest import read_events  # noqa: E402
from services.runtime.supervisor import (  # noqa: E402
    app_origin,
    control_headers,
    data_path,
    load_profile,
    start,
    status,
    stop,
)

JOB_DONE = {"ready", "ready_partial", "error", "cancelled"}


def database(path: Path) -> dict[str, Any]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608 - tables fixes
                  for table in ("documents", "document_versions", "index_generations", "citations")}
        return {"schema_version": connection.execute("SELECT max(version) FROM schema_version").fetchone()[0], "counts": counts,
                "citations": [dict(row) for row in connection.execute("SELECT query_id, source_id, document_id FROM citations ORDER BY query_id, source_id")],
                "active_generations": {row["id"]: row["active_generation_id"] for row in connection.execute("SELECT id, active_generation_id FROM documents WHERE deleted_at IS NULL")}}


def open_citations(client: httpx.Client, citations: list[dict]) -> list[dict]:
    """Chaque citation enregistrée doit rendre sa source, et ses blocs doivent exister dans la révision qu'elle désigne."""
    results = []
    for item in citations:
        response = client.get(f"/api/v1/citations/{item['query_id']}/{item['source_id']}")
        row: dict[str, Any] = {"source_id": item["source_id"], "http_status": response.status_code}
        if response.status_code == 200:
            source = response.json()
            revision = source.get("extraction_revision_id")
            pages = sorted({block["page_index"] for block in source.get("blocks", [])})
            found = set()
            for page in pages:
                blocks = client.get(f"/api/v1/versions/{source['version_id']}/pages/{page}/blocks", params={"extraction_revision_id": revision})
                if blocks.status_code == 200:
                    found |= {block["id"] for block in blocks.json()["blocks"]}
            cited = {block["id"] for block in source.get("blocks", [])}
            row.update({"extraction_revision_id": revision, "pages": pages, "blocks": len(cited), "blocks_found": len(cited & found)})
        results.append(row)
    return results


def wait_jobs(client: httpx.Client, job_ids: list[str], timeout: float) -> dict[str, dict]:
    deadline = time.monotonic() + timeout
    final: dict[str, dict] = {}
    while time.monotonic() < deadline and len(final) < len(job_ids):
        for job in client.get("/api/v1/jobs", params={"limit": 50}).json()["jobs"]:
            if job["id"] in job_ids and job["state"] in JOB_DONE:
                final[job["id"]] = {"state": job["state"], "active": bool(job.get("active")), "error_code": job.get("error_code")}
        time.sleep(2)
    return final


def check(backup: Path, target: Path, job_timeout: float, question: str | None = None, answer_timeout: float = 900) -> dict[str, Any]:
    report: dict[str, Any] = {"started_utc": datetime.now(UTC).isoformat(), "backup": str(backup), "target": str(target), "checks": {}}
    before = database(backup / "data" / "app.sqlite3")
    report["before"] = {key: before[key] for key in ("schema_version", "counts")}
    restored = restore_backup(backup, target)
    report["restore"] = {key: restored.get(key) for key in ("state", "qdrant_data_dir", "qdrant_storage_relocated_for_windows_path_limit", "collections", "error")}
    if restored.get("state") != "restored_storage_verified":
        report["result"] = "FAIL"
        return report
    profile_path = target / "restored-profile.yaml"
    try:
        state = start(profile_path)
        report["start"] = state.get("status")
        profile = load_profile(profile_path)
        migrated = database(data_path(profile) / "app.sqlite3")
        report["after_start"] = {key: migrated[key] for key in ("schema_version", "counts")}
        checks = report["checks"]
        checks["schema_migrated"] = migrated["schema_version"] > before["schema_version"]
        checks["counts_preserved"] = all(migrated["counts"][key] == value for key, value in before["counts"].items())
        origin, verify = app_origin(profile)
        with httpx.Client(base_url=origin, headers={"Origin": origin, **control_headers(data_path(profile))}, timeout=60, trust_env=False, verify=verify) as client:
            checks["readiness_200"] = client.get("/api/v1/readiness").status_code == 200
            old = open_citations(client, before["citations"])
            report["citations_after_migration"] = old
            checks["old_citations_open"] = bool(old) and all(row["http_status"] == 200 and row["blocks_found"] == row["blocks"] for row in old)
            jobs = []
            for document_id in before["active_generations"]:
                response = client.post(f"/api/v1/documents/{document_id}/reindex")
                response.raise_for_status()
                jobs.append(response.json()["job_id"])
            report["reindex_jobs"] = wait_jobs(client, jobs, job_timeout)
            after = database(data_path(profile) / "app.sqlite3")
            report["after_reindex"] = {key: after[key] for key in ("schema_version", "counts")}
            checks["new_generation_active"] = (len(report["reindex_jobs"]) == len(jobs) and all(job["state"] == "ready" and job["active"] for job in report["reindex_jobs"].values())
                                               and all(after["active_generations"][key] != value for key, value in before["active_generations"].items()))
            pinned = open_citations(client, before["citations"])
            report["citations_after_reindex"] = pinned
            checks["old_citations_keep_their_revision"] = (all(row["http_status"] == 200 and row["blocks_found"] == row["blocks"] for row in pinned)
                                                           and [row.get("extraction_revision_id") for row in pinned] == [row.get("extraction_revision_id") for row in old])
            search = client.post("/api/v1/search", json={"question": "pression nominale", "scope": {"kind": "library"}})
            checks["search_after_reindex"] = search.status_code == 200 and bool(search.json().get("top10"))
            if question:
                # Critère D09.3 : une question réelle sur l'instance restaurée, réponse terminée et citations enregistrées relues.
                created = client.post("/api/v1/queries", json={"question": question, "scope": {"kind": "library"}})
                created.raise_for_status()
                query_id = created.json()["query_id"]
                events = read_events(client, query_id, answer_timeout)
                kind, data = events[-1] if events else ("", {})
                cited = [item if isinstance(item, str) else item.get("source_id") for item in data.get("citations") or []]
                opened = [client.get(f"/api/v1/citations/{query_id}/{source_id}").status_code for source_id in cited]
                report["question"] = {"text": question, "terminal": kind, "status": data.get("status"), "code": data.get("code"),
                                      "message": data.get("message") if kind != "done" else None, "answer_text": data.get("text"),
                                      "citations": cited, "citations_http": opened,
                                      "metrics": {key: (data.get("metrics") or {}).get(key) for key in ("model_called", "ttft_ms", "elapsed_ms")}}
                checks["question_answered_with_citations"] = kind == "done" and bool(cited) and all(code == 200 for code in opened)
    finally:
        if status(profile_path).get("status") in {"starting", "running", "stopping"}:
            report["stop"] = stop(profile_path).get("status")
    report["result"] = "PASS" if report["checks"] and all(value is True for value in report["checks"].values()) else "FAIL"
    report["finished_utc"] = datetime.now(UTC).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--job-timeout", type=float, default=900)
    parser.add_argument("--question", help="question réelle posée à l'instance restaurée (critère D09.3)")
    parser.add_argument("--answer-timeout", type=float, default=900)
    parser.add_argument("--cleanup", action="store_true", help="retirer la cible et son stockage Qdrant court après l'arrêt")
    args = parser.parse_args()
    report = check(args.backup.resolve(), args.target.resolve(), args.job_timeout, args.question, args.answer_timeout)
    if args.cleanup:
        restore = report.get("restore") or {}
        # Le stockage court n'est retiré que s'il a été alloué par cette restauration sous .runtime\q (W004).
        storage = Path(restore["qdrant_data_dir"]) if restore.get("qdrant_storage_relocated_for_windows_path_limit") else None
        storage = storage if storage and storage.parent == (ROOT / ".runtime" / "q").resolve() else None
        for folder in filter(None, [args.target.resolve(), storage]):
            shutil.rmtree(folder, ignore_errors=True)
            report.setdefault("removed", {})[str(folder)] = not folder.exists()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("result", "checks", "removed")}, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
