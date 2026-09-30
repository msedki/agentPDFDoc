import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { buildSignature } from "../../src/lib/build-info.ts";
import { readSource, webRoot } from "./theme-support.ts";

test("without an injected revision the signature says so instead of guessing", () => {
  const signature = buildSignature("0.1.0", undefined);
  assert.equal(signature.label, "Atelier documentaire · version 0.1.0 · révision non tracée");
  assert.equal(signature.revision, null);
  assert.match(signature.detail, /Aucune révision n'a été injectée/);
  for (const invalid of ["", "   ", "HEAD", "main", "not-a-sha", "12345", 42, null]) assert.equal(buildSignature("0.1.0", invalid).revision, null, String(invalid));
});

test("an injected commit hash is shortened in the label and kept whole in the detail", () => {
  const revision = "E0BE4AC0123456789abcdef0123456789abcdef0";
  const signature = buildSignature("0.1.0", `  ${revision}\n`);
  assert.equal(signature.revision, revision.toLowerCase());
  assert.equal(signature.label, "Atelier documentaire · version 0.1.0 · révision e0be4ac01234");
  assert.match(signature.detail, new RegExp(revision.toLowerCase()));
});

test("an unreadable version is reported as unknown", () => {
  assert.equal(buildSignature(undefined, undefined).version, null);
  assert.match(buildSignature("latest", undefined).label, /version inconnue/);
  assert.equal(buildSignature("1.2.3-rc.1", undefined).version, "1.2.3-rc.1");
});

test("the help menu reads the version from apps/web/package.json, never a hard-coded value", () => {
  const packageVersion = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8")).version;
  assert.match(packageVersion, /^\d+\.\d+\.\d+/);
  const help = readSource("components/help-menu.tsx");
  assert.match(help, /import packageInfo from "\.\.\/\.\.\/package\.json"/);
  assert.match(help, /buildSignature\(packageInfo\.version, /);
  assert.doesNotMatch(help, new RegExp(packageVersion.replaceAll(".", "\\.")), "la version n'est pas recopiée dans le composant");
});
