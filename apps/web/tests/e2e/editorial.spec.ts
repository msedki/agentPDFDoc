/**
 * R15-2 : les lectures réelles et les états injectés sont nommés séparément.
 * Les POST simulés sont interceptés ; aucun modèle, reprise ou publication n'est lancé par ces cas.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { fixtureAtPath, readOnlyApi, watchPage } from "./guards";
import { monitorBrowser } from "./resources";

async function captureDesktop(page: Page, info: TestInfo, name: string) {
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${name}-${viewport.width}x${viewport.height}.png`), fullPage: true });
  }
}

test("real GET-only UI: initial help and page/block actions select a scope without launching analysis", async ({ page, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const documentId = process.env.RAG_E2E_REUSE_DOCUMENT_ID;
  test.skip(!documentId, "Document contrôlé déjà publié requis ; aucun import implicite.");
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await page.goto("/");
  await expect(page.getByText("Ouvrez les sources citées pour vérifier la page et le texte utilisés.", { exact: false })).toBeVisible();
  await page.goto("/workspace/");
  await expect(page.getByText("Une source consultable s'ouvre ici à la page concernée", { exact: false })).toBeVisible();
  await expect(page.getByText("Si la réponse cite des sources, ouvrez-les", { exact: false })).toBeVisible();
  const response = await page.request.get(`/api/v1/documents/${encodeURIComponent(documentId!)}`);
  expect(response.status()).toBe(200);
  const document = await response.json();
  const input = fixtureAtPath("qualification-v2.1/development/Procédures/Atelier 1 - Banc pneumatique DA-P01.pdf");
  expect(input).toBeTruthy();
  expect(document.name).toBe("Atelier 1 - Banc pneumatique DA-P01.pdf");
  expect(document.active_generation_id).toBeTruthy();
  // Même choix que library-panel.tsx : une ancienne version de la fixture ne suffit pas.
  const selectedVersionId = document.active_version_id ?? document.version_id;
  expect(selectedVersionId).toBeTruthy();
  const selectedVersion = document.versions.find((version: { id: string; sha256: string }) => version.id === selectedVersionId);
  expect(selectedVersion, "La version active choisie doit être présente dans le détail du document").toBeTruthy();
  expect(selectedVersion.sha256).toBe(input!.sha256);
  await page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp("Atelier 1 - Banc pneumatique DA-P01\\.pdf") }).first().click();
  await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.getByText("« Analyser » définit le périmètre", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Analyser cette page", exact: true }).click();
  await expect(page.getByTestId("scope-summary")).toContainText("page 1");
  await page.getByRole("button", { name: "Texte extrait & provenance", exact: false }).click();
  await page.getByRole("button", { name: "Analyser ce bloc", exact: true }).first().click();
  await expect(page.getByTestId("scope-summary")).toContainText("Bloc source");
  await captureDesktop(page, info, "editorial-real-scopes");
  await monitorBrowser(browser, "editorial-real-scopes", info);
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});

for (const resumed of [0, 1, 3]) {
  test(`injected UI: full-page partial extraction and resume count ${resumed} stay factual`, async ({ page, browser }, info) => {
    test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
    const log = watchPage(page);
    const blocked: string[] = [];
    await readOnlyApi(page, blocked);
    await page.route("**/api/v1/jobs", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({
      runtime_mode: "ingestion", generation: null,
      jobs: [
        { id: "editorial-partial", document_id: "editorial-partial-document", state: "ready_partial", stage: "complete", published: false, coverage: { processed: 2, total: 2, ocr: 1 },
          warnings: [{ code: "PDF_RENDER_LIMIT", page_index: 0 }, { code: "OCR_ORIENTATION_UNRESOLVED", page_index: 1 }, { code: "ITEM_WITHOUT_PROVENANCE", page_index: 1 }, { code: "INVALID_SOURCE_CHARSPAN", page_index: 1 }] },
        ...[1, 2, 3].map(id => ({ id: `editorial-paused-${id}`, document_id: `editorial-paused-document-${id}`, state: "paused" })),
      ],
    }) }));
    await page.route("**/api/v1/jobs/resume-paused", route => {
      expect(route.request().method()).toBe("POST");
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ resumed }) });
    });
    await page.goto("/workspace/");
    await page.getByRole("button", { name: "Suivi", exact: false }).click();
    const panel = page.locator(".jobs-panel");
    await expect(panel.getByText("2/2 pages traitées", { exact: false })).toBeVisible();
    await expect(panel.getByText("Extraction partielle terminée, non publiée", { exact: false })).toBeVisible();
    await expect(panel.getByText("leur texte n'est pas disponible pour la recherche", { exact: false })).toBeVisible();
    await expect(panel.getByText("certains passages ont été écartés", { exact: false })).toBeVisible();
    await expect(panel.getByText("la lecture OCR n'a pas été lancée", { exact: false })).toBeVisible();
    await expect(panel.getByRole("button", { name: "Utiliser cette extraction partielle", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Reprendre les 3 indexations en pause", exact: true }).click();
    const notice = resumed === 0 ? "Aucune reprise d'indexation mise en file. Vérifiez les états dans le Suivi."
      : resumed === 1 ? "1 reprise d'indexation mise en file ; son état s'affiche dans le Suivi."
        : "3 reprises d'indexation mises en file ; leur état s'affiche dans le Suivi.";
    await expect(panel.getByText(notice, { exact: true })).toBeVisible();
    await captureDesktop(page, info, `editorial-injected-partial-resume-${resumed}`);
    await monitorBrowser(browser, `editorial-injected-resume-${resumed}`, info);
    await info.attach("substitutions", { contentType: "application/json", body: Buffer.from(JSON.stringify({ jobs: "GET response injected", resume_paused: `POST intercepted with resumed=${resumed}; no backend mutation`, all_pages_processed: true, interpretation: "UI wording/layout only, not an extraction or resume qualification" })) });
    expect(blocked).toEqual([]);
    expect(log.mutations).toEqual(["POST /api/v1/jobs/resume-paused"]);
    expect(log.external).toEqual([]);
    expect(log.pageErrors).toEqual([]);
  });
}

test("injected UI: SSE echoes deduplicate identical warnings but retain distinct details; empty search stays factual", async ({ page, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await page.route("**/api/v1/search", route => route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], warnings: [], elapsed_ms: 1, scope_snapshot: {} }) }));
  await page.route("**/api/v1/queries", route => route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ query_id: "editorial-sse", events_url: "/api/v1/queries/editorial-sse/events" }) }));
  const first = { code: "editorial-context", message: "Limite de contexte simulée.", identifier: "A", details: { b: 2, a: 1 } };
  const distinct = { ...first, identifier: "B" };
  const other = { code: "editorial-other", message: "Autre limite simulée." };
  const echo = { details: { a: 1, b: 2 }, identifier: "A", message: first.message, code: first.code };
  const events = [
    { type: "warning", data: { warning: first } }, { type: "warning", data: { warning: distinct } },
    { type: "warning", data: { warning: other } },
    { type: "done", data: { text: "Réponse simulée sans source.", status: "done", warnings: [echo, distinct, other] } },
  ];
  await page.route("**/api/v1/queries/editorial-sse/events", route => route.fulfill({ contentType: "text/event-stream", body: events.map((event, index) => `id: ${index + 1}\nevent: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`).join("") }));
  await page.goto("/workspace/");
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche", { exact: true }).fill("Recherche simulée");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page.getByText("Une recherche sans résultat ne prouve pas l'absence de l'information", { exact: false })).toBeVisible();
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question", { exact: true }).fill("Question simulée");
  await page.getByRole("button", { name: "Envoyer", exact: true }).click();
  const turn = page.getByTestId("query-turn");
  await expect(turn.getByText("Réponse simulée sans source.", { exact: true })).toBeVisible();
  await expect(turn.locator(".inline-warning")).toHaveCount(3);
  await expect(turn.getByText(first.message, { exact: true })).toHaveCount(2);
  await expect(turn.getByText(other.message, { exact: true })).toHaveCount(1);
  await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
  await captureDesktop(page, info, "editorial-injected-sse");
  await monitorBrowser(browser, "editorial-injected-sse", info);
  await info.attach("substitutions", { contentType: "application/json", body: Buffer.from(JSON.stringify({ search: "empty response injected", query: "POST creation intercepted", events: "synthetic SSE warning/done, no model call", identity: "same code/message/details collapses; differing identifiers remain", interpretation: "UI presentation only, not a query qualification" })) });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual(["POST /api/v1/search", "POST /api/v1/queries"]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});

test("injected UI: a session HTTP failure is not labelled as an unreachable service", async ({ page, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await page.route("**/api/v1/session", route => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ code: "EDITORIAL_SESSION_FAILURE", message: "Erreur de session simulée." }) }));
  await page.goto("/workspace/");
  await expect(page.getByRole("heading", { level: 1, name: "Ouverture de l'atelier impossible", exact: true })).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Vérification de la session impossible");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Erreur de session simulée.");
  await captureDesktop(page, info, "editorial-injected-session-http");
  await monitorBrowser(browser, "editorial-injected-session-http", info);
  await info.attach("substitutions", { contentType: "text/plain", body: Buffer.from("GET /session returns an injected HTTP 500; the service connection did not fail. UI wording/layout only.") });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});

test("injected UI: clipboard rejection gives a visible manual-copy action", async ({ page, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await page.route("**/api/v1/session", route => route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ code: "session_required", message: "Session requise." }) }));
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("clipboard rejection injected"); } } }));
  await page.goto("/workspace/");
  await expect(page.getByRole("heading", { name: "Session requise", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Copier la commande", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText("Copie impossible : sélectionnez la commande voulue et copiez-la manuellement.");
  await expect(page.getByRole("button", { name: "Commande copiée", exact: true })).toHaveCount(0);
  await captureDesktop(page, info, "editorial-injected-copy");
  await monitorBrowser(browser, "editorial-injected-copy", info);
  await info.attach("substitutions", { contentType: "text/plain", body: Buffer.from("Session-required response and clipboard rejection injected in the browser. No clipboard permission or launcher operation performed.") });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
