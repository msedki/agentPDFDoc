/**
 * Session locale (W011) vue par le navigateur : écran sans session, lien rejoué,
 * fermeture. Chaque cas part d'un contexte vierge et ouvre sa propre session ;
 * la session partagée des autres specs n'est pas touchée.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const tokenFile = process.env.RAG_E2E_CONTROL_TOKEN_FILE ?? path.resolve(process.cwd(), "../../.runtime/data/control/admin-token");

async function openingLink(request: APIRequestContext): Promise<string> {
  const response = await request.post("/api/v1/admin/session-links", { headers: { "X-RAG-Control-Token": readFileSync(tokenFile, "ascii").trim() } });
  expect(response.ok()).toBe(true);
  return (await response.json() as { path: string }).path;
}

test.describe("sans session", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("l'atelier affiche la commande d'ouverture au lieu de l'espace de travail", async ({ page }) => {
    await page.goto("/workspace/");
    await expect(page.getByRole("heading", { level: 1, name: "Session requise" })).toBeVisible();
    await expect(page.getByText(".\\rag.ps1 open", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copier la commande" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bibliothèque" })).toHaveCount(0);
  });

  test("un lien d'ouverture ne sert qu'une fois", async ({ page, browser, request }) => {
    const link = await openingLink(request);
    await page.goto(link);
    await expect(page).toHaveURL(/\/workspace\/$/);
    await expect(page.getByRole("heading", { name: "Bibliothèque" })).toBeVisible();
    const other = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    try {
      const replay = await other.newPage();
      await replay.goto(link);
      await expect(replay.getByRole("heading", { level: 1, name: "Lien d'ouverture expiré ou déjà utilisé" })).toBeVisible();
      // Le paramètre de refus ne reste pas dans l'adresse.
      await expect(replay).toHaveURL(/\/workspace\/$/);
    } finally {
      await other.close();
    }
  });

  test("fermer la session efface l'accès de ce navigateur", async ({ page, request }) => {
    await page.goto(await openingLink(request));
    await expect(page.getByRole("heading", { name: "Bibliothèque" })).toBeVisible();
    await page.getByRole("button", { name: "Fermer la session" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Session fermée" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Session requise" })).toBeVisible();
  });
});
