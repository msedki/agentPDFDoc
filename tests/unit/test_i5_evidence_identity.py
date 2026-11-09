"""One citation may contain several quantities; IDs alone cannot cover a need."""

import copy

import pytest

from services.api.evidence_coverage import _matches_obligation, _relation_key


def fact():
    return {"document_id": "doc", "version_id": "v1", "subjects": ["AB12"], "quantity": "voltage",
            "property": "supply", "kind": "interval", "values": ["2.2", "4.8"], "unit": "V",
            "role": "recommended", "bound_role": None, "condition": "at 25 °C",
            "supply_configuration": "single", "polarity": None, "reference_ids": ["R001"]}


def obligation():
    return {"quantity": "voltage", "property": "supply", "kind": "interval", "role": "recommended",
            "document_id": "doc", "subject": "AB12", "supply_configuration": "single",
            "requested_condition": None, "point_conditions": [], "reference_ids": ["R001"]}


@pytest.mark.parametrize("field,value", [("quantity", "temperature"), ("role", "maximum"),
                                         ("supply_configuration", "dual"), ("subject", "AB21"),
                                         ("document_id", "other"), ("property", "bus")])
def test_common_reference_does_not_cover_a_different_obligation(field, value):
    need = obligation()
    need[field] = value
    assert not _matches_obligation(fact(), {"R001"}, need)


def test_true_matching_relation_stays_covered_and_missing_dependency_does_not():
    assert _matches_obligation(fact(), {"R001"}, obligation())
    assert not _matches_obligation(fact(), {"R001", "R002"}, obligation())


def test_point_value_does_not_cover_an_interval_with_the_same_source():
    point = fact() | {"kind": "point", "values": ["2.2"]}
    assert not _matches_obligation(point, {"R001"}, obligation())


@pytest.mark.parametrize("field,value", [("supply_configuration", "dual"), ("polarity", "symmetric"),
                                         ("kind", "point"), ("condition", "at 75 °C")])
def test_different_configurations_and_conditions_cannot_share_a_coverage_atom(field, value):
    other = copy.deepcopy(fact())
    other[field] = value
    assert _relation_key(other) != _relation_key(fact())
