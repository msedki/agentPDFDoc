"use client";
import { useEffect, useId, useRef } from "react";
import { CircleAlert, TriangleAlert } from "lucide-react";
import { Button } from "./button";

/**
 * Confirmation modale sur l'élément natif <dialog> (showModal) : piège de focus,
 * Échap et restitution du focus sont assurés par le navigateur, sans dépendance.
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
  openRef.current = open;
  const titleId = useId();
  const messageId = useId();
  const errorId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    else if (!open && element.open) element.close();
  }, [open]);
  // Démontage pendant l'ouverture (document retiré puis fermé) : libérer la couche supérieure.
  useEffect(() => { const element = dialog.current; return () => { if (element?.open) element.close(); }; }, []);
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby={titleId} aria-describedby={error ? `${messageId} ${errorId}` : messageId}
    onCancel={event => { event.preventDefault(); if (!pending) onCancel(); }}
    onClose={() => { if (openRef.current) onCancel(); }}>
    <h2 id={titleId}><TriangleAlert size={16} aria-hidden="true" />{title}</h2>
    <p id={messageId}>{message}</p>
    {error && <p id={errorId} role="alert" className="action-error"><CircleAlert size={14} aria-hidden="true" />{error}</p>}
    <div className="confirm-dialog-actions">
      <Button type="button" variant="secondary" size="sm" disabled={pending} onClick={onCancel}>{cancelLabel}</Button>
      <Button type="button" variant="danger" size="sm" disabled={pending} aria-busy={pending || undefined} onClick={onConfirm}>{pending ? pendingLabel : confirmLabel}</Button>
    </div>
  </dialog>;
}
