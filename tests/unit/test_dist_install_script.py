"""install.ps1 sur un kit factice altéré : arrêt avant toute installation, messages accentués intacts, préambule de mise à jour.

Le Python du kit est le CPython du dépôt, relié par une jonction (aucun droit administrateur requis). L'essai du 01/10
a montré que PowerShell 5.1 lit sinon la sortie UTF-8 de Python selon la page OEM de la console (« é » devient « ├® »).
La version déjà installée est une doublure de test : son `rag.ps1` journalise les commandes et rend les réponses attendues.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from tests.unit.test_dist_uninstall import ROOT, fake_program

KIT_PYTHON = Path(".runtime/python/cpython-3.12.14-windows-x86_64-none")
PREVIOUS_DOUBLE = """param([string]$Command, [string]$Profile, [string]$Path)
Add-Content -LiteralPath $env:RAG_DOUBLE_LOG -Value $Command
switch ($Command) {
    'up' { '{"status": "running"}' }
    'backup' { '{"path": "D:\\\\sauvegardes\\\\essai"}' }
    'verify' { '{"state": "verified"}' }
    'down' { '{"status": "stopped"}' }
}
exit 0
"""

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 vise Windows PowerShell 5.1"),
    pytest.mark.skipif(not (ROOT / KIT_PYTHON / "python.exe").is_file(), reason="CPython du runtime non provisionné"),
    pytest.mark.skipif(psutil.virtual_memory().total < 15 * 1024**3, reason="prérequis mémoire d'install.ps1 non remplis par ce poste"),
]


@pytest.fixture
def kit(tmp_path):
    """Kit factice dont l'unique fichier ne correspond pas à SHA256SUMS ; la jonction est retirée seule en fin d'essai."""
    folder = tmp_path / "kit"
    (folder / "tools/dist").mkdir(parents=True)
    for name in ("install.ps1", "build_kit.py", "notices.py"):
        (folder / "tools/dist" / name).write_bytes((ROOT / "tools/dist" / name).read_bytes())
    (folder / KIT_PYTHON.parent).mkdir(parents=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(folder / KIT_PYTHON), str(ROOT / KIT_PYTHON)], check=True, capture_output=True)
    (folder / "lisez-moi.txt").write_bytes(b"contenu altere")
    (folder / "SHA256SUMS").write_text("0" * 64 + "  lisez-moi.txt\n", encoding="utf-8")
    (folder / "kit-manifest.json").write_text(json.dumps({"version": "0.0.2-essai", "bytes": 1}), encoding="utf-8")
    yield folder
    os.rmdir(folder / KIT_PYTHON)  # retire la jonction seule, jamais le CPython du dépôt


def install(kit, *arguments, env=None):
    run = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(kit / "tools/dist/install.ps1"), *map(str, arguments)],
                         capture_output=True, timeout=120, env={**{k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}, **(env or {})})
    return run.returncode, run.stdout.decode("utf-8")


def test_altered_kit_file_stops_the_installation_with_an_intact_french_message(kit, tmp_path):
    programs, data = tmp_path / "programmes", tmp_path / "donnees"
    code, output = install(kit, "-Destination", programs, "-DataRoot", data, "-Menu", tmp_path / "menu", "-NoStart")
    assert code == 1, output
    assert "Installation arrêtée : Fichier du kit altéré : lisez-moi.txt (empreinte différente) Recopiez le kit ; rien n'a été installé." in output
    assert "├" not in output and "\ufffd" not in output
    assert not (programs / "0.0.2-essai").exists()
    [report] = data.glob("install-*.json")
    saved = json.loads(report.read_text(encoding="utf-8-sig"))
    assert saved["status"] == "failed" and saved["error"].startswith("Fichier du kit altéré : lisez-moi.txt")


def test_existing_data_without_update_is_refused_before_any_copy(kit, tmp_path):
    data = tmp_path / "donnees"
    data.mkdir()
    (data / "profile.yaml").write_text("app: {data_dir: data}\n", encoding="utf-8")
    code, output = install(kit, "-Destination", tmp_path / "programmes", "-DataRoot", data, "-Menu", tmp_path / "menu", "-NoStart")
    assert code == 1
    assert (f"Un atelier est déjà installé avec ces données ({data / 'profile.yaml'}). Pour installer la version 0.0.2-essai à côté, "
            "relancez avec -Update : sauvegarde vérifiée, puis bascule des raccourcis. Rien n'a été installé.") in output
    assert not (tmp_path / "programmes").exists() and not list(data.glob("install-*.json"))


def test_update_backs_up_verifies_and_stops_the_previous_version_before_copying(kit, tmp_path):
    data, menu, log = tmp_path / "donnees", tmp_path / "menu", tmp_path / "journal.txt"
    data.mkdir()
    (data / "profile.yaml").write_text("app: {data_dir: data}\n", encoding="utf-8")
    previous = fake_program(tmp_path / "programmes/0.0.1-essai")
    (previous / "rag.ps1").write_text(PREVIOUS_DOUBLE, encoding="utf-8")
    command = (f"[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & '{previous / 'tools/dist/shortcuts.ps1'}' "
               f"-Program '{previous}' -Profile '{data / 'profile.yaml'}' -Menu '{menu}'")
    assert subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], capture_output=True).returncode == 0
    code, output = install(kit, "-Destination", tmp_path / "programmes", "-DataRoot", data, "-Menu", menu, "-Update", "-NoStart",
                           env={"RAG_DOUBLE_LOG": str(log)})
    assert code == 1, output
    # La doublure de l'ancienne version a reçu, dans l'ordre : démarrage, sauvegarde, vérification, arrêt.
    assert log.read_text(encoding="utf-8").split() == ["up", "backup", "verify", "down"]
    assert f"[ok] sauvegarde D:\\sauvegardes\\essai vérifiée ; version en place ({previous}) arrêtée" in output
    assert "Installation arrêtée : Fichier du kit altéré" in output
    assert f"La version précédente ({previous}) reste installée avec ses raccourcis" in output
    assert not (tmp_path / "programmes/0.0.2-essai").exists() and len(list(menu.glob("*.lnk"))) == 4
