import assert from "node:assert/strict";
import test from "node:test";
import { analysisToggleLabel, clampPanelWidth, COMPACT_LAYOUT_QUERY, defaultPanelPreferences, isLibraryShortcut, libraryToggleLabel, nextLibraryMode, panelGridColumns, readPanelPreferences, serializePanelPreferences, type AnalysisMode, type LibraryMode } from "../../src/lib/panel-preferences.ts";
import { useWorkspace } from "../../src/lib/store.ts";

const defaults = { version: 2, library: "expanded", analysis: "expanded", widths: [22, 30] };

test("stored v2 preferences are read back as saved", () => {
  const saved = serializePanelPreferences({ library: "rail", analysis: "hidden", widths: [25, 33] });
  assert.deepEqual(JSON.parse(saved), { version: 2, library: "rail", analysis: "hidden", widths: [25, 33] });
  assert.deepEqual(readPanelPreferences(saved, null), { version: 2, library: "rail", analysis: "hidden", widths: [25, 33] });
});

test("an invalid v2 field falls back to its default without discarding the valid ones", () => {
  assert.deepEqual(readPanelPreferences(JSON.stringify({ version: 2, library: "floating", analysis: "hidden", widths: [50, "wide"] }), null), { version: 2, library: "expanded", analysis: "hidden", widths: [36, 30] });
  assert.deepEqual(readPanelPreferences(JSON.stringify({ library: "hidden" }), null), { version: 2, library: "hidden", analysis: "expanded", widths: [22, 30] });
  assert.deepEqual(readPanelPreferences(JSON.stringify({ widths: [10, Number.MAX_VALUE] }), null).widths, [16, 36]);
});

test("v1 preferences are migrated when no v2 key exists", () => {
  const legacy = JSON.stringify({ libraryHidden: true, analysisHidden: false, panelWidths: [14, 38] });
  assert.deepEqual(readPanelPreferences(null, legacy), { version: 2, library: "hidden", analysis: "expanded", widths: [16, 36] }, "les largeurs v1 (14-38 %) sont ramenées dans 16-36 %");
  assert.deepEqual(readPanelPreferences(null, JSON.stringify({ libraryHidden: false, analysisHidden: true, panelWidths: [24, 28] })), { version: 2, library: "expanded", analysis: "hidden", widths: [24, 28] });
  // Migration tolérante : champs absents ou d'un mauvais type → valeurs par défaut.
  assert.deepEqual(readPanelPreferences(null, JSON.stringify({ libraryHidden: "yes", panelWidths: "wide" })), defaults);
});

test("a v2 key takes precedence over v1; corrupt or absent storage yields the defaults", () => {
  const current = serializePanelPreferences({ library: "rail", analysis: "expanded", widths: [20, 30] });
  assert.equal(readPanelPreferences(current, JSON.stringify({ libraryHidden: true, analysisHidden: true, panelWidths: [20, 20] })).library, "rail");
  assert.deepEqual(readPanelPreferences("{not json", JSON.stringify({ libraryHidden: true, analysisHidden: false, panelWidths: [20, 30] })).library, "hidden", "v2 illisible : la v1 reste exploitable");
  for (const [current, legacy] of [[null, null], ["null", "[]"], ["[1,2]", "42"], ["", "{broken"]] as const) assert.deepEqual(readPanelPreferences(current, legacy), defaults);
  // Les défauts retournés sont des copies : une modification ne touche pas la constante partagée.
  const copy = readPanelPreferences(null, null);
  copy.widths[0] = 30;
  assert.equal(defaultPanelPreferences.widths[0], 22);
});

test("the workspace store starts from the documented default layout", () => {
  const state = useWorkspace.getInitialState();
  assert.deepEqual({ library: state.libraryMode, analysis: state.analysisMode, widths: state.panelWidths }, { library: defaultPanelPreferences.library, analysis: defaultPanelPreferences.analysis, widths: defaultPanelPreferences.widths });
});

test("widths are clamped to the 16-36 % bounds", () => {
  assert.equal(clampPanelWidth(10), 16);
  assert.equal(clampPanelWidth(22.5), 22.5);
  assert.equal(clampPanelWidth(80), 36);
});

test("the library toggle cycles expanded, rail, hidden and its label announces the next action", () => {
  assert.equal(nextLibraryMode("expanded"), "rail");
  assert.equal(nextLibraryMode("rail"), "hidden");
  assert.equal(nextLibraryMode("hidden"), "expanded");
  assert.equal(libraryToggleLabel("expanded", false), "Replier la bibliothèque");
  assert.equal(libraryToggleLabel("rail", false), "Masquer la bibliothèque");
  assert.equal(libraryToggleLabel("hidden", false), "Afficher la bibliothèque");
  assert.equal(libraryToggleLabel("expanded", true), "Ouvrir la bibliothèque");
  assert.equal(analysisToggleLabel("expanded", false), "Replier l'analyse");
  assert.equal(analysisToggleLabel("hidden", false), "Afficher l'analyse");
  assert.equal(analysisToggleLabel("expanded", true), "Ouvrir l'analyse");
});

const key = (overrides: Partial<Parameters<typeof isLibraryShortcut>[0]> = {}) => ({ key: "b", ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, repeat: false, target: { tagName: "BODY" }, ...overrides });

test("Ctrl+B and Cmd+B toggle the library, except while typing a question", () => {
  assert.equal(isLibraryShortcut(key()), true);
  assert.equal(isLibraryShortcut(key({ ctrlKey: false, metaKey: true })), true);
  assert.equal(isLibraryShortcut(key({ key: "B", target: { tagName: "BUTTON" } })), true);
  assert.equal(isLibraryShortcut(key({ target: { tagName: "INPUT" } })), true, "le filtre de la bibliothèque n'est pas la zone de question");
  assert.equal(isLibraryShortcut(key({ target: { tagName: "TEXTAREA" } })), false, "zone de question");
  assert.equal(isLibraryShortcut(key({ target: { tagName: "DIV", isContentEditable: true } })), false);
});

test("other combinations and held keys do not toggle the library", () => {
  assert.equal(isLibraryShortcut(key({ ctrlKey: false })), false);
  assert.equal(isLibraryShortcut(key({ altKey: true })), false);
  assert.equal(isLibraryShortcut(key({ shiftKey: true, key: "B" })), false);
  assert.equal(isLibraryShortcut(key({ repeat: true })), false);
  assert.equal(isLibraryShortcut(key({ key: "n" })), false);
  assert.equal(isLibraryShortcut(key({ target: null })), true);
});

test("the panel grid always has five tracks and keeps the reader on the third, elastic one", () => {
  const tracks = (template: string) => template.match(/minmax\([^)]*\)|\S+/g) ?? [];
  const cases: [compact: boolean, library: LibraryMode, analysis: AnalysisMode, expected: string][] = [
    [false, "expanded", "expanded", "22% 5px minmax(0, 1fr) 5px 30%"],
    [false, "rail", "expanded", "64px 0px minmax(0, 1fr) 5px 30%"],
    [false, "hidden", "expanded", "0px 0px minmax(0, 1fr) 5px 30%"],
    [false, "expanded", "hidden", "22% 5px minmax(0, 1fr) 0px 0px"],
    [false, "rail", "hidden", "64px 0px minmax(0, 1fr) 0px 0px"],
    [false, "hidden", "hidden", "0px 0px minmax(0, 1fr) 0px 0px"],
    [true, "expanded", "expanded", "0px 0px minmax(0, 1fr) 0px 0px"],
    [true, "rail", "hidden", "0px 0px minmax(0, 1fr) 0px 0px"],
  ];
  for (const [compact, library, analysis, expected] of cases) {
    const template = panelGridColumns({ compact, library, analysis, widths: [22, 30] });
    assert.equal(template, expected, `${compact ? "compact" : "large"}, ${library}, ${analysis}`);
    assert.equal(tracks(template).length, 5);
    assert.equal(tracks(template)[2], "minmax(0, 1fr)");
  }
});

test("the compact layout query is Tailwind's lg breakpoint", () => {
  assert.equal(COMPACT_LAYOUT_QUERY, "(width < 64rem)");
});
