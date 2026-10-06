"""Budgets des profils livrés ; tokenizer et moteur remplacés explicitement dans les unités."""
import asyncio
import json
from pathlib import Path

import pytest
from test_api_context import fragment
from test_api_queries import query_fixture
from test_api_storage import storage as storage
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.ollama import OllamaGateway
from services.api.schemas import QueryRequest, Scope
from services.api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ["config/local16.yaml", "config/local16-4b.yaml",
            "RAG_Local_Agents/config/local16.yaml", "RAG_Local_Agents/config/local16-4b.yaml"]
MODES = [("question", "Quelle tension pour CCU-21 ?", 768),
         ("question", "Décrire la tension de CCU-21", 1536),
         ("factual", "Décrire la tension de CCU-21", 768),
         ("analysis", "Analyser la tension de CCU-21", 1536),
         ("section", "Décrire la tension de CCU-21", 1536),
         ("comparison", "Comparer la tension de CCU-21", 1536)]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("mode,question,expected", MODES)
def test_delivered_output_budget_is_reserved_and_sent_to_gateway(profile, mode, question, expected):
    """Profils et constructeur réels, comptage caractères/4 ; aucune requête HTTP ni modèle."""
    settings = Settings.load(ROOT / profile)
    assert settings.value("llm", "num_ctx") == 8192
    assert settings.value("llm", "num_predict") == 1536
    assert settings.value("llm", "output_tokens_by_mode") == {
        "factual": 768, "ordinary": 1536, "analysis": 1536, "compare": 1536}
    assert settings.value("retrieval", "context_safety_tokens") == 256
    assert 8192 - settings.value("llm", "num_predict") - 256 == 6400
    retrieval = settings.profile["retrieval"]
    assert retrieval["max_evidence_llm_tokens"] == 4864
    assert retrieval["evidence_tokens_by_mode"] == {
        "factual": 1536, "ordinary": 2560, "analysis": 4864, "compare": 4864}
    assert (retrieval["max_evidence_llm_tokens"] + retrieval["max_history_llm_tokens"]
            + retrieval["max_instructions_question_llm_tokens"] + 1536 + 256) == 8192
    sources = [fragment("A", "CCU-21 : tension nominale 72 V", exact=True)]
    if mode == "comparison":
        sources.append(fragment("B", "CCU-21 : tension nominale 110 V", exact=True))
    _, retained, metrics, _ = ContextBuilder(settings, CharTokenizer()).build(question, sources, mode)
    assert metrics["output_tokens"] == expected
    assert metrics["local_prompt_tokens"] + expected + 256 <= 8192
    assert {source["document_id"] for source in retained} == {source["document_id"] for source in sources}
    gateway = OllamaGateway(settings)
    try:
        for cpu in (True, False):
            options = gateway.chat_options(metrics["output_tokens"], cpu=cpu)
            assert options["num_predict"] == expected and options["num_ctx"] == 8192
            assert (options.get("num_gpu") == 0) if cpu else ("num_gpu" not in options)
    finally:
        asyncio.run(gateway.close())


@pytest.mark.parametrize("profile", PROFILES)
def test_delivered_analysis_budget_keeps_coverage_and_reports_exclusion(profile):
    """Cinq passages synthétiques dépassent le plafond final ; le constructeur réel doit le signaler."""
    settings = Settings.load(ROOT / profile)
    tokenizer = CharTokenizer()
    sources = [fragment("A", "CCU-21 : tension nominale 72 V. " + "x" * 3900, index, exact=True)
               for index in range(5)]
    total = sum(tokenizer.count(ContextBuilder.evidence({**source, "source_id": f"S{index + 1:03d}"}))
                for index, source in enumerate(sources))
    assert 4864 < total <= 5120
    _, retained, metrics, warnings = ContextBuilder(settings, tokenizer).build(
        "Analyser la tension de CCU-21", sources, "analysis")
    assert len(retained) == 4
    assert metrics["evidence_budget"] == 4864 and metrics["evidence_tokens"] <= 4864
    assert metrics["local_prompt_tokens"] <= 6400 and metrics["output_tokens"] == 1536
    assert metrics["exact_identifiers_covered"] == ["CCU-21"]
    assert metrics["context_fragments_excluded_by_budget"] == 1
    assert next(warning["count"] for warning in warnings
                if warning["code"] == "context_fragments_excluded_by_budget") == 1


@pytest.mark.parametrize("question,expected", [("Quelle tension CCU-21 ?", 768),
                                              ("Décrire la tension de CCU-21", 1536)])
@pytest.mark.parametrize("finish_reason", ["stop", "length"])
@pytest.mark.parametrize("prompt_tokens", [6400, 6401])
def test_query_runtime_budget_boundary_preserves_incomplete_status(storage, question, expected, finish_reason, prompt_tokens):
    """QueryService/SQLite réels et stockage temporaire ; Ollama, embedding et tokenizer sont des doubles."""
    service, db, conversation, _ = query_fixture(storage, question)
    delivered = Settings.load(ROOT / "config/local16.yaml")
    service.settings.profile["llm"] = delivered.profile["llm"]
    service.settings.profile["retrieval"] = delivered.profile["retrieval"]

    class BudgetOllama:
        calls = 0

        async def stream(self, messages, cancelled, output_tokens):
            self.calls += 1
            assert output_tokens == expected
            assert "CCU-21" in messages[-1]["content"]
            yield {"type": "delta", "text": "La tension de CCU-21 est de 72 V [S001]."}
            yield {"type": "done", "finish_reason": finish_reason,
                   "metrics": {"prompt_eval_count": prompt_tokens, "eval_count": 12}}

    gateway = BudgetOllama()
    service.ollama = gateway

    async def scenario():
        query_id = service.create(QueryRequest(question=question, scope=Scope(kind="library"),
                                               conversation_id=conversation))["query_id"]
        await service.tasks[query_id]
        events = db.rows("SELECT type,data_json FROM events WHERE query_id=? ORDER BY id", (query_id,))
        terminal = json.loads(events[-1]["data_json"])
        assert gateway.calls == 1
        if prompt_tokens > 6400:
            assert events[-1]["type"] == "error" and terminal["code"] == "runtime_context_exceeded"
            assert db.one("SELECT state FROM query_runs WHERE id=?", (query_id,))["state"] == "error"
            assert not any(event["type"] == "done" for event in events)
        else:
            assert events[-1]["type"] == "done"
            assert terminal["finish_reason"] == finish_reason
            assert terminal["status"] == ("length_limited" if finish_reason == "length" else "done")
            assert terminal["citations"][0]["source_id"] == "S001"
            limits = [warning for warning in terminal["warnings"] if warning["code"] == "answer_length_limit"]
            assert len(limits) == int(finish_reason == "length")
            assert terminal["metrics"]["output_tokens"] == expected
        assert service.settings.value("retrieval", "context_safety_tokens") == 256

    asyncio.run(scenario())
