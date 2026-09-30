"""Entrée locale d'exploitation : aucun service conteneur ni téléchargement nominal."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import psutil

from .artifacts import ROOT, file_hash, provision_artifacts, write_json_atomic
from .supervisor import (
    data_path,
    environment,
    load_profile,
    native_paths,
    qdrant_data_path,
    read_state,
    send_owned_console_interrupt,
    start,
    status,
    stop,
    supervise,
    wait_http,
)
from .windows_process import WindowsJob


def doctor(profile_path: Path) -> dict:
    import httpx

    profile = load_profile(profile_path)
    directory = data_path(profile)
    result = {"utc": datetime.now(UTC).isoformat(), "platform": "Windows native, no WSL/Docker",
              "python": {"version": sys.version.split()[0], "executable": sys.executable},
              "resources": {"available_mib": psutil.virtual_memory().available / 1048576,
                            "disk_free_mib": shutil.disk_usage(ROOT).free / 1048576},
              "profile_sha256": file_hash(profile_path), "data_dir": str(directory), "checks": {},
              "runtime": read_state(directory)}
    checks = result["checks"]
    try:
        checks["qdrant_storage"] = {"status": "valid", "path": str(qdrant_data_path(profile, directory)),
                                    "native_storage_path_limit": 57}
    except ValueError as exc:
        checks["qdrant_storage"] = {"status": "invalid", "reason": str(exc)}
    runtime = result["runtime"]
    checks["profile_application"] = {"status": "not_running"}
    if runtime.get("status") in {"running", "starting"}:
        applied = runtime.get("profile_sha256") == result["profile_sha256"] and runtime.get("data_dir") == str(directory)
        checks["profile_application"] = {"status": "applied" if applied else "restart_required",
            "declared_profile_sha256": result["profile_sha256"], "runtime_profile_sha256": runtime.get("profile_sha256"),
            "limit": "Compares supervisor-recorded profile identity; health/readiness still determine actual service availability."}
    checks["python312"] = sys.version_info[:2] == (3, 12)
    checks["dependencies_locked"] = (ROOT / "uv.lock").is_file() and (ROOT / "apps/web/pnpm-lock.yaml").is_file()
    checks["static_export"] = (ROOT / "apps/web/out/workspace.html").is_file() or (ROOT / "apps/web/out/workspace/index.html").is_file()
    try:
        checks["native_binaries"] = {key: str(value) for key, value in native_paths().items()}
    except (OSError, ValueError) as exc:
        checks["native_binaries"] = {"error": str(exc)}
    result["packages"] = {name: importlib.metadata.version(name) for name in ["fastapi", "docling", "onnxruntime", "psutil"]}
    checks["embedding_files"] = all((ROOT / profile["embedding"]["local_dir"] / name).is_file()
                                    for name in [profile["embedding"]["onnx_file"], "tokenizer.json"])
    checks["llm_tokenizer"] = (ROOT / profile["llm"]["tokenizer_dir"] / "chat_template.jinja").is_file()
    checks["ocr_languages"] = {name: (ROOT / profile["pdf"]["tessdata_dir"] / (name + ".traineddata")).is_file()
                               for name in set(profile["pdf"]["ocr_languages"]) | {"osd"}}
    checks["ocr_tsv_config"] = (ROOT / profile["pdf"]["tessdata_dir"] / "configs/tsv").is_file()
    checks["tesseract_binary"] = (ROOT / profile["pdf"]["tesseract_cmd"]).is_file()
    result["node_tools"] = {}
    for name, command in [("node", shutil.which("node.exe")), ("pnpm", shutil.which("pnpm.cmd"))]:
        if command:
            probe = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15,
                                   env={**os.environ, "COREPACK_ENABLE_NETWORK": "0"})
            result["node_tools"][name] = {"path": command, "version": probe.stdout.strip(), "exit_code": probe.returncode}
        else:
            result["node_tools"][name] = {"status": "absent_from_path"}
    result["services"] = {}
    with httpx.Client(timeout=5, trust_env=False) as client:
        for name, url in [("api_health", f"http://127.0.0.1:{profile['app']['port']}/api/v1/health"),
                          ("api_ready", f"http://127.0.0.1:{profile['app']['port']}/api/v1/readiness"),
                          ("qdrant", profile["qdrant"]["url"]), ("ollama", profile["llm"]["base_url"] + "/api/version")]:
            try:
                response = client.get(url)
                result["services"][name] = {"http_status": response.status_code, "body": response.json()}
            except (httpx.HTTPError, ValueError) as exc:
                result["services"][name] = {"status": "unavailable", "reason": type(exc).__name__}
        try:
            response = client.get(profile["llm"]["base_url"] + "/api/tags")
            response.raise_for_status()
            tags = response.json()["models"]
            model = next((item for item in tags if item["name"] == profile["llm"]["model"]), None)
            checks["llm_model"] = model or {"status": "absent"}
            response = client.get(profile["llm"]["base_url"] + "/api/ps")
            response.raise_for_status()
            result["loaded_models"] = [{"name": item.get("name"), "digest": item.get("digest"),
                                        "size_vram": item.get("size_vram"), "size": item.get("size")}
                                       for item in response.json()["models"]]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            checks["llm_model"] = {"status": "service_unavailable", "reason": type(exc).__name__}
    # Ces diagnostics distinguent présence des fichiers, disponibilité et recette.
    result["qualification"] = "NOT_RUN: doctor does not prove an end-to-end answer"
    return result


OLLAMA_MODELS_DIR = ROOT / ".runtime/models/ollama"
SOURCE_MODEL_MANIFEST = ".runtime/manifests/ollama-model.json"


def _ollama_manifest(name: str) -> dict:
    model, _, tag = name.partition(":")
    path = OLLAMA_MODELS_DIR / "manifests/registry.ollama.ai/library" / model / (tag or "latest")
    return json.loads(path.read_text(encoding="utf-8"))


def _blob(digest: str) -> Path:
    algorithm, _, value = digest.partition(":")
    if algorithm != "sha256" or len(value) != 64:
        raise ValueError(f"Digest de blob inattendu : {digest}")
    return OLLAMA_MODELS_DIR / "blobs" / f"sha256-{value}"


def _model_record(client, base_url: str, name: str, quantization: str) -> tuple[dict, dict]:
    tags = client.get(base_url + "/api/tags").json()["models"]
    model = next((item for item in tags if item["name"] == name), None)
    if model is None:
        raise FileNotFoundError(f"Modèle {name} absent du stockage Ollama local")
    observed = model.get("details", {}).get("quantization_level")
    if observed != quantization:
        raise RuntimeError(f"Quantification {observed} différente du contrat")
    payload = client.post(base_url + "/api/show", json={"model": name})
    payload.raise_for_status()
    return model, payload.json()


def _derive_text_model(client, base_url: str, profile: dict, env: dict, directory: Path,
                       source: dict) -> dict:
    """Dérivation texte seul reproductible ; idempotente si source et cible sont inchangées."""
    from .text_model import create_ollama_model, derive_text_only, modelfile_text, write_modelfile

    llm = profile["llm"]
    target_manifest_path = ROOT / llm["model_manifest"]
    source_manifest = _ollama_manifest(llm["source_model"])
    layers = {layer["mediaType"].rsplit(".", 1)[-1]: layer for layer in source_manifest["layers"]}
    source_digest = layers["model"]["digest"]
    if target_manifest_path.is_file():
        previous = json.loads(target_manifest_path.read_text(encoding="utf-8"))
        try:
            current, _ = _model_record(client, base_url, llm["model"], llm["required_quantization"])
        except FileNotFoundError:
            current = None
        if (current and previous.get("derivation", {}).get("source_model_layer_digest") == source_digest
                and previous.get("model", {}).get("digest") == current.get("digest")):
            return previous
    config = json.loads(_blob(source_manifest["config"]["digest"]).read_text(encoding="utf-8"))
    parameters = json.loads(_blob(layers["params"]["digest"]).read_text(encoding="utf-8")) if "params" in layers else {}
    license_text = _blob(layers["license"]["digest"]).read_text(encoding="utf-8") if "license" in layers else ""
    work = directory / "text-model"
    work.mkdir(parents=True, exist_ok=True)
    gguf = work / "model.gguf"
    gguf.unlink(missing_ok=True)
    if shutil.disk_usage(work).free < 2 * int(layers["model"]["size"]) + 2 * 1024**3:
        raise RuntimeError("Espace disque insuffisant pour dériver puis importer le modèle texte (réserve 2 Gio)")
    print(f"Dérivation texte seul depuis {llm['source_model']} ({source_digest})", flush=True)
    report = derive_text_only(_blob(source_digest), gguf, expected_source_sha256=source_digest.split(":", 1)[1])
    modelfile = work / "Modelfile"
    write_modelfile(modelfile, modelfile_text(gguf.name, config, parameters, license_text))
    try:
        create_ollama_model(native_paths()["ollama"], base_url.removeprefix("http://"), llm["model"], modelfile,
                            env, directory / "ollama-create.log")
    finally:
        gguf.unlink(missing_ok=True)
    model, details = _model_record(client, base_url, llm["model"], llm["required_quantization"])
    created = _ollama_manifest(llm["model"])
    created_layers = {layer["mediaType"].rsplit(".", 1)[-1]: layer for layer in created["layers"]}
    if created_layers["model"]["digest"] != "sha256:" + report["derived_sha256"]:
        raise RuntimeError("Couche modèle importée différente du GGUF dérivé vérifié")
    for kind in ("license", "params"):
        if kind in layers and created_layers.get(kind, {}).get("digest") != layers[kind]["digest"]:
            raise RuntimeError(f"Couche {kind} importée différente de celle du modèle source")
    manifest = {"model": model, "model_info": details.get("model_info"), "details": details.get("details"),
                "template": details.get("template"), "parameters": details.get("parameters"),
                "license": details.get("license"), "provisioned_at_utc": datetime.now(UTC).isoformat(),
                "inference_validated": False,
                "source": f"derived locally from {source['model']['name']} ({source['source']})",
                "source_model": {"name": source["model"]["name"], "digest": source["model"]["digest"]},
                "derivation": {**report, "source_model_layer_digest": source_digest,
                               "derived_model_layer_digest": created_layers["model"]["digest"],
                               "ollama_config": {key: config.get(key) for key in ("renderer", "parser", "requires")},
                               "reason": "Ollama 0.35.0 auto-enables --mmproj on inline v.* tensors; the RAG never sends images",
                               "official_source": "https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go"}}
    write_json_atomic(target_manifest_path, manifest)
    return manifest


def pull_model(profile_path: Path, offline: bool = False) -> dict:
    import httpx

    profile = load_profile(profile_path)
    profile = {**profile, "llm": {**profile["llm"], "base_url": "http://127.0.0.1:11444"}}
    llm = profile["llm"]
    source_name = llm.get("source_model", llm["model"])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 11444))
    paths = native_paths()
    directory = ROOT / ".runtime/provision-service"
    env = environment(profile, directory, profile_path)
    with WindowsJob() as job:
        child = job.launch([str(paths["ollama"]), "serve"], cwd=ROOT, env=env,
                           log_path=directory / "ollama-pull.log")
        wait_http(llm["base_url"] + "/api/version", child, "0.35.0")
        with httpx.Client(timeout=httpx.Timeout(300, connect=10), trust_env=False) as client:
            notified = {}
            if not offline:
                with client.stream("POST", llm["base_url"] + "/api/pull",
                                   json={"model": source_name, "stream": True}) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if "error" in event:
                            raise RuntimeError(event["error"])
                        digest = event.get("digest", "status")
                        completed = event.get("completed", 0)
                        if completed - notified.get(digest, -67108864) >= 67108864 or event.get("status") == "success":
                            print(f"Modèle : {event['status']} {completed / 1048576:.0f} Mio", flush=True)
                            notified[digest] = completed
            model, details = _model_record(client, llm["base_url"], source_name, llm["required_quantization"])
            source = {"model": model, "model_info": details.get("model_info"), "details": details.get("details"),
                      "template": details.get("template"), "parameters": details.get("parameters"),
                      "license": details.get("license"), "provisioned_at_utc": datetime.now(UTC).isoformat(),
                      "inference_validated": False, "source": f"https://ollama.com/library/{source_name}"}
            source_manifest_path = ROOT / llm.get("source_model_manifest", SOURCE_MODEL_MANIFEST)
            if offline and source_manifest_path.is_file():
                recorded = json.loads(source_manifest_path.read_text(encoding="utf-8"))
                if recorded.get("model", {}).get("digest") != model.get("digest"):
                    raise RuntimeError("Modèle source local différent du manifeste provisionné")
                source = recorded
            else:
                write_json_atomic(source_manifest_path, source)
            result = source
            if llm["model"] != source_name:
                result = _derive_text_model(client, llm["base_url"], profile, env, directory, source)
        send_owned_console_interrupt(child)
        try:
            child.wait(30)
        except TimeoutError:
            print("Service de provisionnement : arrêt forcé ciblé du Job, aucune inférence active.", flush=True)
    return result["model"]


def provision(profile_path: Path, only: str | None = None, offline: bool = False, skip_model: bool = False):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Provisionnement applicatif requis sous Python3.12 isolé")
    uv = ROOT / ".runtime/bootstrap/bin/uv.exe"
    if not only:
        subprocess.run([str(uv), "sync", "--locked", "--python", sys.executable, "--no-python-downloads",
                        "--cache-dir", str(ROOT / ".runtime/cache/uv"), *(["--offline"] if offline else [])],
                       cwd=ROOT, check=True)
        node_env = {**os.environ, "COREPACK_ENABLE_NETWORK": "0", "NEXT_TELEMETRY_DISABLED": "1"}
        pnpm = shutil.which("pnpm.cmd")
        if not pnpm:
            raise FileNotFoundError("pnpm10.34.1 requis ; doctor indique le prérequis manquant")
        subprocess.run([pnpm, "install", "--frozen-lockfile", *(["--offline"] if offline else [])],
                       cwd=ROOT / "apps/web", env=node_env, check=True)
    provision_artifacts(only, offline=offline)
    if not only:
        from .provisioning import tesseract
        tesseract(load_profile(profile_path), offline=offline)
        subprocess.run([pnpm, "run", "build"], cwd=ROOT / "apps/web",
                       env={**node_env, "NODE_OPTIONS": "--max-old-space-size=2048"}, check=True)
    if not only and not skip_model:
        if offline:
            llm = load_profile(profile_path)["llm"]
            source = ROOT / llm.get("source_model_manifest", SOURCE_MODEL_MANIFEST)
            if not source.is_file():
                raise FileNotFoundError("Modèle Ollama non provisionné pour installation offline")
            if not (ROOT / llm.get("model_manifest", SOURCE_MODEL_MANIFEST)).is_file():
                # La dérivation texte seul est locale : elle reste permise hors ligne.
                return pull_model(profile_path, offline=True)
        else:
            return pull_model(profile_path)
    return {"artifacts": "verified", "model": "not_requested" if skip_model else "unchanged"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["provision", "doctor", "up", "status", "logs", "down", "_serve", "pull-model", "backup", "restore", "verify"])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--only")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--path", type=Path, help="Destination backup ou snapshot source restore/verify")
    parser.add_argument("--target", type=Path, help="Racine neuve de restauration")
    args = parser.parse_args()
    try:
        if args.command == "_serve":
            return supervise(args.profile)
        if args.command == "provision":
            result = provision(args.profile, args.only, args.offline, args.skip_model)
        elif args.command == "pull-model":
            result = pull_model(args.profile, args.offline)
        elif args.command == "doctor":
            result = doctor(args.profile)
        elif args.command == "backup":
            from .backup import create_backup
            result = create_backup(args.profile, args.path)
        elif args.command == "verify":
            from .backup import verify_backup
            if not args.path:
                raise ValueError("verify requiert --path")
            result = verify_backup(args.path)
        elif args.command == "restore":
            from .backup import restore_backup
            if not args.path or not args.target:
                raise ValueError("restore requiert --path et --target (racine neuve)")
            result = restore_backup(args.path, args.target)
        elif args.command == "up":
            result = start(args.profile)
        elif args.command == "down":
            result = stop(args.profile)
        elif args.command == "status":
            result = status(args.profile)
        else:
            current = status(args.profile)
            result = {name: identity.get("log_path") for name, identity in current.get("services", {}).items()}
        if args.report:
            write_json_atomic(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        failure = {"status": "failed", "error": type(exc).__name__, "message": str(exc)}
        if args.report:
            write_json_atomic(args.report, failure)
        print(json.dumps(failure, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
