"""Named doubles only: no heldout questions, PDF renderer, model or network."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tools.qualification import materialize_production_i4 as materializer
from tools.qualification import prepare_production_i4 as preparer


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n")


@pytest.fixture
def frozen_double(tmp_path, monkeypatch):
    base = tmp_path / "published-explicit-double"
    base.mkdir()
    local = tmp_path / "originals-explicit-double"
    (local / "originals").mkdir(parents=True)
    qa = tmp_path / "qa"
    qa.mkdir()
    monkeypatch.setattr(materializer, "LOCAL_QA", qa)
    originals = {"D" + str(index): b"%PDF-1.7 explicit source double " + str(index).encode() for index in range(3)}
    pairs = {"SCAN" + str(index): (b"%PDF-1.7 image-only double " + str(index).encode(),
                                  b"explicit PNG double " + str(index).encode()) for index in range(2)}
    documents = []
    for key, raw in originals.items():
        relative = "originals/" + key + ".pdf"
        (local / relative).write_bytes(raw)
        documents.append({"id": key, "file": relative, "original_sha256": sha(raw), "bytes": len(raw), "pages": 4,
                          "url": "https://www.analog.com/media/en/technical-documentation/data-sheets/" + key + ".pdf"})
    sources = {"schema_version": "i4-heldout-sources-v1", "documents": documents}
    versions = {"pypdfium2": "explicit-pdfium-double", "reportlab": "explicit-reportlab-double", "Pillow": "explicit-pillow-double"}
    scans = {"schema_version": "i4-heldout-scan-pairs-v1", "versions": versions, "scans": []}
    for index, (key, (pdf, png)) in enumerate(pairs.items()):
        original = documents[index]
        scans["scans"].append({"id": key, "file": "scans/" + key + ".pdf", "sha256": sha(pdf), "bytes": len(pdf),
                               "raster_sha256": sha(png), "raster_dimensions": [200, 300],
                               "original_document_id": original["id"], "original_page_index": index,
                               "original_sha256": original["original_sha256"], "transform": dict(materializer.EXPECTED_TRANSFORM)})
    oracles_raw = json.dumps({"cases": [{"answerable": index < 6, "question": "OPAQUE EXPLICIT DOUBLE " + str(index)}
                                      for index in range(8)]}, indent=3).encode() + b"\r\n"
    (base / "questions-oracles.json").write_bytes(oracles_raw)

    def refreeze():
        write_json(base / "sources.json", sources)
        write_json(base / "scan-transformations.json", scans)
        entries = [{"path": "original/private/path/" + name, "sha256": preparer.digest(base / name),
                    "bytes": (base / name).stat().st_size} for name in sorted(materializer.MANIFESTS)]
        write_json(base / "freeze-receipt.json", {"schema_version": 1, "private_files": entries})
        monkeypatch.setattr(preparer, "HELDOUT_RECEIPT_SHA256", preparer.digest(base / "freeze-receipt.json"))

    refreeze()
    monkeypatch.setattr(materializer, "version", versions.__getitem__)
    render_calls = []

    def explicit_renderer_double(original, spec, output):
        assert preparer.digest(original) == spec["original_sha256"]
        assert spec["transform"] == materializer.EXPECTED_TRANSFORM
        assert output.is_dir()
        pdf, png = pairs[spec["id"]]
        (output / (spec["id"] + ".pdf")).write_bytes(pdf)
        (output / (spec["id"] + ".png")).write_bytes(png)
        render_calls.append(spec["id"])
        return {"id": spec["id"], "pdf_sha256": sha(pdf), "raster_sha256": sha(png),
                "embedded_text": False, "original_sha256_unchanged": True, "byte_identical_to_frozen_pair": True}

    monkeypatch.setattr(preparer, "render_scan_pair", explicit_renderer_double)
    return SimpleNamespace(base=base, local=local, qa=qa, output=qa / "fresh", sources=sources, scans=scans,
                           originals=originals, pairs=pairs, refreeze=refreeze, oracles_raw=oracles_raw,
                           renderer=explicit_renderer_double, render_calls=render_calls)


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_local_materialization_preserves_opaque_bytes_and_checks_full_frozen_validator(frozen_double, monkeypatch, capsys):
    fixture = frozen_double
    before = snapshot(fixture.base), snapshot(fixture.local)
    calls = []
    validator = preparer.frozen_inputs

    def observed_validator(output):
        assert fixture.render_calls == ["SCAN0", "SCAN1"]
        assert all((output / entry["file"]).is_file() for entry in fixture.sources["documents"])
        calls.append(output)
        return validator(output)

    monkeypatch.setattr(preparer, "frozen_inputs", observed_validator)
    result = materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert result["status"] == "materialized_verified" and result["frozen_inputs_verified"]
    assert result["transport_kind"] == "local_copy" and result["model_calls"] == 0
    assert calls == [fixture.output]
    assert (fixture.output / "questions-oracles.json").read_bytes() == fixture.oracles_raw
    assert before == (snapshot(fixture.base), snapshot(fixture.local))
    assert fixture.output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in fixture.output.rglob("*") if path.is_file())
    assert all(stat.S_ISREG(path.lstat().st_mode) for path in fixture.output.rglob("*") if path.is_file())
    receipt = (fixture.output / "materialization-receipt.json").read_text()
    assert "OPAQUE EXPLICIT DOUBLE" not in receipt and not capsys.readouterr().out


def test_absent_originals_never_download_without_explicit_flag(frozen_double):
    fixture = frozen_double
    with pytest.raises(ValueError, match="download-official"):
        materializer.materialize(fixture.base, fixture.output)
    assert not fixture.output.exists() and fixture.render_calls == []


def test_official_download_uses_three_frozen_urls_and_named_mock_transport(frozen_double):
    fixture = frozen_double
    requests = []

    def explicit_http_double(request):
        requests.append(request)
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"] == {name: materializer.DOWNLOAD_TIMEOUT_SECONDS
                                                for name in ("connect", "read", "write", "pool")}
        key = Path(request.url.path).stem
        return httpx.Response(200, stream=httpx.ByteStream(fixture.originals[key]),
                              headers={"Content-Length": str(len(fixture.originals[key]))})

    result = materializer.materialize(fixture.base, fixture.output, download_official=True,
                                      transport=httpx.MockTransport(explicit_http_double))
    assert [str(request.url) for request in requests] == [spec["url"] for spec in fixture.sources["documents"]]
    assert result["transport_kind"] == "explicit_test_substitute"
    assert result["source_inputs_unchanged"] and result["frozen_inputs_verified"]
    assert len(result["originals"]) == 3 and len(result["scans"]) == 2


def test_wrong_receipt_rejects_before_manifest_or_oracle_parse(frozen_double, monkeypatch):
    fixture = frozen_double
    (fixture.base / "freeze-receipt.json").write_bytes(b"different receipt")
    monkeypatch.setattr(materializer.json, "loads", lambda *_: pytest.fail("Unverified receipt parsed"))
    with pytest.raises(ValueError, match="reçu de gel"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert not fixture.output.exists()


def test_modified_opaque_oracle_refused_before_final_validator(frozen_double, monkeypatch):
    fixture = frozen_double
    (fixture.base / "questions-oracles.json").write_bytes(b"not JSON and never parsed\xff")
    monkeypatch.setattr(preparer, "frozen_inputs", lambda *_: pytest.fail("Altered manifest reached final validation"))
    with pytest.raises(ValueError, match="Octets de manifeste"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert not fixture.output.exists() and not fixture.render_calls


@pytest.mark.parametrize("url", ["http://www.analog.com/a.pdf", "https://evil.example/a.pdf",
                               "https://www.analog.com.evil.example/a.pdf", "https://user@www.analog.com/a.pdf",
                               "https://www.analog.com:444/a.pdf", "https://www.analog.com/a.pdf?q=1"])
def test_nonofficial_urls_rejected_before_output_or_network(frozen_double, url):
    fixture = frozen_double
    fixture.sources["documents"][0]["url"] = url
    fixture.refreeze()
    with pytest.raises(ValueError, match="URL HTTPS officielles"):
        materializer.materialize(fixture.base, fixture.output, download_official=True,
                                  transport=httpx.MockTransport(lambda *_: pytest.fail("Disallowed URL fetched")))
    assert not fixture.output.exists()


@pytest.mark.parametrize("relative", ["../outside.pdf", "/tmp/outside.pdf", "originals/../outside.pdf",
                                    "originals\\outside.pdf", "originals/C:outside.pdf", "originals//outside.pdf"])
def test_source_path_cannot_escape_or_renormalize(frozen_double, relative):
    fixture = frozen_double
    fixture.sources["documents"][0]["file"] = relative
    fixture.refreeze()
    with pytest.raises(ValueError, match="Chemin"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert not fixture.output.exists()


def test_manifest_receipt_path_escape_rejected_even_with_matching_fixture_lock(frozen_double, monkeypatch):
    fixture = frozen_double
    path = fixture.base / "freeze-receipt.json"
    receipt = json.loads(path.read_text())
    receipt["private_files"][0]["path"] = "../sources.json"
    write_json(path, receipt)
    monkeypatch.setattr(preparer, "HELDOUT_RECEIPT_SHA256", preparer.digest(path))
    with pytest.raises(ValueError, match="Chemin"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)


def test_source_symlink_refused_without_touching_target(frozen_double):
    fixture = frozen_double
    source = fixture.local / fixture.sources["documents"][0]["file"]
    outside = fixture.local.parent / "outside.pdf"
    source.rename(outside)
    source.symlink_to(outside)
    before = outside.read_bytes()
    with pytest.raises(ValueError, match="symbolique"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert outside.read_bytes() == before and not fixture.output.exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO refusal; no FIFO on this platform")
def test_nonregular_source_is_refused_before_a_blocking_open(frozen_double):
    fixture = frozen_double
    source = fixture.local / fixture.sources["documents"][0]["file"]
    source.unlink()
    os.mkfifo(source)
    with pytest.raises(ValueError, match="non régulière"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert not fixture.output.exists()


def test_versions_differ_before_any_render_download_or_output(frozen_double, monkeypatch):
    fixture = frozen_double
    monkeypatch.setattr(materializer, "version", lambda _: "different version")
    with pytest.raises(ValueError, match="Versions"):
        materializer.materialize(fixture.base, fixture.output, download_official=True,
                                  transport=httpx.MockTransport(lambda *_: pytest.fail("Wrong version fetched PDFs")))
    assert not fixture.output.exists() and not fixture.render_calls


@pytest.mark.parametrize("mutation", ["four-originals", "duplicate-id", "rotation", "large-raster", "page-index",
                                      "source-schema", "scan-schema"])
def test_fixed_counts_transforms_and_pixel_budget_refuse_scope_changes(frozen_double, mutation):
    fixture = frozen_double
    if mutation == "four-originals":
        fixture.sources["documents"].append(dict(fixture.sources["documents"][0]))
    elif mutation == "duplicate-id":
        fixture.sources["documents"][1]["id"] = fixture.sources["documents"][0]["id"]
    elif mutation == "rotation":
        fixture.scans["scans"][0]["transform"]["rotation_degrees"] = 90
    elif mutation == "large-raster":
        fixture.scans["scans"][0]["raster_dimensions"] = [100_000, 100_000]
    elif mutation == "source-schema":
        fixture.sources["schema_version"] = 1
    elif mutation == "scan-schema":
        fixture.scans["schema_version"] = 1
    else:
        fixture.scans["scans"][0]["original_page_index"] = 4
    fixture.refreeze()
    with pytest.raises(ValueError):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert not fixture.output.exists()


@pytest.mark.parametrize("failure", ["checksum", "truncated", "oversized", "redirect", "length", "encoding", "stream-error"])
def test_failed_download_never_publishes_partial_or_calls_renderer(frozen_double, failure):
    fixture = frozen_double

    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"%PDF"
            raise httpx.ReadError("explicit truncated HTTP double")

    def explicit_http_double(request):
        raw = fixture.originals[Path(request.url.path).stem]
        headers = {}
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://evil.example/replacement.pdf"})
        if failure == "length":
            headers["Content-Length"] = str(len(raw) + 1)
        if failure == "encoding":
            headers["Content-Encoding"] = "gzip"
        if failure == "checksum":
            raw = b"x" * len(raw)
        if failure == "truncated":
            raw = raw[:-1]
        if failure == "oversized":
            raw += b"x"
        return httpx.Response(200, stream=BrokenStream() if failure == "stream-error" else httpx.ByteStream(raw), headers=headers)

    with pytest.raises((ValueError, httpx.ReadError)):
        materializer.materialize(fixture.base, fixture.output, download_official=True,
                                  transport=httpx.MockTransport(explicit_http_double))
    assert not list((fixture.output / "originals").iterdir()) and not fixture.render_calls
    receipt = json.loads((fixture.output / "materialization-receipt.json").read_text())
    assert receipt["status"] == "failed" and not receipt["frozen_inputs_verified"]


def test_total_download_deadline_checked_even_with_slow_chunks(frozen_double, monkeypatch):
    fixture = frozen_double
    ticks = iter([0, materializer.DOWNLOAD_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(materializer.time, "monotonic", lambda: next(ticks))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(fixture.originals[Path(request.url.path).stem])))
    with pytest.raises(ValueError, match="Délai"):
        materializer.materialize(fixture.base, fixture.output, download_official=True, transport=transport)
    assert not list((fixture.output / "originals").iterdir())


def test_wrong_local_original_rejected_and_inputs_not_modified(frozen_double):
    fixture = frozen_double
    source = fixture.local / fixture.sources["documents"][0]["file"]
    source.write_bytes(b"different original")
    before = snapshot(fixture.local)
    with pytest.raises(ValueError, match="différent du SHA"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert snapshot(fixture.local) == before and not fixture.output.exists()


@pytest.mark.parametrize("kind", ["text-layer", "pdf-bytes", "png-bytes", "original-change", "manifest-change"])
def test_renderer_or_changed_source_never_receives_success_receipt(frozen_double, monkeypatch, kind):
    fixture = frozen_double

    def damaged_renderer(original, spec, output):
        result = fixture.renderer(original, spec, output)
        if kind == "text-layer":
            result["embedded_text"] = True
        elif kind == "pdf-bytes":
            (output / (spec["id"] + ".pdf")).write_bytes(b"different PDF")
        elif kind == "png-bytes":
            (output / (spec["id"] + ".png")).write_bytes(b"different PNG")
        elif kind == "original-change":
            (fixture.local / fixture.sources["documents"][0]["file"]).write_bytes(b"changed while rendering")
        else:
            (fixture.base / "questions-oracles.json").write_bytes(b"changed opaque manifest")
        return result

    monkeypatch.setattr(preparer, "render_scan_pair", damaged_renderer)
    monkeypatch.setattr(preparer, "frozen_inputs", lambda *_: pytest.fail("Unverified result reached final validator"))
    with pytest.raises(ValueError):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    assert json.loads((fixture.output / "materialization-receipt.json").read_text())["status"] == "failed"


def test_existing_output_outside_qa_and_input_overlap_are_refused(frozen_double, monkeypatch):
    fixture = frozen_double
    fixture.output.mkdir()
    (fixture.output / "keep").write_bytes(b"unchanged")
    for target in (fixture.output, fixture.qa.parent / "outside-qa"):
        with pytest.raises(ValueError):
            materializer.materialize(fixture.base, target, originals=fixture.local)
    assert (fixture.output / "keep").read_bytes() == b"unchanged"
    monkeypatch.setattr(materializer, "LOCAL_QA", fixture.base)
    with pytest.raises(ValueError, match="séparée"):
        materializer.materialize(fixture.base, fixture.base / "child", originals=fixture.local)


def test_final_validator_failure_remains_a_failed_materialization(frozen_double, monkeypatch):
    fixture = frozen_double

    def reject_final(_):
        raise ValueError("explicit final frozen validator rejection")

    monkeypatch.setattr(preparer, "frozen_inputs", reject_final)
    with pytest.raises(ValueError, match="final frozen"):
        materializer.materialize(fixture.base, fixture.output, originals=fixture.local)
    receipt = json.loads((fixture.output / "materialization-receipt.json").read_text())
    assert receipt["status"] == "failed" and not receipt["frozen_inputs_verified"]


def test_publication_is_exclusive_and_discards_own_temporary(frozen_double):
    fixture = frozen_double
    path = fixture.qa / "existing.pdf"
    path.write_bytes(b"first")
    with pytest.raises(FileExistsError):
        materializer.publish_bytes(path, [b"second"], expected_bytes=6, expected_sha256=sha(b"second"))
    assert path.read_bytes() == b"first" and not path.with_suffix(".pdf.part").exists()


def test_cli_reports_only_hashes_counts_and_rejects_conflicting_modes(frozen_double, capsys):
    fixture = frozen_double
    arguments = ["--manifests", str(fixture.base), "--output", str(fixture.output), "--originals", str(fixture.local)]
    materializer.main(arguments)
    displayed = capsys.readouterr().out
    assert "OPAQUE EXPLICIT DOUBLE" not in displayed
    assert json.loads(displayed)["scan_pairs"] == 2
    with pytest.raises(SystemExit):
        materializer.main([*arguments, "--download-official"])
