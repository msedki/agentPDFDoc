"""Profils RAM synthétiques qualifiés : aucune qualification/model/runtime réelle."""

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from services.runtime import cli, model_profiles, profile_setup
from tools.dist import linux_install, linux_kit

ROOT = Path(__file__).resolve().parents[2]
GIB = 1024**3


def synthetic_catalogue():
    entries = []
    for name, minimum, peak, margin, priority in (("base", 6 * GIB, 4 * GIB, 2 * GIB, 1),
                                                ("large", 12 * GIB, 11 * GIB, 2 * GIB, 2)):
        profile = f"config/{name}.yaml"
        tokenizer = f".runtime/models/{name}/tokenizer_config.json"
        entries.append({"id": name, "kit_set": name, "model": name, "served_model": name, "profile": profile,
                        "pins": {profile: "a" * 64, tokenizer: "b" * 64}, "tokenizer_pins": {tokenizer: "b" * 64},
                        "model_manifest_sha256": {name: "c" * 64},
                        "qualification": {"status": "qualified", "minimum_visible_memory_bytes": minimum,
                                          "measured_peak_bytes": peak, "system_margin_bytes": margin, "priority": priority,
                                          "platforms": ["linux-aarch64", "windows-x86_64"], "modes": ["cpu"],
                                          "evidence": ["SYNTHETIC_UNIT_QUALIFICATION_NOT_A_PRODUCT_MEASUREMENT"]}})
    return {"schema_version": 1, "legacy_default_model": "base", "profiles": entries}


def selection(catalogue=None, **overrides):
    catalogue = catalogue or synthetic_catalogue()
    inputs = {"total_memory_bytes": 13 * GIB, "platform": "linux-aarch64", "mode": "cpu",
              "files": {path: digest for entry in catalogue["profiles"] for path, digest in entry["pins"].items()},
              "models": {name: digest for entry in catalogue["profiles"] for name, digest in entry["model_manifest_sha256"].items()}}
    return model_profiles.select_profile(catalogue, **(inputs | overrides))


@pytest.mark.parametrize("memory,expected", [(6 * GIB - 1, "legacy_fallback"), (6 * GIB, "base"),
                                             (13 * GIB - 1, "base"), (13 * GIB, "large"), (13 * GIB + 1, "large")])
def test_exact_byte_boundaries_include_measured_peak_and_margin(memory, expected):
    result = selection(total_memory_bytes=memory)
    assert (result["selection"] if expected == "legacy_fallback" else result["profile_id"]) == expected
    assert result["visible_memory_bytes"] == memory
    assert result["qualification"] is None if expected == "legacy_fallback" else result["qualification"]["status"] == "qualified"


@pytest.mark.parametrize("mutation,reason", [("qualification", "not_qualified"), ("platform", "platform_not_qualified"),
                                            ("mode", "mode_not_qualified"), ("file", "profile_or_artifact_absent_or_pin_mismatch"),
                                            ("model", "model_absent_or_lock_mismatch"), ("delivery", "model_not_delivered")])
def test_better_profile_must_be_qualified_pinned_present_and_compatible(mutation, reason):
    catalogue = synthetic_catalogue()
    inputs = {}
    if mutation == "qualification":
        catalogue["profiles"][1]["qualification"] = None
    elif mutation in {"platform", "mode"}:
        catalogue["profiles"][1]["qualification"][mutation + "s"] = ["other"]
    elif mutation == "file":
        inputs["files"] = dict(catalogue["profiles"][0]["pins"])
    elif mutation == "model":
        inputs["models"] = {"base": "c" * 64, "large": "d" * 64}
    else:
        inputs["available_models"] = {"base"}
    result = selection(catalogue, **inputs)
    assert result["profile_id"] == "base"
    assert reason in next(item for item in result["rejected"] if item["profile_id"] == "large")["reasons"]


@pytest.mark.parametrize("value", [True, 0, -1, 6.5 * GIB, "16GiB"])
def test_invalid_memory_is_never_rounded_or_assumed(value):
    with pytest.raises(ValueError, match="RAM visible"):
        selection(total_memory_bytes=value)


def test_unknown_memory_fallback_is_not_a_qualified_selection_and_manual_choice_is_preserved():
    result = selection(total_memory_bytes=None)
    assert result["selection"] == "legacy_fallback" and result["qualification"] is None
    manual = selection(total_memory_bytes=None, manual_model="large", files={}, models={})
    assert manual["selection"] == "manual_model" and manual["model"] == "large" and manual["qualification"] is None
    with pytest.raises(ValueError, match="non livré"):
        selection(manual_model="large", available_models={"base"})


def test_same_visible_bytes_have_same_decision_on_two_qualified_platforms():
    linux = selection(platform="linux-aarch64")
    windows = selection(platform="windows-x86_64")
    assert linux["model"] == windows["model"] == "large"
    assert selection(platform="linux-x86_64")["selection"] == "legacy_fallback"


def test_catalogue_has_no_new_qualification_or_threshold_and_lock_is_separate():
    catalogue = model_profiles.read_catalogue(ROOT)
    assert catalogue["legacy_default_model"] == "qwen3.5:4b"
    assert {entry["model"] for entry in catalogue["profiles"]} == {"qwen3.5:2b", "qwen3.5:4b"}
    assert all(entry["qualification"] is None for entry in catalogue["profiles"])
    for entry in catalogue["profiles"]:
        assert model_profiles.file_sha256(ROOT / entry["profile"]) == entry["pins"][entry["profile"]]


def write_synthetic_program(root):
    catalogue = synthetic_catalogue()
    lock = {"store": ".runtime/models/ollama", "models": {}}
    real_base = yaml.safe_load((ROOT / "config/local16-4b.yaml").read_text())
    for entry in catalogue["profiles"]:
        name = entry["model"]
        profile = copy.deepcopy(real_base)
        profile["llm"].update(model=name, source_model=name, accelerator="cpu")
        path = root / entry["profile"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile))
        tokenizer = root / next(iter(entry["tokenizer_pins"]))
        tokenizer.parent.mkdir(parents=True, exist_ok=True)
        tokenizer.write_text('{"chat_template":"SYNTHETIC"}')
        entry["pins"] = {entry["profile"]: model_profiles.file_sha256(path),
                         tokenizer.relative_to(root).as_posix(): model_profiles.file_sha256(tokenizer)}
        entry["tokenizer_pins"] = {tokenizer.relative_to(root).as_posix(): model_profiles.file_sha256(tokenizer)}
        content = b"SYNTHETIC_MODEL_BYTES_" + name.encode()
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        layer = {"mediaType": "synthetic", "digest": digest, "size": len(content)}
        manifest_path = f"manifests/registry.ollama.ai/library/{name}/latest"
        manifest = root / lock["store"] / manifest_path
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"config": layer, "layers": []}))
        blob = root / lock["store"] / "blobs" / digest.replace(":", "-")
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(content)
        lock["models"][name] = {"manifest_path": manifest_path, "manifest_sha256": model_profiles.file_sha256(manifest),
                                "config": layer, "layers": []}
        entry["model_manifest_sha256"] = {name: model_profiles.file_sha256(manifest)}
    (root / "config/models.lock.json").write_text(json.dumps(lock))
    (root / model_profiles.CATALOGUE_PATH).write_text(json.dumps(catalogue))
    return catalogue, lock


def test_real_local_presence_requires_tokenizer_and_locked_blobs_without_copy_or_network(tmp_path):
    catalogue, lock = write_synthetic_program(tmp_path)
    decision = model_profiles.select_local_profile(tmp_path, total_memory_bytes=13 * GIB, platform="linux-aarch64", mode="cpu")
    assert decision["selection"] == "automatic" and decision["model"] == "large"
    large_layer = lock["models"]["large"]["config"]
    (tmp_path / lock["store"] / "blobs" / large_layer["digest"].replace(":", "-")).unlink()
    assert model_profiles.select_local_profile(tmp_path, total_memory_bytes=13 * GIB, platform="linux-aarch64", mode="cpu")["model"] == "base"
    assert len(model_profiles.presence(tmp_path, catalogue, lock)[1]) == 1


def test_cli_init_profile_persists_selection_without_mutating_yaml_source(tmp_path, monkeypatch, capsys):
    program, data = tmp_path / "program", tmp_path / "new-data"
    write_synthetic_program(program)
    before = {path: path.read_bytes() for path in program.rglob("*") if path.is_file()}
    monkeypatch.setattr(cli, "ROOT", program)
    monkeypatch.setattr(profile_setup, "ROOT", program)
    monkeypatch.setattr(cli, "platform_id", lambda: "linux-aarch64")
    monkeypatch.setattr(profile_setup, "port_free", lambda port: True)
    monkeypatch.setattr(sys, "argv", ["rag", "init-profile", "--target", str(data), "--memory-total-bytes", str(13 * GIB)])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["model_selection"]["model"] == "large"
    assert json.loads((data / "model-selection.json").read_text()) == result["model_selection"]
    assert yaml.safe_load((data / "profile.yaml").read_text())["llm"]["model"] == "large"
    assert all(path.read_bytes() == content for path, content in before.items())
    assert cli.main() == 1
    assert "jamais remplacé" in json.loads(capsys.readouterr().out)["message"]


def test_explicit_profile_never_reads_catalogue_or_reselects_on_up(monkeypatch, tmp_path, capsys):
    chosen = tmp_path / "custom.yaml"
    monkeypatch.setattr(cli, "read_catalogue", lambda root: pytest.fail("manual profile must not inspect catalogue"))
    monkeypatch.setattr(cli, "select_local_profile", lambda *args, **kw: pytest.fail("existing instance must not reselect"))
    observed = []
    monkeypatch.setattr(cli, "start", lambda path: observed.append(path) or {"status": "explicit_runtime_double"})
    monkeypatch.setattr(sys, "argv", ["rag", "up", "--profile", str(chosen)])
    assert cli.main() == 0 and observed == [chosen]
    capsys.readouterr()


def test_linux_pre_copy_selector_is_hashed_before_execution_and_preserves_historical_manifest(tmp_path):
    write_synthetic_program(tmp_path)
    script = tmp_path / "services/runtime/model_profiles.py"
    script.parent.mkdir(parents=True)
    script.write_bytes((ROOT / "services/runtime/model_profiles.py").read_bytes())
    sums = {path.relative_to(tmp_path).as_posix(): model_profiles.file_sha256(path) for path in tmp_path.rglob("*") if path.is_file()}
    (tmp_path / "SHA256SUMS").write_text(''.join(f'{digest}  {path}\n' for path, digest in sorted(sums.items())))
    manifest = {"platform": "linux-aarch64", "model_profiles": {name: f"config/{name}.yaml" for name in ("base", "large")},
                "model_selection": {"catalogue": model_profiles.CATALOGUE_PATH, "catalogue_sha256": sums[model_profiles.CATALOGUE_PATH]},
                "sha256sums_sha256": model_profiles.file_sha256(tmp_path / "SHA256SUMS")}
    ctx = SimpleNamespace(kit=tmp_path, probe=SimpleNamespace(memory_total_bytes=lambda: 13 * GIB))
    assert linux_install.install_model_selection(ctx, manifest, None)["model"] == "large"
    assert linux_install.install_model_selection(ctx, {}, None) is None
    import importlib.util
    import marshal
    import struct

    cache = Path(importlib.util.cache_from_source(str(script)))
    cache.parent.mkdir()
    header = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, int(script.stat().st_mtime), script.stat().st_size)
    cache.write_bytes(header + marshal.dumps(compile("raise AssertionError('UNVERIFIED_CACHE_EXECUTED')", str(script), "exec")))
    assert linux_install.install_model_selection(ctx, manifest, None)["model"] == "large"
    script.write_text("raise AssertionError('MUST_NOT_EXECUTE_ALTERED_SELECTOR')")
    with pytest.raises(linux_install.InstallError, match="altéré ou absent"):
        linux_install.install_model_selection(ctx, manifest, None)


def test_windows_facade_forwards_exact_memory_to_same_selector_and_update_keeps_profile():
    script = (ROOT / "tools/dist/install.ps1").read_text(encoding="utf-8-sig")
    assert "$memoryBytes = [long]$os.TotalVisibleMemorySize * 1024" in script
    assert "@('-MemoryTotalBytes', [string]$memoryBytes)" in script
    assert "$profilePath = $existingProfile" in script
    facade = (ROOT / "rag.ps1").read_text(encoding="utf-8-sig")
    assert "if ($PSBoundParameters.ContainsKey('Profile'))" in facade
    assert "@('--memory-total-bytes',[string]$MemoryTotalBytes)" in facade
    assert "[string]$Profile = 'config/local16-4b.yaml'" not in facade


def test_selection_pre_copy_files_only_extend_new_manifest_contract():
    historical = {"model_profiles": {"old": "config/old.yaml"}}
    assert "services/runtime/model_profiles.py" not in linux_install.pre_copy_files(historical)
    new = historical | {"model_selection": {"catalogue": model_profiles.CATALOGUE_PATH}}
    assert {"services/runtime/model_profiles.py", model_profiles.CATALOGUE_PATH, "config/models.lock.json"} <= set(linux_install.pre_copy_files(new))
    assert linux_kit.MODEL_PROFILES == {"2b": "config/local16.yaml", "4b": "config/local16-4b.yaml"}


@pytest.mark.parametrize("mutation", ["duplicate_set", "unsafe_set", "duplicate_model", "unsafe_pin", "missing_template_pin"])
def test_ambiguous_or_unpinned_qualification_is_refused(mutation):
    catalogue = synthetic_catalogue()
    entry = catalogue["profiles"][1]
    if mutation == "duplicate_set":
        entry["kit_set"] = "base"
    elif mutation == "unsafe_set":
        entry["kit_set"] = "../outside"
    elif mutation == "duplicate_model":
        entry["model"] = "base"
    elif mutation == "unsafe_pin":
        entry["pins"]["config//x.yaml"] = "a" * 64
    else:
        entry["tokenizer_pins"] = {}
    with pytest.raises(ValueError):
        selection(catalogue)


def test_external_blob_link_is_not_a_locally_present_model(tmp_path):
    program = tmp_path / "program"
    _, lock = write_synthetic_program(program)
    layer = lock["models"]["large"]["config"]
    blob = program / lock["store"] / "blobs" / layer["digest"].replace(":", "-")
    outside = tmp_path / "foreign-blob"
    outside.write_bytes(blob.read_bytes())
    blob.unlink()
    blob.symlink_to(outside)
    result = model_profiles.select_local_profile(program, total_memory_bytes=13 * GIB, platform="linux-aarch64", mode="cpu")
    assert result["model"] == "base"
    assert "model_absent_or_lock_mismatch" in result["rejected"][0]["reasons"]


def test_unknown_memory_from_installer_is_not_reprobed_and_reuses_historical_fallback(tmp_path, monkeypatch, capsys):
    program, data = tmp_path / "program", tmp_path / "data"
    write_synthetic_program(program)
    monkeypatch.setattr(cli, "ROOT", program)
    monkeypatch.setattr(profile_setup, "ROOT", program)
    monkeypatch.setattr(cli, "visible_memory_bytes", lambda: pytest.fail("unknown installer measurement must be preserved"))
    monkeypatch.setattr(profile_setup, "port_free", lambda port: True)
    monkeypatch.setattr(sys, "argv", ["rag", "init-profile", "--target", str(data), "--memory-unknown"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)["model_selection"]
    assert result["selection"] == "legacy_fallback" and result["visible_memory_bytes"] is None
    assert yaml.safe_load((data / "profile.yaml").read_text())["llm"]["model"] == "base"


def test_catalogue_and_yaml_model_identity_must_agree_before_any_profile_is_written(tmp_path, monkeypatch):
    program, data = tmp_path / "program", tmp_path / "data"
    write_synthetic_program(program)
    selection = model_profiles.select_local_profile(program, total_memory_bytes=13 * GIB, platform="linux-aarch64", mode="cpu")
    monkeypatch.setattr(profile_setup, "port_free", lambda port: True)
    with pytest.raises(ValueError, match="mêmes modèles"):
        profile_setup.write_user_profile(program / "config/base.yaml", data, program_root=program, selection=selection)
    assert not data.exists()


@pytest.mark.parametrize("content,expected", [("MemTotal:       16384001 kB\nMemAvailable: 1 kB\n", 16384001 * 1024),
                                             ("MemTotal: invalid kB\n", None), ("MemAvailable: 16384001 kB\n", None)])
def test_linux_visible_memory_keeps_exact_physical_bytes_and_unknown(content, expected, monkeypatch):
    monkeypatch.setattr(model_profiles.sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", lambda path, **kwargs: content if path == Path("/proc/meminfo") else pytest.fail("unexpected memory source"))
    assert model_profiles.visible_memory_bytes() == expected
    probe = linux_install.SystemProbe()
    assert probe.memory_total_bytes() == expected
