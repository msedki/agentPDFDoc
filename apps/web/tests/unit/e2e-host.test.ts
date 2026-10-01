/**
 * Sondes de la recette E2E selon le poste (W018) : interpréteur du projet, identité du worker Node
 * et méthode de mesure mémoire. Le relevé réel est exécuté sur ce poste quand l'environnement
 * Python du projet (psutil compris) est présent ; sinon le test le dit et ne mesure rien.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import type { Browser, TestInfo } from "@playwright/test";
import { dataDirKey, memoryMethod, probeHost, projectPython, projectRoot, workerIdentity } from "../e2e/host.ts";
import { monitorBrowser } from "../e2e/resources.ts";

test("the probe accepts the two supported hosts only", () => {
  assert.equal(probeHost("win32"), "win32");
  assert.equal(probeHost("linux"), "linux");
  assert.throws(() => probeHost("darwin"), /Windows et Linux seulement \(plateforme darwin\)/);
});

test("Windows keeps its interpreter, worker name and measurement method unchanged", () => {
  assert.equal(projectPython("win32", "/racine"), resolve("/racine", ".venv/Scripts/python.exe"));
  assert.equal(workerIdentity("win32", "C:\\node\\node.exe"), "name:node.exe");
  assert.equal(memoryMethod("win32"), "psutil available host RAM; RSS/Windows committed private/USS per process of this Node worker and its Chromium descendants only. No summed RSS or host-peak claim.");
});

test("Linux uses the POSIX venv interpreter, the node process and names RSS and USS", () => {
  assert.equal(projectPython("linux", "/racine"), resolve("/racine", ".venv/bin/python"));
  // Node 24 nomme son thread principal « MainThread » : sous Linux, l'identité passe par l'exécutable.
  assert.equal(workerIdentity("linux", "/opt/node/bin/node"), "exe:/opt/node/bin/node");
  const method = memoryMethod("linux");
  assert.match(method, /RSS from \/proc\/<pid>\/statm/);
  assert.match(method, /USS from \/proc\/<pid>\/smaps/);
  assert.match(method, /no Windows private memory on Linux/);
  assert.equal(projectRoot, resolve(process.cwd(), "../.."));
});

test("the storage identity check is case-insensitive on Windows only", () => {
  // Windows (NTFS) : même dossier quelle que soit la casse, comme avant W018.
  assert.equal(dataDirKey("C:\\RAG\\Data", "win32"), dataDirKey("c:\\rag\\data", "win32"));
  // Linux : deux dossiers distincts qui ne diffèrent que par la casse ne sont pas confondus.
  assert.notEqual(dataDirKey("/srv/rag/Data", "linux"), dataDirKey("/srv/rag/data", "linux"));
  assert.equal(dataDirKey("/srv/rag/data", "linux"), "/srv/rag/data");
  // La garde de la cible lifecycle compare les chemins réels par cette clé, plus par toLowerCase().
  const target = readFileSync(new URL("../e2e/lifecycle-target.ts", import.meta.url), "utf8");
  assert.match(target, /expect\(dataDirKey\(realpathSync\(state\.data_dir\)\)\)\.toBe\(dataDirKey\(dataDir\)\)/);
  assert.doesNotMatch(target, /toLowerCase\(\)/);
});

/** Le relevé exige l'interpréteur du projet et psutil ; l'absence est dite, jamais maquillée en réussite. */
function probePrerequisite(): string | false {
  const python = projectPython();
  if (!existsSync(python)) return `interpréteur du projet absent : ${python}`;
  try {
    execFileSync(python, ["-c", "import psutil"], { stdio: "ignore", timeout: 15000, windowsHide: true });
    return false;
  } catch {
    return `psutil absent de ${python}`;
  }
}

test("the probe measures this live Node process on the current host", { skip: probePrerequisite() }, async () => {
  const attachments: { name: string; body: string }[] = [];
  let closed = false;
  const browser = { close: async () => { closed = true; } } as unknown as Browser;
  const info = { attach: async (name: string, options: { body: Buffer }) => { attachments.push({ name, body: options.body.toString("utf8") }); } } as unknown as TestInfo;
  const snapshot = await monitorBrowser(browser, "unit-host", info);
  assert.equal(snapshot.worker.id, process.pid);
  assert.ok(snapshot.worker.working_set_mib > 0, "RSS du worker");
  assert.ok((snapshot.worker.unique_set_mib ?? 0) > 0, `USS du worker : ${JSON.stringify(snapshot.errors)}`);
  if (probeHost() === "linux") assert.equal(snapshot.worker.private_mib, null, "pas de mémoire privée Windows sous Linux");
  assert.deepEqual(snapshot.chromium, [], "aucun navigateur lancé par ce test");
  assert.equal(attachments.length, 1);
  assert.equal(JSON.parse(attachments[0].body).method, memoryMethod());
  // Sous 1,5 Gio disponibles, la sonde ferme le navigateur de test et lève une erreur : on n'arrive pas ici.
  assert.equal(closed, false);
});
