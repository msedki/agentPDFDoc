"""Particularités de plateforme partagées par le runtime, l'API et les outils.

Deux plateformes natives sont prises en charge : Windows 11 x86-64 (W001) et Linux aarch64 ou x86-64 (W018).
Ce module ne dépend d'aucune bibliothèque propre à une plateforme et s'importe partout.

Commandes citées à l'utilisateur : celles du lanceur du dépôt (`./rag.sh`, `.\\rag.ps1`) dans un clone et sous Windows ;
dans une installation par le kit Linux (R26-KIT-04), celles du lanceur `atelier` de la destination, exécutables telles
quelles et hors ligne.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any

WINDOWS = os.name == "nt"
# Racine du programme qui exécute ce code : clone du dépôt, ou dossier d'une version installée par le kit Linux.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

_MACHINES = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}


def platform_id() -> str:
    """Identifiant employé par `config/artifacts.lock.json` : `windows-x86_64`, `linux-aarch64`…"""
    machine = platform.machine().lower()
    machine = _MACHINES.get(machine, machine)
    system = "windows" if WINDOWS else ("linux" if sys.platform.startswith("linux") else sys.platform)
    return f"{system}-{machine}"


def platform_label() -> str:
    """Libellé lisible pour les rapports et diagnostics."""
    return "Windows natif, sans WSL ni Docker" if WINDOWS else f"{platform.system()} {platform.machine()} natif, sans Docker"


def entries_for_platform(entries: list[dict[str, Any]], current: str | None = None) -> list[dict[str, Any]]:
    """Entrées d'un groupe du verrou valables ici.

    Une entrée sans champ `platform` vaut partout ; sinon le champ nomme une plateforme ou en liste plusieurs.
    """
    current = current or platform_id()

    def applies(entry: dict[str, Any]) -> bool:
        declared = entry.get("platform")
        if declared is None:
            return True
        return current in declared if isinstance(declared, list) else declared == current

    return [entry for entry in entries if applies(entry)]


def executable_name(name: str) -> str:
    """Nom de fichier d'un exécutable natif : `qdrant.exe` sous Windows, `qdrant` ailleurs."""
    return name + ".exe" if WINDOWS else name


def native_executable(configured: str | PurePath) -> str:
    """Chemin d'exécutable du profil adapté à la plateforme.

    Le profil livré nomme l'exécutable Windows (`.runtime/bin/tesseract-5.4.0/tesseract.exe`) ; hors Windows,
    le même emplacement sans suffixe `.exe` est utilisé. Une valeur sans suffixe est rendue telle quelle.
    """
    text = str(configured)
    if not WINDOWS and text.lower().endswith(".exe"):
        return text[:-4]
    return text


def venv_python(root: Path) -> Path:
    """Interpréteur de l'environnement isolé du projet."""
    return root / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


LAUNCHER = r".\rag.ps1" if WINDOWS else "./rag.sh"

# --- Installation par le kit Linux (tools/dist/linux_install.py) --------------------------------------------------------
# Noms écrits par l'installateur ; test_runtime_installation_texts.py vérifie l'accord avec tools/dist.
KIT_MANIFEST = "kit-manifest.json"
INSTALLATION_POINTER = "installation.json"
INSTALLATION_FORMAT = "atelier-installation-v1"
INSTALLED_LAUNCHER = "atelier"
MENU_NAME = "Atelier documentaire"
# Action du lanceur `atelier` pour chaque commande de rag.sh qui en a une.
INSTALLED_ACTIONS = {"open": "ouvrir", "up": "ouvrir", "down": "arreter", "doctor": "diagnostic", "status": "etat",
                     "backup": "sauvegarder", "logs": "journaux"}
# Actions qui choisissent le profil, donc le modèle : `--modele` nomme un modèle autre que celui du pointeur. Les autres
# portent sur la racine des données, commune aux profils d'une installation.
MODEL_ACTIONS = frozenset({"open", "up", "doctor"})
# Toute autre commande de rag.sh (selftest, verify, restore) : rag.sh du programme, avec le profil de l'utilisateur, car
# rag.sh refuse dans une installation le profil livré, rangé dans le programme.
# Phases réseau, refusées dans une installation : le programme se reprend depuis un kit.
NETWORK_ACTIONS = frozenset({"provision", "pull-model"})
_PROFILE_OPTION = re.compile(r"""--profile\s+(?:"([^"]*)"|(\S+))""")

_profile_in_use: Path | None = None


@dataclass(frozen=True)
class Installation:
    """Installation par le kit Linux qui contient ce programme, d'après le pointeur de sa destination."""

    destination: Path
    program: Path
    kit_id: str
    model: str | None
    profiles: dict[str, str] = field(default_factory=dict)
    menu: str | None = None

    @property
    def launcher(self) -> Path:
        return self.destination / INSTALLED_LAUNCHER

    @property
    def reinstall_command(self) -> str:
        """Mise à jour depuis un kit : seule voie de reprise des fichiers du programme, hors ligne. Une version installée
        n'est jamais remplacée sur place : le kit doit être d'une autre version."""
        return f"<dossier du kit>/installer.sh update --destination {shlex.quote(str(self.destination))}"

    def model_of(self, profile: Path | None) -> str | None:
        """Modèle d'un profil de l'installation ; None pour un profil qu'elle ne connaît pas."""
        if profile is None:
            return None
        real = os.path.realpath(profile)
        return next((model for model, path in self.profiles.items() if os.path.realpath(path) == real), None)

    def command(self, subcommand: str, profile: Path | None) -> str:
        action, _, options = subcommand.partition(" ")
        explicit = _PROFILE_OPTION.search(options)
        if explicit:
            profile = Path(explicit.group(1) or explicit.group(2))
            options = (options[:explicit.start()] + options[explicit.end():]).strip()
        if action in INSTALLED_ACTIONS:
            parts = [shlex.quote(str(self.launcher)), INSTALLED_ACTIONS[action]]
            model = self.model_of(profile) if action in MODEL_ACTIONS else None
            if model and model != self.model:
                parts += ["--modele", shlex.quote(model)]
            if "--no-browser" in options.split():
                parts.append("--no-browser")
            return " ".join(parts)
        if action in NETWORK_ACTIONS:
            return self.reinstall_command
        chosen = self.user_profile(profile)
        parts = [shlex.quote(str(self.program / "rag.sh")), action]
        if chosen is not None:
            parts += ["--profile", shlex.quote(str(chosen))]
        return " ".join([*parts, *([options] if options else [])])

    def user_profile(self, profile: Path | None) -> Path | None:
        """Profil à citer avec rag.sh : celui donné s'il est hors du programme, sinon le profil principal du pointeur."""
        if profile is not None and not Path(os.path.realpath(profile)).is_relative_to(os.path.realpath(self.program)):
            return profile
        path = self.profiles.get(self.model or "")
        return Path(path) if path else None


def installation(root: Path | None = None) -> Installation | None:
    """Installation par le kit Linux qui contient `root` (le programme de ce processus par défaut), ou None.

    Critères : `kit-manifest.json` à la racine du programme, et pointeur `installation.json` du dossier parent (la
    destination) au format de l'installateur, dont la version courante ou précédente désigne ce programme. Un clone, un
    kit extrait mais non installé, un pointeur illisible et Windows (W001, textes inchangés) ne sont pas une installation.
    """
    if WINDOWS:
        return None
    program = PROJECT_ROOT if root is None else root
    if not (program / KIT_MANIFEST).is_file():
        return None
    try:
        pointer = json.loads((program.parent / INSTALLATION_POINTER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(pointer, dict) or pointer.get("format") != INSTALLATION_FORMAT:
        return None
    real = os.path.realpath(program)
    entries = [pointer.get(key) for key in ("current", "previous")]
    entry = next((item for item in entries if isinstance(item, dict) and isinstance(item.get("program"), str)
                  and os.path.realpath(item["program"]) == real), None)
    if entry is None:
        return None
    # Commandes du lanceur : celui de la version courante, qui lit les profils du pointeur.
    current: dict[str, Any] = pointer["current"] if isinstance(pointer.get("current"), dict) else entry
    declared = current.get("profiles")
    profiles: dict[Any, Any] = declared if isinstance(declared, dict) else {}
    destination = Path(str(pointer.get("destination") or program.parent))
    if os.path.realpath(destination) != os.path.realpath(program.parent):
        destination = program.parent
    menu_entry = pointer.get("menu_entry")
    menu = (MENU_NAME if pointer.get("menu", True) is not False and isinstance(menu_entry, str) and Path(menu_entry).is_file()
            else None)
    return Installation(destination=destination, program=Path(entry["program"]), kit_id=str(entry.get("kit_id", "")),
                        model=current.get("model"), profiles={str(key): str(value) for key, value in profiles.items()},
                        menu=menu)


def use_profile(path: str | PurePath | None) -> None:
    """Profil de ce processus (option --profile du CLI), cité par les commandes d'une installation."""
    global _profile_in_use
    _profile_in_use = Path(path) if path else None


def profile_in_use() -> Path | None:
    """Profil de ce processus : celui du CLI, sinon RAG_PROFILE, posé par le superviseur pour l'API."""
    if _profile_in_use is not None:
        return _profile_in_use
    declared = os.environ.get("RAG_PROFILE")
    return Path(declared) if declared else None


def launcher_command(subcommand: str, profile: str | PurePath | None = None) -> str:
    """Commande du lanceur à afficher à l'utilisateur : `.\\rag.ps1 open` sous Windows, `./rag.sh open` dans un clone Linux,
    `<destination>/atelier ouvrir` dans une installation par le kit Linux (profil explicite, sinon celui du processus)."""
    installed = installation()
    if installed is None:
        return f"{LAUNCHER} {subcommand}"
    return installed.command(subcommand, Path(profile) if profile else profile_in_use())


def launcher_instruction(subcommand: str) -> str:
    """Commande citée avec l'endroit où la taper : « ./rag.sh logs » depuis le dossier du projet, ou « …/atelier journaux »
    dans un terminal pour une installation, dont le lanceur porte un chemin absolu."""
    where = "dans un terminal" if installation() else "depuis le dossier du projet"
    return f"« {launcher_command(subcommand)} » {where}"


def launcher_kind() -> dict[str, str | None]:
    """Champ `launcher` de GET /health : `installation` (lanceur atelier, entrée de menu si elle existe) ou `projet`."""
    installed = installation()
    return {"kind": "installation", "menu": installed.menu} if installed else {"kind": "projet", "menu": None}
