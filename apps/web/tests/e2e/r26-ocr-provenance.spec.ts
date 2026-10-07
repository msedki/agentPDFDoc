/**
 * R26-UI-01 : méthode d'extraction des sources et avis du service.
 *
 * 1. API réelle, sans modèle : recherche dans la fixture numérisée « Contrôle bilingue FR EN.pdf » (scan-fr-en),
 *    badge de méthode d'extraction sur la carte, avertissement `ocr_evidence` affiché une seule fois, puis
 *    « Ouvrir le passage » et badge dans le bandeau du lecteur. Réutilise le document importé par
 *    ocr-selection.spec.ts s'il existe, sinon l'importe par l'interface avec importPublished (guards.ts), qui choisit
 *    « Priorité aux imports » puis rétablit la priorité trouvée (import-priority.ts, défaut D4 de la recette R26-KIT-02).
 * 2. DOUBLE « SSE injecté » : POST /queries et son flux sont remplacés dans le navigateur par les événements écrits
 *    ici (ocr_evidence émis puis répété dans done, contrôles de valeurs, sources ocr/native/inconnue). Il vérifie
 *    l'affichage seul ; il ne qualifie ni la génération ni les contrôles du service.
 * Captures à 1366×768 et 1920×1080, sans défilement horizontal de la page.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { importPublished, readOnlyApi, watchPage } from "./guards";
import { fixture } from "./lifecycle-target";

const viewports = [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }];
type SearchResult = { source?: { extraction_methods?: string[] }; extraction_methods?: string[]; blocks?: { extraction_method?: string }[] };
type Warning = { code?: string; document_id?: string; message?: string; source_ids?: string[] };

async function captures(page: Page, info: TestInfo, name: string, focus: ReturnType<Page["locator"]>) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await focus.scrollIntoViewIfNeeded();
    await expect(focus).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${name} : aucun défilement horizontal à ${viewport.width}×${viewport.height}`).toBe(true);
    await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}x${viewport.height}.png`) });
  }
  await page.setViewportSize(viewports[0]);
}

test("recherche réelle dans un scan : badge OCR, avertissement ocr_evidence unique et bandeau du lecteur", async ({ page, request }, info) => {
  test.setTimeout(600000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Import de fixtures contrôlées sur stockage isolé autorisé uniquement ; NOT_RUN sinon.");
  const input = fixture("scan-fr-en");
  const log = watchPage(page);
  const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.setViewportSize(viewports[0]);
  const tree = await (await request.get("/api/v1/library/tree")).json() as { documents: { id: string; name: string; state: string }[] };
  let documentId = tree.documents.find(document => document.name === input.name && document.state === "ready")?.id;
  if (!documentId) documentId = (await importPublished(page, request, input, info)).documentId;
  await page.goto("/workspace/");
  await page.getByLabel(`Sélectionner ${input.name}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche").fill("pression bar");
  const searched = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const response = await searched;
  expect(response.status()).toBe(200);
  const body = await response.json() as { results: SearchResult[]; warnings: Warning[] };
  await info.attach("r26-search-response", { body: Buffer.from(JSON.stringify(body, null, 2)), contentType: "application/json" });
  expect(body.results.length).toBeGreaterThan(0);
  const methods = (body.results[0].source ?? body.results[0]).extraction_methods ?? [];
  expect(methods.some(method => method === "ocr" || method === "mixed"), `méthodes du premier résultat : ${methods.join(",")}`).toBe(true);
  const expectedLabel = methods.length === 1 && methods[0] === "ocr" ? "Lu par OCR" : "En partie lu par OCR";
  const ocrWarnings = body.warnings.filter(warning => warning.code === "ocr_evidence" && warning.document_id === documentId);
  expect(ocrWarnings).toHaveLength(1);
  expect(ocrWarnings[0].source_ids).toEqual([]);

  const results = page.locator(".search-results");
  const firstCard = results.getByTestId("source-card").first();
  const badge = firstCard.getByTestId("extraction-badge");
  await expect(badge).toHaveText(expectedLabel);
  await expect(badge).toHaveAttribute("title", /même sans alerte de faible confiance, signes, unités et références peuvent être mal lus/);
  const notice = results.locator(".inline-warning").filter({ hasText: ocrWarnings[0].message! });
  await expect(notice).toHaveCount(1);
  await captures(page, info, "r26-recherche-scan", firstCard);

  await firstCard.getByRole("button", { name: "Ouvrir le passage" }).click();
  const banner = page.locator(".source-navigation");
  await expect(banner.getByTestId("extraction-badge")).toHaveText(expectedLabel);
  await expect(page.getByTestId("source-highlight").first()).toBeVisible();
  await captures(page, info, "r26-lecteur-scan", banner);
  await info.attach("r26-real-ocr-ui", { body: Buffer.from(JSON.stringify({ documentId, methods, expectedLabel, ocrWarning: ocrWarnings[0],
    network: log, consoleErrors }, null, 2)), contentType: "application/json" });
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("DOUBLE SSE injecté : avis d'une réponse dédoublonnés, valeurs et sources ouvrables, badges par source", async ({ page }, info) => {
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await readOnlyApi(page, blocked);
  const queryId = "r26-double-sse";
  const eventsUrl = `/api/v1/queries/${queryId}/events`;
  await page.route("**/api/v1/queries", route => route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ query_id: queryId, events_url: eventsUrl }) }));
  const source = (id: string, name: string, extra: Record<string, unknown>) => ({ source_id: id, query_id: queryId, document_id: `doc-${id}`, version_id: `version-${id}`,
    name, page_index: 0, page_number: 1, text: `Passage ${id} de ${name}.`, precision: "page", ...extra });
  const sources = [
    source("S001", "Contrôle bilingue FR EN.pdf", { extraction_methods: ["ocr"] }),
    source("S002", "Atelier 2 - Banc pneumatique DA-P02.pdf", { extraction_methods: ["native", "ocr"] }),
    source("S003", "Procédure QV-01.pdf", {}),
  ];
  const ocrEvidence = { code: "ocr_evidence", document_id: "doc-S001", document_name: "Contrôle bilingue FR EN.pdf", extraction_methods: ["ocr"], source_ids: ["S001"],
    message: "Passages de « Contrôle bilingue FR EN.pdf » lus par OCR (S001) : vérifiez signes, unités et références sur la page originale." };
  const misattributed = { code: "cited_value_not_in_cited_sources", message: "Valeur absente des sources citées dans sa phrase mais présente dans d'autres sources retenues : 2,7 bar (citée S001, présente dans S002). Vérifiez sa source avant de l'utiliser.",
    values: [{ value: "2,7 bar", number: "2,7", unit: "bar", cited_source_ids: ["S001"], holder_source_ids: ["S002"] }] };
  const absent = { code: "value_not_in_context", message: "Valeur absente de toutes les sources transmises au modèle : 14 N·m. Elle peut avoir été calculée, déduite ou mal reprise ; vérifiez-la avant de l'utiliser.",
    values: [{ value: "14 N·m", number: "14", unit: "N·m", cited_source_ids: ["S009"] }] };
  const text = "La pression de réglage est de 2,7 bar [S001]. Le couple de serrage est de 14 N·m [S003].";
  const repeated = { message: ocrEvidence.message, source_ids: ["S001"], extraction_methods: ["ocr"], document_name: ocrEvidence.document_name, document_id: "doc-S001", code: "ocr_evidence" };
  const events = [
    { type: "status", data: { state: "generating" } },
    { type: "sources", data: { sources } },
    { type: "warning", data: { warning: ocrEvidence } },
    { type: "delta", data: { text } },
    { type: "done", data: { text, status: "done", finish_reason: "stop", citations: sources, warnings: [repeated, misattributed, absent] } },
  ];
  const sse = events.map((event, position) => `id: ${position + 1}\nevent: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`).join("");
  await page.route(`**${eventsUrl}*`, route => route.fulfill({ status: 200, contentType: "text/event-stream", body: sse }));
  await page.setViewportSize(viewports[0]);
  await page.goto("/workspace/");
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question").fill("Quelles sont la pression de réglage et le couple de serrage ?");
  await page.getByRole("button", { name: "Envoyer", exact: true }).click();
  const turn = page.getByTestId("query-turn");
  await expect(turn.locator(".query-status")).toContainText("Réponse terminée");
  await expect(turn.locator(".inline-warning").filter({ hasText: ocrEvidence.message })).toHaveCount(1);
  const valueNotice = turn.locator(".inline-warning").filter({ hasText: misattributed.message });
  await expect(valueNotice).toHaveCount(1);
  await expect(valueNotice.getByRole("button", { name: "S001" })).toBeVisible();
  await expect(valueNotice.getByRole("button", { name: "S002" })).toBeVisible();
  const absentNotice = turn.locator(".inline-warning").filter({ hasText: absent.message });
  await expect(absentNotice.locator(".mono", { hasText: "S009" })).toBeVisible();
  await expect(absentNotice.getByRole("button")).toHaveCount(0);
  await expect(turn.locator(".warning-values")).toHaveCount(0);
  const cards = turn.getByTestId("source-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).getByTestId("extraction-badge")).toHaveText("Lu par OCR");
  await expect(cards.nth(1).getByTestId("extraction-badge")).toHaveText("En partie lu par OCR");
  await expect(cards.nth(2).getByTestId("extraction-badge")).toHaveText("Méthode d'extraction inconnue");
  await expect(turn.locator(".inline-citation", { hasText: "S001" }).first()).toHaveAttribute("title", /· Lu par OCR$/);
  await captures(page, info, "r26-double-avis", valueNotice);
  await captures(page, info, "r26-double-sources", cards.nth(0));
  await info.attach("r26-double-sse", { body: Buffer.from(JSON.stringify({ double: "SSE injecté", events,
    substitutions: ["POST /api/v1/queries", `GET ${eventsUrl}`],
    scope: "Affichage de l'export courant uniquement ; aucune génération, query réelle ni contrôle du service qualifié.",
    blocked, mutations: log.mutations, external: log.external, pageErrors: log.pageErrors, consoleErrors }, null, 2)), contentType: "application/json" });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual(["POST /api/v1/queries"]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
