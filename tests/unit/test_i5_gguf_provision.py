"""Enhanced provisioning with explicit download/import/process doubles.

Real YAML/policy readers and dispatch run against tiny temporary fixtures. No
model, subprocess, socket or network is used; fake model bytes are never claimed
to satisfy a real model checksum or inference qualification.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from services.api.settings import Settings
from services.runtime import artifacts, cli, provisioning
from services.runtime.profile_schema import ProfileValidationError
from tools.qualification import provision_enhanced_4b as importer

ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3-4b-enhanced:q4km"


@pytest.fixture
def enhanced_import(tmp_path, monkeypatch):
    program = tmp_path / "program"
    (program / "config").mkdir(parents=True)
    lock = json.loads((ROOT / "config/enhanced-4b.lock.json").read_text(encoding="utf-8"))
    (program / "config/enhanced-4b.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    profile_path = program / "config/profile.yaml"
    profile_path.write_bytes((ROOT / "config/enhanced-4b.yaml").read_bytes())
    source = program / ".runtime/models" / lock["gguf"]["filename"]
    blob = program / ".runtime/models/ollama/blobs" / ("sha256-" + lock["gguf"]["sha256"])
    executable = program / "explicit-ollama-double"
    state = {"downloads": [], "imports": [], "events": [], "artifact_error": False,
             "import_error": False, "wait_timeout": False, "provision_port": 11444, "port_occupied": False}
    result = {"status": "explicit_importer_double", "model": MODEL, "digest": "a" * 64,
              "verified_inputs": "EXPLICIT_DOUBLE_NOT_MODEL_VERIFICATION"}

    class ProbeDouble:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def bind(self, address):
            assert address == ("127.0.0.1", state["provision_port"])
            state["events"].append("port-probe")
            if state["port_occupied"]:
                raise OSError("explicit occupied provisioning port")

    class ChildDouble:
        def wait(self, timeout):
            assert timeout == 30
            state["events"].append("wait")
            if state["wait_timeout"]:
                raise TimeoutError("explicit child shutdown timeout")
            return 0

    class JobDouble:
        def __enter__(self):
            state["events"].append("job-enter")
            return self

        def __exit__(self, *args):
            state["events"].append("job-closed")
            return False

        def launch(self, command, **kwargs):
            assert command == [str(executable), "serve"]
            state["events"].append("owned-launch")
            return ChildDouble()

    def artifact_double(group, **kwargs):
        assert group == "qwen-4b-gguf"
        state["downloads"].append((group, kwargs))
        if state["artifact_error"]:
            raise FileNotFoundError("explicit absent offline blob")
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(b"EXPLICIT_DOWNLOAD_DOUBLE_NOT_GGUF")

    def import_double(path, binary, gguf):
        assert binary == executable
        adjusted = json.loads(path.read_text(encoding="utf-8"))
        assert Settings.load(path).profile == adjusted
        state["imports"].append({"profile": adjusted, "gguf": gguf})
        state["events"].append("import")
        if state["import_error"]:
            raise ValueError("explicit GGUF verification failure")
        return copy.deepcopy(result)

    def check_double(profile):
        assert state["events"][-1] == "job-closed"
        state["events"].append("store-check-after-cleanup")
        return {"models": {MODEL: {"status": "conform"}}}

    monkeypatch.setattr(cli, "ROOT", program)
    monkeypatch.setattr(cli, "OLLAMA_MODELS_DIR", blob.parent.parent)
    monkeypatch.setattr(cli, "native_paths", lambda: {"ollama": executable})
    monkeypatch.setattr(cli, "port_probe", ProbeDouble)
    monkeypatch.setattr(cli, "ProcessJob", JobDouble)
    monkeypatch.setattr(cli, "model_pull_environment", lambda *args: {})
    monkeypatch.setattr(cli, "ollama_working_directory", lambda path: program)
    monkeypatch.setattr(cli, "wait_http", lambda *args, **kwargs: state["events"].append("service-ready"))
    monkeypatch.setattr(cli, "send_owned_console_interrupt", lambda *args: state["events"].append("owned-stop"))
    monkeypatch.setattr(cli, "provision_artifacts", artifact_double)
    monkeypatch.setattr(cli, "profile_model_lock", check_double)
    monkeypatch.setattr(importer, "provision", import_double)
    return SimpleNamespace(profile=profile_path, source=source, blob=blob, state=state, result=result)


@pytest.fixture
def offline_provision(enhanced_import, monkeypatch):
    fixture = enhanced_import
    fixture.state["discovery"] = []
    artifact = cli.provision_artifacts

    def verified_local_artifacts(group=None, **kwargs):
        # The full dispatcher and its nested pull must both propagate the
        # offline constraint; no actual artifact/model is claimed by this double.
        assert kwargs.get("offline") is True
        assert group in {None, "qwen-4b-gguf"}
        return artifact("qwen-4b-gguf", **kwargs)

    monkeypatch.setattr(cli, "host_signals", lambda: {"explicit_host_double": True})
    monkeypatch.setattr(cli, "gpu_complement", lambda *args: (frozenset(), []))
    monkeypatch.setattr(cli, "pnpm_command", lambda: ["explicit-pnpm-double"])
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(provisioning, "tesseract", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "provision_artifacts", verified_local_artifacts)
    monkeypatch.setattr(cli, "record_provision_discovery", lambda *args, **kwargs:
                        fixture.state["discovery"].append(kwargs["method"]))
    return fixture


@pytest.mark.parametrize("source_present", [False, True], ids=["native-blob", "raw-source"])
@pytest.mark.parametrize("offline", [False, True], ids=["explicit-online-provision", "offline-provision"])
def test_enhanced_import_reuses_the_raw_source_or_provisions_the_locked_blob(enhanced_import, source_present, offline):
    fixture = enhanced_import
    if source_present:
        fixture.source.parent.mkdir(parents=True)
        fixture.source.write_bytes(b"EXPLICIT_RAW_SOURCE_DOUBLE_NOT_GGUF")
    assert cli.pull_model(fixture.profile, offline=offline) == fixture.result
    assert fixture.state["downloads"] == ([] if source_present else [("qwen-4b-gguf", {"offline": offline})])
    assert len(fixture.state["imports"]) == 1
    record = fixture.state["imports"][0]
    assert record["gguf"] == (fixture.source if source_present else fixture.blob)
    assert record["profile"]["llm"]["base_url"] == "http://127.0.0.1:11444"
    assert record["profile"]["llm"]["model"] == record["profile"]["llm"]["source_model"] == MODEL
    assert fixture.state["events"][-4:] == ["owned-stop", "wait", "job-closed", "store-check-after-cleanup"]


def test_missing_offline_blob_stops_before_any_native_launch(enhanced_import):
    fixture = enhanced_import
    fixture.state["artifact_error"] = True
    with pytest.raises(FileNotFoundError, match="absent offline blob"):
        cli.pull_model(fixture.profile, offline=True)
    assert fixture.state["downloads"] == [("qwen-4b-gguf", {"offline": True})]
    assert fixture.state["events"] == [] and fixture.state["imports"] == []


def test_failed_gguf_verification_closes_the_owned_job_and_does_not_publish_success(enhanced_import):
    fixture = enhanced_import
    fixture.state["import_error"] = True
    with pytest.raises(ValueError, match="GGUF verification failure"):
        cli.pull_model(fixture.profile, offline=True)
    assert fixture.state["events"][-2:] == ["import", "job-closed"]
    assert "store-check-after-cleanup" not in fixture.state["events"]


def test_shutdown_timeout_still_exits_the_owned_job_before_store_verification(enhanced_import):
    fixture = enhanced_import
    fixture.state["wait_timeout"] = True
    assert cli.pull_model(fixture.profile, offline=True) == fixture.result
    assert fixture.state["events"][-3:] == ["wait", "job-closed", "store-check-after-cleanup"]


@pytest.mark.parametrize("app_port,qdrant_port,expected_port", [
    (11444, 6333, 11445), (8785, 11444, 11446), (8785, 11443, 11445), (11444, 11445, 11447),
])
def test_valid_custom_service_ports_keep_a_valid_temporary_import_profile(enhanced_import,
                                                                         app_port, qdrant_port, expected_port):
    fixture = enhanced_import
    profile = yaml.safe_load(fixture.profile.read_text(encoding="utf-8"))
    profile["app"]["port"] = app_port
    profile["qdrant"]["url"] = f"http://127.0.0.1:{qdrant_port}"
    fixture.profile.write_text(yaml.safe_dump(profile), encoding="utf-8")
    before = fixture.profile.read_bytes()
    assert Settings.load(fixture.profile).profile == profile
    fixture.state["provision_port"] = expected_port
    assert cli.pull_model(fixture.profile, offline=True) == fixture.result
    adjusted = fixture.state["imports"][0]["profile"]
    assert adjusted["app"] == profile["app"] and adjusted["qdrant"] == profile["qdrant"]
    assert adjusted["llm"]["base_url"] == f"http://127.0.0.1:{expected_port}"
    assert adjusted["llm"]["model"] == adjusted["llm"]["source_model"] == MODEL
    assert fixture.state["events"][-4:] == ["owned-stop", "wait", "job-closed", "store-check-after-cleanup"]
    assert fixture.profile.read_bytes() == before


def test_occupied_provisioning_port_never_contacts_or_stops_another_server(enhanced_import):
    fixture = enhanced_import
    fixture.state["port_occupied"] = True
    with pytest.raises(OSError, match="occupied provisioning port"):
        cli.pull_model(fixture.profile, offline=True)
    assert fixture.state["events"] == ["port-probe"]
    assert fixture.state["imports"] == []


def test_full_offline_provision_imports_the_local_gguf_before_a_manifest_exists(offline_provision):
    fixture = offline_provision
    assert not (cli.ROOT / ".runtime/manifests/qwen3-4b-enhanced.json").exists()
    assert cli.provision(fixture.profile, offline=True) == fixture.result
    assert len(fixture.state["imports"]) == 1 and fixture.state["discovery"] == ["pull_model"]
    assert all(kwargs["offline"] is True for _, kwargs in fixture.state["downloads"])
    assert fixture.state["events"][-4:] == ["owned-stop", "wait", "job-closed", "store-check-after-cleanup"]


@pytest.mark.parametrize("failure", ["missing", "mismatch"])
def test_full_offline_provision_never_reports_success_for_missing_or_mismatched_gguf(offline_provision, failure):
    fixture = offline_provision
    fixture.state["artifact_error" if failure == "missing" else "import_error"] = True
    with pytest.raises(FileNotFoundError if failure == "missing" else ValueError):
        cli.provision(fixture.profile, offline=True)
    assert all(kwargs["offline"] is True for _, kwargs in fixture.state["downloads"])
    assert fixture.state["discovery"] == []
    if failure == "missing":
        assert fixture.state["events"] == [] and fixture.state["imports"] == []
    else:
        assert fixture.state["events"][-2:] == ["import", "job-closed"]
        assert "store-check-after-cleanup" not in fixture.state["events"]


@pytest.mark.parametrize("corrupt", [False, True], ids=["absent", "corrupted"])
def test_offline_artifact_verifier_refuses_network_before_any_download(tmp_path, monkeypatch, corrupt):
    target = tmp_path / "local.gguf"
    if corrupt:
        target.write_bytes(b"tampered")
    before = target.read_bytes() if corrupt else None

    def forbidden_network(*args, **kwargs):
        pytest.fail("An offline failure must not open a network request")

    monkeypatch.setattr(artifacts.urllib.request, "urlopen", forbidden_network)
    with pytest.raises(FileNotFoundError, match="offline"):
        artifacts.download({"sha256": "a" * 64, "size": 8, "url": "https://example.invalid/local.gguf"}, target, offline=True)
    assert (target.read_bytes() if target.exists() else None) == before
    assert not target.with_suffix(".gguf.part").exists()


@pytest.mark.parametrize("legacy", ["qwen3.5:2b", "qwen3.5:4b-text"])
def test_legacy_profile_is_refused_before_download_or_port_probe(enhanced_import, legacy):
    fixture = enhanced_import
    profile = yaml.safe_load(fixture.profile.read_text(encoding="utf-8"))
    profile["llm"]["model"] = legacy
    fixture.profile.write_text(yaml.safe_dump(profile), encoding="utf-8")
    with pytest.raises(ProfileValidationError):
        cli.pull_model(fixture.profile)
    assert fixture.state["events"] == [] and fixture.state["downloads"] == []


def test_skip_model_skips_the_gguf_group_without_losing_other_group_exclusions(tmp_path, monkeypatch):
    profile = yaml.safe_load((ROOT / "config/enhanced-4b.yaml").read_text(encoding="utf-8"))
    calls = []
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "load_profile", lambda path: profile)
    monkeypatch.setattr(cli, "host_signals", lambda: {"explicit_host_double": True})
    monkeypatch.setattr(cli, "gpu_complement", lambda *args: (frozenset({"ollama-gpu"}), []))
    monkeypatch.setattr(cli, "pnpm_command", lambda: ["explicit-pnpm-double"])
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(provisioning, "tesseract", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "record_provision_discovery", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "pull_model", lambda *args, **kwargs: pytest.fail("skip-model must not import"))
    monkeypatch.setattr(cli, "provision_artifacts", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert cli.provision(tmp_path / "profile.yaml", offline=True, skip_model=True) == {
        "artifacts": "verified", "model": "not_requested"}
    assert len(calls) == 1 and calls[0][0] == (None,)
    assert calls[0][1]["skip_groups"] == frozenset({"ollama-gpu", "qwen-4b-gguf"})
    assert calls[0][1]["tokenizer_model_id"] == "Qwen/Qwen3-4B"
