"""Expérience E1 : Tesseract CLI seul sur des cellules de grille déjà conservées.

Lit en lecture seule les PNG d'un diagnostic conservé, vérifie leurs SHA-256
contre son proof-status.json, applique `regional_grid.bounded_cell_crop` puis
Tesseract psm 6 ; psm 7, 8 puis 10 seulement si psm 6 est vide ou sous le seuil,
sans consulter la valeur attendue. Écrit un rapport JSON exclusif. N'importe ni
Docling, ni Torch, ni modèle de layout ; ne modifie aucun fichier d'entrée.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.ingestion.regional_grid import (  # noqa: E402
    bounded_cell_crop,
    read_tesseract_tsv,
    temporary_raster,
)
from services.runtime.platforms import native_executable  # noqa: E402

DIAGNOSTIC = ROOT / ".runtime/qa/ingestion-synthetic/tesseract-aspect-diagnostic-20260930T040453Z"
# Exécutable du profil (`tesseract.exe` sous Windows, même emplacement sans suffixe sous Linux).
TESSERACT = ROOT / native_executable(".runtime/bin/tesseract-5.4.0/tesseract.exe")
TESSDATA = ROOT / ".runtime/models/tessdata"
REPORTS = ROOT / "RAG_Local_Agents/reports/ingestion"
# Valeurs de la fixture synthétique pour les cellules fautives du rendu nominal.
TARGETS = {5: "V", 8: "°C", 11: "A"}
WITNESSES = (0, 1, 2, 3, 4)
FALLBACK_PSM = (7, 8, 10)
LANGUAGES = ("fra", "eng")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def recorded_hashes(directory: Path) -> dict:
    status = json.loads((directory / "proof-status.json").read_text(encoding="utf-8", errors="replace"))
    return {entry["path"]: entry["sha256"] for entry in status.get("files", [])}


def tesseract_words(image_path: str, psm: int) -> tuple[list[dict], int]:
    command = [str(TESSERACT), "-l", "+".join(LANGUAGES), "--tessdata-dir", str(TESSDATA),
               "--psm", str(psm), image_path, "stdout", "tsv"]
    process = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, timeout=30, check=False,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if process.returncode:
        return [], process.returncode
    frame = read_tesseract_tsv(process.stdout.decode("utf-8"))
    return [{"text": str(row["text"]), "confidence": float(row["conf"]) / 100} for _, row in frame.iterrows()], 0


def summarize(words: list[dict]) -> dict:
    return {"text": " ".join(word["text"] for word in words),
            "minimum_word_confidence": min((word["confidence"] for word in words), default=None)}


def baseline(directory: Path, prefix: str, index: int) -> dict:
    """Sortie psm 6 déjà conservée sur la cellule complète, sans recadrage."""
    tsv = directory / f"{prefix}-cell{index}.tsv"
    if not tsv.is_file():
        return {"available": False}
    frame = read_tesseract_tsv(tsv.read_text(encoding="utf-8"))
    words = [{"text": str(row["text"]), "confidence": float(row["conf"]) / 100} for _, row in frame.iterrows()]
    return {"available": True, "tsv_sha256": sha256_path(tsv), "words": words, **summarize(words)}


def probe_cell(directory: Path, prefix: str, index: int, threshold: float, hashes: dict, border: int, inset: int = 0) -> dict:
    from PIL import Image

    name = f"{prefix}-cell{index}.png"
    source = directory / name
    actual = sha256_path(source)
    if hashes.get(name) != actual:
        raise SystemExit(f"Empreinte d'entrée divergente ou absente de proof-status.json : {name}")
    with Image.open(source) as image:
        raster = image.convert("RGB")
    # inset > 0 : hypothèse exploratoire (résidus de règles au bord), hors politique du pipeline.
    patch, offset = bounded_cell_crop(raster, [inset, inset, raster.width - inset, raster.height - inset], border=border)
    record: dict[str, Any] = {"input": name, "input_sha256": actual, "input_size": list(raster.size),
                              "crop": {"policy": f"ink_border_{border}", "inset": inset, "raster_offset": list(offset) if offset else None,
                                       "raster_size": list(patch.size) if patch else None,
                                       "patch_sha256": sha256_bytes(patch.tobytes()) if patch else None},
                              "baseline_full_cell_psm6": baseline(directory, prefix, index), "attempts": []}
    if patch is None:
        record["selected"] = {"psm": None, "text": "", "minimum_word_confidence": None, "reason": "no_ink"}
        return record
    with temporary_raster(patch) as target:
        for psm in (6, *FALLBACK_PSM):
            words, code = tesseract_words(target, psm)
            attempt = {"psm": psm, "returncode": code, "words": words, **summarize(words)}
            record["attempts"].append(attempt)
            confident = attempt["minimum_word_confidence"] is not None and attempt["minimum_word_confidence"] >= threshold
            if confident:
                break
    selected = next((attempt for attempt in record["attempts"] if attempt["minimum_word_confidence"] is not None
                     and attempt["minimum_word_confidence"] >= threshold), record["attempts"][0])
    record["selected"] = {key: selected[key] for key in ("psm", "text", "minimum_word_confidence")}
    return record


def passes(result: dict, expected: str, threshold: float) -> bool:
    return result["text"] == expected and result["minimum_word_confidence"] is not None and result["minimum_word_confidence"] >= threshold


def main() -> int:
    parser = argparse.ArgumentParser(description="E1 : OCR Tesseract des cellules conservées avec recadrage borné sur l'encre")
    parser.add_argument("--diagnostic", type=Path, default=DIAGNOSTIC)
    parser.add_argument("--prefix", default="0-render", help="Jeu de cellules du diagnostic (rendu nominal par défaut)")
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--border", type=int, default=10)
    parser.add_argument("--inset", type=int, default=0, help="Exploratoire : retrait du bord avant détection d'encre (0 = E1 nominal)")
    parser.add_argument("--min-available-mib", type=int, default=3072)
    args = parser.parse_args()
    import psutil

    available = psutil.virtual_memory().available // 1048576
    if available < args.min_available_mib:
        print(json.dumps({"status": "BLOCKED", "reason": "memoire_insuffisante", "available_mib": available}))
        return 3
    directory = args.diagnostic.resolve()
    hashes = recorded_hashes(directory)
    started = dt.datetime.now(dt.UTC)
    cells = {}
    for index in (*WITNESSES, *TARGETS):
        cells[index] = probe_cell(directory, args.prefix, index, args.threshold, hashes, args.border, args.inset)
        role = "target" if index in TARGETS else "witness"
        expected = TARGETS[index] if role == "target" else cells[index]["baseline_full_cell_psm6"].get("text")
        first = cells[index]["attempts"][0] if cells[index]["attempts"] else {"text": "", "minimum_word_confidence": None}
        cells[index].update(role=role, expected_text=expected,
                            psm6_pass=expected is not None and passes(first, expected, args.threshold),
                            with_fallback_pass=expected is not None and passes(cells[index]["selected"], expected, args.threshold))
    psm6 = all(cell["psm6_pass"] for cell in cells.values())
    fallback = all(cell["with_fallback_pass"] for cell in cells.values())
    status = "PASS" if psm6 else "PASS_WITH_FALLBACK_ONLY" if fallback else "FAIL"
    if args.inset:
        status = f"EXPLORATORY_{status}"
    version = subprocess.run([str(TESSERACT), "--version"], capture_output=True, stdin=subprocess.DEVNULL, timeout=15, check=False,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    report = {"experiment": "E1-ocr-cell-ink-crop", "status": status,
              "criterion": "Cellules 5/8/11 exactement « V », « °C », « A » avec confiance minimale de mot >= seuil ; "
                           "témoins 0-4 : texte identique à la sortie psm 6 conservée et confiance >= seuil. "
                           "PASS exige psm 6 seul (politique du pipeline) ; le repli psm 7/8/10 est déclenché "
                           "par une sortie vide ou sous le seuil, jamais par la valeur attendue.",
              "started_utc": started.isoformat(), "finished_utc": dt.datetime.now(dt.UTC).isoformat(),
              "available_memory_mib_before": available,
              "scope": "Tesseract CLI seul ; aucun Docling, Torch ni modèle de layout ; entrées en lecture seule.",
              "inputs": {"diagnostic": directory.relative_to(ROOT).as_posix() if directory.is_relative_to(ROOT) else str(directory),
                         "prefix": args.prefix, "hashes_verified_against": "proof-status.json"},
              "parameters": {"threshold": args.threshold, "border": args.border, "inset": args.inset, "languages": list(LANGUAGES),
                             "nominal_psm": 6, "fallback_psm": list(FALLBACK_PSM),
                             "edge": inspect.signature(bounded_cell_crop).parameters["edge"].default},
              # Relie le verdict à la révision exacte du recadrage et de l'outil.
              "code": {path.relative_to(ROOT).as_posix(): sha256_path(path)
                       for path in (ROOT / "services/ingestion/regional_grid.py", Path(__file__).resolve())},
              "tesseract": {"executable": TESSERACT.relative_to(ROOT).as_posix(), "sha256": sha256_path(TESSERACT),
                            "version": version.stdout.decode("utf-8", "replace").splitlines()[0] if version.stdout else None,
                            "tessdata": TESSDATA.relative_to(ROOT).as_posix(),
                            "tessdata_sha256": {name: sha256_path(TESSDATA / name) for name in
                                                (*(f"{language}.traineddata" for language in LANGUAGES), "configs/tsv")}},
              "summary": {"psm6_all_pass": psm6, "with_fallback_all_pass": fallback,
                          "cells": {str(index): {"role": cell["role"], "expected": cell["expected_text"],
                                                 "psm6": {key: (cell["attempts"][0] if cell["attempts"] else {}).get(key) for key in ("text", "minimum_word_confidence")},
                                                 "selected": cell["selected"], "psm6_pass": cell["psm6_pass"],
                                                 "with_fallback_pass": cell["with_fallback_pass"]} for index, cell in cells.items()}},
              "cells": [cells[index] for index in sorted(cells)]}
    REPORTS.mkdir(parents=True, exist_ok=True)
    target = REPORTS / f"ocr-cell-probe-{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": status, "report": target.relative_to(ROOT).as_posix(), "psm6_all_pass": psm6, "with_fallback_all_pass": fallback}, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
