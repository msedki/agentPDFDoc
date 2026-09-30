"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowUpRight, Ban, BookOpen, Check, CircleAlert, Layers, MessageSquare, RefreshCw, Search, Send } from "lucide-react";
import { api } from "@/lib/api";
import { connectQueryStream } from "@/lib/stream";
import { sourcePage } from "@/lib/selection";
import { useWorkspace } from "@/lib/store";
import { errorMessage } from "@/lib/utils";
import { warningText } from "@/lib/warnings";
import type { QueryState, Scope, SearchResponse, Source, StreamEvent } from "@/lib/types";
import { Button } from "./ui/button";

const statusLabels: Record<string, string> = {
  created: "Question enregistrée", queued: "En attente", searching: "Recherche des passages", retrieving: "Recherche des passages", context_ready: "Preuves prêtes", cancel_requested: "Annulation demandée", generating: "Rédaction en cours", running: "Travail en cours", done: "Réponse terminée", completed: "Réponse terminée", cancelled: "Réponse annulée", interrupted: "Réponse interrompue", error: "Échec", waiting_for_ingestion_checkpoint: "En attente de la pause de l'indexation", waiting_for_resources: "En attente de mémoire disponible", context: "Préparation des preuves", sources: "Sources retrouvées", length: "Réponse limitée par la longueur", length_limited: "Réponse limitée par la longueur", needs_clarification: "Précision nécessaire", insufficient_evidence: "Preuves insuffisantes",
};
function textValue(value: unknown, fallback = "") { return typeof value === "string" ? value : fallback; }

export function CitationText({ text, sources, onCitation }: { text: string; sources: Source[]; onCitation: (source: Source) => void }) {
  const parts = text.split(/(\[S\d{3,}\])/g);
  return <div className="answer-text">{parts.map((part, index) => {
    const match = /^\[(S\d{3,})\]$/.exec(part);
    if (!match) return <span key={index}>{part}</span>;
    const source = sources.find(value => value.source_id === match[1]);
    return source ? <button className="inline-citation" key={index} onClick={() => onCitation(source)} title={`Ouvrir ${source.name ?? source.document_name}, page ${sourcePage(source) + 1}`}>{match[1]}</button> : <span className="invalid-citation" key={index} title="Identifiant absent du registre de sources">{part} · non validée</span>;
  })}</div>;
}

export function SourceCard({ source, onClick }: { source: Source; onClick: () => void }) {
  const page = sourcePage(source) + 1;
  const precision = source.precision ?? source.blocks?.[0]?.precision ?? "page";
  return <button className="source-card" onClick={onClick} data-testid="source-card">
    <div><span className="source-id">{source.source_id ?? "Passage"}</span><span>p. {page}{source.label && source.label !== String(page) ? ` · folio ${source.label}` : ""}</span><ArrowUpRight size={15} /></div>
    <strong>{source.name ?? source.document_name ?? "Document source"}</strong>
    <p>{source.text}</p>
    <small>{precision === "page" ? "Localisation à la page" : precision === "table" ? "Table source" : precision === "span" ? "Passage source" : "Bloc source"} · version {source.version_id.slice(0, 8)}</small>
  </button>;
}

export function AnalysisPanel({ onSource }: { onSource: (source: Source, queryId?: string) => Promise<void> }) {
  const state = useWorkspace();
  const [tab, setTab] = useState<"question" | "search" | "comparison">("question");
  const [question, setQuestion] = useState("");
  const [queries, setQueries] = useState<QueryState[]>([]);
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [searchScope, setSearchScope] = useState<{ scope: Scope; label: string } | null>(null);
  const [error, setError] = useState("");
  const streams = useRef(new Map<string, () => void>());
  const queriesRef = useRef(queries);
  queriesRef.current = queries;
  const conversation = useRef<string | null>(null);
  const followup = useRef<string | undefined>(undefined);
  const focus = useRef<{ query_id: string; source_id: string } | undefined>(undefined);
  const scopeFingerprint = JSON.stringify(state.scope);
  const history = useRef<HTMLDivElement>(null);
  const [cancelBusy, setCancelBusy] = useState(false);

  const update = (id: string, updater: (query: QueryState) => QueryState) => setQueries(current => current.map(query => query.id === id ? updater(query) : query));
  const onEvent = (id: string, event: StreamEvent) => update(id, query => {
    const next = { ...query, lastEventId: event.id || query.lastEventId };
    switch (event.type) {
      case "status": next.status = textValue(event.data.status ?? event.data.state ?? event.data.stage, query.status); break;
      case "sources": if (Array.isArray(event.data.sources)) next.sources = event.data.sources.filter(source => source && typeof source.source_id === "string" && typeof source.version_id === "string") as Source[]; break;
      case "delta": next.text += textValue(event.data.text); next.status = "generating"; break;
      case "warning": next.warnings = [...query.warnings, warningText(event.data.warning ?? event.data)]; break;
      case "done": {
        next.text = textValue(event.data.text, textValue(event.data.message, query.text)) || query.text;
        next.status = textValue(event.data.status, "done"); next.connection = "closed";
        next.finishReason = textValue(event.data.finish_reason, "stop");
        if (Array.isArray(event.data.warnings)) next.warnings = [...query.warnings, ...event.data.warnings.map(warningText)];
        const mentioned = Array.from(next.text.matchAll(/\[(S\d{3,})\]/g), match => match[1]);
        if (mentioned.some(sourceId => !next.sources.some(source => source.source_id === sourceId))) next.warnings.push("Une référence non enregistrée dans les sources a été signalée et reste non cliquable.");
        break;
      }
      case "cancelled": next.status = "cancelled"; next.connection = "closed"; break;
      case "needs_clarification": next.status = "needs_clarification"; next.connection = "closed"; next.text = textValue(event.data.message, "Précisez le référent documentaire de votre question."); break;
      case "error": next.status = textValue(event.data.status, "error"); next.error = textValue(event.data.message, "La réponse a été interrompue par une erreur du service."); next.connection = "closed"; break;
    }
    return next;
  });
  const connect = (id: string, eventsUrl: string, lastEventId = "") => {
    streams.current.get(id)?.();
    streams.current.set(id, connectQueryStream(eventsUrl, lastEventId, event => onEvent(id, event), connection => update(id, query => ({ ...query, connection }))));
  };
  useEffect(() => () => { for (const close of streams.current.values()) close(); }, []);
  useEffect(() => { conversation.current = null; followup.current = undefined; focus.current = undefined; }, [scopeFingerprint]);
  useEffect(() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; }, [queries.at(-1)?.text.length, queries.length]);

  const submission = useMutation({ mutationFn: async ({ text, scope, scopeLabel, mode }: { text: string; scope: Scope; scopeLabel: string; mode: string }) => {
    const created = await api.query(text, scope, mode, conversation.current, followup.current, focus.current);
    if (JSON.stringify(useWorkspace.getState().scope) === JSON.stringify(scope)) {
      conversation.current = created.conversation_id ?? conversation.current;
      followup.current = created.query_id;
    }
    const query: QueryState = { id: created.query_id, question: text, scope, scopeLabel, mode, text: "", status: "created", connection: "connecting", sources: [], warnings: [], lastEventId: "" };
    setQueries(current => [...current, query]);
    connect(created.query_id, created.events_url);
    return created;
  }, onError: failure => setError(errorMessage(failure)) });
  const searchMutation = useMutation({ mutationFn: ({ text, scope }: { text: string; scope: Scope; scopeLabel: string }) => api.search(text, scope), onSuccess: (response, variables) => { setSearch(response); setSearchScope({ scope: variables.scope, label: variables.scopeLabel }); setError(""); }, onError: failure => setError(errorMessage(failure)) });
  const active = queries.findLast(query => query.connection !== "closed");
  const compareAllowed = state.scope.kind === "documents" && state.scope.documentIds.length >= 2 && state.scope.documentIds.length <= 4;
  const emptyScope = state.scope.kind === "documents" && !state.scope.documentIds.length;
  const submit = () => {
    if (!question.trim() || emptyScope || submission.isPending || active || tab === "comparison" && !compareAllowed) return;
    setError("");
    const snapshot = structuredClone(state.scope);
    if (tab === "search") searchMutation.mutate({ text: question.trim(), scope: snapshot, scopeLabel: state.scopeLabel });
    else { submission.mutate({ text: question.trim(), scope: snapshot, scopeLabel: state.scopeLabel, mode: tab === "comparison" ? "comparison" : snapshot.kind === "selection" ? "selection" : snapshot.kind === "section" ? "section" : "question" }); setQuestion(""); }
  };
  const cancel = async () => {
    if (!active) return;
    setCancelBusy(true);
    try { await api.cancelQuery(active.id); } catch (failure) { setError(errorMessage(failure)); }
    finally { setCancelBusy(false); }
  };
  const openSource = (source: Source, queryId?: string, sourceScope?: Scope) => {
    const fromQuery = queriesRef.current.find(query => query.id === queryId);
    const usedScope = fromQuery?.scope ?? sourceScope ?? (queryId && source.query_id === queryId ? searchScope?.scope : undefined);
    focus.current = queryId && source.source_id && usedScope && JSON.stringify(usedScope) === scopeFingerprint ? { query_id: queryId, source_id: source.source_id } : undefined;
    void onSource(source, queryId).catch(failure => setError(errorMessage(failure)));
  };

  return <section className="analysis-panel">
    <div className="panel-heading"><h2>Analyse</h2><span className="eyebrow">Réponses avec sources</span></div>
    <div className="analysis-tabs" role="tablist" aria-label="Mode d'analyse">
      <button role="tab" aria-selected={tab === "question"} onClick={() => setTab("question")}><MessageSquare size={15} />Question</button>
      <button role="tab" aria-selected={tab === "search"} onClick={() => setTab("search")}><Search size={15} />Recherche</button>
      <button role="tab" aria-selected={tab === "comparison"} onClick={() => setTab("comparison")}><Layers size={15} />Comparer</button>
    </div>
    <div className="scope-summary" data-testid="scope-summary"><span className="eyebrow">Périmètre actif</span><strong>{state.scopeLabel}</strong>{state.scope.kind === "selection" && <span>{state.scope.spans.length} passage(s) référencé(s)</span>}</div>
    <div className="analysis-history" ref={history}>
      {tab === "search" && search && searchScope && <p className="result-count">Périmètre de cette recherche : {searchScope.label}</p>}
      {tab === "search" ? search ? <div className="search-results"><p className="result-count">{search.results.length} passages retrouvés · {Math.round(search.elapsed_ms)} ms</p>{search.warnings?.map((warning, index) => <p className="inline-warning" key={index}>{warningText(warning)}</p>)}{!search.results.length && <div className="empty-state"><Search size={32} strokeWidth={1} /><h3>Aucun passage retrouvé</h3><p>Cette recherche ne prouve pas l'absence de l'information dans le document.</p></div>}{search.results.map((result, index) => { const source = ("source" in result && result.source ? result.source : result) as Source; return source.version_id ? <SourceCard key={`${source.source_id}:${index}`} source={source} onClick={() => openSource(source, source.query_id)} /> : <p key={index} className="inline-warning">Le résultat reçu n'expose pas de source consultable.</p>; })}</div> : <div className="empty-state"><Search size={34} strokeWidth={1} /><h3>Retrouver un passage</h3><p>Recherchez un code, une expression ou une notion dans le périmètre choisi. La recherche fonctionne sans génération.</p></div> : !queries.length ? <div className="empty-state"><BookOpen size={34} strokeWidth={1} /><h3>{tab === "comparison" ? "Comparer des preuves" : "Une question, des passages vérifiables."}</h3><p>{tab === "comparison" ? "Sélectionnez deux à quatre PDF et définissez le périmètre. Les sources de chaque document restent visibles." : "Choisissez un périmètre, posez votre question, puis ouvrez les sources pour vérifier la réponse."}</p></div> : queries.map(query => <article className="query-turn" key={query.id} data-testid="query-turn">
        <div className="question-message"><p>{query.question}</p><small>{query.scopeLabel}</small></div>
        <div className="query-status" role="status"><span className={query.connection !== "closed" ? "activity-dot" : "status-dot"} />{statusLabels[query.status] ?? query.status}{query.connection === "reconnecting" && <Button variant="ghost" size="sm" onClick={() => connect(query.id, `/api/v1/queries/${encodeURIComponent(query.id)}/events`, query.lastEventId)}><RefreshCw size={13} />Reconnexion</Button>}</div>
        {query.text && <CitationText text={query.text} sources={query.sources} onCitation={source => openSource(source, query.id)} />}
        {query.error && <p className="inline-warning" role="alert"><CircleAlert size={14} />{query.error}</p>}
        {query.finishReason === "length" && <p className="inline-warning">La réponse a atteint sa limite de longueur. Reformulez ou demandez explicitement une suite dans le même périmètre.</p>}
        {["cancelled", "interrupted"].includes(query.status) && <p className="inline-warning">Cette réponse est incomplète.</p>}
        {query.warnings.map((warning, index) => <p className="inline-warning" key={index}>{warningText(warning)}</p>)}
        {!!query.sources.length && <details className="sources-list" open><summary><Check size={14} />{query.sources.length} sources consultables</summary>{query.sources.map(source => <SourceCard key={source.source_id} source={source} onClick={() => openSource(source, query.id)} />)}</details>}
      </article>)}
    </div>
    <div className="composer-area">
      {state.selection && <div className="selection-action"><span>{state.selection.text.slice(0, 95)}{state.selection.text.length > 95 ? "…" : ""}</span><Button size="sm" variant="secondary" onClick={() => state.setScope({ kind: "selection", versionId: state.selection!.versionId, spans: state.selection!.spans }, "Sélection de texte du document")}>Analyser la sélection</Button></div>}
      {tab === "comparison" && !compareAllowed && <p className="inline-warning">Définissez un périmètre de deux à quatre PDF pour comparer.</p>}
      {error && <p className="inline-warning" role="alert">{error}</p>}
      <form onSubmit={event => { event.preventDefault(); submit(); }}><label className="sr-only" htmlFor="question-input">{tab === "search" ? "Votre recherche" : "Votre question"}</label><textarea id="question-input" value={question} onChange={event => setQuestion(event.target.value)} placeholder={tab === "search" ? "Expression ou référence à retrouver…" : tab === "comparison" ? "Quels points comparer entre ces documents ?" : "Posez une question sur ce périmètre…"} rows={3} maxLength={12000} onKeyDown={event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit(); } }} /><div className="composer-footer"><span>Ctrl + Entrée</span>{active ? <Button variant="danger" size="sm" onClick={() => void cancel()} disabled={cancelBusy} type="button"><Ban size={14} />{cancelBusy ? "Annulation…" : "Annuler"}</Button> : <Button size="sm" type="submit" disabled={!question.trim() || emptyScope || submission.isPending || searchMutation.isPending || tab === "comparison" && !compareAllowed}>{tab === "search" ? <Search size={14} /> : <Send size={14} />}{submission.isPending || searchMutation.isPending ? "Envoi…" : tab === "search" ? "Rechercher" : "Envoyer"}</Button>}</div></form>
    </div>
  </section>;
}
