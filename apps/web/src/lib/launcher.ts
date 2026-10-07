/**
 * Commandes du lanceur citées par l'interface (W018 : Windows et Linux natifs).
 *
 * Le service annonce celles du poste dans la réponse publique de `GET /api/v1/health`
 * (`commands.open`, `status`, `logs`, `doctor`) : `.\rag.ps1 open` sous Windows, `./rag.sh open`
 * dans un clone Linux. L'atelier les lit au chargement et les garde en mémoire. Une commande annoncée est
 * citée telle quelle. Une commande absente de la réponse (service antérieur à l'annonce de `doctor`)
 * prend le lanceur livré qu'emploient toutes les commandes annoncées : la plateforme est alors connue.
 * Sinon (service muet, lanceurs mêlés ou autre chemin), le texte donne les deux formes livrées.
 *
 * Installation par le kit Linux (R26-KIT-04) : le service annonce `launcher.kind = "installation"`, avec
 * le nom de l'entrée de menu des applications (`launcher.menu`, null sans entrée), et les commandes du
 * lanceur `atelier` de la destination, chemin absolu suivi de l'action française (`ouvrir`, `etat`,
 * `journaux`, `diagnostic`), puis de `--modele <tag>` pour ouvrir et diagnostic quand le service sert un
 * autre modèle que celui de l'installation. rag.sh et rag.ps1 n'y sont jamais proposés.
 *
 * La plateforme du navigateur n'est pas employée pour choisir l'une des deux formes, bien que
 * navigateur et service partagent le poste : `navigator.platform` est documenté comme peu fiable
 * (MDN, Navigator.platform) et `navigator.userAgentData.platform` est expérimental, absent de
 * plusieurs navigateurs (MDN, NavigatorUAData.platform).
 */

export type LauncherAction = "open" | "status" | "logs" | "doctor";
/**
 * Commandes annoncées par le service ; `installation` n'est présent que pour une installation par le kit
 * Linux, avec le nom de son entrée de menu (null sans entrée de menu).
 */
export type LauncherCommands = Partial<Record<LauncherAction, string>> & { installation?: { menu: string | null } };

const ACTIONS: readonly LauncherAction[] = ["open", "status", "logs", "doctor"];
/** Lanceurs livrés : `rag.ps1` (PowerShell, Windows) et `rag.sh` (shell POSIX, Linux). */
const DELIVERED = [["Windows", ".\\rag.ps1"], ["Linux", "./rag.sh"]] as const;
/** Action du lanceur `atelier` d'une installation (tools/dist/linux_install.py) pour chaque commande citée. */
export const INSTALLED_ACTIONS: Readonly<Record<LauncherAction, string>> = { open: "ouvrir", status: "etat", logs: "journaux", doctor: "diagnostic" };
/** Actions qui choisissent le modèle : seules à porter `--modele <tag>` dans une installation. */
const MODEL_ACTIONS: readonly LauncherAction[] = ["open", "doctor"];
const INSTALLED_COMMAND = /^(.+) (ouvrir|etat|journaux|diagnostic)( --modele [A-Za-z0-9][A-Za-z0-9._:-]*)?$/;

/** Une ligne de commande affichable : sans caractère de contrôle ni espace de bord, longueur bornée. */
function printableCommand(value: string): boolean {
  return value.length >= 1 && value.length <= 200 && [...value].every(character => {
    const code = character.charCodeAt(0);
    return code > 31 && code !== 127;
  });
}

let current: LauncherCommands | null = null;
const listeners = new Set<() => void>();

/** Champ `launcher` d'une installation par le kit Linux ; undefined pour un projet ou un champ absent ou inconnu. */
function installationFrom(launcher: unknown): { menu: string | null } | undefined {
  if (!launcher || typeof launcher !== "object" || (launcher as { kind?: unknown }).kind !== "installation") return undefined;
  const menu = (launcher as { menu?: unknown }).menu;
  return { menu: typeof menu === "string" && printableCommand(menu) && menu.trim() === menu ? menu : null };
}

/** Lanceur et action française d'une commande d'installation, avec son modèle éventuel ; null sinon. */
function installedParts(command: string): { prefix: string; action: LauncherAction; model: boolean } | null {
  const match = INSTALLED_COMMAND.exec(command);
  const action = match ? ACTIONS.find(name => INSTALLED_ACTIONS[name] === match[2]) : undefined;
  return match && action ? { prefix: match[1], action, model: match[3] !== undefined } : null;
}

/**
 * Commandes valides lues dans la réponse de `/health`, ou null si le service n'en annonce aucune.
 * Chaque valeur doit se terminer par l'action de sa clé (son action française dans une installation) ;
 * seules les commandes annoncées sont gardées.
 */
export function launcherCommandsFrom(health: unknown): LauncherCommands | null {
  const reply = health && typeof health === "object" ? health as { commands?: unknown; launcher?: unknown } : undefined;
  const announced = reply?.commands;
  if (!announced || typeof announced !== "object") return null;
  const installation = installationFrom(reply.launcher);
  const found: LauncherCommands = {};
  for (const action of ACTIONS) {
    const value = (announced as Record<string, unknown>)[action];
    if (typeof value !== "string" || !printableCommand(value) || value.trim() !== value) continue;
    const parts = installation ? installedParts(value) : null;
    const valid = installation ? parts?.action === action && (!parts.model || MODEL_ACTIONS.includes(action)) : value.endsWith(` ${action}`);
    if (valid) found[action] = value;
  }
  if (!ACTIONS.some(action => found[action] !== undefined)) return null;
  return installation ? { ...found, installation } : found;
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

/** Installation par le kit Linux annoncée par le service, avec son entrée de menu ; null pour un projet. */
export function launcherInstallation(commands: LauncherCommands | null = current): { menu: string | null } | null {
  return commands?.installation ?? null;
}

function announcedCommands(commands: LauncherCommands | null): [LauncherAction, string][] {
  return ACTIONS.flatMap(action => commands?.[action] !== undefined ? [[action, commands[action]!] as [LauncherAction, string]] : []);
}

/**
 * Lanceur livré du poste, connu quand toutes les commandes annoncées l'emploient (`.\rag.ps1 <action>`
 * ou `./rag.sh <action>`) ; null sans commande annoncée, avec des lanceurs mêlés ou un autre chemin.
 */
function hostLauncher(commands: LauncherCommands | null): string | null {
  const announced = announcedCommands(commands);
  if (!announced.length) return null;
  return DELIVERED.find(([, launcher]) => announced.every(([action, command]) => command === `${launcher} ${action}`))?.[1] ?? null;
}

/** Lanceur `atelier` d'une installation, lu dans la première commande annoncée, sans action ni modèle. */
function installedLauncher(commands: LauncherCommands | null): string | null {
  const announced = commands?.installation ? announcedCommands(commands) : [];
  return announced.length ? installedParts(announced[0][1])?.prefix ?? null : null;
}

/** Commande du poste ; sinon, plateforme inconnue, « .\rag.ps1 open sous Windows ou ./rag.sh open sous Linux ». */
export function launcherText(action: LauncherAction, commands: LauncherCommands | null = current): string {
  const announced = commands?.[action];
  if (announced) return announced;
  const installed = installedLauncher(commands);
  if (installed) return `${installed} ${INSTALLED_ACTIONS[action]}`;
  const launcher = hostLauncher(commands);
  return launcher ? `${launcher} ${action}` : DELIVERED.map(([system, launcher]) => `${launcher} ${action} sous ${system}`).join(" ou ");
}

/** Variantes de la commande d'ouverture à proposer : la commande du poste, sinon une par lanceur livré. */
export function openCommandChoices(commands: LauncherCommands | null = current): { system: string | null; command: string }[] {
  const installed = installedLauncher(commands);
  if (installed) return [{ system: null, command: commands?.open ?? `${installed} ${INSTALLED_ACTIONS.open}` }];
  const launcher = hostLauncher(commands);
  const open = commands?.open ?? (launcher ? `${launcher} open` : null);
  return open ? [{ system: null, command: open }] : DELIVERED.map(([system, launcher]) => ({ system, command: `${launcher} open` }));
}

/** Où taper la commande : PowerShell pour `rag.ps1`, un terminal pour `rag.sh` et pour le lanceur d'une installation. */
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
