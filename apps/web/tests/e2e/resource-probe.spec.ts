import { test, expect } from "@playwright/test";
import { monitorBrowser } from "./resources";

test("read-only own browser memory probe with a real native PDF", async ({ page, browser }, info) => {
  test.setTimeout(90000);
  test.skip(process.env.RAG_E2E_RESOURCE_PROBE_ALLOWED !== "1", "This resource probe requires its own authorized GET-only window.");
  const name = "Atelier 1 - Banc pneumatique DA-P01.pdf";
  const mutations: string[] = [];
  const errors: string[] = [];
  page.on("request", request => {
    if (!["GET", "HEAD"].includes(request.method())) mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  page.on("pageerror", error => errors.push(error.message));
  await monitorBrowser(browser, "own-headless-start", info);
  await page.goto("/workspace/");
  await page.getByLabel(`Sélectionner ${name}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
  await page.getByLabel("Votre question").fill("Quelle est la pression nominale de DA-P01 ? Citez sa source.");
  // Same local scope/form state as the previous admission attempt. No submit,
  // runtime-mode mutation, retrieval, import, embedding or model call.
  await monitorBrowser(browser, "own-question-form-not-submitted", info);
  const document = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: /Atelier 1 - Banc pneumatique DA-P01\.pdf/ }).first();
  await document.click();
  await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.locator(".textLayer span").filter({ hasText: /3\.1/ }).first()).toBeVisible();
  await monitorBrowser(browser, "own-native-pdf-rendered", info);
  await page.screenshot({ path: info.outputPath("read-only-pdf-memory.png"), fullPage: true });
  await info.attach("browser-probe-configuration", { body: Buffer.from(JSON.stringify({ worker_id: process.pid, browser_version: browser.version(), contexts: browser.contexts().length, pages: browser.contexts().map(context => context.pages().length), headless: true, custom_launch_args: [], mutations, page_errors: errors, interpretation: "Snapshots from a separate GET-only run; do not replace the failed question attempt's historical memory samples." }, null, 2)), contentType: "application/json" });
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});
