"""Fresh-process CLI. No inherited handles, stores or private console output."""

import argparse
import contextlib
import faulthandler
import json
import logging
import os
from pathlib import Path

from .checkpoint import atomic_json
from .errors import IngestionError


@contextlib.contextmanager
def private_output():
    """Suppress Python and native-library descriptors in this isolated worker."""
    with open(os.devnull, "w", encoding="utf-8") as sink:
        saved = {descriptor: os.dup(descriptor) for descriptor in (1, 2)}
        try:
            for descriptor in saved:
                os.dup2(sink.fileno(), descriptor)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
        finally:
            for descriptor, original in saved.items():
                os.dup2(original, descriptor)
                os.close(original)


def main():
    parser = argparse.ArgumentParser(description="Worker PDF local isolé")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    exit_code = 0
    try:
        request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        from .pipeline import extract_pdf, extract_window
        fault_path = Path(request["output_dir"]) / "worker-native-fault.log"
        fault_path.parent.mkdir(parents=True, exist_ok=True)
        if fault_path.is_file() and fault_path.stat().st_size:
            atomic_json(fault_path.parent / "native-fault.json", {"code": "INGESTION_NATIVE_FAULT", "fault_log": fault_path.name})
            raise IngestionError("EXTRACTION_QUARANTINED", "Un ancien journal de faute native est présent ; les preuves sont conservées et l'extraction ne peut pas être reprise.")
        with fault_path.open("ab") as fault_stream:
            fault_start = fault_stream.tell()
            os.environ["RAG_NATIVE_FAULT_LOG"] = str(fault_path.resolve())
            os.environ["RAG_NATIVE_FAULT_START"] = str(fault_start)
            os.environ["RAG_INGESTION_LIFECYCLE_TRACE"] = str((fault_path.parent / "worker-lifecycle.jsonl").resolve())
            faulthandler.enable(file=fault_stream, all_threads=True)
            try:
                with private_output():
                    if "page_start" in request:
                        result = extract_window(request["path"], request["version_id"], request["page_start"], request["page_end"], request.get("config", {}), request["output_dir"], request.get("cancel_path"))
                    else:
                        result = extract_pdf(request["path"], request["output_dir"], request.get("config", {}), request["version_id"], request.get("cancel_path"))
            finally:
                faulthandler.disable()
                os.environ.pop("RAG_NATIVE_FAULT_LOG", None)
                os.environ.pop("RAG_NATIVE_FAULT_START", None)
                os.environ.pop("RAG_INGESTION_LIFECYCLE_TRACE", None)
            fault_stream.flush()
        if fault_path.stat().st_size > fault_start:
            raise IngestionError("INGESTION_NATIVE_FAULT", "Une exception native a été observée ; l'extraction ne peut pas être publiée.", {"fault_log": fault_path.name})
        result = {"ok": True, "result": result}
    except IngestionError as exc:
        native_fault = "fault_path" in locals() and fault_path.is_file() and fault_path.stat().st_size > (fault_start if "fault_start" in locals() else 0)
        if native_fault:
            atomic_json(Path(request["output_dir"]) / "native-fault.json", {"code": exc.code, "fault_log": "worker-native-fault.log"})
        result, exit_code = {"ok": False, "error": exc.as_dict()}, 2
    except Exception:
        if "fault_path" in locals() and fault_path.is_file() and fault_path.stat().st_size:
            atomic_json(Path(request["output_dir"]) / "native-fault.json", {"code": "INGESTION_NATIVE_FAULT", "fault_log": fault_path.name})
        result, exit_code = {"ok": False, "error": {"code": "INGESTION_WORKER_FAILED", "message": "Le worker PDF a échoué.", "details": {}}}, 3
    atomic_json(args.result, result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
