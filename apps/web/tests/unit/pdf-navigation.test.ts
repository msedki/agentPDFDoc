import assert from "node:assert/strict";
import test from "node:test";
import { pdfPageLayout, pdfScrollTarget, type PdfScrollLayout } from "../../src/lib/pdf-navigation.ts";

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
function layout(pageIndex: number, pageOffset: number): PdfScrollLayout { return { document, pageIndex, pageOffset }; }

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
  const before = layout(13, 10000), after = layout(13, 10320);
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
