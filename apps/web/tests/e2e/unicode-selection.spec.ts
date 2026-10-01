/**
 * D06.7 sur l'API réelle d'une instance isolée : sélection native dans la couche texte PDF.js de la fixture Unicode
 * (hors BMP, ligature, accent combinant, césure), puis aller-retour par l'API en points de code, avec hash source.
 *
 * Chaque cas doit aboutir à l'un des deux résultats admis : aller-retour exact (le texte rendu par l'API pour les
 * offsets envoyés est la sélection, espaces normalisés) ou refus explicite qui oriente vers la page ou le bloc.
 * Une correspondance silencieusement fausse fait échouer le test.
 */
import { test, expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

const fixtureName = "Unicode ligatures césures.pdf";
const fixturePath = fileURLToPath(new URL(`../../../../fixtures/qualification-v2.1/text/${fixtureName}`, import.meta.url));
const REFUSAL = "Cette sélection ne correspond pas de façon unique aux blocs extraits";

type Block = { id: string; raw_text: string; text: string; source_text_hash: string; extraction_revision_id: string };
type Outcome = "exact_round_trip" | "explicit_refusal";
type Case = { name: string; anchor: string; starts: string[]; end: string; expected: Outcome };

// Variantes de départ : forme source, puis forme que PDF.js peut produire en normalisant (ligature décomposée,
// accent composé). Les recherches commencent après l'ancre : « fi » existe aussi dans le titre (« fixture »).
// Attendu le 01/10 : la ligature est développée en « fi » par l'extraction (PDFium) comme par PDF.js, l'aller-retour
// porte donc sur la forme extraite et hachée. « ion » figure deux fois dans la page : la sélection est ambiguë.
const cases: Case[] = [
  { name: "hors BMP", anchor: "", starts: ["Selection A"], end: "\u{1F600}", expected: "exact_round_trip" },
  { name: "ligature", anchor: "\u{1F600}", starts: ["\u{FB01}", "fi"], end: "end.", expected: "exact_round_trip" },
  { name: "accent combinant", anchor: "\u{1F600}", starts: ["é end", "é end"], end: "end.", expected: "exact_round_trip" },
  { name: "césure", anchor: "", starts: ["con-"], end: "trole;", expected: "exact_round_trip" },
  { name: "ligne entière", anchor: "", starts: ["Selection A"], end: "end.", expected: "exact_round_trip" },
  { name: "ambiguïté", anchor: "", starts: ["ion"], end: "ion", expected: "explicit_refusal" },
];

const codePoints = (text: string) => Array.from(text).map(char => `U+${char.codePointAt(0)!.toString(16).toUpperCase().padStart(4, "0")}`);
const flat = (text: string) => text.replace(/\s+/gu, " ").trim();

/** Sélection DOM réelle entre deux marqueurs du texte rendu par PDF.js, puis relâchement de souris comme un utilisateur. */
async function selectBetween(page: Page, anchor: string, starts: string[], end: string): Promise<string | null> {
  return page.evaluate(({ anchor, starts, end }) => {
    const layer = document.querySelector('.pdf-page-slot[data-page-index="0"] .textLayer');
    if (!layer) return null;
    const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) nodes.push(node as Text);
    const whole = nodes.map(node => node.data).join("");
    const after = anchor ? whole.indexOf(anchor) : 0;
    if (after < 0) return null;
    const first = starts.map(start => whole.indexOf(start, after)).find(position => position >= 0) ?? -1;
    const last = first < 0 ? -1 : whole.indexOf(end, first);
    if (first < 0 || last < 0) return null;
    const locate = (offset: number) => {
      let consumed = 0;
      for (const node of nodes) {
        if (offset <= consumed + node.data.length) return { node, offset: offset - consumed };
        consumed += node.data.length;
      }
      return null;
    };
    const from = locate(first); const to = locate(last + end.length);
    if (!from || !to) return null;
    const range = document.createRange();
    range.setStart(from.node, from.offset);
    range.setEnd(to.node, to.offset);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    layer.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    return selection.toString();
  }, { anchor, starts, end });
}

test("native Unicode selection round-trips through the API in code points or is refused explicitly", async ({ page }, info) => {
  test.setTimeout(600000);
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Supervisor must confirm the API targets an authorized isolated store before fixture import.");
  await page.goto("/workspace/");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Importer des PDF", exact: true }).click();
  await (await chooser).setFiles(fixturePath);
  const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(fixtureName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
  await expect(documentButton).toContainText("Prêt", { timeout: 540000 });
  const tree = await (await page.request.get("/api/v1/library/tree")).json();
  const document = tree.documents.find((item: { name: string }) => item.name === fixtureName);
  const versionId = document.active_version_id ?? document.version_id;
  const blocks: Block[] = (await (await page.request.get(`/api/v1/versions/${versionId}/pages/0/blocks`)).json()).blocks;
  const backend = blocks.map(block => ({ id: block.id, code_points: codePoints(block.raw_text), hash: block.source_text_hash }));
  await documentButton.click();
  await expect(page.locator('.pdf-page-slot[data-page-index="0"] .textLayer span').first()).toBeAttached();
  const layerText = await page.locator('.pdf-page-slot[data-page-index="0"] .textLayer').evaluate(layer => layer.textContent ?? "");
  const outcomes = [];
  for (const item of cases) {
    const selected = await selectBetween(page, item.anchor, item.starts, item.end);
    if (selected === null) {
      outcomes.push({ case: item.name, outcome: "absent_from_text_layer", markers: item.starts.map(codePoints) });
      continue;
    }
    const action = page.locator(".selection-action");
    const refusal = page.locator('.pdf-page-slot[data-page-index="0"] [role="status"]').filter({ hasText: REFUSAL });
    // Le panneau d'une sélection précédente reste affiché : on attend l'état propre à cette sélection.
    if (item.expected === "explicit_refusal") {
      await expect(refusal).toBeVisible();
      await expect(action).toBeHidden();
    } else {
      await expect(action).toContainText(flat(selected).slice(0, 12));
    }
    if (await refusal.isVisible()) {
      outcomes.push({ case: item.name, outcome: "explicit_refusal", selected_code_points: codePoints(selected) });
      continue;
    }
    await action.getByRole("button", { name: "Analyser la sélection", exact: true }).click();
    await expect(page.getByTestId("scope-summary")).toContainText("Texte sélectionné");
    await page.getByRole("tab", { name: "Recherche", exact: true }).click();
    await page.getByLabel("Votre recherche").fill("selection");
    const request = page.waitForRequest(candidate => candidate.method() === "POST" && candidate.url().endsWith("/api/v1/search"));
    const response = page.waitForResponse(candidate => candidate.request().method() === "POST" && candidate.url().endsWith("/api/v1/search"));
    await page.getByRole("button", { name: "Rechercher", exact: true }).click();
    const spans = (await request).postDataJSON().scope.spans as { blockId: string; blockTextSha256: string; offsetUnit: string; startOffset: number; endOffset: number }[];
    const answer = await response;
    expect(answer.status()).toBe(200);
    const returned = ((await answer.json()).results as { text: string }[]).map(result => result.text).join(" ");
    const expected = spans.map(span => {
      const block = blocks.find(candidate => candidate.id === span.blockId)!;
      expect(span.offsetUnit).toBe("unicode_code_point");
      expect(span.blockTextSha256).toBe(block.source_text_hash);
      return Array.from(block.raw_text).slice(span.startOffset, span.endOffset).join("");
    }).join(" ");
    const exact = flat(returned) === flat(expected) && flat(expected) === flat(selected);
    outcomes.push({ case: item.name, outcome: exact ? "exact_round_trip" : "mismatch", spans, selected_code_points: codePoints(selected), returned_code_points: codePoints(returned) });
  }
  await page.screenshot({ path: info.outputPath("unicode-selection.png"), fullPage: true });
  await info.attach("unicode-selection-outcomes", {
    body: Buffer.from(JSON.stringify({ backend_blocks: backend, text_layer_code_points: codePoints(layerText), outcomes }, null, 2)),
    contentType: "application/json",
  });
  expect(outcomes.map(outcome => [outcome.case, outcome.outcome])).toEqual(cases.map(item => [item.name, item.expected]));
});
