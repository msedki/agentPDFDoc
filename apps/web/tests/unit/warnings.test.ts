import test from "node:test";
import assert from "node:assert/strict";
import { warningText } from "../../src/lib/warnings.ts";

test("structured retrieval warnings display the actual message without passing an object to React", () => {
  assert.equal(warningText({ code: "identifier_not_found_in_scope", identifier: "DA-P01", message: "Référence non retrouvée dans ce périmètre." }), "Référence non retrouvée dans ce périmètre.");
  assert.equal(warningText("Extraction partielle"), "Extraction partielle");
});
test("unknown warning fields are not displayed as arbitrary object content", () => {
  assert.equal(warningText({ code: "partial_extraction", internal_details: "not a user message" }), "partial_extraction");
  assert.equal(warningText(null), "Le service signale une limite.");
});
