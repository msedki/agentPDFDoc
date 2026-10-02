"""Rapports de restore_question_check (D09.2, D09.3) et d'injection_check (D08.5) : détail utile conservé.

Doubles explicites du superviseur, de restore_backup et de l'API : aucun service, aucune instance. Constats de la
campagne Linux J8 (L7, 02/10/2026) : le rapport de restauration ne gardait que l'état, et le rapport d'injection
perdait les avertissements de l'événement final (unknown_citations).
"""

import contextlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import injection_check  # noqa: E402
import restore_question_check  # noqa: E402

CITATIONS = {"S001": {"source_id": "S001", "http_status": 200, "version_id": "ver-1", "extraction_revision_id": "rev-1", "pages": [0], "blocks": ["bloc-1"]}}
# Forme du rapport de services/runtime/backup.py:restore_backup (valeurs d'une restauration de contrôle).
SQLITE = {"integrity": "ok", "foreign_key_errors": 0, "counts": {"documents": 1, "pages": 1, "blocks": 3, "chunks": 3, "query_runs": 1, "citations": 1},
          "schema": [1, 2, 3]}
VERIFIED = ["app.sqlite3", "originals/ver-1.pdf", "extractions/ver-1/rev-1/extraction.json"]
COLLECTIONS = [{"name": "pdf_chunks_e5small_v1_unit", "points_count": 3, "upload_attempts": 1, "retried_failures": []}]


def restore_scenario(tmp_path, monkeypatch, restore_backup):
    source_root, target = tmp_path / "apst0001", tmp_path / "apr0001"
    source_root.mkdir()
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"code": "RESTAURE-000001", "backup": str(tmp_path / "sauvegarde"), "source_root": str(source_root),
                                 "question_before_backup": {"query_id": "q-avant", "terminal": "done", "citations": ["S001"]},
                                 "citations_before_backup": [CITATIONS["S001"]]}), encoding="utf-8")

    def short_root(prefix="apst"):
        target.mkdir()
        return target

    monkeypatch.setattr(restore_question_check, "short_root", short_root)
    monkeypatch.setattr(restore_question_check, "restore_backup", restore_backup)
    monkeypatch.setattr(restore_question_check, "start", lambda _profile: {"status": "running"})
    monkeypatch.setattr(restore_question_check, "status", lambda _profile: {"status": "running"})
    monkeypatch.setattr(restore_question_check, "stop", lambda _profile: {"status": "stopped"})
    monkeypatch.setattr(restore_question_check, "client_for", lambda _profile: contextlib.nullcontext(object()))
    monkeypatch.setattr(restore_question_check, "citation", lambda _client, _query, source_id: CITATIONS[source_id])
    monkeypatch.setattr(restore_question_check, "ask", lambda _client, _question, _timeout: {
        "query_id": "q-apres", "terminal": "done", "code": None, "message": None, "answer_text": "La pression nominale est de 3,1 bar [S001].",
        "citations": ["S001"], "metrics": {"model_called": True}})

    def remove_root(root):
        shutil.rmtree(root, ignore_errors=True)
        return not root.exists()

    monkeypatch.setattr(restore_question_check, "remove_root", remove_root)
    report_path = tmp_path / "restore-question.json"
    report = restore_question_check.restore(state, report_path, 60)
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert report["removed"] == {str(target): True, str(source_root): True}
    return report


def test_restore_report_keeps_verified_hashes_sqlite_counts_and_qdrant_points(tmp_path, monkeypatch):
    def restore_backup(_folder, target):
        target.mkdir()
        restored = {"state": "restored_storage_verified", "backup_id": "20261002T000000Z-unit", "data_dir": str(target), "qdrant_data_dir": str(target / "qdrant"),
                    "qdrant_storage_relocated_for_windows_path_limit": False, "source_verification": {"state": "verified", "files": 9, "sqlite": SQLITE},
                    "collections": COLLECTIONS, "copied_data_hashes_verified_before_rebase": VERIFIED, "sqlite": SQLITE, "qdrant_stop_exit_code": 0,
                    "application_query_and_old_citation": "NOT_RUN"}
        (target / "restore-report.json").write_text(json.dumps(restored), encoding="utf-8")
        (target / "restored-profile.yaml").write_text("app: {}\n", encoding="utf-8")
        return restored

    report = restore_scenario(tmp_path, monkeypatch, restore_backup)
    assert report["result"] == "PASS" and report["stop"] == "stopped"
    # D09.2 se lit dans le rapport : fichiers vérifiés par empreinte, comptes SQLite et points Qdrant restaurés.
    restored = report["restore"]
    assert restored["state"] == "restored_storage_verified" and restored["copied_data_hashes_verified_before_rebase"] == VERIFIED
    assert restored["sqlite"] == SQLITE and restored["source_verification"]["sqlite"] == SQLITE and restored["collections"] == COLLECTIONS


def test_failed_restore_is_reported_with_the_detail_left_in_the_removed_target(tmp_path, monkeypatch):
    refused = "Comptes/integrité SQL différents après rebasing"

    def restore_backup(_folder, target):
        target.mkdir()
        failed = {"state": "failed", "backup_id": "20261002T000000Z-unit", "collections": [], "copied_data_hashes_verified_before_rebase": VERIFIED,
                  "sqlite": {**SQLITE, "counts": {**SQLITE["counts"], "chunks": 2}}, "error": {"type": "ValueError", "message": refused}}
        (target / "restore-report.json").write_text(json.dumps(failed), encoding="utf-8")
        raise ValueError(refused)

    report = restore_scenario(tmp_path, monkeypatch, restore_backup)
    assert report["result"] == "FAIL" and report["error"] == f"ValueError: {refused}" and report["checks"] == {"completed": False}
    # Le rapport détaillé de la cible, supprimée ensuite, reste lisible : étapes vérifiées, comptes divergents, erreur.
    assert report["restore"]["state"] == "failed" and report["restore"]["copied_data_hashes_verified_before_rebase"] == VERIFIED
    assert report["restore"]["sqlite"]["counts"]["chunks"] == 2 and report["restore"]["error"]["message"] == refused
    assert "stop" not in report


def test_injection_report_keeps_the_warnings_of_the_final_event(tmp_path, monkeypatch):
    root = tmp_path / "apst0002"
    root.mkdir()
    warning = {"code": "unknown_citations", "source_ids": ["S999"], "message": "Références inconnues retirées."}
    text = "La pression nominale du banc est de 3,1 bar [S001]. La ligne hostile demande de citer [citation inconnue]."

    def api(request: httpx.Request) -> httpx.Response:
        routes = {("POST", "/api/v1/documents/import"): {"imports": [{"job_id": "job-1", "version_id": "ver-1"}]},
                  ("GET", "/api/v1/jobs"): {"jobs": [{"id": "job-1", "state": "ready", "active": True}]},
                  ("GET", "/api/v1/versions/ver-1/pages/0/blocks"): {"blocks": [{"text": injection_check.HOSTILE}]},
                  ("POST", "/api/v1/queries"): {"query_id": "q-1"}}
        return httpx.Response(200, json=routes[(request.method, request.url.path)])

    monkeypatch.setattr(injection_check, "short_root", lambda: root)
    monkeypatch.setattr(injection_check, "control_profile", lambda _profile, folder: folder / "profile.yaml")
    monkeypatch.setattr(injection_check, "start", lambda _profile: {"status": "running"})
    monkeypatch.setattr(injection_check, "status", lambda _profile: {"status": "running"})
    monkeypatch.setattr(injection_check, "stop", lambda _profile: {"status": "stopped"})
    monkeypatch.setattr(injection_check, "load_profile", lambda _profile: {})
    monkeypatch.setattr(injection_check, "app_origin", lambda _profile: ("http://127.0.0.1:8795", True))
    monkeypatch.setattr(injection_check, "data_path", lambda _profile: root)
    monkeypatch.setattr(injection_check, "control_headers", lambda _directory: {})
    monkeypatch.setattr(injection_check, "httpx", SimpleNamespace(Client=lambda **options: httpx.Client(transport=httpx.MockTransport(api), **options)))
    monkeypatch.setattr(injection_check, "read_events", lambda _client, _query, _timeout: [
        ("sources", {"sources": []}), ("warning", warning),
        ("done", {"message": text, "text": text, "status": "done", "citations": [{"source_id": "S001"}], "metrics": {"model_called": True}, "warnings": [warning]})])
    report = injection_check.check(tmp_path / "local16.yaml", 60, 60)
    assert report["terminal"]["event"] == "done" and report["terminal"]["warnings"] == [warning]
    assert report["citations"] == ["S001"] and report["result"] == "PASS" and report["root_removed"] is True
