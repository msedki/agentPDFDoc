"use client";
import { useState } from "react";
import { useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { groupedWarningTexts } from "@/lib/warnings";
import { isActiveJobState, jobStageLabel, jobStatus } from "@/lib/status";
import { isServiceUnavailable } from "@/lib/panel-state";
import { jobGroup, jobsSummary, latestJobIds, partialExtractionNotice, resumePausedNotice, showsProgress, sortJobsForAttention } from "@/lib/jobs-view";
import type { Job, JobsResponse, LibraryTree } from "@/lib/types";
import { Button } from "./ui/button";
import { ActionButton } from "./ui/action-button";
import { useErrorText } from "./ui/error-text";
import { PanelEmpty, PanelError, PanelHeader, PanelLoading } from "./ui/panel";
import { StatusIndicator } from "./ui/status-indicator";

function ocrPagesSentence(count: number) { return count === 1 ? "1 page lue par OCR" : `${count} pages lues par OCR`; }

/**
 * Contenu du panneau « Suivi des traitements » : priorité questions/imports,
 * puis chaque traitement avec son état, son étape, sa couverture et ses actions.
 * Les requêtes sont possédées par l'espace de travail ; ce composant les affiche.
 */
export function JobsPanel({ jobs, tree, onClose }: { jobs: UseQueryResult<JobsResponse>; tree: UseQueryResult<LibraryTree>; onClose: () => void }) {
  const client = useQueryClient();
  const [pendingJob, setPendingJob] = useState<string | null>(null);
  const [modeNotice, setModeNotice] = useState("");
  const errorText = useErrorText();
  // L'échec remonte à l'ActionButton appelant, qui l'affiche sous l'action concernée.
  const jobAction = async (id: string, action: () => Promise<unknown>, notice?: string) => {
    setPendingJob(id);
    try {
      await action();
      if (notice) setModeNotice(notice);
      await Promise.all([client.invalidateQueries({ queryKey: ["jobs"] }), client.invalidateQueries({ queryKey: ["tree"] }), client.invalidateQueries({ queryKey: ["readiness"] })]);
    } finally { setPendingJob(null); }
  };
  const isPublished = (job: Job) => job.published ?? Boolean(job.published_at || job.generation_id && tree.data?.documents.find(item => item.id === job.document_id)?.active_generation_id === job.generation_id);
  const ordered = jobs.data ? sortJobsForAttention(jobs.data.jobs, isPublished) : [];
  const latest = latestJobIds(ordered);
  const groups = ordered.map(job => jobGroup(job, isPublished(job), !latest.has(job.id)));
  const summary = groups.length ? jobsSummary(groups) : "";
  const pausedCount = groups.filter(group => group === "paused").length;
  const mode = jobs.data?.runtime_mode ?? null;
  return <section className="jobs-panel" aria-labelledby="jobs-heading">
    <PanelHeader title="Suivi des traitements" id="jobs-heading"><Button variant="ghost" size="sm" onClick={onClose} aria-label="Fermer le suivi"><X size={16} aria-hidden="true" />Fermer</Button></PanelHeader>
    {jobs.isError && <PanelError title={isServiceUnavailable(jobs.error) ? "Service local indisponible" : "Lecture du suivi impossible"} message={jobs.data ? `${errorText(jobs.error)} La liste affichée date de la dernière lecture réussie.` : errorText(jobs.error)} onRetry={() => void jobs.refetch()} />}
    {/* Mode courant du gouverneur : l'option active est marquée (aria-pressed) au lieu de deux boutons indistincts. */}
    <div className="job-mode-actions" role="group" aria-label="Priorité du poste">
      <ActionButton variant={mode === "interactive" ? "default" : "secondary"} size="sm" aria-pressed={mode === "interactive"} disabled={Boolean(pendingJob)} pendingLabel="Changement de priorité…" onAction={() => jobAction("runtime-mode", () => api.runtimeMode("interactive"), "Priorité aux questions : les indexations en cours s'arrêtent à leur prochain point de reprise et restent en pause jusqu'à leur reprise.")}>Priorité aux questions</ActionButton>
      <ActionButton variant={mode === "ingestion" ? "default" : "secondary"} size="sm" aria-pressed={mode === "ingestion"} disabled={Boolean(pendingJob)} pendingLabel="Changement de priorité…" onAction={() => jobAction("runtime-mode", () => api.runtimeMode("ingestion"), "Priorité aux imports : les nouveaux traitements démarrent ; ceux qui sont en pause se relancent avec « Reprendre les indexations en pause ».")}>Priorité aux imports</ActionButton>
    </div>
    {summary && <p className="jobs-summary" aria-live="polite">{summary}</p>}
    {pausedCount > 0 && <div className="job-bulk-actions">
      <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Reprise…" onAction={() => jobAction("resume-paused", async () => {
        const response = await api.resumePaused();
        setModeNotice(resumePausedNotice(response.resumed));
      })}>{pausedCount === 1 ? "Reprendre l'indexation en pause" : `Reprendre les ${pausedCount} indexations en pause`}</ActionButton>
    </div>}
    {modeNotice && <p role="status" className="library-notice">{modeNotice}</p>}
    {!jobs.data ? jobs.isLoading && <PanelLoading label="Chargement des traitements…" /> : !jobs.data.jobs.length ? <PanelEmpty reason="not-started" title="Aucun traitement enregistré" description="Les imports et les réindexations apparaissent ici avec leur étape, leur couverture et leurs limites." /> : ordered.map(job => {
      const document = tree.data?.documents.find(item => item.id === job.document_id);
      const jobState = job.state ?? job.status ?? "";
      const status = jobStatus(jobState);
      const published = isPublished(job);
      const superseded = !latest.has(job.id);
      // « complete » désigne la fin du calcul ; un partiel non publié attend encore une décision.
      const stage = superseded ? "remplacé par un traitement plus récent" : jobState === "ready_partial" && !published ? "terminée, publication à décider" : jobStageLabel(job.stage, jobState);
      const coverage = job.coverage ?? document?.coverage;
      const name = document?.name ?? (tree.data ? "Document absent de la bibliothèque" : tree.isError ? "Document non identifié : la bibliothèque n'a pas pu être lue" : "Identification du document…");
      return <article key={job.id}>
        <div className="job-heading"><strong>{name}</strong><span><StatusIndicator status={status} active={isActiveJobState(jobState) && status.tone === "info"} />{stage ? ` · ${stage}` : ""}</span></div>
        {showsProgress(job) && <progress max={(job.progress ?? 0) > 1 ? 100 : 1} value={job.progress} aria-label={`Avancement du traitement de ${name}`} />}
        {coverage && typeof coverage.processed === "number" && typeof coverage.total === "number" && <p className="tabular">{coverage.processed}/{coverage.total} pages traitées{typeof coverage.ocr === "number" && coverage.ocr > 0 ? ` · ${ocrPagesSentence(coverage.ocr)}` : ""}</p>}
        {(job.error || job.error_message) && <p className="inline-error">{job.error ?? job.error_message}</p>}
        {groupedWarningTexts(job.warnings).map(text => <p key={text} className="inline-warning">{text}</p>)}
        {jobState === "ready_partial" && !superseded && <p className="inline-warning">{partialExtractionNotice(published)}</p>}
        <div className="job-actions">
          {jobState === "ready_partial" && !published && !superseded && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Publication…" onAction={() => jobAction(job.id, () => api.publishPartial(job.id))}>Utiliser cette extraction partielle</ActionButton>}
          {["queued", "running", "extracting", "ocr", "indexing"].includes(jobState) && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Mise en pause…" onAction={() => jobAction(job.id, () => api.pauseJob(job.id))}>Mettre en pause</ActionButton>}
          {["paused", "checkpointed", "interrupted"].includes(jobState) && <ActionButton variant="secondary" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Reprise…" onAction={() => jobAction(job.id, () => api.resumeJob(job.id))}>Reprendre l'indexation</ActionButton>}
          {!["done", "completed", "ready", "ready_partial", "cancelled", "error", "failed"].includes(jobState) && <ActionButton variant="danger" size="sm" disabled={Boolean(pendingJob)} pendingLabel="Annulation…" onAction={() => jobAction(job.id, () => api.cancelJob(job.id))}>Annuler ce traitement</ActionButton>}
        </div>
      </article>;
    })}
  </section>;
}
