import asyncio

import pytest

from services.runtime.resources import ResourceAdmissionError, ResourceGovernor


@pytest.fixture
def governor(tmp_path):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
        "initial_llm_load_peak_estimate_mib": 1, "initial_parser_peak_estimate_mib": 1,
    }})
    item._admit = lambda *args: None
    return item


@pytest.mark.asyncio
async def test_generation_waits_for_durable_ingestion_checkpoint(governor):
    acquired = asyncio.Event()
    release = asyncio.Event()
    generation_entered = asyncio.Event()

    async def ingest():
        async with governor.ingestion():
            acquired.set()
            await release.wait()

    async def generate():
        async with governor.generation():
            generation_entered.set()

    parser = asyncio.create_task(ingest())
    await acquired.wait()
    chat = asyncio.create_task(generate())
    await asyncio.sleep(0)
    assert governor.should_checkpoint()
    assert governor.pause_path.exists()
    assert not generation_entered.is_set()
    release.set()
    await asyncio.gather(parser, chat)
    assert generation_entered.is_set()
    assert not governor.allow_ingestion()
    governor.resume_ingestion()
    assert governor.allow_ingestion()


@pytest.mark.asyncio
async def test_cancelling_waiter_does_not_release_other_heavy_owner(governor):
    async with governor.ingestion():
        waiter = asyncio.create_task(_enter_generation(governor))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert governor.snapshot()["heavy_owner"] == "ingestion"
        assert governor._generation_requests == 0
    governor.resume_ingestion()
    async with governor.generation():
        assert governor.snapshot()["heavy_owner"] == "generation"


async def _enter_generation(governor):
    async with governor.generation():
        raise AssertionError("Lease ingestion occupé")


def test_admission_preserves_host_reserve_and_reports_current_sample(tmp_path, monkeypatch):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "initial_llm_load_peak_estimate_mib": 6144,
    }})
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": 7000})
    with pytest.raises(ResourceAdmissionError) as caught:
        item._admit("generation")
    assert caught.value.snapshot["available_mib"] == 7000
    assert "7680" in str(caught.value)


def test_resident_model_counts_only_additional_peak_without_removing_reserve(tmp_path, monkeypatch):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
        "initial_llm_load_peak_estimate_mib": 6144,
    }})
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": 2300})
    item._admit("generation", {"loaded": True, "additional_peak_mib": 512})
    with pytest.raises(ResourceAdmissionError):
        item._admit("generation", {"loaded": False})
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": 2000})
    with pytest.raises(ResourceAdmissionError) as caught:
        item._admit("generation", {"loaded": True, "additional_peak_mib": 512})
    assert caught.value.snapshot["admission"]["required_available_mib"] == 2048


@pytest.mark.asyncio
async def test_residency_probe_runs_under_exclusive_heavy_lease(tmp_path, monkeypatch):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}})
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": 2300})

    async def probe():
        assert item._heavy.locked()
        return {"loaded": True, "additional_peak_mib": 512}

    item.before_generation = probe
    async with item.generation():
        assert item._owner == "generation"
    assert item._owner is None


@pytest.mark.asyncio
async def test_memory_drop_cancels_only_own_generation_and_releases_lease(tmp_path, monkeypatch):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "initial_llm_load_peak_estimate_mib": 1,
    }})
    available = 8000
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": available})
    with pytest.raises(ResourceAdmissionError, match="pendant la génération"):
        async with item.generation():
            available = 1500
            await asyncio.sleep(1)
    assert not item._heavy.locked()
    assert item._owner is None
    assert item._generation_requests == 0
