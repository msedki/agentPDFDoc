import { knownLauncherCommands, launcherText, type LauncherCommands } from "./launcher.ts";
import type { ApiWarning } from "./types.ts";

/**
 * Texte d'un avertissement du service : son message, sinon une phrase qui
 * garde le code pour le diagnostic. Aucun autre champ de l'objet n'est affiché.
 */
export function warningText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const warning = value as { message?: unknown; code?: unknown };
    if (typeof warning.message === "string") return warning.message;
    if (typeof warning.code === "string") return `Limite signalée par le service, sans description (code ${warning.code}).`;
  }
  return "Limite signalée par le service, sans description.";
}

/** Identité d'un avertissement JSON : l'ordre des clés ne distingue pas deux copies du même événement. */
function warningKey(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(warningKey).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map(key => `${JSON.stringify(key)}:${warningKey(record[key])}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? String(value);
}

/** Le SSE puis `done` peuvent livrer le même avertissement ; ses données distinctes restent conservées. */
export function mergeQueryWarnings(previous: ApiWarning[], incoming: unknown[]): ApiWarning[] {
  const result: ApiWarning[] = [];
  const seen = new Set<string>();
  for (const value of [...previous, ...incoming]) {
    const warning = typeof value === "string" || value && typeof value === "object" && !Array.isArray(value)
      ? value as ApiWarning : warningText(value);
    const key = warningKey(warning);
    if (!seen.has(key)) { seen.add(key); result.push(warning); }
  }
  return result;
}

/** La raison de fin et le code du service décrivent la même coupure ; les autres limites restent distinctes. */
export function queryWarningTexts(warnings: unknown[], finishReason?: string): string[] {
  const lengthNotice = "Réponse incomplète : la limite de longueur a été atteinte. Demandez une réponse plus concise ou détaillez un point précis dans le même périmètre.";
  const texts: string[] = finishReason === "length" ? [lengthNotice] : [];
  for (const warning of warnings) {
    if (warning && typeof warning === "object" && "code" in warning && warning.code === "answer_length_limit") {
      if (!texts.includes(lengthNotice)) texts.push(lengthNotice);
    } else texts.push(warningText(warning));
  }
  return texts;
}

/**
 * Limites d'extraction (codes de `services/ingestion`) : intitulé et conséquence pour
 * l'utilisateur. Un même code répété par zone est regroupé avec ses pages.
 */
const ingestionWarnings: Record<string, { title: string; consequence: string }> = {
  GRAPHIC_INTERPRETATION_UNAVAILABLE: { title: "Schémas ou images non interprétés", consequence: "leur contenu n'est ni recherché ni cité ; le texte de ces pages l'est. Consultez la figure dans le lecteur." },
  PAGE_WITHOUT_EXTRACTED_TEXT: { title: "Pages sans texte extrait", consequence: "aucun texte n'y a été trouvé (page blanche, logo seul ou image non lue)." },
  DOCUMENT_WITHOUT_TEXT: { title: "Document sans texte extrait", consequence: "aucune page n'apporte de texte recherchable." },
  DOCLING_CONVERSION_FAILED: { title: "Pages non converties", consequence: "leur texte n'a pas pu être extrait ; réindexez le document ou consultez le diagnostic du poste." },
  PAGE_GROUP_RETRIED_BY_PAGE: { title: "Pages retraitées une à une", consequence: "un groupe de pages a échoué et a été repris page par page." },
  NATIVE_QUALITY_FAILED: { title: "Couche texte native peu fiable", consequence: "le texte intégré au PDF ne passait pas le contrôle de qualité." },
  NATIVE_ESCALATED_TO_STRUCTURED: { title: "Pages relues par l'analyse de mise en page", consequence: "leur couche texte native ne passait pas le contrôle de qualité." },
  STRUCTURED_TEXT_LOSS: { title: "Texte écarté par l'analyse de mise en page", consequence: "une partie du texte intégré au PDF manquait après l'analyse ; si la relecture directe n'a pas pu le reprendre, ce texte n'est ni recherché ni cité." },
  STRUCTURED_FELL_BACK_TO_NATIVE: { title: "Pages reprises depuis le texte intégré au PDF", consequence: "une partie du texte intégré au PDF manquait après l'analyse ; la couche texte native a été utilisée pour cette page. L'ordre de lecture des colonnes ou tableaux peut différer ; vérifiez les passages dans le lecteur." },
  OCR_WORD_LOW_CONFIDENCE: { title: "Mots lus par OCR avec une faible confiance", consequence: "vérifiez les valeurs dans le lecteur avant de les utiliser." },
  OCR_CELL_LOW_CONFIDENCE: { title: "Cellules de tableau lues par OCR avec une faible confiance", consequence: "vérifiez les valeurs dans le lecteur avant de les utiliser." },
  OCR_PRINTED_CELL_UNRESOLVED: { title: "Cellules de tableau non lues", consequence: "leur contenu manque dans l'index ; consultez le tableau dans le lecteur." },
  OCR_NO_RECOGNIZED_CELLS: { title: "Aucun texte reconnu par l'OCR", consequence: "la zone numérisée n'apporte pas de texte recherchable." },
  OCR_ORIENTATION_UNRESOLVED: { title: "Orientation OCR non déterminée", consequence: "la lecture OCR n'a pas été lancée dans les zones dont l'orientation reste indéterminée ; consultez la page originale dans le lecteur." },
  // Structure d'un bloc de tableau (table_coverage, docling_adapter.py) : une seule colonne d'intitulés de lignes, à
  // gauche d'un cadre nettement plus large ; ou un tableau sans cellule (son bloc reste alors sans texte) ou sans colonne.
  TABLE_CONTENT_COVERAGE_UNCERTAIN: { title: "Tableaux réduits à leurs intitulés de lignes", consequence: "l'analyse de mise en page n'a reconnu qu'une colonne d'intitulés à gauche d'un tableau plus large ; les valeurs des autres colonnes peuvent manquer à la recherche et aux citations. Consultez le tableau dans le lecteur." },
  TABLE_WITHOUT_RELIABLE_CELLS: { title: "Tableaux sans cellules reconnues", consequence: "l'analyse de mise en page a repéré un tableau sans en reconnaître les cellules ; son contenu peut manquer à la recherche et aux citations. Consultez le tableau dans le lecteur." },
  OCR_REGION_ISOLATION_LIMIT: { title: "Zones numérisées non isolées", consequence: "une partie de la page n'a pas été soumise à l'OCR." },
  ITEM_WITHOUT_PROVENANCE: { title: "Éléments sans provenance vérifiable", consequence: "leur texte n'est pas disponible pour la recherche et les citations. Consultez la page originale dans le lecteur." },
  INVALID_SOURCE_CHARSPAN: { title: "Positions de texte incohérentes", consequence: "certains passages ont été écartés parce que leurs positions dans le texte sont incohérentes ; ils ne sont ni recherchés ni cités. Consultez la page originale dans le lecteur." },
  PDF_RENDER_LIMIT: { title: "Rendu d'extraction limité", consequence: "le budget de pixels a limité le rendu et certaines zones n'ont pas été lues. Les recherches utilisent uniquement le texte extrait disponible. Consultez la page originale dans le lecteur." },
  OCR_RENDER_LIMIT: { title: "Rendu OCR limité", consequence: "une région dépasse le plafond de pixels réservé à l'OCR ; sa lecture n'a pas été effectuée. Les recherches utilisent uniquement le texte extrait disponible. Consultez la page originale dans le lecteur." },
  INGESTION_NATIVE_FAULT: { title: "Arrêt du composant d'extraction", consequence: "cette extraction ne peut pas être publiée ni réutilisée après une erreur native. Consultez le diagnostic du poste pour corriger la cause, puis réindexez le document." },
  EXTRACTION_QUARANTINED: { title: "Extraction mise en quarantaine", consequence: "ses preuves sont conservées mais ne peuvent pas être réutilisées après une erreur native. Consultez le diagnostic du poste pour corriger la cause, puis réindexez le document." },
  // Repère géométrique (services/ingestion/geometry.py), repris en avertissement par page à la conversion des boîtes
  // du parseur (docling_adapter.py) : l'élément reste indexé sans position fiable, ou une cellule OCR est écartée.
  GEOMETRY_FRAME_MISMATCH: { title: "Repère de page incohérent", consequence: "les positions données par l'analyse de mise en page ne correspondent pas aux dimensions de la page ; des passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur." },
  GEOMETRY_OUTSIDE_PAGE: { title: "Éléments placés hors de la page", consequence: "des positions données par l'analyse de mise en page sortent du cadre de la page ; ces passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur." },
  UNKNOWN_COORDINATE_ORIGIN: { title: "Origine des coordonnées inconnue", consequence: "l'analyse de mise en page n'a pas indiqué comment placer ses éléments sur la page ; des passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur." },
  // Préflight PDFium (preflight.py) : texte de page contenant \x02 ou les non-caractères U+FFFE, U+FFFF. Sur la fixture
  // « Unicode ligatures césures.pdf », get_text_range() (pypdfium2 5.13.0) rend U+FFFE à la césure, sans \x02.
  PREFLIGHT_TEXT_MAPPING_UNCERTAIN: { title: "Caractères incertains dans le texte intégré au PDF", consequence: "des mots coupés en fin de ligne ou des caractères non reconnus y ont été repérés ; ces mots peuvent être mal indexés et échapper à la recherche. Vérifiez le passage dans le lecteur." },
};

function pagesPhrase(pages: number[]): string {
  if (!pages.length) return "";
  const shown = pages.slice(0, 8).join(", ") + (pages.length > 8 ? ` et ${pages.length - 8} autres` : "");
  return pages.length === 1 ? `page ${shown}` : `pages ${shown}`;
}

/**
 * Avertissements d'un traitement regroupés par code : un seul message par type de limite,
 * avec le nombre de zones et les pages (numérotées à partir de 1). Les messages fournis
 * par le service sont conservés tels quels ; un code inconnu reste cité pour le diagnostic.
 */
export function groupedWarningTexts(warnings: unknown[] | undefined): string[] {
  const groups = new Map<string, { count: number; pages: Set<number> }>();
  const texts: string[] = [];
  for (const value of warnings ?? []) {
    const warning = value && typeof value === "object" ? value as { code?: unknown; message?: unknown; page_index?: unknown } : null;
    const code = typeof warning?.code === "string" ? warning.code : null;
    if (!code || !Object.hasOwn(ingestionWarnings, code) || typeof warning?.message === "string") {
      const text = warningText(value);
      if (!texts.includes(text)) texts.push(text);
      continue;
    }
    const group = groups.get(code) ?? { count: 0, pages: new Set<number>() };
    group.count++;
    if (typeof warning?.page_index === "number") group.pages.add(warning.page_index + 1);
    groups.set(code, group);
  }
  const grouped = [...groups].map(([code, group]) => {
    const { title, consequence } = ingestionWarnings[code];
    const pages = pagesPhrase([...group.pages].sort((left, right) => left - right));
    const zones = group.count > 1 && group.count !== group.pages.size ? ` (${group.count} zones)` : "";
    return `${title}${pages ? `, ${pages}` : ""}${zones} : ${consequence}`;
  });
  return [...grouped, ...texts];
}

const readinessLabels: Record<string, string> = {
  sqlite_unavailable: "Base documentaire illisible", sqlite_not_ready: "Base documentaire non vérifiée",
  embedding_not_ready: "Modèle de recherche absent", llm_tokenizer_not_ready: "Tokenizer du modèle de réponse absent",
  qdrant_not_ready: "Index vectoriel indisponible", ollama_not_ready: "Modèle de réponse indisponible",
  governor_not_ready: "Contrôle des ressources inactif",
};

export function readinessBlockerText(code: string): string {
  return Object.hasOwn(readinessLabels, code) ? readinessLabels[code] : `Composant local non prêt (code ${code})`;
}

/** Service injoignable (requête sans réponse) : la commande qui dit s'il est démarré. */
export function serviceUnreachableMessage(commands: LauncherCommands | null = knownLauncherCommands()): string {
  return `Le service local ne répond pas. Vérifiez qu'il est démarré (${launcherText("status", commands)}), puis réessayez.`;
}

/** Refus HTTP sans message du service : le statut reste lisible et l'action possible est indiquée. */
export function httpFailureMessage(status: number, commands: LauncherCommands | null = knownLauncherCommands()): string {
  return status >= 500
    ? `Le service local a échoué (HTTP ${status}). Réessayez ; si l'échec persiste, consultez son journal : la commande ${launcherText("logs", commands)} en donne l'emplacement.`
    : `Le service local a refusé la demande (HTTP ${status}).`;
}

/** Info-bulle de l'état des services dans la barre supérieure, cohérente avec le bandeau de contexte. */
export function serviceDetail(input: { failed: boolean; error?: string; ready?: boolean; blockers: string[]; pendingDocuments: number }): string | undefined {
  if (input.failed) return input.error;
  if (input.ready !== true) return input.blockers.length ? `Non prêts : ${input.blockers.map(readinessBlockerText).join(", ")}.` : "Le service n'a pas confirmé que ses composants sont prêts.";
  if (input.pendingDocuments > 0) return input.pendingDocuments === 1 ? "1 document attend son indexation : il n'est pas encore interrogeable." : `${input.pendingDocuments} documents attendent leur indexation : ils ne sont pas encore interrogeables.`;
  return "Base documentaire, modèles, index vectoriel et contrôle des ressources prêts.";
}

/** Message du bandeau de contexte quand `/readiness` signale des composants non prêts. */
export function readinessSentence(blockers: string[], commands: LauncherCommands | null = knownLauncherCommands()): string {
  return `Préparation du poste incomplète : ${blockers.map(readinessBlockerText).join(", ")}. Les recherches et les questions qui en dépendent échouent tant que ces composants ne sont pas prêts. La commande ${launcherText("doctor", commands)} détaille chaque contrôle ; l'état est relu toutes les 10 secondes.`;
}
