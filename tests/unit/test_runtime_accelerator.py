"""Accélération GPU (W024, W025) : profil, indices du poste, découverte journalisée par Ollama, résolution du mode.

Les extraits de journaux sont réels (Ollama 0.35.0) sauf mention « synthétique » : poste Windows de référence (iGPU Intel
Iris Xe écarté, 30/09), Jetson AGX Orin sans complément (instance du chantier, 01/10) et avec le complément officiel
`jetpack5` (essai réel du 01/10). Les lignes de débogage citées gardent leur forme, chemins du poste remplacés par
`<essai>`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from services.runtime import accelerator, supervisor
from services.runtime.accelerator import (
    BOTH_KEYS_MESSAGE,
    LEGACY_NUM_GPU_MESSAGE,
    QUALIFIED_GPU_PATHS,
    REASON_TEXTS,
    VALUE_MESSAGE,
    AcceleratorProfileError,
    describe_device,
    device_variant,
    discovery_record,
    entries_for_host,
    is_nvidia,
    l4t_major,
    libraries_signature,
    parse_discovery,
    processor_label,
    profile_accelerator,
    read_discovery,
    reason_text,
    resolve_mode,
    verified_libraries,
)

ROOT = Path(__file__).resolve().parents[2]

# Poste Windows de référence (RAG_Local_Agents/reports/cpu-pilot-first.service.log, lignes 5 à 10).
WINDOWS_IRIS_XE = (
    'time=2026-09-30T01:19:12.265Z level=INFO source=routes.go:2159 msg="Listening on 127.0.0.1:11444 (version 0.35.0)"\n'
    'time=2026-09-30T01:19:12.266Z level=INFO source=model_recommendations.go:177 msg="model recommendations cache sleep '
    'scheduled" wait=4h39m30.39077986s consecutive_failures=0\n'
    'time=2026-09-30T01:19:12.269Z level=INFO source=runner.go:60 msg="discovering available GPUs..."\n'
    'time=2026-09-30T01:19:15.477Z level=INFO source=runner.go:405 msg="dropping integrated GPU; to enable, set '
    'OLLAMA_IGPU_ENABLE=1" id=0 library=Vulkan compute=0.0 name=Vulkan0 description="Intel(R) Iris(R) Xe Graphics" pci_id=""\n'
    'time=2026-09-30T01:19:15.478Z level=INFO source=types.go:50 msg="inference compute" id=cpu library=cpu compute="" '
    'name=cpu description=cpu libdirs=ollama driver="" pci_id="" type="" total="15.7 GiB" available="6.0 GiB"\n'
    'time=2026-09-30T01:19:15.479Z level=INFO source=routes.go:2209 msg="vram-based default context" total_vram="0 B" '
    "default_num_ctx=4096\n")

# Jetson AGX Orin, archive de base seule : cuda_v12 et cuda_v13 échouent, Ollama se replie sur CPU (instance 251a33d7).
JETSON_BASE_ONLY = (
    'time=2026-10-01T18:54:05.253+01:00 level=INFO source=routes.go:2159 msg="Listening on 127.0.0.1:11434 (version 0.35.0)"\n'
    'time=2026-10-01T18:54:05.254+01:00 level=INFO source=runner.go:60 msg="discovering available GPUs..."\n'
    'time=2026-10-01T18:54:12.291+01:00 level=INFO source=types.go:50 msg="inference compute" id=cpu library=cpu compute="" '
    'name=cpu description=cpu libdirs=ollama driver="" pci_id="" type="" total="61.3 GiB" available="48.4 GiB"\n'
    'time=2026-10-01T18:54:12.291+01:00 level=INFO source=routes.go:2209 msg="vram-based default context" total_vram="0 B" '
    "default_num_ctx=4096\n")

# Jetson AGX Orin avec le complément officiel jetpack5 (run2-ollama-test-serve.log, OLLAMA_DEBUG=1).
JETSON_JETPACK5 = (
    'time=2026-10-01T21:49:09.541+01:00 level=INFO source=routes.go:2159 msg="Listening on 127.0.0.1:11464 (version 0.35.0)"\n'
    'time=2026-10-01T21:49:09.542+01:00 level=INFO source=runner.go:60 msg="discovering available GPUs..."\n'
    'time=2026-10-01T21:49:16.770+01:00 level=DEBUG source=runner.go:131 msg="evaluating which, if any, devices to filter '
    'out" initial_count=1\n'
    'time=2026-10-01T21:49:16.770+01:00 level=DEBUG source=runner.go:153 msg="verifying if device is supported" '
    "library=<essai>/ollama/lib/ollama/cuda_jetpack5 description=Orin compute=8.7 id=0 pci_id=0000:00:00.0\n"
    'time=2026-10-01T21:49:26.663+01:00 level=DEBUG source=runner.go:42 msg="GPU bootstrap discovery took" '
    "duration=17.121947286s\n"
    'time=2026-10-01T21:49:26.663+01:00 level=INFO source=types.go:32 msg="inference compute" id=0 filter_id=0 library=CUDA '
    "compute=8.7 name=CUDA0 description=Orin libdirs=ollama,cuda_jetpack5 driver=11.4 pci_id=0000:00:00.0 type=iGPU "
    'total="61.3 GiB" available="45.1 GiB"\n'
    'time=2026-10-01T21:49:26.663+01:00 level=INFO source=routes.go:2209 msg="vram-based default context" '
    'total_vram="61.3 GiB" default_num_ctx=262144\n'
    '[GIN] 2026/10/01 - 21:49:26 | 200 |     181.091µs |       127.0.0.1 | GET      "/api/version"\n')

# Synthétiques, au format de discover/types.go (v0.35.0, l. 32-45) : GPU NVIDIA dédié (zip Windows, cuda_v13) et GPU
# AMD dédié vu par Vulkan.
DISCOVERING = 'time=2026-10-02T09:00:00.000Z level=INFO source=runner.go:60 msg="discovering available GPUs..."\n'
CUDA_DISCRETE = ('time=2026-10-02T09:00:05.000Z level=INFO source=types.go:32 msg="inference compute" id=0 filter_id=0 '
                 'library=CUDA compute=8.9 name=CUDA0 description="NVIDIA GeForce RTX 4060" libdirs=ollama,cuda_v13 '
                 'driver=13.0 pci_id=0000:01:00.0 type=discrete total="8.0 GiB" available="7.1 GiB"\n')
VULKAN_DISCRETE = ('time=2026-10-02T09:00:05.000Z level=INFO source=types.go:32 msg="inference compute" id=0 filter_id="" '
                   'library=Vulkan compute=0.0 name=Vulkan0 description="AMD Radeon RX 7600" libdirs=ollama,vulkan '
                   'driver=0.0 pci_id=0000:03:00.0 type=discrete total="8.0 GiB" available="7.5 GiB"\n')

ORIN = {"id": "0", "library": "CUDA", "compute": "8.7", "name": "CUDA0", "description": "Orin",
        "libdirs": ["ollama", "cuda_jetpack5"], "driver": "11.4", "pci_id": "0000:00:00.0", "type": "iGPU",
        "total": "61.3 GiB", "available": "45.1 GiB"}

REASONS = ("imposed_by_profile", "legacy_profile_cpu", "discovery_unreadable", "no_gpu_discovered",
           "gpu_library_not_retained", "gpu_mixed_libraries", "gpu_libraries_unverified", "gpu_path_not_qualified",
           "gpu_unified_memory_not_qualified", "gpu_trial", "gpu_discovered")

# Mémoire totale du poste de l'essai réel du 02/10 (MemTotal 64 307 708 kB), en Mio ; Jetson de 16 Go et de 32 Go simulés.
TRIAL_HOST_MIB = 62800
JETSON_16_MIB = 15600
JETSON_32_MIB = 30600


# --- Découverte journalisée -------------------------------------------------------------------------------------------

def test_windows_iris_xe_is_cpu_only_with_the_integrated_vulkan_gpu_dropped():
    discovery = parse_discovery(WINDOWS_IRIS_XE)
    assert discovery == {"status": "cpu_only", "devices": [], "dropped": [
        {"reason": "integrated_gpu", "id": "0", "library": "Vulkan", "compute": "0.0", "name": "Vulkan0",
         "description": "Intel(R) Iris(R) Xe Graphics", "pci_id": ""}]}


@pytest.mark.skipif(not (ROOT / "RAG_Local_Agents/reports/cpu-pilot-first.service.log").is_file(),
                    reason="journal Windows de référence absent de cet arbre")
def test_the_whole_windows_reference_log_gives_the_same_discovery():
    # Journal complet du pilote Windows (399 lignes, fins de ligne mêlées, sorties de llama-server) : même résultat.
    discovery = read_discovery(ROOT / "RAG_Local_Agents/reports/cpu-pilot-first.service.log")
    assert discovery == parse_discovery(WINDOWS_IRIS_XE)


def test_jetson_with_the_jetpack5_complement_discovers_the_integrated_cuda_gpu():
    discovery = parse_discovery(JETSON_JETPACK5)
    assert discovery == {"status": "gpu", "devices": [ORIN], "dropped": []}
    assert device_variant(discovery["devices"][0]) == "cuda_jetpack5"


def test_jetson_with_the_base_archive_only_is_cpu_only():
    assert parse_discovery(JETSON_BASE_ONLY) == {"status": "cpu_only", "devices": [], "dropped": []}


def test_crlf_line_endings_give_the_same_discovery():
    for text in (JETSON_JETPACK5, WINDOWS_IRIS_XE):
        assert parse_discovery(text.replace("\n", "\r\n")) == parse_discovery(text)


def test_dedicated_cuda_and_vulkan_devices_are_all_reported():
    discovery = parse_discovery(DISCOVERING + CUDA_DISCRETE + VULKAN_DISCRETE)
    assert discovery["status"] == "gpu"
    assert [(item["library"], item["description"], item["type"], item["libdirs"]) for item in discovery["devices"]] == [
        ("CUDA", "NVIDIA GeForce RTX 4060", "discrete", ["ollama", "cuda_v13"]),
        ("Vulkan", "AMD Radeon RX 7600", "discrete", ["ollama", "vulkan"])]


@pytest.mark.parametrize("text", [
    "",
    "Error: listen tcp 127.0.0.1:11444: bind: address already in use\n",
    # Démarrage interrompu pendant la découverte.
    JETSON_JETPACK5.split("level=DEBUG source=runner.go:42")[0] + "\n",
    # Dernière ligne en cours d'écriture : elle n'est pas interprétée.
    DISCOVERING + CUDA_DISCRETE.rstrip("\n"),
    DISCOVERING + CUDA_DISCRETE.split(" type=discrete")[0] + "\n",
    # Ligne de découverte sans le début du bloc (journal tronqué par le haut).
    CUDA_DISCRETE,
])
def test_empty_truncated_or_incomplete_logs_are_unreadable(text):
    assert parse_discovery(text)["status"] == "unreadable"


@pytest.mark.parametrize(("first", "second", "status"), [
    (JETSON_BASE_ONLY, JETSON_JETPACK5, "gpu"),
    (JETSON_JETPACK5, JETSON_BASE_ONLY, "cpu_only"),
    (JETSON_JETPACK5, DISCOVERING, "unreadable"),
])
def test_only_the_last_start_of_an_appended_log_counts(first, second, status):
    # Le journal d'Ollama est ouvert en ajout : un redémarrage ajoute un bloc, et seul le dernier décrit le serveur.
    assert parse_discovery(first + second)["status"] == status


def test_read_discovery_reads_a_bounded_tail(tmp_path):
    log = tmp_path / "ollama.log"
    assert read_discovery(log) == {"status": "unreadable", "devices": [], "dropped": []}
    filler = b"[GIN] 2026/10/01 - 21:50:00 | 200 | 1ms | 127.0.0.1 | POST \"/api/chat\"\n" * 20000
    log.write_bytes(filler + JETSON_JETPACK5.encode() + b"\xff\xfe octets invalides\n" + filler[:16384])
    assert read_discovery(log)["devices"] == [ORIN]
    # Bloc de découverte sorti de la fenêtre lue : rien n'est inventé.
    assert read_discovery(log, limit=8192)["status"] == "unreadable"


# --- Profil ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("llm", "expected"), [
    ({"accelerator": "auto"}, {"requested": "auto", "requested_source": "profile"}),
    ({"accelerator": "cpu"}, {"requested": "cpu", "requested_source": "profile"}),
    ({"accelerator": "gpu"}, {"requested": "gpu", "requested_source": "profile"}),
    ({"num_gpu": 0}, {"requested": "cpu", "requested_source": "legacy_num_gpu"}),
    ({}, {"requested": "auto", "requested_source": "default"}),
])
def test_profile_forms_are_resolved(llm, expected):
    assert profile_accelerator({"llm": {"model": "qwen3.5:4b-text", **llm}}) == expected


@pytest.mark.parametrize(("llm", "message", "keys"), [
    ({"accelerator": "AUTO"}, VALUE_MESSAGE, ("llm.accelerator",)),
    ({"accelerator": ""}, VALUE_MESSAGE, ("llm.accelerator",)),
    ({"accelerator": None}, VALUE_MESSAGE, ("llm.accelerator",)),
    ({"accelerator": True}, VALUE_MESSAGE, ("llm.accelerator",)),
    ({"num_gpu": 1}, LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",)),
    ({"num_gpu": -1}, LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",)),
    ({"num_gpu": False}, LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",)),
    ({"num_gpu": 0.0}, LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",)),
    ({"num_gpu": "0"}, LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",)),
    ({"num_gpu": 0, "accelerator": "cpu"}, BOTH_KEYS_MESSAGE, ("llm.accelerator", "llm.num_gpu")),
])
def test_invalid_profile_forms_are_refused_with_their_message(llm, message, keys):
    with pytest.raises(AcceleratorProfileError) as refused:
        profile_accelerator({"llm": llm})
    assert str(refused.value) == message and refused.value.keys == keys
    assert isinstance(refused.value, ValueError)


def test_refusal_messages_name_the_three_values_and_the_replacement():
    assert VALUE_MESSAGE == ("llm.accelerator accepte auto (GPU utilisé s'il est détecté sur un poste qualifié, CPU "
                             "sinon), cpu (calcul CPU imposé) ou gpu (essai du GPU sur un poste non qualifié).")
    assert BOTH_KEYS_MESSAGE == "llm.num_gpu est remplacé par llm.accelerator : retirez llm.num_gpu du profil."
    # Message lu par l'utilisateur (refus de up, erreur invalid_profile de l'API) : aucun identifiant de décision.
    assert LEGACY_NUM_GPU_MESSAGE == ("llm.num_gpu n'accepte que 0 (profil antérieur à l'accélération GPU) ; pour utiliser "
                                      "le GPU, remplacez-le par llm.accelerator: auto, ou gpu pour l'essayer sur un poste "
                                      "non qualifié.")
    with pytest.raises(AcceleratorProfileError) as refused:
        profile_accelerator({"app": {}})
    assert refused.value.keys == ("llm",)


def test_the_shipped_profile_and_its_documentary_copy_are_accepted():
    for path in (ROOT / "config/local16.yaml", ROOT / "RAG_Local_Agents/config/local16.yaml"):
        requested = profile_accelerator(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert requested["requested"] in ("auto", "cpu")


# --- Indices du poste --------------------------------------------------------------------------------------------------

# Contenu réel de /etc/nv_tegra_release sur le poste de référence (L4T R35.4.1).
TEGRA_R35 = (b"# R35 (release), REVISION: 4.1, GCID: 33958178, BOARD: t186ref, EABI: aarch64, "
             b"DATE: Tue Aug  1 19:57:35 UTC 2023\n")


@pytest.mark.parametrize(("content", "expected"), [
    (TEGRA_R35, 35),
    (TEGRA_R35.replace(b" R35 ", b" R36 "), 36),
    (TEGRA_R35.replace(b" R35 ", b" R38 "), 38),
    (b"# R35(release), REVISION: 4.1\n", None),
    (b"\x00\xff", None),
])
def test_l4t_major_uses_the_expression_of_ollama(tmp_path, content, expected):
    path = tmp_path / "nv_tegra_release"
    path.write_bytes(content)
    assert l4t_major(path) == expected


def test_l4t_major_without_the_file_is_none(tmp_path):
    assert l4t_major(tmp_path / "absent") is None


def _linux_host(tmp_path, monkeypatch, platform="linux-aarch64", release=TEGRA_R35):
    monkeypatch.setattr(accelerator, "platform_id", lambda: platform)
    tegra = tmp_path / "nv_tegra_release"
    if release is not None:
        tegra.write_bytes(release)
    driver = tmp_path / "nvidia-version"
    driver.write_text("NVRM version: NVIDIA UNIX Open Kernel Module for aarch64  35.4.1  Release Build\nGCC version\n",
                      encoding="utf-8")
    node = tmp_path / "nvhost-gpu"
    node.write_bytes(b"")
    meminfo = tmp_path / "meminfo"
    meminfo.write_bytes(b"MemTotal:       64307708 kB\nMemFree:          748956 kB\nMemAvailable:   46284820 kB\n")
    monkeypatch.setattr(accelerator, "MEMINFO", meminfo)
    monkeypatch.setattr(accelerator, "TEGRA_RELEASE", tegra)
    monkeypatch.setattr(accelerator, "NVIDIA_DRIVER_VERSION", driver)
    monkeypatch.setattr(accelerator, "GPU_DEVICE_NODES", (str(node), str(tmp_path / "nvidia0")))
    return node


def test_jetson_signals_name_the_jetpack_variant_and_the_device_nodes(tmp_path, monkeypatch):
    node = _linux_host(tmp_path, monkeypatch)
    signals = accelerator.host_signals()
    assert signals == {"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5",
                       "nvidia_kernel_driver": "NVRM version: NVIDIA UNIX Open Kernel Module for aarch64  35.4.1  Release Build",
                       "gpu_nodes": {str(node): {"exists": True, "access": True},
                                     str(tmp_path / "nvidia0"): {"exists": False, "access": False}},
                       "windows_nvcuda": None, "memory_total_mib": TRIAL_HOST_MIB}


@pytest.mark.parametrize(("platform", "release", "l4t", "jetpack"), [
    ("linux-aarch64", TEGRA_R35.replace(b" R35 ", b" R38 "), 38, None),
    ("linux-aarch64", None, None, None),
    # Ollama ne cherche de variante JetPack que sous Linux arm64.
    ("linux-x86_64", TEGRA_R35, 35, None),
])
def test_signals_without_a_published_jetpack_variant(tmp_path, monkeypatch, platform, release, l4t, jetpack):
    _linux_host(tmp_path, monkeypatch, platform, release)
    signals = accelerator.host_signals()
    assert (signals["platform"], signals["l4t_major"], signals["jetpack"]) == (platform, l4t, jetpack)


@pytest.mark.parametrize("nvcuda", [True, False])
def test_windows_signals_only_look_for_nvcuda(tmp_path, monkeypatch, nvcuda):
    monkeypatch.setattr(accelerator, "platform_id", lambda: "windows-x86_64")
    monkeypatch.setattr(accelerator, "TEGRA_RELEASE", tmp_path / "ne-doit-pas-etre-lu")
    monkeypatch.setattr(accelerator, "read_memory_total_mib", lambda path=None: pytest.fail("mémoire lue sous Windows"))
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    if nvcuda:
        (tmp_path / "System32").mkdir()
        (tmp_path / "System32/nvcuda.dll").write_bytes(b"MZ")
    assert accelerator.host_signals() == {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None,
                                          "nvidia_kernel_driver": None, "gpu_nodes": {}, "windows_nvcuda": nvcuda,
                                          "memory_total_mib": None}


def test_host_signals_never_raise(monkeypatch):
    def broken():
        raise RuntimeError("plateforme illisible")

    monkeypatch.setattr(accelerator, "platform_id", broken)
    assert accelerator.host_signals()["platform"] is None
    assert accelerator.host_signals()["memory_total_mib"] is None


@pytest.mark.parametrize(("content", "expected"), [
    (b"MemTotal:       64307708 kB\nMemFree:          748956 kB\n", TRIAL_HOST_MIB),
    (b"MemFree:          748956 kB\nMemTotal:       15974400 kB\n", JETSON_16_MIB),
    (b"MemTotal:       31334400 kB\n", JETSON_32_MIB),
    (b"MemTotal:       illisible kB\n", None),
    (b"MemTotal:       1024 MB\n", None),
    (b"MemFree:          748956 kB\n", None),
    (b"", None),
])
def test_the_total_memory_is_read_in_meminfo(tmp_path, content, expected):
    # Champ MemTotal de /proc/meminfo, en kB (Kio) ; toute autre forme laisse la mémoire inconnue.
    meminfo = tmp_path / "meminfo"
    meminfo.write_bytes(content)
    assert accelerator.read_memory_total_mib(meminfo) == expected


def test_a_missing_meminfo_leaves_the_memory_unknown(tmp_path, monkeypatch):
    assert accelerator.read_memory_total_mib(tmp_path / "absent") is None
    _linux_host(tmp_path, monkeypatch)
    monkeypatch.setattr(accelerator, "MEMINFO", tmp_path / "absent")
    assert accelerator.host_signals()["memory_total_mib"] is None


# --- Entrées du verrou par poste ---------------------------------------------------------------------------------------

def _gpu_group():
    return json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))["groups"]["ollama-gpu"]


@pytest.mark.parametrize(("signals", "expected"), [
    ({"platform": "linux-aarch64", "l4t_major": 35}, ["ollama-linux-arm64-jetpack5.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": 36}, ["ollama-linux-arm64-jetpack6.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": 38}, []),
    ({"platform": "linux-aarch64", "l4t_major": None}, []),
    ({"platform": "linux-aarch64"}, []),
    ({"platform": "linux-x86_64", "l4t_major": 35}, []),
    ({"platform": "windows-x86_64", "l4t_major": None}, []),
])
def test_the_jetpack_complement_is_chosen_from_the_host(signals, expected):
    assert [entry["url"].rsplit("/", 1)[-1] for entry in entries_for_host(_gpu_group(), signals)] == expected


def test_host_signals_are_not_read_when_no_entry_of_the_platform_needs_them(monkeypatch):
    # Poste Windows ou Linux x86-64 : aucune entrée `host` pour sa plateforme, aucun fichier lu de plus qu'avant.
    monkeypatch.setattr(accelerator, "host_signals", lambda: pytest.fail("indices du poste lus sans raison"))
    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    assert entries_for_host(lock["groups"]["ollama-gpu"], current="windows-x86_64") == []
    assert [entry["platform"] for entry in entries_for_host(lock["groups"]["ollama"], current="windows-x86_64")] == [
        "windows-x86_64"]


def test_an_unknown_host_criterion_never_matches():
    entries = [{"platform": "linux-aarch64", "host": {"l4t_major": 35, "inconnu": 1}, "url": "https://x/a"},
               {"platform": "linux-aarch64", "host": "R35", "url": "https://x/b"}]
    assert entries_for_host(entries, {"platform": "linux-aarch64", "l4t_major": 35}) == []


# --- Bibliothèques vérifiées et résolution du mode ---------------------------------------------------------------------

LOCK = {"groups": {
    "ollama": [{"platform": "linux-aarch64", "url": "https://ici/base.tar.zst", "extract_to": ".runtime/bin/ollama-0.35.0",
                "version": "0.35.0"},
               {"platform": "windows-x86_64", "url": "https://ici/base.zip", "extract_to": ".runtime/bin/ollama-0.35.0",
                "version": "0.35.0"}],
    "ollama-gpu": [{"platform": "linux-aarch64", "host": {"l4t_major": 35}, "variant": "cuda_jetpack5",
                    "url": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "extract_to": ".runtime/bin/ollama-0.35.0"},
                   {"platform": "linux-aarch64", "host": {"l4t_major": 36}, "variant": "cuda_jetpack6",
                    "url": "https://ici/ollama-linux-arm64-jetpack6.tar.zst", "extract_to": ".runtime/bin/ollama-0.35.0"}]}}
JETSON = {"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5"}


def _installed(root, files, links=()):
    """Fichiers et liens posés sous root, avec leurs enregistrements de manifeste."""
    recorded_files, recorded_links = [], []
    for relative, data in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        recorded_files.append({"path": relative, "sha256": "0" * 64, "size": len(data)})
    for relative, target in links:
        (root / relative).symlink_to(target)
        recorded_links.append({"path": relative, "target": target})
    return recorded_files, recorded_links


@pytest.fixture
def jetson_libraries(tmp_path):
    base_files, _ = _installed(tmp_path, [(".runtime/bin/ollama-0.35.0/bin/ollama", b"elf"),
                                          (".runtime/bin/ollama-0.35.0/lib/ollama/libggml-base.so", b"base"),
                                          (".runtime/bin/ollama-0.35.0/lib/ollama/cuda_v12/libggml-cuda.so", b"cuda12")])
    gpu_files, gpu_links = _installed(
        tmp_path, [(".runtime/bin/ollama-0.35.0/lib/ollama/cuda_jetpack5/libggml-cuda.so", b"jetpack5"),
                   (".runtime/bin/ollama-0.35.0/lib/ollama/cuda_jetpack5/libcudart.so.11.4.298", b"cudart")],
        [(".runtime/bin/ollama-0.35.0/lib/ollama/cuda_jetpack5/libcudart.so.11.0", "libcudart.so.11.4.298")])
    manifest = {"ollama": [{"url": "https://autre/base.zip", "extracted_files": [
                    {"path": ".runtime/bin/ollama-0.35.0/lib/ollama/cuda_v13/x.dll", "sha256": "0" * 64, "size": 1}]},
                           {"url": "https://ici/base.tar.zst", "extracted_files": base_files}],
                "ollama-gpu": [{"url": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "extracted_files": gpu_files,
                                "extracted_links": gpu_links}]}
    return tmp_path, manifest


def test_verified_libraries_follow_the_manifest_records_of_this_host(jetson_libraries):
    root, manifest = jetson_libraries
    libraries = verified_libraries(LOCK, manifest, JETSON, root=root)
    assert libraries == {"entry": "ollama-linux-arm64-jetpack5.tar.zst", "required": True, "provisioned": True,
                         "variants": {
                             "cuda_v12": {"group": "ollama", "files": 1, "links": 0, "sizes_ok": True, "links_ok": True},
                             "cuda_jetpack5": {"group": "ollama-gpu", "files": 2, "links": 1, "sizes_ok": True,
                                               "links_ok": True}}}


def test_altered_or_missing_libraries_are_not_verified(jetson_libraries):
    root, manifest = jetson_libraries
    folder = root / ".runtime/bin/ollama-0.35.0/lib/ollama/cuda_jetpack5"
    (folder / "libggml-cuda.so").write_bytes(b"jetpack5 tronque")
    assert verified_libraries(LOCK, manifest, JETSON, root=root)["variants"]["cuda_jetpack5"]["sizes_ok"] is False
    (folder / "libggml-cuda.so").write_bytes(b"jetpack5")
    (folder / "libcudart.so.11.0").unlink()
    assert verified_libraries(LOCK, manifest, JETSON, root=root)["variants"]["cuda_jetpack5"]["links_ok"] is False
    # Complément du poste non extrait : requis, non provisionné, variante absente.
    libraries = verified_libraries(LOCK, {"ollama": manifest["ollama"]}, JETSON, root=root)
    assert (libraries["required"], libraries["provisioned"], "cuda_jetpack5" in libraries["variants"]) == (True, False, False)
    # Poste sans complément publié : rien de requis.
    libraries = verified_libraries(LOCK, manifest, {"platform": "linux-aarch64", "l4t_major": 38}, root=root)
    assert (libraries["entry"], libraries["required"], libraries["provisioned"]) == (None, False, False)


def test_variant_of_reads_windows_and_posix_manifest_paths():
    assert accelerator._variant_of(r".runtime\bin\ollama-0.35.0\lib\ollama\cuda_v13\ggml-cuda.dll") == "cuda_v13"
    assert accelerator._variant_of(".runtime/bin/ollama-0.35.0/lib/ollama/vulkan/ggml-vulkan.so") == "vulkan"
    assert accelerator._variant_of(".runtime/bin/ollama-0.35.0/lib/ollama/libggml-base.so") is None
    assert accelerator._variant_of(".runtime/bin/ollama-0.35.0/bin/ollama") is None


def _verified(*variants):
    return {"variants": {name: {"files": 1, "links": 0, "sizes_ok": True, "links_ok": True} for name in variants}}


AUTO = {"requested": "auto", "requested_source": "profile"}
GPU = {"requested": "gpu", "requested_source": "profile"}
JETPACK5 = parse_discovery(JETSON_JETPACK5)


@pytest.mark.parametrize(("requested", "discovery", "libraries", "platform", "mode", "reason"), [
    ({"requested": "cpu", "requested_source": "profile"}, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64",
     "cpu", "imposed_by_profile"),
    ({"requested": "cpu", "requested_source": "legacy_num_gpu"}, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64",
     "cpu", "legacy_profile_cpu"),
    (AUTO, {"status": "unreadable", "devices": [], "dropped": []}, _verified(), "linux-aarch64",
     "cpu", "discovery_unreadable"),
    (AUTO, parse_discovery(JETSON_BASE_ONLY), _verified("cuda_v12"), "linux-aarch64", "cpu", "no_gpu_discovered"),
    (GPU, parse_discovery(JETSON_BASE_ONLY), _verified("cuda_v12"), "linux-aarch64", "cpu", "no_gpu_discovered"),
    (AUTO, parse_discovery(DISCOVERING + VULKAN_DISCRETE), _verified("vulkan"), "windows-x86_64",
     "cpu", "gpu_library_not_retained"),
    (GPU, parse_discovery(DISCOVERING + CUDA_DISCRETE + VULKAN_DISCRETE), _verified("cuda_v13", "vulkan"),
     "windows-x86_64", "cpu", "gpu_mixed_libraries"),
    (AUTO, JETPACK5, _verified("cuda_v12"), "linux-aarch64", "cpu", "gpu_libraries_unverified"),
    (AUTO, JETPACK5, {"variants": {"cuda_jetpack5": {"files": 2, "links": 1, "sizes_ok": False, "links_ok": True}}},
     "linux-aarch64", "cpu", "gpu_libraries_unverified"),
    (AUTO, parse_discovery(DISCOVERING + CUDA_DISCRETE), _verified("cuda_v13"), "windows-x86_64",
     "cpu", "gpu_path_not_qualified"),
    (AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-x86_64", "cpu", "gpu_path_not_qualified"),
    (GPU, parse_discovery(DISCOVERING + CUDA_DISCRETE), _verified("cuda_v13"), "windows-x86_64", "gpu", "gpu_trial"),
    (AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64", "gpu", "gpu_discovered"),
    (GPU, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64", "gpu", "gpu_discovered"),
    ({"requested": "auto", "requested_source": "default"}, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64",
     "gpu", "gpu_discovered"),
])
def test_each_rule_of_the_resolution_table(requested, discovery, libraries, platform, mode, reason):
    # Mémoire du poste de l'essai réel : la règle du GPU intégré est couverte à part.
    decision = resolve_mode(requested, discovery, libraries, platform, memory_total_mib=TRIAL_HOST_MIB)
    assert (decision["mode"], decision["reason"]) == (mode, reason)
    assert reason in REASON_TEXTS


def test_the_decision_names_the_cuda_device_its_variant_and_its_qualification():
    decision = resolve_mode(AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64", memory_total_mib=TRIAL_HOST_MIB)
    assert decision == {"mode": "gpu", "reason": "gpu_discovered", "device": ORIN, "variant": "cuda_jetpack5",
                        "qualified": True}
    mixed = resolve_mode(AUTO, parse_discovery(DISCOVERING + VULKAN_DISCRETE + CUDA_DISCRETE),
                         _verified("cuda_v13", "vulkan"), "windows-x86_64")
    assert (mixed["device"]["library"], mixed["variant"], mixed["qualified"]) == ("CUDA", "cuda_v13", False)
    assert resolve_mode(AUTO, parse_discovery(WINDOWS_IRIS_XE), _verified(), "windows-x86_64")["device"] is None
    assert QUALIFIED_GPU_PATHS == frozenset({("linux-aarch64", "cuda_jetpack5")})


def test_the_windows_reference_host_resolves_to_cpu_whatever_the_request():
    # Invariant Windows (W025) : poste de référence sans GPU utilisable, en auto comme en gpu.
    for requested in (AUTO, GPU, {"requested": "auto", "requested_source": "default"}):
        decision = resolve_mode(requested, parse_discovery(WINDOWS_IRIS_XE), _verified("cuda_v12", "cuda_v13", "vulkan"),
                                "windows-x86_64")
        assert (decision["mode"], decision["reason"]) == ("cpu", "no_gpu_discovered")


# --- GPU intégré à mémoire unifiée (Jetson) : qualifié au-delà de 16 Gio de mémoire totale -------------------------------
# Essai réel du 02/10 : MemAvailable n'a baissé que de 1,0 à 1,6 Gio pour un modèle de 3,1 Go chargé sur le GPU ; la
# mémoire prise par le GPU n'y est pas mesurable de façon fiable. Qualifié au-delà de 16 Gio ; seul le poste de l'essai (62 800 Mio) a été essayé.

@pytest.mark.parametrize(("requested", "memory", "mode", "reason"), [
    (AUTO, JETSON_16_MIB, "cpu", "gpu_unified_memory_not_qualified"),
    (AUTO, 16384, "cpu", "gpu_unified_memory_not_qualified"),
    (AUTO, None, "cpu", "gpu_unified_memory_not_qualified"),
    ({"requested": "auto", "requested_source": "default"}, JETSON_16_MIB, "cpu", "gpu_unified_memory_not_qualified"),
    (AUTO, 16385, "gpu", "gpu_discovered"),
    (AUTO, JETSON_32_MIB, "gpu", "gpu_discovered"),
    (AUTO, TRIAL_HOST_MIB, "gpu", "gpu_discovered"),
    (GPU, JETSON_16_MIB, "gpu", "gpu_trial"),
    (GPU, None, "gpu", "gpu_trial"),
    (GPU, JETSON_32_MIB, "gpu", "gpu_discovered"),
    ({"requested": "cpu", "requested_source": "profile"}, JETSON_16_MIB, "cpu", "imposed_by_profile"),
], ids=["auto-16go", "auto-16gio-pile", "auto-inconnue", "defaut-16go", "auto-16gio-plus-1", "auto-32go",
        "auto-poste-essai", "gpu-16go", "gpu-inconnue", "gpu-32go", "cpu-16go"])
def test_an_integrated_gpu_is_qualified_only_above_16_gib_of_total_memory(requested, memory, mode, reason):
    decision = resolve_mode(requested, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64", memory_total_mib=memory)
    assert (decision["mode"], decision["reason"]) == (mode, reason)
    # La voie reste qualifiée et le GPU nommé : seule la mémoire du poste écarte le GPU en auto.
    assert (decision["device"], decision["variant"], decision["qualified"]) == (ORIN, "cuda_jetpack5", True)


def test_without_a_given_memory_the_decision_reads_the_host(tmp_path, monkeypatch):
    # Superviseur et calibration ne transmettent pas la mémoire : elle est lue sur le poste, pour un GPU intégré.
    meminfo = tmp_path / "meminfo"
    monkeypatch.setattr(accelerator, "MEMINFO", meminfo)
    meminfo.write_bytes(b"MemTotal:       15974400 kB\n")
    assert resolve_mode(AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64")["reason"] == (
        "gpu_unified_memory_not_qualified")
    meminfo.write_bytes(b"MemTotal:       31334400 kB\n")
    assert resolve_mode(AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64")["reason"] == "gpu_discovered"
    meminfo.unlink()
    assert resolve_mode(AUTO, JETPACK5, _verified("cuda_jetpack5"), "linux-aarch64")["reason"] == (
        "gpu_unified_memory_not_qualified")


def test_a_dedicated_gpu_has_no_memory_condition(monkeypatch):
    # GPU NVIDIA dédié sur un poste de 8 Gio : règle inchangée, la mémoire du poste n'est même pas lue.
    monkeypatch.setattr(accelerator, "read_memory_total_mib", lambda path=None: pytest.fail("mémoire lue, GPU dédié"))
    rtx = parse_discovery(DISCOVERING + CUDA_DISCRETE)
    assert rtx["devices"][0]["type"] == "discrete"
    for memory in ({}, {"memory_total_mib": 8192}, {"memory_total_mib": None}):
        assert resolve_mode(AUTO, rtx, _verified("cuda_v13"), "windows-x86_64", **memory)["reason"] == (
            "gpu_path_not_qualified")
        assert resolve_mode(GPU, rtx, _verified("cuda_v13"), "windows-x86_64", **memory)["reason"] == "gpu_trial"
    # Voie supposée qualifiée : un GPU dédié passe sur GPU en auto, quelle que soit la mémoire du poste.
    monkeypatch.setattr(accelerator, "QUALIFIED_GPU_PATHS", frozenset({("windows-x86_64", "cuda_v13")}))
    for memory in ({}, {"memory_total_mib": 8192}, {"memory_total_mib": None}):
        decision = resolve_mode(AUTO, rtx, _verified("cuda_v13"), "windows-x86_64", **memory)
        assert (decision["mode"], decision["reason"]) == ("gpu", "gpu_discovered")


def test_the_unified_memory_threshold():
    assert accelerator.UNIFIED_MEMORY_MIN_MIB == 16384
    assert [accelerator.unified_memory_qualified(value) for value in (None, 15600, 16384, 16385, 62800)] == [
        False, False, False, True, True]
    # Valeur d'un runtime.json altéré : jamais qualifiée.
    assert [accelerator.unified_memory_qualified(value) for value in ("62800", True, 62800.0)] == [False, False, False]


def test_every_reason_has_a_short_text():
    assert set(REASON_TEXTS) == set(REASONS)
    assert all(text and not text.endswith(".") for text in REASON_TEXTS.values())
    # Placés après « génération sur CPU, » ou « sur GPU, … ; » : une seule paire de parenthèses au plus.
    assert all(text.count("(") <= 1 and "W0" not in text for text in REASON_TEXTS.values())
    assert REASON_TEXTS["imposed_by_profile"] == "imposée par le profil (llm.accelerator: cpu)"


def test_a_nvidia_gpu_seen_only_through_vulkan_keeps_its_vendor_in_the_reason():
    # Revue J11 runtime-7 : CUDA écarté (pilote, capacité), Vulkan actif par défaut ; le GPU reste NVIDIA.
    vulkan = ('time=x level=INFO source=types.go:32 msg="inference compute" id=0 filter_id="" library=Vulkan compute=0.0 '
              'name=Vulkan0 description="NVIDIA GeForce GTX 1060 6GB" libdirs=ollama,vulkan driver=0.0 '
              'pci_id=0000:01:00.0 type=discrete total="6.0 GiB" available="5.2 GiB"\n')
    nvidia = resolve_mode(AUTO, parse_discovery(DISCOVERING + vulkan), _verified("vulkan"), "windows-x86_64")
    amd = resolve_mode(AUTO, parse_discovery(DISCOVERING + VULKAN_DISCRETE), _verified("vulkan"), "windows-x86_64")
    assert nvidia["reason"] == amd["reason"] == "gpu_library_not_retained"
    assert (is_nvidia(nvidia["device"]), is_nvidia(amd["device"]), is_nvidia(None)) == (True, False, False)
    assert reason_text(nvidia) == ("GPU NVIDIA vu seulement par Vulkan, CUDA ne l'a pas retenu : pilote ou capacité de "
                                   "calcul")
    assert reason_text(amd) == REASON_TEXTS["gpu_library_not_retained"]
    assert reason_text({"reason": None}) == "raison non consignée"


def test_libraries_signature_compares_what_ollama_can_load():
    # Revue J11 runtime-3 : une découverte faite avec d'autres bibliothèques GPU que celles d'aujourd'hui est périmée.
    without = {"entry": "jp5", "required": True, "provisioned": False, "variants": {}}
    extracted = {"entry": "jp5", "required": True, "provisioned": True, "variants": {
        "cuda_jetpack5": {"group": "ollama-gpu", "files": 2, "links": 1, "sizes_ok": True, "links_ok": True},
        "cuda_v12": {"group": "ollama", "files": 1, "links": 0, "sizes_ok": False, "links_ok": True}}}
    assert libraries_signature(without) != libraries_signature(extracted)
    assert libraries_signature(extracted) == (True, ("cuda_jetpack5",))
    assert libraries_signature({**extracted, "error": "x", "entry": None}) == libraries_signature(extracted)


# --- Libellés ----------------------------------------------------------------------------------------------------------

def test_device_descriptions():
    assert describe_device(ORIN, "cuda_jetpack5") == "Orin (CUDA, GPU intégré, bibliothèques cuda_jetpack5)"
    discrete = parse_discovery(DISCOVERING + CUDA_DISCRETE)["devices"][0]
    assert describe_device(discrete, None) == "NVIDIA GeForce RTX 4060 (CUDA, GPU dédié)"
    assert describe_device({"name": "Vulkan0", "library": "Vulkan"}) == "Vulkan0 (Vulkan)"


@pytest.mark.parametrize(("size", "size_vram", "label"), [
    (3107811491, 0, "100% CPU"),
    (0, 0, "100% CPU"),
    (3107811491, 3107811491, "100% GPU"),
    (100, 101, "Unknown"),
    (0, 5, "Unknown"),
    (100, 52, "48%/52% CPU/GPU"),
    # math.Round de Go : 0,5 et 2,5 arrondis en s'éloignant de zéro (Python arrondirait au pair).
    (200, 199, "1%/99% CPU/GPU"),
    (200, 195, "3%/97% CPU/GPU"),
])
def test_processor_label_reproduces_ollama_ps(size, size_vram, label):
    assert processor_label(size, size_vram) == label


def test_discovery_record_format():
    record = discovery_record(JETPACK5, source="provision", method="probe", log=".runtime/provision-service/ollama-probe.log",
                              version="0.35.0", signals=JETSON, utc="2026-10-01T22:00:00+00:00")
    assert record == {"schema_version": 1, "source": "provision", "method": "probe", "utc": "2026-10-01T22:00:00+00:00",
                      "version": "0.35.0", "platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5",
                      "log": ".runtime/provision-service/ollama-probe.log", "status": "gpu", "devices": [ORIN],
                      "dropped": []}
    libraries = {"entry": "jp5", "required": True, "provisioned": True, "variants": {}}
    assert discovery_record(JETPACK5, source="provision", method="probe", log="l", version="0.35.0", signals=JETSON,
                            utc="u", libraries=libraries)["libraries"] == libraries


# --- Sonde de provisionnement ------------------------------------------------------------------------------------------

# Arrêt réel du superviseur, avant que la fixture probe_service ne le remplace par un double.
INTERRUPT = supervisor.send_owned_console_interrupt


@pytest.fixture
def probe_service(tmp_path, monkeypatch):
    """Sonde sans Ollama réel : Job, exécutable et disponibilité sont des doubles ; environnement réel du superviseur."""
    from services.runtime import supervisor

    launched, stopped = [], []

    class Child:
        log_path = None
        pid = 4242

        def wait(self, timeout):
            stopped.append("wait")
            return 0

        def still_owned(self):
            return True

    class Job:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def launch(self, argv, *, cwd, env, log_path):
            launched.append({"argv": argv, "cwd": cwd, "env": env, "log_path": log_path})
            return Child()

    def ready(url, child, expected_version=None, timeout=90, verify=True):
        launched[-1]["url"], launched[-1]["version"] = url, expected_version
        launched[-1]["log_path"].parent.mkdir(parents=True, exist_ok=True)
        with launched[-1]["log_path"].open("a", encoding="utf-8") as log:
            log.write(JETSON_JETPACK5)
        return {"version": expected_version}

    binary = tmp_path / "programme/.runtime/bin/ollama-0.35.0/bin/ollama"
    monkeypatch.setattr(supervisor, "ProcessJob", Job)
    monkeypatch.setattr(supervisor, "native_paths", lambda names=("qdrant", "ollama"): {"ollama": binary})
    monkeypatch.setattr(supervisor, "wait_http", ready)
    monkeypatch.setattr(supervisor, "send_owned_console_interrupt", lambda child, service=None: stopped.append(service))
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    return profile, launched, stopped, binary


def test_probe_reads_the_discovery_with_the_unchanged_environment(tmp_path, probe_service):
    from services.runtime import supervisor

    profile, launched, stopped, binary = probe_service
    directory, log, profile_path = tmp_path / "service", tmp_path / "service/ollama-probe.log", ROOT / "config/local16.yaml"
    discovery = accelerator.probe_discovery(profile, profile_path, directory, log, version="0.35.0", port=0)
    assert discovery == JETPACK5 and stopped == ["ollama", "wait"]
    call = launched[0]
    assert call["argv"] == [str(binary), "serve"] and call["log_path"] == log and call["version"] == "0.35.0"
    # Environnement d'Ollama strictement celui du superviseur, au port de la sonde près (W025, règle 2).
    expected = supervisor.environment({**profile, "llm": {**profile["llm"], "base_url": "http://127.0.0.1:0"}},
                                      directory, profile_path)
    assert call["env"] == expected
    assert not any(key.startswith(("CUDA_", "LD_LIBRARY_PATH")) or key in ("OLLAMA_VULKAN", "OLLAMA_LLM_LIBRARY")
                   for key in call["env"])
    if sys.platform != "win32":
        assert Path(call["env"]["HOME"]).is_absolute() and call["env"]["HOME"] == str(directory / "home")


@pytest.mark.parametrize("relative", ["profile_path", "directory", "log_path"])
def test_probe_refuses_relative_paths_before_launching(tmp_path, probe_service, relative):
    # B5 : un dossier relatif serait résolu depuis bin/ d'Ollama et y laisserait HOME/.ollama (clés comprises).
    profile, launched, _, _ = probe_service
    paths = {"profile_path": ROOT / "config/local16.yaml", "directory": tmp_path / "service",
             "log_path": tmp_path / "service/ollama-probe.log"}
    paths[relative] = Path(os.path.relpath(paths[relative]))
    with pytest.raises(ValueError, match="chemin absolu"):
        accelerator.probe_discovery(profile, paths["profile_path"], paths["directory"], paths["log_path"], version="0.35.0")
    assert launched == []


def test_probe_refuses_a_busy_port(tmp_path, probe_service):
    import socket

    profile, launched, _, _ = probe_service
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        with pytest.raises(OSError):
            accelerator.probe_discovery(profile, ROOT / "config/local16.yaml", tmp_path, tmp_path / "probe.log",
                                        version="0.35.0", port=taken.getsockname()[1])
    assert launched == []



def test_a_probe_whose_console_stop_times_out_under_windows_still_reads_its_discovery(tmp_path, probe_service,
                                                                                      monkeypatch, capsys):
    # Revue J11 invariants-04 : sous Windows, l'arrêt passe par l'assistant console_signal (délai de 10 s) ; son
    # dépassement (subprocess.TimeoutExpired) n'interrompt pas la sonde, la fermeture du Job arrête Ollama.
    profile, launched, stopped, _ = probe_service
    monkeypatch.setattr(supervisor, "send_owned_console_interrupt", INTERRUPT)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def helper(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    monkeypatch.setattr(supervisor.subprocess, "run", helper)
    discovery = accelerator.probe_discovery(profile, ROOT / "config/local16.yaml", tmp_path / "service",
                                            tmp_path / "service/ollama-probe.log", version="0.35.0", port=0)
    assert discovery == JETPACK5 and len(launched) == 1 and stopped == []
    assert capsys.readouterr().out == ("Sonde de découverte : arrêt coopératif d'Ollama impossible, TimeoutExpired ; "
                                       "arrêt forcé ciblé du Job, aucune inférence active.\n")
