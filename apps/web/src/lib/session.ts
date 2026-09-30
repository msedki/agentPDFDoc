/**
 * Session locale du poste (W011). Le navigateur ne connaît jamais le jeton de session
 * (cookie HttpOnly) ; il relit seulement le jeton anti-falsification, lisible, pour
 * l'envoyer dans X-CSRF-Token sur les requêtes qui modifient.
 */

export type SessionEndReason = "session_required" | "session_expired" | "session_closed" | "link_invalid";
export type SessionState = {
  authenticated: boolean; method: "session" | "control_token"; environment: "development" | "production";
  idle_timeout_minutes: number; created_at?: string; idle_expires_at?: string; absolute_expires_at?: string;
};

export const SESSION_ENDED_EVENT = "rag:session-ended";
export const OPEN_COMMAND = ".\\rag.ps1 open";
const CSRF_COOKIES = ["__Host-rag_csrf", "rag_csrf"];

/** Jeton CSRF lu dans une chaîne `document.cookie` ; le nom préfixé de la production l'emporte. */
export function csrfFromCookies(cookies: string): string | null {
  const values = new Map<string, string>();
  for (const part of cookies.split(";")) {
    const separator = part.indexOf("=");
    if (separator < 1) continue;
    values.set(part.slice(0, separator).trim(), part.slice(separator + 1).trim());
  }
  for (const name of CSRF_COOKIES) {
    const value = values.get(name);
    if (value) return decodeURIComponent(value);
  }
  return null;
}

export function currentCsrfToken(): string | null {
  return typeof document === "undefined" ? null : csrfFromCookies(document.cookie);
}

export function isSessionFailure(code: string): code is "session_required" | "session_expired" {
  return code === "session_required" || code === "session_expired";
}

/** Le serveur redirige ici un lien d'ouverture refusé (`?session=lien-invalide`). */
export function linkInvalidFromSearch(search: string): boolean {
  return new URLSearchParams(search).get("session") === "lien-invalide";
}

export function announceSessionEnd(reason: SessionEndReason): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent<SessionEndReason>(SESSION_ENDED_EVENT, { detail: reason }));
}

export function sessionScreen(reason: SessionEndReason): { title: string; body: string } {
  switch (reason) {
    case "session_required":
      return { title: "Session requise",
        body: "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Dans PowerShell, depuis le dossier du projet, lancez la commande ci-dessous : elle ouvre l'atelier dans un nouvel onglet." };
    case "session_expired":
      return { title: "Session expirée",
        body: "La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier avec la commande ci-dessous ; documents, index et conversations enregistrés restent intacts." };
    case "session_closed":
      return { title: "Session fermée",
        body: "La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier avec la commande ci-dessous." };
    case "link_invalid":
      return { title: "Lien d'ouverture expiré ou déjà utilisé",
        body: "Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau avec la commande ci-dessous." };
  }
}
