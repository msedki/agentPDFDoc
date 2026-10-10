import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { basename, isAbsolute, relative, resolve } from "node:path";
import { expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { dataDirKey, projectPython, projectRoot } from "./host.ts";
import { e2eTarget } from "./target.ts";

export type LifecycleTarget = {
  schema_version: number; origin: string; data_dir: string; runtime_instance_id: string;
  runtime_profile_file_sha256: string; api_profile_sha256: string; permits: string[];
  document: { id: string; relative_path: string; fixture_key: string; version_id: string; generation_id: string; extraction_revision_id: string; pipeline_fingerprint: string };
  old_version?: { version_id: string; fixture_key: string; expected_text: string };
  old_citation?: { query_id: string; source_id: string; version_id: string; generation_id: string; extraction_revision_id: string; page_index: number; block_hashes: Record<string, string> };
  upload_limit_bytes?: number;
};
type Fixture = { key: string; path: string; sha256: string; bytes: number };
const fixturesRoot = resolve(projectRoot, "fixtures");
export const sha256 = (data: Buffer) => createHash("sha256").update(data).digest("hex");

export function readLifecycleTarget(): LifecycleTarget {
  const path = process.env.RAG_E2E_LIFECYCLE_TARGET;
  if (!path) throw new Error("RAG_E2E_LIFECYCLE_TARGET must name a concrete reviewed binding file; the example is not a target.");
  const target = JSON.parse(readFileSync(resolve(path), "utf8")) as LifecycleTarget;
  if (target.schema_version !== 1 || !Array.isArray(target.permits)) throw new Error("Invalid lifecycle binding schema.");
  return target;
}

export async function guardTarget(request: APIRequestContext, target: LifecycleTarget, info: TestInfo) {
  const origin = new URL(target.origin);
  expect(origin.protocol).toBe("http:");
  expect(["127.0.0.1", "localhost", "[::1]"]).toContain(origin.hostname);
  expect(origin.username + origin.password + origin.search + origin.hash).toBe("");
  expect(origin.pathname).toBe("/");
  expect(target.origin).toBe(e2eTarget().baseURL);
  expect(target.data_dir, "The authorized persistent storage must be explicit").toBeTruthy();
  const dataDir = realpathSync(target.data_dir);
  const runtimeRoot = realpathSync(resolve(projectRoot, ".runtime"));
  const inside = relative(runtimeRoot, dataDir);
  expect(!isAbsolute(inside) && inside !== ".." && !inside.startsWith("..\\") && !inside.startsWith("../")).toBeTruthy();
  const state = JSON.parse(readFileSync(resolve(dataDir, "control/runtime.json"), "utf8"));
  expect(state.status).toBe("running");
  expect(state.instance_id).toBe(target.runtime_instance_id);
  expect(state.app_url).toBe(target.origin);
  expect(dataDirKey(realpathSync(state.data_dir))).toBe(dataDirKey(dataDir));
  expect(target.runtime_profile_file_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(state.profile_sha256).toBe(target.runtime_profile_file_sha256);
  expect(sha256(readFileSync(state.profile_path))).toBe(target.runtime_profile_file_sha256);
  const response = await request.get(`${target.origin}/api/v1/diagnostics`);
  expect(response.status()).toBe(200);
  const diagnostics = await response.json();
  expect(target.api_profile_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(diagnostics.profile_sha256).toBe(target.api_profile_sha256);
  expect(diagnostics.active_queries).toBe(0);
  await info.attach("lifecycle-target-identity", { body: Buffer.from(JSON.stringify({ origin: target.origin, data_dir: dataDir, instance_id: state.instance_id, runtime_profile_file_sha256: state.profile_sha256, api_profile_sha256: diagnostics.profile_sha256, permits: target.permits, telemetry_limit: "embedding_session tracks loads/releases, not embedding calculation count" }, null, 2)), contentType: "application/json" });
}

export function fixture(key: string) {
  const manifest = JSON.parse(readFileSync(resolve(projectRoot, "evals/qualification-v2.1/manifest.json"), "utf8"));
  const entry = (manifest.entries as Fixture[]).find(item => item.key === key);
  if (!entry) throw new Error(`Controlled fixture missing: ${key}`);
  const path = realpathSync(resolve(fixturesRoot, entry.path));
  const inside = relative(fixturesRoot, path);
  if (isAbsolute(inside) || inside.startsWith("..")) throw new Error("Fixture path escaped the controlled source root.");
  const bytes = readFileSync(path);
  expect(sha256(bytes)).toBe(entry.sha256);
  expect(bytes.length).toBe(entry.bytes);
  return { ...entry, absolute_path: path, name: basename(path), bytes };
}

export async function detail(request: APIRequestContext, target: LifecycleTarget) {
  expect(target.document.id).toBeTruthy();
  const response = await request.get(`${target.origin}/api/v1/documents/${encodeURIComponent(target.document.id)}`);
  expect(response.status()).toBe(200);
  const document = await response.json();
  expect(document.relative_path).toBe(target.document.relative_path);
  return document;
}

export function configuredUploadLimit(target: LifecycleTarget) {
  const state = JSON.parse(readFileSync(resolve(target.data_dir, "control/runtime.json"), "utf8"));
  const source = "import json,sys,yaml\nwith open(sys.argv[1],encoding='utf-8-sig') as f: profile=yaml.safe_load(f)\nprint(json.dumps({'bytes':profile.get('pdf',{}).get('max_file_mib',200)*1048576}))";
  const output = execFileSync(projectPython(), ["-c", source, state.profile_path], { encoding: "utf8", timeout: 10000, windowsHide: true });
  return (JSON.parse(output) as { bytes: number }).bytes;
}

export async function uploadFromUi(page: Page, input: ReturnType<typeof fixture>, info: TestInfo) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Importer des documents", exact: true }).click();
  const response = page.waitForResponse(item => item.request().method() === "POST" && item.url().endsWith("/api/v1/documents/import"));
  await (await chooser).setFiles(input.absolute_path);
  const received = await response;
  const body = await received.json();
  await info.attach(`actual-import-${input.key}`, { body: Buffer.from(JSON.stringify({ status: received.status(), fixture_key: input.key, source_sha256: input.sha256, response: body }, null, 2)), contentType: "application/json" });
  return { status: received.status(), body };
}

export async function waitJob(request: APIRequestContext, origin: string, jobId: string, info: TestInfo) {
  const started = Date.now();
  let last: Record<string, unknown> | undefined;
  try {
    while (Date.now() - started < 540000) {
      const response = await request.get(`${origin}/api/v1/jobs`);
      expect(response.status()).toBe(200);
      const jobs = (await response.json()).jobs as Record<string, unknown>[];
      last = jobs.find(job => job.id === jobId);
      if (!last) throw new Error("The exact imported job is missing from the jobs response.");
      if (last.state === "paused") throw new Error(`Actual job paused: ${last.error_code ?? last.stage}; no automatic resume is permitted by this scenario.`);
      if (["ready", "ready_partial", "error", "cancelled"].includes(String(last.state))) return last;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    throw new Error("Actual job exceeded the measured cold recipe deadline; do not reimport or auto-resume it.");
  } finally {
    await info.attach(`actual-job-${jobId}`, { body: Buffer.from(JSON.stringify({ job: last, observed_wait_ms: Date.now() - started, limit: "cold recipe deadline, not a performance objective" }, null, 2)), contentType: "application/json" });
  }
}
