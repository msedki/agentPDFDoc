"""Outil de fautes injectées (D03.5, D03.6).

Arrêt forcé : processus réels créés par le test ; seul l'arbre visé est arrêté, un processus étranger reste vivant.
Rapport d'un cas interrompu : doubles explicites de l'instance isolée, sans service ni processus.
"""

import json
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
sys.path.insert(0, str(ROOT))
import fault_check  # noqa: E402

import services.runtime.supervisor as supervisor  # noqa: E402

# Parent type superviseur : un enfant qui consignerait un arrêt propre (SIGTERM) ; le parent publie le PID de l'enfant.
TREE = textwrap.dedent("""
    import signal, subprocess, sys, time
    from pathlib import Path
    child = subprocess.Popen([sys.executable, "-c",
        "import signal, sys, time\\nfrom pathlib import Path\\n"
        "signal.signal(signal.SIGTERM, lambda *_: (Path(sys.argv[1]).write_text('propre'), sys.exit(0)))\\n"
        "time.sleep(120)", sys.argv[1] + ".arret"])
    Path(sys.argv[1]).write_text(str(child.pid))
    time.sleep(120)
""")


@pytest.mark.skipif(sys.platform == "win32", reason="branche Linux ; Windows garde taskkill /F /T")
def test_kill_tree_stops_the_whole_tree_without_a_clean_exit_and_spares_other_processes(tmp_path):
    marker = tmp_path / "enfant.pid"
    foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    root = subprocess.Popen([sys.executable, "-c", TREE, str(marker)], start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        child = psutil.Process(int(marker.read_text()))
        fault_check.kill_tree(root.pid)
        assert root.wait(10) == -9
        child.wait(10)
        assert not child.is_running()
        # Aucun arrêt propre : l'enfant n'a pas pu traiter de SIGTERM avant SIGKILL.
        assert not (tmp_path / "enfant.pid.arret").exists()
        assert foreign.poll() is None
    finally:
        for process in (root, foreign):
            if process.poll() is None:
                process.kill()
                process.wait(10)


# Refus de redémarrage observé sous Linux le 02/10/2026 (J8, L4) : le port d'un service tué restait en TIME-WAIT.
REFUSED = "Port 33895 occupé ; aucun service existant ne sera arrêté."


class InterruptedInstance:
    """Double de l'instance isolée : arrêts forcés consignés, redémarrage refusé comme sous Linux."""

    def __init__(self, state, database=None):
        self.state, self.profile_path, self.killed, self.connection = state, Path(state["profile"]), [], database

    def runtime(self):
        return {"supervisor": {"pid": 101}, "services": {"qdrant": {"pid": 102}, "api": {"pid": 103}}}

    def kill_tree(self, pid):
        self.killed.append(pid)

    def job(self, job_id):
        return None  # instance arrêtée : API muette

    def database(self):
        return self.connection

    def restart(self):
        raise RuntimeError(REFUSED)


def run_case(tmp_path, monkeypatch, case, instance):
    state = tmp_path / "instance.json"
    state.write_text(json.dumps(instance.state), encoding="utf-8")
    fixture = tmp_path / "Fiche.pdf"
    fixture.write_bytes(b"%PDF-1.7 fixture de test")
    report = tmp_path / "faults.json"
    monkeypatch.setattr(fault_check, "Isolated", lambda _state: instance)
    monkeypatch.setattr(fault_check, "import_fixture", lambda *_args: {"job_id": "job-1", "document_id": "doc-1", "version_id": "ver-1"})
    monkeypatch.setattr(fault_check, "wait_stage", lambda _instance, _job, stages: {"state": "running", "stage": sorted(stages)[0]})
    monkeypatch.setattr(fault_check.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", ["fault_check.py", case, "--instance", str(state), "--fixture", str(fixture), "--report", str(report)])
    assert fault_check.main() == 1
    return json.loads(report.read_text(encoding="utf-8"))["cases"][case]


def test_interrupted_kill_case_keeps_its_observations_and_reports_the_error(tmp_path, monkeypatch):
    instance = InterruptedInstance({"profile": str(tmp_path / "profile.yaml"), "root": str(tmp_path)})
    monkeypatch.setattr(fault_check.psutil, "pid_exists", lambda pid: pid == 102)
    result = run_case(tmp_path, monkeypatch, "kill-extracting", instance)
    # L'échec reste visible : erreur, contrôle « completed » faux, verdict FAIL.
    assert result["error"] == f"RuntimeError: {REFUSED}" and result["result"] == "FAIL"
    # Les observations faites avant le refus restent dans le rapport, avec le contrôle déjà évalué.
    assert result["killed_at"] == {"state": "running", "stage": "extracting"}
    assert result["survivors_after_supervisor_kill"] == [102] and instance.killed == [101, 102]
    assert result["checks"] == {"killed_in_target_stage": True, "completed": False}
    assert result["fixture"] == "Fiche.pdf" and "after_restart" not in result


def test_interrupted_qdrant_case_keeps_the_state_seen_after_the_loss(tmp_path, monkeypatch):
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.execute("CREATE TABLE jobs(id TEXT, state TEXT, stage TEXT, error_code TEXT)")
    database.execute("CREATE TABLE documents(id TEXT, state TEXT, active_generation_id TEXT)")
    database.execute("INSERT INTO jobs VALUES('job-1', 'error', 'indexing', 'vector_store_unavailable')")
    database.execute("INSERT INTO documents VALUES('doc-1', 'processing', NULL)")
    instance = InterruptedInstance({"profile": str(tmp_path / "profile.yaml"), "root": str(tmp_path)}, database)
    monkeypatch.setattr(supervisor, "status", lambda _profile: {"status": "stopped"})
    result = run_case(tmp_path, monkeypatch, "qdrant-down", instance)
    assert result["error"] == f"RuntimeError: {REFUSED}" and result["result"] == "FAIL"
    assert result["killed_at"] == {"state": "running", "stage": "indexing"} and instance.killed == [102]
    assert result["job_after_qdrant_loss"] == {"state": "error", "stage": "indexing", "error_code": "vector_store_unavailable"}
    assert result["document_after_qdrant_loss"] == {"state": "processing", "active_generation_id": None}
    assert result["instance_after_qdrant_loss"] == "stopped"
    assert result["checks"] == {"never_shown_ready": True, "completed": False}


def test_qdrant_case_keeps_the_kill_when_the_state_after_the_loss_cannot_be_read(tmp_path, monkeypatch):
    # Base sans les tables attendues : la lecture qui suit l'arrêt de Qdrant échoue, l'arrêt doit rester consigné.
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    instance = InterruptedInstance({"profile": str(tmp_path / "profile.yaml"), "root": str(tmp_path)}, database)
    result = run_case(tmp_path, monkeypatch, "qdrant-down", instance)
    assert result["error"] == "OperationalError: no such table: jobs" and result["result"] == "FAIL"
    assert result["killed_at"] == {"state": "running", "stage": "indexing"} and instance.killed == [102]
    assert "job_after_qdrant_loss" not in result and result["checks"] == {"completed": False}
