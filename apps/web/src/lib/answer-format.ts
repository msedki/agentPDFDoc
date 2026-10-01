/**
 * Mise en forme d'une réponse du modèle : paragraphes, listes à puces et gras `**…**`, les seules marques Markdown
 * qu'il emploie couramment. Aucune balise n'est interprétée : le résultat ne contient que du texte, rendu ensuite par
 * des éléments React, si bien qu'un balisage présent dans une réponse reste lisible tel quel et inactif.
 */
export type Inline = { text: string; strong: boolean };
export type AnswerBlock = { kind: "paragraph"; lines: Inline[][] } | { kind: "list"; items: Inline[][] };

const BULLET = /^\s*[*•-]\s+(.*)$/;
const STRONG = /\*\*(.+?)\*\*/g;

/** Seuls les couples `**…**` complets passent en gras : un astérisque isolé, ou un couple encore ouvert pendant la réception, reste du texte. */
export function inlineSegments(line: string): Inline[] {
  const segments: Inline[] = [];
  let cursor = 0;
  for (const match of line.matchAll(STRONG)) {
    const start = match.index ?? 0;
    if (start > cursor) segments.push({ text: line.slice(cursor, start), strong: false });
    segments.push({ text: match[1], strong: true });
    cursor = start + match[0].length;
  }
  if (cursor < line.length) segments.push({ text: line.slice(cursor), strong: false });
  return segments;
}

/** Une ligne vide sépare deux paragraphes ; des lignes consécutives commençant par `*`, `-` ou `•` forment une liste. */
export function answerBlocks(text: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = [];
  let open = false;
  for (const line of text.split("\n")) {
    const bullet = BULLET.exec(line);
    const last = blocks.at(-1);
    if (bullet) {
      if (last?.kind === "list") last.items.push(inlineSegments(bullet[1]));
      else blocks.push({ kind: "list", items: [inlineSegments(bullet[1])] });
      open = false;
    } else if (!line.trim()) {
      open = false;
    } else if (open && last?.kind === "paragraph") {
      last.lines.push(inlineSegments(line));
    } else {
      blocks.push({ kind: "paragraph", lines: [inlineSegments(line)] });
      open = true;
    }
  }
  return blocks;
}
