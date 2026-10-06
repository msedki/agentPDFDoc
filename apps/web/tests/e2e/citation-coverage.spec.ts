import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import type { Block, PageBlocks, Source } from "../../src/lib/types";
import { measureCitationCoverage, type CitationCoverageResult } from "./citation-coverage";
import { readOnlyApi, watchPage } from "./guards";
import { detail, guardTarget, readLifecycleTarget, sha256 } from "./lifecycle-target";

type RegisteredBlock = Block & { block_id: string; start_offset: number; end_offset: number; source_text_hash: string };
type RegisteredSource = Omit<Source, "blocks"> & {
  query_id: string; source_id: string; chunk_id: string; page_index: number;
  extraction_revision_id: string; generation_id: string; blocks: RegisteredBlock[];
};
type CitationSet = { schema_version: number; report_sha256: string; sources: RegisteredSource[] };

const originalSha = "994c37186d9985af8ecf5fbde4e2194dcdc061c0fca4f3025dcc643acadf3f86";
const reportSha = "d1a202b4721dd77c05076cd0edcb8f8526026c17418aaf8dba668431c322e6b9";
const queries = ["2d7f8565-f25a-4d8b-9123-04eddaa8ad99", "e0614a6f-a3cf-47a4-8c9c-00ba709b0c59"];

function regionKey(source: RegisteredSource, block: RegisteredBlock) {
  return JSON.stringify([source.version_id, source.extraction_revision_id, block.page_index, block.id,
    block.start_offset, block.end_offset, block.source_text_hash, block.bbox, block.precision]);
}

function passageKey(source: RegisteredSource) {
  return JSON.stringify([source.document_id, source.version_id, source.generation_id,
    source.extraction_revision_id, source.chunk_id, source.text, source.blocks]);
}

test("persisted Q06 passages cover their entire native text without counting repeated citations", async ({ page, request }, info) => {
  test.skip(process.env.RAG_E2E_LIFECYCLE_ALLOWED !== "1", "Requires an admitted GET-only window on the preserved Q05/Q06 instance.");
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("read_citation_coverage"), "The read_citation_coverage permit is absent.");
  await guardTarget(request, target, info);
  const setPath = process.env.RAG_E2E_CITATION_SET;
  const setSha = process.env.RAG_E2E_CITATION_SET_SHA256;
  if (!setPath || !setSha) throw new Error("A reviewed, hash-pinned persisted citation set is required.");
  const frozenBytes = readFileSync(setPath);
  expect(sha256(frozenBytes)).toBe(setSha);
  const frozen = JSON.parse(frozenBytes.toString("utf8")) as CitationSet;
  expect(frozen).toMatchObject({ schema_version: 1, report_sha256: reportSha });
  expect(frozen.sources).toHaveLength(13);
  expect(frozen.sources.map(source => `${source.query_id}/${source.source_id}`).sort()).toEqual([
    ...Array.from({ length: 5 }, (_, index) => `${queries[0]}/S00${index + 1}`),
    ...Array.from({ length: 8 }, (_, index) => `${queries[1]}/S00${index + 1}`),
  ].sort());
  const uniquePassages = new Map(frozen.sources.map(source => [passageKey(source), source]));
  const expectedRegions = new Set(frozen.sources.flatMap(source => source.blocks.map(block => regionKey(source, block))));
  expect(uniquePassages.size).toBe(8);
  expect(expectedRegions.size).toBe(40);
  expect([...new Set(frozen.sources.map(source => source.page_index))].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 5, 8, 12, 13]);

  const document = await detail(request, target);
  expect(document.versions.find((version: { id: string }) => version.id === target.document.version_id)?.sha256).toBe(originalSha);
  const original = await request.get(`${target.origin}/api/v1/versions/${target.document.version_id}/file`);
  expect(original.status()).toBe(200);
  const originalBytes = await original.body();
  expect(originalBytes.length).toBe(55_337);
  expect(sha256(originalBytes)).toBe(originalSha);
  const registryBindings: string[] = [];
  for (const expected of frozen.sources) {
    expect(expected).toMatchObject({ document_id: target.document.id, version_id: target.document.version_id,
      extraction_revision_id: target.document.extraction_revision_id, generation_id: target.document.generation_id,
      precision: "block" });
    expect(expected.text).toBe(expected.blocks.map(block => block.text).join("\n"));
    expect(expected.bboxes).toEqual(expected.blocks.map(block => block.bbox));
    expect(expected.block_ids).toEqual(expected.blocks.map(block => block.id));
    const response = await request.get(`${target.origin}/api/v1/citations/${expected.query_id}/${expected.source_id}`);
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual(expected);
    registryBindings.push(`${expected.query_id}/${expected.source_id}`);
  }

  await page.setViewportSize({ width: 1366, height: 768 });
  const log = watchPage(page), blocked: string[] = [], consoleErrors: string[] = [], consoleWarnings: string[] = [];
  await readOnlyApi(page, blocked);
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text());
    if (message.type() === "warning") consoleWarnings.push(message.text());
  });
  const measurements: { query_id: string; source_id: string; page_index: number; geometry: CitationCoverageResult | null;
    page_anchor?: { slot: { x: number; y: number; width: number; height: number }; viewport: { x: number; y: number; width: number; height: number } } }[] = [];
  const coveredRegions = new Set<string>();
  let scope: string | null = null;
  try {
    for (const source of uniquePassages.values()) {
      const blocksResponse = await request.get(`${target.origin}/api/v1/versions/${source.version_id}/pages/${source.page_index}/blocks?extraction_revision_id=${source.extraction_revision_id}`);
      expect(blocksResponse.status()).toBe(200);
      const blocks = await blocksResponse.json() as PageBlocks;
      expect(blocks).toMatchObject({ version_id: source.version_id, extraction_revision_id: source.extraction_revision_id,
        page: { page_index: source.page_index, extraction_state: "native" } });
      for (const selected of source.blocks) {
        const block = blocks.blocks.find(item => item.id === selected.id);
        expect(block).toBeTruthy();
        expect(selected.page_index).toBe(source.page_index);
        expect(selected.block_id).toBe(selected.id);
        const rawText = block?.raw_text ?? block?.text ?? "";
        expect(sha256(Buffer.from(rawText, "utf8"))).toBe(selected.source_text_hash);
        expect(block?.source_text_hash).toBe(selected.source_text_hash);
        expect(block?.bbox).toEqual(selected.bbox);
        expect(block?.precision).toBe(selected.precision);
        expect(Array.from(rawText).slice(selected.start_offset, selected.end_offset).join("")).toBe(selected.text);
        expect(selected.start_offset).toBe(0);
        expect(selected.end_offset).toBe(Array.from(rawText).length);
      }

      // Real registered deep-link; no restored chat, store injection or generated answer.
      await page.goto(`/workspace/?citation_query=${source.query_id}&citation_source=${source.source_id}`);
      await expect(page.getByLabel("Numéro de page")).toHaveValue(String(source.page_index + 1));
      await expect(page.locator(".source-navigation")).toContainText(source.source_id);
      await expect(page.locator(".source-navigation")).toContainText(source.extraction_revision_id.slice(0, 8));
      await page.getByLabel("Actions et versions du document").click();
      await expect(page.getByLabel("Version affichée")).toHaveValue(source.version_id);
      await page.getByLabel("Actions et versions du document").click();
      if (scope === null) scope = await page.getByTestId("scope-summary").innerText();
      await expect(page.getByTestId("scope-summary")).toHaveText(scope, { useInnerText: true });
      const slot = page.locator(`.pdf-page-slot[data-page-index="${source.page_index}"]`);
      await expect(slot.getByTestId("source-highlight")).toHaveCount(source.blocks.length);
      await expect(slot.locator(".ocr-text-layer span")).toHaveCount(0);
      const observation = { query_id: source.query_id, source_id: source.source_id, page_index: source.page_index,
        geometry: null as CitationCoverageResult | null };
      measurements.push(observation);
      await expect.poll(async () => {
        observation.geometry = await page.evaluate(measureCitationCoverage, { pageIndex: source.page_index,
          passages: source.blocks.map(block => ({ id: regionKey(source, block), text: block.text })) });
        return observation.geometry.passed;
      }, { timeout: 30_000, message: "Every complete native source region must be covered and contain bounded original-canvas ink." }).toBe(true);
      await expect(page.getByLabel("Numéro de page")).toHaveValue(String(source.page_index + 1));
      const pageAnchor = await slot.evaluate(element => {
        const viewport = element.closest(".pdf-scroll");
        if (!viewport) throw new Error("The actual reader viewport is absent.");
        const box = (node: Element) => {
          const rect = node.getBoundingClientRect();
          return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        };
        return { slot: box(element), viewport: box(viewport) };
      });
      measurements[measurements.length - 1].page_anchor = pageAnchor;
      expect(pageAnchor.slot.y).toBeLessThanOrEqual(pageAnchor.viewport.y + 104);
      expect(pageAnchor.slot.y + pageAnchor.slot.height).toBeGreaterThan(pageAnchor.viewport.y + 100);
      expect(pageAnchor.slot.x).toBeLessThan(pageAnchor.viewport.x + pageAnchor.viewport.width);
      expect(pageAnchor.slot.x + pageAnchor.slot.width).toBeGreaterThan(pageAnchor.viewport.x);
      for (const measured of observation.geometry?.passages ?? []) {
        expect(measured.passed).toBe(true);
        coveredRegions.add(measured.id);
      }
      await page.screenshot({ path: info.outputPath(`registered-passage-page${source.page_index + 1}.png`), fullPage: true });
      const canvasPng = await slot.locator("canvas").evaluate(canvas => (canvas as HTMLCanvasElement).toDataURL("image/png"));
      await info.attach(`original-canvas-page${source.page_index + 1}`, {
        body: Buffer.from(canvasPng.split(",")[1], "base64"), contentType: "image/png",
      });
    }
    expect([...coveredRegions].sort()).toEqual([...expectedRegions].sort());
    expect(measurements).toHaveLength(8);
    expect(blocked).toEqual([]);
    expect(log.mutations).toEqual([]);
    expect(log.external).toEqual([]);
    expect(log.pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  } finally {
    await info.attach("registered-citation-coverage", { body: Buffer.from(JSON.stringify({
      report_sha256: reportSha, citation_set_sha256: setSha, original_sha256: originalSha,
      registryBindings, expected_regions: [...expectedRegions], covered_regions: [...coveredRegions], measurements,
      network: log, blocked_mutations: blocked, consoleErrors, consoleWarnings,
      limits: "Thirteen immutable registry bindings, eight distinct passages, forty distinct regions of QLONG at 1366x768. No new generation, import, extraction, inline-chat click, archive, corpus-wide D06.5 or Windows qualification. Original-canvas ink is not RenderTask completion; out-of-viewport regions are measured, not claimed visible."
    }, null, 2)), contentType: "application/json" });
  }
});
