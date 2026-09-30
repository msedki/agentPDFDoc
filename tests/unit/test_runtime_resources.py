import asyncio

import pytest

from services.runtime.resources import ResourceAdmissionError, ResourceGovernor


@pytest.fixture
def governor(tmp_path):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
        "initial_llm_load_peak_estimate_mib": 1, "initial_parser_peak_estimate_mib": 1,
    }}, host_lock_path=tmp_path / "host-heavy.lock")
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
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}}, host_lock_path=tmp_path / "host-heavy.lock")
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
    }}, host_lock_path=tmp_path / "host-heavy.lock")
    available = 8000
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": available})
    with pytest.raises(ResourceAdmissionError, match="pendant la génération"):
        async with item.generation():
            available = 1500
            await asyncio.sleep(1)
    assert not item._heavy.locked()
    assert item._owner is None
    assert item._generation_requests == 0


@pytest.mark.parametrize("value", [True, "true", 1])
def test_auto_resume_ingestion_enabled_in_profile_is_refused(tmp_path, value):
    with pytest.raises(ValueError, match="anti-ping-pong"):
        ResourceGovernor({"app": {"data_dir": str(tmp_path)},
                          "resources": {"scheduling": {"auto_resume_ingestion": value}}})


def test_auto_resume_ingestion_is_read_from_delivered_profile(tmp_path):
    import yaml

    from services.runtime.artifacts import ROOT

    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    assert profile["resources"]["scheduling"]["auto_resume_ingestion"] is False
    item = ResourceGovernor({**profile, "app": {**profile["app"], "data_dir": str(tmp_path)}},
                            host_lock_path=tmp_path / "host-heavy.lock")
    snapshot = item.snapshot()
    assert snapshot["auto_resume_ingestion"] is False and snapshot["host_heavy_lock_held"] is False
    assert ResourceGovernor({"app": {"data_dir": str(tmp_path)}}).auto_resume_ingestion is False


def test_admission_requirement_matches_governor_refusal(tmp_path, monkeypatch):
    from services.runtime.resources import admission_requirement

    settings = {"host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
                "initial_llm_load_peak_estimate_mib": 3456, "initial_parser_peak_estimate_mib": 2304}
    assert admission_requirement(settings, "generation")["required_available_mib"] == 4992
    assert admission_requirement(settings, "ingestion")["required_available_mib"] == 3840
    assert admission_requirement(settings, "generation", {"loaded": True, "additional_peak_mib": 512})["required_available_mib"] == 2048
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": settings})
    monkeypatch.setattr(item, "snapshot", lambda: {"available_mib": 4991})
    with pytest.raises(ResourceAdmissionError) as caught:
        item._admit("generation")
    assert caught.value.code == "resource_admission_denied"
    assert caught.value.snapshot["admission"]["required_available_mib"] == 4992


def _admission_governor(tmp_path, wait_seconds, monkeypatch, sleeps):
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
        "initial_llm_load_peak_estimate_mib": 3456, "generation_admission_wait_seconds": wait_seconds,
    }}, host_lock_path=tmp_path / "host-heavy.lock")
    samples = iter(sleeps)

    def snapshot():
        return {"available_mib": next(samples, sleeps[-1]), "heavy_owner": None}

    monkeypatch.setattr(item, "snapshot", snapshot)
    return item


@pytest.mark.asyncio
async def test_generation_admission_waits_for_memory_then_admits(tmp_path, monkeypatch):
    item = _admission_governor(tmp_path, 30, monkeypatch, [4723, 4800, 5100])
    waits = []
    monkeypatch.setattr("services.runtime.resources.asyncio.sleep", _instant_sleep)
    async with item.generation(on_wait=waits.append):
        pass
    # Un seul état d'attente annoncé, avec le besoin réel ; la réserve n'est pas abaissée.
    assert len(waits) == 1 and waits[0]["admission"]["required_available_mib"] == 3456 + 1536


@pytest.mark.asyncio
async def test_generation_admission_without_wait_refuses_immediately(tmp_path, monkeypatch):
    item = _admission_governor(tmp_path, 0, monkeypatch, [4723])
    waits = []
    with pytest.raises(ResourceAdmissionError) as refused:
        async with item.generation(on_wait=waits.append):
            pass
    assert refused.value.code == "resource_admission_denied" and waits == []
    assert item._generation_requests == 0


async def _instant_sleep(_seconds):
    return None
