"use client";
import { useEffect, useRef, useState } from "react";
import { Activity, LogOut, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from "lucide-react";
import type { StatusView } from "@/lib/status";
import { activeJobsBadge, activeJobsSentence } from "@/lib/panel-state";
import { analysisToggleLabel, libraryToggleLabel, type AnalysisMode, type LibraryMode } from "@/lib/panel-preferences";
import { launcherText } from "@/lib/launcher";
import { useLauncherCommands } from "@/lib/use-launcher-commands";
import { Button } from "./ui/button";
import { StatusIndicator } from "./ui/status-indicator";
import { HelpMenu } from "./help-menu";
import { ScopeControl } from "./scope-control";
import { useSessionControls } from "./session-gate";

/** Marque de l'Atelier documentaire : une page et ses lignes de texte, au trait. */
function BrandMark() {
  return <svg className="brand-mark" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <path d="M6 3h8.5L19 7.5V21H6z" />
    <path d="M14.5 3v4.5H19" />
    <path d="M9 12h7M9 15h7M9 18h4" />
  </svg>;
}

export type ServiceSummary = { status: StatusView; detail?: string };

/**
 * Barre supérieure de 56 px : bascule de la bibliothèque et marque à gauche,
 * périmètre au centre, état des services, Suivi, Aide et bascule de l'analyse à droite.
 */
export function AppTopbar({ compact, libraryMode, analysisMode, librarySheetOpen, analysisSheetOpen, onLibraryToggle, onAnalysisToggle, service, activeJobs, jobsFailed, jobsOpen, onJobsOpen }: {
  compact: boolean; libraryMode: LibraryMode; analysisMode: AnalysisMode; librarySheetOpen: boolean; analysisSheetOpen: boolean;
  onLibraryToggle: () => void; onAnalysisToggle: () => void;
  service: ServiceSummary;
  /** Traitements non terminés (isActiveJobState) ; null tant que le suivi n'a pas été lu. */
  activeJobs: number | null;
  /** Dernière lecture du suivi en échec : le compteur affiché peut être périmé. */
  jobsFailed: boolean; jobsOpen: boolean; onJobsOpen: () => void;
}) {
  const libraryLabel = libraryToggleLabel(libraryMode, compact);
  const session = useSessionControls();
  const commands = useLauncherCommands();
  const analysisLabel = analysisToggleLabel(analysisMode, compact);
  const [announcement, setAnnouncement] = useState("");
  const previousJobs = useRef<number | null>(null);
  // Seul un changement du nombre de traitements est annoncé, pas la première lecture.
  useEffect(() => {
    if (activeJobs === null) return;
    if (previousJobs.current !== null && previousJobs.current !== activeJobs) setAnnouncement(`Suivi : ${activeJobsSentence(activeJobs).toLocaleLowerCase("fr")}`);
    previousJobs.current = activeJobs;
  }, [activeJobs]);
  const count = activeJobs ?? 0;
  const libraryClosed = compact || libraryMode !== "expanded";
  const analysisClosed = compact || analysisMode === "hidden";
  return <header className="app-topbar">
    <div className="topbar-start">
      <Button variant="ghost" size="icon" onClick={onLibraryToggle} aria-label={libraryLabel} title={`${libraryLabel} (Ctrl+B ou ⌘+B)`}
        aria-haspopup={compact ? "dialog" : undefined} aria-expanded={compact ? librarySheetOpen : undefined}>{libraryClosed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}</Button>
      <div className="app-brand"><BrandMark /><div><p className="eyebrow">Poste documentaire local</p><h1>Atelier documentaire</h1></div></div>
    </div>
    <div className="topbar-center"><ScopeControl /></div>
    <div className="topbar-end">
      <StatusIndicator className="topbar-service" status={service.status} title={service.detail} />
      <Button variant="ghost" size="sm" onClick={onJobsOpen} aria-haspopup="dialog" aria-expanded={jobsOpen} title={jobsFailed ? "La dernière lecture du suivi a échoué : ouvrez-le pour voir l'erreur." : undefined}>
        <Activity size={16} aria-hidden="true" /><span className="topbar-label">Suivi</span>
        {count > 0 && <span className="count-pill" aria-hidden="true">{activeJobsBadge(count)}</span>}
        <span className="sr-only">{jobsFailed ? ", lecture du suivi en échec" : activeJobs === null ? "" : `, ${activeJobsSentence(count).toLocaleLowerCase("fr")}`}</span>
      </Button>
      <span className="sr-only" aria-live="polite">{announcement}</span>
      <HelpMenu />
      {session && <Button variant="ghost" size="sm" onClick={() => void session.logout()} aria-label="Fermer la session"
        title={`Ferme la session de ce navigateur. Pour revenir : ${launcherText("open", commands)} depuis le dossier du projet.`}><LogOut size={16} aria-hidden="true" /><span className="topbar-label">Fermer la session</span></Button>}
      <Button variant="ghost" size="icon" onClick={onAnalysisToggle} aria-label={analysisLabel} title={analysisLabel}
        aria-haspopup={compact ? "dialog" : undefined} aria-expanded={compact ? analysisSheetOpen : undefined}>{analysisClosed ? <PanelRightOpen size={16} /> : <PanelRightClose size={16} />}</Button>
    </div>
  </header>;
}
