"""A guarantee remains attached to a proof during real catalogue selection.

The ranking, native text layer and vector transport are explicit unit doubles.
SQLite, obligation construction, replacement and publication remain real.
"""

from types import SimpleNamespace

from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_retrieval import library_search

from services.api.evidence_coverage import quantitative_relation_keys, select_evidence_coverage
from services.api.structured_answer import StructuredAnswerBuilder


def scope(storage, texts):
    _, db, _, _ = storage
    import_fixture(storage, path="DEV728.pdf", text="\n".join(texts), pages=[{
        "page_index": 0, "width": 595, "height": 842,
        "blocks": [{"id": f"b{index}", "text": text,
                    "metadata": {"extraction_method": "native", "ocr_used": False}}
                   for index, text in enumerate(texts)]}])
    search, snapshot, _ = library_search(storage)
    rows = db.rows("SELECT * FROM chunks ORDER BY parent_id")
    candidates = [search.resolver.source_for_chunk(dict(row), snapshot) for row in rows]
    return db, snapshot, candidates


def test_guaranteed_requirement_replaces_an_unqualified_candidate_at_the_same_capacity(storage):
    texts = ["DEV728 operating voltage range: 1.9 V to 4.7 V.",
             "DEV728 guaranteed operating voltage range: 1.9 V to 4.7 V."]
    db, snapshot, candidates = scope(storage, texts)
    question = "What is DEV728 guaranteed operating voltage range?"
    retained, warnings, diagnostic = select_evidence_coverage(
        db, snapshot, question, "question", candidates, candidates[:1], 1,
        SimpleNamespace(priority=[], source_matches=lambda *_: False))
    assert len(retained) == 1 and texts[1] in retained[0]["text"]
    assert not warnings and diagnostic["retained_covered_obligations"] == 1
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(
        [{**retained[0], "source_id": "S001"}], "question")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["obligations"][0]["guarantee_required"]
    assert result["answer_contract"]["matched_relations"][0]["guarantee"] == "explicit"
    assert texts[1] in result["text"] and cat.verify_rendered(result)["status"] == "passed"


def test_additional_relation_cannot_replace_a_guaranteed_proof_by_an_unqualified_copy(storage):
    texts = ["DEV728 operating current range: 1 A to 2 A.",
             "DEV728 guaranteed operating voltage range: 1.9 V to 4.7 V.",
             "DEV728 operating voltage range: 1.9 V to 4.7 V. "
             "DEV728 operating current range: 1 A to 2 A. "
             "DEV728 operating current range: 3 A to 4 A."]
    db, snapshot, candidates = scope(storage, texts)
    question = "What are DEV728 operating voltage and operating current ranges?"
    retained, warnings, diagnostic = select_evidence_coverage(
        db, snapshot, question, "question", candidates, candidates[:2], 2,
        SimpleNamespace(priority=[], source_matches=lambda *_: False))
    # The compound source may replace the redundant current source. It cannot
    # replace the guarantee just because another source has the same numbers.
    assert len(retained) == 2
    assert any(texts[1] in item["text"] for item in retained)
    assert any(texts[2] in item["text"] for item in retained)
    assert not warnings and diagnostic["missing_relation_variants"] == 0
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(
        [{**item, "source_id": f"S{index:03d}"} for index, item in enumerate(retained, 1)], "question")
    assert len(quantitative_relation_keys(cat, "question")) == 4
    result = render(cat)
    assert result["answer_contract"]["status"] == "conflict"
    assert "guaranteed operating voltage" in result["text"]
    assert "1 A to 2 A" in result["text"] and "3 A to 4 A" in result["text"]
