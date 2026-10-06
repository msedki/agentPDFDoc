import { existsSync, readFileSync, realpathSync } from "node:fs";
import { basename, isAbsolute, relative, resolve } from "node:path";
import { expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { fixture, sha256, uploadFromUi, waitJob } from "./lifecycle-target";
import { e2eTarget } from "./target.ts";

export const apiOrigin = e2eTarget().baseURL;
const projectRoot = resolve(process.cwd(), "../..");
const fixturesRoot = resolve(projectRoot, "fixtures");
const loopback = ["127.0.0.1", "localhost", "[::1]"];
export type PageLog = { external: string[]; mutations: string[]; pageErrors: string[]; requests: { method: string; path: string }[] };

/** Journal propre à la page : requêtes non-loopback, mutations et erreurs JS restent observables. */
export function watchPage(page: Page): PageLog {
  const log: PageLog = { external: [], mutations: [], pageErrors: [], requests: [] };
  page.on("request", request => {
    const url = new URL(request.url());
    if (!["blob:", "data:"].includes(url.protocol) && !loopback.includes(url.hostname)) log.external.push(request.url());
    if (!["GET", "HEAD"].includes(request.method())) log.mutations.push(`${request.method()} ${url.pathname}`);
    log.requests.push({ method: request.method(), path: url.pathname + url.search });
  });
  page.on("pageerror", error => log.pageErrors.push(error.message));
  return log;
}

/** Scénario GET seul : toute requête API d'écriture est bloquée dans le navigateur et ne parvient jamais au service. */
export async function readOnlyApi(page: Page, blocked: string[]) {
  await page.route("**/api/v1/**", route => {
    const request = route.request();
    if (["GET", "HEAD"].includes(request.method())) return route.continue();
    blocked.push(`${request.method()} ${new URL(request.url()).pathname}`);
    return route.abort("blockedbyclient");
  });
}

export type ControlledFixture = ReturnType<typeof fixture> & { origin: "manifest" | "sidecar"; expected_pages?: number; expected_native_strings?: string[] };

/** Fixture contrôlée par chemin : entrée du manifeste, sinon sidecar généré hors manifeste ; SHA et taille vérifiés, null si absente. */
export function fixtureAtPath(path: string): ControlledFixture | null {
  const manifest = JSON.parse(readFileSync(resolve(projectRoot, "evals/qualification-v2.1/manifest.json"), "utf8"));
  const entry = (manifest.entries as { key: string; path: string; expected_pages?: number }[]).find(item => item.path === path);
  if (entry) return { ...fixture(entry.key), origin: "manifest", expected_pages: entry.expected_pages };
  const sidecarPath = resolve(fixturesRoot, path.replace(/\.pdf$/, ".sidecar.json"));
  if (!existsSync(sidecarPath)) return null;
  const sidecar = JSON.parse(readFileSync(sidecarPath, "utf8"));
  expect(sidecar.path).toBe(path);
  const absolute = realpathSync(resolve(fixturesRoot, path));
  const inside = relative(fixturesRoot, absolute);
  if (isAbsolute(inside) || inside.startsWith("..")) throw new Error("Fixture path escaped the controlled source root.");
  const bytes = readFileSync(absolute);
  expect(sha256(bytes)).toBe(sidecar.sha256);
  expect(bytes.length).toBe(sidecar.bytes);
  return { key: String(sidecar.key), path, sha256: String(sidecar.sha256), bytes, absolute_path: absolute, name: basename(absolute), origin: "sidecar", expected_pages: Number(sidecar.pages), expected_native_strings: sidecar.expected_native_strings };
}

/** Import réel par l'UI puis attente du job exact ; aucune reprise ni réimport automatique. */
export async function importPublished(page: Page, request: APIRequestContext, input: ReturnType<typeof fixture>, info: TestInfo, accepted = ["ready"]) {
  await page.goto("/workspace/");
  const received = await uploadFromUi(page, input, info);
  expect(received.status).toBe(202);
  const job = await waitJob(request, apiOrigin, received.body.job_id, info);
  expect(accepted, `État réel du job ${received.body.job_id}`).toContain(String(job.state));
  return { documentId: String(received.body.document_id), versionId: String(received.body.version_id), job };
}

export async function pageBlocks(request: APIRequestContext, versionId: string, pageIndex: number) {
  const response = await request.get(`${apiOrigin}/api/v1/versions/${encodeURIComponent(versionId)}/pages/${pageIndex}/blocks`);
  expect(response.status()).toBe(200);
  return response.json();
}
