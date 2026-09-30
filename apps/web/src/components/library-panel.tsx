"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, Crosshair, FileText, Folder as FolderIcon, FolderPlus, RefreshCw, Search, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { errorMessage } from "@/lib/utils";
import type { DocumentRecord, Folder, LibraryTree } from "@/lib/types";
import { Button } from "./ui/button";

export const documentStateLabels: Record<string, string> = { imported: "Importé", queued: "En attente", extracting: "Extraction", ocr: "OCR", indexing: "Indexation", ready: "Prêt", ready_partial: "Partiel", error: "Erreur", deleted: "Retiré", paused: "En pause", waiting_for_ingestion_checkpoint: "Mise en pause en cours" };
export function LibraryPanel() {
  const state = useWorkspace();
  const client = useQueryClient();
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), refetchInterval: 3000 });
  const [filter, setFilter] = useState("");
  const [closed, setClosed] = useState(new Set<string>());
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const openRequest = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const importMutation = useMutation({ mutationFn: (files: File[]) => api.import(files, setUploadProgress), onSuccess: () => { setNotice("Import reçu. Le suivi indique les étapes réellement exécutées."); setUploadProgress(null); void client.invalidateQueries({ queryKey: ["tree"] }); void client.invalidateQueries({ queryKey: ["jobs"] }); }, onError: failure => { setNotice(errorMessage(failure)); setUploadProgress(null); } });
  const openDocument = async (document: DocumentRecord) => {
    const requestId = ++openRequest.current;
    try {
      let version = document.active_version_id ?? document.version_id;
      if (!version) {
        const detail = await client.fetchQuery({ queryKey: ["document", document.id], queryFn: ({ signal }) => api.document(document.id, signal), staleTime: 0 });
        version = detail.versions[0]?.id;
      }
      if (requestId !== openRequest.current) return;
      if (version) { setNotice(""); state.open({ documentId: document.id, versionId: version, pageIndex: 0 }); }
      else setNotice("Ce document n'expose pas encore de version consultable.");
    } catch (failure) { if (requestId === openRequest.current) setNotice(errorMessage(failure)); }
  };
  const imported = (files: FileList | null) => {
    if (!files?.length) return;
    const pdfs = [...files].filter(file => file.name.toLocaleLowerCase().endsWith(".pdf"));
    if (!pdfs.length) { setNotice("Choisissez au moins un fichier PDF. Les autres formats ne sont pas importés ici."); return; }
    if (pdfs.length !== files.length) setNotice(`${files.length - pdfs.length} fichier(s) non PDF ignoré(s).`);
    else setNotice("");
    setUploadProgress(0); importMutation.mutate(pdfs);
  };
  const toggleFolder = (id: string) => setClosed(value => { const next = new Set(value); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const matches = (document: DocumentRecord) => !filter || document.relative_path.toLocaleLowerCase().includes(filter.toLocaleLowerCase()) || document.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase());
  const data: LibraryTree = tree.data ?? { folders: [], documents: [] };
  const folderHasMatch = (folderId: string, visited = new Set<string>()): boolean => {
    if (visited.has(folderId)) return false;
    visited.add(folderId);
    return data.documents.some(document => document.folder_id === folderId && matches(document)) || data.folders.some(folder => folder.parent_id === folderId && folderHasMatch(folder.id, visited));
  };
  const renderDocument = (document: DocumentRecord, depth: number) => <div className={`tree-document ${state.opened?.documentId === document.id ? "is-open" : ""}`} key={document.id} style={{ paddingLeft: depth * 14 + 10 }}>
    <input type="checkbox" aria-label={`Sélectionner ${document.name}`} checked={state.selectedIds.includes(document.id)} onChange={() => state.toggleDocument(document.id)} />
    <button onClick={() => void openDocument(document)} title={document.relative_path}><FileText size={16} /><span><strong>{document.name}</strong><small><i className={`document-dot ${document.state}`} />{documentStateLabels[document.state] ?? document.state}{typeof document.page_count === "number" && document.page_count > 0 && ` · ${document.page_count} p.`}{document.coverage && document.coverage.total > 0 && document.coverage.processed < document.coverage.total && ` · ${document.coverage.processed}/${document.coverage.total}`}</small></span></button>
  </div>;
  const renderFolder = (folder: Folder, depth: number, ancestors: string[] = []): React.ReactNode => {
    if (ancestors.includes(folder.id) || filter && !folderHasMatch(folder.id)) return null;
    const expanded = filter || !closed.has(folder.id);
    return <div key={folder.id}><div className="tree-folder" style={{ paddingLeft: depth * 14 + 10 }}><button onClick={() => toggleFolder(folder.id)} aria-expanded={Boolean(expanded)} title={folder.path}>{expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<FolderIcon size={15} /><span>{folder.name}</span></button><button className="folder-scope" title={`Définir le périmètre : ${folder.path} et sous-dossiers`} aria-label={`Analyser le dossier ${folder.name}`} onClick={() => state.setScope({ kind: "folder", folderId: folder.id, recursive: true }, `${folder.path} · sous-dossiers inclus`)}><Crosshair size={14} /></button></div>{expanded && <div>{data.folders.filter(child => child.parent_id === folder.id).map(child => renderFolder(child, depth + 1, [...ancestors, folder.id]))}{data.documents.filter(document => document.folder_id === folder.id && document.state !== "deleted" && matches(document)).map(document => renderDocument(document, depth + 1))}</div>}</div>;
  };
  const selectedDocuments = data.documents.filter(document => state.selectedIds.includes(document.id) && document.state !== "deleted");
  return <aside className="library-panel">
    <div className="panel-heading"><h2>Bibliothèque</h2><span className="count-pill">{data.total_documents ?? data.documents.length}</span></div>
    <div className="import-actions"><Button variant="secondary" size="sm" onClick={() => fileInput.current?.click()} disabled={importMutation.isPending}><Upload size={14} />PDF</Button><Button variant="secondary" size="sm" onClick={() => folderInput.current?.click()} disabled={importMutation.isPending}><FolderPlus size={14} />Dossier</Button><Button variant="ghost" size="icon" onClick={() => void tree.refetch()} aria-label="Actualiser la bibliothèque" disabled={tree.isFetching}><RefreshCw size={15} /></Button></div>
    <input ref={fileInput} type="file" accept="application/pdf,.pdf" multiple hidden onChange={event => { imported(event.target.files); event.target.value = ""; }} />
    <input ref={folderInput} type="file" multiple hidden {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)} onChange={event => { imported(event.target.files); event.target.value = ""; }} />
    {uploadProgress !== null && <div className="upload-progress" role="status"><span>Transfert des fichiers · {Math.round(uploadProgress * 100)} %</span><progress max={1} value={uploadProgress} /></div>}
    {notice && <p className="library-notice" role="status">{notice}</p>}
    <label className="library-filter"><Search size={14} /><input aria-label="Filtrer les fichiers" placeholder="Filtrer les fichiers…" value={filter} onChange={event => setFilter(event.target.value)} /></label>
    <button className={`library-all ${state.scope.kind === "library" ? "is-active" : ""}`} onClick={() => state.setScope({ kind: "library" }, "Toute la bibliothèque")}><FolderIcon size={16} /><span>Toute la bibliothèque</span>{state.scope.kind === "library" && <Check size={14} />}</button>
    <div className="tree" role="navigation" aria-label="Arborescence documentaire">
      {tree.isError ? <div className="empty-state" role="alert"><h3>Bibliothèque indisponible</h3><p>{errorMessage(tree.error)}</p><Button variant="secondary" size="sm" onClick={() => void tree.refetch()}>Réessayer</Button></div> : tree.isLoading ? <p className="loading-label">Chargement de la bibliothèque…</p> : !data.documents.length ? <div className="empty-state"><FolderIcon size={32} strokeWidth={1} /><h3>La bibliothèque est vide</h3><p>Importez un PDF ou un dossier. Les originaux sont conservés.</p></div> : <>{data.folders.filter(folder => !folder.parent_id || !data.folders.some(parent => parent.id === folder.parent_id)).map(folder => renderFolder(folder, 0))}{data.documents.filter(document => !document.folder_id && document.state !== "deleted" && matches(document)).map(document => renderDocument(document, 0))}</>}
    </div>
    <div className="library-selection"><span>{selectedDocuments.length} document(s) sélectionné(s)</span><Button size="sm" variant="secondary" disabled={!selectedDocuments.length} onClick={() => state.setScope({ kind: "documents", documentIds: selectedDocuments.map(document => document.id) }, selectedDocuments.length === 1 ? selectedDocuments[0].name : `${selectedDocuments.length} PDF sélectionnés`)}>Utiliser ce périmètre</Button></div>
  </aside>;
}
