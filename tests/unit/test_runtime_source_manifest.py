import os
import shutil
import subprocess

import pytest

from services.runtime import source_manifest
from services.runtime.artifacts import ROOT


def _tree(root):
    for name in ("config/models.lock.json", "apps/web/next.config.mjs", "services/demo.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")


def _git(root, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@invalid", "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false", *args], env=env,
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="Git absent du poste")
def test_capture_records_head_and_dirty_flag(tmp_path):
    root = tmp_path / "dépôt"
    _tree(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    head = _git(root, "rev-parse", "HEAD")
    clean = source_manifest.capture(root)
    assert (clean["git_commit"], clean["git_dirty"], clean["git_status"]) == (head, False, "ok")
    paths = {item["path"] for item in clean["files"]}
    assert {"config/models.lock.json", "apps/web/next.config.mjs", "services/demo.py"} <= paths
    (root / "services/demo.py").write_text("{'modifié': 1}\n", encoding="utf-8")
    dirty = source_manifest.capture(root)
    assert dirty["git_commit"] == head and dirty["git_dirty"] is True
    assert dirty["source_fingerprint"] != clean["source_fingerprint"]


def test_capture_without_git_or_outside_repository_root(tmp_path, monkeypatch):
    root = tmp_path / "livraison"
    _tree(root)
    if shutil.which("git"):
        # Dépôt propre au test : le résultat ne dépend pas de l'emplacement du basetemp (dans ce dépôt ou sous %TEMP%).
        _git(root, "init", "-q")
        assert source_manifest.git_identity(root / "services")["git_status"] == "not_repository_root"
        outside = tmp_path / "hors-depot"
        outside.mkdir()
        # Recherche du dépôt bornée : le basetemp de pytest peut se trouver dans ce dépôt-ci.
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        # Git ne peut pas répondre : ce n'est pas la même situation qu'un sous-dossier du dépôt.
        assert source_manifest.git_identity(outside)["git_status"] == "git_error"
    monkeypatch.setattr(source_manifest.shutil, "which", lambda name: None)
    result = source_manifest.capture(root)
    assert (result["git_commit"], result["git_dirty"], result["git_status"]) == (None, None, "git_unavailable")


def test_delivered_files_list_matches_repository():
    assert "config/models.lock.json" in source_manifest.FILES
    assert "apps/web/next.config.ts" not in source_manifest.FILES
    assert (ROOT / "apps/web/next.config.mjs").is_file() and (ROOT / "config/models.lock.json").is_file()
