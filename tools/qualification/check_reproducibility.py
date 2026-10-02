"""Regenerate the synthetic fixtures in a temporary directory and compare bytes; the repository is never rewritten."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from evidence_io import EVALS, LOCAL_QA, checked_output, write_json_exclusive
from generate import EVAL_FILES, ROOT, generate


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def compare(root: Path = ROOT) -> dict:
    folder = root / "evals/qualification-v2.1"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    relative = [Path("fixtures") / entry["path"] for entry in manifest["entries"]] + [Path("evals/qualification-v2.1") / name for name in EVAL_FILES]
    frozen = json.loads((folder / "final.freeze.json").read_text(encoding="utf-8"))["canonical_sha256"]
    before = {path.as_posix(): sha(root / path) for path in relative}
    with tempfile.TemporaryDirectory(prefix="qualification-repro-") as directory:
        generation = generate(Path(directory))
        after = {path.as_posix(): sha(Path(directory) / path) for path in relative}
    changed = [path for path in before if before[path] is None or before[path] != after[path]]
    final_path = "evals/qualification-v2.1/final.json"
    final_same = before[final_path] is not None and before[final_path] == after[final_path]
    status = "PASS" if not changed and generation["final_canonical_sha256"] == frozen else "FAIL"
    return {"status": status, "comparison": "SHA-256 of delivered files versus a sequential regeneration in a temporary directory; delivered files untouched",
            "files_compared": len(relative), "changed_paths": changed, "final_json_identical_bytes": final_same,
            "regenerated_final_matches_freeze": generation["final_canonical_sha256"] == frozen, "frozen_final_sha256": frozen,
            "delivered_sha256": before, "regenerated_sha256": after, "generation": {key: value for key, value in generation.items() if key != "manifest"}}


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Nouveau rapport sous evals/qualification-v2.1/reports/ ou, hors Git, sous .runtime/qa/")
    args = parser.parse_args(argv)
    try:
        output = checked_output(args.output, [EVALS / "reports", LOCAL_QA])
    except ValueError as error:
        parser.error(str(error))
    result = compare()
    write_json_exclusive(output, result)
    print(json.dumps({key: result[key] for key in ("status", "files_compared", "changed_paths", "final_json_identical_bytes", "regenerated_final_matches_freeze")}))
    if result["status"] != "PASS":
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
