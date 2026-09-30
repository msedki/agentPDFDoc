import assert from "node:assert/strict";
import test from "node:test";
import { tabKeyTarget } from "../../src/lib/keyboard.ts";
import { composite, contrast, hexToRgb, readSource, themeTokens, tokenColor, tokenReference, topLevelRules, type Rgb } from "./theme-support.ts";

const tokens = themeTokens();
const rules = topLevelRules(readSource("app/globals.css"));

/** Couleur d'une déclaration `hsl(var(--jeton)[ / alpha])`, composée sur `backdrop` si elle est translucide. */
function resolve(value: string, backdrop?: Rgb): Rgb {
  const reference = tokenReference(value);
  assert.ok(reference, `couleur hors jeton : ${value}`);
  return tokenColor(tokens, reference.name, reference.alpha, backdrop);
}
function declaration(selector: string, property: "color" | "background"): string {
  const value = rules.get(selector)?.get(property);
  assert.ok(value, `${selector} ne déclare pas ${property}`);
  return value;
}
const page = tokenColor(tokens, "background");

test("the WCAG relative luminance formula matches its reference values", () => {
  assert.equal(contrast(hexToRgb("#000000"), hexToRgb("#ffffff")), 21);
  assert.equal(Math.round(contrast(hexToRgb("#777777"), hexToRgb("#ffffff")) * 100) / 100, 4.48);
});

test("the HSL tokens are read from theme.css and convert back to the project hues", () => {
  assert.ok(tokens.size >= 30, `${tokens.size} jetons lus`);
  const hex = (rgb: Rgb) => `#${rgb.map(channel => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
  assert.equal(hex(tokenColor(tokens, "primary")), "#a94324");
  assert.equal(hex(tokenColor(tokens, "foreground")), "#172b33");
  assert.equal(hex(tokenColor(tokens, "background")), "#f6f4ee");
});

test("essential text token pairs from theme.css reach WCAG AA 4.5:1", () => {
  const pairs: [string, string][] = [["foreground", "card"], ["foreground", "background"], ["muted-foreground", "card"], ["muted-foreground", "background"], ["muted-foreground", "muted"], ["muted-foreground", "sidebar"], ["muted-foreground", "reader"], ["primary", "card"], ["primary", "background"], ["primary", "accent"], ["accent-foreground", "accent"], ["primary-foreground", "primary"], ["destructive", "card"], ["destructive", "destructive-muted"], ["warning", "warning-muted"], ["success", "success-muted"], ["info", "info-muted"]];
  for (const [foreground, background] of pairs) {
    const ratio = contrast(tokenColor(tokens, foreground), tokenColor(tokens, background));
    assert.ok(ratio >= 4.5, `--${foreground} sur --${background} : ${ratio.toFixed(2)}`);
  }
});

test("current text rules keep WCAG AA 4.5:1 on their declared backgrounds", () => {
  const pairs: [string, string][] = [
    [".eyebrow", ".app-topbar"], [".eyebrow", ".scope-trigger"], [".eyebrow", ".scope-trigger:hover"], [".topbar-service", ".app-topbar"], [".context-scope", ".context-band"], [".context-service", ".context-band"],
    [".skip-links a", ".skip-links a"], [".shortcut-list dd", ".help-popover"], [".help-note", ".help-popover"], ["kbd", "kbd"], [".page-caption", ".viewer-panel"], [".panel-empty", ".viewer-panel"], [".panel-empty h3", ".viewer-panel"],
    [".tree-document small", ".library-panel"], [".tree-document small", ".tree-document:hover"], [".tree-document small", ".tree-document.is-open"],
    [".library-notice", ".library-panel"], [".library-notice.action-error", ".library-panel"], [".library-all.is-active", ".library-all.is-active"],
    [".analysis-tabs button", ".analysis-panel"], ['.analysis-tabs button[aria-selected="true"]', ".analysis-panel"], [".scope-summary > span:last-child:not(.eyebrow)", ".scope-summary"],
    [".composer-footer > span", ".composer-area form"], [".source-card-meta", ".source-card"], [".source-card-excerpt", ".source-card"], [".source-id", ".source-card"], [".source-card-footer", ".source-card"],
    [".inline-warning", ".viewer-notice"], [".inline-warning", ".analysis-panel"], [".inline-error", ".analysis-panel"], [".action-error", ".document-tools-menu"], [".invalid-citation", ".analysis-panel"], [".inline-citation", ".inline-citation"],
    [".readiness-notice", ".readiness-notice"], [".workspace-error", ".workspace-error"], [".panel-message", ".panel-message"], [".panel-message-error", ".panel-message-error"], [".panel-message-error span", ".panel-message-error"],
    [".source-navigation strong", ".source-navigation"], [".document-tools-menu .document-tools-hash", ".document-tools-menu"], [".reader-footer", ".reader-footer"], [".result-count", ".analysis-panel"],
    [".query-status", ".analysis-panel"], [".question-message small", ".analysis-panel"], [".job-heading > span", ".sheet"], [".scope-help", ".scope-popover"],
  ];
  // Les fonds translucides (survol de la bibliothèque) sont composés sur le fond de leur panneau.
  const panel = resolve(declaration(".library-panel", "background"), page);
  for (const [foreground, background] of pairs) {
    const surface = resolve(declaration(background, "background"), panel);
    const ratio = contrast(resolve(declaration(foreground, "color"), surface), surface);
    assert.ok(ratio >= 4.5, `${foreground} sur ${background} : ${ratio.toFixed(2)}`);
  }
});

test("composited colors follow the sRGB alpha blend", () => {
  assert.deepEqual(composite([0, 0, 0], 0.5, [255, 255, 255]), [127.5, 127.5, 127.5]);
  assert.deepEqual(composite([90, 102, 109], 1, [249, 248, 242]), [90, 102, 109]);
});

test("placeholders override the half-transparent Tailwind default and reach 4.5:1 on their fields", () => {
  // Sans règle propre, le preflight Tailwind (@layer base) rend l'encre à 50 % : environ 3,1:1 sur blanc.
  const placeholder = resolve(declaration("::placeholder", "color"));
  for (const field of [".composer-area textarea", ".library-filter", ".viewer-search", ".scope-popover input", ".page-input input"]) {
    const ratio = contrast(placeholder, resolve(declaration(field, "background")));
    assert.ok(ratio >= 4.5, `placeholder sur ${field} : ${ratio.toFixed(2)}`);
  }
});

test("the icon-only folder scope button keeps 3:1 non-text contrast", () => {
  const panel = resolve(declaration(".library-panel", "background"));
  const alpha = Number(rules.get(".folder-scope")?.get("opacity") ?? 1);
  const ratio = contrast(composite(resolve(declaration(".folder-scope", "color")), alpha, panel), panel);
  assert.ok(ratio >= 3, `.folder-scope sur .library-panel : ${ratio.toFixed(2)}`);
});

test("essential controls keep a visible focus indicator on the ring token", () => {
  for (const selector of ["button:focus-visible", "input:focus-visible", "select:focus-visible", "textarea:focus-visible", "summary:focus-visible", "a:focus-visible", ".panel-resizer:focus-visible", ".analysis-history:focus-visible", ".library-filter:focus-within", ".reader-slot:focus-visible"]) {
    assert.match(rules.get(selector)?.get("outline") ?? "", /^2px solid hsl\(var\(--ring\)\)$/, selector);
  }
  // Le textarea masque son contour : le formulaire parent porte l'indicateur.
  assert.equal(rules.get(".composer-area textarea:focus-visible")?.get("outline"), "0");
  assert.match(rules.get(".composer-area form:focus-within")?.get("box-shadow") ?? "", /hsl\(var\(--ring\)\)/);
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
