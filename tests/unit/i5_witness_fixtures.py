"""Explicit synthetic observations for the existing table-contract regressions.

The character boxes are test data, not a PDF/OCR engine substitute or a claim of
native fidelity. Production code rebuilds and validates the witness normally;
no quality flag or relation result is patched. Sparse parser indices and source
text remain available separately from the canonical geometric projection.
"""

import asyncio
import copy
import hashlib

from test_retrieval import library_search

from services.ingestion.docling_adapter import table_text
from services.ingestion.table_geometry import build_table_general_conditions, build_table_quality

FROZEN_REVISION = "1ac2ef49-36a3-4483-b3c5-dad605e23b14"


def witnessed_sparse_table(storage, rows, *, target=1, mutate=None, general_conditions=None):
    parser_cells = [{"text": text, "start_row_offset_idx": row, "end_row_offset_idx": row + 1,
                     "start_col_offset_idx": column, "end_col_offset_idx": column + 1,
                     "column_header": row == 0, "row_header": column == 1, "row_section": False}
                    for row, fields in enumerate(rows) for column, text in fields]
    original_text = "\n".join(" | ".join(value for _, value in fields) for fields in rows)
    data = {"table_cells": parser_cells, "num_cols": max(column for fields in rows for column, _ in fields) + 1,
            "num_rows": len(rows)}
    block = {"id": "sparse-table", "type": "table", "text": original_text,
             "precision": "table", "metadata": {"table_data": data}}
    if mutate:
        mutate(block)
    widths = [max(52, max((len(cell["text"]) * 4 + 20 for cell in parser_cells
                          if cell["start_col_offset_idx"] == column and cell["end_col_offset_idx"] == column + 1), default=52))
              for column in range(data["num_cols"])]
    positions = [20]
    for width in widths:
        positions.append(positions[-1] + width)
    page_width, page_height = positions[-1] + 20, max(240, 70 + len(rows) * 24)
    payload = b"%PDF-1.7\n" + (("Electrical characteristics\n" + general_conditions + "\n")
                                  if general_conditions is not None else "").encode() + original_text.encode()
    source_sha = hashlib.sha256(payload).hexdigest()
    glyphs = []
    for cell in parser_cells:
        left, right = positions[cell["start_col_offset_idx"]], positions[cell["end_col_offset_idx"]]
        top, bottom = 40 + cell["start_row_offset_idx"] * 24, 52 + (cell["end_row_offset_idx"] - 1) * 24
        cell.update(row_span=cell["end_row_offset_idx"] - cell["start_row_offset_idx"],
                    col_span=cell["end_col_offset_idx"] - cell["start_col_offset_idx"],
                    bbox={"l": left, "t": top, "r": right - 6, "b": bottom, "coord_origin": "TOPLEFT"})
        for offset, character in enumerate(cell["text"]):
            index = len(glyphs)
            x = left + 4 + offset * 4
            glyphs.append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                           "bbox": [x, page_height - top - 10, x + 4, page_height - top - 2],
                           "generated": 0, "unicode_map_error": 0, "render_mode": 0})
    box = [18, page_height - (54 + (len(rows) - 1) * 24), positions[-1], page_height - 36]
    page = {"page_index": 0, "width": page_width, "height": page_height,
            "media_box": [0, 0, page_width, page_height], "crop_box": [0, 0, page_width, page_height],
            "effective_box": [0, 0, page_width, page_height], "rotation": 0,
            "source_sha256": source_sha, "classification": "native"}
    native = {"schema_version": "pdfium-glyphs-v1", "source_sha256": source_sha, "page_index": 0,
              "coordinate_frame": "pdf_user_space_unrotated", "glyphs": glyphs,
              "complete": True, "limit_reason": None}
    original = copy.deepcopy(data)
    projected, quality = build_table_quality(data, box, (page_width, page_height), page,
                                            native=native, source_sha256=source_sha)
    text = table_text(projected)
    block.update(text=text, raw_text=text, bbox=box)
    block["metadata"] = {"extraction_method": "native", "ocr_used": False,
                         "parser_table_data": original, "table_data": projected, "table_quality": quality}
    blocks = [block]
    if general_conditions is not None:
        for identity, literal, kind, y in (("general-heading", "Electrical characteristics", "heading", 8),
                                            ("general-conditions", general_conditions, "text", 22)):
            blocks.append({"id": identity, "type": kind, "text": literal, "raw_text": literal,
                           "bbox": [20, page_height - y - 8, min(page_width - 20, 20 + len(literal) * 4), page_height - y],
                           "precision": "block", "metadata": {"extraction_method": "native", "ocr_used": False}})
    settings, db, _, indexer = storage
    blob = settings.data_dir / "originals" / (source_sha + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original("synthetic-table.pdf", source_sha, blob)
    for item in blocks:
        item.update(page_index=0, version_id=imported["version_id"], extraction_revision_id=FROZEN_REVISION,
                    source_text_hash=hashlib.sha256(item["text"].encode()).hexdigest())
    if general_conditions is not None:
        block["metadata"]["table_general_conditions"] = build_table_general_conditions(block, blocks, page, source_sha256=source_sha)
    extraction = {"sha256": source_sha, "fingerprint": "i5-explicit-glyph-double-v1", "page_count": 1,
                  "extraction_revision_id": FROZEN_REVISION, "status": "ready", "pages": [{**page, "blocks": blocks}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    search, snapshot, db = library_search(storage)
    chunk = db.one("SELECT c.* FROM chunks c JOIN chunk_sources s ON s.chunk_uuid=c.chunk_uuid "
                   "WHERE s.block_id='sparse-table' ORDER BY c.id LIMIT 1")
    source = search.resolver.source_for_chunk(chunk, snapshot)
    lines = text.splitlines()
    line = lines[target]
    start = sum(len(value) + 1 for value in lines[:target])
    source["blocks"] = [item for item in source["blocks"] if item["type"] == "table"]
    source["blocks"][0].update(text=line, start_offset=start, end_offset=start + len(line))
    source["text"] = line
    return search, snapshot, source, text
