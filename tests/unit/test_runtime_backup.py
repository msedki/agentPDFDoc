import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from services.api.db import Database
from services.runtime.artifacts import file_hash, write_json_atomic
from services.runtime.backup import database_summary, inside, rebase_database, upload_snapshot, verify_backup


def populated_database(path, original_root):
    Database(path).initialize()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO documents(id,name,relative_path,created_at,updated_at) VALUES('d','proof.pdf','proof.pdf','t','t')")
        connection.execute("INSERT INTO document_versions(id,document_id,sha256,blob_path,created_at) VALUES('v','d','abc',?,'t')",
                           (str(original_root / "originals/proof.pdf"),))
        connection.execute("INSERT INTO jobs(id,document_id,version_id,state,stage,checkpoint_json,created_at,updated_at) VALUES('j','d','v','paused','extract',?,'t','t')",
                           (json.dumps({"output_dir": str(original_root / "extractions/v/j"), "unrelated": str(Path('C:/foreign/input'))}),))


def test_rebase_preserves_counts_and_original_database(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    source = original / "app.sqlite3"
    populated_database(source, original)
    baseline = database_summary(source)
    original_hash = file_hash(source)
    restored = tmp_path / "restored"
    restored.mkdir()
    target = restored / "app.sqlite3"
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    rebase_database(target, original, restored)
    assert database_summary(target) == baseline
    assert file_hash(source) == original_hash
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("SELECT blob_path FROM document_versions").fetchone()[0] == str(restored / "originals/proof.pdf")
        checkpoint = json.loads(connection.execute("SELECT checkpoint_json FROM jobs").fetchone()[0])
        assert checkpoint["output_dir"] == str(restored / "extractions/v/j")
        assert checkpoint["unrelated"] == str(Path('C:/foreign/input'))


def test_verified_snapshot_rejects_corruption_and_unlisted_file(tmp_path):
    saved_db = tmp_path / "data/app.sqlite3"
    populated_database(saved_db, tmp_path / "active")
    manifest = {"format": "rag-native-backup-v1", "state": "complete", "backup_id": "controlled",
                "sqlite": database_summary(saved_db), "files": [{"path": "data/app.sqlite3",
                "bytes": saved_db.stat().st_size, "sha256": file_hash(saved_db)}]}
    write_json_atomic(tmp_path / "manifest.json", manifest)
    assert verify_backup(tmp_path)["sqlite"]["counts"]["documents"] == 1
    foreign = tmp_path / "extra.txt"
    foreign.write_text("unexpected")
    with pytest.raises(ValueError, match="supplémentaires"):
        verify_backup(tmp_path)
    foreign.unlink()
    with saved_db.open("ab") as file:
        file.write(b"corruption")
    with pytest.raises(ValueError, match="Hash/taille"):
        verify_backup(tmp_path)


@pytest.mark.parametrize("relative", ["../escape", "C:/escape", "/escape", "data\\escape", "data/../../escape"])
def test_snapshot_cannot_escape_root(tmp_path, relative):
    with pytest.raises(ValueError, match="invalide"):
        inside(tmp_path, relative)


def _upload_client(responses, collection_status=404):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(collection_status)
        return responses.pop(0)
    return httpx.Client(base_url="http://127.0.0.1:6343", transport=httpx.MockTransport(handler)), calls


TRANSIENT_145 = {"status": {"error": "Service internal error: IO Error: failed to remove directory `x`: "
                                     "Le répertoire n'est pas vide. (os error 145)"}}


def test_snapshot_upload_retries_transient_windows_io_only_when_collection_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("services.runtime.backup.time.sleep", lambda seconds: None)
    snapshot = tmp_path / "c.snapshot"
    snapshot.write_bytes(b"snapshot")
    client, calls = _upload_client([httpx.Response(500, json=TRANSIENT_145), httpx.Response(200, json={"result": True})])
    with client:
        retried = upload_snapshot(client, "/collections/c", snapshot)
    assert len(retried) == 1 and "os error 145" in retried[0]
    assert calls == [("POST", "/collections/c/snapshots/upload"), ("GET", "/collections/c"),
                     ("POST", "/collections/c/snapshots/upload")]


@pytest.mark.parametrize(("responses", "collection_status"), [
    ([httpx.Response(500, json={"status": {"error": "Wrong input: checksum mismatch"}})], 404),
    ([httpx.Response(500, json=TRANSIENT_145)], 200),
    ([httpx.Response(500, json=TRANSIENT_145)] * 3, 404),
])
def test_snapshot_upload_stops_on_permanent_error_partial_collection_or_exhausted_attempts(
        tmp_path, monkeypatch, responses, collection_status):
    monkeypatch.setattr("services.runtime.backup.time.sleep", lambda seconds: None)
    snapshot = tmp_path / "c.snapshot"
    snapshot.write_bytes(b"snapshot")
    client, calls = _upload_client(list(responses), collection_status)
    with client, pytest.raises(httpx.HTTPStatusError):
        upload_snapshot(client, "/collections/c", snapshot)
    assert sum(method == "POST" for method, _ in calls) == len(responses)


def verified_backup_without_collection(folder: Path, source_root: Path) -> Path:
    """Sauvegarde complète réelle (base SQLite peuplée, profil livré, manifeste vérifiable), sans collection Qdrant."""
    import yaml

    from services.runtime.artifacts import ROOT

    saved_db = folder / "data/app.sqlite3"
    populated_database(saved_db, source_root)
    profile = folder / "config/profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(yaml.safe_dump(yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))),
                       encoding="utf-8")
    files = [{"path": path.relative_to(folder).as_posix(), "bytes": path.stat().st_size, "sha256": file_hash(path)}
             for path in (saved_db, profile)]
    write_json_atomic(folder / "manifest.json", {
        "format": "rag-native-backup-v1", "state": "complete", "backup_id": "d1-essai", "source_data_dir": str(source_root),
        "qdrant_version": "1.19.1", "sqlite": database_summary(saved_db), "collections": [], "files": files})
    assert verify_backup(folder)["state"] == "verified"
    return folder


def empty_qdrant_server(request: httpx.Request) -> httpx.Response:
    """Double nommé du serveur Qdrant de restauration, vide : seule la liste des collections est demandée."""
    assert (request.method, request.url.path) == ("GET", "/collections")
    return httpx.Response(200, json={"result": {"collections": []}})


class HttpxToTheEmptyQdrantServer:
    """Double nommé du module httpx vu par la restauration : de vrais clients httpx, reliés par MockTransport à
    empty_qdrant_server ; HTTPStatusError reste celle de httpx."""

    HTTPStatusError = httpx.HTTPStatusError

    @staticmethod
    def Client(**options) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(empty_qdrant_server), **options)


def ports_assumed_free(ports: list[int]) -> None:
    """Double nommé de check_ports : le port du serveur de restauration est tenu pour libre, sans être sondé."""


# Linux et Windows sont simulés sous Linux ; sous Windows réel, la garde MAX_PATH du stockage Qdrant déplacerait la
# restauration des chemins temporaires longs de pytest.
@pytest.mark.skipif(sys.platform == "win32", reason="plateformes simulées sous Linux")
@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_the_restore_server_starts_from_the_new_qdrant_storage_and_leaves_the_program_untouched(
        tmp_path, monkeypatch, platform):
    """D1 côté restauration : le serveur Qdrant temporaire était lui aussi lancé avec cwd=ROOT et écrivait
    `.qdrant-initialized` dans le programme. Linux : il démarre depuis le stockage neuf de la racine restaurée, dont les
    chemins restent ceux d'avant. Windows simulé : inchangé, racine du programme."""
    import yaml

    from services.runtime import backup, supervisor
    from tests.unit.test_runtime_supervisor import (
        QDRANT_INIT_FILE,
        MsvcrtDouble,
        ProgramBinariesDouble,
        cooperative_stop_accepted,
        program_entries,
        recording_jobs,
        run_on_platform,
        services_ready_at_once,
        simulated_program,
    )

    program = simulated_program(tmp_path)
    for module in (backup, supervisor):
        monkeypatch.setattr(module, "ROOT", program)
    monkeypatch.delenv("QDRANT_INIT_FILE_PATH", raising=False)
    folder = verified_backup_without_collection(tmp_path / "sauvegarde", tmp_path / "ancienne-racine")
    jobs = recording_jobs(monkeypatch, backup)
    monkeypatch.setattr(backup, "check_ports", ports_assumed_free)
    monkeypatch.setattr(backup, "native_paths", ProgramBinariesDouble(program))
    monkeypatch.setattr(backup, "wait_http", services_ready_at_once)
    monkeypatch.setattr(backup, "send_owned_console_interrupt", cooperative_stop_accepted)
    monkeypatch.setattr(backup, "httpx", HttpxToTheEmptyQdrantServer)
    msvcrt = MsvcrtDouble()
    if platform == "win32":
        monkeypatch.setattr(supervisor, "msvcrt", msvcrt, raising=False)
    before = program_entries(program)
    target = tmp_path / "racine-restaurée"
    report = run_on_platform(monkeypatch, platform, backup.restore_backup, folder, target, qdrant_port=16343)
    assert report["state"] == "restored_storage_verified" and len(jobs) == 1
    qdrant = jobs[0].launched["qdrant"]
    qdrant_directory = target.resolve() / "qdrant"
    assert report["qdrant_data_dir"] == str(qdrant_directory)
    config = yaml.safe_load((target / "control/qdrant.yaml").read_text(encoding="utf-8"))
    assert config["storage"]["storage_path"] == str(qdrant_directory / "storage")
    assert config["storage"]["snapshots_path"] == str(qdrant_directory / "snapshots")
    if platform == "win32":
        assert msvcrt.calls == [MsvcrtDouble.LK_NBLCK]
        assert qdrant.cwd == program
    else:
        assert qdrant.cwd == qdrant_directory and (qdrant_directory / QDRANT_INIT_FILE).is_file()
        assert program_entries(program) == before
