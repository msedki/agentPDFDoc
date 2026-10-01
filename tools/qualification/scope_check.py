"""Filtres de périmètre appliqués avant la coupe top-k, avec Qdrant et E5 réels sur une instance isolée (D04.2, D04.8).

L'instance est démarrée par `tools/qualification/e2e_instance.py start`. L'outil y importe deux PDF synthétiques produits
sur place : un document hors périmètre (`hors-champ/`) de 32 pages consacrées au freinage, et un document cible
(`confort/sous-dossier/`) de 3 pages titrées en gras, sans aucun terme de la question. La question « frein disque garniture » ne peut donc
rien trouver dans la cible par la voie plein texte : tout passage cible rendu vient de la voie dense.

Contrôles :
- recherche dense réelle sans filtre de périmètre (vecteur de la question calculé par E5, requête Qdrant directe) : les
  `dense_top_k` premiers points sont tous hors périmètre ; un filtre appliqué après la coupe ne laisserait rien ;
- voie plein texte de la cible vide pour cette question (lecture SQLite seule) ;
- pour les périmètres dossier récursif, documents, pages (et section si l'extraction en a produit) : recherche et
  contexte d'évaluation (`/admin/evaluation/context`, sans modèle) non vides, chaque passage dans le périmètre demandé ;
- sélection courte (D04.8) : seul le texte sélectionné est rendu et transmis, sans aucune requête dense, compteur
  `rest_responses_total` de Qdrant inchangé ; une recherche témoin sur le document l'incrémente, ce qui valide la mesure.

    .venv\\Scripts\\python.exe tools/qualification/scope_check.py --instance <etat.json> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fault_check import Isolated, import_fixture, wait_done  # noqa: E402

from services.api.embedding import EmbeddingService  # noqa: E402
from services.api.retrieval import match_expression  # noqa: E402
from services.api.settings import Settings  # noqa: E402

QUESTION = "frein disque garniture"


def text_pdf(pages: list[list[str]], headings: list[str] | None = None) -> bytes:
    """PDF de texte natif, une ligne par opérateur Tj (structure de `fault_check.long_pdf`), titre de page en gras facultatif."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for index, lines in enumerate(pages):
        heading = f"BT /F2 18 Tf 50 750 Td <{headings[index].encode('cp1252').hex()}> Tj ET " if headings else ""
        content = heading + "BT /F1 12 Tf 50 710 Td 20 TL " + " ".join(f"<{line.encode('cp1252').hex()}> Tj T*" for line in lines) + " ET"
        page_id, stream_id = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_id} 0 R")
        objects += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {stream_id} 0 R >>".encode(),
                    b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content.encode() + b"\nendstream"]
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>".encode()
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def noise_pages() -> list[list[str]]:
    return [[f"Fiche de freinage {page} sur 32."] + [f"Le frein à disque FR-{page:02d} serre la garniture contre le disque à {2 + row * 0.5:.1f} bar, garniture usée remplacée au contrôle {row}."
                                                    for row in range(1, 9)] for page in range(1, 33)]


def target_pages() -> list[list[str]]:
    return [[f"Fiche confort {page} sur 3."] + [f"Le siège SC-{page}{row} offre une assise de {380 + row * 5} mm et un dossier incliné de {10 + row} degrés pour le voyageur."
                                               for row in range(1, 9)] for page in range(1, 4)]


def in_scope(source: dict[str, Any], document_id: str, pages: set[int] | None, blocks: set[str] | None) -> bool:
    return (source["document_id"] == document_id and (pages is None or set(source["page_indices"]) <= pages)
            and all((pages is None or block["page_index"] in pages) and (blocks is None or block["id"] in blocks) for block in source["blocks"]))


def dense_queries(instance: Isolated, key: str) -> int:
    """Requêtes de recherche dense reçues par le Qdrant de l'instance (compteur natif de `/metrics`)."""
    response = httpx.get(f"{instance.profile['qdrant']['url']}/metrics", headers={"api-key": key}, trust_env=False, timeout=30)
    response.raise_for_status()
    return sum(int(float(line.rsplit(" ", 1)[1])) for line in response.text.splitlines()
               if line.startswith("rest_responses_total{") and "/points/query" in line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    instance = Isolated(json.loads(args.instance.read_text(encoding="utf-8")))
    started = datetime.now(UTC)
    root = Path(instance.state["root"])
    noise_pdf, target_pdf = root / "bruit-freinage.pdf", root / "cible-confort.pdf"
    noise_pdf.write_bytes(text_pdf(noise_pages()))
    target_pdf.write_bytes(text_pdf(target_pages(), ["Confort des sièges", "Éclairage intérieur", "Accès des voyageurs"]))
    imported = {"noise": import_fixture(instance, noise_pdf, "hors-champ/bruit-freinage.pdf"),
                "target": import_fixture(instance, target_pdf, "confort/sous-dossier/cible-confort.pdf")}
    jobs = {name: wait_done(instance, item["job_id"]) for name, item in imported.items()}
    admission_retries = 0
    # Mémoire de l'hôte partagée : un import refusé par l'admission est repris explicitement, comme le ferait l'utilisateur.
    while admission_retries < 10 and any(job.get("error_code") == "resource_admission_denied" for job in jobs.values()):
        admission_retries += 1
        time.sleep(30)
        with instance.client() as client:
            for job in jobs.values():
                if job.get("error_code") == "resource_admission_denied":
                    client.post(f"/api/v1/jobs/{job['id']}/resume").raise_for_status()
        jobs = {name: wait_done(instance, item["job_id"]) for name, item in imported.items()}
    checks: dict[str, bool] = {"imports_ready": all(job["state"] == "ready" for job in jobs.values())}
    if not checks["imports_ready"]:
        failed: dict[str, Any] = {"criteria": ["D04.2", "D04.8"], "started_utc": started.isoformat(), "result": "FAIL", "checks": checks,
                                  "jobs": {name: {key: job.get(key) for key in ("state", "stage", "error_code")} for name, job in jobs.items()}}
        args.report.write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failed, ensure_ascii=False))
        return 1
    target_document, target_version = imported["target"]["document_id"], imported["target"]["version_id"]
    settings = Settings.load(instance.profile_path)
    dense_top_k = settings.value("retrieval", "dense_top_k", 24)
    with instance.database() as connection:
        generations = {row["id"]: row["active_generation_id"] for row in connection.execute("SELECT id, active_generation_id FROM documents WHERE deleted_at IS NULL")}
        chunks = {row["document_id"]: row["n"] for row in connection.execute(
            "SELECT d.id document_id, count(*) n FROM chunks c JOIN documents d ON d.active_generation_id=c.generation_id GROUP BY d.id")}
        target_lexical = connection.execute("SELECT count(*) FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid WHERE c.generation_id=? AND chunks_fts MATCH ?",
                                            (generations[target_document], match_expression(QUESTION))).fetchone()[0]
        sections = [row[0] for row in connection.execute("SELECT id FROM sections WHERE generation_id=? ORDER BY page_index, id", (generations[target_document],))]
    checks["noise_chunks_exceed_dense_top_k"] = chunks.get(imported["noise"]["document_id"], 0) > dense_top_k
    checks["target_lexical_lane_empty"] = target_lexical == 0
    # Recherche dense sans autre filtre que les générations actives : ce que verrait une coupe faite avant le périmètre.
    vector = EmbeddingService(settings).embed([QUESTION], False)[0]
    key = (instance.data / "control" / "qdrant-api-key").read_text(encoding="ascii").strip()
    with instance.client() as client:
        collection = client.get("/api/v1/diagnostics").json()["qdrant_collection"]
        response = httpx.post(f"{instance.profile['qdrant']['url']}/collections/{collection}/points/query", headers={"api-key": key}, trust_env=False, timeout=60,
                              json={"query": vector, "using": "dense", "limit": dense_top_k, "with_payload": True, "with_vector": False,
                                    "params": {"hnsw_ef": settings.value("retrieval", "hnsw_ef", 64)},
                                    "filter": {"must": [{"key": "generation_id", "match": {"any": [g for g in generations.values() if g]}}]}})
        if response.status_code != 200:
            raise RuntimeError(f"Qdrant {response.status_code} : {response.text[:500]}")
        unfiltered = response.json()["result"]["points"]
        checks["unfiltered_dense_top_k_all_outside"] = len(unfiltered) == dense_top_k and all(point["payload"]["document_id"] != target_document for point in unfiltered)
        folders = {folder["path"]: folder["id"] for folder in client.get("/api/v1/library/tree", params={"limit": 200}).json()["folders"]}
        scopes: dict[str, tuple[dict[str, Any], set[int] | None, set[str] | None]] = {
            "folder_recursive": ({"kind": "folder", "folderId": folders["confort"], "recursive": True}, None, None),
            "documents": ({"kind": "documents", "documentIds": [target_document]}, None, None),
            "pages": ({"kind": "pages", "versionId": target_version, "pageStart": 1, "pageEnd": 1}, {1}, None)}
        if sections:
            with instance.database() as connection:
                section_blocks = {row[0] for row in connection.execute("SELECT id FROM blocks WHERE generation_id=? AND section_id=?", (generations[target_document], sections[-1]))}
            scopes["section"] = ({"kind": "section", "versionId": target_version, "sectionId": sections[-1]}, None, section_blocks)
        results: dict[str, Any] = {}
        for name, (scope, pages, blocks) in scopes.items():
            searched = client.post("/api/v1/search", json={"question": QUESTION, "scope": scope})
            context = client.post("/api/v1/admin/evaluation/context", json={"question": QUESTION, "scope": scope})
            searched.raise_for_status()
            context.raise_for_status()
            found, top10, sent = searched.json()["results"], searched.json()["top10"], context.json()["context_sources"]
            results[name] = {"results": len(found), "top10": len(top10), "context_sources": len(sent),
                             "pages": sorted({page for source in found + sent for page in source["page_indices"]}),
                             "model_called": context.json()["model_called"]}
            checks[f"{name}_non_empty_and_in_scope"] = bool(found and sent) and all(in_scope(source, target_document, pages, blocks) for source in found + top10 + sent)
        block = next(item for item in client.get(f"/api/v1/versions/{target_version}/pages/1/blocks").json()["blocks"] if len(item["text"]) >= 40 and item["type"] != "heading")
        span = {"extractionRevisionId": block["extraction_revision_id"], "blockId": block["id"], "blockTextSha256": block["source_text_hash"],
                "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": 30}
        selection = {"kind": "selection", "versionId": target_version, "spans": [span]}
        before = dense_queries(instance, key)
        searched = client.post("/api/v1/search", json={"question": QUESTION, "scope": selection})
        context = client.post("/api/v1/admin/evaluation/context", json={"question": QUESTION, "scope": selection, "mode": "selection"})
        searched.raise_for_status()
        context.raise_for_status()
        after = dense_queries(instance, key)
        client.post("/api/v1/search", json={"question": QUESTION, "scope": {"kind": "documents", "documentIds": [target_document]}}).raise_for_status()
        witness = dense_queries(instance, key)
        texts = [source["text"] for source in searched.json()["results"] + context.json()["context_sources"]]
        results["selection"] = {"results": len(searched.json()["results"]), "context_sources": len(context.json()["context_sources"]),
                                "dense_queries_before": before, "dense_queries_after": after, "dense_queries_after_witness": witness}
        checks["selection_only_selected_text"] = len(texts) == 2 and set(texts) == {block["text"][:30]}
        checks["selection_without_dense_query"] = after == before and witness > after
    report = {"criteria": ["D04.2", "D04.8"], "started_utc": started.isoformat(), "seconds": round((datetime.now(UTC) - started).total_seconds(), 1),
              "question": QUESTION, "dense_top_k": dense_top_k, "chunks": {"noise": chunks.get(imported["noise"]["document_id"], 0), "target": chunks.get(target_document, 0)},
              "target_lexical_matches": target_lexical, "target_sections": len(sections), "admission_retries": admission_retries,
              "unfiltered_dense": {"points": len(unfiltered), "target_points": sum(point["payload"]["document_id"] == target_document for point in unfiltered)},
              "scopes": results, "checks": checks, "result": "PASS" if all(checks.values()) else "FAIL"}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "checks": checks}, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
