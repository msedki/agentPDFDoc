import hashlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
import pytest
import yaml

from services.runtime import cli
from services.runtime.artifacts import ROOT, file_hash, write_json_atomic


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
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
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
