"""Real OOXML/SQLite scope refusal; vector/embedding/token counts are doubles."""

import asyncio
import json
from pathlib import Path

from test_office_rag import rag as rag
from test_office_rag import range_scope, workbook
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.execution_trace import read_verified_trace
from services.api.query import QueryService
from services.api.schemas import QueryRequest


def test_request_for_other_sheet_refuses_without_model_or_outside_content(rag):
    imported, extraction = workbook(rag)
    settings, db, _, _, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True,
                                    "complementary_retrieval": True}
    settings.profile["trace"] = {"mode": "full"}

    class ForbiddenGateway:
        async def stream(self, *args, **kwargs):
            raise AssertionError("A proven scope mismatch must not call a model")
            yield  # pragma: no cover -- async-generator interface

    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()),
                           ForbiddenGateway(), settings)

    async def scenario():
        response = await service.create_async(QueryRequest(
            question="Quel marqueur figure dans la deuxième feuille du classeur ?",
            scope=range_scope(imported, extraction)))
        query_id = response["query_id"]
        await service.tasks[query_id]
        run = service.run_detail(query_id)
        assert run["state"] == "done"
        assert run["metrics"]["model_called"] is False
        assert run["metrics"]["response_route"] == "deterministic_scope_refusal"
        assert "périmètre sélectionné" in run["answer"]
        assert "feuille 2" in run["answer"]
        assert "Another-sheet-secret" not in run["answer"]
        assert "72 V" not in run["answer"]
        terminal = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'",
                                     (query_id,))["data_json"])
        assert terminal["citations"] == []
        assert terminal["text"] == run["answer"]
        assert terminal["structured_answer"]["answer_contract"]["scope_refusal"]["reason"] == "requested_sheet_outside_scope"
        trace = read_verified_trace(Path(settings.data_dir) / "traces" / (query_id + ".jsonl"))
        assert "Another-sheet-secret" not in json.dumps(trace)
        assert "llm.request" not in {event["phase"] for event in trace}
        deterministic = next(event for event in trace if event["phase"] == "answer.deterministic_plan")
        assert "requested_sheet_outside_scope" in json.dumps(deterministic)

    asyncio.run(scenario())
