"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { Copy, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { openCommandChoices, retryLauncherCommands } from "@/lib/launcher";
import { copySessionCommand, linkInvalidFromSearch, SESSION_ENDED_EVENT, sessionScreen, type SessionEndReason } from "@/lib/session";
import { checkSession, readLauncherCommands, unreachableText, type GateState } from "@/lib/session-check";
import { useLauncherCommands } from "@/lib/use-launcher-commands";
import { Button } from "./ui/button";
import { PanelError, PanelLoading } from "./ui/panel";

const SessionContext = createContext<{ logout: () => Promise<void> } | null>(null);
const subscribeHydration = () => () => {};
const clientSnapshot = () => true;
const serverSnapshot = () => false;
type SessionGateState = GateState | { kind: "closing" } | { kind: "logout_failed"; failure: unknown };

/** Commandes de session pour la barre supérieure ; null hors de l'atelier ouvert. */
export function useSessionControls() {
  return useContext(SessionContext);
}

/**
 * Garde de l'atelier (W011) : l'espace de travail ne s'affiche qu'avec une session
 * valide ; sinon l'écran dit pourquoi et comment la rouvrir depuis le poste.
 */
export function SessionGate({ children }: { children: ReactNode }) {
  const hydrated = useSyncExternalStore(subscribeHydration, clientSnapshot, serverSnapshot);
  return hydrated ? <SessionGateClient>{children}</SessionGateClient> : <SessionChecking />;
}

function SessionGateClient({ children }: { children: ReactNode }) {
  const [invalidLink] = useState(() => linkInvalidFromSearch(window.location.search));
  const [state, setState] = useState<SessionGateState>(() => invalidLink ? { kind: "ended", reason: "link_invalid" } : { kind: "checking" });
  // Les textes qui citent le lanceur se recalculent quand /health annonce les commandes du poste.
  const commands = useLauncherCommands();
  const stopRetry = useRef<(() => void) | null>(null);
  const mounted = useRef(false);
  const logoutPending = useRef(false);
  // Service muet ou /health en échec : nouvelles lectures espacées et bornées, aucune si les commandes sont
  // connues ; la série précédente est arrêtée, et aucune ne part après le démontage.
  const retryCommands = useCallback(() => {
    stopRetry.current?.();
    stopRetry.current = mounted.current ? retryLauncherCommands(() => api.health()) : null;
  }, []);

  const check = useCallback(() => checkSession(api).then(nextState => {
    // Session et commandes du lanceur (lecture publique de /health, W018) : l'état garde l'échec, pas son texte.
    setState(nextState);
    retryCommands();
  }), [retryCommands]);
  const retrySession = () => {
    // Au montage, checking est déjà l'état initial ; une reprise utilisateur le rétablit immédiatement.
    setState({ kind: "checking" });
    void check();
  };

  useEffect(() => {
    mounted.current = true;
    if (invalidLink) {
      // Le paramètre ne sert qu'à cet affichage : il ne reste pas dans l'adresse ni l'historique.
      window.history.replaceState(null, "", window.location.pathname);
      // Sans vérification de session, les commandes du lanceur sont lues ici pour l'écran du lien refusé.
      void readLauncherCommands(api).then(retryCommands);
    } else {
      void check();
    }
    const ended = (event: Event) => setState({ kind: "ended", reason: (event as CustomEvent<SessionEndReason>).detail });
    window.addEventListener(SESSION_ENDED_EVENT, ended);
    return () => { mounted.current = false; window.removeEventListener(SESSION_ENDED_EVENT, ended); stopRetry.current?.(); };
  }, [check, retryCommands, invalidLink]);

  const logout = useCallback(async () => {
    if (logoutPending.current || !mounted.current) return;
    logoutPending.current = true;
    setState({ kind: "closing" });
    try {
      // Seule la réponse du serveur confirme l'effacement des cookies ; une panne réseau ne le garantit pas.
      await api.logout();
      if (mounted.current) setState({ kind: "ended", reason: "session_closed" });
    } catch (failure) {
      if (mounted.current) setState(current => current.kind === "ended" ? current : { kind: "logout_failed", failure });
    } finally { logoutPending.current = false; }
  }, []);

  if (state.kind === "open") return <SessionContext.Provider value={{ logout }}>{children}</SessionContext.Provider>;
  return <main className="session-screen" aria-labelledby="session-title">
    <div className="session-card">
      <p className="eyebrow">Atelier documentaire</p>
      {state.kind === "checking" && <><h1 id="session-title">Ouverture de l'atelier</h1><PanelLoading label="Vérification de la session…" /></>}
      {state.kind === "closing" && <><h1 id="session-title">Fermeture de la session</h1><PanelLoading label="Confirmation auprès du service local…" /></>}
      {state.kind === "logout_failed" && <><h1 id="session-title">Fermeture de la session non confirmée</h1>
        <PanelError title="La session peut encore être active" message={`${unreachableText(state.failure, commands)} Réessayez la fermeture pour que le service local efface les cookies de ce navigateur et révoque la session.`} onRetry={() => void logout()} retryLabel="Réessayer la fermeture" /></>}
      {state.kind === "unreachable" && <><h1 id="session-title">Ouverture de l'atelier impossible</h1>
        <PanelError title="Vérification de la session impossible" message={unreachableText(state.failure, commands)} onRetry={retrySession} retryLabel="Vérifier de nouveau" /></>}
      {state.kind === "ended" && <SessionEnded reason={state.reason} onRetry={retrySession} />}
    </div>
  </main>;
}

function SessionChecking() {
  return <main className="session-screen" aria-labelledby="session-title"><div className="session-card">
    <p className="eyebrow">Atelier documentaire</p><h1 id="session-title">Ouverture de l'atelier</h1><PanelLoading label="Vérification de la session…" />
  </div></main>;
}

function SessionEnded({ reason, onRetry }: { reason: SessionEndReason; onRetry: () => void }) {
  const commands = useLauncherCommands();
  const screen = sessionScreen(reason, commands);
  const [copied, setCopied] = useState<string | null>(null);
  const [copyError, setCopyError] = useState("");
  const copy = async (command: string) => {
    setCopyError("");
    const result = await copySessionCommand(command, navigator.clipboard);
    setCopied(result.copied);
    setCopyError(result.error);
  };
  return <>
    <h1 id="session-title"><KeyRound size={16} aria-hidden="true" />{screen.title}</h1>
    <p>{screen.body}</p>
    {/* Commande du poste ; tant que la plateforme est inconnue, une ligne par lanceur livré. */}
    {openCommandChoices(commands).map(({ system, command }) => <div className="session-command" key={command}>
      {system && <span className="session-system">{system}</span>}
      <code className="mono">{command}</code>
      <Button type="button" variant="secondary" size="sm" onClick={() => void copy(command)}><Copy size={14} aria-hidden="true" />{copied === command ? "Commande copiée" : system ? `Copier la commande ${system}` : "Copier la commande"}</Button>
    </div>)}
    {copyError && <p className="inline-error" role="alert">{copyError}</p>}
    <p className="session-hint">Si la session a été ouverte dans un autre onglet de ce navigateur, vérifiez de nouveau.</p>
    <Button type="button" variant="secondary" size="sm" onClick={onRetry}>Vérifier de nouveau</Button>
    <span className="sr-only" aria-live="polite">{copied ? "Commande copiée dans le presse-papiers." : ""}</span>
  </>;
}
