"""Sorties de preuve exclusives et empreintes ; aucun jeu gelé ni preuve existante n'est réécrit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals" / "qualification-v2.1"
# Preuves locales hors Git, acceptées en plus des dossiers versionnés de chaque outil. `.runtime` peut être un lien vers
# un autre volume (W018) : checked_output compare des chemins résolus.
LOCAL_QA = ROOT / ".runtime" / "qa"
# Jeux sources, gel et manifeste : jamais une sortie d'outil, quel que soit le dossier.
PROTECTED_NAMES = frozenset({"final.json", "final.freeze.json", "questions.json", "development.json", "manifest.json"})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_output(path: Path, allowed: list[Path], *, sources: tuple[Path, ...] = (), must_exist: bool = False) -> Path:
    """Valide une cible dans un dossier autorisé ; refuse noms protégés, entrées et fichier existant."""
    output = Path(path).resolve()
    if any(char in output.name for char in ":~"):
        raise ValueError(f"Nom de sortie refusé (flux NTFS ou nom court 8.3) : {output.name}")
    # Win32 retire points et espaces finaux : « final.json. » créerait « final.json ».
    if output.name.rstrip(" .").lower() in PROTECTED_NAMES:
        raise ValueError(f"Nom réservé à un jeu, un gel ou un manifeste protégé : {output.name}")
    roots = [Path(root).resolve() for root in allowed]
    if not any(output.is_relative_to(root) and output != root for root in roots):
        raise ValueError("Sortie hors des dossiers autorisés : " + ", ".join(str(root) for root in roots))
    if output in {Path(source).resolve() for source in sources}:
        raise ValueError("La sortie ne peut pas remplacer une entrée")
    if must_exist and not output.is_file():
        raise ValueError("Reprise impossible : journal absent")
    if not must_exist and output.exists():
        raise ValueError("Preuve existante : choisir un nouveau fichier ; aucun écrasement")
    return output


def write_json_exclusive(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def append_jsonl(path: Path, record: dict, *, create: bool = False) -> None:
    """Ajoute une ligne complète puis la force sur disque ; la création reste exclusive."""
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if create else "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"Journal illisible ligne {number} ; aucune réparation automatique") from error
    return records
