"""Session locale du poste (W011) : refus par défaut, lien à usage unique, expiration, CSRF, révocation."""
import json

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from test_api_http import FakeEmbedding, FakeGovernor, FakeOllama, FakeTokenizer, FakeVectors

from services.api.errors import ApiError
from services.api.main import PUBLIC_PATHS, create_app
from services.api.security import SecurityPolicy
from services.api.settings import Settings

CONTROL = "test-only-nonce"
ORIGIN = "http://127.0.0.1:8785"


@pytest.fixture(autouse=True)
def control_token(monkeypatch):
    monkeypatch.setenv("RAG_CONTROL_TOKEN", CONTROL)


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def build(tmp_path, security=None):
    profile = {"app": {"data_dir": "runtime", "port": 8785}}
    if security is not None:
        profile["security"] = security
    settings = Settings(tmp_path, profile)
    app = create_app(settings=settings, embedding=FakeEmbedding(), vectors=FakeVectors(), tokenizer=FakeTokenizer(),
                     ollama=FakeOllama(), governor=FakeGovernor(), start_jobs=False)
    clock = Clock()
    app.state.sessions.clock = clock
    return app, clock


def issue_link(client):
    response = client.post("/api/v1/admin/session-links", headers={"X-RAG-Control-Token": CONTROL})
    assert response.status_code == 200
    return response.json()["path"]


def open_session(client):
    opened = client.get(issue_link(client), follow_redirects=False)
    assert opened.status_code == 303 and opened.headers["location"] == "/workspace/"
    return opened


def test_every_mounted_api_route_refuses_requests_without_session(tmp_path):
    app, _ = build(tmp_path)
    guarded = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/v1/")
               and route.path not in PUBLIC_PATHS and not route.path.startswith("/api/v1/admin/")]
    # Plancher : la population examinée n'est pas vide et couvre les familles de routes connues.
    assert len(guarded) >= 20
    with TestClient(app, base_url=ORIGIN) as client:
        for route in guarded:
            path = route.path.replace("{", "").replace("}", "")
            for method in sorted(route.methods):
                response = client.request(method, path, headers={"Origin": ORIGIN})
                assert response.status_code == 401, (method, route.path, response.status_code)
                assert response.json()["code"] == "session_required"
        # Sondes de disponibilité publiques ; administration réservée au jeton de contrôle.
        assert client.get("/api/v1/health").status_code == 200
        assert client.post("/api/v1/admin/session-links").status_code == 403
        assert client.get("/api/v1/library/tree", headers={"X-RAG-Control-Token": "autre"}).status_code == 401
        assert client.get("/api/v1/library/tree", headers={"X-RAG-Control-Token": CONTROL}).status_code == 200


def test_opening_link_sets_strict_http_only_cookies_and_is_single_use(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        link = issue_link(client)
        opened = client.get(link, follow_redirects=False)
        cookies = {header.split("=", 1)[0]: header.lower() for header in opened.headers.get_list("set-cookie")}
        assert set(cookies) == {"rag_session", "rag_csrf"}
        assert "httponly" in cookies["rag_session"] and "httponly" not in cookies["rag_csrf"]
        for header in cookies.values():
            assert "samesite=strict" in header and "path=/" in header and "max-age=43200" in header
            assert "secure" not in header and "domain=" not in header
        assert client.get("/api/v1/library/tree").status_code == 200
        client.cookies.clear()
        replay = client.get(link, follow_redirects=False)
        assert replay.headers["location"] == "/workspace/?session=lien-invalide"
        assert client.get("/api/v1/library/tree").status_code == 401


def test_link_expires_after_its_validity_window(tmp_path):
    app, clock = build(tmp_path, {"launch_link_ttl_seconds": 60})
    with TestClient(app, base_url=ORIGIN) as client:
        link = issue_link(client)
        clock.now += 61
        assert client.get(link, follow_redirects=False).headers["location"] == "/workspace/?session=lien-invalide"


def test_idle_and_absolute_expiry_are_enforced_server_side(tmp_path):
    app, clock = build(tmp_path, {"session_idle_minutes": 30, "session_absolute_hours": 2})
    with TestClient(app, base_url=ORIGIN) as client:
        open_session(client)
        clock.now += 29 * 60
        assert client.get("/api/v1/library/tree").status_code == 200
        clock.now += 29 * 60
        assert client.get("/api/v1/library/tree").status_code == 200  # activité : l'inactivité repart de zéro
        clock.now += 30 * 60
        refused = client.get("/api/v1/library/tree")
        assert refused.status_code == 401 and refused.json()["details"]["reason"] == "session_idle_expired"
        open_session(client)
        for _ in range(5):  # 125 min d'activité régulière : seule la durée absolue expire
            clock.now += 25 * 60
            last = client.get("/api/v1/library/tree")
        assert last.status_code == 401 and last.json()["details"]["reason"] == "session_absolute_expired"


def test_mutations_require_the_session_csrf_token(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        open_session(client)
        body = {"question": "tension", "scope": {"kind": "library"}}
        missing = client.post("/api/v1/search", json=body, headers={"Origin": ORIGIN})
        wrong = client.post("/api/v1/search", json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": "x" * 43})
        assert missing.status_code == wrong.status_code == 403 and missing.json()["code"] == "csrf_rejected"
        accepted = client.post("/api/v1/search", json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": client.cookies["rag_csrf"]})
        assert accepted.status_code != 403
        # Le jeton de contrôle des outils locaux n'est pas une session de navigateur : pas de CSRF exigé.
        assert client.post("/api/v1/search", json=body, headers={"X-RAG-Control-Token": CONTROL}).status_code != 403


def test_logout_revokes_only_with_csrf_and_always_clears_cookies(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        open_session(client)
        session, csrf = client.cookies["rag_session"], client.cookies["rag_csrf"]
        forced = client.post("/api/v1/session/logout", headers={"Origin": ORIGIN})
        assert forced.json() == {"revoked": False}
        assert any(header.startswith("rag_session=") and "max-age=0" in header.lower() for header in forced.headers.get_list("set-cookie"))
        client.cookies.set("rag_session", session)
        assert client.get("/api/v1/library/tree").status_code == 200
        logout = client.post("/api/v1/session/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert logout.json() == {"revoked": True}
        client.cookies.set("rag_session", session)
        refused = client.get("/api/v1/library/tree")
        assert refused.status_code == 401 and refused.json()["details"]["reason"] == "session_unknown"


def test_new_session_replaces_the_previous_one_and_admin_can_revoke_all(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        open_session(client)
        first = client.cookies["rag_session"]
        open_session(client)
        second = client.cookies["rag_session"]
        assert first != second
        client.cookies.set("rag_session", first)
        assert client.get("/api/v1/library/tree").status_code == 401  # fixation de session : l'ancienne est révoquée
        client.cookies.set("rag_session", second)
        assert client.get("/api/v1/session").json()["method"] == "session"
        assert client.post("/api/v1/admin/sessions/revoke", headers={"X-RAG-Control-Token": CONTROL}).json() == {"revoked": 1}
        assert client.get("/api/v1/library/tree").status_code == 401


def test_security_headers_and_audit_without_secrets(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        link = issue_link(client)
        client.get(link, follow_redirects=False)
        response = client.get("/api/v1/library/tree")
        for name, value in {"X-Frame-Options": "DENY", "Cross-Origin-Opener-Policy": "same-origin",
                            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}.items():
            assert response.headers[name] == value
        assert "Cookie" in response.headers["Vary"] and "camera=()" in response.headers["Permissions-Policy"]
        assert "Strict-Transport-Security" not in response.headers
        client.post("/api/v1/search", json={"question": "x", "scope": {"kind": "library"}}, headers={"Origin": ORIGIN})
        secrets_seen = [link.split("link=")[1], client.cookies["rag_session"], client.cookies["rag_csrf"], CONTROL]
    audit = (tmp_path / "runtime/logs/security-audit.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line)["event"] for line in audit.splitlines()]
    assert {"session_link_issued", "session_opened", "csrf_rejected"} <= set(events)
    assert not any(secret in audit for secret in secrets_seen)


def test_production_requires_tls_files_and_hardens_cookies(tmp_path):
    with pytest.raises(ApiError, match="TLS"):
        SecurityPolicy.from_settings(Settings(tmp_path, {"security": {"environment": "production"}}))
    for invalid in ({"environment": "staging"}, {"session_idle_minutes": 900, "session_absolute_hours": 1}):
        with pytest.raises(ApiError):
            SecurityPolicy.from_settings(Settings(tmp_path, {"security": invalid}))
    (tmp_path / "cert.pem").write_text("certificat de test", encoding="ascii")
    (tmp_path / "key.pem").write_text("clé de test", encoding="utf-8")
    app, _ = build(tmp_path, {"environment": "production", "tls_cert_file": "cert.pem", "tls_key_file": "key.pem"})
    with TestClient(app, base_url="https://127.0.0.1:8785") as client:
        opened = client.get(issue_link(client), follow_redirects=False)
        cookies = {header.split("=", 1)[0]: header.lower() for header in opened.headers.get_list("set-cookie")}
        assert set(cookies) == {"__Host-rag_session", "__Host-rag_csrf"}
        assert all("secure" in header and "path=/" in header and "domain=" not in header for header in cookies.values())
        assert opened.headers["Strict-Transport-Security"] == "max-age=31536000"
        assert client.get("/api/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
        assert client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:8785"}).status_code == 403
