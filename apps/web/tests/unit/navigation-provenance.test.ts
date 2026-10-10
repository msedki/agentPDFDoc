import assert from "node:assert/strict";
import test from "node:test";
import { isPdfLocation, useWorkspace } from "../../src/lib/store.ts";
import type { Source } from "../../src/lib/types.ts";

const archived: Source = { document_id: "document", version_id: "version", query_id: "query-old", source_id: "S001", extraction_revision_id: "revision-old", page_index: 1, text: "Ancienne preuve" };
const current: Source = { ...archived, query_id: "query-current", extraction_revision_id: "revision-current", page_index: 3, text: "Preuve actuelle" };

function reset() { useWorkspace.setState(useWorkspace.getInitialState(), true); }

test("return between citations retains their respective extraction revisions and the explicit scope", () => {
  reset();
  const scope = { kind: "documents" as const, documentIds: ["scope-document"] };
  useWorkspace.getState().setScope(scope, "Périmètre choisi");
  useWorkspace.getState().open({ documentId: "document", versionId: "version", pageIndex: 1 }, archived);
  useWorkspace.getState().open({ documentId: "document", versionId: "version", pageIndex: 3 }, current);
  useWorkspace.getState().back();
  assert.deepEqual(useWorkspace.getState().source, archived);
  const before = useWorkspace.getState().opened; assert.ok(isPdfLocation(before)); assert.equal(before.pageIndex, 1);
  assert.deepEqual(useWorkspace.getState().scope, scope);
  assert.equal(useWorkspace.getState().scopeLabel, "Périmètre choisi");
  useWorkspace.getState().back();
  assert.deepEqual(useWorkspace.getState().source, current);
  const after = useWorkspace.getState().opened; assert.ok(isPdfLocation(after)); assert.equal(after.pageIndex, 3);
});

test("ordinary navigation can return to an archived citation and retains its own unpinned state", () => {
  reset();
  useWorkspace.getState().open({ documentId: "document", versionId: "version", pageIndex: 1 }, archived);
  useWorkspace.getState().open({ documentId: "other", versionId: "other-version", pageIndex: 0 });
  assert.equal(useWorkspace.getState().source, null);
  useWorkspace.getState().back();
  assert.deepEqual(useWorkspace.getState().source, archived);
  useWorkspace.getState().back();
  assert.equal(useWorkspace.getState().source, null);
  assert.equal(useWorkspace.getState().opened?.versionId, "other-version");
  useWorkspace.getState().close();
  useWorkspace.getState().back();
  assert.equal(useWorkspace.getState().opened, null);
  assert.equal(useWorkspace.getState().source, null);
});
