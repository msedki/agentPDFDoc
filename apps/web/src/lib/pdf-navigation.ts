/**
 * Position de lecture associée à une géométrie : page active, son offset, et le scrollTop observé dans cette
 * géométrie (dernier défilement ou dernier recadrage du lecteur), avant tout changement de hauteur des pages.
 */
export type PdfScrollLayout = { document: object; pageIndex: number; pageOffset: number; scrollTop: number };

/** Ligne de lecture du lecteur, sous le haut de la zone de défilement : la page qui la contient est la page lue. */
export const READING_LINE = 100;

/**
 * Page lue d'après le défilement : celle qui contient la ligne de lecture. Une page de fin dont le début ne peut plus
 * atteindre cette ligne (pages restantes plus courtes que la zone de défilement) reste la page courante tant que la vue
 * est en butée basse : le recadrage du navigateur après un agrandissement du lecteur ou une navigation explicite n'est
 * pas un défilement vers la page précédente (R26-UI-02).
 */
export function pdfPageAtScroll(offsets: number[], pageCount: number, scrollTop: number, maxScrollTop: number, current: number): number {
  let page = 0;
  while (page + 1 < pageCount && offsets[page + 1] <= scrollTop + READING_LINE) page++;
  const pinnedAtBottom = scrollTop >= maxScrollTop - 1;
  if (pinnedAtBottom && current > page && current < pageCount && offsets[current] > maxScrollTop + READING_LINE) return current;
  return page;
}

export function pdfPageLayout<T extends { width: number; height: number }>(rendered: { key: string; viewport: T } | null, key: string, width: number, zoom: number, rotation: number) {
  const viewport = rendered?.key === key ? rendered.viewport : null;
  return { viewport, width: viewport?.width ?? (width - 48) * zoom,
    height: viewport?.height ?? (width - 48) * (rotation % 180 ? 1 / 1.414 : 1.414) * zoom };
}

/**
 * A scroll-driven page change is not a request to snap to the page's beginning.
 * `scrollTop` is the live value: when the new slots are shorter (rotation, zoom out, measured heights), the browser
 * has already clamped it in the same commit. The within-page position therefore comes from `previous.scrollTop`,
 * observed in the previous geometry, never from the clamped value (R26-KIT-02 D3).
 */
export function pdfScrollTarget(previous: PdfScrollLayout | null, next: Omit<PdfScrollLayout, "scrollTop">, currentCenter: number, scrollTop: number): number | null {
  if (!previous || previous.document !== next.document || next.pageIndex !== currentCenter || scrollTop === 0 && next.pageIndex > 0) return next.pageOffset;
  if (previous.pageIndex === next.pageIndex && previous.pageOffset !== next.pageOffset) {
    // Ligne de lecture dans la page : position exacte. Plus haut, la page n'était pas atteignable (fin du document) :
    // elle s'affiche à partir de son début.
    const within = previous.scrollTop - previous.pageOffset;
    return Math.max(0, next.pageOffset + (within < -READING_LINE ? 0 : within));
  }
  return null;
}
