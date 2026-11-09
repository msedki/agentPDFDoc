"""A witnessed single-value column grants no statistical or bound meaning.

Invented FR/EN tables use explicit synthetic glyph observations and the real
SQLite catalogue/publication path. No PDF engine or generator is exercised.
"""

import copy

import pytest
from i5_witness_fixtures import witnessed_sparse_table
from test_api_storage import storage as storage
from test_enhanced_answers import render

from services.api.errors import ApiError
from services.api.evidence_selection import table_bundle
from services.api.structured_answer import StructuredAnswerBuilder, digest


def single_value_catalogue(storage, question, *, french=False, columns=(0, 1, 2), label=None):
    headings = [label or ("Paramètre" if french else "Parameter"),
                "Valeur" if french else "Value", "Unité" if french else "Unit"]
    values = ["Courant" if french else "Current", "2", "A"]
    rows = [[(position, fields[column]) for position, column in enumerate(columns)]
            for fields in (headings, values)]
    search, snapshot, source, text = witnessed_sparse_table(storage, rows)
    bundle, warnings = table_bundle(search.db, snapshot, source, question=question)
    assert not warnings
    cat = StructuredAnswerBuilder(search.db, snapshot, question, enforce_contract=True).catalogue(
        [{**bundle, "source_id": "S001"}], "question")
    return cat, text


@pytest.mark.parametrize("french", [False, True])
@pytest.mark.parametrize("columns", [(0, 1, 2), (2, 0, 1)])
def test_explicit_value_keeps_exact_citations_without_acquiring_a_statistical_role(storage, french, columns):
    question = "Quel est le courant ?" if french else "What is the current?"
    cat, text = single_value_catalogue(storage, question, french=french, columns=columns)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    facts = result["answer_contract"]["matched_relations"]
    assert len(facts) == 1
    assert (facts[0]["kind"], facts[0]["quantity"], facts[0]["values"], facts[0]["unit"]) == (
        "value", "current", ["2"], "A")
    assert facts[0]["role"] is None and facts[0]["bound_role"] is None
    assert facts[0]["table_bound"] is True
    assert all(item["covered"] for item in result["answer_contract"]["obligations"])
    assert result["source_ids"] == ["S001"]
    for citation in result["citation_spans"]:
        assert result["text"][citation["start_offset"]:citation["end_offset"]] == "[S001]"
    assert result["citation_spans"]
    assert cat.verify_rendered(result)["status"] == "passed"
    references = {item["id"]: item for item in cat.references}
    for reference_id in facts[0]["reference_ids"]:
        reference = references[reference_id]
        assert reference["text"] in text
        assert reference["version_id"] and reference["extraction_revision_id"]
        for segment in reference["segments"]:
            assert text[segment["start_offset"]:segment["end_offset"]] == reference["text"]


@pytest.mark.parametrize("label", ["Equipment", "Équipement", "Label", "Libellé", "Reference", "Référence"])
def test_label_alias_is_confined_to_the_witnessed_single_value_grammar(storage, label):
    cat, _ = single_value_catalogue(storage, "What is the current?", label=label)
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["answer_contract"]["matched_relations"][0]["bound_role"] is None


@pytest.mark.parametrize("question", [
    "What is the typical current?", "What is the maximum current?",
    "Quel est le courant typique ?", "Quel est le courant maximal ?",
])
def test_value_header_cannot_answer_an_unstated_statistical_or_bound_requirement(storage, question):
    cat, _ = single_value_catalogue(storage, question, french=question.startswith("Quel"))
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert not result["answer_contract"]["matched_relations"]
    for diagnostic in result["answer_contract"]["rejected_relations"]:
        assert diagnostic["role"] is None and diagnostic["bound_role"] is None
    view = cat.model_view()
    assert not any(item["covered"] for item in view["payload"]["question_contract"]["obligations"])
    if view["reference_ids"]:
        assert view["payload"]["question_contract"]["diagnostic_evidence"]
    assert cat.verify_rendered(result)["status"] == "passed"
    assert cat.references  # raw witnessed evidence remains available for audit


@pytest.mark.parametrize("field", ["role", "bound_role"])
@pytest.mark.parametrize("invented_role", ["typical", "maximum"])
def test_post_publication_role_addition_is_blocked_even_with_an_updated_ledger_hash(storage, field, invented_role):
    cat, _ = single_value_catalogue(storage, "What is the current?")
    result = copy.deepcopy(render(cat))
    result["answer_contract"]["matched_relations"][0][field] = invented_role
    result["support_ledger_sha256"] = digest(result["support_ledger"])
    with pytest.raises(ApiError) as failure:
        cat.verify_rendered(result)
    assert failure.value.code == "structured_answer_support_invalid"
