"""Profil par utilisateur (DIST-02) : données, stockage Qdrant et écritures d'exécution hors du programme, ports libres."""
import socket

import pytest
import yaml

from services.runtime.artifacts import ROOT, runtime_location
from services.runtime.profile_setup import user_profile, write_user_profile
from services.runtime.supervisor import data_path, load_profile

BASE = ROOT / "config/local16.yaml"


def free_ports(count):
    sockets = [socket.socket() for _ in range(count)]
    try:
        for probe in sockets:
            probe.bind(("127.0.0.1", 0))
        return [probe.getsockname()[1] for probe in sockets]
    finally:
        for probe in sockets:
            probe.close()


def ports():
    return dict(zip(("app", "qdrant", "ollama"), free_ports(3), strict=True))


def test_generated_profile_places_data_and_runtime_writes_under_the_user_root(tmp_path):
    root, program = tmp_path / "utilisateur", tmp_path / "programme"
    chosen = ports()
    result = write_user_profile(BASE, root, ports=chosen, program_root=program, storage_max=1000)
    profile = load_profile(root / "profile.yaml")
    assert data_path(profile) == (root / "data").resolve()
    # qdrant_data_path n'est pas appelé ici : sous Windows, le dossier temporaire du test dépasse la borne de 57 caractères.
    assert profile["qdrant"]["storage_dir"] == str((root / "q").resolve())
    assert profile["app"]["port"] == chosen["app"] and profile["qdrant"]["url"].endswith(f":{chosen['qdrant']}")
    assert profile["llm"]["base_url"] == f"http://127.0.0.1:{chosen['ollama']}"
    for key in ("host_lock_path", "backups_dir", "restore_storage_dir", "huggingface_cache_dir"):
        assert runtime_location(profile, key).is_relative_to(root.resolve())
    # Tout le reste du profil de référence est repris tel quel.
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    assert profile["retrieval"] == base["retrieval"] and profile["llm"]["model"] == base["llm"]["model"]
    assert result["status"] == "created" and result["next"].endswith('profile.yaml"')
    with pytest.raises(ValueError, match="jamais remplacé"):
        write_user_profile(BASE, root, ports=chosen, program_root=program, storage_max=1000)


def test_restore_stores_sit_beside_the_short_storage_and_init_refuses_them_when_too_long(tmp_path, monkeypatch):
    # Essai du 01/10 : sous une racine de données de 43 caractères, « <racine>\r\<id8>\storage » dépassait la borne de 57.
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    root = tmp_path / "utilisateur"
    profile = user_profile(base, root, qdrant_storage=tmp_path / "court" / "q", ports=ports(), program_root=tmp_path / "programme", storage_max=1000)
    assert profile["runtime"]["restore_storage_dir"] == str((tmp_path / "court" / "qr").resolve())
    monkeypatch.setattr("services.runtime.profile_setup.os.name", "nt")
    storage = (root / "q").resolve()
    main, restores = len(str(storage / "storage")), len(str(storage.with_name("qr") / ("0" * 8) / "storage"))
    assert restores > main
    with pytest.raises(ValueError, match=r"Stockages de restauration trop longs .* --qdrant-storage, par exemple .*apdfq"):
        write_user_profile(BASE, root, ports=ports(), program_root=tmp_path / "programme", storage_max=main)
    assert not (root / "profile.yaml").exists()


def test_profile_refuses_a_root_inside_the_program_a_long_qdrant_path_and_busy_or_equal_ports(tmp_path, monkeypatch):
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="hors du dossier du programme"):
        user_profile(base, tmp_path / "programme" / "donnees", ports=ports(), program_root=tmp_path / "programme", storage_max=1000)
    monkeypatch.setattr("services.runtime.profile_setup.os.name", "nt")
    with pytest.raises(ValueError, match="Stockage Qdrant trop long"):
        user_profile(base, tmp_path / ("u" * 80), ports=ports(), program_root=tmp_path / "programme")
    chosen = ports()
    chosen["qdrant"] = chosen["app"]
    with pytest.raises(ValueError, match="distincts"):
        user_profile(base, tmp_path / "u", ports=chosen, program_root=tmp_path / "programme", storage_max=1000)
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        busy = {**ports(), "app": held.getsockname()[1]}
        with pytest.raises(ValueError, match="Port déjà occupé"):
            user_profile(base, tmp_path / "u", ports=busy, program_root=tmp_path / "programme", storage_max=1000)
