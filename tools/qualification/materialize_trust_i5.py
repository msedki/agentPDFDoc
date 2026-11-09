"""Materialize the frozen I5 bundle; never ingest, run OCR or call a model.

Only --download permits network access, to the exact HTTPS URLs bound to the
published I5 receipt. The default copies verified local originals. Questions
are checked internally but never printed or copied into the operational receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import nullcontext
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qualification import materialize_production_i4 as bounded  # noqa: E402
from tools.qualification import prepare_trust_i5 as preparer  # noqa: E402

RENDERER_PACKAGES = frozenset({"pypdfium2", "Pillow", "reportlab"})


class MaterializationFailure(RuntimeError):
    """A failed fresh output has a receipt, with no input contents in the error."""

    def __init__(self, phase: str, receipt: Path) -> None:
        self.phase, self.receipt = phase, receipt
        super().__init__(f"I5 materialization failed during {phase}; failure receipt preserved.")


def load_bundle(corpus: Path) -> tuple[dict[str, bytes], dict, dict]:
    """Verify every opaque manifest before parsing any question or metadata."""
    raw_receipt = bounded.read_bounded(corpus, "freeze-receipt.json")
    if hashlib.sha256(raw_receipt).hexdigest() != preparer.HELDOUT_RECEIPT_SHA256:
        raise ValueError("The receipt differs from the published I5 lock.")
    receipt = json.loads(raw_receipt)
    if (receipt.get("schema_version") != "i5-heldout-freeze-v1"
            or any(receipt.get("counts", {}).get(key) != value for key, value in preparer.COUNTS.items())):
        raise ValueError("The I5 frozen denominators differ.")
    bundle = {"freeze-receipt.json": raw_receipt}
    for entry in receipt.get("private_files", []):
        name = entry.get("path")
        if name not in preparer.MANIFEST_NAMES or name in bundle:
            raise ValueError("Unexpected or duplicate I5 manifest.")
        raw = bounded.read_bounded(corpus, name)
        if (type(entry.get("bytes")) is not int or len(raw) != entry["bytes"]
                or hashlib.sha256(raw).hexdigest() != entry.get("sha256")):
            raise ValueError("A manifest differs from its frozen bytes.")
        bundle[name] = raw
    if set(bundle) != preparer.MANIFEST_NAMES | {"freeze-receipt.json"}:
        raise ValueError("All three I5 manifests are required.")
    sources = json.loads(bundle["sources.json"])
    derived = json.loads(bundle["scan-transformations.json"])
    # Canonical I5 validation includes question/page/polarity links. Its objects
    # stay inside the harness; no oracle enters the materialization receipt.
    preparer.validate_bundle(sources, json.loads(bundle["questions-oracles.json"]), derived)
    return bundle, sources, derived


def validate_materialization_metadata(sources: dict, derived: dict) -> None:
    """Check paths, fixed HTTPS origins and renderer fields before any side effect."""
    versions = derived.get("versions", {})
    if (set(versions) != RENDERER_PACKAGES
            or any(not isinstance(value, str) or not value for value in versions.values())):
        raise ValueError("The three frozen renderer versions are required.")
    for directory, specifications, checksum_key in (
        ("originals", sources["documents"], "original_sha256"),
        ("scans", derived["scans"], "sha256"),
    ):
        for spec in specifications:
            path = bounded.relative_path(spec["file"])
            if (len(path.parts) != 2 or path.parts[0] != directory or path.suffix.lower() != ".pdf"
                    or type(spec.get("bytes")) is not int or not 0 < spec["bytes"] <= bounded.MAX_PDF_BYTES
                    or not isinstance(spec.get(checksum_key), str)
                    or not bounded.SHA256.fullmatch(spec[checksum_key])):
                raise ValueError("Invalid frozen PDF path, size or checksum.")
            if directory == "originals":
                url = urlsplit(spec["url"])
                # The complete URL is trusted only through the fixed I5 receipt,
                # never accepted as a free CLI value or redirected to a fallback.
                if (url.scheme != "https" or not url.hostname or url.username is not None
                        or url.password is not None or url.fragment or url.port not in {None, 443}
                        or any(ord(char) < 32 for char in spec["url"])):
                    raise ValueError("Frozen source URL must be direct HTTPS without credentials.")
            elif (str(path) != "scans/" + spec["id"] + ".pdf"
                    or any(not isinstance(spec.get(key), str) or not bounded.SHA256.fullmatch(spec[key])
                           for key in ("raster_sha256", "embedded_text_sha256"))):
                raise ValueError("Derived output path or renderer checksum is invalid.")


def verify_original(base: Path, spec: dict) -> None:
    bounded.verify_original(base, spec)
    with bounded.regular_input(base, spec["file"], bounded.MAX_PDF_BYTES) as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("The frozen original is not a PDF.")


def materialize(corpus: Path, output: Path, *, source_cache: Path | None = None,
                download: bool = False, transport: httpx.BaseTransport | None = None) -> dict:
    """Create a fresh confined bundle; explicit test transports are not qualification."""
    if download and source_cache is not None:
        raise ValueError("Choose a source cache or explicit download, not both.")
    if transport is not None and not download:
        raise ValueError("A test transport requires explicit download mode.")
    corpus = corpus.resolve()
    source_root = (source_cache or corpus).resolve()
    # Invalid/existing targets are rejected without touching them. Once a safe
    # fresh target exists, every input, renderer or validator failure gets a receipt.
    output = bounded.private_output(output, (corpus, source_root))
    receipt_path = output / "materialization-receipt.json"
    phase = "verify_manifests"
    report: dict[str, Any] = {
        "kind": "frozen_i5_input_materialization", "status": "started",
        "started_utc": datetime.now(UTC).isoformat(), "output": str(output),
        "heldout_receipt_sha256": preparer.HELDOUT_RECEIPT_SHA256,
        "harness_sha256": bounded.preparer.digest(Path(__file__)),
        "shared_io_sha256": bounded.preparer.digest(Path(bounded.__file__)),
        "shared_renderer_sha256": bounded.preparer.digest(Path(preparer.__file__)),
        "download": download,
        "transport_kind": "explicit_test_substitute" if transport is not None else "native_https" if download else "local_copy",
        "source_url_policy": "Exact HTTPS URLs authenticated by the pre-trial I5 receipt; no free URL input.",
        "download_limits": {"maximum_pdf_bytes": bounded.MAX_PDF_BYTES,
                            "io_timeout_seconds": bounded.DOWNLOAD_TIMEOUT_SECONDS,
                            "deadline_checked_between_chunks_seconds": bounded.DOWNLOAD_DEADLINE_SECONDS,
                            "redirects": False, "environment_proxy": False},
        "oracle_content_emitted": False, "ingestion_executed": False, "model_calls": 0,
        "manifests": [], "originals": [], "derived": [], "frozen_inputs_verified": False,
        "measurement_limit": "Byte-identical input materialization only; no extraction, OCR, answer or production qualification.",
    }
    try:
        bundle, sources, derived = load_bundle(corpus)
        phase = "validate_metadata"
        validate_materialization_metadata(sources, derived)
        phase = "verify_versions"
        report["versions"] = {name: version(name) for name in sorted(RENDERER_PACKAGES)}
        if report["versions"] != derived["versions"]:
            raise ValueError("Renderer versions differ from the frozen I5 versions.")
        phase = "verify_local_originals"
        if not download:
            for spec in sources["documents"]:
                verify_original(source_root, spec)
        phase = "copy_manifests"
        for name, raw in bundle.items():
            checksum = hashlib.sha256(raw).hexdigest()
            bounded.publish_bytes(output / name, [raw], expected_bytes=len(raw), expected_sha256=checksum)
            report["manifests"].append({"file": name, "bytes": len(raw), "sha256": checksum})
        (output / "originals").mkdir(mode=0o700)
        phase = "materialize_originals"
        client_context = (httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
                                      timeout=bounded.DOWNLOAD_TIMEOUT_SECONDS, headers={"Accept-Encoding": "identity"})
                          if download else nullcontext(None))
        with client_context as client:
            for spec in sources["documents"]:
                target = output / spec["file"]
                if client is not None:
                    bounded.download_original(client, spec, target)
                else:
                    with bounded.regular_input(source_root, spec["file"], bounded.MAX_PDF_BYTES) as handle:
                        bounded.publish_bytes(target, iter(lambda: handle.read(bounded.CHUNK_BYTES), b""),
                                              expected_bytes=spec["bytes"], expected_sha256=spec["original_sha256"])
                verify_original(output, spec)
                report["originals"].append({"id": spec["id"], "file": spec["file"], "bytes": spec["bytes"],
                                            "sha256": spec["original_sha256"]})
        phase = "render_derived"
        (output / "scans").mkdir(mode=0o700)
        by_id = {spec["id"]: spec for spec in sources["documents"]}
        for spec in derived["scans"]:
            original = output / by_id[spec["original_document_id"]]["file"]
            checked = preparer.render_derived(original, spec, output / "scans")
            report["derived"].append(checked)
            pdf = bounded.read_bounded(output, spec["file"], bounded.MAX_PDF_BYTES)
            png_name = "scans/" + spec["id"] + ".png"
            png = bounded.read_bounded(output, png_name, bounded.MAX_PDF_BYTES)
            if (checked.get("byte_identical_to_frozen_pair") is not True
                    or checked.get("original_sha256_unchanged") is not True
                    or checked.get("embedded_text_sha256") != spec["embedded_text_sha256"]
                    or len(pdf) != spec["bytes"] or hashlib.sha256(pdf).hexdigest() != spec["sha256"]
                    or hashlib.sha256(png).hexdigest() != spec["raster_sha256"]):
                raise ValueError("Rebuilt I5 pair differs from the frozen PDF, raster or native text.")
            (output / spec["file"]).chmod(0o600)
            (output / png_name).chmod(0o600)
        phase = "verify_source_inputs"
        for name, expected in bundle.items():
            if bounded.read_bounded(corpus, name) != expected:
                raise ValueError("An input manifest changed during materialization.")
        if not download:
            for spec in sources["documents"]:
                verify_original(source_root, spec)
        report["source_inputs_unchanged"] = True
        phase = "final_validator"
        preparer.frozen_inputs(output)
        report.update(status="materialized_verified", frozen_inputs_verified=True)
        phase = "complete"
        return report
    except Exception as error:
        report.update(status="failed", error={"type": type(error).__name__, "phase": phase})
        raise MaterializationFailure(phase, receipt_path) from None
    except BaseException as error:
        report.update(status="interrupted", error={"type": type(error).__name__, "phase": phase})
        raise
    finally:
        report["finished_utc"] = datetime.now(UTC).isoformat()
        report["phase"] = phase
        bounded.preparer.save_new(receipt_path, report)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Published I5 manifest directory, unchanged frozen bytes.")
    parser.add_argument("--output", type=Path, required=True, help="New output directory below .runtime/qa; never overwritten.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--source-cache", type=Path, help="Local root containing originals/ and PDFs at their frozen hashes.")
    mode.add_argument("--download", action="store_true", help="Permit exactly the three HTTPS URLs authenticated by the I5 receipt.")
    args = parser.parse_args(argv)
    try:
        result = materialize(args.corpus, args.output, source_cache=args.source_cache, download=args.download)
    except MaterializationFailure as error:
        print(json.dumps({"status": "failed", "phase": error.phase, "receipt": str(error.receipt),
                          "oracle_content_emitted": False, "model_calls": 0}), file=sys.stderr)
        raise SystemExit(1) from None
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "refused", "error_type": type(error).__name__,
                          "oracle_content_emitted": False, "model_calls": 0}), file=sys.stderr)
        raise SystemExit(1) from None
    receipt = Path(result["output"]) / "materialization-receipt.json"
    print(json.dumps({"status": result["status"], "receipt": str(receipt),
                      "receipt_sha256": bounded.preparer.digest(receipt), "originals": len(result["originals"]),
                      "derived_pairs": len(result["derived"]), "oracle_content_emitted": False, "model_calls": 0}))


if __name__ == "__main__":
    main()
