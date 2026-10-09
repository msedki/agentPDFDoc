"""Scripts POSIX de la distribution Linux (R26-KIT-01, R26-KIT-04) : syntaxe sous dash et bash --posix, contrôles
d'installer.sh, commande `atelier` de l'utilisateur.

`installer.sh` est exécuté réellement sur un kit factice : l'interpréteur du kit y est un script qui rend ses arguments
et LD_LIBRARY_PATH, et laisse un marqueur s'il est lancé (`kit_with_real_python` : un script qui passe la main au CPython 3.12
du dépôt, avec les vrais scripts de l'installateur) ; uname, getconf et ldd sont les doubles de
test_runtime_launchers_sh (architecture et bibliothèque C simulées) et `id` celui d'un compte root, placés en tête du PATH
du seul processus testé. La commande `atelier` est écrite par `linux_install.user_command_text` et exécutée sous sh et
dash avec un lanceur factice qui rend ses arguments.
"""

import hashlib
import importlib.machinery
import json
import os
import py_compile
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_runtime_launchers_sh import ABSENT, MUSL_GETCONF, MUSL_LDD, executable, fake_host
from tools.dist.build_kit import ROOT

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
SHELLS = [shell for shell in (["dash", "-n"], ["bash", "--posix", "-n"]) if shutil.which(shell[0])]


@pytest.mark.parametrize("shell", SHELLS, ids=lambda shell: shell[0])
@pytest.mark.parametrize("script", ["tools/dist/install.sh", "rag.sh", "bootstrap.sh"])
def test_posix_scripts_parse_under_dash_and_bash_posix(shell, script):
    result = subprocess.run([*shell, str(ROOT / script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("shell", SHELLS, ids=lambda shell: shell[0])
def test_the_generated_launcher_parses_and_quotes_unusual_paths(tmp_path, shell):
    from tools.dist.linux_install import launcher_text

    entry = {"kit_id": "0.1.0+abc-linux-aarch64-none-2b", "program": "/opt/a'b $x/0.1.0+abc", "python": ".runtime/python/k/bin/python3.12"}
    launcher = tmp_path / "atelier"
    launcher.write_text(launcher_text(entry, Path("/opt/a'b $x")), encoding="utf-8")
    assert subprocess.run([*shell, str(launcher)], capture_output=True, text=True, check=False).returncode == 0
    assert "'/opt/a'\"'\"'b $x/0.1.0+abc/.runtime/python/k/bin/python3.12'" in launcher.read_text(encoding="utf-8")
    # S06 : -S, ni site ni fichiers .pth ou sitecustomize du CPython du programme.
    assert "/bin/python3.12' -B -I -S -X utf8 " in launcher.read_text(encoding="utf-8")


def fake_kit(tmp_path: Path, *, arch: str = "aarch64", glibc: str = "2.29") -> Path:
    kit = tmp_path / "kit avec espace"
    manifest = {"format": "atelier-kit-v2", "kit_id": "k", "build_host": {"glibc": "2.31"},
                "target": {"arch": arch, "glibc_min": glibc, "reference_os": "Ubuntu 20.04.6 LTS aarch64 (Jetson Linux R35.4.1)"},
                "python": {"key": "cpython", "executable": ".runtime/python/cpython/bin/python3.12"}}
    (kit / "tools/dist").mkdir(parents=True)
    (kit / "kit-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "tools/dist/install.sh", kit / "installer.sh")
    shutil.copy2(ROOT / "tools/dist/install.sh", kit / "tools/dist/install.sh")
    executable(kit / ".runtime/python/cpython/bin/python3.12", "#!/bin/sh\n"
               f"touch '{tmp_path}/interpreteur-lance'\n"
               f"exec {sys.executable} -c 'import json,os,sys; print(json.dumps({{\"argv\": sys.argv[1:], "
               "\"ld\": os.environ.get(\"LD_LIBRARY_PATH\")}))' \"$@\"\n")
    (kit / ".runtime/python/cpython/lib").mkdir()
    (kit / ".runtime/python/cpython/lib/libpython3.12.so.1.0").write_bytes(b"\x7fELF libpython factice")
    for name in ("linux_install.py", "linux_kit.py", "build_kit.py"):
        (kit / "tools/dist" / name).write_text(f"# {name} factice\n", encoding="utf-8")
    write_links(kit, {})
    return kit


def write_sums(kit: Path, *, extra: tuple[str, ...] = ()) -> None:
    """SHA256SUMS du kit factice : interpréteur, libpython, scripts de l'installateur, installer.sh, SYMLINKS s'il existe
    (le fabricant l'écrit toujours) et les fichiers `extra`."""
    listed = [".runtime/python/cpython/bin/python3.12", ".runtime/python/cpython/lib/libpython3.12.so.1.0", "tools/dist/linux_install.py",
              "tools/dist/linux_kit.py", "tools/dist/build_kit.py", "installer.sh", *(["SYMLINKS"] if (kit / "SYMLINKS").exists() else []),
              *extra]
    (kit / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((kit / name).read_bytes()).hexdigest()}  {name}\n" for name in sorted(listed)),
                                    encoding="utf-8")


def write_links(kit: Path, links: dict[str, str], *, extra: tuple[str, ...] = ()) -> None:
    """SYMLINKS du kit factice (`chemin<TAB>cible`, une ligne par lien, comme le fabricant), puis SHA256SUMS, qui le couvre."""
    (kit / "SYMLINKS").write_text("".join(f"{path}\t{target}\n" for path, target in sorted(links.items())), encoding="utf-8")
    write_sums(kit, extra=extra)


def run(script: Path, *args: str, fakes: Path, ld: str | None = None):
    environment = {"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(script.parent), **({"LD_LIBRARY_PATH": ld} if ld else {})}
    return subprocess.run([str(script), *args], env=environment, capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize("entry", ["installer.sh", "tools/dist/install.sh"])
def test_installer_hands_over_to_the_kit_python_in_isolated_mode_without_ld_library_path(tmp_path, entry):
    kit = fake_kit(tmp_path)
    result = run(kit / entry, "install", "--destination", "/p", "--data-root", "/d", fakes=fake_host(tmp_path, "Linux", "aarch64"),
                 ld="/usr/local/cuda-11.4/lib64:")
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    resolved = str(kit.resolve())
    # S06 : -I (ni variables PYTHON*, ni site utilisateur) et -S (ni site, ni .pth, ni sitecustomize du CPython du kit) ;
    # R2-03 : aucun bytecode de __pycache__ lu (pycache_prefix sous /dev/null).
    assert observed["argv"] == ["-B", "-I", "-S", "-X", "utf8", "-X", "pycache_prefix=/dev/null", f"{resolved}/tools/dist/linux_install.py",
                                "--kit", resolved, "install", "--destination", "/p", "--data-root", "/d"]
    assert observed["ld"] is None


@pytest.mark.parametrize(("machine", "getconf", "ldd", "message"), [
    ("x86_64", None, None, "Ce kit vise Linux aarch64 ; ce poste est en x86_64."),
    ("aarch64", "#!/bin/sh\necho 'glibc 2.28'\n", None, "glibc 2.28 trop ancienne : ce kit exige la glibc 2.29 ou plus récente "
                                                     "(binaires et roues livrés ; poste de référence : Ubuntu 20.04.6 LTS aarch64 "
                                                     "(Jetson Linux R35.4.1), glibc 2.31). Rien n'a été installé."),
    ("aarch64", MUSL_GETCONF, MUSL_LDD, "Bibliothèque C musl détectée : ce kit exige la glibc 2.29 ou plus récente."),
    ("aarch64", ABSENT, ABSENT, "Bibliothèque C non reconnue"),
], ids=["architecture", "glibc-ancienne", "musl", "libc-inconnue"])
def test_installer_refuses_another_architecture_or_an_old_glibc_before_python(tmp_path, machine, getconf, ldd, message):
    kit = fake_kit(tmp_path)
    options = {key: value for key, value in (("getconf", getconf), ("ldd", ldd)) if value is not None}
    result = run(kit / "installer.sh", "install", fakes=fake_host(tmp_path, "Linux", machine, **options))
    assert result.returncode == 1 and result.stdout == "" and message in result.stderr


@pytest.mark.parametrize("altered", [".runtime/python/cpython/bin/python3.12", ".runtime/python/cpython/lib/libpython3.12.so.1.0",
                                     "tools/dist/linux_install.py"])
def test_installer_checks_the_kit_interpreter_and_scripts_before_running_them(tmp_path, altered):
    kit = fake_kit(tmp_path)
    path = kit / altered
    path.write_bytes(path.read_bytes() + "\n# altéré\n".encode())
    result = run(kit / "installer.sh", "status", "--destination", "/p", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == ""
    assert "Interpréteur ou installateur du kit altéré" in result.stderr


# Refus d'install.sh : fichier ajouté parmi les modules de l'installateur (QA3-01, S3-01), ou qui changerait les chemins de
# modules de l'interpréteur du kit à son démarrage (S3-02). Chaque message commence par « <chemin> ajouté au kit ».
ADDED_MODULE = ("ajouté au kit, absent de SHA256SUMS : fichier étranger parmi les modules de l'installateur. Recopier le kit "
                "depuis son archive ; rien n'a été exécuté.")
ADDED_STARTUP_FILE = ("ajouté au kit, absent de SHA256SUMS : il changerait les chemins de modules de l'interpréteur du kit à son "
                      "démarrage. Recopier le kit depuis son archive ; rien n'a été exécuté.")


@pytest.mark.parametrize("package", ["tools/__init__.py", "tools/dist/__init__.py"])
def test_installer_refuses_an_added_package_init_executed_at_import(tmp_path, package):
    # S06 : tools et tools/dist sont des paquets d'espace de noms ; un __init__.py ajouté ferait d'eux des paquets ordinaires.
    kit = fake_kit(tmp_path)
    (kit / package).write_text("print('ajouté, exécuté')\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{package} {ADDED_MODULE}"


EXTENSION = importlib.machinery.EXTENSION_SUFFIXES[0]  # .cpython-312-<arch>-linux-gnu.so : chargé avant le .py homonyme


@pytest.mark.parametrize("added", ["tools.py", "tools.pyc", f"tools{EXTENSION}", "tools/__init__.pyc", "tools/dist.py",
                                   f"tools/dist/linux_kit{EXTENSION}", "tools/dist/build_kit.abi3.so", "tools/dist/__init__.pyc",
                                   "tools/dist/linux_kit.pyc"])
def test_installer_refuses_an_added_module_that_python_would_import_before_any_check(tmp_path, added):
    # R2-03 : à la racine, un module tools masquerait le paquet d'espace de noms tools ; dans tools/, un module dist masquerait
    # tools.dist ; un module compilé (.so) est chargé avant le .py vérifié du même nom, un bytecode sans source (.pyc) tient
    # lieu de module. Refusés avant Python s'ils sont absents de SHA256SUMS.
    kit = fake_kit(tmp_path)
    (kit / added).write_bytes(b"\x7fELF ou bytecode ajout\xc3\xa9\n")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{added} {ADDED_MODULE}"


PACKAGE_FOLDERS = ["tools/dist/linux_kit/__init__.py", "tools/dist/build_kit/__init__.py", "tools/dist/linux_install/__init__.pyc",
                   f"tools/dist/notices/__init__{EXTENSION}", "tools/dist/kit_guide/__init__.abi3.so", "tools/autre/__init__.py"]


@pytest.mark.parametrize("added", PACKAGE_FOLDERS)
def test_installer_refuses_an_added_package_folder_among_the_installer_modules(tmp_path, added):
    # QA3-01, S3-01 : dans un même dossier, un paquet ordinaire (<nom>/__init__.*) est trouvé avant le module <nom>.py
    # (PEP 420) ; un dossier de paquet ajouté sous tools/ ou tools/dist/ est refusé avant Python.
    kit = fake_kit(tmp_path)
    (kit / added).parent.mkdir(parents=True)
    (kit / added).write_bytes(b"\x7fELF ou module ajout\xc3\xa9\n")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{added} {ADDED_MODULE}"


def test_a_listed_package_folder_is_checked_like_the_installer_scripts(tmp_path):
    kit = fake_kit(tmp_path)
    added = kit / "tools/dist/gabarits/__init__.py"
    added.parent.mkdir()
    added.write_text("# paquet livré\n", encoding="utf-8")
    sums = kit / "SHA256SUMS"
    sums.write_text(sums.read_text(encoding="utf-8") + f"{hashlib.sha256(added.read_bytes()).hexdigest()}  tools/dist/gabarits/__init__.py\n",
                    encoding="utf-8")
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    added.write_text("# paquet altéré\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and "Interpréteur ou installateur du kit altéré" in result.stderr


@pytest.mark.parametrize("added", ["tools/dist/notes.txt", "tools/dist/brouillon.py", "notes.so", "tarfile.py"])
def test_installer_ignores_an_added_file_that_no_import_reaches(tmp_path, added):
    # KIT4-24 : un fichier ajouté qu'aucun import de l'installateur n'atteint est ignoré (signalé, jamais copié), pas refusé.
    kit = fake_kit(tmp_path)
    (kit / added).write_text("ajouté\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "interpreteur-lance").exists()


def kit_with_real_python(tmp_path: Path) -> Path:
    """Kit factice dont l'interpréteur passe la main au CPython 3.12 du dépôt (celui que le kit livre) et dont les trois scripts
    de l'installateur sont les vrais : installer.sh lance réellement linux_install.py avec ses options."""
    kit = fake_kit(tmp_path)
    executable(kit / ".runtime/python/cpython/bin/python3.12", f'#!/bin/sh\nexec {shlex.quote(os.path.realpath(sys.executable))} "$@"\n')
    for name in ("linux_install.py", "linux_kit.py", "build_kit.py"):
        shutil.copy2(ROOT / "tools/dist" / name, kit / "tools/dist" / name)
    write_links(kit, {})
    return kit


def injected(witness: Path) -> str:
    """Code d'un module injecté : laisse un témoin, puis arrête le processus (code 99)."""
    return f"open({str(witness)!r}, 'w').write('exécuté')\nraise SystemExit(99)\n"


def test_a_standard_module_added_at_the_kit_root_is_never_imported_by_the_installer(tmp_path):
    # R2-03 (a) : la racine du kit est ajoutée après la bibliothèque standard (sys.path.append) : un tarfile.py ajouté au kit
    # n'est jamais importé à la place du module standard, que linux_kit importe au chargement.
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    (kit / "tarfile.py").write_text(injected(witness), encoding="utf-8")
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 0 and "Usage : installer.sh" in result.stdout, result.stderr


def test_bytecode_added_next_to_the_installer_scripts_is_never_read(tmp_path):
    # R2-03 (c) : un .pyc « unchecked-hash » de __pycache__ remplace la source vérifiée sans aucune comparaison. installer.sh
    # lance Python avec -X pycache_prefix=/dev/null : le bytecode est cherché sous /dev/null, où aucun fichier ne peut exister.
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    source = tmp_path / "source-injectee" / "linux_kit.py"
    source.parent.mkdir()
    source.write_text(injected(witness), encoding="utf-8")
    py_compile.compile(str(source), cfile=str(kit / "tools/dist/__pycache__" / f"linux_kit.{sys.implementation.cache_tag}.pyc"),
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH, doraise=True)
    # Témoin : sans cette option, le même interpréteur, avec les autres options de l'installateur, exécute ce bytecode.
    direct = subprocess.run([str(kit / ".runtime/python/cpython/bin/python3.12"), "-B", "-I", "-S", "-X", "utf8",
                             str(kit / "tools/dist/linux_install.py"), "--kit", str(kit), "--aide"],
                            capture_output=True, text=True, timeout=60, check=False)
    assert direct.returncode == 99 and witness.exists(), direct.stdout + direct.stderr
    witness.unlink()
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 0 and "Usage : installer.sh" in result.stdout, result.stderr


@pytest.mark.parametrize("added", ["tools/dist/linux_kit/__init__.py", "tools/dist/build_kit/__init__.py"])
def test_the_reviewer_package_folder_is_refused_before_the_installer_runs(tmp_path, added):
    # QA3-01, S3-01 (a), scénario des relecteurs : vrais scripts, CPython du dépôt ; le paquet ajouté s'exécutait (code 99).
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    (kit / added).parent.mkdir()
    (kit / added).write_text(injected(witness), encoding="utf-8")
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == f"{added} {ADDED_MODULE}"


INSTALLER_PYTHON_OPTIONS = ["-B", "-I", "-S", "-X", "utf8", "-X", "pycache_prefix=/dev/null"]  # options d'install.sh


@pytest.mark.parametrize("added", ["tools/dist/linux_kit/__init__.py", "tools/dist/build_kit/__init__.py",
                                   "tools/dist/linux_install/__init__.py", "tools/__init__.py", "tools/dist/__init__.py", "tools.py",
                                   "tools/dist.py", f"tools/dist/linux_kit{EXTENSION}"])
def test_the_installer_never_imports_a_kit_entry_by_name(tmp_path, added):
    # QA3-01, S3-01, cause : lancé comme installer.sh le lance mais sans ses refus, linux_install.py charge build_kit.py et
    # linux_kit.py par leur chemin ; aucun module, paquet ou module compilé ajouté à côté n'est importé à leur place.
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    (kit / added).parent.mkdir(parents=True, exist_ok=True)
    (kit / added).write_text(injected(witness), encoding="utf-8")
    result = subprocess.run([str(kit / ".runtime/python/cpython/bin/python3.12"), *INSTALLER_PYTHON_OPTIONS, str(kit / "tools/dist/linux_install.py"),
                             "--kit", str(kit), "--aide"], capture_output=True, text=True, timeout=60, check=False)
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 0 and "Usage : installer.sh" in result.stdout, result.stderr


STARTUP_FILES = [".runtime/python/cpython/bin/python3.12._pth", ".runtime/python/cpython/bin/pyvenv.cfg",
                 ".runtime/python/cpython/pyvenv.cfg", ".runtime/python/cpython/bin/pybuilddir.txt",
                 ".runtime/python/cpython/lib/python312.zip"]


@pytest.mark.parametrize("added", STARTUP_FILES)
def test_installer_refuses_an_added_interpreter_startup_file(tmp_path, added):
    # S3-02 : ._pth (remplace sys.path et l'emporte sur -I -S), pyvenv.cfg (clé home : préfixe déduit d'ailleurs),
    # pybuilddir.txt (préfixe de construction, observé sur CPython 3.12.14) et python312.zip (en tête de sys.path) sont lus
    # par l'interpréteur avant toute ligne de Python : refusés avant son lancement s'ils sont absents de SHA256SUMS.
    kit = fake_kit(tmp_path)
    (kit / added).write_text("../../../..\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{added} {ADDED_STARTUP_FILE}"


def test_a_listed_interpreter_startup_file_is_checked_like_the_interpreter(tmp_path):
    kit = fake_kit(tmp_path)
    added = kit / ".runtime/python/cpython/bin/pyvenv.cfg"
    added.write_text("home = /opt/python\n", encoding="utf-8")
    sums = kit / "SHA256SUMS"
    sums.write_text(sums.read_text(encoding="utf-8") + f"{hashlib.sha256(added.read_bytes()).hexdigest()}  "
                    ".runtime/python/cpython/bin/pyvenv.cfg\n", encoding="utf-8")
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    added.write_text("home = /ailleurs\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and "Interpréteur ou installateur du kit altéré" in result.stderr


def kit_with_a_copied_interpreter(tmp_path: Path) -> Path:
    """Double CopieDeCPython : kit factice dont l'interpréteur est une copie du binaire CPython 3.12 du dépôt, à l'emplacement
    du kit (Python lit ._pth et pyvenv.cfg à côté de son exécutable), bibliothèque standard du dépôt reliée par un lien, et vrais
    scripts de l'installateur."""
    kit = kit_with_real_python(tmp_path)
    real = Path(os.path.realpath(sys.executable))
    python = kit / ".runtime/python/cpython/bin/python3.12"
    python.unlink()
    shutil.copy2(real, python)
    standard = real.parent.parent / "lib/python3.12"
    os.symlink(standard, kit / ".runtime/python/cpython/lib/python3.12")
    # Lien déclaré comme le fabricant déclare les siens (une cible absolue n'existe que dans ce double).
    write_links(kit, {".runtime/python/cpython/lib/python3.12": str(standard)})
    return kit


def zip_with(path: Path, name: str, text: str) -> None:
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, text)


@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.base_prefix, "lib/python3.12/os.py")), reason="CPython 3.12 géré par uv")
@pytest.mark.parametrize("added", ["bin/python3.12._pth", "lib/python312.zip"])
def test_the_reviewer_startup_file_is_refused_before_the_interpreter_reads_it(tmp_path, added):
    # S3-02, scénario du relecteur (double FichierPth) : un tarfile.py placé par le fichier ajouté devant la bibliothèque
    # standard est exécuté par l'interpréteur du kit malgré -I -S (témoin) ; installer.sh refuse ce fichier avant de le lancer.
    kit = kit_with_a_copied_interpreter(tmp_path)
    witness = tmp_path / "temoin"
    path = kit / ".runtime/python/cpython" / added
    if added.endswith("._pth"):
        (kit / "tarfile.py").write_text(injected(witness), encoding="utf-8")
        path.write_text("../../../..\n../lib/python3.12\n../lib/python3.12/lib-dynload\n", encoding="utf-8")
    else:
        zip_with(path, "tarfile.py", injected(witness))
    direct = subprocess.run([str(kit / ".runtime/python/cpython/bin/python3.12"), *INSTALLER_PYTHON_OPTIONS,
                             str(kit / "tools/dist/linux_install.py"), "--kit", str(kit), "--aide"],
                            capture_output=True, text=True, timeout=60, check=False)
    assert direct.returncode == 99 and witness.exists(), direct.stdout + direct.stderr  # témoin : le fichier est lu
    witness.unlink()
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert not witness.exists(), result.stdout + result.stderr
    relative = f".runtime/python/cpython/{added}"
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == f"{relative} {ADDED_STARTUP_FILE}"


# --- R3S-01 : dossier de l'interpréteur du kit, lu par le chargeur dynamique et par Python avant toute vérification -------
# Le binaire CPython du kit porte DT_RPATH $ORIGIN/../lib : ld.so cherche ses bibliothèques (libpthread.so.0, libdl.so.2,
# libutil.so.1, libm.so.6, librt.so.1, libc.so.6) dans <CPython>/lib et ses sous-dossiers de capacités matérielles avant
# celles du système (ld.so(8)) ; Python lit sous <CPython> ses fichiers de démarrage et sa bibliothèque standard.
# installer.sh refuse toute entrée de ce dossier absente de SHA256SUMS et de SYMLINKS, hormis le bytecode des dossiers
# __pycache__ (compileall d'un programme installé), que Python ne lit pas sous -X pycache_prefix=/dev/null.
CPYTHON = ".runtime/python/cpython"
ADDED_TO_INTERPRETER = ("ajouté au kit, absent de SHA256SUMS et de SYMLINKS : fichier étranger dans le dossier de l'interpréteur du "
                        "kit, que le chargeur dynamique ou Python pourraient charger avant toute vérification. Recopier le kit depuis "
                        "son archive ; rien n'a été exécuté.")
ALTERED = ("Interpréteur ou installateur du kit altéré (empreintes différentes de SHA256SUMS) : recopier le kit depuis son archive ; "
           "rien n'a été exécuté.")
INTERPRETER_ENTRIES = ["lib/librt.so.1", "lib/tls/librt.so.1", "lib/aarch64/atomics/libm.so.6", "lib/glibc-hwcaps/x86-64-v3/libc.so.6",
                       "lib/libpython3.12.so", "lib/python3.12/tarfile/__init__.py", "lib/python3.12/tarfile.pyc",
                       "lib/python3.12/encodings/ajout.py", f"lib/python3.12/lib-dynload/_ajout{EXTENSION}",
                       "lib/python3.12/__pycache__/ajout.so", "lib/python3.12/__pycache__/ajout.py", "bin/lib/python3.12/os.py",
                       "bin/Modules/Setup.local", "bin/python3.12-ajout", "share/terminfo/x/ajout"]


@pytest.mark.parametrize("added", INTERPRETER_ENTRIES)
def test_installer_refuses_any_entry_added_to_the_interpreter_folder(tmp_path, added):
    kit = fake_kit(tmp_path)
    path = kit / CPYTHON / added
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fELF ou module ajout\xc3\xa9\n")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{CPYTHON}/{added} {ADDED_TO_INTERPRETER}"


@pytest.mark.parametrize("target", ["/lib/aarch64-linux-gnu/libc.so.6", "cible-absente.so"])
def test_installer_refuses_a_link_added_to_the_interpreter_folder(tmp_path, target):
    # Un lien ajouté, absent de SYMLINKS, est refusé de même, que sa cible existe ou non.
    kit = fake_kit(tmp_path)
    os.symlink(target, kit / CPYTHON / "lib/libc.so.6")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == f"{CPYTHON}/lib/libc.so.6 {ADDED_TO_INTERPRETER}"


def test_installer_accepts_listed_entries_and_the_bytecode_of_an_installed_program(tmp_path):
    # Entrées listées (SHA256SUMS, SYMLINKS), bytecode écrit par compileall dans un programme installé (dossiers __pycache__,
    # jamais lu sous -X pycache_prefix=/dev/null) et dossier vide n'arrêtent pas l'installateur.
    kit = fake_kit(tmp_path)
    root = kit / CPYTHON
    standard = root / "lib/python3.12"
    (standard / "encodings/__pycache__").mkdir(parents=True)
    (standard / "__pycache__").mkdir()
    (standard / "os.py").write_text("# os\n", encoding="utf-8")
    (standard / "__pycache__/os.cpython-312.pyc").write_bytes(b"bytecode de compileall")
    (standard / "encodings/__pycache__/__init__.cpython-312.opt-1.pyc").write_bytes(b"bytecode de compileall")
    (root / "lib/tls").mkdir()
    os.symlink("python3.12", root / "bin/python3")
    os.symlink("libpython3.12.so.1.0", root / "lib/libpython3.12.so")
    write_links(kit, {f"{CPYTHON}/bin/python3": "python3.12", f"{CPYTHON}/lib/libpython3.12.so": "libpython3.12.so.1.0"},
                extra=(f"{CPYTHON}/lib/python3.12/os.py",))
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "interpreteur-lance").exists()


@pytest.mark.parametrize("library", ["lib/libtcl9.0.so", "lib/thread3.0.6/libtcl9thread3.0.6.so", "lib/tls/libz.so.1"])
def test_a_listed_library_of_the_interpreter_folder_is_checked_like_the_interpreter(tmp_path, library):
    # Une bibliothèque listée sous <CPython>/lib (sous-dossiers compris) est contrôlée par empreinte avant le lancement.
    kit = fake_kit(tmp_path)
    path = kit / CPYTHON / library
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fELF bibliotheque livree")
    write_links(kit, {}, extra=(f"{CPYTHON}/{library}",))
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    (tmp_path / "interpreteur-lance").unlink()
    path.write_bytes(b"\x7fELF bibliotheque alteree")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == ALTERED
    assert not (tmp_path / "interpreteur-lance").exists()


def test_the_symlinks_list_is_checked_before_it_admits_a_link(tmp_path):
    # SYMLINKS admet les liens du dossier de l'interpréteur : il est lui-même contrôlé par empreinte, et doit figurer dans
    # SHA256SUMS (le fabricant l'y inscrit toujours).
    kit = fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    os.symlink("/lib/aarch64-linux-gnu/librt.so.1", kit / CPYTHON / "lib/librt.so.1")
    (kit / "SYMLINKS").write_text(f"{CPYTHON}/lib/librt.so.1\t/lib/aarch64-linux-gnu/librt.so.1\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == ALTERED
    sums = kit / "SHA256SUMS"
    sums.write_text("".join(line for line in sums.read_text(encoding="utf-8").splitlines(keepends=True) if not line.endswith("  SYMLINKS\n")),
                    encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == ("SYMLINKS absent de SHA256SUMS : kit incomplet ou altéré, le recopier depuis son archive ; rien n'a été "
                                     "exécuté.")
    assert not (tmp_path / "interpreteur-lance").exists()


# QA5-01 : os.geteuid n'existe pas sous Windows (« Availability: Unix ») ; cette expression est évaluée à la collecte, avant le
# refus de plateforme du module : hasattr d'abord.
@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root lit un dossier sans droit de lecture")
def test_an_unreadable_interpreter_folder_is_refused(tmp_path):
    # Un sous-dossier que find ne peut pas parcourir cacherait ses entrées : refus, jamais d'acceptation par défaut.
    kit = fake_kit(tmp_path)
    hidden = kit / CPYTHON / "lib/tls"
    hidden.mkdir()
    (hidden / "librt.so.1").write_bytes(b"\x7fEL")
    hidden.chmod(0)
    try:
        result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    finally:
        hidden.chmod(0o700)
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists()
    assert result.stderr.strip() == (f"Dossier de l'interpréteur du kit illisible ({CPYTHON}) : rétablir les droits de lecture du kit "
                                     "ou recopier le kit depuis son archive ; rien n'a été exécuté.")


def loader_tries(python: Path, candidate: Path) -> bool:
    """Le chargeur dynamique du poste cherche-t-il `candidate` au lancement de `python` ? Relevé par LD_DEBUG=libs (ld.so(8)) :
    lignes « trying file=… », chemins normalisés ($ORIGIN/../lib y reste écrit bin/../lib)."""
    probe = subprocess.run([str(python), "-I", "-S", "-c", "pass"], env={"PATH": "/usr/bin:/bin", "LD_DEBUG": "libs"},
                           capture_output=True, text=True, timeout=60, check=False)
    tried = {os.path.normpath(line.split("trying file=", 1)[1].strip()) for line in probe.stderr.splitlines() if "trying file=" in line}
    return os.path.normpath(candidate) in tried


@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.base_prefix, "lib/python3.12/os.py")), reason="CPython 3.12 géré par uv")
@pytest.mark.parametrize("added", ["lib/librt.so.1", "lib/tls/librt.so.1"])
def test_the_reviewer_library_is_refused_before_the_loader_reads_it(tmp_path, added):
    # R3S-01 (a), scénario du relecteur sans compilateur (double BibliothequeTronquee : quatre octets, non ELF) : placée là où
    # ld.so cherche les bibliothèques de l'interpréteur du kit, elle arrête le chargement (« file too short », code 127),
    # preuve que ld.so la lit avant toute ligne de Python. installer.sh la refuse avant de lancer l'interpréteur.
    kit = kit_with_a_copied_interpreter(tmp_path)
    python = kit / CPYTHON / "bin/python3.12"
    path = kit / CPYTHON / added
    searched = loader_tries(python, path)
    # lib/ est le DT_RPATH du binaire : toujours cherché ; lib/tls/, sous-dossier des capacités matérielles, l'est par la
    # glibc du poste de référence (2.31).
    assert searched or added != "lib/librt.so.1"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fEL")
    if searched:
        direct = subprocess.run([str(python), *INSTALLER_PYTHON_OPTIONS, "-c", "pass"], env={"PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=60, check=False)
        assert direct.returncode == 127 and "librt.so.1: file too short" in direct.stderr, direct.stderr  # témoin : lue par ld.so
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == f"{CPYTHON}/{added} {ADDED_TO_INTERPRETER}"


def kit_with_a_linked_standard_library(tmp_path: Path) -> Path:
    """Double FermeDeLiens : CopieDeCPython dont lib/python3.12 est un vrai dossier fait d'un lien par entrée de la bibliothèque
    standard du dépôt, chaque lien déclaré dans SYMLINKS ; un fichier peut y être ajouté sans rien écrire dans le vrai CPython."""
    kit = kit_with_a_copied_interpreter(tmp_path)
    standard = kit / CPYTHON / "lib/python3.12"
    real = Path(os.readlink(standard))
    standard.unlink()
    standard.mkdir()
    links = {}
    for entry in sorted(real.iterdir()):
        os.symlink(entry, standard / entry.name)
        links[f"{CPYTHON}/lib/python3.12/{entry.name}"] = str(entry)
    write_links(kit, links)
    return kit


@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.base_prefix, "lib/python3.12/os.py")), reason="CPython 3.12 géré par uv")
def test_the_reviewer_package_added_to_the_standard_library_is_refused(tmp_path):
    # R3S-01 (b) : un dossier de paquet tarfile/ ajouté à la bibliothèque standard du kit est trouvé avant tarfile.py
    # (PEP 420) et exécuté dès que linux_kit importe tarfile (témoin, code 99) ; installer.sh le refuse avant de lancer
    # l'interpréteur. Sans ajout, la même bibliothèque, faite de liens déclarés, est acceptée.
    kit = kit_with_a_linked_standard_library(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    accepted = run(kit / "installer.sh", "--aide", fakes=fakes)
    assert accepted.returncode == 0 and "Usage : installer.sh" in accepted.stdout, accepted.stderr
    witness = tmp_path / "temoin"
    added = kit / CPYTHON / "lib/python3.12/tarfile/__init__.py"
    added.parent.mkdir()
    added.write_text(injected(witness), encoding="utf-8")
    direct = subprocess.run([str(kit / CPYTHON / "bin/python3.12"), *INSTALLER_PYTHON_OPTIONS, str(kit / "tools/dist/linux_install.py"),
                             "--kit", str(kit), "--aide"], capture_output=True, text=True, timeout=60, check=False)
    assert direct.returncode == 99 and witness.exists(), direct.stdout + direct.stderr  # témoin : le paquet ajouté est exécuté
    witness.unlink()
    result = run(kit / "installer.sh", "--aide", fakes=fakes)
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == f"{CPYTHON}/lib/python3.12/tarfile/__init__.py {ADDED_TO_INTERPRETER}"


@pytest.mark.parametrize("element", [".", ""], ids=["point", "vide"])
def test_installer_never_looks_up_a_command_in_the_current_folder(tmp_path, element):
    # R3S-01, même classe : un élément « . » ou vide du PATH désigne le dossier courant, souvent le kit (./installer.sh) ; une
    # commande ajoutée à la racine du kit y serait exécutée avant toute vérification. installer.sh ne garde que les éléments
    # absolus du PATH.
    kit = fake_kit(tmp_path)
    witness = tmp_path / "temoin"
    for command in ("id", "dirname", "uname", "sed", "awk", "grep", "find", "getconf", "touch"):
        executable(kit / command, f"#!/bin/sh\necho {command} >> '{witness}'\nexit 0\n")
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    result = subprocess.run([str(kit / "installer.sh"), "status"], cwd=kit, env={"PATH": f"{element}:{fakes}:/usr/bin:/bin", "HOME": str(kit)},
                            capture_output=True, text=True, timeout=60, check=False)
    assert not witness.exists(), witness.read_text(encoding="utf-8")
    assert result.returncode == 0 and (tmp_path / "interpreteur-lance").exists(), result.stderr


def test_installer_checks_a_listed_package_init_like_its_scripts(tmp_path):
    kit = fake_kit(tmp_path)
    (kit / "tools/__init__.py").write_text("# paquet\n", encoding="utf-8")
    sums = kit / "SHA256SUMS"
    digest = hashlib.sha256((kit / "tools/__init__.py").read_bytes()).hexdigest()
    sums.write_text(sums.read_text(encoding="utf-8") + f"{digest}  tools/__init__.py\n", encoding="utf-8")
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    (kit / "tools/__init__.py").write_text("# paquet altéré\n", encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 1 and "Interpréteur ou installateur du kit altéré" in result.stderr


def test_texts_describe_the_targeted_verification_and_the_current_manifest():
    # REL-U19, S15, QA-13 : affirmations périmées depuis KIT4-24 (vérification ciblée, pas complète) et noms actuels.
    install_sh = (ROOT / "tools/dist/install.sh").read_text(encoding="utf-8")
    assert "La vérification complète du kit suit" not in install_sh and "vérification ciblée" in install_sh
    skill = (ROOT / ".agents/skills/linux-offline-kit/SKILL.md").read_text(encoding="utf-8")
    for stale in ("Après la vérification complète du kit", "reference_os_verified", "--output <kit>.tar", "vérifie ensuite le kit en entier"):
        assert stale not in skill, stale
    assert "`<kit_id>.tar.sha256`" in skill and "`<kit_id>.LISEZMOI.md`" in skill and "-B -I -S -X utf8" in skill


def test_installer_refuses_a_kit_whose_sums_omit_the_interpreter(tmp_path):
    kit = fake_kit(tmp_path)
    sums = kit / "SHA256SUMS"
    sums.write_text("".join(line for line in sums.read_text(encoding="utf-8").splitlines(keepends=True) if "bin/python3.12" not in line),
                    encoding="utf-8")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and "absent de SHA256SUMS" in result.stderr and result.stdout == ""


def test_installer_outside_a_kit_says_where_to_run_it(tmp_path):
    script = tmp_path / "seul/installer.sh"
    script.parent.mkdir()
    shutil.copy2(ROOT / "tools/dist/install.sh", script)
    result = run(script, "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 1 and "kit-manifest.json introuvable" in result.stderr


# --- KIT4-02 : refus de root avant Python ----------------------------------------------------------------------------------

ROOT_REFUSAL = ("Ne pas lancer l'installateur avec sudo ni en root : l'atelier s'installe pour votre compte. Relancer ./installer.sh "
                "sans sudo ; rien n'a été installé.")


@pytest.mark.parametrize("entry", ["installer.sh", "tools/dist/install.sh"])
def test_installer_refuses_root_before_python(tmp_path, entry):
    kit = fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 0\n')
    result = run(kit / entry, "install", fakes=fakes)
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == ROOT_REFUSAL
    assert not (tmp_path / "interpreteur-lance").exists()


def test_installer_runs_the_kit_python_for_an_ordinary_account(tmp_path):
    kit = fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 1000\n')
    result = run(kit / "installer.sh", "status", fakes=fakes)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "interpreteur-lance").exists() and json.loads(result.stdout)["argv"][-1] == "status"


def test_the_installer_comment_lists_every_command():
    header = (ROOT / "tools/dist/install.sh").read_text(encoding="utf-8").split("set -eu", 1)[0]
    from tools.dist.linux_install import INSTALLER_COMMANDS

    assert "R26" not in header and all(name in header for name in INSTALLER_COMMANDS)


# --- R4S-01 : type des entrées vérifiées, liens à la place d'un fichier ou d'un dossier ---------------------------------------
# Une ferme de liens ou une déduplication par liens symboliques (jdupes --link-soft, rdfind -makesymlinks) remplace un fichier
# ou un dossier du kit par un lien vers une copie identique : sha256sum suit le lien, mais le chargeur dynamique ($ORIGIN) et
# Python (préfixe, modules voisins) lisent alors l'arbre de la cible, que rien n'a vérifié. installer.sh exige un fichier
# ordinaire pour chaque entrée de SHA256SUMS, un lien pour chaque entrée de SYMLINKS, et aucun lien non déclaré parmi les
# dossiers de leur chemin.
LINK_INSTEAD_OF_FILE = ("est un lien, absent de SYMLINKS, à la place du fichier inscrit dans SHA256SUMS (copie par liens ou "
                        "déduplication) : le chargeur dynamique ou Python liraient alors les fichiers voisins de sa cible, non vérifiés. "
                        "Recopier le kit depuis son archive ; rien n'a été exécuté.")
LINK_INSTEAD_OF_FOLDER = ("est un lien, absent de SYMLINKS, à la place d'un dossier du kit (copie par liens ou déduplication) : "
                          "l'interpréteur ou l'installateur y liraient des fichiers non vérifiés. Recopier le kit depuis son archive ; "
                          "rien n'a été exécuté.")
NO_LONGER_LINK = ("n'est plus un lien, alors que SYMLINKS l'inscrit comme tel (copie qui a suivi les liens) : son contenu n'est "
                  "vérifié par rien. Recopier le kit depuis son archive ; rien n'a été exécuté.")
NOT_REGULAR = ("n'est pas un fichier ordinaire, alors que SHA256SUMS l'inscrit comme tel. Recopier le kit depuis son archive ; rien "
               "n'a été exécuté.")


def linked_to_a_copy(kit: Path, relative: str, elsewhere: Path) -> None:
    """Double LienVersCopie (ferme de liens, déduplication) : `relative`, fichier ou dossier, déplacé hors du kit à l'identique
    (mêmes octets, mêmes droits), puis remplacé par un lien absolu vers cette copie."""
    copy = elsewhere / relative
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(kit / relative, copy)
    os.symlink(copy, kit / relative)


def refused_before_python(result: subprocess.CompletedProcess, tmp_path: Path, message: str) -> None:
    assert result.returncode == 1 and result.stdout == "" and not (tmp_path / "interpreteur-lance").exists(), result.stderr
    assert result.stderr.strip() == message


STARTUP_PYVENV = f"{CPYTHON}/bin/pyvenv.cfg"
VERIFIED_FILES = [f"{CPYTHON}/bin/python3.12", f"{CPYTHON}/lib/libpython3.12.so.1.0", "tools/dist/linux_install.py", "tools/dist/linux_kit.py",
                  "tools/dist/build_kit.py", "SYMLINKS", STARTUP_PYVENV, "tools/__init__.py"]


@pytest.mark.parametrize("relative", VERIFIED_FILES)
def test_a_verified_file_replaced_by_a_link_to_an_identical_copy_is_refused(tmp_path, relative):
    kit = fake_kit(tmp_path)
    if relative in (STARTUP_PYVENV, "tools/__init__.py"):
        (kit / relative).write_text("# fichier livré\n", encoding="utf-8")
        write_links(kit, {}, extra=(relative,))
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0  # témoin : le même kit, sans lien, est accepté
    (tmp_path / "interpreteur-lance").unlink()
    linked_to_a_copy(kit, relative, tmp_path / "copie-identique")
    refused_before_python(run(kit / "installer.sh", "status", fakes=fakes), tmp_path, f"{relative} {LINK_INSTEAD_OF_FILE}")


@pytest.mark.parametrize("folder", ["tools", "tools/dist", ".runtime", ".runtime/python", CPYTHON, f"{CPYTHON}/bin", f"{CPYTHON}/lib"])
def test_a_folder_of_verified_files_replaced_by_a_link_is_refused(tmp_path, folder):
    kit = fake_kit(tmp_path)
    linked_to_a_copy(kit, folder, tmp_path / "copie-identique")
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    refused_before_python(result, tmp_path, f"{folder} {LINK_INSTEAD_OF_FOLDER}")


def test_a_folder_link_declared_in_symlinks_is_followed(tmp_path):
    # Témoin : un lien de dossier déclaré dans SYMLINKS (lien de version de CPython, par exemple) reste admis.
    kit = fake_kit(tmp_path)
    os.rename(kit / CPYTHON, kit / f"{CPYTHON}-3.12.14")
    os.symlink("cpython-3.12.14", kit / CPYTHON)
    write_links(kit, {CPYTHON: "cpython-3.12.14"})
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert result.returncode == 0 and (tmp_path / "interpreteur-lance").exists(), result.stderr


def test_a_declared_link_turned_into_a_file_is_refused(tmp_path):
    # R4S-01 (c) : un chemin de SYMLINKS devenu fichier ordinaire n'est haché par rien ; refusé.
    kit = fake_kit(tmp_path)
    library = kit / CPYTHON / "lib/libpython3.12.so"
    os.symlink("libpython3.12.so.1.0", library)
    write_links(kit, {f"{CPYTHON}/lib/libpython3.12.so": "libpython3.12.so.1.0"})
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    (tmp_path / "interpreteur-lance").unlink()
    library.unlink()
    library.write_bytes(b"\x7fELF contenu quelconque, jamais hach\xc3\xa9")
    refused_before_python(run(kit / "installer.sh", "status", fakes=fakes), tmp_path, f"{CPYTHON}/lib/libpython3.12.so {NO_LONGER_LINK}")


def test_a_declared_folder_link_turned_into_a_copied_folder_is_refused(tmp_path):
    # Copie qui a suivi les liens (cp -rL) : le lien déclaré devient un dossier ; il est nommé, et non son premier fichier.
    kit = fake_kit(tmp_path)
    standard = kit / CPYTHON / "lib/python3.12.14"
    standard.mkdir()
    (standard / "os.py").write_text("# os\n", encoding="utf-8")
    os.symlink("python3.12.14", kit / CPYTHON / "lib/python3.12")
    write_links(kit, {f"{CPYTHON}/lib/python3.12": "python3.12.14"}, extra=(f"{CPYTHON}/lib/python3.12.14/os.py",))
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    (tmp_path / "interpreteur-lance").unlink()
    (kit / CPYTHON / "lib/python3.12").unlink()
    shutil.copytree(standard, kit / CPYTHON / "lib/python3.12")
    refused_before_python(run(kit / "installer.sh", "status", fakes=fakes), tmp_path, f"{CPYTHON}/lib/python3.12 {NO_LONGER_LINK}")


@pytest.mark.parametrize(("relative", "kind"), [(f"{CPYTHON}/lib/python3.12/os.py", "tube"), ("tools/dist/linux_kit.py", "dossier"),
                                                (f"{CPYTHON}/lib/libpython3.12.so.1.0", "dossier vide"),
                                                (f"{CPYTHON}/lib/python3.12/os.py", "dossier vide")])
def test_a_listed_file_replaced_by_a_special_file_or_a_folder_is_refused(tmp_path, relative, kind):
    kit = fake_kit(tmp_path)
    path = kit / relative
    if relative.endswith("os.py"):
        path.parent.mkdir(parents=True)
        path.write_text("# os\n", encoding="utf-8")
        write_links(kit, {}, extra=(relative,))
    path.unlink()
    # U6-06, QA6-01 (double FichierInscritDevenuDossier) : un fichier inscrit sous <CPython> remplacé par un dossier vide n'était
    # ni haché ni refusé (code 0, interpréteur lancé).
    if kind in ("dossier", "dossier vide"):
        path.mkdir()
    elif sys.platform != "win32":  # os.mkfifo n'existe que sous Unix ; ce module est sauté sous Windows (mypy --platform win32)
        os.mkfifo(path)
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    refused_before_python(result, tmp_path, f"{relative} {NOT_REGULAR}")


def test_an_interpreter_without_execute_permission_is_refused_with_its_cause(tmp_path):
    # Droits perdus à la copie (volume sans droits Unix) : cause nommée, au lieu de « Permission denied » (code 126).
    kit = fake_kit(tmp_path)
    (kit / CPYTHON / "bin/python3.12").chmod(0o644)
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    refused_before_python(result, tmp_path, f"Interpréteur du kit sans droit d'exécution ({CPYTHON}/bin/python3.12) : droits perdus à la "
                                            "copie ou à l'extraction, recopier le kit depuis son archive ; rien n'a été exécuté.")


def other_cpython_tree(tmp_path: Path, witness: Path, *, loader_library: bool) -> Path:
    """Double AutreArbreCPython : copie du binaire CPython 3.12 du dépôt (mêmes octets que celui de CopieDeCPython) hors du kit,
    bibliothèque standard en ferme de liens vers celle du dépôt, plus un paquet tarfile/ injecté, ou une bibliothèque du
    chargeur tronquée dans son lib/ (double BibliothequeTronquee : quatre octets, non ELF)."""
    other = tmp_path / "autre-cpython"
    (other / "bin").mkdir(parents=True)
    real = Path(os.path.realpath(sys.executable))
    shutil.copy2(real, other / "bin/python3.12")
    standard = other / "lib/python3.12"
    standard.mkdir(parents=True)
    for entry in sorted((real.parent.parent / "lib/python3.12").iterdir()):
        os.symlink(entry, standard / entry.name)
    if loader_library:
        (other / "lib/librt.so.1").write_bytes(b"\x7fEL")
    else:
        (standard / "tarfile").mkdir()
        (standard / "tarfile/__init__.py").write_text(injected(witness), encoding="utf-8")
    return other


@pytest.mark.skipif(not os.path.isfile(os.path.join(sys.base_prefix, "lib/python3.12/os.py")), reason="CPython 3.12 géré par uv")
@pytest.mark.parametrize("variant", ["paquet-tarfile", "bibliotheque-du-chargeur"])
def test_the_reviewer_interpreter_link_to_another_tree_is_refused(tmp_path, variant):
    # R4S-01 (a), scénario du relecteur : l'interpréteur listé devient un lien vers un binaire identique hors du kit. Lancé par
    # ce lien, il prend sa bibliothèque standard et ses bibliothèques ($ORIGIN) dans l'arbre de la cible (témoins directs) ;
    # installer.sh refuse le lien avant de le lancer.
    kit = kit_with_a_copied_interpreter(tmp_path)
    witness = tmp_path / "temoin"
    other = other_cpython_tree(tmp_path, witness, loader_library=variant == "bibliotheque-du-chargeur")
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    accepted = run(kit / "installer.sh", "--aide", fakes=fakes)
    assert accepted.returncode == 0 and "Usage : installer.sh" in accepted.stdout, accepted.stderr  # témoin sans lien
    python = kit / CPYTHON / "bin/python3.12"
    python.unlink()
    os.symlink(other / "bin/python3.12", python)
    direct = subprocess.run([str(python), *INSTALLER_PYTHON_OPTIONS, str(kit / "tools/dist/linux_install.py"), "--kit", str(kit), "--aide"],
                            env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=60, check=False)
    if variant == "paquet-tarfile":
        assert direct.returncode == 99 and witness.exists(), direct.stdout + direct.stderr
        witness.unlink()
    else:
        assert direct.returncode == 127 and "librt.so.1: file too short" in direct.stderr, direct.stderr
    result = run(kit / "installer.sh", "--aide", fakes=fakes)
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == f"{CPYTHON}/bin/python3.12 {LINK_INSTEAD_OF_FILE}"


def other_installer_tree(tmp_path: Path, witness: Path) -> Path:
    """Double AutreArbreInstallateur : linux_install.py identique à celui du dépôt, à côté d'un build_kit.py et d'un linux_kit.py
    injectés (témoin, puis code 99), hors du kit."""
    other = tmp_path / "autre-installateur/tools/dist"
    other.mkdir(parents=True)
    shutil.copy2(ROOT / "tools/dist/linux_install.py", other / "linux_install.py")
    for name in ("build_kit.py", "linux_kit.py"):
        (other / name).write_text(injected(witness), encoding="utf-8")
    return other / "linux_install.py"


def test_the_reviewer_installer_script_link_to_another_tree_is_refused(tmp_path):
    # R4S-01 (b) : linux_install.py remplacé par un lien vers une copie identique placée à côté de modules injectés.
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    script = kit / "tools/dist/linux_install.py"
    script.unlink()
    os.symlink(other_installer_tree(tmp_path, witness), script)
    result = run(kit / "installer.sh", "--aide", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 1 and result.stdout == "" and result.stderr.strip() == f"tools/dist/linux_install.py {LINK_INSTEAD_OF_FILE}"


def test_the_installer_loads_the_modules_next_to_the_path_it_was_run_from(tmp_path):
    # R4S-01 (3) : lancé par un lien, sans les refus d'installer.sh, linux_install.py charge build_kit.py et linux_kit.py à côté
    # du chemin qu'il a reçu (os.path.abspath, liens non résolus) : ceux qu'installer.sh a hachés, jamais ceux de la cible.
    kit = kit_with_real_python(tmp_path)
    witness = tmp_path / "temoin"
    script = kit / "tools/dist/linux_install.py"
    script.unlink()
    os.symlink(other_installer_tree(tmp_path, witness), script)
    result = subprocess.run([str(kit / CPYTHON / "bin/python3.12"), *INSTALLER_PYTHON_OPTIONS, str(script), "--kit", str(kit), "--aide"],
                            capture_output=True, text=True, timeout=60, check=False)
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 0 and "Usage : installer.sh" in result.stdout, result.stderr


def test_the_profiles_script_loads_the_runtime_modules_next_to_the_path_it_was_run_from(tmp_path):
    # R4S-01 (3), même motif pour linux_profiles.py : services/runtime est pris sous la racine du chemin reçu.
    program = tmp_path / "programme"
    (program / "tools/dist").mkdir(parents=True)
    (program / "services/runtime").mkdir(parents=True)
    other = tmp_path / "autre-programme"
    (other / "tools/dist").mkdir(parents=True)
    (other / "services/runtime").mkdir(parents=True)
    witness = tmp_path / "temoin"
    for name in ("platforms", "accelerator", "artifacts"):
        shutil.copy2(ROOT / "services/runtime" / f"{name}.py", program / "services/runtime" / f"{name}.py")
        (other / "services/runtime" / f"{name}.py").write_text(injected(witness), encoding="utf-8")
    shutil.copy2(ROOT / "tools/dist/linux_profiles.py", other / "tools/dist/linux_profiles.py")
    os.symlink(other / "tools/dist/linux_profiles.py", program / "tools/dist/linux_profiles.py")
    data = tmp_path / "donnees"
    profile = data / "profile.yaml"
    data.mkdir()
    profile.write_text(f"app:\n  data_dir: {data}\n  port: 8785\nqdrant:\n  url: http://127.0.0.1:6333\nllm:\n  base_url: "
                       "http://127.0.0.1:11434\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", "-I", str(program / "tools/dist/linux_profiles.py"), "paths", "--profile", str(profile)],
                            capture_output=True, text=True, timeout=60, check=False)
    assert not witness.exists(), result.stdout + result.stderr
    assert result.returncode == 0 and json.loads(result.stdout)["locations"]["app.data_dir"] == str(data.resolve()), result.stderr


# --- U5-03, U6-02 : refus d'un programme installé, dont l'action dépend de ce que le pointeur dit de cette version ------------
# Réinstaller depuis le kit (dépannage, section 10.4) ne vaut que pour la version courante : la procédure retire toutes les
# versions et reprend les données actives. Une version précédente, abandonnée ou non désignée se retire par l'installateur de
# la version courante, jamais en la réinstallant.
POINTER_FORMAT = "atelier-installation-v1"
OTHER_VERSION = "0.1.0+fedcba987654-linux-aarch64-none-2b4b"  # version courante quand le programme essayé ne l'est pas
ROLES = ("courante", "precedente", "abandonnee", "non-designee", "illisible")
REPAIR_TITLE = "Réparer un programme installé avec le seul kit de sa version"


def write_pointer(destination: Path, program: Path, role: str) -> None:
    """Double nommé PointeurDeDesignation : installation.json de `destination`, écrit comme l'installateur l'écrit (json.dumps,
    indentation 2, ensure_ascii=False), historique compris, qui désigne `program` comme version courante (« courante »),
    précédente (« precedente »), précédente abandonnée par un retour arrière (« abandonnee »), ou ne le désigne pas
    (« non-designee » : une autre version est courante, `program` ne figure plus qu'à l'historique) ; « illisible » : pointeur
    d'un autre format (« {} »)."""
    data = destination.parent / "donnees"

    def entry(kit_id: str, **extra: object) -> dict:
        return {"kit_id": kit_id, "program": str(destination / kit_id), "python": f"{CPYTHON}/bin/python3.12", "data_root": str(data),
                "profile": str(data / "profile.yaml"), "profiles": {"qwen3.5:4b": str(data / "profile.yaml")}, "model": "qwen3.5:4b",
                "started_on_data": True, **extra}

    own, other = entry(program.name), entry(OTHER_VERSION, backup=str(data / "backups/20261007T090000Z-b1"))
    designations = {"courante": (own, None), "precedente": (other, own), "abandonnee": (other, {**own, "rolled_back": True}),
                    "non-designee": (other, None)}
    text = "{}\n"
    if role != "illisible":
        current, previous = designations[role]
        history = [{"event": "install", "kit_id": program.name, "at_utc": "2026-10-07T08:00:00+00:00"},
                   {"event": "update", "kit_id": OTHER_VERSION, "from": program.name, "at_utc": "2026-10-07T09:00:00+00:00"}]
        text = json.dumps({"format": POINTER_FORMAT, "destination": str(destination), "history": history, "current": current,
                           "previous": previous, "menu": True, "menu_entry": None, "user_command": None}, ensure_ascii=False, indent=2) + "\n"
    (destination / "installation.json").write_text(text, encoding="utf-8")


def installed_program(tmp_path: Path, role: str = "courante", *, arch: str = "aarch64") -> Path:
    """Double ProgrammeInstalleFactice : kit factice placé comme une version installée, <destination>/<kit_id>, avec le pointeur
    installation.json dans la destination (critère de rag.sh et d'installer.sh), qui le désigne selon `role` (write_pointer)."""
    kit = fake_kit(tmp_path, arch=arch)
    destination = tmp_path / "programmes atelier"
    destination.mkdir()
    program = destination / "0.1.0+abc-linux-aarch64-none-2b4b"
    shutil.move(kit, program)
    write_pointer(destination, program, role)
    return program


def installed_action(program: Path, role: str = "courante") -> str:
    """Action qu'install.sh donne pour un programme installé selon ce que le pointeur de sa destination dit de lui (U6-02) ;
    destination physique (pwd -P), écrite comme shlex.quote l'écrit."""
    destination = os.path.realpath(program.parent)
    status = f"« <dossier du kit>/installer.sh status --destination {shlex.quote(destination)} »"
    reinstall = f"réinstaller cette version depuis le dossier de son kit (docs/exploitation/DEPANNAGE.md, section 10.4, « {REPAIR_TITLE} »"
    removal = f"« {shlex.quote(os.path.join(destination, OTHER_VERSION, 'installer.sh'))} uninstall --kit-id {program.name} »"
    return {
        "courante": (f"{reinstall}, à partir de {status}), ou mettre à jour l'installation depuis le kit d'une autre version (« <dossier de "
                     f"cet autre kit>/installer.sh update --destination {shlex.quote(destination)} »)"),
        "precedente": ("retirer cette version (version précédente de l'installation, à ne pas réinstaller ; le retour arrière ne sera "
                       f"plus possible) par {removal}"),
        "abandonnee": f"retirer cette version (abandonnée par un retour arrière, à ne pas réinstaller) par {removal}",
        "non-designee": f"retirer cette version (que le pointeur de l'installation ne désigne pas, à ne pas réinstaller) par {removal}",
        "illisible": (f"si {status} montre que {program.name} est la version courante, {reinstall}) ; sinon, la retirer sans la "
                      f"réinstaller par « <programme de la version courante>/installer.sh uninstall --kit-id {program.name} »"),
    }[role]


@pytest.mark.parametrize("role", ROLES)
def test_an_installed_program_refusal_gives_the_action_that_fits_its_designation(tmp_path, role):
    # U6-02 (preuves 04, 05 et 07 de la revue utilisateur) : la réinstallation selon la section 10.4 retire toutes les versions
    # et reprend les données actives ; proposée pour une version précédente ou abandonnée, elle annulait la mise à jour ou le
    # retour arrière. L'action suit le pointeur : version courante, réinstaller (ou mettre à jour depuis un autre kit) ; sinon,
    # retirer cette version par l'installateur de la version courante. L'historique du pointeur, qui nomme aussi cette version,
    # ne vaut pas désignation.
    program = installed_program(tmp_path, role)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(program / "installer.sh", "status", fakes=fakes).returncode == 0  # témoin : programme intact accepté
    (tmp_path / "interpreteur-lance").unlink()
    action = installed_action(program, role)
    added = program / CPYTHON / "lib/NOTES.txt"
    added.write_text("ajouté par erreur\n", encoding="utf-8")
    refused_before_python(run(program / "installer.sh", "status", fakes=fakes), tmp_path, (
        f"{CPYTHON}/lib/NOTES.txt ajouté à ce programme installé, absent de SHA256SUMS et de SYMLINKS : fichier étranger dans le dossier de "
        "l'interpréteur de ce programme installé, que le chargeur dynamique ou Python pourraient charger avant toute vérification. Le "
        f"retirer s'il a été ajouté par erreur, sinon {action} ; rien n'a été exécuté."))
    added.unlink()
    (program / "tools/dist/linux_install.py").write_text("# altéré\n", encoding="utf-8")
    refused_before_python(run(program / "installer.sh", "status", fakes=fakes), tmp_path, (
        f"Interpréteur ou installateur de ce programme installé altéré (empreintes différentes de SHA256SUMS) : {action} ; rien n'a été "
        "exécuté."))


@pytest.mark.parametrize("case", ["interpreteur", "module", "demarrage", "altere", "lien", "illisible"])
def test_an_installed_program_refusal_gives_the_action_for_an_installed_program(tmp_path, case):
    program = installed_program(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(program / "installer.sh", "status", fakes=fakes).returncode == 0  # témoin : programme intact accepté
    (tmp_path / "interpreteur-lance").unlink()
    action = installed_action(program)
    remove = f"Le retirer s'il a été ajouté par erreur, sinon {action} ; rien n'a été exécuté."
    hidden = program / CPYTHON / "lib/tls"
    if case == "interpreteur":
        (program / CPYTHON / "lib/librt.so.1").write_bytes(b"\x7fEL")
        expected = (f"{CPYTHON}/lib/librt.so.1 ajouté à ce programme installé, absent de SHA256SUMS et de SYMLINKS : fichier étranger "
                    "dans le dossier de l'interpréteur de ce programme installé, que le chargeur dynamique ou Python pourraient charger "
                    f"avant toute vérification. {remove}")
    elif case == "module":
        (program / "tools/dist/__init__.py").write_text("print('ajouté')\n", encoding="utf-8")
        expected = f"tools/dist/__init__.py ajouté à ce programme installé, absent de SHA256SUMS : fichier étranger parmi les modules de l'installateur. {remove}"
    elif case == "demarrage":
        (program / STARTUP_PYVENV).write_text("home = /ailleurs\n", encoding="utf-8")
        expected = (f"{STARTUP_PYVENV} ajouté à ce programme installé, absent de SHA256SUMS : il changerait les chemins de modules de "
                    f"l'interpréteur de ce programme installé à son démarrage. {remove}")
    elif case == "altere":
        (program / "tools/dist/linux_install.py").write_text("# altéré\n", encoding="utf-8")
        expected = (f"Interpréteur ou installateur de ce programme installé altéré (empreintes différentes de SHA256SUMS) : {action} ; rien "
                    "n'a été exécuté.")
    elif case == "lien":
        linked_to_a_copy(program, "tools/dist/linux_kit.py", tmp_path / "copie-identique")
        expected = ("tools/dist/linux_kit.py est un lien, absent de SYMLINKS, à la place du fichier inscrit dans SHA256SUMS (copie par "
                    "liens ou déduplication) : le chargeur dynamique ou Python liraient alors les fichiers voisins de sa cible, non "
                    f"vérifiés. R{action[1:]} ; rien n'a été exécuté.")
    else:
        if not hasattr(os, "geteuid") or os.geteuid() == 0:
            pytest.skip("root lit un dossier sans droit de lecture")
        hidden.mkdir()
        hidden.chmod(0)
        expected = (f"Dossier de l'interpréteur de ce programme installé illisible ({CPYTHON}) : rétablir les droits de lecture de ce "
                    f"programme installé ou {action} ; rien n'a été exécuté.")
    try:
        result = run(program / "installer.sh", "status", fakes=fakes)
    finally:
        if hidden.exists():
            hidden.chmod(0o700)
    refused_before_python(result, tmp_path, expected)


# --- U6-04 : contrôles d'installer.sh rejoués en lecture seule (--controle-seul), relayés par status -------------------------
CHECK_ONLY = "--controle-seul"


def test_the_check_only_mode_runs_the_checks_and_stops_before_python(tmp_path):
    # U6-04 : « installer.sh --controle-seul » fait tous les contrôles d'installer.sh, sans rien écrire, puis s'arrête avant de
    # lancer Python : code 0 et aucune sortie pour un programme intact, le refus et son code 1 sinon.
    program = installed_program(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    accepted = run(program / "installer.sh", CHECK_ONLY, fakes=fakes)
    assert (accepted.returncode, accepted.stdout, accepted.stderr) == (0, "", "") and not (tmp_path / "interpreteur-lance").exists()
    (program / CPYTHON / "lib/NOTES.txt").write_text("ajouté par erreur\n", encoding="utf-8")
    refused = run(program / "installer.sh", CHECK_ONLY, fakes=fakes)
    assert refused.returncode == 1 and refused.stdout == "" and not (tmp_path / "interpreteur-lance").exists(), refused.stderr
    assert refused.stderr.startswith(f"{CPYTHON}/lib/NOTES.txt ajouté à ce programme installé"), refused.stderr


class EtatArrete:
    """Double nommé RagEtatArrete : `rag.sh status` rend une instance arrêtée ; aucune autre commande n'est attendue de status."""

    def __init__(self) -> None:
        self.argvs: list[list[str]] = []

    def run(self, argv, *, cwd=None, timeout=None):
        from tools.dist.linux_install import Completed

        self.argvs.append(list(argv))
        assert Path(argv[0]).name == "rag.sh" and argv[1] == "status", argv
        return Completed(0, json.dumps({"status": "stopped"}))


def test_status_relays_the_refusal_of_the_installer_of_the_current_version(tmp_path):
    # U6-04 (preuves 02, scénario c5, et 07) : « <kit>/installer.sh status --destination D », premier pas de la procédure 10.4,
    # rendait « Aucun problème relevé. » (code 0) alors que <programme>/installer.sh refusait toute commande. status rejoue en
    # lecture seule les contrôles du vrai install.sh de chaque version désignée (SystemProbe réel : /bin/sh, PATH=/usr/bin:/bin,
    # architecture et glibc du poste) et relaie le refus, avec son action ; témoin : programme intact, aucun problème.
    import io
    import platform

    from tools.dist import linux_install

    program = installed_program(tmp_path, arch=platform.machine())
    destination = program.parent
    data = destination.parent / "donnees"
    data.mkdir()
    (data / "profile.yaml").write_text("app: {}\n", encoding="utf-8")
    (destination / "atelier").write_text(f"#!/bin/sh\n# Lanceur de l'atelier documentaire, version {program.name}.\n", encoding="utf-8")

    def status(as_json: bool = False) -> tuple[int, str]:
        ctx = linux_install.Context(kit=program, runner=EtatArrete(), probe=linux_install.SystemProbe(), out=io.StringIO(),
                                    err=io.StringIO())
        code = linux_install.status_report(ctx, destination, as_json=as_json)
        return code, ctx.out.getvalue()  # type: ignore[attr-defined]

    code, out = status()
    assert code == 0 and out.rstrip().endswith("Aucun problème relevé."), out
    (program / CPYTHON / "lib/NOTES.txt").write_text("ajouté par erreur\n", encoding="utf-8")
    refusal = (f"{CPYTHON}/lib/NOTES.txt ajouté à ce programme installé, absent de SHA256SUMS et de SYMLINKS : fichier étranger dans le "
               "dossier de l'interpréteur de ce programme installé, que le chargeur dynamique ou Python pourraient charger avant toute "
               f"vérification. Le retirer s'il a été ajouté par erreur, sinon {installed_action(program)} ; rien n'a été exécuté.")
    expected = f"« {shlex.quote(str(program / 'installer.sh'))} » refuse toute commande, avant de lancer Python : {refusal}"
    code, out = status()
    assert code == 1 and f"Problèmes :\n  - {expected}\n" in out, out
    code, out = status(as_json=True)
    assert code == 1 and json.loads(out)["problems"] == [expected], out


# --- U6-05, R5S-02, U6-06 : fichier inscrit illisible, absent ou devenu dossier dans le dossier de l'interpréteur -------------
UNREADABLE = "sans droit de lecture (droits perdus à la copie ou à l'extraction) : rétablir les droits de lecture du kit"


def unreadable_message(kit: Path, relative: str) -> str:
    return (f"{relative} {UNREADABLE} (« chmod -R u+rX {shlex.quote(os.path.realpath(kit))} ») ou recopier le kit depuis son archive ; rien "
            "n'a été exécuté.")


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root lit un fichier sans droit de lecture")
@pytest.mark.parametrize("relative", [f"{CPYTHON}/lib/python3.12/encodings/__init__.py", f"{CPYTHON}/lib/python3.12/tarfile.py",
                                      f"{CPYTHON}/lib/libpython3.12.so.1.0", "tools/dist/linux_kit.py", f"{CPYTHON}/bin/python3.12"])
def test_a_listed_file_without_read_permission_is_refused_as_unreadable_not_as_altered(tmp_path, relative):
    # U6-05 (preuve 03, double DroitsDeLecturePerdus) : un fichier listé de la bibliothèque standard rendu illisible arrêtait
    # Python sur une trace (« Fatal Python error: init_fs_encoding », « PermissionError ») ; un fichier haché illisible était
    # annoncé « altéré ». installer.sh le nomme comme illisible, avec l'action, avant de lancer Python.
    kit = fake_kit(tmp_path)
    if "/python3.12/" in relative:
        (kit / relative).parent.mkdir(parents=True, exist_ok=True)
        (kit / relative).write_text("# module livré\n", encoding="utf-8")
        write_links(kit, {}, extra=(relative,))
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0  # témoin : le même kit, lisible, est accepté
    (tmp_path / "interpreteur-lance").unlink()
    mode = (kit / relative).stat().st_mode & 0o777
    (kit / relative).chmod(mode & 0o333)  # droits de lecture retirés, exécution et écriture gardées
    try:
        result = run(kit / "installer.sh", "status", fakes=fakes)
    finally:
        (kit / relative).chmod(mode)
    refused_before_python(result, tmp_path, unreadable_message(kit, relative))


def absent_message(relative: str, owner: str = "du kit", action: str = "Recopier le kit depuis son archive") -> str:
    return (f"{relative} absent {owner}, alors que SHA256SUMS ou SYMLINKS l'inscrit : copie incomplète ou fichier supprimé. {action} ; rien "
            "n'a été exécuté.")


@pytest.mark.parametrize("relative", [f"{CPYTHON}/lib/python3.12/argparse.py", f"{CPYTHON}/lib/libpython3.12.so.1.0",
                                      f"{CPYTHON}/lib/libpython3.12.so"])
def test_an_entry_listed_under_the_interpreter_folder_and_missing_is_refused(tmp_path, relative):
    # R5S-02 (rejeu 20, double KitCPythonComplet) : copie incomplète de la bibliothèque standard, premier cas du modèle de
    # menace ; argparse.py absent arrêtait Python (« ModuleNotFoundError ») et libpython listée mais absente était acceptée
    # (code 0). Chaque entrée de SHA256SUMS (fichier) ou de SYMLINKS (lien) sous <CPython> doit être présente.
    kit = fake_kit(tmp_path)
    links: dict[str, str] = {}
    if relative.endswith("argparse.py"):
        (kit / relative).parent.mkdir(parents=True)
        (kit / relative).write_text("# argparse livré\n", encoding="utf-8")
    if relative.endswith(".so"):
        os.symlink("libpython3.12.so.1.0", kit / relative)
        links[relative] = "libpython3.12.so.1.0"
    write_links(kit, links, extra=(relative,) if relative.endswith("argparse.py") else ())
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0  # témoin : le même kit, complet, est accepté
    (tmp_path / "interpreteur-lance").unlink()
    (kit / relative).unlink()
    refused_before_python(run(kit / "installer.sh", "status", fakes=fakes), tmp_path, absent_message(relative))


def test_an_entry_missing_from_an_installed_program_gives_the_action_of_its_designation(tmp_path):
    program = installed_program(tmp_path)
    (program / CPYTHON / "lib/libpython3.12.so.1.0").unlink()
    result = run(program / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    action = installed_action(program)
    refused_before_python(result, tmp_path, absent_message(f"{CPYTHON}/lib/libpython3.12.so.1.0", "de ce programme installé",
                                                           f"R{action[1:]}"))


@pytest.mark.parametrize("link", [f"{CPYTHON}/lib/libpython3.12.so", f"{CPYTHON}/bin/python3"])
def test_a_declared_link_turned_into_an_empty_folder_is_refused(tmp_path, link):
    # U6-06, QA6-01, R5S-03 (double LienInscritDevenuDossierVide) : un lien de SYMLINKS remplacé par un dossier vide était admis
    # (code 0) ; installer.sh le refuse comme un lien devenu fichier ou dossier non vide.
    kit = fake_kit(tmp_path)
    os.symlink("libpython3.12.so.1.0" if link.endswith(".so") else "python3.12", kit / link)
    write_links(kit, {link: os.readlink(kit / link)})
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    assert run(kit / "installer.sh", "status", fakes=fakes).returncode == 0
    (tmp_path / "interpreteur-lance").unlink()
    (kit / link).unlink()
    (kit / link).mkdir()
    refused_before_python(run(kit / "installer.sh", "status", fakes=fakes), tmp_path, f"{link} {NO_LONGER_LINK}")


def test_an_interrupted_extraction_is_named_by_the_missing_manifest_refusal(tmp_path):
    # R5S-02 : l'archive porte kit-manifest.json après les fichiers du kit ; une extraction interrompue laisse un dossier sans
    # lui, que le refus doit nommer avec son action.
    kit = fake_kit(tmp_path)
    (kit / "kit-manifest.json").unlink()
    result = run(kit / "installer.sh", "status", fakes=fake_host(tmp_path, "Linux", "aarch64"))
    refused_before_python(result, tmp_path, (
        "kit-manifest.json introuvable à côté de l'installateur : lancer installer.sh depuis la racine d'un kit ou d'une installation. Si "
        "ce dossier vient d'une archive extraite, son extraction s'est arrêtée avant la fin (kit-manifest.json suit les fichiers du kit "
        "dans l'archive) : extraire de nouveau l'archive dans un dossier neuf ; rien n'a été exécuté."))


# --- U5-04 : find pris dans un chemin système fixe ; « illisible » réservé à un parcours en échec ----------------------------

def path_without(tmp_path: Path, command: str) -> Path:
    """Double bin-sans-<commande> : dossier de liens vers chaque commande de /usr/bin et de /bin, sauf `command`."""
    folder = tmp_path / f"bin-sans-{command}"
    folder.mkdir()
    for base in ("/usr/bin", "/bin"):
        for entry in sorted(os.listdir(base)):
            if entry != command and not os.path.lexists(folder / entry):
                os.symlink(os.path.join(base, entry), folder / entry)
    return folder


def test_find_is_taken_from_the_system_folders_and_not_from_the_path(tmp_path):
    # Témoin du relecteur (double bin-sans-find) : PATH sans find, toutes les autres commandes présentes ; find est pris dans
    # /usr/bin ou /bin, comme sha256sum : installation lancée.
    kit = fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    result = subprocess.run([str(kit / "installer.sh"), "status"], env={"PATH": f"{fakes}:{path_without(tmp_path, 'find')}", "HOME": str(kit)},
                            capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0 and (tmp_path / "interpreteur-lance").exists(), result.stderr


def without_system_tool(tool: str, command: list[str]) -> list[str]:
    """Double PosteSansOutil : commande lancée dans un espace de noms utilisateur et de montage (unshare -rm, sans privilège),
    où /usr/bin/<tool> et /bin/<tool> sont recouverts par /dev/null, fichier spécial non exécutable."""
    masks = sorted({os.path.realpath(path) for path in (f"/usr/bin/{tool}", f"/bin/{tool}") if os.path.exists(path)})
    script = "".join(f"mount --bind /dev/null {shlex.quote(path)} && " for path in masks) + 'exec "$@"'
    return ["unshare", "-rm", "sh", "-c", script, "sh", *command]


MISSING_TOOLS = {
    "find": ("find (findutils) absent de /usr/bin et /bin : nécessaire pour contrôler le dossier de l'interpréteur du kit avant de "
             "l'exécuter ; le faire installer par l'administrateur du poste ; rien n'a été exécuté."),
    "sha256sum": ("sha256sum (coreutils) absent de /usr/bin et /bin : nécessaire pour vérifier l'interpréteur et l'installateur du kit "
                  "avant de les exécuter ; le faire installer par l'administrateur du poste ; rien n'a été exécuté."),
}


@pytest.mark.parametrize("tool", sorted(MISSING_TOOLS))
def test_a_missing_control_tool_is_named_with_its_action_and_not_reported_as_unreadable(tmp_path, tool):
    # U5-04 : find (comme sha256sum) est pris dans /usr/bin puis /bin ; absent des deux, refus qui le nomme (code 1), au lieu
    # d'un dossier « illisible ».
    if not shutil.which("unshare") or subprocess.run(["unshare", "-rm", "true"], capture_output=True, timeout=30, check=False).returncode:
        pytest.skip("espaces de noms utilisateur et de montage indisponibles sans privilège")
    kit = fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 1000\n')  # dans l'espace de noms, le compte est vu comme root
    result = subprocess.run(without_system_tool(tool, [str(kit / "installer.sh"), "status"]), capture_output=True, text=True, timeout=60,
                            check=False, env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(kit)})
    refused_before_python(result, tmp_path, MISSING_TOOLS[tool])


# --- QA5-01 : collecte de ce module sans os.geteuid (module os de Windows) ---------------------------------------------------

def test_the_module_is_collected_without_os_geteuid(tmp_path):
    # Double OsSansGeteuid : greffon qui retire os.geteuid avant la collecte, comme le module os de Windows (« Availability:
    # Unix ») ; aucune expression évaluée à l'import de ce module ne doit l'appeler.
    (tmp_path / "sans_geteuid.py").write_text("import os\n\ndel os.geteuid\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-p", "sans_geteuid",
                             "--rootdir", str(ROOT), str(Path(__file__))], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(tmp_path)},
                            capture_output=True, text=True, timeout=300, check=False)
    assert result.returncode == 0 and "tests collected" in result.stdout, result.stdout[-3000:] + result.stderr[-2000:]


# --- R3S-04 : HOME et XDG_* de toute la session sous le dossier temporaire de pytest ------------------------------------------

def test_the_unit_session_runs_with_home_and_xdg_folders_under_the_temporary_root(tmp_path_factory):
    # tests/unit/conftest.py (compte_isole) : ce module n'isole pas HOME lui-même ; un processus enfant, que le crochet d'audit
    # ne voit pas, hérite du compte isolé de la session, jamais du compte réel.
    if sys.platform == "win32":  # pwd et os.getuid n'existent que sous Unix ; ce module est déjà sauté sous Windows (mypy)
        pytest.skip("compte isolé de la session : Linux seulement")
    import pwd

    names = ("HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")
    child = subprocess.run([sys.executable, "-c", "import json, os, sys; print(json.dumps({n: os.environ.get(n) for n in sys.argv[1:]}))",
                            *names], capture_output=True, text=True, timeout=60, check=True)
    seen = json.loads(child.stdout)
    base = Path(os.path.realpath(tmp_path_factory.getbasetemp()))
    real = Path(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))
    for name in names:
        assert seen[name] and Path(os.path.realpath(seen[name])).is_relative_to(base), (name, seen[name], base)
    assert not Path(os.path.realpath(seen["HOME"])).is_relative_to(real) or real.is_relative_to(base)


# --- U4-07, QA5-05 : modèle de menace et portée exacte de la vérification avant exécution ------------------------------------
THREAT_MODEL = ("la vérification du kit protège contre l'altération ACCIDENTELLE (copie ou transport incomplets, fichiers ajoutés par "
                "erreur, déduplication ou fermes de liens, droits perdus). Elle ne protège pas contre une personne qui peut écrire dans "
                "le kit : installer.sh lui-même s'exécute sans vérification préalable, et son intégrité repose sur l'empreinte de "
                "l'archive (<kit_id>.tar.sha256) contrôlée avant extraction.")


def flattened(text: str) -> str:
    """Texte sur une ligne, sans marques de commentaire shell ni accents graves."""
    lines = [line.strip().removeprefix("#").strip() for line in text.splitlines()]
    return " ".join(" ".join(lines).replace("`", "").split())


def test_the_installer_texts_state_the_threat_model_and_the_exact_pre_execution_scope():
    from tools.dist import linux_install

    texts = {"install.sh": (ROOT / "tools/dist/install.sh").read_text(encoding="utf-8").split("set -eu", 1)[0],
             "linux_install.py": linux_install.__doc__ or "",
             "SKILL.md": (ROOT / ".agents/skills/linux-offline-kit/SKILL.md").read_text(encoding="utf-8")}
    for name, text in texts.items():
        flat = flattened(text)
        assert THREAT_MODEL in flat, name
        for sentence in flat.split(". "):
            if "s'exécutent avant d'être hachés" in sentence:
                assert "installer.sh lui-même" in sentence, (name, sentence)
    stale = "rien n'est désigné ni exécuté depuis le kit sans avoir été vérifié"
    assert stale not in flattened(linux_install.verify_targeted.__doc__ or "") and stale not in flattened(texts["linux_install.py"])


# --- KIT4-17 : commande atelier de l'utilisateur -----------------------------------------------------------------------------

def user_command(tmp_path: Path, destination: Path) -> Path:
    from tools.dist.linux_install import user_command_text

    return executable(tmp_path / "bin/atelier", user_command_text(destination))


@pytest.mark.parametrize("shell", [shell for shell in ("sh", "dash") if shutil.which(shell)])
def test_the_user_command_is_written_and_runs_the_launcher(tmp_path, shell):
    destination = tmp_path / "pro'grammes $x"
    executable(destination / "atelier", f"#!/bin/sh\nexec {sys.executable} -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \"$@\"\n")
    command = user_command(tmp_path, destination)
    result = subprocess.run([shell, str(command), "ouvrir", "--modele", "qwen3.5:2b"], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["ouvrir", "--modele", "qwen3.5:2b"]
    assert subprocess.run(["dash" if shutil.which("dash") else "sh", "-n", str(command)], check=False).returncode == 0


@pytest.mark.parametrize("shell", [shell for shell in ("sh", "dash") if shutil.which(shell)])
def test_a_missing_destination_gives_the_mount_message(tmp_path, shell):
    destination = tmp_path / "volume-absent/atelier-documentaire/programme"
    command = user_command(tmp_path, destination)
    result = subprocess.run([shell, str(command), "ouvrir"], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == (f"Programme de l'atelier introuvable ({destination}) : volume non monté ? Monter le volume, "
                                     "puis relancer.")
