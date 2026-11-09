"""Declared synthetic glyph/path observations; no PDF renderer is invoked."""

import hashlib

from test_i5_table_geometry import cell, glyphs_at

from services.ingestion.table_rules import RULE_SCHEMA


def rule_record(lines, *, source_sha256, page_index=0):
    objects = []
    for index, (x0, y0, x1, y1) in enumerate(lines):
        objects.append({
            "id": f"o{index}", "object_index": index, "type": 2,
            "bbox": [min(x0, x1) - .25, min(y0, y1) - .25, max(x0, x1) + .25, max(y0, y1) + .25],
            "active": True, "matrix": [1, 0, 0, 1, 0, 0], "fill_mode": 0, "stroke": True,
            "stroke_width": .5, "stroke_rgba": [0, 0, 0, 255], "fill_rgba": [0, 0, 0, 255],
            "has_transparency": False, "dash_count": 0, "clip": {"handle_present": True, "path_count": -1},
            "segments": [{"index": 0, "type": 2, "point": [x0, y0], "close": False},
                         {"index": 1, "type": 0, "point": [x1, y1], "close": False}],
        })
    return {"schema_version": RULE_SCHEMA, "source_sha256": source_sha256, "page_index": page_index,
            "coordinate_frame": "pdf_user_space_unrotated", "complete": True, "limit_reason": None,
            "object_count": len(objects), "segment_count": 2 * len(objects), "objects": objects}


def grouped_header_fixture():
    """Min and Max have no value-bearing sister cell carrying their subject."""
    payload = b"%PDF-1.7\nsynthetic MODEL-Z7 header rules; Temperature Min 3 Max 9 degC\n"
    source_sha = hashlib.sha256(payload).hexdigest()
    headers = [(20, "Parameter"), (180, "Min"), (280, "Typ"), (380, "Max"), (450, "Units")]
    lines = [(x, 45, text) for x, text in headers] + [(278, 24, "MODEL-Z7"), (20, 80, "Temperature"),
                                                    (180, 80, "3"), (380, 80, "9"), (450, 80, "°C")]
    cells = [cell(text, 0, column, [x, 45, x + len(text) * 4, 53], header=True)
             for column, (x, text) in enumerate(headers)]
    cells[2]["text"] = "MODEL-Z7 Typ"
    cells[2]["bbox"].update(l=278, t=24, r=310, b=53)
    cells.extend(cell(text, 1, column, [x, 80, x + len(text) * 4, 88], row_header=column == 0)
                 for column, x, text in ((0, 20, "Temperature"), (1, 180, "3"), (3, 380, "9"), (4, 450, "°C")))
    page = {"page_index": 0, "width": 500, "height": 400, "media_box": [0, 0, 500, 400],
            "crop_box": [0, 0, 500, 400], "effective_box": [0, 0, 500, 400], "rotation": 0,
            "source_sha256": source_sha, "classification": "native"}
    native = glyphs_at(lines)
    native["source_sha256"] = source_sha
    native["rules"] = rule_record([[15, 382, 480, 382], [15, 340, 480, 340],
                                   [150, 300, 150, 382], [425, 300, 425, 382]], source_sha256=source_sha)
    return {"payload": payload, "data": {"num_rows": 2, "num_cols": 5, "table_cells": cells},
            "page": page, "bbox": [15, 300, 480, 382], "parser_size": (500, 400), "native": native}


def adjacent_grouped_header_fixture():
    """Two real synthetic enclosures: MODEL-Z7 covers Min/Typ, ALT-Q8 Max/Units.

    The distinct subjects are explicit test data. This does not assert that the
    two quantities may be combined into a single component's operating range.
    """
    fixture = grouped_header_fixture()
    fixture["payload"] += b"ALT-Q8 adjacent enclosure, distinct from MODEL-Z7\n"
    source_sha = hashlib.sha256(fixture["payload"]).hexdigest()
    fixture["page"]["source_sha256"] = fixture["native"]["source_sha256"] = source_sha
    fixture["native"]["rules"] = rule_record([[15, 382, 480, 382], [15, 340, 480, 340],
                                              [150, 300, 150, 382], [350, 300, 350, 382], [480, 300, 480, 382]],
                                             source_sha256=source_sha)
    fixture["data"]["table_cells"][4]["bbox"].update(l=410, t=24)
    fixture["data"]["table_cells"][4]["text"] = "ALT-Q8 Units"
    glyphs = fixture["native"]["glyphs"]
    for offset, character in enumerate("ALT-Q8"):
        index = len(glyphs)
        glyphs.append({"id": f"g{index}", "glyph_index": index, "codepoint": ord(character), "text": character,
                       "bbox": [410 + offset * 4, 368, 414 + offset * 4, 376], "generated": 0, "unicode_map_error": 0})
    return fixture
