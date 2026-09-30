"""Profil production (W011) servi par uvicorn en HTTPS réel : cookies Secure/__Host-, HSTS, refus du HTTP clair."""
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from test_api_http import FakeEmbedding, FakeGovernor, FakeOllama, FakeTokenizer, FakeVectors

from services.api.main import create_app
from services.api.settings import Settings

CONTROL = "test-only-nonce"
GIT_OPENSSL = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/usr/bin/openssl.exe",
               Path(os.environ.get("ProgramFiles", "")) / "Git/usr/bin/openssl.exe"]


def openssl() -> str | None:
    return shutil.which("openssl") or next((str(path) for path in GIT_OPENSSL if path.is_file()), None)


pytestmark = [pytest.mark.integration, pytest.mark.skipif(openssl() is None, reason="OpenSSL absent : certificat de test impossible")]


@pytest.fixture
def certificate(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([openssl(), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                   check=True, capture_output=True, timeout=60)
    return cert, key


def test_production_profile_serves_https_with_secure_host_cookies(tmp_path, certificate, monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    cert, key = certificate
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": port},
                                   "security": {"environment": "production", "tls_cert_file": str(cert), "tls_key_file": str(key)}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(),
                     ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                           ssl_certfile=str(cert), ssl_keyfile=str(key)))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    origin = f"https://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        with httpx.Client(base_url=origin, verify=str(cert), trust_env=False) as client:
            health = client.get("/api/v1/health")
            assert health.status_code == 200 and health.headers["Strict-Transport-Security"] == "max-age=31536000"
            link = client.post("/api/v1/admin/session-links", headers={"X-RAG-Control-Token": CONTROL}).json()["path"]
            opened = client.get(link, follow_redirects=False)
            cookies = [header.lower() for header in opened.headers.get_list("set-cookie")]
            assert len(cookies) == 2 and all(header.startswith("__host-rag_") and "secure" in header for header in cookies)
            # Le client HTTPS renvoie les cookies Secure : la session ouverte donne accès à l'API.
            assert client.get("/api/v1/library/tree").status_code == 200
            assert client.get("/api/docs").status_code == 404
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=5, trust_env=False)
    finally:
        server.should_exit = True
        thread.join(timeout=30)
