"""Rejouer les dix sondes littérales figées, sans modèle ni extraction native.

Les entrées viennent du rapport de référence antérieur aux corrections.
L'application et ses helpers de tests sont importés depuis le checkout choisi.
Les sorties préexistantes ne sont jamais remplacées.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve(strict=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path[:0] = [str(repository), str(repository / "tests/unit")]
    from test_enhanced_answers import catalogue, render

    original = json.loads(args.inputs.read_text())
    cases = []
    for case in original["cases"]:
        cat = catalogue(case["question"], case["sources"])
        result = render(cat, [reference["id"] for reference in case["sources"]])
        cases.append({"case": case["case"], "question": case["question"], "sources": case["sources"],
                      "assessment": result["answer_contract"], "answer": result["text"],
                      "support_validation": result.get("support_validation")})
    report = {"kind": original["kind"], "native_model_called": False,
              "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip(),
              "inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "cases": len(cases)}))


if __name__ == "__main__":
    main()
