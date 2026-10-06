import { extractionBadge } from "@/lib/extraction-provenance";
import { Badge } from "./ui/badge";

/** Méthode d'extraction d'une source ou d'une citation : OCR, OCR partiel ou inconnue ; rien pour un texte natif. */
export function ExtractionBadge({ source }: { source: { extraction_methods?: unknown } }) {
  const badge = extractionBadge(source);
  return badge ? <Badge tone={badge.tone} title={badge.title} data-testid="extraction-badge" data-method={badge.method}>{badge.label}</Badge> : null;
}
