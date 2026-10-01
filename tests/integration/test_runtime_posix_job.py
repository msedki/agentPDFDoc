"""Supervision POSIX (W018) sur de vrais processus : groupe propre, mort liée au superviseur, SIGINT, fermeture.

Chaque test ne signale que des processus qu'il a créés (identités relevées par PID et date de création) ; aucun arrêt
par nom. Les racines sont des dossiers temporaires du test.
"""

import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import psutil
import pytest

if sys.platform == "win32":
    pytest.skip("Supervision POSIX ; le Job Object Windows est couvert par test_runtime_windows_job.py", allow_module_level=True)

from services.runtime.artifacts import ROOT  # noqa: E402
from services.runtime.posix_process import PosixJob, group_members  # noqa: E402
from services.runtime.supervisor import (  # noqa: E402
    cooperative_stop_mode,
    posix_environment,
    send_owned_console_interrupt,
)

pytestmark = pytest.mark.integration

# Enfant type Ollama : lance un « runner » dans son groupe, un second qui quitte le groupe (setsid), publie leurs PID,
# relaie SIGTERM à ses runners puis sort ; SIGINT le fait sortir avec le code 0.
CHILD = textwrap.dedent("""
    import json, os, signal, subprocess, sys, time
    from pathlib import Path
    sleeper = [sys.executable, "-c", "import time; time.sleep(120)"]
    runner = subprocess.Popen(sleeper)
    escaped = subprocess.Popen(sleeper, start_new_session=True) if "--escaped" in sys.argv else None
    def stop(signum, frame):
        for process in (runner, escaped):
            if process is not None:
                process.terminate()
        sys.exit(0 if signum == signal.SIGINT else 15)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    Path(sys.argv[1]).write_text(json.dumps({"runner": runner.pid, "escaped": escaped.pid if escaped else None,
                                             "home": os.environ.get("HOME"), "env": sorted(os.environ),
                                             "path": os.environ.get("PATH"), "cwd": os.getcwd(),
                                             "executable": sys.executable, "prefix": sys.prefix,
                                             "base_prefix": sys.base_prefix}))
    time.sleep(120)
""")


def wait_for(predicate, timeout=15.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def alive(pid: int, created: float) -> bool:
    try:
        process = psutil.Process(pid)
        return abs(process.create_time() - created) < 0.01 and process.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def identity(pid: int) -> tuple[int, float]:
    return pid, psutil.Process(pid).create_time()


def published(path: Path) -> dict:
    assert wait_for(path.exists), "l'enfant n'a pas publié ses PID"
    return json.loads(path.read_text(encoding="utf-8"))


def launch_child(job: PosixJob, tmp_path: Path, *extra: str):
    marker = tmp_path / "child.json"
    code = tmp_path / "child.py"
    code.write_text(CHILD, encoding="utf-8")
    env = {**posix_environment(tmp_path / "data"), "PYTHONUNBUFFERED": "1"}
    child = job.launch([sys.executable, str(code), str(marker), *extra], cwd=tmp_path, env=env,
                       log_path=tmp_path / "logs" / "child.log")
    return child, published(marker)


def test_launch_owns_a_new_group_with_the_target_identity_and_a_clean_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/local/cuda/lib64:")
    with PosixJob() as job:
        child, info = launch_child(job, tmp_path)
        record = child.identity()
        assert record["pid"] == child.pid == record["process_group"] == os.getpgid(child.pid) == os.getsid(child.pid)
        assert os.getpgid(child.pid) != os.getpgrp()
        # Programme exécuté par son chemin donné (lien du venv conservé) ; l'identité enregistrée est le chemin résolu,
        # relevé après l'exec de setpriv : le programme lancé, pas setpriv.
        assert psutil.Process(child.pid).cmdline()[0] == sys.executable == info["executable"]
        assert info["prefix"] == sys.prefix and info["prefix"] != info["base_prefix"]
        assert record["executable"] == str(Path(sys.executable).resolve()) == str(Path(psutil.Process(child.pid).exe()).resolve())
        assert child.still_owned() and record["exit_code"] is None
        assert os.getpgid(info["runner"]) == child.pgid
        assert info["home"] == str(tmp_path / "data" / "home") and "LD_LIBRARY_PATH" not in info["env"]
        assert info["cwd"] == str(tmp_path) and "cuda" not in info["path"]
        with open(f"/proc/{child.pid}/fd/0", "rb") as stdin:
            assert stdin.read() == b""


def test_the_project_interpreter_keeps_its_virtual_environment_under_the_job(tmp_path):
    # Défaut R1 : argv[0] résolu avant l'exec (lien .venv/bin/python suivi) ; l'interpréteur ne trouvait plus pyvenv.cfg
    # et l'API perdait ses dépendances (ModuleNotFoundError: fastapi). Même commande que le lancement de l'API.
    with PosixJob() as job:
        child = job.launch([sys.executable, "-c", "import sys, fastapi; assert sys.prefix != sys.base_prefix"],
                           cwd=tmp_path, env=posix_environment(tmp_path / "data"), log_path=tmp_path / "child.log")
        assert child.wait(60) == 0, (tmp_path / "child.log").read_text(encoding="utf-8", errors="replace")


def test_child_and_its_runner_stop_when_the_supervisor_is_killed(tmp_path):
    # Superviseur réel dans sa propre session ; SIGKILL ne lui laisse aucun nettoyage : seul PR_SET_PDEATHSIG agit.
    state = tmp_path / "supervisor.json"
    script = tmp_path / "supervisor.py"
    script.write_text(textwrap.dedent(f"""
        import json, sys, time
        from pathlib import Path
        sys.path.insert(0, {str(ROOT)!r})
        from services.runtime.posix_process import PosixJob
        from services.runtime.supervisor import posix_environment
        root = Path({str(tmp_path)!r})
        job = PosixJob()
        child = job.launch([sys.executable, str(root / "child.py"), str(root / "child.json")], cwd=root,
                           env=posix_environment(root / "data"), log_path=root / "child.log")
        Path({str(state)!r}).write_text(json.dumps(child.identity()))
        time.sleep(120)
    """), encoding="utf-8")
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    supervisor = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path, start_new_session=True,
                                  stdout=subprocess.DEVNULL, stderr=(tmp_path / "supervisor.log").open("wb"))
    try:
        assert wait_for(state.exists), (tmp_path / "supervisor.log").read_text(errors="replace")
        child = json.loads(state.read_text(encoding="utf-8"))
        runner = published(tmp_path / "child.json")["runner"]
        child_id, runner_id = identity(child["pid"]), identity(runner)
        supervisor.send_signal(signal.SIGKILL)
        assert supervisor.wait(10) == -signal.SIGKILL
        assert wait_for(lambda: not alive(*child_id) and not alive(*runner_id)), "enfant ou runner survivant"
        assert group_members(child["process_group"]) == []
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(10)


def test_runner_of_a_child_that_does_not_relay_sigterm_is_left_in_the_group_and_detectable(tmp_path):
    # Limite documentée : PR_SET_PDEATHSIG n'est pas hérité au fork. Un enfant qui meurt de SIGTERM sans arrêter son
    # runner laisse celui-ci dans le groupe ; group_members le retrouve (détection au up suivant).
    code = tmp_path / "plain.py"
    code.write_text(textwrap.dedent("""
        import subprocess, sys, time
        from pathlib import Path
        runner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        Path(sys.argv[1]).write_text(str(runner.pid))
        time.sleep(120)
    """), encoding="utf-8")
    script = tmp_path / "supervisor.py"
    script.write_text(textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {str(ROOT)!r})
        from services.runtime.posix_process import PosixJob
        from services.runtime.supervisor import posix_environment
        root = Path({str(tmp_path)!r})
        job = PosixJob()
        child = job.launch([sys.executable, str(root / "plain.py"), str(root / "runner.pid")], cwd=root,
                           env=posix_environment(root / "data"), log_path=root / "child.log")
        Path(root / "child.pid").write_text(str(child.pid))
        time.sleep(120)
    """), encoding="utf-8")
    supervisor = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path, start_new_session=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    runner_id = None
    try:
        assert wait_for(lambda: (tmp_path / "runner.pid").exists() and (tmp_path / "child.pid").exists())
        child_pid, runner_pid = int((tmp_path / "child.pid").read_text()), int((tmp_path / "runner.pid").read_text())
        child_id, runner_id = identity(child_pid), identity(runner_pid)
        supervisor.kill()
        supervisor.wait(10)
        assert wait_for(lambda: not alive(*child_id))
        assert alive(*runner_id) and group_members(child_pid) == [runner_pid]
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(10)
        # Seul le runner créé par ce test est arrêté, après revalidation de son identité.
        if runner_id and alive(*runner_id):
            psutil.Process(runner_id[0]).kill()
            assert wait_for(lambda: not alive(*runner_id))


def test_close_kills_the_group_and_escaped_descendants_but_spares_a_foreign_process(tmp_path):
    foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    try:
        foreign_id = identity(foreign.pid)
        job = PosixJob()
        child, info = launch_child(job, tmp_path, "--escaped")
        tracked = [identity(child.pid), identity(info["runner"]), identity(info["escaped"])]
        assert os.getpgid(info["escaped"]) != child.pgid
        job.close()
        assert child.reaped and not psutil.pid_exists(child.pid)
        assert wait_for(lambda: not any(alive(*item) for item in tracked)), "descendant survivant après fermeture"
        assert group_members(child.pgid) == []
        assert alive(*foreign_id) and foreign.poll() is None
        assert child.poll() == -signal.SIGKILL
    finally:
        foreign.kill()
        foreign.wait(10)


def test_sigint_reaches_the_group_and_exit_is_observed_without_reaping_the_leader(tmp_path):
    with PosixJob() as job:
        child, info = launch_child(job, tmp_path)
        runner_id = identity(info["runner"])
        assert send_owned_console_interrupt(child)
        assert child.wait(10) == 0
        # Leader zombie, non récolté : son PID réserve le numéro du groupe jusqu'à la fermeture du Job.
        assert open(f"/proc/{child.pid}/stat").read().rsplit(")", 1)[1].split()[0] == "Z"
        assert not child.still_owned() and child.identity()["exit_code"] == 0
        assert send_owned_console_interrupt(child)  # déjà sorti : rien n'est envoyé, l'arrêt est acquis
        assert wait_for(lambda: not alive(*runner_id))
    assert child.reaped and not psutil.pid_exists(child.pid)


def test_launch_is_refused_outside_the_main_thread_and_a_missing_program_leaves_nothing(tmp_path):
    job = PosixJob()
    errors: list[BaseException] = []

    def attempt():
        try:
            job.launch([sys.executable, "-c", "pass"], cwd=tmp_path, env=posix_environment(tmp_path), log_path=tmp_path / "t.log")
        except RuntimeError as exc:
            errors.append(exc)

    worker = threading.Thread(target=attempt)
    worker.start()
    worker.join(30)
    assert errors and "thread principal" in str(errors[0]) and job.children == []
    with pytest.raises(RuntimeError, match="terminé"):
        job.launch([str(tmp_path / "absent")], cwd=tmp_path, env=posix_environment(tmp_path), log_path=tmp_path / "absent.log")
    assert job.children == []
    job.close()


# Enfant qui consigne le signal d'arrêt reçu puis sort avec le code 0.
SIGNAL_RECORDER = textwrap.dedent("""
    import signal, sys, time
    from pathlib import Path
    def stop(signum, frame):
        Path(sys.argv[1]).write_text(signal.Signals(signum).name)
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    Path(sys.argv[1] + ".pret").write_text("")
    time.sleep(60)
""")


@pytest.mark.parametrize(("service", "expected"), [("qdrant", "SIGTERM"), ("ollama", "SIGTERM"), (None, "SIGINT")])
def test_cooperative_stop_sends_the_signal_chosen_for_each_service(tmp_path, service, expected):
    # Qdrant 1.19.1 : SIGTERM donne l'arrêt « graceful », SIGINT l'arrêt « forced » (constat R1 du 01/10). Ollama 0.35.0
    # traite les deux signaux de la même façon ; SIGTERM est retenu (essais réels, modèle chargé, du 01/10).
    marker = tmp_path / "signal.txt"
    with PosixJob() as job:
        child = job.launch([sys.executable, "-c", SIGNAL_RECORDER, str(marker)], cwd=tmp_path,
                           env=posix_environment(tmp_path / "data"), log_path=tmp_path / "child.log")
        assert wait_for((tmp_path / "signal.txt.pret").exists)
        assert send_owned_console_interrupt(child, service)
        assert child.wait(10) == 0
    assert marker.read_text() == expected
    assert cooperative_stop_mode(service) == "group_" + expected.lower()
