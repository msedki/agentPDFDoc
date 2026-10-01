"""Fautes injectées pendant un import, sur une instance isolée (critères D03.5 et D03.6).

L'instance est démarrée par `tools/qualification/e2e_instance.py start` ; seuls ses propres processus, lus dans son
`control/runtime.json`, sont arrêtés. La bibliothèque de l'utilisateur n'est jamais touchée.

    kill-extracting  arrêt forcé de toute l'instance pendant l'extraction, redémarrage, reprise du traitement (D03.5)
    kill-embedding   arrêt forcé pendant le calcul des embeddings, puis reprise (D03.5)
    kill-vectors     arrêt forcé pendant l'écriture et la vérification des points Qdrant, juste avant la publication (D03.5)
    qdrant-down      arrêt forcé du seul Qdrant pendant l'import : le document ne doit jamais paraître prêt (D03.6)

Après reprise, chaque cas exige : traitement prêt, une seule génération publiée pour la version, aucun fragment en
double, autant de points Qdrant dans la collection que de fragments des générations actives, aucun nettoyage en attente.

    .venv\\Scripts\\python.exe tools/qualification/fault_check.py <cas> --instance <etat.json> --fixture <pdf> --report <rapport.json>
    .venv/bin/python tools/qualification/fault_check.py <cas> --instance <etat.json> --fixture <pdf> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psutil
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DONE = {"ready", "ready_partial", "error", "cancelled"}


def kill_tree(pid: int) -> None:
    """Arrêt forcé de l'arbre `pid` : aucune sortie propre, comme une coupure.

    Windows : TerminateProcess de l'arbre (taskkill /F /T). Linux : l'arbre relevé par psutil est d'abord gelé
    (SIGSTOP) : le superviseur ne réagit plus à la perte d'un enfant et le SIGTERM de PR_SET_PDEATHSIG reste en attente ;
    chaque processus reçoit ensuite SIGKILL. psutil revérifie la date de création avant chaque signal.
    """
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
        return
    try:
        root = psutil.Process(pid)
        root.suspend()
    except psutil.Error:
        return
    tree = [root]
    # Deux relevés : un enfant créé pendant le premier gel est rattrapé par le second.
    for _ in range(2):
        try:
            found = root.children(recursive=True)
        except psutil.Error:
            found = []
        for process in found:
            if process not in tree:
                with suppress(psutil.Error):
                    process.suspend()
                tree.append(process)
    for process in tree:
        with suppress(psutil.Error):
            process.kill()


class Isolated:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.profile_path = Path(state["profile"])
        self.profile = yaml.safe_load(self.profile_path.read_text(encoding="utf-8"))
        self.data = Path(self.profile["app"]["data_dir"])

    def client(self) -> httpx.Client:
        token = Path(self.state["token_file"]).read_text(encoding="ascii").strip()
        return httpx.Client(base_url=self.state["origin"], headers={"Origin": self.state["origin"], "x-rag-control-token": token}, timeout=60, trust_env=False)

    def runtime(self) -> dict[str, Any]:
        return json.loads((self.data / "control" / "runtime.json").read_text(encoding="utf-8"))

    def job(self, job_id: str) -> dict[str, Any] | None:
        try:
            with self.client() as client:
                return next((item for item in client.get("/api/v1/jobs", params={"limit": 50}).json()["jobs"] if item["id"] == job_id), None)
        except (httpx.HTTPError, OSError):  # instance arrêtée : jeton retiré ou API muette
            return None

    def kill_tree(self, pid: int) -> None:
        kill_tree(pid)

    def restart(self) -> str:
        from services.runtime.supervisor import start
        return str(start(self.profile_path).get("status"))

    def database(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.data / 'app.sqlite3'}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def qdrant_total(self) -> int:
        key = (self.data / "control" / "qdrant-api-key").read_text(encoding="ascii").strip()
        with self.client() as client:
            collection = client.get("/api/v1/diagnostics").json()["qdrant_collection"]
        response = httpx.post(f"{self.profile['qdrant']['url']}/collections/{collection}/points/count", headers={"api-key": key}, json={"exact": True}, trust_env=False, timeout=30)
        response.raise_for_status()
        return int(response.json()["result"]["count"])


def wait_stage(instance: Isolated, job_id: str, stages: set[str], timeout: float = 600) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = instance.job(job_id)
        if job and (job.get("stage") in stages or job["state"] in stages):
            return job
        if job and job["state"] in DONE:
            raise RuntimeError(f"traitement terminé ({job['state']}) avant l'étape visée {sorted(stages)}")
        time.sleep(0.02)
    raise TimeoutError(f"étape {sorted(stages)} non atteinte")


def wait_done(instance: Isolated, job_id: str, timeout: float = 600) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = instance.job(job_id)
        if job and job["state"] in DONE | {"paused"}:
            return job
        time.sleep(1)
    raise TimeoutError("traitement non terminé")


def wait_admitted(instance: Isolated, job_ids: dict[str, str], attempts: int = 10) -> tuple[dict[str, dict[str, Any]], int]:
    """Attend chaque traitement ; un import refusé par l'admission mémoire est repris explicitement, comme le ferait
    l'utilisateur (la mémoire de l'hôte est partagée avec d'autres programmes). Rend les traitements et le nombre de reprises."""
    jobs = {name: wait_done(instance, job_id) for name, job_id in job_ids.items()}
    retries = 0
    while retries < attempts and any(job.get("error_code") == "resource_admission_denied" for job in jobs.values()):
        retries += 1
        time.sleep(30)
        with instance.client() as client:
            for job in jobs.values():
                if job.get("error_code") == "resource_admission_denied":
                    client.post(f"/api/v1/jobs/{job['id']}/resume").raise_for_status()
        jobs = {name: wait_done(instance, job_id) for name, job_id in job_ids.items()}
    return jobs, retries


def consistency(instance: Isolated, version_id: str) -> dict[str, Any]:
    with instance.client() as client:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and client.get("/api/v1/diagnostics").json()["reconciliation"]["pending_cleanup"]:
            time.sleep(2)
        diagnostics = client.get("/api/v1/diagnostics").json()
    with instance.database() as connection:
        generations = [dict(row) for row in connection.execute("SELECT id, state, published_at FROM index_generations WHERE version_id=?", (version_id,))]
        active_chunks = connection.execute("SELECT count(*) FROM chunks c JOIN documents d ON d.active_generation_id=c.generation_id WHERE d.deleted_at IS NULL").fetchone()[0]
        all_chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
        duplicate_chunks = connection.execute("SELECT count(*) FROM (SELECT chunk_uuid FROM chunks GROUP BY chunk_uuid HAVING count(*) > 1)").fetchone()[0]
    points = instance.qdrant_total()
    return {"generations": generations, "published_generations": sum(1 for row in generations if row["published_at"]),
            "active_chunks": active_chunks, "all_chunks": all_chunks, "duplicate_chunks": duplicate_chunks, "qdrant_points": points,
            "index_consistency": diagnostics["index_consistency"]["status"], "pending_cleanup": diagnostics["reconciliation"]["pending_cleanup"]}


def import_fixture(instance: Isolated, fixture: Path, relative: str) -> dict[str, Any]:
    with instance.client() as client, fixture.open("rb") as handle:
        response = client.post("/api/v1/documents/import", data={"relative_paths": json.dumps([relative])}, files={"files": (fixture.name, handle, "application/pdf")})
    response.raise_for_status()
    return response.json()["imports"][0]


def resume_and_check(instance: Isolated, item: dict[str, Any], result: dict[str, Any]) -> None:
    job = wait_done(instance, item["job_id"], 120)
    result["after_restart"] = {"state": job["state"], "stage": job.get("stage"), "error_code": job.get("error_code")}
    # Un traitement interrompu revient en pause, un traitement en erreur (service perdu) se relance de même.
    if job["state"] in {"paused", "error"}:
        with instance.client() as client:
            result["resume_http"] = client.post(f"/api/v1/jobs/{item['job_id']}/resume").status_code
        job = wait_done(instance, item["job_id"])
    result["final_job"] = {"state": job["state"], "error_code": job.get("error_code"), "active": bool(job.get("active"))}
    result["consistency"] = state = consistency(instance, item["version_id"])
    result["checks"].update({
        "resumed_to_ready": job["state"] in {"ready", "ready_partial"} and bool(job.get("active")),
        "single_published_generation": state["published_generations"] == 1,
        "no_duplicate_chunks": state["duplicate_chunks"] == 0 and state["all_chunks"] == state["active_chunks"],
        "no_orphan_points": state["qdrant_points"] == state["active_chunks"] and state["index_consistency"] == "consistent",
        "no_pending_cleanup": state["pending_cleanup"] == 0})


def case_kill(instance: Isolated, fixture: Path, stages: set[str]) -> dict[str, Any]:
    item = import_fixture(instance, fixture, f"Fautes/{'-'.join(sorted(stages))}/{fixture.name}")
    job = wait_stage(instance, item["job_id"], stages)
    runtime = instance.runtime()
    pids = [runtime["supervisor"]["pid"], *(identity["pid"] for identity in runtime.get("services", {}).values())]
    instance.kill_tree(runtime["supervisor"]["pid"])
    time.sleep(2)
    survivors = [pid for pid in pids if psutil.pid_exists(pid)]
    for pid in survivors:
        instance.kill_tree(pid)
    result: dict[str, Any] = {"killed_at": {"state": job["state"], "stage": job.get("stage")}, "survivors_after_supervisor_kill": survivors, "checks": {}}
    result["restart"] = instance.restart()
    result["checks"]["killed_in_target_stage"] = (job.get("stage") in stages or job["state"] in stages)
    resume_and_check(instance, item, result)
    return result


def case_qdrant_down(instance: Isolated, fixture: Path) -> dict[str, Any]:
    item = import_fixture(instance, fixture, f"Fautes/qdrant/{fixture.name}")
    job = wait_stage(instance, item["job_id"], {"indexing"})
    qdrant_pid = instance.runtime()["services"]["qdrant"]["pid"]
    instance.kill_tree(qdrant_pid)
    from services.runtime.supervisor import status, stop
    # Le superviseur peut arrêter toute l'instance à la perte d'un service : l'état se lit alors dans la base, en lecture seule.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        current = instance.job(item["job_id"])
        if current is None or current["state"] in DONE | {"paused"}:
            break
        time.sleep(1)
    with instance.database() as connection:
        failed = dict(connection.execute("SELECT state, stage, error_code FROM jobs WHERE id=?", (item["job_id"],)).fetchone())
        document = dict(connection.execute("SELECT state, active_generation_id FROM documents WHERE id=?", (item["document_id"],)).fetchone())
    result: dict[str, Any] = {"killed_at": {"state": job["state"], "stage": job.get("stage")}, "job_after_qdrant_loss": failed,
                              "document_after_qdrant_loss": document, "instance_after_qdrant_loss": status(instance.profile_path).get("status"), "checks": {}}
    result["checks"]["never_shown_ready"] = failed["state"] not in {"ready", "ready_partial"} and not document.get("active_generation_id") and document.get("state") != "ready"
    if status(instance.profile_path).get("status") in {"starting", "running", "stopping"}:
        result["stop"] = stop(instance.profile_path).get("status")
    result["restart"] = instance.restart()
    resume_and_check(instance, item, result)
    return result


def long_pdf(pages: int) -> bytes:
    """Document de texte natif de `pages` pages, chacune avec des phrases distinctes (structure de selftest.text_pdf)."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for index in range(pages):
        lines = [f"Fiche de contrôle {index + 1} sur {pages}."] + [f"Le relevé {index + 1}.{row} du banc FAUTE-{index + 1:03d} vaut {row * 3 + index} unités." for row in range(1, 9)]
        content = "BT /F1 12 Tf 50 740 Td 20 TL " + " ".join(f"<{line.encode('cp1252').hex()}> Tj T*" for line in lines) + " ET"
        page_id, stream_id = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_id} 0 R")
        objects += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode(),
                    b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content.encode() + b"\nendstream"]
    objects[1] = f"<< /Type /Pages /Count {pages} /Kids [{' '.join(kids)}] >>".encode()
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", choices=["kill-extracting", "kill-embedding", "kill-vectors", "qdrant-down"])
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--pages", type=int, help="document synthétique de N pages produit sur place, à la place de --fixture")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    instance = Isolated(json.loads(args.instance.read_text(encoding="utf-8")))
    if args.pages:
        # Assez de pages pour que l'écriture des points dure plus que l'intervalle de sondage.
        args.fixture = Path(instance.state["root"]) / f"synthetique-{args.pages}p.pdf"
        args.fixture.write_bytes(long_pdf(args.pages))
    if not args.fixture:
        parser.error("--fixture ou --pages requis")
    report = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {"cases": {}}
    started = datetime.now(UTC)
    try:
        if args.case == "qdrant-down":
            result = case_qdrant_down(instance, args.fixture)
        else:
            result = case_kill(instance, args.fixture, {args.case.removeprefix("kill-")})
    except Exception as error:  # noqa: BLE001 - l'échec du cas est conservé dans le rapport
        result = {"error": f"{type(error).__name__}: {error}", "checks": {"completed": False}}
    result.update(fixture=args.fixture.name, started_utc=started.isoformat(), seconds=round((datetime.now(UTC) - started).total_seconds(), 1),
                  result="PASS" if result["checks"] and all(result["checks"].values()) else "FAIL")
    report["cases"][args.case] = result
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case": args.case, "result": result["result"], "checks": result["checks"], **({"error": result["error"]} if "error" in result else {})}, ensure_ascii=False))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
