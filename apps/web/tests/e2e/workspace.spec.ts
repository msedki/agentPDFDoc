import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { monitorBrowser } from "./resources";
import { doneEvent, registeredAnswerCitation, type DoneEvent } from "./answer-citations";
import { readOnlyApi, watchPage } from "./guards";
import { withImportPriority } from "./import-priority.ts";

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
  const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
  // D4 (recette R26-KIT-02) : de l'import (ou de la reprise d'un document réutilisé) jusqu'à « Prêt », le poste est en
  // « Priorité aux imports », choisie dans une page dédiée du contexte puis rétablie à la priorité trouvée dans un
  // finally (import-priority.ts). La lecture, la rotation et le périmètre se font donc pendant l'indexation.
  await withImportPriority(page, page.request, info, async () => {
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
    // Suivi : l'indexation d'un document réutilisé restée en pause y est reprise, comme le ferait l'utilisateur.
    await page.getByRole("button", { name: "Suivi", exact: false }).click();
    const jobsResponse = await page.request.get("/api/v1/jobs");
    const paused = (await jobsResponse.json()).jobs.find((job: { document_id: string; state: string }) => job.document_id === process.env.RAG_E2E_REUSE_DOCUMENT_ID && job.state === "paused");
    if (paused) {
      const resumeRequest = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/jobs/${paused.id}/resume`));
      await page.getByRole("button", { name: "Reprendre l'indexation", exact: true }).click();
      expect((await resumeRequest).status()).toBe(200);
    }
    await page.getByRole("button", { name: "Fermer le suivi" }).click();
    await expect(documentButton).toContainText("Prêt", { timeout: 540000 });
  });
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
  // D3 (recette R26-KIT-02) : un changement de géométrie (rotation, zoom, largeur) ne change pas la page lue.
  // La page 2 reste celle de la ligne de lecture du lecteur (haut + 100 px) aux deux tailles de bureau, puis au retour.
  for (const [index, viewport] of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 1366, height: 768 }].entries()) {
    await page.setViewportSize(viewport);
    await expect(page.getByLabel("Numéro de page")).toHaveValue("2");
    await expect.poll(() => page.getByTestId("pdf-scroll").evaluate(scroller => {
      const slot = scroller.querySelector('.pdf-page-slot[data-page-index="1"]')?.getBoundingClientRect();
      const view = scroller.getBoundingClientRect();
      return Boolean(slot && slot.top <= view.top + 100 && slot.bottom > view.top + 100);
    })).toBe(true);
    await page.screenshot({ path: info.outputPath(`return-page2-rotation90-${index + 1}-${viewport.width}x${viewport.height}.png`), fullPage: true });
  }
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
    const turn = page.getByTestId("query-turn").last();
    await expect(turn.locator(".answer-text")).toContainText(/3[.,]1/);
    await expect(turn.locator(".answer-text")).toContainText(/\bbar\b/i);
    // D2 (recette R26-KIT-02) : seule compte une citation enregistrée dans l'événement done et affichée dans le texte
    // de la réponse ; les boutons de source des avis portent la même classe et ont validé deux réponses sans citation.
    const replay = await page.request.get(`/api/v1/queries/${encodeURIComponent(queryId!)}/events?after=0`, { timeout: 10000 });
    expect(replay.status()).toBe(200);
    const cited = await registeredAnswerCitation(turn, doneEvent(await replay.text()));
    await info.attach("registered-answer-citations", { body: Buffer.from(JSON.stringify({ registered: cited.registered, shown: cited.shown }, null, 2)), contentType: "application/json" });
    const citationResponse = page.waitForResponse(response => response.url().includes(`/api/v1/citations/${encodeURIComponent(queryId!)}/${encodeURIComponent(cited.sourceId)}`));
    await cited.button.click();
    const citation = await citationResponse;
    expect(citation.status()).toBe(200);
    const source = await citation.json();
    await info.attach("clicked-registered-citation", { body: Buffer.from(JSON.stringify(source, null, 2)), contentType: "application/json" });
    expect(source.source_id).toBe(cited.sourceId);
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

test("DOUBLE SSE injecté : réponse sans citation enregistrée (2B de la recette R26-KIT-02) refusée par l'oracle", async ({ page }, info) => {
  // Double nommé de l'oracle D2, sans génération : POST /queries et son flux sont remplacés dans le navigateur par la
  // réponse 2B rejouée de la recette (requête ce0013ed, texte et avis repris, sources réduites). Ne qualifie ni le modèle
  // ni les contrôles du service ; vérifie que les boutons de source des avis ne sont jamais pris pour des citations.
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  const queryId = "r26-ui02-double-2b";
  const eventsUrl = `/api/v1/queries/${queryId}/events`;
  await page.route("**/api/v1/queries", route => route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ query_id: queryId, events_url: eventsUrl }) }));
  const ids = ["S001", "S002", "S003", "S004", "S005"];
  const sources = ids.map((source_id, index) => ({ source_id, query_id: queryId, document_id: "doc-da-p01", version_id: "version-da-p01", name: nativeDevName,
    page_index: index ? 1 : 0, page_number: index ? 2 : 1, precision: "block", extraction_methods: ["native"], text: index ? "Mesures de contrôle — DA-P01." : "La pression nominale de DA-P01 est de 3.1 bar." }));
  const text = "Selon les preuves fournies, la pression nominale de DA-P01 est de **3.1 bar**. Cette information est explicitement mentionnée dans le texte de la preuve S001 : « La pression nominale de DA-P01 est de 3.1 bar. »\n\nIl est important de noter que les autres preuves (S002, S003, S004, S005) ne contiennent pas d'information concernant la pression nominale ; elles concernent uniquement des mesures de contrôle (diamètres, fuite), une référence à un autre équipement ou le contenu général de la page.";
  const warnings = [
    { code: "answer_without_valid_citation", message: "La réponse ne contient aucune citation valide entre crochets : ses affirmations ne sont reliées à aucune source vérifiable. Contrôlez-les dans les sources listées avant de les utiliser." },
    { code: "source_id_mentioned_without_citation", source_ids: ids, message: "La réponse nomme S001, S002, S003, S004 et S005 sans crochets : ces mentions ne sont pas des citations et n'ouvrent pas les sources. Retrouvez ces sources dans la liste pour vérifier la réponse." },
  ];
  const done: DoneEvent = { status: "done", finish_reason: "stop", text, citations: [], warnings };
  const events = [
    { type: "status", data: { state: "generating" } },
    { type: "sources", data: { sources } },
    { type: "delta", data: { text } },
    { type: "done", data: done },
  ];
  const sse = events.map((event, position) => `id: ${position + 1}\nevent: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`).join("");
  await page.route(`**${eventsUrl}*`, route => route.fulfill({ status: 200, contentType: "text/event-stream", body: sse }));
  await page.goto("/workspace/");
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question").fill("Quelle est la pression nominale de DA-P01 ? Citez sa source.");
  await page.getByRole("button", { name: "Envoyer", exact: true }).click();
  const turn = page.getByTestId("query-turn").last();
  await expect(turn.locator(".query-status")).toContainText("Réponse terminée");
  await expect(turn.locator(".answer-text")).toContainText("3.1 bar");
  // Le piège de l'ancien oracle : des boutons `.inline-citation` existent, mais dans les avis, hors du texte de la réponse.
  await expect(turn.locator(".inline-warning .inline-citation").first()).toBeVisible();
  await expect(turn.locator(".answer-text .inline-citation")).toHaveCount(0);
  const parsed = doneEvent(sse);
  await expect(registeredAnswerCitation(turn, parsed)).rejects.toThrow(/aucune citation/);
  await page.screenshot({ path: info.outputPath("double-2b-sans-citation.png"), fullPage: true });
  await info.attach("r26-ui02-double-2b", { body: Buffer.from(JSON.stringify({ double: "SSE injecté", substitutions: ["POST /api/v1/queries", `GET ${eventsUrl}`],
    warningButtons: await turn.locator(".inline-warning .inline-citation").allInnerTexts(), blocked, mutations: log.mutations, external: log.external, pageErrors: log.pageErrors }, null, 2)), contentType: "application/json" });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual(["POST /api/v1/queries"]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
