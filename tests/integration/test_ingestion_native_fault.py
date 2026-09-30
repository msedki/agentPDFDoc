"""A real isolated fatal process cannot make old checkpoints reusable."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_fatal_process_log_quarantines_worker_restart(tmp_path):
    output_dir = tmp_path / "failed-attempt"
    output_dir.mkdir()
    checkpoint = output_dir / "window-000000-000000.json"
    checkpoint.write_text('{"previous_attempt":"must_be_preserved"}', encoding="utf-8")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    fault_log = output_dir / "worker-native-fault.log"
    # Process-local Windows error mode avoids an interactive crash dialog.  No
    # application, service, model, or host setting is changed by this fixture.
    fatal_script = (
        "import ctypes, faulthandler, os, sys\n"
        "if os.name == 'nt':\n"
        "    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)\n"
        "with open(sys.argv[1], 'ab', buffering=0) as stream:\n"
        "    faulthandler.enable(file=stream, all_threads=True)\n"
        "    os.abort()\n"
    )
    child = subprocess.run(
        [sys.executable, "-c", fatal_script, str(fault_log)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=False,
        close_fds=True,
    )
    assert child.returncode != 0
    assert fault_log.is_file() and fault_log.stat().st_size > 0
    assert b"Fatal Python error" in fault_log.read_bytes()
    assert not (output_dir / "native-fault.json").exists()
    fault_hash = hashlib.sha256(fault_log.read_bytes()).hexdigest()

    source = Path(__file__).resolve().parents[2] / "fixtures/qualification-v2.1/errors/Page blanche.pdf"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(json.dumps({
        "path": str(source), "output_dir": str(output_dir),
        "version_id": "fatal-restart-version", "config": {"pipeline_route": "native"},
    }), encoding="utf-8")
    environment = os.environ.copy()
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    restart = subprocess.run(
        [sys.executable, "-m", "services.ingestion.worker", "--request", str(request), "--result", str(result)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=False,
        close_fds=True, env=environment,
    )
    response = json.loads(result.read_text(encoding="utf-8"))
    assert restart.returncode == 2
    assert response["ok"] is False
    assert response["error"]["code"] == "EXTRACTION_QUARANTINED"
    marker = json.loads((output_dir / "native-fault.json").read_text(encoding="utf-8"))
    assert marker["fault_log"] == fault_log.name
    assert hashlib.sha256(fault_log.read_bytes()).hexdigest() == fault_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert list(output_dir.glob("window-*.json")) == [checkpoint]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash
    assert not (output_dir / "extraction.json").exists()
    assert not restart.stdout and not restart.stderr
