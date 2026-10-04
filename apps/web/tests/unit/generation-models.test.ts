import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { generationModelView, readGeneration } from "../../src/lib/generation.ts";

test("startup model is read from the authenticated jobs payload, never defaulted by the UI", () => {
  assert.equal(generationModelView(readGeneration({ device: "cpu", fallback: false, processor: null })), null);
  for (const model of ["qwen3.5:2b", "qwen3.5:4b-text"]) {
    const state = readGeneration({ device: "cpu", fallback: false, processor: null, model });
    assert.equal(state?.model, model);
    const view = generationModelView(state);
    assert.ok(view?.detail.includes(model));
    assert.match(view!.detail, /arrêtez le poste/);
    assert.match(view!.detail, /sans changer ses chemins de données/);
    assert.match(view!.detail, /redémarrez avec ce même profil/);
    assert.match(view!.detail, /questions utilisent le modèle de cette instance/);
  }
});

test("malformed informational model names are ignored without hiding valid hardware", () => {
  for (const model of [false, 2, null, "", "secret value", "a".repeat(400), "tag\nvalue", { name: "qwen3.5:2b" }]) {
    const state = readGeneration({ device: "cpu", fallback: false, processor: null, model });
    assert.deepEqual(state, { device: "cpu", fallback: false, processor: null });
    assert.equal(generationModelView(state), null);
  }
  assert.equal(readGeneration({ device: "gpu", fallback: true, model: "qwen3.5:2b" }), null);
  assert.equal(generationModelView(null), null);
});

test("implicit latest and registry ports preserve model and hardware compatibility", () => {
  assert.deepEqual(readGeneration({ device: "cpu", fallback: false, processor: null, model: "mymodel" }),
    { device: "cpu", fallback: false, processor: null, model: "mymodel" });
  for (const model of ["mymodel", "namespace/model", "localhost:5000/team/model:tag", "registry.example:11434/model", "qwen3.5:2b"]) {
    const state = readGeneration({ device: "gpu", fallback: false, processor: "100% GPU", model });
    assert.deepEqual(state, { device: "gpu", fallback: false, processor: "100% GPU", model });
    assert.ok(generationModelView(state)?.detail.includes(model));
  }
  const state = readGeneration({ device: "cpu", fallback: true, processor: "100% CPU", model: false });
  assert.deepEqual(state, { device: "cpu", fallback: true, processor: "100% CPU" });
  assert.equal(readGeneration({ device: "gpu", fallback: true, model: "mymodel" }), null);
});

test("the actual indicator keeps the jobs origin and accessible restart explanation", () => {
  const band = readFileSync(new URL("../../src/components/context-band.tsx", import.meta.url), "utf8");
  const workspace = readFileSync(new URL("../../src/components/workspace.tsx", import.meta.url), "utf8");
  assert.match(band, /const model = generationModelView\(generation\)/);
  assert.match(band, /\{model && <Badge tone="neutral">\{model.label\}<\/Badge>\}/);
  assert.match(band, /\{model && <>\{model.detail\} <\/>\}/);
  assert.match(workspace, /generation=\{jobs.isError \? null : readGeneration\(jobs.data\?\.generation\)\}/);
  assert.doesNotMatch(band, /api\.diagnostics|api\.query|qwen3\.5:2b/);
});
