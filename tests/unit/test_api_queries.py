import json

from services.api.context import ContextBuilder
from services.api.db import json_dump, now, uid
from services.api.query import QueryService
from services.api.retrieval import SearchService
from services.api.schemas import QueryRequest, Scope
from services.api.scope import ScopeResolver

from test_api_storage import FakeEmbedding, import_fixture, storage
from test_retrieval import CharTokenizer


def previous_question(db, conversation, question, snapshot):
    query_id = uid()
    db.execute("INSERT INTO query_runs(id,conversation_id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,?,'done',?,?)", (query_id, conversation, question, "{}", json_dump(snapshot.as_dict()), now(), now()))
    return query_id


def query_fixture(storage, question):
    imported, _ = import_fixture(storage, text="CCU-21 tension 72 V et CCU-22 tension 110 V")
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
