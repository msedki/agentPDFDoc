import { knownLauncherCommands, type LauncherCommands } from "./launcher.ts";

/** Texte rédigé par l'atelier quand le service ne fournit pas le sien ; il dépend des commandes du lanceur. */
export type LocalFailureText = (commands: LauncherCommands | null) => string;

/**
 * Erreur d'une requête à l'API locale : code du service (ou `HTTP_<statut>`, `NETWORK_ERROR`), texte et
 * identifiant de requête. Quand le texte est rédigé par l'atelier (service muet, statut HTTP sans message du
 * service), `describe` le recalcule avec les commandes connues au moment de l'affichage (`errorMessage`) :
 * une réponse de `/health` arrivée après l'échec fait alors citer la commande du poste (W018).
 * `message` garde le texte calculé à la création.
 */
export class ApiError extends Error {
  code: string;
  requestId?: string;
  describe?: LocalFailureText;
  constructor(code: string, message: string, requestId?: string, describe?: LocalFailureText) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
    this.describe = describe;
  }
}

/** Échec dont le texte vient de l'atelier, calculé maintenant puis recalculé à chaque affichage. */
export function localFailure(code: string, describe: LocalFailureText, requestId?: string): ApiError {
  return new ApiError(code, describe(knownLauncherCommands()), requestId, describe);
}
