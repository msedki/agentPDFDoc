"""I5 development boundaries for obligations and exact publication intervals.

Literal invented examples, no held-out sources, model, OCR or semantic judge.
The character tokenizer is an explicit unit double; native quality/cost is a
separate qualification. Expected results were written before product changes.
"""

import copy

import pytest
from test_enhanced_answers import catalogue, cell, excerpt, render

from services.api.errors import ApiError
from services.api.structured_answer import digest


def source(identifier, text, *, name="DEV728.pdf"):
    result = excerpt(identifier, text, name=name)
    result.update(source_span_complete=True, version_id="v1", generation_id="g1",
                  extraction_revision_id="e1")
    return result


def composite():
    return catalogue("Quelles plages de tension d’alimentation et de température de fonctionnement du DEV728 ?", [
        source("R001", "DEV728 supply voltage: 2.1 V to 4.6 V."),
        source("R002", "DEV728 operating temperature: -25 °C to 90 °C."),
        source("R003", "DEV728 can drive an indicator lamp."),
    ])


def test_composite_obligations_exist_before_generation_and_keep_separate_quantities():
    contract = composite().support_ledger()
    obligations = contract["obligations"]
    assert len(obligations) == 2
    assert {item["quantity"] for item in obligations} == {"voltage", "temperature"}
    assert len({item["obligation_id"] for item in obligations}) == 2
    assert all(item["covered"] for item in obligations)


def test_omitted_proved_requirement_is_completed_and_free_distractor_is_removed():
    cat = composite()
    result = render(cat, ["R002", "R003"])
    assert result["answer_contract"]["status"] == "covered"
    assert result["effective_plan"]["references"] == ["R001", "R002"]
    assert "2.1 V to 4.6 V" in result["text"] and "-25 °C to 90 °C" in result["text"]
    assert "indicator lamp" not in result["text"]
    assert result["answer_contract"]["excluded_reference_ids"] == ["R003"]
    assert result["answer_contract"]["added_reference_ids"] == ["R001"]
    assert cat.deterministic_plan().references == ["R001", "R002"]


def test_missing_composite_requirement_does_not_discard_other_proved_information():
    cat = composite()
    cat.references = [cat.references[0]]
    result = render(cat)
    assert result["answer_contract"]["status"] == "partial"
    obligations = result["answer_contract"]["obligations"]
    assert [(item["quantity"], item["covered"]) for item in obligations] == [("voltage", True), ("temperature", False)]
    assert "2.1 V to 4.6 V" in result["text"]


def test_postposed_property_does_not_inherit_another_quantitys_typical_role():
    text = ("The DEV728 senses bus voltages from 0 V to 31 V. "
            "The device operates from a single 2.1 V to 4.6 V supply, drawing a typical 420 µA of supply current. "
            "The I2C-compatible interface supports several addresses.")
    cat = catalogue("Quelles plages de tension de bus et d’alimentation du DEV728 ?", [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    supply = next(item for item in result["answer_contract"]["matched_relations"] if item["property"] == "supply")
    assert supply["values"] == ["2.1", "4.6"] and supply["role"] != "typical"
    assert supply["subjects"] == ["DEV728"]


def test_explicit_other_component_cannot_supply_requested_subject():
    cat = catalogue("Quelle plage de tension d’alimentation du DEV728 ?", [source("R001",
        "DEV728 monitors current. ALT421 supply voltage: 2.1 V to 4.6 V.")])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])


def test_symmetric_and_single_ranges_keep_configuration_and_literal_polarity():
    text = "The comparator operates from a single 3 V to 12 V supply or a dual ±1.5 V to ±6 V supply."
    cat = catalogue("Quelles sont les plages d’alimentation simple et symétrique du DEV728 ?", [source("R001", text)])
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert {item["supply_configuration"] for item in assessment["obligations"]} == {"single", "dual"}
    dual = next(item for item in assessment["matched_relations"] if item.get("supply_configuration") == "dual")
    assert dual["polarity"] == "±" and dual["values"] == ["1.5", "6"]
    assert "±1.5 V to ±6 V" in result["text"]
    assert cat.deterministic_plan() is not None


def test_dual_supply_is_not_invented_from_single_range():
    cat = catalogue("Give the single and dual supply voltage ranges for DEV728.", [source("R001", "DEV728 single supply voltage: 3 V to 12 V.")])
    assessment = render(cat)["answer_contract"]
    assert assessment["status"] == "partial"
    assert not next(item for item in assessment["obligations"] if item["supply_configuration"] == "dual")["covered"]


@pytest.mark.parametrize(("question", "text", "markers"), [
    ("D’après la description du DEV728, quelle condition déclenche sa sortie et à quoi sert son hystérésis ?",
     "DEV728 asserts an alarm output only when the ambient pressure exceeds the configured threshold. "
     "DEV728 has approximately 3 units of hysteresis, which prevents repeated switching.",
     ("only when", "approximately", "prevents repeated switching")),
    ("Under what condition does DEV728 assert its output and what is the purpose of debounce?",
     "DEV728 asserts its output when the input is stable. DEV728 has debounce, which prevents repeated alarms.",
     ("when the input is stable", "prevents repeated alarms")),
])
def test_action_condition_and_function_are_independent_literal_obligations(question, text, markers):
    cat = catalogue(question, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert len(result["answer_contract"]["obligations"]) == 2
    assert all(marker in result["text"] for marker in markers)
    assert cat.deterministic_plan() is not None


def test_negated_action_does_not_become_a_positive_trigger_condition():
    cat = catalogue("Under what condition does DEV728 assert its output?", [source("R001",
        "DEV728 does not assert its output when the input is unstable.")])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert "does not assert" in result["text"]


def test_explicit_removed_need_is_supported_without_supplying_extra_items():
    cat = catalogue("Selon DEV728, quels circuits externes ne sont plus nécessaires ?", [source("R001",
        "DEV728 includes conditioning that eliminates the need for external adjustment, isolation, or amplification circuits.")])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert "external adjustment, isolation, or amplification circuits" in result["text"]
    assert "absence" not in result["text"]


def test_requested_relation_projects_out_unrelated_corrupt_sentence():
    text = ("DEV728 operates on a supply voltage from 2.1 V to 4.6 V. "
            "Because of low power dissipation (170 HW at 3.1 V), heating is reduced.")
    cat = catalogue("Quelle plage de tension d’alimentation du DEV728 ?", [source("R001", text)])
    result = render(cat)
    assert "2.1 V to 4.6 V" in result["text"]
    assert "170 HW" not in result["text"]
    assert result["support_validation"]["status"] == "passed"


def test_minimal_proof_keeps_following_explicit_exception():
    text = "DEV728 supply voltage: 2.1 V to 4.6 V. This range applies only at 25 °C, except during startup."
    result = render(catalogue("Quelle plage de tension d’alimentation du DEV728 ?", [source("R001", text)]))
    assert "This range applies only at 25 °C, except during startup." in result["text"]
    assert result["support_validation"]["status"] == "passed"


def test_unknown_request_is_reported_as_unanalysed_and_not_source_absence():
    cat = catalogue("Pourquoi cette architecture est-elle optimale pour DEV728 ?", [source("R001", "DEV728 supply voltage: 2.1 V to 4.6 V.")])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] != "covered"
    assert "analyse" in result["text"].lower() or "grammaire" in result["text"].lower()
    assert "n'est pas établie dans les passages" not in result["text"]


def test_budget_cannot_hide_composite_requirement_loss():
    cat = composite()
    cat.references[0]["text"] += (" This range applies only when "
                                  + "the explicit installation condition and " * 16 + "the source condition hold.")
    # This named tokenizer double counts len(text)/4, not one token/character.
    # 150 tokens fits the remaining proof plus notices but not the long reserve.
    result = render(cat, output_tokens=150)
    assessment = result["answer_contract"]
    assert assessment["status"] == "partial"
    assert assessment["omitted_reference_ids"]
    assert result["tokens"] <= 150


def test_conflicting_proved_variant_cannot_be_hidden_by_model_choice():
    cat = catalogue("Quelle tension d’alimentation du DEV728 ?", [
        source("R001", "DEV728 supply voltage: 3.1 V at 25 °C."),
        source("R002", "DEV728 supply voltage: 3.4 V at 25 °C."),
    ])
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "conflict"
    assert result["effective_plan"]["references"] == ["R001", "R002"]
    assert "3.1 V" in result["text"] and "3.4 V" in result["text"]


@pytest.mark.parametrize("alteration", ["value", "obligation", "projection"])
def test_post_render_verification_rejects_tampered_proof_or_obligation(alteration):
    cat = composite()
    result = copy.deepcopy(render(cat))
    if alteration == "value":
        result["text"] = result["text"].replace("4.6 V", "9.9 V")
    elif alteration == "obligation":
        result["answer_contract"]["obligations"][0]["covered"] = False
    else:
        result["answer_contract"]["publication_spans"]["R001"][0]["end_offset"] -= 1
    result["support_ledger_sha256"] = digest(result["support_ledger"])
    with pytest.raises(ApiError, match="preuves vérifiées"):
        cat.verify_rendered(result)


def test_model_receives_only_admissible_proofs_and_dependencies():
    cat = composite()
    assert cat.schema()["properties"]["references"]["items"]["enum"] == ["R001", "R002"]
    assert "indicator lamp" not in cat.prompt()
    assert len(cat.as_dict()["references"]) == 3  # unchanged internal audit set
    assert cat.evidence()["model_reference_ids"] == ["R001", "R002"]


def test_model_projection_does_not_disclose_an_unrequested_corrupt_sentence():
    text = "DEV728 supply voltage: 2.1 V to 4.6 V. Power dissipation is 170 HW."
    cat = catalogue("What is DEV728 supply voltage range?", [source("R001", text)])
    assert "2.1 V to 4.6 V" in cat.prompt() and "170 HW" not in cat.prompt()
    assert text == cat.references[0]["text"]


def test_unanalysed_question_never_sends_raw_catalogue_to_generator():
    cat = catalogue("Discuss the optimal architecture.", [source("R001", "Supply voltage: 2.1 V to 4.6 V.")])
    assert cat.model_view()["reference_ids"] == []
    assert cat.deterministic_plan().references == []
    assert "2.1 V" not in cat.prompt()


@pytest.mark.parametrize(("literal", "unit", "expected"), [
    ("75 ns", "µs", "0.075"), ("20 pF", "nF", "0.02"),
    ("0.47 µF", "nF", "470"), ("0.47 μF", "pF", "470000"),
    ("0.47 uF", "F", "0.00000047"),
])
def test_new_si_units_keep_exact_conversion_inputs_and_method(literal, unit, expected):
    result = render(catalogue(f"Convertir la cellule A1 en {unit}", [cell("R001", "A1", literal, kind="string")]))
    calculation = result["answer_contract"]["calculation"]
    assert calculation["value"] == expected and calculation["unit"] == unit
    assert calculation["inputs"][0]["reference_id"] == "R001"
    assert calculation["conversion"] and calculation["source_ids"] == ["S001"]
    assert result["support_validation"]["status"] == "passed"


def test_time_cannot_be_converted_into_a_capacitance():
    result = render(catalogue("Convertir la cellule A1 en pF", [cell("R001", "A1", "75 ns", kind="string")]))
    assert result["answer_contract"]["calculation"] is None
    assert any(item["requirement"] == "incompatible_units" for item in result["answer_contract"]["missing"])


def test_capacitance_test_condition_is_not_silently_ignored():
    cat = catalogue("Quel délai typique pour COUT = 30 pF ?", [source("R001", "DEV728 typical delay: 75 ns at COUT = 20 pF.")])
    assert render(cat, ["R001"])["answer_contract"]["status"] == "partial"
    positive = catalogue("Quel délai typique pour COUT = 20 pF ?", cat.references)
    assert render(positive)["answer_contract"]["status"] == "covered"


def test_mixed_quantitative_and_function_obligations_keep_both_proofs():
    cat = catalogue("What is DEV728 supply voltage range and what is the purpose of debounce?", [
        source("R001", "DEV728 supply voltage: 2.1 V to 4.6 V."),
        source("R002", "DEV728 includes debounce, which prevents repeated transitions."),
        source("R003", "DEV728 can drive an indicator lamp."),
    ])
    result = render(cat, ["R001", "R003"])
    obligations = result["answer_contract"]["obligations"]
    assert result["answer_contract"]["status"] == "covered"
    assert {item["kind"] for item in obligations} == {"interval", "qualitative_literal"}
    assert all(item["covered"] for item in obligations)
    assert result["effective_plan"]["references"] == ["R001", "R002"]
    assert "prevents repeated transitions" in result["text"] and "indicator lamp" not in result["text"]


def test_qualitative_literal_cannot_cover_a_different_intent_or_subject():
    from services.api.answer_contract import relation_supports_obligation

    cat = catalogue("What is the purpose of debounce for DEV728?", [
        source("R001", "DEV728 includes debounce, which prevents repeated transitions.")])
    ledger = cat.support_ledger()
    fact, obligation = ledger["relations"][0], ledger["obligations"][0]
    assert relation_supports_obligation(fact, obligation)
    assert not relation_supports_obligation(fact, {**obligation, "intent": "action_condition"})
    assert not relation_supports_obligation(fact, {**obligation, "subject": "ALT421"})
    assert not relation_supports_obligation(fact, {**obligation, "kind": "value_or_interval", "quantity": "voltage"})


def test_local_named_condition_overrides_general_only_under_explicit_unless_clause():
    from services.api.answer_contract import AnswerContract, _condition_measures

    fact = {"condition": "TA = 65 °C ; TA = 18 °C, VB = 4 V unless otherwise noted.",
            "local_condition": "TA = 65 °C", "general_condition": "TA = 18 °C, VB = 4 V unless otherwise noted.",
            "general_conditions_verified": True}
    assert AnswerContract._matches_points(fact, _condition_measures("TA = 65 °C"))
    assert not AnswerContract._matches_points(fact, _condition_measures("TA = 18 °C"))
    assert AnswerContract._matches_points(fact, _condition_measures("VB = 4 V"))
    assert not AnswerContract._matches_points(fact, _condition_measures("TJ = 65 °C"))


def test_literal_chained_assignment_preserves_named_minus_supply_and_alias():
    from services.api.answer_contract import AnswerContract, _condition_measures

    literal = "V− = GND = 0 V"
    fact = {"condition": literal}
    assert AnswerContract._matches_points(fact, _condition_measures("V- = 0 V"))
    assert AnswerContract._matches_points(fact, _condition_measures("GND = 0 V"))
    assert not AnswerContract._matches_points(fact, _condition_measures("V+ = 0 V"))
    assert _condition_measures(literal)[0]["text"] == literal


def test_unrequested_consequence_incise_is_excluded_without_changing_the_relation():
    text = ("DEV728 supply voltage: 2.1 V to 4.6 V, facilitating operation in portable sensors "
            "and fixed monitoring systems.")
    cat = catalogue("What is DEV728 supply voltage range?", [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert "2.1 V to 4.6 V" in result["text"] and "facilitating" not in result["text"]
    assert "facilitating" not in cat.prompt() and cat.references[0]["text"] == text


@pytest.mark.parametrize("restriction", [
    ", enabling operation only when the external input is stable.",
    ", allowing operation unless the protection is active.",
    ", facilitating operation in portable sensors. This range applies only at 18 °C.",
    ", facilitating operation in portable sensors. See section 7 for exceptions.",
])
def test_an_incise_cannot_hide_a_local_or_following_restriction(restriction):
    text = "DEV728 supply voltage: 2.1 V to 4.6 V" + restriction
    cat = catalogue("What is DEV728 supply voltage range?", [source("R001", text)])
    result = render(cat)
    assert text in result["text"]
    assert result["support_validation"]["status"] == "passed"


@pytest.mark.parametrize("question", ["Quelle valeur contient la cellule A1 ?", "Somme des cellules A1 et B1"])
def test_explicit_cells_and_calculation_inputs_exclude_an_unrequested_cell(question):
    cat = catalogue(question, [cell("R001", "A1", 2), cell("R002", "B1", 3), cell("R003", "C3", 999)])
    expected = ["R001", "R002"] if question.startswith("Somme") else ["R001"]
    assert cat.model_view()["reference_ids"] == expected
    result = render(cat, ["R003"])
    assert result["effective_plan"]["references"] == expected
    assert "999" not in result["text"] and "R003" in result["answer_contract"]["excluded_reference_ids"]


def test_required_documents_are_obligations_before_generation_and_cannot_be_erased_by_empty_argument():
    cat = catalogue("Compare the operating supply voltages.", [
        {**source("R001", "Operating supply voltage: 4 V."), "document_id": "a"},
        {**source("R002", "Operating current: 2 A."), "document_id": "b"},
    ])
    cat.required_documents = ("a", "b")
    projected = cat.model_view()["payload"]["question_contract"]
    assert projected["required_document_ids"] == ["a", "b"]
    assert {item["document_id"] for item in projected["obligations"]} == {"a", "b"}
    assert not next(item for item in projected["obligations"] if item["document_id"] == "b")["covered"]
    assert cat.assess(required_documents=[])["status"] == "partial"
    assert cat.as_dict()["required_documents"] == ["a", "b"]
