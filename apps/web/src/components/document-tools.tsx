"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import { errorMessage } from "@/lib/utils";
import type { DocumentDetail } from "@/lib/types";
import { Button } from "./ui/button";

export function DocumentTools({ document }: { document: DocumentDetail }) {
  const state = useWorkspace();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const operate = async (operation: "reindex" | "remove") => {
    if (operation === "remove" && !window.confirm(`Retirer « ${document.name} » de la bibliothèque ? Il ne sera plus utilisé pour les nouvelles recherches.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (operation === "reindex") {
        await api.reindex(document.id);
        setNotice("Réindexation demandée. Le suivi affiche sa progression.");
      } else {
        await api.remove(document.id);
        const current = useWorkspace.getState();
        if (current.opened?.documentId === document.id) current.close();
        if (current.selectedIds.includes(document.id)) current.toggleDocument(document.id);
      }
      await Promise.all([client.invalidateQueries({ queryKey: ["tree"] }), client.invalidateQueries({ queryKey: ["jobs"] }), client.invalidateQueries({ queryKey: ["document", document.id] })]);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  };
  return <details className="document-tools">
    <summary aria-label="Actions et versions du document" title="Actions et versions du document">⋯</summary>
    <div className="document-tools-menu">
      <label>Version affichée<select aria-label="Version affichée" value={state.opened?.versionId ?? ""} disabled={busy} onChange={event => {
        const version = document.versions.find(item => item.id === event.target.value);
        if (version) state.open({ documentId: document.id, versionId: version.id, pageIndex: typeof version.page_count === "number" ? Math.max(0, Math.min(state.opened?.pageIndex ?? 0, version.page_count - 1)) : state.opened?.pageIndex ?? 0 });
      }}>{document.versions.map(version => <option key={version.id} value={version.id}>{version.id.slice(0, 8)} · {typeof version.page_count === "number" ? `${version.page_count} p.` : "pages en attente"}{version.id === (document.active_version_id ?? document.version_id) ? " · active" : ""}</option>)}</select></label>
      <p className="document-tools-hash" title={document.versions.find(version => version.id === state.opened?.versionId)?.sha256}>SHA-256 {document.versions.find(version => version.id === state.opened?.versionId)?.sha256?.slice(0, 16) ?? "indisponible"}</p>
      <Button variant="secondary" size="sm" disabled={busy || !["ready", "ready_partial", "error"].includes(document.state)} onClick={() => void operate("reindex")}>Réindexer ce document</Button>
      <Button variant="danger" size="sm" disabled={busy || document.state === "deleted"} onClick={() => void operate("remove")}>Retirer de la bibliothèque</Button>
      {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="inline-warning">{error}</p>}
    </div>
  </details>;
}
