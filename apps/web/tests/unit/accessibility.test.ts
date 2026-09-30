import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { tabKeyTarget } from "../../src/lib/keyboard.ts";

const css = readFileSync(new URL("../../src/app/globals.css", import.meta.url), "utf8");

/** Règles de premier niveau ; les blocs @media/@keyframes et les @import sont écartés. */
function topLevelRules(source: string) {
  let flat = ""; let index = 0;
  while (index < source.length) {
    const at = source.indexOf("@", index);
    if (at < 0) { flat += source.slice(index); break; }
    flat += source.slice(index, at);
    const brace = source.indexOf("{", at); const semicolon = source.indexOf(";", at);
    if (semicolon >= 0 && (brace < 0 || semicolon < brace)) { index = semicolon + 1; continue; }
    let depth = 0; let cursor = brace;
    do { if (source[cursor] === "{") depth++; else if (source[cursor] === "}") depth--; cursor++; } while (depth > 0 && cursor < source.length);
    index = cursor;
  }
  const rules = new Map<string, Map<string, string>>();
  for (const [, selectors, body] of flat.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    for (const selector of selectors.split(",").map(value => value.trim())) {
      const declarations = rules.get(selector) ?? new Map<string, string>();
      for (const declaration of body.split(";")) {
        const colon = declaration.indexOf(":");
        if (colon > 0) declarations.set(declaration.slice(0, colon).trim(), declaration.slice(colon + 1).trim());
      }
      rules.set(selector, declarations);
    }
  }
  return rules;
}
const rules = topLevelRules(css);
const tokens = rules.get(":root")!;

function color(value: string): string {
  const token = /^var\((--[\w-]+)\)$/.exec(value);
  const resolved = (token ? tokens.get(token[1]) : value) ?? "";
  const hex = resolved === "white" ? "#ffffff" : resolved;
  assert.match(hex, /^#([0-9a-f]{3}|[0-9a-f]{6})$/i, `couleur opaque attendue : ${value}`);
  return hex.length === 4 ? `#${[...hex.slice(1)].map(digit => digit + digit).join("")}` : hex;
}
function declared(selector: string, property: "color" | "background"): string {
  const value = rules.get(selector)?.get(property);
  assert.ok(value, `${selector} ne déclare pas ${property}`);
  return color(value.split(/\s+/)[0]);
}
function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16) / 255).map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(foreground: string, background: string) {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

test("the WCAG relative luminance formula matches its reference values", () => {
  assert.equal(contrast("#000000", "#ffffff"), 21);
  assert.equal(Math.round(contrast("#777777", "#ffffff") * 100) / 100, 4.48);
});

test("essential text token pairs from globals.css reach WCAG AA 4.5:1", () => {
  const pairs: [string, string][] = [["var(--ink)", "var(--surface)"], ["var(--ink)", "var(--paper)"], ["var(--subtle)", "var(--surface)"], ["var(--subtle)", "var(--paper)"], ["var(--accent)", "var(--surface)"], ["var(--accent)", "var(--paper)"], ["var(--accent)", "var(--accent-pale)"], ["white", "var(--accent)"]];
  for (const [foreground, background] of pairs) {
    const ratio = contrast(color(foreground), color(background));
    assert.ok(ratio >= 4.5, `${foreground} sur ${background} : ${ratio.toFixed(2)}`);
  }
});

test("current text rules keep WCAG AA 4.5:1 on their declared backgrounds", () => {
  const pairs: [string, string][] = [
    [".eyebrow", ".workspace-scope-bar"], [".readiness-badge", ".app-header"], [".page-caption", ".viewer-panel"], [".empty-state", ".viewer-empty"],
    [".tree-document small", ".library-panel"], [".tree-document small", ".tree-document:hover"], [".tree-document small", ".tree-document.is-open"],
    [".library-notice", ".library-panel"], [".library-all.is-active", ".library-all.is-active"], [".analysis-tabs button", ".analysis-panel"],
    [".analysis-tabs button[aria-selected=true]", ".analysis-panel"], [".scope-summary>span:last-child:not(.eyebrow)", ".scope-summary"],
    [".composer-footer>span", ".composer-area form"], [".source-card small", ".source-card"], [".source-card p", ".source-card"], [".source-id", ".source-card"],
    [".inline-warning", ".viewer-notice"], [".inline-warning", ".analysis-panel"], [".invalid-citation", ".analysis-panel"], [".inline-citation", ".inline-citation"],
    [".readiness-notice", ".readiness-notice"], [".workspace-error", ".workspace-error"], [".source-navigation strong", ".source-navigation"],
    [".document-tools-hash", ".document-tools-menu"], [".reader-footer", ".reader-footer"], [".result-count", ".analysis-panel"],
  ];
  for (const [foreground, background] of pairs) {
    const ratio = contrast(declared(foreground, "color"), declared(background, "background"));
    assert.ok(ratio >= 4.5, `${foreground} sur ${background} : ${ratio.toFixed(2)}`);
  }
});

/** Couleur affichée d'un premier plan d'opacité `alpha` sur un fond opaque (mélange sRGB). */
function composite(foreground: string, background: string, alpha: number) {
  const channel = (hex: string, offset: number) => parseInt(hex.slice(offset, offset + 2), 16);
  return `#${[1, 3, 5].map(offset => Math.round(alpha * channel(foreground, offset) + (1 - alpha) * channel(background, offset)).toString(16).padStart(2, "0")).join("")}`;
}

test("composited colors follow the sRGB alpha blend", () => {
  assert.equal(composite("#000000", "#ffffff", 0.5), "#808080");
  assert.equal(composite("#5a666d", "#f9f8f2", 1), "#5a666d");
});

test("placeholders override the half-transparent Tailwind default and reach 4.5:1 on their fields", () => {
  // Sans règle propre, le preflight Tailwind (@layer base) rend --ink à 50 % : environ 3,1:1 sur blanc.
  const placeholder = declared("::placeholder", "color");
  const fields = [".composer-area textarea", ".library-filter", ".viewer-search", ".scope-popover input", ".page-input input"];
  for (const field of fields) {
    const ratio = contrast(placeholder, declared(field, "background"));
    assert.ok(ratio >= 4.5, `placeholder sur ${field} : ${ratio.toFixed(2)}`);
  }
});

test("the icon-only folder scope button keeps 3:1 non-text contrast", () => {
  const rule = rules.get(".folder-scope");
  const alpha = Number(rule?.get("opacity") ?? 1);
  const ratio = contrast(composite(declared(".folder-scope", "color"), declared(".library-panel", "background"), alpha), declared(".library-panel", "background"));
  assert.ok(ratio >= 3, `.folder-scope sur .library-panel : ${ratio.toFixed(2)}`);
});

test("essential controls keep a visible focus indicator", () => {
  for (const selector of ["button:focus-visible", "input:focus-visible", "select:focus-visible", "textarea:focus-visible", "summary:focus-visible", ".panel-resizer:focus-visible", ".analysis-history:focus-visible", ".library-filter:focus-within"]) {
    assert.match(rules.get(selector)?.get("outline") ?? "", /^2px solid var\(--accent\)$/, selector);
  }
  // Le textarea masque son contour : le formulaire parent porte l'indicateur.
  assert.equal(rules.get(".composer-area textarea:focus-visible")?.get("outline"), "0");
  assert.match(rules.get(".composer-area form:focus-within")?.get("box-shadow") ?? "", /var\(--accent\)/);
});

test("analysis tabs follow arrow, Home and End keys with wrap-around", () => {
  assert.equal(tabKeyTarget("ArrowRight", 0, 3), 1);
  assert.equal(tabKeyTarget("ArrowRight", 2, 3), 0);
  assert.equal(tabKeyTarget("ArrowLeft", 0, 3), 2);
  assert.equal(tabKeyTarget("Home", 2, 3), 0);
  assert.equal(tabKeyTarget("End", 0, 3), 2);
  assert.equal(tabKeyTarget("Enter", 1, 3), null);
  assert.equal(tabKeyTarget("ArrowDown", 1, 3), null);
  assert.equal(tabKeyTarget("ArrowRight", 0, 0), null);
});
