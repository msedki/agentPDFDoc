"""Page-header authority through real SQLite, table replay and publication.

The PDF text and glyphs are explicitly invented observations. Embedding,
vector and token transports use the existing doubles; no native fidelity or
model result is claimed. A subject is never fabricated from the request/file.
"""

import copy
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import render

from services.api.errors import ApiError
from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.geometry import docling_box_to_pdf
from services.ingestion.table_geometry import build_table_general_conditions

CONDITIONS = "TA = 18°C. V+ = 4V, V– = 0V unless otherwise noted."
QUESTION = ("Dans le tableau Electrical Characteristics du DEV728, quels sont les délais de propagation typiques "
            "pour des overdrives de 7 mV et 70 mV ? Donne aussi les conditions d’essai associées "
            "et les conditions générales du tableau.")
ROWS = [[(0, "PARAMETER"), (1, "CONDITIONS"), (2, "MIN"), (3, "TYP"), (4, "MAX"), (5, "UNITS")],
        [(0, "DEV728A Input Offset Voltage"), (1, "TA = 18 °C"), (3, "0.7"), (5, "mV")],
        [(0, "Propagation Delay"), (1, "COUT = 33pF Overdrive = 7mV"), (3, "21"), (5, "µs")],
        [(0, "Propagation Delay"), (1, "COUT = 33pF Overdrive = 70mV"), (3, "13"), (5, "µs")]]


def workspace(storage, monkeypatch, *, change=None, local_subject=None, filename="observations.pdf", section_layout=None,
              section_subject=None):
    indexer = storage[3]
    actual_index = indexer.index
    captured = {}

    async def index_with_header(job_id, extraction):
        page = extraction["pages"][0]
        original = next(item for item in page["blocks"] if item["id"] == "general-heading")
        header = {**copy.deepcopy(original), "id": "page-subject", "type": "text", "text": "DEV728",
                  "raw_text": "DEV728", "section_id": "preceding-section",
                  "source_text_hash": hashlib.sha256(b"DEV728").hexdigest(),
                  "bbox": [4, page["height"] - 6, 40, page["height"] - 1],
                  "metadata": {"label": "page_header", "extraction_method": "native", "ocr_used": False}}
        page["blocks"].insert(0, header)
        if change is not None:
            change(page, header)
        table = next(item for item in page["blocks"] if item["type"] == "table")
        table["section_id"] = original["id"]
        original["section_id"] = original["id"]
        extraction["sections"] = [{"id": original["id"], "title": original["text"], "page_start": 0, "page_end": 0,
                                   "block_ids": [original["id"], table["id"]]}]
        table["metadata"]["table_general_conditions"] = build_table_general_conditions(
            table, page["blocks"], page, source_sha256=extraction["sha256"])
        captured.update(page=copy.deepcopy(page), header=copy.deepcopy(header))
        return await actual_index(job_id, extraction)

    monkeypatch.setattr(indexer, "index", index_with_header)
    rows = copy.deepcopy(ROWS)
    if local_subject:
        for index in (2, 3):
            rows[index][0] = (0, local_subject + " Propagation Delay")
    if section_layout == "normal":
        rows = [rows[0], [(0, "Supply section")], rows[1], [(0, "Comparator section")], *rows[2:]]
    elif section_layout == "reverse":
        rows = [rows[0], [(0, "Comparator section")], *rows[2:], [(0, "Supply section")], rows[1]]
    if section_subject:
        rows = [[(column, section_subject + " " + text if text == "Comparator section" else text)
                 for column, text in fields] for fields in rows]

    def explicit_sections(block):
        data = block["metadata"]["table_data"]
        for cell in data["table_cells"]:
            if cell["text"] == "Supply section" or cell["text"].endswith("Comparator section"):
                cell.update(row_section=True, row_header=False, column_header=False, end_col_offset_idx=data["num_cols"])

    search, snapshot, source, _ = witnessed_sparse_table(storage, rows, target=4 if section_layout == "normal" else 2,
                                                        mutate=explicit_sections, general_conditions=CONDITIONS)
    search.db.execute("UPDATE documents SET name=? WHERE id=?", (filename, source["document_id"]))
    return SimpleNamespace(db=search.db, resolver=search.resolver, snapshot=snapshot, source=source, **captured)


def sources(work, *, retain_header=True, snapshot=None, question=QUESTION):
    snapshot = snapshot or work.snapshot
    source, _ = table_bundle(work.db, snapshot, work.source, question=question)
    source["source_id"] = "S001"
    result = [source]
    if retain_header:
        chunks = work.db.rows("SELECT c.* FROM chunks c JOIN chunk_sources s ON s.chunk_uuid=c.chunk_uuid "
                              "WHERE s.block_id='page-subject' ORDER BY c.id")
        for chunk in chunks:
            header_source = work.resolver.source_for_chunk(dict(chunk), snapshot)
            if header_source is None:
                continue
            blocks = [item for item in header_source["blocks"] if item["id"] == "page-subject"]
            if not blocks:
                continue
            result.append({**header_source, "source_id": "S002", "blocks": blocks,
                           "text": "\n".join(item["text"] for item in blocks)})
            break
    return result


def catalogue(work, *, retain_header=True, snapshot=None, question=QUESTION):
    snapshot = snapshot or work.snapshot
    return StructuredAnswerBuilder(work.db, snapshot, question, enforce_contract=True).catalogue(
        sources(work, retain_header=retain_header, snapshot=snapshot, question=question), "question")


def assert_no_inherited_values(cat):
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert not result["answer_contract"]["matched_relations"]
    assert "TYP = 21" not in result["text"] and "TYP = 13" not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"
    return result


def test_unique_retained_page_subject_covers_each_delay_with_its_literal_cited_dependency(storage, monkeypatch):
    work = workspace(storage, monkeypatch)
    cat = catalogue(work)
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered", assessment
    facts = assessment["matched_relations"]
    assert {(tuple(fact["values"]), fact["unit"]) for fact in facts} == {(("21",), "µs"), (("13",), "µs")}
    assert len(assessment["obligations"]) == 2 and all(item["covered"] for item in assessment["obligations"])
    header = next(item for item in cat.references if item["text"] == "DEV728")
    assert header["source_ids"] == ["S002"]
    for fact in facts:
        assert fact["subjects"] == ["DEV728"] and fact["entity_context_identifiers"] == ["dev728"]
        assert fact["general_conditions_verified"] and "COUT = 33pF" in fact["local_condition"]
        assert header["id"] in fact["reference_ids"]
        assert fact["dependency_spans"][header["id"]] == [{"start_offset": 0, "end_offset": 6}]
        assert fact["page_subject_binding"]["header"]["source_text_hash"] == hashlib.sha256(b"DEV728").hexdigest()
    assert "Extrait : « DEV728 »" in result["text"] and "[S002]" in result["text"]
    assert CONDITIONS in result["text"] and "DEV728A" not in result["text"]
    assert any(item["source_id"] == "S002" for item in result["citation_spans"])
    assert cat.verify_rendered(result)["status"] == "passed"
    row = work.db.one("SELECT section_id FROM blocks WHERE id='page-subject'")
    assert row["section_id"] == "preceding-section"
    # Dropping the dependent source from the final evidence set removes both
    # facts; neither their nearby table labels nor the request substitute for it.
    checked = cat.contract.assess([item for item in cat.references if item["id"] != header["id"]])
    assert not checked["matched_relations"] and not any(item["covered"] for item in checked["obligations"])


def test_matching_filename_and_question_cannot_supply_a_pdf_table_subject(storage, monkeypatch):
    def without_header(page, header):
        page["blocks"].remove(header)

    work = workspace(storage, monkeypatch, change=without_header, filename="DEV728.pdf")
    assert_no_inherited_values(catalogue(work))


def test_page_identity_is_not_fetched_when_its_evidence_was_not_retained(storage, monkeypatch):
    work = workspace(storage, monkeypatch)
    assert_no_inherited_values(catalogue(work, retain_header=False))


@pytest.mark.parametrize("label", ["page_footer", "section_header", None])
def test_only_explicit_page_header_type_can_authorize_the_page_subject(storage, monkeypatch, label):
    def relabel(_page, header):
        header["metadata"]["label"] = label

    work = workspace(storage, monkeypatch, change=relabel)
    assert_no_inherited_values(catalogue(work))


@pytest.mark.parametrize("text", ["DEV728 / DEV941", "https://example.test/DEV728", "DEV728 family", "I2C"])
def test_ambiguous_or_nonstandalone_header_never_lends_a_subject(storage, monkeypatch, text):
    def relabel(_page, header):
        header.update(text=text, raw_text=text, source_text_hash=hashlib.sha256(text.encode()).hexdigest())

    work = workspace(storage, monkeypatch, change=relabel)
    assert_no_inherited_values(catalogue(work))


def test_competing_page_header_prevents_choosing_a_subject_by_first_match(storage, monkeypatch):
    def add_header(page, header):
        second = {**copy.deepcopy(header), "id": "competing-header", "text": "DEV941", "raw_text": "DEV941",
                  "source_text_hash": hashlib.sha256(b"DEV941").hexdigest()}
        second["bbox"] = [50, header["bbox"][1], 86, header["bbox"][3]]
        page["blocks"].append(second)

    work = workspace(storage, monkeypatch, change=add_header)
    assert_no_inherited_values(catalogue(work))


def test_competing_section_between_header_and_table_blocks_inheritance(storage, monkeypatch):
    def conflicting_section(page, _header):
        title = next(item for item in page["blocks"] if item["id"] == "general-heading")
        text = "DEV941 Electrical characteristics"
        title.update(text=text, raw_text=text, source_text_hash=hashlib.sha256(text.encode()).hexdigest())

    work = workspace(storage, monkeypatch, change=conflicting_section)
    assert_no_inherited_values(catalogue(work))


@pytest.mark.parametrize("method", ["unknown", "ocr"])
def test_header_reading_must_be_native_or_independently_corroborated(storage, monkeypatch, method):
    def uncertain_header(_page, header):
        header["metadata"]["extraction_method"] = method
        header["metadata"]["ocr_used"] = method == "ocr"

    work = workspace(storage, monkeypatch, change=uncertain_header)
    assert_no_inherited_values(catalogue(work))


@pytest.mark.parametrize("position", ["below_heading", "overlap_table", "zero_area", "outside"])
def test_header_needs_positive_page_geometry_above_all_body_blocks(storage, monkeypatch, position):
    def move_header(page, header):
        if position == "below_heading":
            header["bbox"] = [4, page["height"] - 21, 40, page["height"] - 17]
        elif position == "overlap_table":
            header["bbox"] = [4, page["height"] - 60, 40, page["height"] - 35]
        elif position == "zero_area":
            header["bbox"][2] = header["bbox"][0]
        else:
            header["bbox"][0] = -20

    work = workspace(storage, monkeypatch, change=move_header)
    assert_no_inherited_values(catalogue(work))


def test_full_page_authority_is_not_available_to_a_complete_but_narrow_block_scope(storage, monkeypatch):
    work = workspace(storage, monkeypatch)
    ids = [row["id"] for row in work.db.rows("SELECT id FROM blocks WHERE generation_id=?", (work.source["generation_id"],))]
    snapshot = replace(work.snapshot, block_ids=ids)
    assert_no_inherited_values(catalogue(work, snapshot=snapshot))


def test_explicit_local_variant_keeps_priority_and_does_not_alias_to_the_page_subject(storage, monkeypatch):
    work = workspace(storage, monkeypatch, local_subject="DEV941")
    assert_no_inherited_values(catalogue(work))
    cat = catalogue(work, question=QUESTION.replace("DEV728", "DEV941"))
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(fact["subjects"] == ["DEV941"] and not fact.get("page_subject_binding")
               for fact in result["answer_contract"]["matched_relations"])
    assert "Extrait : « DEV728 »" not in result["text"]


@pytest.mark.parametrize("field", ["version_id", "extraction_revision_id"])
def test_extraction_identity_mismatch_cannot_bind_matching_header_text(storage, monkeypatch, field):
    work = workspace(storage, monkeypatch)
    row = work.db.one("SELECT metadata_json FROM blocks WHERE id='page-subject'")
    metadata = json.loads(row["metadata_json"])
    metadata[field] = "another-extraction-identity"
    work.db.execute("UPDATE blocks SET metadata_json=? WHERE id='page-subject'", (json.dumps(metadata),))
    assert_no_inherited_values(catalogue(work))


@pytest.mark.parametrize("alteration", ["hash", "page", "revision", "version", "offset"])
def test_changed_header_span_or_hash_is_rejected_before_publication(storage, monkeypatch, alteration):
    work = workspace(storage, monkeypatch)
    retained = sources(work)
    source, block = retained[-1], retained[-1]["blocks"][0]
    if alteration == "hash":
        block["source_text_hash"] = "0" * 64
    elif alteration == "page":
        block["page_index"] = 1
    elif alteration == "revision":
        source["extraction_revision_id"] = "another-revision"
    elif alteration == "version":
        source["version_id"] = "another-version"
    else:
        block["start_offset"] = 1
    with pytest.raises(ApiError, match="preuves autorisées"):
        StructuredAnswerBuilder(work.db, work.snapshot, QUESTION, enforce_contract=True).catalogue(retained, "question")


@pytest.mark.parametrize("limit", ["MAX_PAGE_BLOCKS", "MAX_PAGE_CHARS", "MAX_PAGE_METADATA_CHARS"])
def test_page_inspection_budget_never_grants_a_partial_subject_authority(storage, monkeypatch, limit):
    from services.api import table_subjects

    work = workspace(storage, monkeypatch)
    monkeypatch.setattr(table_subjects, limit, 2)
    assert_no_inherited_values(catalogue(work))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_page_subject_geometry_uses_the_verified_rotated_and_cropped_frame(rotation):
    from services.api.table_subjects import _display_rectangle

    page = {"page_index": 0, "rotation": rotation, "crop_box": [12, 20, 212, 320], "effective_box": [12, 20, 212, 320]}
    size = (300, 200) if rotation in {90, 270} else (200, 300)
    display = {"l": 25, "t": 8, "r": 75, "b": 17, "coord_origin": "TOPLEFT"}
    original = docling_box_to_pdf(display, size, page)
    assert _display_rectangle(original, page) == [25, 8, 75, 17]


def test_page_rotation_drift_is_not_compensated_by_a_matching_subject(storage, monkeypatch):
    work = workspace(storage, monkeypatch)
    row = work.db.one("SELECT geometry_json FROM pages WHERE page_index=0")
    page = json.loads(row["geometry_json"])
    page["rotation"] = 90
    work.db.execute("UPDATE pages SET geometry_json=? WHERE page_index=0", (json.dumps(page),))
    assert_no_inherited_values(catalogue(work))


def test_emitted_heading_conditions_and_subject_frames_keep_db_hash_without_bulk_diagnostics(storage, monkeypatch):
    def large_diagnostic(page, _header):
        page["regional_diagnostics"] = {"observations": "x" * 8192}

    work = workspace(storage, monkeypatch, change=large_diagnostic)
    raw = work.db.one("SELECT geometry_json FROM pages WHERE page_index=0")["geometry_json"]
    expected_hash = hashlib.sha256(raw.encode()).hexdigest()
    retained = sources(work)
    frames = [block["page"] for source in retained for block in source["blocks"]]
    assert frames and all("regional_diagnostics" not in frame and frame["stored_geometry_sha256"] == expected_hash for frame in frames)
    cat = StructuredAnswerBuilder(work.db, work.snapshot, QUESTION, enforce_contract=True).catalogue(retained, "question")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(fact["page_subject_binding"]["page"]["stored_geometry_sha256"] == expected_hash
               and "regional_diagnostics" not in fact["page_subject_binding"]["page"]
               for fact in result["answer_contract"]["matched_relations"])
    assert work.db.one("SELECT geometry_json FROM pages WHERE page_index=0")["geometry_json"] == raw


@pytest.mark.parametrize("layout", ["normal", "reverse"])
def test_sibling_table_sections_remain_autonomous_with_their_data_dependencies(storage, monkeypatch, layout):
    work = workspace(storage, monkeypatch, section_layout=layout)
    cat = catalogue(work)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    section = next(item for item in cat.references if item["text"] == "Comparator section")
    assert section["table_quality"]["state"] == "supported"
    assert section["table_context"]["row_role"] == "section"
    assert not any(item["kind"] == "row_section" for item in section["table_context"]["dependencies"])
    assert all(section["id"] in fact["reference_ids"] for fact in result["answer_contract"]["matched_relations"])
    assert "Comparator section" in result["text"] and "Supply section" not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"
    # The other sibling's written local model keeps its own identity; the
    # later timing section does not become an ancestor of the offset row.
    other = catalogue(work, question="What is DEV728A typical input offset voltage at TA = 18 °C?")
    other_result = render(other)
    assert other_result["answer_contract"]["status"] == "covered"
    assert any(fact["values"] == ["0.7"] and fact["subjects"] == ["DEV728A"]
               for fact in other_result["answer_contract"]["matched_relations"])
    assert "Supply section" in other_result["text"] and "Comparator section" not in other_result["text"]


@pytest.mark.parametrize("gate", ["missing", "clipped"])
def test_a_missing_or_clipped_section_cannot_be_promoted_from_native_text(storage, monkeypatch, gate):
    work = workspace(storage, monkeypatch, section_layout="normal")
    retained = sources(work)
    target = next(block for block in retained[0]["blocks"] if block["text"] == "Comparator section")
    if gate == "missing":
        retained[0]["blocks"].remove(target)
    else:
        target.update(text=target["text"][1:], start_offset=target["start_offset"] + 1)
        target.pop("table_context", None)
    retained[0]["text"] = "\n".join(block["text"] for block in retained[0]["blocks"])
    cat = StructuredAnswerBuilder(work.db, work.snapshot, QUESTION, enforce_contract=True).catalogue(retained, "question")
    assert_no_inherited_values(cat)


def test_a_contradictory_local_table_section_blocks_page_subject_inheritance(storage, monkeypatch):
    work = workspace(storage, monkeypatch, section_layout="normal", section_subject="DEV941")
    cat = catalogue(work)
    section = next(item for item in cat.references if item["text"] == "DEV941 Comparator section")
    assert section["table_quality"]["state"] == "supported"
    assert_no_inherited_values(cat)
