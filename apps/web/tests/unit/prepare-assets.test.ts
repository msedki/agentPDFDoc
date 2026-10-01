/**
 * Copie des assets PDF.js (scripts/prepare-assets.mjs) : le dossier de destination ne garde que
 * les fichiers de la version installée, et son manifeste n'inventorie qu'eux.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { webRoot } from "./theme-support.ts";

test("assets left by a previous PDF.js copy are removed and never inventoried", () => {
  const destination = mkdtempSync(join(tmpdir(), "pdfjs-assets-"));
  try {
    mkdirSync(join(destination, "wasm"), { recursive: true });
    writeFileSync(join(destination, "wasm", "ancien-module.wasm"), "version précédente");
    writeFileSync(join(destination, "pdf.worker.ancien.mjs"), "version précédente");
    writeFileSync(join(destination, "manifest.json"), JSON.stringify({ package: "pdfjs-dist", version: "0.0.0", files: [] }));
    const output = execFileSync(process.execPath, [join(webRoot, "scripts/prepare-assets.mjs"), destination], { cwd: webRoot, encoding: "utf8" });
    assert.match(output, /PDF\.js \d+\.\d+\.\d+: \d+ local assets prepared/);
    assert.equal(existsSync(join(destination, "wasm", "ancien-module.wasm")), false);
    assert.equal(existsSync(join(destination, "pdf.worker.ancien.mjs")), false);
    const manifest = JSON.parse(readFileSync(join(destination, "manifest.json"), "utf8")) as { files: { path: string }[] };
    assert.ok(manifest.files.some(file => file.path === "pdf.worker.min.mjs"));
    assert.deepEqual(manifest.files.filter(file => /ancien/.test(file.path)), []);
  } finally {
    rmSync(destination, { recursive: true, force: true });
  }
});

test("a folder that is not a previous PDF.js copy is refused and left intact", () => {
  const destination = mkdtempSync(join(tmpdir(), "pdfjs-assets-"));
  try {
    writeFileSync(join(destination, "document.txt"), "à conserver");
    assert.throws(() => execFileSync(process.execPath, [join(webRoot, "scripts/prepare-assets.mjs"), destination], { cwd: webRoot, encoding: "utf8", stdio: "pipe" }),
      (error: { stderr?: string }) => /n'est pas une copie PDF\.js précédente/.test(String(error.stderr)));
    assert.equal(readFileSync(join(destination, "document.txt"), "utf8"), "à conserver");
  } finally {
    rmSync(destination, { recursive: true, force: true });
  }
});
