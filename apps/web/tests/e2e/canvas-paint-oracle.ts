/** QA only: pixel evidence for the known QLONG-14 fixture, never RenderTask completion. */
export type CanvasAllocation = { epoch: number; zoom: string };
export type CanvasPaintState = {
  checkpoint(): number;
  allocation(canvas: HTMLCanvasElement): CanvasAllocation | undefined;
  readPixels(canvas: HTMLCanvasElement, x: number, y: number, width: number, height: number): Uint8ClampedArray | undefined;
};
export type CanvasPaintEvidence = {
  pageIndex: number;
  width: number;
  height: number;
  allocation?: CanvasAllocation;
  anchors: { reference: string; ink: number; background: number; pixels: number }[];
  painted: boolean;
};
export type CanvasPaintProbe = { zoom: string; afterEpoch: number; pages: CanvasPaintEvidence[]; painted: boolean };

// Self-contained so Playwright can serialize this exact function into the page.
// TextLayer identifies the expected fixture regions; only bitmap reads prove ink.
// Neither that layer nor these pixels attest that the PDF.js render promise settled.
export function probeFixtureCanvasPaint({ zoom, afterEpoch }: { zoom: string; afterEpoch: number }): CanvasPaintProbe {
  const state = (window as unknown as { __canvasPaintState: CanvasPaintState }).__canvasPaintState;
  const actualZoom = document.querySelector(".zoom-label")?.textContent ?? "";
  const canvases = [...document.querySelectorAll<HTMLCanvasElement>(".pdf-paper canvas")];
  const pages = canvases.map(canvas => {
    const slot = canvas.closest<HTMLElement>(".pdf-page-slot");
    const pageIndex = Number(slot?.dataset.pageIndex ?? -1);
    const allocation = state.allocation(canvas);
    const result: CanvasPaintEvidence = { pageIndex, width: canvas.width, height: canvas.height, allocation, anchors: [], painted: false };
    if (actualZoom !== zoom || !canvas.isConnected || canvas.width <= 0 || canvas.height <= 0
      || !allocation || allocation.zoom !== zoom || allocation.epoch <= afterEpoch
      || !Number.isInteger(pageIndex) || pageIndex < 0 || pageIndex >= 14 || !slot) return result;
    const canvasBox = canvas.getBoundingClientRect();
    if (canvasBox.width <= 0 || canvasBox.height <= 0) return result;
    for (const paragraph of [1, 6]) {
      const reference = `QLONG-P${String(pageIndex + 1).padStart(2, "0")}-${paragraph}`;
      const spans = [...slot.querySelectorAll<HTMLElement>(".textLayer span")].filter(span => span.textContent?.includes(reference));
      if (spans.length !== 1) return result;
      const box = spans[0].getBoundingClientRect();
      if (box.width <= 0 || box.height <= 0) return result;
      const left = Math.max(0, Math.floor((box.left - canvasBox.left) * canvas.width / canvasBox.width) - 1);
      const top = Math.max(0, Math.floor((box.top - canvasBox.top) * canvas.height / canvasBox.height) - 1);
      const right = Math.min(canvas.width, Math.ceil((box.right - canvasBox.left) * canvas.width / canvasBox.width) + 1);
      const bottom = Math.min(canvas.height, Math.ceil((box.bottom - canvasBox.top) * canvas.height / canvasBox.height) + 1);
      const pixels = (right - left) * (bottom - top);
      // Read only these two glyph strips, without another canvas or full-page copy.
      if (right <= left || bottom <= top || pixels > 160_000) return result;
      const rgba = state.readPixels(canvas, left, top, right - left, bottom - top);
      if (!rgba || rgba.length !== pixels * 4) return result;
      let ink = 0, background = 0;
      for (let offset = 0; offset < rgba.length; offset += 4) {
        if (rgba[offset + 3] !== 255) continue;
        if (Math.max(rgba[offset], rgba[offset + 1], rgba[offset + 2]) < 180) ink++;
        if (Math.min(rgba[offset], rgba[offset + 1], rgba[offset + 2]) >= 245) background++;
      }
      result.anchors.push({ reference, ink, background, pixels });
    }
    result.painted = result.anchors.length === 2 && result.anchors.every(anchor => anchor.ink >= 8 && anchor.background >= 8);
    return result;
  });
  return { zoom: actualZoom, afterEpoch, pages, painted: pages.length > 0 && pages.every(page => page.painted) };
}
