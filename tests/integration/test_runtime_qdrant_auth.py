"""Clé d'API du Qdrant 1.19.1 verrouillé, vérifiée sur le vrai binaire de la plateforme (D08.3).

Windows : binaire msvc sous Job Object, arrêt par CTRL+C console. Linux (aarch64, x86-64) : binaire musl sous PosixJob,
arrêt par SIGTERM au groupe, qui déclenche l'arrêt « graceful » de Qdrant. Le test est ignoré si le binaire de la
plateforme n'est pas provisionné.
"""

import json
import shutil
import socket
import sys
import time
import uuid

import httpx
import pytest
import yaml

from services.runtime.artifacts import ROOT
from services.runtime.supervisor import (
    ProcessJob,
    acquire_qdrant_lock,
    environment,
    issue_qdrant_key,
    native_paths,
    qdrant_environment,
    send_owned_console_interrupt,
    wait_http,
    write_qdrant_config,
)

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="Binaire Qdrant natif Windows ou Linux")]


@pytest.fixture
def owned_qdrant_dir():
    # Chemin court imposé par le binaire Windows : seul le dossier créé par ce test est retiré.
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


def test_locked_qdrant_refuses_requests_without_the_instance_key(tmp_path, owned_qdrant_dir):
    try:
        binary = native_paths(("qdrant",))["qdrant"]
    except FileNotFoundError:
        pytest.skip("Binaire Qdrant non provisionné")
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    profile["qdrant"]["url"] = url
    profile["qdrant"]["storage_dir"] = str(owned_qdrant_dir)
    control = tmp_path / "control"
    control.mkdir()
    config = write_qdrant_config(profile, tmp_path, control)
    key = issue_qdrant_key(control)
    results = {}
    with acquire_qdrant_lock(owned_qdrant_dir), ProcessJob() as job:
        child = job.launch([str(binary), "--config-path", str(config), "--disable-telemetry"], cwd=ROOT,
                           env=qdrant_environment(environment(profile, tmp_path, ROOT / "config/local16.yaml"), key),
                           log_path=tmp_path / "qdrant.log")
        try:
            wait_http(url + "/healthz", child)
            with httpx.Client(base_url=url, timeout=10, trust_env=False) as client:
                cases = {
                    "healthz_without_key": client.get("/healthz"),
                    "healthz_with_key": client.get("/healthz", headers={"api-key": key}),
                    "collections_without_key": client.get("/collections"),
                    # Rebinding DNS : une page d'un domaine étranger atteint le port loopback sans connaître la clé.
                    "collections_foreign_host_origin": client.get("/collections", headers={
                        "Host": "attaquant.example:6333", "Origin": "http://attaquant.example"}),
                    "collections_wrong_key": client.get("/collections", headers={"api-key": "x" * 43}),
                    "telemetry_without_key": client.get("/telemetry"),
                    "collections_with_key": client.get("/collections", headers={"api-key": key}),
                    "collections_bearer_key": client.get("/collections", headers={"Authorization": "Bearer " + key}),
                }
            results = {name: response.status_code for name, response in cases.items()}
        finally:
            # L'arrêt n'est pas l'objet du test : à défaut d'arrêt console, la fermeture du Job termine l'enfant.
            sent = send_owned_console_interrupt(child, "qdrant")
            try:
                results["stop"] = {"console_interrupt": sent, "exit_code": child.wait(15)}
            except TimeoutError:
                results["stop"] = {"console_interrupt": sent, "mode": "forced_job_close"}
    if sys.platform != "win32":
        from services.runtime.posix_process import group_members

        # SIGTERM au groupe : Qdrant s'arrête de lui-même ; après fermeture du Job, rien ne reste de son groupe.
        results["stop"]["group_members_after_close"] = group_members(child.pgid)
        results["stop"]["shutdown_log"] = [line[-120:] for line in (tmp_path / "qdrant.log").read_text(
            encoding="utf-8", errors="replace").splitlines() if "shutdown" in line.lower()]
    (tmp_path / "qdrant-auth-proof.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    assert results["healthz_without_key"] == 200 and results["healthz_with_key"] == 200
    assert results["collections_without_key"] == 401
    assert results["collections_foreign_host_origin"] == 401
    assert results["collections_wrong_key"] in {401, 403}
    assert results["telemetry_without_key"] == 401
    assert results["collections_with_key"] == 200 and results["collections_bearer_key"] == 200
    assert key not in (tmp_path / "qdrant.log").read_text(encoding="utf-8", errors="replace")
    if sys.platform != "win32":
        # Arrêt coopératif réel sous Linux : SIGTERM au groupe, arrêt « graceful » du serveur HTTP de Qdrant (actix ;
        # SIGINT y déclenche l'arrêt « forced »), code 0, aucun processus restant.
        assert results["stop"]["console_interrupt"] is True and results["stop"].get("exit_code") == 0, results["stop"]
        assert any("SIGTERM received; starting graceful shutdown" in line for line in results["stop"]["shutdown_log"]), results["stop"]
        assert results["stop"]["group_members_after_close"] == []
