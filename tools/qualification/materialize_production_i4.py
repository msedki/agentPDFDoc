"""Materialize the frozen I4 inputs without exposing question/oracle contents.

No network is used unless --download-official is supplied. The three official
PDFs must still match their frozen bytes. Rendering is shared with the existing
reproduction harness; this tool never runs ingestion, retrieval, OCR or a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.qualification import prepare_production_i4 as preparer  # noqa: E402
from tools.qualification.evidence_io import LOCAL_QA, checked_output  # noqa: E402

MANIFESTS = frozenset({"sources.json", "questions-oracles.json", "scan-transformations.json"})
MAX_MANIFEST_BYTES = 1_048_576
MAX_PDF_BYTES = 16_777_216
MAX_RASTER_PIXELS = 13_000_000
CHUNK_BYTES = 65_536
DOWNLOAD_TIMEOUT_SECONDS = 15.0
DOWNLOAD_DEADLINE_SECONDS = 120.0
SHA256 = re.compile(r"[0-9a-f]{64}")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}")
EXPECTED_TRANSFORM = {
    "render_dpi": 200, "scale": 200 / 72, "rotation_degrees": 0,
    "color": "8-bit grayscale", "resizing_after_render": False,
    "augmentation": None, "embedded_text": False, "reportlab_invariant": True,
}


def relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError("Chemin de manifeste invalide.")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value or any(part in {".", ".."} for part in path.parts)
            or any(char in value for char in "\\:") or any(part.endswith((".", " ")) for part in path.parts)):
        raise ValueError("Chemin de manifeste hors du dossier autorisé.")
    return path


@contextmanager
def regular_input(base: Path, relative: str, maximum: int) -> Iterator[BinaryIO]:
    """Open an existing confined regular file without following child symlinks."""
    root = base.resolve(strict=True)
    path = root
    for part in relative_path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Lien symbolique refusé dans les entrées gelées.")
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Une entrée gelée sort du dossier autorisé.")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Entrée non régulière refusée avant ouverture.")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
            raise ValueError("Entrée non régulière, vide ou trop volumineuse.")
        yield handle


def read_bounded(base: Path, relative: str, maximum: int = MAX_MANIFEST_BYTES) -> bytes:
    with regular_input(base, relative, maximum) as handle:
        raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("Entrée devenue trop volumineuse pendant la lecture.")
        return raw


def load_bundle(base: Path) -> tuple[dict[str, bytes], dict, dict]:
    """Verify all opaque manifest bytes before parsing source/transform metadata."""
    receipt_raw = read_bounded(base, "freeze-receipt.json")
    if hashlib.sha256(receipt_raw).hexdigest() != preparer.HELDOUT_RECEIPT_SHA256:
        raise ValueError("Le reçu de gel diffère du verrou I4 publié.")
    receipt = json.loads(receipt_raw)
    bundle = {"freeze-receipt.json": receipt_raw}
    for entry in receipt["private_files"]:
        name = relative_path(entry["path"]).name
        if name not in MANIFESTS or name in bundle:
            raise ValueError("Liste des manifestes gelés différente du périmètre I4.")
        raw = read_bounded(base, name)
        if (type(entry.get("bytes")) is not int or len(raw) != entry["bytes"]
                or hashlib.sha256(raw).hexdigest() != entry["sha256"]):
            raise ValueError("Octets de manifeste différents du gel : " + name)
        bundle[name] = raw
    if set(bundle) != MANIFESTS | {"freeze-receipt.json"}:
        raise ValueError("Les trois manifestes gelés sont requis.")
    # questions-oracles.json deliberately remains an opaque byte string here.
    return bundle, json.loads(bundle["sources.json"]), json.loads(bundle["scan-transformations.json"])


def validate_metadata(sources: dict, scans: dict) -> None:
    documents = sources.get("documents", [])
    specifications = scans.get("scans", [])
    if (sources.get("schema_version") != "i4-heldout-sources-v1"
            or scans.get("schema_version") != "i4-heldout-scan-pairs-v1"
            or len(documents) != 3 or len(specifications) != 2
            or set(scans.get("versions", {})) != {"pypdfium2", "Pillow", "reportlab"}):
        raise ValueError("Le périmètre I4 exige trois originaux et deux scans gelés.")
    originals = {}
    paths = set()
    for spec in documents:
        path = relative_path(spec["file"])
        url = urlsplit(spec["url"])
        if (not IDENTIFIER.fullmatch(spec["id"]) or spec["id"] in originals
                or path in paths or len(path.parts) != 2 or path.parts[0] != "originals"
                or path.suffix.lower() != ".pdf" or not SHA256.fullmatch(spec["original_sha256"])
                or type(spec["bytes"]) is not int or not 0 < spec["bytes"] <= MAX_PDF_BYTES
                or type(spec["pages"]) is not int or spec["pages"] <= 0):
            raise ValueError("Métadonnées d'original hors du périmètre gelé.")
        if (url.scheme != "https" or url.netloc != "www.analog.com" or url.query or url.fragment
                or not url.path.startswith("/media/en/technical-documentation/data-sheets/")
                or not url.path.lower().endswith(".pdf")):
            raise ValueError("Seules les URL HTTPS officielles www.analog.com gelées sont admises.")
        originals[spec["id"]] = spec
        paths.add(path)
    scan_ids = set()
    for spec in specifications:
        original = originals.get(spec["original_document_id"])
        dimensions = spec["raster_dimensions"]
        if (not IDENTIFIER.fullmatch(spec["id"]) or spec["id"] in scan_ids
                or str(relative_path(spec["file"])) != "scans/" + spec["id"] + ".pdf"
                or not SHA256.fullmatch(spec["sha256"]) or not SHA256.fullmatch(spec["raster_sha256"])
                or type(spec["bytes"]) is not int or not 0 < spec["bytes"] <= MAX_PDF_BYTES
                or original is None or spec["original_sha256"] != original["original_sha256"]
                or type(spec["original_page_index"]) is not int
                or not 0 <= spec["original_page_index"] < original["pages"]
                or spec["transform"] != EXPECTED_TRANSFORM
                or not isinstance(dimensions, list) or len(dimensions) != 2
                or any(type(value) is not int or value <= 0 for value in dimensions)
                or dimensions[0] * dimensions[1] > MAX_RASTER_PIXELS):
            raise ValueError("Transformation de scan incompatible avec l'algorithme gelé.")
        scan_ids.add(spec["id"])


def verify_original(base: Path, spec: dict) -> None:
    with regular_input(base, spec["file"], MAX_PDF_BYTES) as handle:
        checksum = hashlib.sha256()
        count = 0
        while chunk := handle.read(CHUNK_BYTES):
            count += len(chunk)
            if count > spec["bytes"]:
                raise ValueError("Original plus volumineux que le gel.")
            checksum.update(chunk)
    if count != spec["bytes"] or checksum.hexdigest() != spec["original_sha256"]:
        raise ValueError("Original différent du SHA ou de la taille gelés : " + spec["id"])


def publish_bytes(path: Path, chunks, *, expected_bytes: int, expected_sha256: str) -> None:
    """Never publish a truncated/wrong input, and never replace an existing file."""
    partial = path.with_name(path.name + ".part")
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        checksum, count = hashlib.sha256(), 0
        with os.fdopen(descriptor, "wb") as handle:
            for chunk in chunks:
                count += len(chunk)
                if count > min(expected_bytes, MAX_PDF_BYTES):
                    raise ValueError("Téléchargement ou copie au-delà du plafond gelé.")
                checksum.update(chunk)
                handle.write(chunk)
            if count != expected_bytes or checksum.hexdigest() != expected_sha256:
                raise ValueError("Téléchargement ou copie incomplet, ou SHA différent du gel.")
            handle.flush()
            os.fsync(handle.fileno())
        # A hard link is an exclusive publication, unlike replace()/POSIX rename().
        os.link(partial, path, follow_symlinks=False)
    finally:
        partial.unlink(missing_ok=True)


def download_original(client: httpx.Client, spec: dict, target: Path) -> None:
    started = time.monotonic()
    with client.stream("GET", spec["url"]) as response:
        if response.status_code != 200 or str(response.url) != spec["url"]:
            raise ValueError("Réponse officielle non directe ou en échec ; aucun repli d'URL.")
        length = response.headers.get("content-length")
        if ((length is not None and (not length.isdecimal() or int(length) != spec["bytes"]))
                or response.headers.get("content-encoding", "identity").lower() != "identity"):
            raise ValueError("Taille ou encodage HTTP différent de l'original gelé.")

        def bounded_chunks():
            for chunk in response.iter_raw(CHUNK_BYTES):
                if time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                    raise ValueError("Délai total de téléchargement dépassé.")
                yield chunk
            if time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                raise ValueError("Délai total de téléchargement dépassé.")

        publish_bytes(target, bounded_chunks(), expected_bytes=spec["bytes"], expected_sha256=spec["original_sha256"])


def private_output(path: Path, input_roots: tuple[Path, ...]) -> Path:
    output = checked_output(path, [LOCAL_QA])
    if any(output.is_relative_to(root.resolve()) for root in input_roots):
        raise ValueError("La matérialisation doit rester séparée des entrées immuables.")
    root = LOCAL_QA.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent = root
    for part in output.relative_to(root).parts[:-1]:
        parent = parent / part
        parent.mkdir(mode=0o700, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=False)
    output.chmod(0o700)
    return output


def materialize(manifests: Path, output: Path, *, originals: Path | None = None,
                download_official: bool = False, transport: httpx.BaseTransport | None = None) -> dict:
    """An explicit test transport is only a named substitute, never qualification."""
    if download_official and originals is not None:
        raise ValueError("Choisir les copies locales ou le téléchargement officiel, pas les deux.")
    if transport is not None and not download_official:
        raise ValueError("Un transport de test exige le mode téléchargement explicite.")
    manifests = manifests.resolve(strict=True)
    bundle, sources, scans = load_bundle(manifests)
    validate_metadata(sources, scans)
    actual_versions = {name: version(name) for name in scans["versions"]}
    if actual_versions != scans["versions"]:
        raise ValueError("Versions PDFium/Pillow/reportlab différentes du gel ; aucun rendu ni téléchargement.")
    original_root = (originals or manifests).resolve(strict=True)
    if not download_official:
        for spec in sources["documents"]:
            try:
                verify_original(original_root, spec)
            except FileNotFoundError as error:
                raise ValueError("Originaux locaux absents ; fournir --originals ou autoriser --download-official.") from error
    output = private_output(output, (manifests, original_root))
    report: dict[str, Any] = {"kind": "frozen_i4_input_materialization", "status": "started",
              "started_utc": datetime.now(UTC).isoformat(), "output": str(output),
              "heldout_receipt_sha256": preparer.HELDOUT_RECEIPT_SHA256,
              "harness_sha256": preparer.digest(Path(__file__)),
              "shared_renderer_sha256": preparer.digest(Path(preparer.__file__)),
              "versions": actual_versions, "download_official": download_official,
              "transport_kind": "explicit_test_substitute" if transport is not None else "native_https" if download_official else "local_copy",
              "oracle_content_emitted": False, "ingestion_executed": False, "model_calls": 0,
              "download_limits": {"maximum_pdf_bytes": MAX_PDF_BYTES, "io_timeout_seconds": DOWNLOAD_TIMEOUT_SECONDS,
                                  "deadline_checked_between_chunks_seconds": DOWNLOAD_DEADLINE_SECONDS,
                                  "redirects": False, "environment_proxy": False},
              "manifests": [], "originals": [], "scans": [], "frozen_inputs_verified": False,
              "measurement_limit": "Byte-identical input materialization only; no extraction, OCR, answer or production qualification."}
    try:
        for name, raw in bundle.items():
            checksum = hashlib.sha256(raw).hexdigest()
            publish_bytes(output / name, [raw], expected_bytes=len(raw), expected_sha256=checksum)
            report["manifests"].append({"file": name, "sha256": checksum, "bytes": len(raw)})
        (output / "originals").mkdir(mode=0o700)
        with httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
                          timeout=DOWNLOAD_TIMEOUT_SECONDS, headers={"Accept-Encoding": "identity"}) as client:
            for spec in sources["documents"]:
                target = output / spec["file"]
                if download_official:
                    download_original(client, spec, target)
                else:
                    with regular_input(original_root, spec["file"], MAX_PDF_BYTES) as handle:
                        publish_bytes(target, iter(lambda: handle.read(CHUNK_BYTES), b""),
                                      expected_bytes=spec["bytes"], expected_sha256=spec["original_sha256"])
                report["originals"].append({"id": spec["id"], "file": spec["file"], "sha256": preparer.digest(target),
                                            "bytes": target.stat().st_size, "url": spec["url"],
                                            "method": "official_https" if download_official else "verified_local_copy"})
        (output / "scans").mkdir(mode=0o700)
        by_id = {spec["id"]: spec for spec in sources["documents"]}
        for spec in scans["scans"]:
            original = output / by_id[spec["original_document_id"]]["file"]
            checked = preparer.render_scan_pair(original, spec, output / "scans")
            report["scans"].append(checked)
            png, pdf = output / "scans" / (spec["id"] + ".png"), output / spec["file"]
            if (checked.get("embedded_text") is not False or checked.get("original_sha256_unchanged") is not True
                    or preparer.digest(pdf) != spec["sha256"] or pdf.stat().st_size != spec["bytes"]
                    or preparer.digest(png) != spec["raster_sha256"]):
                raise ValueError("Scan reconstruit différent du gel ou contenant une couche texte.")
            png.chmod(0o600)
            pdf.chmod(0o600)
        for name, expected in bundle.items():
            if read_bounded(manifests, name) != expected:
                raise ValueError("Un manifeste source a changé pendant la matérialisation.")
        if not download_official:
            for spec in sources["documents"]:
                verify_original(original_root, spec)
        report["source_inputs_unchanged"] = True
        # The canonical validator checks the frozen count/polarity internally;
        # neither its oracle object nor its question text is displayed or saved.
        preparer.frozen_inputs(output)
        report["frozen_inputs_verified"] = True
        report["status"] = "materialized_verified"
        return report
    except Exception as error:
        report["status"] = "failed"
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_utc"] = datetime.now(UTC).isoformat()
        preparer.save_new(output / "materialization-receipt.json", report)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests", type=Path, required=True, help="Dossier des quatre manifestes publiés, octets gelés.")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau dossier sous .runtime/qa, jamais écrasé.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--originals", type=Path, help="Racine locale contenant originals/ et les PDF aux SHA gelés.")
    mode.add_argument("--download-official", action="store_true", help="Autoriser exactement les trois URL officielles gelées.")
    args = parser.parse_args(argv)
    result = materialize(args.manifests, args.output, originals=args.originals, download_official=args.download_official)
    receipt = Path(result["output"]) / "materialization-receipt.json"
    print(json.dumps({"status": result["status"], "receipt": str(receipt), "receipt_sha256": preparer.digest(receipt),
                      "originals": len(result["originals"]), "scan_pairs": len(result["scans"]),
                      "oracle_content_emitted": False, "model_calls": 0}))


if __name__ == "__main__":
    main()
