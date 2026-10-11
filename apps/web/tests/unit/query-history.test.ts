import test from "node:test";
import assert from "node:assert/strict";
import { api } from "../../src/lib/api.ts";
import { registeredCitationLocation } from "../../src/lib/citation-link.ts";
import { applyQueryEvent, createHistoryLoader, historicalTurn, historyQueryId, historyQuerySearch, isQueryActive, putHistoricalTurn, sourceFocus, withoutHistoricalTurns } from "../../src/lib/query-history.ts";
import type { HistoricalQuery, QueryState, Source, StreamEvent } from "../../src/lib/types.ts";

const detail = (id = "old-query", state = "done"): HistoricalQuery => ({ query_id: id, conversation_id: "old-conversation", question: "Quelle tension ?", state,
  mode: null, last_event_id: 4, created_at: "2026-10-10T10:00:00+00:00", updated_at: "2026-10-10T10:00:04+00:00", events_url: `/api/v1/queries/${id}/events`,
  scope: { kind: "cell_range", versionId: "old-version", extractionRevisionId: "old-revision", sheetId: "sheet", rowStart: 2, rowEnd: 2, columnStart: 2, columnEnd: 2 },
  answer: "72V [S004]", warnings: [], metrics: {}, resolution: {} });
const source: Source = { source_id: "S004", query_id: "old-query", document_id: "old-document", version_id: "old-version", extraction_revision_id: "old-revision",
  generation_id: "old-generation", format: "xlsx", text: "72V", locator: { kind: "xlsx_cells", unit_id: "sheet", sheet_id: "sheet", sheet_name: "Mesures", part: "xl/worksheets/sheet1.xml", cell_range: "B2", row_start: 2, row_end: 2, column_start: 2, column_end: 2 } };
const event = (type: string, data: Record<string, unknown>, id = "1"): StreamEvent => ({ type, data, id });

test("reload ne conserve qu'un identifiant opaque, et navigation Office conserve cet identifiant", () => {
  const reader = "?citation_query=old-query&citation_source=S004&version=old-version&range=B2&revision=old-revision";
  const search = historyQuerySearch(reader, "old-query");
  assert.equal(historyQueryId(search), "old-query");
  assert.equal(new URLSearchParams(search).get("range"), "B2");
  assert.equal(new URLSearchParams(search).get("revision"), "old-revision");
  assert.equal(new URLSearchParams(search).get("citation_source"), "S004");
  assert.equal(historyQueryId(historyQuerySearch(search, null)), null);
  for (const invalid of ["https://remote.invalid", "a/b", "a\nsecret", "x".repeat(129)]) {
    assert.equal(historyQueryId(`?history_query=${encodeURIComponent(invalid)}`), null);
    assert.throws(() => historyQuerySearch("", invalid));
  }
});

test("tour historique : scope enregistré cloné, mode inconnu, texte vide avant SSE intégral", () => {
  const record = detail(); const turn = historicalTurn(record);
  assert.equal(turn.mode, null); assert.equal(turn.text, ""); assert.equal(turn.historicalState, "done");
  assert.deepEqual(turn.scope, record.scope); assert.notEqual(turn.scope, record.scope);
  assert.equal(isQueryActive(turn), false, "le replay d'une réponse finie n'est pas une nouvelle génération");
  assert.equal(isQueryActive(historicalTurn(detail("live", "running"))), true);
  const noEvents = historicalTurn({ ...record, last_event_id: 0 });
  assert.equal(noEvents.text, record.answer); assert.equal(noEvents.connection, "closed"); assert.deepEqual(noEvents.sources, []);
});

test("deltas, fin, warnings et citation restent exacts après replay : ni doublage ni version courante", () => {
  const activeScope = { kind: "library" }; const immutableScope = JSON.stringify(activeScope);
  let turn = historicalTurn({ ...detail(), warnings: ["Vérifiez le document."] });
  turn = applyQueryEvent(turn, event("sources", { sources: [source] }));
  turn = applyQueryEvent(turn, event("delta", { text: "72V " }, "2"));
  turn = applyQueryEvent(turn, event("delta", { text: "[S004]" }, "3"));
  assert.equal(turn.text, detail().answer);
  turn = applyQueryEvent(turn, event("done", { text: detail().answer, warnings: ["Vérifiez le document."], finish_reason: "stop" }, "4"));
  assert.equal(turn.text, "72V [S004]"); assert.equal(turn.warnings.length, 1); assert.equal(turn.connection, "closed");
  const location = registeredCitationLocation(turn.sources[0], turn.id, "S004");
  assert.equal(location.versionId, "old-version");
  assert.equal("extractionRevisionId" in location && location.extractionRevisionId, "old-revision");
  assert.equal(JSON.stringify(activeScope), immutableScope);
});

test("réponses interrompues et annulées conservent le texte partiel, sans faux done", () => {
  for (const status of ["cancelled", "interrupted", "error"]) {
    let turn = historicalTurn(detail("old-query", status));
    turn = applyQueryEvent(turn, event("delta", { text: "Texte partiel " }));
    assert.equal(turn.text, "Texte partiel ");
    turn = applyQueryEvent(turn, status === "cancelled" ? event("cancelled", { text: "Texte partiel final" }, "2") : event("error", { code: status, message: "Interruption" }, "2"));
    assert.equal(turn.status, status); assert.equal(turn.connection, "closed"); assert.equal(isQueryActive(turn), false);
    assert.equal(turn.text, status === "cancelled" ? "Texte partiel final" : "Texte partiel ");
  }
});

test("une clarification et une référence absente ne deviennent pas une citation cliquable", () => {
  let turn = applyQueryEvent(historicalTurn(detail()), event("done", { text: "72V [S999]" }));
  assert.deepEqual(turn.sources, []); assert.equal(turn.warnings.length, 1);
  turn = applyQueryEvent(historicalTurn(detail("old-query", "needs_clarification")), event("needs_clarification", { message: "Quel document ?" }));
  assert.equal(turn.text, "Quel document ?"); assert.equal(turn.status, "needs_clarification"); assert.equal(turn.connection, "closed");
});

test("list et détail utilisent réellement GET avec AbortSignal, sans création de question", async t => {
  const calls: { url: string; options: RequestInit }[] = [];
  const controller = new AbortController();
  t.mock.method(globalThis, "fetch", async (url: string | URL | Request, options: RequestInit) => {
    calls.push({ url: String(url), options });
    return Response.json(String(url).includes("?limit=") ? { queries: [detail()], next_cursor: null } : detail());
  });
  await api.queryHistory("previous-id", controller.signal); await api.historicalQuery("old-query", controller.signal);
  assert.deepEqual(calls.map(call => call.url), ["/api/v1/queries?limit=20&cursor=previous-id", "/api/v1/queries/old-query"]);
  for (const call of calls) { assert.equal(call.options.method ?? "GET", "GET"); assert.equal(call.options.signal, controller.signal); assert.equal(call.options.credentials, "same-origin"); assert.equal(call.options.body, undefined); }
});

function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }

test("sélections A puis B : GET et flux tardifs de A ne remplacent jamais B", async () => {
  const records = new Map<string, ReturnType<typeof deferred<HistoricalQuery>>>();
  const signals: AbortSignal[] = []; const ready: QueryState[] = []; const events: string[] = []; const errors: unknown[] = [];
  const streams: { id: string; after: string; event: (event: StreamEvent) => void; connection: (value: QueryState["connection"]) => void; closed: boolean }[] = [];
  const loader = createHistoryLoader({ detail: (id, signal) => { signals.push(signal); const pending = deferred<HistoricalQuery>(); records.set(id, pending); return pending.promise; }, start: () => {}, ready: turn => ready.push(turn), event: id => events.push(id), connection: id => events.push(`connection:${id}`), failure: error => errors.push(error),
    connect: (url, after, onEvent, connection) => { const stream = { id: url, after, event: onEvent, connection, closed: false }; streams.push(stream); return () => { stream.closed = true; }; } });
  const a = loader.select("A"); const b = loader.select("B");
  assert.equal(signals[0].aborted, true);
  records.get("B")!.resolve(detail("B")); await b;
  records.get("A")!.resolve(detail("A")); await a;
  assert.deepEqual(ready.map(turn => turn.id), ["B"]); assert.equal(streams.length, 1); assert.equal(streams[0].after, "0");
  const c = loader.select("C"); assert.equal(streams[0].closed, true);
  streams[0].event(event("delta", { text: "Ancienne réponse" })); streams[0].connection("reconnecting"); assert.deepEqual(events, []);
  records.get("C")!.resolve(detail("C")); await c;
  streams[1].event(event("done", { text: "Fin" })); streams[1].connection("connected");
  assert.deepEqual(events, ["C"]); assert.equal(streams[1].closed, true);
  loader.cancel(); assert.equal(signals[2].aborted, true); assert.deepEqual(errors, []);
});

test("unmount/nouvelle question annule le chargement historique et ignore son retour", async () => {
  const pending = deferred<HistoricalQuery>(); let signal: AbortSignal | undefined; let ready = 0; let connected = 0;
  const loader = createHistoryLoader({ detail: (_id, input) => { signal = input; return pending.promise; }, start: () => {}, ready: () => { ready++; }, event: () => {}, connection: () => {}, failure: () => assert.fail("retour annulé"), connect: () => { connected++; return () => {}; } });
  const loading = loader.select("old-query"); loader.cancel(); pending.resolve(detail()); await loading;
  assert.equal(signal?.aborted, true); assert.equal(ready, 0); assert.equal(connected, 0);
});

test("détail 404 ou identité/URL incohérente : erreur visible et aucun flux étranger", async () => {
  const failures: unknown[] = []; let connected = 0;
  for (const value of [new Error("query_not_found"), { ...detail(), query_id: "other" }, { ...detail(), events_url: "https://remote.invalid/events" }]) {
    const loader = createHistoryLoader({ detail: async () => { if (value instanceof Error) throw value; return value; }, start: () => {}, ready: () => assert.fail("détail refusé"), event: () => {}, connection: () => {}, failure: error => failures.push(error), connect: () => { connected++; return () => {}; } });
    await loader.select("old-query"); loader.cancel();
  }
  assert.equal(failures.length, 3); assert.equal(connected, 0);
});

test("sélection d'un tour déjà affiché ne le duplique pas et remplace seulement l'ancien historique", () => {
  const old = historicalTurn(detail()); const normal = { ...historicalTurn(detail("new-query")), historicalState: undefined, mode: "question" };
  const selected = historicalTurn(detail("new-query"));
  const turns = putHistoricalTurn([normal, old], selected);
  assert.deepEqual(turns.map(turn => turn.id), ["new-query"]); assert.equal(turns[0], selected);
});


test("une nouvelle question retire le replay partiel sans le présenter comme une réponse finie", () => {
  const old = applyQueryEvent(historicalTurn(detail()), event("delta", { text: "Ancien texte partiel" }));
  assert.equal(old.connection, "connecting"); assert.equal(old.historicalState, "done"); assert.equal(old.status, "generating");
  const current = { ...historicalTurn(detail("current")), historicalState: undefined, mode: "question" };
  assert.deepEqual(withoutHistoricalTurns([current, old]), [current]);
});

test("le clic historique conserve son registre, sans focus réinjecté dans une question future", () => {
  const record = historicalTurn(detail());
  assert.equal(sourceFocus(record.id, "S004", record.scope, record.scope, true), undefined);
  assert.equal(sourceFocus(record.id, "S004", record.scope, { kind: "library" }), undefined);
  assert.deepEqual(sourceFocus("current", "S004", record.scope, record.scope), { query_id: "current", source_id: "S004" });
});
