"""Installateur Linux (R26-KIT-01) : précontrôles sans écriture, séquence d'installation, mise à jour, bascule atomique,
retour arrière, désinstallation gardée et lanceur `atelier`.

Doubles nommés : `PosteSimule` remplace les lectures du poste (architecture, glibc, noyau, mémoire, espace, système de
fichiers, setpriv, ldd) ; `ProgrammeSimule` remplace les commandes lancées (rag.sh, bootstrap.sh, compileall,
linux_profiles.py) et consigne leur ordre. Le kit, la copie, les liens, la réécriture du préfixe de CPython, le pointeur et
le lanceur sont réels, sous TMPDIR.
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("installateur Linux", allow_module_level=True)

from tests.unit.test_dist_linux_kit import PYTHON_KEY, fake_readelf, git, make_repository, write  # noqa: E402
from tools.dist import linux_install, linux_kit  # noqa: E402
from tools.dist.linux_install import Completed  # noqa: E402

SYSCONFIG = f".runtime/python/{PYTHON_KEY}/lib/python3.12/_sysconfigdata__linux_aarch64-linux-gnu.py"
GREEN = {"verdict": {"level": "vert", "summary": "Atelier prêt", "rubrics": [{"level": "vert", "rubric": "services", "message": "ok"}]}}


class PosteSimule:
    """Lectures du poste ; `ldd_calls` consigne les exécutables passés à ldd."""

    def __init__(self, **values):
        self.values = {"machine": "aarch64", "glibc": "2.31", "kernel": "5.10.120-tegra", "memory": 61.0, "free": 10**12,
                       "fstype": "ext4", "noexec": False, "setpriv": "/usr/bin/setpriv",
                       "ldd": Completed(0, "\tlibjpeg.so.8 => /lib/aarch64-linux-gnu/libjpeg.so.8 (0x0)\n"), **values}
        self.ldd_calls = []

    def machine(self):
        return self.values["machine"]

    def glibc(self):
        return self.values["glibc"]

    def kernel(self):
        return self.values["kernel"]

    def memory_total_gib(self):
        return self.values["memory"]

    def free_bytes(self, path):
        return self.values["free"]

    def filesystem(self, path):
        return {"mount": "/media/x", "fstype": self.values["fstype"], "noexec": self.values["noexec"]}

    def setpriv(self):
        return self.values["setpriv"]

    def ldd(self, binary):
        self.ldd_calls.append(binary)
        return self.values.get("ldd_" + Path(binary).name, self.values["ldd"])

    def shared_libraries(self):
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


class Tout:
    """Cache du chargeur qui connaît toutes les bibliothèques demandées."""

    def __contains__(self, name):
        return True


REAL_PROFILES_SCRIPT = linux_kit.ROOT / "tools/dist/linux_profiles.py"


def free_ports(count: int = 3) -> list[int]:
    """Ports de boucle locale libres à l'instant (aucun service de l'instance principale n'est touché)."""
    import socket

    sockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(count)]
    try:
        for item in sockets:
            item.bind(("127.0.0.1", 0))
        return [item.getsockname()[1] for item in sockets]
    finally:
        for item in sockets:
            item.close()


class ProgrammeSimule:
    """Commandes du programme installé : rag.sh, bootstrap.sh et compileall simulés ; linux_profiles.py exécuté réellement
    (Python de l'environnement du dépôt, script réel). `init-profile` emploie le vrai `write_user_profile` ; `restore`
    écrit `restored-profile.yaml` comme services/runtime/backup.py (données à la racine, ports 8795/6343/11445, sans
    `qdrant.storage_dir`). Chaque appel garde (programme, commande, présence du nouveau dossier)."""

    def __init__(self, *, watch: Path | None = None, results: dict | None = None, locations: dict | None = None,
                 last_started: str | None = None):
        self.calls: list[tuple[str, str, bool]] = []
        self.watch = watch
        self.results = results or {}
        self.locations = locations
        self.running: dict[str, str] = {}
        # Programme dont le superviseur a écrit en dernier runtime.json dans les données (status le rend).
        self.last_started = last_started

    def run(self, argv, *, cwd=None, timeout=None):
        program = Path(argv[0]).parent if argv[0].endswith((".sh",)) else Path(cwd)
        name = Path(argv[0]).name
        if name == "rag.sh":
            command = argv[1]
        elif name == "bootstrap.sh":
            command = "bootstrap"
            write(program, ".venv/bin/python", "#!/bin/sh\n", executable=True)
        elif argv[1:3] == ["-m", "compileall"]:
            command = "compileall"
        else:
            command = argv[4]  # linux_profiles.py <commande>
        self.calls.append((program.name, command, bool(self.watch and self.watch.exists())))
        scripted = self.results.get((program.name, command), self.results.get(command))
        if callable(scripted):
            scripted = scripted(argv)
        if scripted is not None:
            return Completed(scripted.get("_rc", 0), json.dumps({k: v for k, v in scripted.items() if k != "_rc"}))
        if argv[3:4] and argv[3].endswith("linux_profiles.py"):
            if self.locations is not None and command == "paths":
                return Completed(0, json.dumps({"status": "read", "model": "qwen3.5:2b", "source_model": "qwen3.5:2b",
                                                "locations": self.locations}))
            real = subprocess.run([sys.executable, *argv[1:3], str(REAL_PROFILES_SCRIPT), *argv[4:]], cwd=cwd, capture_output=True,
                                  text=True, env={**os.environ, "PYTHONUTF8": "1"}, check=False, timeout=120)
            return Completed(real.returncode, real.stdout, real.stderr)
        return self.default(program, command, argv)

    def default(self, program, command, argv):
        import yaml

        value = lambda option: argv[argv.index(option) + 1]  # noqa: E731
        if command == "init-profile":
            from services.runtime.profile_setup import write_user_profile

            base = program / ("config/local16-4b.yaml" if "--model" in argv and value("--model") == "qwen3.5:4b" else "config/local16.yaml")
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
            if self.last_started:
                result["supervisor"] = {"executable": f"{self.last_started}/.runtime/python/{PYTHON_KEY}/bin/python3.12"}
        elif command == "selftest":
            result = {"level": "vert", "summary": "contrôle réel réussi", "steps": []}
        elif command == "open":
            result = {"url": "http://127.0.0.1:8785/ouvrir#jeton"} if "--no-browser" in argv else {"opened_in_browser": True}
        elif command == "backup":
            profile = Path(value("--profile"))
            backup = program.parent.parent / "sauvegardes" / f"b{len(self.calls)}"
            write(backup / "config", "profile.yaml", profile.read_text(encoding="utf-8"))
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
            write(target, "restored-profile.yaml", yaml.safe_dump(profile, sort_keys=False))
            result = {"state": "restored_storage_verified"}
        else:
            result = {}
        return Completed(0, json.dumps(result))

    def commands(self, program=None):
        return [command for name, command, _ in self.calls if program is None or name == program]


class Horloge:
    def __init__(self):
        import datetime as dt

        self.moment = dt.datetime(2026, 10, 6, 20, 0, tzinfo=dt.UTC)

    def __call__(self):
        import datetime as dt

        self.moment += dt.timedelta(seconds=1)
        return self.moment


def make_kit(tmp_path: Path, monkeypatch, *, name="kit", repository=None, **options) -> Path:
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: None)
    repository = repository or make_repository(tmp_path)
    kit = tmp_path / name
    linux_kit.build_linux_kit(kit, repository, platform="linux-aarch64", home=str(tmp_path / "maison"), **options)
    return kit


def context(kit: Path, runner=None, probe=None) -> linux_install.Context:
    return linux_install.Context(kit=kit, runner=runner or ProgrammeSimule(), probe=probe or PosteSimule(), out=io.StringIO(),
                                 clock=Horloge())


def install(ctx, destination, data_root, *extra):
    return linux_install.main(["install", "--destination", str(destination), "--data-root", str(data_root), *extra], ctx)


@pytest.fixture
def kit(tmp_path, monkeypatch):
    return make_kit(tmp_path, monkeypatch)


# --- Précontrôles ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("values", "message"), [
    ({"machine": "x86_64"}, "ce kit vise aarch64, ce poste est en x86_64"),
    ({"glibc": "2.28"}, "glibc 2.28 trop ancienne : 2.29 ou plus récente exigée"),
    ({"glibc": None}, "glibc introuvable"),
    ({"kernel": "4.9.253-tegra"}, "noyau 4.9.253-tegra"),
    ({"memory": 7.6}, "7.6 Gio de mémoire"),
    ({"setpriv": None}, "setpriv (util-linux) absent"),
    ({"free": 2 * 1024**3}, "espace insuffisant"),
    ({"fstype": "vfat"}, "destination sur vfat"),
    ({"noexec": True}, "monté noexec"),
], ids=["arch", "glibc", "musl", "noyau", "memoire", "setpriv", "espace", "vfat", "noexec"])
def test_prechecks_refuse_before_any_write(kit, tmp_path, values, message):
    ctx = context(kit, probe=PosteSimule(**values))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    output = ctx.out.getvalue()
    assert "Précontrôles refusés, rien n'a été écrit" in output and message in output
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


@pytest.mark.parametrize(("values", "message"), [
    ({"ldd": Completed(0, "\tlibjpeg.so.8 => not found\n")}, "bibliothèques système de Tesseract manquantes"),
    ({"ldd": Completed(1, "", "version `GLIBCXX_3.4.26' not found (required by tesseract)")}, "GLIBCXX_3.4.26"),
], ids=["ldd-absente", "ldd-glibcxx"])
def test_system_checks_after_verification_refuse_before_any_write(kit, tmp_path, values, message):
    ctx = context(kit, probe=PosteSimule(**values))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    output = ctx.out.getvalue()
    assert "Contrôles du système refusés, rien n'a été écrit" in output and message in output and "[ok] kit" in output
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists() and ctx.runner.calls == []


def test_opencv_without_libgl_on_the_host_is_refused_before_any_write(kit, tmp_path):
    ctx = context(kit, probe=PosteSimule(**{"ldd_cv2.abi3.so": Completed(0, "\tlibGL.so.1 => not found\n")}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    output = ctx.out.getvalue()
    assert "bibliothèques système de cv2.abi3.so manquantes ou trop anciennes (libGL.so.1 => not found)" in output and "libGL.so.1" in output
    assert [path.name for path in ctx.probe.ldd_calls] == ["tesseract", "cv2.abi3.so"]
    assert not (tmp_path / "programmes").exists()


def test_ldd_never_runs_on_an_altered_tesseract(kit, tmp_path):
    (kit / linux_kit.TESSERACT_BINARY).write_bytes(b"\x7fELF autre")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Kit non conforme" in ctx.out.getvalue() and ctx.probe.ldd_calls == []


@pytest.mark.parametrize(("destination", "data_root", "message"), [
    ("programmes", "programmes/donnees", "imbriquées"),
    ("donnees/programmes", "donnees", "imbriquées"),
    ("kit/programmes", "donnees", "dans le kit"),
])
def test_destination_and_data_root_must_be_distinct_and_outside_the_kit(kit, tmp_path, destination, data_root, message):
    ctx = context(kit)
    assert install(ctx, tmp_path / destination, tmp_path / data_root) == 1
    assert message in ctx.out.getvalue() and ctx.runner.calls == []


def test_an_existing_profile_or_installation_is_never_replaced(kit, tmp_path):
    write(tmp_path, "donnees/profile.yaml", "schema_version: 2\n")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Un profil existe déjà" in ctx.out.getvalue() and not (tmp_path / "programmes").exists()
    write(tmp_path, "programmes/installation.json", json.dumps({"format": linux_install.POINTER_FORMAT, "current": {"kit_id": "x"}}))
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "autres") == 1
    assert "utiliser la sous-commande update" in ctx.out.getvalue()


# --- Installation ---------------------------------------------------------------------------------------------------------

def test_install_runs_the_whole_sequence_and_switches_atomically(kit, tmp_path):
    ctx = context(kit)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(ctx, destination, data_root) == 0, ctx.out.getvalue()
    manifest = json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))
    program = destination / manifest["kit_id"]
    assert ctx.runner.commands() == ["bootstrap", "compileall", "init-profile", "derive", "doctor", "up", "doctor", "selftest", "open"]
    # Copie réelle : liens recréés, bit x, préfixe de CPython réécrit vers le programme installé.
    assert os.readlink(program / ".runtime/bin/ollama-0.35.0/lib/ollama/libggml.so.0") == "libggml.so.0.24.0"
    assert os.access(program / linux_kit.TESSERACT_BINARY, os.X_OK)
    prefix = str((program / f".runtime/python/{PYTHON_KEY}").resolve())
    assert (program / SYSCONFIG).read_text(encoding="utf-8") == f"build_time_vars = {{'prefix': '{prefix}', 'LIBDIR': '{prefix}/lib', 'CC': 'cc'}}\n"
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    current = pointer["current"]
    assert current["kit_id"] == manifest["kit_id"] and current["program"] == str(program) and pointer["previous"] is None
    assert current["profiles"] == {"qwen3.5:2b": str(data_root / "profile.yaml"), "qwen3.5:4b": str(data_root / "profile-qwen3.5-4b.yaml")}
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
    assert install(ctx, tmp_path / "p", tmp_path / "donnees", "--model", "qwen3.5:4b", "--ports", ports,
                   "--qdrant-storage", str(tmp_path / "q"), "--no-start") == 0, ctx.out.getvalue()
    assert seen["argv"][1:] == ["init-profile", "--target", str(tmp_path / "donnees"), "--model", "qwen3.5:4b",
                                "--qdrant-storage", str(tmp_path / "q"), "--ports", ports]
    assert ctx.runner.commands() == ["bootstrap", "compileall", "init-profile", "derive", "doctor"]
    pointer = json.loads((tmp_path / "p/installation.json").read_text(encoding="utf-8"))
    assert pointer["current"]["model"] == "qwen3.5:4b" and pointer["current"]["started_on_data"] is False
    assert pointer["current"]["profiles"]["qwen3.5:2b"] == str(tmp_path / "donnees/profile-qwen3.5-2b.yaml")


def test_a_red_doctor_stops_before_the_switch_and_removes_what_this_run_created(kit, tmp_path):
    red = {"verdict": {"level": "rouge", "summary": "Bloqué", "rubrics": [{"level": "rouge", "rubric": "ports", "message": "Port 8785 occupé.",
                                                                       "action": "Choisir d'autres ports avec --ports."}]}}
    ctx = context(kit, runner=ProgrammeSimule(results={"doctor": red}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Vérification refusée : Port 8785 occupé. Choisir d'autres ports avec --ports." in ctx.out.getvalue()
    assert [path.name for path in (tmp_path / "programmes").iterdir() if path.name != linux_install.LOCK] == []
    assert not (tmp_path / "donnees/profile.yaml").exists() and not (tmp_path / "donnees/profile-qwen3.5-4b.yaml").exists()
    report = json.loads(next((tmp_path / "donnees").glob("install-*.json")).read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["new_program_removed"]


def test_a_failed_derived_profile_removes_the_profile_init_profile_created(kit, tmp_path):
    ctx = context(kit, runner=ProgrammeSimule(results={"derive": {"_rc": 1, "status": "failed", "message": "port occupé"}}))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Profil qwen3.5:4b non dérivable : port occupé" in ctx.out.getvalue()
    assert not (tmp_path / "donnees/profile.yaml").exists() and [p.name for p in (tmp_path / "programmes").iterdir() if p.name != linux_install.LOCK] == []
    assert install(context(kit), tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0


def test_the_menu_entry_is_written_only_on_request_with_a_quoted_exec(kit, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "maison"))
    ctx = context(kit)
    destination = tmp_path / "pro$grammes \"x\""
    assert install(ctx, destination, tmp_path / "donnees", "--no-start", "--menu", str(tmp_path / "menu")) == 0, ctx.out.getvalue()
    entry = (tmp_path / "menu/atelier-documentaire.desktop").read_text(encoding="utf-8")
    assert "Type=Application" in entry and "Terminal=true" in entry
    assert f'Exec="{tmp_path}/pro\\\\$grammes \\\\"x\\\\"/atelier" ouvrir' in entry
    assert linux_install.desktop_quote("/a b/c") == '"/a b/c"'
    ctx = context(kit)
    assert install(ctx, tmp_path / "autres", tmp_path / "donnees2", "--no-start") == 0
    assert [path.name for path in (tmp_path / "menu").iterdir()] == ["atelier-documentaire.desktop"]
    assert not (tmp_path / "maison/.local/share/applications").exists()


# --- Mise à jour, bascule et retour arrière -------------------------------------------------------------------------------

def second_kit(tmp_path, monkeypatch) -> Path:
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", "VERSION = 'suivante'\n")
    git(repository, "commit", "-q", "-am", "version suivante")
    return make_kit(tmp_path, monkeypatch, name="kit-b", repository=repository)


def test_update_saves_verifies_and_stops_the_current_version_before_copying(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    first = context(kit)
    assert install(first, destination, data_root) == 0
    old = json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    new_id = json.loads((kit_b / "kit-manifest.json").read_text(encoding="utf-8"))["kit_id"]
    runner = ProgrammeSimule(watch=destination / new_id)
    ctx = context(kit_b, runner=runner)
    assert linux_install.main(["update", "--destination", str(destination)], ctx) == 0, ctx.out.getvalue()
    before_copy = [(name, command) for name, command, exists in runner.calls if not exists]
    assert before_copy == [(old["kit_id"], "status"), (old["kit_id"], "status"), (old["kit_id"], "up"), (old["kit_id"], "backup"),
                           (old["kit_id"], "verify"), (old["kit_id"], "down")]
    # status juste avant la bascule : aucune instance relancée sur les données depuis l'arrêt.
    assert runner.commands(new_id) == ["bootstrap", "compileall", "doctor", "status", "up", "doctor", "selftest", "open"]
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    assert pointer["current"]["kit_id"] == new_id and pointer["previous"]["kit_id"] == old["kit_id"]
    assert pointer["current"]["profile"] == old["profile"] and (Path(pointer["current"]["backup"]) / "config/profile.yaml").is_file()
    assert f"version {new_id}." in (destination / "atelier").read_text(encoding="utf-8")


@pytest.mark.parametrize(("failure", "expected"), [
    ({("up"): {"status": "failed", "message": "port occupé"}}, ["status", "status", "up"]),
    ({("verify"): {"state": "failed", "message": "empreinte"}}, ["status", "status", "up", "backup", "verify"]),
])
def test_an_update_without_a_verified_backup_copies_nothing(kit, tmp_path, monkeypatch, failure, expected):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    before = (destination / "installation.json").read_bytes()
    kit_b = second_kit(tmp_path, monkeypatch)
    ctx = context(kit_b, runner=ProgrammeSimule(results=failure))
    assert linux_install.main(["update", "--destination", str(destination)], ctx) == 1
    assert ctx.runner.commands() == expected and "rien n'a été installé" in ctx.out.getvalue().lower()
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
    assert sorted(path.name for path in destination.iterdir() if path.is_file()) == [linux_install.LOCK, "atelier", "installation.json"]


def test_rollback_before_any_start_only_switches_back(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    old = json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    updater = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination), "--no-start"], updater) == 0
    # Dernier superviseur sur les données : celui de la version en place, démarrée pour la sauvegarde.
    assert updater.runner.last_started == old["program"]
    ctx = context(kit, runner=ProgrammeSimule(last_started=updater.runner.last_started))
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 0, ctx.out.getvalue()
    assert ctx.runner.commands() == ["status", "status"]
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    assert pointer["current"]["kit_id"] == old["kit_id"] and pointer["current"]["profile"] == old["profile"]
    assert pointer["previous"]["rolled_back"] is True
    assert f"version {old['kit_id']}." in (destination / "atelier").read_text(encoding="utf-8")


def test_rollback_after_a_start_restores_the_backup_with_the_previous_version(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root) == 0
    old = json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    updater = context(kit_b)
    assert linux_install.main(["update", "--destination", str(destination)], updater) == 0
    backup = json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]["backup"]
    runner = ProgrammeSimule(last_started=updater.runner.last_started)
    runner.running = dict(updater.runner.running)
    ctx = context(kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 0, ctx.out.getvalue()
    new_id = json.loads((kit_b / "kit-manifest.json").read_text(encoding="utf-8"))["kit_id"]
    assert [(name, command) for name, command, _ in runner.calls] == [
        (new_id, "status"), (new_id, "down"), (new_id, "paths"), (old["kit_id"], "restore"), (old["kit_id"], "ports"), (old["kit_id"], "paths"),
        (old["kit_id"], "derive")]
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    restored = pointer["current"]
    assert restored["kit_id"] == old["kit_id"] and restored["profile"].endswith("restored-profile.yaml")
    assert Path(restored["data_root"]).name.startswith("donnees-retour-") and restored["restored_from"] == backup
    assert (data_root / "profile.yaml").exists()


def test_rollback_restores_when_the_supervisor_of_the_new_version_wrote_last_without_the_flag(kit, tmp_path, monkeypatch):
    # Version démarrée hors du lanceur (rag.sh up --profile …) : le pointeur l'ignore, l'état de l'instance le révèle.
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--no-start"], context(kit_b)) == 0
    new = json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]
    assert new["started_on_data"] is False
    ctx = context(kit, runner=ProgrammeSimule(last_started=new["program"]))
    assert linux_install.main(["rollback", "--destination", str(destination), "--restore-target", str(tmp_path / "retour")], ctx) == 0
    assert ctx.runner.commands() == ["status", "status", "paths", "restore", "ports", "paths", "derive"]
    assert json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]["data_root"] == str(tmp_path / "retour")


def test_rollback_without_backup_after_a_start_switches_nothing(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--no-start"], context(kit_b)) == 0
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    pointer["current"].pop("backup")
    pointer["current"]["started_on_data"] = True
    (destination / "installation.json").write_text(json.dumps(pointer), encoding="utf-8")
    ctx = context(kit)
    assert linux_install.main(["rollback", "--destination", str(destination)], ctx) == 1
    assert "aucune sauvegarde n'est associée" in ctx.out.getvalue()
    assert json.loads((destination / "installation.json").read_text(encoding="utf-8")) == pointer


# --- Désinstallation ------------------------------------------------------------------------------------------------------

def installed(kit, tmp_path, *extra):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    ctx = context(kit)
    assert install(ctx, destination, data_root, *extra) == 0
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    return destination, data_root, pointer["current"], ctx.runner


def uninstall(kit, destination, kit_id, runner=None):
    ctx = context(kit, runner=runner)
    return linux_install.main(["uninstall", "--destination", str(destination), "--kit-id", kit_id], ctx), ctx


def test_uninstall_stops_this_version_removes_it_without_following_links_and_keeps_the_data(kit, tmp_path):
    destination, data_root, current, runner = installed(kit, tmp_path)
    outside = write(tmp_path, "ailleurs/precieux.txt", "à garder")
    os.symlink(outside.parent, Path(current["program"]) / "lien-vers-ailleurs")
    code, ctx = uninstall(kit, destination, current["kit_id"], runner)
    assert code == 0, ctx.out.getvalue()
    # Deux profils (2B et 4B, mêmes données) : chacun contrôlé, l'instance de cette version arrêtée une fois.
    assert runner.commands()[-5:] == ["paths", "status", "down", "paths", "status"]
    assert not Path(current["program"]).exists() and outside.read_text(encoding="utf-8") == "à garder"
    assert (data_root / "profile.yaml").exists() and not (destination / "atelier").exists()
    pointer = json.loads((destination / "installation.json").read_text(encoding="utf-8"))
    assert pointer["current"] is None and pointer["history"][-1]["event"] == "uninstall"
    assert list(destination.glob("uninstall-*.json"))


def test_uninstall_refuses_a_link_a_folder_without_markers_or_another_version(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    os.symlink(current["program"], destination / "alias")
    assert uninstall(kit, destination, "alias")[0] == 1
    write(destination, "faux/README.md", "")
    code, ctx = uninstall(kit, destination, "faux")
    assert code == 1 and "kit-manifest.json absent" in ctx.out.getvalue()
    (destination / "faux/kit-manifest.json").write_text(json.dumps({"kit_id": "autre"}), encoding="utf-8")
    write(destination, "faux/SHA256SUMS", "")
    code, ctx = uninstall(kit, destination, "faux")
    assert code == 1 and "ne porte pas la version faux" in ctx.out.getvalue()
    assert Path(current["program"]).is_dir() and (destination / "faux/README.md").exists()


def test_uninstall_refuses_a_profile_that_writes_into_the_program(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    inside = {"app.data_dir": f"{current['program']}/.runtime/data", "runtime.backups_dir": "/ailleurs/backups"}
    code, ctx = uninstall(kit, destination, current["kit_id"], ProgrammeSimule(locations=inside))
    assert code == 1 and "écrit dans le dossier programme (app.data_dir" in ctx.out.getvalue()
    assert Path(current["program"]).is_dir() and (destination / "atelier").exists()


# --- Lanceur et état ------------------------------------------------------------------------------------------------------

def test_the_launcher_actions_always_use_a_profile_of_the_data_root(kit, tmp_path):
    destination, data_root, current, _ = installed(kit, tmp_path, "--no-start")
    program = Path(current["program"])
    runner = ProgrammeSimule()
    ctx = context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--modele", "qwen3.5:4b", "--no-browser"], ctx) == 0
    assert "Lien à usage unique : http://127.0.0.1:8785/ouvrir#jeton" in ctx.out.getvalue()
    assert runner.commands() == ["up", "open"] and runner.running[str(program)] == str(data_root / "profile-qwen3.5-4b.yaml")
    assert json.loads((destination / "installation.json").read_text(encoding="utf-8"))["current"]["started_on_data"] is True
    for action, command in (("arreter", "down"), ("diagnostic", "doctor"), ("etat", "status"), ("sauvegarder", "backup")):
        ctx = context(program, runner=ProgrammeSimule())
        assert linux_install.main(["run", "--destination", str(destination), action], ctx) == 0
        assert ctx.runner.commands() == [command]
    stale = context(kit)
    assert linux_install.main(["run", "--destination", str(destination)], stale) == 1 and "Lanceur périmé" in stale.out.getvalue()


def test_status_reports_a_launcher_of_another_version(kit, tmp_path):
    destination, _, current, _ = installed(kit, tmp_path, "--no-start")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 0
    assert json.loads(ctx.out.getvalue())["versions"] == [current["kit_id"]]
    (destination / "atelier").write_text("#!/bin/sh\n# version autre.\n", encoding="utf-8")
    ctx = context(kit)
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == 1
    assert "lanceur absent ou d'une autre version" in ctx.out.getvalue()
