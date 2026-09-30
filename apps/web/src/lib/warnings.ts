export function warningText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const warning = value as { message?: unknown; code?: unknown };
    if (typeof warning.message === "string") return warning.message;
    if (typeof warning.code === "string") return warning.code;
  }
  return "Le service signale une limite.";
}

const readinessLabels: Record<string, string> = {
  sqlite_unavailable: "Base documentaire illisible", sqlite_not_ready: "Base documentaire non vérifiée",
  embedding_not_ready: "Modèle de recherche absent", llm_tokenizer_not_ready: "Tokenizer du modèle absent",
  qdrant_not_ready: "Index vectoriel indisponible", ollama_not_ready: "Modèle de réponse indisponible",
  governor_not_ready: "Contrôle des ressources inactif",
};

export function readinessBlockerText(code: string): string {
  return readinessLabels[code] ?? code;
}
