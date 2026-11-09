"""Revision campaign boundaries, with explicit lightweight application doubles.

No native service, model, embedding, or product ingestion is launched. Loader
tests use fresh Python processes and minimal named revision fixtures. Campaign
tests exercise the real harness with controlled admission and terminal states.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "tools/qualification/revision_campaign.py"
SPEC = importlib.util.spec_from_file_location("revision_campaign_under_test", HARNESS)
assert SPEC and SPEC.loader
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def revision_fixture(path, identity):
    (path / "tools/qualification").mkdir(parents=True)
    (path / "services/api").mkdir(parents=True)
    (path / "services/__init__.py").write_text("")
    (path / "services/api/__init__.py").write_text("")
    (path / "services/api/marker.py").write_text(f"IDENTITY = {identity!r}\n")
    helper = path / "tools/qualification/enhanced_campaign.py"
    helper.write_text(
        "import sys\nfrom pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[2]\n"
        "sys.path.insert(0, str(ROOT))\n"
        "from services.api.marker import IDENTITY\n"
    )
    return helper


def loader_probe(root, prelude=""):
    code = (
        "import importlib.util,json,sys,types\nfrom pathlib import Path\n"
        "spec=importlib.util.spec_from_file_location('probe',sys.argv[1])\n"
        "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n"
        + prelude
        + "\ntry:\n"
        " result=module.load_application(Path(sys.argv[2]))\n"
        " print(json.dumps({'identity':result.IDENTITY,'origin':sys.modules['services.api.marker'].__file__}))\n"
        "except Exception as error:\n"
        " print(json.dumps({'error':type(error).__name__,'message':str(error)}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(HARNESS), str(root)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return json.loads(result.stdout)


def test_loader_uses_selected_revision_even_when_another_is_on_search_path(tmp_path):
    selected, other = tmp_path / "selected", tmp_path / "other"
    revision_fixture(selected, "selected-revision")
    revision_fixture(other, "wrong-revision")
    result = loader_probe(selected, f"sys.path.insert(0, {str(other)!r})\n")
    assert result["identity"] == "selected-revision"
    assert Path(result["origin"]).is_relative_to(selected)


def test_loader_rejects_an_already_imported_application(tmp_path):
    revision_fixture(tmp_path / "revision", "selected")
    result = loader_probe(tmp_path / "revision", "sys.modules['services']=types.ModuleType('services')\n")
    assert result["error"] == "RuntimeError"
    assert "déjà importée" in result["message"]


def test_loader_rejects_an_import_from_outside_the_selected_root(tmp_path):
    selected = tmp_path / "selected"
    helper = revision_fixture(selected, "selected")
    helper.write_text(helper.read_text() + (
        "import types\nforeign=types.ModuleType('services.foreign')\n"
        f"foreign.__file__={str(tmp_path / 'foreign.py')!r}\n"
        "sys.modules['services.foreign']=foreign\n"
    ))
    result = loader_probe(selected)
    assert result["error"] == "RuntimeError"
    assert "extérieur" in result["message"]


@pytest.mark.parametrize("requested", [["unknown"], ["a", "a"]])
def test_case_selection_rejects_unknown_or_duplicate_requests(requested):
    with pytest.raises(ValueError, match="inconnue ou dupliquée"):
        harness.select_cases({"cases": [{"id": "a"}, {"id": "b"}]}, requested)


def test_case_selection_preserves_manifest_order_and_rejects_duplicate_manifest_ids():
    cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert harness.select_cases({"cases": cases}, ["c", "a"]) == [cases[0], cases[2]]
    with pytest.raises(ValueError, match="dupliqués"):
        harness.select_cases({"cases": [cases[0], cases[0]]}, [])


@pytest.fixture
def controlled_campaign(tmp_path, monkeypatch):
    """Named application double; actual harness/file I/O, no product runtime."""
    for name in ("RAG_DATA_DIR", "RAG_DB_PATH"):
        monkeypatch.delenv(name, raising=False)
    profile = {
        "llm": {"model": "qwen3-4b-enhanced:q4km", "seed": 0, "accelerator": "auto"},
        "enhanced": dict.fromkeys(
            ("preserve_evidence", "structural_reranking", "answer_contract", "complementary_retrieval"), True),
        "app": {"data_dir": "old-data"}, "sqlite": {"path": "old.sqlite3"}, "trace": {},
    }
    settings = SimpleNamespace(profile=profile, value=lambda section, key: profile.get(section, {}).get(key))
    app_root = tmp_path / "application"
    app_root.mkdir()
    source = app_root / "controlled_source.py"
    source.write_text("IDENTITY = 'controlled-double'\n")
    args = SimpleNamespace(
        inputs=tmp_path / "inputs.json", profile=tmp_path / "profile.json", output=tmp_path / "output",
        application_root=app_root, revision_label="iteration1", case_id=[], service_pid=[],
    )
    dataset = {"documents": [], "cases": [
        {"id": "a", "question": "Question A", "mode": "factual"},
        {"id": "b", "question": "Question B", "mode": "factual"},
    ]}
    save(args.profile, profile)
    monitors, requests, indexed = [], [], []

    class ControlledMemory:
        def __init__(self, path, pids):
            self.label = "initialization"
            self.peaks = {}
            self.closed = False
            self.started = False
            self.thread = SimpleNamespace(start=lambda: setattr(self, "started", True))
            monitors.append(self)

        def sample(self):
            self.peaks[self.label] = {"samples": 1, "rss_sum_peak_mib": 0}

        def close(self):
            self.closed = True

    class ControlledQueries:
        def __init__(self):
            self.tasks = {}
            self.states = ["done", "done"]
            self.raise_at = None
            self.after_create = None
            self.cancelled = []

        async def create_async(self, request):
            requests.append(request)
            if len(requests) == self.raise_at:
                raise RuntimeError("controlled admission failure")
            query_id = f"q{len(requests)}"
            self.tasks[query_id] = asyncio.create_task(asyncio.sleep(0))
            if self.after_create:
                self.after_create()
            return {"query_id": query_id}

        async def cancel_async(self, query_id):
            self.cancelled.append(query_id)
            self.tasks[query_id].cancel()
            self.states[int(query_id[1:]) - 1] = "cancelled"

        def run_detail(self, query_id):
            return {"id": query_id, "state": self.states[int(query_id[1:]) - 1],
                    "answer": "controlled result", "metrics": {"model_called": False, "elapsed_ms": 0}}

    queries = ControlledQueries()
    db = SimpleNamespace(
        rows=lambda sql, params: [{"source_json": '{"source_id":"controlled-citation"}'}]
        if "citations" in sql else [{"type": "controlled-event", "query_id": params[0]}],
        import_original=lambda *values: {"document_id": "d", "version_id": "v", "job_id": "j"},
        one=lambda *values: {"active_generation_id": "g"},
    )

    async def index(*values):
        indexed.append(values)
        return "g"

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = SimpleNamespace(router=SimpleNamespace(lifespan_context=lifespan),
                          state=SimpleNamespace(db=db, indexer=SimpleNamespace(index=index), queries=queries))
    scope = SimpleNamespace(model_dump=lambda: {"kind": "documents", "documentIds": []})

    def freeze_code(output):
        save(output / "code-manifest.json", {"files": {source.name: digest(source)}})
        return {"snapshot_kind": "controlled_test_double"}

    application = SimpleNamespace(
        Settings=SimpleNamespace(load=lambda path: settings),
        file_sha256=digest, fingerprint=lambda value: hashlib.sha256(
            json.dumps(value, sort_keys=True).encode()).hexdigest(),
        save=save, freeze_code=freeze_code, MemorySampler=ControlledMemory,
        create_app=lambda **kwargs: app, scope_for=lambda *values: scope,
        QueryRequest=lambda **values: values,
        extraction_content_hash=lambda value: "controlled-extraction",
    )
    # Replace only the harness dependency; globally patching subprocess would
    # also corrupt platform.processor() and other independent library probes.
    monkeypatch.setattr(harness, "subprocess", SimpleNamespace(
        check_output=lambda *values, **kwargs: b"controlled git double\n"))
    monkeypatch.setattr(harness, "version", lambda name: "controlled-version-double")

    def run():
        args.inputs.write_text(json.dumps(dataset), encoding="utf-8")
        return asyncio.run(harness.campaign(args, application))

    return SimpleNamespace(args=args, application=application, dataset=dataset, settings=settings, run=run,
                           monitors=monitors, requests=requests, queries=queries, source=source, indexed=indexed)


def test_campaign_preserves_product_error_terminal_and_next_case_without_retry(controlled_campaign):
    state = controlled_campaign
    state.queries.states = ["error", "done"]
    state.run()
    first = read(state.args.output / "a-iteration1-0.json")
    second = read(state.args.output / "b-iteration1-0.json")
    assert [first["run"]["state"], second["run"]["state"]] == ["error", "done"]
    assert [request["question"] for request in state.requests] == ["Question A", "Question B"]
    assert all("conversation_id" not in request for request in state.requests)
    assert first["judgment"] == {"method": "unreviewed"}
    assert first["citations"] == [{"source_id": "controlled-citation"}]
    assert first["events"][0]["query_id"] == "q1"
    assert not (state.args.output / "block-failure.json").exists()
    assert state.monitors[0].closed


def test_campaign_freezes_inputs_harness_flags_and_isolated_storage(controlled_campaign):
    state = controlled_campaign
    state.args.case_id = ["b", "a"]
    state.run()
    frozen = read(state.args.output / "protocol-frozen.json")
    assert frozen["case_order"] == ["a", "b"]
    assert frozen["dataset"] == state.dataset
    assert frozen["inputs_sha256"] == digest(state.args.inputs)
    assert frozen["profile_file_sha256"] == digest(state.args.profile)
    assert frozen["measurement_harness_sha256"] == digest(HARNESS)
    assert (state.args.output / "measurement-harness.py").read_bytes() == HARNESS.read_bytes()
    assert frozen["profile"]["app"]["data_dir"] == str(state.args.output / "data")
    assert frozen["profile"]["sqlite"]["path"] == str(state.args.output / "data/app.sqlite3")
    assert frozen["profile"]["llm"]["accelerator"] == "cpu"
    assert all(frozen["profile"]["enhanced"].values())
    assert read(state.args.output / "source-stability.json")["changed_since_freeze"] == []


@pytest.mark.parametrize("variable", ["RAG_DATA_DIR", "RAG_DB_PATH"])
def test_campaign_rejects_storage_environment_overrides(controlled_campaign, monkeypatch, variable):
    state = controlled_campaign
    monkeypatch.setenv(variable, "outside-owned-campaign")
    with pytest.raises(ValueError, match="isolation"):
        state.run()
    assert not state.monitors and not state.requests


@pytest.mark.parametrize("change", ["model", "enhanced"])
def test_campaign_rejects_wrong_generator_or_disabled_mechanisms(controlled_campaign, change):
    state = controlled_campaign
    if change == "model":
        state.settings.profile["llm"]["model"] = "other-model"
    else:
        state.settings.profile["enhanced"]["answer_contract"] = False
    with pytest.raises(ValueError):
        state.run()
    assert not state.monitors and not state.requests


def test_campaign_does_not_reuse_or_overwrite_an_output_directory(controlled_campaign):
    state = controlled_campaign
    state.args.output.mkdir()
    sentinel = state.args.output / "previous-evidence.json"
    sentinel.write_bytes(b"preserve previous bytes\n")
    with pytest.raises(FileExistsError):
        state.run()
    assert sentinel.read_bytes() == b"preserve previous bytes\n"
    assert not state.requests


def test_creation_failure_closes_monitor_and_keeps_explicit_block_error(controlled_campaign):
    state = controlled_campaign

    def fail(**kwargs):
        raise RuntimeError("controlled application creation failure")

    state.application.create_app = fail
    with pytest.raises(RuntimeError, match="creation failure"):
        state.run()
    assert state.monitors[0].closed
    failure = read(state.args.output / "block-failure.json")
    assert failure["active_attempt"] is None
    assert failure["error_type"] == "RuntimeError"
    assert "not an inferred application terminal" in failure["kind"]


@pytest.mark.parametrize("phase", ["scope", "admission"])
def test_attempt_failure_keeps_completed_results_and_does_not_invent_terminal(controlled_campaign, phase):
    state = controlled_campaign
    if phase == "admission":
        state.queries.raise_at = 2
    else:
        original = state.application.scope_for

        def scope_for(case, *args):
            if case["id"] == "b":
                raise RuntimeError("controlled scope failure")
            return original(case, *args)

        state.application.scope_for = scope_for
    with pytest.raises(RuntimeError, match="controlled"):
        state.run()
    assert read(state.args.output / "a-iteration1-0.json")["run"]["state"] == "done"
    assert not (state.args.output / "b-iteration1-0.json").exists()
    attempt = read(state.args.output / "b-iteration1-0.attempt-start.json")
    failure = read(state.args.output / "block-failure.json")
    assert attempt["case_id"] == failure["active_attempt"]["case_id"] == "b"
    assert failure["active_attempt"]["query_id"] is None
    assert state.monitors[0].closed


@pytest.mark.parametrize("drain_fails", [False, True])
def test_timeout_preserves_cancelled_terminal_or_explicit_drain_failure(controlled_campaign, monkeypatch, drain_fails):
    state = controlled_campaign
    state.args.case_id = ["a"]
    original_wait_for = asyncio.wait_for

    async def controlled_wait_for(awaitable, timeout):
        if timeout == 600 or drain_fails:
            raise TimeoutError("controlled timeout")
        return await original_wait_for(awaitable, timeout=1)

    monkeypatch.setattr(harness.asyncio, "wait_for", controlled_wait_for)
    if drain_fails:
        with pytest.raises(TimeoutError):
            state.run()
        failure = read(state.args.output / "block-failure.json")
        assert failure["active_attempt"]["query_id"] == "q1"
        assert failure["error_type"] == "TimeoutError"
        assert not (state.args.output / "a-iteration1-0.json").exists()
    else:
        state.run()
        result = read(state.args.output / "a-iteration1-0.json")
        assert result["harness_timeout"] is True
        assert result["run"]["state"] == "cancelled"
    assert state.queries.cancelled == ["q1"]
    assert state.monitors[0].closed


@pytest.mark.parametrize("defect", ["original_hash", "extraction_hash", "extraction_original", "missing_pdf_extraction"])
def test_bad_source_identity_stops_before_indexing_or_queries(controlled_campaign, defect):
    state = controlled_campaign
    original = state.args.inputs.parent / "original.pdf"
    original.write_bytes(b"controlled original, not a parser fixture")
    extraction = state.args.inputs.parent / "extraction.json"
    save(extraction, {"sha256": "wrong" if defect == "extraction_original" else digest(original)})
    document = {"key": "source", "path": original.name, "format": "pdf",
                "sha256": "wrong" if defect == "original_hash" else digest(original),
                "extraction_path": extraction.name,
                "extraction_sha256": "wrong" if defect == "extraction_hash" else digest(extraction)}
    if defect == "missing_pdf_extraction":
        document.pop("extraction_path")
    state.dataset["documents"] = [document]
    with pytest.raises(ValueError):
        state.run()
    assert not state.indexed and not state.requests
    assert read(state.args.output / "block-failure.json")["error_type"] == "ValueError"


def test_source_change_during_block_is_detected_and_recorded(controlled_campaign):
    state = controlled_campaign
    state.queries.after_create = lambda: state.source.write_text("IDENTITY = 'changed-during-block'\n")
    with pytest.raises(RuntimeError, match="modifiées pendant le bloc"):
        state.run()
    assert read(state.args.output / "source-stability.json")["changed_since_freeze"] == [state.source.name]
