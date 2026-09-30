"""One authorized native build with sampled host/process resources; no browser."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,90}", args.tag):
        parser.error("Use a unique simple evidence tag")
    web = Path(__file__).resolve().parents[1]
    node = Path("D:/node/node-v22.17.0-win-x64/node.exe")
    corepack = node.parent / "node_modules/corepack/dist/pnpm.js"
    if not node.is_file() or not corepack.is_file():
        raise SystemExit("The already resolved local Node/Corepack executables are missing")
    log = web / "reports" / f"build-{args.tag}.log"
    resources = web / "reports" / f"build-{args.tag}-resources.jsonl"
    manifest = web / "reports" / f"export-manifest-{args.tag}.json"
    if any(path.exists() for path in (log, resources, manifest)):
        raise SystemExit("Preserve the existing evidence; choose a new tag")
    environment = os.environ.copy()
    environment.update(NEXT_TELEMETRY_DISABLED="1", COREPACK_ENABLE_NETWORK="0", NODE_OPTIONS="--max-old-space-size=2048", FORCE_COLOR="0")
    environment.pop("NO_COLOR", None)
    environment["PATH"] = str(node.parent) + os.pathsep + environment.get("PATH", "")
    psutil.cpu_percent(interval=0.2)

    def sample(phase, process=None):
        children = []
        if process:
            try:
                candidates = [process] + process.children(recursive=True)
            except psutil.Error:
                candidates = []
            for child in candidates:
                try:
                    with child.oneshot():
                        memory = child.memory_info()
                        children.append({"id": child.pid, "parent_id": child.ppid(), "name": child.name(), "rss_mib": round(memory.rss / 1048576, 1), "private_mib": round(memory.private / 1048576, 1) if hasattr(memory, "private") else None})
                except psutil.Error:
                    pass
        return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "phase": phase, "host_available_mib": round(psutil.virtual_memory().available / 1048576, 1), "host_cpu_percent": psutil.cpu_percent(interval=None), "disk_free_bytes": psutil.disk_usage(str(web)).free, "owned_build_tree": children, "method": "Host/per-process snapshots about every 2 seconds; no summed RSS, continuous peak or 30-minute qualification claim"}

    started = time.monotonic()
    with resources.open("x", encoding="utf-8") as samples, log.open("xb") as output:
        def record(value):
            samples.write(json.dumps(value, ensure_ascii=True) + "\n")
            samples.flush()
        record(sample("before"))
        build = subprocess.Popen([str(node), str(corepack), "build"], cwd=web, env=environment, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        owned = psutil.Process(build.pid)
        while build.poll() is None:
            record(sample("during", owned))
            time.sleep(2)
        code = build.wait()
        record({**sample("after"), "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2)})
    if code == 0:
        entries = []
        for path in sorted((web / "out").rglob("*")):
            if path.is_file():
                entries.append({"path": path.relative_to(web / "out").as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest.write_text(json.dumps({"status": "BUILD_EXIT_0_STATIC_EXPORT", "files": len(entries), "total_bytes": sum(entry["bytes"] for entry in entries), "entries": entries}, indent=2), encoding="utf-8")
    print(json.dumps({"exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2), "log": str(log), "resources": str(resources), "manifest": str(manifest) if code == 0 else None}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
