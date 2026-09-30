"""Enfants Windows créés suspendus, assignés au Job avant exécution."""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import cast

import psutil
import win32api
import win32con
import win32job
import win32process


class OwnedProcess:
    def __init__(self, handle, thread_handle, pid: int, executable: str, log_path: Path):
        self.handle, self.thread_handle = handle, thread_handle
        self.pid, self.executable, self.log_path = pid, executable, log_path
        self.created_at = psutil.Process(pid).create_time()

    def poll(self) -> int | None:
        code = win32process.GetExitCodeProcess(self.handle)
        return None if code == win32con.STILL_ACTIVE else code

    def wait(self, timeout: float = 30) -> int:
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Processus {self.pid} encore actif")
            time.sleep(0.1)
        # Le code de sortie d'un processus terminé est définitif : ce second appel ne rend plus None.
        return cast(int, self.poll())

    def identity(self) -> dict:
        return {"pid": self.pid, "created_at": self.created_at, "executable": self.executable,
                "log_path": str(self.log_path), "exit_code": self.poll()}

    def still_owned(self) -> bool:
        if self.poll() is not None:
            return False
        try:
            current = psutil.Process(self.pid)
            return abs(current.create_time() - self.created_at) < 0.01 and Path(current.exe()).resolve() == Path(self.executable).resolve()
        except psutil.Error:
            return False

    def close_handles(self) -> None:
        self.thread_handle.Close()
        self.handle.Close()


def enable_ctrl_c_inheritance() -> None:
    """Rétablit le traitement de CTRL+C du lanceur avant de créer un enfant.

    L'attribut « ignorer CTRL+C » est hérité par les processus enfants (Microsoft,
    SetConsoleCtrlHandler). Un lanceur qui l'a reçu de son terminal le transmettrait
    à Qdrant et Ollama, dont l'arrêt console échouerait jusqu'à la fermeture du Job.
    """
    if not ctypes.WinDLL("kernel32", use_last_error=True).SetConsoleCtrlHandler(None, False):
        raise ctypes.WinError(ctypes.get_last_error())


class WindowsJob:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Ce runtime exige Windows natif")
        self.handle = win32job.CreateJobObject(None, "Local\\agentragpdf-" + uuid.uuid4().hex)
        limits = win32job.QueryInformationJobObject(self.handle, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self.handle, win32job.JobObjectExtendedLimitInformation, limits)
        self.children: list[OwnedProcess] = []

    def launch(self, argv: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> OwnedProcess:
        import msvcrt

        executable = str(Path(argv[0]).resolve())
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab", buffering=0) as log, open(os.devnull, "rb") as null:
            output = msvcrt.get_osfhandle(log.fileno())
            input_handle = msvcrt.get_osfhandle(null.fileno())
            win32api.SetHandleInformation(output, win32con.HANDLE_FLAG_INHERIT, win32con.HANDLE_FLAG_INHERIT)
            win32api.SetHandleInformation(input_handle, win32con.HANDLE_FLAG_INHERIT, win32con.HANDLE_FLAG_INHERIT)
            enable_ctrl_c_inheritance()
            startup = win32process.STARTUPINFO()
            startup.dwFlags = win32con.STARTF_USESTDHANDLES | win32con.STARTF_USESHOWWINDOW
            startup.wShowWindow = win32con.SW_HIDE
            startup.hStdInput, startup.hStdOutput, startup.hStdError = input_handle, output, output
            handles = win32process.CreateProcess(
                executable, subprocess.list2cmdline(argv), None, None, True,
                win32con.CREATE_SUSPENDED | win32con.CREATE_NEW_CONSOLE,
                env, str(cwd), startup,
            )
        handle, thread, pid, _ = handles
        try:
            win32job.AssignProcessToJobObject(self.handle, handle)
            child = OwnedProcess(handle, thread, pid, executable, log_path)
            win32process.ResumeThread(thread)
        except BaseException:
            win32process.TerminateProcess(handle, 1)
            handle.Close()
            thread.Close()
            raise
        self.children.append(child)
        return child

    def close(self) -> None:
        if self.handle is not None:
            self.handle.Close()
            self.handle = None
        for child in self.children:
            child.close_handles()
        self.children.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
