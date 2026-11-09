"""A replayed ruled header must reach Min/Max even when Typ is empty.

Glyphs and painted paths are declared synthetic observations. The geometry
builder, SQLite catalogue, source scope and final publication are real.
"""

import asyncio
import copy

from i5_rule_fixtures import grouped_header_fixture
from test_api_storage import storage as storage
from test_enhanced_answers import render
from test_retrieval import library_search

from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.docling_adapter import table_text
from services.ingestion.table_geometry import build_table_quality


def ruled_catalogue(storage, question, *, filename="observations.pdf", omit_rules=False, forge_span=False):
    fixture = grouped_header_fixture()
    native = copy.deepcopy(fixture["native"])
    if omit_rules:
        native.pop("rules")
    data, quality = build_table_quality(fixture["data"], fixture["bbox"], fixture["parser_size"], fixture["page"],
                                       native=native, source_sha256=fixture["page"]["source_sha256"])
    if forge_span:
        parent = next(item for item in quality["bindings"] if item.get("header_group"))
        parent["column_end"] = 5  # forged scope includes the Units column
    literal = table_text(data)
    block = {"id": "ruled-table", "type": "table", "text": literal, "bbox": fixture["bbox"], "precision": "table",
             "metadata": {"extraction_method": "native", "ocr_used": False,
                          "table_data": data, "parser_table_data": fixture["data"], "table_quality": quality}}
    settings, db, _, indexer = storage
    source_sha = fixture["page"]["source_sha256"]
    path = settings.data_dir / "originals" / (source_sha + ".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fixture["payload"])
    imported = db.import_original(filename, source_sha, path)
    extraction = {"sha256": source_sha, "fingerprint": "i5-synthetic-ruled-header-v1", "status": "ready", "page_count": 1,
                  "pages": [{**fixture["page"], "blocks": [block]}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    search, snapshot, _ = library_search(storage)
    sources = [search.resolver.source_for_chunk(dict(row), snapshot) for row in db.rows("SELECT * FROM chunks ORDER BY id")]
    sources = [table_bundle(db, snapshot, source, question=question)[0] for source in sources]
    sources = [{**source, "source_id": f"S{index:03d}"} for index, source in enumerate(sources, 1)]
    cat = StructuredAnswerBuilder(db, snapshot, question, enforce_contract=True).catalogue(sources, "question")
    return cat, literal


def test_empty_typical_cell_does_not_erase_the_subject_of_minimum_and_maximum(storage):
    cat, literal = ruled_catalogue(storage, "What is MODEL-Z7 temperature range?")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    facts = result["answer_contract"]["matched_relations"]
    assert len(facts) == 1 and facts[0]["values"] == ["3", "9"]
    assert facts[0]["subjects"] == ["MODEL-Z7"]
    assert facts[0]["entity_context_identifiers"] == ["model-z7"]
    data_row = next(item for item in cat.references if item.get("table_context", {}).get("row_role") == "data")
    for cell in data_row["table_context"]["cells"]:
        ancestors = [item for item in cell["headers"] if item["text"] == "MODEL-Z7"]
        assert bool(ancestors) is (cell["text"] in {"3", "9"})
    parent = next(item for item in data_row["table_context"]["binding_quality"]["bindings"] if item.get("header_group"))
    assert (parent["column"], parent["column_end"]) == (1, 4)
    assert parent.get("scope_bbox")
    assert "Min = 3" in result["text"] and "Max = 9" in result["text"]
    assert "Typ = 3" not in result["text"] and "Typ = 9" not in result["text"]
    references = {item["id"]: item for item in cat.references}
    for reference_id in facts[0]["reference_ids"]:
        reference = references[reference_id]
        assert reference["version_id"] and reference["extraction_revision_id"]
        for segment in reference["segments"]:
            assert literal[segment["start_offset"]:segment["end_offset"]] == reference["text"]
    assert result["citation_spans"] and cat.verify_rendered(result)["status"] == "passed"


def test_a_different_explicit_header_subject_overrides_a_matching_filename(storage):
    cat, _ = ruled_catalogue(storage, "What is OTHER-Q8 temperature range?", filename="OTHER-Q8.pdf")
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert all("OTHER-Q8" not in item["subjects"] for item in result["answer_contract"]["matched_relations"])
    assert "Min = 3" not in result["text"] and "Max = 9" not in result["text"]


def test_centered_subject_text_without_rules_cannot_acquire_a_wider_scope(storage):
    cat, _ = ruled_catalogue(storage, "What is MODEL-Z7 temperature range?", omit_rules=True)
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert "Min = 3" not in result["text"] and "Max = 9" not in result["text"]


def test_forged_parent_span_in_database_cannot_replace_the_observed_rules(storage):
    cat, _ = ruled_catalogue(storage, "What is MODEL-Z7 temperature range?", forge_span=True)
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_relations"]
    assert "Liaisons aux en-têtes" not in result["text"]
