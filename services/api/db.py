from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import json
import re
import sqlite3
from urllib.parse import unquote
from uuid import uuid4

from .errors import ApiError


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


def json_dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def relative_pdf_path(value: str):
    if len(value) > 1024:
        raise ApiError("invalid_path", "Chemin trop long.")
    decoded = value
    for _ in range(3):
        result = unquote(decoded)
        if result == decoded:
            break
        decoded = result
    decoded = decoded.replace("\\", "/")
    parts = decoded.split("/")
    if (not decoded or PurePosixPath(decoded).is_absolute() or PureWindowsPath(decoded).drive
        or any(p in {"", ".", ".."} or p.endswith((".", " ")) or re.search(r'[\x00-\x1f<>:"|?*]', p) for p in parts)
        or any(re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p) for p in parts)
        or not parts[-1].lower().endswith(".pdf")):
        raise ApiError("invalid_path", "Un chemin relatif PDF sûr est requis.")
    return "/".join(parts)


MIGRATIONS = Path(__file__).parent / "migrations"


def migrations():
    return sorted((int(path.name[:3]), path) for path in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA cache_size=-32768")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def schema_version(connection):
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone():
            return 0
        return connection.execute("SELECT max(version) FROM schema_version").fetchone()[0] or 0

    @staticmethod
    def migrate(connection, script):
        """Applique un script versionné dans une transaction ; un ADD COLUMN déjà présent (base patchée à chaud) est ignoré."""
        statement = ""
        connection.execute("BEGIN IMMEDIATE")
        try:
            for line in script.splitlines(keepends=True):
                statement += line
                if not sqlite3.complete_statement(statement):
                    continue
                added = re.match(r"\s*ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)", re.sub(r"(?m)^\s*--.*$", "", statement), re.IGNORECASE)
                if not added or added[2] not in {row["name"] for row in connection.execute(f"PRAGMA table_info({added[1]})")}:
                    connection.execute(statement)
                statement = ""
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scripts = migrations()
        with self.connect() as connection:
            current, supported = self.schema_version(connection), scripts[-1][0]
            if current > supported:
                raise ApiError("database_schema_too_new", f"Base au schéma v{current}, plus récent que le code (v{supported}) ; aucune migration descendante.", 503,
                               {"database_version": current, "supported_version": supported})
            connection.execute("PRAGMA journal_mode=WAL")
            for _, path in scripts:
                self.migrate(connection, path.read_text(encoding="utf-8"))
            connection.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(text)")
            connection.execute("INSERT INTO temp.fts_probe VALUES('contrôle')")
            assert connection.execute("SELECT count(*) FROM temp.fts_probe WHERE fts_probe MATCH 'controle'").fetchone()[0] == 1
        with self.transaction() as connection:
            timestamp = now()
            connection.execute("UPDATE jobs SET state='paused',stage='interrupted',error_code='interrupted',error_message='Traitement interrompu ; reprise manuelle au dernier checkpoint.',lease_pid=NULL,updated_at=? WHERE state IN ('extracting','indexing','running','pausing','cancelling')", (timestamp,))
            for row in connection.execute("SELECT id,last_event_id FROM query_runs WHERE state IN ('queued','running')").fetchall():
                event_id = row["last_event_id"] + 1
                connection.execute("UPDATE query_runs SET state='interrupted',last_event_id=?,updated_at=? WHERE id=?", (event_id, timestamp, row["id"]))
                connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (row["id"], event_id, "error", json_dump({"code": "interrupted", "message": "Génération interrompue par le redémarrage."}), timestamp))

    def rows(self, sql, parameters=()):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

    def one(self, sql, parameters=()):
        rows = self.rows(sql, parameters)
        return rows[0] if rows else None

    def execute(self, sql, parameters=()):
        with self.transaction() as connection:
            connection.execute(sql, parameters)

    def version(self, version_id):
        row = self.one("SELECT v.*,d.name AS document_name,d.deleted_at FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE v.id=?", (version_id,))
        if not row or row["deleted_at"]:
            raise ApiError("source_removed", "Source absente ou supprimée.", 404)
        return row

    @staticmethod
    def ensure_folders(connection, components):
        parent_id = None
        for count, name in enumerate(components[:-1], 1):
            folder_path = "/".join(components[:count])
            row = connection.execute("SELECT id FROM folders WHERE path=?", (folder_path,)).fetchone()
            if row:
                parent_id = row[0]
            else:
                folder_id = uid()
                connection.execute("INSERT INTO folders VALUES(?,?,?,?)", (folder_id, parent_id, name, folder_path))
                parent_id = folder_id
        return parent_id

    def import_original(self, relative_path, sha256, blob_path):
        relative_path = relative_pdf_path(relative_path)
        timestamp = now()
        with self.transaction() as connection:
            components = relative_path.split("/")
            parent_id = self.ensure_folders(connection, components)
            document = connection.execute("SELECT * FROM documents WHERE relative_path=?", (relative_path,)).fetchone()
            if document and document["deleted_at"]:
                raise ApiError("document_removed", "Ce chemin appartient à un document supprimé ; utiliser un nouveau chemin.", 409)
            document_id = document["id"] if document else uid()
            if not document:
                connection.execute("INSERT INTO documents(id,folder_id,name,relative_path,created_at,updated_at) VALUES(?,?,?,?,?,?)", (document_id, parent_id, components[-1], relative_path, timestamp, timestamp))
            version = connection.execute("SELECT id FROM document_versions WHERE document_id=? AND sha256=?", (document_id, sha256)).fetchone()
            if version:
                version_id = version[0]
                job = connection.execute("SELECT id,state FROM jobs WHERE version_id=? ORDER BY created_at DESC LIMIT 1", (version_id,)).fetchone()
                if job and job["state"] in {"queued", "extracting", "indexing", "ready", "ready_partial"}:
                    return {"document_id": document_id, "version_id": version_id, "job_id": job["id"], "reused": True}
                if job and job["state"] in {"paused", "pausing", "cancelling"}:
                    # Un second job concurrent sur la même version doublerait extraction et génération.
                    return {"document_id": document_id, "version_id": version_id, "job_id": job["id"], "reused": True,
                            "job_state": job["state"], "resume_required": True}
            else:
                version_id = uid()
                connection.execute("INSERT INTO document_versions(id,document_id,sha256,blob_path,created_at) VALUES(?,?,?,?,?)", (version_id, document_id, sha256, str(blob_path), timestamp))
            job_id = uid()
            connection.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,created_at,updated_at) VALUES(?,?,?,'queued','queued',?,?)", (job_id, document_id, version_id, timestamp, timestamp))
            if not document or not document["active_generation_id"]:
                connection.execute("UPDATE documents SET state='queued',updated_at=? WHERE id=?", (timestamp, document_id))
        return {"document_id": document_id, "version_id": version_id, "job_id": job_id, "reused": False}

    def move_document(self, document_id, relative_path):
        """Déplace ou renomme dans l'arborescence : ni job, ni version, ni génération, ni embedding."""
        relative_path = relative_pdf_path(relative_path)
        with self.transaction() as connection:
            document = connection.execute("SELECT relative_path,folder_id,name,deleted_at FROM documents WHERE id=?", (document_id,)).fetchone()
            if not document or document["deleted_at"]:
                raise ApiError("document_not_found", "Document inconnu.", 404)
            folder_id, name = document["folder_id"], document["name"]
            if relative_path != document["relative_path"]:
                if connection.execute("SELECT 1 FROM documents WHERE relative_path=? AND id<>?", (relative_path, document_id)).fetchone():
                    raise ApiError("path_conflict", "Ce chemin appartient déjà à un autre document, actif ou supprimé.", 409)
                components = relative_path.split("/")
                folder_id, name = self.ensure_folders(connection, components), components[-1]
                connection.execute("UPDATE documents SET relative_path=?,folder_id=?,name=?,updated_at=? WHERE id=?", (relative_path, folder_id, name, now(), document_id))
        return {"document_id": document_id, "relative_path": relative_path, "previous_relative_path": document["relative_path"],
                "folder_id": folder_id, "name": name, "moved": relative_path != document["relative_path"]}

    def generation_for_version(self, version_id, extraction_revision_id=None):
        self.version(version_id)
        revision_filter = " AND extraction_revision_id=?" if extraction_revision_id is not None else ""
        parameters = (version_id, extraction_revision_id) if extraction_revision_id is not None else (version_id,)
        generation = self.one("SELECT * FROM index_generations WHERE version_id=? AND state IN ('ready','ready_partial') AND published_at IS NOT NULL" + revision_filter + " ORDER BY published_at DESC LIMIT 1", parameters)
        if not generation:
            if extraction_revision_id is not None:
                raise ApiError("extraction_revision_not_found", "Révision absente ou non publiée pour cette version.", 404)
            raise ApiError("not_indexed", "Cette version n'est pas encore indexée.", 409)
        return generation

    def add_event(self, query_id, kind, data):
        with self.transaction() as connection:
            query = connection.execute("SELECT last_event_id FROM query_runs WHERE id=?", (query_id,)).fetchone()
            if not query:
                raise ApiError("query_not_found", "Question inconnue.", 404)
            event_id = query[0] + 1
            connection.execute("UPDATE query_runs SET last_event_id=?,updated_at=? WHERE id=?", (event_id, now(), query_id))
            connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (query_id, event_id, kind, json_dump(data), now()))
            connection.execute("DELETE FROM events WHERE query_id=? AND id < ? AND type='delta'", (query_id, max(0, event_id - 512)))
        return event_id

    def file_path(self, version_id, originals_root):
        row = self.version(version_id)
        path = Path(row["blob_path"]).resolve()
        try:
            path.relative_to(Path(originals_root).resolve())
        except ValueError as error:
            raise ApiError("invalid_storage_path", "Chemin de stockage non autorisé.", 409) from error
        if not path.is_file() or path.is_symlink():
            raise ApiError("source_removed", "Original indisponible.", 404)
        return path, row
