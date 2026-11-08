"""Comparer deux révisions réelles avec le même harnais et des entrées gelées.

Une invocation exécute une seule révision et un bloc de questions. Le dossier
applicatif est choisi avant tout import services. Tous les mécanismes enhanced
restent actifs. Les services natifs sont fournis par l'opérateur. Les verdicts
documentaires nécessitent une revue explicite, distincte de cette mesure.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import psutil


def load_application(root: Path):
    """Charger les helpers de la révision choisie, sans mélange de services."""
    root = root.resolve(strict=True)
    if any(name == "services" or name.startswith("services.") for name in sys.modules):
        raise RuntimeError("Une application est déjà importée dans ce processus.")
    helper = root / "tools/qualification/enhanced_campaign.py"
    spec = importlib.util.spec_from_file_location("revision_campaign_adapter", helper)
    if spec is None or spec.loader is None:
        raise ValueError("Révision sans harnais de qualification compatible.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, loaded in sys.modules.items():
        filename = getattr(loaded, "__file__", None)
        if name.startswith("services.") and filename and not Path(filename).resolve().is_relative_to(root):
            raise RuntimeError(f"Import applicatif extérieur à la révision choisie : {name}")
    return module


def select_cases(dataset: dict, requested: list[str]) -> list[dict]:
    cases = dataset["cases"]
    available = [case["id"] for case in cases]
    if len(set(available)) != len(available):
        raise ValueError("Le jeu gelé contient des identifiants de question dupliqués.")
    if not requested:
        return cases
    if len(set(requested)) != len(requested) or set(requested) - set(available):
        raise ValueError("Bloc contenant une question inconnue ou dupliquée.")
    # L'ordre reste celui du manifeste, indépendamment de l'ordre CLI.
    return [case for case in cases if case["id"] in requested]


async def campaign(args, application):
    dataset = json.loads(args.inputs.read_text(encoding="utf-8"))
    cases = select_cases(dataset, args.case_id)
    args.output.mkdir(parents=True, exist_ok=False)
    args.output.chmod(0o700)
    settings = application.Settings.load(args.profile)
    if settings.value("llm", "model") != "qwen3-4b-enhanced:q4km":
        raise ValueError("Cette campagne est limitée au 4B verrouillé.")
    required_flags = ("preserve_evidence", "structural_reranking", "answer_contract", "complementary_retrieval")
    if any(settings.value("enhanced", flag) is not True for flag in required_flags):
        raise ValueError("La comparaison de révisions exige les quatre mécanismes enhanced actifs.")
    if any(os.environ.get(key) for key in ("RAG_DATA_DIR", "RAG_DB_PATH")):
        raise ValueError("Un chemin externe de stockage empêche l'isolation de la campagne.")
    settings.profile["app"]["data_dir"] = str(args.output / "data")
    settings.profile["sqlite"]["path"] = str(args.output / "data/app.sqlite3")
    settings.profile["trace"].update(mode="full", max_files=512, max_total_bytes=268435456,
                                     max_bytes_per_query=8388608)
    settings.profile["llm"].update(accelerator="cpu")
    harness = Path(__file__).resolve()
    (args.output / "measurement-harness.py").write_bytes(harness.read_bytes())
    (args.output / "source-diff.patch").write_bytes(subprocess.check_output(
        ["git", "diff", "HEAD", "--binary"], cwd=args.application_root))
    (args.output / "source-status.txt").write_bytes(subprocess.check_output(
        ["git", "status", "--short"], cwd=args.application_root))
    application.save(args.output / "protocol-frozen.json", {
        "created_utc": datetime.now(UTC).isoformat(), "dataset": dataset,
        "inputs_sha256": application.file_sha256(args.inputs),
        "profile_file_sha256": application.file_sha256(args.profile),
        "profile": settings.profile, "source_code": application.freeze_code(args.output),
        "application_root": str(args.application_root), "revision_label": args.revision_label,
        "measurement_harness_sha256": application.file_sha256(harness),
        "case_order": [case["id"] for case in cases],
        "order": "single revision block; fresh conversation per submission; no favorable retry",
        "judgment": "unreviewed until an explicit per-fact review is saved",
        "environment": {"platform": platform.platform(), "python": sys.version,
                        "libraries": {name: version(name) for name in (
                            "httpx", "tokenizers", "onnxruntime", "numpy", "jinja2", "pydantic", "openpyxl", "python-docx")},
                        "physical_memory_bytes": psutil.virtual_memory().total,
                        "logical_cpus": os.cpu_count(),
                        "affinity": psutil.Process().cpu_affinity() if hasattr(psutil.Process(), "cpu_affinity") else None},
    })
    monitor = application.MemorySampler(args.output / "memory.jsonl", args.service_pid)
    monitor.thread.start()
    documents = {}
    active_attempt = None
    try:
        app = application.create_app(settings=settings, start_jobs=False)
        async with app.router.lifespan_context(app):
            db, indexer = app.state.db, app.state.indexer
            for spec in dataset["documents"]:
                original = Path(spec["path"])
                original = (original if original.is_absolute() else args.inputs.parent / original).resolve()
                if application.file_sha256(original) != spec["sha256"]:
                    raise ValueError("Original différent du manifeste : " + spec["key"])
                imported = db.import_original(original.name, spec["sha256"], original, spec["format"])
                extraction_path = args.output / (spec["key"] + ".extraction.json")
                if spec.get("extraction_path"):
                    frozen = Path(spec["extraction_path"])
                    frozen = frozen if frozen.is_absolute() else args.inputs.parent / frozen
                    if application.file_sha256(frozen) != spec["extraction_sha256"]:
                        raise ValueError("Extraction gelée différente du manifeste")
                    extraction = json.loads(frozen.read_text(encoding="utf-8"))
                    if extraction["sha256"] != spec["sha256"]:
                        raise ValueError("Extraction non associée à cet original")
                else:
                    if spec["format"] not in {"docx", "xlsx"}:
                        raise ValueError("Une extraction PDF explicitement gelée est requise")
                    extraction = await asyncio.to_thread(
                        application.extract_office, original, args.output / (spec["key"] + "-native"),
                        {}, imported["version_id"], spec["format"])
                application.save(extraction_path, extraction)
                generation = await indexer.index(imported["job_id"], extraction, str(extraction_path))
                if db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"] is None:
                    if spec.get("allow_partial") is not True:
                        raise ValueError("Extraction partielle sans autorisation explicite de campagne")
                    count = db.one("SELECT actual_chunks FROM index_generations WHERE id=?", (generation,))["actual_chunks"]
                    indexer.publish(imported["job_id"], generation, count, partial=True, allow_partial=True)
                documents[spec["key"]] = {**imported, "generation_id": generation, "extraction": extraction}
                print(json.dumps({"indexed": spec["key"], "generation_id": generation,
                                  "extraction_content_sha256": application.extraction_content_hash(extraction)}), flush=True)
            application.save(args.output / "bindings.json", {
                key: {k: v for k, v in doc.items() if k != "extraction"} for key, doc in documents.items()})
            queries = app.state.queries
            for case in cases:
                for repeat in range(case.get("repeats", 1)):
                    label = f"{case['id']}-{args.revision_label}-{repeat}"
                    active_attempt = {"case_id": case["id"], "variant": args.revision_label,
                                      "repeat": repeat, "query_id": None,
                                      "started_utc": datetime.now(UTC).isoformat()}
                    application.save(args.output / (label + ".attempt-start.json"), active_attempt)
                    monitor.label = label
                    scope = application.scope_for(case, documents, db)
                    request = application.QueryRequest(question=case["question"], scope=scope,
                                                       mode=case.get("mode", "question"))
                    response = await queries.create_async(request)
                    query_id = response["query_id"]
                    active_attempt["query_id"] = query_id
                    task = queries.tasks.get(query_id)
                    timeout = False
                    if task is not None:
                        try:
                            await asyncio.wait_for(asyncio.shield(task), timeout=600)
                        except TimeoutError:
                            timeout = True
                            await queries.cancel_async(query_id)
                            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=30)
                    monitor.sample()
                    run = queries.run_detail(query_id)
                    events = db.rows("SELECT * FROM events WHERE query_id=? ORDER BY id", (query_id,))
                    citations = db.rows("SELECT source_json FROM citations WHERE query_id=?", (query_id,))
                    record = {"case_id": case["id"], "variant": args.revision_label, "repeat": repeat,
                              "profile_sha256": application.fingerprint(settings.profile),
                              "scope": scope.model_dump(), "run": run, "events": events,
                              "citations": [json.loads(item["source_json"]) for item in citations],
                              "memory": monitor.peaks.get(label), "harness_timeout": timeout,
                              "judgment": {"method": "unreviewed"}}
                    application.save(args.output / (label + ".json"), record)
                    active_attempt = None
                    print(json.dumps({"case_id": case["id"], "variant": args.revision_label, "repeat": repeat,
                                      "state": run["state"], "elapsed_ms": run["metrics"].get("elapsed_ms"),
                                      "model_called": run["metrics"].get("model_called"),
                                      "memory": record["memory"]}), flush=True)
    except Exception as error:
        application.save(args.output / "block-failure.json", {
            "failed_utc": datetime.now(UTC).isoformat(), "active_attempt": active_attempt,
            "error_type": type(error).__name__, "message": str(error),
            "kind": "harness_or_application_exception; not an inferred application terminal",
        })
        raise
    finally:
        monitor.close()
        application.save(args.output / "memory-peaks.json", monitor.peaks)
        frozen = json.loads((args.output / "code-manifest.json").read_text(encoding="utf-8"))
        changed = [name for name, digest in frozen["files"].items()
                   if not (args.application_root / name).is_file()
                   or application.file_sha256(args.application_root / name) != digest]
        application.save(args.output / "source-stability.json", {"changed_since_freeze": changed})
        if changed:
            raise RuntimeError("Sources applicatives modifiées pendant le bloc de campagne.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--revision-label", choices=("iteration1", "iteration2", "baseline", "candidate"), required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--service-pid", type=int, action="append", default=[])
    args = parser.parse_args()
    for name in ("application_root", "profile", "inputs", "output"):
        setattr(args, name, getattr(args, name).resolve())
    asyncio.run(campaign(args, load_application(args.application_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
