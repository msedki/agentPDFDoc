/**
 * Matériel de la génération des réponses (W025, P7), lu dans `GET /api/v1/jobs` (`generation`), route
 * authentifiée que l'atelier relit toutes les 3 secondes. `device` est le mode retenu par le service à son
 * démarrage ; `fallback` signale qu'un échec du chargement sur le GPU l'a fait passer sur le processeur
 * jusqu'à son redémarrage ; `processor` est la dernière occupation du modèle relue par le service, avant
 * chaque question et, en mode GPU, après chaque réponse. En mode GPU, le libellé suit cette occupation :
 * le service peut avoir retenu le GPU alors que le modèle est chargé en partie, ou en totalité, sur le
 * processeur. Seul le modèle de réponse change de matériel : la recherche et l'import restent calculés sur
 * le processeur sur toutes les plateformes (W025, P1). Le détail du matériel (nom du GPU, bibliothèques)
 * reste réservé à `doctor`, que les textes citent.
 */
import { knownLauncherCommands, launcherText, type LauncherCommands } from "./launcher.ts";
import type { StatusView } from "./status.ts";
import { GENERATION_DEVICES, type Generation } from "./types.ts";

/**
 * Champ `generation` validé, ou null : champ absent (API antérieure à W025), null (double de la passerelle)
 * ou mal formé. Aucun matériel n'est alors affiché, plutôt qu'un matériel supposé. Un `processor` absent
 * vaut null : aucune occupation observée.
 */
export function readGeneration(value: unknown): Generation | null {
  if (!value || typeof value !== "object") return null;
  const { device, fallback, processor = null } = value as { device?: unknown; fallback?: unknown; processor?: unknown };
  const known = GENERATION_DEVICES.find(item => item === device);
  if (!known || typeof fallback !== "boolean") return null;
  if (processor !== null && (typeof processor !== "string" || !processor)) return null;
  // Après un repli, l'API publie toujours `cpu` : un repli annoncé sur le GPU est incohérent.
  if (fallback && known !== "cpu") return null;
  return { device: known, fallback, processor };
}

/** Occupation du modèle : entièrement sur le GPU, partagée (parts en pour cent), entièrement sur le processeur, ou inconnue. */
export type Placement = { kind: "gpu" } | { kind: "partial"; cpu: number; gpu: number } | { kind: "cpu" } | { kind: "unknown" };

const PARTIAL = /^(\d{1,3})%\/(\d{1,3})% CPU\/GPU$/;

/**
 * Lecture de la colonne PROCESSOR d'`ollama ps` publiée dans `processor` ; null si aucune occupation n'a été
 * observée. `Unknown` (Ollama l'affiche quand la taille sur le GPU dépasse celle du modèle) et toute forme
 * non reconnue donnent une occupation inconnue, jamais une occupation supposée.
 */
export function readPlacement(processor: string | null): Placement | null {
  if (processor === null) return null;
  if (processor === "100% GPU") return { kind: "gpu" };
  if (processor === "100% CPU") return { kind: "cpu" };
  const shares = PARTIAL.exec(processor);
  if (shares && Number(shares[1]) + Number(shares[2]) === 100) return { kind: "partial", cpu: Number(shares[1]), gpu: Number(shares[2]) };
  return { kind: "unknown" };
}

/** Indicateur du bandeau de contexte, son explication et, en repli seulement, l'avis à afficher dans le bandeau. */
export type GenerationView = { status: StatusView; detail: string; notice: string | null };

const SEARCH_ON_PROCESSOR = "La recherche et l'import des documents restent calculés sur le processeur.";

export function generationView(generation: Generation | null, commands: LauncherCommands | null = knownLauncherCommands()): GenerationView | null {
  if (!generation) return null;
  const doctor = launcherText("doctor", commands);
  if (generation.fallback) {
    const notice = `Le chargement du modèle de réponse sur le GPU a échoué : l'atelier répond sur le processeur jusqu'à son prochain redémarrage. La commande ${doctor} en donne la cause et la marche à suivre pour réessayer le GPU.`;
    return { status: { label: "GPU en échec : réponses calculées sur le processeur", tone: "warning", code: "cpu_fallback", known: true }, detail: notice, notice };
  }
  if (generation.device === "cpu") {
    return {
      status: { label: "Réponses calculées sur le processeur", tone: "neutral", code: "cpu", known: true },
      detail: `Le modèle de réponse est exécuté sur le processeur de ce poste ; la commande ${doctor} en donne la raison dans sa rubrique « calcul ».`,
      notice: null,
    };
  }
  // Mode GPU : seul un modèle vu entièrement sur le GPU permet d'affirmer que les réponses y sont calculées.
  const placement = readPlacement(generation.processor);
  if (!placement) {
    return {
      status: { label: "Génération prévue sur le GPU", tone: "neutral", code: "gpu_pending", known: true },
      detail: `Le service a retenu le GPU de ce poste pour le modèle de réponse, qui n'a pas encore été vu chargé ; sa répartition entre GPU et processeur est relevée à chaque question. ${SEARCH_ON_PROCESSOR}`,
      notice: null,
    };
  }
  if (placement.kind === "gpu") {
    return {
      status: { label: "Réponses calculées sur le GPU", tone: "neutral", code: "gpu", known: true },
      detail: `Le modèle de réponse était chargé entièrement sur le GPU de ce poste lors de la dernière vérification, faite avant chaque question et après chaque réponse. ${SEARCH_ON_PROCESSOR} La commande ${doctor} détaille le GPU dans sa rubrique « calcul ».`,
      notice: null,
    };
  }
  if (placement.kind === "partial") {
    return {
      status: { label: "Réponses calculées en partie sur le processeur", tone: "warning", code: "gpu_partial", known: true },
      detail: `Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé à ${placement.gpu} % sur le GPU et à ${placement.cpu} % sur le processeur, selon la mémoire GPU libre à son chargement. La commande ${doctor} détaille cette répartition dans sa rubrique « calcul ».`,
      notice: null,
    };
  }
  if (placement.kind === "cpu") {
    return {
      status: { label: "GPU retenu, réponses calculées sur le processeur", tone: "warning", code: "gpu_on_cpu", known: true },
      detail: `Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé entièrement sur le processeur. La commande ${doctor} en donne la marche à suivre dans sa rubrique « calcul ».`,
      notice: null,
    };
  }
  return {
    status: { label: "Génération prévue sur le GPU", tone: "neutral", code: "gpu_unknown", known: true },
    detail: `Le service a retenu le GPU de ce poste pour le modèle de réponse, mais la répartition du modèle entre GPU et processeur n'a pas pu être déterminée lors de la dernière vérification. La commande ${doctor} donne l'état du GPU dans sa rubrique « calcul ».`,
    notice: null,
  };
}
