import { randomUUID } from "node:crypto";
import fs, { type Stats } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";

/** Même fichier de session pour la préparation et le navigateur, isolable par recette. */
export function storageStatePath(environment: Readonly<Record<string, string | undefined>> = process.env, cwd = process.cwd()): string {
  const selected = environment.RAG_E2E_STORAGE_STATE;
  if (selected !== undefined && !selected.trim()) throw new Error("RAG_E2E_STORAGE_STATE doit désigner un fichier de session, pas un chemin vide.");
  return resolve(cwd, selected ?? "playwright/.auth/state.json");
}

function ownedEntry(path: string, directory = false): Stats | undefined {
  let entry: Stats;
  try {
    entry = fs.lstatSync(path);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
  const wrongOwner = typeof process.getuid === "function" && entry.uid !== process.getuid();
  if (entry.isSymbolicLink() || !(directory ? entry.isDirectory() : entry.isFile()) || wrongOwner) {
    throw new Error("L'état de session exige une cible régulière et un dossier propres au compte, sans lien.");
  }
  if (directory && process.platform !== "win32" && (entry.mode & 0o022) !== 0) {
    throw new Error("Le dossier de session ne doit pas être modifiable par un autre compte.");
  }
  return entry;
}

/** Fichier privé dès création POSIX ; les ACL Windows et les courses d'un même UID restent hors garantie. */
export function writeStorageStatePrivate(selected: string, state: unknown): void {
  const contents = JSON.stringify(state, null, 2);
  if (contents === undefined) throw new Error("L'état de session n'est pas sérialisable.");
  const target = resolve(selected), parent = dirname(target);
  fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
  if (!ownedEntry(parent, true)) throw new Error("Le dossier de session est absent.");
  const previous = ownedEntry(target);
  const temporary = join(parent, `.${basename(target)}.${randomUUID()}.tmp`);
  let descriptor: number | undefined, created = false;
  let identity: Stats | undefined;
  const errors: unknown[] = [];
  try {
    const noFollow = process.platform === "win32" ? 0 : fs.constants.O_NOFOLLOW;
    descriptor = fs.openSync(temporary, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | noFollow, 0o600);
    created = true;
    identity = fs.fstatSync(descriptor);
    // Umask peut retirer des droits, jamais rendre cette création accessible aux autres comptes.
    if (process.platform !== "win32") fs.fchmodSync(descriptor, 0o600);
    fs.writeFileSync(descriptor, contents, "utf8");
    fs.closeSync(descriptor);
    descriptor = undefined;
    const current = ownedEntry(target);
    if (!!previous !== !!current || previous && current && (
      previous.dev !== current.dev || previous.ino !== current.ino || previous.size !== current.size ||
      previous.ctimeMs !== current.ctimeMs || previous.mtimeMs !== current.mtimeMs || previous.birthtimeMs !== current.birthtimeMs
    )) {
      throw new Error("La cible de session a changé pendant l'écriture.");
    }
    fs.renameSync(temporary, target);
    created = false;
  } catch (error) {
    errors.push(error);
  }
  try {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  } catch (error) {
    errors.push(error);
  }
  try {
    if (created) {
      const remaining = ownedEntry(temporary);
      if (remaining && identity && (remaining.dev !== identity.dev || remaining.ino !== identity.ino)) {
        throw new Error("Le temporaire de session a changé ; il est conservé.");
      }
      if (remaining) fs.unlinkSync(temporary);
    }
  } catch (error) {
    errors.push(error);
  }
  if (errors.length === 1) throw errors[0];
  if (errors.length > 1) throw new AggregateError(errors, "Échec de l'écriture de session et de son nettoyage.", { cause: errors[0] });
}
