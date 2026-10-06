import { defineConfig } from "@playwright/test";
import { storageStatePath } from "./tests/e2e/storage-state.ts";
import { e2eTarget } from "./tests/e2e/target.ts";
const outputDir = process.env.RAG_E2E_OUTPUT_DIR ?? "test-results/default";
// Instance de recette obligatoire (R26) : aucune cible par défaut, instance principale refusée sauf autorisation explicite.
const target = e2eTarget();
export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: "./tests/global-setup.ts",
  timeout: 240000,
  expect: { timeout: 30000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  outputDir,
  reporter: [["list"], ["json", { outputFile: `${outputDir}/results.json` }]],
  use: {
    baseURL: target.baseURL,
    browserName: "chromium",
    viewport: { width: 1366, height: 768 },
    // Session ouverte par globalSetup (W011) ; les specs qui testent l'absence de session la vident explicitement.
    storageState: storageStatePath(),
    headless: true,
    trace: "on",
    screenshot: "only-on-failure",
    video: "off",
  },
});
