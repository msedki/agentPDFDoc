"""Installateur Linux (R26-KIT-01, R26-KIT-04) : précontrôles sans écriture, récapitulatif confirmé, séquence d'installation,
mise à jour, bascule atomique, retour arrière, désinstallation gardée, intégration au bureau et lanceur `atelier`.

Doubles nommés : `PosteSimule` remplace les lectures du poste (architecture, glibc, noyau, mémoire, place et système de
fichiers par chemin, montages, setpriv, ldd, ldconfig, os-release) ; `ProgrammeSimule` remplace les commandes lancées
(rag.sh, bootstrap.sh, compileall, linux_profiles.py) et consigne leur ordre ; `CopieAvecProgression` ajoute le rappel de
progression à la copie réelle ; le terminal et les réponses de l'utilisateur sont simulés par `context(tty=…, answers=…)` ;
`euid_root` simule un compte root, `port_libre_hors` le sondage d'un port, `killed_install` un arrêt brutal (installation
lancée dans un processus séparé, tué par SIGKILL à l'étape voulue), `strip_desktop_integration` une installation faite par
l'installateur de 78ec95c ; les doubles `interrupted_*` lèvent KeyboardInterrupt à l'endroit voulu.
Le kit, la copie, les liens, la réécriture du préfixe de CPython, le pointeur, le lanceur, l'entrée de menu, l'icône, la
commande `atelier` et le registre sont réels, sous TMPDIR, avec HOME et XDG_* propres à chaque test : `context` refuse un
environnement qui désigne le compte réel (`refuse_the_real_account`), y compris hors de pytest, et la garde de
tests/unit/conftest.py fait échouer tout essai qui écrirait sous le HOME réel.
"""

import argparse
import hashlib
import importlib.machinery
import io
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("installateur Linux", allow_module_level=True)

import pwd  # noqa: E402 - module POSIX, importé après le refus de Windows

from tests.unit.test_dist_linux_kit import (  # noqa: E402
    PYTHON_KEY,
    fake_readelf,
    git,
    make_repository,
    no_host_library,
    no_l4t_release,
    no_package_owner,
    web_provenance,
    write,
)
from tools.dist import linux_install, linux_kit  # noqa: E402
from tools.dist.linux_install import Completed  # noqa: E402

SYSCONFIG = f".runtime/python/{PYTHON_KEY}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py"
GREEN = {"verdict": {"level": "vert", "summary": "Atelier prêt", "rubrics": [{"level": "vert", "rubric": "services", "message": "ok"}]}}
GIB = 1024**3
ICON_PATH = "tools/dist/assets/atelier-documentaire.svg"


def test_child_commands_use_the_explicit_profile_not_an_inherited_data_root(monkeypatch):
    monkeypatch.setenv("RAG_DATA_DIR", "/ancienne-qa/donnees")
    assert "RAG_DATA_DIR" not in linux_install.child_environment()


# Compte réel : dossier personnel lu dans la base des comptes, et variables XDG du processus au chargement du module.
ACCOUNT_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
ACCOUNT_XDG = {name: os.environ[name] for name in ("XDG_DATA_HOME", "XDG_STATE_HOME") if os.environ.get(name)}


def account_locations(environ) -> dict[str, Path]:
    """Emplacements du compte que l'installateur écrirait avec cet environnement : registre, entrées de menu, commande
    atelier et dossier par défaut de l'atelier (chemins réels)."""
    found = {}
    for name, location in (("registre", linux_install.registry_file), ("menu", linux_install.applications_dir),
                           ("commande", linux_install.user_bin), ("atelier", linux_install.default_base)):
        try:
            path = location(environ)
        except linux_install.InstallError:
            path = None
        if path is not None:
            found[name] = Path(os.path.realpath(path))
    return found


# Comptes protégés : le compte réel, toujours, et ceux qu'un essai désigne en plus (variable ATELIER_ESSAIS_COMPTES_PROTEGES,
# dossiers séparés par « : ») pour rejouer sans risque un aperçu lancé hors de la fixture isolated_home.
PROTECTED_HOMES = [ACCOUNT_HOME, *(Path(item) for item in os.environ.get("ATELIER_ESSAIS_COMPTES_PROTEGES", "").split(os.pathsep) if item)]
REAL_LOCATIONS = [location for protected in PROTECTED_HOMES for environ in ({"HOME": str(protected)}, {"HOME": str(protected), **ACCOUNT_XDG})
                  for location in account_locations(environ).values()]


def refuse_the_real_account(environ=None) -> None:
    """Garde de tous les doubles qui lancent l'installateur (`context`, donc `installed` et `killed_install`) : un environnement
    dont HOME ou XDG_* désignent le compte réel est refusé avant toute commande, dans pytest comme dans un aperçu lancé à côté
    (QA3-02 : le 7 octobre 2026 à 05:26 UTC, un tel aperçu, sans la fixture isolated_home, a écrit le registre réel)."""
    environ = os.environ if environ is None else environ
    touched = [f"{name} {path}" for name, path in account_locations(environ).items()
               if any(path == real or path.is_relative_to(real) for real in REAL_LOCATIONS)]
    if touched:
        raise RuntimeError("Essai de l'installateur sans HOME isolé : il écrirait dans le compte réel (" + " ; ".join(touched) + "). "
                           "Employer la fixture isolated_home, ou fixer HOME et XDG_* sous TMPDIR.")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """HOME et dossiers XDG propres au test : aucune entrée de menu, commande ni registre n'atteint le compte réel."""
    home = tmp_path / "maison"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for name in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_BIN_HOME"):
        monkeypatch.delenv(name, raising=False)
    return home


class PosteSimule:
    """Lectures du poste ; `ldd_calls` consigne les exécutables passés à ldd. `free`, `fstype` et `device` acceptent une
    valeur unique ou un dictionnaire préfixe de chemin → valeur (le plus long préfixe l'emporte, « * » à défaut).
    `processes` simule les processus du compte lancés depuis un programme (/proc/<pid>/exe) ; `installer_refusals`, les refus
    de `<programme>/installer.sh` que status rejoue (U6-04)."""

    def __init__(self, **values):
        self.values = {"machine": "aarch64", "glibc": "2.31", "kernel": "5.10.120-tegra", "memory": 61.0, "free": 10**12,
                       "fstype": "ext4", "noexec": False, "setpriv": "/usr/bin/setpriv", "device": "179:1", "mounts": [],
                       "os_release": {"ID": "ubuntu", "VERSION_ID": "20.04", "PRETTY_NAME": "Ubuntu 20.04.6 LTS"},
                       "ldd": Completed(0, "\tlibjpeg.so.8 => /lib/aarch64-linux-gnu/libjpeg.so.8 (0x0)\n"), **values}
        self.ldd_calls = []
        self.installer_checks: list[Path] = []

    def by_path(self, key, path):
        value = self.values[key]
        if not isinstance(value, dict):
            return value
        text = str(path)
        matches = [prefix for prefix in value if prefix != "*" and (text == prefix or text.startswith(prefix.rstrip("/") + "/"))]
        return value[max(matches, key=len)] if matches else value.get("*")

    def machine(self):
        return self.values["machine"]

    def glibc(self):
        return self.values["glibc"]

    def kernel(self):
        return self.values["kernel"]

    def memory_total_gib(self):
        return self.values["memory"]

    def free_bytes(self, path):
        return self.by_path("free", path)

    def device(self, path):
        return self.by_path("device", path)

    def filesystem(self, path):
        return {"mount": "/media/x", "fstype": self.by_path("fstype", path), "noexec": self.values["noexec"]}

    def mounts(self):
        return self.values["mounts"]

    def writable(self, path):
        allowed = self.values.get("writable")
        return str(path) in allowed if allowed is not None else os.access(path, os.W_OK | os.X_OK)

    def tree_bytes(self, path):
        sizes = self.values.get("tree_bytes")
        if sizes is None:
            return linux_install.SystemProbe().tree_bytes(path)
        return self.by_path("tree_bytes", path) if isinstance(sizes, dict) else sizes

    def os_release(self):
        return self.values["os_release"]

    def setpriv(self):
        return self.values["setpriv"]

    def ldd(self, binary):
        self.ldd_calls.append(binary)
        return self.values.get("ldd_" + Path(binary).name, self.values["ldd"])

    def shared_libraries(self):
        if self.values.get("ldconfig") is False:
            return None
        libraries = self.values.get("libraries")
        return libraries if libraries is not None else Tout()

    def glibcxx_max(self):
        return self.values.get("glibcxx", "3.4.28")

    def l4t_major(self):
        return self.values.get("l4t")

    def port_free(self, port):
        if self.values.get("real_ports"):
            return linux_install.SystemProbe().port_free(port)
        return port not in self.values.get("busy", set())

    def program_processes(self, program):
        """Processus du compte lancés depuis `program` : `processes`, liste ou fonction du programme (aucun par défaut)."""
        found = self.values.get("processes", [])
        return list(found(Path(program)) if callable(found) else found)

    def installer_refusal(self, program):
        """Refus que rendrait `<program>/installer.sh` (contrôles rejoués par status, U6-04) : `installer_refusals`, dictionnaire
        chemin du programme → message ; aucun par défaut. Chaque programme contrôlé est consigné dans `installer_checks`."""
        self.installer_checks.append(Path(program))
        return self.values.get("installer_refusals", {}).get(str(program))


class Tout:
    """Cache du chargeur qui connaît toutes les bibliothèques demandées."""

    def __contains__(self, name):
        return True


class ToutSauf:
    def __init__(self, *absent):
        self.absent = set(absent)

    def __contains__(self, name):
        return name not in self.absent


REAL_PROFILES_SCRIPT = linux_kit.ROOT / "tools/dist/linux_profiles.py"


def free_ports(count: int = 3) -> list[int]:
    """Ports de boucle locale libres à l'instant (aucun service de l'instance principale n'est touché)."""
    sockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(count)]
    try:
        for item in sockets:
            item.bind(("127.0.0.1", 0))
        return [item.getsockname()[1] for item in sockets]
    finally:
        for item in sockets:
            item.close()


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ProgrammeSimule:
    """Commandes du programme installé : rag.sh, bootstrap.sh et compileall simulés ; linux_profiles.py exécuté réellement
    (Python de l'environnement du dépôt, script réel). `init-profile` emploie le vrai `write_user_profile` ; `backup` écrit
    une sauvegarde (manifest.json, profil) dans `runtime.backups_dir` du profil, comme services/runtime/backup.py ;
    `restore` écrit `restored-profile.yaml` comme lui (données à la racine, ports 8795/6343/11445, sans
    `qdrant.storage_dir`). `status` rend l'empreinte du profil de l'instance en marche (`profile_sha256`). Chaque appel
    garde (programme, commande, présence du nouveau dossier) ; `argvs` garde les arguments complets."""

    def __init__(self, *, watch: Path | None = None, results: dict | None = None, locations: dict | None = None,
                 last_started: str | None = None):
        self.calls: list[tuple[str, str, bool]] = []
        self.argvs: list[list[str]] = []
        self.watch = watch
        self.results = results or {}
        self.locations = locations
        self.running: dict[str, str] = {}
        # Programme dont le superviseur a écrit en dernier runtime.json dans les données (status le rend).
        self.last_started = last_started

    def run(self, argv, *, cwd=None, timeout=None):
        program = Path(argv[0]).parent if argv[0].endswith((".sh",)) else Path(cwd)
        name = Path(argv[0]).name
        # linux_profiles.py <commande>, précédé des options de l'interpréteur (-B -I, et -X pycache_prefix=… pour un nouveau kit).
        script = next((index for index, word in enumerate(argv) if word.endswith("linux_profiles.py")), None)
        if name == "rag.sh":
            command = argv[1]
        elif name == "bootstrap.sh":
            command = "bootstrap"
            write(program, ".venv/bin/python", "#!/bin/sh\n", executable=True)
        elif argv[1:3] == ["-m", "compileall"]:
            command = "compileall"
        else:
            assert script is not None, argv  # hors rag.sh, bootstrap.sh et compileall, l'installateur ne lance que linux_profiles.py
            command = argv[script + 1]
        self.calls.append((program.name, command, bool(self.watch and self.watch.exists())))
        self.argvs.append(list(argv))
        scripted = self.results.get((program.name, command), self.results.get(command))
        if callable(scripted):
            scripted = scripted(argv)
        if scripted is not None:
            return Completed(scripted.get("_rc", 0), json.dumps({k: v for k, v in scripted.items() if k != "_rc"}))
        if script is not None:
            if self.locations is not None and command == "paths":
                return Completed(0, json.dumps({"status": "read", "model": "qwen3.5:2b", "source_model": "qwen3.5:2b",
                                                "locations": self.locations}))
            real = subprocess.run([sys.executable, *argv[1:script], str(REAL_PROFILES_SCRIPT), *argv[script + 1:]], cwd=cwd,
                                  capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"}, check=False, timeout=120)
            return Completed(real.returncode, real.stdout, real.stderr)
        return self.default(program, command, argv)

    def default(self, program, command, argv):
        import yaml

        value = lambda option: argv[argv.index(option) + 1]  # noqa: E731
        if command == "init-profile":
            from services.runtime.profile_setup import write_user_profile

            # Comme rag.sh : --model choisit le profil livré, et sans option le profil du 4B (W045).
            base = program / ("config/local16.yaml" if "--model" in argv and value("--model") == "qwen3.5:2b" else "config/local16-4b.yaml")
            ports = [int(item) for item in value("--ports").split(",")] if "--ports" in argv else free_ports()
            storage = Path(value("--qdrant-storage")) if "--qdrant-storage" in argv else None
            result = write_user_profile(base, Path(value("--target")), qdrant_storage=storage, program_root=program,
                                        ports=dict(zip(("app", "qdrant", "ollama"), ports, strict=True)))
        elif command == "doctor":
            result = GREEN
        elif command == "up":
            profile = value("--profile")
            active_program, active = next(iter(self.running.items()), (None, None))
            if active and active != profile:
                return Completed(1, json.dumps({"status": "failed", "message": "Instance existante avec profil différent : down puis up "
                                                                               "pour appliquer la configuration"}))
            if active_program:
                # Même profil : l'instance en marche est rendue telle quelle, quel que soit le programme qui l'a lancée.
                return Completed(0, json.dumps({"status": "running", "instance_id": "inst-en-place", "supervisor": {
                    "executable": f"{active_program}/.runtime/python/{PYTHON_KEY}/bin/python3.12"}}))
            self.running[str(program)] = profile
            self.last_started = str(program)
            result = {"status": "running", "instance_id": "inst-1",
                      "supervisor": {"executable": f"{program}/.runtime/python/{PYTHON_KEY}/bin/python3.12"}}
        elif command == "down":
            self.running.pop(str(program), None)
            result = {"status": "stopped"}
        elif command == "status":
            active_program = next(iter(self.running), None)
            active_profile = self.running.get(active_program) if active_program else None
            result = {"status": "running" if active_program else "stopped",
                      "profile_matches_current": active_profile == value("--profile")}
            if active_profile:
                result["profile_sha256"] = sha256(active_profile)
            if self.last_started:
                result["supervisor"] = {"executable": f"{self.last_started}/.runtime/python/{PYTHON_KEY}/bin/python3.12"}
        elif command == "selftest":
            result = {"level": "vert", "summary": "contrôle réel réussi", "steps": []}
        elif command == "open":
            result = {"url": "http://127.0.0.1:8785/ouvrir#jeton"} if "--no-browser" in argv else {"opened_in_browser": True}
        elif command == "backup":
            profile = Path(value("--profile"))
            data = yaml.safe_load(profile.read_text(encoding="utf-8"))
            backup = Path(data["runtime"]["backups_dir"]) / f"20261006T2000{len(self.calls):02d}Z-b{len(self.calls)}"
            write(backup / "config", "profile.yaml", profile.read_text(encoding="utf-8"))
            write(backup, "manifest.json", json.dumps({"format": "rag-native-backup-v1", "created_at_utc": "2026-10-06T20:00:00+00:00",
                                                       "state": "verified"}))
            result = {"path": str(backup)}
        elif command == "verify":
            result = {"state": "verified"}
        elif command == "restore":
            target = Path(value("--target"))
            profile = yaml.safe_load((Path(value("--path")) / "config/profile.yaml").read_text(encoding="utf-8"))
            profile["qdrant"].pop("storage_dir", None)
            profile["app"]["data_dir"] = str(target)
            profile["sqlite"]["path"] = str(target / "app.sqlite3")
            profile["app"]["port"], profile["qdrant"]["url"] = 8795, "http://127.0.0.1:6343"
            profile["llm"]["base_url"] = "http://127.0.0.1:11445"
            profile["runtime"]["backups_dir"] = str(target / "backups")
            write(target, "restored-profile.yaml", yaml.safe_dump(profile, sort_keys=False))
            result = {"state": "restored_storage_verified"}
        elif command == "logs":
            result = {"qdrant": "/donnees/data/logs/i1/qdrant.log", "ollama": "/donnees/data/logs/i1/ollama.log",
                      "api": "/donnees/data/logs/i1/api.log"}
        else:
            result = {}
        return Completed(0, json.dumps(result))

    def commands(self, program=None):
        return [command for name, command, _ in self.calls if program is None or name == program]

    def profiles_of(self, command):
        return [argv[argv.index("--profile") + 1] for argv in self.argvs if argv[1:2] == [command] and "--profile" in argv]


class Horloge:
    def __init__(self):
        import datetime as dt

        self.moment = dt.datetime(2026, 10, 6, 20, 0, tzinfo=dt.UTC)

    def __call__(self):
        import datetime as dt

        self.moment += dt.timedelta(seconds=1)
        return self.moment


class Chrono:
    """Horloge monotone simulée : chaque lecture avance d'une demi-seconde."""

    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.5
        return self.value


def make_kit(tmp_path: Path, monkeypatch, *, name="kit", repository=None, **options) -> Path:
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", no_l4t_release)
    monkeypatch.setattr(linux_kit, "host_library_path", no_host_library)
    monkeypatch.setattr(linux_kit, "package_owner", no_package_owner)
    repository = repository or make_repository(tmp_path)
    kit = tmp_path / name
    linux_kit.build_linux_kit(kit, repository, platform="linux-aarch64", home=str(tmp_path / "fabrication"), **options)
    return kit


def context(kit: Path, runner=None, probe=None, *, tty=False, answers=None) -> linux_install.Context:
    """Contexte d'essai : sorties captées ; hors terminal par défaut ; `answers` simule les réponses tapées (une exception
    dans la liste est levée à sa place, comme une fin de fichier ou un Ctrl+C)."""
    refuse_the_real_account()
    replies = list(answers or [])

    def ask():
        if not replies:
            raise AssertionError("question inattendue")
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    ctx = linux_install.Context(kit=kit, runner=runner or ProgrammeSimule(), probe=probe or PosteSimule(), out=io.StringIO(),
                                err=io.StringIO(), clock=Horloge(), monotonic=Chrono(), stdin_tty=tty, stdout_tty=tty, ask=ask)
    ctx.replies = replies
    return ctx


def screen(ctx) -> str:
    return ctx.out.getvalue() + ctx.err.getvalue()


def install(ctx, destination, data_root, *extra):
    return linux_install.main(["install", "--destination", str(destination), "--data-root", str(data_root), "--oui", *extra], ctx)


def manifest_of(kit: Path) -> dict:
    return json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))


def with_manifest(kit: Path, **fields) -> dict:
    """Champs du manifeste remplacés (le manifeste n'est pas dans SHA256SUMS) ; `target` est fusionné."""
    manifest = manifest_of(kit)
    for key, value in fields.items():
        if key == "target":
            manifest["target"].update(value)
        else:
            manifest[key] = value
    (kit / "kit-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def inventory(folder: Path) -> dict[str, str]:
    """Contenu d'un dossier : chemin relatif → empreinte (fichiers) ou cible (liens)."""
    if not folder.exists():
        return {}
    found = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder).as_posix()
        if path.is_symlink():
            found[relative] = "-> " + os.readlink(path)
        elif path.is_file():
            found[relative] = sha256(path)
    return found


def pointer_of(destination: Path) -> dict:
    return json.loads((destination / "installation.json").read_text(encoding="utf-8"))


@pytest.fixture
def kit(tmp_path, monkeypatch):
    return make_kit(tmp_path, monkeypatch)


# --- Précontrôles ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("values", "message"), [
    ({"machine": "x86_64"}, "ce kit vise aarch64, ce poste est en x86_64"),
    ({"glibc": "2.28"}, "glibc 2.28 trop ancienne : 2.29 ou plus récente exigée"),
    ({"glibc": None}, "glibc introuvable"),
    ({"kernel": "4.9.253-tegra"}, "noyau 4.9.253-tegra"),
    ({"memory": 7.6}, "ce poste a 7,6 Gio"),
    ({"setpriv": None}, "setpriv (util-linux) absent"),
    ({"free": 2 * 1024**3}, "espace insuffisant"),
    ({"fstype": "vfat"}, "destination sur vfat"),
    ({"noexec": True}, "monté noexec"),
], ids=["arch", "glibc", "musl", "noyau", "memoire", "setpriv", "espace", "vfat", "noexec"])
def test_prechecks_refuse_before_any_write(kit, tmp_path, values, message):
    ctx = context(kit, probe=PosteSimule(**values))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "Précontrôles refusés, rien n'a été écrit" in errors and message in errors and "Arrêt" not in ctx.out.getvalue()
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


@pytest.mark.parametrize(("values", "message"), [
    ({"ldd": Completed(0, "\tlibjpeg.so.8 => not found\n")}, "libjpeg.so.8 — OCR Tesseract"),
    ({"ldd": Completed(1, "", "version `GLIBCXX_3.4.26' not found (required by tesseract)")}, "GLIBCXX_3.4.26"),
], ids=["ldd-absente", "ldd-glibcxx"])
def test_system_checks_after_verification_refuse_before_any_write(kit, tmp_path, values, message):
    ctx = context(kit, probe=PosteSimule(**values))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    errors = ctx.err.getvalue()
    assert "Contrôles du système refusés, rien n'a été écrit" in errors and message in errors
    assert "[ok] Intégrité du kit" in ctx.out.getvalue()
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


def test_opencv_without_libgl_on_the_host_is_refused_before_any_write(kit, tmp_path):
    ctx = context(kit, probe=PosteSimule(**{"ldd_cv2.abi3.so": Completed(0, "\tlibGL.so.1 => not found\n")}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    assert "libGL.so.1 — OpenCV (OCR et tableaux)" in ctx.err.getvalue()
    assert [path.name for path in ctx.probe.ldd_calls] == ["tesseract", "cv2.abi3.so"]
    assert not (tmp_path / "programmes").exists()


def test_ldd_never_runs_on_an_altered_tesseract(kit, tmp_path):
    (kit / linux_kit.TESSERACT_BINARY).write_bytes(b"\x7fELF autre")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "Kit non conforme" in ctx.err.getvalue() and ctx.probe.ldd_calls == []


@pytest.mark.parametrize(("destination", "data_root", "message"), [
    ("programmes", "programmes/donnees", "imbriquées"),
    ("donnees/programmes", "donnees", "imbriquées"),
    ("kit/programmes", "donnees", "dans le kit"),
])
def test_destination_and_data_root_must_be_distinct_and_outside_the_kit(kit, tmp_path, destination, data_root, message):
    ctx = context(kit)
    assert install(ctx, tmp_path / destination, tmp_path / data_root) == linux_install.EXIT_REFUSED
    assert message in ctx.err.getvalue() and ctx.runner.calls == []


def test_an_existing_profile_or_installation_is_never_replaced(kit, tmp_path):
    write(tmp_path, "donnees/profile.yaml", "schema_version: 2\n")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    # U2-02 : le refus nomme les données conservées et dit qu'elles ne sont jamais remplacées.
    assert (f"Données conservées dans {tmp_path / 'donnees'} (profile.yaml)" in ctx.err.getvalue()
            and "elles ne sont jamais remplacées" in ctx.err.getvalue() and not (tmp_path / "programmes").exists())
    write(tmp_path, "programmes/installation.json", json.dumps({"format": linux_install.POINTER_FORMAT, "current": {"kit_id": "x"}}))
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "autres") == linux_install.EXIT_REFUSED
    # REL-U12 : commande complète et absolue, exécutable telle quelle.
    assert f"« {kit}/installer.sh update --destination {tmp_path / 'programmes'} »" in ctx.err.getvalue()


# --- Installation ---------------------------------------------------------------------------------------------------------

def test_install_runs_the_whole_sequence_and_switches_atomically(kit, tmp_path):
    seen = {}

    def init_profile(argv):
        seen["argv"] = argv  # puis création réelle par write_user_profile (double par défaut)

    ctx = context(kit, runner=ProgrammeSimule(results={"init-profile": init_profile}))
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(ctx, destination, data_root) == 0, screen(ctx)
    manifest = manifest_of(kit)
    program = destination / manifest["kit_id"]
    assert ctx.runner.commands() == ["bootstrap", "compileall", "init-profile", "derive", "doctor", "up", "doctor", "selftest", "open"]
    # Copie réelle : liens recréés, bit x, préfixe de CPython réécrit vers le programme installé.
    assert os.readlink(program / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0") == "libggml.so.0.24.0"
    assert os.access(program / linux_kit.TESSERACT_BINARY, os.X_OK)
    prefix = str((program / f".runtime/python/{PYTHON_KEY}").resolve())
    assert (program / SYSCONFIG).read_text(encoding="utf-8") == f"build_time_vars = {{'prefix': '{prefix}', 'LIBDIR': '{prefix}/lib', 'CC': 'cc'}}\n"
    pointer = pointer_of(destination)
    current = pointer["current"]
    assert current["kit_id"] == manifest["kit_id"] and current["program"] == str(program) and pointer["previous"] is None
    # W045 : profil principal du 4B, modèle par défaut du kit, demandé explicitement à init-profile ; 2B dérivé.
    assert seen["argv"][1:] == ["init-profile", "--target", str(data_root), "--model", "qwen3.5:4b"]
    assert current["model"] == "qwen3.5:4b" == manifest["default_model"]
    assert current["profiles"] == {"qwen3.5:4b": str(data_root / "profile.yaml"), "qwen3.5:2b": str(data_root / "profile-qwen3.5-2b.yaml")}
    import yaml

    principal = yaml.safe_load((data_root / "profile.yaml").read_text(encoding="utf-8"))
    derived = yaml.safe_load((data_root / "profile-qwen3.5-2b.yaml").read_text(encoding="utf-8"))
    assert principal["llm"]["model"] == "qwen3.5:4b-text" and principal["llm"]["source_model"] == "qwen3.5:4b"
    assert derived["llm"]["model"] == "qwen3.5:2b" and derived["llm"]["tokenizer_model_id"] == "Qwen/Qwen3.5-2B"
    assert derived["resources"]["initial_llm_load_peak_estimate_mib"] == 3968
    assert principal["resources"]["initial_llm_load_peak_estimate_mib"] == 4352
    # W046 : l'estimation chaude diffère aussi entre les profils livrés ; la dérivation la reprend du profil 2B.
    assert derived["resources"]["warm_llm_additional_peak_estimate_mib"] == 512
    assert principal["resources"]["warm_llm_additional_peak_estimate_mib"] == 640
    assert {key: derived[key] for key in ("app", "qdrant", "sqlite", "runtime")} == {key: principal[key] for key in ("app", "qdrant", "sqlite", "runtime")}
    assert current["started_on_data"] is True and [event["event"] for event in pointer["history"]] == ["install"]
    launcher = (destination / "atelier").read_text(encoding="utf-8")
    assert f"version {manifest['kit_id']}." in launcher and os.access(destination / "atelier", os.X_OK)
    assert f"--kit {program} run --destination {destination}" in launcher and "unset LD_LIBRARY_PATH" in launcher
    assert [path.name for path in destination.iterdir() if path.name.startswith(".")] == [linux_install.LOCK]
    reports = list(data_root.glob("install-*.json"))
    assert len(reports) == 1 and json.loads(reports[0].read_text(encoding="utf-8"))["status"] == "installed"
    assert "jeton" not in reports[0].read_text(encoding="utf-8")


def test_install_with_another_default_model_and_options_passes_them_to_init_profile(kit, tmp_path):
    seen = {}

    def init_profile(argv):
        seen["argv"] = argv  # puis création réelle par write_user_profile (double par défaut)

    ports = ",".join(map(str, free_ports()))
    ctx = context(kit, runner=ProgrammeSimule(results={"init-profile": init_profile}))
    assert install(ctx, tmp_path / "p", tmp_path / "donnees", "--model", "qwen3.5:2b", "--ports", ports,
                   "--qdrant-storage", str(tmp_path / "q"), "--no-start") == 0, screen(ctx)
    assert seen["argv"][1:] == ["init-profile", "--target", str(tmp_path / "donnees"), "--model", "qwen3.5:2b",
                                "--qdrant-storage", str(tmp_path / "q"), "--ports", ports]
    assert ctx.runner.commands() == ["bootstrap", "compileall", "init-profile", "derive", "doctor"]
    pointer = pointer_of(tmp_path / "p")
    assert pointer["current"]["model"] == "qwen3.5:2b" and pointer["current"]["started_on_data"] is False
    assert pointer["current"]["profiles"]["qwen3.5:4b"] == str(tmp_path / "donnees/profile-qwen3.5-4b.yaml")


def test_a_red_doctor_stops_before_the_switch_and_removes_what_this_run_created(kit, tmp_path):
    red = {"verdict": {"level": "rouge", "summary": "Bloqué", "rubrics": [
        {"level": "rouge", "rubric": "programme", "message": "Fichiers du programme absents ou incomplets : .runtime/bin.",
         "action": "Réinstaller depuis le kit."}]}}
    ctx = context(kit, runner=ProgrammeSimule(results={"doctor": red}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_PARTIAL
    assert "Vérification refusée : Fichiers du programme absents ou incomplets : .runtime/bin. Réinstaller depuis le kit." in ctx.err.getvalue()
    assert [path.name for path in (tmp_path / "programmes").iterdir() if path.name != linux_install.LOCK] == []
    assert not (tmp_path / "donnees/profile.yaml").exists() and not (tmp_path / "donnees/profile-qwen3.5-2b.yaml").exists()
    path = next((tmp_path / "donnees").glob("install-*.json"))
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["new_program_removed"]
    # REL-U02 : le message dit ce qui a été retiré, que rien n'est désigné et où lire le rapport (EXIT_CODES[5]).
    assert (f"État laissé : programme copié et profils créés retirés, rien n'a été désigné ; rapport : {path} ; relancer la même "
            "commande après correction.") in ctx.err.getvalue()


def test_a_failed_derived_profile_removes_the_profile_init_profile_created(kit, tmp_path):
    ctx = context(kit, runner=ProgrammeSimule(results={"derive": {"_rc": 1, "status": "failed", "message": "port occupé"}}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_PARTIAL
    assert "Profil qwen3.5:2b non dérivable : port occupé" in ctx.err.getvalue()
    assert not (tmp_path / "donnees/profile.yaml").exists() and [p.name for p in (tmp_path / "programmes").iterdir() if p.name != linux_install.LOCK] == []
    path = next((tmp_path / "donnees").glob("install-*.json"))
    assert (f"État laissé : programme copié et profils créés retirés, rien n'a été désigné ; rapport : {path} ; relancer la même "
            "commande après correction.") in ctx.err.getvalue()
    assert install(context(kit), tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0


def test_a_profile_not_created_says_the_copied_program_was_removed(kit, tmp_path):
    failed = {"_rc": 1, "status": "failed", "message": "Port déjà occupé sur ce poste : 8785"}
    ctx = context(kit, runner=ProgrammeSimule(results={"init-profile": failed}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_PARTIAL
    path = next((tmp_path / "donnees").glob("install-*.json"))
    errors = ctx.err.getvalue()
    assert "Arrêt : Profil non créé : Port déjà occupé sur ce poste : 8785" in errors and errors.count("Arrêt : ") == 1
    assert (f"État laissé : programme copié retiré, rien n'a été désigné ; rapport : {path} ; relancer la même commande après "
            "correction.") in errors
    assert not (tmp_path / "programmes" / manifest_of(kit)["kit_id"]).exists()


# --- KIT4-02 : terminal, récapitulatif confirmé, stderr, codes, Ctrl+C, root ----------------------------------------------

def test_without_terminal_and_without_oui_nothing_is_written(kit, tmp_path):
    ctx = context(kit)
    code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees")], ctx)
    assert code == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "Récapitulatif" in errors and f"Version : {manifest_of(kit)['kit_id']}" in errors
    assert re.search(r"installer\.sh install --destination \S+ --data-root \S+ --oui", errors), errors
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


def test_interactive_answer_no_writes_nothing(kit, tmp_path):
    ctx = context(kit, tty=True, answers=["n"])
    code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees")], ctx)
    assert code == linux_install.EXIT_REFUSED and "Continuer ? [o/N]" in ctx.out.getvalue() and ctx.replies == []
    assert "rien n'a été écrit" in ctx.err.getvalue()
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


def test_interactive_answer_yes_installs(kit, tmp_path):
    ctx = context(kit, tty=True, answers=["o"])
    code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees"),
                               "--no-start"], ctx)
    assert code == 0, screen(ctx)
    assert pointer_of(tmp_path / "programmes")["current"]["kit_id"] == manifest_of(kit)["kit_id"]


def test_oui_asks_no_question(kit, tmp_path):
    ctx = context(kit, tty=True)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    assert "Continuer ?" not in ctx.out.getvalue() and "Récapitulatif" in ctx.out.getvalue()


def test_refusals_go_to_stderr_with_documented_codes(kit, tmp_path):
    assert (linux_install.EXIT_REFUSED, linux_install.EXIT_SYSTEM, linux_install.EXIT_PARTIAL, linux_install.EXIT_INTERRUPTED) == (3, 4, 5, 130)
    refused = context(kit, probe=PosteSimule(machine="x86_64"))
    assert install(refused, tmp_path / "a", tmp_path / "da") == 3
    system = context(kit, probe=PosteSimule(libraries=ToutSauf("libGL.so.1")))
    assert install(system, tmp_path / "b", tmp_path / "db") == 4
    red = {"verdict": {"level": "rouge", "summary": "Bloqué", "rubrics": [{"level": "rouge", "rubric": "modèle", "message": "Modèle absent."}]}}
    late = context(kit, runner=ProgrammeSimule(results={"doctor": red}))
    assert install(late, tmp_path / "c", tmp_path / "dc") == 5
    for ctx in (refused, system, late):
        assert ctx.err.getvalue().count("Arrêt : ") == 1 and "Arrêt" not in ctx.out.getvalue()
    assert linux_install.EXIT_CODES[130] == "interruption" and set(linux_install.EXIT_CODES) == {0, 1, 2, 3, 4, 5, 130}


def test_keyboard_interrupt_during_copy(kit, tmp_path, monkeypatch):
    data_root = write(tmp_path, "donnees/notes/a.txt", "document de l'utilisateur").parents[1]
    before = inventory(data_root)
    from tools.dist import build_kit

    real_stream_copy = build_kit.stream_copy
    copied = []

    def interrupted_stream_copy(source, target):
        """Copie réelle d'un fichier ; Ctrl+C au cinquième, quand une partie du programme est déjà écrite."""
        if len(copied) == 4:
            raise KeyboardInterrupt
        copied.append(target)
        return real_stream_copy(source, target)

    monkeypatch.setattr(build_kit, "stream_copy", interrupted_stream_copy)
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", data_root) == linux_install.EXIT_INTERRUPTED
    assert len(copied) == 4 and "Traceback" not in screen(ctx)
    assert "Installation interrompue : copie partielle retirée, données inchangées ; relancer la même commande." in ctx.err.getvalue()
    assert not (tmp_path / "programmes" / manifest_of(kit)["kit_id"]).exists() and not (tmp_path / "programmes/installation.json").exists()
    assert inventory(data_root) == before


def test_an_interruption_at_the_confirmation_writes_nothing(kit, tmp_path):
    ctx = context(kit, tty=True, answers=[KeyboardInterrupt()])
    code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees")], ctx)
    assert code == 130 and "rien n'a été écrit" in ctx.err.getvalue() and not (tmp_path / "programmes").exists()


def euid_root() -> int:
    """Double de os.geteuid : compte root (sudo)."""
    return 0


@pytest.mark.parametrize("argv", [["install", "--oui"], ["status"], ["run", "--destination", "/p"]], ids=["install", "status", "run"])
def test_root_is_refused_before_any_write(kit, tmp_path, monkeypatch, argv):
    monkeypatch.setattr(os, "geteuid", euid_root)
    ctx = context(kit)
    assert linux_install.main(argv, ctx) == linux_install.EXIT_REFUSED
    assert "Ne pas lancer l'installateur ni le lanceur avec sudo ni en root" in ctx.err.getvalue()
    assert ctx.runner.calls == [] and not (tmp_path / "maison/.local").exists()


# --- KIT4-03 : emplacements par défaut ------------------------------------------------------------------------------------

def default_paths(home: Path) -> tuple[Path, Path]:
    base = home / ".local/share/atelier-documentaire"
    return base / "programme", base / "donnees"


def test_install_without_arguments_uses_the_xdg_data_home_default(kit, isolated_home):
    ctx = context(kit)
    assert linux_install.main(["--oui", "--no-start"], ctx) == 0, screen(ctx)
    destination, data_root = default_paths(isolated_home)
    assert (destination / manifest_of(kit)["kit_id"] / "kit-manifest.json").is_file()
    assert (data_root / "profile.yaml").is_file()
    assert pointer_of(destination)["current"]["data_root"] == str(data_root)
    # Dossiers créés pour l'utilisateur seul (XDG Base Directory 0.8 : 0700).
    assert (isolated_home / ".local/share/atelier-documentaire").stat().st_mode & 0o777 == 0o700


def test_a_relative_xdg_data_home_is_ignored(kit, tmp_path, isolated_home, monkeypatch):
    # QA-07 : dossier courant isolé, pour qu'une régression n'écrive jamais dans le dépôt.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_DATA_HOME", "relatif/donnees")
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    assert (default_paths(isolated_home)[0] / "installation.json").is_file()
    assert not (tmp_path / "relatif").exists()


def test_an_absolute_xdg_data_home_is_used(kit, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    assert (tmp_path / "xdg/atelier-documentaire/programme/installation.json").is_file()
    assert (tmp_path / "xdg/atelier-documentaire/donnees/profile.yaml").is_file()


def test_emplacement_sets_both_folders(kit, tmp_path):
    ctx = context(kit)
    assert linux_install.main(["--emplacement", str(tmp_path / "volume/atelier"), "--oui", "--no-start"], ctx) == 0, screen(ctx)
    assert (tmp_path / "volume/atelier/programme/installation.json").is_file()
    assert (tmp_path / "volume/atelier/donnees/profile.yaml").is_file()


def test_no_subcommand_parses_as_install():
    args = linux_install.parser().parse_args([])
    assert args.command == "install" and args.implicit is True
    args = linux_install.parser().parse_args(["--oui", "--emplacement", "/media/volume/atelier"])
    assert args.command == "install" and args.oui is True and args.emplacement == Path("/media/volume/atelier")
    explicit = linux_install.parser().parse_args(["install", "--oui"])
    assert explicit.command == "install" and explicit.implicit is False


def test_the_installer_of_an_installed_program_shows_status_without_arguments(kit, tmp_path):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    program = Path(pointer_of(destination)["current"]["program"])
    before = (inventory(destination), inventory(data_root))
    ctx = context(program)
    assert linux_install.main([], ctx) == 0, screen(ctx)
    assert f"Version courante : {manifest_of(kit)['kit_id']}" in ctx.out.getvalue()
    assert (inventory(destination), inventory(data_root)) == before


def test_a_missing_home_is_refused_with_the_emplacement_hint(kit, monkeypatch):
    monkeypatch.delenv("HOME")
    ctx = context(kit)
    assert linux_install.main(["--oui"], ctx) == linux_install.EXIT_REFUSED
    assert "HOME absent ou relatif" in ctx.err.getvalue() and "--emplacement" in ctx.err.getvalue()


# --- KIT4-04 : place, volumes proposés, racine des données ---------------------------------------------------------------

def mount(point, fstype="ext4", *, noexec=False, readonly=False, root="/", device=None):
    return {"mount": point, "root": root, "fstype": fstype, "noexec": noexec, "readonly": readonly, "device": device or f"dev:{point}"}


def test_insufficient_space_proposes_a_local_volume_with_the_exact_command(kit, isolated_home):
    probe = PosteSimule(free={str(isolated_home): 5 * GIB, "/media/safae/devsave1": 116 * GIB, "*": 5 * GIB},
                        mounts=[mount("/"), mount("/media/safae/devsave1")], writable={"/media/safae/devsave1"})
    ctx = context(kit, probe=probe)
    assert linux_install.main(["--oui"], ctx) == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "/media/safae/devsave1 — 116,0 Gio libres" in errors and "volume monté par la session" in errors
    assert re.search(r"installer\.sh --oui --emplacement /media/safae/devsave1/atelier-documentaire", errors), errors
    assert not (isolated_home / ".local/share/atelier-documentaire").exists() and ctx.runner.calls == []


def test_network_tmpfs_or_noexec_mounts_are_never_proposed(kit, isolated_home):
    mounts = [mount("/srv/nfs", "nfs4"), mount("/run/user/1000", "tmpfs"), mount("/mnt/noexec", noexec=True),
              mount("/mnt/lecture", readonly=True), mount("/mnt/lie", root="/sous-dossier"), mount("/mnt/sain", "xfs")]
    probe = PosteSimule(free={str(isolated_home): GIB, "*": 500 * GIB}, mounts=mounts,
                        writable={item["mount"] for item in mounts})
    ctx = context(kit, probe=probe)
    assert linux_install.main(["--oui"], ctx) == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "/mnt/sain — 500,0 Gio libres" in errors
    for refused in ("/srv/nfs", "/run/user/1000", "/mnt/noexec", "/mnt/lecture", "/mnt/lie"):
        assert refused not in errors


def test_the_interactive_choice_installs_on_the_proposed_volume(kit, tmp_path, isolated_home):
    volume = tmp_path / "disque"
    volume.mkdir()
    probe = PosteSimule(free={str(isolated_home): GIB, str(volume): 500 * GIB, "*": GIB}, mounts=[mount(str(volume))],
                        writable={str(volume)})
    ctx = context(kit, probe=probe, tty=True, answers=["1", "o"])
    assert linux_install.main(["--no-start"], ctx) == 0, screen(ctx)
    assert (volume / "atelier-documentaire/programme/installation.json").is_file()
    assert (volume / "atelier-documentaire/donnees/profile.yaml").is_file()


def test_a_data_root_on_a_network_filesystem_is_refused_before_any_write(kit, tmp_path):
    probe = PosteSimule(fstype={str(tmp_path / "donnees"): "nfs4", "*": "ext4"}, device={str(tmp_path / "donnees"): "0:52", "*": "179:1"})
    ctx = context(kit, probe=probe)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "racine des données sur nfs4" in ctx.err.getvalue()
    assert not (tmp_path / "programmes").exists() and ctx.runner.calls == []


def test_a_data_root_below_the_threshold_is_refused_with_the_action(kit, tmp_path):
    probe = PosteSimule(free={str(tmp_path / "donnees"): GIB, "*": 500 * GIB}, device={str(tmp_path / "donnees"): "8:1", "*": "179:1"})
    ctx = context(kit, probe=probe)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "racine des données" in errors and "1,0 Gio libres, 2,0 Gio au moins" in errors and "--data-root" in errors


def test_needs_are_summed_on_a_shared_volume(kit, tmp_path):
    needed = manifest_of(kit)["requirements"]["install_bytes_min"]
    short = context(kit, probe=PosteSimule(free=needed + GIB))
    assert install(short, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "espace insuffisant" in short.err.getvalue() and "réserve de 2,0 Gio des données" in short.err.getvalue()
    enough = context(kit, probe=PosteSimule(free=needed + 3 * GIB))
    assert install(enough, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(enough)


# --- KIT4-05 : ports par défaut contrôlés avant toute écriture -----------------------------------------------------------

def kit_with_ports(kit: Path) -> list[int]:
    ports = free_ports()
    triplet = dict(zip(("app", "qdrant", "ollama"), ports, strict=True))
    with_manifest(kit, profile_ports={"qwen3.5:4b": triplet, "qwen3.5:2b": triplet})
    return ports


def test_busy_default_ports_are_refused_before_any_write_with_a_free_triplet(kit, tmp_path):
    ports = kit_with_ports(kit)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", ports[0]))
        busy.listen()
        ctx = context(kit, probe=PosteSimule(real_ports=True))
        code = linux_install.main(["install", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees")], ctx)
        errors = ctx.err.getvalue()
        assert code == linux_install.EXIT_REFUSED and f"port {ports[0]} occupé" in errors
        chosen = [int(value) for value in re.search(r"--ports (\d+),(\d+),(\d+)", errors).groups()]
        assert len(set(chosen)) == 3 and ports[0] not in chosen and all(linux_install.SystemProbe().port_free(port) for port in chosen)
    assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists()


def test_with_oui_the_free_triplet_is_passed_to_init_profile(kit, tmp_path):
    ports = kit_with_ports(kit)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", ports[0]))
        busy.listen()
        ctx = context(kit, probe=PosteSimule(real_ports=True))
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    argv = next(argv for argv in ctx.runner.argvs if argv[1:2] == ["init-profile"])
    chosen = [int(value) for value in argv[argv.index("--ports") + 1].split(",")]
    assert chosen[0] != ports[0] and chosen[1:] == ports[1:] and f"port {ports[0]} occupé" in ctx.out.getvalue()


def port_libre_hors(busy: set[int]):
    """Double du sondage d'un port : libre sauf s'il figure dans `busy`."""
    def is_free(port: int) -> bool:
        return port not in busy
    return is_free


def test_the_free_triplet_rule_skips_the_restore_ports():
    busy = {8794, 6342, 6344}
    chosen = linux_install.free_triplet({"app": 8794, "qdrant": 6342, "ollama": 11434}, port_libre_hors(busy))
    # 8795 et 6343 sont réservés à la restauration : 8794 → 8796 ; 6342 → 6344 occupé → 6345.
    assert chosen == {"app": 8796, "qdrant": 6345, "ollama": 11434}


def test_an_old_manifest_without_ports_keeps_the_previous_behaviour(kit, tmp_path):
    # Manifeste d'un fabricant antérieur à KIT4-05 : sans `profile_ports` (le fabricant courant l'écrit).
    manifest = manifest_of(kit)
    manifest.pop("profile_ports", None)
    (kit / "kit-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ctx = context(kit, probe=PosteSimule(busy={8785}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    argv = next(argv for argv in ctx.runner.argvs if argv[1:2] == ["init-profile"])
    assert "--ports" not in argv


# --- KIT4-06 : contrôles système avant la lecture complète, bibliothèques nommées ----------------------------------------

def test_missing_libgl_is_refused_before_reading_the_whole_kit(kit, tmp_path, monkeypatch):
    hashed = []
    real_hash = linux_kit.stream_hash

    def counted_hash(path):
        hashed.append(Path(path).relative_to(kit).as_posix())
        return real_hash(path)

    monkeypatch.setattr(linux_kit, "stream_hash", counted_hash)
    ctx = context(kit, probe=PosteSimule(libraries=ToutSauf("libGL.so.1")))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    allowed = {"SHA256SUMS", "SYMLINKS", "EXECUTABLES", *manifest_of(kit)["target"]["ldd_checks"]}
    assert hashed and set(hashed) <= allowed and len(hashed) < len(linux_kit.read_sums(kit)) / 2
    assert not (tmp_path / "programmes").exists() and ctx.runner.calls == []


def test_ldd_never_runs_on_an_altered_ldd_target(kit, tmp_path):
    target = next(item for item in manifest_of(kit)["target"]["ldd_checks"] if item.endswith("cv2.abi3.so"))
    (kit / target).write_bytes((kit / target).read_bytes() + b"\x00")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "Kit non conforme" in ctx.err.getvalue() and target in ctx.err.getvalue() and ctx.probe.ldd_calls == []


def test_the_refusal_names_component_and_build_host_package_when_the_os_matches(kit, tmp_path):
    with_manifest(kit, target={"system_packages": {"libGL.so.1": {"package": "libgl1", "component": "OpenCV (OCR et tableaux)",
                                                                  "observed_on": "Ubuntu 20.04.6 LTS aarch64"}}},
                  build_host={**manifest_of(kit)["build_host"], "os_release": {"ID": "ubuntu", "VERSION_ID": "20.04",
                                                                               "PRETTY_NAME": "Ubuntu 20.04.6 LTS"}})
    ctx = context(kit, probe=PosteSimule(libraries=ToutSauf("libGL.so.1")))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    errors = ctx.err.getvalue()
    assert "  - libGL.so.1 — OpenCV (OCR et tableaux) — paquet du système de fabrication (Ubuntu 20.04.6 LTS aarch64) : libgl1" in errors
    assert "À faire installer par l'administrateur du poste ; l'installateur n'installe aucun paquet." in errors


def test_another_os_gets_sonames_only(kit, tmp_path):
    with_manifest(kit, target={"system_packages": {"libGL.so.1": {"package": "libgl1", "component": "OpenCV (OCR et tableaux)",
                                                                  "observed_on": "Ubuntu 20.04.6 LTS aarch64"}}},
                  build_host={**manifest_of(kit)["build_host"], "os_release": {"ID": "ubuntu", "VERSION_ID": "20.04"}})
    probe = PosteSimule(libraries=ToutSauf("libGL.so.1"), os_release={"ID": "debian", "VERSION_ID": "12", "PRETTY_NAME": "Debian GNU/Linux 12"})
    ctx = context(kit, probe=probe)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    errors = ctx.err.getvalue()
    assert "libGL.so.1 — OpenCV (OCR et tableaux) — paquet à identifier pour ce système" in errors and "libgl1" not in errors


def test_missing_ldconfig_has_its_own_message(kit, tmp_path):
    ctx = context(kit, probe=PosteSimule(ldconfig=False))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_SYSTEM
    assert "ldconfig introuvable" in ctx.err.getvalue() and "libGL.so.1 —" not in ctx.err.getvalue()


@pytest.mark.parametrize(("values", "code"), [({}, 0), ({"libraries": ToutSauf("libGL.so.1")}, 4), ({"machine": "x86_64"}, 3)],
                         ids=["pret", "bibliotheque", "architecture"])
def test_verifier_writes_nothing_and_returns_the_same_verdict(kit, tmp_path, isolated_home, values, code):
    ctx = context(kit, probe=PosteSimule(**values))
    assert linux_install.main(["verifier"], ctx) == code, screen(ctx)
    assert list(isolated_home.iterdir()) == [] and ctx.runner.calls == []
    if code == 0:
        assert "rien n'a été écrit" in ctx.out.getvalue()


# --- KIT4-07 : étapes, progression, durées ---------------------------------------------------------------------------------

class CopieAvecProgression:
    """Double de linux_kit.install_copy : copie réelle, puis rappel de progression pour chaque fichier de SHA256SUMS, dans
    l'ordre, avec le total du manifeste (forme du paramètre `progress` attendu du fabricant)."""

    def __init__(self, real):
        self.real = real
        self.calls = []

    def __call__(self, folder, target, progress=None):
        result = self.real(folder, target)
        total = manifest_of(folder)["bytes"]
        done = 0
        for relative in linux_kit.read_sums(folder):
            done += (Path(folder) / relative).stat().st_size
            self.calls.append(done)
            if progress:
                progress(min(done, total), total)
        if progress:
            progress(total, total)
        return result


def test_steps_are_announced_in_order(kit, tmp_path):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 0, screen(ctx)
    steps = re.findall(r"^Étape (\d+)/(\d+) — ", ctx.out.getvalue(), flags=re.M)
    total = int(steps[0][1])
    assert [int(index) for index, _ in steps] == list(range(1, total + 1)) and {count for _, count in steps} == {str(total)}
    assert "Étape 4/12 — Copie du programme (" in ctx.out.getvalue()


def test_progress_reaches_the_manifest_total(kit, tmp_path, monkeypatch):
    copy = CopieAvecProgression(linux_kit.install_copy)
    monkeypatch.setattr(linux_kit, "install_copy", copy)
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    percents = [int(value) for value in re.findall(r"Copie : (\d+) %", ctx.out.getvalue())]
    assert percents == sorted(percents) and percents[-1] == 100 and len(percents) <= 11
    total = linux_install.fr_size(manifest_of(kit)["bytes"])
    assert f"sur {total})" in ctx.out.getvalue()


def test_no_carriage_return_outside_a_terminal(kit, tmp_path, monkeypatch):
    monkeypatch.setattr(linux_kit, "install_copy", CopieAvecProgression(linux_kit.install_copy))
    plain = context(kit)
    assert install(plain, tmp_path / "a", tmp_path / "da", "--no-start") == 0
    assert "\r" not in plain.out.getvalue()
    terminal = context(kit, tty=True)
    assert install(terminal, tmp_path / "b", tmp_path / "db", "--no-start", "--sans-menu") == 0, screen(terminal)
    assert "\rCopie : " in terminal.out.getvalue()


def test_every_report_step_has_a_duration(kit, tmp_path):
    assert install(context(kit), tmp_path / "programmes", tmp_path / "donnees") == 0
    report = json.loads(next((tmp_path / "donnees").glob("install-*.json")).read_text(encoding="utf-8"))
    assert report["steps"] and all(isinstance(step["duration_s"], float) and step["duration_s"] >= 0 for step in report["steps"])
    assert isinstance(report["duration_s"], float) and report["duration_s"] >= sum(step["duration_s"] for step in report["steps"]) - 1e-6


def test_no_unmeasured_duration_is_announced(kit, tmp_path):
    source = (linux_kit.ROOT / "tools/dist/linux_install.py").read_text(encoding="utf-8")
    assert "minute" not in source
    # Attente maximale réelle de `up` (supervisor.py), seule durée annoncée avant la recette.
    assert "time.monotonic() + 150" in (linux_kit.ROOT / "services/runtime/supervisor.py").read_text(encoding="utf-8")
    assert linux_install.STARTUP_WAIT_MAX_S == 150
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir"], ctx) == 0
    assert "attente maximale du démarrage : 150 s" in ctx.out.getvalue()


# --- KIT4-08 : retrouver l'installation ----------------------------------------------------------------------------------

def registry(home: Path) -> list[str]:
    return json.loads((home / ".local/state/atelier-documentaire/installations.json").read_text(encoding="utf-8"))["destinations"]


def test_a_default_install_registers_its_destination(kit, isolated_home):
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    assert registry(isolated_home) == [str(default_paths(isolated_home)[0])]


def test_a_relative_xdg_state_home_is_ignored(kit, tmp_path, isolated_home, monkeypatch):
    monkeypatch.chdir(tmp_path)  # QA-07
    monkeypatch.setenv("XDG_STATE_HOME", "relatif/etat")
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    assert registry(isolated_home) == [str(default_paths(isolated_home)[0])] and not (tmp_path / "relatif").exists()


def test_update_from_a_second_kit_finds_the_installation_without_destination(kit, tmp_path, monkeypatch, isolated_home):
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["update", "--oui", "--no-start"], ctx) == 0, screen(ctx)
    assert pointer_of(default_paths(isolated_home)[0])["current"]["kit_id"] == manifest_of(kit_b)["kit_id"]


def test_a_new_kit_without_arguments_proposes_the_update(kit, tmp_path, monkeypatch, isolated_home):
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b, tty=True, answers=["o"])
    assert linux_install.main(["--no-start"], ctx) == 0, screen(ctx)
    assert "mise à jour" in ctx.out.getvalue() and "Récapitulatif de la mise à jour" in ctx.out.getvalue()
    pointer = pointer_of(default_paths(isolated_home)[0])
    assert pointer["current"]["kit_id"] == manifest_of(kit_b)["kit_id"] and pointer["previous"]["kit_id"] == manifest_of(kit)["kit_id"]


def test_uninstall_without_kit_id_targets_the_previous_version_then_the_current_one(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(kit_b)) == 0
    first = context(kit_b)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--oui"], first) == 0, screen(first)
    assert "le retour arrière ne sera plus possible" in first.out.getvalue()
    pointer = pointer_of(destination)
    assert pointer["previous"] is None and pointer["current"]["kit_id"] == manifest_of(kit_b)["kit_id"]
    assert not (destination / manifest_of(kit)["kit_id"]).exists()
    second = context(kit_b)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--oui"], second) == 0, screen(second)
    assert pointer_of(destination)["current"] is None and (data_root / "profile.yaml").is_file()


def test_status_without_installation_says_so_in_french_and_returns_1(kit):
    ctx = context(kit)
    assert linux_install.main(["status"], ctx) == 1
    assert "Aucune installation de l'atelier trouvée" in ctx.out.getvalue()


def test_status_json_keeps_the_previous_structure(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination), "--json"], ctx) == 0, screen(ctx)
    result = json.loads(ctx.out.getvalue())
    assert {"destination", "versions", "pointer", "problems", "instance"} <= set(result)
    assert result["versions"] == [current["kit_id"]] and result["pointer"]["current"]["kit_id"] == current["kit_id"]
    assert result["problems"] == [] and result["instance"]["status"] == "stopped"


def test_two_registered_destinations_are_listed_without_terminal(kit, tmp_path):
    # Deux installations inscrites au registre : chacune avec sa propre entrée de menu (--sans-menu n'inscrit rien, S12).
    for name in ("un", "deux"):
        assert install(context(kit), tmp_path / name / "programmes", tmp_path / name / "donnees", "--no-start",
                       "--menu", str(tmp_path / name / "menu")) == 0
    ctx = context(kit)
    assert linux_install.main(["status"], ctx) == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert str(tmp_path / "un/programmes") in errors and str(tmp_path / "deux/programmes") in errors and "--destination" in errors
    chosen = context(kit, tty=True, answers=["2"])
    assert linux_install.main(["status"], chosen) == 0, screen(chosen)
    assert f"Installation : {tmp_path / 'deux/programmes'}" in chosen.out.getvalue()


# --- KIT4-09 : entrée de menu, icône et actions ---------------------------------------------------------------------------

def applications(home: Path) -> Path:
    return home / ".local/share/applications"


def desktop_groups(text: str) -> dict[str, dict[str, str]]:
    groups, name = {}, None
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1]
            groups[name] = {}
        elif "=" in line and name:
            key, value = line.split("=", 1)
            groups[name][key] = value
    return groups


VALIDATOR = shutil.which("desktop-file-validate")


def validate(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([VALIDATOR, str(path)], capture_output=True, text=True, check=False, timeout=60)


def test_install_writes_a_valid_menu_entry_by_default(kit, tmp_path, isolated_home):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    entry = applications(isolated_home) / "atelier-documentaire.desktop"
    groups = desktop_groups(entry.read_text(encoding="utf-8"))
    main = groups["Desktop Entry"]
    assert {key: main[key] for key in ("Type", "Version", "Name", "Terminal", "Categories")} == {
        "Type": "Application", "Version": "1.1", "Name": "Atelier documentaire", "Terminal": "true", "Categories": "Office;"}
    assert main["GenericName"] and main["Keywords"].endswith(";") and main["Comment"]
    assert main["Icon"] == str(destination / "atelier-documentaire.svg") and main["TryExec"] == str(destination / "atelier")
    assert main["Exec"] == f'"{destination}/atelier" ouvrir --attendre' and main["X-Atelier-Destination"] == str(destination)
    if VALIDATOR:
        result = validate(entry)
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(VALIDATOR is None, reason="desktop-file-validate absent de ce poste")
@pytest.mark.parametrize("folder", ["pro grammes", "pro$grammes", "pro%grammes", "pro`grammes", "pro'grammes", "pro\\grammes"],
                         ids=["espace", "dollar", "pourcent", "accent-grave", "apostrophe", "barre-oblique-inverse"])
def test_unusual_destinations_give_valid_entries(tmp_path, folder):
    destination = tmp_path / folder
    current = {"kit_id": "k", "program": str(destination / "k"), "model": "qwen3.5:4b",
               "profiles": {"qwen3.5:4b": "/d/profile.yaml", "qwen3.5:2b": "/d/profile-qwen3.5-2b.yaml"}}
    entry = tmp_path / "atelier-documentaire.desktop"
    entry.write_text(linux_install.desktop_text(destination, current, icon=True), encoding="utf-8")
    result = validate(entry)
    assert result.returncode == 0, result.stdout + result.stderr
    assert linux_install.desktop_owner(entry) == str(destination)


def test_a_destination_with_a_double_quote_gets_no_menu_entry(kit, tmp_path, isolated_home):
    # Exec exigerait `\\"` (Desktop Entry, règle des chaînes puis guillemets ; lu ainsi par GLib 2.64), forme que
    # desktop-file-validate 0.24 refuse : refus avant toute écriture, l'installation reste possible sans menu.
    destination = tmp_path / 'pro"grammes'
    ctx = context(kit)
    assert install(ctx, destination, tmp_path / "donnees", "--no-start") == linux_install.EXIT_REFUSED
    assert "guillemet droit" in ctx.err.getvalue() and "--sans-menu" in ctx.err.getvalue() and not destination.exists()
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start", "--sans-menu") == 0
    assert not applications(isolated_home).exists()


def test_actions_match_their_groups_and_offer_the_other_model(kit, tmp_path, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    groups = desktop_groups((applications(isolated_home) / "atelier-documentaire.desktop").read_text(encoding="utf-8"))
    actions = groups["Desktop Entry"]["Actions"].rstrip(";").split(";")
    assert actions == ["arreter", "diagnostic", "sauvegarder", "modele-qwen3-5-2b"]
    assert {name for name in groups if name.startswith("Desktop Action ")} == {f"Desktop Action {action}" for action in actions}
    launcher = f'"{destination}/atelier"'
    assert groups["Desktop Action arreter"] == {"Name": "Arrêter l'atelier", "Exec": f"{launcher} arreter --attendre"}
    assert groups["Desktop Action modele-qwen3-5-2b"] == {"Name": "Ouvrir avec le modèle 2B",
                                                         "Exec": f'{launcher} ouvrir --modele "qwen3.5:2b" --attendre'}


def test_the_icon_file_exists_at_the_icon_path(kit, tmp_path, isolated_home):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    icon = Path(desktop_groups((applications(isolated_home) / "atelier-documentaire.desktop").read_text(encoding="utf-8"))["Desktop Entry"]["Icon"])
    assert icon.is_file() and icon.read_bytes() == (Path(current["program"]) / linux_install.ICON_SOURCE).read_bytes()
    assert linux_install.ICON_SOURCE == ICON_PATH


def test_sans_menu_writes_nothing_under_xdg_data_home(kit, tmp_path, isolated_home):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start", "--sans-menu") == 0
    assert not applications(isolated_home).exists() and not (isolated_home / ".local/bin").exists()
    pointer = pointer_of(tmp_path / "programmes")
    assert pointer["menu"] is False and pointer.get("menu_entry") is None and pointer.get("user_command") is None
    # S12, choix (a) : --sans-menu n'écrit rien hors des dossiers choisis, registre compris ; la fin dit comment mettre à jour.
    assert not (isolated_home / ".local").exists() and list(isolated_home.iterdir()) == []
    assert (f"Mettre à jour : « <dossier du kit suivant>/installer.sh update --destination {tmp_path / 'programmes'} » "
            "(installation non inscrite au registre : --sans-menu)") in ctx.out.getvalue()


def test_repair_sans_menu_removes_the_registry_entry(kit, isolated_home):
    assert linux_install.main(["--oui", "--no-start", "--emplacement", str(isolated_home / "atelier")], context(kit)) == 0
    destination = isolated_home / "atelier/programme"
    assert registry(isolated_home) == [str(destination)]
    assert linux_install.main(["repair", "--destination", str(destination), "--sans-menu"], context(kit)) == 0
    assert registry(isolated_home) == []


def test_a_relative_xdg_data_home_falls_back_to_home(kit, tmp_path, isolated_home, monkeypatch):
    monkeypatch.chdir(tmp_path)  # QA-07
    monkeypatch.setenv("XDG_DATA_HOME", "relatif")
    installed(kit, tmp_path, "--no-start")
    assert (applications(isolated_home) / "atelier-documentaire.desktop").is_file() and not (tmp_path / "relatif").exists()


def test_update_and_rollback_keep_the_entry(kit, tmp_path, monkeypatch, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    entry = applications(isolated_home) / "atelier-documentaire.desktop"
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(kit_b)) == 0
    assert entry.is_file() and linux_install.desktop_owner(entry) == str(destination)
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    assert entry.is_file() and (destination / "atelier-documentaire.svg").is_file()
    assert pointer_of(destination)["menu_entry"] == str(entry)


def test_a_menu_folder_change_removes_only_our_old_entry(kit, tmp_path, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    old = applications(isolated_home) / "atelier-documentaire.desktop"
    neighbour = write(applications(isolated_home), "autre.desktop", "[Desktop Entry]\nType=Application\nName=Autre\nExec=autre\n")
    ctx = context(kit)
    assert linux_install.main(["repair", "--destination", str(destination), "--menu", str(tmp_path / "menu")], ctx) == 0, screen(ctx)
    assert not old.exists() and (tmp_path / "menu/atelier-documentaire.desktop").is_file() and neighbour.is_file()
    assert pointer_of(destination)["menu_entry"] == str(tmp_path / "menu/atelier-documentaire.desktop")


def test_a_foreign_homonym_is_refused_before_any_write(kit, tmp_path, isolated_home):
    foreign = write(applications(isolated_home), "atelier-documentaire.desktop",
                    "[Desktop Entry]\nType=Application\nName=Autre atelier\nExec=autre\nX-Atelier-Destination=/ailleurs\n")
    before = foreign.read_bytes()
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "entrée de menu" in errors and "--sans-menu" in errors
    # REL-U15 (Desktop Menu Specification 1.1) : --sans-menu est le choix proposé ; une entrée écrite hors des dossiers
    # applications des données XDG n'apparaît pas dans le menu, ce que le message dit.
    assert "installer avec --sans-menu" in errors and errors.index("--sans-menu") < errors.index("--menu <dossier>")
    assert "n'apparaît pas dans le menu des applications" in errors
    assert foreign.read_bytes() == before and not (tmp_path / "programmes").exists() and ctx.runner.calls == []


def test_uninstalling_the_last_version_removes_entry_and_icon(kit, tmp_path, isolated_home):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    code, ctx = uninstall(kit, destination, current["kit_id"])
    assert code == 0, screen(ctx)
    assert not (applications(isolated_home) / "atelier-documentaire.desktop").exists()
    assert not (destination / "atelier-documentaire.svg").exists() and not (isolated_home / ".local/bin/atelier").exists()
    assert (data_root / "profile.yaml").is_file()


def test_status_reports_a_deleted_entry(kit, tmp_path, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    (applications(isolated_home) / "atelier-documentaire.desktop").unlink()
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 1
    assert "entrée de menu absente" in ctx.out.getvalue() and "repair" in ctx.out.getvalue()


def test_repair_sans_menu_removes_and_update_does_not_recreate(kit, tmp_path, monkeypatch, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["repair", "--destination", str(destination), "--sans-menu"], ctx) == 0, screen(ctx)
    assert not (applications(isolated_home) / "atelier-documentaire.desktop").exists() and not (isolated_home / ".local/bin/atelier").exists()
    assert pointer_of(destination)["menu"] is False and pointer_of(destination)["history"][-1]["event"] == "repair"
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(second_kit(tmp_path, monkeypatch))) == 0
    assert not (applications(isolated_home) / "atelier-documentaire.desktop").exists() and not (isolated_home / ".local/bin/atelier").exists()


def test_the_versioned_icon_matches_its_generator():
    from tools.dist import make_icon

    source = (linux_kit.ROOT / "apps/web/src/components/app-topbar.tsx").read_text(encoding="utf-8")
    geometry = make_icon.brand_geometry(source)
    assert geometry["paths"] == ["M6 3h8.5L19 7.5V21H6z", "M14.5 3v4.5H19", "M9 12h7M9 15h7M9 18h4"]
    assert make_icon.render(geometry).encode("utf-8") == (linux_kit.ROOT / ICON_PATH).read_bytes()
    assert make_icon.main(["--check"]) == 0


# --- KIT4-10 : fenêtre du menu lisible ----------------------------------------------------------------------------------

PAUSE = "Appuyez sur Entrée pour fermer cette fenêtre."


def launcher_context(kit, tmp_path, *, tty=True, answers=None, results=None):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(Path(current["program"]), runner=ProgrammeSimule(results=results), tty=tty, answers=answers)
    return destination, ctx


def test_attendre_pauses_after_a_failure(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path, answers=[""], results={"up": {"_rc": 1, "status": "failed", "message": "Qdrant absent."}})
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--attendre"], ctx) == 1
    assert PAUSE in ctx.out.getvalue() and ctx.replies == [] and "Qdrant absent." in ctx.err.getvalue()


@pytest.mark.parametrize("action", ["diagnostic", "etat", "sauvegarder", "journaux"])
def test_attendre_pauses_after_diagnostic_state_and_backup(kit, tmp_path, action):
    destination, ctx = launcher_context(kit, tmp_path, answers=[EOFError()])
    if action == "sauvegarder":
        # Une sauvegarde exige l'atelier démarré (REL-U03) : instance en marche sur le profil principal.
        ctx.runner.running = {str(ctx.kit): pointer_of(destination)["current"]["profile"]}
    assert linux_install.main(["run", "--destination", str(destination), action, "--attendre"], ctx) == 0, screen(ctx)
    assert PAUSE in ctx.out.getvalue() and ctx.replies == []


@pytest.mark.parametrize("action", ["ouvrir", "arreter"])
def test_attendre_does_not_pause_after_a_successful_open(kit, tmp_path, action):
    destination, ctx = launcher_context(kit, tmp_path)
    assert linux_install.main(["run", "--destination", str(destination), action, "--attendre"], ctx) == 0, screen(ctx)
    assert PAUSE not in ctx.out.getvalue()


def test_no_pause_without_the_option(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path)
    assert linux_install.main(["run", "--destination", str(destination), "diagnostic"], ctx) == 0
    assert PAUSE not in ctx.out.getvalue()


def test_no_pause_without_a_terminal(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path, tty=False)
    assert linux_install.main(["run", "--destination", str(destination), "diagnostic", "--attendre"], ctx) == 0
    assert PAUSE not in ctx.out.getvalue()


# --- KIT4-11 : instance en marche, états en français ----------------------------------------------------------------------

def running_2b(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    runner = ProgrammeSimule(last_started=current["program"])
    runner.running = {current["program"]: current["profiles"]["qwen3.5:2b"]}
    return destination, current, runner


def test_open_without_model_reuses_the_running_instance(kit, tmp_path):
    destination, current, runner = running_2b(kit, tmp_path)
    ctx = context(Path(current["program"]), runner=runner)
    assert linux_install.main(["run", "--destination", str(destination)], ctx) == 0, screen(ctx)
    # REL-U11 : instance déjà démarrée, sans ligne de démarrage contradictoire.
    assert runner.commands() == ["status", "up", "open"]
    assert "Atelier déjà démarré avec qwen3.5:2b ; ouverture dans le navigateur…" in ctx.out.getvalue()
    assert "Démarrage de l'atelier si nécessaire" not in ctx.out.getvalue() and "déjà ouvert" not in ctx.out.getvalue()
    assert runner.profiles_of("up") == runner.profiles_of("open") == [current["profiles"]["qwen3.5:2b"]]


def test_open_with_another_model_is_refused_in_launcher_terms(kit, tmp_path):
    destination, current, runner = running_2b(kit, tmp_path)
    ctx = context(Path(current["program"]), runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--modele", "qwen3.5:4b"], ctx) == linux_install.EXIT_REFUSED
    assert ("L'atelier tourne avec qwen3.5:2b. Pour passer à qwen3.5:4b : « atelier arreter », puis « atelier ouvrir --modele "
            "qwen3.5:4b » ; un traitement en cours serait interrompu.") in ctx.err.getvalue()
    assert "down puis up" not in screen(ctx) and runner.commands() == ["status"]


def test_an_unrelated_up_error_does_not_mention_the_model(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path, tty=False, results={"up": {"_rc": 1, "status": "failed", "message": "Qdrant absent."}})
    assert linux_install.main(["run", "--destination", str(destination)], ctx) == 1
    assert "Qdrant absent." in ctx.err.getvalue() and "modèle" not in ctx.err.getvalue() and "--modele" not in ctx.err.getvalue()


@pytest.mark.parametrize(("state", "text"), [
    ("starting", "en cours de démarrage"), ("running", "démarré (modèle qwen3.5:4b)"), ("stopping", "arrêt en cours"),
    ("stopped", "arrêté"), ("failed", "arrêté sur erreur : « atelier diagnostic » en détaille la cause"),
    ("stale", "interrompu sans arrêt propre : relancer « atelier ouvrir »")])
def test_state_is_translated(kit, tmp_path, state, text):
    def status(argv):
        profile = argv[argv.index("--profile") + 1]
        return {"status": state, "profile_matches_current": True, "profile_sha256": sha256(profile)}

    destination, ctx = launcher_context(kit, tmp_path, tty=False, results={"status": status})
    assert linux_install.main(["run", "--destination", str(destination), "etat"], ctx) == 0
    assert f"État : {text}." in ctx.out.getvalue() and f"État : {state}" not in ctx.out.getvalue()


def test_open_says_how_to_stop(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path, tty=False)
    assert linux_install.main(["run", "--destination", str(destination)], ctx) == 0
    assert ("L'atelier reste démarré après la fermeture du navigateur ; pour l'arrêter : menu Atelier documentaire > Arrêter "
            "l'atelier, ou « atelier arreter ».") in ctx.out.getvalue()


def test_journaux_lists_the_log_paths(kit, tmp_path):
    destination, ctx = launcher_context(kit, tmp_path, tty=False)
    assert linux_install.main(["run", "--destination", str(destination), "journaux"], ctx) == 0
    assert "  qdrant : /donnees/data/logs/i1/qdrant.log" in ctx.out.getvalue() and ctx.runner.commands() == ["logs"]


# --- KIT4-12 : version courante gardée, retour arrière exact -------------------------------------------------------------

def updated(kit, tmp_path, monkeypatch, *extra):
    destination, data_root, first, _ = installed(kit, tmp_path, "--no-start")
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start", *extra], ctx) == 0, screen(ctx)
    return destination, data_root, first, pointer_of(destination)["current"], kit_b


def test_uninstalling_the_current_version_with_a_previous_one_is_refused(kit, tmp_path, monkeypatch, isolated_home):
    destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    code, ctx = uninstall(kit_b, destination, second["kit_id"])
    assert code == linux_install.EXIT_REFUSED
    assert f"Revenir d'abord à {first['kit_id']}" in ctx.err.getvalue() and "rien n'a été supprimé" in ctx.err.getvalue()
    assert f"« {second['program']}/installer.sh rollback »" in ctx.err.getvalue()  # REL-U12 : commande absolue
    assert Path(second["program"]).is_dir() and f"version {second['kit_id']}." in (destination / "atelier").read_text(encoding="utf-8")
    assert (applications(isolated_home) / "atelier-documentaire.desktop").is_file()


def test_rollback_then_uninstall_of_the_abandoned_version(kit, tmp_path, monkeypatch, isolated_home):
    destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    assert linux_install.main(["rollback", "--destination", str(destination)], context(kit)) == 0
    ctx = context(kit)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    assert not Path(second["program"]).exists() and f"version {first['kit_id']}." in (destination / "atelier").read_text(encoding="utf-8")
    assert (applications(isolated_home) / "atelier-documentaire.desktop").is_file()


@pytest.mark.parametrize(("change", "message"), [
    (lambda pointer: pointer.update(previous=None), "Aucune version précédente n'est désignée"),
    (lambda pointer: pointer.update(previous=pointer["current"], current=None), "Aucune version courante"),
    (lambda pointer: pointer.update(previous={**pointer["previous"], "rolled_back": True}), "Retour arrière déjà effectué"),
], ids=["sans-precedente", "sans-courante", "abandonnee"])
def test_rollback_message_matches_the_pointer_state(kit, tmp_path, monkeypatch, change, message):
    destination, _, _, _, kit_b = updated(kit, tmp_path, monkeypatch)
    pointer = pointer_of(destination)
    change(pointer)
    (destination / "installation.json").write_text(json.dumps(pointer), encoding="utf-8")
    ctx = context(kit_b)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == linux_install.EXIT_REFUSED
    assert message in ctx.err.getvalue() and pointer_of(destination) == pointer


def test_status_reports_an_undesignated_version(kit, tmp_path, monkeypatch):
    destination, _, first, _, _ = updated(kit, tmp_path, monkeypatch)
    from tests.unit.test_dist_linux_review import third_kit

    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(third_kit(tmp_path, monkeypatch))) == 0
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 1
    assert f"version présente non désignée : {first['kit_id']}" in ctx.out.getvalue() and "uninstall --anciennes" in ctx.out.getvalue()


# --- KIT4-14 : messages de fin --------------------------------------------------------------------------------------------

def test_install_end_block_names_data_stop_and_guide(kit, tmp_path):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 0
    output = ctx.out.getvalue()
    program = tmp_path / "programmes" / manifest_of(kit)["kit_id"]
    assert f"Données : {tmp_path / 'donnees'}" in output and "« atelier arreter »" in output
    assert f"Guide : {program}/LISEZMOI.md" in output and f"Programme : {program}" in output


def test_update_end_gives_an_absolute_rollback_command(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == 0
    new = destination / manifest_of(kit_b)["kit_id"]
    old_id = manifest_of(kit)["kit_id"]
    output = ctx.out.getvalue()
    assert f"{new}/installer.sh rollback" in output and f"{new}/installer.sh uninstall --kit-id {old_id}" in output
    assert re.search(rf"Retirer {re.escape(old_id)} \(\d+,\d \S+\)", output), output


def test_restoring_rollback_names_new_and_old_roots(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    updater = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], updater) == 0
    runner = ProgrammeSimule(last_started=updater.runner.last_started)
    runner.running = dict(updater.runner.running)
    ctx = context(kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    restored = Path(pointer_of(destination)["current"]["data_root"])
    output = ctx.out.getvalue()
    assert f"Données actives : {restored}" in output and f"Ancienne racine conservée, non supprimée : {data_root}" in output
    assert "Ports : " in output and data_root.is_dir()


def test_uninstall_lists_the_kept_paths(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    code, ctx = uninstall(kit, destination, current["kit_id"])
    assert code == 0
    output = ctx.out.getvalue()
    for kept in (f"Données : {data_root}", f"Sauvegardes : {data_root / 'backups'}", f"Pointeur et rapports : {destination}"):
        assert kept in output
    assert "Les supprimer reste une décision de l'utilisateur." in output


# --- KIT4-17 : commande atelier dans ~/.local/bin --------------------------------------------------------------------------

def test_the_user_command_is_installed_with_its_marker(kit, tmp_path, isolated_home):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    command = isolated_home / ".local/bin/atelier"
    assert os.access(command, os.X_OK) and linux_install.command_owner(command) == str(destination)
    assert pointer_of(destination)["user_command"] == str(command)


def test_a_new_local_bin_asks_for_a_new_session(kit, tmp_path, isolated_home):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0
    assert "nouvelle session" in ctx.out.getvalue() and str(tmp_path / "programmes/atelier") in ctx.out.getvalue()
    # REL-U20 : le PATH ne change que si le profil de session ajoute ce dossier (cas d'Ubuntu), ce que le message dit.
    assert (f"Commande atelier : {isolated_home / '.local/bin'} vient d'être créé : « atelier » ne sera trouvé qu'à une nouvelle "
            "session, et seulement si le profil de session ajoute ce dossier au PATH") in ctx.out.getvalue()


def test_an_existing_local_bin_outside_the_path_gives_the_full_path(kit, tmp_path, isolated_home, monkeypatch):
    # REL-U20 : dossier présent mais absent du PATH : aucune promesse de nouvelle session.
    (isolated_home / ".local/bin").mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0
    output = ctx.out.getvalue()
    assert (f"{isolated_home / '.local/bin'} n'est pas dans le PATH de cette session : employer le chemin complet "
            f"{tmp_path / 'programmes/atelier'}") in output and "vient d'être créé" not in output


def test_a_foreign_file_is_kept_with_a_warning(kit, tmp_path, isolated_home):
    foreign = write(isolated_home, ".local/bin/atelier", "#!/bin/sh\necho autre outil\n", executable=True)
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    assert foreign.read_text(encoding="utf-8") == "#!/bin/sh\necho autre outil\n"
    assert "laissé intact" in ctx.out.getvalue() and pointer_of(tmp_path / "programmes")["user_command"] is None
    assert "« atelier arreter »" not in ctx.out.getvalue() and f"{tmp_path / 'programmes/atelier'} arreter" in ctx.out.getvalue()


def test_the_command_is_removed_with_the_last_version(kit, tmp_path, isolated_home):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    assert uninstall(kit, destination, current["kit_id"])[0] == 0
    assert not (isolated_home / ".local/bin/atelier").exists()


# --- KIT4-18 : retour arrière avec restauration confirmé ----------------------------------------------------------------

def started_update(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root) == 0
    updater = context(second_kit(tmp_path, monkeypatch))
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], updater) == 0
    runner = ProgrammeSimule(last_started=updater.runner.last_started)
    runner.running = dict(updater.runner.running)
    return destination, data_root, runner


def test_restoring_rollback_without_confirmation_changes_nothing(kit, tmp_path, monkeypatch):
    destination, _, runner = started_update(kit, tmp_path, monkeypatch)
    before = pointer_of(destination)
    ctx = context(kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == linux_install.EXIT_REFUSED
    assert not {"down", "restore"} & set(runner.commands()) and pointer_of(destination) == before
    assert "Récapitulatif du retour arrière" in ctx.err.getvalue() and "--oui" in ctx.err.getvalue()


def test_restoring_rollback_with_oui_names_backup_and_roots(kit, tmp_path, monkeypatch):
    destination, data_root, runner = started_update(kit, tmp_path, monkeypatch)
    backup = pointer_of(destination)["current"]["backup"]
    ctx = context(kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    output = ctx.out.getvalue()
    assert f"Sauvegarde restaurée : {backup} (2026-10-06 20:00 UTC)" in output
    assert "Nouvelle racine des données : " in output and f"Ancienne racine conservée : {data_root}" in output
    assert "écritures postérieures à la sauvegarde" in output


def test_simple_switch_back_needs_no_confirmation(kit, tmp_path, monkeypatch):
    destination, _, first, _, _ = updated(kit, tmp_path, monkeypatch)
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 0, screen(ctx)
    assert pointer_of(destination)["current"]["kit_id"] == first["kit_id"] and "Récapitulatif" not in screen(ctx)


# --- KIT4-19 : aides en français -----------------------------------------------------------------------------------------

def test_help_is_french_and_hides_internals(kit):
    for argv in (["--aide"], ["install", "--aide"], ["uninstall", "-h"]):
        ctx = context(kit)
        assert linux_install.main(argv, ctx) == 0
        text = ctx.out.getvalue()
        assert text.startswith("Usage : installer.sh") and "==SUPPRESS==" not in text and "R26" not in text
        assert "show this help" not in text and "usage:" not in text and "positional arguments" not in text
    ctx = context(kit)
    linux_install.main(["--aide"], ctx)
    for name in linux_install.INSTALLER_COMMANDS:
        assert f"  {name} " in ctx.out.getvalue()
    assert "LISEZMOI.md" in ctx.out.getvalue() and "run" not in re.findall(r"^  (\w+) ", ctx.out.getvalue(), flags=re.M)


def test_model_help_follows_the_kit_manifest(kit, tmp_path, monkeypatch):
    four = make_kit(tmp_path, monkeypatch, name="kit-4b", repository=tmp_path / "depot", models=("4b",))
    for folder, expected in ((kit, "qwen3.5:4b par défaut ; livrés par ce kit : qwen3.5:4b, qwen3.5:2b"),
                             (four, "qwen3.5:4b par défaut ; livré par ce kit : qwen3.5:4b")):
        ctx = context(folder)
        assert linux_install.main(["install", "--aide"], ctx) == 0
        assert expected in " ".join(ctx.out.getvalue().split())


def test_invalid_argument_gives_a_french_message_and_code_2(kit):
    commands = ", ".join(linux_install.INSTALLER_COMMANDS)
    for argv, message in ((["install", "--inconnue"], "arguments non reconnus : --inconnue"),
                          (["demarrer"], f"installer.sh : commande inconnue : demarrer (commandes : {commands})"),
                          (["instal"], f"installer.sh : commande inconnue : instal (commandes : {commands})"),
                          (["--oui", "instal"], "commande inconnue : instal"),
                          (["uninstall", "--kit-id"], "une valeur est attendue")):
        ctx = context(kit)
        assert linux_install.main(argv, ctx) == linux_install.EXIT_USAGE
        errors = ctx.err.getvalue()
        assert message in errors and "--aide" in errors and ctx.out.getvalue() == ""
        # REL-U07 : ni la commande interne run, ni le jeton anglais d'argparse.
        assert not re.search(r"\brun\b", errors) and "argument command" not in errors and "invalid" not in errors


def test_atelier_help_lists_every_launcher_action(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination), "--aide"], ctx) == 0
    text = ctx.out.getvalue()
    assert text.startswith("Usage : atelier") and "--destination" not in text and "installer.sh" not in text.split("\n")[0]
    for action in linux_install.LAUNCHER_ACTIONS:
        assert f"  {action} " in text
    assert "qwen3.5:4b (principal), qwen3.5:2b" in text


# --- KIT4-20 : libellés, nombres, seuils, refus en liste -----------------------------------------------------------------

def test_screen_labels_are_accented_and_reports_keep_ids(kit, tmp_path):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 0
    output = ctx.out.getvalue()
    for label in ("[ok] Contrôles du poste et des emplacements", "[ok] Précompilation", "[ok] Démarrage", "[vert] Contrôle réel"):
        assert label in output, label
    for raw in ("precontroles", "precompilation", "demarrage", "controle", "systeme"):
        assert f"] {raw}" not in output
    steps = [step["step"] for step in json.loads(next((tmp_path / "donnees").glob("install-*.json")).read_text(encoding="utf-8"))["steps"]]
    assert {"precontroles", "precompilation", "demarrage", "controle"} <= set(steps)


def test_decimal_comma():
    assert linux_install.fr_number(7.6) == "7,6" and linux_install.fr_number(1234.5) == "1 234,5"
    assert linux_install.fr_size(11_978_322_110) == "11,16 Gio" and linux_install.fr_size(512 * 1024**2) == "0,50 Gio"


def test_memory_message_uses_memory_gib_min(kit, tmp_path):
    with_manifest(kit, target={"memory_gib_min": 15})
    ctx = context(kit, probe=PosteSimule(memory=7.6))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "ce poste a 7,6 Gio ; l'atelier exige 15 Gio visibles (poste de 16 Go)" in ctx.err.getvalue()


def test_multiple_refusals_are_listed_one_per_line(kit, tmp_path):
    ctx = context(kit, probe=PosteSimule(machine="x86_64", setpriv=None))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    lines = [line for line in ctx.err.getvalue().splitlines() if line.startswith("  - ")]
    assert len(lines) == 2 and " — " in lines[0] and ";" not in lines[0].split(" — ")[0]


# --- KIT4-21, KIT4-24 : fichiers ajoutés ou altérés, kit lu une seule fois ----------------------------------------------

def test_an_added_file_does_not_block_and_is_not_copied(kit, tmp_path):
    (kit / "notes.txt").write_text("notes de l'utilisateur", encoding="utf-8")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    assert "Fichiers ajoutés dans le dossier du kit, ignorés (non copiés) : notes.txt" in ctx.out.getvalue()
    assert not (tmp_path / "programmes" / manifest_of(kit)["kit_id"] / "notes.txt").exists()


def test_an_altered_file_stops_the_copy_and_designates_nothing(kit, tmp_path):
    write(kit, "services/api/main.py", "altéré")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_PARTIAL
    errors = ctx.err.getvalue()
    assert "Kit altéré (" in errors and "services/api/main.py" in errors and "copie partielle retirée, rien n'a été désigné" in errors
    assert not (tmp_path / "programmes" / manifest_of(kit)["kit_id"]).exists() and not (tmp_path / "programmes/installation.json").exists()
    assert ctx.runner.calls == []


def test_a_kit_on_exfat_names_the_filesystem(kit, tmp_path):
    (kit / linux_kit.TESSERACT_BINARY).write_bytes(b"\x7fELF autre")
    ctx = context(kit, probe=PosteSimule(fstype={str(kit): "exfat", "*": "ext4"}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "volume exfat" in ctx.err.getvalue() and "disque Linux local" in ctx.err.getvalue()


def test_each_kit_file_is_read_once_during_install(kit, tmp_path, monkeypatch):
    opened: dict[str, int] = {}
    real_open = Path.open
    root = kit.resolve()

    def spy(self, mode="r", *args, **kwargs):
        if "r" in mode and "b" in mode and Path(self).resolve().is_relative_to(root):
            relative = Path(self).resolve().relative_to(root).as_posix()
            opened[relative] = opened.get(relative, 0) + 1
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    assert install(context(kit), tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0
    checks = set(manifest_of(kit)["target"]["ldd_checks"])
    for relative in linux_kit.read_sums(kit):
        # Listes déclarées : contrôlées avant la copie, relues par la copie puis copiées ; cibles de ldd : vérifiées puis copiées.
        expected = 3 if relative in {"SYMLINKS", "EXECUTABLES"} else 2 if relative in checks else 1
        assert opened.get(relative, 0) <= expected, (relative, opened.get(relative))
        assert opened.get(relative, 0) >= 1, relative


# --- KIT4-22 : modèle principal durable ----------------------------------------------------------------------------------

def test_model_command_switches_the_principal_without_touching_profiles(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start", "--model", "qwen3.5:2b")
    before = {path: Path(path).read_bytes() for path in current["profiles"].values()}
    ctx = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination), "modele", "qwen3.5:4b"], ctx) == 0, screen(ctx)
    pointer = pointer_of(destination)
    assert pointer["current"]["model"] == "qwen3.5:4b" and pointer["current"]["profile"] == current["profiles"]["qwen3.5:4b"]
    assert pointer["history"][-1]["event"] == "modele" and {path: Path(path).read_bytes() for path in before} == before
    opener = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination)], opener) == 0
    assert opener.runner.profiles_of("up") == [current["profiles"]["qwen3.5:4b"]]


def test_model_command_is_refused_while_the_other_model_runs(kit, tmp_path):
    # Principal 4B en marche ; adopter le 2B exigerait d'arrêter l'instance : refus hors terminal, sans --oui.
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    runner = ProgrammeSimule(last_started=current["program"])
    runner.running = {current["program"]: current["profiles"]["qwen3.5:4b"]}
    before = pointer_of(destination)
    ctx = context(Path(current["program"]), runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "modele", "qwen3.5:2b"], ctx) == linux_install.EXIT_REFUSED
    assert "L'atelier tourne avec qwen3.5:4b" in ctx.err.getvalue() and "atelier arreter" in ctx.err.getvalue()
    assert pointer_of(destination) == before and "down" not in runner.commands()


def test_rollback_restores_the_previous_principal(kit, tmp_path, monkeypatch):
    destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["modele", "qwen3.5:2b", "--destination", str(destination)], ctx) == 0, screen(ctx)
    assert pointer_of(destination)["current"]["model"] == "qwen3.5:2b"
    assert linux_install.main(["rollback", "--destination", str(destination)], context(kit)) == 0
    assert pointer_of(destination)["current"]["model"] == first["model"] == "qwen3.5:4b"


def test_update_to_a_4b_only_kit_succeeds_after_switching(kit, tmp_path, monkeypatch):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start", "--model", "qwen3.5:2b")
    assert linux_install.main(["run", "--destination", str(destination), "modele", "qwen3.5:4b"], context(Path(current["program"]))) == 0
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'suivante'\n")
    git(repository, "commit", "-q", "-am", "version suivante")
    web_provenance(repository)  # interface construite depuis ce commit (KIT4-26)
    four = make_kit(tmp_path, monkeypatch, name="kit-4b", repository=repository, models=("4b",))
    ctx = context(four)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == 0, screen(ctx)
    assert pointer_of(destination)["current"]["model"] == "qwen3.5:4b"


def test_update_with_model_changes_the_principal(kit, tmp_path, monkeypatch):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start", "--model", "qwen3.5:2b")
    ctx = context(second_kit(tmp_path, monkeypatch))
    assert linux_install.main(["update", "--destination", str(destination), "--model", "qwen3.5:4b", "--oui", "--no-start"], ctx) == 0, screen(ctx)
    updated_entry = pointer_of(destination)["current"]
    assert updated_entry["model"] == "qwen3.5:4b" and updated_entry["profile"] == current["profiles"]["qwen3.5:4b"]
    assert "[info] Modèle principal" not in ctx.out.getvalue()


# --- KIT4-23 : reprise des données, anciennes versions, retrait complet -------------------------------------------------

def a_backup(data_root: Path) -> Path:
    backup = data_root / "backups/20261006T190000Z-a1b2c3d4"
    write(backup, "manifest.json", json.dumps({"format": "rag-native-backup-v1", "created_at_utc": "2026-10-06T19:00:00+00:00",
                                               "state": "verified"}))
    return backup


def test_reinstall_on_kept_data_after_full_uninstall(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    a_backup(data_root)
    principal = (data_root / "profile.yaml").read_bytes()
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    before = inventory(data_root)
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--reprendre-donnees", "--no-start") == 0, screen(ctx)
    after = inventory(data_root)
    assert (data_root / "profile.yaml").read_bytes() == principal and {key: after[key] for key in before} == before
    assert all(re.fullmatch(r"reprise-\d{8}T\d{6}Z\.json", name) for name in set(after) - set(before)), set(after) - set(before)
    pointer = pointer_of(destination)
    assert pointer["current"]["kit_id"] == current["kit_id"] and pointer["current"]["profile"] == str(data_root / "profile.yaml")
    assert "derive" in ctx.runner.commands() and "init-profile" not in ctx.runner.commands()


def test_reprise_without_confirmation_writes_nothing(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    a_backup(data_root)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    ctx = context(kit)
    code = linux_install.main(["install", "--destination", str(destination), "--data-root", str(data_root), "--reprendre-donnees"], ctx)
    assert code == linux_install.EXIT_REFUSED and "aucune version installée ne peut les sauvegarder" in ctx.err.getvalue()
    assert "20261006T190000Z-a1b2c3d4" in ctx.err.getvalue() and not (destination / current["kit_id"]).exists()


def test_reprise_without_any_backup_is_refused_pending_arbitration(kit, tmp_path):
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--reprendre-donnees") == linux_install.EXIT_REFUSED
    assert "aucune sauvegarde" in ctx.err.getvalue() and ctx.runner.calls == []


NO_BACKUP_WARNING = ("Attention : aucune sauvegarde dans {backups} ; une réinstallation sur ces données sera refusée (reprise sans "
                     "sauvegarde non prise en charge). Sauvegarder d'abord : « atelier ouvrir », puis « atelier sauvegarder »")


def summary_of(ctx) -> str:
    """Récapitulatif de la désinstallation, affiché avant toute suppression."""
    return ctx.out.getvalue().split("Récapitulatif de la désinstallation :", 1)[1].split("Désinstallation terminée", 1)[0]


@pytest.mark.parametrize("option", [["--tout"], []], ids=["tout", "seule-version"])
def test_uninstalling_the_last_version_without_a_backup_warns_that_reinstalling_will_be_refused(kit, tmp_path, option):
    # U2-02 : sans sauvegarde, les données conservées ne pourront plus être reprises ; le récapitulatif le dit avant la
    # suppression, avec les commandes qui font la sauvegarde tant que l'atelier est installé.
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["uninstall", "--destination", str(destination), *option, "--oui"], ctx) == 0, screen(ctx)
    assert NO_BACKUP_WARNING.format(backups=data_root / "backups") in summary_of(ctx)
    # Bloc de fin : le dossier des sauvegardes conservé est vide, ce que la ligne dit au lieu de laisser croire le contraire.
    assert f"  Sauvegardes : {data_root / 'backups'} (aucune sauvegarde)\n" in ctx.out.getvalue().split("Désinstallation terminée", 1)[1]


def test_no_backup_warning_while_a_version_remains_or_once_a_backup_exists(kit, tmp_path, monkeypatch):
    destination, data_root, _, _, kit_b = updated(kit, tmp_path, monkeypatch)
    shutil.rmtree(data_root / "backups")  # sauvegarde de la mise à jour retirée : seule la version restante compte
    ctx = context(kit_b)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    assert "aucune sauvegarde" not in summary_of(ctx)
    a_backup(data_root)
    ctx = context(kit_b)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], ctx) == 0, screen(ctx)
    assert "aucune sauvegarde" not in summary_of(ctx)


def test_install_on_kept_data_without_backup_offers_another_data_root_and_never_update(kit, tmp_path):
    # U2-02 : après un retrait complet, aucune installation n'existe : ni « update », ni reprise impossible ; la seule voie
    # est une autre racine des données, citée en commande exacte.
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    before = inventory(data_root)
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == linux_install.EXIT_REFUSED
    err = ctx.err.getvalue()
    assert "update" not in err and "--reprendre-donnees" not in err, err
    assert (f"Données conservées dans {data_root} (profile.yaml), sans aucune sauvegarde dans {data_root / 'backups'} : elles ne sont "
            "jamais remplacées, et leur reprise sans sauvegarde n'est pas prise en charge.") in err, err
    assert f"« {kit}/installer.sh install --destination {destination} --oui --no-start --data-root <autre dossier> »" in err, err
    assert inventory(data_root) == before and ctx.runner.calls == []


def test_install_on_kept_data_with_a_backup_cites_the_exact_reprise(kit, tmp_path):
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    backup = a_backup(data_root)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == linux_install.EXIT_REFUSED
    err = ctx.err.getvalue()
    assert "update" not in err and f"dernière sauvegarde : {backup}" in err, err
    reprise = f"{kit}/installer.sh install --destination {destination} --data-root {data_root} --oui --no-start --reprendre-donnees"
    assert f"« {reprise} »" in err and "--data-root <autre dossier> »" in err, err
    code = linux_install.main(shlex.split(reprise)[1:], context(kit))
    assert code == 0 and pointer_of(destination)["current"]["profile"] == str(data_root / "profile.yaml")


def test_the_default_install_on_kept_data_writes_the_install_command(kit, isolated_home):
    # U2-02 : `./installer.sh --oui` sans commande ; la commande citée nomme install.
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    assert linux_install.main(["uninstall", "--tout", "--oui"], context(kit)) == 0
    ctx = context(kit)
    assert linux_install.main(["--oui", "--no-start"], ctx) == linux_install.EXIT_REFUSED
    assert f"« {kit}/installer.sh install --oui --no-start --data-root <autre dossier> »" in ctx.err.getvalue(), screen(ctx)
    assert "update" not in ctx.err.getvalue()


def test_reprise_without_any_backup_names_the_kept_data_and_another_data_root(kit, tmp_path):
    # U2-02 : refus formulé pour l'utilisateur, sans vocabulaire du suivi du projet.
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--reprendre-donnees") == linux_install.EXIT_REFUSED
    err = ctx.err.getvalue()
    assert (f"Reprise refusée : aucune sauvegarde dans {data_root / 'backups'}. La reprise de données sans sauvegarde n'est pas prise "
            "en charge : aucune version installée ne peut les sauvegarder avant une éventuelle évolution de leur format.") in err, err
    assert f"Les données restent dans {data_root}." in err
    assert f"« {kit}/installer.sh install --destination {destination} --oui --data-root <autre dossier> »" in err, err
    assert "trancher" not in err and "arbitrage" not in err and ctx.runner.calls == []


def test_uninstall_anciennes_keeps_current_and_previous(kit, tmp_path, monkeypatch):
    destination, _, first, second, _ = updated(kit, tmp_path, monkeypatch)
    from tests.unit.test_dist_linux_review import third_kit

    kit_c = third_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(kit_c)) == 0
    ctx = context(kit_c)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--anciennes", "--oui"], ctx) == 0, screen(ctx)
    assert not Path(first["program"]).exists() and Path(second["program"]).is_dir() and (destination / manifest_of(kit_c)["kit_id"]).is_dir()
    assert pointer_of(destination)["previous"]["kit_id"] == second["kit_id"]


def test_uninstall_tout_keeps_the_data_root_intact(kit, tmp_path, monkeypatch, isolated_home):
    destination, data_root, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    before = inventory(data_root)
    ctx = context(kit_b)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], ctx) == 0, screen(ctx)
    assert inventory(data_root) == before and not Path(first["program"]).exists() and not Path(second["program"]).exists()
    assert not (destination / "atelier").exists() and not (destination / "atelier-documentaire.svg").exists()
    assert not (applications(isolated_home) / "atelier-documentaire.desktop").exists() and not (isolated_home / ".local/bin/atelier").exists()
    assert registry(isolated_home) == []
    assert re.search(rf"Données : {re.escape(str(data_root))} \(\d+,\d+ \S+\)", ctx.out.getvalue()), ctx.out.getvalue()


# --- KIT4-30 : sauvegarde de mise à jour ---------------------------------------------------------------------------------

def test_update_is_refused_before_up_when_the_backup_would_not_fit(kit, tmp_path, monkeypatch):
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    probe = PosteSimule(tree_bytes=50 * GIB, free={str(data_root): 10 * GIB, "*": 10**12}, device={str(data_root): "8:1", "*": "179:1"})
    ctx = context(second_kit(tmp_path, monkeypatch), probe=probe)
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "sauvegarde" in errors and "100,0 Gio" in errors and "10,0 Gio libres" in errors
    assert "up" not in ctx.runner.commands() and "backup" not in ctx.runner.commands()


def test_backups_are_listed_with_the_rollback_one_marked(kit, tmp_path, monkeypatch):
    destination, data_root, _, second, kit_b = updated(kit, tmp_path, monkeypatch)
    old = a_backup(data_root)
    ctx = context(kit_b)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) in {0, 1}
    output = ctx.out.getvalue()
    assert f"{Path(second['backup']).name} — 2026-10-06 20:00 UTC — " in output and "nécessaire au retour arrière" in output
    assert f"{old.name} — 2026-10-06 19:00 UTC — " in output
    marked = [line for line in output.splitlines() if "nécessaire au retour arrière" in line]
    assert len(marked) == 1 and Path(second["backup"]).name in marked[0]


# --- Mise à jour, bascule et retour arrière -------------------------------------------------------------------------------

def second_kit(tmp_path, monkeypatch) -> Path:
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'suivante'\n")
    git(repository, "commit", "-q", "-am", "version suivante")
    web_provenance(repository)  # interface construite depuis ce commit (KIT4-26)
    return make_kit(tmp_path, monkeypatch, name="kit-b", repository=repository)


def test_update_saves_verifies_and_stops_the_current_version_before_copying(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    first = context(kit)
    assert install(first, destination, data_root) == 0
    old = pointer_of(destination)["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    new_id = manifest_of(kit_b)["kit_id"]
    runner = ProgrammeSimule(watch=destination / new_id)
    ctx = context(kit_b, runner=runner)
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    before_copy = [(name, command) for name, command, exists in runner.calls if not exists]
    # Estimation de la sauvegarde (emplacements du profil), instance en marche, puis sauvegarde vérifiée et arrêt.
    assert before_copy == [(old["kit_id"], "paths"), (old["kit_id"], "status"), (old["kit_id"], "status"), (old["kit_id"], "up"),
                           (old["kit_id"], "backup"), (old["kit_id"], "verify"), (old["kit_id"], "down")]
    # status juste avant la bascule : aucune instance relancée sur les données depuis l'arrêt.
    assert runner.commands(new_id) == ["bootstrap", "compileall", "doctor", "status", "up", "doctor", "selftest", "open"]
    pointer = pointer_of(destination)
    assert pointer["current"]["kit_id"] == new_id and pointer["previous"]["kit_id"] == old["kit_id"]
    assert pointer["current"]["profile"] == old["profile"] and (Path(pointer["current"]["backup"]) / "config/profile.yaml").is_file()
    assert f"version {new_id}." in (destination / "atelier").read_text(encoding="utf-8")


PRINCIPAL_KEPT = ("Profil principal conservé : qwen3.5:2b, choix de cette installation, non converti. Le modèle par défaut de cette "
                  "version est qwen3.5:4b ; pour l'adopter durablement : « atelier modele qwen3.5:4b » ; pour une seule ouverture : "
                  "« atelier arreter », puis « atelier ouvrir --modele qwen3.5:4b ».")


def test_an_update_keeps_a_2b_principal_profile_and_says_how_to_use_the_4b(kit, tmp_path, monkeypatch):
    # W045 : le nouveau défaut ne convertit jamais le profil principal d'une installation existante (choix de l'utilisateur).
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--model", "qwen3.5:2b", "--no-start") == 0
    old = pointer_of(destination)["current"]
    principal = (data_root / "profile.yaml").read_bytes()
    assert old["model"] == "qwen3.5:2b" and old["profile"] == str(data_root / "profile.yaml")
    ctx = context(second_kit(tmp_path, monkeypatch))
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == 0, screen(ctx)
    current = pointer_of(destination)["current"]
    assert current["model"] == "qwen3.5:2b" and current["profile"] == old["profile"] and current["profiles"] == old["profiles"]
    assert (data_root / "profile.yaml").read_bytes() == principal
    assert f"[info] Modèle principal : {PRINCIPAL_KEPT}" in ctx.out.getvalue()
    report = json.loads(next(data_root.glob("update-*.json")).read_text(encoding="utf-8"))
    assert report["principal_model"] == {"model": "qwen3.5:2b", "kit_default": "qwen3.5:4b", "converted": False,
                                         "switch": ["atelier arreter", "atelier ouvrir --modele qwen3.5:4b"],
                                         "persistent": "atelier modele qwen3.5:4b"}
    assert [(step["status"], step["detail"]) for step in report["steps"] if step["step"] == "modele"] == [("info", PRINCIPAL_KEPT)]


def test_an_update_of_a_4b_principal_has_no_model_note(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    ctx = context(second_kit(tmp_path, monkeypatch))
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == 0, screen(ctx)
    assert "[info] Modèle principal" not in ctx.out.getvalue() and "Profil principal conservé" not in ctx.out.getvalue()
    report = json.loads(next(data_root.glob("update-*.json")).read_text(encoding="utf-8"))
    assert report["principal_model"] == {"model": "qwen3.5:4b", "kit_default": "qwen3.5:4b", "converted": False, "switch": None,
                                         "persistent": None}


def test_an_update_to_a_kit_without_the_2b_refuses_a_2b_principal(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--model", "qwen3.5:2b", "--no-start") == 0
    before = (destination / "installation.json").read_bytes()
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'suivante'\n")
    git(repository, "commit", "-q", "-am", "version suivante")
    web_provenance(repository)  # interface construite depuis ce commit (KIT4-26)
    four = make_kit(tmp_path, monkeypatch, name="kit-4b", repository=repository, models=("4b",))
    ctx = context(four)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == linux_install.EXIT_REFUSED
    update = linux_install.installer_command(four, "update", "--destination", str(destination), "--model", "qwen3.5:4b")
    assert ("Le modèle du profil en place (qwen3.5:2b) n'est pas livré par ce kit ; rien n'a été installé. Pour adopter le modèle livré "
            f"pendant la mise à jour : « {update} » ; ou d'abord dans la version en place : « atelier modele qwen3.5:4b », puis relancer la "
            "mise à jour ; ou employer un kit qui livre qwen3.5:2b (fabrication par défaut : --models 4b,2b).") in ctx.err.getvalue()
    assert ctx.runner.calls == [] and (destination / "installation.json").read_bytes() == before


@pytest.mark.parametrize(("failure", "expected"), [
    ({("up"): {"status": "failed", "message": "port occupé"}}, ["paths", "status", "status", "up"]),
    # S3-08 : l'instance démarrée pour la sauvegarde est arrêtée quand la sauvegarde n'est pas vérifiée.
    ({("verify"): {"state": "failed", "message": "empreinte"}}, ["paths", "status", "status", "up", "backup", "verify", "down"]),
])
def test_an_update_without_a_verified_backup_copies_nothing(kit, tmp_path, monkeypatch, failure, expected):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    before = (destination / "installation.json").read_bytes()
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b, runner=ProgrammeSimule(results=failure))
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_ERROR
    assert ctx.runner.commands() == expected and "rien n'a été installé" in ctx.err.getvalue().lower()
    assert (destination / "installation.json").read_bytes() == before and len([p for p in destination.iterdir() if p.is_dir()]) == 1


def test_a_failed_pointer_write_leaves_the_previous_pointer_and_no_temporary(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    before = (destination / "installation.json").read_bytes()
    real_replace = os.replace

    def failing_replace(source, target):
        if str(target).endswith("installation.json"):
            raise OSError("disque plein (simulé)")
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", failing_replace)
    pointer = json.loads(before)
    with pytest.raises(OSError, match="disque plein"):
        linux_install.switch(destination, pointer, None, pointer["current"], {"event": "essai"})
    assert (destination / "installation.json").read_bytes() == before
    assert sorted(path.name for path in destination.iterdir() if path.is_file()) == [
        linux_install.LOCK, "atelier", "atelier-documentaire.svg", "installation.json"]


def test_rollback_before_any_start_only_switches_back(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    old = pointer_of(destination)["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    updater = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], updater) == 0
    # Dernier superviseur sur les données : celui de la version en place, démarrée pour la sauvegarde.
    assert updater.runner.last_started == old["program"]
    ctx = context(kit, runner=ProgrammeSimule(last_started=updater.runner.last_started))
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 0, screen(ctx)
    assert ctx.runner.commands() == ["status", "status"]
    pointer = pointer_of(destination)
    assert pointer["current"]["kit_id"] == old["kit_id"] and pointer["current"]["profile"] == old["profile"]
    assert pointer["previous"]["rolled_back"] is True
    assert f"version {old['kit_id']}." in (destination / "atelier").read_text(encoding="utf-8")


def test_rollback_after_a_start_restores_the_backup_with_the_previous_version(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root) == 0
    old = pointer_of(destination)["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    updater = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], updater) == 0
    backup = pointer_of(destination)["current"]["backup"]
    runner = ProgrammeSimule(last_started=updater.runner.last_started)
    runner.running = dict(updater.runner.running)
    ctx = context(kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    new_id = manifest_of(kit_b)["kit_id"]
    assert [(name, command) for name, command, _ in runner.calls] == [
        (new_id, "status"), (new_id, "down"), (new_id, "paths"), (old["kit_id"], "restore"), (old["kit_id"], "ports"), (old["kit_id"], "paths"),
        (old["kit_id"], "derive")]
    restored = pointer_of(destination)["current"]
    assert restored["kit_id"] == old["kit_id"] and restored["profile"].endswith("restored-profile.yaml")
    assert Path(restored["data_root"]).name.startswith("donnees-retour-") and restored["restored_from"] == backup
    assert (data_root / "profile.yaml").exists()


def test_rollback_restores_when_the_supervisor_of_the_new_version_wrote_last_without_the_flag(kit, tmp_path, monkeypatch):
    # Version démarrée hors du lanceur (rag.sh up --profile …) : le pointeur l'ignore, l'état de l'instance le révèle.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(kit_b)) == 0
    new = pointer_of(destination)["current"]
    assert new["started_on_data"] is False
    ctx = context(kit, runner=ProgrammeSimule(last_started=new["program"]))
    assert linux_install.main(["rollback", "--destination", str(destination), "--restore-target", str(tmp_path / "retour"), "--oui"], ctx) == 0
    assert ctx.runner.commands() == ["status", "status", "paths", "restore", "ports", "paths", "derive"]
    assert pointer_of(destination)["current"]["data_root"] == str(tmp_path / "retour")


def test_rollback_without_backup_after_a_start_switches_nothing(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(kit_b)) == 0
    pointer = pointer_of(destination)
    pointer["current"].pop("backup")
    pointer["current"]["started_on_data"] = True
    (destination / "installation.json").write_text(json.dumps(pointer), encoding="utf-8")
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_REFUSED
    assert "aucune sauvegarde n'est associée" in ctx.err.getvalue()
    assert pointer_of(destination) == pointer


# --- Désinstallation ------------------------------------------------------------------------------------------------------

def installed(kit, tmp_path, *extra):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    ctx = context(kit)
    assert install(ctx, destination, data_root, *extra) == 0, screen(ctx)
    return destination, data_root, pointer_of(destination)["current"], ctx.runner


def uninstall(kit, destination, kit_id, runner=None):
    ctx = context(kit, runner=runner)
    return linux_install.main(["uninstall", "--destination", str(destination), "--kit-id", kit_id, "--oui"], ctx), ctx


def test_uninstall_stops_this_version_removes_it_without_following_links_and_keeps_the_data(kit, tmp_path):
    destination, data_root, current, runner = installed(kit, tmp_path)
    outside = write(tmp_path, "ailleurs/precieux.txt", "à garder")
    os.symlink(outside.parent, Path(current["program"]) / "lien-vers-ailleurs")
    code, ctx = uninstall(kit, destination, current["kit_id"], runner)
    assert code == 0, screen(ctx)
    # Deux profils (2B et 4B, mêmes données) : chacun contrôlé, l'instance de cette version arrêtée une fois.
    assert runner.commands()[-5:] == ["paths", "status", "down", "paths", "status"]
    assert not Path(current["program"]).exists() and outside.read_text(encoding="utf-8") == "à garder"
    assert (data_root / "profile.yaml").exists() and not (destination / "atelier").exists()
    pointer = pointer_of(destination)
    assert pointer["current"] is None and pointer["history"][-1]["event"] == "uninstall"
    assert list(destination.glob("uninstall-*.json"))


def test_uninstall_refuses_a_link_a_folder_without_markers_or_another_version(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    os.symlink(current["program"], destination / "alias")
    assert uninstall(kit, destination, "alias")[0] == linux_install.EXIT_REFUSED
    write(destination, "faux/README.md", "")
    code, ctx = uninstall(kit, destination, "faux")
    assert code == linux_install.EXIT_REFUSED and "kit-manifest.json absent" in ctx.err.getvalue()
    (destination / "faux/kit-manifest.json").write_text(json.dumps({"kit_id": "autre"}), encoding="utf-8")
    write(destination, "faux/SHA256SUMS", "")
    code, ctx = uninstall(kit, destination, "faux")
    assert code == linux_install.EXIT_REFUSED and "ne porte pas la version faux" in ctx.err.getvalue()
    assert Path(current["program"]).is_dir() and (destination / "faux/README.md").exists()


def test_uninstall_refuses_a_profile_that_writes_into_the_program(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    inside = {"app.data_dir": f"{current['program']}/.runtime/data", "runtime.backups_dir": "/ailleurs/backups"}
    code, ctx = uninstall(kit, destination, current["kit_id"], ProgrammeSimule(locations=inside))
    assert code == linux_install.EXIT_REFUSED and "écrit dans le dossier programme (app.data_dir" in ctx.err.getvalue()
    assert Path(current["program"]).is_dir() and (destination / "atelier").exists()


# --- Lanceur et état ------------------------------------------------------------------------------------------------------

def test_the_launcher_actions_always_use_a_profile_of_the_data_root(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    program = Path(current["program"])
    runner = ProgrammeSimule()
    ctx = context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--modele", "qwen3.5:2b", "--no-browser"], ctx) == 0
    assert "Lien à usage unique : http://127.0.0.1:8785/ouvrir#jeton" in ctx.out.getvalue()
    assert runner.commands() == ["status", "up", "open"] and runner.running[str(program)] == str(data_root / "profile-qwen3.5-2b.yaml")
    assert pointer_of(destination)["current"]["started_on_data"] is True
    for action, commands in (("arreter", ["down"]), ("diagnostic", ["status", "doctor"]), ("etat", ["status"]),
                             ("sauvegarder", ["status", "backup"]), ("journaux", ["logs"])):
        ctx = context(program, runner=ProgrammeSimule())
        if action == "sauvegarder":
            ctx.runner.running = {str(program): current["profile"]}  # sauvegarde : atelier démarré (REL-U03)
        assert linux_install.main(["run", "--destination", str(destination), action], ctx) == 0, (action, screen(ctx))
        assert ctx.runner.commands() == commands
        assert all(Path(profile).parent == data_root for profile in sum((ctx.runner.profiles_of(command) for command in commands), []))
    stale = context(kit)
    assert linux_install.main(["run", "--destination", str(destination)], stale) == linux_install.EXIT_REFUSED
    assert "Lanceur périmé" in stale.err.getvalue()


def test_status_reports_a_launcher_of_another_version(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination), "--json"], ctx) == 0
    assert json.loads(ctx.out.getvalue())["versions"] == [current["kit_id"]]
    (destination / "atelier").write_text("#!/bin/sh\n# version autre.\n", encoding="utf-8")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 1
    assert "lanceur absent ou d'une autre version" in ctx.out.getvalue()


# --- Revue de R26-KIT-04 : constats REL-U, S et QA ------------------------------------------------------------------------

def test_a_backup_requested_while_the_atelier_is_stopped_names_the_launcher_commands(kit, tmp_path):
    # REL-U03 : l'état est connu du lanceur ; jamais « rag up », commande absente d'une installation.
    destination, ctx = launcher_context(kit, tmp_path, tty=False)
    assert linux_install.main(["run", "--destination", str(destination), "sauvegarder"], ctx) == linux_install.EXIT_REFUSED
    assert "Arrêt : L'atelier est arrêté : l'ouvrir (« atelier ouvrir »), puis « atelier sauvegarder »." in ctx.err.getvalue()
    assert "rag up" not in screen(ctx) and "rag.sh" not in screen(ctx) and ctx.runner.commands() == ["status"]


def strip_desktop_integration(destination: Path, home: Path) -> None:
    """Installation faite par l'installateur de 78ec95c (R26-KIT-02, phase 1) : pointeur sans clé `menu`, sans entrée de
    menu ni commande `atelier`, et aucun registre."""
    pointer = pointer_of(destination)
    for key in ("menu", "menu_entry", "user_command"):
        pointer.pop(key, None)
    (destination / "installation.json").write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (applications(home) / "atelier-documentaire.desktop").unlink()
    (home / ".local/bin/atelier").unlink()
    shutil.rmtree(home / ".local/state")


def test_an_update_of_an_installation_without_desktop_integration_gives_runnable_commands(kit, tmp_path, monkeypatch, isolated_home):
    # REL-U04 : ni « atelier … » (commande absente du PATH), ni intégration créée sans le dire.
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start", "--model", "qwen3.5:2b")
    strip_desktop_integration(destination, isolated_home)
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == 0, screen(ctx)
    output = ctx.out.getvalue()
    launcher = destination / "atelier"
    assert f"« {launcher} modele qwen3.5:4b »" in output and f"« {launcher} arreter »" in output
    assert "« atelier " not in output
    program = destination / manifest_of(kit_b)["kit_id"]
    assert f"« {program}/installer.sh repair --menu »" in output
    report = json.loads(next(data_root.glob("update-*.json")).read_text(encoding="utf-8"))
    assert report["principal_model"]["persistent"] == f"{launcher} modele qwen3.5:4b"
    assert report["principal_model"]["switch"] == [f"{launcher} arreter", f"{launcher} ouvrir --modele qwen3.5:4b"]


def test_a_first_installation_says_how_to_update_one_made_elsewhere(kit, isolated_home):
    # REL-U04 : sans installation retrouvée, le récapitulatif dit comment viser une installation faite ailleurs.
    ctx = context(kit)
    assert linux_install.main(["--oui", "--no-start"], ctx) == 0, screen(ctx)
    assert (f"Installation existante : aucune trouvée (registre, emplacement par défaut) ; pour mettre à jour une installation faite "
            f"à un autre emplacement : « {kit}/installer.sh update --destination <dossier des versions> »") in ctx.out.getvalue()


def test_status_names_the_state_of_the_atelier_in_french(kit, tmp_path):
    # REL-U11 : « Instance : arrêté » faisait une faute d'accord.
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 0, screen(ctx)
    assert "État de l'atelier : arrêté" in ctx.out.getvalue() and "Instance : " not in ctx.out.getvalue()


def test_rollback_without_installation_says_no_rollback_is_possible(kit, tmp_path):
    (tmp_path / "vide").mkdir()
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(tmp_path / "vide")], ctx) == linux_install.EXIT_REFUSED
    assert f"Aucune installation dans {tmp_path / 'vide'} : aucun retour arrière possible." in ctx.err.getvalue()
    assert "rien à revenir" not in ctx.err.getvalue()


def test_the_model_command_without_a_model_shows_a_placeholder_to_replace(kit, tmp_path):
    # REL-U12 : le texte à remplacer n'est pas passé par shlex (« '<modèle>' »).
    destination, ctx = launcher_context(kit, tmp_path, tty=False)
    assert linux_install.main(["run", "--destination", str(destination), "modele"], ctx) == linux_install.EXIT_USAGE
    assert "« atelier modele <modèle> »" in ctx.err.getvalue() and "'<modèle>'" not in ctx.err.getvalue()


def test_an_instance_with_an_unknown_profile_names_the_launcher_stop_command(kit, tmp_path, monkeypatch):
    # REL-U12 : arrêt par le lanceur (supervisor.stop agit sur le dossier de données), pas « rag.sh down --profile <ce profil> ».
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    foreign = write(tmp_path, "ailleurs/profile.yaml", "schema_version: 2\n# profil inconnu de l'installation\n")
    runner = ProgrammeSimule(last_started=current["program"])
    runner.running = {current["program"]: str(foreign)}
    ctx = context(second_kit(tmp_path, monkeypatch), runner=runner)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == linux_install.EXIT_REFUSED
    errors = ctx.err.getvalue()
    assert "profil que l'installation ne connaît pas : l'arrêter (« atelier arreter »)" in errors and "rag.sh down" not in errors


def test_abandoning_the_volume_choice_writes_nothing_and_shows_the_refusal_once(kit, tmp_path, isolated_home):
    # REL-U14 : le refus affiché avant le choix n'est pas réimprimé sur la sortie d'erreur.
    volume = tmp_path / "disque"
    volume.mkdir()
    probe = PosteSimule(free={str(isolated_home): GIB, str(volume): 500 * GIB, "*": GIB}, mounts=[mount(str(volume))],
                        writable={str(volume)})
    ctx = context(kit, probe=probe, tty=True, answers=[""])
    assert linux_install.main(["--no-start"], ctx) == linux_install.EXIT_REFUSED
    assert ctx.err.getvalue() == "Arrêt : Abandon demandé : rien n'a été écrit.\n"
    assert screen(ctx).count("espace insuffisant") == 1 and not (isolated_home / ".local").exists() and ctx.runner.calls == []


def option_help(parser, command: str, option: str) -> str:
    sub = next(action.choices for action in parser._actions if isinstance(action, argparse._SubParsersAction))  # noqa: SLF001
    return next(action.help for action in sub[command]._actions if option in action.option_strings)  # noqa: SLF001


def test_help_shows_confirmation_options_only_where_something_is_confirmed(kit):
    # REL-U16 : status et verifier n'écrivent rien ; --modele accepté comme dans le lanceur ; --attendre complet.
    def help_of(command: str) -> str:
        ctx = context(kit)
        assert linux_install.main([command, "--aide"], ctx) == 0
        return ctx.out.getvalue()

    assert "--oui" not in help_of("status") and "--oui" not in help_of("verifier") and "--non-interactif" not in help_of("verifier")
    assert "--oui" in help_of("install") and "--oui" in help_of("uninstall")
    assert "--modele" in help_of("install") and "--modele" in help_of("update") and "--modele" in help_of("verifier")
    assert linux_install.parser(kit).parse_args(["install", "--modele", "qwen3.5:2b"]).model == "qwen3.5:2b"
    assert linux_install.parser(kit).parse_args(["update", "--modele", "qwen3.5:4b"]).model == "qwen3.5:4b"
    assert "journaux" in option_help(linux_install.build_parser(), "run", "--attendre")


def test_interrupting_the_launcher_says_the_atelier_may_still_change_state(kit, tmp_path):
    # REL-U17 : le superviseur, détaché, peut poursuivre son démarrage ou son arrêt.
    def interrupted(argv):
        raise KeyboardInterrupt

    destination, ctx = launcher_context(kit, tmp_path, tty=False, results={"up": interrupted})
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir"], ctx) == linux_install.EXIT_INTERRUPTED
    assert ("Commande interrompue : l'atelier peut continuer à démarrer ou à s'arrêter ; « atelier etat » l'indique."
            in ctx.err.getvalue()) and "Traceback" not in screen(ctx)


def test_update_verifies_the_files_it_runs_from_the_new_kit_before_any_derivation(kit, tmp_path, monkeypatch):
    # S01 : linux_profiles.py et les profils livrés du nouveau kit sont lus ou exécutés par la dérivation contrôlée ; ils sont
    # vérifiés avant, et aucune commande ne désigne un fichier de ce kit avant le refus.
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    kit_b = second_kit(tmp_path, monkeypatch)
    before = pointer_of(destination)
    for relative in ("tools/dist/linux_profiles.py", manifest_of(kit_b)["model_profiles"]["qwen3.5:2b"]):
        target = kit_b / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\n# altere\n")
        ctx = context(kit_b)
        code = linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx)
        assert code == linux_install.EXIT_REFUSED, screen(ctx)
        assert "Kit non conforme" in ctx.err.getvalue() and f"{relative} altéré" in ctx.err.getvalue()
        assert ctx.runner.calls == [] and not any(str(kit_b) in word for argv in ctx.runner.argvs for word in argv)
        assert pointer_of(destination) == before
        target.write_bytes(original)


def derivation_kit(tmp_path: Path) -> Path:
    """Dossier d'un nouveau kit réduit à ce que la dérivation contrôlée exécute : le vrai linux_profiles.py et les modules du
    dépôt qu'il importe (PRE_COPY_FILES)."""
    kit = tmp_path / "nouveau-kit"
    for relative in linux_install.PRE_COPY_FILES:
        write(kit, relative, (linux_kit.ROOT / relative).read_text(encoding="utf-8"))
    return kit


def injected(witness: Path) -> str:
    """Code d'un module injecté : laisse un témoin, puis arrête le processus (code 99)."""
    return f"open({str(witness)!r}, 'w').write('exécuté')\nraise SystemExit(99)\n"


def read_profile_with_the_kit_code(kit: Path) -> dict:
    """`linux_profiles.py paths` du kit `kit`, lancé comme la dérivation contrôlée d'une mise à jour : par le vrai exécuteur de
    commandes, avec l'environnement Python du dépôt (celui d'une version en place : PyYAML) et un profil réel du dépôt."""
    ctx = context(kit, runner=linux_install.SystemRunner())
    return linux_install.profiles_tool(ctx, Path(sys.executable), kit, "paths", "--profile", str(linux_kit.ROOT / "config/local16-4b.yaml"),
                                       cwd=kit)


def test_a_module_added_at_the_root_of_a_new_kit_is_never_imported_by_the_derivation(tmp_path):
    # R2-03 (b) : la racine du kit vient après la bibliothèque standard et site-packages (sys.path.append) : un yaml.py ajouté
    # n'est jamais importé à la place de PyYAML par linux_profiles.py.
    kit = derivation_kit(tmp_path)
    witness = tmp_path / "temoin"
    write(kit, "yaml.py", injected(witness))
    result = read_profile_with_the_kit_code(kit)
    assert not witness.exists(), result
    assert result["status"] == "read" and result["ports"]["app"] == 8785, result


def test_bytecode_added_to_a_new_kit_is_never_read_by_the_derivation(tmp_path):
    # R2-03 (c) : un .pyc « unchecked-hash » de __pycache__ remplacerait le module vérifié ; le code d'un autre dossier que
    # celui de l'environnement (nouveau kit) est lancé avec -X pycache_prefix=/dev/null : aucun bytecode n'est lu.
    import py_compile

    kit = derivation_kit(tmp_path)
    witness = tmp_path / "temoin"
    source = tmp_path / "source-injectee" / "artifacts.py"
    write(source.parent, source.name, injected(witness))
    py_compile.compile(str(source), cfile=str(kit / "services/runtime/__pycache__" / f"artifacts.{sys.implementation.cache_tag}.pyc"),
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH, doraise=True)
    # Témoin : le même script, lancé sans cette option, exécute ce bytecode.
    direct = subprocess.run([sys.executable, "-B", "-I", str(kit / "tools/dist/linux_profiles.py"), "paths", "--profile",
                             str(linux_kit.ROOT / "config/local16-4b.yaml")], capture_output=True, text=True, timeout=120, check=False)
    assert direct.returncode == 99 and witness.exists(), direct.stdout + direct.stderr
    witness.unlink()
    result = read_profile_with_the_kit_code(kit)
    assert not witness.exists(), result
    assert result["status"] == "read", result


def test_the_program_own_profiles_tool_keeps_its_bytecode(tmp_path):
    # Le programme installé garde son bytecode (compileall) : l'option n'est donnée qu'au code d'un autre dossier.
    runner = ProgrammeSimule(results={"paths": {"status": "read"}})
    ctx = context(tmp_path / "kit", runner=runner)
    program = tmp_path / "programme"
    linux_install.profiles_tool(ctx, linux_install.venv_python(program), program, "paths", "--profile", "p.yaml", cwd=program)
    linux_install.profiles_tool(ctx, linux_install.venv_python(program), tmp_path / "kit", "paths", "--profile", "p.yaml", cwd=program)
    own, foreign = runner.argvs
    assert "-X" not in own and foreign[1:5] == ["-B", "-I", "-X", "pycache_prefix=/dev/null"]


@pytest.mark.parametrize("added", [f"services/runtime/artifacts{importlib.machinery.EXTENSION_SUFFIXES[0]}",
                                   "services/runtime/platforms.abi3.so", "services/__init__.pyc", "services/runtime/supervisor.pyc"])
def test_update_refuses_a_compiled_module_added_where_the_derivation_imports(kit, tmp_path, monkeypatch, added):
    # R2-03 : un module compilé (.so) est chargé avant le .py vérifié du même nom, un bytecode sans source (.pyc) tient lieu de
    # module : absents de SHA256SUMS dans services/ ou services/runtime/, ils arrêtent la mise à jour avant toute dérivation.
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    kit_b = second_kit(tmp_path, monkeypatch)
    before = pointer_of(destination)
    write(kit_b, added, "\x7fELF ou bytecode ajouté")
    ctx = context(kit_b)
    code = linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx)
    assert code == linux_install.EXIT_REFUSED, screen(ctx)
    assert "Kit non conforme" in ctx.err.getvalue() and f"{added} ajouté, absent de SHA256SUMS" in ctx.err.getvalue()
    assert ctx.runner.calls == [] and pointer_of(destination) == before


DERIVATION_PACKAGE_FOLDERS = ["services/runtime/artifacts/__init__.py", "services/runtime/platforms/__init__.py",
                              "services/runtime/accelerator/__init__.py"]


@pytest.mark.parametrize("added", DERIVATION_PACKAGE_FOLDERS)
def test_a_package_folder_added_to_a_new_kit_is_never_imported_by_the_derivation(tmp_path, added):
    # QA3-01, S3-01 (b), scénario des relecteurs : un dossier de paquet homonyme d'un module vérifié est trouvé avant lui par
    # une recherche par nom (PEP 420). linux_profiles.py, lancé comme la dérivation contrôlée, charge ses modules
    # services.runtime par leur chemin : le paquet ajouté n'est jamais exécuté.
    kit = derivation_kit(tmp_path)
    witness = tmp_path / "temoin"
    write(kit, added, injected(witness))
    result = read_profile_with_the_kit_code(kit)
    assert not witness.exists(), result
    assert result["status"] == "read" and result["ports"]["app"] == 8785, result


@pytest.mark.parametrize("added", ["services/runtime/artifacts/__init__.py", "services/runtime/platforms/__init__.pyc",
                                   f"services/runtime/accelerator/__init__{importlib.machinery.EXTENSION_SUFFIXES[0]}",
                                   "services/autre/__init__.py"])
def test_update_refuses_a_package_folder_added_where_the_derivation_imports(kit, tmp_path, monkeypatch, added):
    # QA3-01, S3-01 (c) : la mise à jour vers un kit qui contient un dossier de paquet ajouté dans services/ ou
    # services/runtime/ rendait le code 0 en le signalant seulement ; elle est refusée avant toute dérivation.
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    kit_b = second_kit(tmp_path, monkeypatch)
    before = pointer_of(destination)
    write(kit_b, added, "\x7fELF ou module ajouté")
    ctx = context(kit_b)
    code = linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx)
    assert code == linux_install.EXIT_REFUSED, screen(ctx)
    assert "Kit non conforme" in errors_of(ctx) and f"{added} ajouté, absent de SHA256SUMS" in errors_of(ctx)
    assert ctx.runner.calls == [] and pointer_of(destination) == before


def test_the_files_verified_before_the_copy_cover_what_the_derivation_loads(tmp_path):
    """S01 : fermeture réelle des imports de `linux_profiles.py derive --check` (script du dépôt, Python du dépôt en -I) :
    chaque module du dépôt chargé figure dans PRE_COPY_FILES, vérifiés avant toute exécution sur un nouveau kit."""
    program = tmp_path / "programme"
    profiles = {"qwen3.5:4b": "config/local16-4b.yaml", "qwen3.5:2b": "config/local16.yaml"}
    for relative in profiles.values():
        write(program, relative, (linux_kit.ROOT / relative).read_text(encoding="utf-8"))
    write(program, "kit-manifest.json", json.dumps({"model_profiles": profiles}))
    root = str(linux_kit.ROOT)
    argv = ["linux_profiles.py", "derive", "--like", str(program / profiles["qwen3.5:4b"]), "--model", "qwen3.5:2b", "--program",
            str(program), "--output", str(tmp_path / "derive.yaml"), "--check"]
    probe = ("import json, runpy, sys\n"
             f"sys.argv = {argv!r}\n"
             "code = 0\n"
             "try:\n"
             f"    runpy.run_path({str(REAL_PROFILES_SCRIPT)!r}, run_name='__main__')\n"
             "except SystemExit as exit_:\n"
             "    code = exit_.code\n"
             f"root = {root!r}\n"
             "files = sorted({module.__file__[len(root) + 1:] for module in list(sys.modules.values())\n"
             "                if (getattr(module, '__file__', None) or '').startswith(root + '/') and '/.venv/' not in module.__file__})\n"
             "print(json.dumps({'code': code, 'files': files}))\n")
    result = subprocess.run([sys.executable, "-B", "-I", "-c", probe], capture_output=True, text=True, check=False, timeout=120)
    found = json.loads(result.stdout.strip().splitlines()[-1])
    assert found["code"] == 0, result.stdout + result.stderr
    assert "tools/dist/linux_profiles.py" in linux_install.PRE_COPY_FILES
    assert set(found["files"]) <= set(linux_install.PRE_COPY_FILES), found["files"]


def test_the_kit_of_the_previous_version_offers_the_rollback_instead_of_an_update(kit, tmp_path, monkeypatch, isolated_home):
    # S02 : relancer le kit de la version précédente n'est pas une mise à jour, et la seule commande proposée ne retire pas
    # la cible du retour arrière.
    assert linux_install.main(["--oui", "--no-start"], context(kit)) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["--oui", "--no-start"], context(kit_b)) == 0
    destination = default_paths(isolated_home)[0]
    before = pointer_of(destination)
    program_b, old = destination / manifest_of(kit_b)["kit_id"], manifest_of(kit)["kit_id"]
    for argv in (["--oui", "--no-start"], ["update", "--oui", "--no-start"]):
        ctx = context(kit)
        assert linux_install.main(argv, ctx) == linux_install.EXIT_REFUSED, screen(ctx)
        assert (f"La version {old} est la version précédente de {destination} : pour y revenir, « {program_b}/installer.sh rollback » ; "
                "rien n'a été modifié.") in ctx.err.getvalue()
        assert "uninstall" not in ctx.err.getvalue() and ctx.runner.calls == [] and pointer_of(destination) == before


@pytest.mark.parametrize("name", ["SIGHUP", "SIGTERM"])
def test_a_closed_terminal_or_a_session_end_during_the_copy_takes_the_interruption_path(kit, tmp_path, monkeypatch, name):
    # S03 (1) : fenêtre du terminal fermée (SIGHUP) ou fin de session (SIGTERM) pendant la copie.
    number = getattr(signal, name)
    data_root = write(tmp_path, "donnees/notes/a.txt", "document de l'utilisateur").parents[1]
    before = inventory(data_root)
    from tools.dist import build_kit

    real_stream_copy = build_kit.stream_copy
    copied = []

    def signalled_stream_copy(source, target):
        """Copie réelle ; au cinquième fichier, le signal est envoyé au processus, s'il a un gestionnaire (sinon il le tuerait)."""
        if len(copied) == 4:
            if signal.getsignal(number) in (signal.SIG_DFL, signal.SIG_IGN, None):
                raise AssertionError(f"aucun gestionnaire de {name} pendant l'installation")
            os.kill(os.getpid(), number)
        copied.append(target)
        return real_stream_copy(source, target)

    monkeypatch.setattr(build_kit, "stream_copy", signalled_stream_copy)
    handlers = (signal.getsignal(signal.SIGHUP), signal.getsignal(signal.SIGTERM))
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", data_root) == linux_install.EXIT_INTERRUPTED, screen(ctx)
    assert "Installation interrompue : copie partielle retirée, données inchangées" in ctx.err.getvalue() and "Traceback" not in screen(ctx)
    assert not (tmp_path / "programmes" / manifest_of(kit)["kit_id"]).exists() and inventory(data_root) == before
    assert (signal.getsignal(signal.SIGHUP), signal.getsignal(signal.SIGTERM)) == handlers


KILLED_INSTALL = """
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tests.unit.test_dist_linux_install import ProgrammeSimule, context
from tools.dist import build_kit, linux_install
kit, destination, data_root, step = sys.argv[2:6]
extra = sys.argv[6:]
def killed(*args):
    os.kill(os.getpid(), signal.SIGKILL)
results = {}
if step == "copie":
    real = build_kit.stream_copy
    copied = []
    def stream_copy(source, target):
        if len(copied) == 4:
            killed()
        copied.append(target)
        return real(source, target)
    build_kit.stream_copy = stream_copy
elif step == "apres-bascule":
    # Arrêt entre le rename(2) du pointeur et le retrait du marqueur : la version est désignée, le marqueur reste.
    real_switch = linux_install.switch
    def switch(*args, **kwargs):
        real_switch(*args, **kwargs)
        killed()
    linux_install.switch = switch
else:
    results[step] = killed
ctx = context(Path(kit), runner=ProgrammeSimule(results=results))
linux_install.main(["install", "--destination", destination, "--data-root", data_root, "--oui", "--no-start", *extra], ctx)
"""


def killed_install(kit: Path, destination: Path, data_root: Path, step: str, *extra: str) -> None:
    """Double d'un arrêt brutal (SIGKILL : manque de mémoire, coupure) : installation (ou reprise, avec `extra`) lancée dans un
    processus séparé, tué à l'étape `step` (`apres-bascule` : juste après la bascule) ; rien ne la nettoie, comme sur un poste
    réel."""
    result = subprocess.run([sys.executable, "-B", "-c", KILLED_INSTALL, str(linux_kit.ROOT), str(kit), str(destination), str(data_root),
                             step, *extra], capture_output=True, text=True, check=False, timeout=600, cwd=linux_kit.ROOT)
    assert result.returncode == -signal.SIGKILL, result.stdout + result.stderr


@pytest.mark.parametrize("then", ["retrait-complet", "destination-supprimee"])
def test_a_marker_left_after_the_switch_never_removes_the_user_profiles(kit, tmp_path, then):
    # R2-01 : arrêt brutal entre la bascule et le retrait du marqueur. La version a été désignée et a pu servir ; après son
    # retrait complet (pointeur et historique conservés) ou la suppression du dossier des versions (plus aucun historique),
    # le marqueur ne fait retirer aucun profil, ne contourne pas la garde de la reprise et le refus le nomme.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    killed_install(kit, destination, data_root, "apres-bascule")
    marker = data_root / linux_install.INSTALL_MARKER
    assert marker.is_file() and pointer_of(destination)["current"]["kit_id"] == manifest_of(kit)["kit_id"]
    if then == "retrait-complet":
        assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    else:
        shutil.rmtree(destination)
    a_backup(data_root)  # la reprise ne peut pas être refusée faute de sauvegarde : seul le marqueur l'arrête
    before = inventory(data_root)
    assert {"profile.yaml", "profile-qwen3.5-2b.yaml"} <= set(before)
    for extra in (["--reprendre-donnees"], []):
        ctx = context(kit)
        assert install(ctx, destination, data_root, "--no-start", *extra) == linux_install.EXIT_REFUSED, screen(ctx)
        err = ctx.err.getvalue()
        assert f"{marker} est périmé" in err and "profils et données sont laissés intacts" in err, err
        assert f"« rm -- {marker} »" in err and "jamais activée" not in screen(ctx)
        # Historique du pointeur conservé par le retrait : il fait foi ; sans lui, le drapeau écrit avant la bascule suffit.
        cause = (f"a activé cette version le 2026-10-06 20:00 UTC (historique de {destination / 'installation.json'})"
                 if then == "retrait-complet" else "s'est arrêtée au moment d'activer cette version, qui a pu servir depuis")
        assert cause in err, err
        assert inventory(data_root) == before and ctx.runner.calls == []


def test_a_fresh_install_marker_is_never_combined_with_a_reprise(kit, tmp_path):
    # R2-01 (2) : le marqueur d'une installation neuve désigne profile.yaml parmi ce qu'elle a créé ; une reprise ne le retire
    # jamais. Refus qui le nomme, puis la même installation, sans --reprendre-donnees, reprend l'installation interrompue.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    killed_install(kit, destination, data_root, "doctor")
    marker = data_root / linux_install.INSTALL_MARKER
    a_backup(data_root)
    before = inventory(data_root)
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start", "--reprendre-donnees") == linux_install.EXIT_REFUSED, screen(ctx)
    err = ctx.err.getvalue()
    assert f"{marker} signale une installation neuve interrompue" in err, err
    assert f"« {kit}/installer.sh install --destination {destination} --data-root {data_root} --oui --no-start »" in err, err
    assert inventory(data_root) == before and ctx.runner.calls == []
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == 0, screen(ctx)
    assert "Installation interrompue le " in ctx.out.getvalue() and not marker.exists()


def test_a_reprise_killed_without_cleanup_is_resumed_by_the_same_command(kit, tmp_path):
    # Reprise interrompue par un arrêt brutal : son marqueur ne désigne que ce qu'elle a créé (jamais profile.yaml) ; la même
    # commande retire son dossier de version, puis reprend les données, dont le profil reste octet pour octet.
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    a_backup(data_root)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    principal = (data_root / "profile.yaml").read_bytes()
    killed_install(kit, destination, data_root, "doctor", "--reprendre-donnees")
    assert (data_root / linux_install.INSTALL_MARKER).is_file() and Path(current["program"]).is_dir()
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start", "--reprendre-donnees") == 0, screen(ctx)
    assert "Reprise interrompue le " in ctx.out.getvalue() and not (data_root / linux_install.INSTALL_MARKER).exists()
    assert (data_root / "profile.yaml").read_bytes() == principal
    assert pointer_of(destination)["current"]["profile"] == str(data_root / "profile.yaml")


def test_the_marker_removal_is_made_durable_after_the_switch(kit, tmp_path, monkeypatch):
    # R2-01 (3) : le retrait du marqueur est suivi d'un fsync du dossier des données, comme la bascule l'est pour le pointeur.
    synced: list[tuple[Path, bool]] = []
    data_root = tmp_path / "donnees"

    def fsync_consigne(folder):
        """Espion de fsync_directory : dossier synchronisé, et présence du marqueur à cet instant."""
        synced.append((Path(folder), (data_root / linux_install.INSTALL_MARKER).exists()))

    monkeypatch.setattr(linux_install, "fsync_directory", fsync_consigne)
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", data_root, "--no-start") == 0, screen(ctx)
    assert (data_root, False) in synced


@pytest.mark.parametrize("step", ["copie", "doctor"])
def test_an_install_killed_without_cleanup_is_resumed_by_the_same_command(kit, tmp_path, step):
    # S03 (3) : le marqueur de l'installation en cours permet la reprise exacte : profils créés par elle et dossier incomplet
    # retirés après confirmation, puis installation normale.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    killed_install(kit, destination, data_root, step)
    program = destination / manifest_of(kit)["kit_id"]
    assert program.is_dir() and not (destination / "installation.json").exists()
    assert (data_root / linux_install.INSTALL_MARKER).is_file() and (data_root / "profile.yaml").exists() == (step == "doctor")
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == 0, screen(ctx)
    assert "Installation interrompue le " in ctx.out.getvalue()
    assert pointer_of(destination)["current"]["program"] == str(program) and (program / "kit-manifest.json").is_file()
    assert not (data_root / linux_install.INSTALL_MARKER).exists() and (data_root / "profile.yaml").is_file()


def test_an_orphan_version_folder_is_listed_and_removed_with_the_exact_command(kit, tmp_path):
    # S03 (2) : copie tuée sans marqueur (installateur antérieur, marqueur retiré) : dossier sans manifeste, ni désigné ni
    # listé jusqu'ici, et que uninstall refusait.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    kit_id = manifest_of(kit)["kit_id"]
    write(destination / kit_id, "services/api/main.py", "copie partielle\n")
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == linux_install.EXIT_REFUSED
    command = f"{kit}/installer.sh uninstall --destination {destination} --kit-id {kit_id}"
    assert f"« {command} »" in ctx.err.getvalue() and f"dossier incomplet {destination / kit_id}" in ctx.err.getvalue()
    status = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], status) == linux_install.EXIT_ERROR
    assert f"dossier incomplet {destination / kit_id}" in status.out.getvalue() and command in status.out.getvalue()
    removal = context(kit)
    assert linux_install.main([*shlex.split(command)[1:], "--oui"], removal) == 0, screen(removal)
    assert not (destination / kit_id).exists()
    assert install(context(kit), destination, data_root, "--no-start") == 0


def installer_commands(text: str) -> list[list[str]]:
    """Commandes de l'installateur citées entre guillemets français dans un message."""
    return [shlex.split(found) for found in re.findall(r"« ([^«»]*installer\.sh[^«»]*) »", text)]


def test_an_update_short_of_space_proposes_only_valid_commands_and_never_another_location(kit, tmp_path, monkeypatch):
    # S04 : --emplacement n'existe pas pour update, et une installation neuve ailleurs n'est pas la mise à jour.
    destination, _, _, _, _ = updated(kit, tmp_path, monkeypatch)
    from tests.unit.test_dist_linux_review import third_kit

    kit_c = third_kit(tmp_path, monkeypatch)
    needed = manifest_of(kit_c)["requirements"]["install_bytes_min"]
    probe = PosteSimule(free={str(destination): needed - GIB, "/mnt/grand": 900 * GIB, "*": needed - GIB}, mounts=[mount("/mnt/grand")],
                        writable={"/mnt/grand"})
    for argv in (["update", "--destination", str(destination), "--oui"], ["--oui"]):
        ctx = context(kit_c, probe=probe)
        assert linux_install.main(argv, ctx) == linux_install.EXIT_REFUSED, screen(ctx)
        errors = ctx.err.getvalue()
        assert "espace insuffisant" in errors and "--emplacement" not in errors and "/mnt/grand" not in errors
        commands = installer_commands(errors)
        assert commands, errors
        for words in commands:
            out, err = io.StringIO(), io.StringIO()
            try:
                args = linux_install.build_parser(streams=(out, err)).parse_args(words[1:])
            except SystemExit as error:
                raise AssertionError(f"« {shlex.join(words)} » refusée par l'analyseur : {err.getvalue()}") from error
            assert args.command in {"uninstall", "status"}, words
        assert ctx.runner.calls == []


def test_an_empty_ldd_list_still_verifies_tesseract_before_ldd(kit, tmp_path):
    # S05 : une seule liste de cibles pour la vérification ciblée et pour ldd (ldd(1) : jamais sur un exécutable non vérifié).
    with_manifest(kit, target={"ldd_checks": []})
    (kit / linux_kit.TESSERACT_BINARY).write_bytes(b"\x7fELF autre")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "Kit non conforme" in ctx.err.getvalue() and linux_kit.TESSERACT_BINARY in ctx.err.getvalue()
    assert ctx.probe.ldd_calls == [] and not (tmp_path / "programmes").exists()


def test_an_interruption_after_the_model_switch_keeps_the_designated_profile(kit, tmp_path, monkeypatch):
    # S07 : le profil dérivé que le pointeur désigne déjà n'est jamais retiré.
    destination, _, current, _ = installed(kit, tmp_path, "--no-start", "--model", "qwen3.5:2b")
    four = current["profiles"]["qwen3.5:4b"]
    Path(four).unlink()
    pointer = pointer_of(destination)
    pointer["current"]["profiles"] = {"qwen3.5:2b": current["profiles"]["qwen3.5:2b"]}
    (destination / "installation.json").write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def interrupted_registry(ctx, destination):
        """Double du registre : Ctrl+C juste après la bascule du pointeur."""
        raise KeyboardInterrupt

    monkeypatch.setattr(linux_install, "registry_record", interrupted_registry)
    ctx = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination), "modele", "qwen3.5:4b"], ctx) == linux_install.EXIT_INTERRUPTED
    assert pointer_of(destination)["current"]["profile"] == four and Path(four).is_file()
    assert ("Changement de modèle interrompu après la bascule : qwen3.5:4b est le modèle principal ; « atelier modele qwen3.5:2b » "
            "revient en arrière.") in ctx.err.getvalue()
    opener = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination)], opener) == 0, screen(opener)
    assert opener.runner.profiles_of("up") == [four]


def test_an_interrupted_full_uninstall_names_what_was_already_removed(kit, tmp_path, monkeypatch):
    # S08 : une version déjà retirée et le pointeur modifié ne sont pas « avant toute suppression ».
    destination, data_root, first, second, kit_b = updated(kit, tmp_path, monkeypatch)

    def interrupted_status(argv):
        raise KeyboardInterrupt

    ctx = context(kit_b, runner=ProgrammeSimule(results={(second["kit_id"], "status"): interrupted_status}))
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], ctx) == linux_install.EXIT_INTERRUPTED
    errors = ctx.err.getvalue()
    assert "avant toute suppression" not in errors and "données conservées" in errors
    assert f"versions déjà retirées : {first['kit_id']} ; non retirées : {second['kit_id']}" in errors
    assert f"« {second['program']}/installer.sh uninstall --tout »" in errors
    assert not Path(first["program"]).exists() and Path(second["program"]).is_dir() and (data_root / "profile.yaml").is_file()


@pytest.mark.parametrize("fstype", ["tmpfs", "ramfs", "overlay"])
@pytest.mark.parametrize("target", ["donnees", "programmes"])
def test_a_volatile_data_root_or_destination_is_refused(kit, tmp_path, fstype, target):
    # S09 : documents, index et sauvegardes perdus au redémarrage.
    probe = PosteSimule(fstype={str(tmp_path / target): fstype, "*": "ext4"}, device={str(tmp_path / "donnees"): "0:40", "*": "179:1"})
    ctx = context(kit, probe=probe)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert f"volume non persistant ({fstype})" in ctx.err.getvalue() and ctx.runner.calls == []


@pytest.mark.parametrize(("name", "content"), [("atelier", "#!/bin/sh\necho mon script\n"),
                                               ("atelier-documentaire.svg", "<svg><!-- icône personnelle --></svg>\n")],
                         ids=["lanceur", "icone"])
def test_a_foreign_launcher_or_icon_in_the_destination_is_refused(kit, tmp_path, name, content):
    # S10 : un fichier personnel du même nom n'est jamais remplacé.
    destination = tmp_path / "mon-dossier"
    mine = write(destination, name, content)
    ctx = context(kit)
    assert install(ctx, destination, tmp_path / "donnees", "--no-start") == linux_install.EXIT_REFUSED
    assert f"{mine} existe et n'appartient pas à l'atelier — le déplacer, ou choisir un autre dossier" in ctx.err.getvalue()
    assert mine.read_text(encoding="utf-8") == content and ctx.runner.calls == []


def test_repair_of_a_mistyped_destination_creates_nothing(kit, tmp_path):
    # S11 : ni dossier ni verrou hors des emplacements de l'atelier.
    ctx = context(kit)
    assert linux_install.main(["repair", "--destination", str(tmp_path / "erreur/programme")], ctx) == linux_install.EXIT_REFUSED
    assert not (tmp_path / "erreur").exists() and "rien à réparer" in ctx.err.getvalue()


@pytest.mark.parametrize("python", [{"key": "../../../../evasion", "executable": f".runtime/python/{PYTHON_KEY}/bin/python3.12"},
                                    {"key": "autre", "executable": f".runtime/python/{PYTHON_KEY}/bin/python3.12"},
                                    {"key": "..", "executable": ".runtime/python/../bin/python3.12"}],
                         ids=["cle-sortante", "cle-differente", "point-point"])
def test_a_forged_python_key_is_refused_before_any_use(kit, tmp_path, python):
    # S13 : python.key devient un chemin (compileall, préfixe réécrit) : validé comme le composant de l'exécutable.
    with_manifest(kit, python=python)
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == linux_install.EXIT_REFUSED
    assert "kit-manifest.json non conforme (" in ctx.err.getvalue() and "python.key" in ctx.err.getvalue()
    assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists()


def test_the_real_copy_reports_its_progress_up_to_100_percent(kit, tmp_path):
    # QA-12 : sans double, la copie du fabricant (linux_kit.install_copy) fournit la progression jusqu'à 100 %.
    assert linux_install.accepts(linux_kit.install_copy, "progress")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, screen(ctx)
    percents = [int(value) for value in re.findall(r"^Copie : (\d+) %", ctx.out.getvalue(), flags=re.M)]
    assert percents and percents == sorted(percents) and percents[-1] == 100 and len(percents) <= 10


# --- Revue 3 de R26-KIT-04 : constats de l'installateur ------------------------------------------------------------------


def output_of(ctx) -> str:
    """Sortie standard captée d'un contexte d'essai (StringIO)."""
    return ctx.out.getvalue()


def errors_of(ctx) -> str:
    """Sortie d'erreur captée d'un contexte d'essai (StringIO)."""
    return ctx.err.getvalue()

def test_the_test_context_refuses_the_real_account(kit, monkeypatch):
    # QA3-02, U3-12, S3-05 : le 7 octobre à 05:26 UTC, un aperçu lancé sans la fixture isolated_home a écrit le registre du
    # compte réel. `context` (donc installed et killed_install) refuse un tel environnement avant toute commande.
    monkeypatch.setenv("HOME", str(ACCOUNT_HOME))
    with pytest.raises(RuntimeError, match="sans HOME isolé : il écrirait dans le compte réel"):
        context(kit)


PREVIEW = """
import pytest

from tests.unit.test_dist_linux_install import context, installed, make_kit
from tools.dist import linux_install


@pytest.fixture
def kit(tmp_path, monkeypatch):
    return make_kit(tmp_path, monkeypatch)


def test_apercu(kit, tmp_path):
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit))
"""


def test_a_preview_outside_the_test_tree_is_refused_like_the_one_of_october_7(tmp_path):
    # QA3-02, scénario rejoué : aperçu écrit hors du dépôt, qui importe les doubles sans la fixture isolated_home et lancé par
    # pytest avec le HOME du compte (ici un compte sentinelle, déclaré protégé). Le 7 octobre, il a inscrit puis retiré une
    # installation dans le registre réel ; `context` le refuse désormais avant toute écriture.
    sentinel = tmp_path / "compte-sentinelle"
    sentinel.mkdir()
    preview = tmp_path / "apercu" / "test_apercu.py"
    write(preview.parent, preview.name, PREVIEW)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("XDG_")}
    environment.update(HOME=str(sentinel), ATELIER_ESSAIS_COMPTES_PROTEGES=str(sentinel), PYTHONUTF8="1")
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(linux_kit.ROOT), str(preview)],
                            cwd=linux_kit.ROOT, env=environment, capture_output=True, text=True, timeout=600, check=False)
    assert not (sentinel / ".local").exists(), result.stdout[-3000:]
    assert result.returncode == 1 and "sans HOME isolé : il écrirait dans le compte réel" in result.stdout, result.stdout[-3000:]


def test_the_test_context_refuses_xdg_folders_of_the_real_account(kit, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(ACCOUNT_HOME / ".local/state"))
    with pytest.raises(RuntimeError, match="registre"):
        context(kit)


def test_the_session_guard_refuses_a_write_under_the_real_account(garde_du_compte):
    # QA3-02 : garde de tests/unit/conftest.py, active dans toute la session. L'événement d'audit est émis seul (sys.audit) :
    # aucune écriture n'a lieu, ni avant ni après la correction.
    target = ACCOUNT_HOME / ".local/state/atelier-documentaire/sonde-de-la-garde.json"
    start = len(garde_du_compte.violations)
    with pytest.raises(PermissionError, match="écriture sous le compte réel refusée"):
        sys.audit("open", str(target), "w", os.O_WRONLY | os.O_CREAT)
    assert garde_du_compte.violations[start:] == [f"open {os.path.realpath(target)}"]
    del garde_du_compte.violations[start:]  # constat attendu de cet essai, retiré avant le contrôle de fin d'essai


def test_the_session_guard_watches_every_writing_event(garde_du_compte, tmp_path):
    # QA4-01 (4) : arguments sous la forme que CPython 3.12.14 émet (dir_fd = -1 sans dir_fd, None pour shutil.rmtree),
    # relevée par le crochet d'observation de test_the_session_guard_flags_every_event_in_the_form_cpython_emits.
    home = tmp_path / "compte"
    depot = home / "Bureau/depot"
    garde = type(garde_du_compte)(home, allowed=(depot,))
    writes: list[tuple[str, tuple[object, ...]]] = [("open", (str(home / ".local/state/registre.json"), "w", 0)), ("open", (str(home / "x"), None, os.O_WRONLY | os.O_CREAT)),
              ("os.mkdir", (str(home / ".local/bin"), 0o700, -1)), ("os.rename", (str(tmp_path / "a"), str(home / "b"), -1, -1)),
              ("os.remove", (str(home / "c"), -1)), ("os.rmdir", (str(home / "d"), -1)), ("os.symlink", ("cible", str(home / "lien"), -1)),
              ("os.chmod", (str(home / ".local/bin"), 0o555, -1)), ("shutil.rmtree", (str(home / "r"), None)),
              ("shutil.copyfile", (str(tmp_path / "s"), str(home / "t"))), ("tempfile.mkstemp", (str(home / "u"),)),
              ("sqlite3.connect", (str(home / "base.sqlite3"),))]
    for event, args in writes:
        with pytest.raises(PermissionError):
            garde(event, args)
    allowed: list[tuple[str, tuple[object, ...]]] = [("open", (str(home / ".bashrc"), "r", os.O_RDONLY)), ("open", (str(depot / "x"), "w", 0)),
                        ("open", (str(tmp_path / "ailleurs"), "w", 0)), ("open", (3, "w", 0)),
                        ("os.symlink", (str(home / "cible"), str(tmp_path / "lien"), -1)), ("sqlite3.connect", (":memory:",)),
                        ("os.listdir", (str(home),))]
    for event, args in allowed:
        garde(event, args)
    assert len(garde.violations) == len(writes)


def test_the_session_guard_lets_relative_operations_outside_the_account_proceed(tmp_path, monkeypatch):
    # QA4-01 (3) : sans dir_fd, CPython 3.12.14 émet dir_fd = -1 (et non None) pour os.mkdir, os.remove, os.rmdir, os.chmod,
    # os.chown et os.utime. La garde résolvait alors un chemin relatif par /proc/self/fd/-1 : FileNotFoundError, opération
    # interrompue dans tout le processus de pytest, même sous tmp_path. Garde de la session active, de vraies opérations
    # relatives sous tmp_path aboutissent.
    work = tmp_path / "relatif"
    work.mkdir()
    monkeypatch.chdir(work)
    os.mkdir("x")
    os.makedirs("a/b")
    Path("f").write_text("contenu", encoding="utf-8")
    os.chmod("f", 0o600)
    os.chown("f", os.getuid(), os.getgid())
    os.utime("f")
    os.rename("f", "g")
    os.symlink("g", "h")
    os.link("g", "k")
    os.remove("h")
    os.unlink("k")
    os.truncate("g", 0)
    os.rmdir("x")
    shutil.rmtree("a")
    Path("p").mkdir()
    Path("p").rmdir()
    assert sorted(os.listdir(".")) == ["g"] and Path("g").stat().st_size == 0


# Double CrochetObservateur : crochet d'audit qui relève, sans rien interdire, les événements nommés en argv[1] pendant le
# code d'argv[2], puis les rend en JSON. Un crochet d'audit ne se retire pas : il ne tourne que dans un processus séparé.
OBSERVER = """
import json, sys
names, seen = set(json.loads(sys.argv[1])), []
def observe(event, args):
    if event in names:
        seen.append([event, [arg if isinstance(arg, (str, int, type(None))) else repr(arg) for arg in args]])
sys.addaudithook(observe)
exec(sys.argv[2])
print(json.dumps(seen))
"""
# Écritures de toutes les familles surveillées par la garde, chemins relatifs (préfixe vide) ou absolus.
WRITING_CODE = """
import os, shutil, sqlite3, tempfile
base = {base!r}
p = lambda name: os.path.join(base, name) if base else name
open(p("f"), "w").close()
os.close(os.open(p("o"), os.O_WRONLY | os.O_CREAT, 0o600))
os.mkdir(p("d"))
os.makedirs(p("m/n"))
os.chmod(p("f"), 0o600)
os.chown(p("f"), os.getuid(), os.getgid())
os.utime(p("f"))
os.truncate(p("f"), 0)
os.rename(p("f"), p("g"))
os.symlink("g", p("h"))
os.link(p("g"), p("k"))
os.remove(p("h"))
os.unlink(p("k"))
os.rmdir(p("d"))
for action in (lambda: os.setxattr(p("g"), "user.essai", b"1"), lambda: os.removexattr(p("g"), "user.essai")):
    try:
        action()
    except OSError:
        pass
shutil.copyfile(p("g"), p("c"))
shutil.copymode(p("g"), p("c"))
shutil.copystat(p("g"), p("c"))
shutil.move(p("c"), p("v"))
shutil.rmtree(p("m"))
os.mkdir(p("t"))
os.close(tempfile.mkstemp(dir=p("t"))[0])
tempfile.mkdtemp(dir=p("t"))
sqlite3.connect(p("base.sqlite3")).close()
"""


# Rang des arguments dir_fd des événements d'écriture (table des événements d'audit, Python 3.12).
DIR_FD_ARGUMENTS = {"os.mkdir": (2,), "os.remove": (1,), "os.rmdir": (1,), "os.chmod": (2,), "os.chown": (3,), "os.utime": (3,),
                    "os.rename": (2, 3), "os.symlink": (2,), "os.link": (2, 3), "shutil.rmtree": (1,)}


def observed_writes(names: list[str], code: str, cwd: Path) -> list[tuple[str, tuple[object, ...]]]:
    """Événements d'écriture tels que CPython les émet pour `code` (double CrochetObservateur, processus séparé)."""
    completed = subprocess.run([sys.executable, "-B", "-I", "-c", OBSERVER, json.dumps(names), code], cwd=cwd, capture_output=True,
                               text=True, timeout=60, check=True)
    return [(event, tuple(args)) for event, args in json.loads(completed.stdout)]


def child_dir_fd(event: str, args: tuple[object, ...]) -> bool:
    """Événement qui porte un descripteur de dossier réel du processus enfant (shutil.rmtree en interne) : sans objet ici."""
    values = [args[index] for index in DIR_FD_ARGUMENTS.get(event, ()) if index < len(args)]
    return any(isinstance(value, int) and value >= 0 for value in values)


# Familles d'événements d'écriture que la garde doit surveiller (docstring de tests/unit/conftest.py ; table des événements
# d'audit de Python 3.12), écrites ici indépendamment de WRITE_EVENTS : un événement retiré de la garde fait échouer l'essai
# (QA5-04 ; le relevé seul suivait WRITE_EVENTS et laissait passer le retrait de shutil.move, os.truncate, tempfile.mkdtemp,
# os.setxattr, os.removexattr, shutil.copymode ou shutil.copystat).
GUARDED_EVENTS = {"open", "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink", "os.link", "os.chmod", "os.chown", "os.utime",
                  "os.truncate", "os.setxattr", "os.removexattr", "shutil.rmtree", "shutil.copyfile", "shutil.copymode", "shutil.copystat",
                  "shutil.move", "tempfile.mkstemp", "tempfile.mkdtemp", "sqlite3.connect"}


@pytest.mark.parametrize("form", ["absolu", "relatif"])
def test_the_session_guard_flags_every_event_in_the_form_cpython_emits(garde_du_compte, tmp_path, monkeypatch, form):
    # QA4-01 (4) : la garde est alimentée par les événements que CPython émet réellement, relevés dans un processus séparé ;
    # chaque famille surveillée est refusée sous le compte simulé, chemins absolus ou relatifs (dir_fd = -1), et rien n'est
    # refusé quand le dossier courant est hors du compte.
    assert {"open", *sys.modules[type(garde_du_compte).__module__].WRITE_EVENTS} == GUARDED_EVENTS
    watched = GUARDED_EVENTS
    home = tmp_path / "compte"
    work = home / "travail"
    work.mkdir(parents=True)
    events = observed_writes(sorted(watched), WRITING_CODE.format(base=str(work) if form == "absolu" else ""), work)
    assert {event for event, _ in events} == watched, events
    replayed = [(event, args) for event, args in events if not child_dir_fd(event, args)]
    monkeypatch.chdir(work)
    garde = type(garde_du_compte)(home)
    refused = set()
    for event, args in replayed:
        try:
            garde(event, args)
        except PermissionError:
            refused.add(event)
    assert refused == watched
    if form == "relatif":
        elsewhere = type(garde_du_compte)(tmp_path / "autre-compte")
        for event, args in replayed:
            elsewhere(event, args)
        assert elsewhere.violations == []


def test_the_session_guard_resolves_every_dir_fd_argument(garde_du_compte, tmp_path, monkeypatch):
    # QA4-01 : un chemin relatif accompagné d'un descripteur de dossier réel est résolu depuis ce dossier, pour chaque argument
    # dir_fd des événements (src_dir_fd et dst_dir_fd de rename et link, dir_fd de symlink et de shutil.rmtree compris) ; un
    # descripteur invalide laisse l'opération échouer d'elle-même (EBADF), sans erreur propre à la garde.
    home = tmp_path / "compte"
    (home / "travail").mkdir(parents=True)
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    garde = type(garde_du_compte)(home)
    inside = os.open(home / "travail", os.O_RDONLY)
    outside = os.open(elsewhere, os.O_RDONLY)
    try:
        refused = [("os.mkdir", ("x", 0o777, inside)), ("os.remove", ("x", inside)), ("os.rename", ("a", "b", outside, inside)),
                   ("os.rename", ("a", "b", inside, outside)), ("os.symlink", ("cible", "lien", inside)), ("os.link", ("a", "b", outside, inside)),
                   ("os.chown", ("x", 0, 0, inside)), ("os.utime", ("x", None, None, inside)), ("shutil.rmtree", ("r", inside))]
        for event, args in refused:
            with pytest.raises(PermissionError):
                garde(event, args)
        proceeding = [("os.mkdir", ("x", 0o777, outside)), ("os.rename", ("a", "b", outside, outside)), ("os.symlink", ("cible", "lien", outside)),
                      ("os.link", ("a", "b", inside, outside)), ("shutil.rmtree", ("r", outside)), ("os.mkdir", ("x", 0o777, 999_999)),
                      ("os.remove", ("x", -1))]
        for event, args in proceeding:
            garde(event, args)
    finally:
        os.close(inside)
        os.close(outside)
    assert len(garde.violations) == len(refused)


def test_the_session_guard_sees_installer_files_written_by_a_child_process(garde_du_compte, tmp_path):
    # Le crochet d'audit ne voit pas les processus enfants : les fichiers de l'atelier du compte, et les dossiers où
    # l'installateur les crée, sont relevés autour de l'essai.
    garde = type(garde_du_compte)(tmp_path / "compte")
    before = garde.snapshot()
    registry_path = garde.home / ".local/state/atelier-documentaire/installations.json"
    subprocess.run([sys.executable, "-B", "-c", "import os, sys; os.makedirs(os.path.dirname(sys.argv[1])); open(sys.argv[1], 'w').write('{}')",
                    str(registry_path)], check=True, timeout=60)
    assert garde.changes(before, garde.snapshot()) == [f"{garde.home / '.local/state'} modifié", f"{registry_path.parent} modifié",
                                                       f"{registry_path} modifié"]


def test_the_session_guard_sees_a_transient_write_of_a_child_process(garde_du_compte, tmp_path):
    # R3S-04 (a), double GardeDuCompte sur un compte simulé : un enfant crée puis retire l'entrée de menu et la commande
    # atelier (motif de l'écriture du 07/10 à 05:31:01 UTC) ; les fichiers relevés sont revenus à leur état, mais la date de
    # leurs dossiers a changé.
    garde = type(garde_du_compte)(tmp_path / "compte")
    folders = [garde.home / ".local/share/applications", garde.home / ".local/bin", garde.home / ".local/state"]
    for folder in folders:
        folder.mkdir(parents=True)
        os.utime(folder, (1_600_000_000, 1_600_000_000))  # date ancienne : toute écriture la change
    before = garde.snapshot()
    code = ("import os, sys\nfor path in sys.argv[1:]:\n    open(path, 'w').write('x')\n    os.remove(path)\n")
    subprocess.run([sys.executable, "-B", "-c", code, str(folders[0] / "atelier-documentaire.desktop"), str(folders[1] / "atelier")],
                   check=True, timeout=60)
    assert not (folders[0] / "atelier-documentaire.desktop").exists() and not (folders[1] / "atelier").exists()
    assert garde.changes(before, garde.snapshot()) == [f"{folders[0]} modifié", f"{folders[1]} modifié"]


def test_a_change_seen_in_the_real_account_is_not_imputed_to_the_test_alone(garde_du_compte):
    # QA4-05 : le relevé voit aussi l'écriture d'un autre processus du compte ; le message le dit. Les refus du crochet, faits
    # par l'essai lui-même, gardent leur libellé.
    failure_text = sys.modules[type(garde_du_compte).__module__].failure_text
    assert failure_text([], ["/maison/.local/bin modifié"]) == ("Fichiers de l'atelier du compte réel modifiés pendant l'essai (par lui ou "
                                                                "par un autre processus) : /maison/.local/bin modifié")
    assert failure_text(["open /maison/x"], []) == "Écriture sous le compte réel refusée pendant l'essai : open /maison/x"


def test_insufficient_space_without_a_found_installation_offers_the_update_of_one_made_elsewhere(kit, tmp_path, monkeypatch, isolated_home):
    # U3-03 : `/` plein, installation de 78ec95c faite ailleurs (ni registre ni intégration), nouveau kit lancé sans argument.
    # Le refus de place dit qu'aucune installation n'a été retrouvée et donne la mise à jour, avant tout choix de volume.
    destination, _, _, _ = installed(kit, tmp_path, "--no-start")
    strip_desktop_integration(destination, isolated_home)
    kit_b = second_kit(tmp_path, monkeypatch)
    volume = tmp_path / "disque"
    volume.mkdir()
    probe = PosteSimule(free={str(isolated_home): 5 * GIB, str(volume): 500 * GIB, "*": 5 * GIB}, mounts=[mount("/"), mount(str(volume))],
                        writable={str(volume)})
    hint = ("aucune installation retrouvée (registre, emplacement par défaut) ; si l'atelier est déjà installé ailleurs, ne choisir "
            f"aucun volume : « {linux_install.installer_command(kit_b, 'update', '--destination')} <dossier des versions> »")
    ctx = context(kit_b, probe=probe)
    assert linux_install.main(["--oui"], ctx) == linux_install.EXIT_REFUSED
    assert hint in errors_of(ctx) and errors_of(ctx).index(hint) < errors_of(ctx).index("commande : ")
    asked = context(kit_b, probe=probe, tty=True, answers=[""])
    assert linux_install.main([], asked) == linux_install.EXIT_REFUSED
    assert output_of(asked).index(hint) < output_of(asked).index("Numéro (Entrée : abandonner)")
    # Relancée sur le volume proposé, l'installation neuve garde l'indice dans son récapitulatif.
    elsewhere = context(kit_b, probe=probe)
    assert linux_install.main(["--oui", "--no-start", "--emplacement", str(volume / "atelier-documentaire")], elsewhere) == 0
    assert "Installation existante : aucune trouvée (registre, emplacement par défaut)" in output_of(elsewhere)
    # La commande citée met à jour l'installation faite ailleurs.
    update = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], update) == 0, screen(update)


def test_status_of_an_installation_without_desktop_integration_gives_the_repair_command(kit, tmp_path, isolated_home):
    # U3-03 (2) : `status` d'une installation de 78ec95c dit comment ajouter l'intégration au bureau.
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    strip_desktop_integration(destination, isolated_home)
    ctx = context(kit)
    linux_install.main(["status", "--destination", str(destination)], ctx)
    repair = linux_install.installer_command(Path(current["program"]), "repair", "--menu")
    assert (f"Intégration au bureau : aucune (installation antérieure à l'intégration au bureau) ; « {repair} » ajoute l'entrée "
            "de menu et la commande atelier") in output_of(ctx)


def kit_remplace(kit: Path, case: str) -> None:
    """Double KitRemplace : le dossier du kit est remplacé de façon cohérente après sa vérification (ré-extraction d'une autre
    archive) : fichier modifié, SHA256SUMS et manifeste réécrits (« liste »), ou manifeste seul (« manifeste »)."""
    if case == "liste":
        target = kit / "services/api/main.py"
        target.write_text("VERSION = 'remplacée'\n", encoding="utf-8")
        sums = kit / "SHA256SUMS"
        lines = [f"{sha256(target)}  services/api/main.py" if line.endswith("  services/api/main.py") else line
                 for line in sums.read_text(encoding="utf-8").splitlines()]
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with_manifest(kit, sha256sums_sha256=sha256(sums))
    else:
        with_manifest(kit, kit_id=manifest_of(kit)["kit_id"] + "-autre")


@pytest.mark.parametrize("case", ["liste", "manifeste"])
def test_a_kit_replaced_after_its_verification_is_never_copied_nor_designated(kit, tmp_path, monkeypatch, case):
    # QA3-07, S3-06 : la copie est liée au manifeste et à la liste vérifiés avant la confirmation.
    real_confirm = linux_install.confirm

    def confirm_puis_kit_remplace(ctx, args, title, lines, **options):
        real_confirm(ctx, args, title, lines, **options)
        kit_remplace(kit, case)

    monkeypatch.setattr(linux_install, "confirm", confirm_puis_kit_remplace)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    kit_id = manifest_of(kit)["kit_id"]
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == linux_install.EXIT_PARTIAL, screen(ctx)
    assert "kit-manifest.json a changé depuis sa vérification" in errors_of(ctx)
    assert "rien n'a été désigné" in errors_of(ctx) and not (destination / "installation.json").exists()
    assert not (destination / kit_id).exists() and not (destination / f"{kit_id}-autre").exists()


class TerminalRaccroche(io.StringIO):
    """Double d'un terminal fermé : après le raccroché (SIGHUP), toute écriture échoue, comme sur un pseudo-terminal disparu
    (EIO)."""

    def __init__(self):
        super().__init__()
        self.gone = False

    def write(self, text):
        if self.gone:
            raise OSError(5, "Input/output error")
        return super().write(text)

    def flush(self):
        if self.gone:
            raise OSError(5, "Input/output error")
        return super().flush()


def test_a_hangup_with_the_terminal_gone_during_the_copy_leaves_no_report_nor_data_root(kit, tmp_path, monkeypatch):
    # S3-07 : fenêtre du terminal fermée pendant la copie, la progression étant affichée au terminal : code 130, ni rapport ni
    # racine des données créée, copie retirée (DEPLOIEMENT §8.3, « Échec et reprise »).
    from tools.dist import build_kit

    real_stream_copy = build_kit.stream_copy
    copied: list[Path] = []
    ctx = context(kit, tty=True)
    out, err = TerminalRaccroche(), TerminalRaccroche()
    ctx.out, ctx.err = out, err

    def stream_copy_puis_raccroche(source, target):
        if len(copied) == 4:
            out.gone = err.gone = True
            os.kill(os.getpid(), signal.SIGHUP)
        copied.append(target)
        return real_stream_copy(source, target)

    monkeypatch.setattr(build_kit, "stream_copy", stream_copy_puis_raccroche)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(ctx, destination, data_root, "--no-start") == linux_install.EXIT_INTERRUPTED
    assert not data_root.exists() and not (destination / manifest_of(kit)["kit_id"]).exists()
    assert not list(tmp_path.rglob("install-*.json"))


@pytest.mark.parametrize("running", [False, True], ids=["arretee", "deja-demarree"])
def test_a_failed_backup_leaves_the_instance_as_it_was_and_states_the_cause_first(kit, tmp_path, monkeypatch, running):
    # S3-08, U3-08 : la mise à jour démarre la version en place pour la sauvegarder ; la sauvegarde refusée, l'instance qu'elle
    # a démarrée est arrêtée (celle que l'utilisateur avait démarrée reste en marche) ; la cause précède l'état laissé.
    destination, data_root, current, _ = installed(kit, tmp_path, *([] if running else ["--no-start"]))
    kit_b = second_kit(tmp_path, monkeypatch)
    runner = ProgrammeSimule(results={"backup": {"_rc": 1, "status": "failed", "message": "Espace insuffisant pour la sauvegarde."}})
    if running:
        runner.running[current["program"]] = current["profile"]
    ctx = context(kit_b, runner=runner)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == linux_install.EXIT_ERROR
    lines = errors_of(ctx).strip().splitlines()
    assert lines[0] == "Arrêt : Sauvegarde refusée : Espace insuffisant pour la sauvegarde. Rien n'a été installé.", lines
    if running:
        assert lines[1] == (f"La version {current['kit_id']} reste la version courante ; son instance, déjà démarrée avant la mise à "
                            "jour, reste démarrée.")
        assert runner.running == {current["program"]: current["profile"]} and "down" not in runner.commands()
    else:
        assert lines[1] == (f"La version {current['kit_id']} reste la version courante ; l'instance démarrée pour la sauvegarde a été "
                            "arrêtée, comme avant la mise à jour.")
        assert runner.running == {} and runner.commands()[-2:] == ["backup", "down"]
    assert "la relancer" not in errors_of(ctx) and pointer_of(destination)["current"]["kit_id"] == current["kit_id"]


def test_a_failed_backup_whose_instance_does_not_stop_says_it_is_still_running(kit, tmp_path, monkeypatch):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    kit_b = second_kit(tmp_path, monkeypatch)
    runner = ProgrammeSimule(results={"backup": {"_rc": 1, "message": "Espace insuffisant pour la sauvegarde."},
                                      "down": {"_rc": 1, "status": "running", "message": "arrêt impossible"}})
    ctx = context(kit_b, runner=runner)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == linux_install.EXIT_ERROR
    stop = linux_install.launcher_command(pointer_of(destination), destination, "arreter")
    assert (f"La version {current['kit_id']} reste la version courante ; l'instance démarrée pour la sauvegarde est toujours en "
            f"marche : « {stop} » l'arrête.") in errors_of(ctx)


def test_a_qdrant_storage_on_a_volatile_or_network_volume_is_refused_before_any_write(kit, tmp_path):
    # S3-09 : --qdrant-storage suit les règles de la racine des données (ni volatil, ni réseau, accessible en écriture).
    for fstype, expected in (("tmpfs", "stockage Qdrant {path} sur un volume non persistant (tmpfs) monté sur /media/x : l'index "
                                        "serait perdu au redémarrage — choisir un dossier sur un disque local (--qdrant-storage)"),
                             ("nfs4", "stockage Qdrant {path} sur nfs4 (/media/x) : Qdrant exige un système de fichiers POSIX local (ni "
                                      "réseau, ni FAT, ni NTFS) — choisir un dossier sur un disque local (--qdrant-storage)")):
        storage = tmp_path / f"volume-{fstype}/qdrant"
        probe = PosteSimule(fstype={str(storage.parent): fstype, "*": "ext4"})
        ctx = context(kit, probe=probe)
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--qdrant-storage", str(storage)) == linux_install.EXIT_REFUSED
        assert expected.format(path=storage) in errors_of(ctx), errors_of(ctx)
        assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists()


def test_a_restore_target_on_a_volatile_volume_is_refused_before_the_rollback(kit, tmp_path, monkeypatch):
    # S3-09 : --restore-target devient la racine active du pointeur : contrôlée avant la confirmation du retour arrière.
    destination, _, runner = started_update(kit, tmp_path, monkeypatch)
    before = pointer_of(destination)
    target = tmp_path / "tmpfs/retour"
    ctx = context(kit, runner=runner, probe=PosteSimule(fstype={str(target.parent): "tmpfs", "*": "ext4"}))
    assert linux_install.main(["rollback", "--destination", str(destination), "--restore-target", str(target), "--oui"], ctx) == linux_install.EXIT_REFUSED
    assert (f"--restore-target {target} sur un volume non persistant (tmpfs) monté sur /media/x : les données restaurées seraient "
            "perdues au redémarrage — choisir une racine neuve sur un disque local ; rien n'a été modifié.") in errors_of(ctx)
    assert not {"down", "restore"} & set(runner.commands()) and pointer_of(destination) == before and not target.exists()


def test_an_unwritable_user_bin_is_refused_before_any_write(kit, tmp_path, isolated_home):
    # S3-10, U3-09 : ~/.local/bin non accessible en écriture arrêtait l'installation à sa dernière étape (PermissionError
    # brut, code 5, tout retiré) ; le précontrôle le refuse sans rien écrire.
    folder = isolated_home / ".local/bin"
    folder.mkdir(parents=True)
    folder.chmod(0o555)
    try:
        ctx = context(kit)
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == linux_install.EXIT_REFUSED, screen(ctx)
        assert (f"commande atelier : {folder} non accessible en écriture pour ce compte — corriger ses droits "
                f"(« chmod u+w {folder} »), ou installer avec --sans-menu") in errors_of(ctx)
        assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists()
        assert install(context(kit), tmp_path / "programmes", tmp_path / "donnees", "--no-start", "--sans-menu") == 0
    finally:
        folder.chmod(0o755)


def third_kit(tmp_path, monkeypatch) -> Path:
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'troisième'\n")
    git(repository, "commit", "-q", "-am", "troisième version")
    web_provenance(repository)
    return make_kit(tmp_path, monkeypatch, name="kit-c", repository=repository)


def test_a_version_folder_no_longer_designated_never_acts_on_another_installation(kit, tmp_path, monkeypatch, isolated_home):
    # S3-03 : A est inscrite au registre ; B (--sans-menu) a été mise à jour deux fois, sa première version y reste sans être
    # désignée. Lancé depuis ce dossier, l'installateur ne se rabat jamais sur le registre : refus qui nomme B.
    a = tmp_path / "a/programme"
    assert linux_install.main(["--oui", "--no-start", "--emplacement", str(tmp_path / "a")], context(kit)) == 0
    kit_b, kit_c = second_kit(tmp_path, monkeypatch), third_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(a), "--oui", "--no-start"], context(kit_b)) == 0
    b = tmp_path / "b/programme"
    assert install(context(kit), b, tmp_path / "b/donnees", "--no-start", "--sans-menu") == 0
    for new in (kit_b, kit_c):
        assert linux_install.main(["update", "--destination", str(b), "--oui", "--no-start"], context(new)) == 0
    first = b / manifest_of(kit)["kit_id"]
    assert first.is_dir() and pointer_of(a)["previous"]["kit_id"] == manifest_of(kit)["kit_id"]
    before = (pointer_of(a), pointer_of(b))
    current_b = Path(pointer_of(b)["current"]["program"])
    for argv, command in ((["rollback"], "rollback"), (["status"], "status"), (["uninstall", "--oui"], "uninstall"),
                          (["repair"], "repair"), (["modele", "qwen3.5:2b", "--oui"], "modele"), (["--oui"], "status")):
        ctx = context(first)
        assert linux_install.main(argv, ctx) == linux_install.EXIT_REFUSED, screen(ctx)
        assert (f"{first} est un dossier de version de {b} que son pointeur ne désigne pas : employer "
                f"« {linux_install.installer_command(current_b, command)} », ou indiquer --destination ; rien n'a été modifié.") in errors_of(ctx)
        assert ctx.runner.calls == []
    assert (pointer_of(a), pointer_of(b)) == before


def test_uninstall_and_the_simple_rollback_name_the_installation(kit, tmp_path, monkeypatch):
    # S3-03 : la destination visée est écrite au récapitulatif de la désinstallation et avant la rebascule simple.
    destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 0, screen(ctx)
    announce = (f"Retour arrière de {destination} : version {first['kit_id']} rétablie, version {second['kit_id']} abandonnée ; elle n'a "
                "jamais démarré sur les données : rien n'est restauré.")
    assert announce in output_of(ctx) and output_of(ctx).index(announce) < output_of(ctx).index("Retour arrière terminé")
    code, ctx = uninstall(kit, destination, second["kit_id"])
    assert code == 0 and f"Récapitulatif de la désinstallation :\n  Installation : {destination}\n" in output_of(ctx)


def test_an_unreadable_instance_state_stops_the_uninstall_before_any_removal(kit, tmp_path):
    # S3-04 : état illisible (status en échec) : jamais traité comme arrêté ; rien n'est retiré, l'arrêt est demandé.
    destination, data_root, current, runner = installed(kit, tmp_path)
    assert runner.running
    runner.results["status"] = {"_rc": 1, "status": "failed", "message": "Programme endommagé"}
    ctx = context(kit, runner=runner)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], ctx) == linux_install.EXIT_REFUSED
    stop = linux_install.launcher_command(pointer_of(destination), destination, "arreter")
    assert (f"État de l'instance de {current['kit_id']} illisible (Programme endommagé) : l'arrêter (« {stop} »), puis relancer ; "
            "rien n'a été supprimé.") in errors_of(ctx)
    assert Path(current["program"]).is_dir() and pointer_of(destination)["current"]["kit_id"] == current["kit_id"]
    assert "down" not in runner.commands()


@pytest.mark.parametrize("step", ["copie", "doctor"])
def test_the_resumed_install_reports_what_it_removed(kit, tmp_path, step):
    # S3-11, U3-06 : le texte de l'étape « interrompue » est calculé avant les suppressions ; accords ; libellé non répété ;
    # chemins retirés consignés au rapport.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    killed_install(kit, destination, data_root, step)
    program = destination / manifest_of(kit)["kit_id"]
    profiles = ["profile.yaml", "profile-qwen3.5-2b.yaml"] if step == "doctor" else []
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--no-start") == 0, screen(ctx)
    if profiles:
        removed = f"profils qu'elle a créés ({', '.join(profiles)}) et dossier de version {program} retirés"
    else:
        removed = f"dossier de version {program} retiré"
    output = output_of(ctx)
    assert (f"  Installation interrompue le 2026-10-06 20:00 UTC (version {manifest_of(kit)['kit_id']}), jamais activée : {removed} "
            "avant la copie\n") in output
    assert f"[ok] Installation interrompue : {removed} (commencée le 2026-10-06 20:00 UTC, jamais activée)\n" in output
    report = json.loads(next(data_root.glob("install-*.json")).read_text(encoding="utf-8"))
    assert report["interrupted_removed"] == [*(str(data_root / name) for name in profiles), str(program)]
    step_detail = next(item["detail"] for item in report["steps"] if item["step"] == "interrompue")
    assert step_detail == f"{removed} (commencée le 2026-10-06 20:00 UTC, jamais activée)"


def help_text(kit, *argv) -> str:
    ctx = context(kit)
    assert linux_install.main([*argv, "--aide"], ctx) == 0
    return " ".join(output_of(ctx).split())


def test_help_texts_say_which_operations_ask_and_name_values_in_french(kit, tmp_path):
    # U3-04 : récapitulatif annoncé pour les seules opérations qui en affichent un ; --oui de repair masqué, celui de modele
    # décrit ; --sans-menu précis ; métavariables en français.
    top = help_text(kit)
    assert ("Une installation, une mise à jour, une désinstallation et un retour arrière avec restauration affichent un récapitulatif "
            "et demandent confirmation (--oui hors terminal).") in top
    assert "Toute opération qui écrit" not in top and "exigé hors terminal pour écrire" not in top
    assert "--oui" not in help_text(kit, "repair")
    assert "--oui ne rien demander ; refuse si l'atelier tourne avec un autre modèle" in help_text(kit, "modele")
    assert "--sans-menu ni entrée de menu, ni commande atelier dans ~/.local/bin, ni inscription au registre des installations" in help_text(kit, "install")
    assert ("--sans-menu retirer l'entrée de menu et la commande atelier ; ce choix est inscrit au pointeur et l'entrée de "
            "l'installation est retirée du registre") in help_text(kit, "repair")
    texts = " ".join(help_text(kit, command) for command in linux_install.INSTALLER_COMMANDS)
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    launcher = context(Path(current["program"]))
    assert linux_install.main(["run", "--destination", str(destination), "--aide"], launcher) == 0
    texts += " " + output_of(launcher)
    for internal in ("DATA_ROOT", "QDRANT_STORAGE", "RESTORE_TARGET", "KIT_ID", "PROFILE", "MENU", "PORTS", "MODELE", "DESTINATION",
                     "EMPLACEMENT"):
        assert not re.search(rf"\b{internal}\b", texts), internal
    for spelled in ("--data-root <dossier>", "--qdrant-storage <dossier>", "--restore-target <dossier>", "--kit-id <kit_id>",
                    "--profile <fichier>", "--ports <API,Qdrant,Ollama>", "--emplacement <dossier>", "--destination <dossier>",
                    "--modele <modèle>", "--menu <dossier>"):
        assert spelled in texts, spelled


def test_update_without_a_designated_version_cites_the_exact_reprise(kit, tmp_path, monkeypatch):
    # U3-05 (1) : après un retrait complet, update cite la commande exacte, pas la seule sous-commande.
    destination, data_root, _, _ = installed(kit, tmp_path, "--no-start")
    a_backup(data_root)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--tout", "--oui"], context(kit)) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_REFUSED
    command = linux_install.installer_command(kit_b, "install", "--destination", str(destination))
    assert (f"Aucune version installée n'est désignée dans {destination / 'installation.json'} : pour reprendre des données "
            f"conservées, « {command} --data-root <données conservées> --reprendre-donnees » ; pour une installation neuve, "
            f"« {command} » ; rien n'a été installé.") in errors_of(ctx)


def test_a_second_rollback_cites_the_commands_that_lead_to_another_version(kit, tmp_path, monkeypatch):
    # U3-05 (2)
    destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    assert linux_install.main(["rollback", "--destination", str(destination)], context(kit_b)) == 0
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == linux_install.EXIT_REFUSED
    removal = linux_install.installer_command(Path(first["program"]), "uninstall", "--kit-id", second["kit_id"])
    assert (f"Retour arrière déjà effectué : la version précédente {second['kit_id']} est celle qu'il a abandonnée ; aucun second "
            f"retour arrière n'est proposé. Pour passer à une autre version : retirer la version abandonnée (« {removal} »), puis "
            f"« <dossier du kit de la version voulue>/{linux_install.quoted('installer.sh', 'update', '--destination', str(destination))} ».") in errors_of(ctx)


@pytest.mark.parametrize("previous", [True, False], ids=["precedente", "seule"])
def test_repair_of_a_missing_program_cites_the_way_back(kit, tmp_path, monkeypatch, previous):
    # U3-05 (3)
    if previous:
        destination, _, first, second, kit_b = updated(kit, tmp_path, monkeypatch)
    else:
        destination, _, second, _ = installed(kit, tmp_path, "--no-start")
    shutil.rmtree(second["program"])
    ctx = context(kit)
    assert linux_install.main(["repair", "--destination", str(destination)], ctx) == linux_install.EXIT_REFUSED
    if previous:
        expected = f"revenir à la version précédente : « {linux_install.installer_command(Path(first['program']), 'rollback')} »"
    else:
        expected = ("réinstaller cette version depuis son kit en reprenant les données : procédure de docs/exploitation/DEPANNAGE.md, "
                    "section 10.4 (« Réparer un programme installé avec le seul kit de sa version »)")
    assert f"Le pointeur désigne {second['program']}, absent : {expected} ; rien n'a été écrit." in errors_of(ctx)


def test_the_repair_procedure_still_works_when_the_program_folder_is_gone(kit, tmp_path):
    # U3-05 (3) : la procédure citée (section 10.4 du dépannage) doit aussi valoir pour un dossier de programme disparu :
    # uninstall --tout met le pointeur à jour sans rien supprimer, puis la reprise réinstalle sur les mêmes données.
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    a_backup(data_root)
    before = inventory(data_root)
    shutil.rmtree(current["program"])
    ctx = context(kit)
    assert linux_install.main(["uninstall", "--tout", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    assert f"{current['program']} déjà absent : version retirée du pointeur" in output_of(ctx)
    assert pointer_of(destination)["current"] is None and inventory(data_root) == before
    ctx = context(kit)
    assert install(ctx, destination, data_root, "--reprendre-donnees", "--no-start") == 0, screen(ctx)
    assert pointer_of(destination)["current"]["data_root"] == str(data_root)


def test_a_reprise_of_data_used_by_an_installation_cites_its_update(kit, tmp_path, monkeypatch):
    # U3-05 (4)
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert install(ctx, tmp_path / "autre", data_root, "--reprendre-donnees") == linux_install.EXIT_REFUSED
    update = linux_install.installer_command(kit, "update", "--destination", str(destination))
    assert (f"La racine des données {data_root} est employée par l'installation {destination} (version {current['kit_id']}) : pour y "
            f"installer ce kit, « {update} », au lieu de la reprendre ; rien n'a été installé.") in errors_of(ctx)


@pytest.mark.parametrize("integration", [True, False], ids=["integration", "78ec95c"])
def test_an_update_to_a_kit_without_the_principal_model_cites_a_runnable_command(kit, tmp_path, monkeypatch, isolated_home, integration):
    # U3-07 : le lanceur d'une installation de 78ec95c n'a pas l'action modele ; la commande valable pour toute installation
    # est update --model, et elle met à jour en une étape.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--model", "qwen3.5:2b", "--no-start") == 0
    if not integration:
        strip_desktop_integration(destination, isolated_home)
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'suivante'\n")
    git(repository, "commit", "-q", "-am", "version suivante")
    web_provenance(repository)
    four = make_kit(tmp_path, monkeypatch, name="kit-4b", repository=repository, models=("4b",))
    ctx = context(four)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx) == linux_install.EXIT_REFUSED
    update = linux_install.installer_command(four, "update", "--destination", str(destination), "--model", "qwen3.5:4b")
    errors = errors_of(ctx)
    assert (f"Le modèle du profil en place (qwen3.5:2b) n'est pas livré par ce kit ; rien n'a été installé. Pour adopter le modèle "
            f"livré pendant la mise à jour : « {update} »") in errors
    assert ("modele qwen3.5:4b" in errors) == integration
    words = shlex.split(update)
    retry = context(four)
    assert linux_install.main([*words[1:], "--oui", "--no-start"], retry) == 0, screen(retry)
    assert pointer_of(destination)["current"]["model"] == "qwen3.5:4b"


# --- Ronde 5 de R26-KIT-04 : U4-02 à U4-06, R3S-02, R3S-03 ---------------------------------------------------------------------

@pytest.mark.parametrize("previous", [True, False], ids=["precedente", "seule"])
def test_status_of_a_missing_current_program_cites_a_present_installer(kit, tmp_path, monkeypatch, previous):
    # U4-02 (S10, S9) : dossier du programme courant supprimé ; status cite la commande d'un installateur présent et la suite
    # de repair, et le récapitulatif d'uninstall dit que seul le pointeur change.
    if previous:
        destination, _, first, second, _ = updated(kit, tmp_path, monkeypatch)
    else:
        destination, _, second, _ = installed(kit, tmp_path, "--no-start")
    shutil.rmtree(second["program"])
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == linux_install.EXIT_ERROR
    output = output_of(ctx)
    assert f"{second['program']}/installer.sh" not in output, output
    if previous:
        rollback = linux_install.installer_command(Path(first["program"]), "rollback")
        assert f"Version précédente : {first['kit_id']} ; retour arrière : « {rollback} »" in output
        assert f"programme courant absent : {second['program']} — revenir à la version précédente : « {rollback} »" in output
    else:
        assert (f"programme courant absent : {second['program']} — réinstaller cette version depuis son kit en reprenant les données : "
                "procédure de docs/exploitation/DEPANNAGE.md, section 10.4 (« Réparer un programme installé avec le seul kit de sa "
                "version »)") in output
    ctx = context(kit)
    assert linux_install.main(["uninstall", "--tout", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    output = output_of(ctx)
    assert f"Retirer du pointeur : {second['kit_id']} (dossier {second['program']} déjà absent)" in output
    assert f"Retirer : {second['kit_id']} (" not in output


def test_verifier_announces_the_update_of_an_installation_it_finds(kit, tmp_path, monkeypatch, isolated_home):
    # U4-03 (S13, cas 1) : une installation existe à l'emplacement par défaut ; ./installer.sh en proposerait la mise à jour,
    # verifier le dit au lieu d'annoncer une installation, et n'écrit rien.
    assert linux_install.main(["install", "--oui", "--no-start"], context(kit)) == 0
    destination = isolated_home / ".local/share/atelier-documentaire/programme"
    current = pointer_of(destination)["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    before = inventory(isolated_home)
    ctx = context(kit_b)
    assert linux_install.main(["verifier"], ctx) == 0, screen(ctx)
    output = output_of(ctx)
    assert (f"Installation existante trouvée dans {destination} (version {current['kit_id']}) : ./installer.sh, lancé depuis ce kit, en "
            f"proposera la mise à jour vers {manifest_of(kit_b)['kit_id']}.") in output
    assert "prêts pour l'installation" not in output
    assert inventory(isolated_home) == before and ctx.runner.calls == []


def test_verifier_refuses_kept_data_without_backup_like_the_installer(kit, tmp_path, isolated_home):
    # U4-03 (S13, cas 2) : après un retrait complet sans sauvegarde, ./installer.sh --oui refuse (code 3) ; verifier aussi, avec
    # la commande d'installation sur une autre racine, et non plus « prêts ».
    assert linux_install.main(["install", "--oui", "--no-start"], context(kit)) == 0
    assert linux_install.main(["uninstall", "--tout", "--oui"], context(kit)) == 0
    data_root = isolated_home / ".local/share/atelier-documentaire/donnees"
    installer = context(kit)
    assert linux_install.main(["--oui"], installer) == linux_install.EXIT_REFUSED
    ctx = context(kit)
    assert linux_install.main(["verifier"], ctx) == linux_install.EXIT_REFUSED, screen(ctx)
    other = linux_install.installer_command(kit, "install", "--data-root") + " <autre dossier>"
    expected = (f"Données conservées dans {data_root} (profile.yaml), sans aucune sauvegarde dans {data_root / 'backups'} : elles ne sont "
                "jamais remplacées, et leur reprise sans sauvegarde n'est pas prise en charge. Pour installer l'atelier, choisir une "
                f"autre racine des données : « {other} » ; les données restent dans {data_root}. Rien n'a été installé.")
    assert expected in errors_of(ctx) and "sans aucune sauvegarde" in errors_of(installer)
    assert "prêts" not in output_of(ctx) and ctx.runner.calls == []


def test_verifier_checks_the_qdrant_storage_like_the_installer(kit, tmp_path):
    # verifier contrôle --qdrant-storage par les mêmes règles qu'install (R3S-02).
    ctx = context(kit)
    code = linux_install.main(["verifier", "--destination", str(tmp_path / "programmes"), "--data-root", str(tmp_path / "donnees"),
                               "--qdrant-storage", str(kit / "index-qdrant")], ctx)
    assert code == linux_install.EXIT_REFUSED and f"stockage Qdrant {kit / 'index-qdrant'} dans le kit ou le programme" in errors_of(ctx)


def test_the_exit_code_1_names_the_refusals_of_installer_sh_in_the_help(kit):
    # U4-04, QA4-10 : les refus d'installer.sh avant Python sortent en code 1 ; l'aide et le guide (EXIT_CODES) le disent.
    meaning = linux_install.EXIT_CODES[linux_install.EXIT_ERROR]
    for cause in ("refus d'installer.sh avant le lancement de Python", "compte root", "architecture", "glibc", "outil absent",
                  "ajouté", "remplacé par un lien", "illisible", "pour status : aucune installation trouvée ou problème relevé",
                  # U6-06 : type changé (dossier, fichier spécial), droits de lecture et d'exécution perdus, manifeste introuvable.
                  "remplacé par un lien, un dossier ou un fichier spécial", "sans droit de lecture ou d'exécution",
                  "manifeste introuvable ou illisible"):
        assert cause in meaning, cause
    ctx = context(kit)
    assert linux_install.main(["--aide"], ctx) == 0
    assert "1 autre erreur, ou refus d'installer.sh avant le lancement de Python ; 2 usage ;" in " ".join(output_of(ctx).split())


def test_an_unwritable_parent_of_a_missing_user_bin_is_named_with_a_command_that_works(kit, tmp_path, isolated_home):
    # U4-05 (S12) : ~/.local en 0555 et ~/.local/bin absent : le refus cite le dossier existant, dont la commande donnée
    # rétablit les droits.
    local = isolated_home / ".local"
    local.mkdir()
    local.chmod(0o555)
    try:
        ctx = context(kit)
        code = linux_install.main(["install", "--emplacement", str(tmp_path / "autre"), "--oui", "--no-start"], ctx)
        assert code == linux_install.EXIT_REFUSED, screen(ctx)
        assert (f"commande atelier : {local} ({local / 'bin'} à y créer) non accessible en écriture pour ce compte — corriger ses droits "
                f"(« chmod u+w {local} »), ou installer avec --sans-menu") in errors_of(ctx)
        assert f"chmod u+w {local / 'bin'}" not in errors_of(ctx) and ctx.runner.calls == []
    finally:
        local.chmod(0o755)
    ctx = context(kit)
    assert linux_install.main(["install", "--emplacement", str(tmp_path / "autre"), "--oui", "--no-start"], ctx) == 0, screen(ctx)


def test_no_installation_found_names_the_real_default_folder_and_the_destination_option(kit, tmp_path, monkeypatch, isolated_home):
    # U4-06 (S2b) : installation --sans-menu placée ailleurs, puis update et status depuis un autre kit : le chemin réel de
    # l'emplacement par défaut, pas l'expression du shell, et status cite --destination.
    assert install(context(kit), tmp_path / "ailleurs/programmes", tmp_path / "ailleurs/donnees", "--no-start", "--sans-menu") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    default = isolated_home / ".local/share/atelier-documentaire/programme"
    ctx = context(kit_b)
    assert linux_install.main(["update", "--oui"], ctx) == linux_install.EXIT_REFUSED
    assert f", emplacement par défaut {default}) : indiquer --destination <dossier des versions>" in errors_of(ctx)
    assert "${XDG_DATA_HOME" not in errors_of(ctx)
    ctx = context(kit_b)
    assert linux_install.main(["status"], ctx) == linux_install.EXIT_ERROR
    assert (f" ; emplacement par défaut {default}). Si l'atelier est installé ailleurs : "
            f"« {linux_install.installer_command(kit_b, 'status', '--destination')} <dossier des versions> » ; sinon, installer depuis le "
            "dossier d'un kit : ./installer.sh.") in output_of(ctx)
    assert "${XDG_DATA_HOME" not in output_of(ctx)


@pytest.mark.parametrize("where", ["kit", "config", "static"])
def test_a_qdrant_storage_in_the_kit_or_holding_qdrant_files_is_refused_before_any_write(kit, tmp_path, where):
    # R3S-02 : un index dans le kit disparaîtrait avec lui ; Qdrant démarre depuis ce dossier et y lirait config/ ou static/.
    if where == "kit":
        storage = kit / "index-qdrant"
        expected = f"stockage Qdrant {storage} dans le kit ou le programme — choisir un dossier hors du kit (--qdrant-storage)"
    else:
        storage = tmp_path / "index"
        (storage / where).mkdir(parents=True)
        expected = (f"stockage Qdrant {storage} : contient {where}/, que Qdrant lirait en démarrant depuis ce dossier (configuration "
                    "config/, pages static/) — choisir un dossier absent, vide ou réservé à l'index (--qdrant-storage)")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--qdrant-storage", str(storage), "--no-start") == linux_install.EXIT_REFUSED
    assert expected in errors_of(ctx), errors_of(ctx)
    assert ctx.runner.calls == [] and not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists()
    # Témoin : un dossier vide hors du kit est accepté.
    empty = tmp_path / "index-vide"
    empty.mkdir()
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--qdrant-storage", str(empty), "--no-start") == 0, screen(ctx)


def running_from(runner: ProgrammeSimule, *programs: Path):
    """Double ProcessusDuProgramme : processus du compte lancés depuis un programme (/proc/<pid>/exe), déduits des instances en
    marche de ProgrammeSimule, plus ceux des `programs` cités (instance que l'installateur ne connaît pas)."""
    def processes(program: Path) -> list[tuple[int, str]]:
        if str(program) in runner.running or program in programs:
            return [(4242, f"{program}/.runtime/python/{PYTHON_KEY}/bin/python3.12")]
        return []
    return processes


def test_an_instance_running_without_its_profiles_stops_the_uninstall_before_any_removal(kit, tmp_path):
    # R3S-03 : profils de la version supprimés pendant que son instance tourne ; l'état est illisible : refus, code 3, rien
    # n'est retiré, l'instance n'est ni lue ni arrêtée.
    destination, data_root, current, runner = installed(kit, tmp_path)
    assert runner.running
    profiles = sorted(current["profiles"].values())
    for profile in profiles:
        Path(profile).unlink()
    ctx = context(kit, runner=runner, probe=PosteSimule(processes=running_from(runner)))
    assert linux_install.main(["uninstall", "--tout", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_REFUSED
    executable = f"{current['program']}/.runtime/python/{PYTHON_KEY}/bin/python3.12"
    assert (f"État de l'instance de {current['kit_id']} illisible (profils {', '.join(profiles)} absents) : processus de ce programme en "
            f"marche (PID 4242 : {executable}) — les arrêter, puis relancer ; rien n'a été supprimé.") in errors_of(ctx)
    assert Path(current["program"]).is_dir() and pointer_of(destination)["current"]["kit_id"] == current["kit_id"]
    assert runner.running and "down" not in runner.commands()
    # Témoin : instance arrêtée, profils toujours absents : le retrait a lieu.
    runner.running.clear()
    ctx = context(kit, runner=runner, probe=PosteSimule(processes=running_from(runner)))
    assert linux_install.main(["uninstall", "--tout", "--destination", str(destination), "--oui"], ctx) == 0, screen(ctx)
    assert not Path(current["program"]).exists()


def test_a_running_undesignated_version_is_not_removed(kit, tmp_path, monkeypatch):
    # R3S-03, variante : version non désignée (--anciennes) dont une instance tourne ; aucun profil ne permet de lire son
    # état : refus, code 3.
    destination, _, first, second, _ = updated(kit, tmp_path, monkeypatch)
    from tests.unit.test_dist_linux_review import third_kit

    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], context(third_kit(tmp_path, monkeypatch))) == 0
    runner = ProgrammeSimule()
    ctx = context(kit, runner=runner, probe=PosteSimule(processes=running_from(runner, Path(first["program"]))))
    assert linux_install.main(["uninstall", "--destination", str(destination), "--anciennes", "--oui"], ctx) == linux_install.EXIT_REFUSED
    assert (f"État de l'instance de {first['kit_id']} illisible (version non désignée par le pointeur, dont aucun profil n'est connu de "
            "l'installation) : processus de ce programme en marche") in errors_of(ctx)
    assert Path(first["program"]).is_dir()


def test_an_instance_started_with_an_unknown_profile_is_not_removed(kit, tmp_path):
    # R3S-03, variante : version désignée, profils lisibles et arrêtés, mais un processus du compte tourne depuis son dossier
    # (profil hors du pointeur) : refus avant tout retrait.
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    runner = ProgrammeSimule()
    ctx = context(kit, runner=runner, probe=PosteSimule(processes=running_from(runner, Path(current["program"]))))
    assert linux_install.main(["uninstall", "--tout", "--destination", str(destination), "--oui"], ctx) == linux_install.EXIT_REFUSED
    assert (f"Processus de {current['kit_id']} encore en marche (PID 4242 : {current['program']}/.runtime/python/{PYTHON_KEY}/bin/"
            "python3.12) : instance lancée avec un profil que l'installation ne désigne pas, ou autre usage de ce programme — les "
            "arrêter, puis relancer ; rien n'a été supprimé.") in errors_of(ctx)
    assert Path(current["program"]).is_dir() and pointer_of(destination)["current"]["kit_id"] == current["kit_id"]


def test_the_system_probe_finds_a_process_of_the_account_by_its_executable(tmp_path):
    # R3S-03 : lecture réelle de /proc ; un processus enfant lancé depuis une copie de sleep (coreutils) placée dans un
    # « programme » est trouvé ; le processus courant ne l'est jamais.
    program = tmp_path / "programme"
    (program / "bin").mkdir(parents=True)
    copy = program / "bin/sleep"
    shutil.copy2(shutil.which("sleep") or "/bin/sleep", copy)
    child = subprocess.Popen([str(copy), "30"], env={"PATH": "/usr/bin:/bin"})
    try:
        deadline = time.monotonic() + 10
        found: list[tuple[int, str]] = []
        while time.monotonic() < deadline and not found:
            found = linux_install.SystemProbe().program_processes(program)
            time.sleep(0.05)
        assert found == [(child.pid, str(copy))]
        own = linux_install.SystemProbe().program_processes(Path(os.path.realpath(sys.executable)).parent)
        assert all(pid != os.getpid() for pid, _ in own), own
    finally:
        child.kill()
        child.wait(timeout=30)


# --- U6-04 : status relaie le refus de l'installateur d'une version désignée ----------------------------------------------------

def test_status_relays_a_refusal_of_the_installer_of_a_designated_version(kit, tmp_path, monkeypatch):
    # U6-04 : status rejoue, pour chaque version désignée présente, les contrôles de son installer.sh (probe.installer_refusal,
    # rejoué réellement par test_dist_linux_scripts) ; un refus devient un problème (code 1), avec le message d'installer.sh, qui
    # porte l'action. Témoin : aucun refus, aucun problème.
    destination, _, first, second, _ = updated(kit, tmp_path, monkeypatch)
    probe = PosteSimule()
    ctx = context(kit, probe=probe)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 0, screen(ctx)
    assert probe.installer_checks == [Path(second["program"]), Path(first["program"])]
    refusal = (".runtime/python/cpython/lib/NOTES.txt ajouté à ce programme installé, absent de SHA256SUMS et de SYMLINKS : … ; rien n'a "
               "été exécuté.")
    ctx = context(kit, probe=PosteSimule(installer_refusals={first["program"]: refusal}))
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 1, screen(ctx)
    expected = (f"« {linux_install.installer_command(Path(first['program']))} » refuse toute commande, avant de lancer Python : "
                f"{refusal}")
    assert f"Problèmes :\n  - {expected}\n" in output_of(ctx), output_of(ctx)


# --- U6-01, R5S-01 : installation faite par un chemin qui traverse un lien symbolique ------------------------------------------
# Le pointeur garde la destination telle qu'elle a été tapée (chemin logique) ; installer.sh, lancé depuis un programme
# installé, transmet le chemin physique de ce programme (--kit "$(pwd -P)"), et son refus cite la destination physique.

def dossier_par_un_lien(tmp_path: Path) -> tuple[Path, Path]:
    """Double nommé DossierParUnLien (DossierRelieAUnAutreDisque du relecteur) : dossier réel sur « un autre disque » et lien
    symbolique par lequel l'utilisateur l'atteint (~/atelier relié à un disque ; .runtime et .venv reliés à la carte microSD sur
    le poste de référence). Rend (lien, dossier réel)."""
    real = tmp_path / "autre-disque/atelier"
    real.mkdir(parents=True)
    linked = tmp_path / "atelier"
    os.symlink(real, linked)
    return linked, real


def physical(path) -> Path:
    """Chemin réel, celui qu'installer.sh transmet pour un programme installé (--kit "$(pwd -P)") et que cite son refus."""
    return Path(os.path.realpath(path))


def installed_through_a_link(kit, tmp_path, *, start: bool = False):
    """Installation faite par le chemin logique ; rend (destination logique, destination physique, données logiques, runner)."""
    linked, real = dossier_par_un_lien(tmp_path)
    ctx = context(kit)
    assert install(ctx, linked / "programmes", linked / "donnees", *([] if start else ["--no-start"])) == 0, screen(ctx)
    return linked / "programmes", real / "programmes", linked / "donnees", ctx.runner


def test_the_installer_of_a_program_reached_through_a_link_owns_its_menu_entry_and_command(kit, tmp_path, isolated_home):
    # U6-01 (a), preuves 09 et 09b : status rendait le code 1 avec deux faux problèmes (« remplacée par un fichier étranger »),
    # repair et modele laissaient l'entrée et la commande « n'appartient pas à cette installation », et les actions du menu
    # n'étaient pas régénérées après modele.
    destination, real, _, runner = installed_through_a_link(kit, tmp_path)
    program = physical(pointer_of(destination)["current"]["program"])
    entry, command = applications(isolated_home) / "atelier-documentaire.desktop", isolated_home / ".local/bin/atelier"
    ctx = context(program, runner=runner)
    assert linux_install.main(["status"], ctx) == 0, screen(ctx)
    assert f"Installation : {destination}\n" in output_of(ctx) and output_of(ctx).rstrip().endswith("Aucun problème relevé."), output_of(ctx)
    ctx = context(program, runner=runner)
    assert linux_install.main(["repair"], ctx) == 0, screen(ctx)
    assert "n'appartient pas" not in screen(ctx), screen(ctx)
    ctx = context(program, runner=runner)
    assert linux_install.main(["modele", "qwen3.5:2b"], ctx) == 0, screen(ctx)
    assert "n'appartient pas" not in screen(ctx), screen(ctx)
    groups = desktop_groups(entry.read_text(encoding="utf-8"))
    assert "Desktop Action modele-qwen3-5-4b" in groups and "Desktop Action modele-qwen3-5-2b" not in groups, list(groups)
    assert linux_install.desktop_owner(entry) == str(destination) and linux_install.command_owner(command) == str(destination)
    assert registry(isolated_home) == [str(destination)]


@pytest.mark.parametrize("by_kit_id", [False, True], ids=["sans-option", "kit-id"])
def test_removing_the_previous_version_from_a_program_reached_through_a_link_updates_the_pointer(kit, tmp_path, monkeypatch, isolated_home,
                                                                                                  by_kit_id):
    # U6-01 (b), R5S-01 (3) : « <nouveau programme>/installer.sh uninstall » (ou la commande de fin de mise à jour, « … uninstall
    # --kit-id <ancienne> ») supprimait l'ancienne version sans la retirer du pointeur ; status proposait encore un retour
    # arrière devenu impossible, et le bloc de fin omettait la racine des données.
    destination, real, data_root, runner = installed_through_a_link(kit, tmp_path)
    update = context(second_kit(tmp_path, monkeypatch), runner=runner)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], update) == 0, screen(update)
    pointer = pointer_of(destination)
    old, new = pointer["previous"], pointer["current"]
    ctx = context(physical(new["program"]), runner=runner)
    assert linux_install.main(["uninstall", *(["--kit-id", old["kit_id"]] if by_kit_id else []), "--oui"], ctx) == 0, screen(ctx)
    assert pointer_of(destination)["previous"] is None and not physical(old["program"]).exists()
    assert pointer_of(destination)["current"]["kit_id"] == new["kit_id"] and physical(new["program"]).is_dir()
    assert f"Données : {data_root} (" in output_of(ctx), output_of(ctx)
    status = context(physical(new["program"]), runner=runner)
    assert linux_install.main(["status"], status) == 0, screen(status)
    assert "Version précédente" not in output_of(status) and "rollback" not in output_of(status), output_of(status)


@pytest.mark.parametrize("option", [["--tout"], []], ids=["tout", "sans-option"])
def test_uninstalling_from_a_program_reached_through_a_link_stops_it_and_updates_the_pointer_first(kit, tmp_path, isolated_home, option):
    # R5S-01 (1) et (2), U6-01 (c) : « <programme>/installer.sh uninstall --tout » rendait « Désinstallation terminée » sans
    # status ni down, supprimait le dossier de la version que le pointeur désignait encore, et laissait lanceur, entrée de menu,
    # commande et registre. Instance de cette version en marche (ProgrammeSimule) : arrêtée avant le retrait.
    destination, real, data_root, runner = installed_through_a_link(kit, tmp_path)
    current = pointer_of(destination)["current"]
    runner.running[current["program"]] = current["profile"]
    runner.last_started = current["program"]
    data_before = inventory(physical(data_root))
    ctx = context(physical(current["program"]), runner=runner)
    assert linux_install.main(["uninstall", *option, "--oui"], ctx) == 0, screen(ctx)
    assert "status" in runner.commands() and "down" in runner.commands() and not runner.running
    after = pointer_of(destination)
    assert after["current"] is None and after["history"][-1]["event"] == "uninstall" and not physical(current["program"]).exists()
    assert not (destination / "atelier").exists() and not (destination / "atelier-documentaire.svg").exists()
    assert not (applications(isolated_home) / "atelier-documentaire.desktop").exists() and not (isolated_home / ".local/bin/atelier").exists()
    assert registry(isolated_home) == [] and inventory(physical(data_root)) == data_before


def test_a_vanished_version_folder_is_removed_from_the_pointer_with_the_physical_destination(kit, tmp_path, isolated_home):
    # R5S-01 (4), U4-02 : depuis le kit, « uninstall --tout --destination <chemin physique> » refusait (« … n'est pas un dossier
    # d'installation (absent ou lien) », code 3) ; seule la graphie reliée réparait le pointeur.
    destination, real, _, runner = installed_through_a_link(kit, tmp_path)
    current = pointer_of(destination)["current"]
    shutil.rmtree(physical(current["program"]))
    ctx = context(kit, runner=runner)
    assert linux_install.main(["uninstall", "--tout", "--destination", str(real), "--oui"], ctx) == 0, screen(ctx)
    assert f"Retirer du pointeur : {current['kit_id']}" in output_of(ctx) and pointer_of(destination)["current"] is None


def test_the_repair_procedure_works_with_the_physical_destination_that_installer_sh_cites(kit, tmp_path, isolated_home):
    # U6-01 (c), preuve 08 : le refus de <programme>/installer.sh cite « status --destination <chemin physique> ». Suivie avec
    # cette destination, la procédure 10.4 retirait le programme sans mettre le pointeur à jour (étape 3), puis la reprise était
    # refusée (« Un atelier est déjà installé dans … », étape 4) : l'atelier restait sans programme. Elle va maintenant au bout,
    # données actives et document importé après la sauvegarde gardés.
    import importlib

    # Lecture de la procédure telle qu'écrite (blocs sh de la section 10.4) par les aides de test_docs_linux_kit, chargées à
    # l'exécution : ce module d'essais de la documentation n'entre pas dans le contrôle de types de celui-ci.
    docs = importlib.import_module("tests.unit.test_docs_linux_kit")
    destination, real, data_root, runner = installed_through_a_link(kit, tmp_path, start=True)
    program = Path(pointer_of(destination)["current"]["program"])
    saver = context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "sauvegarder"], saver) == 0, screen(saver)
    write(data_root, docs.ECRIT_APRES, "document importé après la sauvegarde")
    (program / docs.FICHIER_PERDU).unlink()
    cited = os.path.realpath(program.parent)  # destination physique, celle qu'install.sh cite (dirname du chemin physique)
    assert cited == str(real) != str(destination)
    commands = docs.procedure(docs.DEPANNAGE, docs.REPAIR_TITLE, {"<destination>": cited, "<données>": str(data_root)})
    for words in commands:
        code, ctx = docs.run_documented(sys.modules[__name__], words, kit, runner)
        assert code == linux_install.EXIT_OK, f"« {' '.join(words)} » : {screen(ctx)}"
    pointer = pointer_of(destination)
    kit_id = manifest_of(kit)["kit_id"]
    assert pointer["current"]["kit_id"] == kit_id and physical(pointer["current"]["data_root"]) == physical(data_root)
    assert (physical(real) / kit_id / docs.FICHIER_PERDU).is_file() and (data_root / docs.ECRIT_APRES).is_file()
    entry = applications(isolated_home) / "atelier-documentaire.desktop"
    assert physical(linux_install.desktop_owner(entry)) == physical(real) and len(registry(isolated_home)) == 1
