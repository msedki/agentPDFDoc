"""Contrôle hors ligne de l'espace documentaire : README.md, CHANGELOG.md et docs/.

Depuis la racine du dépôt :

    .venv\\Scripts\\python.exe tools/docs/check_docs.py [--report <nouveau-fichier.json>]

Contrôles, chacun PASS ou FAIL (code de sortie 1 si l'un échoue) :

- links : liens Markdown relatifs résolus (fichier, puis ancre pour un .md), jamais vers .runtime/,
  .git/, hors du dépôt ni vers un chemin ignoré par Git ;
- headers : en-tête de chaque document de docs/ (Rôle, Statut parmi Stabilisé, Vivant, Historique,
  Généré, Référence, Mis à jour AAAA-MM-JJ UTC, Source de vérité, Remplace ou Remplacé par) ;
- index : chaque document de docs/ figure dans docs/README.md avec le statut de son en-tête ;
- ascii_art : aucun caractère de dessin de boîte hors blocs de code, aucune arborescence dessinée
  ni bloc Mermaid dans un bloc de code ;
- images : aucune image distante ; SVG référencés présents et bien formés, fond explicite, titre et
  description, police effective d'au moins 11 px pour un affichage de 880 px de large, sans script
  ni ressource externe ; aucun SVG de docs/assets/ laissé sans référence ;
- versions : même version dans pyproject.toml et apps/web/package.json ; CHANGELOG ouvert par
  [Non publié], mentionnant cette version, sans section de version absente des étiquettes Git ;
- entry_point : le README racine a un titre, un sommaire et renvoie vers docs/README.md et CHANGELOG.md.

Aucune URL n'est ouverte ; Git n'est appelé qu'en lecture (check-ignore, tag -l).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("stabilise", "vivant", "historique", "genere")
HEADER_FIELDS = ("role", "statut", "reference", "mis a jour", "source de verite")
DISPLAY_WIDTH = 880
MIN_DISPLAY_FONT = 11.0
SVG = "{http://www.w3.org/2000/svg}"
BOX_DRAWING = re.compile("[─-╿]")
TREE_LINE = re.compile(r"^[\s│|]*[├└]─")
LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FIELD = re.compile(r"\*\*([^*]+?)\s*:\s*\*\*\s*(.*?)(?=\s+·\s+\*\*|$)")


class Fault(AssertionError):
    """Écart documentaire : message destiné au rapport."""


def fold(text: str) -> str:
    """Minuscules sans diacritiques, pour comparer des libellés français."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower().strip()


def documents(root: Path) -> list[Path]:
    found = [root / name for name in ("README.md", "CHANGELOG.md") if (root / name).is_file()]
    docs = root / "docs"
    if docs.is_dir():
        found += sorted(docs.rglob("*.md"))
    return found


def docs_documents(root: Path) -> list[Path]:
    docs = root / "docs"
    return sorted(docs.rglob("*.md")) if docs.is_dir() else []


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def split_code(text: str) -> tuple[list[tuple[int, str]], list[tuple[str, int, list[str]]]]:
    """Lignes de prose (numérotées) et blocs de code (langage, première ligne, contenu)."""
    prose, blocks = [], []
    active: tuple[str, str, int, list[str]] | None = None
    for number, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line)
        if active is None and fence:
            active = (fence.group(1)[0], fence.group(2).lower(), number, [])
        elif active is not None and fence and fence.group(1)[0] == active[0] and not fence.group(2):
            blocks.append((active[1], active[2], active[3]))
            active = None
        elif active is not None:
            active[3].append(line)
        else:
            prose.append((number, line))
    if active is not None:
        raise Fault(f"bloc de code ouvert ligne {active[2]} et jamais fermé")
    return prose, blocks


def without_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def slug(heading: str) -> str:
    """Ancre produite par GitHub pour un titre Markdown."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text.replace("`", ""))
    text = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    prose, _ = split_code(path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    result = set()
    for _, line in prose:
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def links(path: Path) -> list[tuple[int, bool, str]]:
    """(ligne, image ?, cible) des liens Markdown et images HTML hors code."""
    prose, _ = split_code(path.read_text(encoding="utf-8"))
    found = []
    for number, line in prose:
        visible = without_inline_code(line)
        found += [(number, bool(match.group(1)), match.group(3)) for match in LINK.finditer(visible)]
        found += [(number, True, target) for target in HTML_IMAGE.findall(visible)]
    return found


def git(root: Path, *arguments: str, stdin: str | None = None) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], input=stdin, capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_reason(root: Path) -> str | None:
    """None si `root` est la racine de son propre dépôt Git ; sinon le motif pour ne pas interroger Git.

    Un dossier contrôlé à l'intérieur d'un autre dépôt (fixture de test sous .runtime/) ne doit pas
    hériter des règles d'exclusion ni des étiquettes de ce dépôt englobant.
    """
    process = git(root, "rev-parse", "--show-toplevel")
    if process is None:
        return "git indisponible"
    if process.returncode != 0:
        return "racine hors dépôt Git"
    if Path(process.stdout.strip()).resolve() != root.resolve():
        return "racine incluse dans un autre dépôt Git"
    return None


def git_ignored(root: Path, paths: list[str]) -> tuple[set[str] | None, str | None]:
    if not paths:
        return set(), None
    reason = git_reason(root)
    if reason:
        return None, reason
    process = git(root, "check-ignore", "-z", "--stdin", stdin="\0".join(paths) + "\0")
    if process is None:
        return None, "git indisponible"
    if process.returncode not in (0, 1):
        return None, f"git check-ignore code {process.returncode}"
    return set(filter(None, process.stdout.split("\0"))), None


# -- contrôles -------------------------------------------------------------------------------

def check_links(root: Path) -> dict:
    root = root.resolve()
    faults, targets, checked, warnings = [], [], 0, []
    anchor_cache: dict[Path, set[str]] = {}
    for document in documents(root):
        name = relative(root, document)
        try:
            found = links(document)
        except Fault as exc:
            faults.append(f"{name} : {exc}")
            continue
        for number, _, target in found:
            if urlsplit(target).scheme:
                continue
            checked += 1
            where = f"{name}:{number} → {target}"
            path_part, _, anchor = target.partition("#")
            destination = (document.parent / unquote(path_part)).resolve() if path_part else document
            if not destination.is_relative_to(root):
                faults.append(f"lien hors dépôt : {where}")
                continue
            if destination.is_relative_to(root / ".runtime") or destination.is_relative_to(root / ".git"):
                faults.append(f"lien vers .runtime/ ou .git/ : {where}")
                continue
            if not destination.exists():
                faults.append(f"cible absente : {where}")
                continue
            targets.append((relative(root, destination), where))
            if anchor and destination.suffix.lower() == ".md":
                if destination not in anchor_cache:
                    anchor_cache[destination] = anchors(destination)
                if unquote(anchor) not in anchor_cache[destination]:
                    faults.append(f"ancre absente : {where}")
    ignored, reason = git_ignored(root, sorted({path for path, _ in targets if path}))
    if reason:
        warnings.append(f"contrôle git check-ignore NOT_RUN : {reason}")
    elif ignored:
        faults += [f"cible ignorée par Git : {where}" for path, where in targets if path in ignored]
    if faults:
        raise Fault(f"{len(faults)} lien(s) fautif(s) : " + " | ".join(faults))
    return {"relative_links_checked": checked, "warnings": warnings, "external_urls_fetched": False}


def header_fields(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((index for index, line in enumerate(lines) if line.startswith("# ")), None)
    if title is None:
        raise Fault("titre de niveau 1 absent")
    header = next((line for line in lines[title + 1:] if line.strip()), "")
    return {fold(key): value.strip() for key, value in FIELD.findall(header)}


def check_headers(root: Path) -> dict:
    faults, statuses = [], {}
    for document in docs_documents(root):
        name = relative(root, document)
        try:
            fields = header_fields(document)
        except Fault as exc:
            faults.append(f"{name} : {exc}")
            continue
        missing = [field for field in HEADER_FIELDS if field not in fields]
        if not any(key in fields for key in ("remplace", "remplace par")):
            missing.append("remplace ou remplacé par")
        if missing:
            faults.append(f"{name} : champ(s) d'en-tête absent(s) : {', '.join(missing)}")
            continue
        status = re.sub(r"[^a-z]", " ", fold(fields["statut"])).split()
        if not status or status[0] not in STATUSES:
            faults.append(f"{name} : statut « {fields['statut']} » hors de Stabilisé, Vivant, Historique, Généré")
        else:
            statuses[name] = status[0]
        stamp = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", fields["mis a jour"])
        try:
            valid = stamp is not None and bool(date(*map(int, stamp.groups()))) and "UTC" in fields["mis a jour"]
        except ValueError:
            valid = False
        if not valid:
            faults.append(f"{name} : « Mis à jour » attend AAAA-MM-JJ et UTC : {fields['mis a jour']!r}")
    if faults:
        raise Fault(" | ".join(faults))
    return {"documents": len(statuses), "statuses": statuses}


def check_index(root: Path) -> dict:
    index = root / "docs" / "README.md"
    if not index.is_file():
        raise Fault("docs/README.md absent")
    listed: dict[str, str] = {}
    prose, _ = split_code(index.read_text(encoding="utf-8"))
    for _, line in prose:
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = LINK.search(without_inline_code(cells[0])) if cells else None
        if not match or len(cells) < 3 or urlsplit(match.group(3)).scheme:
            continue
        target = (index.parent / unquote(match.group(3).partition("#")[0])).resolve()
        if target.suffix.lower() == ".md" and target.is_relative_to((root / "docs").resolve()):
            words = re.sub(r"[^a-z]", " ", fold(cells[2])).split()
            listed[relative(root.resolve(), target)] = words[0] if words else ""
    faults = []
    for document in docs_documents(root):
        name = relative(root, document)
        if document.resolve() == index.resolve():
            continue
        if name not in listed:
            faults.append(f"{name} absent de l'index docs/README.md")
            continue
        status = re.sub(r"[^a-z]", " ", fold(header_fields(document).get("statut", ""))).split()
        if status and listed[name] != status[0]:
            faults.append(f"{name} : statut de l'index « {listed[name]} » différent de l'en-tête « {status[0]} »")
    if faults:
        raise Fault(" | ".join(faults))
    return {"indexed_documents": len(listed)}


def check_ascii_art(root: Path) -> dict:
    faults, blocks_checked = [], 0
    for document in documents(root):
        name = relative(root, document)
        try:
            prose, blocks = split_code(document.read_text(encoding="utf-8"))
        except Fault as exc:
            faults.append(f"{name} : {exc}")
            continue
        faults += [f"{name}:{number} : caractère de dessin de boîte hors bloc de code"
                   for number, line in prose if BOX_DRAWING.search(without_inline_code(line))]
        for language, start, lines in blocks:
            blocks_checked += 1
            if language == "mermaid":
                faults.append(f"{name}:{start} : bloc Mermaid (utiliser un SVG généré)")
            faults += [f"{name}:{start + offset + 1} : arborescence dessinée dans un bloc de code"
                       for offset, line in enumerate(lines) if TREE_LINE.match(line)]
    if faults:
        raise Fault(" | ".join(faults))
    return {"code_blocks_checked": blocks_checked}


def svg_faults(path: Path) -> list[str]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return [f"XML mal formé ({exc})"]
    svg = tree.getroot()
    if svg.tag != SVG + "svg":
        return ["élément racine différent de <svg> (espace de noms SVG requis)"]
    # L'analyseur XML normalise les retours chariot : on les cherche dans les octets.
    faults = ["retour chariot (CR) présent : fichier attendu en LF"] if b"\r" in path.read_bytes() else []
    try:
        _, _, box_width, box_height = (float(value) for value in svg.get("viewBox", "").replace(",", " ").split())
    except ValueError:
        return ["viewBox absent ou invalide"]
    for tag, label in (("title", "titre"), ("desc", "description")):
        element = svg.find(SVG + tag)
        if element is None or not (element.text or "").strip():
            faults.append(f"<{tag}> ({label}) absent")
    first = next((child for child in svg if child.tag not in {SVG + "title", SVG + "desc", SVG + "defs"}), None)
    try:
        covered = (first is not None and first.tag == SVG + "rect"
                   and float(first.get("x", 0)) <= 1 and float(first.get("y", 0)) <= 1
                   and float(first.get("width", 0)) >= box_width - 2 and float(first.get("height", 0)) >= box_height - 2
                   and first.get("fill", "none").lower() not in {"none", "transparent"})
    except ValueError:
        covered = False
    if not covered:
        faults.append("fond explicite absent (premier élément : rectangle plein couvrant le viewBox)")
    parents = {child: parent for parent in svg.iter() for child in parent}
    scale = min(1.0, DISPLAY_WIDTH / box_width)
    for element in svg.iter():
        local = element.tag.removeprefix(SVG)
        if local in {"script", "foreignObject"}:
            faults.append(f"élément <{local}> interdit")
        for key, value in element.attrib.items():
            if key.endswith("href") and urlsplit(value).scheme:
                faults.append(f"ressource externe {value}")
        if local != "text":
            continue
        node, size = element, None
        while node is not None and size is None:
            size = node.get("font-size")
            node = parents.get(node)
        try:
            effective = float(str(size).removesuffix("px")) * scale
        except ValueError:
            faults.append(f"texte sans taille de police : {element.text!r}")
            continue
        if effective < MIN_DISPLAY_FONT:
            faults.append(f"texte de {effective:.1f} px affiché (< {MIN_DISPLAY_FONT:g}) : {element.text!r}")
    return faults


def check_images(root: Path) -> dict:
    root = root.resolve()
    faults, referenced = [], set()
    for document in documents(root):
        name = relative(root, document)
        try:
            found = links(document)
        except Fault as exc:
            faults.append(f"{name} : {exc}")
            continue
        for number, image, target in found:
            if not image:
                continue
            if urlsplit(target).scheme:
                faults.append(f"{name}:{number} : image distante interdite ({target})")
                continue
            path = (document.parent / unquote(target.partition("#")[0])).resolve()
            if path.suffix.lower() != ".svg":
                continue
            referenced.add(path)
            if not path.is_file():
                faults.append(f"{name}:{number} : SVG absent ({target})")
                continue
            faults += [f"{relative(root, path)} : {fault}" for fault in svg_faults(path)]
    assets = root / "docs" / "assets"
    orphans = sorted(relative(root, path) for path in assets.rglob("*.svg") if path.resolve() not in referenced) \
        if assets.is_dir() else []
    faults += [f"{path} : SVG jamais référencé" for path in orphans]
    if faults:
        raise Fault(" | ".join(dict.fromkeys(faults)))
    return {"svg_checked": len(referenced), "display_width_px": DISPLAY_WIDTH, "min_display_font_px": MIN_DISPLAY_FONT}


def check_versions(root: Path) -> dict:
    python_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    web_version = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))["version"]
    if python_version != web_version:
        raise Fault(f"pyproject.toml {python_version} différent de apps/web/package.json {web_version}")
    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        raise Fault("CHANGELOG.md absent")
    prose, _ = split_code(changelog.read_text(encoding="utf-8"))
    sections = [match.group(2) for _, line in prose if (match := HEADING.match(line)) and len(match.group(1)) == 2]
    if not sections or "non publie" not in fold(sections[0]):
        raise Fault("CHANGELOG.md doit s'ouvrir sur la section [Non publié]")
    if python_version not in changelog.read_text(encoding="utf-8"):
        raise Fault(f"CHANGELOG.md ne mentionne pas la version déclarée {python_version}")
    released = [match.group(1) for section in sections[1:] if (match := re.match(r"\[(\d+\.\d+\.\d+[^\]]*)\]", section))]
    warnings = []
    if released:
        process = None if git_reason(root) else git(root, "tag", "-l")
        if process is None or process.returncode != 0:
            warnings.append("étiquettes Git illisibles : sections publiées non vérifiées")
        else:
            tags = set(process.stdout.split())
            missing = [version for version in released if version not in tags and f"v{version}" not in tags]
            if missing:
                raise Fault("version(s) publiée(s) sans étiquette Git : " + ", ".join(missing))
    return {"version": python_version, "released_sections": released, "warnings": warnings}


def check_entry_point(root: Path) -> dict:
    readme = root / "README.md"
    if not readme.is_file():
        raise Fault("README.md racine absent")
    lines = readme.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise Fault("README.md doit commencer par un titre de niveau 1")
    prose, _ = split_code("\n".join(lines))
    if not any(fold(line) in {"## sommaire"} for _, line in prose):
        raise Fault("README.md sans section « Sommaire »")
    targets = {(readme.parent / unquote(target.partition("#")[0])).resolve()
               for _, _, target in links(readme) if not urlsplit(target).scheme and target.partition("#")[0]}
    missing = [name for name in ("docs/README.md", "CHANGELOG.md") if (root / name).resolve() not in targets]
    if missing:
        raise Fault("README.md ne renvoie pas vers " + ", ".join(missing))
    return {"entry_links": ["docs/README.md", "CHANGELOG.md"]}


CHECKS: dict[str, Callable[[Path], dict]] = {
    "links": check_links, "headers": check_headers, "index": check_index, "ascii_art": check_ascii_art,
    "images": check_images, "versions": check_versions, "entry_point": check_entry_point,
}


def run(root: Path = ROOT) -> dict:
    results = []
    for name, check in CHECKS.items():
        try:
            results.append({"id": name, "status": "PASS", "detail": check(root)})
        except (Fault, OSError, ValueError, KeyError) as exc:
            results.append({"id": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
    return {"utc": datetime.now(UTC).isoformat(timespec="seconds"), "root": str(root),
            "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
            "checks": results, "network": "none"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="nouveau fichier JSON (jamais écrasé)")
    args = parser.parse_args(argv)
    result = run(args.root.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text + "\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console Windows : accents du rapport
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
