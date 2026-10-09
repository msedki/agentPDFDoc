"""Garde des essais unitaires : aucun essai n'écrit dans le compte réel de l'utilisateur.

Constat QA3-02, S3-05, U3-12 du 7 octobre 2026 : un aperçu de l'installateur, écrit hors du dépôt et lancé par pytest sans la
fixture `isolated_home` (autouse dans test_dist_linux_install seulement), a inscrit puis retiré une installation dans le
registre réel `~/.local/state/atelier-documentaire/installations.json` (05:26 UTC). L'isolement reste celui des modules
(HOME et XDG_* sous tmp_path, et refus du compte réel par `context`). S'y ajoutent, pour toute la suite tests/unit sous Linux :

- HOME et XDG_* (données, état, configuration, cache) de la session placés sous le dossier temporaire de pytest
  (`compte_isole`) : un essai, ou un processus enfant qu'il lance, qui oublierait l'isolement d'un module écrit dans ce
  compte isolé, jamais dans le compte réel (constat R3S-04) ;
- une garde qui fait échouer tout essai qui écrirait quand même sous le HOME réel, lu dans la base des comptes :
  - dans le processus de pytest, un crochet d'audit (sys.addaudithook, Python 3.12) refuse toute écriture sous le dossier
    personnel du compte (open en écriture, mkdir, rename, remove, rmdir, symlink, link, chmod, chown, utime, truncate,
    setxattr, removexattr, rmtree, copyfile, copymode, copystat, move, mkstemp, mkdtemp, sqlite3.connect), hors du dépôt
    et du dossier temporaire ; l'écriture n'a pas lieu (PermissionError) et l'essai échoue même si le code l'a rattrapée ;
  - pour les processus enfants, que le crochet ne voit pas, les fichiers de l'atelier dans le compte réel (registre, entrée
    de menu, commande, dossier par défaut) et les dossiers où l'installateur les crée (~/.local/state,
    ~/.local/share/applications, ~/.local/bin : une écriture passagère, créée puis retirée, y change la date du dossier) sont
    relevés avant et après chaque essai : tout changement le fait échouer. Un autre processus du compte (session de bureau,
    autre outil) peut en être l'auteur : le message le dit. ~/.local/share n'est pas relevé, car la session de bureau y
    réécrit recently-used.xbel ; son dossier de l'atelier l'est.

Le crochet n'est pas un bac à sable (la documentation de sys.addaudithook le dit) : il détecte les écritures accidentelles
des essais, comme celle du 7 octobre. Il n'est installé que sous Linux, plateforme de l'installateur, où un descripteur de
dossier (dir_fd) se résout par /proc/self/fd : la suite Windows reste inchangée (non exécutée ici).

Arguments des événements (constat QA4-01, CPython 3.12.14) : appelées sans dir_fd, les fonctions de `os` émettent
dir_fd = -1, et non None ; un chemin relatif se résout alors depuis le dossier courant, et depuis le dossier du descripteur
quand il est valide (0 ou plus). Un descripteur que /proc/self/fd ne connaît pas laisse l'opération échouer d'elle-même.
Limite : l'événement « open » ne porte pas le dir_fd de os.open ; un chemin relatif s'y résout depuis le dossier courant.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
# Fichiers et dossiers de l'atelier dans un compte (installateur Linux, emplacements XDG par défaut).
ATELIER_FILES = (".local/state/atelier-documentaire", ".local/state/atelier-documentaire/installations.json",
                 ".local/share/atelier-documentaire", ".local/share/applications/atelier-documentaire.desktop", ".local/bin/atelier")
# Dossiers où l'installateur crée ces fichiers : leur date change aussi quand un fichier y est créé puis retiré (R3S-04).
ATELIER_FOLDERS = (".local/state", ".local/share/applications", ".local/bin")
# Variables du compte isolé de la session, relatives à son dossier (XDG Base Directory 0.8 : valeurs par défaut).
ISOLATED_VARIABLES = {"HOME": "", "XDG_DATA_HOME": ".local/share", "XDG_STATE_HOME": ".local/state", "XDG_CONFIG_HOME": ".config",
                      "XDG_CACHE_HOME": ".cache"}
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
# Événements d'audit qui écrivent (Python 3.12, « Audit events table ») : pour chaque chemin écrit, rang de l'argument du
# chemin et rang de son descripteur de dossier (dir_fd, src_dir_fd, dst_dir_fd), ou None s'il n'y en a pas.
WRITE_EVENTS: dict[str, tuple[tuple[int, int | None], ...]] = {
    "os.mkdir": ((0, 2),), "os.rename": ((0, 2), (1, 3)), "os.remove": ((0, 1),), "os.rmdir": ((0, 1),), "os.symlink": ((1, 2),),
    "os.link": ((1, 3),), "os.chmod": ((0, 2),), "os.chown": ((0, 3),), "os.utime": ((0, 3),), "os.truncate": ((0, None),),
    "os.setxattr": ((0, None),), "os.removexattr": ((0, None),), "shutil.rmtree": ((0, 1),), "shutil.copyfile": ((1, None),),
    "shutil.copymode": ((1, None),), "shutil.copystat": ((1, None),), "shutil.move": ((0, None), (1, None)),
    "tempfile.mkstemp": ((0, None),), "tempfile.mkdtemp": ((0, None),), "sqlite3.connect": ((0, None),),
}


def account_home() -> Path:
    """Dossier personnel du compte, lu dans la base des comptes (POSIX) : il ne dépend pas du HOME qu'un essai a changé.
    Sous Windows, où la garde n'est pas installée, celui du profil."""
    if sys.platform == "win32":
        return Path(os.path.realpath(os.path.expanduser("~")))
    import pwd

    return Path(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))


class GardeDuCompte:
    """Double nommé de la garde : refuse et consigne les écritures sous `home`, hors des dossiers `allowed`."""

    def __init__(self, home: Path, *, allowed: tuple[Path, ...] = ()):
        self.home = Path(os.path.realpath(home))
        self.allowed = tuple(Path(os.path.realpath(path)) for path in allowed)
        self.violations: list[str] = []
        self.local = threading.local()

    def forbidden(self, path: Any, dir_fd: Any = None) -> str | None:
        if isinstance(path, int) or path is None:
            return None
        try:
            text = os.fsdecode(os.fspath(path))
        except TypeError:
            return None
        if text in ("", ":memory:") or text.startswith("file:"):
            return None
        # Sans dir_fd, CPython émet -1 : le chemin relatif part du dossier courant (os.path.abspath ci-dessous).
        if not os.path.isabs(text) and isinstance(dir_fd, int) and not isinstance(dir_fd, bool) and dir_fd >= 0:
            try:
                folder = os.readlink(f"/proc/self/fd/{dir_fd}")
            except OSError:
                return None  # descripteur inconnu : l'opération échoue d'elle-même (EBADF), la garde n'y ajoute rien
            text = os.path.join(folder, text)
        real = Path(os.path.realpath(os.path.abspath(text)))
        if not real.is_relative_to(self.home) or any(real.is_relative_to(folder) for folder in self.allowed):
            return None
        return str(real)

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event != "open" and event not in WRITE_EVENTS:
            return
        if getattr(self.local, "busy", False):
            return
        self.local.busy = True
        try:
            if event == "open":
                path, mode, flags = (tuple(args) + (None, None, None))[:3]
                writes = (isinstance(mode, str) and any(letter in mode for letter in "wax+")) or (
                    mode is None and isinstance(flags, int) and bool(flags & WRITE_FLAGS))
                targets = [self.forbidden(path)] if writes else []
            else:
                targets = [self.forbidden(args[index], args[fd] if fd is not None and fd < len(args) else None)
                           for index, fd in WRITE_EVENTS[event] if index < len(args)]
            touched = [target for target in targets if target]
            if touched:
                self.violations.append(f"{event} {', '.join(touched)}")
                raise PermissionError(f"Garde des essais : écriture sous le compte réel refusée ({event} {', '.join(touched)}) ; "
                                      "fixer HOME et XDG_* sous tmp_path (fixture isolated_home)")
        finally:
            self.local.busy = False

    def snapshot(self) -> dict[str, tuple[int, int, int] | None]:
        """Fichiers de l'atelier dans le compte et dossiers où l'installateur les crée : (inode, taille, date de modification en
        ns), ou None s'ils sont absents."""
        found: dict[str, tuple[int, int, int] | None] = {}
        for relative in (*ATELIER_FOLDERS, *ATELIER_FILES):
            try:
                info = (self.home / relative).lstat()
            except OSError:
                found[relative] = None
                continue
            found[relative] = (info.st_ino, info.st_size if not stat.S_ISDIR(info.st_mode) else 0, info.st_mtime_ns)
        return found

    def changes(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        return [f"{self.home / relative} modifié" for relative in (*ATELIER_FOLDERS, *ATELIER_FILES)
                if before.get(relative) != after.get(relative)]


def failure_text(violations: list[str], changes: list[str]) -> str:
    """Échec d'un essai : écritures refusées par le crochet (faites par cet essai), puis changements relevés dans le compte réel,
    dont l'auteur peut être l'essai ou un autre processus du compte (constat QA4-05)."""
    parts = []
    if violations:
        parts.append("Écriture sous le compte réel refusée pendant l'essai : " + " ; ".join(violations))
    if changes:
        parts.append("Fichiers de l'atelier du compte réel modifiés pendant l'essai (par lui ou par un autre processus) : "
                     + " ; ".join(changes))
    return " — ".join(parts)


# Linux seulement : /proc/self/fd, qui résout les descripteurs de dossier, est propre à Linux.
LINUX = sys.platform.startswith("linux")
GARDE = GardeDuCompte(account_home(), allowed=(REPOSITORY, Path(tempfile.gettempdir())))
if LINUX:
    sys.addaudithook(GARDE)


@pytest.fixture(scope="session", autouse=True)
def compte_isole(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path | None]:
    """HOME et XDG_* de toute la session sous le dossier temporaire de pytest (Linux seulement ; Windows inchangé). Les modules
    qui isolent déjà leurs essais (isolated_home) le font par-dessus ; le crochet d'audit et le relevé restent en place."""
    if not LINUX:
        yield None
        return
    home = tmp_path_factory.mktemp("compte-isole")
    with pytest.MonkeyPatch.context() as patch:
        for name, relative in ISOLATED_VARIABLES.items():
            patch.setenv(name, str(home / relative) if relative else str(home))
        yield home


@pytest.fixture
def garde_du_compte() -> GardeDuCompte:
    """La garde active de la session (crochet d'audit installé au chargement de ce fichier)."""
    return GARDE


@pytest.fixture(autouse=True)
def compte_reel_intact() -> Iterator[None]:
    """Échec de l'essai qui a écrit, ou tenté d'écrire, sous le HOME réel (crochet d'audit, processus enfants compris pour
    les fichiers de l'atelier). Sans effet hors de Linux."""
    if not LINUX:
        yield
        return
    before = GARDE.snapshot()
    start = len(GARDE.violations)
    yield
    violations, changes = GARDE.violations[start:], GARDE.changes(before, GARDE.snapshot())
    del GARDE.violations[start:]
    if violations or changes:
        pytest.fail(failure_text(violations, changes), pytrace=False)
