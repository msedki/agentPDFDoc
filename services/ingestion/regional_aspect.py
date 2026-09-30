"""Bounded OCR derivatives with an explicit inverse into the source raster."""

import math

from .geometry import normalize_box


def pdf_box_to_display_top_left(box, page):
    left, bottom, right, top = page["effective_box"]
    width, height = right - left, top - bottom
    rotation = int(page["rotation"]) % 360

    def transform(x, y):
        x, y = x - left, y - bottom
        if rotation == 0:
            return x, height - y
        if rotation == 90:
            return y, x
        if rotation == 180:
            return width - x, y
        if rotation == 270:
            return height - y, width - x
        raise ValueError("Unsupported PDF rotation")

    points = [transform(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    return normalize_box([min(x for x, _ in points), min(y for _, y in points),
                          max(x for x, _ in points), max(y for _, y in points)])


def complete_bitmap_pixel_size(region, page):
    """Use only one complete, unreflected, unskewed top-level image ROI."""
    box = [region[key] for key in ("l", "t", "r", "b")]
    images = page.get("image_regions", [])
    matches = [image for image in images
               if all(math.isclose(a, b, abs_tol=.25) for a, b in
                      zip(box, pdf_box_to_display_top_left(image["bbox"], page), strict=True))]
    if len(matches) != 1:
        return None
    image = matches[0]
    if image.get("object_level", 0) != 0 or not image.get("pixel_size") or not image.get("matrix"):
        return None
    frame = page["effective_box"]
    if image["bbox"][0] < frame[0] or image["bbox"][1] < frame[1] or image["bbox"][2] > frame[2] or image["bbox"][3] > frame[3]:
        return None
    # A second overlapping image means that the rendered pixels are a mixture.
    if any(other is not image and min(other["bbox"][2], image["bbox"][2]) > max(other["bbox"][0], image["bbox"][0])
           and min(other["bbox"][3], image["bbox"][3]) > max(other["bbox"][1], image["bbox"][1]) for other in images):
        return None
    matrix = image["matrix"]
    if len(matrix) != 6 or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in matrix):
        return None
    a, b, c, d, _, _ = matrix
    if a * d - b * c <= 0:
        return None
    tolerance = max(abs(a), abs(b), abs(c), abs(d), 1) * 1e-6
    direct = abs(b) <= tolerance and abs(c) <= tolerance and abs(a) > tolerance and abs(d) > tolerance
    swapped = abs(a) <= tolerance and abs(d) <= tolerance and abs(b) > tolerance and abs(c) > tolerance
    if not direct and not swapped:
        return None
    size = tuple(image["pixel_size"])
    if len(size) != 2 or any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in size):
        return None
    axes_swapped = swapped != (int(page["rotation"]) % 360 in (90, 270))
    return size[::-1] if axes_swapped else size


def reduced_aspect_size(source_size, intrinsic_size, threshold=1.25):
    """Restore intrinsic pixel aspect by reducing one axis, never allocating up."""
    if intrinsic_size is None:
        return tuple(source_size)
    width, height = source_size
    ratio = intrinsic_size[0] / intrinsic_size[1]
    distortion = (width / height) / ratio
    if 1 / threshold <= distortion <= threshold:
        return width, height
    if distortion > 1:
        return max(1, min(width, round(height * ratio))), height
    return width, max(1, min(height, round(width / ratio)))


def oriented_resize(source_size, derived_size, angle):
    """Compose anisotropic reduction before the parent's PIL quarter turn."""
    if angle not in (0, 90, 180, 270):
        raise ValueError("Unsupported OCR orientation")
    if angle in (90, 270):
        source_size, derived_size = source_size[::-1], derived_size[::-1]
    return source_size, derived_size


def inverse_resized_box(box, source_size, derived_size):
    """Invert the actual rounded derivative dimensions on all four corners."""
    sx, sy = source_size[0] / derived_size[0], source_size[1] / derived_size[1]
    points = [(x * sx, y * sy) for x in (box[0], box[2]) for y in (box[1], box[3])]
    return [min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points)]
