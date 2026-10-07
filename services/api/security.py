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
import logging
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.runtime.platforms import installation, launcher_command, launcher_instruction

from .errors import ApiError

ENVIRONMENTS = ("development", "production")


def link_help() -> str:
    """Comment rouvrir l'atelier : « .\\rag.ps1 open » sous Windows (texte inchangé) et « ./rag.sh open » dans un clone
    Linux (W018), depuis le dossier du projet ; dans une installation par le kit Linux, l'entrée de menu si elle existe et
    la commande du lanceur atelier, à taper dans un terminal."""
    installed = installation()
    if installed and installed.menu:
        return (f"Ouvrir l'atelier depuis le menu des applications ({installed.menu}) ou avec "
                f"« {launcher_command('open')} » dans un terminal.")
    return f"Ouvrir l'atelier avec {launcher_instruction('open')}."

logger = logging.getLogger("rag.security")


def scheme_for(environment: str) -> str:
    """Schéma servi par l'API : HTTPS en production (W011), HTTP en développement."""
    return "https" if environment == "production" else "http"


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
        return scheme_for(self.environment)

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


class AuditLog:
    """Journal JSONL borné, écrit hors de la boucle asynchrone de l'API.

    Même politique que la trace de ressources du superviseur (`RotatingJsonl` de `services.runtime.supervisor`) :
    fichier courant d'au plus `max_bytes` puis archives `.1` à `.archives`, lignes jamais coupées ; si Windows
    refuse un renommage (analyse antivirus, lecteur ouvert sans partage de suppression), la rotation est
    reportée de `retry_after_seconds` sans perdre de ligne. Un fil dédié écrit les enregistrements reçus par une
    file : l'appelant, y compris le middleware de l'API, ne fait aucune entrée-sortie disque.

    Le fil survit à toute exception d'écriture (comptée dans `failures`) et l'écriture suivante le relance s'il est
    mort (`writer_restarts`). La file est bornée à `queue_limit_bytes` octets en attente : au-delà, l'enregistrement
    est abandonné et compté (`dropped`) plutôt que de bloquer la requête ou de laisser croître la mémoire quand le
    disque ne répond plus. Les compteurs sont publiés par `state()` dans `/api/v1/diagnostics`.
    """

    def __init__(self, path: Path, max_bytes: int = 5 * 1048576, archives: int = 2,
                 busy_timeout_seconds: float = 1.0, retry_after_seconds: float = 30.0,
                 queue_limit_bytes: int = 8 * 1048576, clock=time.monotonic):
        self.path, self.max_bytes, self.archives = Path(path), max_bytes, archives
        self.busy_timeout_seconds, self.retry_after_seconds = busy_timeout_seconds, retry_after_seconds
        self.queue_limit_bytes, self.clock = queue_limit_bytes, clock
        self.failures = 0
        self.dropped = 0
        self.writer_restarts = 0
        self.rotations_deferred = 0
        self._pending_bytes = 0
        self._dropped_reported = 0
        self._counter_lock = threading.Lock()
        self._queue: queue.SimpleQueue[bytes | threading.Event | None] = queue.SimpleQueue()
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stream: Any = None
        self._retry_at = 0.0

    def state(self) -> dict[str, int]:
        """Compteurs du fil d'écriture depuis le démarrage du processus (diagnostics)."""
        with self._counter_lock:
            return {"failures": self.failures, "dropped": self.dropped, "writer_restarts": self.writer_restarts,
                    "rotations_deferred": self.rotations_deferred, "pending_bytes": self._pending_bytes,
                    "queue_limit_bytes": self.queue_limit_bytes}

    def _ensure_writer(self) -> None:
        thread = self._thread
        if thread is not None and thread.is_alive():
            return
        with self._start_lock:
            thread = self._thread
            if thread is not None and thread.is_alive():
                return
            if thread is not None:
                # Fil terminé sans fermeture (exception hors Exception) : relancé, la file est conservée.
                with self._counter_lock:
                    self.writer_restarts += 1
            self._thread = threading.Thread(target=self._run, name="rag-security-audit", daemon=True)
            self._thread.start()

    def write(self, record: dict[str, Any]) -> None:
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        self._ensure_writer()
        with self._counter_lock:
            if self._pending_bytes + len(line) > self.queue_limit_bytes:
                self.dropped += 1
                return
            self._pending_bytes += len(line)
        self._queue.put(line)

    def flush(self, timeout: float = 5.0) -> bool:
        """Attend l'écriture des enregistrements déjà remis ; faux si le délai expire."""
        if self._thread is None and self._queue.empty():
            return True
        self._ensure_writer()
        written = threading.Event()
        self._queue.put(written)
        return written.wait(timeout)

    def close(self, timeout: float = 5.0) -> bool:
        """Écrit ce qui reste dans la file puis arrête le fil d'écriture ; un enregistrement ultérieur le relance."""
        if self._thread is None and self._queue.empty():
            return True
        self._ensure_writer()
        with self._start_lock:
            thread = self._thread
            if thread is None:
                return True
            self._queue.put(None)
            thread.join(timeout)
            if thread.is_alive():
                return False
            self._thread = None
            return True

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            if isinstance(item, threading.Event):
                item.set()
                continue
            with self._counter_lock:
                self._pending_bytes -= len(item)
            try:
                self._append(item)
            except Exception:
                # Aucune requête n'échoue pour l'audit ; l'échec reste visible dans le journal de l'API et les diagnostics.
                with self._counter_lock:
                    self.failures += 1
                logger.exception("Journal d'audit de sécurité : écriture impossible dans %s", self.path)
                self._discard_stream()
            self._report_dropped()
        self._discard_stream()

    def _report_dropped(self) -> None:
        with self._counter_lock:
            dropped, reported = self.dropped, self._dropped_reported
            self._dropped_reported = dropped
        if dropped != reported:
            logger.warning("Journal d'audit de sécurité : %d enregistrement(s) abandonné(s), file d'attente pleine (%d octets)",
                           dropped - reported, self.queue_limit_bytes)

    def _append(self, line: bytes) -> None:
        if self._stream is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = self.path.open("ab")
        position = self._stream.tell()
        if position and position + len(line) > self.max_bytes and self.clock() >= self._retry_at:
            self._rotate()
        self._stream.write(line)
        self._stream.flush()

    def _rotate(self) -> None:
        self._close_stream()
        deadline = self.clock() + self.busy_timeout_seconds
        try:
            for index in range(self.archives, 0, -1):
                source = self.path if index == 1 else self.path.with_name(f"{self.path.name}.{index - 1}")
                while source.exists():
                    try:
                        source.replace(self.path.with_name(f"{self.path.name}.{index}"))
                    except PermissionError:
                        if self.clock() >= deadline:
                            raise
                        time.sleep(0.02)
        except PermissionError as error:
            # Refus persistant : aucune ligne perdue, rotation reportée (borne dépassée d'autant).
            self._retry_at = self.clock() + self.retry_after_seconds
            with self._counter_lock:
                self.rotations_deferred += 1
            logger.warning("Journal d'audit de sécurité : rotation de %s reportée de %g s (%s)", self.path, self.retry_after_seconds, error)
        finally:
            self._stream = self.path.open("ab")

    def _close_stream(self) -> None:
        if self._stream is not None:
            stream, self._stream = self._stream, None
            stream.close()

    def _discard_stream(self) -> None:
        """Ferme le flux après un échec ; une erreur de fermeture ne doit pas terminer le fil d'écriture."""
        try:
            self._close_stream()
        except Exception:
            logger.exception("Journal d'audit de sécurité : fermeture impossible de %s", self.path)


class SessionRegistry:
    def __init__(self, policy: SecurityPolicy, audit_path: Path | None = None, clock=time.time):
        self.policy, self.audit_path, self.clock = policy, audit_path, clock
        self.audit_log = AuditLog(audit_path) if audit_path is not None else None
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._links: dict[str, float] = {}
        # Motif d'expiration des sessions purgées, pour ne pas les présenter comme inconnues (borné).
        self._expired: dict[str, str] = {}

    def _purge(self, now: float) -> None:
        self._links = {key: expiry for key, expiry in self._links.items() if expiry > now}
        kept: dict[str, Session] = {}
        for key, session in self._sessions.items():
            reason = self._expiry_reason(session, now)
            if reason is None:
                kept[key] = session
            else:
                self._expired[key] = reason
        self._sessions = kept
        while len(self._expired) > 256:
            self._expired.pop(next(iter(self._expired)))

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
                raise ApiError("session_link_invalid", "Lien d'ouverture inconnu, déjà utilisé ou expiré. " + link_help(), 401)
            replaced = previous is not None and self._sessions.pop(digest(previous), None) is not None
            session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self._sessions[digest(session_id)] = Session(digest(csrf), now, now)
            self._purge(now)
        self.audit("session_opened", session=digest(session_id)[:12], replaced_previous=replaced)
        return session_id, csrf

    def check(self, cookie: str | None, *, activity: bool = True) -> tuple[Session | None, str]:
        """Session valide ou motif de refus, sans lever d'exception.

        Seule une activité de l'utilisateur remet l'inactivité à zéro : les relectures
        périodiques de l'atelier (``activity=False``) vérifient la session sans la prolonger.
        """
        if not cookie:
            return None, "session_required"
        now = self.clock()
        key = digest(cookie)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None, self._expired.get(key, "session_unknown")
            reason = self._expiry_reason(session, now)
            if reason:
                del self._sessions[key]
                self._expired[key] = reason
                return None, reason
            if activity:
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
        """Journal JSONL des événements de sécurité : empreintes tronquées, jamais de secret ni de texte de document.

        L'enregistrement est remis au fil d'écriture du journal borné (`AuditLog`) : aucune E/S dans l'appelant.
        """
        if self.audit_log is None:
            return
        self.audit_log.write({"utc": dt.datetime.now(dt.UTC).isoformat(), "event": event, **fields})

    def audit_state(self) -> dict[str, Any]:
        """Compteurs du journal d'audit pour les diagnostics ; aucun contenu d'événement."""
        return self.audit_log.state() if self.audit_log is not None else {"status": "not_configured"}

    def close(self) -> None:
        """Écrit les événements d'audit encore en file ; appelé à l'arrêt de l'API."""
        if self.audit_log is not None:
            self.audit_log.close()


def cookie_attributes(policy: SecurityPolicy, max_age: int, *, http_only: bool) -> dict[str, Any]:
    """Attributs communs des cookies de l'atelier, pour `Response.set_cookie`."""
    return {"max_age": max_age, "path": "/", "secure": policy.production, "httponly": http_only, "samesite": "strict"}
