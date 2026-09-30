import assert from "node:assert/strict";
import test from "node:test";
import { citationLinkIds, registeredCitationLocation } from "../../src/lib/citation-link.ts";
import type { Source } from "../../src/lib/types.ts";

test("citation deep links require both safe IDs and never treat partial links as document navigation", () => {
  assert.equal(citationLinkIds(new URLSearchParams("document=document&version=version")), null);
  assert.deepEqual(citationLinkIds(new URLSearchParams("citation_query=query-old&citation_source=S001")), { queryId: "query-old", sourceId: "S001" });
  assert.throws(() => citationLinkIds(new URLSearchParams("citation_query=query-old")));
  assert.throws(() => citationLinkIds(new URLSearchParams("citation_query=query-old&citation_source=..%2Fother")));
});

test("registered citation location rejects wrong registry identity, missing revision and unknown page", () => {
  const source: Source = { document_id: "document", version_id: "version-old", query_id: "query-old", source_id: "S001", extraction_revision_id: "revision-old", page_index: 2, text: "Ancienne preuve" };
  assert.deepEqual(registeredCitationLocation(source, "query-old", "S001"), { documentId: "document", versionId: "version-old", pageIndex: 2 });
  assert.throws(() => registeredCitationLocation(source, "query-other", "S001"));
  assert.throws(() => registeredCitationLocation(source, "query-old", "S002"));
  assert.throws(() => registeredCitationLocation({ ...source, extraction_revision_id: undefined }, "query-old", "S001"));
  assert.throws(() => registeredCitationLocation({ ...source, page_index: undefined }, "query-old", "S001"));
  assert.throws(() => registeredCitationLocation({ ...source, document_id: undefined } as unknown as Source, "query-old", "S001"));
});
