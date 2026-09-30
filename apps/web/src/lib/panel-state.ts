import type { DocumentRecord, LibraryTree, Scope } from "./types.ts";

/** État d'un document dont une extraction complète ou partielle peut être publiée. */
export function isQueryableDocumentState(state: string | null | undefined): boolean {
  return state === "ready" || state === "ready_partial";
}

/** Un document est interrogeable lorsqu'une génération est publiée : un partiel non publié ne l'est pas. */
export function isQueryableDocument(document: Pick<DocumentRecord, "state" | "active_generation_id">): boolean {
  return isQueryableDocumentState(document.state) && document.active_generation_id !== null;
}

/**
 * État affiché par la bibliothèque. Une lecture en échec sans données reste
 * « unavailable » : une panne n'est jamais présentée comme une bibliothèque vide.
 * Une lecture en échec avec des données déjà reçues garde ces données
 * (« content ») ; le panneau affiche alors l'erreur au-dessus du contenu.
 */
export type LibraryView = "unavailable" | "loading" | "no-documents" | "no-match" | "content";

export function libraryView(input: { hasData: boolean; failed: boolean; total: number; visible: number; filtering: boolean }): LibraryView {
  if (!input.hasData) return input.failed ? "unavailable" : "loading";
  if (input.total === 0) return "no-documents";
  if (input.filtering && input.visible === 0) return "no-match";
  return "content";
}

function descendantFolders(tree: LibraryTree, root: string): Set<string> {
  const found = new Set([root]);
  let added = true;
  while (added) {
    added = false;
    for (const folder of tree.folders) {
      if (folder.parent_id && found.has(folder.parent_id) && !found.has(folder.id)) { found.add(folder.id); added = true; }
    }
  }
  return found;
}

/** Documents vivants couverts par un périmètre, d'après l'arborescence déjà chargée. */
export function scopeDocuments(scope: Scope, tree: LibraryTree): DocumentRecord[] {
  const live = tree.documents.filter(document => document.state !== "deleted");
  switch (scope.kind) {
    case "library": return live;
    case "documents": return live.filter(document => scope.documentIds.includes(document.id));
    case "folder": {
      const folders = descendantFolders(tree, scope.folderId);
      return live.filter(document => document.folder_id !== null && folders.has(document.folder_id));
    }
    default: return live.filter(document => document.active_version_id === scope.versionId || document.version_id === scope.versionId);
  }
}

/** Nombre de documents du périmètre qui ne sont pas encore interrogeables (index incomplet). */
export function unindexedInScope(scope: Scope, tree: LibraryTree): number {
  return scopeDocuments(scope, tree).filter(document => !isQueryableDocument(document)).length;
}

/**
 * Une panne du service local (réseau coupé, passerelle ou service en 5xx
 * transitoire) se distingue d'un refus métier (404, 409, 422) qui a un message
 * propre. La classification lit le code posé par `ApiError` sans l'importer.
 */
export function isServiceUnavailable(error: unknown): boolean {
  if (error instanceof TypeError) return true;
  const code = error && typeof error === "object" && "code" in error ? String((error as { code: unknown }).code) : "";
  return code === "NETWORK_ERROR" || /^HTTP_(502|503|504)$/.test(code);
}

/** Nombre de documents cochés dans la bibliothèque, accordé. */
export function selectedDocumentsSentence(count: number): string {
  return count === 0 ? "Aucun document sélectionné" : count === 1 ? "1 document sélectionné" : `${count} documents sélectionnés`;
}

/** Accord « 1 document … n'est pas » / « 3 documents … ne sont pas ». */
export function unindexedSentence(count: number): string {
  return count === 1
    ? "1 document de ce périmètre n'est pas encore interrogeable"
    : `${count} documents de ce périmètre ne sont pas encore interrogeables`;
}

/** Nature du périmètre, affichée en puce dans le bandeau de contexte. */
export function scopeKindLabel(kind: Scope["kind"]): string {
  switch (kind) {
    case "library": return "Bibliothèque entière";
    case "folder": return "Dossier";
    case "documents": return "Documents sélectionnés";
    case "section": return "Section";
    case "pages": return "Pages";
    case "selection": return "Texte sélectionné";
  }
}

/** Motif d'exclusion d'un document du périmètre, déduit de son état. */
export type ExclusionReason = "processing" | "paused" | "unpublished" | "cancelled" | "error" | "unknown";
const processingStates = new Set(["imported", "queued", "extracting", "ocr", "indexing"]);
const pausedStates = new Set(["paused", "waiting_for_ingestion_checkpoint"]);

function exclusionReason(state: string): ExclusionReason {
  if (processingStates.has(state)) return "processing";
  if (pausedStates.has(state)) return "paused";
  if (isQueryableDocumentState(state)) return "unpublished";
  if (state === "cancelled") return "cancelled";
  if (state === "error") return "error";
  return "unknown";
}

export type ScopeCoverage = { queryable: number; excluded: { reason: ExclusionReason; count: number }[] };

/**
 * Documents interrogeables du périmètre et documents exclus, groupés par motif
 * dans un ordre fixe. Les documents retirés ne comptent pas.
 */
export function scopeCoverage(scope: Scope, tree: LibraryTree): ScopeCoverage {
  const counts = new Map<ExclusionReason, number>();
  let queryable = 0;
  for (const document of scopeDocuments(scope, tree)) {
    if (isQueryableDocument(document)) { queryable++; continue; }
    const reason = exclusionReason(String(document.state ?? ""));
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  }
  const order: ExclusionReason[] = ["processing", "paused", "unpublished", "cancelled", "error", "unknown"];
  return { queryable, excluded: order.filter(reason => counts.has(reason)).map(reason => ({ reason, count: counts.get(reason)! })) };
}

const reasonLabels: Record<ExclusionReason, [singular: string, plural: string]> = {
  processing: ["en cours de traitement", "en cours de traitement"],
  paused: ["indexation en pause", "indexations en pause"],
  unpublished: ["extraction partielle à publier", "extractions partielles à publier"],
  cancelled: ["traitement annulé", "traitements annulés"],
  error: ["en erreur", "en erreur"],
  unknown: ["état non reconnu", "états non reconnus"],
};

/** « 3 documents interrogeables · 2 exclus : 1 en cours de traitement, 1 en erreur ». */
export function coverageSentence(coverage: ScopeCoverage): string {
  const excluded = coverage.excluded.reduce((sum, item) => sum + item.count, 0);
  if (coverage.queryable === 0 && excluded === 0) return "Aucun document dans ce périmètre";
  const queryable = coverage.queryable === 0 ? "Aucun document interrogeable" : coverage.queryable === 1 ? "1 document interrogeable" : `${coverage.queryable} documents interrogeables`;
  if (!excluded) return queryable;
  const reasons = coverage.excluded.map(item => `${item.count} ${reasonLabels[item.reason][item.count === 1 ? 0 : 1]}`).join(", ");
  return `${queryable} · ${excluded} ${excluded === 1 ? "exclu" : "exclus"} : ${reasons}`;
}

/**
 * Documents importés dont l'index n'est pas encore à jour : en attente,
 * en cours de traitement ou en pause. Sert l'état « Index incomplet ».
 */
export function pendingIndexCount(tree: LibraryTree): number {
  return tree.documents.filter(document => processingStates.has(document.state) || pausedStates.has(String(document.state))).length;
}

/** Compteur du bouton Suivi, plafonné pour tenir dans sa pastille. */
export function activeJobsBadge(count: number): string {
  return count > 99 ? "99+" : String(count);
}

/**
 * Le compte porte sur les traitements non terminés (isActiveJobState) : en cours,
 * mais aussi en pause, interrompus ou en extraction partielle. « À suivre » les
 * couvre tous, là où « actifs » laisserait croire qu'ils avancent.
 */
export function activeJobsSentence(count: number): string {
  return count === 0 ? "Aucun traitement à suivre" : count === 1 ? "1 traitement à suivre" : `${count} traitements à suivre`;
}
