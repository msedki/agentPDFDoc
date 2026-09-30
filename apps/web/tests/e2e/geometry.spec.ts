import { test, expect, type Page } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { fixture } from "./lifecycle-target";
import { importPublished, pageBlocks, watchPage } from "./guards";

// Fixtures contrôlées importées sur le service réel : /Rotate 90/180/270 avec
// CropBox à origine non nulle, puis foliotation romaine/annexe. Recherche sans génération.
test.beforeEach(() => {
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Import de fixtures contrôlées sur stockage isolé autorisé uniquement ; NOT_RUN sinon.");
});

const manifestField = <T>(input: object, field: string) => (input as Record<string, unknown>)[field] as T;
const canvasBudget = (page: Page) => page.locator("canvas").evaluateAll(canvases => ({ count: canvases.length, pixels: canvases.reduce((sum, canvas) => sum + (canvas as HTMLCanvasElement).width * (canvas as HTMLCanvasElement).height, 0) }));

for (const key of ["crop-rotate-90", "crop-rotate-180", "crop-rotate-270"]) {
  test(`${key}: viewer rotations 0/90/180/270 keep the CropBox and the native anchor inside its source box`, async ({ page, request, browser }, info) => {
    test.setTimeout(720000);
    const log = watchPage(page);
    const input = fixture(key);
    const fileRotation = manifestField<number>(input, "rotation");
    const crop = manifestField<number[]>(input, "expected_crop_box");
    await monitorBrowser(browser, `${key}-start`, info);
    const imported = await importPublished(page, request, input, info);
    const blocks = await pageBlocks(request, imported.versionId, 0);
    expect(blocks.page.rotation).toBe(fileRotation);
    expect(blocks.page.crop_box).toEqual(crop);
    const anchor = `QG-${fileRotation}`;
    expect(blocks.blocks.some((block: { text: string; bbox: unknown }) => block.text.includes(anchor) && /6[.,]4/.test(block.text) && block.bbox), "Bloc d'ancre extrait avec géométrie").toBe(true);
    const correction = Number(blocks.page.orientation_correction ?? 0);

    await page.goto(`/workspace/?document=${encodeURIComponent(imported.documentId)}&version=${encodeURIComponent(imported.versionId)}&page=1`);
    const slot = page.locator('.pdf-page-slot[data-page-index="0"]');
    await expect(slot.locator("canvas")).toBeVisible();
    await page.getByRole("button", { name: "Analyser cette page", exact: true }).click();
    await expect(page.getByTestId("scope-summary")).toContainText("page 1");
    await page.getByRole("tab", { name: "Recherche", exact: true }).click();
    await page.getByLabel("Votre recherche").fill(`${anchor} pression`);
    const searched = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
    await page.getByRole("button", { name: "Rechercher", exact: true }).click();
    expect((await searched).status()).toBe(200);
    const card = page.getByTestId("source-card").filter({ hasText: `ancre ${anchor}` }).first();
    await expect(card).toBeVisible();
    await card.click();
    await expect(page.locator(".source-navigation")).not.toContainText("Localisation à la page");

    const measure = () => slot.evaluate((section, anchorId) => {
      const paper = section.querySelector(".pdf-paper")!.getBoundingClientRect();
      const span = [...section.querySelectorAll(".textLayer span")].find(item => (item.textContent ?? "").includes(anchorId) && /6[.,]4/.test(item.textContent ?? ""));
      const rect = span?.getBoundingClientRect();
      const center = rect ? { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 } : null;
      const highlights = [...section.querySelectorAll('[data-testid="source-highlight"]')].map(item => { const box = item.getBoundingClientRect(); return { x: box.x, y: box.y, width: box.width, height: box.height }; });
      return { paper: { width: paper.width, height: paper.height }, anchor: span?.textContent ?? null, center, highlights, containsAnchorCenter: Boolean(center && highlights.some(box => center.x >= box.x - 4 && center.x <= box.x + box.width + 4 && center.y >= box.y - 4 && center.y <= box.y + box.height + 4)) };
    }, anchor);
    const samples = [];
    for (const viewerRotation of [0, 90, 180, 270]) {
      if (viewerRotation) await page.getByRole("button", { name: "Pivoter de 90 degrés" }).click();
      await expect(page.getByRole("button", { name: "Pivoter de 90 degrés" })).toHaveAttribute("title", `Rotation ${viewerRotation}°`);
      const effective = (fileRotation + viewerRotation + correction) % 360;
      await expect(slot.locator(".textLayer")).toHaveAttribute("data-main-rotation", String(effective));
      await expect.poll(async () => (await measure()).containsAnchorCenter, { timeout: 30000 }).toBe(true);
      const geometry = await measure();
      // CropBox 541 x 540 pt : le rapport affiché suit la rotation effective, jamais la MediaBox.
      const width = crop[2] - crop[0]; const height = crop[3] - crop[1];
      const expectedRatio = effective % 180 ? height / width : width / height;
      expect(Math.abs(geometry.paper.width / geometry.paper.height - expectedRatio)).toBeLessThan(0.001);
      const budget = await canvasBudget(page);
      expect(budget.count).toBeLessThanOrEqual(5);
      expect(budget.pixels).toBeLessThanOrEqual(24_000_000);
      samples.push({ viewer_rotation: viewerRotation, file_rotation: fileRotation, orientation_correction: correction, effective_rotation: effective, expected_ratio: expectedRatio, ...geometry, budget });
      await page.screenshot({ path: info.outputPath(`${key}-viewer-${viewerRotation}.png`), fullPage: true });
    }
    await info.attach(`${key}-rotation-geometry`, { body: Buffer.from(JSON.stringify({ document_id: imported.documentId, version_id: imported.versionId, api_page: blocks.page, samples }, null, 2)), contentType: "application/json" });
    await monitorBrowser(browser, `${key}-end`, info);
    expect(log.requests.some(item => item.path.startsWith("/api/v1/queries"))).toBe(false);
    expect(log.external).toEqual([]);
    expect(log.pageErrors).toEqual([]);
  });
}

test("roman-labels: physical pages and logical folios stay distinct in captions and navigation", async ({ page, request, browser }, info) => {
  test.setTimeout(720000);
  const log = watchPage(page);
  const input = fixture("roman-labels");
  const labels = manifestField<string[]>(input, "expected_labels");
  await monitorBrowser(browser, "roman-labels-start", info);
  const imported = await importPublished(page, request, input, info);
  const apiPages = [];
  for (const [index, label] of labels.entries()) {
    const blocks = await pageBlocks(request, imported.versionId, index);
    expect(blocks.page.label).toBe(label);
    apiPages.push(blocks.page);
  }
  await page.goto(`/workspace/?document=${encodeURIComponent(imported.documentId)}&version=${encodeURIComponent(imported.versionId)}&page=1`);
  await expect(page.locator(".page-input span")).toHaveText(`/ ${labels.length}`);
  for (const [index, label] of labels.entries()) {
    await expect(page.locator(`.pdf-page-slot[data-page-index="${index}"] .page-caption`)).toContainText(`Page ${index + 1} · folio ${label}`);
  }
  const pageInput = page.getByLabel("Numéro de page");
  await pageInput.fill("3");
  await expect(pageInput).toHaveValue("3");
  await expect(page.locator('.pdf-page-slot[data-page-index="2"]')).toBeInViewport({ ratio: 0.3 });
  await expect(page.locator('.pdf-page-slot[data-page-index="2"] .page-caption')).toContainText("Page 3 · folio A-1");
  await page.getByRole("button", { name: "Page suivante" }).click();
  await expect(pageInput).toHaveValue("4");
  await expect(page.locator('.pdf-page-slot[data-page-index="3"]')).toBeInViewport({ ratio: 0.3 });
  await page.getByRole("button", { name: "Page précédente" }).click();
  await expect(pageInput).toHaveValue("3");
  await page.screenshot({ path: info.outputPath("roman-labels-page3-folio-A-1.png"), fullPage: true });
  await info.attach("roman-labels-api-pages", { body: Buffer.from(JSON.stringify({ document_id: imported.documentId, version_id: imported.versionId, expected_labels: labels, api_pages: apiPages }, null, 2)), contentType: "application/json" });
  await monitorBrowser(browser, "roman-labels-end", info);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
