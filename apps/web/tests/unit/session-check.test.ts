/**
 * Ordre d'arrivée de GET /health et de GET /session (W018) : le texte d'un échec cite la commande
 * du lanceur connue au moment de l'affichage, pas celle connue au moment de l'échec. Sous Windows,
 * le texte final est celui d'avant W018, mot pour mot, quel que soit l'ordre des deux réponses.
 * Les requêtes passent par le vrai client (`api.ts`) et la vraie vérification de l'atelier
 * (`session-check.ts`) ; seul `fetch` est remplacé. Les tests s'enchaînent : les commandes
 * retenues par l'un restent connues du suivant, comme dans l'atelier.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { api } from "../../src/lib/api.ts";
import { knownLauncherCommands, openCommandChoices } from "../../src/lib/launcher.ts";
import { sessionScreen } from "../../src/lib/session.ts";
import { checkSession, unreachableText } from "../../src/lib/session-check.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import { readSource, stripScriptComments } from "./theme-support.ts";

const WINDOWS_HEALTH = { status: "alive", service: "rag-api", commands: { open: ".\\rag.ps1 open", status: ".\\rag.ps1 status", logs: ".\\rag.ps1 logs" } };
const LINUX_HEALTH = { status: "alive", service: "rag-api", commands: { open: "./rag.sh open", status: "./rag.sh status", logs: "./rag.sh logs" } };
// Textes Windows d'avant W018 (commit 26fa7a5, src/lib/api.ts et src/lib/warnings.ts).
const WINDOWS_HTTP_500 = "Le service local a échoué (HTTP 500). Réessayez ; si l'échec persiste, consultez son journal : la commande .\\rag.ps1 logs en donne l'emplacement.";
const WINDOWS_UNREACHABLE = "Le service local ne répond pas. Vérifiez qu'il est démarré (.\\rag.ps1 status), puis réessayez.";
const BOTH_HTTP_500 = "Le service local a échoué (HTTP 500). Réessayez ; si l'échec persiste, consultez son journal : la commande .\\rag.ps1 logs sous Windows ou ./rag.sh logs sous Linux en donne l'emplacement.";
const BOTH_UNREACHABLE = "Le service local ne répond pas. Vérifiez qu'il est démarré (.\\rag.ps1 status sous Windows ou ./rag.sh status sous Linux), puis réessayez.";

type Pending = { resolve: (response: Response) => void; reject: (error: unknown) => void };

/** Remplace `fetch` : chaque chemin reste en attente jusqu'à ce que le test le règle, dans l'ordre voulu. */
function controlledFetch() {
  const pending = new Map<string, Pending>();
  const original = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL) => new Promise<Response>((resolve, reject) => {
    pending.set(String(input), { resolve, reject });
  })) as typeof fetch;
  const take = (path: string) => {
    const entry = pending.get(path);
    assert.ok(entry, `requête ${path} attendue ; en attente : ${[...pending.keys()].join(", ") || "aucune"}`);
    pending.delete(path);
    return entry;
  };
  return {
    respond: (path: string, status: number, body?: unknown) => take(path).resolve(new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })),
    fail: (path: string) => take(path).reject(new TypeError("fetch failed")),
    restore: () => { globalThis.fetch = original; },
  };
}

/** Laisse s'écouler les promesses et la lecture JSON des réponses déjà réglées. */
const settle = (ms = 10) => new Promise(resolve => setTimeout(resolve, ms));

test("/session answered before /health: the texts become the exact Windows ones once /health arrives", async () => {
  assert.equal(knownLauncherCommands(), null, "aucune commande connue au départ");
  const server = controlledFetch();
  try {
    const checking = checkSession(api, 20);
    const jobs = api.jobs().then(() => null, (error: unknown) => error);
    await settle();
    server.respond("/api/v1/session", 500);
    server.fail("/api/v1/jobs");
    // /health n'a pas répondu dans l'attente bornée : l'écran s'affiche avec les deux formes.
    const state = await checking;
    const jobsFailure = await jobs;
    assert.equal(state.kind, "unreachable");
    if (state.kind !== "unreachable") return;
    assert.equal(unreachableText(state.failure, knownLauncherCommands()), BOTH_HTTP_500);
    assert.equal(errorMessage(jobsFailure), BOTH_UNREACHABLE);
    server.respond("/api/v1/health", 200, WINDOWS_HEALTH);
    await settle();
    // Même échec, affiché de nouveau : la commande annoncée par le poste Windows, texte d'avant W018.
    assert.equal(unreachableText(state.failure, knownLauncherCommands()), WINDOWS_HTTP_500);
    assert.equal(errorMessage(jobsFailure), WINDOWS_UNREACHABLE);
  } finally {
    server.restore();
  }
});

test("/health answered first gives the same Windows text directly", async () => {
  const server = controlledFetch();
  try {
    const checking = checkSession(api, 5000);
    await settle();
    server.respond("/api/v1/health", 200, WINDOWS_HEALTH);
    await settle();
    server.respond("/api/v1/session", 500);
    const state = await checking;
    assert.equal(state.kind, "unreachable");
    if (state.kind === "unreachable") assert.equal(unreachableText(state.failure, knownLauncherCommands()), WINDOWS_HTTP_500);
  } finally {
    server.restore();
  }
});

test("the gate waits for /health, within its bound, before leaving the check", async () => {
  const server = controlledFetch();
  try {
    let settled = false;
    const checking = checkSession(api, 5000).finally(() => { settled = true; });
    await settle();
    server.respond("/api/v1/session", 401, { code: "session_required", message: "Session requise." });
    await settle(50);
    assert.equal(settled, false, "l'écran de session attend la réponse de /health");
    server.respond("/api/v1/health", 200, LINUX_HEALTH);
    assert.deepEqual(await checking, { kind: "ended", reason: "session_required" });
    assert.deepEqual(knownLauncherCommands(), LINUX_HEALTH.commands);
    assert.deepEqual(openCommandChoices(knownLauncherCommands()), [{ system: null, command: "./rag.sh open" }]);
    assert.match(sessionScreen("session_required", knownLauncherCommands()).body, /Dans un terminal, depuis le dossier du projet, lancez la commande ci-dessous :/);
  } finally {
    server.restore();
  }
});

test("a failing /health neither delays the gate nor forgets the commands already announced", async () => {
  const server = controlledFetch();
  try {
    const started = Date.now();
    const checking = checkSession(api, 5000);
    await settle();
    server.respond("/api/v1/health", 404);
    server.respond("/api/v1/session", 200, { authenticated: true, method: "session", environment: "development", idle_timeout_minutes: 30 });
    assert.deepEqual(await checking, { kind: "open" });
    assert.ok(Date.now() - started < 1000, `${Date.now() - started} ms`);
    assert.deepEqual(knownLauncherCommands(), LINUX_HEALTH.commands);
  } finally {
    server.restore();
  }
});

function assertGateFailureRendering(gate: string) {
  assert.match(gate, /checkSession\(api\)\.then\(nextState => \{\s*setState\(nextState\);/);
  assert.match(gate, /const commands = useLauncherCommands\(\);/);
  assert.match(gate, /message=\{unreachableText\(state\.failure, commands\)\}/);
  // Le hook de SessionEnded, après cet écran, ne prouve pas le câblage de l'échec réseau.
  assert.match(gate, /const commands = useLauncherCommands\(\);[\s\S]*?message=\{unreachableText\(state\.failure, commands\)\}/);
  assert.doesNotMatch(gate, /kind: "unreachable", message/);
  assert.doesNotMatch(gate, /\.message\b/);
}

test("the gate keeps the failure, not its text, and computes the text when it renders", () => {
  assertGateFailureRendering(stripScriptComments(readSource("components/session-gate.tsx")));
});

test("gate failure guard rejects discarding the response or freezing its message", () => {
  const gate = stripScriptComments(readSource("components/session-gate.tsx"));
  assertGateFailureRendering(gate);
  for (const [before, after] of [
    ["setState(nextState)", 'setState({ kind: "open" })'],
    ["setState(nextState)", 'setState({ kind: "unreachable", message: nextState.message })'],
    ["unreachableText(state.failure, commands)", '"Service indisponible."'],
    ["const commands = useLauncherCommands();", "const commands = null;"],
  ]) {
    const mutant = gate.replace(before, after);
    assert.notEqual(mutant, gate, `mutation exercée : ${before}`);
    assert.throws(() => assertGateFailureRendering(mutant), assert.AssertionError);
  }
});
