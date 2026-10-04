import { expect, test } from "@playwright/test";
import { readOnlyApi, watchPage } from "./guards";
import { monitorBrowser } from "./resources";

test("le modèle choisi répond sur l’index conservé et ouvre sa citation", async ({ page, request, browser }, info) => {
  test.setTimeout(660000);
  test.skip(process.env.RAG_E2E_GENERATION_ALLOWED !== "1" || !process.env.RAG_E2E_NATIVE_VERSION,
    "Créneau de génération et version synthétique publiée requis.");
  const version = process.env.RAG_E2E_NATIVE_VERSION!;
  const generation = process.env.RAG_E2E_NATIVE_GENERATION!;
  expect(generation).toBeTruthy();
  const modelDigest = process.env.RAG_E2E_NATIVE_DIGEST!;
  expect(modelDigest).toMatch(/^[0-9a-f]{64}$/);
  const tree = await request.get("/api/v1/library/tree");
  expect(tree.status()).toBe(200);
  const documents = (await tree.json()).documents as { id: string; name: string; version_id: string; state: string; sha256: string }[];
  const document = documents.find(item => item.version_id === version);
  expect(document?.name).toBe("Procédure QV-01.pdf");
  expect(document?.state).toBe("ready");
  expect(document?.sha256).toBe("a2fe869653f333b8a60cf985300dc8387168d8bc9c7003ca074ef714df7a448b");
  const log = watchPage(page);
  const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.goto("/workspace/");
  await page.getByLabel("Sélectionner Procédure QV-01.pdf").check();
  await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question").fill("Quelle est la pression de réglage de QV-01 ? Citez le passage qui la donne.");
  await monitorBrowser(browser, "before-native-question", info);
  const createdResponse = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/queries"));
  let queryId: string | null = null;
  let replayBody: Buffer | null = null;
  try {
    await page.getByRole("button", { name: "Envoyer", exact: true }).click();
    const created = await createdResponse;
    expect(created.status()).toBe(202);
    expect(created.request().postDataJSON().scope).toEqual({ kind: "documents", documentIds: [document!.id] });
    queryId = (await created.json()).query_id;
    await expect(page.locator(".query-status").last()).toContainText(/Réponse terminée|Réponse limitée|Échec|Réponse annulée|Réponse interrompue/, { timeout: 600000 });
    await expect(page.locator(".query-status").last()).toContainText("Réponse terminée");
    await expect(page.locator(".answer-text").last()).toContainText(/2[.,]7\s*(?:\*\*)?\s*bar/);
    const replay = await request.get(`/api/v1/queries/${encodeURIComponent(queryId!)}/events?after=0`, { timeout: 10000 });
    expect(replay.status()).toBe(200);
    replayBody = await replay.body();
    const done = replayBody.toString("utf8").split(/\r?\n\r?\n/).find(event => event.split(/\r?\n/).includes("event: done"));
    expect(done).toBeTruthy();
    const metrics = JSON.parse(done!.split(/\r?\n/).find(line => line.startsWith("data: "))!.slice(6)).metrics;
    expect(metrics.model_called).toBe(true);
    expect(metrics.verified_model_identity.digest).toBe(modelDigest);
    const clicked = page.waitForResponse(response => response.url().includes(`/api/v1/citations/${queryId}/`));
    await page.locator(".inline-citation").first().click();
    const response = await clicked;
    expect(response.status()).toBe(200);
    const source = await response.json();
    expect(source.query_id).toBe(queryId);
    expect(source.document_id).toBe(document!.id);
    expect(source.version_id).toBe(version);
    expect(source.generation_id).toBe(generation);
    expect(source.extraction_revision_id).toBeTruthy();
    expect(source.page_index).toBe(0);
    expect(source.text).toMatch(/2[.,]7/);
    await info.attach("clicked-native-citation", { body: Buffer.from(JSON.stringify(source)), contentType: "application/json" });
    await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
    await expect(page.getByTestId("source-highlight").first()).toBeVisible();
    await expect(page.getByTestId("scope-summary")).toContainText(document!.name);
    expect(await page.locator("canvas").count()).toBeLessThanOrEqual(5);
    expect(await page.locator("canvas").evaluateAll(canvases => canvases.reduce((pixels, canvas) =>
      pixels + (canvas as HTMLCanvasElement).width * (canvas as HTMLCanvasElement).height, 0))).toBeLessThanOrEqual(24_000_000);
    await page.screenshot({ path: info.outputPath("native-question-citation.png"), fullPage: true });
    await monitorBrowser(browser, "after-native-citation", info);
    expect(log.mutations).toEqual(["POST /api/v1/queries"]);
    expect(log.external).toEqual([]);
    expect(log.pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  } finally {
    if (queryId) {
      if (!replayBody) replayBody = await (await request.get(`/api/v1/queries/${encodeURIComponent(queryId)}/events?after=0`, { timeout: 10000 })).body();
      await info.attach("native-sse-replay", { body: replayBody, contentType: "text/event-stream" });
      const cancel = page.getByRole("button", { name: "Annuler", exact: true });
      if (await cancel.isVisible()) await cancel.click();
    }
  }
});

// API réelle et lecture seule ; aucun modèle ni matériel remplacé dans le navigateur.
test("le modèle de démarrage réel reste lisible avec son aide clavier", async ({ page, request, browser }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const expected = process.env.RAG_E2E_MODEL ?? "qwen3.5:2b";
  const jobs = await request.get("/api/v1/jobs");
  expect(jobs.ok()).toBe(true);
  const generation = (await jobs.json()).generation;
  expect(generation.model).toBe(expected);
  expect(["cpu", "gpu"]).toContain(generation.device);
  const label = expected === "qwen3.5:2b" ? "Qwen 3.5 2B" : expected === "qwen3.5:4b-text" ? "Qwen 3.5 4B · texte seul" : expected;
  const log = watchPage(page);
  const blocked: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await readOnlyApi(page, blocked);
  await monitorBrowser(browser, "model-start", info);
  await page.goto("/workspace/");
  await expect(page.getByRole("heading", { name: "Bibliothèque", exact: true })).toBeVisible();
  const indicator = page.locator(".context-generation");
  const help = page.getByRole("button", { name: "Explication du modèle et du matériel de génération", exact: true });
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await expect(indicator.getByText(label, { exact: true })).toBeVisible();
    await help.focus();
    await page.keyboard.press("Enter");
    await expect(help).toHaveAttribute("aria-expanded", "true");
    const explanation = page.locator(".generation-help-text");
    await expect(explanation).toContainText(expected);
    await expect(explanation).toContainText("redémarrez avec ce même profil");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`model-${viewport.width}x${viewport.height}.png`), fullPage: true });
    await page.keyboard.press("Escape");
    await expect(help).toHaveAttribute("aria-expanded", "false");
    await expect(help).toBeFocused();
  }
  await info.attach("actual-model", { body: Buffer.from(JSON.stringify({ expected, generation, substitutions: [],
    scope: "Modèle et aide lus sur une instance réelle ; ce test ne qualifie pas une génération." })), contentType: "application/json" });
  await monitorBrowser(browser, "model-end", info);
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
