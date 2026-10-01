"""Provisionnement de Tesseract : construction Linux depuis les sources verrouillées, copie Windows inchangée.

Les essais Linux exécutent de vrais petits programmes (scripts POSIX, binaire C compilé à la volée) dans une
racine temporaire ; la compilation complète de Leptonica et Tesseract est prouvée par le manifeste réel de
`.runtime/manifests/tesseract-built.json`, revérifié par le dernier essai lorsqu'il existe.
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.runtime import artifacts, provisioning
from services.runtime.platforms import platform_id

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="Essai par programmes POSIX ; la branche Windows est qualifiée sur son poste.")
PROFILE = {"pdf": {"tesseract_cmd": ".runtime/bin/tesseract-5.4.0/tesseract.exe"}}
REAL_ROOT = Path(__file__).resolve().parents[2]


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def lock_entries(versions=("1.87.0", "5.4.0"), hashes=("a" * 64, "b" * 64), sizes=(1, 1), content=None):
    leptonica, tesseract = versions
    entries = [
        {"version": leptonica, "platform": platform_id(), "publisher": "DanBloomberg/leptonica", "license": "BSD-2-Clause",
         "url": "https://example.invalid/leptonica.tar.gz", "size": sizes[0], "sha256": hashes[0],
         "target": f".runtime/cache/downloads/leptonica-{leptonica}.tar.gz"},
        {"version": tesseract, "platform": [platform_id(), "other-platform"], "publisher": "tesseract-ocr/tesseract",
         "license": "Apache-2.0", "url": "https://example.invalid/tesseract.tar.gz", "size": sizes[1], "sha256": hashes[1],
         "target": f".runtime/cache/downloads/tesseract-{tesseract}-source.tar.gz"},
        # Entrée d'une autre plateforme : elle doit être ignorée par la sélection.
        {"version": "9.9.9", "platform": "other-platform", "publisher": "tesseract-ocr/tesseract", "url": "https://example.invalid/x",
         "sha256": "c" * 64, "target": ".runtime/cache/downloads/other.tar.gz"},
    ]
    if content is not None:
        entries[1]["content_sha256"] = content
    return entries


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = (tmp_path / "root").resolve()
    (base / "config").mkdir(parents=True)
    lock = base / "config/artifacts.lock.json"
    monkeypatch.setattr(provisioning, "ROOT", base)
    monkeypatch.setattr(provisioning, "ARTIFACT_LOCK", lock)
    monkeypatch.setattr(artifacts, "ROOT", base)
    write_lock(base, lock_entries())
    return base


def write_lock(base, entries):
    (base / "config/artifacts.lock.json").write_text(json.dumps({"groups": {"tesseract-source": entries}}), encoding="utf-8")


def forbid(monkeypatch, *names, raising=True):
    for name in names:
        def refuse(*args, _name=name, **kwargs):
            raise AssertionError(f"{_name} ne doit pas être appelé")
        monkeypatch.setattr(provisioning, name, refuse, raising=raising)


def installed_copy(base, version_line="tesseract 5.4.0", leptonica_line=" leptonica-1.87.0"):
    """Construction installée et manifeste concordant, tels que les écrit `build_tesseract`."""
    target = executable(base / ".runtime/bin/tesseract-5.4.0/tesseract",
                        f'echo "{version_line}"\necho "{leptonica_line}"\n')
    (target.parent / "LICENSE").write_text("Apache License 2.0\n", encoding="utf-8")
    (target.parent / "leptonica-license.txt").write_text("BSD 2-clause\n", encoding="utf-8")
    files = [{"path": path.relative_to(base).as_posix(), "sha256": artifacts.file_hash(path), "size": path.stat().st_size}
             for path in sorted(target.parent.iterdir())]
    manifest = {"kind": provisioning.BUILD_KIND, "platform": platform_id(),
                "sources": provisioning._source_records(provisioning.locked_tesseract_sources()),
                "cmake_options": provisioning._cmake_options(),
                "binary": {"path": target.relative_to(base).as_posix(), "sha256": artifacts.file_hash(target)},
                "files": files, "built_at_utc": "2026-10-01T00:00:00+00:00"}
    path = base / provisioning.BUILT_MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return target, path


@POSIX
def test_matching_manifest_reuses_build_without_download_or_compilation(root, monkeypatch):
    target, _ = installed_copy(root)
    forbid(monkeypatch, "download", "compile_sources")
    result = provisioning.tesseract(PROFILE)
    assert result["status"] == "verified_built_copy"
    assert result["version"] == "tesseract 5.4.0"
    assert result["binary"] == ".runtime/bin/tesseract-5.4.0/tesseract"
    assert not (root / ".runtime/manifests/tesseract-installed-copy.json").exists()


@POSIX
@pytest.mark.parametrize("alteration,reason", [
    ("binary", "binaire"), ("license", "fichier .runtime/bin/tesseract-5.4.0/LICENSE"),
    ("sources", "archives sources"), ("options", "options CMake"), ("platform", "pour windows-x86_64"),
])
def test_manifest_mismatch_refuses_reuse_and_preserves_files(root, monkeypatch, alteration, reason):
    target, manifest_path = installed_copy(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if alteration == "binary":
        target.write_text(target.read_text(encoding="utf-8") + "# altéré\n", encoding="utf-8")
    elif alteration == "license":
        (target.parent / "LICENSE").write_text("modifiée\n", encoding="utf-8")
    elif alteration == "sources":
        write_lock(root, lock_entries(hashes=("a" * 64, "d" * 64)))
    elif alteration == "options":
        manifest["cmake_options"]["tesseract"].remove("-DDISABLE_CURL=ON")
    else:
        manifest["platform"] = "windows-x86_64"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = {path: path.read_bytes() for path in target.parent.iterdir()}
    forbid(monkeypatch, "download", "compile_sources")
    with pytest.raises(ValueError, match="aucun remplacement implicite") as error:
        provisioning.tesseract(PROFILE)
    assert reason in str(error.value)
    assert {path: path.read_bytes() for path in target.parent.iterdir()} == before
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


@POSIX
def test_binary_announcing_another_version_is_refused(root, monkeypatch):
    installed_copy(root, version_line="tesseract 5.3.4")
    forbid(monkeypatch, "download", "compile_sources")
    with pytest.raises(ValueError, match="annonce « tesseract 5.3.4 »"):
        provisioning.tesseract(PROFILE)


@POSIX
def test_locked_tesseract_version_other_than_540_is_refused_before_any_work(root, monkeypatch):
    write_lock(root, lock_entries(versions=("1.87.0", "5.5.0")))
    forbid(monkeypatch, "download", "compile_sources", "build_tools")
    with pytest.raises(ValueError, match="Tesseract 5.5.0 verrouillé, 5.4.0 attendu"):
        provisioning.tesseract(PROFILE)
    assert not (root / ".runtime").exists()


@POSIX
def test_lock_without_source_for_this_platform_is_refused(root, monkeypatch):
    entries = lock_entries()
    for entry in entries:
        entry["platform"] = "other-platform"
    write_lock(root, entries)
    with pytest.raises(ValueError, match=f"une archive leptonica attendue pour {platform_id()}, 0 trouvée"):
        provisioning.tesseract(PROFILE)


@POSIX
def test_missing_tools_are_named_before_any_download(root, tmp_path, monkeypatch):
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    # Poste sans outil : ni dans le PATH, ni dans les dossiers système consultés en premier.
    monkeypatch.setattr(provisioning, "SYSTEM_TOOL_DIRS", (str(empty),), raising=False)
    forbid(monkeypatch, "download", "compile_sources")
    with pytest.raises(provisioning.MissingBuildPrerequisites) as error:
        provisioning.tesseract(PROFILE)
    assert error.value.missing == ["cmake 3.15 ou plus récent", "compilateur C (cc, gcc ou clang)",
                                   "compilateur C++ (c++, g++ ou clang++)", "ldd (glibc)", "readelf (binutils)",
                                   "outil de construction : make (ou ninja à défaut)"]
    assert "droits d'administration" in str(error.value) and isinstance(error.value, FileNotFoundError)
    assert not (root / ".runtime").exists()


@POSIX
def test_old_cmake_and_missing_headers_are_named(tmp_path):
    tools = tmp_path / "tools"
    executable(tools / "cmake", 'echo "cmake version 3.10.2"\n')
    # Préprocesseur simulé : seuls png.h et tiffio.h manquent.
    executable(tools / "cc", 'input=$(cat)\ncase "$input" in *"<png.h>"*|*"<tiffio.h>"*) exit 1;; esac\nexit 0\n')
    for name in ("c++", "make", "ldd", "readelf"):
        executable(tools / name, "exit 0\n")
    missing = provisioning.missing_build_prerequisites(provisioning.build_tools(str(tools)))
    assert missing == ["cmake 3.15 ou plus récent (trouvé : 3.10.2)", "en-tête png.h de libpng (libpng-dev)",
                       "en-tête tiffio.h de libtiff (libtiff-dev)"]


def test_unknown_cmake_variables_are_reported():
    log = ("-- Configuring done\nCMake Warning:\n  Manually-specified variables were not used by the project:\n\n"
           "    DISABLE_CRUL\n    ENABLE_TYPO\n\n\n-- Generating done\n")
    assert provisioning.unused_cmake_variables(log) == ["DISABLE_CRUL", "ENABLE_TYPO"]
    assert provisioning.unused_cmake_variables("-- Configuring done\n-- Generating done\n") == []


@POSIX
def test_configuration_with_unused_option_stops_the_build(tmp_path):
    tools = tmp_path / "tools"
    executable(tools / "cmake", 'case " $* " in *" -S "*) printf "CMake Warning:\\n  Manually-specified variables were not '
                                'used by the project:\\n\\n    DISABLE_CRUL\\n\\n";; esac\nexit 0\n')
    found = {"cmake": str(tools / "cmake"), "cc": "/usr/bin/cc", "c++": "/usr/bin/c++", "ninja": None,
             "make": "/usr/bin/make", "ldd": None, "readelf": None}
    build = tmp_path / "build"
    build.mkdir()
    sources = {"leptonica": tmp_path / "src/leptonica", "tesseract": tmp_path / "src/tesseract"}
    with pytest.raises(RuntimeError, match="Options CMake inconnues de leptonica : DISABLE_CRUL"):
        provisioning.compile_sources(sources, build, build / "prefix", found, 2, tmp_path / "logs")
    assert (tmp_path / "logs/leptonica-configure.log").is_file()


ENV_PROBE = 'printf "ARGS:%s\\n" "$@"\nenv | sed "s/^/ENV:/"\nexit 0\n'


def probed_compilation(tmp_path, monkeypatch, tools_dir=None, builder="make"):
    """Compilation par un cmake factice qui consigne ses arguments et son environnement dans les journaux."""
    tools_dir = tools_dir or tmp_path / "tools"
    cmake = executable(tools_dir / "cmake", ENV_PROBE)
    for name, value in (("LD_LIBRARY_PATH", "/usr/local/cuda-11.4/lib64:"), ("CFLAGS", "-O0 -g"), ("CXXFLAGS", "-O0"),
                        ("CPPFLAGS", "-I/opt/x"), ("LDFLAGS", "-L/opt/x"), ("HOME", str(tmp_path / "user-home")),
                        ("TMPDIR", str(tmp_path / "user-tmp")), ("PATH", f"{tmp_path / 'user-bin'}:/usr/bin:/bin")):
        monkeypatch.setenv(name, value)
    found = {"cmake": str(cmake), "cc": "/usr/bin/cc", "c++": "/usr/bin/c++", "ldd": "/usr/bin/ldd", "readelf": "/usr/bin/readelf",
             "make": "/usr/bin/make" if builder == "make" else None, "ninja": str(tools_dir / "ninja") if builder == "ninja" else None}
    # Dossier résolu : un seul drapeau -ffile-prefix-map attendu ; l'espace impose la citation pour le shell.
    build = tmp_path.resolve() / "build root"
    build.mkdir()
    sources = {"leptonica": build / "src/leptonica-1.87.0", "tesseract": build / "src/tesseract-5.4.0"}
    record = provisioning.compile_sources(sources, build, build / "prefix", found, 2, tmp_path / "logs")
    logs = {}
    for name in ("leptonica", "tesseract"):
        text = (tmp_path / f"logs/{name}-configure.log").read_text(encoding="utf-8")
        logs[name] = {"args": [line[5:] for line in text.splitlines() if line.startswith("ARGS:")],
                      "env": dict(line[4:].split("=", 1) for line in text.splitlines() if line.startswith("ENV:"))}
    return build, record, logs


@POSIX
def test_compilation_environment_inherits_no_loader_variable_nor_flags(tmp_path, monkeypatch):
    build, _, logs = probed_compilation(tmp_path, monkeypatch)
    for name in ("leptonica", "tesseract"):
        env = logs[name]["env"]
        assert not {"LD_LIBRARY_PATH", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS"} & set(env), env
        assert env["HOME"] == str(build / "home") and env["TMPDIR"] == str(build / "tmp")
        assert (build / "home").is_dir() and (build / "tmp").is_dir()
        assert env["CC"] == "/usr/bin/cc" and env["CXX"] == "/usr/bin/c++"
        # PATH limité au système et au dossier du seul outil hors système retenu (le cmake factice).
        assert env["PATH"] == f"/usr/bin:/bin:{tmp_path / 'tools'}"


@POSIX
def test_compilation_uses_make_and_maps_the_build_root_out_of_the_binary(tmp_path, monkeypatch):
    build, record, logs = probed_compilation(tmp_path, monkeypatch)
    assert record["generator"] == "Unix Makefiles"
    mapping = f"-ffile-prefix-map='{build}'=."
    lept, tess = logs["leptonica"]["args"], logs["tesseract"]["args"]
    assert "-DCMAKE_MAKE_PROGRAM=/usr/bin/make" in lept and "-DCMAKE_MAKE_PROGRAM=/usr/bin/make" in tess
    # Leptonica ne déclare que le langage C (project(leptonica LANGUAGES C)) : CMAKE_CXX_FLAGS y serait inutilisée.
    assert f"-DCMAKE_C_FLAGS={mapping}" in lept and not any(arg.startswith("-DCMAKE_CXX_FLAGS") for arg in lept)
    assert f"-DCMAKE_C_FLAGS={mapping}" in tess and f"-DCMAKE_CXX_FLAGS={mapping}" in tess
    assert provisioning._cmake_options()["leptonica"].count("-DCMAKE_C_FLAGS=-ffile-prefix-map=<build_root>=.") == 1
    assert {"-DCMAKE_C_FLAGS=-ffile-prefix-map=<build_root>=.", "-DCMAKE_CXX_FLAGS=-ffile-prefix-map=<build_root>=."} \
        <= set(provisioning._cmake_options()["tesseract"])


@POSIX
def test_ninja_is_used_only_without_make(tmp_path, monkeypatch):
    _, record, logs = probed_compilation(tmp_path, monkeypatch, builder="ninja")
    assert record["generator"] == "Ninja"
    assert f"-DCMAKE_MAKE_PROGRAM={tmp_path / 'tools/ninja'}" in logs["tesseract"]["args"]


@POSIX
def test_symlinked_build_root_maps_both_spellings(tmp_path):
    real = tmp_path / "volume/build"
    real.mkdir(parents=True)
    link = tmp_path / "build"
    link.symlink_to(real, target_is_directory=True)
    flags = provisioning.file_prefix_map_flags(link)
    assert flags == f"-ffile-prefix-map={link}=. -ffile-prefix-map={real}=."
    assert provisioning.file_prefix_map_flags(real) == f"-ffile-prefix-map={real}=."


@POSIX
def test_system_tools_are_preferred_and_make_before_ninja(tmp_path, monkeypatch):
    user_bin = tmp_path / "user-bin"
    system = tmp_path / "system-bin"
    for name in ("cc", "c++", "ldd", "readelf", "make"):
        executable(system / name, "exit 0\n")
    executable(system / "cmake", 'echo "cmake version 3.16.3"\n')
    for name in ("cmake", "cc", "ninja", "make"):
        executable(user_bin / name, 'echo "cmake version 3.30.0"\n')
    monkeypatch.setattr(provisioning, "SYSTEM_TOOL_DIRS", (str(system),), raising=False)
    monkeypatch.setenv("PATH", str(user_bin))
    tools = provisioning.build_tools()
    assert tools["cmake"] == str(system / "cmake") and tools["cc"] == str(system / "cc")
    assert tools["make"] == str(system / "make")
    assert provisioning._tool_environment(tools)["PATH"] == f"/usr/bin:/bin:{system}"


@POSIX
def test_too_old_system_cmake_gives_way_to_a_recent_one_in_path(tmp_path, monkeypatch):
    system, user_bin = tmp_path / "system-bin", tmp_path / "user-bin"
    executable(system / "cmake", 'echo "cmake version 3.13.4"\n')
    executable(user_bin / "cmake", 'echo "cmake version 3.27.1"\n')
    monkeypatch.setattr(provisioning, "SYSTEM_TOOL_DIRS", (str(system),), raising=False)
    monkeypatch.setenv("PATH", str(user_bin))
    assert provisioning.build_tools()["cmake"] == str(user_bin / "cmake")


@POSIX
def test_real_cmake_build_keeps_no_absolute_build_path(tmp_path):
    """Vrai cmake, vrai make, vrai compilateur : __FILE__ ne contient plus le dossier de construction (avec espace)."""
    tools = provisioning.build_tools()
    if not all(tools.get(name) for name in ("cmake", "cc", "make")):
        pytest.skip("cmake, make ou compilateur C absent : la réécriture des chemins n'est pas exercée.")
    build = tmp_path / "dossier de construction"
    source = build / "src/projet"
    source.mkdir(parents=True)
    (source / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)\nproject(essai C)\nadd_executable(essai main.c)\n",
                                           encoding="utf-8")
    (source / "main.c").write_text('#include <stdio.h>\nint main(void){puts(__FILE__);return 0;}\n', encoding="utf-8")
    env = {**provisioning._tool_environment(tools), "HOME": str(tmp_path), "CC": tools["cc"]}
    flags = provisioning.file_prefix_map_flags(build)
    subprocess.run([tools["cmake"], "-S", str(source), "-B", str(build / "out"), "-G", "Unix Makefiles",
                    f"-DCMAKE_MAKE_PROGRAM={tools['make']}", f"-DCMAKE_C_FLAGS={flags}"], env=env, check=True, capture_output=True)
    subprocess.run([tools["cmake"], "--build", str(build / "out")], env=env, check=True, capture_output=True)
    binary = build / "out/essai"
    printed = subprocess.run([str(binary)], capture_output=True, text=True, check=True).stdout.strip()
    assert printed == "./src/projet/main.c"
    assert str(build).encode() not in binary.read_bytes()
    assert provisioning.absolute_build_paths(binary, build) == []


@POSIX
def test_binary_quoting_the_build_root_is_refused(tmp_path):
    tools = provisioning.build_tools()
    if not tools.get("cc"):
        pytest.skip("Compilateur C absent.")
    build = tmp_path / "build"
    build.mkdir()
    program = tmp_path / "fuite.c"
    program.write_text(f'#include <stdio.h>\nint main(void){{puts("{build}/src/x.cpp");return 0;}}\n', encoding="utf-8")
    binary = tmp_path / "fuite"
    subprocess.run([tools["cc"], str(program), "-o", str(binary)], check=True)
    assert provisioning.absolute_build_paths(binary, build) == [str(build)]


SYSTEM_LDD = """\tlinux-vdso.so.1 (0x0000ffff8b6f9000)
\tlibtiff.so.5 => /lib/aarch64-linux-gnu/libtiff.so.5 (0x0000ffff8b5e0000)
\tlibstdc++.so.6 => /lib/aarch64-linux-gnu/libstdc++.so.6 (0x0000ffff8b3b0000)
\t/lib/ld-linux-aarch64.so.1 (0x0000ffff8b6c9000)
"""


def test_system_only_dependencies_are_recorded():
    records = provisioning.dynamic_dependencies(SYSTEM_LDD, (Path("/home/project"),))
    assert [record["name"] for record in records] == ["linux-vdso.so.1", "libtiff.so.5", "libstdc++.so.6", "ld-linux-aarch64.so.1"]
    assert records[0]["path"] is None and records[3]["path"] == "/lib/ld-linux-aarch64.so.1"


@pytest.mark.parametrize("line,reason", [
    ("\tliblept.so.5 => /usr/lib/aarch64-linux-gnu/liblept.so.5 (0x0000ffff8b000000)", "statiquement"),
    ("\tlibpng16.so.16 => not found", "libpng16.so.16 introuvable"),
    ("\tlibfoo.so.1 => /build/root/prefix/lib/libfoo.so.1 (0x0000ffff8b000000)", "depuis le projet ou la construction"),
    ("\tlibcudart.so.11.0 => /usr/local/cuda-11.4/lib64/libcudart.so.11.0 (0x0000ffff8b000000)", "hors des répertoires système"),
])
def test_dependencies_outside_the_system_are_refused(line, reason):
    with pytest.raises(ValueError, match=reason):
        provisioning.dynamic_dependencies(SYSTEM_LDD + line + "\n", (Path("/build/root"),))


@POSIX
def test_existing_destination_without_manifest_is_preserved(root):
    stray = root / ".runtime/bin/tesseract-5.4.0/notes.txt"
    stray.parent.mkdir(parents=True)
    stray.write_text("diagnostic\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Installation Tesseract incomplète"):
        provisioning.tesseract(PROFILE)
    assert stray.read_text(encoding="utf-8") == "diagnostic\n"


def test_unmarked_build_directory_is_never_deleted(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "personnel.txt").write_text("à conserver\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sans le marqueur"):
        provisioning._prepare_build_root(build)
    assert (build / "personnel.txt").read_text(encoding="utf-8") == "à conserver\n"
    (build / provisioning.BUILD_MARKER).write_text("", encoding="utf-8")
    provisioning._prepare_build_root(build)
    assert sorted(path.name for path in build.iterdir()) == [provisioning.BUILD_MARKER]


def test_source_archive_with_foreign_entries_is_refused(tmp_path):
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("tesseract-5.4.0/LICENSE", "autre/script.sh"):
            info = tarfile.TarInfo(name)
            info.size = 3
            bundle.addfile(info, io.BytesIO(b"abc"))
    with pytest.raises(ValueError, match="entrées hors de tesseract-5.4.0/"):
        provisioning._extract_source(archive, tmp_path / "src", "tesseract-5.4.0")
    assert not (tmp_path / "src").exists()


def test_profile_naming_a_path_command_is_refused(root):
    with pytest.raises(ValueError, match="seul un exécutable du projet est provisionné"):
        provisioning.build_tesseract({"pdf": {"tesseract_cmd": "tesseract"}})


def source_archive(path, top, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as bundle:
        for name, content in files.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size


@POSIX
def test_build_installs_verified_binary_then_reuses_it(root, monkeypatch):
    tools = provisioning.build_tools()
    if not all(tools.get(name) for name in ("cc", "ldd", "readelf")):
        pytest.skip("Compilateur C, ldd ou readelf absent : aucun binaire réel à vérifier.")
    downloads = root / ".runtime/cache/downloads"
    lept = source_archive(downloads / "leptonica-1.87.0.tar.gz", "leptonica-1.87.0",
                          {"leptonica-license.txt": b"BSD 2-clause\n", "CMakeLists.txt": b"project(leptonica)\n"})
    tess = source_archive(downloads / "tesseract-5.4.0-source.tar.gz", "tesseract-5.4.0",
                          {"LICENSE": b"Apache License 2.0\n", "VERSION": b"5.4.0\n"})
    write_lock(root, lock_entries(hashes=(lept[0], tess[0]), sizes=(lept[1], tess[1])))
    calls = []

    def compile_stub(source_dirs, build_root, prefix, found, jobs, log_dir):
        # Substitut nommé de la compilation CMake : un vrai binaire C, lié dynamiquement à la seule libc.
        calls.append({"sources": sorted(path.name for path in source_dirs.values()), "jobs": jobs})
        program = build_root / "fake.c"
        program.write_text('#include <stdio.h>\nint main(void){puts("tesseract 5.4.0");puts(" leptonica-1.87.0");return 0;}\n',
                           encoding="utf-8")
        (prefix / "bin").mkdir(parents=True)
        subprocess.run([found["cc"], str(program), "-o", str(prefix / "bin/tesseract")], check=True)
        return {"generator": "substitut de test", "steps": [], "configure_summary": {}}

    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    monkeypatch.setattr(provisioning, "compile_sources", compile_stub)
    result = provisioning.tesseract(PROFILE, offline=True)
    assert result["status"] == "built_from_source" and result["version"] == "tesseract 5.4.0"
    assert calls == [{"sources": ["leptonica-1.87.0", "tesseract-5.4.0"], "jobs": min(4, os.cpu_count() or 1)}]
    target = root / ".runtime/bin/tesseract-5.4.0/tesseract"
    manifest = json.loads((root / provisioning.BUILT_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["kind"] == "tesseract-source-build" and manifest["platform"] == platform_id()
    assert manifest["binary"] == {"path": ".runtime/bin/tesseract-5.4.0/tesseract", "sha256": artifacts.file_hash(target),
                                  "size": target.stat().st_size}
    assert [item["path"].rsplit("/", 1)[1] for item in manifest["files"]] == ["LICENSE", "leptonica-license.txt", "tesseract"]
    assert [(item["name"], item["sha256"]) for item in manifest["sources"]] == [("leptonica", lept[0]), ("tesseract", tess[0])]
    assert manifest["cmake_options"] == provisioning._cmake_options()
    assert manifest["version_output"].startswith("tesseract 5.4.0\n") and manifest["rpath"] == []
    assert any(item["name"].startswith("libc.so") for item in manifest["dynamic_dependencies"])
    assert all(item["path"] is None or item["path"].startswith(provisioning.SYSTEM_LIBRARY_DIRS)
               for item in manifest["dynamic_dependencies"])
    assert manifest["toolchain"]["cc"]["path"] == tools["cc"] and manifest["offline"] is True
    assert not list(target.parent.parent.glob("tesseract-5.4.0.tmp-*"))
    assert (root / provisioning.BUILD_DIR / provisioning.BUILD_MARKER).is_file()
    assert not (root / ".runtime/manifests/tesseract-installed-copy.json").exists()

    forbid(monkeypatch, "download", "compile_sources")
    assert provisioning.tesseract(PROFILE, offline=True)["status"] == "verified_built_copy"


TESSERACT_FILES = {"LICENSE": b"Apache License 2.0\n", "VERSION": b"5.4.0\n", "src/api/baseapi.cpp": b"// api\n"}
LEPTONICA_FILES = {"leptonica-license.txt": b"BSD 2-clause\n", "CMakeLists.txt": b"project(leptonica)\n"}


def regenerated_archive(path, top, files, level):
    """Même contenu, autre compression et autre date gzip : ce que produit une archive de tag régénérée."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as bundle:
        for name, content in files.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size, info.mtime = len(content), 1_700_000_000 + level
            bundle.addfile(info, io.BytesIO(content))
    import gzip
    path.write_bytes(gzip.compress(buffer.getvalue(), compresslevel=level, mtime=level))
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size


def expected_content(files, top):
    """Empreinte de contenu calculée indépendamment : listing au format sha256sum trié par chemin."""
    lines = sorted((f"{top}/{name}".encode(), f"{hashlib.sha256(data).hexdigest()}  {top}/{name}\n".encode())
                   for name, data in files.items())
    return hashlib.sha256(b"".join(line for _, line in lines)).hexdigest()


def prepared_sources(root, *, content=True):
    downloads = root / ".runtime/cache/downloads"
    lept = source_archive(downloads / "leptonica-1.87.0.tar.gz", "leptonica-1.87.0", LEPTONICA_FILES)
    tess = source_archive(downloads / "tesseract-5.4.0-source.tar.gz", "tesseract-5.4.0", TESSERACT_FILES)
    digest = expected_content(TESSERACT_FILES, "tesseract-5.4.0") if content else None
    write_lock(root, lock_entries(hashes=(lept[0], tess[0]), sizes=(lept[1], tess[1]), content=digest))
    return lept, tess, digest


def stub_compiler(calls, during=None):
    def compile_stub(source_dirs, build_root, prefix, found, jobs, log_dir):
        # Substitut nommé de la compilation CMake : un vrai binaire C, lié dynamiquement à la seule libc.
        calls.append({"sources": sorted(path.name for path in source_dirs.values()), "jobs": jobs})
        if during:
            during(build_root)
        program = build_root / "fake.c"
        program.write_text('#include <stdio.h>\nint main(void){puts("tesseract 5.4.0");puts(" leptonica-1.87.0");return 0;}\n',
                           encoding="utf-8")
        (prefix / "bin").mkdir(parents=True)
        subprocess.run([found["cc"], str(program), "-o", str(prefix / "bin/tesseract")], check=True)
        return {"generator": "substitut de test", "steps": [], "configure_summary": {}}
    return compile_stub


def require_real_tools():
    tools = provisioning.build_tools()
    if not all(tools.get(name) for name in ("cc", "ldd", "readelf")):
        pytest.skip("Compilateur C, ldd ou readelf absent : aucun binaire réel à vérifier.")
    return tools


HOLD_LOCK = """
import fcntl, sys
handle = open(sys.argv[1], "a+b")
fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
print("verrou pris", flush=True)
sys.stdin.read()
"""
PROBE_LOCK = """
import fcntl, sys
handle = open(sys.argv[1], "a+b")
try:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(3)
sys.exit(0)
"""


@POSIX
def test_build_is_refused_while_another_process_holds_the_build_lock(root, monkeypatch):
    lock = root / provisioning.BUILD_LOCK
    lock.parent.mkdir(parents=True)
    holder = subprocess.Popen([sys.executable, "-c", HOLD_LOCK, str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "verrou pris"
        monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
        forbid(monkeypatch, "download", "compile_sources")
        with pytest.raises(RuntimeError, match="déjà en cours") as error:
            provisioning.tesseract(PROFILE, offline=True)
        assert ".runtime/build/tesseract-5.4.0.lock" in str(error.value)
        assert not (root / ".runtime/bin").exists()
    finally:
        holder.communicate("", timeout=30)
    assert holder.returncode == 0


@POSIX
def test_build_lock_is_held_by_a_real_flock_during_compilation(root, monkeypatch):
    require_real_tools()
    prepared_sources(root)
    probes = []

    def probe(build_root):
        lock = root / provisioning.BUILD_LOCK
        probes.append(subprocess.run([sys.executable, "-c", PROBE_LOCK, str(lock)], timeout=30).returncode)

    calls = []
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    monkeypatch.setattr(provisioning, "compile_sources", stub_compiler(calls, during=probe))
    assert provisioning.tesseract(PROFILE, offline=True)["status"] == "built_from_source"
    assert probes == [3], "un second processus a obtenu le verrou pendant la compilation"
    # Verrou libéré à la fin : un autre processus l'obtient.
    assert subprocess.run([sys.executable, "-c", PROBE_LOCK, str(root / provisioning.BUILD_LOCK)], timeout=30).returncode == 0


@POSIX
def test_failed_copy_removes_the_staging_directory_and_installs_nothing(root, monkeypatch):
    require_real_tools()
    prepared_sources(root)
    calls = []
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    monkeypatch.setattr(provisioning, "compile_sources", stub_compiler(calls))
    original = shutil.copy2

    def failing_copy(source, destination, *args, **kwargs):
        if Path(destination).name == "leptonica-license.txt":
            raise OSError(28, "No space left on device")
        return original(source, destination, *args, **kwargs)

    monkeypatch.setattr(provisioning.shutil, "copy2", failing_copy)
    with pytest.raises(OSError, match="No space left"):
        provisioning.tesseract(PROFILE, offline=True)
    # Ni dossier de préparation `tesseract-5.4.0.tmp-*`, ni installation partielle.
    assert list((root / ".runtime/bin").iterdir()) == []
    assert not (root / provisioning.BUILT_MANIFEST).exists()
    # La relance après correction de la cause reconstruit sans intervention manuelle.
    monkeypatch.setattr(provisioning.shutil, "copy2", original)
    assert provisioning.tesseract(PROFILE, offline=True)["status"] == "built_from_source"


@POSIX
def test_incomplete_installation_names_both_paths_to_move(root):
    target = executable(root / ".runtime/bin/tesseract-5.4.0/tesseract", "exit 0\n")
    with pytest.raises(ValueError, match="Installation Tesseract incomplète") as error:
        provisioning.tesseract(PROFILE)
    message = str(error.value)
    assert ".runtime/bin/tesseract-5.4.0" in message and ".runtime/manifests/tesseract-built.json" in message
    assert "déplacer" in message
    assert target.is_file()


@POSIX
@pytest.mark.parametrize("alteration,reason", [
    ("empty_files", "liste des fichiers du manifeste"),
    ("missing_license", "liste des fichiers du manifeste"),
    ("extra_file", "notes.txt"),
    ("extra_directory", "tessdata"),
])
def test_reuse_requires_exactly_the_installed_file_set(root, monkeypatch, alteration, reason):
    target, manifest_path = installed_copy(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if alteration == "empty_files":
        manifest["files"] = []
    elif alteration == "missing_license":
        manifest["files"] = [item for item in manifest["files"] if not item["path"].endswith("leptonica-license.txt")]
    elif alteration == "extra_file":
        (target.parent / "notes.txt").write_text("ajout\n", encoding="utf-8")
    else:
        (target.parent / "tessdata").mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    forbid(monkeypatch, "download", "compile_sources")
    with pytest.raises(ValueError, match="aucun remplacement implicite") as error:
        provisioning.tesseract(PROFILE)
    assert reason in str(error.value)


@POSIX
def test_reuse_rechecks_the_leptonica_line(root, monkeypatch):
    installed_copy(root, leptonica_line=" leptonica-1.84.1")
    forbid(monkeypatch, "download", "compile_sources")
    with pytest.raises(ValueError, match="Leptonica 1.87.0"):
        provisioning.tesseract(PROFILE)


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("urlopen appelé en mode hors ligne")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


@POSIX
@pytest.mark.parametrize("archive", ["leptonica-1.87.0.tar.gz", "tesseract-5.4.0-source.tar.gz"])
def test_offline_build_with_a_missing_archive_fails_before_compilation(root, monkeypatch, no_network, archive):
    prepared_sources(root)
    (root / ".runtime/cache/downloads" / archive).unlink()
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    forbid(monkeypatch, "compile_sources", "_prepare_build_root")
    with pytest.raises(FileNotFoundError, match=archive):
        provisioning.tesseract(PROFILE, offline=True)


@POSIX
def test_offline_build_with_an_altered_leptonica_archive_fails_before_compilation(root, monkeypatch, no_network):
    prepared_sources(root)
    path = root / ".runtime/cache/downloads/leptonica-1.87.0.tar.gz"
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    forbid(monkeypatch, "compile_sources", "_prepare_build_root")
    with pytest.raises(FileNotFoundError, match="leptonica-1.87.0.tar.gz"):
        provisioning.tesseract(PROFILE, offline=True)


@POSIX
def test_offline_build_with_altered_tesseract_content_fails_before_compilation(root, monkeypatch, no_network):
    prepared_sources(root)
    archive = root / ".runtime/cache/downloads/tesseract-5.4.0-source.tar.gz"
    regenerated_archive(archive, "tesseract-5.4.0", {**TESSERACT_FILES, "VERSION": b"5.4.1\n"}, level=6)
    before = archive.read_bytes()
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    forbid(monkeypatch, "compile_sources")
    with pytest.raises(ValueError, match="contenu extrait de tesseract-5.4.0-source.tar.gz différent du verrou"):
        provisioning.tesseract(PROFILE, offline=True)
    assert archive.read_bytes() == before
    assert not (root / ".runtime/bin").exists()


def test_content_digest_is_the_sha256_of_the_sorted_sha256sum_listing(tmp_path):
    archive = tmp_path / "source.tar.gz"
    files = {"b.txt": b"b\n", "a/z.txt": b"z\n", "a.txt": b"a\n", "a/b/c.txt": b"c\n"}
    regenerated_archive(archive, "projet-1.0", files, level=9)
    provisioning._extract_source(archive, tmp_path / "src", "projet-1.0")
    digest = provisioning.source_content_sha256(tmp_path / "src", "projet-1.0")
    assert digest == expected_content(files, "projet-1.0")
    if shutil.which("sha256sum") and shutil.which("find"):
        listing = subprocess.run("find projet-1.0 -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum", shell=True,
                                 cwd=tmp_path / "src", capture_output=True, check=True).stdout
        assert digest == hashlib.sha256(listing).hexdigest()


def test_content_digest_refuses_links(tmp_path):
    top = tmp_path / "src/projet-1.0"
    top.mkdir(parents=True)
    (top / "a.txt").write_text("a\n", encoding="utf-8")
    (top / "lien").symlink_to("a.txt")
    with pytest.raises(ValueError, match="lien"):
        provisioning.source_content_sha256(tmp_path / "src", "projet-1.0")


@POSIX
def test_regenerated_cached_archive_with_identical_content_is_accepted_and_recorded(root, monkeypatch, no_network, capsys):
    require_real_tools()
    _, tess, digest = prepared_sources(root)
    archive = root / ".runtime/cache/downloads/tesseract-5.4.0-source.tar.gz"
    regenerated = regenerated_archive(archive, "tesseract-5.4.0", TESSERACT_FILES, level=1)
    assert regenerated[0] != tess[0]
    calls = []
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    monkeypatch.setattr(provisioning, "compile_sources", stub_compiler(calls))
    assert provisioning.tesseract(PROFILE, offline=True)["status"] == "built_from_source"
    manifest = json.loads((root / provisioning.BUILT_MANIFEST).read_text(encoding="utf-8"))
    record = {item["name"]: item for item in manifest["source_archives"]}["tesseract"]
    assert record == {"name": "tesseract", "archive": ".runtime/cache/downloads/tesseract-5.4.0-source.tar.gz",
                      "archive_sha256": regenerated[0], "lock_archive_sha256": tess[0], "archive_matches_lock": False,
                      "content_sha256": digest, "lock_content_sha256": digest, "content_matches_lock": True,
                      "origin": "cache"}
    lept_record = {item["name"]: item for item in manifest["source_archives"]}["leptonica"]
    assert lept_record["archive_matches_lock"] is True and lept_record["lock_content_sha256"] is None
    assert "empreinte d'archive différente du verrou, contenu extrait conforme" in capsys.readouterr().out
    # Le verrou n'a pas changé : la construction reste réutilisable.
    forbid(monkeypatch, "download", "compile_sources")
    assert provisioning.tesseract(PROFILE, offline=True)["status"] == "verified_built_copy"


class Served(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@POSIX
@pytest.mark.parametrize("same_content", [True, False])
def test_online_regenerated_archive_is_accepted_only_if_its_content_matches(root, monkeypatch, same_content):
    require_real_tools()
    _, tess, digest = prepared_sources(root)
    archive = root / ".runtime/cache/downloads/tesseract-5.4.0-source.tar.gz"
    archive.unlink()
    served_path = root / "served.tar.gz"
    files = TESSERACT_FILES if same_content else {**TESSERACT_FILES, "src/api/baseapi.cpp": b"// modifie\n"}
    served = regenerated_archive(served_path, "tesseract-5.4.0", files, level=1)
    requests = []

    def serve(request, timeout=None):
        requests.append(request.full_url)
        return Served(served_path.read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", serve)
    monkeypatch.setattr(artifacts.time, "sleep", lambda seconds: None)
    calls = []
    monkeypatch.setattr(provisioning, "missing_build_prerequisites", lambda found: [])
    monkeypatch.setattr(provisioning, "compile_sources", stub_compiler(calls))
    if same_content:
        assert provisioning.tesseract(PROFILE)["status"] == "built_from_source"
        # Trois essais de `download` refusés sur l'empreinte d'archive, puis un seul téléchargement vérifié par contenu.
        assert requests == ["https://example.invalid/tesseract.tar.gz"] * 4
        assert artifacts.file_hash(archive) == served[0]
        record = {item["name"]: item for item in json.loads((root / provisioning.BUILT_MANIFEST).read_text(
            encoding="utf-8"))["source_archives"]}["tesseract"]
        assert record["origin"] == "download" and record["archive_matches_lock"] is False
        assert record["content_matches_lock"] is True and record["archive_sha256"] == served[0]
    else:
        with pytest.raises(ValueError, match="contenu extrait de tesseract-5.4.0-source.tar.gz différent du verrou"):
            provisioning.tesseract(PROFILE)
        # Archive non conforme retirée du cache (téléchargement de cet appel), rien de compilé ni d'installé.
        assert calls == [] and not archive.exists()
        assert not list(archive.parent.glob("*.part"))
        assert not (root / ".runtime/bin").exists()


@pytest.mark.integration
@POSIX
def test_locked_tesseract_source_content_matches_the_cached_archive(tmp_path):
    """Empreinte de contenu du verrou réel recalculée sur l'archive en cache du poste, quand elle existe."""
    lock = json.loads((REAL_ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    entry = next(item for item in lock["groups"]["tesseract-source"] if item["publisher"] == "tesseract-ocr/tesseract")
    assert len(entry["content_sha256"]) == 64
    archive = REAL_ROOT / entry["target"]
    if not archive.is_file():
        pytest.skip("Archive Tesseract absente du cache de ce poste.")
    provisioning._extract_source(archive, tmp_path, "tesseract-5.4.0")
    assert provisioning.source_content_sha256(tmp_path, "tesseract-5.4.0") == entry["content_sha256"]


@pytest.fixture
def windows_installation(tmp_path, monkeypatch):
    """Branche Windows exécutée par simulation de plateforme, sans binaire Windows.

    Les mêmes essais passent sur la version précédente du module (sans `build_tesseract`) : ils fixent le
    comportement Windows d'origine.
    """
    base = (tmp_path / "root").resolve()
    base.mkdir()
    monkeypatch.setattr(provisioning, "ROOT", base)
    monkeypatch.setattr(provisioning, "sys", SimpleNamespace(platform="win32"), raising=False)
    forbid(monkeypatch, "build_tesseract", raising=False)
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    install = tmp_path / "LocalAppData/Programs/Tesseract-OCR"
    return base, install


def install_windows(install, version_line):
    executable(install / "tesseract.exe", f'echo "{version_line}"\necho " leptonica-1.84.1"\n')
    for name, content in (("libtesseract-5.dll", b"dll-1"), ("libleptonica-6.dll", b"dll-2"),
                          ("doc/LICENSE", b"Apache License 2.0"), ("tessdata/eng.traineddata", b"model")):
        (install / name).parent.mkdir(parents=True, exist_ok=True)
        (install / name).write_bytes(content)


@POSIX
def test_windows_branch_copies_the_installed_build_unchanged(windows_installation):
    base, install = windows_installation
    install_windows(install, "tesseract v5.4.0.20240606")
    result = provisioning.tesseract(PROFILE, offline=True)
    assert result == {"status": "copied_local_prerequisite", "files": 4, "publisher_provenance": "not_independently_authenticated"}
    manifest = json.loads((base / ".runtime/manifests/tesseract-installed-copy.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"source", "version_output", "origin", "files", "offline"}
    assert manifest["source"] == str(install.resolve()) and manifest["offline"] is True
    assert manifest["version_output"].startswith("tesseract v5.4.0.20240606")
    assert [item["path"] for item in manifest["files"]] == [
        ".runtime/bin/tesseract-5.4.0/tesseract.exe", ".runtime/bin/tesseract-5.4.0/libleptonica-6.dll",
        ".runtime/bin/tesseract-5.4.0/libtesseract-5.dll", ".runtime/bin/tesseract-5.4.0/doc/LICENSE"]
    assert not (base / ".runtime/bin/tesseract-5.4.0/tessdata").exists()
    assert not (base / ".runtime/manifests/tesseract-built.json").exists()
    assert provisioning.tesseract(PROFILE) == {"status": "verified_installed_copy",
                                              "publisher_provenance": "not_independently_authenticated"}
    (base / ".runtime/bin/tesseract-5.4.0/libtesseract-5.dll").write_bytes(b"altered")
    with pytest.raises(ValueError, match="Copie Tesseract non conforme au manifeste"):
        provisioning.tesseract(PROFILE)


@POSIX
def test_windows_branch_refuses_another_installed_version(windows_installation):
    base, install = windows_installation
    install_windows(install, "tesseract v5.3.4.20240503")
    with pytest.raises(ValueError, match="Tesseract5.4.0 du profil verrouillé"):
        provisioning.tesseract(PROFILE)
    assert not (base / ".runtime").exists()


@POSIX
def test_windows_branch_names_the_missing_installation(windows_installation):
    with pytest.raises(FileNotFoundError, match="Prérequis Tesseract5.4.0 Windows absent"):
        provisioning.tesseract(PROFILE)


@pytest.mark.integration
@POSIX
def test_real_built_tesseract_matches_its_manifest_and_languages():
    """Revérifie la construction réelle du poste : manifeste, binaire, version et langues du profil."""
    manifest_path = REAL_ROOT / provisioning.BUILT_MANIFEST
    if not manifest_path.is_file():
        pytest.skip("Tesseract non compilé sur ce poste : aucun manifeste de construction réel.")
    result = provisioning.build_tesseract(PROFILE)
    assert result["status"] == "verified_built_copy" and result["version"] == "tesseract 5.4.0"
    tessdata = REAL_ROOT / ".runtime/models/tessdata"
    if not all((tessdata / f"{name}.traineddata").is_file() for name in ("fra", "eng", "osd")):
        pytest.skip("Modèles tessdata non provisionnés.")
    binary = REAL_ROOT / result["binary"]
    listed = subprocess.run([str(binary), "--list-langs"], capture_output=True, text=True, check=True, timeout=30,
                            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TESSDATA_PREFIX": str(tessdata)})
    assert {"eng", "fra", "osd"} <= set(listed.stdout.splitlines()[1:])
