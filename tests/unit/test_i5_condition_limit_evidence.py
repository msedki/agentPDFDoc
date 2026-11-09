"""Conditional limits retain literal evidence without proving a missing value.

These are bounded catalogue/render checks with the existing character tokenizer
double. They exercise no native extraction, OCR or generation model.
"""

import copy

import pytest
from test_enhanced_answers import catalogue, excerpt, render

from services.api.answer_contract import relation_supports_obligation
from services.api.errors import ApiError


def source(text, *, identifier="R001", complete=True, method="native", quality="native"):
    result = excerpt(identifier, text, name="DEV728.pdf", method=method)
    result.update(source_span_complete=complete, version_id="v1", generation_id="g1",
                  extraction_revision_id="e1")
    if quality is not None:
        result["source_quality"] = {"state": quality, "text_length": len(text), "intervals": [],
                                    "reading_ids": [], "reasons": []}
    return result


def question(point="95 °C"):
    return f"Quelle est la tension nominale de sortie du DEV728 à {point} ?"


def diagnostics(cat):
    return [item for item in cat.assess()["rejected_relations"]
            if "requested_condition_outside_range" in item["reasons"]]


@pytest.mark.parametrize("point", ["95 °C", "368.15 K"])
def test_outside_range_is_mandatory_cited_diagnostic_with_original_offsets(point):
    prefix = "DEV728 is a sensor. "
    sentence = "DEV728 guaranteed operating temperature range: -12 ° C to 68 ° C."
    ref = source(prefix + sentence + " The package is blue.")
    cat = catalogue(question(point), [ref])

    view = cat.model_view()
    assert view["reference_ids"] == ["R001"]
    assert view["payload"]["question_contract"]["required_reference_ids"] == ["R001"]
    assert view["payload"]["reference_catalogue"][0]["text"] == sentence
    result = render(cat)  # Omitting the range cannot erase its citation.
    assert result["effective_plan"]["references"] == ["R001"]
    assert result["answer_contract"]["status"] == "partial"
    assert result["citation_spans"] and sentence in result["text"]
    assert "hors" in result["text"] and "extrapol" in result["text"]
    assert "package is blue" not in result["text"]
    relation, = diagnostics(cat)
    assert relation["unit"] == "°C" and relation["values"] == ["-12", "68"]
    assert relation["quote"] == ref["text"][relation["source_start"]:relation["source_end"]] == sentence
    assert relation["source_start"] == len(prefix)
    assert all(not item["covered"] and not relation_supports_obligation(relation, item)
               for item in result["answer_contract"]["obligations"])
    assert not result["answer_contract"]["matched_relations"]
    assert cat.verify_rendered(result)["status"] == "passed"

    changed = copy.deepcopy(result)
    changed["text"] = changed["text"].replace("68 ° C", "96 ° C")
    with pytest.raises(ApiError):
        cat.verify_rendered(changed)


@pytest.mark.parametrize("text", [
    "ALT421 guaranteed operating temperature range: -12 °C to 68 °C.",
    "DEV728 guaranteed absolute maximum temperature range: -12 °C to 68 °C.",
    "DEV728 guaranteed operating storage temperature range: -12 °C to 68 °C.",
    "DEV728 guaranteed operating junction temperature range: -12 °C to 68 °C.",
    "DEV728 temperature range: -12 °C to 68 °C.",
    "DEV728 approximate guaranteed operating temperature range: -12 °C to 68 °C.",
    "DEV728 guaranteed operating temperature range is not -12 °C to 68 °C.",
    "DEV728 guaranteed operating temperature range: 68 °C to -12 °C.",
    "DEV728 guaranteed operating temperature range: -12 °C to 68 °C at VCC = 3.3 V.",
    "DEV728 guaranteed operating temperature range: -12 °C to 68 °C or -12 °C to 108 °C.",
])
def test_unrelated_unqualified_or_ambiguous_ranges_never_explain_the_limit(text):
    cat = catalogue(question(), [source(text)])
    assert diagnostics(cat) == []
    assert cat.model_view()["reference_ids"] == []
    assert render(cat, ["R001"])["citation_spans"] == []


@pytest.mark.parametrize("point", ["-12 °C", "20 °C", "68 °C", "341.15 K"])
def test_inside_and_boundary_points_do_not_establish_or_refute_a_missing_value(point):
    cat = catalogue(question(point), [source("DEV728 operating temperature range: -12 °C to 68 °C.")])
    assert diagnostics(cat) == []
    result = render(cat, ["R001"])
    assert result["answer_contract"]["status"] == "partial"
    assert result["citation_spans"] == []


@pytest.mark.parametrize(("complete", "method", "quality"), [
    (False, "native", "native"),
    (True, "ocr", "unavailable"),
    (True, "ocr", None),
])
def test_unverified_or_incomplete_source_cannot_become_a_limit(complete, method, quality):
    cat = catalogue(question(), [source("DEV728 operating temperature range: -12 °C to 68 °C.",
                                        complete=complete, method=method, quality=quality)])
    assert diagnostics(cat) == []
    assert render(cat, ["R001"])["citation_spans"] == []


def test_named_temperature_variable_must_match_without_ambient_junction_substitution():
    text = "DEV728 guaranteed operating temperature TJ range: -12 °C to 68 °C."
    cat = catalogue(question("TA = 95 °C"), [source(text)])
    assert diagnostics(cat) == []
    cat = catalogue(question("TJ = 95 °C"), [source(text)])
    assert diagnostics(cat) and render(cat)["citation_spans"]


def test_differing_ranges_in_one_revision_do_not_arbitrarily_select_a_limit():
    refs = [source("DEV728 operating temperature range: -12 °C to 68 °C."),
            source("DEV728 operating temperature range: -12 °C to 108 °C.", identifier="R002")]
    cat = catalogue(question(), refs)
    assert diagnostics(cat) == []
    assert cat.model_view()["reference_ids"] == []


def test_proved_value_at_requested_point_prevents_a_misleading_limit_diagnostic():
    refs = [source("DEV728 operating temperature range: -12 °C to 68 °C."),
            source("DEV728 nominal output voltage: 1.7 V at 95 °C.", identifier="R002")]
    cat = catalogue(question(), refs)
    assert diagnostics(cat) == []
    result = render(cat)
    assert result["answer_contract"]["status"] == "covered"
    assert result["effective_plan"]["references"] == ["R002"]


def test_condition_range_uses_the_shared_dimension_registry_beyond_temperature():
    text = "DEV728 guaranteed operating pressure range: 1 bar to 3 bar."
    cat = catalogue(question("4 bar"), [source(text)])
    relation, = diagnostics(cat)
    assert relation["quantity"] == "pressure" and relation["requested_quantity"] == "voltage"
    assert relation["requested_point_condition"]["value"] == "400000"
    result = render(cat)
    assert result["answer_contract"]["status"] == "partial"
    assert text in result["text"] and cat.verify_rendered(result)["status"] == "passed"


def test_dual_supply_amplitudes_do_not_refute_an_in_range_negative_point():
    text = "DEV728 dual operating voltage range: ±1.5 V to ±6 V."
    cat = catalogue("What is the nominal current of DEV728 at -5 V?", [source(text)])
    assert diagnostics(cat) == []
    assert cat.model_view()["reference_ids"] == []


@pytest.mark.parametrize("operator", ["<", "≤", "±"])
def test_uninterpreted_lower_bound_operator_cannot_become_an_exact_limit(operator):
    text = f"DEV728 guaranteed operating temperature range: {operator} -12 °C to 68 °C."
    cat = catalogue(question("-20 °C"), [source(text)])
    assert diagnostics(cat) == []
    assert render(cat, ["R001"])["citation_spans"] == []


def test_restriction_in_the_next_sentence_cannot_disappear_from_the_range_scope():
    text = ("DEV728 operating temperature range: -12 °C to 68 °C. "
            "Only the laboratory prototype supports this range.")
    cat = catalogue(question(), [source(text)])
    assert diagnostics(cat) == []
    result = render(cat, ["R001"])
    assert result["citation_spans"] == []
    assert "hors" not in result["text"]
