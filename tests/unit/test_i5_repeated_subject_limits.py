"""Literal repeated-subject limitations through the publication boundary.

Invented prose, a reference catalogue and the existing token-count double;
these tests do not qualify Office extraction or the native generator.
"""

import pytest
from test_enhanced_answers import catalogue, render
from test_i5_obligation_publication import source

from services.api.literal_evidence import proof_envelope


@pytest.mark.parametrize("first", [
    "The output current is not 12 mA.",
    "The output current is 12 mA.",
])
def test_repeated_subject_negation_is_published_with_the_number_and_cannot_establish_it(first):
    limitation = "The output current is not established by this document."
    text = first + " " + limitation
    cat = catalogue("Quel courant de sortie est établi ?", [source("R001", text, name="Limits.docx")])
    result = render(cat, ["R001"])
    assert text in result["text"]
    assert result["answer_contract"]["status"] == "partial"
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert result["source_ids"] == ["S001"] and result["citation_spans"]
    assert result["answer_contract"]["publication_spans"]["R001"] == [
        {"start_offset": 0, "end_offset": len(text)}]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize(("first", "limitation"), [
    ("The output current is 12 mA.", "The output current is not established by this document."),
    ("Output current: 12 mA.", "Output current is not guaranteed during startup."),
    ("The output current is 12 mA.", "THE output current is only valid under the stated load."),
    ("The output current is 12 mA.", "The  output current is never guaranteed."),
    ("Le courant de sortie est de 12 mA.", "Le courant de sortie n'est pas établi par ce document."),
    ("Le courant de sortie est de 12 mA.", "Le courant de sortie n’est pas garanti au démarrage."),
    ("La tension de sortie est de 3 V.", "La tension de sortie est valable seulement sous charge."),
])
def test_explicit_repeated_subject_keeps_its_literal_limitation(first, limitation):
    text = first + " " + limitation
    assert proof_envelope(text, 0, len(first)) == (0, len(text))


@pytest.mark.parametrize("following", [
    "The input current is not established by this document.",
    "The output voltage is not established by this document.",
    "The output current limit is not established by this document.",
    "The output current of ALT318 is not established by this document.",
    "The output current is described in the electrical chapter.",
    "An unrelated sentence. The output current is not established by this document.",
])
def test_a_different_or_unrestricted_assertion_is_not_attached(following):
    first = "The output current is 12 mA."
    assert proof_envelope(first + " " + following, 0, len(first)) == (0, len(first))


@pytest.mark.parametrize(("first", "following"), [
    ("DEV407 output current is 12 mA.", "ALT318 output current is not established."),
    ("Output current at TA = 25 °C is 12 mA.", "Output current at TA = 85 °C is not established."),
])
def test_explicit_component_or_condition_in_the_subject_cannot_be_borrowed(first, following):
    assert proof_envelope(first + " " + following, 0, len(first)) == (0, len(first))


def test_repetition_does_not_cross_a_paragraph_boundary_or_an_authorized_end():
    first = "The output current is 12 mA."
    limitation = "The output current is not established by this document."
    assert proof_envelope(first + "\n\n" + limitation, 0, len(first)) == (0, len(first))
    assert proof_envelope(first, 0, len(first)) == (0, len(first))


def test_unrelated_negation_cannot_poison_the_published_current():
    first = "The output current is 12 mA."
    cat = catalogue("Quel courant de sortie est établi ?", [source(
        "R001", first + " The output voltage is not established by this document.", name="Limits.docx")])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert first in result["text"] and "voltage" not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("other_point", ["TA = 85 °C", "TA = 358.15 K"])
def test_a_negation_at_another_exact_point_does_not_invalidate_the_supported_point(other_point):
    first = "The output current is 12 mA at TA = 25 °C."
    following = "The output current is not established at " + other_point + "."
    cat = catalogue("Quel courant de sortie est établi à TA = 25 °C ?", [source(
        "R001", first + " " + following, name="Limits.docx")])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert first in result["text"] and following not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize("following", [
    "The output current is not established at TA = 25 °C.",
    "The output current is not established at TA = 298.15 K.",
    "The output current is only guaranteed at TA = 85 °C.",
    "The output current is not established except at TA = 85 °C.",
    "The output current is not established globally, even at TA = 85 °C.",
    "The output current is not established at TA = 20 °C to 85 °C.",
    "The output current is not established at TA = 25 °C or 85 °C.",
    "The output current is not established at TJ = 85 °C.",
])
def test_same_equivalent_ambiguous_or_exclusive_condition_cannot_remove_a_restriction(following):
    first = "The output current is 12 mA at TA = 25 °C."
    text = first + " " + following
    assert proof_envelope(text, 0, len(first)) == (0, len(text))


def test_components_named_in_predicates_are_not_equated():
    first = "The output current is 12 mA for DEV407."
    following = "The output current is not established for ALT318."
    text = first + " " + following
    assert proof_envelope(text, 0, len(first)) == (0, len(first))
    cat = catalogue("Quel courant de sortie est établi pour DEV407 ?", [source("R001", text, name="Limits.docx")])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert first in result["text"] and following not in result["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


def test_a_predicate_with_the_same_explicit_component_retains_the_limitation():
    first = "The output current is 12 mA for DEV407."
    following = "The output current is not established for DEV407."
    text = first + " " + following
    assert proof_envelope(text, 0, len(first)) == (0, len(text))
