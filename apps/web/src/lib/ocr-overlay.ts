import type { Bbox, Block } from "./types";

export type OcrOverlay = { key: string; blockId: string; text: string; bbox: Bbox; precision: "span" | "block" | "table" };

function box(value: unknown): value is Bbox {
  return Array.isArray(value) && value.length === 4 && value.every(item => typeof item === "number" && Number.isFinite(item)) && value[2] > value[0] && value[3] > value[1];
}

function extractionMetadata(block: Block): Record<string, unknown> {
  let current: Record<string, unknown> = block.metadata ?? {};
  const combined = { ...current };
  for (let depth = 0; depth < 3; depth++) {
    const nested = current.metadata;
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) break;
    current = nested as Record<string, unknown>;
    Object.assign(combined, current);
  }
  return combined;
}

/** Nature du texte annoncée sous une page : rien n'est affirmé tant que la couche texte de PDF.js ou les blocs extraits sont en lecture. */
export function pageTextCaption(page: { extractionState?: string; nativeText: boolean | null; blocksLoading: boolean; ocrRegions: number; extractedTextAvailable?: boolean; blocksUnavailable?: boolean }): string {
  if (page.extractionState === "blank") return "Page blanche";
  if (page.nativeText === null || page.blocksLoading) return "Lecture de la page…";
  if (page.ocrRegions) return page.nativeText ? "Texte natif et régions OCR" : "Texte OCR";
  if (page.nativeText) return "Texte natif";
  if (page.blocksUnavailable) return "Texte extrait non vérifié";
  return page.extractedTextAvailable ? "Texte extrait disponible" : "Aucun texte extrait";
}

/** Le texte conservé prouve sa disponibilité, pas sa méthode OCR ni une position sur la page. */
export function hasExtractedText(blocks: Block[]): boolean {
  return blocks.some(block => (block.raw_text ?? block.text).trim().length > 0);
}

/** Only block or span provenance establishes OCR. A global parser route does not. */
export function ocrOverlays(blocks: Block[]): OcrOverlay[] {
  const output: OcrOverlay[] = [];
  for (const block of blocks) {
    const metadata = extractionMetadata(block);
    const text = block.raw_text ?? block.text;
    if (!text.trim() || block.precision === "page") continue;
    if (metadata.extraction_method === "ocr" && box(block.bbox)) {
      output.push({ key: block.id, blockId: block.id, text, bbox: block.bbox, precision: block.precision === "span" ? "span" : block.precision === "table" ? "table" : "block" });
    } else if (metadata.extraction_method === "mixed" && Array.isArray(metadata.ocr_spans)) {
      const codepoints = Array.from(text);
      for (const [index, value] of metadata.ocr_spans.entries()) {
        if (!value || typeof value !== "object") continue;
        const span = value as Record<string, unknown>;
        const start = span.start_offset; const end = span.end_offset;
        if (typeof start !== "number" || typeof end !== "number" || !Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > codepoints.length || !box(span.bbox) || span.precision !== "span") continue;
        const substring = codepoints.slice(start, end).join("");
        if (substring.trim()) output.push({ key: `${block.id}:${index}`, blockId: block.id, text: substring, bbox: span.bbox, precision: "span" });
      }
    }
  }
  return output;
}
