"""Capture passive bornée des entrées réellement utilisées, jamais de recherche de diagnostic.

Le mode full est un choix explicite de profil : il contient du texte documentaire.
Les journaux d'exploitation restent sans texte. Les traces sont privées, propres à
l'instance, et ne sont ni servies par HTTP ni supprimées automatiquement.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import ApiError

CURRENT_TRACE: ContextVar[ExecutionTrace | None] = ContextVar("rag_execution_trace", default=None)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class ExecutionTrace:
    """JSONL append-only avec hash de chaque donnée et chaîne d'intégrité des événements.

    Une limite atteinte avant envoi au modèle refuse l'envoi : jamais de promesse
    de rejeu d'une requête qui n'a pas été capturée. Les événements terminaux ne
    masquent pas une erreur primaire si le stockage devient indisponible.
    """

    _quota_lock = threading.Lock()

    def __init__(self, settings, query_id: str):
        self.mode = settings.value("trace", "mode", "off")
        self.path: Path | None = None
        self.sequence = 0
        self.bytes_written = 0
        self.previous_hash = "0" * 64
        self.phases: set[str] = set()
        self.failed: str | None = None
        self.stream = None
        self.started = time.monotonic()
        self.limit = settings.value("trace", "max_bytes_per_query", 2_097_152)
        self.total_limit = settings.value("trace", "max_total_bytes", 67_108_864)
        self.directory = settings.data_dir / settings.value("trace", "directory", "traces")
        if self.mode == "off":
            return
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", query_id):
            raise ApiError("trace_identifier_invalid", "Identifiant de trace invalide.", 500)
        # Aucun suivi de lien symbolique, y compris dans les parents du dossier dédié.
        root = settings.data_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        relative = Path(settings.value("trace", "directory", "traces"))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ApiError("trace_path_invalid", "Dossier de traces hors de l'instance.", 500)
        directory = root
        for part in relative.parts:
            directory = directory / part
            if directory.is_symlink():
                raise ApiError("trace_path_invalid", "Un lien symbolique ne peut pas héberger les traces.", 500)
            directory.mkdir(mode=0o700, exist_ok=True)
        if os.name == "posix":
            directory.chmod(0o700)
        self.directory = directory
        self.path = directory / (query_id + ".jsonl")
        try:
            with self._quota_lock:
                files = list(directory.glob("*.jsonl"))
                if len(files) >= settings.value("trace", "max_files", 256):
                    raise ApiError("trace_storage_full", "Quota de traces atteint ; archiver les traces locales avant de poursuivre.", 503)
                if sum(p.lstat().st_size for p in files) >= self.total_limit:
                    raise ApiError("trace_storage_full", "Quota de traces atteint ; archiver les traces locales avant de poursuivre.", 503)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
                self.stream = os.fdopen(fd, "wb", buffering=0)
        except OSError as error:
            raise ApiError("trace_unavailable", "Impossible de créer la trace privée de cette requête.", 503) from error

    def record(self, phase: str, data: Any, *, required: bool = True) -> bool:
        if self.mode == "off":
            return True
        try:
            payload = canonical_bytes(data)
            item = {"schema_version": 1, "sequence": self.sequence + 1, "phase": phase,
                    "utc": datetime.now(UTC).isoformat(), "elapsed_ms": round((time.monotonic() - self.started) * 1000, 3),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload_bytes": len(payload),
                    "previous_sha256": self.previous_hash, "capture_mode": self.mode}
            if self.mode == "full":
                item["data"] = data
            event_hash = fingerprint(item)
            line = canonical_bytes({**item, "event_sha256": event_hash}) + b"\n"
            with self._quota_lock:
                if self.bytes_written + len(line) > self.limit:
                    raise ApiError("trace_budget_exceeded", "La trace dépasse le budget par requête ; réduire le contexte ou ajuster le profil.", 503)
                total = sum(p.lstat().st_size for p in self.directory.glob("*.jsonl"))
                if total + len(line) > self.total_limit:
                    raise ApiError("trace_storage_full", "Quota de traces atteint ; archiver les traces locales avant de poursuivre.", 503)
                if self.stream is None:
                    raise OSError("Trace fermée")
                written = self.stream.write(line)
                if written != len(line):
                    # FileIO peut réussir partiellement, notamment quand le
                    # stockage se remplit. La trace reste alors interrompue et
                    # aucun envoi ne peut se fonder sur cet événement incomplet.
                    raise OSError("Écriture incomplète de la trace")
                self.bytes_written += len(line)
                self.sequence += 1
                self.previous_hash = event_hash
                self.phases.add(phase)
            return True
        except (OSError, ValueError, TypeError, ApiError) as error:
            self.failed = error.code if isinstance(error, ApiError) else "trace_write_failed"
            if required:
                if isinstance(error, ApiError):
                    raise
                raise ApiError("trace_write_failed", "Écriture de la trace impossible ; envoi non traçable refusé.", 503) from error
            return False

    def summary(self) -> dict:
        return {"mode": self.mode, "file": self.path.name if self.path else None,
                "events": self.sequence, "bytes": self.bytes_written, "last_event_sha256": self.previous_hash,
                "failure": self.failed,
                "replayable_content": self.mode == "full" and self.failed is None and "llm.request" in self.phases,
                "terminal_captured": bool(self.phases & {"query.done", "query.error", "query.cancelled"})}

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def record_event(phase: str, data: Any, *, required: bool = True) -> bool:
    trace = CURRENT_TRACE.get()
    return trace.record(phase, data, required=required) if trace else True


def read_verified_trace(path: Path, max_bytes: int = 16_777_216) -> list[dict]:
    """Vérification hors ligne ; ne crée ni ne relance une requête réseau."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        raise ValueError("Trace non régulière ou trop volumineuse")
    rows = []
    previous = "0" * 64
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.endswith("\n"):
                raise ValueError("Dernier événement interrompu")
            row = json.loads(line)
            if row.get("sequence") != number or row.get("previous_sha256") != previous:
                raise ValueError("Chaîne d'événements discontinue")
            claimed = row.pop("event_sha256")
            if fingerprint(row) != claimed:
                raise ValueError("Événement modifié")
            if "data" in row and fingerprint(row["data"]) != row["payload_sha256"]:
                raise ValueError("Donnée modifiée")
            rows.append({**row, "event_sha256": claimed})
            previous = claimed
    return rows
