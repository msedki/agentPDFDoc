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
