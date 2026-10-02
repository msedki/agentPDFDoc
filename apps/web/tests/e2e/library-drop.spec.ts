import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

// Constat du 02/10 : sous Chromium installé en snap (Ubuntu 20.04), la boîte de choix de fichiers n'a transmis aucun
// fichier à la page et l'import est resté muet. Le dépôt d'un PDF sur la bibliothèque ne dépend pas de cette boîte.
const fixtureName = "Atelier 6 - Banc pneumatique DA-P06.pdf";
const fixturePath = fileURLToPath(new URL(`../../../../fixtures/qualification-v2.1/development/Procédures/${fixtureName}`, import.meta.url));

test("a PDF dropped on the library is imported, with the usual notice", async ({ page }) => {
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Supervisor must confirm the API targets an authorized isolated store before fixture import.");
  const imports: number[] = [];
  page.on("response", response => { if (new URL(response.url()).pathname === "/api/v1/documents/import") imports.push(response.status()); });
  await page.goto("/workspace/");
  const library = page.locator("aside.library-panel");
  await expect(library.getByRole("heading", { name: "Bibliothèque", exact: true })).toBeVisible();
  const bytes = [...readFileSync(fixturePath)];
  const transfer = await page.evaluateHandle(({ bytes, name }) => {
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array(bytes)], name, { type: "application/pdf" }));
    return data;
  }, { bytes, name: fixtureName });
  await library.dispatchEvent("dragenter", { dataTransfer: transfer });
  await library.dispatchEvent("dragover", { dataTransfer: transfer });
  await expect(page.getByText("Déposez les PDF pour les importer dans la bibliothèque.")).toBeVisible();
  await library.dispatchEvent("drop", { dataTransfer: transfer });
  await expect.poll(() => imports, { timeout: 30000 }).toEqual([202]);
  await expect(library.locator(".library-notice").first()).toContainText("1 PDF reçu par le service");
  await expect(page.getByText("Déposez les PDF pour les importer dans la bibliothèque.")).toBeHidden();
});

test("a file choice that brings no file back says so instead of staying silent", async ({ page }) => {
  test.skip(process.env.RAG_E2E_IMPORT_ALLOWED !== "1", "Supervisor must confirm the API targets an authorized isolated store before fixture import.");
  await page.goto("/workspace/");
  const library = page.locator("aside.library-panel");
  await expect(library.getByRole("heading", { name: "Bibliothèque", exact: true })).toBeVisible();
  // Le navigateur annonce une boîte de choix refermée sans fichier par l'événement « cancel » de l'élément de saisie.
  await library.locator('input[type="file"][accept]').dispatchEvent("cancel");
  await expect(library.locator(".library-notice").first()).toContainText("Aucun fichier n'a été transmis par la boîte de choix");
});
