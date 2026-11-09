"""Explicit byte/renderer/HTTP doubles only; no reserved corpus or native engine."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tools.qualification import materialize_trust_i5 as materializer


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return raw


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def frozen_double(tmp_path, monkeypatch):
    corpus, cache, qa = (tmp_path / name for name in ("published-explicit-double", "cache-explicit-double", "qa"))
    corpus.mkdir()
    (cache / "originals").mkdir(parents=True)
    qa.mkdir()
    monkeypatch.setattr(materializer.bounded, "LOCAL_QA", qa)
    originals = {f"D{index}": f"%PDF-1.7 explicit source double {index}".encode() for index in range(3)}
    documents = []
    for key, raw in originals.items():
        relative = f"originals/{key}.pdf"
        (cache / relative).write_bytes(raw)
        documents.append({"id": key, "file": relative, "original_sha256": sha(raw), "bytes": len(raw),
                          "pages": 4, "revision": "explicit-double", "url": f"https://publisher.example/official/{key}.pdf"})
    cases = [{"id": f"Q{index}", "document_id": f"D{index % 3}", "answerable": index < 8,
              "question": f"OPAQUE SYNTHETIC QUESTION {index}",
              "scope": {"kind": "pages", "page_start": 2, "page_end": 2},
              "required_evidence_units": [{"id": f"E{index}", "property": "synthetic oracle only"}]}
             for index in range(10)]
    versions = {name: f"explicit-{name}-double" for name in materializer.RENDERER_PACKAGES}
    scans, pairs = [], {}
    for index, mode in enumerate(("image_only", "image_body_native_footer")):
        key = f"S{index}"
        pdf, png = f"%PDF-1.7 explicit {mode} double".encode(), f"explicit raster double {index}".encode()
        pairs[key] = (pdf, png)
        native = "explicit footer\r\nno answer here\r\n" if index else ""
        transform = {"render_dpi": 200, "scale": 200 / 72, "rotation_degrees": 0, "color": "8-bit grayscale",
                     "resizing_after_render": False, "augmentation": None, "reportlab_invariant": True,
                     "embedded_text": bool(index), "native_footer": ["explicit footer", "no answer here"] if index else None,
                     "native_footer_font": "Helvetica" if index else None,
                     "native_footer_size_points": 7.5 if index else None,
                     "native_footer_positions": [[79, 30], [79, 20]] if index else None,
                     "white_footer_rectangle": [0, 0, 612, 44] if index else None}
        scans.append({"id": key, "kind": mode, "file": f"scans/{key}.pdf", "bytes": len(pdf), "sha256": sha(pdf),
                      "raster_sha256": sha(png), "embedded_text_sha256": sha(native.encode()),
                      "raster_dimensions": [1700, 2200], "original_document_id": f"D{index}",
                      "original_sha256": documents[index]["original_sha256"], "original_page_index": 2,
                      "product_physical_page": 1, "case_id": f"Q{index}", "transform": transform})
    sources = {"schema_version": "i5-heldout-sources-v1", "documents": documents}
    oracles = {"schema_version": "i5-heldout-questions-v1", "cases": cases}
    derived = {"schema_version": "i5-heldout-derived-pairs-v1", "versions": versions, "scans": scans}

    def refreeze():
        for name, value in (("sources.json", sources), ("questions-oracles.json", oracles), ("scan-transformations.json", derived)):
            write_json(corpus / name, value)
        entries = [{"path": name, "bytes": (corpus / name).stat().st_size, "sha256": sha((corpus / name).read_bytes())}
                   for name in sorted(materializer.preparer.MANIFEST_NAMES)]
        receipt = {"schema_version": "i5-heldout-freeze-v1", "counts": dict(materializer.preparer.COUNTS),
                   "frozen_at_utc": "2026-01-01T00:00:00+00:00", "private_files": entries}
        raw = write_json(corpus / "freeze-receipt.json", receipt)
        # A deliberately different synthetic receipt, never a mutation of I5 data.
        monkeypatch.setattr(materializer.preparer, "HELDOUT_RECEIPT_SHA256", sha(raw))

    refreeze()
    monkeypatch.setattr(materializer, "version", versions.__getitem__)
    render_calls = []

    def explicit_renderer_double(original, spec, output):
        assert sha(original.read_bytes()) == spec["original_sha256"]
        pdf, png = pairs[spec["id"]]
        (output / f"{spec['id']}.pdf").write_bytes(pdf)
        (output / f"{spec['id']}.png").write_bytes(png)
        render_calls.append(spec["kind"])
        return {"id": spec["id"], "pdf_sha256": sha(pdf), "raster_sha256": sha(png),
                "embedded_text_sha256": spec["embedded_text_sha256"],
                "original_sha256_unchanged": True, "byte_identical_to_frozen_pair": True}

    monkeypatch.setattr(materializer.preparer, "render_derived", explicit_renderer_double)
    return SimpleNamespace(corpus=corpus, cache=cache, qa=qa, output=qa / "fresh", sources=sources, oracles=oracles,
                           derived=derived, originals=originals, pairs=pairs, refreeze=refreeze,
                           renderer=explicit_renderer_double, render_calls=render_calls)


def failed_receipt(fixture, phase):
    raw = (fixture.output / "materialization-receipt.json").read_text()
    receipt = json.loads(raw)
    assert receipt["status"] == "failed" and not receipt["frozen_inputs_verified"]
    assert receipt["phase"] == phase and receipt["error"]["phase"] == phase
    assert "OPAQUE SYNTHETIC QUESTION" not in raw and "synthetic oracle only" not in raw
    return receipt


def test_local_materialization_checks_i5_mixed_renderer_and_final_validator(frozen_double, monkeypatch, capsys):
    fixture = frozen_double
    before = snapshot(fixture.corpus), snapshot(fixture.cache)
    final_calls = []
    validator = materializer.preparer.frozen_inputs

    def observed_validator(output):
        assert fixture.render_calls == ["image_only", "image_body_native_footer"]
        final_calls.append(output)
        return validator(output)

    monkeypatch.setattr(materializer.preparer, "frozen_inputs", observed_validator)
    monkeypatch.setattr(materializer.httpx, "Client", lambda **_: pytest.fail("Local copies must not create an HTTP client"))
    result = materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    assert result["status"] == "materialized_verified" and result["frozen_inputs_verified"]
    assert result["source_inputs_unchanged"] and result["transport_kind"] == "local_copy"
    assert result["model_calls"] == 0 and not result["ingestion_executed"]
    assert final_calls == [fixture.output] and len(result["originals"]) == 3 and len(result["derived"]) == 2
    for name, raw in before[0].items():
        assert (fixture.output / name).read_bytes() == raw
    assert before == (snapshot(fixture.corpus), snapshot(fixture.cache))
    assert fixture.output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in fixture.output.rglob("*") if path.is_file())
    assert "OPAQUE SYNTHETIC QUESTION" not in (fixture.output / "materialization-receipt.json").read_text()
    assert not capsys.readouterr().out


def test_default_uses_corpus_originals_without_network(frozen_double, monkeypatch):
    fixture = frozen_double
    (fixture.corpus / "originals").mkdir()
    for key, raw in fixture.originals.items():
        (fixture.corpus / "originals" / f"{key}.pdf").write_bytes(raw)
    monkeypatch.setattr(materializer.httpx, "Client", lambda **_: pytest.fail("Unexpected HTTP client"))
    result = materializer.materialize(fixture.corpus, fixture.output)
    assert result["status"] == "materialized_verified" and not result["download"]


def test_missing_default_originals_fail_with_receipt_and_never_download(frozen_double, monkeypatch):
    fixture = frozen_double
    monkeypatch.setattr(materializer.httpx, "Client", lambda **_: pytest.fail("No implicit download"))
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output)
    failed_receipt(fixture, "verify_local_originals")
    assert not fixture.render_calls and not (fixture.output / "sources.json").exists()


def test_receipt_mismatch_rejects_before_parsing_manifests(frozen_double, monkeypatch):
    fixture = frozen_double
    (fixture.corpus / "freeze-receipt.json").write_bytes(b"changed receipt")
    with monkeypatch.context() as patch:
        patch.setattr(materializer.json, "loads", lambda *_: pytest.fail("Unverified bytes parsed"))
        with pytest.raises(materializer.MaterializationFailure):
            materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "verify_manifests")
    assert not fixture.render_calls


def test_corrupted_opaque_oracle_rejected_before_canonical_validation(frozen_double, monkeypatch):
    fixture = frozen_double
    (fixture.corpus / "questions-oracles.json").write_bytes(b"unverified non-JSON oracle \xff")
    monkeypatch.setattr(materializer.preparer, "validate_bundle", lambda *_: pytest.fail("Changed oracle parsed"))
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "verify_manifests")


@pytest.mark.parametrize("mutation", ["i4-schema", "polarity", "unbound-pair", "two-image-only", "footer-position"])
def test_i5_schemas_denominators_and_mixed_page_links_are_mandatory(frozen_double, mutation):
    fixture = frozen_double
    if mutation == "i4-schema":
        fixture.sources["schema_version"] = "i4-heldout-sources-v1"
    elif mutation == "polarity":
        fixture.oracles["cases"][7]["answerable"] = False
    elif mutation == "unbound-pair":
        fixture.derived["scans"][0]["original_document_id"] = "D2"
    elif mutation == "two-image-only":
        fixture.derived["scans"][1]["kind"] = "image_only"
    else:
        fixture.derived["scans"][1]["transform"]["native_footer_positions"] = [[0, 0], [0, 0]]
    fixture.refreeze()
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "verify_manifests")
    assert not fixture.render_calls


@pytest.mark.parametrize("mutation", ["source-traversal", "scan-path", "pdf-size", "raster-sha", "text-sha", "renderer-packages"])
def test_materialization_paths_hashes_and_versions_are_validated_before_copy(frozen_double, mutation):
    fixture = frozen_double
    if mutation == "source-traversal":
        fixture.sources["documents"][0]["file"] = "originals/../outside.pdf"
    elif mutation == "scan-path":
        fixture.derived["scans"][0]["file"] = "scans/different.pdf"
    elif mutation == "pdf-size":
        fixture.sources["documents"][0]["bytes"] = materializer.bounded.MAX_PDF_BYTES + 1
    elif mutation == "raster-sha":
        fixture.derived["scans"][0]["raster_sha256"] = "invalid"
    elif mutation == "text-sha":
        fixture.derived["scans"][0]["embedded_text_sha256"] = "invalid"
    else:
        del fixture.derived["versions"]["Pillow"]
    fixture.refreeze()
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "validate_metadata")
    assert not fixture.render_calls and not (fixture.output / "sources.json").exists()


@pytest.mark.parametrize("url", ["http://publisher.example/source.pdf", "https://user:password@publisher.example/source.pdf",
                               "https://publisher.example:8443/source.pdf", "https://publisher.example/source.pdf#fragment"])
def test_invalid_frozen_url_rejected_before_download(frozen_double, url):
    fixture = frozen_double
    fixture.sources["documents"][0]["url"] = url
    fixture.refreeze()
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, download=True,
                                 transport=httpx.MockTransport(lambda *_: pytest.fail("Invalid URL used")))
    failed_receipt(fixture, "validate_metadata")


def test_renderer_version_mismatch_prevents_copy_or_download(frozen_double, monkeypatch):
    fixture = frozen_double
    monkeypatch.setattr(materializer, "version", lambda _: "different version")
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, download=True,
                                 transport=httpx.MockTransport(lambda *_: pytest.fail("Wrong version downloaded")))
    failed_receipt(fixture, "verify_versions")
    assert not (fixture.output / "originals").exists() and not fixture.render_calls


@pytest.mark.parametrize("kind", ["changed-bytes", "not-pdf", "symlink"])
def test_local_original_integrity_is_checked_before_renderer(frozen_double, kind):
    fixture = frozen_double
    source = fixture.cache / fixture.sources["documents"][0]["file"]
    if kind == "changed-bytes":
        source.write_bytes(b"different original")
    elif kind == "not-pdf":
        raw = b"explicit non-PDF original"
        source.write_bytes(raw)
        fixture.sources["documents"][0].update(bytes=len(raw), original_sha256=sha(raw))
        fixture.derived["scans"][0]["original_sha256"] = sha(raw)
        fixture.refreeze()
    else:
        outside = fixture.cache / "outside.pdf"
        source.rename(outside)
        source.symlink_to(outside)
    before = snapshot(fixture.cache)
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "verify_local_originals")
    assert snapshot(fixture.cache) == before and not fixture.render_calls


def test_explicit_download_uses_exact_frozen_urls_and_named_transport(frozen_double):
    fixture = frozen_double
    requests = []

    def http_double(request):
        requests.append(request)
        assert request.headers["accept-encoding"] == "identity"
        raw = fixture.originals[Path(request.url.path).stem]
        return httpx.Response(200, stream=httpx.ByteStream(raw), headers={"content-length": str(len(raw))})

    result = materializer.materialize(fixture.corpus, fixture.output, download=True, transport=httpx.MockTransport(http_double))
    assert result["status"] == "materialized_verified" and result["transport_kind"] == "explicit_test_substitute"
    assert [str(request.url) for request in requests] == [spec["url"] for spec in fixture.sources["documents"]]
    assert result["download_limits"]["redirects"] is False and result["download_limits"]["environment_proxy"] is False


@pytest.mark.parametrize("failure", ["redirect", "checksum", "truncated", "oversized", "encoding"])
def test_failed_download_keeps_failed_receipt_without_partial_pdf(frozen_double, failure):
    fixture = frozen_double

    def http_double(request):
        raw = fixture.originals[Path(request.url.path).stem]
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/replacement.pdf"})
        if failure == "checksum":
            raw = b"x" * len(raw)
        elif failure == "truncated":
            raw = raw[:-1]
        elif failure == "oversized":
            raw += b"x"
        return httpx.Response(200, stream=httpx.ByteStream(raw), headers={"Content-Encoding": "gzip"} if failure == "encoding" else {})

    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, download=True, transport=httpx.MockTransport(http_double))
    failed_receipt(fixture, "materialize_originals")
    assert not list((fixture.output / "originals").iterdir()) and not fixture.render_calls


@pytest.mark.parametrize("failure", ["pdf", "png", "text", "flag", "exception", "source-change", "manifest-change"])
def test_rendered_and_source_integrity_cannot_receive_success(frozen_double, monkeypatch, failure):
    fixture = frozen_double

    def damaged_renderer(original, spec, output):
        if failure == "exception":
            raise RuntimeError("OPAQUE SYNTHETIC QUESTION must not reach receipt")
        result = fixture.renderer(original, spec, output)
        if failure in {"pdf", "png"}:
            (output / f"{spec['id']}.{failure}").write_bytes(b"different rendered bytes")
        elif failure == "text":
            result["embedded_text_sha256"] = sha(b"different native text")
        elif failure == "flag":
            result["byte_identical_to_frozen_pair"] = False
        elif failure == "source-change":
            (fixture.cache / fixture.sources["documents"][0]["file"]).write_bytes(b"changed source")
        elif failure == "manifest-change":
            (fixture.corpus / "questions-oracles.json").write_bytes(b"changed opaque oracle")
        return result

    monkeypatch.setattr(materializer.preparer, "render_derived", damaged_renderer)
    monkeypatch.setattr(materializer.preparer, "frozen_inputs", lambda *_: pytest.fail("Invalid output reached final validator"))
    with pytest.raises(materializer.MaterializationFailure) as caught:
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    assert "OPAQUE SYNTHETIC QUESTION" not in str(caught.value)
    failed_receipt(fixture, "verify_source_inputs" if failure in {"source-change", "manifest-change"} else "render_derived")


def test_final_validator_error_is_recorded_without_oracle_contents(frozen_double, monkeypatch):
    fixture = frozen_double

    def reject(_):
        raise ValueError("OPAQUE SYNTHETIC QUESTION final validator rejection")

    monkeypatch.setattr(materializer.preparer, "frozen_inputs", reject)
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "final_validator")


def test_interrupt_preserves_receipt_and_completed_inputs(frozen_double, monkeypatch):
    fixture = frozen_double

    def interrupt(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr(materializer.preparer, "render_derived", interrupt)
    with pytest.raises(KeyboardInterrupt):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    receipt = json.loads((fixture.output / "materialization-receipt.json").read_text())
    assert receipt["status"] == "interrupted" and not receipt["frozen_inputs_verified"]
    assert receipt["phase"] == "render_derived" and len(receipt["originals"]) == 3


def test_existing_outside_or_overlapping_output_never_changes_inputs(frozen_double, monkeypatch):
    fixture = frozen_double
    fixture.output.mkdir()
    (fixture.output / "keep").write_bytes(b"preserve")
    before = snapshot(fixture.output), snapshot(fixture.corpus), snapshot(fixture.cache)
    for target in (fixture.output, fixture.qa.parent / "outside"):
        with pytest.raises(ValueError):
            materializer.materialize(fixture.corpus, target, source_cache=fixture.cache)
    monkeypatch.setattr(materializer.bounded, "LOCAL_QA", fixture.corpus)
    with pytest.raises(ValueError):
        materializer.materialize(fixture.corpus, fixture.corpus / "child", source_cache=fixture.cache)
    assert before == (snapshot(fixture.output), snapshot(fixture.corpus), snapshot(fixture.cache))


def test_conflicting_mode_and_implicit_test_transport_have_no_output(frozen_double):
    fixture = frozen_double
    with pytest.raises(ValueError):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache, download=True)
    with pytest.raises(ValueError):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache,
                                 transport=httpx.MockTransport(lambda *_: pytest.fail("Unexpected request")))
    assert not fixture.output.exists()


def test_cli_reports_only_counts_hashes_or_sanitized_failure(frozen_double, capsys, monkeypatch):
    fixture = frozen_double
    arguments = ["--corpus", str(fixture.corpus), "--output", str(fixture.output), "--source-cache", str(fixture.cache)]
    materializer.main(arguments)
    displayed = capsys.readouterr()
    assert "OPAQUE SYNTHETIC QUESTION" not in displayed.out and not displayed.err
    assert json.loads(displayed.out)["derived_pairs"] == 2
    with pytest.raises(SystemExit) as conflict:
        materializer.main([*arguments, "--download"])
    assert conflict.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit) as existing:
        materializer.main(arguments)
    assert existing.value.code == 1 and json.loads(capsys.readouterr().err)["status"] == "refused"
    monkeypatch.setattr(materializer, "version", lambda _: "different")
    arguments[arguments.index(str(fixture.output))] = str(fixture.qa / "different")
    with pytest.raises(SystemExit) as failed:
        materializer.main(arguments)
    assert failed.value.code == 1
    displayed = capsys.readouterr()
    assert not displayed.out and "OPAQUE SYNTHETIC QUESTION" not in displayed.err
    assert json.loads(displayed.err)["phase"] == "verify_versions"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO refusal needs POSIX")
def test_nonregular_original_refused_before_blocking_open(frozen_double):
    fixture = frozen_double
    source = fixture.cache / fixture.sources["documents"][0]["file"]
    source.unlink()
    os.mkfifo(source)
    with pytest.raises(materializer.MaterializationFailure):
        materializer.materialize(fixture.corpus, fixture.output, source_cache=fixture.cache)
    failed_receipt(fixture, "verify_local_originals")
