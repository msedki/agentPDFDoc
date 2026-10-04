export type PdfSearchResult = { kind: "found"; pageIndex: number } | { kind: "absent" } | { kind: "cancelled" };
type PdfReading = { versionId: string | undefined; source: object | null };

/** Le store garde la source immutable tant que la même preuve reste ouverte. */
export function samePdfReading(left: PdfReading, right: PdfReading): boolean {
  return left.versionId === right.versionId && left.source === right.source;
}

/** Parcours circulaire ; une lecture remplacée ne peut pas déplacer le nouveau document. */
export async function findNextPdfPage({ pageCount, pageIndex, expression, signal, isCurrent, readNative, readExtracted }: {
  pageCount: number; pageIndex: number; expression: string; signal: AbortSignal;
  isCurrent: () => boolean;
  readNative: (index: number) => Promise<string>;
  readExtracted?: (index: number, signal: AbortSignal) => Promise<string>;
}): Promise<PdfSearchResult> {
  const current = () => !signal.aborted && isCurrent();
  const needle = expression.trim().toLocaleLowerCase();
  if (!needle) return { kind: "absent" };
  try {
    for (let step = 1; step <= pageCount; step++) {
      if (!current()) return { kind: "cancelled" };
      const index = (pageIndex + step) % pageCount;
      let text = await readNative(index);
      if (!current()) return { kind: "cancelled" };
      // Une page mixte peut porter un paragraphe natif et un tableau OCR.
      if (readExtracted) {
        text += " " + await readExtracted(index, signal);
        if (!current()) return { kind: "cancelled" };
      }
      if (text.toLocaleLowerCase().includes(needle)) return { kind: "found", pageIndex: index };
    }
    return { kind: "absent" };
  } catch (error) {
    if (!current()) return { kind: "cancelled" };
    throw error;
  }
}
