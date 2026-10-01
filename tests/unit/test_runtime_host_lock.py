import asyncio
import multiprocessing
import os
import sys
import time

import pytest

from services.runtime.resources import (
    HostHeavyLockBusy,
    ResourceAdmissionError,
    ResourceGovernor,
    acquire_host_heavy_lock,
    host_heavy_lock_available,
)

# Byte-lock msvcrt sous Windows, flock sous Linux : mêmes garanties vérifiées entre vrais processus.
pytestmark = pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="verrou msvcrt (Windows) ou flock (Linux)")
CONTEXT = multiprocessing.get_context("spawn")


def _hold(path, owner, ready, release):
    from services.runtime.resources import acquire_host_heavy_lock

    with acquire_host_heavy_lock(owner, path):
        ready.set()
        release.wait(30)


def _try_acquire(path, result):
    from services.runtime.resources import HostHeavyLockBusy, acquire_host_heavy_lock

    try:
        with acquire_host_heavy_lock("probe", path):
            result.put("acquired")
    except HostHeavyLockBusy as busy:
        result.put(busy.code)


def _holder(path, owner):
    ready, release = CONTEXT.Event(), CONTEXT.Event()
    process = CONTEXT.Process(target=_hold, args=(path, owner, ready, release), daemon=True)
    process.start()
    assert ready.wait(60), "processus détenteur non prêt"
    return process, release


def _probe(path) -> str:
    result = CONTEXT.Queue()
    process = CONTEXT.Process(target=_try_acquire, args=(path, result), daemon=True)
    process.start()
    try:
        return result.get(timeout=60)
    finally:
        process.join(30)


def _stop(process, release):
    release.set()
    process.join(30)
    assert process.exitcode == 0


def _governor(tmp_path, lock):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}}, host_lock_path=lock)
    item._admit = lambda *args: None
    return item


def test_host_lock_excludes_another_process_and_names_holder(tmp_path):
    lock = tmp_path / "control" / "host-heavy.lock"
    process, release = _holder(lock, "calibration")
    try:
        with pytest.raises(HostHeavyLockBusy) as caught:
            acquire_host_heavy_lock("generation", lock)
        assert caught.value.code == "host_heavy_lock_busy"
        assert caught.value.snapshot["holder"]["pid"] == process.pid
        assert caught.value.snapshot["holder"]["owner"] == "calibration"
    finally:
        _stop(process, release)
    with acquire_host_heavy_lock("generation", lock) as held:
        assert held.owner == "generation"
        assert _probe(lock) == "host_heavy_lock_busy"
    assert _probe(lock) == "acquired"


def test_lock_of_killed_holder_is_released_by_windows(tmp_path):
    # Nom historique (preuves Windows) ; sous Linux, flock est relâché de même à la mort du détenteur.
    lock = tmp_path / "host-heavy.lock"
    process, _ = _holder(lock, "ingestion")
    process.kill()
    process.join(30)
    deadline = time.monotonic() + 10
    while True:
        try:
            acquire_host_heavy_lock("generation", lock).release()
            break
        except HostHeavyLockBusy:
            assert time.monotonic() < deadline, "verrou non libéré après la mort du détenteur"
            time.sleep(0.1)


@pytest.mark.parametrize("lease", ["generation", "ingestion"])
def test_governor_heavy_lease_is_refused_while_other_process_holds_host_lock(tmp_path, lease):
    lock = tmp_path / "host-heavy.lock"
    item = _governor(tmp_path, lock)

    async def enter():
        async with getattr(item, lease)():
            return item.snapshot()

    process, release = _holder(lock, "restored-instance")
    try:
        with pytest.raises(ResourceAdmissionError) as caught:
            asyncio.run(enter())
        # services/api/jobs.py et query.py reconnaissent la classe par son nom exact.
        assert type(caught.value).__name__ == "ResourceAdmissionError"
        assert caught.value.code == "host_heavy_lock_busy"
        # Texte affiché tel quel par l'interface : ni dictionnaire Python ni chemin de verrou.
        assert str(caught.value).startswith("Un travail lourd est déjà en cours sur ce poste (restored-instance, PID ")
        assert "{" not in str(caught.value) and str(lock) not in str(caught.value)
        assert caught.value.snapshot["admission"] == {"owner": lease, "code": "host_heavy_lock_busy"}
        assert caught.value.snapshot["holder"]["pid"] == process.pid
        assert not item._heavy.locked() and item._owner is None and item._generation_requests == 0
    finally:
        _stop(process, release)
    snapshot = asyncio.run(enter())
    assert snapshot["heavy_owner"] == lease and snapshot["host_heavy_lock_held"] is True
    assert item.snapshot()["host_heavy_lock_held"] is False


def test_governor_holds_host_lock_for_whole_generation(tmp_path):
    lock = tmp_path / "host-heavy.lock"
    item = _governor(tmp_path, lock)

    async def generate():
        async with item.generation():
            return await asyncio.to_thread(_probe, lock)

    assert asyncio.run(generate()) == "host_heavy_lock_busy"
    assert _probe(lock) == "acquired"
    assert os.path.getsize(lock) == 1


def test_queue_waits_while_host_lock_is_held_elsewhere_then_resumes(tmp_path):
    lock = tmp_path / "host-heavy.lock"
    item = _governor(tmp_path, lock)
    assert host_heavy_lock_available(lock) and item.allow_ingestion()
    process, release = _holder(lock, "calibration")
    try:
        assert not host_heavy_lock_available(lock)
        # Le job reste en file : aucune tentative de lease, donc aucune mise en pause manuelle.
        assert not item.allow_ingestion()
    finally:
        _stop(process, release)
    assert host_heavy_lock_available(lock) and item.allow_ingestion()


def test_stale_holder_identity_does_not_block_the_queue(tmp_path):
    lock = tmp_path / "host-heavy.lock"
    lock.write_bytes(b'0{"owner": "calibration", "pid": 999999}')
    assert host_heavy_lock_available(lock)
    assert lock.stat().st_size == 1
