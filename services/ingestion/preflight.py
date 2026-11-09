"""Read-only PDF geometry and selective OCR routing signals."""

import math
import statistics
from pathlib import Path
from typing import Any

from .config import OCR_RENDER_SCALE, TABLE_RENDER_SCALE, IngestionConfig, sha256_file
from .errors import IngestionError
from .geometry import normalize_box


def rendered_pixels(width, height, scale):
    if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
        raise IngestionError("INVALID_GEOMETRY", "Les dimensions de rendu PDF sont invalides.")
    return math.ceil(width * scale) * math.ceil(height * scale)


def check_render_budget(page, route, config):
    if route in {"blank", "native"}:
        return
    scale = OCR_RENDER_SCALE if route == "regional_ocr" else TABLE_RENDER_SCALE
    if config.pdf_backend == "pypdfium2":
        # Docling PDFium sharpens by rendering 1.5x then resizing. Full page
        # table images use scale 2; OCR calls render individual crops at scale3.
        scale = TABLE_RENDER_SCALE * 1.5
    pixels = rendered_pixels(page["display_width"], page["display_height"], scale)
    if pixels > config.max_page_render_pixels:
        raise IngestionError("PDF_RENDER_LIMIT", "Cette page dépasse le plafond de pixels du rendu d'extraction.",
                             {"page_index": page["page_index"], "route": route, "scale": scale, "render_pixels": pixels, "pixel_limit": config.max_page_render_pixels})
    if config.pdf_backend == "pypdfium2" and route == "regional_ocr":
        frame = page["effective_box"]
        for region in page.get("image_regions", []):
            box = region["bbox"]
            width = min(box[2], frame[2]) - max(box[0], frame[0])
            height = min(box[3], frame[3]) - max(box[1], frame[1])
            if width <= 0 or height <= 0:
                continue
            pixels = rendered_pixels(width, height, OCR_RENDER_SCALE * 1.5)
            if pixels > config.max_ocr_region_pixels:
                raise IngestionError("OCR_RENDER_LIMIT", "Ce bitmap dépasse le plafond de pixels OCR avant chargement des modèles.",
                                     {"page_index": page["page_index"], "render_pixels": pixels,
                                      "pixel_limit": config.max_ocr_region_pixels, "component": "preflight_bitmap"})


MAX_VECTOR_OBSERVATIONS = 4096
MAX_VECTOR_OCR_REGIONS = 64


def _native_overlap_ratio(region, native_regions):
    """Exact union intersection for the observed native rectangles only."""
    clipped = [[max(region[0], box[0]), max(region[1], box[1]), min(region[2], box[2]), min(region[3], box[3])]
               for box in native_regions]
    clipped = [box for box in clipped if box[0] < box[2] and box[1] < box[3]]
    if not clipped:
        return 0.0
    cuts = sorted({value for box in clipped for value in (box[0], box[2])})
    area = 0.0
    for left, right in zip(cuts, cuts[1:], strict=False):
        intervals = sorted((box[1], box[3]) for box in clipped if box[0] < right and left < box[2])
        if not intervals:
            continue
        low, high = intervals[0]
        covered = 0.0
        for start, end in intervals[1:]:
            if start > high:
                covered += high - low
                low, high = start, end
            else:
                high = max(high, end)
        covered += high - low
        area += covered * (right - left)
    return area / ((region[2] - region[0]) * (region[3] - region[1]))


def uncovered_vector_regions(vector_regions, native_text_regions, effective_box):
    """Locate text-shaped path groups outside the actual native text layer.

    Paths are not interpreted as letters. A group is only an OCR candidate;
    equations, plots and drawings still require explicit unresolved coverage.
    Thin rules and isolated large shapes do not establish a text candidate.
    Coordinates remain unrotated PDF user-space points.
    """
    if not effective_box or len(vector_regions) > MAX_VECTOR_OBSERVATIONS:
        return []
    frame = normalize_box(effective_box)

    def overlap(box, other):
        return max(0, min(box[2], other[2]) - max(box[0], other[0])) * max(0, min(box[3], other[3]) - max(box[1], other[1]))

    candidates = []
    for raw in vector_regions:
        box = normalize_box(raw)
        box = [max(box[0], frame[0]), max(box[1], frame[1]), min(box[2], frame[2]), min(box[3], frame[3])]
        width, height = box[2] - box[0], box[3] - box[1]
        if not (2 <= height <= 32 and width >= 3 and width / height >= .6):
            continue
        if any(overlap(box, native) / (width * height) >= .1 for native in native_text_regions):
            continue
        candidates.append(box)
    if len(candidates) < 6:
        return []
    rows: list[dict] = []
    for box in sorted(candidates, key=lambda item: (-item[3], item[0])):
        row = next((item for item in rows if min(item["bbox"][3], box[3]) - max(item["bbox"][1], box[1])
                    >= .4 * min(item["height"], box[3] - box[1])), None)
        if row is None:
            rows.append({"bbox": list(box), "height": box[3] - box[1], "boxes": [box]})
        else:
            row["boxes"].append(box)
            row["bbox"] = [min(row["bbox"][0], box[0]), min(row["bbox"][1], box[1]),
                           max(row["bbox"][2], box[2]), max(row["bbox"][3], box[3])]
    runs: list[dict[str, Any]] = []
    for row in rows:
        active: dict[str, Any] | None = None
        for box in sorted(row["boxes"]):
            if active is None or box[0] - active["bbox"][2] > max(12, row["height"] * 3):
                active = {"bbox": list(box), "path_count": 1, "row_count": 1, "heights": [box[3] - box[1]]}
                runs.append(active)
            else:
                active["bbox"] = [min(active["bbox"][0], box[0]), min(active["bbox"][1], box[1]),
                                  max(active["bbox"][2], box[2]), max(active["bbox"][3], box[3])]
                active["path_count"] += 1
                active["heights"].append(box[3] - box[1])
    groups: list[dict] = []
    for run in sorted(runs, key=lambda item: (-item["bbox"][3], item["bbox"][0])):
        box = run["bbox"]
        matches = [group for group in groups if
                   0 <= group["last_bottom"] - box[3] <= max(8, statistics.median(group["heights"]) * 2.2)
                   and max(0, min(group["bbox"][2], box[2]) - max(group["bbox"][0], box[0]))
                   >= .5 * min(group["bbox"][2] - group["bbox"][0], box[2] - box[0])]
        if len(matches) != 1:
            groups.append({**run, "bbox": list(box), "heights": list(run["heights"]), "last_bottom": box[1]})
            continue
        group = matches[0]
        group["bbox"] = [min(group["bbox"][0], box[0]), min(group["bbox"][1], box[1]),
                         max(group["bbox"][2], box[2]), max(group["bbox"][3], box[3])]
        group["path_count"] += run["path_count"]
        group["row_count"] += 1
        group["heights"].extend(run["heights"])
        group["last_bottom"] = box[1]
    result = []
    for group in groups:
        if group["path_count"] < 6 or group["row_count"] < 2:
            continue
        region = [max(frame[0], group["bbox"][0] - 2), max(frame[1], group["bbox"][1] - 2),
                  min(frame[2], group["bbox"][2] + 2), min(frame[3], group["bbox"][3] + 2)]
        result.append({"bbox": region, "path_count": group["path_count"], "row_count": group["row_count"],
                       "text_layer_overlap": _native_overlap_ratio(region, native_text_regions),
                       "text_layer_overlap_measure": "union_intersection_over_region_area_observed_native_rectangles",
                       "reason": "vector_body_without_native_text"})
    return result[:MAX_VECTOR_OCR_REGIONS]


def classify_page(text, image_regions, vector_paths, config, *, native_text_regions=(), vector_regions=(), effective_box=None):
    """Signals are explicit; neither sparse text nor an image proves a scan."""
    alphanumeric = sum(character.isalnum() for character in text)
    replacement_ratio = text.count("\ufffd") / max(1, len(text))
    reliable = replacement_ratio <= config.suspect_text_max_replacement_ratio and alphanumeric > 0
    substantial_images = [region for region in image_regions if region["area_ratio"] >= 0.03]
    vector_body = uncovered_vector_regions(vector_regions, native_text_regions, effective_box)
    if vector_body:
        return ("mixed" if reliable else "degraded"), True
    if reliable and not substantial_images:
        return "native", False
    if reliable and substantial_images:
        return "mixed", True
    if substantial_images:
        return "scan_candidate" if not reliable else "mixed", True
    if not text.strip() and vector_paths == 0 and not image_regions:
        return "blank", False
    if not reliable and text.strip():
        return "degraded", True
    return "graphic_uncertain", False


def preflight_pdf(path, config=None):
    settings = config if isinstance(config, IngestionConfig) else IngestionConfig.from_mapping(config)
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise IngestionError("PDF_NOT_FILE", "La source PDF doit être un fichier local.")
    if source.stat().st_size > settings.max_file_mib * 1024 * 1024:
        raise IngestionError("PDF_TOO_LARGE", "Le PDF dépasse la limite de taille configurée.")
    with source.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise IngestionError("INVALID_PDF_SIGNATURE", "La signature du fichier PDF est absente.")
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise IngestionError("PDFIUM_MISSING", "Le runtime pypdfium2 est absent.") from None
    try:
        document = pdfium.PdfDocument(str(source))
    except Exception as exc:
        code = "PDF_ENCRYPTED" if getattr(exc, "err_code", None) == 4 else "PDF_INVALID"
        raise IngestionError(code, "Le PDF ne peut pas être ouvert sans mot de passe ou est invalide.") from None
    try:
        count = len(document)
        if count > settings.max_document_pages:
            raise IngestionError("PDF_TOO_MANY_PAGES", "Le PDF dépasse la limite de pages configurée.")
        if count == 0:
            raise IngestionError("PDF_EMPTY", "Le PDF ne contient aucune page.")
        pages = []
        for index in range(count):
            page = document[index]
            try:
                effective_box = normalize_box(page.get_bbox())
                declared_media = page.get_mediabox(fallback_ok=False)
                declared_crop = page.get_cropbox(fallback_ok=False)
                # PDFium does not reliably expose inherited page-tree boxes.
                # get_bbox is the authoritative effective frame; ANSI defaults
                # would fabricate source metadata for otherwise valid PDFs.
                media_box = normalize_box(declared_media) if declared_media is not None else None
                crop_box = normalize_box(declared_crop) if declared_crop is not None else None
                text_page = page.get_textpage()
                try:
                    text = text_page.get_text_range()
                    text_boxes = []
                    native_region_count = text_page.count_rects()
                    for rectangle in range(min(native_region_count, 256)):
                        text_boxes.append(normalize_box(text_page.get_rect(rectangle)))
                finally:
                    text_page.close()
                image_regions, vector_paths, font_sizes = [], 0, set()
                vector_regions: list[list[float]] = []
                page_area = max(1.0, (effective_box[2] - effective_box[0]) * (effective_box[3] - effective_box[1]))
                for obj in page.get_objects():
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_TEXT:
                        font_sizes.add(round(float(obj.get_font_size()), 2))
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_PATH:
                        vector_paths += 1
                        if len(vector_regions) <= MAX_VECTOR_OBSERVATIONS:
                            vector_regions.append(normalize_box(obj.get_bounds() if hasattr(obj, "get_bounds") else obj.get_pos()))
                    if obj.type != pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                        continue
                    bounds = normalize_box(obj.get_bounds() if hasattr(obj, "get_bounds") else obj.get_pos())
                    area = max(0.0, min(bounds[2], effective_box[2]) - max(bounds[0], effective_box[0])) * max(0.0, min(bounds[3], effective_box[3]) - max(bounds[1], effective_box[1]))
                    image = {"bbox": bounds, "area_ratio": area / page_area, "object_level": int(obj.level)}
                    if obj.level == 0:
                        try:
                            image.update(pixel_size=list(obj.get_px_size()), matrix=list(obj.get_matrix().get()))
                        except Exception:
                            image["intrinsic_geometry_unavailable"] = True
                    image_regions.append(image)
                vector_candidates = uncovered_vector_regions(vector_regions, text_boxes, effective_box)
                classification, needs_ocr = classify_page(text, image_regions, vector_paths, settings,
                                                         native_text_regions=text_boxes, vector_regions=vector_regions,
                                                         effective_box=effective_box)
                text_warnings = []
                geometry_warnings = []
                if any(character in text for character in ("\ufffe", "\uffff", "\x02")):
                    text_warnings.append("PREFLIGHT_TEXT_MAPPING_UNCERTAIN")
                vector_complete = len(vector_regions) <= MAX_VECTOR_OBSERVATIONS and len(vector_candidates) < MAX_VECTOR_OCR_REGIONS
                if not vector_complete:
                    geometry_warnings.append("PREFLIGHT_VECTOR_SCAN_LIMIT")
                if native_region_count > 256:
                    geometry_warnings.append("PREFLIGHT_NATIVE_REGION_SCAN_LIMIT")
                width, height = effective_box[2] - effective_box[0], effective_box[3] - effective_box[1]
                label = document.get_page_label(index) if hasattr(document, "get_page_label") else None
                pages.append({
                    "page_index": index, "page_number": index + 1, "label": label or None,
                    "width": width, "height": height, "media_box": media_box,
                    "crop_box": crop_box, "effective_box": effective_box,
                    "media_box_source": "declared" if media_box else "unavailable_inherited_or_absent",
                    "crop_box_source": "declared" if crop_box else "unavailable_inherited_or_absent",
                    "rotation": page.get_rotation(), "orientation_correction": None,
                    "display_width": page.get_width(), "display_height": page.get_height(),
                    "classification": classification, "needs_ocr": needs_ocr,
                    "text_character_count": len(text),
                    "alphanumeric_count": sum(character.isalnum() for character in text),
                    "native_text_sparse": sum(character.isalnum() for character in text) < settings.suspect_text_min_alnum_chars,
                    "replacement_ratio": text.count("\ufffd") / max(1, len(text)),
                    "text_mapping_warnings": text_warnings,
                    "preflight_geometry_warnings": geometry_warnings,
                    "image_regions": image_regions, "native_text_regions": text_boxes,
                    "native_text_region_count": native_region_count, "native_region_scan_complete": native_region_count <= 256,
                    "uncovered_vector_regions": vector_candidates,
                    "vector_region_scan_complete": vector_complete,
                    "vector_path_count": vector_paths,
                    "text_font_sizes": sorted(value for value in font_sizes if value > 0),
                })
            except IngestionError:
                raise
            except Exception:
                raise IngestionError("PDF_PAGE_INVALID", "Le précontrôle d'une page PDF a échoué.", {"page_index": index}) from None
            finally:
                page.close()
        source_sha256 = sha256_file(source)
        for page in pages:
            page["source_sha256"] = source_sha256
        return {"sha256": source_sha256, "page_count": count, "size_bytes": source.stat().st_size, "pages": pages}
    finally:
        document.close()
