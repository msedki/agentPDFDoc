"""Distribution policy on explicit synthetic filenames and lock declarations.

No model bytes, renderer, native process or network is accessed. The root-wrapper
tests write only tiny YAML/JSON fixtures; they do not qualify a built installation
or prove the SHA-256 of a real model. Generic payload filtering is kept separate
from the held-out corpus and its oracles.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from services.runtime import artifacts
from services.runtime.profile_schema import ProfileValidationError
from tools.dist.generation_payload import filter_generation_files, single_generator_files

MODEL = "qwen3-4b-enhanced:q4km"
STORE = ".runtime/models/ollama"
TOKENIZER = ".runtime/models/qwen3-tokenizer"
MANIFEST = "manifests/registry.ollama.ai/library/qwen3-4b-enhanced/q4km"
PROFILE = "config/enhanced-4b.yaml"
ROOT = Path(__file__).resolve().parents[2]
AUXILIARY_ROOTS = [("llm", "tokenizer_dir"), ("embedding", "local_dir"),
                   ("pdf", "artifacts_path"), ("pdf", "tessdata_dir")]


@pytest.fixture
def payload():
    profile = {
        "schema_version": 2,
        "llm": {"provider": "ollama", "model": MODEL, "source_model": MODEL,
                "required_family": "qwen3", "required_parameter_size": "4.0B",
                "required_quantization": "Q4_K_M", "think": False, "tokenizer_dir": TOKENIZER},
        "embedding": {"local_dir": ".runtime/models/e5-small"},
        "pdf": {"artifacts_path": ".runtime/models/docling", "tessdata_dir": ".runtime/models/tessdata"},
        "enhanced": {"preserve_evidence": True, "answer_contract": True,
                     "explicit_pdf_lists": True, "property_coverage_selection": True},
        "retrieval": {"history_is_evidence": False},
    }
    config = {"digest": "sha256:" + "c" * 64, "size": 7}
    layers = [{"digest": "sha256:" + "a" * 64, "size": 13},
              {"digest": "sha256:" + "b" * 64, "size": 9}]
    lock = {"schema_version": 1, "store": STORE, "models": {
        MODEL: {"manifest_path": MANIFEST, "manifest_sha256": "f" * 64, "config": config, "layers": layers},
        "qwen3.5:2b": {"manifest_path": "manifests/registry.ollama.ai/library/qwen3.5/2b",
                       "config": {"digest": "sha256:" + "d" * 64, "size": 3}, "layers": []},
    }}
    enhanced = {"schema_version": 1, "model": MODEL,
                "gguf": {"filename": "Qwen3-4B-Q4_K_M.gguf", "sha256": "a" * 64, "size": 13},
                "tokenizer": {"files": {"tokenizer.json": "d" * 64, "tokenizer_config.json": "e" * 64}}}
    native = [STORE + "/" + MANIFEST]
    for layer in [config, *layers]:
        digest = layer["digest"].replace(":", "-")
        native += [STORE + "/blobs/" + digest, STORE + "/metadata/" + digest + ".json"]
    required = [STORE + "/" + MANIFEST, *(STORE + "/blobs/" + layer["digest"].replace(":", "-") for layer in [config, *layers])]
    documentary = ["README.md", "services/api/query.py", PROFILE,
                   ".runtime/bin/tesseract/tesseract", ".runtime/models/e5-small/model.onnx",
                   ".runtime/models/e5-small/tokenizer.json", ".runtime/models/e5-small/model.safetensors",
                   ".runtime/models/docling/layout/model.safetensors", ".runtime/models/docling/tableformer/model.pt",
                   ".runtime/models/tessdata/eng.traineddata", ".runtime/models/tessdata/fra.traineddata"]
    tokenizer = [TOKENIZER + "/tokenizer.json", TOKENIZER + "/tokenizer_config.json"]
    kept = [*documentary, *native, *tokenizer, ".runtime/models/Qwen3-4B-Q4_K_M.gguf"]
    excluded = [".runtime/models/another-generator.gguf", ".runtime/models/old-store/blobs/sha256-" + "a" * 64,
                STORE + "/manifests/registry.ollama.ai/library/qwen3.5/2b", STORE + "/blobs/sha256-" + "d" * 64,
                STORE + "/metadata/sha256-" + "d" * 64 + ".json", ".runtime/models/old-tokenizer/tokenizer.json",
                TOKENIZER + "/another-generator.gguf", TOKENIZER + "/model.safetensors",
                TOKENIZER + "/nested/tokenizer.json", TOKENIZER + "-other/model.safetensors",
                ".runtime/models/docling-other/model.safetensors"]
    return {"profile": profile, "lock": lock, "enhanced": enhanced, "kept": kept,
            "required": required, "excluded": excluded}


def filtered(payload, files=None):
    return filter_generation_files(payload["kept"] if files is None else files,
                                   payload["profile"], payload["lock"], payload["enhanced"])


def test_only_the_locked_generator_and_documentary_models_are_retained(payload):
    before = copy.deepcopy(payload)
    files = [*payload["excluded"][:3], *payload["kept"], *payload["excluded"][3:]]
    original_files = files.copy()
    assert filtered(payload, files) == payload["kept"]
    assert files == original_files and payload == before


@pytest.mark.parametrize("required_index", range(4), ids=["manifest", "config", "weights", "parameters"])
def test_each_locked_native_component_is_required_even_when_the_raw_gguf_is_present(payload, required_index):
    missing = payload["required"][required_index]
    with pytest.raises(ValueError):
        filtered(payload, [name for name in payload["kept"] if name != missing])


def test_a_native_import_does_not_require_a_second_copy_of_the_raw_gguf(payload):
    files = [name for name in payload["kept"] if not name.endswith(".gguf")]
    assert filtered(payload, files) == files


@pytest.mark.parametrize("missing", [None, [], "historical-only"])
def test_missing_generator_lock_is_refused(payload, missing):
    if missing == "historical-only":
        del payload["lock"]["models"][MODEL]
    else:
        payload["lock"]["models"][MODEL] = missing
    with pytest.raises(ValueError):
        filtered(payload)


@pytest.mark.parametrize("legacy", ["qwen3.5:2b", "qwen3.5:4b-text"])
def test_legacy_profiles_are_refused_before_any_payload_is_returned(payload, legacy):
    payload["profile"]["llm"]["model"] = legacy
    with pytest.raises(ProfileValidationError) as refused:
        filtered(payload)
    assert "llm.model" in refused.value.keys


def test_disabling_evidence_checks_cannot_build_a_nominal_4b_kit(payload):
    payload["profile"]["enhanced"]["answer_contract"] = False
    with pytest.raises(ProfileValidationError) as refused:
        filtered(payload)
    assert "enhanced.answer_contract" in refused.value.keys


@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", r"C:\outside",
                                 "config//other.yaml", "config/./other.yaml", "config/../other.yaml",
                                 r"config\other.yaml", ".runtime/models/../foreign.gguf"])
def test_unsafe_payload_names_are_refused_instead_of_copied_or_silently_discarded(payload, path):
    with pytest.raises(ValueError):
        filtered(payload, [*payload["kept"], path])


@pytest.mark.parametrize("field", ["store", "manifest", "gguf", "tokenizer-file"])
@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", r"folder\outside"])
def test_unsafe_locked_paths_are_refused(payload, field, path):
    if field == "store":
        payload["lock"]["store"] = path
    elif field == "manifest":
        payload["lock"]["models"][MODEL]["manifest_path"] = path
    elif field == "gguf":
        payload["enhanced"]["gguf"]["filename"] = path
    else:
        payload["enhanced"]["tokenizer"]["files"][path] = "a" * 64
    with pytest.raises(ValueError):
        filtered(payload)


@pytest.mark.parametrize("digest", ["md5:" + "a" * 32, "sha256:" + "a" * 63, "sha256:" + "G" * 64,
                                   "sha256:../../foreign", "", None, 12])
@pytest.mark.parametrize("layer", ["config", "weights"])
def test_layer_digests_cannot_be_used_as_unchecked_paths(payload, digest, layer):
    model = payload["lock"]["models"][MODEL]
    selected = model["config"] if layer == "config" else model["layers"][0]
    selected["digest"] = digest
    with pytest.raises(ValueError):
        filtered(payload)


@pytest.mark.parametrize("section,key", AUXILIARY_ROOTS)
@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", ".runtime/models",
                                 STORE, STORE + "/blobs"])
def test_auxiliary_roots_cannot_escape_or_overlap_the_generative_store(payload, section, key, path):
    payload["profile"][section][key] = path
    with pytest.raises(ValueError):
        filtered(payload, [*payload["kept"], *payload["excluded"]])


def write_program(root, payload):
    profile_path = root / PROFILE
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(yaml.safe_dump(payload["profile"]), encoding="utf-8")
    catalogue = {"schema_version": 1, "legacy_default_model": MODEL, "profiles": [
        {"id": "synthetic-enhanced", "kit_set": "4b", "model": MODEL, "served_model": MODEL,
         "profile": PROFILE, "pins": {PROFILE: hashlib.sha256(profile_path.read_bytes()).hexdigest()},
         "qualification": None}
    ]}
    for name, data in [("model_profiles.json", catalogue), ("models.lock.json", payload["lock"]),
                       ("enhanced-4b.lock.json", payload["enhanced"])]:
        (root / "config" / name).write_text(json.dumps(data), encoding="utf-8")
    return catalogue


def test_root_wrapper_reads_the_single_profile_and_both_locks_without_loading_weights(tmp_path, payload):
    write_program(tmp_path, payload)
    assert single_generator_files(tmp_path, [*payload["kept"], *payload["excluded"]]) == payload["kept"]
    assert not (tmp_path / ".runtime").exists()


@pytest.mark.parametrize("variant", ["missing", "legacy-only", "extra-legacy", "wrong-served"])
def test_missing_or_ambiguous_catalogue_cannot_build_a_single_generator_kit(tmp_path, payload, variant):
    catalogue = write_program(tmp_path, payload)
    path = tmp_path / "config/model_profiles.json"
    if variant == "missing":
        path.unlink()
    else:
        legacy = copy.deepcopy(catalogue["profiles"][0])
        legacy.update(id="historical", kit_set="2b", model="qwen3.5:2b", served_model="qwen3.5:2b")
        if variant == "legacy-only":
            catalogue["profiles"] = [legacy]
            catalogue["legacy_default_model"] = "qwen3.5:2b"
        elif variant == "extra-legacy":
            catalogue["profiles"].append(legacy)
        else:
            catalogue["profiles"][0]["served_model"] = "qwen3.5:2b"
        path.write_text(json.dumps(catalogue), encoding="utf-8")
    with pytest.raises(ValueError):
        single_generator_files(tmp_path, payload["kept"])


def test_delivered_tokenizer_artifact_declarations_match_the_enhanced_lock_and_profile():
    """Cohérence des déclarations livrées ; aucun téléchargement ni hash de poids réel."""
    profile = yaml.safe_load((ROOT / PROFILE).read_text(encoding="utf-8"))
    enhanced = json.loads((ROOT / "config/enhanced-4b.lock.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    tokenizer = enhanced["tokenizer"]
    assert tokenizer["repository"] == "Qwen/Qwen3-4B"
    entries = [entry for entry in lock["groups"]["qwen-tokenizer"] if entry.get("model_id") == tokenizer["repository"]]
    expected = {profile["llm"]["tokenizer_dir"] + "/" + name: digest for name, digest in tokenizer["files"].items()}
    assert len(entries) == len(expected) == 2
    assert {entry["target"]: entry["sha256"] for entry in entries} == expected
    for entry in entries:
        filename = Path(entry["target"]).name
        assert entry["revision"] == tokenizer["revision"]
        assert entry["url"] == f"https://huggingface.co/{tokenizer['repository']}/resolve/{tokenizer['revision']}/{filename}"
        assert type(entry["size"]) is int and entry["size"] > 0


def test_direct_artifact_provision_defaults_to_only_the_locked_enhanced_tokenizer(tmp_path, monkeypatch):
    """Vrai sélecteur, downloader enregistré et octets fictifs ; aucun modèle chargé."""
    program = tmp_path / "synthetic-program"
    program.mkdir()
    monkeypatch.setattr(artifacts, "ROOT", program)
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", ROOT / "config/artifacts.lock.json")
    downloads = []

    def download_double(entry, target, **kwargs):
        downloads.append((entry["model_id"], target.relative_to(program).as_posix(), kwargs))
        return {**entry, "path": entry["target"], "cached": True}

    monkeypatch.setattr(artifacts, "download", download_double)
    manifest = artifacts.provision_artifacts("qwen-tokenizer", offline=True)
    assert downloads == [
        ("Qwen/Qwen3-4B", ".runtime/models/qwen3-4b-tokenizer/tokenizer.json", {"offline": True}),
        ("Qwen/Qwen3-4B", ".runtime/models/qwen3-4b-tokenizer/tokenizer_config.json", {"offline": True}),
    ]
    assert [entry["model_id"] for entry in manifest["qwen-tokenizer"]] == ["Qwen/Qwen3-4B"] * 2
    assert not (program / ".runtime/models").exists()


def test_delivered_gguf_download_is_the_same_locked_native_model_without_a_second_copy():
    enhanced = json.loads((ROOT / "config/enhanced-4b.lock.json").read_text(encoding="utf-8"))
    native = json.loads((ROOT / "config/models.lock.json").read_text(encoding="utf-8"))
    artifacts_lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    entries = artifacts_lock["groups"]["qwen-4b-gguf"]
    assert len(entries) == 1
    entry, expected = entries[0], enhanced["gguf"]
    assert entry["model_id"] == enhanced["model"] == MODEL
    for field in ("url", "revision", "sha256", "size"):
        assert entry[field] == expected[field]
    assert entry["target"] == native["store"] + "/blobs/sha256-" + expected["sha256"]
    layers = native["models"][MODEL]["layers"]
    assert any(layer["digest"] == "sha256:" + expected["sha256"] and layer["size"] == expected["size"] for layer in layers)


def test_linux_kit_requires_the_enhanced_runtime_and_importer_before_it_can_be_built():
    from tools.dist.linux_kit import required_for_build

    assert {"services/runtime/generation_policy.py", "tools/dist/generation_payload.py",
            "tools/qualification/provision_enhanced_4b.py", "config/enhanced-4b.lock.json",
            "config/enhanced-4b.yaml", "config/model_profiles.json"} <= set(required_for_build())
