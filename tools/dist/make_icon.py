"""Icône de l'entrée de menu Linux de l'atelier (R26-KIT-04, KIT4-09), générée depuis la marque de l'interface.

La géométrie (tracés, épaisseur, terminaisons et jonctions du trait, cadre de 24 unités) est lue dans le composant
`BrandMark` de `apps/web/src/components/app-topbar.tsx` : une page à coin replié et ses lignes de texte. Les couleurs
sont fixes, car une icône de menu n'hérite d'aucun thème : trait de la teinte primaire du thème clair (rouille
`#A94324`) sur le fond d'accent (`#F8E9DF`), valeurs d'`apps/web/src/app/theme.css`. La pastille claire reste visible
sur un menu sombre et le trait rouille sur un menu clair.

Le fichier produit, `tools/dist/assets/atelier-documentaire.svg`, est versionné et livré dans le kit : l'installateur le
copie à côté du lanceur et l'entrée de menu le désigne par un chemin absolu (clé `Icon` de la Desktop Entry
Specification). Bibliothèque standard seule.

Depuis la racine du dépôt :
    .venv/bin/python -B -m tools.dist.make_icon            écrit l'icône
    .venv/bin/python -B -m tools.dist.make_icon --check    code 1 si l'icône versionnée diffère du rendu
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "apps/web/src/components/app-topbar.tsx"
OUTPUT = "tools/dist/assets/atelier-documentaire.svg"
PRIMARY = "#A94324"
BACKGROUND = "#F8E9DF"
# Taille intrinsèque déclarée pour les moteurs de rendu qui en exigent une (256 × 256, taille des icônes d'application).
SIZE = 256
# Marge autour de la page : le tracé de 24 unités est réduit à 80 % et centré dans la pastille.
SCALE = 0.8


class IconError(ValueError):
    """Géométrie introuvable dans le composant source."""


def brand_geometry(source: str) -> dict[str, Any]:
    """Tracés et réglages du trait de `BrandMark`, lus dans le texte du composant."""
    match = re.search(r"function BrandMark\(\)\s*\{(.*?)</svg>", source, flags=re.S)
    if not match:
        raise IconError(f"Composant BrandMark introuvable dans {SOURCE}")
    block = match.group(1)
    paths = re.findall(r'<path d="([^"]+)"', block)
    settings = {name: re.search(rf'{name}="([^"]+)"', block) for name in ("viewBox", "strokeWidth", "strokeLinecap", "strokeLinejoin")}
    missing = [name for name, found in settings.items() if not found] + ([] if paths else ["path"])
    if missing:
        raise IconError(f"BrandMark sans {', '.join(missing)} dans {SOURCE}")
    values = {name: found.group(1) for name, found in settings.items() if found}
    if values["viewBox"] != "0 0 24 24":
        raise IconError(f"Cadre de BrandMark inattendu ({values['viewBox']}) : 0 0 24 24 attendu")
    return {"paths": paths, "stroke_width": values["strokeWidth"], "linecap": values["strokeLinecap"], "linejoin": values["strokeLinejoin"]}


def render(geometry: dict[str, Any]) -> str:
    offset = round(12 * (1 - SCALE), 3)
    paths = "".join(f'    <path d="{path}"/>\n' for path in geometry["paths"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 24 24">\n'
            "  <title>Atelier documentaire</title>\n"
            f'  <rect x="0.5" y="0.5" width="23" height="23" rx="5" fill="{BACKGROUND}" stroke="{PRIMARY}" stroke-opacity="0.35" '
            'stroke-width="0.5"/>\n'
            f'  <g transform="translate({offset} {offset}) scale({SCALE})" fill="none" stroke="{PRIMARY}" '
            f'stroke-width="{geometry["stroke_width"]}" stroke-linecap="{geometry["linecap"]}" stroke-linejoin="{geometry["linejoin"]}">\n'
            f"{paths}"
            "  </g>\n"
            "</svg>\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Icône de l'entrée de menu Linux, générée depuis BrandMark.")
    parser.add_argument("--check", action="store_true", help="comparer l'icône versionnée au rendu, sans écrire")
    args = parser.parse_args(argv)
    rendered = render(brand_geometry((ROOT / SOURCE).read_text(encoding="utf-8"))).encode("utf-8")
    output = ROOT / OUTPUT
    if args.check:
        if not output.is_file() or output.read_bytes() != rendered:
            print(f"{OUTPUT} diffère du rendu de BrandMark : relancer python -m tools.dist.make_icon", file=sys.stderr)
            return 1
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rendered)
    print(f"{OUTPUT} écrit ({len(rendered)} octets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
