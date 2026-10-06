import test from "node:test";
import assert from "node:assert/strict";
import { mergeQueryWarnings, queryWarningTexts } from "../../src/lib/warnings.ts";

const lengthNotice = "Réponse incomplète : la limite de longueur a été atteinte. Demandez une réponse plus concise ou détaillez un point précis dans le même périmètre.";
const lengthWarning = { code: "answer_length_limit", message: "Limite de génération atteinte ; réponse incomplète." };

test("la raison de fin seule suffit à signaler une réponse tronquée", () => {
  assert.deepEqual(queryWarningTexts([], "length"), [lengthNotice]);
  assert.deepEqual(queryWarningTexts([], "stop"), []);
  assert.deepEqual(queryWarningTexts([]), []);
});

test("le code de limite seul donne la même aide, même sans message du service", () => {
  assert.deepEqual(queryWarningTexts([lengthWarning]), [lengthNotice]);
  assert.deepEqual(queryWarningTexts([{ code: "answer_length_limit" }], "stop"), [lengthNotice]);
});

test("la raison de fin et les avertissements de limite répétés donnent un seul message", () => {
  const warnings = [lengthWarning, { code: "answer_length_limit", message: "Autre description de la même limite." }];
  assert.deepEqual(queryWarningTexts(warnings, "length"), [lengthNotice]);
  assert.deepEqual(queryWarningTexts(warnings), [lengthNotice]);
  assert.equal(warnings.length, 2, "le regroupement d'affichage ne modifie pas les preuves du service");
});

test("les limites indépendantes, les codes inconnus et les textes sûrs restent affichés", () => {
  assert.deepEqual(queryWarningTexts([
    { code: "context_fragments_excluded_by_budget", message: "Deux passages n'ont pas été retenus dans le contexte." },
    lengthWarning,
    { code: "future_limit", internal_details: "Détail interne non affichable" },
    "Vérifiez les valeurs dans le document.",
  ]), [
    "Deux passages n'ont pas été retenus dans le contexte.",
    lengthNotice,
    "Limite signalée par le service, sans description (code future_limit).",
    "Vérifiez les valeurs dans le document.",
  ]);
});

test("le regroupement au rendu conserve les données SSE et done fusionnées", () => {
  const warnings = mergeQueryWarnings([lengthWarning], [lengthWarning, { code: "citation_validation", message: "Une référence non enregistrée reste non cliquable." }]);
  assert.equal(warnings.length, 2);
  assert.deepEqual(queryWarningTexts(warnings, "length"), [lengthNotice, "Une référence non enregistrée reste non cliquable."]);
  assert.deepEqual(warnings[0], lengthWarning);
});

test("un avertissement d'une autre nature n'est pas assimilé à une limite de génération", () => {
  assert.deepEqual(queryWarningTexts([{ code: "context_limit", message: "Limite de longueur du contexte." }], "stop"), ["Limite de longueur du contexte."]);
});
