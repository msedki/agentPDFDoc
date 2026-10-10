"""Office extraction in the existing isolated worker; no PDF/model imports."""

import hashlib
import json
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from uuid import UUID, uuid5

from services.ingestion.checkpoint import atomic_json
from services.ingestion.errors import IngestionError

from .models import OfficeLimits, limit_error
from .opc import OfficePackage


def office_content_hash(extraction):
    """Hash canonical content before its revision ID is attached to source blocks."""
    units = [{**unit, "blocks": [{key: value for key, value in block.items()
                                 if key != "extraction_revision_id"}
                                for block in unit.get("blocks", [])]}
             for unit in extraction.get("units", [])]
    content = {"units": units, "sections": extraction.get("sections", []),
               "tables": extraction.get("tables", []), "metadata": extraction.get("metadata", {})}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def office_fingerprint(config=None, document_format="docx"):
    if document_format not in {"docx", "xlsx"}:
        raise IngestionError("OFFICE_FORMAT_MISMATCH", "Format Office inconnu.")
    directory = Path(__file__).parent
    modules = ("models.py", "opc.py", "pipeline.py", document_format + ".py")
    identity = {"format": document_format, "revision": "office-native-v1", "limits": asdict(OfficeLimits.from_mapping(config)),
                "libraries": {name: version(name) for name in ("lxml", "defusedxml", "openpyxl", "python-docx")},
                "modules": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in modules}}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def extract_office(path, output_dir, config, version_id, document_format, cancel_path=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = office_fingerprint(config, document_format)
    cancel = Path(cancel_path) if cancel_path else None
    last_progress = 0.0

    def checkpoint(unit):
        nonlocal last_progress
        tick = time.monotonic()
        if tick - last_progress >= 1 or unit.endswith(":complete"):
            atomic_json(output_dir / "office-progress.json", {"unit": unit, "fingerprint": fingerprint})
            last_progress = tick
        if cancel and cancel.exists():
            raise IngestionError("CHECKPOINT_REQUESTED", "Extraction Office suspendue ; la reprise garde l'original et son identité.")

    try:
        with OfficePackage(path, document_format, OfficeLimits.from_mapping(config)) as package:
            cache_dir = output_dir / "office-units"
            cache_dir.mkdir(exist_ok=True)
            cached_units: dict[str, dict] = {}
            cache_bytes = 0
            for cache_path in cache_dir.glob("*.json"):
                try:
                    cache_bytes += cache_path.stat().st_size
                    if len(cached_units) >= package.limits.max_units or cache_bytes > package.limits.max_total_bytes:
                        raise ValueError("cache limit")
                    envelope = json.loads(cache_path.read_text(encoding="utf-8"))
                    payload = envelope["unit"]
                    if not isinstance(payload, dict) or payload.get("id") in cached_units:
                        raise ValueError("cache unit")
                    payload_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                    if (envelope.get("sha256") != package.sha256 or envelope.get("fingerprint") != fingerprint
                            or envelope.get("payload_hash") != payload_hash or not isinstance(payload.get("id"), str)):
                        raise ValueError("cache identity")
                    cached_units[payload["id"]] = payload
                except (OSError, ValueError, KeyError, TypeError) as error:
                    raise IngestionError("OFFICE_CHECKPOINT_INVALID", "Le checkpoint Office ne correspond pas à cet original et à ce parseur.") from error

            def unit_sink(unit):
                nonlocal cache_bytes
                payload_hash = hashlib.sha256(json.dumps(unit, ensure_ascii=False, sort_keys=True,
                                                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                name = hashlib.sha256(unit["id"].encode()).hexdigest() + ".json"
                envelope = {"sha256": package.sha256, "fingerprint": fingerprint, "payload_hash": payload_hash, "unit": unit}
                size = len(json.dumps(envelope, ensure_ascii=False, indent=2).encode()) + 1
                destination = cache_dir / name
                previous = destination.stat().st_size if destination.exists() else 0
                if cache_bytes - previous + size > package.limits.max_total_bytes:
                    raise limit_error()
                atomic_json(destination, envelope)
                cache_bytes = cache_bytes - previous + destination.stat().st_size

            atomic_json(output_dir / "preflight.json", {"format": package.format, "sha256": package.sha256,
                                                       "members": len(package.names), "limits": asdict(package.limits)})
            if document_format == "docx":
                from .docx import parse_docx
                result = parse_docx(package, checkpoint=checkpoint, unit_sink=unit_sink, cached_units=cached_units)
            else:
                from .xlsx import parse_xlsx
                result = parse_xlsx(package, checkpoint=checkpoint, unit_sink=unit_sink, cached_units=cached_units)
            sha256 = package.sha256
            limits = package.limits
            block_ids = set()
            text_size = 0
            for unit in result["units"]:
                if len(result["units"]) > limits.max_units:
                    raise limit_error()
                for block in unit.get("blocks", []):
                    if block["id"] in block_ids:
                        raise IngestionError("OFFICE_DUPLICATE_ANCHOR", "Deux éléments Office ont la même localisation.")
                    block_ids.add(block["id"])
                    text = block.get("raw_text", block.get("text", ""))
                    text_size += len(text)
                    if len(block_ids) > limits.max_blocks or text_size > limits.max_text_chars:
                        raise limit_error()
                    block["source_text_hash"] = hashlib.sha256(text.encode()).hexdigest()
                    block.setdefault("precision", "element" if document_format == "docx" else "range")
                    block.setdefault("metadata", {})["extraction_method"] = "office_native"
            source_hash = office_content_hash(result)
            revision = str(uuid5(UUID(version_id), fingerprint + ":" + source_hash))
            result.update({"format": document_format, "sha256": sha256, "pipeline_fingerprint": fingerprint,
                           "extraction_revision_id": revision, "source_hash": source_hash})
            for unit in result["units"]:
                for block in unit.get("blocks", []):
                    block["extraction_revision_id"] = revision
            atomic_json(output_dir / "extraction.json", result)
            return result
    except IngestionError as error:
        if error.code == "CHECKPOINT_REQUESTED":
            return {"format": document_format, "status": "checkpointed", "pipeline_fingerprint": fingerprint}
        raise
