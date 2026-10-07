import assert from "node:assert/strict";
import test from "node:test";
import { pdfPageAtScroll, pdfPageLayout, pdfScrollTarget, type PdfScrollLayout } from "../../src/lib/pdf-navigation.ts";

const document = {};
function offsets(width: number) {
  const estimatedHeight = (width - 48) * 1.414 + 52;
  return Array.from({ length: 15 }, (_, index) => index * estimatedHeight);
}
function pageAtScroll(pageOffsets: number[], scrollTop: number) {
  let page = 0;
  while (page + 1 < pageOffsets.length - 1 && pageOffsets[page + 1] <= scrollTop + 100) page++;
  return page;
}
/** `scrollTop` : position de lecture observée dans cette géométrie, avant tout recadrage par le navigateur. */
function layout(pageIndex: number, pageOffset: number, scrollTop = pageOffset): PdfScrollLayout { return { document, pageIndex, pageOffset, scrollTop }; }

test("rotation of a two-page document keeps page2 although the browser already clamped scrollTop (R26-KIT-02 D3)", () => {
  // Trace of the failed recette: 1366×768, page 100 % 582.688×824.087 px, page2 at scrollTop 876; scroll area 388 px
  // high while the extraction notice is displayed. After the rotation the viewer landed at scrollTop 128, i.e. page1.
  const width = 582.688 + 48, clientHeight = 388;
  const portrait = 824.087 + 52;
  const before = layout(1, portrait);
  const rotated = pdfPageLayout(null, "rotated", width, 1, 90).height + 52;
  const content = 2 * rotated;
  // The new, shorter slots are committed before the layout effect reads scrollTop: the browser has clamped it.
  const clamped = Math.min(before.scrollTop, content - clientHeight);
  assert.ok(clamped < before.scrollTop, "the rotation shrinks the content below the reading position");
  assert.ok(rotated <= content - clientHeight, "page2 remains reachable after the rotation");
  const target = pdfScrollTarget(before, { document, pageIndex: 1, pageOffset: rotated }, 1, clamped);
  // Float sum (876.087 + 464.08… − 876.087): equality up to the last bits, far below one CSS pixel.
  assert.ok(Math.abs(target! - rotated) < 1e-9, `the start of page2 is kept, not the clamped position minus the height delta (target ${target})`);
  assert.equal(pageAtScroll([0, rotated, content], target!), 1);
});

test("a taller viewer clamping the scroll keeps the unreachable last page current (R26-UI-02, 1366×768 → 1920×1080)", () => {
  // Run C trace: page2 of two rotated pages at 125 % (567 px slots), scrollTop 567; the viewer grows before React
  // measures the new width, so the browser clamps scrollTop to 1134 − 770 = 364 and fires a scroll event.
  const offsets = [0, 567, 1134];
  assert.equal(pdfPageAtScroll(offsets, 2, 364, 364, 1), 1, "a clamp at the bottom is not a navigation to page1");
  assert.equal(pdfPageAtScroll(offsets, 2, 300, 364, 1), 0, "scrolling up from the bottom still selects page1");
  assert.equal(pdfPageAtScroll(offsets, 2, 364, 364, 0), 0, "reaching the bottom from page1 does not jump to page2");
  assert.equal(pdfPageAtScroll(offsets, 2, 567, 567, 1), 1);
  assert.equal(pdfPageAtScroll([0, 400, 800], 2, 0, 0, 1), 1, "both pages visible: the requested page2 stays current");
  // Reachable last page: the reading line decides, as before.
  assert.equal(pdfPageAtScroll([0, 300, 1300], 2, 600, 600, 0), 1);
});

test("an unreachable page kept at the bottom is shown from its start once the geometry grows", () => {
  // Following commit of the same trace: new width, page2 offset 802; the recorded position (364) is 203 px above it.
  assert.equal(pdfScrollTarget(layout(1, 567, 364), { document, pageIndex: 1, pageOffset: 802 }, 1, 364), 802);
  // A reading line inside the page with its start up to 100 px below the top keeps that exact offset.
  assert.equal(pdfScrollTarget(layout(13, 10000, 9950), { document, pageIndex: 13, pageOffset: 10320 }, 13, 9950), 10270);
});

test("within-page position measured before a shrinking commit survives the browser clamp", () => {
  // Reader 120 px into page14; the preceding pages are measured 400 px shorter and the end of the document is near.
  const before = layout(13, 10000, 10120), after = layout(13, 9600);
  assert.equal(pdfScrollTarget(before, after, 13, 9900), 9720);
});

test("late width measurement keeps page14 instead of feeding page13 back into navigation", () => {
  // Same initial width, A4 estimate, 52px slot overhead and +100px scroll probe as PdfViewer.
  const initial = offsets(600), measured = offsets(646);
  const before = layout(13, initial[13]), after = layout(13, measured[13]);
  assert.equal(pageAtScroll(measured, before.pageOffset), 12, "unchanged scroll offset genuinely resolves to page13");
  const target = pdfScrollTarget(before, after, 13, before.pageOffset);
  assert.equal(target, after.pageOffset, "active page must follow its revised offset");
  assert.equal(pageAtScroll(measured, target!), 13);
});

test("measured preceding page heights preserve the reader's within-page scroll position", () => {
  const before = layout(13, 10000, 10240), after = layout(13, 10320, 10560);
  assert.equal(pdfScrollTarget(before, after, 13, 10240), 10560);
  assert.equal(pdfScrollTarget(after, before, 13, 10560), 10240);
});

test("manual scrolling across a page boundary does not snap back to its beginning", () => {
  const before = layout(12, 9600), after = layout(13, 10400);
  assert.equal(pdfScrollTarget(before, after, 13, 10640), null);
  assert.equal(pdfScrollTarget(after, after, 13, 10720), null);
});

test("explicit navigation and return move page14 to page1 and back to page14", () => {
  const first = layout(0, 0), source = layout(13, offsets(646)[13]);
  assert.equal(pdfScrollTarget(first, source, 0, 0), source.pageOffset);
  assert.equal(pdfScrollTarget(source, first, 13, source.pageOffset), 0);
  assert.equal(pdfScrollTarget(first, source, 0, 0), source.pageOffset);
});

test("a new PDF starts at the requested page even when the previous center number matches", () => {
  const before = layout(13, 10000), after = { document: {}, pageIndex: 13, pageOffset: 12000 };
  assert.equal(pdfScrollTarget(before, after, 13, 10000), 12000);
  assert.equal(pdfScrollTarget(null, after, 13, 0), 12000);
});

test("stable geometry does not issue redundant scrolls", () => {
  const source = layout(13, 10000);
  assert.equal(pdfScrollTarget(source, source, 13, 10000), null);
  assert.equal(pdfScrollTarget(source, source, 13, 10400), null);
});

test("resized virtual slots cannot clamp the requested page14 while its PDF viewport is pending", () => {
  // Dimensions from closed native02: five slots (pages10..14), content734px high.
  const previousViewport = { width: 582.6875, height: 824.078125 };
  const nextWidth = 848.609375 + 48;
  const estimate = pdfPageLayout(null, "new", nextWidth, 1, 0).height + 52;
  const requested = 13 * estimate;
  const pending = pdfPageLayout({ key: "old", viewport: previousViewport }, "new", nextWidth, 1, 0);
  const extent = 9 * estimate + 5 * (pending.height + 52);
  const actualScrollTop = Math.min(requested, extent - 734);
  assert.equal(actualScrollTop, requested, `page14 target was clamped by ${requested - actualScrollTop}px`);
  assert.equal(pageAtScroll(Array.from({ length: 15 }, (_, index) => index * estimate), actualScrollTop), 13);
  assert.equal(pending.viewport, null, "old PDF viewport is not a current-layout measurement");
});

test("pending PDF placeholders use the same zoom and rotation dimensions as virtual offsets", () => {
  const old = { key: "old", viewport: { width: 600, height: 848 } };
  const pending = pdfPageLayout(old, "new", 648, 1.5, 90);
  assert.equal(pending.width, 900);
  assert.equal(pending.height, 600 * (1 / 1.414) * 1.5);
  const current = pdfPageLayout(old, "old", 648, 1.5, 90);
  assert.equal(current.viewport, old.viewport);
  assert.equal(current.width, 600);
  assert.equal(current.height, 848);
});
