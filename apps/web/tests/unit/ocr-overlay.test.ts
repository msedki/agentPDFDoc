import { test } from "node:test";
import assert from "node:assert/strict";
import { ocrOverlays, pageTextCaption } from "../../src/lib/ocr-overlay.ts";
import type { Block } from "../../src/lib/types.ts";

function block(id: string, method?: string): Block {
  return { id, text: "A😀 natif\nOCR 3.5 bar", raw_text: "A😀 natif\nOCR 3.5 bar", page_index: 0, precision: "block", bbox: [10, 20, 110, 60], metadata: { extraction_method: method as "ocr" | "native" | "mixed" | "unknown" } };
}
test("native and globally routed unknown blocks do not become OCR overlays", () => {
  const unknown = block("unknown"); unknown.metadata = { route: "regional_ocr", ocr_used: true };
  assert.deepEqual(ocrOverlays([block("native", "native"), unknown]), []);
});
test("whole OCR block uses its exact text and authoritative geometry", () => {
  const source = block("ocr", "ocr");
  assert.deepEqual(ocrOverlays([source]), [{ key: "ocr", blockId: "ocr", text: source.raw_text, bbox: source.bbox, precision: "block" }]);
  source.precision = "page";
  assert.deepEqual(ocrOverlays([source]), []);
});
test("mixed block overlays only exact OCR spans with Unicode codepoint offsets", () => {
  const source = block("mixed", "mixed");
  source.metadata!.ocr_spans = [{ start_offset: 9, end_offset: 20, bbox: [20, 30, 100, 50], precision: "span" }];
  const overlays = ocrOverlays([source]);
  assert.equal(overlays[0].text, "OCR 3.5 bar");
  assert.deepEqual(overlays[0].bbox, [20, 30, 100, 50]);
  source.metadata!.ocr_spans[0].end_offset = 100;
  assert.deepEqual(ocrOverlays([source]), []);
});
test("nested storage metadata is read but missing or inverted geometry is refused", () => {
  const source = block("nested"); source.metadata = { metadata: { extraction_method: "ocr" } };
  assert.equal(ocrOverlays([source]).length, 1);
  source.bbox = [100, 30, 20, 50];
  assert.deepEqual(ocrOverlays([source]), []);
});

test("the page caption states no text only once the text layer and the blocks are read", () => {
  // Constat de la recette du 01/10 : pendant le rendu, la légende annonçait « Aucun texte extrait » sur une page à texte natif.
  assert.equal(pageTextCaption({ nativeText: null, blocksLoading: false, ocrRegions: 0 }), "Lecture de la page…");
  assert.equal(pageTextCaption({ nativeText: false, blocksLoading: true, ocrRegions: 0 }), "Lecture de la page…");
  assert.equal(pageTextCaption({ extractionState: "blank", nativeText: null, blocksLoading: false, ocrRegions: 0 }), "Page blanche");
  assert.equal(pageTextCaption({ nativeText: true, blocksLoading: false, ocrRegions: 0 }), "Texte natif");
  assert.equal(pageTextCaption({ nativeText: true, blocksLoading: false, ocrRegions: 2 }), "Texte natif et régions OCR");
  assert.equal(pageTextCaption({ nativeText: false, blocksLoading: false, ocrRegions: 2 }), "Texte OCR");
  assert.equal(pageTextCaption({ nativeText: false, blocksLoading: false, ocrRegions: 0 }), "Aucun texte extrait");
});
