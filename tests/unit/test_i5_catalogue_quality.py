"""Real SQLite/catalogue seam with named synthetic glyph and OCR observations.

No OCR or PDF native engine is substituted for qualification. These tests check
that publication reloads its witness from SQLite, scopes exact spans and refuses
a forged retrieval hint. Embeddings/vector transport use the existing doubles.
"""

import asyncio
import copy
import hashlib

import pytest
import test_i5_table_geometry as geometry_fixture
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_i5_source_quality import reading, token
from test_retrieval import library_search

from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.docling_adapter import table_text
from services.ingestion.source_quality import annotate_ocr_cells, block_quality
from services.ingestion.table_geometry import build_table_quality

PAYLOAD = b"%PDF-1.7\nI5 synthetic witnessed document; no native engine claim."
SOURCE_HASH = hashlib.sha256(PAYLOAD).hexdigest()


def index_blocks(storage, blocks, *, page_width=550):
    settings, db, _, indexer = storage
    path = settings.data_dir / "originals" / (SOURCE_HASH + ".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PAYLOAD)
    imported = db.import_original("DEV728.pdf", SOURCE_HASH, path)
    extraction = {"sha256": SOURCE_HASH, "fingerprint": "i5-synthetic-witness-v1", "status": "ready", "page_count": 1,
                  "pages": [{"page_index": 0, "width": page_width, "height": 400,
                             "crop_box": [0, 0, page_width, 400], "effective_box": [0, 0, page_width, 400], "rotation": 0,
                             "classification": "native", "blocks": blocks}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    search, snapshot, _ = library_search(storage)
    sources = [search.resolver.source_for_chunk(chunk, snapshot) for chunk in db.rows("SELECT * FROM chunks ORDER BY id")]
    return db, snapshot, sources


def table_catalogue(storage, monkeypatch, *, missing_min=False, tamper=None):
    monkeypatch.setattr(geometry_fixture, "SOURCE_HASH", SOURCE_HASH)
    block, _, _ = geometry_fixture.extract_fixture(missing_min=missing_min)
    block["metadata"]["extraction_method"] = "native"
    if tamper:
        tamper(block)
    # extract_fixture observes a 500x400 page; the registered authority must
    # describe that same explicit fixture, independently of its witness fields.
    db, snapshot, sources = index_blocks(storage, [block], page_width=500)
    sources = [table_bundle(db, snapshot, source, question="typical voltage at 10 °C" if missing_min else "pressure range")[0]
               for source in sources]
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(sources, 1)]
    question = "What is the typical voltage at 10 °C?" if missing_min else "What is the pressure range?"
    return StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(sources, "question")


def test_table_binding_is_replayed_from_db_before_claims(storage, monkeypatch):
    cat = table_catalogue(storage, monkeypatch)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered", result["answer_contract"]
    assert "1.8" in result["text"] and "2.9" in result["text"]
    assert all(item["table_quality"]["state"] == "supported" for item in cat.references if item.get("table_context"))


def test_blank_minimum_does_not_acquire_typical_value_in_final_answer(storage, monkeypatch):
    cat = table_catalogue(storage, monkeypatch, missing_min=True)
    result = render(cat, [item["id"] for item in cat.references])
    assert "Min = 1.25" not in result["text"] and "Min = C" not in result["text"]
    assert "Typ = 1.25" in result["text"]


@pytest.mark.parametrize("mutation", ["missing", "source", "observation", "binding"])
def test_unverified_geometry_never_reaches_public_role_labels(storage, monkeypatch, mutation):
    def tamper(block):
        quality = block["metadata"]["table_quality"]
        if mutation == "missing":
            del block["metadata"]["table_quality"]
        elif mutation == "source":
            quality["source_sha256"] = "0" * 64
        elif mutation == "observation":
            quality["native_glyphs"]["glyphs"][-1]["text"] = "Z"
        else:
            quality["bindings"][-1]["column"] = 0
    cat = table_catalogue(storage, monkeypatch, tamper=tamper)
    result = render(cat, [item["id"] for item in cat.references])
    assert result["answer_contract"]["status"] != "covered"
    assert "Liaisons aux en-têtes" not in result["text"]
    assert "1.8" not in result["text"]


def ocr_block(*, legacy=False, differing_tail=False):
    first = "DEV728 supply voltage: 2.1 V to 4.6 V."
    tail = "Power dissipation is 170 HW." if differing_tail else "The source is readable."
    text = first + " " + tail
    records, cells = [], []
    for index, literal in enumerate([first, tail]):
        record = reading(text=literal, candidate="Power dissipation is 170 µW." if index and differing_tail else literal)
        record["reading_id"] = f"real-double-{index}"
        for value in record["baseline_tokens"] + record["candidate_tokens"]:
            value["bbox"] = [10, 10 + index * 30, 300, 25 + index * 30]
        records.append(record)
        cells.append({**token(literal, (10, 10 + index * 30, 300, 25 + index * 30)), "from_ocr": True})
    metadata = {"extraction_method": "ocr", "ocr_used": True}
    if not legacy:
        annotated = annotate_ocr_cells(cells, records)
        metadata["ocr_quality"] = block_quality(text, annotated, records, SOURCE_HASH, 0)
    return {"id": "ocr-body", "type": "text", "text": text, "bbox": [10, 10, 300, 55], "precision": "block", "metadata": metadata}


def test_uncorroborated_unasked_ocr_tail_is_not_published(storage):
    db, snapshot, sources = index_blocks(storage, [ocr_block(differing_tail=True)])
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(sources, 1)]
    cat = StructuredAnswerBuilder(db, snapshot, "What is DEV728 supply voltage range?", enforce_contract=True).catalogue(sources, "question")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert "2.1 V to 4.6 V" in result["text"]
    assert "170 HW" not in result["text"] and "170 µW" not in result["text"]


def test_legacy_ocr_cannot_be_authorized_by_a_forged_retrieval_flag(storage):
    db, snapshot, sources = index_blocks(storage, [ocr_block(legacy=True)])
    for index, source in enumerate(sources, 1):
        source["source_id"] = f"S{index:03d}"
        for block in source["blocks"]:
            block["source_quality"] = {"state": "corroborated", "verified": True}
    cat = StructuredAnswerBuilder(db, snapshot, "What is DEV728 supply voltage range?", enforce_contract=True).catalogue(sources, "question")
    result = render(cat, [item["id"] for item in cat.references])
    assert result["answer_contract"]["status"] != "covered"
    assert "2.1 V" not in result["text"]


def test_subline_dependency_is_source_bound_and_both_conditions_survive(storage, monkeypatch):
    monkeypatch.setattr(geometry_fixture, "SOURCE_HASH", SOURCE_HASH)
    data, quality, original = geometry_fixture.subline_fixture()
    block = {"id": "subline-table", "type": "table", "text": table_text(data), "bbox": [10, 300, 500, 380], "precision": "table",
             "metadata": {"extraction_method": "native", "table_data": data, "parser_table_data": original, "table_quality": quality}}
    db, snapshot, sources = index_blocks(storage, [block])
    question = "What are the typical delays for drives of 7 mV and 14 mV?"
    sources = [table_bundle(db, snapshot, source, question=question)[0] for source in sources]
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(sources, 1)]
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(sources, "question")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered", result["answer_contract"]
    facts = result["answer_contract"]["matched_relations"]
    assert {tuple(fact["values"]) for fact in facts} == {("75",), ("55",)}
    assert all("Load = 20pF" in fact["condition"] for fact in facts)
    assert "Drive=7mV" in result["text"] and "Drive=14mV" in result["text"]
    assert result["support_validation"]["status"] == "passed"


def test_unverified_shared_condition_blocks_otherwise_readable_second_subline(storage, monkeypatch):
    monkeypatch.setattr(geometry_fixture, "SOURCE_HASH", SOURCE_HASH)
    _, quality, original = geometry_fixture.subline_fixture()
    native = copy.deepcopy(quality["native_glyphs"])
    common_observations = set(quality["dependencies"][0]["observation_ids"])
    common_glyphs = {glyph_id for observation in quality["observations"] if observation["id"] in common_observations
                    for glyph_id in observation.get("glyph_ids", [])}
    affected = next(glyph for glyph in native["glyphs"] if glyph["text"] == "p" and glyph["id"] in common_glyphs)
    affected["unicode_map_error"] = 1
    data, replayable = build_table_quality(original, quality["table_bbox"], quality["parser_size"],
                                          quality["page_frame"], native=native, source_sha256=SOURCE_HASH)
    block = {"id": "subline-table", "type": "table", "text": table_text(data), "bbox": quality["table_bbox"],
             "precision": "table", "metadata": {"extraction_method": "native", "table_data": data,
             "parser_table_data": original, "table_quality": replayable}}
    db, snapshot, sources = index_blocks(storage, [block])
    question = "What is the typical delay for Drive = 14 mV?"
    sources = [table_bundle(db, snapshot, source, question=question)[0] for source in sources]
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(sources, 1)]
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(sources, "question")
    result = render(cat, [reference["id"] for reference in cat.references])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "55" not in result["text"]
    assert "55" in " ".join(reference["text"] for reference in cat.references)
