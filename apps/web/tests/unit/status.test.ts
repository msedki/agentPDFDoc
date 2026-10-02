import assert from "node:assert/strict";
import test from "node:test";
import { documentRecordStatus, documentStatus, isActiveJobState, jobStageLabel, jobStatus, queryStatus, serviceStatus } from "../../src/lib/status.ts";

test("every document state of the API contract has a label and a tone", () => {
  // Liste de packages/contracts/contracts.json (document.state), plus la pause du suivi.
  for (const state of ["imported", "queued", "extracting", "ocr", "indexing", "ready", "ready_partial", "error", "deleted", "paused"]) {
    const status = documentStatus(state);
    assert.equal(status.known, true, state);
    assert.notEqual(status.label, state);
  }
  assert.deepEqual([documentStatus("ready").label, documentStatus("ready").tone], ["Prêt", "success"]);
  assert.deepEqual([documentStatus("error").label, documentStatus("error").tone], ["Erreur", "destructive"]);
});

test("a partial extraction is never labelled as ready", () => {
  // Les recettes E2E attendent « Prêt » pour une publication complète uniquement.
  assert.doesNotMatch(documentStatus("ready_partial").label, /Prêt/);
  assert.equal(documentStatus("ready_partial").tone, "warning");
});

test("an unknown code keeps an explicit label and exposes the raw code for diagnosis only", () => {
  const status = documentStatus("migrating_v3");
  assert.deepEqual(status, { label: "État de document non reconnu", tone: "neutral", code: "migrating_v3", known: false });
  assert.equal(documentStatus(undefined).known, false);
  assert.equal(documentStatus("constructor").known, false, "les propriétés héritées d'Object ne sont pas des états");
  assert.equal(jobStatus("teleporting").label, "État de traitement non reconnu");
  assert.equal(queryStatus("thinking").label, "Statut de réponse non reconnu");
});

test("query terminal labels keep the wording read by the E2E scenarios", () => {
  const terminal = /Réponse terminée|Réponse limitée|Échec|Réponse annulée|Réponse interrompue|Précision nécessaire|Preuves insuffisantes/;
  for (const status of ["done", "completed", "length", "length_limited", "error", "cancelled", "interrupted", "needs_clarification", "insufficient_evidence"]) assert.match(queryStatus(status).label, terminal, status);
  for (const status of ["created", "queued", "searching", "generating", "waiting_for_resources"]) assert.doesNotMatch(queryStatus(status).label, terminal, status);
});

test("job states written by the service during pause and cancellation are translated", () => {
  for (const state of ["pausing", "paused", "checkpointed", "interrupted", "cancelling", "cancelled", "running", "failed"]) assert.equal(jobStatus(state).known, true, state);
  assert.equal(jobStatus("paused").label, "Indexation en pause — reprise manuelle");
  assert.equal(isActiveJobState("indexing"), true);
  assert.equal(isActiveJobState("ready_partial"), true, "une extraction partielle attend encore une décision de publication");
  for (const state of ["done", "completed", "ready", "cancelled", "error", "failed"]) assert.equal(isActiveJobState(state), false, state);
});

test("job stages are shown only when known and different from the state", () => {
  assert.equal(jobStageLabel("vectors", "indexing"), "vectorisation et écriture dans l'index");
  assert.equal(jobStageLabel("extracting", "extracting"), null);
  assert.equal(jobStageLabel("unknown_stage", "indexing"), null);
  assert.equal(jobStageLabel(undefined, "queued"), null);
});

test("service availability names its four states in text: unreachable, not ready, index lagging, ready", () => {
  const view = (probe: Parameters<typeof serviceStatus>[0]) => { const status = serviceStatus(probe); return [status.label, status.tone, status.code]; };
  assert.deepEqual(view({ loading: true, failed: false }), ["Connexion au service local…", "neutral", "connecting"]);
  assert.deepEqual(view({ loading: false, failed: true }), ["Service local injoignable", "destructive", "unreachable"]);
  assert.deepEqual(view({ loading: false, failed: true, unreachable: false }), ["Service local en erreur", "destructive", "error"], "une réponse en erreur n'est pas une coupure");
  assert.deepEqual(view({ loading: false, failed: false, ready: false }), ["Service local pas encore prêt", "warning", "not_ready"]);
  assert.deepEqual(view({ loading: false, failed: false }), ["Service local pas encore prêt", "warning", "not_ready"], "sans confirmation, le service n'est pas présenté comme prêt");
  assert.deepEqual(view({ loading: false, failed: false, ready: true, pendingDocuments: 2 }), ["Index incomplet", "warning", "index_lagging"]);
  assert.deepEqual(view({ loading: false, failed: false, ready: true, pendingDocuments: 0 }), ["Services prêts", "success", "ready"]);
  // Un service non prêt reste signalé comme tel, même si des documents attendent aussi leur indexation.
  assert.equal(serviceStatus({ loading: false, failed: false, ready: false, pendingDocuments: 3 }).code, "not_ready");
  // Aucun libellé d'état de service ne reprend son code technique.
  for (const probe of [{ loading: true, failed: false }, { loading: false, failed: true }, { loading: false, failed: false, ready: true, pendingDocuments: 1 }]) {
    const status = serviceStatus(probe);
    assert.notEqual(status.label, status.code);
  }
});

test("a partial extraction awaiting publication and a cancelled treatment have their own labels", () => {
  assert.equal(documentRecordStatus({ state: "ready_partial", active_generation_id: null }).label, "Extraction partielle à publier");
  assert.equal(documentRecordStatus({ state: "ready_partial", active_generation_id: "g" }).label, "Extraction partielle");
  assert.equal(documentRecordStatus({ state: "cancelled", active_generation_id: null }).label, "Traitement annulé");
  assert.equal(documentRecordStatus({ state: "cancelled", active_generation_id: null }).known, true);
});
