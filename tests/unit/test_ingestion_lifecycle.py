"""The deterministic iterator fix drains on early close without parsing twice."""

from types import SimpleNamespace

import pytest

from services.ingestion.lifecycle import draining_results


def test_early_close_drains_raw_results_without_creating_more_pages():
    steps, pages, events = [], [], []
    telemetry = {"yielded_page_numbers": [], "drained_page_numbers": [], "iterator_exhausted": False}

    def raw_results():
        for number in [1, 2, 3]:
            steps.append(number)
            yield SimpleNamespace(page_number=number)
        steps.append("end")

    def make_page(result):
        pages.append(result.page_number)
        return result.page_number

    iterator = draining_results(raw_results(), make_page, telemetry, lambda event, **fields: events.append((event, fields)))
    assert next(iterator) == 1
    iterator.close()
    assert steps == [1, 2, 3, "end"]
    assert pages == [1]
    assert telemetry == {"yielded_page_numbers": [1], "drained_page_numbers": [2, 3], "iterator_exhausted": True}
    assert [event for event, _ in events] == ["page_yield", "drain_start", "page_drain", "page_drain", "iterator_exhausted"]


def test_natural_exhaustion_does_not_replay_results():
    telemetry = {"yielded_page_numbers": [], "drained_page_numbers": [], "iterator_exhausted": False}
    results = iter([SimpleNamespace(page_number=4), SimpleNamespace(page_number=5)])
    assert list(draining_results(results, lambda result: result.page_number, telemetry, lambda *args, **kwargs: None)) == [4, 5]
    assert telemetry == {"yielded_page_numbers": [4, 5], "drained_page_numbers": [], "iterator_exhausted": True}


def test_raw_failure_during_drain_is_not_reported_as_exhaustion():
    telemetry = {"yielded_page_numbers": [], "drained_page_numbers": [], "iterator_exhausted": False}

    def raw_results():
        yield SimpleNamespace(page_number=1)
        raise RuntimeError("isolated iterator failure")

    iterator = draining_results(raw_results(), lambda result: result.page_number, telemetry, lambda *args, **kwargs: None)
    assert next(iterator) == 1
    with pytest.raises(RuntimeError, match="isolated iterator failure"):
        iterator.close()
    assert telemetry["iterator_exhausted"] is False
