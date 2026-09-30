"""Pure candidate-contract and isolated SQLite tests; no models or servers."""
import hashlib
import json
import sqlite3
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from services.api.embedding_comparison import (
    FrozenDatabase,
    GraniteEmbedding,
    cls_l2,
    validate_granite_contract,
)
from services.api.errors import ApiError
from services.api.settings import Settings


def contracts():
    return {
        "config.json": {"hidden_size": 384, "pad_token_id": 179935, "cls_token_id": 179934},
        "1_Pooling/config.json": {"word_embedding_dimension": 384, "pooling_mode_cls_token": True, "pooling_mode_mean_tokens": False},
        "modules.json": [{"type": "sentence_transformers.models." + name} for name in ["Transformer", "Pooling", "Normalize"]],
        "config_sentence_transformers.json": {"prompts": {"query": "", "document": ""}},
        "sentence_bert_config.json": {"max_seq_length": 32768},
    }


def test_retrieval_granite_contract_rejects_e5_pooling_prefixes_and_missing_normalize():
    valid = contracts()
    validate_granite_contract(valid)
    for edit in [lambda value: value["1_Pooling/config.json"].update(pooling_mode_mean_tokens=True),
                 lambda value: value["config_sentence_transformers.json"]["prompts"].update(query="query: "),
                 lambda value: value["modules.json"].pop(),
                 lambda value: value["config.json"].update(pad_token_id=0)]:
        invalid = deepcopy(valid)
        edit(invalid)
        with pytest.raises(ApiError, match="contrat officiel Granite"):
            validate_granite_contract(invalid)


def test_retrieval_granite_pools_first_cls_token_and_rejects_implicit_pooled_graph():
    hidden = np.zeros((1, 3, 384), dtype=np.float32)
    hidden[0, 0, :2] = [3, 4]
    hidden[0, 1:, :2] = [100, -100]
    result = cls_l2(hidden, 1)
    assert result[0][:2] == pytest.approx([.6, .8])
    with pytest.raises(ApiError, match="sortie tokenisée"):
        cls_l2(hidden[:, 0, :], 1)
    hidden[0, 0, 0] = np.nan
    with pytest.raises(ApiError, match="Vecteurs Granite invalides"):
        cls_l2(hidden, 1)


def test_retrieval_granite_uses_empty_prefixes_actual_signature_and_pinned_padding(tmp_path):
    seen = {}
    class Tokenizer:
        def encode(self, text):
            seen["count_text"] = text
            return SimpleNamespace(ids=[179934, 8, 179938])
        def encode_batch(self, texts):
            seen["texts"] = texts
            return [SimpleNamespace(ids=[179934, 8, 179938]), SimpleNamespace(ids=[179934, 179938])]
    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name=name, type="tensor(int64)", shape=["batch", "sequence"]) for name in ["input_ids", "attention_mask"]]
        def get_outputs(self):
            return [SimpleNamespace(name="last_hidden_state", type="tensor(float)", shape=["batch", "sequence", 384])]
        def get_providers(self):
            return ["CPUExecutionProvider"]
        def run(self, names, feeds):
            seen["feeds"] = feeds
            output = np.zeros((2, 3, 384), dtype=np.float32)
            output[:, 0, 0] = 2
            return [output]
    embedding = GraniteEmbedding(Settings(tmp_path))
    embedding.tokenizer = lambda: Tokenizer()
    embedding.session = lambda: Session()
    assert embedding.count("plain query", False) == 3 and seen["count_text"] == "plain query"
    result = embedding.embed(["first", "second"], False)
    assert seen["texts"] == ["first", "second"]
    assert seen["feeds"]["input_ids"][1].tolist() == [179934, 179938, 179935]
    assert seen["feeds"]["attention_mask"][1].tolist() == [1, 1, 0]
    assert len(result) == 2 and len(result[0]) == 384 and result[0][0] == 1
    assert embedding.graph_signature["providers"] == ["CPUExecutionProvider"]


def test_retrieval_granite_rejects_long_immutable_passage_before_session(tmp_path):
    embedding = GraniteEmbedding(Settings(tmp_path))
    embedding.tokenizer = lambda: SimpleNamespace(encode_batch=lambda texts: [SimpleNamespace(ids=[179934] * 449)])
    embedding.session = lambda: pytest.fail("No graph may load for an incompatible frozen chunk")
    with pytest.raises(ApiError, match="fragmentation inchangée"):
        embedding.embed(["unchanged passage"])


def test_retrieval_comparison_snapshot_fts_is_readonly_without_sidecars(tmp_path):
    source_path = tmp_path / "source.sqlite3"
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    path = export_dir / "frozen.sqlite3"
    with sqlite3.connect(source_path) as writable:
        writable.execute("PRAGMA journal_mode=WAL")
        writable.execute("CREATE TABLE documents(id TEXT PRIMARY KEY,name TEXT)")
        writable.execute("INSERT INTO documents VALUES('d1','immutable')")
        writable.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text)")
        writable.execute("INSERT INTO chunks_fts VALUES('CCU-21 nominal voltage')")
        writable.commit()
        writable.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        with sqlite3.connect(path) as exported:
            writable.backup(exported)
        exported.close()
    writable.close()
    original = path.read_bytes()
    before_files = set(export_dir.iterdir())
    db = FrozenDatabase(path, hashlib.sha256(original).hexdigest())
    assert db.one("SELECT name FROM documents WHERE id=?", ("d1",))["name"] == "immutable"
    assert db.one("SELECT count(*) n FROM chunks_fts WHERE chunks_fts MATCH ?", ('"CCU"',))["n"] == 1
    with db.connect() as connection:
        connection.execute("BEGIN")
        assert connection.execute("SELECT count(*) FROM documents").fetchone()[0] == 1
        for sql in ["DELETE FROM documents", "PRAGMA journal_mode=WAL", "ATTACH DATABASE 'forbidden.sqlite3' AS forbidden"]:
            with pytest.raises(sqlite3.DatabaseError):
                connection.execute(sql)
    for write in [db.initialize, lambda: db.execute("DELETE FROM documents")]:
        with pytest.raises(ApiError, match="image comparative"):
            write()
    db.verify_image()
    assert path.read_bytes() == original and set(export_dir.iterdir()) == before_files == {path}


def test_retrieval_comparison_snapshot_refuses_wal_and_wrong_hash(tmp_path):
    path = tmp_path / "snapshot.sqlite3"
    with sqlite3.connect(path) as writable:
        writable.execute("CREATE TABLE evidence(text TEXT)")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ApiError, match="hash de l'image"):
        FrozenDatabase(path, "0" * 64)
    wal = tmp_path / "snapshot.sqlite3-wal"
    wal.write_bytes(b"pending log")
    with pytest.raises(ApiError, match="sans WAL"):
        FrozenDatabase(path, digest)


def test_retrieval_granite_wrong_publisher_revision_fails_without_engine(tmp_path):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"model_id": "intfloat/multilingual-e5-small", "revision": "other", "files": []}), encoding="utf-8")
    embedding = GraniteEmbedding(Settings(tmp_path), lock)
    with pytest.raises(ApiError, match="verrou officiel comparatif"):
        embedding.identity()
    assert embedding._session is None and embedding._tokenizer is None
