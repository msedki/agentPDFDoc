import { test } from "node:test";
import assert from "node:assert/strict";
import { jobGroup, jobsSummary, latestJobIds, showsProgress, sortJobsForAttention } from "../../src/lib/jobs-view.ts";

test("les traitements qui attendent une décision passent avant les échecs, l'activité, les pauses et les terminés", () => {
  const jobs = [
    { id: "done", state: "ready" }, { id: "paused", state: "paused" }, { id: "partial", state: "ready_partial" },
    { id: "failed", state: "error" }, { id: "running", state: "extracting" }, { id: "published", state: "ready_partial" }, { id: "stopped", state: "cancelled" },
  ];
  const sorted = sortJobsForAttention(jobs, job => job.id === "published");
  assert.deepEqual(sorted.map(job => job.id), ["partial", "failed", "running", "paused", "stopped", "done", "published"]);
});

test("le tri est stable dans un groupe : l'ordre de l'API est conservé", () => {
  const jobs = [{ id: "a", state: "paused" }, { id: "b", state: "paused" }, { id: "c", state: "paused" }];
  assert.deepEqual(sortJobsForAttention(jobs, () => false).map(job => job.id), ["a", "b", "c"]);
});

test("l'avancement ne s'affiche que pendant un calcul, jamais pour une pause ou une attente", () => {
  assert.equal(showsProgress({ state: "extracting", progress: 0.05 }), true);
  assert.equal(showsProgress({ state: "paused", progress: 0 }), false);
  assert.equal(showsProgress({ state: "queued", progress: 0 }), false);
  assert.equal(showsProgress({ state: "ready", progress: 1 }), false);
  assert.equal(showsProgress({ state: "indexing" }), false);
});

test("le résumé accorde chaque groupe et suit l'ordre d'attention", () => {
  const groups = [jobGroup({ state: "paused" }, false), jobGroup({ state: "paused" }, false), jobGroup({ state: "ready_partial" }, false), jobGroup({ state: "ready" }, true)];
  assert.equal(jobsSummary(groups), "1 extraction partielle à publier · 2 en pause · 1 terminé");
  assert.equal(jobsSummary([jobGroup({ state: "ready_partial" }, false), jobGroup({ state: "ready_partial" }, false)]), "2 extractions partielles à publier");
  assert.equal(jobsSummary([]), "");
});

test("un traitement remplacé par une indexation plus récente du même document n'appelle plus de décision", () => {
  const jobs = [
    { id: "nouveau", document_id: "doc", state: "ready" },
    { id: "ancien", document_id: "doc", state: "ready_partial" },
    { id: "autre", document_id: "doc-2", state: "ready_partial" },
  ];
  assert.deepEqual([...latestJobIds(jobs)], ["nouveau", "autre"]);
  assert.deepEqual(sortJobsForAttention(jobs, job => job.id === "nouveau").map(job => job.id), ["autre", "nouveau", "ancien"]);
  assert.equal(jobGroup(jobs[1], false, true), "done");
  assert.equal(jobGroup({ state: "paused" }, false, true), "paused");
});
