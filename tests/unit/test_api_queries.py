import asyncio
import json

import pytest
from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.db import json_dump, now, uid
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


def test_api_followup_unique_user_referent_ignores_assistant(storage):
    service, db, conversation, snapshot = query_fixture(storage, "Quelle tension CCU-21 ?")
    previous = db.one("SELECT id FROM query_runs")["id"]
    db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (uid(), conversation, previous, "assistant", "La réponse mentionne CCU-22 sans preuve", now()))
    question, resolution, choices = service.resolve_followup(QueryRequest(question="Et sa tolérance ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
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
    question, resolution, choices = service.resolve_followup(QueryRequest(question="Et CCU-22 ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
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

    async def search(self, question, snapshot, mode="question"):
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
