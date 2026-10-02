"""Profil livré sous Windows simulé : les clés lues depuis W018 ne changent pas le comportement Windows.

R1 a remplacé des constantes par la lecture du profil, avec des refus nouveaux communs aux deux plateformes :
`app.offline`, `app.telemetry`, `app.asgi_workers`, `llm.keep_alive`, `resources.scheduling.initial_mode` et
`resources.unload_llm_before_ingestion`. Avec `config/local16.yaml` chargé sous `sys.platform == "win32"`, chaque valeur
obtenue est celle que le code fixait avant (révision 26fa7a5) : OLLAMA_KEEP_ALIVE « 10m », un seul processus API, mode
initial « interactive », déchargement du modèle avant chaque extraction, profil admis sans erreur.
"""

import sys

import pytest

from services.runtime.api_entry import server_config
from services.runtime.artifacts import ROOT
from services.runtime.resources import ResourceGovernor
from services.runtime.supervisor import environment, load_profile

PROFILE = ROOT / "config/local16.yaml"


class ProfileSettings:
    """Lecture `value(section, clé)` du profil, comme services.api.settings.Settings."""

    def __init__(self, profile: dict):
        self.profile = profile

    def value(self, section, key, default=None):
        return self.profile.get(section, {}).get(key, default)


class DevelopmentPolicy:
    production = False


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    for name in ("HOME", "TMPDIR", "LD_LIBRARY_PATH"):
        monkeypatch.setenv(name, f"/valeur/{name.lower()}")


def test_shipped_profile_is_admitted_and_ollama_keeps_its_previous_keep_alive(windows, tmp_path):
    profile = load_profile(PROFILE)
    assert (profile["app"]["offline"], profile["app"]["telemetry"]) == (True, False)
    env = environment(profile, tmp_path, PROFILE)
    # Branche Windows de la liste blanche : ni HOME d'instance, ni TMPDIR, ni LD_LIBRARY_PATH (noms absents de la liste).
    assert not {"HOME", "TMPDIR", "LD_LIBRARY_PATH"} & set(env)
    assert env["OLLAMA_KEEP_ALIVE"] == "10m"


def test_shipped_profile_keeps_a_single_api_process(windows):
    config = server_config(ProfileSettings(load_profile(PROFILE)), DevelopmentPolicy())
    assert config.workers == 1 and config.host == "127.0.0.1"


def test_shipped_profile_keeps_the_interactive_start_and_the_unload_before_extraction(windows, tmp_path):
    profile = load_profile(PROFILE)
    governor = ResourceGovernor({**profile, "app": {**profile["app"], "data_dir": str(tmp_path)}},
                                host_lock_path=tmp_path / "host-heavy.lock")
    # Avant W018 : mode initial codé « interactive » et déchargement appelé avant chaque extraction.
    assert governor.snapshot()["mode"] == "interactive"
    assert governor.unload_llm_before_ingestion is True and governor.auto_resume_ingestion is False


# --- Accélération GPU (W024, W025) : poste Windows de référence, sans GPU utilisable --------------------------------------

def _profile_form(tmp_path, **setting):
    """Profil livré dont la section llm porte la seule forme donnée : `num_gpu=0` (forme antérieure des profils
    d'utilisateur existants) ou `accelerator=…`."""
    import yaml

    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile["llm"] = {**{key: value for key, value in profile["llm"].items() if key not in ("num_gpu", "accelerator")},
                      **setting}
    path = tmp_path / ("local16-" + "-".join(f"{key}-{value}" for key, value in setting.items()) + ".yaml")
    path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _auto_profile(tmp_path):
    return _profile_form(tmp_path, accelerator="auto")


@pytest.fixture
def windows_host(windows, tmp_path, monkeypatch):
    """Poste Windows simulé : identifiant de plateforme, lanceur rag.ps1, aucun nvcuda.dll ; verrou réel du dépôt."""
    import json

    from services.runtime import accelerator, cli, platforms, supervisor

    monkeypatch.setattr(accelerator, "platform_id", lambda: "windows-x86_64")
    monkeypatch.setattr(platforms, "WINDOWS", True)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
    program = tmp_path / "programme"
    (program / "config").mkdir(parents=True)
    (program / "config/artifacts.lock.json").write_bytes((ROOT / "config/artifacts.lock.json").read_bytes())
    (program / ".runtime/manifests").mkdir(parents=True)
    (program / ".runtime/manifests/artifacts.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(supervisor, "ROOT", program)
    monkeypatch.setattr(cli, "ROOT", program)


def test_the_reference_windows_host_starts_on_cpu_and_its_verdict_only_gains_a_green_rubric(windows_host, tmp_path):
    from services.runtime import cli, supervisor
    from services.runtime.verdict import doctor_verdict
    from tests.unit.test_runtime_accelerator import WINDOWS_IRIS_XE
    from tests.unit.test_runtime_verdict import healthy

    profile = load_profile(_auto_profile(tmp_path))
    log = tmp_path / "ollama.log"
    log.write_text(WINDOWS_IRIS_XE, encoding="utf-8")
    decision = supervisor.instance_accelerator(profile, log)
    # Chaîne de preuve (conception §11.1) : profil auto, iGPU Vulkan écarté, mode CPU transmis à l'API.
    assert (decision["requested"], decision["mode"], decision["reason"]) == ("auto", "cpu", "no_gpu_discovered")
    assert decision["host"]["platform"] == "windows-x86_64" and decision["host"]["windows_nvcuda"] is False
    assert decision["host"]["l4t_major"] is None and decision["libraries"]["required"] is False
    runtime = {"status": "running", "instance_id": "poste-windows", "accelerator": decision}
    models = [{"name": profile["llm"]["model"], "size": 3107811491, "size_vram": 0}]
    check = cli.accelerator_check(profile, runtime, models, {"llm_accelerator": {"mode": "cpu", "fallback": None}})
    assert check["state"] == "cpu_no_gpu"
    before = doctor_verdict(healthy())
    result = healthy()
    result["checks"]["accelerator"] = check
    after = doctor_verdict(result)
    assert (after["level"], after["summary"]) == (before["level"], before["summary"])
    assert after["rubrics"][:7] == before["rubrics"] and after["proposals"] == []
    assert after["rubrics"][7] == {"rubric": "calcul", "level": "vert", "message": (
        "Calcul sur CPU : Ollama n'a découvert aucun GPU utilisable. GPU intégré ignoré par Ollama : "
        "Intel(R) Iris(R) Xe Graphics (Vulkan).")}


def test_the_legacy_form_and_each_accelerator_value_give_ollama_the_same_environment(windows, tmp_path):
    # Revue J11 runtime-9 : le profil livré est en auto ; la forme antérieure num_gpu: 0, celle des profils d'utilisateur
    # existants, est construite explicitement et comparée à auto, cpu et gpu.
    legacy = load_profile(_profile_form(tmp_path, num_gpu=0))
    assert legacy["llm"]["num_gpu"] == 0 and "accelerator" not in legacy["llm"]
    reference = environment(legacy, tmp_path, PROFILE)
    for value in ("auto", "cpu", "gpu"):
        form = load_profile(_profile_form(tmp_path, accelerator=value))
        assert environment(form, tmp_path, PROFILE) == reference
    assert environment(load_profile(PROFILE), tmp_path, PROFILE) == reference
