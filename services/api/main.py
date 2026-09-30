import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.staticfiles import StaticFiles

from .context import ContextBuilder, LlmTokenizer
from .db import Database, json_dump, now, relative_pdf_path, uid
from .embedding import EmbeddingService
from .errors import ApiError
from .indexing import Indexer
from .jobs import JobSupervisor
from .ollama import OllamaGateway
from .query import QueryService
from .reconcile import Reconciler
from .retrieval import QdrantStore, SearchService
from .schemas import DocumentMove, EvaluationContextRequest, QueryRequest, RuntimeMode
from .scope import ScopeResolver
from .settings import Settings


def create_app(profile_path=None, governor=None, ingestion_runner=None, *, settings=None, embedding=None, vectors=None, ollama=None, tokenizer=None, start_jobs=True):
    settings = settings or Settings.load(profile_path)
    db = Database(settings.db_path)
    embedding = embedding or EmbeddingService(settings)
    vectors = vectors or QdrantStore(settings)
    ollama = ollama or OllamaGateway(settings)
    tokenizer = tokenizer or LlmTokenizer(settings)
    cache_release_state = {"last": None}
    if governor is None:
        try:
            from services.runtime.resources import ResourceGovernor
            governor_profile = {**settings.profile, "app": {**settings.profile.get("app", {}), "data_dir": str(settings.data_dir)}}
            governor = ResourceGovernor(governor_profile)
        except ImportError:
            # Startup is blocked until the real governor exists; test injections are explicit.
            governor = None
    if governor is not None and hasattr(ollama, "unload"):
        governor.before_ingestion = ollama.unload
        governor.after_resource_violation = ollama.unload
    if governor is not None and hasattr(ollama, "loaded_state"):
        async def before_generation():
            loaded = await ollama.loaded_state()
            threshold = settings.value("resources", "initial_llm_load_peak_estimate_mib", 6144) + settings.value("resources", "host_available_min_mib", 1536)
            if loaded.get("resident") is False and governor.snapshot()["available_mib"] < threshold:
                loaded["cold_cache_release_before"] = governor.snapshot()
                if hasattr(embedding, "release_session"):
                    loaded["embedding_release"] = await asyncio.to_thread(embedding.release_session)
                if hasattr(embedding, "release_tokenizer"):
                    loaded["embedding_tokenizer_release"] = await asyncio.to_thread(embedding.release_tokenizer)
                if hasattr(tokenizer, "release_tokenizer"):
                    loaded["llm_tokenizer_release"] = await asyncio.to_thread(tokenizer.release_tokenizer)
                loaded["cold_cache_release_after"] = governor.snapshot()
                cache_release_state["last"] = {"before": loaded["cold_cache_release_before"], "after": loaded["cold_cache_release_after"],
                    "cold_required_mib": threshold, "embedding_session": loaded.get("embedding_release"),
                    "embedding_tokenizer": loaded.get("embedding_tokenizer_release"), "llm_tokenizer": loaded.get("llm_tokenizer_release")}
            return loaded
        governor.before_generation = before_generation
    resolver = ScopeResolver(db)
    search = SearchService(db, resolver, embedding, vectors, settings)
    indexer = Indexer(db, embedding, vectors, settings, tokenizer)
    queries = QueryService(db, resolver, search, ContextBuilder(settings, tokenizer), ollama, settings, governor)
    jobs = JobSupervisor(db, indexer, settings, governor, ingestion_runner)
    reconciler = Reconciler(db, vectors)

    @asynccontextmanager
    async def lifespan(application):
        db.initialize()
        (settings.data_dir / "originals").mkdir(parents=True, exist_ok=True)
        if start_jobs:
            if governor is None:
                raise RuntimeError("ResourceGovernor requis pour l'exécution applicative.")
            jobs.start()
            reconciler.start()
        yield
        await queries.close()
        await jobs.close()
        await reconciler.close()
        await vectors.close()
        await ollama.close()

    application = FastAPI(title="RAG PDF local", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    application.state.db = db
    application.state.settings = settings
    application.state.embedding = embedding
    application.state.vectors = vectors
    application.state.indexer = indexer
    application.state.queries = queries
    application.state.jobs = jobs
    application.state.search = search
    application.state.reconciler = reconciler
    application.state.mutations_paused = False
    # Pas de verrou global : les écritures sont bornées par leurs transactions SQLite. Seule la mise en
    # pause pour sauvegarde attend la fin des mutations déjà admises ; recherche et contrôles n'attendent rien.
    application.state.mutations_in_flight = 0
    # Quiesce et resume restent sérialisés : un resume reçu pendant un quiesce long (timeout de `rag backup`)
    # ne doit pas être suivi d'une re-suspension des jobs et du nettoyage vectoriel.
    control_lock = asyncio.Lock()
    port = settings.value("app", "port", 8785)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    allowed_origins = {f"http://{host}" for host in allowed_hosts}
    maximum_upload = settings.value("pdf", "max_file_mib", 200) * 1024 * 1024

    @application.middleware("http")
    async def local_boundary(request: Request, call_next):
        request_id = uid()
        request.state.request_id = request_id
        if request.headers.get("host", "").lower() not in allowed_hosts:
            return JSONResponse({"code": "invalid_host", "message": "Host non autorisé.", "details": {}, "request_id": request_id}, status_code=400)
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse({"code": "invalid_origin", "message": "Origine non autorisée.", "details": {}, "request_id": request_id}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"code": "cross_site_request", "message": "Requête intersite refusée.", "details": {}, "request_id": request_id}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > maximum_upload + 1024 * 1024):
                return JSONResponse({"code": "request_too_large", "message": "Requête trop volumineuse.", "details": {}, "request_id": request_id}, status_code=413)
            administrative = request.url.path.startswith("/api/v1/admin/")
            if application.state.mutations_paused and not administrative:
                return JSONResponse({"code": "mutations_paused", "message": "Sauvegarde en cours ; mutations suspendues.", "details": {}, "request_id": request_id}, status_code=503)
            counted = not administrative and request.url.path != "/api/v1/search"
            application.state.mutations_in_flight += counted
            try:
                response = await call_next(request)
            finally:
                application.state.mutations_in_flight -= counted
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        return response

    @application.exception_handler(ApiError)
    async def controlled_error(request, error):
        return JSONResponse({"code": error.code, "message": error.message, "details": error.details, "request_id": getattr(request.state, "request_id", uid())}, status_code=error.status)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = [{"loc": list(item["loc"]), "type": item["type"]} for item in error.errors()]
        return JSONResponse({"code": "validation_error", "message": "Entrée invalide.", "details": {"fields": details}, "request_id": getattr(request.state, "request_id", uid())}, status_code=422)

    @application.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse({"code": "internal_error", "message": "Erreur interne ; consulter les diagnostics locaux.", "details": {}, "request_id": getattr(request.state, "request_id", uid())}, status_code=500)

    prefix = "/api/v1"

    def selector_identity():
        files = ["scope.py", "retrieval.py", "context.py", "query.py", "embedding.py"]
        hashes = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in files}
        return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()

    def control_authorized(request):
        token = os.environ.get("RAG_CONTROL_TOKEN", "")
        provided = request.headers.get("x-rag-control-token", "")
        if not token or not provided or not secrets.compare_digest(token, provided):
            raise ApiError("invalid_control_token", "Contrôle d'administration non autorisé.", 403)

    @application.post(prefix + "/admin/quiesce")
    async def quiesce(request: Request):
        control_authorized(request)
        async with control_lock:
            application.state.mutations_paused = True
            while application.state.mutations_in_flight:
                await asyncio.sleep(0.05)
            await queries.close()
            job_state = await jobs.quiesce()
            await reconciler.quiesce()
            with db.connect() as connection:
                checkpoint = list(connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone())
        return {"state": "quiesced", "active_queries": len(queries.tasks), "jobs": job_state, "sqlite_checkpoint": checkpoint}

    @application.post(prefix + "/admin/resume")
    async def resume_mutations(request: Request):
        control_authorized(request)
        async with control_lock:
            jobs.resume_after_backup()
            reconciler.suspended = False
            application.state.mutations_paused = False
        return {"state": "running", "mutations_paused": False, "ingestion_auto_resume": False}

    @application.get(prefix + "/admin/status")
    async def admin_status(request: Request):
        control_authorized(request)
        return {"mutations_paused": application.state.mutations_paused, "active_queries": len(queries.tasks), "active_job": jobs._active}

    @application.post(prefix + "/admin/evaluation/context")
    async def evaluation_context(body: EvaluationContextRequest, request: Request):
        control_authorized(request)
        if application.state.mutations_paused:
            raise ApiError("mutations_paused", "Évaluation suspendue pendant la sauvegarde.", 503)
        if jobs._active:
            raise ApiError("ingestion_active", "Attendre le checkpoint avant une évaluation reproductible.", 409)
        if queries.tasks:
            raise ApiError("query_active", "Attendre la fin des questions avant une évaluation reproductible.", 409)
        snapshot = resolver.resolve(body.scope, body.mode)
        prior = [{"id": "evaluation_prior_user", "question": body.prior_user_question, "snapshot_json": json_dump(snapshot.as_dict())}] if body.prior_user_question else None
        question, resolution, choices = queries.resolve_followup(body, snapshot, prior)
        profile_sha = hashlib.sha256(json.dumps(settings.profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if choices:
            return {"state": "needs_clarification", "choices": choices, "resolution": resolution, "scope_snapshot": snapshot.as_dict(), "model_called": False, "profile_sha256": profile_sha}
        governor.begin_interactive() if governor else None
        try:
            retrieved = await search.search(question, snapshot, body.mode)
            expanded = await asyncio.to_thread(lambda: [resolver.expand_parent(source, snapshot, tokenizer, settings.value("chunking", "parent_expand_max_llm_tokens", 900)) for source in retrieved["results"]])
            messages, sources, metrics, warnings = await asyncio.to_thread(queries.context.build, question, expanded, body.mode, [])
            return {"state": "context_ready", "effective_question": question, "resolution": resolution,
                    "scope_snapshot": snapshot.as_dict(), "retrieval_top10": retrieved["top10"], "retrieval_final": retrieved["results"],
                    "context_sources": sources, "metrics": metrics, "warnings": snapshot.warnings + retrieved["warnings"] + warnings,
                    "retrieval_ms": retrieved["elapsed_ms"], "model_called": False, "profile_sha256": profile_sha,
                    "selector_sha256": selector_identity(), "messages_sha256": hashlib.sha256(json_dump(messages).encode()).hexdigest(),
                    "serialized_context_sha256": hashlib.sha256(tokenizer.serialized(messages).encode()).hexdigest() if hasattr(tokenizer, "serialized") else None,
                    "llm_tokenizer_identity": tokenizer.identity() if hasattr(tokenizer, "identity") else {"status": "explicit_test_substitute"},
                    "dense_identity": embedding.identity() if hasattr(embedding, "identity") else {"status": "explicit_test_substitute"}}
        finally:
            governor.finish_interactive() if governor else None

    @application.get(prefix + "/health")
    async def health():
        return {"status": "alive", "service": "rag-api"}

    @application.get(prefix + "/readiness")
    async def readiness():
        checks = {"sqlite": False, "embedding": False, "llm_tokenizer": False, "qdrant": False, "ollama": False, "governor": governor is not None}
        blockers = []
        try:
            checks["sqlite"] = db.one("PRAGMA quick_check")["quick_check"] == "ok"
        except sqlite3.Error:
            blockers.append("sqlite_unavailable")
        checks["embedding"] = (settings.embedding_dir / "tokenizer.json").exists()
        try:
            embedding.model_path()
            checks["embedding"] = checks["embedding"] and True
        except ApiError:
            checks["embedding"] = False
        checks["llm_tokenizer"] = (settings.llm_tokenizer_dir / "tokenizer.json").exists() and (settings.llm_tokenizer_dir / "tokenizer_config.json").exists()
        try:
            await vectors.request("GET", f"/collections/{vectors.collection}")
            checks["qdrant"] = True
        except (ApiError, AttributeError):
            pass
        try:
            response = await ollama.client.get("/api/tags")
            response.raise_for_status()
            checks["ollama"] = any(model.get("name") == settings.value("llm", "model", "qwen3.5:4b") for model in response.json().get("models", []))
        except Exception:
            pass
        blockers.extend(key + "_not_ready" for key, ready in checks.items() if not ready)
        return JSONResponse({"status": "ready" if all(checks.values()) else "blocked", "checks": checks, "blockers": blockers}, status_code=200 if all(checks.values()) else 503)

    def document_rows(where="d.deleted_at IS NULL", parameters=(), limit=100, offset=0):
        rows = db.rows("SELECT d.*,g.version_id AS active_version_id,g.extraction_revision_id,v.sha256,v.page_count,g.coverage_json FROM documents d LEFT JOIN index_generations g ON g.id=d.active_generation_id LEFT JOIN document_versions v ON v.id=g.version_id WHERE " + where + " ORDER BY d.relative_path LIMIT ? OFFSET ?", tuple(parameters) + (limit, offset))
        for row in rows:
            row["version_id"] = row["active_version_id"]
            row["coverage"] = json.loads(row.pop("coverage_json") or "{}")
        return rows

    def job_rows(where="1", parameters=(), limit=100):
        rows = db.rows("SELECT j.id,j.document_id,j.version_id,j.generation_id,j.state,j.stage,j.progress,j.attempts,j.error_code,j.error_message,j.created_at,j.updated_at,g.coverage_json,g.warnings_json,g.published_at,(d.active_generation_id=j.generation_id AND d.deleted_at IS NULL) AS active FROM jobs j JOIN documents d ON d.id=j.document_id LEFT JOIN index_generations g ON g.id=j.generation_id WHERE " + where + " ORDER BY j.created_at DESC LIMIT ?", tuple(parameters) + (limit,))
        for row in rows:
            row["coverage"] = json.loads(row.pop("coverage_json") or "{}")
            row["warnings"] = json.loads(row.pop("warnings_json") or "[]")
            row["published"] = row["published_at"] is not None
            row["active"] = bool(row["active"])
        return rows

    @application.get(prefix + "/library/tree")
    async def library_tree(limit: int = 100, offset: int = 0, cursor: str | None = None, search: str | None = None):
        if cursor is not None:
            if not cursor.isdigit():
                raise ApiError("invalid_cursor", "Curseur invalide.")
            offset = int(cursor)
        if not 1 <= limit <= 200 or offset < 0:
            raise ApiError("invalid_pagination", "Pagination invalide.")
        where = "d.deleted_at IS NULL"
        parameters = []
        if search:
            where += " AND instr(lower(d.relative_path),lower(?))>0"
            parameters.append(search[:256])
        total = db.one("SELECT count(*) AS n FROM documents d WHERE " + where, parameters)["n"]
        documents = document_rows(where, parameters, limit, offset)
        return {"folders": db.rows("SELECT * FROM folders ORDER BY path"), "documents": documents, "total_documents": total, "total": total, "offset": offset, "limit": limit, "next_cursor": str(offset + limit) if offset + limit < total else None}

    @application.post(prefix + "/documents/import", status_code=202)
    async def import_documents(files: Annotated[list[UploadFile], File()],
                               relative_paths: Annotated[str | None, Form()] = None):
        if not 1 <= len(files) <= 50:
            raise ApiError("invalid_file_count", "Importer entre un et cinquante fichiers.")
        try:
            paths = json.loads(relative_paths) if relative_paths else [upload.filename for upload in files]
        except (ValueError, TypeError) as error:
            raise ApiError("invalid_paths", "La liste de chemins est invalide.") from error
        if not isinstance(paths, list) or len(paths) != len(files) or not all(isinstance(path, str) for path in paths):
            raise ApiError("invalid_paths", "Un chemin relatif est requis par fichier.")
        paths = [relative_pdf_path(path) for path in paths]
        imports = []
        originals = settings.data_dir / "originals"
        temporary_root = settings.data_dir / "uploads"
        temporary_root.mkdir(parents=True, exist_ok=True)
        for upload, relative_path in zip(files, paths, strict=True):
            temporary = temporary_root / (uid() + ".part")
            digest = hashlib.sha256()
            total = 0
            signature = b""
            try:
                with temporary.open("xb") as output:
                    while content := await upload.read(1024 * 1024):
                        total += len(content)
                        if total > maximum_upload:
                            raise ApiError("file_too_large", "PDF trop volumineux.", 413)
                        signature = (signature + content)[:1024] if len(signature) < 1024 else signature
                        digest.update(content)
                        output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
                if not signature.lstrip().startswith(b"%PDF-"):
                    raise ApiError("invalid_pdf", "Signature PDF absente.")
                sha256 = digest.hexdigest()
                blob_path = originals / (sha256 + ".pdf")
                if blob_path.exists():
                    with blob_path.open("rb") as original:
                        existing_hash = hashlib.file_digest(original, "sha256").hexdigest()
                    if existing_hash != sha256:
                        raise ApiError("original_integrity_failure", "Original existant corrompu.", 409)
                else:
                    os.replace(temporary, blob_path)
                imports.append(db.import_original(relative_path, sha256, blob_path))
            finally:
                if temporary.exists():
                    temporary.unlink()
                await upload.close()
        return {"imports": imports, **(imports[0] if len(imports) == 1 else {})}

    @application.get(prefix + "/documents/{document_id}")
    async def document(document_id: str):
        rows = document_rows("d.id=? AND d.deleted_at IS NULL", (document_id,), 1)
        if not rows:
            raise ApiError("document_not_found", "Document inconnu.", 404)
        result = rows[0]
        result["versions"] = db.rows("SELECT id,document_id,sha256,page_count,created_at FROM document_versions WHERE document_id=? ORDER BY created_at DESC", (document_id,))
        for version in result["versions"]:
            version["file_url"] = f"{prefix}/versions/{version['id']}/file"
        result["jobs"] = job_rows("j.document_id=?", (document_id,))
        return result

    @application.delete(prefix + "/documents/{document_id}")
    async def remove_document(document_id: str):
        if not db.one("SELECT id FROM documents WHERE id=?", (document_id,)):
            raise ApiError("document_not_found", "Document inconnu.", 404)
        with db.transaction() as connection:
            connection.execute("UPDATE documents SET deleted_at=?,state='deleted',updated_at=? WHERE id=?", (now(), now(), document_id))
            connection.execute("UPDATE jobs SET cancel_requested=1,updated_at=? WHERE document_id=? AND state NOT IN ('ready','ready_partial','cancelled','error')", (now(), document_id))
            connection.execute("INSERT OR REPLACE INTO vector_cleanup SELECT g.id,'deleted','pending',NULL,?,? FROM index_generations g JOIN document_versions v ON v.id=g.version_id WHERE v.document_id=?", (now(), now(), document_id))
        return {"document_id": document_id, "state": "deleted"}

    @application.post(prefix + "/documents/{document_id}/move")
    async def move_document(document_id: str, body: DocumentMove):
        return db.move_document(document_id, body.relative_path)

    @application.post(prefix + "/documents/{document_id}/reindex", status_code=202)
    async def reindex_document(document_id: str):
        version = db.one("SELECT v.id FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE d.id=? AND d.deleted_at IS NULL ORDER BY v.created_at DESC LIMIT 1", (document_id,))
        if not version:
            raise ApiError("document_not_found", "Document inconnu.", 404)
        existing = db.one("SELECT id FROM jobs WHERE document_id=? AND state IN ('queued','extracting','indexing')", (document_id,))
        if existing:
            return {"job_id": existing["id"], "reused": True}
        job_id = uid()
        db.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, document_id, version["id"], now(), now()))
        return {"job_id": job_id, "version_id": version["id"], "reused": False}

    @application.get(prefix + "/versions/{version_id}/file")
    async def version_file(version_id: str, request: Request):
        path, version = db.file_path(version_id, settings.data_dir / "originals")
        etag = '"' + version["sha256"] + '"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"})
        return FileResponse(path, media_type="application/pdf", filename=version["document_name"], content_disposition_type="inline", headers={"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable", "Accept-Ranges": "bytes"})

    @application.get(prefix + "/versions/{version_id}/outline")
    async def outline(version_id: str, extraction_revision_id: str | None = None):
        generation = db.generation_for_version(version_id, extraction_revision_id)
        sections = db.rows("SELECT id,title,page_index,block_ids_json FROM sections WHERE generation_id=? ORDER BY page_index,id", (generation["id"],))
        for section in sections:
            section["block_ids"] = json.loads(section.pop("block_ids_json"))
        return {"version_id": version_id, "generation_id": generation["id"], "extraction_revision_id": generation["extraction_revision_id"], "sections": sections}

    @application.get(prefix + "/versions/{version_id}/pages/{page_index}/blocks")
    async def page_blocks(version_id: str, page_index: int, extraction_revision_id: str | None = None):
        generation = db.generation_for_version(version_id, extraction_revision_id)
        page = db.one("SELECT * FROM pages WHERE generation_id=? AND page_index=?", (generation["id"], page_index))
        if not page:
            raise ApiError("page_not_found", "Page non extraite ou inconnue.", 404)
        blocks = db.rows("SELECT * FROM blocks WHERE generation_id=? AND page_index=? ORDER BY rowid", (generation["id"], page_index))
        for block in blocks:
            metadata = json.loads(block.pop("metadata_json"))
            block.update(metadata)
            bbox_json = block.pop("bbox_json")
            block["bbox"] = json.loads(bbox_json) if bbox_json else None
            block["type"] = block.pop("kind")
            block["version_id"] = version_id
            block["raw_text"] = block["text"]
        geometry = json.loads(page["geometry_json"])
        geometry["blocks"] = blocks
        return {"version_id": version_id, "generation_id": generation["id"], "extraction_revision_id": generation["extraction_revision_id"], "page": geometry, "blocks": blocks, "warnings": json.loads(generation["warnings_json"])}

    @application.post(prefix + "/search")
    async def search_request(body: QueryRequest):
        snapshot = resolver.resolve(body.scope, body.mode)
        result = await search.search(body.question, snapshot, body.mode)
        result["warnings"] = snapshot.warnings + result["warnings"]
        return result

    @application.post(prefix + "/queries", status_code=202)
    async def create_query(body: QueryRequest):
        return queries.create(body)

    @application.get(prefix + "/queries/{query_id}/events")
    async def query_events(query_id: str, request: Request, after: int = 0):
        if not db.one("SELECT id FROM query_runs WHERE id=?", (query_id,)):
            raise ApiError("query_not_found", "Question inconnue.", 404)
        header = request.headers.get("last-event-id")
        if header:
            if not header.isdigit():
                raise ApiError("invalid_event_id", "ID d'événement invalide.")
            after = max(after, int(header))
        if after < 0:
            raise ApiError("invalid_event_id", "ID d'événement invalide.")
        async def stream():
            cursor = after
            last_heartbeat = time.monotonic()
            while not await request.is_disconnected():
                events = db.rows("SELECT * FROM events WHERE query_id=? AND id>? ORDER BY id LIMIT 128", (query_id, cursor))
                for event in events:
                    cursor = event["id"]
                    yield f"id: {cursor}\nevent: {event['type']}\ndata: {event['data_json']}\n\n"
                row = db.one("SELECT state,last_event_id FROM query_runs WHERE id=?", (query_id,))
                if row["state"] not in {"queued", "running"} and cursor >= row["last_event_id"]:
                    break
                if time.monotonic() - last_heartbeat >= 10:
                    yield ": heartbeat\n\n"
                    last_heartbeat = time.monotonic()
                await asyncio.sleep(0.1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @application.post(prefix + "/queries/{query_id}/cancel")
    async def cancel_query(query_id: str):
        return queries.cancel(query_id)

    @application.get(prefix + "/citations/{query_id}/{source_id}")
    async def citation(query_id: str, source_id: str):
        row = db.one("SELECT * FROM citations WHERE query_id=? AND source_id=?", (query_id, source_id))
        if not row:
            raise ApiError("citation_not_found", "Citation inconnue.", 404)
        db.version(row["version_id"])
        return json.loads(row["source_json"])

    @application.get(prefix + "/jobs")
    async def job_list(limit: int = 100):
        if not 1 <= limit <= 200:
            raise ApiError("invalid_pagination", "Pagination invalide.")
        rows = job_rows(limit=limit)
        return {"jobs": rows, "total": db.one("SELECT count(*) AS n FROM jobs")["n"]}

    @application.post(prefix + "/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        return jobs.cancel(job_id)

    @application.post(prefix + "/jobs/{job_id}/resume")
    async def resume_job(job_id: str):
        return jobs.resume(job_id)

    @application.post(prefix + "/jobs/{job_id}/pause")
    async def pause_job(job_id: str):
        return jobs.pause(job_id)

    @application.post(prefix + "/runtime/mode")
    async def runtime_mode(body: RuntimeMode):
        if governor is None:
            raise ApiError("governor_not_configured", "Gouverneur de ressources absent.", 503)
        if body.mode == "interactive":
            if hasattr(governor, "request_ingestion_pause"):
                governor.request_ingestion_pause()
            else:
                governor.begin_interactive()
                governor.finish_interactive()
            return {"requested_mode": body.mode, **jobs.request_pause_all(), "resources": governor.snapshot()}
        try:
            governor.resume_ingestion()
        except RuntimeError as error:
            raise ApiError("interaction_active", "Une question est active ; reprise différée.", 409) from error
        jobs.resume_after_backup()
        return {"requested_mode": body.mode, "state": "ingestion", "resources": governor.snapshot(), "manual_jobs_require_resume": True}

    @application.post(prefix + "/jobs/{job_id}/publish-partial")
    async def publish_partial(job_id: str):
        job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        generation = db.one("SELECT * FROM index_generations WHERE id=?", (job["generation_id"],))
        if job["state"] != "ready_partial" or not generation or generation["state"] != "ready_partial":
            raise ApiError("not_partial", "Aucune génération partielle vérifiée à publier.", 409)
        indexer.publish(job_id, generation["id"], generation["actual_chunks"], partial=True, allow_partial=True)
        return {"job_id": job_id, "document_id": job["document_id"], "generation_id": generation["id"], "state": "ready_partial", "coverage": json.loads(generation["coverage_json"])}

    @application.get(prefix + "/diagnostics")
    async def diagnostics():
        import platform
        try:
            dense_identity = embedding.identity() if hasattr(embedding, "identity") else {"status": "explicit_test_substitute"}
            collection = vectors.collection if hasattr(vectors, "collection") else None
        except ApiError as error:
            dense_identity, collection = {"status": error.code}, None
        try:
            tokenizer_identity = tokenizer.identity() if hasattr(tokenizer, "identity") else {"status": "explicit_test_substitute"}
        except ApiError as error:
            tokenizer_identity = {"status": error.code}
        return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "platform": platform.system(),
                "logical_cores": os.cpu_count(), "database_bytes": settings.db_path.stat().st_size if settings.db_path.exists() else 0,
                "resources": governor.snapshot() if governor else {"status": "not_configured"},
                "runtime_network": "loopback_only", "active_queries": len(queries.tasks), "dense_identity": dense_identity, "qdrant_collection": collection,
                "llm_tokenizer_identity": tokenizer_identity, "selector_sha256": selector_identity(),
                "embedding_session": embedding.lifecycle() if hasattr(embedding, "lifecycle") else {"status": "explicit_test_substitute"},
                "indexing_cache": indexer.diagnostics(), "ingestion_cache": jobs.diagnostics(),
                "llm_tokenizer_cache": tokenizer.lifecycle() if hasattr(tokenizer, "lifecycle") else {"status": "explicit_test_substitute"},
                "cold_cache_release": cache_release_state["last"],
                "profile_sha256": hashlib.sha256(json.dumps(settings.profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
                "reconciliation": {"staged": reconciler.inspect(), "pending_cleanup": db.one("SELECT count(*) AS n FROM vector_cleanup WHERE state='pending'")["n"]}}

    static_root = settings.root / "apps/web/out"
    if static_root.is_dir():
        application.mount("/", StaticFiles(directory=static_root, html=True), name="web")
    return application


app = create_app()
