"""SIGINT vers la console dédiée d'un enfant possédé (helper isolé)."""

import ctypes
import sys
import time

# Module Windows seulement : mypy ignore la suite hors --platform win32, et l'importer ailleurs est une erreur.
assert sys.platform == "win32", "console_signal exige Windows"


def signal_console(pid: int) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.FreeConsole()
    if not kernel.AttachConsole(pid):
        raise ctypes.WinError(ctypes.get_last_error())
    # Le helper ignore le signal qu'il diffuse dans cette console dédiée.
    if not kernel.SetConsoleCtrlHandler(None, True):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GenerateConsoleCtrlEvent(0, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(0.25)
    kernel.FreeConsole()


if __name__ == "__main__":
    signal_console(int(sys.argv[1]))
