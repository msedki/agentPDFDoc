"""Bounded literal scope after the first I5 development run.

Invented language/table examples; the public I4/native results are not altered.
The tokenizer and glyphs are explicit unit doubles, not a native qualification.
"""

import copy

import pytest
from test_api_storage import storage as storage
from test_enhanced_answers import catalogue, render
from test_i5_obligation_publication import source
from test_iteration2_answer_contract import table_catalogue
from test_iteration2_table_evidence import HEADERS

from services.api.answer_contract import AnswerContract
from services.api.errors import ApiError
from services.api.structured_answer import digest

REMOVED_NEED_QUESTION = "Selon DEV728, quels circuits externes ne sont plus nécessaires ?"


@pytest.mark.parametrize("text", [
    "DEV728 eliminates the need for any adjustment, isolation or amplification circuitry.",
    "DEV728 eliminates the need for all adjustment and isolation circuits.",
    "DEV728 supprime le besoin de tout circuit de réglage.",
    "DEV728 supprime le besoin de tous les circuits de réglage et de compensation.",
])
def test_direct_universal_circuit_scope_covers_a_subset_without_adding_external(text):
    cat = catalogue(REMOVED_NEED_QUESTION, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert cat.deterministic_plan().references == ["R001"]
    assert text in result["text"]
    assert "external" not in result["text"] and "externe" not in result["text"]
    assert result["source_ids"] == ["S001"]
    assert result["citation_spans"]
    assert cat.verify_rendered(result)["status"] == "passed"


def test_universal_removed_need_preserves_explicit_condition_and_following_exception():
    text = ("DEV728 eliminates the need for any adjustment circuitry only when the regulated input is stable. "
            "This applies except during startup.")
    cat = catalogue(REMOVED_NEED_QUESTION, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert text in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("condition", [
    "only when two sensors agree", "provided that four indicators are visible",
])
def test_a_cardinality_in_the_preserved_condition_is_not_a_circuit_subset(condition):
    text = f"DEV728 eliminates the need for any adjustment circuitry {condition}."
    cat = catalogue(REMOVED_NEED_QUESTION, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert text in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("text", [
    "DEV728 eliminates the need for some adjustment circuitry.",
    "DEV728 eliminates the need for adjustment circuitry.",
    "DEV728 eliminates the need for any of the adjustment circuits.",
    "DEV728 eliminates the need for any two adjustment circuits.",
    "DEV728 eliminates the need for any four adjustment circuits.",
    "DEV728 eliminates the need for any twenty adjustment circuits.",
    "DEV728 eliminates the need for any dozen adjustment circuits.",
    "DEV728 eliminates the need for any pair of adjustment circuits.",
    "DEV728 eliminates the need for all selected adjustment circuits.",
    "DEV728 eliminates the need for all our adjustment circuits.",
    "DEV728 eliminates the need for all adjustment circuits in the selected set.",
    "Any installation has a controller. DEV728 eliminates the need for adjustment circuitry.",
    "DEV728 eliminates the need for any controller, but requires adjustment circuitry.",
    "DEV728 eliminates the need for any internal adjustment circuitry.",
    "DEV728 eliminates the need for all on-chip adjustment circuits.",
    "DEV728 eliminates the need for all on‑chip adjustment circuits.",
    "DEV728 eliminates the need for any adjustment circuitry for internal use.",
    "DEV728 supprime le besoin de tous les circuits internes de réglage.",
    "DEV728 supprime le besoin de tout circuit de réglage interne.",
    "DEV728 supprime le besoin de tous les deux circuits de réglage.",
    "DEV728 supprime le besoin de tous les circuits de quelques catégories.",
    "DEV728 does not eliminate the need for any adjustment circuitry.",
    "DEV728 may eliminate the need for any adjustment circuitry.",
    "ALT421 eliminates the need for any adjustment circuitry.",
])
def test_partial_internal_unrelated_uncertain_or_negated_scope_cannot_cover_external(text):
    cat = catalogue(REMOVED_NEED_QUESTION, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_qualitative_relations"]


@pytest.mark.parametrize(("question", "guaranteed", "ordinary"), [
    ("What is DEV728 guaranteed temperature range?",
     "DEV728 guaranteed temperature range: -10 °C to 70 °C.",
     "DEV728 operating temperature range: -25 °C to 95 °C."),
    ("Quelle est la plage de température garantie du DEV728 ?",
     "DEV728 : plage de température garantie de -10 °C à 70 °C.",
     "DEV728 : plage de température de fonctionnement de -25 °C à 95 °C."),
])
def test_guaranteed_range_requires_its_own_qualification_without_inventing_an_operating_role(question, guaranteed, ordinary):
    cat = catalogue(question, [source("R001", ordinary), source("R002", guaranteed)])
    assert cat.contract.requested_role is None and cat.contract.guarantee_required
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["effective_plan"]["references"] == ["R002"]
    assert guaranteed in result["text"] and ordinary not in result["text"]
    assert all(item["guarantee_required"] and item["role"] is None for item in result["answer_contract"]["obligations"])
    assert all(item["guarantee"] == "explicit" and item["role"] is None for item in result["answer_contract"]["matched_relations"])
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("qualification", ["operating", "typical", "", "not guaranteed", "possibly guaranteed"])
def test_other_or_uncertain_range_cannot_establish_a_guarantee(qualification):
    text = f"DEV728 {qualification} temperature range: -25 °C to 95 °C."
    result = render(catalogue("What is DEV728 guaranteed temperature range?", [source("R001", text)]))
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])


def test_composite_request_keeps_operating_voltage_separate_from_guaranteed_temperature():
    cat = catalogue("Quelles sont la plage de tension de fonctionnement et la plage de température garantie du DEV728 ?", [
        source("R001", "DEV728 operating voltage range: 1.9 V to 4.7 V."),
        source("R002", "DEV728 guaranteed temperature range: -10 °C to 70 °C."),
        source("R003", "DEV728 operating temperature range: -25 °C to 95 °C."),
    ])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert {(item["quantity"], item["role"], item["guarantee_required"])
            for item in result["answer_contract"]["obligations"]} == {
        ("voltage", "operating", False), ("temperature", None, True)}
    assert "95 °C" not in result["text"]


def test_verified_table_keeps_guaranteed_and_operating_ranges_distinct(storage):
    cat = table_catalogue(storage, [HEADERS,
        [(1, "DEV728 guaranteed temperature range"), (3, "-10"), (5, "70"), (6, "°C")],
        [(1, "DEV728 operating temperature range"), (3, "-25"), (5, "95"), (6, "°C")],
    ], "What is DEV728 guaranteed temperature range?")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    facts = result["answer_contract"]["matched_relations"]
    assert len(facts) == 1 and facts[0]["role"] is None and facts[0]["guarantee"] == "explicit"
    assert facts[0]["values"] == ["-10", "70"] and facts[0]["table_bound"]
    assert "95" not in result["text"]
    assert result["citation_spans"] and cat.verify_rendered(result)["status"] == "passed"
    altered = copy.deepcopy(result)
    altered["answer_contract"]["matched_relations"][0]["guarantee"] = None
    altered["support_ledger_sha256"] = digest(altered["support_ledger"])
    with pytest.raises(ApiError, match="preuves vérifiées"):
        cat.verify_rendered(altered)


def test_guarantee_verb_in_absolute_limit_question_is_not_a_guaranteed_quantity_role():
    contract = AnswerContract("La limite absolue d'alimentation garantit-elle le fonctionnement normal ?", "question")
    assert contract.operating_guarantee_requested is True
    assert contract.guarantee_required is False


@pytest.mark.parametrize(("question", "required"), [
    ("What is DEV728 operating temperature range?", False),
    ("What is DEV728 guaranteed operating temperature range?", True),
    ("Quelle est la plage de température de fonctionnement du DEV728 ?", False),
    ("Quelle est la plage de température de fonctionnement garantie du DEV728 ?", True),
])
def test_guarantee_qualifies_the_same_operating_relation_without_a_second_requirement(question, required):
    text = "DEV728 guaranteed operating temperature range: -10 °C to 70 °C, only when the regulated supply is stable."
    cat = catalogue(question, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    obligations = result["answer_contract"]["obligations"]
    assert len(obligations) == 1 and obligations[0]["role"] == "operating"
    assert obligations[0]["guarantee_required"] is required
    facts = result["answer_contract"]["matched_relations"]
    assert len(facts) == 1 and facts[0]["role"] == "operating" and facts[0]["guarantee"] == "explicit"
    assert text in result["text"]
    assert cat.deterministic_plan().references == ["R001"]


def test_a_guarantee_without_an_operating_role_does_not_supply_that_missing_role():
    cat = catalogue("What is DEV728 guaranteed operating temperature range?", [source("R001",
        "DEV728 guaranteed temperature range: -10 °C to 70 °C.")])
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])


@pytest.mark.parametrize(("temperature", "covered"), [(25, True), (85, False)])
def test_a_guaranteed_relation_retains_its_measured_condition(temperature, covered):
    text = "DEV728 guaranteed operating voltage range: 1.9 V to 4.7 V at 25 °C."
    cat = catalogue(f"What is DEV728 guaranteed operating voltage range at {temperature} °C?", [source("R001", text)])
    result = render(cat)
    assert (result["answer_contract"]["status"] == "covered") is covered
    assert all(item["covered"] is covered for item in result["answer_contract"]["obligations"])
    if covered:
        assert text in result["text"]
        assert result["answer_contract"]["matched_relations"][0]["guarantee"] == "explicit"


@pytest.mark.parametrize("text", [
    "DEV728 guaranteed voltage range: 1.9 V to 4.7 V; operating temperature range: -10 °C to 70 °C.",
    "DEV728 operating temperature range: -10 °C to 70 °C under the guaranteed supply voltage range.",
])
def test_a_guarantee_of_another_quantity_does_not_transfer_to_temperature(text):
    result = render(catalogue("What is DEV728 guaranteed operating temperature range?", [source("R001", text)]))
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])


def test_post_render_change_of_guarantee_requirement_is_rejected():
    cat = catalogue("What is DEV728 guaranteed operating temperature range?", [source("R001",
        "DEV728 guaranteed operating temperature range: -10 °C to 70 °C.")])
    result = render(cat)
    result["answer_contract"]["obligations"][0]["guarantee_required"] = False
    result["support_ledger_sha256"] = digest(result["support_ledger"])
    with pytest.raises(ApiError, match="preuves vérifiées"):
        cat.verify_rendered(result)


def test_a_guarantee_is_part_of_comparison_context_even_when_operating_roles_match():
    refs = [{**source("R001", "DEV728 operating supply voltage range: 1.9 V to 4.7 V."), "document_id": "a"},
            {**source("R002", "DEV728 guaranteed operating supply voltage range: 1.9 V to 4.7 V."), "document_id": "b"}]
    cat = catalogue("Compare DEV728 operating supply voltage ranges.", refs, mode="comparison")
    result = render(cat, required_documents=["a", "b"])
    comparison = result["answer_contract"]["comparisons"][0]
    assert comparison["status"] == "context_differs"
    assert comparison["numeric_agreement"] == "equal"
    assert "les valeurs citées concordent" not in result["text"]


def test_conflicting_guaranteed_ranges_are_not_silently_chosen_when_operating_role_is_unknown():
    refs = [{**source("R001", "DEV728 guaranteed temperature range: -10 °C to 70 °C."), "document_id": "a"},
            {**source("R002", "DEV728 guaranteed temperature range: -10 °C to 80 °C."), "document_id": "b"}]
    cat = catalogue("What is DEV728 guaranteed temperature range?", refs)
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "conflict"
    assert result["effective_plan"]["references"] == ["R001", "R002"]
    assert "70 °C" in result["text"] and "80 °C" in result["text"]
    assert all(item["role"] is None and item["guarantee"] == "explicit"
               for item in result["answer_contract"]["matched_relations"])
