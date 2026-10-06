"""Installation de l'atelier depuis un kit Linux hors ligne (R26-KIT-01) : install, update, rollback, uninstall, repair,
status et les actions du lanceur `atelier`.

Exécuté par `installer.sh` avec le CPython du kit (`-B -I`), bibliothèque standard seule. Aucun droit administrateur : ni
sudo, ni service, ni PATH, ni fichier hors de la destination, de la racine des données et, sur demande explicite
(`--menu`), d'une entrée de menu. Chaque version s'installe dans `<destination>/<kit_id>` ; les données restent dans la
racine choisie. La version courante est désignée par `<destination>/installation.json` ; le lanceur `<destination>/atelier`
et l'entrée de menu en sont dérivés. Bascule : tous les fichiers sont préparés (temporaire, fsync), puis le `rename(2)`
du pointeur valide la bascule ; un échec ensuite laisse le pointeur juste, et `repair` régénère lanceur et entrée de menu.

Ordre d'une installation : précontrôles sans écriture, vérification complète du kit, contrôles système (bibliothèques,
libstdc++, ldd, Jetson), verrou de l'installateur, copie vérifiée, réécriture du préfixe de CPython, `bootstrap.sh
--offline --no-dev`, précompilation, profils, `doctor` (rouge : arrêt), bascule, puis démarrage, contrôle réel et
ouverture. Une mise à jour valide les profils dérivés, puis sauvegarde et vérifie les données de la version en place
avant toute copie.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

HERE = Path(__file__).resolve().parents[2]
if str(HERE) not in sys.path:
    # Lancé avec -I : le dossier du script n'est pas dans sys.path ; la racine du kit (ou du programme) y est ajoutée.
    sys.path.insert(0, str(HERE))

from tools.dist import linux_kit  # noqa: E402

POINTER = "installation.json"
LAUNCHER = "atelier"
DESKTOP = "atelier-documentaire.desktop"
LOCK = ".atelier-installateur.lock"
POINTER_FORMAT = "atelier-installation-v1"
RED = "rouge"
RUNNING = {"starting", "running", "stopping"}
# Systèmes de fichiers sans liens symboliques ni bit x fiables, ou distants (verrous flock sur volume local seulement).
REFUSED_FILESYSTEMS = {"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk", "nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs"}
# Données d'exécution qui ne doivent jamais exister dans un dossier programme (profil livré employé à tort).
RUNTIME_DATA = (".runtime/data", ".runtime/control", ".runtime/q", ".runtime/qa", "backups")
# Variables héritées sans effet voulu sur l'installation : chemins Python, réglages uv (cache, index, liens, Python).
DROPPED_PREFIXES = ("UV_",)
DROPPED = {"LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONNOUSERSITE"}
KIT_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]*")
PYTHON_EXECUTABLE = re.compile(r"\.runtime/python/[0-9A-Za-z._-]+/bin/python3\.\d+")


class InstallError(RuntimeError):
    """Refus ou échec, avec l'état laissé et la correction attendue."""


class SwitchIncomplete(InstallError):
    """Pointeur basculé, lanceur ou entrée de menu non régénéré : `repair` les reprend depuis le pointeur."""


@dataclass
class Completed:
    returncode: int
    stdout: str
    stderr: str = ""


def child_environment() -> dict[str, str]:
    """Environnement des commandes lancées : celui de l'utilisateur, sans LD_LIBRARY_PATH, chemins Python ni réglages uv
    hérités ; uv sans fichier de configuration de l'utilisateur (UV_NO_CONFIG), Python en UTF-8."""
    environment = {key: value for key, value in os.environ.items() if key not in DROPPED and not key.startswith(DROPPED_PREFIXES)}
    environment["PYTHONUTF8"] = "1"
    environment["UV_NO_CONFIG"] = "1"
    return environment


class SystemRunner:
    def run(self, argv: list[str], *, cwd: Path | None = None, timeout: float | None = None) -> Completed:
        try:
            completed = subprocess.run(argv, cwd=cwd, env=child_environment(), capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            return Completed(127, "", str(error))
        return Completed(completed.returncode, completed.stdout, completed.stderr)


def ldconfig_cache() -> dict[str, str]:
    """Bibliothèques connues du chargeur (`ldconfig -p`, lecture seule) : SONAME → chemin."""
    ldconfig = shutil.which("ldconfig", path="/sbin:/usr/sbin:/usr/bin:/bin")
    if not ldconfig:
        return {}
    completed = subprocess.run([ldconfig, "-p"], capture_output=True, text=True, errors="replace", check=False, timeout=60,
                               env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    found: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        match = re.match(r"\s+(\S+) \(([^)]*)\) => (\S+)", line)
        if match:
            found.setdefault(match.group(1), match.group(3))
    return found


class SystemProbe:
    """Lectures du poste, sans écriture."""

    def machine(self) -> str:
        return platform.machine()

    def glibc(self) -> str | None:
        return linux_kit.host_glibc()

    def kernel(self) -> str:
        return platform.release()

    def memory_total_gib(self) -> float | None:
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024**2
        except (OSError, ValueError, IndexError):
            return None
        return None

    def free_bytes(self, path: Path) -> int:
        return shutil.disk_usage(existing_ancestor(path)).free

    def filesystem(self, path: Path) -> dict[str, Any]:
        """Type du système de fichiers (mountinfo, point de montage le plus long) et option noexec (statvfs)."""
        real = os.path.realpath(existing_ancestor(path))
        best, fstype = "", "inconnu"
        try:
            for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split(" ")
                point = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4])
                tail = fields[fields.index("-") + 1:]
                if (real == point or real.startswith(point.rstrip("/") + "/")) and len(point) >= len(best):
                    best, fstype = point, tail[0]
        except (OSError, ValueError, IndexError):
            pass
        noexec = False
        if sys.platform != "win32":
            noexec = bool(os.statvfs(existing_ancestor(path)).f_flag & getattr(os, "ST_NOEXEC", 8))
        return {"mount": best, "fstype": fstype, "noexec": noexec}

    def setpriv(self) -> str | None:
        return shutil.which("setpriv", path="/usr/bin:/bin")

    def ldd(self, binary: Path) -> Completed:
        ldd = shutil.which("ldd", path="/usr/bin:/bin")
        if not ldd:
            return Completed(127, "", "ldd introuvable dans /usr/bin ou /bin")
        environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
        completed = subprocess.run([ldd, str(binary)], env=environment, capture_output=True, text=True, errors="replace", check=False,
                                   timeout=60)
        return Completed(completed.returncode, completed.stdout, completed.stderr)

    def shared_libraries(self) -> set[str]:
        return set(ldconfig_cache())

    def glibcxx_max(self) -> str | None:
        """Version GLIBCXX la plus haute définie par le libstdc++.so.6 du chargeur (chaînes de sa table de versions)."""
        path = ldconfig_cache().get("libstdc++.so.6")
        if not path:
            return None
        try:
            versions = {int(item) for item in re.findall(rb"GLIBCXX_3\.4\.(\d+)", Path(path).read_bytes())}
        except OSError:
            return None
        return f"3.4.{max(versions)}" if versions else None

    def l4t_major(self) -> int | None:
        release = linux_kit.l4t_release()
        return release.get("major") if release else None

    def port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True


def existing_ancestor(path: Path) -> Path:
    path = path.absolute()
    while not path.exists():
        path = path.parent
    return path


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def inside(path: Path, folder: Path) -> bool:
    """Vrai si `path` est `folder` ou dessous, chemins réels comparés (liens résolus)."""
    real, base = Path(os.path.realpath(path)), Path(os.path.realpath(folder))
    return real == base or real.is_relative_to(base)


def control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    linux_kit.write_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
    except ValueError:
        lines = text.splitlines()
        try:
            value = json.loads(lines[-1]) if lines else {}
        except ValueError:
            value = {}
    return value if isinstance(value, dict) else {}


def model_slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", model).strip("-")


def desktop_quote(value: str) -> str:
    """Argument de la clé Exec (Desktop Entry 1.5) : `%` doublé, guillemets, puis `"`, `` ` ``, `$` et `\\` précédés d'une barre
    oblique inverse ; la règle d'échappement des chaînes (barre oblique inverse doublée) s'applique ensuite."""
    if control_characters(value):
        raise InstallError(f"Chemin à caractère de contrôle refusé dans une entrée de menu : {value!r}")
    quoted = '"' + re.sub(r'(["`$\\\\])', r"\\\1", value.replace("%", "%%")) + '"'
    return quoted.replace("\\", "\\\\")


@dataclass
class Context:
    kit: Path
    runner: Any = field(default_factory=SystemRunner)
    probe: Any = field(default_factory=SystemProbe)
    out: TextIO = sys.stdout
    clock: Any = utc_now

    def say(self, status: str, step: str, detail: str = "") -> None:
        print(f"[{status}] {step} {detail}".rstrip(), file=self.out, flush=True)


class Report:
    def __init__(self, ctx: Context, kind: str, **fields: Any):
        self.ctx = ctx
        self.data: dict[str, Any] = {"format": f"atelier-{kind}-linux-v1", "started_utc": ctx.clock().isoformat(), **fields, "steps": []}
        self.path: Path | None = None

    def step(self, name: str, status: str, detail: str = "") -> None:
        self.data["steps"].append({"step": name, "status": status, "detail": detail, "at_utc": self.ctx.clock().isoformat()})
        self.ctx.say(status, name, detail)

    def save(self) -> None:
        if self.path:
            self.data["finished_utc"] = self.ctx.clock().isoformat()
            write_json_atomic(self.path, self.data)


# --- Verrou de l'installateur ---------------------------------------------------------------------------------------------

@contextmanager
def installer_lock(destination: Path) -> Iterator[None]:
    """Une opération d'installation à la fois par destination (flock non bloquant, libéré à la fermeture)."""
    if sys.platform == "win32":
        raise InstallError("Installateur Linux seulement")
    import fcntl

    destination.mkdir(parents=True, exist_ok=True)
    with (destination / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError(f"Une autre opération d'installation est en cours sur {destination} ; attendre sa fin, puis relancer.") from error
        yield


def lock_is_free(destination: Path) -> bool:
    if sys.platform == "win32" or not (destination / LOCK).exists():
        return True
    import fcntl

    with (destination / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(handle, fcntl.LOCK_UN)
    return True


# --- Commandes du programme installé ------------------------------------------------------------------------------------

def rag(ctx: Context, program: Path, command: str, *arguments: str, timeout: float = 1800) -> dict[str, Any]:
    """`rag.sh <commande>` du programme ; résultat JSON, avec le code de sortie dans `_returncode`."""
    completed = ctx.runner.run([str(program / "rag.sh"), command, *arguments], cwd=program, timeout=timeout)
    result = parse_json(completed.stdout)
    result["_returncode"] = completed.returncode
    if not result.get("message") and completed.returncode:
        result["message"] = (completed.stderr or completed.stdout).strip()[-600:]
    return result


def venv_python(program: Path) -> Path:
    return program / ".venv/bin/python"


def profiles_tool(ctx: Context, python: Path, scripts: Path, *arguments: str, cwd: Path) -> dict[str, Any]:
    """`linux_profiles.py` de `scripts`, exécuté par `python` (environnement isolé d'un programme : PyYAML)."""
    completed = ctx.runner.run([str(python), "-B", "-I", str(scripts / "tools/dist/linux_profiles.py"), *arguments], cwd=cwd, timeout=120)
    result = parse_json(completed.stdout)
    if completed.returncode and not result.get("message"):
        result["message"] = (completed.stderr or completed.stdout).strip()[-400:]
    result.setdefault("status", "failed")
    return result


def profile_info(ctx: Context, program: Path, profile: Path) -> dict[str, Any]:
    """Modèle, ports et emplacements d'écriture d'un profil, lus par l'environnement du programme."""
    result = profiles_tool(ctx, venv_python(program), program, "paths", "--profile", str(profile), cwd=program)
    if result["status"] != "read":
        raise InstallError(f"Profil {profile} illisible par {program} : {result.get('message')}")
    return result


def derive_profiles(ctx: Context, report: Report | None, *, python: Path, scripts: Path, program: Path, like: str,
                    data_root: Path, models: list[str], check: bool = False) -> dict[str, str]:
    """Profils d'autres modèles livrés sur les données de `like` ; rend {modèle: profil} créé, réutilisé ou contrôlé."""
    made: dict[str, str] = {}
    for model in models:
        output = data_root / f"profile-{model_slug(model)}.yaml"
        result = profiles_tool(ctx, python, scripts, "derive", "--like", like, "--model", model, "--program", str(program),
                               "--output", str(output), *(["--check"] if check else []), cwd=program)
        if result["status"] not in {"created", "reused", "checked"}:
            raise InstallError(f"Profil {model} non dérivable : {result.get('message')}")
        made[model] = str(output)
        if report and not check:
            report.step("profil", "ok", f"{output} ({model}, mêmes données ; {'réutilisé' if result['status'] == 'reused' else 'créé'})")
    return made


# --- Pointeur de version, lanceur et entrée de menu --------------------------------------------------------------------------

def read_pointer(destination: Path) -> dict[str, Any] | None:
    path = destination / POINTER
    if not path.exists():
        return None
    pointer = read_json(path)
    if pointer.get("format") != POINTER_FORMAT:
        raise InstallError(f"{path} n'est pas un pointeur d'installation de l'atelier")
    return pointer


def designated(destination: Path) -> dict[str, Any] | None:
    """Version que le pointeur désigne réellement, relue sur disque ; None si absent ou illisible."""
    try:
        return (read_pointer(destination) or {}).get("current")
    except (OSError, ValueError, InstallError):
        return None


def launcher_text(entry: dict[str, Any], destination: Path) -> str:
    program = Path(entry["program"])
    python = program / entry["python"]
    return ("#!/bin/sh\n"
            f"# Lanceur de l'atelier documentaire, version {entry['kit_id']}.\n"
            "# Écrit par l'installateur à chaque bascule de version (installer.sh repair le régénère) : ne pas modifier.\n"
            "# Actions : ouvrir (défaut), arreter, diagnostic, etat, sauvegarder ; options --modele <tag>, --no-browser.\n"
            "set -eu\nunset LD_LIBRARY_PATH\n"
            f"exec {shlex.quote(str(python))} -B -I -X utf8 {shlex.quote(str(program / 'tools/dist/linux_install.py'))} "
            f"--kit {shlex.quote(str(program))} run --destination {shlex.quote(str(destination))} \"$@\"\n")


def desktop_text(destination: Path) -> str:
    return ("[Desktop Entry]\nType=Application\nVersion=1.5\nName=Atelier documentaire\n"
            "Comment=Démarre l'atelier si nécessaire et l'ouvre dans le navigateur\n"
            f"Exec={desktop_quote(str(destination / LAUNCHER))} ouvrir\nTerminal=true\nCategories=Office;\n")


def stage(path: Path, data: bytes, mode: int) -> Path:
    """Fichier temporaire complet et synchronisé à côté de `path`, prêt pour rename(2)."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as writer:
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, mode)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def publish(temporary: Path, path: Path) -> None:
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def derived_files(destination: Path, pointer: dict[str, Any]) -> list[tuple[Path, bytes, int]]:
    current = pointer.get("current")
    if not current:
        return []
    files = [(destination / LAUNCHER, launcher_text(current, destination).encode("utf-8"), 0o755)]
    if pointer.get("menu_entry"):
        files.append((Path(pointer["menu_entry"]), desktop_text(destination).encode("utf-8"), 0o644))
    return files


def refresh_derived(destination: Path, pointer: dict[str, Any]) -> None:
    """Lanceur et entrée de menu dérivés du pointeur : préparés puis publiés ; retirés sans version courante."""
    files = derived_files(destination, pointer)
    staged: list[tuple[Path, Path]] = []
    try:
        for path, data, mode in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            staged.append((stage(path, data, mode), path))
        for temporary, path in staged:
            publish(temporary, path)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    if not pointer.get("current"):
        (destination / LAUNCHER).unlink(missing_ok=True)
        if pointer.get("menu_entry"):
            Path(pointer["menu_entry"]).unlink(missing_ok=True)


def switch(destination: Path, pointer: dict[str, Any] | None, current: dict[str, Any] | None, previous: dict[str, Any] | None,
           event: dict[str, Any], *, menu: Path | None = None) -> dict[str, Any]:
    """Bascule transactionnelle : pointeur, lanceur et entrée de menu préparés d'abord ; le rename(2) du pointeur est le point
    de validation. Avant lui, rien ne change ; après lui, un échec lève SwitchIncomplete (le pointeur est juste, `repair`
    régénère le reste)."""
    new = dict(pointer or {"format": POINTER_FORMAT, "destination": str(destination), "history": []})
    new["current"], new["previous"] = current, previous
    new["history"] = [*new.get("history", []), event]
    if menu is not None:
        new["menu_entry"] = str(menu / DESKTOP)
    files = [(destination / POINTER, (json.dumps(new, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), 0o644),
             *derived_files(destination, new)]
    staged: list[tuple[Path, Path]] = []
    try:
        for path, data, mode in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            staged.append((stage(path, data, mode), path))
        publish(*staged[0])
    except BaseException:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        raise
    try:
        for temporary, path in staged[1:]:
            publish(temporary, path)
        if not current:
            (destination / LAUNCHER).unlink(missing_ok=True)
            if new.get("menu_entry"):
                Path(new["menu_entry"]).unlink(missing_ok=True)
    except BaseException as error:
        for temporary, _ in staged[1:]:
            temporary.unlink(missing_ok=True)
        version = (current or {}).get("kit_id", "aucune")
        raise SwitchIncomplete(f"La version {version} est la version courante (pointeur {destination / POINTER} basculé), mais le lanceur "
                               f"ou l'entrée de menu n'a pas été régénéré ({error}) : « installer.sh repair --destination "
                               f"{destination} » le reprend depuis le pointeur.") from error
    return new


def mark_started(destination: Path, program: Path, *, holding_lock: bool = False) -> None:
    """Consigne qu'une version a démarré sur les données (son retour arrière passera par la restauration). Le lanceur ne
    l'écrit que si aucune opération d'installation ne tient le verrou ; sinon l'exécutable du superviseur, lu par `status`,
    en garde la trace."""
    if not holding_lock and not lock_is_free(destination):
        return
    pointer = read_pointer(destination)
    if pointer and pointer.get("current") and Path(pointer["current"]["program"]) == program and not pointer["current"].get("started_on_data"):
        pointer["current"]["started_on_data"] = True
        write_json_atomic(destination / POINTER, pointer)


# --- Manifeste et précontrôles ---------------------------------------------------------------------------------------------

def read_manifest(kit: Path) -> dict[str, Any]:
    """Manifeste du kit, avec les champs qui deviennent des chemins validés avant tout usage."""
    try:
        manifest = read_json(kit / linux_kit.MANIFEST)
        sums = linux_kit.read_sums(kit)
    except (OSError, ValueError) as error:
        raise InstallError(f"kit-manifest.json ou SHA256SUMS illisible dans {kit} : {error}") from error
    if manifest.get("format") != linux_kit.KIT_FORMAT or not str(manifest.get("platform", "")).startswith("linux-"):
        raise InstallError(f"{kit} n'est pas un kit Linux de l'atelier (format {manifest.get('format')})")
    problems = []
    kit_id = str(manifest.get("kit_id", ""))
    if not KIT_ID.fullmatch(kit_id) or kit_id in {".", ".."}:
        problems.append(f"kit_id {kit_id!r}")
    executable = str((manifest.get("python") or {}).get("executable", ""))
    if not PYTHON_EXECUTABLE.fullmatch(executable) or executable not in sums:
        problems.append(f"python.executable {executable!r}")
    for item in manifest.get("neutralizations") or []:
        if str(item.get("path")) not in sums or not str(item.get("path")).startswith(".runtime/"):
            problems.append(f"neutralizations {item.get('path')!r}")
    for relative in (manifest.get("target") or {}).get("ldd_checks") or []:
        if relative not in sums:
            problems.append(f"ldd_checks {relative!r}")
    if problems:
        raise InstallError(f"kit-manifest.json non conforme ({', '.join(problems)}) : recopier le kit ; rien n'a été installé.")
    return manifest


def writable_target(path: Path) -> bool:
    ancestor = existing_ancestor(path)
    return ancestor.is_dir() and os.access(ancestor, os.W_OK | os.X_OK)


def check_ports(ctx: Context, ports: str) -> list[str]:
    parts = ports.split(",")
    if len(parts) != 3 or not all(part.strip().isdigit() for part in parts):
        return [f"--ports {ports} : trois ports API,Qdrant,Ollama attendus"]
    values = [int(part) for part in parts]
    if len(set(values)) != 3 or not all(1024 <= value <= 65535 for value in values):
        return [f"--ports {ports} : trois ports distincts entre 1024 et 65535 attendus"]
    return [f"--ports : port {value} occupé sur 127.0.0.1" for value in values if not ctx.probe.port_free(value)]


def precheck(ctx: Context, manifest: dict[str, Any], destination: Path, data_root: Path, *, qdrant_storage: Path | None = None,
             program: Path | None = None, menu: Path | None = None, model: str | None = None, ports: str | None = None) -> list[str]:
    """Contrôles du poste, des emplacements et des options, sans écriture ; tous les refus sont rendus ensemble."""
    probe, kit = ctx.probe, ctx.kit
    target = manifest["target"]
    failures: list[str] = []
    passed: list[str] = []
    machine = probe.machine()
    if machine == target["arch"]:
        passed.append(f"architecture {machine}")
    else:
        failures.append(f"ce kit vise {target['arch']}, ce poste est en {machine}")
    glibc = probe.glibc()
    if glibc is None:
        failures.append("glibc introuvable (musl ou bibliothèque C non reconnue)")
    elif target.get("glibc_min") and linux_kit.version_tuple(glibc) < linux_kit.version_tuple(target["glibc_min"]):
        failures.append(f"glibc {glibc} trop ancienne : {target['glibc_min']} ou plus récente exigée")
    else:
        passed.append(f"glibc {glibc}")
    kernel = probe.kernel()
    if linux_kit.version_tuple(kernel)[:2] < linux_kit.version_tuple(target.get("kernel_min", linux_kit.KERNEL_MIN))[:2]:
        failures.append(f"noyau {kernel} : {target.get('kernel_min')} ou plus récent exigé (pidfd)")
    memory = probe.memory_total_gib()
    if memory is not None and memory < target.get("memory_gib_min", linux_kit.MEMORY_MIN_GIB):
        failures.append(f"{memory:.1f} Gio de mémoire : l'atelier en demande 16")
    if not probe.setpriv():
        failures.append("setpriv (util-linux) absent de /usr/bin et /bin : l'arrêt des services à la mort du superviseur "
                        "ne serait pas garanti")
    required = (manifest.get("gpu") or {}).get("requires_l4t_major")
    if required and probe.l4t_major() != required:
        failures.append(f"kit {manifest['gpu'].get('variant')} réservé à Jetson Linux R{required} (ce poste : "
                        f"{'R' + str(probe.l4t_major()) if probe.l4t_major() else 'pas de Jetson Linux'}) : employer un kit --gpu none")
    places = [("destination", destination), ("racine des données", data_root)] + ([("--menu", menu)] if menu else [])
    for name, path in places:
        if control_characters(str(path)):
            failures.append(f"{name} {str(path)!r} : caractère de contrôle refusé")
        elif not path.is_absolute():
            failures.append(f"{name} : chemin absolu attendu ({path})")
        elif inside(path, kit) or (program is not None and inside(path, program)):
            failures.append(f"{name} {path} dans le kit ou le programme")
        elif not writable_target(path):
            failures.append(f"{name} {path} : dossier non accessible en écriture pour ce compte ({existing_ancestor(path)})")
    if inside(data_root, destination) or inside(destination, data_root):
        failures.append(f"racine des données {data_root} et destination {destination} imbriquées : choisir deux dossiers distincts")
    for name in (POINTER, LAUNCHER):
        if (destination / name).is_dir():
            failures.append(f"{destination / name} est un dossier : rien ne le remplace")
    if menu is not None and ((menu / DESKTOP).is_dir() or (menu.exists() and not menu.is_dir())):
        failures.append(f"--menu {menu} : dossier attendu")
    if qdrant_storage is not None and (not qdrant_storage.is_absolute() or inside(qdrant_storage, destination)):
        failures.append(f"stockage Qdrant {qdrant_storage} : chemin absolu hors de la destination attendu")
    if model is not None and model not in (manifest.get("model_profiles") or {}):
        failures.append(f"Modèle {model} absent de ce kit ({', '.join(manifest.get('model_profiles') or {})})")
    if ports is not None:
        failures += check_ports(ctx, ports)
    target_dir = destination / manifest["kit_id"]
    if target_dir.exists() or target_dir.is_symlink():
        failures.append(f"version {manifest['kit_id']} déjà présente dans {target_dir} : jamais remplacée")
    needed = int(manifest["requirements"]["install_bytes_min"])
    free = probe.free_bytes(destination)
    if free < needed:
        failures.append(f"espace insuffisant sous {existing_ancestor(destination)} : {free / linux_kit.GIB:.1f} Gio libres, "
                        f"{needed / linux_kit.GIB:.1f} Gio nécessaires")
    else:
        passed.append(f"{free / linux_kit.GIB:.1f} Gio libres")
    filesystem = probe.filesystem(destination)
    if filesystem["fstype"] in REFUSED_FILESYSTEMS or filesystem["noexec"]:
        failures.append(f"destination sur {filesystem['fstype']}{' monté noexec' if filesystem['noexec'] else ''} "
                        f"({filesystem['mount']}) : liens symboliques et exécutables exigés, volume local seulement")
    if failures:
        raise InstallError("Précontrôles refusés, rien n'a été écrit : " + " ; ".join(failures) + ".")
    return passed


def system_check(ctx: Context, manifest: dict[str, Any], report: Report) -> None:
    """Bibliothèques, libstdc++ et ldd du poste cible, après la vérification complète du kit et sans écriture."""
    target, probe = manifest["target"], ctx.probe
    failures: list[str] = []
    available = probe.shared_libraries()
    missing = [name for name in target.get("system_libraries") or [] if name not in available]
    for name, reason in (target.get("optional_system_libraries") or {}).items():
        if name not in available:
            report.step("systeme", "orange", f"bibliothèque facultative absente : {name} ({reason}) ; installation poursuivie")
    if missing:
        users = target.get("system_libraries_required_by") or {}
        failures.append("bibliothèques du système absentes du chargeur (ldconfig) : "
                        + ", ".join(f"{name} (pour {', '.join(users.get(name, [])[:1]) or 'le kit'})" for name in missing))
    if target.get("glibcxx_min"):
        have = probe.glibcxx_max()
        if have is None:
            failures.append(f"libstdc++.so.6 introuvable : GLIBCXX {target['glibcxx_min']} exigé")
        elif linux_kit.version_tuple(have) < linux_kit.version_tuple(target["glibcxx_min"]):
            failures.append(f"libstdc++ du poste en GLIBCXX {have} : GLIBCXX {target['glibcxx_min']} exigé")
    for relative in target.get("ldd_checks") or [linux_kit.TESSERACT_BINARY]:
        label = "Tesseract" if relative == target.get("tesseract", linux_kit.TESSERACT_BINARY) else relative.rsplit("/", 1)[-1]
        linked = probe.ldd(ctx.kit / relative)
        unresolved = [line.strip() for line in (linked.stdout + "\n" + linked.stderr).splitlines() if "not found" in line]
        if linked.returncode or unresolved:
            failures.append(f"bibliothèques système de {label} manquantes ou trop anciennes ("
                            + ("; ".join(unresolved[:6]) or linked.stderr.strip()[-300:]) + ")")
    if failures:
        raise InstallError("Contrôles du système refusés, rien n'a été écrit : " + " ; ".join(failures)
                           + ". Faire installer ces bibliothèques par l'administrateur du poste.")
    report.step("systeme", "ok", f"{len(target.get('system_libraries') or [])} bibliothèques, GLIBCXX, "
                                 f"{len(target.get('ldd_checks') or [])} contrôles ldd")


def verify_whole_kit(ctx: Context, report: Report) -> None:
    result = linux_kit.verify_kit(ctx.kit)
    if result["status"] != "verified":
        details = result["altered_or_missing"][:3] + result["links_altered_or_missing"][:3] + result["unexpected"][:3] + result["problems"]
        raise InstallError(f"Kit non conforme ({', '.join(map(str, details))}) : recopier le kit ; rien n'a été installé.")
    report.step("kit", "ok", f"{result['files']} fichiers et {result['links']} liens conformes")


# --- Étapes communes ------------------------------------------------------------------------------------------------------

def rewrite_python_prefix(program: Path, manifest: dict[str, Any]) -> int:
    """Jeton du préfixe de CPython remplacé par le préfixe réel du programme installé, comme uv à l'installation."""
    prefix = str((program / ".runtime/python" / manifest["python"]["key"]).resolve()).encode()
    rewritten = 0
    for item in manifest.get("neutralizations", []):
        if not item.get("rewrite_at_install"):
            continue
        path = program / item["path"]
        data = path.read_bytes()
        token = item["token"].encode()
        if data.count(token) != item["replacements"]:
            raise InstallError(f"{item['path']} : {data.count(token)} jetons pour {item['replacements']} attendus")
        linux_kit.write_atomic(path, data.replace(token, prefix), mode=0o644)
        rewritten += item["replacements"]
    return rewritten


def prepare_program(ctx: Context, report: Report, manifest: dict[str, Any], program: Path) -> None:
    """Copie vérifiée, préfixe de CPython, environnement isolé hors ligne et précompilation."""
    copy = linux_kit.install_copy(ctx.kit, program)
    report.step("copie", "ok", f"{copy['files']} fichiers et {copy['links']} liens dans {program}")
    report.step("python", "ok", f"préfixe de CPython réécrit ({rewrite_python_prefix(program, manifest)} occurrences)")
    bootstrap = ctx.runner.run([str(program / "bootstrap.sh"), "--offline", "--no-dev"], cwd=program, timeout=3600)
    if bootstrap.returncode:
        raise InstallError(f"Environnement isolé non créé : {(bootstrap.stderr or bootstrap.stdout).strip()[-600:]}")
    report.step("environnement", "ok", "bootstrap.sh --offline --no-dev")
    # Précompilation de ce qu'importera l'exploitation : le dossier programme ne reçoit plus de bytecode ensuite. Quelques
    # fichiers d'exemple des paquets ne compilent pas (syntaxe d'un autre Python) : code de sortie consigné, non bloquant.
    stdlib = program / ".runtime/python" / manifest["python"]["key"] / "lib/python3.12"
    compiled = ctx.runner.run([str(venv_python(program)), "-m", "compileall", "-q", "-j", "0", str(stdlib),
                               str(program / ".venv/lib/python3.12/site-packages"), str(program / "services"), str(program / "tools")],
                              cwd=program, timeout=3600)
    report.step("precompilation", "ok", f"compileall, code {compiled.returncode}")


def doctor_gate(ctx: Context, report: Report, program: Path, profile: str) -> dict[str, Any]:
    doctor = rag(ctx, program, "doctor", "--profile", profile)
    verdict = doctor.get("verdict") or {}
    report.data["verdict_before_start"] = verdict
    red = [item for item in verdict.get("rubrics", []) if item.get("level") == RED]
    if doctor.get("_returncode") or not verdict:
        raise InstallError(f"Vérification impossible : {doctor.get('message')}")
    if red:
        raise InstallError("Vérification refusée : " + " ".join(f"{item.get('message')} {item.get('action') or ''}".strip() for item in red))
    report.step("doctor", "ok", str(verdict.get("summary", "")))
    return verdict


def start_and_check(ctx: Context, report: Report, destination: Path, program: Path, profile: str, *, browser: bool) -> None:
    up = rag(ctx, program, "up", "--profile", profile)
    if up.get("status") != "running":
        raise InstallError(f"Démarrage refusé : {up.get('message')} Le programme est installé et désigné ; « atelier diagnostic » détaille l'état.")
    # up rend l'instance déjà en marche sur ces données si son profil est identique (supervisor.start) : elle doit être
    # celle de ce programme, jamais une instance d'une autre version.
    executable = (up.get("supervisor") or {}).get("executable")
    if not isinstance(executable, str) or not inside(Path(executable), program):
        raise InstallError(f"L'instance démarrée n'appartient pas au programme {program} (superviseur : {executable or 'inconnu'}) : une "
                           "autre version tourne sur ces données. L'arrêter (rag.sh down --profile <profil> de cette version), puis "
                           "« atelier ouvrir ».")
    mark_started(destination, program, holding_lock=True)
    report.data["started_on_data"] = True
    report.step("demarrage", "ok", str(up.get("instance_id", "")))
    doctor = rag(ctx, program, "doctor", "--profile", profile)
    verdict = doctor.get("verdict") or {}
    report.data["verdict"] = verdict
    for item in verdict.get("rubrics", []):
        ctx.say(item.get("level", "?"), item.get("rubric", ""), item.get("message", ""))
        if item.get("proposal"):
            print(f"      Proposition : {item['proposal']}", file=ctx.out)
    report.step("verdict", str(verdict.get("level", "?")), str(verdict.get("summary", "")))
    control = rag(ctx, program, "selftest", "--profile", profile, timeout=3600)
    report.data["selftest"] = {key: value for key, value in control.items() if key != "_returncode"}
    for item in control.get("steps", []):
        ctx.say(item.get("status", "?"), item.get("step", ""), item.get("detail", ""))
    if control.get("level") == RED or control.get("_returncode"):
        raise InstallError(f"{control.get('summary') or control.get('message')} Le programme est installé et désigné ; « atelier "
                           "diagnostic » et le rapport d'installation détaillent l'échec.")
    report.step("controle", str(control.get("level", "ok")), str(control.get("summary", "")))
    opened = rag(ctx, program, "open", "--profile", profile, *([] if browser else ["--no-browser"]))
    if opened.get("_returncode"):
        report.step("ouverture", "orange", f"{opened.get('message')} ; « atelier ouvrir --no-browser » affiche le lien")
    elif browser:
        report.step("ouverture", "ok", "atelier ouvert dans le navigateur par défaut")
    else:
        # Lien à usage unique : affiché au terminal, jamais écrit dans un rapport.
        print(f"Lien à usage unique, à ouvrir dans un navigateur de ce poste : {opened.get('url')}", file=ctx.out)
        report.step("ouverture", "ok", "lien à usage unique affiché")


def version_entry(manifest: dict[str, Any], program: Path, data_root: Path, profiles: dict[str, str], model: str, **extra: Any) -> dict[str, Any]:
    return {"kit_id": manifest["kit_id"], "program": str(program), "python": manifest["python"]["executable"],
            "data_root": str(data_root), "profile": profiles[model], "profiles": profiles, "model": model,
            "started_on_data": False, **extra}


def remove_new_program(destination: Path, program: Path, report: Report) -> bool:
    """Retire un dossier programme créé par cette exécution, jamais celui que le pointeur désigne (relu sur disque)."""
    current = designated(destination)
    if current and Path(current["program"]) == program:
        return False
    if program.exists() and not program.is_symlink() and (program / linux_kit.MANIFEST).is_file():
        shutil.rmtree(program)
        report.data["new_program_removed"] = str(program)
    return True


def failure_message(ctx: Context, destination: Path, program: Path, previous: dict[str, Any] | None) -> None:
    """Message exact après un échec : version que le pointeur désigne vraiment, et la suite possible."""
    current = designated(destination)
    if current and Path(current["program"]) == program:
        print(f"La version {current['kit_id']} est la version courante (bascule faite) ; « atelier diagnostic » détaille son état"
              + (f", « installer.sh rollback --destination {destination} » revient à {previous['kit_id']}" if previous else "") + ".",
              file=ctx.out)
    elif current and previous and current["program"] == previous["program"]:
        print(f"La version {current['kit_id']} reste la version courante ; la relancer par « {destination / LAUNCHER} ouvrir ».",
              file=ctx.out)


def running_profile(ctx: Context, program: Path, profiles: dict[str, str]) -> tuple[str | None, str | None]:
    """Profil de l'instance en marche sur ces données parmi les profils connus ; refus si elle tourne avec un autre."""
    foreign = False
    for model, profile in profiles.items():
        state = rag(ctx, program, "status", "--profile", profile)
        if state.get("status") in RUNNING:
            if state.get("profile_matches_current"):
                return model, profile
            foreign = True
    if foreign:
        raise InstallError("Une instance tourne sur ces données avec un profil que l'installation ne connaît pas : l'arrêter "
                           "(rag.sh down --profile <ce profil>) avant la mise à jour ; rien n'a été installé.")
    return None, None


# --- Sous-commandes -----------------------------------------------------------------------------------------------------

def install(ctx: Context, args: argparse.Namespace) -> int:
    manifest = read_manifest(ctx.kit)
    destination, data_root = args.destination.absolute(), args.data_root.absolute()
    menu = args.menu.absolute() if args.menu else None
    model = args.model or manifest["default_model"]
    program = destination / manifest["kit_id"]

    def refuse_existing() -> None:
        pointer = read_pointer(destination)
        if pointer and pointer.get("current"):
            raise InstallError(f"Un atelier est déjà installé dans {destination} (version {pointer['current']['kit_id']}) : pour "
                               "installer cette version à côté, utiliser la sous-commande update. Rien n'a été installé.")
        if (data_root / "profile.yaml").exists():
            raise InstallError(f"Un profil existe déjà dans {data_root} : il n'est jamais remplacé. Installer avec une autre racine de "
                               "données, ou mettre à jour l'installation existante (update). Rien n'a été installé.")

    refuse_existing()
    passed = precheck(ctx, manifest, destination, data_root, qdrant_storage=args.qdrant_storage, menu=menu, model=model,
                      ports=args.ports)
    report = Report(ctx, "install", kit=str(ctx.kit), kit_id=manifest["kit_id"], destination=str(destination), data_root=str(data_root))
    report.step("precontroles", "ok", ", ".join(passed))
    verify_whole_kit(ctx, report)
    system_check(ctx, manifest, report)
    created: dict[str, str] = {}
    with installer_lock(destination):
        refuse_existing()
        try:
            data_root.mkdir(parents=True, exist_ok=True)
            report.path = data_root / f"install-{stamp(ctx.clock())}.json"
            prepare_program(ctx, report, manifest, program)
            arguments = ["--target", str(data_root)]
            arguments += ["--model", model] if model != manifest.get("default_model") else []
            arguments += ["--qdrant-storage", str(args.qdrant_storage)] if args.qdrant_storage else []
            arguments += ["--ports", args.ports] if args.ports else []
            initialized = rag(ctx, program, "init-profile", *arguments)
            if initialized.get("status") != "created":
                raise InstallError(f"Profil non créé : {initialized.get('message')}")
            created[model] = initialized["profile"]
            report.step("profil", "ok", f"{initialized['profile']} ({model})")
            others = [name for name in manifest.get("model_profiles") or {} if name != model]
            created.update(derive_profiles(ctx, report, python=venv_python(program), scripts=program, program=program,
                                           like=initialized["profile"], data_root=data_root, models=others))
            doctor_gate(ctx, report, program, created[model])
            entry = version_entry(manifest, program, data_root, dict(created), model, installed_utc=ctx.clock().isoformat())
            switch(destination, read_pointer(destination), entry, None, {"event": "install", "kit_id": manifest["kit_id"],
                                                                         "at_utc": ctx.clock().isoformat(), "report": str(report.path)},
                   menu=menu)
            report.step("bascule", "ok", f"{destination / POINTER} et lanceur {destination / LAUNCHER}")
            if not args.no_start:
                start_and_check(ctx, report, destination, program, created[model], browser=not args.no_browser)
            report.data.update(status="installed", program=str(program), profiles=created)
            print(f"Installation terminée. Lancer l'atelier : {destination / LAUNCHER} ouvrir. Rapport : {report.path}", file=ctx.out)
            return 0
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            if remove_new_program(destination, program, report):
                # Cette version n'est pas désignée : les profils créés par cette exécution sont retirés avec elle.
                for path in created.values():
                    Path(path).unlink(missing_ok=True)
            failure_message(ctx, destination, program, None)
            raise
        finally:
            report.save()


def update(ctx: Context, args: argparse.Namespace) -> int:
    manifest = read_manifest(ctx.kit)
    destination = args.destination.absolute()
    menu = args.menu.absolute() if args.menu else None
    with installer_lock(destination):
        pointer = read_pointer(destination)
        if not pointer or not pointer.get("current"):
            raise InstallError(f"Aucune version installée n'est désignée dans {destination / POINTER} : utiliser install.")
        current = pointer["current"]
        if current["kit_id"] == manifest["kit_id"]:
            raise InstallError(f"La version {manifest['kit_id']} est déjà la version courante : rien à mettre à jour.")
        previous_program, profile = Path(current["program"]), current["profile"]
        data_root = Path(current["data_root"])
        program = destination / manifest["kit_id"]
        available = manifest.get("model_profiles") or {}
        if current.get("model") not in available:
            raise InstallError(f"Le modèle du profil en place ({current.get('model')}) n'est pas livré par ce kit ; rien n'a été installé.")
        passed = precheck(ctx, manifest, destination, data_root, program=previous_program, menu=menu)
        # Profils des modèles nouveaux : dérivation contrôlée avant toute sauvegarde ni copie, par le code et les profils livrés
        # du nouveau kit, avec l'environnement de la version en place.
        missing = [name for name in available if name not in (current.get("profiles") or {})]
        derive_profiles(ctx, None, python=venv_python(previous_program), scripts=ctx.kit, program=ctx.kit, like=profile,
                        data_root=data_root, models=missing, check=True)
        report = Report(ctx, "update", kit=str(ctx.kit), kit_id=manifest["kit_id"], destination=str(destination),
                        data_root=str(data_root), previous=current["kit_id"])
        report.path = data_root / f"update-{stamp(ctx.clock())}.json"
        report.step("precontroles", "ok", ", ".join(passed) + f" ; profils dérivables : {', '.join(missing) or 'aucun nouveau'}")
        stopped = False
        new_profiles: list[str] = []
        try:
            verify_whole_kit(ctx, report)
            system_check(ctx, manifest, report)
            # Sauvegarde vérifiée des données avant toute copie : elle exige l'instance démarrée (up la retrouve), avec le
            # profil de l'instance déjà en marche s'il y en a une (par exemple le 4B).
            active_model, active_profile = running_profile(ctx, previous_program, current.get("profiles") or {current["model"]: profile})
            source = active_profile or profile
            if active_model:
                report.step("instance", "ok", f"instance en marche avec {source} (modèle {active_model}) : sauvegarde par cette instance")
            started = rag(ctx, previous_program, "up", "--profile", source)
            if started.get("status") != "running":
                raise InstallError(f"La version en place ne démarre pas ({started.get('message')}) ; sauvegarde impossible, rien n'a été installé.")
            backup = rag(ctx, previous_program, "backup", "--profile", source, timeout=7200)
            if not backup.get("path"):
                raise InstallError(f"Sauvegarde refusée : {backup.get('message')} Rien n'a été installé.")
            verified = rag(ctx, previous_program, "verify", "--profile", source, "--path", str(backup["path"]), timeout=7200)
            if verified.get("state") != "verified":
                raise InstallError(f"Sauvegarde {backup['path']} non vérifiée : {verified.get('message')} Rien n'a été installé.")
            stopped_state = rag(ctx, previous_program, "down", "--profile", source)
            if stopped_state.get("status") not in {"stopped", "failed"}:
                raise InstallError(f"Arrêt de la version en place non confirmé (état {stopped_state.get('status')}) ; rien n'a été installé.")
            stopped = True
            report.data["backup"] = str(backup["path"])
            report.step("sauvegarde", "ok", f"{backup['path']} vérifiée ; version {current['kit_id']} arrêtée")
            prepare_program(ctx, report, manifest, program)
            profiles = {name: path for name, path in (current.get("profiles") or {}).items() if name in available}
            before = {path for path in (data_root / f"profile-{model_slug(name)}.yaml" for name in missing) if path.exists()}
            report.step("profil", "ok", f"{profile} repris")
            made = derive_profiles(ctx, report, python=venv_python(program), scripts=program, program=program, like=profile,
                                   data_root=data_root, models=missing)
            new_profiles = [path for path in made.values() if Path(path) not in before]
            profiles.update(made)
            doctor_gate(ctx, report, program, profile)
            # Dernier contrôle avant la bascule : aucune instance ne doit avoir été relancée sur ces données depuis l'arrêt
            # (ses écritures seraient postérieures à la sauvegarde, et up de la nouvelle version la reprendrait).
            late = rag(ctx, program, "status", "--profile", profile)
            if late.get("status") in RUNNING:
                relaunched = (late.get("supervisor") or {}).get("executable") or "exécutable inconnu"
                raise InstallError(f"Une instance a été relancée pendant la mise à jour ({relaunched}) : ses écritures sont postérieures à la "
                                   f"sauvegarde {backup['path']}. Rien n'a été basculé ; l'arrêter (« atelier arreter »), puis relancer la "
                                   "mise à jour.")
            entry = version_entry(manifest, program, data_root, profiles, current["model"], installed_utc=ctx.clock().isoformat(),
                                  backup=str(backup["path"]))
            switch(destination, pointer, entry, current, {"event": "update", "kit_id": manifest["kit_id"], "from": current["kit_id"],
                                                          "backup": str(backup["path"]), "at_utc": ctx.clock().isoformat(),
                                                          "report": str(report.path)}, menu=menu)
            report.step("bascule", "ok", f"{current['kit_id']} → {manifest['kit_id']}")
            if not args.no_start:
                start_and_check(ctx, report, destination, program, profile, browser=not args.no_browser)
            report.data.update(status="updated", program=str(program))
            print(f"Mise à jour terminée. Retour arrière possible : installer.sh rollback --destination {destination}. Rapport : {report.path}",
                  file=ctx.out)
            return 0
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            if remove_new_program(destination, program, report):
                for path in new_profiles:
                    Path(path).unlink(missing_ok=True)
            if stopped or designated(destination) is not None:
                failure_message(ctx, destination, program, current)
            if report.data.get("backup"):
                print(f"Sauvegarde conservée : {report.data['backup']}.", file=ctx.out)
            raise
        finally:
            report.save()


def new_version_started(ctx: Context, entry: dict[str, Any]) -> bool:
    """La version a-t-elle démarré sur les données ? Pointeur, puis état de l'instance (exécutable du superviseur)."""
    if entry.get("started_on_data"):
        return True
    program = Path(entry["program"])
    state = rag(ctx, program, "status", "--profile", entry["profile"])
    if state.get("_returncode"):
        return True  # état illisible : la restauration, plus sûre, est retenue
    executable = (state.get("supervisor") or {}).get("executable")
    return isinstance(executable, str) and inside(Path(executable), program)


def rollback(ctx: Context, args: argparse.Namespace) -> int:
    destination = args.destination.absolute()
    with installer_lock(destination):
        pointer = read_pointer(destination)
        if not pointer or not pointer.get("current") or not pointer.get("previous"):
            raise InstallError("Aucune version précédente n'est désignée : retour arrière impossible.")
        current, previous = pointer["current"], pointer["previous"]
        if previous.get("rolled_back"):
            raise InstallError(f"Retour arrière déjà effectué : la version précédente {previous['kit_id']} est celle qu'il a abandonnée ; "
                               "aucun second retour arrière n'est proposé (réinstaller une version depuis son kit si nécessaire).")
        old_program, new_program = Path(previous["program"]), Path(current["program"])
        if not (old_program / "rag.sh").is_file():
            raise InstallError(f"Version précédente absente ({old_program}) : retour arrière impossible.")
        data_root = Path(current["data_root"])
        report = Report(ctx, "rollback", destination=str(destination), current=current["kit_id"], previous=previous["kit_id"])
        report.path = data_root / f"rollback-{stamp(ctx.clock())}.json"
        try:
            state = rag(ctx, new_program, "status", "--profile", current["profile"])
            if state.get("status") in RUNNING:
                down = rag(ctx, new_program, "down", "--profile", current["profile"])
                if down.get("status") not in {"stopped", "failed"}:
                    raise InstallError(f"Arrêt de la version {current['kit_id']} non confirmé ; rien n'a été basculé.")
                report.step("arret", "ok", current["kit_id"])
            # Entrée de retour : la sauvegarde de sa propre mise à jour ne vaut plus pour elle.
            restored_entry = {key: value for key, value in previous.items()
                              if key not in {"backup", "rolled_back", "restored_from", "started_on_data"}}
            restored_entry["started_on_data"] = False
            if new_version_started(ctx, current):
                restored_entry.update(restore_previous(ctx, report, current, old_program, data_root, args.restore_target, destination,
                                                       new_program))
            else:
                report.step("donnees", "ok", f"la version {current['kit_id']} n'a jamais démarré sur les données : profils conservés")
            switch(destination, pointer, restored_entry, {**current, "rolled_back": True},
                   {"event": "rollback", "from": current["kit_id"], "to": previous["kit_id"], "at_utc": ctx.clock().isoformat(),
                    "report": str(report.path)})
            report.step("bascule", "ok", f"{current['kit_id']} → {previous['kit_id']}")
            report.data["status"] = "rolled_back"
            print(f"Retour arrière terminé. Lancer l'atelier : {destination / LAUNCHER} ouvrir.", file=ctx.out)
            return 0
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            raise
        finally:
            report.save()


def restore_previous(ctx: Context, report: Report, current: dict[str, Any], old_program: Path, data_root: Path,
                     restore_target: Path | None, destination: Path, new_program: Path) -> dict[str, Any]:
    """Restauration de la sauvegarde de la mise à jour par l'ancienne version, dans une racine neuve ; ports de l'utilisateur
    repris s'ils sont libres ; profils des autres modèles régénérés sur les données restaurées."""
    backup = current.get("backup")
    if not backup:
        raise InstallError("La nouvelle version a démarré sur les données et aucune sauvegarde n'est associée à sa mise à jour : "
                           "restauration impossible, rien n'a été basculé.")
    target = (restore_target or data_root.with_name(f"{data_root.name}-retour-{stamp(ctx.clock())}")).absolute()
    if inside(target, old_program) or inside(target, new_program) or inside(target, destination):
        raise InstallError(f"Racine de restauration {target} dans un dossier programme : choisir une racine de données neuve.")
    original = profile_info(ctx, new_program, Path(current["profile"])) if venv_python(new_program).exists() else None
    restored = rag(ctx, old_program, "restore", "--path", backup, "--target", str(target), timeout=7200)
    if restored.get("state") != "restored_storage_verified":
        raise InstallError(f"Restauration refusée : {restored.get('message') or restored.get('error')} ; rien n'a été basculé.")
    profile = target / "restored-profile.yaml"
    report.step("restauration", "ok", f"{backup} restaurée dans {target} par la version {Path(old_program).name}")
    if original:
        ports = original["ports"]
        adopted = profiles_tool(ctx, venv_python(old_program), old_program, "ports", "--profile", str(profile), "--ports",
                                f"{ports['app']},{ports['qdrant']},{ports['ollama']}", cwd=old_program)
        if adopted["status"] == "adopted":
            report.step("ports", "ok", f"ports de l'utilisateur repris ({ports['app']}, {ports['qdrant']}, {ports['ollama']})")
        else:
            report.step("ports", "orange", f"ports de l'utilisateur occupés ({', '.join(adopted.get('busy') or [])}) : la restauration garde "
                                            "8795, 6343 et 11445 ; les changer dans le profil restauré une fois libres")
        storage = original["locations"].get("qdrant.storage")
        report.step("stockage", "ok", f"stockage Qdrant restauré dans {target / 'qdrant'} ; l'ancien stockage {storage} garde les "
                                      "données de la version abandonnée et n'est pas réutilisé")
    else:
        report.step("ports", "orange", "profil de la version abandonnée illisible : ports de la restauration (8795, 6343, 11445) conservés")
    info = profile_info(ctx, old_program, profile)
    model = info["source_model"] or info["model"]
    old_manifest = read_json(old_program / linux_kit.MANIFEST)
    others = [name for name in old_manifest.get("model_profiles") or {} if name != model]
    profiles = {model: str(profile), **derive_profiles(ctx, report, python=venv_python(old_program), scripts=old_program,
                                                       program=old_program, like=str(profile), data_root=target, models=others)}
    report.data["restored"] = {"backup": backup, "target": str(target)}
    return {"profile": str(profile), "profiles": profiles, "data_root": str(target), "model": model, "restored_from": backup}


def uninstall(ctx: Context, args: argparse.Namespace) -> int:
    destination = args.destination.absolute()
    program = destination / args.kit_id
    report = Report(ctx, "uninstall", destination=str(destination), kit_id=args.kit_id, program=str(program))
    if not destination.is_dir():
        raise InstallError(f"Destination absente : {destination} ; rien n'a été supprimé.")
    report.path = destination / f"uninstall-{args.kit_id}-{stamp(ctx.clock())}.json"
    with installer_lock(destination):
        try:
            # Gardes : dossier réel, enfant direct de la destination, porteur des marqueurs d'un kit de cette version.
            if program.is_symlink() or not program.is_dir():
                raise InstallError(f"{program} n'est pas un dossier d'installation (absent ou lien) ; rien n'a été supprimé.")
            if Path(os.path.realpath(program)).parent != Path(os.path.realpath(destination)):
                raise InstallError(f"{program} n'est pas directement sous {destination} ; rien n'a été supprimé.")
            for marker in (linux_kit.MANIFEST, linux_kit.SUMS):
                path = program / marker
                if path.is_symlink() or not path.is_file():
                    raise InstallError(f"{program} n'est pas une installation de l'atelier ({marker} absent) ; rien n'a été supprimé.")
            if read_json(program / linux_kit.MANIFEST).get("kit_id") != args.kit_id:
                raise InstallError(f"{program} ne porte pas la version {args.kit_id} ; rien n'a été supprimé.")
            residues = [name for name in RUNTIME_DATA if (program / name).exists() or (program / name).is_symlink()]
            if residues:
                raise InstallError(f"données d'exécution dans le dossier programme ({', '.join(residues)}) : un profil y a écrit. Les "
                                   "déplacer ou les sauvegarder, puis relancer ; rien n'a été supprimé.")
            pointer = read_pointer(destination)
            entries = [entry for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous"))
                       if entry and Path(entry["program"]) == program]
            profiles = sorted({path for entry in entries for path in entry.get("profiles", {}).values()} | set(args.profile or []))
            for profile in profiles:
                if not Path(profile).is_file():
                    continue
                if inside(Path(profile), program):
                    raise InstallError(f"Le profil {profile} est dans le dossier programme ; rien n'a été supprimé.")
                if venv_python(program).exists():
                    info = profile_info(ctx, program, Path(profile))
                    within = [f"{key} {value}" for key, value in info["locations"].items() if inside(Path(value), program)]
                    if within:
                        raise InstallError(f"Le profil {profile} écrit dans le dossier programme ({'; '.join(within)}) ; rien n'a été supprimé.")
                state = rag(ctx, program, "status", "--profile", profile)
                executable = (state.get("supervisor") or {}).get("executable")
                if state.get("status") in RUNNING and executable and inside(Path(executable), program):
                    down = rag(ctx, program, "down", "--profile", profile)
                    if down.get("status") not in {"stopped", "failed"}:
                        raise InstallError(f"Arrêt de l'atelier non confirmé (état {down.get('status')}) ; rien n'a été supprimé.")
                    report.step("arret", "ok", f"instance de {args.kit_id} arrêtée")
            if not shutil.rmtree.avoids_symlink_attacks:
                raise InstallError("Suppression sûre impossible sur ce système (rmtree sans protection contre les liens) ; rien n'a été supprimé.")
            if pointer and entries:
                # Pointeur d'abord : il ne désigne jamais un dossier en cours de suppression.
                current = None if pointer.get("current") and Path(pointer["current"]["program"]) == program else pointer.get("current")
                previous = None if pointer.get("previous") and Path(pointer["previous"]["program"]) == program else pointer.get("previous")
                switch(destination, pointer, current, previous, {"event": "uninstall", "kit_id": args.kit_id,
                                                                 "at_utc": ctx.clock().isoformat(), "report": str(report.path)})
                report.step("pointeur", "ok", "version courante retirée, lanceur supprimé" if not current else "version courante inchangée")
            shutil.rmtree(program)
            report.step("programme", "ok", f"{program} retiré, liens supprimés sans être suivis")
            report.data["status"] = "uninstalled"
            print("Données conservées : profils et dossiers qu'ils désignent. Les supprimer reste une décision de l'utilisateur.", file=ctx.out)
            return 0
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            raise
        finally:
            report.save()


def repair(ctx: Context, args: argparse.Namespace) -> int:
    """Lanceur et entrée de menu régénérés depuis le pointeur, seule source de vérité de la version courante."""
    destination = args.destination.absolute()
    with installer_lock(destination):
        pointer = read_pointer(destination)
        if not pointer:
            raise InstallError(f"Aucun pointeur {destination / POINTER} : rien à réparer.")
        current = pointer.get("current")
        if current and not (Path(current["program"]) / linux_kit.MANIFEST).is_file():
            raise InstallError(f"Le pointeur désigne {current['program']}, absent : revenir à la version précédente (rollback) ou réinstaller.")
        refresh_derived(destination, pointer)
        print(f"Lanceur {'régénéré pour la version ' + current['kit_id'] if current else 'retiré (aucune version courante)'}"
              + (f" ; entrée de menu {pointer['menu_entry']}" if pointer.get("menu_entry") else "") + ".", file=ctx.out)
        return 0


def status(ctx: Context, args: argparse.Namespace) -> int:
    destination = args.destination.absolute()
    pointer = read_pointer(destination)
    versions = sorted(path.name for path in destination.iterdir() if path.is_dir() and not path.is_symlink()
                      and (path / linux_kit.MANIFEST).is_file()) if destination.is_dir() else []
    result: dict[str, Any] = {"destination": str(destination), "versions": versions, "pointer": pointer, "problems": []}
    current = (pointer or {}).get("current")
    if current:
        program = Path(current["program"])
        launcher = destination / LAUNCHER
        if not launcher.is_file() or f"version {current['kit_id']}." not in launcher.read_text(encoding="utf-8"):
            result["problems"].append(f"lanceur absent ou d'une autre version : « installer.sh repair --destination {destination} » "
                                      "le régénère depuis le pointeur")
        if not (program / linux_kit.MANIFEST).is_file():
            result["problems"].append(f"programme courant absent : {program}")
        elif not Path(current["profile"]).is_file():
            result["problems"].append(f"profil absent : {current['profile']}")
        else:
            state = rag(ctx, program, "status", "--profile", current["profile"])
            result["instance"] = {key: state.get(key) for key in ("status", "instance_id", "generation", "profile_matches_current")}
    print(json.dumps(result, ensure_ascii=False, indent=2), file=ctx.out)
    return 0 if not result["problems"] else 1


def run(ctx: Context, args: argparse.Namespace) -> int:
    """Actions du lanceur `atelier`, toujours avec un profil de la racine des données."""
    destination = args.destination.absolute()
    pointer = read_pointer(destination)
    current = (pointer or {}).get("current")
    if not current:
        raise InstallError(f"Aucune version courante dans {destination} : réinstaller ou revenir à une version (rollback).")
    program = Path(current["program"])
    if Path(os.path.realpath(program)) != Path(os.path.realpath(ctx.kit)):
        raise InstallError(f"Lanceur périmé : il vise {ctx.kit}, la version courante est {program} ; « installer.sh repair "
                           f"--destination {destination} » le régénère.")
    model = args.modele or current.get("model")
    profile = (current.get("profiles") or {}).get(model)
    if not profile:
        raise InstallError(f"Modèle {model} non installé ; disponibles : {', '.join(current.get('profiles') or {})}")
    action = args.action
    if action in {"ouvrir", "sauvegarder"} and not lock_is_free(destination):
        raise InstallError(f"Une opération d'installation est en cours sur {destination} (installation, mise à jour, retour arrière ou "
                           f"désinstallation) : « atelier {action} » est refusé jusqu'à sa fin, pour ne pas relancer ni sauvegarder "
                           "une version en cours de remplacement.")
    if action == "ouvrir":
        print("Démarrage de l'atelier si nécessaire (jusqu'à deux minutes au premier lancement)…", file=ctx.out, flush=True)
        up = rag(ctx, program, "up", "--profile", profile)
        if up.get("status") != "running":
            raise InstallError(f"{up.get('message')} (pour changer de modèle : atelier arreter, puis atelier ouvrir --modele <tag>)")
        mark_started(destination, program)
        opened = rag(ctx, program, "open", "--profile", profile, *(["--no-browser"] if args.no_browser else []))
        if opened.get("_returncode"):
            raise InstallError(f"{opened.get('message')} ; « atelier ouvrir --no-browser » affiche le lien à coller dans un navigateur")
        print(f"Lien à usage unique : {opened['url']}" if args.no_browser else "Atelier ouvert dans le navigateur par défaut.", file=ctx.out)
        return 0
    command = {"arreter": "down", "diagnostic": "doctor", "etat": "status", "sauvegarder": "backup"}[action]
    result = rag(ctx, program, command, "--profile", profile, timeout=7200)
    if result.get("_returncode"):
        raise InstallError(str(result.get("message")))
    if action == "arreter":
        print("Atelier arrêté. Les documents, l'index et les sauvegardes sont conservés.", file=ctx.out)
    elif action == "diagnostic":
        verdict = result.get("verdict") or {}
        print(verdict.get("summary", ""), file=ctx.out)
        for item in verdict.get("rubrics", []):
            print(f"[{item.get('level')}] {item.get('rubric')} : {item.get('message')}", file=ctx.out)
            for key, label in (("action", ""), ("proposal", "Proposition : ")):
                if item.get(key):
                    print(f"        {label}{item[key]}", file=ctx.out)
    elif action == "etat":
        print(f"État : {result.get('status')}. {result.get('generation') or ''}".strip(), file=ctx.out)
    else:
        print(f"Sauvegarde écrite dans {result.get('path')}.", file=ctx.out)
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(prog="installer.sh", description=__doc__.splitlines()[0])
    main.add_argument("--kit", type=Path, default=HERE, help=argparse.SUPPRESS)
    sub = main.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        command = sub.add_parser(name, help="installer ce kit" if name == "install" else "installer ce kit à côté de la version courante")
        command.add_argument("--destination", type=Path, required=True, help="dossier des versions du programme")
        if name == "install":
            command.add_argument("--data-root", type=Path, required=True, help="racine des données, hors de la destination")
            command.add_argument("--qdrant-storage", type=Path, help="stockage Qdrant hors de la racine des données")
            command.add_argument("--ports", help="ports API,Qdrant,Ollama")
            command.add_argument("--model", help="modèle du profil principal (défaut : celui du kit, qwen3.5:2b)")
        command.add_argument("--menu", type=Path, help="dossier où écrire une entrée de menu .desktop (jamais par défaut)")
        command.add_argument("--no-start", action="store_true", help="ne pas démarrer l'atelier après l'installation")
        command.add_argument("--no-browser", action="store_true", help="afficher le lien à usage unique au lieu d'ouvrir le navigateur")
    back = sub.add_parser("rollback", help="revenir à la version précédente")
    back.add_argument("--destination", type=Path, required=True)
    back.add_argument("--restore-target", type=Path, help="racine neuve de restauration si la nouvelle version a démarré sur les données")
    remove = sub.add_parser("uninstall", help="retirer le dossier d'une version ; données conservées")
    remove.add_argument("--destination", type=Path, required=True)
    remove.add_argument("--kit-id", required=True)
    remove.add_argument("--profile", action="append", help="profil supplémentaire à contrôler (répétable)")
    fix = sub.add_parser("repair", help="régénérer le lanceur et l'entrée de menu depuis le pointeur")
    fix.add_argument("--destination", type=Path, required=True)
    state = sub.add_parser("status", help="version courante, versions présentes, état de l'instance")
    state.add_argument("--destination", type=Path, required=True)
    launch = sub.add_parser("run", help=argparse.SUPPRESS)
    launch.add_argument("--destination", type=Path, required=True)
    launch.add_argument("action", nargs="?", default="ouvrir", choices=["ouvrir", "arreter", "diagnostic", "etat", "sauvegarder"])
    launch.add_argument("--modele")
    launch.add_argument("--no-browser", action="store_true")
    return main


COMMANDS = {"install": install, "update": update, "rollback": rollback, "uninstall": uninstall, "repair": repair, "status": status,
            "run": run}


def main(argv: list[str] | None = None, ctx: Context | None = None) -> int:
    args = parser().parse_args(argv)
    ctx = ctx or Context(kit=args.kit.resolve())
    try:
        return COMMANDS[args.command](ctx, args)
    except (InstallError, linux_kit.KitError) as error:
        print(f"Arrêt : {error}", file=ctx.out)
        return 1
    except Exception as error:  # noqa: BLE001 - message lisible au lieu d'une trace ; le rapport garde le détail
        print(f"Arrêt : {type(error).__name__} : {error}", file=ctx.out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
