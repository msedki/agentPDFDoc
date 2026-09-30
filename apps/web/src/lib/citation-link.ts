import type { Source } from "./types.ts";

const idPattern = /^[\w-]{1,128}$/;

export function citationLinkIds(params: URLSearchParams) {
  const queryId = params.get("citation_query");
  const sourceId = params.get("citation_source");
  if (!queryId && !sourceId) return null;
  if (!queryId || !sourceId || !idPattern.test(queryId) || !idPattern.test(sourceId)) throw new Error("Le lien de citation ne contient pas deux identifiants valides.");
  return { queryId, sourceId };
}

export function registeredCitationLocation(source: Source, queryId: string, sourceId: string) {
  const pageIndex = source.page_index ?? source.page_indices?.[0] ?? source.blocks?.[0]?.page_index;
  if (source.query_id !== queryId || source.source_id !== sourceId || typeof source.document_id !== "string" || !idPattern.test(source.document_id) || typeof source.version_id !== "string" || !idPattern.test(source.version_id) || typeof source.extraction_revision_id !== "string" || !idPattern.test(source.extraction_revision_id) || !Number.isInteger(pageIndex) || pageIndex! < 0) {
    throw new Error("Le registre ne fournit pas la version, page et révision exactes de cette citation. Aucun document courant n'est substitué.");
  }
  return { documentId: source.document_id, versionId: source.version_id, pageIndex: pageIndex! };
}
