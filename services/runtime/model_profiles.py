"""Choix de profil à la création : qualification et RAM visible, sans réseau ni lancement.

Le sélecteur est pur. L'inventaire local ne lit que profils, tokenizers et
manifestes ; les couches Ollama sont contrôlées par digest déclaré et taille,
comme doctor, puis par la copie vérifiée du kit avant toute mise en service.
"""

from __future__ import annotations

import hashlib
import json
import platform as host_platform
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CATALOGUE_PATH = "config/model_profiles.json"
SHA256 = re.compile(r"[0-9a-f]{64}")
KIT_SET = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")


def relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Chemin relatif de profil/artefact attendu")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"Chemin de profil/artefact hors programme : {value}")
    return value


def validate_catalogue(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1 or not isinstance(value.get("profiles"), list):
        raise ValueError("Catalogue de profils de mémoire invalide")
    seen: set[str] = set()
    sets: set[str] = set()
    source_models: set[str] = set()
    for entry in value["profiles"]:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) and entry[key]
                                                for key in ("id", "model", "served_model", "profile")):
            raise ValueError("Identité de profil absente du catalogue")
        if entry["id"] in seen:
            raise ValueError("Identifiant de profil répété")
        seen.add(entry["id"])
        kit_set = entry.get("kit_set")
        if not isinstance(kit_set, str) or not KIT_SET.fullmatch(kit_set) or kit_set in sets:
            raise ValueError("Ensemble de modèles invalide ou répété")
        sets.add(kit_set)
        if entry["model"] in source_models:
            raise ValueError("Modèle source répété dans le catalogue")
        source_models.add(entry["model"])
        relative_path(entry["profile"])
        pins = entry.get("pins")
        if not isinstance(pins, dict) or entry["profile"] not in pins:
            raise ValueError("Profil sans empreinte dans le catalogue")
        for path, digest in pins.items():
            relative_path(path)
            if not isinstance(digest, str) or not SHA256.fullmatch(digest):
                raise ValueError("Empreinte de profil/artefact invalide")
        qualification = entry.get("qualification")
        if qualification is None:
            continue
        if not isinstance(qualification, dict):
            raise ValueError("Qualification de profil invalide")
        if qualification.get("status") != "qualified":
            raise ValueError("Seule une qualification acquise peut rendre un profil admissible")
        tokenizer = entry.get("tokenizer_pins")
        if not isinstance(tokenizer, dict) or not tokenizer or any(pins.get(path) != digest for path, digest in tokenizer.items()):
            raise ValueError("Qualification sans empreintes du tokenizer/template")
        for key in ("minimum_visible_memory_bytes", "measured_peak_bytes", "system_margin_bytes", "priority"):
            number = qualification.get(key)
            if type(number) is not int or number < (1 if key != "priority" else 0):
                raise ValueError(f"Qualification : {key} entier positif attendu")
        for key in ("platforms", "modes", "evidence"):
            items = qualification.get(key)
            if not isinstance(items, list) or not items or not all(isinstance(item, str) and item for item in items):
                raise ValueError(f"Qualification : {key} requis")
        manifests = entry.get("model_manifest_sha256")
        if not isinstance(manifests, dict) or set(manifests) != {entry["model"], entry["served_model"]}:
            raise ValueError("Qualification sans identité verrouillée des modèles source/servi")
        if not all(isinstance(digest, str) and SHA256.fullmatch(digest) for digest in manifests.values()):
            raise ValueError("Empreinte de modèle invalide")
    if value.get("legacy_default_model") not in {entry["model"] for entry in value["profiles"]}:
        raise ValueError("Repli historique absent du catalogue")
    return value


def select_profile(catalogue: dict[str, Any], *, total_memory_bytes: int | None, platform: str, mode: str,
                   files: Mapping[str, str], models: Mapping[str, str], available_models: set[str] | None = None,
                   manual_model: str | None = None) -> dict[str, Any]:
    """Décision déterministe ; aucun pic/seuil n'est déduit de la taille des poids."""
    validate_catalogue(catalogue)
    if total_memory_bytes is not None and (type(total_memory_bytes) is not int or total_memory_bytes <= 0):
        raise ValueError("RAM visible : nombre entier d'octets positif ou valeur inconnue attendu")
    profiles = catalogue["profiles"]
    available = available_models if available_models is not None else {entry["model"] for entry in profiles}
    rejected = []
    eligible = []
    for entry in profiles:
        reasons = []
        qualification = entry.get("qualification")
        if not qualification:
            reasons.append("not_qualified")
        else:
            if platform not in qualification["platforms"]:
                reasons.append("platform_not_qualified")
            if mode not in qualification["modes"]:
                reasons.append("mode_not_qualified")
            required = max(qualification["minimum_visible_memory_bytes"],
                           qualification["measured_peak_bytes"] + qualification["system_margin_bytes"])
            if total_memory_bytes is None:
                reasons.append("visible_memory_unknown")
            elif total_memory_bytes < required:
                reasons.append("visible_memory_below_qualified_requirement")
            if any(files.get(path) != digest for path, digest in entry["pins"].items()):
                reasons.append("profile_or_artifact_absent_or_pin_mismatch")
            if any(models.get(name) != digest for name, digest in entry["model_manifest_sha256"].items()):
                reasons.append("model_absent_or_lock_mismatch")
        if entry["model"] not in available:
            reasons.append("model_not_delivered")
        if reasons:
            rejected.append({"profile_id": entry["id"], "reasons": reasons})
        else:
            eligible.append(entry)
    if manual_model is not None:
        selected = next((entry for entry in profiles if entry["model"] == manual_model), None)
        if selected is None or manual_model not in available:
            raise ValueError(f"Modèle manuel non livré : {manual_model}")
        selection, reason = "manual_model", "explicit_model_preserved"
    elif eligible:
        selected = sorted(eligible, key=lambda item: (-item["qualification"]["priority"], item["id"]))[0]
        selection, reason = "automatic", "qualified_present_compatible_memory_with_margin"
    else:
        selected = next(entry for entry in profiles if entry["model"] == catalogue["legacy_default_model"])
        if selected["model"] not in available:
            raise ValueError("Aucun profil qualifié admissible et repli historique non livré")
        selection, reason = "legacy_fallback", "no_eligible_qualified_profile"
    return {"schema_version": 1, "selection": selection, "reason": reason,
            "profile_id": selected["id"], "model": selected["model"], "served_model": selected["served_model"], "profile": selected["profile"],
            "visible_memory_bytes": total_memory_bytes, "platform": platform, "mode": mode,
            "qualification": selected.get("qualification") if selection == "automatic" else None,
            "rejected": rejected}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_catalogue(root: Path) -> dict[str, Any] | None:
    path = root / CATALOGUE_PATH
    return validate_catalogue(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None


def layer_present(root: Path, store: Path, layer: Any) -> bool:
    if not isinstance(layer, dict) or not isinstance(layer.get("digest"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", layer["digest"]):
        return False
    if type(layer.get("size")) is not int or layer["size"] <= 0:
        return False
    path = store / "blobs" / layer["digest"].replace(":", "-")
    return path.is_file() and path.resolve().is_relative_to(root.resolve()) and path.stat().st_size == layer["size"]


def presence(root: Path, catalogue: dict[str, Any], lock: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Inventaire borné aux artefacts des candidats qualifiés, sans copie ni téléchargement."""
    files, models = {}, {}
    for entry in catalogue["profiles"]:
        if not entry.get("qualification"):
            continue
        for relative in entry["pins"]:
            path = root / relative
            if path.is_file() and path.resolve().is_relative_to(root.resolve()):
                files[relative] = file_sha256(path)
        for name in entry["model_manifest_sha256"]:
            expected = lock.get("models", {}).get(name)
            if not isinstance(expected, dict):
                continue
            store = root / relative_path(lock.get("store", ".runtime/models/ollama"))
            manifest = store / relative_path(expected["manifest_path"])
            if not manifest.is_file() or not manifest.resolve().is_relative_to(root.resolve()):
                continue
            digest = file_sha256(manifest)
            if digest != expected["manifest_sha256"]:
                continue
            actual = json.loads(manifest.read_text(encoding="utf-8"))
            if actual.get("config") != expected["config"] or actual.get("layers") != expected["layers"]:
                continue
            layers = [expected["config"], *expected["layers"]]
            if all(layer_present(root, store, layer) for layer in layers):
                models[name] = digest
    return files, models


def platform_id() -> str:
    arch = host_platform.machine().lower()
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)
    return f"{'windows' if sys.platform == 'win32' else sys.platform}-{arch}"


def visible_memory_bytes() -> int | None:
    """MemTotal Linux en kio ; mémoire physique visible de psutil ailleurs, sans arrondi."""
    if sys.platform == "linux":
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith("MemTotal:") and line.split()[2] == "kB":
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
        return None
    import psutil
    return int(psutil.virtual_memory().total)


def select_local_profile(root: Path, *, total_memory_bytes: int | None, platform: str, mode: str,
                         available_models: set[str] | None = None, manual_model: str | None = None) -> dict[str, Any] | None:
    catalogue = read_catalogue(root)
    if catalogue is None:
        return None  # kit historique : ancien comportement inchangé
    lock = json.loads((root / "config/models.lock.json").read_text(encoding="utf-8"))
    files, models = presence(root, catalogue, lock)
    decision = select_profile(catalogue, total_memory_bytes=total_memory_bytes, platform=platform, mode=mode,
                              files=files, models=models, available_models=available_models, manual_model=manual_model)
    return {**decision, "catalogue_sha256": file_sha256(root / CATALOGUE_PATH),
            "models_lock_sha256": file_sha256(root / "config/models.lock.json"),
            "artifact_verification": "metadata_hashes_locked_layer_paths_and_sizes; full_kit_copy_before_activation"}
