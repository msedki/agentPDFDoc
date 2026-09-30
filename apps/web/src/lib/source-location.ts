import type { Bbox, Block, Precision, Source } from "./types.ts";

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

/** Régions à surligner sur une page affichée ; aucune bbox fabriquée ni reportée d'une autre page. */
export function sourceRegionBoxes(source: Located | null, versionId: string, pageIndex: number): Bbox[] {
  if (!source || source.version_id !== versionId || sourcePrecision(source) === "page") return [];
  if (source.blocks?.length) return source.blocks.filter(block => block.page_index === pageIndex && regionBlock(block)).map(block => block.bbox!);
  const page = source.page_index ?? source.page_indices?.[0] ?? 0;
  return page === pageIndex && (source.page_indices?.length ?? 1) <= 1 ? (source.bboxes ?? []).filter(box) : [];
}
