import { test, expect } from "@playwright/test";
import type { Block, DocumentDetail, Outline, PageBlocks, Scope, Source } from "../../src/lib/types";
import { watchPage } from "./guards";
import { detail, guardTarget, readLifecycleTarget, sha256, type LifecycleTarget } from "./lifecycle-target";

const identity = {
  document_id: "60ab5828-afa1-4365-808e-b4dd304a6a14", version_id: "9dc53b7d-f2ef-4c87-b6a4-b803355987bd",
  generation_id: "92af4c8c-8b33-4744-af89-a6fdc6749e58", extraction_revision_id: "20153a0f-75f0-5179-9c53-d0b06497e4ec",
};
const sectionId = "1596e7ff-f739-5811-9645-298946d0ff02";
const sectionTitle = "Document long QLONG-14 — page 2 sur 14";
const fixtureSha = "994c37186d9985af8ecf5fbde4e2194dcdc061c0fca4f3025dcc643acadf3f86";
type SectionTarget = LifecycleTarget & { section_scope: { section_id: string; block_ids: string[]; allowed_chunk_ids: string[]; generation_id: string } };
type FragmentBlock = Block & { start_offset: number; end_offset: number };
type Fragment = Source & { chunk_id: string; blocks: FragmentBlock[] };
type Search = { results: Fragment[]; scope_snapshot: { scope: unknown; generations: string[]; versions: Record<string, string>; documents: Record<string, string>; page_indices: number[] | null; block_ids: string[] | null; spans: unknown[] } };

test("outline section action limits real search to its published blocks without starting a question", async ({ page, request }, info) => {
  test.skip(process.env.RAG_E2E_LIFECYCLE_ALLOWED !== "1", "Requires an admitted window on the preserved Q05/Q07 instance.");
  const target = readLifecycleTarget() as SectionTarget;
  test.skip(!target.permits.includes("read_section_scope"), "The exact read_section_scope permit is absent.");
  await guardTarget(request, target, info);
  expect(target.document).toMatchObject({ id: identity.document_id, version_id: identity.version_id,
    generation_id: identity.generation_id, extraction_revision_id: identity.extraction_revision_id, fixture_key: "long-document-14p" });
  expect(target.section_scope).toMatchObject({ section_id: sectionId, generation_id: identity.generation_id });
  expect(target.section_scope.block_ids).toHaveLength(21);
  expect(new Set(target.section_scope.block_ids).size).toBe(21);
  expect(target.section_scope.allowed_chunk_ids.length).toBeGreaterThan(0);
  const document = await detail(request, target) as DocumentDetail;
  expect(document).toMatchObject({ id: identity.document_id, state: "ready", page_count: 14, active_generation_id: identity.generation_id });
  expect(document.active_version_id ?? document.version_id).toBe(identity.version_id);
  expect(document.versions.find(version => version.id === identity.version_id)?.sha256).toBe(fixtureSha);
  const original = await request.get(`${target.origin}/api/v1/versions/${identity.version_id}/file`);
  expect(original.status()).toBe(200);
  expect(sha256(await original.body())).toBe(fixtureSha);
  const revision = `?extraction_revision_id=${identity.extraction_revision_id}`;
  const outlineResponse = await request.get(`${target.origin}/api/v1/versions/${identity.version_id}/outline${revision}`);
  expect(outlineResponse.status()).toBe(200);
  const outline = await outlineResponse.json() as Outline;
  expect(outline).toMatchObject({ version_id: identity.version_id, generation_id: identity.generation_id, extraction_revision_id: identity.extraction_revision_id });
  const section = outline.sections.find(value => value.id === sectionId);
  expect(section).toMatchObject({ title: sectionTitle, page_index: 1 });
  expect([...section!.block_ids].sort()).toEqual([...target.section_scope.block_ids].sort());
  const allowed = new Set(section!.block_ids), allowedChunks = new Set(target.section_scope.allowed_chunk_ids);
  const pages = new Map<number, PageBlocks>();
  async function originalBlock(fragment: FragmentBlock) {
    expect(Number.isInteger(fragment.page_index) && fragment.page_index >= 0 && fragment.page_index < 14).toBe(true);
    if (!pages.has(fragment.page_index)) {
      const response = await request.get(`${target.origin}/api/v1/versions/${identity.version_id}/pages/${fragment.page_index}/blocks${revision}`);
      expect(response.status()).toBe(200);
      const received = await response.json() as PageBlocks;
      expect(received).toMatchObject({ version_id: identity.version_id, generation_id: identity.generation_id,
        extraction_revision_id: identity.extraction_revision_id, page: { page_index: fragment.page_index } });
      pages.set(fragment.page_index, received);
    }
    const block = pages.get(fragment.page_index)!.blocks.find(value => value.id === fragment.id);
    expect(block, "Every search block must exist in the independently read pinned extraction").toBeTruthy();
    const text = block!.raw_text ?? block!.text;
    const hash = sha256(Buffer.from(text, "utf8"));
    expect(block!.source_text_hash ?? block!.source_text_sha256).toBe(hash);
    expect(fragment.extraction_revision_id).toBe(identity.extraction_revision_id);
    expect(fragment.source_text_hash).toBe(hash);
    expect(Number.isInteger(fragment.start_offset) && fragment.start_offset >= 0).toBe(true);
    expect(Number.isInteger(fragment.end_offset) && fragment.end_offset > fragment.start_offset).toBe(true);
    const codepoints = Array.from(text);
    expect(fragment.end_offset).toBeLessThanOrEqual(codepoints.length);
    expect(fragment.text).toBe(codepoints.slice(fragment.start_offset, fragment.end_offset).join(""));
    return block!;
  }

  // globalSetup opens the session before this page guard; its bootstrap is not a document operation.
  const log = watchPage(page), consoleErrors: string[] = [], apiErrors: { path: string; status: number }[] = [];
  const sameOriginViolations: string[] = [], posts: { phase: string; body: unknown }[] = [];
  const evidence: { scope: Scope; result: Search }[] = [];
  let phase = "open-only";
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("response", response => { const url = new URL(response.url()); if (url.pathname.startsWith("/api/v1/") && response.status() >= 400) apiErrors.push({ path: url.pathname, status: response.status() }); });
  page.on("request", received => {
    const url = new URL(received.url());
    if (!["blob:", "data:"].includes(url.protocol) && url.origin !== target.origin) sameOriginViolations.push(url.origin);
    if (received.method() === "POST" && url.pathname === "/api/v1/search") posts.push({ phase, body: received.postDataJSON() });
  });
  async function search(scope: Scope) {
    await page.getByLabel("Votre recherche").fill("QLONG");
    const response = page.waitForResponse(value => value.request().method() === "POST" && new URL(value.url()).pathname === "/api/v1/search");
    await page.getByRole("button", { name: "Rechercher", exact: true }).click();
    const received = await response;
    expect(received.status()).toBe(200);
    expect(received.request().postDataJSON()).toEqual({ question: "QLONG", scope });
    const result = await received.json() as Search;
    evidence.push({ scope, result });
    expect(result.scope_snapshot.scope).toEqual({ ...scope, recursive: true, documentIds: [], spans: [] });
    expect(result.scope_snapshot.generations).toContain(identity.generation_id);
    expect(result.scope_snapshot.versions[identity.generation_id]).toBe(identity.version_id);
    expect(result.scope_snapshot.documents[identity.generation_id]).toBe(identity.document_id);
    expect(result.results.length).toBeGreaterThan(0);
    await expect(page.getByTestId("source-card")).toHaveCount(result.results.length);
    return result;
  }
  try {
    await page.goto("/workspace/");
    await expect(page.getByTestId("scope-summary")).toContainText("Toute la bibliothèque");
    const beforeOpen = await page.getByTestId("scope-summary").innerText();
    await page.getByRole("navigation", { name: "Arborescence documentaire" }).getByTitle(document.relative_path, { exact: true }).click();
    await expect(page.getByLabel("Numéro de page")).toHaveValue("1");
    await expect(page.getByRole("button", { name: "Analyser cette page", exact: true })).toBeEnabled();
    await expect(page.getByTestId("scope-summary")).toHaveText(beforeOpen, { useInnerText: true });
    expect(log.mutations).toEqual([]);
    await page.getByRole("tab", { name: "Recherche", exact: true }).click();
    phase = "global-search";
    const global = await search({ kind: "library" });
    const outside: string[] = [];
    for (const source of global.results.filter(value => value.document_id === identity.document_id)) {
      expect(source).toMatchObject(identity);
      expect(source.blocks.length).toBeGreaterThan(0);
      for (const fragment of source.blocks) {
        await originalBlock(fragment);
        if (!allowed.has(fragment.id) && fragment.text.includes("QLONG")) outside.push(fragment.id);
      }
    }
    expect(outside.length, "The same global search must actually return QLONG evidence outside the target section").toBeGreaterThan(0);
    const countBeforeAction = posts.length;
    phase = "section-action-only";
    await page.getByRole("button", { name: "Afficher le sommaire", exact: true }).click();
    const action = page.getByRole("navigation", { name: "Sommaire", exact: true }).getByRole("button", { name: `Analyser la section ${sectionTitle}`, exact: true });
    await expect(action).toBeEnabled();
    await action.click();
    await expect(page.getByTestId("scope-summary")).toContainText(sectionTitle);
    expect(posts).toHaveLength(countBeforeAction);
    expect(log.mutations).toEqual(["POST /api/v1/search"]);
    phase = "section-search";
    const scoped = await search({ kind: "section", versionId: identity.version_id, sectionId });
    expect(scoped.scope_snapshot.generations).toEqual([identity.generation_id]);
    expect(scoped.scope_snapshot.versions).toEqual({ [identity.generation_id]: identity.version_id });
    expect(scoped.scope_snapshot.documents).toEqual({ [identity.generation_id]: identity.document_id });
    expect(scoped.scope_snapshot.page_indices).toBeNull();
    expect([...(scoped.scope_snapshot.block_ids ?? [])].sort()).toEqual([...allowed].sort());
    expect(scoped.scope_snapshot.spans).toEqual([]);
    for (const source of scoped.results) {
      expect(source).toMatchObject(identity);
      expect(source.chunk_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
      expect(allowedChunks.has(source.chunk_id)).toBe(true);
      expect(source.blocks.length).toBeGreaterThan(0);
      expect(source.page_indices).toEqual([...new Set(source.blocks.map(block => block.page_index))].sort((a, b) => a - b));
      for (const fragment of source.blocks) {
        expect(allowed.has(fragment.id)).toBe(true);
        expect((await originalBlock(fragment)).section_id).toBe(sectionId);
        expect(outside).not.toContain(fragment.id);
      }
      expect(source.text).toBe(source.blocks.map(block => block.text).join("\n"));
    }
    await expect(page.getByRole("tabpanel")).toContainText(`Périmètre de cette recherche : ${sectionTitle}`);
    for (const [index, source] of scoped.results.entries()) {
      const card = page.getByTestId("source-card").nth(index);
      await expect(card.locator(".source-card-title")).toHaveText(document.name);
      await expect(card.locator(".source-card-excerpt")).toHaveText(source.text, { useInnerText: true });
      await expect(card.locator(".source-card-footer")).toContainText(identity.version_id.slice(0, 8));
      await expect(card.locator(".source-card-meta")).toContainText(`p. ${source.page_index! + 1}`);
    }
    await expect(page.getByTestId("scope-summary")).toContainText(sectionTitle);
    await page.screenshot({ path: info.outputPath("section-scoped-search-1366.png"), fullPage: true });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(action).toBeVisible();
    await expect(page.getByTestId("source-card")).toHaveCount(scoped.results.length);
    await expect(page.getByTestId("scope-summary")).toContainText(sectionTitle);
    await page.screenshot({ path: info.outputPath("section-scoped-search-1920.png"), fullPage: true });
    expect(posts.map(value => value.phase)).toEqual(["global-search", "section-search"]);
    expect(log.mutations).toEqual(["POST /api/v1/search", "POST /api/v1/search"]);
    expect(log.external).toEqual([]); expect(log.pageErrors).toEqual([]);
    expect(sameOriginViolations).toEqual([]); expect(consoleErrors).toEqual([]); expect(apiErrors).toEqual([]);
  } finally {
    await info.attach("real-section-scope", { body: Buffer.from(JSON.stringify({ identity, section_id: sectionId, block_ids: [...allowed],
      allowed_chunk_ids: [...allowedChunks], evidence, posts, network: log, consoleErrors, apiErrors, sameOriginViolations,
      limits: "One real published section spanning pages2..7; two UI searches, no page/block recipe replay, import or generation. Chunk IDs intersect section blocks; only returned source fragments, not entire mixed chunk storage, are asserted inside the section. Session bootstrap precedes the page guard."
    }, null, 2)), contentType: "application/json" });
  }
});
