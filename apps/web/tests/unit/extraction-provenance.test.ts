/**
 * R26-UI-01 : méthode d'extraction d'une source ou d'une citation (contrat R26-OCR-01, champ `extraction_methods`).
 * Absence du champ (citation ou événement antérieurs au 2026-10-06) = inconnue, jamais native.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { extractionBadge, OCR_MISREADINGS, sourceExtractionMethods, withExtractionLabel } from "../../src/lib/extraction-provenance.ts";
import { groupedWarningTexts } from "../../src/lib/warnings.ts";

test("la liste du service est relue sans doublon ; un champ absent, vide ou hors vocabulaire vaut « inconnue »", () => {
  assert.deepEqual(sourceExtractionMethods({ extraction_methods: ["ocr", "native", "ocr"] }), ["native", "ocr"]);
  assert.deepEqual(sourceExtractionMethods({}), ["unknown"]);
  assert.deepEqual(sourceExtractionMethods({ extraction_methods: [] }), ["unknown"]);
  assert.deepEqual(sourceExtractionMethods({ extraction_methods: "ocr" }), ["unknown"]);
  assert.deepEqual(sourceExtractionMethods({ extraction_methods: ["native", "vlm", 3] }), ["native", "unknown"]);
});

test("OCR seul, OCR partiel, méthode inconnue ou texte natif donnent chacun un badge distinct ou aucun", () => {
  const ocr = extractionBadge({ extraction_methods: ["ocr"] });
  assert.equal(ocr?.label, "Lu par OCR");
  assert.equal(ocr?.tone, "warning");
  for (const methods of [["mixed"], ["native", "ocr"], ["mixed", "ocr"], ["ocr", "unknown"]]) {
    assert.equal(extractionBadge({ extraction_methods: methods })?.label, "En partie lu par OCR", methods.join("+"));
  }
  for (const source of [{}, { extraction_methods: ["unknown"] }, { extraction_methods: ["native", "unknown"] }]) {
    const badge = extractionBadge(source);
    assert.equal(badge?.label, "Méthode d'extraction inconnue", JSON.stringify(source));
    assert.equal(badge?.tone, "neutral");
    assert.match(badge?.title ?? "", /a pu être lu par OCR/);
    assert.match(badge?.title ?? "", /citation enregistrée ou document indexé avant l'ajout de cette information/);
    assert.doesNotMatch(badge?.title ?? "", /antérieurs à cette information/);
  }
  assert.equal(extractionBadge({ extraction_methods: ["native"] }), null, "aucun badge pour un texte natif");
});

test("l'info-bulle d'un texte lu par OCR reprend la phrase des alertes de faible confiance", () => {
  for (const methods of [["ocr"], ["mixed"]]) {
    const title = extractionBadge({ extraction_methods: methods })?.title ?? "";
    assert.ok(title.includes(OCR_MISREADINGS), title);
    assert.match(title, /même sans alerte de faible confiance/);
    assert.match(title, /comparez-les à la page originale\.$/);
  }
  const [warning] = groupedWarningTexts([{ code: "OCR_WORD_LOW_CONFIDENCE", page_index: 0 }]);
  assert.ok(warning.includes(OCR_MISREADINGS), "une seule formulation pour l'alerte et le badge");
});

test("le titre d'une citation nomme la méthode d'extraction lorsqu'elle appelle une vérification", () => {
  assert.equal(withExtractionLabel("Ouvrir Procédure.pdf, page 3", { extraction_methods: ["ocr"] }), "Ouvrir Procédure.pdf, page 3 · Lu par OCR");
  assert.equal(withExtractionLabel("Ouvrir Procédure.pdf, page 3", {}), "Ouvrir Procédure.pdf, page 3 · Méthode d'extraction inconnue");
  assert.equal(withExtractionLabel("Ouvrir Procédure.pdf, page 3", { extraction_methods: ["native"] }), "Ouvrir Procédure.pdf, page 3");
});
