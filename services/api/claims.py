"""Contrôles déterministes de la réponse générée (R26-ANS-01 et R26-ANS-02).

Ces contrôles ajoutent des avertissements au `done` ; ils ne suppriment ni ne réécrivent rien (W037 refuse tout filtre de
réponse). Ils s'appliquent au texte déjà validé par `validate_answer`, dont les citations valides sont des « [S001] »
unitaires. Le découpage est local à la phrase ou à la puce : une valeur et sa citation séparées par une phrase, une valeur
recopiée avec la mauvaise unité ou un nombre écrit en lettres échappent au contrôle ; ce n'est pas un verdict de justesse.
"""
import re
from collections.abc import Iterable, Iterator
from decimal import Decimal
from typing import Any

from .retrieval import identifier_spans

VALID_CITATION = re.compile(r"\[(S\d+)\]")
SOURCE_ID = re.compile(r"\bS\d+\b")
# Fin de phrase ou de proposition suivie d'un blanc, ou saut de ligne (puce, paragraphe) ; « 3.1 » ne coupe pas.
SEGMENT = re.compile(r"(?<=[.!?;])\s+|\n+")
# Citations en tête du segment suivant (« … 2.7 bar. » [S001] ») : elles concluent la phrase précédente.
LEADING_CITATIONS = re.compile(r"[\s»”\"')\]*_]*((?:\[S\d+\][\s,;.]*)+)")
# Entier, décimal à virgule ou point, milliers séparés par une espace (« 1 020 ») ; jamais une partie d'un mot ou de « 3.4.2 ».
NUMBER = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?(?![.,]?\d)")
PAGE_MENTION = re.compile(r"(?i)\b(?:pages?|pp?\.)\s*\d+(?:\s*(?:[-–—/,]|\bet\b|\band\b|\bà\b|\bto\b)\s*\d+)*")
LIST_MARKER = re.compile(r"(?m)^[ \t>*#_-]*(\d+)[.)](?=\s)")
# Références de lecture et rangs, jamais des valeurs : paragraphe (§ 4.3), ordinal (2e, 3ème, 1er, 2nde, 3rd), date.
SECTION_MENTION = re.compile(r"§\s*\d+(?:[.,]\d+)*")
ORDINAL = re.compile(r"(?i)(?<![\w.,])\d+(?:ères?|ers?|res?|èmes?|emes?|e|è|ndes?|nd|st|rd|th)(?!\w)")
# Une date répète le même séparateur : « 12.5-13.5 » est une plage de valeurs, pas une date.
DATE = re.compile(r"(?<![\w.,/-])(?:\d{1,2}([/.-])\d{1,2}\1\d{2,4}|\d{4}-\d{1,2}-\d{1,2})(?![\w/-])")
# Unité affichée avec la valeur (« 2.7 bar », « 14 N·m », « 0.2 L/min ») ; elle n'intervient pas dans la comparaison.
UNIT = re.compile(r"[ \u00a0\u202f]?(%|‰|°[CF]?|[A-Za-zµΩ]{1,8}(?:[·./-][A-Za-z]{1,8})?[²³]?)(?!\w)")
NOT_UNITS = frozenset("a à au aux d de des du en entre est et l la le les ou par pour sous soit sont sur avec dans contre vs x "
                      "and are at for in is of on or per the to".split())
# Une lettre isolée n'est retenue comme unité que si c'est un symbole d'unité courant (24 V, 5 A, 3 m, 1020 h).
SINGLE_LETTER_UNITS = frozenset("A V W m g s h l L K N J T".split())


def _listing(items: list[str], limit: int = 6) -> str:
    shown = items[:limit]
    if len(items) > limit:
        rest = len(items) - limit
        return ", ".join(shown) + f" et {rest} autre" + ("s" if rest > 1 else "")
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " et " + shown[-1]


def citation_format_warnings(text: str, known_ids: Iterable[str]) -> list[dict[str, Any]]:
    """R26-ANS-01 : réponse sans aucune citation valide, et identifiants de sources connus écrits sans crochets."""
    known = list(dict.fromkeys(known_ids))
    if any(source_id in known for source_id in VALID_CITATION.findall(text)):
        return []
    found = set(SOURCE_ID.findall(VALID_CITATION.sub(" ", text)))
    mentioned = [source_id for source_id in known if source_id in found]
    warnings: list[dict[str, Any]] = [{"code": "answer_without_valid_citation", "message":
        "La réponse ne contient aucune citation valide entre crochets : ses affirmations ne sont reliées à aucune source "
        "vérifiable. Contrôlez-les dans les sources listées avant de les utiliser."}]
    if mentioned:
        single = len(mentioned) == 1
        warnings.append({"code": "source_id_mentioned_without_citation", "source_ids": mentioned, "message":
            f"La réponse nomme {_listing(mentioned, len(mentioned))} sans crochets : " +
            ("cette mention n'est pas une citation et n'ouvre pas la source. Retrouvez cette source dans la liste pour vérifier la réponse."
             if single else
             "ces mentions ne sont pas des citations et n'ouvrent pas les sources. Retrouvez ces sources dans la liste pour vérifier la réponse.")})
    return warnings


def _values(token: str, groups: bool = False) -> frozenset[Decimal]:
    """Lectures possibles d'un nombre : « 3,1 » = 3.1 ; « 1,020 » ou « 1.020 » = 1.02 ou 1020 (séparateur de milliers).
    `groups` (côté sources, lecture permissive) : « 120 150 180 » vaut aussi 120, 150 et 180."""
    compact = re.sub(r"[ \u00a0\u202f]", "", token)
    parts = re.fullmatch(r"(\d+)(?:[.,](\d+))?", compact)
    assert parts is not None  # forme garantie par NUMBER
    whole, fraction = parts.group(1), parts.group(2)
    values = {Decimal(whole + "." + fraction) if fraction else Decimal(whole)}
    if fraction and len(fraction) == 3 and whole.lstrip("0") and compact == token:
        values.add(Decimal(whole + fraction))
    if groups and compact != token:
        values.update(value for group in re.split(r"[ \u00a0\u202f]", token) for value in _values(group))
    return frozenset(values)


def _masked(text: str) -> str:
    """Identifiants à lettres (DA-P02, QV-01, EN 50155, S001), mentions de page, balises de citation et numéros de liste
    remplacés par des blancs de même longueur : leurs chiffres ne sont pas des valeurs."""
    chars = list(text)
    spans = [(start, end) for start, end in identifier_spans(text) if any(char.isalpha() for char in text[start:end])]
    spans += [match.span() for pattern in (PAGE_MENTION, SECTION_MENTION, ORDINAL, DATE, VALID_CITATION) for match in pattern.finditer(text)]
    spans += [match.span(1) for match in LIST_MARKER.finditer(text)]
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _unit(text: str, position: int) -> str | None:
    match = UNIT.match(text, position)
    unit = match.group(1) if match else None
    if not unit or unit.casefold() in NOT_UNITS or (len(unit) == 1 and unit.isalpha() and unit not in SINGLE_LETTER_UNITS):
        return None
    return unit


def _numbers(text: str, scanned: str | None = None, groups: bool = False) -> Iterator[tuple[str, str | None, frozenset[Decimal]]]:
    for match in NUMBER.finditer(text if scanned is None else scanned):
        yield match.group(), _unit(text, match.end()), _values(match.group(), groups)


def _segments(text: str) -> list[tuple[int, int, list[str]]]:
    """Bornes des phrases ou puces du texte, avec les citations reprises de la tête du segment suivant : citations qui
    suivent une fin de phrase sur la même ligne, ou seules sur leur ligne. Une citation qui ouvre une ligne suivie d'un
    texte (« *   [S002] confirme… ») sert d'étiquette à cette puce et lui reste (campagne 2B DEV, DEV-038)."""
    bounds, start, new_line = [], 0, False
    for separator in SEGMENT.finditer(text):
        bounds.append((start, separator.start(), new_line))
        start, new_line = separator.end(), "\n" in separator.group()
    bounds.append((start, len(text), new_line))
    segments: list[tuple[int, int, list[str]]] = []
    for start, end, new_line in bounds:
        leading = LEADING_CITATIONS.match(text, start, end)
        if leading and segments and (not new_line or not text[leading.end():end].strip()):
            segments[-1][2].extend(VALID_CITATION.findall(leading.group(1)))
            start = leading.end()
        if text[start:end].strip():
            segments.append((start, end, []))
    return segments


def value_warnings(text: str, sources: list[dict[str, Any]], question: str | None = None) -> list[dict[str, Any]]:
    """R26-ANS-02 : chaque nombre de la réponse, hors identifiants, pages, paragraphes, rangs, dates, citations et numéros
    de liste, comparé en Decimal aux nombres des sources citées dans sa phrase, puis de toutes les sources retenues. Côté
    sources, tous les nombres comptent, groupes séparés par des espaces compris (lecture permissive). Une phrase sans
    citation n'est contrôlée que contre l'ensemble des sources et, si elle est fournie, la question : une abstention qui
    reprend la condition demandée (« à 20 °C ») n'est pas une valeur absente. Une phrase citée reste contrôlée sans elle."""
    order = [source["source_id"] for source in sources]
    held = {source["source_id"]: frozenset().union(*(values for _, _, values in _numbers(source.get("text") or "", groups=True)))
            for source in sources}
    asked = frozenset().union(*(values for _, _, values in _numbers(question, _masked(question)))) if question else frozenset()
    misattributed: dict[tuple[frozenset[Decimal], tuple[str, ...]], dict[str, Any]] = {}
    absent: dict[tuple[frozenset[Decimal], tuple[str, ...]], dict[str, Any]] = {}
    masked = _masked(text)
    for start, end, following in _segments(text):
        segment = text[start:end]
        cited = list(dict.fromkeys(source_id for source_id in VALID_CITATION.findall(segment) + following if source_id in held))
        cited_values = frozenset().union(*(held[source_id] for source_id in cited))
        for raw, unit, values in _numbers(segment, masked[start:end]):
            if values & cited_values:
                continue
            holders = [source_id for source_id in order if values & held[source_id]]
            if not cited and (holders or values & asked):
                continue
            item = {"value": raw + (" " + unit if unit else ""), "number": raw, "unit": unit, "cited_source_ids": cited}
            if holders:
                misattributed.setdefault((values, tuple(cited)), {**item, "holder_source_ids": holders})
            else:
                absent.setdefault((values, tuple(cited)), item)
    warnings: list[dict[str, Any]] = []
    if misattributed:
        items = list(misattributed.values())
        single = len(items) == 1
        described = [f"{item['value']} (citée {_listing(item['cited_source_ids'])}, présente dans {_listing(item['holder_source_ids'])})" for item in items]
        warnings.append({"code": "cited_value_not_in_cited_sources", "values": items, "message":
            ("Valeur absente des sources citées dans sa phrase mais présente dans d'autres sources retenues : " if single else
             "Valeurs absentes des sources citées dans leur phrase mais présentes dans d'autres sources retenues : ") + _listing(described) +
            (". Vérifiez sa source avant de l'utiliser." if single else ". Vérifiez la source de chaque valeur avant de les utiliser.")})
    if absent:
        items = list(absent.values())
        single = len(items) == 1
        warnings.append({"code": "value_not_in_context", "values": items, "message":
            ("Valeur absente de toutes les sources transmises au modèle : " if single else
             "Valeurs absentes de toutes les sources transmises au modèle : ") + _listing([item["value"] for item in items]) +
            (". Elle peut avoir été calculée, déduite ou mal reprise ; vérifiez-la avant de l'utiliser." if single else
             ". Elles peuvent avoir été calculées, déduites ou mal reprises ; vérifiez-les avant de les utiliser.")})
    return warnings


def answer_warnings(text: str, sources: list[dict[str, Any]], question: str | None = None) -> list[dict[str, Any]]:
    """Avertissements additifs d'une réponse générée sur des sources retenues (identifiants S001… et textes transmis) ;
    `question`, si elle est connue au point d'appel, sert seulement aux phrases sans citation (`value_warnings`)."""
    return citation_format_warnings(text, [source["source_id"] for source in sources]) + value_warnings(text, sources, question)
