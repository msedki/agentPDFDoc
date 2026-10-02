import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
import yaml

from services.runtime.artifacts import ROOT, write_json_atomic
from services.runtime.supervisor import (
    RotatingJsonl,
    environment,
    issue_qdrant_key,
    load_profile,
    orphan_processes,
    port_states,
    qdrant_environment,
    status,
    supervisor_sample,
    write_qdrant_config,
)
from tests.unit.test_runtime_accelerator import jetson_libraries  # noqa: F401  (fixture réutilisée)


def test_resource_trace_rotation_bounds_size_and_keeps_whole_lines(tmp_path):
    path = tmp_path / "resources.jsonl"
    # Rotations rapprochées : les ouvertures transitoires (antivirus, indexation) sont reprises.
    with RotatingJsonl(path, max_bytes=1000, archives=2, busy_timeout_seconds=5) as trace:
        for index in range(200):
            trace.write({"index": index, "payload": "é" * 40})
    files = sorted(tmp_path.iterdir())
    assert [item.name for item in files] == ["resources.jsonl", "resources.jsonl.1", "resources.jsonl.2"]
    assert all(item.stat().st_size <= 1000 for item in files)
    lines = [json.loads(line) for item in (path.with_name("resources.jsonl.2"), path.with_name("resources.jsonl.1"), path)
             for line in item.read_bytes().decode("utf-8").splitlines()]
    indexes = [line["index"] for line in lines]
    assert indexes == list(range(indexes[0], 200)) and indexes[0] > 0
    assert b"\r\n" not in path.read_bytes()


@pytest.mark.skipif(sys.platform != "win32", reason="Lecteur Win32 sans FILE_SHARE_DELETE (pywin32)")
def test_rotation_blocked_by_reader_retries_without_losing_samples(tmp_path):
    import win32con
    import win32file

    path = tmp_path / "resources.jsonl"
    trace = RotatingJsonl(path, max_bytes=200, archives=1, busy_timeout_seconds=0.2, retry_after_seconds=0)
    trace.write({"index": 0, "payload": "x" * 150})
    # Lecteur type Get-Content : partage lecture/écriture, sans FILE_SHARE_DELETE.
    reader = win32file.CreateFile(str(path), win32con.GENERIC_READ,
                                  win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE, None,
                                  win32con.OPEN_EXISTING, win32con.FILE_ATTRIBUTE_NORMAL, None)
    try:
        trace.write({"index": 1, "payload": "x" * 150})
        assert not path.with_name("resources.jsonl.1").exists()
    finally:
        reader.Close()
    trace.busy_timeout_seconds = 5
    trace.write({"index": 2, "payload": "x" * 150})
    trace.close()
    archived = [json.loads(line)["index"] for line in path.with_name("resources.jsonl.1").read_text(encoding="utf-8").splitlines()]
    assert archived == [0, 1]
    assert [json.loads(line)["index"] for line in path.read_text(encoding="utf-8").splitlines()] == [2]


def test_supervisor_sample_reports_measures_without_lease_state(tmp_path):
    sample = supervisor_sample(psutil.Process(), tmp_path / "absent" / "data")
    for misleading in ("mode", "heavy_owner", "pause_requested", "auto_resume_ingestion", "host_reserve_mib"):
        assert misleading not in sample
    assert sample["source"] == "supervisor" and sample["available_mib"] > 0
    assert isinstance(sample["owned_processes"], list)


def _profile(tmp_path, monkeypatch):
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["app"]["data_dir"] = str(tmp_path / "données")
    path = tmp_path / "profil.yaml"
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return path, tmp_path / "données"


@pytest.mark.parametrize("recorded", ["starting", "running", "stopping"])
def test_status_reports_stale_when_supervisor_identity_is_invalid(tmp_path, monkeypatch, recorded):
    profile, data = _profile(tmp_path, monkeypatch)
    me = psutil.Process()
    write_json_atomic(data / "control/runtime.json", {"status": recorded, "services": {},
        "supervisor": {"pid": me.pid, "created_at": me.create_time() - 3600, "executable": me.exe()}})
    state = status(profile)
    assert state["status"] == "stale" and state["recorded_status"] == recorded
    assert state["supervisor_identity_valid"] is False


def test_status_keeps_valid_or_final_states(tmp_path, monkeypatch):
    profile, data = _profile(tmp_path, monkeypatch)
    me = psutil.Process()
    identity = {"pid": me.pid, "created_at": me.create_time(), "executable": me.exe()}
    write_json_atomic(data / "control/runtime.json", {"status": "running", "services": {}, "supervisor": identity})
    assert status(profile)["status"] == "running"
    write_json_atomic(data / "control/runtime.json", {"status": "failed", "services": {}, "supervisor": {**identity, "pid": 0}})
    state = status(profile)
    assert state["status"] == "failed" and "recorded_status" not in state
    (data / "control/runtime.json").unlink()
    assert status(profile)["status"] == "stopped"


def test_port_states_distinguish_free_owned_and_foreign():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        ours = port_states({"app": port, "spare": free_port}, {os.getpid()})
        theirs = port_states({"app": port}, set())
    assert ours["app"]["state"] == "owned" and ours["app"]["listener_pids"] == [os.getpid()]
    assert ours["spare"]["state"] == "free"
    assert theirs["app"]["state"] == "foreign"


def _server_side_time_wait(*, listener_reuse: bool) -> int:
    """Port loopback sans écouteur dont il ne reste qu'une socket TIME-WAIT côté serveur (J8, L2 et L4).

    Le serveur ferme d'abord la connexion acceptée, comme Qdrant ou Ollama à l'arrêt ; le client ferme ensuite.
    Avec `listener_reuse`, l'écouteur pose SO_REUSEADDR comme les serveurs POSIX de l'atelier (Go pour Ollama,
    asyncio pour l'API) ; la connexion acceptée, puis sa socket TIME-WAIT, en héritent.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if listener_reuse:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            accepted, _ = listener.accept()
            accepted.close()
            assert client.recv(1) == b""
    deadline = time.monotonic() + 5
    states: set[str] = set()
    while time.monotonic() < deadline:
        states = {item.status for item in psutil.net_connections(kind="tcp") if item.laddr and item.laddr.port == port}
        if states == {psutil.CONN_TIME_WAIT}:
            return port
        time.sleep(0.02)
    pytest.fail(f"TIME-WAIT côté serveur non obtenu sur {port} : {states}")


def _plain_bind_refused(port: int) -> bool:
    """Sonde d'avant la correction : bind sans option."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


@pytest.mark.skipif(sys.platform == "win32", reason="TIME-WAIT côté serveur sous POSIX ; la sonde Windows reste sans option")
def test_port_left_in_server_side_time_wait_is_free_for_the_restart():
    from services.runtime.supervisor import check_ports

    port = _server_side_time_wait(listener_reuse=True)
    # Cas réel de J8 : le bind sans option échoue (EADDRINUSE) alors qu'aucun processus n'écoute.
    assert _plain_bind_refused(port)
    check_ports([port])
    assert port_states({"qdrant": port}, set())["qdrant"]["state"] == "free"
    # Le service redémarré lie bien ce port, avec la même option que la sonde : le verdict « libre » est exact.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as restarted:
        restarted.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        restarted.bind(("127.0.0.1", port))
        restarted.listen()


@pytest.mark.skipif(sys.platform == "win32", reason="TIME-WAIT côté serveur sous POSIX ; la sonde Windows reste sans option")
def test_time_wait_left_by_a_server_without_reuse_stays_refused_as_for_the_service_itself():
    from services.runtime.supervisor import check_ports

    port = _server_side_time_wait(listener_reuse=False)
    with pytest.raises(RuntimeError, match=f"^Port {port} occupé ; aucun service existant ne sera arrêté.$"):
        check_ports([port])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as restarted:
        restarted.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with pytest.raises(OSError):
            restarted.bind(("127.0.0.1", port))


@pytest.mark.parametrize("address", ["127.0.0.1", "0.0.0.0"])
@pytest.mark.parametrize("listener_reuse", [False, True])
def test_listening_port_stays_refused_by_the_probe(monkeypatch, address, listener_reuse):
    from services.runtime import supervisor

    if address == "0.0.0.0" and sys.platform == "win32":
        pytest.skip("Windows : un écouteur sur toutes les interfaces n'empêche pas un bind loopback du même compte")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if listener_reuse:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((address, 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match=f"^Port {port} occupé ; aucun service existant ne sera arrêté.$"):
            supervisor.check_ports([port])
        # Écouteur invisible dans la liste des connexions : seule la sonde par bind décide.
        monkeypatch.setattr(supervisor.psutil, "net_connections", lambda kind: [])
        assert supervisor.port_states({"app": port}, set())["app"]["state"] == "occupied_unknown_owner"


class RecordingSocket:
    """Socket simulée : options et adresse demandées par la sonde, sans réseau."""

    calls: list = []

    def __init__(self, family, kind):
        self.calls.append(("socket", family, kind))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append(("close",))

    def setsockopt(self, level, option, value):
        self.calls.append(("setsockopt", level, option, value))

    def bind(self, address):
        self.calls.append(("bind", address))


@pytest.mark.parametrize(("platform", "options"), [
    ("win32", []),
    ("linux", [("setsockopt", socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]),
])
def test_probe_options_per_platform(monkeypatch, platform, options):
    """Windows simulé : aucune option, comme avant (SO_REUSEADDR y permettrait de lier un port déjà tenu).
    POSIX : SO_REUSEADDR avant le bind, qui refuse toujours un port en écoute."""
    from services.runtime import supervisor

    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(supervisor.socket, "socket", RecordingSocket)
    monkeypatch.setattr(supervisor.psutil, "net_connections", lambda kind: [])
    expected = [("socket", socket.AF_INET, socket.SOCK_STREAM), *options, ("bind", ("127.0.0.1", 6333)), ("close",)]
    RecordingSocket.calls = []
    supervisor.check_ports([6333])
    assert RecordingSocket.calls == expected
    RecordingSocket.calls = []
    assert supervisor.port_states({"qdrant": 6333}, set())["qdrant"]["state"] == "free"
    assert RecordingSocket.calls == expected


class ProbeDone(Exception):
    """Arrêt du test juste après la sonde de port, avant tout lancement de service."""


def _stop(*args, **kwargs):
    raise ProbeDone


def _probe_of_pull_model(monkeypatch, tmp_path):
    from services.runtime import cli

    monkeypatch.setattr(cli, "load_profile", lambda path: {"llm": {"model": "qwen3.5:4b", "required_quantization": "Q4_K_M"}})
    monkeypatch.setattr(cli, "native_paths", _stop)
    with pytest.raises(ProbeDone):
        cli.pull_model(tmp_path / "profil.yaml")
    return 11444


def _probe_of_calibration(monkeypatch, tmp_path):
    from services.api.settings import Settings
    from services.runtime import calibration

    monkeypatch.setattr(calibration, "load_profile", lambda path: {})
    monkeypatch.setattr(Settings, "load", classmethod(_stop))
    with pytest.raises(ProbeDone):
        calibration.calibrate(tmp_path / "profil.yaml", tmp_path / "pilote.json")
    return 11444


def _probe_of_discovery(monkeypatch, tmp_path):
    from services.runtime import accelerator, supervisor

    monkeypatch.setattr(supervisor, "native_paths", _stop)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    with pytest.raises(ProbeDone):
        accelerator.probe_discovery(profile, ROOT / "config/local16.yaml", tmp_path, tmp_path / "sonde.log",
                                    version="0.35.0", port=11464)
    return 11464


def _probe_of_profile_setup(monkeypatch, tmp_path):
    from services.runtime import profile_setup

    assert profile_setup.port_free(18785) is True
    return 18785


@pytest.mark.parametrize("call", [_probe_of_pull_model, _probe_of_calibration, _probe_of_discovery, _probe_of_profile_setup],
                         ids=["pull-model", "calibration", "sonde-decouverte", "init-profile"])
@pytest.mark.parametrize(("platform", "options"), [
    ("win32", []),
    ("linux", [("setsockopt", socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]),
])
def test_every_runtime_port_probe_follows_the_supervisor_rule(monkeypatch, tmp_path, call, platform, options):
    """Revue runtime J8 : pull-model, le pilote, la sonde de découverte et init-profile sondent leur port comme
    check_ports (port_probe) : SO_REUSEADDR sous POSIX, aucune option sous Windows (appels inchangés)."""
    import services.api.context  # noqa: F401  (importé avant la plateforme simulée)
    import services.api.settings  # noqa: F401

    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(socket, "socket", RecordingSocket)
    RecordingSocket.calls = []
    port = call(monkeypatch, tmp_path)
    assert RecordingSocket.calls == [("socket", socket.AF_INET, socket.SOCK_STREAM), *options,
                                     ("bind", ("127.0.0.1", port)), ("close",)]


def test_qdrant_key_is_long_reserved_to_the_qdrant_child_and_never_written_in_config(tmp_path, monkeypatch):
    monkeypatch.setenv("QDRANT__SERVICE__API_KEY", "variable-heritee-du-poste")
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["qdrant"]["storage_dir"] = ".runtime/q/absent00"
    control = tmp_path / "control"
    control.mkdir()
    key = issue_qdrant_key(control)
    assert len(key.encode("ascii")) >= 32 and (control / "qdrant-api-key").read_text(encoding="ascii") == key
    base = environment(profile, tmp_path, ROOT / "config/local16.yaml")
    # Ni la variable héritée ni la clé ne parviennent à Ollama ou à l'API sous le nom Qdrant.
    assert not any(name.upper().startswith("QDRANT") for name in base)
    child = qdrant_environment(base, key)
    assert child["QDRANT__SERVICE__API_KEY"] == key and "QDRANT__SERVICE__API_KEY" not in base
    assert key not in write_qdrant_config(profile, tmp_path, control).read_text(encoding="utf-8")
    assert issue_qdrant_key(control) != key


def test_production_origin_requires_readable_certificate_and_key(tmp_path):
    from services.runtime.supervisor import app_origin

    profile = {"app": {"port": 8785}, "security": {"environment": "production", "tls_cert_file": str(tmp_path / "cert.pem")}}
    with pytest.raises(ValueError, match="tls_key_file"):
        app_origin(profile)
    (tmp_path / "cert.pem").write_text("certificat", encoding="ascii")
    profile["security"]["tls_key_file"] = str(tmp_path / "key.pem")
    with pytest.raises(ValueError):
        app_origin(profile)
    (tmp_path / "key.pem").write_text("clé", encoding="utf-8")
    assert app_origin(profile) == ("https://127.0.0.1:8785", str((tmp_path / "cert.pem").resolve()))
    assert app_origin({"app": {"port": 8785}}) == ("http://127.0.0.1:8785", True)



def test_runtime_locations_default_under_the_program_and_follow_the_profile(tmp_path):
    from services.runtime.artifacts import runtime_location

    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    # Profil du dépôt : emplacements historiques inchangés.
    assert runtime_location(profile, "host_lock_path") == (ROOT / ".runtime/control/host-heavy.lock").resolve()
    assert runtime_location(profile, "backups_dir") == (ROOT / "backups").resolve()
    assert environment(profile, tmp_path, ROOT / "config/local16.yaml")["HF_HOME"] == str((ROOT / ".runtime/cache/huggingface").resolve())
    # Profil d'installation par utilisateur : écritures hors du dossier programme.
    user = tmp_path / "donnees-utilisateur"
    profile["runtime"] = {"host_lock_path": str(user / "control/host-heavy.lock"), "backups_dir": str(user / "sauvegardes"),
                          "restore_storage_dir": str(user / "q"), "huggingface_cache_dir": str(user / "cache/hf")}
    assert runtime_location(profile, "backups_dir") == (user / "sauvegardes").resolve()
    assert runtime_location(profile, "restore_storage_dir") == (user / "q").resolve()
    assert environment(profile, tmp_path, ROOT / "config/local16.yaml")["HF_HOME"] == str((user / "cache/hf").resolve())
    profile["runtime"]["backups_dir"] = ""
    with pytest.raises(ValueError, match="runtime.backups_dir"):
        runtime_location(profile, "backups_dir")


def _other_process_can_lock(path) -> bool:
    """Essai de verrou depuis un autre processus (msvcrt sous Windows, flock sous Linux), relâché aussitôt."""
    code = ("import sys; from services.runtime.resources import _try_lock\n"
            "with open(sys.argv[1], 'r+b') as handle:\n"
            "    try:\n        _try_lock(handle)\n    except OSError:\n        sys.exit(3)\n")
    return subprocess.run([sys.executable, "-c", code, str(path)], cwd=ROOT, timeout=60).returncode == 0


def test_job_creation_failure_removes_the_token_and_releases_the_data_root(tmp_path, monkeypatch):
    # C11 : jeton et Job étaient créés avant le try ; un échec du Job laissait le jeton de contrôle sur disque.
    from services.runtime import supervisor

    profile, data = _profile(tmp_path, monkeypatch)

    def refused():
        raise OSError("création du Job refusée (essai)")

    monkeypatch.setattr(supervisor, "ProcessJob", refused)
    assert supervisor.supervise(profile) == 1
    control = data / "control"
    assert not (control / "admin-token").exists() and not (control / "qdrant-api-key").exists()
    state = json.loads((control / "runtime.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed" and "création du Job refusée" in state["error"] and state["services"] == {}
    assert _other_process_can_lock(control / "runtime.lock")


def test_data_root_lock_held_by_another_process_refuses_a_second_supervisor(tmp_path, monkeypatch):
    from services.runtime import supervisor

    profile, data = _profile(tmp_path, monkeypatch)
    (data / "control").mkdir(parents=True)
    (data / "control/runtime.lock").write_bytes(b"0")
    holder = subprocess.Popen([sys.executable, "-c",
                               "import sys,time; from services.runtime.resources import _try_lock\n"
                               "handle = open(sys.argv[1], 'r+b'); _try_lock(handle); print('held', flush=True); time.sleep(60)",
                               str(data / "control/runtime.lock")], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(RuntimeError, match="possède déjà cette racine de données"):
            supervisor.supervise(profile)
        assert not (data / "control/admin-token").exists()
    finally:
        holder.kill()
        holder.wait(30)
    assert _other_process_can_lock(data / "control/runtime.lock")


@pytest.mark.skipif(sys.platform == "win32", reason="liste blanche des enfants Linux (W018)")
def test_linux_children_get_an_instance_home_a_sanitized_path_and_no_ld_library_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/local/cuda/lib64:")
    monkeypatch.setenv("PATH", "/usr/local/cuda/bin:/home/compte/.nvm/versions/node/v24/bin:/usr/local/bin:/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/home/compte")
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    monkeypatch.setenv("OLLAMA_MODELS", "/home/compte/.ollama/models")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-du-poste")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("TZ", "Europe/Paris")
    monkeypatch.setenv("USER", "compte")
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    env = environment(profile, tmp_path / "données", ROOT / "config/local16.yaml")
    assert "LD_LIBRARY_PATH" not in env and "AWS_SECRET_ACCESS_KEY" not in env
    assert env["HOME"] == str(tmp_path / "données" / "home")
    assert env["PATH"].split(os.pathsep) == [str(Path(sys.executable).parent), "/usr/bin", "/bin"]
    assert env["OLLAMA_HOST"] == "127.0.0.1:11434" and env["OLLAMA_MODELS"] == str(ROOT / ".runtime/models/ollama")
    assert (env["LC_ALL"], env["TZ"], env["USER"]) == ("C.UTF-8", "Europe/Paris", "compte") and env["LANG"]
    assert Path(env["TMPDIR"]).is_dir()


def test_profile_keys_are_read_instead_of_constants(tmp_path, monkeypatch):
    # C6 : OLLAMA_KEEP_ALIVE suit llm.keep_alive ; app.offline et app.telemetry sont des invariants vérifiés.
    from services.runtime.supervisor import load_profile

    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    assert environment(profile, tmp_path, ROOT / "config/local16.yaml")["OLLAMA_KEEP_ALIVE"] == profile["llm"]["keep_alive"] == "10m"
    profile["llm"]["keep_alive"] = "5m"
    assert environment(profile, tmp_path, ROOT / "config/local16.yaml")["OLLAMA_KEEP_ALIVE"] == "5m"
    path = tmp_path / "profil.yaml"
    for key, value in (("offline", False), ("telemetry", True)):
        changed = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
        changed["app"][key] = value
        path.write_text(yaml.safe_dump(changed), encoding="utf-8")
        with pytest.raises(ValueError, match="app.offline: true et app.telemetry: false"):
            load_profile(path)
    assert load_profile(ROOT / "config/local16.yaml")["app"]["offline"] is True


def test_native_paths_take_this_platform_entry_and_its_own_manifest_record(tmp_path, monkeypatch):
    from services.runtime import supervisor
    from services.runtime.artifacts import file_hash
    from services.runtime.platforms import executable_name, platform_id

    current = platform_id()
    other = "linux-aarch64" if current != "linux-aarch64" else "windows-x86_64"
    lock: dict = {"groups": {}}
    records: dict = {}
    for name, version in (("qdrant", "1.19.1"), ("ollama", "0.35.0")):
        folder = f".runtime/bin/{name}-{version}"
        # Archive Linux d'Ollama : bin/ollama et un dossier lib/ollama du même nom que l'exécutable.
        relative = f"{folder}/bin/{executable_name(name)}" if name == "ollama" else f"{folder}/{executable_name(name)}"
        binary = tmp_path / relative
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"binaire " + name.encode())
        (tmp_path / folder / "lib" / name).mkdir(parents=True)
        lock["groups"][name] = [{"platform": other, "url": f"https://autre/{name}", "extract_to": f".runtime/bin/autre-{name}"},
                                {"platform": current, "url": f"https://ici/{name}", "extract_to": folder}]
        # Enregistrement de l'autre plateforme placé en premier : le choix se fait par l'URL, pas par la position.
        records[name] = [{"url": f"https://autre/{name}", "extracted_files": []},
                         {"url": f"https://ici/{name}", "extracted_files": [{"path": relative, "sha256": file_hash(binary)}]}]
    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (tmp_path / ".runtime/manifests").mkdir(parents=True)
    (tmp_path / ".runtime/manifests/artifacts.json").write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(supervisor, "ROOT", tmp_path)
    paths = supervisor.native_paths()
    assert paths["ollama"] == tmp_path / ".runtime/bin/ollama-0.35.0/bin" / executable_name("ollama")
    assert paths["qdrant"] == tmp_path / ".runtime/bin/qdrant-1.19.1" / executable_name("qdrant")
    if sys.platform != "win32":
        cwd = supervisor.ollama_working_directory(paths["ollama"])
        assert cwd == paths["ollama"].resolve().parent and not (cwd / "build").exists() and not (cwd / "dist").exists()
    paths["ollama"].write_bytes(b"remplace")
    with pytest.raises(ValueError, match="binaire ollama non conforme"):
        supervisor.native_paths()
    lock["groups"]["qdrant"] = lock["groups"]["qdrant"][:1]
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match=f"une entrée qdrant attendue pour {current}"):
        supervisor.native_paths()


@pytest.mark.skipif(sys.platform == "win32", reason="groupes de processus POSIX")
def test_survivors_of_a_dead_supervisor_are_reported_and_block_up(tmp_path, monkeypatch):
    from services.runtime.supervisor import start

    profile, data = _profile(tmp_path, monkeypatch)
    # Survivant créé par ce test, dans sa propre session : il tient lieu du runner d'Ollama resté dans le groupe. Il
    # reçoit l'environnement des enfants de l'instance (RAG_DATA_DIR compris), comme un descendant réel d'Ollama.
    survivor = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True,
                                env=environment(load_profile(profile), data, profile))
    try:
        me = psutil.Process()
        created = psutil.Process(survivor.pid).create_time()
        write_json_atomic(data / "control/runtime.json", {"status": "running", "instance_id": "ancienne", "data_dir": str(data),
            "supervisor": {"pid": me.pid, "created_at": me.create_time() - 3600, "executable": me.exe()},
            "services": {"ollama": {"pid": survivor.pid, "created_at": created, "executable": "/absent/ollama",
                                    "process_group": survivor.pid},
                         "qdrant": {"pid": 1, "created_at": created + 3600, "executable": "/absent/qdrant", "process_group": 1}}})
        state = status(profile)
        assert state["status"] == "stale" and state["orphan_processes"] == {"ollama": [survivor.pid]}
        with pytest.raises(RuntimeError, match=f"ollama : PID {survivor.pid}"):
            start(profile)
        assert survivor.poll() is None and not (data / "control/supervisor-start.log").exists()
    finally:
        survivor.kill()
        survivor.wait(30)
    assert "orphan_processes" not in status(profile)


def _dead_instance_state(data, group: int, created: float) -> dict:
    """État d'une instance dont le superviseur a disparu ; le groupe d'Ollama porte le numéro `group`."""
    return {"status": "running", "instance_id": "ancienne", "data_dir": str(data),
            "supervisor": {"pid": 4194000, "created_at": 1.0, "executable": "/absent/python"},
            "services": {"ollama": {"pid": group, "process_group": group, "created_at": created,
                                    "executable": str(ROOT / ".runtime/bin/ollama-0.35.0/bin/ollama")}}}


@pytest.mark.skipif(sys.platform == "win32", reason="groupes de processus POSIX")
@pytest.mark.parametrize("case", ["sans_marqueur", "racine_exportee_programme_etranger", "programme_autre_instance"])
def test_a_foreign_process_leading_a_reused_group_number_is_not_reported(tmp_path, monkeypatch, case):
    # Revue R1 : après un down propre, le numéro de groupe enregistré peut être réattribué à un processus étranger né
    # plus tard (shell, démon setsid) ; il était signalé comme orphelin et up invitait à l'arrêter.
    profile, data = _profile(tmp_path, monkeypatch)
    base = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG"}}
    command, env = {
        "sans_marqueur": (["sleep", "30"], base),
        # Compte qui a exporté RAG_DATA_DIR : même racine de données, mais un programme hors du dossier du programme.
        "racine_exportee_programme_etranger": (["sleep", "30"], {**base, "RAG_DATA_DIR": str(data)}),
        # Interpréteur du projet, mais enfant d'une autre instance (autre racine de données, par exemple un selftest).
        "programme_autre_instance": ([sys.executable, "-c", "import time; time.sleep(30)"],
                                     {**base, "RAG_DATA_DIR": str(tmp_path / "autre-instance")}),
    }[case]
    foreign = subprocess.Popen(command, start_new_session=True, env=env)
    try:
        assert os.getpgid(foreign.pid) == foreign.pid
        state = _dead_instance_state(data, foreign.pid, time.time() - 86400)
        assert orphan_processes(state) == {}
        write_json_atomic(data / "control/runtime.json", state)
        assert "orphan_processes" not in status(profile)
        assert foreign.poll() is None
    finally:
        foreign.kill()
        foreign.wait(30)


@pytest.mark.skipif(sys.platform == "win32", reason="groupes de processus POSIX")
def test_the_inspecting_process_is_never_reported_even_inside_a_recorded_group(tmp_path, monkeypatch):
    # Numéro réattribué au lanceur lui-même (nouvelle tâche du shell, RAG_DATA_DIR exporté) : up ne se refuse pas.
    profile, data = _profile(tmp_path, monkeypatch)
    code = ("import json, os, sys, time\n"
            "from services.runtime.supervisor import orphan_processes\n"
            "state = {'data_dir': sys.argv[1], 'supervisor': {'pid': 4194000, 'created_at': 1.0, 'executable': '/absent'},\n"
            "         'services': {'ollama': {'pid': os.getpid(), 'process_group': os.getpgrp(), 'created_at': time.time() - 86400}}}\n"
            "print(json.dumps({'group': os.getpgrp(), 'pid': os.getpid(), 'orphans': orphan_processes(state)}))\n")
    result = subprocess.run([sys.executable, "-c", code, str(data)], cwd=ROOT, start_new_session=True, capture_output=True,
                            text=True, timeout=60, env={**environment(load_profile(profile), data, profile)})
    observed = json.loads(result.stdout)
    assert observed["group"] == observed["pid"] and observed["orphans"] == {}, result.stderr


# --- Accélération GPU (W024, W025) : environnement d'Ollama inchangé, mode décidé au démarrage ------------------------

# Variables d'un poste qui ne doivent jamais atteindre Ollama : réglages GPU d'Ollama, de CUDA et du chargeur.
GPU_NOISE = {"CUDA_VISIBLE_DEVICES": "0", "OLLAMA_VULKAN": "1", "OLLAMA_LLM_LIBRARY": "cuda_v12",
             "LD_LIBRARY_PATH": "/usr/local/cuda/lib64:", "CUDA_PATH": "/usr/local/cuda", "OLLAMA_HOST": "0.0.0.0:11434"}


def _only_environment(monkeypatch, values: dict[str, str]) -> None:
    for key in list(os.environ):
        monkeypatch.delenv(key)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _shipped_profile_forms() -> list[dict]:
    """Profil livré, puis sa section llm sous chaque forme admise, construite explicitement : forme antérieure
    `num_gpu: 0` (profils d'utilisateur existants, W025 P5), `accelerator` auto, cpu et gpu, aucune des deux clés."""
    shipped = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    forms = [shipped]
    for setting in ({"num_gpu": 0}, {"accelerator": "auto"}, {"accelerator": "cpu"}, {"accelerator": "gpu"}, {}):
        changed = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
        changed["llm"] = {**{key: value for key, value in changed["llm"].items()
                             if key not in ("num_gpu", "accelerator")}, **setting}
        forms.append(changed)
    return forms


def test_the_profile_forms_cover_the_legacy_form_and_every_accelerator_value():
    # Revue J11 runtime-9 : le profil livré est passé en auto ; la forme antérieure reste couverte explicitement.
    from services.runtime.accelerator import profile_accelerator

    forms = _shipped_profile_forms()[1:]
    assert [(form["llm"].get("num_gpu"), form["llm"].get("accelerator")) for form in forms] == [
        (0, None), (None, "auto"), (None, "cpu"), (None, "gpu"), (None, None)]
    assert [profile_accelerator(form)["requested_source"] for form in forms] == [
        "legacy_num_gpu", "profile", "profile", "profile", "default"]


def _common_snapshot(directory: Path, profile_path: Path) -> dict[str, str]:
    """Variables fixées par environment() avant W024 (révision ba945af), pour le profil livré sous chacune de ses formes."""
    return {"PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "RAG_PROFILE": str(profile_path.resolve()),
            "RAG_DATA_DIR": str(directory), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HOME": str((ROOT / ".runtime/cache/huggingface").resolve()),
            "DOCLING_ARTIFACTS_PATH": str(ROOT / ".runtime/models/docling"),
            "TESSDATA_PREFIX": str(ROOT / ".runtime/models/tessdata"), "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "NEXT_TELEMETRY_DISABLED": "1",
            "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(ROOT / ".runtime/models/ollama"),
            "OLLAMA_NO_CLOUD": "1", "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1",
            "OLLAMA_MAX_QUEUE": "2", "OLLAMA_CONTEXT_LENGTH": "8192", "OLLAMA_KEEP_ALIVE": "10m",
            "LLAMA_ARG_CACHE_RAM": "256", "LLAMA_ARG_CTX_CHECKPOINTS": "2"}


def test_ollama_environment_under_simulated_windows_matches_the_reference_snapshot(tmp_path, monkeypatch):
    # W025 : aucune variable OLLAMA_*, CUDA_* ni LD_LIBRARY_PATH ajoutée, quel que soit llm.accelerator.
    windows = {"SystemRoot": r"C:\Windows", "windir": r"C:\Windows", "PATH": r"C:\Windows\system32;C:\Windows",
               "PATHEXT": ".COM;.EXE;.BAT", "TEMP": r"C:\Users\poste\AppData\Local\Temp",
               "TMP": r"C:\Users\poste\AppData\Local\Temp", "USERPROFILE": r"C:\Users\poste",
               "APPDATA": r"C:\Users\poste\AppData\Roaming", "LOCALAPPDATA": r"C:\Users\poste\AppData\Local",
               "ProgramData": r"C:\ProgramData", "ProgramFiles": r"C:\Program Files", "NUMBER_OF_PROCESSORS": "12",
               "PROCESSOR_ARCHITECTURE": "AMD64", "HOME": "/home/poste", "QDRANT__SERVICE__API_KEY": "cle-du-poste"}
    _only_environment(monkeypatch, {**windows, **GPU_NOISE})
    monkeypatch.setattr(sys, "platform", "win32")
    profile_path = ROOT / "config/local16.yaml"
    expected = {**{key: value for key, value in windows.items() if key not in ("HOME", "QDRANT__SERVICE__API_KEY")},
                **_common_snapshot(tmp_path, profile_path)}
    for profile in _shipped_profile_forms():
        assert environment(profile, tmp_path, profile_path) == expected


@pytest.mark.skipif(sys.platform == "win32", reason="branche Linux de la liste blanche (W018)")
def test_ollama_environment_under_linux_matches_the_reference_snapshot(tmp_path, monkeypatch):
    import tempfile

    linux = {"LANG": "fr_FR.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "Europe/Paris", "USER": "compte", "LOGNAME": "compte",
             "PATH": "/usr/local/cuda/bin:/usr/bin:/bin", "HOME": "/home/compte"}
    _only_environment(monkeypatch, {**linux, **GPU_NOISE})
    profile_path = ROOT / "config/local16.yaml"
    expected = {"LANG": "fr_FR.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "Europe/Paris", "USER": "compte", "LOGNAME": "compte",
                "PATH": os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"]),
                "TMPDIR": tempfile.gettempdir(), "HOME": str(tmp_path / "home"), **_common_snapshot(tmp_path, profile_path)}
    for profile in _shipped_profile_forms():
        assert environment(profile, tmp_path, profile_path) == expected


DECISION_KEYS = {"requested", "requested_source", "mode", "reason", "device", "variant", "qualified", "discovery",
                 "libraries", "host", "utc"}


def _program_root(root: Path, manifest: dict) -> None:
    """Verrou et manifeste d'artefacts d'un programme de test (aucune écriture sous .runtime du dépôt)."""
    from tests.unit.test_runtime_accelerator import LOCK

    (root / "config").mkdir(exist_ok=True)
    (root / "config/artifacts.lock.json").write_text(json.dumps(LOCK), encoding="utf-8")
    write_json_atomic(root / ".runtime/manifests/artifacts.json", manifest)


@pytest.fixture
def accelerator_cases(jetson_libraries, monkeypatch):  # noqa: F811
    from services.runtime import accelerator, supervisor
    from tests.unit.test_runtime_accelerator import JETSON, JETSON_JETPACK5, WINDOWS_IRIS_XE

    root, manifest = jetson_libraries
    _program_root(root, manifest)
    monkeypatch.setattr(supervisor, "ROOT", root)
    # Mémoire totale lue par la décision : celle du poste de l'essai réel du 02/10 (62 800 Mio).
    meminfo = root / "meminfo"
    meminfo.write_bytes(b"MemTotal:       64307708 kB\n")
    monkeypatch.setattr(accelerator, "MEMINFO", meminfo)
    windows = {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None, "nvidia_kernel_driver": None,
               "gpu_nodes": {}, "windows_nvcuda": False}
    return {"windows_iris_xe": (WINDOWS_IRIS_XE, windows, "cpu", "no_gpu_discovered"),
            "jetson_jetpack5": (JETSON_JETPACK5, JETSON, "gpu", "gpu_discovered")}


@pytest.mark.parametrize("case", ["windows_iris_xe", "jetson_jetpack5"])
def test_instance_accelerator_records_the_decision_of_the_instance(tmp_path, monkeypatch, accelerator_cases, case):
    from services.runtime import supervisor

    log, signals, mode, reason = accelerator_cases[case]
    monkeypatch.setattr(supervisor, "host_signals", lambda: signals)
    (tmp_path / "ollama.log").write_text(log, encoding="utf-8")
    profile = {"llm": {"accelerator": "auto"}}
    decision = supervisor.instance_accelerator(profile, tmp_path / "ollama.log")
    assert set(decision) == DECISION_KEYS and (decision["mode"], decision["reason"]) == (mode, reason)
    assert decision["requested"] == "auto" and decision["host"] == signals
    # Forme antérieure (profil livré avant W024) : CPU quelle que soit la découverte.
    legacy = supervisor.instance_accelerator({"llm": {"num_gpu": 0}}, tmp_path / "ollama.log")
    assert (legacy["mode"], legacy["reason"], legacy["requested_source"]) == ("cpu", "legacy_profile_cpu", "legacy_num_gpu")


@pytest.mark.parametrize(("kb", "requested", "mode", "reason"), [
    (b"15974400", "auto", "cpu", "gpu_unified_memory_not_qualified"),
    (b"31334400", "auto", "gpu", "gpu_discovered"),
    (None, "auto", "cpu", "gpu_unified_memory_not_qualified"),
    (b"15974400", "gpu", "gpu", "gpu_trial"),
], ids=["16go-auto", "32go-auto", "inconnue-auto", "16go-gpu"])
def test_the_instance_of_a_jetson_follows_its_total_memory(tmp_path, monkeypatch, accelerator_cases, kb, requested, mode,
                                                           reason):
    from services.runtime import accelerator, supervisor

    log, signals, _, _ = accelerator_cases["jetson_jetpack5"]
    # Fichier distinct de celui du jeu d'essai (même dossier temporaire) : absent, la mémoire est inconnue.
    meminfo = tmp_path / "meminfo-poste"
    if kb is not None:
        meminfo.write_bytes(b"MemTotal:       " + kb + b" kB\n")
    monkeypatch.setattr(accelerator, "MEMINFO", meminfo)
    monkeypatch.setattr(supervisor, "host_signals", lambda: signals)
    (tmp_path / "ollama.log").write_text(log, encoding="utf-8")
    decision = supervisor.instance_accelerator({"llm": {"accelerator": requested}}, tmp_path / "ollama.log")
    assert (decision["mode"], decision["reason"], decision["qualified"]) == (mode, reason, True)


def test_an_unreadable_artifact_manifest_verifies_no_library_and_keeps_the_cpu(tmp_path, monkeypatch, accelerator_cases):
    from services.runtime import supervisor

    log, signals, _, _ = accelerator_cases["jetson_jetpack5"]
    (supervisor.ROOT / ".runtime/manifests/artifacts.json").write_text("{tronqué", encoding="utf-8")
    monkeypatch.setattr(supervisor, "host_signals", lambda: signals)
    (tmp_path / "ollama.log").write_text(log, encoding="utf-8")
    decision = supervisor.instance_accelerator({"llm": {"accelerator": "auto"}}, tmp_path / "ollama.log")
    assert (decision["mode"], decision["reason"]) == ("cpu", "gpu_libraries_unverified")
    assert decision["libraries"]["error"].startswith("JSONDecodeError")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.mark.skipif(sys.platform == "win32", reason="superviseur simulé avec les verrous POSIX de ce poste")
@pytest.mark.parametrize("case", ["windows_iris_xe", "jetson_jetpack5"])
def test_supervise_records_the_mode_and_passes_it_to_the_api_only(tmp_path, monkeypatch, accelerator_cases, case):
    """Superviseur simulé (Job, binaires et disponibilité sont des doubles) : runtime.json reçoit state["accelerator"]
    avant le lancement de l'API, seule destinataire de RAG_LLM_ACCELERATOR et RAG_LLM_ACCELERATOR_REASON."""
    from types import SimpleNamespace

    from services.runtime import source_manifest, supervisor

    log, signals, mode, reason = accelerator_cases[case]
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    monkeypatch.setattr(supervisor, "host_signals", lambda: signals)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["llm"].pop("num_gpu", None)
    profile["llm"]["accelerator"] = "auto"
    profile["app"].update(data_dir=str(tmp_path / "données"), port=_free_port())
    profile["qdrant"]["url"] = f"http://127.0.0.1:{_free_port()}"
    profile["llm"]["base_url"] = f"http://127.0.0.1:{_free_port()}"
    profile_path = tmp_path / "profil.yaml"
    profile_path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    data = tmp_path / "données"
    (data / "control").mkdir(parents=True)
    # Marqueur d'arrêt posé d'avance : la boucle de surveillance n'est pas parcourue.
    (data / "control/shutdown-essai0instance").touch()
    monkeypatch.setattr(supervisor, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="essai0instance")))
    monkeypatch.setattr(source_manifest, "capture", lambda: {"source_fingerprint": "essai", "kind": "test"})
    monkeypatch.setattr(supervisor, "native_paths", lambda: {"qdrant": tmp_path / "qdrant", "ollama": tmp_path / "ollama"})
    monkeypatch.setattr(supervisor, "send_owned_console_interrupt", lambda child, service=None: True)
    monkeypatch.setattr(supervisor, "wait_http", lambda url, child, *args, **kwargs:
                        {"version": "0.35.0"} if url.endswith("/api/version") else {"status": "ok"})
    launched: dict[str, dict] = {}

    class Child:
        def __init__(self, name, log_path):
            self.name, self.log_path = name, log_path

        def identity(self):
            return {"pid": 4194000, "created_at": 1.0, "executable": f"/absent/{self.name}", "log_path": str(self.log_path)}

        def poll(self):
            return None

        def wait(self, timeout=30):
            return 0

    class Job:
        def launch(self, argv, *, cwd, env, log_path):
            name = "api" if "services.runtime.api_entry" in argv else Path(argv[0]).name
            recorded = json.loads((data / "control/runtime.json").read_text(encoding="utf-8"))
            launched[name] = {"env": dict(env), "accelerator_recorded": "accelerator" in recorded}
            if name == "ollama":
                log_path.write_text(log, encoding="utf-8")
            return Child(name, log_path)

        def close(self):
            pass

    monkeypatch.setattr(supervisor, "ProcessJob", Job)
    assert supervisor.supervise(profile_path) == 0
    state = json.loads((data / "control/runtime.json").read_text(encoding="utf-8"))
    assert state["status"] == "stopped" and set(state["accelerator"]) == DECISION_KEYS
    assert (state["accelerator"]["mode"], state["accelerator"]["reason"]) == (mode, reason)
    assert launched["api"]["accelerator_recorded"] and not launched["ollama"]["accelerator_recorded"]
    assert launched["api"]["env"]["RAG_LLM_ACCELERATOR"] == mode
    assert launched["api"]["env"]["RAG_LLM_ACCELERATOR_REASON"] == reason
    for service in ("qdrant", "ollama"):
        assert not {"RAG_LLM_ACCELERATOR", "RAG_LLM_ACCELERATOR_REASON"} & set(launched[service]["env"])
    # Ollama reçoit exactement environment() ; Qdrant la même copie plus sa clé.
    reference = environment(load_profile(profile_path), data, profile_path)
    assert launched["ollama"]["env"] == reference
    assert {key: value for key, value in launched["qdrant"]["env"].items() if key != "QDRANT__SERVICE__API_KEY"} == reference
    api_only = set(launched["api"]["env"]) - set(reference)
    assert api_only == {"RAG_SHUTDOWN_MARKER", "RAG_CONTROL_TOKEN", "RAG_QDRANT_API_KEY", "RAG_LLM_ACCELERATOR",
                        "RAG_LLM_ACCELERATOR_REASON"}
