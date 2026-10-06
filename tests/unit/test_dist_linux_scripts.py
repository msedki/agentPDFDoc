"""Scripts POSIX de la distribution Linux (R26-KIT-01) : syntaxe sous dash et bash --posix, contrôles d'installer.sh.

`installer.sh` est exécuté réellement sur un kit factice : l'interpréteur du kit y est un script qui rend ses arguments
et LD_LIBRARY_PATH ; uname, getconf et ldd sont les doubles de test_runtime_launchers_sh (architecture et bibliothèque C
simulées, placés en tête du PATH du seul processus testé).
"""

import hashlib
import json
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


def fake_kit(tmp_path: Path, *, arch: str = "aarch64", glibc: str = "2.29") -> Path:
    kit = tmp_path / "kit avec espace"
    manifest = {"format": "atelier-kit-v2", "kit_id": "k", "target": {"arch": arch, "glibc_min": glibc},
                "python": {"key": "cpython", "executable": ".runtime/python/cpython/bin/python3.12"}}
    (kit / "tools/dist").mkdir(parents=True)
    (kit / "kit-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "tools/dist/install.sh", kit / "installer.sh")
    shutil.copy2(ROOT / "tools/dist/install.sh", kit / "tools/dist/install.sh")
    executable(kit / ".runtime/python/cpython/bin/python3.12", "#!/bin/sh\n"
               f"exec {sys.executable} -c 'import json,os,sys; print(json.dumps({{\"argv\": sys.argv[1:], "
               "\"ld\": os.environ.get(\"LD_LIBRARY_PATH\")}))' \"$@\"\n")
    (kit / ".runtime/python/cpython/lib").mkdir()
    (kit / ".runtime/python/cpython/lib/libpython3.12.so.1.0").write_bytes(b"\x7fELF libpython factice")
    for name in ("linux_install.py", "linux_kit.py", "build_kit.py"):
        (kit / "tools/dist" / name).write_text(f"# {name} factice\n", encoding="utf-8")
    listed = [".runtime/python/cpython/bin/python3.12", ".runtime/python/cpython/lib/libpython3.12.so.1.0", "tools/dist/linux_install.py",
              "tools/dist/linux_kit.py", "tools/dist/build_kit.py", "installer.sh"]
    (kit / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((kit / name).read_bytes()).hexdigest()}  {name}\n" for name in sorted(listed)),
                                    encoding="utf-8")
    return kit


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
    assert observed["argv"] == ["-B", "-I", "-X", "utf8", f"{resolved}/tools/dist/linux_install.py", "--kit", resolved,
                                "install", "--destination", "/p", "--data-root", "/d"]
    assert observed["ld"] is None


@pytest.mark.parametrize(("machine", "getconf", "ldd", "message"), [
    ("x86_64", None, None, "Ce kit vise Linux aarch64 ; ce poste est en x86_64."),
    ("aarch64", "#!/bin/sh\necho 'glibc 2.28'\n", None, "glibc 2.28 trop ancienne : ce kit exige la glibc 2.29 ou plus récente"),
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
