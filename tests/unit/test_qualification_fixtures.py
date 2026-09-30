"""Controlled fixture structure and annotation safety; these are not RAG metrics."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
from corpus_data import CATEGORY_QUOTAS, frozen_digest  # noqa: E402
from resolve import resolve_dataset, resolve_unit  # noqa: E402


def raw_page(path: Path, page_index=0, password=None) -> str:
    doc = pdfium.PdfDocument(str(path), password=password)
    page = doc[page_index]
    text = page.get_textpage()
    try:
        return text.get_text_bounded()
    finally:
        text.close(); page.close(); doc.close()


class CorpusStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT / "evals" / "qualification-v2.1"
        cls.manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        cls.data = json.loads((folder / "questions.json").read_text(encoding="utf-8"))
        cls.entries = {entry["key"]: entry for entry in cls.manifest["entries"]}

    def path(self, key):
        return ROOT / "fixtures" / self.entries[key]["path"]

    def test_counts_and_exact_split_quotas(self):
        self.assertEqual(len(self.data["questions"]), 200)
        self.assertGreaterEqual(len(self.entries), 16)
        for split in ("development", "final"):
            questions = [item for item in self.data["questions"] if item["split"] == split]
            self.assertEqual(len(questions), 100)
            self.assertEqual(Counter(item["category"] for item in questions), CATEGORY_QUOTAS)
            self.assertEqual(sum(item["answerable"] for item in questions), 80)
        self.assertEqual(len({item["id"] for item in self.data["questions"]}), 200)

    def test_documentary_families_and_question_contexts_are_disjoint(self):
        families = {split: {item["family"] for item in self.data["questions"] if item["split"] == split} for split in ("development", "final")}
        self.assertFalse(families["development"] & families["final"])
        contexts = [json.dumps({key: item.get(key) for key in ("question", "prior_user_question", "scope_template")}, sort_keys=True, ensure_ascii=False) for item in self.data["questions"]]
        self.assertEqual(len(set(contexts)), len(contexts))

    def test_source_hashes_and_runtime_fields_are_honest(self):
        for entry in self.entries.values():
            path = ROOT / "fixtures" / entry["path"]
            self.assertEqual(path.stat().st_size, entry["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
            self.assertIsNone(entry["version_id"])
            self.assertIsNone(entry["extraction_revision_id"])
            self.assertIsNone(entry["generation_id"])
        for question in self.data["questions"]:
            self.assertIsNone(question["scope_resolved"])
            for unit in question["expected_units"]:
                self.assertEqual(unit["file_sha256"], self.entries[unit["document_key"]]["sha256"])
                self.assertIsNone(unit["resolved_spans"])
                self.assertIsNone(unit["version_id"])
                self.assertIsNone(unit["extraction_revision_id"])
            for source in question["document_sources"]:
                self.assertEqual(source["file_sha256"], self.entries[source["document_key"]]["sha256"])

    def test_scan_has_no_native_layer_and_mixed_retains_only_native_paragraph(self):
        for key in ("development-DA-P02", "final-FT-C02", "scan-fr-en"):
            self.assertTrue(all(page["native_character_count"] == 0 for page in self.entries[key]["inspection"]["pages"]))
        for key, code in (("development-DA-P03", "DA-P03"), ("final-FT-C03", "FT-C03")):
            page = raw_page(self.path(key), 1)
            self.assertIn(code, page)
            self.assertNotIn(code + "-", page)
            self.assertGreater(self.entries[key]["inspection"]["pages"][1]["native_character_count"], 0)

    def test_labels_geometry_and_visible_rotated_anchor(self):
        labels = [page["label"] for page in self.entries["roman-labels"]["inspection"]["pages"]]
        self.assertEqual(labels, ["i", "ii", "A-1", "A-2"])
        for rotation in (90, 180, 270):
            entry = self.entries[f"crop-rotate-{rotation}"]
            page = entry["inspection"]["pages"][0]
            self.assertEqual(page["rotation"], rotation)
            self.assertEqual(page["crop_box"], [24, 30, 565, 570])
            self.assertIn("6.4 bar", raw_page(self.path(entry["key"])))

    def test_unicode_fixture_contains_actual_non_bmp_and_combining_text(self):
        text = raw_page(self.path("unicode-selection"))
        self.assertIn("\U0001f600", text)
        self.assertIn("\u00e9", text)
        self.assertIn("e\u0301", text)
        # PDFium converts this real, visible two-line hyphenation to an internal
        # marker. Verify the source and expose the extraction difference.
        self.assertIn(b"(Cesure con-)", self.path("unicode-selection").read_bytes())
        self.assertIn(b"0 -20 Td (trole", self.path("unicode-selection").read_bytes())
        self.assertIn("con\x02trole", text)
        self.assertTrue(self.entries["unicode-selection"]["inspection"]["pages"][0]["hyphenation_marker_observed"])
        # PDFium expands the Type3 ligature's explicit U+FB01 mapping to "fi".
        # Record this parser behavior; do not claim the original codepoint survived.
        self.assertIn(b"<03> <FB01>", self.path("unicode-selection").read_bytes())
        self.assertTrue(self.entries["unicode-selection"]["inspection"]["pages"][0]["ligature_expansion_observed"])

    def test_boundary_version_homonyms_and_explicit_error_inputs(self):
        self.assertIn("continue explicitement page 5", raw_page(self.path("boundary-45"), 3))
        self.assertIn("suite du tableau de la page 4", raw_page(self.path("boundary-45"), 4))
        self.assertIn("2.7 bar", raw_page(self.path("version-1")))
        self.assertIn("4.9 bar", raw_page(self.path("version-2")))
        self.assertNotEqual(self.entries["version-1"]["sha256"], self.entries["version-2"]["sha256"])
        self.assertEqual(self.path("QH-A").name, self.path("QH-B").name)
        self.assertNotEqual(self.path("QH-A").parent, self.path("QH-B").parent)
        self.assertEqual(raw_page(self.path("blank")), "")
        with self.assertRaises(pdfium.PdfiumError):
            pdfium.PdfDocument(str(self.path("encrypted")))
        with self.assertRaises(pdfium.PdfiumError):
            pdfium.PdfDocument(str(self.path("corrupt")))
        self.assertGreater(self.path("size-limit").stat().st_size, self.entries["size-limit"]["isolated_limit_bytes"])
        self.assertFalse(self.entries["size-limit"]["production_oversize_fixture"])

    def test_final_freeze_and_comparison_followup_provenance_templates(self):
        folder = ROOT / "evals" / "qualification-v2.1"
        final = json.loads((folder / "final.json").read_text(encoding="utf-8"))
        freeze = json.loads((folder / "final.freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen_digest(final), freeze["canonical_sha256"])
        for question in self.data["questions"]:
            if question["category"] == "comparison":
                self.assertEqual(len({unit["document_key"] for unit in question["expected_units"]}), 2)
            if question["category"] == "conversation_followup":
                prior = next(item for item in self.data["questions"] if item["id"] == question["followup_of_question_id"])
                self.assertEqual(prior["question"], question["prior_user_question"])
                self.assertEqual(prior["scope_template"], question["scope_template"])
            if question["category"] == "unanswerable_in_scope":
                self.assertFalse(question["answerable"])
                self.assertEqual(question["expected_units"], [])
                self.assertTrue(question["absence_reason"])


class AnnotationResolver(unittest.TestCase):
    """IDs below are unit-test inputs only, never delivered as resolved evidence."""
    def binding(self, texts, *, table_data=None):
        blocks = []
        for index, text in enumerate(texts):
            blocks.append({"id": f"unit-block-{index}", "version_id": "unit-version", "extraction_revision_id": "unit-revision", "generation_id": "unit-generation", "source_text_hash": hashlib.sha256(text.encode()).hexdigest(), "raw_text": text, "precision": "table" if table_data else "block", "metadata": {"table_data": table_data} if table_data else {}})
        return {"document_id": "unit-document", "version_id": "unit-version", "extraction_revision_id": "unit-revision", "generation_id": "unit-generation", "file_sha256": "c" * 64, "pages": [{"page": {"page_index": 0}, "blocks": blocks}]}

    def unit(self, text="3.5 bar", **extra):
        return {"document_key": "unit-fixture", "file_sha256": "c" * 64, "version_id": None, "extraction_revision_id": None, "page_index": 0, "required_texts": [text], "resolved_spans": None, "resolution_status": "NOT_RESOLVED", **extra}

    def test_exact_unicode_offsets_and_multiblock_whitespace(self):
        binding = self.binding(["A \U0001f600 e\u0301 3.5\n", "bar end"])
        result = resolve_unit(self.unit(), {"unit-fixture": binding})
        self.assertEqual(result["resolution_status"], "RESOLVED")
        self.assertEqual([span["text"] for span in result["resolved_spans"]], ["3.5\n", "bar"])
        self.assertEqual(result["resolved_spans"][0]["start_offset"], 7)
        self.assertEqual(result["resolved_spans"][0]["offset_unit"], "unicode_code_point")
        self.assertEqual(result["resolved_spans"][1]["block_id"], "unit-block-1")

    def test_refuse_document_name_only_missing_evidence_and_ambiguous_evidence(self):
        for texts in (["The right document, but no answer"], ["3.5 bar", "3.5 bar"]):
            result = resolve_unit(self.unit(), {"unit-fixture": self.binding(texts)})
            self.assertEqual(result["resolution_status"], "UNRESOLVED")
            self.assertIsNone(result["resolved_spans"])

    def test_refuse_wrong_file_hash_source_hash_revision_and_missing_ids(self):
        original = self.binding(["3.5 bar"])
        for field, value in (("file_sha256", "d" * 64), ("version_id", "another-version"), ("extraction_revision_id", "another-revision")):
            changed = copy.deepcopy(original); changed[field] = value
            self.assertEqual(resolve_unit(self.unit(), {"unit-fixture": changed})["resolution_status"], "UNRESOLVED")
        for field, value in (("source_text_hash", "0" * 64), ("id", None), ("extraction_revision_id", None)):
            changed = copy.deepcopy(original); changed["pages"][0]["blocks"][0][field] = value
            self.assertEqual(resolve_unit(self.unit(), {"unit-fixture": changed})["resolution_status"], "UNRESOLVED")

    def test_ligature_and_dehyphenation_are_not_guessed(self):
        self.assertEqual(resolve_unit(self.unit("fi"), {"unit-fixture": self.binding(["\ufb01"])})["resolution_status"], "UNRESOLVED")
        self.assertEqual(resolve_unit(self.unit("controle"), {"unit-fixture": self.binding(["con-\ntrole"])})["resolution_status"], "UNRESOLVED")

    def test_table_row_association_required_not_arbitrary_cells(self):
        required = {"identifier": "DA-P01-IN", "value": "13", "unit": "mm"}
        unit = self.unit(required_row=required)
        invalid = self.binding(["DA-P01-IN | 14 | mm\nOTHER | 13 | mm"])
        self.assertEqual(resolve_unit(unit, {"unit-fixture": invalid})["resolution_status"], "UNRESOLVED")
        valid = self.binding(["Référence | Valeur | Unité\nDA-P01-IN | 13 | mm\nOTHER | 13 | kPa"])
        result = resolve_unit(unit, {"unit-fixture": valid})
        self.assertEqual(result["resolution_status"], "RESOLVED")
        self.assertEqual(result["resolved_spans"][0]["text"], "DA-P01-IN | 13 | mm")

    def test_structured_cells_prove_one_row(self):
        cells = {"table_cells": [{"start_row_offset": 1, "text": text} for text in ("DA-P01-IN", "13", "mm")]}
        binding = self.binding(["DA-P01-IN\n13\nmm"], table_data=cells)
        required = {"identifier": "DA-P01-IN", "value": "13", "unit": "mm"}
        result = resolve_unit(self.unit(required_row=required), {"unit-fixture": binding})
        self.assertEqual(result["resolution_status"], "RESOLVED")
        binding["pages"][0]["blocks"][0]["metadata"]["table_data"]["table_cells"][2]["start_row_offset"] = 2
        self.assertEqual(resolve_unit(self.unit(required_row=required), {"unit-fixture": binding})["resolution_status"], "UNRESOLVED")

    def test_unanswerable_scope_still_requires_real_matching_version_and_hash(self):
        question = {"scope_template": {"document_keys": ["unit-fixture"]}, "document_sources": [{"document_key": "unit-fixture", "file_sha256": "c" * 64}], "expected_units": []}
        original = {"questions": [question]}
        binding = self.binding([])
        good = resolve_dataset(original, {"documents": {"unit-fixture": binding}})
        self.assertEqual(good["questions"][0]["annotation_state"], "RESOLVED")
        binding["file_sha256"] = "d" * 64
        bad = resolve_dataset(original, {"documents": {"unit-fixture": binding}})
        self.assertEqual(bad["questions"][0]["annotation_state"], "UNRESOLVED")
        self.assertNotIn("scope_resolved", original["questions"][0])


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
