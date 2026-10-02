"""Profil de base des instances isolées de recette (`e2e_instance.py`, `restore_question_check.py prepare`).

Aucun service n'est démarré : `start`, `status`, la sauvegarde et l'API sont des doubles explicites. Le profil de
l'instance isolée est en revanche produit par le vrai `control_profile`, dans une racine temporaire.
"""

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "qualification"))
import e2e_instance  # noqa: E402
import restore_question_check  # noqa: E402

from services.runtime.artifacts import runtime_location  # noqa: E402
from services.runtime.supervisor import load_profile  # noqa: E402

DELIVERED = ROOT / "config/local16.yaml"


def cpu_profile(folder: Path) -> Path:
    """Copie du profil livré qui impose le calcul CPU (recette D07), seule différence avec lui."""
    text = DELIVERED.read_text(encoding="utf-8")
    assert text.count("  accelerator: auto\n") == 1
    target = folder / "local16-cpu.yaml"
    target.write_text(text.replace("  accelerator: auto\n", "  accelerator: cpu\n"), encoding="utf-8")
    return target


def isolated_root(folder: Path, monkeypatch, module) -> Path:
    root = folder / "racine"
    root.mkdir()
    calls = []

    def short_root(*prefix):
        calls.append(prefix)
        return root
    short_root.calls = calls  # type: ignore[attr-defined]
    monkeypatch.setattr(module, "short_root", short_root)
    return root


def assert_instance_profile(profile_path: Path, base: Path, root: Path) -> None:
    instance = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert profile_path.parent == root and instance["llm"]["accelerator"] == "cpu"
    assert Path(instance["app"]["data_dir"]).is_relative_to(root.resolve())
    # Verrou lourd repris du profil de base : l'instance isolée et celle qu'il décrit ne calculent pas en même temps.
    assert instance["runtime"]["host_lock_path"] == str(runtime_location(load_profile(base), "host_lock_path"))


def test_e2e_instance_starts_from_the_requested_base_profile(tmp_path, monkeypatch):
    base = cpu_profile(tmp_path)
    root = isolated_root(tmp_path, monkeypatch, e2e_instance)
    started: list[Path] = []
    monkeypatch.setattr(e2e_instance, "start", lambda path: started.append(path) or {"status": "running"})
    state = tmp_path / "etat.json"
    monkeypatch.setattr(sys, "argv", ["e2e_instance.py", "start", "--state", str(state), "--profile", str(base)])
    assert e2e_instance.main() == 0
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert started == [Path(saved["profile"])] and saved["root"] == str(root)
    assert_instance_profile(Path(saved["profile"]), base, root)
    assert saved["base_profile"] == {"file": "local16-cpu.yaml", "sha256": hashlib.sha256(base.read_bytes()).hexdigest()}


def stop_after_choice(bases: list[Path]):
    def control_profile(base: Path, root: Path) -> Path:
        bases.append(base)
        raise RuntimeError("arrêt après le choix du profil")
    return control_profile


def test_e2e_instance_keeps_the_delivered_profile_by_default_and_refuses_misplaced_profiles(tmp_path, monkeypatch):
    bases: list[Path] = []
    monkeypatch.setattr(e2e_instance, "control_profile", stop_after_choice(bases))
    isolated_root(tmp_path, monkeypatch, e2e_instance)
    monkeypatch.setattr(sys, "argv", ["e2e_instance.py", "start", "--state", str(tmp_path / "etat.json")])
    with pytest.raises(RuntimeError, match="arrêt après le choix du profil"):
        e2e_instance.main()
    assert bases == [DELIVERED]
    created = len(e2e_instance.short_root.calls)
    for argv in (["start", "--profile", str(tmp_path / "absent.yaml")], ["stop", "--profile", str(DELIVERED)]):
        monkeypatch.setattr(sys, "argv", ["e2e_instance.py", *argv, "--state", str(tmp_path / "etat.json")])
        with pytest.raises(SystemExit) as stopped:
            e2e_instance.main()
        assert stopped.value.code == 2
    assert len(e2e_instance.short_root.calls) == created  # profil absent refusé avant toute racine temporaire


def test_restore_question_prepare_uses_the_requested_base_profile(tmp_path, monkeypatch):
    base = cpu_profile(tmp_path)
    root = isolated_root(tmp_path, monkeypatch, restore_question_check)

    def api(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/documents/import":
            return httpx.Response(200, json={"imports": [{"job_id": "j1"}]})
        return httpx.Response(200, json={"jobs": [{"id": "j1", "state": "ready"}]})

    monkeypatch.setattr(restore_question_check, "start", lambda path: {"status": "running"})
    monkeypatch.setattr(restore_question_check, "status", lambda path: {"status": "stopped"})
    monkeypatch.setattr(restore_question_check, "client_for", lambda path: httpx.Client(transport=httpx.MockTransport(api), base_url="http://127.0.0.1:9"))
    monkeypatch.setattr(restore_question_check, "ask", lambda client, question, timeout: {"query_id": "q1", "terminal": "done", "citations": ["s1"]})
    monkeypatch.setattr(restore_question_check, "citation", lambda client, query_id, source_id: {"source_id": source_id, "http_status": 200})
    monkeypatch.setattr(restore_question_check, "create_backup", lambda path: {"path": str(tmp_path / "sauvegarde"), "state": "verified"})
    state = tmp_path / "etat.json"
    monkeypatch.setattr(sys, "argv", ["restore_question_check.py", "prepare", "--state", str(state), "--profile", str(base)])
    assert restore_question_check.main() == 0
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["prepared"] is True and saved["source_root"] == str(root)
    assert_instance_profile(root / "profile.yaml", base, root)
    assert saved["base_profile"] == {"file": "local16-cpu.yaml", "sha256": hashlib.sha256(base.read_bytes()).hexdigest()}


def test_restore_question_default_profile_and_restore_phase_without_profile(tmp_path, monkeypatch):
    bases: list[Path] = []
    monkeypatch.setattr(restore_question_check, "control_profile", stop_after_choice(bases))
    isolated_root(tmp_path, monkeypatch, restore_question_check)
    monkeypatch.setattr(sys, "argv", ["restore_question_check.py", "prepare", "--state", str(tmp_path / "etat.json")])
    with pytest.raises(RuntimeError, match="arrêt après le choix du profil"):
        restore_question_check.main()
    assert bases == [DELIVERED]
    # La restauration reprend le profil enregistré dans la sauvegarde : un profil de base n'y aurait aucun effet.
    monkeypatch.setattr(sys, "argv", ["restore_question_check.py", "restore", "--state", str(tmp_path / "etat.json"),
                                      "--report", str(tmp_path / "rapport.json"), "--profile", str(DELIVERED)])
    with pytest.raises(SystemExit) as stopped:
        restore_question_check.main()
    assert stopped.value.code == 2
