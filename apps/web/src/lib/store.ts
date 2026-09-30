"use client";
import { create } from "zustand";
import type { Scope, SelectedSpan, Source } from "./types";

export type Location = { documentId: string; versionId: string; pageIndex: number };
type State = {
  selectedIds: string[]; scope: Scope; scopeLabel: string; opened: Location | null;
  previous: Location | null; previousSource: Source | null; source: Source | null; zoom: number; rotation: number;
  selection: { versionId: string; spans: SelectedSpan[]; text: string } | null;
  libraryHidden: boolean; analysisHidden: boolean; panelWidths: [number, number];
  toggleDocument: (id: string) => void; setScope: (scope: Scope, label: string) => void;
  open: (location: Location, source?: Source | null) => void; back: () => void; close: () => void;
  page: (pageIndex: number) => void; setZoom: (zoom: number) => void; rotate: () => void;
  setSelection: (selection: State["selection"]) => void;
  setPanels: (update: Partial<Pick<State, "libraryHidden" | "analysisHidden" | "panelWidths">>) => void;
};
export const useWorkspace = create<State>((set, get) => ({
  selectedIds: [], scope: { kind: "library" }, scopeLabel: "Toute la bibliothèque", opened: null,
  previous: null, previousSource: null, source: null, zoom: 1, rotation: 0, selection: null,
  libraryHidden: false, analysisHidden: false, panelWidths: [22, 30],
  toggleDocument: id => set(state => ({ selectedIds: state.selectedIds.includes(id) ? state.selectedIds.filter(value => value !== id) : [...state.selectedIds, id] })),
  setScope: (scope, scopeLabel) => set({ scope, scopeLabel }),
  open: (opened, source = null) => {
    const state = get();
    set({ opened, source, previous: state.opened, previousSource: state.source, selection: null, ...(state.opened?.versionId !== opened.versionId ? { zoom: 1, rotation: 0 } : {}) });
  },
  back: () => { const state = get(); if (state.previous) set({ opened: state.previous, previous: state.opened, source: state.previousSource, previousSource: state.source, selection: null }); },
  close: () => set({ opened: null, previous: null, previousSource: null, source: null, selection: null }),
  page: pageIndex => set(state => ({ opened: state.opened ? { ...state.opened, pageIndex } : null })),
  setZoom: zoom => set({ zoom: Math.min(3, Math.max(0.5, zoom)) }),
  rotate: () => set(state => ({ rotation: (state.rotation + 90) % 360 })),
  setSelection: selection => set({ selection }),
  setPanels: update => set(update),
}));

export function restorePanelPreferences() {
  try {
    const value = JSON.parse(localStorage.getItem("rag-local-panels-v1") ?? "null");
    if (value && typeof value.libraryHidden === "boolean" && typeof value.analysisHidden === "boolean" &&
      Array.isArray(value.panelWidths) && value.panelWidths.length === 2 &&
      value.panelWidths.every((width: unknown) => typeof width === "number" && width >= 14 && width <= 38)) {
      useWorkspace.getState().setPanels(value);
    }
  } catch { /* Corrupt preferences never block the workspace. */ }
}
export function savePanelPreferences() {
  const { libraryHidden, analysisHidden, panelWidths } = useWorkspace.getState();
  try { localStorage.setItem("rag-local-panels-v1", JSON.stringify({ libraryHidden, analysisHidden, panelWidths })); } catch { /* Storage can be unavailable. */ }
}
