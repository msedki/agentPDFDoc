"""Real SQLite boundaries for scoped, immutable table-condition witnesses.

The source bytes and geometric observations are explicitly synthetic. Only the
embedding/vector transports and token counters use the existing storage doubles;
no native PDF/OCR engine or 4B response is claimed by these tests.
"""

import asyncio
import copy
import hashlib
import json
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest
from test_api_storage import storage as storage

from services.api import table_conditions
from services.api.db import json_dump, now, uid
from services.api.query import QueryService
from services.api.schemas import Scope
from services.api.scope import ScopeResolver
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.table_geometry import build_table_general_conditions

PAYLOAD = b"%PDF-1.7\nSynthetic scoped table-condition fixture, not a native PDF."
SOURCE_HASH = hashlib.sha256(PAYLOAD).hexdigest()
FROZEN_VERSION = "b219794c-5dc5-4dc0-af18-7e854ea18801"
FROZEN_REVISION = "84e92103-fce9-40ee-a076-cf07dc04666b"
CONDITION_TEXT = "TA = 18°C, supply = 4V unless otherwise noted."
HEADING_TEXT = "Electrical characteristics"
TABLE_TEXT = "Parameter | Min | Typ | Max | Units\nPulse | 5 | 8 | 11 | ms"


def synthetic_block(identity, text, bbox, kind="text"):
    return {"id": identity, "page_index": 0, "type": kind, "text": text,
            "raw_text": text, "bbox": bbox, "precision": "block",
            "source_text_hash": hashlib.sha256(text.encode()).hexdigest(),
            "version_id": FROZEN_VERSION, "extraction_revision_id": FROZEN_REVISION,
            "metadata": {"extraction_method": "native", "ocr_used": False}}


@dataclass
class ConditionWorkspace:
    db: object
    imported: dict
    extraction: dict
    resolver: ScopeResolver
    snapshot: object
    source: dict
    block: dict

    @property
    def generation(self):
        return self.source["generation_id"]

    def parent(self, block_id="table"):
        return self.db.one("SELECT * FROM blocks WHERE generation_id=? AND id=?",
                           (self.generation, block_id))

    def bundle(self, *, snapshot=None, source=None, block=None, parent=None):
        return table_conditions.table_conditions_bundle(
            self.db, self.snapshot if snapshot is None else snapshot,
            self.source if source is None else source,
            self.block if block is None else block,
            self.parent() if parent is None else parent)


def index_condition_fixture(storage, *, explicit_heading=True):
    settings, db, _, indexer = storage
    blob = settings.data_dir / "originals" / (SOURCE_HASH + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(PAYLOAD)
    imported = db.import_original("controlled-conditions.pdf", SOURCE_HASH, blob)
    heading = synthetic_block("heading", HEADING_TEXT, [20, 308, 250, 318],
                              "heading" if explicit_heading else "text")
    condition = synthetic_block("conditions", CONDITION_TEXT, [20, 290, 470, 302])
    table = synthetic_block("table", TABLE_TEXT, [20, 100, 480, 280], "table")
    blocks = [heading, condition, table]
    page = {"page_index": 0, "width": 500, "height": 400, "rotation": 0,
            "media_box": [0, 0, 500, 400], "crop_box": [0, 0, 500, 400],
            "effective_box": [0, 0, 500, 400], "source_sha256": SOURCE_HASH,
            "classification": "native", "blocks": blocks}
    table["metadata"]["table_general_conditions"] = build_table_general_conditions(
        table, blocks, page, source_sha256=SOURCE_HASH)
    # Page 1 is deliberately empty; it exists to exercise page isolation in DB.
    second_page = {**page, "page_index": 1, "blocks": []}
    extraction = {"sha256": SOURCE_HASH, "fingerprint": "i5-scoped-conditions-synthetic-v1",
                  "extraction_revision_id": FROZEN_REVISION, "status": "ready",
                  "page_count": 2, "pages": [page, second_page]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="pages", versionId=imported["version_id"],
                                      pageStart=0, pageEnd=0))
    sources = [resolver.source_for_chunk(chunk, snapshot)
               for chunk in db.rows("SELECT * FROM chunks ORDER BY chunk_uuid")]
    source = next(source for source in sources if source and any(
        block["id"] == "table" for block in source["blocks"]))
    block = next(block for block in source["blocks"] if block["id"] == "table")
    return ConditionWorkspace(db, imported, extraction, resolver, snapshot, source, block)


@pytest.fixture
def conditions(storage):
    return index_condition_fixture(storage)


def assert_unavailable(result, reason=None):
    fragments, annotation, warnings = result
    assert fragments == []
    assert annotation["state"] == "unavailable" and annotation["pieces"] == []
    assert len(warnings) == 1
    assert warnings[0]["code"] == "table_general_conditions_unavailable"
    if reason is not None:
        assert reason in annotation["reasons"] and warnings[0]["reason"] == reason
    assert CONDITION_TEXT not in json.dumps(warnings, ensure_ascii=False)


def selected_snapshot(workspace, bounds):
    spans = []
    for block_id, start, end in bounds:
        row = workspace.parent(block_id)
        spans.append({"extractionRevisionId": row["extraction_revision_id"],
                      "blockId": block_id, "blockTextSha256": row["source_text_hash"],
                      "offsetUnit": "unicode_code_point", "startOffset": start,
                      "endOffset": len(row["text"]) if end is None else end})
    return workspace.resolver.resolve(Scope(kind="selection", versionId=workspace.imported["version_id"],
                                            spans=spans))


def write_metadata(workspace, block_id, metadata):
    workspace.db.execute("UPDATE blocks SET metadata_json=? WHERE generation_id=? AND id=?",
                         (json_dump(metadata), workspace.generation, block_id))


def test_scoped_table_conditions_reconstruct_literal_fragments_from_sqlite(conditions):
    fragments, annotation, warnings = conditions.bundle()
    assert annotation["state"] == "supported" and warnings == []
    assert annotation["support_scope"] == "geometric_binding_only"
    assert annotation["source_sha256"] == SOURCE_HASH and annotation["page_index"] == 0
    assert [fragment["id"] for fragment in fragments] == ["heading", "conditions"]
    assert [fragment["text"] for fragment in fragments] == [HEADING_TEXT, CONDITION_TEXT]
    for fragment in fragments:
        row = conditions.parent(fragment["id"])
        assert fragment["text"] == row["text"][fragment["start_offset"]:fragment["end_offset"]]
        assert fragment["source_text_hash"] == hashlib.sha256(row["text"].encode()).hexdigest()
        assert fragment["extraction_revision_id"] == FROZEN_REVISION
        assert fragment["page_index"] == fragment["page"]["page_index"] == 0
        assert fragment["extraction_method"] == "native"


def test_complete_explicit_selection_preserves_conditions_without_scope_expansion(conditions):
    snapshot = selected_snapshot(conditions, [("table", 0, None), ("heading", 0, None),
                                               ("conditions", 0, None)])
    fragments, annotation, warnings = conditions.bundle(snapshot=snapshot)
    assert annotation["state"] == "supported" and warnings == []
    assert {fragment["id"] for fragment in fragments} <= set(snapshot.block_ids)
    assert {fragment["id"] for fragment in fragments} == {"heading", "conditions"}


@pytest.mark.parametrize("bounds", [
    [("table", 0, None)],
    [("table", 0, None), ("heading", 0, None)],
    [("table", 0, None), ("heading", 0, None), ("conditions", 0, 12)],
    [("table", 0, None), ("heading", 0, None), ("conditions", 1, None)],
])
def test_selection_cannot_recover_a_missing_or_clipped_condition(conditions, bounds):
    snapshot = selected_snapshot(conditions, bounds)
    assert_unavailable(conditions.bundle(snapshot=snapshot))


@pytest.mark.parametrize("gate", ["generation", "version", "document", "page", "block"])
def test_source_identity_and_table_scope_are_independent_gates(conditions, gate):
    source, block, snapshot = copy.deepcopy(conditions.source), copy.deepcopy(conditions.block), conditions.snapshot
    if gate == "generation":
        source["generation_id"] = "unregistered-generation"
    elif gate == "version":
        source["version_id"] = FROZEN_VERSION
    elif gate == "document":
        source["document_id"] = "unregistered-document"
    elif gate == "page":
        block["page_index"] = 1
    else:
        snapshot = replace(snapshot, block_ids=["heading", "conditions"])
    assert_unavailable(conditions.bundle(snapshot=snapshot, source=source, block=block),
                       "condition_scope_unavailable")


@pytest.mark.parametrize("boundary", ["source", "block", "parent"])
@pytest.mark.parametrize("revision", ["foreign-revision", None])
def test_revision_mismatch_or_missing_revision_cannot_authorize_a_condition(conditions, boundary, revision):
    values = {"source": copy.deepcopy(conditions.source), "block": copy.deepcopy(conditions.block),
              "parent": conditions.parent()}
    if revision is None:
        values[boundary].pop("extraction_revision_id")
    else:
        values[boundary]["extraction_revision_id"] = revision
    assert_unavailable(conditions.bundle(**values))


@pytest.mark.parametrize("mutation", ["text", "hash", "revision", "page"])
def test_stored_condition_text_hash_revision_and_page_are_rechecked(conditions, mutation):
    if mutation == "text":
        conditions.db.execute("UPDATE blocks SET text=? WHERE generation_id=? AND id='conditions'",
                              (CONDITION_TEXT.replace("4V", "7V"), conditions.generation))
    elif mutation == "hash":
        conditions.db.execute("UPDATE blocks SET source_text_hash=? WHERE generation_id=? AND id='conditions'",
                              ("0" * 64, conditions.generation))
    elif mutation == "revision":
        revision = uid()
        conditions.db.execute(
            "INSERT INTO extraction_revisions(id,version_id,fingerprint,source_hash,path,created_at) "
            "SELECT ?,version_id,fingerprint,source_hash,path,created_at FROM extraction_revisions WHERE id=?",
            (revision, FROZEN_REVISION))
        conditions.db.execute("UPDATE blocks SET extraction_revision_id=? WHERE generation_id=? AND id='conditions'",
                              (revision, conditions.generation))
    else:
        conditions.db.execute("UPDATE blocks SET page_index=1 WHERE generation_id=? AND id='conditions'",
                              (conditions.generation,))
    assert_unavailable(conditions.bundle())


@pytest.mark.parametrize("field,value", [("source_sha256", "0" * 64), ("page_index", 1)])
def test_page_geometry_cannot_be_rebound_to_a_different_source_or_page(conditions, field, value):
    row = conditions.db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=0",
                            (conditions.generation,))
    geometry = json.loads(row["geometry_json"])
    geometry[field] = value
    conditions.db.execute("UPDATE pages SET geometry_json=? WHERE generation_id=? AND page_index=0",
                          (json_dump(geometry), conditions.generation))
    assert_unavailable(conditions.bundle(), "condition_geometry_unavailable")


@pytest.mark.parametrize("mutation", ["source", "digest", "piece_text", "piece_hash", "piece_version", "piece_revision", "piece_box"])
def test_changed_stored_witness_is_not_an_authority(conditions, mutation):
    metadata = json.loads(conditions.parent()["metadata_json"])
    witness = metadata["metadata"]["table_general_conditions"]
    if mutation == "source":
        witness["source_sha256"] = "0" * 64
    elif mutation == "digest":
        witness["sha256"] = "0" * 64
    else:
        piece = witness["pieces"][1]
        field, value = {
            "piece_text": ("text", CONDITION_TEXT.replace("4V", "7V")),
            "piece_hash": ("source_text_hash", "0" * 64),
            "piece_version": ("version_id", conditions.imported["version_id"]),
            "piece_revision": ("extraction_revision_id", "foreign-revision"),
            "piece_box": ("bbox", [0, 0, 10, 10]),
        }[mutation]
        piece[field] = value
    write_metadata(conditions, "table", metadata)
    assert_unavailable(conditions.bundle(), "condition_witness_reconstruction_failed")


def test_old_extraction_without_annotation_does_not_claim_absence(conditions):
    metadata = json.loads(conditions.parent()["metadata_json"])
    del metadata["metadata"]["table_general_conditions"]
    write_metadata(conditions, "table", metadata)
    assert conditions.bundle() == ([], None, [])


def test_reconstructed_absent_band_does_not_invent_condition_fragments(storage):
    workspace = index_condition_fixture(storage, explicit_heading=False)
    assert workspace.bundle() == ([], None, [])


@pytest.mark.parametrize("limit", ["MAX_PAGE_BLOCKS", "MAX_PAGE_CHARS", "MAX_PAGE_METADATA_CHARS"])
def test_inspection_limits_stop_before_loading_block_contents(conditions, monkeypatch, limit):
    sizes = conditions.db.rows(
        "SELECT length(text) text_size,length(metadata_json) metadata_size FROM blocks WHERE generation_id=? AND page_index=0",
        (conditions.generation,))
    counts = {"MAX_PAGE_BLOCKS": len(sizes), "MAX_PAGE_CHARS": sum(row["text_size"] for row in sizes),
              "MAX_PAGE_METADATA_CHARS": sum(row["metadata_size"] for row in sizes)}
    monkeypatch.setattr(table_conditions, limit, counts[limit])
    assert conditions.bundle()[1]["state"] == "supported"
    monkeypatch.setattr(table_conditions, limit, counts[limit] - 1)
    calls = []
    real_rows = conditions.db.rows

    def recorded_rows(sql, parameters=()):
        calls.append(sql)
        return real_rows(sql, parameters)

    monkeypatch.setattr(conditions.db, "rows", recorded_rows)
    assert_unavailable(conditions.bundle(), "condition_inspection_limit")
    # The caller's already-read table parent is permitted; page-wide contents
    # must not be materialized after the bounded size query rejects the page.
    page_reads = [sql for sql in calls if "SELECT * FROM blocks" in sql and "page_index=?" in sql]
    assert page_reads == []
    assert any("length(text)" in sql and "LIMIT ?" in sql for sql in calls)


def test_frozen_extraction_identity_survives_import_but_citations_use_real_db_version(conditions):
    fragments, annotation, warnings = conditions.bundle()
    real_version = conditions.imported["version_id"]
    assert real_version != FROZEN_VERSION and annotation["state"] == "supported" and warnings == []
    assert all(piece["version_id"] == FROZEN_VERSION for piece in annotation["pieces"])
    assert conditions.db.version(real_version)["sha256"] == annotation["source_sha256"] == SOURCE_HASH
    assert json.loads(conditions.parent()["metadata_json"])["version_id"] == FROZEN_VERSION
    # Build the citation from the helper's exact fragments under its real DB
    # source identity; the extraction UUID is not a public citation override.
    citation_source = {**conditions.source, "source_id": "S001", "blocks": [conditions.block, *fragments],
                       "text": "\n".join([conditions.block["text"], *(fragment["text"] for fragment in fragments)])}
    catalogue = StructuredAnswerBuilder(conditions.db, conditions.snapshot, "Return the recorded passages.",
                                        enforce_contract=True).catalogue([citation_source], "question")
    assert catalogue.references and all(reference["version_id"] == real_version for reference in catalogue.references)
    assert all(reference["source_file_sha256"] == SOURCE_HASH for reference in catalogue.references)
    query_id = uid()
    conditions.db.execute(
        "INSERT INTO query_runs(id,question,scope_json,snapshot_json,state,created_at,updated_at) "
        "VALUES(?,?,?,?,'running',?,?)",
        (query_id, "Synthetic citation identity check", json_dump(conditions.snapshot.scope),
         json_dump(conditions.snapshot.as_dict()), now(), now()))
    registered = QueryService.register_sources(SimpleNamespace(db=conditions.db), query_id, [citation_source])
    stored = conditions.db.one("SELECT version_id,document_id,source_json FROM citations WHERE query_id=?",
                                (query_id,))
    assert stored["version_id"] == registered[0]["version_id"] == real_version
    assert stored["document_id"] == conditions.imported["document_id"]
    public_citation = json.loads(stored["source_json"])
    assert public_citation["version_id"] == real_version
    assert public_citation["page_number"] == 1
    assert CONDITION_TEXT in public_citation["text"]
    assert public_citation["citation_url"] == f"/api/v1/citations/{query_id}/S001"
