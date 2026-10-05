import { test, expect } from "@playwright/test";
import { answerBlocks } from "../../src/lib/answer-format.ts";
import { citationParts } from "../../src/lib/citations.ts";
import { csrfFromCookies } from "../../src/lib/session.ts";
import { monitorBrowser } from "./resources";

type ObservedEvent = { queryId: string; requestId: string; id: number; type: string; raw: string; data: Record<string, unknown>; phase: string };
type StreamRequest = { requestId: string; queryId: string; after: number; phase: string };
const terminalTypes = ["done", "error", "cancelled", "needs_clarification"];
const fixtureName = "long-document-14p.pdf";
const fixtureSha = "994c37186d9985af8ecf5fbde4e2194dcdc061c0fca4f3025dcc643acadf3f86";

test("real progressive response reconnects the same query, then a second generation is cancelled", async ({ page, context, browser }, info) => {
  test.setTimeout(600000);
  test.skip(process.env.RAG_E2E_GENERATION_ALLOWED !== "1", "Requires supervisor admission of the isolated real fixture and local model generation window.");
  let phase = "preflight";
  const events: ObservedEvent[] = [];
  const streams: StreamRequest[] = [];
  const created = new Set<string>();
  const pendingResponses: Promise<void>[] = [];
  const posts: unknown[] = [];
  const external: string[] = [];
  const pageErrors: string[] = [];
  const consoleErrors: { text: string; url: string; phase: string }[] = [];
  const failures: { requestId: string; error: string; phase: string }[] = [];
  const snapshots: unknown[] = [];
  const cleanupErrors: string[] = [];
  let primaryError: unknown;
  const modelDigest = process.env.RAG_E2E_NATIVE_DIGEST ?? "";
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  // Passive CDP observation of native EventSource: no constructor override, route or synthetic event.
  cdp.on("Network.requestWillBeSent", message => {
    const url = new URL(message.request.url);
    const match = url.pathname.match(/^\/api\/v1\/queries\/([^/]+)\/events$/);
    if (match) streams.push({ requestId: message.requestId, queryId: decodeURIComponent(match[1]), after: Number(url.searchParams.get("after") ?? 0), phase });
  });
  cdp.on("Network.eventSourceMessageReceived", message => {
    const stream = streams.findLast(request => request.requestId === message.requestId);
    if (!stream) return;
    try {
      const data: unknown = JSON.parse(message.data);
      if (typeof data !== "object" || data === null || Array.isArray(data) || !/^[1-9]\d*$/.test(message.eventId)) throw new Error("Malformed real SSE payload or ID");
      events.push({ queryId: stream.queryId, requestId: message.requestId, id: Number(message.eventId), type: message.eventName, raw: message.data, data: data as Record<string, unknown>, phase });
    } catch (error) { pageErrors.push(String(error)); }
  });
  cdp.on("Network.loadingFailed", message => failures.push({ requestId: message.requestId, error: message.errorText, phase }));
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("console", message => { if (message.type() === "error") consoleErrors.push({ text: message.text(), url: message.location().url, phase }); });
  page.on("request", request => {
    const url = new URL(request.url());
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) && !["blob:", "data:"].includes(url.protocol)) external.push(request.url());
    if (request.method() === "POST" && url.pathname === "/api/v1/queries") posts.push(request.postDataJSON());
  });
  page.on("response", response => {
    if (response.request().method() !== "POST" || new URL(response.url()).pathname !== "/api/v1/queries") return;
    pendingResponses.push(response.json().then((body: { query_id?: string }) => { if (body.query_id) created.add(body.query_id); }).catch(error => { cleanupErrors.push(String(error)); }));
  });
  const forQuery = (id: string) => events.filter(event => event.queryId === id);
  const terminal = (id: string) => forQuery(id).find(event => terminalTypes.includes(event.type));
  // Compare real rendered text to the real payload using the product's formatting rules (not whitespace erasure).
  const displayedText = (text: string, id: string) => {
    const sources = (forQuery(id).findLast(event => event.type === "sources")?.data.sources ?? []) as { source_id: string; version_id: string }[];
    return answerBlocks(text).flatMap(block => block.kind === "list" ? block.items : block.lines).flatMap(line => line.map(segment =>
      citationParts(segment.text, sources).map(part => part.kind === "text" ? part.text : part.kind === "citation" ? part.id : `${part.text} (référence inconnue)`).join(""))).join("");
  };
  const failOnError = (id: string) => {
    const end = terminal(id);
    if (end && ["error", "needs_clarification"].includes(end.type)) throw new Error(`Real SSE terminal failure: ${JSON.stringify(end)}`);
    expect(pageErrors).toEqual([]);
  };
  const submit = async (question: string) => {
    await page.getByLabel("Votre question").fill(question);
    const responsePromise = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/queries");
    await page.getByRole("button", { name: "Envoyer", exact: true }).click();
    const response = await responsePromise;
    const body = await response.json() as { query_id: string };
    if (body.query_id) created.add(body.query_id);
    expect(response.status()).toBe(202);
    expect(body.query_id).toMatch(/^[a-f0-9-]{36}$/i);
    return body.query_id;
  };
  const progressive = async (id: string, turn: number) => {
    const deadline = Date.now() + 180000;
    while (Date.now() < deadline) {
      failOnError(id);
      if (terminal(id)) throw new Error("Generation finished before an active progressive UI window could be observed; no retry.");
      const query = page.getByTestId("query-turn").nth(turn);
      const text = await query.locator(".answer-text").textContent({ timeout: 1000 }).catch(() => "");
      const actual = forQuery(id);
      if (text?.trim() && actual.some(event => event.type === "status" && event.data.state === "generating") && actual.some(event => event.type === "delta" && typeof event.data.text === "string" && event.data.text.length > 0)) {
        let prefix = "";
        const displayedPrefixes = actual.filter(event => event.type === "delta").map(event => { prefix += String(event.data.text ?? ""); return displayedText(prefix, id); });
        if (!displayedPrefixes.includes(text)) { await page.waitForTimeout(50); continue; }
        snapshots.push({ phase, queryId: id, text, status: await query.locator(".query-status").innerText(), receivedIds: actual.map(event => event.id) });
        if (terminal(id)) throw new Error("Generation reached a terminal during the progressive observation.");
        return text;
      }
      await page.waitForTimeout(50); // Observation cadence only; does not delay any product transport or generation.
    }
    throw new Error("No real progressive model response in the bounded 180 s window");
  };
  const waitTerminal = async (id: string, expected: "done" | "cancelled") => {
    const deadline = Date.now() + (expected === "done" ? 180000 : 30000);
    while (Date.now() < deadline) {
      failOnError(id);
      const end = terminal(id);
      if (end) {
        expect(end.type).toBe(expected);
        expect((end.data.metrics as Record<string, unknown>).model_called).toBe(true);
        if (expected === "done") {
          expect(end.data.status).toMatch(/^(done|length_limited)$/);
          const metrics = end.data.metrics as { verified_model_identity: { digest: string }; llm_execution: { mode: string; fallback: boolean } };
          expect(metrics.verified_model_identity.digest).toBe(modelDigest);
          expect(metrics.llm_execution).toMatchObject({ mode: "gpu", fallback: false });
        }
        return end;
      }
      await page.waitForTimeout(50);
    }
    throw new Error(`No real ${expected} terminal in the bounded window`);
  };
  try {
    expect(modelDigest, "ROOT must provide the actual pinned local 2B digest").toMatch(/^[0-9a-f]{64}$/);
    await page.goto("/workspace/");
    const jobsResponse = await page.request.get("/api/v1/jobs");
    expect(jobsResponse.status()).toBe(200);
    const configuredGeneration = (await jobsResponse.json()).generation;
    expect(configuredGeneration).toMatchObject({ model: "qwen3.5:2b", device: "gpu", fallback: false });
    snapshots.push({ phase: "configured-model", generation: configuredGeneration, expectedDigest: modelDigest });
    const treeResponse = await page.request.get("/api/v1/library/tree");
    expect(treeResponse.status()).toBe(200);
    const tree = await treeResponse.json() as { documents: { id: string; name: string; state: string; active_generation_id: string | null; active_version_id: string | null; sha256: string }[] };
    const documents = tree.documents.filter(document => document.name === fixtureName);
    expect(documents).toHaveLength(1);
    const document = documents[0];
    expect(document.state).toBe("ready"); expect(document.active_generation_id).toBeTruthy();
    expect(document.active_version_id).toBeTruthy(); expect(document.sha256).toBe(fixtureSha);
    const detailResponse = await page.request.get(`/api/v1/documents/${document.id}`);
    expect(detailResponse.status()).toBe(200);
    const detail = await detailResponse.json() as { versions: { sha256: string }[] };
    expect(detail.versions.some(version => version.sha256 === fixtureSha)).toBe(true);
    const documentButton = page.getByRole("navigation", { name: "Arborescence documentaire" }).getByRole("button", { name: /long-document-14p\.pdf/ });
    await expect(documentButton).toContainText("Prêt"); // Observes readiness, not every historical indexing transition.
    snapshots.push({ phase: "index-ready", document, ui: await documentButton.innerText() });
    await page.getByLabel(`Sélectionner ${fixtureName}`).check();
    await page.getByRole("button", { name: "Utiliser ce périmètre" }).click();
    await expect(page.getByTestId("scope-summary")).toContainText(fixtureName);
    await page.getByRole("button", { name: "Suivi", exact: false }).click();
    await page.getByRole("button", { name: "Priorité aux questions", exact: true }).click();
    await page.getByRole("button", { name: "Fermer le suivi" }).click();
    await page.getByRole("tab", { name: "Question", exact: true }).click();
    await monitorBrowser(browser, "before-stream-generation", info);
    phase = "first-generation";
    const first = await submit("Présentez en détail les six paragraphes QLONG-P01-1 à QLONG-P01-6 : expliquez chaque valeur de repère en bar, puis comparez ces valeurs. Développez une synthèse structurée d'environ 600 mots et citez les sources du document.");
    expect(posts).toHaveLength(1);
    expect(posts[0]).toMatchObject({ scope: { kind: "documents", documentIds: [document.id] } });
    const before = await progressive(first, 0);
    const initialRequests = streams.filter(stream => stream.queryId === first).map(stream => stream.requestId);
    phase = "offline";
    try {
      await context.setOffline(true);
      // Active native intervention: offline alone did not abort this Chromium's already-open SSE.
      await cdp.send("Page.stopLoading");
      await expect(page.getByRole("button", { name: "Reconnecter", exact: true })).toBeVisible({ timeout: 15000 });
      failOnError(first);
      expect(failures.some(failure => initialRequests.includes(failure.requestId) && failure.phase === "offline" && ["net::ERR_ABORTED", "net::ERR_INTERNET_DISCONNECTED"].includes(failure.error))).toBe(true);
      expect(terminal(first)).toBeUndefined();
      const lastId = forQuery(first).at(-1)!.id;
      expect(lastId).toBeGreaterThan(0);
      await page.getByRole("button", { name: "Reconnecter", exact: true }).click();
      await expect.poll(() => streams.filter(stream => stream.queryId === first && stream.after === lastId).length, { timeout: 5000 }).toBeGreaterThan(0);
      snapshots.push({ phase, queryId: first, lastId, reconnect: streams.filter(stream => stream.queryId === first && stream.after === lastId) });
      expect(posts).toHaveLength(1);
    } finally { phase = "reconnected"; await context.setOffline(false); }
    expect(streams.some(stream => stream.queryId === first && stream.after > 0)).toBe(true);
    const completion = await waitTerminal(first, "done");
    const resumed = streams.filter(stream => stream.queryId === first && stream.after > 0);
    const resumedEvents = forQuery(first).filter(event => resumed.some(stream => stream.requestId === event.requestId));
    expect(resumedEvents.some(event => event.type === "delta")).toBe(true);
    for (const event of resumedEvents) expect(event.id).toBeGreaterThan(resumed.find(stream => stream.requestId === event.requestId)!.after);
    expect(new Set(forQuery(first).map(event => event.id)).size).toBe(forQuery(first).length);
    expect(forQuery(first).every((event, index, actual) => index === 0 || event.id > actual[index - 1].id)).toBe(true);
    await expect(page.getByTestId("query-turn").nth(0).locator(".query-status")).toContainText(/Réponse terminée|Réponse limitée/);
    const after = await page.getByTestId("query-turn").nth(0).locator(".answer-text").textContent();
    expect(after?.length).toBeGreaterThan(before.length);
    expect(typeof completion.data.text).toBe("string");
    expect(after).toBe(displayedText(completion.data.text as string, first));
    snapshots.push({ phase, queryId: first, text: after, completion });
    await monitorBrowser(browser, "after-reconnected-done", info);
    expect(posts).toHaveLength(1);
    // GET /events is read-only in main.py:581–610; no claim of a measured Ollama HTTP call count.
    phase = "second-generation";
    const second = await submit("Analysez en détail les valeurs de repère QLONG-P01-1 à QLONG-P01-6 en bar. Décrivez séparément chaque paragraphe de la page 1, comparez les valeurs puis rédigez une synthèse détaillée d'environ 600 mots avec les sources documentaires.");
    expect(second).not.toBe(first); expect(posts).toHaveLength(2);
    await progressive(second, 1);
    phase = "cancel-request";
    const cancelResponse = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/v1/queries/${second}/cancel`);
    expect(terminal(second)).toBeUndefined();
    await page.getByRole("button", { name: "Annuler", exact: true }).click();
    expect((await cancelResponse).status()).toBe(200);
    await waitTerminal(second, "cancelled");
    await expect(page.getByTestId("query-turn").nth(1).locator(".query-status")).toContainText("Réponse annulée");
    await expect(page.getByTestId("query-turn").nth(1)).toContainText("Cette réponse est incomplète");
    await expect.poll(async () => {
      const response = await page.request.get("/api/v1/diagnostics", { timeout: 10000 });
      expect(response.status()).toBe(200);
      const diagnostics = await response.json();
      snapshots.push({ phase: "cancelled-release", active_queries: diagnostics.active_queries, resources: diagnostics.resources, llm_accelerator: diagnostics.llm_accelerator });
      return { active_queries: diagnostics.active_queries, heavy_owner: diagnostics.resources.heavy_owner };
    }, { timeout: 15000 }).toEqual({ active_queries: 0, heavy_owner: null });
    const releasedJobsResponse = await page.request.get("/api/v1/jobs");
    expect(releasedJobsResponse.status()).toBe(200);
    const releasedGeneration = (await releasedJobsResponse.json()).generation;
    expect(releasedGeneration).toMatchObject({ model: "qwen3.5:2b", device: "gpu", fallback: false });
    snapshots.push({ phase: "cancelled-model", generation: releasedGeneration });
    await monitorBrowser(browser, "after-stream-cancelled-release", info);
    await expect(page.getByTestId("scope-summary")).toContainText(fixtureName);
    expect(posts).toHaveLength(2); expect(created.size).toBe(2); expect(external).toEqual([]); expect(pageErrors).toEqual([]);
    const unexpectedConsole = consoleErrors.filter(error => {
      if (error.phase !== "offline" || !error.url) return true;
      const path = new URL(error.url).pathname;
      if (error.text.includes("ERR_ABORTED")) return path !== `/api/v1/queries/${first}/events` || !failures.some(failure => initialRequests.includes(failure.requestId) && failure.phase === "offline" && failure.error === "net::ERR_ABORTED");
      if (!error.text.includes("ERR_INTERNET_DISCONNECTED")) return true;
      return !["/api/v1/library/tree", "/api/v1/readiness", "/api/v1/jobs", `/api/v1/queries/${first}/events`].includes(path);
    });
    expect(unexpectedConsole).toEqual([]);
    await page.screenshot({ path: info.outputPath("stream-reconnect-and-cancel.png"), fullPage: true });
  } catch (error) { primaryError = error; throw error; }
  finally {
    phase = "cleanup";
    await context.setOffline(false).catch(error => cleanupErrors.push(String(error)));
    await Promise.allSettled(pendingResponses);
    for (const id of created) {
      if (!terminal(id)) {
        // Read only the client-visible cookie; never attach the cookie string, token or request headers.
        const csrf = await page.evaluate(() => document.cookie).then(csrfFromCookies).catch(() => null);
        const cancelled = csrf ? await page.request.post(`/api/v1/queries/${encodeURIComponent(id)}/cancel`, {
          timeout: 10000, headers: { "X-CSRF-Token": csrf, Origin: new URL(page.url()).origin },
        }).catch(error => { cleanupErrors.push(`Cleanup cancellation ${id} transport failure: ${error instanceof Error ? error.name : "unknown"}`); return null; }) : null;
        if (!csrf) cleanupErrors.push(`Cleanup cancellation ${id}: client CSRF cookie unavailable`);
        if (cancelled && cancelled.status() !== 200) cleanupErrors.push(`Cleanup cancellation ${id}: ${cancelled.status()}`);
      }
      const replay = await page.request.get(`/api/v1/queries/${encodeURIComponent(id)}/events?after=0`, { timeout: 10000 }).catch(error => { cleanupErrors.push(String(error)); return null; });
      if (replay) { if (replay.status() !== 200) cleanupErrors.push(`Replay ${id}: ${replay.status()}`); await info.attach(`actual-sse-${id}`, { body: await replay.body(), contentType: "text/event-stream; charset=utf-8" }); }
    }
    await cdp.detach().catch(error => cleanupErrors.push(String(error)));
    await info.attach("stream-reconnect-evidence", { body: Buffer.from(JSON.stringify({ created: [...created], posts, streams, events, failures, snapshots, external, pageErrors, consoleErrors, cleanupErrors, primaryError: primaryError instanceof Error ? primaryError.message : null, method: "Passive Chromium CDP EventSource observations and real UI; active interventions are whole-browser-context offline and Page.stopLoading of pending page fetches. Actual initial SSE loadingFailed and Reconnecter required before the real UI reconnect. Cleanup cancels only queries created here, using the product client CSRF-cookie mechanism without recording tokens/headers. GET SSE reconnect does not recreate query; no native Ollama HTTP call-count measurement. Readiness observed as Prêt, no claim for all indexing transitions." }, null, 2)), contentType: "application/json" });
    if (!primaryError) expect(cleanupErrors).toEqual([]);
  }
});
