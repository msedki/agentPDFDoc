export type CitationPart<S> =
  | { kind: "text"; text: string }
  | { kind: "citation"; id: string; source: S }
  | { kind: "unknown"; id: string; text: string };

// Référence simple [S001] ou liste [S001, S002] / [S001; S002]. Le reste reste du texte brut.
const reference = /\[(S\d{3,}(?:\s*[,;]\s*S\d{3,})*)\]/g;

/** IDs cités dans l'ordre d'apparition, listes comprises. */
export function citedSourceIds(text: string): string[] {
  return Array.from(text.matchAll(reference), match => match[1].split(/\s*[,;]\s*/)).flat();
}

/** Découpe une réponse sans jamais interpréter HTML ni Markdown : seuls les IDs enregistrés deviennent cliquables. */
export function citationParts<S extends { source_id?: string }>(text: string, sources: S[]): CitationPart<S>[] {
  const parts: CitationPart<S>[] = [];
  let cursor = 0;
  for (const match of text.matchAll(reference)) {
    const start = match.index ?? 0;
    if (start > cursor) parts.push({ kind: "text", text: text.slice(cursor, start) });
    for (const id of match[1].split(/\s*[,;]\s*/)) {
      const source = sources.find(value => value.source_id === id);
      parts.push(source ? { kind: "citation", id, source } : { kind: "unknown", id, text: `[${id}]` });
    }
    cursor = start + match[0].length;
  }
  if (cursor < text.length) parts.push({ kind: "text", text: text.slice(cursor) });
  return parts;
}
