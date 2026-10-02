import hashlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
import pytest
import yaml

from services.runtime import cli
from services.runtime.artifacts import ROOT, file_hash, write_json_atomic
from tests.unit.test_runtime_accelerator import jetson_libraries  # noqa: F401  (fixture réutilisée)


def _blob(store, data: bytes, media: str) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    (store / "blobs").mkdir(parents=True, exist_ok=True)
    (store / "blobs" / f"sha256-{digest}").write_bytes(data)
    return {"mediaType": media, "digest": "sha256:" + digest, "size": len(data)}


def _model(store, name: str, weights: bytes) -> dict:
    config = _blob(store, json.dumps({"model_format": "gguf", "name": name}).encode(), "application/vnd.docker.container.image.v1+json")
    layers = [_blob(store, weights, "application/vnd.ollama.image.model"),
              _blob(store, b"Apache License\nVersion 2.0", "application/vnd.ollama.image.license")]
    model, _, tag = name.partition(":")
    path = store / "manifests/registry.ollama.ai/library" / model / tag
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schemaVersion": 2, "config": config, "layers": layers}), encoding="utf-8")
    return {"manifest_sha256": file_hash(path), "config": config, "layers": layers}


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "ollama"
    lock = {"schema_version": 1, "models": {"qwen3.5:4b": _model(root, "qwen3.5:4b", b"GGUF" + b"\1" * 4096),
                                            "qwen3.5:4b-text": _model(root, "qwen3.5:4b-text", b"GGUF" + b"\2" * 2048)}}
    path = tmp_path / "models.lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")
    return root, path


def _weights(root, name):
    manifest = json.loads(root.joinpath("manifests/registry.ollama.ai/library", *name.split(":")).read_text(encoding="utf-8"))
    return root / "blobs" / ("sha256-" + manifest["layers"][0]["digest"].split(":")[1])


def test_lock_conformity_and_offline_presence(store):
    root, lock = store
    result = cli.model_lock_conformity(lock, root)
    assert result["status"] == "conform"
    assert {name: item["status"] for name, item in result["models"].items()} == {"qwen3.5:4b": "conform", "qwen3.5:4b-text": "conform"}
    files = cli.ollama_store_files("qwen3.5:4b-text", root)
    assert files["status"] == "present" and files["blobs"] == 3 and not files["issues"]
    assert cli.llm_model_diagnosis(files, {"status": "service_unavailable"})["status"] == "service_unavailable_model_files_present"
    assert cli.llm_model_diagnosis(files, {"name": "qwen3.5:4b-text"})["status"] == "available"
    assert cli.llm_model_diagnosis(files, {"status": "absent"})["status"] == "service_does_not_list_local_model"


def test_absent_manifest_is_model_absent_not_service_failure(store):
    root, lock = store
    root.joinpath("manifests/registry.ollama.ai/library/qwen3.5/4b-text").unlink()
    files = cli.ollama_store_files("qwen3.5:4b-text", root)
    assert files["status"] == "absent"
    assert cli.llm_model_diagnosis(files, {"status": "service_unavailable"})["status"] == "model_absent"
    result = cli.model_lock_conformity(lock, root)
    assert result["status"] == "nonconform" and result["models"]["qwen3.5:4b-text"]["status"] == "absent"
    assert result["models"]["qwen3.5:4b"]["status"] == "conform"


def test_truncated_or_altered_blobs_are_nonconform(store):
    root, lock = store
    weights = _weights(root, "qwen3.5:4b-text")
    weights.write_bytes(weights.read_bytes()[:-1])
    files = cli.ollama_store_files("qwen3.5:4b-text", root)
    assert files["status"] == "incomplete" and files["issues"][0]["issue"] == "size_mismatch"
    assert cli.llm_model_diagnosis(files, {"status": "service_unavailable"})["status"] == "model_files_incomplete"
    weights.write_bytes(b"XXXX" + b"\2" * 2048)
    # Au-delà du seuil, seule la taille est contrôlée : limite explicite, rehachage complet sur demande.
    assert cli.model_lock_conformity(lock, root, hash_limit_bytes=1024)["models"]["qwen3.5:4b-text"]["status"] == "conform"
    full = cli.model_lock_conformity(lock, root, hash_limit_bytes=None)["models"]["qwen3.5:4b-text"]
    assert full["issues"] == [{"digest": files["entries"][1]["digest"], "issue": "blob_hash_mismatch"}]


def test_manifest_differing_from_lock_is_reported(store):
    root, lock = store
    data = json.loads(lock.read_text(encoding="utf-8"))
    data["models"]["qwen3.5:4b"]["manifest_sha256"] = "0" * 64
    data["models"]["qwen3.5:4b"]["layers"] = data["models"]["qwen3.5:4b"]["layers"][:1]
    lock.write_text(json.dumps(data), encoding="utf-8")
    issues = [item["issue"] for item in cli.model_lock_conformity(lock, root)["models"]["qwen3.5:4b"]["issues"]]
    assert issues == ["manifest_digest_mismatch", "layers_differ_from_lock"]


def test_versioned_lock_matches_profile_and_local_store_when_provisioned():
    lock = json.loads((ROOT / "config/models.lock.json").read_text(encoding="utf-8"))
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    assert {profile["llm"]["model"], profile["llm"]["source_model"]} <= set(lock["models"])
    derived = lock["models"]["qwen3.5:4b-text"]
    assert derived["transformation"]["removed_tensor_count"] == 393
    assert derived["transformation"]["source_model_layer_digest"] == lock["models"]["qwen3.5:4b"]["layers"][0]["digest"]
    if not (cli.OLLAMA_MODELS_DIR / lock["models"]["qwen3.5:4b-text"]["manifest_path"]).is_file():
        pytest.skip("Stockage Ollama local non provisionné")
    result = cli.model_lock_conformity()
    assert result["status"] == "conform", result


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def doctor_profile(tmp_path, monkeypatch, store):
    root, lock = store
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    monkeypatch.setattr(cli, "OLLAMA_MODELS_DIR", root)
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    monkeypatch.setattr(cli, "native_paths", lambda: (_ for _ in ()).throw(FileNotFoundError("double de test")))
    monkeypatch.setattr(cli.shutil, "which", lambda name, *args, **kwargs: None)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["app"]["data_dir"] = str(tmp_path / "données")
    profile["app"]["port"] = _free_port()
    profile["qdrant"]["url"] = f"http://127.0.0.1:{_free_port()}"
    profile["llm"]["base_url"] = f"http://127.0.0.1:{_free_port()}"
    path = tmp_path / "profil.yaml"
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    me = psutil.Process()
    write_json_atomic(tmp_path / "données/control/runtime.json", {"status": "running", "services": {},
        "profile_sha256": file_hash(path), "supervisor": {"pid": me.pid, "created_at": 0, "executable": me.exe()}})
    return path, profile, root


def test_doctor_separates_absent_model_from_stopped_service(doctor_profile):
    path, profile, root = doctor_profile
    result = cli.doctor(path)
    checks = result["checks"]
    assert result["runtime"]["status"] == "stale" and checks["profile_application"]["status"] == "stale_runtime_state"
    assert {name: item["state"] for name, item in checks["ports"].items()} == {"app": "free", "qdrant": "free", "ollama": "free"}
    assert checks["llm_model"]["status"] == "service_unavailable"
    assert checks["llm_model_diagnosis"]["status"] == "service_unavailable_model_files_present"
    assert checks["model_lock"]["status"] == "conform" and checks["model_lock"]["profile_models_locked"] is True
    assert checks["index_consistency"] == {"status": "api_unavailable"}
    cold = checks["cold_admission"]["generation"]
    resources = profile["resources"]
    assert cold["required_available_mib"] == max(resources["admit_heavy_min_available_mib"],
                                                 resources["initial_llm_load_peak_estimate_mib"] + resources["host_available_min_mib"])
    assert cold["margin_mib"] == round(cold["available_mib"] - cold["required_available_mib"], 2)
    assert cold["admissible_now"] is (cold["margin_mib"] >= 0)
    root.joinpath("manifests/registry.ollama.ai/library/qwen3.5/4b-text").unlink()
    checks = cli.doctor(path)["checks"]
    assert checks["llm_model_diagnosis"]["status"] == "model_absent"
    assert checks["model_lock"]["models"]["qwen3.5:4b-text"]["status"] == "absent"


def test_doctor_reports_index_consistency_not_exposed_by_running_api(doctor_profile):
    path, profile, _ = doctor_profile

    class Api(BaseHTTPRequestHandler):
        def do_GET(self):
            body = {"/api/v1/health": {"status": "ok"}, "/api/v1/diagnostics": {"python": "3.12", "resources": {}}}.get(self.path)
            payload = json.dumps(body or {"code": "not_found"}).encode()
            self.send_response(200 if body else 404)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", profile["app"]["port"]), Api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        checks = cli.doctor(path)["checks"]
    finally:
        server.shutdown()
        server.server_close()
    assert checks["index_consistency"]["status"] == "not_exposed"
    assert checks["index_consistency"]["diagnostics_keys"] == ["python", "resources"]
    assert checks["ports"]["app"]["state"] == "foreign"


def test_structurally_invalid_manifest_is_reported_not_raised(store):
    root, lock = store
    path = root / "manifests/registry.ollama.ai/library/qwen3.5/4b-text"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["layers"] = ["sha256:" + "0" * 64]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    files = cli.ollama_store_files("qwen3.5:4b-text", root)
    assert files["status"] == "invalid_manifest" and files["reason"] == "TypeError"


@pytest.fixture
def pull_service(tmp_path, monkeypatch, store):
    """pull-model sans Ollama réel : service, registre et dérivation sont des doubles ; stockage, verrou et racine du
    programme sont temporaires (aucune écriture sous .runtime). Le profil livré est lu tel quel."""
    import httpx

    root, lock = store
    program = tmp_path / "programme"
    monkeypatch.setattr(cli, "ROOT", program)
    monkeypatch.setattr(cli, "OLLAMA_MODELS_DIR", root)
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    monkeypatch.setattr(cli, "native_paths", lambda: {"ollama": program / "ollama"})
    monkeypatch.setattr(cli, "environment", lambda *args: {})
    monkeypatch.setattr(cli, "wait_http", lambda *args, **kwargs: {"version": "0.35.0"})
    monkeypatch.setattr(cli, "send_owned_console_interrupt", lambda *args: None)

    class Child:
        def wait(self, timeout):
            return 0

    class Job:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def launch(self, *args, **kwargs):
            return Child()

    monkeypatch.setattr(cli, "ProcessJob", Job)
    pulls = []

    def answer(request):
        if request.url.path == "/api/pull":
            pulls.append(json.loads(request.content))
            return httpx.Response(200, content=b'{"status": "pulling manifest"}\n{"status": "success"}\n')
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b", "digest": "source",
                                                         "details": {"quantization_level": "Q4_K_M"}}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"quantization_level": "Q4_K_M"}, "model_info": {}})
        raise AssertionError(f"route inattendue : {request.url.path}")

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(answer)))
    derived = {"model": {"name": "qwen3.5:4b-text", "digest": "derive"}}
    monkeypatch.setattr(cli, "_derive_text_model", lambda *args: derived)
    return root, lock, pulls, derived


def test_pull_model_returns_the_model_when_the_store_matches_the_lock(pull_service):
    root, lock, pulls, derived = pull_service
    assert cli.pull_model(ROOT / "config/local16.yaml") == derived["model"]
    assert pulls == [{"model": "qwen3.5:4b", "stream": True}]


@pytest.mark.parametrize("alteration", ["derived_manifest", "source_absent"])
def test_pull_model_fails_when_the_pulled_or_derived_store_differs_from_the_lock(pull_service, alteration):
    # Avant correction, pull-model rendait le modèle quel que soit le stockage ; seul doctor signalait ensuite l'écart.
    root, lock, pulls, _ = pull_service
    library = root / "manifests/registry.ollama.ai/library/qwen3.5"
    if alteration == "derived_manifest":
        manifest = json.loads((library / "4b-text").read_text(encoding="utf-8"))
        manifest["layers"] = manifest["layers"][:1]
        (library / "4b-text").write_text(json.dumps(manifest), encoding="utf-8")
        detail = "qwen3.5:4b-text (layers_differ_from_lock, manifest_digest_mismatch)"
    else:
        (library / "4b").unlink()
        detail = "qwen3.5:4b (absent)"
    with pytest.raises(RuntimeError) as failure:
        cli.pull_model(ROOT / "config/local16.yaml")
    assert str(failure.value) == (f"Stockage Ollama différent du verrou {lock} après pull-model : {detail}. "
                                  "Contrôle limité aux modèles du profil, avec les critères de doctor ; les fichiers du "
                                  "stockage sont conservés pour diagnostic.")
    assert pulls == [{"model": "qwen3.5:4b", "stream": True}]


def test_pull_model_fails_when_the_profile_names_a_model_missing_from_the_lock(pull_service, monkeypatch):
    root, lock, _, _ = pull_service
    data = json.loads(lock.read_text(encoding="utf-8"))
    del data["models"]["qwen3.5:4b-text"]
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError) as failure:
        cli.pull_model(ROOT / "config/local16.yaml")
    assert str(failure.value) == (f"Stockage Ollama différent du verrou {lock} après pull-model : modèle du profil absent "
                                  "du verrou (qwen3.5:4b-text). Contrôle limité aux modèles du profil, avec les critères "
                                  "de doctor ; les fichiers du stockage sont conservés pour diagnostic.")


@pytest.fixture
def profile_without_derivation(tmp_path):
    """Profil livré dont le modèle servi est le modèle source (model == source_model) : aucune dérivation texte seul."""
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["llm"]["model"] = profile["llm"]["source_model"]
    path = tmp_path / "profil-sans-derivation.yaml"
    path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("alteration", ["derived_absent", "derived_manifest"])
def test_pull_model_checks_only_the_models_of_its_profile(pull_service, profile_without_derivation, alteration):
    # Le dérivé texte seul du verrou ne concerne pas ce profil : son absence ou son écart ne fait plus échouer pull-model
    # (avant correction, tout le verrou était contrôlé).
    root, lock, pulls, _ = pull_service
    library = root / "manifests/registry.ollama.ai/library/qwen3.5"
    if alteration == "derived_absent":
        (library / "4b-text").unlink()
    else:
        manifest = json.loads((library / "4b-text").read_text(encoding="utf-8"))
        manifest["layers"] = manifest["layers"][:1]
        (library / "4b-text").write_text(json.dumps(manifest), encoding="utf-8")
    assert cli.pull_model(profile_without_derivation) == {"name": "qwen3.5:4b", "digest": "source",
                                                          "details": {"quantization_level": "Q4_K_M"}}
    assert pulls == [{"model": "qwen3.5:4b", "stream": True}]


def test_pull_model_without_derivation_still_fails_when_its_own_model_differs_from_the_lock(pull_service,
                                                                                          profile_without_derivation):
    root, lock, _, _ = pull_service
    library = root / "manifests/registry.ollama.ai/library/qwen3.5"
    (library / "4b").unlink()
    (library / "4b-text").unlink()
    with pytest.raises(RuntimeError) as failure:
        cli.pull_model(profile_without_derivation)
    # Seul le modèle du profil est cité ; le dérivé absent n'est pas un écart de ce profil.
    assert str(failure.value) == (f"Stockage Ollama différent du verrou {lock} après pull-model : qwen3.5:4b (absent). "
                                  "Contrôle limité aux modèles du profil, avec les critères de doctor ; les fichiers du "
                                  "stockage sont conservés pour diagnostic.")


# --- Contrôle « calcul » (D01.4, W024, W025) ---------------------------------------------------------------------------

def _lock_with_sizes() -> dict:
    """Verrou de test (test_runtime_accelerator.LOCK) avec les tailles réelles du complément jetpack5."""
    import copy

    from tests.unit.test_runtime_accelerator import LOCK

    lock = copy.deepcopy(LOCK)
    lock["groups"]["ollama-gpu"][0].update(size=297201571, extracted_size=864658584)
    return lock


@pytest.fixture
def program(jetson_libraries, monkeypatch):  # noqa: F811
    """Racine de programme temporaire (verrou, manifeste, découverte de provision) et Jetson R35 simulé."""
    from tests.unit.test_runtime_accelerator import JETSON

    root, manifest = jetson_libraries
    (root / "config").mkdir(exist_ok=True)
    (root / "config/artifacts.lock.json").write_text(json.dumps(_lock_with_sizes()), encoding="utf-8")
    write_json_atomic(root / ".runtime/manifests/artifacts.json", manifest)
    monkeypatch.setattr(cli, "ROOT", root)
    monkeypatch.setattr(cli, "host_signals", lambda: dict(JETSON, nvidia_kernel_driver="NVRM", gpu_nodes={},
                                                          windows_nvcuda=None))
    return root, manifest


PROFILE = {"llm": {"model": "qwen3.5:4b-text", "accelerator": "auto", "keep_alive": "10m"}}


def _recorded(log: str, utc: str, mode: str, reason: str) -> dict:
    from services.runtime.accelerator import device_variant, parse_discovery

    discovery = parse_discovery(log)
    device = (discovery["devices"] or [None])[0]
    return {"requested": "auto", "requested_source": "profile", "mode": mode, "reason": reason, "device": device,
            "variant": device_variant(device), "qualified": mode == "gpu", "discovery": discovery, "utc": utc}


def _provision_record(root, log: str, utc: str) -> None:
    from services.runtime.accelerator import DISCOVERY_MANIFEST, discovery_record, parse_discovery

    write_json_atomic(root / DISCOVERY_MANIFEST, discovery_record(
        parse_discovery(log), source="provision", method="probe", log=".runtime/provision-service/ollama-probe.log",
        version="0.35.0", signals={"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5"}, utc=utc))


def test_a_running_instance_keeps_its_own_discovery_and_reports_usage_and_fallback(program):
    from tests.unit.test_runtime_accelerator import JETSON_BASE_ONLY, JETSON_JETPACK5

    root, _ = program
    # Sonde de provisionnement plus récente que l'instance : l'instance garde la découverte qui a fixé son mode.
    _provision_record(root, JETSON_BASE_ONLY, "2026-10-01T23:00:00+00:00")
    runtime = {"status": "running", "instance_id": "instance-gpu",
               "accelerator": _recorded(JETSON_JETPACK5, "2026-10-01T21:49:30+00:00", "gpu", "gpu_discovered")}
    models = [{"name": "qwen3.5:4b-text", "digest": "d", "size": 3107811491, "size_vram": 3107811491}]
    check = cli.accelerator_check(PROFILE, runtime, models, {"llm_accelerator": {"fallback": None}})
    assert check["state"] == "gpu_in_use" and check["running"] is True
    assert (check["discovery"]["source"], check["discovery"]["instance_id"]) == ("runtime", "instance-gpu")
    assert check["usage"] == [{"model": "qwen3.5:4b-text", "size": 3107811491, "size_vram": 3107811491,
                               "processor": "100% GPU"}]
    fallback = {"utc": "2026-10-01T22:14:05+00:00", "http_status": 500, "error": "CUDA error"}
    assert cli.accelerator_check(PROFILE, runtime, models, {"llm_accelerator": {"fallback": fallback}})["state"] == "gpu_fallback"
    assert cli.accelerator_check(PROFILE, runtime, [], None)["state"] == "gpu_ready"
    assert cli.accelerator_check(PROFILE, runtime, None, None)["usage"] is None


def test_without_a_running_instance_the_most_recent_discovery_sets_the_next_start(program):
    from tests.unit.test_runtime_accelerator import JETSON_BASE_ONLY, JETSON_JETPACK5

    root, _ = program
    stopped = {"status": "stopped", "instance_id": "ancienne",
               "accelerator": _recorded(JETSON_BASE_ONLY, "2026-10-01T18:54:12+00:00", "cpu", "no_gpu_discovered")}
    _provision_record(root, JETSON_JETPACK5, "2026-10-01T22:00:00+00:00")
    check = cli.accelerator_check(PROFILE, stopped, None, None)
    assert (check["discovery"]["source"], check["state"], check["mode"]) == ("provision", "gpu_pending", "gpu")
    # Instance arrêtée plus récente que la sonde : sa découverte (aucun GPU, complément installé) fait foi.
    stopped["accelerator"]["utc"] = "2026-10-01T23:30:00+00:00"
    check = cli.accelerator_check(PROFILE, stopped, None, None)
    assert (check["discovery"]["source"], check["state"]) == ("runtime", "gpu_rejected_by_ollama")


def test_a_jetson_without_complement_gets_the_proposal_with_the_sizes_of_the_lock(program):
    root, manifest = program
    write_json_atomic(root / ".runtime/manifests/artifacts.json", {"ollama": manifest["ollama"]})
    check = cli.accelerator_check(PROFILE, {"status": "stopped"}, None, None)
    assert check["state"] == "gpu_libraries_missing" and check["discovery"] is None
    assert check["complement"] == {"file": "ollama-linux-arm64-jetpack5.tar.zst", "size": 297201571,
                                   "extracted_size": 864658584, "variant": "cuda_jetpack5", "qualified": True}
    assert (check["libraries"]["required"], check["libraries"]["provisioned"]) == (True, False)


def test_a_legacy_profile_carries_what_auto_would_do(program):
    from tests.unit.test_runtime_accelerator import JETSON_JETPACK5

    root, _ = program
    _provision_record(root, JETSON_JETPACK5, "2026-10-01T22:00:00+00:00")
    legacy = {"llm": {"model": "qwen3.5:4b-text", "num_gpu": 0}}
    check = cli.accelerator_check(legacy, {"status": "stopped"}, None, None)
    assert (check["state"], check["mode"], check["reason"]) == ("cpu_legacy", "cpu", "legacy_profile_cpu")
    assert (check["if_auto"]["mode"], check["if_auto"]["reason"]) == ("gpu", "gpu_discovered")


def test_doctor_adds_the_calcul_check_from_the_instance_and_the_api_diagnostics(doctor_profile, program):
    from tests.unit.test_runtime_accelerator import JETSON_JETPACK5

    path, profile, _ = doctor_profile
    me = psutil.Process()
    data = Path(profile["app"]["data_dir"])
    write_json_atomic(data / "control/runtime.json", {
        "status": "running", "instance_id": "instance-gpu", "services": {}, "profile_sha256": file_hash(path),
        "data_dir": str(data), "supervisor": {"pid": me.pid, "created_at": me.create_time(), "executable": me.exe()},
        "accelerator": _recorded(JETSON_JETPACK5, "2026-10-01T21:49:30+00:00", "gpu", "gpu_discovered")})
    fallback = {"utc": "2026-10-01T22:14:05+00:00", "http_status": 500, "error": "CUDA error"}

    class Api(BaseHTTPRequestHandler):
        def do_GET(self):
            body = {"/api/v1/health": {"status": "ok"},
                    "/api/v1/diagnostics": {"index_consistency": {"status": "consistent", "active_generations": 0},
                                            "llm_accelerator": {"requested": "auto", "requested_source": "profile",
                                                                "mode": "cpu", "reason": "gpu_discovered",
                                                                "fallback": fallback}}}.get(self.path)
            payload = json.dumps(body or {"code": "not_found"}).encode()
            self.send_response(200 if body else 404)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", profile["app"]["port"]), Api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = cli.doctor(path)
    finally:
        server.shutdown()
        server.server_close()
    check = result["checks"]["accelerator"]
    assert (check["state"], check["fallback"], check["usage"]) == ("gpu_fallback", fallback, None)
    calcul = result["verdict"]["rubrics"][-1]
    assert calcul["rubric"] == "calcul" and calcul["level"] == "orange"


def test_status_adds_one_line_on_the_generation_mode(tmp_path, monkeypatch):
    from tests.unit.test_runtime_accelerator import JETSON_JETPACK5, WINDOWS_IRIS_XE

    monkeypatch.setattr(cli, "launcher_command", lambda command: f"./rag.sh {command}")
    states = {"running": {"status": "running", "accelerator": _recorded(JETSON_JETPACK5, "u", "gpu", "gpu_discovered")},
              "stopped": {"status": "stopped", "accelerator": _recorded(WINDOWS_IRIS_XE, "u", "cpu", "no_gpu_discovered")},
              "before": {"status": "running"}}
    lines = {}
    for name, state in states.items():
        monkeypatch.setattr(cli, "status", lambda path, state=state: dict(state))
        lines[name] = cli.status_report(tmp_path / "profil.yaml").get("generation")
    assert lines == {"running": "Génération sur GPU, Orin (CUDA, GPU intégré, bibliothèques cuda_jetpack5). Un repli sur "
                                "CPU après un échec du GPU est signalé par ./rag.sh doctor.",
                     "stopped": "Dernière instance : génération sur CPU, aucun GPU utilisable découvert par Ollama.",
                     "before": None}


def test_a_complement_provisioned_while_the_instance_runs_takes_effect_at_the_next_start(program, monkeypatch):
    from services.runtime import platforms
    from services.runtime.verdict import calcul_rubric
    from tests.unit.test_runtime_accelerator import JETSON_BASE_ONLY, JETSON_JETPACK5

    monkeypatch.setattr(platforms, "WINDOWS", False)
    monkeypatch.setattr(platforms, "LAUNCHER", "./rag.sh")
    root, _ = program
    instance = _recorded(JETSON_BASE_ONLY, "2026-10-01T18:54:12+00:00", "cpu", "no_gpu_discovered")
    instance["libraries"] = {"entry": "ollama-linux-arm64-jetpack5.tar.zst", "required": True, "provisioned": False,
                             "variants": {}}
    runtime = {"status": "running", "instance_id": "instance-cpu", "accelerator": instance}
    # Avant la sonde : complément extrait depuis le démarrage de l'instance, aucune découverte faite avec lui ; le
    # redémarrage la fera (revue J11 runtime-3), il n'y a plus de complément à provisionner.
    check = cli.accelerator_check(PROFILE, runtime, [], None)
    assert (check["state"], check["discovery_stale"], check["next_start"]) == ("discovery_pending", True, None)
    assert calcul_rubric(check)[0]["message"] == (
        "Calcul sur CPU : les bibliothèques GPU d'Ollama ont changé depuis le démarrage de l'instance en marche. Le mode "
        "de calcul, GPU ou CPU, sera choisi à son redémarrage (./rag.sh down puis ./rag.sh up).")
    # provision --only ollama-gpu, sonde comprise, pendant que l'instance tourne.
    _provision_record(root, JETSON_JETPACK5, "2026-10-01T22:00:00+00:00")
    check = cli.accelerator_check(PROFILE, runtime, [], None)
    assert (check["state"], check["mode"], check["next_start"]["mode"]) == ("gpu_pending", "cpu", "gpu")
    assert check["discovery"]["source"] == "runtime"
    assert calcul_rubric(check)[0] == {"rubric": "calcul", "level": "vert", "message": (
        "Génération sur GPU au prochain démarrage de l'atelier (./rag.sh down puis ./rag.sh up) : Orin (CUDA, GPU "
        "intégré, bibliothèques cuda_jetpack5) ; l'instance en marche calcule encore sur CPU.")}


# --- Découverte périmée, illisible ou absente (revue J11 runtime-3, invariants-03, invariants-09) ------------------------

def _without_complement() -> dict:
    return {"entry": "ollama-linux-arm64-jetpack5.tar.zst", "required": True, "provisioned": False, "variants": {}}


def test_a_discovery_made_before_the_complement_was_extracted_waits_for_the_next_start(program, monkeypatch):
    # Instance arrêtée sans complément (découverte cpu_only), puis complément extrait sans nouvelle découverte
    # (provision --offline, modèle présent ; ou pull-model en échec après les artefacts).
    from services.runtime import platforms
    from services.runtime.verdict import calcul_rubric
    from tests.unit.test_runtime_accelerator import JETSON_BASE_ONLY

    monkeypatch.setattr(platforms, "WINDOWS", False)
    monkeypatch.setattr(platforms, "LAUNCHER", "./rag.sh")
    stopped = {"status": "stopped", "instance_id": "avant-complement",
               "accelerator": {**_recorded(JETSON_BASE_ONLY, "2026-10-01T18:54:12+00:00", "cpu", "no_gpu_discovered"),
                               "libraries": _without_complement()}}
    check = cli.accelerator_check(PROFILE, stopped, None, None)
    assert (check["state"], check["discovery"], check["discovery_stale"]) == ("discovery_pending", None, True)
    assert calcul_rubric(check) == ({"rubric": "calcul", "level": "vert", "message": (
        "Les bibliothèques GPU d'Ollama ont changé depuis la dernière découverte des GPU : elle sera refaite au "
        "prochain démarrage, qui choisira le mode de calcul, GPU ou CPU (./rag.sh up).")}, None)
    # Même découverte, bibliothèques inchangées depuis : elle fait foi (rejet par Ollama).
    root, manifest = program
    stopped["accelerator"]["libraries"] = verified(root, manifest)
    assert cli.accelerator_check(PROFILE, stopped, None, None)["state"] == "gpu_rejected_by_ollama"


def verified(root, manifest) -> dict:
    from services.runtime.accelerator import verified_libraries
    from tests.unit.test_runtime_accelerator import JETSON

    return verified_libraries(_lock_with_sizes(), manifest, JETSON, root=root)


def test_a_provision_discovery_made_with_other_libraries_is_stale_too(program):
    from tests.unit.test_runtime_accelerator import JETSON_BASE_ONLY

    root, _ = program
    _provision_record(root, JETSON_BASE_ONLY, "2026-10-01T22:00:00+00:00")
    record = json.loads((root / ".runtime/manifests/ollama-discovery.json").read_text(encoding="utf-8"))
    write_json_atomic(root / ".runtime/manifests/ollama-discovery.json", {**record, "libraries": _without_complement()})
    check = cli.accelerator_check(PROFILE, {"status": "stopped"}, None, None)
    assert (check["state"], check["discovery_stale"]) == ("discovery_pending", True)


def test_a_failed_probe_does_not_hide_the_readable_discovery_of_the_last_instance(program):
    from tests.unit.test_runtime_accelerator import JETSON_JETPACK5

    root, manifest = program
    stopped = {"status": "stopped", "instance_id": "derniere",
               "accelerator": {**_recorded(JETSON_JETPACK5, "2026-10-01T21:49:30+00:00", "gpu", "gpu_discovered"),
                               "libraries": verified(root, manifest)}}
    write_json_atomic(root / ".runtime/manifests/ollama-discovery.json", {
        "schema_version": 1, "source": "provision", "method": "probe", "utc": "2026-10-02T09:00:00+00:00",
        "log": ".runtime/provision-service/ollama-probe.log", "status": "unreadable", "devices": [], "dropped": [],
        "error": "OSError : [Errno 98] Address already in use"})
    check = cli.accelerator_check(PROFILE, stopped, None, None)
    assert (check["state"], check["discovery"]["source"], check["discovery"]["status"]) == ("gpu_pending", "runtime", "gpu")
    assert check["discovery"]["superseded"] == {"source": "provision", "utc": "2026-10-02T09:00:00+00:00",
                                                "log": ".runtime/provision-service/ollama-probe.log",
                                                "error": "OSError : [Errno 98] Address already in use"}
    # Sans découverte lisible encore valable, l'échec de la sonde fait foi : son journal est cité par la rubrique.
    stopped["accelerator"]["libraries"] = _without_complement()
    check = cli.accelerator_check(PROFILE, stopped, None, None)
    assert (check["state"], check["discovery"]["source"]) == ("discovery_unreadable", "provision")


def test_an_instance_started_before_the_gpu_acceleration_is_restarted_and_still_watched(program, monkeypatch):
    # Instance en marche démarrée avant J11 (runtime.json sans clé accelerator) : son API envoie num_gpu: 0. Profil
    # devenu auto depuis : le mode se décide au redémarrage (down puis up) et l'anomalie de résidence reste détectée.
    from services.runtime import platforms
    from services.runtime.verdict import calcul_rubric

    monkeypatch.setattr(platforms, "WINDOWS", False)
    monkeypatch.setattr(platforms, "LAUNCHER", "./rag.sh")
    before = {"status": "running", "instance_id": "avant-j11", "services": {}}
    check = cli.accelerator_check(PROFILE, before, [], None)
    assert (check["state"], check["running"], check["mode"]) == ("discovery_pending", True, "cpu")
    assert check["instance_predates_accelerator"] is True
    assert calcul_rubric(check)[0]["message"] == (
        "Calcul sur CPU : l'instance en marche a démarré avant l'accélération GPU. Le mode de calcul, GPU ou CPU, sera "
        "choisi à son redémarrage (./rag.sh down puis ./rag.sh up).")
    resident = [{"name": "qwen3.5:4b-text", "digest": "d", "size": 3107811491, "size_vram": 3107811491}]
    assert cli.accelerator_check(PROFILE, before, resident, None)["state"] == "anomaly_gpu_in_cpu_mode"
    # Profil resté en forme antérieure : l'instance et le profil calculent sur CPU.
    legacy = {"llm": {"model": "qwen3.5:4b-text", "num_gpu": 0}}
    assert cli.accelerator_check(legacy, before, [], None)["state"] == "cpu_legacy"
    # Démarrage en cours (le superviseur n'a pas encore consigné le mode) : rien n'est supposé de l'instance.
    starting = cli.accelerator_check(PROFILE, {"status": "starting", "services": {}}, None, None)
    assert starting["running"] is False and "instance_predates_accelerator" not in starting


def test_a_jetson_r36_complement_is_not_a_qualified_path(program, monkeypatch):
    from tests.unit.test_runtime_accelerator import LOCK

    root, manifest = program
    monkeypatch.setattr(cli, "host_signals", lambda: {"platform": "linux-aarch64", "l4t_major": 36, "jetpack": "jetpack6",
                                                      "nvidia_kernel_driver": "NVRM", "gpu_nodes": {},
                                                      "windows_nvcuda": None})
    (root / "config/artifacts.lock.json").write_text(json.dumps(LOCK), encoding="utf-8")
    check = cli.accelerator_check(PROFILE, {"status": "stopped"}, None, None)
    assert check["complement"] == {"file": "ollama-linux-arm64-jetpack6.tar.zst", "size": None, "extracted_size": None,
                                   "variant": "cuda_jetpack6", "qualified": False}
    assert check["state"] == "gpu_libraries_missing"


def test_a_windows_kit_without_gpu_libraries_is_named_on_an_nvidia_host(tmp_path, monkeypatch):
    # Kit construit avec --without-gpu : le manifeste consigne cuda_v12, cuda_v13 et vulkan, absents du disque.
    from services.runtime import accelerator
    from tests.unit.test_runtime_accelerator import LOCK, WINDOWS_IRIS_XE

    (tmp_path / "config").mkdir()
    (tmp_path / "config/artifacts.lock.json").write_text(json.dumps(LOCK), encoding="utf-8")
    write_json_atomic(tmp_path / ".runtime/manifests/artifacts.json", {"ollama": [{
        "url": "https://ici/base.zip", "extracted_files": [
            {"path": f".runtime/bin/ollama-0.35.0/lib/ollama/{name}/ggml.dll", "sha256": "0" * 64, "size": 1}
            for name in ("cuda_v12", "cuda_v13", "vulkan")]}]})
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(accelerator, "platform_id", lambda: "windows-x86_64")
    monkeypatch.setattr(cli, "host_signals", lambda: {"platform": "windows-x86_64", "l4t_major": None, "jetpack": None,
                                                      "nvidia_kernel_driver": None, "gpu_nodes": {},
                                                      "windows_nvcuda": True})
    stopped = {"status": "stopped", "accelerator": {**_recorded(WINDOWS_IRIS_XE, "2026-10-01T09:00:00+00:00", "cpu",
                                                                 "no_gpu_discovered")}}
    assert cli.accelerator_check(PROFILE, stopped, None, None)["state"] == "cuda_libraries_absent"
