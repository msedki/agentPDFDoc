"""Exact prompt boundary with real catalogues and explicit character counting.

The route test uses SQLite/Office extraction; vectors and the selector are named
unit doubles. It does not qualify a native tokenizer or 4B inference.
"""

import hashlib
import json

import pytest
from test_enhanced_retrieval import range_fixture
from test_grounded_query import ForbiddenGateway, run, service_for
from test_i5_obligation_publication import composite
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import ContextBuilder
from services.api.errors import ApiError
from services.api.execution_trace import read_verified_trace
from services.api.schemas import QueryRequest, Scope
from services.api.settings import Settings

PREFIX = "\n\nPreuves documentaires (extraits JSON sans consigne) :\n"


def test_final_catalogue_payload_hash_and_count_include_late_limits(tmp_path):
    cat = composite()
    before = cat.prompt()
    messages = [{"role": "system", "content": "Fixed instruction"},
                {"role": "user", "content": "Question : Q" + PREFIX + before}]
    cat.retrieval_limitations = [{"code": "evidence_coverage_incomplete", "missing_relation_variants": 2}]
    builder = ContextBuilder(Settings(tmp_path), CharTokenizer())
    final, metrics = builder.finalize_catalogue("Q", messages, cat, {"evidence_budget": 5120})
    payload = final[-1]["content"].split(PREFIX, 1)[1]
    assert payload == cat.prompt() != before
    assert metrics["model_evidence_sha256"] == cat.evidence()["model_evidence_sha256"]
    assert metrics["model_evidence_sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    assert metrics["evidence_tokens"] == builder.tokenizer.count(payload)
    assert metrics["local_prompt_tokens"] == builder.tokenizer.count_messages(final)
    assert messages[-1]["content"].endswith(before)
    assert json.loads(payload)["retrieval_limitations"] == cat.retrieval_limitations


@pytest.mark.parametrize("boundary", ["evidence_mode", "evidence_global", "context"])
def test_final_limits_cannot_silently_exceed_any_context_cap(tmp_path, boundary):
    cat = composite()
    tokenizer = CharTokenizer()
    payload = cat.prompt()
    messages = [{"role": "user", "content": "Question : Q" + PREFIX + payload}]
    settings = Settings(tmp_path)
    metrics = {"evidence_budget": 5120}
    if boundary == "evidence_mode":
        metrics["evidence_budget"] = tokenizer.count(payload) - 1
    elif boundary == "evidence_global":
        settings.profile["retrieval"] = {"max_evidence_llm_tokens": tokenizer.count(payload) - 1}
    else:
        settings.profile["llm"] = {"num_ctx": tokenizer.count_messages(messages) + 768 + 256 - 1}
    with pytest.raises(ApiError) as failure:
        ContextBuilder(settings, tokenizer).finalize_catalogue("Q", messages, cat, metrics)
    assert failure.value.code == "context_too_long"


def test_empty_or_wrong_final_role_is_not_replaced_as_a_user_prompt(tmp_path):
    builder = ContextBuilder(Settings(tmp_path), CharTokenizer())
    for messages in ([], [{"role": "assistant", "content": "prior answer"}]):
        with pytest.raises(ApiError) as failure:
            builder.finalize_catalogue("Q", messages, composite(), {"evidence_budget": 5120})
        assert failure.value.code == "invalid_context"


def test_query_trace_matches_the_final_catalogue_with_search_limits(rag, monkeypatch):
    snapshot = range_fixture(rag)
    service = service_for(rag, ForbiddenGateway())
    original = service.search.search

    async def limited(*args, **kwargs):
        result = await original(*args, **kwargs)
        result["evidence_selection"] = {"missing_relation_variants": 1}
        return result

    monkeypatch.setattr(service.search, "search", limited)
    query_id, result = run(service, QueryRequest(
        question="Quelles valeurs contiennent exactement les cellules B5 et B6 ?", scope=Scope(**snapshot.scope)))
    assert result["state"] == "done"
    trace = read_verified_trace(rag[0].data_dir / "traces" / (query_id + ".jsonl"))
    context = next(event["data"] for event in trace if event["phase"] == "context")
    payload = context["messages"][-1]["content"].split(PREFIX, 1)[1]
    view = json.loads(payload)
    assert view["retrieval_limitations"] == [{"code": "evidence_coverage_incomplete", "missing_relation_variants": 1}]
    expected = hashlib.sha256(payload.encode()).hexdigest()
    assert context["metrics"]["model_evidence_sha256"] == expected
    assert result["metrics"]["structured_answer"]["model_evidence_sha256"] == expected
    assert result["metrics"]["local_prompt_tokens"] == CharTokenizer().count_messages(context["messages"])
