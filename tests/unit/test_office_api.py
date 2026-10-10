"""Office HTTP contracts over real OOXML parsing and SQLite persistence.

TestClient runs the real FastAPI handlers and Indexer. FakeEmbedding,
FakeVectors and SilentOllama explicitly replace model/server boundaries;
these tests establish API contracts, not a native RAG runtime qualification.
"""

import asyncio
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_api_contract import SilentOllama
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors
from test_office_docx import R, package_file, paragraph

from services.api.main import create_app
from services.api.settings import Settings
from services.ingestion.office.models import OFFICE_MIME
from services.ingestion.office.pipeline import extract_office
from tests.fixtures.office.xlsx_cases import write_workbook

ORIGIN = "http://127.0.0.1:8785"
PREFIX = "/api/v1"


@pytest.fixture
def office_api(tmp_path, monkeypatch):
    nonce = "office-tests-isolated-control-nonce"
    monkeypatch.setenv("RAG_CONTROL_TOKEN", nonce)
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785},
                                  "chunking": {"overlap_max_tokens": 0}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(),
                     tokenizer=FakeLlmTokenizer(), ollama=SilentOllama(),
                     governor=SimpleNamespace(), start_jobs=False)
    with TestClient(app, base_url=ORIGIN, headers={"X-RAG-Control-Token": nonce}) as client:
        yield app, client


def upload(client, payload, name, mime="application/octet-stream"):
    response = client.post(PREFIX + "/documents/import", files=[("files", (name, payload, mime))])
    assert response.status_code == 202, response.text
    return response.json()["imports"][0]


def index_import(app, imported):
    database = app.state.db
    version = database.version(imported["version_id"])
    output = app.state.settings.data_dir / "qa-extractions" / imported["job_id"]
    extraction = extract_office(version["blob_path"], output, app.state.settings.profile,
                                version["id"], version["format"])
    generation_id = asyncio.run(app.state.indexer.index(imported["job_id"], extraction, output / "extraction.json"))
    if extraction["status"] == "ready_partial":
        generation = database.one("SELECT * FROM index_generations WHERE id=?", (generation_id,))
        assert generation["published_at"] is None
        app.state.indexer.publish(imported["job_id"], generation_id, generation["actual_chunks"],
                                  partial=True, allow_partial=True)
    return extraction, generation_id


def docx_bytes(tmp_path, text="Tension nominale : 72 V.", *, images=False, image_data=None):
    body = paragraph("Énergie", '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>') + paragraph(text) + paragraph("Fin")
    parts, relations = {}, []
    raster = None
    if images:
        stream = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(stream, "PNG")
        raster = stream.getvalue() if image_data is None else image_data
        parts = {"word/media/chart.png": raster, "word/media/unregistered.png": raster + b"unregistered"}
        relations = [("image1", R + "/image", "media/chart.png", False)]
        body += '<w:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:r><w:drawing><wp:inline><wp:extent cx="19050" cy="19050"/><wp:docPr id="1" name="Chart" descr="Carré rouge"/><a:graphic><a:graphicData><a:blip r:embed="image1"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    return package_file(tmp_path, body, parts=parts, relations=relations).read_bytes(), raster


def test_mixed_import_exposes_format_correct_mime_and_identical_original(office_api, tmp_path):
    app, client = office_api
    word, _ = docx_bytes(tmp_path)
    excel = write_workbook(tmp_path / "budget.xlsx").read_bytes()
    payloads = {"manual.pdf": b"%PDF-1.7\nreal signature fixture", "report.docx": word, "budget.xlsx": excel}
    response = client.post(PREFIX + "/documents/import", files=[("files", (name, data, "application/octet-stream"))
                                                                  for name, data in payloads.items()])
    assert response.status_code == 202, response.text
    imports = response.json()["imports"]
    assert len(imports) == 3
    for imported, (name, original) in zip(imports, payloads.items(), strict=True):
        document_format = name.rsplit(".", 1)[1]
        version = app.state.db.version(imported["version_id"])
        assert version["format"] == document_format
        assert version["sha256"] == hashlib.sha256(original).hexdigest()
        file = client.get(f"{PREFIX}/versions/{version['id']}/file")
        assert file.status_code == 200 and file.content == original
        assert file.headers["content-type"] == ("application/pdf" if document_format == "pdf" else OFFICE_MIME[document_format])
        assert file.headers["x-content-type-options"] == "nosniff"
        assert ("attachment" if document_format != "pdf" else "inline") in file.headers["content-disposition"]
        assert client.get(f"{PREFIX}/versions/{version['id']}/file", headers={"If-None-Match": file.headers["etag"]}).status_code == 304
    documents = client.get(PREFIX + "/library/tree").json()["documents"]
    assert {row["format"] for row in documents} == {"pdf", "docx", "xlsx"}
    repeat = upload(client, word, "report.docx")
    assert repeat["reused"] and repeat["version_id"] == imports[1]["version_id"]
    assert app.state.db.one("SELECT count(*) n FROM document_versions")["n"] == 3
    assert not list((app.state.settings.data_dir / "uploads").iterdir())


@pytest.mark.parametrize("case", ["xlsx_as_docx", "docx_as_xlsx", "pdf_as_docx", "truncated_xlsx", "invalid_pdf"])
def test_counterfeit_extension_and_corruption_leave_no_registered_or_temporary_original(office_api, tmp_path, case):
    app, client = office_api
    if case == "xlsx_as_docx":
        payload, name = write_workbook(tmp_path / "test.xlsx").read_bytes(), "false.docx"
    elif case == "docx_as_xlsx":
        payload, name = docx_bytes(tmp_path)[0], "false.xlsx"
    elif case == "pdf_as_docx":
        payload, name = b"%PDF-1.7\n", "false.docx"
    elif case == "truncated_xlsx":
        payload, name = b"PK\x03\x04broken", "broken.xlsx"
    else:
        payload, name = b"not a PDF", "false.pdf"
    response = client.post(PREFIX + "/documents/import", files=[("files", (name, payload, OFFICE_MIME["docx"]))])
    assert response.status_code == 400, response.text
    assert response.json()["code"] in {"office_format_mismatch", "office_invalid_package", "invalid_pdf"}
    assert app.state.db.one("SELECT count(*) n FROM document_versions")["n"] == 0
    assert not list((app.state.settings.data_dir / "originals").iterdir())
    assert not list((app.state.settings.data_dir / "uploads").iterdir())


@pytest.mark.parametrize("rejected", ["corrupt", "unsafe_path"])
def test_mixed_batch_continues_after_one_rejected_file_without_orphaned_data(office_api, tmp_path, rejected):
    app, client = office_api
    excel = write_workbook(tmp_path / "budget.xlsx").read_bytes()
    middle = b"PK\x03\x04corrupt" if rejected == "corrupt" else docx_bytes(tmp_path)[0]
    bad_path = "rejected.docx" if rejected == "corrupt" else "../rejected.docx"
    response = client.post(PREFIX + "/documents/import", files=[
        ("files", ("first.pdf", b"%PDF-1.7\nfirst document", "application/pdf")),
        ("files", ("middle.docx", middle, OFFICE_MIME["docx"])),
        ("files", ("last.xlsx", excel, OFFICE_MIME["xlsx"]))],
        data={"relative_paths": json.dumps(["accepted/first.pdf", bad_path, "accepted/last.xlsx"])})
    assert response.status_code == 202, response.text
    body = response.json()
    assert len(body["imports"]) == 2 and len(body["errors"]) == 1
    assert body["errors"][0]["relative_path"] == bad_path
    assert body["errors"][0]["code"] == ("office_invalid_package" if rejected == "corrupt" else "invalid_path")
    assert body["errors"][0]["message"]
    database = app.state.db
    assert [row["relative_path"] for row in database.rows("SELECT relative_path FROM documents ORDER BY relative_path")] == ["accepted/first.pdf", "accepted/last.xlsx"]
    assert database.one("SELECT count(*) n FROM document_versions")["n"] == 2
    assert database.one("SELECT count(*) n FROM jobs")["n"] == 2
    originals = list((app.state.settings.data_dir / "originals").iterdir())
    assert len(originals) == 2 and {path.suffix for path in originals} == {".pdf", ".xlsx"}
    assert not list((app.state.settings.data_dir / "uploads").iterdir())


def test_docx_reader_pagination_anchor_outline_and_revision_mismatch(office_api, tmp_path):
    app, client = office_api
    imported = upload(client, docx_bytes(tmp_path)[0], "report.docx")
    extraction, generation = index_import(app, imported)
    revision = extraction["extraction_revision_id"]
    base = f"{PREFIX}/versions/{imported['version_id']}"
    representation = client.get(base + "/representation", params={"extraction_revision_id": revision, "limit": 1}).json()
    assert representation["format"] == "docx" and representation["generation_id"] == generation
    assert representation["extraction_revision_id"] == revision
    assert representation["total"] == len(extraction["units"])
    unit = representation["units"][0]
    assert "blocks" not in unit and "cells" not in unit
    endpoint = base + f"/units/{unit['id']}/blocks"
    first = client.get(endpoint, params={"extraction_revision_id": revision, "limit": 1}).json()
    assert len(first["blocks"]) == 1 and first["next_cursor"] == 1
    second = client.get(endpoint, params={"extraction_revision_id": revision, "cursor": first["next_cursor"], "limit": 1}).json()
    assert second["blocks"][0]["text"] == "Tension nominale : 72 V."
    anchor = client.get(endpoint, params={"extraction_revision_id": revision, "block_id": second["blocks"][0]["id"], "limit": 1}).json()
    assert anchor["cursor"] == 1 and anchor["blocks"] == second["blocks"]
    block = anchor["blocks"][0]
    assert block["page_index"] is None and block["bbox"] is None
    assert block["precision"] == "element" and block["locator"]["kind"] == "docx_element"
    assert block["source_text_hash"] == hashlib.sha256(block["source_text"].encode()).hexdigest()
    outline = client.get(base + "/outline", params={"extraction_revision_id": revision}).json()
    assert outline["sections"][0]["title"] == "Énergie"
    assert outline["sections"][0]["id"] == extraction["sections"][0]["id"]
    assert client.get(endpoint, params={"block_id": "/document[1]/body[1]/p[2]"}).status_code == 404
    mismatch = client.get(base + "/representation", params={"extraction_revision_id": "another-revision"})
    assert mismatch.status_code == 404 and mismatch.json()["code"] == "extraction_revision_not_found"
    assert client.get(base + "/pages/0/blocks").status_code == 404


def test_xlsx_reader_sparse_windows_exact_types_formulas_and_hidden_sheet(office_api, tmp_path):
    app, client = office_api
    imported = upload(client, write_workbook(tmp_path / "budget.xlsx").read_bytes(), "budget.xlsx")
    extraction, _ = index_import(app, imported)
    revision = extraction["extraction_revision_id"]
    base = f"{PREFIX}/versions/{imported['version_id']}"
    first = client.get(base + "/representation", params={"limit": 1, "extraction_revision_id": revision}).json()
    second = client.get(base + "/representation", params={"cursor": first["next_cursor"], "limit": 1,
                                                         "extraction_revision_id": revision}).json()
    assert first["total"] == 2 and second["next_cursor"] is None
    assert second["units"][0]["metadata"]["visibility"] == "veryHidden"
    endpoint = base + f"/sheets/{first['units'][0]['id']}/cells"
    window = client.get(endpoint, params={"extraction_revision_id": revision, "row_start": 2, "row_end": 4,
                                          "column_start": 2, "column_end": 3}).json()
    cells = {cell["address"]: cell for cell in window["cells"]}
    assert set(cells) == {"B2", "C2", "B3", "C3", "B4", "C4"}
    assert cells["B2"]["raw_value"] == "9007199254740993"
    assert cells["B2"]["value"]["value"] == "9007199254740993"
    assert cells["C4"]["formula"]["raw_text"] == "SUM(B2:B3)"
    assert cells["C4"]["cached_value"]["value"] == "1"
    assert cells["C4"]["cache_freshness"] == "unknown"
    assert cells["C3"]["cached_present"] is False
    assert cells["B3"]["raw_value"] == "0"
    assert cells["B4"]["value"]["kind"] == "error"
    empty = client.get(endpoint, params={"row_start": 100, "row_end": 105, "column_start": 1, "column_end": 3}).json()
    assert empty["cells"] == []
    extreme = client.get(endpoint, params={"row_start": 1048576, "row_end": 1048576,
                                           "column_start": 16384, "column_end": 16384}).json()
    assert [cell["address"] for cell in extreme["cells"]] == ["XFD1048576"]


@pytest.mark.parametrize("suffix", ["representation?limit=101", "representation?cursor=-1", "representation?limit=0",
                                   "sheets/missing/cells?row_start=0", "sheets/missing/cells?column_end=16385",
                                   "sheets/missing/cells?row_start=10&row_end=1", "sheets/missing/cells?row_end=10001&column_end=1"])
def test_office_reader_enforces_bounds_before_loading_a_window(office_api, tmp_path, suffix):
    app, client = office_api
    imported = upload(client, write_workbook(tmp_path / "budget.xlsx").read_bytes(), "budget.xlsx")
    index_import(app, imported)
    response = client.get(f"{PREFIX}/versions/{imported['version_id']}/" + suffix)
    assert response.status_code in {400, 413}, response.text
    assert response.json()["code"] in {"invalid_pagination", "invalid_cell_range", "office_window_too_large"}


def test_archived_office_revision_remains_exact_and_deleted_document_is_refused(office_api, tmp_path):
    app, client = office_api
    old = upload(client, docx_bytes(tmp_path, "Ancienne tension : 72 V.")[0], "report.docx")
    old_extraction, old_generation = index_import(app, old)
    changed = upload(client, docx_bytes(tmp_path, "Nouvelle tension : 110 V.")[0], "report.docx")
    new_extraction, new_generation = index_import(app, changed)
    assert old["document_id"] == changed["document_id"] and old["version_id"] != changed["version_id"]
    assert app.state.db.one("SELECT active_generation_id FROM documents")["active_generation_id"] == new_generation
    old_base = f"{PREFIX}/versions/{old['version_id']}"
    result = client.get(old_base + "/representation", params={"extraction_revision_id": old_extraction["extraction_revision_id"]}).json()
    assert result["generation_id"] == old_generation
    texts = client.get(old_base + f"/units/{result['units'][0]['id']}/blocks",
                       params={"extraction_revision_id": old_extraction["extraction_revision_id"]}).json()["blocks"]
    assert "Ancienne tension : 72 V." in [block["text"] for block in texts]
    assert "Nouvelle tension : 110 V." not in [block["text"] for block in texts]
    assert client.get(old_base + "/representation", params={"extraction_revision_id": new_extraction["extraction_revision_id"]}).status_code == 404
    assert client.delete(f"{PREFIX}/documents/{old['document_id']}").status_code == 200
    for path in (old_base + "/representation", old_base + "/file",
                 old_base + f"/units/{result['units'][0]['id']}/blocks"):
        response = client.get(path, params={"extraction_revision_id": old_extraction["extraction_revision_id"]})
        assert response.status_code == 404 and response.json()["code"] == "source_removed"


def test_same_version_parser_revision_is_pinned_independently_from_latest_generation(office_api, tmp_path):
    app, client = office_api
    imported = upload(client, docx_bytes(tmp_path)[0], "revision.docx")
    first, first_generation = index_import(app, imported)
    # A parser option changes its identity without changing this bounded source
    # document. Both immutable extraction revisions share one original version.
    app.state.settings.profile["office"] = {"max_blocks": 99_999}
    scheduled = client.post(f"{PREFIX}/documents/{imported['document_id']}/reindex")
    assert scheduled.status_code == 202
    second, second_generation = index_import(app, {**imported, **scheduled.json()})
    assert first["source_hash"] == second["source_hash"]
    assert first["extraction_revision_id"] != second["extraction_revision_id"]
    assert first_generation != second_generation
    base = f"{PREFIX}/versions/{imported['version_id']}"
    assert client.get(base + "/representation").json()["generation_id"] == second_generation
    for extraction, generation in ((first, first_generation), (second, second_generation)):
        revision = extraction["extraction_revision_id"]
        result = client.get(base + "/representation", params={"extraction_revision_id": revision}).json()
        assert result["generation_id"] == generation and result["extraction_revision_id"] == revision
        blocks = client.get(base + f"/units/{result['units'][0]['id']}/blocks",
                            params={"extraction_revision_id": revision}).json()["blocks"]
        assert [block["text"] for block in blocks] == [block["text"] for block in extraction["units"][0]["blocks"]]
        assert {block["extraction_revision_id"] for block in blocks} == {revision}


def test_registered_docx_raster_is_served_without_arbitrary_part_access(office_api, tmp_path):
    app, client = office_api
    payload, raster = docx_bytes(tmp_path, images=True)
    imported = upload(client, payload, "images.docx")
    extraction, _ = index_import(app, imported)
    base = f"{PREFIX}/versions/{imported['version_id']}/assets/"
    response = client.get(base + hashlib.sha256(raster).hexdigest(),
                          params={"extraction_revision_id": extraction["extraction_revision_id"]})
    assert response.status_code == 200 and response.content == raster
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(base + hashlib.sha256(raster + b"unregistered").hexdigest()).status_code == 404
    assert client.get(base + "not-a-source-asset").status_code == 404
    assert client.get(base + hashlib.sha256(raster).hexdigest(), params={"extraction_revision_id": "wrong"}).status_code == 404


def test_registered_active_content_disguised_as_png_is_never_rendered(office_api, tmp_path):
    app, client = office_api
    active_content = b'<svg xmlns="http://www.w3.org/2000/svg"><script>private-active-content</script></svg>'
    payload, _ = docx_bytes(tmp_path, images=True, image_data=active_content)
    imported = upload(client, payload, "untrusted-image.docx")
    extraction, _ = index_import(app, imported)
    response = client.get(f"{PREFIX}/versions/{imported['version_id']}/assets/{hashlib.sha256(active_content).hexdigest()}",
                          params={"extraction_revision_id": extraction["extraction_revision_id"]})
    assert response.status_code == 409 and response.json()["code"] == "asset_not_available"
    assert "private-active-content" not in response.text


def test_office_routes_require_session_and_revoke_it_after_logout(office_api, tmp_path):
    app, client = office_api
    imported = upload(client, docx_bytes(tmp_path)[0], "session.docx")
    extraction, _ = index_import(app, imported)
    base = f"{PREFIX}/versions/{imported['version_id']}"
    client.headers.pop("X-RAG-Control-Token")
    for endpoint in ("/representation", "/file", f"/units/{extraction['units'][0]['id']}/blocks"):
        response = client.get(base + endpoint)
        assert response.status_code == 401 and response.json()["code"] == "session_required"
    # The normal one-use browser link and cookies, with server-side revocation.
    link = app.state.sessions.issue_link()
    opened = client.get(PREFIX + "/session/open", params={"link": link}, follow_redirects=False)
    assert opened.status_code == 303
    assert client.get(base + "/representation").status_code == 200
    forbidden = client.delete(f"{PREFIX}/documents/{imported['document_id']}")
    assert forbidden.status_code == 403 and forbidden.json()["code"] == "csrf_rejected"
    saved_cookie = client.cookies.get("rag_session")
    csrf = client.cookies.get("rag_csrf")
    assert client.post(PREFIX + "/session/logout", headers={"X-CSRF-Token": csrf}).json()["revoked"] is True
    client.cookies.set("rag_session", saved_cookie)
    rejected = client.get(base + "/representation")
    assert rejected.status_code == 401 and rejected.json()["code"] == "session_expired"
