"""Isolated 4B fixed-context KV/context and residency experiments.

Only explicitly supplied Ollama children are started/stopped. Each KV/context
cell has two requests on its own server; no retrieval or answer judgment runs.
The captured prompt is never shortened to make a context size admissible.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import hashlib
import json
import math
import os
import platform
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.api.errors import ApiError  # noqa: E402
from services.api.execution_trace import fingerprint  # noqa: E402
from services.api.ollama import OllamaGateway  # noqa: E402
from services.api.settings import Settings  # noqa: E402
from tools.qualification import replay_trace as replay  # noqa: E402
from tools.qualification.evidence_io import LOCAL_QA, checked_output  # noqa: E402

KV_TYPES = ("f16", "q8_0", "q4_0")
CONTEXT_SIZES = (4096, 8192)
REPETITIONS = 2
MIB = 1048576


def private_file(path: Path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")


def file_hash(path: Path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            result.update(block)
    return result.hexdigest()


def positive_int(value):
    return type(value) is int and value > 0


def host_inventory():
    memory, swap = psutil.virtual_memory(), psutil.swap_memory()
    limits = {}
    for name in ("memory.max", "memory.high", "cpu.max", "cpuset.cpus.effective"):
        path = Path("/sys/fs/cgroup") / name
        limits[name] = path.read_text().strip() if path.is_file() else None
    process = psutil.Process()
    return {"os": platform.platform(), "architecture": platform.machine(), "cpu_description": platform.processor() or None,
            "physical_cpus": psutil.cpu_count(logical=False), "logical_cpus": psutil.cpu_count(),
            "process_cpu_affinity": process.cpu_affinity() if hasattr(process, "cpu_affinity") else None,
            "host_visible_memory_bytes": memory.total, "host_available_bytes": memory.available,
            "swap_total_bytes": swap.total, "swap_used_bytes": swap.used, "cgroup_limits": limits,
            "storage_medium": "not_measured", "browser": "not_exercised",
            "scope_limit": "Host-visible memory and cgroup limits are separate observations; this is not a 16 GB target qualification."}


def captured_plan(path: Path, settings: Settings, request_sequence=None):
    rows, source_sha = replay._verified(path)
    selected, body, wire = replay._request(rows, request_sequence)
    provenance = replay._provenance(rows, source_sha, selected, body)
    if not provenance["context_matches_request"]:
        raise ValueError("A verified context event matching the captured request is required")
    if body["model"] != settings.value("llm", "model"):
        raise ValueError("Profile model differs from the captured 4B model")
    if body["model"] != "qwen3:4b" and provenance["model_lock"] is None:
        raise ValueError("This matrix is restricted to Qwen3-4B, including its locked enhanced alias")
    options = body["options"]
    if type(options.get("seed")) is not int or not positive_int(options.get("num_predict")):
        raise ValueError("A captured integer seed and bounded positive num_predict are required")
    if not positive_int(options.get("num_ctx")) or type(options.get("num_gpu")) is not int or options["num_gpu"] != 0:
        raise ValueError("This host-memory matrix requires a captured explicit CPU request")
    margin = settings.value("retrieval", "context_safety_tokens", 256)
    if type(margin) is not int or margin < 0:
        raise ValueError("The profile context safety margin must be a nonnegative integer")
    context = next(row for row in rows if row["event_sha256"] == provenance["context_event_sha256"])
    following = rows[selected["sequence"]:]
    next_request = next((i for i, row in enumerate(following) if row["phase"] == "llm.request"), len(following))
    terminal = next((row for row in following[:next_request] if row["phase"] == "query.done"), None)
    native = terminal.get("data", {}).get("metrics", {}).get("prompt_eval_count") if terminal else None
    local = context["data"].get("metrics", {}).get("local_prompt_tokens")
    verified_count = positive_int(native) and positive_int(local)
    prompt_tokens = max(native, local) if verified_count else None
    budget = {"native_prompt_eval_count": native, "local_prompt_tokens": local,
              "terminal_event_sha256": terminal["event_sha256"] if terminal else None,
              "prompt_token_bound": prompt_tokens, "output_reserved_tokens": options["num_predict"],
              "safety_tokens": margin,
              "required_tokens": prompt_tokens + options["num_predict"] + margin if verified_count else None,
              "method": "max(captured native prompt count, captured local count) + captured output cap + profile margin; no retokenization"}
    return {"rows": rows, "selected": selected, "body": body, "wire": wire,
            "provenance": provenance, "budget": budget}


def admissibility(plan, num_ctx):
    needed = plan["budget"]["required_tokens"]
    if needed is None:
        return "captured_prompt_token_count_unverified"
    if needed > num_ctx:
        return "captured_prompt_plus_output_and_margin_exceeds_context"
    return None


def request_for_context(plan, num_ctx):
    body = copy.deepcopy(plan["body"])
    body["options"]["num_ctx"] = num_ctx
    wire = httpx.Request("POST", "http://127.0.0.1:1/api/chat", json=body).content
    identical = wire == plan["wire"]
    if num_ctx == plan["body"]["options"]["num_ctx"] and not identical:
        raise ValueError("Unmodified request does not reproduce captured wire bytes")
    return body, wire, {"kind": "fixed_context_replay" if identical else "fixed_context_ablation",
                        "request_relation": "exact_captured_wire" if identical else "num_ctx_only_modified",
                        "modified_request_fields": [] if identical else ["options.num_ctx"],
                        "wire_sha256": hashlib.sha256(wire).hexdigest(), "wire_bytes": len(wire),
                        "messages_sha256": fingerprint(body["messages"]),
                        "response_format_sha256": fingerprint(body["format"]) if "format" in body else None}


def server_environment(models_dir: Path, origin: str, kv_type: str, num_ctx: int):
    # Inherited service options must not silently override one matrix cell.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("OLLAMA_", "LLAMA_ARG_"))}
    env.update({"OLLAMA_HOST": origin, "OLLAMA_MODELS": str(models_dir), "OLLAMA_NO_CLOUD": "1",
                "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_MAX_QUEUE": "1",
                "OLLAMA_CONTEXT_LENGTH": str(num_ctx), "OLLAMA_KV_CACHE_TYPE": kv_type,
                "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_GO_TEMPLATE": "1",
                "OLLAMA_DEBUG_LOG_REQUESTS": "0", "LLAMA_ARG_CACHE_RAM": "256",
                "LLAMA_ARG_CTX_CHECKPOINTS": "2"})
    return env


def kv_allocation(log_text: str, kv_type: str, num_ctx: int):
    records = []
    pattern = re.compile(r"llama_kv_cache[^:]*:.*size\s*=\s*([\d.]+) MiB\s*\(\s*(\d+) cells,.*"
                         r"K \(([^)]+)\):\s*([\d.]+) MiB, V \(([^)]+)\):\s*([\d.]+) MiB")
    for line in log_text.splitlines():
        match = pattern.search(line)
        if match:
            records.append({"total_mib": float(match[1]), "cells": int(match[2]), "key_type": match[3],
                            "key_mib": float(match[4]), "value_type": match[5], "value_mib": float(match[6]),
                            "log_line": line})
    contexts = [int(value) for value in re.findall(r"llama_context:\s+n_ctx\s*=\s*(\d+)", log_text)]
    verified = bool(records and contexts) and all(
        row["key_type"] == kv_type and row["value_type"] == kv_type and row["cells"] == num_ctx for row in records)
    return {"requested_type": kv_type, "requested_num_ctx": num_ctx, "allocations": records,
            "observed_context_sizes": contexts,
            "verified": verified and all(value == num_ctx for value in contexts),
            "verification_basis": "allocation log K/V types, KV cells and n_ctx; environment alone is not verification"}


class FamilyMemory:
    """Sample the owned server and descendants; RSS includes shared-page duplication."""

    def __init__(self, process, path):
        self.process, self.path = process, path
        self.label = "startup"
        self.owned = {(process.pid, process.create_time()): process}
        self.peaks: dict[str, dict] = {}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.error: dict[str, str] | None = None

    def sample(self):
        members = dict(self.owned)
        enumeration_complete = True
        try:
            for process in [self.process, *self.process.children(recursive=True)]:
                members[(process.pid, process.create_time())] = process
        except psutil.Error:
            enumeration_complete = False
        measured, unavailable = [], []
        for identity, process in members.items():
            try:
                if not process.is_running() or process.create_time() != identity[1]:
                    continue
                self.owned[identity] = process
                try:
                    memory = process.memory_full_info()
                    pss = getattr(memory, "pss", None)
                except psutil.AccessDenied:
                    memory, pss = process.memory_info(), None
                measured.append({"pid": process.pid, "created": identity[1], "name": process.name(),
                                 "rss_mib": memory.rss / MIB, "pss_mib": pss / MIB if pss is not None else None})
            except psutil.Error:
                unavailable.append(process.pid)
        rss = sum(row["rss_mib"] for row in measured)
        complete = bool(measured) and enumeration_complete and not unavailable and all(row["pss_mib"] is not None for row in measured)
        pss = sum(row["pss_mib"] for row in measured) if complete else None
        label = self.label
        peak = self.peaks.setdefault(label, {"samples": 0, "rss_sum_peak_mib": 0.0, "pss_sum_peak_mib": None,
                                            "incomplete_pss_samples": 0})
        peak["samples"] += 1
        peak["rss_sum_peak_mib"] = max(peak["rss_sum_peak_mib"], rss)
        if pss is None:
            peak["incomplete_pss_samples"] += 1
        else:
            peak["pss_sum_peak_mib"] = max(peak["pss_sum_peak_mib"] or 0, pss)
        swap = psutil.swap_memory()
        return {"utc": datetime.now(UTC).isoformat(), "label": label, "processes": measured,
                "unreadable_or_exited_pids": unavailable, "rss_sum_mib": rss, "pss_sum_mib": pss,
                "pss_complete": complete, "family_enumeration_complete": enumeration_complete,
                "host_available_mib": psutil.virtual_memory().available / MIB,
                "host_swap_used_mib": swap.used / MIB, "host_swap_in_bytes": swap.sin, "host_swap_out_bytes": swap.sout}

    def run(self):
        try:
            with private_file(self.path) as stream:
                while not self.stop_event.is_set():
                    stream.write(json.dumps(self.sample(), allow_nan=False) + "\n")
                    stream.flush()
                    self.stop_event.wait(0.25)
        except (OSError, psutil.Error) as error:
            self.error = {"type": type(error).__name__, "message": str(error)}

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=5)


class OwnedOllama:
    """A fresh loopback listener verified to belong to the child just created."""

    def __init__(self, binary, models_dir, directory, label, kv_type, num_ctx):
        self.binary, self.models_dir, self.directory = binary, models_dir, directory
        self.label, self.kv_type, self.num_ctx = label, kv_type, num_ctx
        self.log_path = directory / f"{label}.server.log"
        self.memory_path = directory / f"{label}.memory.jsonl"
        self.child: subprocess.Popen | None = None
        self.process: psutil.Process | None = None
        self.sampler: FamilyMemory | None = None
        self.log: TextIO | None = None
        self.stop_report: dict[str, Any] = {"all_owned_processes_stopped": True, "created_processes": []}
        self.origin = ""
        self.environment: dict[str, str] = {}
        self.version: Any = None

    def start(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        self.origin = f"http://127.0.0.1:{port}"
        env = server_environment(self.models_dir, self.origin, self.kv_type, self.num_ctx)
        self.environment = {key: value for key, value in env.items() if key.startswith(("OLLAMA_", "LLAMA_ARG_"))}
        self.log = private_file(self.log_path)
        self.child = subprocess.Popen([str(self.binary), "serve"], stdout=self.log, stderr=subprocess.STDOUT,
                                      env=env, start_new_session=True)
        self.process = psutil.Process(self.child.pid)
        self.sampler = FamilyMemory(self.process, self.memory_path)
        self.sampler.thread.start()
        deadline = time.monotonic() + 30
        with httpx.Client(base_url=self.origin, timeout=1, trust_env=False, follow_redirects=False) as client:
            while time.monotonic() < deadline:
                if self.child.poll() is not None:
                    raise RuntimeError("Owned Ollama exited before readiness")
                # A port race must never send a documentary prompt to another server.
                owned_listener = any(connection.status == psutil.CONN_LISTEN and connection.laddr
                                     and connection.laddr.ip == "127.0.0.1" and connection.laddr.port == port
                                     for connection in self.process.net_connections(kind="tcp"))
                if owned_listener:
                    try:
                        response = client.get("/api/tags")
                        if response.status_code == 200:
                            version = client.get("/api/version")
                            if version.status_code == 200:
                                self.version = version.json()
                            return
                    except httpx.HTTPError:
                        pass
                time.sleep(0.1)
        raise RuntimeError("Owned Ollama did not become ready on its own loopback listener")

    def phase(self, label):
        if self.sampler:
            self.sampler.label = label

    def stop(self):
        self.phase("shutdown")
        owned = dict(self.sampler.owned) if self.sampler else {}
        if self.process:
            try:
                for process in [self.process, *self.process.children(recursive=True)]:
                    owned[(process.pid, process.create_time())] = process
            except psutil.Error:
                pass
        running = []
        for (_pid, created), process in owned.items():
            try:
                if process.is_running() and process.create_time() == created:
                    running.append(process)
            except psutil.NoSuchProcess:
                pass
        parent_pid = self.process.pid if self.process else None
        survivors = []
        # Let the still-running server reap its runner before stopping the server.
        # Otherwise an unreaping container PID1 can retain orphan runner zombies.
        for group in ([process for process in running if process.pid != parent_pid],
                      [process for process in running if process.pid == parent_pid]):
            if not group:
                continue
            for process in group:
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(group, timeout=5)
            for process in alive:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            _, remaining = psutil.wait_procs(alive, timeout=5)
            survivors.extend(remaining)
        if self.child:
            try:
                self.child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                survivors.append(self.child)
        if self.sampler:
            self.sampler.close()
        if self.log:
            self.log.close()
        self.stop_report = {"all_owned_processes_stopped": not survivors,
                            "created_processes": [{"pid": pid, "created": created} for pid, created in owned],
                            "surviving_pids": sorted({process.pid for process in survivors})}
        return self.stop_report

    def evidence(self):
        logs = self.log_path.read_bytes() if self.log_path.exists() else b""
        return {"origin": self.origin, "version": self.version, "environment": self.environment, "shutdown": self.stop_report,
                "log_path": str(self.log_path), "log_sha256": hashlib.sha256(logs).hexdigest(),
                "kv_allocation": kv_allocation(logs.decode("utf-8", errors="replace"), self.kv_type, self.num_ctx),
                "memory": {"scope": "owned Ollama server and all observed descendants; excludes client/application",
                           "interval_seconds": 0.25, "rss_limit": "sum counts shared pages in each process; sampled peak, not an absolute maximum",
                           "pss_limit": "PSS reported only for complete readable family samples",
                           "path": str(self.memory_path),
                           "sha256": file_hash(self.memory_path) if self.memory_path.exists() else None,
                           "peaks_by_phase": self.sampler.peaks if self.sampler else {},
                           "sampling_error": self.sampler.error if self.sampler else "sampler_not_started"}}


def read_ps(client):
    response = client.get("/api/ps")
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise ValueError("Runtime residence inventory is not verifiable")
    return value


def verify_four_b(client, plan):
    identity = replay._verify_runtime(client, plan["body"], plan["selected"]["data"]["verified_model_identity"])
    details = identity["model_record"].get("details", {})
    if details.get("family") != "qwen3" or details.get("parameter_size") != "4.0B" or details.get("quantization_level") != "Q4_K_M":
        raise ValueError("Runtime inventory is not the captured Qwen3-4B Q4_K_M model")
    return identity


def native_request(client, plan, num_ctx, repeat):
    body, wire, relation = request_for_context(plan, num_ctx)
    report: dict[str, Any] = {**relation, "repeat": repeat, "request": body, "wire_body_utf8": wire.decode(),
                             "status": "started", "generation_request_attempted": False,
                             "native_events": [], "native_final_event": None, "received_done": False,
                             "response": "", "client_first_content_ms": None, "response_capture_limit_reached": False}
    raw = bytearray()
    started: float | None = None
    try:
        report["verified_model_identity"] = verify_four_b(client, plan)
        report["ps_before"] = read_ps(client)
        request = client.build_request("POST", "/api/chat", content=wire, headers={"Content-Type": "application/json"})
        report["generation_request_attempted"] = True
        started = time.monotonic()
        response = client.send(request, stream=True)
        try:
            report["http_status"] = response.status_code
            replay._consume(response, report, raw, started=started, maximum_bytes=replay.MAX_RESPONSE_BYTES)
        finally:
            response.close()
        report["client_generation_elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
        report["ps_after"] = read_ps(client)
        observed = report["native_final_event"].get("prompt_eval_count")
        report["prompt_token_count_matches_capture"] = observed == plan["budget"]["native_prompt_eval_count"]
        report["status"] = "completed" if report["prompt_token_count_matches_capture"] else "prompt_token_count_mismatch"
    except (httpx.HTTPError, ValueError, OSError) as error:
        report.update(status="error", error={"type": type(error).__name__, "message": str(error)})
    if report["generation_request_attempted"] and "ps_after" not in report:
        try:
            report["ps_after"] = read_ps(client)
        except (httpx.HTTPError, ValueError) as error:
            report["ps_after_error"] = {"type": type(error).__name__, "message": str(error)}
    report["native_raw"] = {"base64": base64.b64encode(raw).decode(), "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(), "encoding": "http_decoded_body_bytes"}
    report["response_sha256"] = hashlib.sha256(report["response"].encode()).hexdigest()
    if started is not None and "client_generation_elapsed_ms" not in report:
        report["client_generation_elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
    return report


async def residency_sequence(server, plan, settings, *, transport=None, read_timeout=300.0):
    """Real gateway, including its finally/residency path; transport injection is tests only."""
    reports = []
    for label, policy in (("keep", "keep"), ("unload", "unload"), ("adaptive_normal", "adaptive"),
                          ("configured_threshold_probe", "adaptive")):
        profile = copy.deepcopy(settings.profile)
        options = plan["body"]["options"]
        llm = profile.setdefault("llm", {})
        llm.update(base_url=server.origin, model=plan["body"]["model"], accelerator="cpu", residency_policy=policy,
                   num_ctx=options["num_ctx"], num_predict=options["num_predict"], seed=options["seed"],
                   temperature=options.get("temperature", 0.2), top_p=options.get("top_p", 0.9),
                   threads_max=options.get("num_thread", 4), keep_alive=plan["body"].get("keep_alive", "10m"),
                   idle_read_timeout_seconds=read_timeout)
        report: dict[str, Any] = {"label": label, "policy": policy, "status": "started", "events": [],
                                 "response": "", "client_first_content_ms": None, "generation_request_attempted": False,
                                 "probe_kind": "configured_threshold_probe" if label == "configured_threshold_probe" else "profile_policy",
                                 "messages_sha256": plan["provenance"]["messages_sha256"],
                                 "response_format_sha256": plan["provenance"]["response_format_sha256"]}
        if label == "configured_threshold_probe":
            total_mib = psutil.virtual_memory().total / MIB
            profile.setdefault("resources", {}).update(host_available_min_mib=math.ceil(total_mib) + 1,
                                                       embedding_load_peak_estimate_mib=0)
            llm["adaptive_reserve_margin_mib"] = 0
            report["threshold_configuration"] = {"host_total_mib": total_mib,
                "host_available_min_mib": profile["resources"]["host_available_min_mib"],
                "embedding_load_peak_estimate_mib": 0, "adaptive_reserve_margin_mib": 0,
                "interpretation": "configured threshold above total physical memory; not naturally observed RAM pressure"}
        configured = Settings(settings.root, profile)
        gateway = OllamaGateway(configured)
        if transport is not None:
            await gateway.client.aclose()
            gateway.client = httpx.AsyncClient(base_url=server.origin, transport=transport,
                                               trust_env=False, follow_redirects=False)
        started: float | None = None

        async def capture_request(request, captured_report=report):
            nonlocal started
            if request.url.path == "/api/chat":
                if request.content != plan["wire"]:
                    raise ValueError("Gateway residency request differs from the captured exact wire")
                captured_report.update(request=json.loads(request.content), wire_body_utf8=request.content.decode(),
                                       wire_sha256=hashlib.sha256(request.content).hexdigest(), generation_request_attempted=True)
                started = time.monotonic()

        gateway.client.event_hooks["request"].append(capture_request)
        server.phase(label)
        try:
            if gateway.chat_options(options["num_predict"], cpu=True) != options:
                report.update(status="NOT_RUN", reason="captured_options_not_representable_by_gateway")
            elif gateway.expected_identity()["digest"] != plan["selected"]["data"]["verified_model_identity"]["digest"]:
                report.update(status="NOT_RUN", reason="profile_manifest_differs_from_capture")
            else:
                before = await gateway.client.get("/api/ps")
                before.raise_for_status()
                report["ps_before"] = before.json()
                async for event in gateway.stream(plan["body"]["messages"], asyncio.Event(),
                                                   output_tokens=options["num_predict"], response_format=plan["body"].get("format")):
                    report["events"].append(event)
                    if event["type"] == "delta":
                        if report["client_first_content_ms"] is None and started is not None:
                            report["client_first_content_ms"] = round((time.monotonic() - started) * 1000, 3)
                        report["response"] += event["text"]
                    if event["type"] == "done":
                        report["native_counters"] = event["metrics"]
                        report["client_generation_elapsed_ms"] = round((time.monotonic() - started) * 1000, 3) if started else None
                report["residency_decision"] = gateway.last_residency
                after = await gateway.client.get("/api/ps")
                after.raise_for_status()
                report["ps_after"] = after.json()
                records = report["ps_after"].get("models")
                if not isinstance(records, list):
                    raise ValueError("Residence inventory after the gateway call is invalid")
                resident = any(row.get("name", row.get("model")) == plan["body"]["model"]
                               and row.get("digest") == plan["selected"]["data"]["verified_model_identity"]["digest"]
                               for row in records)
                decision = (gateway.last_residency or {}).get("action")
                verified = (decision == "kept" and resident) or (decision == "unloaded_verified" and not resident)
                if label == "configured_threshold_probe":
                    verified = decision == "unloaded_verified" and not resident
                report.update(resident_after=resident, residency_verified=verified,
                              prompt_token_count_matches_capture=report.get("native_counters", {}).get("prompt_eval_count")
                              == plan["budget"]["native_prompt_eval_count"])
                report["status"] = "completed" if verified and report["prompt_token_count_matches_capture"] else "error_or_unverified"
        except (ApiError, httpx.HTTPError, OSError, ValueError) as error:
            report.update(status="error", error={"type": type(error).__name__, "message": str(error)})
        finally:
            report.setdefault("residency_decision", gateway.last_residency)
            if report["generation_request_attempted"] and "ps_after" not in report:
                try:
                    after = await gateway.client.get("/api/ps")
                    after.raise_for_status()
                    report["ps_after"] = after.json()
                except (httpx.HTTPError, ValueError) as error:
                    report["ps_after_error"] = {"type": type(error).__name__, "message": str(error)}
            await gateway.close()
        report["response_sha256"] = hashlib.sha256(report["response"].encode()).hexdigest()
        reports.append(report)
    return reports


def run_matrix(trace: Path, binary: Path, models_dir: Path, profile: Path, output: Path, *,
               request_sequence=None, read_timeout=300.0, transport=None, async_transport=None, server_factory=None):
    if not 0 < read_timeout <= 3600:
        raise ValueError("Read timeout is out of bounds")
    settings = Settings.load(profile)
    plan = captured_plan(Path(trace), settings, request_sequence)
    binary, models_dir = Path(binary).resolve(), Path(models_dir).resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK) or not models_dir.is_dir():
        raise ValueError("An executable Ollama binary and existing local model store are required")
    substitute = transport is not None or async_transport is not None or server_factory is not None
    if substitute and (transport is None or async_transport is None or server_factory is None):
        raise ValueError("Test substitution requires explicit sync transport, async transport and server factory")
    output = checked_output(Path(output), [LOCAL_QA], sources=(Path(trace), Path(profile), binary))
    output.parent.mkdir(parents=True, exist_ok=True)
    directory = output.with_name(output.stem + ".artifacts")
    directory.mkdir(mode=0o700, exist_ok=False)
    report: dict[str, Any] = {"kind": "fixed_context_runtime_matrix", "status": "started",
        "started_utc": datetime.now(UTC).isoformat(), "transport_kind": "explicit_test_substitute" if substitute else "native_http",
        "runner_sha256": file_hash(Path(__file__)), "profile_sha256": file_hash(Path(profile)),
        "read_timeout_seconds": read_timeout,
        "ollama_binary": str(binary), "ollama_binary_sha256": file_hash(binary), "models_dir": str(models_dir),
        "execution_scope": "captured Qwen3-4B Q4_K_M request with explicit num_gpu=0",
        "server_options_captured": plan["selected"]["data"].get("server_options_requested"),
        "server_options_captured_verified": plan["selected"]["data"].get("server_options_verified", False),
        "host": host_inventory(), "d07_eligible": False,
        "d07_ineligible_reason": "fixed-context server-family diagnostic; no full application, browser, representative corpus or target-host acceptance scenario",
        "provenance": plan["provenance"], "admission_budget": plan["budget"], "cells": [], "residency": None,
        "quality_judgment": "NOT_ASSESSED", "measurement_limit": "One captured context, two sequential repeats per cell. Output identity is not correctness; no retrieval or answer renderer runs. First request is a new-server observation, not a cold filesystem-cache guarantee."}
    factory = server_factory or OwnedOllama
    with private_file(output) as stream:
        try:
            for kv_type in KV_TYPES:
                for num_ctx in CONTEXT_SIZES:
                    cell: dict[str, Any] = {"kv_type": kv_type, "num_ctx": num_ctx, "runs": [], "status": "started"}
                    report["cells"].append(cell)
                    refusal = admissibility(plan, num_ctx)
                    if refusal:
                        cell.update(status="NOT_RUN", reason=refusal)
                        continue
                    server = factory(binary, models_dir, directory, f"{kv_type}-{num_ctx}", kv_type, num_ctx)
                    try:
                        server.start()
                        with httpx.Client(base_url=server.origin, transport=transport, trust_env=False, follow_redirects=False,
                                          timeout=httpx.Timeout(read_timeout, connect=min(5, read_timeout))) as client:
                            for repeat in range(REPETITIONS):
                                server.phase(f"repeat-{repeat}")
                                run = native_request(client, plan, num_ctx, repeat)
                                run["server_sequence"] = "new_server_first_request" if repeat == 0 else "same_server_repeat"
                                cell["runs"].append(run)
                                if run["status"] != "completed":
                                    break
                    except (OSError, RuntimeError, psutil.Error) as error:
                        cell["error"] = {"type": type(error).__name__, "message": str(error)}
                    finally:
                        shutdown = server.stop()
                        cell["server"] = server.evidence()
                    complete = len(cell["runs"]) == REPETITIONS and all(run["status"] == "completed" for run in cell["runs"])
                    cell["status"] = "completed" if complete and cell["server"]["kv_allocation"]["verified"] else "error_or_unverified"
                    if not shutdown["all_owned_processes_stopped"]:
                        raise RuntimeError("Owned child remains alive; later servers will not be started")
            captured_ctx = plan["body"]["options"]["num_ctx"]
            refusal = admissibility(plan, captured_ctx)
            residence: dict[str, Any] = {"status": "NOT_RUN" if refusal else "started", "reason": refusal, "runs": []}
            report["residency"] = residence
            if not refusal:
                server = factory(binary, models_dir, directory, "residency-q8_0", "q8_0", captured_ctx)
                try:
                    server.start()
                    with httpx.Client(base_url=server.origin, transport=transport, trust_env=False, follow_redirects=False,
                                      timeout=httpx.Timeout(read_timeout, connect=min(5, read_timeout))) as client:
                        residence["verified_model_identity"] = verify_four_b(client, plan)
                    residence["runs"] = asyncio.run(residency_sequence(server, plan, settings,
                                                                      transport=async_transport, read_timeout=read_timeout))
                except (OSError, RuntimeError, psutil.Error, ValueError, httpx.HTTPError) as error:
                    residence["error"] = {"type": type(error).__name__, "message": str(error)}
                finally:
                    shutdown = server.stop()
                    residence["server"] = server.evidence()
                residence["status"] = "completed" if len(residence["runs"]) == 4 and all(
                    run["status"] == "completed" for run in residence["runs"]) and residence["server"]["kv_allocation"]["verified"] else "error_or_unverified"
                if not shutdown["all_owned_processes_stopped"]:
                    raise RuntimeError("Owned residency child remains alive")
            statuses = [cell["status"] for cell in report["cells"]] + [residence["status"]]
            report["status"] = "completed" if all(status == "completed" for status in statuses) else "partial"
        except (OSError, RuntimeError, psutil.Error, KeyboardInterrupt) as error:
            report.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "error",
                          error={"type": type(error).__name__, "message": str(error)})
        finally:
            report["finished_utc"] = datetime.now(UTC).isoformat()
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("trace", "ollama-bin", "models-dir", "profile", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--request-sequence", type=int)
    parser.add_argument("--read-timeout", type=float, default=300)
    args = parser.parse_args(argv)
    try:
        result = run_matrix(args.trace, args.ollama_bin, args.models_dir, args.profile, args.output,
                            request_sequence=args.request_sequence, read_timeout=args.read_timeout)
        print(json.dumps({"status": result["status"], "output": str(args.output),
                          "cells": [{"kv_type": row["kv_type"], "num_ctx": row["num_ctx"], "status": row["status"]}
                                    for row in result["cells"]], "quality_judgment": result["quality_judgment"]}))
        statuses = [row["status"] for row in result["cells"]] + [result["residency"]["status"]] if result["residency"] else []
        return 0 if statuses and all(value in {"completed", "NOT_RUN"} for value in statuses) and "completed" in statuses else 1
    except (OSError, ValueError, ApiError) as error:
        print(json.dumps({"status": "refused", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
