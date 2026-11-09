"""Source-bound general conditions through SQLite, projection and publication.

All glyphs/text are explicit synthetic observations, without native/OCR claims.
"""

import json

from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import render

from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder

ROWS = [[(0, "Parameter"), (1, "Min"), (2, "Typ"), (3, "Max"), (4, "Units")],
        [(0, "Pressure"), (1, "1.8"), (2, "2.2"), (3, "2.9"), (4, "bar")]]
CONDITIONS = "TA = 18°C, supply = 4V unless otherwise noted."
QUESTION = "What is the pressure range with its general conditions?"


def condition_catalogue(storage, *, unknown_reading=False, bundle_budget=8192):
    search, snapshot, source, _ = witnessed_sparse_table(storage, ROWS, general_conditions=CONDITIONS)
    if unknown_reading:
        row = search.db.one("SELECT metadata_json FROM blocks WHERE id='general-conditions'")
        metadata = json.loads(row["metadata_json"])
        metadata["metadata"]["extraction_method"] = "unknown"
        search.db.execute("UPDATE blocks SET metadata_json=? WHERE id='general-conditions'", (json.dumps(metadata),))
    source["source_id"] = "S001"
    bundle, warnings = table_bundle(search.db, snapshot, source, question=QUESTION, maximum_chars=bundle_budget)
    cat = StructuredAnswerBuilder(search.db, snapshot, QUESTION, enforce_contract=True).catalogue([bundle], "question")
    return cat, warnings


def test_verified_general_conditions_are_required_dependencies_of_published_values(storage):
    cat, warnings = condition_catalogue(storage)
    result = render(cat)
    assessment = result["answer_contract"]
    assert not warnings and assessment["status"] == "covered", assessment
    assert "1.8" in result["text"] and "2.9" in result["text"] and CONDITIONS in result["text"]
    fact = assessment["matched_relations"][0]
    assert fact["general_conditions_verified"] and fact["general_condition"]
    assert assessment["obligations"][0]["general_conditions_required"]
    assert set(fact["reference_ids"]) <= set(assessment["rendered_reference_ids"])
    assert "unless otherwise noted" in cat.prompt()
    assert result["support_validation"]["status"] == "passed"


def test_geometric_condition_binding_cannot_authorize_unknown_source_reading(storage):
    cat, _ = condition_catalogue(storage, unknown_reading=True)
    result = render(cat, [reference["id"] for reference in cat.references])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert "1.8" not in result["text"] and CONDITIONS not in result["text"]
    assert any(item["text"] == CONDITIONS for item in cat.references)


def test_condition_bundle_budget_never_silently_publishes_an_unqualified_value(storage):
    cat, warnings = condition_catalogue(storage, bundle_budget=90)
    result = render(cat, [reference["id"] for reference in cat.references])
    assert any(item["code"] == "table_general_conditions_unavailable" for item in warnings)
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "1.8" not in result["text"] and CONDITIONS not in result["text"]


def test_narrow_ancestor_condition_does_not_apply_to_values_outside_its_geometry(storage):
    def header_rows(block):
        for cell in block["metadata"]["table_data"]["table_cells"]:
            if cell["start_row_offset_idx"] == 1:
                cell["column_header"] = True

    rows = [[(0, "TA = 18 °C")], ROWS[0], ROWS[1]]
    search, snapshot, source, _ = witnessed_sparse_table(storage, rows, target=2, mutate=header_rows)
    source["source_id"] = "S001"
    question = "What is the pressure range at TA = 18 °C?"
    bundle, _ = table_bundle(search.db, snapshot, source, question=question)
    cat = StructuredAnswerBuilder(search.db, snapshot, question, enforce_contract=True).catalogue([bundle], "question")
    result = render(cat, [reference["id"] for reference in cat.references])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "1.8" not in result["text"]
    assert any("table_ancestor_condition_scope_unverified" in item["reasons"]
               for item in result["answer_contract"]["rejected_relations"])
