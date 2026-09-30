"use client";
import { useState } from "react";
import { useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/utils";
import { warningText } from "@/lib/warnings";
import { isActiveJobState, jobStageLabel, jobStatus } from "@/lib/status";
import { isServiceUnavailable } from "@/lib/panel-state";
import type { JobsResponse, LibraryTree } from "@/lib/types";
import { Button } from "./ui/button";
import { ActionButton } from "./ui/action-button";
import { PanelEmpty, PanelError, PanelHeader, PanelLoading } from "./ui/panel";
import { StatusIndicator } from "./ui/status-indicator";

function pagesSentence(count: number, what: string) { return `${count} ${count === 1 ? "page" : "pages"} ${what}`; }

/**
 * Contenu du panneau « Suivi des traitements » : priorité questions/imports,
 * puis chaque traitement avec son état, son étape, sa couverture et ses actions.
 * Les requêtes sont possédées par l'espace de travail ; ce composant les affiche.
 */
export function JobsPanel({ jobs, tree, onClose }: { jobs: UseQueryResult<JobsResponse>; tree: UseQueryResult<LibraryTree>; onClose: () => void }) {
  const client = useQueryClient();
  const [pendingJob, setPendingJob] = useState<string | null>(null);
  const [modeNotice, setModeNotice] = useState("");
  // L'échec remonte à l'ActionButton appelant, qui l'affiche sous l'action concernée.
  const jobAction = async (id: string, action: () => Promise<unknown>, notice?: string) => {
    setPendingJob(id);
    try {
      await action();
      if (notice) setModeNotice(notice);
      await Promise.all([client.invalidateQueries({ queryKey: ["jobs"] }), client.invalidateQueries({ queryKey: ["tree"] }), client.invalidateQueries({ queryKey: ["readiness"] })]);
    } finally { setPendingJob(null); }
  };
  return <section className="jobs-panel" aria-labelledby="jobs-heading">
    <PanelHeader title="Suivi des traitements" id="jobs-heading"><Button variant="ghost" size="sm" onClick={onClose} aria-label="Fermer le suivi"><X size={16} aria-hidden="true" />Fermer</Button></PanelHeader>
    {jobs.isError && <PanelError title={isServiceUnavailable(jobs.error) ? "Service local indisponible" : "Lecture du suivi impossible"} message={jobs.data ? `${errorMessage(jobs.error)} La liste affichée date de la dernière lecture réussie.` : errorMessage(jobs.error)} onRetry={() => void jobs.refetch()} />}
    <div className="job-mode-actions">
      <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Changement de priorité…" onAction={() => jobAction("runtime-mode", () => api.runtimeMode("interactive"), "Priorité aux questions demandée : les indexations en cours s'arrêtent à leur prochain point de reprise. Relancez-les ensuite avec « Reprendre l'indexation ».")}>Priorité aux questions</ActionButton>
      <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Changement de priorité…" onAction={() => jobAction("runtime-mode", () => api.runtimeMode("ingestion"), "Priorité aux imports rétablie. Les indexations mises en pause restent à relancer une par une avec « Reprendre l'indexation ».")}>Priorité aux imports</ActionButton>
    </div>
    {modeNotice && <p role="status" className="library-notice">{modeNotice}</p>}
    {!jobs.data ? jobs.isLoading && <PanelLoading label="Chargement des traitements…" /> : !jobs.data.jobs.length ? <PanelEmpty reason="not-started" title="Aucun traitement enregistré" description="Les imports et les réindexations apparaissent ici avec leur étape, leur couverture et leurs limites." /> : jobs.data.jobs.map(job => {
      const document = tree.data?.documents.find(item => item.id === job.document_id);
      const jobState = job.state ?? job.status ?? "";
      const status = jobStatus(jobState);
      const stage = jobStageLabel(job.stage, jobState);
      const published = job.published ?? Boolean(job.published_at || job.generation_id && document?.active_generation_id === job.generation_id);
      const coverage = job.coverage ?? document?.coverage;
      const name = document?.name ?? (tree.data ? "Document absent de la bibliothèque" : tree.isError ? "Document non identifié : la bibliothèque n'a pas pu être lue" : "Identification du document…");
      return <article key={job.id}>
        <div className="job-heading"><strong>{name}</strong><span><StatusIndicator status={status} active={isActiveJobState(jobState) && status.tone === "info"} />{stage ? ` · ${stage}` : ""}</span></div>
        {typeof job.progress === "number" && <progress max={job.progress > 1 ? 100 : 1} value={job.progress} aria-label={`Avancement du traitement de ${name}`} />}
        {coverage && typeof coverage.processed === "number" && typeof coverage.total === "number" && <p className="tabular">{coverage.processed}/{coverage.total} pages traitées{typeof coverage.ocr === "number" && coverage.ocr > 0 ? ` · ${pagesSentence(coverage.ocr, "lues par OCR")}` : ""}</p>}
        {(job.error || job.error_message) && <p className="inline-error">{job.error ?? job.error_message}</p>}
        {job.warnings?.map((warning, index) => <p key={index} className="inline-warning">{warningText(warning)}</p>)}
        {jobState === "ready_partial" && <p className="inline-warning">{published ? "Extraction partielle publiée : les réponses restent limitées aux pages traitées." : "Extraction partielle vérifiée, non publiée. Les pages manquantes ne seront pas recherchées ; publiez-la pour interroger les pages traitées."}</p>}
        <div className="job-actions">
          {jobState === "ready_partial" && !published && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Publication…" onAction={() => jobAction(job.id, () => api.publishPartial(job.id))}>Utiliser cette extraction partielle</ActionButton>}
          {["queued", "running", "extracting", "ocr", "indexing"].includes(jobState) && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Mise en pause…" onAction={() => jobAction(job.id, () => api.pauseJob(job.id))}>Mettre en pause</ActionButton>}
          {["paused", "checkpointed", "interrupted"].includes(jobState) && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Reprise…" onAction={() => jobAction(job.id, () => api.resumeJob(job.id))}>Reprendre l'indexation</ActionButton>}
          {!["done", "completed", "ready", "ready_partial", "cancelled", "error", "failed"].includes(jobState) && <ActionButton variant="danger" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Annulation…" onAction={() => jobAction(job.id, () => api.cancelJob(job.id))}>Annuler ce traitement</ActionButton>}
        </div>
      </article>;
    })}
  </section>;
}
