"""Client de l'API locale loopback : Host/Origin exacts, sans proxy ni redirection, SSE conservé brut."""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import httpx

TERMINAL_EVENTS = frozenset({"done", "error", "cancelled", "needs_clarification"})
IDENTITY_KEYS = ("profile_sha256", "selector_sha256", "dense_identity", "llm_tokenizer_identity", "qdrant_collection")


def loopback_origin(base_url: str) -> str:
    """Origine canonique acceptée par le middleware `local_boundary` (hôte loopback et port explicites)."""
    parsed = urlparse(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.port is None):
        raise ValueError("Seule une origine HTTP loopback avec port explicite est autorisée (ex. http://127.0.0.1:8785)")
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{parsed.port}"


def api_client(base_url: str, *, transport: httpx.BaseTransport | None = None, read_timeout: float = 60.0) -> httpx.Client:
    # Le serveur émet un heartbeat SSE toutes les 10 s : 60 s sans octet signale une coupure réelle.
    origin = loopback_origin(base_url)
    headers = {"Host": origin.removeprefix("http://"), "Origin": origin}
    # Outil local de l'instance (W011) : jeton de contrôle transmis par l'environnement, jamais en argument ni dans l'URL.
    token = os.environ.get("RAG_CONTROL_TOKEN")
    if token:
        headers["X-RAG-Control-Token"] = token
    return httpx.Client(base_url=origin, headers=headers, trust_env=False,
                        follow_redirects=False, transport=transport, timeout=httpx.Timeout(30.0, read=read_timeout))


def fetch_diagnostics(client: httpx.Client) -> dict:
    response = client.get("/api/v1/diagnostics")
    response.raise_for_status()
    return response.json()


def diagnostics_identity(diagnostics: dict) -> dict:
    return {key: diagnostics.get(key) for key in IDENTITY_KEYS}


def http_error(error: Exception) -> dict:
    result: dict[str, Any] = {"error_class": type(error).__name__}
    if isinstance(error, httpx.HTTPStatusError):
        result["http_status"] = error.response.status_code
        try:
            body = error.response.json()
            result.update(code=body.get("code"), message=body.get("message"))
        except ValueError:
            pass
    return result


def read_events(client: httpx.Client, events_url: str, *, started: float, deadline_s: float) -> dict:
    """Lit le flux jusqu'à l'événement terminal ; conserve les octets reçus et l'instant client de chaque événement."""
    if not events_url.startswith("/api/v1/queries/"):
        raise ValueError("events_url inattendu : seule la route SSE locale de la question est suivie")
    fields: dict[str, str]
    raw, buffer, events, fields = bytearray(), b"", [], {}
    terminal = None
    with client.stream("GET", events_url, headers={"Accept": "text/event-stream"}) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            buffer += chunk
            while terminal is None and b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                line = line_bytes.rstrip(b"\r").decode("utf-8")
                if line.startswith(":"):
                    continue
                if line:
                    name, _, value = line.partition(":")
                    value = value[1:] if value.startswith(" ") else value
                    fields[name] = fields[name] + "\n" + value if name == "data" and name in fields else value
                    continue
                if "event" in fields:
                    event = {"id": int(fields["id"]) if fields.get("id", "").isdigit() else None, "event": fields["event"],
                             "data": json.loads(fields.get("data", "null")), "client_s": round(time.perf_counter() - started, 3)}
                    events.append(event)
                    if event["event"] in TERMINAL_EVENTS:
                        terminal = event
                fields = {}
            if terminal is not None:
                break
            if time.perf_counter() - started > deadline_s:
                raise TimeoutError("Délai client dépassé avant l'événement terminal")
    text = bytes(raw).decode("utf-8", errors="replace")
    return {"events": events, "terminal": terminal, "sse": {"raw": text, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                                                              "event_counts": dict(Counter(event["event"] for event in events))}}


def submit_query(client: httpx.Client, body: dict) -> tuple[dict, float, float]:
    """Une seule soumission POST /api/v1/queries ; renvoie la création, l'instant client de départ et la durée du POST."""
    started = time.perf_counter()
    response = client.post("/api/v1/queries", json=body)
    response.raise_for_status()
    created = response.json()
    if not isinstance(created.get("query_id"), str) or created.get("events_url") != f"/api/v1/queries/{created['query_id']}/events":
        raise ValueError("Réponse de création sans query_id/events_url cohérents")
    return created, started, round((time.perf_counter() - started) * 1000, 2)


def follow_query(client: httpx.Client, created: dict, *, started: float, deadline_s: float) -> dict:
    stream = read_events(client, created["events_url"], started=started, deadline_s=deadline_s)
    first_delta = next((event["client_s"] for event in stream["events"] if event["event"] == "delta"), None)
    terminal = stream["terminal"]
    return {**stream, "client_first_delta_ms": round(first_delta * 1000, 2) if first_delta is not None else None,
            "client_terminal_ms": round(terminal["client_s"] * 1000, 2) if terminal else None}
