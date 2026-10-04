"use client";
import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

/**
 * Ferme un menu non modal sur Échap ou sur un clic hors de son conteneur.
 * `onDismiss` reçoit le motif : après Échap, l'appelant rend le focus au déclencheur.
 */
export function useDismiss(open: boolean, container: RefObject<HTMLElement | null>, onDismiss: (reason: "escape" | "outside") => void) {
  const callback = useRef(onDismiss);
  useLayoutEffect(() => { callback.current = onDismiss; }, [onDismiss]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !event.defaultPrevented) { event.preventDefault(); callback.current("escape"); } };
    const onPointer = (event: PointerEvent) => { if (container.current && event.target instanceof Node && !container.current.contains(event.target)) callback.current("outside"); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onPointer); };
  }, [open, container]);
}
