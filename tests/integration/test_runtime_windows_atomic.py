import concurrent.futures
import json
import threading
import time

import pytest

from services.runtime.artifacts import read_json_atomic, write_json_atomic

pytestmark = pytest.mark.skipif(__import__("sys").platform != "win32", reason="NTFS/Win32 integration")


def test_real_windows_reader_sharing_conflict_is_retried(tmp_path):
    import win32con
    import win32file

    target = tmp_path / "state.json"
    write_json_atomic(target, {"revision": 0})
    reader = win32file.CreateFile(str(target), win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE, None,
        win32con.OPEN_EXISTING, win32con.FILE_ATTRIBUTE_NORMAL, None)
    try:
        competitor = tmp_path / "counterexample.tmp"
        competitor.write_text("{}", encoding="utf-8")
        with pytest.raises(PermissionError):
            competitor.replace(target)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(write_json_atomic, target, {"revision": 1})
            time.sleep(0.1)
            assert not writer.done()
            reader.Close()
            reader = None
            writer.result(timeout=3)
        assert json.loads(target.read_text(encoding="utf-8")) == {"revision": 1}
    finally:
        if reader is not None:
            reader.Close()


def test_concurrent_writers_and_readers_publish_only_complete_json(tmp_path):
    target = tmp_path / "state.json"
    write_json_atomic(target, {"value": 0, "payload": "x" * 1024})
    stop = threading.Event()
    observed = []

    def reader():
        while not stop.is_set():
            observed.append(read_json_atomic(target))
            time.sleep(0.001)

    def writer(offset):
        for value in range(offset, offset + 20):
            write_json_atomic(target, {"value": value, "payload": "x" * 1024})

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        watcher = pool.submit(reader)
        try:
            for result in [pool.submit(writer, 100), pool.submit(writer, 200)]:
                result.result(timeout=5)
        finally:
            stop.set()
        watcher.result(timeout=3)
    assert observed
    assert all(len(item["payload"]) == 1024 and isinstance(item["value"], int) for item in observed)
    assert not list(tmp_path.glob("state.json.tmp-*"))
