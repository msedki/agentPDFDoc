/**
 * Matériel de la génération des réponses affiché par l'atelier (W025, P7) : lecture du champ `generation`
 * de `GET /api/v1/jobs` et textes du bandeau de contexte. Cas couverts : processeur, repli sur le
 * processeur après un échec du GPU, mode GPU selon la dernière occupation observée du modèle (entièrement
 * sur le GPU, en partie ou entièrement sur le processeur, inconnue, pas encore observée), champ absent
 * (API antérieure, double de la passerelle) ou mal formé.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { generationView, readGeneration, readPlacement } from "../../src/lib/generation.ts";
import { launcherCommandsFrom } from "../../src/lib/launcher.ts";
import type { Generation, JobsResponse } from "../../src/lib/types.ts";

const linux = launcherCommandsFrom({ commands: { open: "./rag.sh open", status: "./rag.sh status", logs: "./rag.sh logs", doctor: "./rag.sh doctor" } });
const windows = launcherCommandsFrom({ commands: { open: ".\\rag.ps1 open", status: ".\\rag.ps1 status", logs: ".\\rag.ps1 logs", doctor: ".\\rag.ps1 doctor" } });
const gpu = (processor: string | null): Generation => ({ device: "gpu", fallback: false, processor });

test("the generation field of /jobs is read as published by the API", () => {
  assert.deepEqual(readGeneration({ device: "gpu", fallback: false, processor: "100% GPU" }), gpu("100% GPU"));
  assert.deepEqual(readGeneration({ device: "gpu", fallback: false, processor: null }), gpu(null));
  assert.deepEqual(readGeneration({ device: "cpu", fallback: false, processor: "100% CPU" }), { device: "cpu", fallback: false, processor: "100% CPU" });
  assert.deepEqual(readGeneration({ device: "cpu", fallback: true, processor: null }), { device: "cpu", fallback: true, processor: null });
  // Sans `processor`, aucune occupation n'est connue ; un champ ajouté plus tard par l'API ne change pas la lecture.
  assert.deepEqual(readGeneration({ device: "gpu", fallback: false }), gpu(null));
  assert.deepEqual(readGeneration({ device: "gpu", fallback: false, processor: "100% GPU", since: "2026-10-01" }), gpu("100% GPU"));
});

test("an absent, null or malformed field shows nothing rather than a guessed device", () => {
  // Réponse d'une API antérieure à W025 : aucun champ `generation`.
  const before: JobsResponse = { jobs: [], total: 0, runtime_mode: null };
  assert.equal(readGeneration(before.generation), null);
  // `null` : API lancée avec un double de la passerelle Ollama (contrat jobs_response.generation).
  for (const value of [undefined, null, {}, [], "gpu", 1, { device: "gpu" }, { fallback: false }, { device: "GPU", fallback: false },
    { device: "rocm", fallback: false }, { device: "cpu", fallback: "false" }, { device: "cpu", fallback: 0 }, { device: null, fallback: false },
    { device: "gpu", fallback: false, processor: 100 }, { device: "gpu", fallback: false, processor: { gpu: 100 } }, { device: "gpu", fallback: false, processor: "" }]) {
    assert.equal(readGeneration(value), null, JSON.stringify(value));
  }
  // Après un repli, l'API publie toujours `cpu` : un repli annoncé sur le GPU est incohérent.
  assert.equal(readGeneration({ device: "gpu", fallback: true, processor: null }), null);
  assert.equal(generationView(null, linux), null);
});

test("the observed placement follows the PROCESSOR column of ollama ps", () => {
  assert.equal(readPlacement(null), null);
  assert.deepEqual(readPlacement("100% GPU"), { kind: "gpu" });
  assert.deepEqual(readPlacement("100% CPU"), { kind: "cpu" });
  assert.deepEqual(readPlacement("25%/75% CPU/GPU"), { kind: "partial", cpu: 25, gpu: 75 });
  assert.deepEqual(readPlacement("1%/99% CPU/GPU"), { kind: "partial", cpu: 1, gpu: 99 });
  // Forme rapportée par Ollama quand size_vram dépasse size, ou forme inconnue de cette version : répartition inconnue.
  for (const value of ["Unknown", "100% Vulkan", "25%/80% CPU/GPU", "abc%/def% CPU/GPU", " 100% GPU"]) assert.deepEqual(readPlacement(value), { kind: "unknown" }, value);
});

test("GPU fully loaded on the GPU: the only state labelled as answers computed on the GPU", () => {
  const view = generationView(gpu("100% GPU"), linux);
  assert.ok(view);
  assert.deepEqual(view.status, { label: "Réponses calculées sur le GPU", tone: "neutral", code: "gpu", known: true });
  assert.equal(view.notice, null);
  assert.equal(view.detail, "Le modèle de réponse était chargé entièrement sur le GPU de ce poste lors de la dernière vérification, faite avant chaque question et après chaque réponse. La recherche et l'import des documents restent calculés sur le processeur. La commande ./rag.sh doctor détaille le GPU dans sa rubrique « calcul ».");
  for (const processor of [null, "Unknown", "25%/75% CPU/GPU", "100% CPU"]) {
    assert.notEqual(generationView(gpu(processor), linux)!.status.label, view.status.label, String(processor));
  }
  assert.notEqual(generationView({ device: "cpu", fallback: false, processor: "100% GPU" }, linux)!.status.label, view.status.label);
});

test("GPU retained but the model not seen loaded yet: a distinct neutral label that claims no computation", () => {
  const view = generationView(gpu(null), linux);
  assert.ok(view);
  assert.deepEqual(view.status, { label: "Génération prévue sur le GPU", tone: "neutral", code: "gpu_pending", known: true });
  assert.equal(view.notice, null);
  assert.equal(view.detail, "Le service a retenu le GPU de ce poste pour le modèle de réponse, qui n'a pas encore été vu chargé ; sa répartition entre GPU et processeur est relevée à chaque question. La recherche et l'import des documents restent calculés sur le processeur.");
  const unknown = generationView(gpu("Unknown"), windows);
  assert.ok(unknown);
  assert.deepEqual(unknown.status, { label: "Génération prévue sur le GPU", tone: "neutral", code: "gpu_unknown", known: true });
  assert.equal(unknown.detail, "Le service a retenu le GPU de ce poste pour le modèle de réponse, mais la répartition du modèle entre GPU et processeur n'a pas pu être déterminée lors de la dernière vérification. La commande .\\rag.ps1 doctor donne l'état du GPU dans sa rubrique « calcul ».");
});

test("GPU mode with the model partly on the processor: a warning label and the split, with doctor", () => {
  const view = generationView(gpu("25%/75% CPU/GPU"), linux);
  assert.ok(view);
  assert.deepEqual(view.status, { label: "Réponses calculées en partie sur le processeur", tone: "warning", code: "gpu_partial", known: true });
  assert.equal(view.notice, null);
  assert.equal(view.detail, "Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé à 75 % sur le GPU et à 25 % sur le processeur, selon la mémoire GPU libre à son chargement. La commande ./rag.sh doctor détaille cette répartition dans sa rubrique « calcul ».");
});

test("GPU mode with the model entirely on the processor: a warning label and the doctor command for what to do", () => {
  const view = generationView(gpu("100% CPU"), windows);
  assert.ok(view);
  assert.deepEqual(view.status, { label: "GPU retenu, réponses calculées sur le processeur", tone: "warning", code: "gpu_on_cpu", known: true });
  assert.equal(view.notice, null);
  assert.equal(view.detail, "Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé entièrement sur le processeur. La commande .\\rag.ps1 doctor en donne la marche à suivre dans sa rubrique « calcul ».");
});

test("processor: a neutral indicator, no notice, and the doctor command of the host for the reason", () => {
  for (const processor of [null, "100% CPU", "Unknown"]) {
    const view = generationView({ device: "cpu", fallback: false, processor }, windows);
    assert.ok(view);
    assert.deepEqual(view.status, { label: "Réponses calculées sur le processeur", tone: "neutral", code: "cpu", known: true });
    assert.equal(view.notice, null);
    assert.equal(view.detail, "Le modèle de réponse est exécuté sur le processeur de ce poste ; la commande .\\rag.ps1 doctor en donne la raison dans sa rubrique « calcul ».");
  }
});

test("fallback: a warning indicator and a notice saying the GPU failed, the processor answers until restart, with doctor", () => {
  const view = generationView({ device: "cpu", fallback: true, processor: null }, linux);
  assert.ok(view);
  assert.deepEqual(view.status, { label: "GPU en échec : réponses calculées sur le processeur", tone: "warning", code: "cpu_fallback", known: true });
  const expected = "Le chargement du modèle de réponse sur le GPU a échoué : l'atelier répond sur le processeur jusqu'à son prochain redémarrage. La commande ./rag.sh doctor en donne la cause et la marche à suivre pour réessayer le GPU.";
  assert.equal(view.notice, expected);
  assert.equal(view.detail, expected, "l'explication reste ouverte au clavier quand un autre message occupe le bandeau");
  // Sans le bandeau, l'indicateur seul distingue le repli du calcul ordinaire sur le processeur.
  assert.notEqual(view.status.label, generationView({ device: "cpu", fallback: false, processor: null }, linux)!.status.label);
});

test("without announced commands, the doctor command is given in both delivered forms", () => {
  for (const generation of [{ device: "cpu", fallback: true, processor: null }, gpu("100% CPU"), gpu("25%/75% CPU/GPU")] as const) {
    const text = generationView(generation, null)!.detail;
    assert.ok(text.includes(".\\rag.ps1 doctor sous Windows ou ./rag.sh doctor sous Linux"), text);
  }
});

test("the texts carry no raw code, no engine name, no hardware detail and no nested parentheses", () => {
  const generations: Generation[] = [gpu("100% GPU"), gpu(null), gpu("Unknown"), gpu("25%/75% CPU/GPU"), gpu("100% CPU"),
    { device: "cpu", fallback: false, processor: null }, { device: "cpu", fallback: true, processor: null }];
  for (const generation of generations) {
    for (const commands of [linux, null]) {
      const view = generationView(generation, commands)!;
      for (const text of [view.status.label, view.detail, view.notice ?? ""]) {
        assert.doesNotMatch(text, /cpu_fallback|gpu_|_mode|Ollama|CUDA|Jetson|Orin|NVIDIA|num_gpu|processor|PROCESSOR|\bW0\d\d\b|Unknown/, text);
        assert.doesNotMatch(text, /\([^()]*\(/, text);
      }
    }
  }
});
