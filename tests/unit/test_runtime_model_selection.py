"""R23 : profils et provisioning avec transports FS/CLI/Ollama explicitement doublés.

Aucun modèle, port, processus ni stockage du poste n'est lu par ces nouveaux témoins.
Les tests existants du superviseur doivent compléter la preuve après intégration.
"""
import json
import sys
from types import SimpleNamespace

import pytest
import yaml

from services.runtime import artifacts, cli
from services.runtime.artifacts import ROOT
from services.runtime.verdict import model_rubric


@pytest.mark.parametrize("model,name", [(None, "local16-4b.yaml"), ("qwen3.5:2b", "local16.yaml"),
                                        ("qwen3.5:4b", "local16-4b.yaml")])
def test_startup_model_resolves_to_a_real_profile(model, name):
    # W045 (6 octobre 2026) : sans option, le profil livré du 4B ; le 2B reste un choix au lancement.
    assert cli.model_profile_path(None, model) == ROOT / "config" / name


def test_the_default_model_is_the_4b_and_the_cli_without_option_starts_its_profile(monkeypatch, capsys):
    assert cli.DEFAULT_MODEL == "qwen3.5:4b" and cli.MODEL_PROFILES[cli.DEFAULT_MODEL] == "local16-4b.yaml"
    assert cli.MODEL_PROFILES["qwen3.5:2b"] == "local16.yaml"
    called = []
    monkeypatch.setattr(sys, "argv", ["rag", "up"])
    monkeypatch.setattr(cli, "start", lambda path: called.append(path) or {"status": "explicit_start_double"})
    assert cli.main() == 0 and called == [ROOT / "config/local16-4b.yaml"]
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["rag", "--help"])
    with pytest.raises(SystemExit):
        cli.main()
    help_text = " ".join(capsys.readouterr().out.split())
    assert "défaut : qwen3.5:4b" in help_text and "--model qwen3.5:2b" in help_text


def test_an_unknown_model_names_the_default_and_the_2b(tmp_path):
    with pytest.raises(ValueError) as refused:
        cli.model_profile_path(None, "qwen3.5:9b")
    assert str(refused.value) == "Modèle livré inconnu ; choisir qwen3.5:4b (défaut) ou qwen3.5:2b"


def test_every_entry_point_takes_the_same_default_profile():
    """rag.sh, rag.ps1, le CLI et le kit Linux décident le même défaut (W045) ; les profils livrés ne changent pas."""
    from tools.dist import linux_kit

    default = "config/" + cli.MODEL_PROFILES[cli.DEFAULT_MODEL]
    assert default == "config/local16-4b.yaml"
    shell = [line for line in (ROOT / "rag.sh").read_text(encoding="utf-8").splitlines() if line.startswith("profile=")]
    assert shell == [f"profile={default}"]
    powershell = (ROOT / "rag.ps1").read_text(encoding="utf-8-sig")
    assert f"[string]$Profile = '{default}'," in powershell and powershell.count("[string]$Profile =") == 1
    assert linux_kit.MODEL_PROFILES[linux_kit.DEFAULT_MODEL] == default
    four = yaml.safe_load((ROOT / default).read_text(encoding="utf-8"))
    assert four["llm"]["source_model"] == cli.DEFAULT_MODEL and four["llm"]["model"] == "qwen3.5:4b-text"


def test_explicit_user_profile_is_preserved_and_never_overlaid(tmp_path):
    path = tmp_path / "profil-utilisateur.yaml"
    assert cli.model_profile_path(path, None) is path
    with pytest.raises(ValueError, match="exclusifs"):
        cli.model_profile_path(path, "qwen3.5:2b")
    with pytest.raises(ValueError, match="inconnu"):
        cli.model_profile_path(None, "qwen3.5:2b-q4_K_M")


@pytest.mark.parametrize("model", ["qwen3.5:2b", "qwen3.5:4b"])
def test_real_cli_passes_the_selected_file_to_start(monkeypatch, capsys, model):
    called = []
    monkeypatch.setattr(sys, "argv", ["rag", "up", "--model", model])
    monkeypatch.setattr(cli, "start", lambda path: called.append(path) or {"status": "explicit_start_double"})
    assert cli.main() == 0
    assert called == [cli.model_profile_path(None, model)]
    assert json.loads(capsys.readouterr().out)["status"] == "explicit_start_double"


def test_real_cli_rejects_model_plus_user_profile_before_start(monkeypatch, capsys, tmp_path):
    called = []
    monkeypatch.setattr(sys, "argv", ["rag", "up", "--model", "qwen3.5:2b", "--profile", str(tmp_path / "user.yaml")])
    monkeypatch.setattr(cli, "start", lambda path: called.append(path))
    assert cli.main() == 1 and called == []
    assert json.loads(capsys.readouterr().out)["error"] == "ValueError"


def test_profiles_keep_the_same_documentary_and_runtime_contracts():
    two = yaml.safe_load((ROOT / "config/local16.yaml").read_text())
    four = yaml.safe_load((ROOT / "config/local16-4b.yaml").read_text())
    assert two["llm"]["model"] == two["llm"]["source_model"] == "qwen3.5:2b"
    assert two["llm"]["required_quantization"] == "Q8_0"
    assert four["llm"]["model"] == "qwen3.5:4b-text" and four["llm"]["required_quantization"] == "Q4_K_M"
    assert two["llm"]["tokenizer_dir"] != four["llm"]["tokenizer_dir"]
    assert two["llm"]["model_manifest"] != four["llm"]["model_manifest"]
    for section in ("app", "embedding", "pdf", "chunking", "retrieval", "qdrant", "sqlite", "security", "ui"):
        assert two[section] == four[section], section
    for value in (two, four):
        assert value["llm"]["think"] is False and value["llm"]["num_ctx"] == 8192


@pytest.mark.parametrize("name,cold_estimate,warm_estimate", [("local16.yaml", 3968, 512), ("local16-4b.yaml", 4352, 640)])
def test_delivered_model_profile_drives_the_cold_admission_boundary(tmp_path, monkeypatch, name, cold_estimate, warm_estimate):
    """Profils réels, mémoire simulée ; aucun modèle, bail ou stockage hôte acquis."""
    from services.runtime.resources import ResourceAdmissionError, ResourceGovernor, admission_requirement

    profile = yaml.safe_load((ROOT / "config" / name).read_text())
    resources = profile["resources"]
    assert resources["initial_llm_load_peak_estimate_mib"] == cold_estimate
    assert resources["host_available_min_mib"] == 1536
    assert resources["warm_llm_additional_peak_estimate_mib"] == warm_estimate
    required = cold_estimate + 1536
    assert admission_requirement(resources, "generation")["required_available_mib"] == required
    governor = ResourceGovernor({**profile, "app": {**profile["app"], "data_dir": str(tmp_path)}},
                                host_lock_path=tmp_path / "host-heavy.lock")
    monkeypatch.setattr(governor, "snapshot", lambda: {"available_mib": required - 1})
    with pytest.raises(ResourceAdmissionError) as refused:
        governor._admit("generation")
    assert refused.value.snapshot["admission"]["required_available_mib"] == required
    monkeypatch.setattr(governor, "snapshot", lambda: {"available_mib": required})
    assert governor._admit("generation") is None
    assert governor._owner is None and governor._host_lock is None
    assert not governor.host_lock_path.exists() and not governor.pause_path.exists()


@pytest.mark.parametrize("chosen", ["qwen3.5:2b", "qwen3.5:4b"])
def test_real_profile_model_lock_never_reads_an_unselected_store(monkeypatch, tmp_path, chosen):
    lock = tmp_path / "models.lock.json"
    lock.write_text(json.dumps({"models": {name: {} for name in ("qwen3.5:2b", "qwen3.5:4b", "qwen3.5:4b-text")}}))
    profile = {"llm": {"model": chosen, "source_model": chosen}}
    looked = []
    def absent(name, store=None):
        looked.append(name)
        return {"status": "absent", "issues": []}
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    monkeypatch.setattr(cli, "ollama_store_files", absent)
    result = cli.profile_model_lock(profile)
    assert looked == [chosen] and set(result["models"]) == {chosen}
    assert result["status"] == "nonconform" and result["profile_models_locked"] is True
    assert result["scope"] == "profile_source_and_served_models_only"


def test_selected_model_is_green_even_with_other_locked_models_absent(monkeypatch, tmp_path):
    lock = tmp_path / "models.lock.json"
    layer = {"mediaType": "model", "digest": "sha256:" + "a" * 64, "size": 9}
    lock.write_text(json.dumps({"models": {
        "qwen3.5:2b": {"manifest_sha256": "b" * 64, "config": layer, "layers": []},
        "qwen3.5:4b": {}, "qwen3.5:4b-text": {}}}))
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    calls = []
    def files(name, store=None):
        calls.append(name)
        assert name == "qwen3.5:2b"
        return {"status": "present", "issues": [], "manifest_sha256": "b" * 64, "entries": [layer]}
    monkeypatch.setattr(cli, "ollama_store_files", files)
    monkeypatch.setattr(cli, "OLLAMA_MODELS_DIR", tmp_path / "nonexistent-synthetic-store")
    result = cli.profile_model_lock({"llm": {"model": "qwen3.5:2b"}})
    assert result["status"] == "conform" and calls == ["qwen3.5:2b"]
    assert model_rubric({"model_lock": result})["level"] == "vert"


@pytest.mark.parametrize("selected", ["Qwen/Qwen3.5-2B", "Qwen/Qwen3.5-4B"])
def test_real_artifact_provision_downloads_only_the_selected_tokenizer(monkeypatch, tmp_path, selected):
    program = tmp_path / "program"
    program.mkdir()
    lock = tmp_path / "artifacts.lock.json"
    entries = [{"model_id": model, "target": "models/" + model.rsplit("-", 1)[1] + "/tokenizer.json", "url": "https://official.invalid/" + model}
               for model in ("Qwen/Qwen3.5-2B", "Qwen/Qwen3.5-4B")]
    lock.write_text(json.dumps({"groups": {"qwen-tokenizer": entries}}))
    monkeypatch.setattr(artifacts, "ROOT", program)
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", lock)
    downloads = []
    def download(entry, target, **kwargs):
        downloads.append((entry["model_id"], kwargs))
        return {**entry, "sha256": "c" * 64, "path": entry["target"], "cached": True}
    monkeypatch.setattr(artifacts, "download", download)
    manifest = artifacts.provision_artifacts("qwen-tokenizer", offline=True, tokenizer_model_id=selected)
    assert downloads == [(selected, {"offline": True})]
    assert [row["model_id"] for row in manifest["qwen-tokenizer"]] == [selected]
    other = next(row["model_id"] for row in entries if row["model_id"] != selected)
    manifest = artifacts.provision_artifacts("qwen-tokenizer", offline=True, tokenizer_model_id=other)
    assert {row["model_id"] for row in manifest["qwen-tokenizer"]} == {selected, other}


def test_unknown_tokenizer_refused_before_download(monkeypatch, tmp_path):
    lock = tmp_path / "artifacts.lock.json"
    lock.write_text(json.dumps({"groups": {"qwen-tokenizer": [{"model_id": "Qwen/Qwen3.5-2B"}]}}))
    monkeypatch.setattr(artifacts, "ROOT", tmp_path / "program")
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", lock)
    monkeypatch.setattr(artifacts, "download", lambda *args, **kwargs: pytest.fail("unexpected download"))
    with pytest.raises(ValueError, match="absent du verrou"):
        artifacts.provision_artifacts("qwen-tokenizer", tokenizer_model_id="unknown")


def test_real_provision_selects_tokenizer_without_a_host_probe(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(cli, "load_profile", lambda path: {"llm": {"tokenizer_model_id": "Qwen/Qwen3.5-2B"}})
    monkeypatch.setattr(cli, "host_signals", lambda: pytest.fail("unnecessary host probe"))
    monkeypatch.setattr(cli, "provision_artifacts", lambda *args, **kwargs: called.append((args, kwargs)))
    assert cli.provision(tmp_path / "profile.yaml", only="qwen-tokenizer")["artifacts"] == "verified"
    assert called[0][1]["tokenizer_model_id"] == "Qwen/Qwen3.5-2B"


def test_two_b_lock_keeps_the_exact_official_tag_and_layer_order():
    lock = json.loads((ROOT / "config/models.lock.json").read_text())
    model = lock["models"]["qwen3.5:2b"]
    assert model["manifest_sha256"] == "0689d44085e06d165161a8a9a1731344278cfb5aade63a3c3dbdb48ab54b130a"
    assert model["quantization"] == "Q8_0"
    assert [layer["mediaType"].rsplit(".", 1)[1] for layer in model["layers"]] == ["projector", "model", "template", "license", "params"]
    assert model["layers"][1]["size"] == 2012012448


@pytest.mark.parametrize("digest", ["b" * 64, "source", None, False])
def test_real_model_record_rejects_http_digest_before_show_or_publication(monkeypatch, tmp_path, digest):
    lock = tmp_path / "models.lock.json"
    lock.write_text(json.dumps({"models": {"qwen3.5:2b": {"manifest_sha256": "a" * 64}}}))
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    calls = []
    client = SimpleNamespace(
        get=lambda url: SimpleNamespace(json=lambda: {"models": [{"name": "qwen3.5:2b", "digest": digest,
            "details": {"quantization_level": "Q8_0"}}]}),
        post=lambda *args, **kwargs: calls.append("show"),
    )
    with pytest.raises(RuntimeError, match="Digest Ollama"):
        cli._model_record(client, "http://explicit-double", "qwen3.5:2b", "Q8_0")
    assert calls == []


def test_real_model_record_accepts_only_locked_digest_and_quantization(monkeypatch, tmp_path):
    lock = tmp_path / "models.lock.json"
    lock.write_text(json.dumps({"models": {"qwen3.5:2b": {"manifest_sha256": "a" * 64}}}))
    monkeypatch.setattr(cli, "MODELS_LOCK", lock)
    model = {"name": "qwen3.5:2b", "digest": "a" * 64, "details": {"quantization_level": "Q8_0"}}
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"model_info": {"source": "explicit_double"}})
    client = SimpleNamespace(get=lambda url: SimpleNamespace(json=lambda: {"models": [model]}),
                             post=lambda *args, **kwargs: response)
    assert cli._model_record(client, "http://explicit-double", "qwen3.5:2b", "Q8_0")[0] is model
    with pytest.raises(RuntimeError, match="Quantification"):
        cli._model_record(client, "http://explicit-double", "qwen3.5:2b", "Q4_K_M")


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_model_pull_dns_is_scoped_to_provisioning_and_keeps_normal_environment(monkeypatch, tmp_path, platform):
    original = {"OLLAMA_NO_CLOUD": "1", "OLLAMA_HOST": "127.0.0.1:11444"}
    monkeypatch.setattr(cli.sys, "platform", platform)
    monkeypatch.setattr(cli, "environment", lambda *args: dict(original))
    monkeypatch.setenv("GODEBUG", "netdns=go,foreign=1")
    normal = cli.environment({}, tmp_path, tmp_path / "profile.yaml")
    pulled = cli.model_pull_environment({}, tmp_path, tmp_path / "profile.yaml")
    assert normal == original and "GODEBUG" not in normal
    assert pulled == ({**original, "GODEBUG": "netdns=cgo"} if platform == "linux" else original)
