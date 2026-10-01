/**
 * Réponse de POST /documents/{id}/reindex (contrat `reindex_response` et `reindex_outcomes`) : selon le
 * dernier traitement du document, le service renvoie le traitement en cours (`reused`), renvoie le
 * traitement en pause avec `resume_required`, refuse la demande pendant une mise en pause (409
 * `job_pausing`) ou crée un traitement neuf, y compris pendant une annulation. L'atelier dit ce que le
 * service a réellement fait et ne propose la reprise que d'un traitement `paused`.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { api, ApiError } from "../../src/lib/api.ts";
import { reindexOutcome, SUSPENDED_REINDEX_STATES } from "../../src/lib/reindex.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const contract = JSON.parse(readFileSync(new URL("../../../../packages/contracts/contracts.json", import.meta.url), "utf8"));
const STARTED = "Réindexation demandée : sa progression s'affiche dans le Suivi.";
const RUNNING = "Un traitement de ce document est déjà en cours : aucune nouvelle réindexation n'a été lancée. Sa progression s'affiche dans le Suivi.";
const PAUSED = "Le dernier traitement de ce document est en pause : la réindexation n'en lance pas un second. Reprenez-le pour poursuivre l'indexation depuis son dernier point de reprise.";
// Message du service (services/api/main.py, reindex_document), affiché tel quel sous le bouton.
const PAUSING_MESSAGE = "Mise en pause en cours pour ce document : attendez qu'elle aboutisse, puis reprenez ce traitement depuis le Suivi.";

test("the pausing message of the fixture is the one the service sends", () => {
  // Une fixture périmée ferait vérifier l'affichage d'un message que le service n'envoie plus.
  const service = readFileSync(new URL("../../../../services/api/main.py", import.meta.url), "utf8");
  assert.ok(service.includes(`ApiError("job_pausing", ${JSON.stringify(PAUSING_MESSAGE)}, 409`), "PAUSING_MESSAGE diffère du message 409 job_pausing de services/api/main.py");
});

test("the suspended job states handled are those of the contract", () => {
  const field: string = contract.reindex_response.job_state;
  assert.deepEqual([...SUSPENDED_REINDEX_STATES], field.split(",")[0].split("|"));
  assert.match(contract.reindex_response.resume_required, /POST \/jobs\/\{job_id\}\/resume/);
});

test("every last job state of the contract gets the notice of what the service did", () => {
  const outcomes: Record<string, { status: number; fields?: string; reused?: boolean }> = contract.reindex_outcomes;
  // Les issues couvrent chaque état de traitement du contrat, une seule fois.
  const covered = Object.keys(outcomes).flatMap(key => key.split("|"));
  assert.deepEqual([...covered].sort(), contract.job.state.split("|").sort());
  assert.equal(new Set(covered).size, covered.length);
  for (const [states, outcome] of Object.entries(outcomes)) {
    if (outcome.status === 409) continue; // Refus : voir le test du 409 job_pausing ci-dessous.
    assert.equal(outcome.status, 202, states);
    const fields = outcome.fields!.split("|");
    const response = { job_id: "j1", reused: outcome.reused!, ...(fields.includes("version_id") ? { version_id: "v1" } : {}),
      ...(fields.includes("job_state") ? { job_state: states } : {}), ...(fields.includes("resume_required") ? { resume_required: true } : {}) };
    const expected = response.resume_required ? { kind: "resume", jobId: "j1", message: PAUSED } : response.reused ? { kind: "running", message: RUNNING } : { kind: "started", message: STARTED };
    assert.deepEqual(reindexOutcome(response), expected, states);
  }
});

test("a reindexing during a cancellation starts a new job and keeps the former notice", () => {
  assert.match(contract.reindex_outcomes["cancelling|cancelled|error|ready|ready_partial"].rule, /new queued job/);
  assert.deepEqual(reindexOutcome({ job_id: "j9", version_id: "v1", reused: false }), { kind: "started", message: STARTED });
});

test("a job already running is reported as such, without claiming a new reindexing", () => {
  assert.deepEqual(reindexOutcome({ job_id: "j1", reused: true }), { kind: "running", message: RUNNING });
});

test("a paused job of the version is offered for resumption instead of a notice that nothing will follow", () => {
  const outcome = reindexOutcome({ job_id: "j2", version_id: "v1", reused: true, job_state: "paused", resume_required: true });
  assert.deepEqual(outcome, { kind: "resume", jobId: "j2", message: PAUSED });
  assert.doesNotMatch(outcome.message, /Réindexation demandée/);
});

test("a suspended state other than paused is never offered for resumption", () => {
  // Le service ne renvoie que `paused` ; un autre état (version ultérieure du service) renvoie au Suivi sans
  // proposer une reprise que POST /jobs/{job_id}/resume refuserait.
  for (const state of ["pausing", "cancelling", "checkpoint_v9"]) {
    assert.deepEqual(reindexOutcome({ job_id: "j5", reused: true, job_state: state, resume_required: true }),
      { kind: "wait", message: `Un traitement suspendu de ce document existe déjà (état ${state}) : aucune nouvelle réindexation n'a été lancée. Consultez le Suivi pour le reprendre.` });
  }
  assert.deepEqual(reindexOutcome({ job_id: "j6", reused: true, resume_required: true }),
    { kind: "wait", message: "Un traitement suspendu de ce document existe déjà (état non communiqué) : aucune nouvelle réindexation n'a été lancée. Consultez le Suivi pour le reprendre." });
});

test("a 409 job_pausing reaches the button as the service message, whatever the launcher commands", async () => {
  const refusal = contract.reindex_outcomes.pausing;
  assert.equal(refusal.status, 409);
  assert.equal(refusal.error.code, "job_pausing");
  const original = globalThis.fetch;
  const calls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push(`${init?.method} ${String(input)}`);
    return new Response(JSON.stringify({ code: "job_pausing", message: PAUSING_MESSAGE, details: { job_id: "j3", version_id: "v1", job_state: "pausing" }, request_id: "r1" }), { status: 409, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  let failure: unknown;
  try {
    await api.reindex("d1");
  } catch (error) {
    failure = error;
  } finally {
    globalThis.fetch = original;
  }
  assert.deepEqual(calls, ["POST /api/v1/documents/d1/reindex"]);
  assert.ok(failure instanceof ApiError);
  assert.equal(failure.code, "job_pausing");
  assert.equal(failure.requestId, "r1");
  for (const commands of [null, { doctor: ".\\rag.ps1 doctor" }, { doctor: "./rag.sh doctor" }]) assert.equal(errorMessage(failure, commands), PAUSING_MESSAGE);
});

test("the document tools read the reindex reply, let the button show a refusal and offer the resumption of a paused job", () => {
  const tools = stripScriptComments(readSource("components/document-tools.tsx"));
  assert.match(tools, /reindexOutcome\(await api\.reindex\(document\.id\)\)/);
  // Le refus (409 job_pausing) n'est pas intercepté : l'ActionButton de la réindexation l'affiche sous le bouton.
  assert.match(tools, /<ActionButton [^>]*onAction=\{reindex\}/);
  assert.doesNotMatch(/const reindex = async \(\) => \{[\s\S]*?\n {2}\};/.exec(tools)?.[0] ?? "", /catch/);
  const button = stripScriptComments(readSource("components/ui/action-button.tsx"));
  assert.match(button, /catch \(caught\) \{ setFailure\(\{ error: caught \}\); \}/);
  assert.match(button, /const errorText = useErrorText\(\);/);
  assert.match(tools, /api\.resumeJob\(resumeJob\)/);
  assert.match(tools, />Reprendre le traitement</);
  assert.doesNotMatch(tools, /setNotice\("Réindexation demandée/);
});
