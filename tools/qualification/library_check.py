"""Qualification de la bibliothèque par l'API réelle d'une instance isolée (critères D02 et D03), sans génération.

L'instance est démarrée par `tools/qualification/e2e_instance.py start` ; cet outil lit son état (origine, jeton) et joue
un cas à la fois, avec les fixtures contrôlées de `fixtures/qualification-v2.1/`. Chaque cas ajoute son résultat au
rapport ; aucun cas ne touche la bibliothèque de l'utilisateur.

    tree      import d'un dossier : sous-dossiers Unicode, fichiers homonymes, originaux relus octet pour octet (D02.1, D02.2)
    reimport  réimport identique : même document, version et traitement, aucun calcul supplémentaire (D03.1)
    move      déplacement : chemin changé, aucun traitement ni calcul d'embedding (D03.2)
    versions  seconde version au même chemin : invisible en recherche avant sa publication (D03.3)
    delete    retrait : exclu des recherches aussitôt, points Qdrant, fragments et index plein texte nettoyés ensuite (D03.4)
    errors    PDF chiffré, structure invalide, page blanche : état explicite (D02.8)
    size      PDF au-delà de la limite du profil : refus 413, aucun document créé (D02.8 ; instance lancée avec --max-file-mib)

    .venv\\Scripts\\python.exe tools/qualification/library_check.py <cas> --instance <etat.json> --report <rapport.json>
    .venv/bin/python tools/qualification/library_check.py <cas> --instance <etat.json> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures/qualification-v2.1"
DONE = {"ready", "ready_partial", "error", "cancelled"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Instance:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        token = Path(state["token_file"]).read_text(encoding="ascii").strip()
        self.client = httpx.Client(base_url=state["origin"], headers={"Origin": state["origin"], "x-rag-control-token": token}, timeout=120, trust_env=False)

    def counters(self) -> dict[str, int]:
        diagnostics = self.client.get("/api/v1/diagnostics").json()
        return {"embedding_requests": diagnostics["indexing_cache"]["embedding_requests"], "embedding_texts": diagnostics["indexing_cache"]["embedding_texts_submitted"],
                "worker_launches": diagnostics["ingestion_cache"]["native_worker_launches"]}

    def jobs(self) -> list[dict[str, Any]]:
        return self.client.get("/api/v1/jobs", params={"limit": 200}).json()["jobs"]

    def wait(self, job_id: str, timeout: float = 600) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = next(item for item in self.jobs() if item["id"] == job_id)
            if job["state"] in DONE:
                return job
            time.sleep(2)
        raise TimeoutError(f"traitement {job_id} non terminé en {timeout:.0f} s")

    def import_file(self, path: Path, relative: str) -> httpx.Response:
        with path.open("rb") as handle:
            return self.client.post("/api/v1/documents/import", data={"relative_paths": json.dumps([relative])}, files={"files": (path.name, handle, "application/pdf")})

    def documents(self) -> list[dict[str, Any]]:
        return self.client.get("/api/v1/library/tree", params={"limit": 200}).json()["documents"]

    def search(self, question: str) -> list[dict[str, Any]]:
        response = self.client.post("/api/v1/search", json={"question": question, "scope": {"kind": "library"}})
        response.raise_for_status()
        return response.json()["top10"]


def case_tree(instance: Instance, report: dict) -> dict:
    folder = FIXTURES / "imports"
    files = sorted(path for path in folder.rglob("*.pdf"))
    imported = []
    for path in files:
        relative = path.relative_to(folder).as_posix()
        item = instance.import_file(path, relative).json()["imports"][0]
        imported.append({"relative_path": relative, **{key: item.get(key) for key in ("document_id", "version_id", "job_id")}, "fixture_sha256": sha(path)})
    for row in imported:
        row["job_state"] = instance.wait(row["job_id"])["state"]
    documents = {item["id"]: item for item in instance.documents()}
    for row in imported:
        document = documents[row["document_id"]]
        detail = instance.client.get(f"/api/v1/documents/{row['document_id']}").json()
        original = instance.client.get(f"/api/v1/versions/{row['version_id']}/file")
        row.update(library_path=document["relative_path"], version_sha256=detail["versions"][0]["sha256"],
                   original_sha256=hashlib.sha256(original.content).hexdigest(), original_http=original.status_code)
    report["tree_documents"] = {row["relative_path"]: row["document_id"] for row in imported}
    checks = {"distinct_documents_for_homonyms": len({row["document_id"] for row in imported}) == len(imported) == 2,
              "unicode_paths_preserved": all(row["library_path"] == row["relative_path"] for row in imported),
              "extraction_ready": all(row["job_state"] == "ready" for row in imported),
              "original_bytes_identical": all(row["original_http"] == 200 and row["original_sha256"] == row["fixture_sha256"] == row["version_sha256"] for row in imported)}
    return {"imported": imported, "checks": checks}


def case_reimport(instance: Instance, report: dict) -> dict:
    relative = "Unité hiver/Commun.pdf"
    before = {"counters": instance.counters(), "jobs": len(instance.jobs()), "versions": len(instance.client.get(f"/api/v1/documents/{report['tree_documents'][relative]}").json()["versions"])}
    item = instance.import_file(FIXTURES / "imports" / relative, relative).json()["imports"][0]
    time.sleep(3)
    after = {"counters": instance.counters(), "jobs": len(instance.jobs()), "versions": len(instance.client.get(f"/api/v1/documents/{report['tree_documents'][relative]}").json()["versions"])}
    checks = {"same_document": item["document_id"] == report["tree_documents"][relative], "reused": item.get("reused") is True,
              "no_new_job_or_version": before["jobs"] == after["jobs"] and before["versions"] == after["versions"],
              "no_new_extraction_or_embedding": before["counters"] == after["counters"]}
    return {"response": item, "before": before, "after": after, "checks": checks}


def case_move(instance: Instance, report: dict) -> dict:
    document_id = report["tree_documents"]["Unité été/Commun.pdf"]
    before = {"counters": instance.counters(), "jobs": len(instance.jobs())}
    response = instance.client.post(f"/api/v1/documents/{document_id}/move", json={"relative_path": "Archives/Commun été.pdf"})
    time.sleep(3)
    after = {"counters": instance.counters(), "jobs": len(instance.jobs())}
    path = next(item["relative_path"] for item in instance.documents() if item["id"] == document_id)
    found = [source for source in instance.search("code de la fiche QH-A") if source["document_id"] == document_id]
    checks = {"moved": response.status_code == 200 and path == "Archives/Commun été.pdf", "no_new_job": before["jobs"] == after["jobs"],
              "no_new_extraction_or_embedding": before["counters"] == after["counters"], "still_searchable_at_new_path": bool(found) and all(source["relative_path"] == path for source in found)}
    return {"http_status": response.status_code, "path_after": path, "before": before, "after": after, "checks": checks}


def values(sources: list[dict[str, Any]], document_id: str) -> set[str]:
    text = " ".join(source["text"] for source in sources if source["document_id"] == document_id)
    return {value for value in ("2.7", "2,7", "4.9", "4,9") if value in text}


def case_versions(instance: Instance, report: dict) -> dict:
    relative = "Procédure QV-01.pdf"
    first = instance.import_file(FIXTURES / "versions/v1" / relative, relative).json()["imports"][0]
    first_job = instance.wait(first["job_id"])
    question = "pression de réglage QV-01"
    before = values(instance.search(question), first["document_id"])
    second = instance.import_file(FIXTURES / "versions/v2" / relative, relative).json()["imports"][0]
    # Pendant tout le traitement de la seconde version (file, extraction, indexation), la recherche ne voit que la première.
    observations: list[dict[str, Any]] = []
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        job = next(item for item in instance.jobs() if item["id"] == second["job_id"])
        if job["state"] in DONE:
            break
        seen = values(instance.search(question), first["document_id"])
        active = instance.client.get(f"/api/v1/documents/{first['document_id']}").json().get("active_version_id")
        observations.append({"job_state": job["state"], "stage": job.get("stage"), "values": sorted(seen), "active_version_is_first": active == first["version_id"]})
        time.sleep(1)
    second_job = instance.wait(second["job_id"])
    after = values(instance.search(question), first["document_id"])
    stages = sorted({item["stage"] or item["job_state"] for item in observations})
    checks = {"same_document_new_version": second["document_id"] == first["document_id"] and second["version_id"] != first["version_id"],
              "first_published": first_job["state"] == "ready" and before & {"2.7", "2,7"} != set() and not before & {"4.9", "4,9"},
              "second_invisible_before_publication": len(observations) >= 3 and all(item["active_version_is_first"] and set(item["values"]) & {"2.7", "2,7"}
                                                                                   and not set(item["values"]) & {"4.9", "4,9"} for item in observations),
              "second_visible_after_publication": second_job["state"] == "ready" and bool(after & {"4.9", "4,9"}) and not after & {"2.7", "2,7"}}
    return {"first": first, "second": second, "observations_before_publication": len(observations), "stages_observed": stages,
            "values_before": sorted(before), "values_after": sorted(after), "checks": checks}


def qdrant_count(instance: Instance, generation_id: str) -> int:
    profile = yaml.safe_load(Path(instance.state["profile"]).read_text(encoding="utf-8"))
    key = (Path(instance.state["token_file"]).parent / "qdrant-api-key").read_text(encoding="ascii").strip()
    collection = instance.client.get("/api/v1/diagnostics").json()["qdrant_collection"]
    response = httpx.post(f"{profile['qdrant']['url']}/collections/{collection}/points/count", headers={"api-key": key},
                          json={"filter": {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}, "exact": True}, trust_env=False, timeout=30)
    response.raise_for_status()
    return int(response.json()["result"]["count"])


def case_delete(instance: Instance, report: dict) -> dict:
    document_id = report["tree_documents"]["Unité hiver/Commun.pdf"]
    generation = instance.client.get(f"/api/v1/documents/{document_id}").json()["active_generation_id"]
    points_before = qdrant_count(instance, generation)
    found_before = any(source["document_id"] == document_id for source in instance.search("code de la fiche QH-B"))
    response = instance.client.delete(f"/api/v1/documents/{document_id}")
    found_after = any(source["document_id"] == document_id for source in instance.search("code de la fiche QH-B"))
    deadline, points_after = time.monotonic() + 120, points_before
    while time.monotonic() < deadline:
        points_after = qdrant_count(instance, generation)
        pending = instance.client.get("/api/v1/diagnostics").json()["reconciliation"]["pending_cleanup"]
        if points_after == 0 and pending == 0:
            break
        time.sleep(3)
    # Index plein texte : lecture seule de la base de l'instance isolée ; les lignes FTS suivent la table chunks par déclencheur.
    profile = yaml.safe_load(Path(instance.state["profile"]).read_text(encoding="utf-8"))
    with sqlite3.connect(f"file:{Path(profile['app']['data_dir']) / 'app.sqlite3'}?mode=ro", uri=True) as connection:
        chunks_left = connection.execute("SELECT count(*) FROM chunks WHERE generation_id=?", (generation,)).fetchone()[0]
        chunks_total = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
        fts_total = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    checks = {"deleted": response.status_code == 200, "found_before": found_before, "excluded_immediately": not found_after,
              "qdrant_points_cleaned": points_before > 0 and points_after == 0, "sqlite_fragments_cleaned": chunks_left == 0,
              "full_text_index_follows_fragments": fts_total == chunks_total,
              "remaining_index_consistent": instance.client.get("/api/v1/diagnostics").json()["index_consistency"]["status"] == "consistent"}
    return {"generation_id": generation, "points_before": points_before, "points_after": points_after, "sqlite_chunks_left": chunks_left,
            "chunks_total": chunks_total, "fts_rows_total": fts_total, "checks": checks}


def case_errors(instance: Instance, report: dict) -> dict:
    expected = {"Chiffré mot de passe.pdf": "error", "Structure invalide.pdf": "error", "Page blanche.pdf": "ready"}
    rows = []
    for name, state in expected.items():
        response = instance.import_file(FIXTURES / "errors" / name, f"Erreurs/{name}")
        row: dict[str, Any] = {"file": name, "http_status": response.status_code, "expected_state": state}
        if response.status_code == 202:
            item = response.json()["imports"][0]
            job = instance.wait(item["job_id"])
            row.update(job_state=job["state"], error_code=job.get("error_code"), error_message=job.get("error_message"))
            if job["state"] == "ready":
                page = instance.client.get(f"/api/v1/versions/{item['version_id']}/pages/0/blocks").json()
                row.update(page_state=page["page"].get("extraction_state"), blocks=len(page["blocks"]))
        else:
            row.update(code=response.json().get("code"), message=response.json().get("message"))
        rows.append(row)
    by_name = {row["file"]: row for row in rows}
    checks = {"encrypted_explicit_error": by_name["Chiffré mot de passe.pdf"].get("job_state") == "error" and bool(by_name["Chiffré mot de passe.pdf"].get("error_code")),
              "invalid_structure_explicit": (by_name["Structure invalide.pdf"].get("job_state") == "error" and bool(by_name["Structure invalide.pdf"].get("error_code")))
              or by_name["Structure invalide.pdf"]["http_status"] == 400,
              "blank_page_declared_blank": by_name["Page blanche.pdf"].get("job_state") == "ready" and by_name["Page blanche.pdf"].get("page_state") == "blank"
              and by_name["Page blanche.pdf"].get("blocks") == 0}
    return {"rows": rows, "checks": checks}


def case_size(instance: Instance, report: dict) -> dict:
    path = FIXTURES / "errors/Limite de taille isolée.pdf"
    before = len(instance.documents())
    response = instance.import_file(path, "Erreurs/Limite de taille isolée.pdf")
    after = len(instance.documents())
    body = response.json()
    checks = {"refused_413": response.status_code == 413 and body.get("code") == "file_too_large", "no_document_created": before == after}
    return {"bytes": path.stat().st_size, "http_status": response.status_code, "code": body.get("code"), "message": body.get("message"), "checks": checks}


CASES = {"tree": case_tree, "reimport": case_reimport, "move": case_move, "versions": case_versions, "delete": case_delete, "errors": case_errors, "size": case_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.instance.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {"cases": {}}
    instance = Instance(state)
    started = datetime.now(UTC)
    try:
        result = CASES[args.case](instance, report)
    except Exception as error:  # noqa: BLE001 - l'échec d'un cas est conservé dans le rapport
        result = {"error": f"{type(error).__name__}: {error}", "checks": {"completed": False}}
    result.update(started_utc=started.isoformat(), seconds=round((datetime.now(UTC) - started).total_seconds(), 1),
                  result="PASS" if result["checks"] and all(result["checks"].values()) else "FAIL")
    report["cases"][args.case] = result
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case": args.case, "result": result["result"], "checks": result["checks"], "seconds": result["seconds"], **({"error": result["error"]} if "error" in result else {})}, ensure_ascii=False))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
