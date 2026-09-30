import type { DocumentDetail } from "./types";

export function hasPublishedExtraction(document: DocumentDetail | undefined, versionId?: string | null): boolean {
  if (!document || !versionId || document.state === "deleted") return false;
  if (document.active_generation_id && (document.active_version_id ?? document.version_id) === versionId) return true;
  return Boolean(document.jobs?.some(job => job.version_id === versionId && (job.published === true || Boolean(job.published_at))));
}
