"""Build the locked OCR engine in user space on this Debian 13 x86-64 host.

Qualification helper, not a universal installer. No root, package installation,
global PATH or loader variables. Downloads
are explicit and verified. Headers come from the pinned official Debian packages;
the final binary must link only to the already installed system libraries.
The explicit incremental-ablation mode preserves the previous installation and
publishes a candidate only after the recorded OSD probe succeeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime import provisioning as build  # noqa: E402
from services.runtime.artifacts import file_hash, write_json_atomic  # noqa: E402
from services.runtime.platforms import platform_id  # noqa: E402

DEPENDENCIES = (
    ("https://github.com/Kitware/CMake/releases/download/v3.31.12/cmake-3.31.12-linux-x86_64.tar.gz",
     "0dc2e9a6860f06bf10bd8fadc03e35d9eeb4df46e33763a7e480e987758f385c"),
    ("https://security.debian.org/debian-security/pool/updates/main/libp/libpng1.6/libpng-dev_1.6.48-1+deb13u6_amd64.deb",
     "c340b3a68d3e494290db3952293cbb64f01a8ea1ac75ae0ac6980a3418782415"),
    ("https://deb.debian.org/debian/pool/main/libj/libjpeg-turbo/libjpeg62-turbo-dev_2.1.5-4_amd64.deb",
     "e687e3c8b24a3aa74974928b8e0b07f6df2442187492d85cbcea7dacd91e3aba"),
    ("https://deb.debian.org/debian/pool/main/t/tiff/libtiff-dev_4.7.0-3+deb13u3_amd64.deb",
     "06b5847f751423fa8dfe1a05dca9bdf1e6deb51fee254c5d2407ed4e32bb0a17"),
)


def fetch(url: str, sha256: str, destination: Path, download: bool):
    if not destination.is_file():
        if not download:
            raise FileNotFoundError(f"Explicit --download-official required for {url}")
        pending = destination.with_suffix(destination.suffix + ".part")
        with urllib.request.urlopen(url, timeout=90) as response, pending.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if file_hash(pending) != sha256:
            raise ValueError(f"Downloaded checksum differs for {url}; pending file preserved")
        pending.rename(destination)
    if file_hash(destination) != sha256:
        raise ValueError(f"Cached checksum differs for {url}")
    return {"url": url, "sha256": sha256, "size": destination.stat().st_size, "path": str(destination)}


def run(args):
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise ValueError("This qualification recipe is restricted to Linux x86-64")
    release = platform.freedesktop_os_release()
    if release.get("ID") != "debian" or not release.get("VERSION_ID", "").startswith("13"):
        raise ValueError("This pinned headers recipe was prepared for Debian 13 only")
    target = ROOT / ".runtime/bin/tesseract-5.4.0/tesseract"
    sources = build.locked_tesseract_sources()
    if target.exists() or target.parent.exists():
        raise FileExistsError(f"Existing OCR installation preserved: {target.parent}")
    workspace = args.output.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(workspace).free < 2 * 1024**3:
        raise RuntimeError("At least 2 GiB of free build space is required")
    records = []
    unpack = workspace / "verified-dependencies"
    unpack.mkdir(exist_ok=False)
    for url, sha256 in DEPENDENCIES:
        archive = workspace / url.rsplit("/", 1)[1]
        records.append(fetch(url, sha256, archive, args.download_official))
        if archive.suffix == ".deb":
            subprocess.run(["dpkg-deb", "--extract", str(archive), str(unpack / "headers")], check=True)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(unpack, filter="data")
    write_json_atomic(workspace / "verified-dependencies.json", records)
    tools = build.build_tools()
    tools["cmake"] = str(unpack / "cmake-3.31.12-linux-x86_64/bin/cmake")
    if not all(tools.get(key) for key in ("cc", "c++", "make", "ldd", "readelf")):
        raise RuntimeError("Real C/C++ compilers, make, ldd and readelf are required")
    include = unpack / "headers/usr/include"
    libraries = {"PNG_LIBRARY": Path("/usr/lib/x86_64-linux-gnu/libpng16.so.16"),
                 "JPEG_LIBRARY": Path("/usr/lib/x86_64-linux-gnu/libjpeg.so.62"),
                 "TIFF_LIBRARY": Path("/usr/lib/x86_64-linux-gnu/libtiff.so.6")}
    for library in libraries.values():
        if not library.is_file():
            raise FileNotFoundError(library)
    library_records = [{"path": str(path), "resolved": str(path.resolve()), "sha256": file_hash(path)}
                       for path in libraries.values()]
    root = workspace / "build"
    root.mkdir(exist_ok=False)
    env = {**build._tool_environment(tools), "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
           "CC": str(tools["cc"]), "CXX": str(tools["c++"])}
    for key in ("HOME", "TMPDIR"):
        Path(env[key]).mkdir()
    for header in build.REQUIRED_HEADERS:
        subprocess.run([str(tools["cc"]), "-I", str(include), "-I", str(include / "x86_64-linux-gnu"),
                        "-E", "-x", "c", "-", "-o", "/dev/null"],
                       input=f"#include <stddef.h>\n#include <stdio.h>\n#include <{header}>\n".encode(),
                       env=env, check=True, capture_output=True)
    with build._build_lock(ROOT / build.BUILD_LOCK):
        if target.parent.exists():
            raise FileExistsError(target.parent)
        archives = {name: build._source_archive(entry, offline=not args.download_official) for name, entry in sources.items()}
        source_dirs, archive_records = build._extract_verified_sources(sources, archives, root / "src")
        source_fixes = build.apply_source_fixes(source_dirs, sources=sources)
        prefix = root / "prefix"
        logs = workspace / "logs"
        logs.mkdir()
        started = datetime.now(UTC)
        tick = time.monotonic()
        steps = []
        extra = [f"-DCMAKE_INCLUDE_PATH={include};{include / 'x86_64-linux-gnu'}",
                 *(f"-D{key}={value}" for key, value in libraries.items())]
        for name in ("leptonica", "tesseract"):
            destination = root / (name + "-build")
            options = build._expanded_options(build._cmake_options()[name], root)
            specific = extra if name == "leptonica" else [f"-DLeptonica_DIR={prefix / 'lib/cmake/leptonica'}"]
            commands = (
                ("configure", [str(tools["cmake"]), "-S", str(source_dirs[name]), "-B", str(destination),
                               "-G", "Unix Makefiles", f"-DCMAKE_MAKE_PROGRAM={tools['make']}",
                               f"-DCMAKE_INSTALL_PREFIX={prefix}", *specific, *options]),
                ("build", [str(tools["cmake"]), "--build", str(destination), "--parallel", "2"]),
                ("install", [str(tools["cmake"]), "--install", str(destination)]),
            )
            for stage, command in commands:
                print(f"{name}: {stage}", flush=True)
                log = build._run_logged(f"{name}-{stage}", command, logs, env, root)
                steps.append({"step": f"{name}-{stage}", "command": command, "log": str(log)})
                if stage == "configure" and build.unused_cmake_variables(log.read_text()):
                    raise RuntimeError(f"Unused CMake option: {log}")
        binary = prefix / "bin/tesseract"
        check = build.verify_binary(binary, sources["leptonica"]["version"], tools, (ROOT, workspace), root)
        files = build._install(binary, source_dirs, target)
        manifest = {"schema_version": 2, "kind": build.BUILD_KIND, "platform": platform_id(),
                    "host": platform.platform(), "started_at_utc": started.isoformat(),
                    "built_at_utc": datetime.now(UTC).isoformat(), "duration_seconds": round(time.monotonic() - tick, 2),
                    "jobs": 2, "sources": build._source_records(sources), "source_archives": archive_records,
                    "source_fixes": source_fixes,
                    "cmake_options": build._cmake_options(), "qualification_extra_cmake_options": extra,
                    "qualification_method": "official_user_headers_with_existing_system_dynamic_libraries",
                    "dependencies": records, "system_libraries": library_records,
                    "toolchain": build.toolchain_versions(tools), "generator": "Unix Makefiles",
                    "build_environment": env, "steps": steps, "files": files,
                    "binary": {"path": build._display(target), "sha256": file_hash(target), "size": target.stat().st_size},
                    **check, "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        write_json_atomic(ROOT / build.BUILT_MANIFEST, manifest)
        write_json_atomic(workspace / "build-receipt.json", manifest)
        print(json.dumps(build.verify_built_copy(target, ROOT / build.BUILT_MANIFEST, sources)), flush=True)


def file_record(path):
    return {"sha256": file_hash(path), "size": path.stat().st_size}


def tree_records(directory, pattern="*", *, timestamps=False):
    records = {}
    for path in sorted(directory.rglob(pattern)):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink in ablation inputs: {path}")
        if path.is_file():
            records[path.relative_to(directory).as_posix()] = file_record(path)
            if timestamps:
                records[path.relative_to(directory).as_posix()]["mtime_ns"] = path.stat().st_mtime_ns
    return records


def check_cache(cache_path, command, compilers):
    values = {}
    for line in cache_path.read_text().splitlines():
        if line and not line.startswith(("#", "//")) and "=" in line and ":" in line.split("=", 1)[0]:
            key, value = line.split("=", 1)
            values[key.split(":", 1)[0]] = value
    expected = {option[2:].split("=", 1)[0]: option.split("=", 1)[1] for option in command if option.startswith("-D")}
    expected.update(CMAKE_HOME_DIRECTORY=command[command.index("-S") + 1], CMAKE_GENERATOR="Unix Makefiles",
                    CMAKE_C_COMPILER=compilers["cc"], CMAKE_C_FLAGS_RELEASE="-O3 -DNDEBUG")
    if "CMAKE_CXX_FLAGS" in expected:
        expected.update(CMAKE_CXX_COMPILER=compilers["c++"], CMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG")
    if values.get("CMAKE_TOOLCHAIN_FILE"):
        raise ValueError("An additional CMake toolchain would invalidate the ablation")
    mismatches = [key for key, value in expected.items() if values.get(key) != value]
    if mismatches:
        raise ValueError(f"CMake options differ from the original recipe ({cache_path}): {mismatches}")
    return expected


def check_object_changes(before, after, build_log):
    expected = "CMakeFiles/libtesseract.dir/src/classify/normmatch.cpp.o"
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    compiled = re.findall(r"Building CXX object ([^\r\n]+)", build_log)
    if changed != [expected] or compiled != [expected]:
        raise ValueError(f"Ablation must recompile only normmatch: changed={changed}, compiled={compiled}")
    return {"changed_objects": changed, "compiled_objects": compiled, "reused_object_count": len(before) - 1}


def check_configuration_changes(before):
    """Dependency listings are generated by Make; flags and build rules are immutable."""
    dependencies = []
    for name, digest in before.items():
        path = Path(name)
        current = file_hash(path)
        if current != digest:
            if path.name != "compiler_depend.make":
                raise ValueError(f"Immutable CMake configuration changed: {path}")
            dependencies.append({"path": name, "before_sha256": digest, "after_sha256": current})
    return dependencies


def source_digest_before_fixes(directory, fixes):
    """Verify corrected file hashes, then reconstruct only the original hash listing."""
    records = tree_records(directory)
    for fix in fixes:
        if records.get(fix["file"], {}).get("sha256") != fix["after_sha256"]:
            raise ValueError(f"Corrected source differs from the locked result: {fix['file']}")
        records[fix["file"]]["sha256"] = fix["before_sha256"]
    lines = [f"{record['sha256']}  {directory.name}/{name}\n".encode() for name, record in sorted(records.items())]
    return hashlib.sha256(b"".join(lines)).hexdigest()


def ablation_inputs(args):
    """Read-only validation; version commands execute no compilation or OCR."""
    previous = args.ablate_existing_build.resolve()
    build_root, prefix = previous / "build", previous / "build/prefix"
    target, manifest_path = ROOT / ".runtime/bin/tesseract-5.4.0/tesseract", ROOT / build.BUILT_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    sources = build.locked_tesseract_sources()
    fixes = build._source_fix_records(sources)
    if (len(fixes) != 1 or fixes[0]["source"] != "tesseract" or fixes[0]["file"] != "src/classify/normmatch.cpp"
            or fixes[0]["upstream_commit"] != "dac6b18a4764d13d670e7f304bbdb80f756b8431"):
        raise ValueError("This experiment only permits the pinned upstream normmatch PR4259 fix")
    resume_path: Path | None = getattr(args, "resume_built_ablation", None)
    resumed = json.loads(resume_path.read_text()) if resume_path else None
    if resumed is not None:
        assert resume_path is not None
        if (resumed.get("status") != "failed" or resumed.get("error", {}).get("message") != "Generated CMake configuration changed during the ablation"
                or resumed.get("original_manifest") != manifest or resumed.get("source_fixes") != fixes
                or resumed.get("probe") or resumed.get("publication")
                or [(step.get("step"), step.get("status"), step.get("exit_code")) for step in resumed.get("steps", [])]
                != [("tesseract-build", "completed", 0), ("tesseract-install", "completed", 0)]):
            raise ValueError("Resume only accepts the retained configuration-listing harness failure after a successful isolated build")
        if (resume_path.parent / "osd-probe.json").exists():
            raise ValueError("The retained attempt already contains an OSD probe; no implicit repetition")
    if (manifest.get("kind") != build.BUILD_KIND or manifest.get("platform") != platform_id()
            or manifest.get("source_fixes") or manifest.get("sources") != build._source_records(sources)
            or manifest.get("cmake_options") != build._cmake_options()
            or manifest.get("qualification_method") != "official_user_headers_with_existing_system_dynamic_libraries"):
        raise ValueError("The installed manifest is not the unmodified, verified source build expected for this ablation")
    expected_files = {Path(item["path"]).name: {key: item[key] for key in ("sha256", "size")} for item in manifest["files"]}
    if (target.parent.is_symlink() or tree_records(target.parent) != expected_files
            or manifest["binary"]["path"] != build._display(target) or file_record(target) != {key: manifest["binary"][key] for key in ("sha256", "size")}):
        raise ValueError("The original installed binary or licences no longer match the original manifest")
    original_receipt = previous / "build-receipt.json"
    if json.loads(original_receipt.read_text()) != manifest:
        raise ValueError("The retained original build receipt differs from the installed manifest")
    if resumed is None:
        if file_record(prefix / "bin/tesseract") != file_record(target):
            raise ValueError("The existing build prefix does not contain the original binary")
    elif file_record(prefix / "bin/tesseract") != file_record(build_root / "tesseract-build/bin/tesseract"):
        raise ValueError("The resumed prefix differs from the linked incremental candidate")
    source_dirs = {name: build_root / "src" / f"{name}-{entry['version']}" for name, entry in sources.items()}
    for record in manifest["source_archives"]:
        archive = ROOT / record["archive"]
        if file_hash(archive) != record["archive_sha256"]:
            raise ValueError(f"Original source archive altered: {archive}")
        directory = source_dirs[record["name"]]
        digest = (source_digest_before_fixes(directory, fixes) if resumed is not None and record["name"] == "tesseract"
                  else build.source_content_sha256(directory.parent, directory.name))
        if digest != record["content_sha256"]:
            raise ValueError(f"Existing extracted source altered before ablation: {directory}")
    for record in [*manifest["dependencies"], *manifest["system_libraries"]]:
        if file_hash(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"Original dependency altered: {record['path']}")
    if [(item["url"], item["sha256"]) for item in manifest["dependencies"]] != list(DEPENDENCIES):
        raise ValueError("The dependency archives differ from the pinned qualification recipe")
    toolchain = manifest["toolchain"]
    tools = {key: toolchain[key]["path"] for key in ("cmake", "cc", "c++")}
    tools.update(make=toolchain["build_tool"]["path"], ninja=None, ldd="/usr/bin/ldd", readelf="/usr/bin/readelf")
    if build.toolchain_versions(tools) != toolchain:
        raise ValueError("The current toolchain versions or resolved paths differ from the original build")
    env = manifest["build_environment"]
    if (set(env) != {"PATH", "LANG", "LC_ALL", "HOME", "TMPDIR", "CC", "CXX"}
            or env["CC"] != tools["cc"] or env["CXX"] != tools["c++"] or env["LANG"] != "C" or env["LC_ALL"] != "C"):
        raise ValueError("The original build environment is not the isolated qualification environment")
    configurations = {}
    for name in ("leptonica", "tesseract"):
        destination = build_root / (name + "-build")
        specific = manifest["qualification_extra_cmake_options"] if name == "leptonica" else [f"-DLeptonica_DIR={prefix / 'lib/cmake/leptonica'}"]
        expected = [tools["cmake"], "-S", str(source_dirs[name]), "-B", str(destination), "-G", "Unix Makefiles",
                    f"-DCMAKE_MAKE_PROGRAM={tools['make']}", f"-DCMAKE_INSTALL_PREFIX={prefix}",
                    *specific, *build._expanded_options(build._cmake_options()[name], build_root)]
        recorded = [step["command"] for step in manifest["steps"] if step["step"] == f"{name}-configure"]
        if recorded != [expected]:
            raise ValueError(f"Original configure command differs for {name}")
        configurations[name] = check_cache(destination / "CMakeCache.txt", expected, tools)
    tess_build = build_root / "tesseract-build"
    flags = (tess_build / "CMakeFiles/libtesseract.dir/flags.make").read_text()
    expected_flags = build.file_prefix_map_flags(build_root) + " -O3 -DNDEBUG -std=gnu++20"
    if re.findall(r"^CXX_FLAGS = (.*)$", flags, flags=re.MULTILINE) != [expected_flags]:
        raise ValueError("The effective normmatch compiler flags differ from the original recipe")
    if "#define HAVE_FEENABLEEXCEPT 1" not in (tess_build / "config_auto.h").read_text():
        raise ValueError("The original floating-point exception support must remain enabled")
    probe_receipt = json.loads(args.probe_receipt.read_text())
    probe = Path(probe_receipt["command"][-2]).resolve()
    if (probe_receipt["command"][1:] != ["--psm", "0", "-l", "osd", str(probe), "stdout"]
            or probe_receipt.get("exit_code") != -8 or probe_receipt.get("DOTPRODUCT")
            or probe_receipt["binary_sha256"] != file_hash(target) or probe_receipt.get("timeout_seconds") != 30):
        raise ValueError("The baseline probe is not the recorded default OSD SIGFPE experiment")
    from PIL import Image

    with Image.open(probe) as image:
        if (list(image.size) != probe_receipt["raster_size"] or image.mode != "RGB"
                or hashlib.sha256(image.tobytes()).hexdigest() != probe_receipt["raw_raster_sha256"]):
            raise ValueError("The OSD raster pixels differ from the original probe")
    model = Path(probe_receipt["TESSDATA_PREFIX"]) / "osd.traineddata"
    if file_hash(model) != probe_receipt["osd_model_sha256"]:
        raise ValueError("The OSD model differs from the original probe")
    lock = json.loads(build.ARTIFACT_LOCK.read_text())
    entries = [entry for group in lock["groups"].values() for entry in group if (ROOT / entry.get("target", "")).resolve() == model.resolve()]
    if len(entries) != 1:
        raise ValueError("The exact OSD model must have one locked artifact")
    build.download(entries[0], model, offline=True)
    config_files = {path for pattern in ("CMakeCache.txt", "Makefile", "*.make", "link.txt", "config_auto.h", "cmake_install.cmake")
                    for path in tess_build.rglob(pattern) if path.is_file()}
    configuration_hashes = {str(path): file_hash(path) for path in sorted(config_files)}
    object_records = tree_records(tess_build, "*.o", timestamps=True)
    resumed_checks = None
    if resumed is not None:
        assert resume_path is not None
        log = Path(resumed["steps"][0]["log"])
        changes = check_object_changes(resumed["objects_before"], object_records, log.read_text())
        dependency_changes = check_configuration_changes(resumed["configuration_hashes"])
        if (changes != resumed["object_changes"] or not dependency_changes
                or file_record(prefix / "lib/libleptonica.a") != resumed["leptonica_archive_before"]):
            raise ValueError("The retained isolated-build evidence no longer matches the current files")
        resumed_checks = {"receipt": str(resume_path), "receipt_sha256": file_hash(resume_path),
                          "object_changes": changes, "dependency_metadata_changes": dependency_changes,
                          "build_steps_previously_executed": resumed["steps"], "compilation_repeated": False,
                          "correction": "Only generated compiler_depend.make listings may change; CMake cache, flags, rules, source hashes and object isolation remain checked"}
    return {"previous": previous, "build_root": build_root, "prefix": prefix, "tess_build": tess_build,
            "target": target, "manifest_path": manifest_path, "manifest": manifest, "sources": sources,
            "source_dirs": source_dirs, "tools": tools, "env": env, "probe": probe, "probe_receipt": probe_receipt,
            "configurations": configurations, "configuration_hashes": configuration_hashes,
            "objects": object_records, "resumed_checks": resumed_checks,
            "leptonica_archive": file_record(prefix / "lib/libleptonica.a"), "expected_files": expected_files,
            "tesseract_sources": tree_records(source_dirs["tesseract"])}


def osd_probe(binary, inputs, output):
    """One default-CPU OSD attempt; no orientation inferred from a failure."""
    command = [str(binary), *inputs["probe_receipt"]["command"][1:]]
    env = {**inputs["env"], "TESSDATA_PREFIX": inputs["probe_receipt"]["TESSDATA_PREFIX"]}
    started = datetime.now(UTC)
    tick = time.monotonic()
    result = None
    try:
        result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, env=env, check=False, timeout=30)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
    (output / "osd-stdout.txt").write_bytes(stdout)
    (output / "osd-stderr.txt").write_bytes(stderr)
    angles = re.findall(r"^Orientation in degrees:\s*([0-9]+)\s*$", stdout.decode("utf-8", errors="replace"), re.MULTILINE)
    valid = code == 0 and len(angles) == 1 and int(angles[0]) in {0, 90, 180, 270}
    receipt = {"command": command, "started_at_utc": started.isoformat(), "finished_at_utc": datetime.now(UTC).isoformat(),
               "elapsed_seconds": time.monotonic() - tick, "timeout_seconds": 30, "exit_code": code,
               "timed_out": result is None, "binary_sha256": file_hash(binary), "raster_file": str(inputs["probe"]),
               "raster_file_sha256": file_hash(inputs["probe"]), "raw_raster_sha256": inputs["probe_receipt"]["raw_raster_sha256"],
               "osd_model_sha256": inputs["probe_receipt"]["osd_model_sha256"], "environment": env,
               "orientation_degrees_clockwise": int(angles[0]) if valid else None, "orientation_parseable": valid,
               "acceptance": "exit 0 and one explicit quarter-turn angle, as required by the existing Docling parser; OCR accuracy remains unqualified"}
    write_json_atomic(output / "osd-probe.json", receipt)
    if not valid:
        raise RuntimeError("The default OSD probe failed or returned no valid orientation; original installation retained")
    return receipt


def publish_ablation(inputs, binary, manifest, output):
    """Preserve the old canonical installation and roll it back on publish failure."""
    target, manifest_path = inputs["target"], inputs["manifest_path"]
    if tree_records(target.parent) != inputs["expected_files"] or json.loads(manifest_path.read_text()) != inputs["manifest"]:
        raise ValueError("Canonical installation changed during the ablation; no replacement attempted")
    previous_directory, previous_manifest = output / "unpatched-canonical", output / "unpatched-canonical-manifest.json"
    moved_directory = moved_manifest = False
    try:
        target.parent.rename(previous_directory)
        moved_directory = True
        manifest_path.rename(previous_manifest)
        moved_manifest = True
        manifest["files"] = build._install(binary, inputs["source_dirs"], target)
        manifest["binary"] = {"path": build._display(target), **file_record(target)}
        write_json_atomic(manifest_path, manifest)
        build.verify_built_copy(target, manifest_path, inputs["sources"])
    except BaseException:
        if moved_directory:
            if target.parent.exists():
                target.parent.rename(output / "rejected-candidate-install")
            previous_directory.rename(target.parent)
        if moved_manifest:
            if manifest_path.exists():
                manifest_path.rename(output / "rejected-candidate-manifest.json")
            previous_manifest.rename(manifest_path)
        raise
    return {"original_installation": str(previous_directory), "original_manifest": str(previous_manifest),
            "original_binary_sha256": inputs["manifest"]["binary"]["sha256"], "published_binary_sha256": file_hash(target)}


def ablate_existing(args):
    if args.download_official or args.probe_receipt is None:
        raise ValueError("Ablation requires --probe-receipt and never downloads dependencies")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Ablation output must be new; previous evidence preserved: {output}")
    output.mkdir(parents=True)
    receipt: dict[str, Any] = {"kind": "incremental_upstream_source_fix_ablation", "started_at_utc": datetime.now(UTC).isoformat(),
               "status": "validating", "steps": [], "helper_sha256": file_hash(Path(__file__)),
               "reuses_precompiled_objects_and_leptonica": True, "fresh_full_build": False}
    tick = time.monotonic()
    try:
        with build._build_lock(ROOT / build.BUILD_LOCK):
            inputs = ablation_inputs(args)
            manifest = inputs["manifest"]
            receipt.update(original_manifest=manifest, original_manifest_sha256=file_hash(inputs["manifest_path"]),
                           expected_source_fixes=build._source_fix_records(inputs["sources"]),
                           build_environment=inputs["env"], configurations=inputs["configurations"],
                           configuration_hashes=inputs["configuration_hashes"], objects_before=inputs["objects"],
                           leptonica_archive_before=inputs["leptonica_archive"])
            receipt["resumed_checks"] = inputs.get("resumed_checks")
            if args.plan_only:
                receipt["status"] = "validated_plan_only"
                return receipt
            # Both copies precede any source or build mutation. Canonical paths
            # remain untouched until after the successful native probe.
            backup = output / "unpatched-install-copy"
            shutil.copytree(inputs["target"].parent, backup)
            shutil.copy2(inputs["manifest_path"], output / "unpatched-built-manifest.json")
            if (tree_records(backup) != inputs["expected_files"]
                    or file_hash(output / "unpatched-built-manifest.json") != receipt["original_manifest_sha256"]):
                raise ValueError("Original installation backup failed verification")
            source_fixes = (build._source_fix_records(inputs["sources"]) if inputs.get("resumed_checks")
                            else build.apply_source_fixes(inputs["source_dirs"], sources=inputs["sources"]))
            receipt["source_fixes"] = source_fixes
            expected_sources = {key: dict(value) for key, value in inputs["tesseract_sources"].items()}
            for fix in source_fixes:
                if fix["source"] != "tesseract":
                    raise ValueError("This ablation is restricted to the Tesseract normalization fix")
                changed = inputs["source_dirs"]["tesseract"] / fix["file"]
                expected_sources[fix["file"]] = {"sha256": fix["after_sha256"], "size": changed.stat().st_size}
            if tree_records(inputs["source_dirs"]["tesseract"]) != expected_sources:
                raise ValueError("Unexpected source change during the ablation")
            logs = output / "logs"
            commands = [("tesseract-build", [inputs["tools"]["cmake"], "--build", str(inputs["tess_build"]), "--target", "tesseract", "--parallel", "2"]),
                        ("tesseract-install", [inputs["tools"]["cmake"], "--install", str(inputs["tess_build"])])]
            if inputs.get("resumed_checks"):
                commands = []
                receipt["object_changes"] = inputs["resumed_checks"]["object_changes"]
            for name, command in commands:
                step: dict[str, Any] = {"step": name, "command": command, "started_at_utc": datetime.now(UTC).isoformat(), "status": "started"}
                receipt["steps"].append(step)
                write_json_atomic(output / "ablation-receipt.json", receipt)
                print(f"ablation: {name}", flush=True)
                try:
                    log = build._run_logged(name, command, logs, inputs["env"], inputs["build_root"])
                except BaseException:
                    step.update(status="failed", finished_at_utc=datetime.now(UTC).isoformat())
                    raise
                step.update(status="completed", exit_code=0, finished_at_utc=datetime.now(UTC).isoformat(), log=str(log))
                if name == "tesseract-build":
                    receipt["object_changes"] = check_object_changes(inputs["objects"], tree_records(inputs["tess_build"], "*.o", timestamps=True), log.read_text())
            if file_record(inputs["prefix"] / "lib/libleptonica.a") != inputs["leptonica_archive"]:
                raise ValueError("Leptonica changed during a Tesseract-only ablation")
            receipt["dependency_metadata_changes"] = check_configuration_changes(inputs["configuration_hashes"])
            binary = inputs["prefix"] / "bin/tesseract"
            if file_hash(binary) == manifest["binary"]["sha256"]:
                raise ValueError("The corrected binary unexpectedly equals the original binary")
            check = build.verify_binary(binary, inputs["sources"]["leptonica"]["version"], inputs["tools"], (ROOT, inputs["previous"]), inputs["build_root"])
            receipt["probe"] = osd_probe(binary, inputs, output)
            if file_hash(binary) != receipt["probe"]["binary_sha256"]:
                raise ValueError("Candidate binary changed after the successful OSD probe")
            candidate = {**manifest, **check, "started_at_utc": receipt["started_at_utc"], "built_at_utc": datetime.now(UTC).isoformat(),
                         "duration_seconds": round(time.monotonic() - tick, 3), "source_fixes": source_fixes,
                         "qualification_method": "incremental_upstream_source_fix_ablation", "steps": receipt["steps"],
                         "baseline_manifest": str(output / "unpatched-built-manifest.json"),
                         "baseline_manifest_sha256": receipt["original_manifest_sha256"],
                         "resumed_incremental_build": inputs.get("resumed_checks"),
                         "ablation_receipt": str(output / "ablation-receipt.json"), "helper_sha256": receipt["helper_sha256"]}
            receipt["publication"] = publish_ablation(inputs, binary, candidate, output)
            write_json_atomic(output / "build-receipt.json", candidate)
            receipt["status"] = "published_after_successful_probe"
            return receipt
    except BaseException as error:
        receipt.update(status="failed", error={"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        receipt.update(finished_at_utc=datetime.now(UTC).isoformat(), duration_seconds=round(time.monotonic() - tick, 3))
        write_json_atomic(output / "ablation-receipt.json", receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download-official", action="store_true")
    parser.add_argument("--ablate-existing-build", type=Path, help="Existing qualification workspace containing build/ and build-receipt.json")
    parser.add_argument("--probe-receipt", type=Path, help="Recorded unpatched default OSD SIGFPE probe; its raster and model are rechecked")
    parser.add_argument("--resume-built-ablation", type=Path, help="Explicit retained harness-failure receipt; validate and probe its completed build without recompiling")
    parser.add_argument("--plan-only", action="store_true", help="Validate ablation inputs and write a receipt without build, OCR or publication")
    arguments = parser.parse_args()
    if arguments.ablate_existing_build:
        result = ablate_existing(arguments)
        print(json.dumps({"status": result["status"], "receipt": str(arguments.output / "ablation-receipt.json"),
                          "object_changes": result.get("object_changes"), "publication": result.get("publication")}), flush=True)
    elif arguments.plan_only or arguments.probe_receipt or arguments.resume_built_ablation:
        parser.error("--plan-only, --probe-receipt and --resume-built-ablation require --ablate-existing-build")
    else:
        run(arguments)
