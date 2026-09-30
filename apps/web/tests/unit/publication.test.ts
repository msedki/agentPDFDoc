import test from "node:test";
import assert from "node:assert/strict";
import { hasPublishedExtraction } from "../../src/lib/publication.ts";
import type { DocumentDetail } from "../../src/lib/types.ts";

const original: DocumentDetail = { id: "document", folder_id: null, name: "Controlled.pdf", relative_path: "Controlled.pdf", state: "imported", page_count: null, active_generation_id: null, active_version_id: null, versions: [{ id: "new", document_id: "document", sha256: "actual-api-hash", page_count: null, created_at: "2026-09-30" }] };

test("an imported original and verified unpublished partial have no published extraction", () => {
  assert.equal(hasPublishedExtraction(original, "new"), false);
  assert.equal(hasPublishedExtraction({ ...original, state: "ready_partial", jobs: [{ id: "partial", version_id: "new", state: "ready_partial", published: false }] }, "new"), false);
});
test("a different active version does not publish the newly opened original", () => {
  assert.equal(hasPublishedExtraction({ ...original, active_generation_id: "old-generation", active_version_id: "old" }, "new"), false);
});
test("active and archived published generations are both consultable", () => {
  const document = { ...original, active_generation_id: "new-generation", active_version_id: "new", jobs: [{ id: "old-job", version_id: "old", published: true, active: false }] };
  assert.equal(hasPublishedExtraction(document, "new"), true);
  assert.equal(hasPublishedExtraction(document, "old"), true);
  assert.equal(hasPublishedExtraction({ ...document, state: "deleted" }, "new"), false);
});
