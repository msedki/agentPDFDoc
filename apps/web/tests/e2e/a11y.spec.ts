import { test, expect, type Page } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { readOnlyApi, watchPage } from "./guards";

// D06.11 : clavier, focus visible et labels sur l'API réelle, sans aucune écriture
// côté service. La seule requête d'écriture (Ctrl+Entrée) est interceptée et
// annulée dans le navigateur : ce point est un test UI isolé, pas une recherche réelle.
test.beforeEach(() => {
  test.skip(process.env.RAG_E2E_READONLY_ALLOWED !== "1", "Scénario GET seul planifié séparément ; NOT_RUN sans autorisation explicite.");
});

type Stop = { tag: string; role: string; name: string; id: string; className: string; focusVisible: boolean; indicator: boolean };
const focused = (page: Page) => page.evaluate((): Stop | null => {
  const element = document.activeElement as HTMLElement | null;
  if (!element || element === document.body) return null;
  const visible = (style: CSSStyleDeclaration) => style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0 || style.boxShadow !== "none";
  // Textarea et filtre masquent leur contour : le formulaire ou le label parent porte l'indicateur.
  const container = element.closest("form, label");
  return {
    tag: element.tagName.toLowerCase(), role: element.getAttribute("role") ?? "", id: element.id, className: element.getAttribute("class") ?? "",
    name: (element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 80),
    focusVisible: element.matches(":focus-visible"),
    indicator: visible(getComputedStyle(element)) || Boolean(container && visible(getComputedStyle(container))),
  };
});
const scopeTrigger = (stop: Stop) => stop.tag === "button" && stop.className.split(/\s+/).includes("scope-trigger");

test("tab order, visible focus, separators, tabs and Ctrl+Enter work from the keyboard", async ({ page, browser }, info) => {
  test.setTimeout(180000);
  const log = watchPage(page);
  const blocked: string[] = [];
  await readOnlyApi(page, blocked);
  await monitorBrowser(browser, "a11y-start", info);
  await page.goto("/workspace/");
  await expect(page.getByRole("heading", { name: "Analyse", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Arborescence documentaire" })).toBeVisible();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const stops: Stop[] = [];
  for (let press = 0; press < 300; press++) {
    await page.keyboard.press("Tab");
    const stop = await focused(page);
    if (!stop) continue;
    stops.push(stop);
    // Le déclencheur de périmètre n'a pas d'id : il est reconnu par sa classe.
    if (scopeTrigger(stop) || ["question-input", "analysis-tabpanel"].includes(stop.id) || stop.role === "separator" || stop.role === "tab") {
      await page.screenshot({ path: info.outputPath(`focus-${String(stops.length).padStart(3, "0")}-${stop.role || stop.tag}.png`) });
    }
    if (stop.id === "question-input") break;
  }
  await info.attach("keyboard-tab-order", { body: Buffer.from(JSON.stringify(stops, null, 2)), contentType: "application/json" });
  const position = (predicate: (stop: Stop) => boolean, label: string) => {
    const index = stops.findIndex(predicate);
    expect(index, `${label} absent de l'ordre de tabulation`).toBeGreaterThanOrEqual(0);
    return index;
  };
  const order = [
    position(stop => stop.tag === "button" && stop.name.startsWith("Suivi"), "Suivi"),
    position(stop => stop.name === "Replier la bibliothèque", "repli bibliothèque"),
    position(stop => stop.name === "Replier l'analyse", "repli analyse"),
    position(stop => scopeTrigger(stop) && stop.name.startsWith("Périmètre"), "périmètre"),
    position(stop => stop.name === "Filtrer les fichiers", "filtre"),
    position(stop => stop.role === "separator" && stop.name === "Largeur de la bibliothèque", "séparateur bibliothèque"),
    position(stop => stop.role === "separator" && stop.name === "Largeur de l'analyse", "séparateur analyse"),
    position(stop => stop.role === "tab", "onglet"),
    position(stop => stop.id === "analysis-tabpanel", "panneau d'onglet"),
    position(stop => stop.id === "question-input", "question"),
  ];
  expect(order).toEqual([...order].sort((a, b) => a - b));
  expect(stops.filter(stop => stop.role === "tab").map(stop => stop.name), "tabIndex roving : un seul onglet dans la tabulation").toEqual(["Question"]);
  expect(stops.filter(stop => !stop.focusVisible || !stop.indicator), "chaque arrêt clavier montre un indicateur de focus").toEqual([]);

  // Même borne que workspace.tsx : largeur 16-36 %, flèche vers le panneau central = élargir.
  const clamp = (value: number) => Math.min(36, Math.max(16, value));
  for (const [name, grow, shrink] of [["Largeur de la bibliothèque", "ArrowRight", "ArrowLeft"], ["Largeur de l'analyse", "ArrowLeft", "ArrowRight"]] as const) {
    const separator = page.getByRole("separator", { name, exact: true });
    await separator.focus();
    const grown = clamp(Number(await separator.getAttribute("aria-valuenow")) + 1);
    await page.keyboard.press(grow);
    await expect(separator).toHaveAttribute("aria-valuenow", String(grown));
    await page.screenshot({ path: info.outputPath(`separator-${grow}-${name.replace(/\W+/g, "-")}.png`) });
    await page.keyboard.press(shrink);
    await expect(separator).toHaveAttribute("aria-valuenow", String(clamp(grown - 1)));
  }

  const tabpanel = page.getByRole("tabpanel");
  const expectTab = async (name: string, id: string) => {
    const tab = page.getByRole("tab", { name, exact: true });
    await expect(tab).toBeFocused();
    await expect(tab).toHaveAttribute("aria-selected", "true");
    await expect(tab).toHaveAttribute("tabindex", "0");
    await expect(tabpanel).toHaveAttribute("aria-labelledby", `analysis-tab-${id}`);
    await expect(page.getByRole("tab", { selected: false })).toHaveCount(2);
    for (const other of await page.getByRole("tab", { selected: false }).all()) await expect(other).toHaveAttribute("tabindex", "-1");
  };
  await page.getByRole("tab", { name: "Question", exact: true }).focus();
  for (const [key, name, id] of [["ArrowRight", "Recherche", "search"], ["ArrowRight", "Comparer", "comparison"], ["ArrowRight", "Question", "question"], ["ArrowLeft", "Comparer", "comparison"], ["Home", "Question", "question"], ["End", "Comparer", "comparison"], ["ArrowLeft", "Recherche", "search"]] as const) {
    await page.keyboard.press(key);
    await expectTab(name, id);
  }
  await page.screenshot({ path: info.outputPath("tabs-keyboard-search.png") });

  const composer = page.getByLabel("Votre recherche");
  await composer.focus();
  await page.keyboard.press("Control+Enter");
  expect(blocked, "Ctrl+Entrée sur un champ vide n'envoie rien").toEqual([]);
  await composer.fill("DA-P01 pression nominale");
  const intercepted = page.waitForRequest(request => request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/search");
  await page.keyboard.press("Control+Enter");
  expect((await intercepted).postDataJSON()).toMatchObject({ question: "DA-P01 pression nominale", scope: { kind: "library" } });
  await expect(page.locator(".composer-area [role=alert]")).toBeVisible();
  await page.screenshot({ path: info.outputPath("ctrl-enter-intercepted-search.png") });
  expect(blocked).toEqual(["POST /api/v1/search"]);
  await info.attach("keyboard-scenario-limits", { body: Buffer.from(JSON.stringify({ viewport: page.viewportSize(), blocked_before_service: blocked, mutations_seen_by_browser: log.mutations, interpretation: "Ctrl+Entrée prouve la soumission clavier ; la requête interceptée n'est ni une recherche réelle ni une réponse." }, null, 2)), contentType: "application/json" });
  await monitorBrowser(browser, "a11y-end", info);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
});
