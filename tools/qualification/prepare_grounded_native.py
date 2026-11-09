"""Préparer dix questions natives I3, originaux et oracles avant toute réponse.

Les huit cas Office sont dérivés de la matrice contrôlée figée. Les deux PDF
proviennent de Texas Instruments ; seule leur première page est extraite par
la voie native réelle, explicitement publiée comme extraction partielle.
Ce script de qualification télécharge uniquement avec --download-official.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.ingestion.pipeline import extract_window, stitch_structure  # noqa: E402
from tools.qualification.grounded_campaign import digest_file, generate_document, save_json  # noqa: E402

SELECTED = ("P01_general_condition", "P05_sparse_table", "P10_decimal_sum", "P11_conversion",
            "L01_condition_mismatch", "L06_cross_document_conflict", "L13_negated_value", "L16_table_note")
OFFICIAL: tuple[dict[str, Any], ...] = (
    {"key": "ina226", "url": "https://www.ti.com/lit/ds/symlink/ina226.pdf",
     "sha256": "c9b67f886d4a5241a5e070723f7b61867409eeb27eed768b9cdd9cb17e03ca2d",
     "revision_observed": "SBOS547C, revised August 2026",
     "question": "Quelles sont les plages de tension de bus et d'alimentation de l'INA226 ?",
     "required_facts": ["bus 0–36 V", "alimentation 2,7–5,5 V"]},
    {"key": "tmp117", "url": "https://www.ti.com/lit/ds/symlink/tmp117.pdf",
     "sha256": "78212e91e478035a91165397a8de8a90bfc776759dc445243c033537f0c4b789",
     "revision_observed": "SNOSD82D, revised September 2022",
     "question": "Quelles sont les deux plages d'alimentation du TMP117 avec leurs conditions de température ?",
     "required_facts": ["1,7–5,5 V pour −55–70 °C", "1,8–5,5 V pour −55–150 °C"]},
)


def prepare(output: Path, download_official: bool, pdf_directory: Path | None):
    if not download_official and pdf_directory is None:
        raise ValueError("Fournir --pdf-directory ou autoriser --download-official.")
    output.mkdir(parents=True, exist_ok=False)
    corpus = output / "originals"
    corpus.mkdir()
    fixture_path = ROOT / "tests/fixtures/grounded_cases.json"
    fixture = json.loads(fixture_path.read_text())
    documents, cases = [], []
    for spec in OFFICIAL:
        path = corpus / (spec["key"] + ".pdf")
        if download_official:
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "agentragpdf-qualification/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
        else:
            assert pdf_directory is not None
            path.write_bytes((pdf_directory / path.name).read_bytes())
        if not path.read_bytes().startswith(b"%PDF-"):
            raise ValueError("L'original téléchargé n'est pas un PDF : " + spec["key"])
        original_hash = digest_file(path)
        if original_hash != spec["sha256"]:
            raise ValueError("L'original diffère de la révision figée ; conserver le fichier et établir un nouveau corpus : " + spec["key"])
        extraction = extract_window(path, str(uuid.uuid5(uuid.NAMESPACE_URL, original_hash)), 0, 0,
                                    {"pipeline_route": "native", "pdf_backend": "pypdfium2"},
                                    output / (spec["key"] + "-extraction"))
        extraction["sections"], extraction["tables"] = stitch_structure(extraction["pages"])
        extraction["status"] = "ready_partial"
        extraction["coverage"] = {"total": extraction["page_count"], "processed": len(extraction["pages"]),
                                  "ocr": 0, "unresolved": extraction["page_count"] - len(extraction["pages"])}
        extraction["warnings"].append({"code": "qualification_first_page_only",
                                       "message": "Fenêtre native limitée volontairement à la première page de l'original."})
        frozen = output / (spec["key"] + ".extraction.json")
        save_json(frozen, extraction)
        key = spec["key"]
        documents.append({"key": key, "path": str(path.resolve()), "sha256": original_hash,
                          "format": "pdf", "url": spec["url"], "revision_observed": spec["revision_observed"],
                          "allow_partial": True, "extraction_path": str(frozen.resolve()),
                          "extraction_sha256": digest_file(frozen), "extraction_provenance": "real_native_window_page_1"})
        cases.append({"id": "N_" + key, "document_key": key, "question": spec["question"],
                      "scope": {"kind": "pages", "document_key": key, "page_start": 0, "page_end": 0},
                      "oracle": {"answerable": True, "required_facts": spec["required_facts"],
                                 "support": "Every numeric relationship and its condition must appear in the cited source."}})
    for original in fixture["cases"]:
        if original["id"] not in SELECTED:
            continue
        keys = {}
        for spec in original["documents"]:
            key = original["id"] + "_" + spec["key"]
            keys[spec["key"]] = key
            path = corpus / (key + "." + spec["format"])
            checksum = generate_document(spec, path)
            documents.append({"key": key, "path": str(path.resolve()), "sha256": checksum,
                              "format": spec["format"], "extraction_provenance": "native_office_repeated_each_arm"})
        case = {"id": original["id"], "question": original["question"], "document_key": keys[next(iter(keys))],
                "oracle": original}
        scope = dict(original.get("scope", {"kind": "documents"}))
        if scope["kind"] == "documents":
            scope["document_keys"] = [keys[key] for key in scope.pop("document_keys", list(keys))]
        else:
            scope["document_key"] = keys[scope.pop("document", next(iter(keys)))]
            scope.setdefault("sheet_name", "Parametres")
        case["scope"] = scope
        cases.append(case)
    value = {"protocol": "grounded-4b-native-I3", "frozen_utc": datetime.now(UTC).isoformat(),
             "fixture_sha256": digest_file(fixture_path), "documents": documents, "cases": cases,
             "order": "baseline then candidate; fresh stores and conversations; same source bytes and model; no favorable retries",
             "limitations": ["Two official PDF page windows; eight controlled Office cases are not independent external documents",
                             "QueryService and native engines; public HTTP and browser covered separately, not by this campaign",
                             "Case-level explicit review required; automatic contract status is not the oracle"]}
    save_json(output / "inputs.json", value)
    print(json.dumps({"inputs": str(output / "inputs.json"), "sha256": digest_file(output / "inputs.json"),
                      "cases": len(cases), "documents": len(documents)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download-official", action="store_true")
    parser.add_argument("--pdf-directory", type=Path)
    args = parser.parse_args()
    prepare(args.output.resolve(), args.download_official, args.pdf_directory)


if __name__ == "__main__":
    main()
