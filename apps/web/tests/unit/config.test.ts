/**
 * Configuration de l'outillage web : version de pnpm verrouillée, alias shadcn existants.
 * Les valeurs sont lues dans les fichiers du dépôt, jamais recopiées d'une exécution.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { srcRoot, webRoot } from "./theme-support.ts";

const packageJson = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8")) as { packageManager?: string; engines?: Record<string, string> };

test("pnpm is pinned to the documented version with its registry integrity, so Corepack never resolves the latest", () => {
  // Format Corepack : nom@version+algorithme.empreinte-hexadécimale (dist.integrity du registre npm).
  assert.match(packageJson.packageManager ?? "", /^pnpm@10\.34\.1\+sha512\.[0-9a-f]{128}$/);
  assert.match(readFileSync(join(webRoot, "README.md"), "utf8"), /pnpm est\s+fixé à 10\.34\.1 par le champ `packageManager`/);
  assert.equal(packageJson.engines?.node, ">=22.13.0");
});

test("every shadcn alias of components.json designates an existing source path", () => {
  const { aliases } = JSON.parse(readFileSync(join(webRoot, "components.json"), "utf8")) as { aliases: Record<string, string> };
  const entries = Object.entries(aliases);
  assert.ok(entries.length >= 5, `${entries.length} alias lus`);
  const missing = entries.filter(([, alias]) => {
    assert.match(alias, /^@\//);
    const target = join(srcRoot, alias.slice(2));
    return !(existsSync(target) && statSync(target).isDirectory()) && !existsSync(`${target}.ts`) && !existsSync(`${target}.tsx`);
  }).map(([name, alias]) => `${name} → ${alias}`);
  assert.deepEqual(missing, []);
});
