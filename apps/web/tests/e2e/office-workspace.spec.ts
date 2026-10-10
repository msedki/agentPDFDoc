/** R28 actual API journey, authorized synthetic OOXML/PDF only. No intercepted API or model response. */
import { test, expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync, realpathSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, relative } from "node:path";
import { withImportPriority } from "./import-priority.ts";
import { waitJob } from "./lifecycle-target";
import { watchPage } from "./guards";
import { doneEvent, registeredAnswerCitation } from "./answer-citations";
import { e2eTarget } from "./target";
import { waitOriginalBitmap } from "./canvas-paint";
import { objects } from "../../src/lib/office-structure";
import type { DocumentDetail, DocumentFormat, OfficeBlocks, OfficeCells, OfficeRepresentation, Scope, Source } from "../../src/lib/types";

type Fixture = { key: string; path: string; sha256: string; format: DocumentFormat; expected_text: string; sheet_name?: string; cell_range?: string; expected_cell?: string; expected_images?: number; expected_tables?: number; expected_image_alt?: string };
type Published = { fixture: Fixture; document: DocumentDetail; versionId: string; revision: string; unitId: string };
const published = new Map<DocumentFormat, Published>();
test.describe.configure({ mode: "serial" });
test.afterEach(async ({ page }) => {
  const cancel = page.getByRole("button", { name: "Annuler", exact: true });
  if (await cancel.isVisible()) {
    await cancel.click();
    await expect(cancel).toBeHidden({ timeout: 15000 });
  }
});

function fixtures() {
  const file = process.env.RAG_E2E_OFFICE_FIXTURES;
  if (!file) throw new Error("A reviewed RAG_E2E_OFFICE_FIXTURES manifest is required; no default corpus.");
  const manifestPath = realpathSync(file);
  const value = JSON.parse(readFileSync(manifestPath, "utf8")) as { schema_version: number; fixtures: Fixture[] };
  expect(value.schema_version).toBe(1); expect(value.fixtures.map(item => item.format).sort()).toEqual(["docx", "pdf", "xlsx"]);
  for (const item of value.fixtures) {
    const path = realpathSync(item.path); const inside = relative(dirname(manifestPath), path);
    expect(!isAbsolute(inside) && inside !== ".." && !inside.startsWith("../") && !inside.startsWith("..\\")).toBe(true);
    expect(createHash("sha256").update(readFileSync(path)).digest("hex")).toBe(item.sha256);
    expect(item.expected_text).toBeTruthy();
  }
  return value.fixtures;
}

async function open(page: Page, item: Published) {
  await page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: basename(item.fixture.path), exact: false }).click();
}
async function capture(page: Page, info: TestInfo, name: string) {
  await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: false });
}
async function desktopCaptures(page: Page, info: TestInfo, name: string) {
  for (const width of [1366, 1920]) {
    await page.setViewportSize({ width, height: 768 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await capture(page, info, `${name}-${width}`);
  }
  await page.setViewportSize({ width: 1366, height: 768 });
}

async function reusePublished(request: APIRequestContext, info: TestInfo, sourceFiles: Fixture[], file: string) {
  const bytes = readFileSync(file); const digest = createHash("sha256").update(bytes).digest("hex");
  expect(digest, "Replay requires the exact prior real publication receipt").toBe(process.env.RAG_E2E_PUBLISHED_BINDINGS_SHA256);
  const bindings = JSON.parse(bytes.toString()) as { format: DocumentFormat; fixture_sha256: string; document_id: string; version_id: string; extraction_revision_id: string | null; unit_id: string | null }[];
  expect(bindings.map(item => item.format).sort()).toEqual(["docx", "pdf", "xlsx"]);
  for (const binding of bindings) {
    const fixture = sourceFiles.find(item => item.sha256 === binding.fixture_sha256 && item.format === binding.format)!; expect(fixture).toBeTruthy();
    const response = await request.get(`/api/v1/documents/${binding.document_id}`); expect(response.status()).toBe(200); const document = await response.json() as DocumentDetail;
    const version = document.versions.find(item => item.id === binding.version_id)!; expect(version).toBeTruthy(); expect(version.sha256).toBe(fixture.sha256); expect(version.format).toBe(binding.format);
    if (binding.format !== "pdf") {
      const response = await request.get(`/api/v1/versions/${binding.version_id}/representation?extraction_revision_id=${binding.extraction_revision_id}&cursor=0&limit=50`); expect(response.status()).toBe(200);
      const representation = await response.json() as OfficeRepresentation; expect(representation.extraction_revision_id).toBe(binding.extraction_revision_id); expect(representation.units.some(unit => unit.id === binding.unit_id)).toBe(true);
    }
    published.set(binding.format, { fixture, document, versionId: binding.version_id, revision: binding.extraction_revision_id ?? "", unitId: binding.unit_id ?? "" });
  }
  await info.attach("prior-real-import-publication-reused", { body: Buffer.from(JSON.stringify({ sha256: digest, imports_replayed: 0, bindings })), contentType: "application/json" });
}

test("actual mixed PDF/DOCX/XLSX import, structured readers and exact scoped search", async ({ page, request }, info) => {
  test.setTimeout(1_200_000);
  const sourceFiles = fixtures(); const log = watchPage(page);
  const priorBindings = process.env.RAG_E2E_PUBLISHED_BINDINGS;
  await page.goto("/workspace/");
  if (priorBindings) await reusePublished(request, info, sourceFiles, priorBindings);
  else {
    expect(process.env.RAG_E2E_IMPORT_ALLOWED, "Supervisor must authorize this isolated store").toBe("1");
    const initial = await request.get("/api/v1/library/tree"); expect(initial.status()).toBe(200); expect((await initial.json()).documents).toEqual([]);
    await withImportPriority(page, request, info, async () => {
    const chooser = page.waitForEvent("filechooser");
    const imported = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/documents/import"));
    await page.getByRole("button", { name: "Importer des documents", exact: true }).click();
    await (await chooser).setFiles(sourceFiles.map(item => item.path));
    const response = await imported; expect(response.status()).toBe(202);
    const body = await response.json() as { imports: { document_id: string; version_id: string; job_id: string }[]; errors?: unknown[] };
    expect(body.imports).toHaveLength(3); expect(body.errors ?? []).toEqual([]);
    await info.attach("actual-mixed-import", { body: Buffer.from(JSON.stringify(body)), contentType: "application/json" });
    for (const item of body.imports) {
      const job = await waitJob(request, e2eTarget().baseURL, item.job_id, info);
      expect(["ready", "ready_partial"]).toContain(job.state);
      const detail = await request.get(`/api/v1/documents/${item.document_id}`); expect(detail.status()).toBe(200);
      const document = await detail.json() as DocumentDetail;
      const version = document.versions.find(version => version.id === item.version_id)!;
      const fixture = sourceFiles.find(fixture => fixture.sha256 === version.sha256)!;
      expect(fixture, "Exact immutable fixture digest must identify each returned version").toBeTruthy();
      expect(version.format).toBe(fixture.format);
      if (fixture.format !== "pdf") {
        expect(version.page_count).toBeNull();
        const response = await request.get(`/api/v1/versions/${version.id}/representation?cursor=0&limit=50`); expect(response.status()).toBe(200);
        const representation = await response.json() as OfficeRepresentation;
        expect(representation.version_id).toBe(version.id); expect(representation.format).toBe(fixture.format);
        const unit = fixture.sheet_name ? representation.units.find(unit => unit.title === fixture.sheet_name) : representation.units.find(unit => unit.part === "word/document.xml");
        expect(unit).toBeTruthy(); expect(representation.extraction_revision_id).toBeTruthy();
        published.set(fixture.format, { fixture, document, versionId: version.id, revision: representation.extraction_revision_id, unitId: unit!.id });
      } else published.set("pdf", { fixture, document, versionId: version.id, revision: "", unitId: "" });
    }
    writeFileSync(info.outputPath("actual-published-office-bindings.json"), JSON.stringify([...published.values()].map(item => ({ format: item.fixture.format, fixture_sha256: item.fixture.sha256, document_id: item.document.id, version_id: item.versionId, extraction_revision_id: item.revision || null, unit_id: item.unitId || null })), null, 2), { mode: 0o600 });
    });
    await expect(page.locator(".library-notice").first()).toContainText("3 documents reçus par le service");
  }
  const word = published.get("docx")!, excel = published.get("xlsx")!, pdf = published.get("pdf")!;
  await open(page, word);
  await expect(page.getByTestId("office-reader")).toBeVisible();
  await expect(page.locator(".office-source-text").filter({ hasText: word.fixture.expected_text })).toBeVisible();
  await expect(page.getByLabel("Numéro de page")).toHaveCount(0);
  await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
  const blocksResponse = await request.get(`/api/v1/versions/${word.versionId}/units/${encodeURIComponent(word.unitId)}/blocks?extraction_revision_id=${word.revision}&cursor=0&limit=50`);
  expect(blocksResponse.status()).toBe(200); const blocks = await blocksResponse.json() as OfficeBlocks;
  const paragraph = blocks.blocks.find(block => block.text.includes(word.fixture.expected_text))!;
  expect(paragraph.page_index).toBeNull(); expect(paragraph.locator?.kind).toBe("docx_element");
  const sourceText = paragraph.source_text ?? paragraph.raw_text ?? paragraph.text;
  expect(createHash("sha256").update(sourceText).digest("hex")).toBe(paragraph.source_text_hash);
  await expect(page.locator(".office-table-block table").first()).toBeVisible();
  await expect(page.locator(".office-table-block table")).toHaveCount(word.fixture.expected_tables!);
  await expect(page.locator(".office-table-block th").first()).toBeVisible();
  const sourceMerged = blocks.blocks.flatMap(block => objects(block.structure?.rows).flatMap(row => objects(row.cells))).filter(cell => typeof cell.column_span === "number" && cell.column_span > 1);
  expect(sourceMerged).toHaveLength(1); expect(sourceMerged[0].column_span).toBe(3);
  await expect(page.locator('.office-table-block [colspan="3"]').first()).toContainText(String(sourceMerged[0].text));
  const images = page.locator(".office-figure img");
  expect(blocks.blocks.some(block => Array.isArray(block.structure?.images) && block.structure.images.length), "Reviewed DOCX fixture must exercise a real package raster").toBe(true);
  await expect(images.first()).toBeVisible();
  await expect(images).toHaveCount(word.fixture.expected_images!);
  await expect(images.first()).toHaveAttribute("alt", word.fixture.expected_image_alt!);
  await expect.poll(() => images.first().evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  expect(await images.first().getAttribute("src")).toContain(`/api/v1/versions/${word.versionId}/assets/`);
  await images.first().scrollIntoViewIfNeeded(); await capture(page, info, "office-docx-source-raster");
  await page.locator(`[data-office-block="${paragraph.id}"]`).getByRole("button", { name: "Analyser cet élément", exact: true }).click();
  await page.getByRole("tab", { name: "Recherche", exact: true }).click();
  await page.getByLabel("Votre recherche").fill("CCU-21 tension nominale");
  const searchedWord = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const wordResponse = await searchedWord; expect(wordResponse.status()).toBe(200);
  const wordScope = wordResponse.request().postDataJSON().scope as Extract<Scope, { kind: "selection" }>;
  expect(wordScope.kind).toBe("selection"); expect(wordScope.spans[0]).toMatchObject({ extractionRevisionId: word.revision, blockId: paragraph.id, blockTextSha256: paragraph.source_text_hash, offsetUnit: "unicode_code_point" });
  await expect(page.getByTestId("source-card").first()).toContainText("Élément source");
  await page.getByTestId("source-card").first().getByRole("button", { name: "Ouvrir le passage", exact: true }).click();
  await expect(page.locator(".office-element.is-cited").first()).toBeVisible();
  await desktopCaptures(page, info, "office-docx-source");
  await open(page, excel);
  await expect(page.getByRole("combobox", { name: "Feuille", exact: true })).toHaveValue(excel.unitId);
  await expect(page.locator(".office-spreadsheet tbody tr")).toHaveCount(50);
  expect(await page.locator(".office-cell").count()).toBe(1000);
  const cell = page.locator(`.office-cell[data-address="${excel.fixture.expected_cell}"]`);
  await expect(cell).toContainText(excel.fixture.expected_text); await cell.click(); await cell.press("ArrowRight");
  await expect(page.locator('.office-cell[data-address="C2"]')).toBeFocused();
  await page.getByLabel("Adresse ou plage", { exact: true }).fill(excel.fixture.cell_range!);
  await page.getByRole("button", { name: "Afficher", exact: true }).click();
  await page.getByRole("button", { name: "Analyser cette plage", exact: true }).click();
  const rangeResponse = await request.get(`/api/v1/versions/${excel.versionId}/sheets/${encodeURIComponent(excel.unitId)}/cells?extraction_revision_id=${excel.revision}&row_start=1&row_end=3&column_start=1&column_end=2`);
  expect(rangeResponse.status()).toBe(200); const rangeCells = await rangeResponse.json() as OfficeCells;
  expect(rangeCells.bounds).toEqual({ row_start: 1, row_end: 3, column_start: 1, column_end: 2 });
  await page.getByLabel("Votre recherche").fill("CCU-21 tension");
  const searchedExcel = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  const excelResponse = await searchedExcel; expect(excelResponse.status()).toBe(200);
  expect(excelResponse.request().postDataJSON().scope).toEqual({ kind: "cell_range", versionId: excel.versionId, extractionRevisionId: excel.revision, sheetId: excel.unitId, rowStart: 1, rowEnd: 3, columnStart: 1, columnEnd: 2 });
  await expect(page.getByTestId("source-card").first()).toContainText(/Cellule source|Plage source/);
  await desktopCaptures(page, info, "office-xlsx-range");
  await open(page, pdf); await expect(page.locator("canvas").first()).toBeVisible();
  await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
  await page.getByRole("button", { name: "Pivoter de 90 degrés" }).click();
  await page.getByRole("button", { name: "Augmenter le zoom" }).click();
  await waitOriginalBitmap(page, info, "office-preserved-pdf-bitmap", { pageIndex: 0, anchorSelector: ".textLayer span", viewport: { width: 1366, height: 768 }, zoom: (await page.locator(".zoom-label").innerText()) });
  expect(await page.locator("canvas").count()).toBeLessThanOrEqual(5);
  await expect(page.getByTestId("scope-summary")).toContainText(excel.fixture.cell_range!);
  await capture(page, info, "office-pdf-preserved");
  expect(log.external).toEqual([]); expect(log.pageErrors).toEqual([]);
  await info.attach("office-read-search-network", { body: Buffer.from(JSON.stringify(log)), contentType: "application/json" });
});

async function ask(page: Page, info: TestInfo, tab: string, question: string, mode: string) {
  await page.getByRole("tab", { name: tab, exact: true }).click(); await page.getByLabel("Votre question").fill(question);
  const submitted = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/queries"));
  await page.getByRole("button", { name: "Envoyer", exact: true }).click();
  const response = await submitted; expect(response.status()).toBe(202); expect(response.request().postDataJSON().mode).toBe(mode);
  const created = await response.json() as { query_id: string };
  try {
    await expect(page.locator(".query-status").last()).toContainText(/Réponse terminée|Réponse limitée|Échec|Réponse annulée|Réponse interrompue|Précision nécessaire|Preuves insuffisantes/, { timeout: 600000 });
    expect(await page.locator(".query-status").last().innerText()).toMatch(/Réponse terminée|Réponse limitée/);
    const replay = await page.request.get(`/api/v1/queries/${created.query_id}/events?after=0`); expect(replay.status()).toBe(200);
    const done = doneEvent(await replay.text()); expect(done?.status).toBe("done");
    const citation = await registeredAnswerCitation(page.getByTestId("query-turn").last(), done);
    return { queryId: created.query_id, citation, done };
  } finally {
    const replay = await page.request.get(`/api/v1/queries/${created.query_id}/events?after=0`);
    await info.attach(`actual-${mode}-${created.query_id}-sse`, { body: await replay.body(), contentType: "text/event-stream" });
  }
}

test("actual Office question/citations, critical analysis and mixed document comparison", async ({ page }, info) => {
  test.setTimeout(1_800_000);
  expect(process.env.RAG_E2E_GENERATION_ALLOWED, "Supervisor must authorize the single real CPU 4B engine").toBe("1");
  const word = published.get("docx")!, excel = published.get("xlsx")!, pdf = published.get("pdf")!;
  expect(word && excel && pdf, "Previous real import/reader journey must have completed").toBeTruthy();
  const log = watchPage(page); await page.goto("/workspace/");
  await page.getByRole("button", { name: "Suivi", exact: false }).click();
  await page.getByRole("button", { name: "Priorité aux questions", exact: true }).click(); await page.getByRole("button", { name: "Fermer le suivi", exact: true }).click();
  await page.getByLabel(`Sélectionner ${basename(word.fixture.path)}`).check(); await page.getByRole("button", { name: "Utiliser ce périmètre", exact: true }).click();
  const answer = await ask(page, info, "Question", "Quelle est la tension nominale du module CCU-21 ? Répondez en une phrase et citez sa source.", "question");
  const cited = page.waitForResponse(response => response.url().endsWith(`/api/v1/citations/${answer.queryId}/${answer.citation.sourceId}`));
  await answer.citation.button.click(); const actual = await cited; expect(actual.status()).toBe(200);
  const source = await actual.json() as Source;
  expect(source.format).toBe("docx"); expect(source.page_index).toBeNull(); expect(source.page_indices).toEqual([]);
  expect(source.version_id).toBe(word.versionId); expect(source.extraction_revision_id).toBe(word.revision);
  expect(source.locator?.kind).toBe("docx_element"); await expect(page.locator(".office-element.is-cited").first()).toBeVisible();
  await capture(page, info, "office-registered-docx-citation");
  await page.reload(); await expect(page.locator(".office-element.is-cited").first()).toBeVisible();
  await open(page, excel); await page.getByLabel("Adresse ou plage", { exact: true }).fill(excel.fixture.cell_range!); await page.getByRole("button", { name: "Afficher", exact: true }).click();
  await page.getByRole("button", { name: "Analyser cette plage", exact: true }).click();
  const critical = await ask(page, info, "Critique", "Indiquez la tension documentée pour CCU-21 et une limite des données disponibles, en deux phrases. Citez les cellules sources sans recalculer les formules.", "analysis");
  const excelCited = page.waitForResponse(response => response.url().endsWith(`/api/v1/citations/${critical.queryId}/${critical.citation.sourceId}`));
  await critical.citation.button.click(); const excelActual = await excelCited; expect(excelActual.status()).toBe(200);
  const excelSource = await excelActual.json() as Source; expect(excelSource.format).toBe("xlsx"); expect(excelSource.locator?.kind).toBe("xlsx_cells");
  expect(excelSource.extraction_revision_id).toBe(excel.revision); expect(excelSource.page_index).toBeNull();
  await expect(page.locator(".office-spreadsheet td.is-cited").first()).toBeVisible(); await capture(page, info, "office-registered-xlsx-citation");
  await page.getByRole("button", { name: "Retour au passage précédent", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Feuille", exact: true })).toHaveValue(excel.unitId);
  await page.getByLabel(`Sélectionner ${basename(word.fixture.path)}`).check(); await page.getByLabel(`Sélectionner ${basename(pdf.fixture.path)}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre", exact: true }).click();
  const comparison = await ask(page, info, "Comparer", "Comparez uniquement la tension nominale CCU-21 donnée par ces deux documents. Une phrase par document avec sa citation, puis indiquez s'ils concordent.", "comparison");
  const comparedVersions = new Set(comparison.done!.citations?.map(citation => citation.version_id));
  expect(comparedVersions.has(word.versionId), "Comparison must register a DOCX citation").toBe(true);
  expect(comparedVersions.has(pdf.versionId), "Comparison must register a PDF citation").toBe(true);
  await capture(page, info, "office-mixed-comparison");
  expect(log.external).toEqual([]); expect(log.pageErrors).toEqual([]);
  await info.attach("office-generation-network", { body: Buffer.from(JSON.stringify(log)), contentType: "application/json" });
});

test("persisted Office citation recovery and actual mixed comparison after interrupted runner", async ({ page, request }, info) => {
  test.setTimeout(600000);
  expect(process.env.RAG_E2E_GENERATION_ALLOWED).toBe("1");
  const bindingFile = process.env.RAG_E2E_PUBLISHED_BINDINGS!; expect(bindingFile).toBeTruthy();
  await reusePublished(request, info, fixtures(), bindingFile);
  const previousFile = process.env.RAG_E2E_PERSISTED_GENERATIONS!; expect(previousFile).toBeTruthy();
  const previousBytes = readFileSync(previousFile);
  expect(createHash("sha256").update(previousBytes).digest("hex")).toBe(process.env.RAG_E2E_PERSISTED_GENERATIONS_SHA256);
  const previous = JSON.parse(previousBytes.toString()) as { query_id: string; citations: { format: DocumentFormat }[] }[];
  expect(previous).toHaveLength(2);
  const log = watchPage(page);
  for (const item of previous) {
    const replay = await request.get(`/api/v1/queries/${item.query_id}/events?after=0`); expect(replay.status()).toBe(200);
    const done = doneEvent(await replay.text()); expect(done?.status).toBe("done");
    const sourceId = done?.text?.match(/\[(S\d+)\]/)?.[1]; expect(sourceId).toBeTruthy(); expect(done?.citations?.map(source => source.source_id)).toContain(sourceId);
    const response = await request.get(`/api/v1/citations/${item.query_id}/${sourceId}`); expect(response.status()).toBe(200);
    const source = await response.json() as Source; expect(source.format).toBe(item.citations[0].format); expect(source.page_index).toBeNull(); expect(source.page_indices).toEqual([]);
    const fixture = published.get(source.format!)!; expect(source.version_id).toBe(fixture.versionId); expect(source.extraction_revision_id).toBe(fixture.revision);
    await page.goto(`/workspace/?citation_query=${item.query_id}&citation_source=${sourceId}`);
    await expect(page.getByTestId("office-reader")).toBeVisible();
    if (source.format === "docx") await expect(page.locator(".office-element.is-cited").first()).toBeVisible();
    else {
      await expect(page.getByRole("combobox", { name: "Feuille", exact: true })).toHaveValue(fixture.unitId);
      await expect(page.locator(".office-spreadsheet td.is-cited").first()).toBeVisible();
      expect(source.locator?.kind).toBe("xlsx_cells");
    }
    await capture(page, info, `office-persisted-${source.format}-citation`);
    await info.attach(`actual-persisted-${source.format}-citation`, { body: Buffer.from(JSON.stringify({ query_id: item.query_id, source_id: sourceId, source, generation_replayed: false })), contentType: "application/json" });
  }
  const excel = published.get("xlsx")!, word = published.get("docx")!, pdf = published.get("pdf")!;
  const formulaResponse = await request.get(`/api/v1/versions/${excel.versionId}/sheets/${encodeURIComponent(excel.unitId)}/cells?extraction_revision_id=${excel.revision}&row_start=2&row_end=2&column_start=3&column_end=3`);
  expect(formulaResponse.status()).toBe(200); const formulaCells = await formulaResponse.json() as OfficeCells; const formula = formulaCells.cells[0];
  expect(formula.address).toBe("C2"); expect(formula.formula).toBeTruthy(); expect(formula.cached_present).toBe(false);
  await page.getByLabel("Adresse ou plage", { exact: true }).fill("C2"); await page.getByRole("button", { name: "Afficher", exact: true }).click();
  await page.locator('.office-cell[data-address="C2"]').click();
  await expect(page.locator(".office-cell-inspector")).toContainText(formula.formula!.raw_text!);
  await expect(page.locator(".office-cell-inspector")).toContainText("Cache absent");
  await capture(page, info, "office-xlsx-formula-cache-absent");
  await page.getByLabel(`Sélectionner ${basename(word.fixture.path)}`).check(); await page.getByLabel(`Sélectionner ${basename(pdf.fixture.path)}`).check();
  await page.getByRole("button", { name: "Utiliser ce périmètre", exact: true }).click();
  const comparison = await ask(page, info, "Comparer", "Comparez uniquement la tension nominale CCU-21 donnée par ces deux documents. Une phrase par document avec sa citation, puis indiquez s'ils concordent.", "comparison");
  const versions = new Set(comparison.done!.citations?.map(citation => citation.version_id)); expect(versions.has(word.versionId)).toBe(true); expect(versions.has(pdf.versionId)).toBe(true);
  await capture(page, info, "office-recovered-mixed-comparison");
  expect(log.external).toEqual([]); expect(log.pageErrors).toEqual([]);
  await info.attach("office-recovered-network", { body: Buffer.from(JSON.stringify(log)), contentType: "application/json" });
});

test("native Office provenance stays known in real search and persisted citation readers", async ({ page, request }, info) => {
  test.setTimeout(180000);
  expect(process.env.RAG_E2E_IMPORT_ALLOWED).toBe("0");
  expect(process.env.RAG_E2E_GENERATION_ALLOWED).toBe("0");
  const bindingFile = process.env.RAG_E2E_PUBLISHED_BINDINGS!; expect(bindingFile).toBeTruthy();
  await reusePublished(request, info, fixtures(), bindingFile);
  const previousFile = process.env.RAG_E2E_PERSISTED_GENERATIONS!; expect(previousFile).toBeTruthy();
  const previousBytes = readFileSync(previousFile);
  expect(createHash("sha256").update(previousBytes).digest("hex")).toBe(process.env.RAG_E2E_PERSISTED_GENERATIONS_SHA256);
  const previous = JSON.parse(previousBytes.toString()) as { query_id: string; citations: { format: DocumentFormat }[] }[];
  expect(previous).toHaveLength(2);
  const log = watchPage(page); const writes: string[] = [];
  page.on("request", request => {
    if (request.method() === "POST" && /\/api\/v1\/(queries|documents\/import)$/.test(new URL(request.url()).pathname)) writes.push(new URL(request.url()).pathname);
  });
  for (const item of previous) {
    const replay = await request.get(`/api/v1/queries/${item.query_id}/events?after=0`); expect(replay.status()).toBe(200);
    const done = doneEvent(await replay.text()); expect(done?.status).toBe("done");
    const sourceId = done?.text?.match(/\[(S\d+)\]/)?.[1]; expect(sourceId).toBeTruthy();
    const response = await request.get(`/api/v1/citations/${item.query_id}/${sourceId}`); expect(response.status()).toBe(200);
    const source = await response.json() as Source; const fixture = published.get(source.format!)!;
    expect(source.format).toBe(item.citations[0].format); expect(["docx", "xlsx"]).toContain(source.format);
    expect(source.extraction_methods).toEqual(["office_native"]);
    expect(source.blocks?.every(block => block.extraction_method === "office_native")).toBe(true);
    expect(source.version_id).toBe(fixture.versionId); expect(source.extraction_revision_id).toBe(fixture.revision);
    expect(source.page_index).toBeNull(); expect(source.page_indices).toEqual([]);
    await page.goto(`/workspace/?citation_query=${item.query_id}&citation_source=${sourceId}`);
    await expect(page.getByTestId("office-reader")).toBeVisible();
    if (source.format === "docx") {
      const element = page.locator(".office-element.is-cited").first(); await expect(element).toBeVisible();
      await element.getByRole("button", { name: "Analyser cet élément", exact: true }).click();
    } else {
      await expect(page.locator(".office-spreadsheet td.is-cited").first()).toBeVisible();
      await expect(page.getByRole("combobox", { name: "Feuille", exact: true })).toHaveValue(fixture.unitId);
      await page.getByRole("button", { name: "Analyser cette plage", exact: true }).click();
    }
    await page.getByRole("tab", { name: "Recherche", exact: true }).click();
    await page.getByLabel("Votre recherche").fill("72 V");
    const searched = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/search"));
    await page.getByRole("button", { name: "Rechercher", exact: true }).click();
    const search = await searched; expect(search.status()).toBe(200);
    const body = await search.json() as { results: (Source | { source: Source })[] };
    const sources = body.results.map(result => "source" in result ? result.source : result);
    expect(sources.length).toBeGreaterThan(0);
    expect(sources.every(result => result.version_id === fixture.versionId && result.extraction_revision_id === fixture.revision && result.extraction_methods?.every(method => method === "office_native"))).toBe(true);
    await expect(page.getByTestId("source-card").first()).toBeVisible();
    await expect(page.getByTestId("source-card").getByTestId("extraction-badge")).toHaveCount(0);
    for (const size of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
      await page.setViewportSize(size); expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(size.width);
      await capture(page, info, `office-native-${source.format}-${size.width}`);
    }
    await info.attach(`actual-native-${source.format}-source`, { body: Buffer.from(JSON.stringify({ query_id: item.query_id, source_id: sourceId, source, search: body, search_scope: search.request().postDataJSON().scope, new_imports: 0, new_generations: 0 })), contentType: "application/json" });
  }
  expect(writes).toEqual([]); expect(log.external).toEqual([]); expect(log.pageErrors).toEqual([]);
  await info.attach("office-native-provenance-network", { body: Buffer.from(JSON.stringify({ ...log, query_or_import_posts: writes })), contentType: "application/json" });
});
