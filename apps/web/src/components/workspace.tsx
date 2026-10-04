"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { FileText, X } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { restorePanelPreferences, savePanelPreferences } from "@/lib/panel-storage";
import { clampPanelWidth, COMPACT_LAYOUT_QUERY, isLibraryShortcut, nextLibraryMode, PANEL_WIDTH_MAX, PANEL_WIDTH_MIN, panelGridColumns } from "@/lib/panel-preferences";
import { sourcePage } from "@/lib/selection";
import { serviceDetail } from "@/lib/warnings";
import { citationLinkIds, registeredCitationLocation } from "@/lib/citation-link";
import { isActiveJobState, serviceStatus } from "@/lib/status";
import { isServiceUnavailable, pendingIndexCount } from "@/lib/panel-state";
import { readGeneration } from "@/lib/generation";
import type { Source } from "@/lib/types";
import { AnalysisPanel } from "./analysis-panel";
import { AppTopbar, type ServiceSummary } from "./app-topbar";
import { ContextBand } from "./context-band";
import { JobsPanel } from "./jobs-panel";
import { LibraryPanel, LibraryRail, type LibraryController } from "./library-panel";
import { PdfViewer } from "./pdf-viewer";
import { Button } from "./ui/button";
import { useErrorText, type Failure } from "./ui/error-text";
import { Sheet } from "./ui/sheet";

/** Vrai sous le point de rupture lg (64rem) ; faux avant hydratation, le CSS couvre cet intervalle. */
function useCompactLayout() {
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const query = window.matchMedia(COMPACT_LAYOUT_QUERY);
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return compact;
}

/**
 * Nœud DOM stable où un panneau est rendu par portail. Le nœud passe de sa
 * colonne à son panneau latéral sans démonter le panneau : l'historique des
 * questions, les flux en cours et le filtre de la bibliothèque sont conservés
 * quand la fenêtre franchit 1 024 px.
 */
function usePanelNode(slotRef: RefObject<HTMLDivElement | null>) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const attach = useCallback((slot: HTMLDivElement | null) => {
    slotRef.current = slot;
    if (!slot) return;
    const element = document.createElement("div");
    element.className = "panel-host";
    setNode(element);
    return () => { slotRef.current = null; element.remove(); };
  }, [slotRef]);
  return [node, attach] as const;
}

function nextFrame(action: () => void) { requestAnimationFrame(() => requestAnimationFrame(action)); }

type WorkspaceEntry = { kind: "none" } | { kind: "citation"; queryId: string; sourceId: string }
  | { kind: "document"; documentId: string; versionId: string; pageIndex: number } | { kind: "error"; error: unknown };

/** Le lien initial est lu une fois ; une citation invalide ne se rabat pas sur un document courant. */
function readWorkspaceEntry(search: string): WorkspaceEntry {
  try {
    const params = new URLSearchParams(search);
    const citation = citationLinkIds(params);
    if (citation) return { kind: "citation", ...citation };
    const documentId = params.get("document"); const versionId = params.get("version"); const page = Number(params.get("page") ?? "1");
    if (documentId && versionId && /^[\w-]{1,128}$/.test(documentId) && /^[\w-]{1,128}$/.test(versionId) && Number.isInteger(page) && page >= 1) return { kind: "document", documentId, versionId, pageIndex: page - 1 };
    return { kind: "none" };
  } catch (error) { return { kind: "error", error }; }
}

type SheetContext = { compact: boolean; documentId?: string; versionId?: string; source: Source | null };
function shouldCloseSheet(previous: SheetContext, next: SheetContext): boolean {
  return !next.compact || previous.documentId !== next.documentId || previous.versionId !== next.versionId || previous.source !== next.source;
}

function WorkspaceBody() {
  const state = useWorkspace();
  const compact = useCompactLayout();
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: ({ signal }) => api.readiness(signal), refetchInterval: 10000, retry: 1 });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: ({ signal }) => api.jobs(signal), refetchInterval: 3000 });
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), staleTime: 3000 });
  const [jobsVisible, setJobsVisible] = useState(false);
  const [sheet, setSheet] = useState<"library" | "analysis" | null>(null);
  const sheetContext = { compact, documentId: state.opened?.documentId, versionId: state.opened?.versionId, source: state.source };
  const [previousSheetContext, setPreviousSheetContext] = useState(sheetContext);
  if (previousSheetContext.compact !== compact || previousSheetContext.documentId !== sheetContext.documentId || previousSheetContext.versionId !== sheetContext.versionId || previousSheetContext.source !== state.source) {
    setPreviousSheetContext(sheetContext);
    if (shouldCloseSheet(previousSheetContext, sheetContext)) setSheet(null);
  }
  // Workspace ne monte qu'après la session valide (page.tsx). Aucun accès navigateur côté export.
  const [entry] = useState(() => readWorkspaceEntry(typeof window === "undefined" ? "" : window.location.search));
  // Échec d'ouverture d'une citation ou d'un lien : gardé tel quel, son texte se calcule au rendu.
  const [failure, setFailure] = useState<Failure | null>(() => entry.kind === "error" ? { error: entry.error } : null);
  const errorText = useErrorText();
  const layout = useRef<HTMLDivElement>(null);
  const librarySlot = useRef<HTMLDivElement>(null);
  const analysisSlot = useRef<HTMLDivElement>(null);
  const librarySheetBody = useRef<HTMLDivElement>(null);
  const analysisSheetBody = useRef<HTMLDivElement>(null);
  const libraryController = useRef<LibraryController | null>(null);
  const [libraryNode, attachLibrary] = usePanelNode(librarySlot);
  const [analysisNode, attachAnalysis] = usePanelNode(analysisSlot);
  const activeJobs = jobs.data ? jobs.data.jobs.filter(job => isActiveJobState(job.state ?? job.status)).length : null;
  const open = state.open;

  useEffect(() => {
    restorePanelPreferences();
    let disposed = false;
    if (entry.kind === "citation") {
      void api.citation(entry.queryId, entry.sourceId).then(source => {
        const location = registeredCitationLocation(source, entry.queryId, entry.sourceId);
        if (!disposed) open(location, source);
      }).catch(failure => { if (!disposed) setFailure({ error: failure }); });
    } else if (entry.kind === "document") open({ documentId: entry.documentId, versionId: entry.versionId, pageIndex: entry.pageIndex });
    const unsubscribe = useWorkspace.subscribe((next, previous) => { if (next.libraryMode !== previous.libraryMode || next.analysisMode !== previous.analysisMode || next.panelWidths !== previous.panelWidths) savePanelPreferences(); });
    return () => { disposed = true; unsubscribe(); };
  }, [entry, open]);
  useEffect(() => {
    if (!state.opened) return;
    const params = new URLSearchParams({ document: state.opened.documentId, version: state.opened.versionId, page: String(state.opened.pageIndex + 1) });
    if (state.source?.source_id && state.source.query_id && state.source.extraction_revision_id) { params.set("citation_query", state.source.query_id); params.set("citation_source", state.source.source_id); }
    window.history.replaceState(null, "", `/workspace/?${params}`);
  }, [state.opened, state.source]);

  // Chaque panneau vit dans sa colonne au-delà de 1 024 px, dans son panneau latéral en deçà.
  useLayoutEffect(() => {
    const place = (node: HTMLElement | null, target: HTMLElement | null) => { if (node && target && node.parentElement !== target) target.appendChild(node); };
    place(libraryNode, compact ? librarySheetBody.current : librarySlot.current);
    place(analysisNode, compact ? analysisSheetBody.current : analysisSlot.current);
  }, [compact, libraryNode, analysisNode]);

  const toggleLibrary = () => {
    if (compact) setSheet(current => current === "library" ? null : "library");
    else state.setPanels({ libraryMode: nextLibraryMode(useWorkspace.getState().libraryMode) });
  };
  const toggleAnalysis = () => {
    if (compact) setSheet("analysis");
    else state.setPanels({ analysisMode: useWorkspace.getState().analysisMode === "expanded" ? "hidden" : "expanded" });
  };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isLibraryShortcut(event)) return;
      // Sous 1 024 px, le raccourci n'ouvre pas la bibliothèque par-dessus un autre panneau modal.
      if (compact && (jobsVisible || sheet === "analysis")) return;
      event.preventDefault();
      toggleLibrary();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const expandLibrary = (then?: (controller: LibraryController) => void) => {
    state.setPanels({ libraryMode: "expanded" });
    if (then) nextFrame(() => { if (libraryController.current) then(libraryController.current); });
  };
  const focusReader = () => document.getElementById("lecteur")?.focus();
  const focusQuestion = () => {
    if (compact) setSheet("analysis");
    else if (useWorkspace.getState().analysisMode === "hidden") state.setPanels({ analysisMode: "expanded" });
    nextFrame(() => document.getElementById("question-input")?.focus());
  };

  const sourceClick = async (source: Source, queryId?: string) => {
    if (queryId && !source.source_id) throw new Error("Cette citation ne possède pas d'identifiant enregistré : elle ne peut pas être ouverte.");
    const exact = queryId ? await api.citation(queryId, source.source_id!) : source;
    if (!exact.version_id || !exact.document_id) throw new Error("Cette source ne désigne aucune version de document consultable.");
    state.open(queryId ? registeredCitationLocation(exact, queryId, source.source_id!) : { documentId: exact.document_id, versionId: exact.version_id, pageIndex: sourcePage(exact) }, exact);
  };
  const resize = (side: 0 | 1, element: HTMLElement, pointerId: number) => {
    element.setPointerCapture(pointerId);
    const start = (event: PointerEvent) => {
      const rect = layout.current?.getBoundingClientRect();
      if (!rect) return;
      const value = side === 0 ? (event.clientX - rect.left) / rect.width * 100 : (rect.right - event.clientX) / rect.width * 100;
      const next: [number, number] = [...useWorkspace.getState().panelWidths];
      next[side] = clampPanelWidth(value);
      state.setPanels({ panelWidths: next });
    };
    const finish = () => { element.removeEventListener("pointermove", start); element.removeEventListener("pointerup", finish); element.removeEventListener("pointercancel", finish); };
    element.addEventListener("pointermove", start); element.addEventListener("pointerup", finish); element.addEventListener("pointercancel", finish);
  };
  const adjustKeyboard = (side: 0 | 1, delta: number) => {
    const next: [number, number] = [...state.panelWidths]; next[side] = clampPanelWidth(next[side] + delta); state.setPanels({ panelWidths: next });
  };

  const libraryExpanded = !compact && state.libraryMode === "expanded";
  const analysisExpanded = !compact && state.analysisMode === "expanded";
  const comparisonDocuments = state.scope.kind === "documents" && state.scope.documentIds.length >= 2 && state.scope.documentIds.length <= 4 ? tree.data?.documents.filter(document => state.scope.kind === "documents" && state.scope.documentIds.includes(document.id)) ?? [] : [];
  const pendingDocuments = tree.data ? pendingIndexCount(tree.data) : 0;
  const blockers = !readiness.isError ? readiness.data?.blockers ?? [] : [];
  // isPending (ni donnée ni erreur) et non isLoading : pendant l'export statique, aucune requête ne part
  // et isLoading reste faux ; l'état serait alors présenté à tort comme « non prêt ».
  const service: ServiceSummary = {
    status: serviceStatus({ loading: readiness.isPending, failed: readiness.isError, unreachable: isServiceUnavailable(readiness.error), ready: readiness.data?.ready, pendingDocuments }),
    detail: serviceDetail({ failed: readiness.isError, error: readiness.isError ? errorText(readiness.error) : undefined, ready: readiness.data?.ready, blockers, pendingDocuments }),
  };
  const closeButton = (label: string) => <Button variant="ghost" size="sm" onClick={() => setSheet(null)} aria-label={label}><X size={16} aria-hidden="true" />Fermer</Button>;

  return <>
    <nav className="skip-links" aria-label="Accès rapide">
      <a href="#lecteur" onClick={event => { event.preventDefault(); focusReader(); }}>Aller au lecteur</a>
      <a href="#question-input" onClick={event => { event.preventDefault(); focusQuestion(); }}>Aller à la zone de question</a>
    </nav>
    <div className="workspace-shell">
      <AppTopbar compact={compact} libraryMode={state.libraryMode} analysisMode={state.analysisMode} librarySheetOpen={sheet === "library"} analysisSheetOpen={sheet === "analysis"}
        onLibraryToggle={toggleLibrary} onAnalysisToggle={toggleAnalysis} service={service} activeJobs={activeJobs} jobsFailed={jobs.isError} jobsOpen={jobsVisible} onJobsOpen={() => setJobsVisible(true)} />
      {/* Matériel de la génération (W025) : après une lecture du suivi en échec, l'instance a pu redémarrer dans un autre mode. */}
      <ContextBand scope={state.scope} tree={tree.data} treeFailed={tree.isError && !tree.data} blockers={blockers} error={failure ? errorText(failure.error) : ""} onDismissError={() => setFailure(null)} service={service}
        generation={jobs.isError ? null : readGeneration(jobs.data?.generation)} />
      {comparisonDocuments.length > 0 && <nav className="comparison-documents" aria-label="Documents comparés"><span>Comparer {comparisonDocuments.length} documents</span>{comparisonDocuments.map(document => <button key={document.id} className={state.opened?.documentId === document.id ? "is-active" : ""} disabled={!document.active_version_id && !document.version_id} title={!document.active_version_id && !document.version_id ? "Ce document n'a pas encore de version consultable." : undefined} onClick={() => state.open({ documentId: document.id, versionId: document.active_version_id ?? document.version_id!, pageIndex: 0 })}><FileText size={14} aria-hidden="true" />{document.name}</button>)}</nav>}
      <div className="workspace-layout" ref={layout} style={{ gridTemplateColumns: panelGridColumns({ compact, library: state.libraryMode, analysis: state.analysisMode, widths: state.panelWidths }) }}>
        <div className="library-column" data-mode={compact ? "sheet" : state.libraryMode}>
          {!compact && state.libraryMode === "rail" && <LibraryRail selectedCount={state.selectedIds.length}
            onImport={() => { expandLibrary(); libraryController.current?.importFiles(); }}
            onFilter={() => expandLibrary(controller => controller.focusFilter())}
            onSelection={() => expandLibrary(controller => controller.focusSelection())} />}
          <div className="panel-wrapper library-wrapper" ref={attachLibrary} hidden={!libraryExpanded} />
        </div>
        <div className="panel-resizer resizer-library" hidden={!libraryExpanded} role="separator" aria-label="Largeur de la bibliothèque" aria-orientation="vertical" aria-valuemin={PANEL_WIDTH_MIN} aria-valuemax={PANEL_WIDTH_MAX} aria-valuenow={state.panelWidths[0]} tabIndex={libraryExpanded ? 0 : -1} onPointerDown={event => resize(0, event.currentTarget, event.pointerId)} onKeyDown={event => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); adjustKeyboard(0, event.key === "ArrowLeft" ? -1 : 1); } }} />
        <main id="lecteur" className="reader-slot" aria-label="Lecteur" tabIndex={-1}><PdfViewer /></main>
        <div className="panel-resizer resizer-analysis" hidden={!analysisExpanded} role="separator" aria-label="Largeur de l'analyse" aria-orientation="vertical" aria-valuemin={PANEL_WIDTH_MIN} aria-valuemax={PANEL_WIDTH_MAX} aria-valuenow={state.panelWidths[1]} tabIndex={analysisExpanded ? 0 : -1} onPointerDown={event => resize(1, event.currentTarget, event.pointerId)} onKeyDown={event => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); adjustKeyboard(1, event.key === "ArrowLeft" ? 1 : -1); } }} />
          <div className="panel-wrapper analysis-wrapper" ref={attachAnalysis} hidden={!analysisExpanded} />
      </div>
      <Sheet side="left" open={compact && sheet === "library"} onClose={() => setSheet(null)} labelledBy="library-heading" bodyRef={librarySheetBody} className="sheet-library" />
      <Sheet side="right" open={compact && sheet === "analysis"} onClose={() => setSheet(null)} labelledBy="analysis-heading" bodyRef={analysisSheetBody} className="sheet-analysis" />
      <Sheet side="right" open={jobsVisible} onClose={() => setJobsVisible(false)} labelledBy="jobs-heading" className="sheet-jobs"><JobsPanel jobs={jobs} tree={tree} onClose={() => setJobsVisible(false)} /></Sheet>
      {libraryNode && createPortal(<LibraryPanel controller={libraryController} headerAction={compact ? closeButton("Fermer la bibliothèque") : undefined} />, libraryNode)}
      {analysisNode && createPortal(<AnalysisPanel onSource={sourceClick} headerAction={compact ? closeButton("Fermer l'analyse") : undefined} />, analysisNode)}
    </div>
  </>;
}

export function Workspace() {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, gcTime: 60000 } } }));
  return <QueryClientProvider client={client}><WorkspaceBody /></QueryClientProvider>;
}
