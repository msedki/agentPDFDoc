"use client";
import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, CircleAlert, Crosshair, FileText, Folder as FolderIcon, FolderPlus, ListChecks, RefreshCw, Search, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { errorMessage } from "@/lib/utils";
import { documentRecordStatus } from "@/lib/status";
import { isServiceUnavailable, libraryView, selectedDocumentsSentence } from "@/lib/panel-state";
import type { DocumentRecord, Folder, LibraryTree } from "@/lib/types";
import { Button } from "./ui/button";
import { ActionButton } from "./ui/action-button";
import { PanelEmpty, PanelError, PanelHeader, PanelLoading } from "./ui/panel";
import { StatusIndicator } from "./ui/status-indicator";

function ignoredSentence(count: number) { return count === 1 ? "1 fichier non PDF ignoré" : `${count} fichiers non PDF ignorés`; }
function receivedSentence(count: number) { return count === 1 ? "1 PDF reçu par le service" : `${count} PDF reçus par le service`; }
function documentsLabel(documents: DocumentRecord[]) { return documents.length === 1 ? documents[0].name : `${documents.length} documents sélectionnés`; }

/** Actions de la bibliothèque déclenchées depuis le rail, alors que le panneau est replié. */
export type LibraryController = { importFiles: () => void; focusFilter: () => void; focusSelection: () => void };

/**
 * Rail de 64 px de la bibliothèque repliée : importer, filtrer et rejoindre la
 * sélection. Chaque action rouvre le panneau, où s'affichent transfert et résultats.
 */
export function LibraryRail({ selectedCount, onImport, onFilter, onSelection }: { selectedCount: number; onImport: () => void; onFilter: () => void; onSelection: () => void }) {
  const selection = `${selectedDocumentsSentence(selectedCount)} : afficher la bibliothèque pour définir le périmètre`;
  return <div className="library-rail" role="group" aria-label="Bibliothèque repliée">
    <Button variant="ghost" size="icon" onClick={onImport} aria-label="Importer des PDF" title="Importer des PDF : la bibliothèque se rouvre pour suivre le transfert"><Upload size={16} /></Button>
    <Button variant="ghost" size="icon" onClick={onFilter} aria-label="Filtrer la bibliothèque" title="Filtrer la bibliothèque par nom ou chemin de fichier"><Search size={16} /></Button>
    <Button variant="ghost" size="icon" className="rail-selection" onClick={onSelection} aria-label={selection} title={selection}><ListChecks size={16} /><span className="rail-count" aria-hidden="true">{selectedCount}</span></Button>
  </div>;
}

export function LibraryPanel({ controller, headerAction }: { controller?: RefObject<LibraryController | null>; headerAction?: ReactNode }) {
  const state = useWorkspace();
  const client = useQueryClient();
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), refetchInterval: 3000 });
  const filterInput = useRef<HTMLInputElement>(null);
  const selectionButton = useRef<HTMLButtonElement>(null);
  const [filter, setFilter] = useState("");
  const [closed, setClosed] = useState(new Set<string>());
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [openError, setOpenError] = useState("");
  const [importIssue, setImportIssue] = useState("");
  const [importOrigin, setImportOrigin] = useState<"files" | "folder">("files");
  const ignored = useRef(0);
  const openRequest = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const importMutation = useMutation({
    mutationFn: (files: File[]) => api.import(files, setUploadProgress),
    onSuccess: (_, files) => {
      setNotice(`${receivedSentence(files.length)}${ignored.current ? ` ; ${ignoredSentence(ignored.current)}` : ""}. ${files.length === 1 ? "Son extraction et son indexation s'affichent" : "Leur extraction et leur indexation s'affichent"} dans le Suivi.`);
      setUploadProgress(null);
      void client.invalidateQueries({ queryKey: ["tree"] }); void client.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: () => setUploadProgress(null),
  });
  const importFailure = importIssue || (importMutation.isError ? errorMessage(importMutation.error) : "");
  const openDocument = async (document: DocumentRecord) => {
    const requestId = ++openRequest.current;
    setOpenError("");
    try {
      let version = document.active_version_id ?? document.version_id;
      if (!version) {
        const detail = await client.fetchQuery({ queryKey: ["document", document.id], queryFn: ({ signal }) => api.document(document.id, signal), staleTime: 0 });
        version = detail.versions[0]?.id;
      }
      if (requestId !== openRequest.current) return;
      if (version) state.open({ documentId: document.id, versionId: version, pageIndex: 0 });
      else setOpenError(`« ${document.name} » n'a pas encore de version consultable : attendez la fin de son import dans le Suivi.`);
    } catch (failure) { if (requestId === openRequest.current) setOpenError(errorMessage(failure)); }
  };
  const imported = (files: FileList | null) => {
    if (!files?.length) return;
    importMutation.reset(); setImportIssue(""); setNotice("");
    const pdfs = [...files].filter(file => file.name.toLocaleLowerCase().endsWith(".pdf"));
    ignored.current = files.length - pdfs.length;
    if (!pdfs.length) { setImportIssue("Aucun fichier PDF dans cette sélection : seuls les PDF sont importés."); return; }
    setUploadProgress(0); importMutation.mutate(pdfs);
  };
  const chooseFiles = (origin: "files" | "folder") => { setImportOrigin(origin); (origin === "files" ? fileInput : folderInput).current?.click(); };
  useEffect(() => {
    if (!controller) return;
    controller.current = {
      importFiles: () => chooseFiles("files"),
      focusFilter: () => filterInput.current?.focus(),
      focusSelection: () => (selectionButton.current && !selectionButton.current.disabled ? selectionButton.current : filterInput.current)?.focus(),
    };
  });
  const toggleFolder = (id: string) => setClosed(value => { const next = new Set(value); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const matches = (document: DocumentRecord) => !filter || document.relative_path.toLocaleLowerCase().includes(filter.toLocaleLowerCase()) || document.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase());
  const data: LibraryTree = tree.data ?? { folders: [], documents: [] };
  const live = data.documents.filter(document => document.state !== "deleted");
  const view = libraryView({ hasData: tree.data !== undefined, failed: tree.isError, total: live.length, visible: live.filter(matches).length, filtering: filter !== "" });
  const folderHasMatch = (folderId: string, visited = new Set<string>()): boolean => {
    if (visited.has(folderId)) return false;
    visited.add(folderId);
    return data.documents.some(document => document.folder_id === folderId && matches(document)) || data.folders.some(folder => folder.parent_id === folderId && folderHasMatch(folder.id, visited));
  };
  const renderDocument = (document: DocumentRecord, depth: number) => <div className={`tree-document ${state.opened?.documentId === document.id ? "is-open" : ""}`} key={document.id} style={{ paddingLeft: depth * 16 + 12 }}>
    <input type="checkbox" aria-label={`Sélectionner ${document.name}`} checked={state.selectedIds.includes(document.id)} onChange={() => state.toggleDocument(document.id)} />
    <button onClick={() => void openDocument(document)} title={document.relative_path}><FileText size={16} /><span><strong>{document.name}</strong><small><StatusIndicator status={documentRecordStatus(document)} />{typeof document.page_count === "number" && document.page_count > 0 && <span className="tabular"> · {document.page_count} p.</span>}{document.coverage && document.coverage.total > 0 && document.coverage.processed < document.coverage.total && <span className="tabular"> · {document.coverage.processed}/{document.coverage.total} p. traitées</span>}</small></span></button>
  </div>;
  const renderFolder = (folder: Folder, depth: number, ancestors: string[] = []): React.ReactNode => {
    if (ancestors.includes(folder.id) || filter && !folderHasMatch(folder.id)) return null;
    const expanded = filter || !closed.has(folder.id);
    return <div key={folder.id}><div className="tree-folder" style={{ paddingLeft: depth * 16 + 12 }}><button onClick={() => toggleFolder(folder.id)} aria-expanded={Boolean(expanded)} title={folder.path}>{expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<FolderIcon size={16} /><span>{folder.name}</span></button><button className="folder-scope" title={`Périmètre : ${folder.path} et ses sous-dossiers`} aria-label={`Définir le périmètre sur le dossier ${folder.name}`} onClick={() => state.setScope({ kind: "folder", folderId: folder.id, recursive: true }, `${folder.path} · sous-dossiers inclus`)}><Crosshair size={14} /></button></div>{expanded && <div>{data.folders.filter(child => child.parent_id === folder.id).map(child => renderFolder(child, depth + 1, [...ancestors, folder.id]))}{data.documents.filter(document => document.folder_id === folder.id && document.state !== "deleted" && matches(document)).map(document => renderDocument(document, depth + 1))}</div>}</div>;
  };
  const selectedDocuments = live.filter(document => state.selectedIds.includes(document.id));
  return <aside className="library-panel" aria-labelledby="library-heading">
    <PanelHeader title="Bibliothèque" id="library-heading"><div className="panel-heading-actions">{tree.data && <span className="count-pill" title="Documents présents dans la bibliothèque"><span className="sr-only">Documents présents : </span>{data.total_documents ?? live.length}</span>}{headerAction}</div></PanelHeader>
    {tree.isError && <PanelError title={isServiceUnavailable(tree.error) ? "Service local indisponible" : "Lecture de la bibliothèque impossible"} message={view === "unavailable" ? errorMessage(tree.error) : `${errorMessage(tree.error)} La liste affichée date de la dernière lecture réussie.`} onRetry={() => void tree.refetch()} />}
    {view === "loading" && <PanelLoading label="Chargement de la bibliothèque…" />}
    <div className="import-actions">
      <ActionButton variant="secondary" size="sm" onAction={() => chooseFiles("files")} disabled={importMutation.isPending} pending={importMutation.isPending && importOrigin === "files"} pendingLabel="Import en cours…" error={importOrigin === "files" ? importFailure : ""}><Upload size={16} />Importer des PDF</ActionButton>
      <ActionButton variant="secondary" size="sm" onAction={() => chooseFiles("folder")} disabled={importMutation.isPending} pending={importMutation.isPending && importOrigin === "folder"} pendingLabel="Import en cours…" error={importOrigin === "folder" ? importFailure : ""}><FolderPlus size={16} />Importer un dossier</ActionButton>
      <Button variant="ghost" size="icon" onClick={() => void tree.refetch()} aria-label="Actualiser la bibliothèque" title="Actualiser la bibliothèque" disabled={tree.isFetching}><RefreshCw size={16} /></Button>
    </div>
    <input ref={fileInput} type="file" accept="application/pdf,.pdf" multiple hidden onChange={event => { imported(event.target.files); event.target.value = ""; }} />
    <input ref={folderInput} type="file" multiple hidden {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)} onChange={event => { imported(event.target.files); event.target.value = ""; }} />
    {uploadProgress !== null && <div className="upload-progress" role="status"><span>Transfert des fichiers · <span className="tabular">{Math.round(uploadProgress * 100)} %</span></span><progress max={1} value={uploadProgress} aria-label="Transfert des fichiers" /></div>}
    {notice && <p className="library-notice" role="status">{notice}</p>}
    {openError && <p className="library-notice action-error" role="alert"><CircleAlert size={14} aria-hidden="true" />{openError}</p>}
    <label className="library-filter"><Search size={14} aria-hidden="true" /><input ref={filterInput} aria-label="Filtrer les fichiers" placeholder="Nom ou chemin de fichier…" value={filter} onChange={event => setFilter(event.target.value)} /></label>
    <button className={`library-all ${state.scope.kind === "library" ? "is-active" : ""}`} title="Définir le périmètre sur toute la bibliothèque" aria-pressed={state.scope.kind === "library"} onClick={() => state.setScope({ kind: "library" }, "Toute la bibliothèque")}><FolderIcon size={16} /><span>Toute la bibliothèque</span>{state.scope.kind === "library" && <Check size={14} aria-hidden="true" />}</button>
    <div className="tree" role="navigation" aria-label="Arborescence documentaire">
      {view === "no-documents" ? <PanelEmpty reason="no-documents" title="Aucun document dans la bibliothèque" description="Importez des fichiers avec « Importer des PDF » ou tout un dossier avec « Importer un dossier ». Les fichiers originaux sont conservés tels quels." />
        : view === "no-match" ? <PanelEmpty reason="no-match" title={`Aucun fichier ne correspond à « ${filter} »`} description="Le filtre porte sur le nom et le chemin relatif des fichiers." action={<Button variant="secondary" size="sm" onClick={() => setFilter("")}>Effacer le filtre</Button>} />
        : view === "content" ? <>{data.folders.filter(folder => !folder.parent_id || !data.folders.some(parent => parent.id === folder.parent_id)).map(folder => renderFolder(folder, 0))}{data.documents.filter(document => !document.folder_id && document.state !== "deleted" && matches(document)).map(document => renderDocument(document, 0))}</> : null}
    </div>
    <div className="library-selection"><span>{selectedDocumentsSentence(selectedDocuments.length)}</span><Button ref={selectionButton} size="sm" variant="secondary" disabled={!selectedDocuments.length} title={selectedDocuments.length ? undefined : "Cochez au moins un document pour en faire le périmètre."} onClick={() => state.setScope({ kind: "documents", documentIds: selectedDocuments.map(document => document.id) }, documentsLabel(selectedDocuments))}>Utiliser ce périmètre</Button></div>
  </aside>;
}
