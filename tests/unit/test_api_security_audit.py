"""Journal d'audit de sécurité borné (constat C7) : même politique que la trace de ressources du superviseur, 5 Mio × 2."""
import json

import pytest

from services.api.security import AuditLog, SecurityPolicy, SessionRegistry
from services.api.settings import Settings

MIB = 1024 * 1024


def records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_security_audit_journal_stays_bounded_under_a_flood_of_refusals(tmp_path):
    """Plus de 5 Mio de refus journalisés : le fichier courant reste sous 5 Mio, deux archives au plus, aucune ligne coupée."""
    path = tmp_path / "logs" / "security-audit.jsonl"
    registry = SessionRegistry(SecurityPolicy.from_settings(Settings(tmp_path, {})), path)
    padding = "/api/v1/library/tree?" + "x" * 1000
    for index in range(6500):
        registry.audit("request_refused", reason="session_required", method="GET", path=padding, sequence=index)
    registry.close()
    archives = sorted(path.parent.glob("security-audit.jsonl.*"))
    assert path.stat().st_size <= 5 * MIB
    assert [archive.name for archive in archives] == ["security-audit.jsonl.1"]
    kept = records(path.parent / "security-audit.jsonl.1") + records(path)
    sequences = [record["sequence"] for record in kept]
    assert sequences == list(range(sequences[0], 6500)), "les lignes conservées doivent être contiguës, dans l'ordre et entières"


def test_audit_log_rotation_keeps_two_archives_and_whole_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path, max_bytes=400, archives=2)
    for index in range(40):
        log.write({"event": "request_refused", "sequence": index, "path": "/api/v1/jobs"})
    assert log.flush()
    names = sorted(item.name for item in tmp_path.iterdir())
    assert names == ["audit.jsonl", "audit.jsonl.1", "audit.jsonl.2"]
    for name in names:
        assert (tmp_path / name).stat().st_size <= 400
        assert all(line.endswith("}") for line in (tmp_path / name).read_text(encoding="utf-8").splitlines())
    kept = records(tmp_path / "audit.jsonl.2") + records(tmp_path / "audit.jsonl.1") + records(path)
    assert [record["sequence"] for record in kept] == list(range(kept[0]["sequence"], 40))
    assert log.close() and log.failures == 0
    # Un enregistrement après la fermeture relance l'écriture, sans perte.
    log.write({"event": "session_opened", "sequence": 40})
    assert log.close() and records(path)[-1]["sequence"] == 40


def test_audit_write_failure_is_logged_without_failing_the_caller(tmp_path, caplog):
    blocker = tmp_path / "occupé"
    blocker.write_text("fichier à la place du dossier", encoding="utf-8")
    log = AuditLog(blocker / "audit.jsonl")
    with caplog.at_level("ERROR", logger="rag.security"):
        log.write({"event": "request_refused"})
        assert log.close()
    assert log.failures == 1 and "Journal d'audit de sécurité : écriture impossible" in caplog.text


def lines(path):
    return [record["sequence"] for record in records(path)] if path.exists() else []


def test_audit_writer_survives_an_unexpected_exception(tmp_path, caplog):
    """Revue A1 : une exception autre qu'OSError ne termine plus le fil d'écriture ; les enregistrements suivants sont écrits."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    real_append, calls = log._append, []

    def append(line):
        calls.append(line)
        if len(calls) == 1:
            raise ValueError("contrôlée : défaut imprévu du premier enregistrement")
        real_append(line)

    log._append = append
    with caplog.at_level("ERROR", logger="rag.security"):
        for index in range(3):
            log.write({"event": "request_refused", "sequence": index})
        assert log.flush(timeout=2)
    assert lines(path) == [1, 2]
    assert log.failures == 1 and "Journal d'audit de sécurité : écriture impossible" in caplog.text
    assert log.close()


# La mort du fil est provoquée exprès : l'avertissement de pytest sur l'exception du fil est attendu.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_audit_writer_is_restarted_when_its_thread_died(tmp_path):
    """Revue A1 : si le fil d'écriture est mort (exception hors Exception), l'écriture suivante le relance au lieu d'empiler en vain."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    real_append = log._append

    def append(line):
        if b'"sequence": 0' in line:
            raise SystemExit("contrôlée : arrêt brutal du fil")
        real_append(line)

    log._append = append
    log.write({"event": "request_refused", "sequence": 0})
    dead = log._thread
    assert dead is not None
    dead.join(timeout=2)
    assert not dead.is_alive()
    log.write({"event": "request_refused", "sequence": 1})
    assert log.flush(timeout=2)
    assert lines(path) == [1] and log.state()["writer_restarts"] == 1
    assert log.close()


def test_audit_rotation_refused_by_a_persistent_permission_error_is_retried_without_losing_lines(tmp_path, monkeypatch):
    """Renommage refusé (Windows : fichier ouvert sans partage de suppression, analyse antivirus), simulé par PermissionError.

    Aucune ligne perdue ; la rotation est reportée de `retry_after_seconds`, puis retentée, et aboutit quand le refus cesse.
    """
    path = tmp_path / "audit.jsonl"
    now = [100.0]
    log = AuditLog(path, max_bytes=300, archives=2, busy_timeout_seconds=0, retry_after_seconds=30, clock=lambda: now[0])
    attempts, refusing = [], [True]
    real_replace = type(path).replace

    def replace(self, target):
        if self.parent == tmp_path:
            attempts.append((self.name, type(self)(target).name))
            if refusing[0]:
                raise PermissionError(13, "contrôlée : partage refusé", str(self))
        return real_replace(self, target)

    monkeypatch.setattr(type(path), "replace", replace)
    for index in range(12):
        log.write({"event": "request_refused", "sequence": index, "path": "/api/v1/jobs"})
    assert log.flush(timeout=2)
    # Une seule tentative pendant la fenêtre de report, aucune archive, toutes les lignes dans le fichier courant.
    assert attempts == [("audit.jsonl", "audit.jsonl.1")]
    assert sorted(item.name for item in tmp_path.iterdir()) == ["audit.jsonl"] and lines(path) == list(range(12))
    now[0] += 31
    log.write({"event": "request_refused", "sequence": 12, "path": "/api/v1/jobs"})
    assert log.flush(timeout=2)
    assert len(attempts) == 2 and lines(path) == list(range(13))
    refusing[0] = False
    now[0] += 31
    log.write({"event": "request_refused", "sequence": 13, "path": "/api/v1/jobs"})
    assert log.flush(timeout=2)
    assert len(attempts) == 3
    assert lines(tmp_path / "audit.jsonl.1") == list(range(13)) and lines(path) == [13]
    assert log.failures == 0 and log.state()["rotations_deferred"] == 2
    assert log.close()


def test_audit_queue_is_bounded_and_counts_dropped_records_without_blocking_the_caller(tmp_path):
    """Revue A1 : fil d'écriture bloqué (disque figé) : la file reste bornée, l'appelant ne bloque pas, les pertes sont comptées."""
    import threading
    import time

    path = tmp_path / "audit.jsonl"
    line_bytes = len((json.dumps({"event": "request_refused", "sequence": 1}) + "\n").encode("utf-8"))
    log = AuditLog(path, queue_limit_bytes=5 * line_bytes)
    real_append, entered, release = log._append, threading.Event(), threading.Event()

    def append(line):
        entered.set()
        release.wait(5)
        real_append(line)

    log._append = append
    log.write({"event": "request_refused", "sequence": 0})
    assert entered.wait(2)
    started = time.monotonic()
    for index in range(1, 9):
        log.write({"event": "request_refused", "sequence": index})
    assert time.monotonic() - started < 1
    assert log.state()["dropped"] == 3 and log.state()["pending_bytes"] == 5 * line_bytes
    release.set()
    assert log.flush(timeout=2)
    assert lines(path) == [0, 1, 2, 3, 4, 5]
    assert log.close()
