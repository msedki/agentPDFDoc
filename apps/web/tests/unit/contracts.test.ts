/**
 * Dérive entre le contrat de l'API (`packages/contracts/contracts.json`) et l'atelier : états de document
 * et de traitement, événements et statuts du flux de réponse, champs d'un span sélectionné, commandes
 * de `/health` et matériel de la génération publié par `/jobs`. Le test lit le contrat versionné ; toute
 * valeur ajoutée, retirée ou renommée d'un côté seulement le fait échouer.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { DOCUMENT_STATES, GENERATION_DEVICES, JOB_STATES, QUERY_EVENT_TYPES, type Block } from "../../src/lib/types.ts";
import { readGeneration, readPlacement } from "../../src/lib/generation.ts";
import { documentStates, documentStatus, jobStates, jobStatus, queryStates, queryStatus } from "../../src/lib/status.ts";
import { scopeCoverage } from "../../src/lib/panel-state.ts";
import { wholeBlockSpan } from "../../src/lib/selection.ts";
import { INSTALLED_ACTIONS, launcherCommandsFrom } from "../../src/lib/launcher.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const contract = JSON.parse(readFileSync(new URL("../../../../packages/contracts/contracts.json", import.meta.url), "utf8"));
const values = (field: string) => field.split("|");

test("the contract read is the versioned schema 2", () => {
  assert.equal(contract.schema_version, 2);
  assert.equal(contract.api_prefix, "/api/v1");
});

test("document and job states match the contract exactly, each with a readable label", () => {
  assert.deepEqual([...DOCUMENT_STATES], values(contract.document.state));
  assert.deepEqual([...JOB_STATES], values(contract.job.state));
  for (const state of DOCUMENT_STATES) {
    assert.ok(Object.hasOwn(documentStates, state), `libellé de document manquant : ${state}`);
    assert.equal(documentStatus(state).known, true, state);
  }
  for (const state of JOB_STATES) {
    assert.ok(Object.hasOwn(jobStates, state), `libellé de traitement manquant : ${state}`);
    assert.equal(jobStatus(state).known, true, state);
  }
});

test("every unpublished contract document state gets a known exclusion reason in the scope coverage", () => {
  const documents = DOCUMENT_STATES.map((state, index) => ({ id: `d${index}`, folder_id: null, name: state, relative_path: `${state}.pdf`, state, page_count: 1, active_generation_id: null }));
  const coverage = scopeCoverage({ kind: "library" }, { folders: [], documents });
  assert.equal(coverage.queryable, 0);
  assert.ok(!coverage.excluded.some(item => item.reason === "unknown"), JSON.stringify(coverage.excluded));
  // Toutes les lignes sauf le document retiré (« deleted »), qui ne compte pas dans un périmètre.
  assert.equal(coverage.excluded.reduce((sum, item) => sum + item.count, 0), DOCUMENT_STATES.length - 1);
});

test("query stream events match the contract and the stream subscribes to exactly these", () => {
  assert.deepEqual([...QUERY_EVENT_TYPES].sort(), [...contract.query_events.types].sort());
  const stream = stripScriptComments(readSource("lib/stream.ts"));
  assert.match(stream, /for \(const type of QUERY_EVENT_TYPES\)/);
  assert.doesNotMatch(stream, /const eventTypes = \[/);
});

test("every query status of the contract has a readable label", () => {
  const statuses = [
    ...values(contract.query_events.status_data.state),
    contract.query_events.needs_clarification_data.state,
    ...values(contract.query_events.done_data.status),
    contract.query_events.cancelled_data.status,
    ...values(contract.query_run.states),
  ];
  assert.ok(statuses.length >= 15, `${statuses.length} statuts lus`);
  for (const status of statuses) {
    assert.ok(Object.hasOwn(queryStates, status), `libellé de réponse manquant : ${status}`);
    assert.equal(queryStatus(status).known, true, status);
  }
});

test("a selected span carries exactly the contract fields", () => {
  const block: Block = { id: "b1", page_index: 0, text: "Texte", precision: "block", extraction_revision_id: "r1", source_text_hash: "a".repeat(64) };
  const span = wholeBlockSpan(block);
  assert.ok(span);
  const expected = contract.scope.spans[0];
  assert.deepEqual(Object.keys(span).sort(), Object.keys(expected).sort());
  assert.equal(span.offsetUnit, expected.offsetUnit);
  assert.equal(contract.offset_unit.startsWith("Unicode code points"), true);
});

test("the launcher commands of the health contract are all read by the workspace", () => {
  const described: Record<string, string> = contract.health_response.commands;
  // Les quatre commandes citées par l'atelier, chacune décrite avec ses deux formes livrées.
  assert.deepEqual(Object.keys(described).sort(), ["doctor", "logs", "open", "status"]);
  for (const [action, description] of Object.entries(described)) {
    assert.ok(description.includes(`.\\rag.ps1 ${action}`) && description.includes(`./rag.sh ${action}`), description);
  }
  for (const launcher of [".\\rag.ps1", "./rag.sh"]) {
    const commands = Object.fromEntries(Object.keys(described).map(action => [action, `${launcher} ${action}`]));
    assert.deepEqual(launcherCommandsFrom({ commands }), commands);
  }
});

test("the launcher field of the health contract and the commands of an installation are read by the workspace", () => {
  const described = contract.health_response.launcher;
  assert.deepEqual(Object.keys(described).sort(), ["kind", "menu"]);
  assert.deepEqual(described.kind.split(":")[0].split("|"), ["installation", "projet"]);
  assert.match(described.menu, /^string\|null:/);
  for (const [action, description] of Object.entries(contract.health_response.commands as Record<string, string>)) {
    const french = INSTALLED_ACTIONS[action as keyof typeof INSTALLED_ACTIONS];
    assert.ok(description.includes(`<destination>/atelier ${french}`), description);
    const commands = { [action]: `/opt/atelier/programme/atelier ${french}` };
    assert.deepEqual(launcherCommandsFrom({ commands, launcher: { kind: "installation", menu: null } }), { ...commands, installation: { menu: null } });
    // --modele <tag> : décrit pour ouvrir et diagnostic, et lu pour ces seules actions.
    const withModel = { [action]: `/opt/atelier/programme/atelier ${french} --modele qwen3.5:2b` };
    const read = launcherCommandsFrom({ commands: withModel, launcher: { kind: "installation", menu: null } });
    assert.equal(description.includes("--modele <tag>"), read !== null, action);
  }
});

test("the generation hardware published by /jobs matches the contract and every described value is read (W025)", () => {
  const described = contract.jobs_response.generation;
  assert.deepEqual(Object.keys(described).sort(), ["device", "fallback", "model", "null", "processor"]);
  assert.deepEqual([...GENERATION_DEVICES], values(described.device));
  assert.match(described.fallback, /^boolean/);
  assert.match(described.model, /^string: exact served model/);
  // Valeur null décrite par le contrat (API lancée avec un double de la passerelle) : rien n'est affiché.
  assert.ok(Object.hasOwn(described, "null"));
  assert.equal(readGeneration(null), null);
  for (const device of GENERATION_DEVICES) assert.deepEqual(readGeneration({ device, fallback: false, processor: null }), { device, fallback: false, processor: null });
  assert.deepEqual(readGeneration({ device: "cpu", fallback: true, processor: null }), { device: "cpu", fallback: true, processor: null });
  // Chaque forme de la colonne PROCESSOR citée par le contrat est reconnue, la forme partielle avec ses deux parts.
  assert.match(described.processor, /^string\|null:/);
  const placements: [string, string][] = [["100% GPU", "gpu"], ["100% CPU", "cpu"], ["Unknown", "unknown"]];
  for (const [label, kind] of placements) {
    assert.ok(described.processor.includes(label), label);
    assert.equal(readPlacement(label)?.kind, kind, label);
  }
  assert.ok(described.processor.includes("<cpu>%/<gpu>% CPU/GPU"));
  assert.deepEqual(readPlacement("40%/60% CPU/GPU"), { kind: "partial", cpu: 40, gpu: 60 });
});
