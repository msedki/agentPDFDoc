import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import { defineConfig, globalIgnores } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores([
    ".next/**", "out/**", "public/pdfjs/**", "next-env.d.ts",
    "test-results/**", "playwright/.auth/**",
  ]),
  {
    files: ["**/*.{js,mjs,cjs,jsx,ts,tsx}"],
    extends: [js.configs.recommended],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
      reportUnusedInlineConfigs: "error",
    },
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [tseslint.configs.recommended],
  },
  {
    files: ["src/**/*.{js,jsx,ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "@next/next": nextPlugin, "react-hooks": reactHooks },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      ...reactHooks.configs.recommended.rules,
    },
  },
  {
    files: ["scripts/**", "*.mjs", "*.ts", "tests/**"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["tests/e2e/**"],
    languageOptions: { globals: globals.browser },
  },
]);
