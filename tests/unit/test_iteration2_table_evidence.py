"""Sparse table relations and multi-obligation selection on real SQLite text.

The source table geometry is a named synthetic extraction; no OCR/model result
is implied by these tests. Embeddings/vector search use the existing doubles.
"""

import asyncio
import copy
import hashlib

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_office_rag import rag as rag
from test_retrieval import library_search

from services.api.evidence_selection import _focused_rows, _row_records, table_bundle, verified_table_rows
from services.api.schemas import Scope
from services.ingestion.office.pipeline import extract_office

HEADERS = [(1, "PARAMETER"), (2, "TEST CONDITIONS"), (3, "MIN"), (4, "NOM"), (5, "MAX"), (6, "UNIT")]


def sparse_table(storage, rows, *, target=1, mutate=None, section_title=None):
    cells = [{"text": text, "start_row_offset_idx": row, "end_row_offset_idx": row + 1,
              "start_col_offset_idx": column, "end_col_offset_idx": column + 1,
              "column_header": row == 0, "row_header": column == 1, "row_section": False}
             for row, fields in enumerate(rows) for column, text in fields]
    text = "\n".join(" | ".join(value for _, value in fields) for fields in rows)
    block = {"id": "sparse-table", "type": "table", "text": text, "precision": "table", "bbox": [0, 0, 500, 300],
             "metadata": {"table_data": {"table_cells": cells, "num_cols": 7, "num_rows": len(rows)}}}
    if mutate:
        mutate(block)
    blocks, sections = [block], None
    if section_title:
        block["section_id"] = "explicit-heading"
        heading = {"id": "explicit-heading", "type": "heading", "text": section_title,
                   "section_id": "explicit-heading", "bbox": [0, 0, 500, 20], "precision": "block"}
        blocks = [heading, block]
        sections = [{"id": heading["id"], "title": section_title, "page_start": 0, "page_end": 0,
                     "block_ids": [heading["id"], block["id"]]}]
    import_fixture(storage, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}], sections=sections)
    search, snapshot, db = library_search(storage)
    chunk = db.one("SELECT c.* FROM chunks c JOIN chunk_sources s ON s.chunk_uuid=c.chunk_uuid "
                   "WHERE s.block_id='sparse-table' ORDER BY c.id LIMIT 1")
    source = search.resolver.source_for_chunk(chunk, snapshot)
    line = " | ".join(value for _, value in rows[target])
    start = sum(len(" | ".join(value for _, value in fields)) + 1 for fields in rows[:target])
    source["blocks"] = [block for block in source["blocks"] if block["type"] == "table"]
    source["blocks"][0].update(text=line, start_offset=start, end_offset=start + len(line))
    source["text"] = line
    return search, snapshot, source, text


def body(bundle, row=1):
    return next(block["table_context"] for block in bundle["blocks"]
                if block.get("table_context", {}).get("row_index") == row)


def test_sparse_columns_keep_maximum_separate_from_missing_nominal(storage):
    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Bus voltage input range"), (3, "-2.5"), (5, "41"), (6, "V")]])
    before = copy.deepcopy(source)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and source == before
    relation = body(bundle)
    value = next(cell for cell in relation["cells"] if cell["text"] == "41")
    assert value["column_start"] == 5
    assert [(header["text"], header["role"]) for header in value["headers"]] == [("MAX", "maximum")]
    assert not any(cell["column_start"] == 4 for cell in relation["cells"])
    assert relation["source_text_hash"] == hashlib.sha256(text.encode()).hexdigest()
    assert relation["dependencies"][0]["kind"] == "header"
    for cell in relation["cells"]:
        for span in [cell, *cell["headers"]]:
            assert text[span["start_offset"]:span["end_offset"]] == span["text"]


def test_nominal_and_condition_have_distinct_explicit_header_bindings(storage):
    search, snapshot, source, _ = sparse_table(storage, [HEADERS,
        [(1, "Supply range"), (2, "TA = 27 °C"), (3, "1.8"), (4, "3.1"), (5, "4.8"), (6, "V")]])
    bundle, _ = table_bundle(search.db, snapshot, source)
    roles = {cell["text"]: [header["role"] for header in cell["headers"]] for cell in body(bundle)["cells"]}
    assert roles["3.1"] == ["nominal"]
    assert roles["TA = 27 °C"] == ["condition"]
    assert roles["4.8"] == ["maximum"]


@pytest.mark.parametrize("symbol", ["DRR", "drr"])
def test_multiple_requested_properties_survive_a_lexically_stronger_condition_row(storage, symbol):
    search, snapshot, source, _ = sparse_table(storage, [HEADERS,
        [(1, "Bus voltage input range"), (3, "-2.5"), (5, "41"), (6, "V")],
        [(0, "DRR"), (1, "Shunt voltage error vs power supply"), (2, "2 V ≤ VS ≤ 4.8 V"), (4, "±0.3"), (6, "μV/V")],
        [(0, "DRR"), (1, "Bus voltage error vs power supply"), (4, "±0.4"), (6, "mV/V")]], target=3)
    question = f"La condition d'essai {symbol} est-elle une plage de tension de bus ? Donner la plage de bus et d'alimentation."
    bundle, warnings = table_bundle(search.db, snapshot, source, question=question)
    assert not warnings
    assert {0, 1, 2} <= set(bundle["evidence_bundle"]["tables"][0]["source_rows"])
    assert "-2.5 | 41 | V" in bundle["text"]
    assert "2 V ≤ VS ≤ 4.8 V" in bundle["text"]
    assert next(cell for cell in body(bundle, 2)["cells"] if cell["column_start"] == 2)["headers"][0]["role"] == "condition"


def test_condition_binding_does_not_attach_the_question_symbol_to_an_unrelated_row(storage):
    search, snapshot, source, _ = sparse_table(storage, [HEADERS,
        [(1, "Operating supply range"), (3, "1.8"), (5, "4.8"), (6, "V")],
        [(1, "Low-level output voltage"), (2, "IOL = 2 mA"), (3, "0"), (5, "0.6"), (6, "V")]])
    bundle, _ = table_bundle(search.db, snapshot, source,
        question="Condition d'essai DRR, plage de tension de bus et plage d'alimentation ?")
    assert bundle["evidence_bundle"]["tables"][0]["source_rows"] == [0, 1, 2]
    # Voltage is independently requested, so the output row can remain lexical
    # evidence, but its condition must not acquire the named DRR relationship.
    assert "DRR" not in str(body(bundle, 2))


def test_rowspan_unit_keeps_its_origin_and_exact_offsets(storage):
    def span(block):
        next(cell for cell in block["metadata"]["table_data"]["table_cells"]
             if cell["text"] == "µs")["end_row_offset_idx"] = 3

    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Conversion 000"), (4, "150"), (6, "µs")],
        [(1, "Conversion 001"), (4, "210")]], target=2, mutate=span)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and bundle["text"] == text
    relation = body(bundle, 2)
    inherited = next(cell for cell in relation["cells"] if cell["text"] == "µs")
    assert (inherited["row_start"], inherited["row_end"]) == (1, 3)
    assert any(dependency["kind"] == "row_span" and dependency["row_index"] == 1 for dependency in relation["dependencies"])


def multilevel_headers(block):
    for cell in block["metadata"]["table_data"]["table_cells"]:
        row = cell["start_row_offset_idx"]
        cell["column_header"] = row in {0, 1, 3, 4}
        if row in {0, 3}:
            cell["end_col_offset_idx"] = 4


def test_multilevel_header_keeps_ancestor_condition_as_an_exact_dependency(storage):
    labels = [(0, "PARAMETER"), (1, "MIN"), (2, "MAX"), (3, "UNIT")]
    search, snapshot, source, text = sparse_table(storage, [[(0, "TA = 25 °C")], labels,
        [(0, "Supply voltage"), (1, "1.8"), (2, "4.8"), (3, "V")]], target=2, mutate=multilevel_headers)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    relation = body(bundle, 2)
    value = next(cell for cell in relation["cells"] if cell["text"] == "4.8")
    assert [(header["text"], header["role"]) for header in value["headers"]] == [("TA = 25 °C", None), ("MAX", "maximum")]
    assert {dependency["row_index"] for dependency in relation["dependencies"]} == {0, 1}
    assert all(text[dependency["start_offset"]:dependency["end_offset"]] == dependency["text"]
               for dependency in relation["dependencies"])


def test_repeated_header_group_does_not_inherit_previous_groups_conditions(storage):
    labels = [(0, "PARAMETER"), (1, "MIN"), (2, "MAX"), (3, "UNIT")]
    values = [(0, "Supply voltage"), (1, "1.8"), (2, "4.8"), (3, "V")]
    search, snapshot, source, _ = sparse_table(storage,
        [[(0, "TA = 25 °C")], labels, values, [(0, "TA = 85 °C")], labels, values], target=5, mutate=multilevel_headers)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings
    relation = body(bundle, 5)
    assert {dependency["row_index"] for dependency in relation["dependencies"]} == {3, 4}
    assert "TA = 85 °C" in str(relation) and "TA = 25 °C" not in str(relation)


def test_conflicting_multilevel_column_roles_preserve_text_without_assigning_values(storage):
    labels = [(0, "PARAMETER"), (1, "MIN"), (2, "MAX"), (3, "UNIT")]
    search, snapshot, source, text = sparse_table(storage, [[(0, "MIN")], labels,
        [(0, "Supply voltage"), (1, "1.8"), (2, "4.8"), (3, "V")]], target=2, mutate=multilevel_headers)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert bundle["text"] == text
    assert all("table_context" not in block for block in bundle["blocks"])
    assert warnings[0]["code"] == "table_column_bindings_unverified"


def test_excessive_header_ancestry_is_rejected_before_building_quadratic_links(monkeypatch):
    from services.api import evidence_selection

    count = evidence_selection.MAX_TABLE_CELLS
    cells = [{"text": "Context" if row < count - 1 else "Value", "start_row_offset_idx": row,
              "end_row_offset_idx": row + 1, "start_col_offset_idx": 0, "end_col_offset_idx": 1,
              "column_header": row < count - 1} for row in range(count)]
    monkeypatch.setattr(evidence_selection, "_header_role", lambda text: pytest.fail("No ancestor links should be allocated"))
    records = _row_records({"metadata": {"table_data": {"table_cells": cells}}})
    assert len(records) == count
    assert not any(record["column_bindings_verified"] for record in records)
    assert all(not cell["headers"] for record in records for cell in record["cells"])


@pytest.mark.parametrize("bad", [None, True, 3, 100000])
def test_invalid_or_overlapping_column_geometry_never_assigns_a_role(storage, bad):
    def corrupt(block):
        cells = block["metadata"]["table_data"]["table_cells"]
        next(cell for cell in cells if cell["text"] == "41")["end_col_offset_idx"] = bad

    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Bus voltage range"), (3, "-2.5"), (5, "41"), (6, "V")]], mutate=corrupt)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert bundle["text"] == text
    assert all("table_context" not in block for block in bundle["blocks"])
    assert any(warning["code"] == "table_column_bindings_unverified" for warning in warnings)


def test_literal_scope_does_not_publish_headers_outside_the_selection(storage):
    search, snapshot, source, _ = sparse_table(storage, [HEADERS,
        [(1, "Bus voltage range"), (3, "-2.5"), (5, "41"), (6, "V")]])
    block = source["blocks"][0]
    snapshot.spans = [{"block_id": block["id"], "start": block["start_offset"], "end": block["end_offset"]}]
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert bundle is source and "table_context" not in block
    assert warnings[0]["code"] == "table_context_limited_by_selection"


def test_header_like_body_text_does_not_create_a_numeric_role(storage):
    search, snapshot, source, _ = sparse_table(storage, [[(1, "FIELD"), (3, "VALUE")],
        [(1, "MIN"), (3, "41")]])
    bundle, _ = table_bundle(search.db, snapshot, source)
    value = next(cell for cell in body(bundle)["cells"] if cell["text"] == "41")
    assert value["headers"][0]["text"] == "VALUE" and value["headers"][0]["role"] is None


def test_broad_ties_keep_original_span_instead_of_arbitrary_first_twelve():
    cells = [{"start_row_offset_idx": row, "end_row_offset_idx": row + 1,
              "start_col_offset_idx": 0, "end_col_offset_idx": 1,
              "column_header": row == 0, "text": "Parameter" if row == 0 else f"Voltage channel {row}"}
             for row in range(14)]
    rows = _row_records({"metadata": {"table_data": {"table_cells": cells}}})
    assert _focused_rows(rows, "Quelle tension ?", ()) is None


def test_public_revalidation_requires_complete_exact_serialization():
    cell = {"text": "MIN", "start_row_offset_idx": 0, "end_row_offset_idx": 1,
            "start_col_offset_idx": 1, "end_col_offset_idx": 2, "column_header": True}
    metadata = {"metadata": {"table_data": {"table_cells": [cell]}}}
    assert verified_table_rows("MIN", metadata)[0]["cells"][0]["column_start"] == 1
    assert verified_table_rows("MAX", metadata) is None
    assert verified_table_rows("MIN", {"metadata": {"table_data": {"table_cells": None}}}) is None


def test_explicit_external_section_heading_is_an_authorized_citable_block(storage):
    title = "6.3 Recommended Operating Conditions"
    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Supply voltage"), (3, "1.8"), (4, "3.1"), (5, "4.8"), (6, "V")]], section_title=title)
    bundle, warnings = table_bundle(search.db, snapshot, source)
    assert not warnings and bundle["text"] == title + "\n" + text
    relation = body(bundle)["section_heading"]
    heading = next(block for block in bundle["blocks"] if block["id"] == relation["block_id"])
    assert heading["text"] == title
    assert relation["section_id"] == heading["id"] == "explicit-heading"
    assert relation["source_text_hash"] == hashlib.sha256(title.encode()).hexdigest()
    assert relation["start_offset"] == 0 and relation["end_offset"] == len(title)


@pytest.mark.parametrize("failure", ["outside_block_scope", "membership_missing", "hash_mismatch", "title_mismatch"])
def test_external_section_heading_requires_scope_membership_and_literal_integrity(storage, failure):
    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Supply voltage"), (3, "-0.4"), (5, "6.1"), (6, "V")]], section_title="Absolute Maximum Ratings")
    if failure == "outside_block_scope":
        snapshot.block_ids = {"sparse-table"}
    elif failure == "membership_missing":
        search.db.execute("UPDATE sections SET block_ids_json='[\"explicit-heading\"]'")
    elif failure == "hash_mismatch":
        search.db.execute("UPDATE blocks SET source_text_hash=? WHERE id='explicit-heading'", ("0" * 64,))
    else:
        search.db.execute("UPDATE sections SET title='Recommended Operating Conditions'")
    bundle, _ = table_bundle(search.db, snapshot, source)
    assert bundle["text"] == text
    assert all(block["id"] != "explicit-heading" for block in bundle["blocks"])
    assert "section_heading" not in body(bundle)


def test_external_heading_is_counted_in_the_atomic_bundle_budget(storage):
    search, snapshot, source, text = sparse_table(storage, [HEADERS,
        [(1, "Supply voltage"), (3, "1.8"), (5, "4.8"), (6, "V")]], section_title="Recommended Operating Conditions")
    bundle, warnings = table_bundle(search.db, snapshot, source, maximum_chars=len(text))
    assert bundle is source
    assert warnings[0]["code"] == "table_evidence_bundle_too_large"


def test_unmarked_docx_header_uses_explicit_labels_and_real_ooxml_coordinates(rag):
    from docx import Document

    settings, db, _, indexer, resolver, _ = rag
    path = settings.data_dir / "originals" / "explicit-labels.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Document()
    title = "Recommended Operating Conditions"
    book.add_heading(title, level=1)
    table = book.add_table(rows=2, cols=6)
    for row, values in zip(table.rows, [["Grandeur", "Condition", "MIN", "NOM", "MAX", "Unité"],
                                      ["Supply voltage", "TA = 27 °C", "1.8", "3.1", "4.8", "V"]], strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    book.save(path)
    imported = db.import_original(path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path)
    extraction = extract_office(path, settings.data_dir / "extractions" / imported["version_id"], {}, imported["version_id"], "docx")
    asyncio.run(indexer.index(imported["job_id"], extraction))
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))
    chunk = db.one("SELECT c.* FROM chunks c JOIN chunk_sources s ON c.chunk_uuid=s.chunk_uuid "
                   "JOIN blocks b ON b.generation_id=c.generation_id AND b.id=s.block_id WHERE b.kind='table' LIMIT 1")
    source = resolver.source_for_chunk(chunk, snapshot)
    parent_text = source["text"]
    # Deliberately no w:tblHeader was added; source text and its metadata remain
    # unchanged while the complete labels establish a separate derived proof.
    bundle, warnings = table_bundle(db, snapshot, source, question="Quelle plage d'alimentation ?")
    assert not warnings and bundle["text"] == title + "\n" + parent_text
    relation = body(bundle)
    assert relation["header_detection"] == "explicit_labels"
    assert bundle["evidence_bundle"]["tables"][0]["header_detection"] == "explicit_labels"
    values = {cell["text"]: cell for cell in relation["cells"]}
    assert values["3.1"]["headers"][0]["role"] == "nominal"
    assert values["4.8"]["column_start"] == 4 and values["4.8"]["headers"][0]["role"] == "maximum"
    assert values["TA = 27 °C"]["headers"][0]["role"] == "condition"
    heading = relation["section_heading"]
    assert heading["section_id"] != heading["block_id"]
    assert heading["text"] == title
    heading_block = next(block for block in bundle["blocks"] if block["id"] == heading["block_id"])
    assert heading_block["locator"]["kind"] == "docx_element" and heading_block["page_index"] is None
    snapshot.block_ids = [block["id"] for block in source["blocks"]]
    restricted, _ = table_bundle(db, snapshot, source)
    assert "section_heading" not in body(restricted)


@pytest.mark.parametrize("failure", ["incomplete", "ambiguous", "data", "missing_coordinates", "wrong_row", "gap", "merged"])
def test_unmarked_docx_rows_are_not_headers_without_complete_unique_explicit_labels(failure):
    labels = ["Grandeur", "MIN", "MAX", "Unité"]
    if failure == "incomplete":
        labels[2] = ""
    elif failure == "ambiguous":
        labels[2] = "MIN"
    elif failure == "data":
        labels = ["Supply voltage", "1.8", "4.8", "V"]
    rows = [{"row": row, "is_header": False, "cells": [
        {"row": row, "column": column, "row_span": 1, "column_span": 1, "text": text}
        for column, text in enumerate(values)]}
        for row, values in enumerate([labels, ["Supply voltage", "1.8", "4.8", "V"]])]
    if failure == "missing_coordinates":
        rows[0]["cells"][1].pop("column")
    elif failure == "wrong_row":
        rows[0]["cells"][1]["row"] = 2
    elif failure == "gap":
        for row in rows:
            for cell in row["cells"]:
                cell["column"] += 1
    elif failure == "merged":
        rows[0]["cells"][0]["column_span"] = 2
    metadata = {"structure": {"serialization": "tab_newline_v1", "rows": rows}}
    text = "\n".join("\t".join(cell["text"] for cell in row["cells"]) for row in rows)
    records = verified_table_rows(text, metadata)
    assert records and not any(record["header"] for record in records)
    assert all(not cell["headers"] for record in records for cell in record["cells"])
