"""Orient an OCR table crop for the same loaded TableFormer model."""


def rotate_point(x, y, width, height, angle, inverse=False):
    if inverse:
        if angle == 90:
            return y, height - x
        if angle == 180:
            return width - x, height - y
        if angle == 270:
            return width - y, x
    else:
        if angle == 90:
            return height - y, x
        if angle == 180:
            return width - x, height - y
        if angle == 270:
            return y, width - x
    if angle == 0:
        return x, y
    raise ValueError("Unsupported table orientation")


class RegionalTableStage:
    """Delegate upright tables and normalize only a proven rotated OCR region."""

    def __init__(self, model, ocr):
        self.model = model
        self.ocr = ocr
        self.corrections_by_page = {}

    def __call__(self, conv_res, page_batch):
        import copy

        from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, Orientation
        from docling_core.types.doc.page import BoundingRectangle

        for page in page_batch:
            corrections = []
            self.corrections_by_page[int(page.page_no)] = corrections
            clusters = page.predictions.layout.clusters
            rotations = {}
            for cluster in clusters:
                if cluster.label not in (DocItemLabel.TABLE, DocItemLabel.DOCUMENT_INDEX):
                    continue
                records = self.ocr.region_orientations_by_page.get(int(page.page_no), [])
                angles = {record["orientation_degrees"] for record in records
                          if record.get("resolved") and cluster.bbox.intersection_over_self(BoundingBox.model_validate(record["parser_bbox"])) >= .5}
                if len(angles) == 1 and next(iter(angles)):
                    rotations[cluster.id] = next(iter(angles))
            page.predictions.layout.clusters = [cluster for cluster in clusters if cluster.id not in rotations]
            try:
                self.model.predict_tables(conv_res, [page])
            finally:
                page.predictions.layout.clusters = clusters
            for cluster in clusters:
                if cluster.id not in rotations:
                    continue
                angle = rotations[cluster.id]
                bbox = cluster.bbox
                width, height = bbox.r - bbox.l, bbox.b - bbox.t
                image = page._backend.get_page_image(scale=self.model.scale, cropbox=bbox)
                upright = image.rotate(-angle, expand=True)
                local_width, local_height = (height, width) if angle in (90, 270) else (width, height)
                local = copy.deepcopy(cluster)
                local.bbox = BoundingBox(l=0, t=0, r=local_width, b=local_height, coord_origin=CoordOrigin.TOPLEFT)
                for cell in local.cells:
                    bounds = cell.rect.to_bounding_box().to_top_left_origin(page.size.height)
                    points = [rotate_point(x - bbox.l, y - bbox.t, width, height, angle)
                              for x in (bounds.l, bounds.r) for y in (bounds.t, bounds.b)]
                    region = BoundingBox(l=min(x for x, _ in points), t=min(y for _, y in points),
                                         r=max(x for x, _ in points), b=max(y for _, y in points), coord_origin=CoordOrigin.TOPLEFT)
                    cell.rect = BoundingRectangle.from_bounding_box(region)
                table = self.model._do_prediction_on_image_to_table(table_image=upright, table_cluster=local, page_no=page.page_no)
                for cell in table.table_cells:
                    if cell.bbox is None:
                        continue
                    points = [rotate_point(x, y, width, height, angle, inverse=True)
                              for x in (cell.bbox.l, cell.bbox.r) for y in (cell.bbox.t, cell.bbox.b)]
                    cell.bbox = BoundingBox(l=min(x for x, _ in points) + bbox.l, t=min(y for _, y in points) + bbox.t,
                                            r=max(x for x, _ in points) + bbox.l, b=max(y for _, y in points) + bbox.t, coord_origin=CoordOrigin.TOPLEFT)
                table.cluster = cluster
                table.orientation = Orientation[f"ROT_{angle}"]
                page.predictions.tablestructure.table_map[cluster.id] = table
                corrections.append({"orientation_degrees": angle, "parser_bbox": bbox.model_dump(mode="json"),
                                    "model": "same-tableformer-accurate", "cells": len(table.table_cells)})
            yield page
