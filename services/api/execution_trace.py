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
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import ApiError

CURRENT_TRACE: ContextVar[ExecutionTrace | None] = ContextVar("rag_execution_trace", default=None)

# These are logical decoding bounds, not increases to the profile's physical
# JSONL quotas. Small events retain the original v1 representation.
COMPACT_MIN_BYTES = 262_144
COMPACT_MIN_SAVING = 4_096
MAX_EXPANDED_EVENT_BYTES = 33_554_432
MAX_EXPANDED_TRACE_BYTES = 67_108_864
MAX_EXPANDED_EVENT_NODES = 1_048_576
MAX_EXPANDED_TRACE_NODES = 2_097_152
MAX_PAYLOAD_DEPTH = 64
MAX_PAGE_REFERENCES = 4_096
MAX_PAGE_DICTIONARIES = 512
PAGE_ENCODING = "page-dictionary-v1"
_ENCODING_FIELDS = frozenset({"payload_encoding", "data_base", "page_dictionary", "page_references"})


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _shape(value: Any) -> tuple[int, int]:
    """Bound nesting and object count before encoding/copying an expanded tree."""
    nodes, deepest = 0, 0

    def visit(item, depth):
        nonlocal nodes, deepest
        nodes += 1
        if nodes > MAX_EXPANDED_EVENT_NODES:
            raise ValueError("Trop de nœuds dans les données de trace")
        if isinstance(item, (dict, list, tuple)):
            depth += 1
            deepest = max(deepest, depth)
            if depth > MAX_PAYLOAD_DEPTH:
                raise ValueError("Données de trace trop profondes")
            if isinstance(item, dict):
                nodes += len(item)  # JSON object keys also consume memory.
                if nodes > MAX_EXPANDED_EVENT_NODES:
                    raise ValueError("Trop de nœuds dans les données de trace")
                for child in item.values():
                    visit(child, depth)
            else:
                for child in item:
                    visit(child, depth)

    visit(value, 0)
    return nodes, deepest


def _bounded_payload(value: Any) -> bytes:
    parts, total = [], 0
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    for part in encoder.iterencode(value):
        encoded = part.encode("utf-8")
        total += len(encoded)
        if total > MAX_EXPANDED_EVENT_BYTES:
            raise ValueError("Données de trace reconstruites trop volumineuses")
        parts.append(encoded)
    return b"".join(parts)


def _compact_pages(payload: bytes) -> dict | None:
    """Factor only repeated page dictionaries; no marker inside documentary data."""
    if len(payload) < COMPACT_MIN_BYTES:
        return None
    data = json.loads(payload)
    pages: dict[str, dict] = {}
    page_bytes: dict[str, bytes] = {}
    occurrences: list[tuple[list[dict], str]] = []
    counts: dict[str, int] = {}

    def collect(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = [*path, {"key": key}]
                if key == "page" and isinstance(child, dict):
                    raw = canonical_bytes(child)
                    digest = hashlib.sha256(raw).hexdigest()
                    if digest in page_bytes and page_bytes[digest] != raw:
                        raise ValueError("Collision dans le registre de pages")
                    page_bytes[digest], pages[digest] = raw, child
                    counts[digest] = counts.get(digest, 0) + 1
                    occurrences.append((child_path, digest))
                    if len(occurrences) > MAX_PAGE_REFERENCES or len(pages) > MAX_PAGE_DICTIONARIES:
                        raise OverflowError
                else:
                    collect(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect(child, [*path, {"index": index}])

    try:
        collect(data, [])
    except OverflowError:
        return None  # Keep full v1, still subject to the unchanged physical cap.
    repeated = {digest for digest, count in counts.items() if count > 1}
    if not repeated:
        return None
    references = []
    for path, digest in occurrences:
        if digest not in repeated:
            continue
        parent = data
        for step in path[:-1]:
            parent = parent[step.get("key", step.get("index"))]
        del parent["page"]
        references.append({"path": path, "sha256": digest})
    encoded = {"payload_encoding": PAGE_ENCODING, "data_base": data,
               "page_dictionary": {digest: pages[digest] for digest in sorted(repeated)},
               "page_references": references}
    if len(canonical_bytes(encoded)) + COMPACT_MIN_SAVING >= len(payload):
        return None
    return encoded


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Clé JSON dupliquée dans la trace")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("Nombre JSON non fini dans la trace")


def _decode_line(raw: bytes) -> dict:
    # Scan before json.loads: the decoder must not recurse into an arbitrary
    # depth. The fixed envelope adds at most eight levels to a depth-64 payload.
    quoted, escaped, depth = False, False, 0
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > MAX_PAYLOAD_DEPTH + 8:
                raise ValueError("Événement de trace trop profond")
        elif char in (93, 125):
            depth -= 1
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError("Événement de trace non objet")
    return value


def _restore_pages(row: dict, remaining_nodes: int) -> tuple[Any, int]:
    """Validate all references and expansion costs before replicating any page."""
    if row.get("payload_encoding") != PAGE_ENCODING or "data" in row:
        raise ValueError("Encodage de trace inconnu ou ambigu")
    base, pages, references = row.get("data_base"), row.get("page_dictionary"), row.get("page_references")
    if (not isinstance(base, (dict, list)) or not isinstance(pages, dict)
            or not 1 <= len(pages) <= MAX_PAGE_DICTIONARIES or not isinstance(references, list)
            or not 1 <= len(references) <= MAX_PAGE_REFERENCES):
        raise ValueError("Registre de pages invalide ou hors limites")
    nodes, _ = _shape(base)
    if nodes > remaining_nodes:
        raise ValueError("Cumul de nœuds de trace hors limites")
    expanded_bytes = len(_bounded_payload(base))
    sizes, shapes = {}, {}
    for digest, page in pages.items():
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(page, dict):
            raise ValueError("Page de trace invalide")
        shapes[digest] = _shape(page)
        raw = _bounded_payload(page)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Page de trace modifiée")
        sizes[digest] = len(raw)
    targets: list[tuple[dict, str]] = []
    seen: set[tuple[tuple[str, str | int], ...]] = set()
    counts: dict[str, int] = {}
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
            raise ValueError("Référence de page invalide")
        path, digest = reference["path"], reference["sha256"]
        if (not isinstance(digest, str) or digest not in pages or not isinstance(path, list)
                or not 1 <= len(path) <= MAX_PAYLOAD_DEPTH):
            raise ValueError("Référence de page absente ou hors limites")
        steps: list[tuple[str, str | int]] = []
        for step in path:
            if not isinstance(step, dict) or len(step) != 1:
                raise ValueError("Étape de chemin non typée")
            if set(step) == {"key"} and isinstance(step["key"], str):
                steps.append(("key", step["key"]))
            elif set(step) == {"index"} and type(step["index"]) is int and step["index"] >= 0:
                steps.append(("index", step["index"]))
            else:
                raise ValueError("Étape de chemin invalide")
        identity = tuple(steps)
        if steps[-1] != ("key", "page") or identity in seen:
            raise ValueError("Chemin de page dupliqué ou mauvais champ")
        seen.add(identity)
        parent = base
        for kind, value in steps[:-1]:
            if kind == "key" and isinstance(value, str) and isinstance(parent, dict) and value in parent:
                parent = parent[value]
            elif kind == "index" and type(value) is int and isinstance(parent, list) and value < len(parent):
                parent = parent[value]
            else:
                raise ValueError("Chemin de page absent ou type incohérent")
        if not isinstance(parent, dict) or "page" in parent:
            raise ValueError("Collision de champ page")
        page_nodes, page_depth = shapes[digest]
        nodes += page_nodes + 1  # Insert the page key as well as its value.
        expanded_bytes += 7 + sizes[digest] + bool(parent)  # '"page":' and optional comma.
        if (len(path) + page_depth > MAX_PAYLOAD_DEPTH or nodes > min(MAX_EXPANDED_EVENT_NODES, remaining_nodes)
                or expanded_bytes > MAX_EXPANDED_EVENT_BYTES):
            raise ValueError("Expansion de trace hors limites")
        targets.append((parent, digest))
        counts[digest] = counts.get(digest, 0) + 1
    if set(counts) != set(pages) or any(count < 2 for count in counts.values()):
        raise ValueError("Registre de pages inutilisé ou non factorisé")
    if expanded_bytes != row["payload_bytes"]:
        raise ValueError("Taille reconstruite de trace incohérente")
    for parent, digest in targets:
        parent["page"] = deepcopy(pages[digest])
    return base, nodes


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
        self.expanded_bytes_written = 0
        self.expanded_nodes_written = 0
        self.compacted_events = 0
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
            nodes = _shape(data)[0] if self.mode == "full" else 0
            payload = _bounded_payload(data) if self.mode == "full" else canonical_bytes(data)
            if self.mode == "full" and (self.expanded_bytes_written + len(payload) > MAX_EXPANDED_TRACE_BYTES
                                       or self.expanded_nodes_written + nodes > MAX_EXPANDED_TRACE_NODES):
                raise ValueError("Cumul de données reconstruites hors limites")
            item = {"schema_version": 1, "sequence": self.sequence + 1, "phase": phase,
                    "utc": datetime.now(UTC).isoformat(), "elapsed_ms": round((time.monotonic() - self.started) * 1000, 3),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload_bytes": len(payload),
                    "previous_sha256": self.previous_hash, "capture_mode": self.mode}
            if self.mode == "full":
                compacted = _compact_pages(payload)
                if compacted is None:
                    item["data"] = data
                else:
                    item.update(schema_version=2, **compacted)
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
                if self.mode == "full":
                    self.expanded_bytes_written += len(payload)
                    self.expanded_nodes_written += nodes
                    self.compacted_events += item["schema_version"] == 2
                self.sequence += 1
                self.previous_hash = event_hash
                self.phases.add(phase)
            return True
        except (OSError, ValueError, TypeError, RecursionError, ApiError) as error:
            self.failed = error.code if isinstance(error, ApiError) else "trace_write_failed"
            if required:
                if isinstance(error, ApiError):
                    raise
                raise ApiError("trace_write_failed", "Écriture de la trace impossible ; envoi non traçable refusé.", 503) from error
            return False

    def summary(self) -> dict:
        return {"mode": self.mode, "file": self.path.name if self.path else None,
                "events": self.sequence, "bytes": self.bytes_written, "last_event_sha256": self.previous_hash,
                "expanded_payload_bytes": self.expanded_bytes_written, "compacted_events": self.compacted_events,
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
    """Verify stored v1/v2 chains, then return original, bounded full data.

    Version 2 is a storage encoding only: its page registry is local to one
    event. Returned ``data`` is reconstructed after checking the stored hash;
    the original payload hash/byte count must also match. No external lookup.
    """
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        raise ValueError("Trace non régulière ou trop volumineuse")
    rows: list[dict] = []
    previous = "0" * 64
    physical_bytes = expanded_bytes = expanded_nodes = 0
    with path.open("rb") as stream:
        while line := stream.readline(max_bytes + 1):
            physical_bytes += len(line)
            if physical_bytes > max_bytes:
                raise ValueError("Trace trop volumineuse pendant la lecture")
            if not line.endswith(b"\n"):
                raise ValueError("Dernier événement interrompu")
            row = _decode_line(line)
            if (type(row.get("schema_version")) is not int or row["schema_version"] not in {1, 2}
                    or type(row.get("payload_bytes")) is not int or row["payload_bytes"] < 0
                    or not isinstance(row.get("capture_mode"), str) or row["capture_mode"] not in {"full", "hashes"}):
                raise ValueError("En-tête de trace invalide")
            if (type(row.get("sequence")) is not int or row["sequence"] != len(rows) + 1
                    or row.get("previous_sha256") != previous):
                raise ValueError("Chaîne d'événements discontinue")
            claimed = row.pop("event_sha256", None)
            if fingerprint(row) != claimed:
                raise ValueError("Événement modifié")
            if row["capture_mode"] == "full":
                if (row["payload_bytes"] > MAX_EXPANDED_EVENT_BYTES
                        or expanded_bytes + row["payload_bytes"] > MAX_EXPANDED_TRACE_BYTES):
                    raise ValueError("Données reconstruites hors limites")
                if row["schema_version"] == 2:
                    data, nodes = _restore_pages(row, MAX_EXPANDED_TRACE_NODES - expanded_nodes)
                    row = {key: value for key, value in row.items() if key not in _ENCODING_FIELDS}
                    row["data"] = data
                else:
                    if "data" not in row or set(row) & _ENCODING_FIELDS:
                        raise ValueError("Données v1 manquantes ou encodage ambigu")
                    nodes = _shape(row["data"])[0]
                if expanded_nodes + nodes > MAX_EXPANDED_TRACE_NODES:
                    raise ValueError("Cumul de nœuds de trace hors limites")
                payload = _bounded_payload(row["data"])
                if (len(payload) != row["payload_bytes"]
                        or hashlib.sha256(payload).hexdigest() != row.get("payload_sha256")):
                    raise ValueError("Donnée modifiée")
                expanded_bytes += len(payload)
                expanded_nodes += nodes
            elif row["schema_version"] != 1 or "data" in row or set(row) & _ENCODING_FIELDS:
                raise ValueError("Encodage hashes ambigu")
            rows.append({**row, "event_sha256": claimed})
            previous = claimed
    return rows
