"""Materialize the frozen I6 development recipe, without starting any service.

The sixteen DEV questions retain their source document grouping and annotations.
Six real PDF originals use the native PDFium extraction route; DOCX originals
are extracted by each campaign arm. N17/N18 require an observed 4B call later,
never an inference forced by this preparer. No FINAL fixture is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.ingestion import extract_pdf  # noqa: E402
from tools.qualification.grounded_campaign import generate_document  # noqa: E402

FIXTURE_SHA256 = "fbe09846d7fb138ec71b7400e4eba42e2d8fefbcd17e04172a0d28b04b712315"
SELECTED_CASES = (
    "I6D02", "I6D04", "I6D05", "I6D09", "I6D11", "I6D14", "I6D17", "I6D19",
    "I6D28", "I6D32", "I6D33", "I6D35", "I6D38", "I6D42", "I6D45", "I6D48",
)
PDF_CASES = {"I6D04", "I6D09", "I6D33", "I6D42"}
CONDITION_CASES = (
    ("n17", "Output current: 17 mA at TA = 33 °C.", "Quel courant de sortie est établi à TA = 67 °C ?"),
    ("n18", "Output current: 23 mA at TA = 28 °C.", "What output current is established at TA = 74 °C?"),
)
PDF_LAYOUT: dict[str, Any] = {"page_size": [840, 595], "font": "Helvetica", "font_size": 12,
                              "left": 40, "top": 520, "paragraph_spacing": 40}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def build_recipe(fixture_path: Path) -> dict:
    payload = fixture_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != FIXTURE_SHA256:
        raise ValueError("The development fixture differs from the frozen I6 native recipe")
    fixture = json.loads(payload)
    selected = {case["id"]: case for case in fixture["cases"] if case["id"] in SELECTED_CASES}
    if len(selected) != len(SELECTED_CASES):
        raise ValueError("Missing frozen development case")
    documents, cases = [], []
    for case_id in SELECTED_CASES:
        case = selected[case_id]
        grouped: dict[str, list[dict]] = {}
        for source in case["sources"]:
            grouped.setdefault(source["document_id"], []).append(source)
        keys: dict[str, str] = {}
        bindings: list[dict] = []
        for index, (document_id, sources) in enumerate(grouped.items(), 1):
            key = case_id.lower() + "_" + str(index)
            keys[document_id] = key
            documents.append({"key": key, "format": "pdf" if case_id in PDF_CASES else "docx",
                              "fixture_document_id": document_id,
                              "paragraphs": [source["text"] for source in sources]})
            bindings.extend({"reference_id": source["id"], "document_key": key,
                             "fixture_document_id": document_id, "paragraph_index": paragraph,
                             "text": source["text"], "annotation_span": source["annotation_span"]}
                            for paragraph, source in enumerate(sources))
        scope_keys = [keys[document_id] for document_id in case["scope"]["document_ids"]]
        cases.append({"id": "N_" + case_id, "question": case["question"], "mode": case["mode"], "repeats": 1,
                      "document_key": scope_keys[0], "scope": {"kind": "documents", "document_keys": scope_keys},
                      "annotation": {"source_fixture_case": case_id, "expected": case["expected"],
                                     "rationale": case["rationale"], "source_bindings": bindings}})
    for key, text, question in CONDITION_CASES:
        documents.append({"key": key, "format": "docx", "paragraphs": [text]})
        cases.append({"id": key.upper(), "question": question, "mode": "question", "repeats": 1,
                      "document_key": key, "scope": {"kind": "documents", "document_keys": [key]},
                      "annotation": {"expected": {"exact_support": False, "required_literal_texts": [text]},
                                     "rationale": "The observed point differs from the requested point; preserve the current and condition with an explicit limitation.",
                                     "requires_actual_4b_call": True}})
    return {"schema_version": 1, "protocol_id": "I6-RELATIONS-NATIVE-20261109",
            "kind": "synthetic development; not heldout", "source_fixture_sha256": FIXTURE_SHA256,
            "source_protocol_sha256": fixture["protocol_sha256"], "pdf_layout": PDF_LAYOUT,
            "pdf_extraction": {"pipeline_route": "native", "pdf_backend": "pypdfium2"},
            "documents": documents, "cases": cases}


def generate_pdf(spec: dict, destination: Path) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen.canvas import Canvas

    layout = PDF_LAYOUT
    width, height = layout["page_size"]
    canvas = Canvas(str(destination), pagesize=(width, height), invariant=1, pageCompression=0)
    canvas.setTitle("Synthetic I6 relation qualification")
    canvas.setAuthor("Synthetic qualification fixture")
    canvas.setFont(layout["font"], layout["font_size"])
    for index, text in enumerate(spec["paragraphs"]):
        y = layout["top"] - index * layout["paragraph_spacing"]
        if stringWidth(text, layout["font"], layout["font_size"]) > width - 2 * layout["left"] or y < 40:
            raise ValueError("The frozen single-line PDF layout cannot fit the literal paragraph")
        canvas.drawString(layout["left"], y, text)
    canvas.save()
    return digest(destination)


def extraction_check(spec: dict, original: Path, original_sha: str, extracted: dict) -> dict:
    """Check literal block spans; never infer a tighter region than the extractor."""
    witnesses = []
    pages = extracted["pages"]
    for text in spec["paragraphs"]:
        matches = [(page, block) for page in pages for block in page["blocks"] if block.get("raw_text") == text]
        if len(matches) != 1:
            witnesses.append({"text": text, "passed": False, "exact_block_matches": len(matches)})
            continue
        page, block = matches[0]
        box = block.get("bbox")
        geometry = (isinstance(box, list) and len(box) == 4 and all(isinstance(n, (int, float)) and math.isfinite(n) for n in box)
                    and 0 <= box[0] < box[2] <= page["width"] and 0 <= box[1] < box[3] <= page["height"])
        offsets = any(span.get("start_offset") == 0 and span.get("end_offset") == len(text)
                      and span.get("bbox") == box for span in block.get("spans", []))
        identity = (block.get("version_id") == extracted["version_id"]
                    and block.get("extraction_revision_id") == extracted["extraction_revision_id"]
                    and block.get("page_index") == page["page_index"] and page.get("source_sha256") == original_sha)
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        native = block.get("metadata", {}).get("extraction_method") == "native"
        passed = bool(geometry and offsets and identity and native and block.get("source_text_hash") == text_hash)
        witnesses.append({"text": text, "passed": passed, "block_id": block["id"],
                          "page_index": page["page_index"], "start_offset": 0, "end_offset": len(text),
                          "source_text_hash": text_hash, "bbox": box, "precision": block.get("precision"),
                          "geometry_valid": geometry, "offsets_exact": offsets, "identity_valid": identity})
    unchanged = digest(original) == original_sha
    ocr_used = any(page.get("ocr_used", False) or any(block.get("metadata", {}).get("ocr_used", False)
                                                   for block in page["blocks"]) for page in pages)
    passed = (unchanged and extracted.get("sha256") == original_sha and extracted.get("status") == "ready"
              and extracted.get("parser_complete") is True and not ocr_used and all(item["passed"] for item in witnesses))
    return {"key": spec["key"], "original_sha256": original_sha, "source_unchanged": unchanged,
            "status": extracted.get("status"), "ocr_used": ocr_used, "witnesses": witnesses, "passed": passed}


def prepare(fixture_path: Path, output: Path) -> dict:
    recipe = build_recipe(fixture_path)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # Freeze the sources, annotations and layout before materializing any original.
    write_json(output / "recipe.json", recipe)
    documents, checks = [], []
    try:
        for spec in recipe["documents"]:
            original = output / (spec["key"] + "." + spec["format"])
            sha = generate_pdf(spec, original) if spec["format"] == "pdf" else generate_document(spec, original)
            document = {"key": spec["key"], "path": str(original), "sha256": sha, "format": spec["format"]}
            if spec["format"] == "pdf":
                extracted = extract_pdf(original, output / (spec["key"] + "-extraction"),
                                        recipe["pdf_extraction"], str(uuid.uuid5(uuid.NAMESPACE_URL, sha)))
                extraction_path = output / (spec["key"] + "-extraction.json")
                write_json(extraction_path, extracted)
                check = extraction_check(spec, original, sha, extracted)
                checks.append(check)
                if not check["passed"]:
                    raise ValueError("Native PDF extraction did not preserve the literal evidence: " + spec["key"])
                document.update(extraction_path=str(extraction_path), extraction_sha256=digest(extraction_path))
            documents.append(document)
    except Exception as error:
        write_json(output / "preparation-failure.json", {"error": str(error), "extraction_checks": checks,
                                                        "inputs_ready": False, "model_inference": "NOT_RUN"})
        raise
    result = {**recipe, "recipe_sha256": digest(output / "recipe.json"), "documents": documents,
              "extraction_checks": checks, "extraction_passed": all(item["passed"] for item in checks),
              "model_inference": "NOT_RUN", "ocr": "NOT_RUN"}
    # A partial materialization can never be mistaken for a runnable campaign.
    write_json(output / "inputs.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/support_i6_dev.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.fixtures, args.output)
    print(json.dumps({"output": str(args.output.resolve()), "documents": len(result["documents"]),
                      "cases": len(result["cases"]), "extraction_passed": result["extraction_passed"],
                      "model_inference": "NOT_RUN"}))


if __name__ == "__main__":
    main()
