/**
 * Poste qui exécute la recette E2E (W018 : Windows x86-64 ou Linux natif, aarch64 ou x86-64).
 * Interpréteur de l'environnement du projet et méthode de mesure mémoire propres à chaque
 * plateforme ; aucun autre système n'est accepté par les sondes.
 */
import { resolve } from "node:path";

export type ProbeHost = "win32" | "linux";

/** Plateforme du poste, ou une erreur explicite hors des deux plateformes prises en charge. */
export function probeHost(platform: string = process.platform): ProbeHost {
  if (platform === "win32" || platform === "linux") return platform;
  throw new Error(`Recette E2E prise en charge sous Windows et Linux seulement (plateforme ${platform}).`);
}

/** Racine du dépôt : la recette se lance depuis apps/web. */
export const projectRoot = resolve(process.cwd(), "../..");

/** Interpréteur de l'environnement isolé du projet, comme `services/runtime/platforms.venv_python`. */
export function projectPython(host: ProbeHost = probeHost(), root: string = projectRoot): string {
  return host === "win32" ? resolve(root, ".venv/Scripts/python.exe") : resolve(root, ".venv/bin/python");
}

/**
 * Clé de comparaison d'un chemin de stockage réel (`realpathSync`) : insensible à la casse sous Windows,
 * dont les systèmes de fichiers ignorent la casse ; exacte sous Linux, où `Data` et `data` sont deux dossiers.
 */
export function dataDirKey(path: string, host: ProbeHost = probeHost()): string {
  return host === "win32" ? path.toLowerCase() : path;
}

/**
 * Contrôle d'identité du worker Node avant toute mesure, passé en argument à la sonde psutil.
 * Sous Windows, le nom du processus (`node.exe`). Sous Linux, Node 24 renomme son thread principal
 * « MainThread », que psutil renvoie comme nom du processus : la sonde compare alors l'exécutable
 * du PID (`/proc/<pid>/exe`) à celui de ce Node (`process.execPath`).
 */
export function workerIdentity(host: ProbeHost = probeHost(), execPath: string = process.execPath): string {
  return host === "win32" ? "name:node.exe" : `exe:${execPath}`;
}

/**
 * Méthode de mesure écrite dans chaque relevé. Sous Windows : RSS (working set), mémoire privée
 * engagée et USS. Sous Linux, psutil n'a pas de mémoire privée Windows : RSS lu dans
 * /proc/<pid>/statm et USS calculé sur /proc/<pid>/smaps (memory_full_info), séparés par processus.
 */
export function memoryMethod(host: ProbeHost = probeHost()): string {
  return host === "win32"
    ? "psutil available host RAM; RSS/Windows committed private/USS per process of this Node worker and its Chromium descendants only. No summed RSS or host-peak claim."
    : "psutil available host RAM (Linux MemAvailable); RSS from /proc/<pid>/statm and USS from /proc/<pid>/smaps (psutil memory_full_info) per process of this Node worker and its Chromium descendants only; no Windows private memory on Linux. No summed RSS or host-peak claim.";
}
