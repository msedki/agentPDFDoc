"""Atomic extraction checkpoints, independently verifiable after a crash."""

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

from .errors import IngestionError


def canonical_bytes(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical_bytes(data))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def extraction_lock(output_dir):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "native-fault.json").exists():
        raise IngestionError("EXTRACTION_QUARANTINED", "Cette extraction a observé une exception native ; ses preuves sont conservées et ne peuvent pas être réutilisées.")
    with (directory / ".ingestion.lock").open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            lock, unlock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1), lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            lock, unlock = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB), lambda: fcntl.flock(stream, fcntl.LOCK_UN)
        try:
            lock()
        except OSError:
            raise IngestionError("INGESTION_ALREADY_RUNNING", "Une extraction utilise déjà ce dossier.") from None
        try:
            yield
        finally:
            stream.seek(0)
            unlock()


class CheckpointStore:
    def __init__(self, directory, identity):
        self.directory = Path(directory)
        self.identity = identity

    def path(self, first, last):
        return self.directory / f"window-{first:06d}-{last:06d}.json"

    def read(self, first, last):
        path = self.path(first, last)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            payload = envelope["payload"]
            valid = (envelope["identity"] == self.identity and
                     envelope["sha256"] == hashlib.sha256(canonical_bytes(payload)).hexdigest() and
                     payload["page_start"] == first and payload["page_end"] == last)
            if not valid:
                raise ValueError("invalid checkpoint")
            return payload
        except (ValueError, KeyError, TypeError):
            raise IngestionError("CHECKPOINT_INVALID", "Un checkpoint d'extraction est incohérent.", {"page_start": first, "page_end": last}) from None

    def write(self, payload):
        envelope = {"identity": self.identity, "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest(), "payload": payload}
        atomic_json(self.path(payload["page_start"], payload["page_end"]), envelope)
