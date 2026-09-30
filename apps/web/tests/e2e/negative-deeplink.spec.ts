import { test, expect } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { readOnlyApi, watchPage } from "./guards";

// Un lien de citation résout toujours le vrai registre : identité inconnue ou
// invalide = erreur visible, aucun document courant substitué. GET seul.
test.beforeEach(() => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Scénario GET seul planifié séparément ; NOT_RUN sans autorisation explicite.");
});

test("an unknown registered citation shows a visible alert and opens no document", async ({ page, browser }, info) => {
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await monitorBrowser(browser, "negative-deeplink-start", info);
  const registry = page.waitForResponse(response => new URL(response.url()).pathname === "/api/v1/citations/inconnu/S999");
  await page.goto("/workspace/?citation_query=inconnu&citation_source=S999");
  const response = await registry;
  const body = await response.json();
  expect(response.status()).toBe(404);
  const alert = page.locator(".workspace-error[role=alert]");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(String(body.message));
  await expect(page.getByRole("heading", { name: "Aucun document ouvert", exact: true })).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.locator(".source-navigation")).toHaveCount(0);
  expect(new URL(page.url()).searchParams.get("document")).toBeNull();
  await page.screenshot({ path: info.outputPath("unknown-citation-alert.png") });
  await alert.getByRole("button", { name: "Fermer le message" }).click();
  await expect(alert).toHaveCount(0);
  await info.attach("unknown-citation-registry-response", { body: Buffer.from(JSON.stringify({ status: response.status(), body, requests: log.requests }, null, 2)), contentType: "application/json" });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});

test("partial or malformed citation links are refused before any registry request", async ({ page }, info) => {
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  for (const [label, query] of [["query-only", "citation_query=inconnu"], ["source-only", "citation_source=S999"], ["traversal", "citation_query=..%2Fautre&citation_source=S001"]]) {
    await page.goto(`/workspace/?${query}`);
    const alert = page.locator(".workspace-error[role=alert]");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Le lien de citation ne contient pas deux identifiants valides.");
    await expect(page.locator("canvas")).toHaveCount(0);
    await page.screenshot({ path: info.outputPath(`malformed-citation-${label}.png`) });
  }
  expect(log.requests.filter(request => request.path.startsWith("/api/v1/citations/"))).toEqual([]);
  expect(blocked).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
