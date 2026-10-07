/**
 * KIT4-26 : `pnpm build` écrit out/build-provenance.json, que le fabricant du kit Linux compare au commit livré
 * (tools/dist/linux_kit.py, check_web_provenance : commit identique, sources_modified strictement faux, même
 * pnpm-lock.yaml). Ces tests exécutent le vrai script dans un dépôt Git jetable qui reproduit apps/web.
 *
 * DOUBLE « dépôt jetable » : dépôt Git créé sous le dossier temporaire, avec apps/web/{src,tests,README.md,
 * package.json,pnpm-lock.yaml} et une copie de scripts/write-provenance.mjs ; identité Git et configuration
 * globale neutralisées. Il ne vérifie pas le build Next.js lui-même, prouvé par le build réel avant fabrication.
 */
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { webRoot } from "./theme-support.ts";

type Provenance = {
  format: string; commit: string | null; sources_modified: boolean | null; modified_sources: string[];
  pnpm_lock_sha256: string | null; built_utc: string;
};

const LOCK = "lockfileVersion: '9.0'\n";
const gitEnvironment = { ...process.env, GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_NOSYSTEM: "1", LC_ALL: "C" };

function write(root: string, relative: string, content: string) {
  mkdirSync(dirname(join(root, relative)), { recursive: true });
  writeFileSync(join(root, relative), content, "utf8");
}

function git(root: string, ...args: string[]) {
  execFileSync("git", ["-c", "user.name=Essai", "-c", "user.email=essai@example.invalid", "-c", "commit.gpgsign=false", ...args],
    { cwd: root, env: gitEnvironment, stdio: ["ignore", "pipe", "pipe"] });
}

/** Dépôt jetable : apps/web committé, export `out` présent ; `withGit` à faux pour un dossier hors dépôt. */
function fixture(withGit = true): { root: string; web: string } {
  const root = mkdtempSync(join(tmpdir(), "web-provenance-"));
  const web = join(root, "apps", "web");
  write(web, "src/a.ts", "export const a = 1;\n");
  write(web, "src/b.ts", "export const b = 2;\n");
  write(web, "tests/unit/a.test.ts", "// essai\n");
  write(web, "README.md", "# Interface\n");
  write(web, "package.json", "{}\n");
  write(web, "pnpm-lock.yaml", LOCK);
  write(root, ".gitignore", "apps/web/out/\n");
  mkdirSync(join(web, "scripts"), { recursive: true });
  copyFileSync(join(webRoot, "scripts", "write-provenance.mjs"), join(web, "scripts", "write-provenance.mjs"));
  mkdirSync(join(web, "out"));
  if (withGit) {
    git(root, "init", "-q");
    git(root, "add", "-A");
    git(root, "commit", "-q", "-m", "essai");
  }
  return { root, web };
}

function run(web: string, folder = "out") {
  return spawnSync(process.execPath, ["scripts/write-provenance.mjs", folder], { cwd: web, encoding: "utf8", env: gitEnvironment });
}

function readRecord(web: string): Provenance {
  return JSON.parse(readFileSync(join(web, "out", "build-provenance.json"), "utf8")) as Provenance;
}

function head(root: string): string {
  return execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, env: gitEnvironment, encoding: "utf8" }).trim();
}

test("un export construit depuis un commit propre porte ce commit, aucune source modifiée et l'empreinte du verrou", () => {
  const { root, web } = fixture();
  try {
    const result = run(web);
    assert.equal(result.status, 0, result.stderr);
    const record = readRecord(web);
    assert.equal(record.format, "atelier-web-provenance-v1");
    assert.equal(record.commit, head(root));
    assert.equal(record.sources_modified, false);
    assert.deepEqual(record.modified_sources, []);
    assert.equal(record.pnpm_lock_sha256, createHash("sha256").update(LOCK).digest("hex"));
    assert.match(record.built_utc, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    assert.ok(!readFileSync(join(web, "out", "build-provenance.json"), "utf8").includes(root), "aucun chemin absolu du poste");
    assert.match(result.stdout, /sources conformes au commit/);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("une source modifiée, ajoutée ou supprimée est nommée ; README.md et tests/ n'entrent pas dans l'export", () => {
  const { root, web } = fixture();
  try {
    write(web, "src/a.ts", "export const a = 3;\n");
    write(web, "src/neuf.ts", "export const n = 0;\n");
    rmSync(join(web, "src", "b.ts"));
    write(web, "README.md", "# Interface modifiée\n");
    write(web, "tests/unit/a.test.ts", "// essai modifié\n");
    const result = run(web);
    assert.equal(result.status, 0, result.stderr);
    const record = readRecord(web);
    assert.equal(record.sources_modified, true);
    assert.deepEqual(record.modified_sources, ["src/a.ts", "src/b.ts", "src/neuf.ts"]);
    assert.match(result.stderr, /sources modifiées \(3\) ; un kit Linux refusera cet export/);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("un renommage indexé nomme le chemin d'origine et le nouveau chemin", () => {
  const { root, web } = fixture();
  try {
    git(root, "mv", "apps/web/src/a.ts", "apps/web/src/renomme.ts");
    assert.equal(run(web).status, 0);
    assert.deepEqual(readRecord(web).modified_sources, ["src/a.ts", "src/renomme.ts"]);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("un verrou pnpm modifié est une source modifiée et change l'empreinte", () => {
  const { root, web } = fixture();
  try {
    write(web, "pnpm-lock.yaml", `${LOCK}# changé\n`);
    assert.equal(run(web).status, 0);
    const record = readRecord(web);
    assert.deepEqual(record.modified_sources, ["pnpm-lock.yaml"]);
    assert.notEqual(record.pnpm_lock_sha256, createHash("sha256").update(LOCK).digest("hex"));
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("hors d'un dépôt Git, la preuve est écrite sans commit et le build n'échoue pas", () => {
  const { root, web } = fixture(false);
  try {
    const result = run(web);
    assert.equal(result.status, 0, result.stderr);
    const record = readRecord(web);
    assert.equal(record.commit, null);
    assert.equal(record.sources_modified, null);
    assert.deepEqual(record.modified_sources, []);
    assert.match(result.stderr, /sans commit \(Git absent ou hors dépôt\)/);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("sans export, rien n'est écrit et le code vaut 2", () => {
  const { root, web } = fixture();
  try {
    const result = run(web, "absent");
    assert.equal(result.status, 2);
    assert.match(result.stderr, /Export absent : absent ; lancer d'abord le build/);
    assert.equal(existsSync(join(web, "absent")), false);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("le build écrit la preuve après le contrôle des chemins de l'export", () => {
  const { scripts } = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8")) as { scripts: { build: string } };
  assert.ok(scripts.build.endsWith("node scripts/check-export-paths.mjs out && node scripts/write-provenance.mjs out"), scripts.build);
});
