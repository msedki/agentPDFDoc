import { resolve } from "node:path";

/** Même fichier de session pour la préparation et le navigateur, isolable par recette. */
export function storageStatePath(environment: Readonly<Record<string, string | undefined>> = process.env, cwd = process.cwd()): string {
  const selected = environment.RAG_E2E_STORAGE_STATE;
  if (selected !== undefined && !selected.trim()) throw new Error("RAG_E2E_STORAGE_STATE doit désigner un fichier de session, pas un chemin vide.");
  return resolve(cwd, selected ?? "playwright/.auth/state.json");
}
