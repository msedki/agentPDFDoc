"""Désinstallation (DIST-08) : version retirée, raccourcis d'une autre version et données conservés, jonctions non suivies.

Le script n'est jamais lancé depuis le dépôt : chaque essai en place une copie dans un faux programme sous tmp_path.
`rag.ps1` y est remplacé par une doublure de test qui journalise les commandes reçues et rend l'état demandé.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from services.runtime.artifacts import ROOT

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="désinstallation Windows et PowerShell 5.1")
POWERSHELL = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
RAG_DOUBLE = """param([string]$Command, [string]$Profile)
Add-Content -LiteralPath $env:RAG_DOUBLE_LOG -Value $Command
if ($Command -eq 'status') { [ordered]@{ status = $env:RAG_DOUBLE_STATUS; supervisor = @{ executable = $env:RAG_DOUBLE_EXECUTABLE } } | ConvertTo-Json }
else { '{"status": "stopped"}' }
exit 0
"""


def fake_program(folder: Path, *, installed: bool = True) -> Path:
    (folder / "tools/dist").mkdir(parents=True)
    for name in ("uninstall.ps1", "shortcuts.ps1", "raccourci.ps1"):
        (folder / "tools/dist" / name).write_bytes((ROOT / "tools/dist" / name).read_bytes())
    (folder / "rag.ps1").write_text(RAG_DOUBLE, encoding="utf-8")
    if installed:
        (folder / "kit-manifest.json").write_text('{"version": "0.0.0-essai"}', encoding="utf-8")
        (folder / "SHA256SUMS").write_text("", encoding="utf-8")
    (folder / ".runtime/python/cpython").mkdir(parents=True)
    (folder / ".runtime/python/cpython/python.txt").write_text("interpréteur", encoding="utf-8")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(folder / ".runtime/python/3.12"), str(folder / ".runtime/python/cpython")], check=True, capture_output=True)
    return folder


def snapshot(folder: Path) -> dict[str, str]:
    return {path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.rglob("*")) if path.is_file()}


def powershell(arguments, env, timeout=120):
    process = subprocess.run(POWERSHELL + arguments, capture_output=True, timeout=timeout, env={**os.environ, **env})
    return process.returncode, process.stdout.decode("utf-8")


def shortcuts(program: Path, profile: Path, menu: Path):
    command = (f"[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '{program / 'tools/dist/shortcuts.ps1'}' "
               f"-Program '{program}' -Profile '{profile}' -Menu '{menu}'")
    assert powershell(["-Command", command], {})[0] == 0


@pytest.fixture
def user(tmp_path):
    data = tmp_path / "donnees"
    (data / "data/originals").mkdir(parents=True)
    (data / "profile.yaml").write_text("app: {data_dir: data}\n", encoding="utf-8")
    (data / "data/originals/manuel.pdf").write_bytes(b"%PDF-1.7 original")
    outside = tmp_path / "hors-programme"
    outside.mkdir()
    (outside / "temoin.txt").write_text("ne doit pas disparaître", encoding="utf-8")
    return data, outside, tmp_path / "journal.txt"


def test_uninstall_removes_this_version_stops_its_instance_and_keeps_data(tmp_path, user):
    data, outside, log = user
    program = fake_program(tmp_path / "Programmes/AtelierPDF/0.0.0-essai")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(program / "lien-externe"), str(outside)], check=True, capture_output=True)
    menu = tmp_path / "menu"
    shortcuts(program, data / "profile.yaml", menu)
    before = snapshot(data)
    code, output = powershell(["-File", str(program / "tools/dist/uninstall.ps1"), "-Profile", str(data / "profile.yaml"), "-Menu", str(menu)],
                              {"RAG_DOUBLE_LOG": str(log), "RAG_DOUBLE_STATUS": "running", "RAG_DOUBLE_EXECUTABLE": str(program / ".venv/Scripts/python.exe")})
    assert code == 0, output
    assert log.read_text(encoding="utf-8").split() == ["status", "down"]
    assert "[ok] raccourcis : 4 retirés" in output and not menu.exists()
    assert not program.exists() and not program.parent.exists()
    assert (outside / "temoin.txt").read_text(encoding="utf-8") == "ne doit pas disparaître"
    assert snapshot(data) == before
    report = json.loads(Path(output.split("Rapport : ")[1].strip()).read_text(encoding="utf-8-sig"))
    assert report["status"] == "uninstalled" and report["stopped"] is True


def test_uninstall_leaves_the_instance_and_shortcuts_of_another_version(tmp_path, user):
    data, _, log = user
    program, other = fake_program(tmp_path / "Programmes/AtelierPDF/0.0.0-essai"), fake_program(tmp_path / "Programmes/AtelierPDF/0.0.1-essai")
    menu = tmp_path / "menu"
    shortcuts(other, data / "profile.yaml", menu)
    code, output = powershell(["-File", str(program / "tools/dist/uninstall.ps1"), "-Profile", str(data / "profile.yaml"), "-Menu", str(menu)],
                              {"RAG_DOUBLE_LOG": str(log), "RAG_DOUBLE_STATUS": "running", "RAG_DOUBLE_EXECUTABLE": str(other / ".venv/Scripts/python.exe")})
    assert code == 0, output
    assert log.read_text(encoding="utf-8").split() == ["status"]
    assert len(list(menu.glob("*.lnk"))) == 4 and not program.exists() and other.exists()


def test_uninstall_refuses_a_folder_that_is_not_an_installation(tmp_path, user):
    data, _, log = user
    folder = fake_program(tmp_path / "depot", installed=False)
    code, output = powershell(["-File", str(folder / "tools/dist/uninstall.ps1"), "-Profile", str(data / "profile.yaml"), "-Menu", str(tmp_path / "menu")],
                              {"RAG_DOUBLE_LOG": str(log), "RAG_DOUBLE_STATUS": "stopped", "RAG_DOUBLE_EXECUTABLE": ""})
    assert code == 1
    assert f"Désinstallation arrêtée : {folder} n'est pas une installation de l'atelier (kit-manifest.json absent) ; rien n'a été supprimé." in output
    assert (folder / "rag.ps1").is_file() and not log.exists()
