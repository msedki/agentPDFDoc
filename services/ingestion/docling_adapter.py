"""The sole Docling adapter; imported by the isolated extraction process only."""

import gc
import hashlib
import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

from .config import OCR_RENDER_SCALE, IngestionConfig, project_path
from .errors import IngestionError
from .geometry import docling_box_to_pdf


def verify_tesseract(config: IngestionConfig):
    if config.tessdata_path:
        tsv_config = project_path(config.tessdata_path) / "configs" / "tsv"
        if not tsv_config.is_file() or "tessedit_create_tsv 1" not in tsv_config.read_text(encoding="utf-8"):
            raise IngestionError("OCR_CONFIG_MISSING", "Le fichier de configuration TSV Tesseract local est absent ou invalide.")
    command = [config.resolved_tesseract_cmd, "--list-langs"]
    if config.tessdata_path:
        command += ["--tessdata-dir", str(project_path(config.tessdata_path).resolve())]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
    except (OSError, subprocess.TimeoutExpired):
        raise IngestionError("TESSERACT_UNAVAILABLE", "Le binaire OCR local est absent ou ne répond pas.") from None
    installed = set(result.stdout.splitlines()[1:])
    missing = (set(config.ocr_languages) | {"osd"}) - installed
    if result.returncode or missing:
        raise IngestionError("OCR_LANGUAGE_MISSING", "Les langues OCR requises ne sont pas provisionnées.", {"missing_languages": sorted(missing)})


class DoclingSession:
    """Reuse one compatible converter within a bounded extraction session."""
    def __init__(self, config: IngestionConfig):
        self.config = config
        self._converter = None
        self._route = None
        self.last_lifecycle = {}
        self.page_metadata = {}

    def converter(self, route):
        if self._converter is not None and self._route == route:
            return self._converter
        self._converter = None
        from .lifecycle import lifecycle_event

        lifecycle_event("converter_gc_start")
        gc.collect()
        lifecycle_event("converter_gc_end")
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                AcceleratorDevice,
                AcceleratorOptions,
                PdfPipelineOptions,
                TableFormerMode,
                TesseractCliOcrOptions,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError:
            raise IngestionError("DOCLING_MISSING", "Le runtime Docling compatible est absent.") from None
        from .lifecycle import draining_backend_class, observed_pdfium_backend_class

        backend = observed_pdfium_backend_class() if self.config.pdf_backend == "pypdfium2" else draining_backend_class()
        if route == "native":
            try:
                from docling.datamodel.pipeline_options import NativePdfPipelineOptions
                from docling.document_converter import NativePdfFormatOption
            except ImportError:
                raise IngestionError("NATIVE_PIPELINE_UNAVAILABLE", "La voie Docling native n'est pas disponible dans la version installée.") from None
            options = NativePdfPipelineOptions(parser_threads=self.config.parser_threads, generate_page_images=False, generate_picture_images=False)
            format_option = NativePdfFormatOption(pipeline_options=options, backend=backend)
        else:
            from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions

            backend_options = ThreadedDoclingParseBackendOptions(parser_threads=self.config.parser_threads)
            if not self.config.artifacts_path or not project_path(self.config.artifacts_path).is_dir():
                raise IngestionError("DOCLING_ARTIFACTS_MISSING", "Les artefacts Docling locaux sont absents.")
            options = PdfPipelineOptions(
                artifacts_path=project_path(self.config.artifacts_path).resolve(),
                accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=self.config.threads_max),
                enable_remote_services=False, do_ocr=route == "regional_ocr", do_table_structure=True,
                generate_page_images=False, generate_picture_images=False,
                generate_parsed_pages=True,
                do_picture_description=False,
            )
            options.table_structure_options.mode = TableFormerMode.ACCURATE
            if route == "regional_ocr":
                verify_tesseract(self.config)
                keywords = {"lang": list(self.config.ocr_languages), "tesseract_cmd": self.config.resolved_tesseract_cmd, "scale": OCR_RENDER_SCALE}
                if self.config.tessdata_path:
                    keywords["path"] = str(project_path(self.config.tessdata_path).resolve())
                fields = TesseractCliOcrOptions.model_fields
                if "mode" in fields:
                    from docling.datamodel.pipeline_options import OcrMode
                    keywords["mode"] = OcrMode.PDF_AWARE_LAYOUT_REGIONS
                else:
                    raise IngestionError("DOCLING_OCR_MODE_UNAVAILABLE", "La version Docling ne supporte pas l'OCR régional PDF-aware demandé.")
                options.ocr_options = TesseractCliOcrOptions(**keywords)
            if route == "regional_ocr":
                from .regional_grid import regional_pipeline_class
                oversample = 1.5 if self.config.pdf_backend == "pypdfium2" else 1.0
                format_option = PdfFormatOption(pipeline_options=options,
                                               pipeline_cls=regional_pipeline_class(self.config.max_ocr_region_pixels, oversample,
                                                                                    self.page_metadata, self.config.ocr_intrinsic_aspect,
                                                                                    self.config.ocr_cell_border, self.config.ocr_min_word_confidence),
                                               backend_options=backend_options, backend=backend)
            else:
                format_option = PdfFormatOption(pipeline_options=options, backend_options=backend_options, backend=backend)
        self._converter = DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={InputFormat.PDF: format_option})
        self._route = route
        return self._converter

    def convert(self, path, first, last, route):
        previous = os.environ.get("TESSDATA_PREFIX")
        if route == "regional_ocr" and self.config.tessdata_path:
            # Docling 2.131 passes options.path during OCR but omits it from
            # the language inventory and OSD subprocesses. This worker-local
            # environment covers those probes without changing the machine.
            os.environ["TESSDATA_PREFIX"] = str(project_path(self.config.tessdata_path).resolve())
        try:
            return self._convert(path, first, last, route)
        finally:
            if previous is None:
                os.environ.pop("TESSDATA_PREFIX", None)
            else:
                os.environ["TESSDATA_PREFIX"] = previous

    def _convert(self, path, first, last, route):
        converter = self.converter(route)
        from .lifecycle import lifecycle_event

        lifecycle_event("conversion_start", converter_instance=id(converter), page_range=[first + 1, last + 1], route=route)
        try:
            result = converter.convert(Path(path), page_range=(first + 1, last + 1), raises_on_error=False,
                                       max_file_size=int(self.config.max_file_mib * 1024 * 1024),
                                       max_num_pages=self.config.max_document_pages)
            fault_path = os.environ.get("RAG_NATIVE_FAULT_LOG")
            if fault_path and Path(fault_path).stat().st_size > int(os.environ.get("RAG_NATIVE_FAULT_START", "0")):
                raise IngestionError("INGESTION_NATIVE_FAULT", "Une exception native a été observée ; l'extraction ne peut pas être publiée.", {"fault_log": Path(fault_path).name})
            remaining = sorted(thread.name for thread in threading.enumerate() if thread.name.startswith(("Stage-", "PageProducer-")))
            pipeline = converter._get_pipeline(result.input.format)
            backend = result.input._backend
            self.last_lifecycle = {"remaining_stage_threads": remaining,
                                   "converter_instance": id(converter), "pipeline_instance": id(pipeline),
                                   "backend": getattr(backend, "lifecycle", {})}
            lifecycle_event("conversion_end", **self.last_lifecycle)
            if remaining:
                raise IngestionError("DOCLING_THREADS_STILL_ACTIVE", "Les threads du parseur ne sont pas tous libérés ; la conversion ne peut pas être publiée.", {"stage_threads": remaining})
            status = str(result.status.value)
            if status not in {"success", "partial_success"}:
                raise IngestionError("DOCLING_CONVERSION_FAILED", "Docling n'a pas produit une extraction utilisable.", {"page_start": first, "page_end": last, "parser_status": status})
            document = result.document.export_to_dict()
            observed_ocr = {}
            preprocessing = {}
            orientations = {}
            table_corrections = {}
            isolation_failures = {}
            if route == "regional_ocr":
                pipeline = converter._get_pipeline(result.input.format)
                preprocessing = getattr(pipeline.ocr_model, "region_preprocessing_by_page", {})
                orientations = getattr(pipeline.ocr_model, "region_orientations_by_page", {})
                table_corrections = getattr(pipeline.table_model, "corrections_by_page", {})
                isolation_failures = getattr(pipeline.ocr_model, "isolation_failures_by_page", {})
            for parsed_page in result.pages:
                page_no = int(parsed_page.page_no)
                known_pages = {int(key) for key in document.get("pages", {})}
                if page_no not in known_pages and page_no + 1 in known_pages:
                    page_no += 1
                cells = [{"text": cell.text, "from_ocr": bool(getattr(cell, "from_ocr", False)), "bbox": cell.rect.to_bounding_box().model_dump(mode="json")} for cell in parsed_page.cells]
                ocr_cells = [cell for cell in cells if cell["from_ocr"]]
                observed_ocr[page_no - 1] = {"cell_count": len(ocr_cells), "regions": [cell["bbox"] for cell in ocr_cells], "cells": cells,
                                          "preprocessing": preprocessing.get(int(parsed_page.page_no), [])}
                observed_ocr[page_no - 1]["orientations"] = orientations.get(int(parsed_page.page_no), [])
                observed_ocr[page_no - 1]["table_orientation_corrections"] = table_corrections.get(int(parsed_page.page_no), [])
                observed_ocr[page_no - 1]["isolation_failures"] = isolation_failures.get(int(parsed_page.page_no), [])
            return document, status == "success", observed_ocr
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("DOCLING_CONVERSION_FAILED", "La conversion Docling a échoué.", {"page_start": first, "page_end": last, "exception_type": type(exc).__name__}) from None


def stable_id(version_id, revision_id, page_index, item_ref, text, bbox):
    value = json.dumps([version_id, revision_id, page_index, item_ref, text, bbox], ensure_ascii=False, sort_keys=True)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def table_text(data):
    """Serialize an actual table grid with explicit cell coordinates/spans."""
    cells = data.get("table_cells", [])
    rows = {}
    for cell in cells:
        row, column = int(cell.get("start_row_offset_idx", 0)), int(cell.get("start_col_offset_idx", 0))
        rows.setdefault(row, []).append((column, str(cell.get("text", ""))))
    return "\n".join(" | ".join(text for _, text in sorted(rows[row])) for row in sorted(rows))


def canonical_cells(document, pages, observed_ocr, warnings):
    result = {}
    for index, page in pages.items():
        parser_page = document.get("pages", {}).get(str(index + 1), document.get("pages", {}).get(index + 1, {}))
        size = parser_page.get("size", {})
        converted = []
        if "width" not in size or "height" not in size:
            result[index] = converted
            continue
        for cell in (observed_ocr or {}).get(index, {}).get("cells", []):
            try:
                bbox = docling_box_to_pdf(cell["bbox"], (size["width"], size["height"]), page)
            except IngestionError as exc:
                warnings.append({"code": exc.code, "page_index": index, "component": "parser_cell"})
                continue
            converted.append({"text": cell.get("text", ""), "bbox": bbox, "from_ocr": bool(cell.get("from_ocr"))})
        result[index] = converted
    return result


def cell_belongs_to_block(cell, bbox):
    if bbox is None:
        return False
    region = cell["bbox"]
    area = max(0, region[2] - region[0]) * max(0, region[3] - region[1])
    intersection = max(0, min(region[2], bbox[2]) - max(region[0], bbox[0])) * max(0, min(region[3], bbox[3]) - max(region[1], bbox[1]))
    return area > 0 and intersection / area >= 0.5


def source_method(cells, route):
    if not cells:
        return "unknown" if route == "regional_ocr" else "native"
    origins = {cell["from_ocr"] for cell in cells}
    return "mixed" if len(origins) == 2 else "ocr" if True in origins else "native"


def ocr_spans(text, cells):
    """Only map an exact, unique source substring; no normalized offsets."""
    spans = []
    for cell in cells:
        value = cell["text"]
        if not cell["from_ocr"] or not value or text.count(value) != 1:
            continue
        start = text.index(value)
        spans.append({"start_offset": start, "end_offset": start + len(value), "bbox": cell["bbox"], "precision": "span"})
    return sorted(spans, key=lambda span: (span["start_offset"], span["end_offset"]))


def table_coverage(data, bbox, parser_size, page):
    """Expose suspicious structure without claiming unseen cells are empty."""
    canonical = []
    cells = data.get("table_cells", [])
    for cell in cells:
        region = None
        if cell.get("bbox"):
            try:
                region = docling_box_to_pdf(cell["bbox"], parser_size, page)
            except IngestionError:
                pass
        canonical.append({"row": cell.get("start_row_offset_idx"), "column": cell.get("start_col_offset_idx"),
                          "row_span": cell.get("row_span", 1), "col_span": cell.get("col_span", 1),
                          "text": cell.get("text", ""), "bbox": region})
    occupied = [cell["bbox"] for cell in canonical if cell["text"].strip() and cell["bbox"]]
    warnings = []
    if bbox and occupied:
        text_left, text_right = min(box[0] for box in occupied), max(box[2] for box in occupied)
        table_width = bbox[2] - bbox[0]
        only_row_headers = bool(cells) and all(cell.get("row_header", False) for cell in cells if cell.get("text", "").strip())
        if data.get("num_cols") == 1 and data.get("num_rows", 0) >= 2 and only_row_headers and table_width > max(1, text_right - text_left) * 2.5 and text_right < bbox[0] + table_width * 0.6:
            warnings.append("TABLE_CONTENT_COVERAGE_UNCERTAIN")
    if not cells or data.get("num_cols", 0) == 0:
        warnings.append("TABLE_WITHOUT_RELIABLE_CELLS")
    return canonical, warnings


def document_to_pages(document, preflight_pages, version_id, revision_id, route, observed_ocr=None):
    pages = {page["page_index"]: dict(page, blocks=[], extraction_state="ocr" if route == "regional_ocr" else "native", ocr_used=False, coverage_regions=[], unresolved_regions=[]) for page in preflight_pages}
    warnings = []
    for page in pages.values():
        warnings.extend({"code": code, "page_index": page["page_index"], "component": "preflight_text"} for code in page.get("text_mapping_warnings", []))
    cells_by_page = canonical_cells(document, pages, observed_ocr, warnings)
    all_items = {}
    for group in ("texts", "tables", "pictures", "groups"):
        for item in document.get(group, []):
            all_items[item.get("self_ref", "")] = item

    def ordered_items():
        visited = set()
        def walk(item):
            ref = item.get("self_ref")
            if ref in visited:
                return
            visited.add(ref)
            if "prov" in item:
                yield item
            for child in item.get("children", []):
                linked = all_items.get(child.get("$ref"))
                if linked:
                    yield from walk(linked)
        yield from walk(document.get("body", {}))
        for item in all_items.values():
            if item.get("self_ref") not in visited:
                yield from walk(item)

    for item in ordered_items():
        label = str(item.get("label", "text"))
        kind = "heading" if label in {"title", "section_header"} else "table" if label == "table" else "figure" if label == "picture" else "caption" if label == "caption" else "text"
        original_text = item.get("orig")
        text = (original_text if isinstance(original_text, str) else str(item.get("text", ""))) if kind != "table" else table_text(item.get("data", {}))
        for provenance in item.get("prov", []):
            index = int(provenance["page_no"]) - 1
            if index not in pages:
                raise IngestionError("DOCLING_PAGE_RANGE_MISMATCH", "Docling a retourné une page hors de la fenêtre demandée.", {"page_index": index})
            page = pages[index]
            parser_page = document.get("pages", {}).get(str(index + 1), document.get("pages", {}).get(index + 1, {}))
            size = parser_page.get("size", {})
            bbox = None
            if provenance.get("bbox") and "width" in size and "height" in size:
                try:
                    bbox = docling_box_to_pdf(provenance["bbox"], (size["width"], size["height"]), page)
                except IngestionError as exc:
                    warnings.append({"code": exc.code, "page_index": index})
            charspan = provenance.get("charspan")
            source_text = text
            if charspan and kind not in {"table", "figure"}:
                start, end = int(charspan[0]), int(charspan[1])
                if 0 <= start <= end <= len(text):
                    source_text = text[start:end]
                else:
                    warnings.append({"code": "INVALID_SOURCE_CHARSPAN", "page_index": index})
                    page["source_provenance_incomplete"] = True
                    continue
            block_cells = [cell for cell in cells_by_page[index] if cell_belongs_to_block(cell, bbox)]
            extraction_method = source_method(block_cells, route)
            identity = stable_id(version_id, revision_id, index, item.get("self_ref"), source_text, bbox)
            block = {"id": identity, "version_id": version_id, "extraction_revision_id": revision_id,
                     "page_index": index, "type": kind, "kind": kind, "text": source_text, "raw_text": source_text,
                     "text_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                     "source_text_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                     "bbox": bbox, "precision": "table" if bbox and kind == "table" else "block" if bbox else "page",
                     "section_id": None, "parser_provenance": provenance,
                     "spans": [{"start_offset": 0, "end_offset": len(source_text), "bbox": bbox, "precision": "block" if bbox else "page"}],
                     "metadata": {"label": label, "parser_ref": item.get("self_ref"), "route": route,
                                  "extraction_method": extraction_method, "ocr_used": extraction_method in {"ocr", "mixed"},
                                  "ocr_spans": ocr_spans(source_text, block_cells)}}
            if kind == "table":
                block["metadata"]["table_data"] = item.get("data", {})
                canonical, table_warnings = table_coverage(item.get("data", {}), bbox, (size.get("width", 0), size.get("height", 0)), page)
                block["metadata"]["table_cell_regions"] = canonical
                for code in table_warnings:
                    warnings.append({"code": code, "page_index": index, "block_id": identity})
                    page["unresolved_regions"].append({"bbox": bbox, "block_id": identity, "reason": code, "precision": "table" if bbox else "page"})
            if kind == "figure":
                warnings.append({"code": "GRAPHIC_INTERPRETATION_UNAVAILABLE", "page_index": index, "block_id": identity})
                page["unresolved_regions"].append({"bbox": bbox, "block_id": identity, "reason": "GRAPHIC_INTERPRETATION_UNAVAILABLE", "precision": "block" if bbox else "page"})
            page["blocks"].append(block)
            page["coverage_regions"].append({"block_id": identity, "bbox": bbox, "route": route, "type": kind, "extraction_method": extraction_method})
        if not item.get("prov") and text.strip():
            warnings.append({"code": "ITEM_WITHOUT_PROVENANCE"})
    for page in pages.values():
        if page["classification"] == "blank":
            page["extraction_state"] = "blank"
        elif not any(block["text"].strip() for block in page["blocks"]):
            page["extraction_state"] = "error"
            warnings.append({"code": "PAGE_WITHOUT_EXTRACTED_TEXT", "page_index": page["page_index"]})
        ocr = (observed_ocr or {}).get(page["page_index"], {})
        page["ocr_used"] = ocr.get("cell_count", 0) > 0
        page["ocr_cell_count"] = ocr.get("cell_count", 0)
        page["ocr_parser_regions"] = ocr.get("regions", [])
        page["ocr_preprocessing"] = ocr.get("preprocessing", [])
        page["ocr_orientations"] = ocr.get("orientations", [])
        page["table_orientation_corrections"] = ocr.get("table_orientation_corrections", [])
        if page["classification"] in {"native", "mixed"}:
            page["orientation_correction"] = 0
            page["orientation_source"] = "native_page_frame"
        elif page["classification"] == "scan_candidate" and page["ocr_orientations"] and all(record.get("resolved") for record in page["ocr_orientations"]):
            angles = {record["orientation_degrees"] for record in page["ocr_orientations"]}
            if len(angles) == 1:
                page["orientation_correction"] = next(iter(angles))
                page["orientation_source"] = "regional_osd_consensus"
        unresolved = list(ocr.get("isolation_failures", []))
        for preprocessing in page["ocr_preprocessing"]:
            unresolved.extend({"code": "OCR_PRINTED_CELL_UNRESOLVED", "parser_bbox": cell["unresolved_parser_bbox"]}
                              for cell in preprocessing.get("cell_ocr", []) if "unresolved_parser_bbox" in cell)
            unresolved.extend({"code": "OCR_CELL_LOW_CONFIDENCE", "parser_bbox": cell["uncertain_parser_bbox"]}
                              for cell in preprocessing.get("cell_ocr", []) if "uncertain_parser_bbox" in cell)
        unresolved.extend({"code": "OCR_ORIENTATION_UNRESOLVED", "parser_bbox": orientation["parser_bbox"]}
                          for orientation in page["ocr_orientations"] if not orientation.get("resolved"))
        for region_failure in unresolved:
            warning = {"code": region_failure["code"], "page_index": page["page_index"]}
            warnings.append(warning)
            region = None
            try:
                parser_page = document.get("pages", {}).get(str(page["page_index"] + 1), {})
                size = parser_page["size"]
                region = docling_box_to_pdf(region_failure["parser_bbox"], (size["width"], size["height"]), page)
            except (KeyError, IngestionError):
                pass
            page["unresolved_regions"].append({"bbox": region, "reason": warning["code"], "precision": "block" if region else "page"})
        page["ocr_regions"] = [cell["bbox"] for cell in cells_by_page[page["page_index"]] if cell["from_ocr"]]
        if page.get("source_provenance_incomplete"):
            page["extraction_state"] = "error"
        if route == "regional_ocr" and page["classification"] in {"scan_candidate", "degraded"} and not page["ocr_used"]:
            warnings.append({"code": "OCR_NO_RECOGNIZED_CELLS", "page_index": page["page_index"]})
            page["extraction_state"] = "error"
        if route == "regional_ocr" and not page["ocr_used"] and page["extraction_state"] != "error":
            page["extraction_state"] = "native"
    return list(pages.values()), warnings
