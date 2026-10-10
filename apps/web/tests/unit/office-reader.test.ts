import assert from "node:assert/strict";
import test from "node:test";
import { cellKeyTarget, cellRangeError, cellWindow, columnName, locatorRange, movedCellWindow, officeCellText, officeValueText, parseCellRange, verifyOfficeBlocks, verifyOfficeCells, verifyOfficeRepresentation } from "../../src/lib/office-reader.ts";
import { docxTableWindow, officeTableColumnNames, rasterAsset } from "../../src/lib/office-structure.ts";
import { documentLocation, supportedDocumentName, versionFormat } from "../../src/lib/document-format.ts";
import { extractionBadge } from "../../src/lib/extraction-provenance.ts";
import { isOfficeLocation, isPdfLocation, useWorkspace } from "../../src/lib/store.ts";
import type { CellRange, OfficeBlocks, OfficeCell, OfficeCells, OfficeRepresentation } from "../../src/lib/types.ts";

const bounds = { rowStart: 1, rowEnd: 50, columnStart: 1, columnEnd: 20 };
const cell: OfficeCell = { address: "B2", row: 2, column: 2, data_type: "number", value: { kind: "number", value: "123456789012345678.01" }, cached_present: false, cache_freshness: "absent" };
const received: OfficeCells = { version_id: "version", extraction_revision_id: "old", sheet_id: "xlsx:xl/worksheets/sheet1.xml", bounds: { row_start: 1, row_end: 50, column_start: 1, column_end: 20 }, cells: [cell], metadata: {}, warnings: [] };

test("A1 input is numeric, inclusive and strictly bounded; invalid inputs never become a default range", () => {
  assert.deepEqual(parseCellRange("b2:d12"), { rowStart: 2, rowEnd: 12, columnStart: 2, columnEnd: 4 });
  assert.deepEqual(parseCellRange("XFD1048576"), { rowStart: 1048576, rowEnd: 1048576, columnStart: 16384, columnEnd: 16384 });
  assert.equal(columnName(16384), "XFD");
  for (const input of ["A0", "XFE1", "A1048577", "D12:B2", "A1:C0", "A1:B2:C3", "Feuille!A1", "=SUM(A1)", "A1<script>", "A9007199254740993", ""]) assert.equal(parseCellRange(input), null, input);
  assert.ok(cellRangeError({} as CellRange));
  assert.ok(cellRangeError({ ...bounds, rowStart: 1.5 }));
  assert.equal(locatorRange({ kind: "xlsx_cells", unit_id: "u", sheet_id: "u", sheet_name: "f", part: "p", cell_range: "B2", row_start: 2, row_end: 1, column_start: 2, column_end: 2 }), null);
});

test("large sparse ranges only request a bounded window; edge paging stays within Excel coordinates", () => {
  assert.deepEqual(cellWindow({ rowStart: 100, rowEnd: 1048576, columnStart: 16000, columnEnd: 16384 }), { rowStart: 100, rowEnd: 149, columnStart: 16000, columnEnd: 16019 });
  const end = movedCellWindow(1048576, 16384);
  assert.equal(end.rowEnd, 1048576); assert.equal(end.columnEnd, 16384);
  assert.equal(end.rowEnd - end.rowStart + 1, 50); assert.equal(end.columnEnd - end.columnStart + 1, 20);
  assert.equal(cellRangeError(end), null);
  assert.equal(cellRangeError(movedCellWindow(-100, -100)), null);
});

test("cell navigation has a single bounded target and supports arrows and native Home/End keys", () => {
  assert.deepEqual(cellKeyTarget("ArrowLeft", 1, 1, bounds), { row: 1, column: 1 });
  assert.deepEqual(cellKeyTarget("ArrowDown", 2, 2, bounds), { row: 3, column: 2 });
  assert.deepEqual(cellKeyTarget("End", 2, 2, bounds, true), { row: 50, column: 20 });
  assert.deepEqual(cellKeyTarget("Home", 50, 20, bounds, true), { row: 1, column: 1 });
  assert.equal(cellKeyTarget("Tab", 1, 1, bounds), null);
});

test("source values keep exact numeric strings, false and formula caches separate, without calculation", () => {
  assert.equal(officeCellText(cell), "123456789012345678.01");
  assert.equal(officeCellText({ ...cell, value: { kind: "boolean", value: false } }), "false");
  assert.equal(officeCellText({ ...cell, formula: { raw_text: "SUM(B1:B9)" } }), "");
  assert.equal(officeCellText({ ...cell, formula: { raw_text: "SUM(B1:B9)" }, cached_present: true, cached_value: { kind: "number", value: "0" }, cache_freshness: "unknown" }), "0");
  assert.equal(officeCellText({ ...cell, display_text: "000123" }), "000123");
  assert.equal(officeValueText({ kind: "excel_date", serial: "60" }), "Jour Excel 1900 fictif · série 60");
});

test("cell responses reject wrong revision, sheet, bounds, duplicate addresses and coordinate disagreement", () => {
  const verify = (data: OfficeCells) => verifyOfficeCells(data, "version", received.sheet_id, "old", bounds);
  assert.equal(verify(received), received);
  for (const data of [{ ...received, extraction_revision_id: "new" }, { ...received, sheet_id: "other" }, { ...received, bounds: { ...received.bounds, row_end: 49 } }, { ...received, cells: [cell, cell] }, { ...received, cells: [{ ...cell, address: "C2" }] }, { ...received, cells: [{ ...cell, row: 51, address: "B51" }] }]) assert.throws(() => verify(data));
});

test("DOCX responses never substitute a revision, unit or synthetic PDF page", () => {
  const unit = { id: "unit", kind: "docx_part", title: "Document", part: "word/document.xml", order_index: 0, metadata: {} };
  const representation: OfficeRepresentation = { version_id: "version", extraction_revision_id: "old", format: "docx", units: [unit], next_cursor: null, total: 1, metadata: {}, coverage: {}, limits: {}, warnings: [] };
  assert.equal(verifyOfficeRepresentation(representation, "version", "old"), representation);
  assert.throws(() => verifyOfficeRepresentation(representation, "version", "new"));
  const block = { id: "block", text: "Élément", page_index: null, precision: "element" as const, extraction_revision_id: "old", locator: { kind: "docx_element" as const, unit_id: "unit", part: "word/document.xml", element_path: "/document/body/p[3]" } };
  const blocks: OfficeBlocks = { version_id: "version", extraction_revision_id: "old", unit, blocks: [block], total: 1, next_cursor: null };
  assert.equal(verifyOfficeBlocks(blocks, "version", "unit", "old"), blocks);
  assert.throws(() => verifyOfficeBlocks({ ...blocks, blocks: [{ ...block, page_index: 0 }] }, "version", "unit", "old"));
  assert.throws(() => verifyOfficeBlocks({ ...blocks, blocks: [{ ...block, extraction_revision_id: "new" }] }, "version", "unit", "old"));
});

test("table windows preserve a merged origin that starts outside the visible region, without repeating continuation text", () => {
  const rows = Array.from({ length: 23 }, (_, row) => ({ row, is_header: row === 0, cells: row === 18 ? [{ id: "origin", row, column: 8, row_span: 5, column_span: 4, text: "Texte unique" }] : row >= 19 ? [{ row, column: 8, merge_origin_id: "origin", text: "" }] : [] }));
  const window = docxTableWindow({ rows, column_count: 15 }, 20, 10);
  assert.equal(window.length, 3); assert.equal(window[0].cells.filter(cell => !cell.missing).length, 1);
  assert.equal(window[0].cells[0].source.id, "origin"); assert.equal(window[0].cells[0].rowSpan, 3); assert.equal(window[0].cells[0].columnSpan, 2);
  assert.equal(window[0].cells[0].clipped, true);
  assert.equal(window.slice(1).flatMap(row => row.cells).filter(cell => !cell.missing).length, 0);
});

test("table gaps stay in their source columns, including grid_before/after; XML tableColumn names use attributes", () => {
  const rows = [{ row: 0, grid_before: 2, grid_after: 2, cells: [{ id: "third", row: 0, column: 2, text: "Troisième colonne" }] }];
  const window = docxTableWindow({ rows, column_count: 5 }, 0, 0);
  assert.deepEqual(window[0].cells.map(cell => [cell.column, cell.columnSpan, cell.missing === true]), [[0, 2, true], [2, 1, false], [3, 2, true]]);
  assert.deepEqual(officeTableColumnNames({ columns: [{ name: "tableColumn", attributes: { id: "1", name: "Item" } }, { name: "tableColumn", attributes: { id: "2", name: "Amount" } }] }), ["Item", "Amount"]);
  assert.deepEqual(officeTableColumnNames({ columns: [{ name: "tableColumn", label: "Étiquette décodée", attributes: { name: "_x00C9_tiquette décodée" } }] }), ["Étiquette décodée"]);
});

test("inline images require a source digest and a supported raster MIME; remote/SVG payloads remain metadata", () => {
  assert.equal(rasterAsset({ content_type: "image/svg+xml", sha256: "a".repeat(64) }), null);
  assert.equal(rasterAsset({ content_type: "image/png", relation: "https://example.invalid/image" }), null);
  assert.equal(rasterAsset({ content_type: "image/png", sha256: "a".repeat(64), alt_text: "Figure source" })?.alt, "Figure source");
});

test("Office navigation keeps explicit scope and returns to PDF/archived revisions without a fake page", () => {
  useWorkspace.setState(useWorkspace.getInitialState(), true);
  const scope = { kind: "cell_range" as const, versionId: "version", extractionRevisionId: "old", sheetId: "sheet", ...bounds };
  useWorkspace.getState().setScope(scope, "Choix explicite");
  useWorkspace.getState().open(documentLocation("document", "pdf-version", "pdf", 4));
  useWorkspace.getState().open({ documentId: "document", versionId: "version", format: "xlsx", unitId: "sheet", extractionRevisionId: "old" });
  useWorkspace.getState().page(7);
  const office = useWorkspace.getState().opened; assert.ok(isOfficeLocation(office)); assert.equal("pageIndex" in office, false);
  useWorkspace.getState().officeLocation({ cellRange: bounds });
  assert.deepEqual(useWorkspace.getState().scope, scope);
  useWorkspace.getState().back(); const pdf = useWorkspace.getState().opened; assert.ok(isPdfLocation(pdf)); assert.equal(pdf.pageIndex, 4);
  useWorkspace.getState().back(); assert.deepEqual(useWorkspace.getState().opened, { ...office, cellRange: bounds });
});

test("file chooser adds OOXML without admitting executable formats; old API payloads stay PDF", () => {
  for (const name of ["document.PDF", "note.docx", "Bilan.XLSX"]) assert.equal(supportedDocumentName(name), true);
  for (const name of ["note.docm", "macro.xlsm", "old.xls", "note.docx.exe", "page.html"]) assert.equal(supportedDocumentName(name), false);
  assert.equal(versionFormat(undefined, undefined), "pdf");
  assert.equal("pageIndex" in documentLocation("d", "v", "docx"), false);
  assert.doesNotMatch(extractionBadge({ format: "xlsx" })!.title, /page|OCR/);
});
