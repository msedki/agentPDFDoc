import type { ReactNode } from "react";
import { CircleAlert, FileSearch, FolderOpen, LoaderCircle, SearchX } from "lucide-react";
import { Button } from "./button";

/** En-tête de panneau (56 px) : titre h2 à gauche, compteur ou actions à droite. */
export function PanelHeader({ title, id, children }: { title: ReactNode; id?: string; children?: ReactNode }) {
  return <div className="panel-heading"><h2 id={id}>{title}</h2>{children}</div>;
}

/** Chargement signalé sous l'en-tête ; le contenu déjà affiché reste en place. */
export function PanelLoading({ label }: { label: string }) {
  return <p className="panel-message" role="status"><LoaderCircle size={14} className="panel-spinner" aria-hidden="true" />{label}</p>;
}

/**
 * Échec signalé sous l'en-tête, sans effacer le contenu déjà reçu. Le titre par
 * défaut désigne une panne du service local ; un refus métier passe son propre titre.
 */
export function PanelError({ title = "Service local indisponible", message, onRetry, retryLabel = "Réessayer", action }: {
  title?: string; message: string; onRetry?: () => void; retryLabel?: string; action?: ReactNode;
}) {
  return <div className="panel-message panel-message-error" role="alert">
    <CircleAlert size={14} aria-hidden="true" />
    <div><strong>{title}</strong><span>{message}</span></div>
    {onRetry && <Button type="button" variant="secondary" size="sm" onClick={onRetry}>{retryLabel}</Button>}
    {action}
  </div>;
}

/**
 * Motifs d'un panneau vide. Une panne n'en fait pas partie : elle passe par PanelError.
 * « not-started » couvre les zones qui attendent une action (aucun document ouvert,
 * aucune question posée).
 */
export type PanelEmptyReason = "no-documents" | "no-match" | "index-incomplete" | "not-started";
const reasonIcons: Record<PanelEmptyReason, ReactNode> = {
  "no-documents": <FolderOpen size={32} strokeWidth={1.5} aria-hidden="true" />,
  "no-match": <SearchX size={32} strokeWidth={1.5} aria-hidden="true" />,
  "index-incomplete": <FileSearch size={32} strokeWidth={1.5} aria-hidden="true" />,
  "not-started": null,
};

export function PanelEmpty({ reason, title, description, icon, action }: { reason: PanelEmptyReason; title: string; description: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return <div className="panel-empty" data-reason={reason}>
    {icon ?? reasonIcons[reason]}
    <h3>{title}</h3>
    <p>{description}</p>
    {action}
  </div>;
}
