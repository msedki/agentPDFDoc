"""Contrôle des gardes HTTP d'une instance démarrée (D08.3), en lecture seule.

Envoie des requêtes loopback aux en-têtes Host/Origin forgés, comme le ferait une
page web étrangère après rebinding DNS, vers l'API, Ollama et Qdrant de l'instance
décrite par le profil. Aucun document n'est lu ni modifié ; la clé Qdrant de
l'instance est lue dans son dossier de contrôle et n'est jamais écrite dans le
rapport. Ce contrôle ne remplace pas le blocage réseau du système (D08.1).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.supervisor import data_path, load_profile, read_state  # noqa: E402
from tools.qualification.evidence_io import checked_output, write_json_exclusive  # noqa: E402

FOREIGN = "attaquant.example"


def checks(profile: dict, qdrant_key: str | None) -> list[dict]:
    api = f"127.0.0.1:{profile['app']['port']}"
    ollama = profile["llm"]["base_url"].removeprefix("http://").rstrip("/")
    qdrant = profile["qdrant"]["url"].removeprefix("http://").rstrip("/")
    rows = [
        ("api", "GET", api, "/api/v1/health", {}, 200),
        ("api", "GET", api, "/api/v1/health", {"Host": "localhost:" + api.split(":")[1]}, 200),
        ("api", "GET", api, "/api/v1/health", {"Host": FOREIGN}, 400),
        ("api", "GET", api, "/api/v1/health", {"Host": "127.0.0.1:9999"}, 400),
        ("api", "GET", api, "/api/v1/health", {"Origin": "http://" + FOREIGN}, 403),
        ("api", "GET", api, "/api/v1/health", {"Sec-Fetch-Site": "cross-site"}, 403),
        ("api", "POST", api, "/api/v1/search", {"Origin": "http://" + FOREIGN}, 403),
        ("api", "POST", api, "/api/v1/search", {"Origin": "null"}, 403),
        ("ollama", "GET", ollama, "/api/tags", {"Host": FOREIGN}, 403),
        ("ollama", "GET", ollama, "/api/tags", {"Origin": "http://" + FOREIGN}, 403),
        # Liste blanche Qdrant 1.19.1 : `/` (version) et les sondes restent lisibles sans clé.
        ("qdrant", "GET", qdrant, "/healthz", {"Host": FOREIGN}, 200),
        ("qdrant", "GET", qdrant, "/collections", {}, 401),
        ("qdrant", "GET", qdrant, "/collections", {"Host": FOREIGN, "Origin": "http://" + FOREIGN}, 401),
        ("qdrant", "GET", qdrant, "/telemetry", {"Host": FOREIGN}, 401),
    ]
    if qdrant_key:
        rows.append(("qdrant", "GET", qdrant, "/collections", {"api-key": qdrant_key}, 200))
    return [{"service": service, "method": method, "authority": authority, "path": path,
             "headers": headers, "expected_status": expected} for service, method, authority, path, headers, expected in rows]


def run(profile_path: Path) -> dict:
    profile = load_profile(profile_path)
    directory = data_path(profile)
    state = read_state(directory)
    key_path = directory / "control/qdrant-api-key"
    key = key_path.read_text(encoding="ascii").strip() if key_path.exists() else None
    results = []
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        for row in checks(profile, key):
            body = {"question": "contrôle des gardes", "scope": {"kind": "library"}} if row["method"] == "POST" else None
            try:
                response = client.request(row["method"], f"http://{row['authority']}{row['path']}",
                                          headers=row["headers"], json=body)
                status, code = response.status_code, None
                if "json" in response.headers.get("content-type", ""):
                    payload = response.json()
                    code = payload.get("code") if isinstance(payload, dict) else None
            except httpx.HTTPError as exc:
                status, code = None, type(exc).__name__
            shown = {name: ("<clé de l'instance>" if name == "api-key" else value) for name, value in row["headers"].items()}
            results.append({**row, "headers": shown, "status": status, "code": code,
                            "pass": status == row["expected_status"]})
    return {"utc": dt.datetime.now(dt.UTC).isoformat(), "profile": str(profile_path),
            "instance_id": state.get("instance_id"), "instance_status": state.get("status"),
            "qdrant_auth_recorded": state.get("qdrant_auth"), "qdrant_key_available": key is not None,
            "method": "httpx loopback, en-têtes Host/Origin/Sec-Fetch-Site forgés ; aucune redirection suivie",
            "limit": "Contrôle applicatif ; ne prouve pas le blocage réseau du système (D08.1)",
            "results": results, "passed": sum(item["pass"] for item in results), "total": len(results),
            "verdict": "PASS" if key is not None and all(item["pass"] for item in results) else "FAIL"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau rapport JSON (jamais remplacé)")
    args = parser.parse_args()
    output = checked_output(args.output, [ROOT / "RAG_Local_Agents/reports", ROOT / ".runtime/qa"])
    report = run(args.profile)
    write_json_exclusive(output, report)
    print(f"{report['verdict']} {report['passed']}/{report['total']} -> {args.output}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
