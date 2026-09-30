"""Supervision persistante du poste Windows, avec propriété et stockage explicites."""

from __future__ import annotations

import json
import msvcrt
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil
import yaml

from .artifacts import ROOT, file_hash, read_json_atomic, write_json_atomic
from .resources import ResourceGovernor
from .windows_process import OwnedProcess, WindowsJob


def load_profile(path: Path) -> dict:
    from urllib.parse import urlsplit

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != 2:
        raise ValueError("Profil version2 requis")
    if config["app"]["host"] != "127.0.0.1" or config["llm"]["num_gpu"] != 0:
        raise ValueError("Le runtime exige loopback et CPU")
    for value in (config["llm"]["base_url"], config["qdrant"]["url"]):
        url = urlsplit(value)
        if (url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port
                or url.username is not None or url.password is not None
                or url.path not in {"", "/"} or url.query or url.fragment):
            raise ValueError("Les services natifs exigent une URL HTTP loopback avec port explicite")
    return config


def data_path(profile: dict) -> Path:
    return (ROOT / os.environ.get("RAG_DATA_DIR", profile["app"]["data_dir"])).resolve()


def read_state(directory: Path) -> dict:
    path = directory / "control/runtime.json"
    try:
        return read_json_atomic(path)
    except FileNotFoundError:
        return {"status": "stopped"}


def process_identity_valid(identity: dict) -> bool:
    try:
        process = psutil.Process(identity["pid"])
        return (abs(process.create_time() - identity["created_at"]) < 0.01
                and Path(process.exe()).resolve() == Path(identity["executable"]).resolve())
    except (psutil.Error, KeyError, OSError):
        return False


def check_ports(ports: list[int]) -> None:
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(f"Port {port} occupé ; aucun service existant ne sera arrêté.") from exc


def environment(profile: dict, directory: Path, profile_path: Path) -> dict[str, str]:
    # Les enfants reçoivent les variables Windows utiles, pas les identifiants
    # de services ni les réglages Python/Ollama d'autres projets du poste.
    names = {"systemroot", "windir", "systemdrive", "comspec", "path", "pathext",
             "temp", "tmp", "userprofile", "appdata", "localappdata", "programdata",
             "programfiles", "programfiles(x86)", "number_of_processors",
             "processor_architecture", "processor_identifier"}
    env = {key: value for key, value in os.environ.items() if key.lower() in names}
    env.update({
        "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "RAG_PROFILE": str(profile_path.resolve()),
        "RAG_DATA_DIR": str(directory), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HOME": str(ROOT / ".runtime/cache/huggingface"),
        "DOCLING_ARTIFACTS_PATH": str(ROOT / profile["pdf"]["artifacts_path"]),
        "TESSDATA_PREFIX": str(ROOT / profile["pdf"]["tessdata_dir"]),
        "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2", "NEXT_TELEMETRY_DISABLED": "1",
        "OLLAMA_HOST": profile["llm"]["base_url"].removeprefix("http://"),
        "OLLAMA_MODELS": str(ROOT / ".runtime/models/ollama"), "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_MAX_QUEUE": "2",
        "OLLAMA_CONTEXT_LENGTH": str(profile["llm"]["num_ctx"]), "OLLAMA_KEEP_ALIVE": "10m",
        "LLAMA_ARG_CACHE_RAM": str(profile["llm"].get("prompt_cache_mib", 256)),
        "LLAMA_ARG_CTX_CHECKPOINTS": str(profile["llm"].get("context_checkpoints_max", 2)),
    })
    return env


def wait_http(url: str, child: OwnedProcess, expected_version: str | None = None, timeout: float = 90):
    import httpx

    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=3, trust_env=False) as client:
        last = ""
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"Enfant terminé ({child.poll()}) avant disponibilité ; log {child.log_path}")
            try:
                response = client.get(url)
                if response.is_success:
                    payload = response.json() if "json" in response.headers.get("content-type", "") else response.text
                    if expected_version and payload.get("version") != expected_version:
                        raise RuntimeError("Version du service différente de l'artefact verrouillé")
                    return payload
                last = str(response.status_code)
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            time.sleep(0.25)
    raise TimeoutError(f"Disponibilité non atteinte : {url} ({last})")


def native_paths() -> dict[str, Path]:
    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    manifest = ROOT / ".runtime/manifests/artifacts.json"
    if not manifest.exists():
        raise FileNotFoundError("Artefacts non provisionnés ; exécuter rag.ps1 provision")
    records = json.loads(manifest.read_text(encoding="utf-8"))
    paths = {}
    for name in ["qdrant", "ollama"]:
        entry = lock["groups"][name][0]
        folder = ROOT / entry["extract_to"]
        matches = list(folder.rglob(name + ".exe"))
        if len(matches) != 1:
            raise FileNotFoundError(f"Binaire {name} Windows non provisionné ou ambigu")
        expected = {str((ROOT / item["path"]).resolve()): item["sha256"]
                    for item in records.get(name, [{}])[0].get("extracted_files", [])}
        binary = matches[0].resolve()
        if str(binary) not in expected or file_hash(binary) != expected[str(binary)]:
            raise ValueError(f"Empreinte du binaire {name} non conforme au manifeste local")
        paths[name] = matches[0]
    return paths


def qdrant_data_path(profile: dict, directory: Path) -> Path:
    configured = profile.get("qdrant", {}).get("storage_dir")
    path = (ROOT / configured).resolve() if configured else directory / "qdrant"
    # Snapshot recovery adds 202 characters for the locked collection schema,
    # more than the final payload index (175). Bound native paths, not Windows.
    if os.name == "nt" and len(str(path / "storage")) > 57:
        raise ValueError("Chemin Qdrant trop long pour le binaire Windows verrouillé : définir qdrant.storage_dir vers un dossier court distinct")
    return path


def acquire_qdrant_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / "native-runtime.lock").open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise RuntimeError("Une instance possède déjà ce stockage Qdrant") from None
    return handle


def write_qdrant_config(profile: dict, directory: Path, control: Path) -> Path:
    from urllib.parse import urlsplit

    qdrant_directory = qdrant_data_path(profile, directory)
    config = {"log_level": "INFO", "telemetry_disabled": True,
              "storage": {"storage_path": str(qdrant_directory / "storage"),
                          "snapshots_path": str(qdrant_directory / "snapshots"),
                          "performance": {"max_search_threads": 2, "optimizer_cpu_budget": 1}},
              "service": {"host": "127.0.0.1", "http_port": urlsplit(profile["qdrant"]["url"]).port,
                          "grpc_port": None, "enable_cors": False, "max_workers": 1}}
    path = control / "qdrant.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def send_owned_console_interrupt(child: OwnedProcess) -> bool:
    if not child.still_owned():
        return child.poll() is not None
    result = subprocess.run([sys.executable, "-m", "services.runtime.console_signal", str(child.pid)],
                            cwd=ROOT, capture_output=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    return result.returncode == 0


def supervise(profile_path: Path) -> int:
    from urllib.parse import urlsplit

    profile = load_profile(profile_path)
    directory = data_path(profile)
    control = directory / "control"
    control.mkdir(parents=True, exist_ok=True)
    # Byte-lock Windows conservé durant toute la vie du superviseur.
    lock = (control / "runtime.lock").open("a+b")
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        raise RuntimeError("Une instance possède déjà cette racine de données") from None
    self_process = psutil.Process()
    instance = uuid.uuid4().hex
    stop_path = control / f"shutdown-{instance}"
    api_stop = control / f"api-shutdown-{instance}"
    secret_path = control / "admin-token"
    secret_path.write_text(secrets.token_urlsafe(32), encoding="ascii")
    log_root = directory / "logs" / instance
    log_root.mkdir(parents=True, exist_ok=True)
    state = {"instance_id": instance, "status": "starting", "profile_path": str(profile_path.resolve()),
             "profile_sha256": file_hash(profile_path), "data_dir": str(directory),
             "supervisor": {"pid": os.getpid(), "created_at": self_process.create_time(),
                            "executable": self_process.exe()}, "services": {}, "shutdown_marker": str(stop_path),
             "app_url": f"http://127.0.0.1:{profile['app']['port']}", "stop_results": []}
    state_path = control / "runtime.json"
    job = WindowsJob()
    qdrant_lock = None
    try:
        ports = [profile["app"]["port"], urlsplit(profile["qdrant"]["url"]).port,
                 urlsplit(profile["llm"]["base_url"]).port]
        check_ports(ports)
        qdrant_lock = acquire_qdrant_lock(qdrant_data_path(profile, directory))
        from .source_manifest import capture
        source_manifest = capture()
        source_path = log_root / "source-manifest.json"
        write_json_atomic(source_path, source_manifest)
        state["source_manifest_path"] = str(source_path)
        state["source_fingerprint"] = source_manifest["source_fingerprint"]
        state["source_identity_kind"] = source_manifest["kind"]
        binaries = native_paths()
        env = environment(profile, directory, profile_path)
        qconfig = write_qdrant_config(profile, directory, control)
        state["qdrant_config_sha256"] = file_hash(qconfig)
        state["qdrant_data_dir"] = str(qdrant_data_path(profile, directory))
        write_json_atomic(state_path, state)
        qdrant = job.launch([str(binaries["qdrant"]), "--config-path", str(qconfig), "--disable-telemetry"],
                            cwd=ROOT, env=env, log_path=log_root / "qdrant.log")
        state["services"]["qdrant"] = qdrant.identity()
        write_json_atomic(state_path, state)
        wait_http(profile["qdrant"]["url"] + "/healthz", qdrant)
        ollama = job.launch([str(binaries["ollama"]), "serve"], cwd=ROOT, env=env,
                            log_path=log_root / "ollama.log")
        state["services"]["ollama"] = ollama.identity()
        write_json_atomic(state_path, state)
        wait_http(profile["llm"]["base_url"] + "/api/version", ollama, "0.35.0")
        env["RAG_SHUTDOWN_MARKER"] = str(api_stop)
        env["RAG_CONTROL_TOKEN"] = secret_path.read_text(encoding="ascii")
        api = job.launch([sys.executable, "-m", "services.runtime.api_entry"], cwd=ROOT, env=env,
                         log_path=log_root / "api.log")
        state["services"]["api"] = api.identity()
        write_json_atomic(state_path, state)
        state["http_health"] = wait_http(state["app_url"] + "/api/v1/health", api, timeout=120)
        state["status"] = "running"
        write_json_atomic(state_path, state)
        governor = ResourceGovernor({**profile, "app": {**profile["app"], "data_dir": str(directory)}})
        with (log_root / "resources.jsonl").open("a", encoding="utf-8") as trace:
            while not stop_path.exists():
                dead = [name for name, identity in state["services"].items() if not process_identity_valid(identity)]
                if dead:
                    raise RuntimeError("Service arrêté : " + ", ".join(dead))
                sample = governor.snapshot()
                sample["owned_processes"] = []
                for child in self_process.children(recursive=True):
                    try:
                        memory = child.memory_info()
                        sample["owned_processes"].append({"pid": child.pid, "working_set_mib": memory.rss / 1048576,
                                                          "private_mib": getattr(memory, "private", memory.rss) / 1048576})
                    except psutil.Error:
                        continue
                trace.write(json.dumps(sample) + "\n")
                trace.flush()
                time.sleep(1)
        state["status"] = "stopping"
        write_json_atomic(state_path, state)
        api_stop.touch()
        try:
            code = api.wait(timeout=180)
            state["stop_results"].append({"service": "api", "mode": "cooperative_marker", "exit_code": code})
        except TimeoutError:
            state["stop_results"].append({"service": "api", "mode": "forced_job_close_after_stop_timeout"})
        for name, child in [("ollama", ollama), ("qdrant", qdrant)]:
            sent = send_owned_console_interrupt(child)
            try:
                code = child.wait(timeout=30)
                state["stop_results"].append({"service": name, "mode": "console_sigint" if sent else "already_exited", "exit_code": code})
            except TimeoutError:
                state["stop_results"].append({"service": name, "mode": "forced_job_close_after_stop_timeout"})
        state["status"] = "stopped"
        return 0
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = f"{type(exc).__name__}: {exc}"
        print(state["error"], flush=True)
        return 1
    finally:
        job.close()
        if qdrant_lock is not None:
            qdrant_lock.close()
        write_json_atomic(state_path, state)
        secret_path.unlink(missing_ok=True)
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


def start(profile_path: Path) -> dict:
    profile = load_profile(profile_path)
    directory = data_path(profile)
    qdrant_data_path(profile, directory)
    previous = read_state(directory)
    if process_identity_valid(previous.get("supervisor", {})):
        if previous.get("profile_sha256") != file_hash(profile_path):
            raise RuntimeError("Instance existante avec profil différent : down puis up pour appliquer la configuration")
        return previous
    control = directory / "control"
    control.mkdir(parents=True, exist_ok=True)
    log = (control / "supervisor-start.log").open("ab")
    try:
        supervisor_process = subprocess.Popen(
            [sys.executable, "-m", "services.runtime.cli", "_serve", "--profile", str(profile_path.resolve())],
            cwd=ROOT, env=environment(profile, directory, profile_path),
            stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        log.close()
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        current = read_state(directory)
        if current.get("instance_id") != previous.get("instance_id"):
            if current.get("status") == "running":
                return current
            if current.get("status") == "failed":
                raise RuntimeError(current.get("error"))
        exit_code = supervisor_process.poll()
        if exit_code is not None:
            raise RuntimeError(f"Superviseur terminé ({exit_code}) avant disponibilité ; "
                               f"log {control / 'supervisor-start.log'}")
        time.sleep(0.25)
    raise TimeoutError("Le superviseur n'a pas atteint son état running ; conserver le log de démarrage")


def stop(profile_path: Path) -> dict:
    directory = data_path(load_profile(profile_path))
    state = read_state(directory)
    if not process_identity_valid(state.get("supervisor", {})):
        return state
    marker = Path(state["shutdown_marker"]).resolve()
    if not marker.is_relative_to((directory / "control").resolve()):
        raise ValueError("Marqueur d'arrêt hors racine possédée")
    marker.touch()
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        current = read_state(directory)
        if current["status"] in {"stopped", "failed"}:
            return current
        time.sleep(0.25)
    raise TimeoutError("Arrêt toujours en attente ; aucun processus étranger n'a été touché")


def status(profile_path: Path) -> dict:
    state = read_state(data_path(load_profile(profile_path)))
    state["supervisor_identity_valid"] = process_identity_valid(state.get("supervisor", {}))
    state["profile_matches_current"] = state.get("profile_sha256") == file_hash(profile_path)
    for identity in state.get("services", {}).values():
        identity["identity_valid"] = process_identity_valid(identity)
    return state
