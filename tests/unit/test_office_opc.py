"""Real OPC containers exercise the preflight before any Office adapter loads."""

import hashlib
from dataclasses import replace
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest
from pydantic import ValidationError

from services.api.schemas import Scope
from services.ingestion.errors import IngestionError
from services.ingestion.office.models import OfficeLimits
from services.ingestion.office.opc import OfficePackage

CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def package(path, *, main="word/document.xml", body=None, extra=(), relationship=None,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"):
    body = body or b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Texte source</w:t></w:r></w:p></w:body></w:document>'
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", f'<Types xmlns="{CONTENT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/{main}" ContentType="{content_type}"/></Types>')
        archive.writestr("_rels/.rels", f'<Relationships xmlns="{REL}"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{relationship or main}"/></Relationships>')
        archive.writestr(main, body)
        for name, data in extra:
            archive.writestr(name, data)
    return path


def test_verified_package_is_read_only_and_hashes_original(tmp_path):
    path = package(tmp_path / "source.docx")
    before = path.read_bytes()
    with OfficePackage(path, "docx") as source:
        assert source.format == "docx"
        assert source.main_part == "word/document.xml"
        assert source.sha256 == hashlib.sha256(before).hexdigest()
        assert source.xml(source.main_part).tag.endswith("}document")
        assert len(list(source.iter_xml(source.main_part))) == 5
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["source.docx"]


@pytest.mark.parametrize("name", ["../escape.bin", "/absolute.bin", "C:/drive.bin", "word\\evil.bin", "word/../evil.bin", "word//evil.bin", "WORD/DOCUMENT.XML"])
def test_unsafe_or_ambiguous_members_are_rejected(tmp_path, name):
    path = package(tmp_path / "source.docx", extra=[(name, b"payload")])
    with pytest.raises(IngestionError, match="conteneur") as error:
        OfficePackage(path)
    assert error.value.code == "OFFICE_INVALID_PACKAGE"


def test_duplicate_members_are_rejected(tmp_path):
    with pytest.warns(UserWarning):
        path = package(tmp_path / "source.docx", extra=[("word/document.xml", b"duplicate")])
    with pytest.raises(IngestionError):
        OfficePackage(path)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
@pytest.mark.parametrize("main", ["word/document.xml", "word/document.data"])
def test_dtd_entity_payload_is_rejected_even_in_utf16_and_non_xml_extension(tmp_path, encoding, main):
    payload = f'<?xml version="1.0" encoding="{encoding}"?><!DOCTYPE document [<!ENTITY stolen SYSTEM "file:///secret">]><document>&stolen;</document>'
    path = package(tmp_path / "hostile.docx", main=main, body=payload.encode(encoding))
    with pytest.raises(IngestionError) as error:
        OfficePackage(path)
    assert error.value.code == "OFFICE_INVALID_PACKAGE"


def test_corrupt_xml_and_truncated_zip_are_rejected(tmp_path):
    path = package(tmp_path / "source.docx", body=b"<document>")
    with pytest.raises(IngestionError):
        OfficePackage(path)
    path.write_bytes(path.read_bytes()[:-80])
    with pytest.raises(IngestionError):
        OfficePackage(path)


def test_crc_failure_is_rejected(tmp_path):
    path = package(tmp_path / "source.docx")
    path.write_bytes(path.read_bytes().replace(b"Texte source", b"Texte change", 1))
    with pytest.raises(IngestionError):
        OfficePackage(path)


@pytest.mark.parametrize("changes", [{"max_members": 2}, {"max_total_bytes": 512, "max_part_bytes": 512},
                                     {"max_part_bytes": 20}, {"max_xml_depth": 3}, {"max_elements": 5}])
def test_resource_quotas_are_effective(tmp_path, changes):
    path = package(tmp_path / "source.docx")
    with pytest.raises(IngestionError) as error:
        OfficePackage(path, limits=replace(OfficeLimits(), **changes))
    assert error.value.code == "OFFICE_LIMIT_EXCEEDED"


def test_xml_budget_is_global_across_non_xml_extensions_and_not_recounted(tmp_path):
    path = package(tmp_path / "source.docx")
    with ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    types = parts["[Content_Types].xml"].decode().replace('</Types>', '<Default Extension="data" ContentType="application/xml"/></Types>')
    parts["[Content_Types].xml"] = types.encode()
    for name in ("annex1.data", "annex2.data"):
        parts[name] = ("<root>" + "<element/>" * 15 + "</root>").encode()
    with ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    with pytest.raises(IngestionError) as error:
        OfficePackage(path, limits=replace(OfficeLimits(), max_elements=25))
    assert error.value.code == "OFFICE_LIMIT_EXCEEDED"
    with OfficePackage(path, limits=replace(OfficeLimits(), max_elements=45)) as source:
        count = source._xml_elements
        for _ in range(3):
            assert source.xml("annex1.data").tag == "root"
            assert source.xml(source.main_part).tag.endswith("}document")
        assert source._xml_elements == count


def test_inert_comments_and_processing_instructions_in_relationships(tmp_path):
    path = package(tmp_path / "source.docx")
    with ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["_rels/.rels"] = parts["_rels/.rels"].replace(b"<Relationship Id", b"<!-- inert --><?qa safe?><Relationship Id")
    with ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    with OfficePackage(path) as source:
        assert source.relations("")[0]["target"] == source.main_part


def test_compression_bomb_and_symlink_are_rejected(tmp_path):
    path = package(tmp_path / "source.docx")
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("bomb.bin", b"0" * 100_000)
    with pytest.raises(IngestionError) as error:
        OfficePackage(path, limits=replace(OfficeLimits(), max_compression_ratio=10))
    assert error.value.code == "OFFICE_LIMIT_EXCEEDED"
    path = package(tmp_path / "link.docx")
    with ZipFile(path, "a") as archive:
        member = ZipInfo("link")
        member.create_system = 3
        member.external_attr = 0o120777 << 16
        archive.writestr(member, b"/secret")
    with pytest.raises(IngestionError):
        OfficePackage(path)


def test_external_relationship_is_data_and_never_followed(tmp_path):
    rels = f'<Relationships xmlns="{REL}"><Relationship Id="h1" Type="hyperlink" Target="https://example.invalid/private" TargetMode="External"/></Relationships>'
    path = package(tmp_path / "source.docx", extra=[("word/_rels/document.xml.rels", rels)])
    with OfficePackage(path) as source:
        assert source.relations(source.main_part) == [{"id": "h1", "type": "hyperlink", "target": "https://example.invalid/private", "external": True}]


@pytest.mark.parametrize("target", ["../../escape.xml", "https://example.invalid/content.xml", "missing.xml"])
def test_internal_relationship_cannot_escape_or_resolve_remote(tmp_path, target):
    path = package(tmp_path / "source.docx", relationship=target)
    with pytest.raises(IngestionError):
        OfficePackage(path)


def test_macro_content_and_wrong_format_are_rejected(tmp_path):
    path = package(tmp_path / "macro.docx", content_type="application/vnd.ms-word.document.macroEnabled.main+xml")
    with pytest.raises(IngestionError) as error:
        OfficePackage(path)
    assert error.value.code == "OFFICE_MACROS_UNSUPPORTED"
    path = package(tmp_path / "source.docx")
    with pytest.raises(IngestionError) as error:
        OfficePackage(path, "xlsx")
    assert error.value.code == "OFFICE_FORMAT_MISMATCH"


def test_office_scope_requires_pinned_revision_and_ordered_numeric_bounds():
    good = {"kind": "cell_range", "versionId": "version", "extractionRevisionId": "revision", "sheetId": "sheet",
            "rowStart": 1, "rowEnd": 50, "columnStart": 1, "columnEnd": 20}
    assert Scope(**good).rowEnd == 50
    for invalid in ({"rowStart": True}, {"rowEnd": 0}, {"rowStart": 60}, {"columnEnd": 16385},
                    {"extractionRevisionId": None}, {"sheetId": None}, {"versionId": None}):
        with pytest.raises(ValidationError):
            Scope(**{**good, **invalid})
