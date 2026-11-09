"""Small source-page frames; complete extraction diagnostics stay in SQLite.

A source fragment carries the coordinates and provenance needed to locate it.
Repeating every OCR/coverage diagnostic for each block is not a new proof and
can exceed the unchanged logical limits of a full execution trace. The exact
stored JSON is identified when this view omits fields; that digest is only an
identity link, never a substitute for the catalogue's independent DB checks.
The full page endpoints and immutable extraction records are not projected.
"""

import hashlib
import json

from .errors import ApiError

_SOURCE_PAGE_FIELDS = frozenset({
    "page_index", "page_number", "label", "width", "height", "display_width", "display_height",
    "media_box", "crop_box", "effective_box", "rotation", "media_box_source", "crop_box_source",
    "orientation_correction", "orientation_source", "extraction_state", "extraction_route",
    "classification", "ocr_used", "needs_ocr", "source_sha256",
})


def source_page_geometry(raw_geometry_json: str | None) -> dict:
    """Project a new source view without changing the exact stored page JSON.

    Ordinary legacy coordinate-only frames retain their exact shape. Missing
    Office/page metadata keeps the historical empty frame. Values of retained
    geometry fields are never normalized or repaired by this projection.
    """
    if not raw_geometry_json:
        return {}
    page = json.loads(raw_geometry_json)
    if not isinstance(page, dict):
        raise ApiError("invalid_source_geometry", "Le cadre de page enregistré n'est pas un objet vérifiable.", 409)
    if page.keys() <= _SOURCE_PAGE_FIELDS:
        return page
    return {**{key: value for key, value in page.items() if key in _SOURCE_PAGE_FIELDS},
            "stored_geometry_sha256": hashlib.sha256(raw_geometry_json.encode("utf-8")).hexdigest()}
