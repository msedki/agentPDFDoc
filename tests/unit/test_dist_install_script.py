"""install.ps1 sur un kit factice altéré : arrêt avant toute installation et message accentué relayé intact.

Le Python du kit est le CPython du dépôt, relié par une jonction (aucun droit administrateur requis). L'essai du 01/10
a montré que PowerShell 5.1 lit sinon la sortie UTF-8 de Python selon la page OEM de la console (« é » devient « ├® »).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
KIT_PYTHON = Path(".runtime/python/cpython-3.12.14-windows-x86_64-none")

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 vise Windows PowerShell 5.1"),
    pytest.mark.skipif(not (ROOT / KIT_PYTHON / "python.exe").is_file(), reason="CPython du runtime non provisionné"),
    pytest.mark.skipif(psutil.virtual_memory().total < 15 * 1024**3, reason="prérequis mémoire d'install.ps1 non remplis par ce poste"),
]


def test_altered_kit_file_stops_the_installation_with_an_intact_french_message(tmp_path):
    kit = tmp_path / "kit"
    (kit / "tools/dist").mkdir(parents=True)
    for name in ("install.ps1", "build_kit.py", "notices.py"):
        (kit / "tools/dist" / name).write_bytes((ROOT / "tools/dist" / name).read_bytes())
    (kit / KIT_PYTHON.parent).mkdir(parents=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(kit / KIT_PYTHON), str(ROOT / KIT_PYTHON)], check=True, capture_output=True)
    (kit / "lisez-moi.txt").write_bytes(b"contenu altere")
    (kit / "SHA256SUMS").write_text("0" * 64 + "  lisez-moi.txt\n", encoding="utf-8")
    (kit / "kit-manifest.json").write_text(json.dumps({"version": "0.0.0-essai", "bytes": 1}), encoding="utf-8")
    programs, data = tmp_path / "programmes", tmp_path / "donnees"
    try:
        run = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(kit / "tools/dist/install.ps1"),
                              "-Destination", str(programs), "-DataRoot", str(data), "-NoStart"],
                             capture_output=True, timeout=120, env={k: v for k, v in os.environ.items() if k != "PYTHONUTF8"})
    finally:
        os.rmdir(kit / KIT_PYTHON)  # retire la jonction seule, jamais le CPython du dépôt
    output = run.stdout.decode("utf-8")
    assert run.returncode == 1, output
    assert "Installation arrêtée : Fichier du kit altéré : lisez-moi.txt (empreinte différente) Recopiez le kit ; rien n'a été installé." in output
    assert "├" not in output and "�" not in output
    assert not (programs / "0.0.0-essai").exists()
    [report] = data.glob("install-*.json")
    saved = json.loads(report.read_text(encoding="utf-8-sig"))
    assert saved["status"] == "failed" and saved["error"].startswith("Fichier du kit altéré : lisez-moi.txt")
