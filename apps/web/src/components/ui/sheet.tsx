"use client";
import { useEffect, useRef, type ReactNode, type Ref } from "react";
import { cn } from "@/lib/utils";

/**
 * Panneau latéral modal sur l'élément natif <dialog> (showModal) : le reste de
 * la page devient inerte, Échap ferme le panneau et le focus revient à
 * l'élément qui l'a ouvert. Aucun en-tête propre : le contenu porte son titre
 * (`labelledBy`) et son bouton « Fermer » libellé.
 */
export function Sheet({ open, onClose, side, labelledBy, className, bodyRef, children }: {
  open: boolean; onClose: () => void; side: "left" | "right"; labelledBy: string; className?: string;
  /** Conteneur où un panneau peut être déplacé sans être démonté (bibliothèque, analyse). */
  bodyRef?: Ref<HTMLDivElement>; children?: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const openRef = useRef(open);
  openRef.current = open;
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      element.showModal();
    } else if (!open && element.open) element.close();
  }, [open]);
  // Démontage pendant l'ouverture : libérer la couche supérieure.
  useEffect(() => { const element = dialog.current; return () => { if (element?.open) element.close(); }; }, []);
  return <dialog ref={dialog} className={cn("sheet", side === "left" ? "sheet-left" : "sheet-right", className)} aria-labelledby={labelledBy}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClose={() => {
      const target = opener.current;
      opener.current = null;
      if (target?.isConnected) target.focus();
      // Fermeture native (Échap répété sans activation) : l'état React suit.
      if (openRef.current) onClose();
    }}>
    <div className="sheet-body" ref={bodyRef}>{children}</div>
  </dialog>;
}
