/**
 * Session de l'atelier pour les E2E (W011) : lien d'ouverture demandé avec le jeton de
 * contrôle de l'instance ciblée, échangé contre les cookies, puis enregistré comme état
 * de stockage partagé par les pages et le contexte `request` des tests.
 */
import { request, type FullConfig } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { storageStatePath } from "./e2e/storage-state.ts";
import { e2eTarget } from "./e2e/target.ts";

export const STORAGE_STATE = storageStatePath();

export default async function globalSetup(config: FullConfig) {
  // Adresse et jeton de l'instance de recette, validés par tests/e2e/target.ts : aucune instance par défaut.
  const baseURL = String(config.projects[0]?.use.baseURL ?? e2eTarget().baseURL);
  const tokenFile = e2eTarget().tokenFile;
  const token = readFileSync(tokenFile, "ascii").trim();
  const context = await request.newContext({ baseURL });
  try {
    const link = await context.post("/api/v1/admin/session-links", { headers: { "X-RAG-Control-Token": token } });
    if (!link.ok()) throw new Error(`Lien d'ouverture refusé (${link.status()}) : l'instance ${baseURL} est-elle celle du jeton ${tokenFile} ?`);
    const { path: openPath } = await link.json() as { path: string };
    const opened = await context.get(openPath, { maxRedirects: 0 });
    if (opened.status() !== 303 || opened.headers()["location"] !== "/workspace/") throw new Error(`Ouverture de session refusée (${opened.status()})`);
    mkdirSync(path.dirname(STORAGE_STATE), { recursive: true });
    await context.storageState({ path: STORAGE_STATE });
  } finally {
    await context.dispose();
  }
}
