"""Importer hors ligne le seul GGUF 4B verrouillé, dans une instance Ollama locale.

Les fichiers doivent être fournis aux chemins du profil. Aucun pull, aucune
substitution de template, aucune modification des anciens profils/modèles.
Le manifeste indique une identité vérifiée, jamais une qualification d'inférence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.settings import Settings  # noqa: E402


def file_sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate_inputs(lock: dict, gguf: Path, tokenizer: Path) -> dict:
    source = lock["gguf"]
    if gguf.stat().st_size != source["size"] or file_sha256(gguf) != source["sha256"]:
        raise ValueError("Le GGUF ne correspond pas au Qwen3-4B verrouillé.")
    hashes = {name: file_sha256(tokenizer / name) for name in lock["tokenizer"]["files"]}
    if hashes != lock["tokenizer"]["files"]:
        raise ValueError("Le tokenizer ne correspond pas au Qwen3-4B verrouillé.")
    # Le compteur préfère cette variante si le fichier est présent : elle doit
    # rester strictement équivalente à la configuration officielle vérifiée.
    explicit_template = tokenizer / "chat_template.jinja"
    template = json.loads((tokenizer / "tokenizer_config.json").read_text(encoding="utf-8"))["chat_template"]
    if explicit_template.exists() and explicit_template.read_text(encoding="utf-8") != template:
        raise ValueError("Le template local a été remplacé.")
    return {"gguf_sha256": source["sha256"], "tokenizer_sha256": hashes,
            "tokenizer_template_sha256": hashlib.sha256(template.encode()).hexdigest()}


def local_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Une instance HTTP Ollama sur loopback est requise.")
    return value.rstrip("/")


def provision(profile: Path, executable: Path, gguf: Path) -> dict:
    lock_path = ROOT / "config/enhanced-4b.lock.json"
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    lock_sha256 = hashlib.sha256(lock_bytes).hexdigest()
    settings = Settings.load(profile)
    if settings.value("llm", "model") != lock["model"]:
        raise ValueError("Ce provisionnement ne concerne que le modèle 4B verrouillé.")
    verified = validate_inputs(lock, gguf.resolve(), settings.llm_tokenizer_dir)
    url = local_url(settings.value("llm", "base_url"))
    destination = settings.path(settings.value("llm", "model_manifest"))
    with httpx.Client(base_url=url, timeout=30, trust_env=False) as client:
        response = client.get("/api/version")
        response.raise_for_status()
        if response.json().get("version") != lock["ollama_version"]:
            raise ValueError("Version Ollama différente du verrou de l'essai.")
        response = client.get("/api/tags")
        response.raise_for_status()
        existing = next((item for item in response.json().get("models", []) if item["name"] == lock["model"]), None)
        if existing and not destination.exists():
            raise ValueError("Le nom existe sans manifeste vérifié ; aucun remplacement implicite.")
        if destination.exists():
            old = json.loads(destination.read_text(encoding="utf-8"))
            if (old.get("source_sha256") != lock["gguf"]["sha256"] or not existing
                    or old.get("model", {}).get("digest") != existing.get("digest")
                    or old.get("lock_sha256") != lock_sha256
                    or old.get("verified_inputs") != verified):
                raise ValueError("Installation locale différente ou incomplète ; aucun remplacement implicite.")
            return {"status": "verified_existing", "model": existing["name"], "digest": existing["digest"], **verified}
        parameters = lock["parameters"]
        with TemporaryDirectory(prefix="rag-4b-import-") as temporary:
            modelfile = Path(temporary) / "Modelfile"
            lines = ["FROM " + json.dumps(str(gguf.resolve()))]
            for key, value in parameters.items():
                values = value if isinstance(value, list) else [value]
                lines.extend(f"PARAMETER {key} {json.dumps(item)}" for item in values)
            modelfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
            subprocess.run([str(executable.resolve()), "create", lock["model"], "-f", str(modelfile)],
                           env={**os.environ, "OLLAMA_HOST": url}, check=True, timeout=600)
        response = client.get("/api/tags")
        response.raise_for_status()
        record = next(item for item in response.json()["models"] if item["name"] == lock["model"])
        response = client.post("/api/show", json={"model": lock["model"]})
        response.raise_for_status()
        show = response.json()
        details = show.get("details", {})
        if (details.get("family") != lock["family"] or details.get("parameter_size") != lock["parameter_size"]
                or details.get("quantization_level") != lock["quantization"]):
            raise ValueError("L'identité native du modèle importé diffère du verrou.")
        manifest = {"model": record, "source_sha256": lock["gguf"]["sha256"],
                    "source": lock["gguf"]["url"], "lock_sha256": lock_sha256,
                    "source_revisions": {"gguf": lock["gguf"]["revision"], "tokenizer": lock["tokenizer"]["revision"]},
                    "verified_inputs": verified, "native_show": show,
                    "provisioned_at_utc": datetime.now(UTC).isoformat(), "inference_validated": False,
                    "import": "official native ollama create from verified GGUF; no template replacement"}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
    return {"status": "imported_verified", "model": record["name"], "digest": record["digest"], **verified}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/enhanced-4b.yaml")
    parser.add_argument("--ollama", type=Path, required=True)
    parser.add_argument("--gguf", type=Path, default=ROOT / ".runtime/models/Qwen3-4B-Q4_K_M.gguf")
    args = parser.parse_args()
    print(json.dumps(provision(args.profile, args.ollama, args.gguf), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
