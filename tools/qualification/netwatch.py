"""Observation en lecture des sockets d'un processus possédé, sans droits administrateur.

Relève les connexions non loopback et les écoutes d'un PID pendant une fenêtre.
Ce n'est ni un blocage réseau ni une capture DNS : une tentative bloquée avant
l'ouverture d'un socket, ou une résolution de nom, n'apparaît pas ici.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import time
from pathlib import Path

import psutil


def is_loopback(address) -> bool:
    try:
        return ipaddress.ip_address(address.ip).is_loopback
    except ValueError:
        return False


def watch(pid: int, until: dt.datetime, interval: float) -> dict:
    process = psutil.Process(pid)
    report = {"pid": pid, "exe": process.exe(), "create_time": process.create_time(),
              "started_utc": dt.datetime.now(dt.UTC).isoformat(), "until_utc": until.isoformat(),
              "interval_s": interval, "samples": 0, "non_loopback": [], "listening": set(),
              "method": "psutil.Process.net_connections(kind='inet') polled; observes sockets, not DNS or blocked attempts"}
    while dt.datetime.now(dt.UTC) < until:
        for connection in process.net_connections(kind="inet"):
            if connection.status == psutil.CONN_LISTEN:
                report["listening"].add(f"{connection.laddr.ip}:{connection.laddr.port}")
            elif connection.raddr and not is_loopback(connection.raddr):
                report["non_loopback"].append({"utc": dt.datetime.now(dt.UTC).isoformat(),
                                               "laddr": f"{connection.laddr.ip}:{connection.laddr.port}",
                                               "raddr": f"{connection.raddr.ip}:{connection.raddr.port}",
                                               "status": connection.status})
        report["samples"] += 1
        time.sleep(interval)
    report["listening"] = sorted(report["listening"])
    report["ended_utc"] = dt.datetime.now(dt.UTC).isoformat()
    report["result"] = "non-loopback sockets observed" if report["non_loopback"] else "no non-loopback socket observed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--until", required=True, help="Fin de fenêtre ISO 8601 UTC, ex. 2026-09-30T09:24:00+00:00")
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = watch(args.pid, dt.datetime.fromisoformat(args.until), args.interval)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(report["result"], report["samples"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
