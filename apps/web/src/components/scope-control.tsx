"use client";
import { useId, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { errorMessage } from "@/lib/utils";
import { useCitationRevision } from "@/lib/use-citation-revision";
import { pageRangeError, versionPageCount } from "@/lib/page-range";
import { selectedDocumentsSentence } from "@/lib/panel-state";
import type { Scope } from "@/lib/types";
import { Button } from "./ui/button";

/** Choix explicite du périmètre des recherches et des questions, au centre de la barre supérieure. */
export function ScopeControl() {
  const state = useWorkspace();
  const binding = useCitationRevision();
  const [visible, setVisible] = useState(false);
  const [kind, setKind] = useState<Scope["kind"]>("library");
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [folderId, setFolderId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [failure, setFailure] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const popoverId = useId();
  const titleId = useId();
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), staleTime: 3000 });
  const outline = useQuery({ queryKey: ["outline", state.opened?.versionId, binding.revision], queryFn: ({ signal }) => api.outline(state.opened!.versionId, signal, binding.revision), enabled: Boolean(state.opened) && !binding.error, staleTime: 30000 });
  const metadata = useQuery({ queryKey: ["document", state.opened?.documentId], queryFn: ({ signal }) => api.document(state.opened!.documentId, signal), enabled: Boolean(state.opened), staleTime: 30000 });
  const pageCount = versionPageCount(metadata.data, state.opened?.versionId);
  const close = (restoreFocus: boolean) => { setVisible(false); setFailure(""); if (restoreFocus) trigger.current?.focus(); };
  const apply = () => {
    if ((kind === "pages" || kind === "section") && !binding.actions.allowed) { setFailure(binding.actions.reason ?? "La révision de la citation ouverte doit d'abord être vérifiée."); return; }
    const name = metadata.data?.name ?? "Document ouvert";
    if (kind === "library") state.setScope({ kind }, "Toute la bibliothèque");
    else if (kind === "documents") {
      if (!state.selectedIds.length) { setFailure("Cochez au moins un document dans la bibliothèque."); return; }
      state.setScope({ kind, documentIds: [...state.selectedIds] }, state.selectedIds.length === 1 ? tree.data?.documents.find(document => document.id === state.selectedIds[0])?.name ?? "1 document sélectionné" : `${state.selectedIds.length} documents sélectionnés`);
    } else if (kind === "folder") {
      const folder = tree.data?.folders.find(value => value.id === folderId);
      if (!folder) { setFailure("Choisissez un dossier dans la liste."); return; }
      state.setScope({ kind, folderId, recursive: true }, `${folder.path} · sous-dossiers inclus`);
    } else if (kind === "selection") {
      if (!state.selection) { setFailure("Sélectionnez dans le lecteur un texte qui correspond aux blocs extraits, puis appliquez de nouveau."); return; }
      state.setScope({ kind, versionId: state.selection.versionId, spans: state.selection.spans }, "Texte sélectionné dans le document");
    } else if (state.opened && kind === "pages") {
      const rangeError = pageRangeError(pageStart, pageEnd, pageCount);
      if (rangeError) { setFailure(rangeError); return; }
      state.setScope({ kind, versionId: state.opened.versionId, pageStart: pageStart - 1, pageEnd: pageEnd - 1 }, `${name} · pages ${pageStart}–${pageEnd}`);
    } else if (state.opened && kind === "section") {
      const section = outline.data?.sections.find(value => value.id === sectionId);
      if (!section) { setFailure("Choisissez une section dans la liste."); return; }
      state.setScope({ kind, versionId: state.opened.versionId, sectionId }, `${name} · ${section.title}`);
    } else { setFailure("Ouvrez d'abord un document dans le lecteur."); return; }
    close(false);
  };
  const unavailable = (what: string, error: unknown) => `${what} : ${errorMessage(error)}`;
  return <div className="scope-control" onKeyDown={event => { if (visible && event.key === "Escape") { event.preventDefault(); close(true); } }}>
    <button ref={trigger} type="button" className="scope-trigger" aria-expanded={visible} aria-controls={visible ? popoverId : undefined} onClick={() => { setVisible(value => !value); setKind(state.scope.kind); setFailure(""); setPageStart((state.opened?.pageIndex ?? 0) + 1); setPageEnd((state.opened?.pageIndex ?? 0) + 1); }}><span className="eyebrow">Périmètre</span><strong>{state.scopeLabel}</strong><ChevronDown size={14} aria-hidden="true" /></button>
    {visible && <div className="scope-popover" id={popoverId} role="region" aria-labelledby={titleId}>
      <h2 id={titleId}>Définir le périmètre</h2><p className="scope-help">Les recherches et les questions portent sur ce périmètre ; chaque réponse garde celui de son envoi, avec les versions consultées. Ouvrir un document ou une citation ne le modifie pas.</p>
      <label>Portée<select value={kind} onChange={event => { setKind(event.target.value as Scope["kind"]); setFailure(""); }}><option value="library">Toute la bibliothèque</option><option value="folder">Dossier et ses sous-dossiers</option><option value="documents">Documents sélectionnés</option><option value="section" disabled={!binding.actions.allowed}>Section du document ouvert</option><option value="pages" disabled={!binding.actions.allowed}>Pages du document ouvert</option><option value="selection">Texte sélectionné dans le document</option></select></label>
      {binding.actions.reason && <p role="status" className="inline-warning">{binding.actions.reason}</p>}
      {kind === "documents" && <p className="scope-help">{selectedDocumentsSentence(state.selectedIds.length)} dans la bibliothèque.</p>}
      {kind === "folder" && (tree.isError ? <p role="alert" className="inline-error">{unavailable("Liste des dossiers indisponible", tree.error)}</p> : tree.isLoading ? <p role="status" className="scope-help">Chargement des dossiers…</p> : <label>Dossier<select value={folderId} onChange={event => setFolderId(event.target.value)}><option value="">{tree.data?.folders.length ? "Choisir un dossier…" : "Aucun dossier dans la bibliothèque"}</option>{tree.data?.folders.map(folder => <option value={folder.id} key={folder.id}>{folder.path}</option>)}</select></label>)}
      {kind === "pages" && metadata.isError && <p role="alert" className="inline-error">{unavailable("Nombre de pages indisponible", metadata.error)}</p>}
      {kind === "pages" && <div className="page-range"><label>De la page<input type="number" min={1} max={pageCount ?? 1} value={pageStart} onChange={event => setPageStart(Number(event.target.value))} /></label><label>À la page<input type="number" min={pageStart} max={pageCount ?? 1} value={pageEnd} onChange={event => setPageEnd(Number(event.target.value))} /></label></div>}
      {kind === "section" && (outline.isError ? <p role="alert" className="inline-error">{unavailable("Sommaire indisponible", outline.error)}</p> : outline.isLoading ? <p role="status" className="scope-help">Chargement du sommaire…</p> : <label>Section<select value={sectionId} onChange={event => setSectionId(event.target.value)}><option value="">{outline.data?.sections.length ? "Choisir une section…" : state.opened ? "Aucune section extraite pour ce document" : "Ouvrez un document pour choisir une section"}</option>{outline.data?.sections.map(section => <option value={section.id} key={section.id}>{section.title}</option>)}</select></label>)}
      {kind === "selection" && <p className="scope-help">{state.selection ? `« ${state.selection.text.slice(0, 100)} »` : "Aucun texte sélectionné ne correspond aux blocs extraits. Sélectionnez un passage dans le lecteur."}</p>}
      {failure && <p role="alert" className="inline-error">{failure}</p>}
      <div className="scope-popover-actions"><Button size="sm" variant="ghost" onClick={() => close(true)}>Fermer</Button><Button size="sm" disabled={(kind === "pages" || kind === "section") && !binding.actions.allowed} onClick={apply}>Appliquer</Button></div>
    </div>}
  </div>;
}
