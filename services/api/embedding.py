import hashlib
import gc
import json
from pathlib import Path
import threading
import time

import numpy as np

from .errors import ApiError


class EmbeddingService:
    """One lazily loaded local INT8 ONNX session; no model downloads."""

    def __init__(self, settings):
        self.settings = settings
        self.directory = settings.embedding_dir
        self._tokenizer = None
        self._session = None
        self._lock = threading.RLock()
        self._identity = None
        self._load_measurement = None
        self._release_measurement = None
        self._load_count = 0
        self._tokenizer_load_count = 0
        self._tokenizer_load_measurement = None
        self._tokenizer_release_measurement = None
        self._last_token_count = None
        self._token_count_reference = None
        self._inference = {"run_calls": 0, "run_completed": 0, "run_failed": 0,
                           "inputs_submitted": 0, "inputs_completed": 0,
                           "passage_inputs_completed": 0, "query_inputs_completed": 0}

    @staticmethod
    def memory_sample():
        import psutil
        return {"available_mib": round(psutil.virtual_memory().available / 1048576, 2),
                "process_rss_mib": round(psutil.Process().memory_info().rss / 1048576, 2)}

    def lifecycle(self):
        with self._lock:
            return {"session_loaded": self._session is not None, "load_count": self._load_count,
                    "last_load": self._load_measurement, "last_release": self._release_measurement,
                    "tokenizer_loaded": self._tokenizer is not None, "tokenizer_load_count": self._tokenizer_load_count,
                    "last_tokenizer_load": self._tokenizer_load_measurement, "last_tokenizer_release": self._tokenizer_release_measurement,
                    "last_token_count": self._last_token_count,
                    "inference": {**self._inference, "scope": "current_process", "batch_definition": "One session.run invocation"},
                    "measurement_limit": "Point samples of host available RAM and API RSS; no peak or isolated allocation attribution."}

    def release_session(self):
        """Release ORT under its inference lock, preserving tokenizer and identities."""
        with self._lock:
            if self._session is None:
                return {"state": "already_released"}
            started = time.perf_counter()
            before = self.memory_sample()
            self._session = None
            gc.collect()
            after = self.memory_sample()
            self._release_measurement = {"state": "released", "before": before, "after": after,
                                         "rss_decrease_mib": round(before["process_rss_mib"] - after["process_rss_mib"], 2),
                                         "available_increase_mib": round(after["available_mib"] - before["available_mib"], 2),
                                         "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                         "next_reload_measurement": "pending"}
            return dict(self._release_measurement)

    def release_tokenizer(self):
        """Release the Rust tokenizer under the same lock used for encoding."""
        with self._lock:
            if self._tokenizer is None:
                return {"state": "already_released"}
            started, before = time.perf_counter(), self.memory_sample()
            self._tokenizer = None
            self._token_count_reference = dict(self._last_token_count) if self._last_token_count else None
            gc.collect()
            after = self.memory_sample()
            self._tokenizer_release_measurement = {"state": "released", "before": before, "after": after,
                "rss_decrease_mib": round(before["process_rss_mib"] - after["process_rss_mib"], 2),
                "available_increase_mib": round(after["available_mib"] - before["available_mib"], 2),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "next_reload_measurement": "pending",
                "count_parity": {"state": "pending_same_prefixed_input", "reference": self._token_count_reference}}
            return dict(self._tokenizer_release_measurement)

    def identity(self):
        """Artifact hashes and the actual mathematical contract identify a vector space."""
        with self._lock:
            if self._identity is None:
                paths = {"graph_sha256": self.model_path(), "tokenizer_sha256": self.directory / "tokenizer.json"}
                hashes = {}
                for name, path in paths.items():
                    if not path.is_file():
                        raise ApiError("embedding_not_provisioned", "Artefact E5 local absent.", 503)
                    with path.open("rb") as source:
                        hashes[name] = hashlib.file_digest(source, "sha256").hexdigest()
                manifest_path = self.settings.root / "config/artifacts.lock.json"
                if not manifest_path.is_file():
                    raise ApiError("embedding_identity_not_verified", "Manifest officiel d'identité E5 absent.", 503)
                artifacts = json.loads(manifest_path.read_text(encoding="utf-8")).get("groups", {}).get("e5", [])
                locked = {self.settings.path(artifact["target"]): artifact for artifact in artifacts if "target" in artifact}
                for name, path in paths.items():
                    artifact = locked.get(path.resolve())
                    if not artifact or artifact.get("sha256") != hashes[name]:
                        raise ApiError("embedding_identity_not_verified", "Hash E5 local incompatible avec le manifest officiel.", 503)
                graph_artifact = locked[paths["graph_sha256"].resolve()]
                if "qint8" not in graph_artifact.get("url", ""):
                    raise ApiError("embedding_identity_not_verified", "Le manifest ne démontre pas l'export INT8 retenu.", 503)
                identity = {**hashes, "model_id": self.settings.value("embedding", "model_id", "intfloat/multilingual-e5-small"),
                            "revision": graph_artifact.get("revision"),
                            "query_prefix": "query: ", "passage_prefix": "passage: ", "pooling": "attention_mask_mean",
                            "normalize_l2": True, "dimensions": 384, "precision": "int8", "provider": "CPUExecutionProvider"}
                identity["fingerprint"] = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                self._identity = identity
            return dict(self._identity)

    def tokenizer(self):
        with self._lock:
            if self._tokenizer is None:
                from tokenizers import Tokenizer
                path = self.directory / "tokenizer.json"
                if not path.is_file():
                    raise ApiError("embedding_not_provisioned", "Tokenizer E5 local absent.", 503)
                started, before = time.perf_counter(), self.memory_sample()
                self._tokenizer = Tokenizer.from_file(str(path))
                self._tokenizer.no_truncation()
                self._tokenizer.no_padding()
                self._tokenizer_load_count += 1
                self._tokenizer_load_measurement = {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "before": before, "after": self.memory_sample(), "reload_after_release": self._tokenizer_release_measurement is not None}
                if self._tokenizer_release_measurement:
                    self._tokenizer_release_measurement["next_reload_measurement"] = "observed"
            return self._tokenizer

    def count(self, text, passage=True):
        prefix = "passage: " if passage else "query: "
        with self._lock:
            count = len(self.tokenizer().encode(prefix + text).ids)
            self._record_token_count(prefix + text, count)
            return count

    def _record_token_count(self, prefixed_text, count):
        observed = {"prefixed_input_sha256": hashlib.sha256(prefixed_text.encode()).hexdigest(), "tokens": count}
        self._last_token_count = observed
        if self._tokenizer_release_measurement and self._token_count_reference:
            same_input = observed["prefixed_input_sha256"] == self._token_count_reference["prefixed_input_sha256"]
            self._tokenizer_release_measurement["count_parity"] = {"state": "observed" if same_input else "different_input_not_comparable",
                "reference": self._token_count_reference, "observed": observed,
                "counts_equal": count == self._token_count_reference["tokens"] if same_input else None}

    def model_path(self):
        configured = self.settings.value("embedding", "onnx_file", "model.onnx")
        path = self.directory / configured
        if not path.is_file():
            alternatives = [self.directory / "model_quantized.onnx", self.directory / "onnx/model_quantized.onnx"]
            path = next((candidate for candidate in alternatives if candidate.is_file()), path)
        if not path.is_file():
            raise ApiError("embedding_not_provisioned", "Graphe E5 INT8 local absent.", 503)
        return path

    def session(self):
        with self._lock:
            if self._session is None:
                self.identity()
                import psutil
                available_mib = psutil.virtual_memory().available / (1024 * 1024)
                reserve_mib = self.settings.value("resources", "host_available_min_mib", 1536)
                load_estimate_mib = self.settings.value("embedding", "initial_load_peak_estimate_mib", 768)
                if available_mib < reserve_mib + load_estimate_mib:
                    raise ApiError("embedding_admission_denied", "Réserve hôte insuffisante avant chargement E5 CPU.", 503,
                                   {"available_mib": round(available_mib, 2), "reserve_mib": reserve_mib, "load_estimate_mib": load_estimate_mib})
                import onnxruntime as ort
                options = ort.SessionOptions()
                options.intra_op_num_threads = self.settings.value("embedding", "intra_op_threads", 2)
                options.inter_op_num_threads = self.settings.value("embedding", "inter_op_threads", 1)
                options.add_session_config_entry("session.intra_op.allow_spinning", "0")
                options.add_session_config_entry("session.inter_op.allow_spinning", "0")
                started = time.perf_counter()
                before = self.memory_sample()
                self._session = ort.InferenceSession(str(self.model_path()), sess_options=options, providers=["CPUExecutionProvider"])
                if self._session.get_providers() != ["CPUExecutionProvider"]:
                    raise ApiError("invalid_embedding_provider", "E5 doit utiliser le provider CPU.", 503)
                self._load_count += 1
                self._load_measurement = {"elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                          "before": before, "after": self.memory_sample(), "providers": self._session.get_providers(),
                                          "reload_after_release": self._release_measurement is not None}
                if self._release_measurement:
                    self._release_measurement["next_reload_measurement"] = "observed"
            return self._session

    def embed(self, texts, passage=True):
        if not texts:
            return []
        prefix = "passage: " if passage else "query: "
        with self._lock:
            tokenizer = self.tokenizer()
            encodings = tokenizer.encode_batch([prefix + text for text in texts])
            for text, encoding in zip(texts, encodings, strict=True):
                self._record_token_count(prefix + text, len(encoding.ids))
            maximum = 448 if passage else 512
            if any(len(encoding.ids) > maximum for encoding in encodings):
                raise ApiError("embedding_input_too_long", "Entrée E5 trop longue ; découpage requis.")
            session = self.session()
            vectors = []
            for start in range(0, len(encodings), self.settings.value("embedding", "batch_size", 8)):
                batch = encodings[start:start + self.settings.value("embedding", "batch_size", 8)]
                width = max(len(encoding.ids) for encoding in batch)
                pad_id = tokenizer.token_to_id("<pad>")
                if pad_id is None:
                    raise ApiError("invalid_embedding_tokenizer", "Token de padding E5 absent.", 503)
                ids = np.full((len(batch), width), pad_id, dtype=np.int64)
                mask = np.zeros_like(ids)
                for index, encoding in enumerate(batch):
                    ids[index, :len(encoding.ids)] = encoding.ids
                    mask[index, :len(encoding.ids)] = 1
                feeds = {}
                for input_info in session.get_inputs():
                    if input_info.name == "input_ids":
                        feeds[input_info.name] = ids
                    elif input_info.name == "attention_mask":
                        feeds[input_info.name] = mask
                    elif input_info.name == "token_type_ids":
                        feeds[input_info.name] = np.zeros_like(ids)
                    else:
                        raise ApiError("unsupported_embedding_graph", "Entrée ONNX inattendue.", 503)
                self._inference["run_calls"] += 1
                self._inference["inputs_submitted"] += len(batch)
                try:
                    output = session.run(None, feeds)[0]
                except Exception:
                    self._inference["run_failed"] += 1
                    raise
                self._inference["run_completed"] += 1
                self._inference["inputs_completed"] += len(batch)
                self._inference["passage_inputs_completed" if passage else "query_inputs_completed"] += len(batch)
                if output.ndim == 3:
                    output = (output * mask[:, :, None]).sum(axis=1) / np.maximum(mask.sum(axis=1, keepdims=True), 1)
                elif output.ndim != 2:
                    raise ApiError("invalid_embedding_output", "Sortie ONNX invalide.", 503)
                norm = np.linalg.norm(output, axis=1, keepdims=True)
                if output.shape[1] != 384 or not np.isfinite(output).all() or np.any(norm <= 1e-12):
                    raise ApiError("invalid_embedding_output", "Vecteurs E5 invalides.", 503)
                vectors.extend((output / norm).astype(np.float32).tolist())
            return vectors
