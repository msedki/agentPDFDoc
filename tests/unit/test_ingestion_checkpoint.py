import json
import sys
import types

import pytest

from services.ingestion.checkpoint import CheckpointStore, extraction_lock
from services.ingestion.config import IngestionConfig
from services.ingestion.errors import IngestionError


def test_checkpoint_tampering_and_version_drift_are_rejected(tmp_path):
    store = CheckpointStore(tmp_path, {"source_sha256": "original", "pipeline_fingerprint": "parser"})
    payload = {"page_start": 0, "page_end": 3, "pages": [{"text": "Valeur contrôlée 24 V"}]}
    store.write(payload)
    assert store.read(0, 3) == payload
    with pytest.raises(IngestionError) as mismatch:
        CheckpointStore(tmp_path, {"source_sha256": "changed", "pipeline_fingerprint": "parser"}).read(0, 3)
    assert mismatch.value.code == "CHECKPOINT_INVALID"
    path = store.path(0, 3)
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["payload"]["pages"][0]["text"] = "wrong value"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(IngestionError):
        store.read(0, 3)
    assert path.exists()


def test_process_lock_is_released_and_does_not_delete_extraction(tmp_path):
    with extraction_lock(tmp_path):
        with pytest.raises(IngestionError) as caught:
            with extraction_lock(tmp_path):
                pass
        assert caught.value.code == "INGESTION_ALREADY_RUNNING"
    with extraction_lock(tmp_path):
        assert (tmp_path / ".ingestion.lock").exists()


def test_windows_lock_branch_follows_sys_platform(tmp_path, monkeypatch):
    """Plateforme simulée : sous win32, le verrou passe par msvcrt (factice ici), choisi par sys.platform (W022, W029)."""
    calls = []
    msvcrt = types.SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=lambda descriptor, mode, size: calls.append((mode, size)))
    monkeypatch.setitem(sys.modules, "msvcrt", msvcrt)
    monkeypatch.setattr(sys, "platform", "win32")
    with extraction_lock(tmp_path):
        assert calls == [(msvcrt.LK_NBLCK, 1)]
    assert calls == [(msvcrt.LK_NBLCK, 1), (msvcrt.LK_UNLCK, 1)]


def test_embedding_changes_do_not_change_parser_fingerprint():
    first = IngestionConfig.from_mapping({"pdf": {"threads_max": 2}, "embedding": {"model_id": "one"}})
    second = IngestionConfig.from_mapping({"pdf": {"threads_max": 2}, "embedding": {"model_id": "two"}})
    assert first.fingerprint() == second.fingerprint()


def test_locked_parser_weights_change_fingerprint_but_dense_weights_do_not(tmp_path):
    artifact_dir = tmp_path / "docling"
    lock = tmp_path / "artifacts.lock.json"
    manifest = {"groups": {"layout": [{"target": str(artifact_dir / "model.safetensors"), "revision": "one", "sha256": "a"}],
                           "e5": [{"target": str(tmp_path / "e5" / "model.onnx"), "revision": "dense-one", "sha256": "b"}]}}
    lock.write_text(json.dumps(manifest), encoding="utf-8")
    settings = IngestionConfig(artifacts_path=str(artifact_dir), artifacts_lock_path=str(lock))
    initial = settings.fingerprint()
    manifest["groups"]["e5"][0]["sha256"] = "changed-dense"
    lock.write_text(json.dumps(manifest), encoding="utf-8")
    assert settings.fingerprint() == initial
    manifest["groups"]["layout"][0]["sha256"] = "changed-parser"
    lock.write_text(json.dumps(manifest), encoding="utf-8")
    assert settings.fingerprint() != initial


def test_v21_profile_names_are_resolved():
    settings = IngestionConfig.from_mapping({"pdf": {"tessdata_dir": "local-tessdata", "native_parser_threads": 1, "model_inference_threads": 3, "checkpoint_window_pages_initial": 4}})
    assert settings.tessdata_path == "local-tessdata"
    assert settings.parser_threads == 1
    assert settings.threads_max == 3
    assert settings.page_window_size == 4


def test_portable_tesseract_path_is_resolved_from_project_not_worker_cwd(tmp_path, monkeypatch):
    from services.ingestion.config import PROJECT_ROOT

    monkeypatch.chdir(tmp_path)
    settings = IngestionConfig(tesseract_cmd=".runtime/bin/tesseract-5.4.0/tesseract.exe")
    assert settings.resolved_tesseract_cmd == str((PROJECT_ROOT / settings.tesseract_cmd).resolve())


def test_native_fault_quarantine_preserves_artifacts_and_refuses_reuse(tmp_path):
    (tmp_path / "native-fault.json").write_text('{"code":"INGESTION_NATIVE_FAULT"}', encoding="utf-8")
    (tmp_path / "source-evidence.json").write_text("{}", encoding="utf-8")
    with pytest.raises(IngestionError) as caught:
        with extraction_lock(tmp_path):
            pytest.fail("A quarantined extraction cannot be reopened")
    assert caught.value.code == "EXTRACTION_QUARANTINED"
    assert (tmp_path / "source-evidence.json").read_text() == "{}"
