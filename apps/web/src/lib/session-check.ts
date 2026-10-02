/**
 * Vérification de session au chargement de l'atelier (W011), avec la lecture publique des commandes du
 * lanceur (`GET /api/v1/health`, W018). Les deux requêtes partent ensemble ; leur ordre d'arrivée ne change
 * aucun texte : l'état garde l'échec lui-même, et son texte est calculé à l'affichage (`unreachableText`)
 * avec les commandes connues à cet instant.
 */
import { ApiError } from "./api-error.ts";
import { launcherCommandsFrom, rememberLauncherCommands, type LauncherCommands } from "./launcher.ts";
import { isSessionFailure, type SessionEndReason } from "./session.ts";
import { errorMessage } from "./utils.ts";

export type GateState = { kind: "checking" } | { kind: "open" } | { kind: "ended"; reason: SessionEndReason } | { kind: "unreachable"; failure: unknown };

/**
 * Attente maximale de la réponse de `/health` une fois `/session` réglée. Sur la boucle locale, `/health`
 * répond en général avant ; l'attente évite seulement d'afficher les deux formes de commande puis une seule.
 */
export const HEALTH_WAIT_MS = 1000;

export type SessionClient = { health: () => Promise<unknown>; session: () => Promise<unknown> };

/** Lecture publique des commandes du lanceur ; un échec de /health les laisse inconnues, sans erreur. */
export function readLauncherCommands(client: Pick<SessionClient, "health">): Promise<void> {
  return client.health().then(reply => rememberLauncherCommands(launcherCommandsFrom(reply)), () => undefined);
}

export async function checkSession(client: SessionClient, healthWaitMs: number = HEALTH_WAIT_MS): Promise<GateState> {
  // Un échec de /health laisse les commandes inconnues : les textes donnent alors les deux formes livrées.
  const health = readLauncherCommands(client);
  let state: GateState;
  try {
    await client.session();
    state = { kind: "open" };
  } catch (error) {
    state = error instanceof ApiError && isSessionFailure(error.code) ? { kind: "ended", reason: error.code } : { kind: "unreachable", failure: error };
  }
  let timer: ReturnType<typeof setTimeout> | undefined;
  await Promise.race([health, new Promise<void>(resolve => { timer = setTimeout(resolve, healthWaitMs); })]);
  clearTimeout(timer);
  return state;
}

/** Texte de l'échec d'ouverture (réseau ou réponse HTTP), recalculé à chaque affichage. */
export function unreachableText(failure: unknown, commands: LauncherCommands | null): string {
  return failure instanceof Error ? errorMessage(failure, commands) : "Le service local ne répond pas.";
}
