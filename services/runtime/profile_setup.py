"""Profil d'une installation par utilisateur : données, stockage Qdrant court et écritures d'exécution hors du programme (DIST-02).

Le profil généré part du profil de référence du dépôt ; seuls les chemins, les ports et la section `runtime` changent.
Rien n'est écrasé : la racine choisie ne doit contenir aucun profil.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from . import platforms
from .artifacts import ROOT
from .supervisor import port_probe

# Borne de W004 : le binaire Qdrant Windows verrouillé exige « <stockage>\\storage » de 57 caractères au plus.
QDRANT_STORAGE_MAX = 57


def qdrant_path_bounded() -> bool:
    """Vrai sous Windows seulement : la borne W004 tient au binaire Qdrant Windows, pas au binaire Linux."""
    return os.name == "nt"


def port_free(port: int) -> bool:
    """Port loopback libre pour le service qui le prendra, selon la règle de check_ports (port_probe)."""
    with port_probe() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def user_profile(base: dict[str, Any], data_root: Path, *, qdrant_storage: Path | None = None, ports: dict[str, int] | None = None,
                 program_root: Path | None = None, storage_max: int = QDRANT_STORAGE_MAX) -> dict[str, Any]:
    """Profil par utilisateur tiré de `base` ; lève ValueError avec la correction attendue si une contrainte n'est pas tenue."""
    data_root = data_root.resolve()
    if not data_root.is_absolute() or data_root.is_relative_to((program_root or ROOT).resolve()):
        raise ValueError("La racine des données doit être un chemin absolu hors du dossier du programme")
    storage = (qdrant_storage or data_root / "q").resolve()
    if qdrant_path_bounded() and len(str(storage / "storage")) > storage_max:
        raise ValueError(f"Stockage Qdrant trop long ({len(str(storage / 'storage'))} caractères pour {storage_max}) : choisir un dossier court avec --qdrant-storage")
    chosen = {"app": base["app"]["port"], "qdrant": int(base["qdrant"]["url"].rsplit(":", 1)[1].rstrip("/")),
              "ollama": int(base["llm"]["base_url"].rsplit(":", 1)[1].rstrip("/")), **(ports or {})}
    if len(set(chosen.values())) != 3:
        raise ValueError("Les ports de l'API, de Qdrant et d'Ollama doivent être distincts")
    busy = [f"{name} {port}" for name, port in chosen.items() if not port_free(port)]
    if busy:
        raise ValueError("Port déjà occupé sur ce poste : " + ", ".join(busy) + " ; en choisir un autre avec --ports")
    profile = {key: (dict(value) if isinstance(value, dict) else value) for key, value in base.items()}
    profile["app"] = {**base["app"], "data_dir": str(data_root / "data"), "port": chosen["app"]}
    profile["qdrant"] = {**base["qdrant"], "url": f"http://127.0.0.1:{chosen['qdrant']}", "storage_dir": str(storage)}
    profile["llm"] = {**base["llm"], "base_url": f"http://127.0.0.1:{chosen['ollama']}"}
    # Les stockages de restauration (« <dossier>\<id8>\storage », W004) sont placés à côté du stockage court, pas sous la racine.
    profile["runtime"] = {"host_lock_path": str(data_root / "control" / "host-heavy.lock"), "backups_dir": str(data_root / "backups"),
                          "restore_storage_dir": str(restore_dir(storage)), "huggingface_cache_dir": str(data_root / "cache" / "huggingface")}
    return profile


def restore_dir(storage: Path) -> Path:
    return storage.with_name(storage.name + "r")


def restore_store_length(directory: Path) -> int:
    """Longueur du chemin qu'une restauration crée sous `directory` : identifiant de huit caractères puis `storage`."""
    return len(str(directory / ("0" * 8) / "storage"))


def write_user_profile(base_path: Path, data_root: Path, *, qdrant_storage: Path | None = None, ports: dict[str, int] | None = None,
                       program_root: Path | None = None, storage_max: int = QDRANT_STORAGE_MAX) -> dict[str, Any]:
    target = data_root.resolve() / "profile.yaml"
    if target.exists():
        raise ValueError(f"Profil déjà présent, jamais remplacé : {target}")
    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    profile = user_profile(base, data_root, qdrant_storage=qdrant_storage, ports=ports, program_root=program_root, storage_max=storage_max)
    restores = Path(profile["runtime"]["restore_storage_dir"])
    if qdrant_path_bounded() and restore_store_length(restores) > storage_max:
        # Refus dès la création : sinon une restauration ultérieure échouerait sur la même borne du binaire Qdrant.
        example = Path(os.environ.get("USERPROFILE") or Path.home()) / "apdfq"
        raise ValueError(f"Stockages de restauration trop longs ({restore_store_length(restores)} caractères pour {storage_max}) sous {restores} : "
                         f"choisir un stockage Qdrant plus court avec --qdrant-storage, par exemple {example}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        launcher = "rag.ps1" if platforms.WINDOWS else "rag.sh"
        stream.write("# Profil généré par " + launcher + " init-profile depuis " + base_path.name + " ; données et écritures d'exécution hors du programme.\n")
        yaml.safe_dump(profile, stream, allow_unicode=True, sort_keys=False)
    return {"status": "created", "profile": str(target), "data_dir": profile["app"]["data_dir"], "qdrant_storage": profile["qdrant"]["storage_dir"],
            "ports": {"app": profile["app"]["port"], "qdrant": profile["qdrant"]["url"], "ollama": profile["llm"]["base_url"]}, "runtime": profile["runtime"],
            "next": f".\\rag.ps1 up -Profile \"{target}\"" if platforms.WINDOWS else platforms.launcher_command(f"up --profile \"{target}\"")}
