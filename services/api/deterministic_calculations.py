"""Bounded arithmetic on complete, source-bound cells; no spreadsheet evaluation.

The caller selects operands from the revision-pinned catalogue. Neither the LLM
nor a string expression supplies values. This module deliberately supports a
small unit vocabulary and refuses ambiguous operands instead of guessing units,
thousands separators, formula results, or workbook freshness.
"""

from __future__ import annotations

import re
from decimal import Decimal, DecimalException, Inexact, Rounded, localcontext
from typing import Any

MAX_OPERANDS = 64
MAX_VALUE_CHARACTERS = 80
PRECISION = 40

# dimension, factor to the base unit, offset after multiplication. Case matters:
# mV and MV, or m and M, are not interchangeable.
UNITS = {
    "": ("number", "1", "0"),
    "V": ("voltage", "1", "0"), "mV": ("voltage", "0.001", "0"), "kV": ("voltage", "1000", "0"),
    "A": ("current", "1", "0"), "mA": ("current", "0.001", "0"), "µA": ("current", "0.000001", "0"),
    "W": ("power", "1", "0"), "mW": ("power", "0.001", "0"), "kW": ("power", "1000", "0"),
    "Hz": ("frequency", "1", "0"), "kHz": ("frequency", "1000", "0"), "MHz": ("frequency", "1000000", "0"),
    "Ω": ("resistance", "1", "0"), "kΩ": ("resistance", "1000", "0"), "MΩ": ("resistance", "1000000", "0"),
    "s": ("time", "1", "0"), "ms": ("time", "0.001", "0"), "µs": ("time", "0.000001", "0"),
    "min": ("time", "60", "0"), "h": ("time", "3600", "0"),
    "m": ("length", "1", "0"), "mm": ("length", "0.001", "0"), "cm": ("length", "0.01", "0"), "km": ("length", "1000", "0"),
    "Pa": ("pressure", "1", "0"), "kPa": ("pressure", "1000", "0"), "MPa": ("pressure", "1000000", "0"), "bar": ("pressure", "100000", "0"),
    "K": ("temperature", "1", "0"), "°C": ("temperature", "1", "273.15"),
}
UNIT_ALIASES = {"uA": "µA", "μA": "µA", "us": "µs", "μs": "µs", "ohm": "Ω", "ohms": "Ω"}
UNIT_PATTERN = "(?:" + "|".join(re.escape(unit) for unit in sorted(set(UNITS) | set(UNIT_ALIASES), key=len, reverse=True) if unit) + ")"
NUMBER_PATTERN = r"[+\-−]?(?:[0-9]+(?:[.,][0-9]+)?)(?:[eE][+\-]?[0-9]{1,2})?"
QUANTITY = re.compile(rf"\s*(?P<value>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?\s*")


class CalculationRefusal(ValueError):
    """Expected refusal with a machine-readable cause and no invented result."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def decimal_text(value: Decimal) -> str:
    """Plain, bounded result, with zero preserved (including a zero difference)."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def parse_quantity(text: str, *, typed_number: bool = False) -> tuple[Decimal, str]:
    if not isinstance(text, str) or len(text) > MAX_VALUE_CHARACTERS:
        raise CalculationRefusal("numeric_value_limit", "La valeur dépasse la limite du calcul déterministe.")
    match = QUANTITY.fullmatch(text)
    if match is None:
        raise CalculationRefusal("not_a_single_quantity", "Une entrée n'est pas une valeur numérique unique avec une unité reconnue.")
    token = match["value"].replace("−", "-")
    # The XLSX numeric field is canonical and typed. In a text cell, 1,020 or
    # 1.020 may instead use a thousands separator; 0.125 is unambiguous here.
    if not typed_number and re.fullmatch(r"[+\-]?[1-9][0-9]*[.,][0-9]{3}", token):
        raise CalculationRefusal("ambiguous_decimal_separator", "Le séparateur décimal d'une valeur textuelle est ambigu.")
    if len(re.sub(r"\D", "", token)) > 24:
        raise CalculationRefusal("numeric_value_limit", "Une entrée comporte trop de chiffres pour ce calcul borné.")
    try:
        value = Decimal(token.replace(",", "."))
    except DecimalException as error:
        raise CalculationRefusal("invalid_number", "Une entrée numérique n'est pas interprétable.") from error
    if not value.is_finite() or abs(value.adjusted()) > 24:
        raise CalculationRefusal("numeric_value_limit", "L'ordre de grandeur dépasse la limite du calcul déterministe.")
    unit = match["unit"] or ""
    return value, UNIT_ALIASES.get(unit, unit)


def cell_operand(reference: dict[str, Any]) -> dict[str, Any]:
    """Read only the complete, authorized value field, never cell_facts as data."""
    if reference.get("kind") != "cell":
        raise CalculationRefusal("cell_operand_required", "Ce calcul exige des cellules explicitement référencées.")
    facts = reference["cell_facts"]
    if facts.get("formula_present") and not facts.get("cached_present"):
        raise CalculationRefusal("formula_cache_absent", "Une formule n'a pas de cache source ; son résultat reste indisponible.")
    value = next((field for field in reference["fields"] if field["field"] == "value"), None)
    if value is None or not value.get("complete"):
        raise CalculationRefusal("incomplete_operand", "Une valeur nécessaire au calcul est absente ou partiellement autorisée.")
    kind = facts.get("cached_value_kind") if facts.get("formula_present") else facts.get("value_kind", facts.get("data_type"))
    if kind in {"boolean", "date", "excel_date", "datetime", "time", "duration", "error", "empty"} or facts.get("data_type") in {"boolean", "error"}:
        raise CalculationRefusal("nonnumeric_cell_type", "Le type d'une cellule n'est pas admissible à ce calcul.")
    number, unit = parse_quantity(value["text"], typed_number=kind == "number")
    return {"reference_id": reference["id"], "source_ids": list(reference["source_ids"]),
            "document_id": reference["document_id"], "version_id": reference.get("version_id"),
            "extraction_revision_id": reference.get("extraction_revision_id"),
            "address": facts["address"], "unit_id": reference["locator"].get("unit_id"),
            "raw_text": value["text"], "value": decimal_text(number), "unit": unit,
            "value_origin": facts.get("value_origin", "literal"),
            "cache_freshness": facts.get("cache_freshness", "not_applicable"),
            "segments": value.get("segments", [])}


def _convert(value: Decimal, source: str, target: str) -> Decimal:
    if source not in UNITS or target not in UNITS or UNITS[source][0] != UNITS[target][0]:
        raise CalculationRefusal("incompatible_units", "Les unités ne sont pas compatibles dans le calcul demandé.")
    _, factor, offset = UNITS[source]
    _, target_factor, target_offset = UNITS[target]
    return (value * Decimal(factor) + Decimal(offset) - Decimal(target_offset)) / Decimal(target_factor)


def explicit_unit(reference: dict[str, Any], operand: dict[str, Any]) -> dict[str, Any]:
    """Read a unit cell explicitly named by the question, never an adjacent guess."""
    if reference.get("kind") != "cell" or reference["id"] == operand["reference_id"]:
        raise CalculationRefusal("unit_cell_required", "La cellule d'unité doit être distincte de la valeur.")
    facts = reference["cell_facts"]
    if facts.get("formula_present") and not facts.get("cached_present"):
        raise CalculationRefusal("formula_cache_absent", "La cellule d'unité n'a pas de cache source disponible.")
    if (reference["document_id"] != operand["document_id"] or reference.get("version_id") != operand["version_id"]
            or reference.get("extraction_revision_id") != operand["extraction_revision_id"]
            or reference["locator"].get("unit_id") != operand["unit_id"]):
        raise CalculationRefusal("unit_cell_scope_mismatch", "Valeur et unité ne désignent pas la même feuille et révision.")
    value = next((field for field in reference["fields"] if field["field"] == "value"), None)
    if value is None or not value.get("complete"):
        raise CalculationRefusal("incomplete_unit", "L'unité source n'est pas entièrement autorisée et disponible.")
    raw = value["text"].strip()
    unit = UNIT_ALIASES.get(raw, raw)
    if not unit or unit not in UNITS:
        raise CalculationRefusal("unit_not_supported", "La cellule d'unité ne contient pas une unité unique prise en charge.")
    if operand["unit"] and operand["unit"] != unit:
        raise CalculationRefusal("conflicting_source_units", "La valeur et la cellule d'unité déclarent des unités différentes.")
    return {"reference_id": reference["id"], "source_ids": list(reference["source_ids"]),
            "address": facts["address"], "raw_text": value["text"], "unit": unit,
            "document_id": reference["document_id"], "version_id": reference.get("version_id"),
            "extraction_revision_id": reference.get("extraction_revision_id"),
            "segments": value.get("segments", []), "value_origin": facts.get("value_origin", "literal"),
            "cache_freshness": facts.get("cache_freshness", "not_applicable")}


def calculate(operation: str, references: list[dict[str, Any]], target_unit: str | None = None,
              *, unit_reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Perform one whitelisted operation; return inputs, provenance and rounding.

    Subtraction/division preserve question operand order. A ratio is dimensionless
    only when both inputs have the same dimension. Spreadsheet formulas are never
    interpreted. A result based on cached values inherits their unknown freshness.
    """
    if operation not in {"sum", "mean", "difference", "ratio", "convert"}:
        raise CalculationRefusal("unsupported_operation", "L'opération demandée n'appartient pas aux calculs pris en charge.")
    if not 1 <= len(references) <= MAX_OPERANDS:
        raise CalculationRefusal("operand_count_limit", "Le nombre d'entrées du calcul dépasse la limite autorisée.")
    if len({reference["id"] for reference in references}) != len(references):
        raise CalculationRefusal("duplicate_operand", "Une même cellule ne peut être comptée deux fois implicitement.")
    if operation in {"difference", "ratio"} and len(references) != 2 or operation == "convert" and len(references) != 1:
        raise CalculationRefusal("operand_count_mismatch", "Le nombre d'entrées ne correspond pas à l'opération demandée.")
    inputs = [cell_operand(reference) for reference in references]
    unit_evidence = None
    if unit_reference is not None:
        if operation != "convert":
            raise CalculationRefusal("unit_binding_operation", "L'unité séparée est prise en charge pour une conversion explicite seulement.")
        unit_evidence = explicit_unit(unit_reference, inputs[0])
        inputs[0]["unit"] = unit_evidence["unit"]
    unit = inputs[0]["unit"]
    if operation != "convert" and any(UNITS[item["unit"]][0] == "temperature" for item in inputs):
        raise CalculationRefusal("temperature_arithmetic_unsupported", "Seule la conversion explicite des températures est prise en charge.")
    with localcontext() as context:
        context.prec = PRECISION
        context.clear_flags()
        try:
            if operation == "convert":
                target = UNIT_ALIASES.get(target_unit or "", target_unit or "")
                if not target or not unit:
                    raise CalculationRefusal("unit_missing", "La conversion exige une unité source et une unité cible explicites.")
                result = _convert(Decimal(inputs[0]["value"]), unit, target)
                unit = target
            else:
                numbers = [_convert(Decimal(item["value"]), item["unit"], unit) for item in inputs]
                if operation == "sum":
                    result = sum(numbers, Decimal(0))
                elif operation == "mean":
                    result = sum(numbers, Decimal(0)) / Decimal(len(numbers))
                elif operation == "difference":
                    result = numbers[0] - numbers[1]
                else:
                    if numbers[1] == 0:
                        raise CalculationRefusal("division_by_zero", "Le dénominateur est nul ; aucun rapport numérique n'est publié.")
                    result, unit = numbers[0] / numbers[1], ""
        except DecimalException as error:
            raise CalculationRefusal("arithmetic_failure", "Le calcul dépasse les limites numériques configurées.") from error
        rounded = bool(context.flags[Inexact] or context.flags[Rounded])
    if not result.is_finite() or abs(result.adjusted()) > 48:
        raise CalculationRefusal("numeric_result_limit", "Le résultat dépasse la limite du calcul déterministe.")
    provenance = [*inputs, *([unit_evidence] if unit_evidence else [])]
    return {"operation": operation, "inputs": inputs, "unit_reference": unit_evidence,
            "value": decimal_text(result), "unit": unit,
            "precision": PRECISION, "rounded": rounded,
            "source_ids": list(dict.fromkeys(source for item in provenance for source in item["source_ids"])),
            "uses_formula_cache": any(item["value_origin"] == "formula_cache" for item in provenance),
            "formula_evaluated": False}


def calculation_text(result: dict[str, Any]) -> str:
    """Display the exact operands and operation used, without implying freshness."""
    labels = {"sum": "Somme", "mean": "Moyenne arithmétique", "difference": "Différence (première entrée moins seconde)",
              "ratio": "Rapport (première entrée divisée par la seconde)", "convert": "Conversion"}
    entries = "; ".join(f"{item['address']} = {item['raw_text']}" for item in result["inputs"])
    if result.get("unit_reference"):
        evidence = result["unit_reference"]
        entries += f" ; unité source {evidence['address']} = {evidence['raw_text']}"
    relation = "≈" if result["rounded"] else "="
    text = f"Calcul déterministe — {labels[result['operation']]} : {entries} ; résultat {relation} {result['value']}"
    if result["unit"]:
        text += " " + result["unit"]
    text += "."
    if result["rounded"]:
        text += f" Résultat arrondi à {result['precision']} chiffres significatifs."
    if result["uses_formula_cache"]:
        text += " Entrées issues de caches enregistrés de fraîcheur inconnue ; aucune formule du classeur n'a été exécutée."
    return text
