import json
import os
import sys
import time
from pathlib import Path

import psutil
import pytest

from services.runtime.windows_process import WindowsJob


@pytest.mark.integration
def test_job_close_terminates_only_owned_descendants(tmp_path):
    marker = tmp_path / "child.json"
    code = ("import subprocess,sys,time,json;from pathlib import Path;"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']);"
            f"Path({str(marker)!r}).write_text(json.dumps({{'pid':p.pid}}));time.sleep(120)")
    owner = psutil.Process(os.getpid())
    owner_created = owner.create_time()
    job = WindowsJob()
    child = job.launch([sys.executable, "-c", code], cwd=Path.cwd(), env=os.environ.copy(),
                       log_path=tmp_path / "owned.log")
    identity = child.identity()
    deadline = time.monotonic() + 15
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    try:
        assert marker.exists(), (tmp_path / "owned.log").read_text(errors="replace")
        descendant = json.loads(marker.read_text())["pid"]
        assert psutil.pid_exists(descendant)
    finally:
        job.close()
    deadline = time.monotonic() + 10
    while any(psutil.pid_exists(pid) for pid in [identity["pid"], descendant]) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(identity["pid"])
    assert not psutil.pid_exists(descendant)
    assert owner.create_time() == owner_created


@pytest.mark.integration
def test_console_interrupt_reaches_child_of_a_launcher_that_ignored_ctrl_c(tmp_path):
    import ctypes

    from services.runtime.supervisor import send_owned_console_interrupt

    # Lanceur démarré avec CTRL+C ignoré (terminal d'outil) : l'enfant ne doit pas hériter de cet attribut.
    assert ctypes.WinDLL("kernel32").SetConsoleCtrlHandler(None, True)
    marker = tmp_path / "ready"
    code = ("import sys,time;from pathlib import Path\n"
            "try:\n"
            f"    Path({str(marker)!r}).write_text('ready');time.sleep(60);sys.exit(3)\n"
            "except KeyboardInterrupt:\n"
            "    sys.exit(0)\n")
    with WindowsJob() as job:
        child = job.launch([sys.executable, "-c", code], cwd=Path.cwd(), env=os.environ.copy(),
                           log_path=tmp_path / "owned.log")
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert marker.exists(), (tmp_path / "owned.log").read_text(errors="replace")
        assert send_owned_console_interrupt(child)
        assert child.wait(10) == 0
