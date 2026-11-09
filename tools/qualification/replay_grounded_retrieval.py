"""Four pre-registered I3 retrieval counterexamples; no native model/OCR.

Real SQLite/indexer/search/bundler, synthetic extraction and the repository's
named embedding/vector/tokenizer doubles. Run services from --repository.
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repository", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise FileExistsError(args.output)
sys.path[:0] = [str(args.repository), str(args.repository / "tests/unit")]

from test_api_storage import import_fixture, storage  # noqa: E402
from test_iteration2_table_evidence import sparse_table  # noqa: E402
from test_retrieval import CharTokenizer, library_search  # noqa: E402

from services.api.evidence_selection import table_bundle  # noqa: E402
from services.api.retrieval import ocr_evidence_warnings  # noqa: E402

observations = []
with tempfile.TemporaryDirectory(prefix="grounded-retrieval-") as directory:
    base = Path(directory)
    for case in ("long_parent", "footnote", "partial_empty", "mixed_ocr"):
        started = time.perf_counter()
        prepared = storage.__wrapped__(base / case)
        settings, db, _, _ = prepared
        settings.profile["enhanced"] = {"preserve_evidence": True, "structural_reranking": True}
        if case == "long_parent":
            text = "Supply voltage: 3.3 V. " + "Installation instructions. " * 200 + "Ambient temperature: 10 to 45 °C."
            import_fixture(prepared, text=text)
            search, snapshot, _ = library_search(prepared)
            question = "What are the supply voltage and ambient temperature?"
            candidates = asyncio.run(search._candidates(question, snapshot))
            result = asyncio.run(search.search(question, snapshot))
            expanded = [search.resolver.expand_parent(source, snapshot, CharTokenizer(), 900)
                        for source in result["results"]]
            facts = ["Supply voltage: 3.3 V.", "Ambient temperature: 10 to 45 °C."]
            def count(sources, required=facts):
                return sum(any(fact in item["text"] for item in sources) for fact in required)
            observation = {"question": question, "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "parent_tokens_named_double": CharTokenizer().count(text),
                           "candidates": len(candidates), "candidate_facts": count(candidates),
                           "retained": len(result["results"]), "retained_facts": count(result["results"]),
                           "expanded_facts": count(expanded), "required_facts": 2,
                           "accepted": count(expanded) == 2}
        elif case == "footnote":
            rows = [[(0, "Parameter"), (1, "Min"), (2, "Max"), (3, "Unit")],
                    [(0, "Supply voltage (1)"), (1, "0"), (2, "36"), (3, "V")],
                    [(0, "(1) Valid only indoors.")]]
            search, snapshot, source, text = sparse_table(prepared, rows)
            bundle, warnings = table_bundle(db, snapshot, source, question="Quelle plage de tension alimentation ?")
            observation = {"source_text": text, "selected_text": bundle["text"],
                           "warnings": warnings, "accepted": "(1) Valid only indoors." in bundle["text"]}
        elif case == "partial_empty":
            import_fixture(prepared, pages=[{"page_index": 0, "width": 595, "height": 842, "blocks": []}])
            db.execute("UPDATE index_generations SET state='ready_partial',coverage_json=?",
                       (json.dumps({"total": 2, "processed": 1, "unresolved": 1}),))
            search, snapshot, _ = library_search(prepared)
            result = asyncio.run(search.search("Quelle température ?", snapshot))
            observation = {"result_count": len(result["results"]), "warnings": result["warnings"],
                           "accepted": any(w["code"] == "partial_extraction" for w in result["warnings"])}
        else:
            def native(block):
                block["metadata"]["extraction_method"] = "native"
            rows = [[(0, "Parameter"), (1, "Min"), (2, "Max"), (3, "Unit")],
                    [(0, "Supply voltage"), (1, "0"), (2, "36"), (3, "V")]]
            search, snapshot, source, _ = sparse_table(prepared, rows, mutate=native,
                                                     section_title="Recommended operating conditions")
            row = db.one("SELECT metadata_json FROM blocks WHERE id='explicit-heading'")
            metadata = json.loads(row["metadata_json"])
            metadata["metadata"] = {"extraction_method": "ocr"}
            db.execute("UPDATE blocks SET metadata_json=? WHERE id='explicit-heading'", (json.dumps(metadata),))
            bundle, _ = table_bundle(db, snapshot, source)
            warnings = ocr_evidence_warnings([bundle])
            observation = {"block_methods": [block["extraction_method"] for block in bundle["blocks"]],
                           "source_methods": bundle["extraction_methods"], "warning_codes": [w["code"] for w in warnings],
                           "accepted": "ocr" in bundle["extraction_methods"] and bool(warnings)}
        observations.append({"case": case, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), **observation})

report = {"recorded_at": datetime.now(UTC).isoformat(), "repository": str(args.repository),
          "commit": subprocess.check_output(["git", "-C", str(args.repository), "rev-parse", "HEAD"], text=True).strip(),
          "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "limitations": "Synthetic extraction; named embedding/vector/tokenizer doubles; no OCR, E5 or 4B execution.",
          "observations": observations}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
