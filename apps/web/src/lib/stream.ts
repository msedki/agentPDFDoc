import { sameOriginPath } from "./api";
import type { StreamEvent } from "./types";

const eventTypes = ["status", "sources", "delta", "warning", "done", "error", "cancelled", "needs_clarification"];
export function connectQueryStream(url: string, after: string, onEvent: (event: StreamEvent) => void, onConnection: (state: "connected" | "reconnecting") => void) {
  const safe = sameOriginPath(url);
  const params = new URL(safe, window.location.origin);
  if (after) params.searchParams.set("after", after);
  const stream = new EventSource(params.pathname + params.search, { withCredentials: true });
  let lastId = Number(after || 0);
  stream.onopen = () => onConnection("connected");
  stream.onerror = () => onConnection("reconnecting");
  for (const type of eventTypes) stream.addEventListener(type, event => {
    if (!(event instanceof MessageEvent)) return;
    const id = Number(event.lastEventId);
    if (id && id <= lastId) return;
    if (id) lastId = id;
    try {
      const data = JSON.parse(event.data);
      if (typeof data !== "object" || data === null || Array.isArray(data)) throw new Error("Invalid event");
      onEvent({ type, id: event.lastEventId, data });
      if (["done", "cancelled", "error", "needs_clarification"].includes(type)) stream.close();
    } catch {
      onEvent({ type: "error", id: event.lastEventId, data: { message: "Le flux de la réponse contient un événement illisible : la réponse est interrompue. Posez de nouveau la question pour relancer le traitement." } });
      stream.close();
    }
  });
  return () => stream.close();
}
