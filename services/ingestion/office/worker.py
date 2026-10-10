"""Isolated native Office entrypoint; the existing PDF worker stays unchanged."""

import argparse
import faulthandler
import json
import logging
from pathlib import Path

from services.ingestion.checkpoint import atomic_json
from services.ingestion.errors import IngestionError
from services.ingestion.worker import private_output

from .pipeline import extract_office


def main():
    parser = argparse.ArgumentParser(description="Worker DOCX/XLSX local isolé")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    exit_code = 0
    try:
        request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        directory = Path(request["output_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        fault_path = directory / "worker-native-fault.log"
        if fault_path.is_file() and fault_path.stat().st_size:
            raise IngestionError("EXTRACTION_QUARANTINED", "Une ancienne faute native est présente ; preuves conservées, reprise refusée.")
        with fault_path.open("ab") as fault_stream:
            faulthandler.enable(file=fault_stream, all_threads=True)
            try:
                with private_output():
                    result = extract_office(request["path"], directory, request.get("config", {}), request["version_id"],
                                            request["format"], request.get("cancel_path"))
            finally:
                faulthandler.disable()
        if fault_path.stat().st_size:
            raise IngestionError("INGESTION_NATIVE_FAULT", "Une faute native a été observée ; publication refusée.")
        envelope = {"ok": True, "result": result}
    except IngestionError as error:
        envelope, exit_code = {"ok": False, "error": error.as_dict()}, 2
    except Exception:
        envelope, exit_code = {"ok": False, "error": {"code": "INGESTION_WORKER_FAILED",
                                                  "message": "L'extraction Office a échoué ; original conservé.", "details": {}}}, 3
    atomic_json(args.result, envelope)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
