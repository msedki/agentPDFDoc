import json
import os
import socket

import psutil
import pytest
import yaml

from services.runtime.artifacts import ROOT, write_json_atomic
from services.runtime.supervisor import RotatingJsonl, port_states, status, supervisor_sample


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
