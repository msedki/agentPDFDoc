"use client";
import { useSyncExternalStore } from "react";
import { knownLauncherCommands, subscribeLauncherCommands, type LauncherCommands } from "./launcher";

/** Commandes du lanceur annoncées par le poste ; le composant se redessine quand elles arrivent. */
export function useLauncherCommands(): LauncherCommands | null {
  // Rendu serveur de l'export statique : aucune commande connue, les deux formes livrées s'affichent.
  return useSyncExternalStore(subscribeLauncherCommands, knownLauncherCommands, () => null);
}
