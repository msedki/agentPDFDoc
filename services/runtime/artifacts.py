"""Téléchargements explicites et vérifiés ; jamais appelé au démarrage nominal."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_LOCK = ROOT / "config" / "artifacts.lock.json"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Sur NTFS, un lecteur sans FILE_SHARE_DELETE peut empêcher temporairement
    # le remplacement. Chaque écrivain garde son temporaire propre ; seuls
    # les refus transitoires sont repris, dans une fenêtre bornée.
    deadline = time.monotonic() + 5
    while True:
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def read_json_atomic(path: Path) -> Any:
    """Lire une publication complète, avec reprise bornée des conflits NTFS."""
    deadline = time.monotonic() + 5
    while True:
        try:
            with path.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def download(entry: dict[str, Any], target: Path, *, offline: bool = False) -> dict[str, Any]:
    """SHA-256 éditeur ou SHA-1 blob Git du commit officiel obligatoire."""
    expected = entry.get("sha256")
    git_blob = entry.get("git_blob_sha1")
    if not expected and not git_blob:
        raise ValueError("Empreinte attendue absente du verrou de téléchargement")

    def verified(path: Path) -> bool:
        if not path.is_file():
            return False
        if entry.get("size") and path.stat().st_size != entry["size"]:
            return False
        if expected:
            return file_hash(path) == expected
        digest = hashlib.sha1(usedforsecurity=False)
        digest.update(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest() == git_blob

    if verified(target):
        return {**entry, "sha256": file_hash(target), "path": str(target.relative_to(ROOT)), "cached": True}
    if offline:
        raise FileNotFoundError(f"Artefact offline absent ou corrompu : {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    size = int(entry.get("size", 0))
    if shutil.disk_usage(target.parent).free < size + 2 * 1024**3:
        raise RuntimeError(f"Espace disque insuffisant pour {target.name}, réserve disque 2 Gio")
    part = target.with_name(target.name + ".part")
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "agentragpdf-provision/0.1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response, part.open("wb") as output:
                copied = 0
                notified = 0
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(block)
                    copied += len(block)
                    if copied - notified >= 64 * 1024**2:
                        print(f"{target.name} : {copied / 1024**2:.0f} Mio téléchargés", flush=True)
                        notified = copied
                output.flush()
                os.fsync(output.fileno())
            if not verified(part):
                raise ValueError(f"Empreinte non conforme : {target.name}")
            part.replace(target)
            print(f"Vérifié : {target.name} ({target.stat().st_size} octets)", flush=True)
            return {**entry, "sha256": file_hash(target), "path": str(target.relative_to(ROOT)), "cached": False}
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise
            print(f"Téléchargement {target.name}, essai {attempt + 1} interrompu : {type(exc).__name__}", flush=True)
            time.sleep(1)
    raise AssertionError("Téléchargement sans résultat")


def extract_verified_zip(archive_path: Path, destination: Path) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Chemin hors racine dans archive")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Lien symbolique interdit dans archive de runtime")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            files.append({"path": str(target.relative_to(ROOT)), "sha256": file_hash(target), "size": entry.file_size})
    return files


def provision_artifacts(only: str | None = None, *, offline: bool = False) -> dict[str, Any]:
    lock = json.loads(ARTIFACT_LOCK.read_text(encoding="utf-8"))
    manifest_path = ROOT / ".runtime" / "manifests" / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    for name, entries in lock["groups"].items():
        if only and name != only:
            continue
        records = []
        for entry in entries:
            target = ROOT / entry["target"]
            record = download(entry, target, offline=offline)
            if entry.get("extract_to"):
                record["extracted_files"] = extract_verified_zip(target, ROOT / entry["extract_to"])
            records.append(record)
            manifest[name] = records
            write_json_atomic(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    provision_artifacts(args.only, offline=args.offline)
