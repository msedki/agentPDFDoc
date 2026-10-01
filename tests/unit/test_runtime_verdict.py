"""Verdict de doctor (DIST-05) : rubriques, messages, et pannes provoquées sur les vraies fonctions d'observation."""

import copy
import json
import os
import socket

import pytest

from services.runtime import cli, supervisor
from services.runtime.artifacts import file_hash
from services.runtime.verdict import doctor_verdict
from tests.unit.test_runtime_doctor import _weights, store  # noqa: F401  (fixture réutilisée)

READY_EMPTY = {"http_status": 200, "body": {"status": "ready", "checks": {"sqlite": True, "qdrant": True}, "blockers": [],
                                            "qdrant_collection": "absent_empty_library"}}


def healthy() -> dict:
    """Forme d'un résultat de doctor sur une installation neuve démarrée (relevée sur l'instance principale le 01/10)."""
    return {
        "runtime": {"status": "running"},
        "services": {"api_ready": copy.deepcopy(READY_EMPTY)},
        "checks": {
            "qdrant_storage": {"status": "valid"}, "profile_application": {"status": "applied"},
            "ports": {"app": {"port": 8785, "state": "owned", "listener_pids": [1], "listener_names": ["python.exe"]}},
            "cold_admission": {"generation": {"available_mib": 9000.0, "required_available_mib": 4992, "admissible_now": True},
                               "ingestion": {"available_mib": 9000.0, "required_available_mib": 3000, "admissible_now": True},
                               "limit": "texte"},
            "model_lock": {"status": "conform", "profile_models_locked": True,
                           "models": {"qwen3.5:4b": {"status": "conform", "issues": []}, "qwen3.5:4b-text": {"status": "conform", "issues": []}}},
            "python312": True, "dependencies_locked": True, "static_export": True, "native_binaries": {"qdrant": "q", "ollama": "o"},
            "embedding_files": True, "llm_tokenizer": True, "ocr_languages": {"fra": True, "eng": True, "osd": True},
            "ocr_tsv_config": True, "tesseract_binary": True,
        },
    }


def levels(verdict: dict) -> dict:
    return {item["rubric"]: item["level"] for item in verdict["rubrics"]}


def rubric(verdict: dict, name: str) -> dict:
    return next(item for item in verdict["rubrics"] if item["rubric"] == name)


def test_fresh_started_installation_is_green_with_the_expected_empty_index():
    verdict = doctor_verdict(healthy())
    assert verdict["level"] == "vert" and set(levels(verdict).values()) == {"vert"}
    assert verdict["summary"] == "Tout est prêt : services démarrés, index vide, prêt à importer, modèle vérifié."
    assert "ne prouve ni import" in verdict["limit"]


def test_memory_short_of_admission_is_orange_with_figures_and_action():
    result = healthy()
    result["checks"]["cold_admission"]["generation"].update(available_mib=3687.94, admissible_now=False)
    verdict = doctor_verdict(result)
    memory = rubric(verdict, "mémoire")
    assert verdict["level"] == "orange" and memory["level"] == "orange"
    assert memory["message"].startswith("Génération non admise maintenant : 3 688 Mio disponibles, 4 992 Mio requis.")
    assert "Fermez des applications" in memory["action"]
    assert verdict["summary"] == "Atelier utilisable, avec réserve : mémoire."


def test_stopped_or_stale_runtime_is_orange_and_says_how_to_start():
    result = healthy()
    result["runtime"] = {"status": "stopped"}
    result["services"]["api_ready"] = {"status": "unavailable", "reason": "ConnectError"}
    services = rubric(doctor_verdict(result), "services")
    assert services["level"] == "orange" and services["message"] == "Atelier arrêté." and r".\rag.ps1 up" in services["action"]
    result["runtime"] = {"status": "stale"}
    assert rubric(doctor_verdict(result), "services")["level"] == "orange"


def test_running_but_blocked_readiness_is_red_and_names_what_blocks():
    result = healthy()
    result["services"]["api_ready"] = {"http_status": 503, "body": {"status": "blocked", "checks": {"sqlite": True, "qdrant": False, "ollama": False},
                                                                    "qdrant_collection": "absent_with_published_generations"}}
    services = rubric(doctor_verdict(result), "services")
    assert services["level"] == "rouge"
    assert services["message"] == ("Atelier démarré mais pas prêt : index Qdrant, modèle de réponse dans Ollama ; "
                                   "collection Qdrant absente alors que des documents sont publiés.")
    assert "racine neuve" in services["action"]


def test_provoked_busy_port_is_red_and_names_the_listening_process():
    # Panne provoquée : un port de l'atelier tenu par un processus qui n'appartient pas à l'instance (ce test).
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        states = supervisor.port_states({"app": port}, owned=set())
    assert states["app"]["state"] == "foreign" and states["app"]["listener_pids"] == [os.getpid()]
    result = healthy()
    result["checks"]["ports"] = states
    verdict = doctor_verdict(result)
    ports = rubric(verdict, "ports")
    assert verdict["level"] == "rouge" and ports["level"] == "rouge"
    name = states["app"]["listener_names"][0]
    assert ports["message"] == f"Port déjà utilisé : {port} (app) occupé par {name} (PID {os.getpid()}). Rien n'a été arrêté."
    assert "app.port" in ports["action"]


def test_provoked_absent_model_is_red_with_offline_pull_action(store):  # noqa: F811
    root, lock = store
    root.joinpath("manifests/registry.ollama.ai/library/qwen3.5/4b-text").unlink()
    result = healthy()
    result["checks"]["model_lock"] = {**cli.model_lock_conformity(lock, root), "profile_models_locked": True}
    model = rubric(doctor_verdict(result), "modèle")
    assert model["level"] == "rouge" and model["message"] == "Modèle absent du stockage local : qwen3.5:4b-text."
    assert r".\rag.ps1 pull-model -Offline" in model["action"]


def test_provoked_altered_model_file_is_red_and_names_the_issue(store):  # noqa: F811
    root, lock = store
    weights = _weights(root, "qwen3.5:4b-text")
    weights.write_bytes(b"XXXX" + weights.read_bytes()[4:])
    result = healthy()
    result["checks"]["model_lock"] = {**cli.model_lock_conformity(lock, root, hash_limit_bytes=None), "profile_models_locked": True}
    model = rubric(doctor_verdict(result), "modèle")
    assert model["level"] == "rouge" and model["message"] == "Modèle différent du verrou : qwen3.5:4b-text (blob_hash_mismatch)."


def test_provoked_altered_native_binary_is_red_program_files(tmp_path, monkeypatch):
    # Panne provoquée : qdrant.exe ne correspond plus à l'empreinte du manifeste local (copie isolée, aucun binaire réel touché).
    lock = {"groups": {name: [{"extract_to": f".runtime/bin/{name}"}] for name in ("qdrant", "ollama")}}
    records = {}
    for name in ("qdrant", "ollama"):
        binary = tmp_path / ".runtime/bin" / name / f"{name}.exe"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"MZ" + name.encode())
        records[name] = [{"extracted_files": [{"path": f".runtime/bin/{name}/{name}.exe", "sha256": file_hash(binary)}]}]
    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (tmp_path / ".runtime/manifests").mkdir(parents=True)
    (tmp_path / ".runtime/manifests/artifacts.json").write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(supervisor, "ROOT", tmp_path)
    assert set(supervisor.native_paths()) == {"qdrant", "ollama"}
    (tmp_path / ".runtime/bin/qdrant/qdrant.exe").write_bytes(b"MZ altered")
    with pytest.raises(ValueError) as failure:
        supervisor.native_paths()
    result = healthy()
    result["checks"]["native_binaries"] = {"error": str(failure.value)}
    result["checks"]["tesseract_binary"] = False
    program = rubric(doctor_verdict(result), "programme")
    assert program["level"] == "rouge"
    assert program["message"] == ("Fichiers du programme absents ou incomplets : Tesseract, binaires Qdrant et Ollama "
                                  "(Empreinte du binaire qdrant non conforme au manifeste local).")
    assert "Réinstallez l'atelier depuis le kit" in program["action"]


def test_profile_storage_refused_or_restart_required():
    result = healthy()
    result["checks"]["profile_application"] = {"status": "restart_required"}
    assert rubric(doctor_verdict(result), "profil")["level"] == "orange"
    result["checks"]["qdrant_storage"] = {"status": "invalid", "reason": "Chemin Qdrant trop long"}
    profile = rubric(doctor_verdict(result), "profil")
    assert profile["level"] == "rouge" and "qdrant.storage_dir" in profile["action"]
    assert doctor_verdict(result)["summary"] == "Atelier inutilisable en l'état : profil."
