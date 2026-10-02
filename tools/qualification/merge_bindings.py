"""Fusionne des snapshots de bindings publiés par document après contrôle du SHA-256 de chaque fichier.

Chaque snapshot vient de capture_bindings.py. Doublons de document, IDs réels partagés entre clés, SHA original
divergent du manifeste ou texte de bloc altéré sont refusés ; la sortie est un nouveau fichier sous runtime/ ou, hors
Git, sous .runtime/qa/.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evidence_io import EVALS, LOCAL_QA, ROOT, checked_output, write_json_exclusive

REQUIRED = ("document_id", "version_id", "extraction_revision_id", "generation_id", "file_sha256", "pages")


def check_binding(key: str, binding: dict, fixture_sha: str | None) -> None:
    if fixture_sha is None:
        raise ValueError(f"{key} : clé absente du manifeste contrôlé")
    if any(not binding.get(field) for field in REQUIRED):
        raise ValueError(f"{key} : document, version, révision, génération, SHA original et pages réels requis")
    if binding["file_sha256"] != fixture_sha:
        raise ValueError(f"{key} : SHA de l'original différent de la fixture gelée")
    for index, page in enumerate(binding["pages"]):
        if page.get("version_id") != binding["version_id"] or page.get("page", {}).get("page_index") != index:
            raise ValueError(f"{key} : page {index} hors de la version immuable capturée")
        for block in page.get("blocks", []):
            raw = block.get("raw_text")
            if not isinstance(raw, str) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != block.get("source_text_hash"):
                raise ValueError(f"{key} : texte exact de bloc absent ou altéré")
            if block.get("extraction_revision_id") != binding["extraction_revision_id"]:
                raise ValueError(f"{key} : bloc d'une autre révision d'extraction")


def merge(inputs: list[tuple[Path, str]], manifest: dict, root: Path = ROOT) -> dict:
    fixtures = {entry["key"]: entry["sha256"] for entry in manifest["entries"]}
    owners: dict[tuple[str, Any], str]
    sources: list[dict[str, Any]]
    documents, owners, sources = {}, {}, []
    for path, expected in inputs:
        data = Path(path).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected.lower():
            raise ValueError(f"SHA-256 du snapshot {Path(path).name} différent de la valeur attendue")
        if any(source["sha256"] == actual for source in sources):
            raise ValueError(f"Snapshot {Path(path).name} fourni deux fois")
        snapshot = json.loads(data.decode("utf-8"))
        entries = snapshot.get("documents")
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"Snapshot {Path(path).name} sans document")
        for key, binding in entries.items():
            if key in documents:
                raise ValueError(f"{key} présent dans plusieurs snapshots : doublon ou conflit refusé")
            check_binding(key, binding, fixtures.get(key))
            for field in ("document_id", "version_id", "generation_id"):
                other = owners.setdefault((field, binding[field]), key)
                if other != key:
                    raise ValueError(f"{field} {binding[field]} lié à la fois à {other} et {key}")
            documents[key] = copy.deepcopy(binding)
        resolved, local = Path(path).resolve(), LOCAL_QA.resolve()
        # Sous Linux, `.runtime` peut être un lien vers un autre volume (W018) : le chemin reste désigné dans le projet.
        label = (resolved.relative_to(root).as_posix() if resolved.is_relative_to(root)
                 else (Path(".runtime/qa") / resolved.relative_to(local)).as_posix() if resolved.is_relative_to(local) else str(resolved))
        sources.append({"path": label, "sha256": actual,
                        "captured_at_utc": snapshot.get("captured_at_utc"), "method": snapshot.get("method"), "document_keys": sorted(entries)})
    return {"merged_at_utc": datetime.now(UTC).isoformat(),
            "method": "Merge of per-document published snapshots after SHA-256 check of each file, manifest file SHA and exact block text hashes; no API call.",
            "sources": sources, "documents": dict(sorted(documents.items()))}


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", nargs=2, action="append", metavar=("SNAPSHOT", "SHA256"), required=True,
                        help="Snapshot *-published.json (evals/qualification-v2.1/runtime/ ou .runtime/qa/) et son SHA-256 attendu")
    parser.add_argument("--output", type=Path, required=True,
                        help="Nouveau fichier sous evals/qualification-v2.1/runtime/ ou, hors Git, sous .runtime/qa/")
    args = parser.parse_args(argv)
    folders = [(EVALS / "runtime").resolve(), LOCAL_QA.resolve()]
    inputs = [(Path(path), sha) for path, sha in args.input]
    if any(not any(path.resolve().is_relative_to(folder) for folder in folders) for path, _ in inputs):
        parser.error("Les snapshots doivent provenir de evals/qualification-v2.1/runtime/ ou de .runtime/qa/")
    try:
        output = checked_output(args.output, folders, sources=tuple(path for path, _ in inputs))
        merged = merge(inputs, json.loads((EVALS / "manifest.json").read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    write_json_exclusive(output, merged)
    summary = {"output": str(output), "documents": sorted(merged["documents"]), "sources": len(merged["sources"])}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
