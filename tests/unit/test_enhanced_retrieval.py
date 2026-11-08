"""Real OOXML/SQLite source evidence; embedding/vector/token counts use named doubles."""

import asyncio
import copy
import hashlib
import json

import pytest
from openpyxl import Workbook
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer, library_search

from services.api.context import ContextBuilder
from services.api.errors import ApiError
from services.api.evidence_selection import prepare_tables, structural_rerank, table_bundle
from services.api.schemas import Scope
from services.api.scope import ScopeResolver
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.office.pipeline import extract_office


def range_fixture(rag, *, outside="OUTSIDE-SECRET", long=False, columns=6):
    settings, db, _, indexer, resolver, _ = rag
    path = settings.data_dir / "originals" / (hashlib.sha256(outside.encode()).hexdigest() + ".xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Mesures"
    sheet.append([outside] * columns)
    for column in range(1, columns + 1):
        sheet.cell(5, column, "Minimum" if column == 1 else 0)
        sheet.cell(6, column, "Maximum" if column == 1 else 36)
    sheet["C5"], sheet["C6"] = "V", "V"
    sheet["D5"], sheet["D6"] = False, True
    sheet["E5"], sheet["E6"] = "=B5+B6", "sans calcul"
    sheet["F5"], sheet["F6"] = ("long text " * 1000) if long else "25 °C", "36"
    sheet["G5"] = outside
    book.save(path)
    book.close()
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extractions" / imported["version_id"], {}, imported["version_id"], "xlsx")
    asyncio.run(indexer.index(imported["job_id"], extraction))
    snapshot = resolver.resolve(Scope(kind="cell_range", versionId=imported["version_id"],
        extractionRevisionId=extraction["extraction_revision_id"], sheetId=extraction["units"][0]["id"],
        rowStart=5, rowEnd=6, columnStart=1, columnEnd=6))
    return snapshot


def enable(settings, **kwargs):
    settings.profile["enhanced"] = {"preserve_evidence": True, "structural_reranking": True, **kwargs}


def test_explicit_range_keeps_zero_36_boolean_and_uncached_formula_without_embedding(rag):
    snapshot = range_fixture(rag)
    settings, db, embedding, _, _, search = rag
    question = "Indiquer les valeurs maximum et le minimum de la plage."
    baseline = asyncio.run(search.search(question, snapshot))
    baseline_addresses = {fact["address"] for source in baseline["results"] for fact in source["cell_facts"]}
    assert len(baseline_addresses) < 12  # The original final top-k selects individual cells.
    enable(settings)
    embedding.submitted.clear()
    result = asyncio.run(search.search(question, snapshot))
    assert embedding.submitted == []
    assert len(result["results"]) == 1
    source = result["results"][0]
    assert source["evidence_bundle"]["cell_addresses"] == [f"{col}{row}" for row in (5, 6) for col in "ABCDEF"]
    assert source["locator"]["cell_range"] == "A5:F6"
    assert "B5 (value) : 0" in source["text"] and "B6 (value) : 36" in source["text"]
    facts = {fact["address"]: fact for fact in source["cell_facts"]}
    assert facts["D5"]["value_kind"] == "boolean" and facts["D6"]["value_kind"] == "boolean"
    assert facts["E5"]["formula_present"] and not facts["E5"]["cached_present"]
    assert "OUTSIDE-SECRET" not in json.dumps(result)
    for block in source["blocks"]:
        parent = db.one("SELECT text,source_text_hash FROM blocks WHERE generation_id=? AND id=?", (source["generation_id"], block["id"]))
        assert parent["text"][block["start_offset"]:block["end_offset"]] == block["text"]
        assert hashlib.sha256(parent["text"].encode()).hexdigest() == block["source_text_hash"]


def test_range_catalogue_and_context_preserve_all_available_cell_fields(rag):
    snapshot = range_fixture(rag)
    settings, db, _, _, _, search = rag
    enable(settings)
    settings.profile["retrieval"] = {"evidence_tokens_by_mode": {"factual": 100}, "max_evidence_llm_tokens": 5000}
    question = "Quelles valeurs sont enregistrées dans cette plage ?"
    result = asyncio.run(search.search(question, snapshot))
    structured = StructuredAnswerBuilder(db, snapshot)
    messages, kept, metrics, warnings = ContextBuilder(settings, CharTokenizer()).build(
        question, result["results"], structured=structured)
    assert len(kept) == 1 and metrics["evidence_budget"] > 100
    assert metrics["evidence_bundles"]["range_cell_coverage"] == 1.0
    catalogue = structured.catalogue(kept, "question")
    entries = {item["cell_facts"]["address"]: item for item in catalogue.references}
    assert len(entries) == 12
    assert entries["B5"]["fields"][0]["text"] == "0"
    assert entries["B6"]["fields"][0]["text"] == "36"
    assert all(field["complete"] for item in entries.values() for field in item["fields"])
    assert "OUTSIDE-SECRET" not in str(messages)
    assert not any(item["code"] == "evidence_bundle_excluded_by_budget" for item in warnings)


def test_range_hard_context_budget_excludes_whole_bundle_and_reports_available_evidence(rag):
    snapshot = range_fixture(rag)
    settings, _, _, _, _, search = rag
    enable(settings)
    settings.profile["retrieval"] = {"evidence_tokens_by_mode": {"ordinary": 10}, "max_evidence_llm_tokens": 100}
    result = asyncio.run(search.search("Décrire la plage", snapshot))
    _, kept, metrics, warnings = ContextBuilder(settings, CharTokenizer()).build("Décrire la plage", result["results"])
    assert not kept
    assert metrics["evidence_bundles"]["retrieved_range_cells"] == 12
    assert metrics["evidence_bundles"]["context_range_cells"] == 0
    assert any(item["code"] == "evidence_bundle_excluded_by_budget" for item in warnings)


def test_focused_range_does_not_reintroduce_other_cells(rag):
    snapshot = range_fixture(rag)
    enable(rag[0])
    snapshot.cell_ranges = [{"row_start": 5, "row_end": 5, "column_start": 2, "column_end": 2}]
    result = asyncio.run(rag[5].search("Quelle valeur ?", snapshot))
    source = result["results"][0]
    assert source["evidence_bundle"]["cell_addresses"] == ["B5"]
    assert source["text"] == "B5 (value) : 0"
    assert source["locator"]["cell_range"] == "B5"


def test_outside_change_cannot_modify_complete_range_text_or_fields(rag):
    enable(rag[0])
    first = range_fixture(rag, outside="OLD-SECRET")
    second = range_fixture(rag, outside="NEW-SECRET " * 2000)
    results = [asyncio.run(rag[5].search("Plage de valeurs", scope))["results"][0] for scope in (first, second)]
    assert results[0]["text"] == results[1]["text"]
    assert results[0]["cell_facts"] == results[1]["cell_facts"]
    assert "SECRET" not in str(results)


@pytest.mark.parametrize("limit,warning", [(2, None), (64, "cell_range_exhaustive_budget_exceeded")])
def test_non_small_or_overlong_range_retains_bounded_original_route(rag, limit, warning):
    snapshot = range_fixture(rag, long=limit == 64)
    enable(rag[0], exhaustive_range_max_cells=limit, evidence_bundle_max_chars=500)
    rag[2].submitted.clear()
    result = asyncio.run(rag[5].search("Valeurs maximum", snapshot))
    assert rag[2].submitted
    assert all(not source.get("evidence_bundle") for source in result["results"])
    if warning:
        assert any(item["code"] == warning for item in result["warnings"])


def table_fixture(storage, *, rows=None, metadata_override=None):
    rows = rows or [["Grandeur", "Min", "Max", "Unité", "Condition"],
                    ["Tension de fonctionnement", "0", "36", "V", "25 °C"],
                    ["Courant", "0", "12", "mA", "25 °C"]]
    cells = [{"start_row_offset_idx": row, "end_row_offset_idx": row + 1,
              "start_col_offset_idx": col, "end_col_offset_idx": col + 1,
              "column_header": row == 0, "row_header": col == 0,
              "text": value} for row, values in enumerate(rows) for col, value in enumerate(values)]
    text = "\n".join(" | ".join(row) for row in rows)
    block = {"id": "table", "type": "table", "text": text, "precision": "table", "bbox": [0, 0, 500, 300],
             "metadata": {"table_data": {"num_cols": len(rows[0]), "num_rows": len(rows), "table_cells": cells}}}
    if metadata_override is not None:
        metadata_override(block)
    imported, _ = import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": [block]}])
    search, snapshot, db = library_search(storage)
    chunk = db.one("SELECT * FROM chunks ORDER BY id LIMIT 1")
    source = search.resolver.source_for_chunk(chunk, snapshot)
    source_block = source["blocks"][0]
    start = text.index("36")
    source_block.update(text="36", start_offset=start, end_offset=start + 2)
    source["text"] = "36"
    return search, snapshot, source, text, imported


def test_table_value_recovers_its_complete_row_headers_unit_and_condition(storage):
    search, snapshot, source, text, _ = table_fixture(storage)
    original = copy.deepcopy(source)
    bundled, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    assert bundled["text"] == "\n".join(text.splitlines()[:2])
    assert source == original
    assert bundled["evidence_bundle"]["tables"][0]["source_rows"] == [0, 1]
    assert bundled["evidence_bundle"]["tables"][0]["headers_verified"]
    assert all(text[block["start_offset"]:block["end_offset"]] == block["text"] for block in bundled["blocks"])
    assert "0 | 36 | V | 25 °C" in bundled["text"]


def test_merged_table_label_origin_remains_with_the_selected_row(storage):
    def merge(block):
        cells = block["metadata"]["table_data"]["table_cells"]
        origin = next(cell for cell in cells if cell["start_row_offset_idx"] == 1 and cell["start_col_offset_idx"] == 0)
        origin["end_row_offset_idx"] = 3
    search, snapshot, source, text, _ = table_fixture(storage, rows=[
        ["Grandeur", "Valeur", "Unité"], ["Tension", "0", "V"], ["", "36", "V"]], metadata_override=merge)
    bundled, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and bundled["text"] == text
    assert bundled["evidence_bundle"]["tables"][0]["source_rows"] == [0, 1, 2]


def test_unmarked_headers_preserve_whole_bounded_table_without_guessing(storage):
    def no_header(block):
        for cell in block["metadata"]["table_data"]["table_cells"]:
            cell["column_header"] = False
    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=no_header)
    bundled, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and bundled["text"] == text
    structure = bundled["evidence_bundle"]["tables"][0]
    assert structure["whole_table"] and not structure["headers_verified"]


def test_overlarge_table_bundle_keeps_original_and_marks_limit(storage):
    search, snapshot, source, _, _ = table_fixture(storage)
    bundled, warnings = table_bundle(search.db, snapshot, source, maximum_chars=10)
    assert bundled == source and not bundled.get("evidence_bundle")
    assert warnings[0]["code"] == "table_evidence_bundle_too_large"


def test_table_metadata_must_reconstruct_exact_registered_text(storage):
    def corrupt(block):
        block["metadata"]["table_data"]["table_cells"][0]["text"] = "Invented header"
    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=corrupt)
    bundled, warnings = table_bundle(search.db, snapshot, source)
    assert bundled["text"] == text and warnings[0]["code"] == "table_structure_unverified"
    assert bundled["evidence_bundle"]["kind"] == "table_blocks"
    assert not bundled["evidence_bundle"]["tables"][0]["headers_verified"]
    assert "Invented header" not in bundled["text"]


def test_selection_cannot_expand_to_full_table_or_other_headers(storage):
    search, snapshot, source, _, imported = table_fixture(storage)
    block = source["blocks"][0]
    selected = search.resolver.resolve(Scope(kind="selection", versionId=imported["version_id"], spans=[{
        "blockId": block["id"], "extractionRevisionId": block["extraction_revision_id"],
        "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point",
        "startOffset": block["start_offset"], "endOffset": block["end_offset"]}]))
    source = search.resolver.selected_sources(selected)[0]
    bundled, warnings = table_bundle(search.db, selected, source)
    assert bundled["text"] == "36" and not bundled.get("evidence_bundle")
    assert warnings[0]["code"] == "table_context_limited_by_selection"


@pytest.mark.parametrize("damage", ["text", "revision", "hash", "scope"])
def test_table_bundling_refuses_source_or_authorization_drift(storage, damage):
    search, snapshot, source, _, _ = table_fixture(storage)
    if damage == "text":
        search.db.execute("UPDATE blocks SET text=text || 'changed' WHERE id='table'")
    elif damage == "revision":
        source["blocks"][0]["extraction_revision_id"] = "wrong-revision"
    elif damage == "hash":
        source["blocks"][0]["source_text_hash"] = "0" * 64
    else:
        snapshot.page_indices = [1]
    with pytest.raises(ApiError) as error:
        table_bundle(search.db, snapshot, source)
    assert error.value.code == ("scope_leakage" if damage == "scope" else "source_text_integrity_failure")


def test_docx_table_with_internal_newline_uses_exact_row_offsets(rag):
    from docx import Document
    from docx.oxml import OxmlElement

    settings, db, _, indexer, resolver, search = rag
    path = settings.data_dir / "originals" / "table.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Document()
    table = book.add_table(rows=3, cols=3)
    for row, values in zip(table.rows, [["Grandeur", "Bornes", "Unité"], ["Tension", "0\n36", "V"], ["Courant", "12", "mA"]], strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    book.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extractions" / imported["version_id"], {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))
    chunk = db.one("SELECT * FROM chunks")
    source = resolver.source_for_chunk(chunk, snapshot)
    parent_text = source["text"]
    start = parent_text.index("36")
    source["blocks"][0].update(text="36", start_offset=start, end_offset=start + 2)
    source["text"] = "36"
    bundled, warnings = table_bundle(db, snapshot, source)
    assert not warnings
    assert bundled["text"] == "Grandeur\tBornes\tUnité\nTension\t0\n36\tV"
    assert all(parent_text[block["start_offset"]:block["end_offset"]] == block["text"] for block in bundled["blocks"])
    assert all(block["page_index"] is None for block in bundled["blocks"])


def test_structural_rerank_prefers_operating_limit_to_typical_test_condition():
    sources = [{"chunk_id": "typical", "text": "Typical characteristics. Supply voltage test condition: 5 V.", "exact_identifier": True},
               {"chunk_id": "limits", "text": "Recommended operating supply voltage: minimum 0 V, maximum 36 V.", "exact_identifier": True}]
    before = copy.deepcopy(sources)
    ranked = structural_rerank("Quelle plage de tension d'alimentation admissible ?", sources)
    assert ranked[0]["chunk_id"] == "limits"
    assert ranked[1]["rerank_features"]["role_mismatch"]
    assert sources == before


def test_rerank_is_stable_bounded_and_does_not_use_rank_as_a_probability():
    sources = [{"chunk_id": str(index), "text": "tension nominale", "score": 1 / (index + 60)} for index in range(6)]
    first = structural_rerank("Quelle tension ?", sources, maximum_candidates=3)
    second = structural_rerank("Quelle tension ?", sources, maximum_candidates=3)
    assert first == second
    assert [item["chunk_id"] for item in first] == [str(index) for index in range(6)]
    assert first[3:] == sources[3:]
    assert all("confidence" not in item and "probability" not in item for item in first)


def test_bundle_is_not_reduced_to_one_bound_by_context_truncation(storage):
    search, snapshot, source, _, _ = table_fixture(storage)
    source, _ = table_bundle(search.db, snapshot, source)
    enable(storage[0])
    settings = storage[0]
    settings.profile["retrieval"] = {"evidence_tokens_by_mode": {"ordinary": 1}, "max_evidence_llm_tokens": 2000}
    messages, kept, metrics, _ = ContextBuilder(settings, CharTokenizer()).build("Décrire la tension", [source])
    assert kept and "0 | 36 | V | 25 °C" in messages[-1]["content"]
    assert metrics["evidence_bundles"]["retained_bundles"] == 1
    settings.profile["retrieval"]["max_evidence_llm_tokens"] = 10
    _, kept, metrics, _ = ContextBuilder(settings, CharTokenizer()).build("Décrire la tension", [source])
    assert not kept and metrics["evidence_bundles"]["excluded_bundle_ids"]


def test_baseline_profile_does_not_reconstruct_table_evidence(storage):
    search, snapshot, _, _, _ = table_fixture(storage)
    result = asyncio.run(search.search("Tension de fonctionnement", snapshot))
    assert result["results"] and all(not source.get("evidence_bundle") for source in result["results"])
    enable(storage[0])
    enhanced = asyncio.run(search.search("Tension de fonctionnement", snapshot))
    assert enhanced["results"][0].get("evidence_bundle")


def mention_saturation_fixture(storage):
    texts = ["AQ-73 voltage monitor", "AQ-73 package dimensions", "AQ-73 thermal metric",
             "AQ-73 ordering information", "AQ-73 document revisions", "AQ-73 device logo", "AQ-73 mechanical drawing"]
    pages = [{"page_index": index, "width": 595, "height": 842, "blocks": [{
        "id": f"mention-{index}", "type": "text", "text": text, "bbox": [0, 0, 300, 50]}]}
        for index, text in enumerate(texts)]
    for index, text in enumerate(["PARAMETER | MIN | MAX | UNIT\nBus voltage input range | -2.5 | 41 | V",
                                 "PARAMETER | MIN | MAX | UNIT\nOperating supply range | 1.8 | 4.8 | V"], len(pages)):
        pages.append({"page_index": index, "width": 595, "height": 842, "blocks": [{
            "id": f"fact-{index}", "type": "table", "text": text, "bbox": [0, 0, 300, 100],
            "metadata": {"table_cell_regions": [], "text_export": "source_fields_omitted"}}]})
    imported, _ = import_fixture(storage, path="scoped/AQ-73.pdf", text="mention-saturation", pages=pages)
    import_fixture(storage, path="outside/other.pdf", text="OUTSIDE-SECRET AQ-73 voltage input range supply 999 V")
    search, _, _ = library_search(storage)
    snapshot = search.resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))
    return search, snapshot


@pytest.mark.parametrize("complement_only", [False, True])
def test_repeated_identifier_mentions_cannot_crowd_out_requested_table_relations(storage, complement_only):
    search, snapshot = mention_saturation_fixture(storage)
    question = "Pour AQ-73, quelles sont la plage de tension de bus et la plage d'alimentation ?"
    baseline = asyncio.run(search.search(question, snapshot))
    assert all(source["exact_identifier"] for source in baseline["results"])
    assert not any("1.8 | 4.8" in source["text"] for source in baseline["results"])
    enable(storage[0], complementary_retrieval=True)
    if complement_only:
        result = asyncio.run(search.refine_once(question, snapshot, baseline, ["voltage", "supply"]))
        assert result["refinement"]["retained_new_evidence_count"] >= 2
    else:
        result = asyncio.run(search.search(question, snapshot))
    assert len(result["results"]) <= 6
    assert any(source["exact_identifier"] for source in result["results"])
    joined = "\n".join(source["text"] for source in result["results"])
    assert "Bus voltage input range | -2.5 | 41 | V" in joined
    assert "Operating supply range | 1.8 | 4.8 | V" in joined
    assert "OUTSIDE-SECRET" not in str(result)
    bundles = [source for source in result["results"] if source.get("evidence_bundle")]
    assert len(bundles) == 2
    assert all(source["evidence_bundle"]["kind"] == "table_blocks" for source in bundles)
    assert all(not source["evidence_bundle"]["tables"][0]["headers_verified"] for source in bundles)
    structured = StructuredAnswerBuilder(search.db, snapshot, question=question, enforce_contract=True)
    _, kept, metrics, _ = ContextBuilder(storage[0], CharTokenizer()).build(question, result["results"], structured=structured)
    assert metrics["identifier_coverage_at_context"] == 1
    assert any("-2.5 | 41" in source["text"] for source in kept)
    assert any("1.8 | 4.8" in source["text"] for source in kept)


@pytest.mark.parametrize("damaged", [None, [], {"structure": None}, {"structure": {"serialization": "tab_newline_v1", "rows": [{"row": 0, "cells": None}]}}])
def test_missing_or_malformed_table_metadata_preserves_only_exact_whole_text(storage, damaged):
    search, snapshot, source, text, _ = table_fixture(storage)
    search.db.execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id=?",
                      (json.dumps(damaged), source["generation_id"], source["blocks"][0]["id"]))
    result, warnings = table_bundle(search.db, snapshot, source)
    assert result["text"] == text and warnings[0]["code"] == "table_structure_unverified"
    assert result["blocks"][0]["start_offset"] == 0 and result["blocks"][0]["end_offset"] == len(text)
    assert not result["evidence_bundle"]["tables"][0]["serialization_verified"]


def archived_cell_texts(block):
    for cell in block["metadata"]["table_data"]["table_cells"]:
        text = cell.pop("text")
        cell["text_provenance"] = {"text_export": "publisher_text_omitted", "text_characters": len(text),
                                   "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def test_omitted_cell_text_is_recovered_only_by_source_length_hash_and_complete_serialization(storage):
    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=archived_cell_texts)
    result, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    assert result["text"] == "\n".join(text.splitlines()[:2])
    proof = result["evidence_bundle"]["tables"][0]
    assert proof["cell_text_verification"] == "hash_verified" and proof["serialization_verified"]
    assert proof["source_rows"] == [0, 1] and proof["header_rows"] == [0]
    assert all(text[block["start_offset"]:block["end_offset"]] == block["text"] for block in result["blocks"])


@pytest.mark.parametrize("damage", ["hash", "length", "coordinate"])
def test_archived_cell_recovery_cannot_invent_text_or_accept_unverified_row_layout(storage, damage):
    def altered(block):
        archived_cell_texts(block)
        cell = block["metadata"]["table_data"]["table_cells"][1]
        if damage == "hash":
            cell["text_provenance"]["text_sha256"] = "f" * 64
        elif damage == "length":
            cell["text_provenance"]["text_characters"] += 1
        else:
            cell["start_row_offset_idx"] = 10
    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=altered)
    result, warnings = table_bundle(search.db, snapshot, source)
    assert result["text"] == text and result["evidence_bundle"]["kind"] == "table_blocks"
    assert not result["evidence_bundle"]["tables"][0]["headers_verified"]
    assert warnings[0]["code"] == "table_structure_unverified"


def test_archived_cell_recovery_budget_and_literal_scope_have_explicit_fallback(storage, monkeypatch):
    from services.api import evidence_selection

    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=archived_cell_texts)
    monkeypatch.setattr(evidence_selection, "MAX_TABLE_RECOVERY_HASHES", 0)
    result, warnings = table_bundle(search.db, snapshot, source)
    assert result["text"] == text
    assert any(warning["code"] == "table_cell_recovery_budget_exceeded" for warning in warnings)
    snapshot.spans = [{"block_id": source["blocks"][0]["id"], "start_offset": source["blocks"][0]["start_offset"],
                       "end_offset": source["blocks"][0]["end_offset"]}]
    monkeypatch.setattr(evidence_selection, "_recover_cell_texts", lambda *args: pytest.fail("No recovery outside literal selection"))
    strict, warnings = table_bundle(search.db, snapshot, source)
    assert strict == source and strict["text"] == "36"
    assert warnings[0]["code"] == "table_context_limited_by_selection"


def test_archived_cell_hashes_are_checked_once_per_table_candidate_batch(storage, monkeypatch):
    from services.api import evidence_selection

    search, snapshot, source, _, _ = table_fixture(storage, metadata_override=archived_cell_texts)
    calls = []
    original = evidence_selection._recover_cell_texts

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(evidence_selection, "_recover_cell_texts", counted)
    result, warnings = prepare_tables(search.db, snapshot, [source, copy.deepcopy(source)])
    assert len(calls) == 1 and len(result) == 1 and not warnings


def test_proven_row_focus_deduplicates_same_table_chunks_and_keeps_header_and_complete_pair(storage):
    search, snapshot, source, text, _ = table_fixture(storage, metadata_override=archived_cell_texts)
    other = copy.deepcopy(source)
    start = text.index("Courant")
    other["text"] = text[start:]
    other["blocks"][0].update(text=text[start:], start_offset=start, end_offset=len(text))
    result, warnings = prepare_tables(search.db, snapshot, [other, source], question="Quelle plage de tension ?")
    assert not warnings and len(result) == 1
    assert result[0]["text"] == "\n".join(text.splitlines()[:2])
    assert result[0]["evidence_bundle"]["tables"][0]["row_selection"] == "question_terms"
    assert "0 | 36 | V | 25 °C" in result[0]["text"]


def test_proven_row_focus_keeps_explicit_identifier_obligation(storage):
    search, snapshot, source, text, _ = table_fixture(storage, rows=[
        ["Parameter", "Minimum", "Maximum", "Unit"], ["Supply voltage", "0", "36", "V"],
        ["CH-8 current", "2", "8", "mA"]], metadata_override=archived_cell_texts)
    result, warnings = table_bundle(search.db, snapshot, source, question="Quelle tension ?", required_identifiers={"CH-8"})
    assert not warnings and result["text"] == text


def test_proven_row_focus_keeps_verified_section_label(storage):
    def metadata(block):
        archived_cell_texts(block)
        for cell in block["metadata"]["table_data"]["table_cells"]:
            cell["row_section"] = cell["start_row_offset_idx"] == 1

    search, snapshot, source, _, _ = table_fixture(storage, rows=[
        ["Parameter", "Min", "Max", "Unit"], ["INPUT"], ["Bus voltage input range", "0", "36", "V"],
        ["Current", "2", "8", "mA"]], metadata_override=metadata)
    result, warnings = table_bundle(search.db, snapshot, source, question="Quelle plage de tension de bus ?")
    assert not warnings
    assert result["evidence_bundle"]["tables"][0]["source_rows"] == [0, 1, 2]


def complementary_fixture(storage):
    from services.api.retrieval import SearchService

    settings, db, vectors, indexer = storage
    allowed, _ = import_fixture(storage, path="allowed/manual.pdf", text="allowed-original", pages=[{
        "page_index": 0, "width": 595, "height": 842, "blocks": [
            {"id": "assembly", "text": "CCU-21 : assemblage du module."},
            {"id": "supply", "text": "CCU-21 operating supply voltage : 0 V to 36 V."},
            {"id": "input", "text": "CCU-21 input voltage : 0 V to 5 V."}]}])
    import_fixture(storage, path="outside/manual.pdf", text="outside-original", pages=[{
        "page_index": 0, "width": 595, "height": 842, "blocks": [
            {"id": "outside", "text": "OUTSIDE-SECRET voltage voltage voltage 999 V."}]}])
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[allowed["document_id"]]))
    search = SearchService(db, resolver, indexer.embedding, vectors, settings)
    enable(settings, complementary_retrieval=True, complementary_timeout_seconds=5)
    previous = asyncio.run(search.search("Décrire CCU-21", snapshot))
    initial = next(source for source in previous["results"] if source["parent_id"] == "assembly")
    previous = {**previous, "results": [initial]}
    return search, snapshot, previous


def test_one_scoped_lexical_complement_keeps_old_sources_and_adds_missing_evidence(storage, monkeypatch):
    search, snapshot, previous = complementary_fixture(storage)
    prior = copy.deepcopy(previous)
    calls = []
    original = search._complementary_candidates

    def recorded(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(search, "_complementary_candidates", recorded)

    async def scenario():
        result = await search.refine_once("Décrire CCU-21", snapshot, previous, ["voltage"])
        repeated = await search.refine_once("Décrire CCU-21", snapshot, result, ["voltage"])
        return result, repeated

    result, repeated = asyncio.run(scenario())
    assert result["refinement"]["reason"] == "new_evidence"
    assert result["refinement"]["performed"] and result["refinement"]["new_evidence_count"] == 2
    assert {source["parent_id"] for source in result["results"]} == {"assembly", "supply", "input"}
    assert all(source["generation_id"] in snapshot.generations for source in result["results"])
    assert "OUTSIDE-SECRET" not in json.dumps(result)
    assert repeated["refinement"]["reason"] == "already_attempted" and len(calls) == 1
    assert previous == prior


@pytest.mark.parametrize("terms", [[], ["0", "36", "S001", "de", "document"], [None, {}, 36]])
def test_no_lexical_complement_without_substantive_terms(storage, monkeypatch, terms):
    search, snapshot, previous = complementary_fixture(storage)
    monkeypatch.setattr(search, "_complementary_candidates", lambda *args: pytest.fail("Unexpected search"))
    result = asyncio.run(search.refine_once("Décrire CCU-21", snapshot, previous, terms))
    assert result["results"] == previous["results"]
    assert result["refinement"]["reason"] == "no_substantive_missing_terms"
    assert not result["refinement"]["attempted"]


def test_complementary_timeout_leaves_first_evidence_and_does_not_loop(storage, monkeypatch):
    import time

    search, snapshot, previous = complementary_fixture(storage)
    search.settings.profile["enhanced"]["complementary_timeout_seconds"] = 0.005
    calls = []

    def slow(*args):
        calls.append(1)
        time.sleep(0.025)
        return []

    monkeypatch.setattr(search, "_complementary_candidates", slow)
    result = asyncio.run(search.refine_once("Décrire CCU-21", snapshot, previous, ["voltage"]))
    assert result["refinement"]["reason"] == "timeout"
    assert result["refinement"]["attempted"] and not result["refinement"]["performed"]
    assert result["results"] == previous["results"] and calls == [1]


def test_refinement_rejects_literal_scope_and_stops_without_new_evidence(rag, storage, monkeypatch):
    snapshot = range_fixture(rag)
    enable(rag[0], complementary_retrieval=True)
    previous = asyncio.run(rag[5].search("Décrire la plage", snapshot))
    monkeypatch.setattr(rag[5], "_complementary_candidates", lambda *args: pytest.fail("Literal scope widened"))
    result = asyncio.run(rag[5].refine_once("Décrire la plage", snapshot, previous, ["voltage"]))
    assert result["refinement"]["reason"] == "literal_scope"
    search, snapshot, _ = complementary_fixture(storage)
    complete = asyncio.run(search.search("Décrire CCU-21", snapshot))
    result = asyncio.run(search.refine_once("Décrire CCU-21", snapshot, complete, ["voltage"]))
    assert result["refinement"]["reason"] == "no_new_evidence"
    assert result["results"] == complete["results"]


def test_complementary_union_keeps_configured_fragment_cap(storage):
    search, snapshot, previous = complementary_fixture(storage)
    search.settings.profile["retrieval"] = {"final_max_fragments": 2}
    result = asyncio.run(search.refine_once("Décrire CCU-21", snapshot, previous, ["voltage"]))
    assert len(result["results"]) == 2
    assert result["refinement"]["new_evidence_count"] == 2
    assert result["refinement"]["retained_new_evidence_count"] == 2


def test_complementary_cancel_is_not_reported_as_a_success(storage, monkeypatch):
    import time

    search, snapshot, previous = complementary_fixture(storage)
    monkeypatch.setattr(search, "_complementary_candidates", lambda *args: (time.sleep(0.01), [])[1])

    async def scenario():
        task = asyncio.create_task(search.refine_once("Décrire CCU-21", snapshot, previous, ["voltage"]))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
