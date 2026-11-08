"""Préparer I4 sans exposer le transfert aux développeurs avant son gel.

Les originaux et oracles existent déjà dans un dossier privé avec leurs hashes.
Le mode PDF produit d'abord un plan ; --execute lance explicitement les vrais
workers de la révision demandée, un document à la fois, sans téléchargement.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import psutil
import yaml

ROOT = Path(__file__).resolve().parents[2]
HELDOUT_RECEIPT_SHA256 = "becadc6f097cf60a67d52f7e37a3b1d4cdfe6d921ec4afc1d228fce793a2052d"
DEVELOPMENT_PDF_SHA256 = {
    "ina226": "c9b67f886d4a5241a5e070723f7b61867409eeb27eed768b9cdd9cb17e03ca2d",
    "tmp117": "78212e91e478035a91165397a8de8a90bfc776759dc445243c033537f0c4b789",
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def inside(base: Path, relative: str) -> Path:
    path = (base / relative).resolve(strict=True)
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Une entrée gelée sort du dossier autorisé.")
    return path


def frozen_inputs(base: Path) -> tuple[dict, dict, dict, dict]:
    """Vérifier les octets gelés avant toute lecture applicative ou extraction."""
    if digest(base / "freeze-receipt.json") != HELDOUT_RECEIPT_SHA256:
        raise ValueError("Le reçu de gel diffère du hash communiqué avant les essais.")
    receipt = json.loads((base / "freeze-receipt.json").read_text())
    for entry in receipt["private_files"]:
        path = inside(base, Path(entry["path"]).name)
        if digest(path) != entry["sha256"]:
            raise ValueError("Manifeste privé modifié après gel : " + path.name)
    sources = json.loads((base / "sources.json").read_text())
    oracles = json.loads((base / "questions-oracles.json").read_text())
    scans = json.loads((base / "scan-transformations.json").read_text())
    for source in sources["documents"]:
        if digest(inside(base, source["file"])) != source["original_sha256"]:
            raise ValueError("Original modifié après gel : " + source["id"])
    for scan in scans["scans"]:
        if digest(inside(base, scan["file"])) != scan["sha256"]:
            raise ValueError("Scan modifié après gel : " + scan["id"])
    if len(oracles["cases"]) != 8 or sum(bool(case["answerable"]) for case in oracles["cases"]) != 6:
        raise ValueError("Le transfert I4 exige les huit oracles gelés, dont six positifs.")
    return receipt, sources, oracles, scans


def transfer_dataset(base: Path, kind: str) -> dict:
    receipt, sources, oracles, scans = frozen_inputs(base)
    documents, cases = [], []
    if kind == "transfer":
        for spec in sources["documents"]:
            documents.append({"key": spec["id"], "path": str(inside(base, spec["file"])),
                              "sha256": spec["original_sha256"], "format": "pdf",
                              "url": spec["url"], "revision_observed": spec["revision"],
                              "revision_date_month": spec["revision_date_month"], "allow_partial": True})
        pairs = [(case, case["document_id"], case["scope"]) for case in oracles["cases"]]
    elif kind == "ocr":
        by_id = {case["id"]: case for case in oracles["cases"]}
        pairs = []
        for spec in scans["scans"]:
            documents.append({"key": spec["id"], "path": str(inside(base, spec["file"])),
                              "sha256": spec["sha256"], "format": "pdf", "allow_partial": True,
                              "derived_scan": spec})
            pairs.append((by_id[spec["case_id"]], spec["id"],
                          {"kind": "pages", "page_start": 0, "page_end": 0}))
    else:
        raise ValueError("Split inconnu.")
    for oracle, key, scope in pairs:
        cases.append({"id": oracle["id"] if kind == "transfer" else key + "_" + oracle["id"],
                      "document_key": key, "question": oracle["question"],
                      "scope": {**scope, "document_key": key}, "oracle": oracle, "repeats": 1})
    return {"protocol": "production-4b-I4-" + kind, "heldout_freeze_utc": receipt["frozen_at_utc"],
            "heldout_receipt_sha256": digest(base / "freeze-receipt.json"), "documents": documents,
            "cases": cases, "judgment": "unreviewed; compare answers with frozen original-page oracles",
            "partial_policy": "A real partial extraction may be indexed, but all warnings and failures remain; no oracle is relaxed."}


def development_pdf_dataset(inputs: Path) -> dict:
    """Reprendre les deux oracles I3 ; ne jamais recycler leur fenêtre d'extraction."""
    frozen = json.loads(inputs.read_text(encoding="utf-8"))
    originals = [spec for spec in frozen["documents"] if spec["format"] == "pdf"]
    if len(originals) != 2 or {spec["key"] for spec in originals} != set(DEVELOPMENT_PDF_SHA256):
        raise ValueError("Les deux PDF de développement I3 verrouillés sont requis.")
    documents = []
    superseded = []
    for spec in originals:
        original = Path(spec["path"])
        original = (original if original.is_absolute() else inputs.parent / original).resolve(strict=True)
        if digest(original) != DEVELOPMENT_PDF_SHA256[spec["key"]] or spec["sha256"] != digest(original):
            raise ValueError("Original de développement différent du verrou : " + spec["key"])
        documents.append({key: spec[key] for key in ("key", "sha256", "format", "url", "revision_observed", "allow_partial")
                          if key in spec} | {"path": str(original)})
        superseded.append({"document_key": spec["key"], "old_extraction_sha256": spec.get("extraction_sha256"),
                           "old_extraction_provenance": spec.get("extraction_provenance"),
                           "reused": False, "reason": "Full worker of the selected revision replaces the old page window."})
    cases = [copy.deepcopy(case) for case in frozen["cases"] if case.get("document_key") in DEVELOPMENT_PDF_SHA256]
    if len(cases) != 2 or len({case["document_key"] for case in cases}) != 2:
        raise ValueError("Les deux questions de développement I3 sont requises, sans doublon.")
    for case in cases:
        if case["scope"] != {"kind": "pages", "document_key": case["document_key"], "page_start": 0, "page_end": 0}:
            raise ValueError("Le périmètre I3 corrigé doit rester la première page, d'index zéro.")
    return {"protocol": "production-4b-I4-development-pdf", "source_manifest_sha256": digest(inputs),
            "source_manifest": str(inputs.resolve()), "documents": documents, "cases": cases,
            "superseded_extractions": superseded,
            "extraction_route": "Full original document, selected revision real worker; question scopes stay page_index 0.",
            "judgment": "unreviewed; I3 source oracles unchanged", "repeats": 1}


def worker_config(application_root: Path, runtime_root: Path) -> dict:
    profile = yaml.safe_load((application_root / "config/enhanced-4b.yaml").read_text())
    if profile["llm"]["model"] != "qwen3-4b-enhanced:q4km":
        raise ValueError("Le profil doit garder le générateur 4B verrouillé.")
    for field in ("artifacts_path", "tessdata_dir", "tesseract_cmd"):
        value = Path(profile["pdf"][field])
        if sys.platform != "win32" and field == "tesseract_cmd" and value.suffix == ".exe":
            value = value.with_suffix("")
        profile["pdf"][field] = str(value if value.is_absolute() else runtime_root / value)
    profile["pdf"]["artifacts_lock_path"] = str(runtime_root / "config/artifacts.lock.json")
    return profile


def render_scan_pair(original: Path, specification: dict, output: Path) -> dict:
    """Rendre une paire locale sans lire de manifeste/oracle ni utiliser le réseau.

    L'appelant vérifie les versions et l'original, puis fournit un dossier neuf.
    Le rendu et les métadonnées restent ceux de la transformation gelée ; les
    empreintes retournées établissent si les deux octets attendus sont retrouvés.
    """
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    png_path = output / (specification["id"] + ".png")
    pdf_path = output / (specification["id"] + ".pdf")
    if png_path.exists() or pdf_path.exists():
        raise FileExistsError("La paire dérivée existe déjà ; choisir un dossier neuf.")
    document = pdfium.PdfDocument(str(original))
    page = document[specification["original_page_index"]]
    bitmap = None
    try:
        width, height = page.get_size()
        bitmap = page.render(scale=specification["transform"]["scale"], rotation=0)
        raster = bitmap.to_pil().convert("L")
        raster.save(png_path, format="PNG")
        canvas = Canvas(str(pdf_path), pagesize=(width, height), invariant=1, pageCompression=1)
        canvas.setTitle("I4 deterministic image-only derived page")
        canvas.setAuthor("Localagent qualification")
        canvas.drawImage(ImageReader(raster), 0, 0, width=width, height=height)
        canvas.showPage()
        canvas.save()
        raster.close()
    finally:
        if bitmap is not None:
            bitmap.close()
        page.close()
        document.close()
    with pdfium.PdfDocument(str(pdf_path)) as rebuilt:
        rebuilt_page = rebuilt[0]
        text_page = rebuilt_page.get_textpage()
        embedded_text = bool(text_page.get_text_range())
        text_page.close()
        rebuilt_page.close()
    checked = {"id": specification["id"], "pdf_sha256": digest(pdf_path),
               "raster_sha256": digest(png_path), "embedded_text": embedded_text,
               "original_sha256_unchanged": digest(original) == specification["original_sha256"]}
    checked["byte_identical_to_frozen_pair"] = (checked["pdf_sha256"] == specification["sha256"]
        and checked["raster_sha256"] == specification["raster_sha256"]
        and checked["original_sha256_unchanged"] and not embedded_text)
    return checked


def reproduce_scans(base: Path, output: Path) -> None:
    """Reconstruire les deux scans dans un nouveau dossier ; ne jamais modifier le gel."""
    _, sources, _, scans = frozen_inputs(base)
    actual_versions = {name: version(name) for name in scans["versions"]}
    if actual_versions != scans["versions"]:
        raise ValueError("Versions de rendu différentes de celles du gel des scans.")
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    originals = {spec["id"]: spec for spec in sources["documents"]}
    results = []
    for specification in scans["scans"]:
        original = inside(base, originals[specification["original_document_id"]]["file"])
        results.append(render_scan_pair(original, specification, output))
    save_new(output / "reproduction-receipt.json", {"versions": actual_versions, "pairs": results})
    if not all(item["byte_identical_to_frozen_pair"] for item in results):
        raise ValueError("Reconstruction différente ; originaux et scans gelés laissés intacts.")
    print(json.dumps({"scan_pairs": len(results), "all_byte_identical": True,
                      "receipt_sha256": digest(output / "reproduction-receipt.json")}))


def source_hashes(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): digest(path) for path in sorted((root / "services").rglob("*.py"))}


def prepare_pdf(args) -> None:
    dataset = (development_pdf_dataset(args.inputs.resolve(strict=True)) if args.kind == "development-pdf"
               else transfer_dataset(args.heldout.resolve(strict=True), args.kind))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    application_root = args.application_root.resolve(strict=True)
    config = worker_config(application_root, args.runtime_root.resolve(strict=True))
    frozen_sources = source_hashes(application_root)
    plan = {"created_utc": datetime.now(UTC).isoformat(), "kind": args.kind, "dataset": dataset,
            "application_root": str(application_root), "config": config, "source_files": frozen_sources,
            "harness_sha256": digest(Path(__file__)), "worker_timeout_seconds": args.worker_timeout,
            "uv_lock_sha256": digest(application_root / "uv.lock"),
            "artifacts_lock_sha256": digest(Path(config["pdf"]["artifacts_lock_path"])),
            "libraries": {name: version(name) for name in ("pypdfium2", "docling", "docling-core", "Pillow", "torch")},
            "execution_authorized_by_cli": args.execute, "route": "full document, automatic native/structured/OCR routing"}
    save_new(output / "extraction-plan.json", plan)
    if not args.execute:
        print(json.dumps({"plan": str(output / "extraction-plan.json"), "sha256": digest(output / "extraction-plan.json"),
                          "documents": len(dataset["documents"]), "cases": len(dataset["cases"]), "executed": False}))
        return
    if not sys.platform.startswith("linux"):
        raise ValueError("Ce superviseur de qualification utilise les groupes possédés Linux.")
    sys.path.insert(0, str(ROOT))
    from services.runtime.posix_process import PosixJob
    from tools.qualification.run_grounded_native import stop_owned

    receipts = []
    active_document = None
    try:
        for spec in dataset["documents"]:
            key = spec["key"]
            active_document = key
            directory = output / (key + "-extraction")
            directory.mkdir()
            request = {"path": spec["path"], "version_id": str(uuid.uuid5(uuid.NAMESPACE_URL, spec["sha256"])),
                       "output_dir": str(directory), "config": config}
            request_path, result_path = directory / "request.json", directory / "result.json"
            save_new(request_path, request)
            env = {k: v for k, v in os.environ.items() if k.upper() not in {
                "RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "QDRANT__SERVICE__API_KEY", "RAG_DATA_DIR", "RAG_DB_PATH"}}
            env.update(PYTHONPATH=str(application_root), HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                       TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
            job = PosixJob()
            process = None
            started = time.monotonic()
            peak_rss = 0
            samples = 0
            expired = False
            stop = None
            try:
                process = job.launch([sys.executable, "-m", "services.ingestion.worker", "--request", str(request_path),
                                      "--result", str(result_path)], cwd=application_root, env=env,
                                     log_path=directory / "worker.log")
                while process.poll() is None:
                    if time.monotonic() - started > args.worker_timeout:
                        expired = True
                        break
                    try:
                        parent = psutil.Process(process.pid)
                        members = [parent, *parent.children(recursive=True)]
                        peak_rss = max(peak_rss, sum(p.memory_info().rss for p in members))
                        samples += 1
                    except psutil.Error:
                        pass
                    time.sleep(0.5)
            finally:
                if process is not None:
                    stop = stop_owned(process)
                job.close()
            receipt = {"key": key, "elapsed_seconds": time.monotonic() - started, "timeout": expired,
                       "rss_sum_peak_bytes": peak_rss, "memory_samples": samples, "stop": stop,
                       "request_sha256": digest(request_path)}
            receipts.append(receipt)
            save_new(directory / "receipt.json", receipt)
            if expired or stop is None or not stop["owned_group_empty"] or not result_path.is_file():
                raise RuntimeError("Worker non terminé proprement : " + key)
            result = json.loads(result_path.read_text())
            if result.get("ok") is not True or stop["returncode"] != 0:
                raise RuntimeError("Échec d'extraction conservé : " + key)
            extraction = result["result"]
            if extraction["sha256"] != spec["sha256"] or digest(Path(spec["path"])) != spec["sha256"]:
                raise ValueError("L'original ou son rattachement a changé.")
            frozen_path = output / (key + ".extraction.json")
            save_new(frozen_path, extraction)
            spec.update(extraction_path=str(frozen_path), extraction_sha256=digest(frozen_path),
                        extraction_provenance="real_worker_of_selected_revision_full_document",
                        extraction_status=extraction["status"], extraction_coverage=extraction.get("coverage"))
            print(json.dumps({"extracted": key, "status": extraction["status"],
                              "coverage": extraction.get("coverage"), "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)
        save_new(output / "inputs.json", dataset)
    except Exception as error:
        save_new(output / "preparation-failure.json", {"document_key": active_document,
                 "error_type": type(error).__name__, "outputs_preserved": True})
        raise
    finally:
        changed = [path for path, checksum in frozen_sources.items() if not (application_root / path).is_file()
                   or digest(application_root / path) != checksum]
        save_new(output / "preparation-receipt.json", {"documents": receipts, "changed_source_files": changed})
        if changed:
            raise RuntimeError("Code applicatif modifié pendant l'extraction.")


def prepare_http(output: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from tools.qualification.grounded_campaign import generate_document

    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    documents = []
    for key, value in (("A", "2.8"), ("B", "3.2"), ("A_new", "3.0")):
        path = output / (key + ".docx")
        checksum = generate_document({"format": "docx", "paragraphs": [
            f"Composant AX71. Supply voltage: {value} V at 70 °C."]}, path)
        documents.append({"key": key, "path": str(path.resolve()), "sha256": checksum,
                          "format": "docx", "relative_path": "http/" + ("A.docx" if key == "A_new" else key + ".docx")})
    dataset = {"protocol": "production-I4-HTTP-SSE-v1", "frozen_utc": datetime.now(UTC).isoformat(),
             "documents": documents[:2], "replacement": documents[2],
             "cases": [{"id": "HTTP01", "question": "Les documents A et B indiquent-ils la même tension d’alimentation du composant AX71 à 70 °C ?",
                        "scope": {"kind": "documents", "document_keys": ["A", "B"]},
                        "oracle": {"explicit_conflict": True, "values": ["2.8 V", "3.2 V"],
                                   "condition": "70 °C", "no_arbitration": True}, "repeats": 1}],
             "acceptance": {"actual_model_call_required": True, "no_unverified_public_delta": True,
                            "private_structured_events_not_served": True, "old_citation_and_original_immutable_after_update": True},
             "scope": "Real loopback HTTP/SSE, native Office workers, real DB/E5/Qdrant/Ollama/governor; no browser qualification"}
    save_new(output / "inputs.json", dataset)
    print(json.dumps({"inputs": str(output / "inputs.json"), "sha256": digest(output / "inputs.json"),
                      "cases": 1, "documents": 2, "replacement_versions": 1}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=("transfer", "ocr", "http", "development-pdf", "scan-reproduction"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--heldout", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--application-root", type=Path, default=ROOT)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--worker-timeout", type=int, default=1800)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.kind == "http":
        prepare_http(args.output.resolve())
    elif args.kind == "scan-reproduction":
        if args.heldout is None:
            parser.error("--heldout est requis pour reconstruire les scans gelés.")
        reproduce_scans(args.heldout.resolve(strict=True), args.output.resolve())
    else:
        if args.worker_timeout < 1 or (args.kind == "development-pdf" and args.inputs is None):
            parser.error("--inputs est requis pour development-pdf, avec un délai positif.")
        if args.kind != "development-pdf" and args.heldout is None:
            parser.error("--heldout est requis pour les PDF du transfert réservé.")
        prepare_pdf(args)


if __name__ == "__main__":
    main()
