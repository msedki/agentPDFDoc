/** Actual helpers and React rendering; no browser, API or model qualification is claimed. */
import assert from "node:assert/strict";
import test from "node:test";
import * as React from "react";
import { renderToString } from "react-dom/server";
import ts from "typescript";
import { answerBlocks } from "../../src/lib/answer-format.ts";
import { citationParts } from "../../src/lib/citations.ts";
import { applyQueryEvent, historicalTurn } from "../../src/lib/query-history.ts";
import type { CitationSpan, HistoricalQuery, Source } from "../../src/lib/types.ts";
import { readSource } from "./theme-support.ts";

const source: Source = { source_id: "S001", query_id: "saved", document_id: "document-old", document_name: "Source",
  version_id: "version-old", extraction_revision_id: "revision-old", format: "xlsx", text: "72 V",
  locator: { kind: "xlsx_cells", unit_id: "sheet1", sheet_id: "sheet1", sheet_name: "Mesures", part: "xl/worksheets/sheet1.xml", cell_range: "B2", row_start: 2, row_end: 2, column_start: 2, column_end: 2 } };
const literal = "A😀 & <b> **littéral** [S001] [S999]\n- cellule";
const text = `${literal}\nCitation : [S001]`;
const start = Array.from(`${literal}\nCitation : `).length;
const spans: CitationSpan[] = [{ source_id: "S001", start_offset: start, end_offset: start + 6 }];

function loadComponent(name: string, environment: Record<string, unknown>): (props: Record<string, unknown>) => React.ReactNode {
  const code = readSource("components/analysis-panel.tsx");
  const ast = ts.createSourceFile("analysis-panel.tsx", code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declaration = ast.statements.find((node): node is ts.FunctionDeclaration => ts.isFunctionDeclaration(node) && node.name?.text === name);
  assert.ok(declaration?.body, `actual ${name} required`);
  const compiled = ts.transpileModule(declaration.getText(ast).replace(/^export\s+/, ""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, module: ts.ModuleKind.CommonJS },
  }).outputText;
  return new Function(...Object.keys(environment), `${compiled}\nreturn ${name};`)(...Object.values(environment));
}

function components() {
  const CitedSegment = loadComponent("CitedSegment", { React, citationParts, citationTitle: () => "Ouvrir la source exacte" });
  const CitationText = loadComponent("CitationText", { React, Fragment: React.Fragment, answerBlocks, CitedSegment });
  return { CitedSegment, CitationText };
}

test("authoritative Unicode spans keep documentary citation-like text literal and open only the declared source", () => {
  const parts = citationParts(text, [source], spans);
  assert.deepEqual(parts.filter(part => part.kind === "citation").map(part => part.id), ["S001"]);
  assert.equal(parts[0].kind, "text");
  assert.equal(parts[0].kind === "text" && parts[0].text, `${literal}\nCitation : `);
  assert.equal(parts.some(part => part.kind === "unknown"), false);
  assert.equal(parts.find(part => part.kind === "citation")?.source, source);
});

test("an explicitly empty span list preserves every literal marker without legacy regex fallback", () => {
  assert.deepEqual(citationParts(text, [source], []), [{ kind: "text", text }]);
});

test("malformed, overlapping, wrong-token or UTF-16 spans fail closed without interpreting other markers", () => {
  const invalid = [
    [{ ...spans[0], start_offset: -1 }], [{ ...spans[0], end_offset: 9999 }],
    [{ ...spans[0], start_offset: start + .5 }], [{ ...spans[0], source_id: "S999" }],
    [spans[0], spans[0]], [{ ...spans[0], start_offset: start + 1, end_offset: start + 7 }],
  ];
  for (const metadata of invalid) assert.deepEqual(citationParts(text, [source], metadata), [{ kind: "text", text }]);
});

test("typed React rendering shows exact literals, no source HTML/Markdown, and one authoritative citation button", () => {
  const { CitationText, CitedSegment } = components();
  const opened: Source[] = [];
  const html = renderToString(React.createElement(CitationText, { text, sources: [source], citationSpans: spans, onCitation: (value: Source) => opened.push(value) })).replaceAll("<!-- -->", "");
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /A😀 &amp; &lt;b&gt; \*\*littéral\*\* \[S001\] \[S999\]/);
  assert.doesNotMatch(html, /&amp;amp;|<b>|<strong>|<ul>|référence inconnue/);
  assert.match(html, /\n- cellule/);
  // Invoke the actual component's action; only React itself and the title helper are substituted here.
  const elements = CitedSegment({ text, sources: [source], citationSpans: spans, onCitation: (value: Source) => opened.push(value) }) as React.ReactElement<{ onClick: () => void }>[];
  const button = elements.find(element => element.type === "button");
  assert.ok(button);
  button.props.onClick();
  assert.deepEqual(opened, [source]);
});

test("typed done/replay carries exact spans and produces no unknown-citation warning from documentary markers", () => {
  const detail: HistoricalQuery = { query_id: "saved", conversation_id: "conversation", question: "Valeur ?", state: "done", mode: null,
    last_event_id: 8, created_at: "2026-10-11", updated_at: "2026-10-11", events_url: "/api/v1/queries/saved/events",
    scope: { kind: "documents", documentIds: ["document-old"] }, answer: text, warnings: [], metrics: {}, resolution: {} };
  const scopeBefore = structuredClone(detail.scope);
  let turn = historicalTurn(detail);
  turn = applyQueryEvent(turn, { id: "1", type: "sources", data: { sources: [source] } });
  turn = applyQueryEvent(turn, { id: "7", type: "delta", data: { text, citation_spans: spans } });
  assert.deepEqual(turn.citationSpans, spans);
  turn = applyQueryEvent(turn, { id: "8", type: "done", data: { text, message: text, status: "done", finish_reason: "stop", structured_answer: { status: "validated", citation_spans: spans } } });
  assert.equal(turn.text, text);
  assert.deepEqual(turn.citationSpans, spans);
  assert.deepEqual(turn.warnings, []);
  assert.deepEqual(turn.scope, scopeBefore);
  assert.equal(turn.connection, "closed");
  assert.equal(turn.sources[0].version_id, "version-old");
});

test("old plain-text PDF/DOCX responses retain existing Markdown and regex citation behavior", () => {
  const { CitationText } = components();
  const html = renderToString(React.createElement(CitationText, { text: "**Titre**\n- 72 V [S001]\n- [S999]", sources: [source], onCitation: () => undefined }));
  assert.match(html, /<strong>/);
  assert.match(html, /<ul>/);
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /référence inconnue/);
});
