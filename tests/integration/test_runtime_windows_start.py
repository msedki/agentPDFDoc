import json
import shutil
import socket
import sys
import time
import uuid

import pytest
import yaml

from services.runtime.artifacts import ROOT
from services.runtime.supervisor import acquire_qdrant_lock, process_identity_valid, read_state, start

# Superviseur détaché réel : Job Object et msvcrt sous Windows, groupe POSIX et flock sous Linux (W018).
pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="Superviseur natif Windows ou Linux")]


@pytest.fixture
def owned_qdrant_dir():
    # Chemin Qdrant court imposé hors tmp_path : seul le dossier créé par ce test est retiré.
    path = ROOT / ".runtime/q" / uuid.uuid4().hex[:8]
    assert not path.exists()
    yield path
    deadline = time.monotonic() + 10
    while path.exists():
        try:
            shutil.rmtree(path)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def test_port_collision_fails_without_touching_existing_listener(tmp_path, monkeypatch, owned_qdrant_dir):
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    data = tmp_path / "Données arrêtées"
    profile["app"]["data_dir"] = str(data)
    profile["qdrant"]["storage_dir"] = str(owned_qdrant_dir)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        profile["app"]["port"] = listener.getsockname()[1]
        path = tmp_path / "profil test.yaml"
        path.write_text(yaml.safe_dump(profile), encoding="utf-8")
        before = time.monotonic()
        with pytest.raises(RuntimeError, match="Port .* occupé"):
            start(path)
        elapsed = time.monotonic() - before
        state = read_state(data)
        assert state["status"] == "failed"
        assert state["services"] == {}
        assert elapsed < 15
        with socket.create_connection(listener.getsockname(), timeout=2):
            connection, _ = listener.accept()
            connection.close()
    deadline = time.monotonic() + 5
    while process_identity_valid(state["supervisor"]) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not process_identity_valid(state["supervisor"])
    (tmp_path / "proof.json").write_text(json.dumps({"elapsed_seconds": elapsed,
        "services_started": 0, "existing_listener_survived": True,
        "state": state}, ensure_ascii=False, indent=2), encoding="utf-8")


def test_distinct_data_roots_cannot_share_locked_qdrant(tmp_path, monkeypatch, owned_qdrant_dir):
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    data = tmp_path / "Autre racine sans service"
    qdrant = owned_qdrant_dir
    profile["app"]["data_dir"] = str(data)
    profile["qdrant"]["storage_dir"] = str(qdrant)
    for service, key in (("app", "port"), ("qdrant", "url"), ("llm", "base_url")):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        profile[service][key] = port if service == "app" else f"http://127.0.0.1:{port}"
    path = tmp_path / "profil stockage partagé.yaml"
    path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    with acquire_qdrant_lock(qdrant):
        with pytest.raises(RuntimeError, match="possède déjà ce stockage Qdrant"):
            start(path)
        state = read_state(data)
        assert state["status"] == "failed"
        assert state["services"] == {}
    with acquire_qdrant_lock(qdrant):
        pass
    deadline = time.monotonic() + 5
    while process_identity_valid(state["supervisor"]) and time.monotonic() < deadline:
        time.sleep(0.02)
    (tmp_path / "shared-storage-proof.json").write_text(json.dumps({"state": state,
        "qdrant_lock_reacquired_after_close": True}, ensure_ascii=False, indent=2), encoding="utf-8")
