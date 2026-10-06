"""Sonde d'identité d'embedding sur une instance isolée (mécanismes de D03.8), sans génération ni question au modèle.

Ce n'est pas une migration d'embedding. Le profil P1 ne diffère du profil P0 (profil livré, généré pour la racine de
l'essai) que par `embedding.model_id`, suffixé de `#qa-identity-probe` : graphe, tokenizer, préfixes et pooling restent
ceux d'E5. Cette substitution déclarée change l'empreinte d'identité dense, donc la collection Qdrant et la clé du cache
d'embeddings, sans changer l'espace vectoriel. Le critère D03.8 (vrai changement de modèle) reste NOT_RUN.

Déroulement, dans une racine neuve, avec des ports libres distincts de ceux de l'instance principale :
  1. P0 : import de trois fixtures versionnées (scan, natif, Unicode) ; empreinte F0, collection C0, points par
     génération ; recherche anglaise sans mot commun avec les documents (index plein texte contrôlé : branche dense seule).
  2. Arrêt coopératif puis démarrage sous P1 : readiness attendue 503 `absent_with_published_generations`.
  3. Réindexation du seul scan : aucun worker natif, une extraction réutilisée, embeddings recalculés, C1 créée, C0 intacte.
  4. Observations H-A1 (readiness et recherche quand un seul document est dans C1) et H-A2 (points remplacés dans C0).
  5. Réindexation des deux autres documents sous P1.
  6. Retour sous P0 : observation H-A3 avant réindexation, puis réindexation sans OCR ni calcul E5 (cache).
  7. Arrêt coopératif ; racine, journaux et rapports conservés.

Résultat PASS_MECHANISM seulement si l'OCR n'est pas refait, si les collections sont distinctes, si l'instance P1
n'envoie à C0 que la suppression des points des générations remplacées (journal Qdrant, lectures de la sonde exclues
par leur User-Agent ; toute recherche, lecture ou écriture d'une autre nature y reste refusée), si les générations
vivantes de C0 gardent leurs points et si les attendus des étapes sont tenus. H-A1 à H-A3 sont rapportées à part :
CONFIRMED, REFUTED ou INCONCLUSIVE. Le bloc `r26_idx_02` (PASS ou FAIL) vérifie le correctif R26-IDX-02 : état
`dense_migration_incomplete` et `documents_to_reindex` de /readiness, avertissement `dense_identity_mismatch` dans
l'état partiel et au retour sous P0, silence dans les états complets, générations remplacées retirées partout.

Linux (depuis la racine du projet, de préférence sous un verrou lourd partagé) :

    .venv/bin/python -B tools/qualification/embedding_identity_check.py --root <racine neuve> --ports <api,qdrant,ollama>

Windows (PowerShell) :

    .venv\\Scripts\\python.exe tools/qualification/embedding_identity_check.py --root <racine neuve> --ports <api,qdrant,ollama>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psutil  # noqa: E402
import yaml  # noqa: E402

DELIVERED = ROOT / "config/local16.yaml"
FIXTURES = ROOT / "fixtures/qualification-v2.1"
MANIFEST = ROOT / "evals/qualification-v2.1/manifest.json"
PROBE_SUFFIX = "#qa-identity-probe"
PROBE_AGENT = "r26-identity-probe/1"
LIBRARY_FOLDER = "Sonde identité"
# Scan pur (OCR d'une page), natif de développement et texte Unicode : fixtures versionnées, empreintes du manifeste.
DEFAULT_FIXTURES = {"scan": FIXTURES / "scans/Contrôle bilingue FR EN.pdf",
                    "native": FIXTURES / "development/Procédures/Atelier 1 - Banc pneumatique DA-P01.pdf",
                    "unicode": FIXTURES / "text/Unicode ligatures césures.pdf"}
# Question anglaise sur l'alimentation d'essai du banc DA-P01, sans mot commun avec les trois documents.
DEFAULT_QUESTION = "Which supply voltage powers each compressed air rig?"
JOB_DONE = {"ready", "ready_partial", "error", "cancelled"}
GENERATION_ROUTES = ("/api/v1/queries", "/api/v1/admin/evaluation")
QDRANT_LINE = re.compile(r'"(?P<method>[A-Z]+) (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3}) \S+ "[^"]*" "(?P<agent>[^"]*)"')
OLLAMA_LINE = re.compile(r'^\[GIN\].*\|\s+(?P<method>[A-Z]+)\s+"(?P<path>[^"]+)"', re.MULTILINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main_ports(profile: dict) -> dict[str, int]:
    return {"app": int(profile["app"]["port"]), "qdrant": int(profile["qdrant"]["url"].rsplit(":", 1)[1].rstrip("/")),
            "ollama": int(profile["llm"]["base_url"].rsplit(":", 1)[1].rstrip("/"))}


def check_isolation(root: Path, ports: dict[str, int], main_profile: dict, port_free: Callable[[int], bool]) -> Path:
    """Refuse toute cible qui pourrait toucher l'instance principale : racine existante non vide, racine de ses données,
    ports identiques ou occupés. Renvoie la racine résolue."""
    root = Path(root).resolve()
    main_data = (ROOT / main_profile["app"]["data_dir"]).resolve()
    if root == main_data or root.is_relative_to(main_data) or main_data.is_relative_to(root):
        raise ValueError(f"Racine refusée : elle recouvre les données de l'instance principale ({main_data})")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError(f"Racine refusée : {root} existe et n'est pas un dossier vide ; choisir une racine neuve")
    if set(ports) != {"app", "qdrant", "ollama"} or len(set(ports.values())) != 3:
        raise ValueError("Trois ports distincts sont requis : API, Qdrant, Ollama")
    shared = sorted(set(ports.values()) & set(main_ports(main_profile).values()))
    if shared:
        raise ValueError(f"Ports de l'instance principale refusés : {shared}")
    busy = [f"{name} {port}" for name, port in ports.items() if not port_free(port)]
    if busy:
        raise ValueError("Ports occupés : " + ", ".join(busy))
    return root


def probe_profile(profile: dict) -> dict:
    """P1 : copie de P0 dont seul `embedding.model_id` est suffixé (substitution déclarée, poids identiques)."""
    model_id = profile["embedding"]["model_id"]
    if model_id.endswith(PROBE_SUFFIX):
        raise ValueError("Le profil de base porte déjà l'identité de sonde")
    probe = copy.deepcopy(profile)
    probe["embedding"]["model_id"] = model_id + PROBE_SUFFIX
    return probe


def profile_differences(first: Any, second: Any, prefix: str = "") -> list[str]:
    """Chemins pointés des valeurs qui diffèrent entre deux profils (clés ajoutées ou retirées comprises)."""
    if isinstance(first, dict) and isinstance(second, dict):
        return [path for key in sorted(set(first) | set(second), key=str)
                for path in profile_differences(first.get(key), second.get(key), f"{prefix}{key}.")]
    return [] if first == second else [prefix.rstrip(".")]


def write_profiles(root: Path, ports: dict[str, int], base: Path = DELIVERED) -> dict[str, Path]:
    """P0 par le générateur de `init-profile` (chemins, ports et section runtime propres à la racine), puis P1."""
    from services.runtime.profile_setup import write_user_profile

    write_user_profile(base, root, ports=ports)
    p0 = root / "profile.yaml"
    probe = probe_profile(yaml.safe_load(p0.read_text(encoding="utf-8")))
    p1 = root / "profile-p1.yaml"
    with p1.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(f"# Profil de sonde : copie de profile.yaml, seul embedding.model_id suffixé de {PROBE_SUFFIX}.\n")
        yaml.safe_dump(probe, stream, allow_unicode=True, sort_keys=False)
    return {"p0": p0, "p1": p1}


def qdrant_requests(text: str, collection: str) -> dict[str, Any]:
    """Requêtes journalisées par Qdrant (actix) vers une collection : sonde (User-Agent dédié) et autres clients, ces
    derniers détaillés par route (« POST /points/delete », « GET / » pour la collection elle-même)."""
    counts: dict[str, Any] = {"total": 0, "probe": 0, "other": 0, "other_routes": {}}
    for match in QDRANT_LINE.finditer(text):
        path = match["path"].split("?", 1)[0]
        if path == f"/collections/{collection}" or path.startswith(f"/collections/{collection}/"):
            counts["total"] += 1
            counts["probe" if match["agent"] == PROBE_AGENT else "other"] += 1
            if match["agent"] != PROBE_AGENT:
                route = f"{match['method']} /{path[len(f'/collections/{collection}'):].lstrip('/')}"
                counts["other_routes"][route] = counts["other_routes"].get(route, 0) + 1
    return counts


def only_cleanup(requests: dict[str, Any] | None) -> bool:
    """Vrai si une autre vie d'instance n'a envoyé à la collection que des suppressions de points (nettoyage des
    générations remplacées, R26-IDX-02) : recherche, lecture, comptage ou écriture y restent interdits."""
    return requests is not None and set(requests.get("other_routes", {})) <= {"POST /points/delete"}


def ollama_requests(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in OLLAMA_LINE.finditer(text):
        counts[match["path"]] = counts.get(match["path"], 0) + 1
    return counts


def refuse_generation(request: httpx.Request) -> None:
    if request.url.path.startswith(GENERATION_ROUTES):
        raise RuntimeError("Sonde sans génération : route de question refusée " + request.url.path)


def counters(diagnostics: dict) -> dict[str, int]:
    indexing, ingestion = diagnostics["indexing_cache"], diagnostics["ingestion_cache"]
    return {"embedding_requests": indexing["embedding_requests"], "embedding_texts_submitted": indexing["embedding_texts_submitted"],
            "embedding_cache_hits": indexing["cache_hits"], "embedding_cache_misses": indexing["cache_misses"],
            "native_worker_launches": ingestion["native_worker_launches"], "extraction_reuses": ingestion["extraction_reuses"]}


def source_fingerprint() -> dict[str, str]:
    """Code et configuration exécutés par l'instance : une dérive pendant l'essai le rend inexploitable."""
    files = sorted({*ROOT.glob("services/**/*.py"), *ROOT.glob("services/api/migrations/*.sql"), *ROOT.glob("config/*")})
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + sha256(path).encode() + b"\n")
    return {"files": str(len(files)), "sha256": digest.hexdigest()}


def git_state() -> dict[str, Any]:
    """Révision et modifications locales du code exécuté (lecture seule ; absent si Git ne répond pas)."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=30, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "services", "config"], cwd=ROOT, capture_output=True,
                               text=True, timeout=30, check=True).stdout.splitlines()
        return {"head": head, "modified_services_or_config": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"head": None, "modified_services_or_config": None}


class Instance:
    """Instance réelle démarrée par le superviseur : API (jeton de contrôle, routes de question refusées), Qdrant en
    lecture directe identifiée par son User-Agent, base SQLite en lecture seule et journaux de la vie courante."""

    def __init__(self, profile_path: Path, state: dict):
        from services.runtime.supervisor import app_origin, data_path, load_profile

        profile = load_profile(profile_path)
        self.data = data_path(profile)
        origin, verify = app_origin(profile)
        token = (self.data / "control/admin-token").read_text(encoding="ascii").strip()
        self.api = httpx.Client(base_url=origin, headers={"Origin": origin, "X-RAG-Control-Token": token}, timeout=120,
                                trust_env=False, verify=verify, follow_redirects=False, event_hooks={"request": [refuse_generation]})
        key = (self.data / "control/qdrant-api-key").read_text(encoding="ascii").strip()
        self.qdrant = httpx.Client(base_url=profile["qdrant"]["url"], headers={"api-key": key, "User-Agent": PROBE_AGENT},
                                   timeout=30, trust_env=False)
        self.prefix = profile["qdrant"]["collection"] + "_"
        self.logs = {name: Path(service["log_path"]) for name, service in state.get("services", {}).items() if service.get("log_path")}

    def close(self) -> None:
        self.api.close()
        self.qdrant.close()

    def readiness(self) -> dict:
        response = self.api.get("/api/v1/readiness")
        body = response.json()
        return {"http_status": response.status_code, "status": body.get("status"), "qdrant_collection": body.get("qdrant_collection"),
                "blockers": body.get("blockers"), "dense_index": body.get("dense_index"), "documents_to_reindex": body.get("documents_to_reindex")}

    def diagnostics(self) -> dict:
        response = self.api.get("/api/v1/diagnostics")
        response.raise_for_status()
        return response.json()

    def import_file(self, path: Path, relative: str) -> dict:
        with path.open("rb") as handle:
            response = self.api.post("/api/v1/documents/import", data={"relative_paths": json.dumps([relative])},
                                     files={"files": (path.name, handle, "application/pdf")})
        response.raise_for_status()
        return response.json()["imports"][0]

    def reindex(self, document_id: str) -> str:
        response = self.api.post(f"/api/v1/documents/{document_id}/reindex")
        response.raise_for_status()
        return response.json()["job_id"]

    def wait(self, job_id: str, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            jobs = self.api.get("/api/v1/jobs", params={"limit": 200}).json()["jobs"]
            job = next((item for item in jobs if item["id"] == job_id), None)
            if job and job["state"] in JOB_DONE:
                return {"state": job["state"], "active": bool(job.get("active")), "error_code": job.get("error_code")}
            time.sleep(2)
        raise TimeoutError(f"Traitement {job_id} non terminé en {timeout:.0f} s")

    def search(self, question: str, scope: dict) -> dict:
        response = self.api.post("/api/v1/search", json={"question": question, "scope": scope})
        if response.status_code != 200:
            try:
                code = response.json().get("code")
            except ValueError:
                code = None
            return {"http_status": response.status_code, "code": code}
        body = response.json()
        return {"http_status": 200, "top10_documents": [source["document_id"] for source in body["top10"]],
                "results_documents": [source["document_id"] for source in body["results"]],
                "warnings": [{"code": warning.get("code"), "document_id": warning.get("document_id"), "document_ids": warning.get("document_ids")}
                             for warning in body["warnings"]]}

    def collections(self) -> list[str]:
        response = self.qdrant.get("/collections")
        response.raise_for_status()
        return sorted(item["name"] for item in response.json()["result"]["collections"] if item["name"].startswith(self.prefix))

    def count(self, collection: str, generation_id: str | None = None) -> int | None:
        body: dict[str, Any] = {"exact": True}
        if generation_id:
            body["filter"] = {"must": [{"key": "generation_id", "match": {"value": generation_id}}]}
        response = self.qdrant.post(f"/collections/{collection}/points/count", json=body)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return int(response.json()["result"]["count"])

    def connection(self) -> closing[sqlite3.Connection]:
        connection = sqlite3.connect(f"file:{self.data / 'app.sqlite3'}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return closing(connection)

    def sqlite_state(self) -> dict:
        with self.connection() as connection:
            documents = {row["id"]: {"relative_path": row["relative_path"], "active_generation_id": row["active_generation_id"], "state": row["state"]}
                         for row in connection.execute("SELECT id,relative_path,active_generation_id,state FROM documents WHERE deleted_at IS NULL")}
            generations = {row["id"]: {"document_id": row["document_id"], "fingerprint": row["fingerprint"], "state": row["state"],
                                       "published": row["published_at"] is not None, "extraction_revision_id": row["extraction_revision_id"],
                                       "coverage": json.loads(row["coverage_json"]), "chunks": row["chunks"]}
                           for row in connection.execute("SELECT g.id,v.document_id,g.fingerprint,g.state,g.published_at,g.extraction_revision_id,"
                                                         "g.coverage_json,(SELECT count(*) FROM chunks c WHERE c.generation_id=g.id) AS chunks "
                                                         "FROM index_generations g JOIN document_versions v ON v.id=g.version_id ORDER BY g.created_at")}
            cleanup = {row["generation_id"]: {"state": row["state"], "reason": row["reason"], "error_code": row["error_code"]}
                       for row in connection.execute("SELECT generation_id,state,reason,error_code FROM vector_cleanup")}
            cache = {row["model_identity"]: row["n"] for row in connection.execute("SELECT model_identity,count(*) AS n FROM embedding_cache GROUP BY model_identity")}
        return {"documents": documents, "generations": generations, "vector_cleanup": cleanup, "embedding_cache": cache}

    def lexical(self, question: str) -> dict:
        """Branche lexicale de la recherche : identifiants et expression FTS5 du code servi, comptés sur tous les fragments."""
        from services.api.retrieval import identifiers, match_expression

        expression = match_expression(question)
        with self.connection() as connection:
            hits = connection.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?", (expression,)).fetchone()[0] if expression else 0
        return {"identifiers": identifiers(question), "match_expression": expression, "fts_hits_all_fragments": hits}

    def log_text(self, name: str) -> str:
        path = self.logs.get(name)
        return path.read_text(encoding="utf-8", errors="replace") if path and path.is_file() else ""


class HostSampler(threading.Thread):
    """Mémoire disponible, swap et disque du poste, RSS cumulée des processus de l'instance (borne haute), toutes les 2 s."""

    def __init__(self, disk_root: Path, interval: float = 2.0):
        super().__init__(daemon=True)
        self.disk_root, self.interval = disk_root, interval
        self.pids: set[int] = set()
        self.samples: list[dict] = []
        self.halt = threading.Event()

    def sample(self) -> dict:
        rss = 0
        for pid in list(self.pids):
            try:
                process = psutil.Process(pid)
                rss += sum(item.memory_info().rss for item in [process, *process.children(recursive=True)])
            except psutil.Error:
                continue
        return {"utc": datetime.now(UTC).isoformat(), "available_mib": round(psutil.virtual_memory().available / 1048576, 1),
                "swap_free_mib": round(psutil.swap_memory().free / 1048576, 1), "instance_rss_mib": round(rss / 1048576, 1),
                "disk_free_mib": round(shutil.disk_usage(self.disk_root).free / 1048576, 1)}

    def run(self) -> None:
        while not self.halt.wait(self.interval):
            self.samples.append(self.sample())

    def summary(self) -> dict:
        samples = self.samples or [self.sample()]
        return {"samples": len(self.samples), "minimum_available_mib": min(item["available_mib"] for item in samples),
                "maximum_instance_rss_mib_upper_bound": max(item["instance_rss_mib"] for item in samples),
                "minimum_swap_free_mib": min(item["swap_free_mib"] for item in samples),
                "minimum_disk_free_mib": min(item["disk_free_mib"] for item in samples)}


def observe(instance: Any, label: str, question: str, documents: dict[str, str]) -> dict:
    """État complet d'une phase : readiness, identité, compteurs, cohérence, points par collection et par génération,
    état SQLite, recherche sur la bibliothèque puis document par document (aucune génération)."""
    diagnostics = instance.diagnostics()
    sqlite = instance.sqlite_state()
    collections = instance.collections()
    points = {collection: {"total": instance.count(collection),
                           "by_generation": {generation: instance.count(collection, generation) for generation in sqlite["generations"]}}
              for collection in collections}
    search = {"library": instance.search(question, {"kind": "library"})}
    search.update({key: instance.search(question, {"kind": "documents", "documentIds": [document_id]}) for key, document_id in documents.items()})
    return {"label": label, "utc": datetime.now(UTC).isoformat(), "readiness": instance.readiness(),
            "dense_identity": diagnostics["dense_identity"], "collection": diagnostics["qdrant_collection"],
            "counters": counters(diagnostics), "last_extraction": diagnostics["ingestion_cache"].get("last_extraction"),
            "index_consistency": diagnostics["index_consistency"], "pending_cleanup": diagnostics["reconciliation"]["pending_cleanup"],
            "collections": collections, "points": points, "sqlite": sqlite, "search": search}


def reindex(instance: Any, document_ids: list[str], timeout: float) -> dict:
    before = counters(instance.diagnostics())
    jobs = {document_id: instance.reindex(document_id) for document_id in document_ids}
    finals = {document_id: instance.wait(job_id, timeout) for document_id, job_id in jobs.items()}
    diagnostics = instance.diagnostics()
    after = counters(diagnostics)
    sqlite = instance.sqlite_state()
    generations = {document_id: sqlite["documents"][document_id]["active_generation_id"] for document_id in document_ids}
    return {"jobs": jobs, "finals": finals, "before": before, "after": after, "delta": {key: after[key] - before[key] for key in after},
            "new_generations": generations, "fragments": {document_id: sqlite["generations"][generation]["chunks"] if generation else None
                                                          for document_id, generation in generations.items()},
            "last_extraction": diagnostics["ingestion_cache"].get("last_extraction")}


def settle(instance: Any, timeout: float = 120) -> dict:
    """Attend que le nettoyage vectoriel n'ait plus de génération en attente (réconciliateur, passe chaque seconde)."""
    started = time.monotonic()
    pending = instance.diagnostics()["reconciliation"]["pending_cleanup"]
    while pending and time.monotonic() - started < timeout:
        time.sleep(1)
        pending = instance.diagnostics()["reconciliation"]["pending_cleanup"]
    return {"pending_cleanup": pending, "seconds": round(time.monotonic() - started, 1)}


def found(phase: dict, key: str) -> bool | None:
    """Vrai si la recherche limitée au document le retrouve ; None si la recherche n'a pas répondu 200."""
    result = phase["search"][key]
    return None if result["http_status"] != 200 else bool(result["top10_documents"])


def warned(phase: dict, keys: list[str], document_ids: list[str]) -> list[dict]:
    """Avertissements des recherches (bibliothèque et documents `keys`) qui visent l'un de `document_ids` ou aucun document :
    un avertissement propre à un autre document (provenance OCR d'un passage du scan, par exemple) n'en fait pas partie."""
    def concerns(warning: dict) -> bool:
        if warning.get("document_ids"):
            return bool(set(warning["document_ids"]) & set(document_ids))
        return warning.get("document_id") in {None, *document_ids}
    return [warning for key in ["library", *keys] for warning in phase["search"][key].get("warnings") or [] if concerns(warning)]


def mismatched(phase: dict, key: str) -> list[str] | None:
    """Documents nommés par l'avertissement `dense_identity_mismatch` d'une recherche ; None si elle n'a pas répondu 200."""
    result = phase["search"][key]
    if result["http_status"] != 200:
        return None
    return sorted(document for warning in result.get("warnings") or [] if warning.get("code") == "dense_identity_mismatch"
                  for document in warning.get("document_ids") or [])


def generation_points(phase: dict, collection: str, generation: str | None) -> int | None:
    return phase["points"].get(collection, {}).get("by_generation", {}).get(generation) if generation else None


def verdict(observations: dict[str, bool | None]) -> str:
    if any(value is None for value in observations.values()):
        return "INCONCLUSIVE"
    return "CONFIRMED" if all(observations.values()) else "REFUTED"


def evaluate(report: dict) -> dict:
    """Contrôles du mécanisme, attendus des étapes et hypothèses, tirés des seules observations du rapport."""
    phases, steps, keys = report.get("phases", {}), report.get("steps", {}), report.get("documents", {})
    needed = ("p0_published", "p1_started", "p1_scan_reindexed", "p1_all_reindexed", "p0_returned", "p0_reindexed")
    if report.get("error") or any(label not in phases for label in needed):
        return {"mechanism_checks": {}, "expectations": {}, "hypotheses": {}, "r26_idx_02": {}, "result": "ERROR"}
    p0, p1s, p1a, p1b, p0r, p0b = (phases[label] for label in needed)
    c0, c1 = p0["collection"], p1s["collection"]
    f0, f1 = p0["dense_identity"].get("fingerprint"), p1s["dense_identity"].get("fingerprint")
    scan, others = keys["scan"], [keys[name] for name in ("native", "unicode")]
    all_ids = [scan, *others]
    names = {document_id: name for name, document_id in keys.items()}
    g0 = {document_id: p0["sqlite"]["documents"][document_id]["active_generation_id"] for document_id in all_ids}
    g1 = {document_id: p1b["sqlite"]["documents"][document_id]["active_generation_id"] for document_id in all_ids}
    g2 = {document_id: p0b["sqlite"]["documents"][document_id]["active_generation_id"] for document_id in all_ids}
    fragments = {document_id: p0["sqlite"]["generations"][g0[document_id]]["chunks"] for document_id in all_ids}
    scan_step, others_step, back_step = steps["reindex_scan_p1"], steps["reindex_others_p1"], steps["reindex_all_p0"]
    identity_fields = {key for key in p0["dense_identity"] if key not in {"model_id", "fingerprint"}}
    lexical = p0.get("lexical", {})
    imports = steps["import_p0"]["imports"]
    expectations = {
        "fixtures_match_manifest": all(item["sha256"] == item["manifest_sha256"] for item in report["fixtures"].values()),
        "p0_documents_ready_and_active": all(item["final"]["state"] == "ready" and item["final"]["active"] for item in imports.values()),
        "p0_points_match_fragments": all(fragments[d] > 0 and generation_points(p0, c0, g0[d]) == fragments[d] for d in all_ids),
        "p0_lexical_branch_empty": lexical.get("fts_hits_all_fragments") == 0 and lexical.get("identifiers") == [],
        "p0_dense_serves_each_document": all(found(p0, names[d]) is True for d in all_ids),
        "p1_only_model_id_differs": report["profiles"]["differences"] == ["embedding.model_id"]
        and all(p0["dense_identity"].get(key) == p1s["dense_identity"].get(key) for key in identity_fields),
        "p1_identity_and_collection_changed": bool(f0 and f1) and f0 != f1 and c0 != c1,
        "p1_readiness_blocked_without_collection": p1s["readiness"]["http_status"] == 503
        and p1s["readiness"]["qdrant_collection"] == "absent_with_published_generations",
        "p1_scan_reindex_ready": all(item["state"] == "ready" and item["active"] for item in scan_step["finals"].values()),
        "p1_scan_no_native_worker": scan_step["delta"]["native_worker_launches"] == 0,
        "p1_scan_one_extraction_reuse": scan_step["delta"]["extraction_reuses"] == 1,
        "p1_scan_embeddings_recomputed": scan_step["delta"]["embedding_texts_submitted"] == scan_step["fragments"][scan] > 0,
        "p1_scan_collection_created": c1 in p1a["collections"] and generation_points(p1a, c1, g1[scan]) == scan_step["fragments"][scan],
        # Le nettoyage peut retirer de C0 la génération remplacée du scan (R26-IDX-02) ; les générations vivantes et le
        # reste de C0 restent intacts.
        "p1_scan_c0_keeps_live_generations": all(generation_points(p1a, c0, g0[d]) == generation_points(p0, c0, g0[d]) for d in others)
        and generation_points(p1a, c0, g0[scan]) in {0, generation_points(p0, c0, g0[scan])}
        and p1a["points"].get(c0, {}).get("total") == p0["points"][c0]["total"]
        - ((generation_points(p0, c0, g0[scan]) or 0) - (generation_points(p1a, c0, g0[scan]) or 0)),
        "p1_others_reindex_ready": all(item["state"] == "ready" and item["active"] for item in others_step["finals"].values()),
        "p1_others_no_native_worker": others_step["delta"]["native_worker_launches"] == 0,
        "p1_others_two_extraction_reuses": others_step["delta"]["extraction_reuses"] == 2,
        "p1_others_embeddings_recomputed": others_step["delta"]["embedding_texts_submitted"] == sum(others_step["fragments"][d] for d in others) > 0,
        "p1_index_consistent": p1b["index_consistency"].get("status") == "consistent",
        "p1_dense_serves_each_document": all(found(p1b, names[d]) is True for d in all_ids),
        "p0_return_reindex_ready": all(item["state"] == "ready" and item["active"] for item in back_step["finals"].values()),
        "p0_return_no_native_worker": back_step["delta"]["native_worker_launches"] == 0,
        "p0_return_three_extraction_reuses": back_step["delta"]["extraction_reuses"] == 3,
        "p0_return_no_embedding_computed": back_step["delta"]["embedding_texts_submitted"] == 0,
        "p0_return_cache_hits_cover_fragments": back_step["delta"]["embedding_cache_hits"] == sum(back_step["fragments"].values()) > 0,
        "p0_return_index_consistent": p0b["index_consistency"].get("status") == "consistent",
        "p0_return_dense_serves_each_document": all(found(p0b, names[d]) is True for d in all_ids),
        "cleanup_settled": all(steps[label]["pending_cleanup"] == 0 for label in ("settle_p1_scan", "settle_p1_others", "settle_p0_return")),
        "p0_return_no_request_reaches_c1_except_cleanup": only_cleanup(report["lives"][2]["qdrant_requests"]["c1"]),
        "no_generation_request": all(not life["ollama_generation_requests"] for life in report["lives"]),
        "sources_unchanged_during_run": len({life["sources"]["sha256"] for life in report["lives"]}) == 1,
        "cooperative_stops": all(life.get("stop_status") == "stopped" for life in report["lives"]),
    }
    revisions = {d: {p0["sqlite"]["generations"][g0[d]]["extraction_revision_id"], p0b["sqlite"]["generations"][g1[d]]["extraction_revision_id"],
                     p0b["sqlite"]["generations"][g2[d]]["extraction_revision_id"]} for d in all_ids}
    p1_log = report["lives"][1]["qdrant_requests"]
    mechanism = {
        "ocr_not_redone": sum(step["delta"]["native_worker_launches"] for step in (scan_step, others_step, back_step)) == 0
        and [step["delta"]["extraction_reuses"] for step in (scan_step, others_step, back_step)] == [1, 2, 3]
        and all(len(values) == 1 for values in revisions.values()),
        "collections_distinct": c0 != c1 and f0 != f1 and {c0, c1} <= set(p1b["collections"]) and {c0, c1} <= set(p0b["collections"]),
        "no_p1_request_reaches_c0_except_cleanup": only_cleanup(p1_log["c0"]) and p1_log["c1"]["other"] > 0,
    }
    scan_g0 = g0[scan]
    hypotheses = {
        "H-A1": {"statement": "Readiness 200 « present » alors que deux documents publiés n'ont aucun point dans la collection courante "
                              "et que la recherche dense ne les retrouve plus, sans avertissement (contredit IMPLEMENTATION.md l. 108)",
                 "observations": (h1 := {
                     "readiness_200_present": p1a["readiness"]["http_status"] == 200 and p1a["readiness"]["qdrant_collection"] == "present",
                     "index_consistency_shows_zero_points_for_the_two_others":
                         p1a["index_consistency"].get("status") == "inconsistent"
                         and sorted((m["document_id"], m["qdrant_points"]) for m in p1a["index_consistency"].get("mismatches", []))
                         == sorted((d, 0) for d in others),
                     "dense_search_no_longer_finds_the_two_others": None if any(found(p1a, names[d]) is None for d in others)
                     else all(found(p1a, names[d]) is False for d in others),
                     "no_warning_about_the_two_others": not warned(p1a, [names[d] for d in others], others)})},
        "H-A2": {"statement": "Les points de la génération remplacée restent dans C0 ; le nettoyage, qui ne vise que la collection courante, "
                              "se déclare terminé",
                 "observations": (h2 := {
                     "cleanup_marked_complete": p1a["sqlite"]["vector_cleanup"].get(scan_g0, {}).get("state") == "complete",
                     "replaced_points_still_in_c0": (generation_points(p1a, c0, scan_g0) or 0) > 0
                     and generation_points(p1a, c0, scan_g0) == generation_points(p0, c0, scan_g0)})},
        "H-A3": {"statement": "Au retour sous P0, la branche dense ne sert plus aucun document jusqu'à la réindexation",
                 "observations": (h3 := {
                     "index_consistency_shows_zero_points_for_all": p0r["index_consistency"].get("status") == "inconsistent"
                     and sorted((m["document_id"], m["qdrant_points"]) for m in p0r["index_consistency"].get("mismatches", []))
                     == sorted((d, 0) for d in all_ids),
                     "dense_search_finds_no_document": None if any(found(p0r, names[d]) is None for d in all_ids)
                     else all(found(p0r, names[d]) is False for d in all_ids),
                     "restored_after_reindex": all(found(p0b, names[d]) is True for d in all_ids)})},
    }
    for name, observations in (("H-A1", h1), ("H-A2", h2), ("H-A3", h3)):
        hypotheses[name]["status"] = verdict(observations)
    orphans: dict[str, dict[str, int | None]] = {
        "c0_replaced_generations": {names[d]: generation_points(p0b, c0, g0[d]) for d in all_ids},
        "c1_replaced_generations": {names[d]: generation_points(p0b, c1, g1[d]) for d in all_ids}}
    hypotheses["H-A2"]["orphans_at_end"] = orphans
    hypotheses["H-A3"]["readiness_before_reindex"] = p0r["readiness"]
    fix_checks = {
        "absent_collection_lists_every_document": sorted(p1s["readiness"].get("documents_to_reindex") or []) == sorted(all_ids),
        "partial_state_readiness_named": p1a["readiness"]["http_status"] == 200 and p1a["readiness"].get("dense_index") == "dense_migration_incomplete"
        and sorted(p1a["readiness"].get("documents_to_reindex") or []) == sorted(others),
        "partial_state_search_warns": mismatched(p1a, "library") == sorted(others) and mismatched(p1a, names[scan]) == []
        and all(mismatched(p1a, names[d]) == [d] for d in others),
        "return_state_readiness_named": p0r["readiness"]["http_status"] == 200 and p0r["readiness"].get("dense_index") == "dense_migration_incomplete"
        and sorted(p0r["readiness"].get("documents_to_reindex") or []) == sorted(all_ids),
        "return_state_search_warns": mismatched(p0r, "library") == sorted(all_ids),
        "complete_states_quiet": all(phase["readiness"].get("dense_index") == "complete" and phase["readiness"].get("documents_to_reindex") == []
                                     and all(mismatched(phase, key) == [] for key in phase["search"]) for phase in (p0, p1b, p0b)),
        "replaced_generations_removed_everywhere": generation_points(p1a, c0, g0[scan]) == 0
        and all(value == 0 for side in orphans.values() for value in side.values()),
    }
    passed = all(mechanism.values()) and all(expectations.values())
    return {"mechanism_checks": mechanism, "expectations": expectations, "hypotheses": hypotheses,
            "r26_idx_02": {"checks": fix_checks, "status": "PASS" if all(fix_checks.values()) else "FAIL"},
            "result": "PASS_MECHANISM" if passed else "FAIL"}


class Journal:
    """Journal JSONL créé exclusivement ; chaque phase y est écrite et forcée sur disque dès qu'elle est observée."""

    def __init__(self, path: Path):
        self.path = path
        path.open("x", encoding="utf-8").close()

    def write(self, kind: str, label: str, value: Any) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"utc": datetime.now(UTC).isoformat(), "kind": kind, "label": label, "value": value},
                                    ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def run_probe(profiles: dict[str, Path], fixtures: dict[str, Path], question: str, *, start: Callable[[Path], dict],
              stop: Callable[[Path], dict], connect: Callable[[Path, dict], Any], journal: Journal,
              sampler: HostSampler | None = None, job_timeout: float = 1200) -> dict:
    """Déroule les sept étapes ; toute exception est conservée dans le rapport et l'instance en cours est arrêtée."""
    report: dict[str, Any] = {"phases": {}, "steps": {}, "lives": [], "documents": {}}
    current: dict[str, Any] = {}

    def begin(name: str, profile: Path) -> Any:
        state = start(profile)
        life = {"profile": name, "instance_id": state.get("instance_id"), "status": state.get("status"), "sources": source_fingerprint(),
                "logs": {service: identity.get("log_path") for service, identity in state.get("services", {}).items()}}
        report["lives"].append(life)
        if sampler:
            sampler.pids = {identity["pid"] for identity in state.get("services", {}).values() if identity.get("pid")}
        current.update(profile=profile, instance=connect(profile, state), life=life)
        journal.write("start", name, life)
        return current["instance"]

    def end(c0: str | None = None, c1: str | None = None) -> None:
        instance, life = current["instance"], current["life"]
        result = stop(current["profile"])
        life["stop_status"] = result.get("status")
        qdrant, ollama = instance.log_text("qdrant"), instance.log_text("ollama")
        life["qdrant_requests"] = {"c0": qdrant_requests(qdrant, c0) if c0 else None, "c1": qdrant_requests(qdrant, c1) if c1 else None}
        requests = ollama_requests(ollama)
        life["ollama_requests"] = requests
        life["ollama_generation_requests"] = {path: count for path, count in requests.items() if path in {"/api/chat", "/api/generate"}}
        life["log_sha256"] = {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in (("qdrant", qdrant), ("ollama", ollama))}
        instance.close()
        current.clear()
        journal.write("stop", life["profile"], life)

    def phase(instance: Any, label: str) -> dict:
        report["phases"][label] = observe(instance, label, question, report["documents"])
        journal.write("phase", label, report["phases"][label])
        return report["phases"][label]

    def step(label: str, value: dict) -> dict:
        report["steps"][label] = value
        journal.write("step", label, value)
        return value

    stage = "p0_import"
    try:
        instance = begin("p0", profiles["p0"])
        imports = {}
        for key, path in fixtures.items():
            item = instance.import_file(path, f"{LIBRARY_FOLDER}/{path.name}")
            imports[key] = {"document_id": item["document_id"], "version_id": item["version_id"], "job_id": item["job_id"]}
        for item in imports.values():
            item["final"] = instance.wait(item["job_id"], job_timeout)
        report["documents"] = {key: item["document_id"] for key, item in imports.items()}
        step("import_p0", {"imports": imports})
        p0 = phase(instance, "p0_published")
        p0["lexical"] = instance.lexical(question)
        journal.write("lexical", "p0_published", p0["lexical"])
        c0 = p0["collection"]
        end(c0)
        stage = "p1_start"
        instance = begin("p1", profiles["p1"])
        c1 = phase(instance, "p1_started")["collection"]
        stage = "p1_reindex_scan"
        step("reindex_scan_p1", reindex(instance, [report["documents"]["scan"]], job_timeout))
        step("settle_p1_scan", settle(instance))
        phase(instance, "p1_scan_reindexed")
        stage = "p1_reindex_others"
        step("reindex_others_p1", reindex(instance, [report["documents"][key] for key in ("native", "unicode")], job_timeout))
        step("settle_p1_others", settle(instance))
        phase(instance, "p1_all_reindexed")
        end(c0, c1)
        stage = "p0_return"
        instance = begin("p0_return", profiles["p0"])
        phase(instance, "p0_returned")
        step("reindex_all_p0", reindex(instance, list(report["documents"].values()), job_timeout))
        step("settle_p0_return", settle(instance))
        phase(instance, "p0_reindexed")
        end(c0, c1)
    except Exception as error:  # noqa: BLE001 - l'échec est une observation conservée, l'instance est arrêtée
        report["error"] = {"stage": stage, "type": type(error).__name__, "message": str(error)}
        journal.write("error", stage, report["error"])
        if current:
            try:
                end()
            except Exception as stop_error:  # noqa: BLE001
                report["error"]["stop"] = f"{type(stop_error).__name__}: {stop_error}"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="racine neuve de l'essai (créée en mode 700)")
    parser.add_argument("--ports", required=True, help="ports API,Qdrant,Ollama libres et distincts de l'instance principale")
    parser.add_argument("--question", default=DEFAULT_QUESTION, help="recherche sans mot commun avec les documents")
    parser.add_argument("--job-timeout", type=float, default=1200)
    parser.add_argument("--min-available-mib", type=float, default=8192, help="mémoire disponible exigée avant le démarrage")
    args = parser.parse_args()
    from services.runtime.profile_setup import port_free
    from services.runtime.supervisor import start, stop

    main_profile = yaml.safe_load(DELIVERED.read_text(encoding="utf-8"))
    ports = dict(zip(("app", "qdrant", "ollama"), map(int, args.ports.split(",")), strict=True))
    root = check_isolation(args.root, ports, main_profile, port_free)
    available = psutil.virtual_memory().available / 1048576
    if available < args.min_available_mib:
        raise SystemExit(f"Mémoire disponible insuffisante : {available:.0f} Mio pour {args.min_available_mib:.0f} exigés")
    manifest = {entry["path"]: entry["sha256"] for entry in json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]}
    root.mkdir(mode=0o700, parents=False, exist_ok=True)
    os.chmod(root, 0o700)
    profiles = write_profiles(root, ports)
    report: dict[str, Any] = {
        "scope": "Sonde de mécanisme d'identité d'embedding par substitution déclarée (embedding.model_id suffixé, poids identiques) ; "
                 "pas une migration d'embedding : D03.8 reste NOT_RUN, aucun comparatif D10.2 ni génération.",
        "d03_8": "NOT_RUN", "started_utc": datetime.now(UTC).isoformat(), "root": str(root), "ports": ports,
        "tool": {"path": "tools/qualification/embedding_identity_check.py", "sha256": sha256(Path(__file__))}, "git": git_state(),
        "question": args.question,
        "profiles": {"base": {"path": "config/local16.yaml", "sha256": sha256(DELIVERED)},
                     **{name: {"path": str(path), "sha256": sha256(path)} for name, path in profiles.items()},
                     "differences": profile_differences(yaml.safe_load(profiles["p0"].read_text(encoding="utf-8")),
                                                        yaml.safe_load(profiles["p1"].read_text(encoding="utf-8")))},
        "fixtures": {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
                           "manifest_sha256": manifest.get(path.relative_to(FIXTURES.parent).as_posix())}
                     for key, path in DEFAULT_FIXTURES.items()},
        "host_before": {"available_mib": round(available, 1), "disk_free_mib": round(shutil.disk_usage(root).free / 1048576, 1)}}
    sampler = HostSampler(root)
    sampler.start()
    started = time.monotonic()
    try:
        report.update(run_probe(profiles, DEFAULT_FIXTURES, args.question, start=start, stop=stop, connect=Instance,
                                journal=Journal(root / "embedding-identity-journal.jsonl"), sampler=sampler, job_timeout=args.job_timeout))
    finally:
        sampler.halt.set()
        sampler.join(10)
    report["duration_seconds"] = round(time.monotonic() - started, 1)
    report["host"] = sampler.summary()
    report["root_bytes"] = sum(path.stat().st_size for path in root.rglob("*") if path.is_file() and not path.is_symlink())
    report.update(evaluate(report))
    report["finished_utc"] = datetime.now(UTC).isoformat()
    output = root / "embedding-identity-report.json"
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "report": str(output), "report_sha256": sha256(output),
                      "mechanism_checks": report["mechanism_checks"],
                      "failed_expectations": sorted(key for key, value in report["expectations"].items() if not value),
                      "hypotheses": {name: item["status"] for name, item in report["hypotheses"].items()},
                      "r26_idx_02": report.get("r26_idx_02"), "error": report.get("error")}, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS_MECHANISM" else 1


if __name__ == "__main__":
    raise SystemExit(main())
