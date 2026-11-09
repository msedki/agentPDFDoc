"""Exécuter un bras natif I3 dans des services et stockages isolés.

Les artefacts verrouillés doivent être provisionnés explicitement auparavant.
Le processus conserve les preuves et arrête seulement ses propres services.
Ollama/Qdrant sont réels, comme le tokenizer, E5, SQLite et QueryService.
"""

from __future__ import annotations

import argparse
import json
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.supervisor import environment, port_probe  # noqa: E402


def available_port(port):
    with port_probe() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise OSError(error.errno, f"Port loopback {port} indisponible pour la qualification ; aucun service existant ne sera arrêté.") from error


def measurement_script(transport):
    if transport not in {"direct", "http"}:
        raise ValueError("Transport de qualification inconnu.")
    name = "production_i4_http.py" if transport == "http" else "revision_campaign.py"
    return ROOT / "tools/qualification" / name


def stop_owned(process):
    from services.runtime.posix_process import group_members

    # OwnedProcess.poll() keeps the leader unreaped, so its group ID cannot be
    # recycled while descendants are being stopped (same rule as the runtime).
    process.signal_group(signal.SIGTERM)
    deadline = time.monotonic() + 15
    while group_members(process.pgid) and time.monotonic() < deadline:
        time.sleep(0.1)
    process.signal_group(signal.SIGKILL)
    deadline = time.monotonic() + 5
    while group_members(process.pgid) and time.monotonic() < deadline:
        time.sleep(0.01)
    remaining = group_members(process.pgid)
    process.kill_group()
    return {"pid": process.pid, "returncode": process.poll(), "remaining_group_members": remaining,
            "owned_group_empty": not remaining, "leader_reaped": process.reaped}


def run(args):
    if not sys.platform.startswith("linux"):
        raise ValueError("Ce pilote de services est réservé à Linux ; utiliser revision_campaign.py avec les runtimes natifs sur une autre plateforme.")
    from services.runtime.posix_process import PosixJob

    transport = getattr(args, "transport", "direct")
    worker = measurement_script(transport)
    for port in (args.ollama_port, args.qdrant_port, args.qdrant_port + 1):
        available_port(port)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    source = args.application_root.resolve(strict=True)
    profile = yaml.safe_load((source / "config/enhanced-4b.yaml").read_text())
    if profile["llm"]["model"] != "qwen3-4b-enhanced:q4km":
        raise ValueError("Seul le modèle 4B verrouillé est autorisé.")
    profile["llm"].update(base_url=f"http://127.0.0.1:{args.ollama_port}", accelerator="cpu",
                          model_manifest=str(ROOT / ".runtime/manifests/qwen3-4b-enhanced.json"),
                          source_model_manifest=str(ROOT / ".runtime/manifests/qwen3-4b-enhanced.json"),
                          tokenizer_dir=str(ROOT / ".runtime/models/qwen3-4b-tokenizer"))
    profile["embedding"]["local_dir"] = str(ROOT / ".runtime/models/e5-small-int8")
    profile["qdrant"].update(url=f"http://127.0.0.1:{args.qdrant_port}", collection="grounded_i3_" + args.label)
    profile["runtime"] = {"host_lock_path": str(output / "host-heavy.lock"),
                          "huggingface_cache_dir": str(ROOT / ".runtime/cache/huggingface")}
    # E5 vérifie la cible du verrou propre au checkout ; ce lien explicite
    # partage les seuls poids immuables, jamais les bases des deux bras.
    if source != ROOT:
        destination = source / ".runtime/models/e5-small-int8"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.symlink_to(ROOT / ".runtime/models/e5-small-int8", target_is_directory=True)
        if destination.resolve() != (ROOT / ".runtime/models/e5-small-int8").resolve():
            raise ValueError("Le checkout de référence utilise d'autres poids E5.")
    profile_path = output / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False))
    env = environment(profile, output / "service-data", profile_path)
    env.pop("RAG_DATA_DIR", None)
    env.pop("RAG_DB_PATH", None)
    env["PYTHONPATH"] = str(ROOT)
    (output / "service-data/home").mkdir(parents=True)
    key = secrets.token_urlsafe(32)
    env["RAG_QDRANT_API_KEY"] = key
    qdrant_config = {"storage": {"storage_path": str(output / "qdrant-storage")},
                     "service": {"host": "127.0.0.1", "http_port": args.qdrant_port,
                                 "grpc_port": args.qdrant_port + 1, "api_key": key}, "telemetry_disabled": True}
    config_path = output / "qdrant.yaml"
    config_path.write_text(yaml.safe_dump(qdrant_config))
    config_path.chmod(0o600)
    executable = ROOT / ".runtime/bin/ollama-0.35.0/bin/ollama"
    qdrant = ROOT / ".runtime/bin/qdrant-1.19.1/qdrant"
    job = PosixJob()
    processes = []
    try:
        for name, command in (("ollama", [str(executable), "serve"]),
                              ("qdrant", [str(qdrant), "--config-path", str(config_path)])):
            processes.append(job.launch(command, cwd=output, env=env, log_path=output / (name + ".log")))
        deadline = time.monotonic() + 45
        while True:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("Un service natif s'est arrêté avant sa disponibilité ; consulter son journal.")
            try:
                with httpx.Client(trust_env=False, timeout=2) as client:
                    ollama_version = client.get(profile["llm"]["base_url"] + "/api/version")
                    ollama_version.raise_for_status()
                    qdrant_version = client.get(profile["qdrant"]["url"] + "/", headers={"api-key": key})
                    qdrant_version.raise_for_status()
                if ollama_version.json()["version"] != "0.35.0" or qdrant_version.json()["version"] != "1.19.1":
                    raise ValueError("Versions natives différentes du verrou.")
                break
            except httpx.HTTPError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Services natifs indisponibles après 45 secondes.") from None
                time.sleep(0.25)
        subprocess.run([sys.executable, str(ROOT / "tools/qualification/provision_enhanced_4b.py"),
                        "--profile", str(profile_path), "--ollama", str(executable)],
                       cwd=ROOT, env=env, check=True, timeout=600)
        command = [sys.executable, str(worker),
                   "--application-root", str(source), "--revision-label", args.label,
                   "--profile", str(profile_path), "--inputs", str(args.inputs.resolve()),
                   "--output", str(output / "measurements")]
        for process in processes:
            command += ["--service-pid", str(process.pid)]
        for case in args.case_id:
            command += ["--case-id", case]
        # Le harnais de révision importe lui-même le checkout demandé.
        measurement_env = {k: v for k, v in env.items() if k != "PYTHONPATH"}
        # Chaque transport peut posséder des workers : conserver son groupe
        # jusqu'au reçu d'arrêt, même si le cas échoue ou dépasse la limite du
        # bloc. Cette borne du harnais est identique pour les deux bras ; elle
        # ne remplace pas les délais du produit et de chaque cas.
        measured = job.launch(command, cwd=source, env=measurement_env, log_path=output / "measurement.log")
        processes.append(measured)
        deadline = time.monotonic() + 1500
        while measured.poll() is None and time.monotonic() < deadline:
            time.sleep(0.25)
        expired = measured.poll() is None
        (output / "measurement-process.json").write_text(json.dumps({
            "transport": transport, "pid": measured.pid, "deadline_seconds": 1500,
            "harness_timeout": expired, "observed_returncode": measured.poll()}, indent=2) + "\n")
        return 124 if expired else measured.poll()
    finally:
        stopped = []
        for process in reversed(processes):
            stopped.append(stop_owned(process))
        job.close()
        all_stopped = all(item["owned_group_empty"] and item["leader_reaped"] for item in stopped)
        (output / "service-stop.json").write_text(json.dumps({
            "owned_services": stopped,
            "all_owned_services_stopped": all_stopped,
            "data_preserved": True}, indent=2) + "\n")
        if transport == "http":
            measured_path = output / "measurement-process.json"
            outcome_path = output / "measurements/transport-result.json"
            measurement = json.loads(measured_path.read_text()) if measured_path.exists() else {}
            result = json.loads(outcome_path.read_text()) if outcome_path.exists() else {}
            passed = (all_stopped and measurement.get("observed_returncode") == 0
                      and measurement.get("harness_timeout") is False and result.get("operational_passed") is True)
            (output / "http-final-result.json").write_text(json.dumps({
                "operational_passed": passed, "all_owned_services_stopped": all_stopped,
                "measurement": measurement, "api_path_result": result,
                "documentary_judgment": "separate independent review required"}, indent=2) + "\n")
            if not all_stopped:
                raise RuntimeError("Arrêt des processus natifs possédés non confirmé ; aucun PASS HTTP global.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path, required=True)
    parser.add_argument("--label", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-port", type=int, default=11439)
    parser.add_argument("--qdrant-port", type=int, default=6339)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--transport", choices=("direct", "http"), default="direct")
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
