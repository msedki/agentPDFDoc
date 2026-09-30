import { cp, mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const source = dirname(require.resolve("pdfjs-dist/package.json"));
const destination = new URL("../public/pdfjs/", import.meta.url);
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
