"""QueryService real SQLite path; explicitly fake embeddings/vectors/tokenizer.

The gateway must never be called for an exact cell-reading route. This is a
control-flow integration test, not a native 4B or tokenizer qualification.
"""

import asyncio
import json
from pathlib import Path

from test_enhanced_retrieval import range_fixture
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.execution_trace import read_verified_trace
from services.api.query import QueryService
from services.api.schemas import QueryRequest, Scope


def test_exact_cells_use_the_real_rendering_path_without_calling_a_generator(rag):
    snapshot = range_fixture(rag)
    settings, db, _, _, resolver, search = rag
    settings.profile["enhanced"] = {"preserve_evidence": True, "answer_contract": True}
    settings.profile["trace"] = {"mode": "full"}

    class ForbiddenGateway:
        async def stream(self, *args, **kwargs):
            raise AssertionError("Exact reading must not call a model")
            yield  # pragma: no cover -- retain the async-generator interface

    service = QueryService(db, resolver, search, ContextBuilder(settings, CharTokenizer()), ForbiddenGateway(), settings)

    async def scenario():
        response = await service.create_async(QueryRequest(
            question="Quelles valeurs contiennent exactement les cellules B5 et B6 ?", scope=Scope(**snapshot.scope)))
        query_id = response["query_id"]
        await service.tasks[query_id]
        run = service.run_detail(query_id)
        assert run["state"] == "done"
        assert "Valeur littérale « 0 »" in run["answer"] and "Valeur littérale « 36 »" in run["answer"]
        assert run["metrics"]["model_called"] is False
        assert run["metrics"]["response_route"] == "deterministic_cell_contract"
        assert run["metrics"]["execution_trace"]["replayable_content"] is False
        terminal = json.loads(db.one("SELECT data_json FROM events WHERE query_id=? AND type='done'", (query_id,))["data_json"])
        assert terminal["structured_answer"]["plan_origin"] == "deterministic_contract"
        assert terminal["citations"]
        trace = read_verified_trace(Path(settings.data_dir) / "traces" / (query_id + ".jsonl"))
        phases = {row["phase"] for row in trace}
        assert {"query.start", "context", "answer.deterministic_plan", "query.done"} <= phases
        assert "llm.request" not in phases

    asyncio.run(scenario())
