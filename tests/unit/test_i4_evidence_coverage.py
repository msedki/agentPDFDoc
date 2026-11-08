"""I4 R01–R08: verified SQLite evidence, injected ranking, unchanged cap of six.

Extraction/embeddings are named test doubles. These tests isolate selection;
they do not measure model retrieval, OCR or answer quality.
"""

import asyncio
import copy

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_retrieval import library_search

from services.api.structured_answer import StructuredAnswerBuilder


def ranked_case(storage, monkeypatch, documents, question, mode="question", duplicates=0):
    settings, db, _, _ = storage
    settings.profile["enhanced"] = {"preserve_evidence": True, "property_coverage_selection": True}
    settings.profile["retrieval"] = {"final_max_fragments": 6, "constrained_max_fragments": 6}
    for document, texts in documents.items():
        import_fixture(storage, path=f"{document}.pdf", text="\n".join(texts), pages=[
            {"page_index": 0, "width": 595, "height": 842,
             "blocks": [{"id": f"b{index}", "text": text} for index, text in enumerate(texts)]}])
    search, snapshot, _ = library_search(storage)
    candidates = []
    for generation in snapshot.generations:
        rows = db.rows("SELECT * FROM chunks WHERE generation_id=? ORDER BY CAST(substr(parent_id,2) AS INTEGER)", (generation,))
        candidates.extend(search.resolver.source_for_chunk(dict(row), snapshot) for row in rows)
    if duplicates:
        copies = [copy.deepcopy(candidates[0]) for _ in range(duplicates)]
        for index, source in enumerate(copies):
            source["chunk_id"] = f"duplicate-{index}"
        candidates[1:1] = copies

    async def fixed_ranking(_question, narrowed, *_args):
        return [copy.deepcopy(source) for source in candidates if source["generation_id"] in narrowed.generations]

    monkeypatch.setattr(search, "_candidates", fixed_ranking)
    result = asyncio.run(search.search(question, snapshot, mode))
    selected = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(result["results"], 1)]
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(selected, mode)
    assert len(selected) <= 6
    assert all(source in candidates or any(source["chunk_id"] == item["chunk_id"] for item in candidates)
               for source in result["results"])
    return result, cat.assess(required_documents=tuple(snapshot.documents.values()) if mode == "comparison" else ())


def test_r01_minority_property_survives_rank_eight(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {"device": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."]},
        "What are the bus voltage and supply voltage ranges?")
    assert any("Supply voltage: 3 to 5 V." in source["text"] for source in result["results"])
    assert all(item["covered"] for item in assessment["obligations"])


def test_r02_comparison_preserves_both_properties_per_document(storage, monkeypatch):
    _, assessment = ranked_case(storage, monkeypatch,
        {"first": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."],
         "second": ["Bus voltage: 0 to 20 V."] * 7 + ["Supply voltage: 2 to 4 V."]},
        "Compare the bus voltage and supply voltage ranges.", "comparison")
    assert len(assessment["obligations"]) == 4
    assert all(item["covered"] for item in assessment["obligations"])


def test_r03_absolute_rating_does_not_replace_recommended_range(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {"device": ["Absolute maximum supply voltage: 8 V."] * 7 + ["Recommended supply voltage: 3 to 5 V."]},
        "What is the recommended supply voltage range?")
    assert any("Recommended supply voltage: 3 to 5 V." in source["text"] for source in result["results"])
    assert all(item["covered"] for item in assessment["obligations"])


def test_r04_requested_condition_survives_unrelated_condition(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {"device": ["Nominal supply voltage: 3.3 V at 25 °C."] * 7 + ["Nominal supply voltage: 3.1 V at 70 °C."]},
        "What is the nominal supply voltage at 70 °C?")
    assert any("3.1 V at 70 °C" in source["text"] for source in result["results"])
    assert all(item["covered"] for item in assessment["obligations"])


def test_r05_conflicting_variant_is_retained(storage, monkeypatch):
    _, assessment = ranked_case(storage, monkeypatch,
        {"device": ["Nominal supply voltage: 2.8 V."] * 7 + ["Nominal supply voltage: 3.2 V."]},
        "What is the nominal supply voltage?")
    assert assessment["conflicts"]
    assert {tuple(fact["values"]) for fact in assessment["matched_relations"]} == {("2.8",), ("3.2",)}


def test_r06_occurrence_duplicates_do_not_erase_document_provenance(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {"first": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."],
         "second": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."]},
        "Compare the bus voltage and supply voltage ranges.", "comparison", duplicates=3)
    occurrences = [(source["generation_id"], source["blocks"][0]["id"]) for source in result["results"]]
    assert len(occurrences) == len(set(occurrences))
    assert all(item["covered"] for item in assessment["obligations"])


def test_r07_required_identifier_is_not_replaced_by_neighbour(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {"device": ["RS9 bus voltage: 0 to 18 V."] * 7 + ["RS90 supply voltage: 9 V.", "RS9 supply voltage: 3 to 5 V."]},
        "What are the RS9 bus voltage and supply voltage ranges?")
    assert any("RS9 supply voltage: 3 to 5 V." in source["text"] for source in result["results"])
    assert all(item["covered"] for item in assessment["obligations"])
    assert not any(fact.get("values") == ["9"] for fact in assessment["matched_relations"])


def test_r08_insufficient_capacity_is_explicit(storage, monkeypatch):
    result, assessment = ranked_case(storage, monkeypatch,
        {f"document{index}": [f"Bus voltage: 0 to {18 + index} V.", f"Supply voltage: 2 to {5 + index} V."]
         for index in range(4)}, "Compare the bus voltage and supply voltage ranges.", "comparison")
    assert len(result["results"]) == 6
    assert any(not item["covered"] for item in assessment["obligations"])
    assert any(warning["code"] == "evidence_coverage_incomplete" for warning in result["warnings"])


def test_swaps_never_erase_previously_retained_conditions(storage, monkeypatch):
    result, _ = ranked_case(storage, monkeypatch,
        {"device": [f"Bus voltage: 0 to 18 V at {index} °C." for index in range(6)] + ["Supply voltage: 3 to 5 V."]},
        "What are the bus voltage and supply voltage ranges?")
    assert len(result["results"]) == 6
    assert all(any(f"at {index} °C" in source["text"] for source in result["results"]) for index in range(6))
    assert result["evidence_selection"]["initial_relation_variants"] == 6
    assert result["evidence_selection"]["missing_relation_variants"] == 1
    assert any(item["code"] == "evidence_coverage_incomplete" for item in result["warnings"])


def test_coverage_verifies_actual_block_before_crediting_a_fact(storage, monkeypatch):
    from services.api.errors import ApiError
    from services.api.evidence_coverage import select_evidence_coverage
    from services.api.retrieval import resolve_references

    question = "What is the supply voltage?"
    result, _ = ranked_case(storage, monkeypatch, {"device": ["Supply voltage: 3.3 V."]}, question)
    search, snapshot, db = library_search(storage)
    sources = copy.deepcopy(result["results"])
    sources[0]["blocks"][0]["text"] = "Supply voltage: 999 V."
    with pytest.raises(ApiError):
        select_evidence_coverage(db, snapshot, question, "question", sources, sources, 6, resolve_references(question))
    assert result["results"][0]["blocks"][0]["text"] == "Supply voltage: 3.3 V."


def test_complementary_selection_preserves_old_proof_and_adds_missing_property(storage, monkeypatch):
    from services.api.retrieval import resolve_references

    question = "What are the bus voltage and supply voltage ranges?"
    result, _ = ranked_case(storage, monkeypatch,
        {"device": ["Bus voltage: 0 to 18 V."] * 7 + ["Supply voltage: 3 to 5 V."]}, question)
    search, snapshot, db = library_search(storage)
    storage[0].profile["enhanced"]["complementary_retrieval"] = True
    chunks = db.rows("SELECT * FROM chunks ORDER BY CAST(substr(parent_id,2) AS INTEGER)")
    prior = [search.resolver.source_for_chunk(dict(chunk), snapshot) for chunk in chunks[:6]]
    extra = search.resolver.source_for_chunk(dict(chunks[-1]), snapshot)
    monkeypatch.setattr(search, "_complementary_candidates", lambda *_args: [extra])
    refined = asyncio.run(search.refine_once(question, snapshot, {**result, "results": prior}, ["supply"],
                                             references=resolve_references(question)))
    assert len(refined["results"]) == 6
    assert any("Bus voltage" in source["text"] for source in refined["results"])
    assert any("Supply voltage" in source["text"] for source in refined["results"])
    assert refined["evidence_selection"]["retained_relation_variants"] == 2
