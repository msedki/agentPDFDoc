"""Explicit source point conditions shared by obligations and literal scopes.

This is the existing bounded point grammar, with exact Decimal unit conversion.
Ranges and unknown symbols are not inferred as scalar test points.
"""

import re
from decimal import Decimal, localcontext

from .deterministic_calculations import (
    NUMBER_PATTERN,
    UNIT_PATTERN,
    UNITS,
    CalculationRefusal,
    decimal_text,
    parse_quantity,
)

CONDITION_MEASURE = re.compile(
    rf"(?<!\w)(?:(?i:at|à|a|when|for|pour|sous)\s+"
    rf"(?:(?P<prefixed_symbol>[A-Za-z][A-Za-z0-9_+−-]{{0,15}})\s*=\s*)?"
    rf"|(?P<symbol>[A-Za-z][A-Za-z0-9_+−-]{{0,15}})\s*=\s*)"
    rf"(?:(?P<alias>[A-Za-z][A-Za-z0-9_+−-]{{0,15}})\s*=\s*)?"
    rf"(?P<value>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})(?![\w/])")
EXCLUDED_POINT_PREFIX = re.compile(
    r"\b(?:unless|except(?:\s+(?:at|when|if|for))?|without|"
    r"sauf(?:\s+(?:[àa]|si|quand|lorsque))?|sans(?:\s+que)?|"
    r"not(?:\s+(?:at|when|for))?|pas(?:\s+[àa])?)\s*$", re.IGNORECASE)
POINT_COORDINATION = re.compile(r"\s*(?:\)|\])?\s*(?:,|and|or|et|ou)\s*(?:\(|\[)?\s*", re.IGNORECASE)


def point_is_excluded(text: str, start: int) -> bool:
    """A directly excluded point is not an asserted test condition.

    ``not established at TA = 25 °C`` still exposes its point: the negation
    belongs to the predicate, and literal scope checks need that location.
    ``unless otherwise noted`` is not interpreted as an excluded numeric point.
    """
    cursor = start
    words: list[str] = []
    # Only three short words can form a prefix in this grammar. Read them
    # backwards without rescanning the entire preceding document per point.
    for index in range(3):
        while cursor and text[cursor - 1].isspace():
            cursor -= 1
        if index == 0 and cursor and text[cursor - 1] in "([":
            cursor -= 1
            while cursor and text[cursor - 1].isspace():
                cursor -= 1
        end = cursor
        while cursor and text[cursor - 1].isalpha() and end - cursor <= 12:
            cursor -= 1
        if cursor == end or end - cursor > 12:
            break
        words.insert(0, text[cursor:end])
        if EXCLUDED_POINT_PREFIX.fullmatch(" ".join(words)) is not None:
            return True
        if cursor and not text[cursor - 1].isspace():
            break
    return False


def _scoped_conditions(text: str):
    previous_end, previous_excluded = 0, False
    for match in CONDITION_MEASURE.finditer(text):
        excluded = point_is_excluded(text, match.start())
        if (previous_excluded
                and POINT_COORDINATION.fullmatch(text[previous_end:match.start()]) is not None):
            excluded = True
        yield match, excluded
        previous_end, previous_excluded = match.end(), excluded


def has_excluded_point_condition(text: str) -> bool:
    return any(excluded for _, excluded in _scoped_conditions(text))


def condition_measures(text, *, excluded=False):
    """Recognize explicit point conditions without guessing a variable name.

    ``at 25 °C`` is a temperature condition; it is not silently called ambient
    temperature. ``TJ = 25 °C`` keeps TJ distinct from TA. Unit conversion for
    matching uses the same checked Decimal registry as answer calculations.
    """
    measures = []
    for match, point_excluded in _scoped_conditions(text):
        if point_excluded != excluded:
            continue
        if re.match(rf"\s*(?:(?i:to|a|à)|[-–—])\s*{NUMBER_PATTERN}", text[match.end():]):
            continue  # a range endpoint is not a separately asserted point
        try:
            value, unit = parse_quantity(match["value"] + " " + match["unit"])
        except CalculationRefusal:
            continue
        dimension, scale, offset = UNITS[unit]
        with localcontext() as context:
            context.prec = 96
            base = decimal_text(value * Decimal(scale) + Decimal(offset))
        symbol = match["prefixed_symbol"] or match["symbol"]
        measures.append({"quantity": dimension, "symbol": symbol.replace("−", "-") if symbol else None,
                         "aliases": [match["alias"].replace("−", "-")] if match["alias"] else [],
                         "value": base, "text": match[0], "start": match.start(), "end": match.end()})
    return measures
