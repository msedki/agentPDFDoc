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


def condition_measures(text):
    """Recognize explicit point conditions without guessing a variable name.

    ``at 25 °C`` is a temperature condition; it is not silently called ambient
    temperature. ``TJ = 25 °C`` keeps TJ distinct from TA. Unit conversion for
    matching uses the same checked Decimal registry as answer calculations.
    """
    measures = []
    for match in CONDITION_MEASURE.finditer(text):
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
