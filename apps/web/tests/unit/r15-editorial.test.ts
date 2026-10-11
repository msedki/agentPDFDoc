/** R15-2 : textes et fonctions pures ; ces contrôles ne sont pas une preuve de rendu. */
import assert from "node:assert/strict";
import test from "node:test";
import * as warningHelpers from "../../src/lib/warnings.ts";
import * as jobHelpers from "../../src/lib/jobs-view.ts";
import * as reindexHelpers from "../../src/lib/reindex.ts";
import * as sessionHelpers from "../../src/lib/session.ts";
import * as textHelpers from "../../src/lib/ocr-overlay.ts";
import type { Block } from "../../src/lib/types.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const code = (file: string) => stripScriptComments(readSource(file));

test("les blocs sans provenance ou positions de texte valides sont annoncés comme écartés, pas indexés", () => {
  const texts = warningHelpers.groupedWarningTexts([
    { code: "ITEM_WITHOUT_PROVENANCE", page_index: 0 },
    { code: "INVALID_SOURCE_CHARSPAN", page_index: 1 },
  ]);
  assert.equal(texts.length, 2);
  for (const text of texts) {
    assert.match(text, /ni recherch|pas disponible pour la recherche/);
    assert.match(text, /Consultez la page originale dans le lecteur/);
    assert.doesNotMatch(text, /leur texte est indexé|s'ouvrent à la page/);
  }
});

test("la reprise de couche native ne promet pas une conservation intégrale du texte", () => {
  const [text] = warningHelpers.groupedWarningTexts([{ code: "STRUCTURED_FELL_BACK_TO_NATIVE", page_index: 3 }]);
  assert.match(text, /couche texte native a été utilisée/);
  assert.match(text, /ordre de lecture/);
  assert.doesNotMatch(text, /en entier|intégral|complet/);
});

test("le plafond de rendu décrit le texte disponible sans prétendre que toute la page a été interprétée", () => {
  const [text] = warningHelpers.groupedWarningTexts([{ code: "PDF_RENDER_LIMIT", page_index: 2 }]);
  assert.match(text, /^Rendu d'extraction limité, page 3 : /);
  assert.match(text, /budget de pixels/);
  assert.match(text, /texte extrait disponible/);
  assert.match(text, /Consultez la page originale/);
  assert.doesNotMatch(text, /sans description|PDF_RENDER_LIMIT|entier|reprenez|augmentez/);
});

test("les limites OCR distinguent le plafond de pixels de l'orientation non résolue, sans promettre une lecture", () => {
  const render = warningHelpers.groupedWarningTexts([{ code: "OCR_RENDER_LIMIT", page_index: 0 }])[0];
  assert.match(render, /plafond de pixels.*OCR/);
  assert.match(render, /texte extrait disponible/);
  assert.doesNotMatch(render, /sans description|augmentez|OCR_RENDER_LIMIT/);
  const orientation = warningHelpers.groupedWarningTexts([{ code: "OCR_ORIENTATION_UNRESOLVED", page_index: 1 }])[0];
  assert.match(orientation, /lecture OCR n'a pas été lancée/);
  assert.match(orientation, /zones.*orientation reste indéterminée/);
  assert.doesNotMatch(orientation, /redresser la page|essayez une rotation|reprenez/);
});

test("une faute native ou sa quarantaine ne promet pas une reprise des mêmes preuves", () => {
  const texts = warningHelpers.groupedWarningTexts([
    { code: "INGESTION_NATIVE_FAULT", page_index: 0 },
    { code: "EXTRACTION_QUARANTINED", page_index: 0 },
  ]);
  assert.equal(texts.length, 2);
  for (const text of texts) {
    assert.match(text, /ne peu[tv]ent? pas être|ne peut pas être/);
    assert.match(text, /diagnostic/);
    assert.match(text, /réindexez/);
    assert.doesNotMatch(text, /reprenez|supprimez|sans description/);
  }
});

test("une traduction locale ne réécrit jamais le message fourni par le serveur", () => {
  const message = "Le service indique cette limite précise.";
  for (const code of ["ITEM_WITHOUT_PROVENANCE", "INVALID_SOURCE_CHARSPAN", "STRUCTURED_FELL_BACK_TO_NATIVE", "PDF_RENDER_LIMIT", "OCR_RENDER_LIMIT", "OCR_ORIENTATION_UNRESOLVED", "INGESTION_NATIVE_FAULT", "EXTRACTION_QUARANTINED", "CODE_FUTUR"]) {
    assert.deepEqual(warningHelpers.groupedWarningTexts([{ code, message, page_index: 0 }]), [message]);
  }
});

test("l'avis de reprise groupée utilise le nombre accepté et accorde 0, 1 et plusieurs reprises", () => {
  const notice = (jobHelpers as Record<string, unknown>).resumePausedNotice;
  assert.equal(typeof notice, "function");
  const render = notice as (count: number) => string;
  assert.equal(render(0), "Aucune reprise d'indexation mise en file. Vérifiez les états dans le Suivi.");
  assert.equal(render(1), "1 reprise d'indexation mise en file ; son état s'affiche dans le Suivi.");
  assert.equal(render(4), "4 reprises d'indexation mises en file ; leur état s'affiche dans le Suivi.");
  for (const count of [0, 1, 4]) assert.doesNotMatch(render(count), /relancé|elles reprennent|ordre d'import/);
});

test("la reprise groupée lit response.resumed et ne fabrique pas un succès depuis le compteur avant clic", () => {
  const jobs = code("components/jobs-panel.tsx");
  assert.match(jobs, /const response = await api\.resumePaused\(\);\s*setModeNotice\(resumePausedNotice\(response\.resumed\)\)/);
  assert.doesNotMatch(jobs, /pausedCount === 1 \? "1 indexation relancée"/);
  assert.match(jobs, /finally \{ setPendingJob\(null\); \}/, "les échecs continuent de remonter à ActionButton");
});

test("l'extraction partielle décrit le texte disponible et la publication, même si toutes les pages sont traitées", () => {
  const notice = (jobHelpers as Record<string, unknown>).partialExtractionNotice;
  assert.equal(typeof notice, "function");
  const render = notice as (published: boolean) => string;
  assert.match(render(false), /terminée, non publiée/);
  assert.match(render(false), /texte extrait.*interrogeable.*publiez/);
  assert.match(render(true), /publiée.*texte extrait disponible/);
  for (const published of [false, true]) {
    assert.match(render(published), /limites signalées/);
    assert.doesNotMatch(render(published), /vérifiée|pages manquantes|limitées aux pages traitées/);
  }
  const jobs = code("components/jobs-panel.tsx");
  assert.match(jobs, /jobState === "ready_partial" && !superseded[^\n]*partialExtractionNotice\(published\)/);
  assert.match(jobs, /jobState === "ready_partial" && !published && !superseded[^\n]*api\.publishPartial\(job\.id\)/, "le choix explicite de publication reste exigé");
  assert.match(jobs, /"terminée, publication à décider"/);
  assert.doesNotMatch(jobs, /"vérifiée, publication à décider"/);
});

test("une recherche vide rapporte ce qui a été retrouvé, sans certifier une absence dans l'index", () => {
  const analysis = code("components/analysis-panel.tsx");
  const description = /title="Aucun passage retrouvé" description="([^"]+)"/.exec(analysis)?.[1];
  assert.ok(description, "le message attendu est réellement câblé dans l'état vide");
  assert.match(description, /^La recherche n'a retrouvé aucun passage dans ce périmètre\./);
  assert.match(description, /ne prouve pas l'absence de l'information/);
  assert.doesNotMatch(description, /Aucun passage indexé.*contient/);
  assert.match(analysis, /searchScope\?\.unindexed/, "la branche index incomplet est conservée");
});

test("les mêmes avertissements warning puis done sont dédoublonnés sans modifier leur message", () => {
  const merge = (warningHelpers as Record<string, unknown>).mergeQueryWarnings;
  assert.equal(typeof merge, "function");
  const combine = merge as (previous: unknown[], incoming: unknown[]) => unknown[];
  const first = { code: "limite", message: "Texte du serveur", identifier: "REF-A", details: { b: 2, a: 1 } };
  const reordered = { details: { a: 1, b: 2 }, identifier: "REF-A", message: "Texte du serveur", code: "limite" };
  const previous = combine([], [first, "Limite textuelle"]);
  const snapshot = structuredClone(previous);
  const result = combine(previous, [reordered, "Limite textuelle"]);
  assert.deepEqual(result, previous);
  assert.deepEqual(previous, snapshot, "la collection précédente n'est pas modifiée");
  assert.equal(warningHelpers.warningText(result[0]), "Texte du serveur");
});

test("des codes, références, détails ou messages différents restent des avertissements distincts", () => {
  const merge = (warningHelpers as Record<string, unknown>).mergeQueryWarnings;
  assert.equal(typeof merge, "function");
  const combine = merge as (previous: unknown[], incoming: unknown[]) => unknown[];
  const warnings = [
    { code: "a", message: "Même texte", identifier: "REF-A", details: { limit: 1 } },
    { code: "b", message: "Même texte", identifier: "REF-A", details: { limit: 1 } },
    { code: "a", message: "Autre texte", identifier: "REF-A", details: { limit: 1 } },
    { code: "a", message: "Même texte", identifier: "REF-B", details: { limit: 1 } },
    { code: "a", message: "Même texte", identifier: "REF-A", details: { limit: 2 } },
  ];
  assert.deepEqual(combine([], warnings), warnings);
  assert.deepEqual(combine(warnings, warnings), warnings);
  assert.equal(warningHelpers.warningText(warnings[0]), "Même texte", "les autres champs ne sont pas affichés");
});

test("les deux événements SSE alimentent le même dédoublonnage, sans modifier le périmètre", () => {
  const analysis = code("components/analysis-panel.tsx");
  const reducer = code("lib/query-history.ts");
  assert.match(analysis, /query => applyQueryEvent\(query, event\)/);
  assert.match(reducer, /case "warning": next\.warnings = mergeQueryWarnings\(query\.warnings, \[event\.data\.warning \?\? event\.data\]\)/);
  assert.match(reducer, /if \(Array\.isArray\(event\.data\.warnings\)\) next\.warnings = mergeQueryWarnings\(query\.warnings, event\.data\.warnings\)/);
  // R26 : les avis sont structurés (sources et valeurs signalées) ; seul leur texte contrôlé est affiché.
  assert.match(analysis, /<WarningNotices notices=\{warningNotices\(query\.warnings, query\.finishReason\)\}/, "le rendu affiche les textes contrôlés en regroupant la limite de génération");
  assert.match(analysis, /<WarningNotices notices=\{warningNotices\(search\.warnings \?\? \[\]\)\}/, "la recherche emploie les mêmes avis");
  assert.match(analysis, /<p>\{notice\.text\}<\/p>/);
  assert.doesNotMatch(analysis, /query\.warnings\.map\([^\n]*\{warning\}/, "les objets d'avertissement ne sont jamais rendus directement");
  const onEvent = /const onEvent =([\s\S]*?)const connect =/.exec(analysis)?.[1] ?? "";
  assert.ok(onEvent);
  assert.doesNotMatch(onEvent, /setScope\(|api\.query\(/, "aucun changement de scope ou redémarrage de génération au traitement d'événement");
});

test("les introductions ne promettent pas une source pour toute réponse, notamment une abstention", () => {
  const home = code("app/page.tsx");
  const analysis = code("components/analysis-panel.tsx");
  assert.doesNotMatch(home, /chaque réponse renvoie/);
  assert.match(home, /Ouvrez les sources citées pour vérifier/);
  assert.doesNotMatch(analysis, /La réponse cite ses passages/);
  assert.match(analysis, /Si la réponse cite des sources, ouvrez-les/);
});

test("le lecteur annonce une ouverture à la page et ne garantit un surlignage que si la position est connue", () => {
  const reader = code("components/pdf-viewer.tsx");
  const empty = /title="Aucun document ouvert" description="([^"]+)"/.exec(reader)?.[1];
  assert.ok(empty);
  assert.match(empty, /page concernée/);
  assert.match(empty, /surligné lorsque sa position est connue/);
  assert.doesNotMatch(empty, /à la page et au passage utilisés/);
});

test("les actions Analyser expliquent le choix de périmètre sans lancer automatiquement une question", () => {
  const reader = code("components/pdf-viewer.tsx");
  const analysis = code("components/analysis-panel.tsx");
  assert.match(reader, /« Analyser » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement/);
  assert.match(analysis, /Analyser la sélection[\s\S]*Le bouton « Analyser la sélection » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement/);
  const pageAction = /const setPageScope = \(\) => \{([\s\S]*?)\};/.exec(reader)?.[1] ?? "";
  assert.match(pageAction, /state\.setScope\(/);
  assert.doesNotMatch(pageAction, /api\.query\(|submit\(/);
  assert.match(reader, /sectionId: section\.id/);
  assert.match(reader, /wholeBlockSpan\(block/);
});

test("l'aide de réindexation ne demande pas d'attendre un traitement en pause ni annulé", () => {
  const helper = (reindexHelpers as Record<string, unknown>).reindexUnavailableReason;
  assert.equal(typeof helper, "function");
  const reason = helper as (state: string) => string;
  assert.match(reason("paused"), /en pause.*reprenez.*Suivi/);
  assert.doesNotMatch(reason("paused"), /une fois.*terminé/);
  assert.match(reason("cancelled"), /annulé.*importez de nouveau/);
  for (const state of ["queued", "extracting", "indexing"]) assert.match(reason(state), /une fois le traitement en cours terminé/);
  assert.match(reason("future"), /état actuel.*Suivi/);
  const tools = code("components/document-tools.tsx");
  assert.match(tools, /title=\{reindexable \? undefined : reindexUnavailableReason\(document\.state\)\}/);
  assert.match(tools, /const reindexableStates = \["ready", "ready_partial", "error"\]/, "les droits d'action existants ne sont pas étendus");
});

test("un texte extrait à précision page ne devient ni une absence de texte ni une couche OCR", () => {
  const source: Block = { id: "page-text", page_index: 0, text: "Texte conservé sans position", raw_text: "Texte conservé sans position", precision: "page", bbox: null, metadata: { extraction_method: "unknown", route: "regional_ocr", ocr_used: true } };
  const overlays = textHelpers.ocrOverlays([source]);
  assert.deepEqual(overlays, [], "la route et ocr_used ne constituent pas une provenance OCR");
  const available = (textHelpers as Record<string, unknown>).hasExtractedText;
  assert.equal(typeof available, "function");
  const hasText = available as (blocks: Block[]) => boolean;
  assert.equal(hasText([source]), true);
  assert.equal(hasText([{ ...source, raw_text: "  \n " }]), false);
  assert.equal(hasText([]), false);
  const caption = textHelpers.pageTextCaption as (page: Record<string, unknown>) => string;
  const base = { nativeText: false, blocksLoading: false, ocrRegions: 0 };
  assert.equal(caption({ ...base, extractedTextAvailable: hasText([source]) }), "Texte extrait disponible");
  assert.equal(caption({ ...base, blocksUnavailable: true }), "Texte extrait non vérifié");
  assert.equal(caption({ ...base, nativeText: true, blocksUnavailable: true }), "Texte natif");
  assert.equal(caption({ ...base, blocksLoading: true, extractedTextAvailable: true }), "Lecture de la page…");
  assert.equal(caption({ ...base, extractedTextAvailable: false }), "Aucun texte extrait");
  const reader = code("components/pdf-viewer.tsx");
  assert.match(reader, /extractedTextAvailable: hasExtractedText\(blocks\.data\?\.blocks \?\? \[\]\)/);
  assert.match(reader, /blocksUnavailable: blocks\.isError \|\| !provenanceReady \|\| Boolean\(binding\.error\)/);
});

test("un refus HTTP de session n'est pas annoncé comme une panne de connexion", () => {
  const gate = code("components/session-gate.tsx");
  assert.match(gate, /state\.kind === "unreachable"[^\n]*<h1 id="session-title">Ouverture de l'atelier impossible/);
  assert.match(gate, /PanelError title="Vérification de la session impossible" message=\{unreachableText/);
  assert.doesNotMatch(gate, /Service local injoignable/);
});

test("une copie refusée ou indisponible propose une copie manuelle sans prétendre en connaître la cause", async () => {
  const helper = (sessionHelpers as Record<string, unknown>).copySessionCommand;
  assert.equal(typeof helper, "function");
  const copy = helper as (command: string, clipboard?: { writeText: (command: string) => Promise<void> }) => Promise<{ copied: string | null; error: string }>;
  const commands: string[] = [];
  const command = "./rag.sh open";
  assert.deepEqual(await copy(command, { writeText: async value => { commands.push(value); } }), { copied: command, error: "" });
  assert.deepEqual(commands, [command], "la commande est copiée, jamais exécutée");
  for (const clipboard of [undefined, { writeText: async () => { throw new Error("refus privé non affiché"); } }]) {
    const result = await copy(command, clipboard);
    assert.equal(result.copied, null);
    assert.match(result.error, /Copie impossible.*sélectionnez la commande voulue.*manuellement/);
    assert.doesNotMatch(result.error, /refus privé|permission|navigateur|sécurité/);
  }
  const gate = code("components/session-gate.tsx");
  assert.match(gate, /await copySessionCommand\(command, navigator\.clipboard\)/);
  assert.match(gate, /copyError && <p[^>]*role="alert">\{copyError\}<\/p>/);
});
