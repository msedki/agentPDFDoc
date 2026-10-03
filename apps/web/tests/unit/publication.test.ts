import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";
import { hasPublishedExtraction } from "../../src/lib/publication.ts";
import type { DocumentDetail } from "../../src/lib/types.ts";
import { readSource } from "./theme-support.ts";

const publicationCopy = "Original consultable ; son extraction n'est pas encore publiée. Les passages, le sommaire et l'analyse de page seront disponibles après publication de l'extraction. Consultez le Suivi : une extraction partielle peut demander votre accord.";
const oldCopy = "Original consultable ; son extraction n'est pas encore publiée. Les passages, le sommaire et l'analyse de page s'activeront à la fin de l'indexation, visible dans le Suivi.";

function publicationNotice(source: string) {
  const tree = ts.createSourceFile("pdf-viewer.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const matches: { element: ts.JsxElement; guard: ts.BinaryExpression }[] = [];
  const attribute = (element: ts.JsxElement, name: string) => {
    const found = element.openingElement.attributes.properties.filter(item => ts.isJsxAttribute(item) && item.name.getText(tree) === name);
    assert.ok(found.length <= 1, `duplicate ${name} attribute`);
    const value = found[0];
    return value && ts.isJsxAttribute(value) && value.initializer && ts.isStringLiteral(value.initializer) ? value.initializer.text : undefined;
  };
  const visit = (node: ts.Node) => {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
        && ts.isPrefixUnaryExpression(node.left) && node.left.operator === ts.SyntaxKind.ExclamationToken
        && ts.isIdentifier(node.left.operand) && node.left.operand.text === "provenanceReady"
        && ts.isJsxElement(node.right) && node.right.openingElement.tagName.getText(tree) === "p"
        && attribute(node.right, "className") === "viewer-notice" && attribute(node.right, "role") === "status") {
      matches.push({ element: node.right, guard: node });
    }
    ts.forEachChild(node, visit);
  };
  visit(tree);
  assert.equal(matches.length, 1, "exactly one publication notice under !provenanceReady");
  const match = matches[0];
  assert.ok(match.element.children.every(ts.isJsxText), "publication notice must be static text");
  const text = match.element.children.map(child => child.getText(tree)).join("").replace(/\s+/g, " ").trim();
  return { ...match, text, tree };
}

function assertPublicationCopy(source: string) {
  assert.equal(publicationNotice(source).text, publicationCopy);
}

const original: DocumentDetail = { id: "document", folder_id: null, name: "Controlled.pdf", relative_path: "Controlled.pdf", state: "queued", page_count: null, active_generation_id: null, active_version_id: null, versions: [{ id: "new", document_id: "document", sha256: "actual-api-hash", page_count: null, created_at: "2026-09-30" }] };

test("an imported original and verified unpublished partial have no published extraction", () => {
  assert.equal(hasPublishedExtraction(original, "new"), false);
  assert.equal(hasPublishedExtraction({ ...original, state: "ready_partial", jobs: [{ id: "partial", version_id: "new", state: "ready_partial", published: false }] }, "new"), false);
});
test("a different active version does not publish the newly opened original", () => {
  assert.equal(hasPublishedExtraction({ ...original, active_generation_id: "old-generation", active_version_id: "old" }, "new"), false);
});
test("active and archived published generations are both consultable", () => {
  const document = { ...original, active_generation_id: "new-generation", active_version_id: "new", jobs: [{ id: "old-job", version_id: "old", published: true, active: false }] };
  assert.equal(hasPublishedExtraction(document, "new"), true);
  assert.equal(hasPublishedExtraction(document, "old"), true);
  assert.equal(hasPublishedExtraction({ ...document, state: "deleted" }, "new"), false);
});

test("an unpublished partial remains gated until its extraction is explicitly published", () => {
  const partial: DocumentDetail = { ...original, state: "ready_partial", jobs: [{ id: "partial", version_id: "new", state: "ready_partial", published: false }] };
  assert.equal(hasPublishedExtraction(partial, "new"), false);
  assert.equal(hasPublishedExtraction({ ...partial, jobs: [{ ...partial.jobs![0], published: true }] }, "new"), true);
});

test("the gated viewer notice describes publication and possible consent for a partial extraction", () => {
  assertPublicationCopy(readSource("components/pdf-viewer.tsx"));
});

test("old wording cannot be rescued by the correct copy in a comment or another paragraph", () => {
  const source = readSource("components/pdf-viewer.tsx");
  const notice = publicationNotice(source);
  const oldSource = source.slice(0, notice.element.getStart(notice.tree))
    + `<p className="viewer-notice" role="status">${oldCopy}</p>` + source.slice(notice.element.end);
  assert.throws(() => assertPublicationCopy(oldSource));
  assert.throws(() => assertPublicationCopy(`${oldSource}\n/* ${publicationCopy} */`));
  assert.throws(() => assertPublicationCopy(`${oldSource}\nconst unrelatedNotice = <p className="viewer-notice" role="status">${publicationCopy}</p>;`));
});

test("a duplicate publication notice and an inverted publication gate are rejected", () => {
  const source = readSource("components/pdf-viewer.tsx");
  const notice = publicationNotice(source);
  assert.throws(() => assertPublicationCopy(`${source}\nconst duplicateNotice = ${notice.guard.getText(notice.tree)};`));
  const inverted = source.slice(0, notice.guard.left.getStart(notice.tree)) + "provenanceReady" + source.slice(notice.guard.left.end);
  assert.throws(() => assertPublicationCopy(inverted));
});
