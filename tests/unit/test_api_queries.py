import asyncio
import json
import threading

import pytest
from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.db import json_dump, now, uid
from services.api.errors import ApiError
from services.api.query import QueryService
from services.api.retrieval import SearchService
from services.api.schemas import QueryRequest, Scope
from services.api.scope import ScopeResolver
from services.runtime.resources import ResourceAdmissionError


def previous_question(db, conversation, question, snapshot):
    query_id = uid()
    db.execute("INSERT INTO query_runs(id,conversation_id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,?,'done',?,?)", (query_id, conversation, question, "{}", json_dump(snapshot.as_dict()), now(), now()))
    return query_id


def query_fixture(storage, question, *, text="CCU-21 tension 72 V et CCU-22 tension 110 V"):
    imported, _ = import_fixture(storage, text=text)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="library"))
    conversation = uid()
    db.execute("INSERT INTO conversations VALUES(?,?)", (conversation, now()))
    previous_question(db, conversation, question, snapshot)
    search = SearchService(db, resolver, FakeEmbedding(), vectors, settings)
    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()), None, settings)
    return service, db, conversation, snapshot


def test_query_alpha_current_question_keeps_existing_no_inheritance_guard(storage):
    service, _, conversation, snapshot = query_fixture(storage, "Quelle tension CCU-21 ?")
    request = QueryRequest(question="Et sa tension pour AB-CD ?", scope=Scope(kind="library"), conversation_id=conversation)
    effective, resolution, choices, references = service.resolve_followup(request, snapshot)
    assert effective == request.question and resolution["method"] == "explicit_question" and choices == []
    assert references.obligations == {} and references.priority == {"AB-CD"}


def test_query_shares_authorized_focus_resolution_until_context_before_any_llm(storage, monkeypatch):
    service, db, _, _ = query_fixture(storage, "Quelle tension ?", text="ＡＢＣ : tension nominale 72 V.")
    seen = []
    original_search, original_build = service.search.search, service.context.build

    async def search(question, snapshot, mode, references):
        seen.append(references)
        return await original_search(question, snapshot, mode, references)

    def build(question, sources, mode, history, references):
        seen.append(references)
        original_build(question, sources, mode, history, references)
        raise ApiError("qa_stop_before_generation", "Témoin : arrêt avant toute génération.")

    monkeypatch.setattr(service.search, "search", search)
    monkeypatch.setattr(service.context, "build", build)

    async def scenario():
        prepared = service.prepare_query(QueryRequest(question="Quelle tension nominale ?", scope=Scope(kind="library"), focus={"identifier": "ABC"}))
        references = prepared[3]
        response = service.start_query(prepared)
        await service.tasks[response["query_id"]]
        assert len(seen) == 2 and all(item is references for item in seen)
        run = db.one("SELECT metrics_json FROM query_runs WHERE id=?", (response["query_id"],))
        assert json.loads(run["metrics_json"])["model_called"] is False

    asyncio.run(scenario())


def test_api_followup_unique_user_referent_ignores_assistant(storage):
    service, db, conversation, snapshot = query_fixture(storage, "Quelle tension CCU-21 ?")
    previous = db.one("SELECT id FROM query_runs")["id"]
    db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (uid(), conversation, previous, "assistant", "La réponse mentionne CCU-22 sans preuve", now()))
    question, resolution, choices, _ = service.resolve_followup(QueryRequest(question="Et sa tolérance ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
    assert "CCU-21" in question and "CCU-22" not in question
    assert resolution["method"] == "unique_user_referent" and not choices


def test_api_followup_ambiguous_does_not_search_or_generate(storage):
    service, db, conversation, _ = query_fixture(storage, "Comparer CCU-21 et CCU-22")
    result = service.create(QueryRequest(question="Et sa tolérance ?", scope=Scope(kind="library"), conversation_id=conversation))
    assert result["state"] == "needs_clarification" and result["conversation_id"] == conversation
    assert not service.tasks
    event = db.one("SELECT type,data_json FROM events WHERE query_id=?", (result["query_id"],))
    assert event["type"] == "needs_clarification"
    assert {choice["identifier"] for choice in json.loads(event["data_json"])["choices"]} == {"CCU-21", "CCU-22"}


def test_api_named_reference_overrides_user_history(storage):
    service, _, conversation, snapshot = query_fixture(storage, "Quelle tension CCU-21 ?")
    question, resolution, choices, _ = service.resolve_followup(QueryRequest(question="Et CCU-22 ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
    assert question == "Et CCU-22 ?" and resolution["method"] == "explicit_question" and not choices


@pytest.mark.parametrize("launcher", ["./rag.sh", r".\rag.ps1"])
@pytest.mark.parametrize("memory_refusal", [False, True], ids=["private-error", "memory-refusal"])
def test_api_query_error_message_preserves_sse_code_and_private_boundary_with_search_double(
        storage, monkeypatch, launcher, memory_refusal):
    """Double de recherche en échec : vrai QueryService/SQLite, aucun modèle ou service."""
    monkeypatch.setattr("services.runtime.platforms.LAUNCHER", launcher)
    service, db, conversation, _ = query_fixture(storage, "Quelle tension CCU-21 ?")
    memory_message = (
        "Impossible de démarrer la génération de la réponse : 4991 Mio disponibles, 4992 Mio requis "
        "(pic prévu 3456 + réserve 1536). Libérez de la mémoire sur le poste, puis relancez la question."
    )
    error = (ResourceAdmissionError(memory_message, {"available_mib": 4991}) if memory_refusal else
             RuntimeError("PRIVATE_QUERY_SENTINEL"))

    class FailingSearch:
        async def search(self, *args):
            raise error

    service.search = FailingSearch()

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        await service.tasks[query_id]
        await asyncio.sleep(0)
        query = db.one("SELECT state,answer,metrics_json FROM query_runs WHERE id=?", (query_id,))
        assert query["state"] == "error" and query["answer"] == ""
        events = db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))
        assert [event["type"] for event in events] == ["status", "status", "error"]
        event = json.loads(events[-1]["data_json"])
        assert set(event) == {"code", "message", "metrics"}
        assert event["code"] == ("resource_admission_denied" if memory_refusal else "query_failed")
        assert event["metrics"]["model_called"] is False
        assert json.loads(query["metrics_json"]) == event["metrics"]
        assert "PRIVATE_QUERY_SENTINEL" not in event["message"]
        assert event["message"] == (memory_message if memory_refusal else
            "La question n'a pas pu être traitée. Renvoyez-la ; si l'erreur se reproduit, "
            f"exécutez « {launcher} logs » depuis le dossier du projet pour trouver le journal du service local.")
        assert not service.tasks and not service.cancel_events

    asyncio.run(scenario())


class PrivateSearchFailure:
    """Double nommé : recherche en échec sur une erreur privée, jamais affichée à l'utilisateur."""

    async def search(self, *args):
        raise RuntimeError("PRIVATE_QUERY_SENTINEL")


def test_api_query_error_message_of_an_installation_names_the_atelier_logs_command(storage, monkeypatch, tmp_path):
    """Installation par le kit Linux : arborescence factice (double nommé `installation_tree` de
    test_runtime_installation_texts) ; la commande des journaux est celle du lanceur `atelier`, à taper dans un terminal,
    sans renvoi au dossier du projet (KIT4-13, point 5). Vrai QueryService/SQLite, aucun modèle ni service."""
    from test_runtime_installation_texts import installation_tree, run_as

    tree = installation_tree(tmp_path / "poste")
    run_as(monkeypatch, tree.program)
    service, db, conversation, _ = query_fixture(storage, "Quelle tension CCU-21 ?")
    service.search = PrivateSearchFailure()

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        await service.tasks[query_id]
        await asyncio.sleep(0)
        event = json.loads(db.rows("SELECT data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))[-1]["data_json"])
        assert event["code"] == "query_failed"
        assert event["message"] == (
            "La question n'a pas pu être traitée. Renvoyez-la ; si l'erreur se reproduit, "
            f"exécutez « {tree.destination / 'atelier'} journaux » dans un terminal pour trouver le journal du service local.")

    asyncio.run(scenario())


@pytest.mark.parametrize("difference", [256, 257])
def test_api_token_count_warning_text_keeps_threshold_counts_and_citations_with_ollama_double(storage, difference):
    """Ollama et tokenizer synthétiques explicites : aucun modèle ou appel réseau."""
    service, db, conversation, _ = query_fixture(storage, "Quelle tension CCU-21 ?")

    class CountingOllama:
        calls = 0

        async def stream(self, messages, cancelled, output_tokens):
            self.calls += 1
            yield {"type": "delta", "text": "72 V [S001]"}
            yield {"type": "done", "finish_reason": "stop", "metrics": {
                "prompt_eval_count": CharTokenizer().count_messages(messages) + difference, "eval_count": 2,
            }}

    gateway = CountingOllama()
    service.ollama = gateway

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        await service.tasks[query_id]
        done = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query_id,))["data_json"])
        assert gateway.calls == 1 and done["status"] == "done" and done["finish_reason"] == "stop"
        assert done["text"] == "72 V [S001]" and done["citations"][0]["source_id"] == "S001"
        assert done["metrics"]["tokenizer_count_difference"] == difference
        assert done["metrics"]["prompt_eval_count"] == done["metrics"]["local_prompt_tokens"] + difference
        assert service.settings.value("retrieval", "context_safety_tokens", 256) == 256
        drift = [warning for warning in done["warnings"] if warning["code"] == "tokenizer_template_drift"]
        assert len(drift) == int(difference > 256)
        if drift:
            assert drift == [{"code": "tokenizer_template_drift", "difference": 257,
                              "message": "Les comptes de tokens du modèle et du compteur local diffèrent. Vérifiez la configuration du modèle."}]
        stored = db.one("SELECT state,warnings_json,metrics_json FROM query_runs WHERE id=?", (query_id,))
        assert stored["state"] == "done" and json.loads(stored["warnings_json"]) == done["warnings"]
        assert json.loads(stored["metrics_json"]) == done["metrics"]

    asyncio.run(scenario())


def test_api_factual_synonym_without_shared_question_term_still_calls_model(storage):
    """SQLite et QueryService réels ; vecteurs, tokenizer et génération sont des doubles."""
    question = "Quel fabricant est indiqué pour CCU-21 ?"
    evidence = "Le constructeur de CCU-21 est Atelier Exemple."
    service, db, conversation, _ = query_fixture(storage, question, text=evidence)

    class AnsweringOllama:
        calls = 0

        async def stream(self, messages, cancelled, output_tokens):
            self.calls += 1
            assert evidence in messages[-1]["content"]
            yield {"type": "delta", "text": "Le constructeur est Atelier Exemple [S001]."}
            yield {"type": "done", "finish_reason": "stop", "metrics": {}}

    gateway = AnsweringOllama()
    service.ollama = gateway

    async def scenario():
        query_id = service.create(QueryRequest(question=question, scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        await service.tasks[query_id]
        done = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query_id,))["data_json"])
        assert gateway.calls == 1 and done["status"] == "done"
        assert done["text"] == "Le constructeur est Atelier Exemple [S001]."
        assert done["metrics"]["model_called"] is True
        assert done["metrics"]["identifier_coverage_states"] == {"CCU-21": "identifier_present_no_answer_evidence"}
        assert [citation["source_id"] for citation in done["citations"]] == ["S001"]

    asyncio.run(scenario())


class BlockingSearch:
    """Double explicite : la première question garde generation_lock tant que le test ne la libère pas."""
    def __init__(self):
        self.release = asyncio.Event()

    async def search(self, question, snapshot, mode="question", references=None):
        await self.release.wait()
        return {"results": [], "warnings": [], "elapsed_ms": 0}


def cancelled_events(db, query_id):
    return db.one("SELECT count(*) AS n FROM events WHERE query_id=? AND type='cancelled'", (query_id,))["n"]


def test_api_cancel_waiting_or_unstarted_query_writes_one_terminal_event(storage):
    import_fixture(storage)
    settings, db, _, _ = storage
    async def scenario():
        search = BlockingSearch()
        service = QueryService(db, ScopeResolver(db), search, ContextBuilder(settings, CharTokenizer()), None, settings)
        first = service.create(QueryRequest(question="Quelle tension ?", scope=Scope(kind="library")))["query_id"]
        second = service.create(QueryRequest(question="Quelle tolérance ?", scope=Scope(kind="library")))["query_id"]
        for _ in range(200):
            if db.one("SELECT state FROM query_runs WHERE id=?", (first,))["state"] == "running" and db.one("SELECT count(*) AS n FROM events WHERE query_id=?", (second,))["n"]:
                break
            await asyncio.sleep(0.01)
        assert second in service.started and db.one("SELECT state FROM query_runs WHERE id=?", (second,))["state"] == "queued"
        waiting = service.tasks[second]
        assert service.cancel(second)["state"] == "cancel_requested"
        await asyncio.gather(waiting, return_exceptions=True)
        assert db.one("SELECT state FROM query_runs WHERE id=?", (second,))["state"] == "cancelled"
        assert cancelled_events(db, second) == 1 and second not in service.cancel_events and second not in service.tasks
        unstarted = service.create(QueryRequest(question="Quelle intensité ?", scope=Scope(kind="library")))["query_id"]
        never_run = service.tasks[unstarted]
        service.cancel(unstarted)
        await asyncio.gather(never_run, return_exceptions=True)
        assert db.one("SELECT state FROM query_runs WHERE id=?", (unstarted,))["state"] == "cancelled"
        assert cancelled_events(db, unstarted) == 1 and unstarted not in service.cancel_events and unstarted not in service.started
        search.release.set()
        await asyncio.gather(*service.tasks.values())
        assert db.one("SELECT state FROM query_runs WHERE id=?", (first,))["state"] == "done"
        assert service.cancel_events == {} and service.tasks == {} and service.started == set()
        assert service.cancel(second)["state"] == "cancelled" and cancelled_events(db, second) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("cancelled", [False, True])
def test_api_delta_persistence_keeps_the_loop_live_and_finishes_before_cancelled(storage, monkeypatch, cancelled):
    """SQLite réelle ; une barrière de thread remplace seulement la durée de persistance d'un delta."""
    service, db, conversation, _ = query_fixture(storage, "Quelle tension CCU-21 ?")
    entered, release = threading.Event(), threading.Event()
    original_add_event = db.add_event
    persistence_threads = []

    class AnsweringOllama:
        async def stream(self, messages, cancellation, output_tokens):
            yield {"type": "delta", "text": "72 V [S001]"}
            yield {"type": "done", "finish_reason": "stop", "metrics": {}}

    def delayed_event(query_id, kind, data):
        if kind == "delta":
            persistence_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(3), "La boucle doit pouvoir libérer le thread SQLite."
        return original_add_event(query_id, kind, data)

    service.ollama = AnsweringOllama()
    monkeypatch.setattr(db, "add_event", delayed_event)

    async def scenario():
        loop_thread = threading.get_ident()
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        task = service.tasks[query_id]
        try:
            # Le délai de préparation inclut les fsync SD ; l'oracle porte sur le thread et la barrière, pas sur sa latence.
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 15), 16)
            assert len(persistence_threads) == 1 and persistence_threads[0] != loop_thread
            assert not task.done()
            if cancelled:
                service.cancel(query_id)
                await asyncio.sleep(0)
                assert not task.done(), "L'annulation doit attendre la fin de l'écriture déjà admise."
            release.set()
            await asyncio.wait_for(task, 10)
            events = db.rows("SELECT id,type FROM events WHERE query_id=? ORDER BY id", (query_id,))
            assert events[-1]["type"] == ("cancelled" if cancelled else "done")
            assert [event["type"] for event in events].count("delta") == 1
            assert [event["id"] for event in events] == list(range(1, len(events) + 1))
            row = db.one("SELECT state,last_event_id FROM query_runs WHERE id=?", (query_id,))
            assert row == {"state": "cancelled" if cancelled else "done", "last_event_id": events[-1]["id"]}
        finally:
            release.set()
            await service.close()

    asyncio.run(scenario())


def test_api_question_queue_remains_fifo_when_the_first_queued_event_is_slow(storage, monkeypatch):
    import_fixture(storage)
    settings, db, vectors, _ = storage
    entered, release = threading.Event(), threading.Event()
    calls = []
    first = None
    original_add_event = db.add_event

    def delayed_event(query_id, kind, data):
        if query_id == first and kind == "status" and data.get("state") == "queued":
            entered.set()
            assert release.wait(3)
        return original_add_event(query_id, kind, data)

    monkeypatch.setattr(db, "add_event", delayed_event)

    class RecordingSearch(BlockingSearch):
        async def search(self, question, snapshot, mode="question", references=None):
            calls.append(question)
            return await super().search(question, snapshot, mode, references)

    async def scenario():
        nonlocal first
        search = RecordingSearch()
        service = QueryService(db, ScopeResolver(db), search, ContextBuilder(settings, CharTokenizer()), None, settings)
        first = service.create(QueryRequest(question="Première question", scope=Scope(kind="library")))["query_id"]
        second = service.create(QueryRequest(question="Deuxième question", scope=Scope(kind="library")))["query_id"]
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 15), 16)
            await asyncio.sleep(0)
            assert calls == []
            release.set()
            for _ in range(100):
                if calls:
                    break
                await asyncio.sleep(0.01)
            assert calls == ["Première question"]
            assert db.one("SELECT state FROM query_runs WHERE id=?", (second,))["state"] == "queued"
            search.release.set()
            await asyncio.gather(*service.tasks.values())
            assert calls == ["Première question", "Deuxième question"]
        finally:
            release.set()
            search.release.set()
            await service.close()

    asyncio.run(scenario())


def test_api_cancellation_before_the_terminal_transaction_prevents_done(storage, monkeypatch):
    service, db, conversation, _ = query_fixture(storage, "Quelle tension CCU-21 ?")
    entered, release = threading.Event(), threading.Event()
    original_finish = service.finish

    class AnsweringOllama:
        async def stream(self, messages, cancellation, output_tokens):
            yield {"type": "delta", "text": "72 V [S001]"}
            yield {"type": "done", "finish_reason": "stop", "metrics": {}}

    def delayed_finish(*args):
        entered.set()
        assert release.wait(3)
        return original_finish(*args)

    service.ollama = AnsweringOllama()
    monkeypatch.setattr(service, "finish", delayed_finish)

    async def scenario():
        query_id = service.create(QueryRequest(question="Quelle tension CCU-21 ?", scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        task = service.tasks[query_id]
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 15), 16)
            assert service.cancel(query_id)["state"] == "cancel_requested"
            release.set()
            await asyncio.wait_for(task, 10)
            assert db.one("SELECT state FROM query_runs WHERE id=?", (query_id,))["state"] == "cancelled"
            assert [event["type"] for event in db.rows("SELECT type FROM events WHERE query_id=? AND type IN ('done','cancelled')", (query_id,))] == ["cancelled"]
            assert db.one("SELECT count(*) AS n FROM messages WHERE query_id=? AND role='assistant'", (query_id,))["n"] == 0
        finally:
            release.set()
            await service.close()

    asyncio.run(scenario())


def test_api_async_cancellation_does_not_block_the_loop_on_a_real_sqlite_write_lock(storage):
    service, db, _, _ = query_fixture(storage, "Quelle tension CCU-21 ?")
    query_id = db.one("SELECT id FROM query_runs")["id"]
    db.busy_timeout_ms = 400

    async def scenario():
        with db.transaction() as connection:
            connection.execute("UPDATE query_runs SET cancel_requested=0 WHERE id=?", (query_id,))
            cancellation = asyncio.create_task(service.cancel_async(query_id))
            # Ce tick doit se produire alors que le vrai WRITE lock est encore tenu par le test.
            await asyncio.sleep(0.05)
            assert not cancellation.done(), "La boucle a attendu la fin du busy_timeout SQLite."
        response = await asyncio.wait_for(cancellation, 3)
        assert response == {"query_id": query_id, "state": "done"}
        assert db.one("SELECT cancel_requested FROM query_runs WHERE id=?", (query_id,))["cancel_requested"] == 1

    asyncio.run(scenario())


def test_api_async_query_admission_is_serialized_and_keeps_asyncio_tasks_on_the_loop(storage):
    import_fixture(storage)
    settings, db, _, _ = storage

    async def scenario():
        search = BlockingSearch()
        service = QueryService(db, ScopeResolver(db), search, ContextBuilder(settings, CharTokenizer()), None, settings)
        results = await asyncio.gather(*(service.create_async(QueryRequest(question=f"Question {index}", scope=Scope(kind="library")))
                                        for index in range(6)), return_exceptions=True)
        try:
            accepted = [result for result in results if isinstance(result, dict)]
            refused = [result for result in results if isinstance(result, Exception)]
            assert len(accepted) == 3 and len(refused) == 3
            assert all(error.code == "query_queue_full" for error in refused)
            assert db.one("SELECT count(*) AS n FROM query_runs WHERE state IN ('queued','running')")["n"] == 3
            assert all(task.get_loop() is asyncio.get_running_loop() for task in service.tasks.values())
        finally:
            await service.close()

    asyncio.run(scenario())


def test_api_cancelled_async_creation_does_not_leave_an_unstarted_queued_query(storage, monkeypatch):
    import_fixture(storage)
    settings, db, _, _ = storage
    service = QueryService(db, ScopeResolver(db), BlockingSearch(), ContextBuilder(settings, CharTokenizer()), None, settings)
    entered, release = threading.Event(), threading.Event()
    original_prepare = service.prepare_query

    def delayed_prepare(request):
        result = original_prepare(request)
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(service, "prepare_query", delayed_prepare)

    async def scenario():
        creation = asyncio.create_task(service.create_async(QueryRequest(question="Question annulée", scope=Scope(kind="library"))))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 15), 16)
            creation.cancel()
            await asyncio.sleep(0)
            assert not creation.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(creation, 10)
            assert not service.tasks and not service.cancel_events
            assert [row["state"] for row in db.rows("SELECT state FROM query_runs")] == ["cancelled"]
            assert db.one("SELECT count(*) AS n FROM events WHERE type='cancelled'")["n"] == 1
        finally:
            release.set()
            await service.close()

    asyncio.run(scenario())


def test_api_cancelled_cancel_request_still_signals_the_query_on_the_loop(storage, monkeypatch):
    import_fixture(storage)
    settings, db, _, _ = storage
    entered, release = threading.Event(), threading.Event()
    service = QueryService(db, ScopeResolver(db), BlockingSearch(), ContextBuilder(settings, CharTokenizer()), None, settings)
    original_persist = service.request_cancellation

    def delayed_persist(query_id):
        result = original_persist(query_id)
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(service, "request_cancellation", delayed_persist)

    async def scenario():
        query_id = service.create(QueryRequest(question="Question en cours", scope=Scope(kind="library")))["query_id"]
        task = service.tasks[query_id]
        cancellation = asyncio.create_task(service.cancel_async(query_id))
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 15), 16)
            cancellation.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(cancellation, 10)
            await asyncio.wait_for(task, 10)
            assert db.one("SELECT state,cancel_requested FROM query_runs WHERE id=?", (query_id,)) == {"state": "cancelled", "cancel_requested": 1}
            assert not service.tasks and not service.cancel_events
            assert cancelled_events(db, query_id) == 1
        finally:
            release.set()
            await service.close()

    asyncio.run(scenario())
