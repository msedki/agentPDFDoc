"""Prérequis locaux placés dans le projet, sans installation globale ni élévation de privilèges.

Windows (W001) : copie vérifiée d'une installation Tesseract 5.4.0 existante.
Linux (W018) : Leptonica puis Tesseract 5.4.0 compilés depuis les sources du groupe `tesseract-source`
de `config/artifacts.lock.json`, sous `.runtime/build/`, en un exécutable lié statiquement à ces deux
bibliothèques et dynamiquement aux seules bibliothèques du système.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import ARTIFACT_LOCK, ROOT, download, file_hash, write_json_atomic
from .platforms import entries_for_platform, native_executable, platform_id


def tesseract(profile: dict, *, offline: bool = False) -> dict:
    if sys.platform != "win32":
        return build_tesseract(profile, offline=offline)
    target_exe = (ROOT / profile["pdf"]["tesseract_cmd"]).resolve()
    manifest_path = ROOT / ".runtime/manifests/tesseract-installed-copy.json"
    if target_exe.is_file() and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = (ROOT / item["path"]).resolve()
            if not path.is_relative_to(target_exe.parent) or not path.is_file() or file_hash(path) != item["sha256"]:
                raise ValueError("Copie Tesseract non conforme au manifeste ; aucun remplacement implicite")
        return {"status": "verified_installed_copy", "publisher_provenance": "not_independently_authenticated"}
    if target_exe.exists() or manifest_path.exists():
        raise ValueError("Copie Tesseract incomplète : conserver et diagnostiquer les fichiers")
    candidates = [Path(shutil.which("tesseract.exe") or "__absent__")]
    for parent in [os.environ.get("LOCALAPPDATA"), os.environ.get("PROGRAMFILES")]:
        if parent:
            candidates.extend([Path(parent) / "Programs/Tesseract-OCR/tesseract.exe",
                               Path(parent) / "Tesseract-OCR/tesseract.exe"])
    executable = next((p.resolve() for p in candidates if p.is_file()), None)
    if executable is None:
        raise FileNotFoundError("Prérequis Tesseract5.4.0 Windows absent ; fournir une installation locale vérifiable. Aucun installateur tiers n'est téléchargé automatiquement.")
    version = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=15, check=True).stdout
    if not version.startswith("tesseract v5.4.0"):
        raise ValueError("Le prérequis installé doit correspondre à Tesseract5.4.0 du profil verrouillé")
    if target_exe.parent.exists():
        raise ValueError("Destination Tesseract existante sans manifeste")
    target_exe.parent.mkdir(parents=True)
    records = []
    paths = [executable, *sorted(executable.parent.glob("*.dll"))]
    paths.extend(p for p in executable.parent.rglob("*") if p.is_file() and
                 any(term in p.name.lower() for term in ("license", "copying", "notice")))
    for path in paths:
        relative = path.relative_to(executable.parent)
        target = target_exe.parent / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append({"path": str(target.relative_to(ROOT)), "sha256": file_hash(target), "size": target.stat().st_size})
    manifest = {"source": str(executable.parent), "version_output": version,
                "origin": "existing installed Windows build; publisher package provenance not independently authenticated",
                "files": records, "offline": offline}
    write_json_atomic(manifest_path, manifest)
    return {"status": "copied_local_prerequisite", "files": len(records), "publisher_provenance": "not_independently_authenticated"}


TESSERACT_VERSION = "5.4.0"
SOURCE_GROUP = "tesseract-source"
BUILD_KIND = "tesseract-source-build"
BUILT_MANIFEST = Path(".runtime/manifests/tesseract-built.json")
BUILD_DIR = Path(".runtime/build") / f"tesseract-{TESSERACT_VERSION}"
# Hors du dossier de construction, que chaque compilation recrée : le verrou survit à son effacement.
BUILD_LOCK = Path(".runtime/build") / f"tesseract-{TESSERACT_VERSION}.lock"
BUILD_LOGS = Path(".runtime/build/logs")
BUILD_MARKER = ".agentragpdf-build"
# `cmake --install` n'existe qu'à partir de CMake 3.15 ; les deux projets exigent 3.10.
MINIMUM_CMAKE = (3, 15)
SYSTEM_LIBRARY_DIRS = ("/lib/", "/lib64/", "/usr/lib/", "/usr/lib64/")
# Outils du système d'abord ; un outil ailleurs dans le PATH n'est retenu qu'à défaut, ou si cmake y est trop ancien,
# ou si le compilateur n'y applique pas -ffile-prefix-map.
SYSTEM_TOOL_DIRS = ("/usr/bin", "/bin")
# PATH des étapes de compilation et de contrôle : ces dossiers, plus celui de chaque outil retenu hors d'eux.
COMPILATION_PATH = ("/usr/bin", "/bin")
REQUIRED_HEADERS = {"zlib.h": "zlib (paquet Ubuntu zlib1g-dev)", "png.h": "libpng (libpng-dev)",
                    "jpeglib.h": "libjpeg (libjpeg-dev)", "tiffio.h": "libtiff (libtiff-dev)"}
_SOURCE_PUBLISHERS = {"leptonica": "DanBloomberg/leptonica", "tesseract": "tesseract-ocr/tesseract"}
_LICENSE_FILES = {"leptonica": "leptonica-license.txt", "tesseract": "LICENSE"}

# Les chaînes du binaire (__FILE__ des assertions de Tesseract) contiendraient sinon le chemin absolu du dossier de
# construction, donc le dossier personnel de l'utilisateur, et son empreinte dépendrait de l'emplacement du projet.
# L'option apparaît dans le manuel de GCC 8.1.0 (« Overall Options »), absente de celui de GCC 7.5.0, et dans les
# notes de version de Clang 10.0.0 (« New Compiler Flags »). build_tools retient le premier compilateur qui
# l'applique, système d'abord ; missing_build_prerequisites refuse, avant la configuration, un compilateur retenu qui
# ne l'applique pas, et un compilateur qui l'ignorerait malgré tout est arrêté par le contrôle des chaînes du binaire
# (absolute_build_paths). Le jeton est remplacé à la compilation par ce dossier (et par son chemin résolu s'il passe
# par un lien) ; les options consignées restent indépendantes de l'emplacement.
BUILD_ROOT_TOKEN = "<build_root>"
FILE_PREFIX_MAP = f"-ffile-prefix-map={BUILD_ROOT_TOKEN}=."
FILE_PREFIX_MAP_MINIMUM = "GCC 8 ou Clang 10 au minimum"
COMPILER_NAMES = {"cc": ("cc", "gcc", "clang"), "c++": ("c++", "g++", "clang++")}

# Options relues dans les CMakeLists.txt des archives verrouillées (Leptonica 1.87.0, Tesseract 5.4.0).
# Une variable que le projet n'utilise pas fait échouer la configuration au lieu d'être ignorée.
LEPTONICA_OPTIONS = (
    "-DCMAKE_BUILD_TYPE=Release",
    # project(leptonica LANGUAGES C) : CMAKE_CXX_FLAGS y serait une variable inutilisée.
    f"-DCMAKE_C_FLAGS={FILE_PREFIX_MAP}",
    # Le README annonce des bibliothèques partagées par défaut : la liaison statique évite LD_LIBRARY_PATH.
    "-DBUILD_SHARED_LIBS=OFF",
    # LeptonicaConfig.cmake s'installe sous ${CMAKE_INSTALL_LIBDIR}/cmake/leptonica, chemin passé à Tesseract.
    "-DCMAKE_INSTALL_LIBDIR=lib",
    "-DBUILD_PROG=OFF",
    "-DSW_BUILD=OFF",
    # Avec STRICT_CONF, une bibliothèque d'image activée mais introuvable arrête la configuration.
    "-DSTRICT_CONF=ON",
    "-DENABLE_ZLIB=ON", "-DENABLE_PNG=ON", "-DENABLE_JPEG=ON", "-DENABLE_TIFF=ON",
    "-DENABLE_GIF=OFF", "-DENABLE_WEBP=OFF", "-DENABLE_OPENJPEG=OFF",
)
TESSERACT_OPTIONS = (
    "-DCMAKE_BUILD_TYPE=Release",
    f"-DCMAKE_C_FLAGS={FILE_PREFIX_MAP}",
    f"-DCMAKE_CXX_FLAGS={FILE_PREFIX_MAP}",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DCMAKE_INSTALL_LIBDIR=lib",
    "-DSW_BUILD=OFF",
    "-DBUILD_TRAINING_TOOLS=OFF",
    "-DBUILD_TESTS=OFF",
    "-DDISABLE_ARCHIVE=ON",
    "-DDISABLE_CURL=ON",
    "-DGRAPHICS_DISABLED=ON",
    "-DOPENMP_BUILD=OFF",
    # Sans -march=native, le binaire ne dépend pas du cœur qui l'a compilé ; NEON reste détecté pour aarch64.
    "-DENABLE_NATIVE=OFF",
    # L'OSD (`--psm 0 -l osd`, orientation des régions) repose sur le moteur historique.
    "-DDISABLED_LEGACY_ENGINE=OFF",
    # LSTM en float : défaut amont de CMake (FAST_FLOAT) comme d'autotools (--enable-float32). Une construction
    # d'essai en double (FAST_FLOAT=OFF, 01/10, Linux aarch64) et la construction en float de mêmes sources et options
    # rendent les mêmes 36 lectures du glyphe « V » des cellules à 0° et à 90° de l'essai OCR (12 échelles ; --psm 6 ;
    # fra+eng, fra, eng) : mêmes textes, mêmes confiances au centième de point près, précision des relevés conservés
    # (TSV arrondi à deux décimales). Ce réglage n'explique donc pas l'échec du cas à 90° sous Linux. Rien n'est
    # établi ainsi sur l'écart avec le binaire Windows, qui n'a pas lu ces images.
    "-DFAST_FLOAT=ON",
)


class MissingBuildPrerequisites(FileNotFoundError):
    """Outils ou en-têtes de compilation absents du poste."""

    def __init__(self, missing: list[str]):
        self.missing = list(missing)
        super().__init__("Prérequis de compilation de Tesseract absents : " + " ; ".join(self.missing)
                         + ". Leur installation par le gestionnaire de paquets exige des droits d'administration, "
                         "hors du périmètre du provisionnement : aucun contournement n'est tenté.")


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def locked_tesseract_sources() -> dict[str, dict[str, Any]]:
    """Archives Leptonica et Tesseract du verrou valables pour ce poste, version de Tesseract contrôlée."""
    lock = json.loads(ARTIFACT_LOCK.read_text(encoding="utf-8"))
    entries = entries_for_platform(lock.get("groups", {}).get(SOURCE_GROUP, []))
    sources: dict[str, dict[str, Any]] = {}
    for name, publisher in _SOURCE_PUBLISHERS.items():
        matches = [entry for entry in entries if entry.get("publisher") == publisher]
        if len(matches) != 1:
            raise ValueError(f"Verrou {SOURCE_GROUP} : une archive {name} attendue pour {platform_id()}, "
                             f"{len(matches)} trouvée(s)")
        if not matches[0].get("sha256") or not matches[0].get("version"):
            raise ValueError(f"Verrou {SOURCE_GROUP} : version et SHA-256 obligatoires pour l'archive {name}")
        sources[name] = matches[0]
    if sources["tesseract"]["version"] != TESSERACT_VERSION:
        raise ValueError(f"Verrou {SOURCE_GROUP} : Tesseract {sources['tesseract']['version']} verrouillé, "
                         f"{TESSERACT_VERSION} attendu par le profil ; aucune autre version n'est compilée")
    return sources


def _source_records(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": name, "version": entry["version"], "publisher": entry["publisher"], "license": entry.get("license"),
             "url": entry["url"], "size": entry.get("size"), "sha256": entry["sha256"],
             "content_sha256": entry.get("content_sha256"), "archive": entry["target"]}
            for name, entry in sorted(sources.items())]


def _cmake_options() -> dict[str, list[str]]:
    """Options consignées au manifeste, jeton du dossier de construction compris (indépendantes de l'emplacement)."""
    return {"leptonica": list(LEPTONICA_OPTIONS), "tesseract": list(TESSERACT_OPTIONS)}


def file_prefix_map_flags(build_root: Path) -> str:
    """Drapeaux -ffile-prefix-map du dossier de construction, tel qu'écrit et, s'il passe par un lien, résolu.

    CMake insère CMAKE_<LANG>_FLAGS tel quel dans les commandes passées au shell : un chemin contenant une espace
    ou un caractère spécial est donc cité.
    """
    spellings = [str(build_root)]
    resolved = os.path.realpath(build_root)
    if resolved not in spellings:
        spellings.append(resolved)
    return " ".join(f"-ffile-prefix-map={shlex.quote(path)}=." for path in spellings)


def _expanded_options(options: list[str], build_root: Path) -> list[str]:
    flags = file_prefix_map_flags(build_root)
    return [option.replace(FILE_PREFIX_MAP, flags) for option in options]


def absolute_build_paths(binary: Path, build_root: Path) -> list[str]:
    """Chemins absolus du dossier de construction (écrit ou résolu) présents dans les octets du binaire."""
    data = binary.read_bytes()
    spellings = dict.fromkeys([str(build_root), os.path.realpath(build_root)])
    return [path for path in spellings if path.encode() in data]


def build_tools(search_path: str | None = None) -> dict[str, str | None]:
    """Outils de construction et de contrôle : dossiers système d'abord, puis le PATH de l'utilisateur.

    La priorité porte sur les dossiers avant les noms : un `gcc` de SYSTEM_TOOL_DIRS l'emporte sur un `cc` du PATH
    de l'utilisateur. Au sein d'un même groupe de dossiers, l'ordre des noms prime (cc, gcc, clang), puis celui des
    dossiers. Dans cet ordre, cmake : le premier qui atteint MINIMUM_CMAKE ; compilateurs C et C++, choisis
    indépendamment : le premier qui applique -ffile-prefix-map. À défaut, le premier trouvé, que
    missing_build_prerequisites refuse en nommant sa version.
    """
    if search_path is None:
        search_path = os.pathsep.join([*SYSTEM_TOOL_DIRS, os.environ.get("PATH", os.defpath)])
    directories = list(dict.fromkeys(directory for directory in search_path.split(os.pathsep) if directory))
    system = {os.path.normpath(directory) for directory in SYSTEM_TOOL_DIRS}
    groups = ([directory for directory in directories if os.path.normpath(directory) in system],
              [directory for directory in directories if os.path.normpath(directory) not in system])

    def found(*names: str) -> list[str]:
        paths = (shutil.which(name, path=directory) for group in groups for name in names for directory in group)
        return list(dict.fromkeys(path for path in paths if path))

    def first(*names: str) -> str | None:
        return next(iter(found(*names)), None)

    def compiler(key: str, language: str) -> str | None:
        candidates = found(*COMPILER_NAMES[key])
        # Chaque candidat est sondé sous le PATH de compilation qu'il aurait : /usr/bin, /bin et son propre dossier.
        conforming = (path for path in candidates
                      if applies_file_prefix_map(path, language, _tool_environment({key: path})))
        return next(conforming, candidates[0] if candidates else None)

    cmakes = found("cmake")
    cmake = next((path for path in cmakes if (cmake_version(path) or (0,)) >= MINIMUM_CMAKE), cmakes[0] if cmakes else None)
    return {"cmake": cmake, "cc": compiler("cc", "c"), "c++": compiler("c++", "c++"),
            "make": first("make"), "ninja": first("ninja"), "ldd": first("ldd"), "readelf": first("readelf")}


def _builder(tools: dict[str, str | None]) -> tuple[str | None, str]:
    """make et le générateur « Unix Makefiles » ; ninja seulement à défaut de make."""
    if tools.get("make"):
        return tools["make"], "Unix Makefiles"
    return tools.get("ninja"), "Ninja"


def _tool_environment(tools: dict[str, str | None]) -> dict[str, str]:
    """PATH réduit à /usr/bin:/bin et aux dossiers des seuls outils retenus ; aucune variable du chargeur ni drapeau."""
    directories = list(COMPILATION_PATH)
    for tool in (tools.get("cmake"), tools.get("cc"), tools.get("c++"), _builder(tools)[0], tools.get("ldd"),
                 tools.get("readelf")):
        if tool and str(Path(tool).parent) not in directories:
            directories.append(str(Path(tool).parent))
    return {"PATH": os.pathsep.join(directories), "LANG": "C", "LC_ALL": "C"}


def _first_line(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", env=env,
                            stdin=subprocess.DEVNULL, timeout=60, check=False)
    lines = [line.strip() for line in (result.stdout or result.stderr).splitlines() if line.strip()]
    return lines[0] if lines else ""


def cmake_version(cmake: str, env: dict[str, str] | None = None) -> tuple[int, ...] | None:
    match = re.search(r"cmake version (\d+)\.(\d+)(?:\.(\d+))?", _first_line([cmake, "--version"], env or {}))
    return tuple(int(part) for part in match.groups() if part is not None) if match else None


def _header_available(compiler: str, header: str, env: dict[str, str]) -> bool:
    source = f"#include <stddef.h>\n#include <stdio.h>\n#include <{header}>\n"
    result = subprocess.run([compiler, "-E", "-x", "c", "-", "-o", os.devnull], input=source.encode(),
                            capture_output=True, env=env, timeout=60, check=False)
    return result.returncode == 0


def applies_file_prefix_map(compiler: str, language: str, env: dict[str, str]) -> bool:
    """Le compilateur accepte -ffile-prefix-map et l'applique à __FILE__ (préprocesseur seul, aucun binaire produit).

    Un compilateur qui refuse l'option (GCC 7 : « unrecognized command line option ») ou qui l'ignore est refusé.
    """
    with tempfile.TemporaryDirectory(prefix="agentragpdf-prefix-map-") as directory:
        source = Path(directory) / ("essai.c" if language == "c" else "essai.cpp")
        source.write_text("const char *chemin = __FILE__;\n", encoding="utf-8")
        result = subprocess.run([compiler, f"-ffile-prefix-map={directory}=.", "-E", "-x", language, str(source)],
                                capture_output=True, text=True, errors="replace", env=env, stdin=subprocess.DEVNULL,
                                timeout=60, check=False)
    return result.returncode == 0 and f'"./{source.name}"' in result.stdout


def missing_build_prerequisites(tools: dict[str, str | None]) -> list[str]:
    """Prérequis absents, nommés ; les en-têtes sont vérifiés par le préprocesseur du compilateur C retenu."""
    env = _tool_environment(tools)
    labels = {"cmake": "cmake 3.15 ou plus récent", "cc": "compilateur C (cc, gcc ou clang)",
              "c++": "compilateur C++ (c++, g++ ou clang++)", "ldd": "ldd (glibc)", "readelf": "readelf (binutils)"}
    missing = [label for key, label in labels.items() if not tools.get(key)]
    if not _builder(tools)[0]:
        missing.append("outil de construction : make (ou ninja à défaut)")
    cmake = tools.get("cmake")
    if cmake:
        version = cmake_version(cmake, env)
        if version is None or version < MINIMUM_CMAKE:
            found = ".".join(str(part) for part in version) if version else "version illisible"
            missing.append(f"cmake 3.15 ou plus récent (trouvé : {found})")
    # Contrôlé avant la configuration CMake, où un refus de l'option n'apparaîtrait que comme un échec des essais de
    # compilation, sans nommer sa cause. build_tools n'a retenu un compilateur qui ne l'applique pas qu'à défaut d'un
    # autre : le recours, sans droits d'administration, est un compilateur conforme dans le PATH de l'utilisateur.
    for key, language, name in (("cc", "c", "C"), ("c++", "c++", "C++")):
        tool = tools.get(key)
        if tool and not applies_file_prefix_map(tool, language, env):
            found = _first_line([tool, "--version"], env) or "version illisible"
            names = "{}, {} ou {}".format(*COMPILER_NAMES[key])
            missing.append(f"compilateur {name} appliquant -ffile-prefix-map ({FILE_PREFIX_MAP_MINIMUM}) : aucun compilateur "
                           f"trouvé sous les noms {names} ne l'applique (premier trouvé : {found}) ; en installer un "
                           "conforme dans un dossier du PATH de l'utilisateur, retenu à défaut de celui du système")
    compiler = tools.get("cc")
    if compiler:
        missing.extend(f"en-tête {header} de {label}" for header, label in REQUIRED_HEADERS.items()
                       if not _header_available(compiler, header, env))
    return missing


def unused_cmake_variables(configure_log: str) -> list[str]:
    """Variables `-D` signalées par CMake comme inutilisées par le projet."""
    marker = "Manually-specified variables were not used by the project:"
    if marker not in configure_log:
        return []
    names: list[str] = []
    for line in configure_log.split(marker, 1)[1].splitlines():
        if line.strip():
            names.append(line.strip())
        elif names:
            break
    return names


def dynamic_dependencies(ldd_output: str, forbidden_roots: tuple[Path, ...] = ()) -> list[dict[str, str | None]]:
    """Bibliothèques chargées selon `ldd` ; refuse toute bibliothèque hors système, absente ou du projet."""
    roots = tuple(os.path.realpath(root) + os.sep for root in forbidden_roots)
    records: list[dict[str, str | None]] = []
    problems: list[str] = []
    for line in (raw.strip() for raw in ldd_output.splitlines()):
        if not line:
            continue
        path: str | None
        if "=>" in line:
            name, _, location = (part.strip() for part in line.partition("=>"))
            if location.startswith("not found"):
                problems.append(f"{name} introuvable")
                records.append({"name": name, "path": None})
                continue
            path = location.split(" (", 1)[0].strip() or None
        else:
            head = line.split(" (", 1)[0].strip()
            name, path = (Path(head).name, head) if head.startswith("/") else (head, None)
        if re.search(r"lept|tesseract", name, re.IGNORECASE):
            problems.append(f"{name} lié dynamiquement, alors que Leptonica et Tesseract doivent l'être statiquement")
        if path is not None:
            resolved = os.path.realpath(path)
            if resolved.startswith(roots):
                problems.append(f"{name} chargé depuis le projet ou la construction : {path}")
            elif not resolved.startswith(SYSTEM_LIBRARY_DIRS):
                problems.append(f"{name} chargé hors des répertoires système : {path}")
        records.append({"name": name, "path": path})
    if problems:
        raise ValueError("Dépendances dynamiques de Tesseract non conformes : " + " ; ".join(problems))
    return records


def _version_output(binary: Path) -> tuple[str, str]:
    """Sortie de `tesseract --version` sous un environnement sans variable du chargeur dynamique."""
    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, errors="replace",
                            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, stdin=subprocess.DEVNULL,
                            timeout=30, check=False)
    output = result.stdout if result.stdout.strip() else result.stderr
    first = output.strip().splitlines()[0].strip() if output.strip() else ""
    if result.returncode or first != f"tesseract {TESSERACT_VERSION}":
        raise ValueError(f"Le binaire {_display(binary)} annonce « {first} » (code {result.returncode}) "
                         f"au lieu de « tesseract {TESSERACT_VERSION} »")
    return first, output


def _check_leptonica(binary: Path, output: str, leptonica_version: str) -> None:
    if f"leptonica-{leptonica_version}" not in output:
        raise ValueError(f"Le binaire {_display(binary)} n'annonce pas Leptonica {leptonica_version} : {output.strip()!r}")


def verify_binary(binary: Path, leptonica_version: str, tools: dict[str, str | None],
                  forbidden_roots: tuple[Path, ...], build_root: Path | None = None) -> dict[str, Any]:
    """Version annoncée, Leptonica liée, dépendances dynamiques et absence de chemin du dossier de construction."""
    first, output = _version_output(binary)
    _check_leptonica(binary, output, leptonica_version)
    env = _tool_environment(tools)
    ldd = subprocess.run([str(tools["ldd"]), str(binary)], capture_output=True, text=True, errors="replace",
                         env=env, timeout=60, check=False)
    if ldd.returncode:
        raise ValueError(f"ldd refuse {_display(binary)} : {(ldd.stderr or ldd.stdout).strip()}")
    dependencies = dynamic_dependencies(ldd.stdout, forbidden_roots)
    readelf = subprocess.run([str(tools["readelf"]), "-d", str(binary)], capture_output=True, text=True,
                             errors="replace", env=env, timeout=60, check=True)
    search_paths = [line.strip() for line in readelf.stdout.splitlines() if "(RPATH)" in line or "(RUNPATH)" in line]
    if search_paths:
        raise ValueError("Le binaire construit embarque un chemin de recherche de bibliothèques : " + " ; ".join(search_paths))
    leaked = absolute_build_paths(binary, build_root) if build_root is not None else []
    if leaked:
        raise ValueError(f"Le binaire construit contient le chemin absolu du dossier de construction ({', '.join(leaked)}) : "
                         "réécriture -ffile-prefix-map sans effet, construction non reproductible")
    return {"version": first, "version_output": output, "ldd": ldd.stdout, "dynamic_dependencies": dependencies,
            "rpath": search_paths, "absolute_build_paths": leaked}


def _installed_files(target: Path) -> set[str]:
    """Fichiers attendus dans le dossier installé : le binaire et les deux licences, rien d'autre."""
    return {_display(target.parent / name) for name in (target.name, *_LICENSE_FILES.values())}


def verify_built_copy(target: Path, manifest_path: Path, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Réutilise une construction installée seulement si sources, options, fichiers et binaire concordent."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if manifest.get("kind") != BUILD_KIND or manifest.get("platform") != platform_id():
        problems.append(f"manifeste {manifest.get('kind')} pour {manifest.get('platform')}")
    if manifest.get("sources") != _source_records(sources):
        problems.append("archives sources différentes du verrou")
    if manifest.get("cmake_options") != _cmake_options():
        problems.append("options CMake différentes")
    binary = manifest.get("binary") or {}
    if binary.get("path") != _display(target) or not target.is_file() or file_hash(target) != binary.get("sha256"):
        problems.append(f"binaire {_display(target)} différent du manifeste")
    expected = _installed_files(target)
    recorded = [item.get("path") for item in manifest.get("files") or []]
    if sorted(recorded) != sorted(expected):
        problems.append("liste des fichiers du manifeste différente de " + ", ".join(sorted(expected)))
    present = {_display(path) for path in target.parent.rglob("*")}
    if present != expected:
        extra, absent = sorted(present - expected), sorted(expected - present)
        problems.append(f"contenu de {_display(target.parent)} différent de l'installation"
                        + (f" ; en trop : {', '.join(extra)}" if extra else "")
                        + (f" ; manquant : {', '.join(absent)}" if absent else ""))
    directory = target.parent.resolve()
    for item in manifest.get("files") or []:
        path = ROOT / item["path"]
        if (not path.resolve().is_relative_to(directory) or path.is_symlink() or not path.is_file()
                or file_hash(path) != item.get("sha256")):
            problems.append(f"fichier {item['path']} différent du manifeste")
    if problems:
        raise ValueError("Construction Tesseract installée non conforme au manifeste (" + " ; ".join(problems)
                         + ") ; aucun remplacement implicite : conserver pour diagnostic, ou déplacer "
                         + f"{_display(target.parent)} et {_display(manifest_path)} avant de reconstruire")
    version, output = _version_output(target)
    _check_leptonica(target, output, sources["leptonica"]["version"])
    return {"status": "verified_built_copy", "version": version, "binary": _display(target),
            "manifest": _display(manifest_path), "built_at_utc": manifest.get("built_at_utc")}


@contextmanager
def _build_lock(path: Path) -> Iterator[None]:
    """Verrou flock exclusif et non bloquant : une seule construction ou vérification à la fois sur ce projet.

    `flock` est attaché au descripteur ouvert : il est libéré à sa fermeture, y compris si le processus meurt.
    """
    if sys.platform == "win32":
        raise RuntimeError("La construction de Tesseract depuis les sources n'est prévue que sous Linux")
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"Construction de Tesseract déjà en cours dans un autre processus (verrou {_display(path)}) ; "
                               "aucune attente : relancer le provisionnement après sa fin") from None
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _prepare_build_root(build_root: Path) -> None:
    """Arborescence de construction recréée à chaque compilation, seulement si le projet l'a créée."""
    if build_root.exists():
        if not (build_root / BUILD_MARKER).is_file():
            raise ValueError(f"{_display(build_root)} existe sans le marqueur {BUILD_MARKER} : conservé, aucun effacement")
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)
    (build_root / BUILD_MARKER).write_text("Construction de Tesseract par services.runtime.provisioning ; "
                                           "recréée à chaque compilation.\n", encoding="utf-8")


def _extract_source(archive: Path, destination: Path, top: str) -> Path:
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        outside = [member.name for member in members if member.name.split("/", 1)[0] != top]
        if outside:
            raise ValueError(f"{archive.name} : entrées hors de {top}/ ({outside[0]})")
        bundle.extractall(destination, members=members, filter="data")
    return destination / top


def source_content_sha256(directory: Path, top: str) -> str:
    """Empreinte du contenu extrait de `directory/top`, indépendante de la compression de l'archive.

    SHA-256 du listing que produit, dans `directory`, `find <top> -type f -print0 | LC_ALL=C sort -z | xargs -0
    sha256sum` : une ligne `<SHA-256 du fichier>  <chemin relatif>` par fichier ordinaire, triée par chemin (octets
    UTF-8). Seuls des fichiers ordinaires et des dossiers sont admis.
    """
    lines: list[tuple[bytes, bytes]] = []
    for path in (directory / top).rglob("*"):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"{relative} : seul un fichier ordinaire ou un dossier est admis (lien ou fichier spécial)")
        if "\n" in relative or "\\" in relative:
            raise ValueError(f"{relative!r} : nom de fichier non admis dans l'empreinte de contenu")
        if path.is_file():
            lines.append((relative.encode(), f"{file_hash(path)}  {relative}\n".encode()))
    digest = hashlib.sha256()
    for _, line in sorted(lines):
        digest.update(line)
    return digest.hexdigest()


def _fetch_served_archive(entry: dict[str, Any], destination: Path) -> None:
    """Un téléchargement de l'URL du verrou, sans contrôle d'empreinte d'archive ; le contenu est vérifié ensuite."""
    limit = 4 * int(entry.get("size") or 16 * 1024**2)
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "agentragpdf-provision/0.1"})
    copied = 0
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            copied += len(block)
            if copied > limit:
                raise ValueError(f"{destination.name} : archive servie de plus de {limit} octets, refusée")
            output.write(block)
        output.flush()
        os.fsync(output.fileno())


def _source_archive(entry: dict[str, Any], *, offline: bool) -> tuple[Path, dict[str, Any]]:
    """Archive à extraire et sa provenance.

    Empreinte d'archive conforme au verrou : cas nominal, par `artifacts.download`. Une entrée qui porte aussi
    `content_sha256` (archive de tag générée par GitHub, sans garantie de stabilité octet par octet) admet une
    archive d'empreinte différente, en cache ou servie à la même URL, dont le contenu extrait est vérifié ensuite.
    Une archive en cache d'empreinte différente est vérifiée par son contenu, y compris en ligne, et jamais
    remplacée implicitement : un contenu non conforme arrête la construction et l'archive reste pour diagnostic.

    En ligne, un échec ne laisse aucun fichier partiel : le `.part` de `download` ou du téléchargement vérifié par
    contenu (archive tronquée, trop volumineuse, transfert interrompu) est retiré avant de rendre l'erreur.
    """
    target = ROOT / entry["target"]
    tolerant = bool(entry.get("content_sha256"))
    if tolerant and target.is_file() and file_hash(target) != entry["sha256"]:
        return target, {"archive_sha256": file_hash(target), "archive_matches_lock": False, "origin": "cache"}
    cached = target.is_file()
    part = target.with_name(target.name + ".part")
    try:
        try:
            download(entry, target, offline=offline)
        except ValueError:
            # En ligne, après les essais de `download` : l'archive servie diffère du verrou. Même fichier partiel
            # que `download`, remplacé par ce téléchargement puis retiré ou publié selon le contenu.
            if offline or not tolerant:
                raise
            _fetch_served_archive(entry, part)
            return part, {"archive_sha256": file_hash(part), "archive_matches_lock": False, "origin": "download"}
    except BaseException:
        if not offline:
            part.unlink(missing_ok=True)
        raise
    return target, {"archive_sha256": entry["sha256"], "archive_matches_lock": True, "origin": "cache" if cached else "download"}


def _extract_verified_sources(sources: dict[str, dict[str, Any]], archives: dict[str, tuple[Path, dict[str, Any]]],
                              destination: Path) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    """Extraction puis contrôle de l'empreinte de contenu ; une archive servie conforme rejoint le cache."""
    source_dirs: dict[str, Path] = {}
    records: list[dict[str, Any]] = []
    for name, entry in sources.items():
        archive, provenance = archives[name]
        target = ROOT / entry["target"]
        top = f"{name}-{entry['version']}"
        expected = entry.get("content_sha256")
        try:
            source_dirs[name] = _extract_source(archive, destination, top)
            content = source_content_sha256(destination, top)
            if expected and content != expected:
                raise ValueError(f"contenu extrait de {target.name} différent du verrou ({content}, attendu {expected}) ; "
                                 + ("archive téléchargée retirée" if archive != target else
                                    f"archive conservée pour diagnostic : la déplacer hors de {_display(target.parent)}"))
        except BaseException:
            if archive != target:
                archive.unlink(missing_ok=True)
            raise
        if archive != target:
            os.replace(archive, target)
        records.append({"name": name, "archive": entry["target"], "archive_sha256": provenance["archive_sha256"],
                        "lock_archive_sha256": entry["sha256"], "archive_matches_lock": provenance["archive_matches_lock"],
                        "content_sha256": content, "lock_content_sha256": expected,
                        "content_matches_lock": (content == expected) if expected else None,
                        "origin": provenance["origin"]})
        if not provenance["archive_matches_lock"]:
            print(f"{target.name} : empreinte d'archive différente du verrou, contenu extrait conforme "
                  f"(archive {provenance['archive_sha256']}, verrou {entry['sha256']}) ; consigné au manifeste", flush=True)
    return source_dirs, records


def _run_logged(name: str, command: list[str], log_dir: Path, env: dict[str, str], cwd: Path) -> Path:
    log = log_dir / f"{name}.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env=env, cwd=cwd, check=False)
    if result.returncode:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-15:])
        raise RuntimeError(f"Échec de l'étape {name} (code {result.returncode}) ; journal : {_display(log)}\n{tail}")
    return log


def compile_sources(source_dirs: dict[str, Path], build_root: Path, prefix: Path, tools: dict[str, str | None],
                    jobs: int, log_dir: Path) -> dict[str, Any]:
    """Configure, compile et installe Leptonica puis Tesseract dans `prefix` ; journaux sous `log_dir`."""
    env = {**_tool_environment(tools), "HOME": str(build_root / "home"), "TMPDIR": str(build_root / "tmp"),
           "CC": str(tools["cc"]), "CXX": str(tools["c++"])}
    for directory in (build_root / "home", build_root / "tmp"):
        directory.mkdir(parents=True, exist_ok=True)
    builder, generator = _builder(tools)
    cmake = str(tools["cmake"])
    builds = {name: build_root / f"{name}-build" for name in ("leptonica", "tesseract")}
    common = [f"-DCMAKE_MAKE_PROGRAM={builder}", f"-DCMAKE_INSTALL_PREFIX={prefix}"]
    extra = {"leptonica": common, "tesseract": [*common, f"-DLeptonica_DIR={prefix / 'lib/cmake/leptonica'}"]}
    options = {name: _expanded_options(values, build_root) for name, values in _cmake_options().items()}
    steps: list[dict[str, Any]] = []
    summary: dict[str, list[str]] = {}
    for name in ("leptonica", "tesseract"):
        print(f"Compilation de {name} ({jobs} tâches) ; journaux : {_display(log_dir)}", flush=True)
        commands = [
            ("configure", [cmake, "-S", str(source_dirs[name]), "-B", str(builds[name]), "-G", generator,
                           *extra[name], *options[name]]),
            ("build", [cmake, "--build", str(builds[name]), "--parallel", str(jobs)]),
            ("install", [cmake, "--install", str(builds[name])]),
        ]
        for stage, command in commands:
            log = _run_logged(f"{name}-{stage}", command, log_dir, env, build_root)
            steps.append({"step": f"{name}-{stage}", "command": command, "log": _display(log)})
            if stage == "configure":
                text = log.read_text(encoding="utf-8", errors="replace")
                unused = unused_cmake_variables(text)
                if unused:
                    raise RuntimeError(f"Options CMake inconnues de {name} : {', '.join(unused)} ; journal : {_display(log)}")
                summary[name] = [line[3:].strip() for line in text.splitlines()
                                 if re.match(r"-- (Used \w+ library|Found leptonica version|HAVE_\w+:)", line)]
    return {"generator": generator, "steps": steps, "configure_summary": summary,
            "environment": {key: env[key] for key in sorted(env)}}


def toolchain_versions(tools: dict[str, str | None]) -> dict[str, Any]:
    env = _tool_environment(tools)
    record: dict[str, Any] = {"cmake": {"path": tools["cmake"], "version": _first_line([str(tools["cmake"]), "--version"], env)}}
    for key in ("cc", "c++"):
        tool = str(tools[key])
        record[key] = {"path": tool, "resolved": os.path.realpath(tool), "version": _first_line([tool, "--version"], env)}
    builder, _ = _builder(tools)
    record["build_tool"] = {"path": builder, "version": _first_line([str(builder), "--version"], env)}
    record["glibc"] = " ".join(platform.libc_ver())
    return record


def _install(built: Path, source_dirs: dict[str, Path], target: Path) -> list[dict[str, Any]]:
    """Binaire et licences publiés ensemble par renommage d'un dossier préparé à côté de la destination.

    En cas d'échec avant le renommage, le dossier de préparation de cet appel est retiré : rien n'est publié.
    """
    staging = target.parent.with_name(f"{target.parent.name}.tmp-{uuid.uuid4().hex}")
    staging.mkdir(parents=True)
    try:
        shutil.copy2(built, staging / target.name)
        for name, filename in _LICENSE_FILES.items():
            shutil.copy2(source_dirs[name] / filename, staging / filename)
        os.replace(staging, target.parent)
    except BaseException as exc:
        try:
            shutil.rmtree(staging)
        except OSError as cleanup:
            exc.add_note(f"Dossier de préparation {_display(staging)} non retiré : {cleanup}")
        raise
    return [{"path": _display(path), "sha256": file_hash(path), "size": path.stat().st_size}
            for path in sorted(target.parent.iterdir())]


def build_tesseract(profile: dict, *, offline: bool = False, jobs: int | None = None) -> dict[str, Any]:
    """Compile Leptonica et Tesseract 5.4.0 depuis les sources verrouillées, ou revérifie la construction installée."""
    configured = native_executable(profile["pdf"]["tesseract_cmd"])
    if "/" not in configured and "\\" not in configured:
        raise ValueError(f"Le profil désigne « {configured} » dans le PATH ; seul un exécutable du projet est provisionné")
    sources = locked_tesseract_sources()
    target = ROOT / configured
    manifest_path = ROOT / BUILT_MANIFEST

    def installed_state() -> str:
        if target.is_file() and manifest_path.is_file():
            return "installed"
        return "incomplete" if target.exists() or manifest_path.exists() or target.parent.exists() else "absent"

    # Prérequis nommés avant toute écriture, dès qu'une construction sera nécessaire.
    tools: dict[str, str | None] | None = None
    if installed_state() == "absent":
        tools = build_tools()
        missing = missing_build_prerequisites(tools)
        if missing:
            raise MissingBuildPrerequisites(missing)
    with _build_lock(ROOT / BUILD_LOCK):
        # État relu sous le verrou : une construction concurrente a pu s'achever entre-temps.
        state = installed_state()
        if state == "installed":
            return verify_built_copy(target, manifest_path, sources)
        if state == "incomplete":
            raise ValueError(f"Installation Tesseract incomplète : {_display(target.parent)} ou {_display(manifest_path)} "
                             "existe sans construction vérifiable ; fichiers conservés pour diagnostic, aucun remplacement "
                             f"implicite. Pour reconstruire, déplacer {_display(target.parent)} et {_display(manifest_path)} "
                             "(s'il existe) hors de .runtime/bin et .runtime/manifests, puis relancer le provisionnement")
        if tools is None:
            tools = build_tools()
            missing = missing_build_prerequisites(tools)
            if missing:
                raise MissingBuildPrerequisites(missing)
        archives: dict[str, tuple[Path, dict[str, Any]]] = {}
        build_root = ROOT / BUILD_DIR
        try:
            for name, entry in sources.items():
                archives[name] = _source_archive(entry, offline=offline)
            existing = next(parent for parent in (build_root, *build_root.parents) if parent.exists())
            if shutil.disk_usage(existing).free < 2 * 1024**3:
                raise RuntimeError(f"Espace disque insuffisant sous {_display(existing)} pour compiler Tesseract, réserve 2 Gio")
            _prepare_build_root(build_root)
            source_dirs, archive_records = _extract_verified_sources(sources, archives, build_root / "src")
        except BaseException:
            # Archive servie (`.part`) pas encore vérifiée par son contenu ni publiée dans le cache : retirée.
            for name, (archive, _) in archives.items():
                if archive != ROOT / sources[name]["target"]:
                    archive.unlink(missing_ok=True)
            raise
        started_at = datetime.now(UTC)
        log_dir = ROOT / BUILD_LOGS / f"tesseract-{TESSERACT_VERSION}-{started_at:%Y%m%dT%H%M%SZ}"
        jobs = jobs or min(4, os.cpu_count() or 1)
        prefix = build_root / "prefix"
        started = time.monotonic()
        compilation = compile_sources(source_dirs, build_root, prefix, tools, jobs, log_dir)
        duration = round(time.monotonic() - started, 1)
        built = prefix / "bin" / "tesseract"
        check = verify_binary(built, sources["leptonica"]["version"], tools, (ROOT, build_root), build_root)
        files = _install(built, source_dirs, target)
        manifest = {
            "schema_version": 2, "kind": BUILD_KIND, "platform": platform_id(), "host": platform.platform(),
            "cpu_count": os.cpu_count(), "started_at_utc": started_at.isoformat(timespec="seconds"),
            "built_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "duration_seconds": duration, "jobs": jobs,
            "offline": offline, "sources": _source_records(sources), "source_archives": archive_records,
            "cmake_options": _cmake_options(),
            "file_prefix_map": {"token": BUILD_ROOT_TOKEN, "flags": file_prefix_map_flags(build_root)},
            "cmake_paths": {"install_prefix": _display(prefix), "leptonica_dir": _display(prefix / "lib/cmake/leptonica"),
                            "build_root": _display(build_root)},
            "toolchain": toolchain_versions(tools), "generator": compilation["generator"],
            "build_environment": compilation.get("environment"), "steps": compilation["steps"],
            "configure_summary": compilation["configure_summary"],
            "binary": {"path": _display(target), "sha256": file_hash(target), "size": target.stat().st_size},
            "files": files, "version_output": check["version_output"], "ldd": check["ldd"],
            "dynamic_dependencies": check["dynamic_dependencies"], "rpath": check["rpath"],
            "absolute_build_paths": check["absolute_build_paths"],
        }
        write_json_atomic(manifest_path, manifest)
    return {"status": "built_from_source", "version": check["version"], "binary": _display(target),
            "manifest": _display(manifest_path), "duration_seconds": duration}
