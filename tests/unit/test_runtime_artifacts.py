"""Provisionnement par plateforme et extraction sûre des archives .tar.gz et .tar.zst (W018), sur archives construites."""

import gzip
import hashlib
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


def _lock_with_sources_for_this_platform(root, monkeypatch, *, sources_sha256: str = "3" * 64) -> dict:
    """Verrou dont le groupe `tesseract-source` vaut pour ce poste, entre deux groupes ordinaires."""
    current = platform_id()
    lock = {"schema_version": 1, "groups": {
        "qdrant": [{"platform": current, "url": "https://ici/q", "target": "cache/q-ici.bin", "sha256": "1" * 64}],
        "tesseract-source": [
            {"platform": [current, "autre-plateforme"], "url": "https://sources/leptonica", "target": "cache/leptonica.tar.gz",
             "sha256": sources_sha256, "content_sha256": "4" * 64},
            {"platform": [current], "url": "https://sources/tesseract", "target": "cache/tesseract.tar.gz",
             "sha256": sources_sha256, "content_sha256": "5" * 64}],
        "tessdata": [{"url": "https://commun/fra", "target": "models/fra.traineddata", "git_blob_sha1": "2" * 40}]}}
    (root / "config").mkdir(exist_ok=True)
    (root / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", root / "config/artifacts.lock.json")
    return lock


def test_provision_leaves_the_tesseract_sources_to_the_tesseract_build(root, monkeypatch):
    # Revue OCR R2b : provision_artifacts téléchargeait les sources avec contrôle strict de l'empreinte d'archive, avant
    # provisioning.build_tesseract ; une archive de tag régénérée par GitHub (contenu conforme) était refusée avant
    # d'atteindre la vérification par empreinte de contenu. Le groupe est désormais laissé à build_tesseract.
    from services.runtime import provisioning

    _lock_with_sources_for_this_platform(root, monkeypatch)
    downloaded = []

    def fake_download(entry, target, *, offline=False):
        downloaded.append(entry["url"])
        return {**entry, "path": str(target.relative_to(root)), "cached": True}

    monkeypatch.setattr(artifacts, "download", fake_download)
    manifest = artifacts.provision_artifacts()
    assert downloaded == ["https://ici/q", "https://commun/fra"]
    assert set(manifest) == {"qdrant", "tessdata"}
    assert json.loads((root / ".runtime/manifests/artifacts.json").read_text(encoding="utf-8")) == manifest
    # Même nom de groupe des deux côtés : celui que build_tesseract lit dans le verrou.
    assert artifacts.TESSERACT_SOURCE_GROUP == provisioning.SOURCE_GROUP


def test_offline_provision_accepts_a_regenerated_source_archive_left_for_the_tesseract_build(root, monkeypatch):
    # Chaîne réelle hors ligne, sans double de download : archive des sources en cache d'empreinte différente du verrou
    # (archive de tag régénérée). Avant correction : FileNotFoundError « Artefact offline absent ou corrompu ».
    _lock_with_sources_for_this_platform(root, monkeypatch)
    (root / "cache").mkdir()
    for name in ("leptonica", "tesseract"):
        (root / f"cache/{name}.tar.gz").write_bytes(b"archive regeneree " + name.encode())
    qdrant = b"binaire qdrant"
    (root / "cache/q-ici.bin").write_bytes(qdrant)
    tessdata = b"modele fra"
    (root / "models").mkdir()
    (root / "models/fra.traineddata").write_bytes(tessdata)
    lock = json.loads((root / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    lock["groups"]["qdrant"][0]["sha256"] = hashlib.sha256(qdrant).hexdigest()
    lock["groups"]["tessdata"][0]["git_blob_sha1"] = hashlib.sha1(b"blob %d\0" % len(tessdata) + tessdata).hexdigest()
    (root / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    manifest = artifacts.provision_artifacts(offline=True)
    assert set(manifest) == {"qdrant", "tessdata"}
    assert (root / "cache/tesseract.tar.gz").read_bytes() == b"archive regeneree tesseract"


def test_provision_only_the_tesseract_sources_is_refused_with_the_command_to_run(root, monkeypatch):
    _lock_with_sources_for_this_platform(root, monkeypatch)
    monkeypatch.setattr(artifacts, "download", lambda *args, **kwargs: pytest.fail("aucun téléchargement attendu"))
    with pytest.raises(ValueError, match="tesseract-source.*construction de Tesseract.*provision"):
        artifacts.provision_artifacts("tesseract-source")
    assert not (root / ".runtime/manifests/artifacts.json").exists()


# --- Complément GPU d'Ollama (W024, W025) ------------------------------------------------------------------------------

REPOSITORY = __import__("pathlib").Path(__file__).resolve().parents[2]


def _repository_lock() -> dict:
    return json.loads((REPOSITORY / "config/artifacts.lock.json").read_text(encoding="utf-8"))


def test_gpu_complements_share_version_and_folder_with_the_base_archive_of_their_platform():
    import re

    from services.runtime.accelerator import GPU_GROUP, JETPACK_BY_L4T
    from services.runtime.platforms import entries_for_platform

    groups = _repository_lock()["groups"]
    complements = groups[GPU_GROUP]
    # Valeurs de la release v0.35.0 (API des releases et sha256sum.txt, consultés le 01/10/2026).
    assert [(entry["url"].rsplit("/", 1)[-1], entry["size"], entry["sha256"], entry.get("extracted_size"))
            for entry in complements] == [
        ("ollama-linux-arm64-jetpack5.tar.zst", 297201571,
         "f7f1a7e890f2a493014f01cf8de948b5aa4641f34c05d2cb61983649b9c20f5b", 864658584),
        ("ollama-linux-arm64-jetpack6.tar.zst", 269692742,
         "609be1fb0f0d28ea3b10df7194508562da431200568157eef36de5745edd2753", None)]
    for entry in complements:
        (base,) = entries_for_platform(groups["ollama"], entry["platform"])
        jetpack = JETPACK_BY_L4T[entry["host"]["l4t_major"]]
        assert (entry["version"], entry["extract_to"]) == (base["version"], base["extract_to"])
        assert entry["url"] == (f"https://github.com/ollama/ollama/releases/download/v{entry['version']}/"
                                f"ollama-linux-arm64-{jetpack}.tar.zst")
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) and entry["variant"] == f"cuda_{jetpack}"
        assert entry["target"] == f".runtime/cache/downloads/ollama-{entry['version']}-linux-arm64-{jetpack}.tar.zst"
        assert set(entry["host"]) == {"l4t_major"} and entry["license"] == base["license"]
    # Aucun complément Windows ni Linux x86-64 : leurs archives de base portent déjà cuda_v12 et cuda_v13.
    assert {entry["platform"] for entry in complements} == {"linux-aarch64"}
    # Le champ host est propre à ce groupe ; le groupe ollama garde une seule entrée par plateforme (native_paths).
    assert not [name for name, entries in groups.items() if name != GPU_GROUP for entry in entries if "host" in entry]
    for platform in ("windows-x86_64", "linux-aarch64", "linux-x86_64"):
        assert len(entries_for_platform(groups["ollama"], platform)) == 1


def _lock_with_gpu_complements(root, monkeypatch) -> None:
    lock = {"schema_version": 1, "groups": {
        "ollama": [{"platform": "linux-aarch64", "url": "https://ici/ollama-linux-arm64.tar.zst",
                    "target": "cache/base.tar.zst", "sha256": "1" * 64},
                   {"platform": "windows-x86_64", "url": "https://ici/ollama-windows-amd64.zip",
                    "target": "cache/base.zip", "sha256": "2" * 64}],
        "ollama-gpu": [{"platform": "linux-aarch64", "host": {"l4t_major": 35}, "variant": "cuda_jetpack5",
                        "url": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "target": "cache/jp5.tar.zst",
                        "sha256": "3" * 64},
                       {"platform": "linux-aarch64", "host": {"l4t_major": 36}, "variant": "cuda_jetpack6",
                        "url": "https://ici/ollama-linux-arm64-jetpack6.tar.zst", "target": "cache/jp6.tar.zst",
                        "sha256": "4" * 64}]}}
    (root / "config").mkdir(exist_ok=True)
    (root / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", root / "config/artifacts.lock.json")


@pytest.fixture
def downloads(root, monkeypatch):
    _lock_with_gpu_complements(root, monkeypatch)
    downloaded: list[str] = []

    def fake_download(entry, target, *, offline=False):
        downloaded.append(entry["url"].rsplit("/", 1)[-1])
        return {**entry, "path": str(target.relative_to(root)), "cached": True}

    monkeypatch.setattr(artifacts, "download", fake_download)
    return downloaded


@pytest.mark.parametrize(("signals", "skip", "expected"), [
    ({"platform": "linux-aarch64", "l4t_major": 35}, frozenset(),
     ["ollama-linux-arm64.tar.zst", "ollama-linux-arm64-jetpack5.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": 36}, frozenset(),
     ["ollama-linux-arm64.tar.zst", "ollama-linux-arm64-jetpack6.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": 38}, frozenset(), ["ollama-linux-arm64.tar.zst"]),
    ({"platform": "linux-aarch64", "l4t_major": None}, frozenset(), ["ollama-linux-arm64.tar.zst"]),
    # Profil en calcul CPU : le complément est sauté.
    ({"platform": "linux-aarch64", "l4t_major": 35}, frozenset({"ollama-gpu"}), ["ollama-linux-arm64.tar.zst"]),
    ({"platform": "windows-x86_64", "l4t_major": None}, frozenset(), ["ollama-windows-amd64.zip"]),
])
def test_provision_takes_the_complement_of_this_host_only(downloads, signals, skip, expected):
    manifest = artifacts.provision_artifacts(skip_groups=skip, signals=signals)
    assert downloads == expected
    assert [record["url"].rsplit("/", 1)[-1] for records in manifest.values() for record in records] == expected


@pytest.mark.parametrize(("signals", "host"), [
    ({"platform": "linux-x86_64", "l4t_major": None}, "linux-x86_64, hors Jetson"),
    ({"platform": "linux-aarch64", "l4t_major": 38}, "linux-aarch64, Jetson Linux R38"),
    ({"platform": "windows-x86_64", "l4t_major": None}, "windows-x86_64, hors Jetson"),
])
def test_only_the_gpu_complement_without_entry_for_this_host_downloads_nothing(root, downloads, capsys, signals, host):
    assert artifacts.provision_artifacts("ollama-gpu", signals=signals) == {}
    assert downloads == [] and not (root / ".runtime/manifests/artifacts.json").exists()
    assert capsys.readouterr().out == (f"Aucun complément GPU d'Ollama ne correspond à ce poste ({host}) : "
                                       "rien à télécharger.\n")


def test_only_the_gpu_complement_of_a_jetson_downloads_its_own(downloads):
    manifest = artifacts.provision_artifacts("ollama-gpu", signals={"platform": "linux-aarch64", "l4t_major": 36})
    assert downloads == ["ollama-linux-arm64-jetpack6.tar.zst"] and list(manifest) == ["ollama-gpu"]


def test_a_complement_missing_offline_does_not_stop_the_groups_after_it(root, monkeypatch, capsys):
    # Revue J11 runtime-1 : sans --only, le complément GPU est facultatif ; e5, placé
    # après lui dans le verrou réel et déjà en cache, est vérifié et consigné.
    data = b"modele e5 en cache"
    (root / "cache").mkdir()
    (root / "cache/e5.onnx").write_bytes(data)
    lock = {"schema_version": 1, "groups": {
        "ollama-gpu": [{"platform": "linux-aarch64", "host": {"l4t_major": 35}, "variant": "cuda_jetpack5",
                        "url": "https://ici/ollama-linux-arm64-jetpack5.tar.zst", "target": "cache/jp5.tar.zst",
                        "size": 10, "sha256": "3" * 64}],
        "e5": [{"url": "https://ici/e5.onnx", "target": "cache/e5.onnx", "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}]}}
    (root / "config").mkdir()
    (root / "config/artifacts.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(artifacts, "ARTIFACT_LOCK", root / "config/artifacts.lock.json")
    monkeypatch.setattr(artifacts, "launcher_command", lambda command: f"./rag.sh {command}")
    jetson = {"platform": "linux-aarch64", "l4t_major": 35, "jetpack": "jetpack5"}
    manifest = artifacts.provision_artifacts(offline=True, signals=jetson)
    assert list(manifest) == ["e5"] and manifest["e5"][0]["cached"] is True
    assert capsys.readouterr().out == (
        "Accélération GPU : complément jp5.tar.zst absent ou corrompu dans le cache hors ligne. Le provisionnement "
        "continue sans lui : la génération restera sur CPU. Pour l'ajouter ensuite : ./rag.sh provision --only "
        "ollama-gpu, avec un accès réseau.\n")
    # Demande explicite du complément : son absence reste une erreur.
    with pytest.raises(FileNotFoundError, match="Artefact offline absent ou corrompu : jp5.tar.zst"):
        artifacts.provision_artifacts("ollama-gpu", offline=True, signals=jetson)


def test_extraction_fingerprint_ignores_the_gpu_group_and_the_llm_section(tmp_path):
    # Méthode C5 de la conception J11, devenue test (W025 P8) : l'empreinte d'extraction (gel W022) ne lit ni la
    # section llm du profil ni les entrées du verrou hors modèles Docling et tessdata ; contrôle positif sur la section pdf.
    import yaml

    from services.ingestion import extraction_fingerprint
    from services.runtime.platforms import native_executable

    profile = yaml.safe_load((REPOSITORY / "config/local16.yaml").read_text(encoding="utf-8"))
    lock = _repository_lock()
    assert "ollama-gpu" in lock["groups"]
    without_gpu = {**lock, "groups": {name: entries for name, entries in lock["groups"].items() if name != "ollama-gpu"}}
    lock_path = tmp_path / "artifacts.lock.json"

    def fingerprint(changed_profile: dict, changed_lock: dict) -> str:
        lock_path.write_text(json.dumps(changed_lock), encoding="utf-8")
        # Même profil que celui du worker (services/api/jobs.worker_profile), verrou lu à un chemin fixe.
        pdf = {**changed_profile["pdf"], "tesseract_cmd": native_executable(changed_profile["pdf"]["tesseract_cmd"]),
               "artifacts_lock_path": str(lock_path)}
        return extraction_fingerprint({**changed_profile, "pdf": pdf})

    def with_llm(**changes) -> dict:
        llm = {key: value for key, value in profile["llm"].items() if key not in ("num_gpu", "accelerator")}
        return {**profile, "llm": {**llm, **changes}}

    reference = fingerprint(profile, lock)
    assert fingerprint(profile, without_gpu) == reference
    for llm in ({"num_gpu": 0}, {"accelerator": "auto"}, {"accelerator": "cpu"}, {"accelerator": "gpu"}, {}):
        assert fingerprint(with_llm(**llm), lock) == reference
        assert fingerprint(with_llm(**llm), without_gpu) == reference
    # Contrôles positifs : la section pdf et une entrée de modèle Docling du verrou entrent bien dans l'empreinte.
    assert fingerprint({**profile, "pdf": {**profile["pdf"], "max_file_mib": 199}}, lock) != reference
    docling = [{**entry, "sha256": "0" * 64} if "sha256" in entry else entry for entry in lock["groups"]["docling"]]
    assert fingerprint(profile, {**lock, "groups": {**lock["groups"], "docling": docling}}) != reference
