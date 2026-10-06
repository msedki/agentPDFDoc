/**
 * Instance visée par la recette Playwright (R26-UI-01). Aucune cible par défaut : l'adresse et le jeton de
 * contrôle de l'instance de recette sont obligatoires, et l'instance principale (port 8785, jeton
 * .runtime/data/control/admin-token du dépôt) est refusée sauf autorisation explicite
 * RAG_E2E_MAIN_INSTANCE_ALLOWED=1. globalSetup ouvre une session sur la cible (POST /api/v1/admin/session-links)
 * et les specs d'import ou de génération y écrivent : la cible doit donc être choisie, jamais supposée.
 */
import { existsSync, readFileSync, realpathSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { dataDirKey, probeHost } from "./host.ts";

export const MAIN_INSTANCE_PORT = 8785;
/** Jeton de l'instance principale, situé par rapport à ce fichier (racine du dépôt), jamais par le dossier courant. */
export const MAIN_TOKEN_FILE = fileURLToPath(new URL("../../../../.runtime/data/control/admin-token", import.meta.url));
const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]"]);
export type E2ETarget = { baseURL: string; tokenFile: string; mainInstanceAllowed: boolean };
type Environment = Readonly<Record<string, string | undefined>>;

function realOrResolved(path: string): string {
  try { return realpathSync(path); } catch { return path; }
}

/**
 * `cwd` : dossier de lancement, pour un RAG_E2E_CONTROL_TOKEN_FILE relatif ; `mainTokenFile` : jeton de l'instance
 * principale, MAIN_TOKEN_FILE par défaut. Le jeton fourni est comparé par chemin réel (un lien reste le jeton
 * principal) puis par contenu lorsque le jeton principal existe (une copie reste le jeton principal).
 */
export function e2eTarget(environment: Environment = process.env, options: { cwd?: string; mainTokenFile?: string } = {}): E2ETarget {
  const cwd = options.cwd ?? process.cwd();
  const mainInstanceAllowed = environment.RAG_E2E_MAIN_INSTANCE_ALLOWED === "1";
  const override = "ou, pour viser délibérément l'instance principale, définissez RAG_E2E_MAIN_INSTANCE_ALLOWED=1.";
  const baseURL = environment.RAG_E2E_BASE_URL?.trim();
  if (!baseURL) throw new Error("RAG_E2E_BASE_URL est obligatoire : indiquez l'adresse de l'instance de recette isolée (http://127.0.0.1:<port>). La recette ne vise aucune instance par défaut.");
  let url: URL;
  try { url = new URL(baseURL); } catch { url = new URL("invalid:"); }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error(`RAG_E2E_BASE_URL n'est pas une adresse http(s) : ${baseURL}.`);
  if (!LOOPBACK.has(url.hostname)) throw new Error(`RAG_E2E_BASE_URL n'est pas une adresse de bouclage (127.0.0.1, localhost ou [::1]) : ${baseURL}. La recette ne vise qu'une instance locale.`);
  const port = Number(url.port || (url.protocol === "https:" ? 443 : 80));
  if (port === MAIN_INSTANCE_PORT && !mainInstanceAllowed) {
    throw new Error(`RAG_E2E_BASE_URL désigne le port ${MAIN_INSTANCE_PORT} de l'instance principale : lancez une instance de recette isolée sur un autre port, ${override}`);
  }
  const tokenSetting = environment.RAG_E2E_CONTROL_TOKEN_FILE?.trim();
  if (!tokenSetting) throw new Error("RAG_E2E_CONTROL_TOKEN_FILE est obligatoire : indiquez le jeton de contrôle de l'instance de recette (control/admin-token de sa racine de données).");
  const requested = resolve(cwd, tokenSetting);
  let tokenFile: string;
  try { tokenFile = realpathSync(requested); } catch { throw new Error(`Jeton de contrôle introuvable : ${requested}. Vérifiez RAG_E2E_CONTROL_TOKEN_FILE.`); }
  const mainToken = realOrResolved(options.mainTokenFile ?? MAIN_TOKEN_FILE);
  const host = probeHost();
  if (dataDirKey(tokenFile, host) === dataDirKey(mainToken, host) && !mainInstanceAllowed) {
    throw new Error(`RAG_E2E_CONTROL_TOKEN_FILE désigne le jeton de l'instance principale (${mainToken}) : utilisez celui de l'instance de recette, ${override}`);
  }
  // Contenu comparé sans être affiché : une copie du jeton principal ouvrirait une session sur l'instance principale.
  if (existsSync(mainToken) && readFileSync(tokenFile, "utf8").trim() === readFileSync(mainToken, "utf8").trim() && !mainInstanceAllowed) {
    throw new Error(`RAG_E2E_CONTROL_TOKEN_FILE (${tokenFile}) a le même contenu que le jeton de l'instance principale : utilisez celui de l'instance de recette, ${override}`);
  }
  return { baseURL, tokenFile, mainInstanceAllowed };
}
