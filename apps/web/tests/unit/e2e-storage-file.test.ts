import assert from "node:assert/strict";
import fs from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { type TestContext } from "node:test";
import { writeStorageStatePrivate } from "../e2e/storage-state.ts";

const state = { cookies: [], origins: [], fixture: "synthetic-session-state" };
function fixture(t: TestContext) {
  const directory = fs.mkdtempSync(join(tmpdir(), "rag-authstate-unit-"));
  fs.chmodSync(directory, 0o700);
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return { directory, target: join(directory, "state.json") };
}
function previousState(target: string) {
  fs.writeFileSync(target, "previous-synthetic-state", { mode: 0o600 });
}
function unchanged(directory: string, target: string) {
  assert.equal(fs.readFileSync(target, "utf8"), "previous-synthetic-state");
  assert.deepEqual(fs.readdirSync(directory), ["state.json"]);
}

test("état QA : création privée dès open sous umask 002, contenu complet", t => {
  const { directory, target } = fixture(t), openedModes: number[] = [];
  const originalOpen = fs.openSync;
  t.mock.method(fs, "openSync", (...args: Parameters<typeof fs.openSync>) => {
    const descriptor = originalOpen(...args);
    if (String(args[0]).endsWith(".tmp")) openedModes.push(fs.fstatSync(descriptor).mode & 0o777);
    return descriptor;
  });
  const originalUmask = process.umask(0o002);
  try {
    writeStorageStatePrivate(target, state);
  } finally {
    process.umask(originalUmask);
  }
  assert.deepEqual(JSON.parse(fs.readFileSync(target, "utf8")), state);
  assert.deepEqual(fs.readdirSync(directory), ["state.json"]);
  if (process.platform !== "win32") {
    assert.deepEqual(openedModes, [0o600]);
    assert.equal(fs.statSync(target).mode & 0o777, 0o600);
  }
});

test("état QA : renouvellement atomique d'une cible propre, ancien inode intact", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  if (process.platform !== "win32") fs.chmodSync(target, 0o664);
  const previousDescriptor = fs.openSync(target, "r");
  try {
    writeStorageStatePrivate(target, state);
    assert.equal(fs.readFileSync(previousDescriptor, "utf8"), "previous-synthetic-state");
  } finally {
    fs.closeSync(previousDescriptor);
  }
  assert.deepEqual(JSON.parse(fs.readFileSync(target, "utf8")), state);
  assert.deepEqual(fs.readdirSync(directory), ["state.json"]);
  if (process.platform !== "win32") assert.equal(fs.statSync(target).mode & 0o777, 0o600);
});

test("état QA : sérialisation invalide refusée sans toucher la cible", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  assert.throws(() => writeStorageStatePrivate(target, undefined), /sérialisable/);
  const circular: Record<string, unknown> = {}; circular.self = circular;
  assert.throws(() => writeStorageStatePrivate(target, circular), /circular/i);
  unchanged(directory, target);
});

test("état QA : lien cible refusé sans toucher le fichier référencé", { skip: process.platform === "win32" }, t => {
  const { directory, target } = fixture(t), original = join(directory, "original.json");
  previousState(original);
  fs.symlinkSync(original, target);
  assert.throws(() => writeStorageStatePrivate(target, state), /sans lien/);
  assert.equal(fs.lstatSync(target).isSymbolicLink(), true);
  assert.equal(fs.readFileSync(original, "utf8"), "previous-synthetic-state");
  assert.deepEqual(fs.readdirSync(directory).sort(), ["original.json", "state.json"]);
});

test("état QA : cible non régulière refusée", t => {
  const { directory, target } = fixture(t);
  fs.mkdirSync(target);
  assert.throws(() => writeStorageStatePrivate(target, state), /cible régulière/);
  assert.equal(fs.statSync(target).isDirectory(), true);
  assert.deepEqual(fs.readdirSync(directory), ["state.json"]);
});

test("état QA : propriétaire étranger refusé (double explicite de métadonnées UID)", { skip: typeof process.getuid !== "function" }, t => {
  const { directory, target } = fixture(t);
  previousState(target);
  const originalStat = fs.lstatSync;
  t.mock.method(fs, "lstatSync", (...args: Parameters<typeof fs.lstatSync>) => {
    const entry = originalStat(...args);
    assert.ok(entry);
    if (args[0] === target) entry.uid = Number(process.getuid!()) + 1;
    return entry;
  });
  assert.throws(() => writeStorageStatePrivate(target, state), /propres au compte/);
  unchanged(directory, target);
});

test("état QA : dossier parent modifiable par d'autres comptes refusé", { skip: process.platform === "win32" }, t => {
  const { directory, target } = fixture(t);
  fs.chmodSync(directory, 0o777);
  try {
    assert.throws(() => writeStorageStatePrivate(target, state), /modifiable par un autre compte/);
    assert.deepEqual(fs.readdirSync(directory), []);
  } finally {
    fs.chmodSync(directory, 0o700);
  }
});

test("état QA : écriture partielle échouée ferme le fd, retire le temporaire, conserve la cible", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  let descriptor: number | undefined;
  t.mock.method(fs, "writeFileSync", (fd: number) => {
    descriptor = fd;
    fs.writeSync(fd, "partial-synthetic-state");
    throw new Error("controlled-partial-write-failure");
  });
  assert.throws(() => writeStorageStatePrivate(target, state), /controlled-partial-write-failure/);
  assert.equal(typeof descriptor, "number");
  assert.throws(() => fs.fstatSync(descriptor!), { code: "EBADF" });
  unchanged(directory, target);
});

test("état QA : refus du remplacement retire seulement le temporaire", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  t.mock.method(fs, "renameSync", () => { throw new Error("controlled-rename-failure"); });
  assert.throws(() => writeStorageStatePrivate(target, state), /controlled-rename-failure/);
  unchanged(directory, target);
});

test("état QA : remplacement concurrent détecté avant publication", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  const originalWrite = fs.writeFileSync;
  t.mock.method(fs, "writeFileSync", (...args: Parameters<typeof fs.writeFileSync>) => {
    originalWrite(...args);
    fs.unlinkSync(target);
    originalWrite(target, "concurrent-synthetic-state", { mode: 0o600 });
  });
  assert.throws(() => writeStorageStatePrivate(target, state), /changé pendant/);
  assert.equal(fs.readFileSync(target, "utf8"), "concurrent-synthetic-state");
  assert.deepEqual(fs.readdirSync(directory), ["state.json"]);
});

test("état QA : dossier parent qui est un lien refusé avant écriture", { skip: process.platform === "win32" }, t => {
  const { directory } = fixture(t), real = join(directory, "real"), link = join(directory, "link");
  fs.mkdirSync(real);
  fs.symlinkSync(real, link, "dir");
  assert.throws(() => writeStorageStatePrivate(join(link, "state.json"), state), /sans lien/);
  assert.deepEqual(fs.readdirSync(real), []);
  assert.equal(fs.lstatSync(link).isSymbolicLink(), true);
});

test("état QA : erreur d'écriture conservée avec erreur secondaire de fermeture", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  const primary = new Error("controlled-write-primary"), secondary = new Error("controlled-close-secondary");
  const originalClose = fs.closeSync;
  let descriptor: number | undefined;
  t.mock.method(fs, "writeFileSync", (fd: number) => { descriptor = fd; throw primary; });
  t.mock.method(fs, "closeSync", (fd: number) => { originalClose(fd); throw secondary; });
  assert.throws(() => writeStorageStatePrivate(target, state), error => {
    assert.ok(error instanceof AggregateError);
    assert.equal(error.cause, primary);
    assert.deepEqual(error.errors, [primary, secondary]);
    return true;
  });
  t.mock.restoreAll();
  assert.throws(() => fs.fstatSync(descriptor!), { code: "EBADF" });
  unchanged(directory, target);
});

test("état QA : erreur primaire conservée si le retrait du temporaire échoue", t => {
  const { directory, target } = fixture(t);
  previousState(target);
  const primary = new Error("controlled-write-primary"), secondary = new Error("controlled-unlink-secondary");
  t.mock.method(fs, "writeFileSync", (fd: number) => { fs.writeSync(fd, "partial-synthetic-state"); throw primary; });
  t.mock.method(fs, "unlinkSync", () => { throw secondary; });
  assert.throws(() => writeStorageStatePrivate(target, state), error => {
    assert.ok(error instanceof AggregateError);
    assert.equal(error.cause, primary);
    assert.deepEqual(error.errors, [primary, secondary]);
    return true;
  });
  t.mock.restoreAll();
  assert.equal(fs.readFileSync(target, "utf8"), "previous-synthetic-state");
  const remaining = fs.readdirSync(directory).filter(name => name !== "state.json");
  assert.equal(remaining.length, 1);
  const temporary = join(directory, remaining[0]);
  assert.ok(fs.lstatSync(temporary).isFile());
  if (process.platform !== "win32") assert.equal(fs.statSync(temporary).mode & 0o777, 0o600);
  // L'échec de cleanup est explicite ; seul ce fichier synthétique du test est maintenant retiré.
  fs.unlinkSync(temporary);
  unchanged(directory, target);
});
