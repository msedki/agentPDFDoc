"""Provisionnement explicite du seul candidat d'embedding, séparé du runtime."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from .artifacts import ROOT, download, file_hash, read_json_atomic, write_json_atomic


def provision(*, offline: bool = False) -> dict:
    lock_path = ROOT / "config/embedding-comparison.lock.json"
    lock = read_json_atomic(lock_path)
    manifest_path = ROOT / ".runtime/manifests/embedding-comparison.json"
    result = {"schema_version": 1, "purpose": "development-only comparison; active E5 unchanged",
        "lock_sha256": file_hash(lock_path), "revision": lock["revision"],
        "started_at_utc": datetime.now(UTC).isoformat(), "state": "provisioning", "files": []}
    write_json_atomic(manifest_path, result)
    try:
        for entry in lock["files"]:
            result["files"].append(download(entry, ROOT / entry["target"], offline=offline))
            write_json_atomic(manifest_path, result)
        entry = lock.get("license_notice")
        if entry:
            result["license_notice"] = download(entry, ROOT / entry["target"], offline=offline)
    except Exception as exc:
        result["state"] = "failed"
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        write_json_atomic(manifest_path, result)
        raise
    result["state"] = "provisioned_not_inference_validated"
    result["completed_at_utc"] = datetime.now(UTC).isoformat()
    write_json_atomic(manifest_path, result)
    return {"manifest": str(manifest_path), "files_verified": len(result["files"]), "state": result["state"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(provision(offline=args.offline), ensure_ascii=False, indent=2))
