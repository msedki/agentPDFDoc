"""Importe un dossier de PDF/DOCX/XLSX dans l'instance, en conservant son arborescence.

Chaque fichier est envoyé seul à `POST /api/v1/documents/import` de l'API loopback ;
l'API copie l'original dans son stockage géré (l'original du dossier n'est ni
modifié ni déplacé) et crée le job d'extraction. Les fichiers sont envoyés du plus
petit au plus grand pour rendre des documents consultables tôt. Les fichiers qui ne
sont pas des PDF/DOCX/XLSX sont recensés sans être envoyés.

Le rapport contient les chemins relatifs du corpus : l'écrire hors du dépôt
(par défaut sous `.runtime/qa/`). Aucun texte de document n'est lu ni affiché.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.platforms import launcher_command  # noqa: E402
from services.runtime.supervisor import app_origin, control_headers, data_path, load_profile  # noqa: E402

FORMATS = {".pdf": "application/pdf",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def import_folder(source: Path, base_url: str, *, headers: dict[str, str] | None = None, verify: str | bool = True,
                  pause_seconds: float = 0.2) -> dict:
    files = sorted((path for path in source.rglob("*") if path.is_file()), key=lambda path: (path.stat().st_size, str(path)))
    documents = [path for path in files if path.suffix.lower() in FORMATS]
    report: dict[str, Any] = {"started_utc": dt.datetime.now(dt.UTC).isoformat(), "source": str(source), "base_url": base_url,
                              "files_seen": len(files), "pdf_files": sum(path.suffix.lower() == ".pdf" for path in documents),
                              "document_files": len(documents),
                              "skipped_not_pdf": [path.relative_to(source).as_posix() for path in files if path.suffix.lower() != ".pdf"],
                              "skipped_unsupported": [path.relative_to(source).as_posix() for path in files if path.suffix.lower() not in FORMATS],
                              "results": []}
    origin = base_url.rstrip("/")
    with httpx.Client(base_url=origin, headers={"Origin": origin, **(headers or {})}, timeout=httpx.Timeout(600, connect=10),
                      trust_env=False, follow_redirects=False, verify=verify) as client:
        for path in documents:
            relative = path.relative_to(source).as_posix()
            started = time.perf_counter()
            with path.open("rb") as handle:
                response = client.post("/api/v1/documents/import", data={"relative_paths": json.dumps([relative])},
                                       files={"files": (path.name, handle, FORMATS[path.suffix.lower()])})
            row = {"relative_path": relative, "bytes": path.stat().st_size, "http_status": response.status_code,
                   "seconds": round(time.perf_counter() - started, 2)}
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if response.is_success:
                item = (payload.get("imports") or [{}])[0]
                row.update({key: item.get(key) for key in ("document_id", "version_id", "job_id", "reused", "job_state")})
            else:
                row.update({"code": payload.get("code"), "message": payload.get("message")})
            report["results"].append(row)
            print(f"{len(report['results'])}/{len(documents)} {response.status_code} {row.get('code') or ('reprise' if row.get('reused') else 'nouveau')}", flush=True)
            time.sleep(pause_seconds)
    report["finished_utc"] = dt.datetime.now(dt.UTC).isoformat()
    report["accepted"] = sum(200 <= row["http_status"] < 300 for row in report["results"])
    report["refused"] = len(report["results"]) - report["accepted"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT / "PDF")
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau rapport JSON hors dépôt (jamais remplacé)")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Rapport existant : choisir un nouveau fichier")
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / ".runtime"):
        raise SystemExit("Le rapport cite les chemins du corpus : l'écrire sous .runtime/ ou hors du dépôt")
    profile = load_profile(args.profile)
    headers = control_headers(data_path(profile))
    if not headers:
        raise SystemExit(f"Jeton de contrôle absent : l'instance du profil doit être démarrée ({launcher_command('up')})")
    origin, verify = app_origin(profile)
    report = import_folder(args.source.resolve(), origin, headers=headers, verify=verify)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"acceptés {report['accepted']}, refusés {report['refused']}, autres formats {len(report['skipped_unsupported'])}")
    return 0 if report["refused"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
