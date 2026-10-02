/**
 * Gardes de structure de la coquille (lot R16, étape B), lues dans `src/`.
 *
 * Elles couvrent le câblage que les tests de fonctions pures ne voient pas :
 * zones nommées, liens d'évitement, panneaux latéraux natifs, points de
 * rupture, raccourcis annoncés dans l'Aide et emplacement unique de message.
 * Le comportement au rendu (focus, Échap, largeurs) reste à vérifier en E2E.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { allRules, readSource, sourceFiles, stripCssComments, stripScriptComments, topLevelRules } from "./theme-support.ts";
import { activeJobsSentence } from "../../src/lib/panel-state.ts";

const code = (file: string) => stripScriptComments(readSource(file));
const workspace = code("components/workspace.tsx");
const components = sourceFiles(/\.tsx$/).filter(file => file.startsWith("components/"));

test("named zones: aside Bibliothèque, main Lecteur, aside Analyse", () => {
  const library = code("components/library-panel.tsx");
  assert.match(library, /<aside className=\{`library-panel\$\{dropping \? " is-dropping" : ""\}`\} aria-labelledby="library-heading"/);
  assert.match(library, /<PanelHeader title="Bibliothèque" id="library-heading">/);
  const analysis = code("components/analysis-panel.tsx");
  assert.match(analysis, /<aside className="analysis-panel" aria-labelledby="analysis-heading">/);
  assert.match(analysis, /<PanelHeader title="Analyse" id="analysis-heading">/);
  assert.match(workspace, /<main id="lecteur" className="reader-slot" aria-label="Lecteur" tabIndex=\{-1\}><PdfViewer \/><\/main>/);
  assert.ok(components.length >= 10, `${components.length} composants examinés`);
  const mains = components.filter(file => /<main\b/.test(code(file)));
  assert.deepEqual(mains, ["components/session-gate.tsx", "components/workspace.tsx"], "un <main> pour l'atelier, un pour l'écran de session");
  // Les deux ne coexistent jamais : la garde de session rend l'atelier ou son propre écran, pas les deux.
  const gate = code("components/session-gate.tsx");
  assert.ok(/if \(state\.kind === "open"\) return <SessionContext\.Provider[^;]*\{children\}/.test(gate), "atelier rendu seul quand la session est ouverte");
  assert.ok(gate.indexOf("{children}") < gate.indexOf("<main"), "l'écran de session n'est rendu qu'à défaut de l'atelier");
  assert.ok(!/<Workspace\b/.test(gate), "la garde ne rend pas l'atelier elle-même");
});

test("skip links lead to the reader and to the question field, and precede the shell", () => {
  const links = [...workspace.matchAll(/<a href="#([\w-]+)"[\s\S]*?>([^<>{}]+)<\/a>/g)].map(([, target, label]) => [target, label]);
  assert.deepEqual(links, [["lecteur", "Aller au lecteur"], ["question-input", "Aller à la zone de question"]]);
  assert.match(code("components/analysis-panel.tsx"), /<textarea id="question-input"/);
  assert.match(workspace, /getElementById\("lecteur"\)\?\.focus\(\)/);
  assert.match(workspace, /getElementById\("question-input"\)\?\.focus\(\)/);
  // Hors de .workspace-shell : les recettes de balisage actif y comptent les liens.
  assert.ok(workspace.indexOf('className="skip-links"') < workspace.indexOf('className="workspace-shell"'));
});

test("side panels are native modal dialogs labelled by their panel heading, each with a labelled Close button", () => {
  const sheet = code("components/ui/sheet.tsx");
  assert.match(sheet, /<dialog\b/);
  assert.match(sheet, /\.showModal\(\)/);
  assert.match(sheet, /onCancel=\{event => \{ event\.preventDefault\(\); onClose\(\); \}\}/, "Échap passe par l'état React");
  assert.match(sheet, /target\.focus\(\)/, "le focus revient à l'élément qui a ouvert le panneau");
  const sheets = [...workspace.matchAll(/<Sheet side="(left|right)"(?:(?!<Sheet)[\s\S])*?labelledBy="([\w-]+)"/g)].map(([, side, id]) => `${side}:${id}`);
  assert.deepEqual(sheets, ["left:library-heading", "right:analysis-heading", "right:jobs-heading"]);
  for (const id of ["library-heading", "analysis-heading", "jobs-heading"]) assert.ok(components.some(file => code(file).includes(`id="${id}"`)), `titre ${id} absent`);
  for (const label of ["Fermer la bibliothèque", "Fermer l'analyse"]) assert.ok(workspace.includes(`closeButton("${label}")`), label);
  assert.match(workspace, /aria-label=\{label\}><X size=\{16\} aria-hidden="true" \/>Fermer<\/Button>/);
  assert.match(code("components/jobs-panel.tsx"), /aria-label="Fermer le suivi"><X size=\{16\} aria-hidden="true" \/>Fermer<\/Button>/);
  // Chaque panneau n'est rendu qu'une fois, par portail, pour garder son état en franchissant 1 024 px.
  assert.equal((workspace.match(/<LibraryPanel\b/g) ?? []).length, 1);
  assert.equal((workspace.match(/<AnalysisPanel\b/g) ?? []).length, 1);
  assert.match(workspace, /createPortal\(<LibraryPanel\b/);
  assert.match(workspace, /createPortal\(<AnalysisPanel\b/);
});

test("native dialogs follow a closure decided by the browser (Escape repeated without new activation)", () => {
  assert.match(code("components/ui/sheet.tsx"), /if \(openRef\.current\) onClose\(\);/);
  assert.match(code("components/ui/confirm-dialog.tsx"), /onClose=\{\(\) => \{ if \(openRef\.current\) onCancel\(\); \}\}/);
  // Un retrait qui échoue après une fermeture forcée rouvre le dialogue, seul endroit où son erreur s'affiche.
  // L'échec est gardé tel quel ; son texte se calcule au rendu du dialogue (error-text.test.ts).
  assert.match(code("components/document-tools.tsx"), /catch \(failure\) \{\s*setRemoveError\(\{ error: failure \}\);\s*setConfirming\(true\);\s*\}/);
});

test("media queries use Tailwind breakpoints only; the former 1100 and 760 px thresholds are gone", () => {
  const css = stripCssComments(readSource("app/globals.css"));
  const queries = [...css.matchAll(/@media\s*([^{]+)\{/g)].map(([, query]) => query.trim());
  const widths = queries.filter(query => /width/.test(query));
  assert.ok(widths.length >= 5, `${widths.length} requêtes de largeur examinées`);
  for (const query of widths) assert.match(query, /^\(width (?:<|>=) (?:40|48|64|80|96)rem\)$/, query);
  assert.ok(!queries.some(query => /\b(?:1100|760)px\b/.test(query)), "anciens seuils codés");
  assert.ok(queries.includes("(width < 64rem)"));
  assert.match(readSource("lib/panel-preferences.ts"), /COMPACT_LAYOUT_QUERY = "\(width < 64rem\)"/);
  assert.match(workspace, /window\.matchMedia\(COMPACT_LAYOUT_QUERY\)/);
});

test("each child of the panel grid has its own track, so a [hidden] child never shifts the reader", () => {
  // Le preflight Tailwind retire de la grille tout élément [hidden] (display: none !important) :
  // placé automatiquement, le lecteur glisserait alors dans la piste de 0 px d'un séparateur.
  const layout = /<div className="workspace-layout"[^>]*>([\s\S]*?)<Sheet side=/.exec(workspace)?.[1] ?? "";
  const children = [...layout.matchAll(/^ {8}<(?:div|main)\b[^>]*?className="([^"]+)"/gm)].map(([, classes]) => classes.split(" "));
  assert.equal(children.length, 5, `${children.length} enfants directs lus dans la grille`);
  const css = stripCssComments(readSource("app/globals.css"));
  const column = (name: string) => new RegExp(`^\\.${name} \\{[^}]*grid-column: (\\d+);`, "m").exec(css)?.[1];
  children.forEach((classes, index) => {
    assert.deepEqual(classes.map(column).filter(Boolean), [String(index + 1)], `.${classes.join(".")} : piste ${index + 1} attendue`);
  });
  assert.equal(children[2].includes("reader-slot"), true, "le lecteur occupe la troisième piste, la seule élastique");
  assert.match(css, /^\.workspace-layout > \* \{ grid-row: 1; \}/m);
  assert.match(workspace, /style=\{\{ gridTemplateColumns: panelGridColumns\(/);
});

/** Preuve, dans le code, de chaque touche annoncée par le menu Aide. */
const wiring: Record<string, [file: string, proof: RegExp][]> = {
  Ctrl: [["lib/panel-preferences.ts", /event\.ctrlKey \|\| event\.metaKey/], ["components/analysis-panel.tsx", /event\.key === "Enter" && \(event\.ctrlKey \|\| event\.metaKey\)/]],
  "⌘": [["lib/panel-preferences.ts", /event\.ctrlKey \|\| event\.metaKey/], ["components/analysis-panel.tsx", /event\.ctrlKey \|\| event\.metaKey/]],
  B: [["lib/panel-preferences.ts", /event\.key\.toLowerCase\(\) !== "b"/], ["components/workspace.tsx", /if \(!isLibraryShortcut\(event\)\) return;/]],
  Entrée: [["components/analysis-panel.tsx", /event\.key === "Enter"/], ["components/pdf-viewer.tsx", /<form className="viewer-search" onSubmit=/]],
  "←": [["lib/keyboard.ts", /key === "ArrowLeft"/], ["components/workspace.tsx", /\["ArrowLeft", "ArrowRight"\]\.includes\(event\.key\)/]],
  "→": [["lib/keyboard.ts", /key === "ArrowRight"/], ["components/workspace.tsx", /\["ArrowLeft", "ArrowRight"\]\.includes\(event\.key\)/]],
  Début: [["lib/keyboard.ts", /key === "Home"/], ["components/analysis-panel.tsx", /tabKeyTarget\(event\.key/]],
  Fin: [["lib/keyboard.ts", /key === "End"/], ["components/analysis-panel.tsx", /tabKeyTarget\(event\.key/]],
  Échap: [["components/ui/sheet.tsx", /onCancel=/], ["components/ui/confirm-dialog.tsx", /onCancel=/], ["lib/use-dismiss.ts", /event\.key === "Escape"/], ["components/scope-control.tsx", /event\.key === "Escape"/]],
};

test("the help menu lists only keyboard shortcuts that are wired in the code", () => {
  const help = code("components/help-menu.tsx");
  const listed = [...help.matchAll(/keys: (\[\[[^\n]*?\]\]), action/g)].flatMap(([, keys]) => (JSON.parse(keys) as string[][]).flat());
  assert.ok(listed.length >= 10, `${listed.length} touches lues dans le menu Aide`);
  assert.deepEqual([...new Set(listed)].sort(), Object.keys(wiring).sort(), "chaque touche annoncée a sa preuve, et inversement");
  for (const [key, proofs] of Object.entries(wiring)) for (const [file, proof] of proofs) assert.match(code(file), proof, `${key} : ${file}`);
  assert.match(help, /<kbd>\{key\}<\/kbd>/);
  assert.match(workspace, /document\.addEventListener\("keydown", onKey\)/);
});

test("the Suivi counter is capped, announced politely, and the button keeps its visible name", () => {
  const topbar = code("components/app-topbar.tsx");
  assert.match(topbar, /<span className="topbar-label">Suivi<\/span>/);
  assert.match(topbar, /activeJobsBadge\(count\)/);
  assert.match(topbar, /<span className="sr-only" aria-live="polite">\{announcement\}<\/span>/);
});

test("the Suivi button is named « Suivi, … » without a space before the comma, its visible label unchanged", () => {
  // Rejeu R6 (J8) : Chromium calculait « Suivi , aucun traitement à suivre ». Le complément était un span .sr-only en
  // position absolue, traité comme un bloc par le calcul du nom, d'où une espace avant la virgule. Le nom complet est
  // désormais porté par aria-label ; le texte visible reste « Suivi » et le compteur reste masqué aux technologies d'assistance.
  const topbar = code("components/app-topbar.tsx");
  const button = /<Button\b[^>]*onClick=\{onJobsOpen\}[^>]*>([\s\S]*?)<\/Button>/.exec(topbar);
  assert.ok(button, "bouton Suivi trouvé");
  assert.match(button[0], /aria-label=\{jobsName\}/);
  assert.match(button[1], /<span className="topbar-label">Suivi<\/span>/);
  assert.match(button[1], /<span className="count-pill" aria-hidden="true">\{activeJobsBadge\(count\)\}<\/span>/);
  assert.doesNotMatch(button[1], /sr-only/, "aucun complément masqué dans le contenu du bouton");
  const expression = /const jobsName = ([^;]+);/.exec(topbar)?.[1];
  assert.ok(expression, "nom accessible calculé dans le composant");
  const jobsName = new Function("jobsFailed", "activeJobs", "count", "activeJobsSentence", `return ${expression};`) as
    (jobsFailed: boolean, activeJobs: number | null, count: number, sentence: typeof activeJobsSentence) => string;
  const cases: Array<[boolean, number | null, string]> = [
    [false, 0, "Suivi, aucun traitement à suivre"], [false, 1, "Suivi, 1 traitement à suivre"], [false, 3, "Suivi, 3 traitements à suivre"],
    [true, 2, "Suivi, lecture du suivi en échec"], [false, null, "Suivi"],
  ];
  for (const [failed, active, expected] of cases) {
    const name = jobsName(failed, active, active ?? 0, activeJobsSentence);
    assert.equal(name, expected);
    assert.doesNotMatch(name, /\s,/);
    assert.ok(name.startsWith("Suivi"), "le nom commence par le libellé visible (WCAG 2.5.3)");
  }
});

test("the scope trigger shrinks with the centre column of the top bar instead of covering Suivi", () => {
  // J8, L9 : entre 768 et ~915 px, le déclencheur gardait la largeur de son libellé (bouton dans un bloc : jamais sous
  // sa largeur min-content) et recouvrait « Suivi ». Dans une boîte flexible, le bouton (min-width: 0) suit sa colonne
  // et le libellé passe en ellipse ; le plafond fixe de 480 px garde le déclencheur centré aux grandes largeurs.
  const rules = topLevelRules(readSource("app/globals.css"));
  const rule = (selector: string) => rules.get(selector) ?? new Map<string, string>();
  assert.equal(rule(".app-topbar").get("grid-template-columns"), "auto minmax(0, 1fr) auto");
  assert.equal(rule(".topbar-center").get("min-width"), "0");
  assert.equal(rule(".scope-control").get("display"), "flex");
  assert.equal(rule(".scope-control").get("min-width"), "0");
  assert.equal(rule(".scope-control").get("max-width"), "100%");
  assert.equal(rule(".scope-trigger").get("min-width"), "0");
  assert.equal(rule(".scope-trigger").get("max-width"), "480px");
  assert.equal(rule(".scope-trigger").get("overflow"), "hidden", "rien ne déborde du bouton sur la zone de droite");
  assert.equal(rule(".scope-trigger strong").get("min-width"), "0");
  assert.equal(rule(".scope-trigger strong").get("text-overflow"), "ellipsis");
  // Aucune règle, même sous @media, ne rend au déclencheur ou à son conteneur une largeur fixée par le contenu.
  for (const { selector, declarations } of allRules(readSource("app/globals.css")).filter(({ selector }) => /^\.(?:scope-control|scope-trigger|topbar-center)$/.test(selector))) {
    for (const property of ["display", "min-width", "width", "flex", "flex-shrink"]) {
      const value = declarations.get(property);
      if (value !== undefined) assert.ok(rule(selector).get(property) === value, `${selector} { ${property}: ${value} } sous @media`);
    }
  }
});

test("below 64rem the scope trigger keeps its width for the scope label and « Périmètre » only in its accessible name", () => {
  // Revue C2 (J8) : entre 768 et ~960 px, la colonne centrale ne laissait au libellé que quelques pixels (« PÉRIMÈTRE T… ») ;
  // sous lg, le déclencheur est pourtant le seul endroit qui affiche le périmètre actif. Masquage visuel seulement : un
  // display: none ou une visibility: hidden retireraient « Périmètre » du nom accessible du bouton.
  const scope = code("components/scope-control.tsx");
  assert.match(scope, /className="scope-trigger"[^\n]*?\}\}><span className="eyebrow">Périmètre<\/span><strong>\{state\.scopeLabel\}<\/strong>/);
  const css = stripCssComments(readSource("app/globals.css"));
  const compact = /@media \(width < 64rem\) \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
  const hidden = /\.scope-trigger \.eyebrow \{([^}]*)\}/.exec(compact)?.[1] ?? "";
  const declarations = new Map(hidden.split(";").map(part => part.split(":").map(value => value.trim())).filter(([name]) => name).map(([name, ...value]) => [name, value.join(":")]));
  assert.deepEqual(Object.fromEntries(declarations), { position: "absolute", width: "1px", height: "1px", padding: "0", margin: "-1px", overflow: "hidden", clip: "rect(0, 0, 0, 0)", "white-space": "nowrap", border: "0" });
  // Aux autres largeurs, aucune règle ne masque ni ne réduit l'intitulé du déclencheur.
  for (const { selector, declarations: other } of allRules(readSource("app/globals.css")).filter(({ selector }) => /\.scope-trigger \.eyebrow|\.scope-trigger > \.eyebrow/.test(selector))) {
    assert.ok(other.get("position") === "absolute" && other.get("clip") === "rect(0, 0, 0, 0)", `${selector} : seule la règle sous 64rem touche l'intitulé`);
  }
  assert.ok(!topLevelRules(readSource("app/globals.css")).has(".scope-trigger .eyebrow"));
});

test("below 64rem the brand text and the top bar labels leave their room to the scope label, names kept for assistive technologies", () => {
  // Contre-vérification J8 : entre 768 et ~960 px, le libellé du périmètre restait tronqué (0 px à 768, 95 px à 900) ;
  // sous 64rem, le nom de l'atelier et les libellés « Suivi » et « Fermer la session » passent en masquage visuel :
  // les boutons gardent leur icône et leur nom accessible, le titre reste lisible par les lecteurs d'écran.
  const css = stripCssComments(readSource("app/globals.css"));
  const compact = /@media \(width < 64rem\) \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
  for (const selector of [".app-brand > div", ".topbar-label"]) {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const body = new RegExp(`(?:^|[,}\\s])${escaped}[^{]*\\{([^}]*)\\}`).exec(compact)?.[1] ?? "";
    assert.match(body, /position:\s*absolute/, `${selector} : masquage visuel sous 64rem`);
    assert.match(body, /clip:\s*rect\(0, 0, 0, 0\)/, `${selector} : masquage visuel sous 64rem`);
    assert.doesNotMatch(body, /display:\s*none|visibility:\s*hidden/, `${selector} : le nom reste dans l'arbre d'accessibilité`);
  }
});

test("service availability is always spelled out in text, in the top bar or in the context band", () => {
  const topbar = code("components/app-topbar.tsx");
  const band = code("components/context-band.tsx");
  assert.match(topbar, /<StatusIndicator className="topbar-service" status=\{service\.status\}/);
  assert.match(band, /<StatusIndicator className="context-service" status=\{service\.status\}/);
  const css = stripCssComments(readSource("app/globals.css"));
  const narrow = /@media \(width < 48rem\) \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
  assert.match(narrow, /\.topbar-service \{ display: none; \}/);
  assert.match(narrow, /\.context-service \{ display: inline-flex; \}/);
});

test("one message slot replaces the former readiness notice and workspace error bars", () => {
  const band = code("components/context-band.tsx");
  // Erreur de l'espace de travail, puis avis de préparation, puis repli du GPU sur le processeur (W025).
  assert.match(band, /const message = error \? "error" : blockers\.length \? "readiness" : notice \? "generation" : null;/);
  assert.equal((band.match(/className="context-message /g) ?? []).length, 3);
  assert.match(band, /className="context-message workspace-error" role="alert"/);
  assert.match(band, /className="context-message readiness-notice" role="status"/);
  assert.match(band, /className="context-message generation-notice" role="status"/);
  assert.doesNotMatch(workspace, /readiness-notice|workspace-error|workspace-scope-bar/);
  assert.doesNotMatch(stripCssComments(readSource("app/globals.css")), /\.workspace-scope-bar|\.jobs-drawer|\.app-header\b/);
});

test("the generation hardware read on /jobs closes the context band, and nothing is shown after a failed read", () => {
  const band = code("components/context-band.tsx");
  assert.match(band, /const computing = generationView\(generation, commands\);/);
  assert.match(band, /\{computing && <GenerationIndicator view=\{computing\} \/>\}/);
  // Dernier élément du bandeau, aligné à droite sous l'état des services de la barre supérieure.
  assert.ok(band.indexOf("<GenerationIndicator view") > band.lastIndexOf('className="context-message '), "indicateur après l'emplacement de message");
  assert.match(workspace, /generation=\{jobs\.isError \? null : readGeneration\(jobs\.data\?\.generation\)\}/);
  const css = stripCssComments(readSource("app/globals.css"));
  assert.match(css, /^\.context-generation \{[^}]*margin-left: auto;/m);
  // Contrairement à l'état des services, l'indicateur reste dans le bandeau à toutes les largeurs.
  assert.doesNotMatch(css, /\.context-generation \{[^}]*display: none/);
});

test("the generation indicator announces its changes politely and opens its explanation from the keyboard", () => {
  const band = code("components/context-band.tsx");
  // Région de statut polie : un passage en repli ou une nouvelle occupation du modèle est annoncé sans voler le focus.
  assert.match(band, /<div className="context-generation" ref=\{container\}>\s*<span role="status"><StatusIndicator status=\{view\.status\} \/><\/span>/);
  // Explication derrière un bouton : clavier, toucher et lecteurs d'écran, même quand l'emplacement de message est occupé.
  assert.match(band, /<Button ref=\{trigger\} type="button" variant="ghost" size="icon" className="generation-help" aria-expanded=\{open\} aria-controls=\{open \? detailId : undefined\}\s+aria-label="Explication du matériel de génération"/);
  assert.match(band, /\{open && <p className="generation-help-text" id=\{detailId\}>\{view\.detail\}<\/p>\}/);
  assert.match(band, /useDismiss\(open, container, reason => \{ setOpen\(false\); if \(reason === "escape"\) trigger\.current\?\.focus\(\); \}\);/);
  // L'explication n'est plus confiée au seul attribut title, illisible au clavier et au toucher.
  assert.doesNotMatch(band, /title=\{(?:computing|view)\.detail\}/);
  const css = stripCssComments(readSource("app/globals.css"));
  assert.match(css, /^\.generation-help-text \{[^}]*position: absolute;/m);
});
