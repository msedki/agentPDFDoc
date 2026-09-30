import hashlib
import struct

import pytest

from services.runtime.text_model import derive_text_only, modelfile_text, read_layout, write_modelfile


def _string(value):
    data = value.encode("utf-8")
    return struct.pack("<Q", len(data)) + data


def _kv_string(key, value):
    return _string(key) + struct.pack("<I", 8) + _string(value)


def _kv_u32(key, value):
    return _string(key) + struct.pack("<II", 4, value)


def _kv_string_array(key, values):
    body = b"".join(_string(item) for item in values)
    return _string(key) + struct.pack("<IIQ", 9, 8, len(values)) + body


def _kv_u32_array(key, values):
    return _string(key) + struct.pack("<IIQ", 9, 4, len(values)) + struct.pack(f"<{len(values)}I", *values)


def write_gguf(path, tensors, *, architecture="qwen35", alignment=32):
    """tensors: liste (nom, dims, type, octets) dans l'ordre des données."""
    kvs = [_kv_string("general.architecture", architecture), _kv_u32("general.alignment", alignment),
           _kv_string_array("tokenizer.ggml.tokens", ["a", "é", "<|im_end|>"]),
           _kv_u32_array("qwen35.attention.head_count_kv", [0, 4, 0, 4])]
    offsets, cursor, data = [], 0, bytearray()
    for _, _, _, payload in tensors:
        offsets.append(cursor)
        padded = payload + b"\0" * ((-len(payload)) % alignment)
        data += padded
        cursor += len(padded)
    header = bytearray(b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(kvs)) + b"".join(kvs))
    # Ordre d'en-tête volontairement différent de l'ordre des données.
    for index in reversed(range(len(tensors))):
        name, dims, ggml_type, _ = tensors[index]
        header += _string(name) + struct.pack("<I", len(dims)) + struct.pack(f"<{len(dims)}Q", *dims)
        header += struct.pack("<IQ", ggml_type, offsets[index])
    header += b"\0" * ((-len(header)) % alignment)
    path.write_bytes(bytes(header) + bytes(data))


TENSORS = [
    ("token_embd.weight", (4, 2), 0, bytes(range(32))),
    ("v.blk.0.attn_q.weight", (8, 2), 0, b"\x11" * 64),
    ("blk.0.attn_q.weight", (5, 2), 0, bytes(range(100, 140))),
    ("v.patch_embd.weight", (3,), 0, b"\x22" * 12),
    ("mtp.0.eh_proj.weight", (2,), 0, b"\x33" * 8),
]


def test_derivation_removes_only_vision_tensors_and_keeps_bytes(tmp_path):
    source = tmp_path / "source.gguf"
    write_gguf(source, TENSORS)
    target = tmp_path / "out" / "model.gguf"
    report = derive_text_only(source, target, expected_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())

    original, derived = read_layout(source), read_layout(target)
    assert report["removed_tensor_count"] == 2 and report["kept_tensor_count"] == 3
    assert {tensor.name for tensor in derived.tensors} == {"token_embd.weight", "blk.0.attn_q.weight", "mtp.0.eh_proj.weight"}
    assert derived.kv_bytes == original.kv_bytes and derived.architecture == "qwen35"
    assert all(tensor.offset % derived.alignment == 0 for tensor in derived.tensors)
    source_bytes, target_bytes = source.read_bytes(), target.read_bytes()
    source_spans, target_spans = original.spans(), derived.spans()
    for name in report["kept_tensor_sha256"]:
        before = source_bytes[slice(*source_spans[name])]
        after = target_bytes[slice(*target_spans[name])]
        assert before == after
        assert hashlib.sha256(after).hexdigest() == report["kept_tensor_sha256"][name]
    assert report["derived_sha256"] == hashlib.sha256(target_bytes).hexdigest()
    assert not list(target.parent.glob("*.part-*"))


def test_derivation_refuses_changed_source_existing_target_and_useless_runs(tmp_path):
    source = tmp_path / "source.gguf"
    write_gguf(source, TENSORS)
    with pytest.raises(ValueError, match="digest"):
        derive_text_only(source, tmp_path / "a.gguf", expected_source_sha256="0" * 64)
    existing = tmp_path / "exists.gguf"
    existing.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        derive_text_only(source, existing)
    text_only = tmp_path / "text.gguf"
    write_gguf(text_only, [TENSORS[0], TENSORS[2]])
    with pytest.raises(ValueError, match="Aucun tenseur vision"):
        derive_text_only(text_only, tmp_path / "b.gguf")
    other = tmp_path / "other.gguf"
    write_gguf(other, TENSORS, architecture="llama")
    with pytest.raises(ValueError, match="Architecture"):
        derive_text_only(other, tmp_path / "c.gguf")
    assert not (tmp_path / "a.gguf").exists() and not (tmp_path / "b.gguf").exists()


def test_truncated_or_foreign_file_is_rejected(tmp_path):
    source = tmp_path / "source.gguf"
    write_gguf(source, TENSORS)
    truncated = tmp_path / "truncated.gguf"
    truncated.write_bytes(source.read_bytes()[:60])
    with pytest.raises(ValueError):
        read_layout(truncated)
    foreign = tmp_path / "foreign.bin"
    foreign.write_bytes(b"NOPE" + b"\0" * 64)
    with pytest.raises(ValueError, match="non GGUF"):
        read_layout(foreign)


def test_modelfile_keeps_source_renderer_parser_parameters_and_license():
    text = modelfile_text("model.gguf", {"renderer": "qwen3.5", "parser": "qwen3.5", "requires": "0.17.1"},
                          {"temperature": 1, "top_k": 20, "stop": ["<|im_end|>"]}, "Apache License 2.0")
    assert text.splitlines()[:4] == ["FROM ./model.gguf", "RENDERER qwen3.5", "PARSER qwen3.5", "REQUIRES 0.17.1"]
    assert 'PARAMETER stop "<|im_end|>"' in text and "PARAMETER top_k 20" in text
    assert text.rstrip().endswith('LICENSE """Apache License 2.0"""')
    with pytest.raises(ValueError):
        modelfile_text("model.gguf", {}, {}, 'bad """ license')


def test_modelfile_is_written_with_lf_only(tmp_path):
    path = tmp_path / "Modelfile"
    write_modelfile(path, modelfile_text("model.gguf", {}, {}, "line one\nline two\n"))
    data = path.read_bytes()
    assert b"\r" not in data and b'LICENSE """line one\nline two\n"""' in data
