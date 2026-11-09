"""R04/R05 exacts du manifeste préproduit, séparés des variantes initialement testées.

Textes, ordre, documents, questions et limite de six proviennent du JSON gelé.
Le helper partagé crée de vrais enregistrements SQLite avec extraction, ranking,
embedding et tokenizer explicitement doublés ; aucun PDF réel ni modèle lancé.
Les IDs abstraits A/R1 sont liés aux document/version IDs immuables de la fixture.
"""

import hashlib
import json
from pathlib import Path

import pytest
import test_i4_evidence_coverage as shared
from test_api_storage import storage as storage
from test_enhanced_answers import render

from services.api.structured_answer import StructuredAnswerBuilder

FIXTURE = Path(__file__).parents[1] / "fixtures/production_i4_development.json"
FROZEN_SHA256 = "9b5746385171bb16c40c74c025ee265e134bf4f8265d3e8a7a19caa4574c4752"


@pytest.fixture
def exact_case(monkeypatch):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FROZEN_SHA256
    cases = {case["id"]: case for case in json.loads(FIXTURE.read_text())["cases"]}
    original_library_search = shared.library_search

    def execute(storage, case_id):
        case = cases[case_id]
        assert case["primitive_selected_limit"] == case["expected"]["max_selected"] == 6
        documents = {}
        for source in case["candidates_in_initial_rank_order"]:
            assert source["scope_authorized"] and source["document_version"] == "R1"
            documents.setdefault(source["document_id"], []).append(source["text"])
        document_order = list(documents)
        observed = []

        def ordered_library_search(prepared):
            search, snapshot, db = original_library_search(prepared)
            names = {row["id"]: Path(row["relative_path"]).stem for row in db.rows("SELECT id,relative_path FROM documents")}
            snapshot.generations.sort(key=lambda generation: document_order.index(names[snapshot.documents[generation]]))
            original_search = search.search

            async def verify_rank(question, selected_scope, mode="question", references=None):
                # La même liste figée est relue, sans requête dense supplémentaire.
                initial = await search._candidates(question, selected_scope, mode, references)
                texts = [source["text"] for source in initial]
                assert texts == [source["text"] for source in case["candidates_in_initial_rank_order"]]
                observed.append(texts)
                return await original_search(question, selected_scope, mode, references)

            monkeypatch.setattr(search, "search", verify_rank)
            return search, snapshot, db

        monkeypatch.setattr(shared, "library_search", ordered_library_search)
        result, assessment = shared.ranked_case(storage, monkeypatch, documents, case["question"])
        assert len(observed) == 1
        (storage[0].root / "case-diagnostic.json").write_text(json.dumps({
            "case_id": case_id, "manifest_sha256": FROZEN_SHA256, "question": case["question"],
            "selected": [{key: source[key] for key in ("text", "document_id", "version_id")}
                         for source in result["results"]], "assessment": assessment,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return case, result, assessment

    return execute


def test_manifest_R04_recommended_range_keeps_70_degree_condition(storage, exact_case):
    case, result, assessment = exact_case(storage, "R04")
    required = case["candidates_in_initial_rank_order"][-1]["text"]
    assert any(source["text"] == required for source in result["results"])
    assert assessment["obligations"] and all(item["covered"] for item in assessment["obligations"])
    facts = assessment["matched_relations"]
    assert any(fact["values"] == ["3.5", "4.5"] and "70" in fact["condition"] for fact in facts)
    assert not any(fact["values"] == ["3", "5"] for fact in facts), "La plage25°C ne répond pas à70°C."


def test_manifest_R05_both_documents_keep_conflict_for_same_subject_and_condition(storage, exact_case):
    case, result, assessment = exact_case(storage, "R05")
    required = {source["text"] for source in case["candidates_in_initial_rank_order"]
                if "Supply voltage:" in source["text"]}
    selected = [source for source in result["results"] if source["text"] in required]
    assert {source["text"] for source in selected} == required and len(selected) == 2
    assert len({source["document_id"] for source in selected}) == 2
    assert len({source["version_id"] for source in selected}) == 2
    assert assessment["conflicts"]
    assert {tuple(fact["values"]) for fact in assessment["matched_relations"]} == {("2.8",), ("3.2",)}
    assert all("70" in fact["condition"] for fact in assessment["matched_relations"])
    _, snapshot, db = shared.library_search(storage)
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(result["results"], 1)]
    catalogue = StructuredAnswerBuilder(db, snapshot, case["question"], enforce_contract=True).catalogue(sources, "question")
    answer = render(catalogue)
    assert answer["answer_contract"]["status"] == "conflict"
    assert all(text in answer["text"] for text in required)
    assert "aucune valeur n'est arbitrée" in answer["text"]
