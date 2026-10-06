import type { Tone } from "./status.ts";

/**
 * Méthode d'extraction d'une source ou d'une citation (contrat R26-OCR-01, `extraction_methods`).
 * Un champ absent (citation ou événement enregistrés avant le 2026-10-06) se lit « inconnue », jamais « native ».
 */
export type ExtractionMethod = "native" | "ocr" | "mixed" | "unknown";
const vocabulary: ReadonlySet<string> = new Set<ExtractionMethod>(["native", "ocr", "mixed", "unknown"]);

/**
 * Erreurs que le seuil de confiance OCR ne repère pas : sur la fixture DA-P02, « ± » lu « + », « N·m » lu « N-m »
 * et « DA-P02 » lu « DA-PO2 » sont rendus sans alerte. Formulation commune aux alertes de faible confiance et au badge.
 */
export const OCR_MISREADINGS = "signes, unités et références peuvent être mal lus (± lu +, N·m lu N-m, 0 lu O)";

export function sourceExtractionMethods(source: { extraction_methods?: unknown }): ExtractionMethod[] {
  const listed = Array.isArray(source.extraction_methods) ? source.extraction_methods : [];
  const methods = new Set<ExtractionMethod>(listed.map(value => typeof value === "string" && vocabulary.has(value) ? value as ExtractionMethod : "unknown"));
  return methods.size ? [...methods].sort() : ["unknown"];
}

export type ExtractionBadge = { method: "ocr" | "mixed" | "unknown"; label: string; tone: Tone; title: string };

/** Badge d'une source : texte lu par OCR en tout ou partie, méthode inconnue, ou rien pour un texte natif. */
export function extractionBadge(source: { extraction_methods?: unknown }): ExtractionBadge | null {
  const methods = sourceExtractionMethods(source);
  if (methods.length === 1 && methods[0] === "ocr") {
    return { method: "ocr", label: "Lu par OCR", tone: "warning", title: `Texte de cette source reconnu par OCR : même sans alerte de faible confiance, ${OCR_MISREADINGS} ; comparez-les à la page originale.` };
  }
  if (methods.includes("ocr") || methods.includes("mixed")) {
    return { method: "mixed", label: "En partie lu par OCR", tone: "warning", title: `Une partie du texte de cette source a été reconnue par OCR : même sans alerte de faible confiance, ${OCR_MISREADINGS} ; comparez-les à la page originale.` };
  }
  if (methods.includes("unknown")) {
    const part = methods.length === 1 ? "de cette source" : "d'une partie de cette source";
    return { method: "unknown", label: "Méthode d'extraction inconnue", tone: "neutral", title: `La méthode d'extraction ${part} n'est pas connue (citation enregistrée ou document indexé avant l'ajout de cette information) : son texte a pu être lu par OCR. Comparez signes, unités et références à la page originale.` };
  }
  return null;
}

/** Titre d'un lien de citation complété par la méthode d'extraction lorsqu'elle appelle une vérification. */
export function withExtractionLabel(title: string, source: { extraction_methods?: unknown }): string {
  const badge = extractionBadge(source);
  return badge ? `${title} · ${badge.label}` : title;
}
