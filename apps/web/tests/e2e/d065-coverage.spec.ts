/**
 * R26-ANC-01 — D06.5 borné : couverture du surlignage des passages ouverts par « Ouvrir le passage », sans modèle.
 *
 * Étape 1 (RAG_E2E_D065_FREEZE=1) : importe au besoin QLONG et les fixtures DEV DA-P01…DA-P07 sur l'instance isolée,
 * lit les blocs publiés de chaque page et écrit le jeu figé (RAG_E2E_D065_SET) selon les règles ci-dessous, sans
 * aucune mesure. Le lanceur en calcule l'empreinte avant l'étape 2.
 * Étape 2 (RAG_E2E_D065_SET + RAG_E2E_D065_SET_SHA256) : pour chaque bloc compté, recherche dans le document avec
 * le début du texte du bloc, ouvre par « Ouvrir le passage » la carte dont la source contient ce bloc, contrôle la
 * page affichée et mesure la couverture par l'oracle de Q10 (citation-coverage.ts).
 *
 * Règles figées avant exécution (recopiées dans le jeu) :
 * - compté : bloc natif (page `native`, méthode du bloc ni `ocr` ni `mixed`), avec texte et boîte ;
 * - déclaré à part, jamais compté réussi : bloc OCR ou mixte, page non native ; tableau (type ou précision `table`,
 *   ordre de la couche texte inexploitable par l'oracle) ; texte identique à celui d'un autre bloc de la page
 *   (oracle ambigu) ; bloc sans texte ou sans boîte ;
 * - région couverte = oracle `passed` pour le texte complet du bloc ; page exacte = numéro de page affiché ;
 * - bloc compté non retrouvé par la recherche ou non ouvert = région non couverte et page non exacte ;
 * - seuils DoD : régions couvertes ≥ 95 %, pages exactes 100 %.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { measureCitationCoverage, type CitationCoverageResult } from "./citation-coverage";
import { fixtureAtPath, importPublished, readOnlyApi, watchPage } from "./guards";
import { fixture } from "./lifecycle-target";

const RULES_VERSION = "d065-r26-v1";
const documents = [
  { key: "QLONG", path: "qualification-v2.1/layouts/long-document-14p.pdf" },
  ...Array.from({ length: 7 }, (_, index) => ({ key: `development-DA-P0${index + 1}`, path: "" })),
];
type ApiBlock = { id: string; page_index: number; type?: string; kind?: string; text: string; raw_text?: string; bbox?: number[] | null; precision: string; metadata?: { extraction_method?: string } };
type FrozenBlock = { document: string; document_id: string; version_id: string; page_index: number; block_id: string; text: string; text_sha256: string; status: "compté" | "ocr" | "tableau" | "ambigu" | "sans-texte" };
type FrozenSet = { rules: string; generated_at: string; documents: { key: string; name: string; document_id: string; version_id: string; sha256: string; pages: number }[]; blocks: FrozenBlock[] };

const normalize = (text: string) => text.replace(/\s+/gu, " ").trim();
const sha = (text: string) => createHash("sha256").update(text, "utf8").digest("hex");

test("D06.5 étape 1 : jeu figé des blocs, sans mesure", async ({ page, request }, info) => {
  test.setTimeout(3_600_000);
  test.skip(process.env.RAG_E2E_D065_FREEZE !== "1" || process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Gel du jeu D06.5 sur instance isolée seulement.");
  const target = process.env.RAG_E2E_D065_SET;
  if (!target) throw new Error("RAG_E2E_D065_SET doit désigner le fichier du jeu figé.");
  const frozen: FrozenSet = { rules: RULES_VERSION, generated_at: new Date().toISOString(), documents: [], blocks: [] };
  for (const entry of documents) {
    const input = entry.path ? fixtureAtPath(entry.path) : fixture(entry.key);
    if (!input) throw new Error(`Fixture ${entry.key} absente du manifeste et de son sidecar.`);
    const tree = await (await request.get("/api/v1/library/tree")).json() as { documents: { id: string; name: string; state: string; sha256: string }[] };
    let documentId = tree.documents.find(document => document.sha256 === input.sha256 && ["ready", "ready_partial"].includes(document.state))?.id;
    if (!documentId) documentId = (await importPublished(page, request, input, info, ["ready", "ready_partial"])).documentId;
    const detail = await (await request.get(`/api/v1/documents/${encodeURIComponent(documentId)}`)).json() as { name: string; page_count: number; active_version_id?: string; version_id?: string };
    const versionId = String(detail.active_version_id ?? detail.version_id);
    frozen.documents.push({ key: entry.key, name: detail.name, document_id: documentId, version_id: versionId, sha256: input.sha256, pages: detail.page_count });
    for (let pageIndex = 0; pageIndex < detail.page_count; pageIndex++) {
      const response = await request.get(`/api/v1/versions/${encodeURIComponent(versionId)}/pages/${pageIndex}/blocks`);
      expect(response.status()).toBe(200);
      const body = await response.json() as { page: { extraction_state?: string }; blocks: ApiBlock[] };
      const texts = body.blocks.map(block => normalize(block.raw_text ?? block.text ?? ""));
      for (const [index, block] of body.blocks.entries()) {
        const text = block.raw_text ?? block.text ?? "";
        const method = block.metadata?.extraction_method;
        const status: FrozenBlock["status"] = body.page.extraction_state !== "native" || method === "ocr" || method === "mixed" ? "ocr"
          : block.type === "table" || block.kind === "table" || block.precision === "table" ? "tableau"
          : !normalize(text) || !Array.isArray(block.bbox) || block.bbox.length !== 4 ? "sans-texte"
          : texts.filter((other, position) => position !== index && other === texts[index]).length ? "ambigu" : "compté";
        frozen.blocks.push({ document: entry.key, document_id: documentId, version_id: versionId, page_index: pageIndex, block_id: block.id, text, text_sha256: sha(text), status });
      }
    }
  }
  writeFileSync(target, JSON.stringify(frozen, null, 2) + "\n");
  const counts = Object.fromEntries(["compté", "ocr", "tableau", "ambigu", "sans-texte"].map(status => [status, frozen.blocks.filter(block => block.status === status).length]));
  await info.attach("d065-frozen-counts", { body: Buffer.from(JSON.stringify({ target, counts, documents: frozen.documents }, null, 2)), contentType: "application/json" });
});

test("D06.5 étape 2 : régions couvertes et pages exactes sur le jeu figé", async ({ page }, info) => {
  test.setTimeout(3_600_000);
  const setPath = process.env.RAG_E2E_D065_SET, setSha = process.env.RAG_E2E_D065_SET_SHA256;
  test.skip(process.env.RAG_E2E_D065_FREEZE === "1" || !setPath || !setSha, "Jeu D06.5 figé et son empreinte requis.");
  const bytes = readFileSync(setPath!);
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(setSha);
  const frozen = JSON.parse(bytes.toString("utf8")) as FrozenSet;
  expect(frozen.rules).toBe(RULES_VERSION);
  const counted = frozen.blocks.filter(block => block.status === "compté");
  const deadline = Date.now() + Number(process.env.RAG_E2E_D065_BUDGET_MS ?? 3_000_000);
  await page.setViewportSize({ width: 1366, height: 768 });
  const log = watchPage(page), blocked: string[] = [];
  await readOnlyApi(page, blocked);
  // Seul POST admis : la recherche ; readOnlyApi bloque toute autre écriture.
  await page.route("**/api/v1/search", route => route.continue());
  const outcomes: { document: string; page_index: number; block_id: string; opened: boolean; page_exact: boolean; covered: boolean; reason?: string; result_rank?: number; geometry?: CitationCoverageResult }[] = [];
  let currentDocument: string | null = null;
  let stoppedByBudget = false;
  try {
    for (const block of counted) {
      if (Date.now() > deadline) { stoppedByBudget = true; break; }
      const name = frozen.documents.find(document => document.document_id === block.document_id)!.name;
      if (currentDocument !== block.document_id) {
        await page.goto("/workspace/");
        for (const box of await page.getByLabel(/^Sélectionner /).all()) if (await box.isChecked()) await box.uncheck();
        await page.getByLabel(`Sélectionner ${name}`).check();
        await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
        await page.getByRole("tab", { name: "Recherche", exact: true }).click();
        currentDocument = block.document_id;
      }
      const outcome: (typeof outcomes)[number] = { document: block.document, page_index: block.page_index, block_id: block.block_id, opened: false, page_exact: false, covered: false };
      outcomes.push(outcome);
      const query = normalize(block.text).split(" ").slice(0, 12).join(" ").slice(0, 200);
      await page.getByLabel("Votre recherche").fill(query);
      const searched = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
      await page.getByRole("button", { name: "Rechercher", exact: true }).click();
      const response = await searched;
      if (response.status() !== 200) { outcome.reason = `search_http_${response.status()}`; continue; }
      const results = (await response.json()).results as ({ source?: { block_ids?: string[]; blocks?: { id: string }[]; version_id?: string } } & { block_ids?: string[]; blocks?: { id: string }[]; version_id?: string })[];
      const sources = results.map(result => result.source ?? result).filter(source => source.version_id);
      const rank = sources.findIndex(source => (source.block_ids ?? source.blocks?.map(item => item.id) ?? []).includes(block.block_id));
      if (rank < 0) { outcome.reason = "block_not_in_results"; continue; }
      outcome.result_rank = rank;
      await page.locator(".search-results").getByTestId("source-card").nth(rank).getByRole("button", { name: "Ouvrir le passage" }).click();
      outcome.opened = true;
      try {
        await expect(page.getByLabel("Numéro de page")).toHaveValue(String(block.page_index + 1), { timeout: 15_000 });
        outcome.page_exact = true;
      } catch { outcome.reason = "page_not_exact"; continue; }
      try {
        await expect.poll(async () => {
          outcome.geometry = await page.evaluate(measureCitationCoverage, { pageIndex: block.page_index, passages: [{ id: block.block_id, text: block.text }] });
          return outcome.geometry.passed;
        }, { timeout: 15_000 }).toBe(true);
        outcome.covered = true;
      } catch { outcome.reason = outcome.geometry?.passages[0]?.reason ?? outcome.geometry?.reason ?? "coverage_timeout"; }
    }
  } finally {
    const measured = outcomes.length;
    const covered = outcomes.filter(outcome => outcome.covered).length;
    const exact = outcomes.filter(outcome => outcome.page_exact).length;
    const declared = Object.fromEntries(["ocr", "tableau", "ambigu", "sans-texte"].map(status => [status, frozen.blocks.filter(block => block.status === status).length]));
    const summary = { rules: RULES_VERSION, set_sha256: setSha, denominator: counted.length, measured, stopped_by_budget: stoppedByBudget,
      regions_covered: covered, regions_rate: measured ? covered / counted.length : 0, pages_exact: exact, pages_rate: measured ? exact / counted.length : 0,
      declared_apart: declared, failures: outcomes.filter(outcome => !outcome.covered || !outcome.page_exact).map(outcome => ({ ...outcome, geometry: undefined })),
      network: { mutations: log.mutations.length, external: log.external, pageErrors: log.pageErrors }, blocked };
    await info.attach("d065-summary", { body: Buffer.from(JSON.stringify(summary, null, 2)), contentType: "application/json" });
    await info.attach("d065-outcomes", { body: Buffer.from(JSON.stringify(outcomes, null, 2)), contentType: "application/json" });
  }
  expect(blocked).toEqual([]);
  expect(log.external).toEqual([]);
  expect(log.pageErrors).toEqual([]);
  // Seuils DoD D06.5, sur le dénominateur figé (un bloc non mesuré compte comme non couvert).
  expect(outcomes.filter(outcome => outcome.covered).length / counted.length).toBeGreaterThanOrEqual(0.95);
  expect(outcomes.filter(outcome => outcome.page_exact).length).toBe(counted.length);
});
