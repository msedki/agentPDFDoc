import type { DocumentDetail } from "./types.ts";

/** Nombre de pages de la version ouverte ; celui du document décrit sa version active, pas une ancienne. */
export function versionPageCount(document: DocumentDetail | undefined, versionId: string | undefined): number | null {
  const count = document?.versions?.find(version => version.id === versionId)?.page_count;
  return typeof count === "number" && Number.isInteger(count) && count > 0 ? count : null;
}

/** Plage 1-based saisie ; message affichable, ou null si elle appartient à la version ouverte. */
export function pageRangeError(pageStart: number, pageEnd: number, pageCount: number | null): string | null {
  if (pageCount === null) return "Le nombre de pages de la version ouverte n'est pas encore connu.";
  if (!Number.isInteger(pageStart) || !Number.isInteger(pageEnd) || pageStart < 1 || pageEnd < pageStart || pageEnd > pageCount) return `La plage doit correspondre aux pages de la version ouverte (1 à ${pageCount}).`;
  return null;
}
