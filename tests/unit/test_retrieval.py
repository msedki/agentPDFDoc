import asyncio

from services.api.context import ContextBuilder, validate_answer
from services.api.retrieval import SearchService, contains_identifier, identifiers, match_expression, normalized_identifier, rrf
from services.api.scope import ScopeResolver
from services.api.schemas import Scope
from services.api.settings import Settings

from test_api_storage import FakeEmbedding, import_fixture, storage


def test_retrieval_safe_fts_and_identifiers():
    assert match_expression('CCU-21 " OR * column:') == '"CCU" OR "21" OR "OR" OR "column"'
    assert normalized_identifier("en   50155") == "EN 50155"
    assert set(identifiers("CCU-21, EN 50155, UIC 556, section 4.2")) == {"CCU-21", "EN 50155", "UIC 556", "4.2"}
    assert rrf(["exact"], ["other"], 60)[0][1] == 1 / 61


def test_retrieval_scope_filters_precede_topk(storage):
    imported, _ = import_fixture(storage, "allowed/one.pdf", "CCU-21 tension 72 V")
    import_fixture(storage, "outside/one.pdf", "CCU-21 " * 100 + "tension 999 V")
    settings, db, vectors, indexer = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))
    search = SearchService(db, resolver, FakeEmbedding(), vectors, settings)
    lexical, exact = search.lexical("CCU-21 tension", snapshot)
    assert lexical and exact
    assert all(db.one("SELECT generation_id FROM chunks WHERE chunk_uuid=?", (chunk,))["generation_id"] in snapshot.generations for chunk in lexical)
    result = asyncio.run(search.search("CCU-21 tension", snapshot))
    assert result["results"] and all(row["document_id"] == imported["document_id"] for row in result["results"])


def test_retrieval_exact_survives_rrf_competitors(storage):
    pages = [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "exact", "text": "CCU-21 tension = 72 V"}] + [{"id": f"other{i}", "text": "tension alimentation électrique nominale"} for i in range(8)]}]
    imported, _ = import_fixture(storage, pages=pages)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="library"))
    exact_chunk = db.one("SELECT chunk_uuid FROM chunks WHERE parent_id='exact'")["chunk_uuid"]
    original_query = vectors.query
    async def competitors(vector, scope, limit=24):
        return [chunk for chunk in await original_query(vector, scope, limit) if chunk != exact_chunk]
    vectors.query = competitors
    result = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("CCU-21 tension", snapshot))
    assert any("CCU-21" in source["text"] for source in result["results"])


class CharTokenizer:
    def count(self, text):
        return len(text) // 4 + 1
    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)


def test_retrieval_context_extends_budget_for_required_identifier(tmp_path):
    settings = Settings(tmp_path)
    builder = ContextBuilder(settings, CharTokenizer())
    source = {"version_id": "v", "page_indices": [0], "text": "CCU-21 valeur 72 V " + "x " * 3500, "exact_identifier": True}
    messages, retained, metrics, warnings = builder.build("Quelle valeur CCU-21 ?", [source])
    assert retained and metrics["evidence_budget"] > 1536
    assert "CCU-21" in messages[-1]["content"]
    assert metrics["evidence_coverage_at_context"] == 1


def test_retrieval_unknown_citations_and_active_html_are_removed():
    text, warnings = validate_answer('<script>alert(1)</script> Réponse [S001] [S999] ![x](https://external/x)', ["S001"])
    assert "<script>" not in text and "https://external" not in text
    assert "[S001]" in text and "[S999]" not in text
    assert warnings[0]["source_ids"] == ["S999"]


def test_retrieval_exact_codes_do_not_match_close_variants():
    assert contains_identifier("CCU-21.", "CCU-21")
    assert not contains_identifier("CCU-210 CCU-21-A", "CCU-21")
    assert not contains_identifier("EN 50155-1", "EN 50155")
    assert contains_identifier("en   50155 : validé", "EN 50155")


def test_retrieval_two_ids_survive_same_long_parent(storage):
    text = "CCU-21 72 V " + "alimentation " * 160 + " CCU-22 110 V"
    import_fixture(storage, text=text)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="library"))
    result = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("CCU-21 et CCU-22 tension", snapshot))
    assert all(any(contains_identifier(source["text"], code) for source in result["results"]) for code in ["CCU-21", "CCU-22"])
    assert len(result["results"]) <= 8


def test_retrieval_four_document_comparison_and_absent_id(storage):
    docs = [import_fixture(storage, path=f"doc{i}.pdf", text=f"CCU-{i+21} tension {72+i} V")[0]["document_id"] for i in range(4)]
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=docs))
    search = SearchService(db, resolver, FakeEmbedding(), vectors, settings)
    compared = asyncio.run(search.search("Comparer la tension", snapshot, "comparison"))
    assert set(source["document_id"] for source in compared["results"]) == set(docs)
    absent = asyncio.run(search.search("Quelle tension CCU-999 ?", snapshot))
    assert any(warning["code"] == "identifier_not_found_in_scope" for warning in absent["warnings"])


def test_retrieval_final_budget_cut_is_reported(tmp_path):
    settings = Settings(tmp_path, {"llm": {"num_ctx": 450, "num_predict": 100}, "retrieval": {"context_safety_tokens": 50}})
    source = {"version_id": "v", "page_indices": [0], "text": "CCU-21 " + "x" * 4000, "exact_identifier": True}
    _, retained, metrics, warnings = ContextBuilder(settings, CharTokenizer()).build("Quelle valeur CCU-21 ?", [source])
    assert not retained
    assert metrics["identifier_coverage_states"]["CCU-21"] == "not_covered_due_to_budget"
    assert metrics["evidence_coverage_at_context"] == 0
    assert any(warning["code"] == "exact_identifier_not_in_context" for warning in warnings)


def test_retrieval_parent_expansion_clips_multiple_page_sources(storage):
    pages = [{"page_index": i, "width": 595, "height": 842, "blocks": [{"id": f"b{i}", "text": text}]} for i, text in enumerate(["CCU-21 autorisé 72 V", "CCU-22 hors scope 999 V"])]
    imported, _ = import_fixture(storage, pages=pages)
    _, db, _, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="pages", versionId=imported["version_id"], pageStart=0, pageEnd=0))
    chunk = db.one("SELECT * FROM chunks WHERE parent_id='b0'")
    db.execute("INSERT INTO chunk_sources VALUES(?,?,?,?,?,?)", (chunk["chunk_uuid"], "b1", 1, 0, len(pages[1]["blocks"][0]["text"]), 1))
    source = resolver.source_for_chunk(chunk, snapshot)
    expanded = resolver.expand_parent(source, snapshot, CharTokenizer())
    assert expanded["page_indices"] == [0] and "999" not in expanded["text"]
    assert all(block["page_index"] == 0 for block in expanded["blocks"])
