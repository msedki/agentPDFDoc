"""Prérequis locaux copiés dans le projet, sans installation globale."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .artifacts import ROOT, file_hash, write_json_atomic


def tesseract(profile: dict, *, offline: bool = False) -> dict:
    target_exe = (ROOT / profile["pdf"]["tesseract_cmd"]).resolve()
    manifest_path = ROOT / ".runtime/manifests/tesseract-installed-copy.json"
    if target_exe.is_file() and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = (ROOT / item["path"]).resolve()
            if not path.is_relative_to(target_exe.parent) or not path.is_file() or file_hash(path) != item["sha256"]:
                raise ValueError("Copie Tesseract non conforme au manifeste ; aucun remplacement implicite")
        return {"status": "verified_installed_copy", "publisher_provenance": "not_independently_authenticated"}
    if target_exe.exists() or manifest_path.exists():
        raise ValueError("Copie Tesseract incomplète : conserver et diagnostiquer les fichiers")
    candidates = [Path(shutil.which("tesseract.exe") or "__absent__")]
    for parent in [os.environ.get("LOCALAPPDATA"), os.environ.get("PROGRAMFILES")]:
        if parent:
            candidates.extend([Path(parent) / "Programs/Tesseract-OCR/tesseract.exe",
                               Path(parent) / "Tesseract-OCR/tesseract.exe"])
    executable = next((p.resolve() for p in candidates if p.is_file()), None)
    if executable is None:
        raise FileNotFoundError("Prérequis Tesseract5.4.0 Windows absent ; fournir une installation locale vérifiable. Aucun installateur tiers n'est téléchargé automatiquement.")
    version = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=15, check=True).stdout
    if not version.startswith("tesseract v5.4.0"):
        raise ValueError("Le prérequis installé doit correspondre à Tesseract5.4.0 du profil verrouillé")
    if target_exe.parent.exists():
        raise ValueError("Destination Tesseract existante sans manifeste")
    target_exe.parent.mkdir(parents=True)
    records = []
    paths = [executable, *sorted(executable.parent.glob("*.dll"))]
    paths.extend(p for p in executable.parent.rglob("*") if p.is_file() and
                 any(term in p.name.lower() for term in ("license", "copying", "notice")))
    for path in paths:
        relative = path.relative_to(executable.parent)
        target = target_exe.parent / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append({"path": str(target.relative_to(ROOT)), "sha256": file_hash(target), "size": target.stat().st_size})
    manifest = {"source": str(executable.parent), "version_output": version,
                "origin": "existing installed Windows build; publisher package provenance not independently authenticated",
                "files": records, "offline": offline}
    write_json_atomic(manifest_path, manifest)
    return {"status": "copied_local_prerequisite", "files": len(records), "publisher_provenance": "not_independently_authenticated"}
