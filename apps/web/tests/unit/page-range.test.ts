import assert from "node:assert/strict";
import test from "node:test";
import { pageRangeError, versionPageCount } from "../../src/lib/page-range.ts";
import type { DocumentDetail } from "../../src/lib/types.ts";

// L'API renvoie page_count du document depuis sa version active (services/api/main.py, document_rows).
const document: DocumentDetail = {
  id: "document", folder_id: null, name: "Procédure.pdf", relative_path: "Procédure.pdf", state: "ready", page_count: 14,
  active_version_id: "v2", version_id: "v2", active_generation_id: "g2",
  versions: [
    { id: "v2", document_id: "document", sha256: "b".repeat(64), page_count: 14, created_at: "2026-09-30T10:00:00Z" },
    { id: "v1", document_id: "document", sha256: "a".repeat(64), page_count: 4, created_at: "2026-09-29T10:00:00Z" },
    { id: "v0", document_id: "document", sha256: "c".repeat(64), page_count: null, created_at: "2026-09-28T10:00:00Z" },
  ],
};

test("an older opened version is validated against its own page count, not the active document count", () => {
  assert.equal(versionPageCount(document, "v1"), 4);
  assert.equal(versionPageCount(document, "v2"), 14);
  assert.match(pageRangeError(5, 10, versionPageCount(document, "v1"))!, /version ouverte \(1 à 4\)/);
  assert.equal(pageRangeError(1, 4, versionPageCount(document, "v1")), null);
  assert.equal(pageRangeError(5, 10, versionPageCount(document, "v2")), null);
});

test("an unknown version page count refuses the range instead of borrowing another count", () => {
  assert.equal(versionPageCount(document, "v0"), null);
  assert.equal(versionPageCount(document, "missing"), null);
  assert.equal(versionPageCount(undefined, "v1"), null);
  assert.match(pageRangeError(1, 1, null)!, /pas encore connu/);
});

test("inverted, zero and fractional ranges are refused", () => {
  for (const [start, end] of [[0, 1], [3, 2], [1.5, 2], [1, Number.NaN]]) assert.ok(pageRangeError(start, end, 4), `${start}-${end}`);
});
