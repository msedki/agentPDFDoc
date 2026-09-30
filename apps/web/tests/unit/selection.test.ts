import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { boundedCanvasSize, reconcileSelection, utf16ToCodePointOffset, visiblePageWindow, wholeBlockSpan } from "../../src/lib/selection.ts";
import type { Block } from "../../src/lib/types.ts";

function block(id: string, text: string): Block {
  return { id, text, raw_text: text, page_index: 0, precision: "block", extraction_revision_id: "rev-immutable", source_text_hash: createHash("sha256").update(text, "utf8").digest("hex") };
}
test("non-BMP text returns codepoint offsets while retaining revision and exact hash", () => {
  const source = block("unicode", "A😀é");
  const selected = reconcileSelection("😀é", [source]);
  assert.deepEqual(selected, [{ blockId: "unicode", extractionRevisionId: "rev-immutable", blockTextSha256: source.source_text_hash, offsetUnit: "unicode_code_point", startOffset: 1, endOffset: 3 }]);
  assert.equal(utf16ToCodePointOffset(source.text, 3), 2);
  assert.throws(() => utf16ToCodePointOffset(source.text, 2), RangeError);
});
test("ligatures and combining accents preserve the exact source representation", () => {
  const source = block("typography", "Une ﬁgure et e\u0301.");
  const selected = reconcileSelection("ﬁgure et e\u0301", [source]);
  assert.equal(selected?.[0].startOffset, 4);
  assert.equal(selected?.[0].endOffset, 15);
  assert.equal(reconcileSelection("figure et é", [source]), null);
});
test("whitespace map reconciles line breaks but does not invent a dehyphenation", () => {
  const source = block("ocr", "Pression\n  de service : 3,5 bars.\nmainte-\nnance");
  const selected = reconcileSelection("Pression de service", [source]);
  assert.equal(selected?.[0].endOffset, Array.from("Pression\n  de service").length);
  assert.equal(reconcileSelection("maintenance", [source]), null);
});
test("cross-block selection resolves each immutable source and refuses ambiguity", () => {
  const first = block("a", "Le robinet"); const second = block("b", "a une tolérance.");
  const selected = reconcileSelection("robinet a une", [first, second]);
  assert.deepEqual(selected?.map(span => [span.blockId, span.startOffset, span.endOffset]), [["a", 3, 10], ["b", 0, 5]]);
  assert.equal(reconcileSelection("doublon", [block("c", "doublon"), block("d", "doublon")]), null);
});
test("selection is unavailable without an authoritative revision and source hash", () => {
  const source = block("a", "source"); delete source.extraction_revision_id;
  assert.equal(wholeBlockSpan(source), null);
  assert.equal(reconcileSelection("source", [source]), null);
});
test("selection offsets use raw_text when a presentation field differs", () => {
  const source = block("raw", "A😀 é"); source.text = "presentation field";
  assert.equal(wholeBlockSpan(source)?.endOffset, 4);
  assert.deepEqual(reconcileSelection("😀 é", [source])?.map(span => [span.startOffset, span.endOffset]), [[1, 4]]);
  assert.equal(reconcileSelection("presentation field", [source]), null);
});
test("virtual page window never allocates more than five pages and stays in bounds", () => {
  for (const total of [0, 1, 4, 5, 20, 2000]) for (const center of [0, Math.max(0, total - 1), Math.floor(total / 2)]) {
    const window = visiblePageWindow(center, total);
    assert.ok(window.length <= 5);
    assert.ok(window.every(index => index >= 0 && index < total));
  }
});
test("five canvases remain under the pixel cap at extreme zoom and DPR", () => {
  for (const [width, height, dpr] of [[600, 850, 1], [1800, 2550, 2], [4000, 6000, 3], [6000, 4000, 4]]) {
    const raster = boundedCanvasSize(width, height, dpr);
    assert.ok(raster.width * raster.height * 5 <= 24_000_000);
    assert.ok(raster.width > 0 && raster.height > 0);
    assert.ok(raster.scale <= dpr);
  }
});
