/** Le vrai client reçoit un fetch doublé ; aucun appel API ni validation backend réelle. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { api, ApiError } from "../../src/lib/api.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import type { Scope } from "../../src/lib/types.ts";

const limitMessage = "Le périmètre est limité à 1 000 documents sélectionnés. Réduisez la sélection, puis réessayez.";
const fallbackMessage = "Certains paramètres de la demande sont manquants ou incorrects. Vérifiez les champs renseignés, puis réessayez.";

test("validation reply fixtures are bound to the fixed backend formatter literals", () => {
  const source = readFileSync(new URL("../../../../services/api/errors.py", import.meta.url), "utf8");
  for (const message of [limitMessage, fallbackMessage]) assert.ok(source.includes(`return ${JSON.stringify(message)}`), "backend validation copy changed; review the doubled fixture");
});

for (const [kind, message, fields] of [
  ["oversized selection", limitMessage, [{ loc: ["body", "scope", "documentIds"], type: "too_long" }]],
  ["unknown validation failure", fallbackMessage, [{ loc: ["body", "unknown"], type: "unknown" }]],
] as const) {
  test(`a doubled 422 ${kind} keeps the backend message through api.search, ApiError and errorMessage`, async () => {
    const scope: Scope = { kind: "documents", documentIds: Array.from({ length: 1001 }, (_, index) => `synthetic-document-${index}`) };
    const original = globalThis.fetch;
    let calls = 0;
    globalThis.fetch = async (input, options) => {
      calls++;
      assert.equal(input, "/api/v1/search");
      assert.equal(options?.method, "POST");
      assert.equal(options?.credentials, "same-origin");
      assert.equal(options?.cache, "no-store");
      assert.deepEqual(JSON.parse(String(options?.body)), { question: "Recherche synthétique E05", scope });
      return new Response(JSON.stringify({ code: "validation_error", message, details: { fields }, request_id: "synthetic-validation-copy-request" }),
        { status: 422, headers: { "Content-Type": "application/json" } });
    };
    try {
      await assert.rejects(api.search("Recherche synthétique E05", scope), failure => {
        assert.ok(failure instanceof ApiError);
        assert.equal(failure.code, "validation_error");
        assert.equal(failure.requestId, "synthetic-validation-copy-request");
        assert.equal(failure.message, message);
        assert.equal(errorMessage(failure), message);
        return true;
      });
      assert.equal(calls, 1);
    } finally {
      globalThis.fetch = original;
    }
  });
}
