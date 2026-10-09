"""Kit hors ligne Linux (R26-KIT-01, W018) : sélection, fabrication, intégrité et archive de transport.

Format `atelier-kit-v2`. Les fichiers suivis par Git (code, configuration, documentation, lanceurs) sont lus dans le
commit courant : le kit correspond exactement à ce commit, et les modifications locales sont listées sans être livrées.
Les artefacts non suivis (`.runtime` sélectionné, interface construite) viennent de l'arbre de travail. Les liens
symboliques relatifs internes sont conservés (fichier `SYMLINKS`) ; un lien absolu ou sortant arrête la fabrication, sauf
le lien de version mineure de CPython, que rien n'utilise (le `.venv` désigne le dossier de la version complète).

Aucun chemin du poste de fabrication ne doit atteindre le kit : chaque octet copié est comparé aux marqueurs du poste
(racine, cibles réelles de `.runtime`, `.venv` et `node_modules`, HOME). Deux neutralisations seulement sont admises
et déclarées dans le manifeste : des champs descriptifs du manifeste de construction de Tesseract, que la vérification
de la construction ne lit pas, et le préfixe de CPython dans `_sysconfigdata_*.py`, remplacé par un jeton que
l'installateur réécrit vers le préfixe réel (uv fait de même à l'installation d'un Python géré).

Bibliothèque standard seule au chargement : `linux_install.py` importe ce module avec le CPython du kit. PyYAML n'est
importé que par la fabrication, exécutée avec l'environnement du dépôt.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import platform as host
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any
from urllib.parse import urlsplit

from tools.dist.build_kit import FORBIDDEN_PREFIXES, ROOT, stream_hash

KIT_FORMAT = "atelier-kit-v2"
CHUNK = 1024 * 1024
GIB = 1024**3
LINUX_PLATFORMS: dict[str, dict[str, Any]] = {"linux-aarch64": {"machine": "aarch64", "e_machine": 183}, "linux-x86_64": {"machine": "x86_64", "e_machine": 62}}
# Fichiers suivis par Git, lus dans le commit courant. tools/dist sans les scripts PowerShell.
TRACKED = ("services", "config", "docs", "tools/corpus", "tools/dist", "packages/contracts", "rag.sh", "bootstrap.sh", "pyproject.toml",
           "uv.lock", "README.md", "CHANGELOG.md", "apps/web/package.json", "apps/web/pnpm-lock.yaml")
# Artefacts non suivis, lus dans l'arbre de travail ; `{python}` est la clé du CPython géré (bootstrap.sh).
ARTIFACTS = ("apps/web/out", ".runtime/bin", ".runtime/models", ".runtime/python/{python}", ".runtime/bootstrap", ".runtime/cache/uv",
             ".runtime/manifests", ".runtime/model-metadata")
EXCLUDED = ("*/__pycache__/*", "*.pyc", "*/.git/*", "*/node_modules/*", ".runtime/models/granite-*", ".runtime/models/granite-*/*",
            ".runtime/manifests/ollama-discovery.json", ".runtime/cache/uv/interpreter-v4/*", "tools/dist/*.ps1")
# Données d'exécution et de chantier : refusées partout, même sous un dossier de la liste blanche.
LINUX_FORBIDDEN_PREFIXES = tuple(dict.fromkeys(FORBIDDEN_PREFIXES + (
    ".runtime/build/", ".runtime/cache/downloads/", ".runtime/control/", ".runtime/profiles/", ".runtime/cpu-pilot/",
    ".runtime/provision-service/", ".runtime/data/", ".runtime/qa/", ".runtime/evals/", ".runtime/q/", ".runtime/backups/")))
LINUX_NESTED_FORBIDDEN = tuple("/" + prefix for prefix in LINUX_FORBIDDEN_PREFIXES if prefix.startswith(".runtime/"))
# Noms de fichiers refusés partout : journaux, bases, clés et jetons.
FORBIDDEN_NAMES = ("*.log", "*.sqlite3", "*.sqlite3-*", "*.sqlite", "*.db", "*.jsonl", "id_ed25519*", "id_rsa*", "*.pem", "*.key",
                   "*.p12", "*.pfx", ".env", ".netrc", ".npmrc", "*history", "admin-token", "qdrant-api-key")
FORBIDDEN_COMPONENTS = ("secrets",)
# Seule exception constatée sur le poste de référence : le magasin public d'autorités de certification de certifi (roue du
# cache uv et pip vendu par CPython).
ALLOWED_PATHS = ("*/certifi/cacert.pem",)
# Bibliothèques GPU d'Ollama (sous-dossiers de lib/ollama) : seules celles de la variante choisie sont livrées.
# jetpack5 : complément officiel JetPack 5 (Jetson Linux R35) ; cuda_v12/cuda_v13 (CUDA 12.8/13.0) sont inutilisables
# sous R35 et aucune voie « generic » n'est qualifiée (W025).
GPU_VARIANTS = {"none": (), "jetpack5": ("cuda_jetpack5",)}
MODEL_PROFILES = {"2b": "config/local16.yaml", "4b": "config/local16-4b.yaml"}
# W045 : le 4B, modèle par défaut, fait partie de tout kit ; le 2B est livré par défaut pour garder le choix au lancement.
# L'ordre de MODEL_PROFILES reste celui du kit_id et des enregistrements de modèles (…-2b4b).
DEFAULT_MODEL = "4b"
DEFAULT_MODELS = ("4b", "2b")
DEFAULT_MODEL_REFUSAL = ("Kit sans le modèle par défaut qwen3.5:4b refusé (W045) : --models 4b,2b (défaut, les deux modèles au "
                         "choix du lancement) ou --models 4b. Un kit 2B seul n'est pas fabriqué.")
MODELS_LOCK = "config/models.lock.json"
# Interface livrée : prise dans l'arbre de travail (apps/web/out), elle doit avoir été construite depuis le commit du kit.
# Le build du frontend écrit cette preuve (commit, sources apps/web modifiées, empreinte de pnpm-lock.yaml) ; le
# fabricant la compare au commit livré (KIT4-26).
WEB_PROVENANCE = "apps/web/out/build-provenance.json"
WEB_PROVENANCE_FORMAT = "atelier-web-provenance-v1"
WEB_LOCK = "apps/web/pnpm-lock.yaml"
WEB_REBUILD = "reconstruire l'interface depuis le commit du kit (pnpm build dans apps/web)"
TESSERACT_BUILT = ".runtime/manifests/tesseract-built.json"
# Fichiers du commit sans lesquels le kit ne s'installe pas (installateur, intégrité, lanceurs, verrous).
# Le guide (kit_guide.py et son modèle) et l'icône du menu (ICON_SOURCE de linux_install.py, publiée par l'installateur)
# en font partie : required_for_build() complète cette liste.
REQUIRED_FOR_BUILD = ("tools/dist/install.sh", "tools/dist/linux_install.py", "tools/dist/linux_kit.py", "tools/dist/linux_profiles.py",
                      "tools/dist/build_kit.py", "tools/dist/notices.py", "tools/dist/kit_guide.py", "tools/dist/templates/LISEZMOI-linux.md",
                      "services/runtime/profile_schema.py", "config/artifacts.lock.json", "rag.sh", "bootstrap.sh",
                      "packages/contracts/contracts.json")
TESSERACT_BINARY = ".runtime/bin/tesseract-5.4.0/tesseract"
# Contrôles ldd du poste cible, avant toute copie : Tesseract (construit sur le poste, lié aux bibliothèques d'Ubuntu), le
# module d'OpenCV (roue opencv-python, tirée par rapidocr), lié à libGL, X11 et GLib du système, et les ELF qui portent
# les versions maximales de glibc et de libstdc++ requises (trois au plus par maximum).
CV2_MODULE = r"\.runtime/cache/uv/archive-v0/[^/]+/cv2/cv2\.abi3\.so"
CARRIERS_PER_MAXIMUM = 3
# Bibliothèque dont tous les utilisateurs sont listés ici : facultative (signalée, non bloquante à l'installation).
OPTIONAL_USERS = {r".*/lib-dynload/_crypt\.cpython-[^/]+\.so": "module _crypt de CPython (crypt, déprécié) : importé par aucun code de "
                                                                 "l'atelier ni des paquets installés (relevé du 06/10/2026)"}
# Composant fonctionnel d'une bibliothèque du système, déduit des ELF qui la requièrent (KIT4-06) : nommé dans le refus de
# l'installateur et dans le guide. Les bibliothèques de l'environnement C et C++ gardent un libellé commun.
COMPONENT_USERS = ((re.compile(r"^\.runtime/bin/tesseract-[^/]+/"), "OCR Tesseract"),
                   (re.compile(r"^site-packages/(?:cv2|opencv_python\.libs)/"), "OpenCV (OCR et tableaux)"),
                   (re.compile(r"^\.runtime/bin/ollama-[^/]+/lib/ollama/cuda_jetpack5/"), "GPU Jetson"))
C_RUNTIME = re.compile(r"^(?:ld-linux[^/]*|lib(?:c|m|dl|rt|util|pthread|resolv|crypt|stdc\+\+|gcc_s)\.so\.\d+)$")
C_RUNTIME_LABEL = "bibliothèque C/C++"
ARCHIVE_ENTRY = re.compile(r"^\.runtime/cache/uv/archive-v0/[^/]+/(.+)$")
OLLAMA_LIBRARIES = re.compile(r"^(\.runtime/bin/ollama-[^/]+/lib/ollama)/[^/]+/[^/]+$")
PYTHON_PREFIX_TOKEN = "@ATELIER_PYTHON_PREFIX@"
HOST_TOKEN = "<poste de fabrication>"
INSTALLER = "installer.sh"
NOTICES = "THIRD_PARTY_NOTICES.md"
SUMS, LINKS, EXECUTABLES, MANIFEST = "SHA256SUMS", "SYMLINKS", "EXECUTABLES", "kit-manifest.json"
# Guide du kit (KIT4-16), à la racine du kit et à côté de l'archive sous le nom `<kit_id>.LISEZMOI.md`.
GUIDE = "LISEZMOI.md"
GUIDE_TEMPLATE = "tools/dist/templates/LISEZMOI-linux.md"
# Noyau 5.3 : pidfd (supervision POSIX, linux-rag-runtime).
KERNEL_MIN = "5.3"
# Système du poste de référence, où la pile tourne et où le kit se fabrique : ce n'est pas une installation qualifiée.
REFERENCE_OS = "Ubuntu 20.04.6 LTS aarch64 (Jetson Linux R35.4.1, Jetson AGX Orin)"
# Installation d'un kit qualifiée par une recette réelle, par plateforme : référence de la preuve datée. Vide tant que la
# recette R26-KIT-02 n'est pas exécutée ; le manifeste porte alors `installation_qualified: false`.
QUALIFIED_INSTALLATIONS: dict[str, str] = {}
# Outils du poste cible : extraction de l'archive (guide), installer.sh, bootstrap.sh --offline, rag.sh, installateur et
# supervision. Le projet amont est indiqué, jamais un paquet : il dépend de la distribution du poste. Un outil que l'installateur
# ne prend que dans des dossiers fixes du système, jamais dans le PATH, les nomme dans son usage (« dans /usr/bin ou /bin »).
TARGET_TOOLS = (
    {"name": "sha256sum", "project": "GNU coreutils", "used_for": "vérification de l'archive, puis de l'interpréteur et de "
                                                                  "l'installateur du kit avant leur exécution (installer.sh le "
                                                                  "prend dans /usr/bin ou /bin)"},
    {"name": "tar", "project": "GNU tar", "used_for": "extraction de l'archive de transport"},
    {"name": "uname", "project": "GNU coreutils", "used_for": "système et architecture du poste (installer.sh, bootstrap.sh)"},
    {"name": "dirname", "project": "GNU coreutils", "used_for": "dossier des scripts (installer.sh, bootstrap.sh, rag.sh)"},
    {"name": "id", "project": "GNU coreutils", "used_for": "refus d'une exécution en root par installer.sh"},
    {"name": "cat", "project": "GNU coreutils", "used_for": "aide de rag.sh et de bootstrap.sh"},
    {"name": "sed", "project": "GNU sed ou sed POSIX", "used_for": "lecture du manifeste et de la version de la glibc"},
    {"name": "awk", "project": "awk POSIX, mawk ou GNU awk", "used_for": "sélection des empreintes vérifiées par installer.sh"},
    {"name": "find", "project": "GNU findutils ou find POSIX", "used_for": "entrées du dossier de l'interpréteur du kit comparées à "
                                                                         "SHA256SUMS et SYMLINKS par installer.sh avant le "
                                                                         "lancement de Python, dans /usr/bin ou /bin"},
    {"name": "grep", "project": "GNU grep ou grep POSIX", "used_for": "contrôles d'installer.sh et de bootstrap.sh"},
    {"name": "getconf", "project": "GNU C Library", "used_for": "version de la glibc"},
    {"name": "ldd", "project": "GNU C Library", "used_for": "version de la glibc à défaut de getconf ; bibliothèques de Tesseract, "
                                                            "d'OpenCV et des ELF les plus exigeants, contrôlées par l'installateur "
                                                            "avec le ldd pris dans /usr/bin ou /bin"},
    {"name": "ldconfig", "project": "GNU C Library", "used_for": "bibliothèques connues du chargeur (ldconfig -p, lecture seule), "
                                                                 "dans /sbin, /usr/sbin, /usr/bin ou /bin"},
    {"name": "setpriv", "project": "util-linux", "used_for": "arrêt des processus de l'atelier avec leur superviseur, dans /usr/bin "
                                                            "ou /bin"},
)
INSTALL_MARGIN = 3 * GIB
MEMORY_MIN_GIB = 15


class KitError(ValueError):
    """Refus de fabrication, de vérification ou de copie, avec la correction attendue."""


# --- Outils communs ---------------------------------------------------------------------------------------------------

def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def normalized_link(relative: str, target: str) -> str | None:
    """Chemin, relatif à la racine du kit, que désigne un lien relatif ; None s'il est absolu ou sort du kit."""
    if not target or target.startswith("/"):
        return None
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(relative), target))
    return None if resolved == ".." or resolved.startswith("../") or resolved.startswith("/") else resolved


def check_name(relative: str) -> None:
    if "\n" in relative or "\t" in relative or "\r" in relative or relative.startswith("/") or ".." in relative.split("/"):
        raise KitError(f"Nom de fichier inutilisable dans un kit : {relative!r}")


def forbidden(relative: str) -> str | None:
    """Motif qui interdit ce chemin, ou None."""
    if relative.startswith(LINUX_FORBIDDEN_PREFIXES) or any(part in relative for part in LINUX_NESTED_FORBIDDEN):
        return "données d'exécution ou de chantier"
    name = relative.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatch(relative, pattern) for pattern in ALLOWED_PATHS):
        return None
    for pattern in FORBIDDEN_NAMES:
        if fnmatch.fnmatch(name, pattern):
            return pattern
    if any(component in FORBIDDEN_COMPONENTS for component in relative.split("/")):
        return "secrets"
    return None


def scan_markers(chunks: Iterable[bytes], markers: list[bytes]) -> set[bytes]:
    """Marqueurs présents dans un flux, y compris à cheval sur deux blocs."""
    found: set[bytes] = set()
    keep = max((len(marker) for marker in markers), default=1) - 1
    tail = b""
    for block in chunks:
        window = tail + block
        found.update(marker for marker in markers if marker in window)
        tail = window[-keep:] if keep else b""
    return found


def read_blocks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as reader:
        yield from iter(lambda: reader.read(CHUNK), b"")


def write_atomic(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Fichier temporaire du même dossier, fsync puis rename(2) : jamais de fichier à moitié écrit."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as writer:
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


# --- Poste de fabrication -----------------------------------------------------------------------------------------------

def host_platform() -> str:
    from services.runtime.platforms import platform_id

    return platform_id()


def os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in {"NAME", "VERSION", "VERSION_ID", "ID", "PRETTY_NAME"}:
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def l4t_release(path: Path = Path("/etc/nv_tegra_release")) -> dict[str, Any] | None:
    """Version de Jetson Linux, lue comme Ollama (` R(\\d+) `, discover/gpu.go) ; None hors Jetson."""
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return None
    major = re.search(r" R(\d+) ", line)
    revision = re.search(r"REVISION: ([0-9.]+)", line)
    return {"major": int(major.group(1)) if major else None, "revision": revision.group(1) if revision else None, "line": line.strip()}


def host_glibc() -> str | None:
    if sys.platform == "win32":
        return None
    try:
        value = os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, ValueError, OSError):
        return None
    return value.split()[-1] if value else None


def build_os_label() -> str:
    """Système du poste de fabrication, tel que /etc/os-release le nomme, et son architecture."""
    release = os_release()
    return f"{release.get('PRETTY_NAME') or release.get('NAME') or 'Linux'} {host.machine()}".strip()


_LDCONFIG: dict[str, str] | None = None


def host_library_path(soname: str) -> str | None:
    """Chemin d'une bibliothèque connue du chargeur du poste de fabrication (`ldconfig -p`, lecture seule)."""
    global _LDCONFIG
    if _LDCONFIG is None:
        from tools.dist.linux_install import ldconfig_cache

        _LDCONFIG = ldconfig_cache()
    return _LDCONFIG.get(soname)


def package_owner(path: str) -> str | None:
    """Paquet Debian qui possède un fichier (`dpkg-query -S`, lecture seule) ; None sans dpkg-query ou sans propriétaire."""
    dpkg_query = shutil.which("dpkg-query", path="/usr/bin:/bin")
    if not dpkg_query:
        return None
    completed = subprocess.run([dpkg_query, "-S", path], capture_output=True, text=True, errors="replace", check=False, timeout=60,
                               env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    first = completed.stdout.splitlines()[0] if completed.returncode == 0 and completed.stdout.strip() else ""
    owner = first.split(": ", 1)[0].split(",")[0].strip() if ": " in first else ""
    return owner.split(":", 1)[0] or None


def component_of(soname: str, users: set[str]) -> str:
    if C_RUNTIME.match(soname):
        return C_RUNTIME_LABEL
    labels = [label for pattern, label in COMPONENT_USERS if any(pattern.match(user) for user in users)]
    return ", ".join(labels) or f"autre composant du kit ({sorted(users)[0] if users else 'inconnu'})"


def system_packages(names: Iterable[str], users: dict[str, set[str]]) -> dict[str, dict[str, Any]]:
    """Paquet du poste de fabrication qui fournit chaque bibliothèque attendue du système : chemin donné par le chargeur,
    puis son chemin réel, demandés à dpkg-query. Une bibliothèque absente du chargeur ou sans paquet reste sans paquet."""
    observed = build_os_label()
    packages: dict[str, dict[str, Any]] = {}
    for name in sorted(names):
        path = host_library_path(name)
        owner = None
        if path:
            for candidate in dict.fromkeys((os.path.realpath(path), path)):
                owner = package_owner(candidate)
                if owner:
                    break
        packages[name] = {"package": owner, "component": component_of(name, users.get(name, set())), "observed_on": observed}
    return packages


def build_host() -> dict[str, Any]:
    return {"os_release": os_release(), "kernel": host.release(), "machine": host.machine(), "glibc": host_glibc(),
            "l4t": l4t_release()}


def host_markers(root: Path, home: str | None) -> list[str]:
    """Chemins du poste de fabrication : racine du dépôt, cibles réelles de `.runtime`, `.venv`, `node_modules`, HOME."""
    candidates = {str(root), os.path.realpath(root)}
    for relative in (".runtime", ".venv", "apps/web/node_modules"):
        path = root / relative
        if path.exists() or path.is_symlink():
            candidates.add(os.path.realpath(path))
    if home:
        candidates |= {home.rstrip("/"), os.path.realpath(home)}
    return sorted(marker for marker in candidates if len(marker) > 4 and marker != "/")


# --- Analyse ELF -----------------------------------------------------------------------------------------------------

def elf_machine(head: bytes) -> int | None:
    """e_machine d'un en-tête ELF (20 premiers octets), None si ce n'est pas un ELF."""
    if len(head) < 20 or head[:4] != b"\x7fELF":
        return None
    return int.from_bytes(head[18:20], "little" if head[5] == 1 else "big")


@dataclass
class ElfInfo:
    glibc: set[str] = field(default_factory=set)
    glibcxx: set[str] = field(default_factory=set)
    needs: dict[str, set[str]] = field(default_factory=dict)
    needed: set[str] = field(default_factory=set)
    soname: str | None = None
    runpath: list[str] = field(default_factory=list)


def parse_readelf(text: str, files: list[str]) -> dict[str, ElfInfo]:
    """Sortie de `readelf -V -d -W` : versions requises (section .gnu.version_r seulement), NEEDED et SONAME.

    Plusieurs fichiers : readelf les sépare par une ligne « File: <chemin> » en début de ligne ; un seul fichier n'en a pas.
    """
    result: dict[str, ElfInfo] = {}
    current = result.setdefault(files[0], ElfInfo()) if len(files) == 1 else None
    in_needs = False
    library = ""
    for line in text.splitlines():
        header = re.match(r"^File: (.+)$", line)
        if header:
            current = result.setdefault(header.group(1), ElfInfo())
            in_needs = False
            continue
        if current is None:
            continue
        if line.startswith("Version needs section"):
            in_needs = True
            continue
        if line.startswith(("Version definition section", "Version symbols section", "Dynamic section", "There is no dynamic")):
            in_needs = False
        dynamic = re.search(r"\((NEEDED|SONAME|RUNPATH|RPATH)\)\s+(?:Shared library|Library soname|Library runpath|Library rpath): "
                            r"\[(.+)\]", line)
        if dynamic:
            if dynamic.group(1) == "NEEDED":
                current.needed.add(dynamic.group(2))
            elif dynamic.group(1) == "SONAME":
                current.soname = dynamic.group(2)
            else:
                current.runpath += [item for item in dynamic.group(2).split(":") if item]
            continue
        if not in_needs:
            continue
        owner = re.search(r"Version: \d+\s+File: (\S+)\s+Cnt:", line)
        if owner:
            library = owner.group(1)
            continue
        name = re.search(r"Name: (\S+)\s+Flags:", line)
        if name:
            current.needs.setdefault(library, set()).add(name.group(1))
            if re.fullmatch(r"GLIBC_\d+(\.\d+)+", name.group(1)):
                current.glibc.add(name.group(1).removeprefix("GLIBC_"))
            elif re.fullmatch(r"GLIBCXX_\d+(\.\d+)+", name.group(1)):
                current.glibcxx.add(name.group(1).removeprefix("GLIBCXX_"))
    return result


def readelf_batches(paths: list[Path], batch: int = 200) -> dict[str, ElfInfo]:
    readelf = shutil.which("readelf")
    if not readelf:
        raise KitError("readelf (binutils) introuvable : nécessaire pour établir la glibc minimale du kit")
    infos: dict[str, ElfInfo] = {}
    for start in range(0, len(paths), batch):
        group = [str(path) for path in paths[start:start + batch]]
        completed = subprocess.run([readelf, "-V", "-d", "-W", *group], capture_output=True, text=True, errors="replace",
                                   env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"}, check=False)
        infos.update(parse_readelf(completed.stdout, group))
    return infos


def kit_path(value: str, folder: str) -> str | None:
    """Chemin du kit désigné par une entrée RUNPATH/RPATH ou un NEEDED à barre oblique ($ORIGIN = dossier de l'ELF)."""
    expanded = value.replace("${ORIGIN}", folder).replace("$ORIGIN", folder)
    if expanded.startswith("/"):
        return None
    normalized = posixpath.normpath(expanded)
    return None if normalized == ".." or normalized.startswith("../") else normalized


def system_requirements(infos: dict[str, ElfInfo], locate: dict[str, str], present: set[str]) -> dict[str, Any]:
    """glibc et libstdc++ minimales et bibliothèques que les ELF livrés attendent du système.

    Une bibliothèque est fournie par le kit si le chargeur la trouve depuis l'ELF : NEEDED à chemin ($ORIGIN), dossiers
    RUNPATH/RPATH relatifs au kit, dossier de l'ELF, ou `lib/ollama` pour les bibliothèques d'Ollama. Un nom présent
    ailleurs dans le kit ne compte pas : le chargeur ne l'y cherche pas (ld.so(8)). Les roues du cache uv sont vues
    comme installées ensemble (`site-packages/…`), et une bibliothèque livrée par une autre roue y est réputée chargée par
    l'import de son paquet : torchvision (RUNPATH de construction absolu) trouve libtorch déjà chargé par `import torch`.
    `locate` : chemin absolu de l'ELF lu → chemin dans le kit (ou dans `site-packages/`) ; `present` : fichiers et liens.
    """
    glibc: set[str] = set()
    glibcxx: set[str] = set()
    required_by: dict[str, list[str]] = {}
    per_elf: dict[str, dict[str, Any]] = {}
    users: dict[str, set[str]] = {}
    wheel_libraries = {item.rsplit("/", 1)[-1] for item in present if item.startswith("site-packages/")}
    for path, info in infos.items():
        relative = locate.get(path, path)
        folder = posixpath.dirname(relative)
        search = [folder, *(found for item in info.runpath if (found := kit_path(item, folder)) is not None)]
        ollama = OLLAMA_LIBRARIES.match(relative)
        if ollama:
            # Ollama ajoute lib/ollama et le dossier de la variante au chemin des bibliothèques de ses processus (ml/path.go).
            search.append(ollama.group(1))

        runpath = [found for item in info.runpath if (found := kit_path(item, folder)) is not None]

        def provided(name: str, search: list[str] = search, runpath: list[str] = runpath, folder: str = folder,
                     wheel: bool = relative.startswith("site-packages/")) -> str | None:
            """Comment le kit fournit la bibliothèque : `chargeur` (chemin, RUNPATH/RPATH), `processus` (dossier de l'ELF,
            lib/ollama, autre roue), ou None (système)."""
            if "/" in name:
                return "chargeur" if kit_path(name, folder) in present else None
            if any(posixpath.join(directory, name) in present for directory in runpath):
                return "chargeur"
            if any(posixpath.join(directory, name) in present for directory in search) or (wheel and name in wheel_libraries):
                return "processus"
            return None

        ways = {name: provided(name) for name in info.needed}
        for name in sorted(info.needed):
            if ways[name] is None:
                examples = required_by.setdefault(name, [])
                if len(examples) < 3:
                    examples.append(relative)
                users.setdefault(name, set()).add(relative)
        own_glibc: set[str] = set()
        own_glibcxx: set[str] = set()
        for library, names in info.needs.items():
            if provided(library):
                continue
            own_glibc |= {name.removeprefix("GLIBC_") for name in names if re.fullmatch(r"GLIBC_\d+(\.\d+)+", name)}
            own_glibcxx |= {name.removeprefix("GLIBCXX_") for name in names if re.fullmatch(r"GLIBCXX_\d+(\.\d+)+", name)}
        glibc |= own_glibc
        glibcxx |= own_glibcxx
        # ldd ne voit que le chargeur : un ELF dont une dépendance n'est trouvée que par le processus n'est pas un témoin.
        per_elf[path] = {"glibc": max(own_glibc, key=version_tuple, default=None), "glibcxx": max(own_glibcxx, key=version_tuple, default=None),
                         "loader_resolved": "processus" not in ways.values()}
    return {"glibc_min": max(glibc, key=version_tuple, default=None), "glibcxx_min": max(glibcxx, key=version_tuple, default=None),
            "system_libraries": sorted(required_by), "system_libraries_required_by": dict(sorted(required_by.items())),
            "per_elf": per_elf, "users": users}


def manylinux_floor(wheel_tags: Iterable[str], machine: str) -> str | None:
    """Plancher glibc des roues livrées (PEP 600 : manylinux_X_Y ; manylinux2014 = 2.17)."""
    floors = []
    for tag in wheel_tags:
        for match in re.finditer(r"manylinux_(\d+)_(\d+)_" + re.escape(machine), tag):
            floors.append(f"{match.group(1)}.{match.group(2)}")
        if re.search(r"manylinux2014_" + re.escape(machine), tag):
            floors.append("2.17")
    return max(floors, key=version_tuple, default=None)


# --- Sélection ---------------------------------------------------------------------------------------------------------

@dataclass
class Entry:
    relative: str
    kind: str  # "file" ou "link"
    origin: str  # "git" ou "tree"
    size: int = 0
    executable: bool = False
    target: str = ""
    blob: str = ""


@dataclass
class Plan:
    platform: str
    root: Path
    commit: str
    version: str
    python_key: str
    gpu: str
    models: tuple[str, ...]
    entries: dict[str, Entry]
    excluded: dict[str, int]
    rebuilt_links: list[str]
    worktree_modified: list[str]
    model_records: list[dict[str, Any]]
    profiles: dict[str, dict[str, Any]]
    missing_for_build: list[str] = field(default_factory=list)
    # Ports des profils livrés par étiquette de modèle (KIT4-05), écrits au manifeste sous `profile_ports`.
    ports: dict[str, dict[str, int]] = field(default_factory=dict)
    tesseract: str = TESSERACT_BINARY
    web_provenance: dict[str, Any] | None = None
    web_problems: list[str] = field(default_factory=list)

    @property
    def kit_id(self) -> str:
        return f"{self.version}+{self.commit[:12]}-{self.platform}-{self.gpu}-{''.join(self.models)}"


def check_web_provenance(root: Path, commit: str, lock: bytes | None) -> tuple[dict[str, Any] | None, list[str]]:
    """Preuve de provenance de l'interface construite, comparée au commit du kit : absente, illisible, d'un autre commit,
    construite avec des sources apps/web modifiées ou un autre verrou pnpm, elle rend le kit incomplet."""
    path = root / WEB_PROVENANCE
    if not path.is_file():
        return None, [f"interface sans preuve de provenance ({WEB_PROVENANCE} absent) : {WEB_REBUILD}"]
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("format") != WEB_PROVENANCE_FORMAT:
            raise ValueError(record.get("format") if isinstance(record, dict) else type(record).__name__)
    except (OSError, ValueError):
        return None, [f"preuve de provenance de l'interface illisible ({WEB_PROVENANCE}) : reconstruire l'interface (pnpm build dans "
                      "apps/web)"]
    problems = []
    if record.get("commit") != commit:
        problems.append(f"interface construite depuis le commit {str(record.get('commit'))[:12]}, le kit livre {commit[:12]} : {WEB_REBUILD}")
    if record.get("sources_modified") is not False:
        modified = ", ".join(str(item) for item in (record.get("modified_sources") or [])[:5]) or "liste absente"
        problems.append(f"interface construite avec des sources apps/web modifiées ({modified}) : les committer, puis reconstruire "
                        "l'interface (pnpm build dans apps/web)")
    if lock is None or record.get("pnpm_lock_sha256") != hashlib.sha256(lock).hexdigest():
        problems.append(f"interface construite avec un pnpm-lock.yaml différent de celui du commit : {WEB_REBUILD}")
    return record, problems


def run_git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    git = shutil.which("git")
    if not git:
        raise KitError("git introuvable : le kit Linux est fabriqué depuis le commit courant du dépôt")
    completed = subprocess.run([git, "--no-optional-locks", "-C", str(root), *args], input=data, capture_output=True, check=False,
                               env={**os.environ, "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0"})
    if completed.returncode:
        raise KitError(f"git {' '.join(args[:2])} a échoué : {completed.stderr.decode('utf-8', 'replace').strip()}")
    return completed.stdout


def git_tracked(root: Path, commit: str, paths: tuple[str, ...]) -> list[Entry]:
    entries = []
    for record in run_git(root, "ls-tree", "-r", "-z", "--full-tree", "-l", commit, "--", *paths).split(b"\0"):
        if not record:
            continue
        meta, raw = record.split(b"\t", 1)
        mode, kind, blob, size = meta.decode().split()
        relative = raw.decode("utf-8")
        if kind != "blob":
            raise KitError(f"Entrée Git non livrable (sous-module ?) : {relative}")
        if mode == "120000":
            entries.append(Entry(relative, "link", "git", blob=blob))
        else:
            entries.append(Entry(relative, "file", "git", size=int(size), executable=mode == "100755", blob=blob))
    return entries


def git_blobs(root: Path, blobs: list[str]) -> dict[str, bytes]:
    """Contenus des blobs par `git cat-file --batch` (code et documentation : quelques Mio)."""
    output = run_git(root, "cat-file", "--batch", data=("\n".join(blobs) + "\n").encode())
    contents: dict[str, bytes] = {}
    position = 0
    for blob in blobs:
        end = output.index(b"\n", position)
        name, kind, size = output[position:end].decode().split()
        if name != blob or kind != "blob":
            raise KitError(f"Lecture Git inattendue pour {blob}")
        start = end + 1
        contents[blob] = output[start:start + int(size)]
        position = start + int(size) + 1
    return contents


def worktree_changes(root: Path, paths: tuple[str, ...]) -> list[str]:
    """Fichiers suivis modifiés ou nouveaux non ignorés sous la liste blanche : absents du kit, listés au manifeste."""
    changed = []
    records = run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths).split(b"\0")
    skip = False
    for record in records:
        if skip:
            skip = False
            continue
        if not record:
            continue
        status, relative = record[:2].decode(), record[3:].decode("utf-8")
        changed.append(relative)
        skip = status[0] in "RC"
    return sorted(set(changed))


def walk_tree(folder: Path) -> Iterator[tuple[Path, os.DirEntry]]:
    """Fichiers et liens d'un dossier, sans suivre aucun lien (un lien vers un dossier reste un lien)."""
    pending = [folder]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    yield Path(entry.path), entry
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path), entry
                else:
                    raise KitError(f"Fichier spécial refusé dans le kit : {entry.path}")


def python_key(bootstrap: str, machine: str) -> str:
    """Clé du CPython géré, telle que bootstrap.sh la demande à uv (source unique de la version)."""
    match = re.search(r"python_key=cpython-([0-9.]+)-linux-\$machine-gnu", bootstrap)
    if not match:
        raise KitError("Version de CPython introuvable dans bootstrap.sh (python_key)")
    return f"cpython-{match.group(1)}-linux-{machine}-gnu"


def model_selection(root: Path, models: tuple[str, ...], profiles: dict[str, dict[str, Any]], lock: dict[str, Any]) -> dict[str, Any]:
    """Fichiers du magasin Ollama, tokenizers et manifestes locaux des modèles choisis, contrôlés contre models.lock.json."""
    store = lock.get("store", ".runtime/models/ollama").rstrip("/")
    allowed: set[str] = set()
    records = []
    tokenizers, manifests = {}, {}
    for key in MODEL_PROFILES:
        llm = profiles[key]["llm"]
        tokenizers[key] = str(llm.get("tokenizer_dir", "")).rstrip("/")
        manifests[key] = {str(llm.get("model_manifest", "")), str(llm.get("source_model_manifest", ""))} - {""}
    for key in models:
        llm = profiles[key]["llm"]
        for name in dict.fromkeys((llm["source_model"], llm["model"])):
            entry = lock["models"].get(name)
            if not entry:
                raise KitError(f"Modèle {name} absent de {MODELS_LOCK}")
            manifest_path = f"{store}/{entry['manifest_path']}"
            path = root / manifest_path
            if not path.is_file() or stream_hash(path) != entry["manifest_sha256"]:
                raise KitError(f"Manifeste Ollama de {name} absent ou différent du verrou ({manifest_path}) : provisionner le modèle")
            allowed.add(manifest_path)
            size = path.stat().st_size
            for layer in [entry["config"], *entry["layers"]]:
                digest = layer["digest"].replace(":", "-")
                blob = f"{store}/blobs/{digest}"
                if not (root / blob).is_file() or (root / blob).stat().st_size != layer["size"]:
                    raise KitError(f"Couche {layer['digest']} de {name} absente ou de taille différente : provisionner le modèle")
                allowed.add(blob)
                size += layer["size"]
                metadata = f"{store}/metadata/{digest}.json"
                if (root / metadata).is_file():
                    allowed.add(metadata)
            records.append({"name": name, "set": key, "role": entry.get("role"), "manifest_path": manifest_path,
                            "manifest_sha256": entry["manifest_sha256"], "bytes": size})
    unselected = [key for key in MODEL_PROFILES if key not in models]
    kept_tokenizers = {tokenizers[key] for key in models}
    excluded_dirs = [tokenizers[key] for key in unselected if tokenizers[key] and tokenizers[key] not in kept_tokenizers]
    kept_manifests: set[str] = set().union(*(manifests[key] for key in models))
    excluded_files: set[str] = set().union(*(manifests[key] for key in unselected)) - kept_manifests
    return {"store": store, "allowed": allowed, "records": records, "excluded_dirs": excluded_dirs, "excluded_files": excluded_files}


def plan_kit(root: Path = ROOT, *, platform: str, gpu: str = "none", models: tuple[str, ...] = DEFAULT_MODELS,
             commit: str | None = None) -> Plan:
    """Liste du kit sans rien copier : chaque refus nomme sa cause et la correction attendue."""
    import tomllib

    import yaml

    if platform not in LINUX_PLATFORMS:
        raise KitError(f"Plateforme Linux inconnue : {platform}")
    machine = LINUX_PLATFORMS[platform]["machine"]
    if gpu not in GPU_VARIANTS:
        raise KitError(f"Variante GPU inconnue : {gpu} (none ou jetpack5)")
    if gpu == "jetpack5":
        release = l4t_release()
        if platform != "linux-aarch64" or not release or release.get("major") != 35:
            raise KitError("--gpu jetpack5 ne se fabrique que sur un Jetson Linux R35 (JetPack 5) : le complément vise ce seul poste")
    models = tuple(key for key in MODEL_PROFILES if key in models)
    if DEFAULT_MODEL not in models:
        raise KitError(DEFAULT_MODEL_REFUSAL)
    commit = commit or run_git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    tracked = git_tracked(root, commit, TRACKED)
    blobs = git_blobs(root, [entry.blob for entry in tracked if entry.relative in {"pyproject.toml", "bootstrap.sh", MODELS_LOCK, WEB_LOCK,
                                                                                    *MODEL_PROFILES.values()}])
    by_name = {entry.relative: blobs.get(entry.blob) for entry in tracked}
    for required in ("pyproject.toml", "bootstrap.sh", MODELS_LOCK, *MODEL_PROFILES.values()):
        if by_name.get(required) is None:
            raise KitError(f"{required} absent du commit {commit[:12]}")
    version = tomllib.loads(by_name["pyproject.toml"].decode("utf-8"))["project"]["version"]  # type: ignore[union-attr]
    key = python_key(by_name["bootstrap.sh"].decode("utf-8"), machine)  # type: ignore[union-attr]
    profiles = {name: yaml.safe_load(by_name[path].decode("utf-8")) for name, path in MODEL_PROFILES.items()}  # type: ignore[union-attr]
    lock = json.loads(by_name[MODELS_LOCK].decode("utf-8"))  # type: ignore[union-attr]
    selection = model_selection(root, models, profiles, lock)
    ports = {selection_label(profiles[name]): profile_ports(MODEL_PROFILES[name], profiles[name]) for name in models}

    entries: dict[str, Entry] = {}
    excluded: dict[str, int] = {}
    rebuilt: list[str] = []

    def exclude(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    def skipped(relative: str) -> str | None:
        if any(fnmatch.fnmatch(relative, pattern) for pattern in EXCLUDED):
            return "motif exclu"
        gpu_dir = re.match(r"\.runtime/bin/ollama-[^/]+/lib/ollama/([^/]+)/", relative)
        if gpu_dir and gpu_dir.group(1) not in GPU_VARIANTS[gpu]:
            return f"bibliothèques GPU {gpu_dir.group(1)}"
        if relative.startswith(selection["store"] + "/") and relative not in selection["allowed"]:
            return "magasin Ollama hors modèles choisis"
        if any(relative.startswith(folder + "/") for folder in selection["excluded_dirs"]) or relative in selection["excluded_files"]:
            return "modèle non choisi"
        return None

    for entry in tracked:
        check_name(entry.relative)
        reason = skipped(entry.relative)
        if reason:
            exclude(reason)
            continue
        entries[entry.relative] = entry
    for pattern in ARTIFACTS:
        top = pattern.format(python=key)
        base = root / top
        if base.is_symlink():
            raise KitError(f"{top} est un lien : le kit ne suit pas les liens de la liste blanche")
        if not base.exists():
            continue
        for path, item in sorted(walk_tree(base) if base.is_dir() else [], key=lambda pair: str(pair[0])):
            relative = path.relative_to(root).as_posix()
            check_name(relative)
            reason = skipped(relative)
            if reason:
                exclude(reason)
                continue
            if item.is_symlink():
                entries[relative] = Entry(relative, "link", "tree", target=os.readlink(path))
            else:
                mode = item.stat(follow_symlinks=False).st_mode
                entries[relative] = Entry(relative, "file", "tree", size=item.stat(follow_symlinks=False).st_size,
                                          executable=bool(mode & stat.S_IXUSR))
    # Lien de version mineure créé par `uv python install` (absolu sur ce poste) : le .venv désigne la version complète.
    minor = root / f".runtime/python/cpython-{'.'.join(key.split('-')[1].split('.')[:2])}-linux-{machine}-gnu"
    if minor.is_symlink():
        rebuilt.append(minor.relative_to(root).as_posix())
    refused = sorted(f"{relative} ({reason})" for relative in entries if (reason := forbidden(relative)))
    if refused:
        raise KitError(f"Entrée interdite dans le kit : {refused[:5]}")
    # Liens : relatifs, internes et résolus dans le kit ; les autres arrêtent la fabrication.
    if any(entry.kind == "link" and entry.origin == "git" for entry in entries.values()):
        contents = git_blobs(root, [entry.blob for entry in entries.values() if entry.kind == "link" and entry.origin == "git"])
        for entry in entries.values():
            if entry.kind == "link" and entry.origin == "git":
                entry.target = contents[entry.blob].decode("utf-8")
    directories = {posixpath.dirname(name) for name in entries}
    prefixes = {"/".join(name.split("/")[:depth]) for name in directories for depth in range(1, name.count("/") + 2)}
    bad_links = []
    for entry in entries.values():
        if entry.kind != "link":
            continue
        resolved = normalized_link(entry.relative, entry.target)
        if resolved is None:
            bad_links.append(f"{entry.relative} -> {entry.target} (absolu ou hors du kit)")
        elif resolved not in entries and resolved not in prefixes:
            bad_links.append(f"{entry.relative} -> {entry.target} (cible absente du kit)")
    if bad_links:
        raise KitError(f"Lien symbolique refusé : {bad_links[:5]}")
    web_record, web_problems = check_web_provenance(root, commit, by_name.get(WEB_LOCK))
    return Plan(platform=platform, root=root, commit=commit, version=version, python_key=key, gpu=gpu, models=models,
                entries=entries, excluded=excluded, rebuilt_links=rebuilt, worktree_modified=worktree_changes(root, TRACKED),
                model_records=selection["records"], profiles=profiles, ports=ports,
                missing_for_build=[name for name in required_for_build() if name not in entries],
                tesseract=tesseract_path(profiles[DEFAULT_MODEL]), web_provenance=web_record, web_problems=web_problems)


def selection_label(profile: dict[str, Any]) -> str:
    """Étiquette d'un profil livré que `rag.sh --model` et `atelier ouvrir --modele` acceptent : le modèle source
    (qwen3.5:4b pour le profil 4B, servi par qwen3.5:4b-text), ou le modèle servi s'il n'a pas de source distincte."""
    llm = profile["llm"]
    return str(llm.get("source_model") or llm["model"])


PORT_KEYS = {"app": "app.port", "qdrant": "qdrant.url", "ollama": "llm.base_url"}


def profile_ports(path: str, profile: dict[str, Any]) -> dict[str, int]:
    """Ports d'un profil livré, tels que `init-profile` les reprend (services/runtime/profile_setup.user_profile) : `app.port`
    et le port explicite de `qdrant.url` et de `llm.base_url`. L'installateur, qui n'emploie que la bibliothèque standard et
    ne lit pas le YAML, les contrôle avant toute écriture depuis le manifeste (`profile_ports`, KIT4-05)."""
    values: dict[str, Any] = {"app": (profile.get("app") or {}).get("port")}
    for name, (section, key) in (("qdrant", ("qdrant", "url")), ("ollama", ("llm", "base_url"))):
        try:
            values[name] = urlsplit(str((profile.get(section) or {}).get(key) or "")).port
        except ValueError:
            values[name] = None
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
            raise KitError(f"{path} : port de {PORT_KEYS[name]} absent ou invalide ({value!r}) ; init-profile et le superviseur "
                           "exigent un port explicite entre 1 et 65535 : corriger le profil et le committer")
    return values


def tesseract_path(profile: dict[str, Any]) -> str:
    """Exécutable Tesseract du profil livré, sans le suffixe `.exe` du profil commun (platforms.native_executable)."""
    configured = str((profile.get("pdf") or {}).get("tesseract_cmd") or TESSERACT_BINARY)
    return configured[:-4] if configured.lower().endswith(".exe") else configured


def group_of(relative: str) -> str:
    parts = relative.split("/")
    if parts[0] == ".runtime" and len(parts) > 2 and parts[1] in {"models", "cache", "bin"}:
        return "/".join(parts[1:3])
    return parts[1] if parts[0] == ".runtime" and len(parts) > 1 else parts[0]


# --- Neutralisations ---------------------------------------------------------------------------------------------------

def sysconfig_pattern(key: str) -> str:
    return f".runtime/python/{key}/lib/python3.*/_sysconfigdata_*.py"


def neutralize(relative: str, data: bytes, *, markers: list[str], python_prefixes: list[str], key: str) -> tuple[bytes, dict | None]:
    """Seules neutralisations admises ; le contenu rendu est ensuite comparé aux marqueurs comme tout autre fichier."""
    ordered = sorted(markers, key=len, reverse=True)

    def scrub(value: str) -> str:
        for marker in ordered:
            value = value.replace(marker, HOST_TOKEN)
        return value

    if relative == TESSERACT_BUILT:
        manifest = json.loads(data.decode("utf-8"))
        fields: list[str] = []
        if isinstance(manifest.get("file_prefix_map"), dict) and isinstance(manifest["file_prefix_map"].get("flags"), str):
            before = manifest["file_prefix_map"]["flags"]
            manifest["file_prefix_map"]["flags"] = scrub(before)
            fields += ["file_prefix_map.flags"] if before != manifest["file_prefix_map"]["flags"] else []
        for name in ("HOME", "TMPDIR"):
            environment = manifest.get("build_environment") or {}
            if isinstance(environment.get(name), str) and scrub(environment[name]) != environment[name]:
                environment[name] = scrub(environment[name])
                fields.append(f"build_environment.{name}")
        for index, step in enumerate(manifest.get("steps") or []):
            command = step.get("command") if isinstance(step, dict) else None
            if isinstance(command, list):
                cleaned = [scrub(item) if isinstance(item, str) else item for item in command]
                if cleaned != command:
                    step["command"] = cleaned
                    fields.append(f"steps[{index}].command")
        rendered = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        return rendered, {"path": relative, "kind": "json_fields", "fields": fields, "token": HOST_TOKEN,
                          "reason": "chemins de construction descriptifs ; verify_built_copy ne lit ni ces champs ni leur contenu",
                          "source_sha256": hashlib.sha256(data).hexdigest()}
    if fnmatch.fnmatch(relative, sysconfig_pattern(key)):
        count = 0
        for prefix in sorted(python_prefixes, key=len, reverse=True):
            count += data.count(prefix.encode())
            data = data.replace(prefix.encode(), PYTHON_PREFIX_TOKEN.encode())
        return data, {"path": relative, "kind": "python_prefix", "token": PYTHON_PREFIX_TOKEN, "replacements": count,
                      "rewrite_at_install": True,
                      "reason": "préfixe écrit par uv à l'installation de CPython ; réécrit vers le préfixe réel par l'installateur"}
    return data, None


# --- Fabrication -----------------------------------------------------------------------------------------------------

def tree_scan(plan: Plan, markers: list[str], read: Callable[[Path], Iterator[bytes]] = read_blocks) -> dict[str, Any]:
    """Liste seulement (dry-run) : tailles, liens, ELF, fuites. Lit chaque octet, n'écrit rien."""
    raw = [marker.encode() for marker in markers]
    prefixes = python_prefixes(plan)
    leaks: dict[str, list[str]] = {}
    neutralizations = []
    elf: list[Path] = []
    machines: dict[str, int] = {}
    blobs = git_blobs(plan.root, [entry.blob for entry in plan.entries.values() if entry.origin == "git" and entry.kind == "file"])
    for entry in sorted(plan.entries.values(), key=lambda item: item.size):
        if entry.kind == "link":
            if any(marker in entry.target for marker in markers):
                leaks[entry.relative] = [marker for marker in markers if marker in entry.target]
            continue
        if entry.origin == "git":
            data, record = neutralize(entry.relative, blobs[entry.blob], markers=markers, python_prefixes=prefixes, key=plan.python_key)
            found = scan_markers([data], raw)
        else:
            source = plan.root / entry.relative
            if is_neutralized(entry.relative, plan.python_key):
                data, record = neutralize(entry.relative, source.read_bytes(), markers=markers, python_prefixes=prefixes,
                                          key=plan.python_key)
                found = scan_markers([data], raw)
            else:
                record = None
                found = scan_markers(read(source), raw)
            with source.open("rb") as reader:
                machine = elf_machine(reader.read(20))
            if machine is not None:
                elf.append(source)
                machines[entry.relative] = machine
        if record:
            neutralizations.append(record)
        if found:
            leaks[entry.relative] = sorted(marker.decode() for marker in found)
    return {"leaks": leaks, "neutralizations": neutralizations, "elf": elf, "machines": machines, "blobs": blobs}


def python_prefixes(plan: Plan) -> list[str]:
    prefix = plan.root / ".runtime/python" / plan.python_key
    return sorted({str(prefix), os.path.realpath(prefix)}, key=len, reverse=True)


def is_neutralized(relative: str, key: str) -> bool:
    return relative == TESSERACT_BUILT or fnmatch.fnmatch(relative, sysconfig_pattern(key))


def requirements(plan: Plan, elf: list[Path], machines: dict[str, int]) -> dict[str, Any]:
    expected = LINUX_PLATFORMS[plan.platform]["e_machine"]
    machine = LINUX_PLATFORMS[plan.platform]["machine"]
    foreign = sorted(name for name, value in machines.items() if value != expected)
    if foreign:
        raise KitError(f"ELF d'une autre architecture que {plan.platform} ({len(foreign)}) : {foreign[:5]} ; jamais de kit croisé")
    infos = readelf_batches(elf)

    def site(relative: str) -> str:
        match = ARCHIVE_ENTRY.match(relative)
        return f"site-packages/{match.group(1)}" if match else relative

    locate = {str(plan.root / relative): site(relative) for relative in machines}
    needs = system_requirements(infos, locate, set(plan.entries) | {site(relative) for relative in plan.entries})
    relative_of = {str(plan.root / relative): relative for relative in machines}
    checks = {plan.tesseract} & set(machines) | {relative for relative in machines if re.fullmatch(CV2_MODULE, relative)}
    for key in ("glibc", "glibcxx"):
        maximum = needs[f"{key}_min"]
        carriers = sorted((relative_of[path] for path, item in needs["per_elf"].items()
                           if maximum and item[key] == maximum and item["loader_resolved"] and path in relative_of),
                          key=lambda relative: ("opencv_python.libs" not in relative, relative))
        checks |= set(carriers[:CARRIERS_PER_MAXIMUM])
    ldd_checks = sorted(checks)
    optional: dict[str, str] = {}
    for name, found in needs["users"].items():
        for pattern, reason in OPTIONAL_USERS.items():
            if all(re.fullmatch(pattern, user) for user in found):
                optional[name] = reason
    tags = []
    for relative, entry in plan.entries.items():
        if entry.kind == "file" and relative.startswith(".runtime/cache/uv/") and relative.endswith(".dist-info/WHEEL"):
            tags += [line.split(":", 1)[1].strip() for line in (plan.root / relative).read_text(encoding="utf-8", errors="replace").splitlines()
                     if line.startswith("Tag:")]
    floor = manylinux_floor(tags, machine)
    candidates = [value for value in (needs["glibc_min"], floor) if value]
    tesseract = infos.get(str(plan.root / plan.tesseract))
    return {"arch": machine, "glibc_min": max(candidates, key=version_tuple) if candidates else None,
            "glibc_min_sources": {"elf_version_needs": needs["glibc_min"], "wheel_manylinux_tags": floor},
            "glibcxx_min": needs["glibcxx_min"], "kernel_min": KERNEL_MIN, "tools": [dict(item) for item in TARGET_TOOLS],
            "system_libraries": [name for name in needs["system_libraries"] if name not in optional],
            "system_libraries_required_by": {name: users for name, users in needs["system_libraries_required_by"].items() if name not in optional},
            "optional_system_libraries": dict(sorted(optional.items())),
            "system_packages": system_packages(needs["system_libraries"], needs["users"]),
            # Tesseract n'a ni RUNPATH ni RPATH : toutes ses dépendances viennent du système (ldd le vérifie à l'installation).
            "tesseract_system_libraries": sorted(tesseract.needed) if tesseract else [], "ldd_checks": ldd_checks,
            "tesseract": plan.tesseract, "elf_files": len(elf),
            "reference_os": REFERENCE_OS if plan.platform == "linux-aarch64" else None,
            "installation_qualified": plan.platform in QUALIFIED_INSTALLATIONS,
            "installation_qualification_proof": QUALIFIED_INSTALLATIONS.get(plan.platform),
            "memory_gib_min": MEMORY_MIN_GIB}


def required_for_build() -> tuple[str, ...]:
    """Fichiers du commit sans lesquels le kit ne s'installe pas, icône du menu comprise (ICON_SOURCE de l'installateur).
    Une constante absente est rendue comme une entrée manquante nommée : le kit est incomplet, la fabrication refusée."""
    from tools.dist import linux_install

    icon = getattr(linux_install, "ICON_SOURCE", None)
    return (*REQUIRED_FOR_BUILD, icon if isinstance(icon, str) and icon else "ICON_SOURCE (constante absente de tools/dist/linux_install.py)")


def incomplete_causes(plan: Plan) -> list[str]:
    """Ce qui empêche la fabrication, dans l'ordre où build_linux_kit le refuse."""
    missing = [f"absents du commit {plan.commit[:12]} : {plan.missing_for_build} ; le kit livre le commit courant, committer ces "
               "fichiers avant de fabriquer"] if plan.missing_for_build else []
    return missing + plan.web_problems


def dry_run(root: Path = ROOT, *, platform: str, gpu: str = "none", models: tuple[str, ...] = DEFAULT_MODELS,
            home: str | None = None) -> dict[str, Any]:
    """Essai sans copie : ce que contiendrait le kit, ses exigences et ses fuites. Lit tous les octets sélectionnés."""
    started = dt.datetime.now(dt.UTC)
    plan = plan_kit(root, platform=platform, gpu=gpu, models=models)
    markers = host_markers(root, home if home is not None else os.environ.get("HOME"))
    scan = tree_scan(plan, markers)
    needs = requirements(plan, scan["elf"], scan["machines"])
    sizes: dict[str, int] = {}
    for entry in plan.entries.values():
        sizes[group_of(entry.relative)] = sizes.get(group_of(entry.relative), 0) + entry.size
    files = [entry for entry in plan.entries.values() if entry.kind == "file"]
    causes = incomplete_causes(plan)
    guide: dict[str, Any] = {"file": GUIDE, "status": "not_rendered"}
    if not plan.missing_for_build:
        # Fichiers que la fabrication ajouterait (avis, installateur, listes, guide), rendus et comparés aux marqueurs.
        links = sorted((entry.relative, entry.target) for entry in plan.entries.values() if entry.kind == "link")
        executables = [entry.relative for entry in files if entry.executable]
        manifest = kit_manifest(plan, needs=needs, sizes=sizes, links=len(links), files=len(files), neutralizations=scan["neutralizations"],
                                sums=None, links_data=links_text(links), lock_blobs=scan["blobs"])
        try:
            extra = kit_extras(plan, blobs=scan["blobs"], links=links, executables=executables, manifest=manifest)
        except KitError as error:
            causes.append(str(error))
            guide["status"] = "refused"
        else:
            raw = [marker.encode() for marker in markers]
            scan["leaks"].update({name: sorted(marker.decode() for marker in found) for name, (data, _) in extra.items()
                                  if (found := scan_markers([data], raw))})
            guide.update(status="rendered", sections=manifest["guide"]["sections"], sha256=hashlib.sha256(extra[GUIDE][0]).hexdigest())
    status = "leaks" if scan["leaks"] else "incomplete" if causes else "ready"
    return {"status": status, "mode": "dry-run", "kit_id": plan.kit_id, "platform": plan.platform,
            "missing_for_build": plan.missing_for_build, "incomplete_causes": causes, "profile_ports": plan.ports,
            "web_provenance": plan.web_provenance, "guide": guide,
            "commit": plan.commit, "files": len(files), "symlinks": len(plan.entries) - len(files), "bytes": sum(sizes.values()),
            "bytes_by_group": dict(sorted(sizes.items())), "excluded": plan.excluded, "links_rebuilt_by_tools": plan.rebuilt_links,
            "worktree_modified_excluded": plan.worktree_modified, "models": plan.model_records, "target": needs,
            "leaks": scan["leaks"], "neutralizations": scan["neutralizations"], "markers": markers,
            "started_utc": started.isoformat(), "finished_utc": dt.datetime.now(dt.UTC).isoformat()}


def copy_scan(source: Path, target: Path | None, markers: list[bytes]) -> tuple[str, int, set[bytes]]:
    """Copie (si `target`), hachage et recherche des marqueurs en un seul passage."""
    digest, size = hashlib.sha256(), 0
    keep = max((len(marker) for marker in markers), default=1) - 1
    tail, found = b"", set[bytes]()
    writer = target.open("xb") if target is not None else None
    try:
        with source.open("rb") as reader:
            for block in iter(lambda: reader.read(CHUNK), b""):
                digest.update(block)
                size += len(block)
                window = tail + block
                found.update(marker for marker in markers if marker in window)
                tail = window[-keep:] if keep else b""
                if writer:
                    writer.write(block)
    finally:
        if writer:
            writer.close()
    return digest.hexdigest(), size, found


def build_linux_kit(output: Path, root: Path = ROOT, *, platform: str, gpu: str = "none", models: tuple[str, ...] = DEFAULT_MODELS,
                    home: str | None = None) -> dict[str, Any]:
    """Fabrication réelle : dossier neuf hors du dépôt, retiré entièrement au moindre refus."""
    output = output.resolve()
    if output.is_relative_to(root.resolve()) or (output.exists() and any(output.iterdir())):
        raise KitError("Le kit exige un dossier neuf hors du dépôt")
    plan = plan_kit(root, platform=platform, gpu=gpu, models=models)
    if plan.missing_for_build:
        raise KitError(f"Absents du commit {plan.commit[:12]} : {plan.missing_for_build} ; le kit livre le commit courant, "
                       "committer ces fichiers avant de fabriquer")
    if plan.web_problems:
        raise KitError("Interface non conforme au commit du kit : " + " ; ".join(plan.web_problems))
    markers = host_markers(root, home if home is not None else os.environ.get("HOME"))
    raw = [marker.encode() for marker in markers]
    prefixes = python_prefixes(plan)
    # Exigences établies avant toute copie : un binaire étranger ou readelf absent arrête la fabrication tôt.
    elf: list[Path] = []
    machines: dict[str, int] = {}
    for entry in plan.entries.values():
        if entry.kind == "file" and entry.origin == "tree":
            source = root / entry.relative
            with source.open("rb") as reader:
                machine = elf_machine(reader.read(20))
            if machine is not None:
                elf.append(source)
                machines[entry.relative] = machine
    needs = requirements(plan, elf, machines)
    blobs = git_blobs(root, [entry.blob for entry in plan.entries.values() if entry.origin == "git" and entry.kind == "file"])
    output.mkdir(parents=True, exist_ok=True)
    sums: list[str] = []
    sizes: dict[str, int] = {}
    leaks: dict[str, list[str]] = {}
    neutralizations: list[dict] = []
    executables: list[str] = []
    try:
        for entry in sorted((item for item in plan.entries.values() if item.kind == "file"), key=lambda item: (item.size, item.relative)):
            target = output / entry.relative
            writing = not leaks
            if writing:
                target.parent.mkdir(parents=True, exist_ok=True)
            if entry.origin == "git" or is_neutralized(entry.relative, plan.python_key):
                data = blobs[entry.blob] if entry.origin == "git" else (root / entry.relative).read_bytes()
                data, record = neutralize(entry.relative, data, markers=markers, python_prefixes=prefixes, key=plan.python_key)
                if record:
                    record["kit_sha256"] = hashlib.sha256(data).hexdigest()
                    neutralizations.append(record)
                found = scan_markers([data], raw)
                if writing:
                    target.write_bytes(data)
                digest, size = hashlib.sha256(data).hexdigest(), len(data)
            else:
                digest, size, found = copy_scan(root / entry.relative, target if writing else None, raw)
                if writing:
                    shutil.copystat(root / entry.relative, target)
            if found:
                leaks[entry.relative] = sorted(marker.decode() for marker in found)
                continue
            if writing:
                os.chmod(target, 0o755 if entry.executable else 0o644)
            if entry.executable:
                executables.append(entry.relative)
            sums.append(f"{digest}  {entry.relative}")
            sizes[group_of(entry.relative)] = sizes.get(group_of(entry.relative), 0) + size
        if leaks:
            raise KitError(f"Chemin du poste de fabrication présent dans le kit : {sorted(leaks)[:5]}")
        links = sorted((entry.relative, entry.target) for entry in plan.entries.values() if entry.kind == "link")
        for relative, link_target in links:
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(link_target, path)
        # Le guide découle du manifeste ; SHA256SUMS, qui le couvre, n'entre au manifeste qu'ensuite.
        manifest = kit_manifest(plan, needs=needs, sizes=sizes, links=len(links), files=len(sums), neutralizations=neutralizations,
                                sums=None, links_data=links_text(links), lock_blobs=blobs)
        extra = kit_extras(plan, blobs=blobs, links=links, executables=executables, manifest=manifest)
        # Fichiers ajoutés par le fabricant : comparés aux marqueurs du poste comme tout fichier copié.
        leaks = {name: sorted(marker.decode() for marker in found) for name, (data, _) in extra.items() if (found := scan_markers([data], raw))}
        if leaks:
            raise KitError(f"Chemin du poste de fabrication présent dans le kit : {sorted(leaks)[:5]}")
        for name, (data, executable) in extra.items():
            (output / name).write_bytes(data)
            os.chmod(output / name, 0o755 if executable else 0o644)
            sums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
        sums_data = ("\n".join(sorted(sums, key=lambda line: line.split("  ", 1)[1])) + "\n").encode()
        (output / SUMS).write_bytes(sums_data)
        manifest["sha256sums_sha256"] = hashlib.sha256(sums_data).hexdigest()
        (output / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return manifest


def links_text(links: list[tuple[str, str]]) -> bytes:
    return "".join(f"{relative}\t{link_target}\n" for relative, link_target in links).encode()


def kit_extras(plan: Plan, *, blobs: dict[str, bytes], links: list[tuple[str, str]], executables: list[str],
               manifest: dict[str, Any]) -> dict[str, tuple[bytes, bool]]:
    """Fichiers que le fabricant ajoute à la racine du kit : avis de tiers, installateur, listes des liens et des exécutables,
    guide. Le manifeste reçoit les sections canoniques citées par le guide."""
    from tools.dist.kit_guide import GuideError, render, section_links
    from tools.dist.notices import third_party_notices

    lock = json.loads(blobs[plan.entries["config/artifacts.lock.json"].blob].decode("utf-8"))
    notices = third_party_notices(plan.root, sorted(plan.entries), plan.version, plan.platform, lock=lock, gpu=plan.gpu,
                                  models=plan.models).encode("utf-8")
    documents = {relative: blobs[entry.blob].decode("utf-8") for relative, entry in plan.entries.items()
                 if relative.startswith("docs/") and relative.endswith(".md") and entry.kind == "file" and entry.origin == "git"}
    files = {"guide": GUIDE, "manifest": MANIFEST, "sums": SUMS, "links": LINKS, "executables": EXECUTABLES, "notices": NOTICES,
             "installer": INSTALLER}
    try:
        guide = render(manifest, template=blobs[plan.entries[GUIDE_TEMPLATE].blob].decode("utf-8"), documents=documents, files=files)
    except GuideError as error:
        raise KitError(f"Guide {GUIDE} non rendu : {error}") from error
    manifest["guide"] = {"file": GUIDE, "template": GUIDE_TEMPLATE, "sections": section_links(documents)[0],
                         "sha256": hashlib.sha256(guide.encode("utf-8")).hexdigest()}
    return {NOTICES: (notices, False), INSTALLER: (blobs[plan.entries["tools/dist/install.sh"].blob], True), LINKS: (links_text(links), False),
            EXECUTABLES: ("".join(f"{name}\n" for name in sorted({*executables, INSTALLER})).encode(), False),
            GUIDE: (guide.encode("utf-8"), False)}


def kit_manifest(plan: Plan, *, needs: dict[str, Any], sizes: dict[str, int], links: int, files: int, neutralizations: list[dict],
                 sums: bytes | None, links_data: bytes, lock_blobs: dict[str, bytes]) -> dict[str, Any]:
    """Manifeste du kit ; sans `sums`, l'empreinte de SHA256SUMS est ajoutée après l'écriture des fichiers ajoutés."""
    def blob_sha(relative: str) -> str | None:
        entry = plan.entries.get(relative)
        return hashlib.sha256(lock_blobs[entry.blob]).hexdigest() if entry and entry.blob in lock_blobs else None

    provenance = {name: blob_sha(name) for name in ("config/artifacts.lock.json", MODELS_LOCK, "uv.lock")}
    artifacts = plan.root / ".runtime/manifests/artifacts.json"
    provenance[".runtime/manifests/artifacts.json"] = stream_hash(artifacts) if artifacts.is_file() else None
    total = sum(sizes.values())
    default = selection_label(plan.profiles[DEFAULT_MODEL])
    return {"format": KIT_FORMAT, "kit_id": plan.kit_id, "version": plan.version, "commit": plan.commit,
            "built_utc": dt.datetime.now(dt.UTC).isoformat(), "platform": plan.platform, "build_host": build_host(),
            "target": needs, "python": {"key": plan.python_key, "executable": f".runtime/python/{plan.python_key}/bin/python3.12"},
            "gpu": {"variant": plan.gpu, "ollama_libraries": list(GPU_VARIANTS[plan.gpu]),
                    "requires_l4t_major": 35 if plan.gpu == "jetpack5" else None},
            "models": plan.model_records, "model_sets": list(plan.models), "default_model": default,
            "model_profiles": {selection_label(plan.profiles[key]): path for key, path in MODEL_PROFILES.items() if key in plan.models},
            "profile_ports": plan.ports,
            "requirements": {"memory_gib_min": MEMORY_MIN_GIB, "kit_bytes": total, "install_bytes_min": total + INSTALL_MARGIN},
            "provenance": provenance, "web_provenance": {**(plan.web_provenance or {}), "file": WEB_PROVENANCE},
            "tracked_source": {"commit": plan.commit, "paths": list(TRACKED), "worktree_modified_excluded": plan.worktree_modified},
            "untracked_artifacts": [pattern.format(python=plan.python_key) for pattern in ARTIFACTS],
            "neutralizations": neutralizations,
            "excluded": {"patterns": list(EXCLUDED), "forbidden_prefixes": list(LINUX_FORBIDDEN_PREFIXES),
                         "forbidden_names": list(FORBIDDEN_NAMES), "counts": plan.excluded, "links_rebuilt_by_tools": plan.rebuilt_links},
            "files": files, "symlinks": links, "bytes": total, "bytes_by_group": dict(sorted(sizes.items())),
            **({"sha256sums_sha256": hashlib.sha256(sums).hexdigest()} if sums is not None else {}),
            "symlinks_sha256": hashlib.sha256(links_data).hexdigest(),
            "notices": {"file": NOTICES, "usage": "interne, sans redistribution hors de l'organisation (W030)"},
            "installer": INSTALLER}


# --- Intégrité ---------------------------------------------------------------------------------------------------------

def read_sums(folder: Path) -> dict[str, str]:
    return parse_sums((folder / SUMS).read_bytes())


def parse_sums(data: bytes) -> dict[str, str]:
    expected: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if line:
            digest, relative = line.split("  ", 1)
            check_name(relative)
            expected[relative] = digest
    return expected


def read_links(data: bytes) -> dict[str, str]:
    links = {}
    for line in data.decode("utf-8").splitlines():
        if line:
            relative, target = line.split("\t", 1)
            check_name(relative)
            if normalized_link(relative, target) is None:
                raise KitError(f"Lien absolu ou sortant déclaré : {relative} -> {target}")
            links[relative] = target
    return links


def declared(folder: Path, expected: dict[str, str]) -> tuple[dict[str, str], set[str]]:
    """SYMLINKS et EXECUTABLES, contrôlés contre SHA256SUMS avant usage."""
    contents = {}
    for name in (LINKS, EXECUTABLES):
        data = (folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected.get(name):
            raise KitError(f"{name} différent de SHA256SUMS : kit altéré")
        contents[name] = data
    return read_links(contents[LINKS]), {line for line in contents[EXECUTABLES].decode("utf-8").splitlines() if line}


def verify_kit(folder: Path) -> dict[str, Any]:
    """Chaque empreinte, chaque lien (cible exacte), le bit x, aucun fichier ni lien en trop."""
    folder = folder.resolve()
    expected = read_sums(folder)
    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    problems: list[str] = []
    if manifest.get("sha256sums_sha256") != stream_hash(folder / SUMS):
        problems.append("SHA256SUMS différent du manifeste")
    try:
        links, executables = declared(folder, expected)
    except (KitError, OSError) as error:
        return {"status": "failed", "problems": [str(error)], "altered_or_missing": [], "links_altered_or_missing": [], "unexpected": []}
    if manifest.get("symlinks_sha256") != stream_hash(folder / LINKS):
        problems.append("SYMLINKS différent du manifeste")
    altered = []
    modes = []
    for relative, digest in expected.items():
        path = folder / relative
        if path.is_symlink() or not path.is_file() or stream_hash(path) != digest:
            altered.append(relative)
        elif relative in executables and not path.stat().st_mode & stat.S_IXUSR:
            modes.append(relative)
    bad_links = [relative for relative, target in links.items()
                 if not (folder / relative).is_symlink() or os.readlink(folder / relative) != target
                 or not Path(os.path.realpath(folder / relative)).is_relative_to(folder)]
    present_files: set[str] = set()
    present_links: set[str] = set()
    for path, item in walk_tree(folder):
        relative = path.relative_to(folder).as_posix()
        (present_links if item.is_symlink() else present_files).add(relative)
    unexpected = sorted((present_files - set(expected) - {SUMS, MANIFEST}) | (present_links - set(links)))
    ok = not (problems or altered or modes or bad_links or unexpected)
    return {"files": len(expected), "links": len(links), "altered_or_missing": sorted(altered), "links_altered_or_missing": sorted(bad_links),
            "executable_bit_missing": sorted(modes), "unexpected": unexpected, "problems": problems,
            "status": "verified" if ok else "failed"}


def install_copy(folder: Path, target: Path, *, progress: Callable[[int, int], None] | None = None,
                 sums_sha256: str | None = None) -> dict[str, Any]:
    """Copie vérifiée en un seul passage : empreintes pendant la copie, bit x, liens recréés à l'identique.

    Le moindre écart retire la copie partielle ; les fichiers du kit absents de SHA256SUMS ne sont pas copiés.
    `progress(octets copiés, total)` est appelé après chaque fichier, puis une dernière fois au total (KIT4-07).

    Copie liée à la liste vérifiée (S14) : le manifeste et SHA256SUMS ne sont lus qu'une fois. SHA256SUMS doit porter
    l'empreinte `sums_sha256` que l'appelant a contrôlée (à défaut, celle du manifeste lu), chaque fichier est comparé à
    cette liste, et le programme reçoit ces mêmes octets, relus après écriture : une ré-extraction du kit pendant
    l'installation ne fait jamais désigner une liste ou un manifeste non vérifiés."""
    from tools.dist.build_kit import stream_copy

    folder, target = folder.resolve(), target.resolve()
    if target.exists() or target.is_symlink():
        raise KitError(f"Destination déjà présente, jamais remplacée : {target}")
    manifest_data = (folder / MANIFEST).read_bytes()
    try:
        record = json.loads(manifest_data.decode("utf-8"))
    except ValueError as error:
        raise KitError(f"{MANIFEST} illisible : {error}") from error
    recorded = record.get("sha256sums_sha256") if isinstance(record, dict) else None
    if sums_sha256 is not None and recorded != sums_sha256:
        raise KitError(f"{MANIFEST} a changé depuis sa vérification : kit remplacé pendant l'installation, ré-extraire l'archive")
    reference = sums_sha256 or recorded
    sums_data = (folder / SUMS).read_bytes()
    if not reference or hashlib.sha256(sums_data).hexdigest() != reference:
        raise KitError("SHA256SUMS différent du manifeste : kit altéré")
    expected = parse_sums(sums_data)
    links, executables = declared(folder, expected)
    total = sum((folder / relative).stat().st_size for relative in expected if (folder / relative).is_file()) if progress else 0
    target.mkdir(parents=True)
    copied = done = 0
    try:
        for relative, digest in expected.items():
            source, destination = folder / relative, target / relative
            if source.is_symlink():
                # Fichier listé devenu lien (outil de déduplication, ferme de liens) : jamais suivi, nommé pour ce qu'il est.
                raise KitError(f"Fichier du kit remplacé par un lien : {relative} (déduplication ou ferme de liens)")
            if not source.is_file():
                raise KitError(f"Fichier du kit absent : {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            actual, size = stream_copy(source, destination)
            if actual != digest:
                raise KitError(f"Fichier du kit altéré : {relative} (empreinte différente)")
            shutil.copystat(source, destination)
            os.chmod(destination, 0o755 if relative in executables else 0o644)
            copied += 1
            done += size
            if progress:
                progress(min(done, total), total)
        for relative, link_target in sorted(links.items()):
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(link_target, path)
        real = Path(os.path.realpath(target))
        outside = [relative for relative in links if not Path(os.path.realpath(target / relative)).is_relative_to(real)]
        if outside:
            raise KitError(f"Lien résolu hors de la copie : {outside[:5]}")
        dangling = [relative for relative in links if not os.path.exists(target / relative)]
        if dangling:
            raise KitError(f"Lien sans cible après copie : {dangling[:5]}")
        for name, data in ((SUMS, sums_data), (MANIFEST, manifest_data)):
            (target / name).write_bytes(data)
            os.chmod(target / name, 0o644)
        if stream_hash(target / SUMS) != reference:
            raise KitError("SHA256SUMS copié différent de la liste vérifiée")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    if progress:
        progress(total, total)
    return {"status": "copied", "files": copied, "links": len(links), "target": str(target)}


# --- Essai hors ligne (KIT4-27) ---------------------------------------------------------------------------------------

# Commande de l'installateur qui crée l'environnement isolé (linux_install.prepare_program) : seule l'absence d'une roue du
# cache uv la fait échouer hors ligne, ce que l'essai révèle avant la livraison.
OFFLINE_COMMAND = ("bootstrap.sh", "--offline", "--no-dev")
# Message d'uv 0.12.21 pour une distribution absente du cache, réseau désactivé (relevé du 07/10/2026) :
# « error: Failed to download `torch==2.14.0+cpu` ».
UV_MISSING = re.compile(r"Failed to (?:download|fetch|build) `([^`]+)`")


def offline_trial(kit: Path, *, work: Path | None = None, runner: Any = None, root: Path = ROOT) -> dict[str, Any]:
    """Copie vérifiée du kit dans un dossier temporaire hors du dépôt et du kit, préfixe de CPython réécrit, puis la commande
    de l'installateur `bootstrap.sh --offline --no-dev`, réseau coupé par `unshare -r -n` quand le noyau le permet. La copie
    est toujours retirée. Rapport : réussite, ou paquets absents du cache nommés."""
    import tempfile
    import time

    from tools.dist import linux_install

    kit = kit.resolve()
    manifest = json.loads((kit / MANIFEST).read_text(encoding="utf-8"))
    parent = Path(work if work is not None else tempfile.gettempdir()).resolve()
    if parent.is_relative_to(root.resolve()) or parent.is_relative_to(kit):
        raise KitError(f"Dossier d'essai {parent} refusé : il doit être hors du dépôt et du kit")
    needed = int(manifest["requirements"]["install_bytes_min"])
    free = shutil.disk_usage(parent).free
    if free < needed:
        raise KitError(f"Place insuffisante pour l'essai hors ligne dans {parent} : {free} octets libres, {needed} nécessaires "
                       "(copie du kit et environnement isolé) ; indiquer un autre dossier (--dossier-essai)")
    runner = runner or linux_install.SystemRunner()
    unshare = shutil.which("unshare", path="/usr/bin:/bin") or "unshare"
    isolated = runner.run([unshare, "-r", "-n", "true"], timeout=30).returncode == 0
    started = time.monotonic()
    folder = Path(tempfile.mkdtemp(prefix="atelier-essai-hors-ligne-", dir=parent))
    removed = False
    try:
        program = folder / "programme"
        install_copy(kit, program)
        try:
            linux_install.rewrite_python_prefix(program, manifest)
        except linux_install.InstallError as error:
            raise KitError(f"Préfixe de CPython non réécrit dans la copie d'essai : {error}") from error
        command = [str(program / OFFLINE_COMMAND[0]), *OFFLINE_COMMAND[1:]]
        completed = runner.run([unshare, "-r", "-n", *command] if isolated else command, cwd=program, timeout=3600)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        removed = not folder.exists()
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    return {"status": "passed" if completed.returncode == 0 else "failed", "mode": "offline-trial", "kit_id": manifest["kit_id"],
            "command": list(OFFLINE_COMMAND), "network_isolated": isolated, "returncode": completed.returncode,
            "missing_packages": list(dict.fromkeys(UV_MISSING.findall(output))), "output_tail": output[-1500:],
            "work_parent": str(parent), "work_removed": removed, "duration_s": round(time.monotonic() - started, 1)}


# --- Archive de transport --------------------------------------------------------------------------------------------

class HashingWriter:
    def __init__(self, stream: IO[bytes]):
        self.stream, self.digest, self.size = stream, hashlib.sha256(), 0

    def write(self, data: bytes) -> int:
        self.digest.update(data)
        self.size += len(data)
        return self.stream.write(data)


class HashingReader:
    def __init__(self, stream: IO[bytes]):
        self.stream, self.digest = stream, hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def archive_kit(folder: Path, output: Path) -> dict[str, Any]:
    """`<kit_id>.tar` (PAX, sans compression) d'un kit, vérifié pendant l'écriture, le guide `<kit_id>.LISEZMOI.md` à côté et
    `<kit_id>.tar.sha256` au format sha256sum : ligne de l'archive, puis ligne du guide. `output` : dossier existant, ou
    fichier nommé `<kit_id>.tar` (le guide cite ce nom). Rien n'est jamais remplacé."""
    folder, output = folder.resolve(), output.absolute()
    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    kit_id = manifest["kit_id"]
    if output.is_dir():
        output = output / f"{kit_id}.tar"
    if output.name != f"{kit_id}.tar":
        raise KitError(f"Archive : nommer le fichier {kit_id}.tar, nom que cite le guide, ou indiquer un dossier existant")
    guide_copy, checksum = output.with_name(f"{kit_id}.{GUIDE}"), output.with_name(output.name + ".sha256")
    if output.resolve().is_relative_to(folder) or any(path.exists() or path.is_symlink() for path in (output, guide_copy, checksum)):
        raise KitError(f"Archive : {output.name}, {guide_copy.name} et {checksum.name} doivent être neufs et hors du kit")
    expected = read_sums(folder)
    if GUIDE not in expected:
        raise KitError(f"Kit sans {GUIDE} : le refabriquer avec la version courante du fabricant")
    links, executables = declared(folder, expected)
    present = {path.relative_to(folder).as_posix() for path, _ in walk_tree(folder)}
    unexpected = sorted(present - set(expected) - set(links) - {SUMS, MANIFEST})
    if unexpected:
        raise KitError(f"Fichier hors SHA256SUMS dans le kit : {unexpected[:5]}")
    guide = (folder / GUIDE).read_bytes()
    if (folder / GUIDE).is_symlink() or hashlib.sha256(guide).hexdigest() != expected[GUIDE]:
        raise KitError(f"Fichier du kit altéré : {GUIDE}")
    created: list[Path] = []
    try:
        with output.open("xb") as stream:
            created.append(output)
            writer = HashingWriter(stream)
            with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as tar:  # type: ignore[call-overload]
                for relative in [*sorted(expected), SUMS, MANIFEST]:
                    path = folder / relative
                    if path.is_symlink():
                        raise KitError(f"Fichier remplacé par un lien : {relative}")
                    info = tarfile.TarInfo(f"{kit_id}/{relative}")
                    info.size, info.mtime = path.stat().st_size, int(path.stat().st_mtime)
                    info.mode = 0o755 if relative in executables or relative == INSTALLER else 0o644
                    with path.open("rb") as reader:
                        hashing = HashingReader(reader)
                        tar.addfile(info, hashing)  # type: ignore[arg-type]
                    if relative in expected and hashing.digest.hexdigest() != expected[relative]:
                        raise KitError(f"Fichier du kit altéré : {relative}")
                for relative, target in sorted(links.items()):
                    if not (folder / relative).is_symlink() or os.readlink(folder / relative) != target:
                        raise KitError(f"Lien du kit altéré : {relative}")
                    info = tarfile.TarInfo(f"{kit_id}/{relative}")
                    info.type, info.linkname, info.mode = tarfile.SYMTYPE, target, 0o777
                    tar.addfile(info)
        digest = writer.digest.hexdigest()
        with guide_copy.open("xb") as stream:
            created.append(guide_copy)
            stream.write(guide)
        with checksum.open("x", encoding="utf-8", newline="\n") as stream:
            created.append(checksum)
            stream.write(f"{digest}  {output.name}\n{expected[GUIDE]}  {guide_copy.name}\n")
    except BaseException:
        # Seuls les fichiers créés par cet appel sont retirés.
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {"status": "archived", "archive": str(output), "sha256": digest, "bytes": writer.size, "kit_id": kit_id,
            "files": len(expected) + 2, "links": len(links), "checksum": str(checksum), "guide": str(guide_copy)}


def archive_digest(checksum: Path, archive_name: str) -> str:
    """Empreinte de l'archive dans un fichier au format sha256sum : la ligne de son nom (« * » du mode binaire admis)."""
    for line in checksum.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match and match.group(2) == archive_name:
            return match.group(1)
    raise KitError(f"Empreinte de {archive_name} absente de {checksum.name} : la fournir avec --sha256")


def extract_kit(archive: Path, into: Path, *, sha256: str | None = None) -> dict[str, Any]:
    """Extraction contrôlée : empreinte de l'archive, un seul dossier racine, filtre `data` (aucun lien absolu ou sortant,
    ni fichier spécial), puis vérification complète du kit extrait avant de le publier sous son nom."""
    archive, into = archive.resolve(), into.absolute()
    checksum = archive.with_name(archive.name + ".sha256")
    if sha256 is None:
        if not checksum.is_file():
            raise KitError(f"Empreinte de l'archive introuvable ({checksum.name}) : la fournir avec --sha256")
        sha256 = archive_digest(checksum, archive.name)
    digest = hashlib.sha256()
    for block in read_blocks(archive):
        digest.update(block)
    if digest.hexdigest() != sha256.lower():
        raise KitError("Archive altérée : empreinte SHA-256 différente ; rien n'a été extrait")
    into.mkdir(parents=True, exist_ok=True)
    staging = into / f".extraction-{os.getpid()}"
    staging.mkdir()
    roots: set[str] = set()

    def guarded(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
        top = member.name.split("/", 1)[0]
        roots.add(top)
        if top in {"", ".", ".."} or len(roots) > 1 or ("/" not in member.name and not member.isdir()):
            raise KitError("Archive de kit inattendue : un seul dossier racine admis")
        if not (member.isfile() or member.issym() or member.isdir()):
            raise KitError(f"Membre refusé (ni fichier, ni lien symbolique, ni dossier) : {member.name}")
        return tarfile.data_filter(member, path)

    try:
        with tarfile.open(archive, mode="r|") as tar:
            tar.extractall(staging, filter=guarded)
        (kit_id,) = roots
        result = verify_kit(staging / kit_id)
        if result["status"] != "verified":
            raise KitError(f"Kit extrait non conforme : {json.dumps(result, ensure_ascii=False)[:600]}")
        final = into / kit_id
        if final.exists():
            raise KitError(f"{final} existe déjà : jamais remplacé")
        os.rename(staging / kit_id, final)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {"status": "extracted", "kit": str(final), "kit_id": kit_id, "verification": result}
