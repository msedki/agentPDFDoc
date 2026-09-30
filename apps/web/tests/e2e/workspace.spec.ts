import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { monitorBrowser } from "./resources";

let importedName = "";
const nativeDevName = "Atelier 1 - Banc pneumatique DA-P01.pdf";
const nativeDevPath = fileURLToPath(new URL("../../../../fixtures/qualification-v2.1/development/Procédures/Atelier 1 - Banc pneumatique DA-P01.pdf", import.meta.url));

test.afterEach(async ({ page }) => {
  const cancel = page.getByRole("button", { name: "Annuler", exact: true });
  if (await cancel.isVisible()) {
    await cancel.click();
    await expect(cancel).toBeHidden({ timeout: 15000 });
  }
});

test("three panels use a real API and no external requests at both desktop sizes", async ({ page, browser }, info) => {
  const external: string[] = [];
  const requests: { method: string; hostname: string; path: string; status: number }[] = [];
  const messages: { type: string; text: string }[] = [];
  page.on("console", message => messages.push({ type: message.type(), text: message.text() }));
  page.on("pageerror", error => messages.push({ type: "pageerror", text: error.message }));
  page.on("response", response => { const url = new URL(response.url()); requests.push({ method: response.request().method(), hostname: url.hostname, path: url.pathname, status: response.status() }); });
  page.on("request", request => { const url = new URL(request.url()); if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) && !["blob:", "data:"].includes(url.protocol)) external.push(request.url()); });
  await monitorBrowser(browser, "start", info);
  await page.goto("/workspace/");
  const tree = await page.request.get("/api/v1/library/tree");
  expect(tree.status()).toBe(200);
  expect(await tree.json()).toHaveProperty("documents");
  await expect(page.getByRole("heading", { name: "Bibliothèque", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analyse", exact: true })).toBeVisible();
  await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await page.screenshot({ path: test.info().outputPath(`workspace-${viewport.width}x${viewport.height}.png`), fullPage: true });
    await monitorBrowser(browser, `viewport-${viewport.width}`, info);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  }
  expect(external).toEqual([]);
  expect(requests.every(request => request.method === "GET")).toBeTruthy();
  await info.attach("console", { body: Buffer.from(JSON.stringify(messages, null, 2)), contentType: "application/json" });
  await info.attach("network", { body: Buffer.from(JSON.stringify(requests, null, 2)), contentType: "application/json" });
  expect(messages.filter(message => message.type === "pageerror")).toEqual([]);
});

test("real import, reading, scoped search and source navigation", async ({ page, browser }, info) => {
  test.setTimeout(600000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Supervisor must confirm the API targets an authorized isolated store before fixture import.");
  const name = nativeDevName;
  importedName = name;
  const external: string[] = []; const consoleErrors: string[] = [];
  page.on("pageerror", error => consoleErrors.push(error.message));
  page.on("request", request => { const url = new URL(request.url()); if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) && !["blob:", "data:"].includes(url.protocol)) external.push(request.url()); });
  await page.goto("/workspace/");
  if (process.env.RAG_E2E_REUSE_DOCUMENT_ID) {
    const previous = await page.request.get(`/api/v1/documents/${process.env.RAG_E2E_REUSE_DOCUMENT_ID}`);
    expect(previous.status()).toBe(200);
    const detail = await previous.json();
    expect(detail.name).toBe(name);
    const actualSha = createHash("sha256").update(readFileSync(nativeDevPath)).digest("hex");
    expect(detail.versions.some((version: { sha256: string }) => version.sha256 === actualSha)).toBeTruthy();
    await info.attach("reused-controlled-document", { body: Buffer.from(JSON.stringify(detail, null, 2)), contentType: "application/json" });
  } else {
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Importer des PDF", exact: true }).click();
    await (await chooser).setFiles(nativeDevPath);
  }
  const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
  await expect(documentButton).toBeVisible();
  await documentButton.click();
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("Numéro de page").fill("2");
  await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
  await page.getByRole("button", { name: "Pivoter de 90 degrés" }).click();
  await page.getByRole("button", { name: "Augmenter le zoom" }).click();
  await expect.poll(() => page.locator("canvas").count()).toBeLessThanOrEqual(5);
  await expect.poll(() => page.locator("canvas").evaluateAll(canvases => canvases.reduce((sum, canvas) => sum + (canvas as HTMLCanvasElement).width * (canvas as HTMLCanvasElement).height, 0))).toBeLessThanOrEqual(24_000_000);
  await page.getByLabel(`Sélectionner ${name}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
  await expect(page.getByTestId("scope-summary")).toContainText(name);
  await page.getByRole("button", { name: "Suivi", exact: false }).click();
  await page.getByRole("button", { name: "Priorité aux imports", exact: true }).click();
  const jobsResponse = await page.request.get("/api/v1/jobs");
  const paused = (await jobsResponse.json()).jobs.find((job: { document_id: string; state: string }) => job.document_id === process.env.RAG_E2E_REUSE_DOCUMENT_ID && job.state === "paused");
  if (paused) {
    const resumeRequest = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/jobs/${paused.id}/resume`));
    await page.getByRole("button", { name: "Reprendre l'indexation", exact: true }).click();
    expect((await resumeRequest).status()).toBe(200);
  }
  await page.getByRole("button", { name: "Fermer le suivi" }).click();
  await expect(documentButton).toContainText("Prêt", { timeout: 540000 });
  await monitorBrowser(browser, "indexed", info);
  const tree = await page.request.get("/api/v1/library/tree");
  const actualDocument = (await tree.json()).documents.find((document: { name: string }) => document.name === name);
  expect(actualDocument.active_generation_id).toBeTruthy();
  const versionId = actualDocument.active_version_id ?? actualDocument.version_id;
  const pageBindings = [];
  for (let pageIndex = 0; pageIndex < 2; pageIndex++) {
    const response = await page.request.get(`/api/v1/versions/${versionId}/pages/${pageIndex}/blocks`);
    expect(response.status()).toBe(200);
    pageBindings.push(await response.json());
  }
  await info.attach("development-DA-P01-runtime-binding", { body: Buffer.from(JSON.stringify({ document: actualDocument, pages: pageBindings }, null, 2)), contentType: "application/json" });
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche").fill("DA-P01 pression nominale");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const pressureSource = page.getByTestId("source-card").filter({ hasText: /3[.,]1/ }).first();
  await expect(pressureSource).toBeVisible();
  await expect(pressureSource).toContainText(name);
  await expect(pressureSource.locator(".source-id")).toHaveText("Passage");
  await pressureSource.getByRole("button", { name: "Ouvrir le passage", exact: true }).click();
  await expect(page.getByTestId("scope-summary")).toContainText(name);
  await expect(page.getByTestId("source-highlight").first()).toBeVisible();
  await expect(page.locator('.pdf-page-slot[data-page-index="0"] .textLayer span').filter({ hasText: /pression nominale.*3[.,]1/ }).first()).toBeAttached();
  const geometry = await page.locator('.pdf-page-slot[data-page-index="0"]').evaluate(section => {
    const text = [...section.querySelectorAll(".textLayer span")].find(span => /pression nominale.*3[.,]1/.test(span.textContent ?? ""));
    if (!text) return null;
    const rect = text.getBoundingClientRect();
    const center = { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    const highlights = [...section.querySelectorAll('[data-testid="source-highlight"]')].map(highlight => { const box = highlight.getBoundingClientRect(); return { x: box.x, y: box.y, width: box.width, height: box.height }; });
    return { text: text.textContent, textColor: getComputedStyle(text).color, textBox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }, center, highlights, containsNativeCenter: highlights.some(box => center.x >= box.x - 4 && center.x <= box.x + box.width + 4 && center.y >= box.y - 4 && center.y <= box.y + box.height + 4) };
  });
  await info.attach("native-pressure-anchor-rotation90", { body: Buffer.from(JSON.stringify(geometry, null, 2)), contentType: "application/json" });
  expect(geometry?.textColor).toBe("rgba(0, 0, 0, 0)");
  expect(geometry?.containsNativeCenter).toBe(true);
  await page.screenshot({ path: info.outputPath("native-pressure-source-rotation90.png"), fullPage: true });
  await page.getByRole("button", { name: "Revenir au passage précédent" }).click();
  await expect(page.getByLabel("Numéro de page")).toHaveValue("2");
  await page.screenshot({ path: test.info().outputPath("import-search-source.png"), fullPage: true });
  await page.getByLabel("Votre recherche").fill("DA-P99 référence absente");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const missingWarnings = page.locator(".search-results .inline-warning").filter({ hasText: "Référence non retrouvée dans les passages de ce périmètre." });
  await expect.poll(() => missingWarnings.count()).toBeGreaterThan(0);
  for (const warning of await missingWarnings.all()) await expect(warning).toBeVisible();
  await page.screenshot({ path: info.outputPath("structured-retrieval-warning.png"), fullPage: true });
  expect(external).toEqual([]); expect(consoleErrors).toEqual([]);
});

test("real page and immutable block selection scopes reach the API", async ({ page }) => {
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Requires the authorized real indexed fixture from the import scenario.");
  importedName ||= nativeDevName;
  await page.goto("/workspace/");
  const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(importedName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
  await documentButton.click();
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("Numéro de page").fill("2");
  await page.getByRole("button", { name: "Analyser cette page", exact: true }).click();
  await expect(page.getByTestId("scope-summary")).toContainText("page 2");
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche").fill("DA-P01-OUT diamètre");
  const pageSearch = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const pageBody = (await pageSearch).postDataJSON();
  expect(pageBody.scope).toMatchObject({ kind: "pages", pageStart: 1, pageEnd: 1 });
  await expect(page.getByTestId("source-card").first()).toBeVisible();
  for (const source of await page.getByTestId("source-card").all()) await expect(source).toContainText("p. 2");
  await page.getByRole("button", { name: "Texte extrait & provenance", exact: false }).click();
  const sourceBlock = page.locator(".extracted-text > div").filter({ hasText: "DA-P01-OUT" }).first();
  await sourceBlock.getByRole("button", { name: "Analyser ce bloc", exact: true }).click();
  await expect(page.getByTestId("scope-summary")).toContainText("Bloc source");
  const blockSearch = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/api/v1/search"));
  const blockResponse = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const selectionBody = (await blockSearch).postDataJSON();
  expect(selectionBody.scope.kind).toBe("selection");
  expect(selectionBody.scope.spans).toHaveLength(1);
  expect(selectionBody.scope.spans[0]).toMatchObject({ offsetUnit: "unicode_code_point", startOffset: 0 });
  expect(selectionBody.scope.spans[0].extractionRevisionId).toBeTruthy();
  expect(selectionBody.scope.spans[0].blockTextSha256).toMatch(/^[a-f0-9]{64}$/i);
  const response = await blockResponse;
  expect(response.status()).toBe(200);
  await page.screenshot({ path: test.info().outputPath("page-and-block-scope.png"), fullPage: true });
});

test("real local model answers with registered citations and preserves scope", async ({ page, browser }, info) => {
  test.setTimeout(660000);
  test.skip(process.env.RAG_E2E_GENERATION_ALLOWED !== "1", "Supervisor must grant a separate real local model generation window.");
  page.on("console", message => { if (message.text().startsWith("QUALIFICATION ")) console.log(message.text()); });
  const diagnostics = async (phase: string) => {
    const response = await page.request.get("/api/v1/diagnostics");
    expect(response.status()).toBe(200);
    const value = await response.json();
    await info.attach(`cache-diagnostics-${phase}`, { body: Buffer.from(JSON.stringify({ phase, profile_sha256: value.profile_sha256, active_queries: value.active_queries, embedding_session: value.embedding_session, llm_tokenizer_cache: value.llm_tokenizer_cache, method: "Real read-only lifecycle telemetry; loads/releases/reloads do not count inference calls." }, null, 2)), contentType: "application/json" });
  };
  const tree = await page.request.get("/api/v1/library/tree");
  expect(tree.status()).toBe(200);
  const documents = (await tree.json()).documents as { name: string; state: string }[];
  const name = importedName || documents.find(document => document.name === nativeDevName && document.state === "ready")?.name;
  expect(name, "A real indexed controlled UI document is required").toBeTruthy();
  await page.goto("/workspace/");
  await page.getByLabel(`Sélectionner ${name}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
  await page.getByRole("button", { name: "Suivi", exact: false }).click();
  await page.getByRole("button", { name: "Priorité aux questions", exact: true }).click();
  await page.getByRole("button", { name: "Fermer le suivi" }).click();
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question").fill("Quelle est la pression nominale de DA-P01 ? Citez sa source.");
  await monitorBrowser(browser, "before-question", info);
  await diagnostics("before-question");
  await page.evaluate(() => {
    const timings = { started_at_ms: Date.now(), first_answer_text_at_ms: null as number | null };
    (window as unknown as { __qualificationTimings: typeof timings }).__qualificationTimings = timings;
    const observer = new MutationObserver(() => {
      if (!timings.first_answer_text_at_ms && document.querySelector(".answer-text")?.textContent?.trim()) { timings.first_answer_text_at_ms = Date.now(); console.log(`QUALIFICATION ${JSON.stringify({ phase: "first-displayed-answer-text", timestamp_utc: new Date().toISOString() })}`); }
      const status = document.querySelector(".query-status")?.textContent?.trim();
      if (status && status !== lastStatus) { lastStatus = status; console.log(`QUALIFICATION ${JSON.stringify({ phase: "ui-query-status", status, timestamp_utc: new Date().toISOString() })}`); }
    });
    let lastStatus = "";
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  const queryResponse = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/queries"));
  let queryId: string | null = null;
  try {
    await page.getByRole("button", { name: "Envoyer", exact: true }).click();
    const response = await queryResponse;
    const created = await response.json();
    await info.attach("query-created", { body: Buffer.from(JSON.stringify({ status: response.status(), request: response.request().postDataJSON(), response: created }, null, 2)), contentType: "application/json" });
    expect(response.status()).toBe(202);
    queryId = created.query_id;
    console.log(`QUALIFICATION ${JSON.stringify({ phase: "query-created", query_id: queryId, timestamp_utc: new Date().toISOString() })}`);
    await expect(page.locator(".query-status").last()).toContainText(/Réponse terminée|Réponse limitée|Échec|Réponse annulée|Réponse interrompue|Précision nécessaire|Preuves insuffisantes/, { timeout: 600000 });
    await monitorBrowser(browser, "question-terminal", info);
    await diagnostics("question-terminal");
    const terminal = await page.locator(".query-status").last().innerText();
    expect(terminal, "The actual query must complete before an answer/citation assertion; terminal errors are preserved in the SSE attachment").toMatch(/Réponse terminée|Réponse limitée/);
    await expect(page.locator(".answer-text").last()).toContainText(/3[.,]1/);
    await expect(page.locator(".answer-text").last()).toContainText(/\bbar\b/i);
    await expect(page.locator(".inline-citation").first()).toBeVisible();
    const citationResponse = page.waitForResponse(response => response.url().includes(`/api/v1/citations/${queryId}/`));
    await page.locator(".inline-citation").first().click();
    const citation = await citationResponse;
    expect(citation.status()).toBe(200);
    const source = await citation.json();
    await info.attach("clicked-registered-citation", { body: Buffer.from(JSON.stringify(source, null, 2)), contentType: "application/json" });
    expect(source.page_index).toBe(0);
    expect(source.text).toMatch(/3[.,]1/);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
    await expect(page.getByTestId("source-highlight").first()).toBeVisible();
    await expect(page.getByTestId("scope-summary")).toContainText(name!);
    expect(await page.locator("canvas").count()).toBeLessThanOrEqual(5);
    expect(await page.locator("canvas").evaluateAll(canvases => canvases.reduce((sum, canvas) => sum + (canvas as HTMLCanvasElement).width * (canvas as HTMLCanvasElement).height, 0))).toBeLessThanOrEqual(24_000_000);
    await page.screenshot({ path: info.outputPath("import-question-citation.png"), fullPage: true });
  } finally {
    if (queryId) {
      const events = await page.request.get(`/api/v1/queries/${encodeURIComponent(queryId)}/events?after=0`, { timeout: 10000 }).catch(() => null);
      if (events) await info.attach("actual-sse-replay", { body: await events.body(), contentType: "text/event-stream; charset=utf-8" });
    }
    const timings = await page.evaluate(() => (window as unknown as { __qualificationTimings: unknown }).__qualificationTimings).catch(() => null);
    await info.attach("ui-observed-latency", { body: Buffer.from(JSON.stringify({ timings, completed_at_ms: Date.now(), method: "DOM observation of first displayed answer text; server TTFT remains separate in actual SSE metrics." }, null, 2)), contentType: "application/json" });
  }
});
