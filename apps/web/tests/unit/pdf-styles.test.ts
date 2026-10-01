/**
 * Styles PDF.js de l'atelier : seules les règles TextLayer, recopiées et cantonnées à
 * `.pdf-paper` dans pdf-text-layer.css, sont chargées. La feuille complète du visualiseur
 * PDF.js (web/pdf_viewer.css) n'est pas importée : elle redéfinit `:root` après theme.css.
 * Les règles recopiées sont comparées à la version installée de pdfjs-dist à chaque exécution.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import test from "node:test";
import { readSource, srcRoot, stripCssComments, webRoot } from "./theme-support.ts";

type Rule = { selector: string; declarations: Map<string, string>; children: Rule[] };

/** Règles CSS imbriquées (syntaxe de nesting comprise) : déclarations directes et règles enfants. */
function parseRules(css: string): Rule[] {
  const source = stripCssComments(css);
  let cursor = 0;
  function block(): { declarations: Map<string, string>; children: Rule[] } {
    const declarations = new Map<string, string>();
    const children: Rule[] = [];
    let buffer = "";
    while (cursor < source.length) {
      const char = source[cursor++];
      if (char === "{") {
        const selector = buffer.trim();
        buffer = "";
        const inner = block();
        children.push({ selector, ...inner });
      } else if (char === "}") {
        break;
      } else if (char === ";") {
        const separator = buffer.indexOf(":");
        if (separator > 0) declarations.set(buffer.slice(0, separator).trim(), buffer.slice(separator + 1).replace(/\s+/g, " ").trim());
        buffer = "";
      } else {
        buffer += char;
      }
    }
    const rest = buffer.trim();
    const separator = rest.indexOf(":");
    if (separator > 0 && !rest.includes("{")) declarations.set(rest.slice(0, separator).trim(), rest.slice(separator + 1).replace(/\s+/g, " ").trim());
    return { declarations, children };
  }
  return block().children;
}

/** Parties d'une liste de sélecteurs, sans couper les virgules entre parenthèses (`:is(span, br)`). */
function topLevelParts(selector: string): string[] {
  const parts: string[] = [];
  let depth = 0; let current = "";
  for (const char of selector) {
    if (char === "(") depth++;
    if (char === ")") depth--;
    if (char === "," && depth === 0) { parts.push(current.trim()); current = ""; } else current += char;
  }
  return [...parts, current.trim()];
}
const normalizeSelector = (selector: string) => selector.replace(/\s+/g, " ").replace(/\s*,\s*/g, ", ").trim();
/** Déclarations hors préfixes propriétaires (-webkit-, -moz-), que la copie n'a pas besoin de reprendre. */
function standard(declarations: Map<string, string>): Record<string, string> {
  return Object.fromEntries([...declarations].filter(([property]) => !/^-(?:webkit|moz)-/.test(property)).sort(([left], [right]) => left.localeCompare(right)));
}
function find(rules: Rule[], selector: string): Rule {
  const found = rules.find(rule => normalizeSelector(rule.selector) === normalizeSelector(selector));
  assert.ok(found, `règle ${selector} introuvable`);
  return found;
}

const pdfjsRoot = dirname(createRequire(join(webRoot, "package.json")).resolve("pdfjs-dist/package.json"));
const installedCss = readFileSync(join(pdfjsRoot, "web/pdf_viewer.css"), "utf8");
const installed = parseRules(installedCss);
const scoped = parseRules(readSource("app/pdf-text-layer.css"));
const pdfjsVersion = (JSON.parse(readFileSync(join(pdfjsRoot, "package.json"), "utf8")) as { version: string }).version;

/** `color-scheme` effectif de `:root` : dernière déclaration directe, feuilles importées par globals.css dans l'ordre. */
function effectiveRootColorScheme(): string | undefined {
  let value: string | undefined;
  const globals = stripCssComments(readSource("app/globals.css"));
  for (const [, target] of globals.matchAll(/@import\s+"([^"]+)"/g)) {
    if (target === "tailwindcss") continue;
    const css = target.startsWith("./") ? readFileSync(join(srcRoot, "app", target), "utf8") : readFileSync(createRequire(join(webRoot, "package.json")).resolve(target), "utf8");
    for (const rule of parseRules(css)) if (rule.selector === ":root" && rule.declarations.has("color-scheme")) value = rule.declarations.get("color-scheme");
  }
  for (const rule of parseRules(globals)) if (rule.selector === ":root" && rule.declarations.has("color-scheme")) value = rule.declarations.get("color-scheme");
  return value;
}

test("the light-only theme keeps color-scheme light: the whole PDF.js viewer stylesheet is not imported", () => {
  // pdf_viewer.css déclare `:root { color-scheme: light dark }` ; importée après theme.css, elle l'emportait.
  assert.ok(installed.some(rule => rule.selector === ":root" && rule.declarations.get("color-scheme") === "light dark"),
    "la feuille installée ne redéfinit plus color-scheme sur :root : revoir ce test");
  assert.doesNotMatch(stripCssComments(readSource("app/globals.css")), /pdfjs-dist\/web\/pdf_viewer\.css/);
  assert.equal(effectiveRootColorScheme(), "light");
});

test("the scoped TextLayer rules are those of the installed pdfjs-dist", () => {
  assert.match(readSource("app/pdf-text-layer.css"), new RegExp(`pdfjs-dist ${pdfjsVersion.replaceAll(".", "\\.")} web/pdf_viewer\\.css`), "version recopiée = version installée");
  const base = find(installed, ".textLayer");
  assert.deepEqual(standard(find(scoped, ".pdf-paper .textLayer").declarations), standard(base.declarations));
  for (const child of [":is(span, br)", "> :not(.markedContent), .markedContent span:not(.markedContent)", ".markedContent", 'span[role="img"]']) {
    // La copie préfixe chaque partie d'une liste de sélecteurs imbriqués par `.pdf-paper .textLayer`.
    const selector = topLevelParts(child).map(part => `.pdf-paper .textLayer ${part}`).join(", ");
    assert.deepEqual(standard(find(scoped, selector).declarations), standard(find(base.children, child).declarations), child);
  }
  for (const angle of ["90", "180", "270"]) {
    assert.equal(find(scoped, `.pdf-paper .textLayer[data-main-rotation="${angle}"]`).declarations.get("transform"), find(installed, `[data-main-rotation="${angle}"]`).declarations.get("transform"), `rotation ${angle}`);
  }
});

test("the TextLayer API used by the reader creates no element styled only by the full viewer stylesheet", () => {
  // TextLayer (display) crée des span, br et span.markedContent ; son canvas de mesure porte un style en ligne.
  // .endOfContent, .highlight, .selecting et .highlighting appartiennent au visualiseur complet et à l'éditeur.
  const pdf = readFileSync(join(pdfjsRoot, "build/pdf.mjs"), "utf8");
  const start = pdf.indexOf("class TextLayer {");
  const textLayer = pdf.slice(start, pdf.indexOf("\n}\n", start));
  assert.ok(start > 0 && textLayer.length > 1000, "classe TextLayer lue dans build/pdf.mjs");
  const classes = [...textLayer.matchAll(/classList\.add\("([^"]+)"\)|className = "([^"]+)"/g)].map(match => match[1] ?? match[2]);
  assert.deepEqual([...new Set(classes)], ["markedContent"]);
  assert.match(textLayer, /canvas\.style\.cssText = "position:absolute;top:0;left:0;width:0;height:0;display:none;"/);
  // Le lecteur n'active pas les images du TextLayer (option `images`), dont les classes ne sont pas recopiées.
  assert.doesNotMatch(stripCssComments(readSource("components/pdf-viewer.tsx")), /new pdfjs\.TextLayer\(\{[^}]*\bimages\b/);
});
