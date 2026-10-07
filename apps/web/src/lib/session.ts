/**
 * Session locale du poste (W011). Le navigateur ne connaît jamais le jeton de session
 * (cookie HttpOnly) ; il relit seulement le jeton anti-falsification, lisible, pour
 * l'envoyer dans X-CSRF-Token sur les requêtes qui modifient.
 */
import { knownLauncherCommands, launcherInstallation, launcherShell, launcherText, openCommandChoices, type LauncherCommands } from "./launcher.ts";

export type SessionEndReason = "session_required" | "session_expired" | "session_closed" | "link_invalid";
export type SessionState = {
  authenticated: boolean; method: "session" | "control_token"; environment: "development" | "production";
  idle_timeout_minutes: number; created_at?: string; idle_expires_at?: string; absolute_expires_at?: string;
};

export const SESSION_ENDED_EVENT = "rag:session-ended";
const CSRF_COOKIES = ["__Host-rag_csrf", "rag_csrf"];

/** Retour utilisateur de la copie ; aucun lancement de commande et aucune cause de refus supposée. */
export async function copySessionCommand(command: string, clipboard?: Pick<Clipboard, "writeText">): Promise<{ copied: string | null; error: string }> {
  try {
    if (!clipboard) throw new Error("clipboard unavailable");
    await clipboard.writeText(command);
    return { copied: command, error: "" };
  } catch {
    return { copied: null, error: "Copie impossible : sélectionnez la commande voulue et copiez-la manuellement." };
  }
}

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

/**
 * Écran de réouverture ; la commande elle-même vient du poste (`openCommandChoices`). Quand l'écran
 * affiche une ligne par système (commande d'ouverture non annoncée), le texte dit de choisir la sienne.
 * Installation par le kit Linux (R26-KIT-04) : l'entrée du menu des applications, si elle existe, puis la
 * commande du lanceur `atelier`, à taper dans un terminal ; aucun renvoi au dossier du projet.
 */
export function sessionScreen(reason: SessionEndReason, commands: LauncherCommands | null = knownLauncherCommands()): { title: string; body: string } {
  const installation = launcherInstallation(commands);
  if (installation?.menu) return installedScreen(reason, installation.menu);
  const shell = launcherShell(commands);
  const command = openCommandChoices(commands).length > 1 ? "la commande de votre système ci-dessous" : "la commande ci-dessous";
  const terminal = installation ? ", dans un terminal" : "";
  switch (reason) {
    case "session_required":
      return { title: "Session requise",
        body: installation
          ? "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Dans un terminal, lancez la commande ci-dessous : elle ouvre l'atelier dans un nouvel onglet."
          : `L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. ${shell[0].toUpperCase()}${shell.slice(1)}, depuis le dossier du projet, lancez ${command} : elle ouvre l'atelier dans un nouvel onglet.` };
    case "session_expired":
      return { title: "Session expirée",
        body: `La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier avec ${command}${terminal} ; documents, index et conversations enregistrés restent intacts.` };
    case "session_closed":
      return { title: "Session fermée",
        body: `La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier avec ${command}${terminal}.` };
    case "link_invalid":
      return { title: "Lien d'ouverture expiré ou déjà utilisé",
        body: `Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau avec ${command}${terminal}.` };
  }
}

/** Écrans d'une installation munie d'une entrée de menu : le menu des applications, ou la commande dans un terminal. */
function installedScreen(reason: SessionEndReason, menu: string): { title: string; body: string } {
  const either = `depuis le menu des applications (${menu}) ou avec la commande ci-dessous, dans un terminal`;
  switch (reason) {
    case "session_required":
      return { title: "Session requise",
        body: `L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Ouvrez-le depuis le menu des applications (${menu}), ou lancez la commande ci-dessous dans un terminal : il s'affiche dans un nouvel onglet.` };
    case "session_expired":
      return { title: "Session expirée",
        body: `La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier ${either} ; documents, index et conversations enregistrés restent intacts.` };
    case "session_closed":
      return { title: "Session fermée",
        body: `La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier ${either}.` };
    case "link_invalid":
      return { title: "Lien d'ouverture expiré ou déjà utilisé",
        body: `Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau ${either}.` };
  }
}

/**
 * Info-bulle du bouton « Fermer la session » : comment revenir. Clone et Windows : commande d'ouverture depuis le
 * dossier du projet (texte d'avant W018 sous Windows) ; installation : menu des applications, puis commande du lanceur.
 */
export function sessionCloseTitle(commands: LauncherCommands | null = knownLauncherCommands()): string {
  const open = launcherText("open", commands);
  const installation = launcherInstallation(commands);
  if (!installation) return `Ferme la session de ce navigateur. Pour revenir : ${open} depuis le dossier du projet.`;
  const menu = installation.menu ? `menu des applications (${installation.menu}), ou ` : "";
  return `Ferme la session de ce navigateur. Pour revenir : ${menu}${open} dans un terminal.`;
}
