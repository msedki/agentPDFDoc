"""Select the single generative payload without excluding OCR or embeddings."""

from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath

from services.runtime.generation_policy import GENERATION_MODEL, require_generation_profile
from services.runtime.model_profiles import read_catalogue, relative_path
from services.runtime.profile_schema import read_profile_document


def _relative(value):
    result = relative_path(value)
    if PureWindowsPath(result).drive or any(ord(char) < 32 for char in result):
        raise ValueError("Chemin de charge utile non relatif ou contenant des caractères de contrôle.")
    return result


def single_generator_files(root: Path, files: list[str]) -> list[str]:
    """Filter model roots from the explicit catalogue and locked native store.

    A missing/legacy catalogue is refused before a distributable copy is made.
    This checks payload identity declarations, not inference or platform fitness.
    """
    catalogue = read_catalogue(root)
    if (catalogue is None or len(catalogue["profiles"]) != 1
            or catalogue["profiles"][0]["model"] != GENERATION_MODEL
            or catalogue["profiles"][0]["served_model"] != GENERATION_MODEL):
        raise ValueError("La distribution renforcée exige un catalogue contenant uniquement Qwen3-4B verrouillé.")
    profile = read_profile_document(root / catalogue["profiles"][0]["profile"])
    require_generation_profile(profile)
    lock = json.loads((root / "config/models.lock.json").read_text(encoding="utf-8"))
    enhanced_lock = json.loads((root / "config/enhanced-4b.lock.json").read_text(encoding="utf-8"))
    return filter_generation_files(files, profile, lock, enhanced_lock)


def filter_generation_files(files: list[str], profile: dict, lock: dict, enhanced_lock: dict) -> list[str]:
    """Pure filter also used with immutable blobs from the selected kit commit."""
    require_generation_profile(profile)
    files = [_relative(name) for name in files]
    model = lock.get("models", {}).get(GENERATION_MODEL)
    if not isinstance(model, dict):
        raise ValueError("Le générateur renforcé manque au verrou de distribution.")
    store = _relative(lock.get("store", ".runtime/models/ollama"))
    if not store.startswith(".runtime/models/"):
        raise ValueError("Le magasin du générateur doit être un sous-répertoire explicite des modèles.")
    native = {store + "/" + _relative(model["manifest_path"])}
    for layer in [model["config"], *model["layers"]]:
        if not isinstance(layer.get("digest"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", layer["digest"]):
            raise ValueError("Digest de couche du générateur invalide.")
        digest = layer["digest"].replace(":", "-")
        native.add(store + "/blobs/" + digest)
        native.add(store + "/metadata/" + digest + ".json")
    gguf = ".runtime/models/" + _relative(enhanced_lock["gguf"]["filename"])
    native.add(gguf)
    all_roots = [_relative(profile[section][key]) for section, key in (
        ("llm", "tokenizer_dir"), ("embedding", "local_dir"), ("pdf", "artifacts_path"), ("pdf", "tessdata_dir"))]
    if any(not directory.startswith(".runtime/models/") or directory == store
           or directory.startswith(store + "/") or store.startswith(directory + "/") for directory in all_roots):
        raise ValueError("Les modèles documentaires et le tokenizer doivent avoir des racines distinctes et bornées.")
    if any(first == second or first.startswith(second + "/") or second.startswith(first + "/")
           for index, first in enumerate(all_roots) for second in all_roots[index + 1:]):
        raise ValueError("Les racines de modèles se recouvrent.")
    tokenizer_root, *roots = all_roots
    tokenizer_files = {tokenizer_root + "/" + _relative(name) for name in enhanced_lock["tokenizer"]["files"]}
    tokenizer_files.add(tokenizer_root + "/chat_template.jinja")
    native.update(tokenizer_files)
    allowed = [name for name in files if not name.startswith(".runtime/models/")
               or name in native or not name.lower().endswith(".gguf") and any(name.startswith(directory + "/") for directory in roots)]
    required = {store + "/" + _relative(model["manifest_path"]),
                *(store + "/blobs/" + layer["digest"].replace(":", "-") for layer in [model["config"], *model["layers"]])}
    if not required <= set(allowed):
        raise ValueError("Le kit ne contient pas toutes les couches du générateur renforcé verrouillé.")
    return allowed
