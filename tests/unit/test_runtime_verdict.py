"""Verdict de doctor (DIST-05) : rubriques, messages, et pannes provoquées sur les vraies fonctions d'observation."""

import copy
import json
import os
import socket

import pytest

from services.runtime import cli, platforms, supervisor
from services.runtime.artifacts import file_hash
from services.runtime.platforms import executable_name
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
            "index_consistency": {"status": "consistent", "active_generations": 0, "sqlite_chunks": 0, "mismatches": []},
        },
    }


@pytest.fixture(params=["windows", "linux"])
def host(request, monkeypatch):
    """Lanceur du poste simulé : les textes Windows restent mot pour mot ceux de rag.ps1, Linux renvoie à rag.sh."""
    windows = request.param == "windows"
    monkeypatch.setattr(platforms, "WINDOWS", windows)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1" if windows else "./rag.sh")
    return request.param


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


def test_stopped_or_stale_runtime_is_orange_and_says_how_to_start(host):
    result = healthy()
    result["runtime"] = {"status": "stopped"}
    result["services"]["api_ready"] = {"status": "unavailable", "reason": "ConnectError"}
    services = rubric(doctor_verdict(result), "services")
    assert services["level"] == "orange" and services["message"] == "Atelier arrêté."
    assert services["action"] == {"windows": r"Démarrez-le : .\rag.ps1 up, ou ouvrez-le par .\rag.ps1 open.",
                                  "linux": "Démarrez-le : ./rag.sh up, ou ouvrez-le par ./rag.sh open."}[host]
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


def test_provoked_absent_model_is_red_with_offline_pull_action(store, host):  # noqa: F811
    root, lock = store
    root.joinpath("manifests/registry.ollama.ai/library/qwen3.5/4b-text").unlink()
    result = healthy()
    result["checks"]["model_lock"] = {**cli.model_lock_conformity(lock, root), "profile_models_locked": True}
    model = rubric(doctor_verdict(result), "modèle")
    assert model["level"] == "rouge" and model["message"] == "Modèle absent du stockage local : qwen3.5:4b-text."
    assert model["action"] == {
        "windows": r"Lancez .\rag.ps1 pull-model -Offline ; s'il échoue, réinstallez l'atelier depuis le kit.",
        "linux": "Lancez ./rag.sh pull-model --offline ; s'il échoue, lancez ./rag.sh pull-model, qui télécharge le modèle verrouillé."}[host]


def test_provoked_altered_model_file_is_red_and_names_the_issue(store):  # noqa: F811
    root, lock = store
    weights = _weights(root, "qwen3.5:4b-text")
    weights.write_bytes(b"XXXX" + weights.read_bytes()[4:])
    result = healthy()
    result["checks"]["model_lock"] = {**cli.model_lock_conformity(lock, root, hash_limit_bytes=None), "profile_models_locked": True}
    model = rubric(doctor_verdict(result), "modèle")
    assert model["level"] == "rouge" and model["message"] == "Modèle différent du verrou : qwen3.5:4b-text (blob_hash_mismatch)."


def test_provoked_altered_native_binary_is_red_program_files(tmp_path, monkeypatch):
    # Panne provoquée : le binaire Qdrant (qdrant.exe sous Windows) ne correspond plus à l'empreinte du manifeste local
    # (copie isolée, aucun binaire réel touché).
    lock = {"groups": {name: [{"extract_to": f".runtime/bin/{name}"}] for name in ("qdrant", "ollama")}}
    records = {}
    for name in ("qdrant", "ollama"):
        binary = tmp_path / ".runtime/bin" / name / executable_name(name)
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"MZ" + name.encode())
        records[name] = [{"extracted_files": [{"path": f".runtime/bin/{name}/{executable_name(name)}", "sha256": file_hash(binary)}]}]
    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (tmp_path / ".runtime/manifests").mkdir(parents=True)
    (tmp_path / ".runtime/manifests/artifacts.json").write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(supervisor, "ROOT", tmp_path)
    assert set(supervisor.native_paths()) == {"qdrant", "ollama"}
    (tmp_path / ".runtime/bin/qdrant" / executable_name("qdrant")).write_bytes(b"MZ altered")
    with pytest.raises(ValueError) as failure:
        supervisor.native_paths()
    result = healthy()
    result["checks"]["native_binaries"] = {"error": str(failure.value)}
    result["checks"]["tesseract_binary"] = False
    program = rubric(doctor_verdict(result), "programme")
    assert program["level"] == "rouge"
    assert program["message"] == ("Fichiers du programme absents ou incomplets : Tesseract, binaires Qdrant et Ollama "
                                  "(Empreinte du binaire qdrant non conforme au manifeste local).")
    assert program["action"] == ("Réinstallez l'atelier depuis le kit ; les données de l'utilisateur ne sont pas touchées."
                                 if platforms.WINDOWS else "Relancez ./rag.sh provision ; les données de l'utilisateur ne sont pas touchées.")


def test_index_points_differing_from_sqlite_fragments_are_red_and_unverified_index_is_orange(host):
    result = healthy()
    result["checks"]["index_consistency"] = {"status": "inconsistent", "active_generations": 3, "sqlite_chunks": 40,
                                             "mismatches": [{"generation_id": "g1", "document_id": "d1", "sqlite_chunks": 12, "qdrant_points": 9}]}
    index = rubric(doctor_verdict(result), "index")
    assert index["level"] == "rouge" and index["message"] == "Index incohérent pour 1 document(s) : points Qdrant et fragments SQLite diffèrent."
    assert "Réindexez" in index["action"]
    result["checks"]["index_consistency"] = {"status": "api_unavailable"}
    assert rubric(doctor_verdict(result), "index") == {"rubric": "index", "level": "orange", "message": "Cohérence de l'index non vérifiée (atelier arrêté).",
                                                      "action": {"windows": r"Démarrez l'atelier puis relancez .\rag.ps1 doctor.",
                                                                 "linux": "Démarrez l'atelier puis relancez ./rag.sh doctor."}[host]}


def test_profile_storage_refused_or_restart_required():
    result = healthy()
    result["checks"]["profile_application"] = {"status": "restart_required"}
    assert rubric(doctor_verdict(result), "profil")["level"] == "orange"
    result["checks"]["qdrant_storage"] = {"status": "invalid", "reason": "Chemin Qdrant trop long"}
    profile = rubric(doctor_verdict(result), "profil")
    assert profile["level"] == "rouge" and "qdrant.storage_dir" in profile["action"]
    assert doctor_verdict(result)["summary"] == "Atelier inutilisable en l'état : profil."


def test_every_windows_action_text_is_unchanged_and_linux_names_rag_sh(host):
    """Textes d'action relevés avant W018 (rag.ps1) : identiques sous Windows ; sous Linux, rag.sh et ses options POSIX."""
    windows = host == "windows"
    result = healthy()
    result["checks"]["profile_application"] = {"status": "restart_required"}
    assert rubric(doctor_verdict(result), "profil")["action"] == (
        r"Redémarrez : .\rag.ps1 down puis .\rag.ps1 up." if windows else "Redémarrez : ./rag.sh down puis ./rag.sh up.")
    result = healthy()
    result["runtime"] = {"status": "stale"}
    assert rubric(doctor_verdict(result), "services")["action"] == (
        r"Relancez l'atelier : .\rag.ps1 up." if windows else "Relancez l'atelier : ./rag.sh up.")
    result["runtime"] = {"status": "starting"}
    assert rubric(doctor_verdict(result), "services")["action"] == (
        r"Relancez .\rag.ps1 doctor dans une minute." if windows else "Relancez ./rag.sh doctor dans une minute.")
    result = healthy()
    result["services"]["api_ready"] = {"http_status": 503, "body": {"checks": {"qdrant": False}}}
    assert rubric(doctor_verdict(result), "services")["action"] == (
        r"Consultez les journaux (.\rag.ps1 logs). Une collection perdue ne se recrée pas sur place : restaurez une "
        r"sauvegarde dans une racine neuve (.\rag.ps1 restore -Path <sauvegarde> -Target <racine neuve>)." if windows else
        "Consultez les journaux (./rag.sh logs). Une collection perdue ne se recrée pas sur place : restaurez une "
        "sauvegarde dans une racine neuve (./rag.sh restore --path <sauvegarde> --target <racine neuve>).")
    result = healthy()
    result["checks"]["model_lock"] = {"status": "invalid_lock", "reason": "JSON"}
    assert rubric(doctor_verdict(result), "modèle")["action"] == (
        "Réinstallez l'atelier depuis le kit." if windows else
        "Rétablissez config/models.lock.json de la version installée, puis relancez ./rag.sh doctor.")
    result["checks"]["model_lock"] = {"status": "unknown", "profile_models_locked": True, "models": {}}
    assert rubric(doctor_verdict(result), "modèle")["action"] == (
        r"Relancez .\rag.ps1 doctor ; si l'état persiste, réinstallez l'atelier." if windows else
        "Relancez ./rag.sh doctor ; si l'état persiste, relancez ./rag.sh provision.")
    result["checks"]["model_lock"] = {"status": "nonconform", "profile_models_locked": True,
                                      "models": {"qwen3.5:4b-text": {"status": "nonconform", "issues": [{"issue": "size_mismatch"}]}}}
    assert rubric(doctor_verdict(result), "modèle")["action"] == (
        "Réinstallez l'atelier depuis le kit pour retrouver les fichiers vérifiés." if windows else
        "Relancez ./rag.sh pull-model pour retrouver les fichiers vérifiés.")
