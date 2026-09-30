import test from "node:test";
import assert from "node:assert/strict";
import { httpFailureMessage, readinessBlockerText, readinessSentence, serviceDetail, warningText } from "../../src/lib/warnings.ts";
import { errorMessage } from "../../src/lib/utils.ts";

test("structured retrieval warnings display the actual message without passing an object to React", () => {
  assert.equal(warningText({ code: "identifier_not_found_in_scope", identifier: "DA-P01", message: "Référence non retrouvée dans ce périmètre." }), "Référence non retrouvée dans ce périmètre.");
  assert.equal(warningText("Extraction partielle"), "Extraction partielle");
});
test("unknown warning fields are not displayed as arbitrary object content, and a bare code is never shown alone", () => {
  const text = warningText({ code: "partial_extraction", internal_details: "not a user message" });
  assert.equal(text, "Le service signale une limite sans la décrire (code partial_extraction).");
  assert.doesNotMatch(text, /not a user message/);
  assert.notEqual(text, "partial_extraction");
  assert.equal(warningText(null), "Le service signale une limite sans la décrire.");
});
test("readiness blockers are shown with readable labels and unknown codes stay visible for diagnosis", () => {
  assert.equal(readinessBlockerText("qdrant_not_ready"), "Index vectoriel indisponible");
  assert.equal(readinessBlockerText("future_check_not_ready"), "Composant local non prêt (code future_check_not_ready)");
  assert.match(readinessBlockerText("constructor"), /code constructor/, "les propriétés héritées d'Object ne sont pas des libellés");
});
test("the readiness message names the missing components and the command that details them", () => {
  const sentence = readinessSentence(["ollama_not_ready", "qdrant_not_ready"]);
  assert.match(sentence, /^Préparation du poste incomplète : Modèle de réponse indisponible, Index vectoriel indisponible\./);
  assert.match(sentence, /\.\\rag\.ps1 doctor/);
  assert.match(sentence, /toutes les 10 secondes/);
  assert.doesNotMatch(sentence, /_not_ready/);
});
test("an HTTP refusal without service message keeps its status and says what to do", () => {
  assert.equal(httpFailureMessage(409), "Le service local a refusé la demande (HTTP 409).");
  // `rag.ps1 logs` imprime le chemin du journal de chaque service (services/runtime/cli.py), pas son contenu.
  assert.equal(httpFailureMessage(500), "Le service local a échoué (HTTP 500). Réessayez ; si l'échec persiste, consultez son journal : la commande .\\rag.ps1 logs en donne l'emplacement.");
  assert.match(errorMessage("échec sans objet Error"), /consultez le journal du service : la commande \.\\rag\.ps1 logs en donne l'emplacement\.$/);
  for (const message of [httpFailureMessage(503), errorMessage(null)]) assert.doesNotMatch(message, /logs affiche/);
});
test("the service status tooltip explains each state with readable labels", () => {
  assert.equal(serviceDetail({ failed: true, error: "Le service local ne répond pas.", blockers: [], pendingDocuments: 0 }), "Le service local ne répond pas.");
  assert.equal(serviceDetail({ failed: false, ready: false, blockers: ["ollama_not_ready"], pendingDocuments: 0 }), "Non prêts : Modèle de réponse indisponible.");
  assert.equal(serviceDetail({ failed: false, ready: false, blockers: [], pendingDocuments: 0 }), "Le service n'a pas confirmé que ses composants sont prêts.");
  assert.equal(serviceDetail({ failed: false, ready: true, blockers: [], pendingDocuments: 1 }), "1 document attend son indexation : il n'est pas encore interrogeable.");
  assert.match(serviceDetail({ failed: false, ready: true, blockers: [], pendingDocuments: 3 }) ?? "", /^3 documents attendent leur indexation/);
  assert.match(serviceDetail({ failed: false, ready: true, blockers: [], pendingDocuments: 0 }) ?? "", /prêts\.$/);
});
