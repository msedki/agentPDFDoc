"""Ouverture de l'atelier (`open`, W011, W023) : le navigateur reçoit l'URL de boucle locale du profil.

Sous Linux (`webbrowser.open`, xdg-open) comme sous Windows (`os.startfile`), le navigateur par défaut reçoit
`<origine du profil>/api/v1/session/open?link=…`. Le lien à usage unique n'est écrit ni sur disque (rapport, dossier de
l'instance, données de l'API) ni dans un journal ; `--no-browser` l'affiche sans ouvrir de navigateur. La page de
redirection `file://` de la ronde 4 est abandonnée (W023) : la navigation qu'elle déclenche part d'une origine opaque,
porte `Sec-Fetch-Site: cross-site` et l'API la refuse.

L'API est l'application réelle (create_app avec des doubles des services lourds, données temporaires, TestClient) ;
l'instance démarrée et le navigateur sont simulés. Aucun service n'est contacté ; rien n'est écrit hors de tmp_path.
"""

import ipaddress
import json
import logging
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api_storage import FakeEmbedding, FakeLlmTokenizer, FakeVectors

from services.api.main import create_app
from services.api.settings import Settings
from services.runtime import cli

PORT = 8791
ORIGIN = f"http://127.0.0.1:{PORT}"
CONTROL = "jeton-de-controle-de-test"
# En-têtes relevés avec Firefox 136 lors de la revue de la ronde 4 : URL remise directement au navigateur, puis
# navigation déclenchée par une page file:// (origine opaque).
DIRECT_NAVIGATION = {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none",
                     "Sec-Fetch-User": "?1"}
OPAQUE_ORIGIN_NAVIGATION = {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "cross-site"}
OPENED = {"opened_in_browser": True, "expires_in_seconds": 300, "single_use": True}


class SilentOllama:
    """Double : aucune passerelle Ollama n'est contactée."""

    async def close(self):
        pass


class SharedClient:
    """Client HTTP du CLI : le TestClient de l'application, dont le test garde le cycle de vie."""

    def __init__(self, client, options):
        self.client, self.options = client, options

    def __enter__(self):
        return self.client

    def __exit__(self, *exc):
        return False


@contextmanager
def workspace(tmp_path, monkeypatch):
    """Instance démarrée simulée autour de l'API réelle ; rend le TestClient, qui sert aussi de navigateur."""
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)
    monkeypatch.delenv("RAG_DATA_DIR", raising=False)
    data = tmp_path / "données de l'instance"
    (data / "control").mkdir(parents=True)
    (data / "control/admin-token").write_text(CONTROL, encoding="ascii")
    profile = {"app": {"data_dir": str(data), "port": PORT}}
    monkeypatch.setattr(cli, "load_profile", lambda path: profile)
    monkeypatch.setattr(cli, "status", lambda path: {"status": "running"})
    settings = Settings(tmp_path / "api", {"app": {"data_dir": "runtime", "port": PORT}})
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeLlmTokenizer(),
                     ollama=SilentOllama(), governor=types.SimpleNamespace(), start_jobs=False)
    clients: list[SharedClient] = []

    def client_factory(**options):
        clients.append(SharedClient(browser, options))
        return clients[-1]

    with TestClient(app, base_url=ORIGIN) as browser:
        monkeypatch.setattr(httpx, "Client", client_factory)
        yield types.SimpleNamespace(browser=browser, clients=clients)


def run_cli(monkeypatch, *options: str) -> int:
    monkeypatch.setattr(sys, "argv", ["services.runtime.cli", "open", "--profile", "profil.yaml", *options])
    return cli.main()


def link_of(url: str) -> str:
    return parse_qs(urlsplit(url).query)["link"][0]


def assert_loopback_link(url: str) -> str:
    """URL de boucle locale du profil (hôte, port, route) ; rend le lien à usage unique qu'elle porte."""
    parts = urlsplit(url)
    assert parts.hostname is not None and ipaddress.ip_address(parts.hostname).is_loopback
    link = link_of(url)
    assert len(link) >= 32 and url == f"{ORIGIN}/api/v1/session/open?link={link}"
    return link


def files_containing(root: Path, secret: str) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*")
                  if path.is_file() and secret.encode() in path.read_bytes())


def logged(caplog) -> str:
    return "\n".join(record.getMessage() for record in caplog.records)


@pytest.mark.skipif(sys.platform == "win32", reason="ouverture Linux")
def test_linux_opens_the_profile_loopback_url_and_writes_or_logs_the_link_nowhere(tmp_path, monkeypatch, capsys, caplog):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append((url, new)) or True)
    caplog.set_level(logging.DEBUG)
    report = tmp_path / "rapport.json"
    with workspace(tmp_path, monkeypatch) as instance:
        assert run_cli(monkeypatch, "--report", str(report)) == 0
        printed, journal = capsys.readouterr(), logged(caplog)
        # Le navigateur par défaut reçoit l'URL de boucle locale du profil, dans un nouvel onglet ; le lien a été
        # demandé sans mandataire de l'environnement.
        [(url, new)] = opened
        link = assert_loopback_link(url)
        assert new == 2 and [client.options["trust_env"] for client in instance.clients] == [False]
        assert json.loads(printed.out) == OPENED and json.loads(report.read_text(encoding="utf-8")) == OPENED
        assert link not in printed.out + printed.err and link not in journal
        # Navigation directe (Sec-Fetch-Site: none) : session ouverte. Une navigation lancée depuis une origine opaque,
        # comme celle de l'ancienne page file://, est refusée avant la route et ne consomme pas le lien.
        refused = instance.browser.get(url, headers=OPAQUE_ORIGIN_NAVIGATION, follow_redirects=False)
        assert refused.status_code == 403 and refused.json()["code"] == "cross_site_request"
        accepted = instance.browser.get(url, headers=DIRECT_NAVIGATION, follow_redirects=False)
        assert accepted.status_code == 303 and accepted.headers["location"] == "/workspace/"
        session = instance.browser.get("/api/v1/session")
        assert session.status_code == 200 and session.json()["method"] == "session"
        # Usage unique : une seconde présentation renvoie à l'atelier avec le motif du refus.
        replay = instance.browser.get(url, headers=DIRECT_NAVIGATION, follow_redirects=False)
        assert replay.headers["location"] == "/workspace/?session=lien-invalide"
    # Ni le CLI (rapport, dossier de l'instance) ni l'API (base, journal d'audit) n'ont écrit le lien.
    assert files_containing(tmp_path, link) == []


@pytest.mark.skipif(sys.platform == "win32", reason="ouverture Linux")
def test_linux_without_a_browser_names_the_launcher_option_and_keeps_the_link_private(tmp_path, monkeypatch, capsys, caplog):
    offered = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: offered.append(url) or False)
    caplog.set_level(logging.DEBUG)
    report = tmp_path / "rapport.json"
    with workspace(tmp_path, monkeypatch):
        assert run_cli(monkeypatch, "--report", str(report)) == 1
        printed, journal = capsys.readouterr(), logged(caplog)
    [url] = offered
    link = assert_loopback_link(url)
    failure = {"status": "failed", "error": "RuntimeError",
               "message": "Aucun navigateur disponible dans cette session : « ./rag.sh open --no-browser » affiche le "
                          "lien à usage unique"}
    assert json.loads(printed.out) == failure and json.loads(report.read_text(encoding="utf-8")) == failure
    assert link not in printed.out + printed.err and link not in journal
    assert files_containing(tmp_path, link) == []


def test_no_browser_prints_the_loopback_link_but_never_writes_it(tmp_path, monkeypatch, capsys, caplog):
    # `./rag.sh open --no-browser` (Linux) ou `.\rag.ps1 open -NoBrowser` (Windows) : le lien est affiché pour être
    # collé dans un navigateur du poste ; le rapport le retire.
    monkeypatch.setattr("webbrowser.open", lambda *args, **kwargs: pytest.fail("aucun navigateur attendu"))
    monkeypatch.setattr(cli.os, "startfile", lambda *args: pytest.fail("aucun navigateur attendu"), raising=False)
    caplog.set_level(logging.DEBUG)
    report = tmp_path / "rapport.json"
    with workspace(tmp_path, monkeypatch):
        assert run_cli(monkeypatch, "--no-browser", "--report", str(report)) == 0
        printed, journal = capsys.readouterr(), logged(caplog)
    shown = json.loads(printed.out)
    link = assert_loopback_link(shown["url"])
    assert shown == {"opened_in_browser": False, "url": shown["url"], "expires_in_seconds": 300, "single_use": True}
    assert json.loads(report.read_text(encoding="utf-8")) == {"opened_in_browser": False, "expires_in_seconds": 300,
                                                              "single_use": True}
    assert link not in journal and files_containing(tmp_path, link) == []


def test_windows_still_hands_the_link_to_the_default_browser_by_startfile(tmp_path, monkeypatch):
    # Plateforme Windows simulée pour le seul module cli : comportement qualifié inchangé (os.startfile avec le lien).
    started = []
    monkeypatch.setattr(cli, "sys", types.SimpleNamespace(platform="win32"))
    monkeypatch.setattr(cli.os, "startfile", started.append, raising=False)
    monkeypatch.setattr("webbrowser.open", lambda *args, **kwargs: pytest.fail("webbrowser non utilisé sous Windows"))
    with workspace(tmp_path, monkeypatch):
        result = cli.open_workspace(Path("profil.yaml"))
    [url] = started
    link = assert_loopback_link(url)
    assert result == OPENED
    assert files_containing(tmp_path, link) == []
