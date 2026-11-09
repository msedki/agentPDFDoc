"""Tiny declared model payloads for distribution tests, never native weights.

The nominal fixture passes the current single-generator builder. The historical
fixture is explicitly reconstructed test data for readers/install/rollback tests;
it never disables the current build or generation policy.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3-4b-enhanced:q4km"
PROFILE = "config/enhanced-4b.yaml"
STORE = ".runtime/models/ollama"
HISTORICAL_PROFILES = {"qwen3.5:2b": "config/local16.yaml", "qwen3.5:4b": "config/local16-4b.yaml"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def enhanced_fixture_files() -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Return committed declarations and runtime files as separate tiny maps."""
    profile = (ROOT / PROFILE).read_bytes()
    config, weights = b"SYNTHETIC_4B_CONFIG", b"SYNTHETIC_4B_WEIGHTS_NOT_A_MODEL"
    config_layer = {"digest": "sha256:" + sha(config), "size": len(config)}
    model_layer = {"digest": "sha256:" + sha(weights), "size": len(weights)}
    manifest_path = "manifests/registry.ollama.ai/library/qwen3-4b-enhanced/q4km"
    manifest = encoded({"schemaVersion": 2, "config": config_layer, "layers": [model_layer]})
    native = {"manifest_path": manifest_path, "manifest_sha256": sha(manifest),
              "config": config_layer, "layers": [model_layer], "role": "explicit_synthetic_fixture"}
    tokenizer = {"tokenizer.json": b"{}\n", "tokenizer_config.json": b'{"chat_template":"SYNTHETIC"}\n'}
    declarations = {
        PROFILE: profile,
        "config/enhanced-4b.lock.json": encoded({"schema_version": 1, "model": MODEL,
            "gguf": {"filename": "SYNTHETIC-4B.gguf", "sha256": sha(weights), "size": len(weights)},
            "tokenizer": {"files": {name: sha(data) for name, data in tokenizer.items()}},
            "scope": "EXPLICIT_TEST_FIXTURE_NOT_MODEL_VERIFICATION"}),
        "config/models.lock.json": encoded({"store": STORE, "models": {MODEL: native}}),
        "config/model_profiles.json": encoded({"schema_version": 1, "legacy_default_model": MODEL, "profiles": [
            {"id": "synthetic-enhanced-4b", "kit_set": "4b", "model": MODEL, "served_model": MODEL,
             "profile": PROFILE, "pins": {PROFILE: sha(profile)}, "model_manifest_sha256": {MODEL: sha(manifest)},
             "qualification": None}]}),
    }
    # Explicit dependencies: do not populate from required_for_build(), which
    # would conceal the regression checked by the missing-component tests.
    for name in ("services/runtime/model_profiles.py", "services/runtime/profile_schema.py", "services/runtime/generation_policy.py",
                 "tools/dist/generation_payload.py", "tools/qualification/provision_enhanced_4b.py"):
        declarations[name] = (ROOT / name).read_bytes()
    runtime = {f"{STORE}/{manifest_path}": manifest,
               f"{STORE}/blobs/{config_layer['digest'].replace(':', '-')}": config,
               f"{STORE}/blobs/{model_layer['digest'].replace(':', '-')}": weights,
               ".runtime/manifests/qwen3-4b-enhanced.json": encoded({"fixture": True, "model": MODEL}),
               ".runtime/models/e5-small-int8/model.onnx": b"SYNTHETIC_EMBEDDING",
               ".runtime/models/docling/layout/model.safetensors": b"SYNTHETIC_DOCUMENT_LAYOUT",
               ".runtime/models/tessdata/eng.traineddata": b"SYNTHETIC_OCR"}
    runtime.update({f".runtime/models/qwen3-4b-tokenizer/{name}": data for name, data in tokenizer.items()})
    return declarations, runtime


def materialize_enhanced_fixture(root: Path) -> dict:
    declarations, runtime = enhanced_fixture_files()
    for name, data in (declarations | runtime).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return json.loads(declarations["config/model_profiles.json"])


def refresh_profile_pin(root: Path, relative: str) -> None:
    path = root / "config/model_profiles.json"
    if not path.is_file():
        return
    catalogue = json.loads(path.read_text())
    for entry in catalogue["profiles"]:
        if entry["profile"] == relative:
            entry["pins"][relative] = sha((root / relative).read_bytes())
    path.write_bytes(encoded(catalogue))


def historical_synthetic_kit(kit: Path, repository: Path, *, models=("2b", "4b")) -> Path:
    """Materialize an old multi-model archive from a valid nominal fixture base.

    This is a test-data conversion after the current builder accepted enhanced.
    No current builder is called with legacy profiles, and no guard is patched.
    The real kit verifier must accept the reconstructed hashes before use.
    """
    from tools.dist import kit_guide, linux_kit
    from tools.dist.notices import third_party_notices

    if set(models) - {"2b", "4b"} or "4b" not in models:
        raise ValueError("Historical fixture requires its declared 4B default")
    models = tuple(name for name in ("2b", "4b") if name in models)
    manifest = json.loads((kit / linux_kit.MANIFEST).read_text())
    lock = json.loads((repository / "config/models.lock.json").read_text())
    historical_lock = {**lock, "models": {}}
    shutil.rmtree(kit / STORE)
    shutil.rmtree(kit / ".runtime/models/qwen3-4b-tokenizer")
    (kit / "config/model_profiles.json").unlink()
    (kit / "config/enhanced-4b.lock.json").unlink()
    (kit / ".runtime/manifests/qwen3-4b-enhanced.json").unlink(missing_ok=True)
    manifest.pop("model_selection", None)
    labels = [name for name in HISTORICAL_PROFILES if ("2b" if name.endswith(":2b") else "4b") in models]
    records = []
    for name, source_entry in lock["models"].items():
        if not name.startswith("qwen3.5:"):
            continue
        group = "2b" if name.endswith(":2b") else "4b"
        if group not in models:
            continue
        layers = []
        paths = [f"{STORE}/{source_entry['manifest_path']}"]
        for source_layer in [source_entry["config"], *source_entry["layers"]]:
            data = (repository / STORE / "blobs" / source_layer["digest"].replace(":", "-")).read_bytes()
            layer = {**source_layer, "digest": "sha256:" + sha(data), "size": len(data)}
            layers.append(layer)
            relative = f"{STORE}/blobs/{layer['digest'].replace(':', '-')}"
            paths.append(relative)
            target = kit / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        native = encoded({"schemaVersion": 2, "config": layers[0], "layers": layers[1:]})
        target = kit / paths[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(native)
        entry = {**source_entry, "config": layers[0], "layers": layers[1:], "manifest_sha256": sha(native)}
        historical_lock["models"][name] = entry
        records.append({"name": name, "set": group, "role": "explicit_historical_fixture",
                        "manifest_path": paths[0], "manifest_sha256": entry["manifest_sha256"],
                        "bytes": sum((kit / relative).stat().st_size for relative in paths)})
    (kit / "config/models.lock.json").write_bytes(encoded(historical_lock))
    for group in models:
        target = kit / f".runtime/models/qwen3.5-{group}-tokenizer"
        shutil.copytree(repository / f".runtime/models/qwen3.5-{group}-tokenizer", target)
    manifest.update(default_model="qwen3.5:4b", model_sets=list(models), models=records,
                    model_profiles={name: HISTORICAL_PROFILES[name] for name in labels},
                    fixture_scope="historical_synthetic_archive_for_offline_maintenance_not_current_build")
    manifest["kit_id"] = manifest["kit_id"].removesuffix("-4b") + "-" + "".join(models)
    manifest["profile_ports"] = {}
    for name, relative in manifest["model_profiles"].items():
        profile = yaml.safe_load((kit / relative).read_text())
        manifest["profile_ports"][name] = {"app": profile["app"]["port"],
            "qdrant": int(profile["qdrant"]["url"].rstrip("/").rsplit(":", 1)[1]),
            "ollama": int(profile["llm"]["base_url"].rstrip("/").rsplit(":", 1)[1])}
    manifest["provenance"]["config/models.lock.json"] = sha((kit / "config/models.lock.json").read_bytes())
    extras = {linux_kit.MANIFEST, linux_kit.SUMS, linux_kit.GUIDE, linux_kit.NOTICES,
              linux_kit.INSTALLER, linux_kit.LINKS, linux_kit.EXECUTABLES}
    files = [p for p in kit.rglob("*") if not p.is_symlink() and p.is_file() and p.relative_to(kit).as_posix() not in extras]
    sizes = {}
    for path in files:
        group = linux_kit.group_of(path.relative_to(kit).as_posix())
        sizes[group] = sizes.get(group, 0) + path.stat().st_size
    total = sum(sizes.values())
    manifest.update(files=len(files), bytes=total, bytes_by_group=dict(sorted(sizes.items())))
    manifest["requirements"].update(kit_bytes=total, install_bytes_min=total + linux_kit.INSTALL_MARGIN)
    notices = third_party_notices(kit, [p.relative_to(kit).as_posix() for p in files], manifest["version"],
                                  manifest["platform"], models=models, model_names=tuple(record["name"] for record in records),
                                  gpu=manifest["gpu"]["variant"])
    (kit / linux_kit.NOTICES).write_text(notices, encoding="utf-8")
    documents = {p.relative_to(kit).as_posix(): p.read_text() for p in (kit / "docs").rglob("*.md")}
    names = {"guide": linux_kit.GUIDE, "manifest": linux_kit.MANIFEST, "sums": linux_kit.SUMS,
             "links": linux_kit.LINKS, "executables": linux_kit.EXECUTABLES, "notices": linux_kit.NOTICES, "installer": linux_kit.INSTALLER}
    guide = kit_guide.render(manifest, template=(kit / linux_kit.GUIDE_TEMPLATE).read_text(), documents=documents, files=names)
    (kit / linux_kit.GUIDE).write_text(guide, encoding="utf-8")
    manifest["guide"]["sha256"] = sha(guide.encode())
    sums = {p.relative_to(kit).as_posix(): sha(p.read_bytes()) for p in kit.rglob("*")
            if not p.is_symlink() and p.is_file() and p.name not in {linux_kit.MANIFEST, linux_kit.SUMS}}
    (kit / linux_kit.SUMS).write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())), encoding="utf-8")
    manifest["sha256sums_sha256"] = sha((kit / linux_kit.SUMS).read_bytes())
    (kit / linux_kit.MANIFEST).write_bytes(encoded(manifest))
    result = linux_kit.verify_kit(kit)
    if result["status"] != "verified":
        raise AssertionError(f"Historical synthetic fixture is not internally verified: {result}")
    return kit
