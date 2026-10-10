"""Read-only OPC packages, verified before any Office library sees their XML.

No member is extracted to disk. DTD/entities are rejected with defusedxml,
including UTF-16 documents; lxml only receives preflighted, bounded XML.
"""

import hashlib
import posixpath
import re
import stat
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from lxml import etree

from services.ingestion.errors import IngestionError

from .models import OFFICE_MIME, OfficeLimits, limit_error

CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml": "xlsx",
}


def _invalid():
    return IngestionError("OFFICE_INVALID_PACKAGE", "Le conteneur Office est invalide, corrompu ou non pris en charge.")


def _name_safe(name):
    return bool(name and not name.startswith("/") and "\\" not in name
                and not re.search(r"[\x00-\x1f:]", name)
                and all(part not in {"", ".", ".."} for part in name.rstrip("/").split("/")))


class OfficePackage:
    def __init__(self, path, expected_format=None, limits=None):
        self.path = Path(path)
        self.limits = limits or OfficeLimits()
        self._archive = None
        self._validated_xml = set()
        self._xml_elements = 0
        self._types: dict[str, str] = {}
        self._defaults: dict[str, str] = {}
        try:
            if self.path.stat().st_size > self.limits.max_total_bytes:
                raise limit_error()
            # Hash the same immutable original passed to the worker, without loading it.
            with self.path.open("rb") as source:
                self.sha256 = hashlib.file_digest(source, "sha256").hexdigest()
            self._archive = ZipFile(self.path, "r")
            entries = self._archive.infolist()
            if len(entries) > self.limits.max_members:
                raise limit_error()
            canonical = set()
            total = 0
            for member in entries:
                name = member.filename
                key = unicodedata.normalize("NFC", name).casefold()
                if not _name_safe(name) or key in canonical or stat.S_ISLNK(member.external_attr >> 16):
                    raise _invalid()
                canonical.add(key)
                if member.flag_bits & 1 or member.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
                    raise _invalid()
                total += member.file_size
                if (member.file_size > self.limits.max_part_bytes or total > self.limits.max_total_bytes
                        or member.file_size > max(1, member.compress_size) * self.limits.max_compression_ratio):
                    raise limit_error()
            self.names = tuple(member.filename for member in entries if not member.is_dir())
            self._names = frozenset(self.names)
            if "[Content_Types].xml" not in self.names or "_rels/.rels" not in self.names:
                raise _invalid()
            # Consume every member to EOF: ZipFile checks CRC, header names and overlaps.
            # XML is streamed and cleared rather than materialised during security validation.
            for name in self.names:
                if name.lower().endswith((".xml", ".rels")):
                    self._ensure_xml(name)
                else:
                    with self.open(name) as stream:
                        while stream.read(65_536):
                            pass
            types = self.xml("[Content_Types].xml")
            if types.tag != f"{{{CONTENT_NS}}}Types":
                raise _invalid()
            for item in types:
                if not isinstance(item.tag, str):
                    continue
                content_type = item.get("ContentType", "")
                if "macroEnabled" in content_type or "vbaProject" in content_type:
                    raise IngestionError("OFFICE_MACROS_UNSUPPORTED", "Les documents Office contenant des macros sont refusés.")
                if item.tag == f"{{{CONTENT_NS}}}Override":
                    name = unquote(item.get("PartName", "")).lstrip("/")
                    if not _name_safe(name) or name not in self.names or name in self._types:
                        raise _invalid()
                    self._types[name] = content_type
                elif item.tag == f"{{{CONTENT_NS}}}Default":
                    extension = item.get("Extension", "").lower()
                    if not extension or extension in self._defaults:
                        raise _invalid()
                    self._defaults[extension] = content_type
            main = [rel for rel in self.relations("") if rel["type"].endswith("/officeDocument")]
            if len(main) != 1 or main[0]["external"]:
                raise _invalid()
            self.main_part = main[0]["target"]
            self.format = MAIN_TYPES.get(self.content_type(self.main_part))
            if self.format not in OFFICE_MIME or expected_format not in {None, self.format}:
                raise IngestionError("OFFICE_FORMAT_MISMATCH", "Le contenu Office ne correspond pas au format annoncé.")
            # A package XML part need not have an .xml extension. Content type
            # and every explicit XML read receive the same security validation.
            for name in self.names:
                if (self.content_type(name) or "").endswith(("+xml", "/xml")):
                    self._ensure_xml(name)
            # Validate all relationship targets, not only those read by an adapter.
            for name in self.names:
                if name.endswith(".rels") and name != "_rels/.rels":
                    parent, filename = posixpath.split(name)
                    if posixpath.basename(parent) != "_rels":
                        raise _invalid()
                    self.relations(posixpath.join(posixpath.dirname(parent), filename[:-5]))
        except IngestionError:
            self.close()
            raise
        except (OSError, ValueError, KeyError, BadZipFile, RuntimeError, SafeET.ParseError,
                DefusedXmlException, etree.XMLSyntaxError) as error:
            self.close()
            raise _invalid() from error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self._archive is not None:
            self._archive.close()

    @contextmanager
    def open(self, name):
        if self._archive is None or name not in self._names:
            raise _invalid()
        with self._archive.open(name) as stream:
            yield stream

    def read(self, name):
        with self.open(name) as stream:
            value = stream.read(self.limits.max_part_bytes + 1)
        if len(value) > self.limits.max_part_bytes:
            raise limit_error()
        return value

    def xml(self, name):
        self._ensure_xml(name)
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                                 huge_tree=False, recover=False)
        return etree.fromstring(self.read(name), parser=parser)

    def iter_xml(self, name, events=("end",)):
        self._ensure_xml(name)
        with self.open(name) as stream:
            yield from etree.iterparse(stream, events=events, resolve_entities=False,
                                      load_dtd=False, no_network=True, huge_tree=False, recover=False)

    def _ensure_xml(self, name):
        if name in self._validated_xml:
            return
        stack = []
        try:
            with self.open(name) as stream:
                for event, element in SafeET.iterparse(stream, events=("start", "end"),
                                                      forbid_dtd=True, forbid_entities=True, forbid_external=True):
                    if event == "start":
                        stack.append(element)
                        self._xml_elements += 1
                        if len(stack) > self.limits.max_xml_depth or self._xml_elements > self.limits.max_elements:
                            raise limit_error()
                    else:
                        stack.pop()
                        element.clear()
                        if stack:
                            stack[-1].remove(element)
            self._validated_xml.add(name)
        except (SafeET.ParseError, DefusedXmlException, BadZipFile) as error:
            raise _invalid() from error

    def content_type(self, name):
        return self._types.get(name, self._defaults.get(posixpath.splitext(name)[1].lstrip(".").lower()))

    def relations(self, source_part):
        if not source_part:
            name = "_rels/.rels"
        else:
            parent, filename = posixpath.split(source_part)
            name = posixpath.join(parent, "_rels", filename + ".rels")
        if name not in self.names:
            return []
        root = self.xml(name)
        if root.tag != f"{{{REL_NS}}}Relationships":
            raise _invalid()
        ids, result = set(), []
        for item in root:
            if not isinstance(item.tag, str):
                continue
            identifier, relationship = item.get("Id"), item.get("Type", "")
            target, mode = item.get("Target", ""), item.get("TargetMode", "Internal")
            if (item.tag != f"{{{REL_NS}}}Relationship" or not identifier or identifier in ids
                    or not relationship or not target or mode not in {"Internal", "External"}):
                raise _invalid()
            ids.add(identifier)
            external = mode == "External"
            if not external:
                decoded = unquote(target)
                parsed = urlsplit(decoded)
                if parsed.scheme or parsed.netloc or "\\" in decoded or parsed.query:
                    raise _invalid()
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source_part), parsed.path))
                if decoded.startswith("/"):
                    resolved = parsed.path.lstrip("/")
                if not _name_safe(resolved) or resolved not in self.names:
                    raise _invalid()
                target = resolved
            result.append({"id": identifier, "type": relationship, "target": target, "external": external})
        return result
