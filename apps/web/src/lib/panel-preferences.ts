/**
 * Disposition des panneaux : états, préférences locales et raccourci clavier.
 *
 * Fonctions pures, testées par tests/unit/panel-preferences.test.ts. Le
 * stockage local (localStorage) est lu et écrit par lib/panel-storage.ts.
 */

/** Bibliothèque : étendue (largeur réglable), rail de 64 px ou masquée. */
export type LibraryMode = "expanded" | "rail" | "hidden";
/** Analyse : étendue (largeur réglable) ou masquée. */
export type AnalysisMode = "expanded" | "hidden";
export type PanelPreferences = { version: 2; library: LibraryMode; analysis: AnalysisMode; widths: [number, number] };

export const PANEL_PREFERENCES_KEY = "rag-local-panels-v2";
export const LEGACY_PANEL_PREFERENCES_KEY = "rag-local-panels-v1";

/** Bornes de largeur des panneaux latéraux, en pourcentage de la zone de travail. */
export const PANEL_WIDTH_MIN = 16;
export const PANEL_WIDTH_MAX = 36;

export const defaultPanelPreferences: Readonly<PanelPreferences> = Object.freeze({ version: 2, library: "expanded", analysis: "expanded", widths: [22, 30] as [number, number] });

/**
 * Sous le point de rupture `lg` de Tailwind (64rem, soit 1 024 px), la
 * bibliothèque et l'analyse quittent la grille et s'ouvrent en panneaux latéraux.
 */
export const COMPACT_LAYOUT_QUERY = "(width < 64rem)";

const libraryModes: readonly LibraryMode[] = ["expanded", "rail", "hidden"];
const analysisModes: readonly AnalysisMode[] = ["expanded", "hidden"];

export function clampPanelWidth(value: number): number {
  return Math.min(PANEL_WIDTH_MAX, Math.max(PANEL_WIDTH_MIN, value));
}

function parse(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  } catch { return null; }
}

function widths(value: unknown): [number, number] {
  const list = Array.isArray(value) ? value : [];
  const width = (item: unknown, fallback: number) => typeof item === "number" && Number.isFinite(item) ? clampPanelWidth(item) : fallback;
  return [width(list[0], defaultPanelPreferences.widths[0]), width(list[1], defaultPanelPreferences.widths[1])];
}

function member<T extends string>(values: readonly T[], value: unknown, fallback: T): T {
  return values.includes(value as T) ? value as T : fallback;
}

/**
 * Lecture tolérante des préférences : un champ invalide reprend sa valeur par
 * défaut sans faire rejeter les autres. Sans clé v2 lisible, la clé v1
 * (`libraryHidden`, `analysisHidden`, `panelWidths`) est convertie : une
 * bibliothèque masquée le reste, sinon elle est étendue ; les largeurs sont
 * ramenées dans les bornes actuelles.
 */
export function readPanelPreferences(current: string | null, legacy: string | null): PanelPreferences {
  const stored = parse(current);
  if (stored) {
    return {
      version: 2,
      library: member(libraryModes, stored.library, defaultPanelPreferences.library),
      analysis: member(analysisModes, stored.analysis, defaultPanelPreferences.analysis),
      widths: widths(stored.widths),
    };
  }
  const old = parse(legacy);
  if (old) {
    return {
      version: 2,
      library: old.libraryHidden === true ? "hidden" : "expanded",
      analysis: old.analysisHidden === true ? "hidden" : "expanded",
      widths: widths(old.panelWidths),
    };
  }
  return { ...defaultPanelPreferences, widths: [...defaultPanelPreferences.widths] };
}

export function serializePanelPreferences(preferences: { library: LibraryMode; analysis: AnalysisMode; widths: [number, number] }): string {
  const value: PanelPreferences = { version: 2, library: preferences.library, analysis: preferences.analysis, widths: [clampPanelWidth(preferences.widths[0]), clampPanelWidth(preferences.widths[1])] };
  return JSON.stringify(value);
}

/**
 * Pistes de la grille des panneaux, toujours au nombre de cinq : bibliothèque,
 * séparateur, lecteur, séparateur, analyse. globals.css place chaque enfant sur
 * sa piste ; le lecteur reste sur la troisième, la seule élastique, quel que
 * soit l'état des panneaux.
 */
export function panelGridColumns({ compact, library, analysis, widths }: { compact: boolean; library: LibraryMode; analysis: AnalysisMode; widths: readonly [number, number] }): string {
  const libraryTracks = compact || library === "hidden" ? "0px 0px" : library === "rail" ? "64px 0px" : `${widths[0]}% 5px`;
  const analysisTracks = compact || analysis === "hidden" ? "0px 0px" : `5px ${widths[1]}%`;
  return `${libraryTracks} minmax(0, 1fr) ${analysisTracks}`;
}

/** Cycle de la bascule : étendue, puis rail, puis masquée, puis de nouveau étendue. */
export function nextLibraryMode(mode: LibraryMode): LibraryMode {
  return mode === "expanded" ? "rail" : mode === "rail" ? "hidden" : "expanded";
}

/** Le libellé de la bascule annonce l'action qu'elle exécutera, pas l'état courant. */
export function libraryToggleLabel(mode: LibraryMode, compact: boolean): string {
  if (compact) return "Ouvrir la bibliothèque";
  return mode === "expanded" ? "Replier la bibliothèque" : mode === "rail" ? "Masquer la bibliothèque" : "Afficher la bibliothèque";
}

export function analysisToggleLabel(mode: AnalysisMode, compact: boolean): string {
  if (compact) return "Ouvrir l'analyse";
  return mode === "expanded" ? "Replier l'analyse" : "Afficher l'analyse";
}

type ShortcutEvent = { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean; repeat?: boolean; target: unknown };

/**
 * Ctrl+B (⌘+B sous macOS) bascule la bibliothèque. Le raccourci est ignoré
 * pendant la saisie dans la zone de question (textarea) ou dans un contenu
 * éditable, ainsi que pour une touche maintenue enfoncée.
 */
export function isLibraryShortcut(event: ShortcutEvent): boolean {
  if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || event.repeat) return false;
  if (event.key.toLowerCase() !== "b") return false;
  const target = event.target as { tagName?: unknown; isContentEditable?: unknown } | null;
  if (target && (String(target.tagName ?? "").toUpperCase() === "TEXTAREA" || target.isContentEditable === true)) return false;
  return true;
}
