/**
 * Avis de la bibliothèque après un import (POST /documents/import, contrat `import_response` et
 * `import_outcomes` : `{imports: [...]}`, un élément par fichier). Un fichier identique déjà importé au même
 * chemin ne relance rien. Si son dernier traitement est en file, en cours ou terminé, le service le renvoie
 * avec `reused: true`, sans `job_state` ni moyen de savoir s'il est terminé : l'avis dit qu'aucun traitement
 * n'est lancé et renvoie à l'état affiché par la bibliothèque. S'il est `paused` ou `pausing`, le service le
 * renvoie avec `job_state`, et `resume_required: true` pour `paused` seulement. L'avis le dit au lieu
 * d'annoncer une progression dans le Suivi, et seule la reprise d'un traitement `paused` est proposée :
 * POST /jobs/{job_id}/resume refuse `pausing` (409 `job_not_resumable`). Pendant `cancelling`, le service
 * met un traitement neuf en file, annoncé comme tout nouvel import.
 */

/** États renvoyés avec `job_state` par l'import (contrat `import_outcomes`). */
export const IMPORT_SUSPENDED_STATES = ["paused", "pausing"] as const;

export type ImportRefusal = { path: string; code: string; message: string };
export type ImportOutcome = { notice: string; resumeJobs: string[]; rejections?: ImportRefusal[] };

export function receivedSentence(count: number) { return count === 1 ? "1 document reçu par le service" : `${count} documents reçus par le service`; }
export function ignoredSentence(count: number) { return count === 1 ? "1 fichier non pris en charge ignoré" : `${count} fichiers non pris en charge ignorés`; }
export function resumeLabel(count: number) { return count === 1 ? "Reprendre le traitement" : `Reprendre les ${count} traitements`; }
export function resumedNotice(count: number) { return count === 1 ? "Reprise demandée : sa progression s'affiche dans le Suivi." : "Reprises demandées : leur progression s'affiche dans le Suivi."; }

/** Sujet de la phrase : le seul fichier importé, un fichier parmi d'autres, ou plusieurs. */
function subject(count: number, received: number, state: string): string {
  if (count > 1) return `${count} fichiers étaient déjà importés à l'identique et leurs traitements ${state.replace(/^est /, "sont ").replace("suspendu ", "suspendus ")}`;
  return `${received === 1 ? "Ce fichier" : "Un fichier"} était déjà importé à l'identique et son traitement ${state}`;
}

/** Fichiers identiques renvoyés avec leur dernier traitement (`reused: true` sans `job_state`) : aucun traitement créé. */
function reusedSentence(count: number, received: number): string {
  const reindex = "ouvrez-le puis choisissez « Réindexer ce document ».";
  if (count > 1) return `${count} fichiers étaient déjà importés à l'identique : l'import ne lance aucun nouveau traitement pour eux. Leur état s'affiche dans la bibliothèque ; pour traiter de nouveau l'un d'eux, ${reindex}`;
  return `${received === 1 ? "Ce fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement." : "Un fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement pour lui."} Son état s'affiche dans la bibliothèque ; pour le traiter de nouveau, ${reindex}`;
}

function suspendedSentence(state: string, count: number, received: number): string {
  const one = count === 1;
  const refused = one ? "l'import n'en lance pas un second" : "l'import n'en lance pas d'autres";
  switch (state) {
    case "paused":
      return `${subject(count, received, "est en pause")} : ${refused}. ${one ? "Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise." : "Reprenez-les pour poursuivre leur indexation depuis leur dernier point de reprise."}`;
    case "pausing":
      return `${subject(count, received, "est en cours de mise en pause")} : ${refused}. Une fois la pause effective, ${one ? "reprenez-le" : "reprenez-les"} depuis le Suivi.`;
    default:
      return `${subject(count, received, `est suspendu (état ${state})`)} : ${refused}. Consultez le Suivi pour ${one ? "le" : "les"} reprendre.`;
  }
}

/**
 * Avis et traitements en pause à proposer à la reprise. `received` est le nombre de documents envoyés et
 * `ignored` celui des fichiers non pris en charge écartés avant l'envoi. Une réponse illisible donne l'avis d'avant.
 */
export function importOutcome(response: unknown, received: number, ignored: number): ImportOutcome {
  const imports = response && typeof response === "object" ? (response as { imports?: unknown }).imports : undefined;
  const items: unknown[] = Array.isArray(imports) ? imports : [];
  const errors = response && typeof response === "object" ? (response as { errors?: unknown }).errors : undefined;
  if (Array.isArray(errors) && errors.length) {
    const rejections = errors.map((error): ImportRefusal => {
      const value = error && typeof error === "object" ? error as Record<string, unknown> : {};
      return { path: typeof value.relative_path === "string" ? value.relative_path : "Fichier non identifié", code: typeof value.code === "string" ? value.code : "IMPORT_REFUSED", message: typeof value.message === "string" ? value.message : "Le service a refusé ce fichier. Consultez son format et les journaux du service." };
    });
    const accepted = items.filter(item => item && typeof item === "object" && typeof (item as { document_id?: unknown }).document_id === "string" && typeof (item as { version_id?: unknown }).version_id === "string");
    const outcome = accepted.length ? importOutcome({ imports: accepted }, accepted.length, ignored) : { notice: `Aucun document accepté dans cet import${ignored ? ` ; ${ignoredSentence(ignored)}` : ""}.`, resumeJobs: [] };
    return { ...outcome, notice: `${outcome.notice} ${rejections.length === 1 ? "1 fichier refusé" : `${rejections.length} fichiers refusés`} par le service ; les autres résultats sont conservés.`, rejections };
  }
  const withState = (item: unknown) => Boolean(item) && typeof item === "object" && typeof (item as { job_state?: unknown }).job_state === "string" && (item as { job_state: string }).job_state !== "";
  const suspended = items.filter((item): item is { job_id?: unknown; job_state: string; resume_required?: unknown } => withState(item));
  const unchanged = items.filter(item => !withState(item) && Boolean(item) && typeof item === "object" && (item as { reused?: unknown }).reused === true).length;
  const base = `${receivedSentence(received)}${ignored ? ` ; ${ignoredSentence(ignored)}` : ""}.`;
  if (!suspended.length && !unchanged) {
    return { notice: `${base} ${received === 1 ? "Son extraction et son indexation s'affichent" : "Leur extraction et leur indexation s'affichent"} dans le Suivi.`, resumeJobs: [] };
  }
  const byState = new Map<string, number>();
  for (const item of suspended) byState.set(item.job_state, (byState.get(item.job_state) ?? 0) + 1);
  const others = Math.max(0, received - suspended.length - unchanged);
  const sentences = [base];
  if (others) sentences.push(`L'extraction et l'indexation ${others === 1 ? "de l'autre fichier" : `des ${others} autres fichiers`} s'affichent dans le Suivi.`);
  if (unchanged) sentences.push(reusedSentence(unchanged, received));
  const order = [...IMPORT_SUSPENDED_STATES, ...[...byState.keys()].filter(state => !(IMPORT_SUSPENDED_STATES as readonly string[]).includes(state))];
  for (const state of order) {
    const count = byState.get(state);
    if (count) sentences.push(suspendedSentence(state, count, received));
  }
  const resumeJobs = [...new Set(suspended.filter(item => item.job_state === "paused" && item.resume_required === true && typeof item.job_id === "string" && item.job_id).map(item => item.job_id as string))];
  return { notice: sentences.join(" "), resumeJobs };
}
