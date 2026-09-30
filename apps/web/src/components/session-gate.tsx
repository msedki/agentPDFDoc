"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Copy, KeyRound } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { isSessionFailure, linkInvalidFromSearch, OPEN_COMMAND, SESSION_ENDED_EVENT, sessionScreen, type SessionEndReason } from "@/lib/session";
import { Button } from "./ui/button";
import { PanelError, PanelLoading } from "./ui/panel";

type GateState = { kind: "checking" } | { kind: "open" } | { kind: "ended"; reason: SessionEndReason } | { kind: "unreachable"; message: string };

const SessionContext = createContext<{ logout: () => Promise<void> } | null>(null);

/** Commandes de session pour la barre supérieure ; null hors de l'atelier ouvert. */
export function useSessionControls() {
  return useContext(SessionContext);
}

/**
 * Garde de l'atelier (W011) : l'espace de travail ne s'affiche qu'avec une session
 * valide ; sinon l'écran dit pourquoi et comment la rouvrir depuis le poste.
 */
export function SessionGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GateState>({ kind: "checking" });

  const check = useCallback(async () => {
    setState({ kind: "checking" });
    try {
      await api.session();
      setState({ kind: "open" });
    } catch (error) {
      if (error instanceof ApiError && isSessionFailure(error.code)) setState({ kind: "ended", reason: error.code });
      else setState({ kind: "unreachable", message: error instanceof Error ? error.message : "Le service local ne répond pas." });
    }
  }, []);

  useEffect(() => {
    if (linkInvalidFromSearch(window.location.search)) {
      // Le paramètre ne sert qu'à cet affichage : il ne reste pas dans l'adresse ni l'historique.
      window.history.replaceState(null, "", window.location.pathname);
      setState({ kind: "ended", reason: "link_invalid" });
    } else {
      void check();
    }
    const ended = (event: Event) => setState({ kind: "ended", reason: (event as CustomEvent<SessionEndReason>).detail });
    window.addEventListener(SESSION_ENDED_EVENT, ended);
    return () => window.removeEventListener(SESSION_ENDED_EVENT, ended);
  }, [check]);

  const logout = useCallback(async () => {
    // Les cookies sont effacés par le serveur même si la révocation échoue ; l'écran reflète la fermeture.
    await api.logout().catch(() => undefined);
    setState({ kind: "ended", reason: "session_closed" });
  }, []);

  if (state.kind === "open") return <SessionContext.Provider value={{ logout }}>{children}</SessionContext.Provider>;
  return <main className="session-screen" aria-labelledby="session-title">
    <div className="session-card">
      <p className="eyebrow">Atelier documentaire</p>
      {state.kind === "checking" && <><h1 id="session-title">Ouverture de l'atelier</h1><PanelLoading label="Vérification de la session…" /></>}
      {state.kind === "unreachable" && <><h1 id="session-title">Service local injoignable</h1>
        <PanelError message={state.message} onRetry={() => void check()} retryLabel="Vérifier de nouveau" /></>}
      {state.kind === "ended" && <SessionEnded reason={state.reason} onRetry={() => void check()} />}
    </div>
  </main>;
}

function SessionEnded({ reason, onRetry }: { reason: SessionEndReason; onRetry: () => void }) {
  const screen = sessionScreen(reason);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(OPEN_COMMAND);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return <>
    <h1 id="session-title"><KeyRound size={16} aria-hidden="true" />{screen.title}</h1>
    <p>{screen.body}</p>
    <div className="session-command">
      <code className="mono">{OPEN_COMMAND}</code>
      <Button type="button" variant="secondary" size="sm" onClick={() => void copy()}><Copy size={14} aria-hidden="true" />{copied ? "Commande copiée" : "Copier la commande"}</Button>
    </div>
    <p className="session-hint">Si la session a été ouverte dans un autre onglet de ce navigateur, vérifiez de nouveau.</p>
    <Button type="button" variant="ghost" size="sm" onClick={onRetry}>Vérifier de nouveau</Button>
    <span className="sr-only" aria-live="polite">{copied ? "Commande copiée dans le presse-papiers." : ""}</span>
  </>;
}
