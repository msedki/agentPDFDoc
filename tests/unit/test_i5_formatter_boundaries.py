"""Contre-exemples du lecteur de reçus ; rapports synthétiques, SQLite réelles.

Aucun de ces tests ne constitue un parcours QueryService, une ingestion ni une
inférence. La campagne contrôlée réelle doit être exécutée séparément.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tools.qualification import verify_formatter_boundaries as verifier

FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/trust_i5_formatter_boundaries.json"
SOURCE_QUOTE = "Output current: 10 mA at TA = 25 °C."


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@dataclass
class SyntheticReceipts:
    reports: dict[str, Path]
    work_dirs: dict[str, Path]
    application_roots: dict[str, Path]

    def verify(self) -> dict[str, Any]:
        return verifier.verify(FIXTURE, self.reports, self.work_dirs, self.application_roots)

    def mutate_record(self, case_id: str, mutate: Any) -> None:
        report = json.loads(self.reports["candidate"].read_text(encoding="utf-8"))
        record = next(record for record in report["cases"] if record["case_id"] == case_id)
        mutate(record)
        write_json(self.reports["candidate"], report)


@pytest.fixture
def synthetic_receipts(tmp_path: Path) -> SyntheticReceipts:
    frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))
    receipts = SyntheticReceipts({}, {}, {})
    for arm in verifier.ARMS:
        application = tmp_path / arm / "application"
        (application / "services").mkdir(parents=True)
        (application / "services/__init__.py").write_text(f"# Synthetic {arm}; never imported.\n", encoding="utf-8")
        receipts.application_roots[arm] = application
        receipts.work_dirs[arm] = tmp_path / arm / "work"
        receipts.reports[arm] = tmp_path / arm / "report.json"
        records = []
        for case in frozen["cases"]:
            case_id = case["id"]
            valid = case_id == "F01_valid_plan"
            state = "done" if valid else "error"
            answer = f"Conditions demandées non établies. {SOURCE_QUOTE} [S001]" if valid else ""
            query_id, document_id, version_id = (f"synthetic-{arm}-{case_id}-{field}" for field in ("query", "document", "version"))
            citations = [{"source_id": "S001", "document_id": document_id, "version_id": version_id, "text": SOURCE_QUOTE}] if valid else []
            terminal = {"text": answer, "citations": citations} if valid else {"code": "structured_answer_invalid", "message": "Plan invalide."}
            deltas = [answer] if valid else []
            database = receipts.work_dirs[arm] / case_id / "data/app.sqlite3"
            database.parent.mkdir(parents=True)
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE query_runs (id TEXT PRIMARY KEY, state TEXT, answer TEXT, question TEXT)")
                connection.execute("CREATE TABLE messages (query_id TEXT, role TEXT, content TEXT)")
                connection.execute("INSERT INTO query_runs VALUES (?, ?, ?, ?)", (query_id, state, answer, case["question"]))
                if valid:
                    connection.execute("INSERT INTO messages VALUES (?, 'assistant', ?)", (query_id, answer))
            records.append({
                "case_id": case_id, "question": case["question"], "state": state, "answer": answer,
                "selector_calls": 1, "query_called_model_metric_is_double": True,
                "captured_selector_calls": [{
                    "double": "ControlledSelectorDouble",
                    "messages": [{"role": "user", "content": "Synthetic capture: " + json.dumps({"reference_catalogue": [
                        {"id": "R001", "document_id": document_id, "text": SOURCE_QUOTE},
                    ]})}],
                    "response_format": {"properties": {"references": {"items": {"enum": ["R001"]}}}},
                }],
                "metrics": {"response_route": "local_4b_generation", "model_call_attempted": True,
                            "answer_support_validation": {"status": "passed", "unsupported_characters": 0}},
                "query_record": {"query_id": query_id, "state": state, "answer": answer},
                "judgment": {"passed": True, "limitation_notice": valid},
                "events": ([{"type": "delta", "data": {"text": answer}}] if valid else []) + [{"type": state, "data": terminal}],
                "terminal_count": 1, "error_code": None if valid else "structured_answer_invalid",
                "public_deltas": deltas, "citations": citations,
                "citation_checks": [{"source_id": "S001", "valid": True}] if valid else [],
                "documents": {"a": {"document_id": document_id, "version_id": version_id, "sha256": "a" * 64}},
            })
        protocol = {
            "fixtures_sha256": verifier.FIXTURE_SHA256,
            "harness_sha256": frozen["formatter_boundary_protocol"]["harness_sha256"],
            "profile_sha256": "b" * 64, "application_root": str(application),
            "source_files": verifier.application_manifest(application),
            "libraries": {"synthetic_reader_fixture": "1"}, "platform": "synthetic", "python": "synthetic",
            "tokenizer_directory": None, "doubles": ["ControlledSelectorDouble"],
            "test_kind": "synthetic_receipt_reader_only", "model_inference": "NOT_RUN",
            "case_order": list(verifier.CASE_IDS),
        }
        write_json(receipts.reports[arm], {"protocol": protocol, "cases": records,
                                         "source_stability": {"changed_during_run": []},
                                         "acceptance": frozen["acceptance"]})
    return receipts


def failed_criteria(result: dict[str, Any]) -> set[str]:
    gates = result["comparison_gates"][:]
    for arm in result["arms"].values():
        gates.extend(arm["gates"])
        for case in arm["cases"]:
            gates.extend(case.get("gates", []))
            gates.extend(case.get("persistence", {}).get("gates", []))
    return {gate["criterion"] for gate in gates if not gate["passed"]}


def test_synthetic_receipts_exercise_reader_without_claiming_a_campaign(synthetic_receipts: SyntheticReceipts) -> None:
    result = synthetic_receipts.verify()
    assert result["passed"] is True
    assert result["case_pass_count"] == result["required_case_count"] == 6
    assert result["model_inference"] == "NOT_RUN"
    assert result["primary_results_unchanged"] is True


@pytest.mark.parametrize("target", ["reports", "work_dirs", "application_roots"])
@pytest.mark.parametrize("alias", [False, True], ids=["same-path", "symlink-alias"])
def test_one_arm_cannot_count_as_two(
    synthetic_receipts: SyntheticReceipts, tmp_path: Path, target: str, alias: bool,
) -> None:
    paths = getattr(synthetic_receipts, target)
    if alias:
        link = tmp_path / ("alias-" + target)
        link.symlink_to(paths["baseline"], target_is_directory=target != "reports")
        paths["candidate"] = link
    else:
        paths["candidate"] = paths["baseline"]
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "distinct_" + target in failed_criteria(result)
    assert result["required_case_count"] == 6


def test_source_manifest_must_match_real_expected_tree(synthetic_receipts: SyntheticReceipts) -> None:
    source = synthetic_receipts.application_roots["candidate"] / "services/__init__.py"
    source.write_text("# Changed after the synthetic report.\n", encoding="utf-8")
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "source_manifest_matches_expected_application" in failed_criteria(result)


def test_terminal_error_cannot_be_hidden_by_summary(synthetic_receipts: SyntheticReceipts) -> None:
    synthetic_receipts.mutate_record("F02_plan_prose", lambda record: record["events"][-1]["data"].update(code="transport_error"))
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "expected_terminal_error" in failed_criteria(result)


def test_public_delta_cannot_be_hidden_by_summary(synthetic_receipts: SyntheticReceipts) -> None:
    synthetic_receipts.mutate_record("F02_plan_prose", lambda record: record["events"].insert(0, {"type": "delta", "data": {"text": "Uncaught fabricated prose."}}))
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "actual_public_deltas_match_record" in failed_criteria(result)


@pytest.mark.parametrize("field", ["text", "answer"])
def test_error_terminal_must_not_publish_an_answer(synthetic_receipts: SyntheticReceipts, field: str) -> None:
    synthetic_receipts.mutate_record("F03_unknown_reference", lambda record: record["events"][-1]["data"].update({field: "Uncaught fabricated prose."}))
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "no_answer_in_error_terminal" in failed_criteria(result)


def test_sqlite_question_must_match_frozen_case(synthetic_receipts: SyntheticReceipts) -> None:
    path = synthetic_receipts.work_dirs["candidate"] / "F02_plan_prose/data/app.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE query_runs SET question='An unrelated question'")
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "persisted_question_matches_case" in failed_criteria(result)


def test_rejected_answer_must_not_persist_an_assistant_message(synthetic_receipts: SyntheticReceipts) -> None:
    path = synthetic_receipts.work_dirs["candidate"] / "F02_plan_prose/data/app.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO messages SELECT id, 'assistant', 'Invented answer.' FROM query_runs")
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert "persisted_assistant_count" in failed_criteria(result)


def test_missing_record_stays_in_denominator(synthetic_receipts: SyntheticReceipts) -> None:
    report = json.loads(synthetic_receipts.reports["candidate"].read_text(encoding="utf-8"))
    report["cases"].pop()
    write_json(synthetic_receipts.reports["candidate"], report)
    result = synthetic_receipts.verify()
    assert result["passed"] is False
    assert result["case_pass_count"] == 5
    assert result["required_case_count"] == 6
    assert "exact_case_inventory_and_order" in failed_criteria(result)
