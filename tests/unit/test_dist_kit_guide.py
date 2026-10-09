"""Générateur du guide LISEZMOI.md du kit Linux (KIT4-16) : modèle, ancres des sections canoniques, valeurs et refus.

Doubles nommés : `installer_double` remplace les constantes de tools/dist/linux_install.py, `MANIFEST` est un manifeste
factice réduit aux champs que le guide lit. Le test des sections canoniques lit les documents réels de docs/ ; les tests de
concordance avec l'installateur (U3-02, QA3-05, QA3-08) lisent tools/dist/install.sh et tools/dist/linux_install.py réels.
Les tests de la rubrique « Ce dossier », des prérequis et du modèle de menace (U5-02, QA5-02, alignement de la ronde 5)
exécutent le vrai install.sh sur le kit factice de test_dist_linux_scripts (`fake_kit`, interpréteur factice qui laisse un
marqueur s'il est lancé), avec les doubles nommés définis plus bas : InstallateurModifie (`installateur_modifie`),
CopieIdentiqueHorsKit (`dedoublonne_par_lien`), TypeChange (`remplace_par`), LienDeclare (`avec_lien_declare`),
CopieIncomplete (`copie_incomplete_sans`), DroitsPerdus (`droits_perdus_de`), LecturePerdue (`lecture_perdue_de`),
SansAlteration (`sans_alteration`), ProgrammeInstalleFactice (`programme_installe`, pointeur écrit par le double
PointeurDeDesignation, `test_dist_linux_scripts.write_pointer`), OutilsDuPathTemoins (`OUTILS_DU_PATH_TEMOINS`) et
PosteSansOutil (`test_dist_linux_scripts.without_system_tool`). Aucune préparation anonyme (QA6-03). Le test de `verifier`
emploie le kit et le contexte simulés de test_dist_linux_install (`make_kit`, `context`).
"""

import ast
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools.dist import kit_guide
from tools.docs import check_docs

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / kit_guide.TEMPLATE).read_text(encoding="utf-8")
FILES = {"guide": "LISEZMOI.md", "manifest": "kit-manifest.json", "sums": "SHA256SUMS", "links": "SYMLINKS", "executables": "EXECUTABLES",
         "notices": "THIRD_PARTY_NOTICES.md", "installer": "installer.sh"}
DOCUMENTS = {"docs/deploiement/DEPLOIEMENT.md": "# D\n\n## 8. Kit hors ligne Linux\n",
             "docs/exploitation/EXPLOITATION.md": "# E\n\n## 11. Lanceur `atelier` et menu\n",
             "docs/exploitation/DEPANNAGE.md": ("# P\n\n## 10. Installateur et lanceur Linux\n\n### 10.4 Lanceur\n\n"
                                                "#### Réparer un programme installé avec le seul kit de sa version\n"),
             "docs/exploitation/SAUVEGARDE-RESTAURATION.md": "# S\n\n## 2. Sauvegarder\n"}
# Manifeste factice (double nommé), typé pour que mypy accepte les accès aux champs imbriqués (QA4-06).
MANIFEST: dict[str, Any]
MANIFEST = {"version": "0.1.0", "kit_id": "0.1.0+0123456789ab-linux-aarch64-none-2b4b", "commit": "0123456789ab" + "c" * 28,
            "built_utc": "2026-10-07T00:30:00+00:00", "default_model": "qwen3.5:4b", "installer": "installer.sh", "symlinks": 1187,
            "model_profiles": {"qwen3.5:2b": "config/local16.yaml", "qwen3.5:4b": "config/local16-4b.yaml"},
            "gpu": {"variant": "none"}, "notices": {"file": "THIRD_PARTY_NOTICES.md", "usage": "interne (W030)"},
            "requirements": {"memory_gib_min": 15, "kit_bytes": 11_978_322_110, "install_bytes_min": 11_978_322_110 + 3 * 1024**3},
            "target": {"arch": "aarch64", "glibc_min": "2.29", "glibcxx_min": "3.4.26", "kernel_min": "5.3",
                       "tools": [{"name": "sha256sum", "project": "GNU coreutils", "used_for": "empreintes"},
                                 {"name": "tar", "project": "GNU tar", "used_for": "extraction"}],
                       "system_libraries": ["libGL.so.1", "libtiff.so.5"],
                       "system_libraries_required_by": {"libGL.so.1": ["site-packages/cv2/cv2.abi3.so"]},
                       "system_packages": {"libGL.so.1": {"package": "libgl1", "component": "OpenCV (OCR et tableaux)",
                                                          "observed_on": "Ubuntu 20.04.6 LTS aarch64"},
                                           "libtiff.so.5": {"package": None, "component": "OCR Tesseract",
                                                            "observed_on": "Ubuntu 20.04.6 LTS aarch64"}},
                       "optional_system_libraries": {"libcrypt.so.1": "module _crypt de CPython"},
                       "reference_os": "Ubuntu 20.04.6 LTS aarch64 (Jetson Linux R35.4.1, Jetson AGX Orin)",
                       "installation_qualified": False, "installation_qualification_proof": None}}
# Double nommé des constantes de l'installateur (valeurs de la spécification KIT4-02, KIT4-03, KIT4-09, KIT4-17, KIT4-22).
installer_double = SimpleNamespace(LAUNCHER="atelier", USER_COMMAND="atelier", MENU_NAME="Atelier documentaire",
                                   DEFAULT_FOLDER="atelier-documentaire", PROGRAM_FOLDER="programme", DATA_FOLDER="donnees",
                                   EXIT_CODES={0: "réussite", 3: "refus ou annulation avant écriture", 130: "interruption"},
                                   DATA_MIN_FREE_BYTES=2 * 1024**3,
                                   LAUNCHER_ACTIONS={"ouvrir": "ouvrir", "arreter": "arrêter", "diagnostic": "diagnostic", "etat": "état",
                                                     "sauvegarder": "sauvegarder", "journaux": "journaux",
                                                     "modele": "changer durablement le modèle principal"},
                                   DEFAULT_LOCATIONS={"commande": "$HOME/.local/bin/atelier"},
                                   PRE_COPY_PACKAGES=("services", "services/runtime"))


def render(manifest=MANIFEST, documents=DOCUMENTS, installer=installer_double, template=TEMPLATE) -> str:
    return kit_guide.render(manifest, template=template, documents=documents, files=FILES, installer=installer)


def test_kit_guide_loads_only_the_standard_library():
    # Livré dans tools/dist : rien d'autre que la bibliothèque standard n'est importé au chargement du module.
    tree = ast.parse((ROOT / "tools/dist/kit_guide.py").read_text(encoding="utf-8"))
    modules = {alias.name.split(".")[0] for node in tree.body if isinstance(node, ast.Import) for alias in node.names}
    modules |= {node.module.split(".")[0] for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}
    assert modules - {"__future__"} <= set(sys.stdlib_module_names)


def test_the_canonical_sections_exist_in_the_shipped_documents():
    # Documents réels de docs/ (KIT4-15) : chaque section citée par le guide doit exister, avec l'ancre de check_docs.
    documents = {path: (ROOT / path).read_text(encoding="utf-8") for path, _ in kit_guide.SECTIONS.values()}
    links, missing = kit_guide.section_links(documents)
    assert missing == [], f"sections canoniques absentes de docs/ : {missing}"
    for link in links.values():
        path, _, anchor = link.partition("#")
        assert anchor in check_docs.anchors(ROOT / path)


def test_anchors_match_check_docs_for_numbered_and_repeated_headings(tmp_path):
    text = ("# Titre\n\n## 2. Sauvegarder\n\n```sh\n## pas un titre\n```\n\n## Sauvegarder\n\n### 9.1 Lanceur `atelier` et menu\n\n"
            "## 12. Kit hors ligne Linux\n")
    document = tmp_path / "doc.md"
    document.write_text(text, encoding="utf-8")
    found = kit_guide.document_anchors(text)
    assert found["sauvegarder"] == "2-sauvegarder" and found["lanceur atelier et menu"] == "91-lanceur-atelier-et-menu"
    assert found["kit hors ligne linux"] == "12-kit-hors-ligne-linux" and "pas un titre" not in found
    assert set(found.values()) <= check_docs.anchors(document)


def test_the_guide_renders_the_manifest_values():
    guide = render()
    for value in ("# Atelier documentaire : kit hors ligne Linux 0.1.0", "**Statut :** Généré", "kit `0.1.0+0123456789ab-linux-aarch64-none-2b4b`",
                  "**Mis à jour :** 2026-10-07 UTC", "`qwen3.5:4b` (par défaut), `qwen3.5:2b`", "| Taille du kit extrait | 11,2 Gio |",
                  "16,2 Gio au moins avec les emplacements par défaut", "glibc 2.29 ou plus récente", "GLIBCXX_3.4.26", "GNU coreutils (`sha256sum`) ; GNU tar (`tar`)",
                  "| `libGL.so.1` | OpenCV (OCR et tableaux) | `libgl1` |", "| `libtiff.so.5` | OCR Tesseract | à identifier |",
                  "`libcrypt.so.1`, module _crypt de CPython.", "(Ubuntu 20.04.6 LTS aarch64)", "le kit en contient 1187",
                  "l'archive dépasse 4 Gio", "~/.local/share/atelier-documentaire/donnees", "« Atelier documentaire »",
                  "atelier ouvrir --modele qwen3.5:2b", "| 130 | interruption |",
                  "[Déploiement, kit hors ligne Linux](docs/deploiement/DEPLOIEMENT.md#8-kit-hors-ligne-linux)",
                  "[Sauvegarde et restauration](docs/exploitation/SAUVEGARDE-RESTAURATION.md#2-sauvegarder)",
                  "[Réparer un programme installé avec le seul kit de sa version]"
                  "(docs/exploitation/DEPANNAGE.md#réparer-un-programme-installé-avec-le-seul-kit-de-sa-version)"):
        assert value in guide, value
    assert "{{" not in guide and "}}" not in guide


def test_render_refuses_a_missing_section_constant_name_or_placeholder():
    with pytest.raises(kit_guide.GuideError, match="docs/exploitation/DEPANNAGE.md « Installateur et lanceur Linux »"):
        render(documents={**DOCUMENTS, "docs/exploitation/DEPANNAGE.md": "# P\n\n## 10. Autre\n"})
    incomplete = SimpleNamespace(**{key: value for key, value in vars(installer_double).items() if key != "EXIT_CODES"})
    with pytest.raises(kit_guide.GuideError, match="constantes absentes de tools/dist/linux_install.py : EXIT_CODES"):
        render(installer=incomplete)
    with pytest.raises(kit_guide.GuideError, match="emplacements sans valeur .* : inconnu"):
        render(template=TEMPLATE + "\n{{inconnu}}\n")
    with pytest.raises(kit_guide.GuideError, match="noms de fichiers du kit non fournis : guide"):
        kit_guide.render(MANIFEST, template=TEMPLATE, documents=DOCUMENTS, files={**FILES, "guide": ""}, installer=installer_double)


def test_sizes_round_up_with_a_decimal_comma():
    assert kit_guide.gib(11_978_322_110) == "11,2 Gio" and kit_guide.gib(5 * 1024**3) == "5,0 Gio"
    assert kit_guide.gib(5 * 1024**3 + 1) == "5,1 Gio"


def test_the_template_links_only_through_canonical_sections():
    # Les liens du modèle ne passent que par les sections canoniques : aucun lien écrit en dur, aucun lien hors du kit.
    targets = [match.group(3) for match in check_docs.LINK.finditer(TEMPLATE)]
    placeholders = [kit_guide.PLACEHOLDER.fullmatch(target) for target in targets]
    assert targets and all(placeholders)
    assert {match.group(1) for match in placeholders if match} == {f"link_{key}" for key in kit_guide.SECTIONS}


def test_a_kit_with_the_default_model_only_and_without_qualification_says_so():
    single = json.loads(json.dumps(MANIFEST))
    single["model_profiles"] = {"qwen3.5:4b": "config/local16-4b.yaml"}
    single["requirements"]["kit_bytes"] = 3 * 1024**3
    guide = render(single)
    assert "Ce kit ne livre que le modèle `qwen3.5:4b`." in guide and "--modele" not in guide
    assert "FAT32 :" not in guide and "dépasse 4 Gio" not in guide
    assert "aucune installation réelle de ce kit n'est encore qualifiée" in guide
    qualified = json.loads(json.dumps(MANIFEST))
    qualified["target"].update(installation_qualified=True, installation_qualification_proof="recette du 2026-10-20, rapport install-…json")
    assert "qualifiée par une recette réelle : recette du 2026-10-20" in render(qualified)


def test_the_guide_announces_the_space_the_precheck_requires():
    # REL-U08 : le précontrôle exige install_bytes_min, plus la réserve des données (DATA_MIN_FREE_BYTES de l'installateur)
    # quand elles partagent le volume du programme, ce que font les emplacements par défaut.
    row = next(line for line in render().splitlines() if line.startswith("| Place à prévoir pour l'installation |"))
    assert row.index("16,2 Gio") < row.index("14,2 Gio") < row.index("2,0 Gio")
    assert "16,2 Gio au moins avec les emplacements par défaut" in row
    larger = SimpleNamespace(**{**vars(installer_double), "DATA_MIN_FREE_BYTES": 3 * 1024**3})
    assert "17,2 Gio au moins avec les emplacements par défaut" in render(installer=larger)
    assert "l'installation 16,2 Gio au moins avec les emplacements par défaut" in render()


def test_the_guide_describes_added_and_altered_files_as_the_installer_treats_them():
    # REL-U09, S16 : même règle que la section canonique (DEPLOIEMENT §8.2) et que verify_targeted de l'installateur. QA4-07 :
    # le guide place chaque règle en milieu de phrase, la section canonique en début de phrase ; seule la première lettre
    # change de casse, tout le reste est comparé à l'identique (aucun casefold).
    guide = render()
    canonical = (ROOT / "docs/deploiement/DEPLOIEMENT.md").read_text(encoding="utf-8")
    for rule in ("un fichier modifié ou manquant arrête l'installation", "un fichier ajouté est ignoré"):
        assert rule in guide and f"{rule[0].upper()}{rule[1:]}" in canonical, rule
    assert "refuse tout fichier absent" not in guide
    assert "`build_kit verify` et l'archivage, côté fabrication, le refusent" in guide


def section(guide: str, title: str) -> str:
    """Rubrique `## <title>` du guide rendu, sans le titre de la rubrique suivante."""
    return guide.split(f"\n## {title}\n", 1)[1].split("\n## ", 1)[0]


def model_section(guide: str) -> str:
    """Rubrique « Changer de modèle » du guide rendu, sans le titre de la rubrique suivante."""
    return section(guide, "Changer de modèle")


def test_the_guide_cites_the_durable_model_change_and_the_single_opening():
    # U2-04 : le bloc de fin, `installer.sh --aide` et `atelier --aide` citent « atelier modele <modèle> » (durable) ; le guide ne
    # citait que l'ouverture ponctuelle. Les deux voies y figurent, dans le même ordre, avec le renvoi à la section canonique.
    section = model_section(render())
    assert kit_guide.commands(section) == ["atelier modele qwen3.5:2b", "atelier arreter", "atelier ouvrir --modele qwen3.5:2b"]
    assert "Aucun fichier de profil n'est modifié" in section
    assert "`atelier modele qwen3.5:4b` rétablit le modèle par défaut" in section
    assert "[Lanceur atelier et menu](docs/exploitation/EXPLOITATION.md#11-lanceur-atelier-et-menu)" in section


def test_the_model_section_follows_the_launcher_actions_of_the_installer():
    # Les commandes de la rubrique découlent de LAUNCHER_ACTIONS : un installateur sans action « modele » (KIT4-22 refusée) rend
    # un guide sans changement durable ; la constante absente arrête le rendu.
    actions = {name: text for name, text in installer_double.LAUNCHER_ACTIONS.items() if name != "modele"}
    section = model_section(render(installer=SimpleNamespace(**{**vars(installer_double), "LAUNCHER_ACTIONS": actions})))
    assert kit_guide.commands(section) == ["atelier arreter", "atelier ouvrir --modele qwen3.5:2b"]
    assert "`atelier modele" not in section and "durablement" not in section
    incomplete = SimpleNamespace(**{key: value for key, value in vars(installer_double).items() if key != "LAUNCHER_ACTIONS"})
    with pytest.raises(kit_guide.GuideError, match="constantes absentes de tools/dist/linux_install.py : LAUNCHER_ACTIONS"):
        render(installer=incomplete)


def end_block_commands(rows: list[tuple[str, str]], label: str) -> list[str]:
    """Commandes citées (« … ») par les lignes `label` du bloc de fin de l'installateur, dans l'ordre d'affichage."""
    return [command for row, value in rows if row == label for command in re.findall(r"« ([^»]+) »", value)]


@pytest.mark.parametrize("profiles", [("qwen3.5:4b", "qwen3.5:2b"), ("qwen3.5:4b",)], ids=["2b4b", "4b-seul"])
def test_the_guide_and_the_end_of_installation_cite_the_same_model_commands(tmp_path, profiles):
    # Sans double : constantes et bloc de fin réels de tools/dist/linux_install.py (usage_rows) pour une installation dont le
    # modèle principal est le défaut, commande atelier installée. QA3-05 : les listes sont comparées sans tri. Les deux voies
    # (changement durable, puis une seule ouverture) sont citées dans le même ordre des deux côtés, et le guide place l'arrêt,
    # celui du bloc de fin, juste avant la première ouverture avec un autre modèle.
    from tools.dist import linux_install

    manifest = json.loads(json.dumps(MANIFEST))
    manifest["model_profiles"] = {label: MANIFEST["model_profiles"][label] for label in profiles}
    guide = kit_guide.commands(model_section(kit_guide.render(manifest, template=TEMPLATE, documents=DOCUMENTS, files=FILES)))
    data = tmp_path / "donnees"
    entry = {"program": str(tmp_path / "programme" / MANIFEST["kit_id"]), "data_root": str(data), "profile": str(data / "profile.yaml"),
             "model": "qwen3.5:4b", "profiles": {label: str(data / f"profile-{label}.yaml") for label in profiles}}
    pointer = {"current": entry, "menu": True, "user_command": str(tmp_path / ".local/bin/atelier")}
    rows = linux_install.usage_rows(pointer, tmp_path / "programme", entry)
    stop = end_block_commands(rows, linux_install.END_LABELS["stop"])
    change = end_block_commands(rows, linux_install.END_LABELS["model"])
    assert stop == ["atelier arreter"]
    assert [command for command in guide if command not in stop] == change
    single = [command for command in change if "--modele" in shlex.split(command)]
    assert len(change) == 2 * (len(profiles) - 1) and len(single) == len(profiles) - 1
    if single:
        assert guide.index(stop[0]) == guide.index(single[0]) - 1
    else:
        assert guide == []


# --- Concordance du guide avec l'installateur réel (U3-02, QA3-08) ------------------------------------------------------------

def installer_texts() -> str:
    """Textes littéraux de tools/dist/linux_install.py, chaînes adjacentes réunies et valeurs formatées remplacées par « … » :
    ce que l'installateur peut afficher, pour vérifier qu'un texte cité par le guide existe bien."""
    tree = ast.parse((ROOT / "tools/dist/linux_install.py").read_text(encoding="utf-8"))
    parts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            # Parties littérales d'une f-chaîne : des ast.Constant de type str ; les valeurs formatées deviennent « … ».
            parts.append("".join(value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else "…"
                                 for value in node.values))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
    return "\n".join(parts)


def installer_sh_refusals(script: str) -> list[str]:
    """Fichiers ajoutés qu'installer.sh refuse avant de lancer Python, dans l'ordre du script, guillemets retirés : motifs
    relatifs au kit des boucles « for pattern in … ; do », puis chemins des boucles « for path in … ; do » placés sous le
    dossier de l'interpréteur (`$kit/$python_root`), écrits `<CPython>/…` comme dans le guide."""
    joined = script.replace("\\\n", " ")
    refused = [word for words in re.findall(r"^\s*for pattern in (.+?); do$", joined, flags=re.M) for word in shlex.split(words)]
    startup = [word for words in re.findall(r"^\s*for path in (.+?); do$", joined, flags=re.M) for word in shlex.split(words)]
    return refused + [word.replace("$kit/$python_root", "<CPython>", 1) for word in startup if word.startswith("$kit/$python_root/")]


def cited_paths(line: str) -> list[str]:
    """Chemins cités entre accents graves après les deux-points d'une ligne de liste du guide."""
    return re.findall(r"`([^`]+)`", line.split(" : ", 1)[1])


def test_the_guide_explains_how_to_update_an_installation_made_elsewhere():
    # U3-02 (a), delta G : une installation que l'installateur ne retrouve pas (installateur de 78ec95c, chemins en argument)
    # se met à jour par --destination ; le guide cite la ligne réelle du récapitulatif et dit de refuser un autre volume.
    install = section(render(), "Installer")
    assert "./installer.sh update --destination <dossier des versions>" in kit_guide.commands(install)
    assert "« Installation existante : aucune trouvée » (`./installer.sh verifier` l'affiche aussi, sans rien écrire)" in install
    for text in ("registre des installations", "emplacement par défaut", "racine des données vide", "répondre non",
                 "le lanceur `atelier`", "n'en choisir aucun"):
        assert text in install, text
    texts = installer_texts()
    assert "Installation existante : aucune trouvée (registre, emplacement par défaut)" in texts
    # Refus de place d'une installation implicite (U3-03) : même consigne que le guide, avant le choix d'un volume.
    assert "si l'atelier est déjà installé ailleurs, ne choisir aucun volume : « … <dossier des versions> »" in texts
    assert "dossier des versions de l'installation visée" in texts


def test_the_guide_asks_for_a_backup_before_removing_the_last_version():
    # U3-02 (b) : sans sauvegarde, une réinstallation sur ces données est refusée ; le guide le dit avant `uninstall`, avec
    # les commandes du lanceur, et rappelle que la sauvegarde exige l'atelier démarré, comme l'installateur.
    guide = render()
    removal = section(guide, "Mettre à jour, revenir en arrière, désinstaller")
    assert ("Avant de retirer la dernière version, sauvegarder les données (`atelier ouvrir`, puis `atelier sauvegarder`) : une "
            "réinstallation sur des données sans sauvegarde est refusée, et seule une autre racine des données est alors possible ; "
            "le récapitulatif de `uninstall` le rappelle.") in removal
    assert removal.index("Avant de retirer la dernière version") > removal.index("`uninstall` retire le dossier d'une version")
    texts = installer_texts()
    assert "une réinstallation sur ces données sera refusée (reprise sans sauvegarde non prise en charge)" in texts
    assert "Pour installer l'atelier, choisir une autre racine des données" in texts
    backup = section(guide, "Sauvegarder")
    assert "l'atelier démarré (`atelier ouvrir` d'abord)" in backup
    from tools.dist import linux_install

    assert "(atelier démarré)" in linux_install.LAUNCHER_ACTIONS["sauvegarder"]


def test_the_guide_names_exactly_the_added_files_that_stop_the_installer():
    # QA3-08, U3-02 (c) : un fichier ajouté est ignoré et signalé, sauf un module que Python exécuterait avant toute
    # vérification. Le guide nomme exactement les motifs refusés par installer.sh (code 1, avant Python) et, pour une mise à
    # jour, par la vérification ciblée (code 3) ; un motif ajouté ou retiré d'un côté seulement fait échouer ce test.
    from tools.dist import linux_install

    folder = section(kit_guide.render(MANIFEST, template=TEMPLATE, documents=DOCUMENTS, files=FILES), "Ce dossier")
    # U5-02, QA5-02 : l'exception couvre aussi le dossier de l'interpréteur (règle d'install.sh, R3S-01), lu par Python et par
    # le chargeur dynamique ; la confrontation au vrai install.sh est dans test_the_guide_cites_interpreter_entries_….
    assert ("un fichier ajouté est ignoré par l'installateur, qui le signale sans le copier, sauf un fichier de la liste "
            "ci-dessous ou du dossier `<CPython>`, que Python ou le chargeur dynamique liraient avant toute vérification") in folder
    # Ce qui reste exécuté avant d'être contrôlé (U4-07 : installer.sh lui-même, puis la bibliothèque standard listée) est dit
    # mot pour mot comme le skill de l'installateur, avec le renvoi au tableau canonique ; les anciennes phrases ont disparu.
    assert f"{ONLY_BEFORE_HASHING}." in plain(folder)
    assert "La bibliothèque standard de l'interpréteur du kit, chargée avant toute vérification" not in folder
    assert "s'exécutent avant d'être contrôlés : ils ne le sont que pendant la copie" not in folder
    assert "tableau « Ce qui s'exécute avant la vérification » de [Déploiement, kit hors ligne Linux](" in folder
    deployment = (ROOT / "docs/deploiement/DEPLOIEMENT.md").read_text(encoding="utf-8")
    assert "ce qui s'exécute avant la vérification" in kit_guide.document_anchors(deployment)
    assert "Fichiers ajoutés dans le dossier du kit, ignorés (non copiés)" in installer_texts()
    script = (ROOT / "tools/dist/install.sh").read_text(encoding="utf-8")
    refused = installer_sh_refusals(script)
    assert refused, "aucun motif de refus trouvé dans tools/dist/install.sh"
    early = [line for line in folder.splitlines() if line.startswith("- par `installer.sh`")]
    assert len(early) == 2 and "quelle que soit la commande, avant de lancer Python (code 1)" in early[0]
    assert [path for line in early for path in cited_paths(line)] == refused
    assert re.search(r"^fail\(\) \{\n[^}]*\n    exit 1\n\}", script, flags=re.M)
    assert "n'est hachée qu'à la copie" in script
    update = next(line for line in folder.splitlines() if line.startswith("- par une mise à jour"))
    assert "(code 3)" in update and linux_install.EXIT_REFUSED == 3
    assert cited_paths(update) == [f"{package}/{form}" for package in linux_install.PRE_COPY_PACKAGES for form in kit_guide.UPDATE_REFUSED_FORMS]


def test_update_refusals_cited_by_the_guide_match_the_installer(tmp_path):
    # Comportement réel de la vérification ciblée d'une mise à jour (linux_install.added_compiled_modules) dans chaque dossier
    # de PRE_COPY_PACKAGES : chaque forme citée par le guide (UPDATE_REFUSED_FORMS) est refusée, et rien d'autre ; un .py
    # ajouté, ou un module ordinaire d'un dossier ajouté, est seulement ignoré et signalé.
    from fnmatch import fnmatchcase

    from tools.dist import linux_install

    added = ("ajout.pyc", "ajout.cpython-312-aarch64-linux-gnu.so", "ajout.py", "paquet/__init__.py", "paquet/__init__.pyc",
             "paquet/__init__.so", "paquet/__init__.cpython-312-aarch64-linux-gnu.so", "paquet/autre.py")
    for package in linux_install.PRE_COPY_PACKAGES:
        for name in added:
            (tmp_path / package / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / package / name).write_bytes(b"")
    found = set(linux_install.added_compiled_modules(tmp_path, {}))
    forms = [f"{package}/{form}" for package in linux_install.PRE_COPY_PACKAGES for form in kit_guide.UPDATE_REFUSED_FORMS]
    created = {f"{package}/{name}" for package in linux_install.PRE_COPY_PACKAGES for name in added}
    assert found == {path for path in created if any(fnmatchcase(path, form) and path.count("/") == form.count("/") for form in forms)}
    assert all(any(fnmatchcase(path, form) for path in found) for form in forms)
    assert not {path for path in found if path.endswith(".py") and not path.endswith("/__init__.py")}


def test_the_first_steps_give_the_full_launcher_path_when_the_command_is_not_found(tmp_path):
    # U3-02 (d) : `atelier` n'est trouvé qu'à une nouvelle session quand ~/.local/bin vient d'être créé, jamais avec --sans-menu.
    # Le guide donne alors le chemin complet du lanceur, que le bloc de fin de l'installateur cite aussi. Les commandes des
    # premiers pas découlent des actions du lanceur (LAUNCHER_ACTIONS), sauf « modele », traité dans « Changer de modèle ».
    from tools.dist import linux_install

    first = section(kit_guide.render(MANIFEST, template=TEMPLATE, documents=DOCUMENTS, files=FILES), "Premiers pas")
    assert kit_guide.commands(first) == [f"atelier {action}" for action in linux_install.LAUNCHER_ACTIONS if action != "modele"]
    assert "atelier journaux" in kit_guide.commands(first)
    for text in ("`~/.local/share/atelier-documentaire/programme/atelier ouvrir`", "`<dossier des versions>/atelier ouvrir`",
                 "`--sans-menu`", "nouvelle session", "`~/.local/bin`", "la fin de l'installation cite ce chemin"):
        assert text in first, text
    assert "ne sera trouvé qu'à une nouvelle session" in installer_texts()
    # --sans-menu : ni entrée de menu ni commande (choix de l'installateur, sans écriture ni lecture du compte). QA4-06 : un
    # vrai Context, dont l'environnement désigne un HOME propre à l'essai ; sans --sans-menu, le même contexte place l'entrée
    # et la commande sous ce HOME, ce qui montre que l'absence d'intégration vient bien de l'option.
    home = tmp_path / "maison"
    ctx = linux_install.Context(kit=tmp_path / "kit", environ={"HOME": str(home)})
    assert linux_install.integration_for(ctx, tmp_path, sans_menu=True, menu_dir=None) == (
        {"menu": False, "menu_entry": None, "user_command": None}, [])
    assert linux_install.integration_for(ctx, tmp_path, sans_menu=False, menu_dir=None) == (
        {"menu": True, "menu_entry": str(home / ".local/share/applications" / linux_install.DESKTOP),
         "user_command": str(home / ".local/bin" / linux_install.USER_COMMAND)}, [])
    assert not home.exists()
    assert linux_install.DEFAULT_LOCATIONS["commande"] == f"$HOME/.local/bin/{linux_install.USER_COMMAND}"
    data = tmp_path / "donnees"
    entry = {"program": str(tmp_path / "programme" / MANIFEST["kit_id"]), "data_root": str(data), "profile": str(data / "profile.yaml"),
             "model": "qwen3.5:4b", "profiles": {"qwen3.5:4b": str(data / "profile.yaml")}}
    for pointer in ({"current": entry, "menu": True, "user_command": str(tmp_path / ".local/bin/atelier")}, {"current": entry, "menu": False}):
        rows = dict(linux_install.usage_rows(pointer, tmp_path / "programme", entry))
        assert f"« {tmp_path / 'programme' / linux_install.LAUNCHER} ouvrir »" in rows[linux_install.END_LABELS["open"]]


# --- Rubrique « Ce dossier », prérequis et modèle de menace confrontés au vrai install.sh (U5-02, QA5-02, U4-07, ronde 5) ----

POSIX = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="installer.sh : script POSIX")
# Modèle de menace fixé pour R26-KIT-04 (ronde 5), à écrire tel quel là où la garantie de la vérification est décrite ; comparé
# sans accents graves (`plain`), comme dans l'en-tête d'install.sh, la documentation de linux_install.py et le skill.
THREAT_MODEL = ("la vérification du kit protège contre l'altération ACCIDENTELLE (copie ou transport incomplets, fichiers ajoutés par "
                "erreur, déduplication ou fermes de liens, droits perdus). Elle ne protège pas contre une personne qui peut écrire dans "
                "le kit : installer.sh lui-même s'exécute sans vérification préalable, et son intégrité repose sur l'empreinte de "
                "l'archive (<kit_id>.tar.sha256) contrôlée avant extraction.")
# Portée exacte de la vérification avant exécution (U4-07), telle que le skill linux-offline-kit l'écrit pour la documentation.
ONLY_BEFORE_HASHING = ("Seuls installer.sh lui-même et les fichiers listés de la bibliothèque standard du kit, s'ils ont été modifiés, "
                       "s'exécutent avant d'être hachés (à la copie) ; installer.sh lit aussi kit-manifest.json, SHA256SUMS et SYMLINKS "
                       "avant toute vérification Python")
# Titre de la procédure de réparation d'un programme installé (dépannage, section 10.4), que citent install.sh et le guide.
REPAIR_TITLE = "Réparer un programme installé avec le seul kit de sa version"
# Double nommé OutilsDuPathTemoins : `find` et `sha256sum` placés en tête du PATH, qui laissent un témoin s'ils sont lancés.
OUTILS_DU_PATH_TEMOINS = ("find", "sha256sum")


def plain(text: str) -> str:
    """Texte sans accents graves ni gras, espaces réduits : forme sous laquelle les textes sont comparés mot pour mot."""
    return " ".join(text.replace("`", "").replace("**", "").split())


def installer_sh() -> str:
    return (ROOT / "tools/dist/install.sh").read_text(encoding="utf-8")


def matched(pattern: str, text: str) -> re.Match[str]:
    """Correspondance obligatoire d'un motif multiligne : son absence fait échouer l'essai, avec le motif cherché."""
    found = re.search(pattern, text, flags=re.M)
    assert found, f"motif absent : {pattern}"
    return found


def installer_sh_threat_model() -> str:
    """Modèle de menace de l'en-tête de tools/dist/install.sh (lignes de commentaire réunies, « # » retirés)."""
    header = installer_sh().split("\nset -eu\n", 1)[0]
    text = plain(" ".join(line.strip().removeprefix("#") for line in header.splitlines()))
    return matched(r"Modèle de menace : (.+? contrôlée avant extraction\.)", text).group(1)


def programme_installe(folder: Path, role: str = "courante") -> None:
    """Double nommé ProgrammeInstalleFactice : le kit factice (`folder`/kit avec espace) devient le dossier d'une version
    installée, à côté du pointeur `installation.json` de sa destination (`folder`), critère d'install.sh et de rag.sh. Le
    pointeur, écrit par le double PointeurDeDesignation de test_dist_linux_scripts (`write_pointer`), le désigne selon `role` :
    version courante (« courante »), précédente (« precedente »), abandonnée par un retour arrière (« abandonnee ») ou non
    désignée (« non-designee »)."""
    from tests.unit import test_dist_linux_scripts as scripts

    scripts.write_pointer(folder, folder / "kit avec espace", role)


def installer_sh_run(folder: Path, prepare, *, installed: bool = False, role: str = "courante",
                     path_first: tuple[str, ...] = ()) -> tuple[int, str, str, bool]:
    """Vrai install.sh (`installer.sh status`) sur le kit factice de test_dist_linux_scripts (`fake_kit`), placé dans un
    programme installé si `installed` (désigné selon `role` par le pointeur), après `prepare(kit)` ; `path_first` : outils
    témoins placés en tête du PATH. Rend le code, la sortie, la sortie d'erreur et si l'interpréteur du kit a été lancé
    (marqueur du double)."""
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import executable, fake_host

    folder.mkdir(parents=True)
    kit = scripts.fake_kit(folder)
    if installed:
        programme_installe(folder, role)
    prepare(kit)
    fakes = fake_host(folder, "Linux", "aarch64")
    for tool in path_first:
        executable(fakes / tool, f"#!/bin/sh\n: > '{folder}/temoin-{tool}'\nexit 0\n")
    result = scripts.run(kit / "installer.sh", "status", fakes=fakes)
    return result.returncode, result.stdout, result.stderr, (folder / "interpreteur-lance").exists()


def in_interpreter_folder(cited: str) -> str:
    """Chemin du kit factice (relatif à sa racine) pour un chemin `<CPython>/…` cité par le guide ; `*` devient un nom réel."""
    from tests.unit import test_dist_linux_scripts as scripts

    return f"{scripts.CPYTHON}/{cited.removeprefix('<CPython>/')}".replace("*", "os.cpython-312")


def installateur_modifie(witness: Path):
    """Double nommé InstallateurModifie : préparation qui ajoute à installer.sh, juste après sa première ligne, une commande
    qui écrit `witness` (installer.sh reste listé dans SHA256SUMS avec son empreinte d'origine)."""

    def prepare(kit: Path) -> None:
        script = kit / "installer.sh"
        first, rest = script.read_text(encoding="utf-8").split("\n", 1)
        script.write_text(f"{first}\n: > {shlex.quote(str(witness))}\n{rest}", encoding="utf-8")

    return prepare


def dedoublonne_par_lien(relative: str, elsewhere: Path):
    """Double nommé CopieIdentiqueHorsKit : préparation qui remplace le fichier ou le dossier `relative` du kit par un lien
    vers une copie identique placée hors du kit (`elsewhere`), comme une déduplication par liens symboliques ou une ferme de
    liens ; aucun octet ne change."""

    def prepare(kit: Path) -> None:
        source = kit / relative
        elsewhere.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, elsewhere, symlinks=True)
            shutil.rmtree(source)
        else:
            shutil.copy2(source, elsewhere)
            source.unlink()
        os.symlink(elsewhere, source)

    return prepare


def remplace_par(relative: str, kind: str):
    """Double nommé TypeChange : préparation qui remplace l'entrée `relative` du kit par un fichier ordinaire (« fichier » :
    ce que laisse une copie qui a suivi un lien), un dossier non vide (« dossier »), un dossier vide (« dossier vide ») ou un
    tube nommé (« tube », fichier spécial)."""

    def prepare(kit: Path) -> None:
        path = kit / relative
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        if kind == "fichier":
            path.write_bytes(b"contenu de la cible suivie\n")
        elif kind == "tube":
            if sys.platform == "win32":  # os.mkfifo n'existe que sous Unix ; ces essais sont sautés sous Windows (POSIX)
                raise AssertionError("tube nommé : Unix seulement")
            os.mkfifo(path)
        else:
            path.mkdir()
            if kind == "dossier":
                (path / "contenu").write_bytes(b"fichier de la cible suivie\n")

    return prepare


def inscrit(relative: str, content: bytes):
    """Préparation qui ajoute au kit le fichier `relative` et l'inscrit dans SHA256SUMS, comme le fabricant pour un fichier
    du commit (module de la liste des refus ou fichier de démarrage présent dans le kit)."""

    def prepare(kit: Path) -> None:
        from tests.unit import test_dist_linux_scripts as scripts

        (kit / relative).parent.mkdir(parents=True, exist_ok=True)
        (kit / relative).write_bytes(content)
        scripts.write_links(kit, {}, extra=(relative,))

    return prepare


def avec_lien_declare(relative: str, target: str):
    """Double nommé LienDeclare : préparation qui ajoute au kit le lien relatif `relative` → `target`, inscrit dans SYMLINKS
    (SHA256SUMS réécrit, comme le fabricant)."""

    def prepare(kit: Path) -> None:
        from tests.unit import test_dist_linux_scripts as scripts

        os.symlink(target, kit / relative)
        scripts.write_links(kit, {relative: target})

    return prepare


def successively(*steps):
    """Préparation composée : chaque étape, dans l'ordre."""

    def prepare(kit: Path) -> None:
        for step in steps:
            step(kit)

    return prepare


def sans_alteration(kit: Path) -> None:
    """Double nommé SansAlteration : préparation vide, le kit factice reste tel que `fake_kit` l'écrit (témoin)."""


def copie_incomplete_sans(relative: str):
    """Double nommé CopieIncomplete : préparation qui retire du kit l'entrée `relative` (fichier ou lien) inscrite dans
    SHA256SUMS ou SYMLINKS, comme une copie ou une extraction interrompues."""

    def prepare(kit: Path) -> None:
        (kit / relative).unlink()

    return prepare


def droits_perdus_de(relative: str):
    """Double nommé DroitsPerdus : préparation qui laisse au fichier `relative` les droits 0644, sans bit x, comme un
    transport ou une extraction qui perdent le droit d'exécution."""

    def prepare(kit: Path) -> None:
        (kit / relative).chmod(0o644)

    return prepare


def lecture_perdue_de(relative: str):
    """Double nommé LecturePerdue : préparation qui ne laisse au fichier `relative` que le droit d'écriture de son propriétaire
    (0200), comme une copie ou une extraction qui perdent le droit de lecture."""

    def prepare(kit: Path) -> None:
        (kit / relative).chmod(0o200)

    return prepare


@POSIX
def test_the_guide_cites_interpreter_entries_exactly_as_installer_sh_treats_them(tmp_path):
    # U5-02, QA5-02 : installer.sh refuse tout fichier, lien ou fichier spécial ajouté au dossier de l'interpréteur (R3S-01),
    # hormis le bytecode des dossiers __pycache__. Chaque chemin `<CPython>/…` que cite le paragraphe du guide est rejoué sur
    # le vrai install.sh : un exemple de refus doit être refusé (code 1, interpréteur jamais lancé, chemin nommé), comme
    # fichier, comme lien pour le premier et comme tube nommé pour le dernier ; l'exception doit être admise (Python lancé).
    folder = section(render(), "Ce dossier")
    rule = next((paragraph for paragraph in folder.split("\n\n") if "ajouté sous `<CPython>`" in paragraph), "")
    assert "quelle que soit la commande et avant de lancer Python (code 1)" in rule, folder
    assert "tout fichier, lien ou fichier spécial ajouté sous `<CPython>`, absent de `SHA256SUMS` et de `SYMLINKS`" in rule
    cited = re.findall(r"`(<CPython>/[^`]+)`", rule)
    refused = [path for path in cited if "/__pycache__/" not in path]
    admitted = [path for path in cited if "/__pycache__/" in path]
    assert len(refused) >= 3 and admitted == ["<CPython>/lib/python3.12/__pycache__/*.pyc"], cited
    for index, path in enumerate(refused):
        relative = in_interpreter_folder(path)

        def add_file(kit: Path, relative: str = relative) -> None:
            (kit / relative).parent.mkdir(parents=True, exist_ok=True)
            (kit / relative).write_bytes(b"\x7fELF ou module ajout\xc3\xa9\n")

        code, out, err, launched = installer_sh_run(tmp_path / f"fichier-{index}", add_file)
        assert (code, out, launched) == (1, "", False), (path, code, err)
        assert f"{relative} ajouté au kit" in err, (path, err)
    first, last = in_interpreter_folder(refused[0]), in_interpreter_folder(refused[-1])

    def add_link(kit: Path) -> None:
        (kit / first).parent.mkdir(parents=True, exist_ok=True)
        os.symlink("/lib/aarch64-linux-gnu/librt.so.1", kit / first)

    code, out, err, launched = installer_sh_run(tmp_path / "lien", add_link)
    assert (code, out, launched) == (1, "", False) and first in err, (code, err)

    def add_fifo(kit: Path) -> None:
        (kit / last).parent.mkdir(parents=True, exist_ok=True)
        (kit / last).write_bytes(b"")
        remplace_par(last, "tube")(kit)

    code, out, err, launched = installer_sh_run(tmp_path / "tube", add_fifo)
    assert (code, out, launched) == (1, "", False) and f"{last} ajouté au kit" in err, (code, err)
    bytecode = in_interpreter_folder(admitted[0])

    def add_bytecode(kit: Path) -> None:
        (kit / bytecode).parent.mkdir(parents=True, exist_ok=True)
        (kit / bytecode).write_bytes(b"bytecode de compileall")

    code, out, err, launched = installer_sh_run(tmp_path / "bytecode", add_bytecode)
    assert code == 0 and launched, (code, err)


@POSIX
def test_the_type_and_rights_refusals_of_the_guide_are_those_of_installer_sh(tmp_path):
    # Alignement de la ronde 5 (R4S-01 de l'installateur) : chaque refus de type et de droits que cite la rubrique « Ce
    # dossier » est rejoué sur le vrai install.sh avec les doubles CopieIdentiqueHorsKit, TypeChange, LienDeclare,
    # CopieIncomplete, DroitsPerdus et LecturePerdue : code 1, interpréteur jamais lancé, chemin nommé, action du kit. Les
    # fichiers vérifiés que cite le guide sont ceux de la boucle « for name in "$python_relative" … » d'install.sh. Ronde 6 de
    # l'installateur (U6-06, R5S-02, U6-05) : sous <CPython>, une entrée inscrite absente, un fichier inscrit sans droit de
    # lecture pour son propriétaire (find -perm) et un lien inscrit devenu dossier, même vide, sont refusés ; un fichier
    # vérifié par empreinte sans droit de lecture l'est aussi (test -r). Le compte root lit un fichier sans droit de lecture :
    # ces cas-là ne sont pas rejoués en root.
    from tests.unit import test_dist_linux_scripts as scripts

    root = hasattr(os, "geteuid") and os.geteuid() == 0
    blocks = section(render(), "Ce dossier").split("\n\n")
    start = next((index for index, block in enumerate(blocks) if block.startswith("`installer.sh` refuse de même")), None)
    assert start is not None, blocks
    assert blocks[start] == ("`installer.sh` refuse de même, avant de lancer Python (code 1), ce que laissent une copie incomplète, une "
                             "copie par liens, une déduplication, une copie qui a suivi les liens ou des droits perdus :")
    items = blocks[start + 1].splitlines()
    assert len(items) == 3 and all(item.startswith("- ") for item in items), blocks[start + 1]
    checked = shlex.split(matched(r'^for name in "\$python_relative" (.+?); do$', installer_sh()).group(1))
    assert items[0].startswith("- l'interpréteur, un script de l'installateur (")
    # Fichiers des deux premiers points de la liste (boucles « for pattern » et fichiers de démarrage d'install.sh), présents
    # parce qu'inscrits dans SHA256SUMS : cas `tools/__init__.py` et `<CPython>/bin/pyvenv.cfg` ci-dessous.
    assert "ou un module ou un fichier de démarrage des deux premiers points ci-dessus inscrit dans `SHA256SUMS`, remplacé par" in items[0]
    assert re.findall(r"`([^`]+)`", items[0].split(" remplacé par ", 1)[0])[:len(checked)] == checked, (items[0], checked)
    interpreter, library, link = f"{scripts.CPYTHON}/bin/python3.12", f"{scripts.CPYTHON}/lib/libpython3.12.so.1.0", f"{scripts.CPYTHON}/lib/libpython3.12.so"
    declared = avec_lien_declare(link, "libpython3.12.so.1.0")
    elsewhere = tmp_path / "ailleurs"
    link_text, not_regular = "est un lien, absent de SYMLINKS, à la place du fichier inscrit dans SHA256SUMS", "n'est pas un fichier ordinaire"
    folder_text, no_longer = "est un lien, absent de SYMLINKS, à la place d'un dossier du kit", "n'est plus un lien, alors que SYMLINKS l'inscrit"
    absent, added = "absent du kit, alors que SHA256SUMS ou SYMLINKS l'inscrit : copie incomplète", "ajouté au kit, absent de SHA256SUMS et de SYMLINKS"
    unreadable = "sans droit de lecture (droits perdus à la copie ou à l'extraction) : rétablir les droits de lecture du kit (« chmod -R u+rX "
    claims = {
        (0, "remplacé par un lien, un dossier ou un fichier spécial, ou dont un dossier du chemin est devenu un lien absent de `SYMLINKS`"): [
            *((relative, dedoublonne_par_lien(relative, elsewhere / str(index) / Path(relative).name), link_text)
              for index, relative in enumerate([interpreter, *checked])),
            ("tools/__init__.py", successively(inscrit("tools/__init__.py", b""), dedoublonne_par_lien("tools/__init__.py", elsewhere / "m")), link_text),
            (f"{scripts.CPYTHON}/bin/pyvenv.cfg", successively(inscrit(f"{scripts.CPYTHON}/bin/pyvenv.cfg", b"home = /usr\n"),
                                                               remplace_par(f"{scripts.CPYTHON}/bin/pyvenv.cfg", "dossier")), not_regular),
            ("tools/dist/linux_kit.py", remplace_par("tools/dist/linux_kit.py", "dossier"), not_regular),
            ("SYMLINKS", remplace_par("SYMLINKS", "tube"), not_regular),
            ("tools/dist", dedoublonne_par_lien("tools/dist", elsewhere / "dist"), folder_text)],
        (1, "sous `<CPython>`, un fichier inscrit dans `SHA256SUMS` absent, sans droit de lecture pour son propriétaire ou devenu "
            "lien, dossier ou fichier spécial, un dossier de fichiers inscrits devenu lien absent de `SYMLINKS`, et un lien inscrit "
            "dans `SYMLINKS` absent ou devenu fichier ou dossier"): [
            (library, copie_incomplete_sans(library), absent),
            *([(library, lecture_perdue_de(library), unreadable)] if not root else []),
            (library, dedoublonne_par_lien(library, elsewhere / "libpython"), link_text),
            (library, remplace_par(library, "dossier vide"), not_regular),
            # Dossier non vide : son contenu, sous le nom du fichier inscrit, est refusé comme ajouté.
            (library, remplace_par(library, "dossier"), added),
            (library, remplace_par(library, "tube"), not_regular),
            (f"{scripts.CPYTHON}/lib", dedoublonne_par_lien(f"{scripts.CPYTHON}/lib", elsewhere / "lib"), folder_text),
            (link, successively(declared, copie_incomplete_sans(link)), absent),
            (link, successively(declared, remplace_par(link, "fichier")), no_longer),
            (link, successively(declared, remplace_par(link, "dossier")), no_longer),
            (link, successively(declared, remplace_par(link, "dossier vide")), no_longer)],
        (2, "l'interpréteur sans droit d'exécution, et tout fichier du premier point sans droit de lecture"): [
            (interpreter, droits_perdus_de(interpreter), "sans droit d'exécution ("
             f"{interpreter}) : droits perdus à la copie ou à l'extraction"),
            *((relative, lecture_perdue_de(relative), unreadable) for relative in ([] if root else [interpreter, *checked])),
            *([] if root else [("tools/__init__.py", successively(inscrit("tools/__init__.py", b""), lecture_perdue_de("tools/__init__.py")),
                                unreadable)])],
    }
    for (index, claim), cases in claims.items():
        assert claim in items[index], (claim, items[index])
        for number, (relative, prepare, expected) in enumerate(cases):
            code, out, err, launched = installer_sh_run(tmp_path / f"cas-{index}-{number}", prepare)
            assert (code, out, launched) == (1, "", False), (relative, code, err)
            assert relative in err and expected in err, (relative, err)
            assert err.rstrip().endswith("le kit depuis son archive ; rien n'a été exécuté."), (relative, err)


@POSIX
def test_the_guide_gives_the_action_of_installer_sh_in_a_kit_and_in_an_installed_program(tmp_path):
    # Alignement de la ronde 5 (U5-03 de l'installateur) : l'action d'un refus dépend du dossier. Dans un kit, le recopier
    # depuis son archive ; dans un programme installé (pointeur installation.json dans le dossier parent, critère de rag.sh),
    # retirer un fichier ajouté par erreur. Ronde 6 de l'installateur (U6-02) : la suite dépend de ce que le pointeur dit de
    # cette version (double PointeurDeDesignation). Version courante : la réinstaller selon la procédure de dépannage que le
    # guide relie, celle dont install.sh et linux_install.py citent la section et le titre, ou mettre à jour l'installation
    # depuis le kit d'une autre version. Version précédente, abandonnée ou non désignée : la retirer par la commande
    # `uninstall --kit-id` de l'installateur de la version courante, que le refus cite, sans jamais la réinstaller. Un fichier
    # sans droit de lecture (U6-05) : le refus propose aussi `chmod -R u+rX` (non rejoué en root, qui lit ce fichier).
    from tests.unit import test_dist_linux_scripts as scripts

    guide = render()
    folder = section(guide, "Ce dossier")
    anchor = check_docs.slug(REPAIR_TITLE)
    assert kit_guide.SECTIONS["reparation"] == ("docs/exploitation/DEPANNAGE.md", REPAIR_TITLE)
    assert ("Les refus d'`installer.sh` décrits ci-dessus nomment le chemin en cause et l'action à mener : dans un kit, le recopier "
            "depuis son archive (rubrique « Vérifier et extraire l'archive ») ; dans un programme installé (dossier d'une version, à "
            "côté du pointeur `installation.json`), retirer le fichier s'il a été ajouté par erreur ; sinon, pour la version courante, la "
            f"réinstaller depuis le dossier de son kit ([{REPAIR_TITLE}](docs/exploitation/DEPANNAGE.md#{anchor})) ou mettre à jour "
            "l'installation depuis le kit d'une autre version, et pour une version précédente, abandonnée ou non désignée, la retirer par "
            "la commande que cite le refus, sans la réinstaller. Pour un fichier sans droit de lecture, le refus propose aussi de "
            "rétablir ces droits par `chmod -R u+rX`.") in folder
    script = installer_sh()
    assert 'if [ -f "$kit/../installation.json" ]; then' in script
    assert f"section 10.4 (« {REPAIR_TITLE} »)" in installer_texts()
    # La section 10.4 du dépannage réel porte bien cette procédure (install.sh cite « section 10.4 ») : titres de la prose seuls.
    prose, _ = check_docs.split_code((ROOT / "docs/exploitation/DEPANNAGE.md").read_text(encoding="utf-8"))
    headings = [line for _, line in prose if check_docs.HEADING.match(line)]
    position = headings.index(f"#### {REPAIR_TITLE}")
    assert next(line for line in reversed(headings[:position]) if line.startswith("### ")).startswith("### 10.4 "), headings

    def module_added(kit: Path) -> None:
        """Préparation : bytecode ajouté parmi les modules de l'installateur, qu'installer.sh refuse."""
        (kit / "tools/ajout.pyc").write_bytes(b"bytecode ajout\xc3\xa9")

    code, out, err, launched = installer_sh_run(tmp_path / "kit", module_added)
    assert (code, out, launched) == (1, "", False) and err.rstrip().endswith("Recopier le kit depuis son archive ; rien n'a été exécuté."), err

    def action(destination: Path) -> str:
        """Action qu'install.sh donne pour la version courante d'un programme installé dont la destination est `destination`."""
        return scripts.installed_action(destination / "kit avec espace", "courante")

    program = tmp_path / "programme"
    code, out, err, launched = installer_sh_run(program, module_added, installed=True)
    assert (code, out, launched) == (1, "", False), err
    assert "tools/ajout.pyc ajouté à ce programme installé, absent de SHA256SUMS" in err, err
    assert f"Le retirer s'il a été ajouté par erreur, sinon {action(program)} ; rien n'a été exécuté." in err, err
    linked = tmp_path / "programme-lien"
    code, out, err, launched = installer_sh_run(linked, dedoublonne_par_lien("tools/dist/linux_kit.py", tmp_path / "ailleurs" / "linux_kit.py"),
                                                installed=True)
    assert (code, out, launched) == (1, "", False), err
    assert f"R{action(linked)[1:]} ; rien n'a été exécuté." in err, err
    for role in ("precedente", "abandonnee", "non-designee"):
        destination = tmp_path / role
        code, out, err, launched = installer_sh_run(destination, module_added, installed=True, role=role)
        current = shlex.quote(os.path.join(os.path.realpath(destination), scripts.OTHER_VERSION, "installer.sh"))
        assert (code, out, launched) == (1, "", False), (role, err)
        assert "Le retirer s'il a été ajouté par erreur, sinon retirer cette version (" in err and "à ne pas réinstaller" in err, (role, err)
        assert err.rstrip().endswith(f"par « {current} uninstall --kit-id {shlex.quote('kit avec espace')} » ; rien n'a été exécuté."), (role, err)
        assert "section 10.4" not in err and "réinstaller cette version" not in err, (role, err)
    if not (hasattr(os, "geteuid") and os.geteuid() == 0):
        code, out, err, launched = installer_sh_run(tmp_path / "lecture", lecture_perdue_de("tools/dist/linux_kit.py"))
        kit = shlex.quote(os.path.realpath(tmp_path / "lecture" / "kit avec espace"))
        assert (code, out, launched) == (1, "", False), err
        assert f"(« chmod -R u+rX {kit} ») ou recopier le kit depuis son archive ; rien n'a été exécuté." in err, err


@POSIX
def test_the_guide_names_the_tools_installer_sh_takes_from_fixed_system_folders(tmp_path):
    # Alignement de la ronde 5 (U5-04 de l'installateur) : install.sh prend sha256sum et find dans des dossiers fixes du
    # système (fonction system_tool), jamais dans le PATH. Le guide le dit dans ses prérequis, outils et dossiers relevés dans
    # install.sh ; rejoué avec le double OutilsDuPathTemoins : les outils du PATH ne sont pas lancés, l'installation l'est.
    prerequisites = next(line for line in render().splitlines() if line.startswith("- Outils du système : "))
    script = installer_sh()
    tools = re.findall(r"^system_tool (\S+) \|\|$", script, flags=re.M)
    folders = [word.removesuffix("/$1") for word in shlex.split(matched(r"^    for candidate in (.+?); do$", script).group(1))]
    assert set(OUTILS_DU_PATH_TEMOINS) == set(tools) and folders, (tools, folders)
    expected = (f"`installer.sh` prend {' et '.join(f'`{tool}`' for tool in tools)} dans {' ou '.join(f'`{path}`' for path in folders)}, "
                "jamais ailleurs dans le PATH ; si l'un manque des deux, il le nomme et s'arrête avant de lancer Python (code 1) : le "
                "faire installer par l'administrateur du poste.")
    assert prerequisites.endswith(expected), prerequisites
    code, out, err, launched = installer_sh_run(tmp_path / "path", sans_alteration, path_first=OUTILS_DU_PATH_TEMOINS)
    assert code == 0 and launched and not list((tmp_path / "path").glob("temoin-*")), (code, err)


@POSIX
@pytest.mark.parametrize("tool", OUTILS_DU_PATH_TEMOINS)
def test_a_tool_missing_from_the_fixed_folders_is_named_as_the_guide_says(tmp_path, tool):
    # Double PosteSansOutil de test_dist_linux_scripts (unshare -rm, sans privilège) : l'outil absent de /usr/bin et /bin est
    # nommé, avec l'administrateur du poste, avant le lancement de Python (code 1), comme le disent les prérequis du guide.
    import subprocess

    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import executable, fake_host

    if not shutil.which("unshare") or subprocess.run(["unshare", "-rm", "true"], capture_output=True, timeout=30, check=False).returncode:
        pytest.skip("espaces de noms utilisateur et de montage indisponibles sans privilège")
    assert f"`{tool}`" in next(line for line in render().splitlines() if line.startswith("- Outils du système : "))
    kit = scripts.fake_kit(tmp_path)
    fakes = fake_host(tmp_path, "Linux", "aarch64")
    executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 1000\n')  # dans l'espace de noms, le compte est vu comme root
    result = subprocess.run(scripts.without_system_tool(tool, [str(kit / "installer.sh"), "status"]), capture_output=True, text=True,
                            timeout=60, check=False, env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(kit)})
    assert (result.returncode, result.stdout) == (1, "") and not (tmp_path / "interpreteur-lance").exists(), result.stderr
    assert result.stderr.startswith(f"{tool} (") and "absent de /usr/bin et /bin" in result.stderr, result.stderr
    assert "le faire installer par l'administrateur du poste ; rien n'a été exécuté." in result.stderr, result.stderr


def test_the_exit_codes_of_the_guide_are_those_of_the_installer():
    # Garde de concordance (U4-04, QA4-10) : constantes réelles de linux_install.py, sans double. Le tableau du guide reprend
    # EXIT_CODES dans l'ordre, le code 1 y nomme les refus d'installer.sh avant Python, et chaque « (code N) » de la rubrique
    # « Ce dossier » est un code de ce tableau : 1 avant le lancement de Python, 3 pour la mise à jour (EXIT_REFUSED).
    from tools.dist import linux_install

    guide = kit_guide.render(MANIFEST, template=TEMPLATE, documents=DOCUMENTS, files=FILES)
    rows = [line for line in section(guide, "Codes de sortie de l'installateur").splitlines() if line.startswith("| ") and line != "| Code | Signification |"]
    assert rows == [f"| {code} | {meaning} |" for code, meaning in sorted(linux_install.EXIT_CODES.items())]
    assert linux_install.EXIT_CODES[linux_install.EXIT_ERROR].startswith("autre erreur, ou refus d'installer.sh avant le lancement de Python")
    folder = section(guide, "Ce dossier")
    cited = re.findall(r"\(code (\d+)\)", folder)
    assert set(cited) == {str(linux_install.EXIT_ERROR), str(linux_install.EXIT_REFUSED)}, cited
    for sentence in re.split(r"(?<=[.:;])\s", folder):
        if f"(code {linux_install.EXIT_ERROR})" in sentence:
            assert "avant de lancer Python" in sentence, sentence


@POSIX
def test_the_guide_says_verifier_shows_the_no_installation_line_of_the_installer(tmp_path, monkeypatch):
    # Alignement de la ronde 5 (U4-03 de l'installateur) : sans installation retrouvée, `verifier` affiche, sans rien écrire,
    # la ligne « Installation existante : aucune trouvée » du récapitulatif, que le guide cite. Kit et contexte simulés de
    # test_dist_linux_install ; HOME et XDG propres à l'essai.
    from tests.unit import test_dist_linux_install as simulation
    from tools.dist import linux_install

    install = section(render(), "Installer")
    assert "« Installation existante : aucune trouvée » (`./installer.sh verifier` l'affiche aussi, sans rien écrire)" in install
    home = tmp_path / "maison"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_BIN_HOME"):
        monkeypatch.delenv(name, raising=False)
    kit = simulation.make_kit(tmp_path, monkeypatch)
    ctx = simulation.context(kit)
    assert linux_install.main(["verifier"], ctx) == linux_install.EXIT_OK, simulation.screen(ctx)
    assert "\nInstallation existante : aucune trouvée (registre, emplacement par défaut) ; " in simulation.output_of(ctx), simulation.screen(ctx)
    assert list(home.iterdir()) == [] and ctx.runner.calls == []


def test_the_guide_states_the_threat_model_of_the_installer_word_for_word():
    # Modèle de menace écrit tel quel, comme dans l'en-tête d'install.sh, là où l'utilisateur contrôle l'archive, avant toute
    # extraction ; la commande de contrôle nomme l'empreinte de ce kit. La rubrique « Ce dossier » y renvoie sans le recopier,
    # et rien d'autre dans le guide ne promet plus.
    assert installer_sh_threat_model() == THREAT_MODEL
    guide = render()
    check = section(guide, "Vérifier et extraire l'archive")
    assert f"Modèle de menace : {THREAT_MODEL}" in plain(check), check
    assert f"Pour ce kit, il s'agit de `{MANIFEST['kit_id']}.tar.sha256`, contrôlé par la commande ci-dessus." in check
    assert check.index("sha256sum -c") < check.index("tar -xf") < check.index("Une empreinte différente") < check.index("Modèle de menace")
    folder = section(guide, "Ce dossier")
    assert "Portée de cette vérification : rubrique « Vérifier et extraire l'archive »" in folder and "protège" not in folder
    assert plain(guide).count("protège contre") == 1 and guide.count("ACCIDENTELLE") == 1
    for stale in ("ne protège que d'une altération accidentelle", "altération accidentelle", "sans avoir été vérifié", "vérifie tout le kit",
                  "garantit"):
        assert stale not in guide, stale


@POSIX
def test_what_the_guide_says_runs_before_any_check_matches_installer_sh(tmp_path):
    # U4-07 : phrase du skill de l'installateur, écrite mot pour mot (« Seuls installer.sh lui-même et les fichiers listés de
    # la bibliothèque standard du kit… »). Rejouée sur le vrai install.sh : (1) une commande ajoutée à installer.sh s'exécute
    # avant tout contrôle ; (2) un fichier listé de la bibliothèque standard, modifié, n'arrête pas installer.sh (haché à la
    # copie seulement) ; (3) tout autre fichier exécuté ou lu avant Python, SYMLINKS compris, modifié, arrête installer.sh
    # avant le lancement.
    from tests.unit import test_dist_linux_scripts as scripts

    skill = plain((ROOT / ".agents/skills/linux-offline-kit/SKILL.md").read_text(encoding="utf-8"))
    assert ONLY_BEFORE_HASHING in skill
    assert f"{ONLY_BEFORE_HASHING}." in plain(section(render(), "Ce dossier"))
    witness = tmp_path / "installateur-execute"
    installer_sh_run(tmp_path / "installateur", installateur_modifie(witness))
    assert witness.exists()
    standard = f"{scripts.CPYTHON}/lib/python3.12/os.py"

    def standard_library_altered(kit: Path) -> None:
        (kit / standard).parent.mkdir(parents=True)
        (kit / standard).write_text("# os livré\n", encoding="utf-8")
        scripts.write_links(kit, {}, extra=(standard,))
        (kit / standard).write_text("# os modifié après la fabrication\n", encoding="utf-8")

    code, _, err, launched = installer_sh_run(tmp_path / "bibliotheque-standard", standard_library_altered)
    assert code == 0 and launched, err
    for index, relative in enumerate((f"{scripts.CPYTHON}/bin/python3.12", f"{scripts.CPYTHON}/lib/libpython3.12.so.1.0",
                                      "tools/dist/linux_install.py", "tools/dist/linux_kit.py", "tools/dist/build_kit.py", "SYMLINKS")):

        def altered(kit: Path, relative: str = relative) -> None:
            (kit / relative).write_bytes((kit / relative).read_bytes() + b"\n# altere\n")

        code, out, err, launched = installer_sh_run(tmp_path / f"controle-{index}", altered)
        assert (code, out, launched) == (1, "", False) and "altéré" in err, (relative, code, err)


@POSIX
@pytest.mark.parametrize("relative", [".runtime/python/cpython/bin/python3.12", "tools/dist/linux_install.py"],
                         ids=["interpreteur", "installateur"])
def test_the_threat_model_of_the_guide_holds_for_a_link_farm(tmp_path, relative):
    # Le modèle de menace du guide range « déduplication ou fermes de liens » parmi les altérations accidentelles dont la
    # vérification protège. Un fichier exécuté avant la vérification en Python, remplacé par un lien vers une copie identique
    # hors du kit, ferait prendre à ld.so et à Python un autre arbre que celui qu'installer.sh a haché (R4S-01) : installer.sh
    # doit le refuser avant de lancer Python (code 1), en nommant le chemin, sans jamais lancer l'interpréteur.
    assert "déduplication ou fermes de liens" in section(render(), "Vérifier et extraire l'archive")
    code, out, err, launched = installer_sh_run(tmp_path / "kit", dedoublonne_par_lien(relative, tmp_path / "ailleurs" / Path(relative).name))
    assert (code, out, launched) == (1, "", False), (code, out, err)
    assert relative in err, err
