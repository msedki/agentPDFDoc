/**
 * R26-UI-02, limite de D4 (recette R26-KIT-02), levée en ronde 5 de R26-KIT-04 : « Priorité aux questions » est un
 * marqueur durable du gouverneur (data/control/pause-ingestion) ; sous ce mode, un import ou une réindexation reste
 * en file jusqu'au délai de la spec. Toute spec qui déclenche une indexation et l'attend passe donc par
 * withImportPriority (tests/e2e/import-priority.ts), directement ou par importPublished (guards.ts) : le helper
 * choisit « Priorité aux imports » dans une page dédiée du contexte, puis rétablit la priorité trouvée dans un finally.
 *
 * Contrôle statique de l'arbre syntaxique des specs réelles (API du compilateur TypeScript), sans navigateur ni
 * service. Le comportement du helper est vérifié par import-priority.test.ts ; la chaîne réelle, par l'E2E rejoué sur
 * une instance isolée placée en « Priorité aux questions ».
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const e2eDir = new URL("../e2e/", import.meta.url);
const HELPER = "withImportPriority";
/** Specs nommées par la limite D4 de R26-UI-02 : elles importaient sans le helper partagé. */
const D4_SPECS = ["lifecycle.spec.ts", "ocr-selection.spec.ts", "unicode-selection.spec.ts", "workspace.spec.ts"];

/**
 * Imports qui n'attendent aucune indexation : la priorité n'y change rien. Chaque entrée est vérifiée (import présent
 * hors helper, aucune attente d'indexation dans le même test) pour qu'une exception périmée ne couvre rien d'autre.
 */
const NO_INDEXING_AWAITED: Readonly<Record<string, string>> = {
  "lifecycle.spec.ts › identical UI reimport retains exact document version job and publication":
    "réimport identique : le service rend le job publié existant (reused), aucun traitement n'est créé",
  "lifecycle.spec.ts › isolated 64KiB limit rejects a genuinely oversized controlled PDF":
    "refus 413 avant toute création de job",
  "library-drop.spec.ts › a PDF dropped on the library is imported, with the usual notice":
    "vérifie la réception (202) et l'avis de la bibliothèque, sans attendre l'indexation",
};

type Spec = { file: string; tree: ts.SourceFile };
type Site = { key: string; where: string; what: string; inHelper: boolean };

const specs: Spec[] = readdirSync(e2eDir).filter(name => name.endsWith(".spec.ts")).sort().map(file => (
  { file, tree: ts.createSourceFile(file, readFileSync(new URL(file, e2eDir), "utf8"), ts.ScriptTarget.Latest, true) }));

function descendants(root: ts.Node): ts.Node[] {
  const all: ts.Node[] = [];
  const visit = (node: ts.Node) => { all.push(node); ts.forEachChild(node, visit); };
  visit(root);
  return all;
}
const literal = (node: ts.Node | undefined) => node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? node.text : undefined;
const calleeName = (call: ts.CallExpression) => ts.isIdentifier(call.expression) ? call.expression.text
  : ts.isPropertyAccessExpression(call.expression) ? call.expression.name.text : "";
const isHelperCall = (node: ts.Node): node is ts.CallExpression => ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === HELPER;

/** Vrai si le nœud est dans une fonction passée en argument à withImportPriority. */
function insideHelper(node: ts.Node): boolean {
  for (let current = node; current.parent; current = current.parent) {
    if ((ts.isArrowFunction(current) || ts.isFunctionExpression(current)) && isHelperCall(current.parent) && current.parent.arguments.includes(current)) return true;
  }
  return false;
}

/** Titre du test Playwright englobant (appel `test(titre, …)`). */
function testTitle(node: ts.Node, tree: ts.SourceFile): string {
  for (let current: ts.Node | undefined = node; current; current = current.parent) {
    if (ts.isCallExpression(current) && ts.isIdentifier(current.expression) && current.expression.text === "test") {
      const title = current.arguments[0];
      return title ? literal(title) ?? title.getText(tree) : "?";
    }
  }
  return "(hors test)";
}

const hasTimeout = (options: ts.Expression | undefined) => !!options && ts.isObjectLiteralExpression(options)
  && options.properties.some(property => !!property.name && ts.isIdentifier(property.name) && property.name.text === "timeout");
const INDEXING_BUTTONS = ["Réindexer ce document", "Reprendre l'indexation"];
const namesIndexingButton = (call: ts.CallExpression) => call.arguments.some(argument => ts.isObjectLiteralExpression(argument)
  && argument.properties.some(property => ts.isPropertyAssignment(property) && INDEXING_BUTTONS.includes(literal(property.initializer) ?? "")));

/** Attentes d'indexation (waitJob, « Prêt » attendu avec un délai propre) et déclencheurs d'indexation de chaque spec. */
function sites(spec: Spec) {
  const waits: Site[] = [];
  const triggers: Site[] = [];
  for (const node of descendants(spec.tree)) {
    if (!ts.isCallExpression(node)) continue;
    const name = calleeName(node);
    const site = (what: string): Site => {
      const title = testTitle(node, spec.tree);
      const line = spec.tree.getLineAndCharacterOfPosition(node.getStart(spec.tree)).line + 1;
      return { key: `${spec.file} › ${title}`, where: `${spec.file}:${line} (test « ${title} »)`, what, inHelper: insideHelper(node) };
    };
    if (name === "waitJob") waits.push(site("waitJob"));
    if (name === "toContainText" && literal(node.arguments[0]) === "Prêt" && hasTimeout(node.arguments[1])) waits.push(site("attente de « Prêt » dans la bibliothèque"));
    if (name === "uploadFromUi") triggers.push(site("uploadFromUi"));
    if (name === "setFiles") triggers.push(site("choix de fichier (setFiles)"));
    if (name === "dispatchEvent" && literal(node.arguments[0]) === "drop") triggers.push(site("dépôt sur la bibliothèque (drop)"));
    if (name === "post" && /\/documents\/import|\/reindex|\/resume/.test(node.arguments[0]?.getText(spec.tree) ?? "")) triggers.push(site("POST d'indexation par l'API"));
    if (namesIndexingButton(node)) triggers.push(site("bouton qui lance une indexation"));
  }
  return { waits, triggers };
}

const all = specs.map(spec => ({ spec, ...sites(spec) }));
const describe = (items: Site[]) => items.map(item => `${item.where} : ${item.what}`).join("\n");

test("chaque attente d'indexation d'une spec se fait sous withImportPriority", () => {
  const outside = all.flatMap(item => item.waits).filter(site => !site.inHelper);
  assert.deepEqual(outside, [], `Attentes d'indexation hors du helper (bloquées sous « Priorité aux questions ») :\n${describe(outside)}`);
});

test("chaque import ou réindexation passe par withImportPriority, sauf les imports déclarés sans attente d'indexation", () => {
  const outside = all.flatMap(item => item.triggers).filter(site => !site.inHelper && !(site.key in NO_INDEXING_AWAITED));
  assert.deepEqual(outside, [], `Déclencheurs d'indexation hors du helper :\n${describe(outside)}`);
  for (const [key, reason] of Object.entries(NO_INDEXING_AWAITED)) {
    const triggers = all.flatMap(item => item.triggers).filter(site => site.key === key && !site.inHelper);
    const waits = all.flatMap(item => item.waits).filter(site => site.key === key);
    assert.ok(triggers.length > 0, `Exception périmée, aucun import hors helper : ${key}`);
    assert.deepEqual(waits, [], `Exception « ${reason} » contredite par une attente d'indexation : ${key}`);
  }
});

test("aucune spec ne choisit elle-même la priorité du poste : le choix et son rétablissement appartiennent au helper", () => {
  const found: string[] = [];
  for (const { file, tree } of specs) {
    for (const node of descendants(tree)) {
      const where = `${file}:${tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1}`;
      if (literal(node) === "Priorité aux imports") found.push(`${where} : bouton « Priorité aux imports » actionné par la spec, sans rétablissement`);
      if (literal(node)?.includes("/api/v1/runtime/mode")) found.push(`${where} : appel direct de /api/v1/runtime/mode`);
      if (ts.isFunctionDeclaration(node) && ["choosePriority", "readPriority", "restorePriority", HELPER].includes(node.name?.text ?? "")) found.push(`${where} : copie locale de ${node.name!.text}`);
    }
  }
  assert.deepEqual(found, [], found.join("\n"));
});

test("withImportPriority est importé du module partagé et reçoit la page du scénario et une action asynchrone", () => {
  for (const { file, tree } of specs) {
    const calls = descendants(tree).filter(isHelperCall);
    if (!calls.length) continue;
    const imported = tree.statements.filter(ts.isImportDeclaration).some(declaration => literal(declaration.moduleSpecifier) === "./import-priority.ts"
      && !!declaration.importClause?.namedBindings && ts.isNamedImports(declaration.importClause.namedBindings)
      && declaration.importClause.namedBindings.elements.some(element => element.name.text === HELPER));
    assert.ok(imported, `${file} : withImportPriority doit venir de ./import-priority.ts`);
    for (const call of calls) {
      const line = tree.getLineAndCharacterOfPosition(call.getStart(tree)).line + 1;
      assert.equal(call.arguments.length, 4, `${file}:${line} : quatre arguments (page, request, info, action)`);
      assert.equal(call.arguments[0].getText(tree), "page", `${file}:${line} : la page du scénario, dont le helper ne prend que le contexte`);
      const action = call.arguments[3];
      assert.ok((ts.isArrowFunction(action) || ts.isFunctionExpression(action)) && action.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.AsyncKeyword),
        `${file}:${line} : l'action est une fonction asynchrone écrite dans l'appel`);
    }
  }
});

test("les quatre specs de la limite D4 attendent leurs indexations sous le helper", () => {
  for (const file of D4_SPECS) {
    const item = all.find(entry => entry.spec.file === file);
    assert.ok(item, `${file} absente de tests/e2e`);
    assert.ok(item.waits.length > 0, `${file} : aucune attente d'indexation reconnue ; le contrôle serait vide`);
    assert.deepEqual(item.waits.filter(site => !site.inHelper).map(site => site.where), [], `${file} : attentes hors helper`);
    assert.ok(descendants(item.spec.tree).some(isHelperCall), `${file} : aucun appel à withImportPriority`);
  }
});
