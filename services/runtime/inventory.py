"""Inventaire reproductible des versions, licences déclarées et avis présents."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .artifacts import ROOT, file_hash, write_json_atomic
from .platforms import WINDOWS, entries_for_platform, executable_name, platform_id


def notice(path: Path) -> dict:
    location = path.relative_to(ROOT) if path.resolve().is_relative_to(ROOT) else path.resolve()
    return {"path": str(location), "bytes": path.stat().st_size, "sha256": file_hash(path)}


def license_inventory(output: Path) -> dict:
    result: dict[str, Any] = {"created_at_utc": datetime.now(UTC).isoformat(),
                              "scope": "installed project dependencies and provisioned artefacts; metadata is not legal certification",
                              "python": [], "npm": [], "artifacts": [], "native_notices": [],
                              "runtime_prerequisites": [], "limits": []}
    python_root = Path(sys.base_prefix)
    # Windows : LICENSE.txt à la racine de l'installation ; Linux (python-build-standalone) : dans lib/python3.x.
    python_licenses = [python_root / "LICENSE.txt",
                       python_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"]
    result["runtime_prerequisites"].append({"name": "CPython", "version": sys.version.split()[0],
        "path": str(python_root), "redistributed_in_project": python_root.resolve().is_relative_to(ROOT),
        "notices": [notice(path) for path in python_licenses if path.is_file()]})
    result["runtime_prerequisites"].append({"name": "uv", "version": "0.12.21",
        "redistributed_in_project": True, "notices": [notice(path) for path in
            sorted((ROOT / ".runtime/bootstrap").glob("uv-*.dist-info/licenses/*")) if path.is_file()]})
    node_path = shutil.which(executable_name("node"))
    if node_path:
        node_root = Path(node_path).parent
        result["runtime_prerequisites"].append({"name": "Node.js", "path": str(node_path),
            "redistributed_in_project": False, "notices": [notice(path) for path in
                [node_root / "LICENSE", node_root / "node_modules/corepack/LICENSE.md"] if path.is_file()]})
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata.get("Name", "")):
        # Distributions installées sur disque : locate_file rend un pathlib.Path (resolve() l'exige déjà).
        files = [cast(Path, distribution.locate_file(file)) for file in distribution.files or []]
        notices = [notice(path) for path in files if path.is_file() and path.resolve().is_relative_to(ROOT)
                   and any(key in path.name.lower() for key in ("license", "copying", "notice"))]
        metadata = distribution.metadata
        result["python"].append({"name": metadata.get("Name"), "version": distribution.version,
            "license_expression": metadata.get("License-Expression"),
            "license_field": metadata.get("License"),
            "license_classifiers": [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")],
            "notices": notices})
    packages = ROOT / "apps/web/node_modules/.pnpm"
    seen = set()
    for path in sorted(packages.rglob("package.json")):
        if path.is_symlink() or "node_modules" not in path.parts:
            continue
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        identity = (package.get("name"), package.get("version"))
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        notices = [notice(p) for p in path.parent.iterdir() if p.is_file() and
                   any(term in p.name.lower() for term in ("license", "copying", "notice"))]
        result["npm"].append({"name": identity[0], "version": identity[1], "license": package.get("license"),
                              "metadata_sha256": file_hash(path), "notices": notices})
    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    result["platform"] = platform_id()
    for group, artifacts in lock["groups"].items():
        # Artefacts de ce poste seulement : ceux de l'autre plateforme ne sont ni provisionnés ni livrés ici.
        for artifact in entries_for_platform(artifacts):
            path = ROOT / artifact["target"]
            result["artifacts"].append({"group": group, "publisher": artifact.get("publisher"),
                "version": artifact.get("version"), "revision": artifact.get("revision"),
                "declared_license": artifact.get("license"), "source": artifact["url"],
                "file": notice(path) if path.is_file() else None, "provisioned": path.is_file()})
    for parent in (ROOT / ".runtime/bin", ROOT / ".runtime/models"):
        for path in sorted(parent.rglob("*")):
            if path.is_file() and any(term in path.name.lower() for term in ("license", "copying", "notice")):
                result["native_notices"].append(notice(path))
    comparison_manifest = ROOT / ".runtime/manifests/embedding-comparison.json"
    comparison_lock = ROOT / "config/embedding-comparison.lock.json"
    if comparison_manifest.is_file() and comparison_lock.is_file():
        data = json.loads(comparison_manifest.read_text(encoding="utf-8"))
        comparison = json.loads(comparison_lock.read_text(encoding="utf-8"))
        entries = [*comparison["files"]]
        if comparison.get("license_notice"):
            entries.append(comparison["license_notice"])
        result["optional_embedding_comparison"] = {
            "purpose": comparison["scope"], "model_id": comparison["model_id"],
            "revision": comparison["revision"], "manifest_state": data["state"],
            "lock_sha256": file_hash(comparison_lock), "manifest_sha256": file_hash(comparison_manifest),
            "artifacts": [{"publisher": entry.get("publisher"), "declared_license": entry.get("license"),
                "source": entry["url"], "file": notice(ROOT / entry["target"])
                if (ROOT / entry["target"]).is_file() else None} for entry in entries],
            "limit": "Presence and metadata inventory; does not prove inference or an IBM-bundled NOTICE.",
        }
    for key, name in (("ollama_model", "ollama-model.json"), ("ollama_text_model", "ollama-model-text.json")):
        manifest = ROOT / ".runtime/manifests" / name
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            result[key] = {"model": data["model"], "license_notice": data.get("license"),
                           "derived_from": data.get("source_model"), "manifest_sha256": file_hash(manifest)}
    result["limits"] = [
        "Tesseract Windows installed copy has verified local hashes, but installer provenance not independently authenticated"
        if WINDOWS else "Tesseract 5.4.0 and Leptonica 1.87.0 built locally from the locked source archives (tesseract-source)",
        "License declarations and bundled notice paths are recorded; no compatibility or redistribution opinion is inferred",
        "Development dependencies are included because they are installed in this environment",
    ]
    write_json_atomic(output, result)
    return {"path": str(output), "python_distributions": len(result["python"]), "npm_packages": len(result["npm"]),
            "artifact_files": len(result["artifacts"]), "bundled_notices": len(result["native_notices"]), "limits": result["limits"]}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "RAG_Local_Agents/reports/licenses.json")
    args = parser.parse_args()
    print(json.dumps(license_inventory(args.output), ensure_ascii=False, indent=2))
