"""Invented PDF prose observations, real SQLite and exact publication checks.

The text/geometry and transport are explicit unit doubles. No native extraction
or model fidelity is claimed. Printed page identity remains a cited dependency.
"""

import asyncio
import copy
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_retrieval import library_search

from services.api.structured_answer import StructuredAnswerBuilder

REVISION = "7b1f9214-9cbd-47a8-9853-ea90a8f6a037"
QUESTION = "Quelles sont les plages d’alimentation simple et symétrique du DEV728 ?"
RANGES = "The comparator operates from a single 4V to 9V supply or a dual ±2V to ±4.5V supply."
BULLET = "n 23µs Propagation Delay with 7mV Overdrive"
LIMIT_QUESTION = ("La première page du DEV728 permet-elle de garantir un délai maximal de propagation "
                  "de 23 µs pour un overdrive de 1 mV ?")
TITLE = "DEV728 Low-Power Comparator With Reference"


def printed_title(page):
    page["blocks"][0].update(type="heading", text=TITLE)
    page["blocks"][0]["metadata"]["label"] = "section_header"


def workspace(storage, *, text=RANGES, introduction="The DEV®728 is a comparator.", change=None,
              filename="observations.pdf", label="text"):
    settings, db, _, indexer = storage
    blocks = [
        {"id": "page-subject", "type": "text", "text": "DEV728", "bbox": [490, 747, 575, 760],
         "section_id": "historical-unrelated-section", "metadata": {"label": "page_header"}},
        {"id": "description", "type": "heading", "text": "DESCRIPTION", "bbox": [320, 690, 440, 705],
         "metadata": {"label": "section_header"}},
        {"id": "introduction", "type": "text", "text": introduction, "bbox": [320, 650, 575, 678],
         "metadata": {"label": "text"}},
        {"id": "target", "type": "text", "text": text, "bbox": [320, 598, 575, 630],
         "section_id": "historical-unrelated-section", "metadata": {"label": label}},
    ]
    page = {"page_index": 0, "width": 600, "height": 800, "media_box": [0, 0, 600, 800],
            "crop_box": [0, 0, 600, 800], "effective_box": [0, 0, 600, 800], "rotation": 0,
            "classification": "native", "blocks": blocks}
    if change:
        change(page)
    payload = b"%PDF-1.7\n" + "\n".join(block["text"] for block in page["blocks"]).encode()
    source_hash = hashlib.sha256(payload).hexdigest()
    page["source_sha256"] = source_hash
    blob = settings.data_dir / "originals" / (source_hash + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original(filename, source_hash, blob)
    for block in page["blocks"]:
        block.update(raw_text=block["text"], precision="block", page_index=0, version_id=imported["version_id"],
                     extraction_revision_id=REVISION, source_text_hash=hashlib.sha256(block["text"].encode()).hexdigest())
        block["metadata"] = {"extraction_method": "native", "ocr_used": False, **block["metadata"]}
    extraction = {"sha256": source_hash, "fingerprint": "i5-prose-page-subject-double-v1", "page_count": 1,
                  "extraction_revision_id": REVISION, "status": "ready", "pages": [page]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    search, snapshot, _ = library_search(storage)
    return SimpleNamespace(db=db, resolver=search.resolver, snapshot=snapshot, page=page)


def sources(work, *, retain_header=True, snapshot=None, clipped=False):
    snapshot = snapshot or work.snapshot
    result = []
    for block_id, source_id in [("target", "S001"), *(([("page-subject", "S002")]) if retain_header else [])]:
        for chunk in work.db.rows("SELECT c.* FROM chunks c JOIN chunk_sources s ON s.chunk_uuid=c.chunk_uuid "
                                  "WHERE s.block_id=? ORDER BY c.id", (block_id,)):
            source = work.resolver.source_for_chunk(dict(chunk), snapshot)
            if source is None:
                continue
            blocks = [block for block in source["blocks"] if block["id"] == block_id]
            if not blocks:
                continue
            if clipped and block_id == "target":
                blocks = copy.deepcopy(blocks)
                blocks[0]["end_offset"] -= 1
                blocks[0]["text"] = blocks[0]["text"][:-1]
            result.append({**source, "source_id": source_id, "blocks": blocks, "text": "\n".join(block["text"] for block in blocks)})
            break
    return result


def catalogue(work, *, question=QUESTION, snapshot=None, retain_header=True, clipped=False):
    snapshot = snapshot or work.snapshot
    return StructuredAnswerBuilder(work.db, snapshot, question, enforce_contract=True).catalogue(
        sources(work, retain_header=retain_header, snapshot=snapshot, clipped=clipped), "question")


def assert_no_page_values(cat):
    result = render(cat, [item["id"] for item in cat.references])
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert not result["answer_contract"]["matched_relations"]
    assert "4V to 9V" not in result["text"] and "23µs" not in result["text"]
    assert not cat.support_ledger()["obligations"][0]["covered"]
    assert cat.verify_rendered(result)["status"] == "passed"
    return result


@pytest.mark.parametrize("introduction", ["The DEV728 is a comparator.", "The DEV®728 is a comparator."])
def test_page_subject_binds_prose_ranges_with_exact_header_dependency(storage, introduction):
    work = workspace(storage, introduction=introduction)
    cat = catalogue(work)
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert len(assessment["obligations"]) == 2 and all(item["covered"] for item in assessment["obligations"])
    facts = assessment["matched_relations"]
    assert {(tuple(item["values"]), item["supply_configuration"], item["polarity"]) for item in facts} == {
        (("4", "9"), "single", None), (("2", "4.5"), "dual", "±")}
    header = next(item for item in cat.references if item["text"] == "DEV728")
    for fact in facts:
        assert fact["subjects"] == ["DEV728"]
        assert fact["page_subject_binding"]["schema_version"] == "prose-page-subject-v1"
        assert fact["page_subject_binding"]["prose"]["block_id"] == "target"
        assert fact["dependency_spans"][header["id"]] == [{"start_offset": 0, "end_offset": 6}]
        assert header["id"] in fact["reference_ids"] and "S002" in fact["source_ids"]
        assert RANGES[fact["source_start"]:fact["source_end"]] == fact["quote"]
    assert "Extrait : « DEV728 »" in result["text"] and "[S002]" in result["text"]
    assert cat.deterministic_plan() is not None
    assert cat.verify_rendered(result)["status"] == "passed"
    assert work.db.one("SELECT section_id FROM blocks WHERE id='target'")["section_id"] == "historical-unrelated-section"
    checked = cat.contract.assess([item for item in cat.references if item["id"] != header["id"]])
    assert not any(item["covered"] for item in checked["obligations"])
    assert not checked["matched_relations"]


def test_unqualified_delay_is_a_cited_bound_diagnostic_without_grammar_or_guarantee_changes(storage):
    work = workspace(storage, text=BULLET, label="list_item")
    cat = catalogue(work, question=LIMIT_QUESTION)
    assert cat.contract.requested_bound == "maximum" and cat.contract.requested_role is None
    assert cat.contract.guarantee_required is False and cat.contract.requested_point_conditions == []
    view = cat.model_view()
    assert len(view["reference_ids"]) == 2
    assert cat.deterministic_plan() is None  # preserved model selection route, no model used here
    result = render(cat, view["reference_ids"])
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    diagnostic = result["answer_contract"]["rejected_relations"]
    assert len(diagnostic) == 1 and diagnostic[0]["reasons"] == ["requested_bound_not_established"]
    assert diagnostic[0]["bound_role"] is None and diagnostic[0]["guarantee"] is None
    assert "La borne demandée n'est pas établie" in result["text"]
    assert BULLET in result["text"] and "Extrait : « DEV728 »" in result["text"]
    assert {item["source_id"] for item in result["citation_spans"]} == {"S001", "S002"}
    assert cat.verify_rendered(result)["status"] == "passed"


def test_diagnostic_selection_completes_only_the_exact_header_dependency(storage):
    cat = catalogue(workspace(storage, text=BULLET, label="list_item"), question=LIMIT_QUESTION)
    target = next(item for item in cat.references if item["text"] == BULLET)
    header = next(item for item in cat.references if item["text"] == "DEV728")
    result = render(cat, [target["id"]])
    assert BULLET in result["text"] and "Extrait : « DEV728 »" in result["text"]
    assert header["id"] in result["answer_contract"]["added_reference_ids"]
    assert {item["source_id"] for item in result["citation_spans"]} == {"S001", "S002"}
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert cat.verify_rendered(result)["status"] == "passed"
    for selected in ([], [header["id"]]):
        limited = render(cat, selected)
        assert BULLET not in limited["text"]  # no new diagnostic is selected for the model


def test_diagnostic_budget_never_separates_a_value_from_its_page_subject(storage):
    work = workspace(storage, text=BULLET, label="list_item", filename="observation_" + "x" * 160 + ".pdf")
    cat = catalogue(work, question=LIMIT_QUESTION)
    target = next(item for item in cat.references if item["text"] == BULLET)
    complete = render(cat, [item["id"] for item in cat.references])
    limited = render(cat, [target["id"]], output_tokens=complete["tokens"] - 1)
    assert BULLET not in limited["text"]
    assert cat.verify_rendered(limited)["status"] == "passed"


def test_page_authority_does_not_add_a_dependency_to_an_independent_qualitative_proof(storage):
    literal = "Le boîtier est étanche uniquement lorsque le couvercle est fermé."
    cat = catalogue(workspace(storage, text=literal), question="Dans quelle condition le boîtier est-il étanche ?")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert literal in result["text"] and "Extrait : « DEV728 »" not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


def test_unique_dominant_printed_title_lends_only_its_exact_identity_span(storage):
    cat = catalogue(workspace(storage, change=printed_title))
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    title = next(item for item in cat.references if item["text"] == TITLE)
    for fact in result["answer_contract"]["matched_relations"]:
        binding = fact["page_subject_binding"]
        assert binding["authority_kind"] == "printed_title" and binding["header"]["text"] == TITLE
        assert binding["header"]["source_text_hash"] == hashlib.sha256(TITLE.encode()).hexdigest()
        assert fact["dependency_spans"][title["id"]] == [{"start_offset": 0, "end_offset": 6}]
    assert "Extrait : « DEV728 »" in result["text"] and "Low-Power Comparator With Reference" not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


def test_printed_title_identity_keeps_its_nonzero_original_offsets(storage):
    def change(page):
        printed_title(page)
        page["blocks"][0]["text"] = "  " + TITLE
    cat = catalogue(workspace(storage, change=change))
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    title = next(item for item in cat.references if item["text"] == "  " + TITLE)
    assert all(item["dependency_spans"][title["id"]] == [{"start_offset": 2, "end_offset": 8}]
               for item in result["answer_contract"]["matched_relations"])
    assert "Extrait : « DEV728 »" in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


def test_matching_composite_header_is_not_itself_an_identity_authority(storage):
    def change(page):
        printed_title(page)
        page["blocks"].append({"id": "composite-header", "type": "text", "text": "DEV728 DOC731 - REVISED 2024",
                               "bbox": [450, 775, 590, 790], "metadata": {"label": "page_header"}})
    work = workspace(storage, change=change)
    cat = catalogue(work)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(item["page_subject_binding"]["header"]["block_id"] == "page-subject"
               for item in result["answer_contract"]["matched_relations"])
    assert "DOC731" not in result["text"]
    assert_no_page_values(catalogue(work, retain_header=False))


@pytest.mark.parametrize("conflict", ["DEV941", "DEV941 DOC731 - REVISED 2024"])
def test_a_different_autonomous_or_composite_header_blocks_printed_title_authority(storage, conflict):
    def change(page):
        printed_title(page)
        page["blocks"].append({"id": "conflicting-header", "type": "text", "text": conflict,
                               "bbox": [450, 775, 590, 790], "metadata": {"label": "page_header"}})
    assert_no_page_values(catalogue(workspace(storage, change=change)))


@pytest.mark.parametrize("defect", ["competing_title", "below_body", "secondary_identifier", "two_identifiers", "uncertain_reading"])
def test_printed_title_needs_a_unique_leading_identity_and_dominant_native_geometry(storage, defect):
    def change(page):
        printed_title(page)
        title = page["blocks"][0]
        if defect == "competing_title":
            page["blocks"].append({**copy.deepcopy(title), "id": "competing-title", "text": "DEV941 Comparator",
                                   "bbox": [30, 747, 270, 760]})
        elif defect == "below_body":
            title["bbox"] = [320, 635, 575, 646]
        elif defect == "secondary_identifier":
            title["text"] = "Precision Comparator DEV728"
        elif defect == "two_identifiers":
            title["text"] = "DEV728 and DEV941 Comparators"
        else:
            title["metadata"].update(extraction_method="ocr", ocr_used=True)
    assert_no_page_values(catalogue(workspace(storage, change=change)))


def test_a_clipped_printed_title_cannot_attest_its_identity_even_when_prefix_survives(storage):
    work = workspace(storage, change=printed_title)
    retained = sources(work)
    title = retained[1]["blocks"][0]
    title["text"], title["end_offset"] = title["text"][:-1], title["end_offset"] - 1
    retained[1]["text"] = title["text"]
    cat = StructuredAnswerBuilder(work.db, work.snapshot, QUESTION, enforce_contract=True).catalogue(retained, "question")
    assert_no_page_values(cat)


def test_printed_title_full_text_is_rechecked_even_outside_the_published_identity_span(storage):
    cat = catalogue(workspace(storage, change=printed_title))
    title = next(item for item in cat.references if item["text"] == TITLE)
    title["text"] = TITLE.replace("Reference", "Prototype")
    assert_no_page_values(cat)


@pytest.mark.parametrize("alteration", ["remove", "text", "hash", "offset", "revision", "quality"])
def test_changed_prose_header_cannot_survive_final_dependency_revalidation(storage, alteration):
    cat = catalogue(workspace(storage, text=BULLET, label="list_item"), question=LIMIT_QUESTION)
    target = next(item for item in cat.references if item["text"] == BULLET)
    header = next(item for item in cat.references if item["text"] == "DEV728")
    if alteration == "remove":
        cat.references.remove(header)
    elif alteration == "text":
        header["text"] = "DEV941"
    elif alteration == "hash":
        header["segments"][0]["source_text_hash"] = "0" * 64
    elif alteration == "offset":
        header["segments"][0]["start_offset"] = 1
    elif alteration == "revision":
        header["extraction_revision_id"] = "another-revision"
    else:
        header["source_quality"]["state"] = "unavailable"
    result = render(cat, [target["id"]])
    assert BULLET not in result["text"]
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("keep_header", [False, True])
def test_filename_or_unretained_header_cannot_supply_a_prose_subject(storage, keep_header):
    def remove_header(page):
        if not keep_header:
            page["blocks"] = [block for block in page["blocks"] if block["id"] != "page-subject"]
    work = workspace(storage, filename="DEV728.pdf", change=remove_header)
    assert_no_page_values(catalogue(work, retain_header=False))


@pytest.mark.parametrize("subject", ["DEV941", "DEV®941"])
def test_competing_predecessor_blocks_anonymous_prose_without_creating_an_alias(storage, subject):
    work = workspace(storage, introduction=f"The {subject} is a comparator.")
    assert_no_page_values(catalogue(work))


def test_a_different_column_identity_is_not_borrowed_as_the_prose_subject(storage):
    def move_introduction(page):
        page["blocks"][2]["bbox"] = [30, 650, 275, 678]
    work = workspace(storage, introduction="DEV941 is compatible with this interface.", change=move_introduction)
    cat = catalogue(work)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(item["subjects"] == ["DEV728"] for item in result["answer_contract"]["matched_relations"])
    assert "DEV941" not in result["text"]
    assert_no_page_values(catalogue(work, retain_header=False))


def test_local_written_identity_keeps_priority_over_header(storage):
    work = workspace(storage, text=RANGES.replace("The comparator", "DEV941"))
    assert_no_page_values(catalogue(work))
    cat = catalogue(work, question=QUESTION.replace("DEV728", "DEV941"))
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(item["subjects"] == ["DEV941"] and not item.get("page_subject_binding")
               for item in result["answer_contract"]["matched_relations"])
    assert "Extrait : « DEV728 »" not in result["text"]


def test_trademarked_target_identity_is_a_conflict_not_a_new_positive_alias(storage):
    work = workspace(storage, text=RANGES.replace("The comparator", "DEV®941"))
    assert_no_page_values(catalogue(work))
    assert_no_page_values(catalogue(work, question=QUESTION.replace("DEV728", "DEV941")))


def test_matching_trademarked_text_uses_the_separate_exact_header_without_rewriting(storage):
    literal = RANGES.replace("The comparator", "DEV®728")
    work = workspace(storage, text=literal)
    cat = catalogue(work)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert "DEV®728" in result["text"] and "Extrait : « DEV728 »" in result["text"]
    assert any(item["source_id"] == "S002" for item in result["citation_spans"])
    assert all(item["page_subject_binding"]["header"]["text"] == "DEV728"
               for item in result["answer_contract"]["matched_relations"])
    assert_no_page_values(catalogue(work, retain_header=False))


def test_truncated_target_cannot_acquire_page_identity(storage):
    assert_no_page_values(catalogue(workspace(storage), clipped=True))


@pytest.mark.parametrize("label", ["page_footer", "section_header", "text", None])
def test_untyped_body_or_footer_cannot_become_a_page_header(storage, label):
    def change(page):
        page["blocks"][0]["metadata"]["label"] = label
    assert_no_page_values(catalogue(workspace(storage, change=change)))


def test_concurrent_standalone_page_headers_cannot_be_chosen_by_first_match(storage):
    def change(page):
        other = {**copy.deepcopy(page["blocks"][0]), "id": "other-header", "text": "DEV941", "bbox": [30, 747, 100, 760]}
        page["blocks"].append(other)
    assert_no_page_values(catalogue(workspace(storage, change=change)))


@pytest.mark.parametrize("block_id", ["page-subject", "target"])
@pytest.mark.parametrize("method", ["unknown", "ocr"])
def test_header_and_prose_need_revalidated_native_or_corroborated_reading(storage, block_id, method):
    def change(page):
        block = next(block for block in page["blocks"] if block["id"] == block_id)
        block["metadata"].update(extraction_method=method, ocr_used=method == "ocr")
    assert_no_page_values(catalogue(workspace(storage, change=change)))


@pytest.mark.parametrize("shape", ["table_kind", "table_metadata", "overlap_table"])
def test_unrevalidated_tables_cannot_take_the_prose_authority_route(storage, shape):
    def change(page):
        target = page["blocks"][-1]
        if shape == "table_kind":
            target["type"] = "table"
        elif shape == "table_metadata":
            target["metadata"]["table_data"] = {"table_cells": [], "num_rows": 0, "num_cols": 0}
        else:
            page["blocks"].append({"id": "covering-table", "type": "table", "text": "4V | 9V",
                                   "bbox": [310, 590, 580, 640], "metadata": {"label": "table"}})
    assert_no_page_values(catalogue(workspace(storage, change=change)))


@pytest.mark.parametrize("use_title", [False, True])
def test_a_narrow_block_scope_cannot_prove_page_identity(storage, use_title):
    work = workspace(storage, change=printed_title if use_title else None)
    snapshot = replace(work.snapshot, block_ids=["page-subject", "target"])
    assert_no_page_values(catalogue(work, snapshot=snapshot))


@pytest.mark.parametrize("change_kind", ["below", "zero_area", "outside", "rotation_drift"])
def test_header_geometry_cannot_be_repaired_by_matching_text(storage, change_kind):
    def change(page):
        if change_kind == "below":
            page["blocks"][0]["bbox"] = [490, 540, 575, 555]
        elif change_kind == "zero_area":
            page["blocks"][0]["bbox"][2] = page["blocks"][0]["bbox"][0]
        elif change_kind == "outside":
            page["blocks"][0]["bbox"][0] = -1
        else:
            page["rotation"] = 90
    assert_no_page_values(catalogue(workspace(storage, change=change)))


@pytest.mark.parametrize("field", ["version_id", "extraction_revision_id"])
def test_page_identity_is_pinned_to_all_stored_block_metadata(storage, field):
    work = workspace(storage)
    row = work.db.one("SELECT metadata_json FROM blocks WHERE id='page-subject'")
    metadata = json.loads(row["metadata_json"])
    metadata[field] = "other-identity"
    work.db.execute("UPDATE blocks SET metadata_json=? WHERE id='page-subject'", (json.dumps(metadata),))
    assert_no_page_values(catalogue(work))


@pytest.mark.parametrize("limit", ["MAX_PAGE_BLOCKS", "MAX_PAGE_CHARS", "MAX_PAGE_METADATA_CHARS"])
def test_page_budget_failure_cannot_leave_partial_subject_authority(storage, monkeypatch, limit):
    import services.api.table_subjects as module

    work = workspace(storage)
    monkeypatch.setattr(module, limit, 1)
    assert_no_page_values(catalogue(work))
