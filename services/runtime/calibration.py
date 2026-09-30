"""Pilote CPU isolé et surveillé ; ne modifie aucun seuil automatiquement."""

from __future__ import annotations

import concurrent.futures
import json
import socket
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psutil

from .artifacts import ROOT, file_hash, write_json_atomic
from .supervisor import environment, load_profile, native_paths, send_owned_console_interrupt, wait_http
from .windows_process import WindowsJob


def calibrate(profile_path: Path, output: Path, *, input_target: int = 2950,
              output_limit: int = 64, threads: int = 4, read_timeout: int = 600) -> dict:
    from services.api.context import LlmTokenizer
    from services.api.settings import Settings

    profile = load_profile(profile_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 11444))
    settings = Settings.load(profile_path)
    tokenizer = LlmTokenizer(settings)
    messages = [{"role": "system", "content": "Tu réponds en français, sans raisonnement caché. Ce texte est synthétique."},
                {"role": "user", "content": "Voici un corpus synthétique. " +
                 "Le composant SYN-21 fonctionne sous 24 V ; sa température limite est 45 °C. " +
                 "Explique en trois phrases la tension et la température indiquées."}]
    while tokenizer.count_messages(messages) < input_target:
        messages[1]["content"] += " Le contrôle synthétique consiste à mesurer la tension de 24 V et la température de 45 °C."
    input_tokens = tokenizer.count_messages(messages)
    initial = psutil.virtual_memory().available / 1048576
    if initial < 3072:
        raise RuntimeError("Pilote refusé : moins de 3072 Mio disponibles avant chargement contrôlé")
    reserve = profile["resources"]["host_available_min_mib"]
    report = {"scope": "Early QCPU controlled pilot; not the final performance qualification",
              "utc": datetime.now(UTC).isoformat(), "profile_sha256": file_hash(profile_path),
              "model_manifest_sha256": file_hash(ROOT / ".runtime/manifests/ollama-model.json"),
              "baseline_available_mib": initial, "serialized_tokens": input_tokens, "samples": [],
              "trials": [], "status": "RUNNING", "thresholds_modified": False,
              "input_target": input_target, "output_limit": output_limit,
              "threads": threads, "read_timeout_seconds": read_timeout}
    write_json_atomic(output, report)
    service_profile = {**profile, "llm": {**profile["llm"], "base_url": "http://127.0.0.1:11444"}}
    base_url = service_profile["llm"]["base_url"]
    with WindowsJob() as job:
        child = job.launch([str(native_paths()["ollama"]), "serve"], cwd=ROOT,
                           env=environment(service_profile, ROOT / ".runtime/cpu-pilot", profile_path),
                           log_path=output.with_suffix(".service.log"))
        wait_http(base_url + "/api/version", child, "0.35.0")

        def trial(label: str):
            started = time.monotonic()
            first = None
            text = ""
            final = None
            body = {"model": profile["llm"]["model"], "messages": messages, "think": False,
                    "stream": True, "keep_alive": "10m", "options": {
                        "num_ctx": 8192, "num_predict": output_limit, "num_gpu": 0, "num_thread": threads,
                        "temperature": 0.2, "top_p": 0.9}}
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
            return {"label": label, "elapsed_seconds": time.monotonic() - started,
                    "ttft_seconds": first, "final": final, "public_synthetic_output": text,
                    "resident": resident, "serialized_tokens": input_tokens,
                    "output_limit": output_limit,
                    "not_a_400_token_measurement": not final or final.get("eval_count", 0) < 400}

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            for label in ["cold", "warm_same_prefix"]:
                future = executor.submit(trial, label)
                while not future.done():
                    sample = {"monotonic_seconds": time.monotonic(), "trial": label,
                              "available_mib": psutil.virtual_memory().available / 1048576,
                              "cpu_percent": psutil.cpu_percent(interval=None), "processes": []}
                    try:
                        tree = [psutil.Process(child.pid), *psutil.Process(child.pid).children(recursive=True)]
                        for process in tree:
                            memory = process.memory_info()
                            sample["processes"].append({"pid": process.pid, "rss_mib": memory.rss / 1048576,
                                                        "private_mib": getattr(memory, "private", memory.rss) / 1048576})
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
                if any(item.get("size_vram") != 0 for item in result["resident"]):
                    raise RuntimeError("Le modèle pilote a utilisé le GPU")
                report["trials"].append(result)
                write_json_atomic(output, report)
                print(f"Pilote {label} : TTFT {result['ttft_seconds']:.2f}s, sortie {result['final'].get('eval_count')} tokens", flush=True)
        report["status"] = "PASS_PILOT_ONLY"
        report["minimum_available_mib"] = min(item["available_mib"] for item in report["samples"])
        report["peak_sum_rss_mib_upper_bound"] = max(sum(p["rss_mib"] for p in item["processes"]) for item in report["samples"])
        write_json_atomic(output, report)
        send_owned_console_interrupt(child)
        try:
            child.wait(30)
        except TimeoutError:
            report["service_stop"] = "forced_owned_job_close"
            write_json_atomic(output, report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "RAG_Local_Agents/reports/cpu-pilot.json")
    parser.add_argument("--input-tokens", type=int, default=2950)
    parser.add_argument("--output-tokens", type=int, default=64)
    parser.add_argument("--threads", type=int, choices=range(1, 13), default=4)
    parser.add_argument("--read-timeout", type=int, default=600)
    args = parser.parse_args()
    calibrate(args.profile, args.output, input_target=args.input_tokens,
              output_limit=args.output_tokens, threads=args.threads, read_timeout=args.read_timeout)
