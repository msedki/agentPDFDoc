"""Inventaire reproductible des versions, licences déclarées et avis présents."""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .accelerator import GPU_GROUP, entries_for_host, host_signals
from .artifacts import ROOT, file_hash, write_json_atomic
from .platforms import WINDOWS, entries_for_platform, executable_name, platform_id

# Dossiers que la disposition W018 peut placer sur un autre volume par un lien (comme program_executable du superviseur).
LINKED_ROOTS = (".runtime", ".venv")
# Racine du projet et cibles résolues de LINKED_ROOTS, chacune avec le préfixe du chemin rendu (project_roots).
Roots = list[tuple[Path, Path]]
# Archives officielles de uv 0.12.21 que vérifient bootstrap.sh (Linux aarch64 et x86-64) et bootstrap.ps1 (Windows).
UV_ARCHIVES = ("uv-aarch64-unknown-linux-gnu.tar.gz", "uv-x86_64-unknown-linux-gnu.tar.gz", "uv-x86_64-pc-windows-msvc.zip")
# Bibliothèques NVIDIA des archives officielles d'Ollama, d'après leur nom de fichier (Linux et Windows) ; elles relèvent de
# l'annexe A du contrat de licence du CUDA Toolkit, que ces archives ne joignent pas (J8, D09.5).
NVIDIA_CUDA_LIBRARY = re.compile(r"^(?:lib)?(cublaslt|cublas|cudart)", re.IGNORECASE)
NVIDIA_COMPONENTS = {"cublaslt": "CUDA BLAS Library (cuBLASLt)", "cublas": "CUDA BLAS Library (cuBLAS)", "cudart": "CUDA Runtime"}
CUDA_EULA = {"name": "NVIDIA CUDA Toolkit EULA (License Agreement for NVIDIA Software Development Kits)",
             "url": "https://docs.nvidia.com/cuda/eula/",
             "redistribution_terms": "1.1.1 License Grant (distribution of the portions identified as distributable), "
                                     "1.1.2 Distribution Requirements, Attachment A (CUDA Runtime, CUDA BLAS Library)",
             "consulted": "v13.4, last updated 2026-01-26, read 2026-10-02; the EULA in force for each library version is not checked"}
# Runtimes OpenMP que l'archive de base d'Ollama pose dans lib/ollama sous Linux (libgomp.so.1.0.0 et libomp.so en 0.35.0),
# sans texte de licence (revue runtime J8). Licence attribuée par le nom de fichier d'après les sources officielles lues le
# 2026-10-02 : en-tête de libgomp/libgomp.h dans le dépôt de GCC, et LICENSE.txt du projet LLVM, dont relève OpenMP.
OPENMP_RUNTIME = re.compile(r"^(libgomp|libomp)\.so(?:\.\d+)*$")
OPENMP_RUNTIMES = {
    "libgomp": {"component": "GNU Offloading and Multi Processing Runtime Library (libgomp)",
                "publisher": "Free Software Foundation (GCC)",
                "license": "GNU General Public License v3 or later with the GCC Runtime Library Exception 3.1",
                "license_source": "https://gcc.gnu.org/git/?p=gcc.git;a=blob;f=libgomp/libgomp.h;hb=refs/tags/releases/gcc-8.5.0"},
    "libomp": {"component": "LLVM OpenMP runtime (libomp)", "publisher": "LLVM Project",
               "license": "Apache License v2.0 with LLVM Exceptions", "license_source": "https://llvm.org/LICENSE.txt"},
}
# Avis rattachés à un runtime OpenMP : fichiers d'avis du même dossier dont le nom cite le runtime ou son projet.
OPENMP_NOTICE_NAMES = {"libgomp": ("gomp", "gcc"), "libomp": ("libomp", "openmp", "llvm")}
NOTICE_TERMS = ("license", "copying", "notice")


def project_roots() -> Roots:
    """Racine du projet, puis cibles résolues des liens `.runtime` et `.venv` (W018), avec le préfixe rendu pour chacune.

    license_inventory les résout une fois et les passe à chaque localisation : le poste J8 compte 31 366 fichiers de
    distributions Python, dont 267 seulement portent un nom d'avis (revue runtime, constat 4).
    """
    return [(ROOT, Path()), *(((ROOT / folder).resolve(), Path(folder)) for folder in LINKED_ROOTS)]


def project_path(path: Path, roots: Roots | None = None) -> Path | None:
    """Chemin relatif au projet, ou None si le fichier résolu sort du projet.

    Un fichier derrière le lien `.runtime` ou `.venv` (W018) appartient au projet : il est jugé d'après la cible résolue
    de ces dossiers, non d'après celle de chaque fichier ; le chemin rendu garde les liens du projet non résolus.
    `roots` (project_roots) évite de résoudre ces liens à chaque appel.
    """
    resolved = path.resolve()
    for root, alias in project_roots() if roots is None else roots:
        if resolved.is_relative_to(root):
            return path.relative_to(ROOT) if path.is_relative_to(ROOT) else alias / resolved.relative_to(root)
    return None


def notice(path: Path, roots: Roots | None = None) -> dict:
    location = project_path(path, roots)
    return {"path": str(location if location is not None else path.resolve()), "bytes": path.stat().st_size,
            "sha256": file_hash(path)}


def node_prerequisite(node_path: str, roots: Roots | None = None) -> dict:
    """Node.js trouvé dans PATH : version déclarée par l'exécutable et avis de son archive officielle.

    Windows : LICENSE et node_modules à côté de node.exe. Linux (archive officielle, ou nvm qui l'extrait) : bin/node,
    LICENSE dans le dossier parent et corepack sous lib/node_modules.
    """
    if WINDOWS:
        node_root = Path(node_path).parent
        candidates = [node_root / "LICENSE", node_root / "node_modules/corepack/LICENSE.md"]
    else:
        node_root = Path(node_path).resolve().parent.parent
        candidates = [node_root / "LICENSE", node_root / "lib/node_modules/corepack/LICENSE.md"]
    try:
        completed = subprocess.run([node_path, "--version"], capture_output=True, text=True, timeout=30, check=False)
        version = completed.stdout.strip().removeprefix("v") if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        version = None
    return {"name": "Node.js", "version": version or None, "path": str(node_path), "redistributed_in_project": False,
            "notices": [notice(path, roots) for path in candidates if path.is_file()]}


def ollama_archives(lock: dict, signals: dict) -> tuple[dict[str, str | None], dict[str, str]]:
    """Archives d'Ollama de la plateforme du poste : dossier d'extraction → archive de base, variante → complément.

    Toutes les entrées de la plateforme comptent, pas seulement celles que retient ce poste : cuda_jetpack5 vient du
    complément jetpack5 même quand la version de Jetson Linux n'est pas lue ou que `.runtime` vient d'un autre Jetson
    (revue runtime, constat 2). Un dossier d'extraction sans archive de base dans le verrou est associé à None.
    """
    entries = [entry for group in ("ollama", GPU_GROUP)
               for entry in entries_for_platform(lock["groups"].get(group, []), signals.get("platform") or None)]
    bases: dict[str, str | None] = {entry["extract_to"]: None for entry in entries if entry.get("extract_to")}
    bases.update({entry["extract_to"]: entry["url"] for entry in entries if entry.get("extract_to") and not entry.get("variant")})
    return dict(sorted(bases.items())), {entry["variant"]: entry["url"] for entry in entries if entry.get("variant")}


def nvidia_cuda_libraries(lock: dict, signals: dict, roots: Roots | None = None) -> list[dict]:
    """Bibliothèques NVIDIA posées par les archives d'Ollama de ce poste (lib/ollama/cuda_*), avec l'archive d'origine.

    Les liens internes (libcudart.so.11.0 vers libcudart.so.11.4.298) ne sont pas recomptés ; `notices` liste les
    fichiers d'avis du même dossier, vide quand l'archive amont n'en joint aucun. L'archive d'origine est le complément
    qui déclare le dossier, sinon l'archive de base.
    """
    bases, complements = ollama_archives(lock, signals)
    result = []
    for extracted, base in bases.items():
        library_root = ROOT / extracted / "lib/ollama"
        if not library_root.is_dir():
            continue
        for folder in sorted(item for item in library_root.iterdir() if item.is_dir() and item.name.startswith("cuda_")):
            files = sorted(item for item in folder.iterdir() if item.is_file() and not item.is_symlink())
            notices = [notice(item, roots) for item in files
                       if any(term in item.name.lower() for term in (*NOTICE_TERMS, "eula"))]
            for path in files:
                match = NVIDIA_CUDA_LIBRARY.match(path.name)
                if not match:
                    continue
                version = re.search(r"\.so\.(\d+(?:\.\d+)+)$", path.name)
                location = project_path(path, roots)
                result.append({"component": NVIDIA_COMPONENTS[match.group(1).lower()], "publisher": "NVIDIA Corporation",
                               "variant": folder.name, "version": version.group(1) if version else None,
                               "path": str(location if location is not None else path.resolve()),
                               "bytes": path.stat().st_size, "source": complements.get(folder.name, base),
                               "license": CUDA_EULA["name"], "notices": notices})
    return result


def openmp_runtime_libraries(lock: dict, signals: dict, roots: Roots | None = None) -> list[dict]:
    """Runtimes OpenMP (libgomp, libomp) posés par les archives d'Ollama sous lib/ollama, avec leur licence attribuée.

    Les liens (libgomp.so.1 vers libgomp.so.1.0.0) ne sont pas recomptés. `notices` ne retient que les fichiers d'avis du
    même dossier dont le nom cite le runtime ou son projet : ceux de Go, de llama.cpp ou de cpp-httplib n'en sont pas.
    """
    bases, complements = ollama_archives(lock, signals)
    result = []
    for extracted, base in bases.items():
        library_root = ROOT / extracted / "lib/ollama"
        if not library_root.is_dir():
            continue
        for path in sorted(library_root.rglob("*")):
            match = OPENMP_RUNTIME.match(path.name)
            if not match or path.is_symlink() or not path.is_file():
                continue
            runtime = match.group(1)
            names = OPENMP_NOTICE_NAMES[runtime]
            notices = [notice(item, roots) for item in sorted(path.parent.iterdir()) if item.is_file()
                       and any(term in item.name.lower() for term in NOTICE_TERMS)
                       and any(name in item.name.lower() for name in names)]
            location = project_path(path, roots)
            result.append({**OPENMP_RUNTIMES[runtime], "path": str(location if location is not None else path.resolve()),
                           "bytes": path.stat().st_size,
                           "source": base if path.parent == library_root else complements.get(path.parent.name, base),
                           "notices": notices})
    return result


def license_inventory(output: Path) -> dict:
    result: dict[str, Any] = {"created_at_utc": datetime.now(UTC).isoformat(),
                              "scope": "installed project dependencies and provisioned artefacts; metadata is not legal certification",
                              "python": [], "npm": [], "artifacts": [], "native_notices": [],
                              "runtime_prerequisites": [], "limits": []}
    roots = project_roots()
    python_root = Path(sys.base_prefix)
    # Windows : LICENSE.txt à la racine de l'installation ; Linux (python-build-standalone) : dans lib/python3.x.
    python_licenses = [python_root / "LICENSE.txt",
                       python_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"]
    result["runtime_prerequisites"].append({"name": "CPython", "version": sys.version.split()[0],
        "path": str(python_root), "redistributed_in_project": project_path(python_root, roots) is not None,
        "notices": [notice(path, roots) for path in python_licenses if path.is_file()]})
    uv = {"name": "uv", "version": "0.12.21", "redistributed_in_project": True, "notices": [notice(path, roots) for path in
          sorted((ROOT / ".runtime/bootstrap").glob("uv-*.dist-info/licenses/*")) if path.is_file()]}
    if not uv["notices"]:
        # bootstrap.sh et bootstrap.ps1 n'extraient que les exécutables, et les trois archives officielles qu'ils vérifient
        # (SHA-256 des scripts) ne contiennent que uv et uvx, ou uv.exe, uvw.exe et uvx.exe (J8, L0 ; relevé du 2026-10-02).
        uv["missing_notice"] = ("No uv license text in the project: bootstrap installs only the uv executables, and the official "
                                f"0.12.21 archives it verifies ({', '.join(UV_ARCHIVES)}) hold only the executables. Upstream "
                                "declares MIT OR Apache-2.0, with LICENSE-MIT and LICENSE-APACHE in "
                                "https://github.com/astral-sh/uv/tree/0.12.21")
    result["runtime_prerequisites"].append(uv)
    node_path = shutil.which(executable_name("node"))
    if node_path:
        result["runtime_prerequisites"].append(node_prerequisite(node_path, roots))
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata.get("Name", "")):
        # Distributions installées sur disque : locate_file rend un pathlib.Path (resolve() l'exige déjà).
        files = [cast(Path, distribution.locate_file(file)) for file in distribution.files or []]
        # Nom d'avis d'abord : seuls ces fichiers sont localisés (constat 4).
        notices = [notice(path, roots) for path in files if any(key in path.name.lower() for key in NOTICE_TERMS)
                   and path.is_file() and project_path(path, roots) is not None]
        metadata = distribution.metadata
        result["python"].append({"name": metadata.get("Name"), "version": distribution.version,
            "license_expression": metadata.get("License-Expression"),
            "license_field": metadata.get("License"),
            "license_classifiers": [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")],
            "notices": notices})
    packages = ROOT / "apps/web/node_modules/.pnpm"
    seen = set()
    for path in sorted(packages.rglob("package.json")):
        if path.is_symlink() or "node_modules" not in path.parts:
            continue
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        identity = (package.get("name"), package.get("version"))
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        notices = [notice(p, roots) for p in path.parent.iterdir() if p.is_file() and
                   any(term in p.name.lower() for term in ("license", "copying", "notice"))]
        result["npm"].append({"name": identity[0], "version": identity[1], "license": package.get("license"),
                              "metadata_sha256": file_hash(path), "notices": notices})
    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    result["platform"] = platform_id()
    # Indices du poste (plateforme, version de Jetson Linux) : même règle que provision_artifacts.
    signals = host_signals()
    for group, artifacts in lock["groups"].items():
        # Artefacts de ce poste seulement, selon la règle de provision (plateforme, puis champ host) : ceux d'une autre
        # plateforme ou d'un autre Jetson ne sont ni provisionnés ni livrés ici.
        for artifact in entries_for_host(artifacts, signals):
            path = ROOT / artifact["target"]
            result["artifacts"].append({"group": group, "publisher": artifact.get("publisher"),
                "version": artifact.get("version"), "revision": artifact.get("revision"),
                "declared_license": artifact.get("license"), "source": artifact["url"],
                "file": notice(path, roots) if path.is_file() else None, "provisioned": path.is_file()})
    for parent in (ROOT / ".runtime/bin", ROOT / ".runtime/models"):
        for path in sorted(parent.rglob("*")):
            if path.is_file() and any(term in path.name.lower() for term in NOTICE_TERMS):
                result["native_notices"].append(notice(path, roots))
    result["nvidia_cuda_libraries"] = nvidia_cuda_libraries(lock, signals, roots)
    if result["nvidia_cuda_libraries"]:
        result["nvidia_cuda_license"] = CUDA_EULA
    result["openmp_runtime_libraries"] = openmp_runtime_libraries(lock, signals, roots)
    comparison_manifest = ROOT / ".runtime/manifests/embedding-comparison.json"
    comparison_lock = ROOT / "config/embedding-comparison.lock.json"
    if comparison_manifest.is_file() and comparison_lock.is_file():
        data = json.loads(comparison_manifest.read_text(encoding="utf-8"))
        comparison = json.loads(comparison_lock.read_text(encoding="utf-8"))
        entries = [*comparison["files"]]
        if comparison.get("license_notice"):
            entries.append(comparison["license_notice"])
        result["optional_embedding_comparison"] = {
            "purpose": comparison["scope"], "model_id": comparison["model_id"],
            "revision": comparison["revision"], "manifest_state": data["state"],
            "lock_sha256": file_hash(comparison_lock), "manifest_sha256": file_hash(comparison_manifest),
            "artifacts": [{"publisher": entry.get("publisher"), "declared_license": entry.get("license"),
                "source": entry["url"], "file": notice(ROOT / entry["target"], roots)
                if (ROOT / entry["target"]).is_file() else None} for entry in entries],
            "limit": "Presence and metadata inventory; does not prove inference or an IBM-bundled NOTICE.",
        }
    for key, name in (("ollama_model", "ollama-model.json"), ("ollama_text_model", "ollama-model-text.json")):
        manifest = ROOT / ".runtime/manifests" / name
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            result[key] = {"model": data["model"], "license_notice": data.get("license"),
                           "derived_from": data.get("source_model"), "manifest_sha256": file_hash(manifest)}
    result["limits"] = [
        "Tesseract Windows installed copy has verified local hashes, but installer provenance not independently authenticated"
        if WINDOWS else "Tesseract 5.4.0 and Leptonica 1.87.0 built locally from the locked source archives (tesseract-source)",
        "License declarations and bundled notice paths are recorded; no compatibility or redistribution opinion is inferred",
        "Development dependencies are included because they are installed in this environment",
    ]
    if any(not item["notices"] for item in result["nvidia_cuda_libraries"]):
        result["limits"].append("NVIDIA CUDA libraries from the official Ollama archives with no NVIDIA license text beside them "
                                "(empty notices); attributed by file name to the NVIDIA CUDA Toolkit EULA, Attachment A "
                                "(nvidia_cuda_license); the EULA version in force for each library is not checked")
    if any(not item["notices"] for item in result["openmp_runtime_libraries"]):
        result["limits"].append("OpenMP runtimes from the official Ollama archive (libgomp, libomp) with no GCC or LLVM license "
                                "text beside them (empty notices); license attributed by file name (license_source), the "
                                "runtime version is not checked")
    write_json_atomic(output, result)
    return {"path": str(output), "python_distributions": len(result["python"]), "npm_packages": len(result["npm"]),
            "artifact_files": len(result["artifacts"]), "bundled_notices": len(result["native_notices"]),
            "nvidia_cuda_libraries": len(result["nvidia_cuda_libraries"]),
            "openmp_runtime_libraries": len(result["openmp_runtime_libraries"]), "limits": result["limits"]}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "RAG_Local_Agents/reports/licenses.json")
    args = parser.parse_args()
    print(json.dumps(license_inventory(args.output), ensure_ascii=False, indent=2))
