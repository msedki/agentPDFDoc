"""Real source resolver/trace; explicit read-only DB rows, no OCR or model."""

import hashlib
import json
from copy import deepcopy

import pytest

from services.api.errors import ApiError
from services.api.execution_trace import ExecutionTrace, read_verified_trace
from services.api.scope import ScopeResolver, ScopeSnapshot
from services.api.settings import Settings


def geometry():
    return {"page_index": 0, "page_number": 1, "label": "i", "width": 600., "height": 800.,
            "display_width": 800., "display_height": 600., "rotation": 90,
            "media_box": [0., 0., 600., 800.], "crop_box": [10., 20., 590., 780.],
            "effective_box": [10., 20., 590., 780.], "orientation_correction": 0,
            "extraction_state": "native", "source_sha256": "a" * 64,
            "ocr_orientations": [{"bbox": [0., 0., 10., 20.], "rotation": 0,
                                  "confidence": .9, "status": "explicit diagnostic"} for _ in range(256)],
            "unresolved_regions": [{"bbox": [0., 0., 10., 20.], "reason": "explicit unresolved region"}
                                   for _ in range(256)]}


class ReadOnlyRows:
    """Explicit SQL row double; this object never writes an extraction or DB."""
    def __init__(self, page, count=128):
        self.raw = json.dumps(page, ensure_ascii=False)
        self.records = [{"block_id": f"B{index}", "page_index": 0, "text": "x",
                         "start_offset": 0, "end_offset": 1, "bbox_json": "[1,2,3,4]",
                         "precision": "block", "kind": "text", "section_id": None,
                         "extraction_revision_id": "revision", "source_text_hash": hashlib.sha256(b"x").hexdigest(),
                         "metadata_json": '{"metadata":{"extraction_method":"native"}}',
                         "geometry_json": self.raw} for index in range(count)]

    def rows(self, query, parameters=()):
        assert "FROM chunk_sources" in query
        assert parameters == ("generation", "chunk")
        return deepcopy(self.records)

    def one(self, query, parameters=()):
        if "FROM index_generations" in query:
            return {"state": "ready", "coverage_json": "{}", "warnings_json": "[]"}
        assert "FROM blocks" in query
        row = deepcopy(self.records[0])
        return {**row, "id": row["block_id"]}


def source(db):
    snapshot = ScopeSnapshot({"kind": "pages"}, ["generation"], {"generation": "version"},
                             {"generation": "document"}, [0])
    return ScopeResolver(db).source_for_chunk(
        {"generation_id": "generation", "chunk_uuid": "chunk", "extraction_revision_id": "revision"}, snapshot)


def test_many_source_blocks_keep_frames_and_trace_within_unchanged_limits(tmp_path):
    original_page = geometry()
    db = ReadOnlyRows(original_page)
    before = deepcopy(db.records)
    result = source(db)
    payload = {"results": [result], "top10": [result]}
    settings = Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {
        "mode": "full", "max_bytes_per_query": 8_388_608, "max_total_bytes": 67_108_864}})
    trace = ExecutionTrace(settings, "many-source-blocks")
    try:
        trace.record("retrieval", payload)
        trace.record("query.done", {"state": "done"})
    finally:
        trace.close()
    assert read_verified_trace(trace.path)[0]["data"] == payload
    assert trace.bytes_written < 8_388_608
    assert len(result["blocks"]) == 128 and result["text"] == "\n".join(["x"] * 128)
    assert db.records == before and json.loads(db.raw) == original_page
    for block in result["blocks"]:
        frame = block["page"]
        for key in ("page_index", "label", "rotation", "crop_box", "effective_box", "media_box",
                    "width", "height", "display_width", "display_height", "source_sha256", "extraction_state"):
            assert frame[key] == original_page[key]
        assert frame["stored_geometry_sha256"] == hashlib.sha256(db.raw.encode()).hexdigest()
        assert "ocr_orientations" not in frame and "unresolved_regions" not in frame
        assert block["bbox"] == [1, 2, 3, 4] and block["start_offset"] == 0 and block["end_offset"] == 1


def test_coordinate_only_legacy_source_keeps_exact_frame():
    page = {"page_index": 0, "width": 612, "height": 792, "rotation": 0, "label": "A"}
    assert source(ReadOnlyRows(page, 1))["blocks"][0]["page"] == page


def test_selected_span_uses_same_frame_without_changing_literal_identity():
    db = ReadOnlyRows(geometry(), 1)
    span = {"blockId": "B0", "startOffset": 0, "endOffset": 1}
    snapshot = ScopeSnapshot({"kind": "selection"}, ["generation"], {"generation": "version"},
                             {"generation": "document"}, [0], ["B0"], [span])
    selected = ScopeResolver(db).selected_sources(snapshot)[0]
    expected = source(db)["blocks"][0]
    assert selected["blocks"][0]["page"] == expected["page"]
    assert selected["blocks"][0]["source_text_hash"] == expected["source_text_hash"]
    assert selected["text"] == "x"


def test_projection_does_not_repair_invalid_retained_geometry(tmp_path):
    page = geometry()
    page["width"] = float("nan")
    result = source(ReadOnlyRows(page, 1))
    settings = Settings(tmp_path, {"app": {"data_dir": "data"}, "trace": {"mode": "full"}})
    trace = ExecutionTrace(settings, "invalid-retained-frame")
    try:
        with pytest.raises(ApiError, match="trace"):
            trace.record("retrieval", {"results": [result]})
    finally:
        trace.close()
    assert trace.sequence == 0
