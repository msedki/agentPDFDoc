"use client";
import { useId, useRef, useState } from "react";
import { CircleAlert, Info, X } from "lucide-react";
import type { Generation, LibraryTree, Scope } from "@/lib/types";
import { coverageSentence, scopeCoverage, scopeKindLabel } from "@/lib/panel-state";
import { generationView, type GenerationView } from "@/lib/generation";
import { readinessSentence } from "@/lib/warnings";
import { useDismiss } from "@/lib/use-dismiss";
import { useLauncherCommands } from "@/lib/use-launcher-commands";
import { cn } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { StatusIndicator } from "./ui/status-indicator";
import type { ServiceSummary } from "./app-topbar";

/**
 * Bandeau sous la barre supérieure : nature du périmètre, documents
 * interrogeables et exclus par motif (d'après l'arborescence déjà lue), puis
 * un seul emplacement de message et, à droite, le matériel de la génération
 * des réponses (W025). Une erreur de l'espace de travail passe avant l'avis de
 * préparation des services, lui-même avant l'avis de repli du GPU sur le
 * processeur. Sous 768 px, l'état des services quitte la barre supérieure et
 * s'affiche ici. Rien n'est rendu sans contenu.
 */
export function ContextBand({ scope, tree, treeFailed, blockers, error, onDismissError, service, generation }: {
  scope: Scope; tree: LibraryTree | undefined;
  /** Arborescence illisible et jamais reçue : la couverture du périmètre est inconnue. */
  treeFailed: boolean;
  blockers: string[]; error: string; onDismissError: () => void; service: ServiceSummary;
  /** Matériel de la génération lu sur `/jobs` ; null si le champ manque, est mal formé ou si la dernière lecture a échoué. */
  generation: Generation | null;
}) {
  const commands = useLauncherCommands();
  const coverage = tree ? scopeCoverage(scope, tree) : null;
  const computing = generationView(generation, commands);
  const notice = computing?.notice ?? null;
  const message = error ? "error" : blockers.length ? "readiness" : notice ? "generation" : null;
  const scoped = Boolean(coverage) || treeFailed;
  return <div className={cn("context-band", !scoped && !message && "context-band-service-only")}>
    <StatusIndicator className="context-service" status={service.status} title={service.detail} />
    {/* La nature du périmètre ne s'affiche que si elle précise le libellé de la barre supérieure (pas pour toute la bibliothèque). */}
    {scoped && <p className="context-scope">{scope.kind !== "library" && <Badge tone="neutral">{scopeKindLabel(scope.kind)}</Badge>}<span>{coverage ? coverageSentence(coverage) : "Couverture inconnue : la bibliothèque n'a pas pu être lue"}</span></p>}
    {message === "error" && <div className="context-message workspace-error" role="alert"><CircleAlert size={14} aria-hidden="true" /><span>{error}</span><button type="button" onClick={onDismissError} aria-label="Fermer le message"><X size={16} /></button></div>}
    {message === "readiness" && <p className="context-message readiness-notice" role="status" title={`Contrôles non satisfaits : ${blockers.join(", ")}`}>{readinessSentence(blockers, commands)}</p>}
    {message === "generation" && <p className="context-message generation-notice" role="status">{notice}</p>}
    {computing && <GenerationIndicator view={computing} />}
  </div>;
}

/**
 * Matériel de la génération : le libellé est une région de statut polie, qui annonce un passage en repli
 * ou une nouvelle occupation du modèle sans déplacer le focus. L'explication, avec la commande doctor,
 * s'ouvre par un bouton, au clavier comme au toucher, y compris quand l'emplacement de message est occupé.
 */
function GenerationIndicator({ view }: { view: GenerationView }) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const detailId = useId();
  useDismiss(open, container, reason => { setOpen(false); if (reason === "escape") trigger.current?.focus(); });
  return <div className="context-generation" ref={container}>
    <span role="status"><StatusIndicator status={view.status} /></span>
    <Button ref={trigger} type="button" variant="ghost" size="icon" className="generation-help" aria-expanded={open} aria-controls={open ? detailId : undefined}
      aria-label="Explication du matériel de génération" title="Explication du matériel de génération" onClick={() => setOpen(value => !value)}><Info size={16} aria-hidden="true" /></Button>
    {open && <p className="generation-help-text" id={detailId}>{view.detail}</p>}
  </div>;
}
