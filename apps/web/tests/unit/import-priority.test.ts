/**
 * R26-UI-02 (suite), défaut D4 de la recette R26-KIT-02 : une spec qui importe sous « Priorité aux questions »
 * (marqueur durable pause-ingestion) laissait le document `queued` jusqu'au délai. Le helper partagé
 * tests/e2e/import-priority.ts choisit « Priorité aux imports » puis rétablit la priorité trouvée.
 *
 * DOUBLE « poste » : le service (runtime_mode de GET /api/v1/jobs, POST /api/v1/runtime/mode), le contexte du
 * navigateur, la page du scénario et la page dédiée au Suivi (boutons, aria-pressed) sont simulés en mémoire. Il
 * vérifie l'ordre des requêtes, le rétablissement et l'absence d'action sur la page du scénario ; l'interface et le
 * gouverneur réels sont vérifiés par l'E2E sur instance isolée (geometry.spec.ts sous « Priorité aux questions »).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { APIRequestContext, Page, TestInfo } from "@playwright/test";
import { PRIORITY_LABELS, RUNTIME_MODE_PATH, withImportPriority, type ImportPriorityRecord, type Priority } from "../e2e/import-priority.ts";

type ResponseDouble = { request: () => { method: () => string }; url: () => string; status: () => number };
type Waiting = { predicate: (response: ResponseDouble) => boolean; resolve: (response: ResponseDouble) => void };

/** DOUBLE « poste » : `refuse` liste les priorités que le service refuse (409, comme `interaction_active`). */
function workstationDouble(initial: Priority | null, refuse: Priority[] = []) {
  const state: { mode: Priority | null; panelOpen: boolean; openPages: number } = { mode: initial, panelOpen: false, openPages: 0 };
  const calls: string[] = [];
  const scenarioCalls: string[] = [];
  const attachments: { name: string; record: ImportPriorityRecord }[] = [];
  let waiting: Waiting | null = null;
  const modeOf = (name: string) => (Object.entries(PRIORITY_LABELS) as [Priority, string][]).find(([, label]) => label === name)?.[0];
  const request = {
    get: async (path: string) => {
      calls.push(`GET ${path}`);
      return { status: () => 200, json: async () => ({ jobs: [], total: 0, runtime_mode: state.mode }) };
    },
  };
  const button = (name: string) => ({
    click: async () => {
      calls.push(`clic « ${name} »`);
      if (name === "Suivi") { state.panelOpen = true; return; }
      if (!state.panelOpen) throw new Error(`DOUBLE poste : « ${name} » cliqué Suivi fermé`);
      if (name === "Fermer le suivi") { state.panelOpen = false; return; }
      const mode = modeOf(name);
      if (!mode) throw new Error(`DOUBLE poste : bouton inconnu « ${name} »`);
      calls.push(`POST ${RUNTIME_MODE_PATH} ${mode}`);
      const refused = refuse.includes(mode);
      if (!refused) state.mode = mode;
      const response: ResponseDouble = { request: () => ({ method: () => "POST" }), url: () => `http://127.0.0.1:40123${RUNTIME_MODE_PATH}`, status: () => refused ? 409 : 200 };
      if (waiting?.predicate(response)) { waiting.resolve(response); waiting = null; }
    },
    getAttribute: async (attribute: string) => attribute === "aria-pressed" && state.panelOpen ? String(state.mode === modeOf(name)) : null,
  });
  const suiviPage = {
    goto: async (url: string) => { calls.push(`goto ${url}`); state.panelOpen = false; },
    getByRole: (role: string, options: { name: string }) => { assert.equal(role, "button"); return button(options.name); },
    waitForResponse: (predicate: Waiting["predicate"]) => new Promise<ResponseDouble>(resolve => { waiting = { predicate, resolve }; }),
    close: async () => { calls.push("page du Suivi fermée"); state.openPages -= 1; },
  };
  const context = { newPage: async () => { calls.push("page du Suivi ouverte"); state.openPages += 1; return suiviPage; } };
  // Page du scénario : seul son contexte est utilisé ; toute autre action y serait consignée.
  const scenario = new Proxy({ context: () => context }, { get: (target, property) => property in target ? target[property as "context"]
    : (...args: unknown[]) => { scenarioCalls.push(`${String(property)}(${args.map(item => JSON.stringify(item)).join(", ")})`); } });
  const info = { attach: async (name: string, options: { body: Buffer }) => { attachments.push({ name, record: JSON.parse(options.body.toString("utf8")) }); } };
  return { state, calls, scenarioCalls, attachments, page: scenario as unknown as Page, request: request as unknown as APIRequestContext, info: info as unknown as TestInfo };
}

const choose = (mode: Priority) => ["page du Suivi ouverte", "goto /workspace/", "clic « Suivi »", `clic « ${PRIORITY_LABELS[mode]} »`, `POST ${RUNTIME_MODE_PATH} ${mode}`,
  "clic « Fermer le suivi »", "page du Suivi fermée", "GET /api/v1/jobs"];

test("« Priorité aux questions » trouvée : imports choisis avant l'action, questions rétablies après", async () => {
  const station = workstationDouble("interactive");
  const value = await withImportPriority(station.page, station.request, station.info, async () => {
    station.calls.push(`import (priorité ${station.state.mode})`);
    return "document importé";
  });
  assert.equal(value, "document importé");
  assert.deepEqual(station.calls, ["GET /api/v1/jobs", ...choose("ingestion"), "import (priorité ingestion)", ...choose("interactive"), "GET /api/v1/jobs"]);
  assert.equal(station.state.mode, "interactive");
  assert.deepEqual(station.scenarioCalls, [], "aucune navigation ni requête sur la page du scénario (journal watchPage intact)");
  assert.equal(station.state.openPages, 0);
  assert.deepEqual(station.attachments, [{ name: "import-priority", record: { initial: "interactive", during_import: "ingestion", restore_requested: true,
    after: "interactive", action_failed: false, restore_error: null } }]);
});

test("import en échec : la priorité trouvée est rétablie (finally) et l'erreur de l'import est rapportée telle quelle", async () => {
  const station = workstationDouble("interactive");
  const importError = new Error("Actual job exceeded the measured cold recipe deadline");
  await assert.rejects(withImportPriority(station.page, station.request, station.info, async () => {
    station.calls.push(`import (priorité ${station.state.mode})`);
    throw importError;
  }), error => error === importError);
  assert.deepEqual(station.calls, ["GET /api/v1/jobs", ...choose("ingestion"), "import (priorité ingestion)", ...choose("interactive"), "GET /api/v1/jobs"]);
  assert.equal(station.state.mode, "interactive");
  assert.deepEqual(station.attachments.map(item => item.record), [{ initial: "interactive", during_import: "ingestion", restore_requested: true,
    after: "interactive", action_failed: true, restore_error: null }]);
});

test("« Priorité aux imports » déjà choisie : aucun POST, rien à rétablir", async () => {
  const station = workstationDouble("ingestion");
  await withImportPriority(station.page, station.request, station.info, async () => { station.calls.push(`import (priorité ${station.state.mode})`); });
  assert.deepEqual(station.calls, ["GET /api/v1/jobs", "import (priorité ingestion)", "GET /api/v1/jobs"]);
  assert.equal(station.calls.some(call => call.startsWith("POST")), false);
  assert.equal(station.attachments[0].record.restore_requested, false);
  assert.equal(station.attachments[0].record.after, "ingestion");
});

test("rétablissement refusé après un import en échec : l'erreur de l'import reste rapportée, le refus est consigné", async () => {
  const station = workstationDouble("interactive", ["interactive"]);
  const importError = new Error("import en échec");
  await assert.rejects(withImportPriority(station.page, station.request, station.info, async () => { throw importError; }), error => error === importError);
  assert.equal(station.state.mode, "ingestion");
  assert.equal(station.state.openPages, 0, "page du Suivi fermée malgré le refus");
  const [{ record }] = station.attachments;
  assert.equal(record.action_failed, true);
  assert.equal(record.after, "ingestion");
  assert.match(record.restore_error ?? "", /POST \/api\/v1\/runtime\/mode \(« Priorité aux questions »\)/);
});

test("rétablissement refusé après un import réussi : la spec échoue sur le rétablissement", async () => {
  const station = workstationDouble("interactive", ["interactive"]);
  await assert.rejects(withImportPriority(station.page, station.request, station.info, async () => "document importé"),
    error => error instanceof Error && /Priorité aux questions/.test(error.message));
  assert.equal(station.attachments[0].record.action_failed, false);
  assert.ok(station.attachments[0].record.restore_error);
});

test("importPublished et r26-ocr-provenance passent par le helper partagé, sans copie locale", () => {
  const read = (path: string) => readFileSync(new URL(`../e2e/${path}`, import.meta.url), "utf8");
  const guards = read("guards.ts");
  assert.match(guards, /import \{ withImportPriority \} from "\.\/import-priority\.ts";/);
  const importPublished = guards.slice(guards.indexOf("export async function importPublished"));
  assert.match(importPublished.slice(0, importPublished.indexOf("\n}\n")), /return withImportPriority\(page, request, info, async \(\) => \{[\s\S]*uploadFromUi[\s\S]*waitJob/);
  const spec = read("r26-ocr-provenance.spec.ts");
  assert.match(spec, /importPublished\(page, request, input, info\)/);
  for (const local of ["async function priority", "async function choosePriority", "async function withImportPriority", "/api/v1/runtime/mode"]) {
    assert.equal(spec.includes(local), false, `copie locale retirée de r26-ocr-provenance.spec.ts : ${local}`);
  }
});
