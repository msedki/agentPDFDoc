import assert from "node:assert/strict";
import test from "node:test";
import { findNextPdfPage, samePdfReading } from "../../src/lib/pdf-search.ts";

function deferredText() {
  let resolve!: (value: string) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<string>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function fixture() {
  const controller = new AbortController();
  const visits: number[] = [];
  return { controller, visits, options: {
    pageCount: 3, pageIndex: 1, expression: "  PRESSION  ", signal: controller.signal,
    isCurrent: () => true,
    // Lectures doublées : aucune API ni page PDF réelle exécutée par ces unités.
    readNative: async (index: number) => { visits.push(index); return index === 0 ? "Pression : 3,1 bar" : "Autre texte"; },
  } };
}

test("search visits the following pages, wraps once and retains the matching page index", async () => {
  const { visits, options } = fixture();
  assert.deepEqual(await findNextPdfPage(options), { kind: "found", pageIndex: 0 });
  assert.deepEqual(visits, [2, 0]);
});

test("mixed-page search includes extracted text and passes the actual lifetime signal", async () => {
  const { options, controller } = fixture();
  const extracted: number[] = [];
  const result = await findNextPdfPage({ ...options, readNative: async () => "Paragraphe natif", readExtracted: async (index, signal) => {
    assert.equal(signal, controller.signal);
    extracted.push(index);
    return "Tableau OCR : pression 3,1 bar";
  } });
  assert.deepEqual(result, { kind: "found", pageIndex: 2 });
  assert.deepEqual(extracted, [2]);
});

test("absent expression examines exactly one full cycle; empty expression reads nothing", async () => {
  const { visits, options } = fixture();
  assert.deepEqual(await findNextPdfPage({ ...options, expression: "introuvable" }), { kind: "absent" });
  assert.deepEqual(visits, [2, 0, 1]);
  visits.length = 0;
  assert.deepEqual(await findNextPdfPage({ ...options, expression: " \n " }), { kind: "absent" });
  assert.deepEqual(visits, []);
});

test("an already aborted search reads neither native nor extracted text", async () => {
  const { controller, visits, options } = fixture();
  controller.abort();
  assert.deepEqual(await findNextPdfPage(options), { kind: "cancelled" });
  assert.deepEqual(visits, []);
});

test("a version change during native reading rejects its result before extracted reading", async () => {
  const { options } = fixture();
  const pending = deferredText();
  let current = true;
  let extracted = 0;
  const result = findNextPdfPage({ ...options, isCurrent: () => current, readNative: () => pending.promise,
    readExtracted: async () => { extracted++; return "pression"; } });
  current = false;
  pending.resolve("pression");
  assert.deepEqual(await result, { kind: "cancelled" });
  assert.equal(extracted, 0);
});

test("a newer search during extracted reading rejects the old matching result", async () => {
  const { options } = fixture();
  const pending = deferredText();
  const started = deferredText();
  let generation = 1;
  const result = findNextPdfPage({ ...options, isCurrent: () => generation === 1,
    readExtracted: () => { started.resolve(""); return pending.promise; } });
  await started.promise;
  generation = 2;
  pending.resolve("pression");
  assert.deepEqual(await result, { kind: "cancelled" });
});

test("aborting an extracted read cannot return a match or a user-visible failure", async () => {
  const { options, controller } = fixture();
  const pending = deferredText();
  const started = deferredText();
  const result = findNextPdfPage({ ...options, readExtracted: () => { started.resolve(""); return pending.promise; } });
  await started.promise;
  controller.abort();
  pending.reject(new Error("lecture remplacée"));
  assert.deepEqual(await result, { kind: "cancelled" });
});

test("a current native or extracted failure remains an actual failure", async () => {
  const { options } = fixture();
  const native = new Error("Lecture PDF refusée");
  await assert.rejects(findNextPdfPage({ ...options, readNative: async () => { throw native; } }), error => error === native);
  const extracted = new Error("Provenance indisponible");
  await assert.rejects(findNextPdfPage({ ...options, readExtracted: async () => { throw extracted; } }), error => error === extracted);
});

test("reading identity retains a source across page movement but changes for another revision", () => {
  const source = { revision: "R1" };
  const reading = { versionId: "same-version", source };
  assert.equal(samePdfReading(reading, { ...reading }), true);
  assert.equal(samePdfReading(reading, { ...reading, source: { revision: "R2" } }), false);
  assert.equal(samePdfReading(reading, { ...reading, source: null }), false);
  assert.equal(samePdfReading(reading, { ...reading, versionId: "other-version" }), false);
});

test("opening a second source of the same version invalidates an extracted match still in flight", async () => {
  const { options } = fixture();
  const pending = deferredText();
  const started = deferredText();
  const reading = { versionId: "same-version", source: { revision: "R1" } };
  let current = reading;
  const result = findNextPdfPage({ ...options, isCurrent: () => samePdfReading(reading, current),
    readExtracted: () => { started.resolve(""); return pending.promise; } });
  await started.promise;
  current = { versionId: "same-version", source: { revision: "R2" } };
  pending.resolve("pression");
  assert.deepEqual(await result, { kind: "cancelled" });
});
