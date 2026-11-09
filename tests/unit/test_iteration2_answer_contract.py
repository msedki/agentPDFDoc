"""Iteration 2 boundary regressions; literal fixtures and a tokenizer unit double.

The malformed-plan shapes reproduce the I1 native failure, but these tests do
not invoke a model or claim native throughput/answer quality.
"""

import copy

import pytest
from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import catalogue, cell, excerpt, render, requirement_codes
from test_iteration2_table_evidence import HEADERS, sparse_table

from services.api.deterministic_calculations import conversion_description
from services.api.errors import ApiError
from services.api.evidence_selection import table_bundle
from services.api.structured_answer import Catalogue, StructuredAnswerBuilder


def test_enhanced_plan_preserves_known_group_references_and_deduplicates():
    cat = catalogue("Comparer les extraits", [excerpt("R001", "A"), excerpt("R002", "B")])
    plan = cat.validate('{"references":["R001","R001"],"comparisons":[{"references":["R001","R002"]},{"references":["R002","R001"]}]}')
    assert plan.references == ["R001", "R002"]
    assert [item.references for item in plan.comparisons] == [["R001", "R002"]]
    assert plan.normalization
    assert set(plan.model_dump()) == {"references", "comparisons"}


@pytest.mark.parametrize("raw", [
    '{"references":["R001"],"comparisons":[{"references":["R001","R999"]}]}',
    '{"references":["R999","R999"],"comparisons":[]}',
    '{"references":["R001"],"references":["R001"],"comparisons":[]}',
    '{"references":[1],"comparisons":[]}',
    '{"references":["R001"],"comparisons":[],"value":36}',
    '{"references":["R001"],"comparisons":[],"normalization":[]}',
])
def test_normalization_never_accepts_unknown_refs_types_keys_or_prose(raw):
    cat = catalogue("Comparer", [excerpt("R001", "A"), excerpt("R002", "B")])
    with pytest.raises(ApiError, match="preuves autorisées"):
        cat.validate(raw)


def test_normalization_does_not_change_legacy_strict_plan_contract():
    cat = Catalogue("comparison", [excerpt("R001", "A"), excerpt("R002", "B")])
    with pytest.raises(ApiError):
        cat.validate('{"references":["R001"],"comparisons":[{"references":["R001","R002"]}]}')
    with pytest.raises(ApiError):
        cat.validate('{"references":["R001","R001"],"comparisons":[]}')


@pytest.mark.parametrize(("value", "source_unit", "target_unit", "expected", "operation"), [
    ("140", "µs", "ms", "0.14", "/ 1000"),
    ("15.5", "ms", "µs", "15500", "× 1000"),
    ("0", "ms", "s", "0", "/ 1000"),
])
def test_source_bound_conversion_explains_the_actual_scale(value, source_unit, target_unit, expected, operation):
    cat = catalogue(f"Convertir la cellule D8 en {target_unit}, avec l'unité portée par la cellule E8.",
                    [cell("R001", "D8", value), cell("R002", "E8", source_unit, kind="string")])
    result = render(cat)
    calculation = result["answer_contract"]["calculation"]
    assert calculation["value"] == expected
    assert operation in result["text"]
    assert calculation["conversion"]["source_unit"] == source_unit
    assert calculation["conversion"]["target_unit"] == target_unit
    assert calculation["formula_evaluated"] is False


def test_temperature_conversion_shows_offset_and_does_not_claim_a_scale_only():
    result = render(catalogue("Convertir la cellule A1 en K", [cell("R001", "A1", "-40 °C", kind="string")]))
    assert result["answer_contract"]["calculation"]["value"] == "233.15"
    assert "+ 273.15" in result["text"]


def test_two_properties_in_one_exact_paragraph_have_separate_obligations():
    cat = catalogue("Quelles plages de tension de bus et d’alimentation VS pour LMX42 ?", [
        excerpt("R001", "Le composant LMX42 mesure une tension de bus comprise entre 0 et 30 V. "
                "Son alimentation VS doit être comprise entre 2,4 et 5,2 V. Ces deux plages décrivent des grandeurs distinctes.")])
    result = render(cat)
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert {fact["property"] for fact in assessment["matched_relations"]} == {"bus", "supply"}
    assert assessment["added_reference_ids"] == ["R001"]


def test_comparison_requires_each_property_in_each_document_and_shows_divergence():
    refs = [excerpt("R001", "Operating bus voltage: 0 to 30 V. Operating supply voltage: 2.4 to 5.2 V.", document="pdf"),
            excerpt("R002", "Operating bus voltage: 0 to 30 V. Operating supply voltage: 2.4 to 5.4 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension de bus et d’alimentation des deux documents", refs, mode="comparison"),
                    ["R001"], required_documents=["pdf", "docx"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered"
    assert len(assessment["obligations"]) == 4
    assert {entry["status"] for entry in assessment["comparisons"]} == {"equal", "different"}
    assert "diverg" in result["text"].lower()
    assert set(assessment["rendered_reference_ids"]) == {"R001", "R002"}


def test_a_missing_property_in_one_document_cannot_be_masked_by_other_document():
    refs = [excerpt("R001", "Bus voltage: 0 to 30 V. Supply voltage: 2.4 to 5.2 V.", document="pdf"),
            excerpt("R002", "Bus voltage: 0 to 30 V.", document="docx")]
    assessment = render(catalogue("Comparer les plages de tension de bus et d’alimentation", refs, mode="comparison"),
                        required_documents=["pdf", "docx"])["answer_contract"]
    assert assessment["status"] == "partial"
    assert any(item.get("document_id") == "docx" and item.get("property") == "supply"
               for item in assessment["missing"])


def test_inverted_or_detached_limits_are_not_assembled_into_a_range():
    refs = [excerpt("R001", "Bus voltage: entre 30 et 0 V."),
            excerpt("R002", "Supply voltage minimum: 2.4 V."),
            excerpt("R003", "Supply voltage maximum: 5.2 V.")]
    assessment = render(catalogue("Quelles plages de tension de bus et d’alimentation ?", refs),
                        ["R001", "R002", "R003"])["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"]


def test_proven_outside_sheet_refusal_is_explicit_and_deterministic():
    cat = catalogue("Quel marqueur figure dans la deuxième feuille du classeur ?", [cell("R001", "A5", "0")],
                    scope={"kind": "cell_range", "sheetId": "nonordinal-part-name", "rowStart": 5, "rowEnd": 6,
                           "columnStart": 1, "columnEnd": 6,
                           "authorized_sheet": {"id": "nonordinal-part-name", "ordinal": 1, "name": "Mesures"}})
    plan = cat.deterministic_plan()
    assert plan is not None and plan.references == []
    result = render(cat, ["R001"])
    assert result["answer_contract"]["scope_refusal"]["reason"] == "requested_sheet_outside_scope"
    assert result["effective_plan"]["references"] == []
    assert "deuxième" in result["text"] or "2" in result["text"]
    assert "périmètre" in result["text"]


def test_sheet_xml_part_name_is_not_evidence_of_sheet_ordinal():
    cat = catalogue("Quel marqueur figure dans la deuxième feuille du classeur ?", [cell("R001", "A5", "0")],
                    scope={"kind": "cell_range", "sheetId": "xlsx:xl/worksheets/sheet1.xml"})
    assert cat.deterministic_plan().references == []  # I5 no verified input to send to the model.
    assert cat.model_view()["reference_ids"] == []
    assert cat.assess([]).get("scope_refusal") is None


def test_unit_word_target_is_recognized_without_misclassifying_conversion_time():
    cat = catalogue("Exprimer en millisecondes les temps associés aux codes 000 et 111.", [])
    assert cat.contract.operation == "convert" and cat.contract.target_unit == "ms"
    assert cat.contract.requested_codes == ["000", "111"]


def table_catalogue(storage, rows, question, *, mutate_bundle=None):
    # I5 adds explicit synthetic glyph geometry; positive guarantees unchanged.
    search, snapshot, source, text = witnessed_sparse_table(storage, rows)
    source["source_id"] = "S001"
    source["blocks"][0].update(text=text, start_offset=0, end_offset=len(text))
    source["text"] = text
    bundle, _ = table_bundle(search.db, snapshot, source)
    if mutate_bundle:
        mutate_bundle(bundle)
    return StructuredAnswerBuilder(search.db, snapshot, question, enforce_contract=True).catalogue([bundle], "question")


def test_sparse_verified_table_keeps_maximum_separate_from_nominal(storage):
    cat = table_catalogue(storage, [HEADERS, [(1, "Bus voltage range"), (3, "–2.5"), (5, "41"), (6, "V")]],
                          "Quelle plage de tension de bus ?")
    result = render(cat)
    facts = result["answer_contract"]["matched_relations"]
    assert result["answer_contract"]["status"] == "covered", result["answer_contract"]
    assert len(facts) == 1 and facts[0]["values"] == ["-2.5", "41"]
    assert "MAX = 41" in result["text"] and "NOM = 41" not in result["text"]
    assert len(facts[0]["reference_ids"]) == 2


@pytest.mark.parametrize("mutation", ["role", "coordinate", "missing_header"])
def test_exact_text_without_authorized_verified_binding_never_establishes_table_range(storage, mutation):
    def mutate(bundle):
        body = next(block for block in bundle["blocks"] if block.get("table_context", {}).get("row_index") == 1)
        value = next(cell for cell in body["table_context"]["cells"] if cell["text"] == "41")
        if mutation == "role":
            value["headers"][0]["role"] = "minimum"
        elif mutation == "coordinate":
            value["column_start"] += 1  # Canonical geometry may renumber sparse columns.
        else:
            bundle["blocks"] = [body]
    cat = table_catalogue(storage, [HEADERS, [(1, "Bus voltage range"), (3, "0"), (5, "41"), (6, "V")]],
                          "Quelle plage de tension de bus ?", mutate_bundle=mutate)
    assert not any(ref.get("table_context") for ref in cat.references if "Bus voltage" in ref["text"])
    result = render(cat, [ref["id"] for ref in cat.references])
    assert result["answer_contract"]["status"] == "partial"
    assert not result["answer_contract"]["matched_relations"]


def test_code_duration_conversions_preserve_association_and_decimal_witness(storage):
    headers = [(0, "MEASCT2 D8"), (1, "MEASCT1 D7"), (2, "MEASCT0 D6"), (3, "CONVERSION TIME")]
    rows = [headers, [(0, "0"), (1, "0"), (2, "0"), (3, "125µs")],
            [(0, "1"), (1, "0"), (2, "0"), (3, "1.25ms")],
            [(0, "1"), (1, "1"), (2, "1"), (3, "7.812ms")]]
    cat = table_catalogue(storage, rows, "Selon MEASCT, exprimer en millisecondes les temps associés à 000 et 111.")
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered", result["answer_contract"]
    calculations = result["answer_contract"]["derived_calculations"]
    assert [(entry["inputs"][0]["label"], entry["value"], entry["unit"]) for entry in calculations] == [
        ("000", "0.125", "ms"), ("111", "7.812", "ms")]
    assert "/ 1000" in result["text"] and "1.25ms" in result["text"]


def test_ambiguous_text_decimal_is_not_silently_converted_without_same_table_witness(storage):
    headers = [(0, "CFG1"), (1, "CFG0"), (2, "CONVERSION TIME")]
    cat = table_catalogue(storage, [headers, [(0, "1"), (1, "1"), (2, "7.812ms")]],
                          "Exprimer en microsecondes le temps du code 11.")
    assessment = render(cat)["answer_contract"]
    assert assessment["status"] == "partial" and not assessment["derived_calculations"]
    assert "code_quantity_missing_or_ambiguous" in requirement_codes(assessment)


def test_two_conditional_ranges_are_not_covered_by_one_relation():
    cat = catalogue("Donne les deux plages d'alimentation V+ recommandées avec leurs conditions de température.",
                    [excerpt("R001", "Recommended supply voltage: 1.5 to 4.5 V for TA = -40 to 125 °C.")])
    assessment = render(cat)["answer_contract"]
    assert assessment["quantity"] == "voltage" and assessment["status"] == "partial"
    assert assessment["obligations"][0]["expected_count"] == 2
    assert assessment["obligations"][0]["matched_count"] == 1


def test_generic_express_verb_without_target_is_not_an_arithmetic_request():
    cat = catalogue("Exprime la plage de tension du document", [excerpt("R001", "Bus voltage: 0 to 30 V.")])
    assert cat.contract.operation is None and cat.contract.kind == "interval"
    assert render(cat)["answer_contract"]["status"] == "covered"


def test_named_sheet_outside_pinned_selection_is_refused_without_looking_it_up():
    cat = catalogue("Donne le code de contrôle de la feuille Archive.", [cell("R001", "A5", "0")],
                    scope={"kind": "cell_range", "sheetId": "part-x", "authorized_sheet": {
                        "id": "part-x", "name": "Mesures", "ordinal": 1}})
    refusal = render(cat, ["R001"])["answer_contract"]["scope_refusal"]
    assert refusal["reason"] == "requested_sheet_outside_scope" and refusal["requested_name"] == "Archive"
    assert cat.deterministic_plan().references == []


def rectangle_cells():
    values = {"A5": "Paramètre", "B5": "MIN", "C5": "MAX", "D5": "Valeur", "E5": "Unité", "F5": "Rôle / condition",
              "A6": "Température de fonctionnement TA", "B6": "-45", "C6": "125", "E6": "°C",
              "F6": "Conditions recommandées, section 4.2"}
    return [cell(f"R{index:03d}", address, value, kind="number" if address in {"B6", "C6"} else "string")
            for index, (address, value) in enumerate(values.items(), 1)]


def test_selected_cell_rectangle_binds_negative_limits_headers_unit_and_condition():
    scope = {"kind": "cell_range", "sheetId": "sheet-1", "rowStart": 5, "rowEnd": 6, "columnStart": 1, "columnEnd": 6}
    result = render(catalogue("Dans la plage sélectionnée A5:F6, donne la température de fonctionnement minimale, maximale et son unité.",
                              rectangle_cells(), scope=scope))
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered", assessment
    facts = [fact for fact in assessment["matched_relations"] if fact.get("cell_range_bound")]
    assert len(facts) == 1 and facts[0]["values"] == ["-45", "125"] and facts[0]["unit"] == "°C"
    assert "recommandées" in facts[0]["condition"]


@pytest.mark.parametrize("remove", ["B5", "C5", "E5", "E6", "F6"])
def test_rectangle_never_guesses_missing_header_unit_or_declared_condition(remove):
    refs = [ref for ref in rectangle_cells() if ref["cell_facts"]["address"] != remove]
    scope = {"kind": "cell_range", "sheetId": "sheet-1", "rowStart": 5, "rowEnd": 6, "columnStart": 1, "columnEnd": 6}
    assessment = render(catalogue("Quelle plage de température de fonctionnement dans la sélection ?", refs, scope=scope))["answer_contract"]
    assert assessment["status"] == "partial" and not assessment["matched_relations"]


def test_condition_role_is_kept_separate_from_measured_voltage_limits(storage):
    rows = [HEADERS, [(1, "Bus voltage range"), (3, "0"), (5, "41"), (6, "V")],
            [(1, "Operating supply range"), (3, "2"), (5, "4.8"), (6, "V")],
            [(0, "DRR"), (1, "Shunt offset voltage vs supply"), (2, "2 V ≤ VS ≤ 4.8 V"), (4, "±0.3"), (6, "µV/V")]]
    result = render(table_catalogue(storage, rows,
        "La condition DRR est-elle une plage de tension de bus ? Donner les plages de bus et d'alimentation, sans confondre condition d'essai et grandeur mesurée."))
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered", assessment
    assert {fact["property"] for fact in assessment["matched_relations"] if fact["kind"] == "interval"} == {"bus", "supply"}
    conditions = [fact for fact in assessment["matched_relations"] if fact["kind"] == "test_condition"]
    assert len(conditions) == 1 and conditions[0]["condition"] == "2 V ≤ VS ≤ 4.8 V"
    assert "ne définit pas à elle seule une limite" in result["text"]


@pytest.mark.parametrize(("name", "question"), [
    ("Parametres", "Convertis D8 de la feuille Parametres en ms."),
    ("2026", "Donne A1 de la feuille 2026."),
    ("Archive en cours", "Donne A1 de la feuille Archive en cours."),
])
def test_authorized_sheet_name_is_not_confused_with_continuation_or_ordinal(name, question):
    cat = catalogue(question, [], scope={"kind": "cell_range", "authorized_sheet": {"id": "part", "name": name, "ordinal": 1}})
    assert cat.contract.scope_refusal() is None


def test_non_decimal_scale_uses_exact_divisor_and_discloses_rounded_factor():
    conversion = conversion_description("60", "s", "min", "1")
    assert conversion["expression"] == "(60 / 60) min = 1 min"
    assert conversion["factor_ratio"] == ["1", "60"] and conversion["factor_rounded"] is True
    result = render(catalogue("Convertir la cellule A1 en min", [cell("R001", "A1", "1 s", kind="string")]))
    assert result["answer_contract"]["calculation"]["rounded"] is True
    assert "≈" in result["answer_contract"]["calculation"]["conversion"]["expression"]


def test_same_numbers_with_absolute_and_operating_roles_do_not_prove_agreement():
    refs = [excerpt("R001", "Absolute maximum supply voltage: 0 to 6 V.", document="pdf"),
            excerpt("R002", "Recommended supply voltage: 0 to 6 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension d'alimentation", refs, mode="comparison"),
                    required_documents=["pdf", "docx"])
    assert result["answer_contract"]["status"] == "ambiguous"
    assert result["answer_contract"]["comparisons"][0]["status"] == "context_differs"
    assert "les valeurs citées concordent" not in result["text"]
    assert "aucune conclusion d'accord" in result["text"]


def test_unknown_role_does_not_prove_agreement_even_for_identical_values():
    refs = [excerpt("R001", "Supply voltage: 1 to 4 V.", document="pdf"),
            excerpt("R002", "Supply voltage: 1 to 4 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension d'alimentation", refs, mode="comparison"),
                    required_documents=["pdf", "docx"])
    assert result["answer_contract"]["status"] == "partial"
    assert result["answer_contract"]["comparisons"][0]["status"] == "context_unestablished"
    assert "les valeurs citées concordent" not in result["text"]


def test_swapped_values_of_two_components_do_not_compare_as_an_anonymous_set():
    refs = [excerpt("R001", "DEV123 operating supply voltage: 1 to 3 V. DEV456 operating supply voltage: 2 to 4 V.", document="pdf"),
            excerpt("R002", "DEV123 operating supply voltage: 2 to 4 V. DEV456 operating supply voltage: 1 to 3 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension d'alimentation DEV123 et DEV456", refs, mode="comparison"),
                    required_documents=["pdf", "docx"])
    assessment = result["answer_contract"]
    assert assessment["status"] == "covered", assessment
    assert {item["subject"] for item in assessment["comparisons"]} == {"DEV123", "DEV456"}
    assert all(item["status"] == "different" for item in assessment["comparisons"])
    assert all(len(fact["subjects"]) == 1 for fact in assessment["matched_relations"])
    assert "DEV123" in result["text"] and "DEV456" in result["text"]


def test_generic_comparison_keeps_recognized_properties_instead_of_an_anonymous_set():
    refs = [excerpt("R001", "Operating bus voltage: 1 to 3 V. Operating supply voltage: 2 to 4 V.", document="pdf"),
            excerpt("R002", "Operating bus voltage: 2 to 4 V. Operating supply voltage: 1 to 3 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension de fonctionnement des deux documents", refs, mode="comparison"),
                    required_documents=["pdf", "docx"])
    assert {item["property"] for item in result["answer_contract"]["comparisons"]} == {"bus", "supply"}
    assert all(item["status"] == "different" for item in result["answer_contract"]["comparisons"])


def test_unrequested_component_in_a_clause_blocks_subject_inheritance():
    cat = catalogue("Quelle plage de tension d'alimentation pour DEV123 ?", [
        excerpt("R001", "DEV123 est seulement mentionné. DEV456 supply voltage: 2 to 4 V.")])
    assessment = render(cat, ["R001"])["answer_contract"]
    assert assessment["status"] == "partial"
    assert not assessment["matched_relations"]  # I5 excludes the other subject from publication.
    assert cat.references[0]["text"] == "DEV123 est seulement mentionné. DEV456 supply voltage: 2 to 4 V."
    assert cat.model_view()["reference_ids"] == []
    assert "requested_subject_quantity" in requirement_codes(assessment)


def test_single_component_filename_can_supply_the_heading_for_a_table_clause():
    cat = catalogue("Quelle plage de tension d'alimentation pour DEV123 ?", [
        excerpt("R001", "Operating supply voltage: 2 to 4 V.", name="DEV123-derived.docx")])
    assessment = render(cat)["answer_contract"]
    assert assessment["status"] == "covered"
    assert assessment["matched_relations"][0]["subjects"] == ["DEV123"]


@pytest.mark.parametrize("identifiers", [("DEV123", "DEV456"), ("Alpha", "Beta")])
def test_generic_comparison_keeps_each_local_identity_when_question_names_none(identifiers):
    first, second = identifiers
    refs = [excerpt("R001", f"{first} operating supply voltage: 1 to 3 V. {second} operating supply voltage: 2 to 4 V.", document="pdf"),
            excerpt("R002", f"{first} operating supply voltage: 2 to 4 V. {second} operating supply voltage: 1 to 3 V.", document="docx")]
    result = render(catalogue("Comparer les plages de tension d'alimentation de fonctionnement des deux documents", refs, mode="comparison"),
                    required_documents=["pdf", "docx"])
    assert result["answer_contract"]["comparisons"][0]["status"] == "different"
    assert "les valeurs citées concordent" not in result["text"]


def test_another_authorized_rows_valid_context_cannot_be_attached_to_this_excerpt(storage):
    def substitute(bundle):
        first = next(block for block in bundle["blocks"] if block.get("table_context", {}).get("row_index") == 1)
        second = next(block for block in bundle["blocks"] if block.get("table_context", {}).get("row_index") == 2)
        first["table_context"] = copy.deepcopy(second["table_context"])
    cat = table_catalogue(storage, [HEADERS,
                          [(1, "DEV123 operating supply voltage"), (3, "1.8"), (5, "5.5"), (6, "V")],
                          [(1, "DEV456 operating supply voltage"), (3, "2.1"), (5, "4.9"), (6, "V")]],
                          "Quelle plage de tension d'alimentation pour DEV123 ?", mutate_bundle=substitute)
    first = next(reference for reference in cat.references if "DEV123" in reference["text"])
    assert "table_context" not in first
    result = render(cat, [first["id"]])
    assert result["answer_contract"]["status"] == "partial"
    assert "MIN = 2.1" not in result["text"] and "MAX = 4.9" not in result["text"]


def test_minimum_and_the_maximum_excludes_a_nominal_value_from_requested_range():
    cat = catalogue("Comparer les tensions d'alimentation : donne le minimum et le maximum dans chaque document", [
        excerpt("R001", "Operating supply voltage: 1.8 to 5.5 V. Nominal supply voltage: 3.3 V.", document="pdf"),
        excerpt("R002", "Operating supply voltage: 1.9 to 5.2 V.", document="docx")], mode="comparison")
    assert cat.contract.kind == "interval"
    assessment = render(cat, required_documents=["pdf", "docx"])["answer_contract"]
    assert assessment["status"] == "covered"
    assert len(assessment["matched_relations"]) == 2
    assert assessment["comparisons"][0]["status"] == "different"


def test_normative_limit_question_requires_the_source_limitation_not_only_numbers():
    question = "Distingue la plage des limites absolues d'alimentation et le maximum recommandé. La limite absolue garantit-elle le fonctionnement normal ?"
    refs = [excerpt("R001", "Absolute maximum supply voltage: -0.2 to 7 V."),
            excerpt("R002", "Recommended supply voltage: 1.6 to 5 V.")]
    cat = catalogue(question, refs)
    assert "absolute_limit_operating_guarantee_not_established" in requirement_codes(render(cat)["answer_contract"])
    refs.append(excerpt("R003", "Absolute Maximum Ratings are stress ratings only, which do not imply functional operation of the device."))
    result = render(catalogue(question, refs))
    assert result["answer_contract"]["status"] == "covered"
    assert "ne garantissent pas le fonctionnement normal" in result["text"]
    assert "R003" in result["answer_contract"]["added_reference_ids"]


def test_ancestor_header_condition_survives_a_nearer_min_max_header(storage):
    def two_header_rows(block):
        cells = block["metadata"]["table_data"]["table_cells"]
        cells[0]["end_col_offset_idx"] = 7
        for value in cells:
            if value["start_row_offset_idx"] == 1:
                value["column_header"] = True
    search, snapshot, source, text = witnessed_sparse_table(storage, [
        [(1, "TA = 25 °C")], HEADERS,
        [(1, "Operating supply voltage"), (3, "1.8"), (5, "5.5"), (6, "V")]], target=2, mutate=two_header_rows)
    source["source_id"] = "S001"
    source["blocks"][0].update(text=text, start_offset=0, end_offset=len(text))
    source["text"] = text
    bundle, _ = table_bundle(search.db, snapshot, source)
    cat = StructuredAnswerBuilder(search.db, snapshot, "Quelle plage de tension d'alimentation de fonctionnement ?",
                                  enforce_contract=True).catalogue([bundle], "factual")
    result = render(cat)
    fact = result["answer_contract"]["matched_relations"][0]
    assert fact["condition"] == "TA = 25 °C"
    assert len(fact["reference_ids"]) == 3
    assert "TA = 25 °C" in result["text"]


def test_reference_cannot_relabel_its_registered_page_to_claim_another_scope(storage):
    search, snapshot, source, _ = sparse_table(storage, [HEADERS,
        [(1, "Operating supply voltage"), (3, "1.8"), (5, "5.5"), (6, "V")]])
    source["source_id"] = "S001"
    source["blocks"][0]["page_index"] = 1
    snapshot.page_indices = [1]
    with pytest.raises(ApiError) as error:
        StructuredAnswerBuilder(search.db, snapshot, "Quelle plage ?", enforce_contract=True).catalogue([source], "factual")
    assert error.value.code == "source_text_integrity_failure"


def test_equivalent_unit_spellings_do_not_count_as_two_distinct_ranges():
    refs = [excerpt("R001", "Recommended supply voltage: 1 to 5 V."),
            excerpt("R002", "Recommended supply voltage: 1000 to 5000 mV.")]
    assessment = render(catalogue("Donne les deux plages d'alimentation recommandées", refs))["answer_contract"]
    assert assessment["status"] == "partial"
    assert assessment["obligations"][0]["matched_count"] == 1
    assert assessment["conflicts"] == []


@pytest.mark.parametrize(("authorized", "requested"), [
    ("2026", "2025"), ("Parametres", "Parametres Archive"), ("Archive", "Archive en cours"),
])
def test_requested_full_sheet_name_never_collapses_to_authorized_prefix(authorized, requested):
    cat = catalogue(f"Donne la valeur de la cellule A1 de la feuille {requested}.", [cell("R001", "A1", "42")],
                    scope={"kind": "cell_range", "sheetId": "part", "rowStart": 1, "rowEnd": 10,
                           "columnStart": 1, "columnEnd": 6,
                           "authorized_sheet": {"id": "part", "name": authorized, "ordinal": 1}})
    assert cat.contract.scope_refusal() is not None
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "partial" and result["effective_plan"]["references"] == []
    assert "42" not in result["text"]
