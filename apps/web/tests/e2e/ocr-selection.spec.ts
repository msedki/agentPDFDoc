import { test, expect, type Locator } from "@playwright/test";
import { createHash } from "node:crypto";
import { ocrOverlays } from "../../src/lib/ocr-overlay.ts";
import { csrfFromCookies } from "../../src/lib/session.ts";
import type { DocumentDetail, Job, LibraryTree, PageBlocks, SelectedSpan, Source } from "../../src/lib/types.ts";
import { watchPage } from "./guards.ts";
import { withImportPriority } from "./import-priority.ts";
import { fixture, uploadFromUi, waitJob } from "./lifecycle-target.ts";
import { monitorBrowser } from "./resources";

const fixtureSha = "dbec1b85f93d253842b6ae34a156fbb32ce5f49d6dee96b82ae292245bf47387";
const terminalJobs = ["ready", "ready_partial", "cancelled", "error"];

/** Range is read-only here: coordinates of existing OCR text, never addRange or DOM/event injection. */
async function selectionGeometry(overlay: Locator, text: string) {
  return overlay.evaluate((element, selected) => {
    const node = element.firstChild;
    if (!(node instanceof Text)) throw new Error("OCR overlay must contain its real text node");
    const start = node.data.indexOf(selected);
    if (start < 0 || node.data.indexOf(selected, start + 1) !== -1) throw new Error("OCR selection is not unique in the overlay");
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, start + selected.length);
    const reader = element.closest(".pdf-scroll");
    if (!(reader instanceof HTMLElement)) throw new Error("Real reader is missing");
    const rect = range.getBoundingClientRect();
    const viewport = reader.getBoundingClientRect();
    reader.scrollBy({ left: rect.x + rect.width / 2 - viewport.x - viewport.width / 2, top: rect.y + rect.height / 2 - viewport.y - viewport.height / 2, behavior: "instant" });
    const boxes = Array.from(range.getClientRects()).filter(box => box.width > 0 && box.height > 0);
    if (!boxes.length) throw new Error("OCR text has no visible geometry");
    const visible = reader.getBoundingClientRect();
    const paper = element.closest(".pdf-paper")!.getBoundingClientRect();
    const overlayBox = element.getBoundingClientRect();
    const inside = (box: DOMRect, boundary: DOMRect) => box.left >= boundary.left && box.right <= boundary.right && box.top >= boundary.top && box.bottom <= boundary.bottom;
    const serialize = (box: DOMRect) => ({ x: box.x, y: box.y, width: box.width, height: box.height });
    const first = document.createRange(); first.setStart(node, start); first.setEnd(node, start + 1);
    const last = document.createRange(); last.setStart(node, start + selected.length - 1); last.setEnd(node, start + selected.length);
    const from = first.getBoundingClientRect(); const to = last.getBoundingClientRect();
    const fromPoint = { x: from.left + 0.1, y: from.top + from.height / 2 };
    const toPoint = { x: to.right - 0.1, y: to.top + to.height / 2 };
    const inOverlay = (point: { x: number; y: number }) => point.x >= overlayBox.left && point.x <= overlayBox.right && point.y >= overlayBox.top && point.y <= overlayBox.bottom;
    return { boxes: boxes.map(serialize), overlay: serialize(overlayBox), viewport: serialize(visible), contained: inOverlay(fromPoint) && inOverlay(toPoint) && boxes.every(box => inside(box, visible) && inside(box, paper) && box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight), from: fromPoint, to: toPoint };
  }, text);
}

test("real geometric OCR selection retains its exact revision, hash and Unicode offsets through scoped search", async ({ page, browser }, info) => {
  test.setTimeout(600000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Supervisor must admit this isolated store before an OCR fixture import or reuse.");
  const log = watchPage(page);
  const consoleErrors: string[] = [];
  const apiErrors: { path: string; status: number }[] = [];
  const evidence: unknown[] = [];
  const cleanupErrors: string[] = [];
  let ownedJob: string | undefined;
  let primaryError: unknown;
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("response", response => { const url = new URL(response.url()); if (url.pathname.startsWith("/api/v1/") && response.status() >= 400) apiErrors.push({ path: url.pathname, status: response.status() }); });
  async function cleanupOwnedImport() {
    if (!ownedJob) return;
    const jobsResponse = await page.request.get("/api/v1/jobs", { timeout: 10000 });
    expect(jobsResponse.status()).toBe(200);
    const job = ((await jobsResponse.json()).jobs as Job[]).find(job => job.id === ownedJob);
    if (!job) throw new Error("Owned import job disappeared during cleanup");
    if (terminalJobs.includes(String(job.state))) return;
    const csrf = csrfFromCookies(await page.evaluate(() => document.cookie));
    if (!csrf) throw new Error("CSRF cookie unavailable for owned-job cancellation");
    const cancelled = await page.request.post(`/api/v1/jobs/${encodeURIComponent(ownedJob)}/cancel`, { data: {}, headers: { "X-CSRF-Token": csrf, Origin: new URL(page.url()).origin }, timeout: 10000 });
    expect(cancelled.status()).toBe(200);
    await expect.poll(async () => {
      const response = await page.request.get("/api/v1/jobs", { timeout: 10000 });
      expect(response.status()).toBe(200);
      return ((await response.json()).jobs as Job[]).find(job => job.id === ownedJob)?.state;
    }, { timeout: 15000 }).toBe("cancelled");
  }
  try {
    const input = fixture("scan-fr-en");
    expect(input.sha256).toBe(fixtureSha);
    await monitorBrowser(browser, "ocr-start", info);
    await page.goto("/workspace/");
    await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
    const initialTreeResponse = await page.request.get("/api/v1/library/tree");
    expect(initialTreeResponse.status()).toBe(200);
    const initialTree = await initialTreeResponse.json() as LibraryTree;
    let documentId = process.env.RAG_E2E_REUSE_DOCUMENT_ID;
    let importedVersion: string | undefined;
    if (!documentId) {
      expect(initialTree.documents.filter(document => document.name === input.name), "Existing OCR fixture requires explicit reuse; never reimport automatically").toEqual([]);
      // D4 (recette R26-KIT-02) : import et publication sous « Priorité aux imports », choisie dans une page dédiée
      // du contexte puis rétablie à la priorité trouvée dans un finally (import-priority.ts). La page du scénario et
      // son journal ne voient pas ce choix ; un document réutilisé n'en a pas besoin.
      await withImportPriority(page, page.request, info, async () => {
        const received = await uploadFromUi(page, input, info);
        // Retain the exact created job for bounded cleanup even if later publication assertions fail.
        if (received.status === 202 && received.body.reused === false && typeof received.body.job_id === "string") ownedJob = received.body.job_id;
        expect(received.status).toBe(202);
        expect(received.body.reused).toBe(false);
        documentId = String(received.body.document_id);
        importedVersion = String(received.body.version_id);
        expect(ownedJob).toBeTruthy();
        const job = await waitJob(page.request, new URL(page.url()).origin, ownedJob!, info);
        expect(job.state).toBe("ready");
        expect(job.published).toBe(true);
        expect(job.document_id).toBe(documentId);
        expect(job.version_id).toBe(importedVersion);
      });
    }
    const detailResponse = await page.request.get(`/api/v1/documents/${encodeURIComponent(documentId!)}`);
    expect(detailResponse.status()).toBe(200);
    const detail = await detailResponse.json() as DocumentDetail;
    expect(detail.id).toBe(documentId);
    expect(detail.name).toBe(input.name);
    expect(detail.state).toBe("ready");
    expect(detail.page_count).toBe(1);
    expect(detail.active_generation_id).toBeTruthy();
    const versionId = detail.active_version_id ?? detail.version_id;
    expect(versionId).toBeTruthy();
    if (importedVersion) expect(versionId).toBe(importedVersion);
    expect(detail.versions.find(version => version.id === versionId)?.sha256).toBe(fixtureSha);
    const publishedJob = detail.jobs?.find(job => job.version_id === versionId && job.generation_id === detail.active_generation_id && job.state === "ready" && job.published);
    expect(publishedJob, "Exact real OCR publication job must be ready").toBeTruthy();
    const blocksResponse = await page.request.get(`/api/v1/versions/${encodeURIComponent(versionId!)}/pages/0/blocks`);
    expect(blocksResponse.status()).toBe(200);
    const binding = await blocksResponse.json() as PageBlocks;
    expect(binding.version_id).toBe(versionId);
    expect(binding.generation_id).toBe(detail.active_generation_id);
    expect(binding.extraction_revision_id).toBeTruthy();
    expect(binding.page.extraction_state).toBe("ocr");
    expect(binding.page.ocr_regions?.length).toBeGreaterThan(0);
    const overlays = ocrOverlays(binding.blocks);
    const candidates = overlays.flatMap(overlay => {
      const match = overlay.text.match(/(?:pression\s+de|maintain)\s+\d+[.,]\d+\s+bar/iu);
      return match && !match[0].includes("\n") ? [{ overlay, text: match[0] }] : [];
    });
    expect(candidates.length, "A useful real OCR pressure expression is required, not a lone symbol").toBeGreaterThan(0);
    const candidate = candidates[0]!;
    const block = binding.blocks.find(block => block.id === candidate.overlay.blockId)!;
    const raw = block.raw_text ?? block.text;
    const text = candidate.text;
    const start = raw.indexOf(text);
    expect(start).toBeGreaterThanOrEqual(0);
    expect(binding.blocks.map(block => block.raw_text ?? block.text).join(" ").split(text)).toHaveLength(2);
    expect(candidate.overlay.text).toBe(raw); // This image-only fixture must provide a full OCR block, not a guessed page box.
    let metadata: Record<string, unknown> = block.metadata ?? {};
    let extractionMethod = metadata.extraction_method;
    for (let depth = 0; depth < 3 && metadata.metadata && typeof metadata.metadata === "object" && !Array.isArray(metadata.metadata); depth++) {
      metadata = metadata.metadata as Record<string, unknown>;
      extractionMethod = metadata.extraction_method ?? extractionMethod;
    }
    expect(extractionMethod).toBe("ocr");
    expect(block.precision).not.toBe("page");
    expect(candidate.overlay.bbox.every(Number.isFinite)).toBe(true);
    expect(candidate.overlay.bbox[2]).toBeGreaterThan(candidate.overlay.bbox[0]);
    expect(candidate.overlay.bbox[3]).toBeGreaterThan(candidate.overlay.bbox[1]);
    expect(block.version_id).toBe(versionId);
    expect(block.extraction_revision_id).toBe(binding.extraction_revision_id);
    const sourceHash = createHash("sha256").update(raw, "utf8").digest("hex");
    expect(block.source_text_hash ?? block.source_text_sha256).toBe(sourceHash);
    const span: SelectedSpan = { blockId: block.id, extractionRevisionId: binding.extraction_revision_id!, blockTextSha256: sourceHash, offsetUnit: "unicode_code_point", startOffset: Array.from(raw.slice(0, start)).length, endOffset: Array.from(raw.slice(0, start + text.length)).length };
    const scope = { kind: "selection", versionId, spans: [span] };
    await info.attach("ocr-real-publication-binding", { body: Buffer.from(JSON.stringify({ document: detail, page: binding, selected: text, expected_scope: scope }, null, 2)), contentType: "application/json" });
    const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(input.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
    await expect(documentButton).toContainText("Prêt");
    const scopeBeforeOpen = await page.getByTestId("scope-summary").innerText();
    await documentButton.click();
    const slot = page.locator('.pdf-page-slot[data-page-index="0"]');
    await expect(slot.locator(".page-caption")).toContainText("Texte OCR");
    await expect(slot.locator(".textLayer span")).toHaveCount(0);
    await expect.poll(() => page.getByTestId("scope-summary").innerText()).toBe(scopeBeforeOpen);
    const overlay = slot.locator(".ocr-text-layer > span").filter({ hasText: raw }).first();
    await expect(overlay).toHaveAttribute("data-block-id", block.id);
    await expect(overlay).toHaveText(raw);
    await expect(overlay).toHaveAttribute("data-precision", candidate.overlay.precision);
    for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
      await page.setViewportSize(viewport);
      await expect(overlay).toBeVisible();
      // ResizeObserver can replace the overlay: wait for two identical geometric samples without altering it.
      let previous = "";
      await expect.poll(async () => {
        const geometry = await selectionGeometry(overlay, text);
        const signature = JSON.stringify(geometry);
        const stable = signature === previous && geometry.contained;
        previous = signature;
        return stable;
      }, { timeout: 15000 }).toBe(true);
      const geometry = await selectionGeometry(overlay, text);
      expect(geometry.contained).toBe(true);
      await page.mouse.move(geometry.from.x, geometry.from.y);
      await page.mouse.down();
      await page.mouse.move(geometry.to.x, geometry.to.y, { steps: 20 });
      await page.mouse.up();
      await expect.poll(() => page.evaluate(() => window.getSelection()?.toString() ?? "")).toBe(text);
      const selectionVisible = await page.evaluate(() => {
        const selection = window.getSelection();
        const reader = document.querySelector(".pdf-scroll")!.getBoundingClientRect();
        if (!selection?.rangeCount) return false;
        const boxes = Array.from(selection.getRangeAt(0).getClientRects()).filter(box => box.width > 0 && box.height > 0);
        return boxes.length > 0 && boxes.every(box => box.left >= reader.left && box.right <= reader.right && box.top >= reader.top && box.bottom <= reader.bottom && box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight);
      });
      expect(selectionVisible).toBe(true);
      await expect(page.locator(".selection-action")).toContainText(text);
      await page.screenshot({ path: info.outputPath(`ocr-selection-${viewport.width}.png`), fullPage: true });
      await page.locator(".selection-action").getByRole("button", { name: "Analyser la sélection", exact: true }).click();
      await expect(page.getByTestId("scope-summary")).toContainText("Texte sélectionné dans le document");
      await page.getByRole("tab", { name: "Recherche", exact: true }).click();
      await page.getByLabel("Votre recherche").fill("pression");
      const request = page.waitForRequest(request => request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/search");
      const response = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/search");
      await page.getByRole("button", { name: "Rechercher", exact: true }).click();
      const actualRequest = (await request).postDataJSON();
      expect(actualRequest.scope).toEqual(scope);
      const actualResponse = await response;
      expect(actualResponse.status()).toBe(200);
      const result = await actualResponse.json() as { results: Source[]; scope_snapshot: { scope: unknown; generations: string[]; versions: Record<string, string>; documents: Record<string, string>; spans: SelectedSpan[] } };
      expect(result.scope_snapshot).toMatchObject({ scope, generations: [binding.generation_id], versions: { [binding.generation_id!]: versionId }, documents: { [binding.generation_id!]: documentId }, spans: [span] });
      expect(result.results).toHaveLength(1);
      expect(result.results[0]).toMatchObject({ document_id: documentId, version_id: versionId, generation_id: binding.generation_id, extraction_revision_id: binding.extraction_revision_id, text, page_index: 0 });
      expect(result.results[0]!.blocks).toHaveLength(1);
      expect(result.results[0]!.blocks![0]).toMatchObject({ id: block.id, text, extraction_revision_id: binding.extraction_revision_id, source_text_hash: sourceHash, start_offset: span.startOffset, end_offset: span.endOffset });
      expect(Array.from(raw).slice(span.startOffset, span.endOffset).join("")).toBe(text);
      await expect(page.getByTestId("source-card").first()).toContainText(text);
      evidence.push({ viewport, selected_text: text, geometry, selection_visible: selectionVisible, request: actualRequest, response: result });
      await monitorBrowser(browser, `ocr-selection-${viewport.width}`, info);
    }
  } catch (error) { primaryError = error; }
  finally {
    try { await cleanupOwnedImport(); }
    catch (error) { cleanupErrors.push(error instanceof Error ? error.name : "Cleanup failure"); }
    await info.attach("ocr-selection-method-and-results", { body: Buffer.from(JSON.stringify({ method: "Real mouse drag; DOM Range only reads text coordinates. Real OCR import/publication and search, no injected DOM/content/events/responses, no LLM. Two viewport sizes share one publication; no rotation or OCR quality qualification.", evidence, network: log, consoleErrors, apiErrors, cleanupErrors }, null, 2)), contentType: "application/json" });
  }
  if (primaryError) throw primaryError;
  expect(cleanupErrors).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(apiErrors).toEqual([]);
  expect(log.requests.filter(request => request.method === "POST" && request.path === "/api/v1/queries")).toEqual([]);
  expect(log.requests.filter(request => request.method === "POST" && request.path === "/api/v1/documents/import")).toHaveLength(process.env.RAG_E2E_REUSE_DOCUMENT_ID ? 0 : 1);
});
