import { expect, test } from "@playwright/test";
import { readOnlyApi, watchPage } from "./guards";

const lengthNotice = "Réponse incomplète : la limite de longueur a été atteinte. Demandez une réponse plus concise ou détaillez un point précis dans le même périmètre.";
const independentNotice = "Deux passages n'ont pas été retenus dans le contexte.";
const lengthWarning = { code: "answer_length_limit", message: "Limite de génération atteinte ; réponse incomplète." };
const cases = [
  { name: "raison et avertissements répétés", finishReason: "length", backendWarning: true },
  { name: "raison seule", finishReason: "length", backendWarning: false },
  { name: "code seul", finishReason: undefined, backendWarning: true },
] as const;

// POST et SSE remplacés dans le navigateur : contrôle UI isolé, sans génération
// ni écriture de query réelle. Les GET ordinaires gardent l'API de recette ciblée.
for (const [index, scenario] of cases.entries()) test(`UI isolée : un seul avertissement de longueur (${scenario.name})`, async ({ page }, info) => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Instance de recette isolée requise.");
  const log = watchPage(page);
  const blocked: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await readOnlyApi(page, blocked);
  const queryId = `qa-ui-length-${index}`;
  const eventsUrl = `/api/v1/queries/${queryId}/events`;
  let submitted: { scope: unknown; mode: unknown } | null = null;
  await page.route("**/api/v1/queries", route => {
    expect(route.request().method()).toBe("POST");
    submitted = route.request().postDataJSON();
    return route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ query_id: queryId, events_url: eventsUrl }) });
  });
  const warnings = [
    { code: "context_fragments_excluded_by_budget", message: independentNotice },
    { code: "future_limit" },
    ...(scenario.backendWarning ? [lengthWarning, { code: "answer_length_limit", message: "Même coupure signalée une seconde fois." }] : []),
  ];
  const events = [
    { type: "status", data: { state: "generating" } },
    ...(scenario.backendWarning ? [{ type: "warning", data: { warning: lengthWarning } }] : []),
    { type: "done", data: { text: "Début d'une réponse interrompue par son plafond de génération.", status: "length_limited", warnings,
      ...(scenario.finishReason ? { finish_reason: scenario.finishReason } : {}) } },
  ];
  const sse = events.map((event, position) => `id: ${position + 1}\nevent: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`).join("");
  await page.route(`**${eventsUrl}*`, route => route.fulfill({ status: 200, contentType: "text/event-stream", body: sse }));
  await page.goto("/workspace/");
  const scope = page.getByTestId("scope-summary");
  await expect(scope).toBeVisible();
  const scopeLabel = scope.locator("strong");
  const scopeBefore = await scopeLabel.textContent();
  expect(scopeBefore).toBeTruthy();
  await page.getByRole("tab", { name: "Question", exact: true }).click();
  await page.getByLabel("Votre question").fill("Présentez les points du périmètre actif.");
  await page.getByRole("button", { name: "Envoyer", exact: true }).click();
  const turn = page.getByTestId("query-turn");
  await expect(turn.locator(".query-status")).toContainText("Réponse limitée");
  await expect(turn.getByText(lengthNotice, { exact: true })).toHaveCount(1);
  await expect(turn.locator(".inline-warning")).toHaveCount(3);
  await expect(turn.getByText(independentNotice, { exact: true })).toBeVisible();
  await expect(turn.getByText("Limite signalée par le service, sans description (code future_limit).", { exact: true })).toBeVisible();
  await expect(turn).not.toContainText(lengthWarning.message);
  await expect(turn).not.toContainText("demandez explicitement une suite");
  await expect(scopeLabel).toHaveText(scopeBefore!);
  expect(submitted).toMatchObject({ scope: { kind: "library" }, mode: "question" });
  for (const viewport of index === 0 ? [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }] : [{ width: 1366, height: 768 }]) {
    await page.setViewportSize(viewport);
    await turn.getByText(lengthNotice, { exact: true }).scrollIntoViewIfNeeded();
    await expect(turn.getByText(lengthNotice, { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`length-warning-${viewport.width}x${viewport.height}.png`), fullPage: true });
  }
  await info.attach("isolated-ui-length-warning", { body: Buffer.from(JSON.stringify({ scenario, submitted, events,
    substitutions: ["POST /api/v1/queries", `GET ${eventsUrl}`],
    scope: "Affichage de l'export courant uniquement ; aucune génération ni query réelle, aucune qualification backend.",
    blocked, mutations: log.mutations, external: log.external, pageErrors: log.pageErrors, consoleErrors }, null, 2)), contentType: "application/json" });
  expect(blocked).toEqual([]);
  expect(log.mutations).toEqual(["POST /api/v1/queries"]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
