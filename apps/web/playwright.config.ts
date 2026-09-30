import { defineConfig } from "@playwright/test";
const outputDir = process.env.RAG_E2E_OUTPUT_DIR ?? "test-results/default";
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
    baseURL: process.env.RAG_E2E_BASE_URL ?? "http://127.0.0.1:8785",
    browserName: "chromium",
    viewport: { width: 1366, height: 768 },
    // Session ouverte par globalSetup (W011) ; les specs qui testent l'absence de session la vident explicitement.
    storageState: "playwright/.auth/state.json",
    headless: true,
    trace: "on",
    screenshot: "only-on-failure",
    video: "off",
  },
});
