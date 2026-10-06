"""Sonde d'identité d'embedding (`tools/qualification/embedding_identity_check.py`), sans service réel.

Doubles nommés : `SimulatedHost`/`SimulatedInstance` reproduisent les règles du produit utiles à la sonde (collection et
cache par identité dense, réutilisation de l'extraction, nettoyage limité à la collection courante, readiness fondée sur
la seule existence de la collection) ; leurs variantes inversent une règle pour réfuter une hypothèse ou faire échouer
un contrôle, ou reproduisent le produit corrigé par R26-IDX-02 (nettoyage dans toutes les collections, état dense nommé
et avertissement `dense_identity_mismatch`). `RecordingLifecycle` remplace le superviseur. Ces doubles ne valent jamais une exécution native : seules
les fonctions pures, le filtre de routes, l'index plein texte SQLite (FTS5 réel) et le générateur de profil sont réels.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import embedding_identity_check as probe  # noqa: E402

DELIVERED = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
FRAGMENTS = {"scan": 2, "native": 4, "unicode": 1}


def qdrant_line(method: str, path: str, agent: str = "python-httpx/0.28.1") -> str:
    return (f'2026-10-06T10:00:00.000000Z  INFO actix_web::middleware::logger: 127.0.0.1 "{method} {path} HTTP/1.1" '
            f'200 606 "-" "{agent}" 0.002113')


class SimulatedHost:
    """Double nommé du produit, persistant d'une vie d'instance à l'autre (base, stockage Qdrant, cache)."""

    def __init__(self, *, readiness_guard=False, cleanup_everywhere=False, query_previous=False, ocr_on_reindex=False,
                 warn_missing_points=False, signal_dense=False, cleanup_reads_previous=False, cleanup_removes_live=False):
        self.readiness_guard, self.cleanup_everywhere = readiness_guard, cleanup_everywhere
        self.query_previous, self.ocr_on_reindex, self.warn_missing_points = query_previous, ocr_on_reindex, warn_missing_points
        # R26-IDX-02 : état dense nommé et avertissement (produit corrigé) ; variantes fautives du nettoyage étendu.
        self.signal_dense, self.cleanup_reads_previous, self.cleanup_removes_live = signal_dense, cleanup_reads_previous, cleanup_removes_live
        self.documents: dict[str, dict] = {}
        self.generations: dict[str, dict] = {}
        self.collections: dict[str, dict[str, str]] = {}
        self.cache: set[tuple[str, str]] = set()
        self.cleanup: dict[str, dict] = {}
        self.sequence = 0

    def uid(self, prefix: str) -> str:
        self.sequence += 1
        return f"{prefix}{self.sequence}"


class SimulatedInstance:
    """Une vie d'instance sur `SimulatedHost` : identité dense lue dans le profil, compteurs propres au processus."""

    def __init__(self, host: SimulatedHost, profile_path: Path, state: dict):
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        self.host, self.model_id = host, profile["embedding"]["model_id"]
        self.fingerprint = hashlib.sha256(self.model_id.encode()).hexdigest()
        self.prefix = profile["qdrant"]["collection"] + "_"
        self.collection = self.prefix + self.fingerprint[:16]
        self.indexing = dict.fromkeys(("requests", "cache_hits", "cache_misses", "embedding_requests", "embedding_texts_submitted"), 0)
        self.ingestion: dict = {"native_worker_launches": 0, "extraction_reuses": 0, "last_extraction": None}
        self.jobs: dict[str, dict] = {}
        self.qdrant_log: list[str] = []
        self.ollama_log = ['[GIN] 2026/10/06 - 10:00:00 | 200 |      28.961µs |       127.0.0.1 | GET      "/api/version"']
        self.closed = False

    # Mécanique du produit simulée
    def touch(self, method: str, collection: str, tail: str, agent: str = "python-httpx/0.28.1") -> None:
        self.qdrant_log.append(qdrant_line(method, f"/collections/{collection}{tail}", agent))

    def embed_and_upsert(self, key: str, generation: str) -> None:
        texts = [f"{key}-{index}" for index in range(FRAGMENTS[key])]
        missing = [text for text in texts if (self.fingerprint, text) not in self.host.cache]
        self.indexing["requests"] += 1
        self.indexing["cache_hits"] += len(texts) - len(missing)
        self.indexing["cache_misses"] += len(missing)
        if missing:
            self.indexing["embedding_requests"] += 1
            self.indexing["embedding_texts_submitted"] += len(missing)
            self.host.cache.update((self.fingerprint, text) for text in missing)
        self.touch("PUT", self.collection, "/points?wait=true")
        points = self.host.collections.setdefault(self.collection, {})
        points.update({f"{generation}-{index}": generation for index in range(len(texts))})

    def publish(self, document_id: str, key: str, revision: str) -> str:
        generation = self.host.uid("g")
        self.embed_and_upsert(key, generation)
        self.host.generations[generation] = {"document_id": document_id, "fingerprint": self.fingerprint, "state": "ready", "published": True,
                                             "extraction_revision_id": revision, "coverage": {"ocr": int(key == "scan")},
                                             "chunks": FRAGMENTS[key]}
        previous = self.host.documents[document_id]["active"]
        self.host.documents[document_id]["active"] = generation
        if previous:
            self.host.cleanup[previous] = {"state": "pending", "reason": "superseded", "error_code": None}
        return generation

    def reconcile(self) -> None:
        for generation, record in self.host.cleanup.items():
            if record["state"] == "pending":
                targets = list(self.host.collections) if self.host.cleanup_everywhere else [self.collection]
                for collection in targets:
                    if self.host.cleanup_reads_previous and collection != self.collection:
                        self.touch("POST", collection, "/points/scroll")
                    self.touch("POST", collection, "/points/delete?wait=true")
                    points = self.host.collections.get(collection, {})
                    live = {self.host.documents[d]["active"] for d in self.host.documents} if self.host.cleanup_removes_live else set()
                    for point in [point for point, owner in points.items() if owner == generation or (collection != self.collection and owner in live)]:
                        del points[point]
                record["state"] = "complete"

    def active_points(self, document_id: str) -> int:
        generation = self.host.documents[document_id]["active"]
        return sum(owner == generation for owner in self.host.collections.get(self.collection, {}).values())

    def missing(self) -> list[str]:
        present = self.collection in self.host.collections
        return sorted(d for d in self.host.documents if not present or not self.active_points(d))

    # Interface utilisée par la sonde
    def readiness(self) -> dict:
        result = self.base_readiness()
        if self.host.signal_dense:
            result.update(dense_index="dense_migration_incomplete" if self.missing() else "complete", documents_to_reindex=self.missing())
        return result

    def base_readiness(self) -> dict:
        if self.collection in self.host.collections:
            consistent = all(self.active_points(d) == self.host.generations[self.host.documents[d]["active"]]["chunks"] for d in self.host.documents)
            if self.host.readiness_guard and not consistent:
                return {"http_status": 503, "status": "blocked", "qdrant_collection": "inconsistent", "blockers": ["index_not_ready"]}
            return {"http_status": 200, "status": "ready", "qdrant_collection": "present", "blockers": []}
        published = any(item["published"] for item in self.host.generations.values())
        return {"http_status": 503 if published else 200, "status": "blocked" if published else "ready",
                "qdrant_collection": "absent_with_published_generations" if published else "absent_empty_library", "blockers": []}

    def diagnostics(self) -> dict:
        self.reconcile()
        rows = [(d, self.host.documents[d]["active"]) for d in self.host.documents]
        if self.collection in self.host.collections:
            mismatches = [{"generation_id": g, "document_id": d, "sqlite_chunks": self.host.generations[g]["chunks"], "qdrant_points": self.active_points(d)}
                          for d, g in rows if self.active_points(d) != self.host.generations[g]["chunks"]]
            consistency = {"status": "inconsistent" if mismatches else "consistent", "active_generations": len(rows), "mismatches": mismatches}
        else:
            consistency = {"status": "unverifiable", "code": "qdrant_unavailable", "active_generations": len(rows)}
        return {"dense_identity": {"graph_sha256": "graphe", "tokenizer_sha256": "tokenizer", "model_id": self.model_id, "revision": "r",
                                   "fingerprint": self.fingerprint},
                "qdrant_collection": self.collection, "indexing_cache": dict(self.indexing), "ingestion_cache": dict(self.ingestion),
                "index_consistency": consistency,
                "reconciliation": {"pending_cleanup": sum(item["state"] == "pending" for item in self.host.cleanup.values())}}

    def import_file(self, path: Path, relative: str) -> dict:
        key = {fixture.name: name for name, fixture in probe.DEFAULT_FIXTURES.items()}[path.name]
        document_id, version_id, job_id = self.host.uid("d"), self.host.uid("v"), self.host.uid("j")
        self.host.documents[document_id] = {"key": key, "active": None, "relative_path": relative, "revision": self.host.uid("r")}
        self.ingestion["native_worker_launches"] += 1
        self.publish(document_id, key, self.host.documents[document_id]["revision"])
        self.jobs[job_id] = {"state": "ready", "active": True, "error_code": None}
        return {"document_id": document_id, "version_id": version_id, "job_id": job_id}

    def reindex(self, document_id: str) -> str:
        document, job_id = self.host.documents[document_id], self.host.uid("j")
        self.ingestion["native_worker_launches" if self.host.ocr_on_reindex else "extraction_reuses"] += 1
        self.publish(document_id, document["key"], document["revision"])
        self.jobs[job_id] = {"state": "ready", "active": True, "error_code": None}
        return job_id

    def wait(self, job_id: str, timeout: float) -> dict:
        return dict(self.jobs[job_id])

    def search(self, question: str, scope: dict) -> dict:
        if self.collection not in self.host.collections:
            return {"http_status": 503, "code": "qdrant_unavailable"}
        self.touch("POST", self.collection, "/points/query")
        if self.host.query_previous:
            for collection in self.host.collections:
                if collection != self.collection:
                    self.touch("POST", collection, "/points/query")
        documents = scope.get("documentIds") or list(self.host.documents)
        found = [d for d in documents if self.active_points(d)]
        # Provenance OCR d'un passage du scan : avertissement propre à ce document, sans rapport avec l'index dense.
        warnings = [{"code": "ocr_evidence", "document_id": d} for d in found if self.host.documents[d]["key"] == "scan"]
        if self.host.warn_missing_points:
            warnings += [{"code": "dense_points_missing", "document_id": d} for d in documents if not self.active_points(d)]
        missing = [d for d in documents if d in self.missing()]
        if self.host.signal_dense and missing:
            warnings.append({"code": "dense_identity_mismatch", "document_id": None, "document_ids": missing})
        return {"http_status": 200, "top10_documents": found, "results_documents": found, "warnings": warnings}

    def collections(self) -> list[str]:
        return sorted(name for name in self.host.collections if name.startswith(self.prefix))

    def count(self, collection: str, generation_id: str | None = None) -> int | None:
        self.touch("POST", collection, "/points/count", probe.PROBE_AGENT)
        if collection not in self.host.collections:
            return None
        points = self.host.collections[collection].values()
        return sum(owner == generation_id for owner in points) if generation_id else len(points)

    def sqlite_state(self) -> dict:
        return {"documents": {d: {"relative_path": item["relative_path"], "active_generation_id": item["active"], "state": "ready"}
                              for d, item in self.host.documents.items()},
                "generations": {g: dict(item) for g, item in self.host.generations.items()},
                "vector_cleanup": {g: dict(item) for g, item in self.host.cleanup.items()},
                "embedding_cache": {}}

    def lexical(self, question: str) -> dict:
        return {"identifiers": [], "match_expression": '"Which"', "fts_hits_all_fragments": 0}

    def log_text(self, name: str) -> str:
        return "\n".join(self.qdrant_log if name == "qdrant" else self.ollama_log) + "\n"

    def close(self) -> None:
        self.closed = True


class RecordingLifecycle:
    """Double nommé du superviseur : enregistre démarrages et arrêts, aucun processus lancé."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def start(self, profile: Path) -> dict:
        self.calls.append(("start", profile.name))
        return {"status": "running", "instance_id": f"vie-{len(self.calls)}", "services": {"qdrant": {"log_path": "qdrant.log"}}}

    def stop(self, profile: Path) -> dict:
        self.calls.append(("stop", profile.name))
        return {"status": "stopped"}


def profiles(folder: Path) -> dict[str, Path]:
    paths = {"p0": folder / "profile.yaml", "p1": folder / "profile-p1.yaml"}
    paths["p0"].write_text(yaml.safe_dump(DELIVERED, allow_unicode=True), encoding="utf-8")
    paths["p1"].write_text(yaml.safe_dump(probe.probe_profile(DELIVERED), allow_unicode=True), encoding="utf-8")
    return paths


def simulate(tmp_path: Path, host: SimulatedHost) -> tuple[dict, RecordingLifecycle]:
    paths, lifecycle = profiles(tmp_path), RecordingLifecycle()
    report = probe.run_probe(paths, probe.DEFAULT_FIXTURES, probe.DEFAULT_QUESTION, start=lifecycle.start, stop=lifecycle.stop,
                             connect=lambda profile, state: SimulatedInstance(host, profile, state),
                             journal=probe.Journal(tmp_path / "journal.jsonl"))
    report["fixtures"] = {key: {"sha256": "même", "manifest_sha256": "même"} for key in probe.DEFAULT_FIXTURES}
    report["profiles"] = {"differences": probe.profile_differences(DELIVERED, probe.probe_profile(DELIVERED))}
    report.update(probe.evaluate(report))
    return report, lifecycle


def test_the_isolation_check_accepts_only_a_new_root_and_free_ports_distinct_from_the_main_instance(tmp_path):
    ports = {"app": 18885, "qdrant": 16433, "ollama": 21534}
    assert probe.check_isolation(tmp_path / "neuve", ports, DELIVERED, lambda port: True) == (tmp_path / "neuve").resolve()
    (tmp_path / "vide").mkdir()
    assert probe.check_isolation(tmp_path / "vide", ports, DELIVERED, lambda port: True) == (tmp_path / "vide").resolve()
    occupied = tmp_path / "occupée"
    occupied.mkdir()
    (occupied / "profile.yaml").write_text("x", encoding="utf-8")
    refusals = [
        (occupied, ports, lambda port: True, "n'est pas un dossier vide"),
        (ROOT / DELIVERED["app"]["data_dir"], ports, lambda port: True, "données de l'instance principale"),
        ((ROOT / DELIVERED["app"]["data_dir"]).resolve() / "qa", ports, lambda port: True, "données de l'instance principale"),
        (tmp_path / "neuve", {**ports, "app": 8785}, lambda port: True, r"Ports de l'instance principale refusés : \[8785\]"),
        (tmp_path / "neuve", {**ports, "ollama": 11434}, lambda port: True, r"\[11434\]"),
        (tmp_path / "neuve", {**ports, "qdrant": 18885}, lambda port: True, "Trois ports distincts"),
        (tmp_path / "neuve", ports, lambda port: port != 16433, "Ports occupés : qdrant 16433"),
    ]
    for root, chosen, free, message in refusals:
        with pytest.raises(ValueError, match=message):
            probe.check_isolation(root, chosen, DELIVERED, free)


def test_the_probe_profile_changes_only_the_model_id_and_refuses_a_second_suffix():
    probed = probe.probe_profile(DELIVERED)
    assert probed["embedding"]["model_id"] == "intfloat/multilingual-e5-small#qa-identity-probe"
    assert DELIVERED["embedding"]["model_id"] == "intfloat/multilingual-e5-small"
    assert probe.profile_differences(DELIVERED, probed) == ["embedding.model_id"]
    with pytest.raises(ValueError, match="déjà l'identité de sonde"):
        probe.probe_profile(probed)


def test_profile_differences_report_nested_added_and_removed_keys():
    assert probe.profile_differences({"a": {"b": 1, "c": 2}, "d": 3}, {"a": {"b": 1, "c": 4}, "e": 5}) == ["a.c", "d", "e"]
    assert probe.profile_differences({"a": [1, 2]}, {"a": [1, 2]}) == []


def test_the_profiles_come_from_the_init_profile_generator_and_are_never_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr("services.runtime.profile_setup.port_free", lambda port: True)
    root = tmp_path / "racine"
    root.mkdir()
    paths = probe.write_profiles(root, {"app": 18885, "qdrant": 16433, "ollama": 21534})
    p0 = yaml.safe_load(paths["p0"].read_text(encoding="utf-8"))
    p1 = yaml.safe_load(paths["p1"].read_text(encoding="utf-8"))
    assert (p0["app"]["port"], p0["qdrant"]["url"], p0["llm"]["base_url"]) == (18885, "http://127.0.0.1:16433", "http://127.0.0.1:21534")
    assert Path(p0["app"]["data_dir"]) == root.resolve() / "data" and Path(p0["qdrant"]["storage_dir"]) == root.resolve() / "q"
    assert p0["llm"]["model"] == DELIVERED["llm"]["model"] and p0["embedding"] == DELIVERED["embedding"]
    assert probe.profile_differences(p0, p1) == ["embedding.model_id"]
    with pytest.raises(ValueError, match="jamais remplacé"):
        probe.write_profiles(root, {"app": 18885, "qdrant": 16433, "ollama": 21534})


def test_qdrant_log_counts_split_probe_reads_from_other_clients_and_match_whole_collection_names():
    c0, c1 = "pdf_chunks_e5small_v1_aaaa", "pdf_chunks_e5small_v1_bbbb"
    text = "\n".join([
        qdrant_line("POST", f"/collections/{c0}/points/query"),
        qdrant_line("POST", f"/collections/{c0}/points/count", probe.PROBE_AGENT),
        qdrant_line("GET", f"/collections/{c0}"),
        qdrant_line("PUT", f"/collections/{c0}/points?wait=true"),
        qdrant_line("POST", f"/collections/{c0}x/points/query"),
        qdrant_line("POST", f"/collections/{c1}/points/query"),
        qdrant_line("GET", "/collections"),
        "2026-10-06T10:00:00Z  INFO qdrant: texte libre /collections/" + c0,
    ])
    assert probe.qdrant_requests(text, c0) == {"total": 4, "probe": 1, "other": 3,
                                               "other_routes": {"POST /points/query": 1, "GET /": 1, "PUT /points": 1}}
    assert probe.qdrant_requests(text, c1) == {"total": 1, "probe": 0, "other": 1, "other_routes": {"POST /points/query": 1}}


def test_ollama_log_counts_each_route():
    text = ('[GIN] 2026/10/06 - 10:00:00 | 200 |  194.914µs |       127.0.0.1 | GET      "/api/version"\n'
            '[GIN] 2026/10/06 - 10:00:01 | 200 |   39.52µs |       127.0.0.1 | GET      "/api/tags"\n'
            '[GIN] 2026/10/06 - 10:00:02 | 200 |   1.2s |       127.0.0.1 | POST     "/api/chat"\n'
            'time=2026 level=INFO msg="POST \\"/api/chat\\" cité dans un message"\n')
    assert probe.ollama_requests(text) == {"/api/version": 1, "/api/tags": 1, "/api/chat": 1}


def test_question_routes_are_refused_before_leaving_the_client():
    seen: list[str] = []
    transport = httpx.MockTransport(lambda request: seen.append(request.url.path) or httpx.Response(200, json={}))
    with httpx.Client(base_url="http://127.0.0.1:18885", transport=transport, event_hooks={"request": [probe.refuse_generation]}) as client:
        assert client.post("/api/v1/search", json={}).status_code == 200
        for path in ("/api/v1/queries", "/api/v1/queries/q1/events", "/api/v1/admin/evaluation/context"):
            with pytest.raises(RuntimeError, match="route de question refusée"):
                client.post(path, json={})
    assert seen == ["/api/v1/search"]


def test_the_lexical_precondition_uses_the_served_fts_expression_on_real_sqlite(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "app.sqlite3") as connection:
        connection.executescript((ROOT / "services/api/migrations/001_initial.sql").read_text(encoding="utf-8"))
        rows = [("L'alimentation d'essai de DA-P01 est de 22 V.",), ("For test QS-FREN, maintain 3.8 bar with a tolerance of ± 0.2 bar.",),
                ("Cesure con- trole; preserve the source line break.",)]
        connection.execute("INSERT INTO folders VALUES('f',NULL,'r','r')")
        connection.execute("INSERT INTO documents(id,folder_id,name,relative_path,created_at,updated_at) VALUES('d','f','n','p','t','t')")
        connection.execute("INSERT INTO document_versions(id,document_id,sha256,blob_path,created_at) VALUES('v','d','s','b','t')")
        connection.execute("INSERT INTO extraction_revisions VALUES('r','v','f','h',NULL,'t')")
        connection.execute("INSERT INTO index_generations(id,version_id,fingerprint,created_at) VALUES('g','v','f','t')")
        for index, (text,) in enumerate(rows):
            connection.execute("INSERT INTO chunks(chunk_uuid,generation_id,version_id,text,e5_tokens,text_hash,extraction_revision_id) "
                               "VALUES(?,?,?,?,?,?,?)", (f"c{index}", "g", "v", text, 10, "h", "r"))
    instance = object.__new__(probe.Instance)
    instance.data = data
    assert instance.lexical(probe.DEFAULT_QUESTION)["fts_hits_all_fragments"] == 0
    assert instance.lexical(probe.DEFAULT_QUESTION)["identifiers"] == []
    # Témoin positif : un mot du scan bilingue et un identifiant du natif sont bien trouvés par la même expression.
    assert instance.lexical("Which tolerance applies?")["fts_hits_all_fragments"] == 1
    assert instance.lexical("Voltage of DA-P01?")["identifiers"] == ["DA-P01"]


def test_the_full_probe_on_the_simulated_product_confirms_the_three_hypotheses_and_passes(tmp_path):
    report, lifecycle = simulate(tmp_path, SimulatedHost())
    assert lifecycle.calls == [("start", "profile.yaml"), ("stop", "profile.yaml"), ("start", "profile-p1.yaml"), ("stop", "profile-p1.yaml"),
                               ("start", "profile.yaml"), ("stop", "profile.yaml")]
    assert "error" not in report and report["result"] == "PASS_MECHANISM"
    assert report["mechanism_checks"] == {"ocr_not_redone": True, "collections_distinct": True, "no_p1_request_reaches_c0_except_cleanup": True}
    # Produit d'avant R26-IDX-02 : ni état nommé, ni avertissement, ni nettoyage hors de la collection courante.
    assert report["r26_idx_02"]["status"] == "FAIL" and not any(report["r26_idx_02"]["checks"].values())
    assert [key for key, value in report["expectations"].items() if not value] == []
    assert {name: item["status"] for name, item in report["hypotheses"].items()} == {"H-A1": "CONFIRMED", "H-A2": "CONFIRMED", "H-A3": "CONFIRMED"}
    # Points des générations remplacées laissés dans chaque collection après le retour sous P0.
    assert report["hypotheses"]["H-A2"]["orphans_at_end"] == {"c0_replaced_generations": FRAGMENTS, "c1_replaced_generations": FRAGMENTS}
    assert report["steps"]["reindex_scan_p1"]["delta"]["embedding_texts_submitted"] == FRAGMENTS["scan"]
    assert report["steps"]["reindex_all_p0"]["delta"]["embedding_texts_submitted"] == 0
    p1 = report["lives"][1]["qdrant_requests"]
    assert p1["c0"]["other"] == 0 and p1["c0"]["probe"] > 0 and p1["c1"]["other"] > 0
    kinds = [json.loads(line)["kind"] for line in (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds.count("phase") == 6 and kinds.count("start") == kinds.count("stop") == 3 and "error" not in kinds


def test_a_readiness_that_checks_the_index_refutes_h_a1_without_changing_the_mechanism_verdict(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(readiness_guard=True))
    assert report["hypotheses"]["H-A1"]["status"] == "REFUTED"
    assert report["hypotheses"]["H-A1"]["observations"]["readiness_200_present"] is False
    assert report["result"] == "PASS_MECHANISM"


def test_a_warning_about_the_documents_missing_from_the_collection_refutes_h_a1(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(warn_missing_points=True))
    assert report["hypotheses"]["H-A1"]["status"] == "REFUTED"
    assert report["hypotheses"]["H-A1"]["observations"]["no_warning_about_the_two_others"] is False


def test_a_cleanup_that_reaches_every_collection_refutes_h_a2_and_keeps_the_mechanism(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(cleanup_everywhere=True))
    assert report["hypotheses"]["H-A2"]["status"] == "REFUTED"
    assert report["hypotheses"]["H-A2"]["observations"] == {"cleanup_marked_complete": True, "replaced_points_still_in_c0": False}
    assert report["hypotheses"]["H-A2"]["orphans_at_end"] == {"c0_replaced_generations": dict.fromkeys(FRAGMENTS, 0),
                                                              "c1_replaced_generations": dict.fromkeys(FRAGMENTS, 0)}
    # Seule la suppression des générations remplacées atteint l'autre collection : garde et attendus restent tenus.
    p1 = report["lives"][1]["qdrant_requests"]["c0"]
    assert p1["other"] > 0 and p1["other_routes"] == {"POST /points/delete": p1["other"]}
    assert report["expectations"]["p1_scan_c0_keeps_live_generations"] is True and report["result"] == "PASS_MECHANISM"
    assert report["r26_idx_02"]["checks"]["replaced_generations_removed_everywhere"] is True


def test_the_corrected_product_signals_the_degraded_state_and_passes_r26_idx_02(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(cleanup_everywhere=True, signal_dense=True))
    assert report["result"] == "PASS_MECHANISM" and report["r26_idx_02"]["status"] == "PASS"
    assert all(report["r26_idx_02"]["checks"].values())
    assert {name: item["status"] for name, item in report["hypotheses"].items()} == {"H-A1": "REFUTED", "H-A2": "REFUTED", "H-A3": "CONFIRMED"}
    assert report["hypotheses"]["H-A1"]["observations"]["no_warning_about_the_two_others"] is False
    partial = report["phases"]["p1_scan_reindexed"]["readiness"]
    others = sorted(report["documents"][key] for key in ("native", "unicode"))
    assert partial["dense_index"] == "dense_migration_incomplete" and partial["documents_to_reindex"] == others


def test_a_cleanup_that_reads_the_previous_collection_fails_the_guard(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(cleanup_everywhere=True, cleanup_reads_previous=True))
    assert report["lives"][1]["qdrant_requests"]["c0"]["other_routes"]["POST /points/scroll"] > 0
    assert report["mechanism_checks"]["no_p1_request_reaches_c0_except_cleanup"] is False and report["result"] == "FAIL"


def test_a_cleanup_that_removes_live_generations_from_the_previous_collection_fails_the_expectation(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(cleanup_everywhere=True, cleanup_removes_live=True))
    assert report["expectations"]["p1_scan_c0_keeps_live_generations"] is False and report["result"] == "FAIL"


def test_a_query_sent_to_the_previous_collection_fails_the_mechanism(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(query_previous=True))
    assert report["mechanism_checks"]["no_p1_request_reaches_c0_except_cleanup"] is False and report["result"] == "FAIL"
    # Même avec un nettoyage étendu admis, une recherche dans l'ancienne collection reste refusée.
    extended = tmp_path / "étendu"
    extended.mkdir()
    report, _ = simulate(extended, SimulatedHost(query_previous=True, cleanup_everywhere=True))
    assert report["mechanism_checks"]["no_p1_request_reaches_c0_except_cleanup"] is False and report["result"] == "FAIL"


def test_an_ocr_redone_on_reindex_fails_the_mechanism(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost(ocr_on_reindex=True))
    assert report["mechanism_checks"]["ocr_not_redone"] is False and report["result"] == "FAIL"
    assert report["expectations"]["p1_scan_no_native_worker"] is False


def test_a_new_extraction_revision_fails_the_ocr_check_even_without_a_counted_worker(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost())
    final = report["phases"]["p0_reindexed"]["sqlite"]
    scan = report["documents"]["scan"]
    final["generations"][final["documents"][scan]["active_generation_id"]]["extraction_revision_id"] = "révision-nouvelle"
    evaluation = probe.evaluate(report)
    assert evaluation["mechanism_checks"]["ocr_not_redone"] is False and evaluation["result"] == "FAIL"


def test_a_failed_search_leaves_h_a1_inconclusive(tmp_path):
    report, _ = simulate(tmp_path, SimulatedHost())
    report["phases"]["p1_scan_reindexed"]["search"]["native"] = {"http_status": 503, "code": "qdrant_unavailable"}
    assert probe.evaluate(report)["hypotheses"]["H-A1"]["status"] == "INCONCLUSIVE"


def test_an_interrupted_probe_keeps_its_error_stops_the_running_instance_and_is_an_error(tmp_path):
    class TimedOutInstance(SimulatedInstance):
        def wait(self, job_id, timeout):
            if self.model_id.endswith(probe.PROBE_SUFFIX):
                raise TimeoutError(f"Traitement {job_id} non terminé en {timeout:.0f} s")
            return super().wait(job_id, timeout)

    paths, lifecycle, host = profiles(tmp_path), RecordingLifecycle(), SimulatedHost()
    report = probe.run_probe(paths, probe.DEFAULT_FIXTURES, probe.DEFAULT_QUESTION, start=lifecycle.start, stop=lifecycle.stop,
                             connect=lambda profile, state: TimedOutInstance(host, profile, state), journal=probe.Journal(tmp_path / "j.jsonl"))
    assert report["error"]["stage"] == "p1_reindex_scan" and report["error"]["type"] == "TimeoutError"
    assert lifecycle.calls[-1] == ("stop", "profile-p1.yaml") and report["lives"][-1]["stop_status"] == "stopped"
    assert probe.evaluate(report)["result"] == "ERROR"
    with pytest.raises(FileExistsError):
        probe.Journal(tmp_path / "j.jsonl")
