import assert from "node:assert/strict";
import test from "node:test";
import { doneEvent, registeredCitationIds } from "../e2e/answer-citations.ts";

const sse = (...events: { type: string; data: unknown }[]) => events.map((event, index) => `id: ${index + 1}\nevent: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`).join("");

test("2B answer of the R26-KIT-02 recette: source IDs in warnings are not registered citations (D2)", () => {
  // Shape of the replayed done event of query ce0013ed (05a-sse-2b.txt): no citation, five IDs named in a warning.
  const done = doneEvent(sse(
    { type: "status", data: { state: "generating" } },
    { type: "sources", data: { sources: ["S001", "S002", "S003", "S004", "S005"].map(source_id => ({ source_id, page_index: 0 })) } },
    { type: "done", data: { status: "done", text: "La pression nominale de DA-P01 est de **3.1 bar** (preuve S001).", citations: [],
      warnings: [{ code: "answer_without_valid_citation" }, { code: "source_id_mentioned_without_citation", source_ids: ["S001", "S002", "S003", "S004", "S005"] }] } },
  ));
  assert.ok(done);
  assert.deepEqual(registeredCitationIds(done), []);
});

test("4B answer: the registered citation of the done event is kept", () => {
  const done = doneEvent(sse({ type: "done", data: { status: "done", text: "… 3,1 bar. [S001]", citations: [{ source_id: "S001", page_index: 0 }] } }));
  assert.deepEqual(registeredCitationIds(done), ["S001"]);
});

test("replay parsing: CRLF separators, multi-line data and absent done event", () => {
  const crlf = "id: 1\r\nevent: delta\r\ndata: {\"text\":\"a\"}\r\n\r\nid: 2\r\nevent: done\r\ndata: {\"citations\":\r\ndata: [{\"source_id\":\"S002\"}]}\r\n\r\n";
  assert.deepEqual(registeredCitationIds(doneEvent(crlf)), ["S002"]);
  assert.equal(doneEvent(sse({ type: "error", data: { status: "error" } })), null);
  assert.deepEqual(registeredCitationIds(null), []);
  assert.deepEqual(registeredCitationIds({ citations: [{ page_index: 0 }, { source_id: "" }] }), []);
});
