"""Textes d'une installation par le kit Linux (R26-KIT-04, KIT4-13) : détection de l'installation par le runtime,
commandes citées par le runtime et le superviseur, traduites vers le lanceur `atelier` de la destination.

Doubles nommés :
- `installation_tree` écrit une arborescence d'installation factice, au format du pointeur de
  `tools/dist/linux_install.py` (programme `<destination>/<kit_id>` muni de `kit-manifest.json`, pointeur
  `<destination>/installation.json`, profils dans la racine des données) ; aucun programme n'y est copié ni lancé ;
- `run_as` désigne le programme qui exécute le runtime (`platforms.PROJECT_ROOT`, `WINDOWS`, `LAUNCHER`) ;
- section « Doubles du CLI et du superviseur » : `profil_vide` et `profil_des_donnees` (cli.load_profile),
  `etat_arrete`, `etat_en_marche` et `etat_en_marche_sur_gpu` (cli.status), `sans_jeton` (cli.control_headers),
  `rapport_ouverture` (cli.status_report), `survivants_ollama` (supervisor.orphan_processes) ;
- le test d'accord du pointeur réellement écrit emploie ceux de test_dist_linux_install : kit fabriqué par `make_kit`
  depuis un dépôt factice, `context` avec `PosteSimule` (lectures du poste) et `ProgrammeSimule` (commandes lancées) ;
  copie, pointeur, lanceur et entrée de menu y sont réels, sous TMPDIR, avec HOME propre au test.

Le fixture `installed` vaut pour un programme désigné comme version courante, puis comme version précédente : le
runtime d'une version précédente encore présente cite aussi le lanceur `atelier`. Un clone (dépôt sans
`kit-manifest.json`) et Windows gardent leurs textes : chaque test d'installation a son pendant pour le clone.
"""

import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

import psutil
import pytest
import yaml

from services.runtime import cli, platforms, supervisor
from services.runtime.artifacts import ROOT, write_json_atomic

KIT_ID = "0.1.0+0123456789ab-linux-aarch64-none-2b4b"
PRINCIPAL, OTHER = "qwen3.5:4b", "qwen3.5:2b"


@dataclass(frozen=True)
class InstallationTree:
    destination: Path
    program: Path
    data: Path
    profiles: dict[str, str]
    menu_entry: Path | None


def installation_tree(base: Path, *, designated: str = "current", menu: bool = False,
                      destination_name: str = "programme") -> InstallationTree:
    """Arborescence factice d'une installation : le pointeur désigne le programme comme version courante
    (`designated="current"`), précédente (`"previous"`) ou ne le désigne pas (`"none"`)."""
    destination = base / destination_name
    program = destination / KIT_ID
    data = base / "donnees"
    program.mkdir(parents=True)
    data.mkdir(parents=True)
    (program / "kit-manifest.json").write_text(json.dumps({"kit_id": KIT_ID}), encoding="utf-8")
    profiles = {PRINCIPAL: str(data / "profile.yaml"), OTHER: str(data / "profile-qwen3.5-2b.yaml")}
    for path in profiles.values():
        Path(path).write_text("schema_version: 2\n", encoding="utf-8")
    entry = {"kit_id": KIT_ID, "program": str(program), "python": ".runtime/python/cpython-3.12/bin/python3.12",
             "data_root": str(data), "profile": profiles[PRINCIPAL], "profiles": profiles, "model": PRINCIPAL,
             "started_on_data": False}
    other = {**entry, "kit_id": "0.0.9+fedcba987654-linux-aarch64-none-2b4b",
             "program": str(destination / "0.0.9+fedcba987654-linux-aarch64-none-2b4b")}
    pointer = {"format": "atelier-installation-v1", "destination": str(destination), "history": [],
               "current": entry if designated == "current" else other,
               "previous": entry if designated == "previous" else None}
    menu_entry = None
    if menu:
        menu_entry = base / "applications/atelier-documentaire.desktop"
        menu_entry.parent.mkdir(parents=True)
        menu_entry.write_text("[Desktop Entry]\nName=Atelier documentaire\n", encoding="utf-8")
        pointer["menu_entry"] = str(menu_entry)
    (destination / "installation.json").write_text(json.dumps(pointer, ensure_ascii=False), encoding="utf-8")
    return InstallationTree(destination, program, data, profiles, menu_entry)


def run_as(monkeypatch, root: Path, *, windows: bool = False) -> None:
    """Runtime lancé depuis `root` (programme installé ou clone), profil en usage inconnu."""
    monkeypatch.setattr(platforms, "WINDOWS", windows)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1" if windows else "./rag.sh")
    monkeypatch.setattr(platforms, "PROJECT_ROOT", root)
    monkeypatch.setattr(platforms, "_profile_in_use", None)
    monkeypatch.delenv("RAG_PROFILE", raising=False)


@pytest.fixture(params=["current", "previous"], ids=["version_courante", "version_precedente"])
def installed(request, tmp_path, monkeypatch) -> InstallationTree:
    """Runtime lancé depuis un programme que le pointeur désigne comme version courante, puis comme version précédente."""
    tree = installation_tree(tmp_path, designated=request.param)
    run_as(monkeypatch, tree.program)
    return tree


@pytest.fixture
def clone(monkeypatch) -> Path:
    """Dépôt de développement réel : aucun kit-manifest.json à sa racine."""
    assert not (ROOT / "kit-manifest.json").exists()
    run_as(monkeypatch, ROOT)
    return ROOT


def atelier(tree: InstallationTree, action: str) -> str:
    return f"{tree.destination / 'atelier'} {action}"


# --- Détection ------------------------------------------------------------------------------------------------------

def test_a_kit_program_designated_by_the_pointer_is_an_installation(installed):
    found = platforms.installation()
    assert found is not None
    assert (found.destination, found.program, found.kit_id, found.model) == (installed.destination, installed.program,
                                                                             KIT_ID, PRINCIPAL)
    assert found.profiles == installed.profiles and found.menu is None


def test_the_previous_version_of_an_installation_is_recognised(tmp_path, monkeypatch):
    tree = installation_tree(tmp_path, designated="previous")
    run_as(monkeypatch, tree.program)
    found = platforms.installation()
    assert found is not None and found.destination == tree.destination and found.program == tree.program


@pytest.mark.parametrize("case", ["sans_manifeste", "sans_pointeur", "autre_format", "json_illisible",
                                  "autre_programme", "windows"])
def test_a_clone_an_undesignated_program_or_windows_is_not_an_installation(tmp_path, monkeypatch, case):
    tree = installation_tree(tmp_path, designated="none" if case == "autre_programme" else "current")
    pointer = tree.destination / "installation.json"
    if case == "sans_manifeste":
        (tree.program / "kit-manifest.json").unlink()
    elif case == "sans_pointeur":
        pointer.unlink()
    elif case == "autre_format":
        pointer.write_text(json.dumps({**json.loads(pointer.read_text(encoding="utf-8")), "format": "autre"}),
                           encoding="utf-8")
    elif case == "json_illisible":
        pointer.write_text("{ tronqué", encoding="utf-8")
    run_as(monkeypatch, tree.program, windows=case == "windows")
    assert platforms.installation() is None
    assert platforms.launcher_command("open") == (r".\rag.ps1 open" if case == "windows" else "./rag.sh open")


def test_the_development_clone_is_not_an_installation(clone):
    assert platforms.installation() is None
    assert platforms.launcher_kind() == {"kind": "projet", "menu": None}


# --- Commandes traduites --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("command", "action"), [
    ("open", "ouvrir"), ("up", "ouvrir"), ("down", "arreter"), ("doctor", "diagnostic"), ("status", "etat"),
    ("backup", "sauvegarder"), ("logs", "journaux"), ("open --no-browser", "ouvrir --no-browser")])
def test_launcher_actions_become_commands_of_the_atelier_launcher(installed, command, action):
    assert platforms.launcher_command(command) == atelier(installed, action)


@pytest.mark.parametrize(("command", "expected"), [
    ("selftest", "selftest --profile {profile}"),
    ("verify --path <sauvegarde>", "verify --profile {profile} --path <sauvegarde>"),
    ("restore --path <sauvegarde> --target <racine neuve>",
     "restore --profile {profile} --path <sauvegarde> --target <racine neuve>")])
def test_commands_without_launcher_action_name_the_program_and_the_profile(installed, command, expected):
    profile = installed.profiles[PRINCIPAL]
    assert platforms.launcher_command(command) == f"{installed.program / 'rag.sh'} " + expected.format(profile=profile)


def test_a_non_principal_profile_in_use_is_named_by_its_model(installed, monkeypatch):
    platforms.use_profile(installed.profiles[OTHER])
    assert platforms.profile_in_use() == Path(installed.profiles[OTHER])
    assert platforms.launcher_command("open") == atelier(installed, f"ouvrir --modele {OTHER}")
    assert platforms.launcher_command("up") == atelier(installed, f"ouvrir --modele {OTHER}")
    assert platforms.launcher_command("doctor") == atelier(installed, f"diagnostic --modele {OTHER}")
    # Arrêt, état, journaux et sauvegarde portent sur la racine des données, commune aux profils de l'installation.
    assert platforms.launcher_command("down") == atelier(installed, "arreter")
    assert platforms.launcher_command("logs") == atelier(installed, "journaux")
    assert platforms.launcher_command("selftest") == (f"{installed.program / 'rag.sh'} selftest --profile "
                                                      f"{installed.profiles[OTHER]}")
    # Profil explicite d'un appel : il prime sur le profil en usage.
    assert platforms.launcher_command("up", installed.profiles[PRINCIPAL]) == atelier(installed, "ouvrir")


def test_the_api_process_reads_its_profile_from_the_supervisor_environment(installed, monkeypatch):
    monkeypatch.setenv("RAG_PROFILE", installed.profiles[OTHER])
    assert platforms.launcher_command("open") == atelier(installed, f"ouvrir --modele {OTHER}")


@pytest.mark.parametrize("command", ["provision", "provision --only ollama-gpu", "pull-model", "pull-model --offline"])
def test_network_phases_are_replaced_by_a_reinstall_from_a_kit(installed, command):
    text = platforms.launcher_command(command)
    assert text == f"<dossier du kit>/installer.sh update --destination {installed.destination}"
    assert "provision" not in text and "pull-model" not in text


def test_paths_with_spaces_are_quoted_for_the_shell(tmp_path, monkeypatch):
    tree = installation_tree(tmp_path / "Mes documents", destination_name="Atelier documentaire")
    run_as(monkeypatch, tree.program)
    assert shlex.split(platforms.launcher_command("open --no-browser")) == [str(tree.destination / "atelier"), "ouvrir",
                                                                            "--no-browser"]
    assert shlex.split(platforms.launcher_command("selftest")) == [str(tree.program / "rag.sh"), "selftest", "--profile",
                                                                   tree.profiles[PRINCIPAL]]


def test_clone_and_windows_commands_are_unchanged(clone, monkeypatch):
    assert [platforms.launcher_command(command) for command in ("open", "provision --only ollama-gpu")] == [
        "./rag.sh open", "./rag.sh provision --only ollama-gpu"]
    assert platforms.launcher_instruction("logs") == "« ./rag.sh logs » depuis le dossier du projet"
    monkeypatch.setattr(platforms, "WINDOWS", True)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1")
    assert platforms.launcher_command("open") == r".\rag.ps1 open"
    assert platforms.launcher_instruction("logs") == r"« .\rag.ps1 logs » depuis le dossier du projet"


def test_instructions_of_an_installation_say_where_to_type_the_command(installed):
    assert platforms.launcher_instruction("logs") == f"« {atelier(installed, 'journaux')} » dans un terminal"
    assert platforms.launcher_kind() == {"kind": "installation", "menu": None}


def test_the_menu_is_announced_only_while_its_entry_exists(tmp_path, monkeypatch):
    tree = installation_tree(tmp_path, menu=True)
    run_as(monkeypatch, tree.program)
    assert platforms.launcher_kind() == {"kind": "installation", "menu": "Atelier documentaire"}
    assert tree.menu_entry is not None
    tree.menu_entry.unlink()
    assert platforms.launcher_kind() == {"kind": "installation", "menu": None}


# --- Accord avec l'installateur ------------------------------------------------------------------------------------

# --- Doubles du CLI et du superviseur ------------------------------------------------------------------------------
# Lectures du runtime remplacées : aucune instance, aucun profil complet ni processus réel n'est nécessaire.

def profil_vide(path):
    """Double de cli.load_profile : profil sans section, que les textes testés ne lisent pas."""
    return {}


def profil_des_donnees(data_dir: Path):
    """Double de cli.load_profile : profil réduit à la racine des données `data_dir`."""
    def profil(path):
        return {"app": {"data_dir": str(data_dir)}}
    return profil


def etat_arrete(path):
    """Double de cli.status : aucune instance en marche."""
    return {"status": "stopped"}


def etat_en_marche(path):
    """Double de cli.status : instance en marche, sans autre détail."""
    return {"status": "running"}


def etat_en_marche_sur_gpu(path):
    """Double de cli.status : instance en marche, génération sur le GPU intégré du Jetson (variante cuda_jetpack5)."""
    return {"status": "running", "accelerator": {
        "mode": "gpu", "reason": "gpu_discovered", "device": {"library": "CUDA", "name": "CUDA0", "description": "Orin",
                                                              "type": "iGPU"}, "variant": "cuda_jetpack5"}}


def sans_jeton(directory):
    """Double de cli.control_headers : jeton de contrôle de l'instance absent."""
    return None


def rapport_ouverture(path):
    """Double de cli.status_report : la seule commande d'ouverture, citée avec le profil que le CLI a enregistré."""
    return {"open": platforms.launcher_command("open")}


def survivants_ollama(state):
    """Double de supervisor.orphan_processes : un survivant Ollama déclaré, sans processus réel (le relevé lui-même est
    couvert par test_runtime_supervisor)."""
    return {"ollama": [4242]}


# --- Runtime : CLI et superviseur ----------------------------------------------------------------------------------

def test_open_without_a_running_instance_names_the_atelier_launcher(installed, monkeypatch):
    monkeypatch.setattr(cli, "load_profile", profil_vide)
    monkeypatch.setattr(cli, "status", etat_arrete)
    with pytest.raises(RuntimeError) as refused:
        cli.open_workspace(Path(installed.profiles[PRINCIPAL]))
    assert str(refused.value) == f"Instance non démarrée : lancer d'abord {atelier(installed, 'ouvrir')}"


@pytest.mark.parametrize("where", ["installation", "clone"])
def test_a_missing_control_token_names_the_two_commands_to_restart(tmp_path, monkeypatch, where):
    tree = installation_tree(tmp_path)
    run_as(monkeypatch, tree.program if where == "installation" else ROOT)
    monkeypatch.setattr(cli, "load_profile", profil_des_donnees(tmp_path / "donnees"))
    monkeypatch.setattr(cli, "status", etat_en_marche)
    monkeypatch.setattr(cli, "control_headers", sans_jeton)
    with pytest.raises(RuntimeError) as refused:
        cli.open_workspace(Path(tree.profiles[PRINCIPAL]))
    assert str(refused.value) == {
        "installation": (f"Jeton de contrôle de l'instance absent : redémarrer avec {atelier(tree, 'arreter')} puis "
                         f"{atelier(tree, 'ouvrir')}"),
        "clone": "Jeton de contrôle de l'instance absent : redémarrer avec ./rag.sh down puis up"}[where]


def test_the_generation_line_of_status_names_the_atelier_diagnostic(installed, monkeypatch):
    monkeypatch.setattr(cli, "status", etat_en_marche_sur_gpu)
    line = cli.status_report(Path(installed.profiles[PRINCIPAL]))["generation"]
    assert line.endswith(f"Un repli sur CPU après un échec du GPU est signalé par {atelier(installed, 'diagnostic')}.")


def test_the_cli_records_its_profile_for_the_commands_it_cites(installed, monkeypatch, capsys):
    monkeypatch.setattr(cli, "status_report", rapport_ouverture)
    monkeypatch.setattr(sys, "argv", ["cli", "status", "--profile", installed.profiles[OTHER]])
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == {"open": atelier(installed, f"ouvrir --modele {OTHER}")}


def _runtime_profile(tree: InstallationTree, model: str) -> Path:
    """Profil exécutable par le superviseur, écrit à l'emplacement du profil `model` de l'installation factice."""
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["app"]["data_dir"] = str(tree.data / "runtime")
    path = Path(tree.profiles[model])
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return path


@pytest.mark.parametrize("where", ["installation", "clone"])
def test_up_refused_by_another_running_profile_names_the_commands_that_apply_it(tmp_path, monkeypatch, where):
    tree = installation_tree(tmp_path)
    run_as(monkeypatch, tree.program if where == "installation" else ROOT)
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    profile = _runtime_profile(tree, OTHER)
    me = psutil.Process()
    # Instance en marche sur ces données avec un autre profil : identité réelle de ce processus, aucun service lancé.
    write_json_atomic(tree.data / "runtime/control/runtime.json", {
        "status": "running", "instance_id": "en-marche", "profile_sha256": "0" * 64, "data_dir": str(tree.data / "runtime"),
        "supervisor": {"pid": me.pid, "created_at": me.create_time(), "executable": me.exe()}, "services": {}})
    with pytest.raises(RuntimeError) as refused:
        supervisor.start(profile)
    assert str(refused.value) == {
        "installation": (f"Instance existante avec profil différent : {atelier(tree, 'arreter')} puis "
                         f"{atelier(tree, f'ouvrir --modele {OTHER}')} pour appliquer la configuration"),
        "clone": "Instance existante avec profil différent : down puis up pour appliquer la configuration"}[where]


@pytest.mark.parametrize("where", ["installation", "clone"])
def test_survivors_of_a_previous_instance_name_the_command_to_start_again(tmp_path, monkeypatch, where):
    tree = installation_tree(tmp_path)
    run_as(monkeypatch, tree.program if where == "installation" else ROOT)
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    profile = _runtime_profile(tree, PRINCIPAL)
    monkeypatch.setattr(supervisor, "orphan_processes", survivants_ollama)
    with pytest.raises(RuntimeError) as refused:
        supervisor.start(profile)
    assert str(refused.value).endswith({"installation": f"les arrêter, puis relancer {atelier(tree, 'ouvrir')}",
                                        "clone": "les arrêter, puis relancer up"}[where])


@pytest.mark.parametrize("where", ["installation", "clone"])
def test_absent_program_artifacts_point_to_a_reinstall_in_an_installation(tmp_path, monkeypatch, where):
    tree = installation_tree(tmp_path)
    run_as(monkeypatch, tree.program if where == "installation" else ROOT)
    (tmp_path / "copie/config").mkdir(parents=True)
    (tmp_path / "copie/config/artifacts.lock.json").write_text(json.dumps({"groups": {}}), encoding="utf-8")
    monkeypatch.setattr(supervisor, "ROOT", tmp_path / "copie")
    with pytest.raises(FileNotFoundError) as refused:
        supervisor.native_paths()
    assert str(refused.value) == {
        "installation": ("Artefacts du programme absents ; réinstaller le programme depuis le kit d'une autre version : "
                         f"<dossier du kit>/installer.sh update --destination {tree.destination}"),
        "clone": "Artefacts non provisionnés ; exécuter ./rag.sh provision"}[where]


def test_no_launcher_text_of_the_runtime_leaves_the_repository_clone_unchanged(clone):
    """Non-régression du clone : la racine réelle du dépôt n'est pas une installation, rien n'est relu ailleurs."""
    assert os.path.realpath(platforms.PROJECT_ROOT) == os.path.realpath(ROOT)
    assert platforms.launcher_command("doctor") == "./rag.sh doctor"
