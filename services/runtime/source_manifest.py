"""Identité des sources livrées : hashes des fichiers de travail, et commit Git quand il existe."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .artifacts import ROOT, file_hash, write_json_atomic

FILES = ("AGENTS.md", "CLAUDE.md", "rag.ps1", "bootstrap.ps1", "pyproject.toml", "uv.lock",
         "config/local16.yaml", "config/artifacts.lock.json", "config/embedding-comparison.lock.json",
         "config/models.lock.json", "config/qdrant.collection.json",
         "apps/web/package.json", "apps/web/pnpm-lock.yaml", "apps/web/next.config.mjs",
         "apps/web/tsconfig.json", "apps/web/playwright.config.ts",
         ".runtime/manifests/ollama-model.json", ".runtime/manifests/ollama-model-text.json",
         ".runtime/manifests/artifacts.json",
         ".runtime/manifests/embedding-comparison.json")


def git_identity(root: Path = ROOT) -> dict:
    """HEAD et état modifié du dépôt dont root est la racine ; None sans Git ou hors dépôt."""
    unknown = {"git_commit": None, "git_dirty": None}
    git = shutil.which("git")
    if not git:
        return {**unknown, "git_status": "git_unavailable"}

    def run(*args: str) -> str | None:
        # --no-optional-locks : aucun index.lock pris pendant un commit concurrent.
        try:
            completed = subprocess.run([git, "--no-optional-locks", "-C", str(root), *args], capture_output=True,
                                       text=True, encoding="utf-8", errors="replace", timeout=60,
                                       stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout if completed.returncode == 0 else None

    top = run("rev-parse", "--show-toplevel")
    if top is None:
        # Hors dépôt, safe.directory refusé ou délai : Git n'a pas pu répondre.
        return {**unknown, "git_status": "git_error"}
    if Path(top.strip()).resolve() != Path(root).resolve():
        return {**unknown, "git_status": "not_repository_root"}
    head, porcelain = run("rev-parse", "--verify", "HEAD"), run("status", "--porcelain")
    if head is None or porcelain is None:
        return {**unknown, "git_status": "git_error"}
    return {"git_commit": head.strip(), "git_dirty": bool(porcelain.strip()), "git_status": "ok"}


def capture(root: Path = ROOT) -> dict:
    started = datetime.now(UTC).isoformat()
    identity = git_identity(root)
    selected = set()
    extensions = {".py", ".ps1", ".sql", ".json", ".yaml", ".yml", ".ts", ".tsx", ".css", ".md", ".mjs"}
    for folder in ("services", "packages", "tests", "tools/qualification", "apps/web/src", "apps/web/tests", ".agents/skills", "RAG_Local_Agents/skills"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and path.suffix in extensions:
                selected.add(path)
    selected.update(path for path in (root / "RAG_Local_Agents").glob("*.md") if path.is_file())
    for name in FILES:
        path = root / name
        if path.is_file():
            selected.add(path)
    records = []
    for path in sorted(selected):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Source hors racine ou lien refusé")
        before = path.stat()
        digest = file_hash(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Source modifiée pendant capture : {path.relative_to(root)}")
        records.append({"path": path.relative_to(root).as_posix(), "bytes": after.st_size, "sha256": digest})
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema_version": 1, "started_at_utc": started, "completed_at_utc": datetime.now(UTC).isoformat(),
            "kind": "working_files_sha256_manifest", "source_fingerprint": hashlib.sha256(encoded).hexdigest(),
            **identity, "files": records,
            "limits": "File hashes observed during capture are the source identity; git_commit is HEAD read before "
                      "hashing and git_dirty reflects git status --porcelain (tracked and untracked, not ignored)."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture()
    write_json_atomic(args.output, result)
    print(json.dumps({"path": str(args.output), "files": len(result["files"]),
                      "source_fingerprint": result["source_fingerprint"]}))
