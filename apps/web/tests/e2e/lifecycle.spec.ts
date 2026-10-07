import { test, expect, type Page } from "@playwright/test";
import { monitorBrowser } from "./resources";
import { withImportPriority } from "./import-priority.ts";
import { configuredUploadLimit, detail, fixture, guardTarget, readLifecycleTarget, sha256, uploadFromUi, waitJob } from "./lifecycle-target";

// No test is enabled by merely listing it. Every run also needs a concrete
// runtime binding and exact scenario permit. This suite never calls /queries.
// D4 (recette R26-KIT-02) : chaque indexation attendue (import, nouvelle version, réindexation) a lieu sous
// « Priorité aux imports », choisie dans une page dédiée du contexte puis rétablie à la priorité trouvée dans un
// finally (import-priority.ts). Le réimport identique (job publié rendu tel quel) et le refus 413 n'attendent
// aucune indexation : ils ne changent pas la priorité.
test.beforeEach(() => {
  test.skip(process.env.RAG_E2E_LIFECYCLE_ALLOWED !== "1", "Lifecycle windows are scheduled separately; NOT_RUN without explicit authorization.");
});

async function expectCurrentFileFailure(page: Page, name: string, errorMessage: unknown) {
  expect(typeof errorMessage).toBe("string");
  expect((errorMessage as string).trim()).not.toBe("");
  const panel = page.locator(".jobs-panel");
  await expect(panel).toHaveCount(1);
  const exactName = new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
  const card = panel.getByRole("article").filter({ has: page.locator(".job-heading > strong").filter({ hasText: exactName }) });
  await expect(card).toHaveCount(1);
  await expect(card.locator(".job-heading > strong")).toHaveText(name);
  await expect(card.locator(".status-indicator")).toHaveText("Échec");
  const error = card.locator(".inline-error");
  await expect(error).toHaveCount(1);
  await expect(error).toBeVisible();
  await expect(error).toHaveText(errorMessage as string);
}

test("immutable original supports real ETag and byte ranges", async ({ request }, info) => {
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("http_original_cache"), "Exact GET-only scenario not authorized.");
  await guardTarget(request, target, info);
  const document = await detail(request, target);
  const source = fixture(target.document.fixture_key);
  const version = document.versions.find((item: { id: string }) => item.id === target.document.version_id);
  expect(version.sha256).toBe(source.sha256);
  const url = `${target.origin}/api/v1/versions/${encodeURIComponent(version.id)}/file`;
  const original = await request.get(url);
  expect(original.status()).toBe(200);
  expect(sha256(await original.body())).toBe(source.sha256);
  expect(original.headers().etag).toBe(`"${source.sha256}"`);
  expect(original.headers()["cache-control"]).toContain("immutable");
  const cached = await request.get(url, { headers: { "If-None-Match": original.headers().etag } });
  expect(cached.status()).toBe(304);
  expect((await cached.body()).length).toBe(0);
  const range = await request.get(url, { headers: { Range: "bytes=0-63" } });
  expect(range.status()).toBe(206);
  expect(range.headers()["content-range"]).toBe(`bytes 0-63/${source.bytes.length}`);
  expect(await range.body()).toEqual(source.bytes.subarray(0, 64));
  await info.attach("actual-http-cache-and-range", { body: Buffer.from(JSON.stringify({ version_id: version.id, sha256: source.sha256, full_status: original.status(), conditional_status: cached.status(), range_status: range.status(), etag: original.headers().etag, content_range: range.headers()["content-range"], qualification_limit: "HTTP byte cache only; does not measure parsing or embedding reuse" }, null, 2)), contentType: "application/json" });
});

test("registered old citation retains its exact original and revision", async ({ request, page, browser }, info) => {
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("read_old_citation"), "An actual registered old citation binding is required; none is fabricated.");
  await guardTarget(request, target, info);
  const old = target.old_citation;
  expect(old?.query_id).toBeTruthy();
  expect(old?.source_id).toBeTruthy();
  expect(old?.extraction_revision_id).toBeTruthy();
  expect(old?.block_hashes && Object.keys(old.block_hashes).length).toBeGreaterThan(0);
  const document = await detail(request, target);
  const response = await request.get(`${target.origin}/api/v1/citations/${encodeURIComponent(old!.query_id)}/${encodeURIComponent(old!.source_id)}`);
  expect(response.status()).toBe(200);
  const source = await response.json();
  expect(source.document_id).toBe(target.document.id);
  expect(source.version_id).toBe(old!.version_id);
  expect(source.generation_id).toBe(old!.generation_id);
  expect(source.extraction_revision_id).toBe(old!.extraction_revision_id);
  expect(source.page_index).toBe(old!.page_index);
  for (const [blockId, hash] of Object.entries(old!.block_hashes)) {
    const block = source.blocks.find((item: { id: string }) => item.id === blockId);
    expect(block.source_text_hash).toBe(hash);
    expect(sha256(Buffer.from(block.raw_text ?? block.text, "utf8"))).toBe(hash);
  }
  const exactBlock = source.blocks.find((block: { id: string; page_index: number }) => block.page_index === source.page_index && old!.block_hashes[block.id]);
  expect(exactBlock, "An actual bound source block must belong to the displayed physical page").toBeTruthy();
  const latestResponse = await request.get(`${target.origin}/api/v1/versions/${encodeURIComponent(source.version_id)}/outline`);
  expect(latestResponse.status()).toBe(200);
  const latest = await latestResponse.json();
  expect(latest.extraction_revision_id).toBeTruthy();
  await info.attach("actual-old-registered-source", { body: Buffer.from(JSON.stringify(source, null, 2)), contentType: "application/json" });
  const pinnedResponses: Record<string, unknown>[] = [];
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname.includes(`/versions/${source.version_id}/`) && url.searchParams.has("extraction_revision_id")) pinnedResponses.push({ path: url.pathname, revision: url.searchParams.get("extraction_revision_id"), status: response.status() });
  });
  await page.goto(`/workspace/?citation_query=${encodeURIComponent(old!.query_id)}&citation_source=${encodeURIComponent(old!.source_id)}`);
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("Actions et versions du document").click();
  await expect(page.getByLabel("Version affichée")).toHaveValue(source.version_id);
  await page.getByLabel("Actions et versions du document").click();
  await expect(page.getByLabel("Numéro de page")).toHaveValue(String(source.page_index + 1));
  await expect(page.getByTestId("source-highlight").first()).toBeVisible();
  await expect(page.locator(".source-navigation")).toContainText(old!.extraction_revision_id.slice(0, 8));
  const pageAction = page.getByRole("button", { name: "Analyser cette page", exact: true });
  if (latest.extraction_revision_id !== old!.extraction_revision_id) {
    await expect(pageAction).toBeDisabled();
    await expect(pageAction).toHaveAttribute("title", /révision archivée/);
  } else await expect(pageAction).toBeEnabled();
  await page.getByRole("button", { name: "Texte extrait & provenance" }).click();
  await expect(page.locator(".extracted-text")).toContainText(exactBlock.text);
  const exactBlockRow = page.locator(".extracted-text > div").filter({ has: page.getByText(exactBlock.text, { exact: true }) });
  await exactBlockRow.getByRole("button", { name: "Analyser ce bloc", exact: true }).click();
  const explicitScope = await page.locator(".scope-trigger").innerText();
  expect(explicitScope).toContain("Bloc source");
  // Read the current original through the real library, then return. No store
  // injection or model call creates the previous citation state.
  await page.getByRole("navigation", { name: "Arborescence documentaire" }).getByTitle(document.relative_path, { exact: true }).click();
  await expect(page.locator(".source-navigation")).toHaveCount(0);
  await page.getByRole("button", { name: "Revenir au passage précédent", exact: true }).click();
  await expect(page.locator(".source-navigation")).toContainText(old!.extraction_revision_id.slice(0, 8));
  await expect(page.getByLabel("Numéro de page")).toHaveValue(String(source.page_index + 1));
  await expect(page.locator(".extracted-text")).toContainText(exactBlock.text);
  // explicitScope provient d'innerText (eyebrow en majuscules CSS, bouton flex) :
  // comparer le même rendu visible, pas le textContent brut.
  await expect(page.locator(".scope-trigger")).toHaveText(explicitScope, { useInnerText: true });
  expect(pinnedResponses.some(response => String(response.path).includes("/blocks") && response.revision === old!.extraction_revision_id && response.status === 200)).toBeTruthy();
  await info.attach("actual-pinned-viewer-requests", { body: Buffer.from(JSON.stringify(pinnedResponses, null, 2)), contentType: "application/json" });
  await info.attach("actual-revision-action-guard", { body: Buffer.from(JSON.stringify({ cited_revision: old!.extraction_revision_id, latest_published_revision: latest.extraction_revision_id, archived: latest.extraction_revision_id !== old!.extraction_revision_id, selected_block_id: exactBlock.id, selected_block_hash: exactBlock.source_text_hash, explicit_scope_retained_after_return: explicitScope }, null, 2)), contentType: "application/json" });
  await monitorBrowser(browser, "registered-old-version-deeplink", info);
  await page.screenshot({ path: info.outputPath("old-registered-version.png"), fullPage: true });
  // This proves a real registered-source deep link and pinned viewer metadata.
  // It does not claim a model answer or restoration of an entire chat history.
});

test("version menu reads the old original while a different version is active", async ({ request, page, browser }, info) => {
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("read_old_version"), "Actual old/current version bindings must be prepared first.");
  await guardTarget(request, target, info);
  const document = await detail(request, target);
  const old = target.old_version;
  expect(old?.version_id).toBeTruthy();
  const original = fixture(old!.fixture_key);
  expect(document.active_version_id).toBe(target.document.version_id);
  expect(document.active_version_id).not.toBe(old!.version_id);
  expect(document.versions.find((item: { id: string }) => item.id === old!.version_id).sha256).toBe(original.sha256);
  await page.goto(`/workspace/?document=${encodeURIComponent(document.id)}&version=${encodeURIComponent(document.active_version_id)}&page=1`);
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("Actions et versions du document").click();
  await page.getByLabel("Version affichée").selectOption(old!.version_id);
  await expect(page.getByLabel("Version affichée")).toHaveValue(old!.version_id);
  await expect(page.locator(".textLayer span").filter({ hasText: old!.expected_text }).first()).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`version=${old!.version_id}`));
  const versionFile = await request.get(`${target.origin}/api/v1/versions/${encodeURIComponent(old!.version_id)}/file`);
  expect(versionFile.status()).toBe(200);
  expect(sha256(await versionFile.body())).toBe(original.sha256);
  await monitorBrowser(browser, "actual-old-version-menu", info);
  await page.screenshot({ path: info.outputPath("old-version-menu.png"), fullPage: true });
});

test("identical UI reimport retains exact document version job and publication", async ({ request, page, browser }, info) => {
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("reimport_identical"), "One real reimport mutation must be explicitly scheduled.");
  await guardTarget(request, target, info);
  const before = await detail(request, target);
  const input = fixture(target.document.fixture_key);
  expect(target.document.relative_path).toBe(input.name);
  expect(before.active_version_id).toBe(target.document.version_id);
  expect(before.active_generation_id).toBe(target.document.generation_id);
  expect(before.versions.find((item: { id: string }) => item.id === target.document.version_id).sha256).toBe(input.sha256);
  const oldJob = before.jobs.find((job: { version_id: string; published: boolean; active: boolean }) => job.version_id === target.document.version_id && job.published && job.active);
  expect(oldJob?.state).toBe("ready");
  await page.goto("/workspace/");
  await monitorBrowser(browser, "before-identical-reimport", info);
  const received = await uploadFromUi(page, input, info);
  expect(received.status).toBe(202);
  expect(received.body).toMatchObject({ document_id: before.id, version_id: target.document.version_id, job_id: oldJob.id, reused: true });
  const after = await detail(request, target);
  expect(after.versions).toEqual(before.versions);
  expect(after.jobs.map((job: { id: string }) => job.id).sort()).toEqual(before.jobs.map((job: { id: string }) => job.id).sort());
  expect(after.active_generation_id).toBe(before.active_generation_id);
  await monitorBrowser(browser, "after-identical-reimport", info);
  await info.attach("actual-identical-reimport-state", { body: Buffer.from(JSON.stringify({ before, after, zero_embedding_calculation: "NOT_PROVEN by these IDs: requires inference counter deltas with stable process identity and no concurrent computation" }, null, 2)), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("identical-reimport.png"), fullPage: true });
});

test("UI reindex publishes a new verified generation without creating a file version", async ({ request, page, browser }, info) => {
  test.setTimeout(600000);
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("reindex_current"), "Reindex is a separate engine window; no automatic mutation.");
  await guardTarget(request, target, info);
  const before = await detail(request, target);
  expect(before.active_version_id).toBe(target.document.version_id);
  expect(before.active_generation_id).toBe(target.document.generation_id);
  await page.goto(`/workspace/?document=${encodeURIComponent(before.id)}&version=${encodeURIComponent(target.document.version_id)}&page=1`);
  await expect(page.locator("canvas").first()).toBeVisible();
  const { started, job } = await withImportPriority(page, request, info, async () => {
    await page.getByLabel("Actions et versions du document").click();
    const pending = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith(`/documents/${target.document.id}/reindex`));
    await page.getByRole("button", { name: "Réindexer ce document", exact: true }).click();
    const response = await pending;
    expect(response.status()).toBe(202);
    const started = await response.json();
    expect(started.version_id).toBe(target.document.version_id);
    expect(started.reused).toBe(false);
    const job = await waitJob(request, target.origin, started.job_id, info);
    expect(job.state).toBe("ready");
    expect(job.published).toBe(true);
    return { started, job };
  });
  const after = await detail(request, target);
  expect(after.versions).toEqual(before.versions);
  expect(after.active_version_id).toBe(before.active_version_id);
  expect(after.active_generation_id).toBe(job.generation_id);
  expect(after.active_generation_id).not.toBe(before.active_generation_id);
  await monitorBrowser(browser, "after-real-reindex", info);
  await info.attach("actual-reindex-state", { body: Buffer.from(JSON.stringify({ before, after, started, parsing_cache_reuse: "NOT_PROVEN: requires matching current pipeline fingerprint and verified extraction artifact trace", embedding_calculation_reuse: "NOT_PROVEN by this scenario: requires actual inference counter deltas and cache provenance" }, null, 2)), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("real-reindex.png"), fullPage: true });
});

test("updated PDF remains unpublished until ready and preserves its old original", async ({ request, page, browser }, info) => {
  test.setTimeout(600000);
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("import_version_2"), "One controlled new-version import requires its own engine window.");
  await guardTarget(request, target, info);
  expect(target.document.fixture_key).toBe("version-1");
  const before = await detail(request, target);
  expect(before.active_version_id).toBe(target.document.version_id);
  expect(before.active_generation_id).toBe(target.document.generation_id);
  const old = fixture("version-1");
  const next = fixture("version-2");
  expect(target.document.relative_path).toBe(next.name);
  expect(old.name).toBe(next.name);
  expect(before.versions.some((version: { sha256: string }) => version.sha256 === next.sha256), "Keep this mutation a first controlled update; do not silently reimport an already existing v2").toBe(false);
  await page.goto(`/workspace/?document=${before.id}&version=${target.document.version_id}&page=1`);
  await expect(page.locator("canvas").first()).toBeVisible();
  const { received, job } = await withImportPriority(page, request, info, async () => {
    const received = await uploadFromUi(page, next, info);
    expect(received.status).toBe(202);
    expect(received.body.document_id).toBe(before.id);
    expect(received.body.version_id).not.toBe(target.document.version_id);
    expect(received.body.reused).toBe(false);
    const staging = await detail(request, target);
    await info.attach("actual-new-version-before-publication", { body: Buffer.from(JSON.stringify(staging, null, 2)), contentType: "application/json" });
    expect(staging.active_generation_id, "A prepublication observation is required; a fast completion cannot prove this boundary").toBe(before.active_generation_id);
    expect(staging.active_version_id).toBe(before.active_version_id);
    const unpublished = await request.get(`${target.origin}/api/v1/versions/${received.body.version_id}/pages/0/blocks`);
    expect(unpublished.status()).toBe(409);
    expect((await unpublished.json()).code).toBe("not_indexed");
    const job = await waitJob(request, target.origin, received.body.job_id, info);
    expect(job.state).toBe("ready");
    expect(job.published).toBe(true);
    return { received, job };
  });
  const after = await detail(request, target);
  expect(after.active_version_id).toBe(received.body.version_id);
  expect(after.active_generation_id).toBe(job.generation_id);
  expect(after.versions).toHaveLength(before.versions.length + 1);
  for (const [versionId, source] of [[target.document.version_id, old], [received.body.version_id, next]] as const) {
    const original = await request.get(`${target.origin}/api/v1/versions/${versionId}/file`);
    expect(original.status()).toBe(200);
    expect(sha256(await original.body())).toBe(source.sha256);
  }
  await page.goto(`/workspace/?document=${before.id}&version=${received.body.version_id}&page=1`);
  await expect(page.locator(".textLayer span").filter({ hasText: "4.9" }).first()).toBeVisible();
  await page.getByLabel("Actions et versions du document").click();
  await page.getByLabel("Version affichée").selectOption(target.document.version_id);
  await expect(page.locator(".textLayer span").filter({ hasText: "2.7" }).first()).toBeVisible();
  await monitorBrowser(browser, "new-and-old-version-originals", info);
  await info.attach("actual-two-version-publication", { body: Buffer.from(JSON.stringify({ before, after, job, citation_click_qualification: "NOT_RUN: no model or synthetic citation in this scenario" }, null, 2)), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("updated-and-old-original.png"), fullPage: true });
});

for (const [key, expectedCode] of [["encrypted", "PDF_ENCRYPTED"], ["corrupt", "PDF_INVALID"]] as const) {
  test(`UI import ${key} preserves an explicit real file failure`, async ({ request, page, browser }, info) => {
    test.setTimeout(600000);
    const target = readLifecycleTarget();
    test.skip(!target.permits.includes(`file_error:${key}`), "Exact error fixture import must be independently scheduled.");
    await guardTarget(request, target, info);
    const input = fixture(key);
    const tree = await request.get(`${target.origin}/api/v1/library/tree?search=${encodeURIComponent(input.name)}`);
    expect((await tree.json()).documents.some((document: { relative_path: string }) => document.relative_path === input.name), "Preserve prior error evidence; choose a fresh isolated storage rather than silently retry").toBe(false);
    await page.goto("/workspace/");
    const job = await withImportPriority(page, request, info, async () => {
      const received = await uploadFromUi(page, input, info);
      expect(received.status).toBe(202);
      const job = await waitJob(request, target.origin, received.body.job_id, info);
      expect(job.id).toBe(received.body.job_id);
      expect(job.document_id).toBe(received.body.document_id);
      expect(job.version_id).toBe(received.body.version_id);
      expect(job.state).toBe("error");
      expect(job.error_code).toBe(expectedCode);
      return job;
    });
    await page.getByRole("button", { name: "Actualiser la bibliothèque", exact: true }).click();
    const row = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: new RegExp(input.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first();
    await expect(row).toContainText("Erreur");
    await page.getByRole("button", { name: "Suivi", exact: false }).click();
    await expectCurrentFileFailure(page, input.name, job.error_message);
    await monitorBrowser(browser, `actual-file-error-${key}`, info);
    await page.screenshot({ path: info.outputPath(`${key}-real-error.png`), fullPage: true });
  });
}

test("blank PDF requires an explicit visible no-text state", async ({ request, page, browser }, info) => {
  test.setTimeout(600000);
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("file_error:blank"), "Blank import is scheduled separately; ready/zero chunks is not presumed to be an error.");
  await guardTarget(request, target, info);
  const input = fixture("blank");
  const tree = await request.get(`${target.origin}/api/v1/library/tree?search=${encodeURIComponent(input.name)}`);
  expect((await tree.json()).documents.some((document: { relative_path: string }) => document.relative_path === input.name)).toBe(false);
  await page.goto("/workspace/");
  const { received, job } = await withImportPriority(page, request, info, async () => {
    const received = await uploadFromUi(page, input, info);
    expect(received.status).toBe(202);
    const job = await waitJob(request, target.origin, received.body.job_id, info);
    expect(job.state).toBe("ready");
    return { received, job };
  });
  const blocks = await request.get(`${target.origin}/api/v1/versions/${received.body.version_id}/pages/0/blocks`);
  expect(blocks.status()).toBe(200);
  const actual = await blocks.json();
  expect(actual.page.extraction_state).toBe("blank");
  expect(actual.blocks).toEqual([]);
  await info.attach("actual-blank-page-state", { body: Buffer.from(JSON.stringify({ job, page: actual }, null, 2)), contentType: "application/json" });
  await page.goto(`/workspace/?document=${received.body.document_id}&version=${received.body.version_id}&page=1`);
  await expect(page.locator("canvas").first()).toBeVisible();
  await monitorBrowser(browser, "actual-blank-rendered", info);
  await page.screenshot({ path: info.outputPath("blank-before-explicit-state-assertion.png"), fullPage: true });
  await expect(page.getByText(/Page blanche|Aucun texte exploitable/i).first()).toBeVisible();
});

test("isolated 64KiB limit rejects a genuinely oversized controlled PDF", async ({ request, page, browser }, info) => {
  const target = readLifecycleTarget();
  test.skip(!target.permits.includes("file_error:size-limit"), "Requires a separate isolated service/profile with explicit 65536-byte limit.");
  await guardTarget(request, target, info);
  expect(target.upload_limit_bytes).toBe(65536);
  expect(configuredUploadLimit(target)).toBe(65536);
  const input = fixture("size-limit");
  expect(input.bytes.length).toBeGreaterThan(65536);
  const before = await request.get(`${target.origin}/api/v1/library/tree?search=${encodeURIComponent(input.name)}`);
  expect((await before.json()).documents).toEqual([]);
  await page.goto("/workspace/");
  const received = await uploadFromUi(page, input, info);
  expect(received.status).toBe(413);
  expect(received.body.code).toBe("file_too_large");
  await expect(page.getByText(received.body.message, { exact: true })).toBeVisible();
  const after = await request.get(`${target.origin}/api/v1/library/tree?search=${encodeURIComponent(input.name)}`);
  expect((await after.json()).documents).toEqual([]);
  await monitorBrowser(browser, "actual-isolated-size-rejection", info);
  await page.screenshot({ path: info.outputPath("isolated-size-limit-refusal.png"), fullPage: true });
  await info.attach("size-limit-scope", { body: Buffer.from(JSON.stringify({ configured_max_bytes: 65536, actual_fixture_bytes: input.bytes.length, nominal_200_mib_limit_qualified: false }, null, 2)), contentType: "application/json" });
});
