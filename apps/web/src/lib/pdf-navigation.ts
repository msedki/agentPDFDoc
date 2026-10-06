export type PdfScrollLayout = { document: object; pageIndex: number; pageOffset: number };

export function pdfPageLayout<T extends { width: number; height: number }>(rendered: { key: string; viewport: T } | null, key: string, width: number, zoom: number, rotation: number) {
  const viewport = rendered?.key === key ? rendered.viewport : null;
  return { viewport, width: viewport?.width ?? (width - 48) * zoom,
    height: viewport?.height ?? (width - 48) * (rotation % 180 ? 1 / 1.414 : 1.414) * zoom };
}

/** A scroll-driven page change is not a request to snap to the page's beginning. */
export function pdfScrollTarget(previous: PdfScrollLayout | null, next: PdfScrollLayout, currentCenter: number, scrollTop: number): number | null {
  if (!previous || previous.document !== next.document || next.pageIndex !== currentCenter || scrollTop === 0 && next.pageIndex > 0) return next.pageOffset;
  if (previous.pageIndex === next.pageIndex && previous.pageOffset !== next.pageOffset) {
    return Math.max(0, scrollTop + next.pageOffset - previous.pageOffset);
  }
  return null;
}
