"""Fabrication du kit hors ligne de l'atelier (DIST-04) : liste blanche, exclusions, SHA256SUMS et manifeste.

Le kit contient le code d'exécution, l'interface construite, uv, CPython, le cache uv des roues, les binaires et
modèles déjà vérifiés et leurs manifestes. Rien de l'utilisateur ni du chantier n'y entre : corpus `PDF/`, données,
évaluations, sauvegardes, essais, tests, dossier de chantier, dépôt Git. Un fichier texte qui garde un chemin du poste
de fabrication arrête la fabrication, sauf le champ `source` du manifeste Tesseract, neutralisé (il ne sert à aucune
vérification). Les choix encore ouverts (P2 modèle Qwen source, P3 bibliothèques GPU d'Ollama) sont des options.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Chemins relatifs à la racine du dépôt, fichiers ou dossiers copiés entiers (moins les exclusions).
INCLUDED = ("services", "config", "apps/web/out", "apps/web/package.json", "apps/web/pnpm-lock.yaml", "rag.ps1", "bootstrap.ps1",
            "pyproject.toml", "uv.lock", "README.md", "CHANGELOG.md", "docs", "tools/corpus", "tools/dist",
            ".runtime/bin", ".runtime/models", ".runtime/python", ".runtime/bootstrap", ".runtime/cache/uv", ".runtime/manifests",
            ".runtime/model-metadata")
# Motifs exclus partout (fnmatch sur le chemin relatif en POSIX) ; la comparaison Granite n'appartient pas au produit.
EXCLUDED = ("*/__pycache__/*", "*.pyc", ".runtime/models/granite-*", ".runtime/models/granite-*/*", "*/.git/*", "*/node_modules/*")
# Ne doivent jamais apparaître dans le kit, quelle que soit la liste blanche.
FORBIDDEN_PREFIXES = ("PDF/", ".runtime/data/", ".runtime/qa/", ".runtime/evals/", ".runtime/q/", "backups/", "tests/", "RAG_Local_Agents/",
                      ".git/", "evals/", "fixtures/")
GPU_DIRECTORIES = ("cuda_v12", "cuda_v13", "vulkan")  # P3 : sous lib/ollama, inutiles avec num_gpu 0 si H1 est vérifiée.
TEXT_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".py", ".ps1", ".txt", ".toml", ".lock", ".cfg"}
TEXT_SCAN_LIMIT = 32 * 1024 * 1024
LAUNCHER = "Installer l'atelier.cmd"
NOTICES = "THIRD_PARTY_NOTICES.md"
LAUNCHER_CONTENT = (b"@echo off\r\n"
                    b"powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%~dp0tools\\dist\\install.ps1\" %*\r\n"
                    b"pause\r\n")
CHUNK = 1024 * 1024


def stream_copy(source: Path, target: Path) -> tuple[str, int]:
    """Copie par blocs avec hachage : aucun fichier n'est chargé entier en mémoire."""
    digest, size = hashlib.sha256(), 0
    with source.open("rb") as reader, target.open("xb") as writer:
        for block in iter(lambda: reader.read(CHUNK), b""):
            digest.update(block)
            writer.write(block)
            size += len(block)
    return digest.hexdigest(), size


def stream_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def excluded(relative: str, *, without_gpu: bool) -> bool:
    if any(fnmatch.fnmatch(relative, pattern) for pattern in EXCLUDED):
        return True
    return without_gpu and relative.startswith(".runtime/bin/ollama-") and any(f"/lib/ollama/{name}/" in relative for name in GPU_DIRECTORIES)


def walk_files(folder: Path):
    """Fichiers d'un dossier sans traverser jonction ni lien : uv recrée sa jonction de version mineure à l'installation,
    et l'écarter dès le dossier évite d'interroger chaque fichier (chaque accès disque passe par l'antivirus du poste)."""
    pending = [folder]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink() or entry.is_junction():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)


def selected_files(root: Path, *, without_gpu: bool = False) -> list[str]:
    files: set[str] = set()
    for entry in INCLUDED:
        path = root / entry
        candidates = [path] if path.is_file() else (sorted(walk_files(path)) if path.is_dir() and not (path.is_symlink() or path.is_junction()) else [])
        for item in candidates:
            relative = item.relative_to(root).as_posix()
            if not excluded(relative, without_gpu=without_gpu):
                files.add(relative)
    leaked = sorted(name for name in files if name.startswith(FORBIDDEN_PREFIXES))
    if leaked:
        raise ValueError(f"Entrée interdite dans le kit : {leaked[:5]}")
    return sorted(files)


def host_markers(root: Path) -> list[str]:
    markers = {str(root), str(root).replace("\\", "/"), str(root).replace("\\", "\\\\")}
    home = os.environ.get("USERPROFILE")
    if home:
        markers |= {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}
    return sorted(marker for marker in markers if len(marker) > 3)


def neutralized(relative: str, data: bytes) -> bytes:
    """Seul le champ source du manifeste Tesseract est réécrit : il désigne l'installation copiée sur le poste de fabrication."""
    if relative != ".runtime/manifests/tesseract-installed-copy.json":
        return data
    manifest = json.loads(data.decode("utf-8"))
    manifest["source"] = "<poste de fabrication>/Tesseract-OCR"
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_kit(output: Path, *, root: Path = ROOT, version: str, without_gpu: bool = False, commit: str | None = None) -> dict[str, Any]:
    output = output.resolve()
    if output.is_relative_to(root.resolve()) or (output.exists() and any(output.iterdir())):
        raise ValueError("Le kit exige un dossier neuf hors du dépôt")
    files = selected_files(root, without_gpu=without_gpu)
    markers = host_markers(root)
    sums: list[str] = []
    sizes: dict[str, int] = {}
    leaks: list[str] = []
    for relative in files:
        source, target = root / relative, output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(relative).suffix.lower() in TEXT_SUFFIXES and source.stat().st_size < TEXT_SCAN_LIMIT:
            data = neutralized(relative, source.read_bytes())
            content = data.decode("utf-8", errors="ignore")
            leaks += [relative for marker in markers if marker in content][:1]
            target.write_bytes(data)
            digest, size = hashlib.sha256(data).hexdigest(), len(data)
        else:
            digest, size = stream_copy(source, target)
        shutil.copystat(source, target)
        sums.append(f"{digest}  {relative}")
        group = relative.split("/")[1] if relative.startswith(".runtime/") else relative.split("/")[0]
        sizes[group] = sizes.get(group, 0) + size
    # Avis de tiers (DIST-07) : composants, licences déclarées, textes présents et manques connus.
    from tools.dist.notices import third_party_notices

    notices = third_party_notices(root, files, version).encode("utf-8")
    (output / NOTICES).write_bytes(notices)
    sums.append(f"{hashlib.sha256(notices).hexdigest()}  {NOTICES}")
    # Lanceur à double-cliquer : Bypass ne vaut que pour cette session et ne touche pas la politique du poste.
    launcher = output / LAUNCHER
    launcher.write_bytes(LAUNCHER_CONTENT)
    sums.append(f"{hashlib.sha256(LAUNCHER_CONTENT).hexdigest()}  {LAUNCHER}")
    if leaks:
        shutil.rmtree(output)
        raise ValueError(f"Chemin du poste de fabrication présent dans le kit : {sorted(set(leaks))[:5]}")
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    manifest = {"format": "atelier-kit-v1", "version": version, "built_utc": dt.datetime.now(dt.UTC).isoformat(), "source_commit": commit,
                "files": len(files), "bytes": sum(sizes.values()), "bytes_by_group": dict(sorted(sizes.items())),
                "options": {"gpu_libraries_removed": without_gpu, "qwen_source_model": "included"},
                "excluded_patterns": list(EXCLUDED), "forbidden_prefixes": list(FORBIDDEN_PREFIXES),
                "sha256sums_sha256": hashlib.sha256((output / "SHA256SUMS").read_bytes()).hexdigest()}
    (output / "kit-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def verify_kit(folder: Path) -> dict[str, Any]:
    """Contrôle d'intégrité d'un kit copié : chaque empreinte de SHA256SUMS, aucun fichier en trop."""
    folder = folder.resolve()
    expected = {}
    for line in (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    altered = [relative for relative, digest in expected.items()
               if not (folder / relative).is_file() or stream_hash(folder / relative) != digest]
    present = {item.relative_to(folder).as_posix() for item in folder.rglob("*") if item.is_file()} - {"SHA256SUMS", "kit-manifest.json"}
    return {"files": len(expected), "altered_or_missing": sorted(altered), "unexpected": sorted(present - set(expected)),
            "status": "verified" if not altered and present == set(expected) else "failed"}


def install_copy(folder: Path, target: Path) -> dict[str, Any]:
    """Copie vérifiée en un seul passage : chaque fichier de SHA256SUMS est haché pendant sa copie.

    Un fichier absent ou différent arrête la copie et retire la copie partielle : rien d'altéré n'est installé.
    Les fichiers du kit absents de SHA256SUMS ne sont pas copiés."""
    folder, target = folder.resolve(), target.resolve()
    if target.exists():
        raise ValueError(f"Destination déjà présente, jamais remplacée : {target}")
    entries = [line.split("  ", 1) for line in (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line]
    target.mkdir(parents=True)
    copied = 0
    try:
        for digest, relative in entries:
            source, destination = folder / relative, target / relative
            if not source.is_file():
                raise ValueError(f"Fichier du kit absent : {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            actual, _ = stream_copy(source, destination)
            if actual != digest:
                raise ValueError(f"Fichier du kit altéré : {relative} (empreinte différente)")
            shutil.copystat(source, destination)
            copied += 1
        for name in ("SHA256SUMS", "kit-manifest.json"):
            shutil.copy2(folder / name, target / name)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return {"status": "copied", "files": copied, "target": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--without-gpu", action="store_true", help="P3 : retirer cuda_v12, cuda_v13 et vulkan d'Ollama (après vérification de H1)")
    check = sub.add_parser("verify")
    check.add_argument("--kit", type=Path, required=True)
    copy = sub.add_parser("install-copy", help="Copie vérifiée du kit vers le dossier programme, en un seul passage")
    copy.add_argument("--kit", type=Path, required=True)
    copy.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        result = verify_kit(args.kit)
    elif args.command == "install-copy":
        try:
            result = install_copy(args.kit, args.target)
        except ValueError as error:
            result = {"status": "failed", "message": str(error)}
    else:
        import subprocess
        import tomllib

        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip() or None
        result = build_kit(args.output, version=version, without_gpu=args.without_gpu, commit=head)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status", "verified") in {"verified", "copied"} else 1


if __name__ == "__main__":
    sys.exit(main())
