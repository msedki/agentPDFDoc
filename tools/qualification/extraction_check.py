"""Extraction confrontée à la vérité terrain des fixtures, par l'API réelle d'une instance isolée (critères D02.3 à D02.10).

L'instance est démarrée par `tools/qualification/e2e_instance.py start`. L'outil importe les sept documents DEV
(`fixtures/qualification-v2.1/development/`, texte natif, deux colonnes, scan, paragraphe natif et tableau scanné), le
scan bilingue, la frontière de checkpoint pages 4/5, et un document produit sur place : un schéma raster sans aucun texte
entre deux lignes natives. La vérité terrain vient du générateur (`corpus_data.records`, `generate.py`) ; le jeu final
n'est ni importé ni lu. Les extractions partielles sont observées avant publication, puis publiées comme le ferait
l'utilisateur.

Chaque contrôle porte le critère qu'il étaye ; le rapport conserve, page par page, classification, OCR, régions non
résolues et méthodes d'extraction, sans texte de corpus privé (toutes les fixtures sont synthétiques).

    .venv\\Scripts\\python.exe tools/qualification/extraction_check.py --instance <etat.json> --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from corpus_data import records  # noqa: E402
from fault_check import Isolated, import_fixture, wait_admitted  # noqa: E402

FIXTURES = ROOT / "fixtures/qualification-v2.1"
NATIVE_DEV = {1, 4, 5, 6, 7}
FIGURE_LINES = ("Le banc QF-01 comprend un compresseur, un réservoir et deux vannes.", "Figure 1 — schéma de principe du banc QF-01.")
BOUNDARY_ROWS = (("QB-45-A", "7.2", "bar"), ("QB-45-B", "18", "N·m"), ("QB-45-C", "0.6", "L/min"), ("QB-45-D", "1100", "h"))
SCAN_FR_EN = ("QS-FREN", "3.8 bar", "0.2 bar", "contrôle", "tolérance", "maintain", "tolerance")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def figure_pdf() -> bytes:
    """Page A4 : une ligne native, un schéma raster sans texte (blocs, liaisons, cercles), une légende native."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    for box in ((60, 180, 240, 320), (360, 60, 540, 200), (360, 300, 540, 440), (660, 180, 840, 320)):
        draw.rectangle(box, outline="black", width=6)
    for start, end in (((240, 250), (360, 130)), ((240, 250), (360, 370)), ((540, 130), (660, 250)), ((540, 370), (660, 250))):
        draw.line(start + end, fill="black", width=5)
    for x, y in ((150, 250), (450, 130), (450, 370), (750, 250)):
        draw.ellipse((x - 30, y - 30, x + 30, y + 30), outline="black", width=5)
    data = zlib.compress(image.tobytes())
    stream = (f"BT /F1 12 Tf 50 760 Td <{FIGURE_LINES[0].encode('cp1252').hex()}> Tj ET\n"
              "q 450 0 0 250 70 470 cm /Im0 Do Q\n"
              f"BT /F1 11 Tf 50 440 Td <{FIGURE_LINES[1].encode('cp1252').hex()}> Tj ET").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 6 0 R >> >> /Contents 5 0 R >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
               f"<< /Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream"]
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def table_rows(block: dict[str, Any]) -> list[tuple[str, ...]]:
    cells = block.get("table_data", {}).get("table_cells", [])
    rows: dict[int, dict[int, str]] = {}
    for cell in cells:
        rows.setdefault(cell["start_row_offset_idx"], {})[cell["start_col_offset_idx"]] = normalized(cell["text"])
    return [tuple(row[column] for column in sorted(row)) for _, row in sorted(rows.items())]


def page_facts(client: Any, version_id: str, page_count: int) -> list[dict[str, Any]]:
    pages = []
    for index in range(page_count):
        payload = client.get(f"/api/v1/versions/{version_id}/pages/{index}/blocks").json()
        page = payload["page"]
        pages.append({"page_index": index, "classification": page.get("classification"), "extraction_state": page.get("extraction_state"),
                      "ocr_used": bool(page.get("ocr_used")), "ocr_regions": len(page.get("ocr_regions") or []),
                      "unresolved_regions": [{"reason": region.get("reason"), "has_bbox": region.get("bbox") is not None} for region in page.get("unresolved_regions") or []],
                      "blocks": [{"id": block["id"], "type": block["type"], "method": block.get("extraction_method"), "ocr_used": bool(block.get("ocr_used")),
                                  "section_id": block.get("section_id"), "continuation_of": block.get("continuation_of"), "text": normalized(block["text"]),
                                  "rows": table_rows(block) if block["type"] == "table" else []} for block in payload["blocks"]]})
    return pages


def page_text(page: dict[str, Any]) -> str:
    return " ".join(block["text"] for block in page["blocks"])


def summary(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Faits par page conservés dans le rapport, sans le texte des blocs."""
    return [{key: value for key, value in page.items() if key != "blocks"} | {"blocks": len(page["blocks"]), "methods": dict(Counter(block["method"] for block in page["blocks"])),
                                                                            "types": dict(Counter(block["type"] for block in page["blocks"]))} for page in pages]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    instance = Isolated(json.loads(args.instance.read_text(encoding="utf-8")))
    started = datetime.now(UTC)
    dev = {record.index: record for record in records("development")}
    figure = Path(instance.state["root"]) / "Schéma sans texte QF-01.pdf"
    figure.write_bytes(figure_pdf())
    sources = {f"DA-P{index:02d}": (FIXTURES / "development/Procédures" / record.name, f"DEV/{record.name}") for index, record in dev.items()}
    sources |= {"scan-fr-en": (FIXTURES / "scans/Contrôle bilingue FR EN.pdf", "Scans/Contrôle bilingue FR EN.pdf"),
                "boundary-45": (FIXTURES / "layouts/Section et tableau pages 4-5.pdf", "Mises en page/Section et tableau pages 4-5.pdf"),
                "figure": (figure, "Schémas/Schéma sans texte QF-01.pdf")}
    imported = {key: import_fixture(instance, path, relative) for key, (path, relative) in sources.items()}
    jobs, admission_retries = wait_admitted(instance, {key: item["job_id"] for key, item in imported.items()}, attempts=20)
    checks: dict[str, bool] = {}
    documents: dict[str, Any] = {}
    with instance.client() as client:
        partial = {key: job for key, job in jobs.items() if job["state"] == "ready_partial"}
        # D02.9 avant publication : état visible, document absent des recherches.
        before = {}
        for key, job in partial.items():
            listed = client.get(f"/api/v1/documents/{imported[key]['document_id']}").json()
            searched = client.post("/api/v1/search", json={"question": "valeur", "scope": {"kind": "library"}}).json()
            before[key] = {"job_state": job["state"], "published": job["published"], "active_version": listed["version_id"],
                           "in_library_results": any(hit["document_id"] == imported[key]["document_id"] for hit in searched["results"] + searched["top10"])}
            client.post(f"/api/v1/jobs/{job['id']}/publish-partial").raise_for_status()
        checks["D02.3_all_documents_processed"] = all(job["state"] in {"ready", "ready_partial"} for job in jobs.values())
        for key, item in imported.items():
            detail = client.get(f"/api/v1/documents/{item['document_id']}").json()
            job = next(job for job in detail["jobs"] if job["id"] == item["job_id"])
            pages = page_facts(client, item["version_id"], detail["page_count"]) if detail["version_id"] else []
            documents[key] = {"state": job["state"], "published": job["published"], "coverage": job["coverage"], "page_count": detail["page_count"],
                              "warnings": dict(Counter(warning.get("code") for warning in job["warnings"])), "pages": pages}
        after = {}
        for key in partial:
            scope = {"kind": "documents", "documentIds": [imported[key]["document_id"]]}
            searched = client.post("/api/v1/search", json={"question": "pression nominale", "scope": scope}).json()
            context = client.post("/api/v1/admin/evaluation/context", json={"question": "pression nominale", "scope": scope}).json()
            after[key] = {"search_warnings": sorted({warning["code"] for warning in searched["warnings"]}),
                          "context_warnings": sorted({warning["code"] for warning in context["warnings"]}), "model_called": context["model_called"]}
    report: dict[str, Any] = {"criteria": ["D02.3", "D02.4", "D02.5", "D02.6", "D02.7", "D02.9", "D02.10"], "started_utc": started.isoformat(),
                              "admission_retries": admission_retries, "checkpoint_window_pages": 4, "partial_before_publication": before,
                              "partial_after_publication": after}
    try:
        evaluate(documents, partial, before, after, dev, checks, report)
    except (KeyError, IndexError, TypeError) as error:
        checks["evaluation_complete"] = False
        report["error"] = f"{type(error).__name__}: {error}"
    report.update(seconds=round((datetime.now(UTC) - started).total_seconds(), 1), checks=checks, result="PASS" if checks and all(checks.values()) else "FAIL",
                  documents={key: {**{k: v for k, v in doc.items() if k != "pages"}, "pages": summary(doc["pages"])} for key, doc in documents.items()})
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "checks": checks, **({"error": report["error"]} if "error" in report else {})}, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


def evaluate(documents: dict[str, Any], partial: dict[str, Any], before: dict[str, Any], after: dict[str, Any], dev: dict[int, Any],
             checks: dict[str, bool], report: dict[str, Any]) -> None:
    native_keys = [f"DA-P{index:02d}" for index in sorted(NATIVE_DEV)] + ["boundary-45"]
    ocr_expected = {"DA-P02": 2, "scan-fr-en": 1, "DA-P03": 1}
    # D02.3 : chaque document traité, couverture complète déclarée et visible page par page.
    checks["D02.3_coverage_per_page"] = all(doc["coverage"].get("processed") == doc["coverage"].get("total") == doc["page_count"] == len(doc["pages"])
                                            and all(page["classification"] for page in doc["pages"]) for doc in documents.values())
    # D02.4 : aucun OCR sur les documents natifs ; pages OCRisées comptées et localisées.
    checks["D02.4_native_without_ocr"] = all(documents[key]["coverage"].get("ocr") == 0 and not any(page["ocr_used"] or page["ocr_regions"] for page in documents[key]["pages"]) for key in native_keys)
    checks["D02.4_ocr_pages_counted"] = all(documents[key]["coverage"].get("ocr") == count == sum(page["ocr_used"] for page in documents[key]["pages"])
                                            and all(page["ocr_regions"] for page in documents[key]["pages"] if page["ocr_used"]) for key, count in ocr_expected.items())
    # D02.5 : voie native pour les documents simples ; page mixte sans double texte.
    checks["D02.5_native_route"] = all(block["method"] == "native" and not block["ocr_used"] for key in native_keys for page in documents[key]["pages"] for block in page["blocks"])
    mixed = documents["DA-P03"]["pages"][1]
    native_line = "Les valeurs de ce tableau concernent uniquement DA-P03."
    carriers = [block for block in mixed["blocks"] if native_line in block["text"]]
    checks["D02.5_mixed_page_without_double_text"] = (page_text(mixed).count(native_line) == 1 and len(carriers) == 1 and carriers[0]["method"] == "native"
                                                     and not carriers[0]["ocr_used"] and mixed["ocr_used"] and not documents["DA-P03"]["pages"][0]["ocr_used"])
    # D02.6 : régions non résolues visibles ; le schéma ne devient pas du texte.
    figure_page = documents["figure"]["pages"][0]
    figure_text = page_text(figure_page)
    leftover = figure_text
    for expected in FIGURE_LINES:
        leftover = leftover.replace(expected, " ")
    checks["D02.6_figure_declared_unresolved"] = any(region["reason"] == "GRAPHIC_INTERPRETATION_UNAVAILABLE" and region["has_bbox"] for region in figure_page["unresolved_regions"])
    checks["D02.6_figure_without_invented_text"] = all(line in figure_text for line in FIGURE_LINES) and not re.search(r"\w", leftover)
    checks["D02.6_partial_regions_listed"] = all(documents[key]["warnings"] and any(page["unresolved_regions"] for page in documents[key]["pages"]) for key in partial)
    # D02.7 : section et tableau à cheval sur les pages 4/5, frontière de fenêtre de checkpoint (fenêtres de 4 pages).
    boundary = documents["boundary-45"]["pages"]
    tables = {index: [block for block in boundary[index]["blocks"] if block["type"] == "table"] for index in (3, 4)}
    found_rows = {row for index in (3, 4) for block in tables[index] for row in block["rows"]}
    checks["D02.7_rows_on_both_pages"] = all(row in found_rows for row in BOUNDARY_ROWS)
    checks["D02.7_table_continuation"] = bool(tables[3] and tables[4]) and tables[4][0]["continuation_of"] == tables[3][-1]["id"]
    checks["D02.7_same_section_across_window"] = bool(tables[3] and tables[4]) and tables[3][-1]["section_id"] == tables[4][0]["section_id"] is not None
    # D02.9 : extraction partielle signalée avant et après publication, jusqu'au contexte transmis à la réponse.
    checks["D02.9_partial_flagged_before_publication"] = bool(partial) and all(not value["published"] and value["active_version"] is None and not value["in_library_results"] for value in before.values())
    checks["D02.9_partial_flagged_in_results_and_context"] = bool(after) and all("partial_extraction" in value["search_warnings"] and "partial_extraction" in value["context_warnings"]
                                                                                   and value["model_called"] is False for value in after.values())
    # D02.10 : tableaux et unités ; colonnes non mélangées.
    native_tables = {}
    for index in NATIVE_DEV:
        rows = {row for block in documents[f"DA-P{index:02d}"]["pages"][1]["blocks"] for row in block["rows"]}
        native_tables[f"DA-P{index:02d}"] = sum(row in rows for row in dev[index].rows)
    checks["D02.10_native_tables_exact"] = all(count == 3 for count in native_tables.values())
    two_columns = dev[4]
    left = [normalized(paragraph) for paragraph in two_columns.paragraphs[:4]]
    right = [normalized(paragraph) for paragraph in two_columns.paragraphs[4:]]
    column_blocks = documents["DA-P04"]["pages"][0]["blocks"]
    mixed_blocks = [block["id"] for block in column_blocks if any(fragment in block["text"] for fragment in (text[:40] for text in left))
                    and any(fragment in block["text"] for fragment in (text[:40] for text in right))]
    page_zero = page_text(documents["DA-P04"]["pages"][0])
    order = [page_zero.find(text[:40]) for text in left + right]
    checks["D02.10_two_columns_not_mixed"] = not mixed_blocks and all(position >= 0 for position in order) and max(order[:4]) < min(order[4:])
    scanned = {}
    for key, index in (("DA-P02", 2), ("DA-P03", 3)):
        page = documents[key]["pages"][1]
        rows = {row for block in page["blocks"] for row in block["rows"]}
        scanned[key] = {"exact_rows": sum(row in rows for row in dev[index].rows), "expected_rows": 3, "unresolved_regions": len(page["unresolved_regions"])}
    checks["D02.10_scanned_tables_exact_or_flagged"] = all(value["exact_rows"] == 3 or value["unresolved_regions"] for value in scanned.values())
    scan_text = page_text(documents["scan-fr-en"]["pages"][0])
    scan_terms = {term: term in scan_text for term in SCAN_FR_EN}
    checks["D02.3_bilingual_scan_read"] = all(scan_terms.values())
    report.update(native_table_rows_exact=native_tables, scanned_tables=scanned, two_column_mixed_blocks=mixed_blocks, bilingual_scan_terms=scan_terms,
                  boundary_tables={str(index): [{"id": block["id"], "section_id": block["section_id"], "continuation_of": block["continuation_of"], "rows": block["rows"]}
                                                for block in tables[index]] for index in (3, 4)})


if __name__ == "__main__":
    raise SystemExit(main())
