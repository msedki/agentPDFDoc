"""Téléchargements explicites et vérifiés ; jamais appelé au démarrage nominal."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import stat
import tarfile
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .accelerator import GPU_GROUP, entries_for_host, host_signals, no_complement_message
from .platforms import entries_for_platform, launcher_command

ROOT = Path(__file__).resolve().parents[2]
# Sources Leptonica et Tesseract (Linux) : téléchargées, vérifiées (empreinte d'archive, ou empreinte de contenu pour une
# archive de tag régénérée par GitHub) et consignées par provisioning.build_tesseract, jamais par provision_artifacts.
TESSERACT_SOURCE_GROUP = "tesseract-source"
# Fenêtre zstd maximale acceptée (128 Mio, limite par défaut de zstd sans --long) : la mémoire de décompression reste
# bornée ; l'archive Ollama 0.35.0 linux-arm64 annonce 8 Mio.
ZSTD_MAX_WINDOW = 1 << 27
ARTIFACT_LOCK = ROOT / "config" / "artifacts.lock.json"
# Écritures d'exécution que le profil peut sortir du dossier programme (installation par utilisateur, DIST-02) ;
# sans valeur, l'emplacement historique sous le dépôt est gardé.
RUNTIME_LOCATIONS = {"host_lock_path": ".runtime/control/host-heavy.lock", "backups_dir": "backups",
                     "restore_storage_dir": ".runtime/q", "huggingface_cache_dir": ".runtime/cache/huggingface"}


def runtime_location(profile: dict | None, key: str) -> Path:
    """Emplacement d'exécution de la section `runtime` du profil ; un chemin relatif part de la racine du programme."""
    value = ((profile or {}).get("runtime") or {}).get(key)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"runtime.{key} : chemin non vide attendu")
    return (ROOT / (value or RUNTIME_LOCATIONS[key])).resolve()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Sur NTFS, un lecteur sans FILE_SHARE_DELETE peut empêcher temporairement
    # le remplacement. Chaque écrivain garde son temporaire propre ; seuls
    # les refus transitoires sont repris, dans une fenêtre bornée.
    deadline = time.monotonic() + 5
    while True:
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def read_json_atomic(path: Path) -> Any:
    """Lire une publication complète, avec reprise bornée des conflits NTFS."""
    deadline = time.monotonic() + 5
    while True:
        try:
            with path.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def download(entry: dict[str, Any], target: Path, *, offline: bool = False) -> dict[str, Any]:
    """SHA-256 éditeur ou SHA-1 blob Git du commit officiel obligatoire."""
    expected = entry.get("sha256")
    git_blob = entry.get("git_blob_sha1")
    if not expected and not git_blob:
        raise ValueError("Empreinte attendue absente du verrou de téléchargement")

    def verified(path: Path) -> bool:
        if not path.is_file():
            return False
        if entry.get("size") and path.stat().st_size != entry["size"]:
            return False
        if expected:
            return file_hash(path) == expected
        digest = hashlib.sha1(usedforsecurity=False)
        digest.update(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest() == git_blob

    if verified(target):
        return {**entry, "sha256": file_hash(target), "path": str(target.relative_to(ROOT)), "cached": True}
    if offline:
        raise FileNotFoundError(f"Artefact offline absent ou corrompu : {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    size = int(entry.get("size", 0))
    if shutil.disk_usage(target.parent).free < size + 2 * 1024**3:
        raise RuntimeError(f"Espace disque insuffisant pour {target.name}, réserve disque 2 Gio")
    part = target.with_name(target.name + ".part")
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "agentragpdf-provision/0.1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response, part.open("wb") as output:
                copied = 0
                notified = 0
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(block)
                    copied += len(block)
                    if copied - notified >= 64 * 1024**2:
                        print(f"{target.name} : {copied / 1024**2:.0f} Mio téléchargés", flush=True)
                        notified = copied
                output.flush()
                os.fsync(output.fileno())
            if not verified(part):
                raise ValueError(f"Empreinte non conforme : {target.name}")
            part.replace(target)
            print(f"Vérifié : {target.name} ({target.stat().st_size} octets)", flush=True)
            return {**entry, "sha256": file_hash(target), "path": str(target.relative_to(ROOT)), "cached": False}
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise
            print(f"Téléchargement {target.name}, essai {attempt + 1} interrompu : {type(exc).__name__}", flush=True)
            time.sleep(1)
    raise AssertionError("Téléchargement sans résultat")


def extract_verified_zip(archive_path: Path, destination: Path) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Chemin hors racine dans archive")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Lien symbolique interdit dans archive de runtime")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            files.append({"path": str(target.relative_to(ROOT)), "sha256": file_hash(target), "size": entry.file_size})
    return files


def _checked_member(member: tarfile.TarInfo, destination: Path) -> tarfile.TarInfo:
    """Membre accepté par le filtre `data` de tarfile, après refus explicite des chemins absolus et des `..`.

    Le filtre `data` retire seulement la barre initiale d'un chemin absolu : il est refusé ici avant lui. Le filtre
    refuse ensuite toute sortie de la destination (y compris par un lien déjà extrait), les liens absolus ou
    sortants, les périphériques et tubes, et retire les bits setuid, setgid et d'écriture de groupe.
    """
    name = PurePosixPath(member.name)
    if name.is_absolute() or member.name.startswith(("/", "\\")) or ".." in name.parts:
        raise ValueError(f"Chemin absolu ou remontant refusé dans l'archive : {member.name}")
    try:
        return tarfile.data_filter(member, str(destination))
    except tarfile.FilterError as exc:
        raise ValueError(f"Membre refusé dans l'archive ({type(exc).__name__}) : {member.name}") from None


def _refuse_write_through_link(root: Path, name: PurePosixPath, *, replaces_final: bool) -> None:
    """Refuse un membre dont le chemin traverse un lien symbolique déjà présent sous la destination.

    tarfile ouvre un fichier régulier en écriture sans retirer un lien existant : la cible serait écrasée et le
    manifeste ne décrirait plus le disque. Un lien symbolique remplace le dernier élément (tarfile le retire avant
    de le recréer) : seul son dossier parent est alors contrôlé.
    """
    parts = name.parts if not replaces_final else name.parts[:-1]
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Écriture à travers un lien refusée dans l'archive : {name}")


def extract_verified_tar(archive_path: Path, destination: Path) -> dict[str, list[dict[str, Any]]]:
    """Extraction en flux d'une archive .tar.gz ou .tar.zst ; SHA-256 de chaque fichier extrait.

    zstd : `read_across_frames=True` lit l'archive multi-trame (celle d'Ollama) d'un seul tenant. Par défaut,
    python-zstandard arrête chaque lecture à la fin d'une trame, et un lecteur qui prendrait cette lecture courte pour
    la fin de l'archive la tronquerait sans erreur. Les liens symboliques internes sont consignés à part, avec leur
    cible. Chaque nom de membre n'est admis qu'une fois et aucun membre n'est écrit à travers un lien : l'empreinte
    relevée à l'extraction reste celle du fichier sur disque.
    """
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    files: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    seen: set[PurePosixPath] = set()
    with archive_path.open("rb") as raw:
        if archive_path.name.endswith(".tar.zst"):
            import zstandard

            reader: Any = zstandard.ZstdDecompressor(max_window_size=ZSTD_MAX_WINDOW).stream_reader(
                raw, read_across_frames=True, closefd=False)
        elif archive_path.name.endswith((".tar.gz", ".tgz")):
            reader = gzip.GzipFile(fileobj=raw, mode="rb")
        else:
            raise ValueError(f"Format d'archive non pris en charge : {archive_path.name}")
        with reader, tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                accepted = _checked_member(member, root)
                # Nom normalisé (« ./a » et « a », « lib/ » et « lib ») : un second membre du même nom réécrirait le premier.
                name = PurePosixPath(accepted.name)
                if name in seen:
                    raise ValueError(f"Membre déjà présent dans l'archive : {member.name}")
                seen.add(name)
                _refuse_write_through_link(root, name, replaces_final=accepted.issym())
                archive.extract(member, root, filter="data")
                # Chemin consigné sous la racine du programme, sans résoudre les liens de l'installation (.runtime
                # peut désigner un autre volume) ; native_paths résout les deux côtés avant de comparer.
                recorded = str((destination / accepted.name).relative_to(ROOT))
                if accepted.isreg() or accepted.islnk():
                    extracted = root / accepted.name
                    files.append({"path": recorded, "sha256": file_hash(extracted), "size": extracted.stat().st_size})
                elif accepted.issym():
                    links.append({"path": recorded, "target": accepted.linkname})
            # Après la fin de l'archive tar, seul du remplissage nul est admis : d'autres octets échapperaient au contrôle.
            for block in iter(lambda: reader.read(1024 * 1024), b""):
                if block.strip(b"\0"):
                    raise ValueError(f"Données après la fin de l'archive tar : {archive_path.name}")
    return {"files": files, "links": links}


def extract_verified_archive(archive_path: Path, destination: Path) -> dict[str, list[dict[str, Any]]]:
    if archive_path.suffix == ".zip":
        return {"files": extract_verified_zip(archive_path, destination), "links": []}
    return extract_verified_tar(archive_path, destination)


def _complement_unavailable(name: str, exc: Exception, *, offline: bool, extracted: bool) -> str:
    """Complément GPU facultatif non obtenu : cause, effet sur la génération, commande pour l'ajouter."""
    if offline and isinstance(exc, FileNotFoundError):
        cause = f"complément {name} absent ou corrompu dans le cache hors ligne"
    elif offline:
        cause = f"complément {name} refusé, {type(exc).__name__} : {exc}"
    else:
        cause = f"téléchargement du complément {name} en échec, {type(exc).__name__} : {exc}"
    if extracted:
        return (f"Accélération GPU : {cause}. Le provisionnement continue ; les bibliothèques déjà extraites de ce "
                "complément restent en place.")
    return (f"Accélération GPU : {cause}. Le provisionnement continue sans lui : la génération restera sur CPU. Pour "
            f"l'ajouter ensuite : {launcher_command('provision --only ' + GPU_GROUP)}"
            + (", avec un accès réseau." if offline else "."))


def provision_artifacts(only: str | None = None, *, offline: bool = False, skip_groups: frozenset[str] = frozenset(),
                        signals: dict[str, Any] | None = None,
                        tokenizer_model_id: str = "Qwen/Qwen3.5-2B") -> dict[str, Any]:
    """Télécharge, vérifie et extrait les entrées du verrou valables sur ce poste, puis les consigne au manifeste local.

    `skip_groups` écarte des groupes (complément GPU d'un profil en calcul CPU) ; `signals` (host_signals) choisit,
    parmi les entrées de la plateforme, celles dont le champ `host` correspond au poste (complément JetPack). Sans
    `--only ollama-gpu`, le complément GPU est facultatif (le CPU reste le socle, W024) : absent du cache hors ligne ou
    en échec de téléchargement, il est signalé et le provisionnement continue avec les groupes suivants.
    """
    lock = json.loads(ARTIFACT_LOCK.read_text(encoding="utf-8"))
    manifest_path = ROOT / ".runtime" / "manifests" / "artifacts.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if only == GPU_GROUP and not entries_for_host(lock["groups"].get(GPU_GROUP, []), signals):
        # Demande explicite sans objet ici (poste hors Jetson R35 ou R36) : rien à télécharger, ce n'est pas un échec.
        print(no_complement_message(signals if signals is not None else host_signals()), flush=True)
        return manifest
    for name, entries in lock["groups"].items():
        if (only and name != only) or name in skip_groups:
            continue
        if name == TESSERACT_SOURCE_GROUP:
            # Un contrôle strict ici refuserait, avant build_tesseract, une archive régénérée de contenu conforme.
            if only and entries_for_platform(entries):
                raise ValueError(f"Le groupe {name} est téléchargé, vérifié et consigné par la construction de Tesseract : "
                                 f"exécuter {launcher_command('provision')} sans --only")
            continue
        if name == "qwen-tokenizer":
            entries = [entry for entry in entries if entry.get("model_id") == tokenizer_model_id]
            if not entries:
                raise ValueError("Tokenizer du modèle choisi absent du verrou : " + tokenizer_model_id)
            # Préserver les manifestes des autres modèles déjà provisionnés, sans les télécharger ni les ouvrir.
            records = [record for record in manifest.get(name, []) if record.get("model_id") != tokenizer_model_id]
        else:
            records = []
        optional = name == GPU_GROUP and only != GPU_GROUP
        # Seules les entrées de ce poste (sans champ platform, ou avec le sien, puis champ host éventuel) sont téléchargées.
        for entry in entries_for_host(entries, signals):
            target = ROOT / entry["target"]
            try:
                record = download(entry, target, offline=offline)
            except (OSError, ValueError, RuntimeError) as exc:
                if not optional:
                    raise
                # Le manifeste garde l'extraction précédente de ce complément, s'il y en a une.
                kept = any(item.get("url") == entry["url"] for item in manifest.get(name, []))
                print(_complement_unavailable(target.name, exc, offline=offline, extracted=kept), flush=True)
                break
            if entry.get("extract_to"):
                extracted = extract_verified_archive(target, ROOT / entry["extract_to"])
                record["extracted_files"] = extracted["files"]
                if extracted["links"]:
                    record["extracted_links"] = extracted["links"]
            records.append(record)
            manifest[name] = records
            write_json_atomic(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    provision_artifacts(args.only, offline=args.offline)
