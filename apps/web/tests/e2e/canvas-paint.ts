import { expect, type Page, type TestInfo } from "@playwright/test";

type PaintTarget = {
  pageIndex: number;
  anchorSelector: string;
  viewport: { width: number; height: number };
  zoom: string;
};
export type BitmapEvidence = {
  pageIndex: number;
  viewport: { width: number; height: number };
  zoom: string;
  width: number;
  height: number;
  region?: { x: number; y: number; width: number; height: number };
  ink: number;
  background: number;
  fingerprint: number;
  painted: boolean;
};

/** DOM anchors locate a bounded strip; only original canvas pixels attest ink. */
export function probeOriginalBitmap(target: PaintTarget): BitmapEvidence {
  const zoom = document.querySelector(".zoom-label")?.textContent ?? "";
  const viewport = { width: innerWidth, height: innerHeight };
  const slot = document.querySelector<HTMLElement>(`.pdf-page-slot[data-page-index="${target.pageIndex}"]`);
  const canvas = slot?.querySelector<HTMLCanvasElement>(".pdf-paper canvas");
  const result: BitmapEvidence = { pageIndex: target.pageIndex, viewport, zoom, width: canvas?.width ?? 0, height: canvas?.height ?? 0, ink: 0, background: 0, fingerprint: 0, painted: false };
  if (!Number.isInteger(target.pageIndex) || target.pageIndex < 0 || !canvas?.isConnected
    || viewport.width !== target.viewport.width || viewport.height !== target.viewport.height || zoom !== target.zoom
    || canvas.width <= 0 || canvas.height <= 0 || canvas.width * canvas.height > 24_000_000) return result;
  const anchor = [...slot!.querySelectorAll<HTMLElement>(target.anchorSelector)].find(element => {
    const box = element.getBoundingClientRect();
    return (element.textContent?.trim().length ?? 0) >= 4 && box.width > 0 && box.height > 0;
  });
  if (!anchor) return result;
  const paper = canvas.getBoundingClientRect();
  const box = anchor.getBoundingClientRect();
  if (paper.width <= 0 || paper.height <= 0) return result;
  const x = Math.max(0, Math.floor((box.left - paper.left) * canvas.width / paper.width) - 1);
  const y = Math.max(0, Math.floor((box.top - paper.top) * canvas.height / paper.height) - 1);
  const right = Math.min(canvas.width, Math.ceil((box.right - paper.left) * canvas.width / paper.width) + 1);
  const bottom = Math.min(canvas.height, Math.ceil((box.bottom - paper.top) * canvas.height / paper.height) + 1);
  const width = right - x, height = bottom - y;
  if (width <= 0 || height <= 0 || width * height > 160_000) return result;
  result.region = { x, y, width, height };
  const context = canvas.getContext("2d");
  if (!context) return result;
  const rgba = context.getImageData(x, y, width, height).data;
  let fingerprint = 2166136261;
  for (let index = 0; index < rgba.length; index += 4) {
    if (rgba[index + 3] === 255) {
      if (Math.max(rgba[index], rgba[index + 1], rgba[index + 2]) < 180) result.ink++;
      if (Math.min(rgba[index], rgba[index + 1], rgba[index + 2]) >= 245) result.background++;
    }
    for (let channel = 0; channel < 4; channel++) fingerprint = Math.imul(fingerprint ^ rgba[index + channel], 16777619) >>> 0;
  }
  result.fingerprint = fingerprint;
  result.painted = result.ink >= 8 && result.background >= 8;
  return result;
}

/** Stable ink/background samples, without claiming PDF.js RenderTask completion. */
export async function waitOriginalBitmap(page: Page, info: TestInfo, name: string, target: PaintTarget): Promise<BitmapEvidence> {
  let previous = "";
  let evidence: BitmapEvidence | undefined;
  try {
    await expect.poll(async () => {
      evidence = await page.evaluate(probeOriginalBitmap, target);
      const signature = JSON.stringify(evidence);
      const stable = evidence.painted && signature === previous;
      previous = signature;
      return stable;
    }, { timeout: 15000, intervals: [100, 250, 500], message: "Original PDF bitmap must show stable ink and background before capture" }).toBe(true);
  } finally {
    await info.attach(name, { body: Buffer.from(JSON.stringify({ method: "Read-only bounded original canvas pixels; two identical samples. No extra canvas, overlay pixels, response substitution or RenderTask-completion claim.", target, sample: evidence }, null, 2)), contentType: "application/json" });
  }
  return evidence!;
}
