"""Lanceur Windows rag.ps1 lu comme texte, sans PowerShell : options transmises au CLI, dont -NoBrowser.

Le poste Linux n'a pas pwsh : ces tests interprètent les seules lignes qui construisent `$arguments`, dont les formes
sont connues, et refusent toute autre forme. L'essai réel `.\\rag.ps1 open -NoBrowser` reste à faire sur un poste Windows.
"""

import re

from services.runtime.artifacts import ROOT

RAG_PS1 = ROOT / "rag.ps1"
CLI_SOURCE = ROOT / "services/runtime/cli.py"
PROFILE = r"C:\atelier\config\local16.yaml"
BASE = "$arguments = @('-m','services.runtime.cli',$Command,'--profile',$resolvedProfile)"
CALL = "& $projectPython @arguments"
SWITCH = re.compile(r"^if \(\$(?P<name>\w+)\) \{ \$arguments \+= '(?P<flag>--[a-z-]+)' \}$")
VALUED = re.compile(r"^if \(\$(?P<name>\w+)\) \{ \$arguments \+= @\('(?P<flag>--[a-z-]+)',\$(?P=name)\) \}$")
# Toutes les options de rag.ps1, comme dans le test de correspondance de rag.sh (test_runtime_launchers_sh.py).
ALL_OPTIONS = {"Only": "qdrant", "Offline": True, "SkipModel": True, "Path": "sauvegarde", "Target": "racine neuve",
               "Report": "r.json", "QdrantStorage": "/q", "Ports": "1,2,3"}
ALL_ARGUMENTS = ["-m", "services.runtime.cli", "restore", "--profile", PROFILE, "--only", "qdrant", "--offline",
                 "--skip-model", "--path", "sauvegarde", "--target", "racine neuve", "--report", "r.json",
                 "--qdrant-storage", "/q", "--ports", "1,2,3"]


def script() -> str:
    return RAG_PS1.read_text(encoding="utf-8-sig")


def parameters(text: str) -> dict[str, str]:
    """Paramètres déclarés dans le bloc param(...) : nom -> type (switch ou string)."""
    block = re.search(r"^param\($(?P<body>.*?)^\)$", text, re.MULTILINE | re.DOTALL)
    assert block is not None, "bloc param( ) introuvable"
    return {name: kind for kind, name in re.findall(r"\[(switch|string)\]\$(\w+)", block["body"])}


def options(text: str) -> dict[str, tuple[str, str]]:
    """Option du CLI ajoutée par chaque paramètre : nom -> (forme, option)."""
    mapping = {}
    for line in (line.strip() for line in text.splitlines()):
        if "$arguments" not in line or line in {BASE, CALL}:
            continue
        match = SWITCH.match(line) or VALUED.match(line)
        assert match is not None, f"forme de rag.ps1 non interprétée : {line}"
        assert match["name"] not in mapping, f"paramètre transmis deux fois : {match['name']}"
        mapping[match["name"]] = ("switch" if match.re is SWITCH else "string", match["flag"])
    return mapping


def cli_arguments(text: str, command: str, bound: dict[str, str | bool]) -> list[str]:
    """Arguments que rag.ps1 passe à l'interpréteur pour la commande et les paramètres liés donnés."""
    lines = [line.strip() for line in text.splitlines()]
    assert lines.count(BASE) == 1 and lines.count(CALL) == 1 and lines.index(BASE) < lines.index(CALL)
    declared, mapping = parameters(text), options(text)
    arguments = ["-m", "services.runtime.cli", command, "--profile", PROFILE]
    for name, (kind, flag) in mapping.items():
        # La forme de la ligne suit le type déclaré : un switch n'ajoute que l'option, une chaîne l'option et sa valeur.
        assert declared.get(name) == kind, f"{name} : déclaré {declared.get(name)}, transmis comme {kind}"
        value = bound.get(name)
        if kind == "switch" and value is True:
            arguments.append(flag)
        elif kind == "string" and value:
            arguments += [flag, str(value)]
    return arguments


def test_rag_ps1_no_browser_is_a_switch_that_adds_the_cli_option():
    text = script()
    assert parameters(text)["NoBrowser"] == "switch"
    assert options(text)["NoBrowser"] == ("switch", "--no-browser")
    # Déclaration et transmission, nulle part ailleurs.
    assert text.count("$NoBrowser") == 2
    assert cli_arguments(text, "open", {"NoBrowser": True}) == ["-m", "services.runtime.cli", "open", "--profile", PROFILE,
                                                                "--no-browser"]


def test_rag_ps1_arguments_are_unchanged_without_no_browser():
    text = script()
    assert cli_arguments(text, "open", {}) == ["-m", "services.runtime.cli", "open", "--profile", PROFILE]
    assert cli_arguments(text, "restore", ALL_OPTIONS) == ALL_ARGUMENTS
    assert cli_arguments(text, "restore", {**ALL_OPTIONS, "NoBrowser": True}) == [*ALL_ARGUMENTS, "--no-browser"]


def test_rag_ps1_passes_exactly_the_options_of_the_cli():
    # Chaque option transmise existe dans le CLI, et chaque option du CLI a son paramètre dans rag.ps1.
    declared = set(re.findall(r'parser\.add_argument\("(--[a-z-]+)"', CLI_SOURCE.read_text(encoding="utf-8")))
    passed = {flag for _, flag in options(script()).values()} | {"--profile"}
    assert passed == declared
