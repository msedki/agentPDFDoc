"""Verify and prepare the frozen I5 transfer without leaking its contents.

The oracle preparer owns this harness and does not modify product code. Native
workers run only with --execute, sequentially, against the selected checkout.
This tool never downloads a source or silently reuses another arm's extraction.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qualification import prepare_production_i4 as prior  # noqa: E402
from tools.qualification.materialize_production_i4 import (  # noqa: E402
    MAX_MANIFEST_BYTES,
    MAX_PDF_BYTES,
    read_bounded,
    relative_path,
)

HELDOUT_RECEIPT_SHA256 = "6f095117dc3a49734270ef633e5b5f94ee3dc0bfed45f0a8ff0fd8faf99f1091"
CORRECTED_TESSERACT_SHA256 = "61461b50cb385288c9c1a0382c5836202bdb7ded69b899b04f83122399959c97"
MANIFEST_NAMES = frozenset({"sources.json", "questions-oracles.json", "scan-transformations.json"})
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}")
SHA256 = re.compile(r"[0-9a-f]{64}")
COUNTS = {"primary_documents": 3, "questions": 10, "positive_questions": 8,
          "limit_questions": 2, "derived_positive_queries": 2, "native_primary_queries_per_arm": 12}
MAX_DIAGNOSTIC_WINDOW_PAGES = 4

# Runs in the selected checkout/PYTHONPATH, not the harness checkout. Calling
# the existing worker main preserves its native fault handling and private
# descriptors. Its exact raw result is retained before the diagnostic envelope.
WINDOW_WORKER_ADAPTER = r'''
import hashlib
import json
import sys
from pathlib import Path

from services.ingestion.checkpoint import atomic_json
from services.ingestion.worker import main as worker_main

request_path, result_path = (Path(value) for value in sys.argv[1:])
raw_path = result_path.with_suffix(".raw-window.json")
if raw_path.exists() or result_path.exists():
    raise FileExistsError("Diagnostic evidence exists; use a fresh output.")
request = json.loads(request_path.read_text())
sys.argv = ["services.ingestion.worker", "--request", str(request_path), "--result", str(raw_path)]
returncode = worker_main()
raw = raw_path.read_bytes()
result = json.loads(raw)
if returncode == 0 and result.get("ok") is True:
    from services.ingestion.pipeline import stitch_structure
    extraction = result["result"]
    first, last = request["page_start"], request["page_end"]
    indices = [page["page_index"] for page in extraction["pages"]]
    if (indices != list(range(first, last + 1)) or any(type(index) is not int for index in indices)
            or extraction["page_count"] <= last or extraction["sha256"] != request["expected_source_sha256"]):
        raise ValueError("Worker window lost original page indices or source binding.")
    extraction["sections"], extraction["tables"] = stitch_structure(extraction["pages"])
    omitted = extraction["page_count"] - len(extraction["pages"])
    extraction["status"] = "ready_partial"
    extraction["coverage"] = {
        "total": extraction["page_count"], "processed": len(extraction["pages"]),
        "ocr": sum(bool(page.get("ocr_used")) for page in extraction["pages"]),
        "unresolved": omitted + sum(page.get("extraction_state") == "error" or bool(page.get("unresolved_regions"))
                                     for page in extraction["pages"]),
        "unresolved_regions": sum(len(page.get("unresolved_regions", [])) for page in extraction["pages"]),
        "omitted_by_diagnostic_scope": omitted,
    }
    extraction.setdefault("warnings", []).append({
        "code": "qualification_targeted_diagnostic", "page_start": first, "page_end": last,
        "message": "Targeted diagnostic only; original page indices preserved; not full-document qualification.",
        "omitted_pages": omitted,
    })
    extraction["diagnostic_only"] = True
    extraction["diagnostic_raw_worker_sha256"] = hashlib.sha256(raw).hexdigest()
    extraction["diagnostic_raw_worker_file"] = raw_path.name
atomic_json(result_path, result)
raise SystemExit(returncode)
'''


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def _verified_file(base: Path, spec: dict, checksum_field: str, *, directory: str) -> Path:
    name = spec["file"]
    path = relative_path(name)
    if len(path.parts) != 2 or path.parts[0] != directory or path.suffix.lower() != ".pdf":
        raise ValueError("Frozen PDF path is outside its designated directory.")
    checksum = spec[checksum_field]
    size = spec["bytes"]
    if (not isinstance(checksum, str) or not SHA256.fullmatch(checksum)
            or type(size) is not int or not 0 < size <= MAX_PDF_BYTES):
        raise ValueError("Invalid frozen PDF checksum or size.")
    raw = read_bounded(base, name, MAX_PDF_BYTES)
    if len(raw) != size or _sha(raw) != checksum or not raw.startswith(b"%PDF-"):
        raise ValueError("Frozen PDF bytes changed before extraction.")
    return base / name


def validate_bundle(sources: dict, oracles: dict, derived: dict) -> None:
    """Check semantic links without any product extraction or oracle relaxation."""
    documents, cases, scans = sources.get("documents", []), oracles.get("cases", []), derived.get("scans", [])
    if (sources.get("schema_version") != "i5-heldout-sources-v1"
            or oracles.get("schema_version") != "i5-heldout-questions-v1"
            or derived.get("schema_version") != "i5-heldout-derived-pairs-v1"
            or len(documents) != 3 or len(cases) != 10 or len(scans) != 2):
        raise ValueError("I5 requires the three originals, ten questions and two derived pages.")
    by_document: dict[str, dict] = {}
    paths = set()
    for document in documents:
        key, path = document.get("id"), document.get("file")
        if (not _identifier(key) or key in by_document or not isinstance(path, str) or path in paths
                or type(document.get("pages")) is not int or document["pages"] < 1):
            raise ValueError("Duplicate/invalid frozen document identifier, path or page count.")
        by_document[key] = document
        paths.add(path)
    by_case: dict[str, dict] = {}
    for case in cases:
        key = case.get("id")
        document = by_document.get(case.get("document_id"))
        scope = case.get("scope", {})
        start, end = scope.get("page_start"), scope.get("page_end")
        if (not _identifier(key) or key in by_case or document is None
                or type(case.get("answerable")) is not bool or not isinstance(case.get("question"), str)
                or not case["question"].strip() or len(case["question"]) > 8192
                or scope.get("kind") != "pages" or type(start) is not int or type(end) is not int
                or not 0 <= start <= end < document["pages"]
                or not isinstance(case.get("required_evidence_units"), list)
                or not case["required_evidence_units"]):
            raise ValueError("Invalid question, evidence or document/page scope in frozen oracle.")
        by_case[key] = case
    if sum(case["answerable"] for case in cases) != 8:
        raise ValueError("I5 keeps eight positive questions and two limits in the denominator.")
    modes = set()
    scan_ids = set()
    paired_cases = set()
    for scan in scans:
        key, path, case_id = scan.get("id"), scan.get("file"), scan.get("case_id")
        original = by_document.get(scan.get("original_document_id"))
        case = by_case.get(case_id)
        index = scan.get("original_page_index")
        if (not _identifier(key) or key in scan_ids or key in by_document
                or not isinstance(path, str) or path in paths or case_id in paired_cases
                or original is None or case is None or not case["answerable"]
                or case["document_id"] != original["id"] or type(index) is not int
                or not case["scope"]["page_start"] <= index <= case["scope"]["page_end"]
                or scan.get("original_sha256") != original.get("original_sha256")
                or scan.get("product_physical_page") != 1):
            raise ValueError("Derived page is not bound to its frozen positive original and scope.")
        transform = scan.get("transform", {})
        dimensions = scan.get("raster_dimensions")
        if (transform.get("render_dpi") != 200 or transform.get("scale") != 200 / 72
                or transform.get("rotation_degrees") != 0 or transform.get("color") != "8-bit grayscale"
                or transform.get("resizing_after_render") is not False or transform.get("augmentation") is not None
                or transform.get("reportlab_invariant") is not True
                or not isinstance(dimensions, list) or len(dimensions) != 2
                or any(type(value) is not int or value <= 0 for value in dimensions)
                or dimensions[0] * dimensions[1] > 13_000_000):
            raise ValueError("Derived transform differs from the frozen 200 dpi route.")
        mode = scan.get("kind")
        if mode == "image_only":
            if transform.get("embedded_text") is not False or transform.get("native_footer") is not None:
                raise ValueError("The image-only positive must not receive a native text answer.")
        elif mode == "image_body_native_footer":
            footer = transform.get("native_footer")
            if (transform.get("embedded_text") is not True or not isinstance(footer, list)
                    or len(footer) != 2 or any(not isinstance(line, str) or len(line) > 512 for line in footer)
                    or transform.get("native_footer_font") != "Helvetica"
                    or transform.get("native_footer_size_points") != 7.5
                    or transform.get("native_footer_positions") != [[79, 30], [79, 20]]):
                raise ValueError("The mixed page must keep only the declared native footer.")
        else:
            raise ValueError("Unknown derived-page mode.")
        scan_ids.add(key)
        paths.add(path)
        paired_cases.add(case_id)
        modes.add(mode)
    if modes != {"image_only", "image_body_native_footer"}:
        raise ValueError("I5 needs one scan and one mixed page, not two copies of either route.")


def frozen_inputs(base: Path) -> tuple[dict, dict, dict, dict]:
    base = base.resolve(strict=True)
    raw_receipt = read_bounded(base, "freeze-receipt.json", MAX_MANIFEST_BYTES)
    if _sha(raw_receipt) != HELDOUT_RECEIPT_SHA256:
        raise ValueError("The freeze receipt differs from the pre-trial I5 checksum.")
    receipt = json.loads(raw_receipt)
    if (receipt.get("schema_version") != "i5-heldout-freeze-v1"
            or any(receipt.get("counts", {}).get(key) != value for key, value in COUNTS.items())):
        raise ValueError("The freeze receipt has different I5 denominators.")
    bundle = {}
    for entry in receipt.get("private_files", []):
        name = entry.get("path")
        if name not in MANIFEST_NAMES or name in bundle:
            raise ValueError("Unexpected or duplicate frozen manifest.")
        raw = read_bounded(base, name, MAX_MANIFEST_BYTES)
        if len(raw) != entry.get("bytes") or _sha(raw) != entry.get("sha256"):
            raise ValueError("A frozen manifest changed after pre-registration.")
        bundle[name] = json.loads(raw)
    if set(bundle) != MANIFEST_NAMES:
        raise ValueError("All three frozen manifests are required.")
    sources, oracles, derived = (bundle[name] for name in ("sources.json", "questions-oracles.json", "scan-transformations.json"))
    validate_bundle(sources, oracles, derived)
    for source in sources["documents"]:
        _verified_file(base, source, "original_sha256", directory="originals")
    for scan in derived["scans"]:
        _verified_file(base, scan, "sha256", directory="scans")
    return receipt, sources, oracles, derived


def transfer_dataset(base: Path, kind: str) -> dict:
    receipt, sources, oracles, derived = frozen_inputs(base)
    documents, pairs = [], []
    if kind == "transfer":
        for spec in sources["documents"]:
            documents.append({"key": spec["id"], "path": str((base / spec["file"]).resolve()),
                              "sha256": spec["original_sha256"], "format": "pdf", "url": spec["url"],
                              "revision_observed": spec["revision"], "revision_date_month": spec.get("revision_date_month"),
                              "allow_partial": True})
        pairs = [(case, case["document_id"], case["scope"]) for case in oracles["cases"]]
    elif kind == "ocr":
        by_case = {case["id"]: case for case in oracles["cases"]}
        for spec in derived["scans"]:
            documents.append({"key": spec["id"], "path": str((base / spec["file"]).resolve()),
                              "sha256": spec["sha256"], "format": "pdf", "allow_partial": True,
                              "derived_scan": copy.deepcopy(spec)})
            pairs.append((by_case[spec["case_id"]], spec["id"], {"kind": "pages", "page_start": 0, "page_end": 0}))
    else:
        raise ValueError("Unknown I5 split.")
    cases = [{"id": case["id"] if kind == "transfer" else key + "_" + case["id"],
              "document_key": key, "question": case["question"],
              "scope": {**scope, "document_key": key}, "oracle": copy.deepcopy(case), "repeats": 1}
             for case, key, scope in pairs]
    return {"protocol": "trust-4b-I5-" + kind, "heldout_freeze_utc": receipt["frozen_at_utc"],
            "heldout_receipt_sha256": prior.digest(base / "freeze-receipt.json"), "documents": documents, "cases": cases,
            "judgment": "unreviewed; strict original-page oracle review required for every emitted assertion",
            "partial_policy": "Partial extraction and every timeout/failure remain in the original denominator."}


def fresh_development_dataset(inputs: Path, case_ids: list[str] | None = None) -> dict:
    """Prepare a prior consumed campaign without reusing its extracted records."""
    frozen = json.loads(inputs.read_text(encoding="utf-8"))
    result = copy.deepcopy(frozen)
    if not isinstance(result.get("documents"), list) or not isinstance(result.get("cases"), list):
        raise ValueError("Development inputs require documents and frozen questions.")
    if case_ids:
        available = {case["id"] for case in result["cases"]}
        if len(case_ids) != len(set(case_ids)) or not set(case_ids) <= available:
            raise ValueError("Requested diagnostic cases are duplicate or absent from the consumed inputs.")
        result["cases"] = [case for case in result["cases"] if case["id"] in case_ids]
        required = {case["document_key"] for case in result["cases"]}
        result["documents"] = [spec for spec in result["documents"] if spec["key"] in required]
        if {spec["key"] for spec in result["documents"]} != required:
            raise ValueError("A diagnostic question refers to a missing original.")
        result["selected_case_ids"] = [case["id"] for case in result["cases"]]
        result["omitted_case_ids"] = [case["id"] for case in frozen["cases"] if case["id"] not in case_ids]
    seen = set()
    for spec in result["documents"]:
        key = spec.get("key")
        if not _identifier(key) or key in seen or spec.get("format") != "pdf":
            raise ValueError("Development PDF identifiers must be unique.")
        source = Path(spec["path"])
        source = (source if source.is_absolute() else inputs.parent / source).resolve(strict=True)
        if prior.digest(source) != spec.get("sha256"):
            raise ValueError("Development original changed; keep the old evidence intact.")
        for field in ("extraction_path", "extraction_sha256", "extraction_provenance", "extraction_status", "extraction_coverage"):
            spec.pop(field, None)
        spec["path"] = str(source)
        seen.add(key)
    if not result["documents"] or not result["cases"]:
        raise ValueError("The development campaign must not silently become empty.")
    result.update(protocol="trust-4b-I5-development", source_manifest_sha256=prior.digest(inputs),
                  extraction_route="Fresh full worker per arm; previous consumed corpus is development, never heldout.")
    return result


def development_window_dataset(inputs: Path, case_ids: list[str] | None = None) -> dict:
    """Derive bounded windows from previously consumed page scopes, unchanged."""
    dataset = fresh_development_dataset(inputs, case_ids)
    if dataset.get("heldout_receipt_sha256") == HELDOUT_RECEIPT_SHA256:
        raise ValueError("Targeted diagnostic extraction is forbidden for the reserved I5 transfer.")
    by_key = {spec["key"]: spec for spec in dataset["documents"]}
    windows: dict[str, dict[str, int]] = {}
    seen_case_ids = set()
    for case in dataset["cases"]:
        key, scope = case.get("document_key"), case.get("scope", {})
        first, last = scope.get("page_start"), scope.get("page_end")
        if (not _identifier(case.get("id")) or case["id"] in seen_case_ids or key not in by_key
                or scope.get("kind") != "pages" or scope.get("document_key", key) != key
                or type(first) is not int or type(last) is not int or not 0 <= first <= last):
            raise ValueError("Diagnostic windows require unchanged explicit page scopes and original bindings.")
        seen_case_ids.add(case["id"])
        if key not in windows:
            windows[key] = {"page_start": first, "page_end": last}
        else:
            windows[key]["page_start"] = min(windows[key]["page_start"], first)
            windows[key]["page_end"] = max(windows[key]["page_end"], last)
    for key, window in windows.items():
        if window["page_end"] - window["page_start"] + 1 > MAX_DIAGNOSTIC_WINDOW_PAGES:
            raise ValueError("Diagnostic union exceeds four pages; explicitly select a smaller consumed case set.")
        by_key[key]["diagnostic_window"] = window
    if set(windows) != set(by_key):
        raise ValueError("Every diagnostic original needs at least one explicit page-scoped question.")
    dataset.update(protocol="trust-4b-I5-targeted-development-diagnostic", diagnostic_only=True,
                   extraction_route="Real selected-revision worker window; automatic routing; original physical indices; not full qualification.")
    return dataset


def render_derived(original: Path, spec: dict, output: Path) -> dict:
    """Rebuild the declared PDF/raster pair, with no OCR or answer-shaped text."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    png, pdf = output / (spec["id"] + ".png"), output / (spec["id"] + ".pdf")
    if png.exists() or pdf.exists():
        raise FileExistsError("Derived output exists; choose a fresh directory.")
    document = pdfium.PdfDocument(original)
    page = document[spec["original_page_index"]]
    bitmap = None
    raster = None
    try:
        width, height = page.get_size()
        bitmap = page.render(scale=spec["transform"]["scale"], rotation=0)
        raster = bitmap.to_pil().convert("L")
        raster.save(png, format="PNG")
        canvas = Canvas(str(pdf), pagesize=(width, height), invariant=1, pageCompression=1)
        canvas.setTitle("I5 deterministic " + spec["kind"] + " derived page")
        canvas.setAuthor("Localagent qualification")
        canvas.drawImage(ImageReader(raster), 0, 0, width=width, height=height)
        transform = spec["transform"]
        if spec["kind"] == "image_body_native_footer":
            if transform.get("white_footer_rectangle") != [0, 0, width, 44]:
                raise ValueError("Native footer rectangle differs from the declared page geometry.")
            canvas.setFillColorRGB(1, 1, 1)
            canvas.rect(0, 0, width, 44, fill=1, stroke=0)
            canvas.setFillColorRGB(0, 0, 0)
            canvas.setFont(transform["native_footer_font"], transform["native_footer_size_points"])
            for line, position in zip(transform["native_footer"], transform["native_footer_positions"], strict=True):
                canvas.drawString(*position, line)
        canvas.showPage()
        canvas.save()
    finally:
        if raster is not None:
            raster.close()
        if bitmap is not None:
            bitmap.close()
        page.close()
        document.close()
    rebuilt = pdfium.PdfDocument(pdf)
    rebuilt_page = rebuilt[0]
    text_page = rebuilt_page.get_textpage()
    try:
        native = text_page.get_text_range()
    finally:
        text_page.close()
        rebuilt_page.close()
        rebuilt.close()
    result = {"id": spec["id"], "pdf_sha256": prior.digest(pdf), "raster_sha256": prior.digest(png),
              "embedded_text_sha256": _sha(native.encode()), "embedded_text_characters": len(native),
              "original_sha256_unchanged": prior.digest(original) == spec["original_sha256"]}
    result["byte_identical_to_frozen_pair"] = (
        result["pdf_sha256"] == spec["sha256"] and result["raster_sha256"] == spec["raster_sha256"]
        and result["embedded_text_sha256"] == spec["embedded_text_sha256"] and result["original_sha256_unchanged"])
    return result


def reproduce_derived(base: Path, output: Path) -> None:
    _, sources, _, derived = frozen_inputs(base)
    observed_versions = {name: version(name) for name in ("pypdfium2", "Pillow", "reportlab")}
    if observed_versions != derived.get("versions"):
        raise ValueError("Renderer versions differ from the frozen derived pages.")
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    by_id = {spec["id"]: spec for spec in sources["documents"]}
    rows = [render_derived(base / by_id[spec["original_document_id"]]["file"], spec, output)
            for spec in derived["scans"]]
    receipt = output / "reproduction-receipt.json"
    prior.save_new(receipt, {"versions": observed_versions, "pairs": rows})
    if not all(row["byte_identical_to_frozen_pair"] for row in rows):
        raise ValueError("Derived bytes differ; frozen originals and first results stay intact.")
    print(json.dumps({"derived_pairs": len(rows), "all_byte_identical": True, "receipt_sha256": prior.digest(receipt)}))


def _memory_snapshot(pid: int) -> tuple[int, int, int]:
    parent = psutil.Process(pid)
    members = [parent, *parent.children(recursive=True)]
    rss, pss = 0, 0
    for member in members:
        try:
            rss += member.memory_info().rss
            pss += getattr(member.memory_full_info(), "pss", 0)
        except psutil.Error:
            continue
    return rss, pss, psutil.virtual_memory().available


def prepare_native(args: argparse.Namespace, dataset: dict) -> None:
    """Use the existing owned-worker supervision pattern with an explicit dataset."""
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    application_root = args.application_root.resolve(strict=True)
    config = prior.worker_config(application_root, args.runtime_root.resolve(strict=True))
    frozen_sources = prior.source_hashes(application_root)
    plan = {"created_utc": datetime.now(UTC).isoformat(), "kind": args.kind, "dataset": dataset,
            "application_root": str(application_root), "config": config, "source_files": frozen_sources,
            "harness_sha256": prior.digest(Path(__file__)), "worker_timeout_seconds": args.worker_timeout,
            "uv_lock_sha256": prior.digest(application_root / "uv.lock"),
            "execution_authorized_by_cli": args.execute,
            "route": ("targeted consumed-development diagnostic, not full-document qualification"
                      if dataset.get("diagnostic_only") else
                      "full original document, automatic native/structured/OCR routing, sequential real workers")}
    prior.save_new(output / "extraction-plan.json", plan)
    if not args.execute:
        print(json.dumps({"plan": str(output / "extraction-plan.json"), "sha256": prior.digest(output / "extraction-plan.json"),
                          "documents": len(dataset["documents"]), "cases": len(dataset["cases"]), "executed": False}))
        return
    if not sys.platform.startswith("linux"):
        raise ValueError("This native qualification supervisor requires Linux owned process groups.")
    if prior.digest(Path(config["pdf"]["tesseract_cmd"])) != CORRECTED_TESSERACT_SHA256:
        raise ValueError("Both I5 arms require the corrected I4 Tesseract binary.")
    from services.runtime.posix_process import PosixJob
    from tools.qualification.run_grounded_native import stop_owned

    receipts: list[dict[str, Any]] = []
    active_document = None
    try:
        for spec in dataset["documents"]:
            active_document = spec["key"]
            directory = output / (spec["key"] + "-extraction")
            directory.mkdir()
            request = {"path": spec["path"], "version_id": str(uuid.uuid5(uuid.NAMESPACE_URL, spec["sha256"])),
                       "output_dir": str(directory), "config": config}
            window = spec.get("diagnostic_window")
            if window is not None:
                if not dataset.get("diagnostic_only") or args.kind != "development-window":
                    raise ValueError("Window extraction is restricted to explicitly labelled development diagnostics.")
                request.update(window, expected_source_sha256=spec["sha256"])
            request_path, result_path = directory / "request.json", directory / "result.json"
            prior.save_new(request_path, request)
            env = {key: value for key, value in os.environ.items() if key.upper() not in {
                "RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "QDRANT__SERVICE__API_KEY", "RAG_DATA_DIR", "RAG_DB_PATH"}}
            env.update(PYTHONPATH=str(application_root), HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                       TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
            job = PosixJob()
            process, stop = None, None
            started = time.monotonic()
            peak_rss = peak_pss = samples = 0
            minimum_available = psutil.virtual_memory().available
            expired = False
            try:
                command = ([sys.executable, "-c", WINDOW_WORKER_ADAPTER, str(request_path), str(result_path)] if window else
                           [sys.executable, "-m", "services.ingestion.worker", "--request", str(request_path),
                            "--result", str(result_path)])
                process = job.launch(command, cwd=application_root, env=env,
                                     log_path=directory / "worker.log")
                while process.poll() is None:
                    if time.monotonic() - started > args.worker_timeout:
                        expired = True
                        break
                    try:
                        rss, pss, available = _memory_snapshot(process.pid)
                        peak_rss, peak_pss = max(peak_rss, rss), max(peak_pss, pss)
                        minimum_available = min(minimum_available, available)
                        samples += 1
                    except psutil.Error:
                        pass
                    time.sleep(0.5)
            finally:
                if process is not None:
                    stop = stop_owned(process)
                job.close()
            receipt = {"key": spec["key"], "elapsed_seconds": time.monotonic() - started, "timeout": expired,
                       "rss_sum_peak_bytes": peak_rss, "pss_sum_peak_bytes": peak_pss,
                       "minimum_host_available_bytes": minimum_available, "memory_samples": samples,
                       "stop": stop, "request_sha256": prior.digest(request_path)}
            receipts.append(receipt)
            prior.save_new(directory / "receipt.json", receipt)
            if expired or stop is None or not stop["owned_group_empty"] or not result_path.is_file():
                raise RuntimeError("Worker failed to finish cleanly; evidence preserved.")
            result = json.loads(result_path.read_text())
            if result.get("ok") is not True or stop["returncode"] != 0:
                raise RuntimeError("Extraction failure preserved without excluding the document.")
            extraction = result["result"]
            if extraction["sha256"] != spec["sha256"] or prior.digest(Path(spec["path"])) != spec["sha256"]:
                raise ValueError("Original or extraction binding changed during the worker.")
            frozen_path = output / (spec["key"] + ".extraction.json")
            prior.save_new(frozen_path, extraction)
            spec.update(extraction_path=str(frozen_path), extraction_sha256=prior.digest(frozen_path),
                        extraction_provenance=("real_worker_of_selected_revision_targeted_diagnostic" if window else
                                               "real_worker_of_selected_revision_full_document"),
                        extraction_status=extraction["status"], extraction_coverage=extraction.get("coverage"))
            print(json.dumps({"extracted": spec["key"], "status": extraction["status"],
                              "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)
        prior.save_new(output / "inputs.json", dataset)
    except Exception as error:
        prior.save_new(output / "preparation-failure.json", {"document_key": active_document,
                       "error_type": type(error).__name__, "outputs_preserved": True})
        raise
    finally:
        changed = [path for path, checksum in frozen_sources.items() if not (application_root / path).is_file()
                   or prior.digest(application_root / path) != checksum]
        prior.save_new(output / "preparation-receipt.json", {"documents": receipts, "changed_source_files": changed})
        if changed:
            raise RuntimeError("Application code changed during native extraction.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=("transfer", "ocr", "development-pdf", "development-window", "derived-reproduction"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--heldout", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--application-root", type=Path, default=ROOT)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--worker-timeout", type=int, default=1800)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--case-id", action="append", default=[], help="Only for consumed development-window diagnostics.")
    args = parser.parse_args()
    if args.worker_timeout < 1 or args.worker_timeout > 1800:
        parser.error("Worker timeout must remain between 1 and 1800 seconds.")
    if args.case_id and args.kind != "development-window":
        parser.error("--case-id is restricted to consumed development-window diagnostics.")
    if args.kind in {"development-pdf", "development-window"}:
        if args.inputs is None:
            parser.error("--inputs is required for the consumed development corpus.")
        dataset = (development_window_dataset(args.inputs.resolve(strict=True), args.case_id)
                   if args.kind == "development-window" else fresh_development_dataset(args.inputs.resolve(strict=True)))
    else:
        if args.heldout is None:
            parser.error("--heldout is required for the reserved corpus.")
        base = args.heldout.resolve(strict=True)
        if args.kind == "derived-reproduction":
            reproduce_derived(base, args.output.resolve())
            return
        dataset = transfer_dataset(base, args.kind)
    prepare_native(args, dataset)


if __name__ == "__main__":
    main()
