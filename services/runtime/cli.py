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
from typing import Any
from urllib.parse import urlsplit

import psutil

from .artifacts import ROOT, file_hash, provision_artifacts, write_json_atomic
from .resources import admission_requirement
from .supervisor import (
    app_origin,
    control_headers,
    data_path,
    environment,
    load_profile,
    native_paths,
    owned_pids,
    port_states,
    qdrant_data_path,
    send_owned_console_interrupt,
    start,
    status,
    stop,
    supervise,
    wait_http,
)
from .windows_process import WindowsJob

MODELS_LOCK = ROOT / "config/models.lock.json"


def ollama_store_files(name: str, store: Path | None = None) -> dict:
    """Présence locale d'un tag Ollama (manifeste, blobs et tailles), service arrêté ou non."""
    store = store or OLLAMA_MODELS_DIR
    path = _manifest_path(name, store)
    if not path.is_file():
        return {"status": "absent", "manifest": str(path)}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        entries = [manifest["config"], *manifest["layers"]]
        if not all(isinstance(entry, dict) for entry in entries):
            raise TypeError("entrée de manifeste non objet")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "invalid_manifest", "manifest": str(path), "reason": type(exc).__name__}
    issues = []
    for entry in entries:
        algorithm, _, value = str(entry.get("digest", "")).partition(":")
        blob = store / "blobs" / f"sha256-{value}"  # chemin testé seulement si le digest est valide
        if algorithm != "sha256" or len(value) != 64:
            issues.append({"digest": entry.get("digest"), "issue": "invalid_digest"})
        elif not blob.is_file():
            issues.append({"digest": entry["digest"], "issue": "blob_missing"})
        elif blob.stat().st_size != entry.get("size"):
            issues.append({"digest": entry["digest"], "issue": "size_mismatch",
                           "expected": entry.get("size"), "observed": blob.stat().st_size})
    return {"status": "incomplete" if issues else "present", "manifest": str(path),
            "manifest_sha256": file_hash(path), "blobs": len(entries), "issues": issues,
            "entries": [{key: entry.get(key) for key in ("mediaType", "digest", "size")} for entry in entries]}


def model_lock_conformity(lock_path: Path | None = None, store: Path | None = None,
                          hash_limit_bytes: int | None = 1048576) -> dict:
    """Conformité hors ligne du stockage Ollama au verrou versionné.

    Les blobs jusqu'à hash_limit_bytes sont rehachés (None : tous) ; au-delà, la taille est comparée.
    """
    lock_path = lock_path or MODELS_LOCK
    store = store or OLLAMA_MODELS_DIR
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    result: dict = {"status": "conform", "lock": str(lock_path), "lock_sha256": file_hash(lock_path),
              "hash_limit_bytes": hash_limit_bytes, "models": {}}
    for name, expected in lock["models"].items():
        files = ollama_store_files(name, store)
        issues = [*files.get("issues", [])]
        if files["status"] in {"absent", "invalid_manifest"}:
            issues.append({"issue": files["status"]})
        else:
            if files["manifest_sha256"] != expected["manifest_sha256"]:
                issues.append({"issue": "manifest_digest_mismatch", "expected": expected["manifest_sha256"],
                               "observed": files["manifest_sha256"]})
            locked = [{key: entry.get(key) for key in ("mediaType", "digest", "size")}
                      for entry in [expected["config"], *expected["layers"]]]
            if files["entries"] != locked:
                issues.append({"issue": "layers_differ_from_lock"})
            for entry in files["entries"]:
                blob = store / "blobs" / ("sha256-" + str(entry["digest"]).partition(":")[2])
                if (blob.is_file() and (hash_limit_bytes is None or blob.stat().st_size <= hash_limit_bytes)
                        and "sha256:" + file_hash(blob) != entry["digest"]):
                    issues.append({"digest": entry["digest"], "issue": "blob_hash_mismatch"})
        state = "absent" if files["status"] == "absent" else ("nonconform" if issues else "conform")
        result["models"][name] = {"status": state, "issues": issues}
        if state != "conform":
            result["status"] = "nonconform"
    return result


def llm_model_diagnosis(files: dict, service: dict) -> dict:
    """Sépare modèle absent du stockage et service Ollama indisponible."""
    if files["status"] == "absent":
        state = "model_absent"
    elif files["status"] != "present":
        state = "model_files_" + files["status"]
    elif service.get("status") == "service_unavailable":
        state = "service_unavailable_model_files_present"
    elif service.get("status") == "absent":
        state = "service_does_not_list_local_model"
    else:
        state = "available"
    return {"status": state, "files": files["status"], "service": service.get("status", "listed")}


def doctor(profile_path: Path) -> dict:
    import httpx

    profile = load_profile(profile_path)
    directory = data_path(profile)
    available = psutil.virtual_memory().available / 1048576
    result: dict = {"utc": datetime.now(UTC).isoformat(), "platform": "Windows native, no WSL/Docker",
              "python": {"version": sys.version.split()[0], "executable": sys.executable},
              "resources": {"available_mib": available,
                            "disk_free_mib": shutil.disk_usage(ROOT).free / 1048576},
              "profile_sha256": file_hash(profile_path), "data_dir": str(directory), "checks": {},
              "runtime": status(profile_path)}
    checks = result["checks"]
    try:
        checks["qdrant_storage"] = {"status": "valid", "path": str(qdrant_data_path(profile, directory)),
                                    "native_storage_path_limit": 57}
    except ValueError as exc:
        checks["qdrant_storage"] = {"status": "invalid", "reason": str(exc)}
    runtime = result["runtime"]
    checks["profile_application"] = {"status": "not_running"}
    if runtime.get("status") == "stale":
        checks["profile_application"] = {"status": "stale_runtime_state", "recorded_status": runtime.get("recorded_status"),
                                         "limit": "Supervisor identity invalid; recorded state is not a running instance."}
    if runtime.get("status") in {"running", "starting"}:
        applied = runtime.get("profile_sha256") == result["profile_sha256"] and runtime.get("data_dir") == str(directory)
        checks["profile_application"] = {"status": "applied" if applied else "restart_required",
            "declared_profile_sha256": result["profile_sha256"], "runtime_profile_sha256": runtime.get("profile_sha256"),
            "limit": "Compares supervisor-recorded profile identity; health/readiness still determine actual service availability."}
    checks["ports"] = port_states({"app": profile["app"]["port"], "qdrant": urlsplit(profile["qdrant"]["url"]).port,
                                   "ollama": urlsplit(profile["llm"]["base_url"]).port}, owned_pids(runtime))
    checks["cold_admission"] = {}
    for owner in ("generation", "ingestion"):
        requirement = admission_requirement(profile.get("resources", {}), owner)
        margin = available - requirement["required_available_mib"]
        checks["cold_admission"][owner] = {**requirement, "available_mib": round(available, 2),
                                           "margin_mib": round(margin, 2), "admissible_now": margin >= 0}
    checks["cold_admission"]["limit"] = ("Snapshot: required = max(admit minimum, cold peak estimate + host reserve); "
                                         "a resident model only needs its additional peak.")
    try:
        checks["model_lock"] = model_lock_conformity()
        checks["model_lock"]["profile_models_locked"] = all(
            name in checks["model_lock"]["models"] for name in {profile["llm"]["model"], profile["llm"].get("source_model", profile["llm"]["model"])})
    except (OSError, ValueError, KeyError) as exc:
        checks["model_lock"] = {"status": "invalid_lock", "reason": f"{type(exc).__name__}: {exc}"}
    model_files = ollama_store_files(profile["llm"]["model"])
    model_files.pop("entries", None)
    checks["llm_model_files"] = {**model_files, "limit": "Blob sizes only; see model_lock for digests."}
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
    origin, verify = app_origin(profile)
    with httpx.Client(timeout=5, trust_env=False, verify=verify) as client:
        for name, url in [("api_health", origin + "/api/v1/health"),
                          ("api_ready", origin + "/api/v1/readiness"),
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
        checks["index_consistency"] = {"status": "api_unavailable"}
        if result["services"]["api_health"].get("http_status") == 200:
            try:
                response = client.get(origin + "/api/v1/diagnostics", headers=control_headers(data_path(profile)))
                response.raise_for_status()
                diagnostics = response.json()
                checks["index_consistency"] = diagnostics.get("index_consistency") or {
                    "status": "not_exposed",
                    "reason": "GET /api/v1/diagnostics does not expose active-generation Qdrant points vs SQLite chunks",
                    "diagnostics_keys": sorted(diagnostics)}
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                checks["index_consistency"] = {"status": "diagnostics_unavailable", "reason": type(exc).__name__}
    checks["llm_model_diagnosis"] = llm_model_diagnosis(checks["llm_model_files"], checks["llm_model"])
    # Ces diagnostics distinguent présence des fichiers, disponibilité et recette.
    result["qualification"] = "NOT_RUN: doctor does not prove an end-to-end answer"
    return result


OLLAMA_MODELS_DIR = ROOT / ".runtime/models/ollama"
SOURCE_MODEL_MANIFEST = ".runtime/manifests/ollama-model.json"


def _manifest_path(name: str, store: Path | None = None) -> Path:
    model, _, tag = name.partition(":")
    return (store or OLLAMA_MODELS_DIR) / "manifests/registry.ollama.ai/library" / model / (tag or "latest")


def _ollama_manifest(name: str) -> dict:
    return json.loads(_manifest_path(name).read_text(encoding="utf-8"))


def _blob(digest: str, store: Path | None = None) -> Path:
    algorithm, _, value = digest.partition(":")
    if algorithm != "sha256" or len(value) != 64:
        raise ValueError(f"Digest de blob inattendu : {digest}")
    return (store or OLLAMA_MODELS_DIR) / "blobs" / f"sha256-{value}"


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
            notified: dict[str, int] = {}
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
            source: dict[str, Any] = {"model": model, "model_info": details.get("model_info"), "details": details.get("details"),
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
        # Même condition que le premier bloc, qui lève FileNotFoundError si pnpm manque.
        assert pnpm is not None
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


def open_workspace(profile_path: Path, *, launch: bool = True) -> dict[str, Any]:
    """Demande à l'instance un lien d'ouverture à usage unique (W011) et l'ouvre dans le navigateur par défaut."""
    import httpx

    profile = load_profile(profile_path)
    current = status(profile_path)
    if current.get("status") != "running":
        raise RuntimeError("Instance non démarrée : lancer d'abord .\\rag.ps1 up")
    headers = control_headers(data_path(profile))
    if not headers:
        raise RuntimeError("Jeton de contrôle de l'instance absent : redémarrer avec .\\rag.ps1 down puis up")
    origin, verify = app_origin(profile)
    with httpx.Client(timeout=10, trust_env=False, verify=verify) as client:
        response = client.post(origin + "/api/v1/admin/session-links", headers=headers)
        response.raise_for_status()
        link = response.json()
    url = origin + link["path"]
    if launch:
        os.startfile(url)  # type: ignore[attr-defined]  # Windows seulement (W001) ; absent des stubs hors win32
        # Le lien est un secret à usage unique : il n'est ni affiché ni écrit dans un rapport quand le navigateur l'a reçu.
        return {"opened_in_browser": True, "expires_in_seconds": link["expires_in_seconds"], "single_use": True}
    return {"opened_in_browser": False, "url": url, "expires_in_seconds": link["expires_in_seconds"], "single_use": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["provision", "doctor", "up", "status", "logs", "down", "_serve", "pull-model", "backup", "restore", "verify", "open", "init-profile"])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--only")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--path", type=Path, help="Destination backup ou snapshot source restore/verify")
    parser.add_argument("--target", type=Path, help="Racine neuve de restauration")
    parser.add_argument("--no-browser", action="store_true", help="open : afficher le lien au lieu d'ouvrir le navigateur")
    parser.add_argument("--qdrant-storage", type=Path, help="init-profile : dossier court du stockage Qdrant")
    parser.add_argument("--ports", help="init-profile : ports API,Qdrant,Ollama séparés par des virgules")
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
        elif args.command == "init-profile":
            from .profile_setup import write_user_profile
            if not args.target:
                raise ValueError("init-profile requiert --target (racine des données de l'utilisateur)")
            ports = dict(zip(("app", "qdrant", "ollama"), map(int, args.ports.split(",")), strict=True)) if args.ports else None
            result = write_user_profile(args.profile, args.target, qdrant_storage=args.qdrant_storage, ports=ports)
        elif args.command == "open":
            result = open_workspace(args.profile, launch=not args.no_browser)
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
            # Le lien d'ouverture est un secret à usage unique : il n'est jamais écrit dans un rapport.
            write_json_atomic(args.report, {key: value for key, value in result.items() if key != "url"} if args.command == "open" else result)
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
