import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { CitationCoverageInput, CitationCoverageResult, CoverageRectangle } from "../e2e/citation-coverage.ts";

// Named DOM/Range doubles only: exercise the real serialized browser function,
// not PDF.js rendering or E2E. No imported executable helper enters its closure.
const source = readFileSync(new URL("../e2e/citation-coverage.ts", import.meta.url), "utf8");
const tree = ts.createSourceFile("citation-coverage.ts", source, ts.ScriptTarget.Latest, true);
const declaration = tree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "measureCitationCoverage");
assert.ok(declaration);
const compiled = ts.transpileModule(`${declaration.getText(tree).replace(/^export /, "")}\nmeasureCitationCoverage;`, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;
const box = (x = 10, y = 10, width = 80, height = 10): CoverageRectangle => ({ x, y, width, height });
type TextSpec = { text: string; rects?: CoverageRectangle[]; br?: boolean };

function harness(specs: TextSpec[], highlights = [box(8, 8, 84, 84)]) {
  const requests: { nodeIndex: number; start: number; end: number }[] = [];
  const nodes = specs.map((spec, index) => ({ nodeType: 3, nodeName: "#text", data: spec.text,
    parentElement: { closest: () => ({}) }, childNodes: [], index }));
  const layer = { nodeType: 1, nodeName: "DIV", childNodes: specs.flatMap((spec, index) => {
    const span = { nodeType: 1, nodeName: "SPAN", childNodes: [nodes[index]] };
    return spec.br ? [span, { nodeType: 1, nodeName: "BR", childNodes: [] }] : [span];
  }) };
  const canvas = { width: 100, height: 100, isConnected: true, mode: "painted", reads: 0,
    getBoundingClientRect: () => box(0, 0, 100, 100),
    getContext: () => ({ getImageData: (_x: number, _y: number, width: number, height: number) => {
      canvas.reads++;
      const data = new Uint8ClampedArray(width * height * 4).fill(255);
      if (canvas.mode === "transparent") data.fill(0);
      if (canvas.mode === "painted") for (let offset = 0; offset < 32; offset += 4) data.fill(32, offset, offset + 3);
      if (canvas.mode === "black") for (let offset = 0; offset < data.length; offset += 4) data.fill(32, offset, offset + 3);
      return { data };
    } }),
  };
  const overlayNodes = highlights.map(highlight => ({ isConnected: true, getBoundingClientRect: () => highlight }));
  const slot = {
    querySelector: (selector: string) => { assert.equal(selector, "canvas"); return canvas; },
    querySelectorAll: (selector: string) => {
      if (selector === ".textLayer") return [layer];
      assert.equal(selector, '[data-testid="source-highlight"]'); return overlayNodes;
    },
  };
  const documentDouble = {
    querySelectorAll: (selector: string) => { assert.equal(selector, '.pdf-page-slot[data-page-index="0"]'); return [slot]; },
    createRange: () => {
      let selected: (typeof nodes)[number] | undefined, start = 0, end = 0;
      return {
        setStart: (node: (typeof nodes)[number], offset: number) => { selected = node; start = offset; },
        setEnd: (node: (typeof nodes)[number], offset: number) => { assert.equal(node, selected); end = offset; },
        getClientRects: () => {
          assert.ok(selected);
          requests.push({ nodeIndex: selected.index, start, end });
          const spec = specs[selected.index];
          // A partial range has a partial width, so tests reject implementations
          // which inspect a marker alone rather than the complete selected node.
          return spec.rects ?? [box(10 + start * 2, 10 + selected.index * 16, (end - start) * 2, 10)];
        },
      };
    },
  };
  const read = runInNewContext(compiled, { document: documentDouble,
    getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" }) }) as
    (input: CitationCoverageInput) => CitationCoverageResult;
  return { read: (text: string) => read({ pageIndex: 0, passages: [{ id: "block-1", text }] }), requests, canvas, overlayNodes };
}

test("full passage preserves accents, signs and UTF-16 ranges across spans and line breaks", () => {
  const h = harness([{ text: " Q01 : A😀é", br: true }, { text: "e\u0301 ﬁ + ± N·m." }]);
  const result = h.read("Q01 : A😀é\n  e\u0301 ﬁ + ± N·m.");
  assert.equal(result.passed, true);
  assert.equal(result.passages[0].matches, 1);
  assert.deepEqual(h.requests, [{ nodeIndex: 0, start: 1, end: 11 }, { nodeIndex: 1, start: 0, end: 13 }]);
  assert.equal(result.passages[0].fragments.map(item => item.text).join(" "), "Q01 : A😀é e\u0301 ﬁ + ± N·m.");
});

test("a marker cannot stand in for missing remainder of the expected passage", () => {
  const h = harness([{ text: "QLONG-P14-1" }]);
  const result = h.read("QLONG-P14-1 : toute la consigne est requise.");
  assert.equal(result.passed, false);
  assert.equal(result.passages[0].reason, "full_passage_not_found");
  assert.equal(h.requests.length, 0);
});

test("beginning-only and centre-only overlays fail complete-area coverage", () => {
  for (const highlight of [box(10, 10, 12, 10), box(36, 10, 8, 10)]) {
    const h = harness([{ text: "Un passage complet à couvrir.", rects: [box(10, 10, 80, 10)] }], [highlight]);
    assert.equal(h.read("Un passage complet à couvrir.").passages[0].reason, "incomplete_highlight_coverage");
  }
});

test("all native line rectangles are required, not just the first line", () => {
  const h = harness([{ text: "Première et deuxième ligne", rects: [box(10, 10, 60, 10), box(10, 40, 60, 10)] }], [box(10, 10, 60, 10)]);
  assert.equal(h.read("Première et deuxième ligne").passed, false);
});

test("two overlays can cover a complete native line, but an internal gap fails", () => {
  for (const [rightStart, passed] of [[50, true], [65, false]] as const) {
    const h = harness([{ text: "La ligne entière", rects: [box(10, 10, 80, 10)] }], [box(10, 10, 40, 10), box(rightStart, 10, 90 - rightStart, 10)]);
    assert.equal(h.read("La ligne entière").passed, passed);
  }
});

test("duplicate whole text is ambiguous even when one occurrence is highlighted", () => {
  const h = harness([{ text: "Texte répété", br: true }, { text: "Texte répété" }]);
  const result = h.read("Texte répété");
  assert.equal(result.passages[0].reason, "ambiguous_full_passage");
  assert.equal(result.passages[0].matches, 2);
  assert.equal(h.requests.length, 0);
});

test("native text off-page cannot pass even under an otherwise matching overlay", () => {
  const h = harness([{ text: "hors page", rects: [box(95, 10, 20, 10)] }]);
  assert.equal(h.read("hors page").passages[0].reason, "native_text_off_page");
});

test("empty expected text, empty native geometry and non-finite rectangles fail", () => {
  assert.equal(harness([{ text: "texte" }]).read(" \n\t ").passages[0].reason, "empty_expected_text");
  for (const rects of [[], [box(NaN)], [box(10, 10, 0, 10)]]) {
    assert.equal(harness([{ text: "texte", rects }]).read("texte").passages[0].reason, "invalid_native_geometry");
  }
});

test("normalization cannot delete punctuation, expand a ligature or compose accents", () => {
  for (const text of ["Q01 : e\u0301 ﬁ ± N·m", "Q01 : é fi ± N·m", "Q01 : é ﬁ + N-m"]) {
    assert.equal(harness([{ text: "Q01 : é ﬁ ± N·m" }]).read(text).passed, false);
  }
});

test("adjacent spans split inside a word do not gain an invented space", () => {
  const h = harness([{ text: "main" }, { text: "tenance" }]);
  assert.equal(h.read("maintenance").passed, true);
  assert.equal(h.read("main tenance").passed, false);
});

test("range endpoints include the full passage rather than its marker", () => {
  const h = harness([{ text: "avant Q01 : consigne complète. après" }]);
  const result = h.read("Q01 : consigne complète.");
  assert.equal(result.passed, true);
  assert.deepEqual(h.requests, [{ nodeIndex: 0, start: 6, end: 30 }]);
});

test("missing, non-finite, hidden and off-page overlays fail before measuring native ranges", () => {
  for (const highlights of [[], [box(Infinity)], [box(95, 10, 20, 10)]]) {
    const h = harness([{ text: "texte" }], highlights);
    assert.equal(h.read("texte").reason, "invalid_or_missing_highlights");
    assert.equal(h.requests.length, 0);
  }
  const h = harness([{ text: "texte" }]); h.overlayNodes[0].isConnected = false;
  assert.equal(h.read("texte").reason, "invalid_or_missing_highlights");
});

test("matching native text and overlays cannot pass on a white, transparent or all-black canvas", () => {
  for (const mode of ["white", "transparent", "black"]) {
    const h = harness([{ text: "Texte complet" }]); h.canvas.mode = mode;
    const result = h.read("Texte complet");
    assert.equal(result.passages[0].fragments[0].covered, true);
    assert.equal(result.passages[0].reason, "native_bitmap_without_ink_or_background");
    assert.equal(result.passed, false);
  }
});

test("the bitmap budget applies to the entire fragment and is checked before reads", () => {
  const h = harness([{ text: "Texte complet", rects: [box(10, 10, 80, 10)] }]);
  h.canvas.width = 2000; h.canvas.height = 2000;
  const result = h.read("Texte complet");
  assert.equal(result.passages[0].reason, "bounded_bitmap_unavailable");
  assert.equal(h.canvas.reads, 0);
});
