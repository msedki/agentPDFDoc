import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute only the oracle extracted from the real spec. No Playwright imports,
// globalSetup, browser, request or application state is loaded by these doubles.
const source = readFileSync(new URL("../e2e/lifecycle.spec.ts", import.meta.url), "utf8");
const tree = ts.createSourceFile("lifecycle.spec.ts", source, ts.ScriptTarget.Latest, true);
type Element = { tag: string; className?: string; text?: string; visible?: boolean; children?: Element[] };
const elements = (root: Element): Element[] => [root, ...(root.children ?? []).flatMap(elements)];
const textOf = (node: Element): string => [node.text ?? "", ...(node.children ?? []).map(textOf)].join("");
const normalize = (value: string) => value.replace(/\s+/g, " ").trim();
const hasClass = (node: Element, name: string) => node.className?.split(" ").includes(name) ?? false;

class LocatorDouble {
  readonly roots: Element[];
  readonly query: (root: Element) => Element[];
  constructor(roots: Element[], query: (root: Element) => Element[]) { this.roots = roots; this.query = query; }
  matches() { return this.roots.flatMap(this.query); }
  locator(selector: string): LocatorDouble {
    return new LocatorDouble(this.roots, root => this.query(root).flatMap(parent => {
      if (selector === ".job-heading > strong") return elements(parent).filter(node => hasClass(node, "job-heading")).flatMap(node => (node.children ?? []).filter(child => child.tag === "strong"));
      const className = selector.slice(1);
      assert.ok([".jobs-panel", ".inline-error", ".status-indicator"].includes(selector), "unexpected locator contract");
      return elements(parent).slice(1).filter(node => hasClass(node, className));
    }));
  }
  getByRole(role: string): LocatorDouble {
    assert.equal(role, "article");
    return new LocatorDouble(this.roots, root => this.query(root).flatMap(parent => elements(parent).slice(1).filter(node => node.tag === "article")));
  }
  getByText(text: string, options: { exact?: boolean }): LocatorDouble {
    assert.equal(options.exact, true);
    return new LocatorDouble(this.roots, root => this.query(root).flatMap(parent => elements(parent).filter(node => !(node.children?.length) && normalize(textOf(node)) === normalize(text))));
  }
  filter(options: { has?: LocatorDouble; hasText?: string | RegExp }): LocatorDouble {
    return new LocatorDouble(this.roots, root => this.query(root).filter(node => {
      if (options.has && !options.has.query(node).length) return false;
      if (options.hasText !== undefined) return typeof options.hasText === "string" ? textOf(node).includes(options.hasText) : options.hasText.test(textOf(node));
      return true;
    }));
  }
  first(): LocatorDouble { return new LocatorDouble(this.roots, root => this.query(root).slice(0, 1)); }
}

function expectation(actual: unknown) {
  const one = () => {
    assert.ok(actual instanceof LocatorDouble);
    const nodes = actual.matches();
    assert.equal(nodes.length, 1, "one matching element required");
    return nodes[0];
  };
  return {
    toBe: (expected: unknown) => assert.equal(actual, expected),
    not: { toBe: (expected: unknown) => assert.notEqual(actual, expected) },
    toHaveCount: (expected: number) => { assert.ok(actual instanceof LocatorDouble); assert.equal(actual.matches().length, expected); },
    toHaveText: (expected: string) => assert.equal(normalize(textOf(one())), normalize(expected)),
    toBeVisible: () => assert.notEqual(one().visible, false),
  };
}

function oracle() {
  const helper = tree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "expectCurrentFileFailure");
  let code: string;
  if (helper) {
    code = `${helper.getText(tree)}\nexpectCurrentFileFailure;`;
  } else {
    // Before the fix, exercise the actual global assertion, not a reimplementation.
    const old: ts.AwaitExpression[] = [];
    const visit = (node: ts.Node) => {
      if (ts.isAwaitExpression(node) && node.getText(tree).includes("page.getByText(String(job.error_message)")) old.push(node);
      ts.forEachChild(node, visit);
    };
    visit(tree);
    assert.equal(old.length, 1, "exact original oracle required for red proof");
    code = `async function oldOracle(page, name, message) { const job = { error_message: message }; ${old[0].getText(tree)}; }\noldOracle;`;
  }
  const compiled = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  return runInNewContext(compiled, { expect: expectation }) as (page: LocatorDouble, name: string, message: unknown) => Promise<void>;
}

const message = "Le fichier ne peut pas être lu. Vérifiez-le avant de l'importer à nouveau.";
const name = "Structure invalide.pdf";
function card(title: string, error: string | null = message, status = "Échec", visible = true): Element {
  return { tag: "article", children: [
    { tag: "div", className: "job-heading", children: [{ tag: "strong", text: title }, { tag: "span", className: "status-indicator", text: status }] },
    ...(error === null ? [] : [{ tag: "p", className: "inline-error", text: error, visible }]),
  ] };
}
function page(cards: Element[], outside: Element[] = [], panels = 1) {
  const root: Element = { tag: "main", children: [...outside, ...Array.from({ length: panels }, () => ({ tag: "section", className: "jobs-panel", children: cards }))] };
  return new LocatorDouble([root], item => [item]);
}

test("current corrupt card with its own error passes alongside a previous identical error", async () => {
  await oracle()(page([card("PDF chiffré.pdf"), card(name)]), name, message);
});
test("current encrypted card is selected independently of the corrupt card", async () => {
  await oracle()(page([card(name), card("PDF chiffré.pdf")]), "PDF chiffré.pdf", message);
});
test("a previous matching error cannot rescue a current extracting card", async () => {
  await assert.rejects(oracle()(page([card("PDF chiffré.pdf"), card(name, null, "Extraction en cours")]), name, message));
});
test("a previous matching error cannot rescue a wrong current inline message", async () => {
  await assert.rejects(oracle()(page([card("PDF chiffré.pdf"), card(name, "Autre erreur")]), name, message));
});
test("the same message outside Suivi cannot rescue an absent current card", async () => {
  await assert.rejects(oracle()(page([], [{ tag: "p", text: message }]), name, message));
});
test("duplicate current cards are refused rather than selecting the first", async () => {
  await assert.rejects(oracle()(page([card(name), card(name)]), name, message));
});
test("a hidden current inline error is not visible evidence", async () => {
  await assert.rejects(oracle()(page([card("PDF chiffré.pdf"), card(name, message, "Échec", false)]), name, message));
});
test("a matching message without the current failure status is refused", async () => {
  await assert.rejects(oracle()(page([card(name, message, "Extraction en cours")]), name, message));
});
test("the exact heading is not a substring or a regular expression supplied by the name", async () => {
  const literal = "Structure [1].pdf";
  await oracle()(page([card(literal)]), literal, message);
  await assert.rejects(oracle()(page([card(`Copie ${literal}`)]), literal, message));
  await assert.rejects(oracle()(page([card("Structure 1.pdf")]), literal, message));
});
test("duplicate inline errors in the current card are refused", async () => {
  const duplicate = card(name);
  duplicate.children!.push({ tag: "p", className: "inline-error", text: message });
  await assert.rejects(oracle()(page([duplicate]), name, message));
});
test("duplicate Suivi panels are refused", async () => {
  await assert.rejects(oracle()(page([card(name)], [], 2), name, message));
});
test("the backend message must be a nonempty string", async () => {
  for (const value of [undefined, "", "   "]) await assert.rejects(oracle()(page([card(name, String(value))]), name, value));
});
test("both real file-error scenarios call the current card oracle before their capture", () => {
  const loops = tree.statements.filter(ts.isForOfStatement);
  assert.equal(loops.length, 1);
  const calls: ts.CallExpression[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node)) calls.push(node);
    ts.forEachChild(node, visit);
  };
  visit(loops[0]);
  const scoped = calls.filter(call => ts.isIdentifier(call.expression) && call.expression.text === "expectCurrentFileFailure");
  assert.equal(scoped.length, 1);
  assert.deepEqual(scoped[0].arguments.map(argument => argument.getText(tree)), ["page", "input.name", "job.error_message"]);
  const screenshots = calls.filter(call => ts.isPropertyAccessExpression(call.expression) && call.expression.name.text === "screenshot");
  assert.equal(screenshots.length, 1);
  assert.ok(scoped[0].end < screenshots[0].getStart(tree), "capture follows the current-card assertions");
  assert.equal(calls.filter(call => ts.isPropertyAccessExpression(call.expression) && call.expression.name.text === "getByText").length, 0, "no global-message fallback in the file-error scenarios");
});
