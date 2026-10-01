import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ApiError } from "./api-error.ts";
import { knownLauncherCommands, launcherText, type LauncherCommands } from "./launcher.ts";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
/** Texte d'un échec, calculé à l'affichage : un texte rédigé par l'atelier cite les commandes du lanceur connues à cet instant. */
export function errorMessage(error: unknown, commands: LauncherCommands | null = knownLauncherCommands()): string {
  if (error instanceof ApiError && error.describe) return error.describe(commands);
  return error instanceof Error ? error.message : `L'opération a échoué sans message exploitable. Réessayez ; si l'échec persiste, consultez le journal du service : la commande ${launcherText("logs", commands)} en donne l'emplacement.`;
}
