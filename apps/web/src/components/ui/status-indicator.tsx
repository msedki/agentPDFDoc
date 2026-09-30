import type { StatusView } from "@/lib/status";
import { cn } from "@/lib/utils";

/**
 * Pastille de couleur toujours doublée de son libellé : la couleur ne code
 * jamais seule un état. Un code inconnu garde un libellé explicite et expose
 * le code reçu en info-bulle pour le diagnostic.
 */
export function StatusIndicator({ status, active = false, title, className }: { status: StatusView; active?: boolean; title?: string; className?: string }) {
  const diagnostic = status.known ? undefined : `Code transmis par le service : ${status.code || "absent"}`;
  return <span className={cn("status-indicator", className)} data-tone={status.tone} title={title ?? diagnostic}>
    <span className={cn("status-dot", active && "is-active")} aria-hidden="true" />{status.label}
  </span>;
}
