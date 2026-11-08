"""I3 evidence conservation on SQLite with explicit synthetic extraction.

The existing embedding/vector/tokenizer doubles do not qualify native OCR,
retrieval models or generation. These tests exercise the production selector,
scopes, table reconstruction and independent catalogue provenance checks.
"""

import asyncio
import copy
import hashlib
import json

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_iteration2_table_evidence import sparse_table
from test_retrieval import CharTokenizer, library_search

from services.api.evidence_selection import MAX_TABLE_NOTE_LINKS, deduplicate_expanded_sources, table_bundle
from services.api.retrieval import (
    MAX_LEXICAL_ALIAS_TERMS,
    evidence_identity,
    lexical_alias_terms,
    ocr_evidence_warnings,
    resolve_references,
)
from services.api.schemas import Scope
from services.api.structured_answer import StructuredAnswerBuilder

HEADERS = [(0, "Parameter"), (1, "Min"), (2, "Max"), (3, "Unit")]


def enabled(settings):
    settings.profile["enhanced"] = {"preserve_evidence": True, "structural_reranking": True,
                                    "complementary_retrieval": True}


def long_parent(storage):
    text = "Supply voltage: 3.3 V. " + "Installation instructions. " * 200 + "Ambient temperature: 10 to 45 °C."
    import_fixture(storage, text=text)
    search, snapshot, _ = library_search(storage)
    return search, snapshot, text


def test_disjoint_long_parent_facts_survive_deduplication_and_bounded_expansion(storage):
    enabled(storage[0])
    search, snapshot, text = long_parent(storage)
    question = "What are the supply voltage and ambient temperature?"
    assert CharTokenizer().count(text) > 900
    candidates = asyncio.run(search._candidates(question, snapshot))
    result = asyncio.run(search.search(question, snapshot))
    expanded = [search.resolver.expand_parent(source, snapshot, CharTokenizer(), 900)
                for source in result["results"]]
    for fact in ("Supply voltage: 3.3 V.", "Ambient temperature: 10 to 45 °C."):
        assert any(fact in item["text"] for item in candidates)
        assert any(fact in item["text"] for item in expanded)
    assert len(result["results"]) <= 6
    assert all(source["text"] != text for source in expanded)


def test_historical_profile_keeps_original_parent_deduplication(storage):
    search, snapshot, _ = long_parent(storage)
    result = asyncio.run(search.search("What are the supply voltage and ambient temperature?", snapshot))
    assert len(result["results"]) == 1


def test_exact_source_occurrences_are_deduplicated_even_with_different_chunk_ids(storage, monkeypatch):
    enabled(storage[0])
    search, snapshot, _ = long_parent(storage)
    candidates = asyncio.run(search._candidates("Supply voltage", snapshot))
    first = candidates[0]
    second = copy.deepcopy(first)
    second["chunk_id"] = "alternate-index-entry"
    assert evidence_identity(first) == evidence_identity(second)

    async def fixed_candidates(*args, **kwargs):
        return [first, second]

    monkeypatch.setattr(search, "_candidates", fixed_candidates)
    result = asyncio.run(search.search("Supply voltage", snapshot))
    assert len(result["results"]) == 1


def test_same_literal_in_two_documents_keeps_each_document_provenance(storage):
    enabled(storage[0])
    first, _ = import_fixture(storage, path="first/manual.pdf", text="Supply voltage: 3.3 V.")
    second, _ = import_fixture(storage, path="second/manual.pdf", text="Supply voltage: 3.3 V.")
    search, _, _ = library_search(storage)
    snapshot = search.resolver.resolve(Scope(kind="documents", documentIds=[first["document_id"], second["document_id"]]))
    result = asyncio.run(search.search("Supply voltage?", snapshot))
    assert {source["document_id"] for source in result["results"]} == {first["document_id"], second["document_id"]}
    assert len({evidence_identity(source) for source in result["results"]}) == 2


def test_distinct_parent_spans_still_obey_final_fragment_limit(storage):
    enabled(storage[0])
    storage[0].profile["retrieval"] = {"final_max_fragments": 2}
    search, snapshot, _ = long_parent(storage)
    result = asyncio.run(search.search("Supply voltage and ambient temperature?", snapshot))
    assert len(result["results"]) == 2
    assert len({evidence_identity(source) for source in result["results"]}) == 2
    assert any("Supply voltage: 3.3 V." in source["text"] for source in result["results"])
    assert any("Ambient temperature: 10 to 45 °C." in source["text"] for source in result["results"])


def test_exact_expanded_parent_is_counted_once_with_all_provenance_and_order(storage):
    enabled(storage[0])
    text = "Supply voltage: 3.3 V. " + "Installation instructions. " * 60 + "Ambient temperature: 10 to 45 °C."
    import_fixture(storage, text=text)
    search, snapshot, _ = library_search(storage)
    result = asyncio.run(search.search("Supply voltage and ambient temperature?", snapshot))
    expanded = [search.resolver.expand_parent(source, snapshot, CharTokenizer(), 900) for source in result["results"]]
    assert len(expanded) > 1 and all(item["text"] == text for item in expanded)
    before = copy.deepcopy(expanded)
    unique = deduplicate_expanded_sources(expanded)
    assert unique == [expanded[0]] and expanded == before
    assert unique[0] is expanded[0]


@pytest.mark.parametrize("changed", ["version_id", "document_id", "generation_id", "extraction_revision_id",
                                      "required_identifiers", "exact_identifiers", "table_context", "extraction_method"])
def test_post_expansion_deduplication_never_erases_different_provenance_or_obligations(storage, changed):
    import_fixture(storage, text="Supply voltage: 3.3 V.")
    search, snapshot, _ = library_search(storage)
    source = asyncio.run(search.search("Supply voltage?", snapshot))["results"][0]
    other = copy.deepcopy(source)
    other["chunk_id"] = "other-chunk"
    if changed in {"required_identifiers", "exact_identifiers"}:
        other[changed] = ["DEVICE-7"]
    elif changed == "table_context":
        other["blocks"][0]["table_context"] = {"unresolved_note_markers": ["1"]}
    elif changed == "extraction_method":
        other["blocks"][0]["extraction_method"] = "ocr"
    else:
        other[changed] = "distinct-source-identity"
    assert deduplicate_expanded_sources([source, other]) == [source, other]


@pytest.mark.parametrize("marker,definition", [("(1)", "(1)"), ("[2]", "Note 2:"), ("*", "*"), ("†", "†")])
def test_explicit_table_note_stays_with_source_row_and_independent_catalogue(storage, marker, definition):
    rows = [HEADERS, [(0, f"Supply voltage {marker}"), (1, "0"), (2, "36"), (3, "V")],
            [(0, f"{definition} Valid only indoors.")], [(0, "(9) Unrelated mounting instruction.")]]
    search, snapshot, source, text = sparse_table(storage, rows)
    original = copy.deepcopy(source)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?")
    assert not warnings and source == original
    assert "Valid only indoors." in bundle["text"]
    assert "Unrelated mounting instruction." not in bundle["text"]
    assert bundle["evidence_bundle"]["tables"][0]["source_rows"] == [0, 1, 2]
    relation = bundle["blocks"][1]["table_context"]
    note = next(item for item in relation["dependencies"] if item["kind"] == "note")
    assert note["row_index"] == 2
    assert text[note["start_offset"]:note["end_offset"]] == note["text"]
    assert relation["source_text_hash"] == hashlib.sha256(text.encode()).hexdigest()
    catalogue = StructuredAnswerBuilder(search.db, snapshot, question="Quelle plage de tension alimentation ?",
                                        enforce_contract=True).catalogue([{**bundle, "source_id": "S001"}], "question")
    reference = next(item for item in catalogue.references if f"Supply voltage {marker}" in item["text"])
    checked = reference["table_context"]
    assert checked["catalogue_verified"]
    note_reference = next(item for item in catalogue.references if "Valid only indoors." in item["text"])
    assert note_reference["id"] in checked["reference_ids"]
    assert note_reference["table_context"]["row_role"] == "note"


@pytest.mark.parametrize("label", ["NOTE", "Notes", "Remarque", "Remarks"])
def test_note_column_role_comes_only_from_an_explicit_geometric_header(storage, label):
    rows = [HEADERS + [(4, label)],
            [(0, "Supply voltage"), (1, "0"), (2, "36"), (3, "V"), (4, "Valid only indoors.")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    note = next(cell for cell in bundle["blocks"][1]["table_context"]["cells"] if cell["column_start"] == 4)
    assert note["text"] == "Valid only indoors."
    assert [header["role"] for header in note["headers"]] == ["note"]


def test_parenthesized_numeric_cell_does_not_manufacture_a_note_reference(storage):
    rows = [HEADERS, [(0, "Supply voltage"), (1, "(36)"), (2, "48"), (3, "V")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    assert not bundle["blocks"][1]["table_context"]["note_markers"]
    assert "(36)" in bundle["text"]


def test_note_referencing_another_note_keeps_transitive_exact_rows(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Valid only indoors; see (2).")], [(0, "(2) Enclosure must remain closed.")]]
    search, snapshot, source, text = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?")
    assert not warnings and bundle["text"] == text
    assert bundle["blocks"][2]["table_context"]["dependencies"][-1]["row_index"] == 3
    relation = bundle["blocks"][1]["table_context"]
    assert {item["row_index"] for item in relation["dependencies"] if item["kind"] == "note"} == {2, 3}


def test_unresolved_note_in_a_linked_note_limits_the_original_row(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Valid only indoors; see (2).")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?")
    assert any(item["code"] == "table_note_unresolved" for item in warnings)
    assert bundle["blocks"][1]["table_context"]["unresolved_note_markers"] == ["2"]


def test_cyclic_notes_are_bounded_and_keep_both_exact_texts(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Valid only indoors; see (2).")], [(0, "(2) Enclosure must remain closed; see (1).")]]
    search, snapshot, source, text = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and bundle["text"] == text
    assert len(bundle["blocks"]) == 4


def test_missing_note_is_explicit_without_importing_unrelated_text(storage):
    rows = [HEADERS, [(0, "Supply voltage (2)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Unrelated mounting instruction.")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?")
    assert "Unrelated mounting instruction." not in bundle["text"]
    warning = next(item for item in warnings if item["code"] == "table_note_unresolved")
    assert warning["markers"] == ["2"]
    assert bundle["blocks"][1]["table_context"]["unresolved_note_markers"] == ["2"]


def test_conflicting_note_labels_preserve_candidates_without_choosing_one(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Valid only indoors.")], [(0, "(1) Valid only outdoors.")]]
    search, snapshot, source, text = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?")
    assert bundle["text"] == text
    assert any(item["code"] == "table_note_ambiguous" for item in warnings)
    assert bundle["blocks"][1]["table_context"]["ambiguous_note_markers"] == ["1"]


def test_note_lookup_respects_literal_selection(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) OUTSIDE-SECRET condition.")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    block = source["blocks"][0]
    selected = search.resolver.resolve(Scope(kind="selection", versionId=source["version_id"], spans=[{
        "extractionRevisionId": source["extraction_revision_id"], "blockId": block["id"],
        "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point",
        "startOffset": block["start_offset"], "endOffset": block["end_offset"]}]))
    bundle, warnings = table_bundle(search.db, selected, source, question="Quelle plage de tension alimentation ?")
    assert bundle is source
    assert "OUTSIDE-SECRET" not in str(bundle)
    assert any(item["code"] == "table_context_limited_by_selection" for item in warnings)


def test_note_and_row_never_silently_exceed_bundle_budget(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
            [(0, "(1) Valid only indoors. " + "Necessary condition. " * 50)]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension alimentation ?", maximum_chars=100)
    assert bundle is source and "evidence_bundle" not in bundle
    assert any(item["code"] == "table_evidence_bundle_too_large" for item in warnings)


def test_final_bundle_budget_preserves_unresolved_note_warning(storage):
    rows = [HEADERS, [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")]]
    search, snapshot, source, text = sparse_table(storage, rows, section_title="Recommended operating conditions")
    bundle, warnings = table_bundle(search.db, snapshot, source, maximum_chars=len(text) + 1)
    assert bundle is source
    assert {item["code"] for item in warnings} >= {"table_note_unresolved", "table_evidence_bundle_too_large"}


def test_note_dependency_bound_is_reported_without_building_unbounded_links(storage):
    markers = " ".join(f"({index})" for index in range(1, MAX_TABLE_NOTE_LINKS + 2))
    rows = [HEADERS, [(0, "Supply voltage " + markers), (1, "0"), (2, "36"), (3, "V")]]
    search, snapshot, source, _ = sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert any(item["code"] == "table_note_verification_limit" for item in warnings)
    relation = bundle["blocks"][1]["table_context"]
    assert not relation["note_scan_complete"]
    assert not any(item["kind"] == "note" for item in relation["dependencies"])


def partial_empty(storage, path="partial/manual.pdf"):
    imported, _ = import_fixture(storage, path=path,
                                 pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": []}])
    generation = storage[1].one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"]
    storage[1].execute("UPDATE index_generations SET state='ready_partial',coverage_json=? WHERE id=?",
                       (json.dumps({"total": 2, "processed": 1, "unresolved": 1}), generation))
    return imported, generation


def test_partial_scope_without_any_retrieved_text_keeps_revision_warning(storage):
    enabled(storage[0])
    imported, generation = partial_empty(storage)
    search, snapshot, db = library_search(storage)
    result = asyncio.run(search.search("Quelle température ?", snapshot))
    assert not result["results"]
    notices = [item for item in result["warnings"] if item["code"] == "partial_extraction"]
    assert len(notices) == 1
    assert notices[0]["document_id"] == imported["document_id"]
    assert notices[0]["version_id"] == imported["version_id"]
    assert notices[0]["generation_id"] == generation
    assert notices[0]["extraction_revision_id"] == db.one("SELECT extraction_revision_id FROM index_generations WHERE id=?", (generation,))["extraction_revision_id"]


def test_partial_document_without_results_remains_visible_next_to_complete_result(storage):
    enabled(storage[0])
    incomplete, _ = partial_empty(storage)
    complete, _ = import_fixture(storage, path="complete/manual.pdf", text="Ambient temperature: 10 to 45 °C.")
    search, snapshot, _ = library_search(storage)
    result = asyncio.run(search.search("Ambient temperature?", snapshot))
    assert {item["document_id"] for item in result["results"]} == {complete["document_id"]}
    assert any(item["code"] == "partial_extraction" and item["document_id"] == incomplete["document_id"] for item in result["warnings"])


def test_partial_warning_does_not_disclose_document_outside_scope(storage):
    outside, _ = partial_empty(storage, path="OUTSIDE-SECRET/partial.pdf")
    complete, _ = import_fixture(storage, path="allowed/manual.pdf", text="Ambient temperature: 10 to 45 °C.")
    search, _, _ = library_search(storage)
    snapshot = search.resolver.resolve(Scope(kind="documents", documentIds=[complete["document_id"]]))
    result = asyncio.run(search.search("Ambient temperature?", snapshot))
    assert not any(item["code"] == "partial_extraction" for item in result["warnings"])
    assert outside["document_id"] not in str(result) and "OUTSIDE-SECRET" not in str(result)


def test_historical_partial_revision_is_not_confused_with_new_complete_version(storage):
    old, generation = partial_empty(storage)
    complete, _ = import_fixture(storage, path="partial/manual.pdf", text="Ambient temperature: 10 to 45 °C.")
    search, active, db = library_search(storage)
    revision = db.one("SELECT extraction_revision_id FROM index_generations WHERE id=?", (generation,))["extraction_revision_id"]
    historical = search.resolver.resolve(Scope(kind="pages", versionId=old["version_id"],
                                               extractionRevisionId=revision, pageStart=0, pageEnd=0))
    old_result = asyncio.run(search.search("Ambient temperature?", historical))
    active_result = asyncio.run(search.search("Ambient temperature?", active))
    assert complete["version_id"] != old["version_id"]
    assert any(item["code"] == "partial_extraction" and item["version_id"] == old["version_id"] for item in old_result["warnings"])
    assert not any(item["code"] == "partial_extraction" for item in active_result["warnings"])


@pytest.mark.parametrize("heading_allowed", [True, False])
def test_bundle_ocr_methods_are_recomputed_from_effective_scoped_blocks(storage, heading_allowed):
    def native(block):
        block["metadata"]["extraction_method"] = "native"

    rows = [HEADERS, [(0, "Supply voltage"), (1, "0"), (2, "36"), (3, "V")]]
    search, snapshot, source, _ = sparse_table(storage, rows, mutate=native,
                                             section_title="Recommended operating conditions")
    metadata = json.loads(search.db.one("SELECT metadata_json FROM blocks WHERE id='explicit-heading'")["metadata_json"])
    metadata["metadata"] = {"extraction_method": "ocr"}
    search.db.execute("UPDATE blocks SET metadata_json=? WHERE id='explicit-heading'", (json.dumps(metadata),))
    if not heading_allowed:
        snapshot.block_ids = ["sparse-table"]
    bundle, _ = table_bundle(search.db, snapshot, source)
    assert bundle["extraction_methods"] == (["native", "ocr"] if heading_allowed else ["native"])
    assert bool(ocr_evidence_warnings([bundle])) is heading_allowed
    assert ("Recommended operating conditions" in bundle["text"]) is heading_allowed


@pytest.mark.parametrize("question,text", [
    ("Quelle tension ?", "Supply voltage: 3.3 V."),
    ("Quels courants ?", "Input current: 2 mA."),
    ("Quelle alimentation ?", "Supply voltage: 3.3 V."),
    ("Quelles entrées ?", "Input current: 2 mA."),
    ("Quelles sorties ?", "Output current: 4 mA."),
    ("What supply?", "Alimentation : 3,3 V."),
    ("What voltage?", "Tension nominale : 3,3 V."),
])
def test_static_lexical_alias_fallback_ablation_on_same_sources(storage, question, text):
    import_fixture(storage, text=text)
    search, snapshot, db = library_search(storage)
    references = resolve_references(question)
    original_references = copy.deepcopy(references.as_dict())
    assert search.lexical(question, snapshot, references) == ([], [])
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    recovered, exact = search.lexical(question, snapshot, references)
    assert len(recovered) == 1 and exact == []
    assert db.one("SELECT text FROM chunks WHERE chunk_uuid=?", (recovered[0],))["text"] == text
    assert references.original_question == question and references.as_dict() == original_references
    storage[0].profile["enhanced"]["lexical_alias_fallback"] = False
    assert search.lexical(question, snapshot, references) == ([], [])


def test_alias_fallback_does_not_change_a_nonempty_initial_lexical_lane(storage, monkeypatch):
    french, _ = import_fixture(storage, path="french.pdf", text="Tension nominale : 3,3 V.")
    import_fixture(storage, path="english.pdf", text="Supply voltage: 7 V.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, snapshot, db = library_search(storage)
    events = []
    monkeypatch.setattr("services.api.retrieval.record_event", lambda *args, **kwargs: events.append(args))
    ranked, exact = search.lexical("Quelle tension ?", snapshot)
    assert len(ranked) == 1 and exact == [] and events == []
    assert db.one("SELECT version_id FROM chunks WHERE chunk_uuid=?", (ranked[0],))["version_id"] == french["version_id"]


def test_alias_fallback_does_not_change_an_exact_only_lane(storage, monkeypatch):
    import_fixture(storage, text="Opaque ＡＢＣ.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, snapshot, _ = library_search(storage)
    events = []
    monkeypatch.setattr("services.api.retrieval.record_event", lambda *args, **kwargs: events.append(args))
    ranked, exact = search.lexical("Quelle tension ?", snapshot, resolve_references("Quelle tension ?", "ABC"))
    assert len(exact) == 1 and ranked == exact and events == []


@pytest.mark.parametrize("kind", ["documents", "pages", "section"])
def test_alias_fallback_cannot_search_beyond_document_page_or_section(storage, kind):
    pages = [{"page_index": 0, "width": 595, "height": 842,
              "blocks": [{"id": "inside", "text": "Opaque enclosure.", "section_id": "s1"}]}]
    if kind != "documents":
        pages.append({"page_index": 1, "width": 595, "height": 842,
                      "blocks": [{"id": "outside-page", "text": "Supply voltage: 99 V."}]})
    allowed, _ = import_fixture(storage, path="allowed.pdf", pages=pages,
                                sections=[{"id": "s1", "title": "Enclosure", "page_index": 0, "block_ids": ["inside"]}])
    import_fixture(storage, path="outside.pdf", text="Supply voltage: 999 V.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, _, _ = library_search(storage)
    scopes = {"documents": Scope(kind="documents", documentIds=[allowed["document_id"]]),
              "pages": Scope(kind="pages", versionId=allowed["version_id"], pageStart=0, pageEnd=0),
              "section": Scope(kind="section", versionId=allowed["version_id"], sectionId="s1")}
    assert search.lexical("Quelle alimentation ?", search.resolver.resolve(scopes[kind])) == ([], [])


@pytest.mark.parametrize("question", ["電源仕様を示して", "Δώστε τις προδιαγραφές", "Describe tensionless behavior", "Quelle transconductance ?"])
def test_unknown_terms_do_not_trigger_a_search_alias(storage, question, monkeypatch):
    import_fixture(storage, text="Supply voltage: 3.3 V.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, snapshot, _ = library_search(storage)
    events = []
    monkeypatch.setattr("services.api.retrieval.record_event", lambda phase, data: events.append((phase, data)))
    assert lexical_alias_terms(question) == []
    assert search.lexical(question, snapshot) == ([], [])
    assert len(events) == 1 and events[0][1]["reason"] == "no_known_alias"
    assert not events[0][1]["attempted"]


def test_lexical_aliases_are_bounded_static_words_and_exclude_identifiers():
    from services.api.evidence_selection import TERM_GROUPS

    assert lexical_alias_terms("Quelle valeur TENSION-42 SUPPLY_7 750 ?") == []
    question = "Tensions courants alimentations entrées sorties températures plages minimales maximales conditions"
    aliases = lexical_alias_terms(question)
    assert len(aliases) == MAX_LEXICAL_ALIAS_TERMS and len(set(aliases)) == len(aliases)
    assert all(word.isalpha() for word in aliases)
    assert set(aliases) <= set().union(*TERM_GROUPS)
    assert aliases == lexical_alias_terms(question)


def test_alias_fallback_preserves_missing_reference_obligations(storage):
    import_fixture(storage, text="Supply voltage: 3.3 V.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, snapshot, _ = library_search(storage)
    references = resolve_references("Quelle tension pour CCU-99 ?")
    before = copy.deepcopy(references.as_dict())
    ranked, exact = search.lexical(references.original_question, snapshot, references)
    assert ranked and exact == []
    assert references.as_dict() == before and references.obligations == {"CCU-99": "structured_syntax"}


def test_alias_fallback_caps_candidates_and_final_fragments_and_records_route(storage, monkeypatch):
    blocks = [{"id": f"row-{index}", "text": f"Supply voltage: {index} V."} for index in range(8)]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}])
    enabled(storage[0])
    storage[0].profile["enhanced"]["lexical_alias_fallback"] = True
    storage[0].profile["retrieval"] = {"lexical_top_k": 3, "final_max_fragments": 2}
    search, snapshot, _ = library_search(storage)
    events = []
    monkeypatch.setattr("services.api.retrieval.record_event", lambda phase, data: events.append((phase, data)))

    async def empty_dense(*args, **kwargs):
        return []

    monkeypatch.setattr(search.vectors, "query", empty_dense)
    question = "Quelle alimentation ?"
    result = asyncio.run(search.search(question, snapshot))
    assert len(result["top10"]) == 3 and len(result["results"]) == 2
    assert len(events) == 1 and events[0][0] == "retrieval.lexical_alias_fallback"
    event = events[0][1]
    assert event["attempted"] and event["reason"] == "initial_lexical_empty"
    assert event["alias_terms"] == ["supply"] and event["candidate_count"] == event["limit"] == 3
    assert event["question_sha256"] == hashlib.sha256(question.encode()).hexdigest()


def test_alias_fallback_preserves_literal_selection(storage, monkeypatch):
    import_fixture(storage, text="Opaque. Supply voltage: 3.3 V.")
    storage[0].profile["enhanced"] = {"lexical_alias_fallback": True}
    search, snapshot, db = library_search(storage)
    block = db.one("SELECT * FROM blocks WHERE generation_id=?", (snapshot.generations[0],))
    selected = search.resolver.resolve(Scope(kind="selection", versionId=snapshot.versions[snapshot.generations[0]], spans=[{
        "extractionRevisionId": block["extraction_revision_id"], "blockId": block["id"],
        "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point",
        "startOffset": 0, "endOffset": 7}]))
    events = []
    monkeypatch.setattr("services.api.retrieval.record_event", lambda *args, **kwargs: events.append(args))
    result = asyncio.run(search.search("Quelle tension ?", selected))
    assert [source["text"] for source in result["results"]] == ["Opaque."]
    assert events == []
