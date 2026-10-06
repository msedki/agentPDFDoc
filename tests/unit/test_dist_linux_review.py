"""Constats de la revue indépendante de R26-KIT-01 (M1 à M3, m1 à m10, remarques) : chaque scénario reproduit sur des
arbres factices sous TMPDIR, avec les doubles nommés de test_dist_linux_install (`PosteSimule`, `ProgrammeSimule`) et de
vrais appels à tools/dist/linux_profiles.py (profils réels du dépôt, `write_user_profile` réel).
"""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("installateur Linux", allow_module_level=True)

from tests.unit.test_dist_linux_install import (  # noqa: E402
    PosteSimule,
    ProgrammeSimule,
    context,
    free_ports,
    install,
    make_kit,
    second_kit,
)
from tests.unit.test_dist_linux_kit import (  # noqa: E402
    PYTHON_KEY,
    elf_header,
    fake_readelf,
    git,
    link,
    make_repository,
    write,
)
from tools.dist import linux_install, linux_kit  # noqa: E402
from tools.dist.linux_install import Completed  # noqa: E402


def pointer(destination: Path) -> dict:
    return json.loads((destination / "installation.json").read_text(encoding="utf-8"))


def kit_id(kit: Path) -> str:
    return json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))["kit_id"]


def update(kit, destination, runner=None, *extra):
    ctx = context(kit, runner=runner)
    return linux_install.main(["update", "--destination", str(destination), *extra], ctx), ctx


def rollback(kit, destination, runner=None):
    ctx = context(kit, runner=runner)
    return linux_install.main(["rollback", "--destination", str(destination)], ctx), ctx


def third_kit(tmp_path, monkeypatch, name="kit-c", **options) -> Path:
    repository = tmp_path / "depot"
    write(repository, "services/api/main.py", f"VERSION = '{name}'\n")
    git(repository, "commit", "-q", "-am", name)
    return make_kit(tmp_path, monkeypatch, name=name, repository=repository, **options)


@pytest.fixture
def kit(tmp_path, monkeypatch):
    return make_kit(tmp_path, monkeypatch)


# --- M1 : bascule transactionnelle ------------------------------------------------------------------------------------

def test_m1_an_unwritable_menu_is_refused_before_any_write(kit, tmp_path):
    menu = tmp_path / "menu"
    menu.mkdir()
    menu.chmod(0o555)
    try:
        ctx = context(kit)
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start", "--menu", str(menu)) == 1
    finally:
        menu.chmod(0o755)
    assert "--menu" in ctx.out.getvalue() and "rien n'a été écrit" in ctx.out.getvalue()
    assert not (tmp_path / "programmes").exists() and not (tmp_path / "donnees").exists()


def failing_once(monkeypatch, name: str):
    real = os.replace
    state = {"armed": True}

    def replace(source, target):
        if state["armed"] and Path(target).name == name:
            state["armed"] = False
            raise OSError("écriture refusée (simulée)")
        return real(source, target)

    monkeypatch.setattr(os, "replace", replace)


def test_m1_a_failure_after_the_pointer_keeps_the_designated_program_and_repair_restores_the_launcher(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    failing_once(monkeypatch, "atelier")
    ctx = context(kit)
    assert install(ctx, destination, tmp_path / "donnees", "--no-start") == 1
    current = pointer(destination)["current"]
    assert Path(current["program"]).is_dir() and current["kit_id"] == kit_id(kit)
    output = ctx.out.getvalue()
    assert f"La version {kit_id(kit)} est la version courante" in output and "repair" in output
    repaired = context(kit)
    assert linux_install.main(["repair", "--destination", str(destination)], repaired) == 0, repaired.out.getvalue()
    assert f"version {kit_id(kit)}." in (destination / "atelier").read_text(encoding="utf-8")


def test_m1_an_update_message_names_the_version_the_pointer_designates(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    failing_once(monkeypatch, "atelier")
    code, ctx = update(kit_b, destination, None, "--no-start")
    assert code == 1 and pointer(destination)["current"]["kit_id"] == kit_id(kit_b)
    assert Path(pointer(destination)["current"]["program"]).is_dir()
    assert f"La version {kit_id(kit_b)} est la version courante" in ctx.out.getvalue()
    assert "reste la version courante" not in ctx.out.getvalue()


# --- M2 : retour arrière avec restauration, puis mise à jour ----------------------------------------------------------------

def test_m2_an_update_after_a_restoring_rollback_succeeds_and_keeps_the_model_choice(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    ports = free_ports()
    assert install(context(kit), destination, data_root, "--ports", ",".join(map(str, ports))) == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    code, updater = update(kit_b, destination)
    assert code == 0
    runner = ProgrammeSimule(last_started=updater.runner.last_started)
    runner.running = dict(updater.runner.running)
    code, ctx = rollback(kit, destination, runner)
    assert code == 0, ctx.out.getvalue()
    restored = pointer(destination)["current"]
    assert set(restored["profiles"]) == {"qwen3.5:2b", "qwen3.5:4b"}, restored
    import yaml

    profile = yaml.safe_load(Path(restored["profile"]).read_text(encoding="utf-8"))
    assert [profile["app"]["port"], profile["qdrant"]["url"], profile["llm"]["base_url"]] == [
        ports[0], f"http://127.0.0.1:{ports[1]}", f"http://127.0.0.1:{ports[2]}"]
    assert "stockage Qdrant" in ctx.out.getvalue()
    kit_c = third_kit(tmp_path, monkeypatch)
    code, ctx = update(kit_c, destination, None, "--no-start")
    assert code == 0, ctx.out.getvalue()
    assert set(pointer(destination)["current"]["profiles"]) == {"qwen3.5:2b", "qwen3.5:4b"}


def test_m5_a_profile_left_by_a_rollback_is_reused_or_refused_before_the_backup(tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    small = make_kit(tmp_path, monkeypatch, name="kit-2b", models=("2b",))
    assert install(context(small), destination, data_root, "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert update(kit_b, destination, None, "--no-start")[0] == 0
    assert (data_root / "profile-qwen3.5-4b.yaml").is_file()
    assert rollback(small, destination, ProgrammeSimule(last_started=pointer(destination)["previous"]["program"]))[0] == 0
    kit_c = third_kit(tmp_path, monkeypatch)
    code, ctx = update(kit_c, destination, None, "--no-start")
    assert code == 0, ctx.out.getvalue()
    assert pointer(destination)["current"]["profiles"]["qwen3.5:4b"] == str(data_root / "profile-qwen3.5-4b.yaml")
    # Profil laissé, puis modifié à la main : refus dans les précontrôles, avant toute sauvegarde ni copie.
    assert rollback(kit_b, destination, ProgrammeSimule(last_started=pointer(destination)["previous"]["program"]))[0] == 0
    with (data_root / "profile-qwen3.5-4b.yaml").open("a", encoding="utf-8") as stream:
        stream.write("# modifié\nprofile: autre\n")
    kit_d = third_kit(tmp_path, monkeypatch, name="kit-d")
    code, ctx = update(kit_d, destination, None, "--no-start")
    assert code == 1 and "profile-qwen3.5-4b.yaml" in ctx.out.getvalue()
    assert [command for command in ctx.runner.commands() if command in {"up", "backup", "bootstrap"}] == []


# --- M3 : double retour arrière ------------------------------------------------------------------------------------------

def test_m3_a_second_rollback_is_refused_and_the_restored_entry_carries_no_backup(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    assert update(kit_b, destination, None, "--no-start")[0] == 0
    kit_c = third_kit(tmp_path, monkeypatch)
    assert update(kit_c, destination, None, "--no-start")[0] == 0
    last = pointer(destination)["previous"]["program"]
    assert rollback(kit_b, destination, ProgrammeSimule(last_started=last))[0] == 0
    current = pointer(destination)["current"]
    assert current["kit_id"] == kit_id(kit_b) and "backup" not in current
    before = pointer(destination)
    code, ctx = rollback(kit_b, destination, ProgrammeSimule(last_started=last))
    assert code == 1 and "déjà" in ctx.out.getvalue() and pointer(destination) == before


# --- m1 : garde de rag.sh contournable et données sous le programme ---------------------------------------------------------

def installed_tree(tmp_path: Path) -> Path:
    """Programme installé factice : vrai rag.sh, vrai linux_profiles.py et vrais services (lien), Python du dépôt pour le
    garde et interpréteur factice pour le CLI."""
    root = tmp_path / "programme"
    (root / "tools/dist").mkdir(parents=True)
    shutil.copy2(linux_kit.ROOT / "rag.sh", root / "rag.sh")
    shutil.copy2(linux_kit.ROOT / "tools/dist/linux_profiles.py", root / "tools/dist/linux_profiles.py")
    os.symlink(linux_kit.ROOT / "services", root / "services")
    shutil.copytree(linux_kit.ROOT / "config", root / "config")
    (root / "kit-manifest.json").write_text('{"format": "atelier-kit-v2"}\n', encoding="utf-8")
    write(root, ".venv/bin/python", "#!/bin/sh\n"
          f'case "$*" in *linux_profiles.py*) exec {sys.executable} "$@" ;; esac\n'
          "echo '{\"cli\": \"atteint\"}'\n", executable=True)
    return root


def run_rag(root: Path, *args: str):
    return subprocess.run([str(root / "rag.sh"), *args], capture_output=True, text=True, timeout=120, check=False,
                          env={"PATH": "/usr/bin:/bin", "HOME": str(root.parent)})


@pytest.mark.parametrize("profile", ["config/local16.yaml", "{root}/config/local16-4b.yaml", "relatif"])
def test_m1_rag_sh_refuses_any_profile_that_writes_into_the_program(tmp_path, profile):
    root = installed_tree(tmp_path)
    if profile == "relatif":
        import yaml

        data = yaml.safe_load((root / "config/local16.yaml").read_text(encoding="utf-8"))
        data["runtime"] = {key: str(tmp_path / "ailleurs" / key) for key in ("host_lock_path", "backups_dir", "restore_storage_dir",
                                                                              "huggingface_cache_dir")}
        profile = str(write(tmp_path, "profil-utilisateur.yaml", yaml.safe_dump(data)))  # app.data_dir relatif : .runtime/data
    result = run_rag(root, "up", "--profile", profile.format(root=root))
    assert result.returncode == 1 and "cli" not in result.stdout
    assert "dossier du programme" in result.stderr


def test_m1_rag_sh_accepts_a_profile_writing_outside_the_program(tmp_path):
    import yaml

    root = installed_tree(tmp_path)
    data = yaml.safe_load((root / "config/local16.yaml").read_text(encoding="utf-8"))
    data["app"]["data_dir"] = str(tmp_path / "donnees/data")
    data["qdrant"]["storage_dir"] = str(tmp_path / "donnees/q")
    data["runtime"] = {key: str(tmp_path / "donnees" / key) for key in ("host_lock_path", "backups_dir", "restore_storage_dir",
                                                                         "huggingface_cache_dir")}
    profile = write(tmp_path, "donnees/profile.yaml", yaml.safe_dump(data))
    result = run_rag(root, "up", "--profile", str(profile))
    assert result.returncode == 0 and json.loads(result.stdout) == {"cli": "atteint"}, result.stderr


@pytest.mark.parametrize("residue", [".runtime/data/app.sqlite3", ".runtime/control/runtime.json", ".runtime/q/x", ".runtime/qa/y",
                                     "backups/b1/manifest.json"])
def test_m1_uninstall_refuses_a_program_holding_runtime_data(kit, tmp_path, residue):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    program = Path(pointer(destination)["current"]["program"])
    write(program, residue, "données")
    ctx = context(kit)
    assert linux_install.main(["uninstall", "--destination", str(destination), "--kit-id", kit_id(kit)], ctx) == 1
    assert "données d'exécution dans le dossier programme" in ctx.out.getvalue() and (program / residue).exists()


# --- m2 : contrôles système ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("values", "message"), [
    ({"glibcxx": "3.4.25"}, "GLIBCXX 3.4.25"),
    ({"libraries": {"libc.so.6", "libm.so.6"}}, "libGL.so.1"),
])
def test_m2_libstdcxx_and_system_libraries_of_the_target_are_compared(kit, tmp_path, values, message):
    ctx = context(kit, probe=PosteSimule(**values))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert message in ctx.out.getvalue() and not (tmp_path / "programmes").exists()


def test_m2_a_jetpack5_kit_is_refused_off_jetson_r35(tmp_path, monkeypatch):
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: {"major": 35, "revision": "4.1", "line": "R35"})
    repository = make_repository(tmp_path)
    kit = tmp_path / "kit-jp5"
    linux_kit.build_linux_kit(kit, repository, platform="linux-aarch64", gpu="jetpack5", home=str(tmp_path / "maison"))
    ctx = context(kit, probe=PosteSimule(l4t=None))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Jetson Linux R35" in ctx.out.getvalue()


def test_m2_ldd_runs_only_after_the_whole_kit_is_verified(kit, tmp_path):
    write(kit, "services/api/main.py", "altéré")
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "Kit non conforme" in ctx.out.getvalue() and ctx.probe.ldd_calls == []


# --- m3, m4 : environnement transmis, entrée de menu ---------------------------------------------------------------------

def test_m3_the_installation_environment_drops_inherited_python_and_uv_settings(monkeypatch):
    for key, value in (("PYTHONPATH", "/ailleurs"), ("PYTHONHOME", "/ailleurs"), ("UV_INDEX_URL", "https://exemple.invalid"),
                       ("UV_CACHE_DIR", "/ailleurs"), ("LD_LIBRARY_PATH", "/x:"), ("HOME", "/home/essai")):
        monkeypatch.setenv(key, value)
    environment = linux_install.child_environment()
    assert not {"PYTHONPATH", "PYTHONHOME", "UV_INDEX_URL", "UV_CACHE_DIR", "LD_LIBRARY_PATH"} & set(environment)
    assert environment["UV_NO_CONFIG"] == "1" and environment["HOME"] == "/home/essai" and environment["PYTHONUTF8"] == "1"


def test_m4_percent_is_doubled_and_control_characters_are_refused(kit, tmp_path):
    assert linux_install.desktop_quote("/a%b") == '"/a%%b"'
    ctx = context(kit)
    assert install(ctx, tmp_path / "pro\ngrammes", tmp_path / "donnees", "--no-start", "--menu", str(tmp_path / "menu")) == 1
    assert "caractère de contrôle" in ctx.out.getvalue() and not (tmp_path / "pro\ngrammes").exists()


# --- m6, m7, m8 : instance 4B, verrou, options -----------------------------------------------------------------------------

def test_m6_an_update_saves_from_the_running_4b_instance(kit, tmp_path, monkeypatch):
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert install(context(kit), destination, data_root, "--no-start") == 0
    current = pointer(destination)["current"]
    runner = ProgrammeSimule(last_started=current["program"])
    runner.running = {current["program"]: current["profiles"]["qwen3.5:4b"]}
    code, ctx = update(second_kit(tmp_path, monkeypatch), destination, runner, "--no-start")
    assert code == 0, ctx.out.getvalue()
    assert "qwen3.5:4b" in ctx.out.getvalue()


def test_m7_a_concurrent_installer_operation_is_refused(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    kit_b = second_kit(tmp_path, monkeypatch)
    with (destination / ".atelier-installateur.lock").open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, ctx = update(kit_b, destination, None, "--no-start")
    assert code == 1 and "Une autre opération d'installation est en cours" in ctx.out.getvalue()
    assert ctx.runner.calls == []


@pytest.mark.parametrize(("extra", "message"), [
    (["--model", "qwen3.5:9b"], "Modèle qwen3.5:9b absent de ce kit"),
    (["--ports", "8785,6333"], "--ports"),
    (["--ports", "80,6333,11434"], "--ports"),
], ids=["modele", "deux-ports", "port-privilegie"])
def test_m8_model_and_ports_are_checked_before_any_write(kit, tmp_path, extra, message):
    ctx = context(kit)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", *extra) == 1
    assert message in ctx.out.getvalue() and not (tmp_path / "programmes").exists() and ctx.runner.calls == []


def test_m8_a_busy_port_is_refused_before_any_write(kit, tmp_path):
    import socket

    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        free = free_ports(2)
        ctx = context(kit, probe=PosteSimule(real_ports=True))
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--ports", f"{port},{free[0]},{free[1]}") == 1
    assert f"port {port} occupé" in ctx.out.getvalue() and not (tmp_path / "programmes").exists()


# --- m9 : architecture, m10 : inventaire Windows -----------------------------------------------------------------------------

def test_m9_any_elf_of_another_architecture_refuses_the_kit(tmp_path, monkeypatch):
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: None)
    repository = make_repository(tmp_path)
    write(repository, ".runtime/cache/uv/archive-v0/ZzZ/roue/_x86.so", elf_header(62))
    with pytest.raises(linux_kit.KitError, match="autre architecture"):
        linux_kit.build_linux_kit(tmp_path / "kit", repository, platform="linux-aarch64", home=str(tmp_path / "maison"))


def test_m10_the_windows_inventory_is_unchanged(tmp_path, monkeypatch):
    from tools.dist import program_inventory

    write(tmp_path, "programme/a.py", "a")
    link(tmp_path, "programme/lien", "a.py")
    monkeypatch.setattr(program_inventory, "WINDOWS", True, raising=False)
    snapshot = program_inventory.snapshot(tmp_path / "programme")
    assert set(snapshot) == {"folder", "files"} and list(snapshot["files"]) == ["a.py"]
    report = program_inventory.compare(snapshot, snapshot)
    assert set(report) == {"files_before", "files_after", "added", "removed", "changed", "status"} and report["status"] == "unchanged"


# --- Remarques ---------------------------------------------------------------------------------------------------------

def test_a_forged_kit_id_or_python_path_is_refused(kit, tmp_path):
    manifest = json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))
    for field, value in (("kit_id", "../evasion"), ("python", {"key": "k", "executable": "../../bin/sh"})):
        forged = {**manifest, field: value}
        (kit / "kit-manifest.json").write_text(json.dumps(forged), encoding="utf-8")
        ctx = context(kit)
        assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
        assert "kit-manifest.json" in ctx.out.getvalue() and not (tmp_path / "evasion").exists()
    (kit / "kit-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize(("relative", "refused"), [
    (".runtime/models/e5-small-int8/.netrc", True), (".runtime/bin/qdrant-1.19.1/id_rsa", True),
    ("apps/web/out/notes.db", True), (".runtime/models/docling/journal.jsonl", True), (".runtime/bin/x/.bash_history", True),
    (".runtime/manifests/cle.pem", True), (".runtime/cache/uv/archive-v0/AbC/certifi/cacert.pem", False),
])
def test_more_secret_and_data_names_are_refused(tmp_path, monkeypatch, relative, refused):
    monkeypatch.setattr(linux_kit, "readelf_batches", fake_readelf)
    monkeypatch.setattr(linux_kit, "l4t_release", lambda path=None: None)
    repository = make_repository(tmp_path)
    write(repository, relative, "contenu")
    if refused:
        with pytest.raises(linux_kit.KitError, match="Entrée interdite"):
            linux_kit.plan_kit(repository, platform="linux-aarch64")
    else:
        assert relative in linux_kit.plan_kit(repository, platform="linux-aarch64").entries


def test_the_target_procedure_without_the_repository_checks_then_extracts_with_coreutils_and_tar(kit, tmp_path):
    (tmp_path / "transport").mkdir()
    linux_kit.archive_kit(kit, tmp_path / "transport/kit.tar")
    checked = subprocess.run(["sha256sum", "-c", "kit.tar.sha256"], cwd=tmp_path / "transport", capture_output=True, text=True, check=False)
    assert checked.returncode == 0 and "kit.tar: OK" in checked.stdout
    (tmp_path / "poste").mkdir()
    subprocess.run(["tar", "-xf", str(tmp_path / "transport/kit.tar"), "-C", str(tmp_path / "poste")], check=True)
    assert linux_kit.verify_kit(tmp_path / "poste" / kit_id(kit))["status"] == "verified"


def test_a_link_resolving_outside_after_copy_is_refused(kit, tmp_path, monkeypatch):
    # Seconde barrière : même si la normalisation lexicale laissait passer un lien, son chemin réel est contrôlé.
    sums = (kit / "SHA256SUMS").read_text(encoding="utf-8")
    (tmp_path / "ailleurs").mkdir()  # cible existante hors de la copie : seul le chemin réel la trahit
    links = (kit / "SYMLINKS").read_bytes() + b"services/evasion\t../../ailleurs\n"
    (kit / "SYMLINKS").write_bytes(links)
    digest = hashlib.sha256(links).hexdigest()
    (kit / "SHA256SUMS").write_text("".join((f"{digest}  SYMLINKS" if line.endswith("  SYMLINKS") else line) + "\n"
                                            for line in sums.splitlines()), encoding="utf-8")
    monkeypatch.setattr(linux_kit, "normalized_link", lambda relative, target: "services/evasion")
    with pytest.raises(linux_kit.KitError, match="hors de la copie"):
        linux_kit.install_copy(kit, tmp_path / "programme")
    assert not (tmp_path / "programme").exists()


def test_the_launcher_actions_need_no_lock_but_repair_does(kit, tmp_path):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    with (destination / ".atelier-installateur.lock").open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ctx = context(Path(pointer(destination)["current"]["program"]))
        assert linux_install.main(["run", "--destination", str(destination), "etat"], ctx) == 0
        busy = context(kit)
        assert linux_install.main(["repair", "--destination", str(destination)], busy) == 1


def test_probe_double_reports_ldd_by_binary_name():
    # Garde du double : un résultat ldd propre à un binaire n'atteint que lui.
    probe = PosteSimule(**{"ldd_cv2.abi3.so": Completed(1, "", "x")})
    assert probe.ldd(Path("/k/tesseract")).returncode == 0 and probe.ldd(Path("/k/cv2.abi3.so")).returncode == 1


# --- Contre-vérification : verrou du lanceur, instance d'un autre programme, libcrypt facultative -------------------------

def test_open_and_backup_from_the_launcher_are_refused_while_the_installer_lock_is_held(kit, tmp_path):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    program = Path(pointer(destination)["current"]["program"])
    with (destination / ".atelier-installateur.lock").open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for action in ("ouvrir", "sauvegarder"):
            ctx = context(program)
            assert linux_install.main(["run", "--destination", str(destination), action], ctx) == 1
            assert "Une opération d'installation est en cours" in ctx.out.getvalue() and ctx.runner.calls == []
        ctx = context(program)
        assert linux_install.main(["run", "--destination", str(destination), "etat"], ctx) == 0


def test_an_old_instance_restarted_during_the_update_stops_it_before_the_switch(kit, tmp_path, monkeypatch):
    destination = tmp_path / "programmes"
    assert install(context(kit), destination, tmp_path / "donnees", "--no-start") == 0
    old = pointer(destination)["current"]
    kit_b = second_kit(tmp_path, monkeypatch)
    runner = ProgrammeSimule(last_started=old["program"])

    def down_then_restarted_by_the_old_launcher(argv):
        # Arrêt confirmé, puis l'ancien lanceur relance aussitôt l'ancienne instance avec le même profil.
        runner.running = {old["program"]: old["profile"]}
        runner.last_started = old["program"]
        return {"status": "stopped"}

    runner.results[(Path(old["program"]).name, "down")] = down_then_restarted_by_the_old_launcher
    code, ctx = update(kit_b, destination, runner)
    assert code == 1, ctx.out.getvalue()
    assert pointer(destination)["current"]["kit_id"] == old["kit_id"]
    assert not (destination / kit_id(kit_b)).exists()
    assert "relancée pendant la mise à jour" in ctx.out.getvalue() and f"La version {old['kit_id']} reste la version courante" in ctx.out.getvalue()


def test_an_instance_of_another_program_returned_by_up_is_an_explicit_failure(kit, tmp_path):
    elsewhere = f"/ailleurs/programme/.runtime/python/{PYTHON_KEY}/bin/python3.12"
    runner = ProgrammeSimule(results={"up": {"status": "running", "instance_id": "x", "supervisor": {"executable": elsewhere}}})
    ctx = context(kit, runner=runner)
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees") == 1
    assert "n'appartient pas au programme" in ctx.out.getvalue() and "selftest" not in ctx.runner.commands()


class ToutSauf:
    def __init__(self, *absent):
        self.absent = set(absent)

    def __contains__(self, name):
        return name not in self.absent


def test_libcrypt_needed_only_by_the_crypt_module_is_optional_and_reported(kit, tmp_path):
    manifest = json.loads((kit / "kit-manifest.json").read_text(encoding="utf-8"))
    assert "libcrypt.so.1" not in manifest["target"]["system_libraries"]
    assert "libcrypt.so.1" in manifest["target"]["optional_system_libraries"]
    ctx = context(kit, probe=PosteSimule(libraries=ToutSauf("libcrypt.so.1")))
    assert install(ctx, tmp_path / "programmes", tmp_path / "donnees", "--no-start") == 0, ctx.out.getvalue()
    assert "libcrypt.so.1" in ctx.out.getvalue() and "facultative" in ctx.out.getvalue()
