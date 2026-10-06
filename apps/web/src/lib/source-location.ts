import type { Bbox, Block, Precision, Source } from "./types.ts";
import type { Tone } from "./status.ts";

type Located = Pick<Source, "version_id" | "precision" | "blocks" | "bboxes" | "page_index" | "page_indices">;
const labels: Record<Precision, string> = { page: "Localisation à la page", table: "Table source", span: "Passage source", block: "Bloc source" };

function box(value: unknown): value is Bbox {
  return Array.isArray(value) && value.length === 4 && value.every(item => typeof item === "number" && Number.isFinite(item)) && value[2] > value[0] && value[3] > value[1];
}
function regionBlock(block: Block): boolean { return block.precision !== "page" && box(block.bbox); }

/** Précision réellement affichable : une région déclarée sans géométrie valide reste une localisation à la page. */
export function sourcePrecision(source: Located): Precision {
  const declared = source.precision ?? source.blocks?.[0]?.precision ?? "page";
  if (!(declared in labels) || declared === "page") return "page";
  const geometry = source.blocks?.length ? source.blocks.some(regionBlock) : Boolean(source.bboxes?.some(box));
  return geometry ? declared : "page";
}

export function sourcePrecisionLabel(source: Located): string { return labels[sourcePrecision(source)]; }

/**
 * Badge de précision d'une carte de source : famille exacte (passage, bloc ou
 * table avec géométrie), page seule, ou source sans page connue. Le libellé
 * reprend celui du lecteur pour que les deux vues emploient les mêmes termes.
 * Il décrit la localisation, pas le texte : une localisation précise reste une
 * information (ton « info ») et son info-bulle le dit (R26, texte OCR mal lu).
 */
export type SourceLocalization = { family: "exact" | "page" | "unlocated"; label: string; tone: Tone; title: string };
export function sourceLocalization(source: Located): SourceLocalization {
  if (source.page_index === undefined && !source.page_indices?.length) return { family: "unlocated", label: "Source non localisée", tone: "warning", title: "Aucune page n'est associée à cette source : le lecteur ne peut pas la situer." };
  const precision = sourcePrecision(source);
  return precision === "page"
    ? { family: "page", label: labels.page, tone: "neutral", title: "Seule la page est connue : aucune zone n'y est surlignée." }
    : { family: "exact", label: labels[precision], tone: "info", title: "La zone de ce passage est surlignée dans le lecteur. Cette localisation ne garantit pas l'exactitude du texte extrait." };
}

/** Régions à surligner sur une page affichée ; aucune bbox fabriquée ni reportée d'une autre page. */
export function sourceRegionBoxes(source: Located | null, versionId: string, pageIndex: number): Bbox[] {
  if (!source || source.version_id !== versionId || sourcePrecision(source) === "page") return [];
  if (source.blocks?.length) return source.blocks.filter(block => block.page_index === pageIndex && regionBlock(block)).map(block => block.bbox!);
  const page = source.page_index ?? source.page_indices?.[0] ?? 0;
  return page === pageIndex && (source.page_indices?.length ?? 1) <= 1 ? (source.bboxes ?? []).filter(box) : [];
}
