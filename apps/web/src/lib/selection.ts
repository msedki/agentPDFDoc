import type { Block, SelectedSpan } from "./types";

export function utf16ToCodePointOffset(text: string, offset: number): number {
  if (!Number.isInteger(offset) || offset < 0 || offset > text.length) throw new RangeError("Invalid UTF-16 offset");
  if (offset > 0 && offset < text.length && /[\uD800-\uDBFF]/.test(text[offset - 1]) && /[\uDC00-\uDFFF]/.test(text[offset])) throw new RangeError("Offset splits a surrogate pair");
  return Array.from(text.slice(0, offset)).length;
}

export function wholeBlockSpan(block: Block): SelectedSpan | null {
  const hash = block.source_text_hash ?? block.source_text_sha256;
  if (!block.extraction_revision_id || !hash || !/^[a-fA-F0-9]{64}$/.test(hash)) return null;
  return { extractionRevisionId: block.extraction_revision_id, blockId: block.id, blockTextSha256: hash, offsetUnit: "unicode_code_point", startOffset: 0, endOffset: Array.from(block.source_text ?? block.raw_text ?? block.text).length };
}

function normalizedWithMap(text: string) {
  let normalized = "";
  const offsets: number[] = [];
  let whitespace = false;
  for (let index = 0; index < text.length; index++) {
    if (/\s/u.test(text[index])) {
      if (normalized && !whitespace) { normalized += " "; offsets.push(index); }
      whitespace = true;
    } else { normalized += text[index]; offsets.push(index); whitespace = false; }
  }
  if (normalized.endsWith(" ")) { normalized = normalized.slice(0, -1); offsets.pop(); }
  return { normalized, offsets };
}

/** Map selected text back to unique backend text; ambiguous matches are refused. */
export function reconcileSelection(selectedText: string, blocks: Block[]): SelectedSpan[] | null {
  const selected = normalizedWithMap(selectedText).normalized;
  if (!selected) return null;
  const segments = blocks.map(block => ({ block, sourceText: block.source_text ?? block.raw_text ?? block.text })).filter(segment => segment.sourceText.trim()).map(segment => ({ ...segment, ...normalizedWithMap(segment.sourceText) }));
  let documentText = "";
  const locations: { segment: typeof segments[number]; start: number; end: number }[] = [];
  for (const segment of segments) {
    if (documentText) documentText += " ";
    const start = documentText.length;
    documentText += segment.normalized;
    locations.push({ segment, start, end: documentText.length });
  }
  const match = documentText.indexOf(selected);
  if (match < 0 || documentText.indexOf(selected, match + 1) >= 0) return null;
  const finish = match + selected.length;
  const matched = locations.filter(location => location.end > match && location.start < finish);
  if (matched.some(({ segment }) => !wholeBlockSpan(segment.block))) return null;
  return matched.map(({ segment, start, end }) => {
    const first = Math.max(match, start) - start;
    const last = Math.min(finish, end) - start - 1;
    return { ...wholeBlockSpan(segment.block)!, startOffset: utf16ToCodePointOffset(segment.sourceText, segment.offsets[first]), endOffset: utf16ToCodePointOffset(segment.sourceText, segment.offsets[last] + 1) };
  });
}

export function boundedCanvasSize(width: number, height: number, devicePixelRatio: number, totalBudget = 24_000_000, maxCanvases = 5) {
  const scale = Math.min(devicePixelRatio, 2, Math.sqrt((totalBudget / maxCanvases) / (width * height)));
  return { width: Math.max(1, Math.floor(width * scale)), height: Math.max(1, Math.floor(height * scale)), scale };
}

export function sourcePage(source: { page_index?: number | null; page_indices?: number[] }): number {
  return source.page_index ?? source.page_indices?.[0] ?? 0;
}
export function visiblePageWindow(center: number, total: number): number[] {
  const start = Math.min(Math.max(0, center - 2), Math.max(0, total - 5));
  return Array.from({ length: Math.min(5, total) }, (_, offset) => start + offset);
}
