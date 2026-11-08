"""I4 S01–S08: explicit PDF lists, with synthetic parser/embedding boundaries.

The exact dev inputs and geometric oracles preceded product edits. These tests
exercise the production adapter, SQLite, chunk sources and scope projection;
they do not run or qualify a native PDF parser, OCR engine or language model.
"""

import asyncio
import copy
import hashlib
import inspect
import json
from uuid import NAMESPACE_URL, uuid5

import pytest
from test_api_storage import storage as storage

from services.api.schemas import Scope
from services.api.scope import ScopeResolver
from services.ingestion.docling_adapter import document_to_pages


def dev_rows(case="S01"):
    rows = [
        ("B0", "• ", [44, 703, 48, 707]),
        ("P", "Supply range:", [58, 700, 170, 712]),
        ("M1", "– ", [58, 680, 64, 684]),
        ("V1", "2.4 V to 3.6 V at 25 °C", [75, 676, 285, 688]),
        ("M2", "– ", [58, 660, 64, 664]),
        ("V2", "2.7 V to 3.3 V at 70 °C", [75, 656, 285, 668]),
        ("B1", "• ", [44, 640, 48, 644]),
        ("C", "Supply current:", [58, 636, 180, 648]),
    ]
    if case == "S02":
        right = [("R" + name, text.replace("2.4", "7.0").replace("3.6", "9.0"),
                  [x + 300 if index in {0, 2} else x for index, x in enumerate(box)])
                 for name, text, box in rows]
        rows = [row for pair in zip(rows, right, strict=True) for row in pair]
    elif case == "S03":
        rows = [row for row in rows if row[0] != "B0"]
    elif case == "S04":
        rows.insert(2, ("AMB", "Input voltage:", [58, 700, 170, 712]))
    elif case == "S08":
        rows = rows[:2]
        for i in range(1, 41):
            y = 680 - 12 * (i - 1)
            rows.extend([(f"M{i}", "– ", [58, y, 64, y + 4]),
                         (f"V{i}", f"{2 + i / 100:.2f} V to {3 + i / 100:.2f} V at {i} °C; valid only while idle.",
                          [75, y - 4, 575, y + 8])])
        rows.extend([("B1", "• ", [44, 188, 48, 192]), ("C", "Supply current:", [58, 184, 180, 196])])
    return rows


def parser_box(box):
    return {"l": box[0], "b": box[1], "r": box[2], "t": box[3], "coord_origin": "BOTTOMLEFT"}


def adapter_input(case="S01"):
    rows = dev_rows(case)
    document = {"pages": {"1": {"size": {"width": 900 if case == "S02" else 600, "height": 800}}},
                "body": {"self_ref": "#/body", "children": [{"$ref": f"#/texts/{name}"} for name, _, _ in rows]},
                "texts": [{"self_ref": f"#/texts/{name}", "parent": {"$ref": "#/body"}, "children": [],
                           "label": "text", "orig": text, "text": text,
                           "prov": [{"page_no": 1, "charspan": [0, len(text)], "bbox": parser_box(box)}]}
                          for name, text, box in rows], "groups": [], "tables": [], "pictures": []}
    width = document["pages"]["1"]["size"]["width"]
    page = {"page_index": 0, "width": width, "height": 800, "media_box": [0, 0, width, 800],
            "crop_box": [0, 0, width, 800], "rotation": 0, "classification": "native"}
    observed = None
    if case in {"S06", "S07"}:
        page["classification"] = "mixed"
        cells = [{"text": text, "bbox": parser_box(box), "from_ocr": name in {"M1", "V1"},
                  "confidence": .99 if name in {"M1", "V1"} else None} for name, text, box in rows]
        observed = {0: {"cell_count": 2, "cells": cells}}
        if case == "S07":
            observed[0]["preprocessing"] = [{"cell_ocr": [{"numeric_unresolved_parser_bbox": parser_box(rows[3][2])}]}]
    return document, page, observed


def index_dev(storage, case="S01", enabled=True):
    settings, db, _, indexer = storage
    settings.profile.setdefault("enhanced", {})["explicit_pdf_lists"] = enabled
    document, page, observed = adapter_input(case)
    payload = b"%PDF-1.7\nsynthetic-parser-contract\n" + json.dumps(document, sort_keys=True).encode()
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original(f"i4/{case}.pdf", digest, blob)
    revision = str(uuid5(NAMESPACE_URL, f"i4-structure-{case}-{enabled}"))
    pages, warnings = document_to_pages(document, [page], imported["version_id"], revision,
                                       "regional_ocr" if observed else "native", observed, minimum_confidence=.8)
    extraction = {"sha256": digest, "fingerprint": f"i4-synthetic-parser-{case}-{enabled}",
                  "extraction_revision_id": revision, "page_count": 1, "parser_complete": True,
                  "status": "ready_partial" if case == "S07" else "ready", "pages": pages, "warnings": warnings}
    generation = asyncio.run(indexer.index(imported["job_id"], extraction))
    if case == "S07":
        count = db.one("SELECT count(*) n FROM chunks WHERE generation_id=?", (generation,))["n"]
        indexer.publish(imported["job_id"], generation, count, partial=True, allow_partial=True)
    # Compatibility keeps the frozen cases executable on the pre-I4 revision.
    options = {"explicit_pdf_lists": enabled} if "explicit_pdf_lists" in inspect.signature(ScopeResolver).parameters else {}
    resolver = ScopeResolver(db, **options)
    snapshot = resolver.resolve(Scope(kind="library"))
    chunks = db.rows("SELECT * FROM chunks WHERE generation_id=? ORDER BY rowid", (generation,))
    sources = [resolver.source_for_chunk(chunk, snapshot) for chunk in chunks]
    names = {block["metadata"]["parser_ref"].rsplit("/", 1)[-1]: block for block in pages[0]["blocks"]}
    return {"names": names, "pages": pages, "warnings": warnings, "sources": sources, "chunks": chunks,
            "snapshot": snapshot, "resolver": resolver, "imported": imported, "generation": generation}


def contexts(result):
    return {block["id"]: block["list_context"] for source in result["sources"] for block in source["blocks"]
            if block.get("list_context")}


def assert_exact_dependencies(result, context):
    expected_ids = {piece["block_id"] for piece in [context["heading"], context["item"], *context["dependencies"]]}
    group_source = next(source for source in result["sources"]
                        if expected_ids <= {block["id"] for block in source["blocks"]})
    for piece in [context["heading"], context["item"], *context["dependencies"]]:
        block = next(block for block in group_source["blocks"] if block["id"] == piece["block_id"])
        assert block["text"] == piece["text"]
        assert block["start_offset"] == piece["start_offset"] == 0
        assert block["end_offset"] == piece["end_offset"] == len(piece["text"])
        assert block["source_text_hash"] == piece["source_text_hash"] == hashlib.sha256(piece["text"].encode()).hexdigest()


def test_s01_explicit_native_list_keeps_each_value_with_exact_written_dependencies(storage):
    result = index_dev(storage)
    found = contexts(result)
    assert set(found) == {result["names"][name]["id"] for name in ("V1", "V2")}
    for context in found.values():
        assert context["heading"]["text"] == "Supply range:"
        assert context["item_count"] == context["verified_item_count"] == 2 and context["complete"]
        assert_exact_dependencies(result, context)
    assert any("Supply range:" in chunk["text"] and "2.4 V to 3.6 V at 25 °C" in chunk["text"]
               and "2.7 V to 3.3 V at 70 °C" in chunk["text"] for chunk in result["chunks"])


def test_s02_interleaved_columns_never_attach_values_to_the_other_column(storage):
    result = index_dev(storage, "S02")
    found = contexts(result)
    assert len(found) == 4
    for name, heading in (("V1", "P"), ("V2", "P"), ("RV1", "RP"), ("RV2", "RP")):
        context = found[result["names"][name]["id"]]
        assert context["heading"]["block_id"] == result["names"][heading]["id"]
        assert_exact_dependencies(result, context)
    assert found[result["names"]["V1"]["id"]]["group_id"] != found[result["names"]["RV1"]["id"]]["group_id"]


def test_s03_a_colon_and_nearest_title_without_a_parent_marker_are_not_a_list(storage):
    result = index_dev(storage, "S03")
    assert not contexts(result)
    assert all(not block.get("list_structure") for block in result["names"].values())


def test_s04_ambiguous_parent_marker_does_not_choose_a_title_arbitrarily(storage):
    result = index_dev(storage, "S04")
    assert not contexts(result)
    assert all(not block.get("list_structure") for block in result["names"].values())


def test_s05_selected_value_never_imports_its_title_or_markers_from_outside_scope(storage):
    result = index_dev(storage, "S05")
    assert len(contexts(result)) == 2
    item = result["names"]["V1"]
    span = {"extractionRevisionId": item["extraction_revision_id"], "blockId": item["id"],
            "blockTextSha256": item["source_text_hash"], "offsetUnit": "unicode_code_point",
            "startOffset": 0, "endOffset": len(item["text"])}
    selected = result["resolver"].resolve(Scope(kind="selection", versionId=result["imported"]["version_id"], spans=[span]))
    sources = result["resolver"].selected_sources(selected)
    assert len(sources) == 1 and sources[0]["text"] == item["text"]
    assert not sources[0]["blocks"][0].get("list_context")
    assert "Supply range:" not in json.dumps(sources)
    narrowed = copy.copy(result["snapshot"])
    narrowed.block_ids = [item["id"]]
    for chunk in result["chunks"]:
        source = result["resolver"].source_for_chunk(chunk, narrowed)
        if source:
            assert source["text"] == item["text"]
            assert not source["blocks"][0].get("list_context")


def test_s06_mixed_resolved_list_keeps_effective_native_and_ocr_provenance(storage):
    result = index_dev(storage, "S06")
    found = contexts(result)
    assert len(found) == 2
    context = found[result["names"]["V1"]["id"]]
    assert_exact_dependencies(result, context)
    source = next(source for source in result["sources"] if any(block.get("list_context") for block in source["blocks"]))
    methods = {block["id"]: block["extraction_method"] for block in source["blocks"]}
    assert methods[result["names"]["P"]["id"]] == "native"
    assert methods[result["names"]["V1"]["id"]] == "ocr"
    assert methods[result["names"]["V2"]["id"]] == "native"
    assert source["extraction_methods"] == ["native", "ocr"]


def test_s07_ambiguous_ocr_value_is_not_qualified_and_other_value_stays_explicitly_partial(storage):
    result = index_dev(storage, "S07")
    found = contexts(result)
    assert result["names"]["V1"]["id"] not in found
    context = found[result["names"]["V2"]["id"]]
    assert context["item_count"] == 2 and context["verified_item_count"] == 1 and not context["complete"]
    assert any(region["reason"] == "OCR_NUMERIC_AMBIGUITY" for region in result["pages"][0]["unresolved_regions"])
    assert storage[1].one("SELECT state FROM index_generations WHERE id=?", (result["generation"],))["state"] == "ready_partial"


def test_s08_long_list_splits_at_existing_chunk_budget_without_losing_dependencies(storage):
    result = index_dev(storage, "S08")
    found = contexts(result)
    assert len(found) == 40
    group_sources = [source for source in result["sources"] if any(block.get("list_context") for block in source["blocks"])]
    assert len(group_sources) >= 2
    assert all(chunk["e5_tokens"] <= 320 for chunk in result["chunks"])
    for context in found.values():
        assert context["item_count"] == 40 and context["complete"]
        assert context["item"]["text"].endswith("valid only while idle.")
        assert_exact_dependencies(result, context)
    first = group_sources[0]
    assert 0 < sum(bool(block.get("list_context")) for block in first["blocks"]) < 40


@pytest.mark.parametrize("enabled", [False, True])
def test_list_flag_ablates_packing_and_context_without_removing_source_metadata(storage, enabled):
    result = index_dev(storage, enabled=enabled)
    assert len(contexts(result)) == (2 if enabled else 0)
    assert len(result["chunks"]) == (1 if enabled else 8)
    assert sum(bool(block.get("list_structure")) for block in result["names"].values()) == 2
    settings, _, _, indexer = storage
    before = indexer.generation_fingerprint("unchanged-extraction")
    settings.profile["enhanced"]["explicit_pdf_lists"] = not enabled
    assert indexer.generation_fingerprint("unchanged-extraction") != before


@pytest.mark.parametrize("damage", ["hash", "text", "revision", "geometry", "annotation", "method", "missing_marker", "unresolved"])
def test_list_certificate_is_reconstructed_from_pinned_db_and_rejects_damage(storage, damage):
    from services.api.evidence_selection import verified_list_context

    result = index_dev(storage)
    db = storage[1]
    generation, item = result["generation"], result["names"]["V1"]
    assert verified_list_context(db, result["snapshot"], generation, item["id"])
    if damage == "hash":
        db.execute("UPDATE blocks SET source_text_hash=? WHERE generation_id=? AND id=?", ("0" * 64, generation, item["id"]))
    elif damage == "text":
        db.execute("UPDATE blocks SET text=? WHERE generation_id=? AND id=?", ("2.4 V to 9.6 V at 25 °C", generation, item["id"]))
    elif damage == "revision":
        db.execute("INSERT INTO extraction_revisions SELECT ?,version_id,fingerprint,source_hash,path,created_at "
                   "FROM extraction_revisions WHERE id=?", ("other-revision", item["extraction_revision_id"]))
        db.execute("UPDATE blocks SET extraction_revision_id=? WHERE generation_id=? AND id=?", ("other-revision", generation, item["id"]))
    elif damage == "geometry":
        db.execute("UPDATE blocks SET bbox_json=? WHERE generation_id=? AND id=?", (json.dumps([375, 676, 585, 688]), generation, item["id"]))
    elif damage in {"annotation", "method"}:
        row = db.one("SELECT metadata_json FROM blocks WHERE generation_id=? AND id=?", (generation, item["id"]))
        metadata = json.loads(row["metadata_json"])
        if damage == "annotation":
            metadata["list_structure"]["heading_block_id"] = result["names"]["C"]["id"]
        else:
            metadata["metadata"]["extraction_method"] = "unknown"
        db.execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id=?", (json.dumps(metadata), generation, item["id"]))
    elif damage == "missing_marker":
        db.execute("DELETE FROM blocks WHERE generation_id=? AND id=?", (generation, result["names"]["B0"]["id"]))
    else:
        row = db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=0", (generation,))
        page = json.loads(row["geometry_json"])
        page["unresolved_regions"] = [{"bbox": item["bbox"], "reason": "OCR_NUMERIC_AMBIGUITY"}]
        db.execute("UPDATE pages SET geometry_json=? WHERE generation_id=? AND page_index=0", (json.dumps(page), generation))
    assert verified_list_context(db, result["snapshot"], generation, item["id"]) is None


@pytest.mark.parametrize("missing", ["heading", "parent_marker", "item_marker", "list_boundary_marker", "list_boundary"])
def test_omitted_or_truncated_visible_dependency_cannot_keep_a_stale_context(storage, missing):
    from services.api.evidence_selection import attach_list_contexts

    result = index_dev(storage)
    item_id = result["names"]["V1"]["id"]
    context = contexts(result)[item_id]
    piece = context["heading"] if missing == "heading" else next(piece for piece in context["dependencies"] if piece["kind"] == missing)
    source = copy.deepcopy(result["sources"][0])
    source["blocks"] = [block for block in source["blocks"] if block["id"] != piece["block_id"]]
    source["text"] = "\n".join(block["text"] for block in source["blocks"])
    checked = attach_list_contexts(storage[1], result["snapshot"], source, {item_id})
    assert not next(block for block in checked["blocks"] if block["id"] == item_id).get("list_context")


def test_tiny_chunk_budget_preserves_text_but_does_not_create_partial_list_proofs(storage):
    storage[0].profile["chunking"]["target_tokens"] = 12
    result = index_dev(storage)
    assert not contexts(result)
    assert all(chunk["e5_tokens"] <= 12 for chunk in result["chunks"])
    for original in result["names"].values():
        blocks = sorted((block for source in result["sources"] for block in source["blocks"] if block["id"] == original["id"]),
                        key=lambda block: block["start_offset"])
        assert "".join(block["text"] for block in blocks) == original["text"]


@pytest.mark.parametrize("damage", ["bbox_missing", "rotated", "page_break", "closing_marker_missing", "qualifier_between_rows", "possible_minus_sign"])
def test_layout_uncertainty_never_becomes_nearest_heading_attribution(damage):
    from services.ingestion.pdf_structure import annotate_explicit_lists

    document, page, _ = adapter_input()
    pages, _ = document_to_pages(document, [page], "version", "revision", "native")
    page = pages[0]
    names = {block["metadata"]["parser_ref"].rsplit("/", 1)[-1]: block for block in page["blocks"]}
    assert names["V1"].get("list_structure")
    if damage == "bbox_missing":
        names["P"]["bbox"] = None
    elif damage == "rotated":
        page["rotation"] = 90
    elif damage == "page_break":
        names["V1"]["page_index"] = 1
    elif damage == "closing_marker_missing":
        page["blocks"].remove(names["B1"])
    elif damage == "possible_minus_sign":
        # A dash almost touching a number can be its mathematical sign. It
        # cannot be dropped as a list marker while certifying a positive value.
        names["V1"]["bbox"][0] = names["M1"]["bbox"][2] + .5
    else:
        text = "Only valid with external cooling."
        page["blocks"].append({**copy.deepcopy(names["V1"]), "id": "unmarked-qualifier", "text": text, "raw_text": text,
                               "source_text_hash": hashlib.sha256(text.encode()).hexdigest(), "bbox": [75, 669, 285, 675]})
    annotate_explicit_lists(page)
    assert all(not block.get("list_structure") for block in page["blocks"])


def test_list_reconstruction_never_borrows_another_generation_or_clipped_scope(storage):
    from services.api.evidence_selection import verified_list_context

    result = index_dev(storage)
    snapshot = copy.deepcopy(result["snapshot"])
    item = result["names"]["V1"]
    assert verified_list_context(storage[1], snapshot, "foreign-generation", item["id"]) is None
    snapshot.block_ids = [block["id"] for block in result["names"].values() if block is not result["names"]["B1"]]
    assert verified_list_context(storage[1], snapshot, result["generation"], item["id"]) is None
    snapshot = copy.deepcopy(result["snapshot"])
    snapshot.versions[result["generation"]] = "another-document-version"
    assert verified_list_context(storage[1], snapshot, result["generation"], item["id"]) is None


def test_legacy_extraction_without_list_annotations_remains_unattributed(storage):
    from services.api.evidence_selection import verified_list_context

    result = index_dev(storage)
    item = result["names"]["V1"]
    row = storage[1].one("SELECT metadata_json FROM blocks WHERE generation_id=? AND id=?", (result["generation"], item["id"]))
    metadata = json.loads(row["metadata_json"])
    metadata.pop("list_structure")
    storage[1].execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id=?",
                       (json.dumps(metadata), result["generation"], item["id"]))
    assert verified_list_context(storage[1], result["snapshot"], result["generation"], item["id"]) is None


def test_structural_inspection_stops_at_the_registered_page_block_cap():
    from services.ingestion.pdf_structure import MAX_LIST_PAGE_BLOCKS, annotate_explicit_lists

    document, page, _ = adapter_input()
    pages, _ = document_to_pages(document, [page], "version", "revision", "native")
    page = pages[0]
    assert any(block.get("list_structure") for block in page["blocks"])
    page["blocks"].extend({"id": f"empty-{index}", "text": "", "type": "figure"} for index in range(MAX_LIST_PAGE_BLOCKS))
    annotate_explicit_lists(page)
    assert all(not block.get("list_structure") for block in page["blocks"])


@pytest.mark.parametrize("reason,box,complete", [
    ("OCR_NUMERIC_AMBIGUITY", [58, 655, 285, 670], False),
    ("OCR_TEXT_UNRESOLVED", [58, 655, 285, 670], False),
    ("OCR_NUMERIC_AMBIGUITY", [358, 655, 585, 670], True),
    ("GRAPHIC_INTERPRETATION_UNAVAILABLE", [58, 655, 285, 670], True),
])
def test_known_unread_gap_inside_list_prevents_completeness_without_inventing_item_count(reason, box, complete):
    from services.ingestion.pdf_structure import annotate_explicit_lists, explicit_list_groups

    document, page, _ = adapter_input()
    pages, _ = document_to_pages(document, [page], "version", "revision", "native")
    page = pages[0]
    page["blocks"] = [block for block in page["blocks"]
                      if block["metadata"]["parser_ref"].rsplit("/", 1)[-1] not in {"M2", "V2"}]
    page["unresolved_regions"] = [{"reason": reason, "bbox": box}]
    groups = explicit_list_groups(page)
    assert len(groups) == 1 and len(groups[0]["items"]) == 1
    assert groups[0]["items"][0]["verified"]
    assert groups[0]["complete"] is complete
    annotate_explicit_lists(page)
    item = next(block for block in page["blocks"] if block["metadata"]["parser_ref"].endswith("/V1"))
    assert item["text"] == "2.4 V to 3.6 V at 25 °C"
    assert item["list_structure"]["item_count"] == item["list_structure"]["verified_item_count"] == 1
    assert item["list_structure"]["complete"] is complete
