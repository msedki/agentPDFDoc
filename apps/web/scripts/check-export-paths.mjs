/**
 * Contrôle de l'export statique : aucun chemin absolu du poste de build ne doit être livré.
 *
 * Usage : node scripts/check-export-paths.mjs [dossier] [--host-path <chemin>]... [--json]
 *   dossier       export à contrôler, `out` par défaut (relatif au dossier courant) ;
 *   --host-path   chemin du poste à rechercher en plus des chemins détectés (répétable) ;
 *   --json        résultat détaillé en JSON sur la sortie standard.
 * Code de sortie : 0 sans constat, 1 avec constats, 2 si le dossier est absent, vide ou illisible.
 *
 * Tous les fichiers sont lus octet par octet (latin1), binaires compris : une fuite peut se trouver
 * dans un chunk JavaScript, une charge RSC `.txt`, un manifeste JSON ou une page HTML.
 *
 * Repéré : URL file: suivie d'un chemin (un à trois « / », éventuellement échappés « \/ ») ; racines POSIX
 * /home, /media, /mnt, /Users, /run/media, /tmp, /opt, /srv, /root suivies d'un segment, en « / » ou « \/ » ;
 * profils Windows X:\Users ; chemins réels de ce poste (projet, magasin node_modules, dossier personnel,
 * --host-path) sous forme native, en « / » et échappée. Dans les fichiers texte seulement (hors polices,
 * cmaps, wasm, images), heuristiques Windows : lecteur suivi d'un dossier (X:\dossier\) et chemin UNC
 * (\\serveur\partage), simples ou échappés, hors séquences \uXXXX et \xXX.
 * Non couvert : chemins relatifs ; chemin découpé entre plusieurs chaînes ou reconstruit à l'exécution ;
 * encodage pourcentage (%2Fhome%2F), base64, UTF-16 ou contenu compressé ; chemin Windows en « / » hors URL
 * file: (D:/build/…, indiscernable d'un objet ou d'un ternaire minifié) ; autres racines POSIX (/var, /usr,
 * /data…) hors chemins réels de ce poste ; nom d'utilisateur ou d'hôte isolé, sans chemin.
 */
import { realpathSync } from "node:fs";
import { readdir, readFile, realpath, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = fileURLToPath(new URL("../", import.meta.url));

// Une URL file: suivie d'un chemin (le message de PDF.js « only supports file:// URLs » n'en a pas).
// Une racine POSIX non précédée d'un caractère de chemin : `/_next/static/media/` n'est pas visé.
// Un profil Windows, sous forme simple, échappée JSON ou en barres obliques.
const slash = String.raw`(?:\/|\\\/)`;
const notEscape = String.raw`(?!u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2})`;
const rules = [
  { rule: "url-file", pattern: new RegExp(String.raw`file:${slash}+[^\s"'\`<>)/\\][^\s"'\`<>)]*`, "g") },
  { rule: "chemin-racine-posix", pattern: new RegExp(String.raw`(?<![A-Za-z0-9_.~-])${slash}(?:home|media|mnt|Users|run${slash}media|tmp|opt|srv|root)${slash}[A-Za-z0-9._@-]+`, "g") },
  { rule: "profil-windows", pattern: /\b[A-Za-z]:(?:\\\\|\\|\/)(?:Users|Documents and Settings)(?:\\\\|\\|\/)[^\s"'`<>\\/]+/gi },
];
// Heuristiques réservées aux fichiers texte : dans une police ou un wasm, des octets quelconques les imitent.
const textRules = [
  { rule: "lecteur-windows", pattern: new RegExp(String.raw`(?<![A-Za-z0-9_$\\])[A-Za-z]:(?:\\\\|\\)${notEscape}[A-Za-z0-9._ -]+(?:\\\\|\\)`, "g") },
  { rule: "chemin-unc", pattern: new RegExp(String.raw`(?<![\\A-Za-z0-9])(?:\\\\){1,2}${notEscape}[A-Za-z][A-Za-z0-9.-]*[A-Za-z0-9](?:\\\\|\\)${notEscape}[A-Za-z0-9$_.-]+`, "g") },
];
const binaryExtensions = new Set([".bcmap", ".pfb", ".ttf", ".otf", ".woff", ".woff2", ".wasm", ".icc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf"]);

// Constantes des bibliothèques amont copiées telles quelles par prepare-assets.mjs, identiques sur tout poste :
// admises seulement dans le fichier PDF.js désigné et avec leur contexte exact.
const allowed = [
  // Emscripten : HOME par défaut du système de fichiers virtuel, `HOME:"/home/web_user"`, pas un dossier du poste.
  { files: ["pdfjs/pdf.worker.min.mjs", "pdfjs/wasm/openjpeg_nowasm_fallback.js"], before: 'HOME:"', text: "/home/web_user", after: '"',
    reason: "HOME par défaut du système de fichiers virtuel Emscripten (pdfjs-dist)" },
  // Chemin de compilation d'OpenJPEG gravé par la chaîne amont dans le module wasm (message d'assertion).
  { files: ["pdfjs/wasm/openjpeg.wasm"], before: "", text: "/tmp/openjpeg", after: "/src/bin/common/color.c",
    reason: "chemin de compilation d'OpenJPEG dans le wasm amont (pdfjs-dist)" },
];

function parseArguments(argv) {
  const options = { directory: "out", hostPaths: [], json: false };
  for (let index = 0; index < argv.length; index++) {
    const argument = argv[index];
    if (argument === "--json") options.json = true;
    else if (argument === "--host-path") {
      const value = argv[++index];
      if (!value) throw new Error("--host-path attend un chemin.");
      options.hostPaths.push(value);
    } else if (argument.startsWith("--")) throw new Error(`Option inconnue : ${argument}`);
    else options.directory = argument;
  }
  return options;
}

/** Racine du projet, magasin node_modules réel, dossier personnel : sous forme native, en « / » et échappée JSON. */
async function hostRoots(extra) {
  const candidates = [webRoot, resolve(webRoot, "../.."), homedir(), ...extra];
  for (const path of [webRoot, join(webRoot, "node_modules")]) {
    try { candidates.push(await realpath(path)); } catch { /* lien absent : rien à ajouter */ }
  }
  const roots = new Set();
  for (const candidate of candidates) {
    const path = candidate.replace(/[\\/]+$/, "");
    // Une racine seule (« / », « C: ») ne désigne pas le poste et apparaîtrait partout.
    if (path.split(/[\\/]/).filter(Boolean).length < 2) continue;
    for (const form of [path, path.replaceAll("\\", "/"), path.replaceAll("\\", "\\\\")]) roots.add(form);
  }
  return [...roots].sort((left, right) => right.length - left.length);
}

async function filesUnder(directory, found = []) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await filesUnder(path, found);
    else if (entry.isFile()) found.push(path);
  }
  return found;
}

function excerpt(text, index, length) {
  const start = Math.max(0, index - 60);
  return text.slice(start, Math.min(text.length, index + length + 60)).replace(/\s+/g, " ");
}

export async function scanExport(directory, extraHostPaths = []) {
  const root = resolve(directory);
  const info = await stat(root);
  if (!info.isDirectory()) throw new Error(`${root} n'est pas un dossier.`);
  const files = (await filesUnder(root)).sort();
  if (!files.length) throw new Error(`${root} ne contient aucun fichier : aucun export à contrôler.`);
  const roots = await hostRoots(extraHostPaths);
  const findings = [];
  const tolerated = [];
  let bytes = 0;
  for (const file of files) {
    const name = relative(root, file).split(sep).join("/");
    const text = (await readFile(file)).toString("latin1");
    bytes += text.length;
    const matches = [];
    for (const { rule, pattern } of binaryExtensions.has(extname(name).toLowerCase()) ? rules : [...rules, ...textRules]) {
      for (const match of text.matchAll(pattern)) matches.push({ rule, index: match.index, match: match[0] });
    }
    for (const host of roots) {
      for (let index = text.indexOf(host); index !== -1; index = text.indexOf(host, index + host.length)) {
        matches.push({ rule: "chemin-du-poste", index, match: host });
      }
    }
    // Une même fuite déclenche souvent plusieurs règles (URL file:// d'un chemin du poste) : un constat par emplacement.
    const located = [];
    for (const { rule, index, match } of matches.sort((left, right) => left.index - right.index || right.match.length - left.match.length)) {
      const previous = located.at(-1);
      if (previous && index < previous.offset + previous.match.length) {
        if (!previous.rules.includes(rule)) previous.rules.push(rule);
        if (index + match.length > previous.offset + previous.match.length) previous.match = text.slice(previous.offset, index + match.length);
      } else located.push({ file: name, offset: index, rules: [rule], match });
    }
    for (const record of located) {
      const exception = allowed.find(entry => entry.files.includes(name) && record.match === entry.text
        && text.slice(record.offset - entry.before.length, record.offset) === entry.before && text.startsWith(entry.after, record.offset + record.match.length));
      const detailed = { ...record, excerpt: excerpt(text, record.offset, record.match.length) };
      if (exception) tolerated.push({ ...detailed, reason: exception.reason });
      else findings.push(detailed);
    }
  }
  return { directory: root, files: files.length, bytes, hostRoots: roots, findings, tolerated };
}

async function main() {
  let options;
  try { options = parseArguments(process.argv.slice(2)); } catch (error) {
    console.error(error.message);
    return 2;
  }
  let result;
  try { result = await scanExport(options.directory, options.hostPaths); } catch (error) {
    console.error(`Contrôle impossible : ${error.code === "ENOENT" ? `${resolve(options.directory)} est introuvable (lancez d'abord le build).` : error.message}`);
    return 2;
  }
  if (options.json) console.log(JSON.stringify(result, null, 2));
  else {
    for (const finding of result.findings) console.log(`${finding.file}:${finding.offset} [${finding.rules.join(", ")}] ${finding.match}\n  … ${finding.excerpt} …`);
    for (const entry of result.tolerated) console.log(`Admis : ${entry.file}:${entry.offset} ${entry.match} (${entry.reason})`);
    console.log(result.findings.length
      ? `${result.findings.length} chemin(s) absolu(s) du poste dans l'export ${result.directory} (${result.files} fichiers contrôlés).`
      : `Aucun chemin absolu du poste dans l'export ${result.directory} : ${result.files} fichiers contrôlés, ${result.tolerated.length} constante(s) amont admise(s).`);
  }
  return result.findings.length ? 1 : 0;
}

// Lancé directement, y compris par un lien symbolique : les deux chemins sont comparés une fois résolus.
// Toute autre forme d'appel (import, chemin non résolu) échoue bruyamment au lieu de rendre 0 sans contrôle.
function invokedDirectly() {
  try { return Boolean(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)); } catch { return false; }
}
if (invokedDirectly()) process.exitCode = await main();
else {
  console.error("check-export-paths.mjs s'exécute en ligne de commande (node scripts/check-export-paths.mjs <export>) : appel non reconnu, aucun contrôle effectué.");
  process.exitCode = 2;
}
