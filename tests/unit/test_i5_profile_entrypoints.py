"""Live-entry policy checks with real YAML readers and no native services.

Filesystem profiles are real; process launch is replaced by an explicit failing
sentinel or a recording double. These tests do not qualify model bytes, a native
installation, resource limits or answer quality.
"""

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

from services.api.errors import ApiError
from services.api.settings import Settings
from services.runtime import cli, supervisor
from services.runtime.generation_policy import require_generation_profile
from services.runtime.model_profiles import read_catalogue
from services.runtime.profile_schema import ProfileValidationError

ROOT = Path(__file__).resolve().parents[2]
ENHANCED_PATH = ROOT / "config/enhanced-4b.yaml"
MODEL = "qwen3-4b-enhanced:q4km"
ARCHIVES = ["config/local16.yaml", "config/local16-4b.yaml",
            "RAG_Local_Agents/config/local16.yaml", "RAG_Local_Agents/config/local16-4b.yaml"]
# Each entry is a separate invariant of the frozen entry-point addendum, not a
# copy imported from the implementation's policy dictionary.
POLICY_VIOLATIONS = [
    ("schema_version", 1),
    ("llm.provider", "remote-provider"),
    ("llm.model", "qwen3.5:2b"),
    ("llm.source_model", "qwen3.5:4b"),
    ("llm.required_family", "qwen35"),
    ("llm.required_parameter_size", "2.0B"),
    ("llm.required_quantization", "Q8_0"),
    ("llm.think", True),
    ("enhanced.preserve_evidence", False),
    ("enhanced.answer_contract", False),
    ("enhanced.explicit_pdf_lists", False),
    ("enhanced.property_coverage_selection", False),
    ("retrieval.history_is_evidence", True),
]


@pytest.fixture(autouse=True)
def isolated_cli_profile_context(monkeypatch):
    # CLI use_profile mutates a process-local presentation context. Restore it
    # after each test so this suite cannot affect later launcher/UI checks.
    monkeypatch.setattr("services.runtime.platforms._profile_in_use", None)


def enhanced_profile():
    return yaml.safe_load(ENHANCED_PATH.read_text(encoding="utf-8"))


def write_profile(tmp_path, profile):
    path = tmp_path / "explicit-profile.yaml"
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return path


def change(profile, dotted_key, value, *, missing=False):
    node = profile
    *parents, key = dotted_key.split(".")
    for part in parents:
        node = node[part]
    if missing:
        del node[key]
    else:
        node[key] = value


def assert_enhanced(settings):
    assert settings.value("llm", "model") == settings.value("llm", "source_model") == MODEL
    assert settings.value("llm", "required_family") == "qwen3"
    assert settings.value("llm", "required_parameter_size") == "4.0B"
    assert settings.value("llm", "required_quantization") == "Q4_K_M"
    assert settings.value("llm", "think") is False
    for flag in ("preserve_evidence", "answer_contract", "explicit_pdf_lists", "property_coverage_selection"):
        assert settings.value("enhanced", flag) is True
    assert settings.value("retrieval", "history_is_evidence") is False


def test_api_without_environment_selects_the_enhanced_4b_profile(monkeypatch):
    monkeypatch.delenv("RAG_PROFILE", raising=False)
    settings = Settings.load()
    assert settings.profile == enhanced_profile()
    assert_enhanced(settings)


@pytest.mark.parametrize("selection", ["argument", "environment"])
def test_explicit_enhanced_profile_is_loaded_without_rewriting_it(tmp_path, monkeypatch, selection):
    profile = enhanced_profile()
    profile["app"]["data_dir"] = str(tmp_path / "Existing user data")
    path = write_profile(tmp_path, profile)
    before = path.read_bytes()
    if selection == "environment":
        monkeypatch.setenv("RAG_PROFILE", str(path))
        loaded = Settings.load()
    else:
        monkeypatch.setenv("RAG_PROFILE", str(ROOT / ARCHIVES[0]))
        loaded = Settings.load(path)
    assert_enhanced(loaded)
    assert loaded.profile == profile and path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("selection", ["argument", "environment"])
@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "invalid_yaml"])
def test_invalid_profile_path_or_document_never_falls_back_to_another_model(tmp_path, monkeypatch, selection, kind):
    if kind == "directory":
        value = str(tmp_path)
    elif kind == "empty":
        value = ""
    elif kind == "invalid_yaml":
        invalid = tmp_path / "broken.yaml"
        invalid.write_text("llm: [unterminated", encoding="utf-8")
        value = str(invalid)
    else:
        value = str(tmp_path / "missing.yaml")
    # Even with a valid alternative available, an explicit invalid selection
    # must be rejected rather than replaced by the default or historical copy.
    monkeypatch.setenv("RAG_PROFILE", value if selection == "environment" else str(ENHANCED_PATH))
    with pytest.raises(ApiError) as refused:
        Settings.load() if selection == "environment" else Settings.load(value)
    assert refused.value.code == "invalid_profile" and refused.value.status == 400
    assert not (tmp_path / "control").exists()


@pytest.mark.parametrize("relative", ARCHIVES)
def test_archived_profiles_remain_readable_but_cannot_load_a_live_api(relative):
    path = ROOT / relative
    before = path.read_bytes()
    historical = supervisor.load_profile(path)
    assert historical == yaml.safe_load(before)
    with pytest.raises(ApiError) as refused:
        Settings.load(path)
    assert refused.value.code == "invalid_profile"
    assert "llm.model" in refused.value.details["keys"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("dotted_key,value", POLICY_VIOLATIONS, ids=[item[0] for item in POLICY_VIOLATIONS])
@pytest.mark.parametrize("missing", [False, True], ids=["altered", "missing"])
def test_generation_policy_refuses_each_missing_or_changed_trust_invariant_without_repair(dotted_key, value, missing):
    profile = enhanced_profile()
    change(profile, dotted_key, value, missing=missing)
    before = copy.deepcopy(profile)
    with pytest.raises(ProfileValidationError) as refused:
        require_generation_profile(profile)
    assert dotted_key in refused.value.keys
    assert profile == before


@pytest.mark.parametrize("dotted_key,value", [
    ("schema_version", 2.0), ("llm.think", 0),
    ("enhanced.answer_contract", 1), ("retrieval.history_is_evidence", 0),
])
def test_policy_does_not_accept_numeric_substitutes_for_boolean_or_schema_types(dotted_key, value):
    profile = enhanced_profile()
    change(profile, dotted_key, value)
    with pytest.raises(ProfileValidationError) as refused:
        require_generation_profile(profile)
    assert dotted_key in refused.value.keys


@pytest.mark.parametrize("dotted_key,value", [
    ("llm.model", "qwen3.5:2b"), ("enhanced.answer_contract", False),
    ("enhanced.preserve_evidence", False), ("llm.required_parameter_size", "8.0B"),
])
def test_real_api_loader_applies_the_generation_policy_after_schema_validation(tmp_path, dotted_key, value):
    profile = enhanced_profile()
    change(profile, dotted_key, value)
    path = write_profile(tmp_path, profile)
    before = path.read_bytes()
    with pytest.raises(ApiError) as refused:
        Settings.load(path)
    assert refused.value.code == "invalid_profile" and dotted_key in refused.value.details["keys"]
    assert path.read_bytes() == before and list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("entrypoint", ["start", "supervise"])
@pytest.mark.parametrize("relative", ARCHIVES[:2])
def test_supervisor_refuses_historical_generation_before_data_directory_or_process_work(monkeypatch, entrypoint, relative):
    reached = []

    def forbidden_directory_work(profile):
        reached.append(profile)
        raise AssertionError("Generation policy must reject before runtime directory or native work")

    monkeypatch.setattr(supervisor, "data_path", forbidden_directory_work)
    with pytest.raises(ProfileValidationError):
        getattr(supervisor, entrypoint)(ROOT / relative)
    assert reached == []


def test_cli_default_and_explicit_supported_model_select_the_same_enhanced_profile(monkeypatch, capsys):
    assert cli.model_profile_path(None, None) == ENHANCED_PATH
    assert cli.model_profile_path(None, MODEL) == ENHANCED_PATH
    calls = []
    monkeypatch.setattr(sys, "argv", ["rag", "up"])
    monkeypatch.setattr(cli, "start", lambda path: calls.append(path) or {"status": "explicit_launch_double"})
    assert cli.main() == 0 and calls == [ENHANCED_PATH]
    assert json.loads(capsys.readouterr().out)["status"] == "explicit_launch_double"


@pytest.mark.parametrize("model", ["qwen3.5:2b", "qwen3.5:4b", "qwen3.5:4b-text"])
def test_cli_rejects_legacy_model_choice_before_launch(monkeypatch, capsys, model):
    calls = []
    monkeypatch.setattr(sys, "argv", ["rag", "up", "--model", model])
    monkeypatch.setattr(cli, "start", lambda path: calls.append(path) or {"status": "must_not_start"})
    assert cli.main() != 0 and calls == []
    capsys.readouterr()


def test_nominal_catalogue_exposes_only_the_enhanced_generator_without_qualification_claims():
    catalogue = read_catalogue(ROOT)
    assert catalogue is not None
    assert catalogue["legacy_default_model"] == MODEL
    assert {item["model"] for item in catalogue["profiles"]} == {MODEL}
    assert {item["served_model"] for item in catalogue["profiles"]} == {MODEL}
    assert {item["profile"] for item in catalogue["profiles"]} == {"config/enhanced-4b.yaml"}
    assert all(item["qualification"] is None for item in catalogue["profiles"])
