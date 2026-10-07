/**
 * R26 : aucun chemin absolu du poste de build dans l'export statique.
 * Constat d'origine : out/_next/static/chunks/aabb3c6d….js contenait
 * `createRequire("file:///media/…/node_modules/.pnpm/pdfjs-dist@6.3.289/…/build/pdf.mjs")`, valeur figée par
 * webpack pour `import.meta.url` dans la fabrique de canvas Node.js de PDF.js. Le contrôle
 * scripts/check-export-paths.mjs s'exécute sur l'export après chaque build ; ces tests en fixent les règles.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { createPdfJsLoader, PDFJS_LOAD_MESSAGE, PDFJS_MODULE_URL, PDFJS_WORKER_URL, PdfJsLoadError, type PdfJsModule } from "../../src/lib/pdfjs.ts";
import { readSource, sourceFiles, stripScriptComments, webRoot } from "./theme-support.ts";

type Finding = { file: string; rules: string[]; match: string };
type Scan = { files: number; findings: Finding[]; tolerated: Finding[] };

function exportFixture(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), "r26-export-"));
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), content);
  }
  return root;
}

function check(directory: string, ...extra: string[]): { status: number | null; scan?: Scan; stderr: string } {
  return checkWith(join(webRoot, "scripts/check-export-paths.mjs"), directory, ...extra);
}
function checkWith(script: string, directory: string, ...extra: string[]): { status: number | null; scan?: Scan; stderr: string } {
  const run = spawnSync(process.execPath, [script, directory, "--json", ...extra], { encoding: "utf8" });
  return { status: run.status, scan: run.stdout ? JSON.parse(run.stdout) as Scan : undefined, stderr: run.stderr };
}

function withFixture(files: Record<string, string>, body: (root: string) => void) {
  const root = exportFixture(files);
  try { body(root); } finally { rmSync(root, { recursive: true, force: true }); }
}

const leakedChunk = 'class eR extends eM{_createCanvas(t,e){return s.getBuiltinModule("module").createRequire("file:///media/safae/devsave1/agentPDFDoc-runtime/runtime/qa/r15-editorial-20261002T191600Z/frontend-toolchain-vzvpps/node_modules/.pnpm/pdfjs-dist@6.3.289/node_modules/pdfjs-dist/build/pdf.mjs")("@napi-rs/canvas").createCanvas(t,e)}}';

test("la fuite constatée dans l'export livré est un constat unique, avec son fichier et ses règles", () => {
  withFixture({ "index.html": "<!doctype html><title>Atelier</title>", "_next/static/chunks/aabb3c6d.js": leakedChunk }, root => {
    const { status, scan } = check(root);
    assert.equal(status, 1);
    assert.equal(scan?.files, 2);
    assert.equal(scan?.findings.length, 1);
    assert.equal(scan?.findings[0].file, "_next/static/chunks/aabb3c6d.js");
    assert.ok(scan?.findings[0].rules.includes("url-file"));
    assert.ok(scan?.findings[0].rules.includes("chemin-racine-posix"));
    assert.match(scan?.findings[0].match ?? "", /^file:\/\/\/media\/safae\/.*\/pdf\.mjs$/);
  });
});

test("les chaînes légitimes de Next.js et de PDF.js ne sont pas des constats", () => {
  withFixture({
    "_next/static/chunks/main.js": 'let a="/_next/static/media/inter.woff2",b="https://example.org/home/page";if("file:"===e.protocol)throw new Error("PDFNodeStream only supports file:// URLs.")',
    "workspace/index.txt": '1:I["/_next/static/chunks/app/workspace/page.js"]',
    // Constantes amont de pdfjs-dist 6.3.289 copiées telles quelles : HOME Emscripten et chemin de compilation d'openjpeg.
    "pdfjs/pdf.worker.min.mjs": 'ENV={USER:"web_user",LOGNAME:"web_user",PATH:"/",PWD:"/",HOME:"/home/web_user",LANG:"C"}',
    "pdfjs/wasm/openjpeg.wasm": "\u0000asm\u0000/tmp/openjpeg/src/bin/common/color.c\u0000",
  }, root => {
    const { status, scan } = check(root);
    assert.equal(status, 0, JSON.stringify(scan?.findings));
    assert.deepEqual(scan?.findings, []);
    assert.deepEqual(scan?.tolerated.map(entry => [entry.file, entry.match]), [["pdfjs/pdf.worker.min.mjs", "/home/web_user"], ["pdfjs/wasm/openjpeg.wasm", "/tmp/openjpeg"]]);
  });
});

test("une constante amont n'est admise que dans son fichier PDF.js et avec son contexte exact", () => {
  withFixture({
    "_next/static/chunks/app.js": 'ENV={HOME:"/home/web_user"}',
    "pdfjs/pdf.worker.min.mjs": 'const home="/home/web_user"',
    "pdfjs/autre.mjs": 'ENV={HOME:"/home/web_user"}',
    "pdfjs/wasm/openjpeg.wasm": "\u0000/tmp/openjpeg/build/x.c\u0000",
  }, root => {
    const { status, scan } = check(root);
    assert.equal(status, 1);
    assert.deepEqual(scan?.findings.map(entry => [entry.file, entry.match]), [
      ["_next/static/chunks/app.js", "/home/web_user"], ["pdfjs/autre.mjs", "/home/web_user"],
      ["pdfjs/pdf.worker.min.mjs", "/home/web_user"], ["pdfjs/wasm/openjpeg.wasm", "/tmp/openjpeg"],
    ]);
    assert.deepEqual(scan?.tolerated, []);
  });
});

test("les formes échappées, file: à un seul « / », les autres racines POSIX, UNC et lecteurs Windows sont repérés", () => {
  const leaks: Record<string, string> = {
    "json.js": String.raw`{"root":"\/home\/alice\/agentPDFDoc"}`,
    "url.js": 'const a="file:/home/alice/agentPDFDoc/x.mjs"',
    "url-echappee.json": String.raw`{"u":"file:\/\/\/srv\/build\/x.mjs"}`,
    "tmp.js": 'const a="/tmp/build-1234/apps/web"',
    "opt.js": 'const a="/opt/ci/agent/work"',
    "srv.js": 'const a="/srv/build/agentPDFDoc"',
    "root.js": 'const a="/root/.cache/next"',
    "unc.txt": String.raw`\\serveur\partage\agentPDFDoc`,
    "unc-echappe.js": String.raw`const a="\\\\serveur\\partage\\agentPDFDoc"`,
    "lecteur.js": String.raw`const a="D:\\build\\agentPDFDoc"`,
    "lecteur.html": String.raw`<p>E:\projets\agentPDFDoc</p>`,
  };
  withFixture(leaks, root => {
    const { status, scan } = check(root);
    assert.equal(status, 1);
    assert.deepEqual(scan?.findings.map(entry => entry.file).sort(), Object.keys(leaks).sort());
  });
  // Échappements Unicode, ternaire minifié et octets d'une police ne sont pas des chemins.
  withFixture({
    "regex.js": String.raw`const r=/[\\u00B7\\u0300-\\u036F\\u203F-\\u2040]/,t=e?a:/re/g,u="\\x41\\x42";`,
    "pdfjs/standard_fonts/FoxitDingbats.pfb": "\u0000V:\\yh\u0001",
  }, root => {
    const { status, scan } = check(root);
    assert.equal(status, 0, JSON.stringify(scan?.findings));
  });
});

test("lancé par un lien symbolique, le contrôle s'exécute ; importé, il échoue bruyamment au lieu de rendre 0", () => {
  withFixture({ "_next/static/chunks/aabb3c6d.js": leakedChunk }, root => {
    const link = join(root, "..", `check-lien-${process.pid}.mjs`);
    symlinkSync(join(webRoot, "scripts/check-export-paths.mjs"), link);
    try {
      const { status, scan } = checkWith(link, root);
      assert.equal(status, 1, "la fuite est signalée par le lien comme par le script");
      assert.equal(scan?.findings.length, 1);
    } finally { rmSync(link, { force: true }); }
    const imported = spawnSync(process.execPath, ["--input-type=module", "-e", `await import(${JSON.stringify(join(webRoot, "scripts/check-export-paths.mjs"))});`], { encoding: "utf8" });
    assert.equal(imported.status, 2);
    assert.match(imported.stderr, /appel non reconnu, aucun contrôle effectué/);
  });
});

test("le build échoue lui-même si l'export livre un chemin du poste", () => {
  const { scripts } = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8")) as { scripts: Record<string, string> };
  assert.equal(scripts.build, "node scripts/prepare-assets.mjs && next build --webpack && node scripts/check-export-paths.mjs out && node scripts/write-provenance.mjs out");
});

test("les chemins d'un poste Windows sont repérés, sous forme simple, échappée ou d'URL", () => {
  withFixture({
    "a.js": String.raw`const a="C:\\Users\\build\\agentPDFDoc\\apps\\web";`,
    "b.json": String.raw`{"root":"C:\Users\build\agentPDFDoc"}`,
    "c.js": 'import.meta.url="file:///D:/agentPDFDoc/apps/web/node_modules/pdfjs-dist/build/pdf.mjs"',
  }, root => {
    const { status, scan } = check(root);
    assert.equal(status, 1);
    assert.deepEqual(scan?.findings.map(entry => entry.file), ["a.js", "b.json", "c.js"]);
    assert.ok(scan?.findings[2].rules.includes("url-file"));
  });
});

test("un chemin propre au poste est repéré même hors des dossiers personnels, y compris le projet lui-même", () => {
  withFixture({ "a.js": 'const root="/srv/ci-build/agentPDFDoc/apps/web/src";', "b.js": `const here=${JSON.stringify(join(webRoot, "src/lib/pdfjs.ts"))};` }, root => {
    const { status, scan } = check(root, "--host-path", "/srv/ci-build/agentPDFDoc");
    assert.equal(status, 1);
    assert.deepEqual(scan?.findings.map(entry => entry.file), ["a.js", "b.js"]);
    for (const finding of scan?.findings ?? []) assert.ok(finding.rules.includes("chemin-du-poste"), finding.file);
  });
});

test("un export absent ou vide n'est jamais déclaré conforme", () => {
  const missing = check(join(tmpdir(), "r26-export-absent-0"));
  assert.equal(missing.status, 2);
  assert.match(missing.stderr, /introuvable \(lancez d'abord le build\)/);
  withFixture({}, root => {
    const empty = check(root);
    assert.equal(empty.status, 2);
    assert.match(empty.stderr, /aucun fichier/);
  });
});

test("aucune source de l'interface n'importe pdfjs-dist à l'exécution : seul le chargeur natif de src/lib/pdfjs.ts y accède", () => {
  // Un import empaqueté de pdfjs-dist réintroduirait l'évaluation de import.meta.url par webpack au build.
  const runtimeImports = sourceFiles(/\.(ts|tsx)$/).filter(file => {
    const code = stripScriptComments(readSource(file));
    return /import\s*\(\s*["']pdfjs-dist|require\s*\(\s*["']pdfjs-dist|import\s+(?!type\b)[^;]*?\bfrom\s+["']pdfjs-dist/.test(code);
  });
  assert.deepEqual(runtimeImports, []);
  assert.match(readSource("lib/pdfjs.ts"), /import\(\/\* webpackIgnore: true \*\/ url\)/);
  assert.equal(PDFJS_MODULE_URL, "/pdfjs/pdf.min.mjs");
  assert.equal(PDFJS_WORKER_URL, "/pdfjs/pdf.worker.min.mjs");
});

test("le chargeur règle le worker local, partage un seul module et réessaie après un échec", async () => {
  const requested: string[] = [];
  let fail = true;
  const pdfjsModule = { GlobalWorkerOptions: { workerSrc: "" } } as unknown as PdfJsModule;
  const load = createPdfJsLoader(async url => {
    requested.push(url);
    if (fail) { fail = false; throw new TypeError("Failed to fetch dynamically imported module"); }
    return pdfjsModule;
  });
  // m4 : l'échec du module natif devient un message français exact ; l'erreur du navigateur reste en cause.
  await assert.rejects(load(), (error: unknown) => error instanceof PdfJsLoadError && error.message === PDFJS_LOAD_MESSAGE
    && error.cause instanceof TypeError && /dynamically imported module/.test(error.cause.message));
  const [first, second] = await Promise.all([load(), load()]);
  assert.equal(first, pdfjsModule);
  assert.equal(second, pdfjsModule);
  assert.equal(pdfjsModule.GlobalWorkerOptions.workerSrc, "/pdfjs/pdf.worker.min.mjs");
  assert.deepEqual(requested, ["/pdfjs/pdf.min.mjs", "/pdfjs/pdf.min.mjs"]);
});

test("un module PDF.js non chargé est annoncé comme tel dans le lecteur, avec l'action possible, sans texte anglais", () => {
  assert.equal(PDFJS_LOAD_MESSAGE, "Les fichiers du lecteur PDF n'ont pas été chargés (/pdfjs/pdf.min.mjs). Rechargez la page ; si l'échec persiste, vérifiez l'installation de l'interface : le dossier pdfjs de l'export doit être présent.");
  const viewer = readSource("components/pdf-viewer.tsx");
  assert.match(viewer, /<PanelError title=\{loadError\.error instanceof PdfJsLoadError \? "Lecteur PDF indisponible" : "Lecture de l'original impossible"\} message=\{errorText\(loadError\.error\)\}/);
});
