"""Lanceurs POSIX (W018) : rag.sh et bootstrap.sh, équivalents de rag.ps1 et bootstrap.ps1, exécutés réellement.

Chaque essai copie le script dans une racine temporaire ; l'interpréteur du projet y est remplacé par un script qui
rend ses arguments, son répertoire courant, PYTHONUTF8 et LD_LIBRARY_PATH. Aucun réseau : uname, curl et sha256sum sont
des doubles placés en tête du PATH du seul processus testé ; l'architecture du poste est simulée par uname.
"""

import io
import json
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from services.runtime.artifacts import ROOT

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="lanceurs POSIX")


def executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def project(tmp_path: Path, *, venv: bool = True) -> Path:
    root = tmp_path / "projet avec espace"
    root.mkdir()
    for name in ("rag.sh", "bootstrap.sh"):
        shutil.copy2(ROOT / name, root / name)
    if venv:
        # Interpréteur factice : rend argv, cwd et PYTHONUTF8 en JSON puis sort avec le code 7.
        executable(root / ".venv/bin/python", "#!/bin/sh\n"
                   f"exec {sys.executable} -c 'import json,os,sys; print(json.dumps({{\"argv\": sys.argv[1:], \"cwd\": os.getcwd(), "
                   "\"utf8\": os.environ.get(\"PYTHONUTF8\"), \"ld\": os.environ.get(\"LD_LIBRARY_PATH\")}))' \"$@\"\n")
    return root


def run(script: Path, *args: str, cwd: Path | None = None, path_prefix: Path | None = None, extra_env: dict | None = None):
    env = {"PATH": f"{path_prefix}:/usr/bin:/bin" if path_prefix else "/usr/bin:/bin", "HOME": str(script.parent),
           **(extra_env or {})}
    return subprocess.run([str(script), *args], cwd=cwd or script.parent, env=env, capture_output=True, text=True, timeout=60)


# Archives officielles uv 0.12.21 et SHA-256 publiés (fichiers .sha256 de la release, SOURCES.md LNX16).
UV_ARCHIVES = {
    "aarch64": ("uv-aarch64-unknown-linux-gnu", "030b69227b40af8c1981b7301793dc66e71ed3c796ea8688209dd268bd91ec51"),
    "x86_64": ("uv-x86_64-unknown-linux-gnu", "23f02075b652bb1df64178cfae41b5caf160822e720e2663568f3f5d63bc52c0"),
}


GLIBC_HOST = "#!/bin/sh\n[ \"$1\" = GNU_LIBC_VERSION ] && echo 'glibc 2.31'\n"
# Doubles d'un poste musl (forme attendue, non relevée sur un tel poste) : getconf sans GNU_LIBC_VERSION, code non nul ;
# ldd --version qui nomme musl sur stderr.
MUSL_GETCONF = "#!/bin/sh\necho \"getconf: $1: unknown variable\" >&2\nexit 1\n"
MUSL_LDD = "#!/bin/sh\nprintf 'musl libc (x86_64)\\nVersion 1.2.5\\nDynamic Program Loader\\n' >&2\nexit 1\n"
# Commande absente du poste, vue du script : le shell ne la trouve pas (code 127, message sur stderr). Le PATH des essais
# contient /usr/bin, où getconf et ldd existent sur ce poste : l'absence est donc simulée par ce double.
ABSENT = "#!/bin/sh\necho \"sh: 1: ${0##*/}: not found\" >&2\nexit 127\n"


def ldd_banner(first_line: str) -> str:
    """Double de `ldd --version` : première ligne donnée, suivie de la mention de copyright de la glibc."""
    return f"#!/bin/sh\nprintf '%s\\n' '{first_line}' 'Copyright (C) 2020 Free Software Foundation, Inc.'\n"


def fake_host(tmp_path: Path, system: str, machine: str, *, digest: str = "0" * 64, archive: bytes = b"altere",
              getconf: str = GLIBC_HOST, ldd: str | None = None) -> Path:
    """Doubles d'uname (plateforme simulée), de getconf et ldd (bibliothèque C simulée, glibc 2.31 par défaut), de curl
    (écrit `archive`, consigne ses arguments) et de sha256sum (`digest`)."""
    fakes = tmp_path / "doubles"
    executable(fakes / "uname", f'#!/bin/sh\ncase "$1" in -s) echo {system} ;; -m) echo {machine} ;; esac\n')
    executable(fakes / "getconf", getconf)
    if ldd is not None:
        executable(fakes / "ldd", ldd)
    (fakes / "archive.bin").write_bytes(archive)
    executable(fakes / "curl", "#!/bin/sh\n"
               f"printf '%s\\n' \"$@\" > '{fakes}/curl.args'\n"
               'while [ "$#" -gt 0 ]; do [ "$1" = --output ] && { output=$2; shift; }; shift; done\n'
               f"cp '{fakes}/archive.bin' \"$output\"\n")
    executable(fakes / "sha256sum", f'#!/bin/sh\nshift\nprintf \'%s  %s\\n\' {digest} "$1"\n')
    return fakes


def fake_uv_archive(name: str, log: Path) -> bytes:
    """Archive de la forme officielle (`<nom>/uv`, `<nom>/uvx`) ; uv consigne ses appels et un LD_LIBRARY_PATH reçu."""
    script = ("#!/bin/sh\n"
              f"printf '%s\\n' \"$*\" >> '{log}/uv.calls'\n"
              f"[ -z \"${{LD_LIBRARY_PATH+x}}\" ] || printf '%s\\n' \"$LD_LIBRARY_PATH\" >> '{log}/uv.ld_library_path'\n"
              '[ "$1" != --version ] || echo "uv 0.12.21"\n').encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for member in ("uv", "uvx"):
            info = tarfile.TarInfo(f"{name}/{member}")
            info.size, info.mode = len(script), 0o755
            archive.addfile(info, io.BytesIO(script))
    return buffer.getvalue()


def test_rag_sh_help_lists_the_commands_and_options_of_rag_ps1(tmp_path):
    result = run(project(tmp_path) / "rag.sh", "--help")
    assert result.returncode == 0 and result.stdout.startswith("Usage : ./rag.sh")
    for word in ("provision", "doctor", "pull-model", "init-profile", "selftest", "--only", "--offline", "--skip-model",
                 "--path", "--target", "--report", "--qdrant-storage", "--ports", "--profile", "--no-browser"):
        assert word in result.stdout


@pytest.mark.parametrize(("args", "message"), [
    (["--inconnue"], "Option inconnue : --inconnue"),
    (["demarrer"], "Commande inconnue : demarrer"),
    (["up", "down"], "Commande en trop : down"),
    (["up", "--report"], "Option --report : valeur manquante."),
])
def test_rag_sh_refuses_unknown_input_with_exit_code_1(tmp_path, args, message):
    result = run(project(tmp_path) / "rag.sh", *args)
    assert result.returncode == 1 and message in result.stderr and result.stdout == ""


def test_rag_sh_refuses_to_run_without_the_isolated_environment(tmp_path):
    result = run(project(tmp_path, venv=False) / "rag.sh", "doctor")
    assert result.returncode == 1
    assert result.stderr.strip() == ("Environnement isolé absent. Exécuter bootstrap.sh pour préparer uv et Python3.12, "
                                     "puis rag.sh provision.")


def test_rag_sh_maps_every_option_like_rag_ps1_and_returns_the_cli_exit_code(tmp_path):
    root = project(tmp_path)
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    result = run(root / "rag.sh", "restore", "--path", "sauvegarde", "--target=racine neuve", "--offline", "--skip-model",
                 "--only", "qdrant", "--report", "r.json", "--qdrant-storage", "/q", "--ports", "1,2,3", cwd=elsewhere)
    observed = json.loads(result.stdout)
    assert result.returncode == 0
    assert observed["argv"] == ["-m", "services.runtime.cli", "restore", "--profile", str(root.resolve() / "config/local16.yaml"),
                                "--only", "qdrant", "--offline", "--skip-model", "--path", "sauvegarde",
                                "--target", "racine neuve", "--report", "r.json", "--qdrant-storage", "/q", "--ports", "1,2,3"]
    # Comme Push-Location dans rag.ps1 : la CLI s'exécute depuis la racine du projet, en UTF-8.
    assert observed["cwd"] == str(root.resolve()) and observed["utf8"] == "1"
    default = json.loads(run(root / "rag.sh", "--profile", "/profils/poste.yaml").stdout)
    assert default["argv"] == ["-m", "services.runtime.cli", "doctor", "--profile", "/profils/poste.yaml"]
    executable(root / ".venv/bin/python", "#!/bin/sh\nexit 7\n")
    assert run(root / "rag.sh", "status").returncode == 7


@pytest.mark.parametrize(("system", "machine"), [("Linux", "armv7l"), ("Linux", "riscv64"), ("Linux", "i686"),
                                               ("Darwin", "arm64"), ("FreeBSD", "amd64")])
def test_bootstrap_sh_refuses_an_unsupported_platform(tmp_path, system, machine):
    root = project(tmp_path)
    result = run(root / "bootstrap.sh", path_prefix=fake_host(tmp_path, system, machine))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == (f"Plateforme non prise en charge : {system} {machine}. bootstrap.sh vise Linux aarch64 ou "
                                     "x86_64 ; utiliser bootstrap.ps1 sous Windows x86-64.")
    assert not (root / ".runtime").exists() and not (tmp_path / "doubles/curl.args").exists()


@pytest.mark.parametrize("machine", sorted(UV_ARCHIVES))
def test_bootstrap_sh_installs_the_official_uv_archive_of_each_architecture(tmp_path, machine):
    name, official = UV_ARCHIVES[machine]
    root = project(tmp_path)
    log = tmp_path / "journal"
    log.mkdir()
    fakes = fake_host(tmp_path, "Linux", machine, digest=official, archive=fake_uv_archive(name, log))
    result = run(root / "bootstrap.sh", path_prefix=fakes, extra_env={"LD_LIBRARY_PATH": "/opt/fournisseur/lib64:"})
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "doubles/curl.args").read_text().splitlines()[-1] == (
        f"https://github.com/astral-sh/uv/releases/download/0.12.21/{name}.tar.gz")
    assert (root / f".runtime/bootstrap/uv-0.12.21-linux-{machine}.tar.gz").is_file()
    assert (root / ".runtime/bootstrap/bin/uv").stat().st_mode & 0o777 == 0o755
    key = f"cpython-3.12.14-linux-{machine}-gnu"
    calls = (log / "uv.calls").read_text().splitlines()
    assert calls == ["--version",
                     f"python install {key} --install-dir {root.resolve()}/.runtime/python --no-bin --cache-dir {root.resolve()}/.runtime/cache/uv",
                     f"sync --locked --python {root.resolve()}/.runtime/python/{key}/bin/python3.12 --no-python-downloads "
                     f"--cache-dir {root.resolve()}/.runtime/cache/uv"]
    # LD_LIBRARY_PATH du profil shell (élément vide final : répertoire courant pour ld.so) jamais transmis à uv.
    assert not (log / "uv.ld_library_path").exists()
    assert result.stdout.strip() == "Environnement Python isolé prêt. Exécuter ./rag.sh provision pour artefacts et modèle."


@pytest.mark.parametrize("machine", sorted(UV_ARCHIVES))
def test_bootstrap_sh_refuses_the_archive_of_the_other_architecture(tmp_path, machine):
    # Empreinte de l'autre architecture : l'association architecture → archive → SHA-256 est vérifiée, pas seulement
    # la présence d'une empreinte connue.
    other = next(item for item in UV_ARCHIVES if item != machine)
    name, _ = UV_ARCHIVES[machine]
    root = project(tmp_path)
    log = tmp_path / "journal"
    log.mkdir()
    fakes = fake_host(tmp_path, "Linux", machine, digest=UV_ARCHIVES[other][1], archive=fake_uv_archive(name, log))
    result = run(root / "bootstrap.sh", path_prefix=fakes)
    assert result.returncode == 1 and result.stderr.strip() == "Archive officielle uv : SHA-256 non conforme, aucune exécution."
    assert not (root / ".runtime/bootstrap/bin/uv").exists() and not (log / "uv.calls").exists()


@pytest.mark.parametrize("machine", sorted(UV_ARCHIVES))
def test_bootstrap_sh_offline_without_uv_and_a_tampered_archive_are_refused(tmp_path, machine):
    root = project(tmp_path)
    fakes = fake_host(tmp_path, "Linux", machine)
    offline = run(root / "bootstrap.sh", "--offline", path_prefix=fakes)
    assert offline.returncode == 1 and offline.stderr.strip() == "uv local absent du kit offline."
    # curl factice : écrit une archive altérée à l'emplacement demandé, sans réseau ; sha256sum réel.
    (fakes / "sha256sum").unlink()
    tampered = run(root / "bootstrap.sh", path_prefix=fakes)
    assert tampered.returncode == 1 and tampered.stderr.strip() == "Archive officielle uv : SHA-256 non conforme, aucune exécution."
    assert not (root / ".runtime/bootstrap/bin/uv").exists()
    unknown = run(root / "bootstrap.sh", "--option-inconnue")
    assert unknown.returncode == 1 and "Option inconnue : --option-inconnue" in unknown.stderr
    assert run(root / "bootstrap.sh", "--help").stdout.startswith("Usage : ./bootstrap.sh")


def test_rag_sh_does_not_pass_ld_library_path_to_the_project_interpreter(tmp_path):
    result = run(project(tmp_path) / "rag.sh", "status", extra_env={"LD_LIBRARY_PATH": "/opt/fournisseur/lib64:"})
    assert result.returncode == 0 and json.loads(result.stdout)["ld"] is None


LIBC_REQUIREMENT = "bootstrap.sh exige la glibc 2.28 ou plus récente (roues manylinux_2_28 du verrou)"
UNKNOWN_LIBC = (f"Bibliothèque C non reconnue (ni getconf GNU_LIBC_VERSION ni ldd --version ne donnent de version de glibc) : "
                f"{LIBC_REQUIREMENT}.")


@pytest.mark.parametrize("machine", sorted(UV_ARCHIVES))
@pytest.mark.parametrize(("getconf", "ldd", "message"), [
    (MUSL_GETCONF, MUSL_LDD, f"Bibliothèque C musl détectée : {LIBC_REQUIREMENT} ; utiliser une distribution Linux à glibc."),
    ("#!/bin/sh\necho 'glibc 2.27'\n", None, f"glibc 2.27 trop ancienne : {LIBC_REQUIREMENT} ; utiliser une distribution plus récente."),
    ("#!/bin/sh\necho 'glibc 2.17'\n", None, f"glibc 2.17 trop ancienne : {LIBC_REQUIREMENT} ; utiliser une distribution plus récente."),
    ("#!/bin/sh\necho 'glibc 1.99'\n", None, f"glibc 1.99 trop ancienne : {LIBC_REQUIREMENT} ; utiliser une distribution plus récente."),
    (MUSL_GETCONF, "#!/bin/sh\necho 'ldd (autre libc) 9.9'\n", UNKNOWN_LIBC),
    ("#!/bin/sh\necho 'glibc deux.vingt'\n", ldd_banner("ldd (GNU libc) deux.vingt"), UNKNOWN_LIBC),
    (ABSENT, MUSL_LDD, f"Bibliothèque C musl détectée : {LIBC_REQUIREMENT} ; utiliser une distribution Linux à glibc."),
    (ABSENT, ldd_banner("ldd (GNU libc) 2.27"),
     f"glibc 2.27 trop ancienne : {LIBC_REQUIREMENT} ; utiliser une distribution plus récente."),
    (ABSENT, ldd_banner("ldd (Debian GLIBC 2.24-11+deb9u4) 2.24"),
     f"glibc 2.24 trop ancienne : {LIBC_REQUIREMENT} ; utiliser une distribution plus récente."),
    (ABSENT, ABSENT, UNKNOWN_LIBC),
], ids=["musl", "glibc-2.27", "glibc-2.17", "glibc-1.99", "libc-inconnue", "version-illisible", "sans-getconf-musl",
        "sans-getconf-glibc-2.27", "sans-getconf-glibc-debian-2.24", "ni-getconf-ni-ldd"])
def test_bootstrap_sh_refuses_musl_or_a_glibc_older_than_2_28_before_any_download(tmp_path, machine, getconf, ldd, message):
    # Roues manylinux_2_28 du verrou (torch, torchvision, onnxruntime). Sans ce contrôle, le lanceur téléchargeait uv puis
    # échouait plus loin (revue R1b : « Version uv différente du verrou. » sous musl, uv sync avec une glibc ancienne).
    root = project(tmp_path)
    result = run(root / "bootstrap.sh", path_prefix=fake_host(tmp_path, "Linux", machine, getconf=getconf, ldd=ldd))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == message
    assert not (root / ".runtime").exists() and not (tmp_path / "doubles/curl.args").exists()


@pytest.mark.parametrize("version", ["2.28", "2.39", "3.0"])
def test_bootstrap_sh_accepts_glibc_2_28_and_later(tmp_path, version):
    # Contrôle passé : le lanceur poursuit jusqu'au kit hors ligne absent, première étape après lui.
    root = project(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "x86_64", getconf=f"#!/bin/sh\necho 'glibc {version}'\n")
    result = run(root / "bootstrap.sh", "--offline", path_prefix=fakes)
    assert result.returncode == 1 and result.stderr.strip() == "uv local absent du kit offline."


@pytest.mark.parametrize("machine", sorted(UV_ARCHIVES))
@pytest.mark.parametrize("first_line", ["ldd (GNU libc) 2.39", "ldd (Ubuntu GLIBC 2.31-0ubuntu9.18) 2.31",
                                        "ldd (Debian GLIBC 2.36-9+deb12u4) 2.36"],
                         ids=["gnu-libc-2.39", "ubuntu-glibc-2.31", "debian-glibc-2.36"])
def test_bootstrap_sh_without_getconf_identifies_the_glibc_by_ldd_version(tmp_path, machine, first_line):
    # Poste glibc sans getconf : la première ligne de `ldd --version` nomme la glibc (« GNU libc », ou « GLIBC » précédé
    # de la distribution) et finit par sa version. Avant correction : « Bibliothèque C non reconnue ». La forme Ubuntu est
    # celle relevée sur le poste de développement (Ubuntu 20.04, /usr/bin/ldd) ; la forme Debian est supposée par analogie.
    root = project(tmp_path)
    fakes = fake_host(tmp_path, "Linux", machine, getconf=ABSENT, ldd=ldd_banner(first_line))
    result = run(root / "bootstrap.sh", "--offline", path_prefix=fakes)
    assert result.returncode == 1 and result.stderr.strip() == "uv local absent du kit offline."


def test_rag_sh_passes_no_browser_to_the_cli_and_keeps_the_browser_by_default(tmp_path):
    # Poste sans navigateur (serveur, session SSH) : `./rag.sh open --no-browser` affiche le lien à usage unique ;
    # l'option était refusée par le lanceur (« Option inconnue »), seul le CLI la connaissait.
    root = project(tmp_path)
    profile = str(root.resolve() / "config/local16.yaml")
    result = run(root / "rag.sh", "open", "--no-browser")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["argv"] == ["-m", "services.runtime.cli", "open", "--profile", profile, "--no-browser"]
    default = run(root / "rag.sh", "open")
    assert json.loads(default.stdout)["argv"] == ["-m", "services.runtime.cli", "open", "--profile", profile]
