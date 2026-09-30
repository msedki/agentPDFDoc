import assert from "node:assert/strict";
import test from "node:test";
import { sourceLocalization, sourcePrecision, sourcePrecisionLabel, sourceRegionBoxes } from "../../src/lib/source-location.ts";
import type { Block, Source } from "../../src/lib/types.ts";

const block = (id: string, page_index: number, precision: Block["precision"], bbox: Block["bbox"]): Block => ({ id, page_index, precision, bbox, text: id });
const base: Source = { document_id: "document", version_id: "version", text: "Passage", page_index: 1 };

test("a page-precision source draws no region box even when the API supplies bboxes", () => {
  const source: Source = { ...base, precision: "page", bboxes: [[10, 10, 100, 40]], blocks: [block("b", 1, "block", [10, 10, 100, 40])] };
  assert.deepEqual(sourceRegionBoxes(source, "version", 1), []);
  assert.equal(sourcePrecision(source), "page");
  assert.equal(sourcePrecisionLabel(source), "Localisation à la page");
});

test("region sources draw only their own page geometry, in the opened version, without page-level blocks", () => {
  const source: Source = { ...base, precision: "block", page_indices: [1, 2], blocks: [block("a", 1, "block", [1, 2, 3, 4]), block("b", 2, "table", [5, 6, 7, 8]), block("c", 2, "page", [0, 0, 595, 842])], bboxes: [[1, 2, 3, 4], [5, 6, 7, 8], [0, 0, 595, 842]] };
  assert.deepEqual(sourceRegionBoxes(source, "version", 1), [[1, 2, 3, 4]]);
  assert.deepEqual(sourceRegionBoxes(source, "version", 2), [[5, 6, 7, 8]]);
  assert.deepEqual(sourceRegionBoxes(source, "version", 0), []);
  assert.deepEqual(sourceRegionBoxes(source, "other-version", 1), []);
  assert.deepEqual(sourceRegionBoxes(null, "version", 1), []);
});

test("blocks without geometry on the displayed page never borrow a box from another page", () => {
  const source: Source = { ...base, precision: "block", page_indices: [1, 2], blocks: [block("a", 1, "block", null), block("b", 2, "block", [5, 6, 7, 8])], bboxes: [[5, 6, 7, 8]] };
  assert.deepEqual(sourceRegionBoxes(source, "version", 1), []);
  assert.deepEqual(sourceRegionBoxes(source, "version", 2), [[5, 6, 7, 8]]);
});

test("a declared region without valid geometry is shown as a page location, like its source card", () => {
  const missing: Source = { ...base, precision: "block", blocks: [block("a", 1, "block", null)] };
  assert.equal(sourcePrecisionLabel(missing), "Localisation à la page");
  assert.deepEqual(sourceRegionBoxes(missing, "version", 1), []);
  const inverted: Source = { ...base, precision: "span", blocks: [block("a", 1, "span", [100, 40, 10, 10])] };
  assert.equal(sourcePrecision(inverted), "page");
  assert.deepEqual(sourceRegionBoxes(inverted, "version", 1), []);
});

test("labels share the source card vocabulary, including search hits without a top-level precision", () => {
  assert.equal(sourcePrecisionLabel({ ...base, precision: "span", blocks: [block("a", 1, "span", [1, 2, 3, 4])] }), "Passage source");
  assert.equal(sourcePrecisionLabel({ ...base, precision: "table", blocks: [block("a", 1, "table", [1, 2, 3, 4])] }), "Table source");
  assert.equal(sourcePrecisionLabel({ ...base, blocks: [block("a", 1, "block", [1, 2, 3, 4])] }), "Bloc source");
  assert.equal(sourcePrecisionLabel({ ...base, blocks: [block("a", 1, "page", null)] }), "Localisation à la page");
  assert.equal(sourcePrecisionLabel(base), "Localisation à la page");
});

test("source card badges separate exact families, page-only locations and unlocated sources", () => {
  assert.deepEqual(sourceLocalization({ ...base, precision: "table", blocks: [block("a", 1, "table", [1, 2, 3, 4])] }), { family: "exact", label: "Table source", tone: "success" });
  assert.deepEqual(sourceLocalization({ ...base, precision: "block", blocks: [block("a", 1, "block", null)] }), { family: "page", label: "Localisation à la page", tone: "neutral" });
  assert.deepEqual(sourceLocalization({ ...base, page_index: undefined, page_indices: [2] }), { family: "page", label: "Localisation à la page", tone: "neutral" });
  const unlocated: Source = { document_id: "document", version_id: "version", text: "Passage", precision: "span", bboxes: [[1, 2, 3, 4]] };
  assert.deepEqual(sourceLocalization(unlocated), { family: "unlocated", label: "Source non localisée", tone: "warning" });
  assert.deepEqual(sourceLocalization({ ...unlocated, page_indices: [] }).family, "unlocated");
});

test("legacy bboxes without blocks are drawn only for a single-page source", () => {
  assert.deepEqual(sourceRegionBoxes({ ...base, precision: "block", bboxes: [[1, 2, 3, 4]] }, "version", 1), [[1, 2, 3, 4]]);
  assert.deepEqual(sourceRegionBoxes({ ...base, precision: "block", bboxes: [[1, 2, 3, 4]] }, "version", 0), []);
  assert.deepEqual(sourceRegionBoxes({ ...base, precision: "block", page_indices: [1, 2], bboxes: [[1, 2, 3, 4]] }, "version", 1), []);
});
