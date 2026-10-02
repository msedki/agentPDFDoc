"""Inventaire des licences : artefacts du verrou retenus pour ce poste, avec la règle de provision (revue J11 runtime-8).

Racine de programme temporaire ; ni distribution Python ni paquet npm n'est parcouru (doubles), seul le verrou compte.
"""

import json

import pytest

from services.runtime import inventory
from tests.unit.test_runtime_accelerator import LOCK


@pytest.fixture
def program(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps({"schema_version": 1, "groups": {
        group: [{**entry, "target": f".runtime/cache/downloads/{entry['url'].rsplit('/', 1)[-1]}"} for entry in entries]
        for group, entries in LOCK["groups"].items()}}), encoding="utf-8")
    monkeypatch.setattr(inventory, "ROOT", tmp_path)
    monkeypatch.setattr(inventory.importlib.metadata, "distributions", lambda: [])
    return tmp_path


@pytest.mark.parametrize(("signals", "expected"), [
    ({"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5"},
     ["base.tar.zst", "ollama-linux-arm64-jetpack5.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": 36, "jetpack": "jetpack6"},
     ["base.tar.zst", "ollama-linux-arm64-jetpack6.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": None, "jetpack": None}, ["base.tar.zst"]),
    ({"platform": "windows-x86_64", "l4t_major": None, "jetpack": None}, ["base.zip"]),
])
def test_the_inventory_lists_the_artifacts_that_provision_takes_on_this_host(program, monkeypatch, signals, expected):
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(signals))
    output = program / "licences.json"
    inventory.license_inventory(output)
    listed = json.loads(output.read_text(encoding="utf-8"))["artifacts"]
    assert [item["source"].rsplit("/", 1)[-1] for item in listed] == expected
    assert all(item["provisioned"] is False for item in listed)
