"""Documentation du kit hors ligne Linux (R26-KIT-04 : KIT4-01, KIT4-15, KIT4-25 ; revues S17, REL-U18, U2-01, U2-03)
confrontée au code livré.

Les tests lisent les documents réels de docs/ et les Markdown livrés dans le kit (README.md, CHANGELOG.md), et les comparent
à l'analyseur et aux constantes réels de tools/dist/linux_install.py, à la liste blanche de tools/dist/linux_kit.py, aux
messages de tools/dist/install.sh et de rag.sh, au défaut de services/runtime/cli.py et aux profils livrés. Doubles nommés :
MANIFEST_DOUBLE, manifeste réduit aux champs que lit le guide généré (tools/dist/kit_guide.py) ; pour les installations
simulées, PosteSimule et ProgrammeSimule de test_dist_linux_install.py (lectures du poste et commandes lancées), avec un
kit fabriqué par ses aides et un HOME propre à chaque essai ; COPIE_ARRETEE, dossier de version que laisse une copie tuée
avant ses deux derniers fichiers ; FICHIER_PERDU, fichier du programme courant retiré à la main, et ECRIT_APRES, document
écrit dans les données après la dernière sauvegarde. Pour la portée de la vérification (déploiement, section 8.3) et les refus
d'installer.sh (dépannage, section 10.1), le vrai installer.sh est lancé sur les kits factices de test_dist_linux_scripts, et
sur ProgrammeInstalleFactice (le même kit placé en version installée, pointeur dans le dossier parent), avec ces doubles
nommés : FICHIER_LISTE_MODIFIE (fichier inscrit à SHA256SUMS, modifié après l'extraction), COPIE_IDENTIQUE_HORS_KIT (fichier ou
dossier vérifié remplacé par un lien vers une copie de même contenu hors du kit, comme une déduplication par liens
symboliques), LIEN_DEVENU_FICHIER (entrée de SYMLINKS remplacée par un fichier ordinaire), FICHIER_DEVENU_TUBE (entrée de
SHA256SUMS remplacée par un tube), SANS_BIT_X (droit d'exécution perdu), DOSSIER_ILLISIBLE (sous-dossier de l'interpréteur sans
droit de lecture), BIN_SANS_FIND (PATH fait de liens vers /usr/bin et /bin, sauf find : témoin) et PosteSansOutil de
test_dist_linux_scripts (find ou sha256sum masqués dans /usr/bin et /bin par unshare -rm, sans privilège). Ronde 6 de
l'installateur : FICHIER_ABSENT et FICHIER_ILLISIBLE (fichier inscrit retiré, ou privé de son droit de lecture),
LIEN_DEVENU_DOSSIER_VIDE et FICHIER_DEVENU_DOSSIER_VIDE (entrée inscrite remplacée par un dossier vide), PointeurDeDesignation de
test_dist_linux_scripts (pointeur qui désigne le programme comme version courante, précédente, abandonnée, non désignée, ou
pointeur d'un autre format), DossierParUnLien (dossier des versions atteint par un lien) et PosteSimule avec `installer_refusals`
(refus d'installer.sh que status relaie). Pour la désinstallation,
ProcessusDuProgramme de test_dist_linux_install (processus du compte lancés depuis un programme). Les procédures de réparation
(dépannage, section 10.4) et de mise à jour d'une installation de 78ec95c (déploiement, section 8.5) sont exécutées telles
qu'écrites sur ces doubles. Ces contrôles prouvent la concordance des textes avec le code et avec les messages réellement
émis par l'installateur simulé ; ils ne prouvent ni une procédure exécutée sur un poste ni une installation réelle (recette
R26-KIT-02).
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import io
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

import pytest
import yaml

from tools.dist import kit_guide, linux_install, linux_kit
from tools.docs import check_docs

ROOT = Path(__file__).resolve().parents[2]
DEPLOIEMENT = "docs/deploiement/DEPLOIEMENT.md"
EXPLOITATION = "docs/exploitation/EXPLOITATION.md"
DEPANNAGE = "docs/exploitation/DEPANNAGE.md"
SAUVEGARDE = "docs/exploitation/SAUVEGARDE-RESTAURATION.md"
# Fichiers que le fabricant ajoute à la racine du kit (linux_kit), présents dans le kit sans être suivis par Git.
GENERATED = {linux_kit.GUIDE, linux_kit.SUMS, linux_kit.LINKS, linux_kit.EXECUTABLES, linux_kit.MANIFEST, linux_kit.NOTICES,
             linux_install.INSTALLER_NAME}
EMITTERS = {"InstallError", "PrecheckRefusal", "SwitchIncomplete", "Interrupted"}
PLACEHOLDER = re.compile(r"<[^<>\s][^<>]*>")
# Double nommé : manifeste réduit aux champs que le guide lit (valeurs du poste de référence, aucune ne vient d'un kit réel).
MANIFEST_DOUBLE = {"version": "0.1.0", "kit_id": "0.1.0+0123456789ab-linux-aarch64-none-2b4b", "commit": "0123456789ab" + "c" * 28,
                   "built_utc": "2026-10-07T00:30:00+00:00", "default_model": "qwen3.5:4b", "symlinks": 1187,
                   "model_profiles": {"qwen3.5:4b": "config/local16-4b.yaml", "qwen3.5:2b": "config/local16.yaml"},
                   "gpu": {"variant": "none"}, "notices": {"usage": "interne (W030)"},
                   "requirements": {"memory_gib_min": 15, "kit_bytes": 11_978_322_110, "install_bytes_min": 11_978_322_110 + 3 * 1024**3},
                   "target": {"arch": "aarch64", "glibc_min": "2.29", "kernel_min": "5.3", "reference_os": "Ubuntu 20.04.6 LTS aarch64"}}
GUIDE_FILES = {"guide": linux_kit.GUIDE, "manifest": linux_kit.MANIFEST, "sums": linux_kit.SUMS, "links": linux_kit.LINKS,
               "executables": linux_kit.EXECUTABLES, "notices": linux_kit.NOTICES, "installer": linux_install.INSTALLER_NAME}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def section(relative: str, title: str) -> str:
    """Texte d'une section, de son titre jusqu'au titre suivant de même niveau ou de niveau supérieur (hors blocs de code)."""
    lines = read(relative).splitlines()
    fence: str | None = None
    start = level = None
    found: list[str] = []
    for index, line in enumerate(lines):
        marker = check_docs.FENCE.match(line)
        heading = None
        if fence is None and marker:
            fence = marker.group(1)[0]
        elif fence is not None and marker and marker.group(1)[0] == fence and not marker.group(2):
            fence = None
        elif fence is None:
            heading = check_docs.HEADING.match(line)
        if heading and start is not None and level is not None and len(heading.group(1)) <= level:
            break
        if heading and start is None and kit_guide.heading_key(heading.group(2)) == kit_guide.heading_key(title):
            start, level = index, len(heading.group(1))
        if start is not None:
            found.append(line)
    assert start is not None, f"section « {title} » absente de {relative}"
    return "\n".join(found)


def tables(text: str) -> list[list[list[str]]]:
    """Tableaux Markdown de la prose : lignes de cellules, ligne de séparation retirée."""
    prose, _ = check_docs.split_code(text)
    found: list[list[list[str]]] = []
    current: list[list[str]] = []
    for _, line in prose + [(0, "")]:
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                current.append(cells)
        elif current:
            found.append(current)
            current = []
    return found


def table_with_header(text: str, first: str) -> list[list[str]]:
    matching = [table for table in tables(text) if table and table[0][0] == first]
    assert matching, f"tableau d'en-tête « {first} » absent"
    return matching[0]


def in_kit(relative: str) -> bool:
    """Chemin du dépôt livré dans le kit Linux : liste blanche du fabricant, motifs exclus, fichiers ajoutés à la racine."""
    if relative in GENERATED:
        return True
    tracked = any(relative == entry or relative.startswith(entry + "/") for entry in linux_kit.TRACKED)
    return tracked and not any(fnmatch.fnmatch(relative, pattern) for pattern in linux_kit.EXCLUDED)


def link_targets(base: str, text: str) -> list[tuple[str, str]]:
    """(chemin relatif au dépôt, ancre) de chaque lien relatif de la prose ; `base` : document qui porte le texte."""
    prose, _ = check_docs.split_code(text)
    found = []
    for _, line in prose:
        for match in check_docs.LINK.finditer(check_docs.without_inline_code(line)):
            target = match.group(3)
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                continue
            path = unquote(parts.path)
            resolved = base if not path else os.path.normpath(os.path.join(os.path.dirname(base), path)).replace(os.sep, "/")
            found.append((resolved, unquote(parts.fragment)))
    return found


def kit_sections() -> list[tuple[str, str, str]]:
    return [(path, title, section(path, title)) for path, title in kit_guide.SECTIONS.values()]


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    return next(action.choices for action in parser._actions if isinstance(action, argparse._SubParsersAction))  # noqa: SLF001


def visible_options(parser: argparse.ArgumentParser) -> set[str]:
    return {option for action in parser._actions if action.help != argparse.SUPPRESS  # noqa: SLF001
            for option in action.option_strings if option.startswith("--") and option not in {"--aide", "--help"}}


def shell_commands(text: str) -> list[list[str]]:
    _, blocks = check_docs.split_code(text)
    return [shlex.split(PLACEHOLDER.sub("/tmp/atelier-essai", line), comments=True)
            for language, _, lines in blocks if language == "sh" for line in lines if line.strip()]


def longest_literal(message: str) -> str:
    """Plus long fragment constant d'un message de script shell (variables retirées)."""
    pieces = re.split(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*", message)
    return max((piece.strip() for piece in pieces), key=len)


def emitting_functions() -> set[str]:
    """Fonctions de premier niveau de linux_install.py qui émettent un refus, un échec, une interruption, un avertissement
    ou un message sur la sortie d'erreur : chacune doit avoir sa ligne de dépannage."""
    found = set()
    for node in ast.parse(read("tools/dist/linux_install.py")).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            emits = (isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call) and isinstance(sub.exc.func, ast.Name)
                     and sub.exc.func.id in EMITTERS)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                emits |= sub.func.attr == "warn"
                emits |= sub.func.attr == "append" and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "failures"
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "print":
                emits |= any(keyword.arg == "file" and ast.unparse(keyword.value) == "ctx.err" for keyword in sub.keywords)
            if emits:
                found.add(node.name)
                break
    return found


def shell_messages(relative: str, *, start: str | None = None) -> list[str]:
    """Messages de `fail "…"` (et de la variable kit_refusal) d'un script ; `start` : ligne du bloc `if` à lire seul."""
    text = read(relative)
    if start is not None:
        lines = text.splitlines()
        first = next(index for index, line in enumerate(lines) if start in line)
        last = next(index for index in range(first + 1, len(lines)) if lines[index] == "fi")
        text = "\n".join(lines[first:last + 1])
    return re.findall(r'(?:\bfail|kit_refusal=)\s*"((?:[^"\\]|\\.)*)"', text)


# --- KIT4-01 : affirmations fausses retirées -------------------------------------------------------------------------------

def test_no_document_denies_the_linux_kit():
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for statement in ("aucun kit ni installateur Linux", "n'inclut pas `packages/`"):
            assert statement not in text, f"{path.relative_to(ROOT)} : « {statement} »"
    text = read(DEPLOIEMENT)
    assert "installer.sh" in text and "R26-KIT-02" in text
    rows = table_with_header(section(DEPLOIEMENT, "Voies et conditions"), "Voie")
    aarch64 = [row for row in rows if row[0].startswith("Kit hors ligne") and row[1].startswith("Linux aarch64")]
    x86_64 = [row for row in rows if row[0].startswith("Kit hors ligne") and row[1].startswith("Linux x86-64")]
    assert len(aarch64) == 1 and "R26-KIT-02" in aarch64[0][2]
    assert len(x86_64) == 1 and "R26-KIT-03" in x86_64[0][2]
    fields = check_docs.header_fields(ROOT / DEPLOIEMENT)
    assert "78ec95c" in fields["reference"] and "2026-10-07" in fields["mis a jour"]
    for source in ("tools/dist/linux_kit.py", "tools/dist/linux_install.py", "tools/dist/install.sh", "tools/dist/linux_profiles.py"):
        assert source in fields["source de verite"], source


# --- KIT4-15 : procédures canoniques conformes à l'analyseur et aux constantes --------------------------------------------

def test_launcher_actions_table_matches_the_parser():
    parser = linux_install.build_parser()
    run = subparsers(parser)["run"]
    choices = next(action.choices for action in run._actions if action.dest == "action")  # noqa: SLF001
    assert choices is not None and list(choices) == list(linux_install.LAUNCHER_ACTIONS)
    text = section(EXPLOITATION, "Lanceur atelier et menu")
    rows = table_with_header(text, "Action")[1:]
    documented = [re.findall(r"`([^`]+)`", row[0])[0].split()[0] for row in rows]
    assert sorted(documented) == sorted(linux_install.LAUNCHER_ACTIONS)
    for option in visible_options(run):
        assert option in text, option
    for label in linux_install.MENU_ACTIONS.values():
        assert label in text, label
    assert linux_install.MENU_NAME in text and linux_install.DEFAULT_LOCATIONS["commande"] in text
    deploiement = section(DEPLOIEMENT, "Kit hors ligne Linux")
    commands = {name: command for name, command in subparsers(parser).items() if name != "run"}
    assert sorted(commands) == sorted(linux_install.INSTALLER_COMMANDS)
    for name, command in commands.items():
        assert f"installer.sh {name}" in deploiement, name
        for option in visible_options(command):
            assert option in deploiement, f"{name} {option}"
    for option in visible_options(parser):
        assert option in deploiement, option
    for location in linux_install.DEFAULT_LOCATIONS.values():
        assert location in deploiement, location


def test_every_command_of_the_kit_sections_parses():
    installer = launcher = 0
    for path, _, text in kit_sections():
        for words in shell_commands(text):
            if not words:
                continue
            program = words[0].rsplit("/", 1)[-1]
            if program == linux_install.INSTALLER_NAME:
                argv, installer = words[1:], installer + 1
            elif program == linux_install.USER_COMMAND:
                argv, launcher = ["run", "--destination", "/tmp/atelier-essai", *words[1:]], launcher + 1
            else:
                continue
            out, err = io.StringIO(), io.StringIO()
            try:
                linux_install.build_parser(streams=(out, err)).parse_args(argv)
            except SystemExit as error:
                # Code 0 : aide demandée (--aide) ; tout autre code est un refus de l'analyseur.
                if error.code not in (0, None):
                    raise AssertionError(f"{path} : « {' '.join(words)} » refusée par l'analyseur : {err.getvalue().strip()}") from error
    assert installer >= 10 and launcher >= 6, (installer, launcher)


def test_exit_codes_table_matches_the_installer():
    rows = table_with_header(section(DEPLOIEMENT, "Kit hors ligne Linux"), "Code")[1:]
    documented = {int(row[0].strip("`")): row[1] for row in rows}
    assert set(documented) == set(linux_install.EXIT_CODES)
    for code, meaning in linux_install.EXIT_CODES.items():
        assert meaning in documented[code], code


def test_every_installer_message_family_has_a_troubleshooting_row():
    text = section(DEPANNAGE, "Installateur et lanceur Linux")
    rows = [row for table in tables(text) for row in table[1:]]
    cited = {name for row in rows for name in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", row[-1])}
    missing = sorted(emitting_functions() - cited)
    assert not missing, f"fonctions de linux_install.py sans ligne de dépannage : {missing}"
    messages = shell_messages("tools/dist/install.sh") + shell_messages("rag.sh", start='"$project_root/kit-manifest.json" ]; then')
    # « fail "$kit_refusal" » ne porte aucun texte propre : son message est celui de l'affectation kit_refusal=, contrôlée.
    messages = [message for message in messages if longest_literal(message)]
    assert len(messages) >= 15
    for message in messages:
        fragment = longest_literal(message)
        assert len(fragment) >= 12 and fragment in text, fragment


def test_configuration_change_names_the_installation_profile():
    text = section(EXPLOITATION, "Changer la configuration ou le code")
    assert "<données>/profile.yaml" in text and "Lanceur `atelier` et menu" in text


def test_backup_section_covers_the_installation():
    text = section(SAUVEGARDE, "Sauvegarder")
    assert "nécessaire au retour arrière" in read("tools/dist/linux_install.py")
    for expected in ("atelier sauvegarder", "<données>/backups", "installer.sh status", "nécessaire au retour arrière",
                     "rag.sh verify", "rag.sh restore"):
        assert expected in text, expected


# --- Revue de R26-KIT-04 (REL-U18, S17) : textes confrontés au comportement de l'installateur simulé -----------------------

# Appels de linux_install.update et étape que le « Déroulement » de la section 8.5 leur fait correspondre.
UPDATE_STEPS = {"precheck": "précontrôles", "derive_profiles": "dérivation contrôlée", "verify_targeted": "vérification ciblée",
                "system_check": "contrôles du système", "backup_estimate": "estimation de la place de la sauvegarde",
                "confirm": "récapitulatif confirmé"}


def simulated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    """HOME propre à un essai, sans variable XDG : aucune entrée, commande ni registre n'atteint le compte réel."""
    home = tmp_path / name
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for variable in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_BIN_HOME"):
        monkeypatch.delenv(variable, raising=False)
    return home


def files_under(folder: Path) -> set[Path]:
    return {path.relative_to(folder) for path in folder.rglob("*") if path.is_file() or path.is_symlink()}


def home_relative(location: str) -> Path | None:
    """Emplacement par défaut du tableau de la section 8.4, relatif au HOME, variables XDG absentes ; None hors du HOME."""
    text = re.sub(r"\$\{[A-Z_]+:-([^}]*)\}", r"\1", location.strip("`"))
    return Path(text.removeprefix("$HOME/")) if text.startswith("$HOME/") else None


def troubleshooting_row(cause: str) -> list[str]:
    """Ligne du dépannage de l'installateur dont la colonne Cause contient `cause`, casse ignorée."""
    rows = [row for table in tables(section(DEPANNAGE, "Installateur et lanceur Linux")) for row in table[1:]
            if cause.casefold() in row[1].casefold()]
    assert len(rows) == 1, f"DEPANNAGE.md, section 10 : {len(rows)} ligne(s) dont la cause contient « {cause} »"
    return rows[0]


def quoted_messages(cell: str) -> list[str]:
    """Extraits de la colonne Message : « … » de premier niveau (guillemets imbriqués compris) et `…` d'au moins 30 caractères,
    forme employée quand le message contient lui-même des guillemets."""
    found: list[str] = []
    depth, current = 0, []
    for char in cell:
        if char == "«":
            depth += 1
            if depth == 1:
                current = []
                continue
        elif char == "»" and depth:
            depth -= 1
            if depth == 0:
                found.append("".join(current))
                continue
        if depth:
            current.append(char)
    return found + [span for span in re.findall(r"`([^`]+)`", cell) if len(span) >= 30]


def assert_quotes_were_emitted(cell: str, emitted: str) -> None:
    """Chaque extrait de la colonne Message figure dans la sortie réelle, « … » valant pour une valeur variable."""
    quotes = quoted_messages(cell)
    assert quotes, cell
    for quote in quotes:
        for fragment in (piece.strip() for piece in quote.split("…")):
            assert fragment in emitted, f"« {fragment} » absent des messages émis :\n{emitted}"


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_files_written_outside_the_chosen_folders_follow_the_documented_options(tmp_path, monkeypatch):
    """REL-U18 : une installation simulée avec et sans --sans-menu ; chaque fichier écrit dans le HOME a sa ligne au tableau
    de la section 8.4, --sans-menu n'est cité qu'aux éléments qu'il supprime, et la ligne de l'option nomme ceux qu'il écrit
    encore."""
    from tests.unit import test_dist_linux_install as simulation

    kit = simulation.make_kit(tmp_path, monkeypatch)
    rows = table_with_header(section(DEPLOIEMENT, "Emplacements et fichiers écrits"), "Élément")[1:]
    locations = {row[0]: home_relative(row[1]) for row in rows}
    written: dict[str, set[str]] = {}
    for label, extra in (("defaut", ()), ("sans-menu", ("--sans-menu",))):
        home = simulated_home(tmp_path, monkeypatch, f"maison-{label}")
        ctx = simulation.context(kit)
        code = simulation.install(ctx, tmp_path / label / "programmes", tmp_path / label / "donnees", "--no-start", *extra)
        assert code == 0, simulation.screen(ctx)
        written[label] = set()
        for path in files_under(home):
            elements = [name for name, location in locations.items() if location and (path == location or location in path.parents)]
            assert len(elements) == 1, f"{path} écrit dans le HOME ({label}) : ligne du tableau de la section 8.4 attendue, trouvé {elements}"
            written[label] |= set(elements)
    removed, kept = written["defaut"] - written["sans-menu"], written["sans-menu"]
    assert removed and kept <= written["defaut"], written
    for name, _, choice in rows:
        if name in removed:
            assert "--sans-menu" in choice, f"section 8.4, « {name} » : --sans-menu le supprime"
        if name in kept:
            assert "--sans-menu" not in choice, f"section 8.4, « {name} » : écrit aussi avec --sans-menu"
    options = table_with_header(section(DEPLOIEMENT, "Installer"), "Option de `install`")
    effect = next(row[1] for row in options if row[0] == "`--sans-menu`")
    for name in kept:
        assert name.lower() in effect.lower(), f"ligne --sans-menu de la section 8.3 : « {name} » est écrit avec cette option"


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_troubleshooting_covers_a_partial_version_folder(tmp_path, monkeypatch):
    """S17 (constat S03) : arrêt brutal pendant la copie. Avec son marqueur, la même commande reprend l'installation ; sans
    marqueur, le dossier incomplet est refusé, listé par `status` et retiré par la commande citée. Le dépannage cite ces
    messages et ces deux suites."""
    from tests.unit import test_dist_linux_install as simulation

    kit = simulation.make_kit(tmp_path, monkeypatch)
    simulated_home(tmp_path, monkeypatch, "maison")
    kit_id = simulation.manifest_of(kit)["kit_id"]
    # Arrêt brutal réel : double killed_install de test_dist_linux_install (installation tuée par SIGKILL pendant la copie,
    # dans un processus séparé, sans aucun nettoyage).
    destination, data_root = tmp_path / "tuee" / "programmes", tmp_path / "tuee" / "donnees"
    simulation.killed_install(kit, destination, data_root, "copie")
    resumed = simulation.context(kit)
    assert simulation.install(resumed, destination, data_root, "--no-start") == 0, simulation.screen(resumed)
    # Double nommé COPIE_ARRETEE : dossier de version sans marqueur ni kit-manifest.json (écrit en dernier par
    # linux_kit.install_copy), par exemple après une mise à jour tuée pendant sa copie.
    destination, data_root = tmp_path / "orphelin" / "programmes", tmp_path / "orphelin" / "donnees"
    partial = destination / kit_id
    (partial / "services").mkdir(parents=True)
    shutil.copy2(kit / "rag.sh", partial / "rag.sh")
    attempt, state, removal = simulation.context(kit), simulation.context(kit), simulation.context(kit)
    assert simulation.install(attempt, destination, data_root, "--no-start") == linux_install.EXIT_REFUSED
    assert linux_install.main(["status", "--destination", str(destination)], state) == linux_install.EXIT_ERROR
    cited = re.findall(r"« ([^«»]*installer\.sh uninstall [^«»]*) »", attempt.err.getvalue())
    assert cited, attempt.err.getvalue()
    assert linux_install.main([*shlex.split(cited[0])[1:], "--oui"], removal) == 0, simulation.screen(removal)
    assert not partial.exists()
    row = troubleshooting_row("dossier de version partiel")
    emitted = "\n".join(simulation.screen(ctx) for ctx in (resumed, attempt, state, removal))
    assert_quotes_were_emitted(row[0], emitted)
    for expected in ("même commande", linux_install.INSTALL_MARKER, "commande citée"):
        assert expected in row[2], expected
    assert str(linux_install.EXIT_OK) in row[3] and str(linux_install.EXIT_REFUSED) in row[3], row[3]


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_troubleshooting_covers_the_previous_kit_launched_again(tmp_path, monkeypatch):
    """S17 (constat S02) : après une mise à jour, le kit de la version précédente, relancé, est refusé sans rien modifier ;
    le dépannage renvoie au retour arrière, jamais au retrait de cette version."""
    from tests.unit import test_dist_linux_install as simulation

    kit = simulation.make_kit(tmp_path, monkeypatch)
    home = simulated_home(tmp_path, monkeypatch, "maison")
    assert linux_install.main(["--oui", "--no-start"], simulation.context(kit)) == 0
    kit_b = simulation.second_kit(tmp_path, monkeypatch)
    assert linux_install.main(["update", "--oui", "--no-start"], simulation.context(kit_b)) == 0
    destination = simulation.default_paths(home)[0]
    before = simulation.pointer_of(destination)
    assert before["previous"]["kit_id"] == simulation.manifest_of(kit)["kit_id"]
    attempts = [simulation.context(kit), simulation.context(kit)]
    for argv, ctx in zip((["--oui", "--no-start"], ["update", "--oui", "--no-start"]), attempts, strict=True):
        assert linux_install.main(argv, ctx) == linux_install.EXIT_REFUSED, simulation.screen(ctx)
        assert simulation.pointer_of(destination) == before
    row = troubleshooting_row("kit de la version précédente")
    for ctx in attempts:
        assert_quotes_were_emitted(row[0], simulation.screen(ctx))
    assert "installer.sh rollback" in row[2] and "uninstall" not in row[2], row[2]
    assert row[3] == str(linux_install.EXIT_REFUSED)


def first_calls(function: str, names: set[str]) -> dict[str, int]:
    """Ligne du premier appel de chaque fonction de `names` dans la fonction `function` de linux_install.py."""
    tree = ast.parse(read("tools/dist/linux_install.py"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == function)
    found: dict[str, int] = {}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in names:
            found[sub.func.id] = min(found.get(sub.func.id, sub.lineno), sub.lineno)
    return found


def test_update_sequence_is_documented_in_the_order_of_the_code():
    """S17 : le « Déroulement » de la section 8.5 suit l'ordre des appels de linux_install.update avant la confirmation."""
    lines = first_calls("update", set(UPDATE_STEPS))
    assert set(lines) == set(UPDATE_STEPS), f"appels absents de update : {sorted(set(UPDATE_STEPS) - set(lines))}"
    paragraph = next(line for line in section(DEPLOIEMENT, "Mettre à jour").splitlines() if line.startswith("Déroulement"))
    positions = {name: paragraph.find(phrase) for name, phrase in UPDATE_STEPS.items()}
    assert all(position >= 0 for position in positions.values()), positions
    documented = [UPDATE_STEPS[name] for name in sorted(UPDATE_STEPS, key=positions.__getitem__)]
    coded = [UPDATE_STEPS[name] for name in sorted(UPDATE_STEPS, key=lines.__getitem__)]
    assert documented == coded, f"section 8.5 : {documented} ; linux_install.update : {coded}"


# --- KIT4-25 : sections destinées au kit et guide sans lien hors du kit ----------------------------------------------------

def test_kit_facing_sections_and_guide_resolve_inside_the_kit():
    outside = []
    for path, title, text in kit_sections():
        for target, anchor in link_targets(path, text):
            if not in_kit(target):
                outside.append(f"{path} « {title} » → {target}")
            elif anchor and target.endswith(".md"):
                assert anchor in check_docs.anchors(ROOT / target), f"{path} → {target}#{anchor}"
    assert not outside, f"liens hors du kit dans les sections destinées au kit : {outside}"
    documents = {path: read(path) for path, _ in kit_guide.SECTIONS.values()}
    guide = kit_guide.render(MANIFEST_DOUBLE, template=read(kit_guide.TEMPLATE), documents=documents, files=GUIDE_FILES)
    targets = link_targets("LISEZMOI.md", guide)
    assert len(targets) >= len(kit_guide.SECTIONS)
    for target, anchor in targets:
        assert in_kit(target) and (ROOT / target).is_file(), target
        assert anchor in check_docs.anchors(ROOT / target), f"{target}#{anchor}"


# --- W045, W041 et W046 : modèle par défaut et admission cités par la documentation ----------------------------------------

def shipped_markdown() -> list[str]:
    """Markdown du dépôt livrés dans le kit Linux (liste blanche du fabricant) : README.md, CHANGELOG.md et docs/."""
    candidates = ["README.md", "CHANGELOG.md", *(path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "docs").rglob("*.md")))]
    return [relative for relative in candidates if in_kit(relative)]


def test_documents_state_the_default_model_of_the_code():
    cli = read("services/runtime/cli.py")
    default = re.search(r'^DEFAULT_MODEL = "([^"]+)"', cli, re.MULTILINE).group(1)  # type: ignore[union-attr]
    profiles = ast.literal_eval(re.search(r"^MODEL_PROFILES = (\{.*\})$", cli, re.MULTILINE).group(1))  # type: ignore[union-attr]
    assert f"Profil par défaut : `config/{profiles[default]}`" in section(EXPLOITATION, "Conventions")
    stale = ("2B par défaut", "`qwen3.5:2b` (défaut)", "visent maintenant le profil 2B", "utilisent désormais le profil 2B",
             "ces commandes préparent `qwen3.5:2b`", "`qwen3.5:2b` par défaut", "installation par utilisateur en préparation",
             "Le profil actif est [`config/local16.yaml`]")
    shipped = shipped_markdown()
    # REL-U06 : le README fait partie du kit ; il ne doit pas démentir le guide LISEZMOI.md ni la section 8 du déploiement.
    assert "README.md" in shipped and "CHANGELOG.md" in shipped
    for relative in shipped:
        text = read(relative)
        for phrase in stale:
            assert phrase not in text, f"{relative} : « {phrase} »"
    stack = section("README.md", "Stack et versions")
    row = next((row for row in table_with_header(stack, "Couche") if row[0] == "Modèle de langue (défaut)"), None)
    assert row is not None, "README.md : ligne « Modèle de langue (défaut) » absente du tableau des versions"
    assert f"`{default}`" in row[1] and f"config/{profiles[default]}" in row[3], row
    assert f"`./rag.sh up` utilise `{default}` par défaut" in stack


def test_admission_values_quoted_by_the_troubleshooting_follow_the_profiles():
    text = section(DEPANNAGE, "Questions et génération")
    for profile in ("config/local16-4b.yaml", "config/local16.yaml"):
        resources = yaml.safe_load(read(profile))["resources"]
        peak, reserve = resources["initial_llm_load_peak_estimate_mib"], resources["host_available_min_mib"]
        assert f"{peak + reserve} Mio requis (pic prévu {peak} + réserve {reserve})" in text, profile


# --- Revue U2 (U2-01, U2-03) : procédures du dépannage et du déploiement exécutées sur l'installateur simulé ----------------

REPAIR_TITLE = "Réparer un programme installé avec le seul kit de sa version"
OLD_INSTALL_TITLE = "Installation faite par l'installateur de `78ec95c`"
# Double nommé FICHIER_PERDU : fichier du programme courant retiré à la main (programme endommagé, comme dans le message
# de rag.sh « Pour un fichier du programme manquant ») ; ECRIT_APRES : document importé après la dernière sauvegarde.
FICHIER_PERDU = "services/api/main.py"
ECRIT_APRES = "data/originaux/importe-apres-la-sauvegarde.pdf"


def procedure(relative: str, title: str, values: dict[str, str]) -> list[list[str]]:
    """Commandes des blocs sh d'une sous-section, dans l'ordre ; chaque emplacement <…> doit recevoir une valeur."""
    _, blocks = check_docs.split_code(section(relative, title))
    commands = []
    for language, _, lines in blocks:
        for line in lines if language == "sh" else []:
            if not line.strip():
                continue
            unknown = sorted(set(PLACEHOLDER.findall(line)) - set(values))
            assert not unknown, f"{relative} « {title} » : emplacement sans valeur {unknown} dans « {line.strip()} »"
            for name, value in values.items():
                line = line.replace(name, value)
            commands.append(shlex.split(line, comments=True))
    assert commands, f"{relative} « {title} » : aucune commande"
    return commands


def run_documented(simulation, words: list[str], kit: Path, runner) -> tuple[int, linux_install.Context]:
    """Commande `installer.sh` d'un document, lancée depuis le kit (`./installer.sh`) ou depuis le programme qu'elle nomme,
    et confirmée par --oui comme une réponse « o » au récapitulatif ; `status` n'écrit rien et ne le reçoit pas."""
    assert words[0].rsplit("/", 1)[-1] == linux_install.INSTALLER_NAME, words
    base = kit if words[0] == f"./{linux_install.INSTALLER_NAME}" else Path(words[0]).parent
    ctx = simulation.context(base, runner=runner)
    argv = words[1:] + ([] if words[1:2] == ["status"] else ["--oui"])
    return linux_install.main(argv, ctx), ctx


def damaged_installation(simulation, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str):
    """Installation démarrée sur ses données, avec une sauvegarde dans <données>/backups (celle de la mise à jour, ou
    `atelier sauvegarder`), un document importé ensuite et un fichier du programme courant perdu. `case` : « precedente »
    (version précédente gardée pour le retour arrière, seul le kit de la version courante en main), « seule » (une seule
    version), « autre-kit » (kit d'une autre version dont la mise à jour échoue, la version en place ne démarrant plus),
    « disparu » (une seule version, dont tout le dossier du programme a disparu après l'arrêt de l'atelier, comme sur un volume
    perdu). Rend la destination, les données, le kit en main et le double ProgrammeSimule commun à toutes les commandes."""
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    kit_a = simulation.make_kit(tmp_path, monkeypatch)
    runner = simulation.ProgrammeSimule()
    first = simulation.context(kit_a, runner=runner)
    assert simulation.install(first, destination, data_root) == 0, simulation.screen(first)
    kit = kit_a
    if case == "precedente":
        kit = simulation.second_kit(tmp_path, monkeypatch)
        updater = simulation.context(kit, runner=runner)
        assert linux_install.main(["update", "--destination", str(destination), "--oui"], updater) == 0, simulation.screen(updater)
    else:
        program = Path(simulation.pointer_of(destination)["current"]["program"])
        saver = simulation.context(program, runner=runner)
        assert linux_install.main(["run", "--destination", str(destination), "sauvegarder"], saver) == 0, simulation.screen(saver)
    assert simulation.pointer_of(destination)["current"]["started_on_data"] is True
    write(data_root, ECRIT_APRES, "document importé après la sauvegarde")
    current = simulation.pointer_of(destination)["current"]
    if case == "disparu":
        stopper = simulation.context(Path(current["program"]), runner=runner)
        assert linux_install.main(["run", "--destination", str(destination), "arreter"], stopper) == 0
        shutil.rmtree(current["program"])
        return destination, data_root, kit, runner
    (Path(current["program"]) / FICHIER_PERDU).unlink()
    if case == "autre-kit":
        stopper = simulation.context(Path(current["program"]), runner=runner)
        assert linux_install.main(["run", "--destination", str(destination), "arreter"], stopper) == 0
        runner.results[(current["kit_id"], "up")] = {"_rc": 1, "status": "failed", "message": "Démarrage refusé : module absent"}
        kit = simulation.second_kit(tmp_path, monkeypatch)
        attempt = simulation.context(kit, runner=runner)
        assert linux_install.main(["update", "--destination", str(destination), "--oui"], attempt) == linux_install.EXIT_ERROR
        assert "La version en place ne démarre pas" in attempt.err.getvalue(), simulation.screen(attempt)
    return destination, data_root, kit, runner


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def backups(data_root: Path) -> list[str]:
    return sorted(path.name for path in (data_root / "backups").iterdir() if (path / "manifest.json").is_file())


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
@pytest.mark.parametrize("case", ["precedente", "seule", "autre-kit", "disparu"])
def test_the_repair_procedure_keeps_the_active_data(tmp_path, monkeypatch, case):
    """U2-01, puis U4-02 (dossier du programme courant disparu) : la procédure de la section 10.4, exécutée telle qu'écrite
    depuis le seul kit en main, rend le fichier perdu ou le programme entier, garde la version du kit et la racine des données
    active, document importé après la sauvegarde compris ; aucune restauration n'a lieu. Programme disparu : `status` le
    signale (code 1) en renvoyant à cette procédure, et `uninstall --tout` ne fait que mettre le pointeur à jour."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    destination, data_root, kit, runner = damaged_installation(simulation, tmp_path, monkeypatch, case)
    saved = backups(data_root)
    commands = procedure(DEPANNAGE, REPAIR_TITLE, {"<destination>": str(destination), "<données>": str(data_root)})
    assert commands[0][1] == "status", commands
    text = section(DEPANNAGE, REPAIR_TITLE)
    for words in commands:
        code, ctx = run_documented(simulation, words, kit, runner)
        missing = case == "disparu" and words[1] == "status"
        expected = linux_install.EXIT_ERROR if missing else linux_install.EXIT_OK
        assert code == expected, f"« {' '.join(words)} » : {simulation.screen(ctx)}"
        if missing:
            output = cast(io.StringIO, ctx.out).getvalue()
            assert "programme courant absent" in output and "section 10.4" in output, simulation.screen(ctx)
        if case == "disparu" and words[1] == "uninstall":
            assert "Retirer du pointeur : " in simulation.screen(ctx), simulation.screen(ctx)
        if words[1] == "status":
            # La procédure fait relever ces deux lignes de l'état avant tout retrait.
            for line in ("Données : ", "Sauvegardes ("):
                assert line in text and line in ctx.out.getvalue(), line
    kit_id = simulation.manifest_of(kit)["kit_id"]
    pointer = simulation.pointer_of(destination)
    assert pointer["current"]["kit_id"] == kit_id and pointer["current"]["data_root"] == str(data_root)
    assert (destination / kit_id / FICHIER_PERDU).is_file()
    assert (data_root / ECRIT_APRES).is_file() and backups(data_root) == saved
    assert not [path for path in tmp_path.iterdir() if "-retour-" in path.name], "aucune restauration attendue"
    assert "restore" not in runner.commands()
    if case == "precedente":
        assert pointer["previous"] is None and "retour arrière" in text
    if case == "autre-kit":
        assert "La version en place ne démarre pas" in text


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_repair_procedure_removes_nothing_without_a_backup(tmp_path, monkeypatch):
    """U2-01, point 4 : sans sauvegarde, `status` ne liste aucune sauvegarde et la procédure s'arrête avant tout retrait ;
    retirer quand même les versions laisserait l'atelier sans programme, la reprise étant refusée."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    runner = simulation.ProgrammeSimule()
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root) == 0
    commands = procedure(DEPANNAGE, REPAIR_TITLE, {"<destination>": str(destination), "<données>": str(data_root)})
    text = section(DEPANNAGE, REPAIR_TITLE)
    first_removal = next(index for index, words in enumerate(commands) if words[1] == "uninstall")
    assert all(words[1] == "status" for words in commands[:first_removal]) and first_removal >= 1
    code, state = run_documented(simulation, commands[0], kit, runner)
    assert code == linux_install.EXIT_OK and "Sauvegardes (" not in state.out.getvalue(), simulation.screen(state)
    assert "aucune ligne « Sauvegardes (…) : »" in text and "ne rien désinstaller" in text
    # Ce que la condition évite, démontré sur le double : versions retirées, puis reprise refusée.
    outcomes = [run_documented(simulation, words, kit, runner) for words in commands[first_removal:]]
    assert outcomes[0][0] == linux_install.EXIT_OK and outcomes[-1][0] == linux_install.EXIT_REFUSED
    assert "Reprise refusée : aucune sauvegarde" in outcomes[-1][1].err.getvalue()
    assert simulation.pointer_of(destination)["current"] is None and "Reprise refusée" in text


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_repair_procedure_states_what_rollback_does_to_later_writes(tmp_path, monkeypatch):
    """U2-01, point 3 : après une mise à jour qui a démarré, `rollback` restaure la sauvegarde dans une racine neuve et
    laisse le document importé depuis dans l'ancienne racine ; la procédure l'écrit et ne le propose pas comme réparation."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    destination, data_root, kit, runner = damaged_installation(simulation, tmp_path, monkeypatch, "precedente")
    previous_kit = tmp_path / "kit"
    ctx = simulation.context(previous_kit, runner=runner)
    assert linux_install.main(["rollback", "--destination", str(destination), "--oui"], ctx) == 0, simulation.screen(ctx)
    active = Path(simulation.pointer_of(destination)["current"]["data_root"])
    assert active != data_root and not (active / ECRIT_APRES).exists() and (data_root / ECRIT_APRES).is_file()
    text = section(DEPANNAGE, REPAIR_TITLE)
    for statement in ("restaure la sauvegarde de la mise à jour dans une racine neuve", "restent dans l'ancienne racine"):
        assert statement in text, statement
    commands = procedure(DEPANNAGE, REPAIR_TITLE, {"<destination>": str(destination), "<données>": str(data_root)})
    assert all(words[1] != "rollback" for words in commands)


def test_offline_installation_refusals_lead_to_the_repair_procedure():
    """U2-01 : les deux refus de rag.sh qui renvoient à la section 10.4 y trouvent la procédure ; leur colonne Action y
    renvoie et ne propose plus le retour arrière."""
    assert "docs/exploitation/DEPANNAGE.md, section 10.4" in read("rag.sh")
    anchor = check_docs.slug(REPAIR_TITLE)
    assert anchor in check_docs.anchors(ROOT / DEPANNAGE)
    assert REPAIR_TITLE in section(DEPANNAGE, "Lanceur, commande `atelier` et `rag.sh`")
    for cause in ("dans une installation, avec ou sans", "Environnement `.venv` du programme installé absent"):
        action = troubleshooting_row(cause)[2]
        assert f"(#{anchor})" in action and "rollback" not in action, action


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_deployment_updates_an_installation_made_by_78ec95c(tmp_path, monkeypatch):
    """U2-03 : installation de 78ec95c (chemins explicites, ni registre, ni entrée de menu, ni commande). `./installer.sh`
    sans argument ne la retrouve pas et le dit ; les commandes de la section 8.5, exécutées telles qu'écrites, la mettent à
    jour, l'inscrivent au registre et lui ajoutent l'intégration au bureau ; `status` signale l'absence de cette intégration
    comme la section 8.8 l'écrit."""
    from tests.unit import test_dist_linux_install as simulation

    home = simulated_home(tmp_path, monkeypatch, "maison")
    kit_a = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "ailleurs" / "programmes", tmp_path / "ailleurs" / "donnees"
    assert simulation.install(simulation.context(kit_a), destination, data_root, "--no-start") == 0
    simulation.strip_desktop_integration(destination, home)
    kit_b = simulation.second_kit(tmp_path, monkeypatch)
    text = section(DEPLOIEMENT, OLD_INSTALL_TITLE)
    implicit = simulation.context(kit_b)
    assert linux_install.main(["--no-start"], implicit) == linux_install.EXIT_REFUSED
    for line in ("Installation existante : aucune trouvée (registre, emplacement par défaut)",):
        assert line in text and line in simulation.screen(implicit), line
    assert not simulation.default_paths(home)[1].exists()
    before = simulation.context(kit_a)
    linux_install.main(["status", "--destination", str(destination)], before)
    status_text = section(DEPLOIEMENT, "État, réparation, vérification et modèle principal")
    assert "Intégration au bureau : aucune" in before.out.getvalue() and "Intégration au bureau : aucune" in status_text
    assert "repair --menu" in status_text
    program = destination / simulation.manifest_of(kit_b)["kit_id"]
    commands = procedure(DEPLOIEMENT, OLD_INSTALL_TITLE, {"<destination>": str(destination), "<programme>": str(program)})
    assert [words[1] for words in commands] == ["update", "repair"], commands
    runner = simulation.ProgrammeSimule()
    for index, words in enumerate(commands):
        code, ctx = run_documented(simulation, words, kit_b, runner)
        assert code == linux_install.EXIT_OK, f"« {' '.join(words)} » : {simulation.screen(ctx)}"
        if index == 0:
            assert "repair --menu" in simulation.screen(ctx) and simulation.registry(home) == [str(destination)]
            between = simulation.context(program)
            linux_install.main(["status"], between)
            assert "Intégration au bureau : aucune" in between.out.getvalue(), simulation.screen(between)
    assert (simulation.applications(home) / "atelier-documentaire.desktop").is_file() and (home / ".local/bin/atelier").is_file()
    after = simulation.context(program)
    assert linux_install.main(["status"], after) == linux_install.EXIT_OK, simulation.screen(after)
    assert "Intégration au bureau : entrée de menu" in after.out.getvalue()
    for statement in ("garde la racine des données", "inscrit l'installation au registre"):
        assert statement in text, statement
    assert simulation.pointer_of(destination)["current"]["data_root"] == str(data_root)
    space = troubleshooting_row("Place insuffisante sur le volume de la destination")[2]
    assert "update --destination" in space and f"(../deploiement/DEPLOIEMENT.md#{check_docs.slug(OLD_INSTALL_TITLE)})" in space


# --- Revue U3 (U3-10, U3-11, S3-12) : portée de la vérification avant exécution, options, refus et interruptions -----------

SCOPE_TITLE = "Ce qui s'exécute avant la vérification"
# Dossier de CPython du kit factice de test_dist_linux_scripts (python.executable de son manifeste, sans bin/python3.12) ;
# les documents l'écrivent <CPython>.
CPYTHON = ".runtime/python/cpython"
WRITTEN_WITHOUT_SUMMARY = ("repair", "modele")
# Le modèle de menace fixé pour R26-KIT-04 n'est pas recopié ici : installer_sh_threat_model() le lit dans l'en-tête
# d'install.sh, comme test_dist_kit_guide (U6-03, QA6-02 : une copie en minuscules figeait une seconde forme du texte imposé).
# Début de la colonne « Contrôle avant l'exécution » du tableau, et confrontation propre à chacun (QA5-03 : une ligne dont le
# contrôle ne commence par aucun de ces préfixes n'est confrontée à rien, et fait échouer l'essai).
CONTROL_KINDS = ("Aucun contrôle après l'extraction", "Empreinte", "Refusé", "Admis", "Ignoré", "Hachés seulement pendant la copie")
# Lignes « Refusé » dont l'altération n'est pas un ajout (R4S-01, ronde 5) : début de la colonne « Fichier du kit ».
LINKED_FILE_ROW = "Fichier vérifié remplacé par un lien"
LINKED_FOLDER_ROW = "Dossier du chemin d'un fichier vérifié remplacé par un lien"
CHANGED_TYPE_ROW = "Entrée de `<CPython>/` dont le type a changé"
ALTERED_MESSAGE = "Interpréteur ou installateur du kit altéré"


def plain(text: str) -> str:
    """Texte sans accents graves ni gras, espaces normalisés : forme sous laquelle le modèle de menace est cherché."""
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", ""))


def installer_sh_threat_model() -> str:
    """Modèle de menace de l'en-tête de tools/dist/install.sh (lignes de commentaire réunies, « # » retirés, puis `plain`) :
    texte imposé pour R26-KIT-04, à écrire tel quel là où la garantie de la vérification du kit est décrite. Même lecture que
    installer_sh_threat_model() de test_dist_kit_guide, qui le confronte au guide."""
    header = read("tools/dist/install.sh").split("\nset -eu\n", 1)[0]
    text = plain(" ".join(line.strip().removeprefix("#") for line in header.splitlines()))
    found = re.search(r"Modèle de menace : (.+? contrôlée avant extraction\.)", text)
    assert found, "tools/dist/install.sh : modèle de menace absent de l'en-tête"
    return found.group(1)


def scope_rows() -> list[list[str]]:
    """Lignes du tableau « Ce qui s'exécute avant la vérification » (déploiement, section 8.3), en-tête retiré."""
    return table_with_header(section(DEPLOIEMENT, SCOPE_TITLE), "Fichier du kit")[1:]


def backticked(cell: str) -> list[str]:
    """Chaînes citées entre accents graves dans une cellule, <CPython> remplacé."""
    return [span.replace("<CPython>", CPYTHON) for span in re.findall(r"`([^`]+)`", cell)]


def documented_paths(cell: str) -> list[str]:
    """Fichiers cités entre accents graves dans une cellule (au moins une barre oblique ou un point ; un dossier, terminé par
    une barre oblique, n'en est pas un), <CPython> remplacé."""
    return [path for path in backticked(cell) if ("/" in path or "." in path) and not path.endswith("/")]


def documented_folders(cell: str) -> list[str]:
    """Dossiers cités entre accents graves dans une cellule (terminés par une barre oblique), <CPython> remplacé."""
    return [path for path in backticked(cell) if path.endswith("/")]


def instance_of(pattern: str) -> str:
    """Chemin concret d'un motif documenté : chaque `*` devient « ajout »."""
    return pattern.replace("*", "ajout")


def installer_sh_patterns() -> set[str]:
    """Motifs des boucles de refus d'install.sh (`for pattern in … ; do` pour les modules de l'installateur, `for path in
    "$kit/$python_root"… ; do` pour les fichiers lus par l'interpréteur), tels que le shell les lit, relatifs au kit et
    écrits avec le dossier de CPython du kit factice."""
    text = read("tools/dist/install.sh")
    loops = re.findall(r"for (?:pattern|path) in (.*?); do", text, re.DOTALL)
    assert loops, "tools/dist/install.sh : boucles des refus introuvables"
    found = set()
    for loop in loops:
        for word in shlex.split(loop.replace("\\\n", " ")):
            if word.startswith("$kit/$python_root"):
                found.add(CPYTHON + word.removeprefix("$kit/$python_root"))
            elif not word.startswith("$"):
                found.add(word)
    return found


def installer_sh_checked_names() -> set[str]:
    """Fichiers qu'install.sh contrôle par empreinte avant tout (`for name in … ; do`), "$python_relative" écrit avec
    l'interpréteur du kit factice."""
    loops = re.findall(r"for name in (.*?); do", read("tools/dist/install.sh"), re.DOTALL)
    assert len(loops) == 1, "tools/dist/install.sh : boucle des empreintes introuvable"
    return {f"{CPYTHON}/bin/python3.12" if word == "$python_relative" else word for word in shlex.split(loops[0].replace("\\\n", " "))}


def installer_sh_scanned_folders() -> set[str]:
    """Dossiers qu'install.sh parcourt par find pour refuser toute entrée absente des listes, écrits avec le <CPython> du kit
    factice : départ écrit en clair (`find -H "$kit/$python_root"`) ou par une variable (`start=$kit/$python_root`, puis
    `-H "$start…"`) ; les suffixes « /. » d'un même départ désignent le même dossier."""
    text = read("tools/dist/install.sh")
    starts = re.findall(r'find"? -H "\$kit/\$python_root([^"]*)"', text)
    variable = re.search(r"^\s*start=\$kit/\$python_root(\S*)$", text, re.MULTILINE)
    if variable:
        starts += [variable.group(1) + rest for rest in re.findall(r'-H "\$start([^"]*)"', text)]
    found = {CPYTHON + "/" + "/".join(part for part in rest.split("/") if part not in ("", ".")) for rest in starts}
    found = {folder if folder.endswith("/") else folder + "/" for folder in found}
    assert found, "tools/dist/install.sh : parcours du dossier de l'interpréteur introuvable"
    return found


def new_folder(tmp_path: Path, label: str) -> Path:
    folder = tmp_path / f"{label}-{len(list(tmp_path.glob(f'{label}-*')))}"
    folder.mkdir()
    return folder


def run_installer_sh(folder: Path, kit: Path):
    """Vrai installer.sh du kit factice (`--aide`), sur le poste simulé aarch64 de test_runtime_launchers_sh."""
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import fake_host

    return scripts.run(kit / "installer.sh", "--aide", fakes=fake_host(folder, "Linux", "aarch64"))


def launched(folder: Path, result) -> bool:
    """installer.sh a passé la main à l'interpréteur du kit factice (marqueur) et s'est terminé sans erreur."""
    return (folder / "interpreteur-lance").exists() and result.returncode == 0


def installer_sh_outcome(tmp_path: Path, relative: str, *, real_python: bool = False) -> str:
    """Lance le vrai installer.sh (`--aide`) sur un kit factice de test_dist_linux_scripts auquel `relative` a été ajouté,
    absent de SHA256SUMS, avec le contenu du double `injected` (témoin écrit, puis code 99). Rend « refusé » (installer.sh
    s'arrête avant Python), « exécuté » (le fichier ajouté a été importé : témoin) ou « accepté » (Python lancé, rien
    d'ajouté exécuté). `real_python` : interpréteur du kit relié au CPython 3.12 du dépôt et vrais scripts de l'installateur."""
    from tests.unit import test_dist_linux_scripts as scripts

    folder = new_folder(tmp_path, "essai")
    kit = scripts.kit_with_real_python(folder) if real_python else scripts.fake_kit(folder)
    witness = folder / "temoin"
    path = kit / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scripts.injected(witness), encoding="utf-8")
    result = run_installer_sh(folder, kit)
    started = (folder / "interpreteur-lance").exists() or real_python and result.returncode != 1
    if result.returncode == 1 and not started:
        assert f"{relative} ajouté au kit, absent de SHA256SUMS" in result.stderr, result.stderr
        return "refusé"
    if witness.exists():
        return "exécuté"
    assert result.returncode == 0, result.stdout + result.stderr
    return "accepté"


def modified_listed_outcome(tmp_path: Path, relative: str) -> tuple[str, str]:
    """Double FICHIER_LISTE_MODIFIE : `relative` du kit factice (créé et inscrit à SHA256SUMS s'il n'y est pas), puis modifié
    après l'extraction (ligne ajoutée). Rend (« accepté » si installer.sh lance l'interpréteur, sinon « refusé », sortie
    d'erreur)."""
    from tests.unit import test_dist_linux_scripts as scripts

    folder = new_folder(tmp_path, "modifie")
    kit = scripts.fake_kit(folder)
    path = kit / relative
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fichier livré\n", encoding="utf-8")
        scripts.write_links(kit, {}, extra=(relative,))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n# modifié après l'extraction\n")
    result = run_installer_sh(folder, kit)
    return ("accepté" if launched(folder, result) else "refusé"), result.stderr


def lost_listed_outcome(tmp_path: Path, relative: str, double: str) -> tuple[str, str]:
    """Ronde 6 de l'installateur (R5S-02, U6-05) : `relative` du kit factice (créé et inscrit à SHA256SUMS s'il n'y est pas),
    puis retiré (double FICHIER_ABSENT : copie ou extraction incomplètes) ou privé de son droit de lecture (double
    FICHIER_ILLISIBLE, mode 0200 : droits perdus ; le compte root lirait encore le fichier). Rend (« accepté » ou « refusé »,
    sortie d'erreur)."""
    from tests.unit import test_dist_linux_scripts as scripts

    folder = new_folder(tmp_path, double.lower())
    kit = scripts.fake_kit(folder)
    path = kit / relative
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fichier livré\n", encoding="utf-8")
        scripts.write_links(kit, {}, extra=(relative,))
    assert launched(folder, run_installer_sh(folder, kit)), f"témoin refusé : {relative}"
    (folder / "interpreteur-lance").unlink()
    if double == "FICHIER_ABSENT":
        path.unlink()
        result = run_installer_sh(folder, kit)
    else:
        mode = path.stat().st_mode
        path.chmod(0o200)
        try:
            result = run_installer_sh(folder, kit)
        finally:
            path.chmod(mode)
    return ("accepté" if launched(folder, result) else "refusé"), result.stderr


def linked_outcome(tmp_path: Path, relative: str) -> tuple[str, str]:
    """Double COPIE_IDENTIQUE_HORS_KIT : `relative`, fichier du kit factice (créé et inscrit à SHA256SUMS s'il n'y est pas), ou
    dossier terminé par « / », remplacé par un lien absolu vers une copie identique placée hors du kit (mêmes octets, mêmes
    droits). Le kit intact est d'abord lancé en témoin. Rend (« accepté » ou « refusé », sortie d'erreur)."""
    from tests.unit import test_dist_linux_scripts as scripts

    folder = new_folder(tmp_path, "lien")
    kit = scripts.fake_kit(folder)
    target = relative.rstrip("/")
    if not (kit / target).exists():
        (kit / target).parent.mkdir(parents=True, exist_ok=True)
        (kit / target).write_text("# fichier livré\n", encoding="utf-8")
        scripts.write_links(kit, {}, extra=(target,))
    assert launched(folder, run_installer_sh(folder, kit)), f"témoin sans lien refusé : {relative}"
    (folder / "interpreteur-lance").unlink()
    scripts.linked_to_a_copy(kit, target, folder / "hors-du-kit")
    result = run_installer_sh(folder, kit)
    return ("accepté" if launched(folder, result) else "refusé"), result.stderr


def changed_type_outcomes(tmp_path: Path, relative: str) -> dict[str, tuple[str, str]]:
    """Doubles LIEN_DEVENU_FICHIER, FICHIER_DEVENU_TUBE et, depuis la ronde 6 de l'installateur (U6-06, QA6-01),
    LIEN_DEVENU_DOSSIER_VIDE et FICHIER_DEVENU_DOSSIER_VIDE, sur l'entrée `relative` du kit factice, chacun après un témoin
    accepté : lien déclaré dans SYMLINKS remplacé par un fichier ordinaire ou par un dossier vide ; fichier inscrit à SHA256SUMS
    remplacé par un tube ou par un dossier vide. Rend {double : (« accepté » ou « refusé », sortie d'erreur)}."""
    from tests.unit import test_dist_linux_scripts as scripts

    outcomes = {}
    for double in ("LIEN_DEVENU_FICHIER", "FICHIER_DEVENU_TUBE", "LIEN_DEVENU_DOSSIER_VIDE", "FICHIER_DEVENU_DOSSIER_VIDE"):
        folder = new_folder(tmp_path, "type")
        kit = scripts.fake_kit(folder)
        path = kit / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if double.startswith("LIEN_DEVENU_"):
            target = path.parent / "cible-du-lien"
            target.write_text("# cible livrée\n", encoding="utf-8")
            os.symlink(target.name, path)
            scripts.write_links(kit, {relative: target.name}, extra=(target.relative_to(kit).as_posix(),))
        else:
            path.write_text("# fichier livré\n", encoding="utf-8")
            scripts.write_links(kit, {}, extra=(relative,))
        assert launched(folder, run_installer_sh(folder, kit)), f"témoin refusé : {relative} ({double})"
        (folder / "interpreteur-lance").unlink()
        path.unlink()
        if double == "LIEN_DEVENU_FICHIER":
            path.write_bytes(b"contenu quelconque, jamais hach\xc3\xa9")
        elif double.endswith("_DOSSIER_VIDE"):
            path.mkdir()
        elif sys.platform != "win32":  # os.mkfifo n'existe que sous Unix ; les essais qui l'emploient sont sautés sous Windows
            os.mkfifo(path)
        result = run_installer_sh(folder, kit)
        outcomes[double] = ("accepté" if launched(folder, result) else "refusé"), result.stderr
    return outcomes


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_the_pre_execution_table_matches_what_installer_sh_checks(tmp_path):
    """U3-11 et S3-12, puis U5-01, QA5-03, U4-07 et, ronde 5, R4S-01, U5-04 : chaque ligne du tableau « Ce qui s'exécute avant
    la vérification » qui ne concerne pas la mise à jour est confrontée au vrai installer.sh selon le début de sa colonne
    Contrôle (CONTROL_KINDS) ; une ligne sans préfixe connu fait échouer l'essai. « Empreinte » : chaque fichier cité, modifié,
    arrête installer.sh, la liste qu'il hache y figure, et l'interpréteur sans droit d'exécution est refusé avec sa cause ;
    « Refusé » : motifs des boucles d'install.sh (égalité exacte), dossier qu'il parcourt par find (chaque exemple ajouté est
    refusé), fichier ou dossier vérifié remplacé par un lien vers une copie identique, entrée de <CPython> dont le type a changé,
    chacun refusé avec le message cité, et lien de dossier déclaré dans SYMLINKS admis ; « Admis » et « Ignoré » : exemples
    ajoutés acceptés ; « Hachés seulement pendant la copie » : fichier listé puis modifié accepté ; « Aucun contrôle après
    l'extraction » : installer.sh modifié exécuté. Ronde 6 (R5S-02, U6-05, U6-06) : fichier haché ou fichier listé de la
    bibliothèque standard absent (FICHIER_ABSENT) ou sans droit de lecture (FICHIER_ILLISIBLE) refusé avec le message cité,
    jamais annoncé altéré ; lien ou fichier inscrits devenus dossier vide refusés."""
    from tests.unit import test_dist_linux_scripts as scripts

    rows = [row for row in scope_rows() if not row[0].startswith("Mise à jour")]
    unconfronted = [row[0][:80] for row in rows if not row[2].startswith(CONTROL_KINDS)]
    assert not unconfronted, f"lignes du tableau dont le contrôle n'est confronté à rien : {unconfronted}"
    kinds = {kind: [row for row in rows if row[2].startswith(kind)] for kind in CONTROL_KINDS}
    assert all(kinds.values()), {kind: len(found) for kind, found in kinds.items()}
    assert not [row for row in rows if "Accepté par `installer.sh`" in row[2]], "un lien à la place d'un fichier vérifié est refusé"

    # installer.sh lui-même (U4-07) : rien ne le contrôle après l'extraction ; l'empreinte de l'archive l'ancre.
    first = kinds["Aucun contrôle après l'extraction"]
    assert len(first) == 1 and backticked(first[0][0])[:1] == ["installer.sh"], first
    assert "<kit_id>.tar.sha256" in first[0][2] and "copie" in first[0][2], first[0][2]
    for name in ("kit-manifest.json", "SHA256SUMS", "SYMLINKS"):
        assert f"`{name}`" in first[0][1], f"ligne installer.sh : lecture de {name} avant toute vérification"
    outcome, err = modified_listed_outcome(tmp_path, "installer.sh")
    assert outcome == "accepté", err

    # Fichiers hachés par installer.sh avant tout : chacun, modifié, l'arrête ; sa boucle n'en contrôle aucun autre ; un
    # interpréteur sans droit d'exécution est refusé avec la cause que cite la ligne (SANS_BIT_X).
    checked = kinds["Empreinte"]
    assert len(checked) == 1, checked
    witness_kit = scripts.fake_kit(new_folder(tmp_path, "temoin"))
    files = [span for span in backticked(checked[0][0]) if (witness_kit / span).is_file()]
    assert installer_sh_checked_names() <= set(files), (installer_sh_checked_names(), files)
    assert f"{CPYTHON}/lib/libpython3.12.so.1.0" in files and "`lib*.so*`" in checked[0][0], checked[0][0]
    for relative in files:
        outcome, err = modified_listed_outcome(tmp_path, relative)
        assert outcome == "refusé" and ALTERED_MESSAGE in err, (relative, err)
    folder = new_folder(tmp_path, "sans-bit-x")
    kit = scripts.fake_kit(folder)
    (kit / CPYTHON / "bin/python3.12").chmod(0o644)
    result = run_installer_sh(folder, kit)
    assert result.returncode == 1 and not launched(folder, result), result.stderr
    assert_quote_emitted(quote_with(checked[0][2], "sans droit d'exécution"), result.stderr)
    # Ronde 6 (R5S-02, U6-05) : chaque fichier haché, absent (FICHIER_ABSENT) ou sans droit de lecture (FICHIER_ILLISIBLE, hors
    # root), est nommé comme tel avant tout lancement, jamais annoncé altéré, par le message que cite la ligne ; l'interpréteur
    # absent a son propre message, cité aussi.
    interpreter = f"{CPYTHON}/bin/python3.12"
    for relative in files:
        for double, key in (("FICHIER_ABSENT", "Interpréteur du kit absent" if relative == interpreter else "absent du kit, alors que"),
                            ("FICHIER_ILLISIBLE", "sans droit de lecture")):
            if double == "FICHIER_ILLISIBLE" and running_as_root():
                continue
            outcome, err = lost_listed_outcome(tmp_path, relative, double)
            assert outcome == "refusé" and ALTERED_MESSAGE not in err and relative in err, (relative, double, err)
            assert_quote_emitted(quote_with(checked[0][2], key), err)

    # Refus de ce qui est ajouté : motifs des boucles d'install.sh, puis dossier de l'interpréteur parcouru par find (R3S-01).
    refused = kinds["Refusé"]
    special = {label: [row for row in refused if row[0].startswith(label)] for label in (LINKED_FILE_ROW, LINKED_FOLDER_ROW, CHANGED_TYPE_ROW)}
    assert all(len(found) == 1 for found in special.values()), {label: len(found) for label, found in special.items()}
    added_rows = [row for row in refused if not row[0].startswith(tuple(special))]
    pattern_rows = [row for row in added_rows if not documented_folders(row[0])]
    folder_rows = [row for row in added_rows if documented_folders(row[0])]
    assert {path for row in pattern_rows for path in documented_paths(row[0])} == installer_sh_patterns()
    for row in pattern_rows:
        for pattern in documented_paths(row[0]):
            relative = instance_of(pattern)
            outcome = installer_sh_outcome(tmp_path, relative, real_python=relative.endswith(".py"))
            assert outcome == "refusé", f"{pattern} : {outcome}, alors que le tableau le dit refusé"
    assert len(folder_rows) == 1, folder_rows
    folders = documented_folders(folder_rows[0][0])
    assert set(folders) == installer_sh_scanned_folders(), (folders, installer_sh_scanned_folders())
    examples = documented_paths(folder_rows[0][0])
    assert len(examples) >= 4, examples
    for relative in examples:
        assert relative.startswith(tuple(folders)), relative
        outcome = installer_sh_outcome(tmp_path, relative, real_python=relative.endswith(".py"))
        assert outcome == "refusé", f"{relative} : {outcome}, alors que le tableau refuse toute entrée ajoutée sous {folders}"

    # Fichier vérifié (fichier haché, module ou fichier de démarrage listés, entrée de <CPython>) remplacé par un lien vers une
    # copie identique hors du kit (COPIE_IDENTIQUE_HORS_KIT) : refusé avant tout lancement, avec le message cité.
    row = special[LINKED_FILE_ROW][0]
    examples = documented_paths(row[0])
    assert len(examples) >= 3 and set(examples) & set(files) and any(path.startswith(f"{CPYTHON}/lib/python3") for path in examples), examples
    for relative in examples:
        outcome, err = linked_outcome(tmp_path, relative)
        assert outcome == "refusé", f"{relative} remplacé par un lien : {outcome}, alors que le tableau le dit refusé ; {err}"
        assert_quotes_were_emitted(row[2], err)

    # Dossier du chemin d'un fichier vérifié remplacé par un lien : refusé ; un lien de dossier déclaré dans SYMLINKS est suivi.
    row = special[LINKED_FOLDER_ROW][0]
    examples = documented_folders(row[0])
    assert len(examples) >= 3 and f"{CPYTHON}/lib/" in examples, examples
    for relative in examples:
        outcome, err = linked_outcome(tmp_path, relative)
        assert outcome == "refusé", f"{relative} remplacé par un lien : {outcome}, alors que le tableau le dit refusé ; {err}"
        assert_quotes_were_emitted(row[2], err)
    assert "déclaré dans `SYMLINKS` est suivi" in row[0], row[0]
    folder = new_folder(tmp_path, "lien-declare")
    kit = scripts.fake_kit(folder)
    os.rename(kit / CPYTHON, kit / f"{CPYTHON}-3.12.14")
    os.symlink("cpython-3.12.14", kit / CPYTHON)
    scripts.write_links(kit, {CPYTHON: "cpython-3.12.14"})
    assert launched(folder, run_installer_sh(folder, kit)), "lien de dossier déclaré dans SYMLINKS refusé"

    # Entrée de <CPython> dont le type a changé (LIEN_DEVENU_FICHIER, FICHIER_DEVENU_TUBE) : refusée, avec les messages cités.
    row = special[CHANGED_TYPE_ROW][0]
    examples = documented_paths(row[0])
    assert len(examples) >= 2 and all(path.startswith(f"{CPYTHON}/") for path in examples), examples
    quotes = {double: [quote for quote in quoted_messages(row[2]) if key in quote]
              for double, key in (("LIEN_DEVENU_FICHIER", "n'est plus un lien"), ("FICHIER_DEVENU_TUBE", "n'est pas un fichier ordinaire"),
                                  ("LIEN_DEVENU_DOSSIER_VIDE", "n'est plus un lien"),
                                  ("FICHIER_DEVENU_DOSSIER_VIDE", "n'est pas un fichier ordinaire"))}
    assert all(len(found) == 1 for found in quotes.values()), quotes
    # Ronde 6 (U6-06, QA6-01) : un dossier, même vide, à la place d'un lien ou d'un fichier inscrits est refusé ; la ligne le dit.
    for statement in ("lien de `SYMLINKS` devenu fichier ou dossier, même vide", "fichier de `SHA256SUMS` devenu dossier, même vide"):
        assert statement in row[0], f"ligne « {CHANGED_TYPE_ROW} » : « {statement} » attendu ; {row[0]}"
    for relative in examples:
        for double, (outcome, err) in changed_type_outcomes(tmp_path, relative).items():
            assert outcome == "refusé", f"{relative} ({double}) : {outcome}, alors que le tableau la dit refusée ; {err}"
            for fragment in (piece.strip() for piece in quotes[double][0].split("…")):
                assert fragment in err, f"{relative} ({double}) : « {fragment} » absent de « {err.strip()} »"

    # Admis (bytecode des dossiers __pycache__ d'un programme installé) et ignorés (hors du dossier de l'interpréteur).
    for kind, expected_reading in (("Admis", "Jamais lu"), ("Ignoré", "Jamais importé")):
        for row in kinds[kind]:
            assert documented_paths(row[0]) and row[1].startswith(expected_reading), row
            for relative in documented_paths(row[0]):
                outcome = installer_sh_outcome(tmp_path, relative, real_python=relative.endswith(".py"))
                assert outcome == "accepté", f"{relative} : {outcome} ; tableau : {row[2]}"

    # Fichiers listés de la bibliothèque standard : modifiés, ils passent installer.sh (hachés seulement à la copie) ; absents
    # ou sans droit de lecture (ronde 6 : R5S-02, U6-05), ils sont refusés avant, avec les messages que cite la ligne.
    for row in kinds["Hachés seulement pendant la copie"]:
        examples = [path for path in documented_paths(row[0]) if "*" not in path]
        assert examples, row
        for relative in examples:
            outcome, err = modified_listed_outcome(tmp_path, relative)
            assert outcome == "accepté", f"{relative} listé puis modifié : {outcome}, alors que le tableau ne le hache qu'à la copie ; {err}"
            for double, key in (("FICHIER_ABSENT", "absent du kit, alors que"), ("FICHIER_ILLISIBLE", "sans droit de lecture")):
                if double == "FICHIER_ILLISIBLE" and running_as_root():
                    continue
                outcome, err = lost_listed_outcome(tmp_path, relative, double)
                assert outcome == "refusé" and relative in err, f"{relative} ({double}) : {outcome}, alors que le tableau le dit refusé ; {err}"
                assert_quote_emitted(quote_with(row[2], key), err)


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_update_rows_of_the_pre_execution_table_match_the_targeted_verification(tmp_path, monkeypatch):
    """U3-11 et S3-12 : les lignes « Mise à jour » du tableau sont confrontées à la vérification ciblée réelle
    (linux_install.verify_targeted, pre_copy) sur un kit fabriqué par test_dist_linux_install : fichiers exécutés avant la
    copie (PRE_COPY_FILES) et fichiers ajoutés dans les paquets que la dérivation importe, refusés ou non selon le tableau."""
    from tests.unit import test_dist_linux_install as simulation

    rows = [row for row in scope_rows() if row[0].startswith("Mise à jour")]
    executed = [row for row in rows if "linux_profiles.py" in row[0]]
    assert len(executed) == 1 and "profils livrés" in executed[0][0], rows
    assert {path for path in documented_paths(executed[0][0]) if "/" in path} == set(linux_install.PRE_COPY_FILES)
    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    manifest = simulation.manifest_of(kit)
    probes = [(row, instance_of(pattern)) for row in rows if row[2].startswith(("Refusé", "Aucun"))
              for pattern in documented_paths(row[0])]
    assert any(row[2].startswith("Refusé") for row, _ in probes), rows
    for row, relative in probes:
        path = kit / relative
        created = [parent for parent in reversed(path.parents) if not parent.exists()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x7fELF ou bytecode ajout\xc3\xa9\n")
        ctx = simulation.context(kit)
        try:
            linux_install.verify_targeted(ctx, manifest, linux_install.Report(ctx, "update"), pre_copy=True)
            refused = False
        except linux_install.InstallError as error:
            refused = f"{relative} ajouté, absent de SHA256SUMS" in str(error) and error.code == linux_install.EXIT_REFUSED
            assert refused, str(error)
        finally:
            path.unlink()
            for folder in reversed(created):
                folder.rmdir()
        assert refused == row[2].startswith("Refusé"), f"{relative} : {'refusé' if refused else 'accepté'} ; tableau : {row[2]}"


# Affirmations périmées : vérification complète avant exécution (U3-11, S3-12), puis, après R3S-01 (U5-01, QA5-03, U4-07),
# bibliothèque standard seule exécutée avant contrôle, ou fichier ajouté sous <CPython> ignoré ; enfin, après la ronde 5 de
# l'installateur (R4S-01, U5-04, U4-03), lien vers une copie identique accepté par installer.sh, interpréteur sans droit
# d'exécution laissé au shell, find confondu avec un dossier illisible, verifier qui ne résout pas l'installation.
STALE_SCOPE_PHRASES = ("vérifie le nouveau kit avant d'exécuter son code",
                       "importer un module ajouté au kit à la place de la bibliothèque standard ou d'un module vérifié",
                       "refuse tout module absent de `SHA256SUMS` que Python importerait",
                       "rien n'est désigné ni exécuté depuis le kit sans avoir été vérifié",
                       "Seule la bibliothèque standard du kit s'exécute avant tout contrôle",
                       "seule la bibliothèque standard du CPython du kit s'exécute avant d'être hachée",
                       "Hachée seulement pendant la copie ; aucun contrôle avant",
                       "sauf un fichier qu'une recherche par nom trouverait à la place d'un module vérifié ou qui changerait",
                       "Accepté par `installer.sh`, qui hache la cible du lien", "`installer.sh` accepte un tel lien",
                       "n'est refusé qu'à la copie", "un `installer.sh` ou un interpréteur privé de son droit d'exécution",
                       "nécessaire pour vérifier le kit avant de l'exécuter", "il parle alors à tort des droits de lecture",
                       "ne tient compte ni d'une installation existante")
# Phrase qui énumère ce qui s'exécute avant d'être contrôlé : elle doit nommer installer.sh (U4-07, QA5-05).
ONLY_BEFORE = re.compile(r"\b[Ss]eule?s?\b(?:(?!\. )[^;\n])*?s'exécute(?:nt)? avant")


def test_no_text_promises_more_than_the_pre_execution_checks():
    """U3-11 et S3-12, puis U5-01, QA5-03 et U4-07 : ni le CHANGELOG ni les documents n'annoncent une vérification complète
    avant exécution, ni la bibliothèque standard comme seul code exécuté avant contrôle ; toute phrase « seul(s) … s'exécute(nt)
    avant » nomme installer.sh ; l'entrée R26-KIT-04 du CHANGELOG nomme l'exception de la bibliothèque standard, porte le
    modèle de menace tel quel et renvoie au tableau de la section 8.3, que le passage de la section 8.2 sur les fichiers
    ajoutés cite aussi ; ce passage nomme le refus de toute entrée ajoutée sous <CPython>."""
    for relative in sorted({*shipped_markdown(), DEPLOIEMENT, DEPANNAGE, EXPLOITATION, "docs/specifications/SPECIFICATIONS.md"}):
        text = read(relative)
        for phrase in STALE_SCOPE_PHRASES:
            assert phrase not in text, f"{relative} : « {phrase} »"
        for match in ONLY_BEFORE.finditer(text):
            assert "installer.sh" in match.group(0), f"{relative} : énumération sans installer.sh : « {match.group(0).strip()[:160]} »"
    anchor = check_docs.slug(SCOPE_TITLE)
    assert anchor in check_docs.anchors(ROOT / DEPLOIEMENT)
    entry = next(line for line in read("CHANGELOG.md").splitlines() if "(R26-KIT-04)" in line)
    assert f"docs/deploiement/DEPLOIEMENT.md#{anchor}" in entry and "bibliothèque standard" in entry, entry
    assert installer_sh_threat_model() in plain(entry), "CHANGELOG, entrée R26-KIT-04 : modèle de menace absent ou modifié"
    transport = section(DEPLOIEMENT, "Transporter, vérifier et extraire")
    assert "`<CPython>`" in transport and "`__pycache__`" in transport and f"(#{anchor})" in transport, transport[-600:]
    for relative in (DEPLOIEMENT, DEPANNAGE):
        for line in read(relative).splitlines():
            if re.search(r"fichiers? ajoutés?", line, re.IGNORECASE) and re.search(r"\bignorés?\b", line):
                assert f"#{anchor})" in line, f"{relative} : fichiers ajoutés dits ignorés sans renvoi aux exceptions : {line[:120]}"


def test_option_tables_give_every_name_and_the_menu_folder_limit():
    """U3-10 : chaque option visible d'install, update et uninstall figure dans le tableau de sa commande avec tous ses noms
    (--model et --modele), et la ligne --menu reprend la limite que l'aide annonce (entrée absente du menu des applications
    hors du dossier applications des données XDG)."""
    commands = subparsers(linux_install.build_parser())
    for command, title in (("install", "Installer"), ("update", "Mettre à jour"), ("uninstall", "Désinstaller et reprendre des données")):
        rows = table_with_header(section(DEPLOIEMENT, title), f"Option de `{command}`")[1:]
        for action in commands[command]._actions:  # noqa: SLF001
            names = [name for name in action.option_strings if name.startswith("--") and name not in {"--aide", "--help"}]
            if action.help == argparse.SUPPRESS or not names:
                continue
            spelled = {name: re.compile(rf"`{re.escape(name)}(?![\w-])") for name in names}
            documented = [row for row in rows if any(pattern.search(row[0]) for pattern in spelled.values())]
            assert documented, f"{command} {names[0]} absent du tableau « Option de `{command}` »"
            for name, pattern in spelled.items():
                assert any(pattern.search(row[0]) for row in documented), f"{command} : {name} absent de la ligne de {names[0]}"
            if "n'apparaît pas dans le menu" in (action.help or ""):
                assert any("n'apparaît pas dans le menu" in row[1] for row in documented), f"{command} {names[0]} : limite du menu"


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_commands_that_write_without_a_summary_are_documented_as_such(tmp_path, monkeypatch):
    """U3-10 (U3-04, partie documentation) : hors terminal et sans --oui, repair et modele (atelier arrêté) écrivent sans
    récapitulatif ; avec --oui, modele refuse quand l'atelier tourne avec un autre modèle. La section 8.8 le dit, et aucun
    document n'annonce un récapitulatif pour toute opération qui écrit."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    runner = simulation.ProgrammeSimule()
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root, "--no-start") == 0
    program = Path(simulation.pointer_of(destination)["current"]["program"])
    for argv in (["repair", "--menu", "--destination", str(destination)], ["modele", "qwen3.5:2b", "--destination", str(destination)]):
        before = simulation.pointer_of(destination)
        ctx = simulation.context(program, runner=runner)
        assert linux_install.main(argv, ctx) == linux_install.EXIT_OK, simulation.screen(ctx)
        assert "Récapitulatif" not in simulation.screen(ctx) and "Confirmation requise" not in simulation.screen(ctx)
        assert simulation.pointer_of(destination) != before, f"{argv[0]} : rien d'écrit"
    opener = simulation.context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--no-browser"], opener) == 0, simulation.screen(opener)
    refused = simulation.context(program, runner=runner)
    assert linux_install.main(["modele", "qwen3.5:4b", "--oui", "--destination", str(destination)], refused) == linux_install.EXIT_REFUSED
    assert "L'atelier tourne avec qwen3.5:2b" in simulation.screen(refused), simulation.screen(refused)
    rows = table_with_header(section(DEPLOIEMENT, "État, réparation, vérification et modèle principal"), "Commande")
    for name in WRITTEN_WITHOUT_SUMMARY:
        row = next(row for row in rows if row[0].startswith(f"`installer.sh {name}"))
        assert "sans récapitulatif" in row[1], f"section 8.8, {name} : {row[1]}"
    modele = next(row for row in rows if row[0].startswith("`installer.sh modele"))
    assert "`--oui`" in modele[1] and "refus" in modele[1], modele[1]
    for relative in sorted({*shipped_markdown(), "docs/specifications/SPECIFICATIONS.md"}):
        assert "Toute opération qui écrit affiche un récapitulatif" not in read(relative), relative


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_launcher_backup_refusal_when_stopped_has_its_row(tmp_path, monkeypatch):
    """U3-10 : `atelier sauvegarder`, atelier arrêté, est refusé en code 3 avec les commandes à lancer ; le dépannage cite ce
    message et ce code, la ligne générale des échecs du lanceur ne le range plus en code 1, et la section 11 de
    l'exploitation le décrit."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    runner = simulation.ProgrammeSimule()
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root, "--no-start") == 0
    program = Path(simulation.pointer_of(destination)["current"]["program"])
    ctx = simulation.context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "sauvegarder"], ctx) == linux_install.EXIT_REFUSED
    assert "backup" not in runner.commands()
    row = troubleshooting_row("`atelier sauvegarder` lancé alors que l'atelier est arrêté")
    assert_quotes_were_emitted(row[0], simulation.screen(ctx))
    assert row[3] == str(linux_install.EXIT_REFUSED) and "`run`" in row[4], row
    general = troubleshooting_row("navigateur absent")
    assert "sauvegarde" not in general[1].casefold() and "sauvegarder" not in general[2], general
    launcher = table_with_header(section(EXPLOITATION, "Lanceur atelier et menu"), "Action")
    backup = next(item for item in launcher if item[0].startswith("`sauvegarder`"))
    assert "code 3" in backup[1] and "atelier ouvrir" in backup[1], backup[1]


INTERRUPTION = re.compile(r"^(?:\0|[A-ZÉ][^:;«\0]{0,40}?) interrompue?\b")


def interruption_fragments() -> list[tuple[int, str]]:
    """(ligne, fragment) : plus long fragment constant de chaque message d'interruption de linux_install.py, quelle que soit la
    façon dont il est levé (valeurs de INTERRUPTED, messages du retour arrière, `raise Interrupted(…)`) : chaîne ou f-string
    qui commence par « <opération> interrompu(e) ». Les valeurs insérées et les commandes citées entre « » varient : elles
    séparent les fragments."""
    tree = ast.parse(read("tools/dist/linux_install.py"))
    nested = {id(value) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for value in node.values}
    nested |= {id(node.body[0].value) for node in ast.walk(tree)  # docstrings
               if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr)}
    fragments = []
    for node in ast.walk(tree):
        if id(node) in nested:
            continue
        if isinstance(node, ast.JoinedStr):
            text = "".join(str(part.value) if isinstance(part, ast.Constant) else "\0" for part in node.values)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        if INTERRUPTION.match(text):
            pieces = [piece.strip(" ;:,.") for piece in re.split(r"«[^»]*»|\0", text)]
            fragments.append((node.lineno, max(pieces, key=len)))
    return fragments


def ctrl_c_au_demarrage(argv: list[str]) -> dict:
    """Double nommé : Ctrl+C pendant le démarrage de l'atelier (`rag.sh up` interrompu)."""
    raise KeyboardInterrupt


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_every_interruption_message_is_in_the_troubleshooting(tmp_path, monkeypatch):
    """U3-10 : chaque message d'interruption de l'installateur et du lanceur figure dans la section 10 du dépannage (fragment
    constant le plus long ; les interruptions elles-mêmes en section 10.5, le récapitulatif d'une installation interrompue en
    section 10.1), et l'interruption du lanceur pendant un démarrage rend le code 130 avec le message de sa ligne."""
    text = re.sub(r"\s+", " ", section(DEPANNAGE, "Installateur et lanceur Linux"))
    missing = [f"linux_install.py:{line} : {fragment}" for line, fragment in interruption_fragments() if fragment not in text]
    assert len(interruption_fragments()) >= 20
    assert not missing, "messages d'interruption absents de la section 10 :\n" + "\n".join(missing)
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    # Installation --no-start : `up` n'est lancé que par l'ouverture qui suit, où le double l'interrompt.
    runner = simulation.ProgrammeSimule(results={"up": ctrl_c_au_demarrage})
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root, "--no-start") == 0
    program = Path(simulation.pointer_of(destination)["current"]["program"])
    ctx = simulation.context(program, runner=runner)
    assert linux_install.main(["run", "--destination", str(destination), "ouvrir"], ctx) == linux_install.EXIT_INTERRUPTED
    row = troubleshooting_row("pendant une action du lanceur")
    assert_quotes_were_emitted(row[0], simulation.screen(ctx))
    assert row[3] == str(linux_install.EXIT_INTERRUPTED), row


# Double nommé SAUVEGARDE_REFUSEE : `rag.sh backup` de la version en place en échec (place insuffisante), comme le rejeu B03 de
# la revue U3.
SAUVEGARDE_REFUSEE = {"_rc": 1, "status": "failed", "message": "Espace insuffisant pour la sauvegarde."}


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
@pytest.mark.parametrize("before", ["arretee", "demarree"])
def test_an_update_whose_backup_fails_leaves_the_documented_state(tmp_path, monkeypatch, before):
    """U3-08 (partie documentation) : la sauvegarde de la version en place échoue pendant une mise à jour. La cause s'affiche
    avant l'état laissé ; l'instance que la mise à jour a démarrée pour la sauvegarde est arrêtée, celle que l'utilisateur
    avait démarrée reste en marche ; le code de sortie et ces états sont ceux du dépannage (section 10.3) et du déploiement
    (section 8.5)."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    # Ni l'installation --no-start ni l'ouverture ne sauvegardent : seule la mise à jour rencontre le double.
    runner = simulation.ProgrammeSimule(results={"backup": SAUVEGARDE_REFUSEE})
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root, "--no-start") == 0
    if before == "demarree":
        program = Path(simulation.pointer_of(destination)["current"]["program"])
        opener = simulation.context(program, runner=runner)
        assert linux_install.main(["run", "--destination", str(destination), "ouvrir", "--no-browser"], opener) == 0
    kit_b = simulation.second_kit(tmp_path, monkeypatch)
    ctx = simulation.context(kit_b, runner=runner)
    code = linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"], ctx)
    err = cast(io.StringIO, ctx.err).getvalue()
    assert code == linux_install.EXIT_ERROR, simulation.screen(ctx)
    assert "Sauvegarde refusée : Espace insuffisant pour la sauvegarde." in err
    assert err.index("Sauvegarde refusée") < err.index("reste la version courante"), err
    state = ("l'instance démarrée pour la sauvegarde a été arrêtée, comme avant la mise à jour" if before == "arretee"
             else "son instance, déjà démarrée avant la mise à jour, reste démarrée")
    assert state in err, err
    assert bool(runner.running) == (before == "demarree"), runner.running
    row = troubleshooting_row("ne démarre pas ou ne se sauvegarde pas")
    assert "« Sauvegarde refusée : … Rien n'a été installé. »" in row[0] and state in row[0], row[0]
    assert f"{code} pour les autres échecs avant la copie" in row[3], row[3]
    text = section(DEPLOIEMENT, "Mettre à jour")
    for statement in ("le message donne d'abord la cause, puis l'état laissé", "si la mise à jour l'avait démarrée pour la sauvegarde, elle "
                      "l'arrête", "une instance déjà démarrée avant la mise à jour reste démarrée", f"{code} pour un démarrage, une sauvegarde"):
        assert statement in text, statement
    assert simulation.pointer_of(destination)["current"]["kit_id"] == simulation.manifest_of(kit)["kit_id"]


# --- Ronde 5 de R26-KIT-04, alignée sur l'installateur final (install.sh 6a1dc111…, linux_install.py da294092…) : refus d'installer.sh
# mot pour mot (U5-01, QA5-03, U5-03, U5-04, R4S-01), modèle de menace (U4-07), verifier (U4-03), code 1 (U4-04), retrait (R3S-03),
# programme courant disparu (U4-02), stockage Qdrant (R3S-02), commande atelier (U4-05) et status sans installation (U4-06) ----------

INTERPRETER_FOLDER_CAUSE = "Fichier ou lien ajouté sous `<CPython>`"
TOOLS_CAUSE = "Outil de contrôle (GNU coreutils, GNU findutils)"
UNREADABLE_CAUSE = "Parcours du dossier de l'interpréteur par `find` en échec"
PROCESSES_CAUSE = "Retrait d'une version dont un processus du compte tourne"
MISSING_PROGRAM_CAUSE = "Dossier du programme courant supprimé"
ACCIDENTAL_TITLE = "Altération accidentelle"
ACCIDENTAL_CASES = ("Copie ou transport incomplets", "Fichier manquant ou modifié", "Fichier ajouté par erreur",
                    "Déduplication ou ferme de liens : fichier ou dossier", "Copie qui a suivi les liens", "Droits perdus")
SHELL_VARIABLE = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")
# Familles de refus d'install.sh qu'un poste peut ne pas savoir provoquer : outils masqués (espaces de noms utilisateur et de
# montage sans privilège), dossier illisible (le compte root lit tout).
TOOL_FAMILY, UNREADABLE_FAMILY = "absent de /usr/bin et /bin", "illisible ("
# Fichier inscrit sans droit de lecture (U6-05 de l'installateur, ronde 6) : le compte root le lit.
UNREADABLE_FILE_FAMILY = " sans droit de lecture ("


def running_as_root() -> bool:
    """Compte root : il lit un dossier sans droit de lecture (os.geteuid n'existe pas sous Windows)."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def unprivileged_namespaces() -> bool:
    """`unshare -rm` disponible sans privilège : condition du double PosteSansOutil de test_dist_linux_scripts."""
    return bool(shutil.which("unshare")) and subprocess.run(["unshare", "-rm", "true"], capture_output=True, timeout=30,
                                                            check=False).returncode == 0


def bin_without(folder: Path, missing: str) -> Path:
    """Double BIN_SANS_FIND : dossier de liens vers les commandes de /usr/bin et /bin, sauf `missing`."""
    target = folder / f"bin-sans-{missing}"
    target.mkdir()
    for directory in ("/usr/bin", "/bin"):
        for entry in Path(directory).iterdir():
            if entry.name != missing and not os.path.lexists(target / entry.name):
                os.symlink(entry, target / entry.name)
    return target


def message_quotes(cell: str) -> list[str]:
    """Messages cités dans une cellule de la colonne Message : passages entre accents graves d'au moins 30 caractères (forme
    employée quand le message cite lui-même des guillemets ou un <emplacement>), puis, hors de ces passages, chaque « … » de
    premier niveau."""
    spans = [span for span in re.findall(r"`([^`]+)`", cell) if len(span) >= 30]
    return [quote.strip() for quote in spans + quoted_messages(re.sub(r"`[^`]*`", "", cell))]


def quote_matches(quote: str, message: str) -> bool:
    """Le message émis est le message cité en entier, chaque « … » valant pour une valeur variable non vide."""
    return re.fullmatch(".+?".join(re.escape(piece) for piece in quote.split("…")), message, re.DOTALL) is not None


def template_matches(template: str, message: str) -> bool:
    """Le message émis vient du `fail "…"` d'install.sh `template`, chaque variable valant une valeur quelconque."""
    return re.fullmatch(".*?".join(re.escape(piece) for piece in SHELL_VARIABLE.split(template)), message, re.DOTALL) is not None


def constant_length(template: str) -> int:
    """Texte constant d'un message d'install.sh : ce qu'une citation doit garder (« … » ne remplace qu'une valeur variable)."""
    return len(SHELL_VARIABLE.sub("", template))


def assert_quote_emitted(quote: str, emitted: str) -> None:
    """Chaque fragment constant du message cité figure dans la sortie réelle (« … » valant pour une valeur variable)."""
    for fragment in (piece.strip() for piece in quote.split("…")):
        assert fragment in emitted, f"« {fragment} » absent des messages émis :\n{emitted}"


def quote_with(cell: str, key: str) -> str:
    """Seul message cité de la cellule qui contient `key`."""
    found = [quote for quote in message_quotes(cell) if key in quote]
    assert len(found) == 1, f"« {key} » : {len(found)} message(s) cité(s) dans {cell[:200]}"
    return found[0]


def installer_sh_refusals(tmp_path: Path) -> tuple[list[tuple[str, str]], set[str]]:
    """Double REFUS_INSTALLER_SH : chaque refus d'installer.sh provoqué par le vrai script (`--aide`), sur un kit factice de
    test_dist_linux_scripts et, pour les refus dont le texte dépend du dossier, sur ce kit placé en programme installé
    (ProgrammeInstalleFactice). Chaque refus sort en code 1, sortie standard vide, interpréteur jamais lancé. Rend
    ([(cas, message émis)], familles non provoquées sur ce poste)."""
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import (
        ABSENT,
        GLIBC_HOST,
        MUSL_GETCONF,
        MUSL_LDD,
        executable,
        fake_host,
    )

    unprovoked: set[str] = set()
    found: list[tuple[str, str]] = []

    def refused(label: str, folder: Path, result: subprocess.CompletedProcess) -> None:
        assert result.returncode == 1 and result.stdout == "" and not (folder / "interpreteur-lance").exists(), (label, result)
        message = result.stderr.strip()
        assert message and "\n" not in message and not message.startswith("Arrêt"), (label, result.stderr)
        found.append((label, message))

    def manifest_of_another_format(root: Path) -> None:
        (root / "kit-manifest.json").write_text("{}\n", encoding="utf-8")

    def interpreter_removed(root: Path) -> None:
        (root / CPYTHON / "bin/python3.12").unlink()

    def sums_removed(root: Path) -> None:
        (root / linux_kit.SUMS).unlink()

    def sums_line_removed(root: Path) -> None:
        sums = root / linux_kit.SUMS
        sums.write_text("".join(line for line in sums.read_text(encoding="utf-8").splitlines(keepends=True)
                                if not line.rstrip("\n").endswith("tools/dist/build_kit.py")), encoding="utf-8")

    def script_altered(root: Path) -> None:
        with (root / "tools/dist/linux_install.py").open("a", encoding="utf-8") as handle:
            handle.write("# altéré après l'extraction\n")

    def module_added(root: Path) -> None:
        (root / "tools/dist/__init__.py").write_text("print('ajouté')\n", encoding="utf-8")

    def startup_file_added(root: Path) -> None:
        (root / CPYTHON / "bin/pyvenv.cfg").write_text("home = /ailleurs\n", encoding="utf-8")

    def interpreter_entry_added(root: Path) -> None:
        (root / CPYTHON / "lib/librt.so.1").write_bytes(b"\x7fEL")

    def file_linked(root: Path) -> None:
        scripts.linked_to_a_copy(root, "tools/dist/linux_kit.py", root.parent / "copie-identique")

    def folder_linked(root: Path) -> None:
        scripts.linked_to_a_copy(root, "tools/dist", root.parent / "copie-identique")

    def declared_link_turned_file(root: Path) -> None:
        library = root / CPYTHON / "lib/libpython3.12.so"
        os.symlink("libpython3.12.so.1.0", library)
        scripts.write_links(root, {f"{CPYTHON}/lib/libpython3.12.so": "libpython3.12.so.1.0"})
        library.unlink()
        library.write_bytes(b"contenu quelconque")

    def listed_file_turned_fifo(root: Path) -> None:
        relative = f"{CPYTHON}/lib/python3.12/os.py"
        (root / relative).parent.mkdir(parents=True)
        (root / relative).write_text("# os\n", encoding="utf-8")
        scripts.write_links(root, {}, extra=(relative,))
        (root / relative).unlink()
        if sys.platform != "win32":  # os.mkfifo n'existe que sous Unix ; cet essai est sauté sous Windows
            os.mkfifo(root / relative)

    def execute_permission_lost(root: Path) -> None:
        (root / CPYTHON / "bin/python3.12").chmod(0o644)

    def listed_entry_missing(root: Path) -> None:
        # R5S-02 : copie ou extraction incomplètes ; bibliothèque inscrite dans SHA256SUMS absente.
        (root / CPYTHON / "lib/libpython3.12.so.1.0").unlink()

    alterations = [manifest_of_another_format, interpreter_removed, sums_removed, sums_line_removed, script_altered, module_added,
                   startup_file_added, interpreter_entry_added, file_linked, folder_linked, declared_link_turned_file,
                   listed_file_turned_fifo, execute_permission_lost, listed_entry_missing]
    tools = unprivileged_namespaces()
    if not tools:
        unprovoked.add(TOOL_FAMILY)
    if running_as_root():
        unprovoked.add(UNREADABLE_FAMILY)
        unprovoked.add(UNREADABLE_FILE_FAMILY)

    def prepared(place: str, name: str) -> tuple[Path, Path]:
        folder = new_folder(tmp_path, f"{place}-{name}")
        return folder, (scripts.fake_kit(folder) if place == "kit" else scripts.installed_program(folder))

    for place in ("kit", "programme"):
        for alteration in alterations:
            folder, root = prepared(place, alteration.__name__)
            alteration(root)
            refused(f"{place} : {alteration.__name__}", folder, scripts.run(root / "installer.sh", "--aide",
                                                                             fakes=fake_host(folder, "Linux", "aarch64")))
        if UNREADABLE_FAMILY not in unprovoked:
            folder, root = prepared(place, "dossier-illisible")
            hidden = root / CPYTHON / "lib/tls"
            hidden.mkdir()
            hidden.chmod(0)
            try:
                refused(f"{place} : dossier illisible", folder, scripts.run(root / "installer.sh", "--aide",
                                                                            fakes=fake_host(folder, "Linux", "aarch64")))
            finally:
                hidden.chmod(0o700)
        if UNREADABLE_FILE_FAMILY not in unprovoked:
            # U6-05 : fichier inscrit sous <CPython> sans droit de lecture (droits perdus à la copie ou à l'extraction).
            folder, root = prepared(place, "fichier-illisible")
            (root / CPYTHON / "lib/libpython3.12.so.1.0").chmod(0o200)
            refused(f"{place} : fichier illisible", folder, scripts.run(root / "installer.sh", "--aide",
                                                                       fakes=fake_host(folder, "Linux", "aarch64")))
        for tool in ("find", "sha256sum") if tools else ():
            folder, root = prepared(place, f"sans-{tool}")
            fakes = fake_host(folder, "Linux", "aarch64")
            executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 1000\n')  # vu comme root dans l'espace de noms
            refused(f"{place} : {tool} absent", folder, subprocess.run(
                scripts.without_system_tool(tool, [str(root / "installer.sh"), "--aide"]), capture_output=True, text=True,
                timeout=60, check=False, env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(root)}))
    # Refus dont le texte ne dépend pas du dossier : compte, emplacement du script, système, architecture, bibliothèque C.
    # (système, architecture, getconf, ldd) simulés par les doubles de test_runtime_launchers_sh.
    hosts: dict[str, tuple[str, str, str, str | None]] = {
        "root": ("Linux", "aarch64", GLIBC_HOST, None), "systeme": ("Darwin", "arm64", GLIBC_HOST, None),
        "architecture": ("Linux", "x86_64", GLIBC_HOST, None), "glibc-ancienne": ("Linux", "aarch64", "#!/bin/sh\necho 'glibc 2.28'\n", None),
        "musl": ("Linux", "aarch64", MUSL_GETCONF, MUSL_LDD), "libc-inconnue": ("Linux", "aarch64", ABSENT, ABSENT)}
    for name, (system, machine, getconf, ldd) in hosts.items():
        folder = new_folder(tmp_path, f"poste-{name}")
        kit = scripts.fake_kit(folder)
        fakes = fake_host(folder, system, machine, getconf=getconf, ldd=ldd)
        if name == "root":
            executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 0\n')
        refused(f"poste : {name}", folder, scripts.run(kit / "installer.sh", "--aide", fakes=fakes))
    folder = new_folder(tmp_path, "hors-kit")
    alone = folder / "seul/installer.sh"
    alone.parent.mkdir()
    shutil.copy2(ROOT / "tools/dist/install.sh", alone)
    refused("installer.sh hors d'un kit", folder, scripts.run(alone, "--aide", fakes=fake_host(folder, "Linux", "aarch64")))
    return found, unprovoked


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_every_installer_sh_refusal_is_quoted_word_for_word_in_the_troubleshooting(tmp_path):
    """Chaque `fail "…"` d'install.sh est provoqué par le vrai script (REFUS_INSTALLER_SH, kit et programme installé). Chaque
    message émis est cité en entier par une ligne de la section 10.1 dont la source est install.sh et le code 1, « … » ne
    remplaçant qu'une valeur variable : la citation garde au moins tout le texte constant du message d'install.sh.
    Réciproquement, chaque message cité par une ligne propre à install.sh est émis : aucune citation périmée."""
    messages, unprovoked = installer_sh_refusals(tmp_path)
    templates = sorted(set(shell_messages("tools/dist/install.sh")))
    assert len(templates) >= 20, templates

    def best_template(message: str) -> str:
        matching = [template for template in templates if template_matches(template, message)]
        assert matching, f"message émis sans `fail \"…\"` d'install.sh qui lui corresponde : {message}"
        return max(matching, key=constant_length)

    provoked = {best_template(message) for _, message in messages}
    missing = [template for template in templates if template not in provoked and not any(family in template for family in unprovoked)]
    assert not missing, "refus d'install.sh jamais provoqués par l'essai :\n" + "\n".join(missing)
    rows = [row for table in tables(section(DEPANNAGE, "Avant toute écriture")) for row in table[1:] if "`install.sh`" in row[4]]
    for label, message in messages:
        cited = [(row, quote) for row in rows for quote in message_quotes(row[0]) if quote_matches(quote, message)]
        assert cited, f"{label} : message d'install.sh absent de la section 10.1 du dépannage :\n{message}"
        complete = [quote for row, quote in cited if len(quote.replace("…", "")) >= constant_length(best_template(message))]
        assert complete, f"{label} : la citation remplace du texte constant par « … » :\n{message}\n{[quote for _, quote in cited]}"
        assert all(row[3].startswith(str(linux_install.EXIT_ERROR)) for row, _ in cited), (label, [row[3] for row, _ in cited])
    for row in (row for row in rows if row[4] == "`install.sh`"):
        for quote in message_quotes(row[0]):
            if any(family in quote for family in unprovoked):
                continue
            assert any(quote_matches(quote, message) for _, message in messages), f"citation jamais émise par install.sh : {quote}"


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_the_interpreter_folder_refusals_have_their_troubleshooting_row(tmp_path):
    """U5-01, QA5-03 (a), U5-03 et U5-04, sur l'installateur de la ronde 5 : une entrée ajoutée sous <CPython> est refusée ;
    find est pris dans /usr/bin ou /bin, jamais dans le PATH (témoin BIN_SANS_FIND : un PATH sans find est accepté) ; absent
    de ces dossiers (PosteSansOutil), il est nommé, et son message diffère de celui d'un dossier illisible (DOSSIER_ILLISIBLE).
    Les lignes du dépannage disent ces causes, et leur action vaut pour un kit comme pour un programme installé."""
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import executable, fake_host

    folder = new_folder(tmp_path, "ajout")
    kit = scripts.fake_kit(folder)
    added = kit / CPYTHON / "lib/python3.12/NOTES.txt"
    added.parent.mkdir(parents=True)
    added.write_text("ajouté par erreur\n", encoding="utf-8")
    foreign = run_installer_sh(folder, kit)
    assert foreign.returncode == 1 and not (folder / "interpreteur-lance").exists(), foreign.stderr
    assert_quote_emitted(quote_with(troubleshooting_row(INTERPRETER_FOLDER_CAUSE)[0], "ajouté au kit"), foreign.stderr)
    folder = new_folder(tmp_path, "sans-find-dans-le-path")
    kit = scripts.fake_kit(folder)
    witness = subprocess.run([str(kit / "installer.sh"), "--aide"], capture_output=True, text=True, timeout=60, check=False,
                             env={"PATH": f"{fake_host(folder, 'Linux', 'aarch64')}:{bin_without(folder, 'find')}", "HOME": str(kit)})
    assert witness.returncode == 0 and (folder / "interpreteur-lance").exists(), witness.stderr
    tools = troubleshooting_row(TOOLS_CAUSE)
    for expected in ("jamais dans le PATH", "un `find` absent du seul PATH ne gêne pas"):
        assert expected in tools[1], f"ligne des outils de contrôle : « {expected} » attendu ; {tools[1]}"
    assert "findutils" in tools[2] and "coreutils" in tools[2], tools[2]
    emitted = {}
    if unprivileged_namespaces():
        folder = new_folder(tmp_path, "poste-sans-find")
        kit = scripts.fake_kit(folder)
        fakes = fake_host(folder, "Linux", "aarch64")
        executable(fakes / "id", '#!/bin/sh\n[ "$1" = -u ] && echo 1000\n')
        result = subprocess.run(scripts.without_system_tool("find", [str(kit / "installer.sh"), "--aide"]), capture_output=True, text=True,
                                timeout=60, check=False, env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(kit)})
        assert result.returncode == 1 and not (folder / "interpreteur-lance").exists(), result.stderr
        emitted["find"] = result.stderr
        assert_quote_emitted(quote_with(tools[0], "find (findutils) absent de /usr/bin et /bin : nécessaire pour contrôler le dossier "
                                                  "de l'interpréteur du kit"), result.stderr)
    unreadable = troubleshooting_row(UNREADABLE_CAUSE)
    if not running_as_root():
        folder = new_folder(tmp_path, "illisible")
        kit = scripts.fake_kit(folder)
        hidden = kit / CPYTHON / "lib/tls"
        hidden.mkdir()
        hidden.chmod(0)
        try:
            result = run_installer_sh(folder, kit)
        finally:
            hidden.chmod(0o700)
        assert result.returncode == 1 and not (folder / "interpreteur-lance").exists(), result.stderr
        emitted["illisible"] = result.stderr
        assert_quote_emitted(quote_with(unreadable[0], "Dossier de l'interpréteur du kit illisible"), result.stderr)
    assert len(set(emitted.values())) == len(emitted), "find absent et dossier illisible donnent le même message"
    assert "chmod -R u+rX" in unreadable[2] and "droit de lecture ou de traversée" in unreadable[1], unreadable
    for row in (troubleshooting_row(INTERPRETER_FOLDER_CAUSE), unreadable):
        for expected in ("<kit_id>.tar.sha256", "Programme installé", f"(#{check_docs.slug(REPAIR_TITLE)})", "status --destination"):
            assert expected in row[2], f"dépannage, action : « {expected} » attendu ; {row[2]}"
        assert row[3] == "1" and row[4] == "`install.sh`", row


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_the_threat_model_and_its_accidental_cases_match_the_installer(tmp_path, monkeypatch):
    """Modèle de menace de la ronde 5, écrit tel quel dans la section 8.3, et tableau des altérations accidentelles confronté
    au comportement réel. Fichier ou dossier vérifié remplacé par un lien vers une copie identique (COPIE_IDENTIQUE_HORS_KIT) :
    refusé par installer.sh (code 1), fichier soumis à ldd refusé par la vérification ciblée (code 3), autre fichier listé
    refusé par la copie (code 5, rien de désigné), autre dossier copié comme un dossier ordinaire. Lien de SYMLINKS devenu
    fichier (LIEN_DEVENU_FICHIER) : refusé sous <CPython>, comme remplacé par un dossier vide ; ailleurs, accepté par installer.sh
    et recréé par la copie. Droits
    perdus (SANS_BIT_X, DOSSIER_ILLISIBLE, FICHIER_ILLISIBLE) : installer.sh refusé par le shell (126), interpréteur refusé par
    installer.sh avec sa cause (1), dossier illisible (1), fichier inscrit sous <CPython> sans droit de lecture (1), bit x rétabli
    par la copie, fichier illisible hors de <CPython> qui arrête l'installation (5)."""
    from tests.unit import test_dist_linux_install as simulation
    from tests.unit import test_dist_linux_scripts as scripts

    text = section(DEPLOIEMENT, SCOPE_TITLE)
    assert installer_sh_threat_model() in plain(text), "section 8.3 : modèle de menace absent ou modifié"
    rows = table_with_header(text, ACCIDENTAL_TITLE)[1:]
    found = {case: [row for row in rows if row[0].startswith(case)] for case in ACCIDENTAL_CASES}
    assert all(len(found[case]) == 1 for case in ACCIDENTAL_CASES) and len(rows) == len(ACCIDENTAL_CASES), [row[0] for row in rows]
    linked, followed, rights = (found[case][0][1] for case in ACCIDENTAL_CASES[3:])

    # Fichier ou dossier remplacé par un lien.
    emitted = ""
    for relative in ("tools/dist/linux_kit.py", f"{CPYTHON}/bin/python3.12", "tools/dist/"):
        outcome, err = linked_outcome(tmp_path, relative)
        assert outcome == "refusé", f"{relative} remplacé par un lien : {outcome} ; {err}"
        emitted += err
    for expected in ("`installer.sh` refuse", "code 1", "code 3", "code 5", "n'est pas refusé"):
        assert expected in linked, f"ligne « fichier ou dossier remplacé par un lien » : « {expected} » attendu ; {linked}"
    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    manifest = simulation.manifest_of(kit)
    outside = tmp_path / "hors-du-kit"

    def replace_by_identical_link(relative: str) -> Path:
        copy = outside / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(kit / relative, copy)
        os.symlink(copy, kit / relative)
        return copy

    def restore(relative: str, copy: Path) -> None:
        (kit / relative).unlink()
        shutil.move(copy, kit / relative)

    target = linux_install.ldd_targets(manifest)[0]
    copy = replace_by_identical_link(target)
    ctx = simulation.context(kit)
    with pytest.raises(linux_install.InstallError) as refusal:
        linux_install.verify_targeted(ctx, manifest, linux_install.Report(ctx, "install"))
    assert refusal.value.code == linux_install.EXIT_REFUSED and f"{target} altéré ou absent" in str(refusal.value), str(refusal.value)
    restore(target, copy)
    copy = replace_by_identical_link("README.md")
    ctx = simulation.context(kit)
    destination = tmp_path / "liens" / "programmes"
    assert simulation.install(ctx, destination, tmp_path / "liens" / "donnees", "--no-start") == linux_install.EXIT_PARTIAL
    assert not list(destination.glob("*/kit-manifest.json")) and not (destination / "installation.json").exists()
    assert_quotes_were_emitted(linked, emitted + simulation.screen(ctx))
    restore("README.md", copy)
    copy = replace_by_identical_link("docs")
    ctx = simulation.context(kit)
    destination = tmp_path / "dossier-lie" / "programmes"
    assert simulation.install(ctx, destination, tmp_path / "dossier-lie" / "donnees", "--no-start", "--sans-menu") == 0, simulation.screen(ctx)
    program = Path(simulation.pointer_of(destination)["current"]["program"])
    assert not (program / "docs").is_symlink() and files_under(program / "docs") == files_under(copy)
    restore("docs", copy)

    # Lien de SYMLINKS remplacé par un fichier : refusé sous <CPython> ; ailleurs, accepté puis recréé par la copie.
    outcome, err = changed_type_outcomes(tmp_path, f"{CPYTHON}/lib/libpython3.12.so")["LIEN_DEVENU_FICHIER"]
    assert outcome == "refusé", err
    assert_quotes_were_emitted(followed, err)
    folder = new_folder(tmp_path, "lien-hors-interpreteur")
    fake = scripts.fake_kit(folder)
    (fake / "bin").mkdir()
    (fake / "bin/cible").write_text("# cible\n", encoding="utf-8")
    os.symlink("cible", fake / "bin/lien")
    scripts.write_links(fake, {"bin/lien": "cible"}, extra=("bin/cible",))
    (fake / "bin/lien").unlink()
    (fake / "bin/lien").write_bytes(b"contenu quelconque")
    assert launched(folder, run_installer_sh(folder, fake))
    folder = new_folder(tmp_path, "lien-devenu-dossier-vide")
    fake = scripts.fake_kit(folder)
    (fake / CPYTHON / "lib/python3.12.14").mkdir()
    os.symlink("python3.12.14", fake / CPYTHON / "lib/python3.12")
    scripts.write_links(fake, {f"{CPYTHON}/lib/python3.12": "python3.12.14"})
    (fake / CPYTHON / "lib/python3.12").unlink()
    (fake / CPYTHON / "lib/python3.12").mkdir()
    # U6-06 de l'installateur (ronde 6) : un lien de SYMLINKS devenu dossier, même vide, est refusé sous <CPython>.
    empty = run_installer_sh(folder, fake)
    assert not launched(folder, empty) and "n'est plus un lien" in empty.stderr, "lien de SYMLINKS devenu dossier vide sous <CPython>"
    assert "dossier, même vide" in followed and "dossier non vide" not in followed, followed
    links = dict(line.split("\t", 1) for line in (kit / linux_kit.LINKS).read_text(encoding="utf-8").splitlines() if line)
    relative = next(path for path in sorted(links) if not path.startswith(manifest["python"]["executable"].rsplit("/bin/", 1)[0] + "/"))
    (kit / relative).unlink()
    (kit / relative).write_bytes(b"contenu quelconque")
    copied = tmp_path / "copie-lien"
    linux_kit.install_copy(kit, copied)
    assert os.path.islink(copied / relative) and os.readlink(copied / relative) == links[relative]
    for expected in ("Sous `<CPython>/`", "`installer.sh` l'accepte sans le hacher", "recrée le lien"):
        assert expected in followed, f"ligne « copie qui a suivi les liens » : « {expected} » attendu ; {followed}"
    (kit / relative).unlink()
    os.symlink(links[relative], kit / relative)

    # Droits perdus.
    folder = new_folder(tmp_path, "sans-bit-x")
    fake = scripts.fake_kit(folder)
    (fake / CPYTHON / "bin/python3.12").chmod(0o644)
    interpreter = run_installer_sh(folder, fake)
    assert interpreter.returncode == 1 and not launched(folder, interpreter), interpreter.stderr
    (fake / "installer.sh").chmod(0o644)
    script = subprocess.run(["sh", "-c", "./installer.sh --aide"], cwd=fake, env={"PATH": "/usr/bin:/bin", "HOME": str(folder)},
                            capture_output=True, text=True, timeout=60, check=False)
    assert script.returncode == 126 and "Permission denied" in script.stderr, script.stderr
    emitted = interpreter.stderr + script.stderr
    (kit / "rag.sh").chmod(0o644)
    copied = tmp_path / "copie-droits"
    linux_kit.install_copy(kit, copied)
    assert (copied / "rag.sh").stat().st_mode & 0o111 == 0o111
    for expected in ("code 126", "code 1", "`EXECUTABLES`", "code 5"):
        assert expected in rights, f"ligne « Droits perdus » : « {expected} » attendu ; {rights}"
    if not running_as_root():
        folder = new_folder(tmp_path, "dossier-illisible")
        fake = scripts.fake_kit(folder)
        hidden = fake / CPYTHON / "lib/tls"
        hidden.mkdir()
        hidden.chmod(0)
        try:
            emitted += run_installer_sh(folder, fake).stderr
        finally:
            hidden.chmod(0o700)
        # U6-05 : fichier inscrit sous <CPython> sans droit de lecture, nommé par installer.sh avant tout lancement de Python.
        folder = new_folder(tmp_path, "fichier-illisible")
        fake = scripts.fake_kit(folder)
        (fake / CPYTHON / "lib/libpython3.12.so.1.0").chmod(0o200)
        unreadable_file = run_installer_sh(folder, fake)
        assert unreadable_file.returncode == 1 and not launched(folder, unreadable_file), unreadable_file.stderr
        emitted += unreadable_file.stderr
        (kit / "README.md").chmod(0)
        ctx = simulation.context(kit)
        destination = tmp_path / "illisible" / "programmes"
        try:
            code = simulation.install(ctx, destination, tmp_path / "illisible" / "donnees", "--no-start")
        finally:
            (kit / "README.md").chmod(0o644)
        assert code == linux_install.EXIT_PARTIAL and "Arrêt : PermissionError : " in simulation.screen(ctx), simulation.screen(ctx)
        assert not list(destination.glob("*/kit-manifest.json")) and not (destination / "installation.json").exists()
        assert_quotes_were_emitted(rights, emitted + simulation.screen(ctx))
        row = troubleshooting_row("illisible pour le compte pendant la copie")
        assert_quotes_were_emitted(row[0], simulation.screen(ctx))
        assert row[3] == str(linux_install.EXIT_PARTIAL), row


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_verifier_row_matches_the_resolution_of_installer_sh(tmp_path, monkeypatch):
    """U4-03 (partie documentation), installateur de la ronde 5 : `verifier` retrouve l'installation comme `./installer.sh`.
    Le kit de la version courante le dit (code 0) ; le kit d'une autre version annonce la mise à jour (code 0) ; des données
    conservées sans sauvegarde sont refusées comme par `./installer.sh --oui` (code 3) ; sans installation, « prêts » et la
    ligne qui cite `update --destination`. La ligne `verifier` de la section 8.8 cite ces messages et dit que les précontrôles
    propres à `update` ne sont pas rejoués."""
    from tests.unit import test_dist_linux_install as simulation

    home = simulated_home(tmp_path, monkeypatch, "maison")
    runner = simulation.ProgrammeSimule()
    kit_a = simulation.make_kit(tmp_path, monkeypatch)
    assert linux_install.main(["--oui", "--no-start"], simulation.context(kit_a, runner=runner)) == linux_install.EXIT_OK
    screens = []
    for kit in (kit_a, simulation.second_kit(tmp_path, monkeypatch)):
        ctx = simulation.context(kit, runner=runner)
        assert linux_install.main(["verifier"], ctx) == linux_install.EXIT_OK, simulation.screen(ctx)
        screens.append(simulation.screen(ctx))
    assert "est déjà la version courante" in screens[0] and "Installation existante trouvée" in screens[1], screens
    program = Path(simulation.pointer_of(simulation.default_paths(home)[0])["current"]["program"])
    assert linux_install.main(["uninstall", "--tout", "--oui"], simulation.context(program, runner=runner)) == linux_install.EXIT_OK
    kept = simulation.context(kit_a, runner=runner)
    assert linux_install.main(["verifier"], kept) == linux_install.EXIT_REFUSED, simulation.screen(kept)
    refused = simulation.context(kit_a, runner=runner)
    assert linux_install.main(["--oui", "--no-start"], refused) == linux_install.EXIT_REFUSED
    assert "sans aucune sauvegarde" in simulation.screen(kept) and "sans aucune sauvegarde" in simulation.screen(refused)
    simulated_home(tmp_path, monkeypatch, "maison-neuve")
    fresh = simulation.context(kit_a, runner=runner)
    assert linux_install.main(["verifier"], fresh) == linux_install.EXIT_OK, simulation.screen(fresh)
    screens.append(simulation.screen(fresh))
    rows = table_with_header(section(DEPLOIEMENT, "État, réparation, vérification et modèle principal"), "Commande")
    row = next(row for row in rows if row[0].startswith("`installer.sh verifier`"))
    quotes = message_quotes(row[1])
    assert len(quotes) >= 4, quotes
    for quote in quotes:
        assert_quote_emitted(quote, "\n".join(screens))
    for statement in ("ne sont pas rejoués", "même refus qu'`install`", "code 3", "données conservées"):
        assert statement in row[1], f"section 8.8, verifier : « {statement} » attendu ; {row[1]}"
    assert "ne tient compte ni" not in row[1], row[1]


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_the_error_prefix_and_code_1_name_the_installer_sh_refusals(tmp_path, monkeypatch):
    """U4-04 (partie documentation) : les refus d'installer.sh avant Python sortent en code 1 sans le préfixe « Arrêt : »,
    ceux de Python le portent ; la section 8.9 et l'introduction de la section 10 du dépannage le disent ; la ligne du code 1
    reprend EXIT_CODES[1] et renvoie aux lignes de ces refus (dépannage, section 10.1) ; aucun texte n'attribue au shell le refus
    d'un interpréteur sans droit d'exécution, que installer.sh nomme lui-même."""
    from tests.unit import test_dist_linux_install as simulation
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import fake_host

    folder = new_folder(tmp_path, "architecture")
    fake = scripts.fake_kit(folder)
    shell = scripts.run(fake / "installer.sh", "--aide", fakes=fake_host(folder, "Linux", "x86_64"))
    assert shell.returncode == 1 and shell.stderr and not shell.stderr.startswith("Arrêt"), shell.stderr
    simulated_home(tmp_path, monkeypatch, "maison")
    ctx = simulation.context(simulation.make_kit(tmp_path, monkeypatch))
    nested = ["install", "--destination", str(tmp_path / "p"), "--data-root", str(tmp_path / "p" / "d"), "--no-start"]
    assert linux_install.main(nested, ctx) == linux_install.EXIT_REFUSED
    assert cast(io.StringIO, ctx.err).getvalue().startswith("Arrêt : "), simulation.screen(ctx)
    for relative, title in ((DEPLOIEMENT, "Codes de sortie et rapports"), (DEPANNAGE, "Installateur et lanceur Linux")):
        sentences = [sentence for sentence in re.split(r"(?<=\.) |\n", section(relative, title)) if "« Arrêt : »" in sentence]
        assert sentences and all("`installer.sh`" in sentence and "avant le lancement de Python" in sentence for sentence in sentences), \
            (relative, sentences)
    code_1 = next(row for row in table_with_header(section(DEPLOIEMENT, "Codes de sortie et rapports"), "Code") if row[0] == "1")
    assert code_1[1].startswith(linux_install.EXIT_CODES[linux_install.EXIT_ERROR]), code_1[1]
    assert "(../exploitation/DEPANNAGE.md#101-avant-toute-écriture)" in code_1[1], code_1[1]
    for relative in (DEPLOIEMENT, DEPANNAGE):
        assert "un `installer.sh` ou un interpréteur privé de son droit d'exécution" not in read(relative), relative


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_the_removal_refusals_of_running_processes_are_quoted_in_the_troubleshooting(tmp_path, monkeypatch):
    """R3S-03 (partie documentation) : avec le double ProcessusDuProgramme, le retrait d'une version est refusé (code 3, rien
    de supprimé) quand un processus du compte tourne depuis son dossier alors qu'un profil désigné manque (un, puis tous), que
    la version n'est pas désignée, ou qu'il reste après l'arrêt de l'instance désignée ; code 5 quand `uninstall --tout` a déjà
    retiré d'autres versions. La ligne du dépannage (section 10.3) cite chacun de ces messages, ses codes et ses sources."""
    from tests.unit import test_dist_linux_install as simulation
    from tests.unit.test_dist_linux_review import third_kit

    simulated_home(tmp_path, monkeypatch, "maison")
    emitted = []

    def refused_uninstall(kit: Path, destination: Path, option: list[str], runner, *programs: Path,
                          expected: int = linux_install.EXIT_REFUSED) -> None:
        ctx = simulation.context(kit, runner=runner, probe=simulation.PosteSimule(processes=simulation.running_from(runner, *programs)))
        code = linux_install.main(["uninstall", *option, "--destination", str(destination), "--oui"], ctx)
        assert code == expected and "rien n'a été supprimé" in simulation.screen(ctx), simulation.screen(ctx)
        assert ("(déjà retirées : " in simulation.screen(ctx)) == (expected == linux_install.EXIT_PARTIAL), simulation.screen(ctx)
        emitted.append(simulation.screen(ctx))

    kit = simulation.make_kit(tmp_path, monkeypatch)
    runner = simulation.ProgrammeSimule()
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    assert simulation.install(simulation.context(kit, runner=runner), destination, data_root) == 0
    current = simulation.pointer_of(destination)["current"]
    profiles = sorted(current["profiles"].values())
    assert runner.running and len(profiles) >= 2, (runner.running, profiles)
    Path(profiles[-1]).unlink()
    refused_uninstall(kit, destination, ["--tout"], runner)
    for profile in profiles[:-1]:
        Path(profile).unlink()
    refused_uninstall(kit, destination, ["--tout"], runner)
    assert Path(current["program"]).is_dir()
    other = tmp_path / "autre"
    other.mkdir()
    simulated_home(other, monkeypatch, "maison")
    kit = simulation.make_kit(other, monkeypatch)
    destination, _, first, _, _ = simulation.updated(kit, other, monkeypatch)
    assert linux_install.main(["update", "--destination", str(destination), "--oui", "--no-start"],
                              simulation.context(third_kit(other, monkeypatch))) == 0
    refused_uninstall(kit, destination, ["--anciennes"], simulation.ProgrammeSimule(), Path(first["program"]))
    current = simulation.pointer_of(destination)["current"]
    refused_uninstall(kit, destination, ["--tout"], simulation.ProgrammeSimule(), Path(current["program"]), expected=linux_install.EXIT_PARTIAL)
    row = troubleshooting_row(PROCESSES_CAUSE)
    assert_quotes_were_emitted(row[0], "\n".join(emitted))
    for expected in ("(profil … absent)", "(profils … absents)", "version non désignée par le pointeur", "encore en marche"):
        assert expected in row[0], f"dépannage, ligne des processus : « {expected} » attendu ; {row[0]}"
    assert row[3] == f"{linux_install.EXIT_REFUSED} ; {linux_install.EXIT_PARTIAL} si une version a déjà été retirée", row[3]
    assert "`refuse_unreadable_instance`" in row[4] and "`remove_version`" in row[4], row[4]
    removal = section(DEPLOIEMENT, "Désinstaller et reprendre des données")
    for statement in ("`/proc/<pid>/exe`", "refusé avant la confirmation (code 3)", f"jusqu'à {linux_install.PROCESS_EXIT_WAIT_S:g} s",
                      "Aucun processus n'est arrêté d'office"):
        assert statement in removal, f"déploiement, section 8.7 : « {statement} » attendu"


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_a_missing_current_program_has_its_status_repair_and_uninstall_lines(tmp_path, monkeypatch):
    """U4-02 (partie documentation) : dossier du programme courant supprimé, avec et sans version précédente. `status` (code 1)
    et `repair` (code 3) citent le retour arrière, sinon la procédure de la section 10.4 ; le récapitulatif d'`uninstall`
    annonce « Retirer du pointeur » (code 0). La ligne du dépannage (section 10.3) cite ces messages et ces codes."""
    from tests.unit import test_dist_linux_install as simulation

    emitted = []
    for previous in (True, False):
        place = tmp_path / ("avec-precedente" if previous else "seule")
        place.mkdir()
        simulated_home(place, monkeypatch, "maison")
        kit = simulation.make_kit(place, monkeypatch)
        if previous:
            destination, _, _, current, _ = simulation.updated(kit, place, monkeypatch)
        else:
            destination, _, current, _ = simulation.installed(kit, place, "--no-start")
        shutil.rmtree(current["program"])
        for argv, expected in ((["status"], linux_install.EXIT_ERROR), (["repair"], linux_install.EXIT_REFUSED),
                               (["uninstall", "--tout", "--oui"], linux_install.EXIT_OK)):
            ctx = simulation.context(kit)
            assert linux_install.main([*argv, "--destination", str(destination)], ctx) == expected, simulation.screen(ctx)
            emitted.append(simulation.screen(ctx))
    row = troubleshooting_row(MISSING_PROGRAM_CAUSE)
    assert_quotes_were_emitted(row[0], "\n".join(emitted))
    assert row[3] == "1 pour `status` ; 3 pour `repair` ; 0 pour `uninstall`", row[3]
    assert f"(#{check_docs.slug(REPAIR_TITLE)})" in row[2] and "rollback" in row[2], row[2]
    assert "dossier du programme courant a disparu" in section(DEPANNAGE, REPAIR_TITLE)
    assert "« Retirer du pointeur : <kit_id> (dossier … déjà absent) »" in section(DEPLOIEMENT, "Désinstaller et reprendre des données")
    status = next(item for item in table_with_header(section(DEPLOIEMENT, "État, réparation, vérification et modèle principal"), "Commande")
                  if item[0].startswith("`installer.sh status`"))
    assert "programme courant absent" in status[1] and "status --destination <dossier des versions>" in status[1], status[1]


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_qdrant_storage_user_command_and_status_messages_are_quoted(tmp_path, monkeypatch):
    """R3S-02, U4-05 et U4-06 (parties documentation) : `--qdrant-storage` dans le kit, ou dans un dossier qui contient config/ et
    static/, refusé avant toute écriture ; ~/.local en lecture seule sans ~/.local/bin : le refus cite le parent existant et la
    commande chmod qui le vise ; `status` sans installation cite `status --destination`. Les lignes de la section 10.1 citent ces
    messages, et la section 8.3 dit les mêmes règles pour `--qdrant-storage`."""
    from tests.unit import test_dist_linux_install as simulation

    home = simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, data_root = tmp_path / "programmes", tmp_path / "donnees"
    storage = tmp_path / "index-existant"
    (storage / "config").mkdir(parents=True)
    (storage / "static").mkdir()
    qdrant = []
    for folder in (kit / "index-qdrant", storage):
        ctx = simulation.context(kit)
        code = simulation.install(ctx, destination, data_root, "--qdrant-storage", str(folder), "--no-start")
        assert code == linux_install.EXIT_REFUSED and not destination.exists(), simulation.screen(ctx)
        qdrant.append(simulation.screen(ctx))
    row = troubleshooting_row("`--qdrant-storage` relatif")
    assert_quote_emitted(quote_with(row[0], "dans le kit ou le programme"), qdrant[0])
    assert_quote_emitted(quote_with(row[0], "que Qdrant lirait en démarrant depuis ce dossier"), qdrant[1])
    assert "contient config/ et static/" in qdrant[1], qdrant[1]
    option = next(item for item in table_with_header(section(DEPLOIEMENT, "Installer"), "Option de `install`") if item[0].startswith("`--qdrant-storage"))
    for statement in ("hors de la destination, du kit et du programme", "ni `config/` ni `static/`"):
        assert statement in option[1], f"section 8.3, --qdrant-storage : « {statement} » attendu ; {option[1]}"
    local = home / ".local"
    local.mkdir()
    local.chmod(0o555)
    try:
        ctx = simulation.context(kit)
        code = linux_install.main(["install", "--emplacement", str(tmp_path / "autre"), "--oui", "--no-start"], ctx)
    finally:
        local.chmod(0o755)
    assert code == linux_install.EXIT_REFUSED and f"chmod u+w {local} »" in simulation.screen(ctx), simulation.screen(ctx)
    row = troubleshooting_row("Dossier de la commande `atelier`")
    assert_quote_emitted(quote_with(row[0], "ou installer avec --sans-menu"), simulation.screen(ctx))
    assert "à y créer" in row[1] and "premier dossier parent existant" in row[1], row[1]
    ctx = simulation.context(kit)
    assert linux_install.main(["status"], ctx) == linux_install.EXIT_ERROR
    row = troubleshooting_row("Installation sur un volume non monté")
    assert_quote_emitted(quote_with(row[0], "Si l'atelier est installé ailleurs"), simulation.screen(ctx))
    assert "${XDG_DATA_HOME" not in simulation.screen(ctx) and row[3] == "3 ; 1 pour `status`", row


# --- Ronde 6 de R26-KIT-04 (documentation) : modèle de menace sous sa seule forme imposée (U6-03, QA6-02) ---------------------

# Énoncé de ce dont la vérification du kit protège, quelle qu'en soit la tournure (« protège contre l'altération … »,
# « ne protège que d'une altération … ») : hors du modèle de menace écrit tel quel, aucun document ne doit en donner une autre forme.
GUARANTEE = re.compile(r"protèg\w*\s+(?:contre|que\s+d['’e]|de)\s*(?:l['’]|une\s+|toute\s+)?altération", re.IGNORECASE)


def test_the_threat_model_is_written_word_for_word_wherever_the_guarantee_is_described():
    """U6-03 et QA6-02 : la consigne de la ronde impose d'écrire le modèle de menace tel quel, avec « ACCIDENTELLE ». Il est lu
    dans l'en-tête d'install.sh (installer_sh_threat_model), source que test_dist_linux_scripts et test_dist_kit_guide
    confrontent aussi à linux_install.py, au skill et au guide. La section 8.3 du déploiement et l'entrée R26-KIT-04 du
    CHANGELOG, où la garantie est décrite, l'écrivent mot pour mot, sans gras ; aucun document de docs/, ni le README ni le
    CHANGELOG, n'en donne une autre forme (minuscules, gras, autre tournure de la garantie)."""
    threat_model = installer_sh_threat_model()
    assert threat_model.startswith("la vérification du kit protège contre l'altération ACCIDENTELLE ("), threat_model
    entry = next(line for line in read("CHANGELOG.md").splitlines() if "(R26-KIT-04)" in line)
    for place, text in ((f"{DEPLOIEMENT}, section 8.3", section(DEPLOIEMENT, SCOPE_TITLE)), ("CHANGELOG.md, entrée R26-KIT-04", entry)):
        assert re.search(rf"[Mm]odèle de menace : {re.escape(threat_model)}", plain(text)), f"{place} : modèle de menace absent ou modifié"
    documents = sorted({*shipped_markdown(), *(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.md"))})
    assert DEPLOIEMENT in documents and "CHANGELOG.md" in documents, documents
    for relative in documents:
        raw = read(relative)
        assert not re.search(r"\*\*\s*accidentelle\s*\*\*", raw, re.IGNORECASE), f"{relative} : modèle de menace en gras"
        rest = plain(raw).replace(threat_model, "")
        other = GUARANTEE.search(rest)
        assert other is None, f"{relative} : autre forme de la garantie : « {rest[other.start():other.end() + 80] if other else ''} »"
        assert "ACCIDENTELLE" not in rest, f"{relative} : « ACCIDENTELLE » hors du modèle de menace écrit tel quel"


# --- Ronde 6 de R26-KIT-04, alignée sur l'installateur final de la ronde 6 (install.sh 20144693…, linux_install.py 919adc8e…) :
# action d'un refus selon ce que le pointeur dit de la version (U6-02), graphie des chemins (U6-01, R5S-01) et relais des refus
# d'installer.sh par status (U6-04) -----------------------------------------------------------------------------------------

def filled(template: str, values: dict[str, str]) -> str:
    """Commande écrite avec ses repères (`<…>`) dans un document, remplie par les valeurs du poste : chaque mot qui porte un
    repère connu est écrit comme shlex.quote l'écrit (forme des commandes que cite install.sh) ; un repère sans valeur, que le
    message garde tel quel (« <dossier de cet autre kit> »), reste écrit."""
    words = re.findall(r"(?:<[^<>]*>|[^\s<])+", template.strip("`"))
    written = []
    for word in words:
        known = [name for name in values if name in word]
        for name in known:
            word = word.replace(name, values[name])
        written.append(shlex.quote(word) if known else word)
    return " ".join(written)


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"), reason="scripts POSIX")
def test_the_action_of_an_installed_program_refusal_follows_what_the_pointer_says(tmp_path):
    """U6-02 et U6-01 (parties documentation) : le vrai installer.sh d'un programme installé (ProgrammeInstalleFactice), atteint
    par un lien (DossierParUnLien : le dossier des versions est sur « un autre disque »), que le pointeur désigne comme version
    courante, précédente, abandonnée par un retour arrière, non désignée, ou pointeur d'un autre format (PointeurDeDesignation),
    refuse un fichier ajouté sous <CPython>. L'introduction de la section 10.1 du dépannage donne l'action de chaque cas, et ses
    commandes, remplies par les valeurs du poste, sont celles que cite le message : mise à jour depuis un autre kit pour la
    version courante, retrait par l'installateur de la version courante sinon, les deux suites pour un pointeur d'un autre
    format ; le dossier des versions cité est le chemin physique. Les colonnes Action des refus d'install.sh donnent la même
    règle ; la section 10.4 ne vaut que pour la version courante et accepte la destination sous ses deux formes."""
    from tests.unit import test_dist_linux_scripts as scripts
    from tests.unit.test_runtime_launchers_sh import fake_host

    text = section(DEPANNAGE, "Avant toute écriture")
    intro = text[:text.index("\n| Message")]
    update = "`<dossier de cet autre kit>/installer.sh update --destination <dossier des versions>`"
    removal = "`<dossier des versions>/<version courante>/installer.sh uninstall --kit-id <version>`"
    for statement in ("Version courante : la réinstaller", update, removal, "Pointeur d'un autre format : le message donne les deux suites",
                      "Version précédente, abandonnée par un retour arrière, ou que le pointeur ne désigne pas : la retirer, sans la "
                      "réinstaller", "pour une version précédente, le retour arrière ne sera plus possible",
                      "Le dossier des versions cité est le chemin physique du programme (liens résolus)",
                      "Les tableaux citent la forme d'une version courante"):
        assert statement in intro, f"dépannage, introduction de la section 10.1 : « {statement} » attendu"
    for role in scripts.ROLES:
        place = new_folder(tmp_path, role)
        real = place / "autre-disque"
        real.mkdir()
        os.symlink(real, place / "atelier")
        program = scripts.installed_program(real, role)
        reached = place / "atelier" / program.relative_to(real)
        added = program / CPYTHON / "lib/NOTES.txt"
        added.write_text("ajouté par erreur\n", encoding="utf-8")
        result = scripts.run(reached / "installer.sh", "--aide", fakes=fake_host(real, "Linux", "aarch64"))
        assert result.returncode == 1 and not (real / "interpreteur-lance").exists(), (role, result.stderr)
        assert scripts.installed_action(program, role) in result.stderr, (role, result.stderr)
        destination = os.path.realpath(program.parent)
        assert destination in result.stderr and str(place / "atelier") not in result.stderr, (role, result.stderr)
        values = {"<dossier des versions>": destination, "<version courante>": scripts.OTHER_VERSION, "<version>": program.name}
        if role == "courante":
            assert filled(update, values) in result.stderr and "uninstall" not in result.stderr, result.stderr
        elif role == "illisible":
            assert "réinstaller cette version" in result.stderr and f"uninstall --kit-id {program.name}" in result.stderr, result.stderr
        else:
            assert filled(removal, values) in result.stderr and "réinstaller cette version" not in result.stderr, (role, result.stderr)
            assert ("le retour arrière ne sera plus possible" in result.stderr) == (role == "precedente"), (role, result.stderr)
    rows = [row for table in tables(text) for row in table[1:] if row[4] == "`install.sh`" and "Programme installé" in row[2]]
    assert len(rows) >= 8, len(rows)
    for row in rows:
        for statement in ("selon ce que le pointeur dit de cette version", "version courante, la réinstaller",
                          "la retirer, sans la réinstaller, par la commande `uninstall --kit-id` que le message cite"):
            assert statement in row[2], f"dépannage, colonne Action : « {statement} » attendu ; {row[2][:200]}"
    repair = section(DEPANNAGE, REPAIR_TITLE)
    for statement in ("Cas visé : un fichier du programme de la version courante",
                      "Cette procédure ne vaut pas pour une version précédente, abandonnée ou non désignée",
                      "logique (chemin tapé à l'installation, qui traverse un lien) ou physique (liens résolus, celle que cite `installer.sh`)"):
        assert statement in repair, f"dépannage, section 10.4 : « {statement} » attendu"


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_status_relays_the_installer_sh_refusal_as_the_documents_quote_it(tmp_path, monkeypatch):
    """U6-04 (partie documentation) : `status` relaie, comme problème (code 1), le refus que l'installer.sh d'une version
    désignée opposerait à toute commande (contrôles rejoués par SystemProbe.installer_refusal, simulés ici par PosteSimule et
    rejoués réellement par test_dist_linux_scripts). Le « premier réflexe » du dépannage, sa ligne de la section 10.3 (code 1,
    source status_report, action selon la version), la ligne `status` de la section 8.8 du déploiement et la ligne
    d'observabilité de l'architecture citent ce problème ; chaque citation correspond à la ligne émise."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    destination, _, current, _ = simulation.installed(kit, tmp_path, "--no-start")
    refusal = (f"{CPYTHON}/lib/NOTES.txt ajouté à ce programme installé, absent de SHA256SUMS et de SYMLINKS : … ; rien n'a été "
               "exécuté.")
    ctx = simulation.context(kit, probe=simulation.PosteSimule(installer_refusals={current["program"]: refusal}))
    assert linux_install.main(["status", "--destination", str(destination)], ctx) == linux_install.EXIT_ERROR, simulation.screen(ctx)
    problem = next(line for line in simulation.output_of(ctx).splitlines() if "refuse toute commande" in line).strip()
    assert problem.startswith("- ") and problem.endswith(refusal), problem
    status_row = next(row for row in table_with_header(section(DEPLOIEMENT, "État, réparation, vérification et modèle principal"), "Commande")
                      if row[0].startswith("`installer.sh status`"))
    first_reflex = next(paragraph for paragraph in section(DEPANNAGE, "Installateur et lanceur Linux").split("\n\n")
                        if paragraph.startswith("Premier réflexe"))
    relay_row = troubleshooting_row("Contrôles de l'`installer.sh` d'une version désignée")
    assert relay_row[3] == str(linux_install.EXIT_ERROR) and relay_row[4] == "`status_report`", relay_row
    for statement in ("pour la version courante, la réinstaller", "pour la version précédente, la retirer par la commande `uninstall --kit-id`"):
        assert statement in relay_row[2], f"dépannage, section 10.3 : « {statement} » attendu ; {relay_row[2]}"
    for place, text in (("dépannage, premier réflexe", first_reflex), ("déploiement, section 8.8", status_row[1]),
                        ("dépannage, section 10.3", relay_row[0] + " " + relay_row[1])):
        quote = quote_with(text, "refuse toute commande")
        assert quote_matches(quote.replace("<programme>", "…"), problem.removeprefix("- ")), (place, quote, problem)
        assert "--controle-seul" in text or "lecture seule" in text, place
        assert "antérieur" in text and "n'est pas rejoué" in text, f"{place} : limite de l'installateur antérieur attendue"
    assert "refus que l'`installer.sh` d'une version désignée opposerait à toute commande" in read("docs/architecture/ARCHITECTURE.md")


@pytest.mark.skipif(sys.platform == "win32", reason="installateur Linux")
def test_a_destination_reached_through_a_link_is_named_under_both_forms(tmp_path, monkeypatch):
    """U6-01 et R5S-01 (parties documentation) : installation faite par un chemin qui traverse un lien (DossierParUnLien de
    test_dist_linux_install). Depuis le kit, `status --destination` rend l'état sans problème sous la forme tapée comme sous la
    forme physique, et l'installation garde la forme tapée, comme le disent la section 8.4 du déploiement et la section 10.4 du
    dépannage (la procédure elle-même est exécutée avec la forme physique par test_dist_linux_install)."""
    from tests.unit import test_dist_linux_install as simulation

    simulated_home(tmp_path, monkeypatch, "maison")
    kit = simulation.make_kit(tmp_path, monkeypatch)
    logical, physical, _, runner = simulation.installed_through_a_link(kit, tmp_path)
    assert os.path.realpath(logical) == str(physical) and str(physical) != str(logical)
    for written in (logical, physical):
        ctx = simulation.context(kit, runner=runner)
        assert linux_install.main(["status", "--destination", str(written)], ctx) == linux_install.EXIT_OK, simulation.screen(ctx)
        assert f"Installation : {logical}\n" in simulation.output_of(ctx), simulation.output_of(ctx)
    emplacements = section(DEPLOIEMENT, "Emplacements et fichiers écrits")
    for statement in ("se désigne sous l'une ou l'autre forme", "le pointeur garde le chemin tapé à l'installation",
                      "transmet et cite son chemin physique (liens résolus)", "ramène toute destination reçue à celle du pointeur"):
        assert statement in emplacements, f"déploiement, section 8.4 : « {statement} » attendu"
