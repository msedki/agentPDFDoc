"""Sparse SpreadsheetML extraction, without evaluating a workbook.

OOXML supplies exact values and formula caches. openpyxl's maintained
helpers supply format recognition, date conversion and shared-formula
translation; a second workbook/shared-string copy is never loaded.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Iterator, Mapping
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Protocol
from xml.etree.ElementTree import Element

from openpyxl.formula.tokenizer import Tokenizer, TokenizerError
from openpyxl.formula.translate import Translator, TranslatorError
from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format, is_timedelta_format
from openpyxl.utils.cell import get_column_letter
from openpyxl.utils.datetime import MAC_EPOCH, WINDOWS_EPOCH, from_excel
from openpyxl.utils.escape import unescape

from services.ingestion.errors import IngestionError

from .models import limit_error
from .opc import OfficePackage

SPREADSHEET_NAMESPACES = frozenset({
    "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "http://purl.oclc.org/ooxml/spreadsheetml/main",
})
CELL_ADDRESS = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,6})$")
MAX_ROW = 1_048_576
MAX_COLUMN = 16_384
DYNAMIC_ARRAY_NAMESPACE = "http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray"


class PackageReader(Protocol):
    """Minimal streaming surface, implemented by the common OPC preflight."""

    def iter_xml(self, part: str, events: tuple[str, ...] = ("end",)) -> Iterator[tuple[str, Element]]: ...


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def namespace(name: str) -> str:
    return name[1:].split("}", 1)[0] if name.startswith("{") else ""


def spreadsheet_child(element: Element, name: str) -> Element | None:
    return next((child for child in element if local_name(child.tag) == name
                 and namespace(child.tag) in SPREADSHEET_NAMESPACES), None)


def spreadsheet_children(element: Element, name: str) -> list[Element]:
    return [child for child in element if local_name(child.tag) == name
            and namespace(child.tag) in SPREADSHEET_NAMESPACES]


def address_coordinates(address: str) -> tuple[int, int]:
    match = CELL_ADDRESS.fullmatch(address)
    if not match:
        raise IngestionError("OFFICE_INVALID_CELL", "Une adresse de cellule XLSX est invalide.")
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - ord("A") + 1
    row = int(match[2])
    if row > MAX_ROW or column > MAX_COLUMN:
        raise IngestionError("OFFICE_INVALID_CELL", "Une cellule dépasse les limites du format XLSX.")
    return row, column


def range_coordinates(reference: str) -> tuple[int, int, int, int]:
    pieces = reference.replace("$", "").split(":")
    if len(pieces) not in (1, 2):
        raise IngestionError("OFFICE_INVALID_RANGE", "Une plage XLSX est invalide.")
    first = address_coordinates(pieces[0])
    last = address_coordinates(pieces[-1])
    if first[0] > last[0] or first[1] > last[1]:
        raise IngestionError("OFFICE_INVALID_RANGE", "Une plage XLSX est inversée.")
    return first[0], first[1], last[0], last[1]


def decode_xstring(raw: str) -> str:
    """Decode ST_Xstring once; escaped underscores must stay literal.

    openpyxl performs a single substitution on the original string. Joining
    valid UTF-16 surrogate pairs gives Unicode code points for JSON/offsets;
    an isolated surrogate is invalid content, never a replacement character.
    """
    if "_x" not in raw:
        return raw
    decoded = unescape(raw)
    try:
        return decoded.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le")
    except UnicodeError as exc:
        raise IngestionError("OFFICE_INVALID_XSTRING", "Une chaîne XLSX contient un échappement Unicode invalide.") from exc


def rich_text(element: Element) -> tuple[str, list[dict[str, Any]]]:
    """Extract visible rich text, preserving runs and excluding phonetics."""
    pieces: list[str] = []
    runs: list[dict[str, Any]] = []
    for child in element:
        if namespace(child.tag) not in SPREADSHEET_NAMESPACES:
            continue
        kind = local_name(child.tag)
        if kind == "t":
            raw = child.text or ""
            text = decode_xstring(raw)
            pieces.append(text)
            runs.append({"text": text, "raw_text": raw, "properties": {}})
        elif kind == "r":
            text_element = spreadsheet_child(child, "t")
            raw = text_element.text or "" if text_element is not None else ""
            text = decode_xstring(raw)
            properties = spreadsheet_child(child, "rPr")
            values = ({local_name(item.tag): dict(item.attrib) for item in properties}
                      if properties is not None else {})
            pieces.append(text)
            runs.append({"text": text, "raw_text": raw, "properties": values})
    return "".join(pieces), runs


def formula_references(formula: str | None) -> tuple[list[str], bool]:
    """Recognized operands only: this is not an Excel evaluation grammar."""
    if formula is None:
        return [], False
    try:
        tokens = Tokenizer("=" + formula.removeprefix("=")).items
    except (TokenizerError, IndexError, ValueError):
        return [], False
    references = list(dict.fromkeys(token.value for token in tokens
                                   if token.type == "OPERAND" and token.subtype == "RANGE"))
    return references, True


def _number(raw: str) -> str:
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise IngestionError("OFFICE_INVALID_CELL", "Une valeur numérique XLSX est invalide.") from exc
    if not number.is_finite():
        raise IngestionError("OFFICE_INVALID_CELL", "Une valeur numérique XLSX n'est pas finie.")
    return str(number)


def typed_value(raw: str | None, cell_type: str, number_format: str,
                date_system: str, shared_strings: list[dict[str, Any]],
                inline: Element | None = None) -> dict[str, Any]:
    """Return a JSON-safe typed value while retaining exact XML separately."""
    if cell_type == "inlineStr":
        text, runs = rich_text(inline) if inline is not None else ("", [])
        return {"kind": "string", "value": text, "raw_text": "".join(run["raw_text"] for run in runs),
                "rich_text": runs}
    if raw is None:
        if cell_type == "str":
            return {"kind": "string", "value": ""}
        return {"kind": "empty", "value": None}
    if cell_type == "s":
        try:
            index = int(raw)
            if not re.fullmatch(r"[0-9]+", raw) or index >= len(shared_strings):
                raise ValueError
        except ValueError as exc:
            raise IngestionError("OFFICE_INVALID_SHARED_STRING", "Une référence de chaîne XLSX est invalide.") from exc
        return {"kind": "string", "value": shared_strings[index]["text"],
                "raw_text": shared_strings[index]["raw_text"],
                "rich_text": shared_strings[index]["runs"], "shared_string_index": index}
    if cell_type in {"str", "e"}:
        return {"kind": "error" if cell_type == "e" else "string",
                "value": raw if cell_type == "e" else decode_xstring(raw)}
    if cell_type == "b":
        if raw not in {"0", "1", "true", "false"}:
            raise IngestionError("OFFICE_INVALID_CELL", "Une valeur booléenne XLSX est invalide.")
        return {"kind": "boolean", "value": raw in {"1", "true"}}
    if cell_type == "d":
        try:
            value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise IngestionError("OFFICE_INVALID_CELL", "Une date ISO XLSX est invalide.") from exc
        return {"kind": "datetime", "value": value.isoformat(), "conversion": "iso8601"}
    if cell_type != "n":
        raise IngestionError("OFFICE_UNSUPPORTED_CELL_TYPE", "Le type natif d'une cellule XLSX est inconnu.")
    exact = _number(raw)
    if is_timedelta_format(number_format):
        try:
            with localcontext() as context:
                context.prec = max(28, len(exact) + 20)
                seconds = Decimal(exact) * Decimal(86_400)
        except InvalidOperation as exc:
            raise IngestionError("OFFICE_INVALID_CELL", "Une durée XLSX est invalide.") from exc
        return {"kind": "duration", "value": str(seconds), "unit": "seconds", "serial": exact}
    if is_date_format(number_format):
        # Excel's fictitious leap day cannot be represented by datetime.
        serial = Decimal(exact)
        if date_system == "1900" and Decimal(60) <= serial < Decimal(61):
            return {"kind": "excel_date", "value": None, "serial": exact,
                    "date_system": date_system, "excel_1900_leap_day": True}
        try:
            converted = from_excel(float(serial), epoch=MAC_EPOCH if date_system == "1904" else WINDOWS_EPOCH)
        except (OverflowError, ValueError) as exc:
            raise IngestionError("OFFICE_INVALID_CELL", "Une date sérielle XLSX est hors limites.") from exc
        return {"kind": "time" if isinstance(converted, dt.time) else "datetime",
                "value": converted.isoformat(), "serial": exact, "date_system": date_system,
                "conversion": "openpyxl_millisecond_resolution"}
    return {"kind": "number", "value": exact}


def xml_events(package: PackageReader, part: str) -> Iterator[tuple[str, Element]]:
    """The common OPC reader has already checked member/aggregate quotas."""
    yield from package.iter_xml(part, events=("start", "end"))


def read_shared_strings(package: PackageReader, part: str | None, *,
                        max_count: int, max_chars: int) -> list[dict[str, Any]]:
    strings: list[dict[str, Any]] = []
    if part is None:
        return strings
    char_count = 0
    root = None
    for event, element in xml_events(package, part):
        if root is None:
            root = element
            if local_name(root.tag) != "sst" or namespace(root.tag) not in SPREADSHEET_NAMESPACES:
                raise IngestionError("OFFICE_INVALID_XLSX", "La partie des chaînes XLSX est invalide.")
        if event != "end" or local_name(element.tag) != "si":
            continue
        text, runs = rich_text(element)
        char_count += len(text)
        if len(strings) >= max_count or char_count > max_chars:
            raise IngestionError("OFFICE_LIMIT_EXCEEDED", "Les chaînes partagées XLSX dépassent le budget.")
        strings.append({"text": text, "raw_text": "".join(run["raw_text"] for run in runs), "runs": runs})
        element.clear()
        if root is not element:
            root.clear()
    return strings


def read_styles(package: PackageReader, part: str | None, *, max_styles: int) -> list[dict[str, Any]]:
    if part is None:
        return [{"number_format_id": 0, "number_format": "General", "attributes": {}}]
    formats = dict(BUILTIN_FORMATS)
    raw_formats = dict(BUILTIN_FORMATS)
    styles: list[dict[str, Any]] = []
    stack: list[str] = []
    root = None
    for event, element in xml_events(package, part):
        name = local_name(element.tag)
        if event == "start":
            if root is None:
                root = element
                if name != "styleSheet" or namespace(element.tag) not in SPREADSHEET_NAMESPACES:
                    raise IngestionError("OFFICE_INVALID_XLSX", "La partie des styles XLSX est invalide.")
            stack.append(name)
            continue
        if name == "numFmt" and len(stack) >= 2 and stack[-2] == "numFmts":
            try:
                format_id = int(element.attrib["numFmtId"])
                raw_formats[format_id] = element.attrib["formatCode"]
                formats[format_id] = decode_xstring(element.attrib["formatCode"])
            except (KeyError, ValueError) as exc:
                raise IngestionError("OFFICE_INVALID_XLSX", "Un format numérique XLSX est invalide.") from exc
        if name == "xf" and len(stack) >= 2 and stack[-2] == "cellXfs":
            if len(styles) >= max_styles:
                raise IngestionError("OFFICE_LIMIT_EXCEEDED", "Les styles XLSX dépassent le budget.")
            try:
                number_format_id = int(element.get("numFmtId", "0"))
            except ValueError as exc:
                raise IngestionError("OFFICE_INVALID_XLSX", "Un identifiant de style XLSX est invalide.") from exc
            if number_format_id not in formats:
                raise IngestionError("OFFICE_INVALID_XLSX", "Un format numérique XLSX est introuvable.")
            styles.append({"number_format_id": number_format_id,
                           "number_format": formats[number_format_id],
                           "raw_number_format": raw_formats[number_format_id], "attributes": dict(element.attrib),
                           "properties": {local_name(child.tag): dict(child.attrib) for child in element}})
        stack.pop()
        if "cellXfs" not in stack or "xf" not in stack:
            element.clear()
    return styles or [{"number_format_id": 0, "number_format": "General", "attributes": {}}]


def _cell(element: Element, styles: list[dict[str, Any]], shared_strings: list[dict[str, Any]],
          date_system: str, shared_formulas: dict[str, dict[str, Any]],
          max_text_chars: int, inferred_address: str) -> dict[str, Any]:
    address = element.get("r", inferred_address)
    row, column = address_coordinates(address)
    try:
        style_index = int(element.get("s", "0"))
        if style_index < 0 or style_index >= len(styles):
            raise ValueError
    except ValueError as exc:
        raise IngestionError("OFFICE_INVALID_STYLE", "Une cellule XLSX référence un style invalide.") from exc
    style = styles[style_index]
    cell_type = element.get("t", "n")
    value_element = spreadsheet_child(element, "v")
    raw = value_element.text if value_element is not None else None
    inline = spreadsheet_child(element, "is")
    formula_element = spreadsheet_child(element, "f")
    value = typed_value(raw, cell_type, style["number_format"], date_system, shared_strings, inline)
    cell: dict[str, Any] = {"address": address, "row": row, "column": column,
                            "ooxml_type": cell_type, "raw_value": raw,
                            "value_element_present": value_element is not None,
                            "inline_string_present": inline is not None,
                            "source_address_kind": "explicit" if element.get("r") is not None else "implicit_position",
                            "value": None if formula_element is not None else value,
                            "style_index": style_index, "style": style,
                            "attributes": dict(element.attrib), "formula": None,
                            "cache": None, "date_system": date_system}
    if formula_element is not None:
        formula_type = formula_element.get("t", "normal")
        if formula_type not in {"normal", "shared", "array", "dataTable"}:
            raise IngestionError("OFFICE_UNSUPPORTED_FORMULA", "Le type de formule XLSX est inconnu.")
        formula: dict[str, Any] = {"type": formula_type, "raw_text": formula_element.text,
                                   "effective_text": formula_element.text,
                                   "attributes": dict(formula_element.attrib), "resolution": "source"}
        if formula_type == "shared":
            shared_index = formula_element.get("si")
            if shared_index is None:
                raise IngestionError("OFFICE_INVALID_FORMULA", "Une formule partagée XLSX n'a pas d'identifiant.")
            if formula_element.text is not None:
                if shared_index in shared_formulas:
                    raise IngestionError("OFFICE_INVALID_FORMULA", "Une formule partagée XLSX a des origines dupliquées.")
                shared_formulas[shared_index] = {"address": address, "text": formula_element.text,
                                               "range": formula_element.get("ref")}
            elif shared_index in shared_formulas:
                master = shared_formulas[shared_index]
                if master["range"]:
                    r1, c1, r2, c2 = range_coordinates(master["range"])
                    if not r1 <= row <= r2 or not c1 <= column <= c2:
                        raise IngestionError("OFFICE_INVALID_FORMULA", "Une formule partagée XLSX est hors plage.")
                try:
                    formula["effective_text"] = Translator("=" + master["text"].removeprefix("="),
                                                           origin=master["address"]).translate_formula(address).removeprefix("=")
                    formula["resolution"] = "translated_shared_source"
                    formula["shared_source_address"] = master["address"]
                except (TranslatorError, TokenizerError, ValueError, IndexError):
                    formula["resolution"] = "unresolved_shared"
            else:
                formula["resolution"] = "unresolved_shared"
        if formula_element.get("ref") is not None:
            range_coordinates(formula_element.attrib["ref"])
        references, recognized = formula_references(formula["effective_text"])
        formula["references"] = references
        formula["references_coverage"] = "recognized_operands" if recognized else "unresolved"
        formula["external_reference_present"] = any("[" in reference and "]" in reference for reference in references)
        cell["formula"] = formula
        # XML parsers expose <v/> as text=None. For t="str" that element
        # contains an explicitly empty result; a missing <v> is still absent.
        cache_present = raw is not None or (cell_type == "str" and value_element is not None)
        cell["cache"] = {"present": cache_present, "element_present": value_element is not None,
                         "raw_value": raw, "value": value if cache_present else None,
                         "freshness": "unknown", "evaluated": False}
    visible = str(value.get("value") or "")
    formula_text = (cell["formula"] or {}).get("effective_text") or ""
    if max(len(visible), len(formula_text), len(raw or "")) > max_text_chars:
        raise IngestionError("OFFICE_LIMIT_EXCEEDED", "Le contenu d'une cellule XLSX dépasse le budget.")
    return cell


def iter_sheet_rows(package: PackageReader, part: str, *, styles: list[dict[str, Any]],
                    shared_strings: list[dict[str, Any]], date_system: str,
                    max_cells: int, max_text_chars: int,
                    on_row: Callable[[int], None] | None = None) -> Iterator[tuple[int, list[dict[str, Any]]]]:
    """Materialize only cells present in XML, one source row at a time."""
    count = 0
    last_row = 0
    last_column = 0
    row_cells: list[dict[str, Any]] = []
    shared_formulas: dict[str, dict[str, Any]] = {}
    root = None
    sheet_data = None
    current_row = None
    for event, element in xml_events(package, part):
        name = local_name(element.tag)
        if event == "start":
            if root is None:
                root = element
                if name != "worksheet" or namespace(element.tag) not in SPREADSHEET_NAMESPACES:
                    raise IngestionError("OFFICE_INVALID_XLSX", "Une feuille XLSX est invalide.")
            if name == "sheetData":
                sheet_data = element
            if name == "row" and namespace(element.tag) in SPREADSHEET_NAMESPACES:
                try:
                    current_row = int(element.get("r", str(last_row + 1)))
                except ValueError as exc:
                    raise IngestionError("OFFICE_INVALID_CELL", "Un numéro de ligne XLSX est invalide.") from exc
                if not last_row < current_row <= MAX_ROW:
                    raise IngestionError("OFFICE_INVALID_CELL", "Les lignes XLSX sont désordonnées ou dupliquées.")
                last_column = 0
                if on_row is not None:
                    on_row(current_row)
            continue
        if name == "c" and namespace(element.tag) in SPREADSHEET_NAMESPACES:
            count += 1
            if count > max_cells:
                raise IngestionError("OFFICE_LIMIT_EXCEEDED", "Les cellules XLSX dépassent le budget.")
            if current_row is None or last_column >= MAX_COLUMN:
                raise IngestionError("OFFICE_INVALID_CELL", "Une cellule XLSX n'appartient pas à une ligne valide.")
            inferred_address = f"{get_column_letter(last_column + 1)}{current_row}"
            cell = _cell(element, styles, shared_strings, date_system, shared_formulas, max_text_chars, inferred_address)
            if cell["row"] != current_row or cell["column"] <= last_column:
                raise IngestionError("OFFICE_INVALID_CELL", "Les cellules XLSX sont désordonnées ou dupliquées.")
            last_column = cell["column"]
            row_cells.append(cell)
            element.clear()
        elif name == "row" and namespace(element.tag) in SPREADSHEET_NAMESPACES:
            assert current_row is not None
            yield current_row, row_cells
            last_row = current_row
            current_row = None
            row_cells = []
            element.clear()
            if sheet_data is not None:
                sheet_data.clear()
        elif name not in {"f", "v", "t", "is", "r", "rPr", "b", "i", "u", "sz", "color", "rFont"}:
            # Preserve descendants of the current cell until its end event.
            if current_row is None:
                element.clear()


def _relationship_id(element: Element) -> str | None:
    return next((value for key, value in element.attrib.items()
                 if local_name(key) == "id" and "relationships" in namespace(key)), None)


def _xml_record(element: Element) -> dict[str, Any]:
    return {"name": local_name(element.tag), "namespace": namespace(element.tag),
            "attributes": dict(element.attrib), "text": element.text,
            "children": [_xml_record(child) for child in element]}


def _warn(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, "severity": "warning", **details}


def _extension_warnings(records: list[dict[str, Any]], part: str, *,
                        unit_id: str | None = None, dynamic_array_metadata: bool = False) -> list[dict[str, Any]]:
    """Retaining arbitrary extension XML does not imply semantic coverage.

    Only the qualified, leaf dynamic-array flag metadata already represented
    by this adapter is covered. Future attributes/children remain explicit
    unsupported content. Formula evaluation is never implied by these flags.
    """
    warnings: list[dict[str, Any]] = []

    def covered(payload: dict[str, Any]) -> bool:
        attributes = payload["attributes"]
        return (dynamic_array_metadata and payload["name"] == "dynamicArrayProperties"
                and payload["namespace"] == DYNAMIC_ARRAY_NAMESPACE and not payload["children"]
                and not (payload.get("text") or "").strip()
                and not (attributes.keys() - {"fDynamic", "fCollapsed"})
                and attributes.get("fDynamic", "0") in {"0", "1", "false", "true"}
                and attributes.get("fCollapsed", "0") in {"0", "false"})

    def visit(record: dict[str, Any], path: str) -> None:
        if record["name"] == "ext" and record["namespace"] in SPREADSHEET_NAMESPACES:
            payloads = record["children"]
            if (any(not covered(payload) for payload in payloads)
                    or (record.get("text") or "").strip()
                    or record["attributes"].keys() - {"uri"}):
                details = {"part": part, "element_path": path, "uri": record["attributes"].get("uri"),
                           "payloads": [{"name": payload["name"], "namespace": payload["namespace"]}
                                        for payload in payloads]}
                if unit_id is not None:
                    details["unit_id"] = unit_id
                warnings.append(_warn("XLSX_UNSUPPORTED_EXTENSION",
                    "Une extension XLSX est conservée dans les métadonnées, sans interprétation complète.", **details))
            return
        for index, child in enumerate(record["children"]):
            visit(child, f"{path}/{child['name']}[{index}]")

    for index, record in enumerate(records):
        visit(record, f"{record['name']}[{index}]")
    return warnings


def _sheet_metadata(package: OfficePackage, part: str) -> dict[str, Any]:
    """A bounded metadata pass; rows/cells are cleared as they are consumed."""
    result: dict[str, Any] = {"merged_ranges": [], "table_relation_ids": [], "hyperlinks": [],
                              "row_properties": [], "column_properties": [], "features": {}}
    capture = {"sheetPr", "sheetViews", "sheetFormatPr", "sheetProtection", "autoFilter",
               "sortState", "conditionalFormatting", "dataValidations", "printOptions",
               "pageMargins", "pageSetup", "headerFooter", "rowBreaks", "colBreaks", "extLst"}
    stack: list[str] = []
    captured = None
    for event, element in package.iter_xml(part, events=("start", "end")):
        name = local_name(element.tag)
        if event == "start":
            stack.append(name)
            if len(stack) == 1 and (name != "worksheet" or namespace(element.tag) not in SPREADSHEET_NAMESPACES):
                raise IngestionError("OFFICE_INVALID_XLSX", "Une feuille XLSX est invalide.")
            if len(stack) == 2 and name in capture:
                captured = element
            continue
        native = namespace(element.tag) in SPREADSHEET_NAMESPACES
        if name == "dimension" and len(stack) == 2 and native:
            result["declared_dimension"] = element.get("ref")
        elif name == "mergeCell" and native:
            reference = element.get("ref", "")
            range_coordinates(reference)
            result["merged_ranges"].append(reference)
        elif name == "tablePart" and native:
            identifier = _relationship_id(element)
            if not identifier:
                raise IngestionError("OFFICE_INVALID_XLSX", "Une table XLSX n'a pas de relation source.")
            result["table_relation_ids"].append(identifier)
        elif name == "hyperlink" and native:
            item = dict(element.attrib, raw_attributes=dict(element.attrib))
            for key in ("display", "tooltip", "location"):
                if key in element.attrib:
                    item[key] = decode_xstring(element.attrib[key])
            reference = item.get("ref")
            if reference:
                range_coordinates(reference)
            item["relationship_id"] = _relationship_id(element)
            result["hyperlinks"].append(item)
        elif name == "row" and native:
            # Row layout has meaning even for an otherwise empty source row.
            if set(element.attrib) - {"r", "spans"}:
                result["row_properties"].append(dict(element.attrib))
        elif name == "col" and native:
            result["column_properties"].append(dict(element.attrib))
        if element is captured:
            assert element is not None
            result["features"].setdefault(name, []).append(_xml_record(element))
            captured = None
        if captured is None:
            element.clear()
            # lxml keeps cleared siblings unless explicitly removed.
            if hasattr(element, "getparent"):
                parent = element.getparent()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
        stack.pop()
    return result


def _comments(package: OfficePackage, relation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    root = package.xml(relation["target"])
    if local_name(root.tag) != "comments" or namespace(root.tag) not in SPREADSHEET_NAMESPACES:
        raise IngestionError("OFFICE_INVALID_XLSX", "Une partie de commentaires XLSX est invalide.")
    authors_element = spreadsheet_child(root, "authors")
    raw_authors = [element.text or "" for element in authors_element] if authors_element is not None else []
    authors = [decode_xstring(author) for author in raw_authors]
    comments: dict[str, dict[str, Any]] = {}
    comment_list = spreadsheet_child(root, "commentList")
    if comment_list is None:
        return comments
    for comment in comment_list:
        address = comment.get("ref", "")
        address_coordinates(address)
        try:
            author_index = int(comment.get("authorId", "0"))
            if not 0 <= author_index < len(authors):
                raise ValueError
        except ValueError as exc:
            raise IngestionError("OFFICE_INVALID_XLSX", "L'auteur d'un commentaire XLSX est invalide.") from exc
        text_element = spreadsheet_child(comment, "text")
        text, runs = rich_text(text_element) if text_element is not None else ("", [])
        if len(comments) >= package.limits.max_cells or len(text) > package.limits.max_cell_chars:
            raise limit_error()
        if address in comments:
            raise IngestionError("OFFICE_INVALID_XLSX", "Des commentaires XLSX ont une adresse dupliquée.")
        comments[address] = {"author": authors[author_index], "raw_author": raw_authors[author_index],
                             "text": text, "raw_text": "".join(run["raw_text"] for run in runs), "runs": runs,
                             "part": relation["target"], "attributes": dict(comment.attrib)}
    return comments


def _table(package: OfficePackage, relation: dict[str, Any], sheet_id: str) -> dict[str, Any]:
    root = package.xml(relation["target"])
    if local_name(root.tag) != "table" or namespace(root.tag) not in SPREADSHEET_NAMESPACES:
        raise IngestionError("OFFICE_INVALID_XLSX", "Une table structurée XLSX est invalide.")
    reference = root.get("ref", "")
    r1, c1, r2, c2 = range_coordinates(reference)
    columns = spreadsheet_child(root, "tableColumns")
    column_data = [_xml_record(child) for child in columns] if columns is not None else []
    for column in column_data:
        raw_label = column["attributes"].get("name")
        column["label"] = decode_xstring(raw_label) if raw_label is not None else None
    if len(column_data) != c2 - c1 + 1:
        raise IngestionError("OFFICE_INVALID_XLSX", "Une table XLSX ne correspond pas à ses colonnes.")
    try:
        header_rows = int(root.get("headerRowCount", "1"))
        totals_rows = int(root.get("totalsRowCount", "0"))
        if header_rows not in {0, 1} or totals_rows not in {0, 1}:
            raise ValueError
    except ValueError as exc:
        raise IngestionError("OFFICE_INVALID_XLSX", "Les lignes d'en-tête ou de total d'une table XLSX sont invalides.") from exc
    return {"id": f"{sheet_id}:table:{root.get('id', relation['id'])}", "unit_id": sheet_id,
            "part": relation["target"], "name": root.get("name"), "display_name": root.get("displayName"),
            "cell_range": reference, "row_start": r1, "row_end": r2, "column_start": c1, "column_end": c2,
            "header_row_count": header_rows, "totals_row_count": totals_rows,
            "attributes": dict(root.attrib), "columns": column_data,
            "features": [_xml_record(child) for child in root if local_name(child.tag) != "tableColumns"]}


def _display(value: dict[str, Any] | None) -> str:
    if value is None or value.get("kind") == "empty":
        return ""
    if value["kind"] == "boolean":
        return "true" if value["value"] else "false"
    if value["kind"] == "excel_date":
        return f"jour Excel 1900 fictif (série {value['serial']})"
    return str(value.get("value", ""))


def _contract_cell(cell: dict[str, Any], comment: dict[str, Any] | None) -> dict[str, Any]:
    cache = cell["cache"]
    result = dict(cell, data_type=(cell["value"] or (cache or {}).get("value") or {"kind": "empty"})["kind"],
                  display_text=_display(cell["value"] if cell["formula"] is None else (cache or {}).get("value")),
                  number_format=cell["style"]["number_format"],
                  cached_value=(cache or {}).get("value"), cached_present=(cache or {}).get("present", False),
                  cache_freshness="unknown" if (cache or {}).get("present", False) else "absent")
    if comment is not None:
        result["comment"] = comment
    return result


def _cell_fields(cell: dict[str, Any]) -> list[tuple[str, str]]:
    fields = [("value", cell["display_text"])] if cell["display_text"] else []
    formula = cell.get("formula")
    if formula is not None:
        effective = formula.get("effective_text")
        if effective is not None:
            fields.append(("formula", "=" + effective.removeprefix("=")))
        fields.append(("cache_status", "cache de formule : fraîcheur inconnue" if cell["cached_present"]
                       else "cache de formule absent"))
    if cell.get("comment", {}).get("text"):
        fields.append(("comment", cell["comment"]["text"]))
    return fields


def _row_blocks(sheet_id: str, sheet_name: str, part: str, row: int,
                cells: list[dict[str, Any]], max_chars: int,
                tables: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Cells can span derived blocks; every source span retains its address."""
    blocks: list[dict[str, Any]] = []
    text = ""
    bindings: list[dict[str, Any]] = []

    def flush():
        nonlocal text, bindings
        if not bindings:
            return
        columns = [binding["column"] for binding in bindings]
        addresses = list(dict.fromkeys(binding["address"] for binding in bindings))
        cell_range = addresses[0] if len(addresses) == 1 else f"{addresses[0]}:{addresses[-1]}"
        locator = {"kind": "xlsx_cells", "unit_id": sheet_id, "sheet_id": sheet_id,
                   "sheet_name": sheet_name, "part": part, "cell_range": cell_range,
                   "row_start": row, "row_end": row, "column_start": min(columns), "column_end": max(columns)}
        blocks.append({"id": f"{sheet_id}:row:{row}:part:{len(blocks)}", "kind": "table_row",
                       "type": "table_row", "text": text, "section_id": sheet_id,
                       "locator": locator, "structure": {"row": row, "addresses": addresses,
                                                           "headers_included": False,
                                                           "table_contexts": []}, "bindings": bindings})
        for table in tables or []:
            selected = [column for column in columns if table["column_start"] <= column <= table["column_end"]]
            if table["row_start"] <= row <= table["row_end"] and selected:
                headers = []
                for column in sorted(set(selected)):
                    definition = table["columns"][column - table["column_start"]]
                    headers.append({"column": column, "label": definition["label"],
                                    "provenance": "table_column_metadata", "part": table["part"],
                                    "header_source_row": table["row_start"] if table["header_row_count"] else None})
                blocks[-1]["structure"]["table_contexts"].append({"table_id": table["id"], "name": table["name"],
                                                                  "headers": headers})
        text, bindings = "", []

    for cell in cells:
        for field, value in _cell_fields(cell):
            # A source prefix is repeated across pieces, never misrepresented as source text.
            prefix = f"{cell['address']} ({field}) : "
            if len(prefix) >= max_chars:
                raise limit_error()
            offset = 0
            while offset < len(value):
                separator = "\n" if text else ""
                available = max_chars - len(text) - len(separator) - len(prefix)
                if available <= 0:
                    flush()
                    continue
                piece = value[offset:offset + available]
                start = len(text) + len(separator) + len(prefix)
                text += separator + prefix + piece
                bindings.append({"address": cell["address"], "row": row, "column": cell["column"],
                                 "start": start, "end": start + len(piece), "field": field,
                                 "source_start": offset, "source_end": offset + len(piece)})
                offset += len(piece)
                if offset < len(value):
                    flush()
    flush()
    return blocks


def parse_xlsx(package: OfficePackage, *, checkpoint: Callable[[str], None] | None = None,
               unit_sink: Callable[[dict[str, Any]], None] | None = None,
               cached_units: Mapping[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Parse a preflighted workbook with explicit quotas and sparse cells.

    The orchestrator validates cached units against this immutable original's
    SHA and parser/config fingerprint. A unit is emitted only after its full
    sheet has been parsed; a row pause never emits an incomplete sheet.
    """
    if package.format != "xlsx":
        raise IngestionError("OFFICE_FORMAT_MISMATCH", "Le conteneur n'est pas un classeur XLSX.")
    limits = package.limits
    main = package.xml(package.main_part)
    if local_name(main.tag) != "workbook" or namespace(main.tag) not in SPREADSHEET_NAMESPACES:
        raise IngestionError("OFFICE_INVALID_XLSX", "La partie principale XLSX est invalide.")
    workbook_relations = package.relations(package.main_part)
    relations = {relation["id"]: relation for relation in workbook_relations}

    def singleton_part(kind: str) -> str | None:
        candidates = [rel["target"] for rel in workbook_relations
                      if rel["type"].endswith("/" + kind) and not rel["external"]]
        if len(candidates) > 1:
            raise IngestionError("OFFICE_INVALID_XLSX", "Des parties XLSX uniques sont dupliquées.")
        return candidates[0] if candidates else None

    workbook_pr = spreadsheet_child(main, "workbookPr")
    date_flag = workbook_pr.get("date1904", "0") if workbook_pr is not None else "0"
    if date_flag not in {"0", "1", "false", "true"}:
        raise IngestionError("OFFICE_INVALID_XLSX", "Le système de dates XLSX est invalide.")
    date_system = "1904" if date_flag in {"1", "true"} else "1900"
    shared_strings = read_shared_strings(package, singleton_part("sharedStrings"),
                                        max_count=limits.max_shared_strings, max_chars=limits.max_text_chars)
    styles = read_styles(package, singleton_part("styles"), max_styles=limits.max_elements)
    metadata: dict[str, Any] = {"date_system": date_system, "relations": workbook_relations,
                                "styles": styles, "shared_strings_count": len(shared_strings),
                                "calculation": {}, "defined_names": [], "properties": {},
                                "formula_evaluation": "never", "cache_freshness": "unknown"}
    metadata["extensions"] = [_xml_record(element) for element in spreadsheet_children(main, "extLst")]
    calc = spreadsheet_child(main, "calcPr")
    if calc is not None:
        metadata["calculation"] = dict(calc.attrib)
    defined_names = spreadsheet_child(main, "definedNames")
    if defined_names is not None:
        metadata["defined_names"] = [dict(element.attrib, text=element.text) for element in defined_names]
    metadata_part = singleton_part("sheetMetadata")
    if metadata_part is not None:
        metadata_root = package.xml(metadata_part)
        metadata["cell_metadata"] = _xml_record(metadata_root)
        metadata["metadata_part"] = metadata_part
        cell_metadata_element = spreadsheet_child(metadata_root, "cellMetadata")
        metadata["cell_metadata_records"] = ([_xml_record(record) for record in cell_metadata_element]
                                              if cell_metadata_element is not None else [])
    for relation in package.relations(""):
        if relation["type"].endswith(("/core-properties", "/extended-properties", "/custom-properties")) and not relation["external"]:
            metadata["properties"][relation["type"].rsplit("/", 1)[-1]] = _xml_record(package.xml(relation["target"]))
    result: dict[str, Any] = {"units": [], "sections": [], "tables": [], "metadata": metadata,
                              "warnings": [], "coverage": {}, "status": "ready", "parser_complete": True}
    result["warnings"].extend(_extension_warnings(metadata["extensions"], package.main_part))
    if metadata_part is not None:
        result["warnings"].extend(_extension_warnings([metadata["cell_metadata"]], metadata_part,
                                                     dynamic_array_metadata=True))
    sheets = spreadsheet_child(main, "sheets")
    if sheets is None:
        raise IngestionError("OFFICE_INVALID_XLSX", "Le classeur XLSX ne contient pas de catalogue de feuilles.")
    seen_sheet_ids: set[str] = set()
    seen_parts: set[str] = set()
    seen_names: set[str] = set()
    total_cells = 0
    total_blocks = 0
    total_text = sum(len(item["text"]) for item in shared_strings)
    unsupported = len(result["warnings"])
    for order, sheet in enumerate(sheets):
        if order >= limits.max_units:
            raise limit_error()
        raw_sheet_name = sheet.get("name", "")
        sheet_name = decode_xstring(raw_sheet_name)
        source_id = sheet.get("sheetId", "")
        relation = relations.get(_relationship_id(sheet) or "")
        if (not source_id or source_id in seen_sheet_ids or not sheet_name or sheet_name.casefold() in seen_names
                or relation is None or relation["external"] or relation["target"] in seen_parts):
            raise IngestionError("OFFICE_INVALID_XLSX", "Le catalogue des feuilles XLSX est incohérent.")
        seen_sheet_ids.add(source_id)
        seen_names.add(sheet_name.casefold())
        seen_parts.add(relation["target"])
        part = relation["target"]
        sheet_id = f"xlsx:{part}"
        visibility = sheet.get("state", "visible")
        if visibility not in {"visible", "hidden", "veryHidden"}:
            raise IngestionError("OFFICE_INVALID_XLSX", "La visibilité d'une feuille XLSX est invalide.")
        cached = (cached_units or {}).get(sheet_id)
        if cached is not None:
            if (cached.get("id") != sheet_id or cached.get("part") != part or cached.get("title") != sheet_name
                    or cached.get("order_index") != order or cached.get("metadata", {}).get("visibility") != visibility
                    or cached.get("metadata", {}).get("source_sheet_id") != source_id
                    or not isinstance(cached.get("cells"), list) or not isinstance(cached.get("blocks"), list)):
                raise IngestionError("OFFICE_INVALID_CHECKPOINT", "Une feuille en cache ne correspond pas à l'original XLSX.")
            total_cells += len(cached["cells"])
            total_blocks += len(cached["blocks"])
            total_text += sum(len(cell.get("display_text", ""))
                              + len((cell.get("formula") or {}).get("effective_text") or "")
                              + len(cell.get("comment", {}).get("text", "")) for cell in cached["cells"])
            if total_cells > limits.max_cells or total_blocks > limits.max_blocks or total_text > limits.max_text_chars:
                raise limit_error()
            result["units"].append(cached)
            result["warnings"].extend(cached["metadata"].get("extraction_warnings", []))
            unsupported += cached["metadata"].get("unsupported_count", 0)
            result["tables"].extend(cached["metadata"].get("tables", []))
            if cached["metadata"].get("supported", True):
                result["sections"].append({"id": sheet_id, "title": sheet_name, "unit_id": sheet_id,
                                           "parent_id": None, "order_index": order})
            if checkpoint is not None:
                checkpoint(sheet_id)
            continue
        initial_unsupported = unsupported
        first_warning_index = len(result["warnings"])
        if not relation["type"].endswith("/worksheet"):
            unsupported += 1
            result["warnings"].append(_warn("XLSX_UNSUPPORTED_SHEET", "Une feuille graphique ou autre n'est pas indexée.",
                                              part=part, sheet_name=sheet_name, relationship_type=relation["type"]))
            result["units"].append({"id": sheet_id, "kind": "xlsx_sheet", "title": sheet_name, "part": part,
                                    "order_index": order, "parent_id": None,
                                    "metadata": {"source_sheet_id": source_id, "visibility": visibility,
                                                 "supported": False, "relationship_type": relation["type"],
                                                 "unsupported_count": 1,
                                                 "extraction_warnings": result["warnings"][first_warning_index:]},
                                    "blocks": [], "cells": []})
            if unit_sink is not None:
                unit_sink(result["units"][-1])
            if checkpoint is not None:
                checkpoint(sheet_id)
            continue
        sheet_meta = _sheet_metadata(package, part)
        sheet_relations = package.relations(part)
        sheet_rel_by_id = {item["id"]: item for item in sheet_relations}
        sheet_meta.update(source_sheet_id=source_id, raw_sheet_name=raw_sheet_name,
                          visibility=visibility, supported=True, relations=sheet_relations)
        extension_warnings = _extension_warnings([record for records in sheet_meta["features"].values()
                                                   for record in records], part, unit_id=sheet_id)
        result["warnings"].extend(extension_warnings)
        unsupported += len(extension_warnings)
        comments: dict[str, dict[str, Any]] = {}
        for item in sheet_relations:
            if not item["external"] and item["type"].endswith("/comments"):
                incoming = _comments(package, item)
                if comments.keys() & incoming.keys():
                    raise IngestionError("OFFICE_INVALID_XLSX", "Des parties de commentaires XLSX se recouvrent.")
                comments.update(incoming)
            elif not item["external"] and item["type"].endswith(("/drawing", "/vmlDrawing", "/pivotTable", "/threadedComment")):
                unsupported += 1
                result["warnings"].append(_warn("XLSX_UNSUPPORTED_OBJECT", "Un objet XLSX est conservé comme relation, sans interprétation.",
                                                  unit_id=sheet_id, part=item["target"], relationship_type=item["type"]))
        sheet_tables = []
        seen_tables: set[str] = set()
        for identifier in sheet_meta["table_relation_ids"]:
            table_relation = sheet_rel_by_id.get(identifier)
            if table_relation is None or table_relation["external"] or not table_relation["type"].endswith("/table"):
                raise IngestionError("OFFICE_INVALID_XLSX", "Une table XLSX référence une relation invalide.")
            table = _table(package, table_relation, sheet_id)
            if table["id"] in seen_tables:
                raise IngestionError("OFFICE_INVALID_XLSX", "Une table structurée XLSX est dupliquée.")
            seen_tables.add(table["id"])
            sheet_tables.append(table)
            result["tables"].append(table)
            extension_warnings = _extension_warnings(table["features"] + table["columns"],
                                                     table["part"], unit_id=sheet_id)
            result["warnings"].extend(extension_warnings)
            unsupported += len(extension_warnings)
        sheet_meta["tables"] = sheet_tables
        for hyperlink in sheet_meta["hyperlinks"]:
            identifier = hyperlink["relationship_id"]
            if identifier is not None:
                if identifier not in sheet_rel_by_id or not sheet_rel_by_id[identifier]["type"].endswith("/hyperlink"):
                    raise IngestionError("OFFICE_INVALID_XLSX", "Un lien XLSX référence une relation invalide.")
                hyperlink["relation"] = sheet_rel_by_id[identifier]
        unit: dict[str, Any] = {"id": sheet_id, "kind": "xlsx_sheet", "title": sheet_name, "part": part,
                                 "order_index": order, "parent_id": None, "metadata": sheet_meta,
                                 "blocks": [], "cells": []}
        bounds = None

        def row_checkpoint(row: int, unit_id: str = sheet_id):
            if checkpoint is not None:
                checkpoint(f"{unit_id}:row:{row}")

        for row, cells in iter_sheet_rows(package, part, styles=styles, shared_strings=shared_strings,
                                         date_system=date_system, max_cells=limits.max_cells - total_cells,
                                         max_text_chars=limits.max_cell_chars, on_row=row_checkpoint):
            total_cells += len(cells)
            converted = [_contract_cell(cell, comments.get(cell["address"])) for cell in cells]
            for cell in converted:
                total_text += len(cell["display_text"]) + len((cell["formula"] or {}).get("effective_text") or "")
                if cell.get("comment"):
                    total_text += len(cell["comment"]["text"])
                if total_text > limits.max_text_chars:
                    raise limit_error()
                if bounds is None:
                    bounds = [row, cell["column"], row, cell["column"]]
                else:
                    bounds[0], bounds[1] = min(bounds[0], row), min(bounds[1], cell["column"])
                    bounds[2], bounds[3] = max(bounds[2], row), max(bounds[3], cell["column"])
                formula = cell["formula"]
                cell_metadata_index = cell["attributes"].get("cm")
                if cell_metadata_index is not None:
                    try:
                        index = int(cell_metadata_index)
                        records = metadata.get("cell_metadata_records", [])
                        if not 1 <= index <= len(records):
                            raise ValueError
                    except ValueError as exc:
                        raise IngestionError("OFFICE_INVALID_XLSX", "Une cellule XLSX référence des métadonnées invalides.") from exc
                    cell["cell_metadata"] = {"index": index, "part": metadata["metadata_part"], "record": records[index - 1],
                                               "interpretation": "source_only"}
                    if formula is not None:
                        formula["dynamic_array_metadata"] = {"index": index, "part": metadata["metadata_part"],
                                                              "evaluated": False}
                if formula is not None and (formula["resolution"] == "unresolved_shared" or formula["references_coverage"] == "unresolved"):
                    result["warnings"].append(_warn("XLSX_FORMULA_UNRESOLVED", "Une représentation de formule n'a pas pu être résolue.",
                                                      unit_id=sheet_id, address=cell["address"]))
                    unsupported += 1
            unit["cells"].extend(converted)
            blocks = _row_blocks(sheet_id, sheet_name, part, row, converted, limits.max_block_chars, sheet_tables)
            total_blocks += len(blocks)
            if total_blocks > limits.max_blocks:
                raise limit_error()
            unit["blocks"].extend(blocks)
        sheet_meta["bounds"] = {"row_start": bounds[0], "column_start": bounds[1],
                                "row_end": bounds[2], "column_end": bounds[3]} if bounds is not None else None
        sheet_meta["cell_count"] = len(unit["cells"])
        declared_dimension = sheet_meta.get("declared_dimension")
        if declared_dimension and bounds is not None:
            try:
                declared_bounds = range_coordinates(declared_dimension)
            except IngestionError:
                declared_bounds = None
            if declared_bounds != tuple(bounds):
                result["warnings"].append(_warn("XLSX_DECLARED_DIMENSION_MISMATCH", "La dimension déclarée diffère des cellules présentes ; la lecture utilise les adresses sources.",
                                                  unit_id=sheet_id, declared_dimension=declared_dimension,
                                                  actual_bounds=sheet_meta["bounds"]))
        present_addresses = {cell["address"] for cell in unit["cells"]}
        sheet_meta["orphan_comments"] = [dict(comment, address=address) for address, comment in comments.items()
                                          if address not in present_addresses]
        sheet_meta["unsupported_count"] = unsupported - initial_unsupported
        sheet_meta["extraction_warnings"] = result["warnings"][first_warning_index:]
        result["units"].append(unit)
        result["sections"].append({"id": sheet_id, "title": sheet_name, "unit_id": sheet_id,
                                   "parent_id": None, "order_index": order})
        if unit_sink is not None:
            unit_sink(unit)
        if checkpoint is not None:
            checkpoint(sheet_id)
    result["coverage"] = {"total": len(result["units"]), "processed": len(result["units"]) - sum(
        not unit["metadata"].get("supported", True) for unit in result["units"]),
        "unsupported": unsupported, "cells": total_cells, "blocks": total_blocks}
    if unsupported:
        result["status"] = "ready_partial"
        result["parser_complete"] = False
    return result
