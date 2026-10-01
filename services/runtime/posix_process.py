"""Enfants POSIX possédés par le superviseur : équivalent Linux de `windows_process` (W018).

Chaque enfant est lancé sans shell, dans sa propre session et son propre groupe de processus (`setsid`), avec un
répertoire courant explicite, stdin sur /dev/null et sa sortie dans son journal. `setpriv --pdeathsig TERM` (util-linux)
règle PR_SET_PDEATHSIG avant d'exécuter le programme : si le superviseur meurt, même par SIGKILL, l'enfant reçoit
SIGTERM. Ce réglage suit le thread créateur et n'est pas hérité au `fork` : le lancement se fait donc depuis le thread
principal. À la mort du superviseur, seul l'enfant reçoit le signal et arrête lui-même ses descendants (Ollama arrête
ses runners sur SIGTERM) ; un descendant resté dans le groupe est signalé au `up` suivant (`orphan_processes`). À la
fermeture du Job, les descendants sont arrêtés avec leur groupe.

Le leader de chaque groupe n'est récolté qu'à la fermeture : un zombie garde son PID, donc le numéro du groupe ne peut
pas être réattribué, et `killpg` ne vise jamais un groupe étranger. L'état de sortie est observé sans récolte
(`waitid` avec WNOWAIT). La fermeture (`close`) tient lieu du kill-on-close du Job Object Windows : SIGKILL au groupe et
aux descendants encore rattachés, puis récolte du leader.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

import psutil

# Module POSIX seulement : mypy ignore la suite sous --platform win32, et l'importer sous Windows est une erreur.
assert sys.platform != "win32", "posix_process exige un système POSIX ; windows_process s'applique sous Windows"

# Chemin système fixe : le PATH hérité de l'utilisateur ne choisit pas l'outil qui règle la mort liée au parent.
SETPRIV_SEARCH_PATH = "/usr/bin:/bin"
PARENT_DEATH_SIGNAL = "TERM"
EXEC_TIMEOUT_SECONDS = 10.0
REAP_TIMEOUT_SECONDS = 10.0


def setpriv_executable() -> str:
    found = shutil.which("setpriv", path=SETPRIV_SEARCH_PATH)
    if not found:
        raise RuntimeError("setpriv (util-linux 2.33 ou plus récent) introuvable dans /usr/bin ou /bin : "
                           "l'arrêt des enfants à la mort du superviseur ne peut pas être garanti")
    return found


def group_members(pgid: int) -> list[int]:
    """PID vivants (hors zombies) du groupe `pgid`, relevés dans /proc."""
    members = []
    with os.scandir("/proc") as entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                with open(f"/proc/{entry.name}/stat", "rb") as stream:
                    fields = stream.read().rsplit(b")", 1)[1].split()
            except (OSError, IndexError):
                continue
            # Après le nom entre parenthèses : état, PPID, groupe de processus.
            if len(fields) > 2 and int(fields[2]) == pgid and fields[0] not in {b"Z", b"X"}:
                members.append(int(entry.name))
    return sorted(members)


def initial_environment(pid: int) -> dict[str, str]:
    """Environnement reçu par le processus `pid` à son exec (/proc/<pid>/environ).

    Lisible seulement pour les processus du même compte : OSError (PermissionError, ProcessLookupError) sinon.
    """
    with open(f"/proc/{pid}/environ", "rb") as stream:
        raw = stream.read()
    environment = {}
    for item in raw.split(b"\0"):
        key, separator, value = item.partition(b"=")
        if separator:
            environment[os.fsdecode(key)] = os.fsdecode(value)
    return environment


def _exit_code(info: os.waitid_result) -> int:
    # Même convention que subprocess : code de sortie, ou opposé du numéro du signal fatal.
    return info.si_status if info.si_code == os.CLD_EXITED else -info.si_status


class OwnedProcess:
    def __init__(self, popen: subprocess.Popen, executable: str, log_path: Path):
        self._popen = popen
        self.pid = popen.pid
        # start_new_session : l'enfant dirige sa session et son groupe, dont l'identifiant est son PID.
        self.pgid = popen.pid
        self.executable, self.log_path = executable, log_path
        self.created_at = psutil.Process(self.pid).create_time()
        self._exit: int | None = None
        self.reaped = False

    def poll(self) -> int | None:
        if self._exit is not None:
            return self._exit
        try:
            info = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            # Récolté ailleurs (ne devrait pas arriver) : le code connu de Popen fait foi.
            self._exit = self._popen.returncode
            return self._exit
        if info is None:
            return None
        self._exit = _exit_code(info)
        return self._exit

    def wait(self, timeout: float = 30) -> int:
        deadline = time.monotonic() + timeout
        while (code := self.poll()) is None:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Processus {self.pid} encore actif")
            time.sleep(0.1)
        return code

    def identity(self) -> dict:
        return {"pid": self.pid, "created_at": self.created_at, "executable": self.executable,
                "log_path": str(self.log_path), "exit_code": self.poll(), "process_group": self.pgid}

    def still_owned(self) -> bool:
        if self.poll() is not None:
            return False
        try:
            current = psutil.Process(self.pid)
            return abs(current.create_time() - self.created_at) < 0.01 and Path(current.exe()).resolve() == Path(self.executable).resolve()
        except psutil.Error:
            return False

    def signal_group(self, signum: int) -> bool:
        """Signal au groupe ; sûr tant que le leader n'est pas récolté (son PID réserve le numéro du groupe)."""
        if self.reaped:
            return False
        try:
            os.killpg(self.pgid, signum)
            return True
        except ProcessLookupError:
            return False

    def interrupt(self, signum: int = signal.SIGINT) -> bool:
        """Arrêt coopératif : `signum` au groupe (SIGINT par défaut, comme le CTRL+C de la console dédiée sous Windows ;
        le superviseur choisit le signal de chaque service).

        Vrai si le signal est parti ou si l'enfant était déjà sorti ; faux si son identité n'est plus la sienne.
        """
        if not self.still_owned():
            return self.poll() is not None
        return self.signal_group(signum)

    def _await_exec(self, timeout: float) -> None:
        # setpriv exécute le programme après avoir réglé PR_SET_PDEATHSIG : l'identité n'est valable qu'ensuite.
        deadline = time.monotonic() + timeout
        target = Path(self.executable).resolve()
        while True:
            code = self.poll()
            if code is not None:
                raise RuntimeError(f"Enfant terminé ({code}) au lancement ; log {self.log_path}")
            try:
                if Path(psutil.Process(self.pid).exe()).resolve() == target:
                    return
            except psutil.Error:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Programme {target} non exécuté par le processus {self.pid} en {timeout:.0f} s")
            time.sleep(0.01)

    def kill_group(self) -> list[int]:
        """SIGKILL au groupe et aux descendants encore rattachés, puis récolte du leader ; rend les PID visés."""
        if self.reaped:
            return []
        descendants: list[psutil.Process] = []
        with suppress(psutil.Error):
            # Relevé avant SIGKILL : un descendant sorti du groupe (setsid) reste rattaché par sa filiation.
            descendants = psutil.Process(self.pid).children(recursive=True)
        targeted = group_members(self.pgid)
        self.signal_group(signal.SIGKILL)
        for process in descendants:
            # psutil revérifie la date de création avant d'envoyer le signal : pas de PID réattribué visé.
            with suppress(psutil.Error):
                process.kill()
                targeted.append(process.pid)
        try:
            self._popen.wait(timeout=REAP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return sorted(set(targeted))
        if self._exit is None:
            self._exit = self._popen.returncode
        self.reaped = True
        return sorted(set(targeted))


class PosixJob:
    """Ensemble des enfants d'un superviseur ; `close` arrête ce qui reste, comme la fermeture d'un Job Object."""

    def __init__(self):
        self.setpriv = setpriv_executable()
        self.children: list[OwnedProcess] = []

    def launch(self, argv: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> OwnedProcess:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("PR_SET_PDEATHSIG suit le thread créateur : lancer les enfants depuis le thread principal")
        # Le programme est exécuté par son chemin donné, sans résoudre ses liens : `.venv/bin/python` est un lien vers
        # l'interpréteur géré par uv, et lancé par sa cible, Python ne trouverait plus `pyvenv.cfg` (dépendances du venv
        # perdues). Seule l'identité (psutil.exe(), toujours résolu) emploie le chemin résolu.
        program = str(Path(argv[0]).absolute())
        executable = str(Path(program).resolve())
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab", buffering=0) as log:
            popen = subprocess.Popen([self.setpriv, "--pdeathsig", PARENT_DEATH_SIGNAL, "--", program, *argv[1:]],
                                     cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, close_fds=True, start_new_session=True)
        try:
            child = OwnedProcess(popen, executable, log_path)
        except BaseException:
            os.killpg(popen.pid, signal.SIGKILL)
            popen.wait()
            raise
        self.children.append(child)
        try:
            child._await_exec(EXEC_TIMEOUT_SECONDS)
        except BaseException:
            self.children.remove(child)
            child.kill_group()
            raise
        return child

    def close(self) -> None:
        for child in self.children:
            child.kill_group()
        self.children.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
