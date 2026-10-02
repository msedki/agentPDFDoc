"""Question et ancienne citation après restauration (critère D09.3), sur une sauvegarde au format courant.

Deux phases, chacune sous quelques minutes, sans toucher à la bibliothèque de l'utilisateur :

1. `prepare` : instance de contrôle temporaire (mécanismes de `rag.ps1 selftest` et `rag.sh selftest`), import d'un PDF synthétique, question
   réelle dont les citations sont enregistrées, sauvegarde par `create_backup`, arrêt ; l'état est écrit dans --state.
2. `restore` : restauration de cette sauvegarde dans une racine neuve, démarrage, ouverture de chaque citation enregistrée
   avant la sauvegarde (même version, révision et blocs), nouvelle question réelle avec citations, arrêt, suppression des
   racines temporaires.

Chaque génération demande la mémoire d'une instance complète : sur un poste de 16 Gio, l'instance principale est arrêtée
pendant l'essai.

`prepare --profile` choisit le profil de base de l'instance temporaire (par défaut `config/local16.yaml`), par exemple
une copie en `llm.accelerator: cpu` ; `restore` reprend le profil enregistré dans la sauvegarde.

    .venv\\Scripts\\python.exe tools/qualification/restore_question_check.py prepare --state <etat.json> [--profile <profil.yaml>]
    .venv\\Scripts\\python.exe tools/qualification/restore_question_check.py restore --state <etat.json> --report <rapport.json>
    .venv/bin/python tools/qualification/restore_question_check.py prepare --state <etat.json> [--profile <profil.yaml>]
    .venv/bin/python tools/qualification/restore_question_check.py restore --state <etat.json> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from services.runtime.backup import create_backup, restore_backup  # noqa: E402
from services.runtime.selftest import (  # noqa: E402
    JOB_DONE,
    control_profile,
    read_events,
    remove_root,
    short_root,
    synthetic_pdf,
)
from services.runtime.supervisor import (  # noqa: E402
    app_origin,
    control_headers,
    data_path,
    load_profile,
    start,
    status,
    stop,
)

QUESTION = "Quelle est la pression nominale du banc {code} ?"
DELIVERED_PROFILE = ROOT / "config/local16.yaml"


def client_for(profile_path: Path) -> httpx.Client:
    profile = load_profile(profile_path)
    origin, verify = app_origin(profile)
    return httpx.Client(base_url=origin, headers={"Origin": origin, **control_headers(data_path(profile))}, timeout=60, trust_env=False, verify=verify)


def ask(client: httpx.Client, question: str, timeout: float) -> dict[str, Any]:
    created = client.post("/api/v1/queries", json={"question": question, "scope": {"kind": "library"}})
    created.raise_for_status()
    query_id = created.json()["query_id"]
    events = read_events(client, query_id, timeout)
    kind, data = events[-1] if events else ("", {})
    cited = [item if isinstance(item, str) else item.get("source_id") for item in data.get("citations") or []]
    return {"query_id": query_id, "terminal": kind, "code": data.get("code"), "message": data.get("message") if kind != "done" else None,
            "answer_text": data.get("text"), "citations": cited, "metrics": {key: (data.get("metrics") or {}).get(key) for key in ("model_called", "ttft_ms", "elapsed_ms")}}


def citation(client: httpx.Client, query_id: str, source_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/citations/{query_id}/{source_id}")
    if response.status_code != 200:
        return {"source_id": source_id, "http_status": response.status_code}
    source = response.json()
    return {"source_id": source_id, "http_status": 200, "version_id": source.get("version_id"), "extraction_revision_id": source.get("extraction_revision_id"),
            "pages": sorted({block["page_index"] for block in source.get("blocks", [])}), "blocks": sorted(block["id"] for block in source.get("blocks", []))}


def prepare(state_path: Path, job_timeout: float, answer_timeout: float, base_profile: Path = DELIVERED_PROFILE) -> dict[str, Any]:
    code = "RESTAURE-" + datetime.now(UTC).strftime("%H%M%S")
    base = {"file": base_profile.name, "sha256": hashlib.sha256(base_profile.read_bytes()).hexdigest()}
    root = short_root()
    state: dict[str, Any] = {"started_utc": datetime.now(UTC).isoformat(), "code": code, "source_root": str(root), "base_profile": base}
    profile_path = control_profile(base_profile, root)
    try:
        state["start"] = start(profile_path).get("status")
        with client_for(profile_path) as client:
            item = client.post("/api/v1/documents/import", files={"files": ("controle-restauration.pdf", synthetic_pdf(code), "application/pdf")}).json()["imports"][0]
            deadline = time.monotonic() + job_timeout
            while time.monotonic() < deadline:
                job = next(row for row in client.get("/api/v1/jobs", params={"limit": 20}).json()["jobs"] if row["id"] == item["job_id"])
                if job["state"] in JOB_DONE:
                    break
                time.sleep(2)
            state["extraction"] = job["state"]
            state["question_before_backup"] = ask(client, QUESTION.format(code=code), answer_timeout)
            query = state["question_before_backup"]
            state["citations_before_backup"] = [citation(client, query["query_id"], source_id) for source_id in query["citations"]]
        backup = create_backup(profile_path)
        state["backup"] = backup.get("path")
        state["backup_state"] = backup.get("state")
    finally:
        if status(profile_path).get("status") in {"starting", "running", "stopping"}:
            state["stop"] = stop(profile_path).get("status")
    state["prepared"] = bool(state.get("backup")) and state.get("backup_state") == "verified" and state["question_before_backup"]["terminal"] == "done" and bool(state["citations_before_backup"])
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def restore_report(target: Path) -> dict[str, Any] | None:
    """restore-report.json écrit dans la cible par restore_backup, y compris en échec ; None s'il n'a pas été écrit."""
    try:
        return json.loads((target / "restore-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def restore(state_path: Path, report_path: Path, answer_timeout: float) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    report: dict[str, Any] = {"prepared": {key: state.get(key) for key in ("started_utc", "code", "base_profile", "extraction", "backup_state", "question_before_backup", "citations_before_backup")},
                              "started_utc": datetime.now(UTC).isoformat(), "checks": {}}
    # Cible de 42 caractères au plus sous %TEMP% : « <cible>\qdrant\storage » tient sous la borne, sans relocalisation.
    target = short_root("apr")
    target.rmdir()  # restore_backup exige une racine qui n'existe pas encore
    report["target"] = str(target)
    profile_path = target / "restored-profile.yaml"
    checks = report["checks"]
    try:
        restored = restore_backup(Path(state["backup"]), target)
        # Rapport complet (D09.2) : données copiées vérifiées par empreinte, comptes SQLite, points Qdrant par collection ;
        # sa copie restore-report.json disparaît avec la cible.
        report["restore"] = restored
        checks["restored"] = restored.get("state") == "restored_storage_verified"
        report["start"] = start(profile_path).get("status")
        with client_for(profile_path) as client:
            before = {row["source_id"]: row for row in state["citations_before_backup"]}
            after = [citation(client, state["question_before_backup"]["query_id"], source_id) for source_id in before]
            report["citations_after_restore"] = after
            checks["old_citations_identical"] = bool(after) and all(row == before[row["source_id"]] for row in after)
            report["question_after_restore"] = ask(client, QUESTION.format(code=state["code"]), answer_timeout)
            query = report["question_after_restore"]
            opened = [citation(client, query["query_id"], source_id)["http_status"] for source_id in query["citations"]]
            checks["question_answered_with_citations"] = query["terminal"] == "done" and bool(query["citations"]) and all(code == 200 for code in opened)
            checks["answer_gives_document_value"] = "3,1" in (query["answer_text"] or "") or "3.1" in (query["answer_text"] or "")
    except Exception as error:  # noqa: BLE001 - l'échec est conservé dans le rapport avec ce qui a été observé
        report["error"] = f"{type(error).__name__}: {error}"
        checks["completed"] = False
    finally:
        if "restore" not in report:
            # Échec de restore_backup : son rapport (état failed, étapes déjà vérifiées, erreur) n'existe que dans la cible.
            report["restore"] = restore_report(target)
        if profile_path.exists() and status(profile_path).get("status") in {"starting", "running", "stopping"}:
            report["stop"] = stop(profile_path).get("status")
        report["removed"] = {str(target): remove_root(target), state["source_root"]: remove_root(Path(state["source_root"]))}
    report["result"] = "PASS" if checks and all(checks.values()) else "FAIL"
    report["finished_utc"] = datetime.now(UTC).isoformat()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", choices=["prepare", "restore"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--job-timeout", type=float, default=600)
    parser.add_argument("--answer-timeout", type=float, default=480)
    parser.add_argument("--profile", type=Path, help="prepare : profil de base de l'instance temporaire (config/local16.yaml par défaut)")
    args = parser.parse_args()
    if args.phase == "prepare":
        base = args.profile or DELIVERED_PROFILE
        if not base.is_file():
            parser.error(f"Profil de base introuvable : {base}")
        state = prepare(args.state, args.job_timeout, args.answer_timeout, base)
        print(json.dumps({key: state.get(key) for key in ("prepared", "extraction", "backup_state", "stop")}, ensure_ascii=False))
        return 0 if state["prepared"] else 1
    if not args.report:
        parser.error("restore exige --report")
    if args.profile:
        parser.error("--profile ne sert qu'à prepare : restore reprend le profil enregistré dans la sauvegarde")
    report = restore(args.state, args.report, args.answer_timeout)
    print(json.dumps({key: report[key] for key in ("result", "checks", "removed", "error") if key in report}, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
