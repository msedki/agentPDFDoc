"""Transform parser display coordinates to unrotated PDF user-space points."""

import math

from .errors import IngestionError


def normalize_box(values):
    if len(values) != 4 or any(not math.isfinite(float(x)) for x in values):
        raise IngestionError("INVALID_GEOMETRY", "Les coordonnées de provenance sont invalides.")
    x0, y0, x1, y1 = map(float, values)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def display_point_to_pdf(x, y, crop_box, rotation):
    left, bottom, right, top = normalize_box(crop_box)
    width, height = right - left, top - bottom
    if rotation == 0:
        px, py = x, y
    elif rotation == 90:
        px, py = width - y, x
    elif rotation == 180:
        px, py = width - x, height - y
    elif rotation == 270:
        px, py = y, height - x
    else:
        raise IngestionError("INVALID_ROTATION", "La rotation PDF doit être un multiple de 90 degrés.")
    return px + left, py + bottom


def docling_box_to_pdf(bbox, parser_size, page):
    """Docling uses a zero-origin rendered CropBox, potentially rotated.

    Refuse size mismatch instead of inventing a transform. Installed-parser
    contract tests verify the frame; callers retain original parser geometry.
    """
    if bbox is None:
        return None
    crop = normalize_box(page.get("effective_box", page["crop_box"]))
    crop_width, crop_height = crop[2] - crop[0], crop[3] - crop[1]
    rotation = int(page["rotation"]) % 360
    expected = (crop_height, crop_width) if rotation in (90, 270) else (crop_width, crop_height)
    width, height = float(parser_size[0]), float(parser_size[1])
    if not all(math.isclose(a, b, abs_tol=2.0) for a, b in zip((width, height), expected, strict=True)):
        raise IngestionError("GEOMETRY_FRAME_MISMATCH", "Le repère du parseur PDF ne correspond pas à la page.")
    origin = str(bbox.get("coord_origin", "")).upper().split(".")[-1]
    if origin not in {"TOPLEFT", "BOTTOMLEFT"}:
        raise IngestionError("UNKNOWN_COORDINATE_ORIGIN", "L'origine des coordonnées du parseur est inconnue.")
    left, right = float(bbox["l"]), float(bbox["r"])
    low, high = float(bbox["b"]), float(bbox["t"])
    if origin == "TOPLEFT":
        low, high = height - low, height - high
    display_box = normalize_box((left, low, right, high))
    corners = [display_point_to_pdf(x, y, crop, rotation)
               for x in (display_box[0], display_box[2])
               for y in (display_box[1], display_box[3])]
    result = normalize_box((min(p[0] for p in corners), min(p[1] for p in corners),
                            max(p[0] for p in corners), max(p[1] for p in corners)))
    tolerance = 2.0
    if result[0] < crop[0] - tolerance or result[1] < crop[1] - tolerance or result[2] > crop[2] + tolerance or result[3] > crop[3] + tolerance:
        raise IngestionError("GEOMETRY_OUTSIDE_PAGE", "La région source dépasse le repère PDF connu.")
    return result
