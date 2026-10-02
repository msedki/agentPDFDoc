"""Instance isolée pour les scénarios Playwright qui importent des fixtures (RAG_E2E_IMPORT_ALLOWED=1).

`start` démarre une instance neuve dans une racine et des ports temporaires (mécanismes de `rag.ps1 selftest` et de
`rag.sh selftest`, verrou lourd du poste partagé) et écrit dans --state son origine et le fichier de son jeton de
contrôle ; la bibliothèque de l'utilisateur n'est jamais la cible. `stop` arrête cette instance et supprime sa racine.

`--profile` choisit le profil de base (par défaut `config/local16.yaml`) : une copie en `llm.accelerator: cpu` pour une
génération sur CPU, ou le profil d'une instance créée par `init-profile`. Racine, données, ports et stockage Qdrant
sont toujours remplacés ; le verrou lourd est celui du profil de base, partagé avec l'instance qu'il décrit.

Windows (PowerShell) :

    .venv\\Scripts\\python.exe tools/qualification/e2e_instance.py start --state <etat.json> [--profile <profil.yaml>]
    $env:RAG_E2E_BASE_URL = <origin> ; $env:RAG_E2E_CONTROL_TOKEN_FILE = <token_file> ; $env:RAG_E2E_IMPORT_ALLOWED = '1'
    .venv\\Scripts\\python.exe tools/qualification/e2e_instance.py stop --state <etat.json>

Linux (shell POSIX, depuis la racine du projet) :

    .venv/bin/python tools/qualification/e2e_instance.py start --state <etat.json> [--profile <profil.yaml>]
    export RAG_E2E_BASE_URL=<origin> RAG_E2E_CONTROL_TOKEN_FILE=<token_file> RAG_E2E_IMPORT_ALLOWED=1
    .venv/bin/python tools/qualification/e2e_instance.py stop --state <etat.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.selftest import control_profile, remove_root, short_root  # noqa: E402
from services.runtime.supervisor import app_origin, data_path, load_profile, start, status, stop  # noqa: E402

DELIVERED_PROFILE = ROOT / "config/local16.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--max-file-mib", type=float, help="taille maximale d'un PDF importé (essai du refus de taille)")
    parser.add_argument("--profile", type=Path, help="start : profil de base de l'instance isolée (config/local16.yaml par défaut)")
    args = parser.parse_args()
    if args.action == "stop" and args.profile:
        parser.error("--profile ne sert qu'à start : stop reprend le profil enregistré dans --state")
    base = args.profile or DELIVERED_PROFILE
    if args.action == "start":
        if not base.is_file():
            parser.error(f"Profil de base introuvable : {base}")
        root = short_root("ape")
        profile_path = control_profile(base, root)
        if args.max_file_mib:
            settings = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            settings["pdf"]["max_file_mib"] = args.max_file_mib
            profile_path.write_text(yaml.safe_dump(settings, allow_unicode=True, sort_keys=False), encoding="utf-8")
        state = start(profile_path)
        profile = load_profile(profile_path)
        result = {"status": state.get("status"), "root": str(root), "profile": str(profile_path), "origin": app_origin(profile)[0],
                  "token_file": str(data_path(profile) / "control" / "admin-token"),
                  "base_profile": {"file": base.name, "sha256": hashlib.sha256(base.read_bytes()).hexdigest()}}
    else:
        saved = json.loads(args.state.read_text(encoding="utf-8"))
        profile_path, root = Path(saved["profile"]), Path(saved["root"])
        stopped = stop(profile_path).get("status") if status(profile_path).get("status") in {"starting", "running", "stopping"} else "already_stopped"
        result = {**saved, "status": stopped, "root_removed": remove_root(root)}
    args.state.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"running", "stopped", "already_stopped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
