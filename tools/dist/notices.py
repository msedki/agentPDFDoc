"""Avis de tiers du kit (DIST-07) : composants, licences déclarées par les verrous, textes présents et manques connus.

Source de vérité : `config/artifacts.lock.json` (licence, éditeur et source de chaque artefact) ; les textes de licence
sont ceux qui figurent réellement dans le kit. Usage interne selon W030, sans validation juridique ni redistribution
hors de l'organisation ; les manques connus restent déclarés.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.runtime.platforms import entries_for_platform

# Nom qui porte le mot comme élément distinct : LICENSE, LICENSE.txt, LLAMA_CPP_LICENSE, DLFCN_WIN32_COPYING, XGRAMMAR_NOTICE.
LICENSE_FILE = re.compile(r"(?i)(^|[-_.])(licen[cs]es?|notices?|copying|copyright|third[-_ ]?party[-_ ]?notices?)([-_.]|$)")


def license_files(files: list[str], prefix: str) -> list[str]:
    prefix = prefix.rstrip("/") + "/"
    return [name for name in files if name.startswith(prefix) and LICENSE_FILE.search(name.rsplit("/", 1)[-1])]


def artifact_rows(lock: dict[str, Any], files: list[str], platform: str = "windows-x86_64") -> list[dict[str, Any]]:
    """Une ligne par composant et version ; les textes de licence sont cherchés dans les dossiers de ses fichiers.

    Seules les entrées de la plateforme du kit sont livrées, selon la règle du provisionnement (`entries_for_platform` :
    sans champ `platform`, partout ; sinon la plateforme nommée ou l'une de celles listées).
    """
    present = set(files)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for group, entries in lock["groups"].items():
        for entry in entries_for_platform(entries if isinstance(entries, list) else [entries], platform):
            location = str(entry.get("extract_to") or entry.get("target") or "").strip("/")
            folder = location.rsplit("/", 1)[0] if location in present else location
            key = (str(entry.get("model_id") or group), str(entry.get("version") or entry.get("revision") or ""))
            row = rows.setdefault(key, {"component": key[0], "version": key[1], "publisher": entry.get("publisher", ""),
                                        "license": entry.get("license", "non déclarée"), "source": entry.get("url", ""), "texts": []})
            row["texts"] += [name for name in (license_files(files, folder) if folder else []) if name not in row["texts"]]
    return list(rows.values())


# Manques propres aux kits Linux (R26-KIT-01) : constatés sur le contenu livré, non résolus par le kit.
LINUX_GAPS = ("texte de licence d'uv absent : `bootstrap.sh` n'extrait que les exécutables `uv` et `uvx` de l'archive officielle",
              "Tesseract et Leptonica construits depuis les sources verrouillées et liés aux bibliothèques du système "
              "(libjpeg, libpng, libtiff, zlib…), non livrées : leurs licences relèvent de la distribution du poste")
JETPACK5_GAP = ("conditions de licence NVIDIA (CUDA 11.4, cuBLAS) des bibliothèques du complément JetPack 5 d'Ollama "
                "(`lib/ollama/cuda_jetpack5`), livrées sans texte de licence propre")
# Manques communs relevés par l'analyse de distribution, propres à aucune plateforme. Le kit Windows garde son texte
# (DLL de la copie Tesseract, bibliothèques CUDA de l'archive Windows d'Ollama) ; le kit Linux n'en reprend que ce qui le
# concerne, sans renvoi à une section d'un document du dépôt qu'il ne livre pas (KIT4-29).
COMMON_GAPS = ("texte de licence propre à Qdrant et à Ollama absent des archives officielles", "titulaire du copyright d'E5",
               "textes Apache-2.0 de Docling Heron et CDLA-Permissive-2.0 de TableFormer à joindre",
               "avis des paquets npm regroupés dans les scripts de l'interface")
QWEN_4B_SECTION = ["## Modification du modèle Qwen3.5-4B", "",
                   "Le modèle `qwen3.5:4b-text` livré est dérivé localement du modèle Qwen3.5-4B publié sous licence Apache-2.0 : les "
                   "tenseurs de l'encodeur de vision (`v.*`, `mm.*`) ont été retirés, les autres tenseurs sont repris à l'identique et "
                   "vérifiés un à un (décision W006 du projet). Cette mention répond à l'obligation de signaler les fichiers modifiés "
                   "(Apache-2.0, section 4 b).", ""]


def third_party_notices(root: Path, files: list[str], version: str, platform: str = "windows-x86_64", *,
                        lock: dict[str, Any] | None = None, gpu: str | None = None, models: tuple[str, ...] | None = None) -> str:
    """`lock` : verrou lu dans le commit du kit (kit Linux) ; à défaut, celui de l'arbre de travail (kit Windows).

    `models` : jeux de modèles livrés (`model_sets` du kit Linux) ; la mention de la modification du 4B ne figure que si
    `4b` en fait partie. Sans valeur (kit Windows), elle figure toujours. Le texte du kit Windows est inchangé."""
    if lock is None:
        lock = json.loads((root / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    rows = artifact_rows(lock, files, platform)
    lines = [f"# Avis de tiers — Atelier documentaire {version}", "",
             "Composants livrés par ce kit, avec la licence déclarée par le verrou du projet (`config/artifacts.lock.json`) et les textes "
             "de licence effectivement présents dans le kit. Ce document n'est pas un avis juridique. Le projet est d'usage interne, "
             "sans redistribution hors de l'organisation (décision W030). Les manques connus restent listés en fin de document. "
             "Une redistribution hors de l'organisation rouvrirait le contrôle des licences et avis manquants.", "",
             "| Composant | Version ou révision | Éditeur | Licence déclarée | Source | Textes présents dans le kit |", "|---|---|---|---|---|---|"]
    for row in rows:
        texts = "<br>".join(f"`{name}`" for name in row["texts"]) or "aucun"
        lines.append(f"| {row['component']} | {row['version']} | {row['publisher']} | {row['license']} | {row['source']} | {texts} |")
    tesseract = "Tesseract et Leptonica (construits depuis les sources)" if platform.startswith("linux") else "Tesseract (copie locale)"
    bundled = {"CPython (python-build-standalone)": ".runtime/python", "uv": ".runtime/bootstrap", tesseract: ".runtime/bin/tesseract-5.4.0",
               "Interface (PDF.js et paquets regroupés)": "apps/web/out"}
    for name, prefix in bundled.items():
        present = license_files(files, prefix)
        lines.append(f"| {name} | — | — | voir les textes | — | {'<br>'.join(f'`{t}`' for t in present) or 'aucun'} |")
    lines += ["", "Les paquets Python du runtime apportent leurs avis dans leurs métadonnées (`*.dist-info`) ; ils arrivent avec le cache uv "
              "du kit puis dans `.venv` à l'installation.", ""]
    lines += QWEN_4B_SECTION if models is None or "4b" in models else []
    lines += ["## Manques connus", ""]
    if not platform.startswith("linux"):
        lines += ["Relevés par l'analyse de distribution (section 6), non résolus par ce kit : texte de licence propre à Qdrant et à Ollama "
                  "absent des archives officielles ; licences des DLL tierces de la copie Tesseract ; titulaire du copyright d'E5 ; textes "
                  "Apache-2.0 de Docling Heron et CDLA-Permissive-2.0 de TableFormer à joindre ; avis des paquets npm regroupés dans les "
                  "scripts de l'interface ; conditions NVIDIA des bibliothèques CUDA d'Ollama tant qu'elles sont livrées (P3)."]
        return "\n".join(lines) + "\n"
    gaps = (*COMMON_GAPS, *LINUX_GAPS, *((JETPACK5_GAP,) if gpu == "jetpack5" else ()))
    lines += ["Manques relevés par l'analyse de distribution, document du dépôt du projet, non livré avec ce kit. Ils ne sont pas "
              "résolus par ce kit :", ""] + [f"- {gap}." for gap in gaps]
    return "\n".join(lines) + "\n"
