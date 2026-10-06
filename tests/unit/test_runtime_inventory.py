"""Inventaire des licences : artefacts du verrou retenus pour ce poste, avec la règle de provision (revue J11 runtime-8).

Racine de programme temporaire ; ni distribution Python ni paquet npm n'est parcouru (doubles), seul le verrou compte.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.runtime import inventory
from tests.unit.test_runtime_accelerator import JETSON, LOCK


@pytest.fixture
def program(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps({"schema_version": 1, "groups": {
        group: [{**entry, "target": f".runtime/cache/downloads/{entry['url'].rsplit('/', 1)[-1]}"} for entry in entries]
        for group, entries in LOCK["groups"].items()}}), encoding="utf-8")
    monkeypatch.setattr(inventory, "ROOT", tmp_path)
    monkeypatch.setattr(inventory.importlib.metadata, "distributions", lambda: [])
    # Node.js du poste exclu : chaque test qui en a besoin pose le sien.
    monkeypatch.setattr(inventory.shutil, "which", lambda name: None)
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


@pytest.mark.parametrize(("present", "license_text"), [(False, None), (True, "Licence 2B de la fixture"), (True, None)])
def test_ollama_2b_manifest_is_inventoried_without_changing_4b_records(program, monkeypatch, present, license_text):
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(JETSON))
    manifests = program / ".runtime/manifests"
    manifests.mkdir(parents=True)
    expected = {}
    for key, filename, model in (
        ("ollama_model", "ollama-model.json", "qwen3.5:4b"),
        ("ollama_text_model", "ollama-model-text.json", "qwen3.5:4b-text"),
        ("ollama_2b_model", "ollama-model-2b.json", "qwen3.5:2b"),
    ):
        if key == "ollama_2b_model" and not present:
            continue
        source_model = "qwen3.5:4b" if key == "ollama_text_model" else None
        data = {"model": {"name": model, "digest": f"sha256:fixture-{key}"},
                "source_model": source_model,
                "license": license_text if key == "ollama_2b_model" else "Licence 4B de la fixture"}
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        (manifests / filename).write_bytes(payload)
        expected[key] = {"model": data["model"], "license_notice": data["license"],
                         "derived_from": source_model, "manifest_sha256": hashlib.sha256(payload).hexdigest()}
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    assert {key: report[key] for key in expected} == expected
    if not present:
        assert "ollama_2b_model" not in report
    for key, filename in (("ollama_model", "ollama-model.json"), ("ollama_text_model", "ollama-model-text.json"),
                          ("ollama_2b_model", "ollama-model-2b.json")):
        if key in expected:
            assert hashlib.sha256((manifests / filename).read_bytes()).hexdigest() == expected[key]["manifest_sha256"]


class Distribution:
    """Distribution Python installée (double d'importlib.metadata) : fichiers relatifs à `base`."""

    def __init__(self, base, files, name="paquet"):
        self.base, self.files, self.version = base, files, "1.0"
        self.metadata = {"Name": name}

    def locate_file(self, file):
        return self.base / file


class Metadata(dict):
    def get_all(self, name, default=None):
        return default


def _program_with_links(tmp_path, linked):
    """Racine de programme dont `.venv` et `.runtime` sont des liens vers un autre volume (W018) ou des dossiers."""
    program, volume = tmp_path / "programme", tmp_path / "volume"
    program.mkdir()
    for name, folder in ((".venv", volume / "venv"), (".runtime", volume / "runtime")):
        folder.mkdir(parents=True)
        if linked:
            (program / name).symlink_to(folder, target_is_directory=True)
        else:
            folder.rename(program / name)
    return program, (volume if linked else program)


@pytest.mark.parametrize("linked", [
    pytest.param(True, marks=pytest.mark.skipif(sys.platform == "win32", reason="liens W018 posés sous Linux")),
    False,
])
def test_files_behind_the_venv_and_runtime_links_belong_to_the_project(program, monkeypatch, linked):
    """J8 (L0) : derrière les liens `.venv` et `.runtime`, 0 avis Python sur 124 et CPython hors projet. Sans lien
    (disposition Windows), les chemins sont ceux d'avant la correction."""
    root, storage = _program_with_links(program, linked)
    real = {".venv": storage / ("venv" if linked else ".venv"), ".runtime": storage / ("runtime" if linked else ".runtime")}
    site = root / ".venv/lib/python3.12/site-packages"
    licence = real[".venv"] / "lib/python3.12/site-packages/paquet-1.0.dist-info/licenses/LICENSE"
    licence.parent.mkdir(parents=True)
    licence.write_text("MIT", encoding="utf-8")
    outside = program / "ailleurs/LICENSE"
    outside.parent.mkdir()
    outside.write_text("hors projet", encoding="utf-8")
    distribution = Distribution(site, ["paquet-1.0.dist-info/licenses/LICENSE", "../../../../../ailleurs/LICENSE"])
    distribution.metadata = Metadata(Name="paquet")
    # Interpréteur géré : sys.base_prefix est déjà résolu par Python (cible du lien `.runtime`).
    python_root = real[".runtime"] / "python/cpython-3.12.14-linux-aarch64-gnu"
    python_licence = python_root / "lib/python3.12/LICENSE.txt"
    python_licence.parent.mkdir(parents=True)
    python_licence.write_text("PSF", encoding="utf-8")
    monkeypatch.setattr(inventory, "ROOT", root)
    (root / "config").mkdir()
    (root / "config/artifacts.lock.json").write_bytes((program / "config/artifacts.lock.json").read_bytes())
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    monkeypatch.setattr(inventory.importlib.metadata, "distributions", lambda: [distribution])
    monkeypatch.setattr(inventory, "sys", SimpleNamespace(base_prefix=str(python_root), version_info=sys.version_info,
                                                          version="3.12.14 (simulé)"))
    output = program / "licences.json"
    inventory.license_inventory(output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert [item["path"] for item in report["python"][0]["notices"]] == [
        str(Path(".venv/lib/python3.12/site-packages/paquet-1.0.dist-info/licenses/LICENSE"))]
    cpython = report["runtime_prerequisites"][0]
    assert cpython["name"] == "CPython" and cpython["redistributed_in_project"] is True
    assert [item["path"] for item in cpython["notices"]] == [
        str(Path(".runtime/python/cpython-3.12.14-linux-aarch64-gnu/lib/python3.12/LICENSE.txt"))]


def test_uv_without_license_text_is_declared_missing(program, monkeypatch):
    """Linux : bootstrap.sh n'installe que bin/uv et bin/uvx, seuls fichiers de l'archive officielle."""
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    (program / ".runtime/bootstrap/bin").mkdir(parents=True)
    (program / ".runtime/bootstrap/bin/uv").write_bytes(b"elf")
    inventory.license_inventory(program / "licences.json")
    uv = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][1]
    assert uv["name"] == "uv" and uv["notices"] == []
    assert "MIT OR Apache-2.0" in uv["missing_notice"] and "https://github.com/astral-sh/uv/tree/0.12.21" in uv["missing_notice"]


def test_uv_license_texts_present_under_bootstrap_are_listed_as_before(program, monkeypatch):
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None})
    licenses = program / ".runtime/bootstrap/uv-0.12.21.dist-info/licenses"
    licenses.mkdir(parents=True)
    for name in ("LICENSE-APACHE", "LICENSE-MIT"):
        (licenses / name).write_text(name, encoding="utf-8")
    inventory.license_inventory(program / "licences.json")
    uv = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][1]
    assert set(uv) == {"name", "version", "redistributed_in_project", "notices"}
    assert [item["path"] for item in uv["notices"]] == [str(Path(".runtime/bootstrap/uv-0.12.21.dist-info/licenses") / name)
                                                        for name in ("LICENSE-APACHE", "LICENSE-MIT")]


def _node_archive(root, *, windows):
    """Archive officielle de Node.js extraite : node.exe et LICENSE côte à côte (Windows) ou bin/node et LICENSE au-dessus."""
    executable = root / ("node.exe" if windows else "bin/node")
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\necho v24.16.0\n", encoding="utf-8")
    executable.chmod(0o755)
    (root / "LICENSE").write_text("Node.js", encoding="utf-8")
    corepack = root / ("node_modules" if windows else "lib/node_modules") / "corepack/LICENSE.md"
    corepack.parent.mkdir(parents=True)
    corepack.write_text("corepack", encoding="utf-8")
    return executable


@pytest.mark.skipif(sys.platform == "win32", reason="disposition Linux de l'archive Node.js, exécutable shell")
@pytest.mark.parametrize("through_link", [False, True])
def test_node_notices_are_read_in_the_parent_of_bin_under_linux(program, monkeypatch, tmp_path_factory, through_link):
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    home = tmp_path_factory.mktemp("utilisateur")
    node_root = home / ".nvm/versions/node/v24.16.0"
    executable = _node_archive(node_root, windows=False)
    if through_link:
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/node").symlink_to(executable)
        executable = home / ".local/bin/node"
    monkeypatch.setattr(inventory.shutil, "which", lambda name: str(executable) if name == "node" else None)
    inventory.license_inventory(program / "licences.json")
    node = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][2]
    assert [item["path"] for item in node["notices"]] == [str(node_root / "LICENSE"),
                                                          str(node_root / "lib/node_modules/corepack/LICENSE.md")]
    assert node["name"] == "Node.js" and node["version"] == "24.16.0" and node["path"] == str(executable)


def test_node_notices_stay_beside_node_exe_under_simulated_windows(program, monkeypatch, tmp_path_factory):
    monkeypatch.setattr(inventory, "WINDOWS", True)
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None})
    disk = tmp_path_factory.mktemp("disque")
    node_root = disk / "node/node-v22.17.0-win-x64"
    executable = _node_archive(node_root, windows=True)
    (disk / "node/LICENSE").write_text("dossier parent, hors archive", encoding="utf-8")
    monkeypatch.setattr(inventory.shutil, "which", lambda name: str(executable) if name == "node.exe" else None)
    monkeypatch.setattr(inventory, "executable_name", lambda name: f"{name}.exe")
    inventory.license_inventory(program / "licences.json")
    node = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][2]
    assert [item["path"] for item in node["notices"]] == [str(node_root / "LICENSE"),
                                                          str(node_root / "node_modules/corepack/LICENSE.md")]


@pytest.mark.parametrize(("signals", "files", "links", "expected"), [
    (JETSON, [("cuda_jetpack5/libcublas.so.11.6.6.84", b"cublas"), ("cuda_jetpack5/libcublasLt.so.11.6.6.84", b"lt"),
              ("cuda_jetpack5/libcudart.so.11.4.298", b"cudart"), ("cuda_jetpack5/libggml-cuda.so", b"ggml"),
              ("cuda_v12/libcudart.so.12.8.90", b"cudart12"), ("libggml-base.so", b"base")],
     [("cuda_jetpack5/libcudart.so.11.0", "libcudart.so.11.4.298")],
     [("CUDA BLAS Library (cuBLAS)", "cuda_jetpack5", "11.6.6.84", "https://ici/ollama-linux-arm64-jetpack5.tar.zst"),
      ("CUDA BLAS Library (cuBLASLt)", "cuda_jetpack5", "11.6.6.84", "https://ici/ollama-linux-arm64-jetpack5.tar.zst"),
      ("CUDA Runtime", "cuda_jetpack5", "11.4.298", "https://ici/ollama-linux-arm64-jetpack5.tar.zst"),
      ("CUDA Runtime", "cuda_v12", "12.8.90", "https://ici/base.tar.zst")]),
    ({"platform": "windows-x86_64", "l4t_major": None, "jetpack": None},
     [("cuda_v12/cublas64_12.dll", b"cublas"), ("cuda_v12/cublasLt64_12.dll", b"lt"), ("cuda_v12/cudart64_12.dll", b"rt"),
      ("cuda_v12/ggml-cuda.dll", b"ggml")], [],
     [("CUDA BLAS Library (cuBLAS)", "cuda_v12", None, "https://ici/base.zip"),
      ("CUDA BLAS Library (cuBLASLt)", "cuda_v12", None, "https://ici/base.zip"),
      ("CUDA Runtime", "cuda_v12", None, "https://ici/base.zip")]),
])
def test_nvidia_cuda_libraries_from_the_ollama_archives_are_listed_with_their_eula(program, monkeypatch, signals, files,
                                                                                  links, expected):
    """J8 (L0) : libcublas, libcublasLt et libcudart des archives d'Ollama, sans fichier d'avis, absents du registre D09.5."""
    if links and sys.platform == "win32":
        pytest.skip("liens internes de l'archive Linux")
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(signals))
    library_root = program / ".runtime/bin/ollama-0.35.0/lib/ollama"
    for relative, data in files:
        (library_root / relative).parent.mkdir(parents=True, exist_ok=True)
        (library_root / relative).write_bytes(data)
    for relative, target in links:
        (library_root / relative).symlink_to(target)
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    listed = report["nvidia_cuda_libraries"]
    assert [(item["component"], item["variant"], item["version"], item["source"]) for item in listed] == expected
    assert all(item["license"] == report["nvidia_cuda_license"]["name"] and item["notices"] == [] for item in listed)
    assert all(item["publisher"] == "NVIDIA Corporation" and not Path(item["path"]).is_absolute() for item in listed)
    assert report["nvidia_cuda_license"]["url"] == "https://docs.nvidia.com/cuda/eula/"
    assert "Attachment A" in report["nvidia_cuda_license"]["redistribution_terms"]
    assert any("NVIDIA CUDA libraries" in limit for limit in report["limits"])


def test_no_cuda_folder_means_no_nvidia_entry_nor_limit(program, monkeypatch):
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None})
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    assert report["nvidia_cuda_libraries"] == [] and "nvidia_cuda_license" not in report
    assert not any("NVIDIA" in limit for limit in report["limits"])


# --- Seconde passe J8 (revue runtime, constats 1 à 4) et runtimes OpenMP de l'archive d'Ollama ---

UV_ARCHIVES = ("uv-aarch64-unknown-linux-gnu.tar.gz", "uv-x86_64-unknown-linux-gnu.tar.gz", "uv-x86_64-pc-windows-msvc.zip")


@pytest.mark.parametrize(("platform", "windows", "executables"), [
    ("linux-aarch64", False, ("uv", "uvx")),
    ("linux-x86_64", False, ("uv", "uvx")),
    ("windows-x86_64", True, ("uv.exe", "uvw.exe", "uvx.exe")),
])
def test_uv_missing_notice_holds_for_every_bootstrap_archive(program, monkeypatch, platform, windows, executables):
    """Constat 1 : bootstrap.sh et bootstrap.ps1 n'extraient que les exécutables, et aucune des trois archives officielles
    0.12.21 qu'ils vérifient ne contient de texte de licence ; une installation Windows neuve n'a donc pas de dist-info."""
    monkeypatch.setattr(inventory, "WINDOWS", windows)
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": platform, "l4t_major": None, "jetpack": None})
    (program / ".runtime/bootstrap/bin").mkdir(parents=True)
    for name in executables:
        (program / ".runtime/bootstrap/bin" / name).write_bytes(b"exe")
    inventory.license_inventory(program / "licences.json")
    uv = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][1]
    assert uv["name"] == "uv" and uv["notices"] == []
    assert all(archive in uv["missing_notice"] for archive in UV_ARCHIVES)
    assert "MIT OR Apache-2.0" in uv["missing_notice"] and "https://github.com/astral-sh/uv/tree/0.12.21" in uv["missing_notice"]


def _cuda_folders(program, folders):
    library_root = program / ".runtime/bin/ollama-0.35.0/lib/ollama"
    for folder in folders:
        (library_root / folder).mkdir(parents=True)
        (library_root / folder / "libcudart.so.11.4.298").write_bytes(folder.encode())


@pytest.mark.parametrize(("signals", "base", "expected"), [
    # Jetson dont la version de Jetson Linux n'est pas lue : le complément jetpack5 déjà extrait reste le sien.
    ({"platform": "linux-aarch64", "l4t_major": None, "jetpack": None}, True,
     {"cuda_jetpack5": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "cuda_v12": "https://ici/base.tar.zst"}),
    # `.runtime` déplacé vers un Jetson JetPack 6 : cuda_jetpack5 vient toujours du complément jetpack5.
    ({"platform": "linux-aarch64", "l4t_major": 36, "jetpack": "jetpack6"}, True,
     {"cuda_jetpack5": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "cuda_v12": "https://ici/base.tar.zst"}),
    # Verrou sans archive de base pour la plateforme : un dossier qu'aucun complément ne déclare n'a pas d'origine connue.
    ({"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5"}, False,
     {"cuda_jetpack5": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "cuda_v12": None}),
])
def test_cuda_folder_source_comes_from_every_lock_entry_of_the_platform(program, monkeypatch, signals, base, expected):
    """Constat 2 : l'archive d'origine d'un dossier cuda_* ne dépend pas des complements retenus pour ce poste ; le repli
    sur l'archive de base ne vaut que pour un dossier qu'aucun complément de la plateforme ne déclare."""
    if not base:
        lock = json.loads((program / "config/artifacts.lock.json").read_text(encoding="utf-8"))
        lock["groups"]["ollama"] = [entry for entry in lock["groups"]["ollama"] if entry["platform"] != "linux-aarch64"]
        (program / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(signals))
    _cuda_folders(program, expected)
    inventory.license_inventory(program / "licences.json")
    listed = json.loads((program / "licences.json").read_text(encoding="utf-8"))["nvidia_cuda_libraries"]
    assert {item["variant"]: item["source"] for item in listed} == expected


def test_cuda_limit_states_an_attribution_by_file_name(program, monkeypatch):
    """Constat 3 : la licence des bibliothèques CUDA est attribuée d'après leur nom, sans vérifier la version du contrat."""
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(JETSON))
    _cuda_folders(program, ["cuda_jetpack5"])
    inventory.license_inventory(program / "licences.json")
    limits = json.loads((program / "licences.json").read_text(encoding="utf-8"))["limits"]
    assert [limit for limit in limits if "NVIDIA" in limit] == [
        "NVIDIA CUDA libraries from the official Ollama archives with no NVIDIA license text beside them (empty notices); "
        "attributed by file name to the NVIDIA CUDA Toolkit EULA, Attachment A (nvidia_cuda_license); the EULA version "
        "in force for each library is not checked"]


@pytest.mark.skipif(sys.platform == "win32", reason="liens W018 posés sous Linux")
def test_link_targets_are_resolved_once_and_only_notice_names_are_located(program, monkeypatch):
    """Constat 4 : 31 366 fichiers de distributions pour 267 noms d'avis sur le poste J8 ; le filtre de nom passe avant
    la localisation, et les cibles des liens `.venv` et `.runtime` ne sont résolues qu'une fois par inventaire."""
    root, storage = _program_with_links(program, linked=True)
    site = root / ".venv/lib/python3.12/site-packages"
    (storage / "venv/lib/python3.12/site-packages/paquet-1.0.dist-info").mkdir(parents=True)
    names = ["paquet-1.0.dist-info/LICENSE", *(f"paquet/module{index}.py" for index in range(40))]
    for name in names:
        (storage / "venv/lib/python3.12/site-packages" / name).parent.mkdir(parents=True, exist_ok=True)
        (storage / "venv/lib/python3.12/site-packages" / name).write_text("x", encoding="utf-8")
    distribution = Distribution(site, names)
    distribution.metadata = Metadata(Name="paquet")
    monkeypatch.setattr(inventory, "ROOT", root)
    (root / "config").mkdir()
    (root / "config/artifacts.lock.json").write_bytes((program / "config/artifacts.lock.json").read_bytes())
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    monkeypatch.setattr(inventory.importlib.metadata, "distributions", lambda: [distribution])
    located, link_resolutions = [], []
    real_project_path, real_resolve = inventory.project_path, Path.resolve

    def project_path(path, *args, **kwargs):
        located.append(path.name)
        return real_project_path(path, *args, **kwargs)

    def resolve(self, *args, **kwargs):
        if self in (root / ".venv", root / ".runtime"):
            link_resolutions.append(self.name)
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(inventory, "project_path", project_path)
    monkeypatch.setattr(Path, "resolve", resolve)
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in report["python"][0]["notices"]] == [
        str(Path(".venv/lib/python3.12/site-packages/paquet-1.0.dist-info/LICENSE"))]
    # Hors avis, seul le dossier de l'interpréteur est localisé (redistributed_in_project de CPython).
    assert all(inventory.notice_name(name) or name == Path(sys.base_prefix).name
               for name in located), "seuls les noms d'avis sont localisés"
    assert sorted(link_resolutions) == [".runtime", ".venv"]


OPENMP_FILES = [("libgomp.so.1.0.0", b"gomp"), ("libomp.so", b"omp"), ("libggml-base.so.0.24.0", b"base"),
                ("GO_LICENSE", b"Go"), ("LLAMA_CPP_LICENSE", b"MIT")]


def test_openmp_runtimes_of_the_ollama_archive_are_listed_with_their_attributed_license(program, monkeypatch):
    """libgomp (GCC) et libomp (LLVM) de lib/ollama, sans avis joint dans l'archive officielle 0.35.0 (J8, revue runtime) :
    licence attribuée par le nom de fichier d'après les sources officielles de GCC et de LLVM."""
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(JETSON))
    library_root = program / ".runtime/bin/ollama-0.35.0/lib/ollama"
    library_root.mkdir(parents=True)
    for name, data in OPENMP_FILES:
        (library_root / name).write_bytes(data)
    if sys.platform != "win32":
        (library_root / "libgomp.so.1").symlink_to("libgomp.so.1.0.0")
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    listed = report["openmp_runtime_libraries"]
    assert [(item["component"], item["publisher"], item["license"], item["license_source"], item["source"], item["notices"])
            for item in listed] == [
        ("GNU Offloading and Multi Processing Runtime Library (libgomp)", "Free Software Foundation (GCC)",
         "GNU General Public License v3 or later with the GCC Runtime Library Exception 3.1",
         "https://gcc.gnu.org/git/?p=gcc.git;a=blob;f=libgomp/libgomp.h;hb=refs/tags/releases/gcc-8.5.0",
         "https://ici/base.tar.zst", []),
        ("LLVM OpenMP runtime (libomp)", "LLVM Project", "Apache License v2.0 with LLVM Exceptions",
         "https://llvm.org/LICENSE.txt", "https://ici/base.tar.zst", [])]
    assert [Path(item["path"]).name for item in listed] == ["libgomp.so.1.0.0", "libomp.so"]
    assert [item["bytes"] for item in listed] == [4, 3] and not any(Path(item["path"]).is_absolute() for item in listed)
    assert [limit for limit in report["limits"] if "OpenMP" in limit] == [
        "OpenMP runtimes from the official Ollama archive (libgomp, libomp) with no GCC or LLVM license text beside them "
        "(empty notices); license attributed by file name (license_source), the runtime version is not checked"]


def test_openmp_notice_named_after_the_runtime_is_kept_and_lifts_the_limit(program, monkeypatch):
    monkeypatch.setattr(inventory, "host_signals", lambda: dict(JETSON))
    library_root = program / ".runtime/bin/ollama-0.35.0/lib/ollama"
    library_root.mkdir(parents=True)
    for name, data in [*OPENMP_FILES, ("LIBGOMP_LICENSE", b"GPLv3 + RLE"), ("LLVM_OPENMP_LICENSE.txt", b"Apache")]:
        (library_root / name).write_bytes(data)
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    assert [[Path(notice["path"]).name for notice in item["notices"]] for item in report["openmp_runtime_libraries"]] == [
        ["LIBGOMP_LICENSE"], ["LLVM_OPENMP_LICENSE.txt"]]
    assert not any("OpenMP" in limit for limit in report["limits"])


def test_windows_archive_without_openmp_runtime_adds_no_entry(program, monkeypatch):
    monkeypatch.setattr(inventory, "WINDOWS", True)
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None})
    library_root = program / ".runtime/bin/ollama-0.35.0/lib/ollama"
    library_root.mkdir(parents=True)
    for name in ("ggml-base.dll", "llama.dll", "cuda_v12/cudart64_12.dll"):
        (library_root / name).parent.mkdir(parents=True, exist_ok=True)
        (library_root / name).write_bytes(b"dll")
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    assert report["openmp_runtime_libraries"] == [] and not any("OpenMP" in limit for limit in report["limits"])


# --- Rejeu R3 (J8) : orthographe « licence », dossier licenses/ de PEP 639, lien node_modules, aide de --output ---

def _site_distribution(program, name, files):
    """Distribution installée sous .venv du programme (sans lien) : chaque fichier listé existe."""
    site = program / ".venv/lib/python3.12/site-packages"
    for relative in files:
        (site / relative).parent.mkdir(parents=True, exist_ok=True)
        (site / relative).write_text(relative, encoding="utf-8")
    distribution = Distribution(site, files)
    distribution.metadata = Metadata(Name=name)
    return distribution


def test_licence_spelling_and_the_pep_639_license_folder_hold_notices(program, monkeypatch):
    """R3 : et_xmlfile, openpyxl, semchunk, tqdm (LICENCE) et pypdfium2 (dist-info/licenses/LICENSES/Apache-2.0.txt…)
    étaient rapportés sans avis alors que leur texte est installé ; tools/dist/notices.py reconnaît déjà « licen[cs]e »."""
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    files = ["et_xmlfile-2.0.0.dist-info/LICENCE.rst", "et_xmlfile-2.0.0.dist-info/LICENCE.python",
             "et_xmlfile-2.0.0.dist-info/licenses/LICENCE", "et_xmlfile-2.0.0.dist-info/licenses/LICENSES/Apache-2.0.txt",
             "et_xmlfile-2.0.0.dist-info/licenses/data/linux_arm64/BUILD_LICENSES/abseil.txt",
             "et_xmlfile-2.0.0.dist-info/licenses/AUTHORS", "et_xmlfile-2.0.0.dist-info/METADATA", "et_xmlfile-2.0.0.dist-info/RECORD",
             "et_xmlfile/COPYRIGHT", "et_xmlfile/Apache-2.0.txt", "et_xmlfile/licenses/README", "et_xmlfile/module.py"]
    distribution = _site_distribution(program, "et_xmlfile", files)
    monkeypatch.setattr(inventory.importlib.metadata, "distributions", lambda: [distribution])
    inventory.license_inventory(program / "licences.json")
    notices = json.loads((program / "licences.json").read_text(encoding="utf-8"))["python"][0]["notices"]
    site = Path(".venv/lib/python3.12/site-packages")
    # Hors du dossier licenses/ d'un *.dist-info, un nom sans terme d'avis n'en est pas un (Apache-2.0.txt, README).
    assert [item["path"] for item in notices] == [str(site / name) for name in files[:6]] + [str(site / "et_xmlfile/COPYRIGHT")]


def test_notice_names_follow_the_kit_rule_and_keep_the_former_terms():
    from tools.dist.notices import LICENSE_FILE

    # Même expression que le kit Windows (une seule règle de nom pour les deux composants).
    assert inventory.NOTICE_FILE.pattern == LICENSE_FILE.pattern
    for name in ("LICENSE", "LICENCE.rst", "LICENSES.txt", "COPYING", "NOTICE.md", "COPYRIGHT", "ThirdPartyNotices.txt",
                 "MIT-LICENSE", "LLAMA_CPP_LICENSE",
                 # Termes cherchés dans tout le nom depuis l'origine : avis réels de tslib et de typescript (pnpm, J8).
                 "CopyrightNotice.txt", "ThirdPartyNoticeText.txt", "COPYING3", "UNLICENSE"):
        assert inventory.notice_name(name), name
    for name in ("README.md", "Apache-2.0.txt", "package.json", "AUTHORS", "libcudart.so.11.4.298"):
        assert not inventory.notice_name(name), name


@pytest.mark.skipif(sys.platform == "win32", reason="lien apps/web/node_modules posé sous Linux (W018)")
def test_npm_notices_behind_a_node_modules_link_and_cpython_inside_the_project_have_project_paths(program, monkeypatch, tmp_path_factory):
    """R3 : depuis 419b526, apps/web/node_modules est un lien vers un autre volume ; les 70 chemins d'avis npm et celui de
    CPython sortaient absolus (/media/…) dans un rapport dont la sortie par défaut est versionnée."""
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    volume = tmp_path_factory.mktemp("volume")
    package = volume / "web/node_modules/.pnpm/paquet@1.0.0/node_modules/paquet"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": "paquet", "version": "1.0.0", "license": "MIT"}), encoding="utf-8")
    for name in ("LICENCE", "CopyrightNotice.txt", "index.js"):
        (package / name).write_text(name, encoding="utf-8")
    (program / "apps/web").mkdir(parents=True)
    (program / "apps/web/node_modules").symlink_to(volume / "web/node_modules", target_is_directory=True)
    python_root = program / ".runtime/python/cpython-3.12.14-linux-aarch64-gnu"
    (python_root / "lib/python3.12").mkdir(parents=True)
    (python_root / "lib/python3.12/LICENSE.txt").write_text("PSF", encoding="utf-8")
    monkeypatch.setattr(inventory, "sys", SimpleNamespace(base_prefix=str(python_root), version_info=sys.version_info, version="3.12.14 (simulé)"))
    inventory.license_inventory(program / "licences.json")
    report = json.loads((program / "licences.json").read_text(encoding="utf-8"))
    pnpm = Path("apps/web/node_modules/.pnpm/paquet@1.0.0/node_modules/paquet")
    assert sorted(item["path"] for item in report["npm"][0]["notices"]) == [str(pnpm / "CopyrightNotice.txt"), str(pnpm / "LICENCE")]
    cpython = report["runtime_prerequisites"][0]
    assert cpython["path"] == str(Path(".runtime/python/cpython-3.12.14-linux-aarch64-gnu")) and cpython["redistributed_in_project"] is True
    assert str(volume) not in (program / "licences.json").read_text(encoding="utf-8")


def test_cpython_outside_the_project_keeps_its_absolute_path(program, monkeypatch, tmp_path_factory):
    monkeypatch.setattr(inventory, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": None, "jetpack": None})
    python_root = tmp_path_factory.mktemp("systeme") / "python3.12"
    python_root.mkdir()
    monkeypatch.setattr(inventory, "sys", SimpleNamespace(base_prefix=str(python_root), version_info=sys.version_info, version="3.12.14 (simulé)"))
    inventory.license_inventory(program / "licences.json")
    cpython = json.loads((program / "licences.json").read_text(encoding="utf-8"))["runtime_prerequisites"][0]
    assert cpython["path"] == str(python_root) and cpython["redistributed_in_project"] is False


def test_output_option_help_names_the_default_tracked_file():
    """R3 : l'aide affichait « --output OUTPUT » sans texte, alors que la sortie par défaut est un dossier suivi par Git."""
    completed = subprocess.run([sys.executable, "-m", "services.runtime.inventory", "--help"], cwd=inventory.ROOT, capture_output=True,
                               text=True, encoding="utf-8", timeout=120, check=False)
    assert completed.returncode == 0, completed.stderr
    help_text = " ".join(completed.stdout.split())
    assert "--output" in help_text and "RAG_Local_Agents/reports/licenses.json" in help_text and "Git" in help_text
    assert "remplacé" in help_text and ".runtime/qa/" in help_text
