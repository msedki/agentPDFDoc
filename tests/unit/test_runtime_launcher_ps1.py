"""Lanceur Windows rag.ps1 lu comme texte, sans PowerShell : options transmises au CLI, dont -NoBrowser.

Le poste Linux n'a pas pwsh : ces tests interprètent les seules lignes qui construisent `$arguments`, dont les formes
sont connues, et refusent toute autre forme. L'essai réel `.\\rag.ps1 open -NoBrowser` reste à faire sur un poste Windows.
"""

import json
import re
import sys

import pytest

from services.runtime import cli
from services.runtime.artifacts import ROOT

RAG_PS1 = ROOT / "rag.ps1"
CLI_SOURCE = ROOT / "services/runtime/cli.py"
BASE = "$arguments = @('-B','-m','services.runtime.cli',$Command)"
PROFILE_BRANCH = "if ($PSBoundParameters.ContainsKey('Profile')) { $arguments += @('--profile',$resolvedProfile) }"
CALL = "& $projectPython @arguments"
SWITCH = re.compile(r"^if \(\$(?P<name>\w+)\) \{ \$arguments \+= '(?P<flag>--[a-z-]+)' \}$")
VALUED = re.compile(r"^if \(\$(?P<name>\w+)\) \{ \$arguments \+= @\('(?P<flag>--[a-z-]+)',\$(?P=name)\) \}$")
BOUND_LONG = re.compile(r"^if \(\$PSBoundParameters\.ContainsKey\('(?P<name>\w+)'\)\) \{ \$arguments \+= "
                        r"@\('(?P<flag>--[a-z-]+)',\[string\]\$(?P=name)\) \}$")


def script() -> str:
    return RAG_PS1.read_text(encoding="utf-8-sig")


def profile_declaration(text: str) -> str:
    """Déclaration unique de -Profile ; la façade ne doit plus injecter de défaut manuel."""
    block = re.search(r"^param\($(?P<body>.*?)^\)$", text, re.MULTILINE | re.DOTALL)
    assert block is not None, "bloc param( ) introuvable"
    values = re.findall(r"^\s*(\[string\]\$Profile[^\r\n]*),$", block["body"], re.MULTILINE)
    assert len(values) == 1, "déclaration de -Profile introuvable ou répétée"
    return values[0]


# Profil manuel absolu dans une installation fictive C:\atelier, jamais injecté sans paramètre lié.
PROFILE = r"C:\atelier\config\local16-4b.yaml"
# Toutes les options de rag.ps1, comme dans le test de correspondance de rag.sh (test_runtime_launchers_sh.py).
ALL_OPTIONS = {"Profile": PROFILE, "Only": "qdrant", "Offline": True, "SkipModel": True, "Path": "sauvegarde", "Target": "racine neuve",
               "Report": "r.json", "QdrantStorage": "/q", "Ports": "1,2,3", "MemoryTotalBytes": 0}
ALL_ARGUMENTS = ["-B", "-m", "services.runtime.cli", "restore", "--profile", PROFILE, "--only", "qdrant", "--offline",
                 "--skip-model", "--path", "sauvegarde", "--target", "racine neuve", "--report", "r.json",
                 "--qdrant-storage", "/q", "--ports", "1,2,3", "--memory-total-bytes", "0"]


def parameters(text: str) -> dict[str, str]:
    """Paramètres déclarés dans le bloc param(...) : nom -> type (switch, string ou long)."""
    block = re.search(r"^param\($(?P<body>.*?)^\)$", text, re.MULTILINE | re.DOTALL)
    assert block is not None, "bloc param( ) introuvable"
    return {name: kind for kind, name in re.findall(r"\[(switch|string|long)\]\$(\w+)", block["body"])}


def options(text: str) -> dict[str, tuple[str, str]]:
    """Option du CLI ajoutée par chaque paramètre : nom -> (forme, option)."""
    mapping = {}
    for line in (line.strip() for line in text.splitlines()):
        if "$arguments" not in line or line in {BASE, CALL, PROFILE_BRANCH}:
            continue
        match = SWITCH.match(line) or VALUED.match(line) or BOUND_LONG.match(line)
        assert match is not None, f"forme de rag.ps1 non interprétée : {line}"
        assert match["name"] not in mapping, f"paramètre transmis deux fois : {match['name']}"
        mapping[match["name"]] = ("switch" if match.re is SWITCH else "long" if match.re is BOUND_LONG else "string", match["flag"])
    return mapping


def cli_arguments(text: str, command: str, bound: dict[str, str | bool | int]) -> list[str]:
    """Arguments que rag.ps1 passe à l'interpréteur pour la commande et les paramètres liés donnés."""
    lines = [line.strip() for line in text.splitlines()]
    assert lines.count(BASE) == lines.count(PROFILE_BRANCH) == lines.count(CALL) == 1
    assert lines.index(BASE) < lines.index(PROFILE_BRANCH) < lines.index(CALL)
    declared, mapping = parameters(text), options(text)
    assert declared["Profile"] == "string" and declared["Model"] == "string"
    arguments = ["-B", "-m", "services.runtime.cli", command]
    if "Profile" in bound:
        arguments += ["--profile", str(bound["Profile"])]
    for name, (kind, flag) in mapping.items():
        # La forme de la ligne suit le type déclaré : un switch n'ajoute que l'option, une chaîne l'option et sa valeur.
        assert declared.get(name) == kind, f"{name} : déclaré {declared.get(name)}, transmis comme {kind}"
        value = bound.get(name)
        if kind == "switch" and value is True:
            arguments.append(flag)
        elif kind == "string" and value:
            arguments += [flag, str(value)]
        elif kind == "long" and name in bound:
            assert type(value) is int, f"{name} : valeur liée non entière"
            arguments += [flag, str(value)]
    return arguments


def test_rag_ps1_omits_an_unbound_profile_and_keeps_the_model_choice():
    # W060 : le CLI garde le repli historique ; la façade ne transforme pas une absence en choix manuel.
    text = script()
    assert profile_declaration(text) == "[string]$Profile" and parameters(text)["Model"] == "string"
    assert cli_arguments(text, "up", {}) == ["-B", "-m", "services.runtime.cli", "up"]
    assert cli_arguments(text, "init-profile", {"Target": "racine neuve"}) == [
        "-B", "-m", "services.runtime.cli", "init-profile", "--target", "racine neuve"]


def test_rag_ps1_no_browser_is_a_switch_that_adds_the_cli_option():
    text = script()
    assert parameters(text)["NoBrowser"] == "switch"
    assert options(text)["NoBrowser"] == ("switch", "--no-browser")
    # Déclaration et transmission, nulle part ailleurs.
    assert text.count("$NoBrowser") == 2
    assert cli_arguments(text, "open", {"NoBrowser": True}) == ["-B", "-m", "services.runtime.cli", "open",
                                                                "--no-browser"]


def test_rag_ps1_arguments_are_unchanged_without_no_browser():
    text = script()
    assert cli_arguments(text, "open", {}) == ["-B", "-m", "services.runtime.cli", "open"]
    assert cli_arguments(text, "restore", ALL_OPTIONS) == ALL_ARGUMENTS
    assert cli_arguments(text, "restore", {**ALL_OPTIONS, "NoBrowser": True}) == [*ALL_ARGUMENTS, "--no-browser"]


def test_rag_ps1_passes_exactly_the_options_of_the_cli():
    # Chaque option transmise existe dans le CLI, et chaque option du CLI a son paramètre dans rag.ps1.
    declared = set(re.findall(r'(?:parser|memory)\.add_argument\("(--[a-z-]+)"', CLI_SOURCE.read_text(encoding="utf-8")))
    passed = {flag for _, flag in options(script()).values()} | {"--profile"}
    # --memory-unknown est réservé au CLI/installateur Linux ; Windows transmet sa mesure long, même zéro.
    assert passed | {"--memory-unknown"} == declared


@pytest.mark.parametrize("value", [0, 1, 16_000_000_000, 2**63 - 1])
def test_rag_ps1_passes_a_bound_long_memory_measure_even_when_zero(value):
    text = script()
    assert parameters(text)["MemoryTotalBytes"] == "long"
    assert options(text)["MemoryTotalBytes"] == ("long", "--memory-total-bytes")
    assert cli_arguments(text, "init-profile", {"Model": "qwen3.5:2b", "MemoryTotalBytes": value}) == [
        "-B", "-m", "services.runtime.cli", "init-profile", "--model", "qwen3.5:2b", "--memory-total-bytes", str(value)]
    assert cli_arguments(text, "init-profile", {}) == ["-B", "-m", "services.runtime.cli", "init-profile"]


def test_rag_ps1_parser_refuses_a_truthiness_guard_for_a_long_memory_measure():
    branch = "if ($PSBoundParameters.ContainsKey('MemoryTotalBytes')) { $arguments += @('--memory-total-bytes',[string]$MemoryTotalBytes) }"
    changed = script().replace(branch, "if ($MemoryTotalBytes) { $arguments += @('--memory-total-bytes',$MemoryTotalBytes) }")
    assert changed != script()
    with pytest.raises(AssertionError, match="MemoryTotalBytes.*long.*string"):
        cli_arguments(changed, "init-profile", {"MemoryTotalBytes": 0})


@pytest.mark.parametrize("model,name", [("qwen3.5:2b", "local16.yaml"), ("qwen3.5:4b", "local16-4b.yaml")])
def test_rag_ps1_model_omits_the_default_profile_and_reaches_the_cli(monkeypatch, capsys, model, name):
    """Lignes PowerShell interprétées, CLI réel ; démarrage explicitement doublé, aucun PowerShell ni service."""
    arguments = cli_arguments(script(), "up", {"Model": model})
    assert arguments == ["-B", "-m", "services.runtime.cli", "up", "--model", model]
    started = []
    monkeypatch.setattr(sys, "argv", ["rag", *arguments[3:]])
    monkeypatch.setattr(cli, "start", lambda path: started.append(path) or {"status": "explicit_start_double"})
    assert cli.main() == 0 and started == [ROOT / "config" / name]
    assert json.loads(capsys.readouterr().out)["status"] == "explicit_start_double"


def test_rag_ps1_keeps_an_explicit_profile_and_cli_refuses_combining_it_with_model(monkeypatch, capsys):
    supplied = r"C:\atelier utilisateur\profil.yaml"
    assert cli_arguments(script(), "up", {"Profile": supplied}) == ["-B", "-m", "services.runtime.cli", "up", "--profile", supplied]
    arguments = cli_arguments(script(), "up", {"Profile": supplied, "Model": "qwen3.5:2b"})
    assert arguments == ["-B", "-m", "services.runtime.cli", "up", "--profile", supplied, "--model", "qwen3.5:2b"]
    started = []
    monkeypatch.setattr(sys, "argv", ["rag", *arguments[3:]])
    monkeypatch.setattr(cli, "start", lambda path: started.append(path))
    assert cli.main() == 1 and started == []
    assert json.loads(capsys.readouterr().out)["error"] == "ValueError"


@pytest.mark.parametrize("branch", [
    "if ($Model) { $arguments += @('--profile',$resolvedProfile) }",
    PROFILE_BRANCH + "\n" + PROFILE_BRANCH,
    "",
])
def test_rag_ps1_parser_refuses_a_changed_or_missing_profile_condition(branch):
    changed = script().replace(PROFILE_BRANCH, branch)
    with pytest.raises(AssertionError):
        cli_arguments(changed, "up", {"Model": "qwen3.5:2b"})
