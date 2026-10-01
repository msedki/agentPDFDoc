"use client";
import { useId, useState, type ComponentProps, type ReactNode } from "react";
import { CircleAlert } from "lucide-react";
import { Button } from "./button";
import { useErrorText, type Failure } from "./error-text";

type ActionButtonProps = Omit<ComponentProps<typeof Button>, "onClick" | "children" | "asChild"> & {
  /** Action exécutée au clic ; son échec s'affiche sous le bouton. */
  onAction: () => unknown;
  children: ReactNode;
  /** Libellé affiché pendant l'exécution, qui dit ce qui est en cours. */
  pendingLabel: string;
  /** Exécution suivie ailleurs (mutation TanStack Query, import en cours). */
  pending?: boolean;
  /** Échec rapporté ailleurs mais rattaché à cette action. */
  error?: string;
};

/**
 * Bouton d'action asynchrone : libellé d'attente pendant l'exécution, erreur
 * `role="alert"` rendue juste après le bouton et reliée par aria-describedby.
 * Ni toast ni boîte d'alerte du navigateur : le message reste à l'endroit de l'action.
 * L'échec est gardé tel quel et son texte calculé au rendu (`useErrorText`) : le message
 * du service s'affiche inchangé (409 `job_pausing` d'une réindexation, par exemple).
 */
export function ActionButton({ onAction, children, pendingLabel, pending = false, error, disabled, ...props }: ActionButtonProps) {
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const errorText = useErrorText();
  const errorId = useId();
  const busy = running || pending;
  const message = (failure ? errorText(failure.error) : "") || error || "";
  const run = async () => {
    setRunning(true); setFailure(null);
    try { await onAction(); } catch (caught) { setFailure({ error: caught }); } finally { setRunning(false); }
  };
  return <>
    <Button {...props} disabled={disabled || busy} aria-busy={busy || undefined} aria-describedby={message ? errorId : undefined} onClick={() => void run()}>{busy ? pendingLabel : children}</Button>
    {message && <p id={errorId} role="alert" className="action-error"><CircleAlert size={14} aria-hidden="true" />{message}</p>}
  </>;
}
