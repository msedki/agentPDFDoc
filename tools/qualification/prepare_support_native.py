"""Matérialiser les huit cas DOCX synthétiques du complément I5/PJ.

Aucun modèle, service, réseau ni ingestion produit n'est démarré. Les six cas
de développement conservent les annotations gelées ; deux points de condition
distincts préparent le parcours 4B réel, dont l'exécution reste à démontrer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qualification.grounded_campaign import generate_document  # noqa: E402
from tools.qualification.support_benchmark import load_fixture  # noqa: E402

FIXTURE_SHA256 = "4209a27891de7af2d080094767a2b19abfab358f1bc8b735debbe2637e8bbb3b"
SELECTED_CASES = {"D01", "D05", "D11", "D13", "D17", "D21"}
CONDITION_CASES = (
    ("n07", "Output current: 17 mA at TA = 33 °C.", "Quel courant de sortie est établi à TA = 67 °C ?"),
    ("n08", "Output current: 23 mA at TA = 28 °C.", "What output current is established at TA = 74 °C?"),
)


def write_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(fixture_path: Path, output: Path) -> dict:
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != FIXTURE_SHA256:
        raise ValueError("The development fixture differs from the frozen native recipe")
    fixture = load_fixture(fixture_path)
    selected = [case for case in fixture["cases"] if case["id"] in SELECTED_CASES]
    if len(selected) != len(SELECTED_CASES):
        raise ValueError("Missing frozen development case")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases, documents, recipe = [], [], []

    def document(key: str, text: str) -> None:
        spec = {"format": "docx", "paragraphs": [text]}
        original = output / (key + ".docx")
        sha = generate_document(spec, original)
        documents.append({"key": key, "path": str(original), "sha256": sha, "format": "docx"})
        recipe.append({"key": key, **spec})

    for case in selected:
        keys = []
        for index, source in enumerate(case["sources"], 1):
            key = case["id"].lower() + "_" + str(index)
            keys.append(key)
            document(key, source["text"])
        cases.append({"id": "N_" + case["id"], "question": case["question"], "document_key": keys[0],
                      "scope": {"kind": "documents", "document_keys": keys}, "mode": case["mode"], "repeats": 1,
                      "annotation": {"source_fixture_case": case["id"], "expected": case["expected"],
                                     "rationale": case["rationale"]}})
    for key, text, question in CONDITION_CASES:
        document(key, text)
        cases.append({"id": key.upper(), "question": question, "document_key": key,
                      "mode": "question", "repeats": 1,
                      "annotation": {"expected": {"exact_support": False},
                                     "rationale": "The observed point differs from the requested point; preserve the original current and condition with explicit limitation.",
                                     "requires_actual_4b_call": True}})
    data = {"schema_version": 1, "protocol_id": "I5-PJ-NATIVE-SUPPORT-20261109",
            "kind": "development synthetic DOCX; not heldout", "documents": documents, "cases": cases}
    write_json(output / "recipe.json", {"schema_version": 1, "documents": recipe, "cases": cases})
    # Written last: a partial materialization cannot be mistaken for ready inputs.
    write_json(output / "inputs.json", data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/support_i5_pj_dev.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.fixtures, args.output)
    print(json.dumps({"output": str(args.output.resolve()), "documents": len(result["documents"]),
                      "cases": len(result["cases"]), "model_inference": "NOT_RUN"}))


if __name__ == "__main__":
    main()
