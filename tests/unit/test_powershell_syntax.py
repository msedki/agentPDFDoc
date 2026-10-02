"""Scripts PowerShell du dépôt (rag.ps1, bootstrap.ps1, tools/dist/*.ps1) lus et exécutés par PowerShell lui-même.

L'analyseur officiel ([System.Management.Automation.Language.Parser]::ParseFile) d'un PowerShell disponible lit chaque
script : variable d'environnement RAG_TEST_PWSH, sinon `pwsh` ou `powershell` du PATH. Sans PowerShell, les tests sont
ignorés avec leur motif. Le raccourci « Diagnostic de l'atelier » et l'affichage du verdict par l'installation sont aussi
rendus par PowerShell, sur un verdict de doctor réel : la proposition de la rubrique « calcul », à laquelle renvoie le
résumé, doit être affichée (revue J11 runtime-4).

Limite : sur un poste Linux, ces scripts sont analysés et exécutés par PowerShell 7 (édition Core, 7.4 LTS sur le poste
du chantier), pas par Windows PowerShell 5.1, cible du kit ; une construction propre à PowerShell 7 passerait ici et
échouerait sous 5.1. Le rejeu sous Windows reste la preuve pour 5.1.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted([ROOT / "rag.ps1", ROOT / "bootstrap.ps1", *(ROOT / "tools/dist").glob("*.ps1")])
# Analyse de chaque fichier passé en argument ; erreurs rendues en JSON, puis version et édition de PowerShell.
PARSE = r"""
$results = foreach ($path in $args) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
    [ordered]@{ path = $path; errors = @($errors | ForEach-Object {
        [ordered]@{ line = $_.Extent.StartLineNumber; column = $_.Extent.StartColumnNumber; message = $_.Message } }) }
}
ConvertTo-Json -InputObject @($results) -Depth 4 -Compress
$PSVersionTable.PSVersion.ToString()
$PSVersionTable.PSEdition
"""
# Instruction de install.ps1 désignée par son arbre syntaxique, exécutée telle quelle sur un verdict de doctor :
# boucle d'affichage des rubriques après le démarrage, ou bloc « if ($NoStart) » d'une installation sans démarrage.
INSTALL_STATEMENT = r"""
param([string]$Install, [string]$Verdict, [string]$Statement)
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Install, [ref]$null, [ref]$null)
$node = $ast.Find({
    param($item)
    if ($Statement -eq 'rubriques') {
        $item -is [System.Management.Automation.Language.ForEachStatementAst] -and
            $item.Condition.Extent.Text -eq '$doctor.verdict.rubrics'
    } else {
        $item -is [System.Management.Automation.Language.IfStatementAst] -and
            $item.Clauses[0].Item1.Extent.Text -eq '$NoStart'
    }
}, $true)
if (-not $node) { throw "Instruction $Statement introuvable dans $Install" }
$doctor = Get-Content -LiteralPath $Verdict -Raw -Encoding UTF8 | ConvertFrom-Json
$NoStart = $true
Invoke-Expression $node.Extent.Text
"""


def powershell() -> str | None:
    """PowerShell des tests : RAG_TEST_PWSH, sinon pwsh ou powershell du PATH ; None s'il n'y en a aucun."""
    configured = os.environ.get("RAG_TEST_PWSH")
    if configured:
        return configured
    return shutil.which("pwsh") or shutil.which("powershell")


def run_powershell(arguments: list[str], home: Path, *, timeout: float = 120) -> subprocess.CompletedProcess:
    """PowerShell sans profil ni télémétrie ; caches et modules dans `home`, jamais dans le compte de l'utilisateur."""
    executable = powershell()
    if executable is None:
        pytest.skip("PowerShell absent : ni RAG_TEST_PWSH, ni pwsh, ni powershell dans le PATH")
    home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HOME": str(home), "XDG_CACHE_HOME": str(home / "cache"), "XDG_DATA_HOME": str(home / "data"),
           "XDG_CONFIG_HOME": str(home / "config"), "POWERSHELL_TELEMETRY_OPTOUT": "1",
           "POWERSHELL_UPDATECHECK": "Off", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
    return subprocess.run([executable, "-NoLogo", "-NoProfile", "-NonInteractive", *arguments], capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout, env=env, check=False)


def parse(paths: list[Path], home: Path) -> dict:
    script = home / "parse.ps1"
    home.mkdir(parents=True, exist_ok=True)
    script.write_text(PARSE, encoding="utf-8")
    done = run_powershell(["-File", str(script), *map(str, paths)], home)
    assert done.returncode == 0, done.stderr
    payload, version, edition = done.stdout.strip().splitlines()[-3:]
    return {"results": {item["path"]: item["errors"] for item in json.loads(payload)}, "version": version,
            "edition": edition}


@pytest.fixture(scope="module")
def parsed(tmp_path_factory) -> dict:
    return parse(SCRIPTS, tmp_path_factory.mktemp("powershell-home"))


def test_every_powershell_script_of_the_repository_is_analysed():
    names = {path.relative_to(ROOT).as_posix() for path in SCRIPTS}
    assert {"rag.ps1", "bootstrap.ps1", "tools/dist/install.ps1", "tools/dist/raccourci.ps1"} <= names


@pytest.mark.parametrize("script", [path.relative_to(ROOT).as_posix() for path in SCRIPTS])
def test_powershell_script_parses_without_syntax_error(parsed, script):
    errors = parsed["results"][str(ROOT / script)]
    assert errors == [], f"PowerShell {parsed['version']} ({parsed['edition']}) : {errors}"


def test_the_parser_reports_a_syntax_error(tmp_path):
    # Contrôle positif : une accolade non fermée est bien signalée, l'absence d'erreur ci-dessus a donc un sens.
    broken = tmp_path / "casse.ps1"
    broken.write_text("foreach ($item in @(1, 2)) {\n    Write-Output $item\n", encoding="utf-8")
    errors = parse([broken], tmp_path / "home")["results"][str(broken)]
    assert errors and errors[0]["line"] >= 1


@pytest.fixture
def nvidia_verdict(tmp_path, monkeypatch) -> tuple[Path, dict]:
    """Verdict de doctor d'un poste Windows à GPU NVIDIA sur une voie non qualifiée, écrit en JSON comme par rag.ps1."""
    from services.runtime import platforms
    from tests.unit.test_runtime_verdict import WINDOWS_CASES, verdict_of

    monkeypatch.setattr(platforms, "WINDOWS", True)
    monkeypatch.setattr(platforms, "LAUNCHER", r".\rag.ps1")
    verdict = verdict_of(WINDOWS_CASES["gpu_path_not_qualified"][0])
    assert verdict["summary"].endswith("voir la rubrique calcul.") and verdict["rubrics"][-1]["proposal"]
    path = tmp_path / "doctor.json"
    path.write_text(json.dumps({"verdict": verdict}, ensure_ascii=False), encoding="utf-8")
    return path, verdict


def test_the_diagnostic_shortcut_prints_the_proposal_the_summary_points_to(tmp_path, nvidia_verdict):
    # Raccourci réel, dans l'arborescence du programme installé ; rag.ps1 est un double qui rend le verdict.
    doctor, verdict = nvidia_verdict
    program = tmp_path / "programme"
    (program / "tools/dist").mkdir(parents=True)
    (program / "tools/dist/raccourci.ps1").write_bytes((ROOT / "tools/dist/raccourci.ps1").read_bytes())
    (program / "rag.ps1").write_text("param([string]$Command, [string]$Profile)\n"
                                     f"Get-Content -LiteralPath '{doctor}' -Raw -Encoding UTF8\n"
                                     "exit 0\n", encoding="utf-8")
    done = run_powershell(["-File", str(program / "tools/dist/raccourci.ps1"), "-Action", "diagnostic", "-Profile",
                           str(tmp_path / "profile.yaml"), "-NoPause"], tmp_path / "home")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == verdict["summary"]
    calcul = lines.index(f"[vert] calcul : {verdict['rubrics'][-1]['message']}")
    assert lines[calcul + 1:] == [f"        Proposition : {verdict['rubrics'][-1]['proposal']}"]


@pytest.mark.parametrize(("statement", "expected"), [
    ("rubriques", "      Proposition : {proposal}"),
    ("sans-demarrage", "  Proposition, rubrique calcul : {proposal}"),
])
def test_the_installer_prints_the_proposal_the_summary_points_to(tmp_path, nvidia_verdict, statement, expected):
    doctor, verdict = nvidia_verdict
    script = tmp_path / "instruction.ps1"
    script.write_text(INSTALL_STATEMENT, encoding="utf-8")
    done = run_powershell(["-File", str(script), "-Install", str(ROOT / "tools/dist/install.ps1"), "-Verdict",
                           str(doctor), "-Statement", statement], tmp_path / "home")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    proposal = expected.format(proposal=verdict["rubrics"][-1]["proposal"])
    if statement == "rubriques":
        assert lines[-2:] == [f"  [vert] calcul : {verdict['rubrics'][-1]['message']}", proposal]
    else:
        assert lines == [proposal]
