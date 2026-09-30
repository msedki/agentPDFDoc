"use client";
import { useEffect, useRef, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ChevronDown, FileText, Folder, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, X } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace, restorePanelPreferences, savePanelPreferences } from "@/lib/store";
import { sourcePage } from "@/lib/selection";
import { errorMessage } from "@/lib/utils";
import { warningText } from "@/lib/warnings";
import { useCitationRevision } from "@/lib/use-citation-revision";
import { citationLinkIds, registeredCitationLocation } from "@/lib/citation-link";
import type { Scope, Source } from "@/lib/types";
import { AnalysisPanel } from "./analysis-panel";
import { LibraryPanel, documentStateLabels } from "./library-panel";
import { PdfViewer } from "./pdf-viewer";
import { Button } from "./ui/button";

function ScopeControl() {
  const state = useWorkspace();
  const binding = useCitationRevision();
  const [visible, setVisible] = useState(false);
  const [kind, setKind] = useState<Scope["kind"]>("library");
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [folderId, setFolderId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [failure, setFailure] = useState("");
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), staleTime: 3000 });
  const outline = useQuery({ queryKey: ["outline", state.opened?.versionId, binding.revision], queryFn: ({ signal }) => api.outline(state.opened!.versionId, signal, binding.revision), enabled: Boolean(state.opened) && !binding.error, staleTime: 30000 });
  const metadata = useQuery({ queryKey: ["document", state.opened?.documentId], queryFn: ({ signal }) => api.document(state.opened!.documentId, signal), enabled: Boolean(state.opened), staleTime: 30000 });
  const apply = () => {
    if ((kind === "pages" || kind === "section") && !binding.actions.allowed) { setFailure(binding.actions.reason ?? "La révision doit être vérifiée."); return; }
    const name = metadata.data?.name ?? "Document ouvert";
    if (kind === "library") state.setScope({ kind }, "Toute la bibliothèque");
    else if (kind === "documents") {
      if (!state.selectedIds.length) { setFailure("Sélectionnez au moins un PDF dans la bibliothèque."); return; }
      state.setScope({ kind, documentIds: [...state.selectedIds] }, state.selectedIds.length === 1 ? tree.data?.documents.find(document => document.id === state.selectedIds[0])?.name ?? "PDF sélectionné" : `${state.selectedIds.length} PDF sélectionnés`);
    } else if (kind === "folder") {
      const folder = tree.data?.folders.find(value => value.id === folderId);
      if (!folder) { setFailure("Choisissez un dossier existant."); return; }
      state.setScope({ kind, folderId, recursive: true }, `${folder.path} · sous-dossiers inclus`);
    } else if (kind === "selection") {
      if (!state.selection) { setFailure("Sélectionnez un texte rattaché aux blocs extraits du document."); return; }
      state.setScope({ kind, versionId: state.selection.versionId, spans: state.selection.spans }, "Sélection de texte du document");
    } else if (state.opened && kind === "pages") {
      if (pageStart < 1 || pageEnd < pageStart || pageEnd > (metadata.data?.page_count ?? 0)) { setFailure("La plage doit correspondre aux pages du document ouvert."); return; }
      state.setScope({ kind, versionId: state.opened.versionId, pageStart: pageStart - 1, pageEnd: pageEnd - 1 }, `${name} · pages ${pageStart}–${pageEnd}`);
    } else if (state.opened && kind === "section") {
      const section = outline.data?.sections.find(value => value.id === sectionId);
      if (!section) { setFailure("Choisissez une section extraite disponible."); return; }
      state.setScope({ kind, versionId: state.opened.versionId, sectionId }, `${name} · ${section.title}`);
    } else { setFailure("Ouvrez un document pour définir ce périmètre."); return; }
    setVisible(false); setFailure("");
  };
  return <div className="scope-control"><button className="scope-trigger" onClick={() => { setVisible(value => !value); setKind(state.scope.kind); setPageStart((state.opened?.pageIndex ?? 0) + 1); setPageEnd((state.opened?.pageIndex ?? 0) + 1); }} aria-expanded={visible}><span className="eyebrow">Périmètre</span><strong>{state.scopeLabel}</strong><ChevronDown size={15} /></button>{visible && <div className="scope-popover">
    <h3>Définir le périmètre</h3><p>La lecture et les citations ne le changent pas.</p>
    <label>Type<select value={kind} onChange={event => { setKind(event.target.value as Scope["kind"]); setFailure(""); }}><option value="library">Toute la bibliothèque</option><option value="folder">Dossier et descendants</option><option value="documents">PDF sélectionnés</option><option value="section" disabled={!binding.actions.allowed}>Section du PDF ouvert</option><option value="pages" disabled={!binding.actions.allowed}>Pages du PDF ouvert</option><option value="selection">Sélection de texte</option></select></label>
    {binding.actions.reason && <p role="status" className="inline-warning">{binding.actions.reason}</p>}
    {kind === "documents" && <p>{state.selectedIds.length} document(s) coché(s) dans la bibliothèque.</p>}
    {kind === "folder" && <label>Dossier<select value={folderId} onChange={event => setFolderId(event.target.value)}><option value="">Choisir un dossier…</option>{tree.data?.folders.map(folder => <option value={folder.id} key={folder.id}>{folder.path}</option>)}</select></label>}
    {kind === "pages" && <div className="page-range"><label>De la page<input type="number" min={1} max={metadata.data?.page_count || 1} value={pageStart} onChange={event => setPageStart(Number(event.target.value))} /></label><label>À la page<input type="number" min={pageStart} max={metadata.data?.page_count || 1} value={pageEnd} onChange={event => setPageEnd(Number(event.target.value))} /></label></div>}
    {kind === "section" && <label>Section<select value={sectionId} onChange={event => setSectionId(event.target.value)}><option value="">Choisir une section…</option>{outline.data?.sections.map(section => <option value={section.id} key={section.id}>{section.title}</option>)}</select></label>}
    {kind === "selection" && <p>{state.selection ? `« ${state.selection.text.slice(0, 100)} »` : "Aucune sélection réconciliée avec les blocs source."}</p>}
    {failure && <p role="alert" className="inline-warning">{failure}</p>}
    <div className="scope-popover-actions"><Button size="sm" variant="ghost" onClick={() => setVisible(false)}>Fermer</Button><Button size="sm" disabled={(kind === "pages" || kind === "section") && !binding.actions.allowed} onClick={apply}>Appliquer</Button></div>
  </div>}</div>;
}

function WorkspaceBody() {
  const state = useWorkspace();
  const client = useQueryClient();
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: ({ signal }) => api.readiness(signal), refetchInterval: 10000, retry: 1 });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: ({ signal }) => api.jobs(signal), refetchInterval: 3000 });
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), staleTime: 3000 });
  const [jobsVisible, setJobsVisible] = useState(false);
  const [error, setError] = useState("");
  const [pendingJob, setPendingJob] = useState<string | null>(null);
  const [modeNotice, setModeNotice] = useState("");
  const layout = useRef<HTMLDivElement>(null);
  const activeJobs = jobs.data?.jobs.filter(job => !["done", "completed", "ready", "cancelled", "error", "failed"].includes(job.state ?? job.status ?? "")) ?? [];
  useEffect(() => {
    restorePanelPreferences();
    let disposed = false;
    const params = new URLSearchParams(window.location.search);
    const documentId = params.get("document"); const versionId = params.get("version"); const page = Number(params.get("page") ?? "1");
    try {
      const citation = citationLinkIds(params);
      if (citation) {
        void api.citation(citation.queryId, citation.sourceId).then(source => {
          const location = registeredCitationLocation(source, citation.queryId, citation.sourceId);
          if (!disposed) state.open(location, source);
        }).catch(failure => { if (!disposed) setError(errorMessage(failure)); });
      } else if (documentId && versionId && /^[\w-]{1,128}$/.test(documentId) && /^[\w-]{1,128}$/.test(versionId) && Number.isInteger(page) && page >= 1) state.open({ documentId, versionId, pageIndex: page - 1 });
    } catch (failure) { setError(errorMessage(failure)); }
    const unsubscribe = useWorkspace.subscribe((next, previous) => { if (next.libraryHidden !== previous.libraryHidden || next.analysisHidden !== previous.analysisHidden || next.panelWidths !== previous.panelWidths) savePanelPreferences(); });
    return () => { disposed = true; unsubscribe(); };
  }, []);
  useEffect(() => {
    if (!state.opened) return;
    const params = new URLSearchParams({ document: state.opened.documentId, version: state.opened.versionId, page: String(state.opened.pageIndex + 1) });
    if (state.source?.source_id && state.source.query_id && state.source.extraction_revision_id) { params.set("citation_query", state.source.query_id); params.set("citation_source", state.source.source_id); }
    window.history.replaceState(null, "", `/workspace/?${params}`);
  }, [state.opened, state.source]);
  const sourceClick = async (source: Source, queryId?: string) => {
    if (queryId && !source.source_id) throw new Error("Cette citation ne possède pas d'identifiant enregistré.");
    const exact = queryId ? await api.citation(queryId, source.source_id!) : source;
    if (!exact.version_id || !exact.document_id) throw new Error("Cette source ne contient pas de version documentaire consultable.");
    state.open(queryId ? registeredCitationLocation(exact, queryId, source.source_id!) : { documentId: exact.document_id, versionId: exact.version_id, pageIndex: sourcePage(exact) }, exact);
  };
  const jobAction = async (id: string, action: () => Promise<unknown>, notice?: string) => {
    setPendingJob(id); setError("");
    try {
      await action();
      if (notice) setModeNotice(notice);
      await Promise.all([client.invalidateQueries({ queryKey: ["jobs"] }), client.invalidateQueries({ queryKey: ["tree"] }), client.invalidateQueries({ queryKey: ["readiness"] })]);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setPendingJob(null); }
  };
  const resize = (side: 0 | 1, element: HTMLElement, pointerId: number) => {
    element.setPointerCapture(pointerId);
    const start = (event: PointerEvent) => {
      const rect = layout.current?.getBoundingClientRect();
      if (!rect) return;
      const value = side === 0 ? (event.clientX - rect.left) / rect.width * 100 : (rect.right - event.clientX) / rect.width * 100;
      const current = useWorkspace.getState().panelWidths;
      const next: [number, number] = [...current];
      next[side] = Math.max(16, Math.min(36, value));
      state.setPanels({ panelWidths: next });
    };
    const finish = () => { element.removeEventListener("pointermove", start); element.removeEventListener("pointerup", finish); element.removeEventListener("pointercancel", finish); };
    element.addEventListener("pointermove", start); element.addEventListener("pointerup", finish); element.addEventListener("pointercancel", finish);
  };
  const adjustKeyboard = (side: 0 | 1, delta: number) => {
    const next: [number, number] = [...state.panelWidths]; next[side] = Math.min(36, Math.max(16, next[side] + delta)); state.setPanels({ panelWidths: next });
  };
  const gridTemplateColumns = `${state.libraryHidden ? "0px 0px" : `${state.panelWidths[0]}% 5px`} minmax(0, 1fr) ${state.analysisHidden ? "0px 0px" : `5px ${state.panelWidths[1]}%`}`;
  const comparisonDocuments = state.scope.kind === "documents" && state.scope.documentIds.length >= 2 && state.scope.documentIds.length <= 4 ? tree.data?.documents.filter(document => state.scope.kind === "documents" && state.scope.documentIds.includes(document.id)) ?? [] : [];
  return <main className="workspace-shell">
    <header className="app-header"><div className="app-title"><span className="app-mark"><FileText size={21} strokeWidth={1.5} /></span><div><p className="eyebrow">Poste documentaire local</p><h1>Atelier documentaire</h1></div></div><div className="app-actions"><span className={`readiness-badge ${readiness.isError || readiness.data?.ready === false ? "has-warning" : ""}`} title={readiness.isError ? errorMessage(readiness.error) : readiness.data?.blockers?.join(" · ")}><i />{readiness.isLoading ? "Connexion…" : readiness.isError ? "Service indisponible" : readiness.data?.ready === true ? "Services prêts" : "Préparation requise"}</span><Button variant="ghost" size="sm" onClick={() => setJobsVisible(value => !value)} aria-expanded={jobsVisible}><Activity size={16} />Suivi{activeJobs.length > 0 && <span className="count-pill">{activeJobs.length}</span>}</Button><Button variant="ghost" size="icon" onClick={() => state.setPanels({ libraryHidden: !state.libraryHidden })} aria-label={state.libraryHidden ? "Afficher la bibliothèque" : "Replier la bibliothèque"}>{state.libraryHidden ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</Button><Button variant="ghost" size="icon" onClick={() => state.setPanels({ analysisHidden: !state.analysisHidden })} aria-label={state.analysisHidden ? "Afficher l'analyse" : "Replier l'analyse"}>{state.analysisHidden ? <PanelRightOpen size={18} /> : <PanelRightClose size={18} />}</Button></div></header>
    <div className="workspace-scope-bar"><ScopeControl /><p>Les réponses gardent leur périmètre et leurs versions.</p></div>
    {readiness.data?.blockers?.length ? <div className="readiness-notice" role="status">{readiness.data.blockers.join(" · ")}</div> : null}
    {comparisonDocuments.length > 0 && <nav className="comparison-documents" aria-label="Documents comparés"><span>Comparer {comparisonDocuments.length} PDF</span>{comparisonDocuments.map(document => <button key={document.id} className={state.opened?.documentId === document.id ? "is-active" : ""} disabled={!document.active_version_id && !document.version_id} onClick={() => state.open({ documentId: document.id, versionId: document.active_version_id ?? document.version_id!, pageIndex: 0 })}><FileText size={13} />{document.name}</button>)}</nav>}
    <div className="workspace-layout" ref={layout} style={{ gridTemplateColumns }}>
      <div className="panel-wrapper library-wrapper" hidden={state.libraryHidden}><LibraryPanel /></div>
      <div className="panel-resizer" hidden={state.libraryHidden} role="separator" aria-label="Largeur de la bibliothèque" aria-orientation="vertical" aria-valuemin={16} aria-valuemax={36} aria-valuenow={state.panelWidths[0]} tabIndex={state.libraryHidden ? -1 : 0} onPointerDown={event => resize(0, event.currentTarget, event.pointerId)} onKeyDown={event => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); adjustKeyboard(0, event.key === "ArrowLeft" ? -1 : 1); } }} />
      <PdfViewer />
      <div className="panel-resizer" hidden={state.analysisHidden} role="separator" aria-label="Largeur de l'analyse" aria-orientation="vertical" aria-valuemin={16} aria-valuemax={36} aria-valuenow={state.panelWidths[1]} tabIndex={state.analysisHidden ? -1 : 0} onPointerDown={event => resize(1, event.currentTarget, event.pointerId)} onKeyDown={event => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); adjustKeyboard(1, event.key === "ArrowLeft" ? 1 : -1); } }} />
      <div className="panel-wrapper analysis-wrapper" hidden={state.analysisHidden}><AnalysisPanel onSource={sourceClick} /></div>
    </div>
    {jobsVisible && <section className="jobs-drawer" aria-label="Suivi des traitements">
      <div className="panel-heading"><h2>Suivi des traitements</h2><Button variant="ghost" size="icon" onClick={() => setJobsVisible(false)} aria-label="Fermer le suivi"><X size={17} /></Button></div>
      <div className="job-mode-actions"><Button variant="secondary" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction("runtime-mode", () => api.runtimeMode("interactive"), "Priorité aux questions demandée. Les imports se reprennent explicitement.")}>Priorité aux questions</Button><Button variant="secondary" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction("runtime-mode", () => api.runtimeMode("ingestion"), "Priorité aux imports demandée. Le service gère la transition en cours.")}>Priorité aux imports</Button></div>
      {modeNotice && <p role="status" className="library-notice">{modeNotice}</p>}
      {jobs.isError ? <p role="alert">{errorMessage(jobs.error)}</p> : jobs.isLoading ? <p>Chargement…</p> : !jobs.data?.jobs.length ? <p>Aucun traitement enregistré.</p> : jobs.data.jobs.map(job => {
        const document = tree.data?.documents.find(item => item.id === job.document_id);
        const jobState = job.state ?? job.status ?? "";
        const published = job.published ?? Boolean(job.published_at || job.generation_id && document?.active_generation_id === job.generation_id);
        const coverage = job.coverage ?? document?.coverage;
        return <article key={job.id}>
          <div><strong>{document?.name ?? "Traitement documentaire"}</strong><span>{jobState === "paused" ? "Indexation en pause — reprise manuelle" : documentStateLabels[jobState] ?? jobState}{job.stage ? ` · ${job.stage}` : ""}</span></div>
          {typeof job.progress === "number" && <progress max={job.progress > 1 ? 100 : 1} value={job.progress} />}
          {coverage && typeof coverage.processed === "number" && typeof coverage.total === "number" && <p>{coverage.processed}/{coverage.total} pages traitées{typeof coverage.ocr === "number" ? ` · ${coverage.ocr} pages avec OCR` : ""}</p>}
          {(job.error || job.error_message) && <p className="inline-warning">{job.error ?? job.error_message}</p>}
          {job.warnings?.map((warning, index) => <p key={index} className="inline-warning">{warningText(warning)}</p>)}
          {jobState === "ready_partial" && <><p className="inline-warning">{published ? "Extraction partielle publiée : les réponses restent limitées aux pages traitées." : "Extraction partielle vérifiée. Les pages manquantes ne seront pas recherchées."}</p>{!published && <Button variant="secondary" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction(job.id, () => api.publishPartial(job.id))}>Utiliser cette extraction partielle</Button>}</>}
          {["queued", "running", "extracting", "ocr", "indexing"].includes(jobState) && <Button variant="secondary" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction(job.id, () => api.pauseJob(job.id))}>Mettre en pause</Button>}
          {["paused", "checkpointed", "interrupted"].includes(jobState) && <Button variant="secondary" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction(job.id, () => api.resumeJob(job.id))}>Reprendre l'indexation</Button>}
          {!["done", "completed", "ready", "ready_partial", "cancelled", "error", "failed"].includes(jobState) && <Button variant="danger" size="sm" disabled={Boolean(pendingJob)} onClick={() => void jobAction(job.id, () => api.cancelJob(job.id))}>Annuler ce traitement</Button>}
        </article>;
      })}
      {error && <p className="inline-warning" role="alert">{error}</p>}
    </section>}
  </main>;
}

export function Workspace() {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, gcTime: 60000 } } }));
  return <QueryClientProvider client={client}><WorkspaceBody /></QueryClientProvider>;
}
