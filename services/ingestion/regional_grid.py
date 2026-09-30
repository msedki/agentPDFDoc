"""Same-frame ruled-table OCR preprocessing, without changing the PDF."""

import hashlib
import math
from contextlib import contextmanager
from typing import Any


@contextmanager
def temporary_raster(image):
    """Clean the private PNG even when its encoder fails before OCR starts."""
    import tempfile
    from pathlib import Path

    target = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as stream:
            target = Path(stream.name)
            image.save(stream, format="PNG")
        yield str(target)
    finally:
        if target is not None:
            target.unlink(missing_ok=True)


def read_tesseract_tsv(data):
    """Keep recognized source tokens literal, including numbers and NA labels."""
    import csv
    import io

    import pandas as pd

    frame = pd.read_csv(io.StringIO(data), quoting=csv.QUOTE_NONE, sep="\t",
                        dtype={"text": str}, keep_default_na=False)
    return frame[frame["text"].str.strip() != ""].copy()


def bounded_cell_crop(image, bounds, border=10, edge=4):
    """Remove oversized blank margins and retain an explicit raster offset.

    Ink components lying entirely within `edge` pixels of the cell frame are
    residues of removed rules: counted as ink, they widen the crop back to the
    whole cell (E1, cells V/°C/A). A glyph reaching that band is kept whole.
    """
    import numpy as np
    from PIL import ImageOps
    from scipy.ndimage import label

    crop = image.crop(tuple(bounds)).convert("RGB")
    dark = np.asarray(crop.convert("L")) < 128
    height, width = dark.shape
    edge = max(0, min(edge, (min(height, width) - 1) // 2))
    labels, count = label(dark, structure=np.ones((3, 3), dtype=bool))
    interior = np.zeros_like(dark)
    interior[edge:height - edge, edge:width - edge] = True
    content = np.flatnonzero(np.bincount(labels[interior], minlength=count + 1)[1:]) + 1
    kept = np.isin(labels, content)
    rows, columns = np.flatnonzero(kept.any(axis=1)), np.flatnonzero(kept.any(axis=0))
    if not rows.size:
        return None, None
    ink = (int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1)
    patch = ImageOps.expand(crop.crop(ink), border=border, fill="white")
    offset = (bounds[0] + ink[0] - border, bounds[1] + ink[1] - border)
    return patch, offset


def subtract_native_regions(region, obstacles, limit=128):
    """Partition an OCR rectangle around reliable native ink in the same frame."""
    fragments = [region]
    for obstacle in obstacles:
        next_fragments = []
        for left, top, right, bottom in fragments:
            cut_left, cut_top = max(left, obstacle[0]), max(top, obstacle[1])
            cut_right, cut_bottom = min(right, obstacle[2]), min(bottom, obstacle[3])
            if cut_right <= cut_left or cut_bottom <= cut_top:
                next_fragments.append([left, top, right, bottom])
                continue
            candidates = ([left, top, right, cut_top], [left, cut_bottom, right, bottom],
                          [left, cut_top, cut_left, cut_bottom], [cut_right, cut_top, right, cut_bottom])
            next_fragments.extend(box for box in candidates if box[2] > box[0] and box[3] > box[1])
        if len(next_fragments) > limit:
            return [], True
        fragments = next_fragments
    return fragments, False


def _rule_positions(indices):
    groups: list[list[int]]
    groups, previous = [], -2
    for index in indices:
        if index != previous + 1:
            groups.append([])
        groups[-1].append(int(index))
        previous = index
    return [group[len(group) // 2] for group in groups]


def remove_ruled_grid(image):
    """Remove only long crossing rules; preserve size and every text coordinate.

    Plain paragraphs, isolated underlines and charts without a rectangular grid
    are left untouched. The result is an OCR derivative, never an original.
    """
    import numpy as np
    from PIL import Image
    from scipy.ndimage import binary_opening

    original = image.convert("RGB")
    binary = np.asarray(original.convert("L")) < 128
    horizontal = binary_opening(binary, structure=np.ones((1, max(80, image.width // 8)), dtype=bool))
    vertical = binary_opening(binary, structure=np.ones((max(80, image.height // 8), 1), dtype=bool))
    row_lines = _rule_positions(np.flatnonzero(horizontal.sum(axis=1) >= max(80, image.width // 4)))
    column_lines = _rule_positions(np.flatnonzero(vertical.sum(axis=0) >= max(80, image.height // 4)))
    horizontal_count, vertical_count = len(row_lines), len(column_lines)
    intersections = int((horizontal & vertical).sum())
    if horizontal_count < 2 or vertical_count < 2 or intersections < 4:
        return original, None
    pixels = np.asarray(original).copy()
    mask = horizontal | vertical
    pixels[mask] = 255
    derived = Image.fromarray(pixels)
    rectangular = all(horizontal[y, column_lines[0]:column_lines[-1] + 1].mean() >= .95 for y in row_lines) and all(vertical[row_lines[0]:row_lines[-1] + 1, x].mean() >= .95 for x in column_lines)
    grid_cells = [[left + 2, top + 2, right - 2, bottom - 2]
                  for top, bottom in zip(row_lines, row_lines[1:], strict=False)
                  for left, right in zip(column_lines, column_lines[1:], strict=False)] if rectangular else []
    return derived, {"algorithm": "crossing-rules-v2", "width": image.width, "height": image.height,
                     "horizontal_rules": horizontal_count, "vertical_rules": vertical_count,
                     "rectangular_grid": rectangular, "grid_cells": grid_cells,
                     "removed_pixels": int(mask.sum()), "source_raster_sha256": hashlib.sha256(original.tobytes()).hexdigest(),
                     "derived_raster_sha256": hashlib.sha256(derived.tobytes()).hexdigest()}


def regional_pipeline_class(max_region_pixels=8_000_000, render_oversample=1.0,
                            page_metadata=None, intrinsic_aspect=False, cell_border=False, minimum_confidence=None):
    """Version-pinned Docling extension loaded only inside the PDF worker."""
    from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from PIL import Image

    from .errors import IngestionError
    from .preflight import rendered_pixels
    from .regional_aspect import (
        complete_bitmap_pixel_size,
        inverse_resized_box,
        oriented_resize,
        reduced_aspect_size,
    )

    class GridAwareTesseract(TesseractOcrCliModel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.region_preprocessing_by_page = {}
            self.region_orientations_by_page = {}
            self.isolation_failures_by_page = {}
            self._current_preprocessing = []
            self._current_orientations = []

        def get_ocr_rects(self, page):
            from docling_core.types.doc import BoundingBox, CoordOrigin

            # Layout fragments of sideways tables can be too small for OSD.
            # Expand only to an actual bitmap with no overlapping native text.
            rects = super().get_ocr_rects(page)
            native = page._backend.get_visible_text_cells()
            native = list(page._backend.get_text_cells() if native is None else native)
            native_boxes = [cell.rect.to_bounding_box().to_top_left_origin(page.size.height) for cell in native]
            for bitmap in page._backend.get_bitmap_rects():
                bitmap = bitmap.to_top_left_origin(page.size.height)
                frame = BoundingBox(l=0, t=0, r=page.size.width, b=page.size.height, coord_origin=CoordOrigin.TOPLEFT)
                bitmap = bitmap.get_intersection_bbox(frame)
                if bitmap is None:
                    continue
                if any(box.intersection_over_self(bitmap) > 0 for box in native_boxes):
                    continue
                contained = [region for region in rects if region.intersection_over_self(bitmap) >= .5]
                if contained:
                    rects = [region for region in rects if region not in contained] + [bitmap]
            isolated: list[BoundingBox] = []
            failures = []
            obstacles = [[box.l - 1, box.t - 1, box.r + 1, box.b + 1] for box in native_boxes]
            for region in rects:
                fragments, failed = subtract_native_regions([region.l, region.t, region.r, region.b], obstacles)
                if failed:
                    failures.append({"code": "OCR_REGION_ISOLATION_LIMIT", "parser_bbox": region.model_dump(mode="json")})
                isolated.extend(BoundingBox(l=box[0], t=box[1], r=box[2], b=box[3], coord_origin=CoordOrigin.TOPLEFT) for box in fragments)
            rects = isolated
            self.isolation_failures_by_page[int(page.page_no)] = failures
            for region in rects:
                pixels = rendered_pixels(region.r - region.l, region.b - region.t, self.scale * render_oversample)
                if pixels > max_region_pixels:
                    raise IngestionError("OCR_RENDER_LIMIT", "Cette région dépasse le plafond de pixels OCR.", {"render_pixels": pixels, "pixel_limit": max_region_pixels})
            self._current_rects = rects
            return rects

        def __call__(self, conv_res, page_batch):
            for page in page_batch:
                self._current_page_metadata = (page_metadata or {}).get(int(page.page_no) - 1, {})
                self._current_preprocessing = []
                self._current_orientations = []
                yield from super().__call__(conv_res, [page])
                self.region_preprocessing_by_page[int(page.page_no)] = self._current_preprocessing
                self.region_orientations_by_page[int(page.page_no)] = self._current_orientations

        def _perform_osd(self, ifilename):
            import subprocess

            from docling.models.stages.ocr.tesseract_ocr_cli_model import _parse_orientation

            region_index = len(self._current_orientations)
            record: dict[str, Any] = {"parser_bbox": self._current_rects[region_index].model_dump(mode="json"), "resolved": False}
            self._current_orientations.append(record)
            with Image.open(ifilename) as image:
                source = image.convert("RGB")
            pixels = complete_bitmap_pixel_size(record["parser_bbox"], self._current_page_metadata) if intrinsic_aspect else None
            target_size = reduced_aspect_size(source.size, pixels)
            record.update(source_raster_size=list(source.size), derivative_raster_size=list(target_size),
                          intrinsic_pixel_size=list(pixels) if pixels else None)
            derived = source.resize(target_size, Image.Resampling.LANCZOS) if target_size != source.size else source
            if intrinsic_aspect:
                derived = remove_ruled_grid(derived)[0]
            record["osd_raster_sha256"] = hashlib.sha256(derived.tobytes()).hexdigest()
            try:
                with temporary_raster(derived) as target:
                    result = super()._perform_osd(target)
                record["orientation_degrees"] = _parse_orientation(result)
                record["orientation_convention"] = "counterclockwise_from_upright"
                record["correction_degrees_pil"] = -record["orientation_degrees"]
                record["resolved"] = True
                return result
            except subprocess.CalledProcessError:
                raise

        def _run_literal_tsv(self, filename, osd=None, psm=None):
            import subprocess

            command = [self._safe_tesseract_cmd]
            if self._auto_script and osd is not None:
                language = self._parse_language(osd)
                if language is not None:
                    command += ["-l", self._sanitize_lang(language)]
            elif self._native_codes:
                command += ["-l", "+".join(self._native_codes)]
            if self._safe_tessdata_path:
                command += ["--tessdata-dir", self._safe_tessdata_path]
            segmentation = self.options.psm if psm is None else psm
            if segmentation is not None:
                command += ["--psm", str(int(segmentation))]
            command += [self._sanitize_filename(filename), "stdout", "tsv"]
            result = subprocess.run(command, capture_output=True, check=True, shell=False,
                                    stdin=subprocess.DEVNULL, timeout=30)
            return read_tesseract_tsv(result.stdout.decode("utf-8"))

        def _cell_ocr(self, image, bounds):
            patch, offset = bounded_cell_crop(image, bounds) if cell_border else (image.crop(tuple(bounds)), tuple(bounds[:2]))
            if patch is None:
                # Only rule residue: nothing recognized, the printed cell stays unresolved.
                self._last_cell_crop: dict[str, Any] = {"policy": "ink_border_10", "raster_offset": None, "raster_size": None, "ink": "edge_residue_only"}
                return None
            self._last_cell_crop = {"policy": "ink_border_10" if cell_border else "full_grid_cell", "raster_offset": list(offset), "raster_size": list(patch.size)}
            with temporary_raster(patch) as target:
                frame = self._run_literal_tsv(target, psm=6)
                frame["left"] += offset[0]
                frame["top"] += offset[1]
                return frame

        def _run_tesseract(self, ifilename, osd):
            region_index = len(self._current_orientations) - 1
            orientation = self._current_orientations[region_index]
            angle = orientation.get("orientation_degrees", 0)
            with Image.open(ifilename) as image:
                source_size = image.size
                expected_source_size, target_size = oriented_resize(tuple(orientation["source_raster_size"]), tuple(orientation["derivative_raster_size"]), angle)
                if expected_source_size != source_size:
                    raise IngestionError("OCR_RASTER_FRAME_MISMATCH", "Le raster OCR du parent ne correspond pas au repère d'orientation attendu.")
                raster = image.resize(target_size, Image.Resampling.LANCZOS) if target_size != source_size else image.copy()
                derived, metadata = remove_ruled_grid(raster)
            if metadata is None:
                metadata = {"algorithm": "intrinsic-bitmap-aspect-v1" if target_size != source_size else "unchanged-raster",
                            "width": derived.width, "height": derived.height, "grid_cells": [],
                            "source_raster_sha256": hashlib.sha256(raster.tobytes()).hexdigest(),
                            "derived_raster_sha256": hashlib.sha256(derived.tobytes()).hexdigest()}
            metadata.update({"ocr_region_index": region_index,
                             "parser_bbox": self._current_rects[region_index].model_dump(mode="json"),
                             "scale": self.scale, "coordinate_frame": "oriented_ocr_region_pixels",
                             "render_allocation_scale": self.scale * render_oversample,
                             "source_oriented_raster_size": list(source_size), "derived_oriented_raster_size": list(derived.size),
                             "resize_inverse_factors": [source_size[0] / derived.width, source_size[1] / derived.height],
                             "orientation_degrees": orientation.get("orientation_degrees"),
                             "orientation_resolved": orientation["resolved"]})
            self._current_preprocessing.append(metadata)
            with temporary_raster(derived) as target:
                frame = self._run_literal_tsv(target, osd)
                cells = metadata["grid_cells"]
                if not cells:
                    return self._restore_raster(frame, source_size, derived.size)
                import numpy as np
                import pandas as pd

                left, top = min(cell[0] for cell in cells), min(cell[1] for cell in cells)
                right, bottom = max(cell[2] for cell in cells), max(cell[3] for cell in cells)
                center_x, center_y = frame["left"] + frame["width"] / 2, frame["top"] + frame["height"] / 2
                outside = frame[~((center_x >= left) & (center_x <= right) & (center_y >= top) & (center_y <= bottom))]
                frames = [outside]
                metadata["cell_ocr"] = []
                for bounds in cells:
                    printed = int((np.asarray(derived.crop(tuple(bounds)).convert("L")) < 128).sum()) >= 3
                    cell_frame = self._cell_ocr(derived, bounds) if printed else None
                    cell_frame = frame.iloc[0:0] if cell_frame is None else cell_frame
                    frames.append(cell_frame)
                    evidence = {"raster_bbox": bounds, "printed": printed, "recognized_words": len(cell_frame)}
                    if printed:
                        evidence["crop"] = self._last_cell_crop
                    confidence = float(cell_frame["conf"].min()) / 100 if not cell_frame.empty else None
                    if confidence is not None and not math.isfinite(confidence):
                        confidence = None
                    evidence["minimum_word_confidence"] = confidence
                    evidence["minimum_confidence_required"] = minimum_confidence
                    if printed and (cell_frame.empty or confidence is None or (minimum_confidence is not None and confidence < minimum_confidence)):
                        from docling.models.stages.ocr.tesseract_utils import (
                            tesseract_box_to_bounding_rectangle,
                        )
                        from docling_core.types.doc import BoundingBox, CoordOrigin

                        orientation = self._current_orientations[-1]
                        original_bounds = inverse_resized_box(bounds, source_size, derived.size)
                        rect = tesseract_box_to_bounding_rectangle(
                            BoundingBox(l=original_bounds[0], t=original_bounds[1], r=original_bounds[2], b=original_bounds[3], coord_origin=CoordOrigin.TOPLEFT),
                            original_offset=self._current_rects[len(self._current_orientations) - 1], scale=self.scale,
                            orientation=orientation.get("orientation_degrees", 0), im_size=source_size)
                        key = "unresolved_parser_bbox" if cell_frame.empty else "uncertain_parser_bbox"
                        evidence[key] = rect.to_bounding_box().model_dump(mode="json")
                    metadata["cell_ocr"].append(evidence)
                return self._restore_raster(pd.concat(frames, ignore_index=True), source_size, derived.size)

        def _restore_raster(self, frame, source_size, derived_size):
            sx, sy = source_size[0] / derived_size[0], source_size[1] / derived_size[1]
            frame = frame.copy()
            for column, factor in (("left", sx), ("width", sx), ("top", sy), ("height", sy)):
                frame[column] = frame[column] * factor
            return frame

    class RegionalGridPdfPipeline(StandardPdfPipeline):
        def _init_models(self):
            super()._init_models()
            from .regional_tables import RegionalTableStage

            # Adaptateur au même __call__(conv_res, page_batch) que l'étape table, sans en hériter.
            self.table_model = RegionalTableStage(self.table_model, self.ocr_model)  # type: ignore[assignment]

        def _make_ocr_model(self, art_path):
            if not self.pipeline_options.do_ocr:
                return super()._make_ocr_model(art_path)
            return GridAwareTesseract(enabled=True, artifacts_path=art_path, options=self.pipeline_options.ocr_options,
                                      accelerator_options=self.pipeline_options.accelerator_options)

    return RegionalGridPdfPipeline
