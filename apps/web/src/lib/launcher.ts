/**
 * Commandes du lanceur citées par l'interface (W018 : Windows et Linux natifs).
 *
 * Le service annonce celles du poste dans la réponse publique de `GET /api/v1/health`
 * (`commands.open`, `status`, `logs`, `doctor`) : `.\rag.ps1 open` sous Windows, `./rag.sh open`
 * sous Linux. L'atelier les lit au chargement et les garde en mémoire. Une commande annoncée est
 * citée telle quelle. Une commande absente de la réponse (service antérieur à l'annonce de `doctor`)
 * prend le lanceur livré qu'emploient toutes les commandes annoncées : la plateforme est alors connue.
 * Sinon (service muet, lanceurs mêlés ou autre chemin), le texte donne les deux formes livrées.
 *
 * La plateforme du navigateur n'est pas employée pour choisir l'une des deux formes, bien que
 * navigateur et service partagent le poste : `navigator.platform` est documenté comme peu fiable
 * (MDN, Navigator.platform) et `navigator.userAgentData.platform` est expérimental, absent de
 * plusieurs navigateurs (MDN, NavigatorUAData.platform).
 */

export type LauncherAction = "open" | "status" | "logs" | "doctor";
export type LauncherCommands = Partial<Record<LauncherAction, string>>;

const ACTIONS: readonly LauncherAction[] = ["open", "status", "logs", "doctor"];
/** Lanceurs livrés : `rag.ps1` (PowerShell, Windows) et `rag.sh` (shell POSIX, Linux). */
const DELIVERED = [["Windows", ".\\rag.ps1"], ["Linux", "./rag.sh"]] as const;
/** Une ligne de commande affichable : sans caractère de contrôle ni espace de bord, longueur bornée. */
const PRINTABLE = /^[^\u0000-\u001f\u007f]{1,200}$/;

let current: LauncherCommands | null = null;
const listeners = new Set<() => void>();

/**
 * Commandes valides lues dans la réponse de `/health`, ou null si le service n'en annonce aucune.
 * Chaque valeur doit se terminer par l'action de sa clé ; seules les commandes annoncées sont gardées.
 */
export function launcherCommandsFrom(health: unknown): LauncherCommands | null {
  const announced = health && typeof health === "object" ? (health as { commands?: unknown }).commands : undefined;
  if (!announced || typeof announced !== "object") return null;
  const found: LauncherCommands = {};
  for (const action of ACTIONS) {
    const value = (announced as Record<string, unknown>)[action];
    if (typeof value === "string" && PRINTABLE.test(value) && value.trim() === value && value.endsWith(` ${action}`)) found[action] = value;
  }
  return Object.keys(found).length ? found : null;
}

/** Retient les commandes annoncées ; une réponse sans commandes ne fait pas oublier les précédentes. */
export function rememberLauncherCommands(commands: LauncherCommands | null): void {
  if (!commands) return;
  current = commands;
  for (const listener of listeners) listener();
}

export function knownLauncherCommands(): LauncherCommands | null {
  return current;
}

export function subscribeLauncherCommands(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/**
 * Lanceur livré du poste, connu quand toutes les commandes annoncées l'emploient (`.\rag.ps1 <action>`
 * ou `./rag.sh <action>`) ; null sans commande annoncée, avec des lanceurs mêlés ou un autre chemin.
 */
function hostLauncher(commands: LauncherCommands | null): string | null {
  const announced = Object.entries(commands ?? {});
  if (!announced.length) return null;
  return DELIVERED.find(([, launcher]) => announced.every(([action, command]) => command === `${launcher} ${action}`))?.[1] ?? null;
}

/** Commande du poste ; sinon, plateforme inconnue, « .\rag.ps1 open sous Windows ou ./rag.sh open sous Linux ». */
export function launcherText(action: LauncherAction, commands: LauncherCommands | null = current): string {
  const launcher = hostLauncher(commands);
  return commands?.[action] ?? (launcher ? `${launcher} ${action}` : DELIVERED.map(([system, launcher]) => `${launcher} ${action} sous ${system}`).join(" ou "));
}

/** Variantes de la commande d'ouverture à proposer : la commande du poste, sinon une par lanceur livré. */
export function openCommandChoices(commands: LauncherCommands | null = current): { system: string | null; command: string }[] {
  const launcher = hostLauncher(commands);
  const open = commands?.open ?? (launcher ? `${launcher} open` : null);
  return open ? [{ system: null, command: open }] : DELIVERED.map(([system, launcher]) => ({ system, command: `${launcher} open` }));
}

/** Où taper la commande : PowerShell pour `rag.ps1`, un terminal pour `rag.sh`. */
export function launcherShell(commands: LauncherCommands | null = current): string {
  const choices = openCommandChoices(commands);
  if (choices.length > 1) return "dans PowerShell sous Windows ou dans un terminal sous Linux";
  return /\.ps1(?:\s|$)/i.test(choices[0].command) ? "dans PowerShell" : "dans un terminal";
}

/**
 * Délais avant chaque nouvelle lecture de `/health` tant qu'aucune commande n'est connue (service muet au
 * chargement, réponse en échec) : croissants, cinq lectures en moins de deux minutes, puis plus aucune.
 * Le bouton « Vérifier de nouveau » de l'écran de session relance la série.
 */
export const HEALTH_RETRY_DELAYS_MS: readonly number[] = [2_000, 5_000, 15_000, 30_000, 60_000];

export type RetryTimers = { set: (run: () => void, ms: number) => unknown; clear: (handle: unknown) => void };
const browserTimers: RetryTimers = { set: (run, ms) => setTimeout(run, ms), clear: handle => clearTimeout(handle as ReturnType<typeof setTimeout>) };

/**
 * Relit `/health` après chaque délai tant que les commandes restent inconnues : une seule lecture à la fois,
 * la suivante programmée après la réponse, arrêt dès que des commandes sont connues ou après le dernier
 * délai. Renvoie la fonction qui arrête la série (démontage de l'écran, nouvelle vérification).
 */
export function retryLauncherCommands(health: () => Promise<unknown>, delays: readonly number[] = HEALTH_RETRY_DELAYS_MS, timers: RetryTimers = browserTimers): () => void {
  let attempt = 0;
  let handle: unknown = null;
  let stopped = false;
  const schedule = () => {
    handle = null;
    if (stopped || current || attempt >= delays.length) return;
    handle = timers.set(() => {
      handle = null;
      attempt += 1;
      void health().then(reply => rememberLauncherCommands(launcherCommandsFrom(reply)), () => undefined).then(schedule);
    }, delays[attempt]);
  };
  schedule();
  return () => {
    stopped = true;
    if (handle !== null) timers.clear(handle);
    handle = null;
  };
}
