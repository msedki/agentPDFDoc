"use client";
import { CircleAlert, X } from "lucide-react";
import type { LibraryTree, Scope } from "@/lib/types";
import { coverageSentence, scopeCoverage, scopeKindLabel } from "@/lib/panel-state";
import { readinessSentence } from "@/lib/warnings";
import { cn } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { StatusIndicator } from "./ui/status-indicator";
import type { ServiceSummary } from "./app-topbar";

/**
 * Bandeau sous la barre supérieure : nature du périmètre, documents
 * interrogeables et exclus par motif (d'après l'arborescence déjà lue), puis
 * un seul emplacement de message. Une erreur de l'espace de travail y passe
 * avant l'avis de préparation des services. Sous 768 px, l'état des services
 * quitte la barre supérieure et s'affiche ici. Rien n'est rendu sans contenu.
 */
export function ContextBand({ scope, tree, treeFailed, blockers, error, onDismissError, service }: {
  scope: Scope; tree: LibraryTree | undefined;
  /** Arborescence illisible et jamais reçue : la couverture du périmètre est inconnue. */
  treeFailed: boolean;
  blockers: string[]; error: string; onDismissError: () => void; service: ServiceSummary;
}) {
  const coverage = tree ? scopeCoverage(scope, tree) : null;
  const message = error ? "error" : blockers.length ? "readiness" : null;
  const scoped = Boolean(coverage) || treeFailed;
  return <div className={cn("context-band", !scoped && !message && "context-band-service-only")}>
    <StatusIndicator className="context-service" status={service.status} title={service.detail} />
    {scoped && <p className="context-scope"><Badge tone="neutral">{scopeKindLabel(scope.kind)}</Badge><span>{coverage ? coverageSentence(coverage) : "Couverture inconnue : la bibliothèque n'a pas pu être lue"}</span></p>}
    {message === "error" && <div className="context-message workspace-error" role="alert"><CircleAlert size={14} aria-hidden="true" /><span>{error}</span><button type="button" onClick={onDismissError} aria-label="Fermer le message"><X size={16} /></button></div>}
    {message === "readiness" && <p className="context-message readiness-notice" role="status" title={`Contrôles non satisfaits : ${blockers.join(", ")}`}>{readinessSentence(blockers)}</p>}
  </div>;
}
