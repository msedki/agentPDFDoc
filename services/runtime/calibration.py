"""Pilote isolé et surveillé, sur CPU (défaut) ou sur GPU ; ne modifie aucun seuil automatiquement.

Le pilote GPU (`--accelerator auto`) mesure ce poste seulement : il n'est jamais une mesure de la recette D07, qui se fait
en calcul CPU imposé. En `cpu`, les requêtes sont celles d'avant l'accélération GPU, octet pour octet.
"""

from __future__ import annotations

import concurrent.futures
import json
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psutil

from .accelerator import (
    host_signals,
    processor_label,
    read_discovery,
    reason_text,
    resolve_mode,
)
from .artifacts import ROOT, file_hash, runtime_location, write_json_atomic
from .resources import acquire_host_heavy_lock, linux_memory_mib
from .supervisor import (
    ProcessJob,
    environment,
    gpu_libraries,
    load_profile,
    native_paths,
    ollama_working_directory,
    send_owned_console_interrupt,
    wait_http,
)

ACCELERATORS = ("cpu", "auto")
SCOPES = {"cpu": "Early QCPU controlled pilot; not the final performance qualification",
          "auto": "Early GPU pilot on this host; never a D07 measurement"}


def chat_body(profile: dict, messages: list[dict], *, output_limit: int, threads: int, use_mmap: bool | None,
              accelerator: str) -> dict:
    """Corps /api/chat d'un essai : `num_gpu: 0` en `cpu` (clés et ordre d'avant W024), option omise en `auto`."""
    options: dict = {"num_ctx": profile["llm"]["num_ctx"], "num_predict": output_limit}
    if accelerator == "cpu":
        options["num_gpu"] = 0
    options.update({"num_thread": threads, "temperature": profile["llm"]["temperature"], "top_p": profile["llm"]["top_p"]})
    body = {"model": profile["llm"]["model"], "messages": messages, "think": False, "stream": True,
            "keep_alive": profile["llm"].get("keep_alive", "10m"), "options": options}
    if use_mmap is not None:
        # Ollama 0.35.0 respecte un use_mmap explicite (server/sched.go, disableMmapDefaultReason).
        body["options"]["use_mmap"] = use_mmap
    return body


def check_residency(resident: list[dict], accelerator: str) -> None:
    """Pilote CPU : aucun octet sur le GPU ; pilote GPU : modèle chargé au moins en partie sur le GPU."""
    if accelerator == "cpu":
        if any(item.get("size_vram") != 0 for item in resident):
            raise RuntimeError("Le modèle pilote a utilisé le GPU")
    elif not any(item.get("size_vram") for item in resident):
        raise RuntimeError("Le modèle pilote n'a pas été chargé sur le GPU")


def gpu_decision(log_path: Path) -> dict:
    """Découverte du service pilote et décision d'un essai GPU, avec les contrôles de l'instance (W025) : découverte
    lue, CUDA seul retenu, bibliothèques vérifiées. La qualification de la voie n'est pas exigée : elle est consignée."""
    signals = host_signals()
    discovery = read_discovery(log_path)
    decision = resolve_mode({"requested": "gpu", "requested_source": "calibration"}, discovery, gpu_libraries(signals),
                            signals.get("platform"))
    return {"requested": "auto", "discovery": discovery, "decision": decision, "host": signals, "log": str(log_path)}


def gpu_refusal(accelerator: dict) -> str | None:
    reason = accelerator["decision"]["reason"]
    if accelerator["decision"]["mode"] == "gpu":
        return None
    if reason == "no_gpu_discovered":
        return f"Pilote GPU refusé : Ollama n'a découvert aucun GPU utilisable ; journal {accelerator['log']}."
    return f"Pilote GPU refusé : {reason_text(accelerator['decision'])} ; journal {accelerator['log']}."


def swap_free_mib() -> float:
    """SwapFree (fichier d'échange sous Windows) : sur un Jetson, une allocation du GPU puise dans la même DRAM et peut
    repousser des pages vers le swap sans que MemAvailable le montre (W025, revue M1)."""
    return psutil.swap_memory().free / 1048576


def calibrate(profile_path: Path, output: Path, *, input_target: int = 2950,
              output_limit: int = 64, threads: int = 4, read_timeout: int = 600,
              use_mmap: bool | None = None, accelerator: str = "cpu") -> dict:
    from services.api.context import LlmTokenizer
    from services.api.settings import Settings

    if accelerator not in ACCELERATORS:
        raise ValueError(f"Accélération du pilote inconnue : {accelerator} (cpu ou auto)")
    if output.exists():
        raise FileExistsError(f"Rapport pilote déjà présent, aucune réécriture : {output}")
    profile = load_profile(profile_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 11444))
    settings = Settings.load(profile_path)
    tokenizer = LlmTokenizer(settings)
    system = {"role": "system", "content": "Tu réponds en français, sans raisonnement caché. Ce texte est synthétique."}

    def synthetic(component: str, volts: int, celsius: int) -> list[dict]:
        # Même gabarit, valeurs distinctes : le contenu neuf ne réutilise que le préfixe système.
        messages = [system, {"role": "user", "content": "Voici un corpus synthétique. " +
                             f"Le composant {component} fonctionne sous {volts} V ; sa température limite est {celsius} °C. " +
                             "Explique en trois phrases la tension et la température indiquées."}]
        while tokenizer.count_messages(messages) < input_target:
            messages[1]["content"] += (f" Le contrôle synthétique de {component} consiste à mesurer la tension de "
                                       f"{volts} V et la température de {celsius} °C.")
        return messages

    trial_messages = {"cold": synthetic("SYN-21", 24, 45), "warm_same_prefix": synthetic("SYN-21", 24, 45),
                      "warm_new_content": synthetic("SYN-73", 48, 60)}
    messages = trial_messages["cold"]
    input_tokens = tokenizer.count_messages(messages)
    initial = psutil.virtual_memory().available / 1048576
    initial_swap_free = swap_free_mib()
    if initial < 3072:
        raise RuntimeError("Pilote refusé : moins de 3072 Mio disponibles avant chargement contrôlé")
    reserve = profile["resources"]["host_available_min_mib"]
    report = {"scope": SCOPES[accelerator], "accelerator": {"requested": accelerator},
              "utc": datetime.now(UTC).isoformat(), "profile_sha256": file_hash(profile_path),
              "model": profile["llm"]["model"],
              "model_manifest_sha256": file_hash(ROOT / profile["llm"].get("model_manifest", ".runtime/manifests/ollama-model.json")),
              "baseline_available_mib": initial, "baseline_swap_free_mib": initial_swap_free,
              "serialized_tokens": input_tokens, "samples": [],
              "trials": [], "status": "RUNNING", "thresholds_modified": False,
              "input_target": input_target, "output_limit": output_limit,
              "serialized_tokens_by_trial": {label: tokenizer.count_messages(value) for label, value in trial_messages.items()},
              "num_ctx": profile["llm"]["num_ctx"], "threads": threads, "read_timeout_seconds": read_timeout,
              "use_mmap_option": use_mmap}
    write_json_atomic(output, report)
    service_profile = {**profile, "llm": {**profile["llm"], "base_url": "http://127.0.0.1:11444"}}
    base_url = service_profile["llm"]["base_url"]
    # Même verrou que les générations et imports de toutes les instances : un seul modèle chargé par poste.
    with acquire_host_heavy_lock("calibration", runtime_location(profile, "host_lock_path")), ProcessJob() as job:
        ollama = native_paths()["ollama"]
        child = job.launch([str(ollama), "serve"], cwd=ollama_working_directory(ollama),
                           env=environment(service_profile, ROOT / ".runtime/cpu-pilot", profile_path),
                           log_path=output.with_suffix(".service.log"))
        wait_http(base_url + "/api/version", child, "0.35.0")
        if accelerator == "auto":
            # Découverte journalisée avant le service HTTP : relue dès que /api/version répond, avant tout chargement.
            report["accelerator"] = gpu_decision(output.with_suffix(".service.log"))
            refusal = gpu_refusal(report["accelerator"])
            if refusal:
                report["status"] = "REFUSED_NO_USABLE_GPU"
                write_json_atomic(output, report)
                raise RuntimeError(refusal)
            write_json_atomic(output, report)

        def trial(label: str):
            started = time.monotonic()
            first = None
            text = ""
            final = None
            body = chat_body(profile, trial_messages[label], output_limit=output_limit, threads=threads,
                             use_mmap=use_mmap, accelerator=accelerator)
            with httpx.Client(timeout=httpx.Timeout(read_timeout, connect=10), trust_env=False) as client:
                with client.stream("POST", base_url + "/api/chat", json=body) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get("error"):
                            raise RuntimeError(event["error"])
                        if event.get("message", {}).get("thinking"):
                            raise RuntimeError("Thinking produit malgré think:false")
                        delta = event.get("message", {}).get("content", "")
                        if delta:
                            first = first if first is not None else time.monotonic() - started
                            text += delta
                        if event.get("done"):
                            final = event
                resident = client.get(base_url + "/api/ps").json()["models"]
            model = next((item for item in resident if item.get("name", item.get("model")) == profile["llm"]["model"]), None)
            return {"label": label, "elapsed_seconds": time.monotonic() - started,
                    "ttft_seconds": first, "final": final, "public_synthetic_output": text,
                    "resident": resident, "serialized_tokens": tokenizer.count_messages(trial_messages[label]),
                    "processor": processor_label(int(model.get("size") or 0), int(model.get("size_vram") or 0))
                    if model else None,
                    "output_limit": output_limit,
                    "not_a_400_token_measurement": not final or final.get("eval_count", 0) < 400}

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            for label in ["cold", "warm_same_prefix", "warm_new_content"]:
                future = executor.submit(trial, label)
                while not future.done():
                    sample = {"monotonic_seconds": time.monotonic(), "trial": label,
                              "available_mib": psutil.virtual_memory().available / 1048576,
                              "swap_free_mib": swap_free_mib(),
                              "cpu_percent": psutil.cpu_percent(interval=None), "processes": []}
                    try:
                        tree = [psutil.Process(child.pid), *psutil.Process(child.pid).children(recursive=True)]
                        for process in tree:
                            if sys.platform == "win32":
                                memory = process.memory_info()
                                sample["processes"].append({"pid": process.pid, "rss_mib": memory.rss / 1048576,
                                                            "private_mib": getattr(memory, "private", memory.rss) / 1048576})
                            else:
                                sample["processes"].append({"pid": process.pid, **linux_memory_mib(process)})
                    except psutil.Error:
                        pass
                    report["samples"].append(sample)
                    if len(report["samples"]) % 20 == 0:
                        write_json_atomic(output, report)
                    if sample["available_mib"] < reserve:
                        report["status"] = "FAIL_HOST_RESERVE"
                        report["forced_stop"] = "Owned pilot Job closed to protect host; no document job active"
                        write_json_atomic(output, report)
                        job.close()
                        raise RuntimeError("Réserve mémoire menacée ; pilote isolé arrêté, échec conservé")
                    time.sleep(0.25)
                try:
                    result = future.result()
                except Exception as exc:
                    report["status"] = "FAIL_TRIAL"
                    report["failure"] = {"trial": label, "error": type(exc).__name__, "message": str(exc)}
                    report["minimum_available_mib"] = min(item["available_mib"] for item in report["samples"])
                    write_json_atomic(output, report)
                    raise
                if not result["final"] or not result["public_synthetic_output"]:
                    raise RuntimeError("Réponse pilote incomplète")
                check_residency(result["resident"], accelerator)
                report["trials"].append(result)
                write_json_atomic(output, report)
                print(f"Pilote {label} : TTFT {result['ttft_seconds']:.2f}s, sortie {result['final'].get('eval_count')} tokens", flush=True)
        report["status"] = "PASS_PILOT_ONLY"
        report["minimum_available_mib"] = min(item["available_mib"] for item in report["samples"])
        report["minimum_swap_free_mib"] = min(item["swap_free_mib"] for item in report["samples"])
        report["max_swap_free_drop_mib"] = initial_swap_free - report["minimum_swap_free_mib"]
        report["peak_sum_rss_mib_upper_bound"] = max(sum(p["rss_mib"] for p in item["processes"]) for item in report["samples"])
        if sys.platform == "win32":
            report["peak_sum_private_mib"] = max(sum(p["private_mib"] for p in item["processes"]) for item in report["samples"])
        else:
            # USS : pages propres à chaque processus ; la PSS ajoute la part des pages partagées (GGUF mappé).
            report["peak_sum_uss_mib"] = max(sum(p["uss_mib"] for p in item["processes"]) for item in report["samples"])
            report["peak_sum_pss_mib"] = max(sum(p["pss_mib"] or 0 for p in item["processes"]) for item in report["samples"])
        # Grandeur prévue par l'admission : baisse de mémoire disponible de l'hôte due au pilote.
        report["max_available_drop_mib"] = initial - report["minimum_available_mib"]
        write_json_atomic(output, report)
        send_owned_console_interrupt(child, "ollama")
        try:
            child.wait(30)
        except TimeoutError:
            report["service_stop"] = "forced_owned_job_close"
            write_json_atomic(output, report)
    return report


if __name__ == "__main__":
    import argparse

    # La docstring du module sert d'aide : elle s'adresse à l'opérateur, sans identifiant de décision interne.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau rapport ; un fichier existant est refusé")
    parser.add_argument("--input-tokens", type=int, default=2950)
    parser.add_argument("--output-tokens", type=int, default=64)
    parser.add_argument("--threads", type=int, choices=range(1, 13), default=4)
    parser.add_argument("--read-timeout", type=int, default=600)
    parser.add_argument("--use-mmap", choices=["true", "false"], help="Option Ollama explicite ; absente = défaut Ollama")
    parser.add_argument("--accelerator", choices=ACCELERATORS, default="cpu",
                        help="cpu (défaut) : num_gpu 0, comme avant l'accélération GPU ; auto : option omise, GPU "
                             "exigé, jamais une mesure D07")
    args = parser.parse_args()
    calibrate(args.profile, args.output, input_target=args.input_tokens,
              output_limit=args.output_tokens, threads=args.threads, read_timeout=args.read_timeout,
              use_mmap=None if args.use_mmap is None else args.use_mmap == "true", accelerator=args.accelerator)
