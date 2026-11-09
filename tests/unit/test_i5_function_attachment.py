"""A relative function must attach to the requested literal antecedent.

Invented phrases, named tokenizer double, real contract and renderer. These
checks do not qualify native inference or a general semantic parser.
"""

import pytest
from test_enhanced_answers import catalogue, render
from test_i5_obligation_publication import source


@pytest.mark.parametrize(("question", "text"), [
    ("What is the purpose of amplifier?",
     "DEV728 has debounce, which prevents repeated alarms, and an amplifier."),
    ("What is the purpose of hysteresis?",
     "DEV728 has an alarm gate, which prevents repeated switching of hysteresis."),
    ("What is the purpose of hysteresis?",
     "DEV728 has hysteresis and a separate alarm gate, which prevents repeated switching."),
    ("À quoi sert son hystérésis ?",
     "DEV728 possède une hystérésis et un filtre, qui permet de limiter les alarmes."),
])
def test_another_antecedents_function_does_not_cover_requested_target(question, text):
    cat = catalogue(question, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] != "covered"
    assert not result["answer_contract"]["matched_qualitative_relations"]
    assert not any(item["covered"] for item in result["answer_contract"]["obligations"])
    assert cat.model_view()["reference_ids"] == []
    assert text == cat.references[0]["text"]
    assert cat.verify_rendered(result)["status"] == "passed"


@pytest.mark.parametrize(("question", "text", "qualification"), [
    ("What is the purpose of debounce?",
     "DEV728 has debounce, which prevents repeated alarms.", "prevents repeated alarms."),
    ("What is the purpose of hysteresis?",
     "DEV728 has approximately 3 units of hysteresis, which prevents repeated switching.", "prevents repeated switching."),
    ("À quoi sert son hystérésis ?",
     "DEV728 possède une hystérésis, qui permet de limiter les alarmes.", "permet de limiter les alarmes."),
    ("What is the purpose of amplifier?",
     "DEV728 has debounce, which prevents repeated alarms, and an amplifier, which reduces noise.", "reduces noise."),
])
def test_explicit_relative_function_keeps_its_own_antecedent(question, text, qualification):
    cat = catalogue(question, [source("R001", text)])
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert all(item["covered"] for item in result["answer_contract"]["obligations"])
    assert result["answer_contract"]["matched_qualitative_relations"][0]["qualification"] == qualification
    assert text in result["text"]
    assert result["source_ids"] == ["S001"]
    assert cat.verify_rendered(result)["status"] == "passed"
