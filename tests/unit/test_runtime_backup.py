import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from services.api.db import Database
from services.runtime.artifacts import file_hash, write_json_atomic
from services.runtime.backup import database_summary, inside, rebase_database, verify_backup


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
