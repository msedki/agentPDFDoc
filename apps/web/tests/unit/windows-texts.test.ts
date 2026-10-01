/**
 * Textes Windows identiques mot pour mot à ceux d'avant W018 (complément W018 du 01/10/2026). Les textes de
 * référence sont lus par `git show` dans le commit 26fa7a5, dernier commit avant les textes de lanceur de
 * l'atelier, et ne sont jamais recopiés : les modules sans import de ce commit (warnings.ts, session.ts) sont
 * chargés tels quels depuis un dossier temporaire, les autres textes sont extraits de leur source.
 * Les textes actuels sont calculés avec les commandes d'un poste Windows : réponse actuelle de /health, qui
 * annonce doctor, et réponse sans doctor, où la plateforme est connue par les autres commandes.
 * Sans git ou sans ce commit (archive, clone superficiel), les tests sont ignorés avec ce motif ; les mêmes
 * textes restent vérifiés en clair dans launcher.test.ts et session-check.test.ts.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { after } from "node:test";
import { pathToFileURL } from "node:url";
import { api } from "../../src/lib/api.ts";
import { launcherCommandsFrom, launcherText, openCommandChoices, type LauncherCommands } from "../../src/lib/launcher.ts";
import { sessionScreen, type SessionEndReason } from "../../src/lib/session.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import { httpFailureMessage, readinessSentence, serviceUnreachableMessage } from "../../src/lib/warnings.ts";
import { readSource, stripScriptComments, webRoot } from "./theme-support.ts";

const REFERENCE = "26fa7a54cbfae1725fb18ebd5d4a25a17d6f5372";

function referenceSource(path: string): string | null {
  try {
    return execFileSync("git", ["show", `${REFERENCE}:apps/web/${path}`], { cwd: webRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return null;
  }
}

const sources = Object.fromEntries(["src/lib/warnings.ts", "src/lib/session.ts", "src/lib/api.ts", "src/lib/utils.ts", "src/components/app-topbar.tsx"]
  .map(path => [path, referenceSource(path)]));
const skip = Object.values(sources).some(source => source === null) ? `git ou commit ${REFERENCE.slice(0, 7)} indisponible` : false;

type ReferenceWarnings = { httpFailureMessage: (status: number) => string; readinessSentence: (blockers: string[]) => string };
type ReferenceSession = { OPEN_COMMAND: string; sessionScreen: (reason: SessionEndReason) => { title: string; body: string } };
const folder = mkdtempSync(join(tmpdir(), "rag-web-reference-"));
after(() => rmSync(folder, { recursive: true, force: true }));

/** Module du commit de référence, sans import, chargé depuis le dossier temporaire. */
async function referenceModule<T>(path: string): Promise<T> {
  // Extension .mts : module ECMAScript quel que soit le package.json le plus proche du dossier temporaire.
  const file = join(folder, path.split("/").at(-1)!.replace(/\.ts$/, ".mts"));
  writeFileSync(file, sources[path]!, "utf8");
  return await import(pathToFileURL(file).href) as T;
}

/** Littéral de chaîne JavaScript entre guillemets doubles capturé dans une source. */
function stringLiteral(source: string, pattern: RegExp): string {
  const raw = pattern.exec(source)?.[1];
  assert.ok(raw !== undefined, `motif ${pattern} absent de la source de référence`);
  return JSON.parse(`"${raw}"`) as string;
}

const health = (doctor: boolean) => launcherCommandsFrom({ status: "alive", service: "rag-api", commands: {
  open: ".\\rag.ps1 open", status: ".\\rag.ps1 status", logs: ".\\rag.ps1 logs", ...(doctor ? { doctor: ".\\rag.ps1 doctor" } : {}) } })!;
const WINDOWS: [string, LauncherCommands][] = [["/health actuel", health(true)], ["/health sans doctor", health(false)]];

test("readiness and HTTP failure texts are those of the reference commit", { skip }, async () => {
  const reference = await referenceModule<ReferenceWarnings>("src/lib/warnings.ts");
  for (const [label, commands] of WINDOWS) {
    for (const status of [404, 409, 500, 502, 503]) assert.equal(httpFailureMessage(status, commands), reference.httpFailureMessage(status), `${label}, HTTP ${status}`);
    for (const blockers of [["qdrant_not_ready"], ["ollama_not_ready", "qdrant_not_ready"], ["future_check_not_ready"]]) {
      assert.equal(readinessSentence(blockers, commands), reference.readinessSentence(blockers), `${label}, ${blockers.join(", ")}`);
    }
  }
});

test("session screens and the opening command are those of the reference commit", { skip }, async () => {
  const reference = await referenceModule<ReferenceSession>("src/lib/session.ts");
  for (const [label, commands] of WINDOWS) {
    for (const reason of ["session_required", "session_expired", "session_closed", "link_invalid"] as SessionEndReason[]) {
      assert.deepEqual(sessionScreen(reason, commands), reference.sessionScreen(reason), `${label}, ${reason}`);
    }
    assert.deepEqual(openCommandChoices(commands), [{ system: null, command: reference.OPEN_COMMAND }], label);
  }
});

test("failures written by the workspace are those of the reference commit, through the real client", { skip }, async () => {
  const unreachable = stringLiteral(sources["src/lib/api.ts"]!, /throw new ApiError\("NETWORK_ERROR", "((?:[^"\\]|\\.)*)"\);/);
  const fallback = stringLiteral(sources["src/lib/utils.ts"]!, /error instanceof Error \? error\.message : "((?:[^"\\]|\\.)*)";/);
  const reference = await referenceModule<ReferenceWarnings>("src/lib/warnings.ts");
  const original = globalThis.fetch;
  const failures: unknown[] = [];
  try {
    globalThis.fetch = (async () => { throw new TypeError("fetch failed"); }) as typeof fetch;
    await api.jobs().catch((error: unknown) => failures.push(error));
    globalThis.fetch = (async () => new Response(null, { status: 500 })) as typeof fetch;
    await api.jobs().catch((error: unknown) => failures.push(error));
  } finally {
    globalThis.fetch = original;
  }
  assert.equal(failures.length, 2);
  for (const [label, commands] of WINDOWS) {
    assert.equal(serviceUnreachableMessage(commands), unreachable, label);
    assert.equal(errorMessage(failures[0], commands), unreachable, label);
    assert.equal(errorMessage(failures[1], commands), reference.httpFailureMessage(500), label);
    assert.equal(errorMessage(null, commands), fallback, label);
    assert.equal(errorMessage("échec sans objet Error", commands), fallback, label);
  }
});

test("the closing tooltip of the top bar is that of the reference commit", { skip }, () => {
  const before = /title="(Ferme la session de ce navigateur\. Pour revenir : [^"]*)"/.exec(sources["src/components/app-topbar.tsx"]!)?.[1];
  assert.ok(before, "info-bulle absente de la source de référence");
  const template = /title=\{`(Ferme la session de ce navigateur\. Pour revenir : \$\{launcherText\("open", commands\)\} depuis le dossier du projet\.)`\}/
    .exec(stripScriptComments(readSource("components/app-topbar.tsx")))?.[1];
  assert.ok(template, "info-bulle actuelle introuvable");
  for (const [label, commands] of WINDOWS) {
    assert.equal(template.replace('${launcherText("open", commands)}', launcherText("open", commands)), before, label);
  }
});
