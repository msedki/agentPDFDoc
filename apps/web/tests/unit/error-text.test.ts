/**
 * Textes d'échec calculés au rendu (W018) : un composant garde l'échec lui-même, jamais son texte, et le
 * texte se calcule à l'affichage avec les commandes du lanceur connues à cet instant (`useErrorText`,
 * `ErrorText`). Tant qu'aucune commande n'est connue, `/health` est relu à intervalles croissants, en
 * nombre borné (`retryLauncherCommands`). Les composants React ne s'exécutent pas sous `node --test` :
 * leur câblage est vérifié dans la source, la logique dans les modules qu'ils appellent.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { ApiError, localFailure } from "../../src/lib/api-error.ts";
import { HEALTH_RETRY_DELAYS_MS, knownLauncherCommands, retryLauncherCommands, type LauncherCommands } from "../../src/lib/launcher.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import { httpFailureMessage, serviceUnreachableMessage } from "../../src/lib/warnings.ts";
import { readSource, sourceFiles, stripScriptComments } from "./theme-support.ts";

const LINUX = { open: "./rag.sh open", status: "./rag.sh status", logs: "./rag.sh logs", doctor: "./rag.sh doctor" };
const COMPONENTS = ["components/ui/action-button.tsx", "components/analysis-panel.tsx", "components/workspace.tsx", "components/library-panel.tsx",
  "components/pdf-viewer.tsx", "components/jobs-panel.tsx", "components/document-tools.tsx", "components/scope-control.tsx"];

test("no component freezes the text of a failure in a state", () => {
  const scripts = sourceFiles(/\.tsx?$/);
  const frozen = scripts.filter(file => /\bset\w+\(\s*errorMessage\(/.test(stripScriptComments(readSource(file))));
  assert.deepEqual(frozen, []);
  // Seul le composant commun appelle errorMessage ; les autres passent par lui et se redessinent avec les commandes.
  const callers = scripts.filter(file => file.startsWith("components/") && /\berrorMessage\(/.test(stripScriptComments(readSource(file))));
  assert.deepEqual(callers, ["components/ui/error-text.tsx"]);
  const common = stripScriptComments(readSource("components/ui/error-text.tsx"));
  assert.match(common, /const commands = useLauncherCommands\(\);\s*return error => errorMessage\(error, commands\);/);
  for (const file of COMPONENTS) assert.match(stripScriptComments(readSource(file)), /useErrorText\(\)|<ErrorText error=\{/, file);
});

test("components keep the failure itself and compute its text when they render", () => {
  const code = (file: string) => stripScriptComments(readSource(file));
  assert.match(code("components/ui/action-button.tsx"), /const message = \(failure \? errorText\(failure\.error\) : ""\) \|\| error \|\| "";/);
  const analysis = code("components/analysis-panel.tsx");
  assert.equal((analysis.match(/setError\(\{ error: failure \}\)/g) ?? []).length, 4);
  assert.match(analysis, /\{error && <p className="inline-error" role="alert"><CircleAlert size=\{14\} aria-hidden="true" \/><ErrorText error=\{error\.error\} \/><\/p>\}/);
  const workspace = code("components/workspace.tsx");
  assert.equal((workspace.match(/setFailure\(\{ error: failure \}\)/g) ?? []).length, 2);
  assert.match(workspace, /error=\{failure \? errorText\(failure\.error\) : ""\}/);
  assert.match(workspace, /error: readiness\.isError \? errorText\(readiness\.error\) : undefined/);
  const library = code("components/library-panel.tsx");
  assert.match(library, /setOpenError\(\{ error: failure \}\)/);
  assert.match(library, /importMutation\.isError \? errorText\(importMutation\.error\) : ""/);
  const viewer = code("components/pdf-viewer.tsx");
  for (const pattern of [/setFailure\(\{ error \}\)/, /setLoadError\(\{ error \}\)/, /setSearchStatus\(\{ error \}\)/]) assert.match(viewer, pattern);
  assert.match(code("components/jobs-panel.tsx"), /errorText\(jobs\.error\)/);
  assert.match(code("components/document-tools.tsx"), /setRemoveError\(\{ error: failure \}\)/);
  assert.match(code("components/scope-control.tsx"), /\$\{what\} : \$\{errorText\(error\)\}/);
});

test("a failure kept in a state is shown with the commands known when it renders", () => {
  const unreachable = localFailure("NETWORK_ERROR", serviceUnreachableMessage);
  const http = localFailure("HTTP_502", commands => httpFailureMessage(502, commands));
  // Message réel du service : 409 job_pausing de la réindexation (services/api/main.py).
  const service = new ApiError("job_pausing", "Mise en pause en cours pour ce document : attendez qu'elle aboutisse, puis reprenez ce traitement depuis le Suivi.");
  assert.ok(readFileSync(new URL("../../../../services/api/main.py", import.meta.url), "utf8").includes(`ApiError("job_pausing", ${JSON.stringify(service.message)}, 409`),
    "le message de cette fixture diffère de celui de services/api/main.py");
  assert.match(errorMessage(unreachable, null), /\(\.\\rag\.ps1 status sous Windows ou \.\/rag\.sh status sous Linux\)/);
  assert.match(errorMessage(unreachable, LINUX), /\(\.\/rag\.sh status\)/);
  assert.match(errorMessage(http, LINUX), /la commande \.\/rag\.sh logs en donne l'emplacement\.$/);
  // Un message du service n'est jamais réécrit, ni une erreur ordinaire.
  assert.equal(errorMessage(service, LINUX), service.message);
  assert.equal(errorMessage(new Error("Rendu interrompu."), LINUX), "Rendu interrompu.");
});

/** Minuterie simulée : chaque appel est noté, rien ne s'exécute sans `fire`. */
function fakeTimers() {
  const pending = new Map<number, { run: () => void; ms: number }>();
  const delays: number[] = [];
  let next = 0;
  return {
    timers: {
      set: (run: () => void, ms: number) => { delays.push(ms); pending.set(++next, { run, ms }); return next; },
      clear: (handle: unknown) => { pending.delete(handle as number); },
    },
    delays, pending,
    /** Déclenche la seule lecture programmée, puis laisse la réponse de /health se régler. */
    async fire() {
      assert.equal(pending.size, 1, "une seule lecture programmée à la fois");
      const [[handle, { run }]] = pending;
      pending.delete(handle);
      run();
      await new Promise(resolve => setTimeout(resolve, 0));
    },
  };
}

test("the health retries are spaced and bounded, never a tight loop", () => {
  assert.ok(HEALTH_RETRY_DELAYS_MS.length > 0 && HEALTH_RETRY_DELAYS_MS.length <= 6, `${HEALTH_RETRY_DELAYS_MS.length} relectures`);
  assert.ok(HEALTH_RETRY_DELAYS_MS.every((delay, index) => delay >= 1000 && (index === 0 || delay >= HEALTH_RETRY_DELAYS_MS[index - 1])), HEALTH_RETRY_DELAYS_MS.join(", "));
});

// Les tests suivants s'enchaînent : les commandes restent inconnues jusqu'à la réponse valide du quatrième.
test("a silent service is asked again after each delay, then no more", async () => {
  assert.equal(knownLauncherCommands(), null);
  const clock = fakeTimers();
  let calls = 0;
  retryLauncherCommands(async () => { calls++; throw new TypeError("fetch failed"); }, [1000, 2000, 4000], clock.timers);
  for (let attempt = 1; attempt <= 3; attempt++) {
    await clock.fire();
    assert.equal(calls, attempt);
  }
  assert.deepEqual(clock.delays, [1000, 2000, 4000]);
  assert.equal(clock.pending.size, 0, "plus aucune lecture après la dernière");
});

test("a reply without commands is not enough to stop; stopping cancels the next reading", async () => {
  const clock = fakeTimers();
  let calls = 0;
  const stop = retryLauncherCommands(async () => { calls++; return { status: "alive", service: "rag-api" }; }, [1000, 2000], clock.timers);
  await clock.fire();
  assert.equal(calls, 1);
  assert.equal(clock.pending.size, 1, "réponse sans commandes : nouvelle lecture programmée");
  stop();
  assert.equal(clock.pending.size, 0);
  assert.equal(knownLauncherCommands(), null);
});

test("a reading in flight is never doubled, and the announced commands end the retries", async () => {
  const clock = fakeTimers();
  let answer: (value: unknown) => void = () => undefined;
  let calls = 0;
  retryLauncherCommands(() => { calls++; return new Promise(resolve => { answer = resolve; }); }, [1000, 2000, 4000], clock.timers);
  await clock.fire();
  assert.equal(clock.pending.size, 0, "rien n'est programmé tant que /health n'a pas répondu");
  answer({ status: "alive", service: "rag-api", commands: LINUX });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls, 1);
  assert.deepEqual(knownLauncherCommands(), LINUX);
  assert.equal(clock.pending.size, 0, "commandes connues : plus de relecture");
});

test("nothing is scheduled when the commands are already known", () => {
  const clock = fakeTimers();
  const known: LauncherCommands | null = knownLauncherCommands();
  assert.ok(known);
  retryLauncherCommands(async () => { throw new Error("jamais appelé"); }, [1000], clock.timers);
  assert.deepEqual(clock.delays, []);
});

test("the session gate reads /health on every screen, keeps asking while the commands are unknown, and stops on unmount", () => {
  const gate = stripScriptComments(readSource("components/session-gate.tsx"));
  assert.match(gate, /stopRetry\.current\?\.\(\);\s*stopRetry\.current = mounted\.current \? retryLauncherCommands\(\(\) => api\.health\(\)\) : null;/);
  assert.match(gate, /setState\(await checkSession\(api\)\);\s*retryCommands\(\);/);
  // Lien refusé : aucune vérification de session, mais les commandes sont lues pour cet écran aussi.
  assert.match(gate, /setState\(\{ kind: "ended", reason: "link_invalid" \}\);\s*void readLauncherCommands\(api\)\.then\(retryCommands\);/);
  assert.match(gate, /return \(\) => \{ mounted\.current = false; window\.removeEventListener\(SESSION_ENDED_EVENT, ended\); stopRetry\.current\?\.\(\); \};/);
});
