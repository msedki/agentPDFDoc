import assert from "node:assert/strict";
import test from "node:test";
import { importOutcome } from "../../src/lib/import-outcome.ts";

const failure = { relative_path: "corrompu.xlsx", code: "OFFICE_INVALID_XLSX", message: "Le classeur est corrompu." };
test("a mixed Office/PDF import counts actual accepted files and keeps each refusal separate", () => {
  const response = { imports: [{ document_id: "docx", version_id: "v1", job_id: "j1", reused: false }, { document_id: "pdf", version_id: "v2", job_id: "j2", reused: true, job_state: "paused", resume_required: true }], errors: [failure] };
  const outcome = importOutcome(response, 3, 1);
  assert.match(outcome.notice, /^2 documents reçus par le service/);
  assert.match(outcome.notice, /1 fichier refusé/); assert.doesNotMatch(outcome.notice, /3 documents|PDF reçu/);
  assert.deepEqual(outcome.resumeJobs, ["j2"]);
  assert.deepEqual(outcome.rejections, [{ path: failure.relative_path, code: failure.code, message: failure.message }]);
});
test("an entirely refused batch announces no extraction, progress or resumable job", () => {
  const outcome = importOutcome({ imports: [], errors: [failure, { ...failure, relative_path: "autre.docx" }] }, 2, 0);
  assert.match(outcome.notice, /^Aucun document accepté/); assert.match(outcome.notice, /2 fichiers refusés/);
  assert.doesNotMatch(outcome.notice, /extraction|indexation|s'affichent dans le Suivi/);
  assert.deepEqual(outcome.resumeJobs, []); assert.equal(outcome.rejections?.length, 2);
});
