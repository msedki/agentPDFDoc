/**
 * Oracle des citations d'une réponse (R26-UI-02, défaut D2 de la recette R26-KIT-02).
 *
 * Une citation de réponse est un identifiant que le service a enregistré dans l'événement SSE `done`
 * (`citations[].source_id`) et que le texte de la réponse affiche comme bouton (`.answer-text .inline-citation`).
 * Les boutons de source des avis (« Sources concernées », valeurs signalées) portent la même classe
 * `inline-citation` hors de `.answer-text` : ils ne prouvent aucune citation. La recette du 7 octobre a validé
 * deux réponses 2B sans citation enregistrée parce que le sélecteur global attrapait ces boutons.
 */
import { expect, type Locator } from "@playwright/test";

export type DoneCitation = { source_id?: string; page_index?: number; version_id?: string; text?: string };
export type DoneEvent = { status?: string; text?: string; finish_reason?: string; citations?: DoneCitation[]; warnings?: unknown[] };

/** Dernier événement `done` d'un flux SSE (rejeu `/queries/{id}/events?after=0`), ou null s'il est absent. */
export function doneEvent(sse: string): DoneEvent | null {
  let done: DoneEvent | null = null;
  for (const block of sse.split(/\r?\n\r?\n/)) {
    const lines = block.split(/\r?\n/);
    if (lines.find(line => line.startsWith("event:"))?.slice(6).trim() !== "done") continue;
    done = JSON.parse(lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).replace(/^ /, "")).join("\n")) as DoneEvent;
  }
  return done;
}

/** Identifiants de citation enregistrés par le service pour la réponse. */
export function registeredCitationIds(done: DoneEvent | null): string[] {
  return (done?.citations ?? []).map(citation => citation.source_id).filter((id): id is string => typeof id === "string" && id.length > 0);
}

/**
 * Exige au moins une citation enregistrée dans `done`, puis des boutons de citation dans le texte de la réponse
 * de ce tour, chacun enregistré. Retourne le premier bouton et son identifiant.
 */
export async function registeredAnswerCitation(turn: Locator, done: DoneEvent | null) {
  expect(done, "Événement done absent du flux SSE rejoué").not.toBeNull();
  const registered = registeredCitationIds(done);
  expect(registered, "La réponse n'enregistre aucune citation (done.citations vide) : un bouton de source dans un avis n'est pas une citation de la réponse").not.toEqual([]);
  const buttons = turn.locator(".answer-text .inline-citation");
  await expect(buttons.first(), "Aucune citation affichée dans le texte de la réponse").toBeVisible();
  const shown = (await buttons.allInnerTexts()).map(text => text.trim());
  for (const id of shown) expect(registered, `Citation ${id} affichée dans la réponse sans être enregistrée par le service`).toContain(id);
  return { registered, shown, button: buttons.first(), sourceId: shown[0] };
}
