"""Synthetic evidence for explicit pre-table bands and literal native repair."""

import copy
import hashlib

from services.ingestion.table_geometry import (
    build_table_general_conditions,
    native_condition_projection,
    validate_native_condition_projection,
    validate_table_general_conditions,
)

SOURCE_HASH = hashlib.sha256(b"independent generic conditions fixture").hexdigest()


def block(identity, text, box, kind="text"):
    return {"id": identity, "page_index": 0, "type": kind, "text": text, "raw_text": text, "bbox": box,
            "source_text_hash": hashlib.sha256(text.encode()).hexdigest(), "version_id": "version", "extraction_revision_id": "revision", "metadata": {}}


def condition_page():
    table = block("table", "Parameter | Min | Typ | Max | Units\nPulse | 5 | 8 | 11 | ms", [20, 100, 480, 280], "table")
    heading = block("heading", "Electrical characteristics", [20, 308, 250, 318], "heading")
    condition = block("conditions", "TA = 18°C, supply = 4V unless otherwise noted.", [20, 290, 470, 302])
    page = {"page_index": 0, "crop_box": [0, 0, 500, 400], "effective_box": [0, 0, 500, 400], "rotation": 0, "source_sha256": SOURCE_HASH}
    blocks = [heading, condition, table]
    table["metadata"]["table_general_conditions"] = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    return table, blocks, page


def test_explicit_band_preserves_all_condition_text_and_source_identities():
    table, blocks, page = condition_page()
    annotation = validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "supported" and annotation["support_scope"] == "geometric_binding_only"
    assert [piece["block_id"] for piece in annotation["pieces"]] == ["heading", "conditions"]
    assert annotation["pieces"][1]["text"].endswith("unless otherwise noted.")
    assert all(piece["version_id"] == "version" and piece["extraction_revision_id"] == "revision" for piece in annotation["pieces"])


def test_proximity_alone_does_not_establish_general_conditions():
    table, blocks, page = condition_page()
    blocks[0]["type"] = "text"
    assert build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)["state"] == "absent"
    assert validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)["state"] == "unavailable"


def test_missing_fragment_of_declared_band_is_not_relabelled_absent():
    table, blocks, page = condition_page()
    assert validate_table_general_conditions(table, [blocks[0], table], page, source_sha256=SOURCE_HASH)["state"] == "unavailable"
    assert validate_table_general_conditions(table, blocks, page, source_sha256="0" * 64)["state"] == "unavailable"


def test_fragment_hash_revision_and_exact_scope_are_independent_gates():
    table, blocks, page = condition_page()
    for modification in ({"source_text_hash": "0" * 64}, {"extraction_revision_id": "other"}, {"page_index": 1}):
        altered = copy.deepcopy(blocks)
        altered[1].update(modification)
        assert validate_table_general_conditions(table, altered, page, source_sha256=SOURCE_HASH)["state"] == "unavailable"
    clipped = copy.deepcopy(blocks)
    clipped[1].update(text="TA = 18°C", raw_text="TA = 18°C", source_text_hash=hashlib.sha256("TA = 18°C".encode()).hexdigest())
    assert validate_table_general_conditions(table, clipped, page, source_sha256=SOURCE_HASH)["state"] == "unavailable"


def test_intervening_table_prevents_cross_table_inheritance():
    table, blocks, page = condition_page()
    intervening = block("other_table", "Other", [20, 283, 480, 289], "table")
    assert build_table_general_conditions(table, [*blocks, intervening], page, source_sha256=SOURCE_HASH)["state"] == "absent"


def test_piece_budget_failure_remains_explicit(monkeypatch):
    table, blocks, page = condition_page()
    monkeypatch.setattr("services.ingestion.table_geometry.MAX_GENERAL_PIECES", 1)
    annotation = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert annotation["state"] == "unavailable" and annotation["reasons"] == ["general_condition_band_limit"]


def test_general_condition_binding_respects_rotation_and_crop_origin():
    from services.ingestion.geometry import display_point_to_pdf

    table, blocks, page = condition_page()
    frame = [12, 19, 512, 419]
    for item in blocks:
        box = item["bbox"]
        corners = [display_point_to_pdf(x, y, frame, 180) for x in (box[0], box[2]) for y in (box[1], box[3])]
        item["bbox"] = [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]
    page.update(rotation=180, crop_box=frame, effective_box=frame)
    table["metadata"]["table_general_conditions"] = build_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)
    assert validate_table_general_conditions(table, blocks, page, source_sha256=SOURCE_HASH)["state"] == "supported"


def native_band(text):
    page = {"page_index": 0, "crop_box": [0, 0, 500, 400], "effective_box": [0, 0, 500, 400], "rotation": 0}
    glyphs = [{"id": f"g{index}", "glyph_index": index, "codepoint": ord(char), "text": char,
               "bbox": [20 + index * 4, 290, 24 + index * 4, 298], "generated": 0, "unicode_map_error": 0, "render_mode": 0}
              for index, char in enumerate(text)]
    native = {"schema_version": "pdfium-glyphs-v1", "source_sha256": SOURCE_HASH, "page_index": 0,
              "coordinate_frame": "pdf_user_space_unrotated", "glyphs": glyphs, "complete": True, "limit_reason": None}
    return page, native


def test_parser_duplicate_is_replaced_only_by_literal_acquired_glyphs():
    parser_text = "V-- = 8V unless otherwise noted."
    source_text = "V- = 8V unless otherwise noted."
    page, native = native_band(source_text)
    actual, witness = native_condition_projection(parser_text, [20, 290, 480, 300], page, native, SOURCE_HASH)
    assert actual == source_text and witness["state"] == "supported"
    metadata = {"parser_original_text": parser_text, "native_condition_projection": witness}
    assert validate_native_condition_projection(actual, metadata, source_sha256=SOURCE_HASH, page_index=0)["state"] == "supported"
    assert validate_native_condition_projection(actual.replace("8V", "9V"), metadata, source_sha256=SOURCE_HASH, page_index=0)["state"] == "unavailable"


def test_uncertain_native_glyph_never_becomes_a_symbolic_correction():
    parser_text = "V-- = 8V unless otherwise noted."
    page, native = native_band("V- = 8V unless otherwise noted.")
    native["glyphs"][1]["unicode_map_error"] = 1
    actual, witness = native_condition_projection(parser_text, [20, 290, 480, 300], page, native, SOURCE_HASH)
    assert actual == parser_text and witness["state"] == "unavailable"
