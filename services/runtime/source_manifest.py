"""Identité des sources livrées quand aucun commit Git n'identifie le dossier."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .artifacts import ROOT, file_hash, write_json_atomic


def capture() -> dict:
    started = datetime.now(UTC).isoformat()
    selected = set()
    extensions = {".py", ".ps1", ".sql", ".json", ".yaml", ".yml", ".ts", ".tsx", ".css", ".md", ".mjs"}
    for folder in ("services", "packages", "tests", "tools/qualification", "apps/web/src", "apps/web/tests", ".agents/skills", "RAG_Local_Agents/skills"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in extensions:
                selected.add(path)
    selected.update(path for path in (ROOT / "RAG_Local_Agents").glob("*.md") if path.is_file())
    for name in ("AGENTS.md", "CLAUDE.md", "rag.ps1", "bootstrap.ps1", "pyproject.toml", "uv.lock",
                 "config/local16.yaml", "config/artifacts.lock.json", "config/embedding-comparison.lock.json",
                 "apps/web/package.json", "apps/web/pnpm-lock.yaml", "apps/web/next.config.ts",
                 "apps/web/tsconfig.json", "apps/web/playwright.config.ts",
                 ".runtime/manifests/ollama-model.json", ".runtime/manifests/ollama-model-text.json",
                 ".runtime/manifests/artifacts.json",
                 ".runtime/manifests/embedding-comparison.json"):
        path = ROOT / name
        if path.is_file():
            selected.add(path)
    records = []
    for path in sorted(selected):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Source hors racine ou lien refusé")
        before = path.stat()
        digest = file_hash(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Source modifiée pendant capture : {path.relative_to(ROOT)}")
        records.append({"path": path.relative_to(ROOT).as_posix(), "bytes": after.st_size, "sha256": digest})
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema_version": 1, "started_at_utc": started, "completed_at_utc": datetime.now(UTC).isoformat(),
            "kind": "working_files_sha256_manifest", "source_fingerprint": hashlib.sha256(encoded).hexdigest(),
            "git_commit": None, "files": records,
            "limits": "File hashes observed during capture; not an atomic repository revision or a Git commit."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture()
    write_json_atomic(args.output, result)
    print(json.dumps({"path": str(args.output), "files": len(result["files"]),
                      "source_fingerprint": result["source_fingerprint"]}))
