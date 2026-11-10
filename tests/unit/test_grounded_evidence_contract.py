"""Literal evidence controls; no model, OCR or semantic judge is substituted.

The positive controls prevent lower error counts from being obtained merely by
rejecting every quantity. Integrity tests mutate the rendered boundary after a
valid source selection, which the publication gate must reject.
"""

import copy
import hashlib
import json

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_enhanced_answers import catalogue, cell, excerpt, render, requirement_codes
from test_retrieval import CharTokenizer, library_search

from services.api.answer_contract import AnswerContract
from services.api.errors import ApiError
from services.api.structured_answer import StructuredAnswerBuilder, digest


@pytest.mark.parametrize(("question", "source", "expected"), [
    ("Quelle est la tension nominale d'alimentation à 85 °C ?", "Nominal supply voltage: 3.3 V at 25 °C.", "partial"),
    ("Quelle est la tension nominale d'alimentation à 25 °C ?", "Nominal supply voltage: 3.3 V at 25 °C.", "covered"),
    ("Quel courant de sortie est établi à TA = 85 °C ?", "Output current: 10 mA at TA = 25 °C.", "partial"),
    ("Quel courant de sortie est établi à TA = 25 °C ?", "Output current: 10 mA at TA = 25 °C.", "covered"),
    ("Quelle est la tension nominale d'alimentation à 25 °C ?", "At 25 °C, nominal supply voltage: 3.3 V.", "covered"),
    ("Quelle est la tension nominale d'alimentation à 25 °C ?", "Nominal supply voltage: 3.3 V at 298.15 K.", "covered"),
    ("Quelle est la tension nominale d'alimentation à TJ = 25 °C ?", "Nominal supply voltage: 3.3 V at TA = 25 °C.", "partial"),
])
def test_explicit_conditions_are_matched_without_silent_transposition(question, source, expected):
    cat = catalogue(question, [excerpt("R001", source)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == expected
    assert source in result["text"]
    if expected == "partial":
        assert "requested_condition_not_established" in requirement_codes(result["answer_contract"])
        assert cat.deterministic_plan() is None
    else:
        assert cat.deterministic_plan().references == ["R001"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("question", [
    "Donne les deux plages d'alimentation recommandées avec leurs conditions de température.",
    "Donne les deux plages d’alimentation du TMP117 avec leurs conditions de température.",
    "Give the two recommended supply ranges with their temperature conditions.",
])
def test_supply_ranges_keep_each_explicit_temperature_condition(question):
    sources = ["Recommended supply voltage: 1.5 to 4.5 V for TA = -40 to 125 °C.",
               "Recommended supply voltage: 1.8 to 4.5 V for TA = -55 to 150 °C."]
    # The named component is a question constraint, so its name must also be in
    # the literal supporting passages for that parametrized question.
    if "TMP117" in question:
        sources = ["TMP117 " + source for source in sources]
    cat = catalogue(question, [excerpt(f"R{index:03d}", source) for index, source in enumerate(sources, 1)])
    rendered = render(cat)
    assessment = rendered["answer_contract"]
    assert assessment["quantity"] == "voltage" and assessment["status"] == "covered"
    assert {(tuple(fact["values"]), fact["unit"], fact["condition"]) for fact in assessment["matched_relations"]} == {
        (("1.5", "4.5"), "V", "for TA = -40 to 125 °C."),
        (("1.8", "4.5"), "V", "for TA = -55 to 150 °C."),
    }
    assert all(source in rendered["text"] for source in sources)
    assert cat.deterministic_plan().references == ["R001", "R002"]
    assert rendered["support_validation"]["status"] == "passed"


def test_supply_range_condition_grammar_does_not_invent_a_missing_second_relation():
    cat = catalogue("Donne les deux plages d'alimentation recommandées avec leurs conditions de température.",
                    [excerpt("R001", "Recommended supply voltage: 1.5 to 4.5 V for TA = -40 to 125 °C.")])
    assessment = render(cat)["answer_contract"]
    assert assessment["quantity"] == "voltage" and assessment["status"] == "partial"
    assert assessment["obligations"][0]["expected_count"] == 2
    assert assessment["obligations"][0]["matched_count"] == 1
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("suffix", ["", " See section 5.", " for P = 5 Pa.", " at room temperature."])
def test_requested_temperature_condition_is_not_inferred_from_a_missing_or_unrecognized_condition(suffix):
    source = "Recommended supply voltage: 1.5 to 4.5 V." + suffix
    cat = catalogue("Donne la plage d'alimentation recommandée avec ses conditions de température.",
                    [excerpt("R001", source)])
    rendered = render(cat, ["R001"])
    assert rendered["answer_contract"]["status"] == "partial"
    assert "requested_temperature_condition_not_established" in requirement_codes(rendered["answer_contract"])
    assert "conditions de température" in rendered["text"]
    assert source in rendered["text"]
    assert cat.deterministic_plan() is None


def test_each_requested_range_needs_its_own_temperature_condition():
    sources = ["Recommended supply voltage: 1.5 to 4.5 V for TA = -40 to 125 °C.",
               "Recommended supply voltage: 1.8 to 4.5 V."]
    cat = catalogue("Donne les deux plages d'alimentation recommandées avec leurs conditions de température.",
                    [excerpt(f"R{index:03d}", source) for index, source in enumerate(sources, 1)])
    rendered = render(cat, ["R001", "R002"])
    assessment = rendered["answer_contract"]
    assert assessment["status"] == "partial"
    assert assessment["obligations"][0]["matched_count"] == 1
    assert assessment["rejected_relations"][0]["condition"] == ""
    assert "requested_temperature_condition_not_established" in assessment["rejected_relations"][0]["reasons"]
    assert all(source in rendered["text"] for source in sources)
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize(("source", "condition"), [
    ("Recommended supply voltage: 1.5 to 4.5 V at TA = 25 °C.", "at TA = 25 °C."),
    ("Recommended supply voltage: 1.5 to 4.5 V for TA = 25 °C.", "for TA = 25 °C."),
    ("At TA = 25 °C, recommended supply voltage: 1.5 to 4.5 V.", "At TA = 25 °C"),
    ("At 25 °C, recommended supply voltage: 1.5 to 4.5 V.", "At 25 °C"),
])
def test_explicit_point_temperature_condition_remains_sufficient_and_literal(source, condition):
    cat = catalogue("Donne la plage d'alimentation recommandée avec ses conditions de température.",
                    [excerpt("R001", source)])
    rendered = render(cat)
    assert rendered["answer_contract"]["status"] == "covered"
    assert rendered["answer_contract"]["matched_relations"][0]["condition"] == condition
    assert source in rendered["text"]
    assert cat.deterministic_plan().references == ["R001"]


@pytest.mark.parametrize("source", [
    "Recommended supply voltage: 1.5 to 4.5 V; storage temperature: -40 to 125 °C.",
    "Recommended supply voltage: 1.5 to 4.5 V; junction temperature: -40 to 125 °C.",
    "Recommended supply voltage: 1.5 to 4.5 V; junction temperature is measured at TA = 25 °C.",
    "Recommended supply voltage: 1.5 to 4.5 V; storage temperature: -40 to 125 °C for TA = 25 °C.",
    "Junction temperature is measured at TA = 25 °C; recommended supply voltage: 1.5 to 4.5 V.",
])
def test_an_independent_temperature_assertion_cannot_qualify_a_supply_range(source):
    cat = catalogue("Donne la plage d'alimentation recommandée avec ses conditions de température.",
                    [excerpt("R001", source)])
    rendered = render(cat, ["R001"])
    assessment = rendered["answer_contract"]
    assert assessment["status"] == "partial"
    assert "requested_temperature_condition_not_established" in requirement_codes(assessment)
    assert not assessment["matched_relations"]
    assert "recommended supply voltage: 1.5 to 4.5 v" in rendered["text"].lower()
    assert cat.support_ledger()["references"][0]["literal"]["text"] == source
    assert all("requested_temperature_condition_not_established" in item["reasons"]
               for item in assessment["rejected_relations"])
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("question", [
    "Quelle est la température d'alimentation ?",
    "Quelle température ambiante est indiquée pour l'alimentation ?",
    "Quelles conditions de température s'appliquent à la plage d'alimentation ?",
    "What is the operating temperature of the power supply?",
])
def test_temperature_as_the_question_object_is_not_replaced_by_supply_voltage(question):
    contract = AnswerContract(question, "question")
    assert contract.quantity == "temperature"
    assert not contract.parse_failures


@pytest.mark.parametrize(("question", "decomposed"), [
    ("Donne les plages de tension d'alimentation et de température avec leurs conditions.", True),
    ("Donne la tension d'alimentation et la température ambiante dans les conditions recommandées.", True),
    ("Donne les deux plages d'alimentation avec leurs conditions de température et la température de stockage.", False),
    ("Give the supply voltage and temperature with their operating conditions.", True),
])
def test_independent_temperature_requests_have_separate_obligations_or_explicit_parse_limit(question, decomposed):
    contract = AnswerContract(question, "question")
    assert contract.quantity is None
    if decomposed:
        # I5 recognizes explicit coordination, without filling either fact.
        assert not contract.parse_failures and contract.kind == "composite"
        assert {part.quantity for part in contract.components} == {"voltage", "temperature"}
        assert len(contract.assess([])["obligations"]) == 2
        assert all(not item["covered"] for item in contract.assess([])["obligations"])
    else:
        assert "multiple_quantities_not_decomposed" in contract.parse_failures


@pytest.mark.parametrize("source", [
    "Nominal supply voltage is not 3.3 V.",
    "La tension nominale d'alimentation n'est pas de 3,3 V.",
    "La tension nominale d'alimentation ne dépasse jamais 3,3 V.",
])
def test_negated_quantity_is_kept_literal_without_becoming_a_positive_fact(source):
    cat = catalogue("Quelle est la tension nominale d'alimentation ?", [excerpt("R001", source)])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]
    assert "source_assertion_negated" in requirement_codes(result["answer_contract"])
    assert source in result["text"]
    assert cat.support_ledger()["rejected_relations"][0]["quote"] == source


@pytest.mark.parametrize("source", [
    "Nominal supply voltage may be 3.3 V.",
    "La tension nominale d'alimentation est d'environ 3,3 V.",
    "Nominal supply voltage: approximately 3.3 V.",
])
def test_uncertainty_is_disclosed_and_never_promoted_to_certainty(source):
    result = render(catalogue("Quelle est la tension nominale d'alimentation ?", [excerpt("R001", source)]), ["R001"])
    assert result["answer_contract"]["status"] == "ambiguous"
    assert not result["answer_contract"]["matched_relations"]
    assert "source_assertion_uncertain" in requirement_codes(result["answer_contract"])
    assert source in result["text"]


def test_asserted_positive_quantity_remains_answerable():
    cat = catalogue("Quelle est la tension nominale d'alimentation ?", [excerpt("R001", "Nominal supply voltage is 3.3 V.")])
    assert render(cat)["answer_contract"]["status"] == "covered"
    assert cat.deterministic_plan().references == ["R001"]


@pytest.mark.parametrize(("source", "covered"), [
    ("Typical supply voltage: 3.3 V.", False),
    ("Nominal supply voltage: 3.3 V.", False),
    ("Minimum supply voltage: 3.3 V.", False),
    ("Supply voltage: 3.3 V.", False),
    ("Maximum supply voltage: 3.3 V.", True),
    ("Operating supply voltage: 2 to 5 V.", True),
])
def test_a_requested_upper_bound_is_not_replaced_by_a_different_numeric_role(source, covered):
    cat = catalogue("Quelle est la tension maximale d'alimentation ?", [excerpt("R001", source)])
    result = render(cat, ["R001"])
    assert (result["answer_contract"]["status"] == "covered") is covered
    if not covered:
        assert "requested_bound_not_established" in requirement_codes(result["answer_contract"])
        assert cat.deterministic_plan() is None


def test_prefix_conditions_are_retained_and_block_an_unjustified_comparison():
    refs = [excerpt("R001", "At 25 °C, nominal supply voltage: 3.3 V.", document="a"),
            excerpt("R002", "At 85 °C, nominal supply voltage: 3.3 V.", document="b")]
    result = render(catalogue("Comparer les tensions nominales d'alimentation", refs, mode="comparison"))
    assert result["answer_contract"]["comparisons"][0]["status"] == "context_differs"
    assert "les valeurs citées concordent" not in result["text"]
    assert {fact["condition"] for fact in result["answer_contract"]["matched_relations"]} == {"At 25 °C", "At 85 °C"}


def test_identical_prefix_conditions_preserve_a_valid_comparison():
    refs = [excerpt("R001", "At 25 °C, nominal supply voltage: 3.3 V.", document="a"),
            excerpt("R002", "At 25 °C, nominal supply voltage: 3.3 V.", document="b")]
    result = render(catalogue("Comparer les tensions nominales d'alimentation", refs, mode="comparison"))
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["comparisons"][0]["status"] == "equal"


def test_cross_document_conflict_cannot_be_arbitrated_by_model_selection():
    refs = [excerpt("R001", "DEV123 operating supply voltage: 2 to 6 V.", document="a"),
            excerpt("R002", "DEV123 operating supply voltage: 2 to 8 V.", document="b")]
    cat = catalogue("Quelle est la plage de tension de fonctionnement de DEV123 ?", refs)
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "conflict"
    assert "same_entity_cross_document_conflicting_values" in requirement_codes(result["answer_contract"])
    assert set(result["effective_plan"]["references"]) == {"R001", "R002"}
    assert cat.deterministic_plan() is None


def test_cross_document_numeric_discrepancy_does_not_invent_entity_identity_or_precedence():
    refs = [excerpt("R001", "Recommended supply voltage: 3.0 V at TA = 25 °C.", document="a"),
            excerpt("R002", "Recommended supply voltage: 3.6 V at TA = 25 °C.", document="b")]
    result = render(catalogue("Quelle tension d'alimentation recommandée à TA = 25 °C selon les deux documents ?", refs), ["R001"])
    conflict = result["answer_contract"]["conflicts"][0]
    assert conflict["requirement"] == "same_label_cross_document_value_discrepancy"
    assert conflict["entity_identity_established"] is False and conflict["precedence_inferred"] is False
    assert "valeurs concurrentes" in result["text"]
    assert "aucune valeur n'est arbitrée" in result["text"]
    assert all(reference["text"] in result["text"] for reference in refs)
    assert {span["source_id"] for span in result["citation_spans"]} == {"S001", "S002"}


@pytest.mark.parametrize("second", [
    "DEV123 operating supply voltage: 2000 to 6000 mV.",
    "DEV456 operating supply voltage: 2 to 8 V.",
    "DEV123 operating supply voltage: 2 to 8 V at 85 °C.",
])
def test_equivalent_units_distinct_subjects_or_conditions_are_not_false_conflicts(second):
    refs = [excerpt("R001", "DEV123 operating supply voltage: 2 to 6 V.", document="a"), excerpt("R002", second, document="b")]
    assessment = catalogue("Quelle plage de tension de fonctionnement de DEV123 ?", refs).assess()
    assert assessment["status"] == "covered" and not assessment["conflicts"]


def test_ledger_preserves_known_provenance_and_leaves_missing_reference_fields_unknown():
    ref = excerpt("R001", "Nominal supply voltage: 3.3 V.")
    ref.update(version_id="version-frozen", extraction_revision_id="extraction-frozen", source_file_sha256="f" * 64,
               segments=[{"block_id": "block-frozen", "start_offset": 3, "end_offset": 34, "source_text_hash": "b" * 64}])
    cat = catalogue("Quelle tension nominale d'alimentation ?", [ref])
    evidence = cat.evidence()
    ledger = evidence["support_ledger"]
    assert evidence["support_ledger_sha256"] == digest(ledger)
    assert ledger["references"][0]["version_id"] == "version-frozen"
    assert ledger["references"][0]["generation_id"] is None
    assert ledger["references"][0]["source_file_sha256"] == "f" * 64
    assert ledger["references"][0]["literal"]["segments"] == ref["segments"]
    assert ledger["general_semantic_entailment_verified"] is False
    assert ledger["relations"][0]["source_ids"] == ["S001"]


def test_ledger_records_partial_extraction_and_reads_method_from_pinned_database(storage):
    import_fixture(storage, text="Nominal supply voltage: 3.3 V.")
    search, snapshot, db = library_search(storage)
    db.execute("UPDATE index_generations SET state='ready_partial' WHERE id=?", (snapshot.generations[0],))
    chunk = db.one("SELECT * FROM chunks LIMIT 1")
    source = search.resolver.source_for_chunk(chunk, snapshot)
    source["source_id"] = "S001"
    source["blocks"][0]["extraction_method"] = "native"  # unknown in pinned extraction metadata
    cat = StructuredAnswerBuilder(db, snapshot, "Quelle tension nominale d'alimentation ?",
                                  enforce_contract=True).catalogue([source], "question")
    ledger = cat.support_ledger()
    assert ledger["partial_generation_ids"] == snapshot.generations
    assert ledger["references"][0]["index_generation_state"] == "ready_partial"
    assert ledger["references"][0]["extraction_method"] == "unknown"
    assert ledger["original_extraction_fidelity_verified"] is False
    # I5 never turns a retrieval hint into proof of an unknown PDF extraction.
    assert ledger["question_status"] == "partial"
    assert ledger["references"][0]["literal"]["text"] == "Nominal supply voltage: 3.3 V."
    assert not ledger["relations"] and cat.model_view()["reference_ids"] == []


@pytest.mark.parametrize("mutation", ["tail", "value", "quote_source", "citation", "missing_citation", "fake_support", "coverage"])
def test_post_render_gate_rejects_added_or_altered_claims_even_with_recomputed_answer_hash(mutation):
    cat = catalogue("Quelle tension nominale d'alimentation ?", [excerpt("R001", "Nominal supply voltage: 3.3 V.")])
    rendered = copy.deepcopy(render(cat))
    if mutation == "tail":
        rendered["text"] += " Therefore the device is safe at 99 V."
    elif mutation == "value":
        rendered["text"] = rendered["text"].replace("3.3 V", "9.9 V")
    elif mutation == "quote_source":
        rendered["support_ledger"]["segments"][0]["source_ids"] = []
    elif mutation == "citation":
        rendered["text"] = rendered["text"].replace("[S001]", "[S999]")
    elif mutation == "missing_citation":
        rendered["text"] = rendered["text"].replace("[S001]", "      ")
        rendered["support_ledger"]["segments"] = rendered["support_ledger"]["segments"][:-1]
        rendered["citation_spans"] = []
        rendered["source_ids"] = []
    elif mutation == "fake_support":
        rendered["support_ledger"]["segments"][0]["reference_ids"] = ["R999"]
    else:
        rendered["answer_contract"]["status"] = "unassessed"
    rendered["support_ledger"]["answer_sha256"] = hashlib.sha256(rendered["text"].encode()).hexdigest()
    rendered["support_ledger_sha256"] = digest(rendered["support_ledger"])
    with pytest.raises(ApiError) as error:
        cat.verify_rendered(rendered)
    assert error.value.code == "structured_answer_support_invalid"


def test_post_render_gate_rejects_catalogue_mutation_after_planning():
    cat = catalogue("Quelle tension nominale d'alimentation ?", [excerpt("R001", "Nominal supply voltage: 3.3 V.")])
    rendered = render(cat)
    cat.references[0]["text"] = "Nominal supply voltage: 9.9 V."
    with pytest.raises(ApiError):
        cat.verify_rendered(rendered)


def test_calculation_support_preserves_verified_inputs_and_does_not_accept_an_altered_result():
    cat = catalogue("Somme des cellules A1 et B1", [cell("R001", "A1", "1.25"), cell("R002", "B1", "2.75")])
    rendered = render(cat)
    assert rendered["answer_contract"]["calculation"]["value"] == "4"
    assert rendered["support_validation"]["status"] == "passed"
    rendered["answer_contract"]["calculation"]["value"] = "5"
    with pytest.raises(ApiError):
        cat.verify_rendered(rendered)


def test_simple_question_without_complete_source_span_keeps_its_useful_quote_and_limit():
    source = "Le boîtier est étanche uniquement lorsque le couvercle est fermé."
    cat = catalogue("Dans quelle condition le boîtier est-il étanche ?", [excerpt("R001", source)])
    rendered = render(cat, ["R001"])
    assert rendered["answer_contract"]["status"] == "partial"
    assert source in rendered["text"] and "passage source complet n'est pas vérifié" in rendered["text"]
    assert rendered["support_validation"]["general_semantic_entailment_verified"] is False
    assert cat.deterministic_plan() is None


def test_deterministic_quantity_route_requires_all_requested_documents():
    cat = catalogue("Comparer les tensions nominales d'alimentation", [excerpt("R001", "Nominal supply voltage: 3.3 V.", document="a")], mode="comparison")
    assert cat.deterministic_plan(required_documents=["a", "b"]) is None


def test_model_schema_accepts_only_reference_organization_and_never_an_added_claim():
    cat = catalogue("Quelle tension ?", [excerpt("R001", "Supply voltage: 3.3 V.")])
    with pytest.raises(ApiError):
        cat.validate(json.dumps({"references": ["R001"], "comparisons": [], "conclusion": "Safe at 99 V"}))
    plan = cat.validate('{"references":["R001"],"comparisons":[]}')
    rendered = cat.render(plan, CharTokenizer(), 5000)
    assert cat.verify_rendered(rendered)["unsupported_characters"] == 0
