"""Real SQLite/catalogue with injected rank, vectors and native-text extraction."""

from types import SimpleNamespace

from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_retrieval import library_search

from services.api.evidence_coverage import quantitative_relation_keys, select_evidence_coverage
from services.api.structured_answer import StructuredAnswerBuilder


def test_qualitative_proof_survives_an_extra_numeric_variant_at_same_capacity(storage):
    _, db, _, _ = storage
    texts = ["DEV728 supply voltage: 2.1 V to 4.6 V.",
             "DEV728 has debounce, which prevents repeated alarms.",
             "DEV728 supply voltage: 2.3 V to 4.8 V."]
    import_fixture(storage, path="DEV728.pdf", text="\n".join(texts), pages=[{
        "page_index": 0, "width": 595, "height": 842,
        "blocks": [{"id": f"b{index}", "text": text,
                    "metadata": {"extraction_method": "native", "ocr_used": False}}
                   for index, text in enumerate(texts)]}])
    search, snapshot, _ = library_search(storage)
    rows = db.rows("SELECT * FROM chunks ORDER BY parent_id")
    candidates = [search.resolver.source_for_chunk(dict(row), snapshot) for row in rows]
    question = "What is DEV728 supply voltage range and what is the purpose of debounce?"
    references = SimpleNamespace(priority=[], source_matches=lambda *_: False)
    retained, warnings, diagnostic = select_evidence_coverage(
        db, snapshot, question, "question", candidates, candidates[:2], 2, references)
    assert len(retained) == 2
    assert any("prevents repeated alarms" in source["text"] for source in retained)
    assert any("2.1 V to 4.6 V" in source["text"] for source in retained)
    assert diagnostic["missing_relation_variants"] == 1
    assert any(warning["code"] == "evidence_coverage_incomplete" for warning in warnings)
    identified = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(retained)]
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(identified, "question")
    assessment = cat.assess()
    assert len(assessment["obligations"]) == 2
    assert all(item["covered"] for item in assessment["obligations"])
    facts = [*assessment["matched_relations"], *assessment["matched_qualitative_relations"]]
    assert {item["kind"] for item in facts} == {"interval", "qualitative_literal"}
    assert len(quantitative_relation_keys(cat, "question")) == 2


def test_two_qualitative_meanings_cannot_share_one_coverage_atom():
    from services.api.evidence_coverage import _relation_key

    base = {"kind": "qualitative_literal", "document_id": "d", "version_id": "v",
            "subject": "debounce", "predicate": "function", "intent": "function",
            "quote": "Debounce prevents repeated alarms.", "negative": False}
    assert _relation_key(base) != _relation_key({**base, "quote": "Debounce prevents short pulses."})
    assert _relation_key(base) != _relation_key({**base, "negative": True})
