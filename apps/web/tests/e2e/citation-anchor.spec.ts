import { test, expect } from "@playwright/test";
import type { PageBlocks, Source } from "../../src/lib/types";
import { watchPage } from "./guards";
import { detail, guardTarget, readLifecycleTarget, sha256 } from "./lifecycle-target";

const fixtureSha = "994c37186d9985af8ecf5fbde4e2194dcdc061c0fca4f3025dcc643acadf3f86";
const queryId = "2d7f8565-f25a-4d8b-9123-04eddaa8ad99";
const markers = Array.from({ length: 6 }, (_, index) => `QLONG-P14-${index + 1}`);

/** TextLayer native indépendante des bboxes du registre ; lectures bitmap bornées comme l'oracle Q05. */
function measureCitationAnchor({ pageIndex, references }: { pageIndex: number; references: string[] }) {
  const slot = document.querySelector(`.pdf-page-slot[data-page-index="${pageIndex}"]`);
  const canvas = slot?.querySelector<HTMLCanvasElement>(".pdf-paper canvas");
  if (!slot || !canvas || !canvas.isConnected || canvas.width <= 0 || canvas.height <= 0) return null;
  const rectangle = (element: Element) => {
    const box = element.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height };
  };
  const canvasBox = rectangle(canvas);
  const viewport = slot.closest(".pdf-scroll");
  if (!viewport) return null;
  const slotBox = rectangle(slot);
  const viewportBox = rectangle(viewport);
  const alignedInViewport = slotBox.y <= viewportBox.y + 104
    && slotBox.y + slotBox.height > viewportBox.y + 100
    && canvasBox.x < viewportBox.x + viewportBox.width
    && canvasBox.x + canvasBox.width > viewportBox.x;
  if (![canvasBox.x, canvasBox.y, canvasBox.width, canvasBox.height].every(Number.isFinite)
      || canvasBox.width <= 0 || canvasBox.height <= 0) return null;
  const highlights = [...slot.querySelectorAll('[data-testid="source-highlight"]')].map(rectangle);
  const context = canvas.getContext("2d");
  const anchors = references.map(reference => {
    const matches = [...slot.querySelectorAll<HTMLElement>(".textLayer span")].filter(span => span.textContent?.includes(reference));
    if (matches.length !== 1) return { reference, covered: false, painted: false, reason: "native_marker_not_unique" };
    const span = matches[0];
    const native = rectangle(span);
    if (![native.x, native.y, native.width, native.height].every(Number.isFinite) || native.width <= 0 || native.height <= 0) {
      return { reference, covered: false, painted: false, reason: "native_marker_without_geometry" };
    }
    // Tolérance locale de quatre pixels CSS, comme workspace.spec.ts ; pas un seuil de recette globale.
    const coveringIndices = highlights.flatMap((box, index) => box.width > 0 && box.height > 0
      && native.x >= box.x - 4 && native.y >= box.y - 4
      && native.x + native.width <= box.x + box.width + 4
      && native.y + native.height <= box.y + box.height + 4 ? [index] : []);
    const covered = coveringIndices.length === 1;
    const intersectionRatios = highlights.map(box => {
      const width = Math.max(0, Math.min(native.x + native.width, box.x + box.width) - Math.max(native.x, box.x));
      const height = Math.max(0, Math.min(native.y + native.height, box.y + box.height) - Math.max(native.y, box.y));
      return width * height / (native.width * native.height);
    });
    const left = Math.max(0, Math.floor((native.x - canvasBox.x) * canvas.width / canvasBox.width) - 1);
    const top = Math.max(0, Math.floor((native.y - canvasBox.y) * canvas.height / canvasBox.height) - 1);
    const right = Math.min(canvas.width, Math.ceil((native.x + native.width - canvasBox.x) * canvas.width / canvasBox.width) + 1);
    const bottom = Math.min(canvas.height, Math.ceil((native.y + native.height - canvasBox.y) * canvas.height / canvasBox.height) + 1);
    const pixels = (right - left) * (bottom - top);
    if (!context || right <= left || bottom <= top || pixels > 160_000) {
      return { reference, native, covered, coveringIndices, painted: false, intersectionRatios, reason: "bounded_bitmap_unavailable" };
    }
    const rgba = context.getImageData(left, top, right - left, bottom - top).data;
    let ink = 0, background = 0;
    for (let offset = 0; offset < rgba.length; offset += 4) {
      if (rgba[offset + 3] !== 255) continue;
      if (Math.max(rgba[offset], rgba[offset + 1], rgba[offset + 2]) < 180) ink++;
      if (Math.min(rgba[offset], rgba[offset + 1], rgba[offset + 2]) >= 245) background++;
    }
    const visible = native.x >= viewportBox.x - 4 && native.y >= viewportBox.y - 4
      && native.x + native.width <= viewportBox.x + viewportBox.width + 4
      && native.y + native.height <= viewportBox.y + viewportBox.height + 4;
    return { reference, native, covered, coveringIndices, intersectionRatios, ink, background, pixels, visible,
      textColor: getComputedStyle(span).color, painted: ink >= 8 && background >= 8 };
  });
  const distinctRegions = new Set(anchors.flatMap(anchor => anchor.coveringIndices ?? [])).size;
  return { pageIndex, canvas: { width: canvas.width, height: canvas.height, box: canvasBox }, highlights, anchors,
    slotBox, viewportBox, alignedInViewport,
    passed: alignedInViewport && anchors[0]?.visible === true && anchors.length === 6 && distinctRegions === 6
      && anchors.every(anchor => anchor.covered && anchor.painted) };
}

test("persisted Q06 citation opens its native page anchors and returns to the registered passage", async ({ page, request }, info) => {
  test.skip(process.env.RAG_E2E_LIFECYCLE_ALLOWED !== "1", "Requires an explicitly admitted GET-only window on the preserved Q05/Q06 instance.");
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("read_citation_anchor"), "The exact read_citation_anchor permit is absent.");
  await guardTarget(request, target, info);
  const bound = target.old_citation;
  expect(bound).toBeTruthy();
  if (!bound) throw new Error("The persisted Q06 citation binding is required.");
  expect(bound).toMatchObject({ query_id: queryId, source_id: "S005", page_index: 13,
    version_id: "9dc53b7d-f2ef-4c87-b6a4-b803355987bd", generation_id: "92af4c8c-8b33-4744-af89-a6fdc6749e58",
    extraction_revision_id: "20153a0f-75f0-5179-9c53-d0b06497e4ec" });
  expect(target.document.id).toBe("60ab5828-afa1-4365-808e-b4dd304a6a14");
  expect(Object.keys(bound.block_hashes).length).toBeGreaterThanOrEqual(6);
  const document = await detail(request, target);
  expect(document.versions.find((version: { id: string }) => version.id === bound.version_id)?.sha256).toBe(fixtureSha);
  const original = await request.get(`${target.origin}/api/v1/versions/${bound.version_id}/file`);
  expect(original.status()).toBe(200);
  const bytes = await original.body();
  expect(bytes.length).toBe(55_337);
  expect(sha256(bytes)).toBe(fixtureSha);
  const registry = await request.get(`${target.origin}/api/v1/citations/${queryId}/S005`);
  expect(registry.status()).toBe(200);
  const source = await registry.json() as Source;
  expect(source).toMatchObject({ source_id: "S005", document_id: target.document.id, version_id: bound.version_id,
    generation_id: bound.generation_id, extraction_revision_id: bound.extraction_revision_id, page_index: 13, precision: "block" });
  expect(source.bboxes).toHaveLength(9);
  for (const [id, hash] of Object.entries(bound.block_hashes)) {
    const block = source.blocks?.find(item => item.id === id);
    expect(block?.source_text_hash).toBe(hash);
    expect(sha256(Buffer.from(block?.raw_text ?? block?.text ?? "", "utf8"))).toBe(hash);
  }
  const blocksResponse = await request.get(`${target.origin}/api/v1/versions/${bound.version_id}/pages/13/blocks?extraction_revision_id=${bound.extraction_revision_id}`);
  expect(blocksResponse.status()).toBe(200);
  const blocks = await blocksResponse.json() as PageBlocks;
  expect(blocks).toMatchObject({ version_id: bound.version_id, extraction_revision_id: bound.extraction_revision_id,
    page: { page_index: 13, extraction_state: "native" } });
  for (const reference of markers) {
    const matches = source.blocks?.filter(block => block.text.includes(reference)) ?? [];
    expect(matches).toHaveLength(1);
    expect(matches[0].page_index).toBe(13);
    expect(bound.block_hashes[matches[0].id]).toBeTruthy();
    expect(blocks.blocks.find(block => block.id === matches[0].id)?.source_text_hash).toBe(bound.block_hashes[matches[0].id]);
  }

  await page.setViewportSize({ width: 1366, height: 768 });
  const log = watchPage(page);
  const pinnedResponses: { path: string; revision: string | null; status: number }[] = [];
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname === `/api/v1/versions/${bound.version_id}/pages/13/blocks`) {
      pinnedResponses.push({ path: url.pathname, revision: url.searchParams.get("extraction_revision_id"), status: response.status() });
    }
  });
  let geometry: ReturnType<typeof measureCitationAnchor> = null;
  let returnGeometry: ReturnType<typeof measureCitationAnchor> = null;
  let resizedGeometry: ReturnType<typeof measureCitationAnchor> = null;
  let beforeResizeWidth: number | null = null;
  try {
    // Production deep-link, not a restored chat, injected store, mocked response or new question.
    await page.goto(`/workspace/?citation_query=${queryId}&citation_source=S005`);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("14");
    await expect(page.locator(".source-navigation")).toContainText("S005");
    await expect(page.locator(".source-navigation")).toContainText(bound.extraction_revision_id.slice(0, 8));
    await page.getByLabel("Actions et versions du document").click();
    await expect(page.getByLabel("Version affichée")).toHaveValue(bound.version_id);
    await page.getByLabel("Actions et versions du document").click();
    const scope = await page.getByTestId("scope-summary").innerText();
    const sourceSlot = page.locator('.pdf-page-slot[data-page-index="13"]');
    await expect(sourceSlot.getByTestId("source-highlight")).toHaveCount(9);
    await expect(sourceSlot.locator(".ocr-text-layer span")).toHaveCount(0);
    await expect.poll(async () => {
      geometry = await page.evaluate(measureCitationAnchor, { pageIndex: 13, references: markers });
      return geometry?.passed ?? false;
    }, { timeout: 30_000, message: "Six native QLONG-P14 anchors must be covered and contain bounded original-canvas ink." }).toBe(true);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("14");
    expect(pinnedResponses.some(response => response.revision === bound.extraction_revision_id && response.status === 200)).toBe(true);
    await page.screenshot({ path: info.outputPath("registered-source-page14.png"), fullPage: true });

    // The deep-link has no pre-load reader position. Exercise the existing real return: source14 → original1 → source14.
    await page.getByRole("navigation", { name: "Arborescence documentaire" }).getByTitle(document.relative_path, { exact: true }).click();
    await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
    await expect(page.locator(".source-navigation")).toHaveCount(0);
    await expect(page.getByTestId("scope-summary")).toHaveText(scope, { useInnerText: true });
    await page.getByRole("button", { name: "Revenir au passage précédent", exact: true }).click();
    await expect(page.getByLabel("Numéro de page")).toHaveValue("14");
    await expect(page.locator(".source-navigation")).toContainText("S005");
    await expect(page.locator(".source-navigation")).toContainText(bound.extraction_revision_id.slice(0, 8));
    await expect(page.getByTestId("scope-summary")).toHaveText(scope, { useInnerText: true });
    await expect.poll(async () => {
      returnGeometry = await page.evaluate(measureCitationAnchor, { pageIndex: 13, references: markers });
      return returnGeometry?.passed ?? false;
    }, { timeout: 30_000, message: "Returning must restore the actual registered source and its six native anchors." }).toBe(true);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("14");
    await page.screenshot({ path: info.outputPath("returned-registered-source-page14.png"), fullPage: true });
    // Exercise the actual late-width path, without another document, question or browser run.
    beforeResizeWidth = await sourceSlot.locator("canvas").evaluate(canvas => canvas.getBoundingClientRect().width);
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect.poll(async () => {
      resizedGeometry = await page.evaluate(measureCitationAnchor, { pageIndex: 13, references: markers });
      return Boolean(resizedGeometry?.passed && beforeResizeWidth !== null && resizedGeometry.canvas.box.width > beforeResizeWidth);
    }, { timeout: 30_000, message: "Resizing the reader must keep page14 visible and its native anchors aligned." }).toBe(true);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("14");
    await expect(page.getByTestId("scope-summary")).toHaveText(scope, { useInnerText: true });
    await page.screenshot({ path: info.outputPath("resized-registered-source-page14.png"), fullPage: true });
    expect(log.mutations).toEqual([]);
    expect(log.external).toEqual([]);
    expect(log.pageErrors).toEqual([]);
  } finally {
    await info.attach("registered-citation-anchor", { body: Buffer.from(JSON.stringify({
      query_id: queryId, source_id: "S005", document_id: source.document_id, version_id: source.version_id,
      generation_id: source.generation_id, extraction_revision_id: source.extraction_revision_id,
      page_index: source.page_index, precision: source.precision, original_sha256: fixtureSha,
      original_bytes: bytes.length, block_hashes: bound.block_hashes, geometry, returnGeometry, resizedGeometry, beforeResizeWidth, pinnedResponses,
      network: log, limits: "One persisted citation and six marker regions at 1366x768 and 1920x1080; no inline-chat click, distinct archive, 95% corpus rate, D06 global, CPU performance or new model generation. Bitmap ink is not RenderTask completion."
    }, null, 2)), contentType: "application/json" });
  }
});
