"""Ablation guards with tiny files and subprocess doubles; no build or OCR."""

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qualification import provision_production_ocr as qualification


@pytest.mark.parametrize("damage", [None, "compiler", "flags", "source", "toolchain"])
def test_cmake_cache_must_match_the_recorded_command_and_release_flags(tmp_path, damage):
    command = ["cmake", "-S", "/source", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_FLAGS=-ffile-prefix-map=/build=."]
    values = {"CMAKE_HOME_DIRECTORY": "/source", "CMAKE_GENERATOR": "Unix Makefiles", "CMAKE_C_COMPILER": "/cc",
              "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG", "CMAKE_CXX_COMPILER": "/c++", "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
              "CMAKE_BUILD_TYPE": "Release", "CMAKE_CXX_FLAGS": "-ffile-prefix-map=/build=."}
    if damage:
        key = {"compiler": "CMAKE_CXX_COMPILER", "flags": "CMAKE_CXX_FLAGS", "source": "CMAKE_HOME_DIRECTORY",
               "toolchain": "CMAKE_TOOLCHAIN_FILE"}[damage]
        values[key] = "different"
    cache = tmp_path / "CMakeCache.txt"
    cache.write_text("\n".join(f"{key}:STRING={value}" for key, value in values.items()))
    if damage:
        with pytest.raises(ValueError):
            qualification.check_cache(cache, command, {"cc": "/cc", "c++": "/c++"})
    else:
        checked = qualification.check_cache(cache, command, {"cc": "/cc", "c++": "/c++"})
        assert checked["CMAKE_CXX_FLAGS"] == values["CMAKE_CXX_FLAGS"]


@pytest.mark.parametrize("damage", [None, "another_object", "unchanged_object", "another_compilation"])
def test_only_normmatch_may_be_recompiled_or_change(damage):
    name = "CMakeFiles/libtesseract.dir/src/classify/normmatch.cpp.o"
    before = {name: {"sha256": "before", "mtime_ns": 1}, "other.cpp.o": {"sha256": "kept", "mtime_ns": 1}}
    after = copy.deepcopy(before)
    after[name] = {"sha256": "after", "mtime_ns": 2}
    log = "[1%] Building CXX object " + name + "\n[2%] Linking CXX static library libtesseract.a\n"
    if damage == "another_object":
        after["other.cpp.o"]["mtime_ns"] = 2
    elif damage == "unchanged_object":
        after = before
    elif damage == "another_compilation":
        log += "Building CXX object other.cpp.o\n"
    if damage:
        with pytest.raises(ValueError, match="only normmatch"):
            qualification.check_object_changes(before, after, log)
    else:
        result = qualification.check_object_changes(before, after, log)
        assert result["changed_objects"] == [name] and result["reused_object_count"] == 1


@pytest.mark.parametrize("filename,allowed", [("compiler_depend.make", True), ("flags.make", False),
                                              ("CMakeCache.txt", False), ("build.make", False), ("link.txt", False)])
def test_regenerated_dependency_listing_is_distinct_from_immutable_configuration(tmp_path, filename, allowed):
    path = tmp_path / filename
    path.write_bytes(b"before")
    before = {str(path): qualification.file_hash(path)}
    path.write_bytes(b"after")
    if allowed:
        changes = qualification.check_configuration_changes(before)
        assert len(changes) == 1 and changes[0]["path"] == str(path)
        assert changes[0]["before_sha256"] != changes[0]["after_sha256"]
    else:
        with pytest.raises(ValueError, match="Immutable CMake"):
            qualification.check_configuration_changes(before)


def test_resume_source_proof_requires_exact_patch_and_preserves_other_source_hashes(tmp_path):
    source = tmp_path / "tesseract-5.4.0"
    source.mkdir()
    changed, untouched = source / "normmatch.cpp", source / "other.cpp"
    changed.write_bytes(b"old")
    untouched.write_bytes(b"unchanged")
    original = qualification.build.source_content_sha256(source.parent, source.name)
    changed.write_bytes(b"fixed")
    fixes = [{"file": changed.name, "before_sha256": hashlib.sha256(b"old").hexdigest(),
              "after_sha256": hashlib.sha256(b"fixed").hexdigest()}]
    assert qualification.source_digest_before_fixes(source, fixes) == original
    untouched.write_bytes(b"other change")
    assert qualification.source_digest_before_fixes(source, fixes) != original
    changed.write_bytes(b"wrong fix")
    with pytest.raises(ValueError, match="Corrected source differs"):
        qualification.source_digest_before_fixes(source, fixes)


@pytest.mark.parametrize("exit_code,stdout,timeout,valid", [
    (0, b"Orientation in degrees: 0\nRotate: 0\n", False, True),
    (0, b"Orientation in degrees: 90\n", False, True),
    (-8, b"", False, False), (0, b"", False, False),
    (0, b"Orientation in degrees: 45\n", False, False),
    (0, b"Orientation in degrees: 0\nOrientation in degrees: 0\n", False, False),
    (None, b"partial", True, False),
])
def test_osd_probe_never_infers_zero_from_error_or_uses_dotproduct_override(tmp_path, monkeypatch, exit_code, stdout, timeout, valid):
    binary, raster = tmp_path / "binary", tmp_path / "raster.png"
    binary.write_bytes(b"binary double")
    raster.write_bytes(b"raster double")
    inputs = {"env": {"LANG": "C"}, "probe": raster,
              "probe_receipt": {"command": ["old-binary", "--psm", "0", "-l", "osd", str(raster), "stdout"],
                                "TESSDATA_PREFIX": "/verified/models", "raw_raster_sha256": "pixels", "osd_model_sha256": "model"}}
    monkeypatch.setenv("DOTPRODUCT", "generic")

    def run(command, **kwargs):
        assert command == [str(binary), *inputs["probe_receipt"]["command"][1:]]
        assert "DOTPRODUCT" not in kwargs["env"] and kwargs["timeout"] == 30
        if timeout:
            raise subprocess.TimeoutExpired(command, 30, output=stdout, stderr=b"timeout")
        return SimpleNamespace(returncode=exit_code, stdout=stdout, stderr=b"diagnostic")

    monkeypatch.setattr(qualification.subprocess, "run", run)
    if valid:
        assert qualification.osd_probe(binary, inputs, tmp_path)["orientation_parseable"]
    else:
        with pytest.raises(RuntimeError, match="original installation retained"):
            qualification.osd_probe(binary, inputs, tmp_path)
    receipt = json.loads((tmp_path / "osd-probe.json").read_text())
    assert receipt["exit_code"] == exit_code and receipt["timed_out"] is timeout
    assert receipt["orientation_parseable"] is valid
    assert (tmp_path / "osd-stdout.txt").read_bytes() == stdout


@pytest.mark.parametrize("failure", [None, "install", "verify"])
def test_publication_preserves_old_installation_and_rolls_back_on_failure(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(qualification.build, "ROOT", tmp_path)
    target = tmp_path / "bin/tesseract-5.4.0/tesseract"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unpatched binary")
    (target.parent / "LICENSE").write_bytes(b"Apache")
    (target.parent / "leptonica-license.txt").write_bytes(b"BSD")
    old_files = qualification.tree_records(target.parent)
    manifest_path = tmp_path / "old-manifest.json"
    manifest_path.write_text(json.dumps({"state": "original", "binary": qualification.file_record(target)}))
    old_manifest = manifest_path.read_bytes()
    dirs = {name: tmp_path / "sources" / name for name in ("leptonica", "tesseract")}
    for path in dirs.values():
        path.mkdir(parents=True)
    (dirs["tesseract"] / "LICENSE").write_bytes(b"Apache")
    (dirs["leptonica"] / "leptonica-license.txt").write_bytes(b"BSD")
    binary = tmp_path / "candidate"
    binary.write_bytes(b"corrected candidate")
    output = tmp_path / "ablation"
    output.mkdir()
    inputs = {"target": target, "manifest_path": manifest_path, "manifest": json.loads(old_manifest),
              "expected_files": old_files, "source_dirs": dirs, "sources": {}}

    def verify(*args):
        if failure == "verify":
            raise ValueError("verification double failed")

    monkeypatch.setattr(qualification.build, "verify_built_copy", verify)
    if failure == "install":
        monkeypatch.setattr(qualification.build, "_install", lambda *_: (_ for _ in ()).throw(ValueError("install double failed")))
    if failure:
        with pytest.raises(ValueError, match="double failed"):
            qualification.publish_ablation(inputs, binary, {"state": "candidate"}, output)
        assert qualification.tree_records(target.parent) == old_files
        assert manifest_path.read_bytes() == old_manifest
        if failure == "verify":
            assert (output / "rejected-candidate-install/tesseract").read_bytes() == binary.read_bytes()
    else:
        receipt = qualification.publish_ablation(inputs, binary, {"state": "candidate"}, output)
        assert target.read_bytes() == binary.read_bytes()
        assert qualification.tree_records(output / "unpatched-canonical") == old_files
        assert (output / "unpatched-canonical-manifest.json").read_bytes() == old_manifest
        assert receipt["original_binary_sha256"] != receipt["published_binary_sha256"]


def test_plan_only_cannot_apply_patch_compile_probe_or_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, "ROOT", tmp_path)
    source_manifest = tmp_path / "manifest.json"
    source_manifest.write_text("{}")
    inputs = {"manifest": {}, "manifest_path": source_manifest, "sources": {}, "env": {}, "configurations": {},
              "configuration_hashes": {}, "objects": {}, "leptonica_archive": {}}
    monkeypatch.setattr(qualification, "ablation_inputs", lambda _: inputs)

    def forbidden(*args, **kwargs):
        pytest.fail("plan-only must not mutate, compile, probe or publish")

    monkeypatch.setattr(qualification.build, "apply_source_fixes", forbidden)
    monkeypatch.setattr(qualification.build, "_run_logged", forbidden)
    monkeypatch.setattr(qualification, "osd_probe", forbidden)
    monkeypatch.setattr(qualification, "publish_ablation", forbidden)
    output = tmp_path / "new-output"
    args = SimpleNamespace(download_official=False, probe_receipt=Path("baseline.json"), output=output, plan_only=True)
    result = qualification.ablate_existing(args)
    assert result["status"] == "validated_plan_only" and result["steps"] == []
    assert json.loads((output / "ablation-receipt.json").read_text())["status"] == "validated_plan_only"
