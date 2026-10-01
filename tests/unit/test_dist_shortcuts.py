"""Raccourcis du menu Démarrer (DIST-06) : création sans droit dans un dossier choisi, et actions sur une instance arrêtée."""

import json
import subprocess
import sys

import pytest

from services.runtime.artifacts import ROOT
from services.runtime.profile_setup import write_user_profile
from tests.unit.test_runtime_profile_setup import ports

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="raccourcis Windows et PowerShell 5.1")
POWERSHELL = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]


def run(arguments, timeout=180):
    process = subprocess.run(POWERSHELL + arguments, capture_output=True, timeout=timeout)
    return process.returncode, process.stdout.decode("utf-8")


def test_shortcuts_point_to_the_action_script_with_the_user_profile(tmp_path):
    menu, profile = tmp_path / "menu", tmp_path / "données" / "profile.yaml"
    # Appel comme dans install.ps1 : même processus, console déjà passée en UTF-8.
    code, output = run(["-Command", f"[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '{ROOT / 'tools/dist/shortcuts.ps1'}' "
                                    f"-Program '{ROOT}' -Profile '{profile}' -Menu '{menu}'"])
    assert code == 0, output
    assert json.loads(output)["status"] == "created"
    read = (f"$s = New-Object -ComObject WScript.Shell; Get-ChildItem -LiteralPath '{menu}' -Filter *.lnk | Sort-Object Name | ForEach-Object {{ "
            "$l = $s.CreateShortcut($_.FullName); [ordered]@{ name = $_.BaseName; target = $l.TargetPath; arguments = $l.Arguments; "
            "directory = $l.WorkingDirectory; description = $l.Description } } | ConvertTo-Json")
    code, output = run(["-Command", "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); " + read])
    links = {item["name"]: item for item in json.loads(output)}
    assert code == 0 and set(links) == {"Atelier documentaire", "Arrêter l'atelier", "Diagnostic de l'atelier", "Sauvegarder l'atelier"}
    actions = {"Atelier documentaire": "ouvrir", "Arrêter l'atelier": "arreter", "Diagnostic de l'atelier": "diagnostic", "Sauvegarder l'atelier": "sauvegarder"}
    for name, link in links.items():
        assert link["target"].lower().endswith(r"\system32\windowspowershell\v1.0\powershell.exe")
        assert link["arguments"] == f'-NoProfile -ExecutionPolicy Bypass -File "{ROOT / "tools/dist/raccourci.ps1"}" -Action {actions[name]} -Profile "{profile}"'
        assert link["directory"] == str(ROOT) and link["description"]


def test_shortcut_actions_on_a_stopped_instance_report_in_french_without_pausing(tmp_path):
    created = write_user_profile(ROOT / "config/local16.yaml", tmp_path / "utilisateur", ports=ports(), program_root=ROOT, storage_max=1000)
    action = ["-File", str(ROOT / "tools/dist/raccourci.ps1"), "-Profile", created["profile"], "-NoPause"]
    code, output = run(action + ["-Action", "sauvegarder"])
    assert code == 1 and "Échec : Sauvegarde : démarrer l'instance propriétaire avec rag up" in output, output
    code, output = run(action + ["-Action", "diagnostic"])
    assert code == 0, output
    assert "[orange] services : Atelier arrêté." in output and r"Démarrez-le : .\rag.ps1 up" in output
    assert "├" not in output and "�" not in output
