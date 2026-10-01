"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Ellipsis, Play, RefreshCw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { reindexOutcome } from "@/lib/reindex";
import { useWorkspace } from "@/lib/store";
import type { DocumentDetail } from "@/lib/types";
import { Button } from "./ui/button";
import { ActionButton } from "./ui/action-button";
import { useErrorText, type Failure } from "./ui/error-text";
import { ConfirmDialog } from "./ui/confirm-dialog";

const reindexableStates = ["ready", "ready_partial", "error"];

export function DocumentTools({ document }: { document: DocumentDetail }) {
  const state = useWorkspace();
  const client = useQueryClient();
  const [notice, setNotice] = useState("");
  // Traitement suspendu renvoyé par la réindexation (`resume_required`), à reprendre au lieu d'en lancer un second.
  const [resumeJob, setResumeJob] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);
  // Échec du retrait gardé tel quel : son texte se calcule au rendu, dans le dialogue.
  const [removeError, setRemoveError] = useState<Failure | null>(null);
  const errorText = useErrorText();
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: ["tree"] }), client.invalidateQueries({ queryKey: ["jobs"] }), client.invalidateQueries({ queryKey: ["document", document.id] })]);
  const reindex = async () => {
    setNotice(""); setResumeJob(null);
    const outcome = reindexOutcome(await api.reindex(document.id));
    setNotice(outcome.message);
    if (outcome.kind === "resume") setResumeJob(outcome.jobId);
    await refresh();
  };
  const resume = async () => {
    if (!resumeJob) return;
    await api.resumeJob(resumeJob);
    setResumeJob(null);
    setNotice("Reprise demandée : sa progression s'affiche dans le Suivi.");
    await refresh();
  };
  const remove = async () => {
    setRemoving(true); setRemoveError(null);
    try {
      await api.remove(document.id);
      const current = useWorkspace.getState();
      if (current.opened?.documentId === document.id) current.close();
      if (current.selectedIds.includes(document.id)) current.toggleDocument(document.id);
      setConfirming(false);
      await refresh();
    } catch (failure) {
      setRemoveError({ error: failure });
      // Le navigateur a pu fermer le dialogue pendant le retrait : il revient pour montrer l'échec.
      setConfirming(true);
    }
    finally { setRemoving(false); }
  };
  const shown = document.versions.find(version => version.id === state.opened?.versionId);
  const reindexable = reindexableStates.includes(document.state);
  return <>
    <details className="document-tools">
      <summary aria-label="Actions et versions du document" title="Actions et versions du document"><Ellipsis size={16} aria-hidden="true" /></summary>
      <div className="document-tools-menu">
        <label>Version affichée<select aria-label="Version affichée" value={state.opened?.versionId ?? ""} disabled={removing} onChange={event => {
          const version = document.versions.find(item => item.id === event.target.value);
          if (version) state.open({ documentId: document.id, versionId: version.id, pageIndex: typeof version.page_count === "number" ? Math.max(0, Math.min(state.opened?.pageIndex ?? 0, version.page_count - 1)) : state.opened?.pageIndex ?? 0 });
        }}>{document.versions.map(version => <option key={version.id} value={version.id}>{version.id.slice(0, 8)} · {typeof version.page_count === "number" ? `${version.page_count} p.` : "nombre de pages inconnu"}{version.id === (document.active_version_id ?? document.version_id) ? " · version active" : ""}</option>)}</select></label>
        <p className="document-tools-hash" title={shown?.sha256}>Empreinte SHA-256 <span className="mono">{shown?.sha256?.slice(0, 16) ?? "non communiquée"}</span></p>
        <ActionButton variant="secondary" size="sm" disabled={removing || !reindexable} title={reindexable ? undefined : "Réindexation possible une fois le traitement en cours terminé."} onAction={reindex} pendingLabel="Demande de réindexation…"><RefreshCw size={16} />Réindexer ce document</ActionButton>
        <Button variant="danger" size="sm" disabled={removing || document.state === "deleted"} onClick={() => { setRemoveError(null); setConfirming(true); }}><Trash2 size={16} />Retirer de la bibliothèque</Button>
        {notice && <p role="status">{notice}</p>}
        {resumeJob && <ActionButton variant="secondary" size="sm" disabled={removing} onAction={resume} pendingLabel="Reprise…"><Play size={16} />Reprendre le traitement</ActionButton>}
      </div>
    </details>
    <ConfirmDialog open={confirming} title="Retirer ce document de la bibliothèque ?"
      message={`« ${document.name} » ne sera plus proposé dans la bibliothèque ni utilisé par les recherches et les questions : ses traitements en cours sont annulés et le retrait de ses passages de l'index est programmé. Le fichier original et ses versions restent enregistrés sur le poste.`}
      confirmLabel="Retirer le document" pendingLabel="Retrait en cours…" pending={removing} error={removeError ? errorText(removeError.error) : undefined}
      onConfirm={() => void remove()} onCancel={() => setConfirming(false)} />
  </>;
}
