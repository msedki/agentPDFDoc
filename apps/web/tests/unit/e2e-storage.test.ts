import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { storageStatePath } from "../e2e/storage-state.ts";

test("session E2E : emplacement historique conservé sans option", () => {
  assert.equal(storageStatePath({}, "/atelier/apps/web"), resolve("/atelier/apps/web", "playwright/.auth/state.json"));
});

test("session E2E : chemin absolu de recette conservé, espaces compris", () => {
  const selected = resolve("/qa/recette PDF/session.json");
  assert.equal(storageStatePath({ RAG_E2E_STORAGE_STATE: selected }, "/atelier/apps/web"), selected);
});

test("session E2E : chemin relatif résolu depuis le répertoire de la recette", () => {
  assert.equal(storageStatePath({ RAG_E2E_STORAGE_STATE: "qa/session.json" }, "/atelier/apps/web"), resolve("/atelier/apps/web", "qa/session.json"));
});

test("session E2E : chemin explicite vide refusé avant ouverture", () => {
  for (const selected of ["", " ", "\t\n"]) assert.throws(() => storageStatePath({ RAG_E2E_STORAGE_STATE: selected }), /chemin vide/);
});

test("session E2E : préparation et configuration utilisent le même résolveur", () => {
  const setup = readFileSync(new URL("../global-setup.ts", import.meta.url), "utf8");
  const config = readFileSync(new URL("../../playwright.config.ts", import.meta.url), "utf8");
  assert.match(setup, /export const STORAGE_STATE = storageStatePath\(\)/);
  assert.match(setup, /writeStorageStatePrivate\(STORAGE_STATE, await context.storageState\(\)\)/);
  assert.doesNotMatch(setup, /storageState\(\{\s*path:/);
  assert.match(setup, /finally\s*\{\s*await context.dispose\(\)/);
  assert.match(config, /storageState: storageStatePath\(\)/);
});
