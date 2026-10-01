"""Contrôle réel de l'installation (DIST-05) dans une racine et des ports temporaires.

Une instance de contrôle démarre à côté de celle de l'utilisateur, avec le même programme et le même verrou lourd du
poste : import d'un PDF synthétique produit ici, extraction native, recherche hybride, provenance du passage retrouvé,
puis réponse du modèle avec citation si la mémoire l'admet maintenant. L'instance est arrêtée et sa racine supprimée à la
fin ; les données de l'utilisateur ne sont ni lues ni modifiées. Pas de page OCR : la voie OCR n'est pas exercée ici.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
import yaml

from .artifacts import runtime_location
from .profile_setup import user_profile
from .resources import admission_requirement
from .supervisor import app_origin, control_headers, data_path, load_profile, start, status, stop
from .verdict import mib

PASS, FAIL, SKIPPED = "PASS", "FAIL", "SKIPPED"
JOB_DONE = {"ready", "ready_partial", "error", "cancelled"}


def synthetic_pdf(code: str) -> bytes:
    return text_pdf(["Contrôle de l'atelier documentaire.", f"La pression nominale du banc {code} est de 3,1 bar.",
                     f"Le couple de serrage du banc {code} est de 12 N.m."])


def text_pdf(lines: list[str]) -> bytes:
    """Une page de texte natif (Helvetica, WinAnsi) sans second analyseur PDF, comme les essais d'extraction réelle."""
    content = "BT /F1 14 Tf 50 700 Td 22 TL " + " ".join(f"<{line.encode('cp1252').hex()}> Tj T*" for line in lines) + " ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content.encode() + b"\nendstream"]
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def free_ports() -> dict[str, int]:
    sockets = [socket.socket() for _ in range(3)]
    try:
        for probe in sockets:
            probe.bind(("127.0.0.1", 0))
        return dict(zip(("app", "qdrant", "ollama"), (probe.getsockname()[1] for probe in sockets), strict=True))
    finally:
        for probe in sockets:
            probe.close()


def control_profile(profile_path: Path, root: Path) -> Path:
    """Profil de l'instance de contrôle : données et index dans root, ports libres, verrou lourd partagé avec l'utilisateur."""
    base = load_profile(profile_path)
    profile = user_profile(yaml.safe_load(profile_path.read_text(encoding="utf-8")), root, qdrant_storage=root / "q", ports=free_ports())
    # Le verrou lourd du poste reste commun : extraction ou génération de l'utilisateur et du contrôle ne se chevauchent pas.
    profile["runtime"]["host_lock_path"] = str(runtime_location(base, "host_lock_path"))
    target = root / "profile.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
    return target


def short_root(prefix: str = "apst") -> Path:
    """Racine courte sous %TEMP% : le stockage Qdrant y tient sous la borne de 57 caractères du binaire Windows."""
    temp = Path(os.environ.get("TEMP") or os.environ.get("TMP") or Path.home())
    for _ in range(16):
        candidate = temp / f"{prefix}{secrets.token_hex(2)}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"Aucune racine de contrôle libre sous {temp}")


def remove_root(root: Path, attempts: int = 10) -> bool:
    """Qdrant peut tenir un fichier de collection quelques instants après son arrêt : la suppression est réessayée."""
    for _ in range(attempts):
        shutil.rmtree(root, ignore_errors=True)
        if not root.exists():
            return True
        time.sleep(1)
    return False


def read_events(client: Any, query_id: str, timeout: float) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    kind = ""
    with client.stream("GET", f"/api/v1/queries/{query_id}/events", params={"after": 0}, timeout=timeout) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((kind, json.loads(line.split(":", 1)[1])))
                if kind in {"done", "error", "cancelled"}:
                    break
    return events


def selftest(profile_path: Path, *, generation: bool = True, keep: bool = False, job_timeout: float = 600, answer_timeout: float = 900) -> dict[str, Any]:
    import httpx

    report: dict[str, Any] = {"utc": datetime.now(UTC).isoformat(), "profile": str(profile_path), "steps": []}

    def step(name: str, action: Callable[[], str]) -> bool:
        started = time.perf_counter()
        try:
            detail, outcome = action(), PASS
        except _Skipped as skipped:
            detail, outcome = str(skipped), SKIPPED
        except Exception as error:  # noqa: BLE001 - chaque échec devient une étape lisible du rapport
            detail, outcome = f"{type(error).__name__}: {error}", FAIL
        report["steps"].append({"step": name, "status": outcome, "seconds": round(time.perf_counter() - started, 1), "detail": detail})
        return outcome != FAIL

    root = short_root()
    report["root"] = str(root)
    context: dict[str, Any] = {"code": "AUTOTEST-" + secrets.token_hex(3).upper()}
    try:
        def prepare() -> str:
            context["profile"] = control_profile(profile_path, root)
            return f"racine {root}, ports {load_profile(context['profile'])['app']['port']} et suivants"

        def launch() -> str:
            state = start(context["profile"])
            if state.get("status") != "running":
                raise RuntimeError(f"instance de contrôle à l'état {state.get('status')}")
            return f"instance {state.get('instance_id')} démarrée"

        if step("préparation", prepare) and step("démarrage", launch):
            profile = load_profile(context["profile"])
            origin, verify = app_origin(profile)
            headers = {"Origin": origin, **control_headers(data_path(profile))}
            with httpx.Client(base_url=origin, headers=headers, timeout=60, trust_env=False, verify=verify) as client:
                def import_pdf() -> str:
                    response = client.post("/api/v1/documents/import", files={"files": ("controle-atelier.pdf", synthetic_pdf(context["code"]), "application/pdf")})
                    response.raise_for_status()
                    context.update(response.json()["imports"][0])
                    return f"document {context['document_id']}, traitement {context['job_id']}"

                def extract() -> str:
                    deadline = time.monotonic() + job_timeout
                    while time.monotonic() < deadline:
                        jobs = client.get("/api/v1/jobs", params={"limit": 20}).json()["jobs"]
                        job = next(item for item in jobs if item["id"] == context["job_id"])
                        if job["state"] in JOB_DONE:
                            if job["state"] != "ready" or not job.get("active"):
                                raise RuntimeError(f"traitement {job['state']} ({job.get('error_code') or 'non publié'})")
                            return "extraction native publiée"
                        time.sleep(2)
                    raise TimeoutError(f"extraction non terminée en {job_timeout:.0f} s")

                def search() -> str:
                    response = client.post("/api/v1/search", json={"question": f"pression nominale {context['code']}", "scope": {"kind": "library"}})
                    response.raise_for_status()
                    found = next((source for source in response.json()["top10"] if source["document_id"] == context["document_id"]
                                  and context["code"] in source["text"] and "3,1 bar" in source["text"]), None)
                    if not found:
                        raise RuntimeError("passage attendu absent des dix premiers résultats")
                    context["source"] = found
                    return f"passage retrouvé page {found['page_number']}"

                def provenance() -> str:
                    page = client.get(f"/api/v1/versions/{context['version_id']}/pages/{context['source']['page_index']}/blocks").json()
                    known = {block["id"]: block for block in page["blocks"]}
                    cited = [block["id"] for block in context["source"]["blocks"]]
                    if not cited or any(block_id not in known or not known[block_id].get("bbox") for block_id in cited):
                        raise RuntimeError("bloc du passage absent de la page ou sans boîte")
                    return f"{len(cited)} bloc(s) localisé(s) sur la page {context['source']['page_number']}"

                def answer() -> str:
                    requirement = admission_requirement(profile.get("resources", {}), "generation")
                    available = psutil.virtual_memory().available / 1048576
                    if not generation:
                        raise _Skipped("génération non demandée")
                    if available < requirement["required_available_mib"]:
                        raise _Skipped(f"génération non admise maintenant : {mib(available)} disponibles, "
                                       f"{mib(requirement['required_available_mib'])} requis")
                    created = client.post("/api/v1/queries", json={"question": f"Quelle est la pression nominale du banc {context['code']} ?",
                                                                  "scope": {"kind": "library"}})
                    created.raise_for_status()
                    query_id = created.json()["query_id"]
                    events = read_events(client, query_id, answer_timeout)
                    kind, done = events[-1] if events else ("", {})
                    if kind != "done":
                        raise RuntimeError(f"question terminée par {kind or 'aucun événement'} : {done.get('message', '')}")
                    citations = done.get("citations") or []
                    if "3,1" not in done.get("text", "") or not citations:
                        raise RuntimeError("réponse sans la valeur attendue ou sans citation")
                    source_id = citations[0] if isinstance(citations[0], str) else citations[0].get("source_id")
                    cited = client.get(f"/api/v1/citations/{query_id}/{source_id}")
                    cited.raise_for_status()
                    return f"réponse citée ({source_id}), citation enregistrée et relue"

                step("import", import_pdf) and step("extraction", extract) and step("recherche", search) and step("provenance", provenance) and step("réponse", answer)
    finally:
        if "profile" in context:
            step("arrêt", lambda: f"instance de contrôle {stop(context['profile']).get('status')}"
                 if status(context["profile"]).get("status") in {"starting", "running", "stopping"} else "instance de contrôle déjà arrêtée")
        report["root_removed"] = keep or remove_root(root)
    failed = [item["step"] for item in report["steps"] if item["status"] == FAIL]
    skipped = [item for item in report["steps"] if item["status"] == SKIPPED]
    report["level"] = "rouge" if failed else ("orange" if skipped else "vert")
    report["summary"] = ("Contrôle réel en échec : " + ", ".join(failed) + "." if failed else
                         "Contrôle réel réussi : import, extraction, recherche et provenance" +
                         (" ; " + skipped[0]["detail"] + "." if skipped else ", réponse citée."))
    return report


class _Skipped(Exception):
    """Étape volontairement non exécutée, avec sa raison."""
