/**
 * Présentation du Suivi : les traitements qui attendent une décision passent en tête,
 * les compteurs résument la file et l'avancement ne s'affiche que pendant un calcul.
 */
import type { Job } from "./types.ts";

export type JobGroup = "decision" | "error" | "active" | "paused" | "cancelled" | "done";

const activeStates = new Set(["queued", "running", "extracting", "ocr", "indexing", "pausing", "cancelling", "waiting_for_ingestion_checkpoint"]);
const runningStates = new Set(["running", "extracting", "ocr", "indexing", "pausing"]);

export function jobState(job: Pick<Job, "state" | "status">): string {
  return job.state ?? job.status ?? "";
}

/**
 * Traitement le plus récent de chaque document (l'API les liste du plus récent au plus ancien) :
 * un traitement plus ancien est remplacé et n'appelle plus de décision.
 */
export function latestJobIds(jobs: Pick<Job, "id" | "document_id">[]): Set<string> {
  const seen = new Set<string>();
  const latest = new Set<string>();
  for (const job of jobs) {
    const key = job.document_id ?? job.id;
    if (seen.has(key)) continue;
    seen.add(key);
    latest.add(job.id);
  }
  return latest;
}

/** Groupe d'attention : décision à prendre, échec, en cours, en pause, annulé, terminé. */
export function jobGroup(job: Pick<Job, "state" | "status">, published: boolean, superseded = false): JobGroup {
  const state = jobState(job);
  if (superseded && ["ready_partial", "error", "failed", "cancelled"].includes(state)) return "done";
  if (state === "ready_partial" && !published) return "decision";
  if (state === "error" || state === "failed") return "error";
  if (activeStates.has(state)) return "active";
  if (["paused", "checkpointed", "interrupted"].includes(state)) return "paused";
  if (state === "cancelled") return "cancelled";
  return "done";
}

const order: JobGroup[] = ["decision", "error", "active", "paused", "cancelled", "done"];

/** Tri stable par groupe d'attention ; l'ordre de l'API (du plus récent au plus ancien) est conservé dans un groupe. */
export function sortJobsForAttention<T extends Pick<Job, "id" | "document_id" | "state" | "status">>(jobs: T[], isPublished: (job: T) => boolean): T[] {
  const latest = latestJobIds(jobs);
  return jobs.map((job, index) => ({ job, index, rank: order.indexOf(jobGroup(job, isPublished(job), !latest.has(job.id))) }))
    .sort((left, right) => left.rank - right.rank || left.index - right.index)
    .map(item => item.job);
}

/** L'avancement n'a de sens que pendant un calcul ; une pause à 0 % ne doit pas ressembler à une barre pleine. */
export function showsProgress(job: Pick<Job, "state" | "status" | "progress">): boolean {
  return typeof job.progress === "number" && runningStates.has(jobState(job));
}

const groupLabels: Record<JobGroup, [singular: string, plural: string]> = {
  decision: ["extraction partielle à publier", "extractions partielles à publier"],
  error: ["échec", "échecs"],
  active: ["en cours ou en attente", "en cours ou en attente"],
  paused: ["en pause", "en pause"],
  cancelled: ["annulé", "annulés"],
  done: ["terminé", "terminés"],
};

/** « 4 extractions partielles à publier · 61 en pause · 1 terminé ». */
export function jobsSummary(groups: JobGroup[]): string {
  const counts = new Map<JobGroup, number>();
  for (const group of groups) counts.set(group, (counts.get(group) ?? 0) + 1);
  return order.filter(group => counts.has(group)).map(group => {
    const count = counts.get(group)!;
    return `${count} ${groupLabels[group][count === 1 ? 0 : 1]}`;
  }).join(" · ");
}

/** Nombre de reprises effectivement mises en file par le service, pas le compteur avant le clic. */
export function resumePausedNotice(count: number): string {
  if (count === 0) return "Aucune reprise d'indexation mise en file. Vérifiez les états dans le Suivi.";
  return count === 1
    ? "1 reprise d'indexation mise en file ; son état s'affiche dans le Suivi."
    : `${count} reprises d'indexation mises en file ; leur état s'affiche dans le Suivi.`;
}

/** Une extraction partielle peut manquer de régions ou de texte, même avec toutes ses pages traitées. */
export function partialExtractionNotice(published: boolean): string {
  return published
    ? "Extraction partielle publiée : pour ce document, les recherches et les réponses utilisent seulement le texte extrait disponible. Consultez les limites signalées."
    : "Extraction partielle terminée, non publiée : seul le texte extrait deviendra interrogeable si vous la publiez. Consultez les limites signalées avant de décider.";
}
