import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync } from "node:fs";
import { citationParts, citedSourceIds } from "../../src/lib/citations.ts";

const sources = [{ source_id: "S001", name: "Un" }, { source_id: "S002", name: "Deux" }];
const text = (value: string) => ({ kind: "text", text: value });
const cited = (id: string) => ({ kind: "citation", id, source: sources.find(source => source.source_id === id) });

test("single and list references resolve each registered ID individually", () => {
  assert.deepEqual(citationParts("A [S001] et B [S001, S002].", sources), [text("A "), cited("S001"), text(" et B "), cited("S001"), cited("S002"), text(".")]);
  assert.deepEqual(citationParts("[S002;S001][S001]", sources), [cited("S002"), cited("S001"), cited("S001")]);
});

test("an unknown ID inside a list stays non-validated while registered IDs stay clickable", () => {
  assert.deepEqual(citationParts("Voir [S001, S999].", sources), [text("Voir "), cited("S001"), { kind: "unknown", id: "S999", text: "[S999]" }, text(".")]);
  assert.deepEqual(citationParts("[S999]", []), [{ kind: "unknown", id: "S999", text: "[S999]" }]);
});

test("cited IDs include list members so an unregistered reference is reported", () => {
  assert.deepEqual(citedSourceIds("x [S001, S999] y [S003] z [S01] [S002,]"), ["S001", "S999", "S003"]);
});

test("malformed references remain plain text", () => {
  for (const value of ["[S01]", "[S001,]", "[ S001 ]", "[s001]", "[S001 S002]", "S001"]) assert.deepEqual(citationParts(value, sources), [text(value)]);
});

test("HTML and Markdown markup stays literal text and is never turned into another part", () => {
  const hostile = '<img src=x onerror="alert(1)"> **gras** [lien](http://exemple.invalid) ![image](http://exemple.invalid/a.png) <script>fetch("//x")</script> ';
  const parts = citationParts(`${hostile}[S001](http://exemple.invalid)`, sources);
  assert.deepEqual(parts, [text(hostile), cited("S001"), text("(http://exemple.invalid)")]);
  assert.ok(parts.every(part => part.kind !== "unknown"));
});

test("components render no raw HTML sink or dynamic code", () => {
  const root = new URL("../../src/", import.meta.url);
  const files = readdirSync(root, { recursive: true, encoding: "utf8" }).filter(file => /\.(ts|tsx)$/.test(file));
  assert.ok(files.length > 10);
  for (const file of files) {
    const source = readFileSync(new URL(file.replaceAll("\\", "/"), root), "utf8");
    assert.doesNotMatch(source, /dangerouslySetInnerHTML|\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|new Function\(|\beval\(/, file);
  }
});
