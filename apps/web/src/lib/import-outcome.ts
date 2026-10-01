/**
 * Avis de la bibliothèque après un import (POST /documents/import, `{imports: [...]}`, un élément par
 * fichier). Un fichier identique déjà importé au même chemin, dont le dernier traitement est `paused`,
 * `pausing` ou `cancelling`, ne relance rien : le service renvoie ce traitement avec `job_state` et
 * `resume_required: true` (`Database.import_original`). L'avis le dit au lieu d'annoncer une progression
 * dans le Suivi, et seule la reprise d'un traitement `paused` est proposée : POST /jobs/{job_id}/resume
 * refuse `pausing` et `cancelling` (409 `job_not_resumable`).
 */

/** États renvoyés avec `resume_required` par l'import (`Database.SUSPENDED_JOB_STATES`). */
export const IMPORT_SUSPENDED_STATES = ["paused", "pausing", "cancelling"] as const;

export type ImportOutcome = { notice: string; resumeJobs: string[] };

export function receivedSentence(count: number) { return count === 1 ? "1 PDF reçu par le service" : `${count} PDF reçus par le service`; }
export function ignoredSentence(count: number) { return count === 1 ? "1 fichier non PDF ignoré" : `${count} fichiers non PDF ignorés`; }
export function resumeLabel(count: number) { return count === 1 ? "Reprendre le traitement" : `Reprendre les ${count} traitements`; }
export function resumedNotice(count: number) { return count === 1 ? "Reprise demandée : sa progression s'affiche dans le Suivi." : "Reprises demandées : leur progression s'affiche dans le Suivi."; }

/** Sujet de la phrase : le seul fichier importé, un fichier parmi d'autres, ou plusieurs. */
function subject(count: number, received: number, state: string): string {
  if (count > 1) return `${count} fichiers étaient déjà importés à l'identique et leurs traitements ${state.replace(/^est /, "sont ").replace("suspendu ", "suspendus ")}`;
  return `${received === 1 ? "Ce fichier" : "Un fichier"} était déjà importé à l'identique et son traitement ${state}`;
}

function suspendedSentence(state: string, count: number, received: number): string {
  const one = count === 1;
  const refused = one ? "l'import n'en lance pas un second" : "l'import n'en lance pas d'autres";
  switch (state) {
    case "paused":
      return `${subject(count, received, "est en pause")} : ${refused}. ${one ? "Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise." : "Reprenez-les pour poursuivre leur indexation depuis leur dernier point de reprise."}`;
    case "pausing":
      return `${subject(count, received, "est en cours de mise en pause")} : ${refused}. Une fois la pause effective, ${one ? "reprenez-le" : "reprenez-les"} depuis le Suivi.`;
    case "cancelling":
      return `${subject(count, received, "est en cours d'annulation")} : ${refused}. Une fois l'annulation terminée, ${one ? "importez-le de nouveau pour lancer un nouveau traitement" : "importez-les de nouveau pour lancer de nouveaux traitements"} ; le Suivi indique quand elle l'est.`;
    default:
      return `${subject(count, received, `est suspendu (état ${state})`)} : ${refused}. Consultez le Suivi pour ${one ? "le" : "les"} reprendre.`;
  }
}

/**
 * Avis et traitements en pause à proposer à la reprise. `received` est le nombre de PDF envoyés et
 * `ignored` celui des fichiers non PDF écartés avant l'envoi. Une réponse illisible donne l'avis d'avant.
 */
export function importOutcome(response: unknown, received: number, ignored: number): ImportOutcome {
  const imports = response && typeof response === "object" ? (response as { imports?: unknown }).imports : undefined;
  const suspended = (Array.isArray(imports) ? imports : [])
    .filter((item): item is { job_id?: unknown; job_state?: unknown; resume_required: true } => Boolean(item) && typeof item === "object" && (item as { resume_required?: unknown }).resume_required === true);
  const base = `${receivedSentence(received)}${ignored ? ` ; ${ignoredSentence(ignored)}` : ""}.`;
  if (!suspended.length) {
    return { notice: `${base} ${received === 1 ? "Son extraction et son indexation s'affichent" : "Leur extraction et leur indexation s'affichent"} dans le Suivi.`, resumeJobs: [] };
  }
  const byState = new Map<string, number>();
  for (const item of suspended) {
    const state = typeof item.job_state === "string" && item.job_state ? item.job_state : "non communiqué";
    byState.set(state, (byState.get(state) ?? 0) + 1);
  }
  const others = Math.max(0, received - suspended.length);
  const sentences = [base];
  if (others) sentences.push(`L'extraction et l'indexation ${others === 1 ? "de l'autre fichier" : `des ${others} autres fichiers`} s'affichent dans le Suivi.`);
  const order = [...IMPORT_SUSPENDED_STATES, ...[...byState.keys()].filter(state => !(IMPORT_SUSPENDED_STATES as readonly string[]).includes(state))];
  for (const state of order) {
    const count = byState.get(state);
    if (count) sentences.push(suspendedSentence(state, count, received));
  }
  const resumeJobs = [...new Set(suspended.filter(item => item.job_state === "paused" && typeof item.job_id === "string" && item.job_id).map(item => item.job_id as string))];
  return { notice: sentences.join(" "), resumeJobs };
}
