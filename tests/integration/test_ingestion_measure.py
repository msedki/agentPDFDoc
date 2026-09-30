"""CLI measurement wrapper for authorized isolated ingestion test targets."""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    if not args.target.startswith("tests/integration/test_ingestion") or any(char in args.name for char in "/\\:"):
        parser.error("Use a local ingestion test target and a directory name.")
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    run = root / ".runtime/qa/ingestion-synthetic" / f"{args.name}-{stamp}"
    run.mkdir(parents=True, exist_ok=False)
    cancel = run / "pause-requested"
    environment = os.environ.copy()
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                       OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
                       PYTHONUTF8="1", RAG_TEST_CANCEL_PATH=str(cancel),
                       DOCLING_ARTIFACTS_PATH=str(root / ".runtime/models/docling"))
    started = time.monotonic()
    peak_rss = peak_private = 0
    minimum_available = psutil.virtual_memory().available
    minimum_disk = psutil.disk_usage(root.anchor).free
    cpu = {}
    paused = False
    with (run / "pytest.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, "-m", "pytest", args.target, "-q", "--basetemp", str(run / "pytest"),
             "--junitxml", str(run / "junit.xml")],
            cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            close_fds=True, env=environment,
        )
        handle = psutil.Process(child.pid)
        with (run / "samples.jsonl").open("w", encoding="utf-8") as samples:
            while child.poll() is None:
                rss = private = 0
                try:
                    tree = [handle, *handle.children(recursive=True)]
                except psutil.Error:
                    tree = []
                for member in tree:
                    try:
                        memory = member.memory_info()
                        rss += memory.rss
                        private += getattr(memory, "private", memory.rss)
                        times = member.cpu_times()
                        identity = f"{member.pid}:{member.create_time()}"
                        cpu[identity] = max(cpu.get(identity, 0), times.user + times.system)
                    except psutil.Error:
                        pass
                peak_rss, peak_private = max(peak_rss, rss), max(peak_private, private)
                available = psutil.virtual_memory().available
                disk = psutil.disk_usage(root.anchor).free
                minimum_available, minimum_disk = min(minimum_available, available), min(minimum_disk, disk)
                if available < 1536 * 1024**2 and not paused:
                    cancel.touch()
                    paused = True
                samples.write(json.dumps({"seconds": time.monotonic() - started,
                                          "tree_rss_bytes": rss, "tree_private_bytes": private,
                                          "host_available_bytes": available, "drive_free_bytes": disk}) + "\n")
                samples.flush()
                time.sleep(.25)
        code = child.wait()
    metrics = {"run": str(run.relative_to(root)), "target": args.target, "exit_code": code,
               "elapsed_seconds": time.monotonic() - started,
               "tree_peak_rss_mib": peak_rss / 1024**2, "tree_peak_private_mib": peak_private / 1024**2,
               "host_min_available_mib": minimum_available / 1024**2, "drive_min_free_mib": minimum_disk / 1024**2,
               "sampled_tree_cpu_seconds": sum(cpu.values()), "pause_requested": paused,
               "sample_interval_seconds": .25,
               "finished_utc": datetime.datetime.now(datetime.UTC).isoformat(),
               "adapter_source_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in sorted((root / "services/ingestion").glob("*.py"))}}
    (run / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest = [{"path": str(path.relative_to(run)), "size_bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(run.rglob("*")) if path.is_file()]
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False))
    print((run / "pytest.log").read_text(encoding="utf-8"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
