/**
 * Recette visuelle (R20) : captures des états principaux de l'atelier aux deux tailles
 * de bureau et en largeur réduite, sur l'instance réelle, en lecture seule. Le document
 * ouvert est la fixture synthétique DA-P01 (aucune page du corpus privé n'est capturée).
 * Planifiée séparément : NOT_RUN sans RAG_E2E_VISUAL_QA=1.
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { readOnlyApi } from "./guards";

const fixtureName = "Atelier 1 - Banc pneumatique DA-P01.pdf";
const outputRoot = process.env.RAG_E2E_VISUAL_QA_DIR ?? path.resolve(process.cwd(), "reports/visual-qa");

test.skip(process.env.RAG_E2E_VISUAL_QA !== "1", "Recette visuelle planifiée séparément ; NOT_RUN sans autorisation explicite.");

async function capture(page: Page, name: string) {
  mkdirSync(outputRoot, { recursive: true });
  const size = page.viewportSize();
  await page.screenshot({ path: path.join(outputRoot, `${name}-${size?.width}x${size?.height}.png`) });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`états principaux de l'atelier à ${viewport.width}×${viewport.height}`, async ({ page }) => {
    const blocked: string[] = [];
    await readOnlyApi(page, blocked);
    await page.setViewportSize(viewport);
    await page.goto("/workspace/");
    await expect(page.getByRole("heading", { name: "Bibliothèque", exact: true })).toBeVisible();
    await capture(page, "01-accueil");

    await page.getByRole("button", { name: new RegExp(fixtureName.replace(/[.()]/g, "\\$&")) }).first().click();
    await expect(page.getByRole("heading", { name: fixtureName })).toBeVisible();
    await page.waitForTimeout(1500);
    await capture(page, "02-document-ouvert");

    await page.getByRole("button", { name: /Périmètre/ }).first().click();
    await expect(page.getByRole("heading", { name: "Définir le périmètre" })).toBeVisible();
    await capture(page, "03-perimetre");
    await page.keyboard.press("Escape");

    await page.getByRole("tab", { name: "Recherche" }).click();
    await capture(page, "04-onglet-recherche");

    await page.getByRole("button", { name: /Suivi/ }).first().click();
    await expect(page.getByRole("heading", { name: "Suivi des traitements" })).toBeVisible();
    await capture(page, "05-suivi");
    await page.getByRole("button", { name: "Fermer le suivi" }).click();

    await page.getByRole("button", { name: "Aide" }).click();
    await expect(page.getByRole("heading", { name: "Raccourcis clavier" })).toBeVisible();
    await capture(page, "06-aide");
    await page.keyboard.press("Escape");

    await page.keyboard.press("Control+b");
    await page.waitForTimeout(300);
    await capture(page, "07-bibliotheque-reduite");
    await page.keyboard.press("Control+b");
    await page.waitForTimeout(300);
    await capture(page, "08-bibliotheque-masquee");
    await page.keyboard.press("Control+b");
    expect(blocked).toEqual([]);
  });
}

test("largeur réduite : panneaux en feuilles latérales", async ({ page }) => {
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await page.setViewportSize({ width: 900, height: 700 });
  await page.goto("/workspace/");
  await expect(page.getByRole("heading", { name: "Lecteur", exact: true })).toBeVisible();
  await capture(page, "09-largeur-reduite");
  await page.keyboard.press("Control+b");
  await page.waitForTimeout(400);
  await capture(page, "10-feuille-bibliotheque");
  expect(blocked).toEqual([]);
});

test.describe("sans session", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test("écran d'ouverture", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/workspace/");
    await expect(page.getByRole("heading", { level: 1, name: "Session requise" })).toBeVisible();
    await capture(page, "11-session-requise");
  });
});
