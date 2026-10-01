import { cp, mkdir, readFile, rm, writeFile, readdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const source = dirname(require.resolve("pdfjs-dist/package.json"));
// Destination : public/pdfjs/ ; un autre dossier peut être passé en argument (tests).
const destination = process.argv[2] ? pathToFileURL(resolve(process.argv[2]) + "/") : new URL("../public/pdfjs/", import.meta.url);
// Dossier entièrement généré : on le vide pour qu'aucun fichier d'une copie précédente ne soit exporté ni inventorié.
// public/pdfjs/ (ignoré par Git) est toujours vidé ; un dossier passé en argument ne l'est que s'il est vide
// ou porte le manifeste d'une copie PDF.js précédente.
const existing = await readdir(destination).catch(error => { if (error.code === "ENOENT") return []; throw error; });
if (existing.length) {
  const previous = await readFile(new URL("manifest.json", destination), "utf8").then(text => JSON.parse(text).package === "pdfjs-dist", () => false);
  if (process.argv[2] && !previous) throw new Error(`${fileURLToPath(destination)} n'est pas une copie PDF.js précédente (manifest.json absent ou étranger) : dossier laissé intact.`);
  await rm(destination, { recursive: true });
}
await mkdir(destination, { recursive: true });
for (const directory of ["cmaps", "wasm", "standard_fonts", "iccs"]) {
  await cp(join(source, directory), new URL(`${directory}/`, destination), { recursive: true });
}
await cp(join(source, "build/pdf.worker.min.mjs"), new URL("pdf.worker.min.mjs", destination));
await cp(join(source, "LICENSE"), new URL("LICENSE", destination));
const version = JSON.parse(await readFile(join(source, "package.json"), "utf8")).version;
const files = [];
async function inventory(directory, prefix = "") {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (!prefix && entry.name === "manifest.json") continue;
    const path = new URL(entry.name + (entry.isDirectory() ? "/" : ""), directory);
    if (entry.isDirectory()) await inventory(path, `${prefix}${entry.name}/`);
    else files.push({ path: prefix + entry.name, sha256: createHash("sha256").update(await readFile(path)).digest("hex") });
  }
}
await inventory(destination);
files.sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
await writeFile(new URL("manifest.json", destination), JSON.stringify({ package: "pdfjs-dist", version, files }, null, 2));
console.log(`PDF.js ${version}: ${files.length} local assets prepared`);
