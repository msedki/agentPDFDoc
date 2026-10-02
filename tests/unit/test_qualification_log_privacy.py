"""Exclusions Git du contrôle D08.7 quand `.runtime` est un lien vers un autre volume (poste Linux, W018).

Dépôts Git réels et temporaires ; `.runtime` y est un lien symbolique vers un dossier extérieur au dépôt, comme sur le
poste Linux où les données sont déportées sur la carte microSD. Aucune instance n'est lue.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import log_privacy_check  # noqa: E402

PRIVATE = ".runtime/data/app.sqlite3"


def repository(tmp_path: Path, ignore: str) -> Path:
    """Dépôt dont `.runtime` est un lien vers `extérieur/runtime`, avec les sous-dossiers réels du poste."""
    outside = tmp_path / "extérieur" / "runtime"
    for folder in ("data/originals", "data/logs/x", "models/e5"):
        (outside / folder).mkdir(parents=True)
    (outside / "data" / "app.sqlite3").write_bytes(b"base privee")
    repo = tmp_path / "depot"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    try:
        os.symlink(outside, repo / ".runtime", target_is_directory=True)
    except OSError as error:  # Windows sans droit de créer un lien : le cas n'existe pas sur ce poste
        pytest.skip(f"lien symbolique impossible ici : {error}")
    (repo / ".gitignore").write_text(ignore, encoding="utf-8")
    return repo


def check_ignore_code(repo: Path, path: str) -> int:
    return subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=repo, capture_output=True, check=False).returncode


def test_path_beyond_an_ignored_link_is_excluded_through_the_link(tmp_path):
    repo = repository(tmp_path, "/.runtime\nPDF/\n")
    # Comportement de Git constaté (2.25 sur ce poste) : refus au-delà du lien, verdict possible sur le lien lui-même.
    assert check_ignore_code(repo, PRIVATE) == 128
    assert check_ignore_code(repo, ".runtime") == 0
    for path in log_privacy_check.PRIVATE_PATHS:
        expected = ".runtime" if path.startswith(".runtime/") else path
        assert log_privacy_check.git_exclusion(path, repo) == expected, path
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout == "?? .gitignore\n"


def test_link_left_unignored_still_fails_the_check(tmp_path):
    # `.runtime/` ne désigne qu'un dossier : Git voit le lien comme un fichier, qui serait versionné.
    repo = repository(tmp_path, ".runtime/\nPDF/\n")
    assert check_ignore_code(repo, ".runtime") == 1
    assert "?? .runtime\n" in subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert log_privacy_check.git_exclusion(PRIVATE, repo) is None
    assert log_privacy_check.git_exclusion("PDF/exemple.pdf", repo) == "PDF/exemple.pdf"
    (repo / ".gitignore").write_text("", encoding="utf-8")
    assert all(log_privacy_check.git_exclusion(path, repo) is None for path in log_privacy_check.PRIVATE_PATHS)


def test_unignored_link_below_an_ignored_folder_and_plain_paths_keep_git_verdict(tmp_path):
    repo = repository(tmp_path, "/.runtime\nstockage/\n")
    # Lien non ignoré placé dans un dossier réel ignoré : l'exclusion du dossier parent le couvre.
    (repo / "stockage").mkdir()
    os.symlink(tmp_path / "extérieur", repo / "stockage" / "volume", target_is_directory=True)
    assert check_ignore_code(repo, "stockage/volume/runtime/data/app.sqlite3") == 128
    assert log_privacy_check.git_exclusion("stockage/volume/runtime/data/app.sqlite3", repo) == "stockage/volume"
    # Lien non ignoré hors de tout dossier ignoré : un motif de fichier ne suffit pas, Git versionnerait le lien.
    (repo / ".gitignore").write_text("/.runtime\n*.sqlite3\n", encoding="utf-8")
    os.symlink(tmp_path / "extérieur", repo / "volume", target_is_directory=True)
    assert log_privacy_check.git_exclusion("volume/runtime/data/app.sqlite3", repo) is None
    # Chemin ordinaire : verdict de Git inchangé.
    assert log_privacy_check.git_exclusion("notes/app.sqlite3", repo) == "notes/app.sqlite3"
    assert log_privacy_check.git_exclusion("notes/lisezmoi.txt", repo) is None


def test_a_link_tracked_by_force_fails_the_tracked_paths_check(tmp_path):
    """Revue J8 : `/.runtime` ignore le lien, mais `git add -f` le versionne ; le contrôle doit le voir."""
    repo = repository(tmp_path, "/.runtime\nPDF/\n")
    subprocess.run(["git", "add", "-f", ".runtime"], cwd=repo, check=True)
    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout.splitlines()
    assert ".runtime" in tracked
    exclusions = {path: log_privacy_check.git_exclusion(path, repo) for path in log_privacy_check.PRIVATE_PATHS}
    assert log_privacy_check.tracked_private_paths(tracked, exclusions) == [".runtime"]
    assert log_privacy_check.tracked_private_paths(["README.md", "PDF/a.pdf", ".runtime/x"], exclusions) == ["PDF/a.pdf", ".runtime/x"]
