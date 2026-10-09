"""Kit hors ligne Linux (R26-KIT-01) : liste blanche, liens, marqueurs du poste, neutralisations, variantes, glibc,
intégrité, copie et archive, sur un dépôt Git factice et un `.runtime` factice sous TMPDIR.

Doubles nommés : `fake_readelf` remplace readelf (les ELF factices n'ont que leur en-tête) et rend la sortie réelle de
`readelf -V -d -W` du Tesseract du poste de référence ; `no_l4t_release` et `jetson_r35_release` (fixture `jetson_r35`)
simulent /etc/nv_tegra_release ; `no_host_library`, `ldconfig_double`, `no_package_owner` et `dpkg_query_double`
remplacent `ldconfig -p` et `dpkg-query -S` ; `plateforme_jetson` remplace la plateforme du poste de fabrication,
`DryRunPret` le dry-run, `which_present` et `which_absent` shutil.which, `essai_reussi` et `trial_double` l'essai hors
ligne ; `ReextractionPendantLaCopie` simule une ré-extraction du kit pendant la copie ; `droits_perdus` (bit x perdu au
transport) et `dedoublonne_par_lien` (fichier remplacé par un lien vers une copie identique) simulent les altérations
accidentelles que nomme le modèle de menace du guide. Les essais de bout en bout reprennent
`PosteSimule` et `ProgrammeSimule` des essais de l'installateur. Le dépôt Git factice est créé et committé dans le dossier
temporaire du test, jamais dans le dépôt du projet.
"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":
    pytest.skip("kit Linux : liens symboliques et bits d'exécution POSIX", allow_module_level=True)

from tools.dist import linux_kit  # noqa: E402

AARCH64 = 183
X86_64 = 62
# Sortie réelle de `readelf -V -d -W` sur .runtime/bin/tesseract-5.4.0/tesseract (Jetson, 06/10/2026), abrégée.
READELF_TESSERACT = """
Dynamic section at offset 0x5a6d78 contains 34 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libpthread.so.0]
 0x0000000000000001 (NEEDED)             Shared library: [libjpeg.so.8]
 0x0000000000000001 (NEEDED)             Shared library: [libpng16.so.16]
 0x0000000000000001 (NEEDED)             Shared library: [libz.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libtiff.so.5]
 0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [ld-linux-aarch64.so.1]

Version symbols section '.gnu.version' contains 912 entries:
 Addr: 0x0000000000003b88  Offset: 0x003b88  Link: 5 (.dynsym)
  000:   0 (*local*)       2 (GLIBC_2.17)    3 (PNG16_0)       4 (GLIBC_2.17)

Version needs section '.gnu.version_r' contains 9 entries:
 Addr: 0x00000000000044e8  Offset: 0x0044e8  Link: 6 (.dynstr)
  000000: Version: 1  File: ld-linux-aarch64.so.1  Cnt: 1
  0x0010:   Name: GLIBC_2.17  Flags: none  Version: 15
  0x0060: Version: 1  File: libm.so.6  Cnt: 3
  0x0070:   Name: GLIBC_2.27  Flags: none  Version: 21
  0x0080:   Name: GLIBC_2.29  Flags: none  Version: 19
  0x0090:   Name: GLIBC_2.17  Flags: none  Version: 9
  0x00a0: Version: 1  File: libtiff.so.5  Cnt: 1
  0x00b0:   Name: LIBTIFF_4.0  Flags: none  Version: 6
  0x00e0: Version: 1  File: libc.so.6  Cnt: 2
  0x00f0:   Name: GLIBC_2.22  Flags: none  Version: 26
  0x0100:   Name: GLIBC_2.17  Flags: none  Version: 4
  0x0130: Version: 1  File: libstdc++.so.6  Cnt: 3
  0x0140:   Name: GLIBCXX_3.4.20  Flags: none  Version: 25
  0x0150:   Name: CXXABI_1.3.8  Flags: none  Version: 24
  0x0190:   Name: GLIBCXX_3.4.26  Flags: none  Version: 18
"""
# Bibliothèque livrée qui définit ses propres versions (section .gnu.version_d, à ignorer) et en requiert d'autres.
READELF_BUNDLED = """
Dynamic section at offset 0x1000 contains 3 entries:
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000e (SONAME)             Library soname: [libgomp.so.1]

Version definition section '.gnu.version_d' contains 2 entries:
  000000: Rev: 1  Flags: BASE  Index: 1  Cnt: 1  Name: libgomp.so.1
  0x001c: Rev: 1  Flags: none  Index: 2  Cnt: 1  Name: GLIBC_9.99

Version needs section '.gnu.version_r' contains 1 entries:
  000000: Version: 1  File: libc.so.6  Cnt: 1
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 3
"""


def elf_header(machine: int) -> bytes:
    """En-tête ELF 64 bits petit-boutiste : e_machine à l'octet 18."""
    return b"\x7fELF\x02\x01\x01" + b"\x00" * 9 + b"\x02\x00" + machine.to_bytes(2, "little") + b"\x00" * 44


def write(root: Path, relative: str, content: bytes | str = b"x", *, executable: bool = False) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    if executable:
        path.chmod(0o755)
    return path


def link(root: Path, relative: str, target: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, path)
    return path


def git(root: Path, *args: str) -> str:
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root.parent), "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_AUTHOR_NAME": "Essai", "GIT_AUTHOR_EMAIL": "essai@example.invalid", "GIT_COMMITTER_NAME": "Essai",
                   "GIT_COMMITTER_EMAIL": "essai@example.invalid"}
    return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], cwd=root, env=environment,
                          check=True, capture_output=True, text=True).stdout


def digest(name: str) -> str:
    return "sha256:" + hashlib.sha256(name.encode()).hexdigest()


MODELS = {"qwen3.5:2b": ("2b", [("c2b", 5), ("w2b", 11)]), "qwen3.5:4b": ("4b", [("c4b", 6), ("w4b", 13)]),
          "qwen3.5:4b-text": ("4b-text", [("c4t", 7), ("w4t", 12)])}
# Profils livrés réels : les profils d'utilisateur des essais d'installation en dérivent comme sur un poste.
PROFILE_2B = (linux_kit.ROOT / "config/local16.yaml").read_text(encoding="utf-8")
PROFILE_4B = (linux_kit.ROOT / "config/local16-4b.yaml").read_text(encoding="utf-8")
INSTALL_SH = "#!/bin/sh\n# installateur factice du test\nexit 0\n"
PYTHON_KEY = "cpython-3.12.14-linux-aarch64-gnu"
# Modèle réel du guide ; documents factices qui portent les sections canoniques (KIT4-15) sous un numéro quelconque.
GUIDE_TEMPLATE = (linux_kit.ROOT / "tools/dist/templates/LISEZMOI-linux.md").read_text(encoding="utf-8")
CANONICAL_DOCUMENTS = {"docs/deploiement/DEPLOIEMENT.md": "# Déploiement\n\n## 1. Voies\n\n## 8. Kit hors ligne Linux\n\nProcédure.\n",
                       "docs/exploitation/EXPLOITATION.md": "# Exploitation\n\n## 11. Lanceur `atelier` et menu\n\nActions.\n",
                       "docs/exploitation/DEPANNAGE.md": ("# Dépannage\n\n## 10. Installateur et lanceur Linux\n\nMessages.\n\n"
                                                          "### 10.4 Lanceur\n\n#### Réparer un programme installé avec le seul kit "
                                                          "de sa version\n\nProcédure.\n"),
                       "docs/exploitation/SAUVEGARDE-RESTAURATION.md": "# Sauvegarde\n\n## 2. Sauvegarder\n\nCommandes.\n"}
def icon_source() -> str:
    from tools.dist import linux_install

    return linux_install.ICON_SOURCE


def make_repository(tmp_path: Path, *, machine: int = AARCH64) -> Path:
    """Dépôt Git factice committé, `.runtime` lien vers un autre dossier (comme sur le poste de référence)."""
    root = tmp_path / "depot"
    for relative, content in {"services/api/main.py": "VERSION = 'commit'\n", "services/runtime/profile_schema.py": "",
                              "config/local16.yaml": PROFILE_2B,
                              "config/local16-4b.yaml": PROFILE_4B, "pyproject.toml": '[project]\nname = "x"\nversion = "0.1.0"\n',
                              "bootstrap.sh": "#!/bin/sh\npython_key=cpython-3.12.14-linux-$machine-gnu\n", "rag.sh": "#!/bin/sh\n",
                              "uv.lock": "version = 1\n", "README.md": "# Atelier\n", "CHANGELOG.md": "# Journal\n",
                              "docs/index.md": "# Docs\n", "tools/corpus/x.py": "", "tools/dist/linux_install.py": "",
                              "tools/dist/linux_kit.py": "", "tools/dist/linux_profiles.py": "", "tools/dist/build_kit.py": "",
                              "tools/dist/notices.py": "", "tools/dist/install.ps1": "# Windows\n", "tools/dist/kit_guide.py": "",
                              "tools/dist/templates/LISEZMOI-linux.md": GUIDE_TEMPLATE, icon_source(): "<svg/>\n", **CANONICAL_DOCUMENTS,
                              "packages/contracts/contracts.json": "{}\n", "apps/web/package.json": "{}\n",
                              "apps/web/pnpm-lock.yaml": "lockfileVersion: 9\n", "tests/unit/test_x.py": "",
                              "RAG_Local_Agents/PLAN.md": "# Plan\n",
                              ".gitignore": "/.runtime\n.runtime/\napps/web/out/\n__pycache__/\n"}.items():
        write(root, relative, content, executable=relative.endswith(".sh"))
    write(root, "tools/dist/install.sh", INSTALL_SH, executable=True)
    lock_models: dict[str, dict[str, Any]] = {}
    for name, (tag, layers) in MODELS.items():
        manifest = json.dumps({"name": name}).encode()
        lock_models[name] = {"manifest_path": f"manifests/registry.ollama.ai/library/qwen3.5/{tag}",
                             "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                             "config": {"digest": digest(layers[0][0]), "size": layers[0][1]},
                             "layers": [{"digest": digest(label), "size": size} for label, size in layers[1:]]}
    write(root, "config/models.lock.json", json.dumps({"store": ".runtime/models/ollama", "models": lock_models}))
    write(root, "config/artifacts.lock.json", json.dumps({"groups": {"qdrant": [
        {"version": "1.19.1", "platform": "linux-aarch64", "publisher": "Qdrant", "license": "Apache-2.0",
         "url": "https://example.invalid/qdrant-aarch64.tar.gz", "extract_to": ".runtime/bin/qdrant-1.19.1"}]}}))
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    # Artefacts non suivis, dans un autre dossier relié par .runtime.
    runtime = tmp_path / "volume" / "runtime"
    runtime.mkdir(parents=True)
    os.symlink(runtime, root / ".runtime")
    real = os.path.realpath(runtime)
    write(root, ".runtime/bin/ollama-0.35.0/bin/ollama", elf_header(machine), executable=True)
    write(root, ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0.24.0", elf_header(machine))
    link(root, ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0", "libggml.so.0.24.0")
    for variant, name in (("cuda_v12", "libcudart.so.12.8.90"), ("cuda_v13", "libcudart.so.13.0.96"), ("cuda_jetpack5", "libcudart.so.11.4.298")):
        write(root, f".runtime/bin/ollama-0.35.0/lib/ollama/{variant}/{name}", elf_header(machine))
        link(root, f".runtime/bin/ollama-0.35.0/lib/ollama/{variant}/{name.rsplit('.', 2)[0]}", name)
    write(root, ".runtime/bin/qdrant-1.19.1/qdrant", elf_header(machine), executable=True)
    write(root, linux_kit.TESSERACT_BINARY, elf_header(machine), executable=True)
    write(root, ".runtime/bin/tesseract-5.4.0/LICENSE", "Apache")
    python = f".runtime/python/{PYTHON_KEY}"
    write(root, f"{python}/bin/python3.12", elf_header(machine), executable=True)
    link(root, f"{python}/bin/python3", "python3.12")
    link(root, f"{python}/share/terminfo/t/tty5410-w", "../a/att5410-w")
    write(root, f"{python}/share/terminfo/a/att5410-w", b"\x1a\x01")
    prefix = f"{real}/python/{PYTHON_KEY}"
    write(root, f"{python}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py",
          f"build_time_vars = {{'prefix': '{prefix}', 'LIBDIR': '{prefix}/lib', 'CC': 'cc'}}\n")
    write(root, f"{python}/lib/python3.12/os.py", "# stdlib\n")
    write(root, f"{python}/lib/python3.12/lib-dynload/_crypt.cpython-312-aarch64-linux-gnu.so", elf_header(machine))
    link(root, ".runtime/python/cpython-3.12-linux-aarch64-gnu", f"{real}/python/{PYTHON_KEY}")
    write(root, ".runtime/python/.lock", "")
    write(root, ".runtime/bootstrap/bin/uv", elf_header(machine), executable=True)
    write(root, ".runtime/cache/uv/archive-v0/AbC/pkg/__init__.py", "")
    write(root, ".runtime/cache/uv/archive-v0/AbC/pkg-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nTag: cp312-cp312-manylinux_2_28_aarch64\n")
    link(root, ".runtime/cache/uv/wheels-v6/pypi/pkg/1.0-py3-none-any", "../../../archive-v0/AbC")
    # Roues à bibliothèques : OpenCV (libGL du système) et torchvision, qui trouve libtorch dans torch une fois installé.
    write(root, ".runtime/cache/uv/archive-v0/CvX/cv2/cv2.abi3.so", elf_header(machine))
    write(root, ".runtime/cache/uv/archive-v0/CvX/opencv_python.libs/libavcodec-1a2b.so.61", elf_header(machine))
    write(root, ".runtime/cache/uv/archive-v0/TvX/torchvision/_C.so", elf_header(machine))
    write(root, ".runtime/cache/uv/archive-v0/ThX/torch/lib/libtorch.so", elf_header(machine))
    write(root, ".runtime/cache/uv/interpreter-v4/abc/info.msgpack", f"{prefix}/bin/python3.12")
    store = ".runtime/models/ollama"
    for name, entry in lock_models.items():
        write(root, f"{store}/{entry['manifest_path']}", json.dumps({"name": name}).encode())
        for layer in (entry["config"], *entry["layers"]):
            write(root, f"{store}/blobs/{layer['digest'].replace(':', '-')}", b"m" * layer["size"])
    write(root, f"{store}/metadata/{lock_models['qwen3.5:2b']['layers'][0]['digest'].replace(':', '-')}.json", "{}")
    write(root, f"{store}/blobs/sha256-{'0' * 64}", b"orphelin")
    write(root, ".runtime/models/qwen3.5-2b-tokenizer/tokenizer.json", "{}")
    write(root, ".runtime/models/qwen3.5-4b-tokenizer/tokenizer.json", "{}")
    write(root, ".runtime/models/granite-97m/model.onnx", "g")
    for name in ("ollama-model-2b.json", "ollama-model.json", "ollama-model-text.json", "artifacts.json"):
        write(root, f".runtime/manifests/{name}", "{}")
    write(root, ".runtime/manifests/ollama-discovery.json", '{"poste": "fabrication"}')
    write(root, linux_kit.TESSERACT_BUILT, json.dumps({
        "kind": "tesseract-source-build", "platform": "linux-aarch64", "sources": [{"name": "tesseract"}],
        "cmake_options": {"BUILD_SHARED_LIBS": "OFF"}, "binary": {"path": linux_kit.TESSERACT_BINARY, "sha256": "ab"},
        "files": [{"path": linux_kit.TESSERACT_BINARY}],
        "file_prefix_map": {"token": "@BUILD@", "flags": f"-ffile-prefix-map={root}/.runtime/build/t=. -ffile-prefix-map={real}/build/t=."},
        "build_environment": {"HOME": f"{root}/.runtime/build/t/home", "TMPDIR": f"{real}/build/t/tmp", "LANG": "C.UTF-8"},
        "steps": [{"name": "configure", "command": ["cmake", "-S", f"{real}/build/t/src", "-DX=1"]}]}, indent=2))
    write(root, ".runtime/data/app.sqlite3", "base")
    write(root, "apps/web/out/index.html", "<html></html>")
    write(root, "apps/web/out/_next/static/chunks/page.js", "console.log('ok')")
    web_provenance(root)
    return root


def web_provenance(root: Path, **changes) -> Path:
    """Preuve de provenance écrite par le build de l'interface : commit courant, sources propres, verrou pnpm du commit."""
    record = {"format": "atelier-web-provenance-v1", "commit": git(root, "rev-parse", "HEAD").strip(), "sources_modified": False,
              "modified_sources": [], "pnpm_lock_sha256": hashlib.sha256((root / "apps/web/pnpm-lock.yaml").read_bytes()).hexdigest(),
              "built_utc": "2026-10-07T00:00:00+00:00"}
    record.update(changes)
    return write(root, "apps/web/out/build-provenance.json", json.dumps(record, indent=2))


READELF_CV2 = """
 0x0000000000000001 (NEEDED)             Shared library: [libavcodec-1a2b.so.61]
 0x0000000000000001 (NEEDED)             Shared library: [libGL.so.1]
 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/../opencv_python.libs]
"""
# RUNPATH réel de torchvision 0.29 : chemin absolu de la machine de construction de la roue.
READELF_CRYPT = """
 0x0000000000000001 (NEEDED)             Shared library: [libcrypt.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
"""
READELF_TORCHVISION = """
 0x0000000000000001 (NEEDED)             Shared library: [libtorch.so]
 0x000000000000001d (RUNPATH)            Library runpath: [/__w/_temp/conda_environment_33057293334/lib]
"""


def fake_readelf(paths, batch=200):
    """Double de readelf : Tesseract rend la sortie réelle, les autres ELF des sorties de bibliothèques livrées."""
    infos = {}
    for path in paths:
        name = str(path)
        text = (READELF_TESSERACT if name.endswith("tesseract") else READELF_BUNDLED.replace("2.34", "2.17") if "libggml" in name
                else READELF_CV2 if name.endswith("cv2.abi3.so") else READELF_TORCHVISION if name.endswith("torchvision/_C.so")
                else READELF_CRYPT if name.endswith("_crypt.cpython-312-aarch64-linux-gnu.so") else None)
        if text:
            infos.update(linux_kit.parse_readelf(text, [name]))
    return infos


def no_host_library(soname):
    """Double de `ldconfig -p` : aucune bibliothèque connue du chargeur du poste de fabrication."""
    return None


def no_package_owner(path):
    """Double de `dpkg-query -S` : aucun paquet propriétaire."""
    return None


def no_l4t_release(path=None):
    """Double de la lecture de /etc/nv_tegra_release : poste sans Jetson Linux."""
    return None


def jetson_r35_release(path=None):
    """Double de la lecture de /etc/nv_tegra_release : Jetson Linux R35.4.1, comme le poste de référence."""
    return {"major": 35, "revision": "4.1", "line": "# R35 (release), REVISION: 4.1"}


def plateforme_jetson():
    """Double de linux_kit.host_platform : poste de fabrication Linux aarch64."""
    return "linux-aarch64"


class DryRunPret:
    """Double de linux_kit.dry_run : consigne les options reçues et rend le statut « ready » sans lire de dépôt."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, root, **options):
        self.calls.append(options)
        return {"status": "ready"}


def which_present(name, path=None):
    """Double de shutil.which : outil présent dans /usr/bin."""
    return f"/usr/bin/{name}"


def which_absent(name, path=None):
    """Double de shutil.which : outil absent du poste."""
    return None


def essai_reussi(folder, **options):
    """Double de linux_kit.offline_trial : essai hors ligne réussi, aucun paquet absent du cache."""
    return {"status": "passed", "missing_packages": []}


def prepare_repository(tmp_path: Path, monkeypatch) -> Path:
    """Préparation de la fixture `repository` : doubles du poste de fabrication, puis dépôt Git factice. Les constantes de
    tools/dist/linux_install.py (icône, noms, emplacements, codes de sortie) sont celles du module réel : aucun double ne les
    complète (QA3-06)."""
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", no_l4t_release)
    monkeypatch.setattr(linux_kit, "host_library_path", no_host_library)
    monkeypatch.setattr(linux_kit, "package_owner", no_package_owner)
    return make_repository(tmp_path)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    return prepare_repository(tmp_path, monkeypatch)


@pytest.fixture
def jetson_r35(monkeypatch):
    monkeypatch.setattr(linux_kit, "l4t_release", jetson_r35_release)


def build(repository: Path, tmp_path: Path, name: str = "kit", **options) -> tuple[Path, dict]:
    kit = tmp_path / name
    manifest = linux_kit.build_linux_kit(kit, repository, platform="linux-aarch64", home=str(tmp_path / "maison"), **options)
    return kit, manifest


# --- Liste blanche et contenu du commit -----------------------------------------------------------------------------------

def test_the_linux_whitelist_takes_the_commit_and_selected_artifacts_only(repository):
    write(repository, "services/api/main.py", "VERSION = 'modification locale'\n")
    write(repository, "services/api/nouveau.py", "")
    plan = linux_kit.plan_kit(repository, platform="linux-aarch64")
    names = set(plan.entries)
    assert {"services/api/main.py", "tools/dist/install.sh", "packages/contracts/contracts.json", "rag.sh", "bootstrap.sh",
            f".runtime/python/{PYTHON_KEY}/bin/python3.12", ".runtime/cache/uv/archive-v0/AbC/pkg/__init__.py",
            "apps/web/out/index.html"} <= names
    forbidden = [name for name in names if name.startswith(("tests/", "RAG_Local_Agents/", ".runtime/data/", "PDF/"))
                 or name.endswith(".ps1") or "interpreter-v4" in name or "granite" in name or "ollama-discovery" in name
                 or name in {".runtime/python/.lock", ".gitignore"}]
    assert forbidden == []
    assert plan.worktree_modified == ["services/api/main.py", "services/api/nouveau.py"]
    assert plan.kit_id == f"0.1.0+{plan.commit[:12]}-linux-aarch64-none-2b4b"
    assert plan.rebuilt_links == [".runtime/python/cpython-3.12-linux-aarch64-gnu"]


def test_the_kit_carries_the_committed_content_not_the_local_modification(repository, tmp_path):
    write(repository, "services/api/main.py", "VERSION = 'modification locale'\n")
    kit, manifest = build(repository, tmp_path)
    assert (kit / "services/api/main.py").read_text(encoding="utf-8") == "VERSION = 'commit'\n"
    assert manifest["tracked_source"]["worktree_modified_excluded"] == ["services/api/main.py"]
    assert manifest["format"] == "atelier-kit-v2" and manifest["kit_id"].startswith("0.1.0+")


@pytest.mark.parametrize(("gpu", "kept", "dropped"), [
    ("none", set(), {"cuda_v12", "cuda_v13", "cuda_jetpack5"}),
    ("jetpack5", {"cuda_jetpack5"}, {"cuda_v12", "cuda_v13"}),
])
def test_gpu_variants_ship_only_their_ollama_libraries(repository, jetson_r35, gpu, kept, dropped):
    plan = linux_kit.plan_kit(repository, platform="linux-aarch64", gpu=gpu)
    variants = {name.split("/lib/ollama/")[1].split("/")[0] for name in plan.entries if "/lib/ollama/cuda" in name}
    assert variants == kept and not variants & dropped
    assert ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0" in plan.entries
    assert plan.kit_id.endswith(f"-{gpu}-2b4b")


def test_jetpack5_is_refused_off_jetson_r35(repository):
    with pytest.raises(linux_kit.KitError, match="Jetson Linux R35"):
        linux_kit.plan_kit(repository, platform="linux-aarch64", gpu="jetpack5")


def test_models_4b_alone_drops_the_2b_blobs_manifest_and_tokenizer(repository):
    full = linux_kit.plan_kit(repository, platform="linux-aarch64")
    small = linux_kit.plan_kit(repository, platform="linux-aarch64", models=("4b",))
    dropped = set(full.entries) - set(small.entries)
    assert ".runtime/models/qwen3.5-2b-tokenizer/tokenizer.json" in dropped and ".runtime/manifests/ollama-model-2b.json" in dropped
    assert {f".runtime/models/ollama/blobs/{digest(label).replace(':', '-')}" for label in ("c2b", "w2b")} <= dropped
    assert {".runtime/manifests/ollama-model.json", ".runtime/manifests/ollama-model-text.json",
            ".runtime/models/qwen3.5-4b-tokenizer/tokenizer.json"} <= set(small.entries)
    assert [record["name"] for record in small.model_records] == ["qwen3.5:4b", "qwen3.5:4b-text"] and small.kit_id.endswith("-none-4b")
    assert [record["name"] for record in full.model_records] == ["qwen3.5:2b", "qwen3.5:4b", "qwen3.5:4b-text"]
    assert f".runtime/models/ollama/blobs/sha256-{'0' * 64}" not in full.entries
    assert full.excluded["magasin Ollama hors modèles choisis"] == 1


def test_the_default_kit_ships_both_models_and_requires_the_4b(repository):
    # W045 : le 4B est le modèle par défaut, présent dans tout kit ; le 2B suit par défaut pour garder le choix au lancement.
    assert linux_kit.DEFAULT_MODEL == "4b" and linux_kit.DEFAULT_MODELS == ("4b", "2b")
    assert linux_kit.plan_kit(repository, platform="linux-aarch64").models == ("2b", "4b")
    with pytest.raises(linux_kit.KitError) as refused:
        linux_kit.plan_kit(repository, platform="linux-aarch64", models=("2b",))
    assert str(refused.value) == ("Kit sans le modèle par défaut qwen3.5:4b refusé (W045) : --models 4b,2b (défaut, les deux modèles "
                                  "au choix du lancement) ou --models 4b. Un kit 2B seul n'est pas fabriqué.")
    assert linux_kit.plan_kit(repository, platform="linux-aarch64", models=("4b",)).models == ("4b",)


def test_an_altered_model_is_refused(repository):
    write(repository, ".runtime/models/ollama/manifests/registry.ollama.ai/library/qwen3.5/4b", "altéré")
    with pytest.raises(linux_kit.KitError, match="qwen3.5:4b absent ou différent du verrou"):
        linux_kit.plan_kit(repository, platform="linux-aarch64")


# --- Liens symboliques ------------------------------------------------------------------------------------------------

def test_internal_relative_links_are_kept_and_recreated_identically(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    for relative, target in ((".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0", "libggml.so.0.24.0"),
                             (f".runtime/python/{PYTHON_KEY}/bin/python3", "python3.12"),
                             (f".runtime/python/{PYTHON_KEY}/share/terminfo/t/tty5410-w", "../a/att5410-w"),
                             (".runtime/cache/uv/wheels-v6/pypi/pkg/1.0-py3-none-any", "../../../archive-v0/AbC")):
        assert (kit / relative).is_symlink() and os.readlink(kit / relative) == target
        assert f"{relative}\t{target}\n" in (kit / "SYMLINKS").read_text(encoding="utf-8")
    assert not (kit / ".runtime/python/cpython-3.12-linux-aarch64-gnu").exists()
    assert manifest["excluded"]["links_rebuilt_by_tools"] == [".runtime/python/cpython-3.12-linux-aarch64-gnu"]
    sums = (kit / "SHA256SUMS").read_text(encoding="utf-8")
    assert "  SYMLINKS\n" in sums and "  EXECUTABLES\n" in sums
    assert manifest["symlinks_sha256"] == hashlib.sha256((kit / "SYMLINKS").read_bytes()).hexdigest()


@pytest.mark.parametrize(("relative", "target", "message"), [
    (".runtime/bin/ollama-0.35.0/lib/ollama/libsys.so", "/usr/lib/libsys.so", "absolu ou hors du kit"),
    (".runtime/models/e5/model.onnx", "../../../../ailleurs/model.onnx", "absolu ou hors du kit"),
    (".runtime/bin/ollama-0.35.0/lib/ollama/libabsent.so", "libabsent.so.1", "cible absente du kit"),
])
def test_absolute_outgoing_or_dangling_links_stop_the_build(repository, relative, target, message):
    link(repository, relative, target)
    with pytest.raises(linux_kit.KitError, match=message):
        linux_kit.plan_kit(repository, platform="linux-aarch64")


# --- Marqueurs du poste et neutralisations -------------------------------------------------------------------------------

def test_markers_name_the_root_the_real_targets_of_runtime_links_and_home(repository, tmp_path):
    markers = linux_kit.host_markers(repository, str(tmp_path / "maison"))
    assert str(repository) in markers and os.path.realpath(tmp_path / "volume/runtime") in markers
    assert str(tmp_path / "maison") in markers


@pytest.mark.parametrize(("relative", "content"), [
    ("apps/web/out/_next/static/chunks/aabb.js", "import('file://{runtime}/qa/x/node_modules/pdfjs-dist/build/pdf.mjs')"),
    (".runtime/manifests/ollama-model-2b.json", '{{"chemin": "{home}/notes"}}'),
    (".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0.24.0", "\x00\x01 binaire {root}/.runtime/build"),
])
def test_a_build_host_path_in_any_copied_file_stops_the_build_and_leaves_nothing(repository, tmp_path, relative, content):
    text = content.format(runtime=os.path.realpath(tmp_path / "volume/runtime"), home=tmp_path / "maison", root=repository)
    write(repository, relative, text.encode())
    with pytest.raises(linux_kit.KitError, match="Chemin du poste de fabrication présent dans le kit"):
        build(repository, tmp_path)
    assert not (tmp_path / "kit").exists()
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "leaks" and list(report["leaks"]) == [relative]


def test_markers_split_across_two_blocks_are_found():
    marker = b"/media/poste/runtime"
    assert linux_kit.scan_markers([b"debut " + marker[:7], marker[7:] + b" fin"], [marker]) == {marker}
    assert linux_kit.scan_markers([b"/media/po", b"ste"], [marker]) == set()


def test_only_declared_fields_are_neutralized_and_the_python_prefix_becomes_a_token(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    built = json.loads((kit / linux_kit.TESSERACT_BUILT).read_text(encoding="utf-8"))
    source = json.loads((repository / linux_kit.TESSERACT_BUILT).read_text(encoding="utf-8"))
    for key in ("kind", "platform", "sources", "cmake_options", "binary", "files"):
        assert built[key] == source[key]
    assert built["file_prefix_map"]["flags"] == "-ffile-prefix-map=<poste de fabrication>/.runtime/build/t=. -ffile-prefix-map=<poste de fabrication>/build/t=."
    assert built["build_environment"]["LANG"] == "C.UTF-8" and built["steps"][0]["command"][2] == "<poste de fabrication>/build/t/src"
    sysconfig = (kit / f".runtime/python/{PYTHON_KEY}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py").read_text(encoding="utf-8")
    assert sysconfig == "build_time_vars = {'prefix': '@ATELIER_PYTHON_PREFIX@', 'LIBDIR': '@ATELIER_PYTHON_PREFIX@/lib', 'CC': 'cc'}\n"
    records = {item["path"]: item for item in manifest["neutralizations"]}
    assert records[linux_kit.TESSERACT_BUILT]["fields"] == ["file_prefix_map.flags", "build_environment.HOME", "build_environment.TMPDIR",
                                                           "steps[0].command"]
    python = records[f".runtime/python/{PYTHON_KEY}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py"]
    assert python["rewrite_at_install"] is True and python["replacements"] == 2
    leaked = [path for path in kit.rglob("*") if path.is_file() and not path.is_symlink()
              and os.path.realpath(tmp_path / "volume/runtime").encode() in path.read_bytes()]
    assert leaked == []


def test_the_verification_of_the_tesseract_build_reads_none_of_the_neutralized_fields():
    # verify_built_copy (provisioning.py) ne lit que kind, platform, sources, cmake_options, binary et files.
    import inspect

    from services.runtime.provisioning import verify_built_copy

    code = inspect.getsource(verify_built_copy)
    for name in ("file_prefix_map", "build_environment", "steps"):
        assert name not in code


# --- Exigences du poste cible ---------------------------------------------------------------------------------------------

def test_glibc_and_libstdcxx_minimums_come_from_the_version_needs_of_shipped_elf():
    infos = linux_kit.parse_readelf(READELF_TESSERACT, ["tesseract"])
    infos.update(linux_kit.parse_readelf(READELF_BUNDLED, ["libgomp.so.1.0.0"]))
    tesseract = infos["tesseract"]
    assert tesseract.glibc == {"2.17", "2.22", "2.27", "2.29"} and tesseract.glibcxx == {"3.4.20", "3.4.26"}
    assert "libjpeg.so.8" in tesseract.needed and infos["libgomp.so.1.0.0"].soname == "libgomp.so.1"
    # Un libjpeg.so.8 livré ailleurs dans le kit (roue) n'est pas sur le chemin du chargeur de Tesseract.
    present = {"bin/tesseract", "cache/roue.libs/libjpeg.so.8", "lib/libgomp.so.1.0.0", "lib/libgomp.so.1"}
    needs = linux_kit.system_requirements({"tesseract": tesseract}, {"tesseract": "bin/tesseract"}, present)
    assert needs["glibc_min"] == "2.29" and needs["glibcxx_min"] == "3.4.26"
    assert {"libjpeg.so.8", "libpng16.so.16", "libtiff.so.5", "libz.so.1", "libstdc++.so.6", "libc.so.6"} <= set(needs["system_libraries"])
    assert needs["system_libraries_required_by"]["libjpeg.so.8"] == ["bin/tesseract"]
    # Une définition de version (.gnu.version_d) n'est pas une exigence ; la bibliothèque livrée requiert GLIBC_2.34.
    with_bundled = linux_kit.system_requirements(infos, {"tesseract": "bin/tesseract", "libgomp.so.1.0.0": "lib/libgomp.so.1.0.0"}, present)
    assert with_bundled["glibc_min"] == "2.34"


def test_libraries_found_through_origin_runpath_or_the_elf_folder_are_provided_by_the_kit():
    text = """
 0x0000000000000001 (NEEDED)             Shared library: [libggml.so.0]
 0x0000000000000001 (NEEDED)             Shared library: [$ORIGIN/../lib/libpython3.12.so.1.0]
 0x0000000000000001 (NEEDED)             Shared library: [libroue-1a2b.so]
 0x0000000000000001 (NEEDED)             Shared library: [libcuda.so.1]
 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/../roue.libs:/usr/local/cuda/lib64]
"""
    info = linux_kit.parse_readelf(text, ["/k/bin/llama-server"])["/k/bin/llama-server"]
    assert info.runpath == ["$ORIGIN/../roue.libs", "/usr/local/cuda/lib64"]
    present = {"bin/llama-server", "bin/libggml.so.0", "lib/libpython3.12.so.1.0", "roue.libs/libroue-1a2b.so"}
    needs = linux_kit.system_requirements({"/k/bin/llama-server": info}, {"/k/bin/llama-server": "bin/llama-server"}, present)
    assert needs["system_libraries"] == ["libcuda.so.1"]


def test_multi_file_readelf_output_is_split_by_file_header():
    text = f"\nFile: /k/tesseract\n{READELF_TESSERACT}\nFile: /k/libgomp.so.1.0.0\n{READELF_BUNDLED}"
    infos = linux_kit.parse_readelf(text, ["/k/tesseract", "/k/libgomp.so.1.0.0"])
    assert max(infos["/k/tesseract"].glibc, key=linux_kit.version_tuple) == "2.29"
    assert infos["/k/libgomp.so.1.0.0"].glibc == {"2.34"}


def test_manylinux_tags_give_the_wheel_floor():
    tags = ["cp312-cp312-manylinux_2_28_aarch64", "py3-none-any", "cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64",
            "cp312-cp312-manylinux_2_34_x86_64"]
    assert linux_kit.manylinux_floor(tags, "aarch64") == "2.28"
    assert linux_kit.manylinux_floor(["py3-none-any"], "aarch64") is None


def test_the_manifest_declares_target_requirements_provenance_and_notices(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    target = manifest["target"]
    assert target["arch"] == "aarch64" and target["glibc_min"] == "2.29" and target["glibcxx_min"] == "3.4.26"
    assert target["glibc_min_sources"] == {"elf_version_needs": "2.29", "wheel_manylinux_tags": "2.28"}
    assert "libjpeg.so.8" in target["tesseract_system_libraries"] and target["kernel_min"] == "5.3"
    assert target["system_libraries_required_by"]["libjpeg.so.8"] == [linux_kit.TESSERACT_BINARY]
    # libGL du système pour OpenCV ; libavcodec (même roue) et libtorch (roue torch) sont fournis par le kit.
    assert target["system_libraries_required_by"]["libGL.so.1"] == ["site-packages/cv2/cv2.abi3.so"]
    assert "libtorch.so" not in target["system_libraries"] and "libavcodec-1a2b.so.61" not in target["system_libraries"]
    assert target["ldd_checks"] == [".runtime/bin/tesseract-5.4.0/tesseract", ".runtime/cache/uv/archive-v0/CvX/cv2/cv2.abi3.so"]
    assert "libggml.so.0" not in target["system_libraries"]
    assert manifest["python"]["executable"] == f".runtime/python/{PYTHON_KEY}/bin/python3.12"
    assert set(manifest["provenance"]) == {"config/artifacts.lock.json", "config/models.lock.json", "uv.lock", ".runtime/manifests/artifacts.json"}
    assert manifest["model_profiles"] == {"qwen3.5:2b": "config/local16.yaml", "qwen3.5:4b": "config/local16-4b.yaml"}
    # Étiquette de sélection du 4B, celle que --model (rag.sh) et --modele (atelier) acceptent, pas le modèle servi.
    assert manifest["default_model"] == "qwen3.5:4b" and manifest["model_sets"] == ["2b", "4b"]
    assert target["tesseract"] == linux_kit.TESSERACT_BINARY
    assert manifest["requirements"]["install_bytes_min"] == manifest["bytes"] + 3 * 1024**3
    notices = (kit / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "texte de licence d'uv absent" in notices and "| qdrant | 1.19.1 |" in notices and "JetPack 5" not in notices
    assert (kit / "installer.sh").read_text(encoding="utf-8") == INSTALL_SH and os.access(kit / "installer.sh", os.X_OK)


def test_a_4b_kit_declares_only_the_4b_profile_as_default(repository, tmp_path):
    kit, manifest = build(repository, tmp_path, models=("4b",))
    assert manifest["default_model"] == "qwen3.5:4b" and manifest["model_profiles"] == {"qwen3.5:4b": "config/local16-4b.yaml"}
    assert manifest["model_sets"] == ["4b"] and manifest["kit_id"].endswith("-none-4b")
    assert not (kit / ".runtime/manifests/ollama-model-2b.json").exists() and (kit / "config/local16.yaml").is_file()


# --- Ports des profils livrés (KIT4-05, REL-U01, QA-03) ------------------------------------------------------------------

def committed_ports(repository: Path, path: str) -> dict[str, int]:
    """Oracle : ports d'un profil du commit, lus comme init-profile les lit (services/runtime/profile_setup.user_profile)."""
    import yaml

    profile = yaml.safe_load(git(repository, "show", f"HEAD:{path}"))
    return {"app": int(profile["app"]["port"]), "qdrant": int(profile["qdrant"]["url"].rsplit(":", 1)[1].rstrip("/")),
            "ollama": int(profile["llm"]["base_url"].rsplit(":", 1)[1].rstrip("/"))}


def commit_profile(repository: Path, path: str, *replacements: tuple[str, str]) -> None:
    """Profil du commit modifié puis committé : le kit livre le commit, jamais l'arbre de travail."""
    text = (repository / path).read_text(encoding="utf-8")
    for before, after in replacements:
        assert before in text, before
        text = text.replace(before, after)
    write(repository, path, text)
    git(repository, "commit", "-q", "-am", f"ports de {path}")
    web_provenance(repository)


def test_the_manifest_carries_the_ports_of_each_delivered_profile(repository, tmp_path):
    # L'installateur, bibliothèque standard seule, ne lit pas le YAML : il contrôle avant toute écriture les ports que le
    # fabricant écrit ici, par étiquette de modèle livré.
    _, manifest = build(repository, tmp_path)
    assert manifest["profile_ports"] == {label: committed_ports(repository, path) for label, path in manifest["model_profiles"].items()}
    assert manifest["profile_ports"]["qwen3.5:4b"] == {"app": 8785, "qdrant": 6333, "ollama": 11434}
    # Les valeurs suivent le profil du commit, jamais une constante du fabricant.
    commit_profile(repository, "config/local16.yaml", ("  port: 8785", "  port: 18785"),
                   ("url: http://127.0.0.1:6333", "url: http://127.0.0.1:16333/"), ("base_url: http://127.0.0.1:11434", "base_url: http://127.0.0.1:21434"))
    _, changed = build(repository, tmp_path, "kit-ports")
    assert changed["profile_ports"]["qwen3.5:2b"] == {"app": 18785, "qdrant": 16333, "ollama": 21434} == committed_ports(repository, "config/local16.yaml")
    assert changed["profile_ports"]["qwen3.5:4b"] == manifest["profile_ports"]["qwen3.5:4b"]
    # Kit 4B seul : seuls les ports du profil livré.
    _, single = build(repository, tmp_path, "kit-4b", models=("4b",))
    assert single["profile_ports"] == {"qwen3.5:4b": committed_ports(repository, "config/local16-4b.yaml")}
    # Le dry-run annonce les mêmes ports.
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["profile_ports"] == changed["profile_ports"]


def test_a_delivered_profile_without_an_explicit_port_is_refused_before_any_copy(repository, tmp_path):
    # init-profile et le superviseur exigent un port explicite : le fabricant le refuse dès la liste du kit.
    commit_profile(repository, "config/local16.yaml", ("url: http://127.0.0.1:6333", "url: http://127.0.0.1"))
    with pytest.raises(linux_kit.KitError, match=r"config/local16\.yaml : port de qdrant\.url absent ou invalide"):
        build(repository, tmp_path)
    assert not (tmp_path / "kit").exists()


def test_build_kit_models_option_defaults_to_both_and_refuses_the_2b_alone(repository, monkeypatch, capsys, tmp_path):
    from tools.dist import build_kit

    monkeypatch.setattr(linux_kit, "host_platform", plateforme_jetson)
    real_dry_run, dry_run = linux_kit.dry_run, DryRunPret()
    monkeypatch.setattr(linux_kit, "dry_run", dry_run)
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--dry-run"])
    assert build_kit.main() == 0 and dry_run.calls[-1]["models"] == ("4b", "2b")
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--dry-run", "--models", "4b"])
    assert build_kit.main() == 0 and dry_run.calls[-1]["models"] == ("4b",)
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--dry-run", "--models", "9b"])
    assert build_kit.main() == 1 and "--models : 4b,2b (défaut) ou 4b" in capsys.readouterr().out
    # Refus réel de plan_kit, sur le dépôt factice, avant toute lecture du commit.
    monkeypatch.setattr(linux_kit, "dry_run", real_dry_run)
    # main rend ROOT importable pour son processus CLI. Ici, le ROOT factice ne doit pas rester dans les recherches
    # d'import de pytest : une recherche ultérieure chargerait son linux_profiles.py vide et le garderait en sys.modules.
    original_path = sys.path
    with monkeypatch.context() as cli_process:
        cli_process.setattr(sys, "path", list(original_path))
        cli_process.setattr(build_kit, "ROOT", repository)
        cli_process.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--dry-run", "--models", "2b"])
        capsys.readouterr()
        assert build_kit.main() == 1
        assert "Kit sans le modèle par défaut qwen3.5:4b refusé (W045)" in capsys.readouterr().out
    assert sys.path is original_path and str(repository) not in sys.path
    help_text = build_kit_help(capsys, monkeypatch)
    assert "4b,2b (défaut) ou 4b" in help_text


def build_kit_help(capsys, monkeypatch) -> str:
    from tools.dist import build_kit

    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--help"])
    with pytest.raises(SystemExit):
        build_kit.main()
    return " ".join(capsys.readouterr().out.split())


def test_a_binary_of_another_architecture_refuses_a_cross_kit(repository, tmp_path):
    write(repository, ".runtime/bin/ollama-0.35.0/bin/ollama", elf_header(X86_64), executable=True)
    with pytest.raises(linux_kit.KitError, match="jamais de kit croisé"):
        build(repository, tmp_path)


def test_build_kit_refuses_a_platform_other_than_the_build_host(monkeypatch, capsys, tmp_path):
    from tools.dist import build_kit

    monkeypatch.setattr(linux_kit, "host_platform", plateforme_jetson)
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-x86_64", "--output", str(tmp_path / "kit")])
    assert build_kit.main() == 1
    assert "un kit se fabrique sur un poste de sa plateforme" in capsys.readouterr().out and not (tmp_path / "kit").exists()
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--without-gpu", "--dry-run"])
    assert build_kit.main() == 1 and "--gpu none" in capsys.readouterr().out


@pytest.mark.parametrize("component", ["tools/dist/linux_install.py", "services/runtime/profile_schema.py"])
def test_a_commit_without_a_required_runtime_component_cannot_be_built(repository, tmp_path, component):
    git(repository, "rm", "-q", component)
    git(repository, "commit", "-q", "-m", "sans composant requis")
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete" and report["missing_for_build"] == [component]
    with pytest.raises(linux_kit.KitError, match="committer ces fichiers"):
        build(repository, tmp_path)


def test_dry_run_lists_without_copying(repository, tmp_path):
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "ready" and report["files"] > 30 and report["symlinks"] == 4
    assert report["target"]["glibc_min"] == "2.29" and report["bytes_by_group"]["models/ollama"] > 0
    assert not (tmp_path / "kit").exists()


# --- Intégrité, copie et archive ---------------------------------------------------------------------------------------

def test_verify_detects_altered_missing_extra_links_and_lost_executable_bits(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    assert linux_kit.verify_kit(kit)["status"] == "verified"
    libggml = kit / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0"
    libggml.unlink()
    os.symlink("libggml.so.0.24.0.autre", libggml)
    (kit / f".runtime/python/{PYTHON_KEY}/bin/python3").unlink()
    os.symlink("libggml.so.0.24.0", kit / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so")
    (kit / ".runtime/bin/qdrant-1.19.1/qdrant").chmod(0o644)
    report = linux_kit.verify_kit(kit)
    assert report["status"] == "failed"
    assert report["links_altered_or_missing"] == [".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0", f".runtime/python/{PYTHON_KEY}/bin/python3"]
    assert report["unexpected"] == [".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so"]
    assert report["executable_bit_missing"] == [".runtime/bin/qdrant-1.19.1/qdrant"]


def test_install_copy_recreates_links_and_modes_and_removes_a_partial_copy(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    result = linux_kit.install_copy(kit, tmp_path / "programme")
    program = tmp_path / "programme"
    assert result["status"] == "copied" and result["links"] == 4
    assert os.readlink(program / ".runtime/cache/uv/wheels-v6/pypi/pkg/1.0-py3-none-any") == "../../../archive-v0/AbC"
    assert (program / ".runtime/cache/uv/wheels-v6/pypi/pkg/1.0-py3-none-any/pkg/__init__.py").is_file()
    assert os.access(program / linux_kit.TESSERACT_BINARY, os.X_OK) and not os.access(program / "README.md", os.X_OK)
    assert linux_kit.verify_kit(program)["status"] == "verified"
    with pytest.raises(linux_kit.KitError, match="jamais remplacée"):
        linux_kit.install_copy(kit, program)
    write(kit, "services/api/main.py", "altéré")
    with pytest.raises(linux_kit.KitError, match="altéré : services/api/main.py"):
        linux_kit.install_copy(kit, tmp_path / "autre")
    assert not (tmp_path / "autre").exists()


def test_install_copy_refuses_a_kit_whose_link_list_was_altered(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    with (kit / "SYMLINKS").open("a", encoding="utf-8") as stream:
        stream.write("services/evasion\t/etc\n")
    with pytest.raises(linux_kit.KitError, match="SYMLINKS différent de SHA256SUMS"):
        linux_kit.install_copy(kit, tmp_path / "programme")
    assert not (tmp_path / "programme").exists()


def droits_perdus(kit: Path) -> None:
    """Double nommé : tous les fichiers du kit passent en 0644, comme après un transport qui perd le bit x."""
    for path in kit.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o644)


def dedoublonne_par_lien(kit: Path, relative: str, elsewhere: Path) -> None:
    """Double nommé : le fichier `relative` du kit devient un lien vers une copie identique hors du kit, comme une déduplication
    par liens symboliques ou une ferme de liens ; aucun octet ne change."""
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kit / relative, elsewhere)
    (kit / relative).unlink()
    os.symlink(elsewhere, kit / relative)


def test_install_copy_handles_the_accidental_alterations_named_by_the_guide(repository, tmp_path):
    # Modèle de menace du guide (« Vérifier et extraire l'archive ») : la copie vérifiée rétablit les droits perdus (bit x pris
    # dans EXECUTABLES), ne copie pas un fichier ajouté par erreur, refuse un fichier remplacé par un lien vers une copie
    # identique (déduplication ou ferme de liens) en le nommant pour ce qu'il est, et un fichier absent (copie ou transport
    # incomplets) ; chaque refus retire la copie partielle.
    kit, _ = build(repository, tmp_path)
    droits_perdus(kit)
    write(kit, "notes-ajoutees.txt", "ajouté par erreur")
    program = tmp_path / "programme"
    linux_kit.install_copy(kit, program)
    assert os.access(program / linux_kit.TESSERACT_BINARY, os.X_OK) and os.access(program / "installer.sh", os.X_OK)
    assert not (program / "notes-ajoutees.txt").exists() and linux_kit.verify_kit(program)["status"] == "verified"
    relative = "services/api/main.py"
    dedoublonne_par_lien(kit, relative, tmp_path / "ailleurs/main.py")
    with pytest.raises(linux_kit.KitError) as refused:
        linux_kit.install_copy(kit, tmp_path / "lien")
    assert str(refused.value) == f"Fichier du kit remplacé par un lien : {relative} (déduplication ou ferme de liens)"
    assert not (tmp_path / "lien").exists()
    (kit / relative).unlink()
    with pytest.raises(linux_kit.KitError) as refused:
        linux_kit.install_copy(kit, tmp_path / "incomplet")
    assert str(refused.value) == f"Fichier du kit absent : {relative}"
    assert not (tmp_path / "incomplet").exists()


# --- Copie liée à la liste vérifiée (S14) ----------------------------------------------------------------------------------

def substitute(kit: Path, relative: str, content: bytes, *, manifest: bool) -> str:
    """Fichier remplacé et SHA256SUMS réécrit en conséquence (kit cohérent avec sa nouvelle liste) ; avec `manifest`, le
    manifeste suit aussi, comme après une ré-extraction d'un autre kit. Rend l'empreinte de la nouvelle liste."""
    write(kit, relative, content)
    return relist(kit, relative, content, manifest=manifest)


def relist(kit: Path, relative: str, content: bytes, *, manifest: bool) -> str:
    """SHA256SUMS (et, avec `manifest`, son empreinte au manifeste) réécrit comme si `relative` valait `content`."""
    lines = [(f"{hashlib.sha256(content).hexdigest()}  {relative}" if line.endswith(f"  {relative}") else line)
             for line in (kit / "SHA256SUMS").read_text(encoding="utf-8").splitlines()]
    data = ("\n".join(lines) + "\n").encode()
    (kit / "SHA256SUMS").write_bytes(data)
    if manifest:
        record = json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))
        record["sha256sums_sha256"] = hashlib.sha256(data).hexdigest()
        (kit / "kit-manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(data).hexdigest()


def test_install_copy_refuses_a_sha256sums_that_differs_from_the_manifest(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    substitute(kit, "services/api/main.py", b"VERSION = 'substituee'\n", manifest=False)
    with pytest.raises(linux_kit.KitError, match="SHA256SUMS différent du manifeste"):
        linux_kit.install_copy(kit, tmp_path / "programme")
    assert not (tmp_path / "programme").exists()


def test_install_copy_holds_to_the_list_verified_by_the_caller(repository, tmp_path):
    # Ré-extraction d'un autre kit, cohérent, entre la vérification de l'installateur et la copie : la copie suit
    # l'empreinte que l'appelant a vérifiée, pas le manifeste relu.
    kit, manifest = build(repository, tmp_path)
    verified = manifest["sha256sums_sha256"]
    substitute(kit, "services/api/main.py", b"VERSION = 'autre kit'\n", manifest=True)
    with pytest.raises(linux_kit.KitError, match="kit-manifest.json a changé depuis sa vérification"):
        linux_kit.install_copy(kit, tmp_path / "programme", sums_sha256=verified)
    assert not (tmp_path / "programme").exists()


class ReextractionPendantLaCopie:
    """Double du rappel `progress` : au premier fichier copié, remplace dans le dossier du kit SHA256SUMS et le manifeste par
    ceux d'un autre kit, comme une ré-extraction concurrente pendant la copie ; les fichiers copiés ne changent pas."""

    def __init__(self, kit: Path):
        self.kit, self.calls = kit, 0

    def __call__(self, done: int, total: int) -> None:
        self.calls += 1
        if self.calls == 1:
            relist(self.kit, "README.md", b"# Autre kit\n", manifest=True)


def test_the_copied_control_files_are_the_verified_ones(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    sums, manifest = (kit / "SHA256SUMS").read_bytes(), (kit / "kit-manifest.json").read_bytes()
    double = ReextractionPendantLaCopie(kit)
    linux_kit.install_copy(kit, tmp_path / "programme", progress=double)
    program = tmp_path / "programme"
    assert double.calls > 1 and (kit / "SHA256SUMS").read_bytes() != sums
    # SHA256SUMS et manifeste du programme : ceux contre lesquels chaque fichier a été vérifié.
    assert (program / "SHA256SUMS").read_bytes() == sums and (program / "kit-manifest.json").read_bytes() == manifest
    assert linux_kit.verify_kit(program)["status"] == "verified"


def test_archive_and_controlled_extraction_round_trip(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    (tmp_path / "transport").mkdir()
    tar = tmp_path / "transport" / f"{manifest['kit_id']}.tar"
    archive = linux_kit.archive_kit(kit, tar)
    assert archive["status"] == "archived" and archive["archive"] == str(tar)
    assert tar.with_name(tar.name + ".sha256").read_text(encoding="utf-8").startswith(archive["sha256"])
    result = linux_kit.extract_kit(tar, tmp_path / "poste")
    assert result["status"] == "extracted" and result["kit"] == str(tmp_path / "poste" / manifest["kit_id"])
    extracted = Path(result["kit"])
    assert os.readlink(extracted / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0") == "libggml.so.0.24.0"
    assert os.access(extracted / "installer.sh", os.X_OK)
    with pytest.raises(linux_kit.KitError, match="existe déjà"):
        linux_kit.extract_kit(tar, tmp_path / "poste")
    assert [path.name for path in (tmp_path / "poste").iterdir()] == [manifest["kit_id"]]


def test_a_tampered_archive_is_refused_before_extraction(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    (tmp_path / "transport").mkdir()
    tar = Path(linux_kit.archive_kit(kit, tmp_path / "transport")["archive"])
    with tar.open("r+b") as stream:
        stream.seek(2000)
        stream.write(b"!")
    with pytest.raises(linux_kit.KitError, match="Archive altérée"):
        linux_kit.extract_kit(tar, tmp_path / "poste")
    assert not (tmp_path / "poste").exists()


@pytest.mark.parametrize(("name", "linkname", "message"), [
    ("kit/evasion", "/etc/passwd", "absolute|Absolute"),
    ("kit/evasion", "../../outside", "outside|Outside"),
    ("autre/fichier", None, "un seul dossier racine"),
])
def test_extraction_refuses_absolute_or_outgoing_links_and_a_second_root(tmp_path, name, linkname, message):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        first = tarfile.TarInfo("kit/fichier")
        first.size = 1
        tar.addfile(first, io.BytesIO(b"x"))
        member = tarfile.TarInfo(name)
        if linkname:
            member.type, member.linkname = tarfile.SYMTYPE, linkname
            tar.addfile(member)
        else:
            member.size = 1
            tar.addfile(member, io.BytesIO(b"y"))
    archive = tmp_path / "piege.tar"
    archive.write_bytes(buffer.getvalue())
    with pytest.raises((linux_kit.KitError, tarfile.FilterError), match=message):
        linux_kit.extract_kit(archive, tmp_path / "poste", sha256=hashlib.sha256(buffer.getvalue()).hexdigest())
    assert list((tmp_path / "poste").iterdir()) == []


def test_build_kit_dispatches_verify_and_install_copy_by_kit_format(repository, tmp_path, monkeypatch, capsys):
    from tools.dist import build_kit

    kit, _ = build(repository, tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_kit", "verify", "--kit", str(kit)])
    assert build_kit.main() == 0 and json.loads(capsys.readouterr().out)["links"] == 4
    monkeypatch.setattr(sys, "argv", ["build_kit", "install-copy", "--kit", str(kit), "--target", str(tmp_path / "programme")])
    assert build_kit.main() == 0 and (tmp_path / "programme/SYMLINKS").is_file()


def test_program_inventory_records_links_and_reports_a_redirected_one(tmp_path):
    from tools.dist.program_inventory import compare, snapshot

    write(tmp_path, "programme/lib/libx.so.1.0", "a")
    link(tmp_path, "programme/lib/libx.so.1", "libx.so.1.0")
    link(tmp_path, "programme/cache/vers-dossier", "../lib")
    before = snapshot(tmp_path / "programme")
    assert before["links"] == {"cache/vers-dossier": "../lib", "lib/libx.so.1": "libx.so.1.0"}
    assert "cache/vers-dossier/libx.so.1.0" not in before["files"]
    (tmp_path / "programme/lib/libx.so.1").unlink()
    link(tmp_path, "programme/lib/libx.so.1", "/tmp/ailleurs")
    report = compare(before, snapshot(tmp_path / "programme"))
    assert report["status"] == "changed" and report["links"]["changed"] == ["lib/libx.so.1"] and report["changed"] == []


# --- Avis de tiers du kit Linux (KIT4-29) ---------------------------------------------------------------------------------

def test_linux_notices_have_no_dll_nor_section_6(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    notices = (kit / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "DLL" not in notices and "section 6" not in notices and "(P3)" not in notices
    # Le document d'analyse n'est pas livré : la phrase le dit au lieu d'y renvoyer.
    assert "document du dépôt du projet, non livré avec ce kit" in notices
    assert "Qdrant et à Ollama" in notices and "texte de licence d'uv absent" in notices
    assert "usage interne" in notices and "W030" in notices


def test_the_4b_section_follows_model_sets(repository):
    from tools.dist.notices import third_party_notices

    lock = json.loads((repository / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    title = "## Modification du modèle Qwen3.5-4B"
    with_4b = third_party_notices(repository, [], "0.1.0", "linux-aarch64", lock=lock, gpu="none", models=("2b", "4b"))
    without_4b = third_party_notices(repository, [], "0.1.0", "linux-aarch64", lock=lock, gpu="none", models=("2b",))
    assert title in with_4b and "qwen3.5:4b-text" in with_4b
    assert title not in without_4b and "qwen3.5:4b-text" not in without_4b
    # Kit Windows (sans model_sets) : section inchangée.
    assert title in third_party_notices(repository, [], "0.1.0")


# --- Prérequis déclarés au manifeste (KIT4-28) -----------------------------------------------------------------------------

# Utilitaires externes cherchés dans les scripts du kit (mots entiers hors commentaires, chaînes de message et documents
# en ligne) ; les commandes internes du shell (cd, printf, read, exec, command…) n'y figurent pas.
CANDIDATE_TOOLS = ("awk", "sed", "grep", "sha256sum", "tar", "ldd", "ldconfig", "getconf", "setpriv", "uname", "dirname",
                   "basename", "cut", "tr", "head", "tail", "sort", "uniq", "find", "xargs", "readlink", "realpath", "mktemp",
                   "mv", "cp", "rm", "mkdir", "chmod", "ln", "cat", "id", "stat", "du", "df", "curl", "wget", "flock", "file",
                   "env", "date", "sleep", "timeout", "nproc", "unshare", "pgrep", "pkill", "ps", "dpkg", "dpkg-query", "lsof",
                   "ss", "xdg-open", "gio", "sudo", "su", "chown", "touch", "wc", "tee", "md5sum", "sha1sum")
# bootstrap.sh télécharge uv quand il est absent : jamais dans un kit, où `--offline` s'arrête avant (« uv local absent du
# kit offline »). Outils de ce seul bloc, et `cat` de l'aide (--help).
BOOTSTRAP_ONLINE_ONLY = {"curl", "cut", "mktemp", "mkdir", "mv", "chmod", "rm", "tar", "cat"}


def shell_tools(text: str) -> set[str]:
    """Utilitaires employés par un script POSIX : sans commentaires, documents en ligne, chaînes entre apostrophes ni messages
    entre guillemets (une chaîne entre guillemets qui contient « $( » est gardée : c'est une commande)."""
    text = re.sub(r"<<'?(\w+)'?\n.*?\n\1\n", "\n", text, flags=re.S)
    text = "\n".join(line.split(" #", 1)[0] for line in text.splitlines() if not line.lstrip().startswith("#"))
    text = re.sub(r"'[^'\n]*'", " ", text)
    text = re.sub(r'"([^"$\n]|\$[^(\n])*"', " ", text)
    return {name for name in CANDIDATE_TOOLS if re.search(rf"(?<![\w./$-]){re.escape(name)}(?![\w.-])", text)
            or re.search(rf"(?<![\w.-])/(?:usr/)?s?bin/{re.escape(name)}(?![\w.-])", text)}


def test_target_tools_list_every_tool_the_scripts_use(repository, tmp_path):
    _, manifest = build(repository, tmp_path)
    declared = {item["name"]: item for item in manifest["target"]["tools"]}
    assert all(item["project"] and item["used_for"] for item in declared.values())
    root = linux_kit.ROOT
    used = shell_tools((root / "tools/dist/install.sh").read_text(encoding="utf-8")) | shell_tools((root / "rag.sh").read_text(encoding="utf-8"))
    used |= shell_tools((root / "bootstrap.sh").read_text(encoding="utf-8")) - BOOTSTRAP_ONLINE_ONLY
    # Outils cherchés par le code Python de l'installateur et de la supervision.
    for relative in ("tools/dist/linux_install.py", "services/runtime/posix_process.py"):
        used |= set(re.findall(r"which\(\"([\w.-]+)\"", (root / relative).read_text(encoding="utf-8")))
    used |= {"ldd"} if "def ldd(" in (root / "tools/dist/linux_install.py").read_text(encoding="utf-8") else set()
    # Commandes du guide pour vérifier puis extraire l'archive avant toute exécution du kit.
    used |= {"sha256sum", "tar"}
    assert sorted(used - set(declared)) == [], "outil employé mais non déclaré au manifeste"
    assert sorted(set(declared) - used) == [], "outil déclaré que rien n'emploie"


def fixed_folder_tools() -> dict[str, list[str]]:
    """Outils pris dans des dossiers fixes du système, jamais dans le PATH, avec ces dossiers dans l'ordre de recherche :
    `system_tool <outil>` d'install.sh (dossiers de sa boucle « for candidate in … »), `shutil.which("<outil>", path=…)` de
    l'installateur et de la supervision (chemin écrit en clair ou par une constante du module)."""
    import shlex

    root = linux_kit.ROOT
    script = (root / "tools/dist/install.sh").read_text(encoding="utf-8")
    candidates = re.search(r"^\s*for candidate in (.+?); do$", script, flags=re.M)
    assert candidates, "tools/dist/install.sh : boucle de system_tool absente"
    folders = [word.removesuffix("/$1") for word in shlex.split(candidates.group(1))]
    found = {name: folders for name in re.findall(r"^system_tool (\S+) \|\|$", script, flags=re.M)}
    for relative in ("tools/dist/linux_install.py", "services/runtime/posix_process.py"):
        text = (root / relative).read_text(encoding="utf-8")
        constants = dict(re.findall(r'^([A-Z_]+) = "([^"]*)"$', text, flags=re.M))
        for name, literal, constant in re.findall(r'which\("([\w.-]+)", path=(?:"([^"]+)"|([A-Z_]+))\)', text):
            found.setdefault(name, (literal or constants[constant]).split(":"))
    return found


def test_tools_taken_from_fixed_system_folders_say_where(repository, tmp_path):
    # Alignement de la ronde 5 (U5-04 de l'installateur) : un outil que l'installateur ne prend que dans des dossiers fixes
    # du système est refusé ailleurs, même présent dans le PATH. Son usage déclaré au manifeste (TARGET_TOOLS) nomme ces
    # dossiers, dans l'ordre de recherche (« dans /usr/bin ou /bin »).
    _, manifest = build(repository, tmp_path)
    declared = {item["name"]: item["used_for"] for item in manifest["target"]["tools"]}
    found = fixed_folder_tools()
    assert {"sha256sum", "find"} <= set(found) <= set(declared), (sorted(found), sorted(declared))
    missing = {name: folders for name, folders in found.items()
               if f"dans {', '.join(folders[:-1])} ou {folders[-1]}" not in declared[name]}
    assert missing == {}, "usage déclaré sans les dossiers où l'outil est pris"


def test_no_manifest_field_claims_a_verified_installation_without_proof(repository, tmp_path):
    _, manifest = build(repository, tmp_path)
    target = manifest["target"]
    assert "reference_os_verified" not in target
    assert target["reference_os"] == linux_kit.REFERENCE_OS and target["installation_qualified"] is False
    assert target["installation_qualification_proof"] is None

    def claims(value, path=""):
        if isinstance(value, dict):
            for key, item in value.items():
                if ("verified" in key or "qualified" in key) and item and not value.get(f"{key.removesuffix('_qualified')}_qualification_proof"):
                    yield f"{path}{key}"
                yield from claims(item, f"{path}{key}.")
        elif isinstance(value, list):
            for item in value:
                yield from claims(item, path)

    assert list(claims(manifest)) == []


# --- Provenance de l'interface livrée (KIT4-26) ----------------------------------------------------------------------------

def test_an_export_without_provenance_is_incomplete(repository, tmp_path):
    (repository / "apps/web/out/build-provenance.json").unlink()
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete" and report["missing_for_build"] == []
    assert report["incomplete_causes"] == ["interface sans preuve de provenance (apps/web/out/build-provenance.json absent) : "
                                           "reconstruire l'interface depuis le commit du kit (pnpm build dans apps/web)"]
    with pytest.raises(linux_kit.KitError, match="interface sans preuve de provenance"):
        build(repository, tmp_path)
    assert not (tmp_path / "kit").exists()


def test_an_export_of_another_commit_is_incomplete(repository, tmp_path):
    web_provenance(repository, commit="0123456789ab" + "0" * 28)
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    commit = git(repository, "rev-parse", "HEAD").strip()
    assert report["status"] == "incomplete"
    assert report["incomplete_causes"] == [f"interface construite depuis le commit 0123456789ab, le kit livre {commit[:12]} : "
                                           "reconstruire l'interface depuis le commit du kit (pnpm build dans apps/web)"]
    with pytest.raises(linux_kit.KitError, match="interface construite depuis le commit 0123456789ab"):
        build(repository, tmp_path)


def test_an_export_with_modified_sources_is_incomplete(repository, tmp_path):
    web_provenance(repository, sources_modified=True, modified_sources=["apps/web/src/app/page.tsx"])
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete"
    assert report["incomplete_causes"] == ["interface construite avec des sources apps/web modifiées (apps/web/src/app/page.tsx) : "
                                           "les committer, puis reconstruire l'interface (pnpm build dans apps/web)"]
    web_provenance(repository, pnpm_lock_sha256="0" * 64)
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["incomplete_causes"] == ["interface construite avec un pnpm-lock.yaml différent de celui du commit : reconstruire "
                                           "l'interface depuis le commit du kit (pnpm build dans apps/web)"]
    write(repository, "apps/web/out/build-provenance.json", "{illisible")
    assert linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))["incomplete_causes"] == [
        "preuve de provenance de l'interface illisible (apps/web/out/build-provenance.json) : reconstruire l'interface (pnpm build "
        "dans apps/web)"]


def test_a_clean_export_is_ready_and_recorded(repository, tmp_path):
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "ready" and report["incomplete_causes"] == []
    commit = git(repository, "rev-parse", "HEAD").strip()
    assert report["web_provenance"]["commit"] == commit
    kit, manifest = build(repository, tmp_path)
    assert manifest["web_provenance"] == {**json.loads((repository / "apps/web/out/build-provenance.json").read_text(encoding="utf-8")),
                                          "file": "apps/web/out/build-provenance.json"}
    assert (kit / "apps/web/out/build-provenance.json").is_file()


# --- Paquets des bibliothèques du système sur le poste de fabrication (KIT4-06, partie fabricant) -------------------------

def test_system_packages_are_recorded_from_dpkg_query(repository, tmp_path, monkeypatch):
    # Correspondances relevées par `dpkg -S` sur le poste de référence (audit du 07/10/2026), sous un préfixe /poste absent
    # du poste de test : os.path.realpath les laisse inchangées.
    paths = {"libGL.so.1": "/poste/usr/lib/aarch64-linux-gnu/libGL.so.1", "libjpeg.so.8": "/poste/usr/lib/aarch64-linux-gnu/libjpeg.so.8",
             "libc.so.6": "/poste/lib/aarch64-linux-gnu/libc.so.6", "libcrypt.so.1": "/poste/lib/aarch64-linux-gnu/libcrypt.so.1"}
    owners = {"/poste/usr/lib/aarch64-linux-gnu/libGL.so.1": "libgl1", "/poste/usr/lib/aarch64-linux-gnu/libjpeg.so.8": "libjpeg-turbo8",
              "/poste/lib/aarch64-linux-gnu/libc.so.6": "libc6", "/poste/lib/aarch64-linux-gnu/libcrypt.so.1": "libcrypt1"}
    asked = []

    def ldconfig_double(soname):
        """Double de `ldconfig -p` : chemins du poste de référence."""
        return paths.get(soname)

    def dpkg_query_double(path):
        """Double de `dpkg-query -S` : paquet propriétaire d'un chemin."""
        asked.append(path)
        return owners.get(path)

    monkeypatch.setattr(linux_kit, "host_library_path", ldconfig_double)
    monkeypatch.setattr(linux_kit, "package_owner", dpkg_query_double)
    _, manifest = build(repository, tmp_path)
    packages = manifest["target"]["system_packages"]
    observed = linux_kit.build_os_label()
    assert packages["libGL.so.1"] == {"package": "libgl1", "component": "OpenCV (OCR et tableaux)", "observed_on": observed}
    assert packages["libjpeg.so.8"] == {"package": "libjpeg-turbo8", "component": "OCR Tesseract", "observed_on": observed}
    assert packages["libc.so.6"]["component"] == "bibliothèque C/C++" and packages["libc.so.6"]["package"] == "libc6"
    # Bibliothèque facultative (module _crypt de CPython) : son paquet est relevé aussi.
    assert packages["libcrypt.so.1"]["package"] == "libcrypt1"
    # Bibliothèque inconnue du chargeur du poste de fabrication : sans paquet, jamais deviné.
    assert packages["libtiff.so.5"] == {"package": None, "component": "OCR Tesseract", "observed_on": observed}
    assert set(packages) == set(manifest["target"]["system_libraries"]) | set(manifest["target"]["optional_system_libraries"])
    assert sorted(asked) == sorted(owners)


def test_package_owner_reads_the_first_field_of_dpkg_query(monkeypatch):
    def run_double(argv, **options):
        """Double de subprocess.run pour `dpkg-query -S` : sortie réelle du poste de référence pour libGL."""
        assert argv[1:] == ["-S", "/usr/lib/aarch64-linux-gnu/libGL.so.1.7.0"]
        return subprocess.CompletedProcess(argv, 0, "libgl1:arm64: /usr/lib/aarch64-linux-gnu/libGL.so.1.7.0\n", "")

    monkeypatch.setattr(linux_kit.shutil, "which", which_present)
    monkeypatch.setattr(linux_kit.subprocess, "run", run_double)
    assert linux_kit.package_owner("/usr/lib/aarch64-linux-gnu/libGL.so.1.7.0") == "libgl1"
    monkeypatch.setattr(linux_kit.shutil, "which", which_absent)
    assert linux_kit.package_owner("/usr/lib/aarch64-linux-gnu/libGL.so.1.7.0") is None


# --- Guide LISEZMOI.md (KIT4-16) et icône du menu --------------------------------------------------------------------------

def test_the_installer_publishes_the_constants_of_the_guide():
    # Sans double : les constantes réelles de linux_install.py (lot de l'installateur) sont exigées.
    from tools.dist import kit_guide, linux_install

    absent = [name for name in (*kit_guide.INSTALLER_CONSTANTS, "ICON_SOURCE") if not hasattr(linux_install, name)]
    assert absent == [], f"constantes absentes de tools/dist/linux_install.py : {absent}"
    assert (linux_kit.ROOT / linux_install.ICON_SOURCE).is_file()


def guide_and_icon_constants() -> list[str]:
    from tools.dist import kit_guide

    return [*kit_guide.INSTALLER_CONSTANTS, "ICON_SOURCE"]


@pytest.mark.parametrize("name", guide_and_icon_constants())
def test_a_constant_missing_from_the_installer_is_never_supplied_by_the_tests(tmp_path, monkeypatch, name):
    # QA3-06 : la préparation du dépôt factice (fixture `repository`) ne complète aucune constante de linux_install.py. Une
    # constante disparue arrête la préparation ou la fabrication au lieu de laisser passer les essais avec une valeur de test.
    from tools.dist import linux_install

    monkeypatch.delattr(linux_install, name)
    with pytest.raises((AttributeError, linux_kit.KitError), match=name):
        build(prepare_repository(tmp_path, monkeypatch), tmp_path)
    assert not hasattr(linux_install, name)


def test_the_guide_is_in_the_kit_and_in_sha256sums(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    guide = kit / "LISEZMOI.md"
    assert guide.is_file() and not os.access(guide, os.X_OK)
    assert f"{hashlib.sha256(guide.read_bytes()).hexdigest()}  LISEZMOI.md\n" in (kit / "SHA256SUMS").read_text(encoding="utf-8")
    assert manifest["guide"] == {"file": "LISEZMOI.md", "template": "tools/dist/templates/LISEZMOI-linux.md",
                                 "sha256": hashlib.sha256(guide.read_bytes()).hexdigest(),
                                 "sections": {"deploiement": "docs/deploiement/DEPLOIEMENT.md#8-kit-hors-ligne-linux",
                                              "lanceur": "docs/exploitation/EXPLOITATION.md#11-lanceur-atelier-et-menu",
                                              "depannage": "docs/exploitation/DEPANNAGE.md#10-installateur-et-lanceur-linux",
                                              "reparation": "docs/exploitation/DEPANNAGE.md#réparer-un-programme-installé-avec-le-seul-"
                                                            "kit-de-sa-version",
                                              "sauvegarde": "docs/exploitation/SAUVEGARDE-RESTAURATION.md#2-sauvegarder"}}
    assert linux_kit.verify_kit(kit)["status"] == "verified"
    linux_kit.install_copy(kit, tmp_path / "programme")
    assert (tmp_path / "programme/LISEZMOI.md").read_bytes() == guide.read_bytes()
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["guide"]["status"] == "rendered" and report["guide"]["sections"] == manifest["guide"]["sections"]


def test_guide_values_follow_the_manifest(repository, tmp_path):
    from tools.dist import kit_guide

    kit, manifest = build(repository, tmp_path)
    guide = (kit / "LISEZMOI.md").read_text(encoding="utf-8")
    for value in (manifest["kit_id"], manifest["commit"], "glibc 2.29 ou plus récente", "noyau 5.3", "15 Gio de mémoire",
                  "`qwen3.5:4b` (par défaut), `qwen3.5:2b`", "atelier ouvrir --modele qwen3.5:2b", kit_guide.gib(manifest["bytes"]),
                  "`libGL.so.1` | OpenCV (OCR et tableaux)", "GNU coreutils (`sha256sum`", "| 130 | interruption |",
                  "~/.local/share/atelier-documentaire/programme", "aucune installation réelle de ce kit n'est encore qualifiée",
                  "interne, sans redistribution hors de l'organisation (W030)", "sur CPU ; aucune bibliothèque GPU"):
        assert value in guide, value
    # U5-02 : chaque outil du poste cible déclaré au manifeste (TARGET_TOOLS, confronté aux scripts par
    # test_target_tools_list_every_tool_the_scripts_use) figure dans les prérequis du guide, `find` d'installer.sh compris.
    prerequisites = next(line for line in guide.splitlines() if line.startswith("- Outils du système : "))
    assert [tool["name"] for tool in manifest["target"]["tools"] if f"`{tool['name']}`" not in prerequisites] == []
    assert "`find`" in prerequisites
    files = {"guide": "LISEZMOI.md", "manifest": "kit-manifest.json", "sums": "SHA256SUMS", "links": "SYMLINKS", "executables": "EXECUTABLES",
             "notices": "THIRD_PARTY_NOTICES.md", "installer": "installer.sh"}

    def rendered(changed: dict) -> str:
        return kit_guide.render(changed, template=GUIDE_TEMPLATE, documents=CANONICAL_DOCUMENTS, files=files)

    assert rendered(manifest) == guide
    other = json.loads(json.dumps(manifest))
    other["target"]["glibc_min"] = "2.35"
    other["requirements"]["kit_bytes"] = 5 * 1024**3
    other["model_profiles"] = {"qwen3.5:4b": "config/local16-4b.yaml"}
    other["gpu"] = {"variant": "jetpack5", "ollama_libraries": ["cuda_jetpack5"], "requires_l4t_major": 35}
    changed = rendered(other)
    assert "glibc 2.35 ou plus récente" in changed and "glibc 2.29" not in changed
    assert "5,0 Gio" in changed and "taille maximale d'un fichier sur FAT32" in changed and "FAT32 :" not in guide.split("Transport :")[1][:20]
    assert "Ce kit ne livre que le modèle `qwen3.5:4b`." in changed and "--modele" not in changed
    assert "bibliothèques GPU d'Ollama livrées (`cuda_jetpack5`), pour Jetson Linux R35" in changed


def guide_arguments(command: str, user_command: str) -> list[str] | None:
    """Arguments que reçoit linux_install.parser() pour une commande du guide ; None pour les commandes du système. Chaque
    texte à remplacer (`<dossier>`, `<dossier des versions>`) devient un chemin, comme le lecteur le fait."""
    import shlex

    words = shlex.split(re.sub(r"<[^<>]+>", "/media/volume/atelier", command))
    if words[0] == "./installer.sh":
        return words[1:]
    if words[0] == user_command:
        return ["run", "--destination", "/media/volume/atelier/programme", *words[1:]]
    return None


def test_every_command_of_the_guide_parses(repository, tmp_path):
    from tools.dist import kit_guide, linux_install

    kit, manifest = build(repository, tmp_path)
    commands = kit_guide.commands((kit / "LISEZMOI.md").read_text(encoding="utf-8"))
    kit_id = manifest["kit_id"]
    system = [command for command in commands if guide_arguments(command, linux_install.USER_COMMAND) is None]
    assert system == [f"sha256sum -c {kit_id}.tar.sha256", f"tar -xf {kit_id}.tar -C <dossier>", f"cd <dossier>/{kit_id}"]
    installer = [command for command in commands if command.startswith("./installer.sh")]
    assert installer[0] == "./installer.sh" and len(installer) >= 8
    failures = []
    for command in commands:
        arguments = guide_arguments(command, linux_install.USER_COMMAND)
        if arguments is None:
            continue
        try:
            linux_install.parser().parse_args(arguments)
        except SystemExit:
            failures.append(command)
    assert failures == [], f"commandes du guide refusées par linux_install.parser() : {failures}"


def test_guide_links_resolve_inside_the_kit(repository, tmp_path):
    from urllib.parse import unquote

    from tools.docs.check_docs import LINK, anchors

    kit, _ = build(repository, tmp_path)
    targets = [match.group(3) for match in LINK.finditer((kit / "LISEZMOI.md").read_text(encoding="utf-8"))]
    assert len(targets) >= 5
    for target in targets:
        path, _, anchor = target.partition("#")
        resolved = (kit / unquote(path)).resolve()
        assert "://" not in target and resolved.is_relative_to(kit.resolve()) and resolved.is_file(), target
        assert anchor and anchor in anchors(resolved), target


def test_the_guide_has_no_host_marker(repository, tmp_path, monkeypatch):
    from tools.dist import kit_guide

    kit, _ = build(repository, tmp_path)
    markers = linux_kit.host_markers(repository, str(tmp_path / "maison"))
    assert linux_kit.scan_markers([(kit / "LISEZMOI.md").read_bytes()], [marker.encode() for marker in markers]) == set()
    real_render = kit_guide.render

    def render_with_home(*args, **options):
        """Double du rendu : le guide réel suivi du dossier personnel du poste de fabrication."""
        return real_render(*args, **options) + f"\n{tmp_path / 'maison'}/notes\n"

    monkeypatch.setattr(kit_guide, "render", render_with_home)
    with pytest.raises(linux_kit.KitError, match="Chemin du poste de fabrication présent dans le kit : \\['LISEZMOI.md'\\]"):
        build(repository, tmp_path, name="kit-fuite")
    assert not (tmp_path / "kit-fuite").exists()
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "leaks" and list(report["leaks"]) == ["LISEZMOI.md"]


def test_a_missing_canonical_section_makes_the_kit_incomplete(repository, tmp_path):
    # La section 10 change de titre ; la procédure de réparation (section canonique `reparation`) reste : une seule absente.
    write(repository, "docs/exploitation/DEPANNAGE.md", "# Dépannage\n\n## 10. Autre titre\n\n#### Réparer un programme installé avec le "
                                                         "seul kit de sa version\n")
    git(repository, "commit", "-q", "-am", "sans la section du kit")
    web_provenance(repository)
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete" and report["guide"]["status"] == "refused"
    assert report["incomplete_causes"] == ["Guide LISEZMOI.md non rendu : sections canoniques absentes des documents du kit : "
                                           "docs/exploitation/DEPANNAGE.md « Installateur et lanceur Linux »"]
    with pytest.raises(linux_kit.KitError, match="Installateur et lanceur Linux"):
        build(repository, tmp_path)
    assert not (tmp_path / "kit").exists()


def test_the_menu_icon_and_the_guide_sources_are_required_to_build(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    assert (kit / icon_source()).read_bytes() == b"<svg/>\n"
    git(repository, "rm", "-q", icon_source(), "tools/dist/templates/LISEZMOI-linux.md")
    git(repository, "commit", "-q", "-m", "sans icône ni modèle du guide")
    web_provenance(repository)
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete" and report["missing_for_build"] == ["tools/dist/templates/LISEZMOI-linux.md", icon_source()]
    assert report["guide"]["status"] == "not_rendered"


def test_archive_writes_an_identical_guide_and_a_two_line_checksum(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    kit_id = manifest["kit_id"]
    transport = tmp_path / "transport"
    transport.mkdir()
    with pytest.raises(linux_kit.KitError, match=re.escape(f"nommer le fichier {kit_id}.tar,")):
        linux_kit.archive_kit(kit, transport / "kit.tar")
    result = linux_kit.archive_kit(kit, transport)
    tar, guide = transport / f"{kit_id}.tar", transport / f"{kit_id}.LISEZMOI.md"
    assert result["archive"] == str(tar) and result["guide"] == str(guide)
    assert guide.read_bytes() == (kit / "LISEZMOI.md").read_bytes()
    lines = (transport / f"{kit_id}.tar.sha256").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{result['sha256']}  {kit_id}.tar", f"{hashlib.sha256(guide.read_bytes()).hexdigest()}  {kit_id}.LISEZMOI.md"]
    assert sorted(path.name for path in transport.iterdir()) == sorted([tar.name, guide.name, f"{kit_id}.tar.sha256"])
    sha256sum = shutil.which("sha256sum")
    if sha256sum:
        checked = subprocess.run([sha256sum, "-c", f"{kit_id}.tar.sha256"], cwd=transport, capture_output=True, text=True, check=False)
        assert checked.returncode == 0 and checked.stdout.splitlines() == [f"{kit_id}.tar: OK", f"{kit_id}.LISEZMOI.md: OK"]
    # Rien n'est remplacé : une seconde archive vers le même dossier est refusée et laisse les fichiers en place.
    before = {path.name: path.read_bytes() for path in transport.iterdir()}
    with pytest.raises(linux_kit.KitError, match="doivent être neufs"):
        linux_kit.archive_kit(kit, transport)
    assert {path.name: path.read_bytes() for path in transport.iterdir()} == before


def test_extract_reads_the_archive_line_of_a_two_line_checksum(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    (tmp_path / "transport").mkdir()
    result = linux_kit.archive_kit(kit, tmp_path / "transport")
    checksum = Path(result["checksum"])
    archive_line, guide_line = checksum.read_text(encoding="utf-8").splitlines()
    checksum.write_text(f"{guide_line}\n{archive_line}\n", encoding="utf-8")
    assert linux_kit.extract_kit(Path(result["archive"]), tmp_path / "poste")["status"] == "extracted"
    checksum.write_text(f"{guide_line}\n", encoding="utf-8")
    with pytest.raises(linux_kit.KitError, match=re.escape(f"Empreinte de {manifest['kit_id']}.tar absente")):
        linux_kit.extract_kit(Path(result["archive"]), tmp_path / "autre")
    assert not (tmp_path / "autre").exists()


# --- Essai hors ligne du kit fabriqué (KIT4-27) ----------------------------------------------------------------------------

# Sortie réelle de `uv sync --locked --offline --no-dev` (uv 0.12.21) avec un cache sans la roue de torch, relevée le
# 07/10/2026 sur le poste de référence dans un dossier temporaire, réseau coupé par `unshare -rn`.
UV_MISSING_WHEEL = """Using CPython 3.12.14 interpreter at: /essai/programme/.runtime/python/cpython-3.12.14-linux-aarch64-gnu/bin/python3.12
Creating virtual environment at: .venv
Resolved 130 packages in 3ms
error: Failed to download `torch==2.14.0+cpu`
  cause: Network connectivity is disabled, but the requested data wasn't found in the cache for: `https://download-r2.pytorch.org/whl/cpu/torch-2.14.0%2Bcpu-cp312-cp312-manylinux_2_28_aarch64.whl`

hint: `torch` (v2.14.0+cpu) was included because `agentragpdf` (v0.1.0) depends on `torch`
"""


class TrialRunner:
    """Double du lanceur de commandes de l'essai : `unshare -r -n true` réussit si `isolation`, bootstrap.sh rend `result`.
    Pendant bootstrap.sh, relève l'état de la copie (préfixe de CPython réécrit, emplacement)."""

    def __init__(self, result, *, isolation=True):
        self.result, self.isolation, self.calls, self.seen = result, isolation, [], {}

    def run(self, argv, *, cwd=None, timeout=None):
        from tools.dist.linux_install import Completed

        self.calls.append((list(argv), cwd))
        if argv[-1] == "true":
            return Completed(0 if self.isolation else 1, "", "" if self.isolation else "unshare: write failed /proc/self/uid_map")
        program = Path(cwd)
        sysconfig = program / f".runtime/python/{PYTHON_KEY}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py"
        self.seen = {"program": program, "exists": (program / "bootstrap.sh").is_file(), "sysconfig": sysconfig.read_text(encoding="utf-8")}
        return self.result


def test_offline_trial_runs_bootstrap_offline_in_a_temporary_copy(repository, tmp_path):
    from tools.dist.linux_install import Completed

    kit, manifest = build(repository, tmp_path)
    work = tmp_path / "essais"
    work.mkdir()
    runner = TrialRunner(Completed(0, "Environnement Python isolé prêt.\n"))
    result = linux_kit.offline_trial(kit, work=work, runner=runner)
    program = runner.seen["program"]
    assert result["status"] == "passed" and result["kit_id"] == manifest["kit_id"] and result["network_isolated"] is True
    argv, cwd = runner.calls[-1]
    assert Path(argv[0]).name == "unshare" and argv[1:] == ["-r", "-n", str(program / "bootstrap.sh"), "--offline", "--no-dev"]
    assert cwd == program and runner.calls[0][0][1:] == ["-r", "-n", "true"]
    assert result["command"] == ["bootstrap.sh", "--offline", "--no-dev"] and result["missing_packages"] == []
    # Copie vérifiée hors du dépôt et du kit, préfixe de CPython réécrit comme par l'installateur, puis retirée.
    assert runner.seen["exists"] and program.is_relative_to(work) and not program.is_relative_to(kit) and not program.is_relative_to(repository)
    assert "@ATELIER_PYTHON_PREFIX@" not in runner.seen["sysconfig"] and str(program / ".runtime/python") in runner.seen["sysconfig"]
    assert result["work_removed"] is True and list(work.iterdir()) == []
    assert linux_kit.verify_kit(kit)["status"] == "verified"


def test_offline_trial_reports_the_missing_package(repository, tmp_path):
    from tools.dist.linux_install import Completed

    kit, _ = build(repository, tmp_path)
    work = tmp_path / "essais"
    work.mkdir()
    runner = TrialRunner(Completed(1, "", UV_MISSING_WHEEL), isolation=False)
    result = linux_kit.offline_trial(kit, work=work, runner=runner)
    assert result["status"] == "failed" and result["returncode"] == 1 and result["missing_packages"] == ["torch==2.14.0+cpu"]
    assert result["network_isolated"] is False and runner.calls[-1][0][1:] == ["--offline", "--no-dev"]
    assert "Network connectivity is disabled" in result["output_tail"] and list(work.iterdir()) == []


def test_offline_trial_refuses_a_work_folder_in_the_repository_or_the_kit_or_without_room(repository, tmp_path, monkeypatch):
    from tools.dist.linux_install import Completed

    kit, manifest = build(repository, tmp_path)
    runner = TrialRunner(Completed(0, ""))
    for folder in (repository, kit / "docs"):
        with pytest.raises(linux_kit.KitError, match="hors du dépôt et du kit"):
            linux_kit.offline_trial(kit, work=folder, runner=runner, root=repository)
    work = tmp_path / "essais"
    work.mkdir()

    real = shutil.disk_usage(tmp_path)

    def disk_usage_double(path):
        """Double de shutil.disk_usage : 1 Gio libre."""
        return real._replace(free=1024**3)

    monkeypatch.setattr(linux_kit.shutil, "disk_usage", disk_usage_double)
    with pytest.raises(linux_kit.KitError, match="Place insuffisante pour l'essai hors ligne"):
        linux_kit.offline_trial(kit, work=work, runner=runner)
    assert runner.calls == [] and list(work.iterdir()) == []


def test_build_kit_verify_runs_the_offline_trial_on_request(repository, tmp_path, monkeypatch, capsys):
    from tools.dist import build_kit

    kit, _ = build(repository, tmp_path)
    asked = []

    def trial_double(folder, *, work=None, **options):
        """Double de l'essai hors ligne : échec nommant un paquet."""
        asked.append((folder, work))
        return {"status": "failed", "missing_packages": ["torch==2.14.0+cpu"]}

    monkeypatch.setattr(linux_kit, "offline_trial", trial_double)
    monkeypatch.setattr(sys, "argv", ["build_kit", "verify", "--kit", str(kit), "--essai-hors-ligne", "--dossier-essai", str(tmp_path)])
    assert build_kit.main() == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "failed" and printed["verification"]["status"] == "verified"
    assert printed["offline_trial"]["missing_packages"] == ["torch==2.14.0+cpu"] and asked == [(kit, tmp_path)]
    monkeypatch.setattr(linux_kit, "offline_trial", essai_reussi)
    monkeypatch.setattr(sys, "argv", ["build_kit", "verify", "--kit", str(kit), "--essai-hors-ligne"])
    assert build_kit.main() == 0 and json.loads(capsys.readouterr().out)["status"] == "verified"


def test_a_missing_icon_constant_makes_the_kit_incomplete_instead_of_crashing(repository, tmp_path, monkeypatch):
    from tools.dist import linux_install

    monkeypatch.delattr(linux_install, "ICON_SOURCE", raising=False)
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete"
    assert report["missing_for_build"] == ["ICON_SOURCE (constante absente de tools/dist/linux_install.py)"]
    with pytest.raises(linux_kit.KitError, match="ICON_SOURCE"):
        build(repository, tmp_path)
    assert not (tmp_path / "kit").exists()


def test_the_offline_trial_options_are_refused_for_a_windows_kit(tmp_path, monkeypatch, capsys):
    from tools.dist import build_kit

    write(tmp_path, "kit-windows/kit-manifest.json", json.dumps({"format": "atelier-kit-v1"}))
    monkeypatch.setattr(sys, "argv", ["build_kit", "verify", "--kit", str(tmp_path / "kit-windows"), "--essai-hors-ligne"])
    assert build_kit.main() == 1
    assert json.loads(capsys.readouterr().out)["message"] == "--essai-hors-ligne et --dossier-essai sont des options du kit Linux"


def test_libraries_of_the_opencv_wheel_are_labelled_opencv():
    # Relevé du dry-run du 07/10/2026 : GLib est requise par Qt, livré dans opencv_python.libs avec cv2.
    qt = {"site-packages/opencv_python.libs/libQt5Core-fd04ed63.so.5.15.19"}
    assert linux_kit.component_of("libglib-2.0.so.0", qt) == "OpenCV (OCR et tableaux)"
    assert linux_kit.component_of("libgthread-2.0.so.0", qt | {"site-packages/cv2/cv2.abi3.so"}) == "OpenCV (OCR et tableaux)"
    assert linux_kit.component_of("libz.so.1", {linux_kit.TESSERACT_BINARY, "site-packages/cv2/cv2.abi3.so"}) == \
        "OCR Tesseract, OpenCV (OCR et tableaux)"
    assert linux_kit.component_of("libinconnue.so.1", {"site-packages/autre/x.so"}) == "autre composant du kit (site-packages/autre/x.so)"


def test_install_copy_reports_progress_up_to_the_total(repository, tmp_path):
    # KIT4-07 : rappel progress(octets copiés, total) après chaque fichier de SHA256SUMS, puis le total atteint.
    kit, _ = build(repository, tmp_path)
    calls = []

    def progression_relevee(done, total):
        """Rappel `progress` espion : consigne chaque appel."""
        calls.append((done, total))

    linux_kit.install_copy(kit, tmp_path / "programme", progress=progression_relevee)
    total = sum((kit / relative).stat().st_size for relative in linux_kit.read_sums(kit))
    assert len(calls) == len(linux_kit.read_sums(kit)) + 1 and calls[-1] == (total, total)
    assert all(total == expected for _, expected in calls) and [done for done, _ in calls] == sorted(done for done, _ in calls)
    assert linux_kit.verify_kit(tmp_path / "programme")["status"] == "verified"


# --- Chaîne fabricant → installateur, sans retouche du manifeste (QA-03, REL-U08) -------------------------------------------

GIB = 1024**3


@pytest.fixture
def session_isolee(tmp_path, monkeypatch):
    """HOME et XDG_* propres au test, comme `isolated_home` des essais de l'installateur : aucune entrée de menu, commande ni
    registre n'atteint le compte réel."""
    home = tmp_path / "session"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_BIN_HOME"):
        monkeypatch.delenv(name, raising=False)
    return home


def installer_tests():
    """Doubles nommés des essais de l'installateur (`PosteSimule`, `ProgrammeSimule` par `context`), importés à l'appel :
    tests/unit/test_dist_linux_install.py importe ce module."""
    from tests.unit import test_dist_linux_install

    return test_dist_linux_install


def test_a_built_kit_refuses_busy_default_ports_before_any_write(repository, tmp_path, session_isolee):
    # Kit fabriqué, manifeste tel que le fabricant l'écrit : le port par défaut de l'API occupé est refusé avant toute
    # écriture, hors terminal et sans --oui, avec la commande qui reprend un triplet libre.
    from tools.dist import linux_install

    doubles = installer_tests()
    kit, manifest = build(repository, tmp_path)
    assert manifest["profile_ports"][manifest["default_model"]] == {"app": 8785, "qdrant": 6333, "ollama": 11434}
    ctx = doubles.context(kit, probe=doubles.PosteSimule(busy={8785}))
    code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees")], ctx)
    errors = ctx.err.getvalue()
    assert code == linux_install.EXIT_REFUSED, doubles.screen(ctx)
    assert "port 8785 occupé" in errors and "--ports 8786,6333,11434" in errors
    assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists()
    assert list(session_isolee.iterdir()) == []


def announced_space(guide: str) -> list[int]:
    """Tailles de la ligne « Place à prévoir pour l'installation » du guide, en octets, dans leur ordre."""
    row = next(line for line in guide.splitlines() if line.startswith("| Place à prévoir pour l'installation |"))
    return [int(float(value.replace(",", ".")) * GIB) for value in re.findall(r"(\d+,\d) Gio", row)]


def test_the_space_announced_by_the_guide_passes_the_installer_precheck(repository, tmp_path, session_isolee):
    # Le guide annonce d'abord la place de la disposition par défaut (programme et données sur un même volume), puis le
    # programme seul et la réserve du volume des données : chacune suffit au précontrôle réel de l'installateur.
    from tools.dist import linux_install

    doubles = installer_tests()
    kit, manifest = build(repository, tmp_path)
    shared, program, reserve = announced_space((kit / "LISEZMOI.md").read_text(encoding="utf-8"))
    needed = manifest["requirements"]["install_bytes_min"]
    assert program >= needed and reserve == linux_install.DATA_MIN_FREE_BYTES and shared >= needed + reserve
    same_volume = doubles.context(kit, probe=doubles.PosteSimule(free=shared))
    assert linux_install.main(["verifier"], same_volume) == linux_install.EXIT_OK, doubles.screen(same_volume)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    split = doubles.context(kit, probe=doubles.PosteSimule(device={str(destination): "8:1", str(data_root): "8:2", "*": "8:3"},
                                                           free={str(destination): program, str(data_root): reserve, "*": 0}))
    assert linux_install.main(["verifier", "--destination", str(destination), "--data-root", str(data_root)], split) == 0, \
        doubles.screen(split)
    assert list(session_isolee.iterdir()) == [] and not destination.exists() and not data_root.exists()
