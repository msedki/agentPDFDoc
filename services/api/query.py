import asyncio
from contextlib import asynccontextmanager
import json
import re
import time

from .context import validate_answer
from .db import json_dump, now, uid
from .errors import ApiError
from .retrieval import identifiers, contains_identifier


@asynccontextmanager
async def empty_lease():
    yield


class QueryService:
    def __init__(self, db, resolver, search, context, ollama, settings, governor=None):
        self.db, self.resolver, self.search, self.context, self.ollama, self.settings = db, resolver, search, context, ollama, settings
        self.governor = governor
        self.tasks = {}
        self.cancel_events = {}
        self.generation_lock = asyncio.Lock()

    def create(self, request):
        pending = self.db.one("SELECT count(*) AS n FROM query_runs WHERE state IN ('queued','running')")["n"]
        if pending >= 1 + self.settings.value("llm", "max_pending_generations", 2):
            raise ApiError("query_queue_full", "La file de questions est pleine.", 429)
        snapshot = self.resolver.resolve(request.scope)
        effective_question, resolution, choices = self.resolve_followup(request, snapshot)
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
            return {"query_id": query_id, "conversation_id": conversation_id, "events_url": f"/api/v1/queries/{query_id}/events", "state": "needs_clarification"}
        resolved_request = request.model_copy(update={"question": effective_question})
        event = asyncio.Event()
        self.cancel_events[query_id] = event
        task = asyncio.create_task(self.run(query_id, resolved_request, snapshot, event))
        self.tasks[query_id] = task
        task.add_done_callback(lambda finished: self.tasks.pop(query_id, None))
        return {"query_id": query_id, "conversation_id": conversation_id, "events_url": f"/api/v1/queries/{query_id}/events"}

    def resolve_followup(self, request, snapshot, prior_user_questions=None):
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
            return request.question + ("\nRéférence ciblée : " + focus["identifier"] if "identifier" in focus else ""), resolution, []
        if identifiers(request.question) or (not request.conversation_id and not prior_user_questions):
            return request.question, resolution, []
        followup = bool(request.followup_of) or bool(re.search(r"(?i)\b(?:elle|celui|celle|son|sa|ses|leur|its|it|this|that)\b", request.question))
        if not followup:
            return request.question, resolution, []
        rows = prior_user_questions if prior_user_questions is not None else self.db.rows("SELECT id,question,snapshot_json FROM query_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 8", (request.conversation_id,))
        if request.followup_of:
            rows = [row for row in rows if row["id"] == request.followup_of]
            if not rows:
                raise ApiError("followup_not_found", "Question de suivi inconnue dans cette conversation.", 404)
        choices = []
        for row in rows:
            previous = json.loads(row["snapshot_json"])
            if not set(previous.get("generations", [])) & set(snapshot.generations):
                continue
            for code in identifiers(row["question"]):
                if code not in {choice["identifier"] for choice in choices} and self.search.lexical(code, snapshot)[1]:
                    choices.append({"identifier": code, "query_id": row["id"], "label": code})
            if choices:
                break
        if len(choices) == 1:
            return request.question + "\nRéférence utilisateur précédente : " + choices[0]["identifier"], {"method": "unique_user_referent", "focus": choices[0], "history_is_evidence": False}, []
        if len(choices) > 1:
            return request.question, {"method": "ambiguous_user_referent", "history_is_evidence": False}, choices[:4]
        return request.question, {"method": "no_authorized_referent", "history_is_evidence": False}, []

    def register_sources(self, query_id, sources):
        prepared = []
        with self.db.transaction() as connection:
            for source in sources:
                version = self.db.version(source["version_id"])
                item = dict(source)
                item.update({"query_id": query_id, "name": version["document_name"], "document_name": version["document_name"],
                             "page_index": source["page_indices"][0], "page_number": source["page_indices"][0] + 1,
                             "label": source["blocks"][0]["page"].get("label"), "block_ids": [block["id"] for block in source["blocks"]],
                             "bboxes": [block["bbox"] for block in source["blocks"] if block.get("bbox")],
                             "precision": "page" if not any(block.get("bbox") for block in source["blocks"]) else "block",
                             "citation_url": f"/api/v1/citations/{query_id}/{source['source_id']}"})
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

    async def run(self, query_id, request, snapshot, cancelled):
        started = time.perf_counter()
        first_token_at = None
        warnings = []
        answer = ""
        metrics = {"model_called": False}
        sources = []
        finish_reason = "stop"
        try:
            self.db.add_event(query_id, "status", {"state": "queued"})
            if self.governor:
                self.governor.begin_interactive()
                if self.governor.snapshot().get("heavy_owner") == "ingestion":
                    self.db.add_event(query_id, "status", {"state": "waiting_for_ingestion_checkpoint"})
            async with self.generation_lock:
                metrics["queue_wait_ms"] = round((time.perf_counter() - started) * 1000, 2)
                if cancelled.is_set():
                    raise asyncio.CancelledError
                # Retrieval/abstention does not admit or load a language model.
                lease = empty_lease()
                async with lease:
                    allowed = self.db.rows("SELECT id FROM documents WHERE deleted_at IS NULL")
                    allowed_ids = {row["id"] for row in allowed}
                    if set(snapshot.documents.values()) - allowed_ids:
                        raise ApiError("scope_authorization_changed", "Un document du périmètre a été retiré pendant l'attente.", 409)
                    self.db.execute("UPDATE query_runs SET state='running',updated_at=? WHERE id=?", (now(), query_id))
                    self.db.add_event(query_id, "status", {"state": "searching"})
                    search_result = await self.search.search(request.question, snapshot, request.mode)
                    metrics["retrieval_ms"] = search_result["elapsed_ms"]
                    warnings.extend(search_result["warnings"])
                    if search_result["results"]:
                        search_result["results"] = await asyncio.to_thread(lambda: [self.resolver.expand_parent(source, snapshot, self.context.tokenizer, self.settings.value("chunking", "parent_expand_max_llm_tokens", 900)) for source in search_result["results"]])
                        history = self.authorized_history(query_id, request, snapshot)
                        context_started = time.perf_counter()
                        messages, retained, context_metrics, context_warnings = await asyncio.to_thread(self.context.build, request.question, search_result["results"], request.mode, history)
                        metrics.update(context_metrics)
                        metrics["context_ms"] = round((time.perf_counter() - context_started) * 1000, 2)
                        warnings.extend(context_warnings)
                        sources = self.register_sources(query_id, retained)
                    else:
                        messages = []
                    self.db.add_event(query_id, "sources", {"sources": sources})
                    for warning in warnings:
                        self.db.add_event(query_id, "warning", warning)
                    if not sources:
                        answer = "Les preuves disponibles dans ce périmètre ne suffisent pas pour répondre à cette question."
                        metrics["model_called"] = False
                        self.db.add_event(query_id, "delta", {"text": answer})
                    else:
                        if self.governor and self.governor.snapshot().get("heavy_owner") == "ingestion":
                            self.db.add_event(query_id, "status", {"state": "waiting_for_ingestion_checkpoint"})
                        generation_lease = self.governor.generation() if self.governor else empty_lease()
                        admission_started = time.perf_counter()
                        async with generation_lease:
                            metrics["generation_admission_wait_ms"] = round((time.perf_counter() - admission_started) * 1000, 2)
                            allowed_ids = {row["id"] for row in self.db.rows("SELECT id FROM documents WHERE deleted_at IS NULL")}
                            if set(snapshot.documents.values()) - allowed_ids:
                                raise ApiError("scope_authorization_changed", "Un document a été retiré pendant l'attente ; nouveau contexte refusé.", 409)
                            self.db.add_event(query_id, "status", {"state": "generating"})
                            metrics["model_call_attempted"] = True
                            async for event in self.ollama.stream(messages, cancelled, metrics.get("output_tokens")):
                                metrics["model_called"] = True
                                if cancelled.is_set():
                                    raise asyncio.CancelledError
                                if event["type"] == "delta":
                                    first_token_at = first_token_at or time.perf_counter()
                                    answer += event["text"]
                                    self.db.add_event(query_id, "delta", {"text": event["text"]})
                                else:
                                    metrics.update(event["metrics"])
                                    finish_reason = event["finish_reason"]
                    max_input = self.settings.value("llm", "num_ctx", 8192) - self.settings.value("llm", "num_predict", 768) - self.settings.value("retrieval", "context_safety_tokens", 256)
                    if isinstance(metrics.get("prompt_eval_count"), int) and metrics["prompt_eval_count"] > max_input:
                        raise ApiError("runtime_context_exceeded", "Le runtime a dépassé le budget de contexte réel.", 503)
                    if isinstance(metrics.get("prompt_eval_count"), int):
                        difference = metrics["prompt_eval_count"] - metrics.get("local_prompt_tokens", 0)
                        metrics["tokenizer_count_difference"] = difference
                        if abs(difference) > self.settings.value("retrieval", "context_safety_tokens", 256):
                            warnings.append({"code": "tokenizer_template_drift", "difference": difference, "message": "Écart entre le compteur local et le runtime ; template à vérifier."})
                    answer, validation_warnings = validate_answer(answer, [source["source_id"] for source in sources])
                    warnings.extend(validation_warnings)
                    state = "length_limited" if finish_reason == "length" else "done"
                    if state == "length_limited":
                        warnings.append({"code": "answer_length_limit", "message": "Limite de génération atteinte ; réponse incomplète."})
                    metrics.update({"elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                    "ttft_ms": round((first_token_at - started) * 1000, 2) if first_token_at else None})
                    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
                    citations = [source for source in sources if source["source_id"] in cited_ids]
                    with self.db.transaction() as connection:
                        connection.execute("UPDATE query_runs SET state=?,answer=?,warnings_json=?,metrics_json=?,updated_at=? WHERE id=?", (state, answer, json_dump(warnings), json_dump(metrics), now(), query_id))
                        conversation_id = connection.execute("SELECT conversation_id FROM query_runs WHERE id=?", (query_id,)).fetchone()[0]
                        connection.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (uid(), conversation_id, query_id, "assistant", answer, now()))
                    self.db.add_event(query_id, "done", {"message": answer, "text": answer, "status": state, "citations": citations, "finish_reason": finish_reason, "metrics": metrics, "warnings": warnings})
        except asyncio.CancelledError:
            metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self.db.execute("UPDATE query_runs SET state='cancelled',answer=?,metrics_json=?,updated_at=? WHERE id=?", (answer, json_dump(metrics), now(), query_id))
            self.db.add_event(query_id, "cancelled", {"status": "cancelled", "text": answer, "metrics": metrics})
        except Exception as error:
            admission_failure = error.__class__.__name__ == "ResourceAdmissionError"
            code = error.code if isinstance(error, ApiError) else ("resource_admission_denied" if admission_failure else "query_failed")
            message = error.message if isinstance(error, ApiError) else (str(error) if admission_failure else "La question a échoué ; consulter les diagnostics locaux.")
            metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self.db.execute("UPDATE query_runs SET state='error',answer=?,metrics_json=?,updated_at=? WHERE id=?", (answer, json_dump(metrics), now(), query_id))
            self.db.add_event(query_id, "error", {"code": code, "message": message, "metrics": metrics})
        finally:
            self.cancel_events.pop(query_id, None)
            if self.governor:
                self.governor.finish_interactive()

    def cancel(self, query_id):
        query = self.db.one("SELECT state FROM query_runs WHERE id=?", (query_id,))
        if not query:
            raise ApiError("query_not_found", "Question inconnue.", 404)
        self.db.execute("UPDATE query_runs SET cancel_requested=1 WHERE id=?", (query_id,))
        event = self.cancel_events.get(query_id)
        if event:
            event.set()
        task = self.tasks.get(query_id)
        if task:
            task.cancel()
            if query["state"] == "queued":
                self.db.execute("UPDATE query_runs SET state='cancelled',updated_at=? WHERE id=?", (now(), query_id))
                self.db.add_event(query_id, "cancelled", {"state": "cancelled"})
        return {"query_id": query_id, "state": "cancel_requested" if task else query["state"]}

    async def close(self):
        for query_id in list(self.tasks):
            self.cancel(query_id)
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
