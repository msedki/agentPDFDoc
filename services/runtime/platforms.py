"""Particularités de plateforme partagées par le runtime, l'API et les outils.

Deux plateformes natives sont prises en charge : Windows 11 x86-64 (W001) et Linux aarch64 ou x86-64 (W018).
Ce module ne dépend d'aucune bibliothèque propre à une plateforme et s'importe partout.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path, PurePath
from typing import Any

WINDOWS = os.name == "nt"

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


def launcher_command(subcommand: str) -> str:
    """Commande du lanceur à afficher à l'utilisateur, par exemple `.\\rag.ps1 open` ou `./rag.sh open`."""
    return f"{LAUNCHER} {subcommand}"
