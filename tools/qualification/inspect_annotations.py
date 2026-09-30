"""Check expected source text against independent native PDFium preflight only."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
from resolve import whitespace_map

ROOT = Path(__file__).resolve().parents[2]


def main():
    folder = ROOT / "evals/qualification-v2.1"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    questions = json.loads((folder / "questions.json").read_text(encoding="utf-8"))["questions"]
    entries = {entry["key"]: entry for entry in manifest["entries"]}
    pages = {}
    for key in {unit["document_key"] for question in questions for unit in question["expected_units"]}:
        doc = pdfium.PdfDocument(str(ROOT / "fixtures" / entries[key]["path"]))
        try:
            for index in range(len(doc)):
                page = doc[index]
                textpage = page.get_textpage()
                try:
                    pages[(key, index)] = textpage.get_text_bounded()
                finally:
                    textpage.close()
                    page.close()
        finally:
            doc.close()
    observations = []
    for question in questions:
        for unit_index, unit in enumerate(question["expected_units"]):
            raw = pages[(unit["document_key"], unit["page_index"])]
            normalized, mapping = whitespace_map(raw)
            spans = []
            if unit.get("required_row"):
                row = unit["required_row"]
                pattern = r"(?<![\w.-])" + re.escape(row["identifier"]) + r"(?![\w.-]).*?(?<![\w.])" + re.escape(row["value"]) + r"(?![\w.]).*?(?<![\w/])" + re.escape(row["unit"]) + r"(?![\w/])"
                offset = 0
                for text in raw.splitlines(keepends=True):
                    hit = re.search(pattern, text)
                    if hit:
                        spans.append({"start_codepoint": offset + hit.start(), "end_codepoint": offset + hit.end(), "source_text": hit.group(0)})
                    offset += len(text)
                matched = len(spans) == 1
            else:
                matched = True
                for expected in unit["required_texts"]:
                    target, _ = whitespace_map(expected)
                    hits = [hit.start() for hit in re.finditer(re.escape(target), normalized)]
                    if len(hits) != 1:
                        matched = False
                    else:
                        start = mapping[hits[0]]
                        end = mapping[hits[0] + len(target) - 1] + 1
                        spans.append({"start_codepoint": start, "end_codepoint": end, "source_text": raw[start:end]})
            kind = entries[unit["document_key"]]["type"]
            status = "EXPECTED_TEXT_PRESENT_NATIVE_PREFLIGHT" if matched else "REQUIRES_OCR_PREFLIGHT" if not raw else "SCANNED_REGION_REQUIRES_OCR_PREFLIGHT" if kind == "native_paragraph_scanned_table" and unit["page_index"] == 1 else "EXPECTED_TEXT_NOT_FOUND_NATIVE_PREFLIGHT"
            observations.append({"question_id": question["id"], "unit_index": unit_index, "document_key": unit["document_key"], "page_index": unit["page_index"], "pdf_sha256": entries[unit["document_key"]]["sha256"], "native_page_text_sha256": hashlib.sha256(raw.encode()).hexdigest(), "native_characters": len(raw), "status": status, "native_preflight_spans": spans if matched else [], "version_id": None, "extraction_revision_id": None, "block_id": None})
    report = {"status": "INDEPENDENT_NATIVE_SOURCE_INSPECTION_NOT_RUNTIME_ANNOTATION_OR_RAG_SCORE", "method": "pypdfium2 5.13.0 get_text_bounded; only whitespace normalized for matching, exact codepoint offsets retained", "limitations": ["Offsets and hashes belong to this independent preflight parser, not API blocks", "Runtime versions, revisions and block IDs remain null", "OCR required regions not processed", "No retrieval/question/model call occurred"], "expected_units_inspected": len(observations), "counts": dict(Counter(item["status"] for item in observations)), "observations": observations}
    (folder / "reports/native-annotations-2026-09-30.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"expected_units_inspected": len(observations), "counts": report["counts"]}))


if __name__ == "__main__":
    main()
