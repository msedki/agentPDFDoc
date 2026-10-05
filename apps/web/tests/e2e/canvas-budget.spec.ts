import { test, expect } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { fixtureAtPath, importPublished, watchPage } from "./guards";
import { probeFixtureCanvasPaint, type CanvasAllocation, type CanvasPaintProbe, type CanvasPaintState } from "./canvas-paint-oracle";

// Budget de rendu du lecteur : au plus 5 canvases et 24 M pixels RGBA, pendant
// défilement et zoom jusqu'à 300 %, puis libération des canvases détachés.
// pdf.js 6.3 (TextLayer.#getCtx) attache à body un canvas caché de mesure du texte,
// retiré seulement par TextLayer.cleanup() à la destruction du document : il sort du
// compte des canvases de rendu, mais ses pixels restent dans le budget et il est joint.
const fixturePath = "qualification-v2.1/layouts/long-document-14p.pdf";
const MAX_CANVASES = 5;
const PIXEL_BUDGET = 24_000_000;
type Census = { connected: number; rendering: number; pageCanvases: number; measuring: { width: number; height: number; lang: string }[]; connectedPixels: number; registered: number; allocatedPixels: number; detachedAllocated: number; detachedPixels: number };
type Sample = Census & { phase: string; zoom: string; scrollTop: number };

// Frame just the literal marker, not its much wider paragraph at 300 %.
// A DOM Range measures existing text; only the reader's real scroll position changes.
function frameFixtureAnchor(element: HTMLElement, { reference, scroll }: { reference: string; scroll: boolean }): boolean {
  const reader = element.closest<HTMLElement>('[data-testid="pdf-scroll"]');
  const node = element.firstChild;
  if (!reader || !element.isConnected || node?.nodeType !== Node.TEXT_NODE) return false;
  const offset = (node.textContent ?? "").indexOf(reference);
  if (offset < 0) return false;
  const range = document.createRange();
  range.setStart(node, offset);
  range.setEnd(node, offset + reference.length);
  const viewport = reader.getBoundingClientRect();
  const left = Math.max(0, viewport.left + reader.clientLeft);
  const top = Math.max(0, viewport.top + reader.clientTop);
  const right = Math.min(window.innerWidth, viewport.left + reader.clientLeft + reader.clientWidth);
  const bottom = Math.min(window.innerHeight, viewport.top + reader.clientTop + reader.clientHeight);
  if (scroll) {
    const before = range.getBoundingClientRect();
    reader.scrollBy({ left: (before.left + before.right - left - right) / 2,
      top: (before.top + before.bottom - top - bottom) / 2, behavior: "instant" });
  }
  const marker = range.getBoundingClientRect();
  return marker.width > 0 && marker.height > 0 && right > left && bottom > top
    && marker.left >= left && marker.right <= right && marker.top >= top && marker.bottom <= bottom;
}

test("scroll and zoom to 300 % stay within five canvases and 24 M pixels, then release detached canvases", async ({ page, request, browser }, info) => {
  test.setTimeout(900000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Import de fixtures contrôlées sur stockage isolé autorisé uniquement ; NOT_RUN sinon.");
  const input = fixtureAtPath(fixturePath);
  test.skip(!input, `Fixture ${fixturePath} absente du manifeste et de son sidecar : NOT_RUN.`);
  const log = watchPage(page);
  // Instrumentation de test uniquement : tout canvas qui obtient un contexte est
  // recensé, pour vérifier aussi les canvases retirés du DOM (miniatures ou rendus remplacés).
  await page.addInitScript(() => {
    const registry: HTMLCanvasElement[] = [];
    const original = HTMLCanvasElement.prototype.getContext;
    const allocations = new WeakMap<HTMLCanvasElement, CanvasAllocation>();
    let epoch = 0;
    // Setting even an unchanged bitmap dimension clears it (HTML canvas contract).
    // Track the real producer's resets, including raster sizes capped at two zooms.
    for (const dimension of ["width", "height"] as const) {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype, dimension)!;
      const set = descriptor.set!;
      Object.defineProperty(HTMLCanvasElement.prototype, dimension, { ...descriptor, set(this: HTMLCanvasElement, value: number) {
        set.call(this, value);
        allocations.set(this, { epoch: ++epoch, zoom: document.querySelector(".zoom-label")?.textContent ?? "" });
      } });
    }
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args: unknown[]) {
      if (!registry.includes(this)) registry.push(this);
      return (original as (...values: unknown[]) => RenderingContext | null).apply(this, args);
    } as unknown as typeof original;
    (window as unknown as { __canvasPaintState: CanvasPaintState }).__canvasPaintState = {
      checkpoint: () => epoch,
      allocation: canvas => allocations.get(canvas),
      // Bypass our getContext wrapper: an observation cannot register a producer reset.
      readPixels: (canvas, x, y, width, height) => (original.call(canvas, "2d") as CanvasRenderingContext2D | null)?.getImageData(x, y, width, height).data,
    };
    const area = (canvas: HTMLCanvasElement) => canvas.width * canvas.height;
    const pixels = (canvases: HTMLCanvasElement[]) => canvases.reduce((sum, canvas) => sum + area(canvas), 0);
    const measuring = (canvas: HTMLCanvasElement) => canvas.parentElement === document.body && canvas.style.display === "none";
    (window as unknown as { __canvasCensus: () => Census }).__canvasCensus = () => {
      const connected = [...document.querySelectorAll("canvas")];
      const rendering = connected.filter(canvas => !measuring(canvas));
      const detached = registry.filter(canvas => !canvas.isConnected && area(canvas) > 0);
      return { connected: connected.length, rendering: rendering.length, pageCanvases: rendering.filter(canvas => canvas.closest(".pdf-paper")).length, measuring: connected.filter(measuring).map(canvas => ({ width: canvas.width, height: canvas.height, lang: canvas.lang })), connectedPixels: pixels(connected), registered: registry.length, allocatedPixels: pixels(registry), detachedAllocated: detached.length, detachedPixels: pixels(detached) };
    };
  });
  await monitorBrowser(browser, "canvas-budget-start", info);
  const imported = await importPublished(page, request, input!, info, ["ready", "ready_partial"]);
  const expectedPages = Number(input!.expected_pages);
  expect(expectedPages, "Plus de pages que la fenêtre de cinq canvases").toBeGreaterThan(MAX_CANVASES);
  await page.goto(`/workspace/?document=${encodeURIComponent(imported.documentId)}&version=${encodeURIComponent(imported.versionId)}&page=1`);
  await expect(page.locator(".page-input span")).toHaveText(`/ ${expectedPages}`);
  await page.evaluate(() => {
    const census = (window as unknown as { __canvasCensus: () => Census }).__canvasCensus;
    const peak = { rendering: 0, measuring: 0, pixels: 0, frames: 0 };
    (window as unknown as { __canvasPeak: typeof peak }).__canvasPeak = peak;
    const tick = () => {
      const value = census();
      peak.rendering = Math.max(peak.rendering, value.rendering);
      peak.measuring = Math.max(peak.measuring, value.measuring.length);
      peak.pixels = Math.max(peak.pixels, value.connectedPixels);
      peak.frames++;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  const samples: Sample[] = [];
  const paintSamples: { phase: string; evidence: CanvasPaintProbe }[] = [];
  const scroller = page.getByTestId("pdf-scroll");
  let zoom = 100;
  let paint: CanvasPaintProbe;
  const settled = (afterEpoch = 0) => expect.poll(async () => {
    paint = await page.evaluate(probeFixtureCanvasPaint, { zoom: `${zoom} %`, afterEpoch });
    return paint.painted;
  }, { timeout: 30000, message: "QLONG-14 : encre réelle des premier/sixième repères dans les bitmaps du zoom demandé, après réallocation ; pas une preuve de fin RenderTask" }).toBe(true);
  const sample = async (phase: string) => {
    const value: Sample = await page.evaluate(phase => ({ phase, zoom: document.querySelector(".zoom-label")?.textContent ?? "", scrollTop: document.querySelector('[data-testid="pdf-scroll"]')?.scrollTop ?? 0, ...(window as unknown as { __canvasCensus: () => Census }).__canvasCensus() }), phase);
    samples.push(value);
    paintSamples.push({ phase, evidence: paint });
    expect(value.rendering, `${phase} : canvases de rendu (mesure pdf.js exclue)`).toBeLessThanOrEqual(MAX_CANVASES);
    expect(value.connectedPixels, phase).toBeLessThanOrEqual(PIXEL_BUDGET);
    expect(value.allocatedPixels, phase).toBeLessThanOrEqual(PIXEL_BUDGET);
    return value;
  };
  const scrollThrough = async (phase: string) => {
    await scroller.evaluate(element => element.scrollTo({ top: 0, behavior: "instant" }));
    for (let step = 0; step < 400; step++) {
      await settled();
      await sample(`${phase}-${step}`);
      const atEnd = await scroller.evaluate(element => { const before = element.scrollTop; element.scrollBy({ top: element.clientHeight * 0.9, behavior: "instant" }); return element.scrollTop === before; });
      if (atEnd) break;
    }
    await expect(page.getByLabel("Numéro de page")).toHaveValue(String(expectedPages));
  };

  await settled();
  await sample("opened-100");
  await scrollThrough("scroll-100");
  const zoomIn = page.getByRole("button", { name: "Augmenter le zoom" });
  for (let step = 0; step < 8; step++) {
    const beforeZoom = await page.evaluate(() => (window as unknown as { __canvasPaintState: CanvasPaintState }).__canvasPaintState.checkpoint());
    await zoomIn.click();
    zoom += 25;
    await settled(beforeZoom);
    await sample(`zoom-step-${step + 1}`);
  }
  await expect(page.locator(".zoom-label")).toHaveText("300 %");
  await expect(zoomIn).toBeDisabled();
  await page.getByLabel("Numéro de page").fill("1");
  await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
  await settled();
  const captureAnchor = page.locator('.pdf-page-slot[data-page-index="0"] .textLayer span').filter({ hasText: "QLONG-P01-1" });
  await expect(captureAnchor).toHaveCount(1);
  await expect.poll(() => captureAnchor.evaluate(frameFixtureAnchor, { reference: "QLONG-P01-1", scroll: true }),
    { timeout: 30000, message: "Le repère synthétique doit être entièrement cadré dans le viewport du lecteur à300%" }).toBe(true);
  await settled();
  await expect.poll(() => captureAnchor.evaluate(frameFixtureAnchor, { reference: "QLONG-P01-1", scroll: false }),
    { timeout: 30000, message: "Le repère doit rester visible après l'attente des pixels" }).toBe(true);
  await sample("capture-300-framed");
  await page.screenshot({ path: info.outputPath("canvas-budget-zoom-300.png") });
  await monitorBrowser(browser, "canvas-budget-zoom-300", info);
  await scrollThrough("scroll-300");
  await scroller.evaluate(element => element.scrollTo({ top: 0, behavior: "instant" }));
  await settled();
  await expect.poll(async () => (await sample("released")).detachedPixels, { timeout: 30000, message: "Les canvases retirés du DOM doivent être libérés (largeur/hauteur 0)" }).toBe(0);
  const peak = await page.evaluate(() => (window as unknown as { __canvasPeak: { rendering: number; measuring: number; pixels: number; frames: number } }).__canvasPeak);
  await info.attach("canvas-budget-samples", { body: Buffer.from(JSON.stringify({ document_id: imported.documentId, version_id: imported.versionId, job_state: imported.job.state, viewport: page.viewportSize(), device_scale_factor: await page.evaluate(() => window.devicePixelRatio), peak_per_animation_frame: peak, samples, paintSamples, method: "Canvases DOM par frame + registre des canvases ayant obtenu un contexte ; pixels = largeur x hauteur allouées (RGBA), tous canvases compris. Le compte de 5 exclut seulement le canvas de mesure du TextLayer pdf.js (enfant direct de body, display:none), relevé dans measuring. Attente bornée30s : encre/fond des repères natifs QLONG-Pxx-1/-6 dans chaque bitmap, zoom exact et allocation postérieure au clic ; la couche texte localise les régions, sans prouver peinture ni fin de RenderTask." }, null, 2)), contentType: "application/json" });
  expect(peak.rendering, "canvases de rendu par frame (mesure pdf.js exclue)").toBeLessThanOrEqual(MAX_CANVASES);
  expect(peak.pixels).toBeLessThanOrEqual(PIXEL_BUDGET);
  await monitorBrowser(browser, "canvas-budget-end", info);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
