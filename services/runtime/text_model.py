"""GGUF texte seul dérivé du blob Qwen verrouillé, sans encodeur vision.

Ollama 0.35.0 passe automatiquement le GGUF qwen35 en ``--mmproj`` dès qu'il
contient des tenseurs ``v.*`` (llm/llama_server.go, NewLlamaServerRunner) ; aucun
réglage ne le désactive. Le RAG n'envoie jamais d'image, alors que cet encodeur
occupe environ 0,9 Gio (poids vision + tampon de calcul) sur le poste 16 Gio.
La dérivation retire uniquement ces tenseurs, recopie les autres octets à
l'identique et le prouve tenseur par tenseur avant publication du fichier.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GGUF_MAGIC = b"GGUF"
REMOVED_PREFIXES = ("v.", "mm.")
SUPPORTED_ARCHITECTURES = {"qwen35"}
HEADER_READ_LIMIT = 128 * 1024 * 1024
COPY_BLOCK = 8 * 1024 * 1024
_SCALAR_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_SCALAR_FORMATS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
_STRING = 8
_ARRAY = 9


@dataclass(frozen=True)
class TensorInfo:
    name: str
    dims: tuple[int, ...]
    ggml_type: int
    offset: int


@dataclass(frozen=True)
class GgufLayout:
    version: int
    kv_count: int
    kv_bytes: bytes
    alignment: int
    architecture: str
    tensors: tuple[TensorInfo, ...]
    data_start: int
    file_size: int

    def spans(self) -> dict[str, tuple[int, int]]:
        """Plage absolue de chaque tenseur, remplissage d'alignement inclus."""
        ordered = sorted(self.tensors, key=lambda tensor: tensor.offset)
        spans = {}
        data_size = self.file_size - self.data_start
        for index, tensor in enumerate(ordered):
            end = ordered[index + 1].offset if index + 1 < len(ordered) else data_size
            if end < tensor.offset or end > data_size:
                raise ValueError(f"Plage de tenseur incohérente : {tensor.name}")
            spans[tensor.name] = (self.data_start + tensor.offset, self.data_start + end)
        return spans


class _Reader:
    def __init__(self, buffer: bytes):
        self.buffer = buffer
        self.position = 0

    def take(self, size: int) -> bytes:
        end = self.position + size
        if end > len(self.buffer):
            raise ValueError("En-tête GGUF tronqué ou plus grand que la limite de lecture")
        value = self.buffer[self.position:end]
        self.position = end
        return value

    def unpack(self, fmt: str) -> Any:
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self) -> str:
        return self.take(self.unpack("Q")).decode("utf-8")

    def value(self, value_type: int) -> Any:
        if value_type in _SCALAR_FORMATS:
            return self.unpack(_SCALAR_FORMATS[value_type])
        if value_type == _STRING:
            return self.string()
        if value_type == _ARRAY:
            item_type = self.unpack("I")
            count = self.unpack("Q")
            if item_type in _SCALAR_SIZES:
                self.take(_SCALAR_SIZES[item_type] * count)
            else:
                for _ in range(count):
                    self.value(item_type)
            return None
        raise ValueError(f"Type de métadonnée GGUF inconnu : {value_type}")


def read_layout(path: Path) -> GgufLayout:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        reader = _Reader(stream.read(min(file_size, HEADER_READ_LIMIT)))
    if reader.take(4) != GGUF_MAGIC:
        raise ValueError("Fichier non GGUF")
    version = reader.unpack("I")
    if version != 3:
        raise ValueError(f"Version GGUF non prise en charge : {version}")
    tensor_count = reader.unpack("Q")
    kv_count = reader.unpack("Q")
    kv_start = reader.position
    alignment = 32
    architecture = ""
    for _ in range(kv_count):
        key = reader.string()
        value = reader.value(reader.unpack("I"))
        if key == "general.alignment":
            alignment = int(value)
        elif key == "general.architecture":
            architecture = str(value)
    kv_bytes = reader.buffer[kv_start:reader.position]
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("Alignement GGUF invalide")
    tensors = []
    for _ in range(tensor_count):
        name = reader.string()
        dims = tuple(reader.unpack("Q") for _ in range(reader.unpack("I")))
        tensors.append(TensorInfo(name, dims, reader.unpack("I"), reader.unpack("Q")))
    if len({tensor.name for tensor in tensors}) != len(tensors):
        raise ValueError("Noms de tenseurs dupliqués")
    data_start = -(-reader.position // alignment) * alignment
    if any(tensor.offset % alignment for tensor in tensors):
        raise ValueError("Tenseur non aligné")
    return GgufLayout(version, kv_count, kv_bytes, alignment, architecture, tuple(tensors), data_start, file_size)


def _hash_range(stream, start: int, end: int, *, copy_to=None, total=None) -> str:
    digest = hashlib.sha256()
    stream.seek(start)
    remaining = end - start
    while remaining:
        block = stream.read(min(COPY_BLOCK, remaining))
        if not block:
            raise EOFError("Fin de fichier dans une plage de tenseur")
        digest.update(block)
        if copy_to is not None:
            copy_to.write(block)
        if total is not None:
            total.update(block)
        remaining -= len(block)
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(COPY_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def derive_text_only(source: Path, target: Path, *, expected_source_sha256: str | None = None) -> dict[str, Any]:
    """Écrire ``target`` sans tenseurs vision ; refuser toute autre transformation."""
    if target.exists():
        raise FileExistsError(f"Destination déjà présente : {target}")
    if expected_source_sha256 is not None and file_sha256(source) != expected_source_sha256:
        raise ValueError("Blob source différent du digest verrouillé ; aucune dérivation")
    layout = read_layout(source)
    if layout.architecture not in SUPPORTED_ARCHITECTURES:
        raise ValueError(f"Architecture non qualifiée pour la dérivation : {layout.architecture}")
    removed = [tensor for tensor in layout.tensors if tensor.name.startswith(REMOVED_PREFIXES)]
    kept = [tensor for tensor in layout.tensors if not tensor.name.startswith(REMOVED_PREFIXES)]
    if not removed:
        raise ValueError("Aucun tenseur vision à retirer : dérivation inutile")
    if not kept:
        raise ValueError("Aucun tenseur texte conservé")
    spans = layout.spans()
    kept_in_data_order = sorted(kept, key=lambda tensor: tensor.offset)
    new_offsets = {}
    cursor = 0
    for tensor in kept_in_data_order:
        start, end = spans[tensor.name]
        new_offsets[tensor.name] = cursor
        cursor += end - start

    header = bytearray(GGUF_MAGIC)
    header += struct.pack("<IQQ", layout.version, len(kept), layout.kv_count)
    header += layout.kv_bytes
    for tensor in kept:
        encoded_name = tensor.name.encode("utf-8")
        header += struct.pack("<Q", len(encoded_name)) + encoded_name
        header += struct.pack("<I", len(tensor.dims)) + struct.pack(f"<{len(tensor.dims)}Q", *tensor.dims)
        header += struct.pack("<IQ", tensor.ggml_type, new_offsets[tensor.name])
    header += b"\0" * ((-len(header)) % layout.alignment)

    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part-" + uuid.uuid4().hex)
    source_hashes = {}
    total = hashlib.sha256()
    try:
        with source.open("rb") as input_stream, part.open("wb") as output:
            output.write(header)
            total.update(header)
            for tensor in kept_in_data_order:
                start, end = spans[tensor.name]
                source_hashes[tensor.name] = _hash_range(input_stream, start, end, copy_to=output, total=total)
            output.flush()
            os.fsync(output.fileno())
        derived = read_layout(part)
        if derived.kv_bytes != layout.kv_bytes or derived.architecture != layout.architecture:
            raise ValueError("Métadonnées GGUF modifiées pendant la dérivation")
        expected = {tensor.name: (tensor.dims, tensor.ggml_type) for tensor in kept}
        observed = {tensor.name: (tensor.dims, tensor.ggml_type) for tensor in derived.tensors}
        if observed != expected:
            raise ValueError("Table des tenseurs dérivée différente des tenseurs texte source")
        derived_spans = derived.spans()
        with part.open("rb") as check:
            for name, digest in source_hashes.items():
                if _hash_range(check, *derived_spans[name]) != digest:
                    raise ValueError(f"Octets du tenseur {name} différents après copie")
        part.replace(target)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    removed_bytes = sum(spans[tensor.name][1] - spans[tensor.name][0] for tensor in removed)
    return {
        "transformation": "remove_gguf_tensors_with_prefixes",
        "removed_prefixes": list(REMOVED_PREFIXES),
        "architecture": layout.architecture,
        "source_size": layout.file_size,
        "source_tensor_count": len(layout.tensors),
        "removed_tensor_count": len(removed),
        "removed_bytes": removed_bytes,
        "kept_tensor_count": len(kept),
        "kv_metadata_bytes_identical": True,
        "kept_tensor_bytes_identical": True,
        "kept_tensor_sha256": dict(sorted(source_hashes.items())),
        "derived_size": target.stat().st_size,
        "derived_sha256": total.hexdigest(),
    }


def modelfile_text(gguf_name: str, config: dict[str, Any], parameters: dict[str, Any], license_text: str) -> str:
    """Modelfile reprenant rendu, analyseur, prérequis, paramètres et licence du modèle source."""
    if '"""' in license_text:
        raise ValueError("Licence non représentable dans un Modelfile")
    lines = [f"FROM ./{gguf_name}"]
    for key, command in (("renderer", "RENDERER"), ("parser", "PARSER"), ("requires", "REQUIRES")):
        if config.get(key):
            lines.append(f"{command} {config[key]}")
    for key, value in sorted(parameters.items()):
        values = value if isinstance(value, list) else [value]
        lines.extend(f"PARAMETER {key} {json.dumps(item) if isinstance(item, str) else item}" for item in values)
    lines.append(f'LICENSE """{license_text}"""')
    return "\n".join(lines) + "\n"


def write_modelfile(path: Path, text: str) -> None:
    """Fins de ligne LF : la licence importée doit rester octet pour octet celle de la source."""
    path.write_text(text, encoding="utf-8", newline="\n")


def create_ollama_model(ollama_exe: Path, host: str, name: str, modelfile: Path, env: dict[str, str],
                        log_path: Path) -> None:
    """Import local officiel ``ollama create`` ; aucun accès réseau requis."""
    with log_path.open("ab") as log:
        subprocess.run([str(ollama_exe), "create", name, "-f", str(modelfile)], cwd=modelfile.parent,
                       env={**env, "OLLAMA_HOST": host}, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=1800)
