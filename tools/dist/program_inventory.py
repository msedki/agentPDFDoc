"""Inventaire SHA-256 du dossier programme installé, pour prouver qu'aucune écriture d'exécution ne le modifie (DIST-02).

`snapshot` écrit l'inventaire (chemin relatif, taille, empreinte) ; `compare` liste les fichiers ajoutés, retirés ou modifiés
entre deux inventaires. Lecture par blocs : les modèles dépassent la mémoire disponible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


WINDOWS = os.name == "nt"


def walk(folder: Path):
    """Fichiers et liens symboliques, sans traverser aucun lien (un lien vers un dossier reste une entrée)."""
    pending = [folder]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    pending.append(Path(entry.path))
                else:
                    yield Path(entry.path), entry.is_symlink()


def snapshot(folder: Path) -> dict[str, Any]:
    """Inventaire du dossier programme. Sous Windows, comportement d'origine inchangé : fichiers seulement. Ailleurs, les
    liens symboliques (cible exacte) s'y ajoutent : un lien ajouté, retiré ou redirigé est une écriture dans le programme."""
    folder = folder.resolve()
    files: dict[str, Any] = {}
    if WINDOWS:
        files = {item.relative_to(folder).as_posix(): {"bytes": item.stat().st_size, "sha256": file_digest(item)}
                 for item in sorted(folder.rglob("*")) if item.is_file() and not item.is_symlink()}
        return {"folder": str(folder), "files": files}
    links: dict[str, str] = {}
    for item, is_link in sorted(walk(folder)):
        relative = item.relative_to(folder).as_posix()
        if is_link:
            links[relative] = os.readlink(item)
        elif item.is_file():
            files[relative] = {"bytes": item.stat().st_size, "sha256": file_digest(item)}
    return {"folder": str(folder), "files": files, "links": links}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old, new = before["files"], after["files"]
    changed = sorted(name for name in set(old) & set(new) if old[name]["sha256"] != new[name]["sha256"])
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    report: dict[str, Any] = {"files_before": len(old), "files_after": len(new), "added": added, "removed": removed, "changed": changed}
    old_links, new_links = before.get("links"), after.get("links")
    moved = False
    if old_links is not None and new_links is not None:
        # Inventaires Linux : liens comparés par leur cible. Sous Windows, aucune clé `links` : rapport d'origine inchangé.
        links = {"added": sorted(set(new_links) - set(old_links)), "removed": sorted(set(old_links) - set(new_links)),
                 "changed": sorted(name for name in set(old_links) & set(new_links) if old_links[name] != new_links[name])}
        report.update(links_before=len(old_links), links_after=len(new_links), links=links)
        moved = any(links.values())
    report["status"] = "unchanged" if not (added or removed or changed or moved) else "changed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    take = sub.add_parser("snapshot")
    take.add_argument("--folder", type=Path, required=True)
    take.add_argument("--output", type=Path, required=True)
    diff = sub.add_parser("compare")
    diff.add_argument("--before", type=Path, required=True)
    diff.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        result = snapshot(args.folder)
        args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"files": len(result["files"]), "output": str(args.output)}))
        return 0
    report = compare(*(json.loads(path.read_text(encoding="utf-8")) for path in (args.before, args.after)))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["status"] == "unchanged" else 1


if __name__ == "__main__":
    sys.exit(main())
