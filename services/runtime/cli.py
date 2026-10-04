"""Entrée locale d'exploitation : aucun service conteneur ni téléchargement nominal."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psutil

from .accelerator import (
    DISCOVERY_MANIFEST,
    GPU_GROUP,
    QUALIFIED_GPU_PATHS,
    cuda_libraries_removed,
    describe_device,
    device_variant,
    discovery_record,
    entries_for_host,
    host_signals,
    is_nvidia,
    jetson_label,
    libraries_signature,
    ollama_version,
    probe_discovery,
    processor_label,
    profile_accelerator,
    read_discovery,
    reason_text,
    resolve_mode,
    verified_libraries,
)
from .artifacts import ROOT, file_hash, provision_artifacts, write_json_atomic
from .platforms import executable_name, launcher_command, native_executable, platform_label
from .resources import admission_requirement
from .supervisor import (
    ProcessJob,
    app_origin,
    control_headers,
    data_path,
    environment,
    load_profile,
    native_paths,
    ollama_working_directory,
    owned_pids,
    port_probe,
    port_states,
    qdrant_data_path,
    send_owned_console_interrupt,
    start,
    status,
    stop,
    supervise,
    wait_http,
)

MODELS_LOCK = ROOT / "config/models.lock.json"
PNPM_DEFAULT_VERSION = "10.34.1"
MODEL_PROFILES = {"qwen3.5:2b": "local16.yaml", "qwen3.5:4b": "local16-4b.yaml"}


def model_profile_path(profile: Path | None, model: str | None) -> Path:
    """Un choix au démarrage sélectionne un vrai profil, sans réécrire un profil utilisateur."""
    if profile is not None and model is not None:
        raise ValueError("--model et --profile sont exclusifs ; choisissez le profil utilisateur ou un modèle livré")
    if model is not None and model not in MODEL_PROFILES:
        raise ValueError("Modèle livré inconnu ; choisir qwen3.5:2b ou qwen3.5:4b")
    return profile if profile is not None else ROOT / "config" / MODEL_PROFILES[model or "qwen3.5:2b"]


def pnpm_required_version() -> str:
    """Version de pnpm fixée par `packageManager` de l'interface (« pnpm@10.34.1+sha512… »)."""
    try:
        declared = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8")).get("packageManager", "")
    except (OSError, ValueError):
        declared = ""
    name, _, version = str(declared).partition("@")
    return version.split("+", 1)[0] if name == "pnpm" and version else PNPM_DEFAULT_VERSION


def _tool_version(command: list[str]) -> str | None:
    try:
        probe = subprocess.run([*command, "--version"], capture_output=True, text=True, timeout=30, cwd=ROOT,
                               env={**os.environ, "COREPACK_ENABLE_NETWORK": "0"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return probe.stdout.strip() if probe.returncode == 0 else None


def pnpm_command() -> list[str] | None:
    """Commande pnpm : `pnpm.cmd` du PATH sous Windows ; sous Linux, pnpm du PATH s'il a la version de
    `packageManager`, sinon `corepack pnpm`, qui applique cette version."""
    if sys.platform == "win32":
        found = shutil.which("pnpm.cmd")
        return [found] if found else None
    found = shutil.which("pnpm")
    if found and _tool_version([found]) == pnpm_required_version():
        return [found]
    corepack = shutil.which("corepack")
    if corepack:
        return [corepack, "pnpm"]
    return [found] if found else None


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
                          hash_limit_bytes: int | None = 1048576, *, models: set[str] | None = None) -> dict:
    """Conformité hors ligne du stockage Ollama au verrou versionné.

    Les blobs jusqu'à hash_limit_bytes sont rehachés (None : tous) ; au-delà, la taille est comparée.
    """
    lock_path = lock_path or MODELS_LOCK
    store = store or OLLAMA_MODELS_DIR
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    result: dict = {"status": "conform", "lock": str(lock_path), "lock_sha256": file_hash(lock_path),
              "hash_limit_bytes": hash_limit_bytes, "models": {}}
    for name, expected in lock["models"].items():
        if models is not None and name not in models:
            continue
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


def _profile_models(profile: dict) -> set[str]:
    llm = profile["llm"]
    return {llm["model"], llm.get("source_model", llm["model"])}


def profile_model_lock(profile: dict) -> dict:
    """Contrôle du verrou des modèles commun à doctor et pull-model : stockage Ollama comparé au verrou (blobs rehachés
    jusqu'au seuil de model_lock_conformity, tailles au-delà) et modèles du profil présents dans le verrou."""
    check = model_lock_conformity(models=_profile_models(profile))
    check["scope"] = "profile_source_and_served_models_only"
    check["profile_models_locked"] = all(name in check["models"] for name in _profile_models(profile))
    return check


def model_lock_differences(check: dict, profile: dict) -> str | None:
    """Écarts au verrou des seuls modèles du profil (source et servi) dans un contrôle profile_model_lock, en une phrase ;
    None s'ils sont conformes. Les autres modèles du verrou n'entrent pas dans ce contrôle (doctor juge également les seuls modèles du profil)."""
    used = _profile_models(profile)
    parts = []
    unlocked = sorted(used - set(check["models"]))
    if unlocked:
        parts.append(f"modèle du profil absent du verrou ({', '.join(unlocked)})")
    for name in sorted(used & set(check["models"])):
        model = check["models"][name]
        if model.get("status") != "conform":
            issues = sorted({str(issue.get("issue", "?")) for issue in model.get("issues", [])})
            parts.append(f"{name} ({', '.join(issues) or model.get('status')})")
    return " ; ".join(parts) or None


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


RUNNING_STATES = {"starting", "running", "stopping"}


def _read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _utc(value: Any) -> datetime:
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


READABLE = ("gpu", "cpu_only")


def latest_discovery(runtime: dict, provision: dict | None, *, keep_running: bool = True,
                     libraries: dict | None = None) -> dict | None:
    """Découverte la plus récente : celle de l'instance (runtime.json) ou celle de `provision` (DISCOVERY_MANIFEST).

    Une instance en marche garde la sienne, qui a fixé son mode (`keep_running`) ; sinon la plus récente des deux fait
    foi, comme pour le prochain démarrage. Avec `libraries` (bibliothèques actuelles), une découverte consignée avec
    d'autres bibliothèques GPU est écartée : elle ne dit plus ce que découvrira le prochain démarrage (revue J11
    runtime-3). Une découverte illisible plus récente qu'une découverte lisible encore valable ne la masque pas : la
    lisible est retenue, et l'illisible est rappelée dans `superseded`.
    """
    candidates = []
    recorded = runtime.get("accelerator")
    if isinstance(recorded, dict) and isinstance(recorded.get("discovery"), dict):
        candidates.append({"source": "runtime", "utc": recorded.get("utc"), "instance_id": runtime.get("instance_id"),
                           **{key: recorded["discovery"].get(key) for key in ("status", "devices", "dropped")},
                           **({"libraries": recorded["libraries"]} if isinstance(recorded.get("libraries"), dict) else {})})
        if keep_running and runtime.get("status") in RUNNING_STATES:
            return candidates[0]
    if provision and provision.get("status"):
        candidates.append({"source": "provision", "utc": provision.get("utc"), "log": provision.get("log"),
                           **{key: provision.get(key) for key in ("status", "devices", "dropped")},
                           **({"error": provision["error"]} if provision.get("error") else {}),
                           **({"libraries": provision["libraries"]} if isinstance(provision.get("libraries"), dict)
                              else {})})
    if libraries is not None:
        current = libraries_signature(libraries)
        candidates = [item for item in candidates
                      if "libraries" not in item or libraries_signature(item["libraries"]) == current]
    latest = max(candidates, key=lambda item: _utc(item.get("utc")), default=None)
    readable = [item for item in candidates if item.get("status") in READABLE]
    if latest is not None and latest.get("status") not in READABLE and readable:
        kept = max(readable, key=lambda item: _utc(item.get("utc")))
        return {**kept, "superseded": {key: latest[key] for key in ("source", "utc", "log", "error") if key in latest}}
    return latest


def accelerator_state(check: dict) -> str:
    """État de la rubrique « calcul » (conception J11 §9.2, revue M2, W025), dans l'ordre de priorité.

    Une anomalie de résidence prime ; puis le CPU imposé par le profil ; puis l'instance en marche sur GPU (repli,
    usage) ; enfin le mode CPU résolu, ou attendu au prochain démarrage, d'après sa raison et les indices du poste.
    """
    usage = check.get("usage") or []
    running, mode, reason = check.get("running"), check.get("mode"), check.get("reason")
    # Bibliothèques telles que l'instance en marche les a vérifiées à son démarrage, sinon telles qu'elles sont.
    host, libraries = check.get("host") or {}, check.get("instance_libraries") or check.get("libraries") or {}
    missing = bool(libraries.get("required") and not libraries.get("provisioned"))
    current = check.get("libraries") or {}
    if running and mode == "cpu" and any(item.get("size_vram") for item in usage):
        return "anomaly_gpu_in_cpu_mode"
    if check.get("requested") == "cpu":
        return "cpu_legacy" if check.get("requested_source") == "legacy_num_gpu" else "cpu_imposed"
    if running and mode == "cpu" and (check.get("next_start") or {}).get("mode") == "gpu":
        # Complément provisionné après le démarrage : l'instance calcule sur CPU, le prochain démarrage sur GPU.
        return "gpu_pending"
    if running and mode == "cpu" and (check.get("instance_predates_accelerator") or check.get("discovery_stale")):
        # Instance démarrée avant l'accélération GPU, ou avant le dernier changement des bibliothèques : le mode du
        # prochain démarrage reste à découvrir, avec les bibliothèques actuelles.
        if current.get("required") and not current.get("provisioned"):
            return "gpu_libraries_missing" if check.get("requested") == "auto" else "gpu_requested_unavailable"
        return "discovery_pending"
    if running and mode == "gpu":
        model = next((item for item in usage if item.get("model") == check.get("model")), None)
        if check.get("fallback"):
            return "gpu_fallback"
        if model is not None and not model.get("size_vram"):
            return "gpu_mode_on_cpu"
        if reason == "gpu_trial":
            return "gpu_trial"
        if model is None:
            return "gpu_ready"
        return "gpu_in_use" if model["size_vram"] >= model.get("size", 0) else "gpu_partial"
    if mode is None:
        if missing:
            return "gpu_libraries_missing" if check.get("requested") == "auto" else "gpu_requested_unavailable"
        return "discovery_pending"
    if mode == "gpu":
        return "gpu_pending"
    if reason == "discovery_unreadable":
        return "discovery_unreadable"
    if reason == "gpu_libraries_unverified":
        return "gpu_libraries_unverified"
    if check.get("requested") == "gpu":
        return "gpu_requested_unavailable"
    if reason == "no_gpu_discovered":
        if missing:
            return "gpu_libraries_missing"
        if host.get("jetpack") and libraries.get("provisioned"):
            return "gpu_rejected_by_ollama"
        if host.get("l4t_major") is not None and not host.get("jetpack"):
            return "jetson_unsupported"
        if host.get("nvidia_kernel_driver") or host.get("windows_nvcuda"):
            # Kit sans bibliothèques CUDA (--without-gpu) : la cause est l'installation, pas le pilote.
            return "cuda_libraries_absent" if cuda_libraries_removed(libraries) else "nvidia_not_retained"
        return "cpu_no_gpu"
    if reason == "gpu_library_not_retained" and any(is_nvidia(item) for item in (check.get("discovery") or {}).get(
            "devices") or []):
        # GPU NVIDIA écarté par CUDA (pilote, capacité) et vu seulement par Vulkan, actif par défaut dans Ollama 0.35.0.
        return "nvidia_not_retained"
    return {"gpu_library_not_retained": "gpu_not_retained", "gpu_mixed_libraries": "gpu_mixed_libraries",
            "gpu_path_not_qualified": "gpu_path_not_qualified",
            "gpu_unified_memory_not_qualified": "gpu_unified_memory_not_qualified"}.get(str(reason), "cpu_no_gpu")


def accelerator_check(profile: dict, runtime: dict, loaded_models: list[dict] | None,
                      diagnostics: dict | None) -> dict:
    """Contrôle « calcul » de doctor (D01.4, W024, W025), en lecture seule.

    Sources : mode et découverte de l'instance (runtime.json), sinon découverte de `provision`, la plus récente ;
    bibliothèques comparées au manifeste local ; occupation du modèle lue dans /api/ps et repli éventuel dans
    /api/v1/diagnostics, tous deux déjà interrogés par doctor. Sans instance en marche, le mode est celui qu'aurait le
    prochain démarrage avec le profil et les bibliothèques actuels. Une découverte faite avec d'autres bibliothèques GPU
    que celles d'aujourd'hui est écartée (`discovery_stale`) ; une instance en marche démarrée avant l'accélération GPU
    calcule sur CPU et reste surveillée (résidence du modèle), son mode se décidant à son redémarrage.
    """
    signals = host_signals()
    # Mémoire totale du poste, qui décide d'un GPU intégré : la même valeur fonde la décision et le message.
    memory = signals.get("memory_total_mib")
    recorded = runtime.get("accelerator") if isinstance(runtime.get("accelerator"), dict) else None
    running = bool(recorded) and runtime.get("status") in RUNNING_STATES
    # Instance en marche démarrée avant l'accélération GPU (runtime.json sans clé accelerator) : son API envoie
    # num_gpu: 0, elle calcule donc sur CPU ; le superviseur consigne le mode avant de passer à running.
    predates = recorded is None and runtime.get("status") == "running"
    requested = ({key: recorded[key] for key in ("requested", "requested_source")} if running and recorded
                 else profile_accelerator(profile))
    complement = None
    version = None
    try:
        lock = _artifact_lock()
        manifest = _read_json(ROOT / ".runtime/manifests/artifacts.json") or {}
        libraries = verified_libraries(lock, manifest, signals, root=ROOT)
        version = ollama_version(lock, signals.get("platform"))
        entries = entries_for_host(lock["groups"].get(GPU_GROUP, []), signals)
        if entries:
            # Voie qualifiée ou non (W025 P4) : seule une voie qualifiée calcule sur le GPU en auto.
            complement = {"file": entries[0]["url"].rsplit("/", 1)[-1], "size": entries[0].get("size"),
                          "extracted_size": entries[0].get("extracted_size"), "variant": entries[0].get("variant"),
                          "qualified": (signals.get("platform"), entries[0].get("variant")) in QUALIFIED_GPU_PATHS}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        libraries = {"entry": None, "required": False, "provisioned": False, "variants": {},
                     "error": f"{type(exc).__name__} : {exc}"[:300]}
    provision_record = _read_json(ROOT / DISCOVERY_MANIFEST)
    discovery = latest_discovery(runtime, provision_record, libraries=libraries)
    decision: dict | None = None
    next_start: dict | None = None
    # Découverte consignée avec d'autres bibliothèques GPU que celles d'aujourd'hui : écartée, refaite au prochain
    # démarrage (pour une instance en marche, sa propre découverte comparée aux bibliothèques actuelles).
    stale = discovery is None and latest_discovery(runtime, provision_record) is not None
    if running and recorded:
        decision = {key: recorded.get(key) for key in ("mode", "reason", "device", "variant", "qualified")}
        latest = latest_discovery(runtime, provision_record, keep_running=False, libraries=libraries)
        if latest:
            next_start = resolve_mode(profile_accelerator(profile), latest, libraries, signals.get("platform"),
                                      memory_total_mib=memory)
        stale = (isinstance(recorded.get("libraries"), dict)
                 and libraries_signature(recorded["libraries"]) != libraries_signature(libraries))
    elif predates:
        decision = {"mode": "cpu", "reason": "legacy_profile_cpu", "device": None, "variant": None, "qualified": False}
        latest = latest_discovery(runtime, provision_record, keep_running=False, libraries=libraries)
        if latest:
            next_start = resolve_mode(requested, latest, libraries, signals.get("platform"), memory_total_mib=memory)
    elif discovery:
        decision = resolve_mode(requested, discovery, libraries, signals.get("platform"), memory_total_mib=memory)
    preview = None
    if requested["requested"] == "cpu" and discovery:
        # Ce que donnerait llm.accelerator: auto : fonde la proposition faite à un profil antérieur (W025 P5).
        preview = resolve_mode({"requested": "auto", "requested_source": "profile"}, discovery, libraries,
                               signals.get("platform"), memory_total_mib=memory)
    usage = None if loaded_models is None else [
        {"model": item.get("name"), "size": item.get("size") or 0, "size_vram": item.get("size_vram") or 0,
         "processor": processor_label(int(item.get("size") or 0), int(item.get("size_vram") or 0))}
        for item in loaded_models]
    reported = (diagnostics or {}).get("llm_accelerator") if isinstance(diagnostics, dict) else None
    check: dict[str, Any] = {
        **requested, "running": running or predates, "host": signals, "libraries": libraries, "complement": complement,
        "ollama_version": version, "discovery": discovery, **(decision or {"mode": None, "reason": None}),
        "if_auto": preview, "fallback": reported.get("fallback") if isinstance(reported, dict) else None,
        "usage": usage, "model": profile["llm"]["model"], "keep_alive": profile["llm"].get("keep_alive", "10m"),
        "discovery_stale": stale}
    if running and recorded:
        check.update(instance_libraries=recorded.get("libraries"), next_start=next_start)
    elif predates:
        check.update(instance_predates_accelerator=True, next_start=next_start)
    check["state"] = accelerator_state(check)
    return check


def doctor(profile_path: Path) -> dict:
    import httpx

    profile = load_profile(profile_path)
    directory = data_path(profile)
    available = psutil.virtual_memory().available / 1048576
    result: dict = {"utc": datetime.now(UTC).isoformat(),
              "platform": "Windows native, no WSL/Docker" if sys.platform == "win32" else platform_label(),
              "python": {"version": sys.version.split()[0], "executable": sys.executable},
              "resources": {"available_mib": available,
                            "disk_free_mib": shutil.disk_usage(ROOT).free / 1048576},
              "profile_sha256": file_hash(profile_path), "data_dir": str(directory), "checks": {},
              "runtime": status(profile_path)}
    checks = result["checks"]
    try:
        checks["qdrant_storage"] = {"status": "valid", "path": str(qdrant_data_path(profile, directory)),
                                    "native_storage_path_limit": 57 if sys.platform == "win32" else None}
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
        checks["model_lock"] = profile_model_lock(profile)
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
    checks["tesseract_binary"] = (ROOT / native_executable(profile["pdf"]["tesseract_cmd"])).is_file()
    if sys.platform != "win32":
        # Arrêt des enfants à la mort du superviseur (PR_SET_PDEATHSIG) : outil util-linux vérifié, pas supposé.
        from .posix_process import setpriv_executable

        try:
            checks["parent_death_signal"] = {"status": "available", "setpriv": setpriv_executable()}
        except RuntimeError as exc:
            checks["parent_death_signal"] = {"status": "missing", "reason": str(exc)}
    result["node_tools"] = {}
    if sys.platform == "win32":
        tools = [("node", shutil.which("node.exe")), ("pnpm", shutil.which("pnpm.cmd"))]
    else:
        tools = [("node", shutil.which("node")), ("pnpm", shutil.which("pnpm")), ("corepack", shutil.which("corepack"))]
    for name, command in tools:
        if command:
            probe = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15,
                                   env={**os.environ, "COREPACK_ENABLE_NETWORK": "0"})
            result["node_tools"][name] = {"path": command, "version": probe.stdout.strip(), "exit_code": probe.returncode}
        else:
            result["node_tools"][name] = {"status": "absent_from_path"}
    if sys.platform != "win32":
        selected = pnpm_command()
        result["node_tools"]["pnpm_selected"] = {"command": selected, "required_version": pnpm_required_version()}
    result["services"] = {}
    diagnostics: dict | None = None
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
                payload = response.json()
                checks["index_consistency"] = payload.get("index_consistency") or {
                    "status": "not_exposed",
                    "reason": "GET /api/v1/diagnostics does not expose active-generation Qdrant points vs SQLite chunks",
                    "diagnostics_keys": sorted(payload)}
                diagnostics = payload
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                checks["index_consistency"] = {"status": "diagnostics_unavailable", "reason": type(exc).__name__}
    checks["llm_model_diagnosis"] = llm_model_diagnosis(checks["llm_model_files"], checks["llm_model"])
    try:
        checks["accelerator"] = accelerator_check(profile, runtime, result.get("loaded_models"), diagnostics)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        checks["accelerator"] = {"state": "check_failed", "error": f"{type(exc).__name__} : {exc}"[:300]}
    # Ces diagnostics distinguent présence des fichiers, disponibilité et recette.
    result["qualification"] = "NOT_RUN: doctor does not prove an end-to-end answer"
    from .verdict import doctor_verdict

    return {"verdict": doctor_verdict(result), **result}


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
    expected = json.loads(MODELS_LOCK.read_text(encoding="utf-8"))["models"].get(name, {})
    digest = expected.get("manifest_sha256")
    if (not isinstance(digest, str) or len(digest) != 64 or set(digest) - set("0123456789abcdef")
            or model.get("digest") != digest):
        raise RuntimeError("Digest Ollama différent ou absent du verrou ; aucun manifeste provisionné écrit")
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


def model_pull_environment(profile: dict, directory: Path, profile_path: Path) -> dict[str, str]:
    """Réseau du provisionnement seul ; les services du poste restent hors ligne."""
    env = environment(profile, directory, profile_path)
    if sys.platform == "linux":
        # Go 1.26 : le résolveur système respecte getaddrinfo sur un hôte sans route IPv6.
        # Valeur propre au processus, pas héritée d'un GODEBUG utilisateur ni propagée à up.
        env["GODEBUG"] = "netdns=cgo"
    return env


def pull_model(profile_path: Path, offline: bool = False) -> dict:
    import httpx

    profile = load_profile(profile_path)
    profile = {**profile, "llm": {**profile["llm"], "base_url": "http://127.0.0.1:11444"}}
    llm = profile["llm"]
    source_name = llm.get("source_model", llm["model"])
    with port_probe() as probe:
        probe.bind(("127.0.0.1", 11444))
    paths = native_paths()
    directory = ROOT / ".runtime/provision-service"
    env = model_pull_environment(profile, directory, profile_path)
    with ProcessJob() as job:
        child = job.launch([str(paths["ollama"]), "serve"], cwd=ollama_working_directory(paths["ollama"]), env=env,
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
        send_owned_console_interrupt(child, "ollama")
        try:
            child.wait(30)
        except TimeoutError:
            print("Service de provisionnement : arrêt forcé ciblé du Job, aucune inférence active.", flush=True)
    # Service arrêté, fichiers définitifs : un tirage ou une dérivation qui ne reproduit pas le stockage verrouillé des
    # modèles du profil échoue ici, au lieu d'être découvert ensuite par doctor.
    differences = model_lock_differences(profile_model_lock(profile), profile)
    if differences:
        raise RuntimeError(f"Stockage Ollama différent du verrou {MODELS_LOCK} après pull-model : {differences}. "
                           "Contrôle limité aux modèles du profil, avec les critères de doctor ; les fichiers du stockage "
                           "sont conservés pour diagnostic.")
    return result["model"]


# Service Ollama de provisionnement (dossier de pull_model) ; la sonde de découverte y tient son propre journal.
PROVISION_SERVICE = ".runtime/provision-service"


def _artifact_lock() -> dict:
    return json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))


def gpu_complement(profile: dict, only: str | None, signals: dict) -> tuple[frozenset[str], list[dict]]:
    """Complément GPU officiel d'Ollama pour ce poste (W025 P2) : groupes à sauter et entrées du poste.

    Le complément d'un Jetson R35 ou R36 est retenu d'office, sauf profil en calcul CPU (explicite ou forme antérieure) ;
    `--only ollama-gpu` le télécharge quel que soit le profil. Le choix est annoncé avant tout téléchargement.
    """
    if only not in (None, GPU_GROUP):
        return frozenset(), []
    entries = entries_for_host(_artifact_lock()["groups"].get(GPU_GROUP, []), signals)
    if not entries:
        return frozenset(), []
    requested = profile_accelerator(profile)
    if requested["requested"] == "cpu" and only != GPU_GROUP:
        names = ", ".join(entry["url"].rsplit("/", 1)[-1] for entry in entries)
        form = ("llm.num_gpu: 0 ; remplacez cette ligne par llm.accelerator: auto pour utiliser le GPU"
                if requested["requested_source"] == "legacy_num_gpu" else "llm.accelerator: cpu")
        print(f"Accélération GPU : complément {names} non téléchargé, le profil impose le calcul CPU ({form}).",
              flush=True)
        return frozenset({GPU_GROUP}), entries
    for entry in entries:
        print(f"Accélération GPU : {jetson_label(signals) or signals.get('platform')} détecté ; complément officiel "
              f"{entry['url'].rsplit('/', 1)[-1]} retenu (bibliothèques {entry.get('variant')}).", flush=True)
    return frozenset(), entries


def record_provision_discovery(profile: dict, profile_path: Path, signals: dict, *, method: str) -> dict:
    """Découverte des GPU confirmée par Ollama lui-même, consignée dans DISCOVERY_MANIFEST et annoncée.

    `pull_model` : dernier bloc du journal du service de pull-model, qui vient de s'arrêter ; `probe` : sonde
    (`probe_discovery`). Une sonde en échec n'interrompt pas le provisionnement : l'échec est consigné et la découverte
    sera relevée au prochain démarrage de l'instance. Les bibliothèques GPU vérifiées au même moment sont consignées :
    doctor écarte une découverte faite avec d'autres bibliothèques que celles du poste.
    """
    directory = ROOT / PROVISION_SERVICE
    lock = _artifact_lock()
    version = ollama_version(lock, signals.get("platform"))
    error = None
    if method == "pull_model":
        log = directory / "ollama-pull.log"
        discovery = read_discovery(log)
    else:
        log = directory / "ollama-probe.log"
        try:
            discovery = probe_discovery(profile, profile_path.resolve(), directory, log, version=version)
        except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
            # SubprocessError : arrêt de la sonde par l'assistant console_signal hors délai sous Windows.
            discovery = {"status": "unreadable", "devices": [], "dropped": []}
            error = f"{type(exc).__name__} : {exc}"[:300]
    manifest_path = ROOT / ".runtime/manifests/artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    libraries = verified_libraries(lock, manifest, signals, root=ROOT)
    record = discovery_record(discovery, source="provision", method=method, log=log.relative_to(ROOT).as_posix(),
                              version=version, signals=signals, libraries=libraries)
    if error:
        record["error"] = error
    write_json_atomic(ROOT / DISCOVERY_MANIFEST, record)
    if discovery["status"] == "unreadable":
        detail = f" ; {error}" if error else ""
        print(f"Découverte d'Ollama non lue dans son journal ({record['log']}{detail}) : elle sera relevée au prochain "
              f"démarrage ({launcher_command('up')}).", flush=True)
        return record
    if discovery["status"] == "gpu":
        found = " ; ".join(describe_device(device, device_variant(device)) for device in discovery["devices"])
        print(f"Découverte d'Ollama : {found}.", flush=True)
    else:
        print("Découverte d'Ollama : aucun GPU utilisable, calcul sur CPU.", flush=True)
    decision = resolve_mode(profile_accelerator(profile), discovery, libraries, signals.get("platform"),
                            memory_total_mib=signals.get("memory_total_mib"))
    if decision["mode"] == "gpu":
        print(f"Génération attendue au prochain démarrage : GPU, {describe_device(decision['device'], decision['variant'])} "
              f"; {reason_text(decision)}.", flush=True)
    else:
        print(f"Génération attendue au prochain démarrage : CPU, {reason_text(decision)}.", flush=True)
    return record


def provision(profile_path: Path, only: str | None = None, offline: bool = False, skip_model: bool = False):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Provisionnement applicatif requis sous Python3.12 isolé")
    # Profil et indices du poste servent au complément GPU et à la confirmation de la découverte d'Ollama ; un
    # provisionnement limité à un autre groupe ne lit pas le profil, comme avant.
    profile: dict | None = None
    signals: dict | None = None
    if only in (None, "ollama", GPU_GROUP, "qwen-tokenizer"):
        profile = load_profile(profile_path)
        if only != "qwen-tokenizer":
            signals = host_signals()
    uv = ROOT / ".runtime/bootstrap/bin" / executable_name("uv")
    if not only:
        subprocess.run([str(uv), "sync", "--locked", "--python", sys.executable, "--no-python-downloads",
                        "--cache-dir", str(ROOT / ".runtime/cache/uv"), *(["--offline"] if offline else [])],
                       cwd=ROOT, check=True)
        node_env = {**os.environ, "COREPACK_ENABLE_NETWORK": "0", "NEXT_TELEMETRY_DISABLED": "1"}
        pnpm = pnpm_command()
        if not pnpm:
            raise FileNotFoundError("pnpm10.34.1 requis ; doctor indique le prérequis manquant")
        subprocess.run([*pnpm, "install", "--frozen-lockfile", *(["--offline"] if offline else [])],
                       cwd=ROOT / "apps/web", env=node_env, check=True)
    skip_groups: frozenset[str] = frozenset()
    complements: list[dict] = []
    if profile is not None and signals is not None:
        skip_groups, complements = gpu_complement(profile, only, signals)
    tokenizer_model_id = (profile or {}).get("llm", {}).get("tokenizer_model_id", "Qwen/Qwen3.5-4B")
    provision_artifacts(only, offline=offline, skip_groups=skip_groups, signals=signals,
                        tokenizer_model_id=tokenizer_model_id)
    if not only:
        assert profile is not None
        from .provisioning import tesseract
        tesseract(profile, offline=offline)
        # Même condition que le premier bloc, qui lève FileNotFoundError si pnpm manque.
        assert pnpm is not None
        subprocess.run([*pnpm, "run", "build"], cwd=ROOT / "apps/web",
                       env={**node_env, "NODE_OPTIONS": "--max-old-space-size=2048"}, check=True)
    if not only and not skip_model:
        assert profile is not None and signals is not None
        if offline:
            llm = profile["llm"]
            source = ROOT / llm.get("source_model_manifest", SOURCE_MODEL_MANIFEST)
            if not source.is_file():
                raise FileNotFoundError("Modèle Ollama non provisionné pour installation offline")
            if not (ROOT / llm.get("model_manifest", SOURCE_MODEL_MANIFEST)).is_file():
                # La dérivation texte seul est locale : elle reste permise hors ligne.
                model = pull_model(profile_path, offline=True)
                record_provision_discovery(profile, profile_path, signals, method="pull_model")
                return model
            # Modèle déjà présent hors ligne : aucun service de pull-model ne tourne, la sonde ci-dessous consigne la
            # découverte faite avec les bibliothèques que provision vient d'extraire (revue J11 runtime-3).
        else:
            model = pull_model(profile_path)
            record_provision_discovery(profile, profile_path, signals, method="pull_model")
            return model
    if not only or only == "ollama" or (only == GPU_GROUP and complements):
        # Sans service de pull-model (--skip-model, modèle présent hors ligne, --only ollama ou ollama-gpu), une sonde
        # confirme la découverte ; rien à confirmer pour un complément sans objet sur ce poste.
        assert profile is not None and signals is not None
        record_provision_discovery(profile, profile_path, signals, method="probe")
    return {"artifacts": "verified", "model": "not_requested" if skip_model else "unchanged"}


def status_report(profile_path: Path) -> dict:
    """État de l'instance, avec une ligne `generation` sur le mode de génération consigné à son démarrage (W024)."""
    from .verdict import generation_text

    state = status(profile_path)
    accelerator = state.get("accelerator")
    if isinstance(accelerator, dict) and accelerator.get("mode") in ("gpu", "cpu"):
        text = generation_text(accelerator)
        if state.get("status") in RUNNING_STATES:
            line = text[0].upper() + text[1:] + "."
            if accelerator["mode"] == "gpu":
                line += f" Un repli sur CPU après un échec du GPU est signalé par {launcher_command('doctor')}."
        else:
            line = f"Dernière instance : {text}."
        state["generation"] = line
    return state


def open_workspace(profile_path: Path, *, launch: bool = True) -> dict[str, Any]:
    """Demande à l'instance un lien d'ouverture à usage unique (W011) et l'ouvre dans le navigateur par défaut."""
    import httpx

    profile = load_profile(profile_path)
    current = status(profile_path)
    if current.get("status") != "running":
        raise RuntimeError("Instance non démarrée : lancer d'abord " + launcher_command("up"))
    headers = control_headers(data_path(profile))
    if not headers:
        raise RuntimeError("Jeton de contrôle de l'instance absent : redémarrer avec " + launcher_command("down") + " puis up")
    origin, verify = app_origin(profile)
    with httpx.Client(timeout=10, trust_env=False, verify=verify) as client:
        response = client.post(origin + "/api/v1/admin/session-links", headers=headers)
        response.raise_for_status()
        link = response.json()
    url = origin + link["path"]
    if launch:
        if sys.platform == "win32":
            os.startfile(url)
        else:
            import webbrowser

            # Navigateur par défaut de la session (xdg-open sous Linux) : URL de boucle locale, comme sous Windows. Le lien
            # figure dans la ligne de commande de xdg-open et du navigateur et ne sert plus une fois consommé (W023).
            # Sans navigateur, le lien n'est pas affiché.
            if not webbrowser.open(url, new=2):
                raise RuntimeError("Aucun navigateur disponible dans cette session : « "
                                   + launcher_command("open --no-browser") + " » affiche le lien à usage unique")
        # Le lien est un secret à usage unique : il n'est ni affiché ni écrit dans un rapport quand le navigateur l'a reçu.
        return {"opened_in_browser": True, "expires_in_seconds": link["expires_in_seconds"], "single_use": True}
    return {"opened_in_browser": False, "url": url, "expires_in_seconds": link["expires_in_seconds"], "single_use": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["provision", "doctor", "up", "status", "logs", "down", "_serve", "pull-model", "backup", "restore", "verify", "open", "init-profile", "selftest"])
    parser.add_argument("--profile", type=Path, help="Profil utilisateur explicite, exclusif de --model")
    parser.add_argument("--model", choices=list(MODEL_PROFILES), help="Modèle du profil livré (défaut : qwen3.5:2b)")
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
        args.profile = model_profile_path(args.profile, args.model)
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
        elif args.command == "selftest":
            from .selftest import selftest
            result = selftest(args.profile)
        elif args.command == "open":
            result = open_workspace(args.profile, launch=not args.no_browser)
        elif args.command == "up":
            result = start(args.profile)
        elif args.command == "down":
            result = stop(args.profile)
        elif args.command == "status":
            result = status_report(args.profile)
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
