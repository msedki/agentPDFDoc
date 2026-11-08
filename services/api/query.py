import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from typing import Any

from services.runtime.platforms import launcher_instruction

from .claims import answer_warnings
from .context import validate_answer
from .db import json_dump, now, uid
from .errors import ApiError
from .evidence_selection import deduplicate_expanded_sources
from .execution_trace import CURRENT_TRACE, ExecutionTrace, fingerprint, record_event
from .retrieval import identifiers, ocr_evidence_warnings, resolve_references
from .structured_answer import Catalogue, StructuredAnswerBuilder


@asynccontextmanager
async def empty_lease():
    yield


async def database_call(operation, *args):
    """Déporte SQLite, puis termine l'opération en cours avant de propager une annulation.

    Annuler `to_thread` n'arrête pas son thread : une écriture delta tardive ne doit pas suivre l'événement terminal.
    """
    task = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
        raise


def complementary_terms(assessment):
    """Use explicit, missing question obligations, never generated answer text."""
    terms = []
    for missing in assessment.get("missing", []):
        for key in ("quantity", "subject", "role"):
            value = missing.get(key)
            if isinstance(value, str) and value not in terms:
                terms.append(value.replace("_", " "))
    return terms[:6]


def _retrieval_limitations(result, context_metrics=None):
    diagnostic = result.get("evidence_selection") or {}
    missing = diagnostic.get("missing_relation_variants", 0)
    lost = ((context_metrics or {}).get("verified_relation_coverage") or {}).get("lost_relation_variants", 0)
    missing = (missing if type(missing) is int and missing > 0 else 0) + (lost if type(lost) is int and lost > 0 else 0)
    return ([{"code": "evidence_coverage_incomplete", "missing_relation_variants": missing}]
            if type(missing) is int and missing > 0 else [])


class QueryService:
    def __init__(self, db, resolver, search, context, ollama, settings, governor=None):
        self.db, self.resolver, self.search, self.context, self.ollama, self.settings = db, resolver, search, context, ollama, settings
        self.governor = governor
        self.tasks = {}
        self.cancel_events = {}
        self.started = set()
        self.generation_lock = asyncio.Lock()
        self.creation_lock = asyncio.Lock()

    @staticmethod
    def history_summary(row):
        return {"query_id": row["id"], "conversation_id": row["conversation_id"], "question": row["question"],
                "state": row["state"], "mode": None, "last_event_id": row["last_event_id"],
                "created_at": row["created_at"], "updated_at": row["updated_at"],
                "events_url": f"/api/v1/queries/{row['id']}/events"}

    def list_runs(self, limit=20, cursor=None, conversation_id=None):
        """Read a stable keyset page; neither stored scope nor archived sources are resolved anew."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ApiError("invalid_history_limit", "Choisir entre 1 et 100 questions par page.")
        clauses: list[str] = []
        parameters: list[Any] = []
        if conversation_id is not None:
            clauses.append("conversation_id=?")
            parameters.append(conversation_id)
        with self.db.connect() as connection:
            if cursor is not None:
                anchor = connection.execute("SELECT created_at,conversation_id FROM query_runs WHERE id=?", (cursor,)).fetchone()
                if not anchor or (conversation_id is not None and anchor["conversation_id"] != conversation_id):
                    raise ApiError("invalid_query_cursor", "Cette page d’historique n’est plus disponible. Rechargez la liste.")
                clauses.append("(created_at<? OR (created_at=? AND id<?))")
                parameters.extend([anchor["created_at"], anchor["created_at"], cursor])
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = connection.execute("SELECT id,conversation_id,question,state,last_event_id,created_at,updated_at FROM query_runs"
                                      + where + " ORDER BY created_at DESC,id DESC LIMIT ?", (*parameters, limit + 1)).fetchall()
        page = rows[:limit]
        return {"queries": [self.history_summary(row) for row in page],
                "next_cursor": page[-1]["id"] if len(rows) > limit else None}

    def run_detail(self, query_id):
        row = self.db.one("SELECT id,conversation_id,question,scope_json,state,answer,warnings_json,metrics_json,"
                          "resolution_json,last_event_id,created_at,updated_at FROM query_runs WHERE id=?", (query_id,))
        if not row:
            raise ApiError("query_not_found", "Question inconnue.", 404)
        # The mode was not persisted. Metrics/text are not an authority for reconstructing it.
        return {**self.history_summary(row), "scope": json.loads(row["scope_json"]), "answer": row["answer"],
                "warnings": json.loads(row["warnings_json"]), "metrics": json.loads(row["metrics_json"]),
                "resolution": json.loads(row["resolution_json"])}

    def create(self, request):
        return self.start_query(self.prepare_query(request))

    async def create_async(self, request):
        # Sérialisation de l'admission : deux threads ne doivent pas dépasser ensemble la borne de file.
        async with self.creation_lock:
            prepared = []

            def prepare():
                prepared.append(self.prepare_query(request))

            try:
                await database_call(prepare)
            except asyncio.CancelledError:
                if prepared:
                    await database_call(self.mark_cancelled, prepared[0][0]["query_id"])
                raise
            return self.start_query(prepared[0])

    def prepare_query(self, request):
        pending = self.db.one("SELECT count(*) AS n FROM query_runs WHERE state IN ('queued','running')")["n"]
        if pending >= 1 + self.settings.value("llm", "max_pending_generations", 2):
            raise ApiError("query_queue_full", "La file de questions est pleine.", 429)
        snapshot = self.resolver.resolve(request.scope, request.mode)
        effective_question, resolution, choices, references = self.resolve_followup(request, snapshot)
        query_id = uid()
        conversation_id = request.conversation_id
        with self.db.transaction() as connection:
            if conversation_id and not connection.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
                raise ApiError("conversation_not_found", "Conversation inconnue.", 404)
            if not conversation_id:
                conversation_id = uid()
                connection.execute("INSERT INTO conversations VALUES(?,?)", (conversation_id, now()))
            state = "needs_clarification" if choices else "queued"
            connection.execute("INSERT INTO query_runs(id,conversation_id,question,scope_json,snapshot_json,state,resolution_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (query_id, conversation_id, request.question, json_dump(request.scope.model_dump()), json_dump(snapshot.as_dict()), state, json_dump(resolution), now(), now()))
            connection.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (uid(), conversation_id, query_id, "user", request.question, now()))
        if choices:
            self.db.add_event(query_id, "needs_clarification", {"state": "needs_clarification", "message": "Choisir la référence visée avant de poursuivre.", "choices": choices})
        response = {"query_id": query_id, "conversation_id": conversation_id, "events_url": f"/api/v1/queries/{query_id}/events"}
        if choices:
            response["state"] = "needs_clarification"
        resolved_request = request.model_copy(update={"question": effective_question})
        return response, resolved_request, snapshot, references

    def start_query(self, prepared):
        response, resolved_request, snapshot, references = prepared
        if response.get("state") == "needs_clarification":
            return response
        query_id = response["query_id"]
        event = asyncio.Event()
        self.cancel_events[query_id] = event
        task = asyncio.create_task(self.run(query_id, resolved_request, snapshot, event, references))
        self.tasks[query_id] = task
        task.add_done_callback(lambda finished: self.forget(query_id))
        return response

    def forget(self, query_id):
        # Appelé aussi pour une tâche annulée avant son démarrage, dont le finally de run() ne s'exécute jamais.
        self.tasks.pop(query_id, None)
        self.cancel_events.pop(query_id, None)
        self.started.discard(query_id)

    @asynccontextmanager
    async def generation_turn(self, query_id):
        # Réserve le tour avant le premier déport SQLite : la vitesse du disque ne réordonne pas les questions.
        acquisition = asyncio.create_task(self.generation_lock.acquire())
        acquired = False
        try:
            await database_call(self.db.add_event, query_id, "status", {"state": "queued"})
            if self.governor and self.governor.snapshot().get("heavy_owner") == "ingestion":
                await database_call(self.db.add_event, query_id, "status", {"state": "waiting_for_ingestion_checkpoint"})
            await acquisition
            acquired = True
            yield
        finally:
            if not acquired:
                acquisition.cancel()
                while not acquisition.done():
                    try:
                        await asyncio.shield(acquisition)
                    except asyncio.CancelledError:
                        continue
                acquired = not acquisition.cancelled() and acquisition.result()
            if acquired:
                self.generation_lock.release()

    def resolve_followup(self, request, snapshot, prior_user_questions=None, *, allow_implicit=True):
        def resolved(question, resolution, choices):
            focus = resolution.get("focus", {})
            origin = "focus.identifier" if resolution["method"] == "explicit_focus" else "previous_user_referent"
            references = resolve_references(request.question, focus.get("identifier"), origin)
            resolution["reference_resolution"] = references.as_dict()
            return question, resolution, choices, references

        resolution = {"method": "explicit_question", "history_is_evidence": False}
        focus = request.focus or {}
        if focus:
            if "source_id" in focus:
                reference_query = focus.get("query_id") or request.followup_of
                referenced_run = self.db.one("SELECT conversation_id FROM query_runs WHERE id=?", (reference_query,))
                if not referenced_run or (request.conversation_id and referenced_run["conversation_id"] != request.conversation_id):
                    raise ApiError("focus_not_found", "Le focus n'appartient pas à cette conversation.", 404)
                source_row = self.db.one("SELECT source_json FROM citations WHERE query_id=? AND source_id=?", (reference_query, focus["source_id"]))
                if not source_row:
                    raise ApiError("focus_not_found", "Référence de focus inconnue.", 404)
                source = json.loads(source_row["source_json"])
                if source["generation_id"] not in snapshot.generations:
                    raise ApiError("focus_outside_scope", "Cette référence n'est plus autorisée dans le périmètre.", 409)
                if snapshot.scope["kind"] == "cell_range":
                    scope = snapshot.scope
                    ranges = []
                    for source_block in source.get("blocks", []):
                        locator = source_block.get("locator", {})
                        if (locator.get("sheet_id") != scope["sheetId"]
                                or not scope["rowStart"] <= locator.get("row_start", 0) <= locator.get("row_end", 0) <= scope["rowEnd"]
                                or not scope["columnStart"] <= locator.get("column_start", 0) <= locator.get("column_end", 0) <= scope["columnEnd"]):
                            raise ApiError("focus_outside_scope", "La citation ciblée comporte des cellules hors de cette plage.", 409)
                        ranges.append({key: locator[key] for key in ("row_start", "row_end", "column_start", "column_end")})
                    if not ranges:
                        raise ApiError("focus_outside_scope", "Cette citation ne possède pas de cellules autorisées.", 409)
                    snapshot.cell_ranges = ranges
                focus = {**focus, "version_id": source["version_id"], "block_id": source["block_ids"][0]}
            if "version_id" in focus:
                generations = [generation for generation in snapshot.generations if snapshot.versions[generation] == focus["version_id"]]
                if not generations:
                    raise ApiError("focus_outside_scope", "Version de focus hors périmètre.", 409)
                if "block_id" in focus:
                    block = self.db.one("SELECT page_index FROM blocks WHERE generation_id=? AND id=?", (generations[0], focus["block_id"]))
                    if not block or (snapshot.page_indices is not None and block["page_index"] not in snapshot.page_indices) or (snapshot.block_ids is not None and focus["block_id"] not in snapshot.block_ids):
                        raise ApiError("focus_outside_scope", "Bloc de focus hors périmètre.", 409)
                    snapshot.block_ids = [focus["block_id"]]
                snapshot.generations = generations
                snapshot.versions = {generation: snapshot.versions[generation] for generation in generations}
                snapshot.documents = {generation: snapshot.documents[generation] for generation in generations}
            resolution = {"method": "explicit_focus", "focus": focus, "history_is_evidence": False}
            return resolved(request.question + ("\nRéférence ciblée : " + focus["identifier"] if "identifier" in focus else ""), resolution, [])
        if not allow_implicit or identifiers(request.question) or (not request.conversation_id and not prior_user_questions):
            return resolved(request.question, resolution, [])
        followup = bool(request.followup_of) or bool(re.search(r"(?i)\b(?:elle|celui|celle|son|sa|ses|leur|its|it|this|that)\b", request.question))
        if not followup:
            return resolved(request.question, resolution, [])
        rows = prior_user_questions if prior_user_questions is not None else self.db.rows("SELECT id,question,snapshot_json FROM query_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 8", (request.conversation_id,))
        if request.followup_of:
            rows = [row for row in rows if row["id"] == request.followup_of]
            if not rows:
                raise ApiError("followup_not_found", "Question de suivi inconnue dans cette conversation.", 404)
        choices: list[dict[str, Any]] = []
        for row in rows:
            previous = json.loads(row["snapshot_json"])
            if snapshot.cell_ranges is not None and previous.get("cell_ranges") != snapshot.cell_ranges:
                continue
            if not set(previous.get("generations", [])) & set(snapshot.generations):
                continue
            for code in identifiers(row["question"]):
                if code not in {choice["identifier"] for choice in choices} and self.search.lexical(code, snapshot)[1]:
                    choices.append({"identifier": code, "query_id": row["id"], "label": code})
            if choices:
                break
        if len(choices) == 1:
            return resolved(request.question + "\nRéférence utilisateur précédente : " + choices[0]["identifier"], {"method": "unique_user_referent", "focus": choices[0], "history_is_evidence": False}, [])
        if len(choices) > 1:
            return resolved(request.question, {"method": "ambiguous_user_referent", "history_is_evidence": False}, choices[:4])
        return resolved(request.question, {"method": "no_authorized_referent", "history_is_evidence": False}, [])

    def register_sources(self, query_id, sources):
        prepared = []
        with self.db.transaction() as connection:
            for source in sources:
                version = self.db.version(source["version_id"])
                item = dict(source)
                item.update({"query_id": query_id, "name": version["document_name"], "document_name": version["document_name"],
                             "page_index": source["page_indices"][0] if source["page_indices"] else None, "page_number": source["page_indices"][0] + 1 if source["page_indices"] else None,
                             "label": source["blocks"][0]["page"].get("label"), "block_ids": [block["id"] for block in source["blocks"]],
                             "bboxes": [block["bbox"] for block in source["blocks"] if block.get("bbox")],
                             "precision": "page" if not any(block.get("bbox") for block in source["blocks"]) else "block",
                             "citation_url": f"/api/v1/citations/{query_id}/{source['source_id']}"})
                if version["format"] != "pdf":
                    item.update({"format": version["format"], "locator": source.get("locator") or source["blocks"][0].get("locator"),
                                 "precision": source.get("precision", source["blocks"][0].get("precision", "element"))})
                connection.execute("INSERT INTO citations VALUES(?,?,?,?,?)", (query_id, item["source_id"], item["version_id"], item["document_id"], json_dump(item)))
                prepared.append(item)
        return prepared

    def authorized_history(self, query_id, request, snapshot):
        requested_scope = json_dump(request.scope.model_dump())
        rows = self.db.rows("SELECT m.role,m.content,q.scope_json,q.snapshot_json FROM messages m JOIN query_runs q ON q.id=m.query_id WHERE m.conversation_id=(SELECT conversation_id FROM query_runs WHERE id=?) AND m.query_id<>? ORDER BY m.created_at DESC LIMIT 24", (query_id, query_id))
        authorized = []
        for row in rows:
            if row["scope_json"] != requested_scope:
                continue
            previous = json.loads(row["snapshot_json"])
            if not set(previous.get("generations", [])) <= set(snapshot.generations):
                continue
            previous_documents = set(previous.get("documents", {}).values())
            if not previous_documents <= set(snapshot.documents.values()):
                continue
            authorized.append({"role": row["role"], "content": row["content"]})
        authorized.reverse()
        return authorized

    def mark_cancelled(self, query_id, answer="", metrics=None):
        """Un seul état terminal et un seul événement `cancelled`, quel que soit le chemin d'annulation."""
        metrics = metrics if metrics is not None else {"model_called": False}
        with self.db.transaction() as connection:
            row = connection.execute("SELECT state,last_event_id FROM query_runs WHERE id=?", (query_id,)).fetchone()
            if not row or row["state"] not in {"queued", "running"}:
                return False
            event_id = row["last_event_id"] + 1
            connection.execute("UPDATE query_runs SET state='cancelled',answer=?,metrics_json=?,last_event_id=?,updated_at=? WHERE id=?", (answer, json_dump(metrics), event_id, now(), query_id))
            connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, event_id, "cancelled", json_dump({"state": "cancelled", "status": "cancelled", "text": answer, "metrics": metrics}), now()))
        return True

    def finish(self, query_id, state, answer, warnings, metrics, event):
        """État, message et événement terminal publiés dans une seule transaction SQLite."""
        with self.db.transaction() as connection:
            row = connection.execute("SELECT conversation_id,last_event_id,cancel_requested FROM query_runs WHERE id=?", (query_id,)).fetchone()
            event_id = row["last_event_id"] + 1
            if row["cancel_requested"]:
                connection.execute("UPDATE query_runs SET state='cancelled',answer=?,metrics_json=?,last_event_id=?,updated_at=? WHERE id=?",
                                   (answer, json_dump(metrics), event_id, now(), query_id))
                connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, event_id, "cancelled",
                                   json_dump({"state": "cancelled", "status": "cancelled", "text": answer, "metrics": metrics}), now()))
                return
            connection.execute("UPDATE query_runs SET state=?,answer=?,warnings_json=?,metrics_json=?,updated_at=? WHERE id=?",
                               (state, answer, json_dump(warnings), json_dump(metrics), now(), query_id))
            connection.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (uid(), row["conversation_id"], query_id, "assistant", answer, now()))
            connection.execute("UPDATE query_runs SET last_event_id=? WHERE id=?", (event_id, query_id))
            connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, event_id, "done", json_dump(event), now()))

    def fail(self, query_id, answer, metrics, event):
        with self.db.transaction() as connection:
            row = connection.execute("SELECT last_event_id FROM query_runs WHERE id=?", (query_id,)).fetchone()
            event_id = row["last_event_id"] + 1
            connection.execute("UPDATE query_runs SET state='error',answer=?,metrics_json=?,last_event_id=?,updated_at=? WHERE id=?",
                               (answer, json_dump(metrics), event_id, now(), query_id))
            connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, event_id, "error", json_dump(event), now()))

    def capture_persisted_terminal(self, query_id, trace):
        """Observe le terminal commis, dans le worker que database_call termine avant fermeture de la trace.

        La lecture jointe voit l'état et son événement dans le même snapshot SQLite.
        Aucune écriture applicative : le résumé déjà publié reste celui pris avant
        confirmation, tandis que le fichier porte cette observation finale.
        """
        try:
            row = self.db.one(
                "SELECT q.state,q.last_event_id,e.type AS event_type,e.data_json FROM query_runs q "
                "LEFT JOIN events e ON e.query_id=q.id AND e.id=q.last_event_id WHERE q.id=?", (query_id,))
            expected = {"done": "done", "length_limited": "done", "cancelled": "cancelled", "error": "error"}
            if not row or expected.get(row["state"]) is None or row["event_type"] != expected[row["state"]]:
                trace.record("query.persistence_unconfirmed", {
                    "persistence_confirmed": False, "reason": "terminal_state_event_mismatch",
                    "state": row["state"] if row else None, "event_id": row["last_event_id"] if row else None,
                    "event_type": row["event_type"] if row else None}, required=False)
                return
            payload = json.loads(row["data_json"])
            if not isinstance(payload, dict) or any(
                    payload.get(key) not in {None, row["state"]} for key in ("state", "status")):
                trace.record("query.persistence_unconfirmed", {
                    "persistence_confirmed": False, "reason": "terminal_payload_mismatch",
                    "state": row["state"], "event_id": row["last_event_id"]}, required=False)
                return
        except Exception as error:
            # Une erreur d'observation ne remplace jamais celle de la requête ou
            # de sa persistance ; aucune erreur applicative n'est inventée ici.
            trace.record("query.persistence_unconfirmed", {
                "persistence_confirmed": False, "reason": "terminal_read_failed",
                "error_type": type(error).__name__}, required=False)
            return
        trace.record("query." + row["event_type"], {
            **payload, "state": row["state"], "event_id": row["last_event_id"],
            "persistence_confirmed": True}, required=False)

    async def run(self, query_id, request, snapshot, cancelled, references=None):
        references = references or resolve_references(request.question, (request.focus or {}).get("identifier"))
        self.started.add(query_id)
        started = time.perf_counter()
        first_token_at = None
        warnings = list(snapshot.warnings)
        answer = ""
        metrics: dict[str, Any] = {"model_called": False}
        sources = []
        finish_reason = "stop"
        catalogue: Catalogue | None = None
        deterministic_plan = None
        raw_structured = ""
        trace = None
        trace_token = None
        interactive_started = False
        try:
            trace = ExecutionTrace(self.settings, query_id)
            trace_token = CURRENT_TRACE.set(trace)
            if trace.mode != "off":
                def source_identities():
                    records = []
                    for generation in snapshot.generations:
                        records.append(self.db.one(
                            "SELECT g.id AS generation_id,g.fingerprint AS index_fingerprint,"
                            "g.extraction_revision_id,e.fingerprint AS extraction_fingerprint,e.source_hash,"
                            "v.id AS version_id,v.sha256 AS original_sha256,v.format "
                            "FROM index_generations g JOIN document_versions v ON v.id=g.version_id "
                            "LEFT JOIN extraction_revisions e ON e.id=g.extraction_revision_id WHERE g.id=?",
                            (generation,)))
                    return records

                record_event("query.start", {"query_id": query_id, "question": request.question, "mode": request.mode,
                             "scope_snapshot": snapshot.as_dict(), "profile_sha256": fingerprint(self.settings.profile),
                             "source_identities": await database_call(source_identities)})
            if self.governor:
                self.governor.begin_interactive()
                interactive_started = True
            async with self.generation_turn(query_id):
                metrics["queue_wait_ms"] = round((time.perf_counter() - started) * 1000, 2)
                if cancelled.is_set():
                    raise asyncio.CancelledError
                # Retrieval/abstention does not admit or load a language model.
                lease = empty_lease()
                async with lease:
                    allowed = await database_call(self.db.rows, "SELECT id FROM documents WHERE deleted_at IS NULL")
                    allowed_ids = {row["id"] for row in allowed}
                    if set(snapshot.documents.values()) - allowed_ids:
                        raise ApiError("scope_authorization_changed", "Un document du périmètre a été retiré pendant l'attente.", 409)
                    await database_call(self.db.execute, "UPDATE query_runs SET state='running',updated_at=? WHERE id=?", (now(), query_id))
                    await database_call(self.db.add_event, query_id, "status", {"state": "searching"})
                    search_result = await self.search.search(request.question, snapshot, request.mode, references)
                    record_event("retrieval", search_result)
                    metrics["retrieval_ms"] = search_result["elapsed_ms"]
                    metrics["evidence_selection"] = search_result.get("evidence_selection")
                    warnings.extend(search_result["warnings"])
                    if search_result["results"]:
                        search_result["results"] = await asyncio.to_thread(lambda: [source if source.get("evidence_bundle") else self.resolver.expand_parent(source, snapshot, self.context.tokenizer, self.settings.value("chunking", "parent_expand_max_llm_tokens", 900)) for source in search_result["results"]])
                        search_result["results"] = deduplicate_expanded_sources(search_result["results"])
                        history = await database_call(self.authorized_history, query_id, request, snapshot)
                        context_started = time.perf_counter()
                        # The authorized snapshot, rather than retrieval alone, selects the mixed-format contract.
                        has_xlsx = await database_call(lambda: any(self.db.version(version)["format"] == "xlsx"
                                                                 for version in set(snapshot.versions.values())))
                        enforce_contract = self.settings.value("enhanced", "answer_contract", False)
                        structured = (StructuredAnswerBuilder(self.db, snapshot, question=request.question, enforce_contract=True)
                                      if enforce_contract else StructuredAnswerBuilder(self.db, snapshot) if has_xlsx else None)
                        build_arguments = {"structured": structured} if structured is not None else {}
                        messages, retained, context_metrics, context_warnings = await asyncio.to_thread(
                            self.context.build, request.question, search_result["results"], request.mode, history, references, **build_arguments)
                        if structured is not None:
                            catalogue = await asyncio.to_thread(structured.catalogue, retained, request.mode)
                            if enforce_contract:
                                catalogue.retrieval_limitations = _retrieval_limitations(search_result, context_metrics)
                                required_documents = (list(dict.fromkeys(snapshot.documents.values()))
                                                      if snapshot.scope["kind"] == "documents" else ())
                                assessment = catalogue.assess(required_documents=required_documents)
                                if (assessment["status"] == "partial"
                                        and self.settings.value("enhanced", "complementary_retrieval", False)):
                                    record_event("context.initial", {"messages": messages, "retained": retained,
                                                 "metrics": context_metrics, "assessment": assessment})
                                    refined = await self.search.refine_once(
                                        request.question, snapshot, search_result, complementary_terms(assessment),
                                        request.mode, references)
                                    metrics["complementary_retrieval"] = refined["refinement"]
                                    record_event("retrieval.complementary", refined)
                                    if refined["refinement"].get("retained_new_evidence_count", 0):
                                        refined["results"] = await asyncio.to_thread(lambda: [
                                            source if source.get("evidence_bundle") else self.resolver.expand_parent(
                                                source, snapshot, self.context.tokenizer,
                                                self.settings.value("chunking", "parent_expand_max_llm_tokens", 900))
                                            for source in refined["results"]])
                                        refined["results"] = deduplicate_expanded_sources(refined["results"])
                                        messages, retained, context_metrics, context_warnings = await asyncio.to_thread(
                                            self.context.build, request.question, refined["results"], request.mode,
                                            history, references, **build_arguments)
                                        catalogue = await asyncio.to_thread(structured.catalogue, retained, request.mode)
                                        catalogue.retrieval_limitations = _retrieval_limitations(refined, context_metrics)
                                        metrics["context_assessment_initial"] = assessment
                                        assessment = catalogue.assess(required_documents=required_documents)
                                        metrics["evidence_selection"] = refined.get("evidence_selection")
                                        warnings = [item for item in warnings if item.get("code") != "evidence_coverage_incomplete"]
                                        warnings.extend(refined.get("warnings", []))
                                    metrics["retrieval_ms"] = refined["elapsed_ms"]
                                metrics["context_assessment"] = assessment
                            evidence = catalogue.evidence()
                            if enforce_contract:
                                record_event("evidence.ledger", {"ledger": evidence["support_ledger"],
                                             "sha256": evidence["support_ledger_sha256"]})
                            metrics["structured_answer"] = {"status": "pending", "schema_sha256": evidence["schema_sha256"],
                                                            "catalogue_sha256": evidence["catalogue_sha256"]}
                            if enforce_contract:
                                metrics["structured_answer"]["support_ledger_sha256"] = evidence["support_ledger_sha256"]
                            await database_call(self.db.add_event, query_id, "structured_answer", evidence)
                        metrics.update(context_metrics)
                        metrics["context_ms"] = round((time.perf_counter() - context_started) * 1000, 2)
                        warnings.extend(context_warnings)
                        record_event("context", {"messages": messages, "retained": retained, "metrics": context_metrics,
                                                 "assessment": metrics.get("context_assessment"), "warnings": context_warnings})
                        sources = await database_call(self.register_sources, query_id, retained)
                        # Provenance OCR des seules sources transmises au modèle : remplace celle des passages de la recherche.
                        warnings = [warning for warning in warnings if warning.get("code") != "ocr_evidence"] + ocr_evidence_warnings(sources)
                    else:
                        messages = []
                    metrics["reference_resolution"] = references.as_dict()
                    resolution_row = await database_call(self.db.one, "SELECT resolution_json FROM query_runs WHERE id=?", (query_id,))
                    resolution = json.loads(resolution_row["resolution_json"])
                    resolution["reference_resolution"] = references.as_dict()
                    await database_call(self.db.execute, "UPDATE query_runs SET resolution_json=? WHERE id=?", (json_dump(resolution), query_id))
                    await database_call(self.db.add_event, query_id, "sources", {"sources": sources})
                    for warning in warnings:
                        await database_call(self.db.add_event, query_id, "warning", warning)
                    if catalogue is not None and self.settings.value("enhanced", "answer_contract", False):
                        deterministic_plan = catalogue.deterministic_plan(
                            list(dict.fromkeys(snapshot.documents.values())) if snapshot.scope["kind"] == "documents"
                            else metrics.get("required_documents", ()))
                    if not sources or catalogue is not None and not catalogue.references:
                        if catalogue is not None:
                            metrics["structured_answer"]["status"] = "no_references"
                        answer = "Les preuves disponibles dans ce périmètre ne suffisent pas pour répondre à cette question."
                        metrics["model_called"] = False
                        await database_call(self.db.add_event, query_id, "delta", {"text": answer})
                    elif deterministic_plan is not None:
                        assert catalogue is not None
                        # Exact cell facts or an explicit scope mismatch are
                        # established by the authorized catalogue itself.
                        raw_structured = json_dump(deterministic_plan.model_dump())
                        scope_refusal = metrics.get("context_assessment", {}).get("scope_refusal")
                        metrics["response_route"] = ("deterministic_scope_refusal" if scope_refusal
                                                     else "deterministic_cell_contract" if catalogue.contract and catalogue.contract.requested_cells
                                                     else "deterministic_evidence_contract")
                        record_event("answer.deterministic_plan", {"plan": deterministic_plan.model_dump(),
                                     "scope_refusal": scope_refusal,
                                     "catalogue_sha256": metrics["structured_answer"]["catalogue_sha256"]})
                    else:
                        metrics["response_route"] = "local_4b_generation"
                        if self.governor and self.governor.snapshot().get("heavy_owner") == "ingestion":
                            await database_call(self.db.add_event, query_id, "status", {"state": "waiting_for_ingestion_checkpoint"})
                        awaited = False
                        async def waiting(sample):
                            # Appelée par l'admission du bail et par la nouvelle admission d'un repli sur CPU.
                            nonlocal awaited
                            awaited = True
                            admission = sample.get("admission") or {}
                            record_event("admission.wait", sample, required=False)
                            await database_call(self.db.add_event, query_id, "status", {"state": "waiting_for_resources",
                                                                                        "available_mib": sample.get("available_mib"),
                                                                                        "required_mib": admission.get("required_available_mib")})
                        generation_lease = self.governor.generation(on_wait=waiting) if self.governor else empty_lease()
                        admission_started = time.perf_counter()
                        async with generation_lease:
                            metrics["generation_admission_wait_ms"] = round((time.perf_counter() - admission_started) * 1000, 2)
                            if self.governor:
                                record_event("admission.granted", self.governor.snapshot())
                            allowed_ids = {row["id"] for row in await database_call(self.db.rows, "SELECT id FROM documents WHERE deleted_at IS NULL")}
                            if set(snapshot.documents.values()) - allowed_ids:
                                raise ApiError("scope_authorization_changed", "Un document a été retiré pendant l'attente ; nouveau contexte refusé.", 409)
                            await database_call(self.db.add_event, query_id, "status", {"state": "generating"})
                            awaited = False
                            metrics["model_call_attempted"] = True
                            format_arguments = {"response_format": catalogue.schema()} if catalogue is not None else {}
                            async for event in self.ollama.stream(messages, cancelled, metrics.get("output_tokens"), **format_arguments):
                                if event["type"] == "cpu_fallback":
                                    # Repli sur CPU admis : après une attente de mémoire, la génération reprend.
                                    if awaited:
                                        awaited = False
                                        await database_call(self.db.add_event, query_id, "status", {"state": "generating"})
                                    continue
                                metrics["model_called"] = True
                                if cancelled.is_set():
                                    raise asyncio.CancelledError
                                if event["type"] == "delta":
                                    first_token_at = first_token_at or time.perf_counter()
                                    if catalogue is not None:
                                        # Audit only: the public SSE route excludes this event type.
                                        raw_structured += event["text"]
                                        await database_call(self.db.add_event, query_id, "structured_delta", {"text": event["text"]})
                                        if len(raw_structured.encode()) > 131_072:
                                            raise ApiError("structured_answer_invalid", "Le plan généré dépasse la limite de restitution structurée.", 503)
                                    else:
                                        answer += event["text"]
                                        await database_call(self.db.add_event, query_id, "delta", {"text": event["text"]})
                                else:
                                    metrics.update(event["metrics"])
                                    finish_reason = event["finish_reason"]
                            residency = getattr(self.ollama, "last_residency", None)
                            if residency is not None:
                                metrics["residency"] = residency
                    max_input = self.settings.value("llm", "num_ctx", 8192) - self.settings.value("llm", "num_predict", 768) - self.settings.value("retrieval", "context_safety_tokens", 256)
                    if isinstance(metrics.get("prompt_eval_count"), int) and metrics["prompt_eval_count"] > max_input:
                        raise ApiError("runtime_context_exceeded", "Le runtime a dépassé le budget de contexte réel.", 503)
                    if isinstance(metrics.get("prompt_eval_count"), int):
                        difference = metrics["prompt_eval_count"] - metrics.get("local_prompt_tokens", 0)
                        metrics["tokenizer_count_difference"] = difference
                        if abs(difference) > self.settings.value("retrieval", "context_safety_tokens", 256):
                            warnings.append({"code": "tokenizer_template_drift", "difference": difference, "message": "Les comptes de tokens du modèle et du compteur local diffèrent. Vérifiez la configuration du modèle."})
                    structured_result = None
                    structured_cited = None
                    if catalogue is not None and (metrics.get("model_called") or deterministic_plan is not None):
                        if finish_reason == "length":
                            metrics["structured_answer"]["status"] = "incomplete"
                            if self.settings.value("enhanced", "answer_contract", False):
                                raise ApiError("structured_answer_incomplete", "Le plan a atteint sa limite avant validation ; aucun texte non vérifié n'est publié.", 503)
                        elif finish_reason != "stop":
                            raise ApiError("structured_answer_invalid", "Le plan généré n'a pas de fin complète vérifiable.", 503)
                        else:
                            plan = catalogue.validate(raw_structured)
                            rendered = catalogue.render(
                                plan, self.context.tokenizer, metrics["output_tokens"],
                                list(dict.fromkeys(snapshot.documents.values())) if snapshot.scope["kind"] == "documents"
                                else metrics.get("required_documents", ()))
                            if self.settings.value("enhanced", "answer_contract", False):
                                support_validation = catalogue.verify_rendered(rendered)
                                record_event("answer.support_validation", support_validation)
                                metrics["answer_support_validation"] = support_validation
                            structured_cited = rendered["source_ids"]
                            structured_result = {"status": "validated", "plan": plan.model_dump(),
                                                 "plan_origin": "deterministic_contract" if deterministic_plan is not None else "model",
                                                 "schema_sha256": metrics["structured_answer"]["schema_sha256"],
                                                 "catalogue_sha256": metrics["structured_answer"]["catalogue_sha256"],
                                                 "rendered_tokens": rendered["tokens"], "citation_spans": rendered["citation_spans"]}
                            if "support_ledger_sha256" in metrics["structured_answer"]:
                                structured_result["support_ledger_sha256"] = metrics["structured_answer"]["support_ledger_sha256"]
                                structured_result["rendered_support_ledger_sha256"] = rendered["support_ledger_sha256"]
                            if "answer_contract" in rendered:
                                structured_result["answer_contract"] = rendered["answer_contract"]
                                structured_result["effective_plan"] = rendered.get("effective_plan")
                            await database_call(self.db.add_event, query_id, "structured_answer", structured_result)
                            metrics["structured_answer"] = {key: value for key, value in structured_result.items() if key not in {"plan", "citation_spans"}}
                            warnings.extend(rendered["warnings"])
                            if cancelled.is_set():
                                raise asyncio.CancelledError
                            answer = rendered["text"]
                            await database_call(self.db.add_event, query_id, "delta", {"text": answer, "citation_spans": rendered["citation_spans"]})
                    if catalogue is None:
                        answer, validation_warnings = validate_answer(answer, [source["source_id"] for source in sources])
                    else:
                        validation_warnings = []
                    warnings.extend(validation_warnings)
                    state = "length_limited" if finish_reason == "length" else "done"
                    if state == "length_limited":
                        warnings.append({"code": "answer_length_limit", "message": "Limite de génération atteinte ; réponse incomplète."})
                    metrics.update({"elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                    "ttft_ms": round((first_token_at - started) * 1000, 2) if first_token_at else None})
                    cited_ids = set(structured_cited) if structured_cited is not None else set(re.findall(r"\[(S\d+)\]", answer))
                    citations = [source for source in sources if source["source_id"] in cited_ids]
                    if metrics.get("model_called") and sources and catalogue is None:
                        # Signaux seulement (R26-ANS-01/02) : texte, citations et événements déjà émis restent inchangés.
                        warnings.extend(answer_warnings(answer, sources, request.question))
                    terminal = {"message": answer, "text": answer, "status": state, "citations": citations,
                                "finish_reason": finish_reason, "metrics": metrics, "warnings": warnings}
                    record_event("query.done_intent", {"intended_state": state, "finish_reason": finish_reason}, required=False)
                    if trace.mode != "off":
                        metrics["execution_trace"] = {**trace.summary(), "snapshot_stage": "before_terminal_persistence"}
                    if catalogue is not None:
                        terminal["structured_answer"] = structured_result or metrics["structured_answer"]
                    await database_call(self.finish, query_id, state, answer, warnings, metrics, terminal)
        except asyncio.CancelledError:
            record_event("query.cancelled_intent", {"intended_state": "cancelled"}, required=False)
            if catalogue is not None and metrics.get("structured_answer", {}).get("status") == "pending":
                metrics["structured_answer"]["status"] = "cancelled"
            metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            if trace is not None and trace.mode != "off":
                metrics["execution_trace"] = {**trace.summary(), "snapshot_stage": "before_terminal_persistence"}
            await database_call(self.mark_cancelled, query_id, answer, metrics)
        except Exception as error:
            if catalogue is not None and metrics.get("structured_answer", {}).get("status") == "pending":
                metrics["structured_answer"]["status"] = "invalid"
            admission_failure = error.__class__.__name__ == "ResourceAdmissionError"
            code = error.code if isinstance(error, ApiError) else ("resource_admission_denied" if admission_failure else "query_failed")
            message = error.message if isinstance(error, ApiError) else (str(error) if admission_failure else
                "La question n'a pas pu être traitée. Renvoyez-la ; si l'erreur se reproduit, "
                f"exécutez {launcher_instruction('logs')} pour trouver le journal du service local.")
            metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            record_event("query.error_intent", {"intended_state": "error", "code": code, "message": message}, required=False)
            if trace is not None and trace.mode != "off":
                metrics["execution_trace"] = {**trace.summary(), "snapshot_stage": "before_terminal_persistence"}
            await database_call(self.fail, query_id, answer, metrics, {"code": code, "message": message, "metrics": metrics})
        finally:
            if trace is not None and trace.mode != "off":
                try:
                    await database_call(self.capture_persisted_terminal, query_id, trace)
                except asyncio.CancelledError:
                    # database_call a terminé le worker, y compris sa capture.
                    # Une annulation tardive ne change pas un terminal déjà commis.
                    pass
                except Exception as error:
                    trace.record("query.persistence_unconfirmed", {
                        "persistence_confirmed": False, "reason": "terminal_observer_failed",
                        "error_type": type(error).__name__}, required=False)
            if trace_token is not None:
                CURRENT_TRACE.reset(trace_token)
            if trace is not None:
                trace.close()
            self.cancel_events.pop(query_id, None)
            if self.governor and interactive_started:
                self.governor.finish_interactive()

    def request_cancellation(self, query_id):
        with self.db.transaction() as connection:
            query = connection.execute("SELECT state FROM query_runs WHERE id=?", (query_id,)).fetchone()
            if not query:
                raise ApiError("query_not_found", "Question inconnue.", 404)
            connection.execute("UPDATE query_runs SET cancel_requested=1 WHERE id=?", (query_id,))
            return query["state"]

    def signal_cancellation(self, query_id, state):
        event = self.cancel_events.get(query_id)
        if event:
            event.set()
        task = self.tasks.get(query_id)
        if task:
            task.cancel()
        return {"query_id": query_id, "state": "cancel_requested" if task else state}, bool(task and query_id not in self.started)

    def cancel(self, query_id):
        response, unstarted = self.signal_cancellation(query_id, self.request_cancellation(query_id))
        if unstarted:
            self.mark_cancelled(query_id)
        return response

    async def cancel_async(self, query_id):
        persisted = []

        def persist():
            persisted.append(self.request_cancellation(query_id))

        try:
            await database_call(persist)
        except asyncio.CancelledError:
            if persisted:
                _, unstarted = self.signal_cancellation(query_id, persisted[0])
                if unstarted:
                    await database_call(self.mark_cancelled, query_id)
            raise
        state = persisted[0]
        response, unstarted = self.signal_cancellation(query_id, state)
        if unstarted:
            await database_call(self.mark_cancelled, query_id)
        return response

    async def close(self):
        for query_id in list(self.tasks):
            await self.cancel_async(query_id)
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
