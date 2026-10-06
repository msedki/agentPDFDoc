"""Fichiers du programme lus par la sauvegarde : tous livrés par les kits (défaut C3 du lot R26-KIT-01).

`create_backup` copie dans chaque sauvegarde des fichiers du dossier programme (verrous, contrat d'API, manifestes).
Dans une installation, ce dossier est un kit : un fichier lu par la sauvegarde mais absent de la liste blanche fait
échouer la sauvegarde (FileNotFoundError), donc aussi la mise à jour, qui commence par une sauvegarde vérifiée.
"""

import ast
import json
from pathlib import Path

import pytest

from tools.dist.build_kit import INCLUDED, ROOT, build_kit, selected_files


def program_files_read_by_backup() -> list[str]:
    """Chemins relatifs à ROOT que services/runtime/backup.py lit : `ROOT / "x"` et la table (source, nom sauvé)."""
    tree = ast.parse((ROOT / "services/runtime/backup.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.left, ast.Name)
                and node.left.id == "ROOT" and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)):
            found.add(node.right.value)
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple) and isinstance(node.iter, ast.Tuple):
            names = [element.id for element in node.target.elts if isinstance(element, ast.Name)]
            if names[:1] == ["source_name"]:
                for item in node.iter.elts:
                    if isinstance(item, ast.Tuple) and isinstance(item.elts[0], ast.Constant):
                        found.add(str(item.elts[0].value))
    return sorted(found)


def covered(relative: str, whitelist: tuple[str, ...] | list[str]) -> bool:
    return any(relative == entry or relative.startswith(entry.rstrip("/") + "/") for entry in whitelist)


def test_the_backup_reads_the_api_contract_and_the_locks_of_the_program():
    # Garde du test lui-même : la lecture du module trouve bien les fichiers attendus.
    read = program_files_read_by_backup()
    assert {"packages/contracts/contracts.json", "uv.lock", "pyproject.toml", "config/artifacts.lock.json",
            "apps/web/pnpm-lock.yaml"} <= set(read)


@pytest.mark.parametrize("relative", program_files_read_by_backup())
def test_every_program_file_read_by_the_backup_is_in_the_windows_kit_whitelist(relative):
    # Version config/local16.yaml lue par la restauration et .runtime/manifests : couverts par la liste blanche.
    assert covered(relative, INCLUDED), f"{relative} lu par la sauvegarde mais absent du kit Windows"


def test_a_windows_kit_built_from_a_repository_carries_the_api_contract(tmp_path):
    root = tmp_path / "depot"
    for relative in ("services/runtime/backup.py", "packages/contracts/contracts.json", "uv.lock", "pyproject.toml",
                     "apps/web/pnpm-lock.yaml", "config/local16.yaml", ".runtime/manifests/artifacts.json"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    (root / "config/artifacts.lock.json").write_text(json.dumps({"groups": {}}), encoding="utf-8")
    assert "packages/contracts/contracts.json" in selected_files(root)
    build_kit(tmp_path / "kit", root=root, version="0.1.0")
    assert (tmp_path / "kit/packages/contracts/contracts.json").is_file()


def test_the_contract_file_exists_in_the_repository():
    assert Path(ROOT / "packages/contracts/contracts.json").is_file()
