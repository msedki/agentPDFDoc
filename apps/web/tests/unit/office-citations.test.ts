import assert from "node:assert/strict";
import test from "node:test";
import { registeredCitationLocation } from "../../src/lib/citation-link.ts";
import { sourceLocalization } from "../../src/lib/source-location.ts";
import type { Source } from "../../src/lib/types.ts";

const identity = { document_id: "document", version_id: "version-old", query_id: "query-old", source_id: "S001", extraction_revision_id: "revision-old", text: "Preuve Office" };
const word = { ...identity, format: "docx", page_index: null, page_indices: [], precision: "element", locator: { kind: "docx_element", unit_id: "word-body", part: "word/document.xml", element_path: "/document/body/p[3]" } } as unknown as Source;
const excel = { ...identity, format: "xlsx", page_index: null, page_indices: [], precision: "range", locator: { kind: "xlsx_cells", unit_id: "sheet-1", sheet_id: "sheet-1", sheet_name: "Mesures été", part: "xl/worksheets/sheet1.xml", cell_range: "B2:C3", row_start: 2, row_end: 3, column_start: 2, column_end: 3 } } as unknown as Source;

test("registered DOCX citations keep their original element and revision without a synthetic PDF page", () => {
  assert.deepEqual(registeredCitationLocation(word, "query-old", "S001"), { documentId: "document", versionId: "version-old", format: "docx", unitId: "word-body", elementPath: "/document/body/p[3]", extractionRevisionId: "revision-old" });
});

test("registered XLSX citations keep exact sheet and cell bounds without a synthetic PDF page", () => {
  assert.deepEqual(registeredCitationLocation(excel, "query-old", "S001"), { documentId: "document", versionId: "version-old", format: "xlsx", unitId: "sheet-1", extractionRevisionId: "revision-old", cellRange: { rowStart: 2, rowEnd: 3, columnStart: 2, columnEnd: 3 } });
});

test("Office citations remain registry-bound and missing revisions never fall back to current content", () => {
  assert.throws(() => registeredCitationLocation(word, "other", "S001"));
  assert.throws(() => registeredCitationLocation(excel, "query-old", "S002"));
  assert.throws(() => registeredCitationLocation({ ...word, extraction_revision_id: undefined }, "query-old", "S001"));
});

test("Office localization uses source elements and cells rather than PDF geometry", () => {
  assert.equal(sourceLocalization(word).label, "Élément source");
  assert.equal(sourceLocalization(excel).label, "Plage source");
  assert.equal(sourceLocalization(word).family, "exact");
  assert.equal(sourceLocalization(excel).family, "exact");
});
