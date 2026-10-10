/** Explicit fetch doubles test the browser contract only; they do not qualify ingestion or RAG. */
import assert from "node:assert/strict";
import test from "node:test";
import { api } from "../../src/lib/api.ts";
import type { Scope } from "../../src/lib/types.ts";

test("Office GETs encode opaque part IDs and retain exact revision/window/known block anchor", async () => {
  const previous = globalThis.fetch;
  const unit = { id: "unit-123", part: "word/document.xml", kind: "docx_part", title: "Document", order_index: 0, metadata: {} };
  const seen: URL[] = [];
  globalThis.fetch = async (input, options) => {
    const url = new URL(String(input), "http://127.0.0.1"); seen.push(url);
    assert.equal(options?.credentials, "same-origin"); assert.equal(options?.cache, "no-store");
    assert.equal(url.searchParams.get("extraction_revision_id"), "revision-old");
    const response = url.pathname.endsWith("/representation")
      ? { version_id: "version", extraction_revision_id: "revision-old", format: "docx", units: [unit], next_cursor: null, total: 1, metadata: {}, warnings: [], coverage: {}, limits: {} }
      : url.pathname.endsWith("/blocks") ? { version_id: "version", extraction_revision_id: "revision-old", unit, blocks: [], cursor: 88, next_cursor: null, total: 88 }
        : { version_id: "version", extraction_revision_id: "revision-old", sheet_id: "xlsx:xl/worksheets/sheet1.xml", bounds: { row_start: 2, row_end: 3, column_start: 2, column_end: 4 }, cells: [], metadata: {}, warnings: [] };
    return Response.json(response);
  };
  try {
    await api.representation("version", undefined, "revision-old", 50);
    await api.officeBlocks("version", unit.id, "revision-old", 0, undefined, "docx-known-source-block");
    await api.officeCells("version", "xlsx:xl/worksheets/sheet1.xml", "revision-old", { rowStart: 2, rowEnd: 3, columnStart: 2, columnEnd: 4 });
    assert.equal(seen[0].searchParams.get("cursor"), "50"); assert.equal(seen[0].searchParams.get("limit"), "50");
    assert.equal(seen[1].searchParams.get("block_id"), "docx-known-source-block");
    assert.match(seen[2].pathname, /xlsx%3Axl%2Fworksheets%2Fsheet1\.xml\/cells$/);
    assert.deepEqual(Object.fromEntries([...seen[2].searchParams].filter(([key]) => key !== "extraction_revision_id")), { row_start: "2", row_end: "3", column_start: "2", column_end: "4" });
    assert.equal(api.assetUrl("version", "a".repeat(64), "revision-old"), `/api/v1/versions/version/assets/${"a".repeat(64)}?extraction_revision_id=revision-old`);
  } finally { globalThis.fetch = previous; }
});

test("a stale Office response is rejected instead of entering the current revision cache", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ version_id: "version", extraction_revision_id: "current", format: "xlsx", units: [] });
  try { await assert.rejects(api.representation("version", undefined, "old"), /Aucune révision récente/); }
  finally { globalThis.fetch = previous; }
});

test("range scopes use numeric source coordinates and exact revision in the existing search contract", async () => {
  const previous = globalThis.fetch;
  const scope: Scope = { kind: "cell_range", versionId: "version", extractionRevisionId: "old", sheetId: "xlsx:xl/worksheets/sheet1.xml", rowStart: 2, rowEnd: 3, columnStart: 2, columnEnd: 4 };
  globalThis.fetch = async (input, options) => {
    assert.equal(input, "/api/v1/search"); assert.equal(options?.method, "POST");
    assert.deepEqual(JSON.parse(String(options?.body)), { question: "Budget", scope });
    assert.equal("cell_range" in JSON.parse(String(options?.body)).scope, false);
    return Response.json({ results: [], warnings: [], scope_snapshot: scope, elapsed_ms: 1 });
  };
  try { await api.search("Budget", scope); }
  finally { globalThis.fetch = previous; }
});
