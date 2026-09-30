"""Development-only Granite adapter. Never imported by the running API.

The separate publisher lock is owned by runtime provisioning. This adapter
does not download artifacts or apply E5 prefixes/mean pooling to Granite.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from .db import Database
from .embedding import EmbeddingService
from .errors import ApiError
from .retrieval import QdrantStore

GRANITE_MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
GRANITE_REVISION = "835ad14087e140460703cf0fae09f97d469d65c2"
GRANITE_GRAPH_SHA = "a6022dd8220ea6f6595562a1328ee216f4a94faa55362f2f4747c80f1e78772e"
GRANITE_TOKENIZER_SHA = "4f2842d568e2724370aec203652a42ac783c7937f8347a1a2cc7506d71f1582f"


def file_sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def validate_granite_contract(configs):
    model, pool = configs["config.json"], configs["1_Pooling/config.json"]
    enabled = {key for key, value in pool.items() if key.startswith("pooling_mode_") and value is True}
    modules = [module["type"].rsplit(".", 1)[-1] for module in configs["modules.json"]]
    if (model.get("hidden_size") != 384 or model.get("pad_token_id") != 179935
            or model.get("cls_token_id") != 179934 or pool.get("word_embedding_dimension") != 384
            or enabled != {"pooling_mode_cls_token"} or modules != ["Transformer", "Pooling", "Normalize"]
            or configs["config_sentence_transformers.json"].get("prompts") != {"query": "", "document": ""}
            or configs["sentence_bert_config.json"].get("max_seq_length") != 32768):
        raise ApiError("incompatible_comparison_contract", "Le contrat officiel Granite CLS/L2/préfixes vides ne correspond pas aux artefacts.", 503)


def cls_l2(hidden_state, batch_size):
    hidden_state = np.asarray(hidden_state)
    if hidden_state.ndim != 3 or hidden_state.shape[0] != batch_size or hidden_state.shape[1] < 1 or hidden_state.shape[2] != 384:
        raise ApiError("unsupported_comparison_graph", "Granite exige une sortie tokenisée non poolée [batch, sequence, 384].", 503)
    vectors = hidden_state[:, 0, :].astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if not np.isfinite(vectors).all() or np.any(norms <= 1e-12):
        raise ApiError("invalid_embedding_output", "Vecteurs Granite invalides.", 503)
    return (vectors / norms).tolist()


class GraniteEmbedding(EmbeddingService):
    def __init__(self, settings, lock_path=None):
        super().__init__(settings)
        self.directory = settings.root / ".runtime/models/granite-97m-int8"
        self.lock_path = Path(lock_path or settings.root / "config/embedding-comparison.lock.json")
        self.graph_signature = None

    def model_path(self):
        path = self.directory / "onnx/model_quint8_avx2.onnx"
        if not path.is_file():
            raise ApiError("comparison_not_provisioned", "Graphe Granite local absent ; aucun téléchargement implicite.", 503)
        return path

    def identity(self):
        with self._lock:
            if self._identity is None:
                lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if lock.get("model_id") != GRANITE_MODEL or lock.get("revision") != GRANITE_REVISION or len(lock.get("files", [])) != 10:
                    raise ApiError("comparison_identity_not_verified", "Le verrou officiel comparatif est incompatible.", 503)
                hashes = {}
                for artifact in lock["files"]:
                    path = self.settings.path(artifact["target"])
                    if (not path.is_relative_to(self.directory.resolve()) or artifact.get("revision") != GRANITE_REVISION
                            or not artifact.get("url", "").startswith(f"https://huggingface.co/{GRANITE_MODEL}/resolve/{GRANITE_REVISION}/")):
                        raise ApiError("comparison_identity_not_verified", "Source ou chemin Granite incompatible.", 503)
                    if not path.is_file() or path.stat().st_size != artifact["size"]:
                        raise ApiError("comparison_not_provisioned", "Artefact Granite local absent ou incomplet.", 503)
                    sha = file_sha(path)
                    if "sha256" in artifact:
                        verified = sha == artifact["sha256"]
                    else:
                        data = path.read_bytes()
                        verified = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == artifact.get("git_blob_sha1")
                    if not verified:
                        raise ApiError("comparison_identity_not_verified", "Hash local différent du verrou officiel Granite.", 503)
                    relative = path.relative_to(self.directory.resolve()).as_posix()
                    if relative in hashes:
                        raise ApiError("comparison_identity_not_verified", "Artefact Granite dupliqué dans le verrou.", 503)
                    hashes[relative] = sha
                if hashes.get("onnx/model_quint8_avx2.onnx") != GRANITE_GRAPH_SHA or hashes.get("tokenizer.json") != GRANITE_TOKENIZER_SHA:
                    raise ApiError("comparison_identity_not_verified", "Identité de graphe/tokenizer Granite différente de la révision retenue.", 503)
                config_paths = ["config.json", "1_Pooling/config.json", "modules.json", "sentence_bert_config.json", "config_sentence_transformers.json"]
                configs = {path: json.loads((self.directory / path).read_text(encoding="utf-8")) for path in config_paths}
                validate_granite_contract(configs)
                identity = {"model_id": GRANITE_MODEL, "revision": GRANITE_REVISION, "files_sha256": hashes,
                            "graph_sha256": GRANITE_GRAPH_SHA, "tokenizer_sha256": GRANITE_TOKENIZER_SHA,
                            "query_prefix": "", "passage_prefix": "", "pooling": "cls_first_token", "normalize_l2": True,
                            "dimensions": 384, "precision": "uint8", "provider": "CPUExecutionProvider",
                            "publisher_max_tokens": 32768, "controlled_passage_max_tokens": 448, "controlled_query_max_tokens": 512}
                identity["fingerprint"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                self._identity = identity
            return dict(self._identity)

    def tokenizer(self):
        with self._lock:
            if self._tokenizer is None:
                self.identity()
                from tokenizers import Tokenizer
                started, before = time.perf_counter(), self.memory_sample()
                tokenizer = Tokenizer.from_file(str(self.directory / "tokenizer.json"))
                tokenizer.no_padding()
                tokenizer.no_truncation()
                config = json.loads((self.directory / "tokenizer_config.json").read_text(encoding="utf-8"))
                pad = config.get("pad_token")
                if isinstance(pad, dict):
                    pad = pad.get("content")
                if tokenizer.token_to_id(pad) != 179935:
                    raise ApiError("invalid_embedding_tokenizer", "Le padding Granite ne correspond pas au contrat officiel.", 503)
                self._tokenizer = tokenizer
                self._tokenizer_load_count += 1
                self._tokenizer_load_measurement = {"elapsed_ms": (time.perf_counter() - started) * 1000,
                    "before": before, "after": self.memory_sample(), "reload_after_release": self._tokenizer_release_measurement is not None}
                if self._tokenizer_release_measurement:
                    self._tokenizer_release_measurement["next_reload_measurement"] = "observed"
            return self._tokenizer

    def count(self, text, passage=True):
        with self._lock:
            count = len(self.tokenizer().encode(text).ids)
            self._record_token_count(text, count)
            return count

    def embed(self, texts, passage=True):
        if not texts:
            return []
        with self._lock:
            encodings = self.tokenizer().encode_batch(texts)
            for text, encoding in zip(texts, encodings, strict=True):
                self._record_token_count(text, len(encoding.ids))
            maximum = 448 if passage else 512
            if any(not encoding.ids or encoding.ids[0] != 179934 for encoding in encodings):
                raise ApiError("invalid_embedding_tokenizer", "Le premier token Granite doit être le CLS officiel.", 503)
            if any(len(encoding.ids) > maximum for encoding in encodings):
                raise ApiError("comparison_input_too_long", "Un texte figé dépasse le budget contrôlé Granite ; fragmentation inchangée, essai refusé.", 422)
            session = self.session()
            inputs, outputs = session.get_inputs(), session.get_outputs()
            self.graph_signature = {"inputs": [{"name": node.name, "type": node.type, "shape": node.shape} for node in inputs],
                                    "outputs": [{"name": node.name, "type": node.type, "shape": node.shape} for node in outputs],
                                    "providers": session.get_providers()}
            if {node.name for node in inputs} != {"input_ids", "attention_mask"}:
                raise ApiError("unsupported_comparison_graph", "Entrées ONNX Granite non qualifiées.", 503)
            token_outputs = [node for node in outputs if len(node.shape) == 3 and node.shape[-1] == 384]
            if len(token_outputs) != 1:
                raise ApiError("unsupported_comparison_graph", "Une sortie tokenisée Granite unique est requise avant pooling CLS.", 503)
            batch_size = min(8, self.settings.value("embedding", "batch_size", 8))
            vectors = []
            for start in range(0, len(encodings), batch_size):
                batch = encodings[start:start + batch_size]
                ids = np.full((len(batch), max(len(encoding.ids) for encoding in batch)), 179935, dtype=np.int64)
                mask = np.zeros_like(ids)
                for index, encoding in enumerate(batch):
                    ids[index, :len(encoding.ids)] = encoding.ids
                    mask[index, :len(encoding.ids)] = 1
                feeds = {}
                for node in inputs:
                    dtype = {"tensor(int64)": np.int64, "tensor(int32)": np.int32}.get(node.type)
                    if dtype is None:
                        raise ApiError("unsupported_comparison_graph", "Type d'entrée ONNX Granite non qualifié.", 503)
                    feeds[node.name] = (ids if node.name == "input_ids" else mask).astype(dtype, copy=False)
                self._inference["run_calls"] += 1
                self._inference["inputs_submitted"] += len(batch)
                try:
                    output = session.run([token_outputs[0].name], feeds)[0]
                except Exception:
                    self._inference["run_failed"] += 1
                    raise
                self._inference["run_completed"] += 1
                self._inference["inputs_completed"] += len(batch)
                self._inference["passage_inputs_completed" if passage else "query_inputs_completed"] += len(batch)
                vectors.extend(cls_l2(output, len(batch)))
            return vectors


class FrozenDatabase(Database):
    """An exported checkpointed SQLite image, immutable and without sidecars."""
    def __init__(self, path, expected_sha256):
        super().__init__(Path(path).resolve())
        self.expected_sha256 = expected_sha256
        self.verify_image()
        self._stat = (self.path.stat().st_size, self.path.stat().st_mtime_ns)

    def verify_image(self):
        if not self.path.is_file() or any(Path(str(self.path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise ApiError("comparison_snapshot_required", "Une image SQLite exportée sans WAL/SHM/journal est requise.", 409)
        if file_sha(self.path) != self.expected_sha256:
            raise ApiError("comparison_snapshot_changed", "Le hash de l'image SQLite diffère de l'identité figée.", 409)

    @staticmethod
    def _authorize(action, first, second, database, trigger):
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_RECURSIVE}
        if action in allowed or (action == sqlite3.SQLITE_PRAGMA and first in {"data_version", "quick_check", "table_info"} and second is None):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    @contextmanager
    def connect(self):
        if (self.path.stat().st_size, self.path.stat().st_mtime_ns) != self._stat:
            raise ApiError("comparison_snapshot_changed", "L'image SQLite a changé pendant le comparatif.", 409)
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro&immutable=1", uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.set_authorizer(self._authorize)
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self):
        raise ApiError("comparison_read_only", "L'image comparative ne peut pas être initialisée.", 409)

    def execute(self, sql, parameters=()):
        raise ApiError("comparison_read_only", "L'image comparative ne peut pas être modifiée.", 409)

    @contextmanager
    def transaction(self):
        raise ApiError("comparison_read_only", "Les transactions d'écriture comparatives sont interdites.", 409)
        yield


class ComparisonVectorStore(QdrantStore):
    def __init__(self, settings, embedding, prefix):
        if not re.fullmatch(r"diag_gr97(?:_[a-z0-9]{1,8})?", prefix):
            raise ApiError("invalid_comparison_collection", "Préfixe court diag_gr97 avec suffixe optionnel de huit caractères maximum requis.", 422)
        identity = embedding.identity()
        super().__init__(settings)
        self.collection_prefix = prefix
        self._identity = identity
