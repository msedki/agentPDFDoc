/**
 * Priorité du poste pendant un import de recette (R26-UI-02, défaut D4 de la recette R26-KIT-02).
 *
 * « Priorité aux questions » est un marqueur durable du gouverneur (`data/control/pause-ingestion`,
 * services/runtime/resources.py) : une recette de génération le laisse, un redémarrage le conserve, et l'import
 * suivant reste `queued` jusqu'au délai de la spec. Une spec qui importe choisit donc « Priorité aux imports » dans
 * le Suivi, comme l'utilisateur, puis rétablit la priorité trouvée, que l'import réussisse ou échoue.
 *
 * Le choix se fait dans une page dédiée du même contexte (même session), fermée aussitôt : la page du scénario et
 * son journal (watchPage) ne voient ni cette navigation ni le POST du choix ; hostile-markup.spec.ts n'admet par
 * exemple que l'import et la recherche comme mutations de sa page.
 *
 * Le module ne choisit aucune cible : chemins relatifs au `baseURL` du navigateur et du contexte `request`, fixé par
 * playwright.config.ts à partir de target.ts, seule garde de cible.
 */
import { expect, type APIRequestContext, type BrowserContext, type Page, type TestInfo } from "@playwright/test";

export type Priority = "interactive" | "ingestion";
export const JOBS_PATH = "/api/v1/jobs";
export const RUNTIME_MODE_PATH = "/api/v1/runtime/mode";
export const PRIORITY_LABELS: Readonly<Record<Priority, string>> = { interactive: "Priorité aux questions", ingestion: "Priorité aux imports" };

/** Parcours consigné en pièce jointe `import-priority` de la spec. */
export type ImportPriorityRecord = {
  initial: Priority | null;
  during_import: "ingestion";
  restore_requested: boolean;
  after: Priority | null | "illisible";
  action_failed: boolean;
  restore_error: string | null;
};

/** Priorité choisie, lue côté service (`runtime_mode` de GET /api/v1/jobs) ; null si le service n'a pas de gouverneur. */
export async function readPriority(request: APIRequestContext): Promise<Priority | null> {
  const response = await request.get(JOBS_PATH);
  expect(response.status(), `GET ${JOBS_PATH}`).toBe(200);
  return (await response.json() as { runtime_mode?: Priority | null }).runtime_mode ?? null;
}

/**
 * Choix dans le Suivi d'une page dédiée du contexte, comme l'utilisateur : réponse du service, bouton marqué, page
 * fermée, puis priorité relue côté service.
 */
export async function choosePriority(context: BrowserContext, request: APIRequestContext, mode: Priority): Promise<void> {
  const label = PRIORITY_LABELS[mode];
  const panel = await context.newPage();
  try {
    await panel.goto("/workspace/");
    await panel.getByRole("button", { name: "Suivi", exact: false }).click();
    const changed = panel.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(RUNTIME_MODE_PATH));
    await panel.getByRole("button", { name: label, exact: true }).click();
    expect((await changed).status(), `POST ${RUNTIME_MODE_PATH} (« ${label} »)`).toBe(200);
    await expect.poll(() => panel.getByRole("button", { name: label, exact: true }).getAttribute("aria-pressed"), { message: `Bouton « ${label} » marqué` }).toBe("true");
    await panel.getByRole("button", { name: "Fermer le suivi", exact: true }).click();
  } finally {
    await panel.close();
  }
  expect(await readPriority(request), `Priorité relue après « ${label} »`).toBe(mode);
}

/**
 * Exécute `action` sous « Priorité aux imports », puis rétablit « Priorité aux questions » si c'était la priorité
 * trouvée. Le rétablissement a lieu dans le `finally`, donc aussi quand l'import échoue ; l'erreur de l'import reste
 * alors celle rapportée et un échec du rétablissement est seulement consigné. Après un import réussi, un échec du
 * rétablissement fait échouer la spec.
 */
export async function withImportPriority<T>(page: Page, request: APIRequestContext, info: TestInfo, action: () => Promise<T>): Promise<T> {
  const initial = await readPriority(request);
  if (initial !== "ingestion") await choosePriority(page.context(), request, "ingestion");
  let actionFailed = true;
  try {
    const value = await action();
    actionFailed = false;
    return value;
  } finally {
    await restorePriority(page, request, info, initial, actionFailed);
  }
}

async function restorePriority(page: Page, request: APIRequestContext, info: TestInfo, initial: Priority | null, actionFailed: boolean) {
  const restoreRequested = initial === "interactive";
  let restoreError: unknown = null;
  if (restoreRequested) {
    try { await choosePriority(page.context(), request, "interactive"); } catch (error) { restoreError = error; }
  }
  let after: ImportPriorityRecord["after"];
  try { after = await readPriority(request); } catch { after = "illisible"; }
  const record: ImportPriorityRecord = { initial, during_import: "ingestion", restore_requested: restoreRequested, after, action_failed: actionFailed,
    restore_error: restoreError === null ? null : restoreError instanceof Error ? restoreError.message : String(restoreError) };
  await info.attach("import-priority", { body: Buffer.from(JSON.stringify(record, null, 2)), contentType: "application/json" });
  if (restoreError !== null && !actionFailed) throw restoreError;
}
