"""Owned qualification deadlines, using clocks/processes/HTTP as explicit doubles.

No native executable, socket, model, corpus or real sleep is used. The real
launcher orchestration writes its receipt files to a temporary directory.
"""

import json
from types import SimpleNamespace

import pytest
import yaml

from services.runtime import posix_process
from tools.qualification import run_grounded_native as launcher


class ClockDouble:
    def __init__(self):
        self.elapsed = 0.0

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


class OwnedProcessDouble:
    def __init__(self, pid, name, clock, expires):
        self.pid = self.pgid = pid
        self.name = name
        self.clock = clock
        self.expires = expires
        self.reaped = False
        self.group_stopped = False

    def poll(self):
        if self.group_stopped:
            return -15
        if self.name == "measurement" and not self.expires and self.clock.elapsed >= 0.5:
            return 0
        return None


@pytest.mark.parametrize("transport", ["direct", "http"])
@pytest.mark.parametrize("expires", [False, True], ids=["completes", "deadline"])
def test_every_transport_uses_owned_measurement_and_stops_all_groups_at_its_fixed_deadline(tmp_path, monkeypatch, transport, expires):
    root = tmp_path / "program"
    config = root / "config"
    config.mkdir(parents=True)
    (config / "enhanced-4b.yaml").write_text(yaml.safe_dump({
        "llm": {"model": "qwen3-4b-enhanced:q4km"}, "embedding": {}, "qdrant": {}}), encoding="utf-8")
    output = tmp_path / "results"
    clock = ClockDouble()
    launched, stopped, provisions, ports = [], [], [], []

    class JobDouble:
        closed = False

        def launch(self, command, **kwargs):
            name = "measurement" if len(launched) == 2 else "ollama" if not launched else "qdrant"
            process = OwnedProcessDouble(7001 + len(launched), name, clock, expires)
            launched.append((process, command, kwargs))
            if name == "measurement":
                assert command[1].endswith("revision_campaign.py" if transport == "direct" else "production_i4_http.py")
                assert kwargs["log_path"] == output / "measurement.log"
                measurements = output / "measurements"
                measurements.mkdir()
                (measurements / "transport-result.json").write_text(json.dumps({"operational_passed": not expires}), encoding="utf-8")
            return process

        def close(self):
            self.closed = True

    job = JobDouble()

    class HttpDouble:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            version = "0.35.0" if url.endswith("/api/version") else "1.19.1"
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"version": version})

    def stop_double(process):
        stopped.append(process.name)
        process.group_stopped = True
        process.reaped = True
        return {"pid": process.pid, "returncode": process.poll(), "remaining_group_members": [],
                "owned_group_empty": True, "leader_reaped": True}

    def provisioning_double(command, **kwargs):
        # The former unbounded direct subprocess.run reaches this assertion.
        # Only the existing separate 600 s provisioning call may use it.
        assert command[1].endswith("provision_enhanced_4b.py")
        assert kwargs["timeout"] == 600 and kwargs["check"] is True
        provisions.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    monkeypatch.setattr(launcher, "time", clock)
    monkeypatch.setattr(launcher, "available_port", ports.append)
    monkeypatch.setattr(launcher, "environment", lambda *args: {})
    monkeypatch.setattr(launcher, "stop_owned", stop_double)
    monkeypatch.setattr(launcher.httpx, "Client", HttpDouble)
    monkeypatch.setattr(launcher.subprocess, "run", provisioning_double)
    monkeypatch.setattr(posix_process, "PosixJob", lambda: job)
    args = SimpleNamespace(application_root=root, output=output, transport=transport,
                           ollama_port=11439, qdrant_port=6339, label="candidate",
                           inputs=tmp_path / "synthetic-inputs.json", case_id=["SYNTHETIC_CASE"])

    assert launcher.run(args) == (124 if expires else 0)
    assert ports == [11439, 6339, 6340] and len(provisions) == 1
    assert [process.name for process, _, _ in launched] == ["ollama", "qdrant", "measurement"]
    assert stopped == ["measurement", "qdrant", "ollama"]
    assert job.closed and all(process.reaped and process.group_stopped for process, _, _ in launched)
    assert clock.elapsed == (1500.0 if expires else 0.5)
    receipt = json.loads((output / "measurement-process.json").read_text())
    assert receipt == {"transport": transport, "pid": 7003, "deadline_seconds": 1500,
                       "harness_timeout": expires, "observed_returncode": None if expires else 0}
    cleanup = json.loads((output / "service-stop.json").read_text())
    assert cleanup["all_owned_services_stopped"] is True
    assert len(cleanup["owned_services"]) == 3
    if transport == "http":
        assert json.loads((output / "http-final-result.json").read_text())["operational_passed"] is not expires
