import type { Outline, PageBlocks, Source } from "./types.ts";

export type RevisionBinding = { revision: string | null; pinned: boolean; error: string | null };

export function citedRevision(versionId: string | undefined, source: Source | null): RevisionBinding {
  if (!versionId || !source?.source_id || source.version_id !== versionId) return { revision: null, pinned: false, error: null };
  if (!source.extraction_revision_id) return { revision: null, pinned: true, error: "La citation ne fournit pas sa révision d'extraction. Les blocs courants ne peuvent pas la remplacer." };
  return { revision: source.extraction_revision_id, pinned: true, error: null };
}

export function revisionActionGuard(binding: RevisionBinding, currentRevision: string | undefined, unavailable = false) {
  if (!binding.pinned) return { allowed: true, archived: false, reason: null };
  if (binding.error) return { allowed: false, archived: false, reason: binding.error };
  if (!currentRevision) return { allowed: false, archived: false, reason: unavailable ? "La révision courante ne peut pas être vérifiée. Analysez un texte sélectionné ou un bloc source." : "Vérification de la révision courante…" };
  if (currentRevision !== binding.revision) return { allowed: false, archived: true, reason: "Cette citation utilise une révision archivée. Analysez un texte sélectionné ou un bloc pour conserver sa révision." };
  return { allowed: true, archived: false, reason: null };
}

export function blocksPath(versionId: string, pageIndex: number, revision?: string | null) {
  return `/versions/${encodeURIComponent(versionId)}/pages/${pageIndex}/blocks${revision ? `?extraction_revision_id=${encodeURIComponent(revision)}` : ""}`;
}

export function outlinePath(versionId: string, revision?: string | null) {
  return `/versions/${encodeURIComponent(versionId)}/outline${revision ? `?extraction_revision_id=${encodeURIComponent(revision)}` : ""}`;
}

export function blocksKey(versionId: string | undefined, pageIndex: number | undefined, revision?: string | null) {
  return ["blocks", versionId, pageIndex, revision ?? null] as const;
}

export function verifyPinnedBlocks(result: PageBlocks, versionId: string, pageIndex: number, revision?: string | null): PageBlocks {
  if (revision && (result.version_id !== versionId || result.page.page_index !== pageIndex || result.extraction_revision_id !== revision || result.blocks.some(block => block.extraction_revision_id !== revision))) {
    throw new Error("Les blocs reçus ne correspondent pas à la version, page et révision de la citation. Aucune extraction récente n'est substituée.");
  }
  return result;
}

export function verifyPinnedOutline(result: Outline, versionId: string, revision?: string | null): Outline {
  if (revision && (result.version_id !== versionId || result.extraction_revision_id !== revision)) throw new Error("Le sommaire reçu ne correspond pas à la révision de la citation.");
  return result;
}
