"""Explicit Linux profile migration using tiny files and real validators.

No installation, service, model, network or native inference is run. Script
tests use the isolated Python entry point with only the declared source files;
historical profiles remain separate, readable migration inputs.
"""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from services.runtime.generation_policy import GENERATION_MODEL, require_generation_profile
from services.runtime.profile_schema import validate_profile
from tools.dist import linux_install, linux_profiles

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = "config/enhanced-4b.yaml"
LOAD_ESTIMATES = ("initial_llm_load_peak_estimate_mib", "warm_llm_additional_peak_estimate_mib")


def write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


@pytest.fixture
def migration(tmp_path):
    program = tmp_path / "new-program"
    template = yaml.safe_load((ROOT / TEMPLATE).read_text(encoding="utf-8"))
    write_yaml(program / TEMPLATE, template)
    manifest = program / "kit-manifest.json"
    manifest.write_text(json.dumps({"model_profiles": {GENERATION_MODEL: TEMPLATE}}), encoding="utf-8")
    source = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    user = tmp_path / "user-data"
    source["app"].update(data_dir=str(user / "documents"), port=18785)
    source["qdrant"].update(url="http://127.0.0.1:16333", storage_dir=str(user / "vectors"))
    source["sqlite"]["path"] = str(user / "sqlite/custom.sqlite3")
    source["runtime"] = {name: str(user / name) for name in linux_profiles.WRITE_KEYS}
    source["llm"].update(base_url="http://127.0.0.1:21434", num_predict=128,
                         output_tokens_by_mode={mode: 128 for mode in ("factual", "ordinary", "analysis", "compare")})
    source["enhanced"] = {"preserve_evidence": False, "answer_contract": False,
                           "explicit_pdf_lists": False, "property_coverage_selection": False}
    source["retrieval"].update(dense_top_k=17, history_is_evidence=True)
    source["security"].update(environment="production", tls_cert_file=str(user / "tls/cert.pem"),
                               tls_key_file=str(user / "tls/key.pem"), session_idle_minutes=31)
    source["resources"].update(host_available_min_mib=2048, generation_admission_wait_seconds=23)
    source["trace"] = {"mode": "hashes", "directory": "custom-traces"}
    like, output = user / "old-profile.yaml", user / "enhanced-profile.yaml"
    write_yaml(like, source)
    return {"program": program, "template": template, "source": source, "like": like,
            "output": output, "manifest": manifest}


def derive(case, *, check=False):
    return linux_profiles.derive(case["like"], GENERATION_MODEL, case["program"], case["output"], check=check)


def inventory(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_single_model_template_replaces_every_model_control_and_only_declared_keys(migration):
    before = inventory(migration["program"].parent)
    result, keys = linux_profiles.derived_profile(migration["like"], GENERATION_MODEL, migration["program"])
    source, template = migration["source"], migration["template"]
    validate_profile(result, consumer="runtime")
    require_generation_profile(result)
    assert result["llm"] == {**template["llm"], "base_url": source["llm"]["base_url"]}
    assert "tokenizer_model_id" not in result["llm"]
    assert result["enhanced"] == template["enhanced"]
    assert result["retrieval"] == {**source["retrieval"], "history_is_evidence": False}
    assert result["resources"] == {**source["resources"], **{key: template["resources"][key] for key in LOAD_ESTIMATES}}
    for section in linux_profiles.PROTECTED:
        assert result[section] == source[section]
    for section in set(source) - {"llm", "enhanced", "retrieval", "resources"}:
        assert result[section] == source[section]
    old, new = linux_profiles.flatten(source), linux_profiles.flatten(result)
    changed = {".".join(key) for key in old.keys() | new.keys()
               if key not in old or key not in new or old[key] != new[key] or type(old[key]) is not type(new[key])}
    assert set(keys) == changed and "llm.model" in keys and "llm.base_url" not in keys
    assert inventory(migration["program"].parent) == before


def test_check_writes_nothing_then_create_and_reuse_are_idempotent(migration):
    before = inventory(migration["program"].parent)
    assert derive(migration, check=True)["status"] == "checked"
    assert inventory(migration["program"].parent) == before
    first = derive(migration)
    assert first["status"] == "created"
    output_bytes = migration["output"].read_bytes()
    second = derive(migration)
    assert second["status"] == "reused" and second["replaced_keys"] == first["replaced_keys"]
    assert migration["output"].read_bytes() == output_bytes
    assert migration["like"].read_bytes() == before[str(migration["like"].relative_to(migration["program"].parent))]
    assert not list(migration["output"].parent.glob(".*.tmp"))
    result, keys = linux_profiles.derived_profile(migration["output"], GENERATION_MODEL, migration["program"])
    assert result == linux_profiles.load(migration["output"]) and keys == []


def test_existing_different_output_and_original_path_are_never_replaced(migration):
    migration["output"].write_text("different: profile\n", encoding="utf-8")
    before = inventory(migration["program"].parent)
    with pytest.raises(ValueError, match="déjà présent"):
        derive(migration)
    with pytest.raises(ValueError, match="déjà présent"):
        linux_profiles.derive(migration["like"], GENERATION_MODEL, migration["program"], migration["like"])
    assert inventory(migration["program"].parent) == before


def test_a_source_filename_cannot_change_the_validated_yaml_document(migration):
    unusual = migration["like"].with_name("old\nunexpected_setting: true\nprofile.yaml")
    original = migration["like"].read_bytes()
    unusual.write_bytes(original)
    migration["like"] = unusual
    expected, _ = linux_profiles.derived_profile(unusual, GENERATION_MODEL, migration["program"])
    assert derive(migration)["status"] == "created"
    assert linux_profiles.load(migration["output"]) == expected
    assert unusual.read_bytes() == original


@pytest.mark.parametrize("variant", ["mixed-models", "outside", "absolute", "noncanonical", "symlink-outside", "missing-model"])
def test_ambiguous_catalogue_or_template_scope_is_refused_without_writes(migration, variant):
    mapping = {GENERATION_MODEL: TEMPLATE}
    if variant == "mixed-models":
        mapping["historical-model"] = "config/historical.yaml"
        write_yaml(migration["program"] / mapping["historical-model"], migration["source"])
    elif variant == "missing-model":
        mapping = {"historical-model": TEMPLATE}
    elif variant == "symlink-outside":
        external = migration["program"].parent / "outside.yaml"
        write_yaml(external, migration["template"])
        path = migration["program"] / TEMPLATE
        path.unlink()
        path.symlink_to(external)
    else:
        mapping[GENERATION_MODEL] = {"outside": "../outside.yaml", "absolute": str(migration["like"]),
                                     "noncanonical": "config/../config/enhanced-4b.yaml"}[variant]
    migration["manifest"].write_text(json.dumps({"model_profiles": mapping}), encoding="utf-8")
    before = inventory(migration["program"].parent)
    for check in (True, False):
        with pytest.raises(ValueError):
            derive(migration, check=check)
    assert inventory(migration["program"].parent) == before


@pytest.mark.parametrize("variant", ["llm-section", "enhanced-section", "resource-section", "retrieval-section",
                                     "security", "unknown-field", "port-collision", "budget-collision"])
def test_invalid_preserved_configuration_is_refused_before_any_temporary_file(migration, variant):
    source = copy.deepcopy(migration["source"])
    if variant.endswith("-section"):
        section = {"resource": "resources"}.get(variant.removesuffix("-section"), variant.removesuffix("-section"))
        source[section] = ["ambiguous"]
    elif variant == "security":
        source["security"]["tls_key_file"] = None
    elif variant == "unknown-field":
        source["unrecognized_migration_option"] = True
    elif variant == "port-collision":
        source["app"]["port"] = 21434
    else:
        source["retrieval"]["max_evidence_llm_tokens"] = 8192
    write_yaml(migration["like"], source)
    before = inventory(migration["program"].parent)
    for check in (True, False):
        with pytest.raises(ValueError):
            derive(migration, check=check)
    assert inventory(migration["program"].parent) == before


@pytest.mark.parametrize("variant", ["model", "control", "missing-estimate", "empty-manifest", "wrong-tokenizer-type"])
def test_invalid_target_template_is_refused_before_writing(migration, variant):
    template = copy.deepcopy(migration["template"])
    if variant == "model":
        template["llm"]["model"] = "historical-model"
    elif variant == "control":
        template["enhanced"]["answer_contract"] = False
    elif variant == "missing-estimate":
        del template["resources"][LOAD_ESTIMATES[0]]
    elif variant == "empty-manifest":
        template["llm"]["model_manifest"] = ""
    else:
        template["llm"]["tokenizer_dir"] = []
    write_yaml(migration["program"] / TEMPLATE, template)
    before = inventory(migration["program"].parent)
    with pytest.raises(ValueError):
        derive(migration)
    assert inventory(migration["program"].parent) == before


@pytest.mark.parametrize("path", ["app.data_dir", "qdrant.storage_dir", "runtime.host_lock_path",
                                  "runtime.backups_dir", "runtime.restore_storage_dir", "runtime.huggingface_cache_dir",
                                  "security.tls_cert_file", "security.tls_key_file", "runtime"])
def test_relative_or_missing_persistent_scope_is_never_reinterpreted(migration, path):
    source = copy.deepcopy(migration["source"])
    if path == "runtime":
        del source["runtime"]
    else:
        section, key = path.split(".")
        source[section][key] = "../old-instance/data"
    write_yaml(migration["like"], source)
    before = inventory(migration["program"].parent)
    for check in (True, False):
        with pytest.raises(ValueError, match="emplacements absolus"):
            derive(migration, check=check)
    assert inventory(migration["program"].parent) == before


def test_missing_qdrant_override_keeps_the_same_absolute_data_fallback(migration):
    source = copy.deepcopy(migration["source"])
    del source["qdrant"]["storage_dir"]
    write_yaml(migration["like"], source)
    result, _ = linux_profiles.derived_profile(migration["like"], GENERATION_MODEL, migration["program"])
    assert "storage_dir" not in result["qdrant"]
    old = linux_profiles.write_locations(source, migration["program"].parent / "old-program")
    new = linux_profiles.write_locations(result, migration["program"])
    assert old == new


def test_profile_created_by_the_real_setup_remains_an_admissible_migration_input(migration, monkeypatch):
    from services.runtime import profile_setup

    # Port availability is unrelated to the profile migration and is doubled;
    # the actual setup code builds the preserved absolute storage locations.
    monkeypatch.setattr(profile_setup, "port_free", lambda _port: True)
    base = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    source = profile_setup.user_profile(base, migration["like"].parent,
        program_root=migration["program"].parent / "old-program")
    write_yaml(migration["like"], source)
    before = migration["like"].read_bytes()
    read = linux_profiles.paths(migration["like"], migration["program"])
    assert read["model"] == "qwen3.5:2b" and migration["like"].read_bytes() == before
    result, _ = linux_profiles.derived_profile(migration["like"], GENERATION_MODEL, migration["program"])
    validate_profile(result, consumer="runtime")
    require_generation_profile(result)
    for section in linux_profiles.PROTECTED:
        assert result[section] == source[section]
    assert migration["like"].read_bytes() == before


def test_historical_archive_derivation_keeps_its_original_scope(tmp_path):
    program = tmp_path / "historical"
    mapping = {"qwen3.5:2b": "config/local16.yaml", "qwen3.5:4b": "config/local16-4b.yaml"}
    for relative in mapping.values():
        write_yaml(program / relative, yaml.safe_load((ROOT / relative).read_text(encoding="utf-8")))
    (program / "kit-manifest.json").write_text(json.dumps({"model_profiles": mapping}), encoding="utf-8")
    like = program / mapping["qwen3.5:2b"]
    before = like.read_bytes()
    result, keys = linux_profiles.derived_profile(like, "qwen3.5:4b", program)
    assert result["llm"]["model"] == "qwen3.5:4b-text"
    assert "llm.model" in keys and like.read_bytes() == before
    assert result["app"] == linux_profiles.load(like)["app"]


def test_isolated_script_uses_only_verified_modules_despite_added_package(migration):
    program = migration["program"]
    for relative in linux_install.PRE_COPY_FILES:
        target = program / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    assert {"services/runtime/profile_schema.py", "services/runtime/generation_policy.py"} <= set(linux_install.PRE_COPY_FILES)
    witness = program.parent / "unexpected-import"
    injected = program / "services/runtime/generation_policy/__init__.py"
    injected.parent.mkdir()
    injected.write_text(f"open({str(witness)!r}, 'w').write('imported')\nraise SystemExit(99)\n", encoding="utf-8")
    completed = subprocess.run([sys.executable, "-B", "-I", "-X", "pycache_prefix=/dev/null",
        str(program / "tools/dist/linux_profiles.py"), "derive", "--like", str(migration["like"]),
        "--model", GENERATION_MODEL, "--program", str(program), "--output", str(migration["output"]), "--check"],
        capture_output=True, text=True, check=False, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["status"] == "checked"
    assert not witness.exists() and not migration["output"].exists()
