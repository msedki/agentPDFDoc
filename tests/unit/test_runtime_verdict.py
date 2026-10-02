"""Verdict de doctor (DIST-05) : rubriques, messages, et pannes provoquées sur les vraies fonctions d'observation."""

import copy
import json
import os
import re
import socket

import pytest

from services.runtime import cli, platforms, supervisor
from services.runtime.accelerator import parse_discovery, processor_label
from services.runtime.artifacts import file_hash
from services.runtime.platforms import executable_name
from services.runtime.verdict import PROPOSAL_SUFFIX, doctor_verdict, generation_text
from tests.unit.test_runtime_accelerator import (
    CUDA_DISCRETE,
    DISCOVERING,
    JETSON_BASE_ONLY,
    JETSON_JETPACK5,
    ORIN,
    VULKAN_DISCRETE,
    WINDOWS_IRIS_XE,
)
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



# --- Rubrique « calcul » (D01.4, W024, W025) ---------------------------------------------------------------------------
# Chaque contrôle passe par cli.accelerator_state (état) puis par doctor_verdict (textes) : deux fonctions pures du
# résultat de doctor. Les découvertes sont les extraits réels ou synthétiques de test_runtime_accelerator.

# Mémoire totale du poste de l'essai réel du 02/10 (62 800 Mio) ; un Jetson de 16 Go est simulé à part.
JETSON_HOST = {"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5",
               "nvidia_kernel_driver": "NVRM version: NVIDIA UNIX Open Kernel Module for aarch64  35.4.1",
               "gpu_nodes": {"/dev/nvhost-gpu": {"exists": True, "access": True}}, "windows_nvcuda": None,
               "memory_total_mib": 62800}
JETSON_16_HOST = {**JETSON_HOST, "memory_total_mib": 15600}
JETSON_R36_HOST = {**JETSON_HOST, "l4t_major": 36, "jetpack": "jetpack6",
                   "nvidia_kernel_driver": "NVRM version: NVIDIA UNIX Open Kernel Module for aarch64  540.4.0"}
WINDOWS_HOST = {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None, "nvidia_kernel_driver": None,
                "gpu_nodes": {}, "windows_nvcuda": False, "memory_total_mib": None}
LIBRARIES_OK = {"entry": "ollama-linux-arm64-jetpack5.tar.zst", "required": True, "provisioned": True,
                "variants": {"cuda_jetpack5": {"group": "ollama-gpu", "files": 2, "links": 1, "sizes_ok": True,
                                               "links_ok": True}}}
LIBRARIES_MISSING = {"entry": "ollama-linux-arm64-jetpack5.tar.zst", "required": True, "provisioned": False,
                     "variants": {}}
LIBRARIES_MISSING_R36 = {**LIBRARIES_MISSING, "entry": "ollama-linux-arm64-jetpack6.tar.zst"}
NONE_REQUIRED = {"entry": None, "required": False, "provisioned": False, "variants": {}}
# Zip Windows d'Ollama consigné au manifeste, installé depuis un kit construit avec --without-gpu : fichiers absents.
WINDOWS_KIT_WITHOUT_GPU = {"entry": None, "required": False, "provisioned": False, "variants": {
    name: {"group": "ollama", "files": 4, "links": 0, "sizes_ok": False, "links_ok": True}
    for name in ("cuda_v12", "cuda_v13", "vulkan")}}
COMPLEMENT = {"file": "ollama-linux-arm64-jetpack5.tar.zst", "size": 297201571, "extracted_size": 864658584,
              "variant": "cuda_jetpack5", "qualified": True}
# Complément JetPack 6 du verrou : taille extraite inconnue, voie cuda_jetpack6 non qualifiée (W025 P4).
COMPLEMENT_R36 = {"file": "ollama-linux-arm64-jetpack6.tar.zst", "size": 269692742, "extracted_size": None,
                  "variant": "cuda_jetpack6", "qualified": False}
MODEL = "qwen3.5:4b-text"
ORIN_TEXT = "Orin (CUDA, GPU intégré, bibliothèques cuda_jetpack5)"
RTX_TEXT = "NVIDIA GeForce RTX 4060 (CUDA, GPU dédié, bibliothèques cuda_v13)"
# GPU NVIDIA que CUDA écarte (pilote ancien ou capacité trop basse) : Ollama ne le voit plus que par Vulkan, actif par
# défaut en 0.35.0 (envconfig/config.go).
NVIDIA_VULKAN = ('time=2026-10-02T09:00:05.000Z level=INFO source=types.go:32 msg="inference compute" id=0 filter_id="" '
                 'library=Vulkan compute=0.0 name=Vulkan0 description="NVIDIA GeForce GTX 1060 6GB" '
                 'libdirs=ollama,vulkan driver=0.0 pci_id=0000:01:00.0 type=discrete total="6.0 GiB" '
                 'available="5.2 GiB"\n')
GTX_TEXT = "NVIDIA GeForce GTX 1060 6GB (Vulkan, GPU dédié, bibliothèques vulkan)"
DRIVER_PROPOSAL = ("Ollama 0.35.0 exige une capacité de calcul 5.0 ou plus et un pilote NVIDIA 550 ou plus récent "
                   "(570 ou plus récent pour une capacité de 5.0 à 6.2) : vérifiez la version du pilote, dont la mise à "
                   "jour relève de l'administrateur du poste, puis le journal d'Ollama ({logs}).")
# Propositions informatives : aucune action dans l'atelier ne mène au GPU, le résumé ne les annonce pas.
INFORMATIVE = {"nvidia_not_retained", "gpu_mixed_libraries", "cuda_libraries_absent"}


def discovery(text: str, source: str = "runtime") -> dict:
    return {"source": source, "utc": "2026-10-01T21:49:26+00:00", **parse_discovery(text)}


def accelerator(**fields) -> dict:
    """checks["accelerator"] tel que doctor le compose ; l'état est établi par cli.accelerator_state."""
    check = {"requested": "auto", "requested_source": "profile", "running": False, "host": JETSON_HOST,
             "libraries": LIBRARIES_OK, "complement": COMPLEMENT, "ollama_version": "0.35.0", "discovery": None,
             "mode": None, "reason": None, "device": None, "variant": None, "qualified": False, "if_auto": None,
             "fallback": None, "usage": None, "model": MODEL, "keep_alive": "10m", **fields}
    check["state"] = cli.accelerator_state(check)
    return check


def gpu_instance(**fields) -> dict:
    """Instance en marche sur le GPU du Jetson (voie qualifiée)."""
    return accelerator(**{"running": True, "discovery": discovery(JETSON_JETPACK5), "mode": "gpu",
                          "reason": "gpu_discovered", "device": ORIN, "variant": "cuda_jetpack5", "qualified": True,
                          "usage": [], **fields})


def loaded(size: int, size_vram: int) -> list[dict]:
    return [{"model": MODEL, "size": size, "size_vram": size_vram, "processor": processor_label(size, size_vram)}]


def verdict_of(check: dict) -> dict:
    result = healthy()
    result["checks"]["accelerator"] = check
    return doctor_verdict(result)


def calcul(check: dict) -> tuple[dict, str | None, list]:
    """Rubrique « calcul » sans sa proposition, sa proposition, et la liste des propositions annoncées par le résumé."""
    verdict = verdict_of(check)
    item = dict(rubric(verdict, "calcul"))
    proposal = item.pop("proposal", None)
    announced = bool(proposal) and check.get("state") not in INFORMATIVE
    assert verdict["proposals"] == ([{"rubric": "calcul", "text": proposal}] if announced else [])
    assert verdict["summary"].endswith(PROPOSAL_SUFFIX) is announced
    return item, proposal, verdict["proposals"]


def cpu_decision(text: str, reason: str, device=None, variant=None) -> dict:
    return {"discovery": discovery(text), "mode": "cpu", "reason": reason, "device": device, "variant": variant}


LINUX_CASES = {
    "cpu_imposed": (accelerator(requested="cpu", **cpu_decision(JETSON_JETPACK5, "imposed_by_profile", ORIN,
                                                              "cuda_jetpack5")),
                    "vert", "Calcul sur CPU, imposé par le profil (llm.accelerator: cpu). GPU présent, laissé "
                    f"inutilisé : {ORIN_TEXT}.", None, None),
    "cpu_legacy": (accelerator(requested="cpu", requested_source="legacy_num_gpu",
                               if_auto={"mode": "gpu", "reason": "gpu_discovered", "device": ORIN,
                                        "variant": "cuda_jetpack5"},
                               **cpu_decision(JETSON_JETPACK5, "legacy_profile_cpu", ORIN, "cuda_jetpack5")),
                   "vert", "Calcul sur CPU : le profil est antérieur à l'accélération GPU (llm.num_gpu: 0).", None,
                   f"Un GPU utilisable est présent : {ORIN_TEXT}. Remplacez llm.num_gpu: 0 par llm.accelerator: auto "
                   "dans le profil, puis redémarrez (./rag.sh down puis ./rag.sh up)."),
    "gpu_libraries_missing": (accelerator(libraries=LIBRARIES_MISSING, **cpu_decision(JETSON_BASE_ONLY,
                                                                                      "no_gpu_discovered")),
                              "vert", "Calcul sur CPU : GPU NVIDIA Jetson présent (Jetson Linux R35, JetPack 5), mais "
                              "les bibliothèques GPU d'Ollama pour cette version ne sont pas installées.", None,
                              "Pour calculer les réponses sur le GPU : ./rag.sh provision --only ollama-gpu (283 Mio à "
                              "télécharger, 825 Mio une fois extraits), puis ./rag.sh down et ./rag.sh up. Pour rester "
                              "sur CPU sans cette proposition, indiquez llm.accelerator: cpu dans le profil."),
    "jetson_unsupported": (accelerator(host={**JETSON_HOST, "l4t_major": 38, "jetpack": None}, libraries=NONE_REQUIRED,
                                       complement=None, **cpu_decision(JETSON_BASE_ONLY, "no_gpu_discovered")),
                           "vert", "Calcul sur CPU : Jetson Linux R38 n'a pas de bibliothèques GPU publiées pour "
                           "Ollama 0.35.0 (seuls JetPack 5 et JetPack 6 en ont), et Ollama n'a découvert aucun GPU "
                           "utilisable.", None, None),
    "nvidia_not_retained": (accelerator(host={**WINDOWS_HOST, "platform": "linux-x86_64", "windows_nvcuda": None,
                                              "nvidia_kernel_driver": "NVRM version: NVIDIA UNIX x86_64 Kernel Module  535.183.01"},
                                        libraries=NONE_REQUIRED, complement=None,
                                        **cpu_decision(JETSON_BASE_ONLY, "no_gpu_discovered")),
                            "vert", "Calcul sur CPU : un pilote NVIDIA est installé, mais Ollama n'a retenu aucun GPU.",
                            None, DRIVER_PROPOSAL.format(logs="./rag.sh logs")),
    "gpu_rejected_by_ollama": (accelerator(**cpu_decision(JETSON_BASE_ONLY, "no_gpu_discovered")),
                               "orange", "Calcul sur CPU : les bibliothèques GPU d'Ollama pour ce Jetson (Jetson Linux "
                               "R35, JetPack 5) sont installées, mais Ollama n'a retenu aucun GPU.",
                               "Consultez le journal d'Ollama (./rag.sh logs) : il indique pourquoi le GPU a été écarté. "
                               "Pour ne plus voir cet avertissement, indiquez llm.accelerator: cpu dans le profil.", None),
    "gpu_libraries_unverified": (accelerator(libraries={**LIBRARIES_OK, "variants": {"cuda_jetpack5": {
                                     **LIBRARIES_OK["variants"]["cuda_jetpack5"], "sizes_ok": False}}},
                                     **cpu_decision(JETSON_JETPACK5, "gpu_libraries_unverified", ORIN, "cuda_jetpack5")),
                                 "orange", f"Calcul sur CPU : Ollama a trouvé un GPU, {ORIN_TEXT}, mais ces bibliothèques "
                                 "ne correspondent pas au manifeste vérifié.",
                                 "Relancez ./rag.sh provision --only ollama-gpu pour rétablir les fichiers vérifiés "
                                 "d'Ollama, puis ./rag.sh down et ./rag.sh up.", None),
    "gpu_pending": (accelerator(discovery=discovery(JETSON_JETPACK5, "provision"), mode="gpu", reason="gpu_discovered",
                                device=ORIN, variant="cuda_jetpack5", qualified=True),
                    "vert", f"Génération sur GPU attendue au prochain démarrage : {ORIN_TEXT}.", None, None),
    "gpu_ready": (gpu_instance(), "vert", f"Génération sur GPU : {ORIN_TEXT} ; le modèle n'est pas encore chargé.",
                  None, None),
    "gpu_in_use": (gpu_instance(usage=loaded(3107811491, 3107811491)), "vert",
                   f"Génération sur GPU : {ORIN_TEXT}, modèle chargé à 100 % sur le GPU.", None, None),
    "gpu_partial": (gpu_instance(usage=loaded(100, 52)), "vert",
                    f"Génération sur GPU et CPU : {ORIN_TEXT}, modèle chargé à 52 % sur le GPU et 48 % sur le CPU, "
                    "selon la mémoire GPU libre au chargement.", None, None),
    "gpu_mode_on_cpu": (gpu_instance(usage=loaded(3107811491, 0)), "orange",
                        f"GPU retenu, {ORIN_TEXT}, mais le modèle est chargé entièrement sur le CPU.",
                        "Attendez la fin du maintien en mémoire du modèle (llm.keep_alive : 10m) : la question suivante "
                        "le rechargera sur le GPU, sans redémarrage. S'il revient sur le CPU, libérez de la mémoire et "
                        "consultez le journal d'Ollama (./rag.sh logs).", None),
    "gpu_fallback": (gpu_instance(usage=loaded(3107811491, 0), fallback={
                         "utc": "2026-10-01T22:14:05.123456+00:00", "http_status": 500,
                         "error": "llama runner process has terminated: CUDA error: out of memory"}),
                     "orange", "Le chargement du modèle sur le GPU a échoué (01/10/2026 22:14:05 UTC) : l'atelier répond "
                     "sur CPU jusqu'au prochain redémarrage. Message d'Ollama (HTTP 500) : « llama runner process has "
                     "terminated: CUDA error: out of memory ».",
                     "Consultez le journal d'Ollama (./rag.sh logs), puis redémarrez (./rag.sh down puis ./rag.sh up) "
                     "pour réessayer le GPU ; pour ne plus l'essayer, indiquez llm.accelerator: cpu dans le profil.",
                     None),
    "anomaly_gpu_in_cpu_mode": (accelerator(requested="cpu", running=True, usage=loaded(100, 52),
                                            **cpu_decision(JETSON_JETPACK5, "imposed_by_profile", ORIN, "cuda_jetpack5")),
                                "orange", "Anomalie : le modèle est chargé sur le GPU (48%/52% CPU/GPU) alors que "
                                "l'atelier calcule sur CPU.",
                                "Redémarrez l'atelier (./rag.sh down puis ./rag.sh up) ; si l'anomalie persiste, "
                                "conservez le journal d'Ollama (./rag.sh logs). Aucune mesure de recette D07 n'est "
                                "valable dans cet état.", None),
    "discovery_unreadable": (accelerator(**cpu_decision("", "discovery_unreadable")), "orange",
                             "Calcul sur CPU : la découverte des GPU par Ollama n'a pas pu être lue dans son journal.",
                             "Consultez le journal d'Ollama (./rag.sh logs) ; l'atelier fonctionne sur CPU.", None),
    # Jetson R35 de 16 Go, complément vérifié : GPU intégré non qualifié pour la mémoire du poste, essai proposé.
    "gpu_unified_memory_not_qualified": (accelerator(host=JETSON_16_HOST, **cpu_decision(
                                             JETSON_JETPACK5, "gpu_unified_memory_not_qualified", ORIN, "cuda_jetpack5")),
                                         "vert", f"Calcul sur CPU : GPU NVIDIA détecté, {ORIN_TEXT}, qui partage la "
                                         "mémoire du poste avec le CPU ; le calcul sur ce GPU n'est qualifié qu'au-delà "
                                         "de 16 Gio de mémoire totale, et ce poste en a 15 600 Mio.", None,
                                         "La mémoire que ce GPU partage avec le CPU n'est pas mesurable de façon fiable "
                                         "sur ce poste : pour essayer tout de même le GPU, indiquez llm.accelerator: gpu "
                                         "dans le profil, redémarrez (./rag.sh down puis ./rag.sh up) puis lancez "
                                         "./rag.sh selftest."),
}

WINDOWS_CASES = {
    "cpu_no_gpu": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None,
                               **cpu_decision(WINDOWS_IRIS_XE, "no_gpu_discovered")),
                   "vert", "Calcul sur CPU : Ollama n'a découvert aucun GPU utilisable. GPU intégré ignoré par Ollama : "
                   "Intel(R) Iris(R) Xe Graphics (Vulkan).", None, None),
    "gpu_not_retained": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None,
                                     **cpu_decision(DISCOVERING + VULKAN_DISCRETE, "gpu_library_not_retained")),
                         "vert", "Calcul sur CPU : AMD Radeon RX 7600 (Vulkan, GPU dédié, bibliothèques vulkan) détecté "
                         "par Ollama, non retenu par l'atelier, qui n'emploie que les GPU NVIDIA (CUDA).", None, None),
    "gpu_mixed_libraries": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None,
                                        **cpu_decision(DISCOVERING + CUDA_DISCRETE + VULKAN_DISCRETE,
                                                       "gpu_mixed_libraries")),
                            "vert", f"Calcul sur CPU : Ollama a détecté ensemble {RTX_TEXT} et AMD Radeon RX 7600 "
                            "(Vulkan, GPU dédié, bibliothèques vulkan) ; il choisirait lui-même la bibliothèque employée, "
                            "l'atelier reste donc sur CPU.", None,
                            f"Le GPU NVIDIA, {RTX_TEXT}, serait utilisable seul, mais l'atelier ne réserve pas Ollama à "
                            "CUDA faute d'un essai réel de cette configuration. Conservez ce diagnostic pour décider d'un "
                            "essai sur ce poste, ou indiquez llm.accelerator: cpu dans le profil pour ne plus voir cette "
                            "proposition."),
    "gpu_path_not_qualified": (accelerator(host={**WINDOWS_HOST, "windows_nvcuda": True}, libraries=NONE_REQUIRED,
                                           complement=None, **cpu_decision(
                                               DISCOVERING + CUDA_DISCRETE, "gpu_path_not_qualified",
                                               parse_discovery(DISCOVERING + CUDA_DISCRETE)["devices"][0], "cuda_v13")),
                               "vert", f"Calcul sur CPU : GPU NVIDIA détecté, {RTX_TEXT}, sur une voie non qualifiée par "
                               "un essai réel sur ce type de poste.", None,
                               r"GPU NVIDIA détecté, voie non qualifiée : pour l'essayer, indiquez llm.accelerator: gpu "
                               r"dans le profil, redémarrez (.\rag.ps1 down puis .\rag.ps1 up) puis lancez "
                               r".\rag.ps1 selftest."),
    "gpu_trial": (accelerator(host={**WINDOWS_HOST, "windows_nvcuda": True}, libraries=NONE_REQUIRED, complement=None,
                              requested="gpu", running=True, discovery=discovery(DISCOVERING + CUDA_DISCRETE),
                              mode="gpu", reason="gpu_trial",
                              device=parse_discovery(DISCOVERING + CUDA_DISCRETE)["devices"][0], variant="cuda_v13",
                              usage=loaded(100, 100)),
                  "vert", f"Génération sur GPU, essai sur un poste non qualifié : {RTX_TEXT} ; modèle chargé à 100 % "
                  "sur le GPU.", None, None),
    "gpu_requested_unavailable": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None,
                                              requested="gpu", **cpu_decision(WINDOWS_IRIS_XE, "no_gpu_discovered")),
                                  "orange", "Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais "
                                  "Ollama n'a découvert aucun GPU utilisable.",
                                  r"Consultez le journal d'Ollama (.\rag.ps1 logs) ; pour retirer cet avertissement, "
                                  r"indiquez llm.accelerator: auto ou cpu dans le profil, puis redémarrez "
                                  r"(.\rag.ps1 down puis .\rag.ps1 up).", None),
    "discovery_unreadable": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None,
                                         **cpu_decision("", "discovery_unreadable")),
                             "vert", "Calcul sur CPU : la découverte des GPU par Ollama n'a pas pu être lue dans son "
                                     "journal.", None, None),
    "discovery_pending": (accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None),
                          "vert", r"Découverte des GPU par Ollama au prochain démarrage : le mode de calcul (GPU ou CPU) "
                          r"sera choisi à ce moment (.\rag.ps1 up).", None, None),
    # Kit construit avec --without-gpu installé sur un poste muni d'un pilote NVIDIA : le kit, pas le pilote, est en cause.
    "cuda_libraries_absent": (accelerator(host={**WINDOWS_HOST, "windows_nvcuda": True},
                                          libraries=WINDOWS_KIT_WITHOUT_GPU, complement=None,
                                          **cpu_decision(WINDOWS_IRIS_XE, "no_gpu_discovered")),
                              "vert", "Calcul sur CPU : un pilote NVIDIA est installé, mais l'installation d'Ollama de ce "
                              "poste ne contient pas les bibliothèques CUDA vérifiées (kit construit sans GPU, ou fichiers "
                              "retirés depuis) : Ollama ne peut retenir aucun GPU NVIDIA.", None,
                              "Pour essayer ce GPU, réinstallez l'atelier depuis un kit complet, construit sans l'option "
                              r"--without-gpu, puis suivez la proposition de .\rag.ps1 doctor."),
}


@pytest.fixture
def linux_launcher(monkeypatch):
    monkeypatch.setattr(platforms, "WINDOWS", False)
    monkeypatch.setattr(platforms, "LAUNCHER", "./rag.sh")


@pytest.fixture
def windows_launcher(monkeypatch):
    monkeypatch.setattr(platforms, "WINDOWS", True)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1")


def _assert_case(case, state):
    check, level, message, action, proposal = case
    assert check["state"] == state
    item, rubric_proposal, _ = calcul(check)
    assert (item["level"], item["message"], item.get("action")) == (level, message, action)
    assert rubric_proposal == proposal


@pytest.mark.parametrize("state", sorted(LINUX_CASES))
def test_each_state_of_the_calcul_rubric_on_linux(linux_launcher, state):
    _assert_case(LINUX_CASES[state], state)


@pytest.mark.parametrize("state", sorted(WINDOWS_CASES))
def test_each_state_of_the_calcul_rubric_on_windows(windows_launcher, state):
    _assert_case(WINDOWS_CASES[state], state)


def test_every_state_is_covered():
    states = {"cpu_imposed", "cpu_legacy", "cpu_no_gpu", "gpu_libraries_missing", "jetson_unsupported",
              "nvidia_not_retained", "gpu_not_retained", "gpu_mixed_libraries", "gpu_path_not_qualified", "gpu_trial",
              "gpu_requested_unavailable", "gpu_libraries_unverified", "gpu_pending", "gpu_ready", "gpu_in_use",
              "gpu_partial", "gpu_mode_on_cpu", "gpu_fallback", "anomaly_gpu_in_cpu_mode", "discovery_unreadable",
              "discovery_pending", "gpu_rejected_by_ollama", "cuda_libraries_absent", "gpu_unified_memory_not_qualified"}
    assert set(LINUX_CASES) | set(WINDOWS_CASES) == states


def _depth(text: str) -> int:
    deepest = depth = 0
    for character in text:
        depth += {"(": 1, ")": -1}.get(character, 0)
        deepest = max(deepest, depth)
    return deepest


def _all_texts() -> list[str]:
    texts = []
    for cases in (LINUX_CASES, WINDOWS_CASES):
        for check, *_ in cases.values():
            item = rubric(verdict_of(check), "calcul")
            texts += [item["message"], item.get("action") or "", item.get("proposal") or ""]
    return texts


@pytest.mark.parametrize("launcher", ["linux_launcher", "windows_launcher"])
def test_calcul_texts_name_no_internal_decision_and_nest_no_parentheses(request, launcher):
    # Revue J11 (web-5) : textes lus par l'utilisateur, sans identifiant de décision interne ni parenthèses imbriquées.
    from services.runtime.accelerator import (
        BOTH_KEYS_MESSAGE,
        LEGACY_NUM_GPU_MESSAGE,
        REASON_TEXTS,
        VALUE_MESSAGE,
    )

    request.getfixturevalue(launcher)
    extra = [_legacy_r36()[0], _r36_missing()[1], _r36_unreadable()[1], *_vulkan_nvidia_texts(), VALUE_MESSAGE,
             BOTH_KEYS_MESSAGE, LEGACY_NUM_GPU_MESSAGE, verdict_of(LINUX_CASES["gpu_libraries_missing"][0])["summary"]]
    extra += [generation_text({"mode": "gpu" if reason in ("gpu_trial", "gpu_discovered") else "cpu", "reason": reason,
                               "device": ORIN, "variant": "cuda_jetpack5"}) for reason in REASON_TEXTS]
    for text in _all_texts() + extra:
        assert not re.search(r"\bW0\d\d\b", text), text
        assert _depth(text) <= 1, text


# --- Voie non qualifiée : Jetson R36 (JetPack 6), revue J11 runtime-2 et web-3 ----------------------------------------

def _r36_missing() -> tuple[dict, str | None]:
    check = accelerator(host=JETSON_R36_HOST, libraries=LIBRARIES_MISSING_R36, complement=COMPLEMENT_R36,
                        **cpu_decision(JETSON_BASE_ONLY, "no_gpu_discovered"))
    return check, rubric(verdict_of(check), "calcul").get("proposal")


def _legacy_r36() -> tuple[str | None, dict]:
    check = accelerator(requested="cpu", requested_source="legacy_num_gpu", host=JETSON_R36_HOST,
                        libraries=LIBRARIES_MISSING_R36, complement=COMPLEMENT_R36,
                        if_auto={"mode": "cpu", "reason": "no_gpu_discovered"},
                        **cpu_decision(JETSON_BASE_ONLY, "legacy_profile_cpu"))
    return rubric(verdict_of(check), "calcul").get("proposal"), check


def _r36_unreadable() -> tuple[dict, str | None]:
    check = accelerator(host=JETSON_R36_HOST, libraries=LIBRARIES_MISSING_R36, complement=COMPLEMENT_R36,
                        **cpu_decision("", "discovery_unreadable"))
    return check, rubric(verdict_of(check), "calcul").get("proposal")


TRIAL_STEPS = ("lancez ./rag.sh provision --only ollama-gpu (257 Mio à télécharger), indiquez llm.accelerator: gpu dans "
               "le profil, puis ./rag.sh down et ./rag.sh up, et vérifiez la réponse avec ./rag.sh selftest.")


def test_a_jetson_r36_is_offered_a_trial_not_the_gpu_in_auto(linux_launcher):
    # Après provision --only ollama-gpu, le mode auto resterait sur CPU (gpu_path_not_qualified) : aucune promesse.
    check, proposal = _r36_missing()
    assert check["state"] == "gpu_libraries_missing"
    assert proposal == ("Pour essayer le GPU de ce Jetson, sur une voie non qualifiée par un essai réel : " + TRIAL_STEPS
                        + " Pour rester sur CPU sans cette proposition, indiquez llm.accelerator: cpu dans le profil.")
    assert calcul(check)[2] == [{"rubric": "calcul", "text": proposal}]


def test_a_legacy_profile_on_a_jetson_r36_is_offered_a_trial(linux_launcher):
    proposal, check = _legacy_r36()
    assert check["state"] == "cpu_legacy"
    assert proposal == ("Un GPU NVIDIA Jetson est présent (Jetson Linux R36, JetPack 6), sur une voie non qualifiée par "
                        "un essai réel : pour l'essayer, remplacez llm.num_gpu: 0 par llm.accelerator: gpu dans le "
                        "profil, lancez ./rag.sh provision --only ollama-gpu (257 Mio à télécharger), puis ./rag.sh down "
                        "et ./rag.sh up, et vérifiez la réponse avec ./rag.sh selftest.")


def test_an_unreadable_discovery_on_a_jetson_r36_is_offered_a_trial(linux_launcher):
    check, proposal = _r36_unreadable()
    assert check["state"] == "discovery_unreadable"
    assert proposal == "Pour essayer le GPU de ce Jetson, sur une voie non qualifiée par un essai réel : " + TRIAL_STEPS
    # Essai déjà demandé par le profil : la proposition ne redemande pas llm.accelerator: gpu.
    requested = accelerator(host=JETSON_R36_HOST, libraries=LIBRARIES_MISSING_R36, complement=COMPLEMENT_R36,
                            requested="gpu", **cpu_decision("", "discovery_unreadable"))
    assert rubric(verdict_of(requested), "calcul")["proposal"] == (
        "Pour essayer le GPU de ce Jetson, sur une voie non qualifiée par un essai réel : "
        + TRIAL_STEPS.replace("indiquez llm.accelerator: gpu dans le profil, ", ""))
    # Voie qualifiée (R35) : la proposition promet le calcul sur GPU.
    check = accelerator(libraries=LIBRARIES_MISSING, **cpu_decision("", "discovery_unreadable"))
    assert rubric(verdict_of(check), "calcul")["proposal"] == (
        "Pour calculer les réponses sur le GPU de ce Jetson : ./rag.sh provision --only ollama-gpu (283 Mio à "
        "télécharger, 825 Mio une fois extraits), puis ./rag.sh down et ./rag.sh up.")


def test_legacy_profile_proposals_follow_what_auto_would_do(linux_launcher):
    # Jetson R35 sans complément : le profil antérieur est invité à passer en auto et à provisionner le complément.
    jetson = accelerator(requested="cpu", requested_source="legacy_num_gpu", libraries=LIBRARIES_MISSING,
                         if_auto={"mode": "cpu", "reason": "no_gpu_discovered"},
                         **cpu_decision(JETSON_BASE_ONLY, "legacy_profile_cpu"))
    assert calcul(jetson)[1] == (
        "Un GPU NVIDIA Jetson est présent (Jetson Linux R35, JetPack 5) : remplacez llm.num_gpu: 0 par "
        "llm.accelerator: auto dans le profil, lancez ./rag.sh provision --only ollama-gpu (283 Mio à télécharger, "
        "825 Mio une fois extraits), puis ./rag.sh down et ./rag.sh up.")
    # GPU NVIDIA sur une voie non qualifiée : l'essai (gpu) est proposé, pas auto, qui resterait sur CPU.
    rtx = parse_discovery(DISCOVERING + CUDA_DISCRETE)["devices"][0]
    trial = accelerator(requested="cpu", requested_source="legacy_num_gpu", host=WINDOWS_HOST, libraries=NONE_REQUIRED,
                        complement=None, if_auto={"mode": "cpu", "reason": "gpu_path_not_qualified", "device": rtx,
                                                  "variant": "cuda_v13"},
                        **cpu_decision(DISCOVERING + CUDA_DISCRETE, "legacy_profile_cpu", rtx, "cuda_v13"))
    assert calcul(trial)[1] == (
        f"GPU NVIDIA détecté sur une voie non qualifiée : {RTX_TEXT}. Pour l'essayer, remplacez llm.num_gpu: 0 par "
        "llm.accelerator: gpu dans le profil, redémarrez (./rag.sh down puis ./rag.sh up) puis lancez ./rag.sh selftest.")
    # Poste sans GPU utilisable : aucune proposition.
    plain = accelerator(requested="cpu", requested_source="legacy_num_gpu", host=WINDOWS_HOST, libraries=NONE_REQUIRED,
                        complement=None, if_auto={"mode": "cpu", "reason": "no_gpu_discovered"},
                        **cpu_decision(WINDOWS_IRIS_XE, "legacy_profile_cpu"))
    assert calcul(plain) == ({"rubric": "calcul", "level": "vert", "message": "Calcul sur CPU : le profil est antérieur à "
                              "l'accélération GPU (llm.num_gpu: 0)."}, None, [])


# --- GPU intégré d'un Jetson de 16 Go ou de mémoire inconnue : CPU en auto, essai proposé ------------------------------

UNIFIED = ("qualifié seulement au-delà de 16 Gio de mémoire totale, car la mémoire qu'il partage avec le CPU n'est pas "
           "mesurable de façon fiable")


def test_a_jetson_of_16_gb_is_offered_a_trial_announced_by_the_summary(linux_launcher):
    check = LINUX_CASES["gpu_unified_memory_not_qualified"][0]
    item, proposal, announced = calcul(check)
    assert item["level"] == "vert" and announced == [{"rubric": "calcul", "text": proposal}]
    assert verdict_of(check)["summary"] == ("Tout est prêt : services démarrés, index vide, prêt à importer, modèle "
                                            "vérifié. " + PROPOSAL_SUFFIX)


def test_an_unknown_total_memory_keeps_the_integrated_gpu_unqualified(linux_launcher):
    check = accelerator(host={**JETSON_HOST, "memory_total_mib": None}, **cpu_decision(
        JETSON_JETPACK5, "gpu_unified_memory_not_qualified", ORIN, "cuda_jetpack5"))
    assert check["state"] == "gpu_unified_memory_not_qualified"
    item, proposal, _ = calcul(check)
    assert item["message"] == (f"Calcul sur CPU : GPU NVIDIA détecté, {ORIN_TEXT}, qui partage la mémoire du poste avec "
                               "le CPU ; le calcul sur ce GPU n'est qualifié qu'au-delà de 16 Gio de mémoire totale, et "
                               "celle de ce poste n'a pas pu être lue.")
    assert proposal == LINUX_CASES["gpu_unified_memory_not_qualified"][4]


def test_a_jetson_of_16_gb_without_complement_is_offered_a_trial_not_the_gpu_in_auto(linux_launcher):
    # Voie qualifiée (R35), mais auto resterait sur CPU une fois le complément extrait : aucune promesse.
    check = accelerator(host=JETSON_16_HOST, libraries=LIBRARIES_MISSING, **cpu_decision(JETSON_BASE_ONLY,
                                                                                         "no_gpu_discovered"))
    assert check["state"] == "gpu_libraries_missing"
    trial = ("lancez ./rag.sh provision --only ollama-gpu (283 Mio à télécharger, 825 Mio une fois extraits), indiquez "
             "llm.accelerator: gpu dans le profil, puis ./rag.sh down et ./rag.sh up, et vérifiez la réponse avec "
             "./rag.sh selftest.")
    assert calcul(check)[1] == (f"Pour essayer le GPU de ce Jetson, {UNIFIED} : {trial} Pour rester sur CPU sans cette "
                                "proposition, indiquez llm.accelerator: cpu dans le profil.")
    unreadable = accelerator(host={**JETSON_HOST, "memory_total_mib": None}, libraries=LIBRARIES_MISSING,
                             **cpu_decision("", "discovery_unreadable"))
    assert calcul(unreadable)[1] == f"Pour essayer le GPU de ce Jetson, {UNIFIED} : {trial}"


def test_a_legacy_profile_on_a_jetson_of_16_gb_is_offered_a_trial(linux_launcher):
    missing = accelerator(requested="cpu", requested_source="legacy_num_gpu", host=JETSON_16_HOST,
                          libraries=LIBRARIES_MISSING, if_auto={"mode": "cpu", "reason": "no_gpu_discovered"},
                          **cpu_decision(JETSON_BASE_ONLY, "legacy_profile_cpu"))
    assert calcul(missing)[1] == (
        f"Un GPU NVIDIA Jetson est présent (Jetson Linux R35, JetPack 5), {UNIFIED} : pour l'essayer, remplacez "
        "llm.num_gpu: 0 par llm.accelerator: gpu dans le profil, lancez ./rag.sh provision --only ollama-gpu (283 Mio "
        "à télécharger, 825 Mio une fois extraits), puis ./rag.sh down et ./rag.sh up, et vérifiez la réponse avec "
        "./rag.sh selftest.")
    provisioned = accelerator(requested="cpu", requested_source="legacy_num_gpu", host=JETSON_16_HOST,
                              if_auto={"mode": "cpu", "reason": "gpu_unified_memory_not_qualified", "device": ORIN,
                                       "variant": "cuda_jetpack5"},
                              **cpu_decision(JETSON_JETPACK5, "legacy_profile_cpu", ORIN, "cuda_jetpack5"))
    assert calcul(provisioned)[1] == (
        f"GPU NVIDIA détecté, {ORIN_TEXT}, {UNIFIED}. Pour l'essayer, remplacez llm.num_gpu: 0 par llm.accelerator: gpu "
        "dans le profil, redémarrez (./rag.sh down puis ./rag.sh up) puis lancez ./rag.sh selftest.")


def test_a_jetson_of_16_gb_on_trial_runs_on_its_gpu(linux_launcher):
    check = gpu_instance(host=JETSON_16_HOST, requested="gpu", reason="gpu_trial", usage=loaded(3107811491, 3107811491))
    assert check["state"] == "gpu_trial"
    assert calcul(check)[0]["message"] == (f"Génération sur GPU, essai sur un poste non qualifié : {ORIN_TEXT} ; modèle "
                                           "chargé à 100 % sur le GPU.")


def test_gpu_requested_on_a_jetson_without_complement_points_to_provision(linux_launcher):
    check = accelerator(requested="gpu", libraries=LIBRARIES_MISSING)
    assert check["state"] == "gpu_requested_unavailable"
    item, proposal, _ = calcul(check)
    assert item["level"] == "orange" and proposal is None
    assert item["message"] == ("Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais les bibliothèques "
                               "GPU d'Ollama pour ce Jetson (Jetson Linux R35, JetPack 5) ne sont pas installées.")
    assert item["action"] == ("Lancez ./rag.sh provision --only ollama-gpu (283 Mio à télécharger, 825 Mio une fois "
                              "extraits), puis ./rag.sh down et ./rag.sh up ; sinon, indiquez llm.accelerator: auto "
                              "ou cpu dans le profil.")


def test_gpu_requested_beside_other_libraries_names_each_gpu_without_nesting(windows_launcher):
    amd = accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None, requested="gpu",
                      **cpu_decision(DISCOVERING + VULKAN_DISCRETE, "gpu_library_not_retained"))
    assert calcul(amd)[0]["message"] == (
        "Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais le seul GPU détecté, AMD Radeon RX 7600 "
        "(Vulkan, GPU dédié, bibliothèques vulkan), n'emploie pas CUDA, seule bibliothèque retenue par l'atelier.")
    mixed = accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None, requested="gpu",
                        **cpu_decision(DISCOVERING + CUDA_DISCRETE + VULKAN_DISCRETE, "gpu_mixed_libraries"))
    assert calcul(mixed)[0]["message"] == (
        f"Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais un GPU NVIDIA, {RTX_TEXT}, côtoie un "
        "GPU d'une autre bibliothèque, AMD Radeon RX 7600 (Vulkan, GPU dédié, bibliothèques vulkan), et Ollama "
        "choisirait lui-même entre les deux.")


# --- GPU NVIDIA vu seulement par Vulkan (revue J11 runtime-7) ---------------------------------------------------------

def _vulkan_nvidia(**fields) -> dict:
    return accelerator(**{"host": {**WINDOWS_HOST, "windows_nvcuda": True}, "libraries": NONE_REQUIRED,
                          "complement": None, **cpu_decision(DISCOVERING + NVIDIA_VULKAN, "gpu_library_not_retained"),
                          **fields})


def _vulkan_nvidia_texts() -> list[str]:
    texts = []
    for check in (_vulkan_nvidia(), _vulkan_nvidia(requested="gpu")):
        item = rubric(verdict_of(check), "calcul")
        texts += [item["message"], item.get("action") or "", item.get("proposal") or ""]
    return texts


def test_a_nvidia_gpu_seen_only_through_vulkan_points_to_the_driver(windows_launcher):
    check = _vulkan_nvidia()
    assert check["state"] == "nvidia_not_retained"
    item, proposal, announced = calcul(check)
    assert item == {"rubric": "calcul", "level": "vert", "message": (
        f"Calcul sur CPU : {GTX_TEXT} n'est vu par Ollama que par Vulkan ; CUDA ne l'a pas retenu, à cause du pilote ou "
        "de la capacité de calcul du GPU.")}
    assert proposal == DRIVER_PROPOSAL.format(logs=r".\rag.ps1 logs") and announced == []
    requested = _vulkan_nvidia(requested="gpu")
    assert requested["state"] == "gpu_requested_unavailable"
    assert calcul(requested)[0]["message"] == (
        f"Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais le GPU NVIDIA détecté, {GTX_TEXT}, n'est "
        "vu par Ollama que par Vulkan : CUDA ne l'a pas retenu, à cause du pilote ou de la capacité de calcul du GPU.")
    # status et selftest : la raison ne dit plus « GPU non NVIDIA » pour un GPU NVIDIA.
    device = parse_discovery(DISCOVERING + NVIDIA_VULKAN)["devices"][0]
    assert generation_text({"mode": "cpu", "reason": "gpu_library_not_retained", "device": device}) == (
        "génération sur CPU, GPU NVIDIA vu seulement par Vulkan, CUDA ne l'a pas retenu : pilote ou capacité de calcul")


# --- Lecture de la colonne PROCESSOR (revue J11 web-4) ----------------------------------------------------------------

def test_an_unknown_share_of_the_model_reads_as_undetermined(linux_launcher):
    trial = WINDOWS_CASES["gpu_trial"][0]
    item, _, _ = calcul({**trial, "usage": loaded(100, 101)})
    assert item["message"] == (f"Génération sur GPU, essai sur un poste non qualifié : {RTX_TEXT} ; répartition du "
                               "modèle entre GPU et CPU non déterminée par Ollama.")
    partial = LINUX_CASES["gpu_partial"][0]
    item, _, _ = calcul({**partial, "usage": [{"model": MODEL, "size": 0, "size_vram": 5, "processor": "Unknown"}]})
    assert item["message"] == (f"Génération sur GPU : {ORIN_TEXT} ; répartition du modèle entre GPU et CPU non "
                               "déterminée par Ollama.")
    anomaly = LINUX_CASES["anomaly_gpu_in_cpu_mode"][0]
    item, _, _ = calcul({**anomaly, "usage": loaded(100, 101)})
    assert item["message"] == "Anomalie : le modèle est chargé sur le GPU alors que l'atelier calcule sur CPU."


# --- Découverte consignée par provision, illisible ou remplacée (revue J11 runtime-3, invariants-03) ------------------

PROBE_LOG = ".runtime/provision-service/ollama-probe.log"
PROBE_ERROR = "OSError : [Errno 98] Address already in use"


def _unreadable_probe(error: str | None = PROBE_ERROR, **fields) -> dict:
    record = {"source": "provision", "utc": "2026-10-02T09:00:00+00:00", "log": PROBE_LOG, "status": "unreadable",
              "devices": [], "dropped": [], **({"error": error} if error else {})}
    return accelerator(discovery=record, mode="cpu", reason="discovery_unreadable", **fields)


def test_an_unreadable_provision_discovery_points_to_the_probe_log_and_its_error(linux_launcher):
    check = _unreadable_probe()
    assert check["state"] == "discovery_unreadable"
    item, _, _ = calcul(check)
    assert item == {"rubric": "calcul", "level": "orange", "message": (
        "Calcul sur CPU : la découverte des GPU n'a pas pu être lue dans le journal d'Ollama du provisionnement ; "
        f"erreur consignée : {PROBE_ERROR}."), "action": (
        f"Consultez ce journal ({PROBE_LOG}) ; la découverte sera relevée au prochain démarrage (./rag.sh up), "
        "l'atelier fonctionne sur CPU d'ici là.")}


def test_an_unreadable_provision_discovery_on_windows_cites_the_windows_path(windows_launcher):
    check = _unreadable_probe(error=None, host={**WINDOWS_HOST, "windows_nvcuda": True}, libraries=NONE_REQUIRED,
                              complement=None)
    item, _, _ = calcul(check)
    assert item["message"] == ("Calcul sur CPU : la découverte des GPU n'a pas pu être lue dans le journal d'Ollama du "
                               "provisionnement.")
    assert item["action"] == (r"Consultez ce journal (.runtime\provision-service\ollama-probe.log) ; la découverte sera "
                              r"relevée au prochain démarrage (.\rag.ps1 up), l'atelier fonctionne sur CPU d'ici là.")


def test_a_rejection_read_in_the_provision_log_points_to_that_log(linux_launcher):
    record = {**discovery(JETSON_BASE_ONLY, "provision"), "log": ".runtime/provision-service/ollama-pull.log"}
    check = accelerator(discovery=record, mode="cpu", reason="no_gpu_discovered")
    assert check["state"] == "gpu_rejected_by_ollama"
    assert calcul(check)[0]["action"] == (
        "Consultez le journal d'Ollama du provisionnement (.runtime/provision-service/ollama-pull.log) : il indique "
        "pourquoi le GPU a été écarté. Pour ne plus voir cet avertissement, indiquez llm.accelerator: cpu dans le profil.")


def test_a_failed_probe_that_did_not_replace_the_last_discovery_is_mentioned(windows_launcher):
    superseded = {"source": "provision", "utc": "2026-10-02T09:00:00+00:00", "log": PROBE_LOG, "error": PROBE_ERROR}
    check = accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None, mode="cpu",
                        reason="no_gpu_discovered", discovery={**discovery(WINDOWS_IRIS_XE), "superseded": superseded})
    assert check["state"] == "cpu_no_gpu"
    item, _, _ = calcul(check)
    assert item["level"] == "vert" and item["message"] == (
        "Calcul sur CPU : Ollama n'a découvert aucun GPU utilisable. GPU intégré ignoré par Ollama : Intel(R) Iris(R) Xe "
        "Graphics (Vulkan). La sonde de découverte du provisionnement du 02/10/2026 09:00:00 UTC a échoué : "
        f"{PROBE_ERROR}. La découverte précédente, lisible, reste retenue.")
    assert verdict_of(check)["summary"] == doctor_verdict(healthy())["summary"]


@pytest.mark.parametrize(("fields", "message"), [
    ({"discovery_stale": True},
     r"Les bibliothèques GPU d'Ollama ont changé depuis la dernière découverte des GPU : elle sera refaite au prochain "
     r"démarrage, qui choisira le mode de calcul, GPU ou CPU (.\rag.ps1 up)."),
    ({"running": True, "mode": "cpu", "reason": "legacy_profile_cpu", "instance_predates_accelerator": True},
     r"Calcul sur CPU : l'instance en marche a démarré avant l'accélération GPU. Le mode de calcul, GPU ou CPU, sera "
     r"choisi à son redémarrage (.\rag.ps1 down puis .\rag.ps1 up)."),
    ({"running": True, "mode": "cpu", "reason": "no_gpu_discovered", "discovery_stale": True},
     r"Calcul sur CPU : les bibliothèques GPU d'Ollama ont changé depuis le démarrage de l'instance en marche. Le mode "
     r"de calcul, GPU ou CPU, sera choisi à son redémarrage (.\rag.ps1 down puis .\rag.ps1 up)."),
])
def test_a_discovery_still_to_come_says_which_command_brings_it(windows_launcher, fields, message):
    check = accelerator(host=WINDOWS_HOST, libraries=NONE_REQUIRED, complement=None, **fields)
    assert check["state"] == "discovery_pending"
    assert calcul(check)[0] == {"rubric": "calcul", "level": "vert", "message": message}


def test_a_gpu_instance_whose_usage_was_not_read_does_not_claim_an_unloaded_model(linux_launcher):
    item, _, _ = calcul(gpu_instance(usage=None))
    assert item["message"] == (f"Génération sur GPU : {ORIN_TEXT} ; chargement du modèle non vérifié (Ollama n'a pas "
                               "répondu à /api/ps).")


def test_a_failed_check_is_orange_and_says_what_to_do(linux_launcher):
    item, _, _ = calcul({"state": "check_failed", "error": "JSONDecodeError : verrou illisible"})
    assert item == {"rubric": "calcul", "level": "orange",
                    "message": "Mode de calcul non établi (JSONDecodeError : verrou illisible).",
                    "action": "Relancez ./rag.sh doctor ; si l'état persiste, consultez le journal d'Ollama (./rag.sh logs)."}


def test_a_proposal_never_changes_the_level_and_is_announced_in_the_summary(linux_launcher):
    check = LINUX_CASES["gpu_libraries_missing"][0]
    result = healthy()
    result["checks"]["accelerator"] = check
    verdict = doctor_verdict(result)
    assert verdict["level"] == "vert" and len(verdict["rubrics"]) == 8 and verdict["rubrics"][-1]["rubric"] == "calcul"
    assert verdict["summary"] == ("Tout est prêt : services démarrés, index vide, prêt à importer, modèle vérifié. "
                                  "Proposition : accélération GPU disponible, voir la rubrique calcul.")
    result["checks"]["cold_admission"]["generation"].update(available_mib=3687.94, admissible_now=False)
    assert doctor_verdict(result)["summary"] == ("Atelier utilisable, avec réserve : mémoire. Proposition : accélération "
                                                 "GPU disponible, voir la rubrique calcul.")
    result["checks"]["tesseract_binary"] = False
    verdict = doctor_verdict(result)
    assert verdict["level"] == "rouge" and verdict["summary"] == "Atelier inutilisable en l'état : programme, mémoire."
    assert verdict["proposals"] == [{"rubric": "calcul", "text": LINUX_CASES["gpu_libraries_missing"][4]}]


@pytest.mark.parametrize("state", sorted(INFORMATIVE))
def test_an_informative_proposal_stays_in_the_rubric_and_is_not_announced(windows_launcher, state):
    # Revue J11 (runtime-5, web-2, invariants-01) : aucune action de l'atelier ne mène au GPU dans ces états.
    check = {**LINUX_CASES, **WINDOWS_CASES}[state][0]
    verdict = verdict_of(check)
    assert rubric(verdict, "calcul").get("proposal")
    assert verdict["proposals"] == [] and verdict["summary"] == doctor_verdict(healthy())["summary"]


def test_windows_host_without_usable_gpu_keeps_its_level_and_summary(windows_launcher):
    # Invariant Windows (W025) : poste de référence (iGPU Iris Xe écarté par Ollama), profil auto ; une rubrique verte
    # de plus, ni réserve ni proposition.
    before = doctor_verdict(healthy())
    result = healthy()
    result["checks"]["accelerator"] = WINDOWS_CASES["cpu_no_gpu"][0]
    after = doctor_verdict(result)
    assert (after["level"], after["summary"]) == (before["level"], before["summary"])
    assert after["rubrics"][:7] == before["rubrics"] and len(after["rubrics"]) == 8
    assert after["rubrics"][7]["level"] == "vert" and after["proposals"] == []
    assert "calcul" not in levels(before)


@pytest.mark.parametrize("libraries", [NONE_REQUIRED, WINDOWS_KIT_WITHOUT_GPU])
def test_windows_host_with_nvcuda_but_no_retained_gpu_keeps_the_summary_of_head(windows_launcher, libraries):
    # nvcuda.dll présent (pilote ancien, capacité trop basse, ou kit sans GPU) et aucun GPU retenu par Ollama : même
    # niveau et même résumé qu'à la révision 0dbae7b ; la proposition reste informative, dans la rubrique.
    before = doctor_verdict(healthy())
    check = accelerator(host={**WINDOWS_HOST, "windows_nvcuda": True}, libraries=libraries, complement=None,
                        **cpu_decision(WINDOWS_IRIS_XE, "no_gpu_discovered"))
    assert check["state"] in INFORMATIVE
    after = verdict_of(check)
    assert (after["level"], after["summary"]) == (before["level"], before["summary"])
    assert after["summary"] == "Tout est prêt : services démarrés, index vide, prêt à importer, modèle vérifié."
    assert after["rubrics"][:7] == before["rubrics"] and after["proposals"] == []


def test_generation_text_for_selftest_and_status():
    assert generation_text({"mode": "gpu", "reason": "gpu_discovered", "device": ORIN, "variant": "cuda_jetpack5"}) == (
        f"génération sur GPU, {ORIN_TEXT}")
    rtx = parse_discovery(DISCOVERING + CUDA_DISCRETE)["devices"][0]
    assert generation_text({"mode": "gpu", "reason": "gpu_trial", "device": rtx, "variant": "cuda_v13"}) == (
        f"génération sur GPU, {RTX_TEXT} ; essai demandé par le profil (llm.accelerator: gpu) sur une voie ou un poste non qualifiés")
    assert generation_text({"mode": "cpu", "reason": "no_gpu_discovered"}) == (
        "génération sur CPU, aucun GPU utilisable découvert par Ollama")
    assert generation_text({"mode": "cpu", "reason": "legacy_profile_cpu"}) == (
        "génération sur CPU, profil antérieur à l'accélération GPU (llm.num_gpu: 0)")
    assert generation_text({"mode": "cpu", "reason": "imposed_by_profile"}) == (
        "génération sur CPU, imposée par le profil (llm.accelerator: cpu)")
