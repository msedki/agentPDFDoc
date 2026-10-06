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

test("le préflight qui repère des caractères incertains dans le texte intégré au PDF est décrit, avec l'action possible", () => {
  // J8, L9 : avertissement émis par services/ingestion/preflight.py et docling_adapter.py (composant preflight_text)
  // pour la fixture « Unicode ligatures césures.pdf » ; le Suivi n'affichait que le code.
  const texts = groupedWarningTexts([
    { code: "PREFLIGHT_TEXT_MAPPING_UNCERTAIN", page_index: 0, component: "preflight_text" },
    { code: "PREFLIGHT_TEXT_MAPPING_UNCERTAIN", page_index: 2, component: "preflight_text" },
  ]);
  assert.deepEqual(texts, ["Caractères incertains dans le texte intégré au PDF, pages 1, 3 : des mots coupés en fin de ligne ou des caractères non reconnus y ont été repérés ; ces mots peuvent être mal indexés et échapper à la recherche. Vérifiez le passage dans le lecteur."]);
  assert.doesNotMatch(texts[0], /PREFLIGHT_|sans description/);
});

test("les deux limites de structure des tableaux sont décrites avec leur conséquence et l'action possible", () => {
  // Codes émis par table_coverage (services/ingestion/docling_adapter.py) pour un bloc de tableau, avec page et bloc,
  // sans message : le Suivi n'affichait que « sans description (code …) ».
  const texts = groupedWarningTexts([
    { code: "TABLE_CONTENT_COVERAGE_UNCERTAIN", page_index: 3, block_id: "t-1" },
    { code: "TABLE_WITHOUT_RELIABLE_CELLS", page_index: 0, block_id: "t-2" },
    { code: "TABLE_WITHOUT_RELIABLE_CELLS", page_index: 0, block_id: "t-3" },
    { code: "TABLE_WITHOUT_RELIABLE_CELLS", page_index: 4, block_id: "t-4" },
  ]);
  assert.deepEqual(texts, [
    "Tableaux réduits à leurs intitulés de lignes, page 4 : l'analyse de mise en page n'a reconnu qu'une colonne d'intitulés à gauche d'un tableau plus large ; les valeurs des autres colonnes peuvent manquer à la recherche et aux citations. Consultez le tableau dans le lecteur.",
    "Tableaux sans cellules reconnues, pages 1, 5 (3 zones) : l'analyse de mise en page a repéré un tableau sans en reconnaître les cellules ; son contenu peut manquer à la recherche et aux citations. Consultez le tableau dans le lecteur.",
  ]);
  for (const text of texts) assert.doesNotMatch(text, /TABLE_|sans description/);
});

test("les positions incohérentes avec le repère de la page sont décrites, avec leur conséquence et l'action possible", () => {
  // Codes de services/ingestion/geometry.py repris en avertissements par page (docling_adapter.py, conversion des
  // boîtes du parseur) : l'élément reste indexé sans position fiable, ou une cellule OCR est écartée.
  const texts = groupedWarningTexts([
    { code: "GEOMETRY_FRAME_MISMATCH", page_index: 1 },
    { code: "GEOMETRY_OUTSIDE_PAGE", page_index: 2, component: "parser_cell" },
    { code: "GEOMETRY_OUTSIDE_PAGE", page_index: 2, component: "parser_cell" },
    { code: "UNKNOWN_COORDINATE_ORIGIN", page_index: 0 },
  ]);
  assert.equal(texts.length, 3);
  assert.match(texts[0], /^Repère de page incohérent, page 2 : /);
  assert.match(texts[1], /^Éléments placés hors de la page, page 3 \(2 zones\) : /);
  assert.match(texts[2], /^Origine des coordonnées inconnue, page 1 : /);
  for (const text of texts) {
    assert.match(text, /Vérifiez le passage dans le lecteur\.$/);
    assert.doesNotMatch(text, /GEOMETRY_|COORDINATE_|sans description/);
  }
});

test("une faible confiance OCR désigne les mots ou cellules signalés sans laisser croire que les autres sont exacts", () => {
  // R26 : sur la fixture DA-P02, l'OCR rend « + » pour « ± », « N-m » pour « N·m », « DA-PO2 » et « CCO » sans
  // OCR_WORD_LOW_CONFIDENCE, alors que des « DA-P02 » corrects sont signalés. Codes émis sans message par
  // services/ingestion/docling_adapter.py : le texte affiché est celui de l'interface.
  const texts = groupedWarningTexts([
    { code: "OCR_WORD_LOW_CONFIDENCE", page_index: 0, count: 2, minimum_confidence_required: 0.8 },
    { code: "OCR_CELL_LOW_CONFIDENCE", page_index: 2 },
  ]);
  assert.equal(texts.length, 2);
  assert.match(texts[0], /^Mots lus par OCR avec une faible confiance, page 1 : vérifiez ces mots sur la page originale/);
  assert.match(texts[1], /^Cellules de tableau lues par OCR avec une faible confiance, page 3 : vérifiez ces cellules sur la page originale/);
  assert.match(texts[0], /L'absence d'alerte ne garantit pas que les autres mots soient exacts : /);
  assert.match(texts[1], /L'absence d'alerte ne garantit pas que les autres cellules soient exactes : /);
  for (const text of texts) {
    assert.match(text, /signes, unités et références peuvent être mal lus \(± lu \+, N·m lu N-m, 0 lu O\)\.$/);
    assert.equal(text.match(/page originale/g)?.length, 1, "la page originale n'est nommée qu'une fois");
    assert.doesNotMatch(text, /LOW_CONFIDENCE|sans description|fiable|sont exact/);
  }
});
