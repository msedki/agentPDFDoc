/**
 * Outils partagés par accessibility.test.ts et ui-guards.test.ts : lecture des
 * sources de `src/`, des jetons HSL de theme.css et des règles CSS, calcul du
 * contraste WCAG 2.x. Les valeurs sont lues dans les fichiers, jamais recopiées.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const webRoot = fileURLToPath(new URL("../../", import.meta.url));
export const srcRoot = join(webRoot, "src");

export function readSource(relativePath: string): string { return readFileSync(join(srcRoot, relativePath), "utf8"); }

/** Fichiers de `src/` dont le nom correspond au motif, en chemins relatifs à `src/` avec des « / ». */
export function sourceFiles(pattern: RegExp, directory = srcRoot, found: string[] = []): string[] {
  for (const entry of readdirSync(directory)) {
    const full = join(directory, entry);
    if (statSync(full).isDirectory()) sourceFiles(pattern, full, found);
    else if (pattern.test(entry)) found.push(relative(srcRoot, full).split(sep).join("/"));
  }
  return found.sort();
}

export function stripCssComments(css: string): string { return css.replace(/\/\*[\s\S]*?\*\//g, ""); }
export function stripScriptComments(code: string): string {
  return code.replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

export type Rgb = [number, number, number];
export type Hsl = [number, number, number];

/** Jetons `--nom: H S% L%` du bloc :root de theme.css. */
export function themeTokens(css = readSource("app/theme.css")): Map<string, Hsl> {
  const clean = stripCssComments(css);
  const start = clean.indexOf(":root");
  const root = clean.slice(start, clean.indexOf("}", start));
  const tokens = new Map<string, Hsl>();
  for (const [, name, h, s, l] of root.matchAll(/--([\w-]+):\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%\s*;/g)) tokens.set(name, [Number(h), Number(s), Number(l)]);
  return tokens;
}

export function hslToRgb([h, s, l]: Hsl): Rgb {
  const saturation = s / 100; const lightness = l / 100;
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
  const x = chroma * (1 - Math.abs((h / 60) % 2 - 1));
  const m = lightness - chroma / 2;
  const [r, g, b] = ([[chroma, x, 0], [x, chroma, 0], [0, chroma, x], [0, x, chroma], [x, 0, chroma], [chroma, 0, x]] as const)[Math.floor(h / 60) % 6];
  return [(r + m) * 255, (g + m) * 255, (b + m) * 255];
}

export function hexToRgb(hex: string): Rgb {
  const value = hex.length === 4 ? `#${[...hex.slice(1)].map(digit => digit + digit).join("")}` : hex;
  return [1, 3, 5].map(offset => parseInt(value.slice(offset, offset + 2), 16)) as Rgb;
}

export function luminance(rgb: Rgb): number {
  const [r, g, b] = rgb.map(channel => channel / 255).map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(foreground: Rgb, background: Rgb): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

/** Couleur affichée d'un premier plan d'opacité `alpha` posé sur un fond opaque (mélange sRGB). */
export function composite(foreground: Rgb, alpha: number, background: Rgb): Rgb {
  return foreground.map((channel, index) => alpha * channel + (1 - alpha) * background[index]) as Rgb;
}

/** Couleur d'un jeton, éventuellement translucide, rendue sur `backdrop`. */
export function tokenColor(tokens: Map<string, Hsl>, name: string, alpha = 1, backdrop?: Rgb): Rgb {
  const value = tokens.get(name);
  if (!value) throw new Error(`jeton absent de theme.css : --${name}`);
  const rgb = hslToRgb(value);
  if (alpha === 1) return rgb;
  if (!backdrop) throw new Error(`fond requis pour composer --${name} / ${alpha}`);
  return composite(rgb, alpha, backdrop);
}

/** `hsl(var(--x))` ou `hsl(var(--x) / 0.6)` : nom du jeton et opacité. */
export function tokenReference(value: string): { name: string; alpha: number } | null {
  const match = /^hsl\(var\(--([\w-]+)\)(?:\s*\/\s*([\d.]+))?\)$/.exec(value.trim());
  return match ? { name: match[1], alpha: match[2] ? Number(match[2]) : 1 } : null;
}

/** Règles de premier niveau (hors @media, @keyframes, @layer, @theme), sélecteurs normalisés. */
export function topLevelRules(source: string): Map<string, Map<string, string>> {
  const css = stripCssComments(source);
  let flat = ""; let index = 0;
  while (index < css.length) {
    const at = css.indexOf("@", index);
    if (at < 0) { flat += css.slice(index); break; }
    flat += css.slice(index, at);
    const brace = css.indexOf("{", at); const semicolon = css.indexOf(";", at);
    if (semicolon >= 0 && (brace < 0 || semicolon < brace)) { index = semicolon + 1; continue; }
    let depth = 0; let cursor = brace;
    do { if (css[cursor] === "{") depth++; else if (css[cursor] === "}") depth--; cursor++; } while (depth > 0 && cursor < css.length);
    index = cursor;
  }
  const rules = new Map<string, Map<string, string>>();
  for (const [, selectors, body] of flat.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    for (const selector of selectors.split(",").map(value => value.trim().replace(/\s+/g, " "))) {
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

/** Toutes les règles, y compris celles des blocs @media, avec leur sélecteur et leurs déclarations. */
export function allRules(source: string): { selector: string; declarations: Map<string, string> }[] {
  const found: { selector: string; declarations: Map<string, string> }[] = [];
  for (const [, selector, body] of stripCssComments(source).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const declarations = new Map<string, string>();
    for (const declaration of body.split(";")) {
      const colon = declaration.indexOf(":");
      if (colon > 0) declarations.set(declaration.slice(0, colon).trim(), declaration.slice(colon + 1).trim());
    }
    found.push({ selector: selector.trim().replace(/\s+/g, " "), declarations });
  }
  return found;
}
