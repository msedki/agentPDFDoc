"""Admission et coordination des travaux CPU, sans arrêter de processus étrangers."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from contextlib import asynccontextmanager, contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from .artifacts import ROOT

# Commun à toutes les instances lancées depuis cette racine (principale,
# restaurée, pilote de calibration) : un seul chargement lourd par poste.
HOST_HEAVY_LOCK = ROOT / ".runtime/control/host-heavy.lock"


class ResourceAdmissionError(RuntimeError):
    """Le travail demandé ne peut pas préserver la réserve mémoire hôte."""

    def __init__(self, message: str, snapshot: dict[str, Any], code: str = "resource_admission_denied"):
        super().__init__(message)
        self.snapshot = snapshot
        self.code = code


class HostHeavyLockBusy(ResourceAdmissionError):
    """Un autre handle de l'hôte (autre processus ou gouverneur) détient le verrou lourd."""

    def __init__(self, path: Path, owner: str, holder: dict[str, Any] | None):
        # Message court pour l'interface ; chemin et détenteur restent dans le snapshot de diagnostic.
        who = f"{holder.get('owner')}, PID {holder.get('pid')}" if isinstance(holder, dict) else "détenteur non identifié"
        super().__init__(f"Un travail lourd est déjà en cours sur ce poste ({who}) ; réessayer après sa fin.",
                         {"host_heavy_lock": str(path), "holder": holder, "requested_by": owner},
                         code="host_heavy_lock_busy")


class HostHeavyLock:
    """Byte-lock Windows non bloquant ; le système le libère si le détenteur meurt."""

    def __init__(self, handle, path: Path, owner: str):
        self._handle, self.path, self.owner = handle, path, owner

    def release(self) -> None:
        import msvcrt

        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        try:
            with suppress(OSError):
                handle.truncate(1)
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()  # Libère aussi le verrou si le déverrouillage explicite a échoué.

    def __enter__(self) -> HostHeavyLock:
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _lock_holder(path: Path) -> dict[str, Any] | None:
    # L'octet 0 verrouillé est illisible pour les autres handles ; l'identité suit.
    try:
        with path.open("rb") as stream:
            stream.seek(1)
            return json.loads(stream.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def acquire_host_heavy_lock(owner: str, path: Path | None = None) -> HostHeavyLock:
    """Prendre sans attendre le verrou lourd de l'hôte, ou lever HostHeavyLockBusy."""
    import msvcrt

    path = Path(path or HOST_HEAVY_LOCK)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise HostHeavyLockBusy(path, owner, _lock_holder(path)) from None
    try:
        handle.truncate(1)
        handle.write(json.dumps({"owner": owner, "pid": os.getpid(),
                                 "since_utc": datetime.now(UTC).isoformat()}).encode("utf-8"))
        handle.flush()
    except OSError:
        pass  # Identité informative seulement ; le verrou reste tenu.
    return HostHeavyLock(handle, path, owner)


def host_heavy_lock_available(path: Path | None = None) -> bool:
    """Sonde sans effet durable : vrai si aucun autre handle ne tient le verrou lourd.

    Un verrou libéré proprement laisse un fichier d'un octet ; seul un contenu plus
    long (détenteur actif ou arrêté brutalement) justifie un essai de verrouillage.
    """
    import msvcrt

    path = Path(path or HOST_HEAVY_LOCK)
    try:
        if path.stat().st_size <= 1:
            return True
    except FileNotFoundError:
        return True
    try:
        handle = path.open("r+b")
    except OSError:
        return False
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False
    try:
        handle.truncate(1)  # Identité périmée d'un détenteur disparu.
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        handle.close()
    return True


def admission_requirement(settings: dict[str, Any], owner: str, loaded: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pic additionnel prévu et mémoire disponible requise, réserve hôte incluse."""
    reserve = int(settings.get("host_available_min_mib", 1536))
    estimate_key = (
        "initial_llm_load_peak_estimate_mib" if owner == "generation"
        else "initial_parser_peak_estimate_mib"
    )
    resident = owner == "generation" and loaded is not None and loaded.get("loaded") is True
    estimated = (int(loaded["additional_peak_mib"]) if resident and loaded is not None else
                 int(settings.get(estimate_key, 6144 if owner == "generation" else 4096)))
    if estimated < 0:
        raise ValueError("Estimation de mémoire additionnelle négative")
    required = max(0 if resident else int(settings.get("admit_heavy_min_available_mib", 3072)), estimated + reserve)
    return {"owner": owner, "resident_model": resident, "additional_peak_estimate_mib": estimated,
            "host_reserve_mib": reserve, "required_available_mib": required}


def host_sample(disk_root: Path, process: psutil.Process | None = None) -> dict[str, Any]:
    """Mesures hôte et processus courant seulement, sans état de lease."""
    memory = psutil.virtual_memory()
    process = process or psutil.Process()
    info = process.memory_info()
    private = getattr(info, "private", None)
    root = Path(disk_root)
    while not root.exists() and root != root.parent:
        root = root.parent
    return {
        "utc": datetime.now(UTC).isoformat(),
        "available_mib": round(memory.available / 1048576, 2),
        "total_mib": round(memory.total / 1048576, 2),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "disk_free_mib": round(shutil.disk_usage(root).free / 1048576, 2),
        "process_rss_mib": round(info.rss / 1048576, 2),
        "process_private_mib": None if private is None else round(private / 1048576, 2),
        "memory_method": "Windows working set and private bytes; shared pages not summed",
    }


class ResourceGovernor:
    """Un lease lourd ; la priorité interactive demande un checkpoint durable.

    Le worker observe should_checkpoint() ou le fichier pause. Aucun délai
    nominal ne tue le worker. La reprise d'un import exige une action explicite.
    Le lease lourd prend aussi le verrou fichier de l'hôte (HOST_HEAVY_LOCK).
    """

    def __init__(self, settings: dict[str, Any] | None = None, host_lock_path: Path | None = None):
        profile = settings or {}
        self.settings = profile.get("resources", profile)
        app = profile.get("app", {})
        self.data_dir = Path(app.get("data_dir", ".runtime/data")).resolve()
        self.reserve_mib = int(self.settings.get("host_available_min_mib", 1536))
        self.admit_min_mib = int(self.settings.get("admit_heavy_min_available_mib", 3072))
        auto_resume = (self.settings.get("scheduling") or {}).get("auto_resume_ingestion", False)
        if auto_resume is not False:
            raise ValueError("resources.scheduling.auto_resume_ingestion doit valoir false : aucune reprise "
                             "automatique sans essai anti-ping-pong documenté (D07).")
        self.auto_resume_ingestion = False
        self.host_lock_path = Path(host_lock_path) if host_lock_path else HOST_HEAVY_LOCK
        self._host_lock: HostHeavyLock | None = None
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
        return {
            **host_sample(self.data_dir),
            "mode": self._mode,
            "heavy_owner": self._owner,
            "host_heavy_lock_held": self._host_lock is not None,
            "pause_requested": self.should_checkpoint(),
            "host_reserve_mib": self.reserve_mib,
            "auto_resume_ingestion": self.auto_resume_ingestion,
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
        # Verrou tenu ailleurs (autre instance, calibration) : le job attend en file au lieu d'être mis en pause.
        return (not self.should_checkpoint() and not self._heavy.locked()
                and host_heavy_lock_available(self.host_lock_path))

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
        requirement = admission_requirement(self.settings, owner, loaded)
        estimated, required = requirement["additional_peak_estimate_mib"], requirement["required_available_mib"]
        snapshot["admission"] = {key: requirement[key] for key in
                                 ("owner", "resident_model", "additional_peak_estimate_mib", "required_available_mib")}
        if snapshot["available_mib"] < required:
            raise ResourceAdmissionError(
                f"Admission {owner} refusée : {snapshot['available_mib']:.0f} Mio disponibles, "
                f"{required} Mio requis (pic prévu {estimated} + réserve {self.reserve_mib}).",
                snapshot,
            )

    @contextmanager
    def _host_heavy(self, owner: str):
        try:
            lock = acquire_host_heavy_lock(owner, self.host_lock_path)
        except HostHeavyLockBusy as busy:
            # Classe de base : l'API reconnaît ResourceAdmissionError par son nom (pause, message).
            raise ResourceAdmissionError(str(busy), {**self.snapshot(), **busy.snapshot,
                                         "admission": {"owner": owner, "code": busy.code}}, code=busy.code) from None
        self._host_lock = lock
        try:
            yield lock
        finally:
            self._host_lock = None
            lock.release()

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
            with self._host_heavy("ingestion"):
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

    async def _admit_generation(self, loaded: dict[str, Any] | None, on_wait) -> None:
        """Admission bornée : la mémoire hôte fluctue avec la charge étrangère ; la réserve reste intacte."""
        deadline = time.monotonic() + float(self.settings.get("generation_admission_wait_seconds", 0))
        announced = False
        while True:
            try:
                self._admit("generation", loaded)
                return
            except ResourceAdmissionError as refused:
                if time.monotonic() >= deadline:
                    raise
                if on_wait is not None and not announced:
                    announced = True
                    on_wait(refused.snapshot)
            await asyncio.sleep(2)

    @asynccontextmanager
    async def generation(self, on_wait=None):
        self._generation_requests += 1
        if self._owner == "ingestion":
            self._request_checkpoint()
        try:
            async with self._heavy:
                with self._host_heavy("generation"):
                    loaded = await self.before_generation() if self.before_generation else None
                    await self._admit_generation(loaded, on_wait)
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
