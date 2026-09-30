import { test } from "node:test";
import assert from "node:assert/strict";
import { groupedWarningTexts } from "../../src/lib/warnings.ts";

test("une limite répétée par zone devient un seul message avec ses pages, numérotées à partir de 1", () => {
  const warnings = [0, 1, 2, 5, 5].map(page_index => ({ code: "GRAPHIC_INTERPRETATION_UNAVAILABLE", page_index, block_id: `b-${page_index}` }));
  const texts = groupedWarningTexts(warnings);
  assert.equal(texts.length, 1);
  assert.equal(texts[0], "Schémas ou images non interprétés, pages 1, 2, 3, 6 (5 zones) : leur contenu n'est ni recherché ni cité ; le texte de ces pages l'est. Consultez la figure dans le lecteur.");
  assert.doesNotMatch(texts[0], /GRAPHIC_INTERPRETATION_UNAVAILABLE/);
});

test("chaque code connu garde son message ; un message fourni par le service et un code inconnu restent affichés", () => {
  const texts = groupedWarningTexts([
    { code: "PAGE_WITHOUT_EXTRACTED_TEXT", page_index: 1 },
    { code: "DOCLING_CONVERSION_FAILED", page_index: 10 },
    { code: "DOCLING_CONVERSION_FAILED", page_index: 11 },
    { code: "context_fragments_excluded_by_budget", message: "2 fragment(s) écarté(s)." },
    { code: "CODE_FUTUR" },
  ]);
  assert.deepEqual(texts, [
    "Pages sans texte extrait, page 2 : aucun texte n'y a été trouvé (page blanche, logo seul ou image non lue).",
    "Pages non converties, pages 11, 12 : leur texte n'a pas pu être extrait ; réindexez le document ou consultez le diagnostic du poste.",
    "2 fragment(s) écarté(s).",
    "Limite signalée par le service, sans description (code CODE_FUTUR).",
  ]);
});

test("une longue liste de pages est abrégée", () => {
  const texts = groupedWarningTexts(Array.from({ length: 12 }, (_, page_index) => ({ code: "GRAPHIC_INTERPRETATION_UNAVAILABLE", page_index })));
  assert.match(texts[0], /pages 1, 2, 3, 4, 5, 6, 7, 8 et 4 autres :/);
  assert.deepEqual(groupedWarningTexts(undefined), []);
});

test("la perte de texte de l'analyse de mise en page et sa reprise sont décrites sans code", () => {
  const texts = groupedWarningTexts([
    { code: "STRUCTURED_TEXT_LOSS", page_index: 6, text_layer_coverage: 0.008 },
    { code: "STRUCTURED_FELL_BACK_TO_NATIVE", page_index: 6, monotonic_vertical_order: false },
  ]);
  assert.equal(texts.length, 2);
  assert.match(texts[0], /^Texte écarté par l'analyse de mise en page, page 7 : /);
  assert.match(texts[1], /^Pages reprises depuis le texte intégré au PDF, page 7 : .*ordre de lecture/);
  for (const text of texts) assert.doesNotMatch(text, /STRUCTURED_/);
});
