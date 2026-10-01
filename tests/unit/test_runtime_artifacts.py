"""Provisionnement par plateforme et extraction sûre des archives .tar.gz et .tar.zst (W018), sur archives construites."""

import gzip
import io
import json
import tarfile

import pytest

from services.runtime import artifacts
from services.runtime.artifacts import extract_verified_archive, file_hash
from services.runtime.platforms import platform_id

zstandard = pytest.importorskip("zstandard")


def member(name: str, data: bytes = b"", **fields) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o755
    for key, value in fields.items():
        setattr(info, key, value)
    return info, data


def tar_bytes(*members: tuple[tarfile.TarInfo, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for info, data in members:
            archive.addfile(info, io.BytesIO(data) if info.isreg() else None)
    return buffer.getvalue()


def write_gz(path, payload: bytes):
    path.write_bytes(gzip.compress(payload))
    return path


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    return tmp_path


def test_tar_gz_extraction_records_sha256_of_files_and_internal_links(root):
    payload = tar_bytes(member("qdrant", b"\x7fELF qdrant"), member("lib/", type=tarfile.DIRTYPE),
                        member("lib/libx.so.1", b"bibliotheque"),
                        member("lib/libx.so", type=tarfile.SYMTYPE, linkname="libx.so.1"))
    archive = write_gz(root / "qdrant.tar.gz", payload)
    result = extract_verified_archive(archive, root / "bin/qdrant-1.19.1")
    binary = root / "bin/qdrant-1.19.1/qdrant"
    assert {item["path"]: item["sha256"] for item in result["files"]} == {
        "bin/qdrant-1.19.1/qdrant": file_hash(binary), "bin/qdrant-1.19.1/lib/libx.so.1": file_hash(root / "bin/qdrant-1.19.1/lib/libx.so.1")}
    assert result["links"] == [{"path": "bin/qdrant-1.19.1/lib/libx.so", "target": "libx.so.1"}]
    assert (root / "bin/qdrant-1.19.1/lib/libx.so").read_bytes() == b"bibliotheque"
    assert binary.stat().st_mode & 0o100


@pytest.mark.parametrize(("hostile", "reason"), [
    (member("../evade", b"x"), "remontant"),
    (member("bin/../../evade", b"x"), "remontant"),
    (member("/etc/evade", b"x"), "absolu"),
    (member("lien", type=tarfile.SYMTYPE, linkname="../../evade"), "LinkOutsideDestinationError"),
    (member("lien", type=tarfile.SYMTYPE, linkname="/etc/passwd"), "AbsoluteLinkError"),
    (member("dur", type=tarfile.LNKTYPE, linkname="../evade"), "refusé"),
    (member("console", type=tarfile.CHRTYPE, devmajor=5, devminor=1), "SpecialFileError"),
    (member("tube", type=tarfile.FIFOTYPE), "SpecialFileError"),
])
def test_hostile_members_are_refused_and_nothing_leaves_the_destination(root, hostile, reason):
    archive = write_gz(root / "hostile.tar.gz", tar_bytes(member("ok", b"premier"), hostile))
    with pytest.raises(ValueError, match=reason):
        extract_verified_archive(archive, root / "dest")
    assert not (root / "evade").exists() and not (root.parent / "evade").exists()
    assert sorted(path.name for path in (root / "dest").iterdir()) == ["ok"]


def test_link_planted_by_an_earlier_member_cannot_redirect_a_later_file(root):
    # Un lien interne vers un dossier, puis un fichier « à travers » ce lien : refusé s'il sort de la destination.
    (root / "dehors").mkdir()
    payload = tar_bytes(member("sortie", type=tarfile.SYMTYPE, linkname="../dehors"), member("sortie/fichier", b"x"))
    with pytest.raises(ValueError):
        extract_verified_archive(write_gz(root / "detour.tar.gz", payload), root / "dest")
    assert list((root / "dehors").iterdir()) == []


def multi_frame_zst(path, payload: bytes, cut: int):
    """Deux trames zstd concaténées, coupées à une frontière de membre : forme des archives produites en parallèle."""
    compressor = zstandard.ZstdCompressor(level=3)
    path.write_bytes(compressor.compress(payload[:cut]) + compressor.compress(payload[cut:]))
    return path


def test_multi_frame_zstd_archive_is_read_to_the_end(root):
    first, second = member("bin/ollama", b"o" * 1000), member("lib/ollama/libggml.so", b"g" * 3000)
    payload = tar_bytes(first, second)
    cut = 512 + 1024  # en-tête du premier membre et ses données arrondies au bloc
    archive = multi_frame_zst(root / "ollama.tar.zst", payload, cut)
    # Témoin de la forme multi-trame : par défaut (read_across_frames=False), une lecture s'arrête à la frontière de
    # trame. Constat avec python-zstandard 0.25.0 : la lecture suivante reprend à la trame suivante ; seul un lecteur
    # qui prendrait une lecture courte pour la fin perdrait la suite.
    with archive.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader:
        assert len(reader.read(10240)) == cut
    result = extract_verified_archive(archive, root / "bin/ollama-0.35.0")
    assert [item["path"] for item in result["files"]] == ["bin/ollama-0.35.0/bin/ollama", "bin/ollama-0.35.0/lib/ollama/libggml.so"]
    assert (root / "bin/ollama-0.35.0/lib/ollama/libggml.so").read_bytes() == b"g" * 3000


def test_trailing_data_after_the_tar_end_is_refused(root):
    payload = tar_bytes(member("a", b"x")) + b"donnees parasites" + b"\0" * 1024
    with pytest.raises(ValueError, match="Données après la fin"):
        extract_verified_archive(write_gz(root / "queue.tar.gz", payload), root / "dest")


def test_zstd_window_above_the_bound_is_refused(root, monkeypatch):
    monkeypatch.setattr(artifacts, "ZSTD_MAX_WINDOW", 1 << 20)
    payload = tar_bytes(member("gros", bytes(range(256)) * 16384))
    compressor = zstandard.ZstdCompressor(compression_params=zstandard.ZstdCompressionParameters.from_level(3, window_log=24))
    archive = root / "fenetre.tar.zst"
    archive.write_bytes(compressor.compress(payload))
    with pytest.raises(zstandard.ZstdError):
        extract_verified_archive(archive, root / "dest")


def test_provision_downloads_only_the_entries_of_this_platform(root, monkeypatch):
    current = platform_id()
    other = "windows-x86_64" if current != "windows-x86_64" else "linux-aarch64"
    lock = {"schema_version": 1, "groups": {
        "qdrant": [{"platform": other, "url": "https://autre/q.zip", "target": "cache/q-autre.zip", "sha256": "0" * 64},
                   {"platform": current, "url": "https://ici/q", "target": "cache/q-ici.bin", "sha256": "1" * 64}],
        "tessdata": [{"url": "https://commun/fra", "target": "models/fra.traineddata", "git_blob_sha1": "2" * 40}],
        "tesseract-source": [{"platform": other, "url": "https://autre/src", "target": "cache/src.tar.gz", "sha256": "3" * 64}]}}
    (root / "config").mkdir()
    (root / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", root / "config/artifacts.lock.json")
    downloaded = []

    def fake_download(entry, target, *, offline=False):
        downloaded.append(entry["url"])
        return {**entry, "path": str(target.relative_to(root)), "cached": True}

    monkeypatch.setattr(artifacts, "download", fake_download)
    manifest = artifacts.provision_artifacts()
    assert downloaded == ["https://ici/q", "https://commun/fra"]
    assert set(manifest) == {"qdrant", "tessdata"} and [item["url"] for item in manifest["qdrant"]] == ["https://ici/q"]
    assert json.loads((root / ".runtime/manifests/artifacts.json").read_text(encoding="utf-8")) == manifest


def test_manifest_paths_stay_relative_to_the_program_when_runtime_is_a_symlink(tmp_path, monkeypatch):
    # Installation Linux (W018) dont .runtime est un lien vers un autre volume : le manifeste garde des chemins sous la racine.
    program, card = tmp_path / "programme", tmp_path / "carte"
    (card / "runtime").mkdir(parents=True)
    program.mkdir()
    (program / ".runtime").symlink_to(card / "runtime", target_is_directory=True)
    monkeypatch.setattr(artifacts, "ROOT", program)
    archive = write_gz(tmp_path / "qdrant.tar.gz", tar_bytes(member("qdrant", b"\x7fELF")))
    result = extract_verified_archive(archive, program / ".runtime/bin/qdrant-1.19.1")
    assert result["files"] == [{"path": ".runtime/bin/qdrant-1.19.1/qdrant",
                                "sha256": file_hash(card / "runtime/bin/qdrant-1.19.1/qdrant"), "size": 4}]


def test_a_regular_member_reusing_the_name_of_an_internal_link_is_refused(root):
    # Revue R1 : `t`, puis `x` → `t`, puis un fichier régulier `x` écrit à travers le lien ; `t` était écrasé alors que
    # le manifeste gardait son ancienne empreinte, et `x` restait un lien consigné comme fichier.
    payload = tar_bytes(member("t", b"target"), member("x", type=tarfile.SYMTYPE, linkname="t"), member("x", b"pwn-via-link"))
    with pytest.raises(ValueError, match="déjà présent"):
        extract_verified_archive(write_gz(root / "meme-nom.tar.gz", payload), root / "dest")
    assert (root / "dest/t").read_bytes() == b"target"


@pytest.mark.parametrize("names", [("lib/", "lib/"), ("./a", "a"), ("a", "a")])
def test_a_member_name_seen_twice_is_refused(root, names):
    first, second = (member(name, type=tarfile.DIRTYPE) if name.endswith("/") else member(name, b"premier") for name in names)
    with pytest.raises(ValueError, match="déjà présent"):
        extract_verified_archive(write_gz(root / "double.tar.gz", tar_bytes(first, second)), root / "dest")


def test_no_member_is_written_through_an_internal_directory_link(root):
    # Lien interne vers un dossier de la destination : le filtre `data` l'admet, mais le fichier consigné sous `alias/`
    # serait écrit dans `reel/` ; le manifeste ne décrirait plus le disque.
    payload = tar_bytes(member("reel/", type=tarfile.DIRTYPE), member("alias", type=tarfile.SYMTYPE, linkname="reel"),
                        member("alias/f", b"x"))
    with pytest.raises(ValueError, match="à travers un lien"):
        extract_verified_archive(write_gz(root / "alias.tar.gz", payload), root / "dest")
    assert list((root / "dest/reel").iterdir()) == []


def test_no_member_is_written_through_a_link_left_by_an_earlier_extraction(root):
    # Nouvelle extraction dans un dossier déjà provisionné : un lien interne existant n'est jamais traversé en écriture.
    destination = root / "dest"
    destination.mkdir()
    (destination / "t").write_bytes(b"ancien")
    (destination / "x").symlink_to("t")
    with pytest.raises(ValueError, match="à travers un lien"):
        extract_verified_archive(write_gz(root / "reprise.tar.gz", tar_bytes(member("x", b"pwn"))), destination)
    assert (destination / "t").read_bytes() == b"ancien"


def test_links_of_an_earlier_extraction_are_replaced_by_the_same_links(root):
    # Réextraction d'une archive à liens internes (forme de l'archive Ollama) : chaque lien existant est remplacé, pas
    # traversé, et le manifeste est identique à celui de la première extraction.
    payload = tar_bytes(member("lib/", type=tarfile.DIRTYPE), member("lib/libx.so.1", b"bibliotheque"),
                        member("lib/libx.so", type=tarfile.SYMTYPE, linkname="libx.so.1"))
    archive = write_gz(root / "liens.tar.gz", payload)
    first = extract_verified_archive(archive, root / "dest")
    assert extract_verified_archive(archive, root / "dest") == first
    assert (root / "dest/lib/libx.so").is_symlink() and (root / "dest/lib/libx.so.1").read_bytes() == b"bibliotheque"
