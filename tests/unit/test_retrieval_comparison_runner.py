"""Real frozen SQLite/retrieval/context, explicitly fake model/vector boundaries."""
import asyncio
import hashlib
import json
import sqlite3
import ssl
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors, import_fixture
from test_api_storage import storage as storage

from services.api import comparison
from services.api.embedding_comparison import ComparisonVectorStore, FrozenDatabase
from services.api.errors import ApiError


class ControlledEmbedding(FakeEmbedding):
    def __init__(self, settings):
        self.loaded, self.calls = False, 0
    def identity(self):
        return {"fingerprint": "c" * 64, "model_id": "explicit_test_encoder"}
    def lifecycle(self):
        return {"session_loaded": self.loaded, "calls": self.calls}
    def embed(self, texts, passage=True):
        self.loaded, self.calls = True, self.calls + 1
        return super().embed(texts, passage)
    def release_session(self):
        self.loaded = False
    def release_tokenizer(self):
        pass


class ControlledTokenizer(FakeLlmTokenizer):
    def __init__(self, settings):
        pass
    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)
    def identity(self):
        return {"fingerprint": "explicit_test_template"}
    def release_tokenizer(self):
        pass


def frozen_inputs(storage, monkeypatch):
    imported, _ = import_fixture(storage, text="CCU-21 : tension nominale 72 V. 😀")
    settings, db, vectors, _ = storage
    export = settings.root / "export.sqlite3"
    with db.connect() as source, sqlite3.connect(export) as target:
        source.backup(target)
    block = db.one("SELECT * FROM blocks")
    version = db.version(imported["version_id"])
    generation = block["generation_id"]
    span = {"block_id": block["id"], "version_id": version["id"], "generation_id": generation,
        "extraction_revision_id": block["extraction_revision_id"], "source_text_hash": block["source_text_hash"], "page_index": 0,
        "offset_unit": "unicode_code_point", "start_offset": 0, "end_offset": len(block["text"]), "text": block["text"]}
    base = {"id": "dev-1", "split": "development", "category": "technical", "language": "fr", "question": "Quelle tension CCU-21 ?",
        "answerable": True, "expected_units": [{"required_texts": [block["text"]]}]}
    resolved = {**base, "annotation_state": "RESOLVED", "scope_resolved": {"kind": "documents", "documentIds": [imported["document_id"]]},
        "versions_snapshot": [{"document_id": imported["document_id"], "version_id": version["id"], "generation_id": generation,
            "extraction_revision_id": block["extraction_revision_id"], "file_sha256": version["sha256"]}],
        "expected_units": [{**base["expected_units"][0], "resolved_spans": [span]}]}
    source_path, dataset_path = settings.root / "source.json", settings.root / "resolved.json"
    source_path.write_text(json.dumps({"questions": [base]}, ensure_ascii=False), encoding="utf-8")
    dataset_path.write_text(json.dumps({"questions": [resolved]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(comparison.Settings, "load", lambda profile: settings)
    monkeypatch.setattr(comparison, "EmbeddingService", ControlledEmbedding)
    monkeypatch.setattr(comparison, "GraniteEmbedding", ControlledEmbedding)
    monkeypatch.setattr(comparison, "LlmTokenizer", ControlledTokenizer)
    async def quiet(settings):
        pass
    monkeypatch.setattr(comparison, "assert_quiet", quiet)
    class Store(FakeVectors):
        created = []
        def __init__(self, settings, embedding=None, prefix=None):
            super().__init__()
            self.collection = "diag_gr97_" + "c" * 16 if embedding else "baseline_real_identity"
            self.closed, self.ensure_calls = False, 0
            if not embedding:
                self.points = deepcopy(vectors.points)
            self.created.append(self)
        async def ensure_collection(self):
            self.ensure_calls += 1
        async def request(self, method, path):
            assert method == "GET"
            return {"config": {"explicit_test_store": True}, "points_count": len(self.points)}
        async def close(self):
            self.closed = True
    monkeypatch.setattr(comparison, "QdrantStore", Store)
    monkeypatch.setattr(comparison, "ComparisonVectorStore", Store)
    args = SimpleNamespace(profile=None, snapshot=export, snapshot_sha256=hashlib.sha256(export.read_bytes()).hexdigest(),
        source_dataset=source_path, dataset=dataset_path, model="e5", build_candidate=False, collection_prefix="diag_gr97", qdrant_collections_dir=None)
    return args, Store, resolved


def test_retrieval_comparison_uses_frozen_store_actual_selector_and_never_marks_partial_pass(storage, monkeypatch):
    args, stores, _ = frozen_inputs(storage, monkeypatch)
    before = args.snapshot.read_bytes()
    baseline = asyncio.run(comparison.run(args))
    assert baseline["status"] == "INCOMPLETE" and baseline["failure"] is None
    assert baseline["metrics"]["evidence_coverage_at_context"]["rate"] == 1
    assert baseline["metrics"]["evaluated_questions"] == 1
    assert baseline["questions"][0]["response"]["model_called"] is False
    assert stores.created[0].closed and stores.created[0].ensure_calls == 0
    args.model, args.build_candidate = "granite", True
    candidate = asyncio.run(comparison.run(args))
    assert candidate["status"] == "INCOMPLETE" and candidate["indexing"]["chunks"] == 1
    assert candidate["metrics"]["recall_at_10"]["rate"] == 1
    assert stores.created[1].closed and stores.created[1].ensure_calls == 1
    assert stores.created[1].collection != stores.created[0].collection
    paired = comparison.compare_reports(baseline, candidate)
    assert paired["complete_arms"] is False and paired["automatic_winner"] is None
    assert all(value == 0 for value in paired["delta_granite_minus_e5"].values())
    candidate["identity"]["chunks_identity_sha256"] = "changed"
    with pytest.raises(ValueError, match="inputs/source/selector"):
        comparison.compare_reports(baseline, candidate)
    assert args.snapshot.read_bytes() == before
    assert not any(Path(str(args.snapshot) + suffix).exists() for suffix in ["-wal", "-shm", "-journal"])


def test_retrieval_comparison_preserves_identity_failure_before_any_engine(storage, monkeypatch):
    args, stores, _ = frozen_inputs(storage, monkeypatch)
    args.model, args.build_candidate = "granite", True
    class Unavailable(ControlledEmbedding):
        def identity(self):
            raise ApiError("comparison_not_provisioned", "Controlled missing artifact", 503)
        def embed(self, *args, **kwargs):
            pytest.fail("No encoder may run after artifact identity failure")
    monkeypatch.setattr(comparison, "GraniteEmbedding", Unavailable)
    report = asyncio.run(comparison.run(args))
    assert report["status"] == "FAIL" and report["failure"] == {"code": "comparison_not_provisioned", "phase": "artifact_identity"}
    assert report["questions"] == [] and not stores.created
    assert report["embedding_lifecycle"]["calls"] == 0


def test_retrieval_comparison_refuses_changed_gold_source_before_model(storage, monkeypatch):
    args, _, question = frozen_inputs(storage, monkeypatch)
    db = FrozenDatabase(args.snapshot, args.snapshot_sha256)
    resolver = comparison.ScopeResolver(db)
    bad = deepcopy(question)
    bad["expected_units"][0]["resolved_spans"][0]["source_text_hash"] = "0" * 64
    with pytest.raises(ValueError, match="proof span/hash"):
        comparison.corpus_chunks(db, resolver, [bad])
    bad = deepcopy(question)
    bad["versions_snapshot"][0]["extraction_revision_id"] = "changed"
    with pytest.raises(ValueError, match="extraction revision"):
        comparison.corpus_chunks(db, resolver, [bad])
    args.build_candidate = True
    with pytest.raises(ValueError, match="strictly read-only"):
        asyncio.run(comparison.run(args))


def test_retrieval_comparison_does_not_ignore_reserve_violation_at_final_sample(storage, monkeypatch):
    from contextlib import contextmanager
    args, _, _ = frozen_inputs(storage, monkeypatch)
    class FinalViolation(comparison.ResourceSamples):
        @contextmanager
        def running(self):
            yield self
            self.violation.set()
    monkeypatch.setattr(comparison, "ResourceSamples", FinalViolation)
    report = asyncio.run(comparison.run(args))
    assert report["status"] == "FAIL" and report["failure"] == {"code": "comparison_resource_reserve", "phase": "final_resource_sample"}


def test_retrieval_comparison_collection_names_are_dedicated_and_bounded(tmp_path):
    from services.api.settings import Settings
    settings = Settings(tmp_path)
    embedding = ControlledEmbedding(settings)
    for prefix in ["diag_gr97", "diag_gr97_abcdefgh"]:
        store = ComparisonVectorStore(settings, embedding, prefix)
        assert store.collection.startswith("diag_gr97_") and len(store.collection) <= 35
        assert store.collection != settings.value("qdrant", "collection", "pdf_chunks_e5small_v1")
        asyncio.run(store.close())
    for prefix in ["pdf_chunks_e5small_v1", "qualification_granite_dev_v1", "diag_gr97_toolongxx", "../diag_gr97"]:
        with pytest.raises(ApiError, match="Préfixe court"):
            ComparisonVectorStore(settings, embedding, prefix)


@pytest.mark.parametrize("api_active,llm_resident", [(True, False), (False, True), (False, False)])
def test_retrieval_comparison_checks_stopped_api_and_unloaded_llm_without_mutation(tmp_path, monkeypatch, api_active, llm_resident):
    from services.api.settings import Settings
    settings = Settings(tmp_path)
    requests = []
    def handler(request):
        requests.append((request.method, request.url.path))
        assert request.method == "GET"
        if request.url.path.endswith("/health"):
            if not api_active:
                raise httpx.ConnectError("Controlled stopped API", request=request)
            return httpx.Response(200, json={"alive": True})
        return httpx.Response(200, json={"models": [{"name": "controlled"}] if llm_resident else []})
    actual_client = httpx.AsyncClient
    monkeypatch.setattr(comparison.httpx, "AsyncClient", lambda **kwargs: actual_client(**kwargs, transport=httpx.MockTransport(handler)))
    # Double explicite du port : API arrêtée = refus de connexion (ECONNREFUSED), sinon un service écoute.
    async def port_open(origin, timeout=comparison.API_PORT_PROBE_TIMEOUT_SECONDS):
        return api_active
    monkeypatch.setattr(comparison, "api_port_open", port_open)
    if api_active or llm_resident:
        with pytest.raises(ApiError):
            asyncio.run(comparison.assert_quiet(settings))
    else:
        asyncio.run(comparison.assert_quiet(settings))
    assert all(method == "GET" for method, path in requests)


def test_retrieval_comparison_quiet_check_reaches_the_https_api_in_production(tmp_path, monkeypatch):
    """C16 : en production l'API écoute en HTTPS ; la sonde vérifie le certificat du profil, comme le superviseur."""
    from services.api.settings import Settings
    settings = Settings(tmp_path, {"app": {"port": 8790}, "security": {"environment": "production", "tls_cert_file": "certs/api.pem", "tls_key_file": "certs/api.key"}})
    urls, verifies, cafiles, context = [], [], [], object()
    monkeypatch.setattr(comparison.ssl, "create_default_context", lambda cafile=None: cafiles.append(cafile) or context)
    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"status": "alive"} if request.url.path.endswith("/health") else {"models": []})
    actual_client = httpx.AsyncClient
    def client(**kwargs):
        # Double explicite : transport simulé, aucune connexion TLS ouverte.
        verifies.append(kwargs.pop("verify", True))
        return actual_client(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(comparison.httpx, "AsyncClient", client)
    probed = []
    async def port_open(origin, timeout=comparison.API_PORT_PROBE_TIMEOUT_SECONDS):
        probed.append(origin)
        return True
    monkeypatch.setattr(comparison, "api_port_open", port_open)
    with pytest.raises(ApiError, match="Arrêter l'API"):
        asyncio.run(comparison.assert_quiet(settings))
    assert probed == ["https://127.0.0.1:8790"]
    assert urls == ["https://127.0.0.1:8790/api/v1/health"]
    assert cafiles == [str((tmp_path / "certs/api.pem").resolve())] and verifies[0] is context


@pytest.mark.parametrize("failure,expected", [("tls", "comparison_api_tls_unverified"), ("connect", "comparison_api_unverified"),
                                              ("timeout", "comparison_api_unverified"), ("eof", "comparison_api_unverified"),
                                              ("zero_return", "comparison_api_unverified")])
def test_retrieval_comparison_quiet_check_never_takes_an_unidentified_listener_for_a_stopped_api(tmp_path, monkeypatch, failure, expected):
    """Revue A1 : seul un refus de connexion prouve l'arrêt ; un service qui écoute sans répondre à la sonde arrête le comparatif."""
    from services.api.settings import Settings
    settings = Settings(tmp_path, {"app": {"port": 8790}, "security": {"environment": "production", "tls_cert_file": "certs/api.pem", "tls_key_file": "certs/api.key"}})
    monkeypatch.setattr(comparison.ssl, "create_default_context", lambda cafile=None: object())
    def handler(request):
        if not request.url.path.endswith("/health"):
            return httpx.Response(200, json={"models": []})
        if failure == "tls":
            # Chaîne levée par httpx quand le certificat servi n'est pas celui du profil (essai réel : test_api_tls.py).
            try:
                raise ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
            except ssl.SSLError as error:
                raise httpx.ConnectError(str(error), request=request) from error
        if failure == "connect":
            raise httpx.ConnectError("Controlled connection reset after accept", request=request)
        if failure in {"eof", "zero_return"}:
            # Flux fermé par le service avant la fin de la négociation TLS : aucun certificat n'a été vérifié
            # (chaîne réelle ConnectError -> EndOfStream -> SSLEOFError : test_api_tls.py).
            ended = ssl.SSLEOFError(8, "EOF occurred in violation of protocol") if failure == "eof" else ssl.SSLZeroReturnError(6, "TLS/SSL connection has been closed (EOF)")
            try:
                raise ended
            except ssl.SSLError as error:
                raise httpx.ConnectError(str(error), request=request) from error
        raise httpx.ReadTimeout("Controlled silent listener", request=request)
    actual_client = httpx.AsyncClient
    monkeypatch.setattr(comparison.httpx, "AsyncClient", lambda **kwargs: actual_client(
        **{key: value for key, value in kwargs.items() if key != "verify"}, transport=httpx.MockTransport(handler)))
    async def port_open(origin, timeout=comparison.API_PORT_PROBE_TIMEOUT_SECONDS):
        return True
    monkeypatch.setattr(comparison, "api_port_open", port_open)
    with pytest.raises(ApiError) as refused:
        asyncio.run(comparison.assert_quiet(settings))
    assert refused.value.code == expected and refused.value.status == 409


def test_retrieval_comparison_port_probe_reports_only_a_real_refusal_as_stopped():
    """ECONNREFUSED réel sur loopback : port fermé = API arrêtée ; port en écoute = service présent."""
    import socket
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert asyncio.run(comparison.api_port_open(f"https://127.0.0.1:{port}")) is True
    assert asyncio.run(comparison.api_port_open(f"https://127.0.0.1:{port}")) is False


def test_retrieval_comparison_quiet_check_names_the_profile_certificate_when_it_cannot_be_read(tmp_path):
    """Revue J5 : en production, un service écoute (socket réelle) et `security.tls_cert_file` désigne un fichier absent.

    Le comparatif reste refusé, par une erreur 409 qui nomme la clé du profil, au lieu d'un FileNotFoundError brut.
    """
    import socket

    from services.api.settings import Settings
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        settings = Settings(tmp_path, {"app": {"port": port}, "security": {"environment": "production", "tls_cert_file": "certs/absent.pem",
                                                                           "tls_key_file": "certs/absent.key"}})
        with pytest.raises(ApiError) as refused:
            asyncio.run(comparison.assert_quiet(settings))
    assert (refused.value.code, refused.value.status) == ("comparison_api_certificate_unreadable", 409)
    assert "security.tls_cert_file" in refused.value.message
    assert refused.value.details == {"tls_cert_file": str((tmp_path / "certs/absent.pem").resolve()), "reason": "FileNotFoundError"}
    assert isinstance(refused.value.__cause__, FileNotFoundError)


def test_retrieval_comparison_percentiles_and_storage_use_actual_files(tmp_path):
    observed = comparison.durations([1, 2, 3, 4])
    assert observed["p50_ms"] == 2.5 and observed["p95_ms"] == pytest.approx(3.85)
    directory = tmp_path / "diag_gr97_abc"
    directory.mkdir()
    (directory / "segment").write_bytes(b"abc")
    assert comparison.storage_measurement(tmp_path, directory.name)["bytes"] == 3
    assert comparison.storage_measurement(None, directory.name)["status"] == "NOT_MEASURED"


def test_retrieval_comparison_cli_keeps_failed_preflight_as_new_report(tmp_path, monkeypatch):
    import sys
    output = tmp_path / "RAG_Local_Agents/reports/backend/failure.json"
    monkeypatch.setattr(comparison, "__file__", str(tmp_path / "services/api/comparison.py"))
    async def failed(args):
        raise ApiError("comparison_not_provisioned", "Controlled unavailable candidate", 503)
    monkeypatch.setattr(comparison, "run", failed)
    monkeypatch.setattr(sys, "argv", ["comparison", "--snapshot", str(tmp_path / "export.sqlite3"), "--snapshot-sha256", "0" * 64,
        "--dataset", str(tmp_path / "resolved.json"), "--source-dataset", str(tmp_path / "development.json"), "--model", "granite", "--output", str(output)])
    assert comparison.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL" and report["failure"]["code"] == "comparison_not_provisioned"
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        comparison.main()
    assert output.read_bytes() == before
