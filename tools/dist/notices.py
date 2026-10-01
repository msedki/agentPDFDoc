"""Avis de tiers du kit (DIST-07) : composants, licences déclarées par les verrous, textes présents et manques connus.

Source de vérité : `config/artifacts.lock.json` (licence, éditeur et source de chaque artefact) ; les textes de licence
sont ceux qui figurent réellement dans le kit. Ce fichier n'est pas un avis juridique : les manques connus restent soumis
à la décision P7 de l'analyse de distribution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Nom qui porte le mot comme élément distinct : LICENSE, LICENSE.txt, LLAMA_CPP_LICENSE, DLFCN_WIN32_COPYING, XGRAMMAR_NOTICE.
LICENSE_FILE = re.compile(r"(?i)(^|[-_.])(licen[cs]es?|notices?|copying|copyright|third[-_ ]?party[-_ ]?notices?)([-_.]|$)")


def license_files(files: list[str], prefix: str) -> list[str]:
    prefix = prefix.rstrip("/") + "/"
    return [name for name in files if name.startswith(prefix) and LICENSE_FILE.search(name.rsplit("/", 1)[-1])]


def artifact_rows(lock: dict[str, Any], files: list[str]) -> list[dict[str, Any]]:
    """Une ligne par composant et version ; les textes de licence sont cherchés dans les dossiers de ses fichiers."""
    present = set(files)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for group, entries in lock["groups"].items():
        for entry in entries if isinstance(entries, list) else [entries]:
            location = str(entry.get("extract_to") or entry.get("target") or "").strip("/")
            folder = location.rsplit("/", 1)[0] if location in present else location
            key = (str(entry.get("model_id") or group), str(entry.get("version") or entry.get("revision") or ""))
            row = rows.setdefault(key, {"component": key[0], "version": key[1], "publisher": entry.get("publisher", ""),
                                        "license": entry.get("license", "non déclarée"), "source": entry.get("url", ""), "texts": []})
            row["texts"] += [name for name in (license_files(files, folder) if folder else []) if name not in row["texts"]]
    return list(rows.values())


def third_party_notices(root: Path, files: list[str], version: str) -> str:
    lock = json.loads((root / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    rows = artifact_rows(lock, files)
    lines = [f"# Avis de tiers — Atelier documentaire {version}", "",
             "Composants livrés par ce kit, avec la licence déclarée par le verrou du projet (`config/artifacts.lock.json`) et les textes "
             "de licence effectivement présents dans le kit. Ce document n'est pas un avis juridique : les manques listés en fin de "
             "document attendent la décision P7 de l'analyse de distribution.", "",
             "| Composant | Version ou révision | Éditeur | Licence déclarée | Source | Textes présents dans le kit |", "|---|---|---|---|---|---|"]
    for row in rows:
        texts = "<br>".join(f"`{name}`" for name in row["texts"]) or "aucun"
        lines.append(f"| {row['component']} | {row['version']} | {row['publisher']} | {row['license']} | {row['source']} | {texts} |")
    bundled = {"CPython (python-build-standalone)": ".runtime/python", "uv": ".runtime/bootstrap", "Tesseract (copie locale)": ".runtime/bin/tesseract-5.4.0",
               "Interface (PDF.js et paquets regroupés)": "apps/web/out"}
    for name, prefix in bundled.items():
        present = license_files(files, prefix)
        lines.append(f"| {name} | — | — | voir les textes | — | {'<br>'.join(f'`{t}`' for t in present) or 'aucun'} |")
    lines += ["", "Les paquets Python du runtime apportent leurs avis dans leurs métadonnées (`*.dist-info`) ; ils arrivent avec le cache uv "
              "du kit puis dans `.venv` à l'installation.", "",
              "## Modification du modèle Qwen3.5-4B", "",
              "Le modèle `qwen3.5:4b-text` livré est dérivé localement du modèle Qwen3.5-4B publié sous licence Apache-2.0 : les tenseurs "
              "de l'encodeur de vision (`v.*`, `mm.*`) ont été retirés, les autres tenseurs sont repris à l'identique et vérifiés un à un "
              "(décision W006 du projet). Cette mention répond à l'obligation de signaler les fichiers modifiés (Apache-2.0, section 4 b).", "",
              "## Manques connus", "",
              "Relevés par l'analyse de distribution (section 6), non résolus par ce kit : texte de licence propre à Qdrant et à Ollama "
              "absent des archives officielles ; licences des DLL tierces de la copie Tesseract ; titulaire du copyright d'E5 ; textes "
              "Apache-2.0 de Docling Heron et CDLA-Permissive-2.0 de TableFormer à joindre ; avis des paquets npm regroupés dans les "
              "scripts de l'interface ; conditions NVIDIA des bibliothèques CUDA d'Ollama tant qu'elles sont livrées (P3)."]
    return "\n".join(lines) + "\n"
