"""I4 bounded literal QA: documentary meaning stays in the source quotation.

Development examples were recorded before the implementation in the I4
qualitative-baseline artifact. No generator or semantic judge is substituted.
The explicit completeness flag below represents the builder's checked block
boundary; separate tests exercise the real DB check and a forged hint.
"""

import copy
import hashlib

import pytest
from test_api_storage import import_fixture
from test_api_storage import storage as storage
from test_enhanced_answers import catalogue, excerpt, render
from test_i4_pdf_structure import index_dev
from test_retrieval import library_search

from services.api.answer_contract import AnswerContract
from services.api.errors import ApiError
from services.api.structured_answer import StructuredAnswerBuilder, digest


def complete_excerpt(reference, text, *, document="document-1"):
    value = excerpt(reference, text, document=document)
    value.update(source_span_complete=True, version_id="version-1", extraction_revision_id="extraction-1")
    return value


@pytest.mark.parametrize("question", [
    "Les documents A et B indiquent-ils la même tension d’alimentation du composant RS9 à 70 °C ?",
    "Do documents A and B give the same supply voltage for RS9 at 70 °C?",
    "Are the supply voltages for RS9 the same?",
    "La tension d'alimentation est-elle la même ?",
])
def test_equality_question_keeps_untyped_numeric_discrepancy_without_inventing_a_role(question):
    # The exact development R05 pair has a subject in the preceding sentence;
    # the literal excerpt, not the filename, establishes this local context.
    references = [complete_excerpt("R001", "Composant RS9. Supply voltage: 2.8 V at 70 °C.", document="a"),
                  complete_excerpt("R002", "Composant RS9. Supply voltage: 3.2 V at 70 °C.", document="b")]
    references[1]["version_id"] = "version-2"
    cat = catalogue(question, references)
    assert cat.contract.agreement_requested and cat.contract.comparison_requested
    answer = render(cat, ["R001"], required_documents=["a", "b"])
    assessment = answer["answer_contract"]
    assert assessment["status"] == "conflict"
    conflict = assessment["conflicts"][0]
    assert conflict["requirement"] == "same_label_cross_document_value_discrepancy"
    assert conflict["precedence_inferred"] is False and conflict["role_established"] is False
    assert set(conflict["reference_ids"]) == {"R001", "R002"}
    assert {fact["version_id"] for fact in assessment["matched_relations"]} == {"version-1", "version-2"}
    assert all(fact["role"] is None and fact["condition"] == "at 70 °C." for fact in assessment["matched_relations"])
    assert all(reference["text"] in answer["text"] for reference in references)
    assert "aucune valeur n'est arbitrée" in answer["text"]
    assert "les valeurs citées concordent" not in answer["text"]
    assert cat.deterministic_plan(required_documents=["a", "b"]) is None
    assert answer["support_validation"]["unsupported_characters"] == 0


@pytest.mark.parametrize("second", [
    "Composant RS9. Supply voltage: 2.8 V at 70 °C.",
    "Composant RS9. Supply voltage: 2800 mV at 70 °C.",
])
def test_equal_untyped_numbers_do_not_prove_agreement_of_unknown_roles(second):
    references = [complete_excerpt("R001", "Composant RS9. Supply voltage: 2.8 V at 70 °C.", document="a"),
                  complete_excerpt("R002", second, document="b")]
    answer = render(catalogue("Do the documents give the same supply voltage for RS9 at 70 °C?", references),
                    required_documents=["a", "b"])
    assessment = answer["answer_contract"]
    assert assessment["status"] == "partial" and not assessment["conflicts"]
    assert assessment["comparisons"][0]["status"] == "context_unestablished"
    assert assessment["comparisons"][0]["numeric_agreement"] == "equal"
    assert "les valeurs citées concordent" not in answer["text"]
    assert all(reference["text"] in answer["text"] for reference in references)


def test_known_nominal_roles_and_equivalent_units_allow_bounded_agreement():
    references = [complete_excerpt("R001", "Composant RS9. Nominal supply voltage: 2.8 V at 70 °C.", document="a"),
                  complete_excerpt("R002", "Composant RS9. Nominal supply voltage: 2800 mV at 70 °C.", document="b")]
    answer = render(catalogue("Do the documents give the same nominal supply voltage for RS9 at 70 °C?", references),
                    required_documents=["a", "b"])
    assessment = answer["answer_contract"]
    assert assessment["status"] == "covered" and not assessment["conflicts"]
    assert assessment["comparisons"][0]["status"] == "equal"
    assert "les valeurs citées concordent" in answer["text"]


@pytest.mark.parametrize("second", [
    "Composant RS10. Supply voltage: 3.2 V at 70 °C.",
    "Composants RS9 et RS10. Supply voltage: 3.2 V at 70 °C.",
    "Composant RS9. Supply voltage: 3.2 V at 85 °C.",
    "Composant RS9. Nominal supply voltage: 3.2 V at 70 °C.",
    "Composant RS9. Bus voltage: 3.2 V at 70 °C.",
    "Composant RS9. Supply voltage: approximately 3.2 V at 70 °C.",
    "Composant RS9. Supply voltage: not 3.2 V at 70 °C.",
])
def test_different_context_does_not_become_same_label_conflict_or_positive_agreement(second):
    references = [complete_excerpt("R001", "Composant RS9. Supply voltage: 2.8 V at 70 °C.", document="a"),
                  complete_excerpt("R002", second, document="b")]
    answer = render(catalogue("Do the documents give the same supply voltage for RS9 at 70 °C?", references),
                    required_documents=["a", "b"])
    assessment = answer["answer_contract"]
    assert assessment["status"] in {"partial", "ambiguous"} and not assessment["conflicts"]
    assert "les valeurs citées concordent" not in answer["text"]
    assert all(item["status"] != "equal" for item in assessment["comparisons"])


def test_a_single_document_cannot_establish_an_interdocument_agreement():
    cat = catalogue("Do the documents give the same nominal supply voltage for RS9?", [
        complete_excerpt("R001", "Composant RS9. Nominal supply voltage: 2.8 V at 70 °C.")])
    assessment = cat.assess()
    assert assessment["status"] == "partial"
    assert any(item["requirement"] == "comparison_context_not_established" for item in assessment["missing"])
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize("question", [
    "Quelle tension d'alimentation de RS9 est donnée dans les mêmes conditions ?",
    "What supply voltage for RS9 applies under the same conditions?",
    "Donne la tension d'alimentation et la même température.",
])
def test_same_conditions_or_another_quantity_does_not_request_voltage_agreement(question):
    contract = AnswerContract(question, "question")
    assert not contract.agreement_requested


@pytest.mark.parametrize(("question", "source"), [
    ("Dans quelle condition le boîtier est-il étanche ?", "Le boîtier est étanche uniquement lorsque le couvercle est fermé."),
    ("Sous quelle condition la vanne est-elle ouverte ?", "La vanne est ouverte uniquement lorsque la pression est stabilisée."),
    ("Under what condition is the latch locked?", "The latch is locked when the lever is down."),
    ("Quel est le matériau du carter ?", "Matériau du carter : aluminium."),
    ("What is the material of the casing?", "Material of the casing: aluminium."),
    ("Why is the alarm active?", "The alarm is active because the inlet is blocked."),
    ("Pourquoi la vanne est-elle ouverte ?", "La vanne est ouverte parce que le réservoir est plein."),
    ("Sous quelle condition la vanne est-elle ouverte ?", "La vanne est ouverte lorsque la pression est stabilisée, sauf pendant la maintenance."),
    ("Under what condition is the latch not locked?", "The latch is not locked when the lever is down."),
    ("Sous quelle condition la vanne est-elle ouverte ?", "La vanne est ouverte lorsque la commande n'est pas désactivée."),
])
def test_literal_question_answer_preserves_the_entire_assertion_and_qualifier(question, source):
    cat = catalogue(question, [complete_excerpt("R001", source)])
    plan = cat.deterministic_plan()
    assert plan is not None and plan.references == ["R001"]
    answer = render(cat)
    assert answer["answer_contract"]["status"] == "covered"
    assert source in answer["text"]
    assert "reste à vérifier" not in answer["text"]
    assert answer["source_ids"] == ["S001"]
    assert answer["support_validation"]["unsupported_characters"] == 0
    ledger = cat.support_ledger()
    assert ledger["general_semantic_entailment_verified"] is False
    assert ledger["relations"][0]["quote"] == source
    assert ledger["relations"][0]["reference_ids"] == ["R001"]
    assert ledger["relations"][0]["version_id"] == "version-1"
    assert ledger["references"][0]["source_span_complete"] is True


@pytest.mark.parametrize(("question", "source", "status"), [
    ("Sous quelle condition la vanne est-elle ouverte ?", "La trappe est ouverte uniquement lorsque la pression est stabilisée.", "partial"),
    ("Under what condition is the latch locked?", "The latch is painted when the lever is down.", "partial"),
    ("Under what condition is the latch locked?", "The latch is not locked when the lever is down.", "partial"),
    ("Under what condition is the latch locked?", "The latch is locked.", "partial"),
    ("Pourquoi la tension nominale est-elle de 3,3 V ?", "Nominal voltage: 3.3 V.", "partial"),
    ("Pourquoi la vanne est-elle ouverte ?", "La vanne est ouverte uniquement lorsque la pression est stabilisée.", "partial"),
    ("Under what condition is it locked?", "It is locked when the lever is down.", "ambiguous"),
    ("Under what condition is the latch locked?", "The latch is possibly locked when the lever is down.", "ambiguous"),
    ("Under what condition is the latch locked?", "The latch is locked when the lever is down. This statement is unverified.", "ambiguous"),
])
def test_an_answer_like_passage_does_not_establish_an_absent_or_qualified_fact(question, source, status):
    cat = catalogue(question, [complete_excerpt("R001", source)])
    answer = render(cat, ["R001"])
    assert answer["answer_contract"]["status"] == status
    assert not answer["answer_contract"]["matched_qualitative_relations"]
    assert source in answer["text"]
    assert cat.deterministic_plan() is None
    assert answer["support_validation"]["status"] == "passed"
    if question.startswith("Pourquoi"):
        assert "L'explication causale demandée n'est pas explicitement établie" in answer["text"]
        assert not answer["answer_contract"]["matched_relations"]


def test_opposite_statements_and_versions_are_preserved_even_if_the_model_omits_one():
    positive = complete_excerpt("R001", "The latch is locked when the lever is down.")
    negative = complete_excerpt("R002", "The latch is not locked when the lever is down.")
    negative["version_id"] = "version-2"
    cat = catalogue("Under what condition is the latch locked?", [positive, negative])
    answer = render(cat, ["R001"])
    assert answer["answer_contract"]["status"] == "conflict"
    assert answer["answer_contract"]["added_reference_ids"] == ["R002"]
    assert positive["text"] in answer["text"] and negative["text"] in answer["text"]
    assert "aucune priorité entre documents ou versions" in answer["text"]
    assert answer["source_ids"] == ["S001", "S002"]
    assert cat.deterministic_plan() is None
    assert cat.support_ledger()["conflicts"][0]["precedence_inferred"] is False


@pytest.mark.parametrize(("question", "source"), [
    ("Dans quelle condition le boîtier est-il étanche ?", "Le boîtier est étanche uniquement lorsqu'il est fermé."),
    ("Dans quelle condition le boîtier est-il étanche ?", "Le boîtier est étanche uniquement lorsque celui-ci est fermé."),
    ("Under what condition is the latch locked?", "The latch is locked when it is closed."),
    ("Under what condition is the latch locked?", "The latch is locked when its cover is closed."),
])
def test_a_pronoun_or_possessive_in_the_condition_does_not_get_an_invented_antecedent(question, source):
    cat = catalogue(question, [complete_excerpt("R001", source)])
    answer = render(cat)
    assert answer["answer_contract"]["status"] == "ambiguous"
    assert source in answer["text"] and "référent du pronom" in answer["text"]
    assert not answer["answer_contract"]["matched_qualitative_relations"]
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize(("question", "source"), [
    ("Quel est le matériau du carter ?", "Matériau du carter : non renseigné."),
    ("What is the material of the casing?", "Material of the casing: unknown."),
    ("Under what condition is the latch locked?", "The latch is locked when unknown."),
])
def test_an_explicitly_missing_field_or_condition_does_not_become_an_established_fact(question, source):
    cat = catalogue(question, [complete_excerpt("R001", source)])
    answer = render(cat)
    assert answer["answer_contract"]["status"] == "partial"
    assert source in answer["text"]
    assert "qualitative_information_absent" in {item["requirement"] for item in answer["answer_contract"]["missing"]}
    assert cat.deterministic_plan() is None


def test_source_boundary_is_recomputed_from_the_database_and_cannot_be_asserted_by_a_source_hint(storage):
    text = "Context. The latch is locked when the lever is down."
    import_fixture(storage, text=text)
    search, snapshot, db = library_search(storage)
    chunk = db.one("SELECT * FROM chunks LIMIT 1")
    source = search.resolver.source_for_chunk(chunk, snapshot)
    source["source_id"] = "S001"
    block = source["blocks"][0]
    block.update(start_offset=len("Context. "), text=text[len("Context. "):], source_span_complete=True)
    cat = StructuredAnswerBuilder(db, snapshot, "Under what condition is the latch locked?",
                                  enforce_contract=True).catalogue([source], "question")
    assert cat.references[0]["source_span_complete"] is False
    answer = render(cat, [cat.references[0]["id"]])
    assert answer["answer_contract"]["status"] == "partial"
    assert "passage source complet n'est pas vérifié" in answer["text"]
    assert block["text"] in answer["text"]


def test_complete_verified_database_passage_answers_the_simple_question_without_a_model(storage):
    text = "Le boîtier est étanche uniquement lorsque le couvercle est fermé."
    import_fixture(storage, text=text)
    search, snapshot, db = library_search(storage)
    source = search.resolver.source_for_chunk(db.one("SELECT * FROM chunks LIMIT 1"), snapshot)
    source["source_id"] = "S001"
    cat = StructuredAnswerBuilder(db, snapshot, "Dans quelle condition le boîtier est-il étanche ?",
                                  enforce_contract=True).catalogue([source], "question")
    assert cat.references[0]["source_span_complete"] is True
    assert cat.deterministic_plan() is not None
    answer = render(cat)
    assert answer["answer_contract"]["status"] == "covered"
    assert text in answer["text"] and "reste à vérifier" not in answer["text"]


def test_post_render_verification_rejects_removing_only_from_a_source_condition():
    cat = catalogue("Under what condition is the latch locked?", [
        complete_excerpt("R001", "The latch is locked only when the lever is down.")])
    answer = copy.deepcopy(render(cat))
    answer["text"] = answer["text"].replace("only when", "when")
    answer["support_ledger"]["answer_sha256"] = hashlib.sha256(answer["text"].encode()).hexdigest()
    answer["support_ledger_sha256"] = digest(answer["support_ledger"])
    with pytest.raises(ApiError) as error:
        cat.verify_rendered(answer)
    assert error.value.code == "structured_answer_support_invalid"


@pytest.mark.parametrize("question", [
    "Explique le fonctionnement avec la tension nominale de 3,3 V.",
    "How does the nominal voltage control the device?",
    "Peux-tu expliquer pourquoi la tension nominale est de 3,3 V ?",
])
def test_an_unrecognized_explanation_request_cannot_be_reduced_to_a_quantity_lookup(question):
    source = "Nominal supply voltage: 3.3 V."
    cat = catalogue(question, [complete_excerpt("R001", source)])
    answer = render(cat, ["R001"])
    assert answer["answer_contract"]["status"] == "partial"
    assert source in answer["text"] and "L'explication demandée n'est pas établie" in answer["text"]
    assert cat.deterministic_plan() is None


def list_catalogue(storage, case="S01", *, damage=None, first_only=False):
    result = index_dev(storage, case)
    sources = copy.deepcopy(result["sources"][:1] if first_only else result["sources"])
    for index, source in enumerate(sources, 1):
        source["source_id"] = f"S{index:03d}"
        if damage == "missing_heading":
            source["blocks"] = [block for block in source["blocks"] if block["id"] != result["names"]["P"]["id"]]
        elif damage == "forged_heading":
            for block in source["blocks"]:
                if block.get("list_context"):
                    block["list_context"]["heading"]["text"] = "Recommended bus voltage:"
    cat = StructuredAnswerBuilder(storage[1], result["snapshot"],
                                  "Donne les deux plages d'alimentation avec leurs conditions de température.",
                                  enforce_contract=True).catalogue(sources, "question")
    return cat, result


def test_verified_list_keeps_numeric_rows_conditions_and_heading_as_separate_support(storage):
    cat, result = list_catalogue(storage)
    assert cat.deterministic_plan() is not None
    answer = render(cat)
    assessment = answer["answer_contract"]
    assert assessment["status"] == "covered"
    assert {(tuple(fact["values"]), fact["condition"]) for fact in assessment["matched_relations"]} == {
        (("2.4", "3.6"), "at 25 °C"), (("2.7", "3.3"), "at 70 °C")}
    by_id = {reference["id"]: reference for reference in cat.references}
    for fact in assessment["matched_relations"]:
        assert fact["quote"] in {result["names"][name]["text"] for name in ("V1", "V2")}
        assert "Supply range" not in fact["quote"]
        assert fact["list_binding"]["catalogue_group_complete"]
        assert any(by_id[reference]["text"] == "Supply range:" for reference in fact["reference_ids"])
        assert set(fact["reference_ids"]) <= set(assessment["rendered_reference_ids"])
    assert answer["support_validation"]["status"] == "passed"


def test_selecting_one_item_from_a_complete_catalogue_recomputes_list_coverage(storage):
    cat, _ = list_catalogue(storage)
    assert cat.assess()["status"] == "covered"
    item = next(reference for reference in cat.references if reference.get("list_context"))
    visible_ids = item["list_context"]["reference_ids"]
    subset = cat.assess(selected_ids=visible_ids)
    assert subset["status"] == "partial" and len(subset["matched_relations"]) == 1
    assert subset["matched_relations"][0]["list_binding"]["visible_item_count"] == 1
    assert not subset["matched_relations"][0]["list_binding"]["catalogue_group_complete"]
    assert any(item["requirement"] == "list_group_incomplete" for item in subset["missing"])


@pytest.mark.parametrize("damage", ["missing_heading", "forged_heading"])
def test_a_list_title_is_neither_borrowed_from_outside_the_catalogue_nor_trusted_as_a_hint(storage, damage):
    cat, _ = list_catalogue(storage, damage=damage)
    answer = render(cat, [reference["id"] for reference in cat.references])
    assert not any(reference.get("list_context") for reference in cat.references)
    assert answer["answer_contract"]["status"] == "partial"
    assert not answer["answer_contract"]["matched_relations"]
    assert cat.deterministic_plan() is None


@pytest.mark.parametrize(("case", "first_only"), [("S07", False), ("S08", True)])
def test_incomplete_list_keeps_known_relations_without_claiming_group_completeness(storage, case, first_only):
    cat, _ = list_catalogue(storage, case, first_only=first_only)
    answer = render(cat, [reference["id"] for reference in cat.references])
    assessment = answer["answer_contract"]
    assert assessment["status"] == "partial"
    assert assessment["matched_relations"]
    assert any(item["requirement"] == "list_group_incomplete" for item in assessment["missing"])
    assert all(not fact["list_binding"]["catalogue_group_complete"] for fact in assessment["matched_relations"])
    assert "aucune complétude du groupe" in answer["text"]
    assert cat.deterministic_plan() is None


def test_explicit_from_temperature_range_is_a_literal_condition_not_a_storage_statement():
    source = "Supply voltage: 2.1 V to 4.9 V from –30 °C to 90 °C"
    cat = catalogue("Donne la plage d'alimentation avec ses conditions de température.", [excerpt("R001", source)])
    answer = render(cat)
    assert answer["answer_contract"]["status"] == "covered"
    assert answer["answer_contract"]["matched_relations"][0]["condition"] == "from –30 °C to 90 °C"
    unrelated = "Supply voltage: 2.1 V to 4.9 V; storage temperature: from –30 °C to 90 °C"
    refused = catalogue(cat.contract.question, [excerpt("R001", unrelated)])
    assert render(refused, ["R001"])["answer_contract"]["status"] == "partial"


def test_omitted_retrieval_variant_is_reported_in_the_text_and_prevents_an_agreement_conclusion():
    refs = [excerpt("R001", "Nominal supply voltage: 3.3 V.", document="a"),
            excerpt("R002", "Nominal supply voltage: 3.3 V.", document="b")]
    cat = catalogue("Comparer les tensions nominales d'alimentation", refs, mode="comparison")
    assert render(cat, required_documents=["a", "b"])["answer_contract"]["status"] == "covered"
    cat.retrieval_limitations = [{"code": "evidence_coverage_incomplete", "missing_relation_variants": 1}]
    answer = render(cat, required_documents=["a", "b"])
    assert answer["answer_contract"]["status"] == "partial"
    assert "n'a pas conservé toutes les variantes" in answer["text"]
    assert "les valeurs citées concordent" not in answer["text"]
    assert not answer["answer_contract"]["comparisons"]
    assert cat.deterministic_plan(required_documents=["a", "b"]) is None
    notice = next(item for item in answer["support_ledger"]["segments"] if item.get("notice") == "retrieval_coverage_incomplete")
    assert notice["reference_ids"] == notice["source_ids"] == []
    assert cat.support_ledger()["retrieval_limitations"] == cat.retrieval_limitations
    assert answer["support_validation"]["status"] == "passed"
    cat.retrieval_limitations = []
    with pytest.raises(ApiError):
        cat.verify_rendered(answer)


@pytest.mark.parametrize("limitation", [
    {"code": "evidence_coverage_incomplete", "missing_relation_variants": True},
    {"code": "evidence_coverage_incomplete", "missing_relation_variants": 0},
    {"code": "evidence_coverage_incomplete", "missing_relation_variants": 1, "message": "Unverified fact"},
    {"code": "arbitrary_fact", "missing_relation_variants": 1},
])
def test_retrieval_notices_cannot_introduce_free_text_or_invalid_counts(limitation):
    cat = catalogue("Quelle tension ?", [excerpt("R001", "Supply voltage: 3.3 V.")])
    cat.retrieval_limitations = [limitation]
    with pytest.raises(ApiError) as error:
        render(cat)
    assert error.value.code == "invalid_retrieval_limitation"
