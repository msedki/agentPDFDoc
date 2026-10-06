import test from "node:test";
import assert from "node:assert/strict";
import { mergeQueryWarnings, queryWarningTexts, warningNotices } from "../../src/lib/warnings.ts";

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

// R26 (contrat packages/contracts/contracts.json, query_events.warning_data) : messages rédigés par le service, qui font foi.
const ocrA = { code: "ocr_evidence", document_id: "doc-a", document_name: "DA-P02.pdf", extraction_methods: ["ocr"], source_ids: ["S001", "S003"], message: "Passages de « DA-P02.pdf » lus par OCR : vérifiez-les sur la page originale." };
const ocrB = { code: "ocr_evidence", document_id: "doc-b", document_name: "QV-01.pdf", extraction_methods: ["mixed"], source_ids: ["S002"], message: "Passages de « QV-01.pdf » en partie lus par OCR : vérifiez-les sur la page originale." };

test("ocr_evidence s'affiche une fois par document, même répété dans done avec un ordre de clés différent", () => {
  const repeated = { message: ocrA.message, source_ids: ["S001", "S003"], extraction_methods: ["ocr"], document_name: "DA-P02.pdf", document_id: "doc-a", code: "ocr_evidence" };
  const merged = mergeQueryWarnings(mergeQueryWarnings([], [ocrA]), [repeated, ocrB, { ...ocrA, source_ids: ["S001"] }]);
  assert.equal(merged.filter(warning => typeof warning === "object" && warning.code === "ocr_evidence").length, 2);
  // La dernière version reçue (done) remplace la précédente à la même place.
  assert.deepEqual(merged[0], { ...ocrA, source_ids: ["S001"] });
  const notices = warningNotices(merged);
  assert.deepEqual(notices.map(notice => notice.text), [ocrA.message, ocrB.message]);
  assert.deepEqual(notices.map(notice => notice.sourceIds), [["S001"], ["S002"]]);
  // POST /search : un avertissement par document, source_ids vide ; un doublon éventuel reste regroupé au rendu.
  assert.deepEqual(warningNotices([{ ...ocrA, source_ids: [] }, { ...ocrA, source_ids: [] }]).map(notice => [notice.text, notice.sourceIds]), [[ocrA.message, []]]);
});

test("une réponse sans citation valide et ses identifiants écrits sans crochets forment un seul avertissement", () => {
  const without = { code: "answer_without_valid_citation", message: "La réponse ne contient aucune citation valide entre crochets." };
  const mentioned = { code: "source_id_mentioned_without_citation", source_ids: ["S001", "S004"], message: "La réponse nomme S001 et S004 sans crochets." };
  const notices = warningNotices([without, { code: "context_fragments_excluded_by_budget", message: "Deux passages n'ont pas été retenus." }, mentioned]);
  assert.equal(notices.length, 2);
  assert.equal(notices[0].text, `${without.message} ${mentioned.message}`);
  assert.deepEqual(notices[0].sourceIds, ["S001", "S004"]);
  assert.equal(notices[1].text, "Deux passages n'ont pas été retenus.");
  assert.deepEqual(warningNotices([mentioned]).map(notice => notice.text), [mentioned.message], "le second code seul garde son message");
  // m7 : ordre inverse (identifiants nommés reçus avant l'absence de citation) : même avis, même ordre de lecture.
  const reversed = warningNotices([mentioned, without]);
  assert.deepEqual(reversed.map(notice => [notice.text, notice.sourceIds]), [[`${without.message} ${mentioned.message}`, ["S001", "S004"]]]);
});

test("les deux contrôles de valeurs gardent le message du service et listent chaque valeur avec ses sources", () => {
  const misattributed = { code: "cited_value_not_in_cited_sources", message: "Valeur absente des sources citées dans sa phrase mais présente dans d'autres sources retenues : 2.7 bar (citée S001, présente dans S002). Vérifiez sa source avant de l'utiliser.",
    values: [{ value: "2.7 bar", number: "2.7", unit: "bar", cited_source_ids: ["S001"], holder_source_ids: ["S002"] }] };
  const absent = { code: "value_not_in_context", message: "Valeurs absentes de toutes les sources transmises au modèle : 14 N·m et 3 %. Elles peuvent avoir été calculées, déduites ou mal reprises ; vérifiez-les avant de les utiliser.",
    values: [{ value: "14 N·m", number: "14", unit: "N·m", cited_source_ids: ["S003"] }, { value: "3 %", number: "3", unit: "%", cited_source_ids: [] }, { number: "sans valeur affichable" }] };
  const [first, second] = warningNotices([misattributed, absent]);
  // m5 : le message énumère déjà ces valeurs ; l'avis n'y ajoute que les sources à ouvrir, sans répéter le texte.
  assert.equal(first.text, misattributed.message);
  assert.deepEqual(first.values, []);
  assert.deepEqual(first.sourceIds, ["S001", "S002"]);
  assert.equal(second.text, absent.message);
  assert.deepEqual(second.values, []);
  assert.deepEqual(second.sourceIds, ["S003"]);
});

test("un code inconnu porteur d'un message l'affiche tel quel, sans détail ni promesse ajoutés", () => {
  const mismatch = { code: "dense_identity_mismatch", document_ids: ["doc-a"], document_names: ["DA-P02.pdf"], message: "L'index vectoriel de « DA-P02.pdf » ne correspond pas au modèle de recherche actif : réindexez ce document." };
  assert.deepEqual(warningNotices([mismatch]).map(notice => [notice.text, notice.sourceIds, notice.values]), [[mismatch.message, [], []]]);
  assert.deepEqual(queryWarningTexts([mismatch, ocrA]), [mismatch.message, ocrA.message]);
});

test("au-delà des six valeurs que le message énumère, les suivantes sont listées avec leurs sources", () => {
  // services/api/claims.py, _listing(limit=6) : six valeurs écrites, puis « et N autres ».
  const values = Array.from({ length: 8 }, (_, index) => ({ value: `${index + 1}.5 bar`, number: `${index + 1}.5`, unit: "bar", cited_source_ids: [`S00${index + 1}`], holder_source_ids: ["S009"] }));
  const [notice] = warningNotices([{ code: "cited_value_not_in_cited_sources", values, message: "Valeurs absentes des sources citées … et 2 autres. Vérifiez la source de chaque valeur avant de les utiliser." }]);
  assert.deepEqual(notice.values, [{ value: "7.5 bar", citedSourceIds: ["S007"], holderSourceIds: ["S009"] }, { value: "8.5 bar", citedSourceIds: ["S008"], holderSourceIds: ["S009"] }]);
  assert.deepEqual(notice.sourceIds, ["S001", "S009", "S002", "S003", "S004", "S005", "S006", "S007", "S008"]);
});
