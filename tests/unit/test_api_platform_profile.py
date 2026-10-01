"""Textes du lanceur selon la plateforme (W018), origine HTTPS (C16) et clés du profil effectivement lues (C6)."""
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors

from services.api.errors import ApiError
from services.api.main import create_app
from services.api.ollama import OllamaGateway
from services.api.security import LINK_HELP
from services.api.settings import FIXED_PROFILE_VALUES, Settings, unsupported_profile_values
from services.runtime.platforms import launcher_command

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ".\\rag.ps1" if sys.platform == "win32" else "./rag.sh"


class SilentOllama:
    """Double explicite : aucune passerelle Ollama n'est contactée."""
    async def close(self):
        pass


class SilentGovernor:
    """Double explicite du gouverneur : aucune admission n'est demandée par ces tests."""


def build(tmp_path, profile=None):
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": 8785}, **(profile or {})})
    return create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                      ollama=SilentOllama(), governor=SilentGovernor(), start_jobs=False)


def test_session_help_names_the_launcher_of_this_platform_and_keeps_the_windows_text():
    assert LINK_HELP == f"Ouvrir l'atelier avec « {LAUNCHER} open » depuis le dossier du projet."
    if sys.platform == "win32":
        assert LINK_HELP == "Ouvrir l'atelier avec « .\\rag.ps1 open » depuis le dossier du projet."


def test_refused_session_and_public_health_announce_the_launcher_commands(tmp_path):
    with TestClient(build(tmp_path), base_url="http://127.0.0.1:8785") as client:
        refused = client.get("/api/v1/library/tree")
        health = client.get("/api/v1/health")
    assert refused.status_code == 401 and refused.json()["message"].endswith(f"« {LAUNCHER} open » depuis le dossier du projet.")
    assert health.status_code == 200
    assert health.json() == {"status": "alive", "service": "rag-api",
                             "commands": {"open": f"{LAUNCHER} open", "status": f"{LAUNCHER} status", "logs": f"{LAUNCHER} logs",
                                          "doctor": f"{LAUNCHER} doctor"}}
    assert health.json()["commands"] == {action: launcher_command(action) for action in ("open", "status", "logs", "doctor")}
    if sys.platform == "win32":
        # Texte Windows de l'avis de préparation (HEAD) : « La commande .\rag.ps1 doctor détaille chaque contrôle ».
        assert health.json()["commands"]["doctor"] == ".\\rag.ps1 doctor"


def test_origin_follows_the_security_environment(tmp_path):
    """C16 : l'API passe en HTTPS en production ; l'origine utilisée par les outils doit suivre."""
    development = Settings(tmp_path, {"app": {"port": 8785}})
    assert development.origin == "http://127.0.0.1:8785" and development.origin_certificate is None
    production = Settings(tmp_path, {"app": {"port": 8790}, "security": {"environment": "production", "tls_cert_file": "certs/api.pem", "tls_key_file": "certs/api.key"}})
    assert production.origin == "https://127.0.0.1:8790"
    assert production.origin_certificate == (tmp_path / "certs/api.pem").resolve()


@pytest.mark.parametrize("profile", ["config/local16.yaml", "RAG_Local_Agents/config/local16.yaml"])
def test_delivered_profiles_load_without_unsupported_values(profile):
    settings = Settings.load(ROOT / profile)
    assert unsupported_profile_values(settings.profile) == []
    for path, expected in FIXED_PROFILE_VALUES.items():
        node = settings.profile
        for name in path:
            node = node[name]
        assert node == expected and type(node) is type(expected), path


def altered(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value * 2
    return value + "-modifié"


@pytest.mark.parametrize("path", sorted(FIXED_PROFILE_VALUES), ids=".".join)
def test_profile_value_the_code_does_not_implement_is_refused_at_startup(tmp_path, path):
    """C6 : une clé du profil sans effet ne doit plus être ignorée en silence."""
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    node = profile
    for name in path[:-1]:
        node = node[name]
    node[path[-1]] = altered(node[path[-1]])
    target = tmp_path / "profil.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ApiError) as refused:
        Settings.load(target)
    assert refused.value.code == "invalid_profile" and refused.value.details["keys"] == [".".join(path)]


def test_sqlite_busy_timeout_and_cache_size_are_read_from_the_profile(tmp_path):
    app = build(tmp_path / "shipped", {"sqlite": {"busy_timeout_ms": 5000, "cache_size_kib": 32768}})
    app.state.db.initialize()
    with app.state.db.connect() as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA cache_size").fetchone()[0] == -32768
    app = build(tmp_path / "tuned", {"sqlite": {"busy_timeout_ms": 7500, "cache_size_kib": 16384}})
    app.state.db.initialize()
    with app.state.db.connect() as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 7500
        assert connection.execute("PRAGMA cache_size").fetchone()[0] == -16384
    with pytest.raises(ApiError):
        build(tmp_path / "invalid", {"sqlite": {"busy_timeout_ms": 0}})


def test_ollama_connect_timeout_is_read_from_the_profile(tmp_path):
    import asyncio

    for configured, expected in ((None, 5), (5, 5), (9, 9)):
        llm = {"base_url": "http://127.0.0.1:11434"} | ({"connect_timeout_seconds": configured} if configured is not None else {})
        gateway = OllamaGateway(Settings(tmp_path, {"llm": llm}))
        assert gateway.client.timeout.connect == expected
        asyncio.run(gateway.close())
