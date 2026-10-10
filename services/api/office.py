"""Revision-pinned, bounded views of registered Office source structures."""

import hashlib
import io
import json

from PIL import Image, UnidentifiedImageError

from services.ingestion.office.models import OfficeLimits
from services.ingestion.office.opc import OfficePackage

from .errors import ApiError


def office_generation(db, version_id, revision=None, expected=None):
    version = db.version(version_id)
    if version["format"] not in {"docx", "xlsx"} or expected and version["format"] != expected:
        raise ApiError("invalid_document_format", "Ce format ne possède pas cette représentation Office.", 409)
    generation = db.generation_for_version(version_id, revision)
    return version, generation


def identity(version, generation):
    return {"version_id": version["id"], "generation_id": generation["id"],
            "extraction_revision_id": generation["extraction_revision_id"], "format": version["format"]}


def cell_semantics(cell):
    """Types and cache state without duplicating unbounded cell contents."""
    formula_present = cell.get("formula") is not None
    cached_present = cell.get("cached_present", False)
    if formula_present:
        value_origin = "formula_cache" if cached_present else "formula_without_cache"
    else:
        value_origin = "literal" if (cell.get("value") or {}).get("kind") not in {None, "empty"} else "empty"
    return {"address": cell["address"], "data_type": cell["data_type"], "number_format": cell.get("number_format"),
            "value_kind": (cell.get("value") or {}).get("kind"),
            "cached_value_kind": (cell.get("cached_value") or {}).get("kind"),
            "value_origin": value_origin, "formula_present": formula_present, "cached_present": cached_present,
            "cache_freshness": cell.get("cache_freshness", "absent")}


def unit_record(row):
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json"))
    return result


def block_record(row, version_id):
    result = dict(row)
    metadata = json.loads(result.pop("metadata_json"))
    result.update(metadata)
    result["type"] = result.pop("kind")
    result["bbox"] = json.loads(result.pop("bbox_json")) if result["bbox_json"] else None
    result["version_id"] = version_id
    result["raw_text"] = result["source_text"] = result["text"]
    return result


def pagination(cursor, limit):
    if cursor < 0 or not 1 <= limit <= 100:
        raise ApiError("invalid_pagination", "Pagination Office invalide.")


def representation(db, settings, version_id, revision, cursor, limit):
    pagination(cursor, limit)
    version, generation = office_generation(db, version_id, revision)
    total = db.one("SELECT count(*) n FROM office_units WHERE generation_id=?", (generation["id"],))["n"]
    units = db.rows("SELECT * FROM office_units WHERE generation_id=? ORDER BY order_index,id LIMIT ? OFFSET ?", (generation["id"], limit, cursor))
    snapshot = db.one("SELECT metadata_json FROM office_documents WHERE generation_id=?", (generation["id"],))
    metadata = json.loads(snapshot["metadata_json"]) if snapshot else {}
    return {**identity(version, generation), "units": [unit_record(row) for row in units],
            "total": total, "cursor": cursor, "next_cursor": cursor + limit if cursor + limit < total else None,
            "metadata": metadata, "coverage": json.loads(generation["coverage_json"]),
            "warnings": json.loads(generation["warnings_json"]),
            "limits": {"max_window_cells": 10_000, "max_page_units": 100,
                       "max_cells": OfficeLimits.from_mapping(settings.profile).max_cells}}


def unit_blocks(db, version_id, unit_id, revision, cursor, limit, block_id=None):
    pagination(cursor, limit)
    version, generation = office_generation(db, version_id, revision)
    unit = db.one("SELECT * FROM office_units WHERE generation_id=? AND id=?", (generation["id"], unit_id))
    if not unit:
        raise ApiError("office_unit_not_found", "Unité Office absente de cette révision.", 404)
    if block_id is not None:
        anchor = db.one("SELECT order_index FROM office_unit_blocks WHERE generation_id=? AND unit_id=? AND block_id=?", (generation["id"], unit_id, block_id))
        if not anchor:
            raise ApiError("block_not_found", "Élément source absent de cette unité et révision.", 404)
        cursor = anchor["order_index"]
    total = db.one("SELECT count(*) n FROM office_unit_blocks WHERE generation_id=? AND unit_id=?", (generation["id"], unit_id))["n"]
    rows = db.rows("SELECT b.* FROM office_unit_blocks u JOIN blocks b ON b.generation_id=u.generation_id AND b.id=u.block_id WHERE u.generation_id=? AND u.unit_id=? ORDER BY u.order_index LIMIT ? OFFSET ?", (generation["id"], unit_id, limit, cursor))
    return {**identity(version, generation), "unit": unit_record(unit), "blocks": [block_record(row, version_id) for row in rows],
            "cursor": cursor, "total": total, "next_cursor": cursor + limit if cursor + limit < total else None,
            "warnings": json.loads(generation["warnings_json"])}


def sheet_cells(db, version_id, sheet_id, revision, row_start, row_end, column_start, column_end):
    if not (1 <= row_start <= row_end <= 1_048_576 and 1 <= column_start <= column_end <= 16_384):
        raise ApiError("invalid_cell_range", "Plage hors des limites du classeur.")
    if (row_end - row_start + 1) * (column_end - column_start + 1) > 10_000:
        raise ApiError("office_window_too_large", "La fenêtre du lecteur est limitée à 10 000 positions ; réduisez la plage.", 413)
    version, generation = office_generation(db, version_id, revision, "xlsx")
    unit = db.one("SELECT * FROM office_units WHERE generation_id=? AND id=? AND kind='xlsx_sheet'", (generation["id"], sheet_id))
    if not unit:
        raise ApiError("sheet_not_found", "Feuille absente de cette révision.", 404)
    cells = db.rows("SELECT data_json FROM office_cells WHERE generation_id=? AND unit_id=? AND row_index BETWEEN ? AND ? AND column_index BETWEEN ? AND ? ORDER BY row_index,column_index", (generation["id"], sheet_id, row_start, row_end, column_start, column_end))
    metadata = json.loads(unit["metadata_json"])
    return {**identity(version, generation), "sheet_id": sheet_id, "sheet": unit_record(unit),
            "bounds": {"row_start": row_start, "row_end": row_end, "column_start": column_start, "column_end": column_end},
            "cells": [json.loads(cell["data_json"]) for cell in cells], "metadata": metadata,
            "tables": metadata.get("tables", []), "warnings": json.loads(generation["warnings_json"])}


def registered_asset(db, settings, version_id, asset_id, revision):
    version, generation = office_generation(db, version_id, revision, "docx")
    if len(asset_id) != 64 or any(char not in "0123456789abcdef" for char in asset_id):
        raise ApiError("asset_not_found", "Image source inconnue.", 404)
    # Only registered images, never a client-supplied package part or XPath.
    images = []
    for row in db.rows("SELECT metadata_json FROM blocks WHERE generation_id=?", (generation["id"],)):
        structure = json.loads(row["metadata_json"]).get("structure", {})
        stack = [structure]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                if value.get("sha256") == asset_id and "part" in value:
                    images.append(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
    if not images:
        raise ApiError("asset_not_found", "Image absente de cette révision.", 404)
    path, _ = db.file_path(version_id, settings.data_dir / "originals")
    with OfficePackage(path, "docx", OfficeLimits.from_mapping(settings.profile)) as package:
        if package.sha256 != version["sha256"]:
            raise ApiError("original_integrity_failure", "L'original ne correspond plus à cette version.", 409)
        data = package.read(images[0]["part"])
    if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != asset_id:
        raise ApiError("asset_not_available", "Cette image ne peut être affichée dans le lecteur.", 409)
    formats = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "BMP": "image/bmp", "WEBP": "image/webp"}
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in formats or image.width * image.height > 16_000_000:
                raise ApiError("asset_not_available", "Ce format ou cette taille d'image n'est pas affichable.", 409)
            mime = formats[image.format]
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ApiError("asset_not_available", "L'image source ne peut pas être affichée.", 409) from error
    return data, mime
