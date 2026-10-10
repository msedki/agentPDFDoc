import asyncio

import pytest
from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage

from services.api.context import ContextBuilder, validate_answer
from services.api.db import json_dump, now, uid
from services.api.query import QueryService
from services.api.retrieval import (
    SearchService,
    contains_identifier,
    identifiers,
    match_expression,
    normalized_identifier,
    resolve_references,
    rrf,
)
from services.api.schemas import QueryRequest, Scope
from services.api.scope import ScopeResolver
from services.api.settings import Settings


def test_retrieval_safe_fts_and_identifiers():
    assert match_expression('CCU-21 " OR * column:') == '"CCU" OR "21" OR "OR" OR "column"'
    assert normalized_identifier("en   50155") == "EN 50155"
    assert set(identifiers("CCU-21, EN 50155, UIC 556, section 4.2")) == {"CCU-21", "EN 50155", "UIC 556", "4.2"}
    assert rrf(["exact"], ["other"], 60)[0][1] == 1 / 61


def test_reference_candidates_preserve_alpha_without_making_prose_obligatory():
    references = resolve_references("Quelle périodicité DA-P01 doit-il avoir avec AB-CD/aa-il ?")
    assert {item.normalized for item in references.candidates} == {"DA-P01", "DOIT-IL", "AB-CD", "AA-IL"}
    assert references.obligations == {"DA-P01": "structured_syntax"}
    assert all(item.ambiguous for item in references.candidates if item.normalized != "DA-P01")
    assert resolve_references("Quelle valeur DA-P99 ?").obligations == {"DA-P99": "structured_syntax"}
    assert resolve_references("Quelle valeur ?", "   ").obligations == {}
    assert resolve_references("Quelle valeur ?", "doit-il").obligations == {"DOIT-IL": "focus.identifier"}
    assert {row["normalized"] for row in resolve_references("P01 EN 50155 section 3.4").as_dict()["obligations"]} == {"P01", "EN 50155", "3.4"}


@pytest.mark.parametrize("focus,source", [("ABC", "ＡＢＣ"), ("fix", "ﬁx"), ("STRASSE", "Straße"),
                                         ("é", "e\u0301"), ("code_bleu", "code_bleu"), ("aa/il", "aa/il")])
def test_focus_unicode_is_found_by_real_search_with_original_source_offsets(storage, focus, source):
    text = "😀 " + source + " : tension nominale 72 V."
    imported, _ = import_fixture(storage, text=text)
    search, snapshot, db = library_search(storage)
    references = resolve_references("Quelle tension nominale ?", focus)
    result = asyncio.run(search.search("Quelle tension nominale ?", snapshot, references=references))
    assert result["results"] and result["results"][0]["exact_identifier"]
    code = normalized_identifier(focus)
    occurrences = result["reference_resolution"]["occurrences"]["retrieval_final"]
    occurrence = next(item for item in occurrences if item["identifier"] == code)
    block = db.one("SELECT * FROM blocks WHERE id=? AND generation_id=?", (occurrence["block_id"], occurrence["generation_id"]))
    assert normalized_identifier(block["text"][occurrence["start_offset"]:occurrence["end_offset"]]) == code
    assert block["text"][occurrence["start_offset"]:occurrence["end_offset"]] == source
    assert occurrence["version_id"] == imported["version_id"] and occurrence["source_text_hash"] == block["source_text_hash"]
    _, retained, metrics, _ = ContextBuilder(storage[0], CharTokenizer()).build("Quelle tension nominale ?", result["results"], references=references)
    assert retained and metrics["exact_identifiers_required"] == [code] and metrics["identifier_coverage_at_context"] == 1


@pytest.mark.parametrize("source", ["XABC", "ABC-X", "ABC_1", "X/ABC", "X.ABC", "ABC.1", "ß"])
def test_focused_bare_reference_does_not_accept_prefix_or_partial_expansion(storage, source):
    import_fixture(storage, text=source + " tension nominale 72 V")
    search, snapshot, _ = library_search(storage)
    references = resolve_references("Quelle tension ?", "S" if source == "ß" else "ABC")
    result = asyncio.run(search.search("Quelle tension ?", snapshot, references=references))
    assert not search.lexical("Quelle tension ?", snapshot, references)[1]
    assert not result["reference_resolution"]["occurrences"]["retrieval_final"]
    assert any(warning["code"] == "identifier_not_found_in_scope" for warning in result["warnings"])


def test_focused_search_scans_authorized_sources_before_any_hit_cap(storage):
    pages = [{"page_index": 0, "width": 595, "height": 842, "blocks":
              [{"id": f"false{i}", "text": "ABC-X tension nominale " * 10} for i in range(30)] +
              [{"id": "true", "text": "ＡＢＣ : tension nominale 72 V."}]},
             {"page_index": 1, "width": 595, "height": 842, "blocks": [{"id": "outside", "text": "outsideOnly : 999 V"}]}]
    imported, _ = import_fixture(storage, pages=pages)
    search, _, _ = library_search(storage)
    snapshot = search.resolver.resolve(Scope(kind="pages", versionId=imported["version_id"], pageStart=0, pageEnd=0))
    references = resolve_references("Quelle tension ?", "ABC")
    result = asyncio.run(search.search("Quelle tension ?", snapshot, references=references))
    assert result["results"][0]["blocks"][0]["id"] == "true"
    excluded = resolve_references("Quelle tension ?", "outsideOnly")
    result = asyncio.run(search.search("Quelle tension ?", snapshot, references=excluded))
    assert not result["reference_resolution"]["occurrences"]["retrieval_final"]
    assert all(source["page_indices"] == [0] for source in result["results"])
    assert any(warning.get("identifier") == "OUTSIDEONLY" for warning in result["warnings"])


def test_alpha_exact_priority_survives_actual_constrained_final_context(storage):
    noise = [{"id": f"noise{i}", "text": f"Tension nominale du circuit voisin {i} " + "alimentation nominale " * 16} for i in range(8)]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": noise +
        [{"id": "upper", "text": "AB-CD : tension nominale 72 V."}, {"id": "lower", "text": "aa-il : tension nominale 110 V."}]}])
    search, snapshot, _ = library_search(storage)
    storage[0].profile["retrieval"] = {"evidence_tokens_by_mode": {"factual": 180}, "max_evidence_llm_tokens": 220}
    question = "Quelle tension nominale pour AB-CD et aa-il ?"
    references = resolve_references(question)
    result = asyncio.run(search.search(question, snapshot, references=references))
    assert len(result["results"]) == 8  # cap historique des plusieurs candidats, pas des obligations seules
    expanded = [search.resolver.expand_parent(source, snapshot, CharTokenizer()) for source in result["results"]]
    _, retained, metrics, warnings = ContextBuilder(storage[0], CharTokenizer()).build(question, expanded, references=references)
    assert all(any(references.matches(source["text"], code) for source in retained) for code in ("AB-CD", "AA-IL"))
    assert metrics["exact_identifiers_required"] == [] and metrics["identifier_coverage_at_context"] is None
    assert metrics["context_fragments_excluded_by_budget"] == 6
    assert not any(warning["code"] == "exact_identifier_not_in_context" for warning in warnings)
    assert {row["identifier"] for row in metrics["reference_resolution"]["occurrences"]["context_final"]} == {"AB-CD", "AA-IL"}


def test_focused_scan_skips_irrelevant_reconstruction_and_stops_at_authorized_cap(storage, monkeypatch):
    blocks = [{"id": f"absent{i}", "text": f"Tension nominale circuit voisin {i}."} for i in range(30)]
    blocks += [{"id": f"focus{i}", "text": f"ＡＢＣ : tension nominale 72 V, repère {i}."} for i in range(32)]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, _ = library_search(storage)
    calls = []
    original = search.resolver.source_for_chunk

    def reconstructed(chunk, scope):
        calls.append(chunk["parent_id"])
        return original(chunk, scope)

    monkeypatch.setattr(search.resolver, "source_for_chunk", reconstructed)
    _, exact = search.lexical("Quelle tension nominale ?", snapshot, resolve_references("Quelle tension nominale ?", "ABC"))
    assert len(exact) == 24 and len(calls) == 24
    assert all(parent.startswith("focus") for parent in calls)
    assert len(set(calls)) == 24  # huit vraies occurrences suivantes ne sont pas reconstruites


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


class FilteringVectors:
    """Double de la recherche filtrée Qdrant : conditions `must`/`any` du snapshot appliquées avant la limite."""
    def __init__(self, points):
        self.points = points

    async def query(self, vector, snapshot, limit=24):
        def kept(payload):
            return all(set(condition["match"]["any"]) & set(payload[condition["key"]] if isinstance(payload[condition["key"]], list) else [payload[condition["key"]]])
                       for condition in snapshot.vector_filter()["must"])
        return [key for key, point in self.points.items() if kept(point["payload"])][:limit]


def page_of(index, blocks):
    return {"page_index": index, "width": 595, "height": 842, "blocks": blocks}


@pytest.mark.parametrize("kind", ["folder", "documents", "pages", "section"])
def test_retrieval_scope_filters_precede_topk_against_dominant_outside_chunks(storage, kind):
    # Plus de concurrents hors périmètre que lexical_top_k et dense_top_k (24), tous mieux classés : un filtre appliqué
    # après la coupe ne laisserait rien ; appliqué avant, il rend les passages autorisés, jusqu'au contexte.
    settings, db, vectors, _ = storage
    noise, _ = import_fixture(storage, path="outside/noise.pdf", pages=[page_of(0, [{"id": f"n{i}", "text": " ".join(["frein"] * 8)} for i in range(30)])])
    target_block = {"id": "t", "text": " ".join(["frein"] + ["voiture"] * 7), "section_id": "s1"}
    rivals = [page_of(i, [{"id": f"c{i}", "text": " ".join(["frein"] * 4 + ["voiture"] * 4)}]) for i in range(1, 31)]
    target, _ = import_fixture(storage, path="allowed/sub/target.pdf", pages=[page_of(0, [target_block])] + rivals,
                               sections=[{"id": "s1", "title": "Freinage", "page_index": 0, "block_ids": ["t"]}])
    resolver = ScopeResolver(db)
    folders = {row["path"]: row["id"] for row in db.rows("SELECT id,path FROM folders")}
    scope = {"folder": Scope(kind="folder", folderId=folders["allowed"], recursive=True),
             "documents": Scope(kind="documents", documentIds=[target["document_id"]]),
             "pages": Scope(kind="pages", versionId=target["version_id"], pageStart=0, pageEnd=0),
             "section": Scope(kind="section", versionId=target["version_id"], sectionId="s1")}[kind]
    snapshot = resolver.resolve(scope)
    search = SearchService(db, resolver, FakeEmbedding(), FilteringVectors(vectors.points), settings)
    outside = set(db.one("SELECT active_generation_id FROM documents WHERE id=?", (noise["document_id"],)).values())
    unfiltered, _ = search.lexical("frein", resolver.resolve(Scope(kind="library")))
    assert len(unfiltered) == 24 and all(db.one("SELECT generation_id FROM chunks WHERE chunk_uuid=?", (chunk,))["generation_id"] in outside for chunk in unfiltered)
    lexical, _ = search.lexical("frein", snapshot)
    dense = asyncio.run(search.vectors.query([0.0], snapshot, 24))
    allowed_pages = {0} if kind in {"pages", "section"} else set(range(31))
    allowed_blocks = {"t"} if kind == "section" else {"t"} | {f"c{i}" for i in range(1, 31)}
    for chunk in lexical + dense:
        assert db.one("SELECT generation_id FROM chunks WHERE chunk_uuid=?", (chunk,))["generation_id"] in snapshot.generations
        sources = db.rows("SELECT page_index,block_id FROM chunk_sources WHERE chunk_uuid=?", (chunk,))
        assert sources and {row["page_index"] for row in sources} <= allowed_pages and {row["block_id"] for row in sources} <= allowed_blocks
    assert lexical and dense
    if kind in {"pages", "section"}:
        assert parents(db, lexical) == parents(db, dense) == ["t"]
    result = asyncio.run(search.search("frein", snapshot))
    expanded = [resolver.expand_parent(source, snapshot, CharTokenizer()) for source in result["results"]]
    _, retained, _, _ = ContextBuilder(settings, CharTokenizer()).build("frein", expanded)
    assert retained and all(source["document_id"] == target["document_id"] for source in expanded + retained)
    assert all(block["page_index"] in allowed_pages and block["id"] in allowed_blocks for source in expanded + retained for block in source["blocks"])


def test_retrieval_exact_survives_rrf_competitors(storage):
    pages = [{"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "exact", "text": "CCU-21 tension = 72 V"}] + [{"id": f"other{i}", "text": f"tension alimentation électrique nominale du circuit {i}"} for i in range(8)]}]
    imported, _ = import_fixture(storage, pages=pages)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="library"))
    exact_chunk = db.one("SELECT chunk_uuid FROM chunks WHERE parent_id='exact'")["chunk_uuid"]
    original_query = vectors.query
    async def competitors(vector, scope, limit=24):
        return [chunk for chunk in await original_query(vector, scope, limit) if chunk != exact_chunk]
    vectors.query = competitors
    search = SearchService(db, resolver, FakeEmbedding(), vectors, settings)
    # Contre-exemple de QUALIFICATION.md §4 : seule occurrence exacte, première en lexical, absente du dense ; sans contrainte,
    # la fusion RRF la classe après les huit voisins présents dans les deux branches, donc hors des six fragments finaux.
    lexical, exact = search.lexical("CCU-21 tension", snapshot)
    dense = asyncio.run(vectors.query([0.0], snapshot))
    assert exact == [exact_chunk] and lexical[0] == exact_chunk and exact_chunk not in dense
    assert [chunk for chunk, _ in rrf(lexical, dense, 60)].index(exact_chunk) >= settings.value("retrieval", "final_max_fragments", 6)
    result = asyncio.run(search.search("CCU-21 tension", snapshot))
    assert any("CCU-21" in source["text"] for source in result["results"])
    # Contrôle après déduplication, expansion de parent et coupe finale du contexte.
    expanded = [resolver.expand_parent(source, snapshot, CharTokenizer()) for source in result["results"]]
    messages, retained, metrics, warnings = ContextBuilder(settings, CharTokenizer()).build("CCU-21 tension", expanded)
    assert metrics["identifier_coverage_states"] == {"CCU-21": "covered"} and any("CCU-21" in source["text"] for source in retained)
    assert "CCU-21 tension = 72 V" in messages[-1]["content"] and not any(warning["code"] == "exact_identifier_not_in_context" for warning in warnings)


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


def test_retrieval_identifiers_keep_maximal_matches_only():
    # Cas réel observé : exact_identifiers_required=['DA-P01','P01'] pour une question sur DA-P01.
    assert identifiers("Quelle valeur pour DA-P01 ?") == ["DA-P01"]
    assert identifiers("CCU-21-A puis P01") == ["CCU-21-A", "P01"]
    assert identifiers("ISO/IEC 27001 et NF EN 50155") == ["EN 50155", "ISO/IEC 27001"]
    assert identifiers("section 3.4.2 et CCU-21.3") == ["3.4.2", "CCU-21.3"]


def test_retrieval_identifier_boundaries_are_symmetric_and_dash_insensitive():
    assert not contains_identifier("Voir DB-P01, DA_P01 et X/P01", "P01")
    assert contains_identifier("Voir P01.", "P01") and contains_identifier("(P01, DA-P01)", "P01")
    assert not contains_identifier("section 3.4.2", "4.2")
    assert contains_identifier("DA‑P01 puis DA–P02", "DA-P01") and contains_identifier("DA-P02", "DA−P02")
    assert identifiers("Tension DA‑P01 ?") == ["DA‑P01"] and normalized_identifier("DA‑P01") == "DA-P01"
    assert identifiers("DA—P01") == ["DA—P01"] and normalized_identifier("da−p01") == "DA-P01"


def test_retrieval_standard_prefixes_are_case_sensitive():
    assert identifiers("en 2020 la tension est passée à 72 V") == []
    assert identifiers("En 2020, selon EN 50155 et UIC 556") == ["EN 50155", "UIC 556"]


def test_retrieval_slash_separates_lists_of_complete_identifiers_only():
    assert identifiers("Modules DA-P01/DA-P02 : 72 V") == ["DA-P01", "DA-P02"]
    assert identifiers("Conforme EN 50155/EN 50121-3-2/EN 50122") == ["EN 50121-3-2", "EN 50122", "EN 50155"]
    assert identifiers("A1/B2/C3") == ["A1", "B2", "C3"]
    assert all(contains_identifier("Modules DA-P01/DA-P02 : 72 V", code) for code in ["DA-P01", "DA-P02"])
    assert all(contains_identifier("Conforme EN 50155/EN 50121-3-2", code) for code in ["EN 50155", "EN 50121-3-2"])
    # « / » de liaison : X, 1, 22 et ISO ne sont pas des identifiants complets.
    assert identifiers("X/P01, 1/P01, CCU-21/22 et ISO/IEC 27001") == ["CCU-21/22", "ISO/IEC 27001", "X/P01"]
    assert not any(contains_identifier("X/P01, 1/P01 et CCU-21/22", code) for code in ["P01", "CCU-21"])
    # Tiret de liaison (décision en attente) : « NF-EN 50155 » reste distinct de EN 50155, contrairement à « NF EN 50155 ».
    assert identifiers("NF-EN 50155") == ["NF-EN 50155"] and not contains_identifier("NF-EN 50155", "EN 50155")
    assert contains_identifier("NF EN 50155", "EN 50155")


def test_retrieval_extracted_identifiers_are_contained_in_their_text():
    # Extraction (index, question) et comparaison partagent les mêmes frontières.
    for text in ["1.P01 : 72 V", "2.CCU-21 voir", "Modules DA-P01/DA-P02", "EN 50155/EN 50121-3-2", "NF-EN 50155", "ISO/IEC 27001",
                 "section 3.4.2 et CCU-21.3", "DA‑P01/DA–P02", "X/P01/Q02"]:
        assert identifiers(text) and all(contains_identifier(text, code) for code in identifiers(text)), text
    # « en » minuscule : norme reconnue à la comparaison sans masquer le numéro de section.
    assert contains_identifier("voir en 3.4.2", "3.4.2") and not contains_identifier("section 3.4.2", "4.2")


def test_retrieval_slash_list_member_is_indexed_found_and_covered(storage):
    # Constat de revue : DA-P02 de « DA-P01/DA-P02 » était déclaré not_found_in_scope alors que le passage était transmis au modèle.
    blocks = [{"id": "list", "text": "Modules DA-P01/DA-P02 : tension nominale 72 V"}, {"id": "norms", "text": "Conforme EN 50155/EN 50121-3-2"},
              {"id": "other", "text": "Tension de secours 24 V"}]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, db = library_search(storage)
    assert {"DA-P01", "DA-P02", "EN 50155", "EN 50121-3-2"} <= {row["normalized"] for row in db.rows("SELECT normalized FROM identifiers")}
    builder = ContextBuilder(storage[0], CharTokenizer())
    for question, code, parent in (("Quelle tension nominale pour DA-P02 ?", "DA-P02", "list"), ("Quelle conformité EN 50121-3-2 ?", "EN 50121-3-2", "norms")):
        _, exact = search.lexical(question, snapshot)
        assert parents(db, exact) == [parent]
        result = asyncio.run(search.search(question, snapshot))
        assert not any(warning["code"] == "identifier_not_found_in_scope" for warning in result["warnings"])
        _, _, metrics, warnings = builder.build(question, result["results"])
        assert metrics["identifier_coverage_states"] == {code: "covered"}
        assert not any(warning["code"] == "exact_identifier_not_in_context" for warning in warnings)


def test_retrieval_rrf_deterministic_ranks_and_spec_counterexample():
    lexical = ["exact"] + [f"l{rank}" for rank in range(2, 10)] + ["both"]
    dense = [f"d{rank}" for rank in range(1, 10)] + ["both", "both"]
    ranked = rrf(lexical, dense, 60)
    scores = dict(ranked)
    assert scores["exact"] == 1 / 61 and scores["l2"] == 1 / 62 and scores["d9"] == 1 / 69
    assert scores["both"] == 1 / 70 + 1 / 70 and 1 / 61 < 2 / 70
    assert [chunk for chunk, _ in ranked[:3]] == ["both", "d1", "exact"]
    assert rrf(["b", "a"], ["a", "b"], 60) == [("a", 1 / 62 + 1 / 61), ("b", 1 / 61 + 1 / 62)]


def library_search(prepared):
    settings, db, vectors, _ = prepared
    resolver = ScopeResolver(db)
    return SearchService(db, resolver, FakeEmbedding(), vectors, settings), resolver.resolve(Scope(kind="library")), db


def parents(db, chunks):
    return [db.one("SELECT parent_id FROM chunks WHERE chunk_uuid=?", (chunk,))["parent_id"] for chunk in chunks]


def test_retrieval_bm25_ranks_denser_chunks_first_on_real_fts5(storage):
    blocks = [{"id": f"d{count}", "text": " ".join(["frein"] * count + ["voiture"] * (8 - count))} for count in (1, 3, 6)]
    blocks += [{"id": f"filler{i}", "text": "voiture roulante confort"} for i in range(5)]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, db = library_search(storage)
    lexical, exact = search.lexical("frein", snapshot)
    assert exact == [] and parents(db, lexical) == ["d6", "d3", "d1"]
    scores = [row["score"] for row in db.rows("SELECT bm25(chunks_fts,2.0,1.0) score FROM chunks_fts WHERE chunks_fts MATCH '\"frein\"' ORDER BY score")]
    assert len(scores) == 3 and scores[0] < scores[1] < scores[2] < 0


def test_retrieval_exact_matches_are_ranked_by_question_bm25(storage):
    blocks = [{"id": f"e{count}", "text": " ".join(["CCU-21"] + ["frein"] * count + ["voiture"] * (6 - count))} for count in range(5)]
    blocks += [{"id": f"filler{i}", "text": "voiture roulante confort"} for i in range(6)]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, db = library_search(storage)
    _, exact = search.lexical("CCU-21 frein", snapshot)
    assert parents(db, exact) == ["e4", "e3", "e2", "e1", "e0"]


def test_retrieval_exact_lane_rechecks_boundaries_of_stale_identifier_rows(storage):
    blocks = [{"id": "neighbour", "text": "DA-P01 tension 72 V"}, {"id": "target", "text": "P01 tension 110 V"}]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, db = library_search(storage)
    neighbour = db.one("SELECT chunk_uuid FROM chunks WHERE parent_id='neighbour'")["chunk_uuid"]
    assert db.one("SELECT 1 FROM identifiers WHERE chunk_uuid=? AND normalized='P01'", (neighbour,)) is None
    # Ligne héritée d'un index construit avant la correction : reindexation nécessaire, sans effet sur la voie exacte.
    db.execute("INSERT INTO identifiers VALUES(?,?,?)", (neighbour, "P01", "P01"))
    _, exact = search.lexical("Quelle tension P01 ?", snapshot)
    assert parents(db, exact) == ["target"]


def test_retrieval_mandatory_identifier_prefers_fragment_with_question_terms(storage):
    blocks = [{"id": "reference", "text": "Voir CCU-21 en annexe B."}, {"id": "answer", "text": "CCU-21 : tension nominale 72 V."}]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    search, snapshot, _ = library_search(storage)
    original = search._candidates
    async def reference_first(question, scope, dense_available=True, references=None):
        return sorted(await original(question, scope, dense_available, references), key=lambda source: source["parent_id"] != "reference")
    search._candidates = reference_first
    result = asyncio.run(search.search("Quelle tension nominale pour CCU-21 ?", snapshot))
    assert result["results"][0]["parent_id"] == "answer" and result["results"][0]["required_identifiers"] == ["CCU-21"]


def test_retrieval_final_selection_drops_duplicate_texts(storage):
    header = "Manuel CCU-21 : consignes de tension"
    pages = [{"page_index": i, "width": 595, "height": 842, "blocks": [{"id": f"h{i}", "text": header}, {"id": f"b{i}", "text": f"tension page {i} valeur {70 + i} V"}]} for i in range(2)]
    import_fixture(storage, pages=pages)
    search, snapshot, _ = library_search(storage)
    texts = [source["text"] for source in asyncio.run(search.search("tension CCU-21", snapshot))["results"]]
    assert header in texts and len(texts) == len(set(texts)) == 3


def test_retrieval_comparison_keeps_identical_text_of_each_document(storage):
    def page():
        return {"page_index": 0, "width": 595, "height": 842, "blocks": [{"id": "b0", "text": "Tension nominale 72 V"}]}
    docs = [import_fixture(storage, path=f"doc{i}.pdf", text=f"doc{i}", pages=[page()])[0]["document_id"] for i in range(2)]
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=docs))
    compared = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("Comparer la tension", snapshot, "comparison"))
    assert sorted(source["document_id"] for source in compared["results"]) == sorted(docs)


def test_retrieval_followup_resolution_uses_maximal_identifiers(storage):
    # Effet sur query.py (relances, l.84 et l.99) sans le modifier : DA-P01 n'engendre plus le référent parasite P01.
    import_fixture(storage, text="DA-P01 tension 72 V et DB-P01 tension 110 V")
    search, snapshot, db = library_search(storage)
    settings = storage[0]
    conversation = uid()
    db.execute("INSERT INTO conversations VALUES(?,?)", (conversation, now()))
    db.execute("INSERT INTO query_runs(id,conversation_id,question,scope_json,snapshot_json,state,created_at,updated_at) VALUES(?,?,?,?,?,'done',?,?)",
               (uid(), conversation, "Quelle tension DA-P01 ?", "{}", json_dump(snapshot.as_dict()), now(), now()))
    service = QueryService(db, search.resolver, search, ContextBuilder(settings, CharTokenizer()), None, settings)
    question, resolution, choices, _ = service.resolve_followup(QueryRequest(question="Et sa tolérance ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
    assert resolution["method"] == "unique_user_referent" and not choices and question.endswith(": DA-P01")
    # « en 2020 » n'est plus une référence explicite : la relance pronominale reste résolue par le référent utilisateur.
    _, resolution, _, _ = service.resolve_followup(QueryRequest(question="Et sa valeur en 2020 ?", scope=Scope(kind="library"), conversation_id=conversation), snapshot)
    assert resolution["method"] == "unique_user_referent"
