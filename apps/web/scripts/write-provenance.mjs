/**
 * Preuve de provenance de l'export (KIT4-26) : écrit `<dossier>/build-provenance.json` après le build, pour que le
 * fabricant du kit Linux (tools/dist/linux_kit.py, check_web_provenance) vérifie que l'interface livrée a été
 * construite depuis le commit du kit, sans source modifiée.
 *
 * Usage : node scripts/write-provenance.mjs [dossier]
 *   dossier   export à compléter, `out` par défaut (relatif au dossier courant).
 * Code de sortie : 0 preuve écrite, 2 si le dossier d'export est absent.
 *
 * Contenu (format atelier-web-provenance-v1) :
 *   commit             commit Git courant (40 caractères hexadécimaux) ;
 *   sources_modified   vrai si une entrée de BUILD_INPUTS diffère du commit (modifiée, ajoutée hors .gitignore,
 *                      supprimée ou renommée) ;
 *   modified_sources   ces entrées, en chemins relatifs à apps/web ;
 *   pnpm_lock_sha256   empreinte SHA-256 de pnpm-lock.yaml lu sur le disque ;
 *   built_utc          date d'écriture de la preuve.
 * Sans Git ou hors d'un dépôt, `commit` et `sources_modified` valent null : le build n'échoue pas (poste sans Git),
 * mais le fabricant Linux refuse alors l'export avec la cause nommée. Aucun chemin absolu du poste n'est écrit.
 *
 * Les entrées de BUILD_INPUTS sont celles que lit `pnpm build` : sources, actifs publics, scripts, manifestes et
 * configurations. README.md, reports/, tests/ et playwright.config.ts n'entrent pas dans l'export.
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const PROVENANCE_FORMAT = "atelier-web-provenance-v1";
export const PROVENANCE_FILE = "build-provenance.json";
export const BUILD_INPUTS = [
  "src", "public", "scripts", "package.json", "pnpm-lock.yaml", "next.config.mjs", "tsconfig.json", "postcss.config.mjs",
  "components.json", "next-env.d.ts",
];

const webRoot = fileURLToPath(new URL("../", import.meta.url));

/**
 * Chemins d'une sortie `git status --porcelain=v1 -z` : « XY chemin », suivi, pour un renommage ou une copie (R, C),
 * du chemin d'origine dans l'enregistrement suivant. Les deux chemins sont retenus.
 */
export function porcelainPaths(output) {
  const records = output.split("\0").filter((record) => record.length > 0);
  const paths = [];
  for (let index = 0; index < records.length; index += 1) {
    const record = records[index];
    if (record.length < 4 || record[2] !== " ") throw new Error(`sortie de git status illisible : ${JSON.stringify(record)}`);
    paths.push(record.slice(3));
    if (record[0] === "R" || record[0] === "C") {
      index += 1;
      if (index >= records.length) throw new Error("sortie de git status illisible : chemin d'origine manquant");
      paths.push(records[index]);
    }
  }
  return paths;
}

/** Préfixe du dossier apps/web dans le dépôt (« apps/web/ ») retiré : chemins relatifs à apps/web, triés, uniques. */
export function webRelative(paths, prefix) {
  return [...new Set(paths.map((path) => (prefix && path.startsWith(prefix) ? path.slice(prefix.length) : path)))].sort();
}

export function provenanceRecord({ commit, modified, lock, builtUtc }) {
  const known = typeof commit === "string" && /^[0-9a-f]{40}$/.test(commit);
  return {
    format: PROVENANCE_FORMAT,
    commit: known ? commit : null,
    sources_modified: known && Array.isArray(modified) ? modified.length > 0 : null,
    modified_sources: known && Array.isArray(modified) ? modified : [],
    pnpm_lock_sha256: lock ? createHash("sha256").update(lock).digest("hex") : null,
    built_utc: builtUtc,
  };
}

function git(args) {
  return execFileSync("git", ["--no-optional-locks", ...args], {
    cwd: webRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], env: { ...process.env, LC_ALL: "C", GIT_TERMINAL_PROMPT: "0" },
  });
}

/** Commit courant et entrées de BUILD_INPUTS qui en diffèrent ; null pour les deux sans Git ou hors d'un dépôt. */
export function gitState() {
  try {
    const commit = git(["rev-parse", "--verify", "HEAD"]).trim();
    const prefix = git(["rev-parse", "--show-prefix"]).trim();
    const status = git(["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ...BUILD_INPUTS]);
    return { commit, modified: webRelative(porcelainPaths(status), prefix) };
  } catch {
    return { commit: null, modified: null };
  }
}

function main(argv) {
  const target = resolve(argv[0] ?? "out");
  if (!existsSync(target) || !statSync(target).isDirectory()) {
    console.error(`Export absent : ${argv[0] ?? "out"} ; lancer d'abord le build (pnpm build). Aucune preuve écrite.`);
    return 2;
  }
  const { commit, modified } = gitState();
  const lockPath = join(webRoot, "pnpm-lock.yaml");
  const lock = existsSync(lockPath) ? readFileSync(lockPath) : null;
  const record = provenanceRecord({ commit, modified, lock, builtUtc: new Date().toISOString() });
  writeFileSync(join(target, PROVENANCE_FILE), `${JSON.stringify(record, null, 2)}\n`, "utf8");
  if (record.commit === null) {
    console.warn(`Provenance écrite sans commit (Git absent ou hors dépôt) : ${PROVENANCE_FILE} ; un kit Linux refusera cet export.`);
  } else if (record.sources_modified) {
    console.warn(`Provenance écrite : commit ${record.commit.slice(0, 12)}, sources modifiées (${record.modified_sources.length}) ; `
      + "un kit Linux refusera cet export tant qu'elles ne sont pas committées.");
  } else {
    console.log(`Provenance écrite : commit ${record.commit.slice(0, 12)}, sources conformes au commit.`);
  }
  return 0;
}

function invokedDirectly() {
  try { return Boolean(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)); } catch { return false; }
}
if (invokedDirectly()) process.exitCode = main(process.argv.slice(2));
