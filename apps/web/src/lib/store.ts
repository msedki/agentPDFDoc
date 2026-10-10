"use client";
import { create } from "zustand";
import type { CellRange, Scope, SelectedSpan, Source } from "./types";
import type { AnalysisMode, LibraryMode } from "./panel-preferences";

export type PdfLocation = { documentId: string; versionId: string; pageIndex: number; format?: "pdf" };
export type OfficeLocation = { documentId: string; versionId: string; format: "docx" | "xlsx"; unitId?: string; elementPath?: string; blockId?: string; cellRange?: CellRange; extractionRevisionId?: string };
export type Location = PdfLocation | OfficeLocation;
export function isOfficeLocation(location: Location | null | undefined): location is OfficeLocation {
  return location?.format === "docx" || location?.format === "xlsx";
}
export function isPdfLocation(location: Location | null | undefined): location is PdfLocation {
  return Boolean(location && "pageIndex" in location && !isOfficeLocation(location));
}
type State = {
  selectedIds: string[]; scope: Scope; scopeLabel: string; opened: Location | null;
  previous: Location | null; previousSource: Source | null; source: Source | null; zoom: number; rotation: number;
  selection: { versionId: string; spans: SelectedSpan[]; text: string } | null;
  libraryMode: LibraryMode; analysisMode: AnalysisMode; panelWidths: [number, number];
  toggleDocument: (id: string) => void; setScope: (scope: Scope, label: string) => void;
  open: (location: Location, source?: Source | null) => void; back: () => void; close: () => void;
  page: (pageIndex: number) => void; setZoom: (zoom: number) => void; rotate: () => void;
  officeLocation: (update: Partial<Pick<OfficeLocation, "unitId" | "elementPath" | "blockId" | "cellRange">>) => void;
  setSelection: (selection: State["selection"]) => void;
  setPanels: (update: Partial<Pick<State, "libraryMode" | "analysisMode" | "panelWidths">>) => void;
};
// Disposition initiale : mêmes valeurs que defaultPanelPreferences (panel-preferences.ts),
// vérifiées par tests/unit/panel-preferences.test.ts ; le stockage local les remplace au montage.
export const useWorkspace = create<State>((set, get) => ({
  selectedIds: [], scope: { kind: "library" }, scopeLabel: "Toute la bibliothèque", opened: null,
  previous: null, previousSource: null, source: null, zoom: 1, rotation: 0, selection: null,
  libraryMode: "expanded", analysisMode: "expanded", panelWidths: [22, 30],
  toggleDocument: id => set(state => ({ selectedIds: state.selectedIds.includes(id) ? state.selectedIds.filter(value => value !== id) : [...state.selectedIds, id] })),
  setScope: (scope, scopeLabel) => set({ scope, scopeLabel }),
  open: (opened, source = null) => {
    const state = get();
    set({ opened, source, previous: state.opened, previousSource: state.source, selection: null, ...(state.opened?.versionId !== opened.versionId ? { zoom: 1, rotation: 0 } : {}) });
  },
  back: () => { const state = get(); if (state.previous) set({ opened: state.previous, previous: state.opened, source: state.previousSource, previousSource: state.source, selection: null }); },
  close: () => set({ opened: null, previous: null, previousSource: null, source: null, selection: null }),
  page: pageIndex => set(state => "pageIndex" in (state.opened ?? {}) ? { opened: { ...state.opened as PdfLocation, pageIndex } } : {}),
  officeLocation: update => set(state => isOfficeLocation(state.opened) ? { opened: { ...state.opened, ...update } } : {}),
  setZoom: zoom => set({ zoom: Math.min(3, Math.max(0.5, zoom)) }),
  rotate: () => set(state => ({ rotation: (state.rotation + 90) % 360 })),
  setSelection: selection => set({ selection }),
  setPanels: update => set(update),
}));
