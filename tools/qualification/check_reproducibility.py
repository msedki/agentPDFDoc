"""Regenerate only the owned synthetic fixtures and compare actual bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from generate import ROOT, generate


def main():
    folder = ROOT / "evals/qualification-v2.1"
    before = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    frozen_before = (folder / "final.json").read_bytes()
    actual_before = {entry["path"]: hashlib.sha256((ROOT / "fixtures" / entry["path"]).read_bytes()).hexdigest() for entry in before["entries"]}
    generation = generate()
    actual_after = {path: hashlib.sha256((ROOT / "fixtures" / path).read_bytes()).hexdigest() for path in actual_before}
    changed = [path for path in actual_before if actual_before[path] != actual_after[path]]
    final_same = frozen_before == (folder / "final.json").read_bytes()
    result = {"status": "PASS" if not changed and final_same else "FAIL", "comparison": "Actual SHA-256 before and after sequential regeneration in locked venv", "pdf_files_compared": len(actual_before), "changed_paths": changed, "final_json_identical_bytes": final_same, "before_pdf_sha256": actual_before, "after_pdf_sha256": actual_after, "generation": generation}
    (folder / "reports/reproducibility-2026-09-30.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "pdf_files_compared", "changed_paths", "final_json_identical_bytes")}))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
