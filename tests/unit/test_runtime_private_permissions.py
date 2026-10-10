"""Permissions POSIX réelles ; services, disponibilité et transport de restauration sont doublés."""

import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.runtime import backup, supervisor
from services.runtime.artifacts import file_hash
from tests.unit.test_runtime_backup import (
    BackupTransportDouble,
    HttpxToTheEmptyQdrantServer,
    backup_target,
    ports_assumed_free,
    verified_backup_without_collection,
)
from tests.unit.test_runtime_supervisor import (
    ProgramBinariesDouble,
    _profile,
    cooperative_stop_accepted,
    recording_jobs,
    simulated_program,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Permissions POSIX, Windows natif inchangé")


@pytest.fixture
def permissive_umask():
    """Seulement le processus pytest isolé ; le runtime applicatif ne change jamais son umask."""
    previous = os.umask(0o002)
    try:
        yield
    finally:
        os.umask(previous)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def unchanged_identity(path: Path) -> tuple:
    info = path.lstat()
    # La lecture de hash peut actualiser atime ; identité, contenu, mode et timestamps d'écriture restent invariants.
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_uid, info.st_gid, info.st_mode,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@pytest.mark.parametrize("failed", [False, True])
def test_backup_root_is_private_before_quiesce_in_success_and_failure(tmp_path, monkeypatch, permissive_umask, failed):
    output = tmp_path / "new-parent" / "backup"
    transport = BackupTransportDouble(primary=ValueError("quiesce double refusé") if failed else None)
    observed = []

    def transport_double(request):
        if request.url.path.endswith("/quiesce"):
            observed.append(mode(output))
        return transport(request)

    profile, _ = backup_target(tmp_path, monkeypatch, transport_double)
    if failed:
        with pytest.raises(ValueError, match="quiesce double refusé"):
            backup.create_backup(profile, output)
    else:
        assert backup.create_backup(profile, output)["state"] == "verified"
    assert observed == [0o700] and mode(output) == 0o700


def test_windows_backup_directory_creation_keeps_its_previous_mode_under_simulation(tmp_path, monkeypatch, permissive_umask):
    profile, _ = backup_target(tmp_path, monkeypatch, BackupTransportDouble())
    monkeypatch.setattr(backup, "os", SimpleNamespace(name="nt"))  # seule sélection de mode doublée sous POSIX
    output = tmp_path / "windows-backup-double"
    assert backup.create_backup(profile, output)["state"] == "verified"
    assert mode(output) == 0o775


def test_restore_creates_private_root_control_and_qdrant_key(tmp_path, monkeypatch, permissive_umask):
    program = simulated_program(tmp_path)
    for module in (backup, supervisor):
        monkeypatch.setattr(module, "ROOT", program)
    folder = verified_backup_without_collection(tmp_path / "backup", tmp_path / "old-data")
    target = tmp_path / "restored-data"
    recording_jobs(monkeypatch, backup)
    monkeypatch.setattr(backup, "check_ports", ports_assumed_free)
    monkeypatch.setattr(backup, "native_paths", ProgramBinariesDouble(program))
    monkeypatch.setattr(backup, "send_owned_console_interrupt", cooperative_stop_accepted)
    monkeypatch.setattr(backup, "httpx", HttpxToTheEmptyQdrantServer)
    observed = {}

    def ready_double(*args, **kwargs):
        observed.update(root=mode(target), control=mode(target / "control"),
                        qdrant_key=mode(target / "control/qdrant-api-key"))

    monkeypatch.setattr(backup, "wait_http", ready_double)
    assert backup.restore_backup(folder, target, qdrant_port=16343)["state"] == "restored_storage_verified"
    assert observed == {"root": 0o700, "control": 0o700, "qdrant_key": 0o600}
    assert not (target / "control/qdrant-api-key").exists()


def test_admin_key_is_private_before_job_creation_and_removed_on_failure(tmp_path, monkeypatch, permissive_umask):
    profile, data = _profile(tmp_path, monkeypatch)
    observed = {}

    def refused_job_double():
        observed.update(control=mode(data / "control"), admin_key=mode(data / "control/admin-token"))
        raise OSError("Job double refusé")

    monkeypatch.setattr(supervisor, "ProcessJob", refused_job_double)
    assert supervisor.supervise(profile) == 1
    assert observed == {"control": 0o700, "admin_key": 0o600}
    assert not (data / "control/admin-token").exists()


def test_qdrant_keys_are_private_on_creation_and_regular_file_rotation(tmp_path, permissive_umask):
    supervisor.issue_qdrant_key(tmp_path)
    path = tmp_path / "qdrant-api-key"
    first_inode, first_hash = path.stat().st_ino, file_hash(path)
    first_mode = mode(path)
    supervisor.issue_qdrant_key(tmp_path)
    assert (first_mode, mode(path)) == (0o600, 0o600)
    assert path.stat().st_ino != first_inode and file_hash(path) != first_hash
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_qdrant_key_refuses_preexisting_links_without_modifying_them(tmp_path, link_kind):
    source = tmp_path / "original-test-double"
    source.write_bytes(b"known-test-double-secret")
    path = tmp_path / "qdrant-api-key"
    if link_kind == "symlink":
        path.symlink_to(source)
    else:
        path.hardlink_to(source)
    before = (source.stat().st_ino, file_hash(source), unchanged_identity(path), mode(source))
    with pytest.raises(ValueError, match="Jeton runtime"):
        supervisor.issue_qdrant_key(tmp_path)
    assert (source.stat().st_ino, file_hash(source), unchanged_identity(path), mode(source)) == before


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_supervisor_does_not_remove_or_modify_rejected_admin_key(tmp_path, monkeypatch, link_kind):
    profile, data = _profile(tmp_path, monkeypatch)
    control = data / "control"
    control.mkdir(parents=True)
    control_mode = mode(control)
    source = tmp_path / "original-test-double"
    source.write_bytes(b"known-test-double-secret")
    path = control / "admin-token"
    if link_kind == "symlink":
        path.symlink_to(source)
    else:
        path.hardlink_to(source)
    before = (file_hash(source), unchanged_identity(path), mode(source))

    def unexpected_job_double():
        pytest.fail("Aucun Job ne doit être créé après le refus du jeton")

    monkeypatch.setattr(supervisor, "ProcessJob", unexpected_job_double)
    assert supervisor.supervise(profile) == 1
    assert (file_hash(source), unchanged_identity(path), mode(source)) == before
    assert mode(control) == control_mode


def test_token_write_failure_keeps_the_existing_regular_key_and_removes_temporary(tmp_path, monkeypatch):
    path = tmp_path / "qdrant-api-key"
    path.write_bytes(b"known-test-double-secret")
    before = file_hash(path), unchanged_identity(path), mode(path)

    def replace_refused(*args, **kwargs):
        raise OSError("remplacement double refusé")

    monkeypatch.setattr(supervisor.os, "replace", replace_refused)
    with pytest.raises(OSError, match="remplacement double refusé"):
        supervisor.issue_qdrant_key(tmp_path)
    assert (file_hash(path), unchanged_identity(path), mode(path)) == before
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


def test_windows_key_write_keeps_the_existing_branch_under_simulation(tmp_path, monkeypatch, permissive_umask):
    monkeypatch.setattr(sys, "platform", "win32")
    supervisor.issue_qdrant_key(tmp_path)
    path = tmp_path / "qdrant-api-key"
    first_inode = path.stat().st_ino
    supervisor.issue_qdrant_key(tmp_path)
    assert mode(path) == 0o664 and path.stat().st_ino == first_inode


def test_fdopen_failure_closes_descriptor_keeps_original_and_removes_temporary(tmp_path, monkeypatch):
    path = tmp_path / "qdrant-api-key"
    path.write_bytes(b"known-test-double-secret")
    before = file_hash(path), unchanged_identity(path)
    descriptors = []

    def fdopen_refused(descriptor, *args, **kwargs):
        descriptors.append(descriptor)
        raise OSError("fdopen double refusé")

    monkeypatch.setattr(supervisor.os, "fdopen", fdopen_refused)
    with pytest.raises(OSError, match="fdopen double refusé"):
        supervisor.issue_qdrant_key(tmp_path)
    assert (file_hash(path), unchanged_identity(path)) == before
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert sorted(item.name for item in tmp_path.iterdir()) == [path.name]


def test_foreign_owner_is_refused_without_changing_key(tmp_path, monkeypatch):
    path = tmp_path / "qdrant-api-key"
    path.write_bytes(b"known-test-double-secret")
    before = file_hash(path), unchanged_identity(path)
    monkeypatch.setattr(supervisor.os, "geteuid", lambda: -1)  # propriétaire étranger simulé, aucune élévation
    with pytest.raises(ValueError, match="Jeton runtime"):
        supervisor.issue_qdrant_key(tmp_path)
    assert (file_hash(path), unchanged_identity(path)) == before


def test_stale_regular_key_with_permissive_mode_is_rotated_privately(tmp_path, permissive_umask):
    path = tmp_path / "qdrant-api-key"
    path.write_bytes(b"known-test-double-secret")
    before = path.stat().st_ino
    assert mode(path) == 0o664
    supervisor.issue_qdrant_key(tmp_path)
    assert mode(path) == 0o600 and path.stat().st_ino != before
