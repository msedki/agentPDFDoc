/**
 * Réponse de POST /documents/import : `{imports: [{document_id, version_id, job_id, reused}]}`, avec
 * `job_state` et `resume_required: true` quand un fichier identique déjà importé au même chemin a un
 * traitement `paused`, `pausing` ou `cancelling` (`Database.import_original`, docs/interfaces/API.md §4.3).
 * Aucun traitement n'est alors lancé : l'avis de la bibliothèque le dit, et la reprise n'est proposée que
 * pour un traitement `paused`, seul état que POST /jobs/{job_id}/resume accepte parmi les trois.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { IMPORT_SUSPENDED_STATES, importOutcome, resumedNotice, resumeLabel } from "../../src/lib/import-outcome.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const created = (index: number) => ({ document_id: `d${index}`, version_id: `v${index}`, job_id: `j${index}`, reused: false });
const suspended = (index: number, job_state: string) => ({ document_id: `d${index}`, version_id: `v${index}`, job_id: `j${index}`, reused: true, job_state, resume_required: true });

test("an import without a suspended job keeps the former notice, word for word", () => {
  assert.deepEqual(importOutcome({ imports: [created(1)] }, 1, 0), { notice: "1 PDF reçu par le service. Son extraction et son indexation s'affichent dans le Suivi.", resumeJobs: [] });
  assert.deepEqual(importOutcome({ imports: [created(1), created(2), created(3)] }, 3, 2), { notice: "3 PDF reçus par le service ; 2 fichiers non PDF ignorés. Leur extraction et leur indexation s'affichent dans le Suivi.", resumeJobs: [] });
  assert.equal(importOutcome({ imports: [{ ...created(1), reused: true }] }, 1, 1).notice, "1 PDF reçu par le service ; 1 fichier non PDF ignoré. Son extraction et son indexation s'affichent dans le Suivi.");
  // Réponse illisible : le nombre de fichiers envoyés suffit à l'avis d'avant, sans reprise proposée.
  for (const response of [null, undefined, "ok", {}, { imports: "x" }, { imports: [null, 3] }]) {
    assert.deepEqual(importOutcome(response, 2, 0), { notice: "2 PDF reçus par le service. Leur extraction et leur indexation s'affichent dans le Suivi.", resumeJobs: [] }, JSON.stringify(response));
  }
});

test("a reimported file whose job is paused gets the offer to resume it", () => {
  assert.deepEqual(importOutcome({ imports: [suspended(1, "paused")] }, 1, 0), {
    notice: "1 PDF reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est en pause : l'import n'en lance pas un second. Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise.",
    resumeJobs: ["j1"] });
  assert.equal(resumeLabel(1), "Reprendre le traitement");
  assert.equal(resumedNotice(1), "Reprise demandée : sa progression s'affiche dans le Suivi.");
});

test("a job still pausing or cancelling is not offered for resumption: the notice says what to wait for", () => {
  assert.deepEqual(importOutcome({ imports: [suspended(1, "pausing")] }, 1, 0), {
    notice: "1 PDF reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est en cours de mise en pause : l'import n'en lance pas un second. Une fois la pause effective, reprenez-le depuis le Suivi.",
    resumeJobs: [] });
  assert.deepEqual(importOutcome({ imports: [suspended(1, "cancelling")] }, 1, 0), {
    notice: "1 PDF reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est en cours d'annulation : l'import n'en lance pas un second. Une fois l'annulation terminée, importez-le de nouveau pour lancer un nouveau traitement ; le Suivi indique quand elle l'est.",
    resumeJobs: [] });
  // État inconnu de l'atelier (version ultérieure du service) : renvoi au Suivi, aucune action qui pourrait échouer.
  assert.deepEqual(importOutcome({ imports: [suspended(1, "checkpoint_v9")] }, 1, 0), {
    notice: "1 PDF reçu par le service. Ce fichier était déjà importé à l'identique et son traitement est suspendu (état checkpoint_v9) : l'import n'en lance pas un second. Consultez le Suivi pour le reprendre.",
    resumeJobs: [] });
});

test("a mixed import counts each case and offers only the paused jobs", () => {
  const response = { imports: [created(1), suspended(2, "paused"), created(3), suspended(4, "paused"), suspended(5, "cancelling"), { ...suspended(6, "paused"), job_id: 6 }] };
  assert.deepEqual(importOutcome(response, 6, 1), {
    notice: "6 PDF reçus par le service ; 1 fichier non PDF ignoré. L'extraction et l'indexation des 2 autres fichiers s'affichent dans le Suivi. "
      + "3 fichiers étaient déjà importés à l'identique et leurs traitements sont en pause : l'import n'en lance pas d'autres. Reprenez-les pour poursuivre leur indexation depuis leur dernier point de reprise. "
      + "Un fichier était déjà importé à l'identique et son traitement est en cours d'annulation : l'import n'en lance pas un second. Une fois l'annulation terminée, importez-le de nouveau pour lancer un nouveau traitement ; le Suivi indique quand elle l'est.",
    // Le traitement sans identifiant lisible est compté, mais sa reprise n'est pas proposée.
    resumeJobs: ["j2", "j4"] });
  assert.equal(importOutcome({ imports: [created(1), suspended(2, "pausing"), suspended(3, "pausing")] }, 3, 0).notice,
    "3 PDF reçus par le service. L'extraction et l'indexation de l'autre fichier s'affichent dans le Suivi. "
    + "2 fichiers étaient déjà importés à l'identique et leurs traitements sont en cours de mise en pause : l'import n'en lance pas d'autres. Une fois la pause effective, reprenez-les depuis le Suivi.");
  assert.equal(importOutcome({ imports: [suspended(1, "cancelling"), suspended(2, "cancelling")] }, 2, 0).notice,
    "2 PDF reçus par le service. 2 fichiers étaient déjà importés à l'identique et leurs traitements sont en cours d'annulation : l'import n'en lance pas d'autres. Une fois l'annulation terminée, importez-les de nouveau pour lancer de nouveaux traitements ; le Suivi indique quand elle l'est.");
  assert.equal(resumeLabel(2), "Reprendre les 2 traitements");
  assert.equal(resumedNotice(2), "Reprises demandées : leur progression s'affiche dans le Suivi.");
});

test("the suspended states handled are those for which the service returns resume_required on import", () => {
  // L'import n'a pas d'entrée dans packages/contracts/contracts.json : la source est Database.import_original.
  const db = readFileSync(new URL("../../../../services/api/db.py", import.meta.url), "utf8");
  const declared = /SUSPENDED_JOB_STATES = frozenset\(\{([^}]*)\}\)/.exec(db)?.[1];
  assert.ok(declared, "SUSPENDED_JOB_STATES introuvable dans services/api/db.py");
  assert.deepEqual([...IMPORT_SUSPENDED_STATES].sort(), [...declared.matchAll(/"(\w+)"/g)].map(([, state]) => state).sort());
  assert.match(db, /"job_state": job\["state"\], "resume_required": True\}/);
});

test("the library reads the import reply and offers the resumption of the paused jobs", () => {
  const library = stripScriptComments(readSource("components/library-panel.tsx"));
  assert.match(library, /onSuccess: \(response, files\) => \{\s*const outcome = importOutcome\(response, files\.length, ignored\.current\);\s*setNotice\(outcome\.notice\); setResumeJobs\(outcome\.resumeJobs\);/);
  assert.match(library, /await api\.resumeJob\(id\);/);
  assert.match(library, /\{resumeJobs\.length > 0 && <div className="library-resume"><ActionButton [^>]*onAction=\{resumeImported\} pendingLabel="Reprise…"><Play size=\{16\} \/>\{resumeLabel\(resumeJobs\.length\)\}<\/ActionButton><\/div>\}/);
  assert.doesNotMatch(library, /Son extraction et son indexation s'affichent/, "l'avis est rédigé par import-outcome.ts");
});
