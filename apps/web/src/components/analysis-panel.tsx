"use client";
import { Fragment, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Ban, BookOpen, Check, CircleAlert, Layers, MessageSquare, RefreshCw, Search, Send } from "lucide-react";
import { api } from "@/lib/api";
import { connectQueryStream } from "@/lib/stream";
import { useWorkspace } from "@/lib/store";
import { warningNotices, type WarningNotice } from "@/lib/warnings";
import { answerBlocks, type Inline } from "@/lib/answer-format";
import { citationParts } from "@/lib/citations";
import { tabKeyTarget } from "@/lib/keyboard";
import { sourceLocalization, sourceLocationLabel } from "@/lib/source-location";
import { withExtractionLabel } from "@/lib/extraction-provenance";
import { applyQueryEvent, createHistoryLoader, historyQueryId, historyQuerySearch, isQueryActive, putHistoricalTurn, sourceFocus, withoutHistoricalTurns } from "@/lib/query-history";
import { queryStatus } from "@/lib/status";
import { unindexedInScope, unindexedSentence } from "@/lib/panel-state";
import type { LibraryTree, QueryState, Scope, SearchResponse, Source } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { ExtractionBadge } from "./extraction-badge";
import { ErrorText, type Failure } from "./ui/error-text";
import { PanelEmpty, PanelHeader } from "./ui/panel";
import { StatusIndicator } from "./ui/status-indicator";

function passagesFound(count: number) { return count === 0 ? "Aucun passage retrouvé" : count === 1 ? "1 passage retrouvé" : `${count} passages retrouvés`; }
const analysisTabs = [{ id: "question", label: "Question", Icon: MessageSquare }, { id: "search", label: "Recherche", Icon: Search }, { id: "analysis", label: "Critique", Icon: BookOpen }, { id: "comparison", label: "Comparer", Icon: Layers }] as const;

function CitedSegment({ text, sources, onCitation }: { text: string; sources: Source[]; onCitation: (source: Source) => void }) {
  return citationParts(text, sources).map((part, index) => part.kind === "text" ? <span key={index}>{part.text}</span>
    : part.kind === "citation" ? <button className="inline-citation" key={index} onClick={() => onCitation(part.source)} title={citationTitle(part.source)}>{part.id}</button>
    : <span className="invalid-citation" key={index} title="Cette référence n'est pas enregistrée dans les sources de la réponse : elle n'ouvre aucun passage.">{part.text} (référence inconnue)</span>);
}

/** Paragraphes, listes et gras de la réponse, rendus en éléments React : aucune balise de la réponse n'est interprétée. */
export function CitationText({ text, sources, onCitation }: { text: string; sources: Source[]; onCitation: (source: Source) => void }) {
  const line = (segments: Inline[]) => segments.map((segment, index) => segment.strong
    ? <strong key={index}><CitedSegment text={segment.text} sources={sources} onCitation={onCitation} /></strong>
    : <CitedSegment key={index} text={segment.text} sources={sources} onCitation={onCitation} />);
  return <div className="answer-text">{answerBlocks(text).map((block, index) => block.kind === "list"
    ? <ul key={index}>{block.items.map((item, position) => <li key={position}>{line(item)}</li>)}</ul>
    : <p key={index}>{block.lines.map((segments, position) => <Fragment key={position}>{position > 0 && <br />}{line(segments)}</Fragment>)}</p>)}</div>;
}

/** Titre d'un lien vers une source enregistrée : document, page et méthode d'extraction à vérifier. */
function citationTitle(source: Source) { return withExtractionLabel(`Ouvrir ${source.name ?? source.document_name}, ${sourceLocationLabel(source) ?? "localisation non disponible"}`, source); }

/**
 * Avis d'une recherche ou d'une réponse : texte contrôlé, puis valeurs et sources signalées. Une source
 * enregistrée s'ouvre comme une citation ; un identifiant inconnu reste du texte.
 */
function WarningNotices({ notices, sources = [], onSource }: { notices: WarningNotice[]; sources?: Source[]; onSource?: (source: Source) => void }) {
  const reference = (id: string) => { const source = sources.find(item => item.source_id === id); return source && onSource ? <button type="button" className="inline-citation" onClick={() => onSource(source)} title={citationTitle(source)}>{id}</button> : <span className="mono">{id}</span>; };
  const references = (ids: string[]) => ids.map((id, index) => <Fragment key={id}>{index > 0 && ", "}{reference(id)}</Fragment>);
  return notices.map(notice => <div className="inline-warning" key={notice.key}><div>
    <p>{notice.text}</p>
    {notice.values.length > 0 && <ul className="warning-values">{notice.values.map((item, index) => <li key={index}><span className="mono">{item.value}</span> · {item.citedSourceIds.length ? <>phrase ou puce citant {references(item.citedSourceIds)}</> : "phrase ou puce sans citation"}{item.holderSourceIds.length > 0 && <> · présente dans {references(item.holderSourceIds)}</>}</li>)}</ul>}
    {notice.sourceIds.length > 0 && <p>Sources concernées : {references(notice.sourceIds)}</p>}
  </div></div>);
}

/** Carte de source : identifiant, document, page, précision, extrait de trois lignes et une seule action. */
export function SourceCard({ source, onOpen }: { source: Source; onOpen: () => void }) {
  const titleId = useId();
  const place = sourceLocationLabel(source);
  const location = sourceLocalization(source);
  return <article className="source-card" data-testid="source-card" aria-labelledby={titleId}>
    <div className="source-card-meta"><span className="source-id">{source.source_id ?? "Passage"}</span>{place && <span className="tabular">{place}{source.label && source.locator?.kind !== "docx_element" && source.locator?.kind !== "xlsx_cells" && source.label !== String((source.page_index ?? source.page_indices?.[0] ?? 0) + 1) ? ` · folio ${source.label}` : ""}</span>}<Badge tone={location.tone} title={location.title}>{location.label}</Badge><ExtractionBadge source={source} /></div>
    <h3 className="source-card-title" id={titleId}>{source.name ?? source.document_name ?? "Document sans nom"}</h3>
    <p className="source-card-excerpt">{source.text}</p>
    <div className="source-card-footer"><span title={source.version_id}>version <span className="mono">{source.version_id.slice(0, 8)}</span></span><Button type="button" variant="secondary" size="sm" onClick={onOpen} aria-describedby={titleId}><ArrowUpRight size={16} />Ouvrir le passage</Button></div>
  </article>;
}

export function AnalysisPanel({ onSource, headerAction }: { onSource: (source: Source, queryId?: string) => Promise<void>; headerAction?: ReactNode }) {
  const state = useWorkspace();
  const [tab, setTab] = useState<typeof analysisTabs[number]["id"]>("question");
  const [question, setQuestion] = useState("");
  const [queries, setQueries] = useState<QueryState[]>([]);
  const [search, setSearch] = useState<SearchResponse | null>(null);
  // `unindexed` est figé au moment de la recherche : null si l'arborescence n'était pas lisible.
  const [searchScope, setSearchScope] = useState<{ scope: Scope; label: string; unindexed: number | null } | null>(null);
  const client = useQueryClient();
  // Échec gardé tel quel : son texte se calcule au rendu, avec les commandes du lanceur connues à cet instant.
  const [error, setError] = useState<Failure | null>(null);
  const streams = useRef(new Map<string, () => void>());
  const conversation = useRef<string | null>(null);
  const followup = useRef<string | undefined>(undefined);
  const focus = useRef<{ query_id: string; source_id: string } | undefined>(undefined);
  const scopeFingerprint = JSON.stringify(state.scope);
  const history = useRef<HTMLDivElement>(null);
  const tabButtons = useRef<(HTMLButtonElement | null)[]>([]);
  const [cancelBusy, setCancelBusy] = useState(false);
  const searchSequence = useRef(0);
  const searchPending = useRef<number | null>(null);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [selectedQueryId, setSelectedQueryId] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<Failure | null>(null);
  const historyLoader = useRef<ReturnType<typeof createHistoryLoader> | null>(null);
  const historyPage = useQuery({ queryKey: ["query-history", historyCursor], queryFn: ({ signal }) => api.queryHistory(historyCursor, signal), enabled: historyOpen });
  const rememberQuery = (id: string | null) => window.history.replaceState(null, "", `${window.location.pathname}${historyQuerySearch(window.location.search, id)}${window.location.hash}`);

  useEffect(() => {
    const loader = createHistoryLoader({
      detail: api.historicalQuery, connect: connectQueryStream,
      start: id => { setSelectedQueryId(id); setHistoryLoading(true); setHistoryError(null); setQueries(current => withoutHistoricalTurns(current)); },
      ready: turn => { setQueries(current => putHistoricalTurn(current, turn)); setHistoryLoading(turn.connection !== "closed" && !isQueryActive(turn)); },
      event: (id, event) => { setQueries(current => current.map(query => query.id === id ? applyQueryEvent(query, event) : query)); if (["done", "error", "cancelled", "needs_clarification"].includes(event.type)) setHistoryLoading(false); },
      connection: (id, connection) => setQueries(current => current.map(query => query.id === id ? { ...query, connection } : query)),
      failure: failure => { setHistoryLoading(false); setHistoryError({ error: failure }); },
    });
    historyLoader.current = loader;
    const id = historyQueryId(window.location.search);
    if (id) void loader.select(id);
    return () => { loader.cancel(); historyLoader.current = null; };
  }, []);
  const chooseHistory = (id: string) => {
    conversation.current = null; followup.current = undefined; focus.current = undefined;
    setTab("question"); rememberQuery(id || null);
    if (!id) {
      historyLoader.current?.cancel(); setSelectedQueryId(""); setHistoryLoading(false); setHistoryError(null);
      setQueries(current => withoutHistoricalTurns(current));
    } else if (queries.some(query => query.id === id && query.historicalState === undefined)) {
      historyLoader.current?.cancel(); setSelectedQueryId(id); setHistoryLoading(false); setHistoryError(null); setQueries(current => withoutHistoricalTurns(current));
    } else void historyLoader.current?.select(id);
  };

  const update = (id: string, updater: (query: QueryState) => QueryState) => setQueries(current => current.map(query => query.id === id ? updater(query) : query));
  const onEvent = (id: string, event: Parameters<typeof applyQueryEvent>[1]) => update(id, query => applyQueryEvent(query, event));
  const connect = (id: string, eventsUrl: string, lastEventId = "") => {
    streams.current.get(id)?.();
    streams.current.set(id, connectQueryStream(eventsUrl, lastEventId, event => onEvent(id, event), connection => update(id, query => ({ ...query, connection }))));
  };
  useEffect(() => () => {
    for (const close of streams.current.values()) close();
    searchSequence.current++;
    searchPending.current = null;
  }, []);
  useEffect(() => { conversation.current = null; followup.current = undefined; focus.current = undefined; }, [scopeFingerprint]);
  const lastAnswerLength = queries.at(-1)?.text.length;
  useEffect(() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; }, [lastAnswerLength, queries.length]);

  const submission = useMutation({ mutationFn: async ({ text, scope, scopeLabel, mode }: { text: string; scope: Scope; scopeLabel: string; mode: string }) => {
    const created = await api.query(text, scope, mode, conversation.current, followup.current, focus.current);
    if (JSON.stringify(useWorkspace.getState().scope) === JSON.stringify(scope)) {
      conversation.current = created.conversation_id ?? conversation.current;
      followup.current = created.query_id;
    }
    const query: QueryState = { id: created.query_id, question: text, scope, scopeLabel, mode, text: "", status: "created", connection: "connecting", sources: [], warnings: [], lastEventId: "" };
    setQueries(current => [...current.filter(item => item.id !== query.id), query]);
    rememberQuery(created.query_id); setSelectedQueryId(created.query_id); setHistoryCursor(null);
    void client.invalidateQueries({ queryKey: ["query-history"] });
    connect(created.query_id, created.events_url);
    return created;
  }, onError: failure => setError({ error: failure }) });
  const searchMutation = useMutation({ mutationFn: ({ text, scope }: { text: string; scope: Scope; scopeLabel: string; requestId: number }) => api.search(text, scope), onSuccess: (response, variables) => {
    if (variables.requestId !== searchSequence.current) return;
    const tree = client.getQueryData<LibraryTree>(["tree"]);
    setSearch(response); setSearchScope({ scope: variables.scope, label: variables.scopeLabel, unindexed: tree ? unindexedInScope(variables.scope, tree) : null }); setError(null);
  }, onError: (failure, variables) => {
    if (variables.requestId === searchSequence.current) setError({ error: failure });
  }, onSettled: (_response, _failure, variables) => {
    if (searchPending.current === variables.requestId) searchPending.current = null;
  } });
  const active = queries.findLast(isQueryActive);
  const compareAllowed = state.scope.kind === "documents" && state.scope.documentIds.length >= 2 && state.scope.documentIds.length <= 4;
  const emptyScope = state.scope.kind === "documents" && !state.scope.documentIds.length;
  const submit = () => {
    if (!question.trim() || emptyScope || submission.isPending || searchMutation.isPending || searchPending.current !== null || active || tab === "comparison" && !compareAllowed) return;
    setError(null);
    const snapshot = structuredClone(state.scope);
    if (tab === "search") {
      // Le verrou précède mutate : deux événements peuvent arriver avant le rendu de isPending.
      const requestId = ++searchSequence.current;
      searchPending.current = requestId;
      searchMutation.mutate({ text: question.trim(), scope: snapshot, scopeLabel: state.scopeLabel, requestId });
    }
    else { historyLoader.current?.cancel(); setHistoryLoading(false); setHistoryError(null); setSelectedQueryId(""); rememberQuery(null); setQueries(current => withoutHistoricalTurns(current)); submission.mutate({ text: question.trim(), scope: snapshot, scopeLabel: state.scopeLabel, mode: tab === "comparison" ? "comparison" : tab === "analysis" ? "analysis" : snapshot.kind === "selection" ? "selection" : snapshot.kind === "section" ? "section" : "question" }); setQuestion(""); }
  };
  const cancel = async () => {
    if (!active) return;
    setCancelBusy(true);
    try { await api.cancelQuery(active.id); } catch (failure) { setError({ error: failure }); }
    finally { setCancelBusy(false); }
  };
  const openSource = (source: Source, queryId?: string, sourceScope?: Scope) => {
    const fromQuery = queries.find(query => query.id === queryId);
    const usedScope = fromQuery?.scope ?? sourceScope ?? (queryId && source.query_id === queryId ? searchScope?.scope : undefined);
    focus.current = sourceFocus(queryId, source.source_id, usedScope, state.scope, fromQuery?.historicalState !== undefined);
    void onSource(source, queryId).catch(failure => setError({ error: failure }));
  };

  return <aside className="analysis-panel" aria-labelledby="analysis-heading">
    <PanelHeader title="Analyse" id="analysis-heading"><div className="panel-heading-actions">{headerAction}</div></PanelHeader>
    <div className="analysis-tabs" role="tablist" aria-label="Mode d'analyse" onKeyDown={event => {
      const current = tabButtons.current.indexOf(event.target as HTMLButtonElement);
      const target = current < 0 ? null : tabKeyTarget(event.key, current, analysisTabs.length);
      if (target === null) return;
      event.preventDefault(); setTab(analysisTabs[target].id); tabButtons.current[target]?.focus();
    }}>
      {analysisTabs.map(({ id, label, Icon }, index) => <button key={id} ref={element => { tabButtons.current[index] = element; }} type="button" role="tab" id={`analysis-tab-${id}`} aria-selected={tab === id} aria-controls="analysis-tabpanel" tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}><Icon size={14} aria-hidden="true" />{label}</button>)}
    </div>
    <div className="scope-summary" data-testid="scope-summary"><span className="eyebrow">Périmètre actif</span><strong>{state.scopeLabel}</strong>{state.scope.kind === "selection" && <span>{state.scope.spans.length === 1 ? "1 passage référencé" : `${state.scope.spans.length} passages référencés`}</span>}</div>
    <details className="query-history" onToggle={event => setHistoryOpen(event.currentTarget.open)}>
      <summary>Anciennes questions</summary>
      <label htmlFor="query-history-selector">Choisir une question enregistrée</label>
      <select id="query-history-selector" data-testid="query-history-selector" value={selectedQueryId} disabled={!!active || submission.isPending} onChange={event => chooseHistory(event.target.value)}>
        <option value="">Aucune question sélectionnée</option>
        {selectedQueryId && !historyPage.data?.queries.some(query => query.query_id === selectedQueryId) && <option value={selectedQueryId}>{queries.find(query => query.id === selectedQueryId)?.question ?? "Question sélectionnée"}</option>}
        {historyPage.data?.queries.map(query => <option key={query.query_id} value={query.query_id}>{query.question.slice(0, 160)} · {queryStatus(query.state).label}</option>)}
      </select>
      <div className="query-history-actions">
        <Button variant="ghost" size="sm" onClick={() => { if (historyCursor) setHistoryCursor(null); else void historyPage.refetch(); }} disabled={historyPage.isFetching}>Actualiser</Button>
        {historyCursor && <Button variant="ghost" size="sm" onClick={() => setHistoryCursor(null)}>Plus récentes</Button>}
        {historyPage.data?.next_cursor && <Button variant="ghost" size="sm" onClick={() => setHistoryCursor(historyPage.data!.next_cursor)} disabled={historyPage.isFetching}>Plus anciennes</Button>}
      </div>
      {historyPage.isFetching && <p role="status">Chargement des questions…</p>}
      {historyPage.data && !historyPage.data.queries.length && <p>Aucune question enregistrée.</p>}
      {historyPage.error && <p className="inline-error" role="alert"><ErrorText error={historyPage.error} /></p>}
    </details>
    {historyLoading && <p className="history-notice" role="status">Chargement de la question enregistrée…</p>}
    {historyError && <div className="history-notice"><p className="inline-error" role="alert"><ErrorText error={historyError.error} /></p><Button variant="ghost" size="sm" onClick={() => { if (selectedQueryId) void historyLoader.current?.select(selectedQueryId); }}>Réessayer le chargement</Button></div>}
    <div className="analysis-history" ref={history} role="tabpanel" id="analysis-tabpanel" aria-labelledby={`analysis-tab-${tab}`} tabIndex={0}>
      {tab === "search" && search && searchScope && <p className="result-count">Périmètre de cette recherche : {searchScope.label}</p>}
      {tab === "search" ? search ? <div className="search-results"><p className="result-count tabular">{passagesFound(search.results.length)} · {Math.round(search.elapsed_ms)} ms</p><WarningNotices notices={warningNotices(search.warnings ?? [])} />{!search.results.length && (searchScope?.unindexed
        ? <PanelEmpty reason="index-incomplete" title="Index incomplet pour ce périmètre" description={`Aucun passage retrouvé dans les documents déjà indexés. ${unindexedSentence(searchScope.unindexed)}. Consultez le Suivi pour vérifier leur état et les actions possibles, puis relancez la recherche lorsqu'ils sont interrogeables.`} />
        : <PanelEmpty reason="no-match" title="Aucun passage retrouvé" description="La recherche n'a retrouvé aucun passage dans ce périmètre. Une recherche sans résultat ne prouve pas l'absence de l'information : reformulez ou élargissez le périmètre." />)}{search.results.map((result, index) => { const source = ("source" in result && result.source ? result.source : result) as Source; return source.version_id ? <SourceCard key={`${source.source_id}:${index}`} source={source} onOpen={() => openSource(source, source.query_id)} /> : <p key={index} className="inline-warning">Ce résultat ne désigne aucune version de document : il ne peut pas être ouvert dans le lecteur.</p>; })}</div>
        : <PanelEmpty reason="not-started" icon={<Search size={32} strokeWidth={1.5} aria-hidden="true" />} title="Retrouver un passage" description="Recherchez un code, une expression ou une notion dans le périmètre actif. La recherche lit l'index sans appeler le modèle de réponse." />
        : !queries.length ? <PanelEmpty reason="not-started" icon={<BookOpen size={32} strokeWidth={1.5} aria-hidden="true" />} title={tab === "comparison" ? "Comparer des documents" : "Aucune question posée"} description={tab === "comparison" ? "Définissez un périmètre de deux à quatre documents, puis posez votre question de comparaison. Chaque source indique son document et sa localisation." : "Posez une question sur le périmètre actif. Si la réponse cite des sources, ouvrez-les pour vérifier le contenu source utilisé."} /> : queries.map(query => <article className="query-turn" key={query.id} data-testid="query-turn" data-query-id={query.id}>
        <div className="question-message"><p>{query.question}</p><small>{query.scopeLabel}</small>{query.historicalState !== undefined && <small>Question enregistrée · mode non enregistré · périmètre actif inchangé</small>}</div>
        <div className="query-status" role="status"><StatusIndicator status={queryStatus(query.connection !== "closed" && query.historicalState !== undefined && !isQueryActive(query) ? query.historicalState : query.status)} active={isQueryActive(query)} />{query.connection === "reconnecting" && <Button variant="ghost" size="sm" onClick={() => { if (query.historicalState !== undefined) void historyLoader.current?.select(query.id); else connect(query.id, `/api/v1/queries/${encodeURIComponent(query.id)}/events`, query.lastEventId); }}><RefreshCw size={16} />Reconnecter</Button>}</div>
        {query.text && <CitationText text={query.text} sources={query.sources} onCitation={source => openSource(source, query.id)} />}
        {query.error && <p className="inline-error" role="alert"><CircleAlert size={14} aria-hidden="true" />{query.error}</p>}
        {["cancelled", "interrupted"].includes(query.status) && <p className="inline-warning">Cette réponse est incomplète : elle a été annulée ou interrompue avant la fin.</p>}
        <WarningNotices notices={warningNotices(query.warnings, query.finishReason)} sources={query.sources} onSource={source => openSource(source, query.id)} />
        {!!query.sources.length && <details className="sources-list" open><summary><Check size={14} aria-hidden="true" />{query.sources.length === 1 ? "1 source consultable" : `${query.sources.length} sources consultables`}</summary>{query.sources.map(source => <SourceCard key={source.source_id} source={source} onOpen={() => openSource(source, query.id)} />)}</details>}
      </article>)}
    </div>
    <div className="composer-area">
      {tab === "analysis" && <p className="inline-warning">L'analyse critique porte sur les sources retrouvées dans le périmètre actif. Elle ne vérifie pas exhaustivement le document et ne recalcule aucune formule de classeur.</p>}
      {state.selection && <div className="selection-action"><span>{state.selection.text.slice(0, 95)}{state.selection.text.length > 95 ? "…" : ""}</span><Button size="sm" variant="secondary" onClick={() => state.setScope({ kind: "selection", versionId: state.selection!.versionId, spans: state.selection!.spans }, "Texte sélectionné dans le document")}>Analyser la sélection</Button></div>}
      {state.selection && <p className="inline-warning">Le bouton « Analyser la sélection » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement.</p>}
      {tab === "comparison" && !compareAllowed && <p className="inline-warning">Définissez un périmètre de deux à quatre documents pour comparer.</p>}
      {error && <p className="inline-error" role="alert"><CircleAlert size={14} aria-hidden="true" /><ErrorText error={error.error} /></p>}
      <form onSubmit={event => { event.preventDefault(); submit(); }}><label className="sr-only" htmlFor="question-input">{tab === "search" ? "Votre recherche" : "Votre question"}</label><textarea id="question-input" value={question} onChange={event => setQuestion(event.target.value)} placeholder={tab === "search" ? "Expression ou référence à retrouver…" : tab === "comparison" ? "Quels points comparer entre ces documents ?" : "Posez une question sur ce périmètre…"} rows={3} maxLength={12000} onKeyDown={event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit(); } }} /><div className="composer-footer"><span><kbd>Ctrl</kbd> + <kbd>Entrée</kbd> {tab === "search" ? "pour rechercher" : "pour envoyer"}</span>{active ? <Button variant="danger" size="sm" onClick={() => void cancel()} disabled={cancelBusy} type="button"><Ban size={16} />{cancelBusy ? "Annulation…" : "Annuler"}</Button> : <Button size="sm" type="submit" disabled={!question.trim() || emptyScope || submission.isPending || searchMutation.isPending || tab === "comparison" && !compareAllowed}>{tab === "search" ? <Search size={16} /> : <Send size={16} />}{searchMutation.isPending ? "Recherche…" : submission.isPending ? "Envoi…" : tab === "search" ? "Rechercher" : "Envoyer"}</Button>}</div></form>
    </div>
  </aside>;
}
