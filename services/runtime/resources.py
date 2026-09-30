"""Admission et coordination des travaux CPU, sans arrêter de processus étrangers."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


class ResourceAdmissionError(RuntimeError):
    """Le travail demandé ne peut pas préserver la réserve mémoire hôte."""

    def __init__(self, message: str, snapshot: dict[str, Any]):
        super().__init__(message)
        self.snapshot = snapshot


class ResourceGovernor:
    """Un lease lourd ; la priorité interactive demande un checkpoint durable.

    Le worker observe should_checkpoint() ou le fichier pause. Aucun délai
    nominal ne tue le worker. La reprise d'un import exige une action explicite.
    """

    def __init__(self, settings: dict[str, Any] | None = None):
        profile = settings or {}
        self.settings = profile.get("resources", profile)
        app = profile.get("app", {})
        self.data_dir = Path(app.get("data_dir", ".runtime/data")).resolve()
        self.reserve_mib = int(self.settings.get("host_available_min_mib", 1536))
        self.admit_min_mib = int(self.settings.get("admit_heavy_min_available_mib", 3072))
        self._heavy = asyncio.Lock()
        self._interactive_requests = 0
        self._generation_requests = 0
        self._owner: str | None = None
        self._mode = "interactive"
        self._pause_path = self.data_dir / "control" / "pause-ingestion"
        self.before_ingestion = None
        self.before_generation = None
        self.after_resource_violation = None

    def snapshot(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        process = psutil.Process()
        try:
            private = process.memory_info().private
        except (AttributeError, psutil.Error):
            private = None
        root = self.data_dir
        while not root.exists() and root != root.parent:
            root = root.parent
        return {
            "utc": datetime.now(UTC).isoformat(),
            "available_mib": round(memory.available / 1048576, 2),
            "total_mib": round(memory.total / 1048576, 2),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "disk_free_mib": round(shutil.disk_usage(root).free / 1048576, 2),
            "process_rss_mib": round(process.memory_info().rss / 1048576, 2),
            "process_private_mib": None if private is None else round(private / 1048576, 2),
            "memory_method": "Windows working set and private bytes; shared pages not summed",
            "mode": self._mode,
            "heavy_owner": self._owner,
            "pause_requested": self.should_checkpoint(),
            "host_reserve_mib": self.reserve_mib,
            "auto_resume_ingestion": False,
        }

    @property
    def pause_path(self) -> Path:
        return self._pause_path

    def _request_checkpoint(self) -> None:
        self._pause_path.parent.mkdir(parents=True, exist_ok=True)
        self._pause_path.touch(exist_ok=True)

    def begin_interactive(self) -> dict[str, Any]:
        self._interactive_requests += 1
        self._mode = "interactive"
        if self._owner == "ingestion":
            self._request_checkpoint()
        return self.snapshot()

    def finish_interactive(self) -> None:
        self._interactive_requests = max(0, self._interactive_requests - 1)
        # Le marqueur n'est pas effacé : seul resume_ingestion() le fait.

    def should_checkpoint(self) -> bool:
        if self._owner == "ingestion" and psutil.virtual_memory().available / 1048576 < self.reserve_mib:
            self._request_checkpoint()
        return self._interactive_requests > 0 or self._generation_requests > 0 or self._pause_path.exists()

    def allow_ingestion(self) -> bool:
        return not self.should_checkpoint() and not self._heavy.locked()

    def resume_ingestion(self) -> None:
        if self._interactive_requests or self._generation_requests:
            raise RuntimeError("Une interaction est encore active ; reprise différée.")
        self._pause_path.unlink(missing_ok=True)
        self._mode = "ingestion"

    def request_ingestion_pause(self) -> dict[str, Any]:
        self._mode = "interactive"
        self._request_checkpoint()
        return self.snapshot()

    def _admit(self, owner: str, loaded: dict[str, Any] | None = None) -> None:
        snapshot = self.snapshot()
        estimate_key = (
            "initial_llm_load_peak_estimate_mib" if owner == "generation"
            else "initial_parser_peak_estimate_mib"
        )
        resident = owner == "generation" and loaded is not None and loaded.get("loaded") is True
        estimated = (int(loaded["additional_peak_mib"]) if resident else
                     int(self.settings.get(estimate_key, 6144 if owner == "generation" else 4096)))
        if estimated < 0:
            raise ValueError("Estimation de mémoire additionnelle négative")
        required = max(0 if resident else self.admit_min_mib, estimated + self.reserve_mib)
        snapshot["admission"] = {"owner": owner, "resident_model": resident,
                                 "additional_peak_estimate_mib": estimated, "required_available_mib": required}
        if snapshot["available_mib"] < required:
            raise ResourceAdmissionError(
                f"Admission {owner} refusée : {snapshot['available_mib']:.0f} Mio disponibles, "
                f"{required} Mio requis (pic prévu {estimated} + réserve {self.reserve_mib}).",
                snapshot,
            )

    @asynccontextmanager
    async def interactive(self):
        self.begin_interactive()
        try:
            yield self.snapshot()
        finally:
            self.finish_interactive()

    @asynccontextmanager
    async def ingestion(self):
        if self.should_checkpoint():
            raise ResourceAdmissionError("Import en pause ; reprise explicite requise.", self.snapshot())
        async with self._heavy:
            if self.should_checkpoint():
                raise ResourceAdmissionError("Import en pause ; reprise explicite requise.", self.snapshot())
            if self.before_ingestion:
                await self.before_ingestion()
            if self.should_checkpoint():
                raise ResourceAdmissionError("Import en pause ; reprise explicite requise.", self.snapshot())
            self._admit("ingestion")
            self._owner = "ingestion"
            self._mode = "ingestion"
            try:
                yield self.snapshot()
            finally:
                self._owner = None
                self._mode = "interactive"

    @asynccontextmanager
    async def generation(self):
        self._generation_requests += 1
        if self._owner == "ingestion":
            self._request_checkpoint()
        try:
            async with self._heavy:
                loaded = await self.before_generation() if self.before_generation else None
                self._admit("generation", loaded)
                self._owner = "generation"
                self._mode = "generation"
                owner_task = asyncio.current_task()
                violation = None

                async def protect_reserve():
                    nonlocal violation
                    while True:
                        await asyncio.sleep(0.5)
                        sample = self.snapshot()
                        if sample["available_mib"] < self.reserve_mib:
                            violation = ResourceAdmissionError("Réserve hôte menacée pendant la génération ; requête annulée.", sample)
                            owner_task.cancel()
                            return

                monitor = asyncio.create_task(protect_reserve(), name="generation-host-reserve")
                try:
                    yield self.snapshot()
                except asyncio.CancelledError:
                    if violation is not None:
                        if self.after_resource_violation:
                            await self.after_resource_violation()
                        raise violation from None
                    raise
                finally:
                    monitor.cancel()
                    with suppress(asyncio.CancelledError):
                        await monitor
                    self._owner = None
                    self._mode = "interactive"
        finally:
            self._generation_requests -= 1


async def monitor_resources(path: Path, governor: ResourceGovernor, stop: asyncio.Event) -> None:
    """Trace JSONL hôte/processus, sans contenu documentaire ni secret."""
    path.parent.mkdir(parents=True, exist_ok=True)
    interval = max(0.25, float(governor.settings.get("sampling_interval_seconds", 1)))
    with path.open("a", encoding="utf-8") as stream:
        while not stop.is_set():
            sample = governor.snapshot()
            children = []
            for child in psutil.Process(os.getpid()).children(recursive=True):
                try:
                    info = child.memory_info()
                    children.append({"pid": child.pid, "rss_mib": round(info.rss / 1048576, 2),
                                     "private_mib": round(getattr(info, "private", info.rss) / 1048576, 2),
                                     "cpu_seconds": sum(child.cpu_times()[:2])})
                except psutil.Error:
                    continue
            sample["children"] = children
            sample["monotonic_seconds"] = time.monotonic()
            stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
            stream.flush()
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass
