import assert from "node:assert/strict";
import test from "node:test";
import { activeJobsBadge, activeJobsSentence, coverageSentence, isQueryableDocument, isQueryableDocumentState, isServiceUnavailable, libraryView, pendingIndexCount, scopeCoverage, scopeDocuments, scopeKindLabel, selectedDocumentsSentence, unindexedInScope, unindexedSentence } from "../../src/lib/panel-state.ts";
import { isActiveJobState } from "../../src/lib/status.ts";
import type { DocumentRecord, LibraryTree } from "../../src/lib/types.ts";

const view = (input: Partial<Parameters<typeof libraryView>[0]>) => libraryView({ hasData: true, failed: false, total: 3, visible: 3, filtering: false, ...input });

test("a failed library read without data is an outage, never an empty library", () => {
  assert.equal(view({ hasData: false, failed: true, total: 0, visible: 0 }), "unavailable");
  assert.equal(view({ hasData: false, failed: false, total: 0, visible: 0 }), "loading");
});

test("a failed refresh keeps the documents already received", () => {
  assert.equal(view({ failed: true }), "content");
});

test("an empty library and a filter without match are distinct states", () => {
  assert.equal(view({ total: 0, visible: 0 }), "no-documents");
  assert.equal(view({ total: 0, visible: 0, filtering: true }), "no-documents");
  assert.equal(view({ visible: 0, filtering: true }), "no-match");
  assert.equal(view({ visible: 1, filtering: true }), "content");
});

// Comme l'API : une génération publiée pour les documents prêts ou partiels publiés, null sinon.
const documentRecord = (id: string, state: DocumentRecord["state"], folder: string | null, version = `v-${id}`, generation: string | null = ["ready", "ready_partial"].includes(String(state)) ? `g-${id}` : null): DocumentRecord => ({ id, folder_id: folder, name: `${id}.pdf`, relative_path: `${id}.pdf`, state, active_version_id: version, active_generation_id: generation, page_count: 1 });
const tree: LibraryTree = {
  folders: [{ id: "root", parent_id: null, name: "root", path: "root" }, { id: "child", parent_id: "root", name: "child", path: "root/child" }, { id: "loop-a", parent_id: "loop-b", name: "a", path: "a" }, { id: "loop-b", parent_id: "loop-a", name: "b", path: "b" }, { id: "other", parent_id: null, name: "other", path: "other" }],
  documents: [documentRecord("ready", "ready", "root"), documentRecord("partial", "ready_partial", "child"), documentRecord("indexing", "indexing", "child"), documentRecord("removed", "deleted", "root"), documentRecord("loose", "queued", null), documentRecord("looped", "ocr", "loop-a"), documentRecord("elsewhere", "error", "other")],
};

test("scope documents follow folders recursively, ignore removed documents and survive folder cycles", () => {
  assert.deepEqual(scopeDocuments({ kind: "folder", folderId: "root", recursive: true }, tree).map(document => document.id), ["ready", "partial", "indexing"]);
  assert.deepEqual(scopeDocuments({ kind: "folder", folderId: "loop-a", recursive: true }, tree).map(document => document.id), ["looped"]);
  assert.deepEqual(scopeDocuments({ kind: "documents", documentIds: ["partial", "removed"] }, tree).map(document => document.id), ["partial"]);
  assert.deepEqual(scopeDocuments({ kind: "pages", versionId: "v-indexing", pageStart: 0, pageEnd: 0 }, tree).map(document => document.id), ["indexing"]);
  assert.equal(scopeDocuments({ kind: "library" }, tree).length, 6);
});

test("an incomplete index counts documents of the scope that are not queryable yet", () => {
  assert.equal(isQueryableDocumentState("ready_partial"), true);
  assert.equal(isQueryableDocumentState("indexing"), false);
  assert.equal(unindexedInScope({ kind: "folder", folderId: "root", recursive: true }, tree), 1);
  assert.equal(unindexedInScope({ kind: "library" }, tree), 4);
  assert.equal(unindexedInScope({ kind: "documents", documentIds: ["ready", "partial"] }, tree), 0);
  assert.equal(unindexedInScope({ kind: "selection", versionId: "unknown-version", spans: [] }, tree), 0);
});

test("outages are told apart from business refusals", () => {
  assert.equal(isServiceUnavailable(new TypeError("Failed to fetch")), true);
  assert.equal(isServiceUnavailable({ code: "NETWORK_ERROR" }), true);
  assert.equal(isServiceUnavailable({ code: "HTTP_503" }), true);
  assert.equal(isServiceUnavailable({ code: "document_not_found" }), false);
  assert.equal(isServiceUnavailable({ code: "HTTP_409" }), false);
  assert.equal(isServiceUnavailable(null), false);
});

test("counts are written with French agreement", () => {
  assert.equal(selectedDocumentsSentence(0), "Aucun document sélectionné");
  assert.equal(selectedDocumentsSentence(1), "1 document sélectionné");
  assert.equal(selectedDocumentsSentence(3), "3 documents sélectionnés");
  assert.equal(unindexedSentence(1), "1 document de ce périmètre n'est pas encore interrogeable");
  assert.equal(unindexedSentence(2), "2 documents de ce périmètre ne sont pas encore interrogeables");
});

test("scope coverage counts queryable documents and groups exclusions by reason in a fixed order", () => {
  // Bibliothèque : ready, partial (interrogeables) ; indexing, loose/queued, looped/ocr (traitement) ; elsewhere (erreur) ; removed ignoré.
  assert.deepEqual(scopeCoverage({ kind: "library" }, tree), { queryable: 2, excluded: [{ reason: "processing", count: 3 }, { reason: "error", count: 1 }] });
  assert.deepEqual(scopeCoverage({ kind: "documents", documentIds: ["ready", "partial"] }, tree), { queryable: 2, excluded: [] });
  const withPause: LibraryTree = { folders: [], documents: [documentRecord("held", "paused" as DocumentRecord["state"], null), documentRecord("odd", "migrating" as DocumentRecord["state"], null)] };
  assert.deepEqual(scopeCoverage({ kind: "library" }, withPause), { queryable: 0, excluded: [{ reason: "paused", count: 1 }, { reason: "unknown", count: 1 }] });
});

test("the coverage sentence states queryable and excluded documents with their reasons", () => {
  assert.equal(coverageSentence(scopeCoverage({ kind: "library" }, tree)), "2 documents interrogeables · 4 exclus : 3 en cours de traitement, 1 en erreur");
  assert.equal(coverageSentence({ queryable: 1, excluded: [] }), "1 document interrogeable");
  assert.equal(coverageSentence({ queryable: 0, excluded: [{ reason: "paused", count: 1 }] }), "Aucun document interrogeable · 1 exclu : 1 indexation en pause");
  assert.equal(coverageSentence({ queryable: 0, excluded: [] }), "Aucun document dans ce périmètre");
});

test("every scope kind has a chip label distinct from its technical kind", () => {
  const kinds = ["library", "folder", "documents", "section", "pages", "selection"] as const;
  const labels = kinds.map(scopeKindLabel);
  assert.equal(new Set(labels).size, kinds.length);
  kinds.forEach((kind, index) => assert.notEqual(labels[index], kind));
});

test("documents waiting for indexing make the index lag; ready, partial, failed and removed ones do not", () => {
  // indexing, loose (queued) et looped (ocr) attendent leur index ; elsewhere est en erreur, removed est retiré.
  assert.equal(pendingIndexCount(tree), 3);
  assert.equal(pendingIndexCount({ folders: [], documents: [documentRecord("held", "paused" as DocumentRecord["state"], null)] }), 1);
  assert.equal(pendingIndexCount({ folders: [], documents: [documentRecord("done", "ready", null), documentRecord("half", "ready_partial", null)] }), 0);
});

test("the Suivi counter is capped at 99+ and its sentence agrees in number", () => {
  assert.equal(activeJobsBadge(1), "1");
  assert.equal(activeJobsBadge(99), "99");
  assert.equal(activeJobsBadge(100), "99+");
  assert.equal(activeJobsSentence(0), "Aucun traitement à suivre");
  assert.equal(activeJobsSentence(1), "1 traitement à suivre");
  assert.equal(activeJobsSentence(120), "120 traitements à suivre");
  // Le compte inclut des traitements arrêtés en attente de reprise ou de publication : ils ne sont pas « actifs ».
  for (const state of ["paused", "checkpointed", "interrupted", "ready_partial"]) assert.equal(isActiveJobState(state), true, state);
  for (const count of [0, 1, 120]) assert.doesNotMatch(activeJobsSentence(count), /actif/);
});

test("an unpublished partial extraction is not queryable and is counted apart", () => {
  const pending = documentRecord("half", "ready_partial", null, "v-half", null);
  assert.equal(isQueryableDocument(pending), false);
  assert.equal(isQueryableDocument(documentRecord("published", "ready_partial", null)), true);
  const partialTree: LibraryTree = { folders: [], documents: [pending, documentRecord("done", "ready", null), documentRecord("stopped", "cancelled" as DocumentRecord["state"], null)] };
  assert.deepEqual(scopeCoverage({ kind: "library" }, partialTree), { queryable: 1, excluded: [{ reason: "unpublished", count: 1 }, { reason: "cancelled", count: 1 }] });
  assert.equal(coverageSentence(scopeCoverage({ kind: "library" }, partialTree)), "1 document interrogeable · 2 exclus : 1 extraction partielle à publier, 1 traitement annulé");
  assert.equal(unindexedInScope({ kind: "library" }, partialTree), 2);
});
