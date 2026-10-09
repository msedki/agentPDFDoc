/**
 * Session locale (W011) vue par le navigateur : écran sans session, lien rejoué,
 * fermeture. Chaque cas part d'un contexte vierge et ouvre sa propre session ;
 * la session partagée des autres specs n'est pas touchée.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { readFileSync } from "node:fs";
import { e2eTarget } from "./target.ts";

const tokenFile = e2eTarget().tokenFile;
// Le binding de recette fournit la commande installée ; le checkout garde son lanceur natif.
const expectedOpenCommand = process.env.RAG_E2E_OPEN_COMMAND
  ?? (process.platform === "win32" ? ".\\rag.ps1 open" : "./rag.sh open");

async function openingLink(request: APIRequestContext): Promise<string> {
  const response = await request.post("/api/v1/admin/session-links", { headers: { "X-RAG-Control-Token": readFileSync(tokenFile, "ascii").trim() } });
  expect(response.ok()).toBe(true);
  return (await response.json() as { path: string }).path;
}

test.describe("sans session", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("l'atelier affiche la commande d'ouverture au lieu de l'espace de travail", async ({ page, request }) => {
    // L'attente provient du binding revu, indépendamment de l'annonce /health et du rendu.
    const health = await request.get("/api/v1/health");
    expect(health.ok()).toBe(true);
    const announced = (await health.json() as { commands?: { open?: unknown } }).commands?.open;
    expect(announced).toBe(expectedOpenCommand);
    await page.goto("/workspace/");
    await expect(page.getByRole("heading", { level: 1, name: "Session requise" })).toBeVisible();
    await expect(page.getByText(String(announced), { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copier la commande", exact: true })).toBeVisible();
    // Commande connue : une seule ligne, sans la variante de l'autre plateforme.
    await expect(page.locator(".session-command")).toHaveCount(1);
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

  test("un échec réseau de fermeture est signalé, puis une nouvelle tentative révoque réellement la session", async ({ page, request }, info) => {
    await page.goto(await openingLink(request));
    await expect(page.getByRole("heading", { name: "Bibliothèque" })).toBeVisible();
    // Fault injection navigateur uniquement : aucune première requête de révocation n'atteint le serveur.
    await page.route("**/api/v1/session/logout", route => route.abort("connectionrefused"));
    await page.getByRole("button", { name: "Fermer la session", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Fermeture de la session non confirmée" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Session fermée", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Bibliothèque", exact: true })).toHaveCount(0);
    expect((await page.request.get("/api/v1/session")).status()).toBe(200);
    await page.screenshot({ path: info.outputPath("logout-not-confirmed.png"), fullPage: true });
    await page.unroute("**/api/v1/session/logout");
    await page.getByRole("button", { name: "Réessayer la fermeture", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Session fermée", exact: true })).toBeVisible();
    expect((await page.request.get("/api/v1/session")).status()).toBe(401);
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Session requise", exact: true })).toBeVisible();
  });
});
