"""Campagne 4B appariée sur des originaux et extractions explicitement gelés.

SQLite, E5, Qdrant, le tokenizer Qwen, QueryService et Ollama sont réels.
Le transport HTTP public et l'interface graphique ne sont pas exercés ici.
Les services sont fournis par l'opérateur ; un manifeste décrit chaque original,
son SHA-256, la provenance de l'extraction et chaque périmètre autorisé.
Aucun verdict documentaire n'est inféré automatiquement du texte d'une réponse.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import platform
import subprocess
import sys
import threading
import zipfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.execution_trace import fingerprint  # noqa: E402
from services.api.indexing import extraction_content_hash  # noqa: E402
from services.api.main import create_app  # noqa: E402
from services.api.schemas import QueryRequest, Scope, SelectedSpan  # noqa: E402
from services.api.settings import Settings  # noqa: E402
from services.ingestion.office.pipeline import extract_office  # noqa: E402
from tools.qualification.provision_enhanced_4b import file_sha256  # noqa: E402


def save(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def freeze_code(output: Path) -> dict:
    files = sorted({*ROOT.joinpath("services").rglob("*.py"), Path(__file__).resolve()})
    identities = {str(path.relative_to(ROOT)): file_sha256(path) for path in files}
    archive = output / "code-snapshot.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(ROOT))
    record = {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "snapshot_kind": "working_source_files_before_first_query", "files": identities,
              "archive_sha256": file_sha256(archive)}
    save(output / "code-manifest.json", record)
    return {"archive_sha256": record["archive_sha256"], "files_sha256": fingerprint(identities)}


class MemorySampler:
    """RSS de l'application, des services explicités et de leurs descendants.

    RSS est une somme, pas une mesure de mémoire physique exclusive. Les pages
    partagées peuvent être comptées plusieurs fois ; la réserve hôte est séparée.
    """

    def __init__(self, path: Path, service_pids: list[int]):
        self.path, self.pids = path, [os.getpid(), *service_pids]
        self.label = "initialization"
        self.stop = threading.Event()
        self.peaks: dict[str, dict] = {}
        self.thread = threading.Thread(target=self.run, daemon=True)

    def sample(self):
        processes = {}
        for pid in self.pids:
            try:
                process = psutil.Process(pid)
                for member in [process, *process.children(recursive=True)]:
                    processes[member.pid] = member
            except psutil.Error:
                continue
        measured = []
        for pid, process in processes.items():
            try:
                memory = process.memory_full_info()
                measured.append({"pid": pid, "name": process.name(), "rss_mib": memory.rss / 1048576,
                                 "pss_mib": getattr(memory, "pss", 0) / 1048576 if hasattr(memory, "pss") else None,
                                 "uss_mib": getattr(memory, "uss", 0) / 1048576 if hasattr(memory, "uss") else None})
            except psutil.Error:
                continue
        total = sum(p["rss_mib"] for p in measured)
        available = psutil.virtual_memory().available / 1048576
        peak = self.peaks.setdefault(self.label, {"rss_sum_peak_mib": 0.0, "available_min_mib": available, "samples": 0})
        peak["rss_sum_peak_mib"] = max(peak["rss_sum_peak_mib"], total)
        peak["available_min_mib"] = min(peak["available_min_mib"], available)
        peak["samples"] += 1
        for field in ("pss_mib", "uss_mib"):
            if measured and all(p[field] is not None for p in measured):
                key = field.replace("_mib", "_sum_peak_mib")
                peak[key] = max(peak.get(key, 0), sum(p[field] for p in measured))
        return {"utc": datetime.now(UTC).isoformat(), "label": self.label, "rss_sum_mib": total,
                "available_mib": available, "processes": measured}

    def run(self):
        with self.path.open("x", encoding="utf-8") as stream:
            while not self.stop.is_set():
                stream.write(json.dumps(self.sample()) + "\n")
                stream.flush()
                self.stop.wait(0.5)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)


def scope_for(case, documents, db):
    definition = case.get("scope", {"kind": "documents", "document_keys": [case["document_key"]]})
    kind = definition["kind"]
    if kind == "documents":
        return Scope(kind=kind, documentIds=[documents[key]["document_id"] for key in definition["document_keys"]])
    document = documents[definition.get("document_key", case.get("document_key"))]
    version = document["version_id"]
    if kind in {"cell_range", "sheet"}:
        extraction = document["extraction"]
        units = extraction["units"]
        name = definition.get("sheet_name", "Parametres")
        sheet = next(unit for unit in units if unit.get("name") == name or unit.get("sheet_name") == name
                     or unit.get("title") == name or unit.get("locator", {}).get("sheet_name") == name)
        values = {"kind": kind, "versionId": version, "extractionRevisionId": extraction["extraction_revision_id"],
                  "sheetId": sheet["id"]}
        if kind == "cell_range":
            from openpyxl.utils.cell import range_boundaries

            column_start, row_start, column_end, row_end = range_boundaries(definition["range"])
            values.update(rowStart=row_start, rowEnd=row_end, columnStart=column_start, columnEnd=column_end)
        return Scope(**values)
    if kind == "selection":
        text = definition["text"]
        rows = db.rows("SELECT * FROM blocks WHERE generation_id=? ORDER BY page_index,id", (document["generation_id"],))
        block = next(row for row in rows if text in row["text"] and
                     (definition.get("block_id") is None or row["id"] == definition["block_id"]))
        offset = block["text"].index(text)
        return Scope(kind=kind, versionId=version, spans=[SelectedSpan(**{
            "extractionRevisionId": block["extraction_revision_id"], "blockId": block["id"],
            "blockTextSha256": block["source_text_hash"], "offsetUnit": "unicode_code_point",
            "startOffset": offset, "endOffset": offset + len(text)})])
    if kind == "pages":
        return Scope(kind=kind, versionId=version, pageStart=definition["page_start"], pageEnd=definition["page_end"])
    raise ValueError("Périmètre de campagne non supporté")


async def campaign(profile: Path, inputs: Path, output: Path, service_pids: list[int]):
    dataset = json.loads(inputs.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    settings = Settings.load(profile)
    if settings.value("llm", "model") != "qwen3-4b-enhanced:q4km":
        raise ValueError("Cette campagne est limitée au 4B verrouillé.")
    settings.profile["app"]["data_dir"] = str(output / "data")
    settings.profile["sqlite"]["path"] = str(output / "data/app.sqlite3")
    settings.profile["trace"].update(mode="full", max_files=512, max_total_bytes=268435456, max_bytes_per_query=8388608)
    # Residency is a controlled profile input shared by both arms. In a
    # constrained host, forcing keep here would hide the adaptive policy under
    # evaluation and retain the generator before the next embedding phase.
    settings.profile["llm"].update(accelerator="cpu")
    enhanced = copy.deepcopy(settings.profile["enhanced"])
    baseline = {**enhanced, "preserve_evidence": False, "structural_reranking": False,
                "answer_contract": False, "complementary_retrieval": False}
    save(output / "protocol-frozen.json", {"created_utc": datetime.now(UTC).isoformat(), "dataset": dataset,
         "inputs_sha256": file_sha256(inputs), "profile": settings.profile,
         "source_code": freeze_code(output),
         "variants": {"baseline": baseline, "enhanced": enhanced},
         "order": "alternating baseline-first/enhanced-first by case, fresh conversation per submission",
         "judgment": "unreviewed until an explicit per-fact review is saved",
         "environment": {"platform": platform.platform(), "python": sys.version,
                         "libraries": {name: version(name) for name in (
                             "httpx", "tokenizers", "onnxruntime", "numpy", "jinja2", "pydantic", "openpyxl", "python-docx")},
                         "physical_memory_bytes": psutil.virtual_memory().total, "logical_cpus": os.cpu_count(),
                         "affinity": psutil.Process().cpu_affinity() if hasattr(psutil.Process(), "cpu_affinity") else None}})
    monitor = MemorySampler(output / "memory.jsonl", service_pids)
    monitor.thread.start()
    documents = {}
    application = create_app(settings=settings, start_jobs=False)
    try:
        async with application.router.lifespan_context(application):
            db, indexer = application.state.db, application.state.indexer
            for spec in dataset["documents"]:
                original = Path(spec["path"])
                original = (original if original.is_absolute() else inputs.parent / original).resolve()
                if file_sha256(original) != spec["sha256"]:
                    raise ValueError("Original différent du manifeste : " + spec["key"])
                imported = db.import_original(original.name, spec["sha256"], original, spec["format"])
                extraction_path = output / (spec["key"] + ".extraction.json")
                if spec.get("extraction_path"):
                    frozen = Path(spec["extraction_path"])
                    frozen = frozen if frozen.is_absolute() else inputs.parent / frozen
                    if file_sha256(frozen) != spec["extraction_sha256"]:
                        raise ValueError("Extraction gelée différente du manifeste")
                    extraction = json.loads(frozen.read_text(encoding="utf-8"))
                    if extraction["sha256"] != spec["sha256"]:
                        raise ValueError("Extraction non associée à cet original")
                else:
                    if spec["format"] not in {"docx", "xlsx"}:
                        raise ValueError("Une extraction PDF explicitement gelée est requise")
                    extraction = await asyncio.to_thread(extract_office, original, output / (spec["key"] + "-native"),
                                                        {}, imported["version_id"], spec["format"])
                save(extraction_path, extraction)
                generation = await indexer.index(imported["job_id"], extraction, str(extraction_path))
                if db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"] is None:
                    if spec.get("allow_partial") is not True:
                        raise ValueError("Extraction partielle sans autorisation explicite de campagne")
                    count = db.one("SELECT actual_chunks FROM index_generations WHERE id=?", (generation,))["actual_chunks"]
                    indexer.publish(imported["job_id"], generation, count, partial=True, allow_partial=True)
                documents[spec["key"]] = {**imported, "generation_id": generation, "extraction": extraction}
                print(json.dumps({"indexed": spec["key"], "generation_id": generation,
                                  "extraction_content_sha256": extraction_content_hash(extraction)}), flush=True)
            save(output / "bindings.json", {key: {k: v for k, v in doc.items() if k != "extraction"}
                                            for key, doc in documents.items()})
            queries = application.state.queries
            for index, case in enumerate(dataset["cases"]):
                scope = scope_for(case, documents, db)
                variants = ["baseline", "enhanced"] if index % 2 == 0 else ["enhanced", "baseline"]
                for repeat in range(case.get("repeats", 1)):
                    for variant in variants:
                        settings.profile["enhanced"] = enhanced if variant == "enhanced" else baseline
                        label = f"{case['id']}-{variant}-{repeat}"
                        monitor.label = label
                        request = QueryRequest(question=case["question"], scope=scope, mode=case.get("mode", "question"))
                        response = await queries.create_async(request)
                        query_id = response["query_id"]
                        task = queries.tasks.get(query_id)
                        if task is not None:
                            await asyncio.wait_for(asyncio.shield(task), timeout=600)
                        monitor.sample()
                        run = queries.run_detail(query_id)
                        events = db.rows("SELECT * FROM events WHERE query_id=? ORDER BY id", (query_id,))
                        citations = db.rows("SELECT source_json FROM citations WHERE query_id=?", (query_id,))
                        record = {"case_id": case["id"], "variant": variant, "repeat": repeat,
                                  "profile_sha256": fingerprint(settings.profile), "scope": scope.model_dump(),
                                  "run": run, "events": events,
                                  "citations": [json.loads(item["source_json"]) for item in citations],
                                  "memory": monitor.peaks.get(label), "judgment": {"method": "unreviewed"}}
                        save(output / (label + ".json"), record)
                        print(json.dumps({"case_id": case["id"], "variant": variant, "repeat": repeat,
                                          "state": run["state"], "elapsed_ms": run["metrics"].get("elapsed_ms"),
                                          "model_called": run["metrics"].get("model_called"),
                                          "memory": record["memory"]}), flush=True)
    finally:
        monitor.close()
        save(output / "memory-peaks.json", monitor.peaks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/enhanced-4b.yaml")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--service-pid", type=int, action="append", default=[])
    args = parser.parse_args()
    asyncio.run(campaign(args.profile, args.inputs, args.output.resolve(), args.service_pid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
