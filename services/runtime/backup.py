"""Snapshots cohérents et restauration dans une racine neuve, sans écrasement."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx
import yaml

from .artifacts import ROOT, file_hash, runtime_location, write_json_atomic
from .supervisor import (
    ProcessJob,
    acquire_qdrant_lock,
    app_origin,
    check_ports,
    data_path,
    environment,
    issue_qdrant_key,
    load_profile,
    native_paths,
    qdrant_data_path,
    qdrant_environment,
    qdrant_working_directory,
    send_owned_console_interrupt,
    status,
    wait_http,
    write_qdrant_config,
)

TABLES = ("documents", "document_versions", "extraction_revisions", "index_generations",
          "pages", "blocks", "chunks", "jobs", "query_runs", "citations", "embedding_cache")


# Codes Win32 relevés par Qdrant 1.19.1 quand un analyseur tient encore un fichier extrait :
# accès refusé (5), violation de partage (32), répertoire non vide (145).
TRANSIENT_WINDOWS_IO = ("(os error 5)", "(os error 32)", "(os error 145)")


def upload_snapshot(client: httpx.Client, base: str, snapshot: Path, attempts: int = 3) -> list[str]:
    """Charge un snapshot ; reprise bornée d'une erreur d'E/S Windows transitoire, collection absente.

    Toute autre erreur, ou une collection partiellement créée, arrête la restauration.
    Renvoie les échecs repris, conservés dans le rapport.
    """
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        with snapshot.open("rb") as file:
            response = client.post(base + "/snapshots/upload", params={"wait": "true", "priority": "snapshot",
                "checksum": file_hash(snapshot)}, files={"snapshot": (snapshot.name, file, "application/octet-stream")})
        if response.is_success:
            return failures
        transient = response.status_code == 500 and any(code in response.text for code in TRANSIENT_WINDOWS_IO)
        if not transient or attempt == attempts or client.get(base).status_code != 404:
            break
        failures.append(response.text[:400])
        time.sleep(attempt)
    response.raise_for_status()
    return failures

def database_summary(path: Path) -> dict:
    # Réservé aux bases figées/backup/checkpointées. immutable évite de créer
    # des fichiers WAL/SHM pendant la vérification des octets du snapshot.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        counts = {table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for table in TABLES}
        schema = [row[0] for row in connection.execute("SELECT version FROM schema_version ORDER BY version")]
    if integrity != "ok" or foreign_keys:
        raise ValueError("La base n'a pas satisfait integrity_check et foreign_key_check")
    return {"integrity": integrity, "foreign_key_errors": len(foreign_keys), "counts": counts, "schema": schema}


def inside(root: Path, relative: str) -> Path:
    name = PurePosixPath(relative)
    if not relative or name.is_absolute() or ".." in name.parts or "\\" in relative or ":" in relative:
        raise ValueError("Chemin de snapshot invalide")
    path = root.joinpath(*name.parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Chemin de snapshot hors racine")
    return path


def verify_backup(folder: Path) -> dict:
    folder = folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "rag-native-backup-v1" or manifest.get("state") != "complete":
        raise ValueError("Snapshot incomplet ou format non reconnu")
    seen = set()
    for item in manifest["files"]:
        if item["path"] in seen:
            raise ValueError("Chemin dupliqué dans le manifeste")
        seen.add(item["path"])
        path = inside(folder, item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or file_hash(path) != item["sha256"]:
            raise ValueError(f"Hash/taille du snapshot non conforme : {item['path']}")
    if {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()} != seen | {"manifest.json"}:
        raise ValueError("Fichiers supplémentaires dans le snapshot")
    database = database_summary(folder / "data/app.sqlite3")
    if database != manifest["sqlite"]:
        raise ValueError("Comptes SQLite différents du manifeste")
    return {"state": "verified", "backup_id": manifest["backup_id"], "files": len(seen), "sqlite": database}


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise ValueError("Lien sortant ou reparse point refusé dans les données")
        destination = target / path.relative_to(source)
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def create_backup(profile_path: Path, output: Path | None = None) -> dict:
    profile = load_profile(profile_path)
    directory = data_path(profile)
    current = status(profile_path)
    if current.get("status") != "running" or not current.get("supervisor_identity_valid"):
        raise RuntimeError("Sauvegarde : démarrer l'instance propriétaire avec rag up")
    if not all(item.get("identity_valid") for item in current["services"].values()):
        raise RuntimeError("Identité des services invalide")
    token = (directory / "control/admin-token").read_text(encoding="ascii")
    key_path = directory / "control/qdrant-api-key"
    qdrant_headers = {"api-key": key_path.read_text(encoding="ascii")} if key_path.exists() else {}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    identifier = f"{stamp}-{uuid.uuid4().hex[:8]}"
    output = (output or runtime_location(profile, "backups_dir") / identifier).resolve()
    if output.exists() or output.is_relative_to(directory):
        raise ValueError("La sauvegarde exige un chemin neuf hors données actives")
    existing = next(parent for parent in (output.parent, *output.parent.parents) if parent.exists())
    if shutil.disk_usage(existing).free < 2 * 1024**3:
        raise RuntimeError("Réserve disque de 2 Gio insuffisante avant sauvegarde")
    output.mkdir(parents=True)
    origin, verify = app_origin(profile)
    api = origin + "/api/v1"
    headers = {"X-RAG-Control-Token": token}
    manifest: dict[str, Any] = {"format": "rag-native-backup-v1", "backup_id": identifier,
                                "created_at_utc": datetime.now(UTC).isoformat(), "state": "incomplete",
                                "source_data_dir": str(directory), "profile_sha256": file_hash(profile_path),
                                "qdrant_version": "1.19.1", "collections": [], "files": []}
    write_json_atomic(output / "manifest.json", manifest)
    quiesce_requested = False
    backup_failure: BaseException | None = None
    try:
        with httpx.Client(timeout=600, trust_env=False, verify=verify) as client:
            quiesce_requested = True
            response = client.post(api + "/admin/quiesce", headers=headers)
            response.raise_for_status()
            manifest["quiesce"] = response.json()
            if manifest["quiesce"].get("active_queries"):
                raise RuntimeError("Une requête reste active après quiesce")
            saved_db = output / "data/app.sqlite3"
            saved_db.parent.mkdir(parents=True)
            with closing(sqlite3.connect(directory / "app.sqlite3")) as source, closing(sqlite3.connect(saved_db)) as target:
                source.backup(target)
                target.execute("PRAGMA journal_mode=DELETE")
            manifest["sqlite"] = database_summary(saved_db)
            for name in ("originals", "extractions"):
                copy_tree(directory / name, output / "data" / name)
            copy_tree(ROOT / ".runtime/manifests", output / "runtime-manifests")
            config = output / "config"
            config.mkdir()
            shutil.copy2(profile_path, config / "profile.yaml")
            shutil.copy2(ROOT / "config/artifacts.lock.json", config / "artifacts.lock.json")
            for source_name, saved_name in (("uv.lock", "uv.lock"),
                                            ("apps/web/pnpm-lock.yaml", "pnpm-lock.yaml"),
                                            ("pyproject.toml", "pyproject.toml"),
                                            ("packages/contracts/contracts.json", "contracts.json")):
                shutil.copy2(ROOT / source_name, config / saved_name)
            from .source_manifest import capture
            write_json_atomic(config / "source-manifest.json", capture())
            response = client.get(profile["qdrant"]["url"] + "/collections", headers=qdrant_headers)
            response.raise_for_status()
            for collection in response.json()["result"]["collections"]:
                name = collection["name"]
                escaped = quote(name, safe="")
                base = profile["qdrant"]["url"] + "/collections/" + escaped
                info = client.get(base, headers=qdrant_headers)
                info.raise_for_status()
                before = client.post(base + "/points/count", json={"exact": True}, headers=qdrant_headers)
                before.raise_for_status()
                response = client.post(base + "/snapshots", params={"wait": "true"}, headers=qdrant_headers)
                response.raise_for_status()
                snapshot = response.json()["result"]
                relative = "qdrant/" + uuid.uuid4().hex + ".snapshot"
                destination = inside(output, relative)
                destination.parent.mkdir(exist_ok=True)
                with client.stream("GET", base + "/snapshots/" + quote(snapshot["name"], safe=""), headers=qdrant_headers) as stream:
                    stream.raise_for_status()
                    with destination.open("xb") as file:
                        for chunk in stream.iter_bytes():
                            file.write(chunk)
                if snapshot.get("checksum") and file_hash(destination) != snapshot["checksum"]:
                    raise ValueError("Hash serveur Qdrant différent du téléchargement")
                manifest["collections"].append({"name": name, "snapshot": relative,
                    "points_count": before.json()["result"]["count"], "info": info.json()["result"],
                    "server_snapshot": snapshot})
            manifest["files"] = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size,
                                  "sha256": file_hash(p)} for p in sorted(output.rglob("*"))
                                 if p.is_file() and p != output / "manifest.json"]
            manifest["state"] = "complete"
            write_json_atomic(output / "manifest.json", manifest)
            result = verify_backup(output)
            return {**result, "path": str(output), "collections": len(manifest["collections"])}
    except BaseException as exc:
        backup_failure = exc
        manifest["state"] = "failed"
        manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
        try:
            write_json_atomic(output / "manifest.json", manifest)
        except Exception as record_error:
            exc.add_note(f"Écriture du manifeste d'échec impossible : {type(record_error).__name__}: {record_error}")
        raise
    finally:
        if quiesce_requested:
            try:
                with httpx.Client(timeout=30, trust_env=False, verify=verify) as client:
                    response = client.post(api + "/admin/resume", headers=headers)
                    response.raise_for_status()
            except Exception as resume_error:
                manifest["resume"] = {"state": "failed", "error": {"type": type(resume_error).__name__, "message": str(resume_error)}}
                if backup_failure is not None:
                    backup_failure.add_note(f"La reprise de l'instance a aussi échoué : {type(resume_error).__name__}: {resume_error}")
                try:
                    write_json_atomic(output / "manifest.json", manifest)
                except Exception as record_error:
                    (backup_failure or resume_error).add_note(
                        f"Écriture de l'échec de reprise impossible : {type(record_error).__name__}: {record_error}")
                if backup_failure is None:
                    raise


def rebase_value(value, old: Path, new: Path):
    if isinstance(value, dict):
        return {key: rebase_value(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rebase_value(item, old, new) for item in value]
    if isinstance(value, str):
        path = Path(value)
        if path.is_absolute() and path.is_relative_to(old):
            return str(new / path.relative_to(old))
    return value


def rebase_database(path: Path, old: Path, new: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table, field in (("document_versions", "blob_path"), ("extraction_revisions", "path"),
                             ("index_generations", "extraction_path")):
            for row_id, value in connection.execute(f'SELECT id,"{field}" FROM "{table}"').fetchall():
                if value:
                    connection.execute(f'UPDATE "{table}" SET "{field}"=? WHERE id=?',
                                       (rebase_value(value, old, new), row_id))
        for row_id, value in connection.execute("SELECT id,checkpoint_json FROM jobs").fetchall():
            connection.execute("UPDATE jobs SET checkpoint_json=? WHERE id=?",
                               (json.dumps(rebase_value(json.loads(value), old, new)), row_id))
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def restore_backup(folder: Path, target: Path, *, qdrant_port: int = 6343) -> dict:
    folder = folder.resolve()
    target = target.resolve()
    verification = verify_backup(folder)
    if target.exists() or target.is_relative_to(folder) or folder.is_relative_to(target):
        raise ValueError("Restauration : racine neuve, distincte de la sauvegarde exigée")
    check_ports([qdrant_port])
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["qdrant_version"] != "1.19.1":
        raise ValueError("Version snapshot Qdrant incompatible avec le runtime verrouillé")
    profile = yaml.safe_load((folder / "config/profile.yaml").read_text(encoding="utf-8"))
    profile["qdrant"].pop("storage_dir", None)
    if os.name == "nt" and len(str(target / "qdrant/storage")) > 57:
        identifier = hashlib.sha256(str(target).encode()).hexdigest()[:8]
        stores = runtime_location(profile, "restore_storage_dir")
        short_store = (stores / identifier).resolve()
        if not short_store.is_relative_to(stores) or short_store.exists():
            raise ValueError("Restauration : stockage Qdrant court neuf exigé sous runtime.restore_storage_dir")
        if len(str(short_store / "storage")) > 57:
            raise ValueError(f"Restauration : la cible {target} impose un stockage Qdrant court, mais runtime.restore_storage_dir ({stores}) "
                             f"donne {len(str(short_store / 'storage'))} caractères pour 57 ; choisir une cible de {57 - len(chr(92) + 'qdrant' + chr(92) + 'storage')} caractères au plus")
        profile["qdrant"]["storage_dir"] = str(short_store)
    qdrant_directory = qdrant_data_path(profile, target)
    target.mkdir(parents=True)
    report = {"state": "restoring", "backup_id": manifest["backup_id"], "data_dir": str(target),
              "qdrant_data_dir": str(qdrant_directory),
              "qdrant_storage_relocated_for_windows_path_limit": bool(profile["qdrant"].get("storage_dir")),
              "source_verification": verification, "collections": []}
    report_path = target / "restore-report.json"
    write_json_atomic(report_path, report)
    try:
        copy_tree(folder / "data", target)
        verified_copies = []
        for entry in manifest["files"]:
            relative = entry["path"]
            if not relative.startswith("data/"):
                continue
            copied = inside(target, relative.removeprefix("data/"))
            if copied.stat().st_size != entry["bytes"] or file_hash(copied) != entry["sha256"]:
                raise ValueError("Hash/taille différents dans les données restaurées avant rebasing")
            verified_copies.append(relative.removeprefix("data/"))
        report["copied_data_hashes_verified_before_rebase"] = verified_copies
        rebase_database(target / "app.sqlite3", Path(manifest["source_data_dir"]), target)
        report["sqlite"] = database_summary(target / "app.sqlite3")
        if report["sqlite"] != manifest["sqlite"]:
            raise ValueError("Comptes/integrité SQL différents après rebasing")
        profile["app"]["data_dir"] = str(target)
        profile["sqlite"]["path"] = str(target / "app.sqlite3")
        profile["qdrant"]["url"] = f"http://127.0.0.1:{qdrant_port}"
        control = target / "control"
        control.mkdir()
        config = write_qdrant_config(profile, target, control)
        # Le serveur de restauration exige lui aussi une clé, propre à cette restauration.
        restore_key = issue_qdrant_key(control)
        try:
            with closing(acquire_qdrant_lock(qdrant_directory)), ProcessJob() as job:
                # Serveur temporaire lancé depuis le stockage neuf, comme celui de l'instance (D1) : rien dans le programme.
                child = job.launch([str(native_paths()["qdrant"]), "--config-path", str(config), "--disable-telemetry"],
                                   cwd=qdrant_working_directory(qdrant_directory),
                                   env=qdrant_environment(environment(profile, target, ROOT / "config/local16.yaml"), restore_key),
                                   log_path=target / "restore-qdrant.log")
                wait_http(profile["qdrant"]["url"] + "/healthz", child)
                with httpx.Client(base_url=profile["qdrant"]["url"], headers={"api-key": restore_key},
                                  timeout=600, trust_env=False) as client:
                    listing = client.get("/collections")
                    listing.raise_for_status()
                    if listing.json()["result"]["collections"]:
                        raise ValueError("Le serveur de restauration n'est pas vide")
                    for item in manifest["collections"]:
                        base = "/collections/" + quote(item["name"], safe="")
                        retried = upload_snapshot(client, base, inside(folder, item["snapshot"]))
                        response = client.post(base + "/points/count", json={"exact": True})
                        response.raise_for_status()
                        count = response.json()["result"]["count"]
                        if count != item["points_count"]:
                            raise ValueError("Compte des points Qdrant différent après restauration")
                        report["collections"].append({"name": item["name"], "points_count": count,
                                                      "upload_attempts": len(retried) + 1, "retried_failures": retried})
                send_owned_console_interrupt(child, "qdrant")
                try:
                    report["qdrant_stop_exit_code"] = child.wait(30)
                except TimeoutError:
                    report["qdrant_stop"] = "forced_owned_job_close"
        finally:
            # La clé ne sert qu'au serveur temporaire, arrêté ici en succès comme en échec.
            (control / "qdrant-api-key").unlink(missing_ok=True)
        # Profil prêt pour un démarrage distinct ; le port API est explicite et libre.
        profile["app"]["port"] = 8795
        profile["qdrant"]["url"] = "http://127.0.0.1:6343" if qdrant_port == 6343 else f"http://127.0.0.1:{qdrant_port}"
        profile["llm"]["base_url"] = "http://127.0.0.1:11445"
        (target / "restored-profile.yaml").write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
        report["state"] = "restored_storage_verified"
        report["application_query_and_old_citation"] = "NOT_RUN"
        write_json_atomic(report_path, report)
        return report
    except Exception as exc:
        report["state"] = "failed"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, httpx.HTTPStatusError):
            report["error"]["http_status"] = exc.response.status_code
            report["error"]["native_error_body"] = exc.response.text[:8192]
        write_json_atomic(report_path, report)
        raise
