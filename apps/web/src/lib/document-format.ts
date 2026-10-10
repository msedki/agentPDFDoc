import type { DocumentFormat, DocumentRecord, VersionRecord } from "./types.ts";
import type { Location } from "./store.ts";

export const DOCUMENT_FORMATS = ["pdf", "docx", "xlsx"] as const;
export const DOCUMENT_ACCEPT = "application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.xlsx";

/** La sélection navigateur est indicative ; le service contrôle le format réel. */
export function supportedDocumentName(name: string): boolean { return /\.(pdf|docx|xlsx)$/i.test(name); }

/** Les anciennes réponses sans format restent des PDF. Une version porte son propre format. */
export function versionFormat(document: DocumentRecord | undefined, version: VersionRecord | undefined): DocumentFormat {
  return version?.format ?? document?.format ?? "pdf";
}

export function formatLabel(format: DocumentFormat): string { return { pdf: "PDF", docx: "DOCX", xlsx: "XLSX" }[format]; }

export function documentLocation(documentId: string, versionId: string, format: DocumentFormat, pageIndex = 0): Location {
  return format === "pdf" ? { documentId, versionId, pageIndex } : { documentId, versionId, format };
}
