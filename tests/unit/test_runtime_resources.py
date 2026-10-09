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


@pytest.mark.parametrize("owner,loaded,required,estimated,label,action", [
    ("generation", None, 4992, 3456, "la génération de la réponse", "relancez la question"),
    ("ingestion", None, 3840, 2304, "l'indexation du document", "reprenez l'indexation depuis le Suivi"),
    ("generation", {"loaded": True, "additional_peak_mib": 512}, 2048, 512,
     "la génération de la réponse", "relancez la question"),
])
def test_admission_message_is_human_without_changing_snapshot_or_threshold(
        tmp_path, monkeypatch, owner, loaded, required, estimated, label, action):
    """Sonde mémoire synthétique : aucun bail, modèle ou processus hôte acquis."""
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {
        "host_available_min_mib": 1536, "admit_heavy_min_available_mib": 3072,
        "initial_llm_load_peak_estimate_mib": 3456, "initial_parser_peak_estimate_mib": 2304,
    }}, host_lock_path=tmp_path / "host-heavy.lock")
    snapshot = {"available_mib": required - 0.6, "synthetic_probe": "PRIVATE_SNAPSHOT_SENTINEL"}
    monkeypatch.setattr(item, "snapshot", lambda: dict(snapshot))
    with pytest.raises(ResourceAdmissionError) as refused:
        item._admit(owner, loaded)
    assert refused.value.code == "resource_admission_denied"
    assert refused.value.snapshot == {**snapshot, "admission": {
        "owner": owner, "resident_model": loaded is not None,
        "additional_peak_estimate_mib": estimated, "required_available_mib": required,
    }}
    assert "PRIVATE_SNAPSHOT_SENTINEL" not in str(refused.value)
    assert str(refused.value) == (
        f"Impossible de démarrer {label} : {required - 1} Mio disponibles, {required} Mio requis "
        f"(pic prévu {estimated} + réserve 1536). Libérez de la mémoire sur le poste, puis {action}."
    )
    snapshot["available_mib"] = required
    assert item._admit(owner, loaded) is None
    assert item._owner is None and not item._heavy.locked() and item._host_lock is None
    assert not item.host_lock_path.exists() and not item.pause_path.exists()


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
async def test_generation_awaits_the_resource_wait_callback_before_admitting(tmp_path, monkeypatch):
    item = _admission_governor(tmp_path, 30, monkeypatch, [4723, 5100])
    waits = []
    monkeypatch.setattr("services.runtime.resources.asyncio.sleep", _instant_sleep)

    async def waiting(sample):
        await asyncio.to_thread(waits.append, sample)

    async with item.generation(on_wait=waiting):
        assert len(waits) == 1
    assert waits[0]["admission"]["required_available_mib"] == 3456 + 1536


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


def test_memory_measures_are_labelled_by_platform(tmp_path):
    import sys

    import psutil

    from services.runtime.resources import host_sample, linux_memory_mib

    sample = host_sample(tmp_path)
    assert sample["process_rss_mib"] > 0
    if sys.platform == "win32":
        assert sample["memory_method"].startswith("Windows working set and private bytes")
        assert "process_pss_mib" not in sample and "process_uss_mib" not in sample
    else:
        # Aucune « private bytes » sous Linux : RSS, USS, et PSS quand le noyau fournit smaps_rollup (4.14 ou plus récent).
        assert sample["process_private_mib"] is None
        assert sample["memory_method"] == ("Linux RSS/USS/PSS" if sample["process_pss_mib"] is not None else "Linux RSS/USS")
        assert 0 < sample["process_uss_mib"] <= sample["process_rss_mib"]
        measured = linux_memory_mib(psutil.Process())
        assert set(measured) == {"rss_mib", "uss_mib", "pss_mib"}


@pytest.mark.asyncio
@pytest.mark.parametrize("unload", [True, False])
async def test_llm_unload_before_ingestion_follows_the_profile_key(tmp_path, unload):
    # C6 : resources.unload_llm_before_ingestion (vrai dans le profil livré) commande le déchargement d'Ollama.
    item = ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {"unload_llm_before_ingestion": unload}},
                            host_lock_path=tmp_path / "host-heavy.lock")
    item._admit = lambda *args: None
    calls = []

    async def unload_llm():
        calls.append("unload")

    item.before_ingestion = unload_llm
    async with item.ingestion():
        pass
    assert calls == (["unload"] if unload else [])


def test_delivered_profile_unloads_llm_and_starts_interactive(tmp_path):
    import yaml

    from services.runtime.artifacts import ROOT

    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    item = ResourceGovernor({**profile, "app": {**profile["app"], "data_dir": str(tmp_path)}}, host_lock_path=tmp_path / "l")
    assert item.unload_llm_before_ingestion is True and item.snapshot()["mode"] == "interactive"
    with pytest.raises(ValueError, match="initial_mode doit valoir interactive"):
        ResourceGovernor({"app": {"data_dir": str(tmp_path)}, "resources": {"scheduling": {"initial_mode": "ingestion"}}})
