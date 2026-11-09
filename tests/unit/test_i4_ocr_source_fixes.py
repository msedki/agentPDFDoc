"""Source-fix integrity with tiny files and a version-script binary double.

No Tesseract build or OCR engine is run here. The native OSD ablation is a
separate recorded experiment; these tests enforce its reproducible provenance.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_runtime_provisioning import installed_copy, lock_entries, write_lock
from test_runtime_provisioning import root as root

from services.ingestion.config import IngestionConfig
from services.runtime import provisioning


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def fix_tree(root):
    before, after = b"before\nold expression\nafter\n", b"before\nchecked expression\nafter\n"
    source_root = root / "extracted/tesseract-5.4.0"
    source = source_root / "src/normalization.cpp"
    source.parent.mkdir(parents=True)
    source.write_bytes(before)
    archive = root / "original-source.tar.gz"
    archive.write_bytes(b"original archive is preserved")
    patch = root / "config/source-fixes/checked.json"
    patch.parent.mkdir()
    patch.write_text(json.dumps({"schema_version": 1, "before": "old expression", "after": "checked expression"}))
    commit = "d" * 40
    fix = {"id": "upstream-test", "upstream_commit": commit,
           "upstream_url": f"https://github.com/tesseract-ocr/tesseract/commit/{commit}",
           "file": "src/normalization.cpp", "before_sha256": sha(before), "after_sha256": sha(after),
           "patch": "config/source-fixes/checked.json", "patch_sha256": sha(patch.read_bytes())}
    entries = lock_entries()
    entries[1]["source_fixes"] = [fix]
    write_lock(root, entries)
    return {"source": source, "dirs": {"tesseract": source_root}, "archive": archive, "patch": patch,
            "before": before, "after": after, "fix": fix, "entries": entries}


def test_exact_backport_is_idempotent_and_preserves_original_archive(root, fix_tree):
    original_archive = fix_tree["archive"].read_bytes()
    receipt = provisioning.apply_source_fixes(fix_tree["dirs"])
    assert fix_tree["source"].read_bytes() == fix_tree["after"]
    assert receipt == [{"source": "tesseract", "version": "5.4.0", **fix_tree["fix"]}]
    assert provisioning.apply_source_fixes(fix_tree["dirs"]) == receipt
    assert fix_tree["archive"].read_bytes() == original_archive
    assert not list(fix_tree["source"].parent.glob("*.fix"))


@pytest.mark.parametrize("damage", ["source", "patch", "before_hash", "after_hash", "patch_hash", "commit", "upstream_url",
                                    "missing_source", "source_escape", "patch_escape", "source_symlink", "patch_symlink"])
def test_tampering_or_incomplete_provenance_refuses_before_source_mutation(root, fix_tree, damage):
    fix = fix_tree["fix"]
    if damage == "source":
        fix_tree["source"].write_bytes(fix_tree["before"] + b"unreviewed change\n")
    elif damage == "patch":
        fix_tree["patch"].write_bytes(fix_tree["patch"].read_bytes() + b" ")
    elif damage in {"before_hash", "after_hash", "patch_hash"}:
        fix[damage.replace("_hash", "_sha256")] = "0" * 64
    elif damage == "commit":
        fix.pop("upstream_commit")
    elif damage == "upstream_url":
        fix["upstream_url"] = "https://example.invalid/unverified-commit"
    elif damage == "missing_source":
        fix_tree["dirs"] = {}
    elif damage == "source_escape":
        fix["file"] = "../outside.cpp"
    elif damage == "patch_escape":
        fix["patch"] = "../outside.json"
    else:
        path = fix_tree["source"] if damage == "source_symlink" else fix_tree["patch"]
        outside = root.parent / (damage + ".txt")
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    write_lock(root, fix_tree["entries"])
    source_before, archive_before = fix_tree["source"].read_bytes(), fix_tree["archive"].read_bytes()
    with pytest.raises(ValueError):
        provisioning.apply_source_fixes(fix_tree["dirs"])
    assert fix_tree["source"].read_bytes() == source_before
    assert fix_tree["archive"].read_bytes() == archive_before


def test_all_source_targets_are_validated_before_first_write(root, fix_tree):
    second = copy.deepcopy(fix_tree["fix"])
    second.update(id="second-test", file="src/missing.cpp")
    fix_tree["entries"][1]["source_fixes"].append(second)
    write_lock(root, fix_tree["entries"])
    with pytest.raises(ValueError, match="Fichier source absent"):
        provisioning.apply_source_fixes(fix_tree["dirs"])
    assert fix_tree["source"].read_bytes() == fix_tree["before"]


def test_receipt_is_not_returned_if_written_source_hash_differs(root, fix_tree, monkeypatch):
    real_replace = provisioning.os.replace

    def damaged_write(temporary, destination):
        real_replace(temporary, destination)
        Path(destination).write_bytes(b"write corruption")

    monkeypatch.setattr(provisioning.os, "replace", damaged_write)
    with pytest.raises(ValueError, match="écrit différent"):
        provisioning.apply_source_fixes(fix_tree["dirs"])


def test_duplicate_fix_target_is_not_applied_twice(root, fix_tree):
    fix_tree["entries"][1]["source_fixes"].append(copy.deepcopy(fix_tree["fix"]))
    write_lock(root, fix_tree["entries"])
    with pytest.raises(ValueError, match="dupliqué"):
        provisioning.apply_source_fixes(fix_tree["dirs"])
    assert fix_tree["source"].read_bytes() == fix_tree["before"]


@pytest.mark.parametrize("damage", ["missing_receipt", "commit", "after_hash", "source_version", "unexpected_receipt"])
def test_old_or_altered_build_receipt_is_rejected_even_with_matching_version_and_binary(root, fix_tree, monkeypatch, damage):
    target, manifest_path = installed_copy(root)
    manifest = json.loads(manifest_path.read_text())
    receipt = provisioning._source_fix_records(provisioning.locked_tesseract_sources())
    if damage != "missing_receipt":
        manifest["source_fixes"] = receipt
        if damage == "commit":
            receipt[0]["upstream_commit"] = "e" * 40
        elif damage == "after_hash":
            receipt[0]["after_sha256"] = "f" * 64
        elif damage == "source_version":
            receipt[0]["version"] = "5.4.1"
        else:
            receipt.append(copy.deepcopy(receipt[0]))
    manifest_path.write_text(json.dumps(manifest))
    original_binary = target.read_bytes()

    def no_engine(*args, **kwargs):
        pytest.fail("A rejected provenance must not execute the binary")

    monkeypatch.setattr(provisioning, "_version_output", no_engine)
    with pytest.raises(ValueError, match="correctifs sources différents du verrou"):
        provisioning.verify_built_copy(target, manifest_path, provisioning.locked_tesseract_sources())
    assert target.read_bytes() == original_binary
    assert json.loads(manifest_path.read_text()) == manifest


def test_matching_build_receipt_is_accepted_and_exposes_backport_provenance(root, fix_tree, monkeypatch):
    target, manifest_path = installed_copy(root)
    manifest = json.loads(manifest_path.read_text())
    manifest["source_fixes"] = provisioning.apply_source_fixes(fix_tree["dirs"])
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(provisioning, "_version_output", lambda *_: ("tesseract 5.4.0", "tesseract 5.4.0\nleptonica-1.87.0\n"))
    result = provisioning.verify_built_copy(target, manifest_path, provisioning.locked_tesseract_sources())
    assert result["status"] == "verified_built_copy"
    assert manifest["source_fixes"][0]["upstream_commit"] == fix_tree["fix"]["upstream_commit"]


def test_legacy_fixture_without_locked_fixes_needs_no_source_files(root):
    assert provisioning.apply_source_fixes({}) == []
    assert provisioning._source_fix_records(provisioning.locked_tesseract_sources()) == []


def test_same_engine_path_and_version_with_different_binary_invalidates_extraction_cache(tmp_path):
    executable = tmp_path / "tesseract"
    unchanged_version_line = b"#!/bin/sh\necho 'tesseract 5.4.0'\n"
    executable.write_bytes(unchanged_version_line)
    executable.chmod(0o700)
    config = IngestionConfig(tesseract_cmd=str(executable), artifacts_lock_path=None)
    before = config.fingerprint()
    executable.write_bytes(unchanged_version_line + b"# verified source backport\n")
    assert config.fingerprint() != before
    executable.write_bytes(unchanged_version_line)
    assert config.fingerprint() == before


def test_repository_lock_pins_the_final_official_patch_and_full_file_hashes():
    repository = Path(__file__).resolve().parents[2]
    lock = json.loads((repository / "config/artifacts.lock.json").read_bytes())
    entry = next(entry for entry in lock["groups"]["tesseract-source"] if entry["publisher"] == "tesseract-ocr/tesseract")
    fix, = entry["source_fixes"]
    assert entry["version"] == "5.4.0"
    assert fix["upstream_commit"] == "dac6b18a4764d13d670e7f304bbdb80f756b8431"
    assert fix["file"] == "src/classify/normmatch.cpp"
    assert fix["before_sha256"] == "cecd5abbc2394a39f353b94552f45a77590ef0a4d66176999da0daa508f3ab1f"
    assert fix["after_sha256"] == "9ac54083f9b944f47d5710c28fb841a9045495eecd2f7c47c51c9de0f35c338b"
    patch = (repository / fix["patch"]).read_bytes()
    assert sha(patch) == fix["patch_sha256"]
    rule = json.loads(patch)
    assert "if (Protos == nullptr)" in rule["after"] and "return 1.0f;" in rule["after"]
