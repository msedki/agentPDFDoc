"""Kit hors ligne Linux (R26-KIT-01) : liste blanche, liens, marqueurs du poste, neutralisations, variantes, glibc,
intégrité, copie et archive, sur un dépôt Git factice et un `.runtime` factice sous TMPDIR.

Doubles nommés : `fake_readelf` remplace readelf (les ELF factices n'ont que leur en-tête) et rend la sortie réelle de
`readelf -V -d -W` du Tesseract du poste de référence ; `jetson_r35` simule /etc/nv_tegra_release. Le dépôt Git factice
est créé et committé dans le dossier temporaire du test, jamais dans le dépôt du projet.
"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

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


def make_repository(tmp_path: Path, *, machine: int = AARCH64) -> Path:
    """Dépôt Git factice committé, `.runtime` lien vers un autre dossier (comme sur le poste de référence)."""
    root = tmp_path / "depot"
    for relative, content in {"services/api/main.py": "VERSION = 'commit'\n", "config/local16.yaml": PROFILE_2B,
                              "config/local16-4b.yaml": PROFILE_4B, "pyproject.toml": '[project]\nname = "x"\nversion = "0.1.0"\n',
                              "bootstrap.sh": "#!/bin/sh\npython_key=cpython-3.12.14-linux-$machine-gnu\n", "rag.sh": "#!/bin/sh\n",
                              "uv.lock": "version = 1\n", "README.md": "# Atelier\n", "CHANGELOG.md": "# Journal\n",
                              "docs/index.md": "# Docs\n", "tools/corpus/x.py": "", "tools/dist/linux_install.py": "",
                              "tools/dist/linux_kit.py": "", "tools/dist/linux_profiles.py": "", "tools/dist/build_kit.py": "",
                              "tools/dist/notices.py": "", "tools/dist/install.ps1": "# Windows\n",
                              "packages/contracts/contracts.json": "{}\n", "apps/web/package.json": "{}\n",
                              "apps/web/pnpm-lock.yaml": "lockfileVersion: 9\n", "tests/unit/test_x.py": "",
                              "RAG_Local_Agents/PLAN.md": "# Plan\n",
                              ".gitignore": "/.runtime\n.runtime/\napps/web/out/\n__pycache__/\n"}.items():
        write(root, relative, content, executable=relative.endswith(".sh"))
    write(root, "tools/dist/install.sh", INSTALL_SH, executable=True)
    lock_models = {}
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
    return root


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


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: None)
    return make_repository(tmp_path)


@pytest.fixture
def jetson_r35(monkeypatch):
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: {"major": 35, "revision": "4.1", "line": "# R35 (release), REVISION: 4.1"})


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


def test_models_2b_alone_drops_the_4b_blobs_manifests_and_tokenizer(repository):
    full = linux_kit.plan_kit(repository, platform="linux-aarch64")
    small = linux_kit.plan_kit(repository, platform="linux-aarch64", models=("2b",))
    dropped = set(full.entries) - set(small.entries)
    assert ".runtime/models/qwen3.5-4b-tokenizer/tokenizer.json" in dropped
    assert {".runtime/manifests/ollama-model.json", ".runtime/manifests/ollama-model-text.json"} <= dropped
    assert {f".runtime/models/ollama/blobs/{digest(label).replace(':', '-')}" for label in ("c4b", "w4b", "c4t", "w4t")} <= dropped
    assert ".runtime/manifests/ollama-model-2b.json" in small.entries and ".runtime/models/qwen3.5-2b-tokenizer/tokenizer.json" in small.entries
    assert [record["name"] for record in small.model_records] == ["qwen3.5:2b"] and small.kit_id.endswith("-none-2b")
    assert [record["name"] for record in full.model_records] == ["qwen3.5:2b", "qwen3.5:4b", "qwen3.5:4b-text"]
    assert f".runtime/models/ollama/blobs/sha256-{'0' * 64}" not in full.entries
    assert full.excluded["magasin Ollama hors modèles choisis"] == 1


def test_a_kit_without_the_default_2b_model_or_with_an_altered_model_is_refused(repository):
    with pytest.raises(linux_kit.KitError, match="2B"):
        linux_kit.plan_kit(repository, platform="linux-aarch64", models=("4b",))
    write(repository, ".runtime/models/ollama/manifests/registry.ollama.ai/library/qwen3.5/4b", "altéré")
    with pytest.raises(linux_kit.KitError, match="qwen3.5:4b absent ou différent du verrou"):
        linux_kit.plan_kit(repository, platform="linux-aarch64")
    assert linux_kit.plan_kit(repository, platform="linux-aarch64", models=("2b",)).models == ("2b",)


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
    assert manifest["requirements"]["install_bytes_min"] == manifest["bytes"] + 3 * 1024**3
    notices = (kit / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "texte de licence d'uv absent" in notices and "| qdrant | 1.19.1 |" in notices and "JetPack 5" not in notices
    assert (kit / "installer.sh").read_text(encoding="utf-8") == INSTALL_SH and os.access(kit / "installer.sh", os.X_OK)


def test_a_binary_of_another_architecture_refuses_a_cross_kit(repository, tmp_path):
    write(repository, ".runtime/bin/ollama-0.35.0/bin/ollama", elf_header(X86_64), executable=True)
    with pytest.raises(linux_kit.KitError, match="jamais de kit croisé"):
        build(repository, tmp_path)


def test_build_kit_refuses_a_platform_other_than_the_build_host(monkeypatch, capsys, tmp_path):
    from tools.dist import build_kit

    monkeypatch.setattr(linux_kit, "host_platform", lambda: "linux-aarch64")
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-x86_64", "--output", str(tmp_path / "kit")])
    assert build_kit.main() == 1
    assert "un kit se fabrique sur un poste de sa plateforme" in capsys.readouterr().out and not (tmp_path / "kit").exists()
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--platform", "linux-aarch64", "--without-gpu", "--dry-run"])
    assert build_kit.main() == 1 and "--gpu none" in capsys.readouterr().out


def test_a_commit_without_the_linux_installer_cannot_be_built(repository, tmp_path):
    git(repository, "rm", "-q", "tools/dist/linux_install.py")
    git(repository, "commit", "-q", "-m", "sans installateur")
    report = linux_kit.dry_run(repository, platform="linux-aarch64", home=str(tmp_path / "maison"))
    assert report["status"] == "incomplete" and report["missing_for_build"] == ["tools/dist/linux_install.py"]
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


def test_archive_and_controlled_extraction_round_trip(repository, tmp_path):
    kit, manifest = build(repository, tmp_path)
    (tmp_path / "transport").mkdir()
    archive = linux_kit.archive_kit(kit, tmp_path / "transport/kit.tar")
    assert archive["status"] == "archived" and (tmp_path / "transport/kit.tar.sha256").read_text(encoding="utf-8").startswith(archive["sha256"])
    result = linux_kit.extract_kit(tmp_path / "transport/kit.tar", tmp_path / "poste")
    assert result["status"] == "extracted" and result["kit"] == str(tmp_path / "poste" / manifest["kit_id"])
    extracted = Path(result["kit"])
    assert os.readlink(extracted / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0") == "libggml.so.0.24.0"
    assert os.access(extracted / "installer.sh", os.X_OK)
    with pytest.raises(linux_kit.KitError, match="existe déjà"):
        linux_kit.extract_kit(tmp_path / "transport/kit.tar", tmp_path / "poste")
    assert [path.name for path in (tmp_path / "poste").iterdir()] == [manifest["kit_id"]]


def test_a_tampered_archive_is_refused_before_extraction(repository, tmp_path):
    kit, _ = build(repository, tmp_path)
    (tmp_path / "transport").mkdir()
    linux_kit.archive_kit(kit, tmp_path / "transport/kit.tar")
    with (tmp_path / "transport/kit.tar").open("r+b") as stream:
        stream.seek(2000)
        stream.write(b"!")
    with pytest.raises(linux_kit.KitError, match="Archive altérée"):
        linux_kit.extract_kit(tmp_path / "transport/kit.tar", tmp_path / "poste")
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
