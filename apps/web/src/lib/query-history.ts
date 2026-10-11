import { citedSourceIds } from "./citations.ts";
import { mergeQueryWarnings } from "./warnings.ts";
import type { HistoricalQuery, QueryState, Scope, Source, StreamEvent } from "./types.ts";

const terminalStates = new Set(["done", "completed", "cancelled", "interrupted", "error", "needs_clarification", "insufficient_evidence", "length", "length_limited"]);
const terminalEvents = new Set(["done", "cancelled", "error", "needs_clarification"]);
const textValue = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;

/** L'URL conserve uniquement l'identifiant du tour, jamais sa réponse ni ses preuves. */
export function historyQueryId(search: string): string | null {
  const id = new URLSearchParams(search).get("history_query");
  return id && /^[\w-]{1,128}$/.test(id) ? id : null;
}

export function historyQuerySearch(search: string, id: string | null): string {
  const params = new URLSearchParams(search);
  if (id !== null && !/^[\w-]{1,128}$/.test(id)) throw new Error("Identifiant de question non valide.");
  if (id) params.set("history_query", id); else params.delete("history_query");
  const value = params.toString();
  return value ? `?${value}` : "";
}

function recordedScopeLabel(scope: Scope): string {
  switch (scope.kind) {
    case "library": return "Bibliothèque lors de la question";
    case "folder": return "Dossier lors de la question";
    case "documents": return `${scope.documentIds.length} document${scope.documentIds.length > 1 ? "s" : ""} lors de la question`;
    case "pages": return `Pages ${scope.pageStart + 1} à ${scope.pageEnd + 1} lors de la question`;
    case "selection": return "Sélection enregistrée lors de la question";
    case "section": return "Section enregistrée lors de la question";
    case "sheet": return "Feuille enregistrée lors de la question";
    case "cell_range": return "Plage de cellules enregistrée lors de la question";
  }
}

export function historicalTurn(detail: HistoricalQuery): QueryState {
  return { id: detail.query_id, question: detail.question, scope: structuredClone(detail.scope), scopeLabel: recordedScopeLabel(detail.scope),
    mode: null, text: detail.last_event_id > 0 ? "" : detail.answer, status: detail.state,
    connection: detail.last_event_id > 0 || !terminalStates.has(detail.state) ? "connecting" : "closed",
    sources: [], warnings: mergeQueryWarnings([], detail.warnings), lastEventId: "", historicalState: detail.state };
}

export function isQueryActive(query: QueryState): boolean {
  return query.connection !== "closed" && (!query.historicalState || !terminalStates.has(query.historicalState));
}

export function withoutHistoricalTurns(queries: QueryState[]): QueryState[] {
  return queries.filter(query => query.historicalState === undefined);
}

/** Consulter une citation archivée n'en fait pas le référent de la prochaine question. */
export function sourceFocus(queryId: string | undefined, sourceId: string | undefined, scope: Scope | undefined, activeScope: Scope, historical = false) {
  return !historical && queryId && sourceId && scope && JSON.stringify(scope) === JSON.stringify(activeScope) ? { query_id: queryId, source_id: sourceId } : undefined;
}

/** Une sélection remplace le tour consulté sans dupliquer un tour déjà présent. */
export function putHistoricalTurn(queries: QueryState[], turn: QueryState): QueryState[] {
  return [...withoutHistoricalTurns(queries).filter(query => query.id !== turn.id), turn];
}

export function applyQueryEvent(query: QueryState, event: StreamEvent): QueryState {
  const next = { ...query, lastEventId: event.id || query.lastEventId };
  switch (event.type) {
    case "status": next.status = textValue(event.data.status ?? event.data.state ?? event.data.stage, query.status); break;
    case "sources": if (Array.isArray(event.data.sources)) next.sources = event.data.sources.filter(source => source && typeof source.source_id === "string" && typeof source.version_id === "string") as Source[]; break;
    case "delta": next.text += textValue(event.data.text); next.status = "generating"; break;
    case "warning": next.warnings = mergeQueryWarnings(query.warnings, [event.data.warning ?? event.data]); break;
    case "done": {
      next.text = textValue(event.data.text, textValue(event.data.message, query.text)) || query.text;
      next.status = textValue(event.data.status, "done"); next.connection = "closed";
      next.finishReason = textValue(event.data.finish_reason, "stop");
      if (Array.isArray(event.data.warnings)) next.warnings = mergeQueryWarnings(query.warnings, event.data.warnings);
      if (citedSourceIds(next.text).some(id => !next.sources.some(source => source.source_id === id))) next.warnings = mergeQueryWarnings(next.warnings, ["Une référence non enregistrée dans les sources a été signalée et reste non cliquable."]);
      break;
    }
    case "cancelled": next.text = textValue(event.data.text, query.text); next.status = "cancelled"; next.connection = "closed"; break;
    case "needs_clarification": next.status = "needs_clarification"; next.connection = "closed"; next.text = textValue(event.data.message, "Précisez le référent documentaire de votre question."); break;
    case "error": next.status = textValue(event.data.status, event.data.code === "interrupted" ? "interrupted" : "error"); next.error = textValue(event.data.message, "La réponse a été interrompue par une erreur du service."); next.connection = "closed"; break;
  }
  return next;
}

type HistoryDependencies = {
  detail: (id: string, signal: AbortSignal) => Promise<HistoricalQuery>;
  connect: (url: string, after: string, event: (event: StreamEvent) => void, connection: (connection: QueryState["connection"]) => void) => () => void;
  start: (id: string) => void;
  ready: (turn: QueryState) => void;
  event: (id: string, event: StreamEvent) => void;
  connection: (id: string, connection: QueryState["connection"]) => void;
  failure: (error: unknown) => void;
};

/** Chaque sélection possède sa requête et son flux : leurs retours tardifs sont ignorés. */
export function createHistoryLoader(dependencies: HistoryDependencies) {
  let sequence = 0;
  let abort: AbortController | undefined;
  let close: (() => void) | undefined;
  const cancel = () => { sequence++; abort?.abort(); close?.(); abort = undefined; close = undefined; };
  const select = async (id: string) => {
    cancel();
    const current = sequence;
    const controller = new AbortController(); abort = controller;
    dependencies.start(id);
    try {
      const detail = await dependencies.detail(id, controller.signal);
      if (current !== sequence) return;
      if (detail.query_id !== id || detail.events_url !== `/api/v1/queries/${encodeURIComponent(id)}/events`) throw new Error("L'historique reçu ne correspond pas à la question sélectionnée.");
      dependencies.ready(historicalTurn(detail));
      if (detail.last_event_id === 0 && terminalStates.has(detail.state)) return;
      let finished = false;
      close = dependencies.connect(detail.events_url, "0", event => {
        if (current !== sequence || finished) return;
        dependencies.event(id, event);
        if (terminalEvents.has(event.type)) { finished = true; close?.(); close = undefined; }
      }, connection => { if (current === sequence && !finished) dependencies.connection(id, connection); });
    } catch (failure) {
      if (current === sequence && !controller.signal.aborted) dependencies.failure(failure);
    }
  };
  return { select, cancel };
}
