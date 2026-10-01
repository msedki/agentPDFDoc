import assert from "node:assert/strict";
import test from "node:test";
import { answerBlocks, inlineSegments } from "../../src/lib/answer-format.ts";

const plain = (text: string) => ({ text, strong: false });
const strong = (text: string) => ({ text, strong: true });

test("bold pairs become strong segments; a lone or still open marker stays literal", () => {
  assert.deepEqual(inlineSegments("La pression est de **3,1 bar** [S001]."), [plain("La pression est de "), strong("3,1 bar"), plain(" [S001].")]);
  assert.deepEqual(inlineSegments("3 * 4 et **ouvert"), [plain("3 * 4 et **ouvert")]);
  assert.deepEqual(inlineSegments("**[S001]** :"), [strong("[S001]"), plain(" :")]);
});

test("the real R2 answer shape gives paragraphs and one bullet list without asterisks", () => {
  // Forme de la réponse réelle du 01/10 (R2) : gras, ligne vide, puces « *   ».
  const text = "La pression nominale de DA-P01 est de **3.1 bar**.\n\nCette affirmation repose sur la preuve suivante :\n*   **[S001]** : le texte l'indique.\n*   [S004] écarte DA-P010.\n\nAucune contradiction.";
  const blocks = answerBlocks(text);
  assert.deepEqual(blocks.map(block => block.kind), ["paragraph", "paragraph", "list", "paragraph"]);
  assert.deepEqual(blocks[2], { kind: "list", items: [[strong("[S001]"), plain(" : le texte l'indique.")], [plain("[S004] écarte DA-P010.")]] });
  const rendered = JSON.stringify(blocks);
  assert.doesNotMatch(rendered, /\*\*/);
});

test("consecutive lines stay in one paragraph, markup stays text and a dash inside a line is not a bullet", () => {
  assert.deepEqual(answerBlocks("Ligne un\nLigne deux - suite"), [{ kind: "paragraph", lines: [[plain("Ligne un")], [plain("Ligne deux - suite")]] }]);
  assert.deepEqual(answerBlocks("<img src=x onerror=alert(1)>"), [{ kind: "paragraph", lines: [[plain("<img src=x onerror=alert(1)>")]] }]);
  assert.deepEqual(answerBlocks(""), []);
});
