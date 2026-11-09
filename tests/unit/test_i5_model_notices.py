"""Notices from explicit model identities and synthetic delivered inventories.

No build, model, native engine or download is exercised. Historical rendering
is checked separately from the identities passed by current kit builders.
"""

import copy
import json
from pathlib import Path

import pytest

from tools.dist.notices import artifact_rows, third_party_notices

MODEL = "qwen3-4b-enhanced:q4km"
TOKENIZER = ".runtime/models/qwen3-4b-tokenizer/tokenizer.json"
WEIGHTS = ".runtime/models/ollama/blobs/sha256-" + "a" * 64
NATIVE_TITLE = "## Modèle Qwen3-4B natif"
HISTORICAL_TITLE = "## Modification du modèle Qwen3.5-4B"


@pytest.fixture
def lock():
    def entry(model, target):
        return {"model_id": model, "target": target, "revision": "pinned-revision",
                "license": "Apache-2.0", "publisher": "synthetic-publisher",
                "url": "https://example.invalid/" + model + "/artifact"}

    return {"groups": {
        "qwen-4b-gguf": [entry(MODEL, WEIGHTS)],
        "qwen-tokenizer": [entry("Qwen/Qwen3-4B", TOKENIZER),
                           entry("Qwen/Qwen3.5-2B", ".runtime/models/qwen3.5-2b-tokenizer/tokenizer.json"),
                           entry("Qwen/Qwen3.5-4B", ".runtime/models/qwen3.5-4b-tokenizer/tokenizer.json")],
        "e5": [entry("intfloat/multilingual-e5-small", ".runtime/models/e5/model.onnx")],
        "tesseract-source": [{"version": "5.4.0", "platform": ["linux-aarch64", "linux-x86_64"],
                              "license": "Apache-2.0", "target": ".runtime/cache/downloads/tesseract.tar.gz"}],
    }}


@pytest.mark.parametrize("platform", ["windows-x86_64", "linux-aarch64", "linux-x86_64"])
def test_enhanced_identity_overrides_the_historical_4b_set_and_excludes_unshipped_tokenizers(tmp_path, lock, platform):
    files = [TOKENIZER, WEIGHTS, ".runtime/models/e5/model.onnx"]
    before = copy.deepcopy(lock), files.copy()
    notice = third_party_notices(tmp_path, files, "0.1.0", platform, lock=lock,
                                models=("4b",), model_names=(MODEL,))
    assert NATIVE_TITLE in notice and "Qwen3-4B-Q4_K_M.gguf" in notice
    assert f"| {MODEL} |" in notice and "| Qwen/Qwen3-4B |" in notice
    assert "| intfloat/multilingual-e5-small |" in notice
    assert HISTORICAL_TITLE not in notice and "Qwen3.5" not in notice and "qwen3.5" not in notice
    assert "section 4 b" not in notice and "v.*" not in notice and "mm.*" not in notice
    assert "GGUF conserve son empreinte verrouillée" in notice
    assert "## Manques connus" in notice and "W030" in notice
    assert (lock, files) == before


@pytest.mark.parametrize("model_names", [(), ("another:4b",), ("qwen3.5:4b",)])
def test_4b_size_or_source_tag_alone_does_not_claim_a_native_import_or_tensor_modification(tmp_path, lock, model_names):
    notice = third_party_notices(tmp_path, [], "0.1.0", lock=lock, models=("4b",), model_names=model_names)
    assert NATIVE_TITLE not in notice and HISTORICAL_TITLE not in notice


def test_explicit_archived_derived_identity_keeps_its_actual_modification_notice(tmp_path, lock):
    files = [".runtime/models/qwen3.5-4b-tokenizer/tokenizer.json"]
    notice = third_party_notices(tmp_path, files, "0.1.0", "linux-aarch64", lock=lock,
                                models=(), model_names=("qwen3.5:4b", "qwen3.5:4b-text"))
    assert HISTORICAL_TITLE in notice and "section 4 b" in notice and "v.*" in notice
    assert "| Qwen/Qwen3.5-4B |" in notice
    assert "| Qwen/Qwen3.5-2B |" not in notice and "| Qwen/Qwen3-4B |" not in notice
    assert NATIVE_TITLE not in notice


@pytest.mark.parametrize("models,expected", [(None, True), (("4b",), True), (("2b",), False)])
def test_old_manifest_reader_keeps_the_historical_model_set_semantics(tmp_path, lock, models, expected):
    notice = third_party_notices(tmp_path, [], "archived-version", lock=lock, models=models)
    assert (HISTORICAL_TITLE in notice) is expected
    assert NATIVE_TITLE not in notice


def test_selected_model_rows_require_exact_payload_paths_but_keep_compiled_source_notices(lock):
    rows = artifact_rows(lock, [TOKENIZER + ".bak", WEIGHTS + "-foreign"], "linux-aarch64", delivered_models_only=True)
    assert {row["component"] for row in rows} == {"tesseract-source"}
    # The old reader remains able to describe the declarations of an archived lock.
    historical = artifact_rows(lock, [], "linux-aarch64")
    assert {row["component"] for row in historical} >= {MODEL, "Qwen/Qwen3.5-2B", "Qwen/Qwen3.5-4B"}


def test_a_model_archive_is_listed_only_when_its_extracted_directory_is_delivered():
    lock = {"groups": {"layout": [{"model_id": "publisher/layout", "revision": "revision",
                                  "extract_to": ".runtime/models/layout"}]}}
    assert artifact_rows(lock, [".runtime/models/layout-other/model.bin"], delivered_models_only=True) == []
    rows = artifact_rows(lock, [".runtime/models/layout/model.bin"], delivered_models_only=True)
    assert [row["component"] for row in rows] == ["publisher/layout"]


def test_notice_names_only_license_texts_in_the_delivered_inventory(tmp_path, lock):
    license_path = ".runtime/models/qwen3-4b-tokenizer/LICENSE"
    absent = third_party_notices(tmp_path, [TOKENIZER, WEIGHTS], "0.1.0", lock=lock, model_names=(MODEL,))
    assert license_path not in absent
    assert next(line for line in absent.splitlines() if line.startswith("| Qwen/Qwen3-4B |")).endswith("| aucun |")
    present = third_party_notices(tmp_path, [TOKENIZER, WEIGHTS, license_path], "0.1.0", lock=lock, model_names=(MODEL,))
    assert f"`{license_path}`" in present
    assert "déclaration de licence ne remplace pas un texte absent" in present


def test_current_locked_inventory_does_not_advertise_excluded_historical_tokenizers(tmp_path):
    root = Path(__file__).resolve().parents[2]
    lock = json.loads((root / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    # Names only: no real model bytes or their license contents are read here.
    files = [entry["target"] for group in ("qwen-tokenizer", "qwen-4b-gguf")
             for entry in lock["groups"][group] if entry["model_id"] in (MODEL, "Qwen/Qwen3-4B")]
    notice = third_party_notices(tmp_path, files, "0.1.0", "linux-aarch64", lock=lock,
                                models=("4b",), model_names=(MODEL,))
    assert NATIVE_TITLE in notice and "| Qwen/Qwen3-4B |" in notice
    assert "Qwen3.5" not in notice and "qwen3.5" not in notice
