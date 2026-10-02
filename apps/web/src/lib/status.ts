/**
 * Source unique des libellés et des tons d'état affichés par le poste.
 *
 * Le ton choisit une couleur de jeton (theme.css) ; le libellé l'accompagne
 * toujours, car la couleur ne code jamais seule un état. Un code inconnu n'est
 * pas affiché brut : il reçoit un libellé explicite et reste disponible dans
 * `code` pour l'info-bulle ou le diagnostic.
 */
import type { DocumentState, JobState } from "./types.ts";

export type Tone = "neutral" | "info" | "success" | "warning" | "destructive";
export type StatusView = { label: string; tone: Tone; code: string; known: boolean };
type Entry = readonly [label: string, tone: Tone];

function view(table: Record<string, Entry>, code: string | null | undefined, unknown: string): StatusView {
  const value = code ?? "";
  const entry = Object.hasOwn(table, value) ? table[value] : undefined;
  return entry ? { label: entry[0], tone: entry[1], code: value, known: true } : { label: unknown, tone: "neutral", code: value, known: false };
}

/** États de document du contrat (`document.state`, tous exigés à la compilation) et états hérités ou transitoires. */
export const documentStates = {
  imported: ["Importé", "neutral"],
  queued: ["En attente", "neutral"],
  extracting: ["Extraction en cours", "info"],
  ocr: ["OCR en cours", "info"],
  indexing: ["Indexation en cours", "info"],
  ready: ["Prêt", "success"],
  ready_partial: ["Extraction partielle", "warning"],
  ready_partial_unpublished: ["Extraction partielle à publier", "warning"],
  error: ["Erreur", "destructive"],
  deleted: ["Retiré", "neutral"],
  paused: ["En pause", "warning"],
  cancelled: ["Traitement annulé", "neutral"],
  waiting_for_ingestion_checkpoint: ["Mise en pause en cours", "warning"],
} as const satisfies Record<DocumentState, Entry> & Record<string, Entry>;

export function documentStatus(state: string | null | undefined): StatusView {
  return view(documentStates, state, "État de document non reconnu");
}

/**
 * État affiché d'un document de la bibliothèque : une extraction partielle sans
 * génération publiée attend une décision (publication explicite, IMPLEMENTATION §2).
 */
export function documentRecordStatus(document: { state?: string | null; active_generation_id?: string | null }): StatusView {
  return documentStatus(document.state === "ready_partial" && document.active_generation_id === null ? "ready_partial_unpublished" : document.state);
}

/** États des traitements (`/jobs`), y compris ceux que le service écrit pendant pause et annulation. */
export const jobStates = {
  queued: ["En attente", "neutral"],
  running: ["Traitement en cours", "info"],
  extracting: ["Extraction en cours", "info"],
  ocr: ["OCR en cours", "info"],
  indexing: ["Indexation en cours", "info"],
  pausing: ["Mise en pause en cours", "warning"],
  waiting_for_ingestion_checkpoint: ["Mise en pause en cours", "warning"],
  paused: ["Indexation en pause — reprise manuelle", "warning"],
  checkpointed: ["Point de reprise enregistré — reprise manuelle", "warning"],
  interrupted: ["Interrompu — reprise manuelle", "warning"],
  cancelling: ["Annulation en cours", "warning"],
  cancelled: ["Annulé", "neutral"],
  ready: ["Terminé", "success"],
  done: ["Terminé", "success"],
  completed: ["Terminé", "success"],
  ready_partial: ["Extraction partielle", "warning"],
  error: ["Échec", "destructive"],
  failed: ["Échec", "destructive"],
} as const satisfies Record<JobState, Entry> & Record<string, Entry>;

export function jobStatus(state: string | null | undefined): StatusView {
  return view(jobStates, state, "État de traitement non reconnu");
}

/** Étapes écrites par l'indexation (`jobs.stage`) ; une étape inconnue n'est pas affichée. */
const jobStages: Record<string, string> = {
  extracting: "extraction du texte",
  embedding: "passages découpés, vectorisation à venir",
  vectors: "vectorisation et écriture dans l'index",
  complete: "publication terminée",
  resume: "reprise demandée",
  interrupted: "arrêt au dernier point de reprise",
};

export function jobStageLabel(stage: string | null | undefined, state?: string | null): string | null {
  if (!stage || stage === state || !Object.hasOwn(jobStages, stage)) return null;
  return jobStages[stage];
}

/**
 * Traitements non terminés, comptés par le Suivi : en cours, en pause, mis en
 * point de reprise, interrompus ou en extraction partielle.
 */
const finishedJobStates = new Set(["done", "completed", "ready", "cancelled", "error", "failed"]);
export function isActiveJobState(state: string | null | undefined): boolean {
  return !finishedJobStates.has(state ?? "");
}

/** Statuts d'une question (SSE `status`, `done`, `error`, `cancelled`). */
export const queryStates = {
  created: ["Question enregistrée", "neutral"],
  queued: ["En attente", "neutral"],
  searching: ["Recherche des passages", "info"],
  retrieving: ["Recherche des passages", "info"],
  context: ["Préparation des preuves", "info"],
  context_ready: ["Preuves prêtes", "info"],
  sources: ["Sources retrouvées", "info"],
  generating: ["Rédaction en cours", "info"],
  running: ["Traitement de la question en cours", "info"],
  waiting_for_ingestion_checkpoint: ["En attente de la pause de l'indexation", "warning"],
  waiting_for_resources: ["En attente de mémoire disponible", "warning"],
  cancel_requested: ["Annulation demandée", "warning"],
  done: ["Réponse terminée", "success"],
  completed: ["Réponse terminée", "success"],
  length: ["Réponse limitée par la longueur", "warning"],
  length_limited: ["Réponse limitée par la longueur", "warning"],
  needs_clarification: ["Précision nécessaire", "warning"],
  insufficient_evidence: ["Preuves insuffisantes", "warning"],
  cancelled: ["Réponse annulée", "warning"],
  interrupted: ["Réponse interrompue", "warning"],
  error: ["Échec", "destructive"],
} as const satisfies Record<string, Entry>;

export function queryStatus(status: string | null | undefined): StatusView {
  return view(queryStates, status, "Statut de réponse non reconnu");
}

/**
 * Disponibilité des services locaux, lue sur `/readiness` et complétée par
 * l'arborescence : `unreachable` distingue une panne de connexion d'une
 * réponse en erreur ; `pendingDocuments` compte les documents importés que
 * l'index ne couvre pas encore.
 */
export type ServiceProbe = { loading: boolean; failed: boolean; unreachable?: boolean; ready?: boolean; pendingDocuments?: number };
export function serviceStatus({ loading, failed, unreachable = true, ready, pendingDocuments = 0 }: ServiceProbe): StatusView {
  if (loading) return { label: "Connexion au service local…", tone: "neutral", code: "connecting", known: true };
  if (failed) return unreachable
    ? { label: "Service local injoignable", tone: "destructive", code: "unreachable", known: true }
    : { label: "Service local en erreur", tone: "destructive", code: "error", known: true };
  if (ready !== true) return { label: "Service local pas encore prêt", tone: "warning", code: "not_ready", known: true };
  if (pendingDocuments > 0) return { label: "Index incomplet", tone: "warning", code: "index_lagging", known: true };
  return { label: "Services prêts", tone: "success", code: "ready", known: true };
}
