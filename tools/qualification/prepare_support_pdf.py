"""Prepare two controlled PDF originals and their real native extractions.

This development supplement shares no held-out sources. It measures literal
extraction separately; the native campaign measures retrieval and rendering.
No OCR, network request or model inference is performed by this preparer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.ingestion import extract_pdf  # noqa: E402

CLAUSES = {
    "pdf_bound": "The nominal supply voltage of the equipment is less than 3.3 V.",
    "pdf_exact": "The nominal supply voltage of the equipment is exactly 3.3 V.",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output: Path) -> dict:
    from reportlab.pdfgen.canvas import Canvas

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    documents, checks = [], []
    for key, text in CLAUSES.items():
        original = output / (key + ".pdf")
        canvas = Canvas(str(original), pagesize=(600, 800), invariant=1, pageCompression=0)
        canvas.setTitle("Controlled numeric relation")
        canvas.setAuthor("Synthetic qualification fixture")
        canvas.setFont("Helvetica", 12)
        canvas.drawString(40, 700, text)
        canvas.save()
        original_hash = digest(original)
        extracted = extract_pdf(
            original, output / (key + "-extraction"),
            {"pipeline_route": "native", "pdf_backend": "pypdfium2"},
            str(uuid.uuid5(uuid.NAMESPACE_URL, original_hash)),
        )
        extraction_path = output / (key + "-extraction.json")
        extraction_path.write_text(json.dumps(extracted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        blocks = [block for page in extracted["pages"] for block in page["blocks"]]
        exact = [block for block in blocks if block["raw_text"] == text]
        check = {
            "key": key, "original_sha256": original_hash, "source_text": text,
            "source_unchanged": original_hash == digest(original),
            "status": extracted["status"], "complete_literal_found": bool(exact),
            "text_hashes_correct": all(block["source_text_hash"] == hashlib.sha256(block["raw_text"].encode()).hexdigest()
                                       for block in exact),
            "geometry_present": bool(exact) and all(block.get("bbox") is not None for block in exact),
            "ocr_used": any(page.get("ocr_used", False) for page in extracted["pages"]),
        }
        checks.append(check)
        documents.append({
            "key": key, "path": str(original), "sha256": original_hash, "format": "pdf",
            "extraction_path": str(extraction_path), "extraction_sha256": digest(extraction_path),
        })
    passed = all(item["source_unchanged"] and item["complete_literal_found"] and item["text_hashes_correct"]
                 and item["geometry_present"] and item["status"] == "ready" and not item["ocr_used"] for item in checks)
    cases = [
        {"id": "NP01_pdf_bound", "question": "What is the nominal supply voltage?", "document_key": "pdf_bound",
         "mode": "question", "repeats": 1, "required_facts": [CLAUSES["pdf_bound"]], "exact_support": False},
        {"id": "NP02_pdf_exact", "question": "What is the nominal supply voltage?", "document_key": "pdf_exact",
         "mode": "question", "repeats": 1, "required_facts": [CLAUSES["pdf_exact"]], "exact_support": True},
        {"id": "NP03_pdf_compare", "question": "Compare les tensions nominales d’alimentation.",
         "document_key": "pdf_bound",
         "scope": {"kind": "documents", "document_keys": ["pdf_bound", "pdf_exact"]},
         "mode": "comparison", "repeats": 1, "required_facts": list(CLAUSES.values()), "exact_support": False},
    ]
    manifest = {"documents": documents, "cases": cases, "extraction_checks": checks,
                "extraction_passed": passed, "kind": "synthetic_development_pdf_native", "ocr": "NOT_RUN"}
    (output / "inputs.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise ValueError("Native extraction did not preserve every original literal; inspect inputs.json")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({"documents": len(result["documents"]), "cases": len(result["cases"]),
                      "extraction_passed": result["extraction_passed"]}))
