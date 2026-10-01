/**
 * Suite à donner à une demande de réindexation (POST /documents/{id}/reindex, contrat `reindex_response`
 * et `reindex_outcomes`). Selon le dernier traitement du document, le service :
 * - renvoie le traitement en cours (`queued`, `extracting`, `indexing`) avec `reused`, sans en créer ;
 * - renvoie le traitement `paused` de la dernière version avec `resume_required`, à reprendre
 *   (POST /jobs/{job_id}/resume) au lieu d'une seconde extraction ;
 * - refuse la demande pendant `pausing` (409 `job_pausing`) : l'erreur et son message, rédigé par le
 *   service, remontent au bouton qui l'affiche ; aucun avis n'est produit ici ;
 * - crée un traitement neuf dans tous les autres cas, y compris pendant `cancelling` : l'annulation reste
 *   définitive et la file, qui traite un travail à la fois, exécute le nouveau traitement après elle.
 */
import type { ReindexResponse } from "./types.ts";

/** États suspendus que la réindexation renvoie avec `resume_required` (`reindex_response.job_state`). */
export const SUSPENDED_REINDEX_STATES = ["paused"] as const;

export type ReindexOutcome =
  | { kind: "started"; message: string }
  | { kind: "running"; message: string }
  | { kind: "resume"; jobId: string; message: string }
  | { kind: "wait"; message: string };

export function reindexOutcome(response: ReindexResponse | null | undefined): ReindexOutcome {
  if (response?.resume_required) {
    if (response.job_state === "paused") {
      return { kind: "resume", jobId: response.job_id,
        message: "Le dernier traitement de ce document est en pause : la réindexation n'en lance pas un second. Reprenez-le pour poursuivre l'indexation depuis son dernier point de reprise." };
    }
    // Repli pour un état que ce service ne renvoie pas : aucune reprise proposée, que le service pourrait refuser.
    return { kind: "wait", message: `Un traitement suspendu de ce document existe déjà (état ${response.job_state ?? "non communiqué"}) : aucune nouvelle réindexation n'a été lancée. Consultez le Suivi pour le reprendre.` };
  }
  if (response?.reused) {
    return { kind: "running", message: "Un traitement de ce document est déjà en cours : aucune nouvelle réindexation n'a été lancée. Sa progression s'affiche dans le Suivi." };
  }
  return { kind: "started", message: "Réindexation demandée : sa progression s'affiche dans le Suivi." };
}
