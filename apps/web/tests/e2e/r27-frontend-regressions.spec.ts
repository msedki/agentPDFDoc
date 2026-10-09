/**
 * Régressions R27 B04/B05 sur le vrai export navigateur. Recherche et catalogue sont
 * interceptés par des doubles déclarés : ces cas qualifient l'UI, pas les moteurs
 * ni une bibliothèque native de 10001 documents. Session/health restent sur l'API
 * de recette isolée imposée par la configuration Playwright.
 */
import { expect, test } from "@playwright/test";

test("UI isolée : Ctrl et Meta+Entrée ne doublent pas une recherche en cours", async ({ page }, info) => {
  let count = 0;
  // Compter fetch au déclenchement évite qu'une assertion précède la réception asynchrone d'une route en double.
  await page.addInitScript(() => {
    const probe = window as typeof window & { __r27SearchPosts: number };
    probe.__r27SearchPosts = 0;
    const original = window.fetch.bind(window);
    window.fetch = (input, options) => {
      if (String(input).endsWith("/api/v1/search") && options?.method === "POST") probe.__r27SearchPosts++;
      return original(input, options);
    };
  });
  let release: (() => void) | undefined;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/search", async route => {
    count++;
    expect(route.request().postDataJSON()).toMatchObject({ question: "terme de la première recherche", scope: { kind: "library" } });
    if (count === 1) await held;
    await route.fulfill({ json: { results: [], warnings: [], scope_snapshot: { kind: "library" }, elapsed_ms: 1 } });
  });
  try {
    await page.goto("/workspace/");
    await expect(page.getByRole("heading", { name: "Analyse", exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Recherche", exact: true }).click();
    const input = page.getByLabel("Votre recherche", { exact: true });
    await input.fill("terme de la première recherche");
    await input.press("Control+Enter");
    await expect.poll(() => count).toBe(1);
    await expect(page.getByRole("button", { name: "Recherche…", exact: true })).toBeDisabled();
    await input.press("Control+Enter");
    await input.press("Meta+Enter");
    await input.press("Control+Enter");
    expect(await page.evaluate(() => (window as typeof window & { __r27SearchPosts: number }).__r27SearchPosts)).toBe(1);
    expect(count).toBe(1);
    release?.();
    await expect(page.getByRole("button", { name: "Rechercher", exact: true })).toBeEnabled();
    await expect(page.getByText("Aucun passage retrouvé", { exact: true })).toBeVisible();
    await info.attach("search-transport-double", { body: JSON.stringify({ intercepted_posts: count, held_response: true, native_retrieval: false }), contentType: "application/json" });
  } finally { release?.(); }
});

test("UI isolée : le document après 10000 reste filtrable, sélectionnable et utilisable comme périmètre", async ({ page }, info) => {
  const total = 10001;
  const lastName = "Dernier document du catalogue.pdf";
  const offsets = new Set<number>();
  let holdFirst = true;
  let release: (() => void) | undefined;
  const first = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/library/tree?*", async route => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.add(offset);
    if (offset === 0 && holdFirst) { holdFirst = false; await first; }
    const documents = Array.from({ length: Math.min(100, total - offset) }, (_, local) => {
      const index = offset + local;
      const name = index === total - 1 ? lastName : `Document synthétique ${index}.pdf`;
      return { id: `document-${index}`, folder_id: null, name, relative_path: `Catalogue/${name}`, state: "ready", page_count: 1, active_version_id: `version-${index}`, active_generation_id: `generation-${index}` };
    });
    await route.fulfill({ json: { folders: [], documents, total_documents: total, next_cursor: offset + documents.length < total ? String(offset + documents.length) : null } });
  });
  try {
    await page.goto("/workspace/");
    // Filtrer avant de libérer la première page évite de fabriquer 10001 lignes DOM pour ce contrôle de pagination.
    await expect(page.getByLabel("Filtrer les fichiers", { exact: true })).toBeVisible();
    await page.getByLabel("Filtrer les fichiers", { exact: true }).fill(lastName);
    release?.();
    const tree = page.getByRole("navigation", { name: "Arborescence documentaire", exact: true });
    const checkbox = tree.getByRole("checkbox", { name: `Sélectionner ${lastName}`, exact: true });
    await expect(checkbox).toBeVisible();
    await expect(tree.getByRole("checkbox")).toHaveCount(1);
    await expect(page.locator(".library-panel .count-pill")).toContainText(String(total));
    expect(offsets.has(10000)).toBe(true);
    await checkbox.check();
    await page.getByRole("button", { name: "Utiliser ce périmètre", exact: true }).click();
    await expect(page.getByTestId("scope-summary")).toContainText(lastName);
    await info.attach("catalogue-transport-double", { body: JSON.stringify({ total, last_offset_loaded: 10000, distinct_offsets: offsets.size, native_catalogue: false }), contentType: "application/json" });
  } finally { release?.(); }
});
