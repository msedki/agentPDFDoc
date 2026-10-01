"""Gardes HTTP, traversées et écoute réseau d'une instance en marche, en lecture seule (critères D08.3, D08.4).

Rejoue sur l'API, Ollama et Qdrant de l'instance les contrôles d'en-têtes forgés du 30/09 (Host et Origin étrangers,
requête inter-sites, Qdrant sans clé), vérifie qu'aucune réponse n'ouvre le CORS à toute origine et qu'un préflight
étranger est refusé, tente des traversées encodées vers le profil, la base et les jetons de l'instance (refus sans
aucun contenu sensible), puis relève les sockets en écoute de chaque processus de l'instance : seules les adresses de
bouclage sont admises. Aucune écriture, aucun import, aucune question.

Limite : contrôle applicatif ; il ne prouve pas le blocage réseau du système (D08.1).

    .venv\\Scripts\\python.exe tools/qualification/http_guards_check.py [--profile config/local16.yaml] --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.supervisor import data_path, load_profile, status  # noqa: E402

FOREIGN = "attaquant.example"
LOOPBACK = {"127.0.0.1", "::1"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    profile = load_profile(args.profile)
    state = status(args.profile)
    if state.get("status") != "running":
        print(json.dumps({"result": "NOT_RUN", "reason": f"instance {state.get('status')}"}, ensure_ascii=False))
        return 2
    api = f"{profile['app']['host']}:{profile['app']['port']}"
    ollama = urlparse(profile["llm"]["base_url"]).netloc
    qdrant = urlparse(profile["qdrant"]["url"]).netloc
    key = (data_path(profile) / "control" / "qdrant-api-key").read_text(encoding="ascii").strip()
    origin = f"http://{api}"
    cases: list[tuple[str, str, str, str, dict[str, str], int, str | None]] = [
        ("api", "GET", api, "/api/v1/health", {}, 200, None),
        ("api", "GET", api, "/api/v1/health", {"Host": f"localhost:{profile['app']['port']}"}, 200, None),
        ("api", "GET", api, "/api/v1/health", {"Host": FOREIGN}, 400, "invalid_host"),
        ("api", "GET", api, "/api/v1/health", {"Host": "127.0.0.1:9999"}, 400, "invalid_host"),
        ("api", "GET", api, "/api/v1/health", {"Origin": f"http://{FOREIGN}"}, 403, "invalid_origin"),
        ("api", "GET", api, "/api/v1/health", {"Sec-Fetch-Site": "cross-site"}, 403, "cross_site_request"),
        ("api", "POST", api, "/api/v1/search", {"Origin": f"http://{FOREIGN}"}, 403, "invalid_origin"),
        ("api", "POST", api, "/api/v1/search", {"Origin": "null"}, 403, "invalid_origin"),
        ("api", "OPTIONS", api, "/api/v1/search", {"Origin": f"http://{FOREIGN}", "Access-Control-Request-Method": "POST"}, 403, "invalid_origin"),
        ("ollama", "GET", ollama, "/api/tags", {"Host": FOREIGN}, 403, None),
        ("ollama", "GET", ollama, "/api/tags", {"Origin": f"http://{FOREIGN}"}, 403, None),
        ("qdrant", "GET", qdrant, "/healthz", {"Host": FOREIGN}, 200, None),
        ("qdrant", "GET", qdrant, "/collections", {}, 401, None),
        ("qdrant", "GET", qdrant, "/collections", {"Host": FOREIGN, "Origin": f"http://{FOREIGN}"}, 401, None),
        ("qdrant", "GET", qdrant, "/telemetry", {"Host": FOREIGN}, 401, None),
        ("qdrant", "GET", qdrant, "/collections", {"api-key": key}, 200, None),
        ("qdrant", "GET", qdrant, "/collections", {"api-key": key, "Origin": f"http://{FOREIGN}"}, 200, None),
    ]
    results = []
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        for service, method, authority, path, headers, expected, code in cases:
            response = client.request(method, f"http://{authority}{path}", headers=headers, json={"question": "x", "scope": {"kind": "library"}} if method == "POST" else None)
            try:
                body_code = response.json().get("code") if response.headers.get("content-type", "").startswith("application/json") else None
            except (ValueError, AttributeError):
                body_code = None
            allow = response.headers.get("access-control-allow-origin")
            results.append({"service": service, "method": method, "authority": authority, "path": path,
                            "headers": {name: ("<clé de l'instance>" if name == "api-key" else value) for name, value in headers.items()},
                            "expected_status": expected, "status": response.status_code, "code": body_code, "allow_origin": allow,
                            "pass": response.status_code == expected and (code is None or body_code == code) and allow not in {"*", f"http://{FOREIGN}", "null"}})
        same_origin = client.get(f"http://{api}/api/v1/health", headers={"Origin": origin})
        results.append({"service": "api", "method": "GET", "authority": api, "path": "/api/v1/health", "headers": {"Origin": origin}, "expected_status": 200,
                        "status": same_origin.status_code, "code": None, "allow_origin": same_origin.headers.get("access-control-allow-origin"),
                        "pass": same_origin.status_code == 200 and same_origin.headers.get("access-control-allow-origin") != "*"})
        # D08.4 : traversées encodées vers les fichiers de l'instance ; refus attendu sans aucun contenu sensible.
        admin = (data_path(profile) / "control" / "admin-token").read_text(encoding="ascii").strip()
        markers = {"jeton de contrôle": admin.encode(), "clé Qdrant": key.encode(), "profil": b"schema_version", "base SQLite": b"SQLite format 3"}
        for path in ("/..%2f..%2fconfig/local16.yaml", "/%2e%2e/%2e%2e/config/local16.yaml", "/..%5c..%5cconfig%5clocal16.yaml",
                     "/workspace/..%2f..%2f..%2f.runtime/data/control/admin-token", "/_next/..%2f..%2f..%2f..%2f.runtime/data/control/qdrant-api-key",
                     "/api/v1/versions/..%2f..%2fapp.sqlite3/file", "/api/v1/versions/%2e%2e/file", "/api/v1/versions/%2e%2e%2f%2e%2e%2fapp.sqlite3/file"):
            # Routes de l'API authentifiées par le jeton de contrôle : la route elle-même est éprouvée, pas seulement l'accès.
            authenticated = path.startswith("/api/")
            response = client.get(f"http://{api}{path}", headers={"x-rag-control-token": admin} if authenticated else {})
            leaked = [name for name, marker in markers.items() if marker in response.content]
            results.append({"service": "api", "method": "GET", "authority": api, "path": path, "headers": {"x-rag-control-token": "<jeton de l'instance>"} if authenticated else {}, "expected_status": "4xx",
                            "status": response.status_code, "code": None, "allow_origin": response.headers.get("access-control-allow-origin"),
                            "leaked": leaked, "pass": 400 <= response.status_code < 500 and not leaked})
    pids = {name: (service or {}).get("pid") for name, service in (state.get("services") or {}).items()}
    pids["supervisor"] = (state.get("supervisor") or {}).get("pid")
    listeners: dict[tuple[int, str, int], dict] = {}
    for name, pid in pids.items():
        if not pid or not psutil.pid_exists(pid):
            continue
        process = psutil.Process(pid)
        for member in [process] + process.children(recursive=True):
            for connection in member.net_connections(kind="inet"):
                if connection.status == psutil.CONN_LISTEN:
                    # Le superviseur énumère aussi ses enfants : un socket n'est compté qu'une fois, sous le premier service.
                    listeners.setdefault((member.pid, connection.laddr.ip, connection.laddr.port),
                                         {"service": name, "pid": member.pid, "process": member.name(), "address": connection.laddr.ip, "port": connection.laddr.port})
    sockets_ok = bool(listeners) and all(item["address"] in LOOPBACK for item in listeners.values())
    model_loaded = any(member.name().lower().startswith(("llama", "ollama_llama")) for pid in pids.values() if pid and psutil.pid_exists(pid)
                       for member in psutil.Process(pid).children(recursive=True))
    passed = sum(item["pass"] for item in results)
    report = {"utc": datetime.now(UTC).isoformat(), "criteria": ["D08.3", "D08.4"], "profile": args.profile.name, "instance_id": state.get("instance_id"),
              "method": "httpx loopback, en-têtes Host/Origin/Sec-Fetch-Site forgés, préflight CORS étranger, traversées encodées vers les fichiers de l'instance ; aucune redirection suivie ; sockets en écoute relevés par psutil",
              "limit": "Contrôle applicatif ; ne prouve pas le blocage réseau du système (D08.1). Sans modèle chargé, le processus d'inférence lancé par Ollama n'est pas observé.",
              "results": results, "passed": passed, "total": len(results), "listeners": list(listeners.values()), "listeners_loopback_only": sockets_ok,
              "inference_process_observed": model_loaded,
              "result": "PASS" if passed == len(results) and sockets_ok else "FAIL"}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "passed": passed, "total": len(results), "listeners": len(listeners), "loopback_only": sockets_ok}, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
