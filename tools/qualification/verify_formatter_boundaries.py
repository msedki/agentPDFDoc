#!/usr/bin/env python3
"""Vérifier les six parcours contrôlés I5, sans requête ni écriture dans leurs bases.

Le complément ne modifie ni le score des trente cas primaires, ni leurs oracles.
Le sélecteur est un double explicite : aucune inférence du modèle 4B n'est prouvée.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIXTURE_SHA256 = "e721fef074f76fd70f86bc71b7808a984c0c8f0bc241b5dc22e376e98de236e5"
PROTOCOL_ID = "G4B-I5-FORMATTER-BOUNDARIES-V1"
CASE_IDS = ("F01_valid_plan", "F02_plan_prose", "F03_unknown_reference")
ARMS = ("baseline", "candidate")
COMPARABLE_FIELDS = (
    "fixtures_sha256", "harness_sha256", "profile_sha256", "libraries", "platform", "python",
    "tokenizer_directory", "doubles", "test_kind", "model_inference", "case_order",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_object(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("receipt_size_limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("receipt_not_object")
    return value


def gate(gates: list[dict[str, Any]], name: str, passed: Any) -> None:
    gates.append({"criterion": name, "passed": bool(passed)})


def captured_catalogue(call: dict[str, Any]) -> list[Any]:
    messages = sequence(call.get("messages"))
    users = [message for message in messages if mapping(message).get("role") == "user"]
    if not users:
        return []
    content = mapping(users[-1]).get("content")
    if not isinstance(content, str) or "{" not in content:
        return []
    try:
        payload = json.loads(content[content.index("{"):])
    except (TypeError, ValueError):
        return []
    return sequence(mapping(payload).get("reference_catalogue"))


def check_persistence(
    work_dir: Path, case_id: str, record: dict[str, Any], expectation: dict[str, Any],
) -> dict[str, Any]:
    """Lire la base imposée par le harnais, jamais un chemin fourni par le rapport."""
    result: dict[str, Any] = {"mode": "read_only", "gates": []}
    gates = result["gates"]
    try:
        root = work_dir.resolve(strict=True)
        database = root / case_id / "data" / "app.sqlite3"
        if not database.resolve(strict=True).is_relative_to(root):
            raise ValueError("database_outside_work_dir")
        if any(path.is_symlink() for path in (database, database.parent, database.parent.parent)):
            raise ValueError("database_link")
        query = mapping(record.get("query_record"))
        query_id = query.get("query_id")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("missing_query_id")
        result["database_sha256_before"] = digest(database)
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT state, answer, question FROM query_runs WHERE id=? LIMIT 2", (query_id,),
            ).fetchall()
            messages = connection.execute(
                "SELECT content FROM messages WHERE query_id=? AND role='assistant' LIMIT 2", (query_id,),
            ).fetchall()
        gate(gates, "persisted_query_unique", len(rows) == 1)
        gate(gates, "persisted_state", len(rows) == 1 and rows[0][0] == expectation["expected_state"])
        gate(gates, "persisted_answer_matches_record", len(rows) == 1 and rows[0][1] == record.get("answer"))
        gate(gates, "persisted_question_matches_case", len(rows) == 1 and rows[0][2] == record.get("question"))
        gate(gates, "persisted_assistant_count", len(messages) == expectation["required_persisted_assistant_messages"])
        if expectation["kind"] == "valid_witness":
            gate(gates, "persisted_assistant_matches_answer", len(messages) == 1 and messages[0][0] == record.get("answer"))
        else:
            gate(gates, "persisted_answer_empty", len(rows) == 1 and rows[0][1] == "")
        result["persisted_assistant_count"] = len(messages)
        result["database_sha256_after"] = digest(database)
        gate(gates, "database_bytes_unchanged", result["database_sha256_before"] == result["database_sha256_after"])
    except (OSError, ValueError, sqlite3.Error) as error:
        result["error_type"] = type(error).__name__
        gate(gates, "persistence_read_succeeded", False)
    result["passed"] = all(item["passed"] for item in gates)
    return result


def check_case(case: dict[str, Any], record: dict[str, Any], work_dir: Path) -> dict[str, Any]:
    expectation = case["formatter_expectation"]
    gates: list[dict[str, Any]] = []
    calls = sequence(record.get("captured_selector_calls"))
    metrics = mapping(record.get("metrics"))
    query = mapping(record.get("query_record"))
    judgment = mapping(record.get("judgment"))
    events = sequence(record.get("events"))
    terminals = [mapping(event) for event in events if mapping(event).get("type") in {"done", "error", "cancelled"}]
    terminal = mapping(terminals[0].get("data")) if len(terminals) == 1 else {}
    citations = sequence(record.get("citations"))
    document = mapping(mapping(record.get("documents")).get("a"))
    deltas = sequence(record.get("public_deltas"))
    answer = record.get("answer")
    call = mapping(calls[0]) if len(calls) == 1 else {}
    catalogue = captured_catalogue(call)
    ids = [mapping(entry).get("id") for entry in catalogue]
    properties = mapping(mapping(call.get("response_format")).get("properties"))
    reference_enum = mapping(mapping(properties.get("references")).get("items")).get("enum")

    gate(gates, "question_unchanged", record.get("question") == case["question"])
    gate(gates, "frozen_primary_grader_passed", judgment.get("passed") is True)
    gate(gates, "selector_called_exactly_once", record.get("selector_calls") == expectation["required_selector_calls"])
    gate(gates, "captured_call_exactly_once", len(calls) == expectation["required_captured_calls"])
    gate(gates, "selector_double_explicit", call.get("double") == "ControlledSelectorDouble" and record.get("query_called_model_metric_is_double") is True)
    gate(gates, "model_route_exercised", metrics.get("response_route") == expectation["required_route"])
    gate(gates, "model_call_attempted", metrics.get("model_call_attempted") is expectation["required_model_call_attempted"])
    gate(gates, "actual_prompt_catalogue_nonempty", len(catalogue) >= expectation["required_catalogue_min_entries"])
    gate(gates, "catalogue_ids_unique_nonempty", bool(ids) and all(isinstance(value, str) and value for value in ids) and len(set(map(str, ids))) == len(ids))
    gate(gates, "schema_enum_matches_actual_catalogue", reference_enum == ids and bool(ids))
    gate(gates, "catalogue_preserves_source_and_document", bool(document.get("document_id")) and any(
        mapping(entry).get("text") == expectation["source_quote"]
        and mapping(entry).get("document_id") == document.get("document_id") for entry in catalogue
    ))
    gate(gates, "one_terminal_receipt", record.get("terminal_count") == expectation["required_terminal_count"])
    gate(gates, "one_actual_terminal", len(terminals) == expectation["required_terminal_count"])
    gate(gates, "expected_terminal_type", len(terminals) == 1 and terminals[0].get("type") == expectation["expected_state"])
    gate(gates, "expected_state", record.get("state") == query.get("state") == expectation["expected_state"])
    gate(gates, "expected_error", record.get("error_code") == expectation["expected_error_code"])
    gate(gates, "expected_terminal_error", terminal.get("code") == expectation["expected_error_code"])
    gate(gates, "answer_matches_query", isinstance(answer, str) and answer == query.get("answer"))
    actual_deltas = [mapping(mapping(event).get("data")).get("text") for event in events if mapping(event).get("type") == "delta"]
    gate(gates, "actual_public_deltas_match_record", actual_deltas == record.get("public_deltas"))
    gate(gates, "terminal_citation_count", len(citations) == expectation["required_terminal_citations"])
    gate(gates, "terminal_citations_match_record", sequence(terminal.get("citations")) == citations)
    public = json.dumps({"answer": answer, "deltas": deltas, "query": query, "terminal": terminal}, ensure_ascii=False)
    gate(gates, "no_untrusted_public_literal", all(value not in public for value in expectation["forbidden_public_literals"]))
    if expectation["kind"] == "valid_witness":
        checks = sequence(record.get("citation_checks"))
        support = mapping(metrics.get("answer_support_validation"))
        gate(gates, "source_condition_preserved", isinstance(answer, str) and expectation["source_quote"] in answer)
        gate(gates, "limitation_notice_present", judgment.get("limitation_notice") is True)
        gate(gates, "public_deltas_match_final_answer", bool(deltas) and all(isinstance(value, str) for value in deltas) and "".join(map(str, deltas)) == answer)
        gate(gates, "all_citations_valid", len(checks) == len(citations) and all(mapping(check).get("valid") is True for check in checks))
        gate(gates, "citation_identity_and_source", bool(citations) and all(
            mapping(citation).get("document_id") == document.get("document_id")
            and mapping(citation).get("version_id") == document.get("version_id")
            and mapping(citation).get("text") == expectation["source_quote"] for citation in citations
        ))
        gate(gates, "source_reconstruction_passed", support.get("status") == "passed" and support.get("unsupported_characters") == 0)
    else:
        gate(gates, "no_public_delta", record.get("public_deltas") == [])
        gate(gates, "no_final_answer", answer == "" and query.get("answer") == "")
        gate(gates, "no_final_citation", record.get("citations") == [])
        gate(gates, "no_answer_in_error_terminal", terminal.get("text") in (None, "") and terminal.get("answer") in (None, ""))
    persistence = check_persistence(work_dir, case["id"], record, expectation)
    gate(gates, "read_only_persistence_checks", persistence["passed"])
    return {
        "case_id": case["id"], "passed": all(item["passed"] for item in gates),
        "gates": gates, "persistence": persistence,
        "observed": {"state": record.get("state"), "selector_calls": record.get("selector_calls"),
                     "captured_calls": len(calls), "catalogue_entries": len(catalogue),
                     "public_delta_count": len(deltas), "citations": len(citations),
                     "document_sha256": document.get("sha256")},
    }


def application_manifest(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): digest(path) for path in sorted((root / "services").rglob("*.py"))}


def verify(
    fixtures: Path, reports: dict[str, Path], work_dirs: dict[str, Path], application_roots: dict[str, Path],
) -> dict[str, Any]:
    fixture = load_object(fixtures)
    fixture_hash = digest(fixtures)
    if fixture_hash != FIXTURE_SHA256 or fixture.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("frozen_fixture_changed")
    cases = fixture["cases"]
    if tuple(case["id"] for case in cases) != CASE_IDS:
        raise ValueError("frozen_case_inventory_changed")
    result: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID, "verified_utc": datetime.now(UTC).isoformat(),
        "verifier_sha256": digest(Path(__file__)), "fixtures_sha256": fixture_hash,
        "primary_results_unchanged": True, "model_inference": "NOT_RUN",
        "scope": "ControlledSelectorDouble with real Office ingestion, SQLite and QueryService",
        "required_case_count": 6, "arms": {}, "comparison_gates": [],
    }
    loaded: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_result: dict[str, Any] = {"gates": [], "cases": []}
        result["arms"][arm] = arm_result
        gates = arm_result["gates"]
        try:
            arm_result["report_sha256"] = digest(reports[arm])
            report = load_object(reports[arm])
            loaded[arm] = report
            protocol = mapping(report.get("protocol"))
            gate(gates, "frozen_fixture_used", protocol.get("fixtures_sha256") == fixture_hash)
            gate(gates, "frozen_harness_used", protocol.get("harness_sha256") == fixture["formatter_boundary_protocol"]["harness_sha256"])
            gate(gates, "no_native_inference_claimed", protocol.get("model_inference") == "NOT_RUN")
            gate(gates, "sources_stable_during_run", mapping(report.get("source_stability")).get("changed_during_run") == [])
            gate(gates, "protocol_has_comparable_fields", all(key in protocol for key in COMPARABLE_FIELDS))
            gate(gates, "profile_hash_present", re.fullmatch(r"[0-9a-f]{64}", str(protocol.get("profile_sha256", ""))) is not None)
            recorded_root = protocol.get("application_root")
            expected_root = application_roots[arm].resolve(strict=True)
            gate(gates, "expected_application_root", isinstance(recorded_root, str) and Path(recorded_root).resolve(strict=True) == expected_root)
            actual_sources = application_manifest(expected_root)
            gate(gates, "source_manifest_matches_expected_application", bool(actual_sources) and protocol.get("source_files") == actual_sources)
            records = sequence(report.get("cases"))
            ids = [mapping(record).get("case_id") for record in records]
            gate(gates, "exact_case_inventory_and_order", ids == list(CASE_IDS) and protocol.get("case_order") == list(CASE_IDS))
            gate(gates, "frozen_acceptance_unchanged", report.get("acceptance") == fixture["acceptance"])
            for case in cases:
                matches = [mapping(record) for record in records if mapping(record).get("case_id") == case["id"]]
                arm_result["cases"].append(check_case(case, matches[0] if len(matches) == 1 else {}, work_dirs[arm]))
            gate(gates, "report_bytes_unchanged", digest(reports[arm]) == arm_result["report_sha256"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            arm_result["error_type"] = type(error).__name__
            gate(gates, "report_read_and_validation_succeeded", False)
        by_id = {item["case_id"]: item for item in arm_result["cases"]}
        arm_result["cases"] = [by_id.get(case_id, {"case_id": case_id, "passed": False, "reason": "missing_or_unreadable_record"}) for case_id in CASE_IDS]
        arm_result["passed"] = all(item["passed"] for item in gates) and all(item["passed"] for item in arm_result["cases"])

    comparison = result["comparison_gates"]
    for label, paths in (("reports", reports), ("work_dirs", work_dirs), ("application_roots", application_roots)):
        gate(comparison, "distinct_" + label, paths["baseline"].resolve() != paths["candidate"].resolve())
    source_manifests = [mapping(mapping(loaded.get(arm, {}).get("protocol")).get("source_files")) for arm in ARMS]
    gate(comparison, "distinct_nonempty_source_manifests", all(source_manifests) and source_manifests[0] != source_manifests[1])
    for key in COMPARABLE_FIELDS:
        baseline = mapping(loaded.get("baseline", {}).get("protocol"))
        candidate = mapping(loaded.get("candidate", {}).get("protocol"))
        gate(comparison, "same_" + key, key in baseline and key in candidate and baseline[key] == candidate[key])
    document_hashes = [mapping(item.get("observed")).get("document_sha256") for arm in ARMS for item in result["arms"][arm]["cases"]]
    gate(comparison, "six_documents_byte_identical", len(document_hashes) == 6 and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in document_hashes) and len(set(map(str, document_hashes))) == 1)
    gate(comparison, "fixture_bytes_unchanged", digest(fixtures) == fixture_hash)
    result["case_pass_count"] = sum(item["passed"] for arm in ARMS for item in result["arms"][arm]["cases"])
    result["passed"] = all(result["arms"][arm]["passed"] for arm in ARMS) and all(item["passed"] for item in comparison)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, required=True)
    for arm in ARMS:
        parser.add_argument(f"--{arm}-report", type=Path, required=True)
        parser.add_argument(f"--{arm}-work-dir", type=Path, required=True)
        parser.add_argument(f"--{arm}-application-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Le rapport de vérification doit être nouveau")
    try:
        result = verify(
            args.fixtures,
            {arm: getattr(args, arm + "_report") for arm in ARMS},
            {arm: getattr(args, arm + "_work_dir") for arm in ARMS},
            {arm: getattr(args, arm + "_application_root") for arm in ARMS},
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"protocol_id": PROTOCOL_ID, "passed": False, "required_case_count": 6,
                  "case_pass_count": 0, "error_type": type(error).__name__, "primary_results_unchanged": True}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("passed", "case_pass_count", "required_case_count")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
