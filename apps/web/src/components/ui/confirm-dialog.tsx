"use client";
import { useEffect, useId, useLayoutEffect, useRef, type KeyboardEvent } from "react";
import { CircleAlert, TriangleAlert } from "lucide-react";
import { Button } from "./button";

/** Le dialogue n'a que des actions : compléter la navigation native aux bornes. */
function keepTabWithinConfirmation(event: KeyboardEvent<HTMLDialogElement>) {
  const element = event.currentTarget;
  if (event.key !== "Tab" || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || !element.open) return;
  const actions = Array.from(element.querySelectorAll<HTMLButtonElement>("button:enabled"));
  const active = element.ownerDocument.activeElement;
  if (!actions.length) {
    event.preventDefault();
    element.querySelector<HTMLElement>("h2")?.focus();
  } else if (!actions.includes(active as HTMLButtonElement) || (event.shiftKey ? active === actions[0] : active === actions.at(-1))) {
    event.preventDefault();
    (event.shiftKey ? actions.at(-1) : actions[0])?.focus();
  }
}

/**
 * Confirmation modale native : arrière-plan inerte et restitution du focus par
 * le navigateur ; boucle Tab/Shift+Tab assurée aux bornes des actions du dialogue.
 * Le message dit la conséquence de l'action ; un échec reste affiché dans le
 * dialogue, que Échap ne ferme pas tant que l'action est en cours. Le navigateur
 * peut toutefois le fermer de lui-même (Échap répété sans nouvelle activation) :
 * `onCancel` est alors appelé pour que l'état React suive, et l'appelant rouvre
 * le dialogue si l'action échoue ensuite.
 */
export function ConfirmDialog({ open, title, message, confirmLabel, pendingLabel, cancelLabel = "Annuler", pending = false, error, onConfirm, onCancel }: {
  open: boolean; title: string; message: string; confirmLabel: string; pendingLabel: string; cancelLabel?: string;
  pending?: boolean; error?: string; onConfirm: () => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const openRef = useRef(open);
  const cancelAction = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => { openRef.current = open; }, [open]);
  const titleId = useId();
  const messageId = useId();
  const errorId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      element.showModal();
      if (!pending) cancelAction.current?.focus();
    }
    else if (!open && element.open) element.close();
    // Les actions désactivées ne sont plus des cibles de focus pendant le traitement.
    if (open && pending) element.querySelector<HTMLElement>("h2")?.focus();
  }, [open, pending]);
  // Démontage pendant l'ouverture (document retiré puis fermé) : libérer la couche supérieure.
  useEffect(() => { const element = dialog.current; return () => { if (element?.open) element.close(); }; }, []);
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby={titleId} aria-describedby={error ? `${messageId} ${errorId}` : messageId}
    onKeyDown={keepTabWithinConfirmation}
    onCancel={event => { event.preventDefault(); if (!pending) onCancel(); }}
    onClose={() => { if (openRef.current) onCancel(); }}>
    <h2 id={titleId} tabIndex={-1}><TriangleAlert size={16} aria-hidden="true" />{title}</h2>
    <p id={messageId}>{message}</p>
    {error && <p id={errorId} role="alert" className="action-error"><CircleAlert size={14} aria-hidden="true" />{error}</p>}
    <div className="confirm-dialog-actions">
      <Button ref={cancelAction} type="button" variant="secondary" size="sm" disabled={pending} onClick={onCancel}>{cancelLabel}</Button>
      <Button type="button" variant="danger" size="sm" disabled={pending} aria-busy={pending || undefined} onClick={onConfirm}>{pending ? pendingLabel : confirmLabel}</Button>
    </div>
  </dialog>;
}
