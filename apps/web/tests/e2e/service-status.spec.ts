import { test, expect } from "@playwright/test";
import { readOnlyApi, watchPage } from "./guards";
import { monitorBrowser } from "./resources";

const expectedDoctorCommand = process.env.RAG_E2E_DOCTOR_COMMAND
  ?? (process.platform === "win32" ? ".\\rag.ps1 doctor" : "./rag.sh doctor");

// État négatif injecté dans le navigateur : ce test valide le texte et son rendu,
// pas une panne réelle du modèle ni la disponibilité du backend.
test("isolated UI: blocked readiness keeps its cause and a readable service label", async ({ page, request, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  const health = await request.get("/api/v1/health");
  expect(health.ok()).toBe(true);
  const announced = (await health.json() as { commands?: { doctor?: unknown } }).commands?.doctor;
  expect(announced).toBe(expectedDoctorCommand);
  await page.route("**/api/v1/readiness", route => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ status: "blocked", checks: { embedding: false }, blockers: ["embedding_not_ready"] }),
  }));
  await monitorBrowser(browser, "service-status-start", info);
  await page.goto("/workspace/");
  // En desktop, l'état est dans la barre supérieure ; le bandeau le reprend seulement sous 48rem.
  const status = page.locator(".topbar-service");
  await expect(status).toHaveText("Service local pas encore prêt");
  await expect(status).toHaveAttribute("title", /Non prêts :/);
  await expect(page.locator(".readiness-notice")).toContainText(expectedDoctorCommand);
  await expect(page.locator(".readiness-notice")).toHaveAttribute("title", "Contrôles non satisfaits : embedding_not_ready");
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await expect(status).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`service-not-ready-${viewport.width}x${viewport.height}.png`), fullPage: true });
  }
  await info.attach("scenario-scope", {
    body: Buffer.from(JSON.stringify({ readiness: "HTTP 503 injected only in the browser", api_writes_blocked: blocked,
      interpretation: "UI text and layout only; other GET requests use the isolated API. No backend failure qualification." }, null, 2)),
    contentType: "application/json",
  });
  await monitorBrowser(browser, "service-status-end", info);
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
