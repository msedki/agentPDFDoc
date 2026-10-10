import type { Source } from "./types.ts";
import { locatorRange } from "./office-reader.ts";
import type { Location } from "./store.ts";

const idPattern = /^[\w-]{1,128}$/;

export function citationLinkIds(params: URLSearchParams) {
  const queryId = params.get("citation_query");
  const sourceId = params.get("citation_source");
  if (!queryId && !sourceId) return null;
  if (!queryId || !sourceId || !idPattern.test(queryId) || !idPattern.test(sourceId)) throw new Error("Le lien de citation ne contient pas deux identifiants valides.");
  return { queryId, sourceId };
}

export function sourceLocation(source: Source): Location {
  const identity = { documentId: source.document_id, versionId: source.version_id };
  const locator = source.locator;
  if (source.format && locator && (source.format === "docx" && locator.kind !== "docx_element" || source.format === "xlsx" && locator.kind !== "xlsx_cells" || source.format === "pdf" && locator.kind !== "pdf_page")) throw new Error("Le format et la localisation de cette source ne correspondent pas.");
  if (locator?.kind === "docx_element" && locator.unit_id && locator.part && locator.element_path && source.extraction_revision_id) return { ...identity, format: "docx", unitId: locator.unit_id, elementPath: locator.element_path, extractionRevisionId: source.extraction_revision_id, ...(source.block_ids?.[0] ? { blockId: source.block_ids[0] } : {}) };
  if (locator?.kind === "xlsx_cells" && locator.sheet_id && locator.unit_id === locator.sheet_id && source.extraction_revision_id) {
    const cellRange = locatorRange(locator);
    if (cellRange) return { ...identity, format: "xlsx", unitId: locator.sheet_id, cellRange, extractionRevisionId: source.extraction_revision_id };
  }
  if (source.format === "docx" || source.format === "xlsx" || locator?.kind === "docx_element" || locator?.kind === "xlsx_cells") throw new Error("Cette source Office ne fournit pas sa localisation et sa révision exactes. Aucune page PDF ou révision récente n'est substituée.");
  const pageIndex = source.page_index ?? source.page_indices?.[0] ?? source.blocks?.[0]?.page_index;
  if (!Number.isInteger(pageIndex) || pageIndex! < 0) throw new Error("Cette source ne fournit pas sa page exacte.");
  return { ...identity, pageIndex: pageIndex! };
}

export function registeredCitationLocation(source: Source, queryId: string, sourceId: string): Location {
  if (source.query_id !== queryId || source.source_id !== sourceId || typeof source.document_id !== "string" || !idPattern.test(source.document_id) || typeof source.version_id !== "string" || !idPattern.test(source.version_id) || typeof source.extraction_revision_id !== "string" || !idPattern.test(source.extraction_revision_id)) {
    throw new Error("Le registre ne fournit pas la version, la localisation et la révision exactes de cette citation. Aucun document courant n'est substitué.");
  }
  return sourceLocation(source);
}
