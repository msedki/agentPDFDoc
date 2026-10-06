/** QA only: full native TextLayer passages versus observed highlight rectangles. */
export type CoverageRectangle = { x: number; y: number; width: number; height: number };
export type CitationCoverageInput = {
  pageIndex: number;
  passages: { id: string; text: string }[];
};
export type CitationCoverageFragment = {
  nodeIndex: number;
  startOffset: number;
  endOffset: number;
  text: string;
  rects: CoverageRectangle[];
  covered: boolean;
  ink: number;
  background: number;
  pixels: number;
  painted: boolean;
  reason?: string;
};
export type CitationCoveragePassage = {
  id: string;
  expectedText: string;
  normalizedText: string;
  matches: number;
  fragments: CitationCoverageFragment[];
  passed: boolean;
  reason?: string;
};
export type CitationCoverageResult = {
  pageIndex: number;
  pageBox?: CoverageRectangle;
  highlights: CoverageRectangle[];
  passages: CitationCoveragePassage[];
  passed: boolean;
  reason?: string;
};

// Keep all executable dependencies inside this function: page.evaluate serializes
// the function, not this module or its closure. No API bbox enters the oracle.
export function measureCitationCoverage(input: CitationCoverageInput): CitationCoverageResult {
  const tolerance = 4;
  const result: CitationCoverageResult = { pageIndex: input.pageIndex, highlights: [], passages: [], passed: false };
  const normalize = (text: string) => text.replace(/\s+/gu, " ").trim();
  const rectangle = (box: DOMRect): CoverageRectangle => ({ x: box.x, y: box.y, width: box.width, height: box.height });
  const valid = (box: CoverageRectangle) => [box.x, box.y, box.width, box.height, box.x + box.width, box.y + box.height].every(Number.isFinite)
    && box.width > 0 && box.height > 0;
  const inside = (box: CoverageRectangle, outer: CoverageRectangle) => box.x >= outer.x - tolerance
    && box.y >= outer.y - tolerance && box.x + box.width <= outer.x + outer.width + tolerance
    && box.y + box.height <= outer.y + outer.height + tolerance;

  // Sweep the complete target area, rather than testing its centre or summing
  // overlapping areas. Separate overlays may together cover one native line.
  const covered = (box: CoverageRectangle, highlights: CoverageRectangle[]) => {
    const right = box.x + box.width, bottom = box.y + box.height;
    const clipped = highlights.map(highlight => ({
      left: Math.max(box.x, highlight.x - tolerance),
      top: Math.max(box.y, highlight.y - tolerance),
      right: Math.min(right, highlight.x + highlight.width + tolerance),
      bottom: Math.min(bottom, highlight.y + highlight.height + tolerance),
    })).filter(item => item.right > item.left && item.bottom > item.top);
    const edges = [...new Set([box.x, right, ...clipped.flatMap(item => [item.left, item.right])])].sort((a, b) => a - b);
    for (let index = 0; index < edges.length - 1; index++) {
      const left = edges[index], end = edges[index + 1];
      const vertical = clipped.filter(item => item.left <= left && item.right >= end).sort((a, b) => a.top - b.top);
      let reached = box.y;
      for (const item of vertical) {
        if (item.top > reached) return false;
        reached = Math.max(reached, item.bottom);
      }
      if (reached < bottom) return false;
    }
    return clipped.length > 0;
  };

  if (!Number.isInteger(input.pageIndex) || input.pageIndex < 0 || !input.passages.length) {
    result.reason = "invalid_page_or_empty_passages";
    return result;
  }
  const slots = [...document.querySelectorAll<HTMLElement>(`.pdf-page-slot[data-page-index="${input.pageIndex}"]`)];
  if (slots.length !== 1) { result.reason = "page_not_unique"; return result; }
  const slot = slots[0];
  const canvas = slot.querySelector<HTMLCanvasElement>("canvas");
  const layers = [...slot.querySelectorAll<HTMLElement>(".textLayer")];
  if (!canvas || !canvas.isConnected || ![canvas.width, canvas.height].every(value => Number.isInteger(value) && value > 0)
    || layers.length !== 1) {
    result.reason = "native_page_unavailable";
    return result;
  }
  const pageBox = rectangle(canvas.getBoundingClientRect());
  result.pageBox = pageBox;
  if (!valid(pageBox)) { result.reason = "invalid_page_geometry"; return result; }
  const highlightElements = [...slot.querySelectorAll<HTMLElement>('[data-testid="source-highlight"]')];
  result.highlights = highlightElements.map(element => rectangle(element.getBoundingClientRect()));
  if (!result.highlights.length || result.highlights.some(box => !valid(box) || !inside(box, pageBox))
    || highlightElements.some(element => {
      const style = getComputedStyle(element);
      return !element.isConnected || style.display === "none" || style.visibility !== "visible" || Number(style.opacity) === 0;
    })) {
    result.reason = "invalid_or_missing_highlights";
    return result;
  }

  type Unit = { character: string; nodeIndex: number | null; start: number; end: number };
  const nodes: Text[] = [], units: Unit[] = [];
  const append = (text: string, nodeIndex: number | null) => {
    let offset = 0;
    for (const character of text) {
      const end = offset + character.length;
      if (/\s/u.test(character)) {
        if (units.at(-1)?.character !== " ") units.push({ character: " ", nodeIndex: null, start: 0, end: 0 });
      } else units.push({ character, nodeIndex, start: offset, end });
      offset = end;
    }
  };
  const visit = (node: Node) => {
    if (node.nodeType === 3) {
      const text = node as Text;
      // PDF.js creates span text nodes; markedContent containers are traversed
      // once, not counted again as overlapping parent-span text.
      if (text.parentElement?.closest("span")) {
        const nodeIndex = nodes.push(text) - 1;
        append(text.data, nodeIndex);
      }
    } else if (node.nodeName === "BR") append("\n", null);
    else for (const child of node.childNodes) visit(child);
  };
  visit(layers[0]);
  const actual = units.map(unit => unit.character);
  for (const expected of input.passages) {
    const normalizedText = normalize(expected.text);
    const passage: CitationCoveragePassage = { id: expected.id, expectedText: expected.text, normalizedText, matches: 0, fragments: [], passed: false };
    result.passages.push(passage);
    if (!normalizedText) { passage.reason = "empty_expected_text"; continue; }
    const wanted = Array.from(normalizedText);
    const matches: number[] = [];
    for (let start = 0; start <= actual.length - wanted.length; start++) {
      if (wanted.every((character, offset) => character === actual[start + offset])) matches.push(start);
    }
    passage.matches = matches.length;
    if (matches.length !== 1) { passage.reason = matches.length ? "ambiguous_full_passage" : "full_passage_not_found"; continue; }
    const selected = units.slice(matches[0], matches[0] + wanted.length);
    for (const unit of selected) {
      if (unit.nodeIndex === null) continue;
      const last = passage.fragments.at(-1);
      if (last?.nodeIndex === unit.nodeIndex) last.endOffset = unit.end;
      else passage.fragments.push({ nodeIndex: unit.nodeIndex, startOffset: unit.start, endOffset: unit.end,
        text: "", rects: [], covered: false, ink: 0, background: 0, pixels: 0, painted: false });
    }
    for (const fragment of passage.fragments) {
      const node = nodes[fragment.nodeIndex];
      fragment.text = node.data.slice(fragment.startOffset, fragment.endOffset);
      const range = document.createRange();
      try {
        range.setStart(node, fragment.startOffset);
        range.setEnd(node, fragment.endOffset);
        fragment.rects = [...range.getClientRects()].map(rectangle);
      } catch {
        fragment.reason = "native_range_unavailable";
        continue;
      }
      if (!fragment.rects.length || fragment.rects.some(box => !valid(box))) fragment.reason = "invalid_native_geometry";
      else if (fragment.rects.some(box => !inside(box, pageBox))) fragment.reason = "native_text_off_page";
      else {
        fragment.covered = fragment.rects.every(box => covered(box, result.highlights));
        if (!fragment.covered) fragment.reason = "incomplete_highlight_coverage";
        // Original-canvas ink is a separate bounded observation; neither the
        // TextLayer nor these pixels attest RenderTask.promise completion.
        const context = canvas.getContext("2d");
        const windows = fragment.rects.map(box => {
          const left = Math.max(0, Math.floor((box.x - pageBox.x) * canvas.width / pageBox.width) - 1);
          const top = Math.max(0, Math.floor((box.y - pageBox.y) * canvas.height / pageBox.height) - 1);
          const right = Math.min(canvas.width, Math.ceil((box.x + box.width - pageBox.x) * canvas.width / pageBox.width) + 1);
          const bottom = Math.min(canvas.height, Math.ceil((box.y + box.height - pageBox.y) * canvas.height / pageBox.height) + 1);
          return { left, top, width: right - left, height: bottom - top };
        });
        fragment.pixels = windows.reduce((sum, item) => sum + item.width * item.height, 0);
        if (!context || windows.some(item => item.width <= 0 || item.height <= 0) || fragment.pixels > 160_000) {
          fragment.reason ??= "bounded_bitmap_unavailable";
        } else {
          try {
            for (const item of windows) {
              const rgba = context.getImageData(item.left, item.top, item.width, item.height).data;
              for (let offset = 0; offset < rgba.length; offset += 4) {
                if (rgba[offset + 3] !== 255) continue;
                if (Math.max(rgba[offset], rgba[offset + 1], rgba[offset + 2]) < 180) fragment.ink++;
                if (Math.min(rgba[offset], rgba[offset + 1], rgba[offset + 2]) >= 245) fragment.background++;
              }
            }
            fragment.painted = fragment.ink >= 8 && fragment.background >= 8;
            if (!fragment.painted) fragment.reason ??= "native_bitmap_without_ink_or_background";
          } catch { fragment.reason ??= "bounded_bitmap_unavailable"; }
        }
      }
    }
    passage.passed = passage.fragments.length > 0 && passage.fragments.every(fragment => fragment.covered && fragment.painted);
    if (!passage.passed) passage.reason = passage.fragments.find(fragment => fragment.reason)?.reason ?? "no_native_fragments";
  }
  result.passed = result.passages.length === input.passages.length && result.passages.every(passage => passage.passed);
  if (!result.passed) result.reason = "passage_coverage_failed";
  return result;
}
