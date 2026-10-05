import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { CanvasPaintProbe, CanvasPaintState } from "../e2e/canvas-paint-oracle.ts";

// Execute the actual browser instrumentation and oracle with named DOM/bitmap
// doubles only. No Playwright import, browser, PDF.js render or application state.
const spec = readFileSync(new URL("../e2e/canvas-budget.spec.ts", import.meta.url), "utf8");
const specTree = ts.createSourceFile("canvas-budget.spec.ts", spec, ts.ScriptTarget.Latest, true);
const init: ts.ArrowFunction[] = [];
function visit(node: ts.Node) {
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
    && node.expression.name.text === "addInitScript" && ts.isArrowFunction(node.arguments[0])) init.push(node.arguments[0]);
  ts.forEachChild(node, visit);
}
visit(specTree);
assert.equal(init.length, 1, "the existing canvas registry remains the only init script");
const helper = readFileSync(new URL("../e2e/canvas-paint-oracle.ts", import.meta.url), "utf8");
const helperTree = ts.createSourceFile("canvas-paint-oracle.ts", helper, ts.ScriptTarget.Latest, true);
const probe = helperTree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "probeFixtureCanvasPaint");
assert.ok(probe);
const probeText = probe.getText(helperTree).replace(/^export /, "");
const compile = (source: string) => ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type PixelMode = "painted" | "white" | "transparent" | "black" | "first-only";
type Box = { left: number; top: number; right: number; bottom: number; width: number; height: number };
const box = (left: number, top: number, width: number, height: number): Box => ({ left, top, right: left + width, bottom: top + height, width, height });

function harness(pageIndices = [0]) {
  let zoom = "300 %";
  class CanvasBitmapDOMDouble {
    bitmapWidth = 100;
    bitmapHeight = 200;
    isConnected = true;
    parentElement = null;
    style = { display: "" };
    lang = "";
    mode: PixelMode = "black";
    contextAvailable = true;
    reads = 0;
    spans: { textContent: string; getBoundingClientRect(): Box }[];
    pageIndex: string;
    constructor(index: number) {
      this.pageIndex = String(index);
      this.spans = [1, 6].map((paragraph, offset) => ({
        textContent: `QLONG-P${String(index + 1).padStart(2, "0")}-${paragraph} : texte synthétique`,
        getBoundingClientRect: () => box(10, offset ? 150 : 40, 70, 15),
      }));
    }
    get width() { return this.bitmapWidth; }
    set width(value: number) { this.bitmapWidth = value; this.mode = "black"; }
    get height() { return this.bitmapHeight; }
    set height(value: number) { this.bitmapHeight = value; this.mode = "black"; }
    getBoundingClientRect() { return box(0, 0, 100, 200); }
    closest(selector: string) {
      if (selector !== ".pdf-page-slot") return null;
      return { dataset: { pageIndex: this.pageIndex }, querySelectorAll: () => this.spans };
    }
    getContext() {
      if (!this.contextAvailable) return null;
      return { getImageData: (_x: number, y: number, width: number, height: number) => {
        this.reads++;
        const rgba = new Uint8ClampedArray(width * height * 4).fill(255);
        if (this.mode === "transparent") rgba.fill(0);
        if (this.mode === "black") for (let offset = 0; offset < rgba.length; offset += 4) rgba.fill(0, offset, offset + 3);
        if (this.mode === "painted" || (this.mode === "first-only" && y < 100)) {
          for (let offset = 0; offset < 32; offset += 4) rgba.fill(32, offset, offset + 3);
        }
        return { data: rgba };
      } };
    }
  }
  const canvases = pageIndices.map(index => new CanvasBitmapDOMDouble(index));
  const windowDouble = {} as { __canvasPaintState: CanvasPaintState; __canvasCensus: () => { registered: number } };
  const documentDouble = {
    body: {},
    querySelector: (selector: string) => { assert.equal(selector, ".zoom-label"); return { textContent: zoom }; },
    querySelectorAll: (selector: string) => { assert.ok(["canvas", ".pdf-paper canvas"].includes(selector)); return canvases.filter(canvas => canvas.isConnected); },
  };
  const context = { window: windowDouble, document: documentDouble, HTMLCanvasElement: CanvasBitmapDOMDouble };
  runInNewContext(compile(`(${init[0].getText(specTree)})();`), context);
  const read = runInNewContext(compile(`${probeText}\nprobeFixtureCanvasPaint;`), context) as
    (options: { zoom: string; afterEpoch: number }) => CanvasPaintProbe;
  const allocate = (mode: PixelMode = "painted") => {
    for (const canvas of canvases) {
      canvas.width = 100;
      canvas.height = 200;
      canvas.getContext();
      canvas.mode = mode;
    }
  };
  return { canvases, state: windowDouble.__canvasPaintState, census: windowDouble.__canvasCensus,
    read: (afterEpoch = 0) => read({ zoom: "300 %", afterEpoch }), allocate, setZoom: (value: string) => { zoom = value; } };
}

test("fresh 300-percent bitmap with ink/background at both known fixture anchors passes", () => {
  const h = harness(); h.allocate();
  const result = h.read();
  assert.equal(result.painted, true);
  assert.equal(result.pages[0].anchors.length, 2);
  assert.equal(result.pages[0].anchors[0].reference, "QLONG-P01-1");
  assert.equal(result.pages[0].anchors[1].reference, "QLONG-P01-6");
});
for (const mode of ["white", "transparent", "black", "first-only"] as const) {
  test(`allocated ${mode} bitmap does not establish painted fixture content`, () => {
    const h = harness(); h.allocate(mode); assert.equal(h.read().painted, false);
  });
}
test("old painted bitmap fails after a zoom checkpoint even when capped dimensions match", () => {
  const h = harness(); h.allocate();
  const checkpoint = h.state.checkpoint();
  assert.equal(h.canvases[0].width, 100);
  assert.equal(h.read(checkpoint).painted, false);
  h.allocate("white");
  assert.equal(h.canvases[0].width, 100);
  assert.equal(h.read(checkpoint).painted, false);
  h.canvases[0].mode = "painted";
  assert.equal(h.read(checkpoint).painted, true);
});
test("old zoom cannot pass by changing only the toolbar label", () => {
  const h = harness(); h.setZoom("275 %"); h.allocate(); h.setZoom("300 %");
  assert.equal(h.read().painted, false);
  assert.equal(h.canvases[0].reads, 0);
});
test("observations neither advance allocation epochs nor add census registrations", () => {
  const h = harness(); h.allocate();
  const checkpoint = h.state.checkpoint(), registered = h.census().registered;
  assert.equal(h.read().painted, true); assert.equal(h.read().painted, true);
  assert.equal(h.state.checkpoint(), checkpoint);
  assert.equal(h.census().registered, registered);
});
test("changing a dimension to the same value requires painted pixels again", () => {
  const h = harness(); h.allocate(); const checkpoint = h.state.checkpoint();
  const width = h.canvases[0].width;
  h.canvases[0].width = width;
  assert.ok(h.state.checkpoint() > checkpoint);
  assert.equal(h.read(checkpoint).painted, false);
});
test("five page bitmaps must all carry their own first and sixth anchors", () => {
  const h = harness([0, 1, 2, 3, 4]); h.allocate(); assert.equal(h.read().painted, true);
  h.canvases[4].mode = "white"; assert.equal(h.read().painted, false);
});
test("a previous page's text cannot identify the current page's painted regions", () => {
  const h = harness(); h.allocate(); h.canvases[0].pageIndex = "1";
  assert.equal(h.read().painted, false);
});
test("missing or duplicate fixture anchors are refused", () => {
  const h = harness(); h.allocate(); h.canvases[0].spans[1].textContent = "Autre document";
  assert.equal(h.read().painted, false);
  h.canvases[0].spans[1] = h.canvases[0].spans[0];
  assert.equal(h.read().painted, false);
});
test("detached, absent and zero-sized page canvases are refused", () => {
  const h = harness(); h.allocate(); h.canvases[0].isConnected = false;
  assert.equal(h.read().painted, false);
  h.canvases[0].isConnected = true; h.canvases[0].width = 0;
  assert.equal(h.read().painted, false);
  assert.equal(harness([]).read().painted, false);
});
test("missing pixel context is not rescued by a text layer", () => {
  const h = harness(); h.allocate(); h.canvases[0].contextAvailable = false;
  assert.equal(h.read().painted, false);
});
test("fixture anchor outside the bitmap is refused without a pixel read", () => {
  const h = harness(); h.allocate(); h.canvases[0].spans[0].getBoundingClientRect = () => box(500, 500, 70, 15);
  assert.equal(h.read().painted, false); assert.equal(h.canvases[0].reads, 0);
});
test("the real spec keeps bounded polling, all budgets and native guards", () => {
  assert.match(spec, /page\.evaluate\(probeFixtureCanvasPaint, \{ zoom: `\$\{zoom\} %`, afterEpoch \}\)/);
  assert.match(spec, /timeout: 30000, message:/);
  assert.match(spec, /await settled\(beforeZoom\)/);
  assert.match(spec, /expect\(value\.rendering[\s\S]*?toBeLessThanOrEqual\(MAX_CANVASES\)/);
  assert.match(spec, /expect\(value\.connectedPixels, phase\)\.toBeLessThanOrEqual\(PIXEL_BUDGET\)/);
  assert.match(spec, /expect\(value\.allocatedPixels, phase\)\.toBeLessThanOrEqual\(PIXEL_BUDGET\)/);
  assert.match(spec, /detachedPixels[\s\S]*?\.toBe\(0\)/);
  assert.match(spec, /expect\(peak\.rendering[\s\S]*?toBeLessThanOrEqual\(MAX_CANVASES\)/);
  assert.match(spec, /expect\(peak\.pixels\)\.toBeLessThanOrEqual\(PIXEL_BUDGET\)/);
  assert.match(spec, /expect\(log\.external\)\.toEqual\(\[\]\)/);
  assert.match(spec, /expect\(log\.pageErrors\)\.toEqual\(\[\]\)/);
  assert.match(spec, /RAG_E2E_IMPORT_ALLOWED/);
});

const frame = specTree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "frameFixtureAnchor");
assert.ok(frame);
const frameText = frame.getText(specTree);
function frameHarness(markerBox: Box, paragraphWidth = 1500) {
  let rect = { ...markerBox };
  const scrolls: { left: number; top: number; behavior: string }[] = [];
  const reader = {
    clientLeft: 0, clientTop: 0, clientWidth: 600, clientHeight: 460,
    getBoundingClientRect: () => box(300, 266, 600, 460),
    scrollBy: (options: { left: number; top: number; behavior: string }) => {
      scrolls.push(options); rect = box(rect.left - options.left, rect.top - options.top, rect.width, rect.height);
    },
  };
  const node = { nodeType: 3, textContent: "QLONG-P01-1 : paragraphe beaucoup plus large que le lecteur" };
  const marker = { isConnected: true, firstChild: node, closest: () => reader,
    getBoundingClientRect: () => box(rect.left, rect.top, paragraphWidth, rect.height) };
  const range = { setStart: (value: unknown, offset: number) => { assert.equal(value, node); assert.equal(offset, 0); },
    setEnd: (value: unknown, offset: number) => { assert.equal(value, node); assert.equal(offset, "QLONG-P01-1".length); },
    getBoundingClientRect: () => rect };
  const fn = runInNewContext(compile(`${frameText}\nframeFixtureAnchor;`), {
    document: { createRange: () => range }, window: { innerWidth: 1366, innerHeight: 768 }, Node: { TEXT_NODE: 3 },
  }) as (element: unknown, options: { reference: string; scroll: boolean }) => boolean;
  return { marker, scrolls, read: (scroll: boolean) => fn(marker, { reference: "QLONG-P01-1", scroll }) };
}
test("an inked marker outside the reader viewport cannot justify the capture", () => {
  const h = frameHarness(box(1000, 900, 240, 32));
  assert.equal(h.read(false), false); assert.equal(h.scrolls.length, 0);
  assert.equal(h.read(true), true); assert.equal(h.read(false), true);
  assert.equal(h.scrolls.length, 1); assert.equal(h.scrolls[0].behavior, "instant");
});
test("the visible literal marker passes even though its paragraph is wider than the reader", () => {
  const h = frameHarness(box(420, 400, 240, 32));
  assert.equal(h.read(false), true); assert.equal(h.scrolls.length, 0);
});
test("a partially clipped marker is not visible evidence", () => {
  assert.equal(frameHarness(box(850, 400, 240, 32)).read(false), false);
  assert.equal(frameHarness(box(420, 720, 240, 32)).read(false), false);
});
test("capture follows navigation, framing, painted-content wait and unchanged budget assertions", () => {
  const start = spec.indexOf('await page.getByLabel("Numéro de page").fill("1")');
  const capture = spec.indexOf('await page.screenshot({ path: info.outputPath("canvas-budget-zoom-300.png") });');
  const beforeCapture = spec.slice(start, capture);
  assert.ok(start > 0 && capture > start);
  assert.match(beforeCapture, /scroll: true[\s\S]*?await settled\(\);[\s\S]*?scroll: false/);
  assert.match(beforeCapture, /await sample\("capture-300-framed"\)/);
  assert.equal((beforeCapture.match(/timeout: 30000/g) ?? []).length, 2);
  assert.match(spec.slice(capture), /await scrollThrough\("scroll-300"\)/);
});
