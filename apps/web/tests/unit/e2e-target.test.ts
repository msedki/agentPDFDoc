/**
 * R26-UI-01 : la recette Playwright ne vise jamais l'instance principale par défaut.
 * Avant : playwright.config.ts, global-setup.ts, guards.ts et session.spec.ts prenaient 127.0.0.1:8785 et
 * .runtime/data/control/admin-token sans variable ; globalSetup y ouvrait une session (POST /admin/session-links).
 */
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { e2eTarget, MAIN_INSTANCE_PORT, MAIN_TOKEN_FILE } from "../e2e/target.ts";
import { webRoot } from "./theme-support.ts";

function tokens(body: (paths: { root: string; main: string; isolated: string; alias: string }) => void) {
  const root = mkdtempSync(join(tmpdir(), "r26-e2e-target-"));
  try {
    const main = join(root, "main-admin-token");
    const isolated = join(root, "isolated-admin-token");
    writeFileSync(main, "principal");
    writeFileSync(isolated, "isole");
    const alias = join(root, "alias-admin-token");
    symlinkSync(main, alias);
    body({ root, main, isolated, alias });
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("l'adresse et le jeton de l'instance de recette sont obligatoires", () => {
  tokens(({ root, main, isolated }) => {
    const options = { cwd: root, mainTokenFile: main };
    assert.throws(() => e2eTarget({ RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /RAG_E2E_BASE_URL est obligatoire/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: " ", RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /RAG_E2E_BASE_URL est obligatoire/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785" }, options), /RAG_E2E_CONTROL_TOKEN_FILE est obligatoire/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /n'est pas une adresse http/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: join(root, "absent") }, options), /Jeton de contrôle introuvable/);
  });
});

test("une instance isolée est acceptée, avec le chemin réel de son jeton", () => {
  tokens(({ root, main, isolated }) => {
    const target = e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: "isolated-admin-token" }, { cwd: root, mainTokenFile: main });
    assert.equal(target.baseURL, "http://127.0.0.1:18785");
    assert.equal(target.tokenFile, realpathSync(isolated));
    assert.equal(target.mainInstanceAllowed, false);
  });
});

test("le port de l'instance principale et son jeton, même par un lien, sont refusés sans autorisation explicite", () => {
  tokens(({ root, main, isolated, alias }) => {
    const options = { cwd: root, mainTokenFile: main };
    assert.equal(MAIN_INSTANCE_PORT, 8785);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:8785", RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /port 8785 de l'instance principale/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://localhost:8785/", RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /port 8785/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: alias }, options), /jeton de l'instance principale/);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: main, RAG_E2E_MAIN_INSTANCE_ALLOWED: "true" }, options), /RAG_E2E_MAIN_INSTANCE_ALLOWED=1/, "seule la valeur 1 autorise");
    const allowed = e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:8785", RAG_E2E_CONTROL_TOKEN_FILE: alias, RAG_E2E_MAIN_INSTANCE_ALLOWED: "1" }, options);
    assert.equal(allowed.mainInstanceAllowed, true);
    assert.equal(allowed.tokenFile, realpathSync(main));
  });
});

test("la configuration, la préparation de session et les specs passent toutes par la garde", () => {
  const read = (path: string) => readFileSync(join(webRoot, path), "utf8");
  assert.match(read("playwright.config.ts"), /baseURL: target\.baseURL/);
  assert.match(read("tests/global-setup.ts"), /e2eTarget\(\)\.tokenFile/);
  assert.match(read("tests/e2e/guards.ts"), /export const apiOrigin = e2eTarget\(\)\.baseURL;/);
  assert.match(read("tests/e2e/session.spec.ts"), /const tokenFile = e2eTarget\(\)\.tokenFile;/);
  assert.match(read("tests/e2e/lifecycle-target.ts"), /toBe\(e2eTarget\(\)\.baseURL\)/);
  for (const path of ["playwright.config.ts", "tests/global-setup.ts", "tests/e2e/guards.ts", "tests/e2e/session.spec.ts", "tests/e2e/lifecycle-target.ts"]) {
    assert.doesNotMatch(read(path), /127\.0\.0\.1:8785|control\/admin-token/, `${path} ne porte plus de cible par défaut`);
  }
});

test("seule une adresse de bouclage est admise comme instance de recette", () => {
  tokens(({ root, main, isolated }) => {
    const options = { cwd: root, mainTokenFile: main };
    for (const host of ["http://192.168.1.20:18785", "http://example.org:18785", "http://0.0.0.0:18785"]) {
      assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: host, RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options), /n'est pas une adresse de bouclage/, host);
    }
    for (const host of ["http://127.0.0.1:18785", "http://localhost:18785", "http://[::1]:18785"]) {
      assert.equal(e2eTarget({ RAG_E2E_BASE_URL: host, RAG_E2E_CONTROL_TOKEN_FILE: isolated }, options).baseURL, host);
    }
  });
});

test("une copie du jeton principal est refusée comme le jeton lui-même", () => {
  tokens(({ root, main }) => {
    const copy = join(root, "copie-admin-token");
    writeFileSync(copy, "principal\n");
    const options = { cwd: root, mainTokenFile: main };
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: copy }, options), /même contenu que le jeton de l'instance principale/);
    assert.equal(e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: copy, RAG_E2E_MAIN_INSTANCE_ALLOWED: "1" }, options).mainInstanceAllowed, true);
  });
});

test("le jeton principal par défaut est celui du dépôt, quel que soit le dossier de lancement", () => {
  assert.equal(MAIN_TOKEN_FILE, resolve(webRoot, "../../.runtime/data/control/admin-token"));
  if (!existsSync(MAIN_TOKEN_FILE)) return;
  // Lien vers le jeton réel depuis un autre dossier courant : refusé sans lire ni afficher son contenu.
  tokens(({ root }) => {
    const link = join(root, "lien-jeton-principal");
    symlinkSync(MAIN_TOKEN_FILE, link);
    assert.throws(() => e2eTarget({ RAG_E2E_BASE_URL: "http://127.0.0.1:18785", RAG_E2E_CONTROL_TOKEN_FILE: link }, { cwd: root }), /jeton de l'instance principale/);
  });
});
