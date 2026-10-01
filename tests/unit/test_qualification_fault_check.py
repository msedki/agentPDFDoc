"""Arrêt forcé de l'outil de fautes injectées (D03.5) : arbre de l'instance seulement, sans sortie propre.

Processus réels créés par le test ; seul l'arbre visé est arrêté, un processus étranger reste vivant.
"""

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import fault_check  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="branche Linux ; Windows garde taskkill /F /T")

# Parent type superviseur : un enfant qui consignerait un arrêt propre (SIGTERM) ; le parent publie le PID de l'enfant.
TREE = textwrap.dedent("""
    import signal, subprocess, sys, time
    from pathlib import Path
    child = subprocess.Popen([sys.executable, "-c",
        "import signal, sys, time\\nfrom pathlib import Path\\n"
        "signal.signal(signal.SIGTERM, lambda *_: (Path(sys.argv[1]).write_text('propre'), sys.exit(0)))\\n"
        "time.sleep(120)", sys.argv[1] + ".arret"])
    Path(sys.argv[1]).write_text(str(child.pid))
    time.sleep(120)
""")


def test_kill_tree_stops_the_whole_tree_without_a_clean_exit_and_spares_other_processes(tmp_path):
    marker = tmp_path / "enfant.pid"
    foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    root = subprocess.Popen([sys.executable, "-c", TREE, str(marker)], start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        child = psutil.Process(int(marker.read_text()))
        fault_check.kill_tree(root.pid)
        assert root.wait(10) == -9
        child.wait(10)
        assert not child.is_running()
        # Aucun arrêt propre : l'enfant n'a pas pu traiter de SIGTERM avant SIGKILL.
        assert not (tmp_path / "enfant.pid.arret").exists()
        assert foreign.poll() is None
    finally:
        for process in (root, foreign):
            if process.poll() is None:
                process.kill()
                process.wait(10)
