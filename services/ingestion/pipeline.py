"""Windowed extraction and durable, versioned provenance manifests."""

import re
import time
import uuid
from pathlib import Path
from typing import Any

from .checkpoint import CheckpointStore, atomic_json, extraction_lock
from .config import IngestionConfig, sha256_file
from .docling_adapter import DoclingSession, document_to_pages
from .errors import IngestionError
from .preflight import check_render_budget, preflight_pdf

# Page-local failures: the page stays visible in error, the others are published.
# Environment, lifecycle and native faults keep failing the whole extraction.
PAGE_LOCAL_ERRORS = frozenset({"PDF_RENDER_LIMIT", "OCR_RENDER_LIMIT", "INVALID_GEOMETRY",
                               "DOCLING_CONVERSION_FAILED", "OCR_RASTER_FRAME_MISMATCH"})


def page_local(error):
    # Une exception levée hors du statut Docling (initialisation du pipeline,
    # entrée refusée) n'est attribuable à aucune page.
    return error.code in PAGE_LOCAL_ERRORS and not (error.code == "DOCLING_CONVERSION_FAILED" and "exception_type" in error.details)


def conversion_failures(pages):
    return [page["page_index"] for page in pages if any(region.get("reason") == "DOCLING_CONVERSION_FAILED" for region in page.get("unresolved_regions", []))]


def require_conversion(pages, warnings, converted):
    """Sans aucune conversion réussie, un échec du parseur ne se distingue pas d'une faute d'environnement."""
    failed = conversion_failures(pages)
    if failed and not converted:
        cause: dict[str, Any] = next((item for item in warnings if item["code"] == "DOCLING_CONVERSION_FAILED" and item.get("page_index") == failed[0]), {})
        raise IngestionError("DOCLING_CONVERSION_FAILED", "Aucune page n'a pu être convertie ; l'échec du parseur n'est attribuable à aucune page.",
                             {"failed_pages": failed, "parser_status": cause.get("parser_status")})


def should_cancel(event):
    if event is None:
        return False
    return event.is_set() if hasattr(event, "is_set") else Path(event).exists()


def page_route(page, settings):
    if page["classification"] == "blank":
        return "blank"
    if settings.pipeline_route != "auto":
        return settings.pipeline_route
    if page["needs_ocr"]:
        return "regional_ocr"
    regions = page.get("native_text_regions", [])
    midpoint = (page["effective_box"][0] + page["effective_box"][2]) / 2
    left = [box for box in regions if box[2] < midpoint - 15]
    right = [box for box in regions if box[0] > midpoint + 15]
    if page["vector_path_count"] >= 8 or (len(left) >= 3 and len(right) >= 3):
        return "structured"
    if page["vector_path_count"] > 0 and page.get("native_text_sparse", False):
        return "structured"
    sizes = page.get("text_font_sizes", [])
    if sizes and max(sizes) >= min(sizes) * 1.3 and max(sizes) - min(sizes) >= 2:
        return "structured"
    return "native" if page["classification"] == "native" else "structured"


def routing_reason(page, route, settings):
    if route == "blank":
        return "no_visible_content"
    if settings.pipeline_route != "auto":
        return "explicit_profile_route"
    if route == "regional_ocr":
        return "uncovered_image_regions" if page["image_regions"] else "degraded_native_layer"
    if route == "structured":
        if page["vector_path_count"] >= 8:
            return "vector_layout_or_table"
        if page.get("text_font_sizes") and len(page["text_font_sizes"]) > 1:
            return "typography_requires_structure"
        return "ambiguous_order_or_columns"
    return "simple_native_signals"


# Part minimale des caractères alphanumériques de la couche texte PDF à retrouver dans les blocs d'une page.
TEXT_COVERAGE_MIN = 0.95


def native_quality(page):
    blocks = [block for block in page["blocks"] if block["type"] in {"text", "heading", "caption"}]
    count = sum(sum(character.isalnum() for character in block["raw_text"]) for block in blocks)
    expected = page.get("alphanumeric_count", 0)
    coverage = count / max(1, expected)
    boxes = [block["bbox"] for block in blocks]
    localized = bool(boxes) and all(box is not None for box in boxes)
    ordered = localized and all(second[3] <= first[3] + 3 for first, second in zip(boxes, boxes[1:], strict=False))
    return {"passed": coverage >= TEXT_COVERAGE_MIN and localized and ordered,
            "alphanumeric_coverage_ratio": coverage, "localized": localized, "monotonic_vertical_order": ordered}


def text_layer_coverage(page, source):
    """Part de la couche texte PDF retrouvée dans les blocs d'une page ; None si cette couche n'est pas une référence fiable."""
    if source.get("classification") not in {"native", "mixed"} or source.get("native_text_sparse") or not source.get("alphanumeric_count"):
        return None
    found = sum(sum(character.isalnum() for character in block.get("raw_text") or "") for block in page.get("blocks", []))
    return found / source["alphanumeric_count"]


def failed_page(page, route, settings, error):
    warning = {"code": error.code, **error.details, "page_index": page["page_index"], "route": route}
    return dict(page, extraction_state="error", extraction_route=route, routing_reason=routing_reason(page, route, settings),
                ocr_used=False, ocr_cell_count=0, blocks=[], coverage_regions=[],
                unresolved_regions=[{"bbox": None, "reason": error.code, "precision": "page"}]), warning


def _extract_window(path, version_id, first, last, settings, output_dir, preflight, session, cancel_event, fingerprint=None, revision_id=None):
    if not 0 <= first <= last < preflight["page_count"]:
        raise IngestionError("INVALID_PAGE_RANGE", "La plage de pages demandée est invalide.")
    fingerprint = fingerprint or settings.fingerprint()
    revision = revision_id or settings.extraction_revision_id or str(uuid.uuid5(uuid.NAMESPACE_URL, f"{version_id}:{preflight['sha256']}:{fingerprint}"))
    result = {"version_id": version_id, "extraction_revision_id": revision,
              "sha256": preflight["sha256"], "page_count": preflight["page_count"],
              "page_start": first, "page_end": last, "pages": [], "sections": [], "tables": [],
              "warnings": [], "pipeline_fingerprint": fingerprint, "fingerprint": fingerprint, "complete": False}
    if should_cancel(cancel_event):
        result["warnings"].append({"code": "PAUSE_REQUESTED"})
        return result
    pages = preflight["pages"][first:last + 1]
    grouped: list[tuple[Any, list[Any], IngestionError | None]] = []
    for page in pages:
        route = page_route(page, settings)
        error = None
        try:
            check_render_budget(page, route, settings)
        except IngestionError as exc:
            if not page_local(exc):
                raise
            error = exc
        # A failed page also breaks adjacency: a group range never spans it.
        if error is None and grouped and grouped[-1][0] == route and grouped[-1][2] is None:
            grouped[-1][1].append(page)
        else:
            grouped.append((route, [page], error))
    complete = True
    while grouped:
        route, selected, error = grouped.pop(0)
        render_limit = None
        if (error is not None and error.code == "PDF_RENDER_LIMIT" and settings.pipeline_route == "auto"
                and text_layer_coverage({"blocks": []}, selected[0]) is not None
                and not selected[0].get("text_mapping_warnings")):
            # Le rendu est refusé, pas la couche texte : la voie native sans modèles garde ses preuves localisées.
            render_limit = error
            _, warning = failed_page(selected[0], route, settings, error)
            result["warnings"].append(warning)
            route, error = "native", None
        if route == "blank" and error is None:
            result["pages"] += [dict(page, extraction_state="blank", ocr_used=False, ocr_cell_count=0, blocks=[], coverage_regions=[]) for page in selected]
            continue
        started = time.monotonic()
        if error is None:
            session.page_metadata.update({page["page_index"]: page for page in selected})
            try:
                document, parser_complete, observed_ocr = session.convert(path, selected[0]["page_index"], selected[-1]["page_index"], route)
            except IngestionError as exc:
                if not page_local(exc):
                    raise
                if len(selected) > 1:
                    # The failing page is unknown: convert each page alone.
                    result["warnings"].append({"code": "PAGE_GROUP_RETRIED_BY_PAGE", "cause": exc.code, "route": route,
                                               "page_start": selected[0]["page_index"], "page_end": selected[-1]["page_index"]})
                    grouped[:0] = [(route, [page], None) for page in selected]
                    continue
                error = exc
        if error is not None:
            page, warning = failed_page(selected[0], route, settings, error)
            if render_limit is not None:
                page["unresolved_regions"].append({"bbox": None, "reason": render_limit.code, "precision": "page"})
            result["pages"].append(page)
            result["warnings"].append(warning)
            complete = False
            continue
        docling_path = Path(output_dir) / f"docling-{selected[0]['page_index']:06d}-{selected[-1]['page_index']:06d}-{route}.json"
        atomic_json(docling_path, document)
        converted, warnings = document_to_pages(document, selected, version_id, revision, route, observed_ocr, settings.ocr_min_word_confidence)
        for page in converted:
            page["extraction_route"] = route
            page["routing_reason"] = routing_reason(page, route, settings)
            if route == "native":
                page["native_quality"] = native_quality(page)
                quality_passed = page["native_quality"]["passed"]
                if render_limit is not None:
                    page["routing_reason"] = "render_limit_native_fallback"
                    page["unresolved_regions"].append({"bbox": None, "reason": render_limit.code, "precision": "page"})
                    # Les colonnes et tableaux peuvent rompre l'ordre vertical ; leur structure et l'OCR restent non résolus.
                    quality_passed = page["native_quality"]["alphanumeric_coverage_ratio"] >= TEXT_COVERAGE_MIN and page["native_quality"]["localized"]
                if not quality_passed:
                    page["extraction_state"] = "error"
                    warnings.append({"code": "NATIVE_QUALITY_FAILED", "page_index": page["page_index"]})
                    if render_limit is None and settings.pipeline_route == "auto" and not should_cancel(cancel_event):
                        index = page["page_index"]
                        try:
                            check_render_budget(preflight["pages"][index], "structured", settings)
                            repaired_document, repaired_complete, repaired_ocr = session.convert(path, index, index, "structured")
                            repair_path = Path(output_dir) / f"docling-{index:06d}-{index:06d}-structured.json"
                            atomic_json(repair_path, repaired_document)
                            repaired, repair_warnings = document_to_pages(repaired_document, [preflight["pages"][index]], version_id, revision, "structured", repaired_ocr, settings.ocr_min_word_confidence)
                            prior_quality = page["native_quality"]
                            page.clear()
                            page.update(repaired[0], extraction_route="structured", routing_reason="native_quality_escalation", native_quality_before_escalation=prior_quality)
                            warnings.extend(repair_warnings)
                            warnings.append({"code": "NATIVE_ESCALATED_TO_STRUCTURED", "page_index": index})
                            parser_complete = parser_complete and repaired_complete
                        except IngestionError as exc:
                            warnings.append({"code": exc.code, "page_index": index, "component": "native_quality_escalation"})
            elif route == "structured":
                # La mise en page peut écarter presque tout le texte d'une page (listes, tableaux mal détectés) sans erreur :
                # la couche texte fiable du PDF sert de référence, puis la voie native est tentée pour cette page seule.
                index = page["page_index"]
                coverage = text_layer_coverage(page, preflight["pages"][index])
                if coverage is not None and coverage < TEXT_COVERAGE_MIN:
                    warnings.append({"code": "STRUCTURED_TEXT_LOSS", "page_index": index, "text_layer_coverage": round(coverage, 3)})
                    fallback = None
                    if not should_cancel(cancel_event):
                        try:
                            check_render_budget(preflight["pages"][index], "native", settings)
                            native_document, native_complete, native_ocr = session.convert(path, index, index, "native")
                            atomic_json(Path(output_dir) / f"docling-{index:06d}-{index:06d}-native.json", native_document)
                            candidates, native_warnings = document_to_pages(native_document, [preflight["pages"][index]], version_id, revision, "native", native_ocr, settings.ocr_min_word_confidence)
                            quality = native_quality(candidates[0])
                            # L'ordre vertical n'est pas exigé : colonnes et tableaux le rompent, et le texte complet localisé vaut mieux qu'une perte.
                            if quality["alphanumeric_coverage_ratio"] >= TEXT_COVERAGE_MIN and quality["localized"]:
                                fallback = (candidates[0], quality, native_warnings, native_complete)
                        except IngestionError as exc:
                            warnings.append({"code": exc.code, "page_index": index, "component": "structured_text_loss_fallback"})
                    if fallback:
                        candidate, quality, native_warnings, native_complete = fallback
                        page.clear()
                        page.update(candidate, extraction_route="native", routing_reason="structured_text_loss_fallback", native_quality=quality,
                                    structured_text_layer_coverage=round(coverage, 3))
                        warnings.extend(native_warnings)
                        warnings.append({"code": "STRUCTURED_FELL_BACK_TO_NATIVE", "page_index": index,
                                         "monotonic_vertical_order": quality["monotonic_vertical_order"]})
                        parser_complete = parser_complete and native_complete
                    else:
                        page.setdefault("unresolved_regions", []).append({"bbox": None, "reason": "STRUCTURED_TEXT_LOSS", "precision": "page",
                                                                           "text_layer_coverage": round(coverage, 3)})
        result["pages"] += converted
        result["warnings"] += warnings
        result.setdefault("route_metrics", []).append({"route": route, "page_start": selected[0]["page_index"], "page_end": selected[-1]["page_index"], "elapsed_seconds": time.monotonic() - started, "parser_complete": parser_complete, "artifact": docling_path.name, "lifecycle": session.last_lifecycle})
        complete = complete and parser_complete and all(page["extraction_state"] != "error" and not page.get("unresolved_regions") for page in converted)
    result["pages"].sort(key=lambda page: page["page_index"])
    result["complete"] = complete and len(result["pages"]) == last - first + 1
    return result


def extract_window(path, version_id, page_start, page_end, config, output_dir, cancel_event=None):
    settings = IngestionConfig.from_mapping(config)
    target = Path(output_dir).resolve()
    source = Path(path).resolve(strict=True)
    if target == source or source.is_relative_to(target):
        raise IngestionError("INVALID_OUTPUT_DIRECTORY", "L'extraction doit être séparée de l'original.")
    preflight = preflight_pdf(source, settings)
    with extraction_lock(target):
        result = _extract_window(source, version_id, page_start, page_end, settings, target, preflight, DoclingSession(settings), cancel_event)
        if sha256_file(source) != preflight["sha256"]:
            raise IngestionError("ORIGINAL_CHANGED", "Les octets du PDF ont changé pendant l'extraction.")
        require_conversion(result["pages"], result["warnings"], bool(result.get("route_metrics")))
        return result


# Écart de position des titres répétés et marges de page, en points PDF.
REPEATED_HEADING_TOLERANCE = 3
PAGE_EDGE_MARGIN = 100
CONTINUED_TITLE = re.compile(r"\s*\((?:suite(?: et fin)?|continued|cont\.)\)\s*$", re.IGNORECASE)


def running_header(block, page, previous_page):
    """Titre répété dans la marge haute des deux cadres PDF, pas une nouvelle section."""
    if previous_page is None or block["bbox"] is None:
        return False
    top, previous_top = page["effective_box"][3], previous_page["effective_box"][3]
    return top - PAGE_EDGE_MARGIN <= block["bbox"][1] <= block["bbox"][3] <= top and any(
        other["type"] == "heading" and other["bbox"] is not None and other["text"].split() == block["text"].split()
        and previous_top - PAGE_EDGE_MARGIN <= other["bbox"][1] <= other["bbox"][3] <= previous_top
        and all(abs(first - second) <= REPEATED_HEADING_TOLERANCE for first, second in zip(other["bbox"], block["bbox"], strict=True))
        for other in previous_page["blocks"])


def continues_section(block, section):
    """« Titre (suite) » prolonge la section ouverte par « Titre » ; tout autre titre ouvre une section."""
    marker = CONTINUED_TITLE.search(block["text"])
    return marker is not None and block["text"][:marker.start()].split() == section["title"].split()


def ends_page(block_id, page):
    """Seule la marge basse de la page (folio, pied de page) suit ce bloc."""
    following = page["blocks"][[block["id"] for block in page["blocks"]].index(block_id) + 1:]
    return all(block["bbox"] is not None and block["bbox"][3] <= page["effective_box"][1] + PAGE_EDGE_MARGIN for block in following)


def stitch_structure(pages):
    """Carry sections across checkpoints; table continuation stays evidenced."""
    sections: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    page_by_index = {page["page_index"]: page for page in pages}
    current_section = None
    previous_table = None
    for page in sorted(pages, key=lambda value: value["page_index"]):
        continued_title = None
        for position, block in enumerate(page["blocks"]):
            if block["type"] == "heading":
                if sections and continues_section(block, sections[-1]):
                    continued_title = block["id"]
                elif not running_header(block, page, page_by_index.get(page["page_index"] - 1)):
                    current_section = block["id"]
                    sections.append({"id": current_section, "title": block["text"], "page_start": page["page_index"], "page_end": page["page_index"], "block_ids": []})
            block["section_id"] = current_section
            if sections and current_section:
                sections[-1]["page_end"] = page["page_index"]
                sections[-1]["block_ids"].append(block["id"])
            if block["type"] != "table":
                continue
            block["metadata"].pop("continuation_of", None)
            table = {"id": block["id"], "page_index": page["page_index"], "section_id": current_section,
                     "bbox": block["bbox"], "data": block["metadata"]["table_data"], "continuation_of": None}
            headers = [cell["text"] for cell in table["data"].get("table_cells", []) if cell.get("column_header")]
            if previous_table:
                old_headers = [cell["text"] for cell in previous_table["data"].get("table_cells", []) if cell.get("column_header")]
                prior_page = page_by_index.get(previous_table["page_index"])
                prior_box, box = previous_table["bbox"], table["bbox"]
                at_edges = prior_box and box and prior_page and prior_box[1] <= prior_page["effective_box"][1] + PAGE_EDGE_MARGIN and box[3] >= page["effective_box"][3] - PAGE_EDGE_MARGIN
                # Sans les bords de page : le tableau précédent finit sa page et « Titre (suite) » précède immédiatement celui-ci.
                announced = position > 0 and page["blocks"][position - 1]["id"] == continued_title and prior_page and ends_page(previous_table["id"], prior_page)
                if headers and headers == old_headers and table["data"].get("num_cols") == previous_table["data"].get("num_cols") and table["page_index"] == previous_table["page_index"] + 1 and table["section_id"] == previous_table["section_id"] and (at_edges or announced):
                    table["continuation_of"] = previous_table["id"]
                    table["continuation_evidence"] = ["same_headers", "same_columns", "adjacent_pages", "same_section"] + (["page_boundary_positions"] if at_edges else ["previous_table_ends_page", "continued_title"])
                    block["metadata"]["continuation_of"] = previous_table["id"]
            tables.append(table)
            previous_table = table
    return sections, tables


def extract_pdf(path, output_dir, config, version_id, cancel_path=None):
    settings = IngestionConfig.from_mapping(config)
    source = Path(path).resolve(strict=True)
    target = Path(output_dir).resolve()
    if target == source or source.is_relative_to(target):
        raise IngestionError("INVALID_OUTPUT_DIRECTORY", "L'extraction doit être séparée de l'original.")
    fingerprint = settings.fingerprint()
    with extraction_lock(target):
        preflight_path = target / "preflight.json"
        preflight = preflight_pdf(source, settings)
        atomic_json(preflight_path, preflight)
        revision = settings.extraction_revision_id or str(uuid.uuid5(uuid.NAMESPACE_URL, f"{version_id}:{preflight['sha256']}:{fingerprint}"))
        identity = {"source_sha256": preflight["sha256"], "pipeline_fingerprint": fingerprint, "version_id": version_id, "extraction_revision_id": revision}
        store = CheckpointStore(target, identity)
        session = DoclingSession(settings)
        pages, warnings, windows = [], [], []
        interrupted = converted = False
        for first in range(0, preflight["page_count"], settings.page_window_size):
            if should_cancel(cancel_path):
                interrupted = True
                break
            last = min(preflight["page_count"] - 1, first + settings.page_window_size - 1)
            window = store.read(first, last)
            # Un échec de conversion peut être transitoire (mémoire, faute du parseur) :
            # sa fenêtre reste écrite (progression, preuve) mais une reprise la reconvertit.
            if window is not None and conversion_failures(window["pages"]):
                window = None
            reused = window is not None
            if window is None:
                window = _extract_window(source, version_id, first, last, settings, target, preflight, session, cancel_path, fingerprint, revision)
                if len(window["pages"]) != last - first + 1:
                    interrupted = True
                    break
                store.write(window)
            converted = converted or bool(window.get("route_metrics"))
            pages += window["pages"]
            warnings += window["warnings"]
            # Parseur complet : toutes ses conversions de la fenêtre ont réussi sans « partial_success » (W012).
            windows.append({"page_start": first, "page_end": last, "reused": reused, "complete": window["complete"],
                            "parser_complete": all(metric.get("parser_complete") is True for metric in window.get("route_metrics", []))})
        if sha256_file(source) != preflight["sha256"]:
            raise IngestionError("ORIGINAL_CHANGED", "Les octets du PDF ont changé pendant l'extraction.")
        if not interrupted:
            require_conversion(pages, warnings, converted)
        sections, tables = stitch_structure(pages)
        if not interrupted and not any(block["text"].strip() for page in pages for block in page["blocks"]):
            warnings.append({"code": "DOCUMENT_WITHOUT_TEXT", "page_count": preflight["page_count"],
                             "blank_pages": sum(page["extraction_state"] == "blank" for page in pages),
                             "error_pages": sum(page["extraction_state"] == "error" for page in pages)})
        partial = len(pages) != preflight["page_count"] or any(page["extraction_state"] == "error" for page in pages) or any(not window["complete"] for window in windows)
        result = {"version_id": version_id, "extraction_revision_id": revision, "sha256": preflight["sha256"],
                  "fingerprint": fingerprint, "pipeline_fingerprint": fingerprint, "page_count": preflight["page_count"],
                  "status": "interrupted" if interrupted else "ready_partial" if partial else "ready",
                  "pages": pages, "sections": sections, "tables": tables, "warnings": warnings,
                  "coverage": {"total": preflight["page_count"], "processed": len(pages), "ocr": sum(page.get("ocr_used", False) for page in pages),
                               "unresolved": sum(page["extraction_state"] == "error" or bool(page.get("unresolved_regions")) for page in pages),
                               "unresolved_regions": sum(len(page.get("unresolved_regions", [])) for page in pages)},
                  "windows": windows, "parser_complete": all(window["parser_complete"] for window in windows)}
        atomic_json(target / "extraction.json", result)
        return result
