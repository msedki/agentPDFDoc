"use client";
import { useWorkspace } from "./store";
import { LEGACY_PANEL_PREFERENCES_KEY, PANEL_PREFERENCES_KEY, readPanelPreferences, serializePanelPreferences } from "./panel-preferences";

/**
 * Relit la disposition enregistrée (clé v2, ou v1 convertie). Un stockage
 * indisponible ou corrompu laisse la disposition par défaut ; la clé v1 n'est
 * pas effacée, elle est simplement ignorée dès qu'une clé v2 existe.
 */
export function restorePanelPreferences() {
  let current: string | null = null;
  let legacy: string | null = null;
  try {
    current = localStorage.getItem(PANEL_PREFERENCES_KEY);
    legacy = current === null ? localStorage.getItem(LEGACY_PANEL_PREFERENCES_KEY) : null;
  } catch { /* Stockage inaccessible : disposition par défaut. */ }
  const preferences = readPanelPreferences(current, legacy);
  useWorkspace.getState().setPanels({ libraryMode: preferences.library, analysisMode: preferences.analysis, panelWidths: preferences.widths });
}

export function savePanelPreferences() {
  const { libraryMode, analysisMode, panelWidths } = useWorkspace.getState();
  try { localStorage.setItem(PANEL_PREFERENCES_KEY, serializePanelPreferences({ library: libraryMode, analysis: analysisMode, widths: panelWidths })); } catch { /* Stockage inaccessible. */ }
}
