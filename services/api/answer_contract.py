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
from decimal import Decimal, localcontext
from typing import Any, cast

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
    convert_relation,
    decimal_text,
    parse_quantity,
)

VERIFICATION = "bounded_structural_checks"
LIMITATION = "Contrôles de couverture explicite et de relations locales ; aucune preuve générale de justesse sémantique."
QUANTITIES = {
    "voltage": r"\b(?:tensions?|voltages?|vcc|vdd|vss)\b|(?<!\w)v\+(?!\w)",
    "current": r"\b(?:courants?|currents?)\b",
    "temperature": r"\b(?:temperature|temperatures)\b",
    "power": r"\b(?:puissances?|power(?!\s+supply))\b",
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
    "nominal": r"\b(?:nominal\w*|nom\.)",
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
INTERVAL_LANGUAGE = re.compile(r"\b(?:plages?|intervalles?|ranges?|bornes?|minimum\s+et\s+(?:le\s+)?maximum|min\s+et\s+max)\b")
SUPPLY_RANGE_LANGUAGE = re.compile(
    r"\bplages?\s+(?:d['’]\s*|de\s+l['’]\s*)alimentation\b"
    r"|\b(?:power\s+)?supply(?:\s+voltages?)?\s+ranges?\b")
TEMPERATURE_CONDITION_ATTACHMENT = re.compile(
    r"\bavec\s+(?:(?:leurs?|ses|les|des)\s+)?conditions?\s+de\s+temperatures?\b"
    r"|\bwith\s+(?:(?:their|its|the)\s+)?temperature\s+conditions?\b")
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
BETWEEN_RANGE = re.compile(
    rf"\b(?:entre|between)\s+(?P<low>{NUMBER_PATTERN})\s*(?P<low_unit>{UNIT_PATTERN})?\s*"
    rf"(?:et|and)\s+(?P<high>{NUMBER_PATTERN})\s*(?P<high_unit>{UNIT_PATTERN})(?!\w)", re.IGNORECASE)
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
UNIT_WORDS = {"millisecondes": "ms", "milliseconde": "ms", "milliseconds": "ms", "millisecond": "ms",
              "microsecondes": "µs", "microseconde": "µs", "microseconds": "µs", "microsecond": "µs",
              "secondes": "s", "seconde": "s", "seconds": "s", "second": "s",
              "millivolts": "mV", "millivolt": "mV", "volts": "V", "volt": "V"}
PROPERTY_LABELS = {"bus": "tension de bus", "supply": "alimentation", "shunt": "shunt",
                   "ambient": "température ambiante", "junction": "température de jonction",
                   "storage": "température de stockage", "input": "entrée", "output": "sortie",
                   "quiescent": "repos", "leakage": "fuite", "conversion": "temps de conversion"}
INEQUALITY_RANGE = re.compile(
    rf"(?P<low>{NUMBER_PATTERN})\s*(?P<low_unit>{UNIT_PATTERN})?\s*(?:≤|<=)\s*"
    rf"(?P<symbol>[A-Za-z][A-Za-z0-9_+]{{0,15}})\s*(?:≤|<=)\s*"
    rf"(?P<high>{NUMBER_PATTERN})\s*(?P<high_unit>{UNIT_PATTERN})(?!\w)")
BOUND_ROLES = {
    "minimum": r"\b(?:minimum|minimal\w*|min\.?|lower\s+(?:bound|limit))\b",
    "maximum": r"\b(?:maximum|maximal\w*|max\.?|upper\s+(?:bound|limit))\b",
}
# These are rejection signals, not a general language-understanding model. A
# negated or uncertain clause remains visible as a quotation, but its number
# cannot become an asserted value or feed a comparison/calculation.
NEGATED_ASSERTION = re.compile(
    r"\b(?:not|never|neither|cannot|can't|isn't|aren't|wasn't|weren't|"
    r"no\s+(?:range|value|voltage|current|guarantee|evidence|proof)\b|"
    r"n['’](?:est|etait|atteint)\s+(?:pas|plus|jamais)|ne\s+[^.!?;]{0,50}\b(?:pas|plus|jamais)|"
    r"ni|aucun\w*|non\s+(?:garanti\w*|valid\w*|verifi\w*))\b")
UNCERTAIN_ASSERTION = re.compile(
    r"\b(?:may|might|could|perhaps|possibly|approximately|approx\.?|estimated|"
    r"unverified|preliminary|environ|approximati\w*|estime\w*|indicatif\w*|"
    r"incertain\w*|provisoire\w*|preliminaire\w*|a\s+confirmer|peut[- ]etre)\b|[~≈]")
CONDITION_MEASURE = re.compile(
    rf"(?<!\w)(?:(?i:at|à|a|when|for|pour|sous)\s+"
    rf"(?:(?P<prefixed_symbol>[A-Za-z][A-Za-z0-9_+]{{0,15}})\s*=\s*)?"
    rf"|(?P<symbol>[A-Za-z][A-Za-z0-9_+]{{0,15}})\s*=\s*)"
    rf"(?P<value>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})(?![\w/])")


def _assertion_status(text):
    normalized = folded(text)
    if NEGATED_ASSERTION.search(normalized):
        return "negated"
    if UNCERTAIN_ASSERTION.search(normalized) or "?" in text:
        return "uncertain"
    return "asserted"


# A small literal question grammar, not a semantic entailment model. All
# documentary words below are taken from the question and a complete retained
# block. The grammar only changes interrogative word order and punctuation.
# It deliberately has no domain/entity vocabulary, synonym or translation map.
QUALITATIVE_CONNECTOR = re.compile(
    r"\s+(?P<marker>only\s+when|only\s+if|provided\s+that|when|if|"
    r"uniquement\s+lorsque|seulement\s+lorsque|uniquement\s+si|seulement\s+si|"
    r"uniquement\s+lorsqu['’]|seulement\s+lorsqu['’]|lorsqu['’]|"
    r"à\s+condition\s+que|lorsque|quand|si|because|parce\s+que|car)(?:\s+|(?<=['’]))", re.IGNORECASE)
QUALITATIVE_CAUSES = {"because", "parce que", "car"}
QUALITATIVE_SUFFICIENT = {"when", "if", "provided that", "lorsque", "quand", "si", "à condition que"}
QUALITATIVE_PRONOUNS = {"it", "they", "he", "she", "this", "that", "these", "those", "we", "you",
                        "il", "elle", "ils", "elles", "ceci", "cela", "ça", "on", "nous", "vous"}
QUALITATIVE_MODIFIER = re.compile(r"^(?:possibly|perhaps|approximately|maybe|peut-être|peut etre|environ)\s+", re.IGNORECASE)
QUALITATIVE_ANAPHORA = re.compile(
    r"\b(?:it|its|they|their|he|she|il|elle|ils|elles|celui-ci|celle-ci|ceux-ci|celles-ci|"
    r"celui-la|celle-la|ceux-la|celles-la|cela|ceci|ca|son|sa|ses|leur|leurs|"
    r"ce\s+dernier|cette\s+derniere|the\s+(?:former|latter))\b"
    r"|\b(?:this|that|these|those)\s+(?:is|are|was|were)\b")
QUALITATIVE_ABSENCE = re.compile(
    r"(?:unknown|unspecified|unavailable|not\s+(?:specified|known|provided|available|established)|"
    r"non\s+(?:renseignee?|fournie?|indiquee?|disponible|etablie?)|inconnue?|n/?a)")


def _literal_key(text: str) -> str:
    """Normalize typography, without changing documentary vocabulary."""
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    text = text.replace("‑", "-").replace("‐", "-")
    return re.sub(r"\s+", " ", text).strip(" \t\r\n.!?")


def _qualitative_request(question: str) -> dict[str, Any] | None:
    value = _literal_key(question)
    for language, pattern in (
        ("fr", r"^(?:(?:explique|expliquez)\s+)?pourquoi\s+(.+)$"),
        ("en", r"^(?:explain\s+)?why\s+(.+)$"),
        ("fr", r"^(?:dans|sous)\s+quelles?\s+conditions?\s+(.+)$"),
        ("en", r"^(?:under|in)\s+what\s+conditions?\s+(.+)$"),
    ):
        match = re.fullmatch(pattern, value)
        if not match:
            continue
        intent = "cause" if "pourquoi" in pattern or "why" in pattern else "condition"
        clause = match[1]
        inverted = None
        if language == "fr":
            clause = re.sub(r"\b(est|sont)-(?:il|elle|ils|elles)\b", r"\1", clause)
            grammar = bool(_literal_copula(clause, language))
        else:
            inverted = re.fullmatch(r"(is|are)\s+(.+)", clause)
            grammar = inverted is not None
            clause = inverted[2] if inverted else clause
        return {"intent": intent, "language": language, "target": clause,
                "grammar_supported": grammar,
                "copula": inverted[1] if language == "en" and inverted else None}
    for language, pattern in (("fr", r"^quell?e?\s+est\s+(.+)$"), ("en", r"^what\s+is\s+(.+)$")):
        match = re.fullmatch(pattern, value)
        if match:
            label = re.sub(r"^(?:le|la|les|the)\s+|^l'", "", match[1])
            return {"intent": "field", "language": language, "target": label, "grammar_supported": True}
    return None


def _literal_copula(text: str, language: str) -> dict[str, Any] | None:
    value = _literal_key(text)
    pattern = (r"(?P<subject>.+?)\s+(?P<verb>is|are)\s+(?P<predicate>.+)" if language == "en" else
               r"(?P<subject>.+?)\s+(?P<negative>n'|ne\s+)?(?P<verb>est|sont)\s+(?P<predicate>.+)")
    match = re.fullmatch(pattern, value)
    if not match:
        return None
    subject, verb, predicate = match["subject"], match["verb"], match["predicate"]
    negative = False
    if language == "en" and predicate.startswith("not "):
        negative, predicate = True, predicate[4:]
    elif language == "fr" and match["negative"]:
        if not predicate.startswith("pas "):
            return None  # n'est ... que, jamais and plus are not rewritten as pas
        negative, predicate = True, predicate[4:]
    predicate = QUALITATIVE_MODIFIER.sub("", predicate)
    if not predicate or not subject:
        return None
    return {"subject": subject, "verb": verb, "predicate": predicate, "negative": negative,
            "uncertain": bool(UNCERTAIN_ASSERTION.search(folded(value))),
            "pronoun": subject in QUALITATIVE_PRONOUNS,
            "positive": f"{subject} {verb} {predicate}", "body": f"{subject} {predicate}"}


def _qualitative_identity(request: dict[str, Any], statement: dict[str, Any]) -> bool | None:
    """Return the requested polarity only for the exact subject/predicate."""
    if not request["grammar_supported"]:
        return None
    if request["language"] == "fr":
        target = _literal_copula(request["target"], "fr")
        if target and not target["uncertain"] and target["positive"] == statement["positive"]:
            return bool(target["negative"])
    elif request.get("copula") == statement["verb"]:
        if request["target"] == statement["body"]:
            return False
        if request["target"] == f"{statement['subject']} not {statement['predicate']}":
            return True
    return None


def _qualitative_relations(request: dict[str, Any], references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations = []
    for reference in references:
        if reference["kind"] != "excerpt":
            continue
        text = reference["text"]
        # Large/general passages keep their literal output, with no claim that
        # this finite grammar established all of their dependencies.
        if len(text) > 16_384:
            continue
        literal = text.strip()
        source_start = text.find(literal)
        connector = QUALITATIVE_CONNECTOR.search(literal)
        main = literal[:connector.start()].strip() if connector else literal.rstrip(".!?").strip()
        marker = _literal_key(connector["marker"]) if connector else ""
        qualification = literal[connector.start():].strip() if connector else ""
        statement = None
        value = None
        if request["intent"] == "field":
            label = re.fullmatch(r"([^:\n;]+):\s*([^\n;]+)", literal)
            if not label or _literal_key(label[1]) != request["target"]:
                continue
            value = label[2].strip().rstrip(".")
            if not value:
                continue
            polarity_matches = True
            subject_key, predicate_key = request["target"], ""
        else:
            statement = _literal_copula(main, request["language"])
            if not statement:
                continue
            polarity = _qualitative_identity(request, statement)
            if polarity is None:
                continue
            polarity_matches = polarity == statement["negative"]
            subject_key, predicate_key = statement["subject"], statement["predicate"]
        reasons = []
        if reference.get("source_span_complete") is not True:
            reasons.append("qualitative_source_span_incomplete")
        if statement and statement["pronoun"]:
            reasons.append("qualitative_pronoun_unresolved")
        if connector and QUALITATIVE_ANAPHORA.search(folded(literal[connector.end():])):
            reasons.append("qualitative_pronoun_unresolved")
        answer_value = (value or "") if request["intent"] == "field" else literal[connector.end():] if connector else ""
        if QUALITATIVE_ABSENCE.fullmatch(folded(answer_value).strip(" .!?")):
            reasons.append("qualitative_information_absent")
        if UNCERTAIN_ASSERTION.search(folded(literal)) or "?" in literal:
            reasons.append("qualitative_source_uncertain")
        # A subsequent sentence may retract or qualify the first one. Retain
        # it verbatim, but do not certify a single-clause answer from that text.
        if re.search(r"[.!?][\"'»”)]*\s+\S", literal):
            reasons.append("qualitative_clause_ambiguous")
        if not polarity_matches:
            reasons.append("qualitative_polarity_mismatch")
        qualifier_kind = "cause" if marker in QUALITATIVE_CAUSES else "condition" if marker else None
        if request["intent"] != "field" and (qualifier_kind != request["intent"] or not qualification):
            reasons.append("qualitative_" + request["intent"] + "_not_established")
        relations.append({"kind": "qualitative_literal", "intent": request["intent"],
                          "reference_id": reference["id"], "reference_ids": [reference["id"]],
                          "document_id": reference["document_id"], "source_ids": reference["source_ids"],
                          "version_id": reference.get("version_id"),
                          "extraction_revision_id": reference.get("extraction_revision_id"),
                          "quote": text, "source_start": source_start, "source_end": source_start + len(literal),
                          "subject": subject_key, "predicate": predicate_key,
                          "negative": bool(statement and statement["negative"]),
                          "qualification": qualification, "qualifier_kind": qualifier_kind, "marker": marker,
                          "value": value, "reasons": reasons,
                          "verification": "literal_subject_predicate_qualification_match"})
    return relations


def _qualitative_conflicts(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for relation in relations:
        if any(reason != "qualitative_polarity_mismatch" for reason in relation["reasons"]):
            continue
        marker = relation["marker"]
        if relation["intent"] == "condition" and marker not in QUALITATIVE_SUFFICIENT:
            continue  # "only when" gives a necessary, not sufficient condition
        key = (relation["subject"], relation["predicate"], relation["intent"],
               _literal_key(relation["qualification"]))
        groups.setdefault(key, []).append(relation)
    conflicts = []
    for group in groups.values():
        if (len({item["negative"] for item in group}) < 2
                and not (group[0]["intent"] == "field" and len({_literal_key(item["value"]) for item in group}) > 1)):
            continue
        conflicts.append({"requirement": "qualitative_source_discrepancy",
                          "reference_ids": list(dict.fromkeys(item["reference_id"] for item in group)),
                          "document_ids": list(dict.fromkeys(item["document_id"] for item in group)),
                          "quotes": [item["quote"] for item in group], "precedence_inferred": False,
                          "entity_identity_established": len({item["document_id"] for item in group}) == 1})
    return conflicts


def _bound_role(text):
    roles = [role for role, pattern in BOUND_ROLES.items() if re.search(pattern, folded(text))]
    return roles[0] if len(roles) == 1 else None


def _condition_measures(text):
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
        measures.append({"quantity": dimension, "symbol": match["prefixed_symbol"] or match["symbol"],
                         "value": base, "text": match[0], "start": match.start(), "end": match.end()})
    return measures


def _local_condition(line, start, end):
    # The old suffix-only representation lost conditions placed before a
    # quantity, allowing two temperatures to be compared as one context.
    # A preceding assertion separated by a semicolon cannot donate its own
    # temperature condition to the next quantity.
    before = [item["text"] for item in _condition_measures(line[:start].rsplit(";", 1)[-1])]
    after = line[end:].strip()
    return " ; ".join([*before, *([after] if after.strip(" .;") else [])])


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
    word_matches = list(re.finditer(r"\b(?:en|into|to)\s+(" + "|".join(UNIT_WORDS) + r")\b", normalized))
    # "Conversion time" is a measured property, not an instruction to do
    # arithmetic. A nominal unit-conversion request needs an explicit target;
    # verb requests may still be classified and then refused for a missing unit.
    if operation is None and (matches or word_matches) and re.search(r"\b(?:conversion|exprimer|exprimez?|express)\b", normalized):
        operation = "convert"
    if operation == "convert" and matches:
        target = matches[-1][1]
    elif operation == "convert" and word_matches:
        target = UNIT_WORDS[word_matches[-1][1]]
    return operation, target


def _properties(text: str, quantity: str) -> list[str]:
    normalized = folded(text)
    properties = [name for name, pattern in QUANTITY_PROPERTIES.get(quantity, {}).items()
                  if re.search(pattern, normalized)]
    if quantity == "voltage" and re.search(r"\bVS\b|(?<!\w)V\+(?!\w)", text) and "supply" not in properties:
        properties.append("supply")
    return properties


def _requested_quantities(normalized: str) -> list[str]:
    """Separate an explicitly attached condition from the requested quantity.

    Only the temperature mention inside ``with its temperature conditions``
    (or its French equivalent) can be removed from quantity classification.
    Other temperature mentions remain independent requirements. This changes
    neither the original question nor any source condition or numeric value.
    """
    quantity_text = normalized
    supply_range = False
    attachment = TEMPERATURE_CONDITION_ATTACHMENT.search(normalized)
    if attachment:
        primary = normalized[:attachment.start()]
        supply_range = bool(SUPPLY_RANGE_LANGUAGE.search(primary))
        supply_voltage = bool(re.search(QUANTITIES["voltage"], primary)
                              and re.search(QUANTITY_PROPERTIES["voltage"]["supply"] + r"|(?<!\w)v\+(?!\w)", primary))
        if supply_range or supply_voltage:
            quantity_text = normalized[:attachment.start()] + " " + normalized[attachment.end():]
    quantities = [quantity for quantity, pattern in QUANTITIES.items() if re.search(pattern, quantity_text)]
    if supply_range and "voltage" not in quantities:
        # The established supply-range alias is explicit here even when another
        # independently requested quantity makes the whole question ambiguous.
        quantities.append("voltage")
    if not quantities and re.search(r"\b(?:alimentation|supply)\b", normalized):
        quantities = ["voltage"]
    return quantities


def _temperature_condition_present(text: str) -> bool:
    """Require a temperature explicitly attached to this quantity's clause.

    An independent ``storage temperature: ...`` assertion in the suffix is not
    a condition on the voltage. Do not search past such an intervening clause,
    even when it contains its own ``at`` or ``for`` phrase.
    """
    condition = text.lstrip(" \t.,;:").split(";", 1)[0].strip(" \t.,")
    attachment = re.match(r"^(?:at|a|à|for|pour|when|lorsque|from|de)\s+", condition, re.IGNORECASE)
    if attachment is None:
        return False
    points = _condition_measures(condition)
    if any(point["quantity"] == "temperature" and point["start"] == 0 and point["end"] == len(condition)
           for point in points):
        return True
    remainder = condition[attachment.end():]
    # A named variable is preserved in the source, never supplied by the parser.
    remainder = re.sub(r"^[A-Z][A-Z0-9_+]{0,10}\s*(?:=|de\b|from\b)?\s*", "", remainder)
    for pattern in (BETWEEN_RANGE, RANGE_VALUE, LABELLED_RANGE, INEQUALITY_RANGE):
        match = pattern.fullmatch(remainder)
        if match is None:
            continue
        try:
            low, low_unit = parse_quantity(match["low"] + " " + (match["low_unit"] or match["high_unit"]))
            high, high_unit = parse_quantity(match["high"] + " " + match["high_unit"])
        except CalculationRefusal:
            continue
        if low_unit == high_unit and UNITS[low_unit][0] == "temperature" and low <= high:
            return True
    return False


def _condition_key(text):
    """Normalize only a complete SYMBOL + explicit range condition."""
    raw = text.strip(" .;")
    points = _condition_measures(raw)
    if len(points) == 1 and points[0]["start"] == 0 and points[0]["end"] == len(raw):
        point = points[0]
        return ("point", point["quantity"], point["symbol"], point["value"])
    raw = re.sub(r"^(?:pour|for|when|lorsque)\s+", "", raw, flags=re.IGNORECASE)
    symbol = re.match(r"^([A-Z][A-Z0-9_+]{0,10})\s*(?:=|de|from)?\s*", raw)
    if symbol:
        rest = raw[symbol.end():]
        match = RANGE_VALUE.fullmatch(rest) or BETWEEN_RANGE.fullmatch(rest)
        if match:
            try:
                low, unit = parse_quantity(match["low"] + " " + (match["low_unit"] or match["high_unit"]))
                high, high_unit = parse_quantity(match["high"] + " " + match["high_unit"])
            except CalculationRefusal:
                return ("literal", folded(raw))
            if unit == high_unit and low <= high:
                return (symbol[1], UNITS[unit][0], decimal_text(low * Decimal(UNITS[unit][1]) + Decimal(UNITS[unit][2])),
                        decimal_text(high * Decimal(UNITS[unit][1]) + Decimal(UNITS[unit][2])))
    return ("literal", folded(raw))


def _relation(reference, *, quantity, role, values, unit, label, condition, quote, kind, subjects,
              value_text=None, code=None, dependency_ids=(), decimal_notation_verified=False, list_context=None):
    context = reference.get("table_context") or {}
    note_issues = []
    if context.get("catalogue_verified"):
        notes = [item["text"] for item in context.get("dependencies", []) if item["kind"] == "note"]
        notes.extend(cell["text"].strip() for cell in context.get("cells", [])
                     if "note" in _cell_roles(cell) and cell["text"].strip())
        condition = " ; ".join(dict.fromkeys(part for part in [condition, *notes] if part))
        if context.get("unresolved_note_markers"):
            note_issues.append("table_note_unresolved")
        if context.get("ambiguous_note_markers"):
            note_issues.append("table_note_ambiguous")
        if context.get("note_scan_complete") is False:
            note_issues.append("table_note_scan_incomplete")
        dependency_ids = [*dependency_ids, *context.get("reference_ids", [])]
    source_ids = list(context.get("source_ids", reference["source_ids"])) if context.get("catalogue_verified") else list(reference["source_ids"])
    list_binding = None
    if list_context:
        dependency_ids = [*dependency_ids, *list_context["reference_ids"]]
        source_ids = list(dict.fromkeys([*source_ids, *list_context["source_ids"]]))
        heading = list_context["heading"]["text"]
        if (_assertion_status(heading) != "asserted" or MEASURE.search(heading)
                or QUALITATIVE_CONNECTOR.search(heading)):
            note_issues.append("list_heading_qualification_unassessed")
        heading_role, line_role = _role(heading), _role(quote)
        if heading_role and line_role and heading_role != line_role:
            note_issues.append("list_heading_role_conflict")
        heading_properties, line_properties = _properties(heading, quantity), _properties(quote, quantity)
        if heading_properties and line_properties and set(heading_properties) != set(line_properties):
            note_issues.append("list_heading_property_conflict")
        if len(reference_text(reference).splitlines()) > 1:
            note_issues.append("list_item_multiline_unassessed")
        list_binding = {key: list_context[key] for key in ("group_id", "heading", "item", "item_count", "verified_item_count",
                                                          "visible_item_count", "catalogue_group_complete", "reference_ids")}
    properties = _properties(label, quantity)
    def identifiers(text):
        return {match[0].casefold() for match in SUBJECT.finditer(text) if any(char.isdigit() for char in match[0])
                and match[0].casefold() not in NOT_SUBJECTS}
    clause_ids = identifiers(quote)
    excerpt_ids = identifiers(reference_text(reference))
    heading_ids = identifiers(list_context["heading"]["text"]) if list_context else set()
    document_ids = identifiers(reference.get("document_name", ""))
    # Count competing identifiers, including ones that the question did not
    # request. A value explicitly attached to DEV456 cannot inherit DEV123 just
    # because the latter was mentioned elsewhere in the same paragraph.
    local_ids = clause_ids or excerpt_ids
    if heading_ids:
        # The verified title is part of the written relation, before any
        # filename fallback. Different explicit title/item identifiers cannot
        # be reconciled by assigning the value to either entity.
        if len(heading_ids) > 1:
            note_issues.append("list_heading_subject_ambiguous")
        if local_ids and local_ids != heading_ids:
            note_issues.append("list_heading_subject_conflict")
        candidates = local_ids | heading_ids
    else:
        candidates = local_ids or document_ids
    local_subjects = [subject for subject in subjects if _contains_subject(next(iter(candidates)), subject)] if len(candidates) == 1 else []
    return {"reference_id": reference["id"], "reference_ids": list(dict.fromkeys([reference["id"], *dependency_ids])),
            "document_id": reference["document_id"],
            "source_ids": source_ids,
            "version_id": reference.get("version_id"), "generation_id": reference.get("generation_id"),
            "extraction_revision_id": reference.get("extraction_revision_id"),
            "subjects": local_subjects,
            "evidence_identifiers": sorted(clause_ids),
            # A preceding subject in the same literal excerpt remains part of
            # the local context. Keep it distinct from clause-local identity;
            # filenames alone do not prove that two quantities name one entity.
            "entity_context_identifiers": sorted(local_ids | heading_ids),
            "kind": kind, "quantity": quantity, "property": properties[0] if len(properties) == 1 else None,
            "properties": properties, "role": role, "values": [decimal_text(value) for value in values], "unit": unit,
            "label": folded(label).strip(" :;|="), "condition": condition, "quote": quote,
            "assertion_status": _assertion_status(quote + " " + condition), "bound_role": _bound_role(label) if kind == "value" else None,
            "note_issues": note_issues,
            "list_binding": list_binding,
            "segments": reference.get("segments", []), "value_text": value_text, "code": code,
            "decimal_notation_verified": decimal_notation_verified}


def _quantity_lines(reference: dict[str, Any], quantity: str, requested_role: str | None, subjects: tuple[str, ...],
                    references: list[dict[str, Any]]):
    """Yield complete local relations without rewriting their quoted evidence."""
    raw = reference_text(reference)
    available = {item["id"] for item in references}
    context = reference.get("list_context") or {}
    if not context.get("catalogue_verified") or not set(context.get("reference_ids", [])) <= available:
        context = {}
    if context:
        visible = {item["list_context"]["item_index"] for item in references if item.get("list_context")
                   and item.get("generation_id") == reference.get("generation_id")
                   and item["list_context"]["group_id"] == context["group_id"]
                   and set(item["list_context"]["reference_ids"]) <= available}
        context = {**context, "visible_item_count": len(visible),
                   "catalogue_group_complete": context["complete"] and visible == set(range(context["item_count"]))}
    heading = context["heading"]["text"] if context else ""
    # Split at explicit sentence boundaries, never at a decimal point, table
    # delimiter, or a condition separator. Each resulting quote stays complete.
    lines = [clause for line in raw.splitlines() for clause in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Þ])", line)]
    for line in lines:
        if (not re.search(QUANTITIES[quantity], folded(line)) and not _properties(line, quantity)
                and not re.search(QUANTITIES[quantity], folded(heading)) and not _properties(heading, quantity)):
            continue
        role = _role(line) or _role(heading)
        if requested_role and role != requested_role or role == "characterization" and requested_role != role:
            continue
        for pattern in (BETWEEN_RANGE, RANGE_VALUE, LABELLED_RANGE):
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
            prefix = line[:match.start()]
            label = prefix if re.search(QUANTITIES[quantity], folded(prefix)) or _properties(prefix, quantity) else heading or prefix
            yield _relation(reference, quantity=quantity, role=role, values=[low, high], unit=high_unit,
                            label=label, condition=_local_condition(line, match.start(), match.end()), quote=line,
                            kind="interval", subjects=subjects, list_context=context)
            break
        else:
            measurements = []
            for match in MEASURE.finditer(line):
                if line[match.end():].startswith("/"):
                    continue  # a ratio such as mV/V is not a voltage value
                try:
                    value, unit = parse_quantity(match[0])
                except CalculationRefusal:
                    continue
                if UNITS[unit][0] == quantity:
                    measurements.append((match, value, unit))
            if len(measurements) == 1:
                match, value, unit = measurements[0]
                prefix = line[:match.start()]
                label = prefix if re.search(QUANTITIES[quantity], folded(prefix)) or _properties(prefix, quantity) else heading or prefix
                yield _relation(reference, quantity=quantity, role=role, values=[value], unit=unit,
                                label=label, condition=_local_condition(line, match.start(), match.end()), quote=line,
                                kind="value", subjects=subjects, value_text=match[0], list_context=context)


def _cell_roles(cell):
    return {header["role"] for header in cell.get("headers", []) if header.get("role")}


def _table_code(cells):
    bits = []
    for cell in cells:
        value = cell["text"].strip()
        if value not in {"0", "1"}:
            continue
        for header in cell["headers"]:
            # Bit significance comes from an explicit common prefix + bit index,
            # not the compressed column ordinal. D8/D7 suffixes stay descriptive.
            match = re.match(r"^([A-Za-z][A-Za-z_]*)([0-9]+)(?:\s|$)", header["text"].strip())
            if match:
                bits.append((match[1], int(match[2]), value))
    if not 2 <= len(bits) <= 16 or len({item[0] for item in bits}) != 1:
        return None, None
    ordered = sorted(bits, key=lambda item: item[1], reverse=True)
    if [item[1] for item in ordered] != list(range(len(bits) - 1, -1, -1)):
        return None, None
    return "".join(item[2] for item in ordered), ordered[0][0]


def _decimal_witness(reference, cell, references):
    """A textual x.xxx needs a same-table/column/unit decimal witness.

    A short fraction such as 1.25 cannot be a three-digit thousands group. Its
    exact authorized row is retained as a dependency of the interpretation.
    Mixed decimal marks or a witness from a different table remain unusable.
    """
    context = reference["table_context"]
    try:
        _, expected_unit = parse_quantity(cell["text"], typed_number=True)
    except CalculationRefusal:
        expected_unit = ""
    marks = set()
    witnesses = []
    for candidate in references:
        other = candidate.get("table_context") or {}
        if not other.get("catalogue_verified") or (candidate.get("generation_id"), other.get("table_block_id")) != (
                reference.get("generation_id"), context["table_block_id"]):
            continue
        for value in other["cells"]:
            if (value["column_start"], value["column_end"]) != (cell["column_start"], cell["column_end"]):
                continue
            match = re.fullmatch(rf"[+\-−]?[0-9]+([.,])[0-9]{{1,2}}\s*({UNIT_PATTERN})?", value["text"].strip())
            if match and UNIT_ALIASES.get(match[2] or "", match[2] or "") == expected_unit:
                marks.add(match[1])
                witnesses.append(candidate["id"])
    mark = "," if "," in cell["text"] else "."
    return witnesses[:1] if marks == {mark} else []


def _table_relations(reference, quantity, subjects, references):
    context = reference.get("table_context") or {}
    available = {item["id"] for item in references}
    if not context.get("catalogue_verified") or context.get("row_role") != "data" or not set(context["reference_ids"]) <= available:
        return []
    cells = context["cells"]
    roles = {id(cell): _cell_roles(cell) for cell in cells}
    label_cells = [cell for cell in cells if "parameter" in roles[id(cell)]
                   or not roles[id(cell)] and not re.fullmatch(rf"\s*{NUMBER_PATTERN}\s*({UNIT_PATTERN})?\s*", cell["text"])]
    label = " | ".join(cell["text"].strip() for cell in label_cells)
    sections = " | ".join(item["text"] for item in context["dependencies"] if item["kind"] == "row_section")
    conditions = " ; ".join(cell["text"].strip() for cell in cells if "condition" in roles[id(cell)])
    all_headers = [header for cell in cells for header in cell["headers"]]
    last_header_row = max((header["row_start"] for header in all_headers), default=-1)
    ancestor_qualifiers = list(dict.fromkeys(header["text"].strip() for header in all_headers
                                            if header["row_start"] < last_header_row and not header.get("role")))
    conditions = " ; ".join(value for value in [*(item for item in ancestor_qualifiers if _role(item) is None), conditions] if value)
    embedded_condition = re.search(r"[,;]\s*([A-Za-z][A-Za-z0-9_ ]{0,8}\s*=\s*.+)$", label)
    if embedded_condition:
        conditions = "; ".join(value for value in (conditions, embedded_condition[1]) if value)
        label = label[:embedded_condition.start()]
    section_heading = context.get("section_heading", {}).get("text", "")
    role = _role(label + " " + sections + " " + section_heading + " " + " ".join(ancestor_qualifiers))
    code, code_name = _table_code(cells)
    units = [UNIT_ALIASES.get(cell["text"].strip(), cell["text"].strip()) for cell in cells if "unit" in roles[id(cell)]]
    unit = units[0] if len(units) == 1 and units[0] in UNITS else ""
    numeric = []
    for cell in cells:
        bound_roles = roles[id(cell)]
        headers = " ".join(header["text"] for header in cell["headers"])
        value_role = bound_roles & {"minimum", "maximum", "typical", "nominal"}
        if not value_role and not (code and re.search(QUANTITIES[quantity], folded(headers))):
            continue
        raw = cell["text"].strip()
        value_text = raw if MEASURE.fullmatch(raw) else raw + (" " + unit if unit else "")
        witnesses = []
        try:
            number, value_unit = parse_quantity(value_text)
        except CalculationRefusal as error:
            if error.code != "ambiguous_decimal_separator":
                continue
            witnesses = _decimal_witness(reference, cell, references)
            if not witnesses:
                continue
            number, value_unit = parse_quantity(value_text, typed_number=True)
        if not value_unit or UNITS[value_unit][0] != quantity:
            continue
        numeric.append({"number": number, "unit": value_unit, "roles": value_role, "text": value_text,
                        "header": headers, "witnesses": witnesses})
    if not numeric:
        return []
    if not (re.search(QUANTITIES[quantity], folded(label)) or _properties(label, quantity)
            or code and any(re.search(QUANTITIES[quantity], folded(item["header"])) for item in numeric)):
        return []
    low = [item for item in numeric if "minimum" in item["roles"]]
    high = [item for item in numeric if "maximum" in item["roles"]]
    relations = []
    dependencies = context["reference_ids"]
    if len(low) == len(high) == 1 and low[0]["unit"] == high[0]["unit"] and low[0]["number"] <= high[0]["number"]:
        relations.append(_relation(reference, quantity=quantity, role=role, values=[low[0]["number"], high[0]["number"]],
                                   unit=low[0]["unit"], label=label, condition=conditions, quote=reference_text(reference),
                                   kind="interval", subjects=subjects, dependency_ids=dependencies))
    for item in numeric:
        if item in low or item in high:
            if relations:
                continue
        # A lone MIN/MAX retains its bound role; it cannot satisfy an interval.
        bound_role = next(iter(item["roles"]), None)
        relation = _relation(reference, quantity=quantity, role=role, values=[item["number"]], unit=item["unit"],
                             label=label or item["header"], condition=conditions, quote=reference_text(reference), kind="value",
                             subjects=subjects, value_text=item["text"], code=code,
                             dependency_ids=[*dependencies, *item["witnesses"]], decimal_notation_verified=bool(item["witnesses"]))
        relation.update(bound_role=bound_role, code_name=code_name)
        relations.append(relation)
    for relation in relations:
        relation["table_bound"] = True
        relation["source_ids"] = list(dict.fromkeys(source_id for item in references if item["id"] in relation["reference_ids"]
                                                     for source_id in item["source_ids"]))
    return relations


def _table_conditions(reference, references):
    context = reference.get("table_context") or {}
    if not context.get("catalogue_verified") or context.get("row_role") != "data":
        return []
    if (context.get("unresolved_note_markers") or context.get("ambiguous_note_markers")
            or context.get("note_scan_complete") is False):
        return []
    if not set(context["reference_ids"]) <= {item["id"] for item in references}:
        return []
    facts = []
    label = " | ".join(cell["text"].strip() for cell in context["cells"]
                       if not _cell_roles(cell) or "parameter" in _cell_roles(cell))
    for cell in context["cells"]:
        if "condition" not in _cell_roles(cell) or not cell["text"].strip():
            continue
        facts.append({"reference_id": reference["id"], "reference_ids": context["reference_ids"],
                      "document_id": reference["document_id"], "source_ids": context["source_ids"],
                      "kind": "test_condition", "role": "characterization", "label": label,
                      "condition": cell["text"].strip(), "quote": reference_text(reference)})
    return facts


def _cell_range_relations(references, scope, quantity, subjects):
    """Read a small, explicitly selected rectangle with a complete header row.

    MIN/MAX/UNIT/PARAMETER are literal headers in the first selected row. Every
    value and condition is linked by actual sheet coordinates and must survive
    as a complete authorized field. This does not bind an adjacent cell's unit
    for general arithmetic or infer headers outside the selected rectangle.
    """
    if scope.get("kind") != "cell_range" or type(scope.get("rowStart")) is not int:
        return []
    from .evidence_selection import _header_role
    by_sheet: dict[tuple[Any, ...], dict[tuple[int, int], list[tuple[dict[str, Any], str]]]] = {}
    for reference in references:
        if reference["kind"] != "cell":
            continue
        field = next((field for field in reference["fields"] if field["field"] == "value" and field["complete"]), None)
        if field is None or reference["cell_facts"].get("formula_present") and not reference["cell_facts"].get("cached_present"):
            continue
        row, column = address_coordinates(reference["cell_facts"]["address"])
        if not (scope["rowStart"] <= row <= scope.get("rowEnd", row) and scope.get("columnStart", column) <= column <= scope.get("columnEnd", column)):
            continue
        key = (reference["document_id"], reference.get("version_id"), reference.get("extraction_revision_id"), reference["locator"]["unit_id"])
        by_sheet.setdefault(key, {}).setdefault((row, column), []).append((reference, field["text"]))
    facts = []
    for cells in by_sheet.values():
        headers: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for (row, column), entries in cells.items():
            if row != scope["rowStart"] or len(entries) != 1:
                continue
            reference, text = entries[0]
            role = _header_role(text)
            if folded(text).strip() in {"role / condition", "role / conditions"}:
                role = "condition"
            if role:
                headers.setdefault(role, []).append((column, reference))
        needed = {"parameter", "minimum", "maximum", "unit"}
        if any(len(headers.get(role, [])) != 1 for role in needed) or any(len(value) > 1 for value in headers.values()):
            continue
        for row in sorted({row for row, _ in cells if row > scope["rowStart"]}):
            bindings = {role: cells.get((row, choices[0][0]), []) for role, choices in headers.items()}
            if any(len(bindings[role]) != 1 for role in needed):
                continue
            label = bindings["parameter"][0][1]
            if not (re.search(QUANTITIES[quantity], folded(label)) or _properties(label, quantity)):
                continue
            unit = UNIT_ALIASES.get(bindings["unit"][0][1].strip(), bindings["unit"][0][1].strip())
            if not unit or unit not in UNITS or UNITS[unit][0] != quantity:
                continue
            low_reference, low_text = bindings["minimum"][0]
            high_reference, high_text = bindings["maximum"][0]
            try:
                low, low_unit = parse_quantity(low_text + " " + unit, typed_number=low_reference["cell_facts"].get("value_kind") == "number")
                high, high_unit = parse_quantity(high_text + " " + unit, typed_number=high_reference["cell_facts"].get("value_kind") == "number")
            except CalculationRefusal:
                continue
            if low_unit != high_unit or low > high:
                continue
            condition = bindings["condition"][0][1] if len(bindings.get("condition", [])) == 1 else ""
            if "condition" in headers and not condition:
                continue  # do not discard a declared but missing condition
            used = ["parameter", "minimum", "maximum", "unit", *(["condition"] if "condition" in headers else [])]
            dependencies = [ref for role in used for ref in (headers[role][0][1], bindings[role][0][0])]
            quote = " ; ".join(f"{role} = {bindings[role][0][1]}" for role in ("parameter", "minimum", "maximum", "unit", "condition") if role in used)
            fact = _relation(low_reference, quantity=quantity, role=_role(label + " " + condition), values=[low, high], unit=unit,
                             label=label, condition=condition, quote=quote, kind="interval", subjects=subjects,
                             dependency_ids=[ref["id"] for ref in dependencies])
            fact["cell_range_bound"] = True
            fact["source_ids"] = list(dict.fromkeys(source_id for ref in dependencies for source_id in ref["source_ids"]))
            facts.append(fact)
    return facts


def _agreement_requested(question: str, quantity: str | None) -> bool:
    """Recognize equality asked of the quantity, not merely of its conditions.

    Only existing quantity/property/role labels and short grammatical words may
    separate ``same``/``même`` from the quantity. No domain synonym or entity is
    supplied by this intent check.
    """
    if quantity is None:
        return False
    normalized = folded(question)
    quantity_matches = list(re.finditer(QUANTITIES[quantity], normalized))
    same_matches = list(re.finditer(r"\b(?:memes?|same)\b", normalized))
    removable = [*ROLES.values(), *QUANTITY_PROPERTIES.get(quantity, {}).values(),
                 r"\b(?:le|la|les|l|de|du|des|d|est|sont|il|ils|elle|elles|the|is|are|for)\b"]
    removable.extend(r"(?<!\w)" + re.escape(match[0]) + r"(?!\w)" for match in SUBJECT.finditer(normalized)
                     if any(char.isdigit() for char in match[0]) and match[0] not in NOT_SUBJECTS)
    for same in same_matches:
        for measured in quantity_matches:
            between = (normalized[same.end():measured.start()] if same.end() <= measured.start()
                       else normalized[measured.end():same.start()])
            for pattern in removable:
                between = re.sub(pattern, " ", between)
            if not between.strip(" \t'’-"):
                return True
    return False


def _conflicting_relations(facts: list[dict[str, Any]], *, cross_document=False, agreement_requested=False) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for fact in facts:
        key = (fact["document_id"], fact["quantity"], fact["role"], fact["label"], fact["condition"], fact["kind"],
               fact.get("code"), fact.get("code_name"), fact.get("bound_role"), tuple(fact.get("entity_context_identifiers", fact.get("evidence_identifiers", []))))
        groups.setdefault(key, []).append(fact)
    for group in groups.values():
        values = {(_base_values(fact), UNITS[fact["unit"]][0]) for fact in group}
        if len(values) > 1:
            conflicts.append({"requirement": "same_label_conflicting_values",
                              "reference_ids": list(dict.fromkeys(fact["reference_id"] for fact in group)),
                              "quotes": [fact["quote"] for fact in group]})
    if cross_document or agreement_requested:
        # A direct value request cannot silently choose among two documents
        # naming the same entity. Anonymous quantities in different documents
        # are not presumed to refer to the same equipment. An explicit compare
        # request reports the divergence through _comparisons instead. An
        # explicit equality question also needs a discrepancy notice when the
        # exact label and condition carry different numbers; a missing role is
        # preserved as unknown and cannot establish a positive agreement.
        external: dict[tuple, list[dict[str, Any]]] = {}
        for fact in facts:
            identifiers = tuple(fact.get("entity_context_identifiers", fact.get("evidence_identifiers", [])))
            if len(identifiers) > 1 or fact["role"] is None and not agreement_requested:
                continue
            external_key = (identifiers, fact["quantity"], fact["role"], fact["label"], _condition_key(fact["condition"]),
                            fact["kind"], fact.get("code"), fact.get("code_name"), fact.get("bound_role"))
            external.setdefault(external_key, []).append(fact)
        for group in external.values():
            if len({fact["document_id"] for fact in group}) < 2 or len({_base_values(fact) for fact in group}) < 2:
                continue
            entity_known = bool(group[0].get("entity_context_identifiers", group[0].get("evidence_identifiers")))
            role_established = all(fact["role"] is not None or fact.get("bound_role") is not None for fact in group)
            conflicts.append({"requirement": ("same_entity_cross_document_conflicting_values" if entity_known and role_established else
                                               "same_label_cross_document_value_discrepancy"),
                              "document_ids": list(dict.fromkeys(fact["document_id"] for fact in group)),
                              "reference_ids": list(dict.fromkeys(reference_id for fact in group for reference_id in fact["reference_ids"])),
                              "quotes": [fact["quote"] for fact in group], "precedence_inferred": False,
                              "entity_identity_established": entity_known, "role_established": role_established})
    return conflicts


def _base_values(fact):
    # Inputs have at most 24 digits and bounded exponents. This precision keeps
    # every finite scale/offset digit for signatures, unlike Decimal's ambient
    # default context. Answer calculations still report their own rounding.
    with localcontext() as context:
        context.prec = 96
        return tuple((Decimal(value) * Decimal(UNITS[fact["unit"]][1]) + Decimal(UNITS[fact["unit"]][2])).normalize()
                     for value in fact["values"])


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
    requested_codes: list[str] = field(init=False)
    distinguish_roles: bool = field(init=False)
    comparison_requested: bool = field(init=False)
    agreement_requested: bool = field(init=False)
    requested_roles: list[str] = field(init=False)
    required_relation_count: int = field(init=False)
    requested_condition: tuple | None = field(init=False)
    operating_guarantee_requested: bool = field(init=False)
    requested_bound: str | None = field(init=False)
    requested_point_conditions: list[dict[str, Any]] = field(init=False)
    requested_temperature_conditions: bool = field(init=False)
    qualitative_request: dict[str, Any] | None = field(init=False)

    def __post_init__(self):
        normalized = folded(self.question)
        self.qualitative_request = _qualitative_request(self.question)
        quantities = _requested_quantities(normalized)
        self.quantity = quantities[0] if len(quantities) == 1 else None
        if (self.quantity and (self.qualitative_request is None or self.qualitative_request["intent"] == "field")
                and re.search(r"\b(?:pourquoi|why|expliqu\w*|explain\w*|comment|raisons?|reasons?)\b"
                              r"|\bhow\s+(?:does|do|can|could|would|should|is|are|to)\b", normalized)):
            # An unrecognized explanatory question must not be reduced to the
            # mere presence of a numeric quantity. No causal/method relation is
            # inferred; the literal sources and the missing explanation remain.
            self.qualitative_request = {"intent": "explanation", "language": "unknown",
                                        "target": _literal_key(self.question), "grammar_supported": False}
        self.requested_temperature_conditions = (self.quantity == "voltage"
                                                 and bool(TEMPERATURE_CONDITION_ATTACHMENT.search(normalized)))
        self.requested_properties = _properties(self.question, self.quantity or "")
        self.requested_bound = _bound_role(self.question)
        self.requested_point_conditions = _condition_measures(self.question)
        self.scope_read_requested = bool(SCOPE_READ_LANGUAGE.search(normalized))
        self.unit_requested = bool(UNIT_LANGUAGE.search(normalized))
        self.requested_role = _role(self.question)
        self.requested_roles = [role for role, pattern in ROLES.items() if re.search(pattern, normalized)]
        self.distinguish_roles = bool(re.search(r"\b(?:confond\w*|separe\w*|distinct\w*|disting\w*)\b", normalized)
                                      and re.search(r"\b(?:conditions?|roles?|limites?|absolute|absolu\w*)\b", normalized))
        if self.distinguish_roles:
            self.requested_role = None
            self.requested_roles = [role for role in self.requested_roles if role != "characterization"]
        if len(self.requested_roles) > 1:
            self.requested_role = None
        self.operating_guarantee_requested = ("absolute_maximum" in self.requested_roles
                                             and bool(re.search(r"\b(?:garanti\w*|guarantee\w*)\b", normalized))
                                             and bool(re.search(r"\b(?:fonctionnement|operation|operating)\b", normalized)))
        counts = re.findall(r"\b(deux|trois|quatre|two|three|four|[2-4])\s+(?:plages?|ranges?)\b", normalized)
        self.required_relation_count = {"deux": 2, "two": 2, "trois": 3, "three": 3, "quatre": 4, "four": 4}.get(
            counts[0], int(counts[0]) if counts and counts[0].isdigit() else 1) if counts else 1
        self.agreement_requested = _agreement_requested(self.question, self.quantity)
        self.comparison_requested = (self.mode == "comparison" or bool(COMPARISON_LANGUAGE.search(normalized))
                                     or self.agreement_requested)
        self.operation, self.target_unit = _operation(self.question)
        self.requested_condition = None
        conditional = re.search(r"\b(?:pour|for)\s+([A-Z][A-Z0-9_+]{0,10})\s+(?:(?:de|from)\s+)?", self.question)
        if conditional:
            bound = RANGE_VALUE.match(self.question[conditional.end():])
            if bound:
                self.requested_condition = _condition_key(conditional[1] + " " + bound[0])
        self.requested_codes = list(dict.fromkeys(match[0] for match in re.finditer(r"(?<!\w)[01]{2,16}(?!\w)", self.question))) if (
            MAPPING_LANGUAGE.search(normalized) or self.operation == "convert" and self.quantity == "time") else []
        self.configurations = list(dict.fromkeys((match[1].casefold(), match[2].casefold())
                                                 for match in CONFIGURATION.finditer(self.question)))
        explicit_cell_language = re.search(r"\b(?:cellules?|cells?)\b", normalized)
        cell_context = self.cell_context or self.scope.get("kind") in {"cell_range", "sheet"}
        self.requested_cells, self.parse_failures = _addresses(
            self.question, enabled=bool(explicit_cell_language or cell_context and CELL_LANGUAGE.search(normalized)))
        mentioned_cells = set(self.requested_cells)
        if self.quantity and not self.operation and not self.parse_failures and self.scope.get("kind") == "cell_range":
            scoped_range = CELL_RANGE.search(self.question)
            if scoped_range and re.search(r"\bdans\s+la\s+plage\s+selectionnee\s*$", folded(self.question[:scoped_range.start()])):
                bounds = range_coordinates(scoped_range[1] + ":" + scoped_range[2])
                if list(bounds) == [self.scope.get(key) for key in ("rowStart", "columnStart", "rowEnd", "columnEnd")]:
                    self.requested_cells = []
        self.requested_field = "formula" if re.search(r"\b(?:formule|formula)\b", normalized) and not re.search(
            r"\b(?:resultat|result|valeur|value|calcul\w*)\b", normalized) else "value"
        self.subjects = tuple(dict.fromkeys(match[0] for match in SUBJECT.finditer(self.question)
                                           if any(char.isdigit() for char in match[0])
                                           and match[0].upper() not in mentioned_cells
                                           and match[0].casefold() not in NOT_SUBJECTS))
        if (self.qualitative_request is not None
                and (self.qualitative_request["intent"] in {"cause", "condition", "explanation"}
                     or not self.quantity and not self.operation and not self.requested_cells and not self.comparison_requested)):
            self.kind = "qualitative"
        elif self.operation and self.requested_cells:
            self.kind = "calculation"
        elif self.operation and self.operation != "difference":
            self.kind = "calculation"
        elif INTERVAL_LANGUAGE.search(normalized) and self.quantity:
            self.kind = "interval"
        elif (self.comparison_requested
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
        if self.kind != "qualitative":
            self.qualitative_request = None
        if len(quantities) > 1 and self.kind != "qualitative":
            self.parse_failures.append("multiple_quantities_not_decomposed")

    def scope_refusal(self) -> dict[str, Any] | None:
        """Reject only a scope mismatch established by pinned scope metadata.

        OOXML part names and retained text are not evidence of sheet order. The
        builder supplies the actual extraction unit ordinal after DB validation.
        """
        if self.scope.get("kind") not in {"sheet", "cell_range"}:
            return None
        normalized = folded(self.question)
        sheet = self.scope.get("authorized_sheet") or {}
        ordinal_words = {"premiere": 1, "premier": 1, "first": 1, "deuxieme": 2, "seconde": 2,
                         "second": 2, "troisieme": 3, "third": 3, "quatrieme": 4, "fourth": 4}
        ordinal_match = re.search(r"\b(" + "|".join(ordinal_words) + r")\s+(?:feuille|sheet)\b", normalized)
        digit_match = re.search(r"\b(?:feuille|sheet)\s+(?:numero\s+|number\s+|n°\s*|#\s*)([1-9][0-9]*)\b", normalized)
        ordinal = ordinal_words[ordinal_match[1]] if ordinal_match else int(digit_match[1]) if digit_match else None
        if ordinal is not None and type(sheet.get("ordinal")) is int and ordinal != sheet["ordinal"]:
            return {"reason": "requested_sheet_outside_scope", "requested_ordinal": ordinal,
                    "authorized_sheet": sheet,
                    "message": f"La question demande la feuille {ordinal}, mais le périmètre sélectionné autorise seulement "
                               f"la feuille {sheet['ordinal']} ({sheet.get('name', sheet.get('id', ''))}). "
                               "Son contenu extérieur n'a pas été consulté ; élargissez la sélection à cette feuille pour y répondre."}
        name_match = re.search(r"\b(?:feuille|sheet)\s+(?:(?:nommée|named)\s+)?(?:[\"«“]([^\"»”]+)[\"»”]|([\w][\w -]*))",
                               self.question, re.IGNORECASE) if ordinal is None else None
        requested_name = (name_match[1] or name_match[2]).strip() if name_match else None
        if requested_name and name_match is not None and not name_match[1]:
            if self.operation == "convert" and self.target_unit:
                requested_name = re.sub(rf"\s+(?:en|into|to)\s+(?:{UNIT_PATTERN}|{'|'.join(UNIT_WORDS)})\s*$",
                                        "", requested_name, flags=re.IGNORECASE).strip()
            if folded(requested_name) in {"selectionnee", "selected", "active", "courante", "current", "du classeur"}:
                requested_name = None
        if requested_name and sheet.get("name") and requested_name.casefold() != sheet["name"].casefold():
            if re.match(re.escape(sheet["name"]) + r"\s", requested_name, re.IGNORECASE):
                return {"reason": "requested_sheet_not_unambiguous", "requested_name": requested_name,
                        "authorized_sheet": sheet,
                        "message": f"Le nom demandé « {requested_name} » ne correspond pas univoquement à la feuille "
                                   f"sélectionnée « {sheet['name']} ». Aucune valeur n'est attribuée à une autre feuille ; "
                                   "précisez le nom exact ou adaptez le périmètre sélectionné."}
            return {"reason": "requested_sheet_outside_scope", "requested_name": requested_name,
                    "authorized_sheet": sheet,
                    "message": f"La question demande la feuille {requested_name}, mais le périmètre sélectionné autorise seulement "
                               f"la feuille {sheet['name']}. Son contenu extérieur n'a pas été consulté ; "
                               "élargissez la sélection à cette feuille pour y répondre."}
        bounds = [self.scope.get(key) for key in ("rowStart", "columnStart", "rowEnd", "columnEnd")]
        if self.scope.get("kind") == "cell_range" and all(type(value) is int for value in bounds):
            row_start, column_start, row_end, column_end = [cast(int, value) for value in bounds]
            outside = [address for address in self.requested_cells if not (
                row_start <= address_coordinates(address)[0] <= row_end
                and column_start <= address_coordinates(address)[1] <= column_end)]
            if outside:
                return {"reason": "requested_cells_outside_scope", "addresses": outside,
                        "message": "Les cellules demandées " + ", ".join(outside) +
                                   " sont en dehors du périmètre sélectionné. Leur contenu n'a pas été consulté ; "
                                   "élargissez la sélection pour les inclure."}
        return None

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

    def _fact_candidates(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.quantity is None or self.kind == "qualitative":
            return []
        facts: list[dict[str, Any]] = []
        def eligible(fact):
            return ((self.kind != "interval" or fact["kind"] == "interval")
                    and (self.requested_role is None or fact["role"] == self.requested_role
                         or fact.get("bound_role") == self.requested_role)
                    and (not self.requested_roles or fact["role"] in self.requested_roles
                         or fact.get("bound_role") in self.requested_roles))
        for reference in references:
            table_facts = _table_relations(reference, self.quantity, self.subjects, references)
            candidates = table_facts or list(_quantity_lines(reference, self.quantity, self.requested_role, self.subjects, references))
            facts.extend(fact for fact in candidates if eligible(fact))
        facts.extend(fact for fact in _cell_range_relations(references, self.scope, self.quantity, self.subjects) if eligible(fact))
        if self.requested_condition:
            facts = [fact for fact in facts if _condition_key(fact["condition"]) == self.requested_condition]
        return facts

    def _relation_rejections(self, fact):
        reasons = list(fact.get("note_issues", []))
        if fact.get("assertion_status", "asserted") != "asserted":
            reasons.append("source_assertion_" + fact["assertion_status"])
        if (self.requested_bound and fact["kind"] == "value"
                and fact.get("bound_role") != self.requested_bound):
            reasons.append("requested_bound_not_established")
        if self.requested_temperature_conditions and not _temperature_condition_present(fact["condition"]):
            reasons.append("requested_temperature_condition_not_established")
        available = _condition_measures(fact["condition"])
        for requested in self.requested_point_conditions:
            if not any(point["quantity"] == requested["quantity"] and point["value"] == requested["value"]
                       and (not requested["symbol"] or requested["symbol"] == point["symbol"])
                       for point in available):
                reasons.append("requested_condition_not_established")
                break
        return reasons

    def _facts(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [fact for fact in self._fact_candidates(references) if not self._relation_rejections(fact)]

    def _rejected_relations(self, references):
        rejected = []
        for fact in self._fact_candidates(references):
            if self.subjects and not any(subject in fact["subjects"] for subject in self.subjects):
                continue
            if self.requested_properties and fact.get("property") not in self.requested_properties:
                continue
            reasons = self._relation_rejections(fact)
            if reasons:
                rejected.append({"reference_ids": fact["reference_ids"], "source_ids": fact["source_ids"],
                                 "quote": fact["quote"], "condition": fact["condition"], "reasons": reasons})
        return rejected

    def _conditions(self, references):
        if not self.distinguish_roles or not re.search(r"\bconditions?\b", folded(self.question)):
            return []
        named = re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", self.question)
        return [fact for reference in references for fact in _table_conditions(reference, references)
                if any(_contains_subject(fact["label"], token) for token in named)]

    def _operating_limitations(self, references):
        if not self.operating_guarantee_requested:
            return []
        facts = []
        for reference in references:
            text = reference_text(reference)
            normalized = folded(text)
            if (re.search(ROLES["absolute_maximum"], normalized)
                    and re.search(r"\b(?:do(?:es)?\s+not\s+imply\s+functional\s+operation|"
                                  r"ne\s+garanti\w*[^.!?]{0,60}\bfonctionnement)\b", normalized)):
                facts.append({"kind": "operating_guarantee_limitation", "reference_id": reference["id"],
                              "reference_ids": [reference["id"]], "source_ids": reference["source_ids"],
                              "document_id": reference["document_id"], "quote": text})
        return facts

    def _code_facts(self, references):
        facts = [fact for fact in self._facts(references) if fact.get("code") in self.requested_codes and fact["kind"] == "value"]
        names: set[str] = {fact["code_name"] for fact in facts if isinstance(fact.get("code_name"), str) and fact["code_name"]}
        explicitly_named = {name for name in names if _contains_subject(self.question, name)}
        if explicitly_named:
            facts = [fact for fact in facts if fact.get("code_name") in explicitly_named]
        return facts

    def relation_calculations(self, references):
        if self.operation != "convert" or self.requested_cells or not self.requested_codes:
            return []
        if not self.target_unit:
            raise CalculationRefusal("unit_missing", "La conversion exige une unité cible explicite.")
        facts = self._code_facts(references)
        results = []
        for code in self.requested_codes:
            candidates = [fact for fact in facts if fact["code"] == code]
            if len(candidates) != 1:
                raise CalculationRefusal("code_quantity_missing_or_ambiguous",
                                         f"Le code {code} n'est pas relié à une durée unique avec son unité dans les preuves retenues.")
            results.append(convert_relation(candidates[0], self.target_unit))
        return results

    def _obligations(self, facts, required_documents=()):
        """One independently checkable obligation per property/document/subject."""
        if not self.quantity or self.kind in {"cell_values", "calculation", "mapping", "qualitative"}:
            return []
        documents = list(dict.fromkeys(required_documents)) or [None]
        properties: list[str | None] = list(self.requested_properties) or [None]
        subjects = self.subjects or (None,)
        roles: list[str | None] = list(self.requested_roles) or [None]
        obligations = []
        for document in documents:
            for subject in subjects:
                for property_name in properties:
                    for requested_role in roles:
                        matching = [fact for fact in facts if (document is None or fact["document_id"] == document)
                                    and (subject is None or subject in fact["subjects"])
                                    and (property_name is None or fact.get("property") == property_name)
                                    and (requested_role is None and fact["role"] != "characterization"
                                         or requested_role is not None and requested_role in {fact["role"], fact.get("bound_role")} )]
                        count = len({(_base_values(fact), _condition_key(fact["condition"]), fact["role"], fact.get("bound_role")) for fact in matching})
                        obligations.append({"document_id": document, "subject": subject, "property": property_name,
                                            "quantity": self.quantity, "role": requested_role,
                                            "kind": "interval" if self.kind == "interval" else "value_or_interval",
                                            "covered": count >= self.required_relation_count,
                                            "expected_count": self.required_relation_count, "matched_count": count,
                                            "reference_ids": list(dict.fromkeys(reference_id for fact in matching
                                                                                for reference_id in fact.get("reference_ids", [fact["reference_id"]])))})
        return obligations

    def _comparisons(self, facts, required_documents=()):
        if not self.comparison_requested or not self.quantity:
            return []
        documents = list(dict.fromkeys(required_documents)) or list(dict.fromkeys(fact["document_id"] for fact in facts))
        if len(documents) < 2:
            return []
        result = []
        compared_properties: list[str | None] = list(self.requested_properties) or list(dict.fromkeys(fact.get("property") for fact in facts)) or [None]
        for subject in self.subjects or (None,):
            for property_name in compared_properties:
                groups = [[fact for fact in facts if fact["document_id"] == document
                           and (subject is None or subject in fact["subjects"])
                           and fact.get("property") == property_name] for document in documents]
                if any(not group for group in groups):
                    continue
                # Subjects, roles and conditions remain attached to values. An
                # equal set of anonymous numbers cannot prove a comparison.
                def local_context(fact):
                    return (fact["kind"], fact["property"] or fact["label"], fact["role"], fact.get("bound_role"),
                            _condition_key(fact["condition"]), fact.get("code_name"), fact.get("code"),
                            tuple(fact.get("entity_context_identifiers", fact.get("evidence_identifiers", []))))
                preserve_labels = subject is None and any(len({local_context(fact) for fact in group}) < len(group) for group in groups)
                def identity(fact, keep_labels=preserve_labels):
                    return (*local_context(fact), fact["label"] if keep_labels else None)
                def values(fact):
                    return _base_values(fact)
                signatures = [{(identity(fact), values(fact)) for fact in group} for group in groups]
                contexts = [{signature[0] for signature in group} for group in signatures]
                same_context = all(group == contexts[0] for group in contexts[1:])
                known_roles = all(fact["role"] is not None or fact.get("bound_role") is not None for group in groups for fact in group)
                numeric = [{(fact["kind"], fact["property"] or fact["label"], _condition_key(fact["condition"]),
                             fact.get("code_name"), fact.get("code"), tuple(fact.get("entity_context_identifiers", fact.get("evidence_identifiers", []))),
                             fact["label"] if preserve_labels else None, values(fact)) for fact in group} for group in groups]
                agreement = "equal" if all(group == numeric[0] for group in numeric[1:]) else "different"
                status = ("context_unestablished" if not known_roles else "context_differs" if not same_context
                          else "equal" if all(group == signatures[0] for group in signatures[1:]) else "different")
                result.append({"property": property_name, "subject": subject, "quantity": self.quantity,
                               "document_ids": documents, "status": status, "numeric_agreement": agreement,
                               "conditions_explicit": all(fact["condition"].strip(" .;") for group in groups for fact in group),
                               "reference_ids": list(dict.fromkeys(reference_id for group in groups for fact in group
                                                                  for reference_id in fact.get("reference_ids", [fact["reference_id"]])))})
        return result

    def _mappings(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        facts = []
        for reference in references:
            for line in reference_text(reference).splitlines():
                if _assertion_status(line) != "asserted":
                    continue
                for match in MAPPING_RELATION.finditer(line):
                    configuration = (match["key"].casefold(), match["value"].casefold())
                    if configuration in self.configurations:
                        facts.append({"reference_id": reference["id"], "document_id": reference["document_id"],
                                      "source_ids": reference["source_ids"], "kind": "mapping",
                                      "configuration": list(configuration), "code": match["code"], "quote": line})
        return facts

    def required_ids(self, references: list[dict[str, Any]], required_documents=()) -> list[str]:
        if self.scope_refusal():
            return []
        if self.qualitative_request is not None:
            # The model cannot hide a literal negation, qualification or
            # contradiction by selecting only the favourable statement.
            return list(dict.fromkeys(item["reference_id"] for item in
                                      _qualitative_relations(self.qualitative_request, references)))
        by_address, requested = self._cells(references)
        required = [by_address[address][0]["id"] for address in requested if len(by_address.get(address, [])) == 1]
        facts = self._facts(references)
        for obligation in self._obligations(facts, required_documents):
            required.extend(obligation["reference_ids"])
        if self.requested_codes:
            required.extend(reference_id for fact in self._code_facts(references) for reference_id in fact["reference_ids"])
        required.extend(reference_id for fact in self._conditions(references) for reference_id in fact["reference_ids"])
        required.extend(fact["reference_id"] for fact in self._operating_limitations(references))
        if self.comparison_requested:
            for reference in references:
                text = folded(reference_text(reference))
                if (re.search(r"\b(?:derive\w*|derived)\b", text) and re.search(r"\b(?:provien\w*|source\w*|fiche|from)\b", text)
                        or re.search(r"\b(?:syntheti\w*|synthetic|ficti\w*)\b", text)
                        and re.search(r"\b(?:temoin|test|specification|source|document)\b", text)):
                    required.append(reference["id"])
        for conflict in _conflicting_relations(facts, cross_document=not self.comparison_requested,
                                              agreement_requested=self.agreement_requested):
            required.extend(conflict["reference_ids"])
        for configuration in self.configurations:
            required.extend(fact["reference_id"] for fact in self._mappings(references)
                            if tuple(fact["configuration"]) == configuration)
        return list(dict.fromkeys(required))

    def prompt(self, references: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind, "quantity": self.quantity, "requested_role": self.requested_role,
                  "requested_bound": self.requested_bound, "requested_point_conditions": self.requested_point_conditions,
                  "requested_cells": self.requested_cells, "requested_field": self.requested_field, "requested_subjects": list(self.subjects),
                  "requested_properties": self.requested_properties,
                  "requested_configurations": [list(configuration) for configuration in self.configurations],
                  "requested_codes": self.requested_codes,
                  "obligations": self._obligations(self._facts(references)),
                  "required_reference_ids": self.required_ids(references),
                  "coverage_scope": "retained_catalogue_only"}
        if self.qualitative_request is not None:
            result["qualitative_request"] = self.qualitative_request
            result["qualitative_relations"] = _qualitative_relations(self.qualitative_request, references)
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
            if self.operation == "convert" and self.requested_codes:
                return None
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

    def _assess_qualitative(self, references, selected_ids, required_documents):
        assert self.qualitative_request is not None
        selected_set = set(selected_ids) if selected_ids is not None else {item["id"] for item in references}
        selected = [item for item in references if item["id"] in selected_set]
        relations = _qualitative_relations(self.qualitative_request, references)
        matched = [item for item in relations if not item["reasons"] and item["reference_id"] in selected_set]
        rejected = [item for item in relations if item["reasons"]]
        conflicts = _qualitative_conflicts(relations)
        missing = [{"requirement": reason} for reason in self.parse_failures]
        ambiguous = []
        for item in rejected:
            for reason in item["reasons"]:
                if reason in {"qualitative_pronoun_unresolved", "qualitative_source_uncertain", "qualitative_clause_ambiguous"}:
                    ambiguous.append({"requirement": reason, "reference_ids": item["reference_ids"]})
                elif reason == "qualitative_source_span_incomplete" or not matched:
                    missing.append({"requirement": reason, "reference_ids": item["reference_ids"]})
        if not self.qualitative_request["grammar_supported"]:
            missing.append({"requirement": "qualitative_question_grammar_not_supported"})
        if not matched:
            missing.append({"requirement": "qualitative_" + self.qualitative_request["intent"] + "_not_established",
                            "stage": "selection" if any(not item["reasons"] for item in relations) else "context"})
        obligations = []
        for document in list(dict.fromkeys(required_documents)) or [None]:
            matching = [item for item in matched if document is None or item["document_id"] == document]
            obligation = {"document_id": document, "subject": None, "property": self.qualitative_request["target"],
                          "quantity": None, "role": None, "kind": "qualitative_literal",
                          "covered": bool(matching), "expected_count": 1, "matched_count": len(matching),
                          "reference_ids": list(dict.fromkeys(item["reference_id"] for item in matching))}
            obligations.append(obligation)
            if document is not None and not matching:
                missing.append({"requirement": "requested_qualitative_document", **obligation})
        status = "conflict" if conflicts else "ambiguous" if ambiguous else "partial" if missing else "covered"
        return {"version": 1, "kind": self.kind, "status": status, "verification": VERIFICATION,
                "coverage_scope": "retained_catalogue_only", "limitation": LIMITATION,
                "quantity": self.quantity, "requested_role": self.requested_role,
                "requested_properties": self.requested_properties, "requested_cells": self.requested_cells,
                "requested_subjects": list(self.subjects), "qualitative_request": self.qualitative_request,
                "required_reference_ids": self.required_ids(references, required_documents),
                "missing": missing, "ambiguous": ambiguous, "conflicts": conflicts,
                "matched_relations": [], "rejected_relations": [],
                "matched_qualitative_relations": matched, "rejected_qualitative_relations": rejected,
                "obligations": obligations, "comparisons": [], "calculation": None, "derived_calculations": [],
                "selected_reference_ids": [item["id"] for item in selected]}

    def assess(self, references: list[dict[str, Any]], selected_ids: list[str] | None = None, required_documents=()) -> dict[str, Any]:
        refusal = self.scope_refusal()
        if refusal:
            return {"version": 1, "kind": self.kind, "status": "partial", "verification": VERIFICATION,
                    "coverage_scope": "retained_catalogue_only", "limitation": LIMITATION,
                    "quantity": self.quantity, "requested_role": self.requested_role,
                    "requested_properties": self.requested_properties, "requested_cells": self.requested_cells,
                    "requested_subjects": list(self.subjects), "required_reference_ids": [],
                    "missing": [{"requirement": refusal["reason"], "message": refusal["message"]}],
                    "ambiguous": [], "conflicts": [], "matched_relations": [], "obligations": [],
                    "comparisons": [], "calculation": None, "selected_reference_ids": [], "scope_refusal": refusal}
        if self.qualitative_request is not None:
            return self._assess_qualitative(references, selected_ids, required_documents)
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
        incomplete_groups = {}
        for fact in facts:
            binding = fact.get("list_binding")
            if binding and not binding["catalogue_group_complete"]:
                incomplete_groups[(fact["generation_id"], binding["group_id"])] = binding
        missing.extend({"requirement": "list_group_incomplete", "group_id": binding["group_id"],
                        "expected_items": binding["item_count"], "visible_items": binding["visible_item_count"],
                        "verified_items": binding["verified_item_count"]} for binding in incomplete_groups.values())
        rejected = self._rejected_relations(references)
        for item in rejected:
            if "source_assertion_uncertain" in item["reasons"]:
                ambiguous.append({"requirement": "source_assertion_uncertain", "reference_ids": item["reference_ids"],
                                  "source_ids": item["source_ids"], "raw_text_preserved": True})
        if not facts:
            for reason in dict.fromkeys(reason for item in rejected for reason in item["reasons"]):
                if reason != "source_assertion_uncertain":
                    missing.append({"requirement": reason})
        conditions = self._conditions(selected)
        limitations = self._operating_limitations(selected)
        if self.operating_guarantee_requested and not limitations:
            missing.append({"requirement": "absolute_limit_operating_guarantee_not_established"})
        if self.distinguish_roles and re.search(r"\bconditions?\b", folded(self.question)) and not conditions:
            missing.append({"requirement": "requested_test_condition"})
        obligations = self._obligations(facts, required_documents)
        missing_obligations = [obligation for obligation in obligations if not obligation["covered"]]
        missing.extend({"requirement": "requested_property_document", **obligation} for obligation in missing_obligations)
        if missing_obligations and len(self.requested_properties) > 1:
            # Kept as a stable machine-readable reason for older API clients;
            # the explicit missing obligations now identify what remains absent.
            missing.append({"requirement": "multiple_properties_not_decomposed"})
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
            if self.requested_role is None and not self.requested_roles and not self.distinguish_roles and len({fact["role"] for fact in facts if fact["role"]}) > 1:
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
        conflicts = _conflicting_relations(self._facts(references), cross_document=not self.comparison_requested,
                                           agreement_requested=self.agreement_requested)
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
        derived_calculations = []
        if self.kind == "calculation":
            try:
                calculation = self.calculation(selected)
                derived_calculations = self.relation_calculations(selected)
            except CalculationRefusal as error:
                missing.append({"requirement": error.code, "message": error.message})
        comparisons = self._comparisons(facts, required_documents)
        if self.agreement_requested and not comparisons:
            missing.append({"requirement": "comparison_context_not_established"})
        for comparison in comparisons:
            if comparison["status"] == "context_unestablished":
                missing.append({"requirement": "comparison_role_not_established", "subject": comparison["subject"],
                                "property": comparison["property"], "reference_ids": comparison["reference_ids"]})
            elif comparison["status"] == "context_differs":
                missing.append({"requirement": "comparison_context_differs", "subject": comparison["subject"],
                                "property": comparison["property"], "reference_ids": comparison["reference_ids"]})
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
                "requested_bound": self.requested_bound, "requested_point_conditions": self.requested_point_conditions,
                "requested_temperature_conditions": self.requested_temperature_conditions,
                "requested_properties": self.requested_properties,
                "required_reference_ids": self.required_ids(references, required_documents),
                "requested_cells": requested, "requested_subjects": list(self.subjects),
                "missing": missing, "ambiguous": ambiguous, "conflicts": conflicts,
                "matched_relations": [*facts, *mappings, *conditions, *limitations], "calculation": calculation,
                "rejected_relations": rejected,
                "derived_calculations": derived_calculations,
                "obligations": obligations, "comparisons": comparisons,
                "selected_reference_ids": [reference["id"] for reference in selected]}


def assessment_message(assessment: dict[str, Any]) -> str | None:
    if assessment.get("scope_refusal"):
        return assessment["scope_refusal"]["message"]
    status = assessment["status"]
    if assessment.get("qualitative_request"):
        reasons = {item["requirement"] for item in [*assessment["missing"], *assessment["ambiguous"]]}
        if status == "conflict":
            return ("Les sources donnent des formulations divergentes pour le même sujet et la même propriété littérale. "
                    "Elles sont citées séparément ; aucune priorité entre documents ou versions n'est déduite.")
        if status == "ambiguous":
            if "qualitative_pronoun_unresolved" in reasons:
                return "Le référent du pronom n'est pas établi dans les passages retenus. Aucun sujet n'est attribué par supposition."
            if "qualitative_source_uncertain" in reasons:
                return "Le passage comporte une réserve d'incertitude. Sa formulation est conservée ; aucune affirmation certaine n'en est déduite."
            return ("Les contrôles ne relient pas sans ambiguïté toute la formulation source à la question. "
                    "Les passages sont conservés intégralement, sans interprétation supplémentaire.")
        if status == "partial":
            if "qualitative_source_span_incomplete" in reasons:
                return "Le passage source complet n'est pas vérifié dans le contexte retenu. Une éventuelle réserve extérieure à l'extrait ne peut pas être écartée."
            intent = assessment["qualitative_request"]["intent"]
            if intent == "cause":
                return "L'explication causale demandée n'est pas explicitement établie dans les passages retenus. Aucune cause supplémentaire n'est ajoutée."
            if intent == "explanation":
                return "L'explication demandée n'est pas établie par les passages retenus. Une valeur isolée ne suffit pas à la justifier ; aucune explication supplémentaire n'est ajoutée."
            if intent == "condition":
                return "La condition demandée pour le sujet et la propriété de la question n'est pas établie dans les passages retenus. Les formulations sources, y compris leurs négations, sont conservées."
            return "Le champ demandé n'est pas établi dans les passages retenus. Aucune valeur manquante n'est supposée."
    if status == "conflict":
        return "Les extraits retenus donnent des valeurs différentes pour un même libellé et une même condition. Les sources sont restituées séparément ; aucune valeur n'est arbitrée."
    if status == "ambiguous":
        if any(item["requirement"] == "source_assertion_uncertain" for item in assessment["ambiguous"]):
            return "La source qualifie une donnée d'incertaine ou d'approximative. Cette réserve est conservée ; aucune valeur certaine n'en est déduite."
        return "Une ambiguïté subsiste dans les preuves retenues (lecture, adresse ou rôle de la grandeur). Les données brutes sont conservées ; aucune correction n'est supposée."
    if status == "partial":
        if any(item["requirement"].startswith("list_") for item in assessment["missing"]):
            return ("La liste source ou ses réserves ne sont pas entièrement établies dans les passages retenus. "
                    "Les éléments vérifiés restent cités ; aucune complétude du groupe ni condition absente n'est supposée.")
        if any(item["requirement"].startswith("table_note_") for item in assessment["missing"]):
            return "Une note applicable au tableau est absente, ambiguë ou n'a pas pu être entièrement vérifiée. La valeur ne permet pas d'établir une réponse sans cette réserve."
        if any(item["requirement"] == "multiple_properties_not_decomposed" for item in assessment["missing"]):
            return "La demande porte sur plusieurs propriétés distinctes. Certaines propriétés ne sont pas établies pour chaque document demandé ; une seule plage ne suffit pas à toutes les couvrir."
        if assessment["kind"] == "calculation":
            if assessment.get("calculation") is not None:
                return "Le calcul ci-dessous utilise les entrées citées ; la couverture des autres éléments demandés reste partielle."
            reason = next((item["message"] for item in assessment["missing"] if item.get("message")), None)
            return ("Le calcul demandé n'est pas établi : " + reason if reason else
                    "Le calcul demandé ne peut pas être établi à partir d'entrées complètes et univoques dans les preuves retenues.")
        if any(item["requirement"] == "requested_unit_not_provided" for item in assessment["missing"]):
            return "L'unité demandée n'est pas établie par les champs des cellules retenues. Les valeurs brutes sont restituées ; aucune unité d'une cellule extérieure n'est supposée."
        if any(item["requirement"] == "requested_condition_not_established" for item in assessment["missing"]):
            return "Les preuves retenues n'établissent pas la valeur dans les conditions demandées. Les valeurs associées à d'autres conditions ne sont pas transposées."
        if any(item["requirement"] == "requested_temperature_condition_not_established" for item in assessment["missing"]):
            return "Les contrôles n'établissent pas toutes les conditions de température demandées dans les passages retenus. Les extraits sont conservés sans supposer de condition manquante."
        if any(item["requirement"] == "requested_bound_not_established" for item in assessment["missing"]):
            return "La borne demandée n'est pas établie. Une valeur typique, nominale ou dépourvue de rôle explicite ne permet pas de déduire ce minimum ou ce maximum."
        if any(item["requirement"] == "source_assertion_negated" for item in assessment["missing"]):
            return "Le passage contient une négation portant sur la donnée repérée. Son nombre n'est pas retenu comme valeur affirmée ; l'extrait conserve la formulation source."
        if assessment.get("quantity") and not assessment.get("matched_relations"):
            return "La grandeur demandée n'est pas établie par les preuves retenues dans le périmètre sélectionné. Je ne peux pas donner une valeur fiable à partir de cette sélection."
        if assessment["kind"] == "interval":
            return "La plage demandée n'est pas entièrement établie : les preuves retenues ne relient pas toutes les bornes, unités, grandeurs ou conditions demandées. Cela ne démontre pas l'absence de ces données dans les documents."
        return "Restitution partielle : certains faits demandés ne sont pas établis dans les preuves retenues. Cela ne démontre pas leur absence dans les documents."
    if status == "unassessed":
        return "Restitution littérale des sources. Les contrôles vérifient la provenance des extraits ; l'interprétation complète de la question reste à vérifier."
    return None
