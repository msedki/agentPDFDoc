"""Profil production (W011) servi par uvicorn en HTTPS réel : cookies Secure/__Host-, HSTS, refus du HTTP clair."""
import asyncio
import os
import shutil
import socket
import ssl
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from test_api_http import FakeEmbedding, FakeGovernor, FakeOllama, FakeTokenizer, FakeVectors

from services.api import comparison
from services.api.errors import ApiError
from services.api.main import create_app
from services.api.settings import Settings

CONTROL = "test-only-nonce"
GIT_OPENSSL = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/usr/bin/openssl.exe",
               Path(os.environ.get("ProgramFiles", "")) / "Git/usr/bin/openssl.exe"]


def openssl() -> str | None:
    return shutil.which("openssl") or next((str(path) for path in GIT_OPENSSL if path.is_file()), None)


pytestmark = [pytest.mark.integration, pytest.mark.skipif(openssl() is None, reason="OpenSSL absent : certificat de test impossible")]


def issue_certificate(cert: Path, key: Path) -> tuple[Path, Path]:
    """Certificat autosigné de test pour 127.0.0.1, régénéré à chaque appel (clé distincte)."""
    subprocess.run([openssl(), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                   check=True, capture_output=True, timeout=60)
    return cert, key


@pytest.fixture
def certificate(tmp_path):
    return issue_certificate(tmp_path / "cert.pem", tmp_path / "key.pem")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def https_api(tmp_path, cert, key, port):
    """API réelle du profil production servie par uvicorn en HTTPS sur 127.0.0.1:port, arrêtée en sortie."""
    settings = Settings(tmp_path, {"app": {"data_dir": "runtime", "port": port},
                                   "security": {"environment": "production", "tls_cert_file": str(cert), "tls_key_file": str(key)}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(),
                     ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                           ssl_certfile=str(cert), ssl_keyfile=str(key)))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        yield f"https://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=30)


def test_production_profile_serves_https_with_secure_host_cookies(tmp_path, certificate, monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    cert, key = certificate
    port = free_port()
    with https_api(tmp_path, cert, key, port) as origin:
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


def test_comparison_quiet_check_refuses_a_running_api_whose_certificate_is_not_the_profile_one(tmp_path, certificate, monkeypatch):
    """Revue A1 (C16) : API réelle en HTTPS, profil du comparatif pointant vers un autre certificat.

    L'échec de vérification TLS n'est pas un refus de connexion : le comparatif s'arrête avec une erreur explicite au lieu
    de démarrer à côté d'une API en marche. Seul le port fermé après l'arrêt de l'API est tenu pour « API arrêtée ».
    """
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    cert, key = certificate
    other_cert, other_key = issue_certificate(tmp_path / "other-cert.pem", tmp_path / "other-key.pem")
    port, llm_port = free_port(), free_port()

    def comparison_settings(served_certificate, served_key):
        # Ollama sondé sur un port fermé : seul le contrôle de l'API est exercé.
        return Settings(tmp_path / "comparison", {"app": {"port": port}, "llm": {"base_url": f"http://127.0.0.1:{llm_port}"},
                                                  "security": {"environment": "production", "tls_cert_file": str(served_certificate),
                                                               "tls_key_file": str(served_key)}})

    mismatched, matching = comparison_settings(other_cert, other_key), comparison_settings(cert, key)
    with https_api(tmp_path, cert, key, port):
        with pytest.raises(ApiError) as refused:
            asyncio.run(comparison.assert_quiet(mismatched))
        assert refused.value.code == "comparison_api_tls_unverified" and refused.value.status == 409
        with pytest.raises(ApiError) as running:
            asyncio.run(comparison.assert_quiet(matching))
        assert running.value.code == "comparison_requires_stopped_api"
    # API arrêtée : connexion refusée sur son port, le contrôle laisse passer quel que soit le certificat du profil.
    asyncio.run(comparison.assert_quiet(mismatched))


def exception_chain(error: BaseException | None) -> list[BaseException]:
    links: list[BaseException] = []
    while error is not None and all(error is not link for link in links):
        links.append(error)
        error = error.__cause__ or error.__context__
    return links


def test_comparison_quiet_check_reports_a_silent_listener_as_unverified_not_as_a_tls_failure(tmp_path, certificate):
    """Revue J5 : un service accepte la connexion TCP sans jamais répondre (socket en écoute, aucun accept).

    La négociation TLS expire (chaîne réelle httpx.ConnectTimeout -> ... -> ssl.SSLWantReadError) : ce n'est pas un
    échec de vérification du certificat. Le comparatif s'arrête avec `comparison_api_unverified`, sans inviter à
    corriger le certificat du profil.
    """
    cert, key = certificate
    llm_port = free_port()
    with socket.socket() as silent:
        silent.bind(("127.0.0.1", 0))
        silent.listen()
        port = silent.getsockname()[1]
        settings = Settings(tmp_path / "comparison", {"app": {"port": port}, "llm": {"base_url": f"http://127.0.0.1:{llm_port}"},
                                                      "security": {"environment": "production", "tls_cert_file": str(cert),
                                                                   "tls_key_file": str(key)}})
        with pytest.raises(ApiError) as refused:
            asyncio.run(comparison.assert_quiet(settings))
    assert (refused.value.code, refused.value.status) == ("comparison_api_unverified", 409)
    assert "sans répondre" in refused.value.message and "certificat" not in refused.value.message
    # Le cas réel de la revue est bien exercé : délai dépassé pendant la négociation TLS, sans refus de certificat.
    assert isinstance(refused.value.__cause__, httpx.TimeoutException)
    links = exception_chain(refused.value.__cause__)
    assert any(isinstance(link, ssl.SSLWantReadError) for link in links)
    assert not any(isinstance(link, ssl.SSLCertVerificationError) for link in links)


@contextmanager
def closing_listener():
    """Service réel qui accepte chaque connexion TCP puis ferme son sens d'émission sans un octet TLS.

    `shutdown(SHUT_WR)` envoie la fin de flux aussitôt après `accept` ; le service lit ensuite ce que le client envoie
    jusqu'à sa fermeture, pour qu'aucune réinitialisation (RST) ne remplace la fin de flux attendue par le client.
    """
    stop = threading.Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.1)

    def serve():
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                connection.shutdown(socket.SHUT_WR)
                connection.settimeout(5)
                try:
                    while connection.recv(4096):
                        pass
                except OSError:
                    pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        stop.set()
        thread.join(timeout=10)
        listener.close()


def test_comparison_quiet_check_reports_a_stream_closed_before_tls_as_unverified_not_as_a_tls_failure(tmp_path, certificate):
    """Ronde 4 : un service accepte la connexion puis ferme le flux avant toute négociation TLS.

    Chaîne réelle httpx.ConnectError -> ... -> ssl.SSLEOFError : aucun certificat n'a été présenté ni vérifié. Le
    comparatif s'arrête avec `comparison_api_unverified` (service non identifié), sans inviter à corriger le certificat.
    """
    cert, key = certificate
    llm_port = free_port()
    with closing_listener() as port:
        settings = Settings(tmp_path / "comparison", {"app": {"port": port}, "llm": {"base_url": f"http://127.0.0.1:{llm_port}"},
                                                      "security": {"environment": "production", "tls_cert_file": str(cert),
                                                                   "tls_key_file": str(key)}})
        with pytest.raises(ApiError) as refused:
            asyncio.run(comparison.assert_quiet(settings))
    assert (refused.value.code, refused.value.status) == ("comparison_api_unverified", 409)
    assert "sans répondre" in refused.value.message and "certificat" not in refused.value.message
    # Le cas visé est bien exercé : fin de flux pendant la négociation TLS, sans délai dépassé ni refus de certificat.
    assert isinstance(refused.value.__cause__, httpx.ConnectError)
    links = exception_chain(refused.value.__cause__)
    assert any(isinstance(link, ssl.SSLEOFError) for link in links)
    assert not any(isinstance(link, ssl.SSLCertVerificationError) for link in links)
