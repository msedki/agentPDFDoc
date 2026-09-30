"""Session locale du poste (W011) : lien d'ouverture à usage unique, cookies, CSRF et journal d'audit.

Poste mono-utilisateur sans compte : le lanceur local, muni du jeton de contrôle de
l'instance, demande un lien d'ouverture ; le navigateur l'échange contre un cookie de
session. Le registre reste en mémoire du seul processus API : un redémarrage révoque
toutes les sessions. Seuls les SHA-256 des identifiants et jetons sont conservés.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ApiError

ENVIRONMENTS = ("development", "production")
LINK_HELP = "Ouvrir l'atelier avec « .\\rag.ps1 open » depuis le dossier du projet."


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SecurityPolicy:
    environment: str
    idle_seconds: int
    absolute_seconds: int
    link_seconds: int
    tls_cert_file: Path | None
    tls_key_file: Path | None

    @classmethod
    def from_settings(cls, settings) -> SecurityPolicy:
        section = settings.profile.get("security") or {}
        environment = section.get("environment", "development")
        if environment not in ENVIRONMENTS:
            raise ApiError("invalid_profile", "security.environment doit valoir development ou production.")
        try:
            idle = int(section.get("session_idle_minutes", 120)) * 60
            absolute = int(section.get("session_absolute_hours", 12)) * 3600
            link = int(section.get("launch_link_ttl_seconds", 300))
        except (TypeError, ValueError) as error:
            raise ApiError("invalid_profile", "Durées de session du profil invalides.") from error
        if not (0 < idle <= absolute and 0 < link <= 3600):
            raise ApiError("invalid_profile", "Durées de session incohérentes : inactivité ≤ durée absolue, lien ≤ 1 h.")
        cert, key = (settings.path(section[name]) if section.get(name) else None for name in ("tls_cert_file", "tls_key_file"))
        if environment == "production" and not (cert and key and cert.is_file() and key.is_file()):
            raise ApiError("invalid_profile", "Production : certificat et clé TLS du profil requis et lisibles.")
        return cls(environment, idle, absolute, link, cert, key)

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def scheme(self) -> str:
        return "https" if self.production else "http"

    @property
    def session_cookie(self) -> str:
        # Le préfixe __Host- impose Secure, Path=/ et l'absence de Domain (OWASP) : production seulement.
        return "__Host-rag_session" if self.production else "rag_session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-rag_csrf" if self.production else "rag_csrf"


@dataclass
class Session:
    csrf_hash: str
    created: float
    last_seen: float


class SessionRegistry:
    def __init__(self, policy: SecurityPolicy, audit_path: Path | None = None, clock=time.time):
        self.policy, self.audit_path, self.clock = policy, audit_path, clock
        self._lock = threading.Lock()
        self._audit_lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._links: dict[str, float] = {}

    def _purge(self, now: float) -> None:
        self._links = {key: expiry for key, expiry in self._links.items() if expiry > now}
        self._sessions = {key: session for key, session in self._sessions.items() if self._expiry_reason(session, now) is None}

    def _expiry_reason(self, session: Session, now: float) -> str | None:
        if now - session.created >= self.policy.absolute_seconds:
            return "session_absolute_expired"
        if now - session.last_seen >= self.policy.idle_seconds:
            return "session_idle_expired"
        return None

    def issue_link(self) -> str:
        token = secrets.token_urlsafe(32)
        now = self.clock()
        with self._lock:
            self._purge(now)
            self._links[digest(token)] = now + self.policy.link_seconds
        self.audit("session_link_issued", link=digest(token)[:12])
        return token

    def open(self, link: str, previous: str | None) -> tuple[str, str]:
        now = self.clock()
        with self._lock:
            # Usage unique : le lien est retiré dès sa présentation, valide ou non.
            expiry = self._links.pop(digest(link), None) if link else None
            if expiry is None or expiry <= now:
                reason = "unknown_or_used" if expiry is None else "expired"
                self._purge(now)
                self.audit("session_link_rejected", reason=reason)
                raise ApiError("session_link_invalid", "Lien d'ouverture inconnu, déjà utilisé ou expiré. " + LINK_HELP, 401)
            replaced = previous is not None and self._sessions.pop(digest(previous), None) is not None
            session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self._sessions[digest(session_id)] = Session(digest(csrf), now, now)
            self._purge(now)
        self.audit("session_opened", session=digest(session_id)[:12], replaced_previous=replaced)
        return session_id, csrf

    def check(self, cookie: str | None) -> tuple[Session | None, str]:
        """Session valide (inactivité remise à zéro) ou motif de refus, sans lever d'exception."""
        if not cookie:
            return None, "session_required"
        now = self.clock()
        key = digest(cookie)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None, "session_unknown"
            reason = self._expiry_reason(session, now)
            if reason:
                del self._sessions[key]
                return None, reason
            session.last_seen = now
            return session, "ok"

    def expires(self, session: Session) -> dict[str, str]:
        def iso(seconds: float) -> str:
            return dt.datetime.fromtimestamp(seconds, dt.UTC).isoformat()
        return {"created_at": iso(session.created),
                "idle_expires_at": iso(session.last_seen + self.policy.idle_seconds),
                "absolute_expires_at": iso(session.created + self.policy.absolute_seconds)}

    @staticmethod
    def csrf_valid(session: Session, token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(session.csrf_hash, digest(token or ""))

    def revoke(self, cookie: str | None, reason: str) -> bool:
        if not cookie:
            return False
        with self._lock:
            revoked = self._sessions.pop(digest(cookie), None) is not None
        if revoked:
            self.audit("session_revoked", session=digest(cookie)[:12], reason=reason)
        return revoked

    def revoke_all(self, reason: str) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            self._links.clear()
        self.audit("sessions_revoked_all", count=count, reason=reason)
        return count

    def active_count(self) -> int:
        with self._lock:
            self._purge(self.clock())
            return len(self._sessions)

    def audit(self, event: str, **fields: Any) -> None:
        """Journal JSONL des événements de sécurité : empreintes tronquées, jamais de secret ni de texte de document."""
        if self.audit_path is None:
            return
        record = {"utc": dt.datetime.now(dt.UTC).isoformat(), "event": event, **fields}
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_lock, self.audit_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def cookie_attributes(policy: SecurityPolicy, max_age: int, *, http_only: bool) -> dict[str, Any]:
    """Attributs communs des cookies de l'atelier, pour `Response.set_cookie`."""
    return {"max_age": max_age, "path": "/", "secure": policy.production, "httponly": http_only, "samesite": "strict"}
