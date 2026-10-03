import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";
import { readSource } from "./theme-support.ts";

const prefix = "Aucun passage retrouvé dans les documents déjà indexés. ";
const advice = ". Consultez le Suivi pour vérifier leur état et les actions possibles, puis relancez la recherche lorsqu'ils sont interrogeables.";
const oldAdvice = " : relancez la recherche une fois leur traitement terminé dans le Suivi.";

/** La vraie branche vide du composant, pas un commentaire ou un autre état vide. */
function incompleteNotice(source: string) {
  const tree = ts.createSourceFile("analysis-panel.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const components = tree.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === "AnalysisPanel");
  assert.equal(components.length, 1, "one AnalysisPanel component");
  const component = components[0];
  assert.ok(ts.isFunctionDeclaration(component) && component.body);
  const attribute = (element: ts.JsxSelfClosingElement, name: string) => {
    const matches = element.attributes.properties.filter(item => ts.isJsxAttribute(item) && item.name.getText(tree) === name);
    assert.ok(matches.length <= 1, `duplicate ${name} attribute`);
    return matches[0];
  };
  const literal = (element: ts.JsxSelfClosingElement, name: string) => {
    const value = attribute(element, name);
    return value && ts.isJsxAttribute(value) && value.initializer && ts.isStringLiteral(value.initializer) ? value.initializer.text : undefined;
  };
  const matches: ts.JsxSelfClosingElement[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(tree) === "PanelEmpty" && literal(node, "reason") === "index-incomplete") matches.push(node);
    ts.forEachChild(node, visit);
  };
  visit(component.body);
  assert.equal(matches.length, 1, "exactly one index-incomplete PanelEmpty");
  const element = matches[0];
  const branch = element.parent;
  assert.ok(ts.isConditionalExpression(branch) && branch.whenTrue === element);
  assert.ok(ts.isPropertyAccessExpression(branch.condition) && branch.condition.questionDotToken);
  assert.equal(branch.condition.expression.getText(tree), "searchScope");
  assert.equal(branch.condition.name.text, "unindexed");
  assert.ok(ts.isJsxSelfClosingElement(branch.whenFalse));
  assert.equal(literal(branch.whenFalse, "reason"), "no-match");
  assert.ok(ts.isParenthesizedExpression(branch.parent));
  const emptyResults = branch.parent.parent;
  assert.ok(ts.isBinaryExpression(emptyResults) && emptyResults.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken);
  assert.ok(ts.isPrefixUnaryExpression(emptyResults.left) && emptyResults.left.operator === ts.SyntaxKind.ExclamationToken);
  assert.equal(emptyResults.left.operand.getText(tree), "search.results.length");
  const description = attribute(element, "description");
  assert.ok(description && ts.isJsxAttribute(description) && description.initializer && ts.isJsxExpression(description.initializer));
  const template = description.initializer.expression;
  assert.ok(template && ts.isTemplateExpression(template));
  assert.equal(template.head.text, prefix);
  assert.equal(template.templateSpans.length, 1);
  assert.equal(template.templateSpans[0].expression.getText(tree), "unindexedSentence(searchScope.unindexed)");
  return { tree, element, branch, template, advice: template.templateSpans[0].literal.text };
}

function assertCopy(source: string) { assert.equal(incompleteNotice(source).advice, advice); }

function withAdvice(source: string, suffix: string) {
  const notice = incompleteNotice(source);
  return source.replace(notice.template.getText(notice.tree), "`" + prefix + "${unindexedSentence(searchScope.unindexed)}" + suffix + "`");
}

test("the incomplete search advice refers to Suivi actions and actual queryability, not completion alone", () => {
  assertCopy(readSource("components/analysis-panel.tsx"));
});

test("the old advice is not rescued by a comment or an unrelated empty state", () => {
  const source = withAdvice(readSource("components/analysis-panel.tsx"), advice);
  assertCopy(source);
  const old = withAdvice(source, oldAdvice);
  assert.throws(() => assertCopy(old));
  assert.throws(() => assertCopy(`${old}\n/* ${advice} */`));
  assert.throws(() => assertCopy(`${old}\nconst unrelated = <PanelEmpty reason="no-match" title="Autre état" description="${advice}" />;`));
});

test("duplicated branches, inverted queryability and a fabricated excluded count are rejected", () => {
  const source = withAdvice(readSource("components/analysis-panel.tsx"), advice);
  const notice = incompleteNotice(source);
  const jsx = notice.element.getText(notice.tree);
  assert.throws(() => assertCopy(source.replace(jsx, `<>${jsx}${jsx}</>`)), /exactly one index-incomplete/);
  assert.throws(() => assertCopy(source.replace(notice.branch.condition.getText(notice.tree), "!searchScope?.unindexed")));
  assert.throws(() => assertCopy(source.replace("unindexedSentence(searchScope.unindexed)", "unindexedSentence(999)")));
});
