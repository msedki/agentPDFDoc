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
