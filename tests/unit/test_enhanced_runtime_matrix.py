"""Explicit simulated server/HTTP transport only; never starts Ollama or loads a model."""

import copy
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from services.api.execution_trace import ExecutionTrace, fingerprint
from services.api.settings import Settings
from tools.qualification import enhanced_runtime_matrix as matrix

MODEL = {"name": "qwen3:4b", "digest": "a" * 64,
         "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M"}}


def trace_fixture(tmp_path, *, prompt_tokens=1000, native_count=True, mutate=None):
    manifest = tmp_path / "model-identity.json"
    manifest.write_text(json.dumps({"model": MODEL}))
    profile = {"app": {"data_dir": "trace-data"}, "trace": {"mode": "full"},
               "llm": {"model": MODEL["name"], "model_manifest": str(manifest), "accelerator": "cpu"},
               "retrieval": {"context_safety_tokens": 256},
               "resources": {"host_available_min_mib": 1536, "embedding_load_peak_estimate_mib": 512}}
    settings = Settings(tmp_path, profile)
    body = {"model": MODEL["name"], "messages": [{"role": "system", "content": "Preuves exactes seulement."},
             {"role": "user", "content": "PRIVATE-CONTEXT : zéro = 0 V, limite = 36 V 😀"}],
            "stream": True, "think": False, "keep_alive": "10m",
            "options": {"num_ctx": 8192, "num_predict": 100, "temperature": 0.2, "top_p": 0.9,
                        "seed": 0, "num_gpu": 0, "num_thread": 4},
            "format": {"type": "object", "properties": {"reference": {"enum": ["R001", "R002"]}}}}
    if mutate:
        mutate(body)
    wire = httpx.Request("POST", "http://127.0.0.1:1/api/chat", json=body).content
    trace = ExecutionTrace(settings, "runtime-matrix")
    trace.record("context", {"messages": body["messages"], "retained": [{"text": "0 V ; 36 V"}],
                             "metrics": {"local_prompt_tokens": prompt_tokens}})
    trace.record("llm.request", {"body": body, "wire_body_utf8": wire.decode(), "wire_bytes": len(wire),
                                 "wire_sha256": hashlib.sha256(wire).hexdigest(),
                                 "verified_model_identity": {"digest": MODEL["digest"], "source": "/api/tags"}})
    metrics = {"prompt_eval_count": prompt_tokens, "prompt_eval_cached_count": 250} if native_count else {}
    trace.record("query.done", {"status": "done", "metrics": metrics})
    trace.close()
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("explicit test profile substitute\n")
    return settings, profile_path, trace.path, body, wire


def test_plan_reserves_full_output_and_margin_without_adding_cached_subset_twice(tmp_path):
    settings, _, path, body, wire = trace_fixture(tmp_path, prompt_tokens=4000)
    plan = matrix.captured_plan(path, settings)
    assert plan["budget"]["required_tokens"] == 4356
    assert matrix.admissibility(plan, 4096) == "captured_prompt_plus_output_and_margin_exceeds_context"
    assert matrix.admissibility(plan, 8192) is None
    changed, changed_wire, relation = matrix.request_for_context(plan, 4096)
    expected = copy.deepcopy(body)
    expected["options"]["num_ctx"] = 4096
    assert changed == expected and json.loads(changed_wire) == expected
    assert relation["kind"] == "fixed_context_ablation" and relation["modified_request_fields"] == ["options.num_ctx"]
    exact, exact_wire, exact_relation = matrix.request_for_context(plan, 8192)
    assert exact == body and exact_wire == wire and exact_relation["kind"] == "fixed_context_replay"
    assert exact_relation["messages_sha256"] == relation["messages_sha256"] == fingerprint(body["messages"])
    assert exact_relation["response_format_sha256"] == relation["response_format_sha256"]


@pytest.mark.parametrize("change", [lambda body: body["options"].pop("seed"),
                                     lambda body: body["options"].update(seed=False),
                                     lambda body: body["options"].update(num_predict=-1),
                                     lambda body: body["options"].update(num_gpu=False)])
def test_unbounded_or_implicit_request_options_are_refused_before_server_use(tmp_path, change):
    settings, _, path, _, _ = trace_fixture(tmp_path, mutate=change)
    with pytest.raises(ValueError):
        matrix.captured_plan(path, settings)


def test_missing_native_token_count_never_assumes_the_smaller_context_fits(tmp_path):
    settings, _, path, _, _ = trace_fixture(tmp_path, native_count=False)
    plan = matrix.captured_plan(path, settings)
    assert plan["budget"]["required_tokens"] is None
    assert matrix.admissibility(plan, 8192) == "captured_prompt_token_count_unverified"


def test_server_environment_isolated_options_and_correct_cache_names(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://192.0.2.1:11434")
    monkeypatch.setenv("LLAMA_ARG_CACHE_RAM", "9999")
    monkeypatch.setenv("LLAMA_ARG_CTX_CHECKPOINTS", "99")
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "24")
    env = matrix.server_environment(tmp_path, "http://127.0.0.1:11590", "q4_0", 4096)
    assert env["OLLAMA_HOST"] == "http://127.0.0.1:11590"
    assert env["OLLAMA_MODELS"] == str(tmp_path)
    assert env["OLLAMA_NUM_PARALLEL"] == env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert env["LLAMA_ARG_CACHE_RAM"] == "256" and env["LLAMA_ARG_CTX_CHECKPOINTS"] == "2"
    assert env["OLLAMA_KV_CACHE_TYPE"] == "q4_0" and env["OLLAMA_FLASH_ATTENTION"] == "1"


def allocation_log(kv="q8_0", context=8192):
    return (f"llama_context: n_ctx                 = {context}\n"
            f"llama_kv_cache: size =  612.00 MiB (  {context} cells,  36 layers,  1/1 seqs), "
            f"K ({kv}):  306.00 MiB, V ({kv}):  306.00 MiB\n")


@pytest.mark.parametrize("kv", matrix.KV_TYPES)
def test_kv_verification_requires_native_allocation_and_context_records(kv):
    observed = matrix.kv_allocation(allocation_log(kv), kv, 8192)
    assert observed["verified"] and observed["allocations"][0]["key_type"] == kv
    assert not matrix.kv_allocation(f"OLLAMA_KV_CACHE_TYPE:{kv}", kv, 8192)["verified"]
    assert not matrix.kv_allocation(allocation_log(kv, 4096), kv, 8192)["verified"]
    assert not matrix.kv_allocation(allocation_log("wrong"), kv, 8192)["verified"]


class SimulatedServers:
    """Records exclusive server ownership; no OS process is created."""

    def __init__(self, *, prompt_tokens=1000, wrong_digest=False, survive=False):
        self.started, self.stopped, self.active, self.states, self.requests = [], [], 0, {}, []
        self.prompt_tokens, self.wrong_digest, self.survive = prompt_tokens, wrong_digest, survive

    def factory(self, binary, models, directory, label, kv, context):
        owner = self
        origin = f"http://127.0.0.1:{20000 + len(self.states)}"
        self.states[origin] = {"resident": False, "context": context}

        class Server:
            def __init__(self):
                self.origin = origin

            def start(self):
                assert owner.active == 0, "servers must be sequential"
                owner.active += 1
                owner.started.append(label)

            def phase(self, phase):
                pass

            def stop(self):
                owner.active -= 1
                owner.stopped.append(label)
                return {"all_owned_processes_stopped": not owner.survive}

            def evidence(self):
                return {"kv_allocation": matrix.kv_allocation(allocation_log(kv, context), kv, context),
                        "memory": {"kind": "explicit_test_substitute", "peaks_by_phase": {}}}

        return Server()

    def handler(self, request):
        self.requests.append(request)
        state = self.states[f"{request.url.scheme}://{request.url.host}:{request.url.port}"]
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{**MODEL, "digest": "b" * 64 if self.wrong_digest else MODEL["digest"]}]})
        if request.url.path == "/api/ps":
            running = [{**MODEL, "context_length": state["context"], "size_vram": 0, "size": 2000 * matrix.MIB}]
            return httpx.Response(200, json={"models": running if state["resident"] else []})
        if request.url.path == "/api/generate":
            body = json.loads(request.content)
            assert body["prompt"] == "" and body["keep_alive"] == 0
            state["resident"] = False
            return httpx.Response(200, json={"done": True, "done_reason": "unload"})
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["options"]["seed"] == 0
        state["resident"] = True
        events = [{"message": {"content": '{"reference":"R001"}'}, "done": False},
                  {"message": {"content": ""}, "done": True, "done_reason": "stop",
                   "prompt_eval_count": self.prompt_tokens, "eval_count": 5, "prompt_eval_cached_count": 250}]
        return httpx.Response(200, content="\n".join(json.dumps(event) for event in events) + "\n")


def run_simulated(tmp_path, monkeypatch, *, prompt_tokens=1000, native_count=True, wrong_digest=False, survive=False):
    settings, profile, trace, body, wire = trace_fixture(tmp_path, prompt_tokens=prompt_tokens, native_count=native_count)
    monkeypatch.setattr(matrix.Settings, "load", lambda path: settings)
    monkeypatch.setattr(matrix, "LOCAL_QA", tmp_path / "qa")
    monkeypatch.setattr(matrix, "host_inventory", lambda: {"kind": "explicit_test_substitute"})
    monkeypatch.setattr(matrix.psutil, "cpu_count", lambda logical=False: 8)
    monkeypatch.setattr(matrix.psutil, "virtual_memory", lambda: SimpleNamespace(available=10000 * matrix.MIB, total=16384 * matrix.MIB))
    binary = tmp_path / "ollama-test-substitute"
    binary.write_text("Never executed\n")
    binary.chmod(0o700)
    models = tmp_path / "models"
    models.mkdir()
    server = SimulatedServers(prompt_tokens=prompt_tokens, wrong_digest=wrong_digest, survive=survive)
    output = tmp_path / "qa" / "matrix.json"
    result = matrix.run_matrix(trace, binary, models, profile, output,
                               transport=httpx.MockTransport(server.handler), async_transport=httpx.MockTransport(server.handler),
                               server_factory=server.factory)
    return result, server, body, wire, output


def test_full_matrix_exact_wire_ablation_and_gateway_residence_are_distinct(tmp_path, monkeypatch):
    result, server, body, wire, output = run_simulated(tmp_path, monkeypatch)
    assert result["status"] == "completed" and result["quality_judgment"] == "NOT_ASSESSED"
    assert result["transport_kind"] == "explicit_test_substitute"
    assert len(server.started) == 7 and server.started == server.stopped and server.active == 0
    assert len(result["cells"]) == 6 and all(len(cell["runs"]) == 2 for cell in result["cells"])
    for cell in result["cells"]:
        for run in cell["runs"]:
            assert run["request"]["messages"] == body["messages"] and run["request"]["format"] == body["format"]
            assert run["client_first_content_ms"] is not None and run["native_final_event"]["eval_count"] == 5
            assert run["prompt_token_count_matches_capture"] and run["ps_after"]["models"]
            if cell["num_ctx"] == 8192:
                assert run["wire_body_utf8"].encode() == wire and run["kind"] == "fixed_context_replay"
            else:
                assert run["kind"] == "fixed_context_ablation"
    residence = result["residency"]["runs"]
    assert [row["label"] for row in residence] == ["keep", "unload", "adaptive_normal", "configured_threshold_probe"]
    assert [row["resident_after"] for row in residence] == [True, False, True, False]
    assert all(row["wire_body_utf8"].encode() == wire and row["residency_verified"] for row in residence)
    assert residence[-1]["threshold_configuration"]["host_available_min_mib"] == 16385
    assert "not naturally observed RAM pressure" in residence[-1]["threshold_configuration"]["interpretation"]
    assert len([request for request in server.requests if request.url.path == "/api/chat"]) == 16
    assert len([request for request in server.requests if request.url.path == "/api/generate"]) == 2
    assert json.loads(output.read_text()) == result and output.stat().st_mode & 0o777 == 0o600


def test_4096_cells_not_run_without_any_prompt_truncation(tmp_path, monkeypatch):
    result, server, body, _, _ = run_simulated(tmp_path, monkeypatch, prompt_tokens=4000)
    assert result["status"] == "partial"
    assert len(server.started) == 4
    assert all(row["status"] == "NOT_RUN" and not row["runs"] for row in result["cells"] if row["num_ctx"] == 4096)
    sent = [json.loads(request.content) for request in server.requests if request.url.path == "/api/chat"]
    assert len(sent) == 10 and all(item["messages"] == body["messages"] and item["options"]["num_ctx"] == 8192 for item in sent)


def test_no_servers_when_native_token_budget_cannot_be_verified(tmp_path, monkeypatch):
    result, server, _, _, _ = run_simulated(tmp_path, monkeypatch, native_count=False)
    assert not server.started and not server.requests
    assert all(cell["status"] == "NOT_RUN" for cell in result["cells"])
    assert result["residency"]["status"] == "NOT_RUN"


def test_digest_mismatch_never_transmits_context_and_still_stops_owned_servers(tmp_path, monkeypatch):
    result, server, _, _, _ = run_simulated(tmp_path, monkeypatch, wrong_digest=True)
    assert result["status"] == "partial"
    assert all(request.url.path == "/api/tags" for request in server.requests)
    assert server.started == server.stopped and server.active == 0
    assert all(cell["status"] == "error_or_unverified" for cell in result["cells"])


def test_surviving_owned_child_prevents_starting_any_later_server(tmp_path, monkeypatch):
    result, server, _, _, _ = run_simulated(tmp_path, monkeypatch, survive=True)
    assert result["status"] == "error" and len(server.started) == 1
    assert result["residency"] is None
    assert "later servers will not be started" in result["error"]["message"]


class ProcessDouble:
    def __init__(self, pid, *, rss=100, pss=60, running=True, children=()):
        self.pid, self.rss, self.pss, self.running, self.descendants = pid, rss, pss, running, children
        self.terminated = self.killed = False

    def create_time(self):
        return self.pid + 0.5

    def is_running(self):
        return self.running

    def children(self, recursive):
        assert recursive
        return self.descendants

    def memory_full_info(self):
        return SimpleNamespace(rss=self.rss * matrix.MIB, pss=self.pss * matrix.MIB if self.pss is not None else None)

    def name(self):
        return "explicit-process-double"

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def test_memory_totals_cover_parent_and_child_and_unknown_pss_stays_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix.psutil, "virtual_memory", lambda: SimpleNamespace(available=4096 * matrix.MIB))
    child = ProcessDouble(2, rss=50, pss=20)
    parent = ProcessDouble(1, children=[child])
    sampler = matrix.FamilyMemory(parent, tmp_path / "unused.jsonl")
    first = sampler.sample()
    assert first["rss_sum_mib"] == 150 and first["pss_sum_mib"] == 80 and first["pss_complete"]
    assert {row["pid"] for row in first["processes"]} == {1, 2}
    child.pss = None
    second = sampler.sample()
    assert second["rss_sum_mib"] == 150 and second["pss_sum_mib"] is None and not second["pss_complete"]
    assert sampler.peaks["startup"]["incomplete_pss_samples"] == 1
    child.running = False
    parent.descendants = []
    third = sampler.sample()
    assert third["rss_sum_mib"] == 100 and third["pss_sum_mib"] == 60


def test_shutdown_only_signals_owned_live_process_identities(tmp_path, monkeypatch):
    child = ProcessDouble(2)
    stale = ProcessDouble(99, running=False)
    unrelated = ProcessDouble(100)
    parent = ProcessDouble(1, children=[child])
    server = matrix.OwnedOllama(tmp_path / "not-executed", tmp_path, tmp_path, "test", "f16", 8192)
    server.process = parent
    server.sampler = SimpleNamespace(owned={(99, 99.5): stale}, close=lambda: None)
    waited = []

    def wait(procs, timeout):
        waited.append([process.pid for process in procs])
        return procs, []

    monkeypatch.setattr(matrix.psutil, "wait_procs", wait)
    result = server.stop()
    assert parent.terminated and child.terminated
    assert not stale.terminated and not unrelated.terminated and not unrelated.killed
    assert result["all_owned_processes_stopped"]
    assert [group for group in waited if group] == [[2], [1]]
