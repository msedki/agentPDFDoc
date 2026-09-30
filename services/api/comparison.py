"""One development embedding arm against a frozen SQLite export.

Stop the API and unload Ollama first. Run E5 and Granite in separate processes
with the same export/annotations. The baseline collection is read-only;
--build-candidate explicitly permits the separate Granite diagnostic collection.
No PDF extraction, second API, final tuning or shared SQLite cache is involved.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psutil

from .context import ContextBuilder, LlmTokenizer
from .db import json_dump
from .embedding import EmbeddingService
from .embedding_comparison import ComparisonVectorStore, FrozenDatabase, GraniteEmbedding, file_sha
from .errors import ApiError
from .qualification import canonical_sha, evaluate_question, summary, verify_annotations
from .query import QueryService
from .retrieval import QdrantStore, SearchService
from .schemas import EvaluationContextRequest
from .scope import ScopeResolver
from .settings import Settings


class ResourceSamples:
    def __init__(self, reserve_mib, disk_path):
        self.reserve_mib = reserve_mib
        self.disk_path = Path(disk_path).resolve()
        self.samples = []
        self.stop = threading.Event()
        self.violation = threading.Event()
        self.error = None

    def sample(self):
        process = psutil.Process()
        memory = process.memory_info()
        private = getattr(memory, "private", None)
        row = {"monotonic_seconds": time.monotonic(), "host_available_mib": psutil.virtual_memory().available / 1048576,
               "rss_mib": memory.rss / 1048576, "private_mib": private / 1048576 if private is not None else None,
               "disk_free_mib": psutil.disk_usage(str(self.disk_path)).free / 1048576, "threads": process.num_threads()}
        self.samples.append(row)
        if row["host_available_mib"] < self.reserve_mib:
            self.violation.set()

    def ensure(self):
        if self.error:
            raise ApiError("comparison_sampler_failed", "Mesure de ressources indisponible ; essai arrêté.", 503)
        self.sample()
        if self.violation.is_set():
            raise ApiError("comparison_resource_reserve", "Réserve hôte menacée ; aucun nouvel appel d'inférence comparatif.", 503)

    @contextmanager
    def running(self):
        self.sample()
        def watch():
            while not self.stop.wait(.5):
                try:
                    self.sample()
                except Exception as error:
                    self.error = type(error).__name__
                    return
        thread = threading.Thread(target=watch, name="comparison-reserve-sampler", daemon=True)
        thread.start()
        try:
            self.ensure()
            yield self
        finally:
            self.stop.set()
            thread.join(timeout=2)
            self.sample()


class TimedEmbedding:
    """Measure the actual encoder, retaining no input text in timing telemetry."""
    def __init__(self, embedding):
        self.embedding, self.calls = embedding, []
        self.lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self.embedding, name)

    def embed(self, texts, passage=True):
        before = self.embedding.lifecycle()["session_loaded"]
        started = time.perf_counter()
        successful = False
        try:
            result = self.embedding.embed(texts, passage)
            successful = True
            return result
        finally:
            with self.lock:
                self.calls.append({"elapsed_ms": (time.perf_counter() - started) * 1000, "passage": passage,
                    "input_count": len(texts), "session_loaded_before": before, "completed": successful})


def durations(values):
    values = sorted(values)
    def quantile(fraction):
        position = (len(values) - 1) * fraction
        lower = math.floor(position)
        return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)
    return {"count": len(values), "p50_ms": quantile(.5) if values else None, "p95_ms": quantile(.95) if values else None,
            "method": "Linear interpolation of empirical durations; includes actual tokenizer/inference and first load when recorded cold"}


def storage_measurement(collections_dir, collection):
    if collections_dir is None:
        return {"status": "NOT_MEASURED", "reason": "Pass the verified Qdrant collections directory explicitly"}
    root = Path(collections_dir).resolve()
    path = root / collection
    if not path.is_dir() or not path.resolve().is_relative_to(root):
        raise ValueError("The requested actual collection directory is absent or outside the verified storage root")
    files = [file for file in path.rglob("*") if file.is_file()]
    if any(not file.resolve().is_relative_to(path.resolve()) for file in files):
        raise ValueError("Collection file points outside its actual directory")
    return {"status": "MEASURED", "collection": collection, "files": len(files), "bytes": sum(file.stat().st_size for file in files),
            "measurement_limit": "Logical file sizes at this instant, including current index/WAL; not allocated disk bytes or final compaction"}


def artifact_storage(embedding):
    directory = getattr(embedding, "directory", None)
    if directory is None or not Path(directory).is_dir():
        return {"status": "NOT_MEASURED", "reason": "No actual artifact directory is present"}
    root = Path(directory).resolve()
    files = [path for path in root.rglob("*") if path.is_file()]
    if any(not path.resolve().is_relative_to(root) for path in files):
        raise ValueError("Model artifact file points outside its configured directory")
    return {"status": "MEASURED", "files": len(files), "bytes": sum(path.stat().st_size for path in files),
            "measurement_limit": "Logical sizes of all provisioned files in the model directory, separately from collection storage"}


def selector_identity():
    files = ["scope.py", "retrieval.py", "context.py", "query.py", "embedding.py"]
    hashes = {name: file_sha(Path(__file__).parent / name) for name in files}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


async def assert_quiet(settings):
    """Refuse a second API or a resident LLM; no service starts or stops here."""
    async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
        try:
            await client.get(settings.origin + "/api/v1/health")
        except httpx.ConnectError:
            pass
        else:
            raise ApiError("comparison_requires_stopped_api", "Arrêter l'API avant le comparatif à un seul graphe.", 409)
        try:
            response = await client.get(settings.value("llm", "base_url", "http://127.0.0.1:11434").rstrip("/") + "/api/ps")
            response.raise_for_status()
            if response.json().get("models"):
                raise ApiError("comparison_requires_unloaded_llm", "Décharger les modèles Ollama avant le comparatif.", 409)
        except httpx.ConnectError:
            pass


def development_inputs(source_path, dataset_path):
    source = json.loads(source_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    verify_annotations(source, dataset)
    if not dataset.get("questions") or any(question.get("split") != "development" for question in dataset["questions"]):
        raise ValueError("Only frozen development questions are admitted; final comparison is forbidden")
    return source, dataset


def resolved(question):
    return question.get("annotation_state") == "RESOLVED" and question.get("scope_resolved") and all(unit.get("resolved_spans") for unit in question.get("expected_units", []))


def corpus_chunks(db, resolver, questions):
    generations = set()
    for question in questions:
        if not resolved(question):
            continue
        snapshot = resolver.resolve(EvaluationContextRequest(question=question["question"], scope=question["scope_resolved"], mode=question.get("mode", "question")).scope)
        if not question.get("versions_snapshot") or {version["generation_id"] for version in question["versions_snapshot"]} != set(snapshot.generations):
            raise ValueError("Frozen annotations must cover every exported scope generation")
        for version in question.get("versions_snapshot", []):
            generation = version["generation_id"]
            if (generation not in snapshot.generations or snapshot.versions[generation] != version["version_id"]
                    or snapshot.documents[generation] != version["document_id"]):
                raise ValueError("Frozen annotation generation/version/document differs from exported scope")
            actual = db.version(version["version_id"])
            if version.get("file_sha256") and actual["sha256"] != version["file_sha256"]:
                raise ValueError("Frozen PDF SHA differs from exported original")
            generation_row = db.one("SELECT extraction_revision_id FROM index_generations WHERE id=?", (generation,))
            if generation_row["extraction_revision_id"] != version.get("extraction_revision_id"):
                raise ValueError("Frozen extraction revision differs from exported generation")
        for unit in question.get("expected_units", []):
            for alternative in [unit] + [value for value in unit.get("alternatives", []) if isinstance(value, dict)]:
                for span in alternative.get("resolved_spans") or []:
                    block = db.one("SELECT * FROM blocks WHERE generation_id=? AND id=?", (span["generation_id"], span["block_id"]))
                    start, end = span["start_offset"], span["end_offset"]
                    if (not block or span["generation_id"] not in snapshot.generations or span["version_id"] != snapshot.versions[span["generation_id"]]
                            or block["extraction_revision_id"] != span["extraction_revision_id"] or block["page_index"] != span["page_index"]
                            or span.get("offset_unit") != "unicode_code_point" or type(start) is not int or type(end) is not int
                            or not 0 <= start < end <= len(block["text"]) or block["text"][start:end] != span["text"]
                            or block["source_text_hash"] != span["source_text_hash"]
                            or hashlib.sha256(block["text"].encode()).hexdigest() != span["source_text_hash"]):
                        raise ValueError("Frozen proof span/hash/revision/codepoint offsets differ from exported source")
        # A selected source bypasses embeddings and survives vector cleanup.
        if not snapshot.spans:
            generations.update(snapshot.generations)
    if not generations:
        return []
    ordered = sorted(generations)
    chunks = db.rows(f"SELECT * FROM chunks WHERE generation_id IN ({','.join('?' for _ in ordered)}) ORDER BY chunk_uuid", ordered)
    for chunk in chunks:
        if hashlib.sha256(chunk["text"].encode()).hexdigest() != chunk["text_hash"]:
            raise ValueError("Exported immutable chunk text hash differs")
    return chunks


async def build_candidate(db, embedding, vectors, chunks, resources):
    # Validate every immutable passage before making a collection or embedding.
    counts = [embedding.count(chunk["text"]) for chunk in chunks]
    if any(count > 448 for count in counts):
        raise ApiError("comparison_input_too_long", "Les chunks figés dépassent 448 tokens Granite ; aucun redécoupage implicite.", 422)
    await vectors.ensure_collection()
    started = time.perf_counter()
    for start in range(0, len(chunks), 8):
        resources.ensure()
        batch = chunks[start:start + 8]
        encoded = await asyncio.to_thread(embedding.embed, [chunk["text"] for chunk in batch])
        resources.ensure()
        points = []
        for chunk, vector in zip(batch, encoded, strict=True):
            sources = db.rows("SELECT page_index,block_id FROM chunk_sources WHERE chunk_uuid=? ORDER BY position", (chunk["chunk_uuid"],))
            document = db.version(chunk["version_id"])["document_id"]
            points.append({"id": chunk["chunk_uuid"], "vector": {"dense": vector}, "payload": {
                "generation_id": chunk["generation_id"], "version_id": chunk["version_id"], "document_id": document,
                "page_indices": sorted({source["page_index"] for source in sources}), "block_ids": sorted({source["block_id"] for source in sources}), "text_hash": chunk["text_hash"]}})
        await vectors.upsert(points)
        await vectors.verify({chunk["chunk_uuid"]: chunk["text_hash"] for chunk in batch})
    elapsed = time.perf_counter() - started
    return {"chunks": len(chunks), "elapsed_seconds": elapsed, "chunks_per_second": len(chunks) / elapsed if elapsed else None,
            "maximum_passage_tokens": max(counts, default=0), "cache": "Dedicated Qdrant collection; SQLite production cache untouched"}


async def evaluate_context(question, db, resolver, search, tokenizer, settings):
    request = EvaluationContextRequest(question=question["question"], scope=question["scope_resolved"], mode=question.get("mode", "question"), prior_user_question=question.get("prior_user_question"))
    snapshot = resolver.resolve(request.scope)
    context = ContextBuilder(settings, tokenizer)
    queries = QueryService(db, resolver, search, context, None, settings)
    prior = [{"id": "evaluation_prior_user", "question": request.prior_user_question, "snapshot_json": json_dump(snapshot.as_dict())}] if request.prior_user_question else None
    effective, resolution, choices = queries.resolve_followup(request, snapshot, prior)
    if choices:
        return {"state": "needs_clarification", "resolution": resolution, "choices": choices, "scope_snapshot": snapshot.as_dict(), "model_called": False}
    retrieved = await search.search(effective, snapshot, request.mode)
    expanded = [resolver.expand_parent(source, snapshot, tokenizer, settings.value("chunking", "parent_expand_max_llm_tokens", 900)) for source in retrieved["results"]]
    messages, sources, metrics, warnings = context.build(effective, expanded, request.mode, [])
    return {"state": "context_ready", "effective_question": effective, "resolution": resolution, "scope_snapshot": snapshot.as_dict(),
            "retrieval_top10": retrieved["top10"], "retrieval_final": retrieved["results"], "context_sources": sources,
            "metrics": metrics, "warnings": retrieved["warnings"] + warnings, "model_called": False,
            "retrieval_ms": retrieved["elapsed_ms"], "messages_sha256": hashlib.sha256(json_dump(messages).encode()).hexdigest()}


async def run(args):
    settings = Settings.load(args.profile)
    if args.snapshot.resolve() == settings.db_path.resolve():
        raise ValueError("Use an exported checkpointed SQLite image, never the live application database")
    if args.build_candidate and args.model != "granite":
        raise ValueError("The E5 production collection is strictly read-only")
    source, dataset = development_inputs(args.source_dataset, args.dataset)
    db = FrozenDatabase(args.snapshot, args.snapshot_sha256)
    resolver = ScopeResolver(db)
    chunks = corpus_chunks(db, resolver, dataset["questions"])
    engine = EmbeddingService(settings) if args.model == "e5" else GraniteEmbedding(settings)
    embedding = TimedEmbedding(engine)
    tokenizer = LlmTokenizer(settings)
    vectors = None
    resources = ResourceSamples(settings.value("resources", "host_available_min_mib", 1536), args.snapshot.parent)
    rows, index_measurement, collection_state, failure, storage, model_storage = [], None, None, None, None, None
    phase = "quiet_preflight"
    identity = {"snapshot_sha256": args.snapshot_sha256, "source_dataset_sha256": canonical_sha(source), "resolved_annotations_sha256": canonical_sha(dataset),
                "chunks_identity_sha256": canonical_sha([{key: chunk[key] for key in ("chunk_uuid", "text_hash", "generation_id", "version_id", "extraction_revision_id")} for chunk in chunks]),
                "profile_sha256": canonical_sha(settings.profile), "selector_sha256": selector_identity(),
                "runner_sha256": canonical_sha({name: file_sha(Path(__file__).parent / name) for name in ["comparison.py", "embedding_comparison.py", "qualification.py"]})}
    try:
        await assert_quiet(settings)
        with resources.running():
            phase = "artifact_identity"
            identity.update(dense_identity=embedding.identity(), llm_tokenizer_identity=tokenizer.identity())
            model_storage = artifact_storage(engine)
            vectors = QdrantStore(settings) if args.model == "e5" else ComparisonVectorStore(settings, embedding, args.collection_prefix)
            identity["qdrant_collection"] = vectors.collection
            phase = "candidate_index" if args.build_candidate else "collection_readback"
            if args.build_candidate:
                index_measurement = await build_candidate(db, embedding, vectors, chunks, resources)
            await vectors.verify({chunk["chunk_uuid"]: chunk["text_hash"] for chunk in chunks})
            search = SearchService(db, resolver, embedding, vectors, settings)
            phase = "retrieval_context"
            for question in dataset["questions"]:
                if not resolved(question):
                    rows.append({"question_id": question["id"], "category": question["category"], "language": question["language"], "status": "UNRESOLVED"})
                    continue
                resources.ensure()
                started = time.perf_counter()
                before_calls = len(embedding.calls)
                try:
                    response = await evaluate_context(question, db, resolver, search, tokenizer, settings)
                    resources.ensure()
                    row = evaluate_question(question, response)
                    row.update(language=question["language"], elapsed_ms=(time.perf_counter() - started) * 1000)
                    row["query_embedding_calls"] = embedding.calls[before_calls:]
                except (ApiError, ValueError, KeyError) as error:
                    if isinstance(error, ApiError) and (error.status >= 500 or error.code == "comparison_input_too_long"):
                        raise
                    row = {"question_id": question["id"], "category": question["category"], "language": question["language"], "status": "ERROR", "error_code": error.code if isinstance(error, ApiError) else type(error).__name__}
                rows.append(row)
            phase = "collection_storage"
            collection_state = await vectors.request("GET", f"/collections/{vectors.collection}")
            storage = storage_measurement(getattr(args, "qdrant_collections_dir", None), vectors.collection)
    except Exception as error:
        failure = {"code": error.code if isinstance(error, ApiError) else type(error).__name__, "phase": phase}
    finally:
        embedding.release_session()
        embedding.release_tokenizer()
        tokenizer.release_tokenizer()
        if vectors is not None:
            await vectors.close()
    try:
        db.verify_image()
    except (ApiError, OSError) as error:
        failure = {"code": error.code if isinstance(error, ApiError) else type(error).__name__, "phase": "snapshot_final_verification"}
    if resources.violation.is_set() and failure is None:
        failure = {"code": "comparison_resource_reserve", "phase": "final_resource_sample"}
    metrics = summary(rows)
    metrics["by_language"] = {language: summary([row for row in rows if row.get("language") == language], False) for language in sorted({row["language"] for row in rows})}
    dense_exercised = any(not call["passage"] and call["completed"] for call in embedding.calls)
    complete = not failure and len(rows) == metrics["evaluated_questions"] == 100 and dense_exercised
    passes = (metrics["recall_at_10"]["rate"] or 0) >= .9 and (metrics["evidence_coverage_at_context"]["rate"] or 0) >= .9 and metrics["scope_leakage_count"] == 0
    return {"date_utc": datetime.now(UTC).isoformat(), "model_arm": args.model, "split": "development",
            "status": "FAIL" if failure or complete and not passes else ("PASS" if complete else "INCOMPLETE"),
            "identity": identity, "metrics": metrics, "questions": rows, "failure": failure, "indexing": index_measurement,
            "resources": {"sample_interval_seconds": .5, "samples": resources.samples, "reserve_mib": resources.reserve_mib, "violation": resources.violation.is_set(),
                          "sample_error": resources.error, "disk_path": str(resources.disk_path)},
            "timings": {"query_embedding": durations([call["elapsed_ms"] for call in embedding.calls if not call["passage"] and call["completed"]]),
                        "warm_query_embedding": durations([call["elapsed_ms"] for call in embedding.calls if not call["passage"] and call["completed"] and call["session_loaded_before"]]),
                        "context_total": durations([row["elapsed_ms"] for row in rows if row["status"] == "EVALUATED"]), "actual_embedding_calls": embedding.calls},
            "graph_signature": getattr(embedding, "graph_signature", None), "embedding_lifecycle": embedding.lifecycle(),
            "qdrant_effective_state": collection_state, "collection_storage": storage, "model_storage": model_storage, "dense_exercised": dense_exercised,
            "limits": ["One graph in this process; API stopped and Ollama unloaded are checked before engine loading; root still owns OCR/concurrency admission.",
                       "No generation, answer accuracy, final split, 25000-chunk performance or winner selection is qualified by this report.",
                       "Resource samples observe this process and host available memory, not all independent service RSS/private peaks.",
                       "Unresolved annotations/errors or a run without actual dense-query calls cannot yield PASS. Collections are retained for inspection; no destructive cleanup."]}


def compare_reports(baseline, candidate):
    if baseline.get("model_arm") != "e5" or candidate.get("model_arm") != "granite" or any(report.get("split") != "development" for report in (baseline, candidate)):
        raise ValueError("Only the E5 and Granite development arms may be paired")
    shared = ["snapshot_sha256", "source_dataset_sha256", "resolved_annotations_sha256", "chunks_identity_sha256", "profile_sha256", "selector_sha256", "runner_sha256", "llm_tokenizer_identity"]
    if any(not baseline.get("identity", {}).get(key) or baseline["identity"][key] != candidate.get("identity", {}).get(key) for key in shared):
        raise ValueError("Comparison inputs/source/selector differ; no quality delta is admitted")
    if [row["question_id"] for row in baseline["questions"]] != [row["question_id"] for row in candidate["questions"]]:
        raise ValueError("The two arms must record the same ordered development questions")
    if baseline.get("qdrant_effective_state", {}).get("config") != candidate.get("qdrant_effective_state", {}).get("config"):
        raise ValueError("The actual Qdrant collection configuration differs between arms")
    def delta(first, second):
        values = {}
        for key, field in [("recall_at_5", "rate"), ("recall_at_10", "rate"), ("evidence_coverage_at_context", "rate"), ("mrr_at_10", "mean")]:
            old, new = first[key][field], second[key][field]
            values[key] = new - old if old is not None and new is not None else None
        return values
    result = {"status": "PAIRED_DEVELOPMENT_DIAGNOSTIC", "delta_granite_minus_e5": delta(baseline["metrics"], candidate["metrics"]),
              "complete_arms": baseline["status"] == candidate["status"] == "PASS", "automatic_winner": None,
              "limit": "Quality deltas alone do not select a model; compare cost, failure evidence and unchanged DoD before a root decision"}
    for group in ("by_category", "by_language"):
        result[group] = {key: delta(baseline["metrics"][group][key], candidate["metrics"][group][key])
                         for key in sorted(set(baseline["metrics"][group]) & set(candidate["metrics"][group]))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["snapshot", "dataset", "source-dataset", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--model", choices=["e5", "granite"], required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--collection-prefix", default="diag_gr97")
    parser.add_argument("--qdrant-collections-dir", type=Path, help="Verified actual Qdrant collections directory for read-only logical-size measurement")
    parser.add_argument("--compare-baseline", type=Path, help="Prior E5 report from exactly the same frozen inputs/code")
    parser.add_argument("--build-candidate", action="store_true")
    args = parser.parse_args()
    report_root = Path(__file__).resolve().parents[2] / "RAG_Local_Agents/reports/backend"
    if not args.output.resolve().is_relative_to(report_root) or args.output.exists():
        parser.error("Output must be a new backend report")
    try:
        report = asyncio.run(run(args))
    except Exception as error:
        report = {"date_utc": datetime.now(UTC).isoformat(), "model_arm": args.model, "split": "development", "status": "FAIL",
                  "failure": {"phase": "preflight", "code": error.code if isinstance(error, ApiError) else type(error).__name__}, "questions": [],
                  "limit": "Preflight failed; no comparison quality or winner can be inferred"}
    if args.compare_baseline:
        try:
            report["comparison"] = compare_reports(json.loads(args.compare_baseline.read_text(encoding="utf-8")), report)
        except (ValueError, KeyError, OSError) as error:
            report["comparison"] = {"status": "NOT_COMPARABLE", "code": type(error).__name__}
            report["arm_status"], report["status"] = report["status"], "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"status": report["status"], "model_arm": args.model, "output": str(args.output)}, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
