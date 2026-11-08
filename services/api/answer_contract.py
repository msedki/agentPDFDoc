"""Question-aware, bounded coverage checks for the reference-only renderer.

These checks are deliberately narrower than semantic entailment. They establish
explicit cell coverage or recognize a value/range on one source line with its
quantity, unit and role. They never assemble a range from unrelated numbers,
repair OCR by substitution, or infer that an unobserved fact is absent from a
document. Unknown question forms remain ``unassessed`` and keep their excerpts.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from openpyxl.utils.cell import get_column_letter

from services.ingestion.errors import IngestionError
from services.ingestion.office.xlsx import address_coordinates, range_coordinates

from .deterministic_calculations import (
    MAX_OPERANDS,
    NUMBER_PATTERN,
    UNIT_ALIASES,
    UNIT_PATTERN,
    UNITS,
    CalculationRefusal,
    calculate,
    decimal_text,
    parse_quantity,
)

VERIFICATION = "bounded_structural_checks"
LIMITATION = "Contrôles de couverture explicite et de relations locales ; aucune preuve générale de justesse sémantique."
QUANTITIES = {
    "voltage": r"\b(?:tensions?|voltages?|vcc|vdd|vss)\b",
    "current": r"\b(?:courants?|currents?)\b",
    "temperature": r"\b(?:temperature|temperatures)\b",
    "power": r"\b(?:puissances?|power)\b",
    "frequency": r"\b(?:frequences?|frequency|frequencies)\b",
    "resistance": r"\b(?:resistances?|resistors?)\b",
    "pressure": r"\b(?:pressions?|pressures?)\b",
    "time": r"\b(?:durees?|durations?|delays?|delais?|temps|time)\b",
    "length": r"\b(?:longueurs?|lengths?|distances?)\b",
}
# These labels detect compound requirements; they do not establish a semantic
# relation merely because two labels occur somewhere in the same excerpt.
QUANTITY_PROPERTIES = {
    "voltage": {"bus": r"\b(?:bus|vbus)\b", "supply": r"\b(?:alimentation|supply|vdd|vcc)\b",
                "shunt": r"\bshunt\b", "common_mode": r"\b(?:mode commun|common[ -]mode)\b"},
    "current": {"quiescent": r"\b(?:repos|quiescent)\b", "input": r"\b(?:entree|input)\b",
                "output": r"\b(?:sortie|output)\b", "leakage": r"\b(?:fuite|leakage)\b"},
    "temperature": {"ambient": r"\b(?:ambiante?|ambient)\b", "junction": r"\b(?:jonction|junction)\b",
                    "storage": r"\b(?:stockage|storage)\b"},
    "time": {"conversion": r"\bconversion\b", "startup": r"\b(?:demarrage|start[ -]?up)\b",
             "erase": r"\b(?:effacement|erase)\b", "read": r"\b(?:lecture|read)\b"},
}
ROLES = {
    "absolute_maximum": r"\b(?:absolute\s+maximum|absolut[es]?\s+max|maxim\w*\s+absolu\w*|limites?\s+absolu\w*)\b",
    "operating": r"\b(?:operating|recommended|recommande\w*|fonctionnement|admissible\w*)\b",
    "typical": r"\b(?:typical|typically|typique\w*|typ\.)",
    "characterization": r"\b(?:test\s+conditions?|conditions?\s+d['’ ]essai|characterization|caracterisation|courbes?|curves?|measured\s+at)\b",
}
CELL = r"\$?[A-Z]{1,3}\$?[1-9][0-9]{0,6}"
CELL_RANGE = re.compile(rf"(?<!\w)({CELL})\s*:\s*({CELL})(?!\w)", re.IGNORECASE)
CELL_SINGLE = re.compile(rf"(?<!\w)({CELL})(?!\w)", re.IGNORECASE)
CELL_LANGUAGE = re.compile(r"\b(?:cellules?|cells?|valeurs?|values?|plage|range|somme|sum|moyenne|mean|difference|rapport|ratio|convert\w*|conversion)\b")
SCOPE_READ_LANGUAGE = re.compile(
    r"\b(?:restitue|restituer|restituez|lis|lire|read|show|list|liste|donne)\s+"
    r"(?:(?:les|la|le|the|des|de|all)\s+)*(?:selection|selected|cellules?|cells?|valeurs?|values?|plage|range|contenu|contents?)\b"
    r"|\b(?:valeurs?|values?|contenu|contents?)\s+(?:des?\s+)?(?:cellules?\s+selectionnees?|selection|selected\s+cells?)\b")
UNIT_LANGUAGE = re.compile(r"\b(?:unites?|units?)\b")
INTERVAL_LANGUAGE = re.compile(r"\b(?:plages?|intervalles?|ranges?|bornes?|minimum\s+et\s+maximum|min\s+et\s+max)\b")
COMPARISON_LANGUAGE = re.compile(r"\b(?:compar\w*|versus|difference\s+entre)\b")
MAPPING_LANGUAGE = re.compile(r"\b(?:adresse|address|mapping|correspondance|configuration|configurations|code|codes)\b")
CALCULATIONS = (
    ("convert", r"\b(?:convert|converts|converting|convertis|convertir|convertissez)\b"),
    ("mean", r"\b(?:moyenne|mean|average)\b"),
    ("sum", r"\b(?:somme|sum|additionne\w*)\b"),
    ("difference", r"\b(?:soustra\w*|difference)\b"),
    ("ratio", r"\b(?:rapport|ratio|divis\w*)\b"),
)
RANGE_VALUE = re.compile(
    rf"(?<![\w.,])(?P<low>{NUMBER_PATTERN})\s*(?P<low_unit>{UNIT_PATTERN})?\s*"
    rf"(?:\bto\b|\ba\b|à|[-–—…]|\.\.)\s*"
    rf"(?P<high>{NUMBER_PATTERN})\s*(?P<high_unit>{UNIT_PATTERN})(?!\w)", re.IGNORECASE)
# A labelled min/max relation must stay on one source line. Separate blocks or
# unlabelled table columns are not stitched into a fact by this checker.
LABELLED_RANGE = re.compile(
    rf"\b(?:min(?:imum)?)[.\s:=|]*(?P<low>{NUMBER_PATTERN})\s*(?P<low_unit>{UNIT_PATTERN})?"
    rf"[^\n]{{0,40}}?\b(?:max(?:imum)?)[.\s:=|]*(?P<high>{NUMBER_PATTERN})\s*(?P<high_unit>{UNIT_PATTERN})(?!\w)",
    re.IGNORECASE)
MEASURE = re.compile(rf"(?<![\w.,])(?P<value>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})(?!\w)")
AMBIGUOUS_ZERO = re.compile(r"(?<!\w)[Oo]\s*(?:mV|kV|V|mA|A)(?!\w)")
CODE = re.compile(r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|[01]{7,})\b")
CONFIGURATION = re.compile(r"(?<!\w)([A-Za-z][A-Za-z0-9_]{0,15})\s*=\s*([A-Za-z0-9_]+)(?!\w)")
MAPPING_RELATION = re.compile(
    r"(?<!\w)(?P<key>[A-Za-z][A-Za-z0-9_]{0,15})\s*=\s*(?P<value>[A-Za-z0-9_]+)\s*"
    r"(?:->|=>|→|[:,;])\s*(?:(?:I2C\s+)?(?:address|adresse|code)\s*[:=]?\s*)?"
    r"(?P<code>0[xX][0-9a-fA-F]+|0[bB][01]+|[01]{7,})(?!\w)", re.IGNORECASE)
SUBJECT = re.compile(r"(?<!\w)[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*(?!\w)")
NOT_SUBJECTS = {"i2c", "i3c", "rs232", "rs485", "usb2", "usb3"}


def folded(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))


def reference_text(reference: dict[str, Any]) -> str:
    if reference["kind"] == "cell":
        return "\n".join(field["text"] for field in reference["fields"] if field["field"] == "value")
    return reference["text"]


def _role(text: str) -> str | None:
    normalized = folded(text)
    return next((role for role, pattern in ROLES.items() if re.search(pattern, normalized)), None)


def _contains_subject(text: str, subject: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", text, re.IGNORECASE) is not None


def _addresses(question: str, *, enabled: bool) -> tuple[list[str], list[str]]:
    requested: list[str] = []
    failures: list[str] = []
    consumed = []
    for match in CELL_RANGE.finditer(question):
        consumed.append(match.span())
        reference = match[1].replace("$", "").upper() + ":" + match[2].replace("$", "").upper()
        try:
            row1, column1, row2, column2 = range_coordinates(reference)
        except IngestionError:
            failures.append("invalid_cell_range")
            continue
        if (row2 - row1 + 1) * (column2 - column1 + 1) > MAX_OPERANDS:
            failures.append("cell_request_limit")
            continue
        requested.extend(f"{get_column_letter(column)}{row}" for row in range(row1, row2 + 1)
                         for column in range(column1, column2 + 1))
    if enabled:
        for match in CELL_SINGLE.finditer(question):
            if any(low <= match.start() < high for low, high in consumed):
                continue
            address = match[1].replace("$", "").upper()
            try:
                address_coordinates(address)
            except IngestionError:
                continue
            requested.append(address)
    if len(requested) > MAX_OPERANDS:
        failures.append("cell_request_limit")
        requested = requested[:MAX_OPERANDS]
    if len(requested) != len(set(requested)):
        failures.append("duplicate_cell_operand")
    return list(dict.fromkeys(requested)), list(dict.fromkeys(failures))


def _operation(question: str) -> tuple[str | None, str | None]:
    normalized = folded(question)
    operation = next((name for name, pattern in CALCULATIONS if re.search(pattern, normalized)), None)
    target = None
    matches = list(re.finditer(rf"\b(?:en|into|to)\s+({UNIT_PATTERN})(?!\w)", question))
    # "Conversion time" is a measured property, not an instruction to do
    # arithmetic. A nominal unit-conversion request needs an explicit target;
    # verb requests may still be classified and then refused for a missing unit.
    if operation is None and matches and re.search(r"\bconversion\b", normalized):
        operation = "convert"
    if operation == "convert" and matches:
        target = matches[-1][1]
    return operation, target


def _quantity_lines(reference: dict[str, Any], quantity: str, requested_role: str | None, subjects: tuple[str, ...]):
    """Yield complete local relations without rewriting their quoted evidence."""
    raw = reference_text(reference)
    for line in raw.splitlines():
        if not re.search(QUANTITIES[quantity], folded(line)):
            continue
        role = _role(line)
        if requested_role and role != requested_role or role == "characterization" and requested_role != role:
            continue
        named = [subject for subject in subjects if _contains_subject(line, subject)
                 or _contains_subject(reference.get("document_name", ""), subject)]
        # A component elsewhere in the same complete excerpt can provide its
        # heading; a name from another reference cannot.
        if subjects and not named:
            named = [subject for subject in subjects if _contains_subject(raw, subject)]
        for pattern in (RANGE_VALUE, LABELLED_RANGE):
            match = pattern.search(line)
            if match is None:
                continue
            try:
                low, low_unit = parse_quantity(match["low"] + " " + (match["low_unit"] or match["high_unit"]))
                high, high_unit = parse_quantity(match["high"] + " " + match["high_unit"])
            except CalculationRefusal:
                continue
            if UNITS[low_unit][0] != quantity or UNITS[high_unit][0] != quantity or low_unit != high_unit or low > high:
                continue
            yield {"reference_id": reference["id"], "document_id": reference["document_id"],
                   "source_ids": reference["source_ids"], "subjects": named, "kind": "interval",
                   "quantity": quantity, "role": role, "values": [decimal_text(low), decimal_text(high)], "unit": high_unit,
                   "label": folded(line[:match.start()]).strip(" :;|="), "condition": line[match.end():].strip(), "quote": line}
            break
        else:
            measurements = []
            for match in MEASURE.finditer(line):
                try:
                    value, unit = parse_quantity(match[0])
                except CalculationRefusal:
                    continue
                if UNITS[unit][0] == quantity:
                    measurements.append((match, value, unit))
            if len(measurements) == 1:
                match, value, unit = measurements[0]
                yield {"reference_id": reference["id"], "document_id": reference["document_id"],
                       "source_ids": reference["source_ids"], "subjects": named, "kind": "value",
                       "quantity": quantity, "role": role, "values": [decimal_text(value)], "unit": unit,
                       "label": folded(line[:match.start()]).strip(" :;|="), "condition": line[match.end():].strip(), "quote": line}


def _conflicting_relations(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts = []
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for fact in facts:
        key = (fact["document_id"], fact["quantity"], fact["role"], fact["label"], fact["condition"], fact["kind"])
        groups.setdefault(key, []).append(fact)
    for group in groups.values():
        values = {(tuple((Decimal(value) * Decimal(UNITS[fact["unit"]][1]) + Decimal(UNITS[fact["unit"]][2])).normalize()
                         for value in fact["values"]), UNITS[fact["unit"]][0]) for fact in group}
        if len(values) > 1:
            conflicts.append({"requirement": "same_label_conflicting_values",
                              "reference_ids": list(dict.fromkeys(fact["reference_id"] for fact in group)),
                              "quotes": [fact["quote"] for fact in group]})
    return conflicts


@dataclass
class AnswerContract:
    question: str
    mode: str
    scope: dict[str, Any] = field(default_factory=dict)
    cell_context: bool = False
    kind: str = field(init=False)
    quantity: str | None = field(init=False)
    requested_role: str | None = field(init=False)
    requested_cells: list[str] = field(init=False)
    operation: str | None = field(init=False)
    target_unit: str | None = field(init=False)
    subjects: tuple[str, ...] = field(init=False)
    parse_failures: list[str] = field(init=False)
    requested_field: str = field(init=False)
    configurations: list[tuple[str, str]] = field(init=False)
    requested_properties: list[str] = field(init=False)
    scope_read_requested: bool = field(init=False)
    unit_requested: bool = field(init=False)

    def __post_init__(self):
        normalized = folded(self.question)
        quantities = [quantity for quantity, pattern in QUANTITIES.items() if re.search(pattern, normalized)]
        self.quantity = quantities[0] if len(quantities) == 1 else None
        self.requested_properties = [name for name, pattern in QUANTITY_PROPERTIES.get(self.quantity or "", {}).items()
                                     if re.search(pattern, normalized) or self.quantity == "voltage" and name == "supply"
                                     and re.search(r"\bVS\b", self.question)]
        self.scope_read_requested = bool(SCOPE_READ_LANGUAGE.search(normalized))
        self.unit_requested = bool(UNIT_LANGUAGE.search(normalized))
        self.requested_role = _role(self.question)
        self.operation, self.target_unit = _operation(self.question)
        self.configurations = list(dict.fromkeys((match[1].casefold(), match[2].casefold())
                                                 for match in CONFIGURATION.finditer(self.question)))
        explicit_cell_language = re.search(r"\b(?:cellules?|cells?)\b", normalized)
        cell_context = self.cell_context or self.scope.get("kind") in {"cell_range", "sheet"}
        self.requested_cells, self.parse_failures = _addresses(
            self.question, enabled=bool(explicit_cell_language or cell_context and CELL_LANGUAGE.search(normalized)))
        self.requested_field = "formula" if re.search(r"\b(?:formule|formula)\b", normalized) and not re.search(
            r"\b(?:resultat|result|valeur|value|calcul\w*)\b", normalized) else "value"
        self.subjects = tuple(dict.fromkeys(match[0] for match in SUBJECT.finditer(self.question)
                                           if any(char.isdigit() for char in match[0])
                                           and match[0].upper() not in self.requested_cells
                                           and match[0].casefold() not in NOT_SUBJECTS))
        if self.operation and self.requested_cells:
            self.kind = "calculation"
        elif self.operation and self.operation != "difference":
            self.kind = "calculation"
        elif INTERVAL_LANGUAGE.search(normalized) and self.quantity:
            self.kind = "interval"
        elif (self.mode == "comparison" or COMPARISON_LANGUAGE.search(normalized)
              or re.search(r"(?<!\w)vs\.?(?!\w)", self.question)):
            # Preserve case here: electrical VS is a supply label, not "vs".
            self.kind = "comparison"
        elif MAPPING_LANGUAGE.search(normalized):
            self.kind = "mapping"
        elif self.requested_cells or self.scope.get("kind") == "cell_range" and not self.quantity and self.scope_read_requested:
            self.kind = "cell_values"
        elif self.quantity:
            self.kind = "value"
        else:
            self.kind = "general"
        if len(quantities) > 1:
            self.parse_failures.append("multiple_quantities_not_decomposed")
        if len(self.requested_properties) > 1 and self.kind not in {"calculation", "cell_values"}:
            self.parse_failures.append("multiple_properties_not_decomposed")

    def _cells(self, references: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        by_address: dict[str, list[dict[str, Any]]] = {}
        for reference in references:
            if reference["kind"] == "cell":
                by_address.setdefault(reference["cell_facts"]["address"], []).append(reference)
        # A small explicit scope may be restituted in full from its retained
        # catalogue. This does not certify that extraction/retrieval was complete.
        requested = list(self.requested_cells)
        if (not requested and self.scope_read_requested and self.scope.get("kind") == "cell_range"
                and len(by_address) <= MAX_OPERANDS):
            requested = list(by_address)
        return by_address, requested

    def _facts(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.quantity is None:
            return []
        return [fact for reference in references for fact in _quantity_lines(reference, self.quantity, self.requested_role, self.subjects)
                if self.kind != "interval" or fact["kind"] == "interval"]

    def _mappings(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        facts = []
        for reference in references:
            for line in reference_text(reference).splitlines():
                for match in MAPPING_RELATION.finditer(line):
                    configuration = (match["key"].casefold(), match["value"].casefold())
                    if configuration in self.configurations:
                        facts.append({"reference_id": reference["id"], "document_id": reference["document_id"],
                                      "source_ids": reference["source_ids"], "kind": "mapping",
                                      "configuration": list(configuration), "code": match["code"], "quote": line})
        return facts

    def required_ids(self, references: list[dict[str, Any]], required_documents=()) -> list[str]:
        by_address, requested = self._cells(references)
        required = [by_address[address][0]["id"] for address in requested if len(by_address.get(address, [])) == 1]
        facts = self._facts(references)
        groups = [[fact for fact in facts if subject in fact["subjects"]] for subject in self.subjects]
        groups += [[fact for fact in facts if fact["document_id"] == document] for document in required_documents]
        if not groups and self.quantity:
            groups = [facts]
        for group in groups:
            candidates = list(dict.fromkeys(fact["reference_id"] for fact in group))
            if len(candidates) == 1:
                required.append(candidates[0])
        for conflict in _conflicting_relations(facts):
            required.extend(conflict["reference_ids"])
        for configuration in self.configurations:
            required.extend(fact["reference_id"] for fact in self._mappings(references)
                            if tuple(fact["configuration"]) == configuration)
        return list(dict.fromkeys(required))

    def prompt(self, references: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind, "quantity": self.quantity, "requested_role": self.requested_role,
                  "requested_cells": self.requested_cells, "requested_field": self.requested_field, "requested_subjects": list(self.subjects),
                  "requested_properties": self.requested_properties,
                  "requested_configurations": [list(configuration) for configuration in self.configurations],
                  "required_reference_ids": self.required_ids(references),
                  "coverage_scope": "retained_catalogue_only"}
        if self.kind == "calculation":
            result["calculation"] = {"operation": self.operation, "target_unit": self.target_unit,
                                     "values_generated_by_model": False}
        return result

    def calculation(self, references: list[dict[str, Any]]) -> dict[str, Any] | None:
        if self.kind != "calculation":
            return None
        if self.parse_failures:
            raise CalculationRefusal(self.parse_failures[0], "La demande de calcul ne désigne pas un ensemble d'entrées univoque et borné.")
        if not self.requested_cells:
            raise CalculationRefusal("explicit_cell_operands_required", "Précisez les cellules à utiliser pour le calcul.")
        by_address, _ = self._cells(references)
        if any(len(by_address.get(address, [])) != 1 for address in self.requested_cells):
            raise CalculationRefusal("operand_missing_or_ambiguous", "Une cellule demandée est absente des preuves retenues ou désigne plusieurs feuilles/documents.")
        operands = list(self.requested_cells)
        unit_reference = None
        if self.operation == "convert":
            # The question must bind the unit explicitly. Mere cell adjacency
            # or a header outside the retained catalogue is not a binding.
            matches = re.findall(
                r"\b(?:unite|unit)\s+(?:(?:portee|donnee|indiquee|source)\s+)?"
                r"(?:par|dans|de|from|in|at)\s+(?:(?:la\s+)?(?:cellule|cell)\s+)?([a-z]{1,3}[1-9][0-9]*)\b",
                folded(self.question))
            unit_addresses = list(dict.fromkeys(address.upper() for address in matches))
            if len(unit_addresses) > 1:
                raise CalculationRefusal("ambiguous_unit_binding", "Plusieurs cellules d'unité sont désignées pour la conversion.")
            if unit_addresses:
                address = unit_addresses[0]
                if address not in operands or len(by_address.get(address, [])) != 1:
                    raise CalculationRefusal("unit_cell_missing", "La cellule d'unité explicitement demandée n'est pas disponible.")
                unit_reference = by_address[address][0]
                operands.remove(address)
        return calculate(self.operation or "", [by_address[address][0] for address in operands], self.target_unit,
                         unit_reference=unit_reference)

    def assess(self, references: list[dict[str, Any]], selected_ids: list[str] | None = None, required_documents=()) -> dict[str, Any]:
        selected_set = set(selected_ids) if selected_ids is not None else {reference["id"] for reference in references}
        selected = [reference for reference in references if reference["id"] in selected_set]
        selected_documents = {reference["document_id"] for reference in selected}
        missing: list[dict[str, Any]] = [{"requirement": reason} for reason in self.parse_failures]
        ambiguous: list[dict[str, Any]] = []
        by_address, requested = self._cells(references)
        for address in requested:
            candidates = by_address.get(address, [])
            if len(candidates) > 1:
                ambiguous.append({"requirement": "cell_address_ambiguous", "address": address,
                                  "reference_ids": [ref["id"] for ref in candidates]})
            elif not candidates or candidates[0]["id"] not in selected_set:
                missing.append({"requirement": "requested_cell", "address": address,
                                "stage": "selection" if candidates else "context"})
            else:
                fields = [field for field in candidates[0]["fields"] if field["field"] == self.requested_field]
                if not fields:
                    missing.append({"requirement": "requested_cell_field", "field": self.requested_field, "address": address})
                elif any(not field["complete"] for field in fields):
                    ambiguous.append({"requirement": "cell_value_partial", "address": address, "reference_ids": [candidates[0]["id"]]})
                if self.kind == "cell_values" and self.unit_requested and self.requested_field == "value":
                    unit_established = False
                    for value_field in fields:
                        if not value_field["complete"]:
                            continue
                        raw_value = value_field["text"].strip()
                        if raw_value and (raw_value in UNITS or raw_value in UNIT_ALIASES):
                            unit_established = True
                            continue
                        try:
                            _, source_unit = parse_quantity(raw_value)
                            unit_established |= bool(source_unit)
                        except CalculationRefusal:
                            pass
                    if not unit_established:
                        missing.append({"requirement": "requested_unit_not_provided", "address": address,
                                        "stage": "retained_cell_fields"})
                if (self.requested_field == "value" and candidates[0]["cell_facts"].get("formula_present")
                        and not candidates[0]["cell_facts"].get("cached_present")):
                    missing.append({"requirement": "formula_cache_absent", "address": address})
        for document in required_documents:
            if document not in selected_documents:
                missing.append({"requirement": "requested_document", "document_id": document})
        for reference in selected:
            if self.quantity in {"voltage", "current"} and AMBIGUOUS_ZERO.search(reference_text(reference)):
                ambiguous.append({"requirement": "ambiguous_numeric_glyph", "reference_ids": [reference["id"]],
                                  "source_ids": reference["source_ids"], "raw_text_preserved": True,
                                  "extraction_method": reference.get("extraction_method", "unknown")})
        facts = self._facts(selected)
        if self.quantity:
            if not facts:
                missing.append({"requirement": "same_relation_lower_upper_unit" if self.kind == "interval" else "quantity_value_unit",
                                "quantity": self.quantity, "role": self.requested_role})
            for subject in self.subjects:
                if not any(subject in fact["subjects"] for fact in facts):
                    missing.append({"requirement": "requested_subject_quantity", "subject": subject, "quantity": self.quantity})
            for document in required_documents:
                if document in selected_documents and not any(fact["document_id"] == document for fact in facts):
                    missing.append({"requirement": "same_quantity_for_document", "document_id": document, "quantity": self.quantity})
            if self.requested_role is None and len({fact["role"] for fact in facts if fact["role"]}) > 1:
                ambiguous.append({"requirement": "quantity_role_not_specified", "roles": sorted({fact["role"] for fact in facts if fact["role"]})})
        mappings = self._mappings(selected) if self.kind == "mapping" else []
        if self.kind == "mapping":
            mapping_refs = [reference for reference in selected if any(CODE.search(line) and MAPPING_LANGUAGE.search(folded(line))
                                                                       for line in reference_text(reference).splitlines())]
            if not mapping_refs and not mappings:
                missing.append({"requirement": "configuration_code_on_same_line"})
            for configuration in self.configurations:
                if not any(tuple(fact["configuration"]) == configuration for fact in mappings):
                    missing.append({"requirement": "explicit_configuration_mapping", "configuration": list(configuration)})
            for subject in self.subjects:
                if not any(_contains_subject(reference_text(reference), subject) for reference in mapping_refs) and not any(
                        _contains_subject(fact["quote"], subject) for fact in mappings):
                    missing.append({"requirement": "mapping_subject", "subject": subject})
        # Inspect all counted evidence so model omission cannot arbitrate a
        # contradiction. Other documents or different conditions stay distinct.
        conflicts = _conflicting_relations(self._facts(references))
        all_mappings = self._mappings(references) if self.kind == "mapping" else []
        for configuration in self.configurations:
            group = [fact for fact in all_mappings if tuple(fact["configuration"]) == configuration]
            for document in {fact["document_id"] for fact in group}:
                same_document = [fact for fact in group if fact["document_id"] == document]
                if len({fact["code"].casefold() for fact in same_document}) > 1:
                    conflicts.append({"requirement": "configuration_conflicting_codes", "configuration": list(configuration),
                                      "reference_ids": [fact["reference_id"] for fact in same_document],
                                      "quotes": [fact["quote"] for fact in same_document]})
        calculation = None
        if self.kind == "calculation":
            try:
                calculation = self.calculation(selected)
            except CalculationRefusal as error:
                missing.append({"requirement": error.code, "message": error.message})
        supported_form = (self.kind in {"cell_values", "calculation", "interval", "value"}
                          or self.kind == "comparison" and self.quantity is not None
                          or self.kind == "mapping" and bool(self.configurations))
        # A mere address/code co-occurrence stays unassessed; only the explicit
        # CONFIG=VALUE -> CODE grammar receives a local mapping coverage check.
        status = ("conflict" if conflicts else "ambiguous" if ambiguous else "partial" if missing
                  else "covered" if supported_form and selected else "unassessed")
        return {"version": 1, "kind": self.kind, "status": status, "verification": VERIFICATION,
                "coverage_scope": "retained_catalogue_only", "limitation": LIMITATION,
                "quantity": self.quantity, "requested_role": self.requested_role,
                "requested_properties": self.requested_properties,
                "required_reference_ids": self.required_ids(references, required_documents),
                "requested_cells": requested, "requested_subjects": list(self.subjects),
                "missing": missing, "ambiguous": ambiguous, "conflicts": conflicts,
                "matched_relations": [*facts, *mappings], "calculation": calculation,
                "selected_reference_ids": [reference["id"] for reference in selected]}


def assessment_message(assessment: dict[str, Any]) -> str | None:
    status = assessment["status"]
    if status == "conflict":
        return "Les extraits retenus donnent des valeurs différentes pour un même libellé et une même condition. Les sources sont restituées séparément ; aucune valeur n'est arbitrée."
    if status == "ambiguous":
        return "Une ambiguïté subsiste dans les preuves retenues (lecture, adresse ou rôle de la grandeur). Les données brutes sont conservées ; aucune correction n'est supposée."
    if status == "partial":
        if any(item["requirement"] == "multiple_properties_not_decomposed" for item in assessment["missing"]):
            return "La demande porte sur plusieurs propriétés distinctes. Les extraits cités sont disponibles, mais les contrôles ne valident pas séparément la couverture de chacune ; une seule plage ne suffit pas à toutes les établir."
        if assessment["kind"] == "calculation":
            if assessment.get("calculation") is not None:
                return "Le calcul ci-dessous utilise les entrées citées ; la couverture des autres éléments demandés reste partielle."
            reason = next((item["message"] for item in assessment["missing"] if item.get("message")), None)
            return ("Le calcul demandé n'est pas établi : " + reason if reason else
                    "Le calcul demandé ne peut pas être établi à partir d'entrées complètes et univoques dans les preuves retenues.")
        if any(item["requirement"] == "requested_unit_not_provided" for item in assessment["missing"]):
            return "L'unité demandée n'est pas établie par les champs des cellules retenues. Les valeurs brutes sont restituées ; aucune unité d'une cellule extérieure n'est supposée."
        if assessment["kind"] == "interval":
            return "La plage demandée n'est pas entièrement établie : les preuves retenues ne relient pas toutes les bornes, unités, grandeurs ou conditions demandées. Cela ne démontre pas l'absence de ces données dans les documents."
        return "Restitution partielle : certains faits demandés ne sont pas établis dans les preuves retenues. Cela ne démontre pas leur absence dans les documents."
    if status == "unassessed":
        return "Les extraits ci-dessous sont restitués avec leurs sources. La couverture complète de cette demande n'est pas établie par les contrôles disponibles."
    return None
