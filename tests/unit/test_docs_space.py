"""Tests de l'espace documentaire (lot R14) : tools/docs/check_docs.py et tools/docs/diagrams.py.

Ils exercent les vraies fonctions sur le dépôt réel, puis sur un projet temporaire minimal
dont on altère un seul point par test pour vérifier que le contrôle concerné échoue, et lui seul.
Aucun réseau ; Git n'est appelé qu'en lecture ou dans le dossier temporaire.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = next(p for p in [*Path(__file__).resolve().parents, Path.cwd()]
               if (p / "tools" / "docs" / "check_docs.py").is_file())
sys.path.insert(0, str(PROJECT / "tools" / "docs"))

import check_docs  # noqa: E402
import diagrams  # noqa: E402

GIT = shutil.which("git")

HEADER = ("**Rôle :** exemple · **Propriétaire :** documentation · **Statut :** Stabilisé · **Référence :** commit `abc1234` · "
          "**Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** code · **Remplace :** aucun document")

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="880" height="100" viewBox="0 0 880 100">
<title>Schéma</title>
<desc>Ce que montre le schéma.</desc>
<rect x="0" y="0" width="880" height="100" fill="#F6F4EE"/>
<text x="20" y="40" font-size="12">Texte lisible</text>
</svg>
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture
def space(tmp_path: Path) -> Path:
    """Projet minimal conforme : README, CHANGELOG, index, un document, un SVG, deux versions."""
    root = tmp_path / "projet"
    write(root / "README.md", "# Projet\n\nAccroche.\n\n## Sommaire\n\n- [1. Vue](#1-vue-densemble)\n\n"
                              "## 1. Vue d'ensemble\n\nVoir [la documentation](docs/README.md), "
                              "[les changements](CHANGELOG.md) et [l'exploitation](docs/exploitation/A.md#2-démarrer).\n\n"
                              "![Schéma](docs/assets/diagrams/a.svg)\n")
    write(root / "CHANGELOG.md", "# Journal\n\nVersion déclarée : 0.1.0.\n\n## [Non publié]\n\n### Ajouté\n\n- Entrée.\n")
    write(root / "docs/README.md", f"# Index\n\n{HEADER}\n\n| Document | Rôle | Statut | Source de vérité |\n"
                                   "|---|---|---|---|\n| [A](exploitation/A.md) | Procédure | Stabilisé | code |\n")
    write(root / "docs/exploitation/A.md", f"# Procédure\n\n{HEADER}\n\n## 1. Préparer\n\n## 2. Démarrer\n\n"
                                           "```powershell\n.\\rag.ps1 up\n```\n")
    write(root / "docs/assets/diagrams/a.svg", SVG)
    write(root / "pyproject.toml", '[project]\nname = "x"\nversion = "0.1.0"\n')
    write(root / "apps/web/package.json", json.dumps({"name": "x", "version": "0.1.0"}))
    return root


def statuses(root: Path) -> dict[str, str]:
    return {item["id"]: item["status"] for item in check_docs.run(root)["checks"]}


def failing(root: Path) -> list[str]:
    return sorted(name for name, status in statuses(root).items() if status != "PASS")


# -- dépôt réel ------------------------------------------------------------------------------

def test_real_repository_documentation_passes():
    result = check_docs.run(PROJECT)
    failures = [item for item in result["checks"] if item["status"] != "PASS"]
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)
    names = {item["id"] for item in result["checks"]}
    assert names == set(check_docs.CHECKS)
    # Le contrôle doit avoir examiné une population réelle, pas un ensemble vide.
    details = {item["id"]: item["detail"] for item in result["checks"]}
    assert details["links"]["relative_links_checked"] > 100
    assert details["headers"]["documents"] >= 6
    assert details["images"]["svg_checked"] == 5


def test_committed_diagrams_match_generator():
    rendered = diagrams.render_all()
    assert set(rendered) == {path.name for path in (PROJECT / "docs/assets/diagrams").glob("*.svg")}
    for name, content in rendered.items():
        on_disk = (PROJECT / "docs/assets/diagrams" / name).read_bytes()
        assert on_disk == content.encode("utf-8"), f"{name} à régénérer par tools/docs/diagrams.py"
        assert b"\r\n" not in on_disk


def test_generated_diagrams_pass_svg_rules(tmp_path: Path):
    for name, content in diagrams.render_all().items():
        path = write(tmp_path / name, content)
        assert check_docs.svg_faults(path) == [], name


def test_diagram_refuses_text_wider_than_its_box():
    drawing = diagrams.Diagram("essai", 200, "Titre", "Description")
    with pytest.raises(ValueError, match="trop long"):
        drawing.box(24, 40, 120, 60, "service", "Titre", ["une ligne beaucoup trop longue pour ce cadre étroit"])


def test_diagram_refuses_control_characters():
    # Défaut reproduit : « control\runtime.lock » non doublé dans le script produisait un CR dans le SVG.
    drawing = diagrams.Diagram("essai", 200, "Titre", "Description")
    with pytest.raises(ValueError, match="caractère de contrôle"):
        drawing.text(24, 40, "Verrou control\runtime.lock")


def test_diagram_refuses_font_below_minimum():
    drawing = diagrams.Diagram("essai", 200, "Titre", "Description")
    with pytest.raises(ValueError, match="inférieure au minimum"):
        drawing.text(24, 40, "petit", size=10)


# -- projet temporaire : cas nominal et altérations ciblées ---------------------------------

def test_minimal_space_passes(space: Path):
    assert failing(space) == []


def test_broken_relative_link_is_reported(space: Path):
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\nVoir [absent](docs/absent.md).\n")
    assert failing(space) == ["links"]


def test_missing_anchor_is_reported(space: Path):
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\nVoir [section](docs/exploitation/A.md#9-inexistante).\n")
    assert failing(space) == ["links"]


def test_link_into_runtime_is_reported(space: Path):
    write(space / ".runtime/data/x.json", "{}")
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\nVoir [données](.runtime/data/x.json).\n")
    assert failing(space) == ["links"]


def test_links_inside_code_are_ignored(space: Path):
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\n`[absent](docs/absent.md)`\n\n```text\n[absent](nulle-part.md)\n```\n")
    assert failing(space) == []


@pytest.mark.skipif(GIT is None, reason="git absent du poste")
def test_link_to_git_ignored_path_is_reported(space: Path):
    subprocess.run([GIT, "init", "-q", str(space)], check=True, capture_output=True)
    write(space / ".gitignore", "ignored/\n")
    write(space / "ignored/notes.md", "# Notes\n")
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\nVoir [notes](ignored/notes.md).\n")
    result = check_docs.run(space)
    links = next(item for item in result["checks"] if item["id"] == "links")
    assert links["status"] == "FAIL" and "ignorée par Git" in links["detail"]


def test_missing_header_field_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8").replace(" · **Source de vérité :** code", ""))
    assert failing(space) == ["headers"]


@pytest.mark.parametrize("replacement", ["", " · **Propriétaire :**   "])
def test_missing_or_empty_owner_is_reported(space: Path, replacement: str):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8").replace(" · **Propriétaire :** documentation", replacement))
    result = check_docs.run(space)
    headers = next(item for item in result["checks"] if item["id"] == "headers")
    assert headers["status"] == "FAIL" and "proprietaire" in headers["detail"]
    assert "docs/exploitation/A.md" in headers["detail"]
    assert failing(space) == ["headers"]


def test_invalid_status_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8").replace("**Statut :** Stabilisé", "**Statut :** Brouillon"))
    assert "headers" in failing(space)


def test_invalid_update_date_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8").replace("2026-09-30 (UTC)", "30/09/2026"))
    assert failing(space) == ["headers"]


def test_document_missing_from_index_is_reported(space: Path):
    write(space / "docs/interfaces/B.md", f"# Interface\n\n{HEADER}\n")
    assert failing(space) == ["index"]


def test_index_status_must_match_header(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8").replace("**Statut :** Stabilisé", "**Statut :** Historique"))
    assert failing(space) == ["index"]


def test_box_drawing_outside_code_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8") + "\n┌── API\n")
    assert failing(space) == ["ascii_art"]


def test_directory_tree_in_code_block_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8") + "\n```text\nservices/\n├── api/\n└── runtime/\n```\n")
    assert failing(space) == ["ascii_art"]


def test_command_output_with_box_characters_is_allowed(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8") + "\n```text\nRoute (app)\n──── fin\n```\n")
    assert failing(space) == []


def test_mermaid_block_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8") + "\n```mermaid\nflowchart LR\n  A --> B\n```\n")
    assert failing(space) == ["ascii_art"]


def test_remote_image_is_reported(space: Path):
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8") + "\n![badge](https://img.shields.io/badge/x-y-blue)\n")
    assert failing(space) == ["images"]


def test_malformed_svg_is_reported(space: Path):
    write(space / "docs/assets/diagrams/a.svg", SVG.replace("</svg>", ""))
    assert failing(space) == ["images"]


def test_missing_svg_is_reported(space: Path):
    (space / "docs/assets/diagrams/a.svg").unlink()
    assert failing(space) == ["images", "links"]


def test_svg_without_background_is_reported(space: Path):
    write(space / "docs/assets/diagrams/a.svg", SVG.replace('<rect x="0" y="0" width="880" height="100" fill="#F6F4EE"/>', ""))
    assert failing(space) == ["images"]


def test_svg_text_too_small_once_displayed_is_reported(space: Path):
    # 12 px dans un viewBox de 1 200 px affiché sur 880 px : environ 8,8 px à l'écran.
    wide = SVG.replace('width="880" height="100" viewBox="0 0 880 100"', 'width="1200" height="100" viewBox="0 0 1200 100"')
    write(space / "docs/assets/diagrams/a.svg", wide.replace('width="880" height="100" fill', 'width="1200" height="100" fill'))
    result = check_docs.run(space)
    images = next(item for item in result["checks"] if item["id"] == "images")
    assert images["status"] == "FAIL" and "px affiché" in images["detail"]


def test_svg_with_script_or_external_resource_is_reported(space: Path):
    hostile = SVG.replace("</svg>", '<script>alert(1)</script><image href="https://example.org/x.png"/></svg>')
    write(space / "docs/assets/diagrams/a.svg", hostile)
    result = check_docs.run(space)
    images = next(item for item in result["checks"] if item["id"] == "images")
    assert "script" in images["detail"] and "ressource externe" in images["detail"]


def test_svg_with_carriage_return_is_reported(space: Path):
    write(space / "docs/assets/diagrams/a.svg", SVG.replace("Texte lisible", "Verrou control\rruntime.lock"))
    result = check_docs.run(space)
    images = next(item for item in result["checks"] if item["id"] == "images")
    assert images["status"] == "FAIL" and "retour chariot" in images["detail"]


def test_unreferenced_svg_is_reported(space: Path):
    write(space / "docs/assets/diagrams/orphelin.svg", SVG)
    assert failing(space) == ["images"]


def test_version_mismatch_is_reported(space: Path):
    write(space / "apps/web/package.json", json.dumps({"name": "x", "version": "0.2.0"}))
    assert failing(space) == ["versions"]


def test_changelog_must_open_on_unreleased_section(space: Path):
    write(space / "CHANGELOG.md", "# Journal\n\nVersion 0.1.0.\n\n## [0.1.0] - 2026-09-30\n\n- Entrée.\n")
    assert failing(space) == ["versions"]


@pytest.mark.skipif(GIT is None, reason="git absent du poste")
def test_released_section_without_git_tag_is_reported(space: Path):
    subprocess.run([GIT, "init", "-q", str(space)], check=True, capture_output=True)
    changelog = space / "CHANGELOG.md"
    write(changelog, changelog.read_text(encoding="utf-8") + "\n## [0.1.0] - 2026-09-30\n\n- Publication.\n")
    result = check_docs.run(space)
    versions = next(item for item in result["checks"] if item["id"] == "versions")
    assert versions["status"] == "FAIL" and "sans étiquette Git" in versions["detail"]


def test_readme_must_link_documentation_index(space: Path):
    readme = space / "README.md"
    write(readme, readme.read_text(encoding="utf-8").replace("[la documentation](docs/README.md), ", ""))
    assert failing(space) == ["entry_point"]


def test_unclosed_code_fence_is_reported(space: Path):
    document = space / "docs/exploitation/A.md"
    write(document, document.read_text(encoding="utf-8") + "\n```powershell\n.\\rag.ps1 down\n")
    assert "ascii_art" in failing(space)


def test_slug_follows_github_rules():
    assert check_docs.slug("1. Vue d'ensemble") == "1-vue-densemble"
    assert check_docs.slug("11. Écarts constatés avec l'exigence V2.1") == "11-écarts-constatés-avec-lexigence-v21"
    assert check_docs.slug("10. Extraction et ordonnancement : contrats de processus") == \
        "10-extraction-et-ordonnancement--contrats-de-processus"
    assert check_docs.slug("`rag.ps1` et [lien](x.md)") == "ragps1-et-lien"


def test_report_file_is_never_overwritten(space: Path, tmp_path: Path):
    report = tmp_path / "rapport.json"
    assert check_docs.main(["--root", str(space), "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "PASS"
    with pytest.raises(FileExistsError):
        check_docs.main(["--root", str(space), "--report", str(report)])
