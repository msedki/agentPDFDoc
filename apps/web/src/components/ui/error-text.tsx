"use client";
import { errorMessage } from "@/lib/utils";
import { useLauncherCommands } from "@/lib/use-launcher-commands";

/**
 * Échec retenu dans un état React : l'erreur elle-même, jamais son texte. Un texte rédigé par l'atelier
 * (service muet, statut HTTP sans message du service, échec sans objet Error) cite une commande du
 * lanceur ; calculé au rendu, il suit les commandes que `/health` annonce après l'échec (W018).
 */
export type Failure = { error: unknown };

/** Texte d'un échec avec les commandes connues au rendu ; le composant se redessine quand elles arrivent. */
export function useErrorText(): (error: unknown) => string {
  const commands = useLauncherCommands();
  return error => errorMessage(error, commands);
}

/** Texte d'un échec, à placer dans le JSX d'un message d'erreur. */
export function ErrorText({ error }: { error: unknown }) {
  return <>{useErrorText()(error)}</>;
}
