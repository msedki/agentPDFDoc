"""Régressions du pilote natif : extraction doublée, processus Python possédés.

Aucun modèle, moteur documentaire, serveur Ollama ou Qdrant n'est lancé ici.
Les processus adverses sont créés dans des groupes isolés propres au test.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qualification import prepare_grounded_native as preparer
from tools.qualification import run_grounded_native as launcher


def test_first_page_scope_matches_native_zero_based_extraction_and_keeps_quality_failure(tmp_path, monkeypatch):
    """Une page imprimée « 1 » se sélectionne avec l'index API 0, même partielle."""
    originals = tmp_path / "pdfs"
    originals.mkdir()
    content = b"%PDF-1.7\nexplicit extraction double\n"
    monkeypatch.setattr(preparer, "OFFICIAL", tuple(
        {**specification, "sha256": hashlib.sha256(content).hexdigest()}
        for specification in preparer.OFFICIAL
    ))
    for specification in preparer.OFFICIAL:
        (originals / (specification["key"] + ".pdf")).write_bytes(content)
    calls = []
    extracted = {
        "page_count": 3,
        "pages": [{"page_index": 0, "extraction_state": "error", "blocks": [],
                   "native_quality": {"passed": False, "monotonic_vertical_order": False}}],
        "warnings": [{"code": "NATIVE_QUALITY_FAILED", "page_index": 0}],
        "complete": False,
    }

    def native_window_double(path, version_id, first, last, settings, output_dir):
        calls.append((path.stem, first, last, settings))
        return copy.deepcopy(extracted)

    monkeypatch.setattr(preparer, "extract_window", native_window_double)
    monkeypatch.setattr(preparer, "stitch_structure", lambda pages: ([], []))
    monkeypatch.setattr(preparer, "SELECTED", ())
    output = tmp_path / "frozen"
    preparer.prepare(output, download_official=False, pdf_directory=originals)
    manifest = json.loads((output / "inputs.json").read_text())
    assert len(calls) == len(manifest["cases"]) == 2
    for case, document, observed in zip(manifest["cases"], manifest["documents"], calls, strict=True):
        scope = case["scope"]
        extraction = json.loads(Path(document["extraction_path"]).read_text())
        assert observed[1:3] == (0, 0)
        assert (scope["page_start"], scope["page_end"]) == observed[1:3]
        assert scope["page_start"] == extraction["pages"][0]["page_index"]
        assert extraction["pages"][0]["extraction_state"] == "error"
        assert not extraction["pages"][0]["native_quality"]["passed"]
        assert extraction["status"] == "ready_partial" and document["allow_partial"]
        assert extraction["coverage"] == {"total": 3, "processed": 1, "ocr": 0, "unresolved": 2}
        assert {warning["code"] for warning in extraction["warnings"]} == {
            "NATIVE_QUALITY_FAILED", "qualification_first_page_only",
        }
        assert document["extraction_sha256"] == preparer.digest_file(Path(document["extraction_path"]))


def test_changed_pdf_is_refused_before_extraction_or_oracle_publication(tmp_path, monkeypatch):
    originals = tmp_path / "pdfs"
    originals.mkdir()
    expected = b"%PDF-1.7\nexplicit expected source double\n"
    changed = b"%PDF-1.7\nexplicit changed source double\n"
    specification = {**preparer.OFFICIAL[0], "sha256": hashlib.sha256(expected).hexdigest()}
    monkeypatch.setattr(preparer, "OFFICIAL", (specification,))
    filename = specification["key"] + ".pdf"
    (originals / filename).write_bytes(changed)

    def forbidden(*args, **kwargs):
        raise AssertionError("Un original différent doit être refusé sans extraction ni réseau.")

    monkeypatch.setattr(preparer, "extract_window", forbidden)
    monkeypatch.setattr(preparer.urllib.request, "urlopen", forbidden)
    output = tmp_path / "frozen"
    with pytest.raises(ValueError, match="original diffère de la révision figée"):
        preparer.prepare(output, download_official=False, pdf_directory=originals)
    assert not (output / "inputs.json").exists()
    assert (output / "originals" / filename).read_bytes() == changed


def wait_for(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Le processus contrôlé n'a pas atteint l'état attendu.")
        time.sleep(0.01)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Le pilote utilise les groupes POSIX Linux.")
@pytest.mark.parametrize("leader_exits_first", [False, True])
def test_stop_owned_kills_ignoring_descendant_even_after_leader_exit(tmp_path, monkeypatch, leader_exits_first):
    from services.runtime.posix_process import PosixJob, group_members

    ready = tmp_path / "child-ready.json"
    script = tmp_path / "owned-parent.py"
    child_code = (
        "import json, os, signal, sys, time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()})); time.sleep(30)"
    )
    script.write_text(
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, sys.argv[1]])\n"
        "time.sleep(30)\n"
    )
    # Seule l'horloge du pilote est accélérée : la grâce de 15 s tient en 150 ms.
    # Le groupe et les signaux restent réels ; aucun service externe n'est visé.
    monkeypatch.setattr(launcher, "time", SimpleNamespace(monotonic=lambda: time.monotonic() * 100,
                                                         sleep=time.sleep))
    with PosixJob() as job:
        owned = job.launch([sys.executable, str(script), str(ready)], cwd=tmp_path,
                           env=dict(os.environ), log_path=tmp_path / "owned.log")
        unrelated = job.launch([sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path,
                               env=dict(os.environ), log_path=tmp_path / "unrelated.log")
        wait_for(ready.exists)
        child_pid = json.loads(ready.read_text())["pid"]
        assert child_pid in group_members(owned.pgid)
        if leader_exits_first:
            os.kill(owned.pid, signal.SIGTERM)
            wait_for(lambda: owned.poll() is not None)
            assert not owned.reaped
            assert child_pid in group_members(owned.pgid)
        receipt = launcher.stop_owned(owned)
        wait_for(lambda: not group_members(owned.pgid))
        assert receipt["owned_group_empty"] and receipt["leader_reaped"], receipt
        assert receipt["remaining_group_members"] == []
        assert owned.reaped and owned.poll() is not None
        assert unrelated.poll() is None, "L'arrêt doit se limiter au groupe possédé demandé."
