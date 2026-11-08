"""Discriminating selection -> context checks at unchanged short budgets.

SQLite, provenance validation, selection, catalogue and context packing are
real. Ranking/extraction/embedding fixtures and the named character tokenizer
are doubles: this isolates prefix loss, not native Qwen token counts or recall.
"""

import json

import pytest
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_i4_evidence_coverage import ranked_case
from test_retrieval import library_search

from services.api.context import ContextBuilder
from services.api.query import _retrieval_limitations
from services.api.structured_answer import StructuredAnswerBuilder


class CharacterQuarterTokenizer:
    """Explicit deterministic budget double; one token per four characters."""

    def count(self, text):
        return len(text) // 4 + 1

    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)


@pytest.mark.parametrize("boundary", ["evidence_budget", "serialized_budget"])
@pytest.mark.parametrize("metadata_priority", [False, True])
def test_a_recovered_property_survives_context_when_its_minimal_support_fits(storage, monkeypatch, boundary, metadata_priority):
    question = "What are the bus voltage and supply voltage ranges?"
    result, before = ranked_case(storage, monkeypatch,
        {"device": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."]}, question)
    assert len(result["results"]) == 6
    assert all(item["covered"] for item in before["obligations"])
    settings = storage[0]
    _, snapshot, db = library_search(storage)
    structured = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True)
    context = ContextBuilder(settings, CharacterQuarterTokenizer())
    sources = result["results"]
    if metadata_priority:
        # Ranking metadata may favour every duplicate. It cannot move those
        # occurrences ahead of the independently verified minority relation.
        sources = [{**source, "exact_identifier": "Bus voltage:" in source["text"]} for source in sources]
    bus = next(source for source in sources if "Bus voltage:" in source["text"])
    supply = next(source for source in sources if "Supply voltage:" in source["text"])
    minimal = [bus, supply]
    duplicates = [source for source in sources if "Bus voltage:" in source["text"]][:2]
    assert len(duplicates) == 2
    _, _, minimum, _ = context.build(question, minimal, structured=structured)
    _, _, duplicate_cost, _ = context.build(question, duplicates, structured=structured)
    if boundary == "evidence_budget":
        cap = max(minimum["evidence_tokens"], duplicate_cost["evidence_tokens"])
        settings.profile["retrieval"].update(evidence_tokens_by_mode={"factual": cap}, max_evidence_llm_tokens=cap)
    else:
        cap = max(minimum["local_prompt_tokens"], duplicate_cost["local_prompt_tokens"])
        settings.profile.setdefault("llm", {})["num_ctx"] = (
            cap + settings.value("llm", "num_predict", 768) + settings.value("retrieval", "context_safety_tokens", 256))
    # Both required relations demonstrably fit this exact configuration. A
    # missing property below therefore cannot be explained by an impossible cap.
    _, feasible, feasible_metrics, _ = context.build(question, minimal, structured=structured)
    feasible_assessment = structured.catalogue(feasible, "question").assess()
    assert all(item["covered"] for item in feasible_assessment["obligations"])
    messages, retained, metrics, warnings = context.build(question, sources, structured=structured)
    after = structured.catalogue(retained, "question").assess()
    diagnostic = {"boundary": boundary, "cap": cap, "selected_texts": [source["text"] for source in sources],
                  "retained_texts": [source["text"] for source in retained],
                  "feasible_evidence_tokens": feasible_metrics["evidence_tokens"],
                  "feasible_prompt_tokens": feasible_metrics["local_prompt_tokens"],
                  "actual_evidence_tokens": metrics["evidence_tokens"], "actual_prompt_tokens": metrics["local_prompt_tokens"],
                  "before_obligations": before["obligations"], "after_obligations": after["obligations"],
                  "warning_codes": [warning["code"] for warning in warnings]}
    assert all(item["covered"] for item in after["obligations"]), json.dumps(diagnostic, ensure_ascii=False)
    assert after["status"] == "covered"
    assert any("Supply voltage:" in source["text"] for source in retained)
    assert any("Bus voltage:" in source["text"] for source in retained)
    assert len(retained) <= 6
    if boundary == "evidence_budget":
        assert metrics["evidence_budget"] == cap and metrics["evidence_tokens"] <= cap
    else:
        assert CharacterQuarterTokenizer().count_messages(messages) <= cap


@pytest.mark.parametrize(("question", "texts", "before_status"), [
    ("What are the bus voltage and supply voltage ranges?",
     ["Bus voltage: 0 to 18 V.", "Supply voltage: 3 to 5 V."], "covered"),
    ("What is the nominal supply voltage?",
     ["Nominal supply voltage: 2.8 V at 25 °C.", "Nominal supply voltage: 3.2 V at 70 °C."], "covered"),
    ("What is the nominal supply voltage?",
     ["Nominal supply voltage: 2.8 V at 70 °C.", "Nominal supply voltage: 3.2 V at 70 °C."], "conflict"),
])
def test_an_impossible_context_cap_keeps_lost_property_condition_or_conflict_visible(storage, monkeypatch,
                                                                                    question, texts, before_status):
    result, before = ranked_case(storage, monkeypatch, {"device": texts}, question)
    assert before["status"] == before_status
    settings = storage[0]
    _, snapshot, db = library_search(storage)
    structured = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True)
    context = ContextBuilder(settings, CharacterQuarterTokenizer())
    sources = result["results"]
    cap = max(context.build(question, [source], structured=structured)[2]["evidence_tokens"] for source in sources)
    settings.profile["retrieval"].update(evidence_tokens_by_mode={"factual": cap}, max_evidence_llm_tokens=cap)
    _, retained, metrics, warnings = context.build(question, sources, structured=structured)
    assert len(retained) == 1 and metrics["evidence_tokens"] <= cap
    coverage = metrics["verified_relation_coverage"]
    assert coverage["available_relation_variants"] == 2 and coverage["retained_relation_variants"] == 1
    assert coverage["lost_relation_variants"] == 1
    assert any(warning["code"] == "evidence_coverage_incomplete" and warning.get("stage") == "context"
               for warning in warnings)
    catalogue = structured.catalogue(retained, "question")
    catalogue.retrieval_limitations = _retrieval_limitations(result, metrics)
    assert catalogue.retrieval_limitations == [{"code": "evidence_coverage_incomplete", "missing_relation_variants": 1}]
    answer = render(catalogue)
    assert answer["answer_contract"]["status"] == "partial"
    assert any(item["requirement"] == "retrieval_coverage_incomplete" for item in answer["answer_contract"]["missing"])
    assert not answer["answer_contract"]["comparisons"]
    assert catalogue.deterministic_plan() is None
    assert answer["support_validation"]["unsupported_characters"] == 0
    assert "toutes les variantes de relations retrouvées" in answer["text"]
    assert "La réponse reste partielle" in answer["text"]
    assert retained[0]["text"] in answer["text"]


def test_losing_a_property_not_asked_for_does_not_create_a_false_partial_answer(storage, monkeypatch):
    question = "What is the supply voltage range?"
    result, _ = ranked_case(storage, monkeypatch,
        {"device": ["Bus voltage: 0 to 18 V.", "Supply voltage: 3 to 5 V."]}, question)
    settings = storage[0]
    _, snapshot, db = library_search(storage)
    structured = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True)
    context = ContextBuilder(settings, CharacterQuarterTokenizer())
    supply = next(source for source in result["results"] if "Supply voltage:" in source["text"])
    cap = context.build(question, [supply], structured=structured)[2]["evidence_tokens"]
    settings.profile["retrieval"].update(evidence_tokens_by_mode={"factual": cap}, max_evidence_llm_tokens=cap)
    _, retained, metrics, _ = context.build(question, result["results"], structured=structured)
    assert len(retained) == 1 and retained[0]["text"] == supply["text"]
    catalogue = structured.catalogue(retained, "question")
    catalogue.retrieval_limitations = _retrieval_limitations(result, metrics)
    assert not catalogue.retrieval_limitations, metrics
    assert catalogue.assess()["status"] == "covered"
    assert catalogue.deterministic_plan() is not None
