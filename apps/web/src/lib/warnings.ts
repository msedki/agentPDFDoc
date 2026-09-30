/**
 * Texte d'un avertissement du service : son message, sinon une phrase qui
 * garde le code pour le diagnostic. Aucun autre champ de l'objet n'est affiché.
 */
export function warningText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const warning = value as { message?: unknown; code?: unknown };
    if (typeof warning.message === "string") return warning.message;
    if (typeof warning.code === "string") return `Le service signale une limite sans la décrire (code ${warning.code}).`;
  }
  return "Le service signale une limite sans la décrire.";
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

/** Refus HTTP sans message du service : le statut reste lisible et l'action possible est indiquée. */
export function httpFailureMessage(status: number): string {
  return status >= 500
    ? `Le service local a échoué (HTTP ${status}). Réessayez ; si l'échec persiste, consultez son journal : la commande .\\rag.ps1 logs en donne l'emplacement.`
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
export function readinessSentence(blockers: string[]): string {
  return `Préparation du poste incomplète : ${blockers.map(readinessBlockerText).join(", ")}. Les recherches et les questions qui en dépendent échouent tant que ces composants ne sont pas prêts. La commande .\\rag.ps1 doctor détaille chaque contrôle ; l'état est relu toutes les 10 secondes.`;
}
