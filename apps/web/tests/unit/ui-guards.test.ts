/**
 * Gardes statiques de l'interface (lot R16), lues dans `src/` à chaque exécution.
 *
 * Chaque garde commence par vérifier qu'elle examine une population non vide :
 * un fichier renommé ou un motif devenu introuvable la ferait sinon passer à vide.
 * La non-vacuité porte sur ce qui est examiné, jamais sur les fautes trouvées.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { allRules, composite, contrast, readSource, sourceFiles, stripCssComments, stripScriptComments, themeTokens, tokenColor, tokenReference, type Rgb } from "./theme-support.ts";
import { documentStates, jobStates, queryStates, type Tone } from "../../src/lib/status.ts";

const THEME = "app/theme.css";
const scripts = sourceFiles(/\.tsx?$/);
const components = scripts.filter(file => file.endsWith(".tsx"));
const styles = sourceFiles(/\.css$/);
const code = new Map(scripts.map(file => [file, stripScriptComments(readSource(file))]));
const css = new Map(styles.map(file => [file, stripCssComments(readSource(file))]));
const tokens = themeTokens();

type Element = { name: string; attributes: string; content: string; index: number };

/** Éléments JSX `<nom …>` : attributs jusqu'au `>` de profondeur 0, contenu jusqu'à la fermeture. */
function jsxElements(source: string, names: string[]): Element[] {
  const found: Element[] = [];
  for (const match of source.matchAll(new RegExp(`<(${names.join("|")})(?=[\\s>/])`, "g"))) {
    const start = match.index! + match[0].length;
    let depth = 0; let quote = ""; let cursor = start;
    for (; cursor < source.length; cursor++) {
      const char = source[cursor];
      if (quote) { if (char === quote) quote = ""; continue; }
      if (char === "\"" || char === "'" || char === "`") quote = char;
      else if (char === "{") depth++;
      else if (char === "}") depth--;
      else if (char === ">" && depth === 0) break;
    }
    const attributes = source.slice(start, cursor);
    const close = attributes.trimEnd().endsWith("/") ? -1 : source.indexOf(`</${match[1]}>`, cursor);
    found.push({ name: match[1], attributes, content: close < 0 ? "" : source.slice(cursor + 1, close), index: match.index! });
  }
  return found;
}

const ICON = "\u0000icône\u0000";
const letters = /[A-Za-zÀ-ÿ0-9]/;
/** Le contenu d'un bouton produit-il un texte visible ? Les icônes auto-fermantes n'en produisent pas. */
function rendersText(content: string): boolean {
  const withoutIcons = content.replace(/<[A-Z][\w.]*\b[^<>]*?\/>/g, ICON);
  let depth = 0; let outside = ""; let current = "";
  const expressions: string[] = [];
  for (const char of withoutIcons) {
    if (char === "{" && depth++ === 0) { current = ""; continue; }
    if (char === "}" && --depth === 0) { expressions.push(current); continue; }
    if (depth === 0) outside += char; else current += char;
  }
  if (letters.test(outside.replace(/<[^>]*>/g, "").replaceAll(ICON, ""))) return true;
  return expressions.some(expression => {
    const operands = expression.replace(/(?:===|!==|==|!=)\s*(["'`])[^"'`]*\1/g, "").replace(/(["'`])[^"'`]*\1\s*(?:===|!==|==|!=)/g, "");
    if (!operands.includes(ICON) && !operands.includes("<")) return operands.trim() !== "";
    return /(["'`])[^"'`]*[A-Za-zÀ-ÿ][^"'`]*\1/.test(operands) || />[^<>{}]*[A-Za-zÀ-ÿ][^<>{}]*</.test(operands);
  });
}

test("text never goes below 10 px, stays on the type scale, and 10 px is reserved for uppercase overlines", () => {
  const scale = new Set([10, 11, 12, 14, 16, 18]);
  const offenders: string[] = [];
  let examined = 0;
  for (const [file, source] of css) {
    for (const { selector, declarations } of allRules(source)) {
      const size = /^(\d+(?:\.\d+)?)px$/.exec(declarations.get("font-size")?.replace("!important", "").trim() ?? "");
      if (!size) continue;
      examined++;
      const value = Number(size[1]);
      if (!scale.has(value)) offenders.push(`${file} ${selector} : ${value}px hors échelle`);
      if (value === 10 && declarations.get("text-transform") !== "uppercase") offenders.push(`${file} ${selector} : 10px sans capitales`);
    }
  }
  for (const [file, source] of code) {
    for (const match of source.matchAll(/text-\[(\d+(?:\.\d+)?)px\]/g)) {
      examined++;
      const value = Number(match[1]);
      const classes = source.slice(source.lastIndexOf("\"", match.index!), source.indexOf("\"", match.index!));
      if (!scale.has(value)) offenders.push(`${file} text-[${value}px] hors échelle`);
      if (value === 10 && !/\buppercase\b/.test(classes)) offenders.push(`${file} text-[10px] sans capitales`);
    }
    for (const match of source.matchAll(/fontSize:\s*(\d+(?:\.\d+)?)\b/g)) { examined++; if (Number(match[1]) < 10) offenders.push(`${file} fontSize ${match[1]}`); }
  }
  assert.ok(examined >= 40, `${examined} tailles de texte examinées`);
  assert.deepEqual(offenders, []);
});

test("typography uses local system stacks only: no remote font and no retired family", () => {
  const theme = readSource(THEME);
  assert.match(theme, /--font-family-sans:\s*system-ui/);
  assert.match(theme, /--font-family-mono:\s*ui-monospace/);
  const all = [...css.values(), ...code.values()];
  assert.ok(all.length >= 20, `${all.length} fichiers examinés`);
  for (const source of all) {
    assert.doesNotMatch(source, /fonts\.googleapis|fonts\.gstatic|@font-face/);
    assert.doesNotMatch(source, /Georgia|Bahnschrift|Trebuchet/);
  }
});

test("spacing stays on the 4 px grid, with 1-2 px optical adjustments only", () => {
  const offenders: string[] = [];
  let examined = 0;
  for (const { selector, declarations } of allRules(css.get("app/globals.css")!)) {
    for (const [property, value] of declarations) {
      if (!/^(?:padding|margin|gap|row-gap|column-gap)(?:-|$)/.test(property)) continue;
      for (const [, amount] of value.matchAll(/(-?\d+(?:\.\d+)?)px/g)) {
        examined++;
        const pixels = Math.abs(Number(amount));
        if (pixels % 4 !== 0 && pixels > 2) offenders.push(`${selector} ${property}: ${value}`);
      }
    }
  }
  assert.ok(examined >= 80, `${examined} espacements examinés`);
  assert.deepEqual(offenders, []);
});

test("icon-only buttons carry an accessible name", () => {
  const unnamed: string[] = [];
  let buttons = 0; let iconOnly = 0;
  for (const file of components) {
    for (const element of jsxElements(code.get(file)!, ["button", "Button", "summary"])) {
      buttons++;
      if (element.content === "" || rendersText(element.content)) continue;
      iconOnly++;
      if (!/aria-label(?:ledby)?=/.test(element.attributes)) unnamed.push(`${file} <${element.name}${element.attributes.slice(0, 80)}…>`);
    }
  }
  assert.ok(buttons >= 30, `${buttons} boutons examinés`);
  assert.ok(iconOnly >= 8, `${iconOnly} boutons-icônes reconnus : la détection ne reconnaît plus les icônes`);
  assert.deepEqual(unnamed, []);
});

test("form controls are labelled and every label designates a control", () => {
  const offenders: string[] = [];
  let controls = 0; let labels = 0;
  for (const file of components) {
    const source = code.get(file)!;
    for (const control of jsxElements(source, ["input", "select", "textarea"])) {
      if (/(^|\s)hidden(?=[\s/]|$)/.test(control.attributes) || /type="hidden"/.test(control.attributes)) continue;
      controls++;
      const id = /\bid="([^"]+)"/.exec(control.attributes)?.[1];
      const enclosed = source.lastIndexOf("<label", control.index) > source.lastIndexOf("</label>", control.index);
      if (!/aria-label(?:ledby)?=/.test(control.attributes) && !(id && source.includes(`htmlFor="${id}"`)) && !enclosed) offenders.push(`${file} <${control.name}${control.attributes.slice(0, 60)}…>`);
    }
    for (const label of jsxElements(source, ["label"])) {
      labels++;
      if (!/htmlFor=/.test(label.attributes) && !/<(?:input|select|textarea)\b/.test(label.content)) offenders.push(`${file} <label> sans contrôle`);
    }
  }
  assert.ok(controls >= 8, `${controls} champs examinés`);
  assert.ok(labels >= 6, `${labels} libellés examinés`);
  assert.deepEqual(offenders, []);
});

const PALETTE = /\b(?:bg|text|border|outline|ring|fill|stroke|from|to|via|accent|caret|decoration|divide|placeholder|shadow)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b|\b(?:bg|text|border|outline|ring|fill|stroke)-(?:white|black)\b|-\[#/;
const HEX = /#[0-9a-fA-F]{3,8}\b/;
const LITERAL_FUNCTION = /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb|color-mix)\((?!var\()/;
const NAMED = /(?:^|[\s,(])(?:white|black|red|green|blue|orange|yellow|gray|grey|silver|navy|maroon|purple|teal)(?=[\s,)!]|$)/i;

test("colours come from theme tokens only; theme.css is the single documented exception", () => {
  const offenders: string[] = [];
  let tokenUses = 0;
  for (const [file, source] of css) {
    if (file === THEME) continue;
    if (HEX.test(source)) offenders.push(`${file} : ${HEX.exec(source)![0]}`);
    if (LITERAL_FUNCTION.test(source)) offenders.push(`${file} : ${LITERAL_FUNCTION.exec(source)![0]}`);
    for (const { selector, declarations } of allRules(source)) {
      for (const [property, value] of declarations) {
        if (!/color|background|border|outline|fill|stroke|shadow/.test(property)) continue;
        tokenUses += value.match(/hsl\(var\(--/g)?.length ?? 0;
        if (NAMED.test(value)) offenders.push(`${file} ${selector} ${property}: ${value}`);
      }
    }
  }
  for (const [file, source] of code) {
    for (const pattern of [HEX, LITERAL_FUNCTION, PALETTE]) if (pattern.test(source)) offenders.push(`${file} : ${pattern.exec(source)![0]}`);
  }
  assert.ok(styles.length >= 3 && scripts.length >= 25, `${styles.length} feuilles et ${scripts.length} scripts examinés`);
  assert.ok(tokenUses >= 60, `${tokenUses} couleurs de jeton examinées`);
  assert.deepEqual(offenders, []);
  // Le fichier de jetons ne porte que des triplets HSL ; la liste blanche PDF y est commentée.
  const theme = readSource(THEME);
  assert.doesNotMatch(stripCssComments(theme), HEX);
  assert.match(theme, /Liste blanche/);
  for (const name of ["pdf-page", "highlight-source", "highlight-search", "highlight-selection"]) assert.ok(tokens.has(name), `--${name}`);
});

test("no dark: variant or dark media query exists while no dark theme is declared", () => {
  const theme = stripCssComments(readSource(THEME));
  assert.match(theme, /color-scheme:\s*light/);
  const darkDeclared = /\.dark\b|\[data-theme="dark"\]|prefers-color-scheme:\s*dark/.test(theme);
  const offenders = [...code, ...css].filter(([file, source]) => file !== THEME && /(?:^|[\s"'`])dark:|prefers-color-scheme:\s*dark/.test(source)).map(([file]) => file);
  assert.ok(code.size + css.size >= 25);
  if (!darkDeclared) assert.deepEqual(offenders, []);
});

const AA = 4.5;
const surfaces = ["card", "background", "popover"].map(name => [name, tokenColor(tokens, name)] as const);

test("badge tone pairs reach 4.5:1 and every status tone has a badge variant", () => {
  const badge = readSource("components/ui/badge.tsx");
  const pairs = [...badge.matchAll(/"bg-([\w-]+)(?:\/(\d+))?\s+text-([\w-]+)"/g)];
  assert.ok(pairs.length >= 5, `${pairs.length} couples de badge lus`);
  for (const [source, background, opacity, foreground] of pairs) {
    for (const [surface, rgb] of surfaces) {
      const fill = tokenColor(tokens, background, opacity ? Number(opacity) / 100 : 1, rgb);
      const ratio = contrast(tokenColor(tokens, foreground), fill);
      assert.ok(ratio >= AA, `${source} sur ${surface} : ${ratio.toFixed(2)}`);
    }
  }
  const tones = new Set<Tone>(["neutral", ...[documentStates, jobStates, queryStates].flatMap(table => Object.values(table).map(([, tone]) => tone as Tone))]);
  for (const tone of tones) assert.match(badge, new RegExp(`\\b${tone}:\\s*"bg-`), `variante ${tone} absente de badge.tsx`);
});

test("status dots keep 3:1 non-text contrast on every panel surface", () => {
  const rules = allRules(css.get("app/globals.css")!);
  const dots = rules.filter(rule => /\.status-dot$/.test(rule.selector) && rule.declarations.has("background"));
  assert.ok(dots.length >= 5, `${dots.length} pastilles lues`);
  for (const { selector, declarations } of dots) {
    const reference = tokenReference(declarations.get("background")!);
    assert.ok(reference, selector);
    for (const surface of ["card", "background", "sidebar", "sidebar-accent", "muted"]) {
      const ratio = contrast(tokenColor(tokens, reference.name), tokenColor(tokens, surface));
      assert.ok(ratio >= 3, `${selector} sur --${surface} : ${ratio.toFixed(2)}`);
    }
  }
});

test("button variants keep 4.5:1 at rest and on hover", () => {
  const button = readSource("components/ui/button.tsx");
  const variants = [...button.matchAll(/(\w+): "([^"]*\bbg-[\w-]+[^"]*\btext-[\w-]+[^"]*)"/g)];
  assert.ok(variants.length >= 3, `${variants.length} variantes lues`);
  for (const [, variant, classes] of variants) {
    const background = /(?:^|\s)bg-([\w-]+)(?=\s|$)/.exec(classes)![1];
    const foreground = /(?:^|\s)text-([\w-]+)(?=\s|$)/.exec(classes)![1];
    const hover = /hover:bg-([\w-]+)(?:\/(\d+))?/.exec(classes);
    for (const [surface, rgb] of surfaces) {
      const rest = tokenColor(tokens, background, 1, rgb);
      assert.ok(contrast(tokenColor(tokens, foreground), rest) >= AA, `${variant} au repos sur ${surface}`);
      if (hover) {
        const hovered: Rgb = tokenColor(tokens, hover[1], hover[2] ? Number(hover[2]) / 100 : 1, rgb);
        const ratio = contrast(tokenColor(tokens, foreground), hovered);
        assert.ok(ratio >= AA, `${variant} au survol sur ${surface} : ${ratio.toFixed(2)}`);
      }
    }
  }
  assert.match(button, /bg-primary text-primary-foreground/);
  assert.match(button, /focus-visible:outline-ring/);
  assert.match(button, /\[&_svg\]:size-4/);
});

test("a failed query or mutation is never rendered as an empty state", () => {
  const offenders: string[] = [];
  let queries = 0; let mutations = 0;
  for (const file of components) {
    const source = code.get(file)!;
    for (const [, name] of source.matchAll(/const (\w+) = useQuery\(/g)) {
      queries++;
      if (!new RegExp(`\\b${name}\\.(?:isError|error)\\b`).test(source)) offenders.push(`${file} : ${name} n'affiche pas son échec`);
    }
    for (const match of source.matchAll(/const (\w+) = useMutation\(/g)) {
      mutations++;
      let depth = 0; let cursor = match.index! + match[0].length - 1;
      do { if (source[cursor] === "(") depth++; else if (source[cursor] === ")") depth--; cursor++; } while (depth > 0 && cursor < source.length);
      const call = source.slice(match.index!, cursor);
      if (!/onError\s*:/.test(call) && !new RegExp(`\\b${match[1]}\\.(?:isError|error)\\b`).test(source)) offenders.push(`${file} : ${match[1]} n'affiche pas son échec`);
    }
    if (/(?:isError|\berror)\s*(?:\?|&&)\s*<PanelEmpty/.test(source)) offenders.push(`${file} : un échec rendu par PanelEmpty`);
  }
  assert.ok(queries >= 6, `${queries} requêtes examinées`);
  assert.ok(mutations >= 3, `${mutations} mutations examinées`);
  assert.deepEqual(offenders, []);
  const panel = readSource("components/ui/panel.tsx");
  const reasons = /type PanelEmptyReason = ([^;]+);/.exec(panel)?.[1] ?? "";
  assert.match(reasons, /"no-documents"/);
  assert.doesNotMatch(reasons, /unavailable|error|failure/);
});

test("no browser confirm or alert box: consequences and failures stay in the page", () => {
  assert.ok(code.size >= 25);
  for (const [file, source] of code) assert.doesNotMatch(source, /\b(?:window\.)?(?:confirm|alert)\(/, file);
  assert.match(readSource("components/document-tools.tsx"), /<ConfirmDialog\b/);
});

test("lucide icons use the normalized sizes: 12 badges, 14 secondary, 16 buttons, 32-40 empty states", () => {
  const allowed = new Set([12, 14, 16, 32, 40]);
  const offenders: string[] = [];
  let usages = 0;
  for (const file of components) {
    const source = code.get(file)!;
    const imported = [...source.matchAll(/import\s*\{([^}]+)\}\s*from\s*"lucide-react"/g)].flatMap(([, names]) => names.split(",").map(name => name.trim().split(/\s+as\s+/).at(-1)!).filter(Boolean));
    if (!imported.length) continue;
    for (const match of source.matchAll(new RegExp(`<(${[...imported, "Icon"].join("|")})\\b([^<>]*?)\\/>`, "g"))) {
      usages++;
      const size = /size=\{(\d+)\}/.exec(match[2]);
      if (!size || !allowed.has(Number(size[1]))) offenders.push(`${file} <${match[1]} ${match[2].trim()}>`);
    }
  }
  assert.ok(usages >= 30, `${usages} icônes examinées`);
  assert.deepEqual(offenders, []);
});

test("coloured status dots are rendered only by StatusIndicator, which always prints the label", () => {
  const indicator = readSource("components/ui/status-indicator.tsx");
  assert.match(indicator, /status-dot/);
  assert.match(indicator, /\{status\.label\}/);
  const dotUsers = components.filter(file => /status-dot|document-dot|activity-dot/.test(code.get(file)!));
  assert.deepEqual(dotUsers, ["components/ui/status-indicator.tsx"]);
  const indicatorUsers = components.filter(file => /<StatusIndicator\b/.test(code.get(file)!));
  assert.ok(indicatorUsers.length >= 3, `${indicatorUsers.length} composants utilisent StatusIndicator`);
});

test("every known state has a readable label distinct from its technical code", () => {
  const tables = { documentStates, jobStates, queryStates };
  let entries = 0;
  for (const [table, values] of Object.entries(tables)) {
    for (const [code, [label]] of Object.entries(values)) {
      entries++;
      assert.ok(label.trim().length > 2, `${table}.${code}`);
      assert.notEqual(label, code, `${table}.${code} affiche son code brut`);
    }
  }
  assert.ok(entries >= 40, `${entries} états examinés`);
});

test("shared helpers compose translucent tokens over their surface", () => {
  const card = tokenColor(tokens, "card");
  assert.deepEqual(tokenColor(tokens, "primary", 1, card), tokenColor(tokens, "primary"));
  const half = tokenColor(tokens, "primary", 0.5, card);
  assert.deepEqual(half, composite(tokenColor(tokens, "primary"), 0.5, card));
});
