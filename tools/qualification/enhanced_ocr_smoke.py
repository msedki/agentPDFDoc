"""Three bounded OCR component checks using real Tesseract on synthetic images.

The second and third cases inject an ambiguous baseline; their candidate is
produced by the real engine. This is not a full Docling/PDF ingestion benchmark.
Outputs are exclusive, private QA files. No existing extraction is modified.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.ingestion.numeric_evidence import literal  # noqa: E402
from services.ingestion.regional_grid import bounded_cell_crop, read_tesseract_tsv  # noqa: E402
from services.ingestion.regional_row_context import recognize_grid_rows  # noqa: E402
from tools.qualification.evidence_io import (  # noqa: E402
    LOCAL_QA,
    checked_output,
    file_sha256,
    write_json_exclusive,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--numeric-density-factor", type=int, choices=(1, 2), default=1)
    args = parser.parse_args(argv)
    output = checked_output(args.output, [LOCAL_QA])
    executable = shutil.which(args.tesseract)
    if executable is None or not args.font.is_file():
        parser.error("Tesseract et la police locale doivent être disponibles avant l'essai.")
    output.mkdir(parents=True, exist_ok=False)
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(args.font), 30)
    cells = [[20, 20, 350, 75], [370, 20, 720, 75], [20, 85, 350, 145], [370, 85, 720, 145]]
    image = Image.new("RGB", (760, 170), "white")
    draw = ImageDraw.Draw(image)
    for text, position in (("Min", (35, 25)), ("Max", (385, 25)), ("0 V", (35, 90)), ("36 V", (385, 90))):
        draw.text(position, text, font=font, fill="black")
    image.save(output / "source-volts.png")
    calls: list[dict[str, Any]] = []

    def recognize(patch):
        number = len(calls)
        path = output / f"ocr-input-{number:02d}.png"
        patch.save(path)
        command = [executable, str(path), "stdout", "-l", "eng", "--psm", "6", "tsv"]
        started = time.perf_counter()
        result = subprocess.run(command, capture_output=True, check=True, timeout=30, stdin=subprocess.DEVNULL)
        elapsed = time.perf_counter() - started
        (output / f"ocr-result-{number:02d}.tsv").write_bytes(result.stdout)
        calls.append({"input": path.name, "input_sha256": file_sha256(path), "psm": 6, "language": "eng",
                      "elapsed_s": elapsed, "returncode": result.returncode})
        return read_tesseract_tsv(result.stdout.decode("utf-8"))

    baselines, evidence = [], []
    for box in cells:
        patch, offset = bounded_cell_crop(image, box)
        if patch is None:
            raise RuntimeError("Fixture synthétique sans encre")
        frame = recognize(patch)
        frame["left"] += offset[0]
        frame["top"] += offset[1]
        baselines.append(frame)
        evidence.append({"printed": True, "crop": {"policy": "ink_border_10", "density_retry": {"attempted": False}}})

    cases = []
    for name, fault, unit in (("native_baselines", False, "V"),
                              ("injected_ambiguity_real_retry", True, "V"),
                              ("injected_unit_conflict_real_retry", True, "A")):
        raster = image.copy()
        if unit == "A":
            raster.paste("white", (20, 85, 350, 145))
            ImageDraw.Draw(raster).text((35, 90), "0 A", font=font, fill="black")
            raster.save(output / "source-unit-conflict.png")
        inputs = [frame.copy(deep=True) for frame in baselines]
        if fault:
            # Fault injection is explicit; not represented as an observed baseline OCR error.
            inputs[2] = inputs[2].iloc[:1].copy()
            inputs[2]["text"] = "OV"
            inputs[2]["conf"] = 95.0
        cell_evidence = copy.deepcopy(evidence)
        readings: list[dict[str, Any]] = []
        selected, traces, budget = recognize_grid_rows(raster, cells, inputs, cell_evidence, recognize, .8,
                                                       13_000_000, private_numeric_readings=readings,
                                                       numeric_density_factor=args.numeric_density_factor)
        texts = [literal(frame) for frame in selected]
        if name == "native_baselines":
            passed = texts[2].replace(" ", "") == "0V" and texts[3].replace(" ", "") == "36V"
        elif unit == "V":
            passed = (budget["additional_ocr_calls"] == 1 and texts[2].replace(" ", "") == "0V"
                      and cell_evidence[2].get("numeric_ambiguity_unresolved") is False)
        else:
            passed = (budget["additional_ocr_calls"] == 1 and texts[2] == "OV"
                      and cell_evidence[2].get("numeric_ambiguity_unresolved") is True)
        cases.append({"case": name, "baseline_fault_injected": fault, "selected_texts": texts,
                      "status": "PASS" if passed else "FAIL", "traces": traces, "budget": budget,
                      "private_numeric_readings": readings})
    version = subprocess.run([executable, "--version"], capture_output=True, check=True, text=True, timeout=10)
    report = {
        "scope": "Synthetic image / real Tesseract component checks; no Docling or full PDF ingestion",
        "tesseract_version": version.stdout.splitlines()[0], "tesseract_sha256": file_sha256(Path(executable)),
        "font_sha256": file_sha256(args.font), "threshold": .8, "numeric_density_factor": args.numeric_density_factor,
        "source_hashes": {str(path.relative_to(ROOT)): file_sha256(path) for path in
                          [Path(__file__), ROOT / "services/ingestion/numeric_evidence.py",
                           ROOT / "services/ingestion/regional_row_context.py"]},
        "calls": calls, "cases": cases,
        "passed": sum(case["status"] == "PASS" for case in cases), "total": len(cases),
    }
    write_json_exclusive(output / "result.json", report)
    print(json.dumps({"output": str(output / "result.json"), "passed": report["passed"], "total": report["total"],
                      "cases": [{"case": c["case"], "status": c["status"], "texts": c["selected_texts"]} for c in cases]}, ensure_ascii=False))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
