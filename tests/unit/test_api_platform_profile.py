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
from services.runtime.accelerator import BOTH_KEYS_MESSAGE, LEGACY_NUM_GPU_MESSAGE, VALUE_MESSAGE
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


# --- Accélération de la génération (W024, W025) ----------------------------------------------------------------------

def delivered_profile_with(tmp_path, **llm_changes):
    """Copie du profil livré, section llm sans clé d'accélération, qui reçoit `llm_changes` (None retire la clé) ;
    chemin du fichier écrit."""
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    for key in ("accelerator", "num_gpu"):
        profile["llm"].pop(key, None)
    for key, value in llm_changes.items():
        if value is None:
            profile["llm"].pop(key, None)
        else:
            profile["llm"][key] = value
    target = tmp_path / "profil.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return target


def test_delivered_profile_requests_auto(monkeypatch):
    monkeypatch.delenv("RAG_LLM_ACCELERATOR", raising=False)
    monkeypatch.delenv("RAG_LLM_ACCELERATOR_REASON", raising=False)
    state = Settings.load(ROOT / "config/local16.yaml").llm_accelerator
    assert (state["requested"], state["requested_source"], state["mode"]) == ("auto", "profile", "cpu")


@pytest.mark.parametrize("changes,requested", [
    ({"num_gpu": 0}, ("cpu", "legacy_num_gpu")),
    ({}, ("auto", "default")),
    ({"accelerator": "auto"}, ("auto", "profile")),
    ({"accelerator": "cpu"}, ("cpu", "profile")),
    ({"accelerator": "gpu"}, ("gpu", "profile")),
], ids=["forme-anterieure", "sans-cle", "auto", "cpu", "gpu"])
def test_both_profile_forms_of_the_accelerator_are_accepted(tmp_path, monkeypatch, changes, requested):
    monkeypatch.delenv("RAG_LLM_ACCELERATOR", raising=False)
    monkeypatch.delenv("RAG_LLM_ACCELERATOR_REASON", raising=False)
    settings = Settings.load(delivered_profile_with(tmp_path, **changes))
    state = settings.llm_accelerator
    assert (state["requested"], state["requested_source"]) == requested and state["mode"] == "cpu"


@pytest.mark.parametrize("changes,message,keys", [
    ({"accelerator": "turbo"}, VALUE_MESSAGE, ["llm.accelerator"]),
    ({"accelerator": True}, VALUE_MESSAGE, ["llm.accelerator"]),
    ({"accelerator": "GPU"}, VALUE_MESSAGE, ["llm.accelerator"]),
    ({"accelerator": "auto", "num_gpu": 0}, BOTH_KEYS_MESSAGE, ["llm.accelerator", "llm.num_gpu"]),
    ({"num_gpu": 1}, LEGACY_NUM_GPU_MESSAGE, ["llm.num_gpu"]),
    ({"num_gpu": -1}, LEGACY_NUM_GPU_MESSAGE, ["llm.num_gpu"]),
    ({"num_gpu": False}, LEGACY_NUM_GPU_MESSAGE, ["llm.num_gpu"]),
], ids=["valeur-inconnue", "booleen", "majuscules", "deux-cles", "num-gpu-1", "num-gpu-auto-ollama", "num-gpu-false"])
def test_accelerator_refusals_name_the_keys_with_the_supervisor_messages(tmp_path, changes, message, keys):
    with pytest.raises(ApiError) as refused:
        Settings.load(delivered_profile_with(tmp_path, **changes))
    assert refused.value.code == "invalid_profile" and refused.value.status == 400
    assert refused.value.message == message and refused.value.details == {"keys": keys}


@pytest.mark.parametrize("llm", [["base_url", "http://127.0.0.1:11434"], "ollama", None, 3],
                         ids=["liste", "texte", "vide", "nombre"])
def test_an_llm_section_that_is_not_a_table_is_refused_with_its_key(tmp_path, llm):
    # Relecture J11.9 : section llm présente mais qui n'est pas une table ; AttributeError dans Settings.value avant
    # la correction, refus invalid_profile nommant la clé depuis, avec le message du superviseur.
    from services.runtime.accelerator import AcceleratorProfileError
    from services.runtime.supervisor import load_profile

    path = delivered_profile_with(tmp_path)
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    profile["llm"] = llm
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ApiError) as refused:
        Settings.load(path)
    assert (refused.value.code, refused.value.status, refused.value.details) == ("invalid_profile", 400, {"keys": ["llm"]})
    assert refused.value.message == "La section llm du profil est absente ou n'est pas une table."
    with pytest.raises(AcceleratorProfileError) as supervisor_refusal:
        load_profile(path)
    assert str(supervisor_refusal.value) == refused.value.message and supervisor_refusal.value.keys == ("llm",)


@pytest.mark.parametrize("qdrant", [["url", "http://127.0.0.1:6333"], "qdrant", None], ids=["liste", "texte", "vide"])
def test_a_qdrant_section_that_is_not_a_table_is_refused_with_its_key(tmp_path, qdrant):
    path = delivered_profile_with(tmp_path)
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    profile["qdrant"] = qdrant
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ApiError) as refused:
        Settings.load(path)
    assert (refused.value.code, refused.value.status, refused.value.details) == ("invalid_profile", 400,
                                                                                {"keys": ["qdrant"]})
    assert refused.value.message == "La section qdrant du profil n'est pas une table."


def test_an_absent_llm_section_keeps_the_loopback_refusal(tmp_path):
    # Comportement documenté (DEPANNAGE, section 2) : une section absente est refusée par la règle de boucle locale.
    path = delivered_profile_with(tmp_path)
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    del profile["llm"]
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ApiError) as refused:
        Settings.load(path)
    assert (refused.value.code, refused.value.message) == ("invalid_profile", "Les services doivent rester sur loopback.")


@pytest.mark.parametrize("llm,decided,expected", [
    ({"accelerator": "auto"}, None, ("cpu", None)),
    ({"accelerator": "auto"}, ("gpu", "gpu_discovered"), ("gpu", "gpu_discovered")),
    ({"accelerator": "gpu"}, ("gpu", "gpu_trial"), ("gpu", "gpu_trial")),
    ({}, ("gpu", "gpu_discovered"), ("gpu", "gpu_discovered")),
    ({"accelerator": "auto"}, ("cpu", "no_gpu_discovered"), ("cpu", "no_gpu_discovered")),
    ({"accelerator": "auto"}, ("cpu", "gpu_path_not_qualified"), ("cpu", "gpu_path_not_qualified")),
    ({"accelerator": "cpu"}, ("gpu", "gpu_discovered"), ("cpu", "imposed_by_profile")),
    ({"num_gpu": 0}, ("gpu", "gpu_discovered"), ("cpu", "legacy_profile_cpu")),
    # Décision illisible ou raison contraire au mode : le mode suit la décision, la raison n'est pas inventée.
    ({"accelerator": "auto"}, ("cuda", "gpu_discovered"), ("cpu", None)),
    ({"accelerator": "auto"}, ("gpu", "no_gpu_discovered"), ("gpu", None)),
    ({"accelerator": "auto"}, ("cpu", "gpu_discovered"), ("cpu", None)),
    ({"accelerator": "auto"}, ("cpu", "raison-inconnue"), ("cpu", None)),
])
def test_generation_mode_follows_the_supervisor_decision_only_when_the_profile_allows_it(tmp_path, monkeypatch, llm, decided, expected):
    for name, value in zip(("RAG_LLM_ACCELERATOR", "RAG_LLM_ACCELERATOR_REASON"), decided or (None, None), strict=True):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    state = Settings(tmp_path, {"llm": llm}).llm_accelerator
    assert (state["mode"], state["reason"]) == expected
    assert set(state) == {"requested", "requested_source", "mode", "reason"}
