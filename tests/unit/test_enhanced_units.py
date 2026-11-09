"""Explicit separate-unit bindings; no model or OCR is simulated as native evidence."""

import copy

import pytest
from test_enhanced_answers import catalogue, cell, render

from services.api.deterministic_calculations import CalculationRefusal, calculate, calculation_text


@pytest.mark.parametrize("unit", ["µs", "μs", "us"])
def test_microseconds_are_converted_exactly_with_source_provenance(unit):
    result = calculate("convert", [cell("R001", "B2", "140 " + unit, kind="string")], "ms")
    assert result["value"] == "0.14" and result["unit"] == "ms"
    assert result["inputs"][0]["raw_text"] == "140 " + unit
    assert result["rounded"] is False and result["formula_evaluated"] is False


def values():
    return [cell("R001", "D8", 140), cell("R002", "E8", "µs", kind="string")]


def test_question_explicitly_binds_authorized_unit_cell_and_cites_both_inputs():
    references = values()
    before = copy.deepcopy(references)
    cat = catalogue("Convertis en ms la valeur de D8, en utilisant l’unité portée par E8 ; citer les cellules et le calcul.",
                    references, scope={"kind": "cell_range"})
    result = cat.contract.calculation(references)
    assert result["value"] == "0.14" and result["unit"] == "ms"
    assert result["unit_reference"]["reference_id"] == "R002"
    assert result["source_ids"] == ["S001", "S002"]
    assert "unité source E8 = µs" in calculation_text(result)
    assert references == before
    rendered = render(cat, ["R001"], output_tokens=768)
    assert rendered["answer_contract"]["status"] == "covered"
    assert rendered["answer_contract"]["rendered_reference_ids"] == ["R001", "R002"]
    assert rendered["source_ids"] == ["S001", "S002"]


def test_unrequested_neighbor_unit_is_never_used_even_when_present_in_catalogue():
    references = values()
    cat = catalogue("Convertis la cellule D8 en ms.", references, scope={"kind": "cell_range"})
    with pytest.raises(CalculationRefusal) as failure:
        cat.contract.calculation(references)
    assert failure.value.code == "unit_missing"


def test_requested_unit_outside_scope_is_not_invented():
    references = values()[:1]
    cat = catalogue("Convertis D8 en ms avec l’unité de E8.", references, scope={"kind": "cell_range"})
    with pytest.raises(CalculationRefusal) as failure:
        cat.contract.calculation(references)
    assert failure.value.code == "operand_missing_or_ambiguous"


@pytest.mark.parametrize("change,code", [
    ("document", "unit_cell_scope_mismatch"),
    ("revision", "unit_cell_scope_mismatch"),
    ("sheet", "unit_cell_scope_mismatch"),
    ("partial", "incomplete_unit"),
    ("unknown", "unit_not_supported"),
    ("formula_without_cache", "formula_cache_absent"),
])
def test_unit_binding_refuses_incomplete_or_unrelated_evidence(change, code):
    operand, unit = values()
    if change == "document":
        unit["document_id"] = "another-document"
    elif change == "revision":
        unit["extraction_revision_id"] = "another-revision"
    elif change == "sheet":
        unit["locator"]["unit_id"] = "another-sheet"
    elif change == "partial":
        unit["fields"][0]["complete"] = False
    elif change == "unknown":
        unit["fields"][0]["text"] = "µs or ms"
    else:
        unit["cell_facts"].update(formula_present=True, cached_present=False)
    with pytest.raises(CalculationRefusal) as failure:
        calculate("convert", [operand], "ms", unit_reference=unit)
    assert failure.value.code == code


def test_two_source_units_in_disagreement_are_a_refusal():
    operand, unit = values()
    operand["fields"][0]["text"] = "140 ms"
    with pytest.raises(CalculationRefusal) as failure:
        calculate("convert", [operand], "ms", unit_reference=unit)
    assert failure.value.code == "conflicting_source_units"
