/**
 * Réponse de POST /documents/import (contrat `import_response` et `import_outcomes`) :
 * `{imports: [{document_id, version_id, job_id, reused}]}`. Un fichier identique déjà importé au même chemin
 * dont le dernier traitement est en file, en cours ou terminé ne relance rien : ce traitement est renvoyé avec
 * `reused: true`, sans `job_state`. S'il est `paused` ou `pausing`, le service renvoie ce traitement avec
 * `job_state`, et `resume_required: true` pour `paused` seulement, seul état que POST /jobs/{job_id}/resume
 * accepte. Pendant `cancelling`, l'annulation reste définitive et un traitement neuf est mis en file.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { IMPORT_SUSPENDED_STATES, importOutcome, resumedNotice, resumeLabel } from "../../src/lib/import-outcome.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const contract = JSON.parse(readFileSync(new URL("../../../../packages/contracts/contracts.json", import.meta.url), "utf8"));
const created = (index: number) => ({ document_id: `d${index}`, version_id: `v${index}`, job_id: `j${index}`, reused: false });
// Contenu identique au même chemin, dernier traitement `queued`, `extracting`, `indexing`, `ready` ou `ready_partial` : renvoyé tel quel.
const reused = (index: number) => ({ ...created(index), reused: true });
// Entrée de l'import pour un traitement suspendu, telle que le contrat la décrit : `resume_required` pour `paused` seulement.
const suspended = (index: number, job_state: string) => ({ document_id: `d${index}`, version_id: `v${index}`, job_id: `j${index}`, reused: true, job_state, ...(job_state === "paused" ? { resume_required: true } : {}) });

test("an import without refusal reports accepted documents and their real jobs", () => {
  assert.deepEqual(importOutcome({ imports: [created(1)] }, 1, 0), { notice: "1 document reçu par le service. Son extraction et son indexation s'affichent dans le Suivi.", resumeJobs: [] });
  assert.deepEqual(importOutcome({ imports: [created(1), created(2), created(3)] }, 3, 2), { notice: "3 documents reçus par le service ; 2 fichiers non pris en charge ignorés. Leur extraction et leur indexation s'affichent dans le Suivi.", resumeJobs: [] });
  // Réponse illisible : le nombre de fichiers envoyés suffit à l'avis d'avant, sans reprise proposée.
  for (const response of [null, undefined, "ok", {}, { imports: "x" }, { imports: [null, 3] }]) {
    assert.deepEqual(importOutcome(response, 2, 0), { notice: "2 documents reçus par le service. Leur extraction et leur indexation s'affichent dans le Suivi.", resumeJobs: [] }, JSON.stringify(response));
  }
});

test("a reimported file whose last job is queued, running or finished starts nothing and the notice says so", () => {
  // Le service renvoie ce dernier traitement avec `reused: true`, sans `job_state` : il ne dit pas s'il est terminé.
  assert.match(contract.import_outcomes["queued|extracting|indexing|ready|ready_partial"].rule, /no job is created/);
  assert.deepEqual(importOutcome({ imports: [reused(1)] }, 1, 1), {
    notice: "1 document reçu par le service ; 1 fichier non pris en charge ignoré. Ce fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement. "
      + "Son état s'affiche dans la bibliothèque ; pour le traiter de nouveau, ouvrez-le puis choisissez « Réindexer ce document ».",
    resumeJobs: [] });
  assert.deepEqual(importOutcome({ imports: [reused(1), reused(2)] }, 2, 0), {
    notice: "2 documents reçus par le service. 2 fichiers étaient déjà importés à l'identique : l'import ne lance aucun nouveau traitement pour eux. "
      + "Leur état s'affiche dans la bibliothèque ; pour traiter de nouveau l'un d'eux, ouvrez-le puis choisissez « Réindexer ce document ».",
    resumeJobs: [] });
  assert.deepEqual(importOutcome({ imports: [created(1), reused(2), suspended(3, "paused")] }, 3, 0), {
    notice: "3 documents reçus par le service. L'extraction et l'indexation de l'autre fichier s'affichent dans le Suivi. "
      + "Un fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement pour lui. Son état s'affiche dans la bibliothèque ; pour le traiter de nouveau, ouvrez-le puis choisissez « Réindexer ce document ». "
      + "Un fichier était déjà importé à l'identique et son traitement est en pause : l'import n'en lance pas un second. Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise.",
    resumeJobs: ["j3"] });
});

test("a reimported file whose job is paused gets the offer to resume it", () => {
  assert.deepEqual(importOutcome({ imports: [suspended(1, "paused")] }, 1, 0), {
    notice: "1 document reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est en pause : l'import n'en lance pas un second. Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise.",
    resumeJobs: ["j1"] });
  assert.equal(resumeLabel(1), "Reprendre le traitement");
  assert.equal(resumedNotice(1), "Reprise demandée : sa progression s'affiche dans le Suivi.");
});

test("a job still pausing is not offered for resumption: the notice says what to wait for", () => {
  // Le service renvoie `job_state: "pausing"` sans `resume_required` : l'avis le dit quand même.
  assert.deepEqual(importOutcome({ imports: [suspended(1, "pausing")] }, 1, 0), {
    notice: "1 document reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est en cours de mise en pause : l'import n'en lance pas un second. Une fois la pause effective, reprenez-le depuis le Suivi.",
    resumeJobs: [] });
  // `resume_required` ne fait proposer la reprise que d'un traitement `paused` (POST /jobs/{job_id}/resume refuse les autres).
  assert.deepEqual(importOutcome({ imports: [{ ...suspended(1, "pausing"), resume_required: true }] }, 1, 0).resumeJobs, []);
  // État inconnu de l'atelier (version ultérieure du service) : renvoi au Suivi, aucune action qui pourrait échouer.
  assert.deepEqual(importOutcome({ imports: [suspended(1, "checkpoint_v9")] }, 1, 0), {
    notice: "1 document reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est suspendu (état checkpoint_v9) : l'import n'en lance pas un second. Consultez le Suivi pour le reprendre.",
    resumeJobs: [] });
});

test("a reimport during a cancellation queues a new job and reports the new extraction", () => {
  assert.match(contract.import_outcomes["cancelling|cancelled|error"].rule, /new queued job/);
  assert.deepEqual(importOutcome({ imports: [{ ...created(1), reused: false }] }, 1, 0),
    { notice: "1 document reçu par le service. Son extraction et son indexation s'affichent dans le Suivi.", resumeJobs: [] });
});

test("a mixed import counts each case and offers only the paused jobs", () => {
  const response = { imports: [created(1), suspended(2, "paused"), created(3), suspended(4, "paused"), suspended(5, "pausing"), { ...suspended(6, "paused"), job_id: 6 }] };
  assert.deepEqual(importOutcome(response, 6, 1), {
    notice: "6 documents reçus par le service ; 1 fichier non pris en charge ignoré. L'extraction et l'indexation des 2 autres fichiers s'affichent dans le Suivi. "
      + "3 fichiers étaient déjà importés à l'identique et leurs traitements sont en pause : l'import n'en lance pas d'autres. Reprenez-les pour poursuivre leur indexation depuis leur dernier point de reprise. "
      + "Un fichier était déjà importé à l'identique et son traitement est en cours de mise en pause : l'import n'en lance pas un second. Une fois la pause effective, reprenez-le depuis le Suivi.",
    // Le traitement sans identifiant lisible est compté, mais sa reprise n'est pas proposée.
    resumeJobs: ["j2", "j4"] });
  assert.equal(importOutcome({ imports: [created(1), suspended(2, "pausing"), suspended(3, "pausing")] }, 3, 0).notice,
    "3 documents reçus par le service. L'extraction et l'indexation de l'autre fichier s'affichent dans le Suivi. "
    + "2 fichiers étaient déjà importés à l'identique et leurs traitements sont en cours de mise en pause : l'import n'en lance pas d'autres. Une fois la pause effective, reprenez-les depuis le Suivi.");
  assert.equal(resumeLabel(2), "Reprendre les 2 traitements");
  assert.equal(resumedNotice(2), "Reprises demandées : leur progression s'affiche dans le Suivi.");
});

test("the suspended states handled are those for which the contract returns job_state on import", () => {
  const outcomes: Record<string, { status: number; fields: string; reused: boolean }> = contract.import_outcomes;
  const withState = Object.entries(outcomes).filter(([, outcome]) => outcome.fields.split("|").includes("job_state")).flatMap(([states]) => states.split("|"));
  const resumable = Object.entries(outcomes).filter(([, outcome]) => outcome.fields.split("|").includes("resume_required")).flatMap(([states]) => states.split("|"));
  assert.deepEqual([...IMPORT_SUSPENDED_STATES].sort(), withState.sort());
  assert.deepEqual(contract.import_response.imports[0].job_state.split(",")[0].split("|").sort(), withState.sort());
  assert.deepEqual(resumable, ["paused"]);
});

test("every last job state of the contract gets the notice of what the service did on import", () => {
  const outcomes: Record<string, { status: number; fields: string; reused: boolean }> = contract.import_outcomes;
  // Les issues couvrent chaque état de traitement du contrat, une seule fois.
  const covered = Object.keys(outcomes).flatMap(key => key.split("|"));
  assert.deepEqual([...covered].sort(), contract.job.state.split("|").sort());
  assert.equal(new Set(covered).size, covered.length);
  const started = "1 document reçu par le service. Son extraction et son indexation s'affichent dans le Suivi.";
  const unchanged = "1 document reçu par le service. Ce fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement. "
    + "Son état s'affiche dans la bibliothèque ; pour le traiter de nouveau, ouvrez-le puis choisissez « Réindexer ce document ».";
  for (const [states, outcome] of Object.entries(outcomes)) {
    assert.equal(outcome.status, 202, states);
    const fields = outcome.fields.split("|");
    for (const state of states.split("|")) {
      const entry = { document_id: "d1", version_id: "v1", job_id: "j1", reused: outcome.reused,
        ...(fields.includes("job_state") ? { job_state: state } : {}), ...(fields.includes("resume_required") ? { resume_required: true } : {}) };
      assert.deepEqual(Object.keys(entry).sort(), [...fields].sort(), state);
      const result = importOutcome({ imports: [entry], ...entry }, 1, 0);
      // Sans `job_state`, `reused` dit si l'import a créé un traitement (vrai : aucun traitement créé).
      if (!fields.includes("job_state")) assert.deepEqual(result, { notice: outcome.reused ? unchanged : started, resumeJobs: [] }, state);
      else {
        assert.match(result.notice, /^1 document reçu par le service\. Ce fichier était déjà importé à l'identique et son traitement /, state);
        assert.deepEqual(result.resumeJobs, state === "paused" ? ["j1"] : [], state);
      }
    }
  }
});

test("the library reads the import reply and offers the resumption of the paused jobs", () => {
  const library = stripScriptComments(readSource("components/library-panel.tsx"));
  assert.match(library, /onSuccess: \(response, files\) => \{\s*const outcome = importOutcome\(response, files\.length, ignored\.current\);\s*setNotice\(outcome\.notice\); setResumeJobs\(outcome\.resumeJobs\);/);
  assert.match(library, /await api\.resumeJob\(id\);/);
  assert.match(library, /\{resumeJobs\.length > 0 && <div className="library-resume"><ActionButton [^>]*onAction=\{resumeImported\} pendingLabel="Reprise…"><Play size=\{16\} \/>\{resumeLabel\(resumeJobs\.length\)\}<\/ActionButton><\/div>\}/);
  assert.doesNotMatch(library, /Son extraction et son indexation s'affichent/, "l'avis est rédigé par import-outcome.ts");
});
