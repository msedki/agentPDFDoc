import { test, expect } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { apiOrigin, fixtureAtPath, importPublished, pageBlocks, watchPage } from "./guards";

// D08 : le balisage HTML/Markdown d'un PDF reste une donnée affichée littéralement.
// Recherche lexicale seule, aucun appel /queries ni génération, périmètre inchangé.
const fixturePath = "qualification-v2.1/hostile/markup-injection.pdf";
const markup = /<\/?[a-z][^>]*>|!\[[^\]]*\]\([^)]*\)|\[[^\]]+\]\((?:javascript:|(?:https?:)?\/\/)[^)]*\)/i;

test("hostile markup stays literal text with no active element, no remote request and no scope change", async ({ page, request, browser }, info) => {
  test.setTimeout(720000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Import de fixtures contrôlées sur stockage isolé autorisé uniquement ; NOT_RUN sinon.");
  const input = fixtureAtPath(fixturePath);
  test.skip(!input, `Fixture ${fixturePath} absente du manifeste et de son sidecar : NOT_RUN.`);
  const log = watchPage(page);
  await monitorBrowser(browser, "hostile-markup-start", info);
  const imported = await importPublished(page, request, input!, info);
  const detail = await (await request.get(`${apiOrigin}/api/v1/documents/${encodeURIComponent(imported.documentId)}`)).json();
  const pageCount = Number(detail.versions.find((version: { id: string }) => version.id === imported.versionId)?.page_count ?? 0);
  expect(pageCount).toBeGreaterThan(0);
  // Chaînes déclarées par le sidecar, confrontées à l'extraction réelle : l'UI doit
  // restituer littéralement ce que l'API fournit ; un écart d'extraction est seulement consigné.
  let found: { pageIndex: number; texts: string[] } | null = null;
  for (let pageIndex = 0; pageIndex < pageCount && !found; pageIndex++) {
    const texts = (await pageBlocks(request, imported.versionId, pageIndex)).blocks.map((block: { text: string; raw_text?: string }) => block.raw_text ?? block.text) as string[];
    if (texts.some(text => markup.test(text))) found = { pageIndex, texts };
  }
  expect(found, "Balisage présent dans l'extraction réelle de la fixture").not.toBeNull();
  const declared = (input!.expected_native_strings ?? []).filter(value => markup.test(value));
  const candidates = declared.length ? declared : found!.texts.map(text => text.match(markup)?.[0] ?? "").filter(Boolean);
  const literals = candidates.filter(literal => found!.texts.some(text => text.includes(literal)));
  await info.attach("hostile-markup-extraction", { body: Buffer.from(JSON.stringify({ origin: input!.origin, declared, extracted_page: found!.pageIndex, literals_present_in_api: literals, literals_absent_from_api: candidates.filter(literal => !literals.includes(literal)), block_texts: found!.texts }, null, 2)), contentType: "application/json" });
  expect(literals.length, "Au moins un balisage déclaré présent tel quel dans l'extraction").toBeGreaterThan(0);
  const anchorText = found!.texts.find(text => text.includes(literals[0]))!;
  const words = anchorText.replace(new RegExp(markup.source, "gi"), " ").match(/[\p{L}\p{N}][\p{L}\p{N}-]{3,}/gu) ?? [];
  expect(words.length, "Mots non balisés disponibles pour la recherche lexicale").toBeGreaterThan(0);

  await page.goto(`/workspace/?document=${encodeURIComponent(imported.documentId)}&version=${encodeURIComponent(imported.versionId)}&page=${found!.pageIndex + 1}`);
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.evaluate(() => {
    const created: string[] = [];
    (window as unknown as { __activeElements: string[] }).__activeElements = created;
    const active = ["IMG", "IMAGE", "SCRIPT", "IFRAME", "OBJECT", "EMBED", "A", "LINK", "BASE", "META", "STYLE"];
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        for (const element of [node, ...node.querySelectorAll("*")]) if (active.includes(element.tagName.toUpperCase())) created.push(element.outerHTML.slice(0, 200));
      }
    }).observe(document.querySelector(".workspace-shell")!, { childList: true, subtree: true });
  });
  await page.getByRole("button", { name: "Analyser cette page", exact: true }).click();
  const scopeLabel = `page ${found!.pageIndex + 1}`;
  await expect(page.getByTestId("scope-summary")).toContainText(scopeLabel);
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche").fill(words.slice(0, 6).join(" "));
  const searched = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const search = await searched;
  expect(search.status()).toBe(200);
  expect(search.request().postDataJSON().scope).toMatchObject({ kind: "pages", versionId: imported.versionId, pageStart: found!.pageIndex, pageEnd: found!.pageIndex });
  const card = page.getByTestId("source-card").filter({ hasText: literals[0] }).first();
  await expect(card).toBeVisible();
  await expect(card.locator("p")).toContainText(literals[0]);
  await card.getByRole("button", { name: "Ouvrir le passage", exact: true }).click();
  await expect(page.getByTestId("scope-summary")).toContainText(scopeLabel);
  await page.getByRole("button", { name: "Texte extrait & provenance" }).click();
  for (const literal of literals) await expect(page.locator(".extracted-text")).toContainText(literal);
  await page.screenshot({ path: info.outputPath("hostile-markup-literal.png"), fullPage: true });

  const created = await page.evaluate(() => (window as unknown as { __activeElements: string[] }).__activeElements);
  await info.attach("hostile-markup-observation", { body: Buffer.from(JSON.stringify({ document_id: imported.documentId, version_id: imported.versionId, page_index: found!.pageIndex, literals, search_request: search.request().postDataJSON(), created_active_elements: created, requests: log.requests, external: log.external }, null, 2)), contentType: "application/json" });
  expect(created).toEqual([]);
  expect(await page.locator(".workspace-shell").locator("img, script, iframe, object, embed, a[href], image").count()).toBe(0);
  expect(log.requests.some(item => item.path.startsWith("/api/v1/queries"))).toBe(false);
  expect(log.mutations.filter(item => !["POST /api/v1/documents/import", "POST /api/v1/search"].includes(item))).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  await monitorBrowser(browser, "hostile-markup-end", info);
});
