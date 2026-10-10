"""Read DOCX source parts without rendering, executing fields or inventing pages.

The source XML is authoritative for both OOXML namespace families. Paragraph
strings are literal final-view text; table strings are explicit tab/newline
serializations accompanied by the cells, source paragraphs and offset bindings.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from lxml import etree

from ..errors import IngestionError
from .opc import OfficePackage

WORD_NAMESPACES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
}
REL_NAMESPACES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/officeDocument/relationships",
}
RASTER_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/tiff"}
DRAWING_NAMESPACES = {
    "http://schemas.openxmlformats.org/drawingml/2006/main",
    "http://purl.oclc.org/ooxml/drawingml/main",
}
MC_NAMESPACE = "http://schemas.openxmlformats.org/markup-compatibility/2006"
REVISION_TAGS = {"ins", "del", "moveFrom", "moveTo"}
PROPERTY_TAGS = {"pPr", "rPr", "tblPr", "tblGrid", "trPr", "tcPr", "sdtPr", "sdtEndPr"}
PART_TITLES = {"document": "Document", "header": "En-tête", "footer": "Pied de page",
               "footnotes": "Note de bas de page", "endnotes": "Note de fin", "comments": "Commentaire"}


def _local(element: Any) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def _namespace(element: Any) -> str:
    return etree.QName(element).namespace or "" if isinstance(element.tag, str) else ""


def _word(element: Any, name: str) -> bool:
    return _namespace(element) in WORD_NAMESPACES and _local(element) == name


def _attr(element: Any, name: str, namespaces: set[str] | None = None) -> str | None:
    for key, value in element.attrib.items():
        qualified = etree.QName(key)
        if qualified.localname == name and (namespaces is None or qualified.namespace in namespaces):
            return value
    return None


def _child(element: Any, name: str) -> Any:
    return next((item for item in element if _word(item, name)), None) if element is not None else None


def _value(element: Any, name: str) -> str | None:
    item = _child(element, name) if element is not None else None
    return _attr(item, "val", WORD_NAMESPACES) if item is not None else None


def _integer(value: str | None, default: int | None = None) -> int | None:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _on(element: Any) -> bool:
    return element is not None and (_attr(element, "val", WORD_NAMESPACES) or "true") not in {"0", "false", "off"}


def _path(parent: str, element: Any, ordinal: int) -> str:
    # The ordinal counts every XML element sibling, including omitted revisions.
    return f"{parent}/{_local(element)}[{ordinal}]"


def _source_path(element: Any) -> str:
    items = []
    while element is not None:
        parent = element.getparent()
        ordinal = 1 if parent is None else list(parent).index(element) + 1
        items.append(f"{_local(element)}[{ordinal}]")
        element = parent
    return "/" + "/".join(reversed(items))


def _walk_paths(element: Any, path: str):
    """Linear source walk; no repeated scan of a many-paragraph body."""
    yield element, path
    for ordinal, child in enumerate(element, 1):
        if isinstance(child.tag, str):
            yield from _walk_paths(child, _path(path, child, ordinal))


def _descendant_path(ancestor: Any, ancestor_path: str, element: Any) -> str:
    items = []
    while element is not ancestor:
        parent = element.getparent()
        items.append(f"{_local(element)}[{list(parent).index(element) + 1}]")
        element = parent
    return ancestor_path + "/" + "/".join(reversed(items))


def _id(part: str, path: str, prefix: str = "docx") -> str:
    return f"{prefix}-" + hashlib.sha256(f"{part}\0{path}".encode()).hexdigest()[:24]


def _literal(element: Any) -> str:
    values = []
    for item in element.iter():
        if _namespace(item) not in WORD_NAMESPACES:
            continue
        name = _local(item)
        if name in {"t", "delText"}:
            values.append(item.text or "")
        elif name in {"tab", "ptab"}:
            values.append("\t")
        elif name in {"br", "cr"}:
            values.append("\n")
        elif name == "noBreakHyphen":
            values.append("\u2011")
        elif name == "softHyphen":
            values.append("\u00ad")
    return "".join(values)


def _properties_data(element: Any) -> dict[str, Any]:
    return {"kind": _local(element), "namespace": _namespace(element), "attributes": dict(element.attrib),
            "text": element.text, "children": [_properties_data(child) for child in element if isinstance(child.tag, str)]}


class _DocxReader:
    def __init__(self, package: OfficePackage, checkpoint: Callable[[str], None] | None,
                 unit_sink: Callable[[dict[str, Any]], None] | None,
                 cached_units: Mapping[str, dict[str, Any]] | None):
        self.package = package
        self.checkpoint = checkpoint
        self.unit_sink = unit_sink
        self.cached_units = cached_units or {}
        self.units: list[dict[str, Any]] = []
        self.sections: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {"revision_view": "final", "fields_recalculated": False}
        self.styles: dict[str, Any] = {}
        self.default_style: str | None = None
        self.style_cache: dict[str, dict[str, Any]] = {}
        self.numbers: dict[str, dict[int, dict[str, Any]]] = {}
        self.counters: dict[str, dict[int, int]] = {}
        self.section_stack: list[dict[str, Any]] = []
        self.part_relations: dict[str, dict[str, dict[str, Any]]] = {}
        self.image_metadata: dict[str, dict[str, Any]] = {}
        self._charged_parts: set[str] = set()
        self.source_text_chars = 0
        self.block_count = self.cell_count = self.grid_cells = self.text_chars = self.total = self.unsupported = 0
        self._seen_warnings: set[tuple[str, str, str]] = set()

    def warning(self, code: str, message: str, part: str, path: str, *, unsupported: bool = True) -> None:
        key = (code, part, path)
        if key in self._seen_warnings:
            return
        self._seen_warnings.add(key)
        self.warnings.append({"code": code, "message": message, "severity": "warning", "part": part,
                              "element_path": path})
        if unsupported:
            self.unsupported += 1

    def limit(self, condition: bool, name: str) -> None:
        if condition:
            raise IngestionError("OFFICE_LIMIT_EXCEEDED", "Le document Office dépasse une limite d'extraction.",
                                 {"limit": name})

    def xml(self, part: str) -> Any:
        root = self.package.xml(part)
        if part not in self._charged_parts:
            self._charged_parts.add(part)
            for node in root.iter():
                self.source_text_chars += len(node.text or "") + len(node.tail or "") + sum(len(value) for value in node.attrib.values())
                self.limit(self.source_text_chars > self.package.limits.max_text_chars, "max_text_chars")
        return root

    def source_block(self) -> None:
        self.block_count += 1
        self.limit(self.block_count > self.package.limits.max_blocks, "max_blocks")

    def relations(self, part: str) -> dict[str, dict[str, Any]]:
        if part not in self.part_relations:
            self.part_relations[part] = {rel["id"]: rel for rel in self.package.relations(part)}
        return self.part_relations[part]

    def related(self, part: str, kind: str) -> str | None:
        return next((rel["target"] for rel in self.relations(part).values()
                     if rel["type"].rsplit("/", 1)[-1] == kind and not rel["external"]), None)

    def properties(self, element: Any, path: str, part: str) -> dict[str, Any]:
        if element is None:
            return {}
        result: dict[str, Any] = {}
        outline = _value(element, "outlineLvl")
        if outline is not None:
            level = _integer(outline)
            if level is None or not 0 <= level <= 9:
                self.warning("DOCX_OUTLINE_INVALID", "Un niveau de titre source n'est pas interprétable.", part, path)
            else:
                result["outline_level"] = level
        num = _child(element, "numPr")
        if num is not None:
            result["numbering"] = {key: value for key, value in
                                   (("num_id", _value(num, "numId")), ("level", _integer(_value(num, "ilvl"))))
                                   if value is not None}
        changes = [node for node in element.iter() if _namespace(node) in WORD_NAMESPACES and _local(node).endswith("PrChange")]
        if changes:
            result["property_revisions"] = [_properties_data(change) for change in changes]
        return result

    def load_styles(self) -> None:
        part = self.related(self.package.main_part, "styles")
        if part is None:
            return
        root = self.xml(part)
        for position, style in enumerate(root, 1):
            if not _word(style, "style"):
                continue
            identity = _attr(style, "styleId", WORD_NAMESPACES)
            if identity is None:
                self.warning("DOCX_STYLE_ID_MISSING", "Un style ne porte pas d'identifiant source.", part,
                             f"/styles[1]/style[{position}]")
                continue
            if identity in self.styles:
                self.warning("DOCX_STYLE_DUPLICATE", "Un identifiant de style est défini plusieurs fois.", part,
                             f"/styles[1]/style[{position}]")
                continue
            self.styles[identity] = {"based_on": _value(style, "basedOn"), "name": _value(style, "name"),
                                     "properties": self.properties(_child(style, "pPr"), f"/style[{position}]", part)}
            if _attr(style, "type", WORD_NAMESPACES) == "paragraph" and _attr(style, "default", WORD_NAMESPACES) in {"1", "true", "on"}:
                self.default_style = identity

    def resolved_style(self, identity: str | None) -> dict[str, Any]:
        if not identity:
            return {}
        if identity in self.style_cache:
            return self.style_cache[identity]
        seen: set[str] = set()
        chain: list[dict[str, Any]] = []
        identities: list[str] = []
        current: str | None = identity
        while current:
            if current in seen:
                self.warning("DOCX_STYLE_CYCLE", "L'héritage des styles contient un cycle.", self.package.main_part,
                             f"/styles/{identity}")
                break
            seen.add(current)
            identities.append(current)
            style = self.styles.get(current)
            if style is None:
                self.warning("DOCX_STYLE_UNKNOWN", "Un style source est absent des définitions.", self.package.main_part,
                             f"/styles/{current}")
                break
            chain.append(style)
            current = style["based_on"]
        result: dict[str, Any] = {}
        for style in reversed(chain):
            previous_numbering = result.get("numbering", {})
            result.update(style["properties"])
            if "numbering" in style["properties"]:
                result["numbering"] = {**previous_numbering, **style["properties"]["numbering"]}
        result["style_chain"] = identities
        self.style_cache[identity] = result
        return result

    def load_numbering(self) -> None:
        part = self.related(self.package.main_part, "numbering")
        if part is None:
            return
        root = self.xml(part)
        abstracts: dict[str, dict[int, dict[str, Any]]] = {}
        for abstract in root:
            if not _word(abstract, "abstractNum"):
                continue
            identity = _attr(abstract, "abstractNumId", WORD_NAMESPACES)
            if identity is None:
                continue
            abstracts[identity] = {}
            for level in abstract:
                if not _word(level, "lvl"):
                    continue
                index = _integer(_attr(level, "ilvl", WORD_NAMESPACES))
                if index is not None and 0 <= index <= 8:
                    abstracts[identity][index] = self.number_level(level)
        for num in root:
            if not _word(num, "num"):
                continue
            identity = _attr(num, "numId", WORD_NAMESPACES)
            levels = {key: dict(value) for key, value in abstracts.get(_value(num, "abstractNumId") or "", {}).items()}
            for override in num:
                if not _word(override, "lvlOverride"):
                    continue
                index = _integer(_attr(override, "ilvl", WORD_NAMESPACES))
                if index is None or not 0 <= index <= 8:
                    continue
                level = _child(override, "lvl")
                if level is not None:
                    levels[index] = self.number_level(level)
                start = _integer(_value(override, "startOverride"))
                if start is not None:
                    levels.setdefault(index, {})["start"] = start
            if identity is not None:
                self.numbers[identity] = levels

    @staticmethod
    def number_level(level: Any) -> dict[str, Any]:
        return {"start": _integer(_value(level, "start"), 1), "format": _value(level, "numFmt") or "decimal",
                "text": _value(level, "lvlText"), "restart": _integer(_value(level, "lvlRestart")),
                "suffix": _value(level, "suff") or "tab", "legal": _child(level, "isLgl") is not None}

    @staticmethod
    def number_text(number: int, fmt: str) -> str | None:
        if fmt == "decimal":
            return str(number)
        if fmt == "decimalZero":
            return str(number).zfill(2)
        if fmt in {"lowerLetter", "upperLetter"} and 0 < number <= 100000:
            result = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                result = chr(65 + remainder) + result
            return result.lower() if fmt == "lowerLetter" else result
        if fmt in {"lowerRoman", "upperRoman"} and 0 < number < 4000:
            result = ""
            for value, roman in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
                quotient, number = divmod(number, value)
                result += roman * quotient
            return result.lower() if fmt == "lowerRoman" else result
        if fmt == "none":
            return ""
        return None

    def numbering(self, properties: dict[str, Any], part: str, path: str) -> dict[str, Any] | None:
        source = properties.get("numbering")
        if not source or source.get("num_id") == "0":
            return None
        identity, index = str(source.get("num_id", "")), source.get("level", 0)
        levels = self.numbers.get(identity, {})
        definition = levels.get(index)
        result = {**source, "level": index, "label": None, "label_is_derived": True}
        if definition is None:
            self.warning("DOCX_NUMBERING_UNRESOLVED", "La numérotation source n'a pas de définition exploitable.", part, path)
            return result
        result["definition"] = definition
        counters = self.counters.setdefault(identity, {})
        counters[index] = counters.get(index, int(definition.get("start", 1)) - 1) + 1
        for deeper in list(counters):
            restart = levels.get(deeper, {}).get("restart")
            if deeper > index and restart != 0 and (restart is None or restart - 1 == index):
                del counters[deeper]
        label = definition.get("text")
        if definition["format"] == "bullet":
            result["label"] = label
            return result
        if label is None:
            self.warning("DOCX_NUMBERING_LABEL_MISSING", "Le modèle source du libellé de liste est absent.", part, path)
            return result
        failed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal failed
            at = int(match.group(1)) - 1
            level = levels.get(at, {})
            value = counters.get(at, int(level.get("start", 1)))
            formatted = self.number_text(value, "decimal" if definition["legal"] else level.get("format", "decimal"))
            if formatted is None:
                failed = True
                return match.group(0)
            return formatted

        derived = re.sub(r"%([1-9])", replace, label)
        if failed:
            self.warning("DOCX_NUMBERING_FORMAT_UNSUPPORTED", "Un format de numérotation n'est pas calculé.", part, path)
        else:
            result["label"] = derived
        return result

    def inline(self, element: Any, part: str, path: str) -> tuple[str, dict[str, Any]]:
        pieces: list[str] = []
        metadata: dict[str, Any] = {"runs": [], "references": [], "revisions": [], "fields": [], "images": [],
                                    "bookmarks": [], "links": [], "textboxes": []}
        offset = 0

        def append(text: str) -> None:
            nonlocal offset
            pieces.append(text)
            offset += len(text)

        def visit(node: Any, source_path: str) -> None:
            if not isinstance(node.tag, str):
                return
            name, namespace = _local(node), _namespace(node)
            if namespace == MC_NAMESPACE and name == "AlternateContent":
                fallback = next((child for child in node if _local(child) == "Fallback"), None)
                choices = [(position, child) for position, child in enumerate(node, 1) if _local(child) == "Choice"]
                selected = fallback if fallback is not None else (choices[0][1] if choices else None)
                self.warning("DOCX_ALTERNATE_CONTENT", "Une branche de compatibilité source est sélectionnée ; rendu non reproduit.", part, source_path)
                if selected is not None:
                    visit(selected, _path(source_path, selected, list(node).index(selected) + 1))
                return
            if namespace in WORD_NAMESPACES:
                if name in PROPERTY_TAGS:
                    return
                if name in REVISION_TAGS:
                    metadata["revisions"].append({"kind": name, "id": _attr(node, "id", WORD_NAMESPACES),
                                                   "author": _attr(node, "author", WORD_NAMESPACES),
                                                   "date": _attr(node, "date", WORD_NAMESPACES),
                                                   "element_path": source_path, "text": _literal(node),
                                                   "included": name in {"ins", "moveTo"}, "offset": offset})
                    if name in {"del", "moveFrom"}:
                        return
                elif name in {"t", "delText"}:
                    if name == "delText":
                        self.warning("DOCX_DELETED_TEXT_WITHOUT_REVISION", "Un texte supprimé apparaît hors d'une révision reconnue.", part, source_path)
                        return
                    append(node.text or "")
                    return
                elif name in {"tab", "ptab"}:
                    append("\t")
                    return
                elif name in {"br", "cr"}:
                    append("\n")
                    metadata.setdefault("breaks", []).append({"offset": offset - 1, "type": _attr(node, "type", WORD_NAMESPACES) or "textWrapping"})
                    return
                elif name in {"noBreakHyphen", "softHyphen"}:
                    append("\u2011" if name == "noBreakHyphen" else "\u00ad")
                    return
                elif name == "instrText":
                    metadata["fields"].append({"kind": "instruction", "instruction": node.text or "", "offset": offset,
                                                "element_path": source_path, "evaluated": False})
                    return
                elif name in {"fldChar", "fldSimple"}:
                    metadata["fields"].append({"kind": name, "instruction": _attr(node, "instr", WORD_NAMESPACES),
                                                "field_type": _attr(node, "fldCharType", WORD_NAMESPACES),
                                                "offset": offset, "element_path": source_path, "evaluated": False})
                elif name in {"footnoteReference", "endnoteReference", "commentReference", "commentRangeStart", "commentRangeEnd"}:
                    relation_kind = "footnotes" if name == "footnoteReference" else "endnotes" if name == "endnoteReference" else "comments"
                    metadata["references"].append({"kind": name, "id": _attr(node, "id", WORD_NAMESPACES),
                                                    "offset": offset, "element_path": source_path,
                                                    "target_part": self.related(self.package.main_part, relation_kind)})
                    return
                elif name in {"bookmarkStart", "bookmarkEnd"}:
                    metadata["bookmarks"].append({"kind": name, "id": _attr(node, "id", WORD_NAMESPACES),
                                                   "name": _attr(node, "name", WORD_NAMESPACES), "offset": offset})
                    return
                elif name == "hyperlink":
                    relationship_id = _attr(node, "id", REL_NAMESPACES)
                    relation = self.relations(part).get(relationship_id or "")
                    record = {"element_path": source_path, "start": offset, "anchor": _attr(node, "anchor", WORD_NAMESPACES),
                              "relationship_id": relationship_id, "relation": relation, "followed": False}
                    for position, child in enumerate(node, 1):
                        visit(child, _path(source_path, child, position))
                    record["end"] = offset
                    metadata["links"].append(record)
                    if relationship_id and relation is None:
                        self.warning("DOCX_RELATION_MISSING", "Un lien source n'a pas de relation définie.", part, source_path)
                    return
                elif name in {"drawing", "pict"}:
                    metadata["images"].extend(self.images(node, part, source_path, offset))
                    # Textboxes are separate source content, never added twice to the paragraph.
                    for textbox in node.iter():
                        if _word(textbox, "txbxContent"):
                            textbox_path = _descendant_path(node, source_path, textbox)
                            contents = []
                            for child, child_path, revisions in self.source_items(textbox, part, textbox_path):
                                content = self.paragraph(child, part, child_path, heading=False) if _word(child, "p") else self.table(child, part, child_path)
                                if revisions:
                                    content["structure"].setdefault("revisions", []).extend(revisions)
                                contents.append(content)
                            metadata["textboxes"].append({"element_path": textbox_path,
                                                           "text": "\n".join(content["text"] for content in contents),
                                                           "contents": contents, "placement": "source_anchor"})
                            self.warning("DOCX_TEXTBOX_LAYOUT", "Le texte d'une zone flottante est conservé à son ancre ; sa position visuelle n'est pas reproduite.", part, source_path)
                    return
                elif name == "sym":
                    metadata.setdefault("symbols", []).append({"font": _attr(node, "font", WORD_NAMESPACES),
                                                               "char": _attr(node, "char", WORD_NAMESPACES), "offset": offset})
                    self.warning("DOCX_SYMBOL_UNMAPPED", "Un symbole de police est conservé sans conversion Unicode inventée.", part, source_path)
                    return
                elif name in {"object", "altChunk"}:
                    self.warning("DOCX_ACTIVE_CONTENT_UNSUPPORTED", "Un objet incorporé ou contenu alternatif n'est pas interprété ni exécuté.", part, source_path)
                    metadata.setdefault("unsupported", []).append({"kind": name, "element_path": source_path})
                    return
                elif name in {"lastRenderedPageBreak", "proofErr", "permStart", "permEnd"}:
                    return
                elif name in {"sdt", "customXml", "smartTag", "dir", "bdo"}:
                    metadata.setdefault("wrappers", []).append({"kind": name, "element_path": source_path,
                                                                "attributes": dict(node.attrib)})
                    if name == "sdt":
                        properties = _child(node, "sdtPr")
                        if properties is not None:
                            metadata["wrappers"][-1]["properties"] = _properties_data(properties)
                elif name not in {"r", "p", "sdtContent", "footnoteRef", "endnoteRef", "annotationRef"}:
                    self.warning("DOCX_INLINE_ELEMENT_UNSUPPORTED", "Un élément WordprocessingML n'est pas interprété complètement ; son texte reconnu est conservé.", part, source_path)
            elif namespace not in {MC_NAMESPACE, ""}:
                if name in {"oMath", "oMathPara"}:
                    metadata.setdefault("equations", []).append({"element_path": source_path,
                                                                 "text": "".join(node.itertext())})
                    self.warning("DOCX_EQUATION_UNSUPPORTED", "Une équation est conservée comme métadonnée ; sa sémantique n'est pas interprétée.", part, source_path)
                    return
                if name not in {"Choice", "Fallback"}:
                    self.warning("DOCX_INLINE_EXTENSION", "Un élément d'extension est conservé sans interprétation complète.", part, source_path)
            start = offset
            for position, child in enumerate(node, 1):
                visit(child, _path(source_path, child, position))
            if namespace in WORD_NAMESPACES and name == "r":
                run_properties = _child(node, "rPr")
                metadata["runs"].append({"element_path": source_path, "start": start, "end": offset,
                                         "style": _value(run_properties, "rStyle"),
                                         "language": _value(run_properties, "lang")})

        for position, child in enumerate(element, 1):
            visit(child, _path(path, child, position))
        return "".join(pieces), {key: value for key, value in metadata.items() if value}

    def images(self, element: Any, part: str, path: str, offset: int) -> list[dict[str, Any]]:
        properties = next((node for node in element.iter() if _local(node) in {"docPr", "cNvPr"}), None)
        extent = next((node for node in element.iter() if _local(node) == "extent"), None)
        anchor = "floating" if any(_local(node) == "anchor" for node in element.iter()) else "inline"
        results = []
        for node in element.iter():
            if (_namespace(node) in DRAWING_NAMESPACES and _local(node) == "blip") or _local(node) == "imagedata":
                identity = _attr(node, "embed", REL_NAMESPACES) or _attr(node, "link", REL_NAMESPACES) or _attr(node, "id", REL_NAMESPACES)
                relation = self.relations(part).get(identity or "")
                record: dict[str, Any] = {"relationship_id": identity, "relation": relation, "element_path": path,
                                           "offset": offset, "placement": anchor, "interpreted": False,
                                           "alt_text": _attr(properties, "descr") if properties is not None else None,
                                           "title": _attr(properties, "title") if properties is not None else None,
                                           "name": _attr(properties, "name") if properties is not None else None,
                                           "extent_emu": {"cx": _attr(extent, "cx"), "cy": _attr(extent, "cy")} if extent is not None else None}
                if relation is None:
                    self.warning("DOCX_IMAGE_RELATION_MISSING", "Une image source n'a pas de relation définie.", part, path)
                elif relation["external"]:
                    self.warning("DOCX_EXTERNAL_IMAGE_NOT_LOADED", "Une image externe reste référencée ; aucun accès réseau n'est effectué.", part, path)
                else:
                    target = relation["target"]
                    if target not in self.image_metadata:
                        data = self.package.read(target)
                        self.image_metadata[target] = {"part": target, "sha256": hashlib.sha256(data).hexdigest(),
                                                       "content_type": self.package.content_type(target), "size_bytes": len(data)}
                    record.update(self.image_metadata[target])
                    if record["content_type"] not in RASTER_IMAGE_TYPES:
                        self.warning("DOCX_IMAGE_TYPE_UNSUPPORTED", "Le type d'image source n'est pas un format raster pris en charge ; aucun rendu ni conversion n'est effectué.", part, path)
                results.append(record)
        if not results and not any(_word(node, "txbxContent") for node in element.iter()):
            self.warning("DOCX_DRAWING_UNINTERPRETED", "Un dessin sans image reconnue n'est pas interprété.", part, path)
        if _word(element, "pict"):
            self.warning("DOCX_VML_LAYOUT", "Un objet VML est conservé à son ancre ; son rendu n'est pas reproduit.", part, path)
        return results

    def paragraph(self, element: Any, part: str, path: str, *, heading: bool = True) -> dict[str, Any]:
        self.source_block()
        ppr = _child(element, "pPr")
        style_id = _value(ppr, "pStyle") or self.default_style
        properties = dict(self.resolved_style(style_id))
        direct = self.properties(ppr, path, part)
        if "numbering" in direct:
            direct["numbering"] = {**properties.get("numbering", {}), **direct["numbering"]}
        properties.update(direct)
        text, inline = self.inline(element, part, path)
        structure: dict[str, Any] = {"style_id": style_id, "style_name": self.styles.get(style_id or "", {}).get("name"),
                                    **properties, **inline, "source_text": text}
        numbering = self.numbering(properties, part, path)
        if numbering is not None:
            structure["numbering"] = numbering
        para_id = next((value for key, value in element.attrib.items() if etree.QName(key).localname == "paraId"), None)
        if para_id is not None:
            structure["para_id"] = para_id
        property_revisions = [node for node in element.iter() if _namespace(node) in WORD_NAMESPACES and _local(node).endswith("PrChange")]
        if property_revisions:
            structure["property_revisions"] = [_properties_data(node) for node in property_revisions]
        level = properties.get("outline_level", 9)
        kind = "heading" if level < 9 else "paragraph"
        result: dict[str, Any] = {"id": _id(part, path), "kind": kind, "text": text, "element_path": path, "structure": structure}
        if heading and kind == "heading":
            while self.section_stack and self.section_stack[-1]["level"] >= level + 1:
                self.section_stack.pop()
            section = {"id": _id(part, path, "section"), "title": text,
                       "parent_id": self.section_stack[-1]["id"] if self.section_stack else None,
                       "level": level + 1, "block_ids": []}
            self.sections.append(section)
            self.section_stack.append(section)
        result["section_id"] = self.section_stack[-1]["id"] if self.section_stack else None
        return result

    def rows(self, element: Any, part: str, path: str):
        for position, row in enumerate(element, 1):
            if not isinstance(row.tag, str):
                continue
            source_path = _path(path, row, position)
            if _word(row, "tr"):
                deleted = _child(_child(row, "trPr"), "del")
                if deleted is not None:
                    self.metadata.setdefault("revisions", []).append({"kind": "deleted_row", "part": part,
                                                                      "element_path": source_path, "included": False,
                                                                      "text": _literal(row), "id": _attr(deleted, "id", WORD_NAMESPACES)})
                else:
                    yield row, source_path
            elif _namespace(row) in WORD_NAMESPACES and _local(row) in {"ins", "moveTo", "sdt", "sdtContent", "customXml"}:
                yield from self.rows(row, part, source_path)
            elif _namespace(row) in WORD_NAMESPACES and _local(row) in {"del", "moveFrom"}:
                self.metadata.setdefault("revisions", []).append({"kind": _local(row), "part": part,
                                                                  "element_path": source_path, "included": False,
                                                                  "text": _literal(row), "id": _attr(row, "id", WORD_NAMESPACES)})
            elif not (_namespace(row) in WORD_NAMESPACES and _local(row) in PROPERTY_TAGS):
                self.warning("DOCX_TABLE_ELEMENT_UNSUPPORTED", "Un élément du tableau n'est pas interprété.", part, source_path)

    def source_items(self, parent: Any, part: str, parent_path: str):
        """Walk wrappers without changing the ordinals of source descendants."""
        for position, item in enumerate(parent, 1):
            if not isinstance(item.tag, str):
                continue
            path = _path(parent_path, item, position)
            if _namespace(item) in WORD_NAMESPACES:
                name = _local(item)
                if name in {"p", "tbl"}:
                    yield item, path, []
                elif name in {"sdt", "sdtContent", "customXml", "ins", "moveTo"}:
                    if name in {"sdt", "customXml"}:
                        self.metadata.setdefault("content_wrappers", {})[f"{part}:{path}"] = {
                            "kind": name, "part": part, "element_path": path, "attributes": dict(item.attrib),
                            "properties": _properties_data(_child(item, "sdtPr")) if _child(item, "sdtPr") is not None else None,
                        }
                    for node, nested_path, revisions in self.source_items(item, part, path):
                        revision = [{"kind": name, "id": _attr(item, "id", WORD_NAMESPACES),
                                     "author": _attr(item, "author", WORD_NAMESPACES), "date": _attr(item, "date", WORD_NAMESPACES),
                                     "element_path": path, "included": True}] if name in REVISION_TAGS else []
                        yield node, nested_path, revision + revisions
                elif name in {"del", "moveFrom"}:
                    self.metadata.setdefault("revisions", []).append({"kind": name, "part": part,
                                                                      "element_path": path, "id": _attr(item, "id", WORD_NAMESPACES),
                                                                      "author": _attr(item, "author", WORD_NAMESPACES),
                                                                      "date": _attr(item, "date", WORD_NAMESPACES),
                                                                      "text": _literal(item), "included": False})
                elif name in PROPERTY_TAGS or name == "sectPr":
                    continue
                else:
                    self.warning("DOCX_BLOCK_UNSUPPORTED", "Un élément de document n'est pas interprété dans la vue de lecture.", part, path)
            elif _namespace(item) == MC_NAMESPACE and _local(item) == "AlternateContent":
                selected = next((child for child in item if _local(child) == "Fallback"), None)
                if selected is None:
                    selected = next((child for child in item if _local(child) == "Choice"), None)
                self.warning("DOCX_ALTERNATE_CONTENT", "Une branche de compatibilité source est sélectionnée ; rendu non reproduit.", part, path)
                if selected is not None:
                    yield from self.source_items(selected, part, _path(path, selected, list(item).index(selected) + 1))
            else:
                self.warning("DOCX_BLOCK_EXTENSION", "Un élément d'extension documentaire n'est pas interprété.", part, path)

    def table(self, element: Any, part: str, path: str) -> dict[str, Any]:
        self.source_block()
        identity = _id(part, path, "table")
        grid = _child(element, "tblGrid")
        grid_widths = [_attr(child, "w", WORD_NAMESPACES) for child in grid if _word(child, "gridCol")] if grid is not None else []
        self.limit(len(grid_widths) > self.package.limits.max_cells, "table_grid")
        structure: dict[str, Any] = {"id": identity, "part": part, "element_path": path, "grid_widths": grid_widths,
                                    "rows": [], "text_is_derived": True, "serialization": "tab_newline_v1",
                                    "style_id": _value(_child(element, "tblPr"), "tblStyle")}
        active_vertical: dict[int, dict[str, Any]] = {}
        texts: list[str] = []
        bindings: list[dict[str, Any]] = []
        offset = 0
        for row_index, (row, row_path) in enumerate(self.rows(element, part, path)):
            row_properties = _child(row, "trPr")
            grid_before = _integer(_value(row_properties, "gridBefore"), 0) or 0
            grid_after = _integer(_value(row_properties, "gridAfter"), 0) or 0
            self.limit(grid_before < 0 or grid_after < 0 or grid_before + grid_after > self.package.limits.max_cells, "table_grid")
            row_info: dict[str, Any] = {"row": row_index, "element_path": row_path, "grid_before": grid_before,
                                        "grid_after": grid_after, "is_header": _on(_child(row_properties, "tblHeader")),
                                        "cells": []}
            column = grid_before
            next_vertical: dict[int, dict[str, Any]] = {}
            horizontal: dict[str, Any] | None = None
            row_texts: list[str] = []
            for cell_position, cell in enumerate(row, 1):
                if not _word(cell, "tc"):
                    if isinstance(cell.tag, str) and not _word(cell, "trPr"):
                        self.warning("DOCX_TABLE_ROW_EXTENSION", "Un élément de ligne de tableau n'est pas interprété.", part,
                                     _path(row_path, cell, cell_position))
                    continue
                self.cell_count += 1
                self.limit(self.cell_count > self.package.limits.max_cells, "max_cells")
                cell_path = _path(row_path, cell, cell_position)
                properties = _child(cell, "tcPr")
                raw_span = _value(properties, "gridSpan")
                span = _integer(raw_span, 1) or 1
                if raw_span is not None and (_integer(raw_span) is None or int(raw_span) <= 0):
                    self.warning("DOCX_TABLE_SPAN_INVALID", "Une largeur de fusion source n'est pas un entier ; la cellule est conservée séparément.", part, cell_path)
                    span = 1
                self.limit(span < 1 or column + span > self.package.limits.max_cells, "table_grid")
                self.grid_cells += span
                self.limit(self.grid_cells > self.package.limits.max_cells, "max_cells")
                vmerge = _child(properties, "vMerge") if properties is not None else None
                hmerge = _child(properties, "hMerge") if properties is not None else None
                vertical_mode = (_attr(vmerge, "val", WORD_NAMESPACES) or "continue") if vmerge is not None else None
                horizontal_mode = (_attr(hmerge, "val", WORD_NAMESPACES) or "continue") if hmerge is not None else None
                if vertical_mode not in {None, "restart", "continue"} or horizontal_mode not in {None, "restart", "continue"}:
                    self.warning("DOCX_MERGE_MODE_INVALID", "Un mode de fusion source n'est pas interprétable ; les cellules restent distinctes.", part, cell_path)
                contents: list[dict[str, Any]] = []
                for child, child_path, revisions in self.source_items(cell, part, cell_path):
                    if _word(child, "p"):
                        content = self.paragraph(child, part, child_path, heading=False)
                    else:
                        content = self.table(child, part, child_path)
                    if revisions:
                        content["structure"].setdefault("revisions", []).extend(revisions)
                    contents.append(content)
                cell_text = "\n".join(content["text"] for content in contents)
                self.limit(len(cell_text) > self.package.limits.max_cell_chars, "max_cell_chars")
                info: dict[str, Any] = {"id": _id(part, cell_path, "cell"), "element_path": cell_path,
                                        "row": row_index, "column": column, "column_span": span, "row_span": 1,
                                        "vertical_merge": vertical_mode, "horizontal_merge": horizontal_mode,
                                        "text": cell_text, "contents": contents, "merge_origin_id": None}
                origin: dict[str, Any] | None = None
                if horizontal_mode == "continue":
                    origin = horizontal
                    if origin is None:
                        self.warning("DOCX_MERGE_ORPHAN", "Une continuation de fusion horizontale n'a pas d'origine.", part, cell_path)
                    else:
                        origin["column_span"] += span
                elif horizontal_mode == "restart":
                    horizontal = info
                else:
                    horizontal = None
                if vertical_mode == "continue":
                    previous = [active_vertical.get(at) for at in range(column, column + span)]
                    first = previous[0] if previous else None
                    if first is None or any(item is not first for item in previous):
                        self.warning("DOCX_MERGE_ORPHAN", "Une continuation de fusion verticale n'a pas d'origine compatible.", part, cell_path)
                    else:
                        origin = first
                        if row_index + 1 > origin["row"] + origin["row_span"]:
                            origin["row_span"] = row_index - origin["row"] + 1
                if vertical_mode in {"restart", "continue"}:
                    for at in range(column, column + span):
                        next_vertical[at] = origin or info
                if origin is not None:
                    info["merge_origin_id"] = origin["id"]
                    if cell_text:
                        self.warning("DOCX_MERGE_CONTINUATION_TEXT", "Une continuation de fusion contient du texte ; il reste conservé séparément.", part, cell_path)
                row_info["cells"].append(info)
                # Empty continuation placeholders retain the grid without repeating the origin.
                row_texts.append(cell_text)
                column += span
            active_vertical = next_vertical
            row_info["column_count"] = column + grid_after
            structure["rows"].append(row_info)
            row_text = "\t".join(row_texts)
            texts.append(row_text)
            cell_offset = offset
            for cell in row_info["cells"]:
                bindings.append({"start": cell_offset, "end": cell_offset + len(cell["text"]),
                                 "element_path": cell["element_path"], "cell_id": cell["id"],
                                 "row": cell["row"], "column": cell["column"]})
                cell_offset += len(cell["text"]) + 1
            offset += len(row_text) + 1
        text = "\n".join(texts)
        structure["column_count"] = max([len(grid_widths)] + [row["column_count"] for row in structure["rows"]])
        result = {"id": _id(part, path), "kind": "table", "text": text, "element_path": path,
                  "section_id": self.section_stack[-1]["id"] if self.section_stack else None,
                  "structure": structure, "bindings": bindings}
        self.tables.append(structure)
        return result

    def add_block(self, unit: dict[str, Any], source: dict[str, Any]) -> None:
        self.text_chars += len(source["text"])
        self.limit(self.text_chars > self.package.limits.max_text_chars, "max_text_chars")
        block = {"id": source["id"], "kind": source["kind"], "text": source["text"],
                 "section_id": source.get("section_id"), "structure": source["structure"],
                 "bindings": source.get("bindings", []),
                 "locator": {"kind": "docx_element", "unit_id": unit["id"], "part": unit["part"],
                             "element_path": source["element_path"]}}
        unit["blocks"].append(block)
        for section in self.section_stack:
            section["block_ids"].append(block["id"])
        self.total += 1
        if self.checkpoint is not None:
            self.checkpoint(f"{unit['part']}:{source['element_path']}")

    def read_part(self, part: str, role: str, root: Any, *, note: dict[str, Any] | None = None,
                  source_path: str | None = None) -> None:
        root_path = source_path or _source_path(root)
        identity_path = root_path
        unit_id = _id(part, root_path, "unit")
        self.limit(len(self.units) >= self.package.limits.max_units, "max_units")
        cached = self.cached_units.get(unit_id)
        if cached is not None:
            self.restore_unit(cached, unit_id, part, root_path)
            if self.checkpoint is not None:
                self.checkpoint(f"{part}:{root_path}:complete")
            return
        initial = {"sections": len(self.sections), "tables": len(self.tables), "warnings": len(self.warnings),
                   "revisions": len(self.metadata.get("revisions", [])), "blocks": self.block_count,
                   "cells": self.cell_count, "grid_cells": self.grid_cells, "text_chars": self.text_chars, "total": self.total,
                   "unsupported": self.unsupported}
        wrapper_keys = set(self.metadata.get("content_wrappers", {}))
        title = PART_TITLES[role] + (f" {note['id']}" if note is not None else "")
        unit: dict[str, Any] = {"id": unit_id, "kind": "docx_part", "part": part, "title": title,
                                "order_index": len(self.units), "parent_id": None, "metadata": {"role": role}, "blocks": []}
        if note is not None:
            unit["metadata"]["note"] = note
        saved_stack = self.section_stack
        self.section_stack = []
        if _word(root, "document"):
            body = _child(root, "body")
            if body is None:
                raise IngestionError("OFFICE_INVALID_DOCUMENT", "Le document DOCX ne contient pas de corps.")
            root = body
            root_path = _source_path(body)
        for element, path, revisions in self.source_items(root, part, root_path):
            source = self.paragraph(element, part, path) if _word(element, "p") else self.table(element, part, path)
            if revisions:
                source["structure"].setdefault("revisions", []).extend(revisions)
            self.add_block(unit, source)
            for textbox in source["structure"].get("textboxes", []):
                self.source_block()
                self.add_block(unit, {"id": _id(part, textbox["element_path"]), "kind": "textbox", "text": textbox["text"],
                                      "element_path": textbox["element_path"], "section_id": source.get("section_id"),
                                      "structure": {"source_anchor_block_id": source["id"], "placement": "source_anchor",
                                                    "contents": textbox["contents"], "text_is_derived": True}})
        self.units.append(unit)
        self.section_stack = saved_stack
        if self.unit_sink is not None:
            fragment = {"schema": 1, "sha256": self.package.sha256, "limits": asdict(self.package.limits),
                        "part": part, "source_path": identity_path,
                        "sections": self.sections[initial["sections"]:], "tables": self.tables[initial["tables"]:],
                        "warnings": self.warnings[initial["warnings"]:],
                        "revisions": self.metadata.get("revisions", [])[initial["revisions"]:],
                        "content_wrappers": {key: value for key, value in self.metadata.get("content_wrappers", {}).items()
                                             if key not in wrapper_keys},
                        "numbering_state": self.counters,
                        "counts": {"blocks": self.block_count - initial["blocks"], "cells": self.cell_count - initial["cells"],
                                   "grid_cells": self.grid_cells - initial["grid_cells"],
                                   "text_chars": self.text_chars - initial["text_chars"], "total": self.total - initial["total"],
                                   "unsupported": self.unsupported - initial["unsupported"]}}
            self.unit_sink(deepcopy({**unit, "_resume": fragment}))
        if self.checkpoint is not None:
            self.checkpoint(f"{part}:{identity_path}:complete")

    def restore_unit(self, cached: dict[str, Any], unit_id: str, part: str, path: str) -> None:
        fragment = cached.get("_resume")
        if (not isinstance(fragment, dict) or fragment.get("schema") != 1 or fragment.get("sha256") != self.package.sha256
                or fragment.get("limits") != asdict(self.package.limits) or fragment.get("part") != part
                or fragment.get("source_path") != path or cached.get("id") != unit_id
                or cached.get("part") != part or cached.get("order_index") != len(self.units)):
            raise IngestionError("OFFICE_INVALID_CHECKPOINT", "Le checkpoint DOCX ne correspond pas à cette unité source.")
        counts = fragment.get("counts")
        keys = {"blocks", "cells", "grid_cells", "text_chars", "total", "unsupported"}
        if (not isinstance(counts, dict) or set(counts) != keys
                or any(type(value) is not int or value < 0 for value in counts.values())
                or counts["total"] != len(cached.get("blocks", []))):
            raise IngestionError("OFFICE_INVALID_CHECKPOINT", "Les compteurs du checkpoint DOCX sont invalides.")
        for key in ("sections", "tables", "warnings", "revisions"):
            if not isinstance(fragment.get(key), list):
                raise IngestionError("OFFICE_INVALID_CHECKPOINT", "Le fragment du checkpoint DOCX est incomplet.")
        if not isinstance(fragment.get("content_wrappers"), dict):
            raise IngestionError("OFFICE_INVALID_CHECKPOINT", "Les métadonnées du checkpoint DOCX sont incomplètes.")
        state = fragment.get("numbering_state")
        if (not isinstance(state, dict) or any(not isinstance(levels, dict) for levels in state.values())
                or any(type(value) is not int for levels in state.values() for value in levels.values())
                or any(not re.fullmatch(r"[0-8]", str(level)) for levels in state.values() for level in levels)):
            raise IngestionError("OFFICE_INVALID_CHECKPOINT", "L'état de numérotation du checkpoint DOCX est invalide.")
        self.block_count += counts["blocks"]
        self.cell_count += counts["cells"]
        self.grid_cells += counts["grid_cells"]
        self.text_chars += counts["text_chars"]
        self.limit(self.block_count > self.package.limits.max_blocks, "max_blocks")
        self.limit(self.cell_count > self.package.limits.max_cells, "max_cells")
        self.limit(self.grid_cells > self.package.limits.max_cells, "max_cells")
        self.limit(self.text_chars > self.package.limits.max_text_chars, "max_text_chars")
        self.total += counts["total"]
        self.unsupported += counts["unsupported"]
        self.sections.extend(deepcopy(fragment["sections"]))
        self.tables.extend(deepcopy(fragment["tables"]))
        self.warnings.extend(deepcopy(fragment["warnings"]))
        self._seen_warnings.update((warning["code"], warning["part"], warning["element_path"]) for warning in fragment["warnings"])
        if fragment["revisions"]:
            self.metadata.setdefault("revisions", []).extend(deepcopy(fragment["revisions"]))
        if fragment["content_wrappers"]:
            self.metadata.setdefault("content_wrappers", {}).update(deepcopy(fragment["content_wrappers"]))
        # JSON checkpoints encode mapping keys as strings.
        self.counters = {identity: {int(level): value for level, value in levels.items()} for identity, levels in state.items()}
        self.units.append(deepcopy({key: value for key, value in cached.items() if key != "_resume"}))

    def read_metadata(self) -> None:
        for rel in self.package.relations(""):
            kind = rel["type"].rsplit("/", 1)[-1]
            if kind == "metadata/core-properties":
                kind = "core-properties"
            if rel["external"] or kind not in {"core-properties", "extended-properties", "custom-properties"}:
                continue
            root = self.xml(rel["target"])
            values = []
            for position, node in enumerate(root, 1):
                values.append({"name": _attr(node, "name") or _local(node), "namespace": _namespace(node),
                               "type": _local(node[0]) if len(node) else None,
                               "value": "".join(node.itertext()), "part": rel["target"], "ordinal": position,
                               "attributes": dict(node.attrib)})
            self.metadata[kind] = values

    def resolve_references(self) -> None:
        targets: dict[tuple[str, str], list[str]] = {}
        for unit in self.units:
            note = unit["metadata"].get("note")
            if note is not None:
                targets.setdefault((unit["part"], str(note["id"])), []).append(unit["id"])

        def visit(value: Any, part: str) -> None:
            if isinstance(value, list):
                for item in value:
                    visit(item, part)
            elif isinstance(value, dict):
                for reference in value.get("references", []):
                    target = targets.get((reference.get("target_part"), str(reference.get("id"))), [])
                    reference["target_unit_id"] = target[0] if len(target) == 1 else None
                    if len(target) != 1:
                        self.warning("DOCX_REFERENCE_UNRESOLVED", "Une référence de note ou commentaire n'a pas de cible unique.",
                                     part, reference["element_path"])
                for key, item in value.items():
                    if key != "references":
                        visit(item, part)

        for unit in self.units:
            for block in unit["blocks"]:
                visit(block["structure"], unit["part"])

    def run(self) -> dict[str, Any]:
        if self.package.format != "docx":
            raise IngestionError("OFFICE_FORMAT_MISMATCH", "L'adaptateur DOCX a reçu un autre format.")
        self.load_styles()
        self.load_numbering()
        self.read_metadata()
        root = self.xml(self.package.main_part)
        if not _word(root, "document"):
            raise IngestionError("OFFICE_INVALID_DOCUMENT", "La partie principale n'est pas un document WordprocessingML.")
        self.metadata["ooxml_family"] = "strict" if _namespace(root).startswith("http://purl.oclc.org") else "transitional"
        self.metadata["relations"] = self.package.relations(self.package.main_part)
        self.metadata["sections"] = [{"element_path": path,
                                      "references": [{"kind": _local(child), "variant": _attr(child, "type", WORD_NAMESPACES),
                                                      "relationship_id": _attr(child, "id", REL_NAMESPACES)}
                                                     for child in section if _local(child) in {"headerReference", "footerReference"}]}
                                     for section, path in _walk_paths(root, _source_path(root)) if _word(section, "sectPr")]
        self.read_part(self.package.main_part, "document", root)
        seen: set[str] = {self.package.main_part}
        for relation in self.relations(self.package.main_part).values():
            role = relation["type"].rsplit("/", 1)[-1]
            if role not in {"header", "footer", "footnotes", "endnotes", "comments"} or relation["external"]:
                continue
            part = relation["target"]
            if part in seen:
                continue
            seen.add(part)
            auxiliary = self.xml(part)
            expected_root = {"header": "hdr", "footer": "ftr"}.get(role, role)
            if not _word(auxiliary, expected_root):
                raise IngestionError("OFFICE_INVALID_DOCUMENT", "Une partie DOCX ne correspond pas à son rôle déclaré.")
            if role in {"footnotes", "endnotes", "comments"}:
                note_ids: set[str] = set()
                for position, note in enumerate(auxiliary, 1):
                    expected_note = {"footnotes": "footnote", "endnotes": "endnote", "comments": "comment"}[role]
                    if not _word(note, expected_note):
                        self.warning("DOCX_NOTE_ELEMENT_UNSUPPORTED", "Un élément de partie de notes n'est pas interprété.", part, _source_path(note))
                        continue
                    identity = _attr(note, "id", WORD_NAMESPACES)
                    # Separators are structural notes; keep their role without indexing them as prose.
                    metadata = {"id": identity, "type": _attr(note, "type", WORD_NAMESPACES),
                                "author": _attr(note, "author", WORD_NAMESPACES), "date": _attr(note, "date", WORD_NAMESPACES),
                                "source_ordinal": position}
                    if identity is None:
                        self.warning("DOCX_NOTE_ID_MISSING", "Une note ou un commentaire n'a pas d'identifiant source.", part,
                                     f"/{role}[1]/{_local(note)}[{position}]")
                        metadata["id"] = f"ordinal-{position}"
                    elif identity in note_ids:
                        self.warning("DOCX_NOTE_ID_DUPLICATE", "Une référence de note est ambiguë car son identifiant est défini plusieurs fois.", part, _source_path(note))
                    else:
                        note_ids.add(identity)
                    if metadata["type"] in {"separator", "continuationSeparator", "continuationNotice"}:
                        self.metadata.setdefault("note_separators", []).append({"part": part, **metadata})
                        continue
                    self.read_part(part, role, note, note=metadata,
                                   source_path=f"/{_local(auxiliary)}[1]/{_local(note)}[{position}]")
            else:
                self.read_part(part, role, auxiliary)
        self.resolve_references()
        return {"units": self.units, "sections": self.sections, "tables": self.tables, "metadata": self.metadata,
                "warnings": self.warnings, "coverage": {"total": self.total, "processed": self.total,
                                                       "unsupported": self.unsupported},
                "status": "ready_partial" if self.unsupported else "ready", "parser_complete": True}


def parse_docx(package: OfficePackage, *, checkpoint: Callable[[str], None] | None = None,
               unit_sink: Callable[[dict[str, Any]], None] | None = None,
               cached_units: Mapping[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Extract a validated immutable package; callbacks may stop at source units."""
    return _DocxReader(package, checkpoint, unit_sink, cached_units).run()
